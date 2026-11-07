"""Enemy defaults must survive template inheritance and mode-disabled slots."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import enemy_movesets
import species
from dws import backend


class EnemyMovesets(unittest.TestCase):
    def test_story_placements_use_specialty_moves_and_clear_template_weights(self):
        for sid, expected in enemy_movesets.load().items():
            with self.subTest(species=sid):
                for template in ([0, 0, 0, 0], [60, 30, 10, 0], [0, 0, 0, 100]):
                    entry = {f'prio{k}': value for k, value in enumerate(template)}
                    backend.set_moves(entry, sid, None)
                    self.assertEqual(([entry[f'move{k}'] for k in range(4)],
                                      [entry[f'prio{k}'] for k in range(4)]), expected)

    def test_iceleomon_off_retains_three_attacks(self):
        sp = species.load_content(ids={63})[63]
        moves, weights = enemy_movesets.load()[63]
        off = sp['off']['techniques']
        self.assertEqual(sum(bool(w) and slot - 46 < len(off) for slot, w in zip(moves, weights)), 3)

    def test_misspelled_move_and_invalid_weights_fail(self):
        for row in ({'moves': ['Ice Statue typo', None, None, None], 'weights': [90, 10, 0, 0]},
                    {'moves': ['Ice Statue', None, None, None], 'weights': [0, 0, 0, 0]},
                    {'moves': ['War Cry', None, None, None], 'weights': [90, 10, 0, 0]}):
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / 'profiles.json'
                path.write_text(json.dumps({'100': row}))
                with self.assertRaises(ValueError):
                    enemy_movesets.load(path=path)


if __name__ == '__main__':
    unittest.main()
