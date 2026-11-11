"""Check Woodmon's walk, tired walk and run (species 272) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 272`). Before the change it is
`woodmon.PROFILE['source']`: the generator is run on it and its bytes are checked; afterwards it is the result itself and
the checks that need the old clips are skipped.
"""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from tools.models.field_animations import quadruped, woodmon as gait
from test_tortomon_gait import inside, DIRS

EXPECTED = 'f21deba9b27d56fc417e8d00533e6e75d1dcc915e50a54010e7383319a8e150d'
LEGS = {'RF': (12, 13, 14), 'LF': (15, 16, 17), 'RH': (18, 19, 20), 'LH': (21, 22, 23)}
ARMS = [2, 3, 4, 5]
TRUNK = [1]
ALL_LEGS = [b for leg in LEGS.values() for b in leg]


class WoodmonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        path = Path('build/imported-model-edit/edit/272-Woodmon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 272')
        cls.rig = json.loads(Path('content/species/272-woodmon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[272] = cls.rig
        mmd.exe().bone_count[272] = len(cls.rig)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gait.PROFILE['source']:
            cls.old = mmd.MMD.parse(data, 24)
            cls.old.type = 272
            data, cls.report = gait.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.new = mmd.MMD.parse(data, 24)
        cls.new.type = 272
        import animstudio
        cls.mesh = animstudio.FastMesh(SimpleNamespace(m=cls.new, skel=cls.rig))

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.new, 24, slot)[0]

    def inside_count(self, pose, a_bones, b_bones):
        np, mesh = self.np, self.mesh
        p = copy.deepcopy(pose)
        p[0] = [4096]*3 + [0]*6
        world = mesh.world(mmd.bone_matrices(self.new, p)).astype(float)
        sel = np.isin(mesh.bone, a_bones)
        tri = world[mesh.tri[sel]]
        points = np.vstack([tri.reshape(-1, 3), tri.mean(1)])
        tris = world[mesh.tri[np.isin(mesh.bone, b_bones)]]
        votes = sum(inside(np, points, tris, d).astype(int) for d in DIRS)
        return int((votes >= 3).sum())

    def trunk_motion(self, slot):
        """Range of the trunk bone's lift and sideways shift (units) and of its pitch, yaw and roll (degrees)."""
        fr = self.frames(slot)[:-1]
        d = 4096 / 360
        lift = [f[1][7] for f in fr]
        side = [f[1][6] for f in fr]
        rng = lambda v: max(v) - min(v)
        return rng(lift), rng(side), [rng([f[1][k] for f in fr]) / d for k in (3, 4, 5)]

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_only_the_three_clips_and_the_aliases_change(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        self.assertEqual(self.report['changed_slots'], [0, 2, 3, 4, 33, 35, 36])
        self.assertTrue(self.report['mesh_exact'] and self.report['other_programs_exact'])
        for slot in (1, 5, 34):
            self.assertEqual(self.frames(slot), self.frames(slot, self.old))

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, 24)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_cycle_lengths_clips_differ_and_speed_order(self):
        walk, tired, run = (self.frames(s) for s in (2, 3, 4))
        self.assertEqual((len(walk) - 1, len(tired) - 1, len(run) - 1), (12, 16, 10))
        speed = lambda fr: -(fr[-1][0][8] - fr[0][0][8]) / (len(fr) - 1)
        self.assertLess(speed(tired), speed(walk))
        self.assertLess(speed(walk), speed(run))
        for slot, (low, high) in gait.PROFILE['speed_range'].items():
            self.assertTrue(low <= speed(self.frames(slot)) <= high, slot)
        self.assertNotEqual(walk[1:5], tired[1:5])
        self.assertNotEqual(walk[1:5], run[1:5])
        for fr in (walk, tired, run):
            steps = {fr[i + 1][0][8] - fr[i][0][8] for i in range(len(fr) - 1)}
            self.assertEqual(len(steps), 1)

    def test_loops_are_seamless(self):
        for slot in (2, 3, 4):
            fr = self.frames(slot)
            self.assertEqual(fr[-1][1:], fr[0][1:])

    def test_the_trunk_bobs_sways_and_leans(self):
        # the trunk bone used to stay still in every gait; now it rides the footfalls
        walk, tired, run = (self.trunk_motion(s) for s in (2, 3, 4))
        for (lift, side, (pitch, yaw, roll)) in (walk, tired, run):
            self.assertGreater(lift, 4)
            self.assertLess(lift, 22)
            self.assertGreater(side, 8)
            self.assertLess(side, 30)
            self.assertGreater(roll, 5)
            self.assertLess(roll, 24)
        # the run leans into its travel and the tired walk slouches, the walk stays upright
        mean_pitch = lambda slot: sum(f[1][3] for f in self.frames(slot)[:-1]) / 4096 * 360 / (len(self.frames(slot)) - 1)
        rest = self.frames(0)[0][1][3] / 4096 * 360
        self.assertGreater(abs(mean_pitch(3) - rest), abs(mean_pitch(2) - rest))

    def test_the_idle_is_calm_but_alive(self):
        # the imported idle swung the arms 45-90 degrees and the claws 40-100; now about a fifth of that, slow, and the
        # legs and feet stay put
        d = 4096 / 360
        fr = self.frames(0)
        self.assertEqual(len(fr) - 1, 40)
        self.assertEqual(fr[-1][1:], fr[0][1:])
        self.assertEqual(self.frames(33), fr)
        rng = lambda b: max(max(f[b][k] for f in fr) - min(f[b][k] for f in fr) for k in (3, 4, 5)) / d
        for b in ARMS + [6, 7, 8, 9, 10, 11]:
            self.assertGreater(rng(b), 5, b)
            self.assertLess(rng(b), 24, b)
        for b in range(12, 24):
            self.assertLess(rng(b), 3, b)
        self.assertLess(rng(1), 4)
        steps = [max(abs(fr[i + 1][b][k] - fr[i][b][k]) for b in range(1, 24) for k in (3, 4, 5)) / d for i in range(len(fr) - 1)]
        self.assertLess(max(steps), 2.5 * sorted(steps)[len(steps) // 2] + 0.5)
        self.assertLess(max(steps), 3)
        # the body breathes a little and the feet do not travel
        lift = [f[1][7] for f in fr]
        self.assertGreater(max(lift) - min(lift), 0.5)
        self.assertLess(max(lift) - min(lift), 4)
        np = self.np
        for paw in (14, 17, 20, 23):
            pts = []
            for pose in fr[:-1]:
                p = copy.deepcopy(pose)
                p[0] = [4096]*3 + [0]*6
                pts.append(np.array(mmd.bone_matrices(self.new, p)[paw], float)[:3, 3])
            drift = np.array(pts).max(0) - np.array(pts).min(0)
            self.assertLess(float(drift.max()), 6, paw)

    def test_the_arms_swing_against_each_other(self):
        np = self.np
        for slot in (2, 3, 4):
            fr = self.frames(slot)[:-1]
            r = np.array([f[2][3] for f in fr], float)
            l = np.array([f[4][3] for f in fr], float)
            self.assertLess(float(np.corrcoef(r, l)[0, 1]), -0.5, slot)
            self.assertGreater((r.max() - r.min()) / (4096 / 360), 12, slot)

    def test_the_planted_feet_do_not_slide(self):
        if self.old is None:
            self.skipTest('needs the generator report')
        for check in self.report['checks']:
            self.assertLessEqual(max(check['stance_slip'].values()), gait.PROFILE['stance_slip'], check['slot'])
            self.assertLess(check['unreached'], 1.0, check['slot'])
            self.assertLessEqual(check['lowest_point'], 6)
            self.assertGreaterEqual(check['lowest_point'], -6)
        np = self.np
        sole = np.array([0, 30, -15, 1.0])
        for slot, speed in ((2, 15), (3, 11), (4, 38)):
            frames = self.frames(slot)[:-1]
            n = len(frames)
            rows = {leg: [] for leg in LEGS}
            for pose in frames:
                p = copy.deepcopy(pose)
                p[0] = [4096]*3 + [0, 0, 0, 0, 0, p[0][8]]
                mats = [np.array(m, float) for m in mmd.bone_matrices(self.new, p)]
                for leg, (_, _, paw) in LEGS.items():
                    rows[leg].append(mats[paw] @ sole)
            for leg, r in rows.items():
                best = [i for i in range(n) if quadruped.leg_phase(gait.PROFILE['gaits'][slot], leg, i / n)[0]]
                # the sole's world z changes by less than a quarter of the body's travel from one stance tick to the next
                # (the pair across the loop's end is skipped: the root's travel does not wrap)
                for i in best:
                    if i + 1 in best:
                        self.assertLess(abs(r[i + 1][2] - r[i][2]), 0.25 * speed + 1, (slot, leg, i))

    def test_no_pose_jumps_from_one_tick_to_the_next(self):
        np = self.np
        for slot in (2, 3, 4):
            fr = self.frames(slot)
            steps = []
            for i in range(len(fr) - 1):
                steps.append(max(abs(a - b) for bone in range(1, 24) for a, b in zip(fr[i + 1][bone][3:6], fr[i][bone][3:6])
                                 if abs(a - b) < 2048) / (4096 / 360))
            self.assertLess(max(steps), 2.5 * float(np.median(steps)) + 8, (slot, steps))

    def test_penetration_is_small(self):
        # arm points inside the trunk or legs, leg points inside the trunk (vertices and triangle centres)
        for slot, limit in PENETRATION.items():
            worst = {'arms': 0, 'legs': 0}
            for pose in self.frames(slot)[:-1]:
                worst['arms'] = max(worst['arms'], self.inside_count(pose, ARMS, TRUNK + ALL_LEGS))
                worst['legs'] = max(worst['legs'], self.inside_count(pose, ALL_LEGS, TRUNK))
            self.assertLessEqual(worst['arms'], limit[0], (slot, worst))
            self.assertLessEqual(worst['legs'], limit[1], (slot, worst))


# The meshes of the trunk and limbs overlap already at rest (157 and 173 vertices at the idle's worst tick); the imported
# gaits kept 157 / 173, these 115 / 148, so no clip is worse than before.
PENETRATION = {2: (120, 150), 3: (120, 150), 4: (120, 150)}

if __name__ == '__main__':
    unittest.main()
