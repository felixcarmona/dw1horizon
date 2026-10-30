"""MD3 compatibility and integrity regression tests (no game data)."""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.models import delta as modeldelta


class ModelDeltaTests(unittest.TestCase):
    def test_multiple_sources_and_overlapping_target_copies(self):
        sources = [b'0123456789' * 20, bytes(range(256))]
        target = sources[1][17:100] + b'new-keyframe' * 60 + sources[0][50:180]
        delta = modeldelta.encode(target, sources)
        self.assertEqual(delta[:5], b'MD3\0\0')
        self.assertEqual(modeldelta.decode(delta, sources), target)

    def test_empty_target_and_no_sources(self):
        for target in (b'', b'authored animation' * 20):
            self.assertEqual(modeldelta.decode(modeldelta.encode(target, []), []), target)

    def test_wrong_source_bytes_of_same_size(self):
        source = bytes(range(256)) * 4
        delta = modeldelta.encode(source, [source])
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            modeldelta.decode(delta, [b'x' * len(source)])

    def test_wrong_source_count_or_size(self):
        delta = modeldelta.encode(b'target', [b'source'])
        for sources in ([], [b'wrong length']):
            with self.assertRaises(ValueError):
                modeldelta.decode(delta, sources)

    def test_truncation(self):
        delta = modeldelta.encode(bytes(range(256)), [b'source'])
        for end in range(len(delta)):
            with self.assertRaises(ValueError):
                modeldelta.decode(delta[:end], [b'source'])

    def test_refuse_structured_mode(self):
        delta = bytearray(modeldelta.encode(b'target', []))
        delta[4] = 1
        with self.assertRaisesRegex(ValueError, 'mode 0'):
            modeldelta.decode(delta, [])


if __name__ == '__main__':
    unittest.main()
