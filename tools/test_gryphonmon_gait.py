"""Check Gryphonmon's idle, walk, tired walk and run (species 293) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 293`). Before the change it is
`gryphonmon_gait.SOURCE`: the generator is run on it and its bytes are checked; afterwards it is the result itself and the
checks that need the old clips are skipped (the old model's penetration counts are kept below as numbers).
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
from tools.models.field_animations import gryphonmon_gait as gait
from test_tortomon_gait import inside, DIRS

EXPECTED = 'bc8a53dd61671470dd3918cf7c5c6e85906d66d4f3af020184a57dbf7867e807'
LEGS = [9, 10, 11, 12, 13, 14, 19, 20, 21, 22, 23, 24]
BODY = [1, 6]
HEAD = [7, 8]
WINGS = [15, 16, 17, 18]
# the previous clips' worst vertex counts inside the body (legs, head, wings), per slot: idle, walk, tired, run
OLD_INSIDE = {0: (27, 27, 0), 2: (28, 29, 2), 3: (28, 29, 2), 4: (28, 29, 2)}
BONES = 25
# the sole pivots of the paws (bone, point in the bone's space), as in the generator's profile
SOLES = {11: [0, 46, -40], 14: [0, 46, -40], 21: [0, 41, -50], 24: [0, 41, -50]}


class GryphonmonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        path = Path('build/imported-model-edit/edit/293-Gryphonmon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 293')
        cls.rig = json.loads(Path('content/species/293-gryphonmon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[293] = cls.rig
        mmd.exe().bone_count[293] = len(cls.rig)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gait.SOURCE:
            cls.old = mmd.MMD.parse(data, BONES)
            cls.old.type = 293
            data, cls.report = gait.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.new = mmd.MMD.parse(data, BONES)
        cls.new.type = 293
        import animstudio
        cls.mesh = animstudio.FastMesh(SimpleNamespace(m=cls.new, skel=cls.rig))

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.new, BONES, slot)[0]

    def world(self, pose):
        p = copy.deepcopy(pose)
        p[0] = [4096] * 3 + [0, 0, 0, 0, 0, p[0][8]]
        return [self.np.array(m, float) for m in mmd.bone_matrices(self.new, p)]

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

    def test_only_the_four_clips_change(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        self.assertEqual(self.report['changed_slots'], [0, 2, 3, 4])
        self.assertTrue(self.report['mesh_exact'] and self.report['other_programs_exact'])
        for slot in (1, 33, 35, 36, 42):
            self.assertEqual(self.frames(slot), self.frames(slot, self.old))

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, BONES)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_cycle_lengths_clips_differ_and_speed_order(self):
        idle, walk, tired, run = (self.frames(s) for s in (0, 2, 3, 4))
        lengths = (len(idle) - 1, len(walk) - 1, len(tired) - 1, len(run) - 1)
        self.assertEqual(lengths, (96, 22, 28, 16))
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
        np = self.np
        for slot in (2, 3, 4):
            fr = self.frames(slot)[:-1]
            n = len(fr)
            speed = self.speed(slot)
            for bone, pivot in SOLES.items():
                point = np.array(pivot + [1.0])
                pts = [self.world(p)[bone] @ point for p in fr]
                ys = [q[1] for q in pts]
                # a foot stands at its most common height (the gallop spends most ticks in the air: the third-lowest)
                rounded = [round(y) for y in ys]
                stand = sorted(ys)[-3] if slot == 4 else max(set(rounded), key=rounded.count)
                planted = [t for t in range(n - 1) if abs(ys[t] - stand) <= 2 and abs(ys[t + 1] - stand) <= 2]
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
                self.assertLess(abs(stand), 6, (slot, bone))
        if self.old is not None:
            for check in self.report['checks']:
                self.assertGreater(check['lowest_point'], -3, check['slot'])

    def test_no_tick_jumps(self):
        np = self.np
        for slot in (0, 2, 3, 4):
            pts = []
            for pose in self.frames(slot):
                p = copy.deepcopy(pose)
                p[0] = [4096] * 3 + [0] * 6
                pts.append(self.mesh.world(mmd.bone_matrices(self.new, p)).astype(float))
            step = [float(np.linalg.norm(pts[i + 1] - pts[i], axis=1).mean()) for i in range(len(pts) - 1)]
            self.assertLess(max(step), 2.5 * sorted(step)[len(step) // 2] + 0.5, slot)

    def test_each_wing_is_one_flowing_chain(self):
        np = self.np
        D = 4096 / 360
        for slot in (2, 3, 4):
            fr = self.frames(slot)[:-1]
            for arm, fan in ((15, 16), (17, 18)):
                z = lambda b: np.array([f[b][5] for f in fr], float) / D
                # the whole wing beats large enough to read from the front, the fan trailing its arm on the hinge axis only
                self.assertGreaterEqual(np.ptp(z(arm)), 28 if slot != 3 else 24, (slot, arm))
                self.assertGreaterEqual(np.ptp(z(fan)), np.ptp(z(arm)), (slot, fan))
                self.assertEqual({f[fan][3] for f in fr} | {f[fan][4] for f in fr}, {0}, (slot, fan))
                a, b = z(arm) - z(arm).mean(), z(fan) - z(fan).mean()
                lag = max(range(len(fr)), key=lambda k: float(np.dot(a, np.roll(b, -k))))
                self.assertTrue(1 <= min(lag, len(fr) - lag) <= 5, (slot, fan, lag))
                self.assertLess(np.ptp(z(fan)), 62, (slot, fan))
        for slot in (0, 2, 3, 4):
            fr = self.frames(slot)[:-1]
            for arm, fan in ((15, 16), (17, 18)):
                self.assertEqual({f[fan][3] for f in fr} | {f[fan][4] for f in fr}, {0}, (slot, fan))
        self.assertNotEqual(self.frames(2)[3][15], self.frames(3)[3][15])

    def test_the_wing_pieces_stay_joined(self):
        np = self.np
        for slot in (0, 2, 3, 4):
            for pose in self.frames(slot)[:-1]:
                p = copy.deepcopy(pose)
                p[0] = [4096] * 3 + [0] * 6
                world = self.mesh.world(mmd.bone_matrices(self.new, p)).astype(float)
                for arm, fan in ((15, 16), (17, 18)):
                    a = world[self.mesh.tri[np.isin(self.mesh.bone, arm)]].reshape(-1, 3)
                    f = world[self.mesh.tri[np.isin(self.mesh.bone, fan)]].reshape(-1, 3)
                    gap = float(np.sqrt(((a[:, None] - f[None]) ** 2).sum(-1)).min())
                    self.assertLess(gap, 2.5, (slot, arm))

    def test_penetration_is_not_worse_than_the_previous_clips(self):
        for slot in (0, 2, 3, 4):
            frames = self.frames(slot)[:-1]
            legs = max(self.inside_count(p, LEGS, BODY) for p in frames[::2])
            head = max(self.inside_count(p, HEAD, BODY) for p in frames[::2])
            wings = max(self.inside_count(p, WINGS, BODY + HEAD) for p in frames[::2])
            self.assertLessEqual(legs, OLD_INSIDE[slot][0], slot)
            self.assertLessEqual(head, OLD_INSIDE[slot][1], slot)
            self.assertLessEqual(wings, OLD_INSIDE[slot][2], slot)


if __name__ == '__main__':
    unittest.main()
