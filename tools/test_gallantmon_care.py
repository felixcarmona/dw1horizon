"""Gallantmon's (318) care clips keep both feet on the ground and its soles turn out the same amount.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 318`; GALLANTMON_MODEL names another
path). Skipped when it is absent.
"""
import math
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet
import footfix
import mmd
import retarget

RIGHT_ANKLE, LEFT_ANKLE, RIGHT_TOE, LEFT_TOE = 22, 26, 23, 27


class GallantmonCare(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(os.environ.get('GALLANTMON_MODEL', 'build/imported-model-edit/edit/318-Gallantmon.MMD'))
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 318')
        cls.m = mmd.MMD.load(str(path), 318)
        cls.nb = mmd.exe().bone_count[318]
        cls.skel = mmd.exe().skeleton[318]

    def test_the_eating_clip_keeps_the_right_foot_down_and_beside_the_body(self):
        frames, _, _ = animsheet.slot_frames(self.m, self.nb, 8)
        for pose in frames:
            pos = retarget.world_pos(self.skel, pose)
            self.assertLess(-pos[RIGHT_ANKLE][1], 200, 'the ankle was lifted to the mouth')
            self.assertGreater(pos[RIGHT_ANKLE][0], 0, 'the foot crossed the middle of the body')

    def test_both_soles_turn_out_equally_in_the_standing_and_walking_clips(self):
        for slot in (0, 2, 4):
            frames, _, _ = animsheet.slot_frames(self.m, self.nb, slot)
            for pose in frames:
                yaw = []
                for toe in (RIGHT_TOE, LEFT_TOE):
                    d = footfix.foot_dirs(self.m, self.nb, self.skel, pose, toe)
                    yaw.append(math.degrees(math.atan2(d[0], -d[2])))
                self.assertAlmostEqual(yaw[0], -yaw[1], delta=3.0)


if __name__ == '__main__':
    unittest.main()
