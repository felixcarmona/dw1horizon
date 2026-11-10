"""Baronmon's idle, walk, condition walk and run stand on the floor, keep the field speeds and loop seamlessly.

Needs the reviewed imported model (tools/models/edit.py get 228 writes it to build/imported-model-edit/edit)."""
import copy
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
from tools.models.field_animations import baronmon, upright_gait

SOURCE = Path(os.environ.get('BARONMON_MODEL', 'build/imported-model-edit/edit/228-Baronmon.MMD'))
SPEED = {2: 20., 3: 13.3, 4: 38.}


class BaronmonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.exists() or not Path(mmd.EXTRACTED).exists():
            raise unittest.SkipTest('needs the imported Baronmon model and the player DW1 extraction')
        data = SOURCE.read_bytes()
        if hashlib.sha256(data).hexdigest() != baronmon.SOURCE:
            raise unittest.SkipTest('needs the reviewed Baronmon field model')
        cls.skeleton = json.loads(Path('content/species/228-baronmon.json').read_text())['model']['skeleton']
        cls.before = data
        cls.after, cls.proof = baronmon.build(data, cls.skeleton)

    def model(self, data):
        mmd.exe().add_type(228, self.skeleton)
        model = mmd.MMD.parse(data, baronmon.NB)
        model.type = 228
        return model

    def test_only_the_four_field_slots_change(self):
        self.assertEqual(self.proof['changed_slots'], [0, 2, 3, 4])
        old, new = self.model(self.before), self.model(self.after)
        self.assertEqual(new.tmd.build(), old.tmd.build())
        for slot, index in enumerate(old.anims.table):
            if slot in baronmon.SLOTS or index is None:
                continue
            self.assertEqual(new.anims.anims[new.anims.table[slot]].__dict__, old.anims.anims[index].__dict__, slot)

    def test_storage_fits(self):
        self.assertTrue(motionstorage.audit(self.after, baronmon.NB)['fits'])

    def test_speeds_loops_and_floor(self):
        model = self.model(self.after)
        for slot in baronmon.SLOTS:
            frames = animsheet.slot_frames(model, baronmon.NB, slot)[0]
            n = len(frames) - 1
            for b in range(1, baronmon.NB):
                self.assertEqual(frames[0][b][3:9], frames[n][b][3:9], (slot, b))
            if slot in SPEED:
                self.assertAlmostEqual(-frames[n][0][8] / n, SPEED[slot], delta=0.1)
            low = upright_gait.ticks_floor(model, self.skeleton, frames, tuple(range(1, baronmon.NB)))
            self.assertLessEqual(max(low), 3.0, slot)
            feet = [max(upright_gait.lowest(model, self.skeleton, f, (b,)) for f in frames[:n]) for b in (18, 21)]
            self.assertGreater(min(feet), -2.0, slot)     # each foot comes down to the floor (y is down)

    def test_planted_soles_do_not_slide(self):
        import numpy as np
        model = self.model(self.after)
        heel, toe = np.array([0, 23, 32, 1.]), np.array([0, 23, -63, 1.])
        for slot in (2, 3, 4):
            frames = animsheet.slot_frames(model, baronmon.NB, slot)[0]
            n = len(frames) - 1
            for bone in (18, 21):
                for point in (heel, toe):
                    runs, current = [], []
                    for t in range(n + 1):
                        pose = copy.deepcopy(frames[t])
                        pose[0] = [4096] * 3 + [0] * 6
                        w = np.array(mmd.bone_matrices(model, pose)[bone])[:3] @ point
                        if w[1] > -1.5:
                            current.append(w[2] + frames[t][0][8])
                        elif current:
                            runs.append(current)
                            current = []
                    runs.append(current)
                    # a point on the floor stays where it touched down (a unit or two of rounding)
                    for run in runs:
                        if run:
                            self.assertLess(max(run) - min(run), 4, (slot, bone))

    def test_feet_stay_clear_of_the_skirt(self):
        """Shoe vertices at the skirt's height inside its flared solid (waist, middle and hem rings): none in the idle,
        walk and condition walk, a handful in the run (it was 986, 151, 246 and 195 over a loop before)."""
        import numpy as np
        model = self.model(self.after)
        verts = {b: np.array(model.tmd.obj_verts(self.skeleton[b][0]))[:, :3] for b in (18, 21)}
        heights, rx, rz = [0, 63, 98], [40, 65, 73], [33, 50, 58]
        for slot, bound in ((0, 0), (2, 0), (3, 0), (4, 8)):
            frames = animsheet.slot_frames(model, baronmon.NB, slot)[0]
            inside = 0
            for pose in frames[:-1]:
                pose = copy.deepcopy(pose)
                pose[0] = [4096] * 3 + [0] * 6
                mats = [np.vstack([np.array(m)[:3], [0, 0, 0, 1]]) for m in mmd.bone_matrices(model, pose)]
                inv = np.linalg.inv(mats[baronmon.SKIRT])
                for b in (18, 21):
                    world = verts[b] @ mats[b][:3, :3].T + mats[b][:3, 3]
                    for x, y, z in world @ inv[:3, :3].T + inv[:3, 3]:
                        if 0 <= y <= 98:
                            inside += (x / np.interp(y, heights, rx)) ** 2 + (z / np.interp(y, heights, rz)) ** 2 < 1
            self.assertLessEqual(inside, bound, slot)

    def test_run_arms_hang_beside_the_body(self):
        """The run's upper arms hang about vertical on average (not held forward) and the hands never get far ahead of
        the shoulders (the arms were 12 degrees forward on average, the hands 52 units ahead, before)."""
        import math
        import numpy as np
        model = self.model(self.after)
        angles, ahead = [], []
        for pose in animsheet.slot_frames(model, baronmon.NB, 4)[0][:-1]:
            pose = copy.deepcopy(pose)
            pose[0] = [4096] * 3 + [0] * 6
            mats = [np.array(m)[:3] for m in mmd.bone_matrices(model, pose)]
            for arm, fore, hand in ((8, 9, 10), (12, 13, 14)):
                upper = mats[fore][:, 3] - mats[arm][:, 3]
                angles.append(math.degrees(math.atan2(-upper[2], upper[1])))
                ahead.append(-(mats[hand][2, 3] - mats[arm][2, 3]))
        self.assertLessEqual(abs(sum(angles) / len(angles)), 3.)
        self.assertLessEqual(max(angles), 20.)
        self.assertGreaterEqual(min(angles), -25.)
        self.assertLessEqual(max(ahead), 70.)
        self.assertLessEqual(sum(ahead) / len(ahead), 40.)


if __name__ == '__main__':
    unittest.main()
