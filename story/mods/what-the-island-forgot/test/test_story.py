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
                 and n.name in ('after_him', 'elapsed_days', 'chasing', 'resting', 'city_ferry_presence', 'return_to_dock')]
        sea = ast.parse(path.with_name('sea-ambush.py').read_text())
        funcs += [copy.deepcopy(n) for n in sea.body if isinstance(n, ast.FunctionDef)
                  and n.name in ('factory_ferry_presence', 'factory_ferry_closed')]
        for fn in funcs: fn.decorator_list = []
        cls.code = compile(ast.Module(body=funcs, type_ignores=[]), str(path), 'exec')

    def handlers(self, departure, year):
        def closed(): raise Closed()
        scratch = {n: Counter() for n in (90, 91, 92, 120)}
        env = dict(clock=SimpleNamespace(day=departure, year=(year-1) % 100),
                   whamon_left_day=Counter(departure), whamon_left_year=Counter(year),
                   whamon_hurt=Counter(1), away=closed, hurt=closed, pstat=scratch.__getitem__,
                   WHAMON_HIDDEN_PSTAT=120, recruited=lambda species: True,
                   Species=SimpleNamespace(Whamon=24, Whamon146=146))
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

    def test_return_restores_only_the_removed_instance(self):
        for handler, days in [('chasing', 5), ('resting', 10)]:
            for reload in (False, True):
                for departure in (0, 26, 29):
                    with self.subTest(handler=handler, reload=reload, departure=departure):
                        env = self.handlers(departure, 100)
                        env['recruited'] = lambda species: True
                        env['Species'] = SimpleNamespace(Whamon=24, Whamon146=146)
                        env['seadramon_chased'] = Counter(handler == 'chasing')
                        env['whamon_hurt'].set(handler == 'resting')
                        present, spawns = [True], []
                        def leave():
                            self.assertTrue(present[0], 'removed an absent entity')
                            present[0] = False
                        def spawn(species, *, slot):
                            self.assertFalse(present[0], 'spawned an existing entity')
                            self.assertEqual((species, slot), (146, 7))
                            present[0] = True
                            spawns.append(slot)
                        env['whamon'] = SimpleNamespace(leave=leave)
                        env['spawn'] = spawn
                        env['city_ferry_presence']()
                        self.assertFalse(present[0])
                        with self.assertRaises(Closed): env[handler]()
                        env['clock'].day = (departure + days) % 30
                        env['clock'].year = (99 + (departure + days) // 30) % 100
                        if reload:
                            present[0] = True  # the normal MAPHEAD setup
                            env['city_ferry_presence']()
                        env[handler]()
                        self.assertTrue(present[0])
                        self.assertEqual(len(spawns), 0 if reload else 1)
                        env[handler]()
                        self.assertEqual(len(spawns), 0 if reload else 1, 'repeated trigger spawned twice')

    def test_each_square_layout_has_the_return_slot(self):
        root = Path(__file__).resolve().parents[4]
        for screen in range(168, 180):
            presence = (root / f'story/base/city/presence/s{screen}.dws').read_text()
            self.assertIn('npc 146 slot 7 when r7;', presence)

    def test_departure_on_this_visit_is_remembered(self):
        env = self.handlers(4, 43)
        env['clock'].year = 42
        env['to_the_dock'] = lambda: None
        env['seadramon_chased'] = Counter()
        env['whamon'] = SimpleNamespace(say=lambda *args: None, ask=lambda **kw: True, leave=lambda: None)
        with self.assertRaises(Closed): env['after_him']()
        spawned = []
        env['spawn'] = lambda species, **kw: spawned.append((species, kw['slot']))
        env['clock'].day = 9
        env['chasing']()
        self.assertEqual(spawned, [(146, 7)])

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


class Byte(Counter):
    """An engine pstat: 0-255, saturating (REDUCE_PSTAT stops at 0)."""
    def add(self, value): self.value = min(255, self.value + value)
    def sub(self, value): self.value = max(0, self.value - value)


class TuskmonDeal(unittest.TestCase):
    """The Monochrome Shop's deal of the day (arcs/canyon/monochrome-shop.py), run on its own Python with the engine mocked."""
    PATH = Path(__file__).resolve().parents[1] / 'arcs/canyon/monochrome-shop.py'

    @classmethod
    def setUpClass(cls):
        tree = ast.parse(cls.PATH.read_text())
        keep = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name not in ('talk', 'counter', 'conversation')
                or isinstance(n, ast.Assign) and all(isinstance(t, ast.Name) and t.id.isupper() for t in n.targets)]
        for fn in keep:
            if isinstance(fn, ast.FunctionDef): fn.decorator_list = []
        cls.code = compile(ast.Module(body=keep, type_ignores=[]), str(cls.PATH), 'exec')
        cls.tree = tree

    def env(self, day=0, stored_day=0, step=0, item=6, bits=5000, roll=0, chance=True, bag_full=False):
        said, given, taken, menu, bubbles = [], [], [], [], []
        npc = SimpleNamespace(say=lambda *a: said.append(a[0]),
                              choose=lambda **o: menu.append(sorted(o)) or menu_pick[0],
                              ask=lambda **o: menu.append(sorted(o)) or menu_pick[0] == 'buy')
        menu_pick = ['leave']
        items = SimpleNamespace(LargeMP=6, Omnipotent=9, HealthShoe=37, Digicatfish=66)
        pstats = {n: Byte() for n in (88, 89, 93, 247, 248)}
        env = dict(clock=SimpleNamespace(day=day), deal_day=Counter(stored_day), deal_item=Counter(item),
                   deal_step=Counter(step), pstat=pstats.__getitem__,
                   random=SimpleNamespace(roll=lambda n: roll, chance=lambda p: chance),
                   tuskmon=npc, narrator=npc, Item=items, bits=bits, trigger=lambda n: bag_full,
                   give=lambda what: given.append(what), take=lambda bits: taken.append(bits),
                   call=lambda r: bubbles.append((pstats[247].value, pstats[248].value)), wait=lambda ms: None, Routine=SimpleNamespace(monochromon_mood_bubble=28),
                   dws=self.ends)
        exec(self.code, env)
        deal = env['deal']
        def run():                  # dws("return;") ends the whole talk, as the shared block does in the game
            try: deal()
            except Closed: pass
        env['deal'] = run
        return env, SimpleNamespace(said=said, given=given, taken=taken, menu=menu, pick=menu_pick, bubbles=bubbles)

    @staticmethod
    def ends(code):
        assert code == 'return;', code
        raise Closed()

    def test_today_is_the_stored_day_only(self):
        for stored in range(32):
            for day in range(30):
                env, _ = self.env(day=day, stored_day=stored)
                env['deal_is_today']()
                with self.subTest(stored=stored, day=day):
                    self.assertEqual(env["pstat"](88).value, int(stored == day + 1))

    def test_a_new_day_rolls_a_new_deal(self):
        for roll, item in enumerate((6, 9, 37, 66)):
            env, out = self.env(day=7, stored_day=3, step=4, roll=roll)
            env['deal']()
            self.assertEqual((env['deal_day'].value, env['deal_step'].value, env['deal_item'].value), (8, 0, item))
            self.assertEqual(env['pstat'](93).value, item)          # {item 93} names it
        env, out = self.env(day=7, stored_day=8, step=4, item=9)    # the same day: kept, and sold
        env['deal']()
        self.assertEqual((env['deal_step'].value, env['deal_item'].value, out.menu), (4, 9, []))

    def test_haggle_wins_twice_then_only_buy_or_leave(self):
        env, out = self.env(day=0, stored_day=1)
        out.pick[0] = 'haggle'
        env['deal'](); env['deal']()
        self.assertEqual(env['deal_step'].value, 2)
        env['deal']()
        self.assertEqual(out.menu[-1], ['no', 'yes'])              # no third haggle
        self.assertEqual(env['deal_step'].value, 2)

    def test_a_lost_haggle_closes_the_deal_until_tomorrow(self):
        for step in (0, 1):
            env, out = self.env(day=0, stored_day=1, step=step, chance=False)
            out.pick[0] = 'haggle'
            env['deal']()
            self.assertEqual(env['deal_step'].value, 3)
            self.assertEqual(out.bubbles, [(10, 3), (10, 5)])            # the angry face over Tuskmon, then taken away
            out.menu.clear(); env['deal']()
            self.assertEqual((out.menu, out.taken), ([], []))
            out.pick[0] = 'leave'; env['clock'].day = 1; env['deal']()
            self.assertEqual(env['deal_step'].value, 0)

    def test_buying_pays_the_current_price(self):
        for step, price in ((0, 2500), (1, 2150), (2, 1800)):
            env, out = self.env(day=0, stored_day=1, step=step, item=37)
            out.pick[0] = 'buy'
            env['deal']()
            self.assertEqual((out.taken, out.given, env['deal_step'].value), ([price], [37], 4))

    def test_no_bits_or_no_room_takes_nothing(self):
        for kw in (dict(bits=2499), dict(bag_full=True)):
            env, out = self.env(day=0, stored_day=1, **kw)
            out.pick[0] = 'buy'
            env['deal']()
            self.assertEqual((out.taken, env['deal_step'].value), ([], 0), kw)

    def test_prices_stay_above_what_the_items_sell_for(self):
        import json
        root = Path(__file__).resolve().parents[4]
        items = {json.loads(p.read_text())['id']: json.loads(p.read_text()) for p in (root / 'content/items').glob('*.json')}
        sell = json.loads((root / 'content/tables/economy.json').read_text())['economy']['shop']['sellPercent']
        prices = [k.value.value for n in ast.walk(self.tree) if isinstance(n, ast.Call)
                  and isinstance(n.func, ast.Name) and n.func.id == 'take' for k in n.keywords if k.arg == 'bits']
        self.assertEqual(sorted(prices), [1800, 2150, 2500])
        for item in (6, 9, 37, 66):
            self.assertEqual(items[item]['value'], 2000)
            self.assertGreater(min(prices), items[item]['value'] * sell // 100)


if __name__ == '__main__':
    unittest.main()
