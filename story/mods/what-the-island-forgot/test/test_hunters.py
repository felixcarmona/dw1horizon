"""Never remove the rumour hunter when its clock-gated setup did not spawn it."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


class HunterLifetime(unittest.TestCase):
    def test_day_arrival_leaves_no_dangling_removal(self):
        root = Path(__file__).resolve().parents[4]/'story/mods/what-the-island-forgot/arcs/rumours'
        for name in ('hunters-forest.py', 'hunters-savanna.py'):
            tree = ast.parse((root/name).read_text())
            fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'not_heard')
            fn.decorator_list = []
            code = compile(ast.Module(body=[fn], type_ignores=[]), str(root/name), 'exec')
            for hour in range(24):
                calls = []
                env = dict(clock=SimpleNamespace(hour=hour), hunter=SimpleNamespace(leave=lambda: calls.append('leave')))
                exec(code, env)
                env['not_heard']()
                with self.subTest(source=name, hour=hour):
                    self.assertEqual(calls, ['leave'] if hour >= 20 or hour < 5 else [])


if __name__ == '__main__': unittest.main()
