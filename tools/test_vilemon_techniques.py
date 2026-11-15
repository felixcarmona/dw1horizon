"""Vilemon's restored source strike and unchanged field/care programs."""
import json
import os
from pathlib import Path
import sys

sys.path[:0] = [str(Path(__file__).resolve().parent / 'models')]
from tools.battle_retry_testcase import BattleRetryCase
import animsheet
import battle_qa_native as native
import mmd


class VilemonTechniques(BattleRetryCase):
    sid = 295
    changed_slots = (55,)
    review_env = 'BATTLE_TECHNIQUE_REVIEW'

    def test_source_strike_keeps_its_motion_and_sound_cues(self):
        folder = os.environ.get(self.review_env)
        if not folder:
            self.skipTest('needs provider fixtures')
        review = Path(folder)
        before, final = [(review / part / '295.C.MMD').read_bytes() for part in ('main', 'final')]
        source = (review / 'source/295.B.MMD').read_bytes()
        row = native.check('295', final, source, before, [55])[55]
        self.assertEqual(row['flags'], [])
        self.assertEqual(row['ticks'], 61)
        self.assertLessEqual(max(row['ticks']/row['source_ticks'], row['source_ticks']/row['ticks']), 1.6)
        skeleton = json.loads((review / 'final/295-species.json').read_text())['model']['skeleton']
        models = [mmd.MMD.parse(data, len(skeleton)) for data in (before, final)]
        events = [animsheet.slot_frames(model, len(skeleton), 55)[2] for model in models]
        def cues(rows):
            return [(kind, {k: v for k, v in payload.items() if k != 'frame'})
                    for _, kind, payload in rows]
        self.assertEqual(cues(events[0]), cues(events[1]))
