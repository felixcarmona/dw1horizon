"""tools/models/clip_repair.py: the repair operations of a rebuilt clip leave what they do not name as it was."""
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path[:0] = [ROOT, os.path.join(ROOT, 'tools')]

from tools.models import clip_repair  # noqa: E402

PARENTS = [-1, 0, 1, 2]


def clip(n=12):
    return [[[4096, 4096, 4096, 0, 0, 0, 0, -t, 0],
             [4096, 4096, 4096, 40 * t, 0, 0, 0, -300, 0],
             [4096, 4096, 4096, 0, 20 * t, -10 * t, 0, -200, 0],
             [4096, 4096, 4096, 100, 0, 30 * t, 50, -100, 0]] for t in range(n)]


class ClipRepairTest(unittest.TestCase):
    def test_no_ops_is_exact(self):
        self.assertEqual(clip_repair.apply_ops(clip(), PARENTS, []), clip())

    def test_turn_changes_only_its_bone(self):
        out = clip_repair.apply_ops(clip(), PARENTS, [{'op': 'turn', 'bone': 2, 'axis': 'x', 'deg': 15}])
        for a, b in zip(out, clip()):
            for bone in (0, 1, 3):
                self.assertEqual(a[bone], b[bone])
            self.assertEqual(a[2][:3] + a[2][6:], b[2][:3] + b[2][6:])
        self.assertNotEqual([p[2] for p in out], [p[2] for p in clip()])

    def test_turn_envelope_outside_is_exact(self):
        ops = [{'op': 'turn', 'bone': 1, 'axis': [0, 0, 1], 'deg': 20, 'ticks': [4, 5, 6, 8]}]
        out = clip_repair.apply_ops(clip(), PARENTS, ops)
        self.assertEqual(out[:4], clip()[:4])
        self.assertEqual(out[9:], clip()[9:])

    def test_damp_keep_one_and_zero(self):
        self.assertEqual(clip_repair.apply_ops(clip(), PARENTS, [{'op': 'damp', 'bone': 1, 'keep': 1.0}]), clip())
        out = clip_repair.apply_ops(clip(), PARENTS, [{'op': 'damp', 'bone': 1, 'keep': 0.0, 'to': 'first'}])
        self.assertTrue(all(p[1][3:6] == [0, 0, 0] for p in out))

    def test_lift_moves_a_body_bone_only(self):
        out = clip_repair.apply_ops(clip(), PARENTS, [{'op': 'lift', 'bone': 1, 'up': 25}])
        self.assertTrue(all(a[1][7] == b[1][7] - 25 and a[0] == b[0] for a, b in zip(out, clip())))
        with self.assertRaises(ValueError):
            clip_repair.apply_ops(clip(), PARENTS, [{'op': 'lift', 'bone': 0, 'up': 5}])


if __name__ == '__main__':
    unittest.main()
