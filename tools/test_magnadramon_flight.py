"""Magnadramon's idle, walk, tired walk and run are four different, seamless flights at the field speed.

Needs the reviewed imported model (tools/models/edit.py get 215 writes it to build/imported-model-edit/edit)."""
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from tools.models.field_animations import magnadramon_flight as flight

SOURCE = Path(os.environ.get('MAGNADRAMON_MODEL', 'build/imported-model-edit/edit/215-Magnadramon.MMD'))
NB = 30


class MagnadramonFlight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.exists() or not Path(mmd.EXTRACTED).exists():
            raise unittest.SkipTest('needs the imported Magnadramon model and the player DW1 extraction')
        cls.record = json.loads(next(Path('content/species').glob('215-*.json')).read_text())
        cls.skeleton = cls.record['model']['skeleton']
        cls.data = SOURCE.read_bytes()
        cls.after, cls.proof = flight.build(cls.data, cls.skeleton)

    def clips(self, data):
        mmd.exe().add_type(215, self.skeleton)
        model = mmd.MMD.parse(data, NB)
        model.type = 215
        return {s: animsheet.slot_frames(model, NB, s) for s in flight.SLOTS}, model

    def test_only_the_field_slots_change_and_the_mesh_stays(self):
        _, old = self.clips(self.data)
        _, new = self.clips(self.after)
        self.assertEqual(new.tmd.build(), old.tmd.build())

    def test_loops_are_seamless_and_run_at_the_field_speed(self):
        after, _ = self.clips(self.after)
        for slot, (frames, loop, _) in after.items():
            self.assertEqual(loop, 0)
            for bone in range(1, NB):
                for channel in range(3, 9):
                    gap = abs(frames[-1][bone][channel] - frames[0][bone][channel]) % 4096
                    self.assertLessEqual(min(gap, 4096 - gap), flight.TOL, (slot, bone, channel))
        self.assertEqual({f[0][8] for f in after[0][0]}, {0})
        for slot, kind in ((2, 'walk'), (3, 'tired'), (4, 'run')):
            frames = after[slot][0]
            steps = [frames[i + 1][0][8] - frames[i][0][8] for i in range(len(frames) - 1)]
            self.assertTrue(all(s < 0 for s in steps), slot)
            per_tick = abs(frames[-1][0][8] - frames[0][0][8]) / (len(frames) - 1)
            self.assertAlmostEqual(per_tick, abs(flight.TRAVEL[kind]) / flight.TICKS[kind], delta=1.5)

    def test_the_blades_beat_and_the_jaw_opens_in_every_clip(self):
        after, _ = self.clips(self.after)
        for slot in (0, 2, 3, 4):
            frames = after[slot][0]
            for right, left in flight.BLADES:
                for bone in (right, left):
                    chan = [max(range(3, 6), key=lambda c: max(f[bone][c] for f in frames) - min(f[bone][c] for f in frames))]
                    wing = [f[bone][chan[0]] for f in frames]
                    self.assertGreater(max(wing) - min(wing), 100, (slot, bone))
            jaw = [f[5][3] for f in frames]
            self.assertGreater(max(jaw) - min(jaw), 10 * 4096 / 360, slot)
            self.assertLess(max(abs(b - a) for a, b in zip(jaw, jaw[1:])), 12 * 4096 / 360, slot)
        # idle, walk and run are three different movements
        lean = {s: after[s][0][0][1][3] for s in (0, 2, 4)}
        self.assertEqual(len(set(lean.values())), 3)


if __name__ == '__main__':
    unittest.main()
