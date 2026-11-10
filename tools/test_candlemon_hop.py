"""Candlemon's hopping field clips (tools/models/field_animations/candlemon_hop.py) and its face (candlemon_face.py).

The face tests need nothing; the clip tests need the final model (tools/models/edit.py get 235 writes it to
build/imported-model-edit/edit) and the player DW1 extraction.

    python3 tools/test_candlemon_hop.py
"""
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet  # noqa: E402
import mmd  # noqa: E402
from tools.models.field_animations import candlemon_face as face, candlemon_hop as gen  # noqa: E402

MODEL = Path(os.environ.get('CANDLEMON_MODEL', 'build/imported-model-edit/edit/235-Candlemon.MMD'))
SKELETON = [(i - 1, p) for i, p in enumerate(gen.PARENTS)]


class FakeTim:
    def __init__(self):
        self.idx = bytearray(256 * 128)
        for y in range(24):
            for x in range(256):
                self.idx[y * 256 + x] = 2 + x % 7 + (y > 11) * 3 + (y > 17) * 5
        eye = [[(x * 3 + y) % 16 for x in range(32)] for y in range(24)]
        for at in (face.EYE_AT, face.EYE_FRAMES[0]):
            face._put(self, at, eye)


class CandlemonFace(unittest.TestCase):
    def test_frames_land_in_the_spare_rows_only(self):
        tim = FakeTim()
        before = bytes(tim.idx)
        face.stamp(tim)
        changed = {(i % 256, i // 256) for i in range(len(before)) if before[i] != tim.idx[i]}
        allowed = {(x + dx, y + dy) for x, y in face.MOUTH_FRAMES for dx in range(32) for dy in range(24)}
        self.assertTrue(changed <= allowed)
        rest = face._grab(tim, face.MOUTH_AT, face.MOUTH_SIZE)
        self.assertEqual(face._grab(tim, face.MOUTH_FRAMES[face.REST], face.MOUTH_SIZE), rest)
        shut = face._grab(tim, face.MOUTH_FRAMES[face.MSHUT], face.MOUTH_SIZE)
        self.assertNotEqual(shut, rest)

    def test_moves_are_word_aligned_and_inside_the_texture(self):
        for state in (face.OPEN, face.HALF, face.SHUT):
            m = face.eye_move(state)
            self.assertEqual((m['size'], m['dst']), ((8, 24), (2, 0)))
        for state in (face.REST, face.MHALF, face.MSHUT, face.WIDE):
            m = face.mouth_move(state)
            self.assertEqual((m['size'], m['dst']), ((8, 24), (13, 0)))
            self.assertLessEqual(m['src'][0] * 4 + 32, 256)
            self.assertLessEqual(m['src'][1] + 24, 128)

    def test_the_idle_sets_its_face_first_and_comes_back_to_it(self):
        events = face.events(gen.IDLE_EYES, gen.IDLE_MOUTH, gen.IDLE_TICKS)
        self.assertEqual(events[:2], [(0, 'tex', face.eye_move(face.OPEN)), (0, 'tex', face.mouth_move(face.REST))])
        self.assertEqual(gen.IDLE_EYES[-1][1], face.OPEN)
        self.assertEqual(gen.IDLE_MOUTH[-1][1], face.REST)
        with self.assertRaises(AssertionError):
            face.events([(5, face.SHUT)], [], 20)                            # a plan that does not reopen the eyes


class CandlemonClips(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEL.exists() or not Path(mmd.EXTRACTED).exists():
            raise unittest.SkipTest('needs the final Candlemon model and the player DW1 extraction')
        mmd.exe().skeleton[235] = SKELETON
        mmd.exe().bone_count[235] = gen.NB
        cls.model = mmd.MMD.parse(MODEL.read_bytes(), gen.NB)
        cls.model.type = 235
        cls.clips = {s: animsheet.slot_frames(cls.model, gen.NB, s) for s in gen.SLOTS}

    def test_lengths_speeds_and_seamless_loops(self):
        for slot, ticks, speed in ((0, 96, 0), (2, 56, 20), (3, 54, 13), (4, 50, 38)):
            frames = self.clips[slot][0]
            self.assertEqual(len(frames) - 1, ticks)
            self.assertAlmostEqual(-(frames[-1][0][8] - frames[0][0][8]) / ticks, speed, delta=.1)
            for bone in range(1, gen.NB):
                for channel in range(9):
                    gap = abs(frames[-1][bone][channel] - frames[0][bone][channel]) % 4096
                    self.assertLessEqual(min(gap, 4096 - gap), 1, (slot, bone, channel))

    def test_hops_leave_the_ground_and_land_without_sliding(self):
        for slot, g in gen.GAITS.items():
            frames = self.clips[slot][0]
            foot = [f[gen.FOOT][8] + f[0][8] for f in frames]                # where the foot is along z
            lift = [-f[gen.FOOT][7] for f in frames]
            for t in range(len(frames) - 1):
                if t % g['period'] < g['contact']:
                    self.assertLessEqual(abs(foot[t + 1] - foot[t]), 2, (slot, t))
            self.assertGreater(max(lift) - min(lift), g['height'] * .8, slot)

    def test_each_clip_carries_its_face_and_its_landing_sounds(self):
        for slot in gen.SLOTS:
            events = self.clips[slot][2]
            tex = [e for e in events if e[1] == 'tex']
            self.assertGreaterEqual(len(tex), 10, slot)
            self.assertEqual({e[0] for e in tex[:2]}, {0}, slot)
            sounds = [e for e in events if e[1] == 'sound']
            self.assertEqual(len(sounds), 0 if slot == 0 else gen.GAITS[slot]['hops'], slot)

    def test_the_four_clips_differ(self):
        def profile(slot):
            frames = self.clips[slot][0]
            return [max(f[b][c] for f in frames) - min(f[b][c] for f in frames)
                    for b in (gen.FOOT, gen.CANDLE, gen.FLAME, 3) for c in (1, 3, 4, 7)]
        profiles = {s: profile(s) for s in gen.SLOTS}
        for a in gen.SLOTS:
            for b in gen.SLOTS:
                if a < b:
                    self.assertGreater(sum(abs(x - y) for x, y in zip(profiles[a], profiles[b])), 100, (a, b))


if __name__ == '__main__':
    unittest.main()
