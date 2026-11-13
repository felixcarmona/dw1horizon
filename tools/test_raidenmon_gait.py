"""Check Raidenmon's idle floor, walk, tired walk and run (species 336) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 336`; RAIDENMON_MODEL names another
path). Before the change it is `raidenmon_gait.SOURCE`: the generator is run on it and its bytes are checked; afterwards
it is the result itself.

Raidenmon faces -z: body 1, left arm 2-3, tail 4-7, head 8, right arm 10-14, right leg 15-18 (hip, knee, ankle, foot
block), left leg 19-22.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
import motionstorage
from tools.models.field_animations import raidenmon_gait as gait, quadruped

EXPECTED = '00742ad6a09e0b381365d203046aece36b45c8c12c94d90f91a09c76c7ef0c9d'
BONES = 24
TICKS = {2: 24, 3: 30, 4: 14}
SPEED = {2: 17, 3: 11, 4: 40}


class RaidenmonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(os.environ.get('RAIDENMON_MODEL', 'build/imported-model-edit/edit/336-Raidenmon.MMD'))
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 336')
        cls.rig = json.loads(Path('content/species/336-raidenmon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[336] = cls.rig
        mmd.exe().bone_count[336] = BONES
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest == gait.SOURCE:
            data, cls.report = gait.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        else:
            cls.report = None
        cls.data = data
        cls.model = mmd.MMD.parse(data, BONES)
        cls.model.type = 336
        gait.prepare(cls.model, cls.rig)
        cls.profile = dict(gait.PROFILE)
        cls.rigobj = quadruped.Rig(cls.model, cls.rig, cls.profile)

    def frames(self, slot):
        return animsheet.slot_frames(self.model, BONES, slot)[0]

    def test_bytes(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_no_point_under_the_floor(self):
        for slot in (0, 2, 3, 4):
            frames = self.frames(slot)
            worst = max(gait.lowest(self.rigobj, f) for f in frames)
            self.assertLessEqual(worst, 3, (slot, worst))

    def test_speeds_and_loops(self):
        speeds = {}
        for slot, ticks in TICKS.items():
            frames = self.frames(slot)
            self.assertEqual(len(frames) - 1, ticks)
            speeds[slot] = abs(frames[-1][0][8] - frames[0][0][8]) / ticks
            self.assertAlmostEqual(speeds[slot], SPEED[slot], delta=0.5)
            self.assertTrue(all(abs(a - b) <= 2 for x, y in zip(frames[0][1:], frames[-1][1:]) for a, b in zip(x, y)))
        self.assertLess(speeds[3], speeds[2])
        self.assertLess(speeds[2], speeds[4])

    def test_soles_stand_still(self):
        for slot in (2, 3, 4):
            frames = self.frames(slot)
            cfg = gait.PROFILE['gaits'][slot]
            slips = quadruped._stance_slip(self.rigobj, cfg, frames)
            self.assertLessEqual(max(slips.values()), 0.2, (slot, slips))

    def test_calm_trunk(self):
        # the donor's trunk jumped up to 3.8 degrees a tick at the pelvis and 55 degrees at an arm in the run
        for slot in (2, 3, 4):
            frames = self.frames(slot)[:-1]
            n = len(frames)
            for b in range(1, 24):
                if b in (15, 16, 17, 18, 19, 20, 21, 22):
                    continue
                for k in (3, 4, 5):
                    for i in range(n):
                        step = abs((frames[(i + 1) % n][b][k] - frames[i][b][k] + 2048) % 4096 - 2048) / (4096 / 360)
                        self.assertLess(step, 3 if b == 1 else 25, (slot, b, k, i, step))

    def test_storage_and_programs(self):
        self.assertLessEqual(motionstorage.require(self.data, BONES)['resident_bytes'], 100352)


if __name__ == '__main__':
    unittest.main()
