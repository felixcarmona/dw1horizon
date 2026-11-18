"""Pabumon's (470) four calm field clips: native speeds in order, a planted body, the mesh never under the floor."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animstudio  # noqa: E402
import numpy as np  # noqa: E402
from tools.models import babies  # noqa: E402


@unittest.skipUnless((ROOT / 'extracted/CHDAT/MMD0/PUNI.MMD').exists(), 'needs the player extraction')
class PabumonClips(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        model, tim = babies.build_species(470, ROOT / 'extracted')
        cls.tmp = tempfile.TemporaryDirectory()
        (Path(cls.tmp.name) / '470.MMD').write_bytes(model)
        (Path(cls.tmp.name) / '470.TIM').write_bytes(tim)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def clip(self, slot):
        return animstudio.Model(f'{self.tmp.name}/470.MMD:470:{self.tmp.name}/470.TIM', slot)

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
                self.assertGreaterEqual(floor - pts[:, 1].max(), -0.5, (slot, t))

    def test_hops_are_modest_and_squash_is_soft(self):
        for slot in (2, 3, 4):
            frames = self.clip(slot).frames
            self.assertTrue(all(.7 <= f[1][1] / 4096 <= 1.3 for f in frames), slot)
            self.assertLess(max(-f[1][7] for f in frames) - 45, 55, slot)

    def test_the_eyes_blink_long_enough_to_see(self):
        shut = {'src': (28, 0)}                               # the closed-eye frame (x = 112 px, in units of four)
        for slot in (0, 2, 3):
            events = [e for e in animstudio.animsheet.slot_frames(self.clip(slot).m, 3, slot)[2] if e[1] == 'tex']
            closed = [k for k, _, c in events if c['src'] == shut['src']]
            self.assertGreaterEqual(len(closed), 1, slot)
            reopen = min(k for k, _, c in events if k > closed[0] and c['src'] != shut['src'])
            self.assertGreaterEqual(reopen - closed[0], 3, slot)


if __name__ == '__main__':
    unittest.main()
