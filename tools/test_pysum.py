#!/usr/bin/env python3
"""Tests of tools/derive/pysum.py: its sum() is CPython 3.12's, bit for bit.

On Python 3.12 every case must give the builtin's result exactly (the same type, the same double: NaN for NaN, the sign
of a zero) or the same exception; on 3.13 too (its sum is 3.12's). On 3.14 and newer, the same for every case but
those that add an int to a running float sum (3.14 compensates those too: the builtin changed, the port stays 3.12's). On 3.10 and 3.11 there is nothing
to compare with: the test checks that the cases where 3.12 differs from plain addition do differ there (else it would
prove nothing) and that install() makes builtins.sum the port.

  tools/test_pysum.py [--n N]     (selftest: derive-sum; N random lists per kind, default 3000)
"""
import builtins, fractions, decimal, math, os, random, struct, sys  # noqa: E401
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.derive import pysum  # noqa: E402

V = sys.version_info[:2]


def key(v):
    """What 'the same result' means: the type and, for a float, its 64 bits."""
    if type(v) is float:
        return ('float', struct.pack('<d', v))
    if type(v) is complex:
        return ('complex', struct.pack('<dd', v.real, v.imag))
    return (type(v).__name__, repr(v))


def run(f, items, start):
    try:
        return key(f(iter(items)) if start is None else f(iter(items), start))
    except Exception as e:
        return ('raises', type(e).__name__, str(e))


def floats_with_ints(items, start):
    """True when an int (or bool) meets a running float total: there 3.14 changed what the builtin does."""
    t = start if start is not None else 0
    for x in items:
        if type(t) is float and isinstance(x, int):
            return True
        try:
            t = t + x
        except Exception:
            return False
    return False


class F(float):
    pass


class I(int):
    pass


def adversarial():
    big = 2.0 ** 53
    inf, nan = math.inf, math.nan
    yield [], None
    yield [], 0.0
    yield [], -0.0
    yield [-0.0], None
    yield [-0.0, -0.0], -0.0
    yield [-0.0], 0.0
    yield [1.0, 1e100, 1.0, -1e100], None
    yield [1e308, 1e308, -1e308], None                    # overflows to inf, then a finite item
    yield [1e308, 1e308, -1e308, -1e308], 0.0
    yield [inf, 1.0, -inf], None
    yield [inf, -inf], 0.0
    yield [nan, 1.0], None
    yield [1.0, nan, 2.0], 0.5
    yield [0.1] * 10, None
    yield [0.1] * 10, 0.0
    yield [big, 1.0, 1.0, -big], None
    yield [big, 1.0, -1.0, 1.0], 0.0
    yield [1.0, 2 ** 53 + 1, 1.0], None                    # ints inside a float sum
    yield [0.5, 2 ** 63 - 1, 0.5], None                    # the largest long
    yield [0.5, 2 ** 63, 0.5, 1e-3], None                  # one past it: plain addition from there on
    yield [0.5, -(2 ** 63), 0.5], None
    yield [0.5, -(2 ** 63) - 1, 0.1, 0.2, 0.3], None
    yield [0.1, True, 0.2, False, 0.3], None
    yield [0.1, I(3), 0.2], None
    yield [1, 2, 3], None
    yield [1, 2, 3], 10
    yield [True, True, 1], None
    yield [1, 2, 3], True                                  # a bool start: no fast path
    yield [1, 2.5, 0.1, 0.2, 0.3], None                    # the int loop hands over to the float loop
    yield [2 ** 63 - 2, 1, 1, 0.1, 0.2, 0.3], None          # the int loop overflows: plain addition from there on
    yield [2 ** 62, 2 ** 62, 0.1, 0.2], None
    yield [-(2 ** 63), -1, 0.1], None
    yield [0.1, 0.2], 2 ** 64                              # a start too big for the int loop
    yield [0.1, 0.2, 0.3], 2 ** 63 - 1
    yield [F(0.1), 0.2, 0.3], None                         # a float subclass: plain addition
    yield [0.1, F(0.2), 0.3, 0.4], None
    yield [0.1, 0.2, 0.3], F(1.0)
    yield [0.1, fractions.Fraction(1, 3), 0.2, 0.3], None
    yield [fractions.Fraction(1, 3), 0.1, 0.2], None
    yield [decimal.Decimal('0.1'), decimal.Decimal('0.2')], None
    yield [0.1, decimal.Decimal('0.2')], None              # raises
    yield [0.1, 'a'], None                                 # raises
    yield ['a', 'b'], ''                                   # raises: strings
    yield [b'a'], b''                                      # raises: bytes
    yield [b'a'], bytearray()                              # raises: bytearray
    yield [[1], [2]], []
    yield [(1,), (2,)], ()
    yield [1j, 0.5, 2j], None
    yield [0.5, 1j, 0.25], 0.0
    yield [5e-324, -5e-324, 5e-324], None
    yield [1.7976931348623157e308, -1.7976931348623157e308, 1.0], None
    yield [3.0, -1e16, 1e16, 2.0 ** -60], None


