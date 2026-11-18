"""MetalTyrannomon's authored final-rig faint and recovery regressions."""
import unittest

from tools.battle_finish_testcase import FinishCase


class MetalTyrannomonFinishes(FinishCase):
    sid = 260


class Grounding(unittest.TestCase):
    def test_a_rig_whose_blend_needs_more_clearance_than_its_keys(self):
        import math
        from tools.models.battle_finishes import _ground_frames
        from motiontailspace import interpolate_pose

        # A rotating point has y=0 at either key and reaches down 20 units
        # between them. No carrier line can stay within six units throughout.
        def floor(pose):
            return 20 * math.cos(pose[2][3] * math.tau / 4096) + pose[1][7]

        frames = [[[4096] * 3 + [0] * 6 for _ in range(3)] for _ in range(2)]
        frames[0][2][3], frames[1][2][3] = -1024, 1024
        for pose in frames:
            pose[1][7] = -2
        _ground_frames(frames, floor)
        levels = [floor(interpolate_pose(*frames, alpha)) for alpha in (0, 1365, 2730, 4096)]
        self.assertLessEqual(max(levels), 0.5)  # integer carrier rounding
        self.assertGreaterEqual(min(levels), -21)  # lift follows the 20-unit rig
        self.assertEqual([pose[2][3] for pose in frames], [-1024, 1024])

    def test_a_planted_rig_keeps_its_reviewed_keys(self):
        from tools.models.battle_finishes import _ground_frames
        frames = [[[4096] * 3 + [0] * 6 for _ in range(2)] for _ in range(2)]
        for pose in frames:
            pose[1][7] = -2
        _ground_frames(frames, lambda pose: pose[1][7])
        self.assertEqual([pose[1][7] for pose in frames], [-2, -2])
