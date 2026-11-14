"""The imports' unique finishers in DIGI.DAT: record bytes 0x1D2..0x1E9, the neutral switch and the name sectors
(docs/mods/unique-finishers.md)."""
import copy
import importlib.util
import json
import os
import struct
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, ROOT)
import species as S  # noqa: E402
from tools.languages import CODES  # noqa: E402

DATA = json.load(open(S.FINISHERS, encoding='utf-8'))


def moves_with(**top):
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(dict(DATA, **top), f)
    try:
        return S.finisher_moves(f.name)
    finally:
        os.unlink(f.name)


def bank_dir(code):
    return os.path.join(ROOT, 'text', 'ours' if code == 'en' else code)


class Record(unittest.TestCase):
    def test_designed_numbers_round_trip(self):
        fins, order = moves_with(neutral=False)
        self.assertEqual(len(order), len(DATA['finishers']))
        for t, f in fins.items():
            f = dict(f, nameStride=3, nameSector=1234, nameOffset=96)
            f.pop('nativeRange')
            b = bytearray(S.RECORD_SIZE)
            S.pack_finisher(b, f)
            self.assertEqual(S.unpack_finisher(b), f)
            self.assertEqual(bytes(b[:0x1D2]), bytes(0x1D2))
            self.assertEqual(bytes(b[0x1EE:]), bytes(S.RECORD_SIZE - 0x1EE))
            self.assertEqual(b[0x1D2], f['tech'])
            self.assertEqual(struct.unpack_from('<ih', b, 0x1D4), (f['distance'], f['power']))   # Move at 0x1D4

    def test_designed_fields(self):
        fins, _ = moves_with(neutral=False)
        for e in DATA['finishers']:
            f, m = fins[e['species']], (e['fallback']['move'] if 'buff' in e else e['move'])
            self.assertEqual(f['tech'], e['replaces']['id'])
            self.assertEqual((f['power'], f['range'], f['distance'], f['accuracy'], f['iframes']),
                             (m['power'], m['range'], m['distance'], m['accuracy'], m['iframes']))
            self.assertEqual((f['status'], f['statusChance']), (m['status'], m['statusChance']))
            self.assertEqual(S.FINISHER_ELEMENTS[f['special']], m['element'])
            self.assertEqual(f['flags'], S.FINISHER_PRESENT)
            self.assertEqual(f['unk3'] & 1, 'T' in m['flags'])
            native = S.native_move(f['tech'])
            self.assertEqual((f['mpCost'], f['unk4'], f['unk5'], f['unk3'] & ~1),
                             (native['mpCost'], native['unk4'], native['unk5'], native['unk3'] & ~1))
        skull = fins[277]
        self.assertEqual((skull['tech'], skull['range']), (63, 3))

    def test_area_finishers_spread_unless_an_own_chunk_plays_them(self):
        fins, _ = moves_with(neutral=False)
        species = S.load_content(None)
        spread = {t for t, f in fins.items() if S.finisher_spreads(f, species[t])}
        self.assertNotIn(277, spread)          # SkullMeramon: chunk 122 is an area chunk itself
        self.assertNotIn(264, spread)          # Raremon: Buffalo Breath hits one fighter
        own = {t: S.id_of('techs', s['own_effect']['technique'], 'species') for t, s in species.items() if s.get('own_effect')}
        expected = {t for t, f in fins.items() if f['range'] == 3 and f['nativeRange'] != 3 and own.get(t) != f['tech']}
        self.assertEqual(spread, expected)
        self.assertTrue(spread)

    def test_support_moves_ship_their_fallback(self):
        fins, _ = moves_with(neutral=False)
        for e in DATA['finishers']:
            if 'buff' in e:
                self.assertEqual(fins[e['species']]['range'], e['fallback']['move']['range'])

    def test_neutral_writes_no_numbers(self):
        self.assertTrue(DATA.get('neutral', True), 'the shipped data keeps the DW1 numbers (docs/mods/unique-finishers.md)')
        fins, _ = moves_with(neutral=True)
        for t, f in fins.items():
            self.assertEqual(set(f), {'tech', 'name'})
            b = bytearray(S.RECORD_SIZE)
            S.pack_finisher(b, dict(f, nameStride=3, nameSector=9, nameOffset=0))
            self.assertEqual(b[0x1D9] & S.FINISHER_PRESENT, 0)
            self.assertEqual(bytes(b[0x1D4:0x1E4]), bytes(16))
            self.assertEqual(S.unpack_finisher(b)['tech'], f['tech'])

    def test_bad_values_stop_the_build(self):
        data = copy.deepcopy(DATA)
        data['finishers'][0]['move']['element'] = 'water'
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
            json.dump(data, f)
        try:
            with self.assertRaises(SystemExit):
                S.finisher_moves(f.name)
        finally:
            os.unlink(f.name)


