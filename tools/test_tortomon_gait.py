"""Check Tortomon's walk, tired walk and run (species 261) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 261`). Before the change it is
`tortomon.PROFILE['source']`: the generator is run on it and its bytes are checked; afterwards it is the result itself and
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
from motiondiscidentity import changed_programs
from tools.models.field_animations import quadruped, tortomon as gait

EXPECTED = '5af45f7442ccd0faf63e9282bd8a54745335f9fe7634bcdacad77b452091d1ab'
LEGS = {'RF': (5, 6, 7), 'LF': (8, 9, 10), 'RH': (11, 12, 13), 'LH': (14, 15, 16)}
DIRS = ([1, .3, .2], [0, 1, .1], [.1, .2, 1], [-.7, .2, .5], [.3, -1, .2])


def inside(np, points, tris, direction):
    """Points inside the closed mesh `tris` (n,3,3) by one ray's parity (Moeller-Trumbore)."""
    a0, a1, a2 = tris[:, 0], tris[:, 1], tris[:, 2]
    e1, e2 = a1 - a0, a2 - a0
    d = np.array(direction, float)
    h = np.cross(d, e2)
    det = (e1*h).sum(1)
    ok = np.abs(det) > 1e-9
    det = np.where(ok, det, 1)
    s = points[:, None, :] - a0[None]
    u = (s*h[None]).sum(2)/det[None]
    q = np.cross(s, e1[None])
    v = (q*d).sum(2)/det[None]
    t = (e2[None]*q).sum(2)/det[None]
    hit = ok[None] & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-6)
    return hit.sum(1) % 2 == 1


class TortomonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        path = Path('build/imported-model-edit/edit/261-Tortomon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 261')
        cls.rig = json.loads(Path('content/species/261-tortomon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[261] = cls.rig
        mmd.exe().bone_count[261] = len(cls.rig)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gait.PROFILE['source']:
            cls.old = mmd.MMD.parse(data, 21)
            cls.old.type = 261
            data, cls.report = gait.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.new = mmd.MMD.parse(data, 21)
        cls.new.type = 261
        import animstudio
        cls.mesh = animstudio.FastMesh(SimpleNamespace(m=cls.new, skel=cls.rig))

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.new, 21, slot)[0]

    def inside_count(self, pose, a_bones, b_bones):
        """Vertices and triangle centres of a_bones inside the closed meshes of b_bones (majority of five rays)."""
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

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_only_the_three_clips_and_the_battle_alias_change(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        self.assertEqual(changed_programs(self.old, self.new), [2, 3, 4, 36])      # 36 plays the run's clip
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, 21)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_cycle_lengths_and_speed_order(self):
        walk, tired, run = (self.frames(s) for s in (2, 3, 4))
        self.assertEqual((len(walk) - 1, len(tired) - 1, len(run) - 1), (16, 22, 10))
        speed = lambda fr: -(fr[-1][0][8] - fr[0][0][8]) / (len(fr) - 1)
        self.assertLess(speed(tired), speed(walk))
        self.assertLess(speed(walk), speed(run))
        self.assertGreater(len(tired), len(walk))          # tired cycle is the slowest
        # the root moves at one constant speed on each tick
        for fr in (walk, tired, run):
            steps = {fr[i + 1][0][8] - fr[i][0][8] for i in range(len(fr) - 1)}
            self.assertEqual(len(steps), 1)

    def test_loops_are_seamless(self):
        for slot in (2, 3, 4):
            fr = self.frames(slot)
            self.assertEqual(fr[-1][1:], fr[0][1:])

    def test_the_planted_feet_hardly_slide_and_the_walk_lifts_the_legs(self):
        if self.old is None:
            self.skipTest('needs the generator report')
        for check in self.report['checks']:
            self.assertLessEqual(max(check['stance_slip'].values()), gait.PROFILE['stance_slip'], check['slot'])
            self.assertLess(check['unreached'], 1.0, check['slot'])
        walk = self.report['checks'][0]
        self.assertEqual(walk['slot'], 2)
        self.assertGreaterEqual(gait.PROFILE['gaits'][2]['lift']['front'], 26)      # thigh and knee, not only the shin
        # the paw rises off the floor: at some tick of the walk the paw bone is clearly higher than when planted
        np = self.np
        for leg, (_, _, paw) in LEGS.items():
            heights = []
            for pose in self.frames(2)[:-1]:
                p = copy.deepcopy(pose)
                p[0] = [4096]*3 + [0]*6
                heights.append(-float(np.array(mmd.bone_matrices(self.new, p)[paw], float)[1, 3]))
            self.assertGreater(max(heights) - min(heights), 20, leg)

    def test_the_planted_foot_is_flat_and_still_and_the_shin_turns_over_the_ankle(self):
        # world positions (the root keeps its travel): per leg, the longest run of ticks with the sole on the ground
        import math
        np = self.np
        sole = np.array([0, 30, -55, 1.0])
        bounds = {2: (6, 8), 3: (8, 8), 4: (12, 14)}       # sole slide, ankle slide (units) in stance; measured 0-2, 0-5 and 4-8, 4-12 for the run
        for slot, (slide, ankle_slide) in bounds.items():
            frames = self.frames(slot)[:-1]
            n, speed = len(frames), 12 if slot == 2 else 9 if slot == 3 else 36
            rows = {leg: [] for leg in LEGS}
            for pose in frames:
                p = copy.deepcopy(pose)
                p[0] = [4096]*3 + [0, 0, 0, 0, 0, p[0][8]]
                mats = [np.array(m, float) for m in mmd.bone_matrices(self.new, p)]
                for leg, (_, knee, paw) in LEGS.items():
                    pm = mats[paw]
                    rows[leg].append((pm @ sole, mats[knee][:3, 3], mats[paw][:3, 3], math.degrees(math.asin(max(-1, min(1, pm[1, 2]))))))
            for leg, r in rows.items():
                best = [i for i in range(n) if quadruped.leg_phase(gait.PROFILE['gaits'][slot], leg, i / n)[0]]
                zs = [r[i][0][2] for i in best]
                az = [r[i][2][2] for i in best]
                self.assertLessEqual(max(zs) - min(zs), slide, (slot, leg))
                self.assertLessEqual(max(az) - min(az), ankle_slide, (slot, leg))
                # the sole stays level for the first half of the stance; the heel peels off only at its end
                for i in best[:max(2, len(best) // 2)]:
                    self.assertLessEqual(abs(r[i][3]), 6, (slot, leg))
                # the foot travels much less than the body does, while the knee swings over the ankle
                self.assertLess(max(az) - min(az), 0.3 * speed * len(best) + 1, (slot, leg))

    def _world_legs(self, slot, keep_root=False):
        """Per tick, per leg: hip, knee and ankle positions (the body frame unless keep_root) and the two bone lengths."""
        np = self.np
        rows = []
        for pose in self.frames(slot)[:-1]:
            p = copy.deepcopy(pose)
            p[0] = [4096]*3 + [0]*6
            pts = [np.array(m, float)[:3, 3] for m in mmd.bone_matrices(self.new, p)]
            rows.append({leg: (pts[hip], pts[knee], pts[ankle]) for leg, (hip, knee, ankle) in LEGS.items()})
        return rows

    def test_no_leg_is_ever_stretched_or_folded_to_its_limit(self):
        # a leg whose target is out of reach is capped by the IK at the length of its two bones (less 2) or at their
        # difference (plus 2): the foot then sticks there and pops away. Every tick of every clip stays clear of both,
        # and of the swing paw's minimum distance from the hip (`fold`, where the wrist would be pushed out of the hip)
        np = self.np
        norm = np.linalg.norm
        for slot in (2, 3, 4):
            for tick, row in enumerate(self._world_legs(slot)):
                for leg, (hip, knee, ankle) in row.items():
                    upper, lower, dist = norm(knee - hip), norm(ankle - knee), norm(ankle - hip)
                    self.assertLess(dist, upper + lower - 2 - 1.0, (slot, leg, tick, 'stretched'))
                    self.assertGreater(dist, abs(upper - lower) + 2 + 3.0, (slot, leg, tick, 'folded'))

    def test_no_joint_jumps_from_one_tick_to_the_next(self):
        import math
        np = self.np
        # largest step per tick of a leg's joint in the body frame: units for the knee and ankle, degrees for the thigh
        # and shin directions. Measured on the reviewed clips; a planted foot moves with the body (12, 9, 36 a tick), so
        # the trot's bounds are the widest.
        bounds = {2: (14.0, 14.0, 18.0, 28.0), 3: (11.0, 11.0, 12.0, 30.0), 4: (36.0, 28.0, 33.0, 65.0)}
        angle = lambda a, b: math.degrees(math.acos(max(-1.0, min(1.0, float(a @ b / np.linalg.norm(a) / np.linalg.norm(b))))))
        for slot, (ankle_step, knee_step, thigh_step, shin_step) in bounds.items():
            rows = self._world_legs(slot)
            n = len(rows)
            for leg in LEGS:
                steps = {'ankle': [], 'knee': [], 'thigh': [], 'shin': []}
                for t in range(n):
                    (h0, k0, a0), (h1, k1, a1) = rows[t][leg], rows[(t + 1) % n][leg]
                    steps['ankle'].append(float(np.linalg.norm(a1 - a0)))
                    steps['knee'].append(float(np.linalg.norm(k1 - k0)))
                    steps['thigh'].append(angle(k0 - h0, k1 - h1))
                    steps['shin'].append(angle(a0 - k0, a1 - k1))
                self.assertLessEqual(max(steps['ankle']), ankle_step, (slot, leg))
                self.assertLessEqual(max(steps['knee']), knee_step, (slot, leg))
                self.assertLessEqual(max(steps['thigh']), thigh_step, (slot, leg))
                self.assertLessEqual(max(steps['shin']), shin_step, (slot, leg))
                if slot != 4:        # the walks: no step beyond about 2.6 times the leg's usual thigh step
                    self.assertLessEqual(max(steps['thigh']), 2.6 * float(np.median(steps['thigh'])), (slot, leg))

    def test_every_leg_uses_a_long_stroke(self):
        # thigh swing (degrees of the hip-knee line from the vertical), knee bend and the ankle's fore-aft travel
        # and rise relative to the body, per clip: lower bounds, measured 2026-11 on the reviewed clips
        import math
        np = self.np
        floors = {2: (45, 55, 40, 28), 3: (40, 55, 35, 22), 4: (50, 65, 40, 25)}
        for slot, (swing, bend, travel, rise) in floors.items():
            for leg, (hip, knee, ankle) in LEGS.items():
                rows = []
                for pose in self.frames(slot)[:-1]:
                    p = copy.deepcopy(pose)
                    p[0] = [4096]*3 + [0]*6
                    pts = [np.array(m, float)[:3, 3] for m in mmd.bone_matrices(self.new, p)]
                    v1, v2 = pts[knee] - pts[hip], pts[ankle] - pts[knee]
                    cos = float(v1 @ v2 / np.linalg.norm(v1) / np.linalg.norm(v2))
                    rows.append((math.degrees(math.atan2(v1[2], -v1[1])), math.degrees(math.acos(max(-1, min(1, cos)))),
                                 float((pts[ankle] - pts[hip])[2]), -float(pts[ankle][1])))
                spans = [max(r[k] for r in rows) - min(r[k] for r in rows) for k in range(4)]
                self.assertGreaterEqual(spans[0], swing, (slot, leg))
                self.assertGreaterEqual(spans[1], bend, (slot, leg))
                self.assertGreaterEqual(spans[2], travel, (slot, leg))
                self.assertGreaterEqual(spans[3], rise, (slot, leg))

    def test_the_legs_stay_out_of_the_shell(self):
        legs = [b for trio in LEGS.values() for b in trio]
        for slot in (0, 2, 3, 4):
            poses = self.frames(slot)[:-1]
            for tick in range(0, len(poses), 4 if slot == 0 else 1):
                self.assertLessEqual(self.inside_count(poses[tick], legs, [1]), 240, (slot, tick))     # the hips are built inside the shell: idle 69, the old walk about 90

    def test_the_legs_never_go_through_each_other(self):
        left, right = (8, 9, 10, 14, 15, 16), (5, 6, 7, 11, 12, 13)
        for slot in (2, 3, 4):
            for tick, pose in enumerate(self.frames(slot)[:-1]):
                self.assertLessEqual(self.inside_count(pose, left, right), 6, (slot, tick))
                self.assertLessEqual(self.inside_count(pose, right, left), 6, (slot, tick))


if __name__ == '__main__':
    unittest.main()
