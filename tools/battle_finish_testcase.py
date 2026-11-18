"""Shared decoded regressions for final-rig battle finishes (disc assets optional)."""
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools'), str(ROOT / 'tools/models')]
import animsheet
import mmd
import motionstorage
from tools.models.battle_finishes import SLOTS, author
from tools.models.battle_finish_contacts import audit
from tools.models.field_animations.native_battle import scaled_events


class FinishCase(unittest.TestCase):
    sid = None

    @classmethod
    def setUpClass(cls):
        if cls.sid is None:
            raise unittest.SkipTest('shared case')
        review = Path(os.environ.get('FINISH_REVIEW', ROOT / 'build/battle-finishes'))
        paths = [review / part / f'{cls.sid}.C.MMD' for part in ('main', 'final', 'reference')]
        if not all(path.is_file() for path in paths):
            raise unittest.SkipTest('needs reconstructed provider and retargeted reference models')
        cls.before, cls.data, cls.reference = [path.read_bytes() for path in paths]
        cls.sk = json.loads((review / 'main' / f'{cls.sid}-species.json').read_text())['model']['skeleton']
        cls.nb = len(cls.sk)
        cls.old, cls.new = [mmd.MMD.parse(data, cls.nb) for data in (cls.before, cls.data)]

    def test_recipe_replays_exactly(self):
        replay = mmd.MMD.parse(author(self.before, self.sk, self.sid, self.reference), self.nb)
        # The provider may coalesce unrelated technique aliases after this pass.
        for slot in SLOTS[self.sid]:
            self.assertEqual(replay.anims.anims[replay.anims.table[slot]].build(),
                             self.new.anims.anims[self.new.anims.table[slot]].build(), slot)

    def test_only_authored_programs_change(self):
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())
        for slot, program in enumerate(self.old.anims.table):
            if program is None:
                self.assertIsNone(self.new.anims.table[slot], slot)
            elif slot not in SLOTS[self.sid]:
                self.assertEqual(animsheet.slot_frames(self.old, self.nb, slot),
                                 animsheet.slot_frames(self.new, self.nb, slot), slot)
        for slot in range(5):
            self.assertEqual(self.old.anims.anims[self.old.anims.table[slot]].build(),
                             self.new.anims.anims[self.new.anims.table[slot]].build(), slot)
        self.assertLess(motionstorage.require(self.data, self.nb)['resident_bytes'], 100352)

    def test_clocks_and_sound_ticks(self):
        for slot in SLOTS[self.sid]:
            old, _, events = animsheet.slot_frames(self.old, self.nb, slot)
            new, loop, actual = animsheet.slot_frames(self.new, self.nb, slot)
            self.assertIsNone(loop)
            self.assertLessEqual(len(new)-1, (len(old)-1)*1.6)
            def content(rows):
                return [(tick, kind, {k: v for k, v in payload.items() if k != 'frame'})
                        for tick, kind, payload in rows]
            self.assertEqual(content(actual), content(scaled_events(events, len(old), len(new))), slot)

    def test_floor_landing_and_support(self):
        report = audit(self.data, self.sk, self.sid)
        self.assertTrue(report['passed'], report)

    def test_polished_checks_and_crossings(self):
        import battle_qa as qa
        slots = SLOTS[self.sid]
        rows = qa.species_check(self.data, self.reference, self.before, self.sk, slots, slots)
        for slot, row in rows.items():
            self.assertEqual(row['flags'], [], slot)
            self.assertLessEqual(row['final']['cross'][0], row['main']['cross'][0], slot)
            self.assertLessEqual(row['final']['cross'][1], row['main']['cross'][1], slot)
