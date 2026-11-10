"""Apemon (227) field clips: grounded idle, planted diagonal gait, gallop with flight.

The generator reads the model as it was before the gorilla pass (APEMON_BEFORE=PATH to that 227-Apemon.MMD, which
`tools/models/edit.py get 227` wrote at the previous commit); without it the generation tests are skipped.

    APEMON_BEFORE=before.MMD PYTHONPATH=tools:. python3 -m unittest tools.test_apemon_gait
"""
import copy
import glob
import json
import os
import unittest

import numpy as np

import animsheet
import mmd
from tools.models.field_animations import apemon

SK = json.load(open(glob.glob(os.path.join(os.path.dirname(__file__), '..', 'content/species/227-*.json'))[0]))['model']['skeleton']


def clip(model, slot):
    return animsheet.slot_frames(model, 17, slot)[0]


@unittest.skipUnless(os.environ.get('APEMON_BEFORE'), 'needs the pre-pass model')
class Generation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = open(os.environ['APEMON_BEFORE'], 'rb').read()
        cls.result, cls.report = apemon.build(data, SK)
        cls.before = apemon._parse(data, SK)
        cls.after = apemon._parse(cls.result, SK)

    def test_only_four_programs_change(self):
        for slot, (x, y) in enumerate(zip(self.before.anims.table, self.after.anims.table)):
            if x is None or slot in (0, 2, 3, 4):
                continue
            a = mmd.AnimPlayer(self.before.anims.anims[x], 17, slot)
            b = mmd.AnimPlayer(self.after.anims.anims[y], 17, slot)
            for _ in range(120):
                a.tick(), b.tick()
                self.assertEqual((a.pose, a.root), (b.pose, b.root), slot)

    def test_idle_stays_on_the_ground(self):
        hip = [f[9][7] for f in clip(self.after, 0)]
        self.assertLessEqual(max(hip) - min(hip), 2)
        self.assertEqual(clip(self.after, 0)[0][1:], clip(self.after, 0)[-1][1:])

    def test_contacts_and_travel(self):
        for row in self.report['solver']:
            self.assertLess(row['maximum_FK_contact_error'], 0.5)
            self.assertLess(row['maximum_lift_clipped'], 0.5)   # no leg is held back by the reach limit
        self.assertEqual([r['speed'] for r in self.report['solver']], [0, 20, 14, 35])
        self.assertTrue(self.report['storage']['fits'])

    def test_hind_legs_are_not_mirrored(self):
        # each side has its own height, landing point and timing, and the strides inside a loop differ a little
        for slot in (2, 3, 4):
            frames = clip(self.after, slot)[:-1]
            right = np.array([f[11][3:6] for f in frames], float)
            left = np.array([f[14][3:6] for f in frames], float)
            self.assertGreater(np.abs(right).max(), 0)
            for shift in range(len(frames)):
                if np.abs(np.roll(left, shift, axis=0) - right).max() < 4:
                    self.fail((slot, 'left hind knee is the right one shifted'))
        walk = np.array([f[11][3:6] for f in clip(self.after, 2)[:-1]], float)
        stride = len(walk) // 3
        self.assertGreater(np.abs(walk[:stride] - walk[stride:2 * stride]).max(), 2)   # stride 1 is not stride 2

    def test_limbs_alternate_instead_of_pairing(self):
        # foot z against the pelvis, phase of the gait harmonic (fraction of a cycle, right hind = 0): the two sides sit half a
        # cycle apart and front and hind a quarter apart in the walk, the tired shamble and the run (no 2-and-2 unison)
        cycles = {2: 3, 3: 1, 4: 2}
        for slot, c in cycles.items():
            frames = clip(self.after, slot)[:-1]
            T = len(frames)
            z = {}
            for b in (5, 8, 12, 15):
                z[b] = []
                for f in frames:
                    g = copy.deepcopy(f)
                    g[0] = [4096] * 3 + [0] * 6
                    w = np.array(mmd.bone_matrices(self.after, g))
                    z[b].append(w[b, 2, 3] - w[9, 2, 3])
                z[b] = np.array(z[b])
            t = np.arange(T)
            ph = {b: (np.angle(np.sum(z[b] * np.exp(-2j * np.pi * c * t / T))) / (2 * np.pi)) % 1 for b in z}
            rel = {b: (ph[b] - ph[12]) % 1 for b in z}
            self.assertAlmostEqual(rel[15], 0.5, delta=0.06, msg=(slot, 'hind sides'))
            self.assertAlmostEqual((rel[8] - rel[5]) % 1, 0.5, delta=0.06, msg=(slot, 'front sides'))
            for fore in (5, 8):
                for hind in (12, 15):
                    d = abs((rel[fore] - rel[hind] + 0.5) % 1 - 0.5)
                    self.assertGreater(d, 0.15, (slot, fore, hind))
            for a, b in ((5, 8), (12, 15)):
                self.assertLess(np.corrcoef(z[a], z[b])[0, 1], -0.6, (slot, a, b))

    def test_staff_rests_on_the_back(self):
        # the staff keeps its original pose relative to the chest, lowered a fixed 9/22/6 units onto the back (it used to
        # point up through the body, then hovered): no motion of its own in any clip
        stand = animsheet.slot_frames(self.after, 17, 1)[0][0]
        for slot in (0, 2, 3, 4):
            for f in clip(self.after, slot):
                self.assertEqual(f[16][6:9], [stand[16][6] - 6, stand[16][7] + 9, stand[16][8] - 22], slot)
                self.assertLess(np.abs(np.array(mmd.rot_matrix(*f[16][3:6])) - np.array(mmd.rot_matrix(*stand[16][3:6]))).max(), 0.01, slot)


if __name__ == '__main__':
    unittest.main()
