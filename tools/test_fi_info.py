"""Clock frames must survive localization and reject the former label layout."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import struct
import unittest

from tools.localize.fi_info import CELLS, CLOCK_FRAMES, SHARED_SIZES, check_cells, check_clock


class ClockCells(unittest.TestCase):
    def test_allocated_labels(self):
        check_cells([(u, v, *SHARED_SIZES[e]) for e, (_, u, v) in CELLS.items()])

    def test_former_layout_rejected(self):
        with self.assertRaisesRegex(ValueError, 'clock frame'):
            check_cells([(128, 32, 28, 7)])

    def test_each_animation_frame_protected(self):
        # Minimal indexed TIM without a palette; deterministic synthetic pixels.
        base = struct.pack('<II IHHHH', 16, 0, 12 + 256*64//2, 896, 448, 64, 64)
        base += bytes(i % 256 for i in range(256*64//2))
        check_clock(base, base)
        for u, v, _, _ in CLOCK_FRAMES:
            changed = bytearray(base)
            changed[20 + v*128 + u//2] ^= 1
            with self.subTest(frame=(u, v)), self.assertRaisesRegex(ValueError, 'animation frame'):
                check_clock(base, changed)
        changed = bytearray(base)
        changed[20 + 48*128 + 128//2] ^= 1
        check_clock(base, changed)


if __name__ == '__main__':
    unittest.main()
