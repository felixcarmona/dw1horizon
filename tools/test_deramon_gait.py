"""Check Deramon's idle, walk, tired walk and run (species 286) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 286`). Before the change it is
`deramon_gait.SOURCE`: the generator is run on it and its bytes are checked; afterwards it is the result itself and the
checks that need the old clips are skipped (the old penetration counts are kept below).
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
from tools.models.field_animations import deramon_gait as gait
from test_tortomon_gait import inside, DIRS

EXPECTED = '7d51320b1e73bc167591d4a8a97ae7a9aca748c7af06d5d981e47ad4272090b8'
D = 4096 / 360
# the most points of one part inside another's mesh over the four old clips (before this change), sampled the same way
OLD = {'feet>body': 218, 'body>shell': 56, 'head>shell': 114, 'wings>shell': 16, 'head>body': 16, 'wings>body': 58,
       'shell>body': 8, 'feet>shell': 22}
PAIRS = {'feet>body': ([3, 4], [2]), 'body>shell': ([2], [1]), 'head>shell': ([5], [1]), 'wings>shell': ([6, 7], [1]),
         'head>body': ([5], [2]), 'wings>body': ([6, 7], [2]), 'shell>body': ([1], [2]), 'feet>shell': ([3, 4], [1])}


class DeramonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        path = Path('build/imported-model-edit/edit/286-Deramon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 286')
        cls.rig = json.loads(Path('content/species/286-deramon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[286] = cls.rig
        mmd.exe().bone_count[286] = 8
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gait.SOURCE:
            cls.old = mmd.MMD.parse(data, 8)
            cls.old.type = 286
            data, cls.report = gait.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.new = mmd.MMD.parse(data, 8)
        cls.new.type = 286
        import animstudio
        cls.mesh = animstudio.FastMesh(SimpleNamespace(m=cls.new, skel=cls.rig))
        cls.cache = {}

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.new, 8, slot)[0]

    def worlds(self, slot):
        """The world vertices of every tick of a clip (root travel left out) -> (ticks+1, vertices, 3)."""
        if slot not in self.cache:
            out = []
            for f in self.frames(slot):
                p = copy.deepcopy(f)
                p[0] = [4096] * 3 + [0] * 6
                out.append(self.mesh.world(mmd.bone_matrices(self.new, p)).astype(float))
            self.cache[slot] = out
        return self.cache[slot]

    def speed(self, slot):
        fr = self.frames(slot)
        return -(fr[-1][0][8] - fr[0][0][8]) / (len(fr) - 1)

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_only_the_four_clips_and_the_idle_alias_change(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        self.assertEqual(self.report['changed_slots'], [0, 2, 3, 4, 33])
        self.assertTrue(self.report['mesh_exact'] and self.report['other_programs_exact'])
        for slot in (1, 5, 14, 34, 35, 36):
            self.assertEqual(self.frames(slot), self.frames(slot, self.old))

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, 8)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_cycle_lengths_clips_differ_and_speed_order(self):
        idle, walk, tired, run = (self.frames(s) for s in (0, 2, 3, 4))
        self.assertEqual((len(idle) - 1, len(walk) - 1, len(tired) - 1, len(run) - 1), (120, 16, 20, 10))
        self.assertLess(self.speed(3), self.speed(2))
        self.assertLess(self.speed(2), self.speed(4))
        for slot, (low, high) in gait.SPEED_RANGE.items():
            self.assertTrue(low <= self.speed(slot) <= high, slot)
        for a, b in ((walk, tired), (walk, run), (tired, run)):
            self.assertNotEqual(a[1:5], b[1:5])
        for fr in (walk, tired, run):          # the root moves the same distance every tick
            self.assertEqual(len({fr[i + 1][0][8] - fr[i][0][8] for i in range(len(fr) - 1)}), 1)
        self.assertEqual(self.frames(33), idle)

    def test_loops_are_seamless(self):
        for slot in (0, 2, 3, 4):
            fr = self.frames(slot)
            self.assertEqual(fr[-1][1:], fr[0][1:])

    def test_feet_are_planted_flat_and_on_the_floor(self):
        np = self.np
        feet = np.isin(self.mesh.bone, [3, 4])
        for slot in (2, 3, 4):
            W = self.worlds(slot)
            n = len(W) - 1
            speed = self.speed(slot)
            slips = []
            for foot, bone in ((3, 3), (4, 4)):
                sel = np.isin(self.mesh.bone, [bone])
                low = [w[self.mesh.tri[sel]][..., 1].max() for w in W]
                self.assertLess(max(low), 3.0, (slot, 'sinks'))
                self.assertGreater(min(low), -50, slot)
                down = [i for i in range(n) if low[i] > -1.5 and low[i + 1] > -1.5]
                self.assertGreater(len(down), 2, (slot, foot))
                for i in down:
                    z0 = W[i][self.mesh.tri[sel]][..., 2].mean()
                    z1 = W[i + 1][self.mesh.tri[sel]][..., 2].mean()
                    slips.append(abs((z1 - speed) - z0) / speed)
                    # flat: the foot's own up axis stays within a few degrees of the vertical
                    p = copy.deepcopy(self.frames(slot)[i])
                    p[0] = [4096] * 3 + [0] * 6
                    R = mmd.bone_matrices(self.new, p)[bone]
                    self.assertLess(math.degrees(math.acos(min(1, abs(R[1][1])))), 4.0, (slot, i))
            self.assertLess(sum(slips) / len(slips), 0.25, slot)
            self.assertLess(max(slips), 0.45, slot)

    def test_both_feet_leave_the_ground_in_the_run(self):
        np = self.np
        W = self.worlds(4)
        lows = [max(w[self.mesh.tri[np.isin(self.mesh.bone, [3, 4])]][..., 1].max() for _ in (0,)) for w in W]
        self.assertLess(min(lows), -10)       # a flight phase: the lowest foot point is well off the floor

    def test_shell_stays_off_the_floor_and_on_it(self):
        np = self.np
        for slot in (0, 2, 3, 4):
            low = [w[self.mesh.tri[np.isin(self.mesh.bone, [1])]][..., 1].max() for w in self.worlds(slot)]
            self.assertLess(max(low), 2.0, slot)          # never into the floor
            self.assertGreater(min(low), -45, slot)       # and never far off it

    def test_no_tick_jumps(self):
        np = self.np
        for slot in (0, 2, 3, 4):
            W = self.worlds(slot)
            sp = [np.linalg.norm(W[(i + 1) % (len(W) - 1)] - W[i % (len(W) - 1)], axis=1).mean() for i in range(len(W) - 1)]
            self.assertLess(max(sp), 2.5 * float(np.median(sp)) + 0.01, slot)

    def test_penetration_is_not_worse_than_before(self):
        np, mesh = self.np, self.mesh
        worst = {k: 0 for k in PAIRS}
        for slot in (0, 2, 3, 4):
            W = self.worlds(slot)
            step = max(1, (len(W) - 1) // 30)
            for w in W[:-1:step]:
                for k, (a, b) in PAIRS.items():
                    tri = w[mesh.tri[np.isin(mesh.bone, a)]]
                    pts = np.vstack([tri.reshape(-1, 3), tri.mean(1)])
                    tris = w[mesh.tri[np.isin(mesh.bone, b)]]
                    votes = sum(inside(np, pts, tris, d).astype(int) for d in DIRS)
                    worst[k] = max(worst[k], int((votes >= 3).sum()))
        for k, old in OLD.items():
            self.assertLessEqual(worst[k], old * 1.1 + 4, (k, worst[k], old))

    def test_the_body_bobs_sways_and_the_shell_moves_against_it(self):
        rng = lambda fr, b, k: (max(f[b][k] for f in fr[:-1]) - min(f[b][k] for f in fr[:-1]))
        for slot in (2, 3, 4):
            fr = self.frames(slot)
            self.assertGreater(rng(fr, 1, 7), 6, slot)                     # the shell bone's lift (bob)
            self.assertGreater(max(rng(fr, 1, k) for k in (3, 4, 5)) / D, 5, slot)
            # the body bone moves against the shell bone (it is its child): its local rotation changes
            self.assertGreater(max(rng(fr, 2, k) for k in (3, 4, 5)) / D, 2, slot)
        # the body leans forward most in the run, then in the tired walk, and least in the walk (world pitch of the body)
        def lean(slot):
            out = []
            for f in self.frames(slot)[:-1]:
                p = copy.deepcopy(f)
                p[0] = [4096] * 3 + [0] * 6
                R = mmd.bone_matrices(self.new, p)[2]
                out.append(math.degrees(math.atan2(-R[1][2], R[2][2])))
            return sum(out) / len(out)
        self.assertGreater(abs(lean(4)), abs(lean(3)))
        self.assertGreater(abs(lean(3)), abs(lean(2)) + 2)

    def test_wings_swing_against_each_other_and_the_head_bobs(self):
        np = self.np
        for slot in (2, 3):
            fr = self.frames(slot)[:-1]
            r = np.array([f[6][3] for f in fr], float)
            l = np.array([f[7][3] for f in fr], float)
            self.assertLess(float(np.corrcoef(r, l)[0, 1]), -0.3, slot)
            self.assertGreater((r.max() - r.min()) / D, 8, slot)
        for slot in (2, 3, 4):
            fr = self.frames(slot)[:-1]
            self.assertGreater(max(max(f[5][k] for f in fr) - min(f[5][k] for f in fr) for k in (3, 4, 5)) / D, 4, slot)

    def test_the_idle_is_calm_but_alive(self):
        fr = self.frames(0)
        rng = lambda b: max(max(f[b][k] for f in fr) - min(f[b][k] for f in fr) for k in (3, 4, 5)) / D
        self.assertGreater(rng(5), 8)        # the head looks about
        self.assertLess(rng(5), 40)
        for b in (6, 7):
            self.assertGreater(rng(b), 4)
            self.assertLess(rng(b), 20)
        self.assertLess(rng(1), 8)
        self.assertGreater(rng(1), 1.5)      # the shell rocks a little behind the breath
        lift = [f[1][7] for f in fr]
        self.assertGreater(max(lift) - min(lift), 2)
        self.assertLess(max(lift) - min(lift), 14)
        # the feet stay where they are: the idle never moves a foot more than rounding
        W = self.worlds(0)
        np = self.np
        for bone in (3, 4):
            sel = np.isin(self.mesh.bone, [bone])
            pts = np.array([w[self.mesh.tri[sel]].mean((0, 1)) for w in W])
            self.assertLess(float((pts.max(0) - pts.min(0)).max()), 2.5, bone)

    def test_the_blink_is_kept(self):
        events = animsheet.slot_frames(self.new, 8, 0)[2]
        self.assertEqual([t for t, k, e in events if k == 'tex'], [0, 38, 39, 41, 42, 92, 93, 95, 96])
        self.assertEqual(events[0][2]['src'], events[4][2]['src'])        # eyes open again after each blink


if __name__ == '__main__':
    unittest.main()
