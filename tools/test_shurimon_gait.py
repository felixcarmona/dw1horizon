"""Shurimon's idle, walk, condition walk and run: seamless, different from each other, feet planted, arms in the direction
of travel. Needs the field model the clips were authored from (see field_animations/shurimon_gait.py) and the DW1 extraction.

    python3 tools/models/edit.py get 225 DIR     (at the commit before the clips) and SHURIMON_MODEL=DIR/225-Shurimon.MMD"""
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import animsheet
import mmd
import motionstorage
from tools.models.field_animations import shurimon_gait as gait

SOURCE = Path(os.environ.get('SHURIMON_MODEL', 'build/imported-model-edit/edit/225-Shurimon.MMD'))
NB = 23


class ShurimonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.exists() or not Path(mmd.EXTRACTED).exists():
            raise unittest.SkipTest('needs the previous Shurimon field model and the player DW1 extraction')
        data = SOURCE.read_bytes()
        if __import__('hashlib').sha256(data).hexdigest() != gait.SOURCE_SHA256:
            raise unittest.SkipTest('the model is not the one the clips were authored from')
        cls.skeleton = [tuple(b) for b in json.loads(next(Path('content/species').glob('225-*.json')).read_text())['model']['skeleton']]
        cls.out, cls.proof = gait.build(data, cls.skeleton)
        mmd.exe().add_type(225, cls.skeleton)
        cls.model = mmd.MMD.parse(cls.out, NB)
        cls.model.type = 225
        cls.clips = {s: animsheet.slot_frames(cls.model, NB, s)[0] for s in gait.SLOTS}

    def worlds(self, slot, bone):
        out = []
        for f in self.clips[slot]:
            g = [list(b) for b in f]
            m = mmd.bone_matrices(self.model, [[4096] * 3 + [0] * 6] + g[1:])
            out.append(np.array([m[bone][0][3], m[bone][1][3], m[bone][2][3] + f[0][8]]))
        return np.array(out)

    def test_clips_loop_and_keep_their_length_and_speed(self):
        for slot, (ticks, speed) in {2: (40, 12), 3: (72, 8), 4: (80, 28)}.items():
            f = self.clips[slot]
            self.assertEqual(len(f) - 1, ticks)
            self.assertEqual(f[1][0][8] - f[0][0][8], -speed)
        for slot in gait.SLOTS:
            f = self.clips[slot]
            self.assertEqual(f[0][1:], f[-1][1:], slot)

    def test_only_the_field_slots_change(self):
        self.assertEqual(sorted(self.proof['changed_slots']), [0, 2, 3, 4])
        self.assertTrue(self.proof['storage']['fits'])
        self.assertLessEqual(self.proof['storage']['resident_bytes'], 100352)

    def test_feet_are_planted_and_clear_of_the_floor(self):
        for slot, limit in {0: 1, 2: 12, 3: 12, 4: 18}.items():
            speed = abs(self.clips[slot][1][0][8] - self.clips[slot][0][0][8])
            for foot in (19, 22):
                w = self.worlds(slot, foot)
                lo, hi = w[:, 1].max(), w[:, 1].min()
                stance = [t for t in range(len(w) - 1) if w[t, 1] > lo - .25 * (lo - hi)]
                if speed:
                    slip = np.mean([abs(w[t + 1, 2] - w[t, 2]) for t in stance]) / speed * 100
                else:
                    slip = np.max(np.abs(np.diff(w[:, 2])))
                self.assertLess(slip, limit, (slot, foot, slip))
            for check in self.proof['checks']:
                self.assertLessEqual(check['lowest_leg'][1], 1)

    def test_arms_swing_forward_and_back_and_the_clips_differ(self):
        for slot in (2, 3, 4):
            for hand in (10, 15):
                z = self.worlds(slot, hand)[:, 2] - self.clips[slot][0][0][8] * 0
                z = z - np.array([f[0][8] for f in self.clips[slot]])
                self.assertGreater(z.max() - z.min(), 20, (slot, hand))
        mean = [np.mean([f[1][3:6] for f in self.clips[s]], axis=0) for s in (2, 3, 4)]
        self.assertGreater(float(np.abs(mean[0] - mean[2]).max()), 30)    # the run leans further than the walk
        self.assertGreater(float(np.abs(mean[0] - mean[1]).max()), 30)    # and the tired walk differs too


if __name__ == '__main__':
    unittest.main()
