"""Nyokimon's (473) four calm field clips: native speeds in order, a planted body, the mesh never under the floor."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet  # noqa: E402
import animstudio  # noqa: E402
import mmd  # noqa: E402
import numpy as np  # noqa: E402
from tools.models import babies  # noqa: E402


@unittest.skipUnless((ROOT / 'extracted/CHDAT/MMD0/BOTA.MMD').exists(), 'needs the player extraction')
class NyokimonClips(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        model, tim = babies.build_species(473, ROOT / 'extracted')
        cls.model = model
        cls.tim = tim
        cls.tmp = tempfile.TemporaryDirectory()
        (Path(cls.tmp.name) / '473.MMD').write_bytes(model)
        (Path(cls.tmp.name) / '473.TIM').write_bytes(tim)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def clip(self, slot):
        return animstudio.Model(f'{self.tmp.name}/473.MMD:1:{self.tmp.name}/473.TIM', slot)

    def test_speeds_are_native_and_ordered(self):
        speed = {s: abs(animstudio.metrics(self.clip(s))[0]) for s in (2, 3, 4)}
        self.assertTrue(15 <= speed[2] <= 31 and 10 <= speed[3] <= 20 and 35 <= speed[4] <= 52, speed)
        self.assertLess(speed[3], speed[2])
        self.assertLess(speed[2], speed[4])

    def test_the_body_is_planted_while_it_is_down(self):
        # the studio's slip metric follows a fixed bone on this rig, so measure the lowest points of the mesh themselves
        for slot in (2, 3, 4):
            m = self.clip(slot)
            floor = float(m.verts[:, 1].max())
            rows = []
            for t in range(len(m.frames)):
                pose, root = m.pose(t)
                pts = np.array([v for tri in animstudio.animsheet.world_tris(m.m, pose, m.skel) for v in tri[0]])
                y = pts[:, 1].max()
                rows.append((floor - (y + root[1]), pts[pts[:, 1] > y - 3][:, 2].mean() + root[2]))
            speed = abs((m.pose(len(m.frames) - 1)[1][2] - m.pose(0)[1][2]) / (len(m.frames) - 1))
            slip = [abs(rows[t + 1][1] - rows[t][1]) / speed * 100 for t in range(len(rows) - 1)
                    if abs(rows[t][0]) < .6 and abs(rows[t + 1][0]) < .6]
            self.assertTrue(slip, slot)
            self.assertLess(sum(slip) / len(slip), 12, slot)
            self.assertLess(max(slip), 25, slot)

    def test_it_blinks_with_half_lids(self):
        record = babies.records()[473]
        parsed = mmd.MMD.parse(self.model, record['bones'])
        want = {0: 2, 2: 1, 3: 1}                                  # blinks in the idle, walk and tired clips
        for slot, blinks in want.items():
            events = animsheet.slot_frames(parsed, record['bones'], slot)[2]
            eyes = [(e[0], e[2]['src']) for e in events if e[1] == 'tex' and e[2]['dst'] == (2, 8)]
            for i, (tick, src) in enumerate(eyes):
                if src == (24, 0):                                                  # the closed eye: lid before, lid after
                    self.assertEqual(eyes[i - 1][1], (30, 0), slot)
                    self.assertEqual(eyes[i + 1][1], (30, 0), slot)
                    self.assertGreaterEqual(eyes[i + 1][0] - tick, 2, slot)         # closed for two ticks or more
            self.assertEqual(sum(1 for _, src in eyes if src == (24, 0)), blinks, slot)

    def test_an_open_mouth_replaces_the_closed_one(self):
        # every mouth frame is the whole window: the grey lip line of the closed mouth is in no open/happy/down frame
        tim = mmd.Tim4(self.tim)
        pal = [mmd.c15_to_rgba(c)[:3] for c in tim.pal[0]]
        light = [i for i, c in enumerate(pal) if sum(c) > 450 and abs(c[0] - c[2]) < 40]       # the grey of the line
        def grey(x, y):
            return sum(1 for r in range(y, y + 16) for c in range(x, x + 24) if tim.idx[r * tim.w + c] in light)
        self.assertGreater(grey(48, 16), 4)                         # the closed frame has the line
        for x in (72, 96, 120):                                      # down, open, happy
            self.assertEqual(grey(x, 16), 0, x)

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
            self.assertTrue(all(.8 <= f[2][1] / 4096 <= 1.1 for f in frames), slot)

    def test_every_other_program_is_koromons(self):
        record = babies.records()[473]
        parsed = mmd.MMD.parse(self.model, record['bones'])
        donor = mmd.MMD.load(str(ROOT / 'extracted/CHDAT' / record['donor_model']), record['donor'])
        self.assertEqual(len(parsed.anims.table), len(donor.anims.table))
        for slot, (a, b) in enumerate(zip(parsed.anims.table, donor.anims.table)):
            self.assertEqual(a is None, b is None)
            if a is not None and slot not in (0, 2, 3, 4):
                self.assertEqual(vars(parsed.anims.anims[a]), vars(donor.anims.anims[b]), slot)


if __name__ == '__main__':
    unittest.main()
