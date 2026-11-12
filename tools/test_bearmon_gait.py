"""Check Bearmon's idle, walk, tired walk and run (species 353) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 353`; BEARMON_MODEL names another
path). Before the change it is `bearmon_gait.SOURCE`: the generator is run on it and its bytes are checked; afterwards
it is the result itself. """
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
import motionstorage
from tools.models.field_animations import bearmon_gait as gait, quadruped

EXPECTED = '894ee1e1fb8660be3821d858dbc30584edd190ae61ba85e4bb6e8bedc6a2104f'
NB = 18
TICKS = {2: 20, 3: 28, 4: 16}
IDLE = 96
SPEED = {2: 16, 3: 10, 4: 36}
# Triangle-inside counts per clip, the worst tick of each group pair summed over the pairs, on every second tick: the
# imported clips measured 485 / 565 / 481, so the new ones must not interpenetrate more than that.
PENETRATION = {0: 343, 2: 485, 3: 565, 4: 481}
GROUPS = dict(arm_r=[2, 3, 4], arm_l=[5, 6, 7], leg_r=[11, 12, 13], leg_l=[14, 15, 16], hips=[10], torso=[1],
              head=[8, 9], tail=[17])


class BearmonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        path = Path(os.environ.get('BEARMON_MODEL', 'build/imported-model-edit/edit/353-Bearmon.MMD'))
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 353')
        cls.rig = json.loads(Path('content/species/353-bearmon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[353] = cls.rig
        mmd.exe().bone_count[353] = NB
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gait.SOURCE:
            cls.old = mmd.MMD.parse(data, NB)
            cls.old.type = 353
            data, cls.report = gait.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.new = mmd.MMD.parse(data, NB)
        cls.new.type = 353

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.new, NB, slot)[0]

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_cycle_lengths_and_speed_order(self):
        fr = {s: self.frames(s) for s in TICKS}
        self.assertEqual({s: len(f) - 1 for s, f in fr.items()}, TICKS)
        speed = {s: -(fr[s][-1][0][8] - fr[s][0][0][8]) / (len(fr[s]) - 1) for s in SPEED}
        self.assertEqual(speed, SPEED)
        self.assertLess(speed[3], speed[2])
        self.assertLess(speed[2], speed[4])
        for s, (low, high) in quadruped.SPEED_RANGE.items():
            self.assertTrue(low <= speed[s] <= high, s)
        for s in SPEED:       # one constant root speed
            f = fr[s]
            self.assertEqual(len({round(f[i + 1][0][8] - f[i][0][8], 6) for i in range(len(f) - 1)}), 1, s)

    def test_loops_are_seamless(self):
        for s in TICKS:
            f = self.frames(s)
            for a, b in zip(f[0][1:], f[-1][1:]):
                self.assertLess(max(abs(x - y) for x, y in zip(a[:6], b[:6])), 3, s)

    def test_only_the_idle_and_field_gaits_change(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        from motiondiscidentity import changed_programs
        self.assertEqual(changed_programs(self.old, self.new), self.report['changed_slots'])
        self.assertEqual(self.report['changed_slots'], [0, 2, 3, 4, 33])     # 33 is the idle's alias
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())

    def test_storage_fits_the_resident_buffer(self):
        storage = motionstorage.audit(self.data, NB)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_feet_plant_and_the_floor_holds(self):
        for c in self.report['checks'] if self.old is not None else []:
            self.assertLess(max(c['stance_slip'].values()), 0.25, c['slot'])
            self.assertLessEqual(c['lowest_point'], 3, c['slot'])

    def test_arms_and_head_are_alive_and_follow_the_stride(self):
        """The imported gaits froze both arms, the jaw and the tail. Now every one of them moves, and each hand swings
        against the leg on its side (negative correlation of the fore-aft position, left hand with left foot; the run's arms also flail wide)."""
        np = self.np
        for s in TICKS:
            f = self.frames(s)[:-1]
            for bone in (2, 3, 5, 6, 8, 10, 17):
                span = max(max(p[bone][a] for p in f) - min(p[bone][a] for p in f) for a in (3, 4, 5))
                self.assertGreater(span, 14 if bone != 8 else 8, (s, bone))      # 1.2 degrees of 4096 turn or more
            mats = [mmd.bone_matrices(self.new, [[4096] * 3 + [0] * 6] + [list(b) for b in p[1:]]) for p in f]
            z = lambda b: [float(np.asarray(m[b])[2, 3]) for m in mats]
            for hand, foot in ((7, 16), (4, 13)):
                self.assertLess(np.corrcoef(z(hand), z(foot))[0, 1], -0.1, (s, hand))
                self.assertGreater(max(z(hand)) - min(z(hand)), 15, (s, hand))

    def test_the_idle_has_life(self):
        """96 ticks that close: the head looks round and tilts, the right arm lifts in a wave, the tail wags in a burst, the
        body breathes and shifts; the legs stay as the import has them."""
        f = self.frames(0)
        self.assertEqual(len(f) - 1, IDLE)
        f = f[:-1]
        for a, b in zip(self.frames(0)[0][1:], self.frames(0)[-1][1:]):
            self.assertLess(max(abs(x - y) for x, y in zip(a[:6], b[:6])), 3)
        span = lambda bone, axis: max(p[bone][axis] for p in f) - min(p[bone][axis] for p in f)
        self.assertGreater(span(8, 4), 300)        # looks round: about 30 degrees of yaw
        self.assertGreater(span(8, 5), 100)        # tilts its head
        self.assertGreater(span(2, 3), 150)        # the paw gesture
        self.assertGreater(span(17, 4), 200)       # the wag
        self.assertGreaterEqual(span(1, 7), 2)       # breath and the happy dip, in units
        for bone in (11, 12, 13, 14, 15, 16):
            self.assertEqual(span(bone, 3), 0, bone)

    def test_hips_counter_rotate_against_the_chest(self):
        np = self.np
        for s in TICKS:
            f = self.frames(s)[:-1]
            for axis in (4, 5):        # yaw and roll
                body = [p[1][axis] for p in f]
                hips = [p[10][axis] for p in f]
                self.assertLess(np.corrcoef(body, hips)[0, 1], -0.5, (s, axis))

    def test_the_two_cycles_differ(self):
        for s in TICKS:
            f = self.frames(s)[:-1]
            half = len(f) // 2
            gap = max(abs(f[i][b][a] - f[i + half][b][a]) for i in range(half) for b in (2, 5, 11, 14) for a in (3, 4, 5))
            self.assertGreater(gap, 12, s)       # not one cycle copied: about one degree or more

    def test_no_bone_jumps_between_ticks(self):
        for s in TICKS:
            f = self.frames(s)[:-1]
            n = len(f)
            for bone in (1, 2, 3, 8, 9, 10, 17):
                for axis in (3, 4, 5):
                    series = [p[bone][axis] for p in f]
                    step = max(min(abs(series[(i + 1) % n] - series[i]), 4096 - abs(series[(i + 1) % n] - series[i]))
                               for i in range(n))
                    self.assertLess(step, 200, (s, bone, axis, step))            # under 18 degrees a tick

    def test_legs_keep_their_length(self):
        for s in TICKS:
            for p in self.frames(s)[:-1]:
                for b in (12, 13, 15, 16):
                    self.assertEqual(tuple(p[b][6:9]), tuple(self.frames(s)[0][b][6:9]), (s, b))

    def test_no_more_interpenetration_than_the_import(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        from types import SimpleNamespace
        import numpy as np
        import animstudio
        from test_tortomon_gait import inside, DIRS
        mesh = animstudio.FastMesh(SimpleNamespace(m=self.new, skel=self.rig))
        total = {}
        for s in PENETRATION:
            worst = {}
            for pose in self.frames(s)[:-1][::2]:
                p = [list(b) for b in pose]
                p[0] = [4096] * 3 + [0] * 6
                world = mesh.world(mmd.bone_matrices(self.new, p)).astype(float)
                for a, b in itertools.permutations(GROUPS, 2):
                    tri = world[mesh.tri[np.isin(mesh.bone, GROUPS[a])]]
                    pts = np.vstack([tri.reshape(-1, 3), tri.mean(1)])
                    tris = world[mesh.tri[np.isin(mesh.bone, GROUPS[b])]]
                    votes = sum(inside(np, pts, tris, d).astype(int) for d in DIRS)
                    worst[a, b] = max(worst.get((a, b), 0), int((votes >= 3).sum()))
            total[s] = sum(worst.values())
        for s, n in total.items():
            self.assertLessEqual(n, PENETRATION[s], (s, total))


if __name__ == '__main__':
    unittest.main()
