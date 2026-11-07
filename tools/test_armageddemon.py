"""Replay the baked model's paired support and technique-slot contracts."""
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
import retarget as rt
from tools.models.field_animations.armageddemon import ATTACKS, PAIRS, build
from tools.models.scale_lock import measure


@unittest.skipUnless(os.environ.get('ARMAGEDDEMON_SOURCE'), 'needs the preceding reviewed model')
class Armageddemon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skeleton = json.loads(Path('content/species/407-armageddemon.json').read_text())['model']['skeleton']
        cls.source = Path(os.environ['ARMAGEDDEMON_SOURCE']).read_bytes()
        cls.output, cls.storage = build(cls.source, cls.skeleton)
        cls.old = mmd.MMD.parse(cls.source, 27)
        cls.new = mmd.MMD.parse(cls.output, 27)

    def test_constant_scale_and_hardware_storage(self):
        audit = measure(self.new, self.skeleton, 0)
        self.assertFalse(audit['across_slots'])
        self.assertTrue(self.storage['fits'])
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())

    def test_four_supporting_feet_and_closed_gestures(self):
        rest = animsheet.slot_frames(self.new, 27, 0)[0][0]
        _, positions = rt.world_transform(self.skeleton, rest)
        feet = [hip + 2 for pair in PAIRS for hip in pair]
        for slot, ticks in ((0, 24), (11, 60)):
            frames, loop, _ = animsheet.slot_frames(self.new, 27, slot)
            self.assertEqual(len(frames), ticks + 1)
            self.assertEqual(loop, 0 if slot == 0 else None)
            for tick, pose in enumerate(frames):
                _, actual = rt.world_transform(self.skeleton, pose)
                raised = [b for b in feet if positions[b][1] - actual[b][1] > 3]
                self.assertLessEqual(len(raised), 2, (slot, tick, raised))
                if raised:
                    pair = min(2, tick * 3 // ticks)
                    self.assertTrue(set(raised) <= {b + 2 for b in PAIRS[pair]})
                for b in feet:
                    if b not in raised:
                        self.assertLess(sum((actual[b][c] - positions[b][c]) ** 2 for c in range(3)), 16)
            self.assertEqual(frames[0], frames[-1])

    def test_all_techniques_use_the_selected_existing_program(self):
        for target, source in enumerate(ATTACKS):
            before = animsheet.slot_frames(self.old, 27, 46 + source)
            after = animsheet.slot_frames(self.new, 27, 46 + target)
            self.assertEqual(before, after, target)
        for slot in (2, 3, 4, 8, 9, 10, 12, 33, 34, 35, 36, 40, 41, 42, 43, 44):
            self.assertEqual(animsheet.slot_frames(self.old, 27, slot),
                             animsheet.slot_frames(self.new, 27, slot), slot)


if __name__ == '__main__':
    unittest.main()
