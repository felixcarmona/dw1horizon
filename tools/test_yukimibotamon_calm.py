"""Yukimibotamon's (472) four calm field clips: native speeds in order, a planted body, the mesh never under the floor."""
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


@unittest.skipUnless((ROOT / 'extracted/CHDAT/MMD0/BOTA.MMD').exists(), 'needs the player extraction')
class YukimibotamonClips(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        model, tim = babies.build_species(472, ROOT / 'extracted')
        cls.model = model
        cls.tim = tim
        cls.tmp = tempfile.TemporaryDirectory()
        (Path(cls.tmp.name) / '472.MMD').write_bytes(model)
        (Path(cls.tmp.name) / '472.TIM').write_bytes(tim)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def clip(self, slot):
        return animstudio.Model(f'{self.tmp.name}/472.MMD:1:{self.tmp.name}/472.TIM', slot)

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
                self.assertGreaterEqual(floor - pts[:, 1].max(), -1.0, (slot, t))

    def test_hops_are_modest_and_squash_is_soft(self):
        for slot in (2, 3, 4):
            frames = self.clip(slot).frames
            self.assertTrue(all(.8 <= f[2][1] / 4096 <= 1.1 for f in frames), slot)

    def test_an_open_mouth_replaces_the_closed_one(self):
        # the mouth window is copied whole, so each open frame must be ONE shape: no lobe of the closed omega mouth left
        # in it (that read as two mouths), and the frame must not touch the window's two outer columns
        tim = mmd.Tim4(self.tim)
        idx = np.frombuffer(bytes(tim.idx), np.uint8).reshape(tim.h, tim.w)

        def shapes(x):
            f = idx[16:32, x:x + 24]
            ink = f != f[0, 0]
            seen, n = np.zeros_like(ink), 0
            for y, xx in zip(*np.nonzero(ink)):
                if seen[y, xx]:
                    continue
                n += 1
                todo = [(y, xx)]
                while todo:
                    a, b = todo.pop()
                    if 0 <= a < 16 and 0 <= b < 24 and ink[a, b] and not seen[a, b]:
                        seen[a, b] = True
                        todo += [(a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1), (a + 1, b + 1), (a - 1, b - 1), (a + 1, b - 1), (a - 1, b + 1)]
            return n, ink
        closed_n, closed_ink = shapes(48)
        self.assertTrue(closed_ink[:, :2].any() and closed_ink[:, -2:].any())     # the omega reaches both sides
        for x in (72, 96, 120):                                                  # small, mid, wide
            n, ink = shapes(x)
            self.assertEqual(n, 1, x)
            self.assertFalse(ink[:, :2].any() or ink[:, -2:].any(), x)

    def test_every_other_program_is_koromons(self):
        record = babies.records()[472]
        parsed = mmd.MMD.parse(self.model, record['bones'])
        donor = mmd.MMD.load(str(ROOT / 'extracted/CHDAT' / record['donor_model']), record['donor'])
        self.assertEqual(len(parsed.anims.table), len(donor.anims.table))
        for slot, (a, b) in enumerate(zip(parsed.anims.table, donor.anims.table)):
            self.assertEqual(a is None, b is None)
            if a is not None and slot not in (0, 2, 3, 4):
                self.assertEqual(vars(parsed.anims.anims[a]), vars(donor.anims.anims[b]), slot)


if __name__ == '__main__':
    unittest.main()
