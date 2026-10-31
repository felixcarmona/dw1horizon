"""City roster invariants and the compiled-story drift gate."""
import json
from pathlib import Path
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
                          for lv in ('rookie', 'champion', 'ultimate')], [28, 52, 16])
        points = lambda i: 1 if i in (11, 39, 53) else city.LEVELS[species[i]['level']] - 2
        self.assertEqual(sum(points(r['id']) for r in rows), 177)
        original = [r for r in rows if r['id'] < 59]
        self.assertEqual((len(original), sum(points(r['id']) for r in original)), (50, 100))
        self.assertEqual({r['id'] for r in rows if r['hidden']}, {6, 7, 12})

    def test_scan_decodes_instructions(self):
        source = '.section 5 start\nstart:\n SET_TRIGGER 268\n UNSET_TRIGGER 290\n END_SCRIPT\n .byte 0x19\n'
        script = bytecode.assemble_script(source, 'fixture')[0]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'MAPHEAD.SCN'
            path.write_bytes(script)
            self.assertEqual(city.compiled_recruits(path), {68})

    def test_missing_or_new_resident_fails(self):
        ids = {r['id'] for r in city.residents()}
        with patch.object(city, 'compiled_recruits', return_value=ids):
            self.assertEqual(city.verify(['compiled']), 96)
        for bad in (ids - {110}, ids | {59}):
            with patch.object(city, 'compiled_recruits', return_value=bad):
                with self.assertRaisesRegex(ValueError, 'disagrees'):
                    city.verify(['compiled'])

    def test_out_of_range_listed_id_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'roster.json'
            path.write_text('[{"id":112,"hidden":false}]')
            with patch.object(city, 'ROSTER', path):
                with self.assertRaisesRegex(ValueError, 'below 112'):
                    city.residents()

    def test_prosperity_overflow_fails(self):
        raised = {r['id']: {'level': 'mega'} for r in city.residents()}
        with self.assertRaisesRegex(ValueError, 'exceeds'):
            city.residents(raised)


if __name__ == '__main__':
    unittest.main()
