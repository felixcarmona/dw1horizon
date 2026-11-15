"""Decoded before/after provider checks for a battle-motion retry."""
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet
import mmd
import motionstorage


class BattleRetryCase(unittest.TestCase):
    review_env = "BATTLE_RETRY_REVIEW"
    sid = None
    changed_slots = ()

    def test_final_programs_and_field_bytes(self):
        if self.sid is None:
            self.skipTest('shared case')
        review = os.environ.get(self.review_env)
        if not review:
            self.skipTest('needs before/after provider fixtures')
        review = Path(review)
        skeleton = json.loads((review / 'main' / f'{self.sid}-species.json').read_text())['model']['skeleton']
        nb = len(skeleton)
        before, after = [(review / part / f'{self.sid}.C.MMD').read_bytes()
                         for part in ('main', 'final')]
        old, new = [mmd.MMD.parse(data, nb) for data in (before, after)]
        self.assertEqual(old.tmd.build(), new.tmd.build())
        for slot, program in enumerate(old.anims.table):
            if slot in self.changed_slots:
                continue
            if program is None:
                self.assertIsNone(new.anims.table[slot], slot)
            else:
                self.assertEqual(animsheet.slot_frames(old, nb, slot),
                                 animsheet.slot_frames(new, nb, slot), slot)
        for slot in range(5):
            self.assertEqual(old.anims.anims[old.anims.table[slot]].build(),
                             new.anims.anims[new.anims.table[slot]].build(), slot)
        self.assertLess(motionstorage.require(after, nb)['resident_bytes'], 100352)
