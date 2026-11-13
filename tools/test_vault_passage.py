"""The statue room's band (97, step 1) is the only way on to the rest of the Ice Sanctuary (BlueMeramon, the gym):
the descent to the Vault may be offered, but never again once answered, or the Sanctuary is lost behind it."""
import ast
from pathlib import Path
import unittest

ARCS = Path(__file__).resolve().parent.parent / 'story/mods/what-the-island-forgot/arcs/vault'


def step1_handlers():
    tree = ast.parse((ARCS / 'statue-room.py').read_text())
    out = {}
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef):
            for dec in fn.decorator_list:
                if isinstance(dec, ast.Call) and ast.unparse(dec.func) == 'sanctuary.on_step' \
                        and ast.unparse(dec.args[0]) == '1':
                    when = next((ast.unparse(k.value) for k in dec.keywords if k.arg == 'when'), 'True')
                    out[fn.name] = (when, ast.unparse(fn))
    return out


class VaultPassage(unittest.TestCase):
    def test_descent_is_offered_once_and_leaves_the_way_open(self):
        h = step1_handlers()
        when, body = h['the_voice_below']
        self.assertIn('not vault_kept', when)
        self.assertNotIn('vault_kept.clear', body, 'asking again on every crossing closes the Sanctuary')

    def test_melted_wall_lets_the_tamer_pass_after_the_thaw(self):
        when, _ = step1_handlers()['to_the_door']
        self.assertIn('not thaw_told', when)

    def test_declining_at_the_wall_records_the_answer(self):
        self.assertIn('vault_kept.set()', (ARCS / 'wall-of-hearts.py').read_text())


if __name__ == '__main__':
    unittest.main()
