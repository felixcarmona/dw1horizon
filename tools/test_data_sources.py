"""Build data must remain authored when input executables or config folders change."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import balance


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


if __name__ == '__main__':
    unittest.main()
