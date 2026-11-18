"""Codec preservation and the direction of the split-budget proof."""
import copy
import itertools
from pathlib import Path
import sys
import unittest

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import animsheet
import mmd
from tools.models.mesh_ge import ease_rotation
from tools.models.mesh_ge_audit import fractional_floor
from tools.test_meshcheck import model, box_object


class EasedClip(unittest.TestCase):
    def test_root_events_loop_endpoints_and_other_channels_survive_codec(self):
        m, bones = model(box_object())
        frames = [[[4096]*3+[0]*6 for _ in bones] for _ in range(17)]
        for tick, pose in enumerate(frames):
            pose[0][6] = tick*13
            pose[1][3:6] = [tick*7, tick*3, -tick*5]
        events = [(5, 'sound', dict(bank=4, note=17))]
        m.anims.anims = [mmd.encode_anim(frames, len(bones), 0, events, tol=0)]
        m.anims.table = [0]
        before, loop, original_events = animsheet.slot_frames(m, len(bones), 0)
        ease_rotation(m, bones, 0, 1, 0, 15)
        after, new_loop, new_events = animsheet.slot_frames(m, len(bones), 0)
        self.assertEqual((loop, original_events), (new_loop, new_events))
        self.assertEqual((before[0], before[-1]), (after[0], after[-1]))
        self.assertGreater(after[8][1][3], before[8][1][3])
        for a, b in zip(before, after):
            self.assertEqual(a[0], b[0])
            self.assertEqual(a[1][:3]+a[1][4:], b[1][:3]+b[1][4:])

    def test_alias_rejected_before_mutating_program(self):
        m, bones = model(box_object())
        frame = [[4096]*3+[0]*6 for _ in bones]
        m.anims.anims = [mmd.encode_anim([frame, frame], len(bones), 0, [], tol=0)]
        m.anims.table = [0, 0]
        original = copy.deepcopy(m.anims.anims[0].build())
        with self.assertRaisesRegex(ValueError, 'independent'):
            ease_rotation(m, bones, 0, 1, 0, 15)
        self.assertEqual(original, m.anims.anims[0].build())


class SplitBound(unittest.TestCase):
    def test_fractional_residual_never_overstates_exact_knapsack_floor(self):
        rows = [dict(cost=c, risk=r) for c, r in [(24, 31.), (28, 35.), (24, 29.), (28, 4.)]]
        for budget in range(110):
            exact = min(sum(r['risk'] for r, use in zip(rows, choice) if not use)
                        for choice in itertools.product((0, 1), repeat=len(rows))
                        if sum(r['cost'] for r, use in zip(rows, choice) if use) <= budget)
            self.assertLessEqual(fractional_floor(rows, budget), exact+1e-10)

    def test_invalid_cost_does_not_become_a_certificate(self):
        with self.assertRaises(ValueError):
            fractional_floor([dict(cost=0, risk=1)], 1024)


if __name__ == '__main__':
    unittest.main()
