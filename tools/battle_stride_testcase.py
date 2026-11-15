"""Provider, contact and clock regressions for reviewed battle strides."""
import importlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools'), str(ROOT / 'tools/models')]
import animsheet
import mmd
import battle_qa
from tools.models.battle_stride_contacts import audit
from tools.battle_retry_testcase import BattleRetryCase


class BattleStrideCase(BattleRetryCase):
    author_module = 'tools.models.authored_battle'

    def test_stride_contacts_source_motion_and_clock(self):
        if self.sid is None:
            self.skipTest('shared case')
        folder = os.environ.get('BATTLE_RETRY_REVIEW')
        if not folder:
            self.skipTest('needs before/after provider fixtures')
        review = Path(folder)
        sid = self.sid
        slot, = self.changed_slots
        skeleton = json.loads((review / 'main' / f'{sid}-species.json').read_text())['model']['skeleton']
        before, final, reference, prepass = [(review / part / f'{sid}.C.MMD').read_bytes()
                                           for part in ('main', 'final', 'reference', 'prepass')]
        self.assertTrue(audit(final, skeleton, slot)['passed'])
        rows = battle_qa.species_check(final, reference, before, skeleton, [slot], [slot])
        self.assertEqual(rows[slot]['flags'], [])
        for new, old in zip(rows[slot]['final']['cross'], rows[slot]['main']['cross']):
            self.assertLessEqual(new, old)
        nb = len(skeleton)
        old_model, new_model = [mmd.MMD.parse(data, nb) for data in (before, final)]
        old_frames, old_loop, old_events = animsheet.slot_frames(old_model, nb, slot)
        new_frames, loop, events = animsheet.slot_frames(new_model, nb, slot)
        self.assertEqual((len(new_frames), loop), (len(old_frames), old_loop))
        self.assertEqual(loop, 0)
        def content(rows):
            return [(t, kind, {k: v for k, v in payload.items() if k != 'frame'})
                    for t, kind, payload in rows]
        self.assertEqual(content(events), content(old_events))
        author = importlib.import_module(self.author_module).author
        replay = mmd.MMD.parse(author(prepass, skeleton, sid, reference), nb)
        self.assertEqual(animsheet.slot_frames(replay, nb, slot),
                         animsheet.slot_frames(new_model, nb, slot))
