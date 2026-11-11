"""Check Mammothmon's walk, tired walk and run (species 267) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 267`; MAMMOTHMON_MODEL names another
path). Before the change it is `mammothmon_gait.PROFILE['source']`: the generator is run on it and its bytes are checked;
afterwards it is the result itself and the checks that need the old clips are skipped.

Mammothmon faces -z: its head and trunk are at the front (-z), the "hind" legs (bones 7-12) hang from the rear body bone 2
and the "front" legs (21-26) from the body bone 1.
"""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from motiondiscidentity import changed_programs
from tools.models.field_animations import quadruped, mammothmon_gait as gait
from tools.test_tortomon_gait import inside, DIRS

EXPECTED = '37ba809050e70d313850f9e694a19db1c16327a6676c86481bf5b20df142e65b'
BONES = 27
LEGS = {'RF': (24, 25, 26), 'LF': (21, 22, 23), 'RH': (7, 8, 9), 'LH': (10, 11, 12)}
HIND, FRONT = ('RH', 'LH'), ('RF', 'LF')
SOLE = {'F': (0, 75, -15), 'H': (0, 73, -15)}
TICKS = {2: 20, 3: 24, 4: 10}
SPEED = {2: 15, 3: 11, 4: 36}


class MammothmonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        path = Path(os.environ.get('MAMMOTHMON_MODEL', 'build/imported-model-edit/edit/267-Mammothmon.MMD'))
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 267')
        cls.rig = json.loads(Path('content/species/267-mammothmon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[267] = cls.rig
        mmd.exe().bone_count[267] = BONES
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gait.PROFILE['source']:
            cls.old = mmd.MMD.parse(data, BONES)
            cls.old.type = 267
            data, cls.report = gait.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.new = mmd.MMD.parse(data, BONES)
        cls.new.type = 267
        import animstudio
        cls.mesh = animstudio.FastMesh(SimpleNamespace(m=cls.new, skel=cls.rig))
        cls._tracks = {}

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.new, BONES, slot)[0]

    def world(self, pose):
        p = copy.deepcopy(pose)
        p[0] = [4096]*3 + [0]*6
        return [self.np.array(m, float) for m in mmd.bone_matrices(self.new, p)]

    def track(self, slot):
        """Per leg and tick (loop ticks only): hip, knee, ankle, sole pivot (world z with the root's travel) and the height
        of the lowest vertex of the foot bone over the floor."""
        if slot in self._tracks:
            return self._tracks[slot]
        np = self.np
        rows = {leg: [] for leg in LEGS}
        frames = self.frames(slot)
        for pose in frames:       # the loop's closing frame too (the root has travelled the whole cycle)
            W = self.world(pose)
            for leg, (hip, knee, ankle) in LEGS.items():
                sole = np.array(SOLE['F' if leg[1] == 'F' else 'H'] + (1.0,))
                pivot = W[ankle] @ sole
                verts = np.array([v[:3] + (1.0,) for v in self.new.tmd.obj_verts(self.rig[ankle][0])], float)
                low = -float((W[ankle] @ verts.T)[1].max())
                rows[leg].append(dict(hip=W[hip][:3, 3], knee=W[knee][:3, 3], ankle=W[ankle][:3, 3],
                                      pivot=(pivot[0], pivot[1], pivot[2] + pose[0][8]), low=low))
        self._tracks[slot] = rows
        return rows

    def loop(self, slot):
        """The track without the closing frame."""
        return {leg: rows[:-1] for leg, rows in self.track(slot).items()}

    def stance(self, slot, leg):
        rows = self.loop(slot)[leg]
        return [i for i, r in enumerate(rows) if r['low'] < 4.5]

    def inside_count(self, pose, a_bones, b_bones):
        """Vertices and triangle centres of a_bones inside the closed meshes of b_bones (majority of five rays)."""
        np, mesh = self.np, self.mesh
        world = mesh.world(mmd.bone_matrices(self.new, [[4096]*3 + [0]*6] + copy.deepcopy(pose)[1:])).astype(float)
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
        changed = changed_programs(self.old, self.new)
        self.assertEqual(changed, self.report['changed_slots'])
        self.assertNotIn(0, changed)                       # the idle is the source's own
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())

    def test_the_idle_is_unchanged(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        self.assertEqual(self.frames(0), self.frames(0, self.old))
        self.assertEqual(len(self.frames(0)), 48)

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, BONES)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_cycle_lengths_and_speed_order(self):
        fr = {s: self.frames(s) for s in (2, 3, 4)}
        self.assertEqual({s: len(f) - 1 for s, f in fr.items()}, TICKS)
        speed = {s: -(f[-1][0][8] - f[0][0][8]) / (len(f) - 1) for s, f in fr.items()}
        self.assertEqual(speed, SPEED)
        self.assertLess(speed[3], speed[2])
        self.assertLess(speed[2], speed[4])
        for s, (low, high) in quadruped.SPEED_RANGE.items():     # inside the native partners' field speeds
            self.assertTrue(low <= speed[s] <= high, s)
        # the root moves at one constant speed on each tick
        for f in fr.values():
            self.assertEqual(len({f[i + 1][0][8] - f[i][0][8] for i in range(len(f) - 1)}), 1)

    def test_loops_are_seamless(self):
        for slot in (2, 3, 4):
            fr = self.frames(slot)
            self.assertEqual(fr[-1][1:], fr[0][1:])

    def test_the_hind_feet_are_planted_in_stance(self):
        # the sole pivot hardly moves over the ground while the foot is down: slip as a share of the root's speed
        for slot in (2, 3, 4):
            speed = SPEED[slot]
            for leg in LEGS:
                rows = self.track(slot)[leg]          # with the closing frame
                n = len(rows) - 1
                st = set(self.stance(slot, leg))
                slips = [abs(rows[i + 1]['pivot'][2] - rows[i]['pivot'][2]) / speed * 100 for i in st if (i + 1) % n in st]
                self.assertTrue(slips, (slot, leg))
                self.assertLess(sum(slips) / len(slips), 25 if leg in HIND else 25, (slot, leg))
                self.assertLess(max(slips), 45, (slot, leg))

    def test_every_foot_has_a_real_stance_and_a_real_stride(self):
        for slot in (2, 3, 4):
            n = TICKS[slot]
            for leg in LEGS:
                st = self.stance(slot, leg)
                self.assertGreaterEqual(len(st), 0.4 * n, (slot, leg))
                self.assertLessEqual(len(st), 0.6 * n, (slot, leg))
                rows = self.loop(slot)[leg]
                z = [rows[i]['pivot'][2] - self.frames(slot)[i][0][8] for i in st]
                self.assertGreaterEqual(max(z) - min(z), 115, (slot, leg))      # the foot is carried back under the body

    def test_the_hind_feet_lift_in_a_clear_arc(self):
        # clearance of the foot's lowest vertex over the floor in the swing, and the knee and hock fold in the swing
        np = self.np
        for slot in (2, 3, 4):
            for leg in HIND:
                rows = self.loop(slot)[leg]
                lows = [r['low'] for r in rows]
                self.assertGreaterEqual(max(lows), {2: 28, 3: 22, 4: 28}[slot], (slot, leg))
                # a smooth arc: one rise and one fall, the foot rising on more than one tick
                air = [i for i, v in enumerate(lows) if v > 8]
                self.assertGreaterEqual(len(air), 3, (slot, leg))
                dist = [float(np.linalg.norm(r['ankle'] - r['hip'])) for r in rows]
                self.assertGreaterEqual(max(dist) - min(dist), 35, (slot, leg))     # the leg shortens as the hock folds

    def test_the_feet_land_flat(self):
        # in the first half of the stance the sole is level (the heel peels off only at its end)
        np = self.np
        for slot in (2, 3, 4):
            frames = self.frames(slot)[:-1]
            for leg, (_, _, ankle) in LEGS.items():
                st = self.stance(slot, leg)
                run = [i for i in st if (i + 1) % len(frames) in st or (i - 1) % len(frames) in st]
                for i in run[:max(2, len(run) // 2)]:
                    W = self.world(frames[i])
                    pitch = math.degrees(math.asin(max(-1, min(1, W[ankle][1, 2]))))
                    self.assertLessEqual(abs(pitch), 8, (slot, leg, i))

    def test_the_gait_alternates_the_sides_and_the_diagonals(self):
        # the walks touch down in a lateral sequence (hind, then the front foot of that side), the run in diagonal pairs
        for slot in (2, 3):
            n = TICKS[slot]
            down = {leg: min(self.stance(slot, leg), key=lambda i: (i - self.stance(slot, leg)[0]) % n)
                    for leg in LEGS}
            first = {leg: (self.stance(slot, leg)[0] if (self.stance(slot, leg)[0] - 1) % n not in self.stance(slot, leg) else
                           next(i for i in self.stance(slot, leg) if (i - 1) % n not in self.stance(slot, leg))) for leg in LEGS}
            order = sorted(LEGS, key=lambda leg: (first[leg] - first['LH']) % n)
            self.assertEqual(order, ['LH', 'LF', 'RH', 'RF'], (slot, first))
        n = TICKS[4]
        first = {}
        for leg in LEGS:
            st = self.stance(4, leg)
            first[leg] = next(i for i in st if (i - 1) % n not in st)
        self.assertEqual(first['LF'], first['RH'])
        self.assertEqual(first['RF'], first['LH'])
        self.assertNotEqual(first['LF'], first['RF'])

    def test_no_leg_is_ever_stretched_or_folded_to_its_limit(self):
        # a leg whose target is out of reach is capped by the IK at the length of its two bones (less 2) or at their
        # difference (plus 2): the foot then sticks there and pops away. Every tick of every clip stays clear of both
        np = self.np
        norm = np.linalg.norm
        for slot in (2, 3, 4):
            for leg, rows in self.loop(slot).items():
                for tick, r in enumerate(rows):
                    upper, lower, dist = norm(r['knee'] - r['hip']), norm(r['ankle'] - r['knee']), norm(r['ankle'] - r['hip'])
                    self.assertLess(dist, upper + lower - 2 - 15.0, (slot, leg, tick, 'stretched'))
                    self.assertGreater(dist, abs(upper - lower) + 2 + 20.0, (slot, leg, tick, 'folded'))

    def test_no_joint_jumps_from_one_tick_to_the_next(self):
        np = self.np
        angle = lambda a, b: math.degrees(math.acos(max(-1.0, min(1.0, float(a @ b / np.linalg.norm(a) / np.linalg.norm(b))))))
        bounds = {2: (26.0, 28.0, 2.6), 3: (19.0, 21.0, 2.6), 4: (40.0, 40.0, 2.6)}      # ankle and knee units, thigh ratio
        for slot, (ankle_step, knee_step, ratio) in bounds.items():
            for leg, rows in self.loop(slot).items():
                n = len(rows)
                steps = {'ankle': [], 'knee': [], 'thigh': [], 'shin': []}
                for t in range(n):
                    a, b = rows[t], rows[(t + 1) % n]
                    steps['ankle'].append(float(np.linalg.norm(b['ankle'] - a['ankle'])))
                    steps['knee'].append(float(np.linalg.norm(b['knee'] - a['knee'])))
                    steps['thigh'].append(angle(a['knee'] - a['hip'], b['knee'] - b['hip']))
                    steps['shin'].append(angle(a['ankle'] - a['knee'], b['ankle'] - b['knee']))
                self.assertLessEqual(max(steps['ankle']), ankle_step, (slot, leg))
                self.assertLessEqual(max(steps['knee']), knee_step, (slot, leg))
                for k in ('thigh', 'shin'):
                    self.assertLessEqual(max(steps[k]), ratio * float(np.median(steps[k])) + 8, (slot, leg, k))

    def test_the_parts_follow_the_body_and_their_loops_close(self):
        # trunk (15-17), ears (19, 20), jaw (18) and tail (3-6) move in every walk, each one a closed loop
        np = self.np
        for slot in (2, 3, 4):
            fr = np.array(self.frames(slot))
            for b in (3, 4, 5, 6, 15, 16, 17, 18, 19, 20):
                span = fr[:, b, 3:6].max(0) - fr[:, b, 3:6].min(0)
                self.assertGreater(float(span.max()) * 360 / 4096, 2.0, (slot, b))
                self.assertTrue((fr[-1, b] == fr[0, b]).all(), (slot, b))
        # the trunk swings later than the body bob (a delay of at least a tick)
        fr = np.array(self.frames(2))[:-1]
        bob = fr[:, 1, 7] - fr[:, 1, 7].mean()
        trunk = fr[:, 16, 3] - fr[:, 16, 3].mean()
        lags = [float(np.dot(bob, np.roll(trunk, k))) for k in range(len(bob))]
        self.assertNotEqual(int(np.argmax(np.abs(lags))), 0)

    def test_the_feet_stay_above_the_floor(self):
        for slot in (2, 3, 4):
            for leg, rows in self.loop(slot).items():
                self.assertGreaterEqual(min(r['low'] for r in rows), -1.0, (slot, leg))

    def test_the_legs_stay_out_of_the_body(self):
        legs = [b for trio in LEGS.values() for b in trio]
        for slot in (0, 2, 3, 4):
            poses = self.frames(slot)[:-1]
            for tick in range(0, len(poses), 4 if slot == 0 else 1):
                self.assertLessEqual(self.inside_count(poses[tick], legs, [1, 2]), 230, (slot, tick))     # the hips are built inside the body: idle 197

    def test_the_legs_never_go_through_each_other(self):
        right, left = (7, 8, 9, 24, 25, 26), (10, 11, 12, 21, 22, 23)
        hind, front = (7, 8, 9, 10, 11, 12), (21, 22, 23, 24, 25, 26)
        for slot in (2, 3, 4):
            for tick, pose in enumerate(self.frames(slot)[:-1]):
                for a, b in ((left, right), (right, left), (hind, front), (front, hind)):
                    self.assertEqual(self.inside_count(pose, a, b), 0, (slot, tick))

    def test_the_trunk_never_goes_through_a_leg(self):
        legs = [b for trio in LEGS.values() for b in trio]
        for slot in (2, 3, 4):
            for tick, pose in enumerate(self.frames(slot)[:-1]):
                self.assertEqual(self.inside_count(pose, [15, 16, 17], legs), 0, (slot, tick))


if __name__ == '__main__':
    unittest.main()
