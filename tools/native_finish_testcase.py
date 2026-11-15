"""Final-provider fidelity and exact untouched programs for restored native finishes."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools'), str(ROOT / 'tools/models')]
import animsheet
import mmd
import battle_qa_native
from tools.models.field_animations import native_battle
from tools.retained_finish_testcase import RetainedFinishCase


class NativeFinishCase(RetainedFinishCase):
    changed_slots = (42,)

    def test_source_victory_and_clock(self):
        if self.sid is None:
            self.skipTest('shared case')
        review = Path(os.environ.get('FINISH_REVIEW', ROOT / 'build/battle-finishes'))
        paths = [review / part / f'{self.sid}{suffix}' for part, suffix in
                 [('main', '.C.MMD'), ('final', '.C.MMD'), ('reference', '.B.MMD')]]
        if not all(p.is_file() for p in paths):
            self.skipTest('needs reconstructed provider models and importer output')
        main, final, source = [p.read_bytes() for p in paths]
        rows = battle_qa_native.check(str(self.sid), final, source, main, self.changed_slots)
        for slot, row in rows.items():
            self.assertEqual(row['verdict'], 'pass', row['flags'])
            self.assertEqual(row['flags'], [])
        nb = len(json.loads((review / 'main' / f'{self.sid}-species.json').read_text())['model']['skeleton'])
        ns = len(battle_qa_native.source_skeleton(self.sid))
        original, result = mmd.MMD.parse(source, ns), mmd.MMD.parse(final, nb)
        for slot in self.changed_slots:
            poses, loop, events = animsheet.slot_frames(result, nb, slot)
            _, expected, _, _ = native_battle.source_clip(original, ns, slot, len(poses))
            expected = [(t, k) for t, k, p in expected if k == 'sound' and p['bank'] in (1, 4)]
            self.assertIsNone(loop)
            self.assertEqual([(t, k) for t, k, _ in events], expected)
