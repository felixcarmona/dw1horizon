"""MarineAngemon's idle, walk, condition walk and run: four different loops with flapping wings, swinging arms, swaying
ears and a blink; seamless, hovering above the ground, smooth from tick to tick. Needs the field model (see
field_animations/marine_angemon.py):

    python3 tools/models/edit.py get 248 DIR     and MARINEANGEMON_MODEL=DIR/248-MarineAngemon.MMD

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
from tools.models.field_animations import marine_angemon as gait
from tools.models.field_animations import marine_angemon_face as face

SOURCE = Path(os.environ.get('MARINEANGEMON_MODEL', 'build/imported-model-edit/edit/248-MarineAngemon.MMD'))
TEXTURE = SOURCE.with_suffix('.TIM')
NB = 26
SLOTS = (0, 2, 3, 4)
CLIPS = {0: (48, 0), 2: (24, 18), 3: (28, 13), 4: (18, 38)}      # ticks, units a tick
MOVING = {'wings': (16, 17, 18, 19), 'arms': (4, 5, 6, 7, 8, 9), 'ears': (10, 11, 12, 13, 14, 15), 'tail': (20, 21, 22, 23, 24)}


class MarineAngemonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.exists():
            raise unittest.SkipTest('needs the MarineAngemon field model (tools/models/edit.py get 248)')
        data = SOURCE.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.skeleton = [tuple(b) for b in json.loads(Path('content/species/248-marineangemon.json').read_text())['model']['skeleton']]
        cls.proof = cls.tex = None
        if digest == gait.SOURCE:
            data, cls.tex, cls.proof = gait.build(data, TEXTURE.read_bytes())
        mmd.exe().skeleton[248] = cls.skeleton
        mmd.exe().bone_count[248] = NB
        cls.model = mmd.MMD.parse(data, NB)
        cls.model.type = 248
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

    def test_wings_arms_ears_and_tail_move_in_every_clip(self):
        # every group turns over a loop by a visible angle (1/4096 of a turn): the previous clips held all of them still
        least = {'wings': 150, 'arms': 60, 'ears': 80, 'tail': 80}
        for slot in SLOTS:
            angles = np.array([[b[3:6] for b in f[1:]] for f in self.clips[slot]])
            for group, bones in MOVING.items():
                span = max(np.ptp(angles[:, b - 1, :], axis=0).max() for b in bones)
                self.assertGreater(span, least[group], (slot, group, span))

    def test_hovering_above_the_ground(self):
        for slot in SLOTS:
            low = max(self.vertices(slot, t)[:, 1].max() for t in range(len(self.clips[slot]) - 1))
            self.assertLessEqual(low, -40, (slot, low))       # y is down: the rest model's lowest point is about -90
            high = min(self.vertices(slot, t)[:, 1].min() for t in range(len(self.clips[slot]) - 1))
            self.assertGreater(high, -520, (slot, high))

    def test_clips_change_smoothly(self):
        limits = {0: 90, 2: 160, 3: 100, 4: 200}      # the most any vertex moves in one tick, in units
        for slot in SLOTS:
            v = [self.vertices(slot, t) for t in range(len(self.clips[slot]))]
            step = max(np.linalg.norm(b - a, axis=1).max() for a, b in zip(v, v[1:]))
            self.assertLessEqual(step, limits[slot] + CLIPS[slot][1], (slot, step))
            angles = np.array([[b[3:6] for b in f[1:]] for f in self.clips[slot]])
            self.assertLess(np.abs(np.diff(angles, axis=0)).max(), 700, slot)

    def test_the_four_clips_look_different(self):
        poses = {s: np.array([self.vertices(s, t) for t in range(CLIPS[s][0])]) for s in SLOTS}
        for a, b in itertools.combinations(SLOTS, 2):
            mean = np.sqrt(((poses[a].mean(0) - poses[b].mean(0)) ** 2).sum(-1).mean())
            self.assertGreater(mean, 5, (a, b, 'average pose'))
            n = 48
            ia = [int(i * len(poses[a]) / n) for i in range(n)]
            ib = [int(i * len(poses[b]) / n) for i in range(n)]
            phase = np.sqrt(((poses[a][ia] - poses[b][ib]) ** 2).sum(-1).mean())
            self.assertGreater(phase, 15, (a, b, 'phase by phase'))

    def test_the_tired_walk_is_lower_and_slower_than_the_walk(self):
        height = {s: np.mean([self.vertices(s, t)[:, 1].min() for t in range(CLIPS[s][0])]) for s in SLOTS}
        self.assertGreater(height[3], height[2] + 5)       # y is down: a larger top is a lower body
        self.assertGreater(CLIPS[3][0], CLIPS[2][0])
        self.assertLess(CLIPS[3][1], CLIPS[2][1])
        self.assertLess(CLIPS[2][1], CLIPS[4][1])

    def eye_state(self, slot, tick):
        """The eye frame showing at `tick` of a clip: the last texture move up to it (its source says which)."""
        moves = [e[2] for e in self.events[slot] if e[1] == 'tex' and e[0] <= tick]
        return face.FRAMES.index((moves[-1]['src'][0] * 4, moves[-1]['src'][1]))

    def test_every_clip_sets_its_eye_first_and_ends_with_it(self):
        for slot in SLOTS:
            tex = [e for e in self.events[slot] if e[1] == 'tex']
            self.assertEqual(tex[0][0], 0, slot)
            for e in tex:
                move = e[2]
                self.assertEqual((move['size'], move['dst']), ((face.PLATE_SIZE[0] // 4, face.PLATE_SIZE[1]), (face.PLATE_AT[0] // 4, face.PLATE_AT[1])), slot)
                self.assertIn((move['src'][0] * 4, move['src'][1]), face.FRAMES, slot)
            self.assertEqual(tex[-1][2]['src'], tex[0][2]['src'], slot)      # the last face is the first: the loop closes
            self.assertEqual(self.eye_state(slot, CLIPS[slot][0]), face.OPEN, slot)

    def test_the_eyes_blink_and_the_tired_ones_droop(self):
        states = {s: {self.eye_state(s, t) for t in range(CLIPS[s][0])} for s in SLOTS}
        for s in (0, 2, 3):
            self.assertEqual(states[s], {face.OPEN, face.HALF, face.SHUT}, s)
        self.assertIn(face.HALF, states[4])
        shut = lambda s: sum(self.eye_state(s, t) == face.SHUT for t in range(CLIPS[s][0]))
        self.assertGreater(shut(3), shut(2))

    def test_the_texture_only_gains_the_three_eye_frames(self):
        if self.tex is None:
            self.skipTest('the stored model is not regenerated')
        old, new = mmd.Tim4(TEXTURE.read_bytes()), mmd.Tim4(self.tex)
        self.assertEqual(old.pal, new.pal)
        self.assertEqual(len(old.idx), len(new.idx))
        w, h = face.PLATE_SIZE
        spare = [set((x0 + x, y0 + y) for y in range(h) for x in range(w)) for x0, y0 in face.FRAMES[1:]]
        spare = set().union(*spare)
        changed = {(i % 256, i // 256) for i in range(len(old.idx)) if old.idx[i] != new.idx[i]}
        self.assertLessEqual(changed, spare | {(face.FRAMES[0][0] + x, face.FRAMES[0][1] + y) for y in range(h) for x in range(w)})
        at = face.FRAMES[0]
        plate = [[new.idx[(at[1] + y) * 256 + at[0] + x] for x in range(w)] for y in range(h)]
        painted = [[old.idx[(face.PLATE_AT[1] + y) * 256 + face.PLATE_AT[0] + x] for x in range(w)] for y in range(h)]
        self.assertEqual(plate, painted, 'the open frame is the painted eye')
        for state in (face.HALF, face.SHUT):
            at = face.FRAMES[state]
            frame = [[new.idx[(at[1] + y) * 256 + at[0] + x] for x in range(w)] for y in range(h)]
            self.assertNotEqual(frame, painted)


if __name__ == '__main__':
    unittest.main()
