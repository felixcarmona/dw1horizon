#!/usr/bin/env python3
"""The rotation helpers of the native battle retarget (tools/models/field_animations/native_battle.py)."""
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]

from tools.models.field_animations import native_battle  # noqa: E402


def _rz(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


class NativeBattle(unittest.TestCase):
    def close(self, a, b, places=6):
        for ra, rb in zip(a, b):
            for x, y in zip(ra, rb):
                self.assertAlmostEqual(x, y, places=places)

    def test_polar_drops_the_stretch(self):
        r = _rz(0.7)
        stretched = [[v * k for v, k in zip(row, (2.0, 0.5, 1.3))] for row in r]
        self.close(native_battle.polar(stretched), r)

    def test_mean_of_one_rotation_is_itself(self):
        r = _rz(1.1)
        self.close(native_battle.mean_rotation([r], [1.0]), r)

    def test_mean_lies_between(self):
        self.close(native_battle.mean_rotation([_rz(0.2), _rz(0.6)], [1.0, 1.0]), _rz(0.4))

    def test_order_puts_parents_first(self):
        skeleton = [(0, -1), (1, 2), (2, 0)]        # bone 1's parent comes after it
        order = native_battle.order(skeleton)
        self.assertLess(order.index(2), order.index(1))


if __name__ == '__main__':
    unittest.main()
