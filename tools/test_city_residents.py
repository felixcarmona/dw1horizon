"""City roster invariants and the compiled-story drift gate."""
from collections import Counter
import json
from pathlib import Path
import re
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools import city_residents as city
from tools.dws import bytecode


class CityResidents(unittest.TestCase):
    def test_owned_roster(self):
        rows = city.residents()
        species = {s['id']: s for p in (city.ROOT / 'content/species').glob('*.json')
                   for s in [json.loads(p.read_text())]}
        self.assertEqual([sum(species[r['id']]['level'] == lv for r in rows)
                          for lv in ('rookie', 'champion', 'ultimate')], [18, 34, 20])
        points = lambda i: 1 if i in (11, 39, 53) else city.LEVELS[species[i]['level']] - 2
        self.assertEqual(sum(points(r['id']) for r in rows), 143)
        original = [r for r in rows if r['id'] < 59]
        self.assertEqual((len(original), sum(points(r['id']) for r in original)), (50, 100))
        self.assertEqual({r['id'] for r in rows if r['hidden']}, {6, 7, 12})

    def test_only_the_two_kept_high_residents_can_repeat(self):
        species = {s['id']: s for p in (city.ROOT / 'content/species').glob('*.json')
                   for s in [json.loads(p.read_text())]}
        name = lambda i: species[i]['name'].replace('-', '')
        unique = {name(r['id']) for r in city.residents() if r['id'] > 58} - {'Myotismon', 'WaruMonzaemon'}
        mod = city.ROOT / 'story/mods/what-the-island-forgot'
        placed = Counter()
        for path in mod.rglob('*.py'):
            folder = path.relative_to(mod).parts[0]
            if folder not in ('city', 'district', 'maps', 'test'):
                placed.update(re.findall(r'\.npc\(Species\.(\w+)', path.read_text()))
                placed.update(re.findall(r'take_over\(.*species=Species\.(\w+)', path.read_text()))
        for maps in (city.ROOT / 'content/maps').glob('*.json'):
            for row in json.loads(maps.read_text()).get('digimon', ()):
                if row.get('type') in species:
                    placed[name(row['type'])] += 1
        self.assertEqual({n: placed[n] for n in unique if placed[n] != 1}, {})

    def test_scan_decodes_instructions(self):
        source = '.section 5 start\nstart:\n SET_TRIGGER 268\n UNSET_TRIGGER 290\n SET_TRIGGER 33009\n UNSET_TRIGGER 33041\n SET_TRIGGER 312\n SET_TRIGGER 33792\n END_SCRIPT\n .byte 0x19\n'
        script = bytecode.assemble_script(source, 'fixture')[0]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'MAPHEAD.SCN'
            path.write_bytes(script)
            self.assertEqual(city.compiled_recruits(path), {68, 241})

    def test_missing_or_new_resident_fails(self):
        ids = {r['id'] for r in city.residents()}
        with patch.object(city, 'compiled_recruits', return_value=ids):
            self.assertEqual(city.verify(['compiled']), 72)
        for bad in (ids - {66}, ids | {59}):
            with patch.object(city, 'compiled_recruits', return_value=bad):
                with self.assertRaisesRegex(ValueError, 'disagrees'):
                    city.verify(['compiled'])

    def test_otamamon_is_a_story_flag(self):
        ids = {r['id'] for r in city.residents()}
        self.assertNotIn(109, ids)
        self.assertFalse(city.membership_bits()[109 // 8] & (1 << (109 % 8)))
        with patch.object(city, 'compiled_recruits', return_value=ids | {109}):
            self.assertEqual(city.verify(['compiled']), 72)

    def test_original_pass_ignores_legacy_enemy_flags(self):
        ids = {r['id'] for r in city.residents() if r['id'] < 59}
        with patch.object(city, 'compiled_recruits', return_value=ids | {74, 83, 88, 100, 101, 105}):
            self.assertEqual(city.verify(['original'], original=True), 50)
            with self.assertRaisesRegex(ValueError, 'disagrees'):
                city.verify(['original'])
        with patch.object(city, 'compiled_recruits', return_value=ids - {3}):
            with self.assertRaisesRegex(ValueError, 'unreachable'):
                city.verify(['original'], original=True)

    def test_out_of_range_listed_id_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'roster.json'
            path.write_text('[{"id":1024,"hidden":false}]')
            with patch.object(city, 'ROSTER', path):
                with self.assertRaisesRegex(ValueError, 'below 1024'):
                    city.residents()

    def test_sparse_high_roster_header_and_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'roster.json'
            path.write_text(json.dumps([{'id': i, 'hidden': False} for i in (294, 112, 241, 273, 290)]))
            with patch.object(city, 'ROSTER', path):
                self.assertEqual({r['id'] for r in city.residents()}, {112, 241, 273, 290, 294})
                self.assertEqual(city.membership_bits(), bytes(14))
                self.assertIn('EXTRA_COUNT 5', city.extra_header())
                self.assertIn('{112, 241, 273, 290, 294}', city.extra_header())
            for ids in ((241, 241), (-1,), (1023,)):
                path.write_text(json.dumps([{'id': i, 'hidden': False} for i in ids]))
                with patch.object(city, 'ROSTER', path), self.assertRaisesRegex(ValueError, 'unique, defined'):
                    city.residents()

    def test_prosperity_overflow_fails(self):
        raised = {r['id']: {'level': 'mega'} for r in city.residents()}
        with self.assertRaisesRegex(ValueError, 'exceeds'):
            city.residents(raised)


if __name__ == '__main__':
    unittest.main()