class AreaChunks(unittest.TestCase):
    def test_area_only_with_the_designed_numbers(self):
        """An own effect chunk picks its own targets: it hits every enemy only when the designed numbers play."""
        from unittest import mock
        from tools.derive.steps import effects
        self.assertEqual(effects.finisher_area_chunks(ROOT), set())
        real = json.load
        with mock.patch('json.load', lambda f, **k: (lambda d: dict(d, neutral=False) if 'finishers' in d else d)(real(f, **k))):
            self.assertIn(122, effects.finisher_area_chunks(ROOT))          # SkullMeramon's Metal Fireball
            self.assertNotIn(123, effects.finisher_area_chunks(ROOT))       # Raremon's Buffalo Breath: one target


class Names(unittest.TestCase):
    def test_every_species_has_a_name_in_every_bank(self):
        english = {e['species']: e['name'] for e in DATA['finishers']}
        for code in CODES:
            bank = json.load(open(os.path.join(bank_dir(code), 'names.json'), encoding='utf-8'))
            for t, name in english.items():
                key = f'species.{t}.finisher'
                self.assertTrue(bank.get(key, '').strip(), f'{code}: {key}')
                if code == 'en':
                    self.assertEqual(bank[key], name, key)

    def test_name_sectors(self):
        _, order = S.finisher_moves()
        names = S.finisher_names(order)
        self.assertEqual(list(names), list(CODES))      # MOD_LANG order: en es pt-br fr de it ja ca zh-hans
        data, stride = S.finisher_name_sectors(names)
        per = S.SECTOR // S.FINISHER_NAME_SLOT
        self.assertEqual(len(data), len(CODES) * stride * S.SECTOR)
        for lang, code in enumerate(CODES):
            for ref, raw in enumerate(names[code], 1):
                self.assertTrue(0 < len(raw) <= S.FINISHER_NAME_MAX)
                o = (lang * stride + (ref - 1) // per) * S.SECTOR + (ref - 1) % per * S.FINISHER_NAME_SLOT
                self.assertEqual(data[o:o + S.FINISHER_NAME_SLOT], raw.ljust(S.FINISHER_NAME_SLOT, b'\0'))

    def test_bytes_match_the_executable_compiler(self):
        """The names are encoded exactly as gen_text encodes MOVE_NAMES in the same language."""
        # the patched tree's compiler (the submodule's own knows no text bank)
        path = next((p for p in (os.path.join(ROOT, 'build', tree, 'tools', 'gen_text.py') for tree in ('decomp-dev', 'decomp-int'))
                     if os.path.exists(p)), None)
        if path is None:
            self.skipTest('no patched decomp tree (tools/mods.sh prepare)')
        if importlib.util.find_spec('yaml') is None:
            self.skipTest('gen_text needs PyYAML, which this interpreter lacks')
        spec = importlib.util.spec_from_file_location('gen_text_for_test', path)
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)
        sys.path.insert(0, ROOT)
        from tools.localize.executable.bank import exe_bank
        for code in CODES:
            bank, _ = exe_bank('ours' if code == 'en' else code)
            gen.__dict__['__BANK'] = bank
            for key in ('main.MOVE_NAMES.63', 'species.277.finisher', 'species.264.finisher'):
                literal = gen.__dict__['__c_string'](bank['text'][key], key)[1:-1]
                compiled = literal.encode('latin1').decode('unicode_escape').encode('latin1')
                self.assertEqual(S.exe_text_bytes(bank['text'][key], bank['font']), compiled, f'{code} {key}')


if __name__ == '__main__':
    unittest.main()
