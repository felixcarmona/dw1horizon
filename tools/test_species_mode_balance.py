"""Mode payload layout and the production shared-id finisher lookup."""
import copy
import ctypes
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import species as S


class ModeBalance(unittest.TestCase):
    def test_sector_rows_keep_animation_slots_and_both_scalar_blocks(self):
        s = dict(level='ultimate', techniques=['Water Blit', None, 'Blasting Spout'],
                 finisher=dict(power=210, mpCost=40, element='ice'),
                 off=dict(level='champion', techniques=[None, None, 'Blasting Spout'],
                          finisher=dict(power=150, mpCost=40, element='ice')))
        with patch.object(S, 'originals', side_effect=AssertionError('disc read')):
            row, = S.balance_swaps({24: s})
        self.assertEqual(len(row), 44)
        self.assertEqual(struct.unpack_from('<H', row)[0], 24)
        self.assertEqual(row[2:5], bytes([S.id_of('techs', 'Water Blit', 'test'), 255, 90]))
        self.assertEqual(row[23:26], bytes([255, 255, 90]))
        self.assertEqual(struct.unpack_from('<BHBB', row, 18), (90, 210, 40, 4))
        self.assertEqual(struct.unpack_from('<BHBB', row, 39), (90, 150, 40, 4))

    def test_level_moved_species_require_every_mode_balance_field(self):
        original = S.load_content()[59]
        for path in [('finisher',), ('off', 'finisher'), ('off', 'stats'), ('off', 'techniques'),
                     ('evolution', 'gains', 'hp')]:
            s = copy.deepcopy(original)
            parent = s
            for key in path[:-1]: parent = parent[key]
            del parent[path[-1]]
            with self.subTest(path=path), self.assertRaises(SystemExit):
                S.validate(s)

    def test_boss_power_cannot_leak_into_a_moved_partner(self):
        s = copy.deepcopy(S.load_content()[115])
        s['finisher']['power'] = 777
        with self.assertRaisesRegex(SystemExit, 'outside mega band'):
            S.validate(s)

    def test_unpaired_finisher_data_cannot_be_silently_ignored(self):
        s = copy.deepcopy(S.load_content()[5])
        s['finisher'] = dict(power=170, mpCost=40, element='fire')
        with self.assertRaisesRegex(SystemExit, 'paired on/off finisher blocks'):
            S.validate(s)

    def test_rookie_off_ordinary_moves_use_measured_peer_limits(self):
        import content
        s = copy.deepcopy(S.load_content()[67])
        rows = content.load_techniques()
        rows[S.id_of('techs', 'Wind Cutter', 'test')]['power'] = 501
        with patch.object(content, 'load_techniques', return_value=rows):
            with self.assertRaisesRegex(SystemExit, 'off.techniques: ordinary move'):
                S.validate(s)

    def test_off_mode_keeps_existing_encounter_attack_slots(self):
        import content
        moved = {s['name']: s for s in S.load_content().values() if 'techniques' in s.get('off', {})}
        checked = 0
        for name, map_data in content.load_maps().items():
            for entry in map_data.get('digimon', []):
                species = moved.get(entry.get('species'))
                if species is None: continue
                on = S.techniques_from_json(species['techniques'], name)
                off = S.techniques_from_json(species['off']['techniques'], name)
                for animation in entry['moves']:
                    if 46 <= animation < 62 and on[animation - 46] != 255:
                        self.assertNotEqual(off[animation - 46], 255,
                                            (name, species['name'], animation))
                        checked += 1
        self.assertGreater(checked, 20)

    def test_production_sector_reader_applies_all_species_in_both_modes(self):
        source = Path(S.ROOT, 'build/decomp-int/src/main/mod_species.c')
        if not source.exists() or not shutil.which('cc'):
            self.skipTest('needs a prepared engine and host C compiler')
        text = source.read_text()
        first = text.index('Move *modSpeciesMove(')
        last = text.index('\nvoid modApplySpeciesLevels', first)
        production = text[first:last]
        sp = S.load_content()
        rows = S.balance_swaps(sp)
        payload = struct.pack('<H', len(rows)) + b''.join(rows)
        move = Path(S.ROOT, 'build/decomp-int/include/dw/move.h').read_text()
        move = move[move.index('typedef struct'):move.index('extern Move')]
        checks = []
        for mode in (0, 1):
            checks.append(f'MOD_OPT_NEW_DIGIMON={mode}; applySpeciesMoveBalance(1);')
            for t, species in sp.items():
                if 'finisher' not in species.get('off', {}): continue
                block = species if mode else species['off']
                moves = S.techniques_from_json(block['techniques'], 'test')
                fin = next(m for m in reversed(moves) if 58 <= m <= 112)
                f = block['finisher']
                checks.extend(f'if(DIGIMON_DATA[{t}].moves[{j}]!={value}) return 1;'
                              for j, value in enumerate(moves))
                for key, value in [('power', f['power']), ('mpCost', f['mpCost']),
                                   ('special', S.ELEMENTS.index(f['element']))]:
                    checks.append(f'if(modSpeciesMove({t},{fin})->{key}!={value}) return 2;')
        with tempfile.TemporaryDirectory() as directory:
            code = Path(directory, 'reader.c')
            code.write_text('#include <stdint.h>\n#include <string.h>\n' + move +
                '#define SPECIES_BALANCE_SWAP_MAX 19\n#define NUM_ORIGINAL_DIGIMON 180\n' +
                'typedef struct {uint16_t type,move,power;uint8_t cost,element;} SpeciesMoveBalance;\n' +
                'static SpeciesMoveBalance SPECIES_MOVE_BALANCE[19];\n' +
                'static int32_t SPECIES_MOVE_BALANCES,MOD_OPT_NEW_DIGIMON;\n' +
                'static Move SPECIES_MOVE_COPY; Move MOVE_DATA[122];\n' +
                'static struct {uint8_t moves[16];} DIGIMON_DATA[180];\n' +
                'static uint32_t SPECIES_SECTOR[512];\n' +
                'static const uint8_t payload[]={' + ','.join(map(str, payload)) + '};\n' +
                'static void readSpeciesSector(int32_t s){memcpy(SPECIES_SECTOR,payload,sizeof(payload));}\n' +
                production + '\nint main(void){' + ''.join(checks) + 'return 0;}\n')
            binary = Path(directory, 'reader')
            subprocess.run(['cc', '-Wall', '-Werror', str(code), '-o', str(binary)], check=True, capture_output=True)
            subprocess.run([str(binary)], check=True)

    def test_production_lookup_does_not_change_another_species_or_shared_table(self):
        source = Path(S.ROOT, 'build/decomp-int/src/main/mod_species.c')
        if not source.exists() or not shutil.which('cc'):
            self.skipTest('needs a prepared engine and host C compiler')
        text = source.read_text()
        start = text.index('Move *modSpeciesMove(')
        end = text.index('\nstatic void applySpeciesMoveBalance', start)
        production = text[start:end]
        move = Path(S.ROOT, 'build/decomp-int/include/dw/move.h').read_text()
        move = move[move.index('typedef struct'):move.index('extern Move')]
        with tempfile.TemporaryDirectory() as directory:
            code = Path(directory, 'check.c')
            code.write_text('#include <stdint.h>\n' + move + '''
Move MOVE_DATA[122];
typedef struct { uint16_t type, move, power; uint8_t cost, element; } SpeciesMoveBalance;
static SpeciesMoveBalance SPECIES_MOVE_BALANCE[19];
static int32_t SPECIES_MOVE_BALANCES;
static Move SPECIES_MOVE_COPY;
''' + production + '''
int main(void) {
 MOVE_DATA[61].power=155; MOVE_DATA[61].mpCost=40; MOVE_DATA[61].special=0;
 SPECIES_MOVE_BALANCE[0]=(SpeciesMoveBalance){69,61,155,40,0};
 SPECIES_MOVE_BALANCE[1]=(SpeciesMoveBalance){113,61,230,40,0}; SPECIES_MOVE_BALANCES=2;
 if(modSpeciesMove(69,61)->power!=155 || modSpeciesMove(113,61)->power!=230) return 1;
 if(modSpeciesMove(8,61)->power!=155 || MOVE_DATA[61].power!=155) return 2;
 SPECIES_MOVE_BALANCE[1].power=90;
 if(modSpeciesMove(113,61)->power!=90 || modSpeciesMove(69,61)->power!=155) return 3;
 return 0;
}
''')
            binary = Path(directory, 'check')
            subprocess.run(['cc', '-Wall', '-Werror', str(code), '-o', str(binary)], check=True, capture_output=True)
            subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    unittest.main()
