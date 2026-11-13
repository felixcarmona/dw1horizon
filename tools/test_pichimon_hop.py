"""Pichimon's (471) four calm field clips: native speeds in order, a planted body, the mesh never under the floor."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animstudio  # noqa: E402
import mmd  # noqa: E402
import numpy as np  # noqa: E402
from tools.models import babies  # noqa: E402


@unittest.skipUnless((ROOT / 'extracted/CHDAT/MMD0/KORO.MMD').exists(), 'needs the player extraction')
class PichimonClips(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        model, tim = babies.build_species(471, ROOT / 'extracted')
        cls.model = model
        cls.tmp = tempfile.TemporaryDirectory()
        (Path(cls.tmp.name) / '471.MMD').write_bytes(model)
        (Path(cls.tmp.name) / '471.TIM').write_bytes(tim)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def clip(self, slot):
        return animstudio.Model(f'{self.tmp.name}/471.MMD:471:{self.tmp.name}/471.TIM', slot)

    def test_speeds_are_native_and_ordered(self):
        speed = {s: abs(animstudio.metrics(self.clip(s))[0]) for s in (2, 3, 4)}
        self.assertTrue(15 <= speed[2] <= 31 and 10 <= speed[3] <= 20 and 35 <= speed[4] <= 52, speed)
        self.assertLess(speed[3], speed[2])
        self.assertLess(speed[2], speed[4])

    def test_the_body_is_planted_while_it_is_down(self):
        for slot in (2, 3, 4):
            _, res = animstudio.metrics(self.clip(slot))
            self.assertTrue(all(r[3] < 25 and r[4] < 45 for r in res), (slot, res))

    def test_the_mesh_never_sinks_under_the_floor(self):
        for slot in (0, 2, 3, 4):
            m = self.clip(slot)
            floor = float(m.verts[:, 1].max())
            for t in range(len(m.frames)):
                pose, _ = m.pose(t)
                pts = np.array([v for tri in animstudio.animsheet.world_tris(m.m, pose, m.skel) for v in tri[0]])
                self.assertGreaterEqual(floor - pts[:, 1].max(), -1.0, (slot, t))      # one unit: the body is placed in whole units

    def test_hops_are_modest_and_squash_is_soft(self):
        for slot in (2, 3, 4):
            frames = self.clip(slot).frames
            self.assertTrue(all(.8 <= f[1][1] / 4096 <= 1.1 for f in frames), slot)
            self.assertLess(max(-f[1][7] for f in frames) - 69, 40, slot)

    def test_every_other_program_is_koromons(self):
        record = babies.records()[471]
        parsed = mmd.MMD.parse(self.model, record['bones'])
        donor = mmd.MMD.load(str(ROOT / 'extracted/CHDAT' / record['donor_model']), record['donor'])
        self.assertEqual(len(parsed.anims.table), len(donor.anims.table))
        for slot, (a, b) in enumerate(zip(parsed.anims.table, donor.anims.table)):
            self.assertEqual(a is None, b is None)
            if a is not None and slot not in (0, 2, 3, 4):
                self.assertEqual(vars(parsed.anims.anims[a]), vars(donor.anims.anims[b]), slot)

    def test_the_eyes_shut_in_a_blink(self):
        import animsheet
        m = mmd.MMD.parse(self.model, 7)
        for slot, blinks in ((0, 3), (2, 1), (3, 2), (4, 0)):
            shut = [e for e in animsheet.slot_frames(m, 7, slot)[2] if e[1] == 'tex' and e[2]['src'] == (54, 0)]
            self.assertEqual(len(shut), blinks, slot)

    def test_the_little_arms_have_their_own_bones_and_swing_from_the_shoulder(self):
        m = mmd.MMD.parse(self.model, 7)
        exe = mmd.exe()
        exe.skeleton[471] = exe.skeleton[babies.records()[471]['donor']]
        exe.bone_count[471] = 7
        m.type = 471
        t = m.tmd
        self.assertEqual([len(t.objects[i].prims) for i in (2, 4)], [6, 6])
        self.assertEqual(sum(1 for p in t.objects[0].prims if all(u >= 176 and 32 <= v < 64 for u, v in p.decode()['uv'])), 0)
        import animsheet

        def body_frame(f, obj, bone):
            mats = [np.vstack([np.array(M, float)[:3], [0, 0, 0, 1]]) for M in mmd.bone_matrices(m, f)]
            v = np.array([c[:3] + (1,) for c in t.obj_verts(obj)], float)
            return v @ (np.linalg.inv(mats[1]) @ mats[bone])[:3].T

        for slot, swing in ((0, 3), (2, 6), (3, 2), (4, 5)):
            frames = animsheet.slot_frames(m, 7, slot)[0]
            for obj, bone in ((2, 4), (4, 6)):
                shape = [body_frame(f, obj, bone) for f in frames]
                root = np.argmin(np.abs(shape[0][:, 0]))                    # the vertex at the shoulder
                centre = np.array([s_.mean(axis=0) for s_ in shape])
                shoulder = np.array([s_[root] for s_ in shape])
                self.assertGreater(np.ptp(centre, axis=0).max(), swing, (slot, obj))
                self.assertLess(np.ptp(shoulder, axis=0).max(), 14, (slot, obj))

if __name__ == '__main__':
    unittest.main()
