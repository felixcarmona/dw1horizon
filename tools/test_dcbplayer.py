"""Fixed-point Card Battle interpolation, including negative truncation and loops."""
import struct
import unittest
from tools.derive.dcbplayer import play


def animation(keys, loop=-1):
    raw = bytearray(struct.pack('<I', len(keys)))
    for duration, event, rotation, translation in keys:
        channels = [0] * 384
        channels[:12] = [rotation, 0, 0, 0, translation, 0, 0, 0, 4096, 4096, 4096, loop]
        raw.extend(struct.pack('<hh384h', duration, event, *channels))
    return raw


class CardPlayer(unittest.TestCase):
    def test_negative_rotation_truncates_translation_shifts(self):
        raw = animation([(1, 0, 0, 0), (2, 7, -3, -3)])
        frames, events, looped = play(raw, 1)
        self.assertEqual(frames.shape, (7, 1, 9))
        self.assertEqual(frames[:, 0, 0].tolist(), [0, 0, 0, 0, -1, -2, -3])
        self.assertEqual(frames[:, 0, 3].tolist(), [0, 0, 0, -1, -2, -3, -3])
        self.assertEqual(events, [(2,7)])
        self.assertFalse(looped)

    def test_loop_and_empty_record(self):
        frames, events, looped = play(animation([(1, 2, 0, 0)], loop=0), 1)
        self.assertEqual(frames.shape, (5,1,9))
        self.assertEqual(events, [(0,2), (2,2)])
        self.assertTrue(looped)
        frames, events, looped = play(struct.pack('<I',0), 4)
        self.assertEqual(frames.shape, (0,4,9))
        self.assertEqual(events, [])
        self.assertFalse(looped)


if __name__ == '__main__': unittest.main()
