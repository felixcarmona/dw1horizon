"""Check Starmon's refined legs, arms, head carriage and flowing ribbons on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 243`). Before the change it is
`star_gait_refine.SOURCE`: the generator is run on it and its bytes are checked; afterwards it is the result itself and
the checks that need the old clips are skipped.
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
from motiondiscidentity import changed_programs
from tools.models.field_animations import star_gait_refine as gait

EXPECTED = '67a8504a372e94e13a1541f491a03a9ded6a83843920823a680bae9a29361cbc'
LEFT, RIGHT = (8, 9, 10, 11), (12, 13, 14, 15)
TORSO = (1, 2, 3, 4, 5, 6, 7)
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


class StarmonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        path = Path('build/imported-model-edit/edit/243-Starmon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 243')
        cls.rig = json.loads(Path('content/species/243-starmon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[243] = cls.rig
        mmd.exe().bone_count[243] = len(cls.rig)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gait.SOURCE:
            cls.old = mmd.MMD.parse(data, 20)
            cls.old.type = 243
            data, cls.report = gait.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.new = mmd.MMD.parse(data, 20)
        cls.new.type = 243
        cls.body = gait.Body(cls.new)
        import animstudio
        cls.mesh = animstudio.FastMesh(SimpleNamespace(m=cls.new, skel=cls.rig))

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.new, 20, slot)[0]

    def need_old(self):
        if self.old is None:
            self.skipTest('needs the model before this change')

    def inside_count(self, pose, a_bones, b_bones, socket=None):
        """Vertices and triangle centres of a_bones inside the closed meshes of b_bones (majority of five rays)."""
        np, mesh = self.np, self.mesh
        p = copy.deepcopy(pose)
        p[0] = [4096]*3 + [0]*6
        world = mesh.world(mmd.bone_matrices(self.new, p)).astype(float)
        sel = np.isin(mesh.bone, a_bones)
        tri = world[mesh.tri[sel]]
        points = np.vstack([tri.reshape(-1, 3), tri.mean(1)])
        if socket is not None:           # the shoulder joint itself is built inside the torso
            joint = np.array(mmd.bone_matrices(self.new, p)[socket], float)[:3, 3]
            points = points[np.linalg.norm(points - joint, axis=1) > 30]
        tris = world[mesh.tri[np.isin(mesh.bone, b_bones)]]
        votes = sum(inside(np, points, tris, d).astype(int) for d in DIRS)
        return int((votes >= 3).sum())

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_only_the_four_clips_and_their_aliases_change(self):
        self.need_old()
        self.assertEqual(changed_programs(self.old, self.new), [0, 2, 3, 4, 35, 36])      # 35 and 36 play the walk's and the run's clips
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, 20)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_the_legs_never_go_through_each_other(self):
        for slot in (2, 3, 4):
            for tick, pose in enumerate(self.frames(slot)[:-1]):
                self.assertEqual(self.inside_count(pose, LEFT, RIGHT), 0, (slot, tick))
                self.assertEqual(self.inside_count(pose, RIGHT, LEFT), 0, (slot, tick))

    def test_the_legs_stay_out_of_the_body(self):
        # hips, thighs, shins and boots against the torso, star plate and head mesh, idle included
        for slot in (0, 2, 3, 4):
            poses = self.frames(slot)[:-1]
            for tick in range(0, len(poses), 4 if slot == 0 else 1):
                self.assertLessEqual(self.inside_count(poses[tick], LEFT + RIGHT, [1]), 8, (slot, tick))

    def test_the_old_legs_did_go_through_the_body(self):
        self.need_old()
        worst = max(self.inside_count(pose, LEFT + RIGHT, [1]) for pose in self.frames(2, self.old)[:-1])
        self.assertGreater(worst, 20)

    def test_the_old_clips_did_cross(self):
        self.need_old()
        crossings = [self.inside_count(pose, LEFT, RIGHT) + self.inside_count(pose, RIGHT, LEFT)
                     for pose in self.frames(4, self.old)[:-1]]
        self.assertGreater(max(crossings), 0)

    def test_head_stays_up(self):
        # bone 1 carries the star plate and the head: its pitch (4096 = 360 degrees) is the head's lean over the horizon
        limits = {0: 20, 2: 28, 3: 38, 4: 32}                    # degrees; the old clips reached 41, 61 and 79
        for slot, limit in limits.items():
            pitch = [p[1][3] for p in self.frames(slot)[:-1]]
            self.assertLess(max(pitch), 4096*limit/360, slot)
            self.assertGreater(min(pitch), 0, slot)                # and never tipped backwards
        self.assertLess(max(p[1][3] for p in self.frames(4)[:-1]) - min(p[1][3] for p in self.frames(4)[:-1]), 4096*10/360)

    def test_arms_stay_out_of_the_body(self):
        for slot in (0, 2, 3, 4):
            for tick, pose in list(enumerate(self.frames(slot)[:-1]))[::6 if slot == 0 else 1]:
                for shoulder, other in ((2, 5), (5, 2)):
                    arm = (shoulder, shoulder + 1, shoulder + 2)
                    self.assertEqual(self.inside_count(pose, arm, (other, other + 1, other + 2), shoulder), 0, (slot, tick))
                    self.assertLessEqual(self.inside_count(pose, arm, tuple(range(8, 16)), shoulder), 8, (slot, tick))
                    self.assertLessEqual(self.inside_count(pose, arm, (1,), shoulder), 110, (slot, tick))   # the star's spikes
        # the arms still swing against each other
        for slot in (2, 3, 4):
            frames = self.frames(slot)[:-1]
            left = [p[3][3] for p in frames]
            right = [p[6][3] for p in frames]
            self.assertGreater(max(left) - min(left), 60, slot)
            self.assertGreater(max(right) - min(right), 60, slot)

    def test_old_arms_did_go_through_the_body(self):
        self.need_old()
        worst = 0
        for pose in self.frames(3, self.old)[:-1]:
            worst = max(worst, self.inside_count(pose, (2, 3, 4), tuple(range(8, 16)), 2))
        self.assertGreater(worst, 100)

    def test_ribbons_hang_down_and_flow(self):
        np = self.np
        ranges = {0: (4, 14), 2: (12, 30), 3: (12, 32), 4: (22, 58)}      # degrees from the mean direction; the old clips swung 26 to 80
        for slot, (low, high) in ranges.items():
            frames = self.frames(slot)[:-1]
            worlds = [self.body.world(p) for p in frames]
            for root, tip, side in gait.RIG['ribbons']:
                swings = []
                for bone in (root, tip):
                    axes = [w[bone, :3, :3] @ np.array([0, 0, 1.]) for w in worlds]
                    mean = sum(axes)/len(axes)
                    mean = mean/np.linalg.norm(mean)
                    self.assertGreater(float(mean[1]), .25, (slot, bone))        # y is down: it hangs
                    swings.append(max(math.degrees(math.atan2(float(np.linalg.norm(np.cross(mean, a))), float(mean @ a)))
                                      for a in axes))
                self.assertTrue(all(low < x < high for x in swings), (slot, root, swings))

    def test_ribbon_joint_is_a_hinge_and_loops_are_seamless(self):
        for slot in (0, 2, 3, 4):
            frames = self.frames(slot)
            self.assertEqual(frames[-1][1:], frames[0][1:])
            for p in frames:
                for tip in (17, 19):
                    self.assertEqual(p[tip][4:6], [0, 0])
            for a, b in zip(frames, frames[1:]):
                for bone in (16, 17, 18, 19):
                    for k in (3, 4, 5):
                        self.assertLess(abs(a[bone][k] - b[bone][k]), 700, (slot, bone))   # never a half turn between ticks

    def test_speeds_and_feet_are_kept(self):
        self.need_old()
        for slot, speed in ((2, 14.6), (3, 13.0), (4, 32.5)):
            old = mmd.AnimPlayer(self.old.anims.anims[self.old.anims.table[slot]], 20, slot)
            new = mmd.AnimPlayer(self.new.anims.anims[self.new.anims.table[slot]], 20, slot)
            for _ in range(len(self.frames(slot))):
                self.assertTrue(old.tick() and new.tick())
                self.assertEqual(old.base, new.base)
            for a, b in zip(self.frames(slot, self.old), self.frames(slot)):
                wa, wb = self.body.world(a), self.body.world(b)
                for boot in (11, 15):
                    # the boots keep their height (so planting) and fore-aft place; only the sideways spread differs
                    self.assertLess(abs(float(wa[boot, 1, 3] - wb[boot, 1, 3])), 12, (slot, boot))
                    self.assertLess(abs(float(wa[boot, 2, 3] - wb[boot, 2, 3])), 3, (slot, boot))


if __name__ == '__main__':
    unittest.main()
