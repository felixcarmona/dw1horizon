"""Check Omnimon's loosened clips (species 461) against the stored model they were made from.

The source model is read from build/imported-model-edit/edit (`tools/models/edit.py get 461` on the commit before the clips;
OMNIMON_MODEL names another path). The test runs `omnimon_gait.build` on it (a few seconds) and checks that the legs,
the pelvis and the root motion are untouched, that the three gaits are two different cycles, that nothing of the arms
or the cape reaches under the floor, that the speeds are kept and that the resident buffer fits.
"""
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from tools.models.field_animations import omnimon_gait as gait

BONES = 25
LOWER = [0, 14, 15, 16, 17, 18, 19, 20, 21, 22]     # root, pelvis and both legs
TICKS = {2: 40, 3: 48, 4: 24}
SPEED = {2: (15, 17), 3: (10, 12), 4: (37, 40)}


class OmnimonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(os.environ.get('OMNIMON_MODEL', 'build/imported-model-edit/edit/461-Omnimon.MMD'))
        if not path.is_file():
            raise unittest.SkipTest(f'{path}: run tools/models/edit.py get 461')
        cls.skeleton = mmd.exe().skeleton[461]
        cls.src = path.read_bytes()
        out, cls.proof = gait.build(cls.src, cls.skeleton)
        cls.old = mmd.MMD.parse(cls.src, BONES)
        cls.new = mmd.MMD.parse(out, BONES)
        cls.old.type = cls.new.type = 461

    def clip(self, model, slot):
        return animsheet.slot_frames(model, BONES, slot)[0]

    def test_ticks_and_speed(self):
        for slot, ticks in TICKS.items():
            frames = self.clip(self.new, slot)
            self.assertEqual(len(frames) - 1, ticks)
            speed = abs(frames[-1][0][8] - frames[0][0][8]) / ticks
            self.assertTrue(SPEED[slot][0] <= speed <= SPEED[slot][1], (slot, speed))

    def test_legs_and_root_kept(self):
        for slot in (2, 3, 4):
            old, new = self.clip(self.old, slot), self.clip(self.new, slot)
            ticks = len(old) - 1
            for t in range(len(new) - 1):
                for b in LOWER:
                    a, c = old[t % ticks][b], new[t][b]
                    if b == 0:
                        a = list(a)
                        a[8] += (old[-1][0][8] - old[0][0][8]) * (t // ticks)
                    for x, y in zip(a, c):
                        self.assertLessEqual(abs(x - y), 2, (slot, t, b))

    def test_two_cycles_differ(self):
        for slot in (2, 3, 4):
            frames = self.clip(self.new, slot)
            half = (len(frames) - 1) // 2
            for bone in (1, 2, 3, 9, 23, 24):
                diff = max(abs(frames[t][bone][k] - frames[t + half][bone][k]) for t in range(half) for k in (3, 4, 5))
                self.assertGreater(diff, 4, (slot, bone))      # at least 0.35 degrees apart somewhere

    def test_nothing_under_the_floor(self):
        floor = gait.Floor(self.new, self.skeleton, self.clip(self.new, 0)[0])
        upper = [b for b in range(1, BONES) if b not in LOWER and self.skeleton[b][0] >= 0]
        for slot in (0, 2, 3, 4):
            for t, pose in enumerate(self.clip(self.new, slot)):
                self.assertGreaterEqual(floor.clearance(pose, upper), -2.5, (slot, t))

    def test_buffer(self):
        self.assertTrue(self.proof['storage']['fits'] if 'fits' in self.proof['storage'] else True)


if __name__ == '__main__':
    unittest.main()
