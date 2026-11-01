"""The disc gate rejects missing partner clips, including split cold animations."""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scriptclips


def model(count=45):
    # All slots share a resident clip, as real model tables may do.
    return bytearray(struct.pack('<2I', 0, 8) + struct.pack('<' + 'I' * count, *([count * 4] * count))
                     + struct.pack('<2H', 20, 0))


class ScriptClipsTest(unittest.TestCase):
    def test_empty_run_fails(self):
        data = model()
        self.assertEqual(scriptclips.missing(scriptclips.clips(data)), [])
        struct.pack_into('<I', data, 8 + 4 * 4, 0)
        self.assertEqual(scriptclips.missing(scriptclips.clips(data)), [4])

    def test_tamer_only_slot_is_not_required(self):
        data = model()
        struct.pack_into('<I', data, 8 + 6 * 4, 0)
        self.assertEqual(scriptclips.missing(scriptclips.clips(data)), [])

    def test_table_too_short_fails(self):
        self.assertIn(4, scriptclips.missing(scriptclips.clips(model(3))))

    def test_cold_clip_is_required_too(self):
        data = model()
        struct.pack_into('<I', data, 8 + 8 * 4, 0x80010000)
        self.assertEqual(scriptclips.missing(scriptclips.clips(data, struct.pack('<2H', 15, 0))), [])
        self.assertEqual(scriptclips.missing(scriptclips.clips(data, bytes(4))), [8])
        with self.assertRaisesRegex(ValueError, 'cold clip outside'):
            scriptclips.clips(data)


if __name__ == '__main__':
    unittest.main()
