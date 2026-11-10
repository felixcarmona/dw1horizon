"""Rosemon's walk, condition walk and run: one step beat for every channel."""
import cmath
import json
import math
import os
from pathlib import Path
import unittest
import mmd
import animsheet
from tools.models.field_animations import rosemon_gait as G


class Footfall(unittest.TestCase):
    def test_support_foot_moves_with_the_ground_and_swing_closes_the_loop(self):
        for slot, g in ((s, g) for s, g in G.GAIT.items() if not g.get('still')):
            gait = G.Gait(g, 14.0, 20.0)
            step = 1 / 14.0
            for i in range(1, 100):
                phase = i / 100 * g['duty'] - step
                if phase < 0 or phase + step >= g['duty']:
                    continue
                a, b = gait.at(phase), gait.at(phase + step)
                self.assertAlmostEqual(b[0] - a[0], 20.0, 6, slot)
                self.assertEqual((a[1], b[1]), (0.0, 0.0))
            start, end = gait.at(0.0), gait.at(1.0 - 1e-9)
            self.assertAlmostEqual(start[0], end[0], 3, slot)
            self.assertAlmostEqual(end[1], 0.0, 2, slot)
            self.assertGreater(max(gait.at(g['duty'] + (1 - g['duty']) * i / 50)[1] for i in range(51)), g['lift'] * 0.95)


