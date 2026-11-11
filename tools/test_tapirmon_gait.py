"""Check Tapirmon's idle, walk, tired walk and run (species 287) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 287`). Before the change it is
`tapirmon.SOURCE`: the generator is run on it and its bytes are checked; afterwards it is the result itself and the checks
that need the old clips are skipped (the old model's penetration counts are kept below as numbers).
"""
import copy
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from tools.models.field_animations import tapirmon as gait
from test_tortomon_gait import inside, DIRS

EXPECTED = '02dcb5e36e9d1c3a2897f3e72f693d867b016f08b7f56294719b996cd6564181'
LEGS = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 17, 18, 19, 20]
BODY = [1, 2]
HEAD = [13, 14]
# the imported clips' worst vertex counts inside the body (legs, head), per slot: idle, walk, tired, run
OLD_INSIDE = {0: (236, 32), 2: (606, 34), 3: (563, 39), 4: (464, 33)}
D = 4096 / 360


class TapirmonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        path = Path('build/imported-model-edit/edit/287-Tapirmon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 287')
        cls.rig = json.loads(Path('content/species/287-tapirmon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[287] = cls.rig
        mmd.exe().bone_count[287] = len(cls.rig)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gait.SOURCE:
            cls.old = mmd.MMD.parse(data, 21)
            cls.old.type = 287
            data, cls.report = gait.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.new = mmd.MMD.parse(data, 21)
        cls.new.type = 287
        import animstudio
        cls.mesh = animstudio.FastMesh(SimpleNamespace(m=cls.new, skel=cls.rig))

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.new, 21, slot)[0]

    def world(self, pose):
        p = copy.deepcopy(pose)
        p[0] = [4096] * 3 + [0, 0, 0, 0, 0, p[0][8]]
        return [self.np.array(m, float) for m in mmd.bone_matrices(self.new, p)]

    def new_world(self, pose):
        return self.mesh.world(mmd.bone_matrices(self.new, pose)).astype(float)

    def inside_count(self, pose, a_bones, b_bones):
        np, mesh = self.np, self.mesh
        p = copy.deepcopy(pose)
        p[0] = [4096] * 3 + [0] * 6
        world = mesh.world(mmd.bone_matrices(self.new, p)).astype(float)
        sel = np.isin(mesh.bone, a_bones)
        tri = world[mesh.tri[sel]]
        points = np.vstack([tri.reshape(-1, 3), tri.mean(1)])
        tris = world[mesh.tri[np.isin(mesh.bone, b_bones)]]
        votes = sum(inside(np, points, tris, d).astype(int) for d in DIRS)
        return int((votes >= 3).sum())

    def speed(self, slot):
        fr = self.frames(slot)
        return -(fr[-1][0][8] - fr[0][0][8]) / (len(fr) - 1)

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_only_the_four_clips_and_the_aliases_change(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        self.assertEqual(self.report['changed_slots'], [0, 2, 3, 4, 33])
        self.assertTrue(self.report['mesh_exact'] and self.report['other_programs_exact'])
        for slot in (1, 34, 35, 36):
            self.assertEqual(self.frames(slot), self.frames(slot, self.old))

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, 21)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_cycle_lengths_clips_differ_and_speed_order(self):
        idle, walk, tired, run = (self.frames(s) for s in (0, 2, 3, 4))
        lengths = (len(idle) - 1, len(walk) - 1, len(tired) - 1, len(run) - 1)
        self.assertEqual(lengths, (64, 27, 39, 14))
        self.assertEqual(len(set(lengths)), 4)
        self.assertEqual(self.frames(33), idle)
        self.assertLess(self.speed(3), self.speed(2))
        self.assertLess(self.speed(2), self.speed(4))
        for slot, (low, high) in {2: (15, 31), 3: (10, 20), 4: (35, 52)}.items():
            self.assertTrue(low <= self.speed(slot) <= high, slot)
            self.assertEqual(self.speed(slot), round(self.speed(slot)), slot)
        self.assertNotEqual(walk[1:5], tired[1:5])
        self.assertNotEqual(walk[1:5], run[1:5])
        for fr in (walk, tired, run):
            steps = {fr[i + 1][0][8] - fr[i][0][8] for i in range(len(fr) - 1)}
            self.assertEqual(len(steps), 1)

    def test_loops_are_seamless(self):
        for slot in (0, 2, 3, 4):
            fr = self.frames(slot)
            self.assertEqual(fr[-1][1:], fr[0][1:])

    def test_feet_are_planted_in_stance_and_on_the_floor(self):
        # the soles of the hind plates (bones 12 and 7, where the metrics tool looks) and of the front paws
        np = self.np
        for slot in (2, 3, 4):
            fr = self.frames(slot)[:-1]
            n = len(fr)
            speed = self.speed(slot)
            for bone in (12, 7, 18, 20):
                point = np.array([0, 49, -8, 1.0]) if bone in (18, 20) else np.array([0, 0, 0, 1.0])
                pts = [self.world(p)[bone] @ point for p in fr]
                if slot == 4 and bone in (12, 7):
                    # the gallop's hind feet stand only a couple of ticks, so the mean of the lowest sole vertices of the leg (within 3 units of the lowest) is followed, not the bone origin
                    group = (3, 4, 5, 6, 7) if bone == 7 else (8, 9, 10, 11, 12)
                    pts = []
                    for p in fr:
                        q = copy.deepcopy(p)
                        q[0] = [4096] * 3 + [0, 0, 0, 0, 0, p[0][8]]
                        w = self.new_world(q)
                        sel = self.np.isin(self.mesh.bone, group)
                        v = w[self.mesh.tri[sel]].reshape(-1, 3)
                        pts.append(v[v[:, 1] > v[:, 1].max() - 3].mean(0))
                ys = [q[1] for q in pts]
                # the bone's height while the foot stands is its most common height; it stands while within 2 units of that (the front soles stand at the floor, 0)
                rounded = [round(y) for y in ys]
                stand = 0 if bone in (18, 20) else max(set(rounded), key=rounded.count)
                if slot == 4 and bone in (12, 7):     # the gallop spends most ticks in the air: the standing height is the third-lowest sole height
                    stand = sorted(ys)[-3]
                planted = [t for t in range(n - 1) if abs(ys[t] - stand) <= 2 and abs(ys[t + 1] - stand) <= 2]
                # the longest run of standing ticks, less the settling tick of the touchdown while the swing still brakes
                runs, cur = [], []
                for t in planted:
                    if cur and t != cur[-1] + 1:
                        runs.append(cur)
                        cur = []
                    cur.append(t)
                runs.append(cur)
                planted = max(runs, key=len)
                planted = planted[1:] if len(planted) > 3 else planted
                self.assertGreaterEqual(len(planted), 1 if slot == 4 else 2, (slot, bone))
                slip = [abs(pts[t + 1][2] - pts[t][2]) / speed for t in planted]
                self.assertLess(sum(slip) / len(slip), 0.25, (slot, bone))
                self.assertLess(max(slip), 0.45, (slot, bone))
        if self.old is not None:
            for check in self.report['checks']:
                self.assertLess(check['over'], 1.0, check['slot'])

    def test_no_tick_jumps(self):
        np = self.np
        mesh = self.mesh
        for slot in (0, 2, 3, 4):
            fr = self.frames(slot)
            pts = []
            for pose in fr:
                p = copy.deepcopy(pose)
                p[0] = [4096] * 3 + [0] * 6
                pts.append(mesh.world(mmd.bone_matrices(self.new, p)).astype(float))
            step = [float(np.linalg.norm(pts[i + 1] - pts[i], axis=1).mean()) for i in range(len(pts) - 1)]
            self.assertLess(max(step), 2.5 * sorted(step)[len(step) // 2] + 0.5, slot)

    def test_tired_walk_hangs_its_head_but_faces_forward(self):
        np = self.np
        for slot in (2, 3, 4):
            ratio = []
            for pose in self.frames(slot)[:-1]:
                w = self.world(pose)
                head = w[13]
                snout = w[14]
                # the head's forward axis: from the head bone to the snout; the body's forward is -z
                d = (snout @ np.array([0, 0, 0, 1.0]))[:3] - (head @ np.array([0, 0, 0, 1.0]))[:3]
                d[1] = 0
                yaw = math.degrees(math.atan2(d[0], -d[2]))
                ratio.append(abs(yaw))
            self.assertLess(max(ratio), 22, slot)
        # the tired body rides lower than the walk's, which sits lower than the idle's
        height = lambda slot: sum(f[1][7] for f in self.frames(slot)[:-1]) / (len(self.frames(slot)) - 1)
        self.assertGreater(height(3), height(0))

    def attitude(self, slot):
        """Mean world pitch (degrees, positive = nose down) of the snout line 13->14 and of the line from the rear block to the head."""
        np = self.np
        head, body = [], []
        for pose in self.frames(slot)[:-1]:
            w = self.world(pose)
            o = lambda b: (w[b] @ np.array([0, 0, 0, 1.0]))[:3]
            d = o(14) - o(13)
            head.append(math.degrees(math.atan2(d[1], -d[2])))
            d = o(13) - o(2)
            body.append(math.degrees(math.atan2(d[1], -d[2])))
        return sum(head) / len(head), sum(body) / len(body)

    def test_each_gait_has_its_own_attitude(self):
        walk, tired, run = (self.attitude(s) for s in (2, 3, 4))
        # the tired head hangs lower than the walk's, the run's snout is lower than the walk's too, and the run carries
        # the body forward of the walk's
        self.assertGreater(tired[0], walk[0] + 8)
        self.assertGreater(run[0], walk[0] + 3)
        self.assertGreater(run[1], walk[1] + 1)

    def test_ears_hang_when_tired_and_sweep_back_in_the_run(self):
        # the ear bones' mean pose (degrees) differs from the walk's: out and down when tired, folded back in the run
        def mean(slot, bone, k):
            fr = self.frames(slot)[:-1]
            return sum(f[bone][k] for f in fr) / len(fr) / D
        for bone in (15, 16):
            tired = max(abs(mean(3, bone, k) - mean(2, bone, k)) for k in (3, 4, 5))
            run = max(abs(mean(4, bone, k) - mean(2, bone, k)) for k in (3, 4, 5))
            self.assertGreater(tired, 12, bone)
            self.assertGreater(run, 12, bone)

    def test_the_run_is_a_gallop(self):
        # every foot leaves the floor for at least two ticks at once (the flight), the hind pair and the front pair
        # stand at different times, and the spine flexes (rear block and chest pitch over a wide range)
        np = self.np
        fr = self.frames(4)[:-1]
        low = {}
        for group, name in (((3, 4, 5, 6, 7), 'LH'), ((8, 9, 10, 11, 12), 'RH'), ((17, 18), 'LF'), ((19, 20), 'RF')):
            ys = []
            for p in fr:
                q = copy.deepcopy(p)
                q[0] = [4096] * 3 + [0] * 6
                v = self.new_world(q)[self.mesh.tri[np.isin(self.mesh.bone, group)]].reshape(-1, 3)
                ys.append(v[:, 1].max())
            low[name] = [y > -3 for y in ys]
        air = [not any(low[n][t] for n in low) for t in range(len(fr))]
        self.assertGreaterEqual(sum(air), 2)
        hind = [low['LH'][t] or low['RH'][t] for t in range(len(fr))]
        front = [low['LF'][t] or low['RF'][t] for t in range(len(fr))]
        self.assertFalse(any(h and f for h, f in zip(hind, front)))
        self.assertGreater(sum(hind), 1)
        self.assertGreater(sum(front), 1)
        rear = [p[2][3] / D for p in fr]
        chest = [p[1][3] / D for p in fr]
        self.assertGreater(max(rear) - min(rear), 6)
        self.assertGreater(max(chest) - min(chest), 4)

    def test_it_breathes(self):
        # the idle takes one slow breath (64 ticks, 2.1 s): the chest pitches, the head follows and the flanks swell;
        # the gaits layer a breath on the stride: walk 27 ticks, tired 39 (deeper), run 14 (one gallop cycle, fast and shallow)
        np = self.np
        def rise(slot, bone):
            ys = [(self.world(p)[bone] @ np.array([0, 0, 0, 1.0]))[1] for p in self.frames(slot)[:-1]]
            return max(ys) - min(ys)
        self.assertGreater(rise(0, 13), 5)
        fr = self.frames(0)[:-1]
        scale = [f[2][1] for f in fr]
        self.assertGreater(max(scale) - min(scale), 100)
        pitch = [f[1][3] for f in fr]
        self.assertGreater((max(pitch) - min(pitch)) / D, 3)
        # an asymmetric breath: the inhale (rise of the flank scale) is shorter than the exhale
        top = scale.index(max(scale))
        low = scale.index(min(scale))
        up, down = (top - low) % len(scale), (low - top) % len(scale)
        self.assertLess(min(up, down), max(up, down) - 5)
        for slot in (2, 3, 4):
            sc = [f[2][1] for f in self.frames(slot)[:-1]]
            self.assertGreater(max(sc) - min(sc), 40, slot)
        self.assertGreater(max(f[2][1] for f in self.frames(3)) - min(f[2][1] for f in self.frames(3)),
                           max(f[2][1] for f in self.frames(4)) - min(f[2][1] for f in self.frames(4)))

    def test_the_idle_is_calm_but_alive(self):
        fr = self.frames(0)
        rng = lambda b: max(max(f[b][k] for f in fr) - min(f[b][k] for f in fr) for k in (3, 4, 5)) / D
        for b in (1, 13, 14, 15, 16, 2):
            self.assertGreater(rng(b), 1.0, b)
            self.assertLess(rng(b), 40, b)
        # breathing is a slow pitch of the body (whole units of lift would step every vertex at once)
        self.assertGreater(rng(1), 0.5)
        self.assertLess(rng(1), 6)
        np = self.np
        for bone in (18, 20, 7, 12):
            pts = np.array([(self.world(p)[bone] @ np.array([0, 0, 0, 1.0]))[:3] for p in fr[:-1]])
            self.assertLess(float((pts.max(0) - pts.min(0)).max()), 8, bone)

    def test_penetration_is_not_worse_than_the_imported_clips(self):
        for slot in (0, 2, 3, 4):
            frames = self.frames(slot)[:-1]
            legs = max(self.inside_count(p, LEGS, BODY) for p in frames[::2])
            head = max(self.inside_count(p, HEAD, BODY) for p in frames[::2])
            self.assertLessEqual(legs, OLD_INSIDE[slot][0], slot)
            self.assertLessEqual(head, OLD_INSIDE[slot][1], slot)


if __name__ == '__main__':
    unittest.main()
