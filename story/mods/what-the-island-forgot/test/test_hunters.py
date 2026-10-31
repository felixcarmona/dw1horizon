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




class HunterFirstSighting(unittest.TestCase):
    def handlers(self):
        root = Path(__file__).resolve().parents[4] / 'story/mods/what-the-island-forgot/arcs/rumours'
        handlers = {}
        for name in ('hunters-forest.py', 'hunters-savanna.py'):
            tree = ast.parse((root / name).read_text())
            handlers[name] = {}
            for func in ('remember_hunter', 'first_sighting'):
                fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == func)
                guard = next(k.value for k in fn.decorator_list[0].keywords if k.arg == 'when')
                fn.decorator_list = []
                handlers[name][func] = (compile(ast.Expression(guard), name, 'eval'),
                                       compile(ast.Module(body=[fn], type_ignores=[]), name, 'exec'))
        return handlers

    def environment(self, hour, spread):
        class Flag:
            value = False
            def __bool__(self): return self.value
            def set(self): self.value = True
        class Byte:
            value = 0
            def set(self, n): self.value = n
            def __eq__(self, n): return self.value == n
        seen, byte, lines = Flag(), Byte(), []
        env = dict(clock=SimpleNamespace(hour=hour), rumours_spread=spread,
                   hunter_noticed=seen, tamer=SimpleNamespace(say=lines.append),
                   HUNTER_PRESENT_PSTAT=120, pstat=lambda n: byte)
        return env, lines

    def run_handler(self, handler, func, env):
        guard, code = handler[func]
        exec(code, env)
        if eval(guard, env): env[func]()

    def test_shared_once_flag_and_clock(self):
        handlers = self.handlers()
        for first in handlers:
            second = next(n for n in handlers if n != first)
            for spread in (False, True):
                for hour in range(24):
                    env, lines = self.environment(hour, spread)
                    for name in (first, first, second):
                        self.run_handler(handlers[name], 'remember_hunter', env)
                        self.run_handler(handlers[name], 'first_sighting', env)
                    night = hour >= 20 or hour < 5
                    with self.subTest(first=first, rumours=spread, hour=hour):
                        self.assertEqual(lines, ["That Gururumon isn't from around here... Is it looking for me?"]
                                         if spread and night else [])
                        self.assertEqual(bool(env['hunter_noticed']), spread and night)

    def test_waiting_until_night_does_not_invent_a_hunter(self):
        for name, handler in self.handlers().items():
            env, lines = self.environment(12, True)
            self.run_handler(handler, 'remember_hunter', env)
            env['clock'].hour = 22
            self.run_handler(handler, 'first_sighting', env)
            with self.subTest(source=name):
                self.assertEqual(lines, [])
                self.assertFalse(env['hunter_noticed'])


if __name__ == '__main__': unittest.main()
