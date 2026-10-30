"""Characterize the engine's unpacked boxes, including near-miss keys."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dws import bytecode as bytecode
from dws import backend as B


class TextProfiles(unittest.TestCase):
    def test_key_and_binary_identity_agree(self):
        for script in (0, 102, 168, 209, 213):
            for section in (0, 10, 1237, 1238, 1240):
                for entry in range(18):
                    key = f'm{section}.u{entry}' if section >= 1000 else f's{script}.sec{section}.u{entry}'
                    self.assertEqual(bool(B.packed_key(key)), not bytecode.unpacked_entry(script, section, entry), key)

    def test_legacy_key_matching_is_unchanged(self):
        for key in ('m1237.u40', 'm1238.u150', 'm1240.u01'):
            self.assertTrue(B.packed_key(key), key)
        for key in (None, '', 's102.sec100.u0', 's103.sec10.u0', 'prefixm1237.u4'):
            self.assertTrue(B.packed_key(key), key)

    def test_explicit_fonts_do_not_leak_layout_configuration(self):
        from dws.text import layout
        original = dict(name='original', extra=False)
        pixel = dict(name='b', extra=True)
        row = 'i' * 32
        self.assertFalse(layout.fits(row, original))
        self.assertTrue(layout.fits(row, pixel))
        self.assertFalse(layout.fits(row, original))
        self.assertEqual(original, dict(name='original', extra=False))

    def test_compiler_headroom_differs_from_binary_capacity(self):
        self.assertEqual(B.MAX_UNITS, 31)
        self.assertEqual(bytecode.LINE_UNITS, 32)


if __name__ == '__main__':
    unittest.main()
