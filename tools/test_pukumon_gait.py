"""Pukumon's idle, walk, tired walk and run (species 401): both arms down, four different seamless clips on the fists.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 401`). Before the change it is
`pukumon_gait.SOURCE`: the generator is run on it and the checks that need the old clips are skipped afterwards."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import animstudio
import mmd
from tools.models.field_animations import pukumon_gait as gait
from tools.models.field_animations.okuwamon_limbs import DIRS, inside

EXPECTED = '6cedc3337a045d7a93e413f89e2de972e953479a504b4b3a2f22951eed3d0b81'
NB = 16
BODY = (1, 2, 14, 15)
GROUPS = {'armL': (7, 8, 9), 'armR': (10, 11, 12)}
SOCKET = 60.0
TICKS = {0: 96, 2: 16, 3: 24, 4: 12}
SPEED = {2: 19, 3: 12, 4: 38}


class PukumonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('build/imported-model-edit/edit/401-Pukumon.MMD')
        if not path.exists() or not Path(mmd.EXTRACTED).exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 401 (needs the player DW1 extraction)')
        cls.rig = json.loads(Path('content/species/401-pukumon.json').read_text())['model']['skeleton']
        mmd.exe().add_type(401, cls.rig)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gait.SOURCE:
            cls.old = mmd.MMD.parse(data, NB)
            cls.old.type = 401
            data, _ = gait.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.new = mmd.MMD.parse(data, NB)
        cls.new.type = 401
        cls.clips = {s: animsheet.slot_frames(cls.new, NB, s) for s in TICKS}
        cls.mesh = animstudio.FastMesh(type('M', (), dict(m=cls.new, skel=cls.rig))())

    def frames(self, slot):
        return self.clips[slot][0]

    def world(self, pose):
        p = copy.deepcopy(pose)
        p[0] = [4096] * 3 + [0] * 6
        mats = mmd.bone_matrices(self.new, p)
        return mats, self.mesh.world(mats).astype(float)

    def test_only_the_four_field_slots_change(self):
        if self.old is not None:
            self.assertEqual(self.old.tmd.build(), self.new.tmd.build())
            self.assertEqual(gait.changed_programs(self.old, self.new), [0, 2, 3, 4])

    def test_ticks_and_speeds_keep_their_order(self):
        for slot, n in TICKS.items():
            self.assertEqual(len(self.frames(slot)) - 1, n, slot)
        for slot, speed in SPEED.items():
            self.assertEqual([-f[0][8] for f in self.frames(slot)], [speed * i for i in range(TICKS[slot] + 1)])
        self.assertTrue(10 <= SPEED[3] < SPEED[2] < SPEED[4] <= 52 and SPEED[2] >= 15 and SPEED[4] >= 35)

    def test_loops_are_seamless(self):
        for slot in TICKS:
            self.assertEqual(self.clips[slot][1], 0)
            frames = self.frames(slot)
            for bone in range(1, NB):
                for channel in range(3, 9):
                    gap = abs(frames[-1][bone][channel] - frames[0][bone][channel])
                    self.assertLessEqual(min(gap % 4096, 4096 - gap % 4096) if channel < 6 else gap, 2, (slot, bone, channel))

    def test_no_arm_is_held_up_and_the_arms_mirror(self):
        for slot in TICKS:
            for pose in self.frames(slot)[:-1]:
                mats, w = self.world(pose)
                for fist in (9, 12):
                    shoulder = mats[7 if fist == 9 else 10]
                    self.assertGreater(mats[fist][1][3], shoulder[1][3] + (20 if slot in (0, 3) else -15), (slot, fist))   # y down: the fist hangs below the shoulder, the swing may reach its height
        for slot in (0, 2, 3, 4):
            lows = [(self.world(f)[0][9][1][3], self.world(f)[0][12][1][3]) for f in self.frames(slot)[:-1]]
            self.assertLess(max(abs(a - b) for a, b in lows), 80, slot)

    def test_the_clips_differ(self):
        key = lambda s: [[tuple(j[3:]) for j in f[1:]] for f in self.frames(s)]
        for a in TICKS:
            for b in TICKS:
                if a < b:
                    n = min(TICKS[a], TICKS[b])
                    self.assertLess(sum(1 for x, y in zip(key(a)[:n], key(b)[:n]) if x == y), n // 4, (a, b))
        tail = lambda s: np.ptp([f[gait.TAIL][4] for f in self.frames(s)[:-1]])
        self.assertLess(tail(0), tail(2))
        self.assertGreater(tail(4), tail(2))

    def test_the_fists_are_planted_and_never_sink(self):
        for slot in TICKS:
            low = [self.world(f)[1][:, 1].max() for f in self.frames(slot)[:-1]]
            self.assertLessEqual(max(low), 1.0, slot)                           # y down: the floor is 0 (a unit of rounding)
        for slot in (2, 3, 4):
            ys = {b: [self.world(f)[0][b][1][3] for f in self.frames(slot)] for b in (9, 12)}
            zs = {b: [self.world(f)[0][b][2][3] + f[0][8] for f in self.frames(slot)] for b in (9, 12)}
            for b in (9, 12):
                lo, hi = max(ys[b]), min(ys[b])
                stance = [t for t in range(len(ys[b]) - 1) if ys[b][t] > lo - 0.25 * (lo - hi)]
                slip = [abs(zs[b][t + 1] - zs[b][t]) / SPEED[slot] for t in stance]
                self.assertLess(sum(slip) / len(slip), 0.25, (slot, b))
                self.assertLess(max(slip), 0.47 if slot != 4 else 0.8, (slot, b))

    def test_nothing_goes_through_the_body_or_the_other_arm(self):
        for slot in TICKS:
            worst = {}
            for pose in self.frames(slot)[:-1]:
                mats, w = self.world(pose)
                for name, group in GROUPS.items():
                    others = BODY + tuple(b for n, g in GROUPS.items() if n != name for b in g)
                    tri = w[self.mesh.tri[np.isin(self.mesh.bone, group)]]
                    points = np.vstack([tri.reshape(-1, 3), tri.mean(1)])
                    root = np.array(mats[group[0]], float)[:3, 3]
                    points = points[np.linalg.norm(points - root, axis=1) > SOCKET]
                    cage = w[self.mesh.tri[np.isin(self.mesh.bone, others)]]
                    votes = sum(inside(points, cage, d).astype(int) for d in DIRS)
                    worst[name] = max(worst.get(name, 0), int((votes >= 3).sum()))
            self.assertEqual({k: v for k, v in worst.items() if v}, {}, slot)


if __name__ == '__main__':
    unittest.main()
