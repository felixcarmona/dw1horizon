"""The healthy sewer conversation must still unlock the original factory inquiry."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

from test_story import Counter

ROOT = Path(__file__).resolve().parents[4]


class Dummy:
    def __getattr__(self, name): return self
    def __call__(self, *args, **kwargs): pass


def handler(path, name, env, decorator=None):
    tree = ast.parse((ROOT / path).read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name
              and (decorator is None or ast.unparse(n.decorator_list[0]).startswith(decorator)))
    fn.decorator_list = []
    exec(compile(ast.Module(body=[fn], type_ignores=[]), path, 'exec'), env)
    return env[name]


class Factory(unittest.TestCase):
    def test_clean_sewer_reaches_andromons_refusal(self):
        # Run the authored talk, then the unchanged base guard and Andromon
        # handlers. No saved progression flags are supplied by the test.
        env = {name: Counter() for name in (
            'sewer_numemon_met', 'guard_shift_change_heard', 'factory_check_refused',
            'factory_permit_required', 'island_history_read', 'factorial_town_reopened',
            'factory_giromon_beaten', 'factory_shut_down')}
        dummy = Dummy()
        env.update(tamer=dummy, partner=dummy, guardromon6=dummy, t5=dummy, t11=dummy,
                   say=dummy, sound=dummy, wait=dummy, anim=dummy,
                   clock=SimpleNamespace(hour=10, minute=0), recruited=lambda _: False,
                   Species=dummy, trigger=lambda _: False)
        healthy = handler('story/mods/what-the-island-forgot/arcs/factory/sewer-numemon.py', 'feeling_fine', env)
        guard = handler('story/base/zones/factorial-town/s149-155/script.py', 'talk', env, 'guardromon6.')
        andromon = handler('story/base/zones/factorial-town/s151-157/script.py', 'talk', env)
        healthy()
        self.assertTrue(env['sewer_numemon_met'])
        guard()
        self.assertTrue(env['factory_permit_required'])
        andromon()
        self.assertTrue(env['factory_check_refused'])


if __name__ == '__main__': unittest.main()
