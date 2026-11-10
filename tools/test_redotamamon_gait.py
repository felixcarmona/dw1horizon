"""RedOtamamon's idle, walk, condition walk and run: four clearly different loops, seamless, claws planted, nothing under the
ground, smooth from tick to tick. Needs the field model (see field_animations/redotamamon.py):

    python3 tools/models/edit.py get 233 DIR     and REDOTAMAMON_MODEL=DIR/233-RedOtamamon.MMD

The file may be the stored model or the one before the clips (then the generator makes them)."""
import hashlib
import itertools
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import animsheet
import mmd
from tools.models.field_animations import redotamamon as gait
from tools.models.field_animations import redotamamon_face as face

SOURCE = Path(os.environ.get('REDOTAMAMON_MODEL', 'build/imported-model-edit/edit/233-RedOtamamon.MMD'))
TEXTURE = SOURCE.with_suffix('.TIM')
NB = 14
SLOTS = (0, 2, 3, 4)
CLIPS = {0: (96, 0), 2: (16, 20), 3: (22, 13), 4: (10, 38)}      # ticks, units a tick
STANCE = {2: 5, 3: 7, 4: 2.8}


class RedOtamamonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.exists():
            raise unittest.SkipTest('needs the RedOtamamon field model (tools/models/edit.py get 233)')
        data = SOURCE.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.skeleton = [tuple(b) for b in json.loads(Path('content/species/233-redotamamon.json').read_text())['model']['skeleton']]
        cls.proof = cls.tex = None
        if digest == gait.SOURCE:
            data, cls.tex, cls.proof = gait.build(data, TEXTURE.read_bytes())
        mmd.exe().skeleton[233] = cls.skeleton
        mmd.exe().bone_count[233] = NB
        cls.model = mmd.MMD.parse(data, NB)
        cls.model.type = 233
        cls.clips = {s: animsheet.slot_frames(cls.model, NB, s)[0] for s in SLOTS}
        cls.events = {s: animsheet.slot_frames(cls.model, NB, s)[2] for s in SLOTS}

    def local(self, slot, tick):
        f = self.clips[slot][tick]
        return [[4096] * 3 + [0] * 6] + [list(b) for b in f[1:]]

    def vertices(self, slot, tick):
        pose, out = self.local(slot, tick), []
        mats = mmd.bone_matrices(self.model, pose)
        for b, (obj, _) in enumerate(self.skeleton):
            if obj >= 0:
                m = np.array(mats[b])
                out.append(np.array(self.model.tmd.obj_verts(obj), float)[:, :3] @ m[:3, :3].T + m[:3, 3])
        return np.concatenate(out)

    def claw_tip(self, slot, tick, name):
        """The claw's lowest vertex in the world (travel included): where it touches the ground."""
        cl = gait.ARMS[name][1]
        m = np.array(mmd.bone_matrices(self.model, self.local(slot, tick))[cl])
        v = np.array(self.model.tmd.obj_verts(self.skeleton[cl][0]), float)[:, :3] @ m[:3, :3].T + m[:3, 3]
        tip = v[v[:, 1].argmax()].copy()
        tip[2] += self.clips[slot][tick][0][8]
        return tip

    def test_loops_keep_their_length_and_speed(self):
        for slot, (ticks, speed) in CLIPS.items():
            f = self.clips[slot]
            self.assertEqual(len(f) - 1, ticks, slot)
            self.assertEqual(f[0][1:], f[-1][1:], slot)
            self.assertAlmostEqual((f[0][0][8] - f[-1][0][8]) / ticks, speed, delta=0.01, msg=slot)
            if speed:
                steps = {round(f[i][0][8] - f[i + 1][0][8], 3) for i in range(ticks)}
                self.assertEqual(steps, {float(speed)})

    def test_only_the_field_slots_change(self):
        if self.proof is None:
            self.skipTest('the stored model is not regenerated')
        self.assertTrue(set(self.proof['changed_slots']) >= set(SLOTS))
        self.assertTrue(self.proof['storage']['fits'])
        self.assertLessEqual(self.proof['storage']['resident_bytes'], 100352)
        self.assertEqual(max(self.proof['unreached'].values()), 0)

    def test_planted_claws_do_not_slide(self):
        for slot, stance in STANCE.items():
            ticks, speed = CLIPS[slot]
            for name in gait.ARMS:
                tips = np.array([self.claw_tip(slot, t, name) for t in range(ticks)])
                # a planted claw lies on the floor and keeps its place in the world while the body passes over it
                still = [abs(tips[(i + 1) % ticks][2] - tips[i][2]) < 1.5 and min(tips[i][1], tips[(i + 1) % ticks][1]) > gait.FLOOR - 12
                         for i in range(ticks)]
                self.assertGreaterEqual(sum(still), int(stance) - 2, (slot, name, sum(still)))

    def test_nothing_sinks_under_the_ground(self):
        for slot in SLOTS:
            low = max(self.vertices(slot, t)[:, 1].max() for t in range(len(self.clips[slot]) - 1))
            self.assertLessEqual(low, gait.FLOOR + 3, (slot, low))

    def test_clips_change_smoothly(self):
        limits = {0: 20, 2: 60, 3: 30, 4: 90}      # the most any vertex moves in one tick, in units
        for slot in SLOTS:
            v = [self.vertices(slot, t) for t in range(len(self.clips[slot]))]
            step = max(np.linalg.norm(b - a, axis=1).max() for a, b in zip(v, v[1:]))
            self.assertLessEqual(step, limits[slot], (slot, step))
            accel = max(np.linalg.norm(c - 2 * b + a, axis=1).max() for a, b, c in zip(v, v[1:], v[2:]))
            self.assertLessEqual(accel, 100, (slot, accel))
            # no joint may jump across an angle branch (that would spin it through the loop)
            angles = np.array([[b[3:6] for b in f[1:]] for f in self.clips[slot]])
            self.assertLess(np.abs(np.diff(angles, axis=0)).max(), 600, slot)

    def test_the_four_clips_look_different(self):
        poses = {}
        for slot in SLOTS:
            ticks = CLIPS[slot][0]
            poses[slot] = np.array([self.vertices(slot, t) for t in range(ticks)])
        for a, b in itertools.combinations(SLOTS, 2):
            mean = np.sqrt(((poses[a].mean(0) - poses[b].mean(0)) ** 2).sum(-1).mean())
            self.assertGreater(mean, 10, (a, b, 'average pose'))
            # phase by phase over one loop of each (the shorter loop is stretched over the longer one's)
            n = 48
            ia = [int(i * len(poses[a]) / n) for i in range(n)]
            ib = [int(i * len(poses[b]) / n) for i in range(n)]
            phase = np.sqrt(((poses[a][ia] - poses[b][ib]) ** 2).sum(-1).mean())
            self.assertGreater(phase, 15, (a, b, 'phase by phase'))

    def test_the_tired_walk_is_lower_and_slower_than_the_walk(self):
        height = {s: np.mean([self.vertices(s, t)[:, 1].min() for t in range(CLIPS[s][0])]) for s in SLOTS}
        # y is down: a larger (less negative) top is a lower body
        self.assertGreater(height[3], height[2] + 5)
        self.assertGreater(CLIPS[3][0], CLIPS[2][0])
        self.assertLess(CLIPS[3][1], CLIPS[2][1] < CLIPS[4][1] and CLIPS[2][1])

    def eye_state(self, slot, tick):
        """The eye frame showing at `tick` of a clip: the last texture move up to it (its source column says which)."""
        moves = [e[2] for e in self.events[slot] if e[1] == 'tex' and e[0] <= tick]
        return face.FRAMES.index((moves[-1]['src'][0] * 4, moves[-1]['src'][1]))

    def test_every_clip_sets_its_eye_first_and_ends_with_it(self):
        for slot in SLOTS:
            tex = [e for e in self.events[slot] if e[1] == 'tex']
            self.assertEqual(tex[0][0], 0, slot)
            for e in tex:
                move = e[2]
                self.assertEqual((move['size'], move['dst']), ((10, 40), (22, 32)), slot)       # the whole eye plate
                self.assertIn((move['src'][0] * 4, move['src'][1]), face.FRAMES, slot)
            self.assertEqual(tex[-1][2]['src'], tex[0][2]['src'], slot)      # the last face is the first: the loop closes

    def test_the_eyes_blink_and_the_tired_ones_droop(self):
        states = {s: {self.eye_state(s, t) for t in range(CLIPS[s][0])} for s in SLOTS}
        self.assertEqual(states[0], {face.OPEN, face.HALF, face.SHUT})
        self.assertEqual(states[2], {face.OPEN, face.HALF, face.SHUT})
        self.assertEqual(states[3], {face.OPEN, face.HALF, face.SHUT})
        self.assertIn(face.HALF, states[4])
        shut = sum(self.eye_state(3, t) == face.SHUT for t in range(CLIPS[3][0]))
        self.assertGreater(shut, sum(self.eye_state(2, t) == face.SHUT for t in range(CLIPS[2][0])))

    def test_the_texture_only_gains_the_three_eye_frames(self):
        if self.tex is None:
            self.skipTest('the stored model is not regenerated')
        old, new = mmd.Tim4(TEXTURE.read_bytes()), mmd.Tim4(self.tex)
        self.assertEqual(old.pal, new.pal)
        self.assertEqual(len(old.idx), len(new.idx))
        changed = {(i % 256, i // 256) for i in range(len(old.idx)) if old.idx[i] != new.idx[i]}
        left = {x for x, y in changed if x < 132}
        self.assertEqual(left, set(), 'the painted texture is untouched')
        for at in face.FRAMES[:1]:
            plate = [[new.idx[(at[1] + y) * 256 + at[0] + x] for x in range(40)] for y in range(40)]
            painted = [[old.idx[(32 + y) * 256 + 88 + x] for x in range(40)] for y in range(40)]
            self.assertEqual(plate, painted, 'the open frame is the painted eye')
        for state in (face.HALF, face.SHUT):       # a lid hides part of the eyeball and keeps its outline in the box
            at = face.FRAMES[state]
            frame = [[new.idx[(at[1] + y) * 256 + at[0] + x] for x in range(40)] for y in range(40)]
            painted = [[old.idx[(32 + y) * 256 + 88 + x] for x in range(40)] for y in range(40)]
            self.assertNotEqual(frame, painted)
            diff = {(x + 88, y + 32) for y in range(40) for x in range(40) if frame[y][x] != painted[y][x]}
            x0, y0, x1, y1 = face.EYE_BOX
            self.assertTrue(all(x0 <= x < x1 and y0 - 1 <= y < y1 for x, y in diff), 'only the eyeball changes')


if __name__ == '__main__':
    unittest.main()
