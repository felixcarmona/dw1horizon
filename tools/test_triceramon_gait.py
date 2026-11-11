"""Check Triceramon's authored idle, walk, tired walk and run on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 257`). Before the change it is
`triceramon_gait.SOURCE`: the generator is run on it and its bytes are checked; afterwards it is the result itself and
the checks that need the old clips are skipped.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import animstudio
import mmd
from motiondiscidentity import changed_programs
from test_starmon_gait import inside, DIRS
from tools.models.field_animations import triceramon_gait as gait

EXPECTED = '35f2feb64f59bb842dcaef2b4839110e2e40611df47b42193ad22b3592e3c3ab'
SPEEDS = {2: 16, 3: 11, 4: 38}
GROUPS = {'legR': (15, 16, 17), 'legL': (18, 19, 20), 'armR': (5, 6, 7), 'armL': (8, 9, 10), 'body': (1, 11),
          'head': (2, 3, 4)}
# the original arms swung through the same-side leg (up to 106 points of the arm mesh inside the leg)
PAIRS = (('armR', 'legR'), ('armL', 'legL'), ('head', 'body'), ('legR', 'body'), ('legL', 'body'))
LIMITS = {('armR', 'legR'): 30, ('armL', 'legL'): 30, ('head', 'body'): 45, ('legR', 'body'): 60, ('legL', 'body'): 60}


class TriceramonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('build/imported-model-edit/edit/257-Triceramon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 257')
        cls.rig = json.loads(Path('content/species/257-triceramon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[257] = cls.rig
        mmd.exe().bone_count[257] = len(cls.rig)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gait.SOURCE:
            cls.old = mmd.MMD.parse(data, 21)
            cls.old.type = 257
            data, cls.report = gait.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.new = mmd.MMD.parse(data, 21)
        cls.new.type = 257
        cls.body = gait.Body(cls.new, cls.rig)

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.new, 21, slot)[0]

    def need_old(self):
        if self.old is None:
            self.skipTest('needs the model before this change')

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_only_the_four_field_clips_change(self):
        self.need_old()
        self.assertEqual(changed_programs(self.old, self.new), [0, 2, 3, 4])
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())
        for slot in (1, 5, 33):
            self.assertEqual(self.frames(slot), self.frames(slot, self.old), slot)

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, 21)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_speeds_are_ordered_tired_walk_run(self):
        speed = {}
        for slot in SPEEDS:
            player = mmd.AnimPlayer(self.new.anims.anims[self.new.anims.table[slot]], 21, slot)
            player.tick()
            player.tick()
            speed[slot] = -player.base[2]
            self.assertEqual(speed[slot], SPEEDS[slot], slot)
        self.assertLess(speed[3], speed[2])
        self.assertLess(speed[2], speed[4])
        self.assertGreater(len(self.frames(3)), len(self.frames(2)))     # slower and longer step
        self.assertGreater(len(self.frames(2)), len(self.frames(4)))

    def test_loops_close(self):
        for slot in (0, 2, 3, 4):
            frames = self.frames(slot)
            self.assertEqual(frames[-1][1:], frames[0][1:], slot)

    def test_idle_is_planted_and_breathes(self):
        frames = self.frames(0)
        ankles = [[self.body.world(p)[b, :3, 3] for b in (17, 20)] for p in frames]
        for i in range(2):
            for a in ankles:
                self.assertLess(float(abs(a[i] - ankles[0][i]).max()), 3.5)
        for bone in (1, 2, 3, 12, 13, 14):
            spans = [max(p[bone][k] for p in frames) - min(p[bone][k] for p in frames) for k in (3, 4, 5)]
            self.assertGreater(max(spans), 8, bone)

    def test_stance_feet_are_planted(self):
        # the stance ankle is solved onto a point that moves back by exactly the root speed
        for slot, speed in SPEEDS.items():
            frames = self.frames(slot)
            n = len(frames) - 1
            for foot in (17, 20):
                pos = [float(self.body.world(p)[foot, 2, 3]) - speed * t for t, p in enumerate(frames)]
                height = [float(-self.body.world(p)[foot, 1, 3]) for p in frames]
                floor = min(height)
                stance = [t for t in range(n) if height[t] - floor < 3]
                self.assertGreaterEqual(len(stance), 4, (slot, foot))
                slip = [abs(pos[t + 1] - pos[t]) for t in stance if t + 1 in stance]
                self.assertLessEqual(sum(slip) / max(1, len(slip)), .3 * speed + 1, (slot, foot))

    def test_the_body_bobs_with_the_steps(self):
        # the torso rides up and down with every step instead of gliding on a rail (peak to peak, units)
        for slot, least in ((2, 14), (3, 9), (4, 24)):
            pelvis = [-float(self.body.world(p)[11, 1, 3]) for p in self.frames(slot)]
            self.assertGreaterEqual(max(pelvis) - min(pelvis), least, slot)
        self.assertLess(max(-float(self.body.world(p)[11, 1, 3]) for p in self.frames(3)),
                        max(-float(self.body.world(p)[11, 1, 3]) for p in self.frames(2)))

    def test_gaits_stay_on_the_floor(self):
        for slot in (0, 2, 3, 4):
            low = [self.body.lowest(p) for p in self.frames(slot)]
            self.assertGreaterEqual(min(low), -4, slot)
            self.assertLessEqual(max(low), 30 if slot == 4 else 12, slot)     # the run has a short flight

    def test_limbs_do_not_pass_through_the_body(self):
        import numpy
        m = self.new
        mesh = animstudio.FastMesh(SimpleNamespace(m=m, skel=self.rig))
        for slot in (2, 3, 4):
            worst = {}
            for pose in self.frames(slot)[:-1:2]:
                p = copy.deepcopy(pose)
                p[0] = [4096] * 3 + [0] * 6
                W = mesh.world(mmd.bone_matrices(m, p)).astype(float)
                for a, b in PAIRS:
                    tri = W[mesh.tri[numpy.isin(mesh.bone, GROUPS[a])]]
                    pts = numpy.vstack([tri.reshape(-1, 3), tri.mean(1)])
                    tris = W[mesh.tri[numpy.isin(mesh.bone, GROUPS[b])]]
                    votes = sum(inside(numpy, pts, tris, d).astype(int) for d in DIRS)
                    worst[(a, b)] = max(worst.get((a, b), 0), int((votes >= 3).sum()))
            for pair, count in worst.items():
                self.assertLessEqual(count, LIMITS[pair], (slot, pair, count))


if __name__ == '__main__':
    unittest.main()