def rnd_float(r):
    k = r.random()
    if k < 0.25:
        return r.uniform(-1, 1) * 10 ** r.randint(-30, 30)
    if k < 0.5:
        return (r.uniform(0, 255) - r.uniform(0, 255)) ** 2   # what the colour searches add
    if k < 0.75:
        return struct.unpack('<d', struct.pack('<Q', r.getrandbits(64)))[0]   # any bit pattern: nan, inf, subnormals
    return r.choice([0.0, -0.0, 1.0, -1.0, 0.1, 1e16, -1e16, 2.0 ** 53, 1e308, -1e308, 5e-324])


def rnd_item(r, mixed):
    if not mixed or r.random() < 0.8:
        return rnd_float(r)
    return r.choice([r.randint(-10, 10), r.getrandbits(r.randint(1, 70)) * r.choice([1, -1]), True, False])


def randoms(n, seed=12):
    r = random.Random(seed)
    for _ in range(n):                       # floats alone, as the colour searches give them
        yield [rnd_float(r) for _ in range(r.randint(0, 40))], r.choice([None, None, 0.0, -0.0, 0])
    for _ in range(n):                       # mixed ints and floats
        yield [rnd_item(r, True) for _ in range(r.randint(0, 40))], r.choice([None, 0.0, 0, 7, 2 ** 63 - 1])
    for _ in range(n):                       # cancellation: big values that cancel around small ones
        b = [r.uniform(-1, 1) * 10 ** r.randint(10, 300) for _ in range(r.randint(1, 10))]
        s = [r.uniform(-1, 1) * 10 ** r.randint(-20, 5) for _ in range(r.randint(1, 10))]
        items = b + [-x for x in b] + s
        r.shuffle(items)
        yield items, None
    for _ in range(n // 10):                 # long lists
        yield [rnd_float(r) for _ in range(r.randint(100, 3000))], None


def main():
    n = int(sys.argv[sys.argv.index('--n') + 1]) if '--n' in sys.argv else 3000
    cases = list(adversarial()) + list(randoms(n))
    native = builtins.sum
    if V >= (3, 12):
        bad = skipped = 0
        for items, start in cases:
            if V >= (3, 14) and floats_with_ints(items, start):
                skipped += 1
                continue
            a, b = run(native, items, start), run(pysum.sum, items, start)
            if a != b:
                bad += 1
                if bad <= 10:
                    print(f'DIFFERS start={start!r} items={items[:12]!r}{"..." if len(items) > 12 else ""}\n'
                          f'  builtin {a}\n  pysum   {b}')
        print(f'Python {V[0]}.{V[1]}: {len(cases) - skipped} cases, {bad} differ from the builtin'
              + (f' ({skipped} with ints in a float sum skipped: 3.14 changed those)' if skipped else ''))
        if bad:
            sys.exit(1)
    else:
        # the port must not be plain addition: the cases 3.12 sums differently differ here
        plain = sum(1 for items, start in cases if run(native, items, start) != run(pysum.sum, items, start))
        print(f'Python {V[0]}.{V[1]}: {plain} of {len(cases)} cases differ from this Python\'s own sum (3.12\'s '
              f'compensation)')
        if plain < 100 or run(pysum.sum, [0.1] * 10, None) != key(1.0):
            sys.exit('the port looks like plain addition')
    # install() swaps the builtin only where it is needed
    pysum.install()
    assert (builtins.sum is pysum.sum) == (V < (3, 12)), builtins.sum
    pysum.uninstall()
    assert builtins.sum is native
    print('ok')


if __name__ == '__main__':
    main()
