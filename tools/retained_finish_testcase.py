"""Decoded regressions for battle finishes retained after the final-rig review."""
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


class RetainedFinishCase(unittest.TestCase):
    sid = None
    slots = ()

    def test_retained_finishes_and_field_programs(self):
        if self.sid is None:
            self.skipTest('shared case')
        review = Path(os.environ.get('FINISH_REVIEW', ROOT / 'build/battle-finishes'))
        files = [review / part / f'{self.sid}.C.MMD' for part in ('main', 'final')]
        if not all(p.is_file() for p in files):
            self.skipTest('needs reconstructed before/after provider models')
        sk = json.loads((review / 'main' / f'{self.sid}-species.json').read_text())['model']['skeleton']
        nb = len(sk)
        before, after = [mmd.MMD.parse(p.read_bytes(), nb) for p in files]
        self.assertEqual(before.tmd.build(), after.tmd.build())
        for slot, program in enumerate(before.anims.table):
            if program is None:
                self.assertIsNone(after.anims.table[slot], slot)
            else:
                self.assertEqual(animsheet.slot_frames(before, nb, slot),
                                 animsheet.slot_frames(after, nb, slot), slot)
        for slot in range(5):
            self.assertEqual(before.anims.anims[before.anims.table[slot]].build(),
                             after.anims.anims[after.anims.table[slot]].build(), slot)
        self.assertLess(motionstorage.require(files[1].read_bytes(), nb)['resident_bytes'], 100352)
