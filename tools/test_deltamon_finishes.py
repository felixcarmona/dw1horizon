"""Guard Deltamon's retained battle finishes and unchanged field motion."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'models'))
from tools.retained_finish_testcase import RetainedFinishCase


class DeltamonFinishes(RetainedFinishCase):
    sid = 292
    slots = (42, 43, 44)


from tools.battle_retry_testcase import BattleRetryCase


class DeltamonRetry(BattleRetryCase):
    sid = 292
    changed_slots = (40, 41, 42)

    def test_victory_contacts_motion_and_replay(self):
        import json
        import os
        from pathlib import Path
        import mmd
        import battle_qa
        from tools.models.battle_finishes import author
        from tools.models.deltamon_contacts import audit
        review = os.environ.get('BATTLE_RETRY_REVIEW')
        if not review:
            self.skipTest('needs before/after provider fixtures')
        review = Path(review)
        skeleton = json.loads((review / 'main/292-species.json').read_text())['model']['skeleton']
        before, final, reference, prepass = [(review / part / '292.C.MMD').read_bytes()
                                           for part in ('main', 'final', 'reference', 'prepass')]
        self.assertTrue(audit(final, skeleton)['passed'])
        rows = battle_qa.species_check(final, reference, before, skeleton, [42], [42])
        self.assertEqual(rows[42]['flags'], [])
        for value, baseline in zip(rows[42]['final']['cross'], rows[42]['main']['cross']):
            self.assertLessEqual(value, baseline)
        import animsheet
        from tools.models.field_animations.native_battle import scaled_events
        old_model, new_model = [mmd.MMD.parse(data, len(skeleton)) for data in (before, final)]
        old_frames, _, old_events = animsheet.slot_frames(old_model, len(skeleton), 42)
        new_frames, loop, actual_events = animsheet.slot_frames(new_model, len(skeleton), 42)
        self.assertIsNone(loop)
        self.assertLessEqual(len(new_frames)-1, 1.6*(len(old_frames)-1))
        def content(events):
            return [(tick, kind, {k: v for k, v in payload.items() if k != 'frame'})
                    for tick, kind, payload in events]
        self.assertEqual(content(actual_events),
                         content(scaled_events(old_events, len(old_frames), len(new_frames))))
        nb = len(skeleton)
        replay, result = [mmd.MMD.parse(data, nb)
                          for data in (author(prepass, skeleton, 292, reference), final)]
        self.assertEqual(replay.anims.anims[replay.anims.table[42]].build(),
                         result.anims.anims[result.anims.table[42]].build())

    def test_source_recoil_retiming(self):
        import os
        import json
        from pathlib import Path
        import animsheet
        import mmd
        import battle_qa_native
        from tools.models.field_animations.native_battle import source_clip
        review = os.environ.get('BATTLE_RETRY_REVIEW')
        if not review:
            self.skipTest('needs before/after provider fixtures')
        review = Path(review)
        before, final = [(review / part / '292.C.MMD').read_bytes() for part in ('main', 'final')]
        source = (review / 'main/292.B.MMD').read_bytes()
        rows = battle_qa_native.check('292', final, source, before, [40, 41])
        for row in rows.values():
            self.assertEqual(row['flags'], [])
            self.assertEqual(row['verdict'], 'pass')
            self.assertLessEqual(row['ticks'] / row['source_ticks'], 1.6)
        nb = len(json.loads((review / 'main/292-species.json').read_text())['model']['skeleton'])
        ns = len(battle_qa_native.source_skeleton('292'))
        model, original = mmd.MMD.parse(final, nb), mmd.MMD.parse(source, ns)
        for slot in (40, 41):
            frames, loop, events = animsheet.slot_frames(model, nb, slot)
            self.assertIsNone(loop)
            _, expected, _, _ = source_clip(original, ns, slot, len(frames))
            self.assertEqual([(t, k) for t, k, _ in events],
                             [(t, k) for t, k, p in expected if k == 'sound' and p['bank'] in (1, 4)])
