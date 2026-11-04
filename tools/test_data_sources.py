"""Build data must remain authored when input executables or config folders change."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import balance
import content
import tempfile
from pathlib import Path


class NativeDefaults(unittest.TestCase):
    def test_build_never_decodes_executable_numeric_defaults(self):
        exe = SimpleNamespace(compiled=False)
        with patch.object(balance, 'decode', side_effect=AssertionError('executable numeric read')), \
             patch.object(balance, 'c_rows', side_effect=AssertionError('compiled numeric read')):
            result = balance.built_layer(exe)
        self.assertEqual(result['species']['24']['para']['level'], 5)
        self.assertIn('evoReqs', result['species']['62'])

    def test_missing_resident_configuration_fails_closed(self):
        with patch.object(balance, 'native_species_defaults', return_value={}):
            with self.assertRaisesRegex(SystemExit, 'missing resident species'):
                balance.species_rows(SimpleNamespace(compiled=True))


class EmptyDomains(unittest.TestCase):
    def test_empty_directories_remove_all_rows(self):
        with patch.object(content, 'load_techniques', return_value=None), \
             patch.object(content, 'load_items', return_value=None), \
             patch.object(content, 'load_screens', return_value=None):
            doc = content.doc()
        self.assertEqual(len(doc['techniques']), content.NUM_TECHS)
        self.assertEqual(len(doc['items']), content.NUM_ITEMS)
        self.assertEqual(len(doc['screens']), content.NUM_SCREENS)
        self.assertTrue(all(row['power'] == 0 for row in doc['techniques'].values()))
        self.assertTrue(all(row == content.EMPTY_ITEM for row in doc['items'].values()))
        self.assertTrue(all(row['fileBytes'] == [0] * 10 for row in doc['screens'].values()))


class EmptyMaps(unittest.TestCase):
    def test_empty_directory_clears_source_enemies(self):
        # The malformed, never-read map exception remains outside the gameplay parser.
        fake = SimpleNamespace(digimon=[{'type': 24}], digimon_count=1)
        fake.build = lambda: (fake.digimon_count, fake.digimon)
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(content, 'MAPS_DIR', directory), \
             patch('dwmap.MapFile', return_value=fake):
            self.assertEqual(content.load_maps(), {})
            self.assertEqual(content.build_map('FOREST01', b'geometry and enemies'), (0, []))


if __name__ == '__main__':
    unittest.main()
