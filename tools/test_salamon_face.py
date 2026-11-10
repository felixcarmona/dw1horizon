"""Tests of Salamon's blink schedule (tools/models/field_animations/salamon_face.py) and of its gait table (salamon.py).

    python3 tools/test_salamon_face.py
"""
import unittest

from tools.models.field_animations import salamon, salamon_face as face


class FakeTim:
    def __init__(self):
        self.idx = bytearray(256 * 128)
        for y in range(52):                                   # a used part: a skin gradient and a dark eye
            for x in range(256):
                self.idx[y * 256 + x] = 3 + x % 5
        for y in range(8, 24):
            for x in range(18, 40):
                self.idx[y * 256 + x] = 9 if (x + y) % 3 else 11


class SalamonFace(unittest.TestCase):
    def test_every_clip_opens_and_ends_with_open_eyes(self):
        opened = face.eye_move(0)
        for slot, plan in salamon.EYES.items():
            self.assertEqual(plan[-1][1], 0, slot)
            ticks = {0: 92, 2: 27, 3: 27, 4: 32}[slot]
            events = salamon._events(slot, ticks)
            self.assertEqual(events[0], (0, 'tex', opened), slot)
            self.assertEqual(max(t for t, _, _ in events), plan[-1][0])
            self.assertLess(plan[-1][0], ticks)

    def test_blinks_do_not_overlap_and_close_before_the_next_starts(self):
        for slot, plan in salamon.EYES.items():
            ticks = [t for t, _ in plan]
            self.assertEqual(ticks, sorted(set(ticks)), slot)
            starts = [t for t, k in plan if k == 1 and (plan.index((t, k)) == 0 or plan[plan.index((t, k)) - 1][1] == 0)]
            self.assertTrue(starts)

    def test_frames_stay_in_the_free_rows_and_leave_the_used_part_alone(self):
        tim = FakeTim()
        before = bytes(tim.idx)
        face.stamp(tim)
        self.assertEqual(bytes(tim.idx[:face.FRAME_Y * 256]), before[:face.FRAME_Y * 256])
        w, h = face.EYE_SIZE
        for x in face.EYE_FRAMES:
            self.assertLessEqual(x + w, 256)
            self.assertLessEqual(face.FRAME_Y + h, 128)
        open_eye = [tim.idx[(face.FRAME_Y + y) * 256 + x] for y in range(h) for x in range(w)]
        self.assertEqual(bytes(open_eye), bytes(before[(face.EYE_AT[1] + y) * 256 + face.EYE_AT[0] + x]
                                                for y in range(h) for x in range(w)))

    def test_gait_table_is_a_small_dogs(self):
        gaits = salamon.PROFILE['gaits']
        for slot in (2, 3):                                    # lateral sequence: hind foot then the front foot on its side
            t = gaits[slot]['touchdown']
            self.assertEqual(sorted(t, key=t.get), ['LH', 'LF', 'RH', 'RF'])
        trot = gaits[4]['touchdown']
        self.assertEqual(trot['LF'], trot['RH'])
        self.assertEqual(trot['RF'], trot['LH'])
        self.assertNotEqual(trot['LF'], trot['RF'])
        # the rest stance, not the midline: the legs hang from their own side
        sides = {name: leg[3] for name, leg in salamon.PROFILE['legs'].items()}
        self.assertEqual(sides, {'RF': 1, 'LF': -1, 'RH': 1, 'LH': -1})
        # the body is calm: modest bob, pitch and nod on every gait (peak per-tick pelvis speed of the stored clips is about
        # 4 / 2 / 7 units and chest pitch 3 / 2.3 / 5.7 degrees for walk / tired / run; v3's 7 / 5 / 11 and up to 11.2 degrees
        # read as hyperactive)
        for slot, cap in ((2, 2), (3, 2), (4, 6)):
            self.assertLessEqual(gaits[slot]['bob'], cap, slot)
            self.assertLessEqual(gaits[slot]['pitch'], 4, slot)
            self.assertLessEqual(gaits[slot]['nod'], 3, slot)
            self.assertLessEqual(gaits[slot]['loose'], 5, slot)
        self.assertGreater(gaits[4]['bob'], gaits[2]['bob'])
        self.assertEqual({s: (g['ticks'], g['speed']) for s, g in gaits.items()}, {2: (9, 10), 3: (9, 8), 4: (8, 28)})


if __name__ == '__main__':
    unittest.main()
