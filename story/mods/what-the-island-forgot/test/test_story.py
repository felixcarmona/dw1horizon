#!/usr/bin/env python3
"""Calendar regressions for the authored What the island forgot story, without an emulator."""
import ast
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest


class Counter:
    def __init__(self, value=0): self.value = value
    def __bool__(self): return bool(self.value)
    def __eq__(self, other): return self.value == other
    def __lt__(self, other): return self.value < other
    def __le__(self, other): return self.value <= other
    def __ge__(self, other): return self.value >= other
    def set(self, value=True): self.value = value.value if isinstance(value, Counter) else value
    def add(self, value): self.value += value
    def sub(self, value): self.value -= value
    def clear(self): self.value = 0


class Closed(Exception): pass


class DrownedShore(unittest.TestCase):
    """Screen 309 has one way out, Whamon: the arrival stays outside its body box, and the chest stays reachable."""
    def test_arrival_and_chest(self):
        import json, re, sys
        from collections import deque
        root = Path(__file__).resolve().parents[4]
        sys.path.insert(0, str(root / 'tools' / 'maps'))
        import reach
        data = json.loads((root / 'story/mods/what-the-island-forgot/maps/drowned-shore-data.json').read_text())
        script = (root / 'story/mods/what-the-island-forgot/arcs/shore/drowned-shore.py').read_text()
        self.assertIn('autotalk=False', script)
        wx, wz = map(int, re.search(r'shore\.npc\(.*at=\((-?\d+), (-?\d+)\)', script).groups())
        ax, az = data['warps'][0]['x'], data['warps'][0]['z']
        self.assertFalse(abs(ax - wx) < 300 and abs(az - wz) < 300, 'the arrival is inside Whamon')     # radius 200 + tamer 100
        cx, cz, facing = map(int, re.search(r'spawn_chest\(.*at=\((-?\d+), (-?\d+)\).*facing=(\d+)', script).groups())
        tx, tz = reach.col(cx), reach.row(cz)
        grid = type('Grid', (), {'collision': list(data['collision'])})()
        for r in range(tz - 2, tz + 2):
            for c in range(tx - 2, tx + 2): grid.collision[r * 100 + c] = 0x80       # setImpassableSquare(tile, 2)
        ox, oz = {0: (0, 4), 2048: (0, -4), 1024: (-4, 0), 3072: (4, 0)}[facing]
        seen = {(ax // 10 * 10, az // 10 * 10)}; queue = deque(seen); opens = False
        while queue and not opens:
            x, z = queue.popleft()
            opens = abs(reach.col(x) - tx - ox) <= 1 and abs(reach.row(z) - tz - oz) <= 1
            for d in (1, -1):
                if reach.can_x(grid, x, z, d, 100) and (x + d * 10, z) not in seen: seen.add((x + d * 10, z)); queue.append((x + d * 10, z))
                if reach.can_z(grid, x, z, d, 100) and (x, z + d * 10) not in seen: seen.add((x, z + d * 10)); queue.append((x, z + d * 10))
        self.assertTrue(opens, 'no walkable tile opens the chest')


class WhamonWait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[4] / 'story/mods/what-the-island-forgot/arcs/shore/city-dock.py'
        tree = ast.parse(path.read_text())
        funcs = [copy.deepcopy(n) for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name in ('elapsed_days', 'chasing', 'resting', 'city_ferry_presence')]
        sea = ast.parse(path.with_name('sea-ambush.py').read_text())
        funcs += [copy.deepcopy(n) for n in sea.body if isinstance(n, ast.FunctionDef)
                  and n.name in ('factory_ferry_presence', 'factory_ferry_closed')]
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

    def test_dock_visibility_uses_the_same_wait_after_reentry(self):
        for handler in ('city_ferry_presence', 'factory_ferry_presence'):
            for chased, hurt, days in [(0, 0, 0), (1, 0, 5), (0, 1, 10), (1, 1, 10)]:
                for year in (0, 42, 99):
                    for departure in range(30):
                        for elapsed in (0, 4, 5, 9, 10, 30, 60):
                            env = self.handlers(departure, year + 1)
                            env['seadramon_chased'] = Counter(chased)
                            env['whamon_hurt'].set(hurt)
                            env['clock'].day = (departure + elapsed) % 30
                            env['clock'].year = (year + (departure + elapsed) // 30) % 100
                            left = []
                            env['whamon'] = SimpleNamespace(leave=lambda: left.append(True))
                            with self.subTest(handler=handler, chased=chased, hurt=hurt, year=year,
                                              departure=departure, elapsed=elapsed):
                                env[handler]()
                                self.assertEqual(bool(left), elapsed < days)
                                # Reentry does not start a new wait or consume the departure date.
                                self.assertEqual(env['whamon_left_day'].value, departure)
                                self.assertEqual(env['whamon_left_year'].value, year + 1)
                                env['whamon_left_year'].set(0)
                                left.clear()
                                env[handler]()
                                self.assertFalse(left, 'undated old saves must remain open')

    def test_both_docks_keep_the_same_calendar_calculation(self):
        root = Path(__file__).resolve().parents[4] / 'story/mods/what-the-island-forgot/arcs/shore'
        helpers = []
        for name in ('city-dock.py', 'sea-ambush.py'):
            tree = ast.parse((root / name).read_text())
            helpers.append(next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'elapsed_days'))
        self.assertEqual(ast.dump(helpers[0]), ast.dump(helpers[1]))

    def test_factory_use_tile_cannot_offer_an_invisible_ferry(self):
        for chased, hurt, days in [(0, 0, 0), (1, 0, 5), (0, 1, 10), (1, 1, 10)]:
            for departure in range(30):
                for elapsed in (0, 4, 5, 9, 10, 30, 60):
                    env = self.handlers(departure, 100)
                    env['seadramon_chased'] = Counter(chased)
                    env['whamon_hurt'].set(hurt)
                    env['clock'].day = (departure + elapsed) % 30
                    env['clock'].year = (99 + (departure + elapsed) // 30) % 100
                    lines = []
                    env['tamer'] = SimpleNamespace(say=lines.append)
                    def end_section(code):
                        self.assertEqual(code, 'return;')
                        raise Closed()
                    env['dws'] = end_section
                    with self.subTest(chased=chased, hurt=hurt, departure=departure, elapsed=elapsed):
                        if elapsed < days:
                            with self.assertRaises(Closed): env['factory_ferry_closed']()
                            self.assertIn('resting' if hurt else 'chasing', lines[0])
                        else:
                            env['factory_ferry_closed']()
                            self.assertFalse(lines)


if __name__ == '__main__':
    unittest.main()
