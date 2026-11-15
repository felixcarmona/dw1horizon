"""Decoded final-provider regressions for reviewed authored techniques."""
import json
import math
import os
from pathlib import Path
import sys

sys.path[:0] = [str(Path(__file__).resolve().parent / "models")]

from tools.battle_retry_testcase import BattleRetryCase
from tools.models import authored_techniques
from tools.models.battle_stride_contacts import audit, support_band
import animsheet
import battle_qa
import mmd


class BattleTechniqueCase(BattleRetryCase):
    review_env = "BATTLE_TECHNIQUE_REVIEW"

    def test_eased_techniques_match_the_reviewed_keys(self):
        if self.sid is None:
            self.skipTest('shared case')
        folder = os.environ.get(self.review_env)
        if not folder:
            self.skipTest('needs before/after provider fixtures')
        review = Path(folder)
        sid = self.sid
        skeleton = json.loads((review / 'main' / f'{sid}-species.json').read_text())['model']['skeleton']
        blobs = [(review / part / f'{sid}.C.MMD').read_bytes()
                 for part in ('main', 'final', 'reference', 'prepass')]
        before, final, reference, prepass = blobs
        nb = len(skeleton)
        old, new, replay = [mmd.MMD.parse(data, nb) for data in
                            (before, final, authored_techniques.author(prepass, skeleton, sid, reference))]
        for slot, profile in authored_techniques.PROFILES[sid].items():
            with self.subTest(slot=slot):
                original, _, _ = animsheet.slot_frames(old, nb, slot)
                frames, loop, _ = animsheet.slot_frames(new, nb, slot)
                self.assertEqual(loop, None)
                self.assertEqual(len(frames), profile.get('final_frames', math.floor((len(original)-1)*profile['factor'])+1))
                self.assertEqual(animsheet.slot_frames(new, nb, slot),
                                 animsheet.slot_frames(replay, nb, slot))
                self.assertTrue(audit(final, skeleton, slot)['passed'])
                if profile.get('support_feet'):
                    old_support = support_band(before, skeleton, slot, profile['support_feet'])
                    new_support = support_band(final, skeleton, slot, profile['support_feet'])
                    self.assertGreaterEqual(new_support[0], old_support[0])
                    self.assertLessEqual(new_support[1], 3)
                row = battle_qa.species_check(final, reference, before, skeleton, [slot], [slot])[slot]
                self.assertEqual(row['flags'], [])
                for actual, baseline in zip(row['final']['cross'], row['main']['cross']):
                    self.assertLessEqual(actual, baseline)
