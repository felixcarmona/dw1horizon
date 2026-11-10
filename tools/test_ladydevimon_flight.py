"""LadyDevimon's idle, walk, condition walk and run are different, seamless flights that keep the field speed.

Needs her current model (tools/models/edit.py get 223 writes it to build/imported-model-edit/edit)."""
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from tools.models.field_animations import ladydevimon_flight as flight

SOURCE = Path(os.environ.get('LADYDEVIMON_MODEL', 'build/imported-model-edit/edit/223-LadyDevimon.MMD'))
NB = flight.NB


class LadyDevimonFlight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.exists() or not Path(mmd.EXTRACTED).exists():
            raise unittest.SkipTest('needs the imported LadyDevimon model and the player DW1 extraction')
        record = json.loads(next(Path('content/species').glob('223-*.json')).read_text())
        cls.skeleton = record['model']['skeleton']
        cls.before = SOURCE.read_bytes()
        cls.after, cls.proof = flight.build(cls.before, cls.skeleton)

    def parse(self, data):
        mmd.exe().add_type(223, self.skeleton)
        model = mmd.MMD.parse(data, NB)
        model.type = 223
        return model

    def clips(self, data):
        model = self.parse(data)
        return {s: animsheet.slot_frames(model, NB, s) for s in range(0, 40)
                if model.anims.table[s] is not None}, model

    def test_only_the_field_slots_change_and_the_speed_stays(self):
        before, old = self.clips(self.before)
        after, new = self.clips(self.after)
        self.assertEqual(new.tmd.build(), old.tmd.build())
        for slot in before:
            if slot in flight.SLOTS:
                continue
            self.assertEqual(after[slot][0], before[slot][0], slot)
        for slot in (2, 3, 4):
            self.assertEqual(len(after[slot][0]), len(before[slot][0]))
            self.assertEqual(after[slot][0][-1][0][8], before[slot][0][-1][0][8])
            self.assertEqual([e[0] for e in after[slot][2]], [e[0] for e in before[slot][2]])
        self.assertEqual(after[1][0], after[0][0])

    def test_loops_are_seamless_and_the_clips_differ(self):
        after, _ = self.clips(self.after)
        poses = {}
        for slot in flight.SLOTS:
            frames, loop, _ = after[slot]
            self.assertEqual(loop, 0)
            for bone in range(1, NB):
                for channel in range(3, 9):
                    gap = abs(frames[-1][bone][channel] - frames[0][bone][channel]) % 4096
                    self.assertLessEqual(min(gap, 4096 - gap), 1, (slot, bone, channel))
            poses[slot] = frames[0][1][3:6]
        self.assertEqual(len({tuple(poses[s]) for s in (0, 2, 3, 4)}), 4)
        for slot in (2, 3, 4):
            frames = after[slot][0]
            steps = [frames[i + 1][0][8] - frames[i][0][8] for i in range(len(frames) - 1)]
            self.assertTrue(all(s < 0 for s in steps), slot)
        self.assertEqual({f[0][8] for f in after[0][0]}, {0})

    def test_the_bones_move_and_the_wings_beat_without_jumps(self):
        after, _ = self.clips(self.after)
        for slot in (0, 2, 3, 4):
            frames = after[slot][0]
            for bone in (1, 2, 4, 5, 6, 7, 17, 18, 20, 11, 14) + ((3,) if slot != 4 else ()):   # the dash holds the head still
                spread = max(max(f[bone][c] for f in frames) - min(f[bone][c] for f in frames) for c in (3, 4, 5))
                self.assertGreater(spread, 4, (slot, bone))
        for slot, beats in ((0, 2), (2, 1), (3, 1), (4, 2)):
            for bone in (6, 7):
                wing = [f[bone][5 if bone == 6 else 3] for f in after[slot][0]]
                self.assertGreater(max(wing) - min(wing), 20, (slot, bone))
                self.assertLess(max(abs(b - a) for a, b in zip(wing, wing[1:])), 120, (slot, bone))
                moves = [b - a for a, b in zip(wing, wing[1:]) if b != a]
                turns = sum(1 for a, b in zip(moves, moves[1:]) if a * b < 0)
                self.assertGreaterEqual(turns, 2 * beats - 1, (slot, bone))

    def test_the_four_clips_read_as_four_states(self):
        after, _ = self.clips(self.after)
        mean = {}
        for slot in (0, 2, 3, 4):
            frames = after[slot][0][:-1]
            mean[slot] = [[sum(f[b][c] for f in frames) / len(frames)
                           for c in (3, 4, 5)] for b in range(1, NB)]
        for a in (0, 2, 3, 4):
            for b in (0, 2, 3, 4):
                if a >= b:
                    continue
                gaps = [sum(min((x - y) % 4096, (y - x) % 4096) for x, y in zip(m, n)) * 360 / 4096
                        for m, n in zip(mean[a], mean[b])]
                self.assertGreater(max(gaps), 8, (a, b))      # some bone is posed clearly differently
                self.assertGreater(sum(gaps), 60, (a, b))     # and the whole body is
        # the body leans, the hips sit and the wings beat differently: idle upright and hovering, tired low, run leaning most
        lean = {s: mean[s][0][0] for s in mean}
        self.assertEqual(len({round(v / 40) for v in lean.values()}), 4, lean)
        hips = {s: sum(f[1][7] for f in after[s][0]) / len(after[s][0]) for s in (0, 2, 3, 4)}
        self.assertGreater(hips[3] - hips[2], 8)
        periods = {s: len(after[s][0]) - 1 for s in (0, 2, 3, 4)}
        self.assertEqual(len(set(periods.values())), 4, periods)

    def test_the_hover_height_is_kept(self):
        after, _ = self.clips(self.after)
        before, _ = self.clips(self.before)
        rest = before[0][0][0][1][7]
        for slot in flight.SLOTS:
            heights = [f[1][7] for f in after[slot][0]]
            self.assertLessEqual(abs(sum(heights) / len(heights) - rest), 14, slot)
            self.assertLessEqual(max(abs(h - rest) for h in heights), 22, slot)

    def test_storage(self):
        self.assertLessEqual(self.proof['field_flight']['storage']['resident_bytes'], 100352)


if __name__ == '__main__':
    unittest.main()
