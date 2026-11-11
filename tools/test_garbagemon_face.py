"""Check Garbagemon's face: eyes that blink and a mouth that opens, by texture moves in the four field clips.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 269`). Before the change it is
`garbagemon_face.SOURCE`: the generator is run on it and the result is checked; afterwards it is the result itself.
The texture is checked texel by texel, and the clips by replaying their texture moves tick by tick like the engine.
"""
import hashlib
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mmd
import motionstorage
from tools.models.field_animations import garbagemon_face as face

EXPECTED = 'd79cfceaf4dbe7464aa6fc33253291ce34ddcbbf7a66d350566acb91661f53b0'
EXPECTED_TIM = 'd3fee9e74072b8602447a52765bcfe01c47dfd6a80114c37a7095b0427eca3d6'
NB = face.NB
BUFFER = 100352
SLOTS = (0, 2, 3, 4)
EDIT = Path('build/imported-model-edit/edit')


def sampled_texels(model, pad=1):
    """Every texel some primitive of the model can sample (a triangle's texels, grown by `pad`)."""
    mask = np.zeros((128, 256), bool)
    for obj in model.tmd.objects:
        for prim in obj.prims:
            uv = prim.decode()['uv']
            if not uv:
                continue
            for tri in ([[uv[0], uv[1], uv[2]], [uv[1], uv[3], uv[2]]] if len(uv) == 4 else [uv]):
                (x0, y0), (x1, y1), (x2, y2) = tri

                def inside(px, py):
                    d1 = (px - x1) * (y0 - y1) - (x0 - x1) * (py - y1)
                    d2 = (px - x2) * (y1 - y2) - (x1 - x2) * (py - y2)
                    d3 = (px - x0) * (y2 - y0) - (x2 - x0) * (py - y0)
                    return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))
                for j in range(min(y0, y1, y2), max(y0, y1, y2) + 1):
                    for i in range(min(x0, x1, x2), max(x0, x1, x2) + 1):
                        if any(inside(i + a / 4, j + b / 4) for a in range(5) for b in range(5)):
                            mask[max(0, j - pad):j + pad + 1, max(0, i - pad):i + pad + 1] = True
    return mask


def place_boxes():
    """(x, y, w, h) of every stored frame band (bands with identical pixels in two states share one place)."""
    boxes = []
    for places in face.EYE_PLACES:
        boxes += [(at[0], at[1], b[2], b[3]) for at, b in zip(places, face.EYE_BANDS)]
    for places in face.MOUTH_PLACES:
        boxes += [(at[0], at[1], b[2], b[3]) for at, b in zip(places, face.MOUTH_BANDS)]
    return list(dict.fromkeys(boxes))


def overlap(a, b):
    return not (a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0] or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1])


