"""Sorcermon casting while its new stride stays unchanged."""
from tools.battle_technique_testcase import BattleTechniqueCase


class SorcermonTechniques(BattleTechniqueCase):
    sid = 242
    changed_slots = (35, 55)

    def test_the_reviewed_walk_stays_unchanged(self):
        import json
        import os
        from pathlib import Path
        import animsheet
        import mmd
        if not (os.environ.get('BATTLE_RETRY_REVIEW') and os.environ.get('BATTLE_TECHNIQUE_REVIEW')):
            self.skipTest('needs before/after provider fixtures')
        previous = Path(os.environ['BATTLE_RETRY_REVIEW']) / 'final'
        current = Path(os.environ['BATTLE_TECHNIQUE_REVIEW']) / 'final'
        skeleton = json.loads((current / '242-species.json').read_text())['model']['skeleton']
        models = [mmd.MMD.parse((folder / '242.C.MMD').read_bytes(), len(skeleton))
                  for folder in (previous, current)]
        self.assertEqual(animsheet.slot_frames(models[0], len(skeleton), 35),
                         animsheet.slot_frames(models[1], len(skeleton), 35))
