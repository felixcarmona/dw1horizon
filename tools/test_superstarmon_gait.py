"""Check SuperStarmon's clips (Starmon's refined clips on its larger body) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 244`). Before the change it is
`superstar_gait.SOURCE`: the generator is run on it (with Starmon's clips from `get 243`) and its bytes are checked;
afterwards it is the result itself and the checks that need the old clips are skipped.
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
from test_starmon_gait import DIRS, LEFT, RIGHT, inside
from tools.models.field_animations import superstar_gait as gait

EXPECTED = 'e350b6b890f28d96184c61ad4feb41755e02f228cb2b9dcb6d1cb6ae16c7075d'
BONES = 27


class SuperStarmonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        path = Path('build/imported-model-edit/edit/244-SuperStarmon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 244')
        cls.rig = json.loads(Path('content/species/244-superstarmon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[244] = cls.rig
        mmd.exe().bone_count[244] = len(cls.rig)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gait.SOURCE:
            starmon = Path('build/imported-model-edit/edit/243-Starmon.MMD')
            if not starmon.exists():
                raise unittest.SkipTest('reconstruct with tools/models/edit.py get 243')
            cls.old = mmd.MMD.parse(data, BONES)
            cls.old.type = 244
            data, cls.report = gait.build(data, cls.rig, starmon.read_bytes())
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.new = mmd.MMD.parse(data, BONES)
        cls.new.type = 244
        import animstudio
        cls.mesh = animstudio.FastMesh(SimpleNamespace(m=cls.new, skel=cls.rig))

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.new, BONES, slot)[0]

    def need_old(self):
        if self.old is None:
            self.skipTest('needs the model before this change')

    def inside_count(self, pose, a_bones, b_bones, socket=None):
        np, mesh = self.np, self.mesh
        p = copy.deepcopy(pose)
        p[0] = [4096]*3 + [0]*6
        world = mesh.world(mmd.bone_matrices(self.new, p)).astype(float)
        sel = np.isin(mesh.bone, a_bones)
        tri = world[mesh.tri[sel]]
        points = np.vstack([tri.reshape(-1, 3), tri.mean(1)])
        if socket is not None:
            joint = np.array(mmd.bone_matrices(self.new, p)[socket], float)[:3, 3]
            points = points[np.linalg.norm(points - joint, axis=1) > 30*gait.SCALE]
        tris = world[mesh.tri[np.isin(mesh.bone, b_bones)]]
        votes = sum(inside(np, points, tris, d).astype(int) for d in DIRS)
        return int((votes >= 3).sum())

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_only_the_four_clips_and_their_aliases_change(self):
        self.need_old()
        self.assertEqual(changed_programs(self.old, self.new), [0, 2, 3, 4])
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, BONES)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_speeds_and_cycle_lengths(self):
        for slot, speed in ((2, 19.5), (3, 13.5), (4, 37.9)):
            frames = self.frames(slot)
            self.assertEqual(len(frames), gait.TICKS[slot], slot)
            travel = abs(frames[-1][0][8] - frames[0][0][8])
            self.assertAlmostEqual(travel/(len(frames) - 1), speed, delta=.6, msg=slot)

    def test_the_legs_never_go_through_each_other(self):
        for slot in (2, 3, 4):
            for tick, pose in enumerate(self.frames(slot)[:-1]):
                self.assertEqual(self.inside_count(pose, LEFT, RIGHT), 0, (slot, tick))
                self.assertEqual(self.inside_count(pose, RIGHT, LEFT), 0, (slot, tick))

    def test_the_legs_stay_out_of_the_body(self):
        for slot in (0, 2, 3, 4):
            poses = self.frames(slot)[:-1]
            for tick in range(0, len(poses), 4 if slot == 0 else 1):
                self.assertLessEqual(self.inside_count(poses[tick], LEFT + RIGHT, [1]), 8, (slot, tick))

    def test_arms_stay_out_of_the_legs_and_each_other(self):
        for slot in (0, 2, 3, 4):
            for tick, pose in list(enumerate(self.frames(slot)[:-1]))[::6 if slot == 0 else 1]:
                for shoulder, other in ((2, 5), (5, 2)):
                    arm = (shoulder, shoulder + 1, shoulder + 2)
                    self.assertEqual(self.inside_count(pose, arm, (other, other + 1, other + 2), shoulder), 0, (slot, tick))
                    self.assertLessEqual(self.inside_count(pose, arm, tuple(range(8, 16)), shoulder), 8, (slot, tick))

    def test_idle_hangs_the_arms(self):
        # y is down: the fists are below the shoulders and the head is carried up
        body = gait.star.Body(self.new)
        for pose in self.frames(0)[:-1:6]:
            w = body.world(pose)
            for shoulder, fist in ((2, 4), (5, 7)):
                self.assertGreater(float(w[fist, 1, 3] - w[shoulder, 1, 3]), 100)

    def test_loops_are_seamless(self):
        for slot in (0, 2, 3, 4):
            frames = self.frames(slot)
            for a, b in zip(frames[-1][1:], frames[0][1:]):
                self.assertTrue(all(abs(x - y) <= 3 for x, y in zip(a, b)), (slot, a, b))      # keys are packed within 1 unit


if __name__ == '__main__':
    unittest.main()
