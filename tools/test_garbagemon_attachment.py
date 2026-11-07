"""Check the repaired provider model with locally reconstructed inputs.

GARBAGEMON_BEFORE=MODEL GARBAGEMON_AFTER=MODEL PYTHONPATH=tools python3 -m
unittest tools.test_garbagemon_attachment
"""
import os
from pathlib import Path
import unittest

import animsheet
import mmd
import motionstorage
from tools.models.field_animations.garbagemon import can_floor


class AttachmentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        paths = [os.environ.get(n) for n in ('GARBAGEMON_BEFORE', 'GARBAGEMON_AFTER')]
        if not all(p and Path(p).is_file() for p in paths):
            raise unittest.SkipTest('requires reconstructed before/after Garbagemon models')
        cls.before, cls.after = [mmd.MMD.load(p, 269) for p in paths]
        cls.result = Path(paths[1]).read_bytes()

    def test_attachment_and_acting_in_every_occupied_slot(self):
        a, b = self.before, self.after
        self.assertEqual(a.tmd.build(), b.tmd.build())
        attachment = animsheet.slot_frames(a, 22, 1)[0][0][2]
        for slot, index in enumerate(a.anims.table):
            with self.subTest(slot=slot):
                if index is None:
                    self.assertIsNone(b.anims.table[slot])
                    continue
                frames, loop, events = animsheet.slot_frames(a, 22, slot)
                result, new_loop, new_events = animsheet.slot_frames(b, 22, slot)
                self.assertEqual((len(frames), loop), (len(result), new_loop))
                def semantic(cues):
                    return [(tick, kind, {k: v for k, v in cue.items() if k != 'frame'})
                            for tick, kind, cue in cues if not
                            (kind == 'sound' and cue['bank'] == 1 and cue['note'] == 15)]
                self.assertEqual(semantic(events), semantic(new_events))
                self.assertFalse(any(kind == 'sound' and cue['bank'] == 1 and cue['note'] == 15
                                     for _, kind, cue in new_events))
                for before, after in zip(frames, result):
                    self.assertEqual(after[2], attachment)
                    self.assertLessEqual(abs(can_floor(a, before) - can_floor(b, after)), 0.51)
                    # Root travel, body rotation, limbs, face and equipment keep
                    # the original acting; only support height may change.
                    for bone in range(22):
                        if bone == 2:
                            continue
                        for channel in range(9):
                            if (bone, channel) != (1, 7):
                                self.assertEqual(before[bone][channel], after[bone][channel])

    def test_original_console_storage(self):
        self.assertTrue(motionstorage.require(self.result, 22)['fits'])


if __name__ == '__main__':
    unittest.main()
