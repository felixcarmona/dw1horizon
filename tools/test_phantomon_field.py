"""Phantomon's idle, walk, condition walk and run are four different, seamless hover clips that keep the field speed.

Needs the final model (tools/models/edit.py get 229 writes it to build/imported-model-edit/edit)."""
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from tools.models.field_animations import phantomon as gen

MODEL = Path(os.environ.get('PHANTOMON_MODEL', 'build/imported-model-edit/edit/229-Phantomon.MMD'))
SKELETON = [(i - 1, p) for i, p in enumerate(gen.PARENTS)]


class PhantomonField(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEL.exists() or not Path(mmd.EXTRACTED).exists():
            raise unittest.SkipTest('needs the final Phantomon model and the player DW1 extraction')
        mmd.exe().skeleton[229] = SKELETON
        mmd.exe().bone_count[229] = 20
        cls.model = mmd.MMD.parse(MODEL.read_bytes(), 20)
        cls.model.type = 229
        cls.clips = {s: animsheet.slot_frames(cls.model, 20, s)[0] for s in (0, 2, 3, 4)}

    def test_lengths_speeds_and_loops(self):
        for slot, ticks, speed in ((0, 104, 0), (2, 24, 21.9), (3, 28, 18.8), (4, 20, 52.7)):
            frames = self.clips[slot]
            self.assertEqual(len(frames) - 1, ticks)
            self.assertAlmostEqual(-(frames[-1][0][8] - frames[0][0][8]) / ticks, speed, delta=.1)
            steps = {frames[i + 1][0][8] - frames[i][0][8] for i in range(ticks)}
            self.assertLessEqual(max(steps) - min(steps), 1)
            for bone in range(1, 20):
                for channel in range(3, 9):
                    gap = abs(frames[-1][bone][channel] - frames[0][bone][channel]) % 4096
                    self.assertLessEqual(min(gap, 4096 - gap), 1, (slot, bone, channel))

    def test_the_four_clips_differ_and_keep_the_hover_height(self):
        poses = {s: [[tuple(b[3:6]) for b in f[1:]] for f in fr[:20]] for s, fr in self.clips.items()}
        slots = sorted(poses)
        for i, a in enumerate(slots):
            for b in slots[i + 1:]:
                gap = sum(abs(x - y) for pa, pb in zip(poses[a], poses[b]) for ra, rb in zip(pa, pb) for x, y in zip(ra, rb))
                self.assertGreater(gap, 10000, (a, b))
        lean = {s: fr[0][1][3] for s, fr in self.clips.items()}
        self.assertEqual(len(set(lean.values())), 4)
        for fr in self.clips.values():
            mean = sum(f[1][7] for f in fr[:-1]) / (len(fr) - 1)
            self.assertAlmostEqual(mean, -246, delta=2)
            self.assertEqual({f[0][7] for f in fr}, {0})

    def test_arms_swing_forward_and_back_only(self):
        for slot in (2, 4):
            arm = [f[6][3] for f in self.clips[slot]]
            self.assertGreater(max(arm) - min(arm), 20 * 4096 / 360)
        for slot, fr in self.clips.items():
            for bone in (6, 9):
                self.assertLess(max(f[bone][5] for f in fr) - min(f[bone][5] for f in fr), 15 * 4096 / 360)

    def test_only_those_four_programs_changed(self):
        other = [s for s in range(0, 40) if s not in (0, 2, 3, 4) and self.model.anims.table[s] in (
            self.model.anims.table[0], self.model.anims.table[2], self.model.anims.table[3], self.model.anims.table[4])]
        self.assertEqual(other, [])

    def test_generator_rejects_another_source(self):
        with self.assertRaises(ValueError):
            gen.build(MODEL.read_bytes(), SKELETON)


if __name__ == '__main__':
    unittest.main()
