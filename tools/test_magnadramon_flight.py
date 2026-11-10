"""Magnadramon's idle, walk and run are three different, seamless flights that keep the field speed.

Needs the reviewed imported model (tools/models/edit.py get 215 writes it to build/imported-model-edit/edit)."""
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from tools.models.field_animations import gliding, magnadramon_flight as flight

SOURCE = Path(os.environ.get('MAGNADRAMON_MODEL', 'build/imported-model-edit/edit/215-Magnadramon.MMD'))
NB = 30


class MagnadramonFlight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.exists() or not Path(mmd.EXTRACTED).exists():
            raise unittest.SkipTest('needs the imported Magnadramon model and the player DW1 extraction')
        cls.record = json.loads(next(Path('content/species').glob('215-*.json')).read_text())
        cls.skeleton = cls.record['model']['skeleton']
        data = SOURCE.read_bytes()
        cls.before, _ = gliding.build(data, cls.skeleton)
        cls.after, cls.proof = flight.build(data, cls.skeleton)

    def clips(self, data):
        mmd.exe().add_type(215, self.skeleton)
        model = mmd.MMD.parse(data, NB)
        model.type = 215
        return {s: animsheet.slot_frames(model, NB, s) for s in flight.SLOTS}, model

    def test_only_the_field_slots_change_and_the_speed_stays(self):
        before, old = self.clips(self.before)
        after, new = self.clips(self.after)
        for slot in (2, 3, 4):
            self.assertEqual(len(after[slot][0]), len(before[slot][0]))
            self.assertEqual(after[slot][0][-1][0][8], before[slot][0][-1][0][8])
        self.assertEqual(new.tmd.build(), old.tmd.build())

    def test_loops_are_seamless_and_the_clips_differ(self):
        after, _ = self.clips(self.after)
        for slot, (frames, loop, _) in after.items():
            self.assertEqual(loop, 0)
            for bone in range(1, NB):
                for channel in range(3, 9):
                    gap = abs(frames[-1][bone][channel] - frames[0][bone][channel]) % 4096
                    self.assertLessEqual(min(gap, 4096 - gap), 1, (slot, bone, channel))
        lean = {s: after[s][0][0][1][3] for s in (0, 2, 4)}
        self.assertEqual(len(set(lean.values())), 3)
        for slot in (2, 3, 4):
            frames = after[slot][0]
            steps = [frames[i + 1][0][8] - frames[i][0][8] for i in range(len(frames) - 1)]
            self.assertTrue(all(s < 0 for s in steps), slot)
        self.assertEqual({f[0][8] for f in after[0][0]}, {0})
        # the wings beat (idle two, walk three, run four times per loop) without jumps
        for slot, beats in ((0, 2), (2, 3), (4, 4)):
            wing = [f[12][5] for f in after[slot][0]]
            self.assertGreater(max(wing) - min(wing), 300)
            self.assertLess(max(abs(b - a) for a, b in zip(wing, wing[1:])), 200)
            moves = [b - a for a, b in zip(wing, wing[1:]) if b != a]
            turns = sum(1 for a, b in zip(moves, moves[1:]) if a * b < 0)
            self.assertGreaterEqual(turns, 2 * beats - 1)
            self.assertLessEqual(turns, 2 * beats + 1)
        # the jaw opens and closes smoothly, clearly (20 to 40 degrees), in every clip
        for slot in (0, 2, 4):
            jaw = [f[5][3] for f in after[slot][0]]
            self.assertGreater(max(jaw) - min(jaw), 20 * 4096 / 360)
            self.assertLess(max(jaw) - min(jaw), 40 * 4096 / 360)
            self.assertLess(max(abs(b - a) for a, b in zip(jaw, jaw[1:])), 8 * 4096 / 360)


if __name__ == '__main__':
    unittest.main()
