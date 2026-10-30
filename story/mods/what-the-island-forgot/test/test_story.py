#!/usr/bin/env python3
"""Calendar regressions for the authored What the island forgot story, without an emulator."""
import ast
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest


class Counter:
    def __init__(self, value=0): self.value = value
    def __eq__(self, other): return self.value == other
    def __lt__(self, other): return self.value < other
    def __le__(self, other): return self.value <= other
    def __ge__(self, other): return self.value >= other
    def set(self, value=True): self.value = value.value if isinstance(value, Counter) else value
    def add(self, value): self.value += value
    def sub(self, value): self.value -= value
    def clear(self): self.value = 0


class Closed(Exception): pass


class WhamonWait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[4] / 'story/mods/what-the-island-forgot/arcs/shore/city-dock.py'
        tree = ast.parse(path.read_text())
        funcs = [copy.deepcopy(n) for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name in ('elapsed_days', 'chasing', 'resting')]
        for fn in funcs: fn.decorator_list = []
        cls.code = compile(ast.Module(body=funcs, type_ignores=[]), str(path), 'exec')

    def handlers(self, departure, year):
        def closed(): raise Closed()
        scratch = {n: Counter() for n in (90, 91, 92)}
        env = dict(clock=SimpleNamespace(day=departure, year=(year-1) % 100),
                   whamon_left_day=Counter(departure), whamon_left_year=Counter(year),
                   whamon_hurt=Counter(1), away=closed, hurt=closed, pstat=scratch.__getitem__)
        exec(self.code, env)
        return env

    def test_delayed_first_visit_and_year_rollover(self):
        for handler, days in [('chasing', 5), ('resting', 10)]:
            for year in (0, 1, 42, 98, 99):
                for departure in range(30):
                    for elapsed in (0, days-1, days, 29, 30, 31, 59, 60, 2999):
                        env = self.handlers(departure, year+1)
                        env['clock'].day = (departure+elapsed) % 30
                        env['clock'].year = (year+(departure+elapsed)//30) % 100
                        with self.subTest(handler=handler, year=year, departure=departure, elapsed=elapsed):
                            if elapsed < days:
                                with self.assertRaises(Closed): env[handler]()
                            else:
                                env[handler]()
                                self.assertEqual(env['whamon_left_day'].value, 255)
                                if handler == 'resting': self.assertEqual(env['whamon_hurt'].value, 0)

    def test_completed_wait_stays_open(self):
        for departure in range(30):
            env = self.handlers(departure, 1)
            for elapsed in range(65):
                env['clock'].day = (departure+elapsed) % 30
                env['clock'].year = (departure+elapsed) // 30
                if elapsed < 5:
                    with self.assertRaises(Closed): env['chasing']()
                else: env['chasing']()

    def test_old_saves_have_no_invented_departure_year(self):
        for handler in ('chasing', 'resting'):
            for departure in range(30):
                for year in (0, 1, 99):
                    env = self.handlers(departure, 0)
                    env['clock'].year = year
                    env[handler]()
                    self.assertEqual(env['whamon_left_day'].value, 255)
                    if handler == 'resting': self.assertEqual(env['whamon_hurt'].value, 0)

    def test_both_departures_store_year_plus_one(self):
        root = Path(__file__).resolve().parents[4] / 'story/mods/what-the-island-forgot/arcs/shore'
        for name, handler in [('city-dock.py', 'after_him'), ('sea-ambush.py', 'the_first_crossing')]:
            tree = ast.parse((root/name).read_text())
            # Check the actual timestamp writes, including the ambush's loss branch.
            calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                     and isinstance(n.func.value, ast.Name) and n.func.value.id == 'whamon_left_year']
            self.assertEqual([(c.func.attr, ast.unparse(c.args[0])) for c in calls],
                             [('set', 'clock.year'), ('add', '1')], name)


if __name__ == '__main__':
    unittest.main()
