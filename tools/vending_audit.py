"""Exercise authored vending handlers with every menu path and every random roll.

The Python view is executable with a small stand-in for the story API. Prices, stock,
prizes and odds come from that source, so changing a script cannot leave a separate
price table green. This is an economy check, not an emulator or bytecode verifier.
"""
import ast
from collections import Counter
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
MACHINES = {9: 'Dragon Eye Lake', 78: 'Ancient Glacial Region',
            71: 'Gear Savanna', 12: 'Tropical Jungle'}
DAILY_FLAGS = {'vending_happy_sold': 798, 'vending_ice_sold': 799}


@lru_cache(maxsize=1)
def item_ids():
    tree = ast.parse((ROOT / 'typings/dw/__init__.pyi').read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Item')
    return {n.targets[0].id: ast.literal_eval(n.value) for n in cls.body if isinstance(n, ast.Assign)}


class NeedChoice(Exception):
    def __init__(self, options):
        self.options = options


class Flag:
    def __init__(self, flags, ident):
        self.flags, self.ident = flags, ident

    def __bool__(self):
        return self.ident in self.flags

    def set(self):
        self.flags.add(self.ident)


@lru_cache(maxsize=16)
def handler(source):
    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'use1')
    fn.decorator_list = []
    program = compile(ast.Module(body=[fn], type_ignores=[]), '<vending>', 'exec')
    attrs = tuple(n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)
                  and isinstance(n.value, ast.Name) and n.value.id == 't81')
    return program, attrs


def run_handler(source, choices, roll, money=999999, full=False, flags=()):
    """One transaction; returns paid bits, received items, saved flags and menu sizes."""
    program, attrs = handler(source)
    queue = iter(choices)
    stock, received, sizes, spent = set(flags), Counter(), [], 0
    engine = SimpleNamespace(item_did_not_fit=False)
    for name, ident in DAILY_FLAGS.items():
        setattr(engine, name, Flag(stock, ident))

    def choose(**options):
        sizes.append(len(options))
        try:
            return next(queue)
        except StopIteration:
            raise NeedChoice(tuple(options)) from None

    def give(item, amount=1):
        engine.item_did_not_fit = full
        if not full:
            received[item] += amount

    def take(*args, bits=0):
        nonlocal spent
        if args:
            raise ValueError('unmodelled vending item payment')
        spent += bits
        env['bits'] -= bits

    null = SimpleNamespace(say=lambda *a: None, turn=lambda *a: None)
    keys = SimpleNamespace(**{name: name for name in attrs})
    env = dict(Item=SimpleNamespace(**item_ids()), engine=engine, bits=money, give=give,
               take=take, choose=choose, ask=lambda **kw: choose(**kw) == 'yes',
               narrator=null, tamer=null, t81=keys,
               random=SimpleNamespace(roll=lambda bound: roll),
               trigger=lambda ident: Flag(stock, ident))
    exec(program, env)
    env['use1']()
    return spent, received, stock, sizes


def menu_paths(source):
    pending, done = [()], []
    while pending:
        path = pending.pop()
        try:
            run_handler(source, path, 99)
            done.append(path)
        except NeedChoice as choice:
            # Each machine has at most two pages. A Back revisits the same first page;
            # test a purchase after Back as well, then stop expanding that cycle.
            if len(path) < 4:
                pending.extend(path + (key,) for key in (*choice.options, 'cancel'))
    return done


def check_vending(worth, names, sources=None, log=print):
    fails, sold = [], set()
    for sid, caption in MACHINES.items():
        path = next((ROOT / 'story/base/zones').glob(f'*/s{sid:03d}-*/script.py'))
        source = sources[sid] if sources and sid in sources else path.read_text()
        unique = set()
        for menu in menu_paths(source):
            outcomes = [run_handler(source, menu, roll) for roll in range(100)]
            prices = {o[0] for o in outcomes}
            if len(prices) != 1:
                fails.append(f'{caption}: random price or unpaid prize')
                continue
            price = prices.pop()
            if not price:
                if any(o[1] for o in outcomes):
                    fails.append(f'{caption}: free payout')
                continue
            signature = tuple((o[0], tuple(sorted(o[1].items())), tuple(sorted(o[2]))) for o in outcomes)
            if signature in unique:
                continue
            unique.add(signature)
            value = sum(sum(worth[i] * count for i, count in o[1].items()) for o in outcomes) / 100
            stock = set.union(*(o[2] for o in outcomes))
            awarded = set.union(*(set(o[1]) for o in outcomes))
            sold.update(awarded)
            label = ', '.join(names[i] for i in sorted(awarded))
            log(f'{caption}: {label}: {price} bits -> {float(value):.2f} best exit value'
                + (' (daily)' if stock else ''))
            if value >= price:
                fails.append(f'{caption}: {price} -> {float(value):.2f}')
            # Each fixed-price item must also beat its individual best conversion exit.
            if sid != 12 and any(worth[i] >= price for i in awarded if i != 7):
                fails.append(f'{caption}: item can be converted for its price or more')
            if sid == 9:
                primary = next(iter(outcomes[0][1]))
                expected = {69: {798}, 45: {799}, 44: set()}[primary]
                if stock != expected:
                    fails.append(f'{caption}: wrong daily stock flag for {names[primary]}')
                if stock:
                    again = run_handler(source, menu, 99, flags=stock)
                    if again[0] or again[1]:
                        fails.append(f'{caption}: daily stock can be bought twice')
            for budget, full in ((price - 1, False), (999999, True)):
                for roll in range(100):
                    failure = run_handler(source, menu, roll, money=budget, full=full)
                    if (failure[0] != (price if sid == 12 and full else 0)
                            or failure[1] or failure[2]):
                        fails.append(f'{caption}: unsafe refused purchase (roll {roll}, full bag {full})')
                        break
            if any(size > 3 for o in outcomes for size in o[3]):
                fails.append(f'{caption}: choice box exceeds three rows')
        if not unique:
            fails.append(f'{caption}: no purchasable menu path')
    return fails, sold


def conversion_changes(sold):
    """Fail closed on new script conversions fed by vending items, pending graph review.

Mojyamon is modelled by shops.json. Item -> cards/merit is not a service in this
engine: meritValue is a purchase cost. Cards -> merit/items/bits are covered by
    economy_audit. Recruitment consumes Meat once and produces no saleable object.
"""
    ids = item_ids()
    fails = []
    paths = [*(ROOT / 'story/base/zones').rglob('script.py'),
             *(ROOT / 'story/mods/what-the-island-forgot').rglob('*.py')]
    for path in paths:
        tree = ast.parse(path.read_text())
        for fn in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)):
            calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)]
            def consumes(c):
                return (isinstance(c.func, ast.Name) and c.func.id == 'take' and c.args
                        and isinstance(c.args[0], ast.Attribute) and isinstance(c.args[0].value, ast.Name)
                        and c.args[0].value.id == 'Item' and ids[c.args[0].attr] in sold)
            if not any(consumes(c) for c in calls):
                continue
            # The new-game inventory wipe does not convert an input: it removes
            # every old stack and sets the one-time starting inventory.
            if path.parent.name == 's193-238' and fn.name == 'step4':
                continue
            outputs = [c for c in calls if isinstance(c.func, ast.Name) and c.func.id == 'give']
            if outputs:
                fails.append(f'unreviewed vending-fed conversion: {path.relative_to(ROOT)}:{fn.lineno}')
    return fails