class GarbagemonFace(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path, tim = EDIT / '269-Garbagemon.MMD', EDIT / '269-Garbagemon.TIM'
        if not path.exists() or not tim.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 269')
        data, tdata = path.read_bytes(), tim.read_bytes()
        cls.old = cls.tim0 = None
        if hashlib.sha256(data).hexdigest() == face.SOURCE:
            cls.old = face.parse(data)
            data, _ = face.build(data)
        elif hashlib.sha256(data).hexdigest() != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        if hashlib.sha256(tdata).hexdigest() == face.SOURCE_TIM:
            cls.tim0 = mmd.Tim4(tdata)
            tdata = face.texture(tdata)
        cls.data, cls.tdata = data, tdata
        cls.new = face.parse(data)
        cls.tim = mmd.Tim4(tdata)
        cls.states = {}

    def program(self, slot, model=None):
        model = model or self.new
        return model.anims.anims[model.anims.table[slot]]

    def plane_states(self, slot):
        if slot in self.states:
            return self.states[slot]
        tim = self.tim0 or self.tim
        eye0, mouth0 = face._grab(tim, face.EYE_AT, face.EYE_SIZE), face._grab(tim, face.MOUTH_AT, face.MOUTH_SIZE)
        eye_ref = [np.array(face.eye_frame(eye0, s)) for s in (face.OPEN, face.HALF, face.SHUT)]
        mouth_ref = [np.array(face.mouth_frame(mouth0, s)) for s in (face.REST, face.AJAR, face.WIDE)]
        plane = np.array(self.tim.idx, np.uint8).reshape(128, 256)
        anim = self.program(slot)
        poses, info = mmd.simulate(anim, NB, slot=slot)
        events = {}
        for t, c in info['texs']:
            events.setdefault(t, []).append(c)
        out = []
        ex, ey, ew, eh = face.EYE_AT + face.EYE_SIZE
        mx, my, mw, mh = face.MOUTH_AT + face.MOUTH_SIZE
        for t in range(len(poses)):
            for c in events.get(t, []):
                sx, sy, w, h = c['src'][0] * 4, c['src'][1], c['size'][0] * 4, c['size'][1]
                dx, dy = c['dst'][0] * 4, c['dst'][1]
                plane[dy:dy + h, dx:dx + w] = plane[sy:sy + h, sx:sx + w].copy()
            eye, mouth = plane[ey:ey + eh, ex:ex + ew], plane[my:my + mh, mx:mx + mw]
            es = [s for s, r in enumerate(eye_ref) if (eye == r).all()]
            ms = [s for s, r in enumerate(mouth_ref) if (mouth == r).all()]
            out.append((es[0] if es else None, ms[0] if ms else None))
        self.states[slot] = out
        return out

    # ---- the frames
    def test_frames_exist_and_differ(self):
        tim = self.tim
        eyes = [[face._grab(tim, at, b[2:]) for at, b in zip(places, face.EYE_BANDS)] for places in face.EYE_PLACES]
        mouths = [[face._grab(tim, at, b[2:]) for at, b in zip(places, face.MOUTH_BANDS)] for places in face.MOUTH_PLACES]
        for frames in (eyes, mouths):
            for a in range(3):
                self.assertTrue(any(any(any(r) for r in band) for band in frames[a]), 'an empty frame')
                for b in range(a + 1, 3):
                    self.assertNotEqual(frames[a], frames[b])
        # a shut eye has no iris blue left in the part the eye alone samples
        t0 = self.tim0 or self.tim
        block = face._grab(t0, face.EYE_AT, face.EYE_SIZE)
        shut = face.eye_frame(block, face.SHUT)
        spans = [(x, y) for y, (a, b) in face.EYE_SPANS.items() for x in range(a, b + 1)]
        blues = lambda rows: sum(1 for x, y in spans if rows[y - face.EYE_AT[1]][x - face.EYE_AT[0]] in (2, 3, 4, 5))
        self.assertGreater(blues(block), 40)
        self.assertEqual(blues(shut), 0)
        mouth = face._grab(t0, face.MOUTH_AT, face.MOUTH_SIZE)
        dark = lambda rows: sum(v == face.INSIDE for row in rows for v in row)
        self.assertGreater(dark(face.mouth_frame(mouth, face.WIDE)), dark(face.mouth_frame(mouth, face.AJAR)) + 30)
        self.assertGreater(dark(face.mouth_frame(mouth, face.AJAR)), dark(mouth) + 20)

    def test_bands_sharing_a_place_hold_the_same_pixels(self):
        tim = self.tim0 if self.tim0 is not None else None
        if tim is None:
            self.skipTest('needs the texture before the change')
        eye, mouth = face._grab(tim, face.EYE_AT, face.EYE_SIZE), face._grab(tim, face.MOUTH_AT, face.MOUTH_SIZE)
        seen = {}
        for bands, places, frames, origin in (
                (face.EYE_BANDS, face.EYE_PLACES, [face.eye_frame(eye, s) for s in range(3)], face.EYE_AT),
                (face.MOUTH_BANDS, face.MOUTH_PLACES, [face.mouth_frame(mouth, s) for s in range(3)], face.MOUTH_AT)):
            for state, frame in enumerate(frames):
                for band, at in zip(bands, places[state]):
                    pixels = face._band_rows(frame, origin, band)
                    self.assertEqual(seen.setdefault(at + tuple(band[2:]), pixels), pixels, at)

    def test_the_frames_lie_in_texels_no_prim_samples(self):
        used = sampled_texels(self.new)
        boxes = place_boxes()
        for x, y, w, h in boxes:
            self.assertGreaterEqual(x, 0)
            self.assertLessEqual(x + w, 256)
            self.assertLessEqual(y + h, 128)
            self.assertFalse(used[y:y + h, x:x + w].any(), (x, y, w, h))
        painted = [face.EYE_AT + face.EYE_SIZE, face.MOUTH_AT + face.MOUTH_SIZE]
        for i, a in enumerate(boxes):
            for b in boxes[i + 1:] + painted:
                self.assertFalse(overlap(a, b), (a, b))
        for x, y, w, h in boxes:
            self.assertTrue(x % 4 == 0 and w % 4 == 0, 'moves are in 4-pixel columns')
        t0 = self.tim0
        if t0 is not None:
            plane = np.array(t0.idx, np.uint8).reshape(128, 256)
            for x, y, w, h in boxes:
                self.assertFalse(plane[y:y + h, x:x + w].any(), 'a frame over painted texels')

    def test_the_eye_frames_change_only_texels_the_eye_alone_samples(self):
        t0 = self.tim0 or self.tim
        block = face._grab(t0, face.EYE_AT, face.EYE_SIZE)
        allowed = {(x, y) for y, (a, b) in face.EYE_SPANS.items() for x in range(a, b + 1)}
        for state in (face.HALF, face.SHUT):
            frame = face.eye_frame(block, state)
            for y in range(face.EYE_SIZE[1]):
                for x in range(face.EYE_SIZE[0]):
                    if frame[y][x] != block[y][x]:
                        self.assertIn((x + face.EYE_AT[0], y + face.EYE_AT[1]), allowed)
        # the bands hold every texel that differs
        for state in (face.HALF, face.SHUT):
            frame = face.eye_frame(block, state)
            for y in range(face.EYE_SIZE[1]):
                for x in range(face.EYE_SIZE[0]):
                    if frame[y][x] != block[y][x]:
                        self.assertTrue(any(bx <= x + face.EYE_AT[0] < bx + bw and by <= y + face.EYE_AT[1] < by + bh
                                            for bx, by, bw, bh in face.EYE_BANDS), (x, y))

    def test_the_texture_changes_only_in_the_frames(self):
        if self.tim0 is None:
            self.skipTest('needs the texture before this change')
        self.assertEqual(hashlib.sha256(self.tdata).hexdigest(), EXPECTED_TIM)
        t0, t1 = self.tim0, self.tim
        self.assertEqual(t0.pal, t1.pal)
        self.assertEqual((t0.w, t0.h), (t1.w, t1.h))
        a, b = np.array(t0.idx, np.uint8).reshape(128, 256), np.array(t1.idx, np.uint8).reshape(128, 256)
        keep = np.ones((128, 256), bool)
        for x, y, w, h in place_boxes():
            keep[y:y + h, x:x + w] = False
        self.assertTrue((a[keep] == b[keep]).all())

    # ---- the clips
    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_the_model_mesh_and_other_clips_are_untouched(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        self.assertEqual(self.new.tmd.build(), self.old.tmd.build())
        used = {self.new.anims.table[s] for s in SLOTS}
        self.assertEqual(self.new.anims.table, self.old.anims.table)
        for i, (a, b) in enumerate(zip(self.old.anims.anims, self.new.anims.anims)):
            if i not in used:
                self.assertEqual(a.build(), b.build(), i)

    def test_only_the_texture_events_changed(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        for slot in SLOTS:
            a, b = self.program(slot, self.old), self.program(slot)
            if slot != 0:
                self.assertEqual([i for i in a.instrs if i['op'] != 'tex'], [i for i in b.instrs if i['op'] != 'tex'], slot)
                self.assertEqual(a.frame_count, b.frame_count)
                self.assertEqual(a.pose, b.pose)
            n = face.ticks_of(b)
            self.assertEqual(n % face.ticks_of(a), 0, slot)
            p0 = face.decoded(a, n)
            p1 = face.decoded(b, n)
            self.assertEqual(p0, p1, f'slot {slot}: a pose changed')

    def test_the_idle_is_the_old_loop_repeated(self):
        if self.old is None:
            self.skipTest('needs the model before this change')
        loop = face.ticks_of(self.program(0, self.old))
        self.assertEqual(face.ticks_of(self.program(0)), loop * face.IDLE_REPEATS)
        # the repeated program closes its own loop: the pose after the last tick is the one before the first
        new = face.decoded(self.program(0), face.ticks_of(self.program(0)) + 1)
        for b in range(1, NB):
            self.assertEqual(new[0][b], new[-1][b], b)

    def test_resident_buffer(self):
        self.assertLess(motionstorage.require(self.data, NB)['resident_bytes'], BUFFER)

    def test_slots_sharing_a_program(self):
        shared = [s for s, v in enumerate(self.new.anims.table) if v == self.new.anims.table[0]]
        self.assertEqual(shared, [0, 1, 18, 33])
        for slot in (2, 3, 4):
            self.assertEqual([s for s, v in enumerate(self.new.anims.table) if v == self.new.anims.table[slot]], [slot])

    def test_loops_and_ticks(self):
        for slot, n in ((0, 134), (2, 20), (3, 22), (4, 20)):
            anim = self.program(slot)
            poses, info = mmd.simulate(anim, NB, slot=slot)
            self.assertEqual(len(poses), n, slot)
            self.assertEqual(info['loop'][1], anim.frame_count, slot)
            self.assertFalse(info['tex_quirk'], slot)

    # ---- the rest state: every clip starts and ends with open eyes and a shut mouth
    def test_every_clip_starts_and_ends_at_rest(self):
        for slot in SLOTS:
            moves = [(i['frame'], (i['src'], i['size'], i['dst'])) for i in self.program(slot).instrs if i['op'] == 'tex']
            first = [m for f, m in moves if f == 1]
            for rest in face.eye_moves(face.OPEN) + face.mouth_moves(face.REST):
                self.assertIn((rest['src'], rest['size'], rest['dst']), first, slot)
            states = self.plane_states(slot)
            self.assertEqual(states[0], (face.OPEN, face.REST), slot)
            self.assertEqual(states[-1], (face.OPEN, face.REST), slot)
            self.assertNotIn(None, [s[0] for s in states], 'an eye that is none of the three frames')
            self.assertNotIn(None, [s[1] for s in states], 'a mouth that is none of the three frames')
            # the last texture change of each feature goes back to rest
            band_dsts = [m['dst'] for m in face.eye_moves(face.OPEN)]
            eyes = [i for i in self.program(slot).instrs if i['op'] == 'tex' and i['dst'] in band_dsts]
            self.assertEqual({(i['src'], i['size'], i['dst']) for i in eyes[-6:]},
                             {(m['src'], m['size'], m['dst']) for m in face.eye_moves(face.OPEN)}, slot)
            mouths = [i for i in self.program(slot).instrs if i['op'] == 'tex' and i['dst'] in
                      [m['dst'] for m in face.mouth_moves(face.REST)]]
            self.assertEqual({(i['src'], i['size'], i['dst']) for i in mouths[-2:]},
                             {(m['src'], m['size'], m['dst']) for m in face.mouth_moves(face.REST)}, slot)

    # ---- the timing
    def runs(self, slot, feature, rest):
        """(start, length) of every stretch away from rest within one loop."""
        states = [s[feature] for s in self.plane_states(slot)]
        out, start = [], None
        for t, s in enumerate(states):
            if s != rest and start is None:
                start = t
            elif s == rest and start is not None:
                out.append((start, t - start))
                start = None
        self.assertIsNone(start, 'a clip that ends away from rest')
        return out

    def test_blinks_last_three_to_five_ticks(self):
        for slot in SLOTS:
            blinks = self.runs(slot, 0, face.OPEN)
            self.assertTrue(blinks, slot)
            for start, length in blinks:
                self.assertTrue(3 <= length <= 5, (slot, start, length))
                seq = [self.plane_states(slot)[t][0] for t in range(start, start + length)]
                self.assertIn(face.SHUT, seq)
                self.assertIn(face.HALF, seq)

    def test_idle_blinks_are_irregular_and_one_is_double(self):
        blinks = self.runs(0, 0, face.OPEN)
        self.assertEqual(len(blinks), 3)
        gaps = [b[0] - (a[0] + a[1]) for a, b in zip(blinks, blinks[1:])]
        gaps.append(face.ticks_of(self.program(0)) - (blinks[-1][0] + blinks[-1][1]) + blinks[0][0])
        self.assertTrue(any(g <= 6 for g in gaps), 'a double blink')
        self.assertEqual(len(set(gaps)), len(gaps), 'regular blinking')
        self.assertTrue(all(g >= 3 for g in gaps))
        long_gaps = [g for g in gaps if g > 6]
        self.assertTrue(all(55 <= g <= 125 for g in long_gaps), long_gaps)

    def test_idle_gapes_are_slow_and_do_not_cover_a_blink(self):
        gapes = self.runs(0, 1, face.REST)
        self.assertTrue(1 <= len([g for g in gapes if g[1] >= 15]) <= 2)
        self.assertTrue(all(g[1] <= 25 for g in gapes))
        states = self.plane_states(0)
        for start, length in gapes:
            for t in range(start, start + length):
                self.assertEqual(states[t][0], face.OPEN, 'a blink during a yawn')
        wide = [t for t, s in enumerate(states) if s[1] == face.WIDE]
        self.assertGreaterEqual(len(wide), 12)

    def test_the_mouth_is_clearly_open(self):
        for slot in SLOTS:
            self.assertTrue(any(s[1] == face.WIDE for s in self.plane_states(slot)), slot)
            for start, length in self.runs(slot, 1, face.REST):
                self.assertGreaterEqual(length, 3, (slot, start))

    def test_walk_blinks_once_and_chews_with_the_steps(self):
        for slot, step in ((2, 7), (3, 5), (4, 7)):
            self.assertEqual(len(self.runs(slot, 0, face.OPEN)), 1, slot)
        # walk and run: the jaws shut on the footfall, the sound's tick
        for slot in (2, 4):
            mouth_runs = self.runs(slot, 1, face.REST)
            ends = [s + n for s, n in mouth_runs]
            sound_tick = [i['frame'] - 1 for i in self.program(slot).instrs if i['op'] == 'sound'][0]
            self.assertIn(sound_tick, ends, slot)
        # the tired walk is slow and heavy: one long gape, longer than the walk's chew and the run's snaps
        tired = self.runs(3, 1, face.REST)
        self.assertEqual(len(tired), 1)
        self.assertGreater(tired[0][1], max(n for _, n in self.runs(2, 1, face.REST)))
        self.assertGreater(tired[0][1], max(n for _, n in self.runs(4, 1, face.REST)))
        self.assertGreater(len(self.runs(4, 1, face.REST)), len(self.runs(2, 1, face.REST)))
        self.assertGreater(self.runs(3, 0, face.OPEN)[0][1], self.runs(2, 0, face.OPEN)[0][1])


if __name__ == '__main__':
    unittest.main()
