"""Guard Magnamon's retained battle finishes and exact field programs.

Set FINISH_REVIEW to a review directory containing main/ and final/ provider
models. These are reconstructed with the source discs, as for the gait tests.
"""
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


class MagnamonFinishes(unittest.TestCase):
    def test_retained_finishes_and_field_programs(self):
        recipe = json.loads((ROOT / 'content/models/imports/native-bindings.json').read_text())['197']
        self.assertFalse({42, 43, 44}.intersection(recipe['battle_originals']['slots']))
        review = Path(os.environ.get('FINISH_REVIEW', ROOT / 'build/battle-finishes'))
        paths = [review / d / '197.C.MMD' for d in ('main', 'final')]
        if not all(p.is_file() for p in paths):
            self.skipTest('needs the before/after provider models')
        before, after = [mmd.MMD.parse(p.read_bytes(), 23) for p in paths]
        self.assertEqual(before.tmd.build(), after.tmd.build())
        for slot in range(len(before.anims.table)):
            if before.anims.table[slot] is not None:
                self.assertEqual(animsheet.slot_frames(before, 23, slot),
                                 animsheet.slot_frames(after, 23, slot), slot)
        for slot in range(5):
            self.assertEqual(before.anims.anims[before.anims.table[slot]].build(),
                             after.anims.anims[after.anims.table[slot]].build(), slot)
        self.assertLess(motionstorage.require(paths[1].read_bytes(), 23)['resident_bytes'], 100352)


if __name__ == '__main__':
    unittest.main()