class Clips(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p = Path(os.environ.get('ROSEMON_PACED', 'build/rosemon-paced/230.MMD'))
        if not p.exists():
            raise unittest.SkipTest('needs the paced Rosemon model (ROSEMON_PACED)')
        cls.sk = json.loads(Path('content/species/230-rosemon.json').read_text())['model']['skeleton']
        cls.data = p.read_bytes()
        cls.out, cls.report = G.build(cls.data, cls.sk)
        mmd.exe().skeleton[230] = cls.sk
        mmd.exe().bone_count[230] = len(cls.sk)
        cls.old = mmd.MMD.parse(cls.data, G.NB); cls.old.type = 230
        cls.new = mmd.MMD.parse(cls.out, G.NB); cls.new.type = 230

    def test_only_the_three_slots_change_and_storage_fits(self):
        self.assertEqual(self.report['changed_slots'], list(G.SLOTS))
        self.assertTrue(self.report['storage']['fits'])
        self.assertLessEqual(self.report['storage']['resident_bytes'], 100352)

    def test_every_channel_holds_whole_cycles_and_closes(self):
        for slot in G.SLOTS:
            frames, loop, _ = animsheet.slot_frames(self.new, G.NB, slot)
            n = len(frames) - 1
            cycles = G.GAIT[slot]['cycles']
            for bone in range(1, G.NB):
                self.assertEqual(frames[0][bone][3:6], frames[-1][bone][3:6], (slot, bone))
                for c in (3, 4, 5):
                    xs = [frames[t][bone][c] for t in range(n)]
                    mean = sum(xs) / n
                    energy = [abs(sum((x - mean) * cmath.exp(-2j * math.pi * k * t / n) for t, x in enumerate(xs))) ** 2 for k in range(1, n // 2)]
                    total = sum(energy)
                    if max(xs) - min(xs) < 6 * G.TOLERANCE["body"]:   # smaller swings are inside the key-reduction tolerance
                        continue
                    whole = sum(e for k, e in zip(range(1, n // 2), energy) if k % cycles == 0)
                    self.assertGreater(whole / total, 0.8, (slot, bone, c))

    def _world(self, frame):
        pose = [list(x) for x in frame]
        pose[0] = [4096] * 3 + [0] * 6
        return mmd.bone_matrices(self.new, pose)

    def test_idle_is_upright_not_leaning_back(self):
        frames = animsheet.slot_frames(self.new, G.NB, 0)[0]
        for frame in frames:
            w = self._world(frame)
            head = [w[2][i][3] - w[17][i][3] for i in range(3)]
            lean = math.degrees(math.atan2(-head[2], -head[1]))     # positive: the head is in front of the pelvis
            self.assertGreater(lean, -4.0)
            self.assertLess(lean, 8.0)
        old = animsheet.slot_frames(self.old, G.NB, 0)[0][0]
        w = self._world(old)
        head = [w[2][i][3] - w[17][i][3] for i in range(3)]
        self.assertLess(math.degrees(math.atan2(-head[2], -head[1])), -10.0)      # the clip it replaces leaned back

    def test_forearms_keep_daylight_from_the_body(self):
        mesh = {b: [list(v)[:3] for v in self.new.tmd.obj_verts(o)][::3] for b, (o, _) in enumerate(self.sk) if o >= 0}
        for slot, least in ((0, 12.0), (2, 14.0), (3, 10.0), (4, 14.0)):
            frames = animsheet.slot_frames(self.new, G.NB, slot)[0][:-1]
            for frame in frames[::6]:
                w = self._world(frame)
                def points(bones):
                    out = []
                    for b in bones:
                        m = w[b]
                        out += [[sum(m[i][j] * v[j] for j in range(3)) + m[i][3] for i in range(3)] for v in mesh[b]]
                    return out
                body = points((1, 17, 18, 19, 20, 21, 22, 23))
                for arm in ((12, 13), (15, 16)):
                    gap = min(math.dist(a, b) for a in points(arm) for b in body)
                    self.assertGreater(gap, least, (slot, arm))

    def _harmonic(self, frames, bone, cycles):
        n = len(frames) - 1
        xs = [frames[t][bone][3] for t in range(n)]
        mean = sum(xs) / n
        h = sum((x - mean) * cmath.exp(-2j * math.pi * cycles * t / n) for t, x in enumerate(xs))
        return cmath.phase(h) / (2 * math.pi), abs(h) * 2 / n * 360 / 4096

    def test_walk_arms_trail_and_differ_between_sides(self):
        frames = animsheet.slot_frames(self.new, G.NB, 2)[0]
        right = [self._harmonic(frames, b, 4) for b in (11, 12, 13)]
        left = [self._harmonic(frames, b, 4) for b in (14, 15, 16)]
        elbow = (right[0][0] - right[1][0]) % 1.0
        wrist = (right[1][0] - right[2][0]) % 1.0
        self.assertTrue(0.08 < elbow < 0.2, elbow)               # about an eighth of a cycle behind the shoulder
        self.assertTrue(0.08 < wrist < 0.25, wrist)              # the wrist trails the elbow
        self.assertGreater(right[1][1], 5.0)
        self.assertGreater(right[2][1], 5.0)
        self.assertTrue(0.05 < 1 - left[0][1] / right[0][1] < 0.2)      # the left arm swings a little less
        for b in (11, 12, 13, 14, 15, 16):
            ticks = [mmd.rot_matrix(*frames[t][b][3:6]) for t in range(len(frames))]
            steps = [math.degrees(math.acos(max(-1, min(1, (sum(a[i][j] * c[i][j] for i in range(3) for j in range(3)) - 1) / 2))))
                     for a, c in zip(ticks, ticks[1:])]
            self.assertLess(max(steps), 14.0, b)

    def test_run_is_a_light_jog(self):
        frames = animsheet.slot_frames(self.new, G.NB, 4)[0][:-1]
        verts = {b: [list(v)[:3] for v in self.new.tmd.obj_verts(o)][::2] for b, (o, _) in enumerate(self.sk) if o >= 0 and b in (20, 23)}
        air, height, knees = 0, [], []
        for frame in frames:
            w = self._world(frame)
            height.append(w[17][1][3])
            for hip, knee, ankle in ((18, 19, 20), (21, 22, 23)):
                u = [w[knee][i][3] - w[hip][i][3] for i in range(3)]
                v = [w[ankle][i][3] - w[knee][i][3] for i in range(3)]
                bend = math.degrees(math.acos(sum(a * b for a, b in zip(u, v)) / math.hypot(*u) / math.hypot(*v)))
                knees.append(bend)
            low = [max(sum(w[b][1][j] * v[j] for j in range(3)) + w[b][1][3] for v in verts[b]) for b in (20, 23)]
            air += all(l < -3.0 - 6.0 for l in low)
        self.assertTrue(0.15 * len(frames) < air < 0.35 * len(frames), air)   # a short flight phase, not a bound
        self.assertTrue(8.0 < max(height) - min(height) < 20.0)              # the pelvis bobs a little
        self.assertLess(max(knees), 105.0)       # the swing knee folds far less than a native run's (about 135 degrees)
        self.assertLess(min(knees), 28.0)        # and the leg is nearly straight at the top of its stride


if __name__ == '__main__':
    unittest.main()
