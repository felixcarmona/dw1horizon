"""Mode payload layout and the production shared-id finisher lookup."""
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
