"""ShellNumemon's idle, walk, condition walk and run are four different, seamless crawl clips that keep the field speed.

Needs the final model (tools/models/edit.py get 231 writes it to build/imported-model-edit/edit)."""
import math
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / 'models'))
import animsheet
import mmd
from tools.models.field_animations import shell_numemon_gait as gen

MODEL = Path(os.environ.get('SHELLNUMEMON_MODEL', 'build/imported-model-edit/edit/231-ShellNumemon.MMD'))
SKELETON = [(i - 1, p) for i, p in enumerate(gen.PARENTS)]
DEG = 4096 / 360


class ShellNumemonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEL.exists() or not Path(mmd.EXTRACTED).exists():
            raise unittest.SkipTest('needs the final ShellNumemon model and the player DW1 extraction')
        mmd.exe().skeleton[231] = SKELETON
        mmd.exe().bone_count[231] = 16
        cls.model = mmd.MMD.parse(MODEL.read_bytes(), 16)
        cls.model.type = 231
        cls.clips = {s: animsheet.slot_frames(cls.model, 16, s)[0] for s in (0, 1, 2, 3, 4)}
        cls.verts = {b: cls.model.tmd.obj_verts(o) for b, (o, _) in enumerate(SKELETON) if o >= 0}

    def world_y_z(self, frame, bones):
        w = mmd.bone_matrices(self.model, frame)
        return [(w[b][1][0] * x + w[b][1][1] * y + w[b][1][2] * z + w[b][1][3],
                 w[b][2][0] * x + w[b][2][1] * y + w[b][2][2] * z + w[b][2][3])
                for b in bones for x, y, z, _ in self.verts[b]]

    def test_lengths_speeds_and_loops(self):
        for slot, ticks, speed in ((0, 104, 0), (2, 24, 19.25), (3, 32, 12.84), (4, 18, 35)):
            frames = self.clips[slot]
            self.assertEqual(len(frames) - 1, ticks)
            self.assertAlmostEqual(-(frames[-1][0][8] - frames[0][0][8]) / ticks, speed, delta=.1)
            steps = {frames[i + 1][0][8] - frames[i][0][8] for i in range(ticks)}
            self.assertLessEqual(max(steps) - min(steps), 1)
            for bone in range(1, 16):
                for channel in range(3, 9):
                    gap = abs(frames[-1][bone][channel] - frames[0][bone][channel]) % 4096
                    self.assertLessEqual(min(gap, 4096 - gap), 1, (slot, bone, channel))
                for a, b in zip(frames, frames[1:]):
                    turn = max(abs(x - y) for x, y in zip(a[bone][3:6], b[bone][3:6]))
                    self.assertLess(turn, 10 * DEG, (slot, bone))

    def test_scales_never_change(self):
        scales = [tuple(b[:3]) for b in self.clips[1][0]]
        for slot, frames in self.clips.items():
            for f in frames:
                self.assertEqual([tuple(b[:3]) for b in f], scales, slot)

    def test_the_four_clips_differ_and_the_head_and_eyes_move(self):
        poses = {s: [[tuple(b[3:6]) for b in f[1:]] for f in self.clips[s][:18]] for s in (0, 2, 3, 4)}
        slots = sorted(poses)
        for i, a in enumerate(slots):
            for b in slots[i + 1:]:
                gap = sum(abs(x - y) for pa, pb in zip(poses[a], poses[b]) for ra, rb in zip(pa, pb) for x, y in zip(ra, rb))
                self.assertGreater(gap, 3000, (a, b))
        for slot in (2, 3, 4):
            # the head rides on the body: its pitch in the world (the body turns, not the head on it)
            head = [math.degrees(math.atan2(-m[1][2], m[2][2])) for m in
                    (mmd.bone_matrices(self.model, f)[gen.HEAD] for f in self.clips[slot])]
            self.assertGreater(max(head) - min(head), 8, slot)
            for stalk in (10, 13):
                pitch = [f[stalk][3] for f in self.clips[slot]]
                self.assertGreater(max(pitch) - min(pitch), 4 * DEG, (slot, stalk))
        for stalk in (10, 13):
            look = [f[stalk][4] for f in self.clips[0]]
            self.assertGreater(max(look) - min(look), 15 * DEG, stalk)

    def test_the_belly_stays_on_the_floor_and_never_slides_back(self):
        for slot in (2, 3, 4):
            frames = self.clips[slot]
            belly = [self.world_y_z(f, gen.BELLY) for f in frames]
            floors = [max(y for y, _ in pts) for pts in belly]
            self.assertLess(max(floors) - min(floors), 3, slot)
            for t in range(len(frames) - 1):
                low = [i for i, (y, _) in enumerate(belly[t]) if y > floors[t] - 3]
                self.assertGreaterEqual(min(belly[t][i][1] - belly[t + 1][i][1] for i in low), 0, (slot, t))
            flaps = [max(y for y, _ in self.world_y_z(f, (5, 7))) for f in frames]
            self.assertLessEqual(max(f - g for f, g in zip(flaps, floors)), 1, slot)

    def test_the_mesh_stays_closed(self):
        # pieces that touch (within 10 units) in the rest pose may not part further than on the model before this
        # change: the head and the front of the foot share a ring of vertices that tears when the head turns on it
        world = lambda f: {b: [(m[0][0] * x + m[0][1] * y + m[0][2] * z + m[0][3],
                                m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3],
                                m[2][0] * x + m[2][1] * y + m[2][2] * z + m[2][3]) for x, y, z, _ in self.verts[b]]
                           for b, m in enumerate(mmd.bone_matrices(self.model, f)) if b in self.verts}
        rest = world(self.clips[0][0])
        pairs = {}
        for a in rest:
            for b in rest:
                if a < b:
                    near = [(i, j, math.dist(p, q)) for i, p in enumerate(rest[a]) for j, q in enumerate(rest[b])
                            if math.dist(p, q) < 10]
                    if near:
                        pairs[(a, b)] = near
        self.assertIn((3, 8), pairs)
        limit = {(2, 8): 5, (4, 5): 4.5}
        for slot in (0, 2, 3, 4):
            for f in self.clips[slot]:
                w = world(f)
                for (a, b), near in pairs.items():
                    opened = max(math.dist(w[a][i], w[b][j]) - d for i, j, d in near)
                    self.assertLess(opened, limit.get((a, b), 2.5), (slot, a, b))

    def test_the_mouth_opens_and_shuts_inside_each_clip(self):
        shut = gen.mouth.move(gen.mouth.REST)
        for slot in (0, 2, 3, 4):
            moves = [(e[0], e[2]) for e in animsheet.slot_frames(self.model, 16, slot)[2] if 'tex' in e[1]]
            self.assertEqual(moves[0][0], 0, slot)
            for t, c in (moves[0], moves[-1]):
                self.assertEqual((tuple(c['src']), tuple(c['size']), tuple(c['dst'])),
                                 (shut['src'], shut['size'], shut['dst']), slot)
            opened = gen.mouth.move(gen.mouth.OPEN)['src']
            self.assertIn(opened, [tuple(c['src']) for _, c in moves], slot)

    def test_only_those_four_programs_changed(self):
        other = [s for s in range(0, 40) if s not in (0, 2, 3, 4) and self.model.anims.table[s] in (
            self.model.anims.table[0], self.model.anims.table[2], self.model.anims.table[3], self.model.anims.table[4])]
        self.assertEqual(other, [])

    def test_generator_rejects_another_source(self):
        tex = MODEL.with_suffix('.TIM').read_bytes()
        with self.assertRaises(ValueError):
            gen.build(MODEL.read_bytes(), tex, SKELETON)


if __name__ == '__main__':
    unittest.main()
