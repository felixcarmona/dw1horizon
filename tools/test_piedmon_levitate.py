"""Piedmon's idle, walk, condition walk and run are four different, seamless levitating clips with a steady hover.

Needs the final model (tools/models/edit.py get 245 writes it to build/imported-model-edit/edit)."""
import copy
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
import motionstorage
from tools.models.field_animations import piedmon_levitate as gen

MODEL = Path(os.environ.get('PIEDMON_MODEL', 'build/imported-model-edit/edit/245-Piedmon.MMD'))
SKELETON = [(i - 1, p) for i, p in enumerate(gen.PARENTS)]
TICKS = {0: 104, 2: 24, 3: 28, 4: 20}


class PiedmonLevitate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MODEL.exists() or not Path(mmd.EXTRACTED).exists():
            raise unittest.SkipTest('needs the final Piedmon model and the player DW1 extraction')
        mmd.exe().skeleton[245] = SKELETON
        mmd.exe().bone_count[245] = 28
        cls.data = MODEL.read_bytes()
        cls.model = mmd.MMD.parse(cls.data, 28)
        cls.model.type = 245
        cls.clips = {s: animsheet.slot_frames(cls.model, 28, s)[0] for s in (0, 1, 2, 3, 4, 18, 33)}

    def test_lengths_speeds_and_loops(self):
        for slot, ticks in TICKS.items():
            frames = self.clips[slot]
            self.assertEqual(len(frames) - 1, ticks)
            steps = {frames[i + 1][0][8] - frames[i][0][8] for i in range(ticks)}
            self.assertLessEqual(max(steps) - min(steps), 1)
            for bone in range(1, 28):
                for channel in range(3, 9):
                    gap = abs(frames[-1][bone][channel] - frames[0][bone][channel]) % 4096
                    self.assertLessEqual(min(gap, 4096 - gap), 1, (slot, bone, channel))
        for slot, speed in ((0, 0), (2, 19.0), (3, 16.4), (4, 46.3)):
            fr = self.clips[slot]
            self.assertAlmostEqual(-(fr[-1][0][8] - fr[0][0][8]) / TICKS[slot], speed, delta=.1)
        self.assertEqual(self.model.anims.table[1], self.model.anims.table[0])

    def test_the_four_clips_differ(self):
        poses = {s: [[tuple(b[3:6]) for b in f[1:]] for f in self.clips[s][:20]] for s in TICKS}
        slots = sorted(poses)
        for i, a in enumerate(slots):
            for b in slots[i + 1:]:
                gap = sum(abs(x - y) for pa, pb in zip(poses[a], poses[b]) for ra, rb in zip(pa, pb) for x, y in zip(ra, rb))
                self.assertGreater(gap, 20000, (a, b))
        self.assertEqual(len({fr[0][1][3] for s, fr in self.clips.items() if s in TICKS}), 4)

    def test_hover_height_is_the_same_in_every_clip(self):
        for slot, ticks in TICKS.items():
            heights = [gen.lowest(self.model, SKELETON, self.clips[slot][t]) for t in range(ticks)]
            self.assertAlmostEqual(sum(heights) / ticks, gen.HOVER, delta=2.5, msg=slot)
            self.assertGreater(min(heights), 15, slot)       # never touches the ground
            self.assertLess(max(heights) - min(heights), 45, slot)
            ribbons = [gen.lowest(self.model, SKELETON, self.clips[slot][t], skip=()) for t in range(ticks)]
            self.assertGreater(min(ribbons), 5, slot)

    def test_only_the_idle_and_the_three_walks_changed(self):
        table = self.model.anims.table
        for slot in (18, 33):
            self.assertNotEqual(table[slot], table[0])
            self.assertEqual(len(self.clips[slot]) - 1, 104)
        self.assertEqual(len({table[s] for s in (0, 2, 3, 4)}), 4)

    def test_buffer(self):
        report = motionstorage.require(self.data, 28)
        self.assertLess(report['resident_bytes'], report['resident_limit'])

    def test_generator_rejects_another_source(self):
        with self.assertRaises(ValueError):
            gen.build(self.data, SKELETON)


if __name__ == '__main__':
    unittest.main()
