"""Correctly rounded sin, cos, tan, atan, atan2, asin and acos: the same double on every machine.

The C library's sin, cos, atan2 ... (which Python's math module calls) are accurate to about one unit in the last place,
but each library rounds differently: glibc (CPython on Linux) and musl (Pyodide, the browser's Python) give another
last bit for ~3% of the arguments our model scripts use. A model script turns those angles into integer keyframes, and
one flipped rounding is a different MMD (MUGP.MMD came out 20 bytes longer in Pyodide; 24 species portraits of
DIGI.DAT differed). These functions return the double nearest the exact value (as mpmath at 200 bits would), so the
bytes no longer depend on the library. On the build's arguments glibc gave the correctly rounded value but for ~0.1%,
and none of those changed a byte of the everything disc (tools/derive/README.md).

How: the argument is an exact rational; the value is computed with Python integers in fixed point (P fraction bits,
P chosen from the library's own result so that ~100 bits beyond a double's are kept), with an error bound of a few
units; if both ends of the bound round to the same double that double is the answer (int / int is correctly rounded
in CPython), else P grows. Zeros, infinities and NaN go to the C library (those results are exact everywhere).
Results are cached (the scripts call sin and cos millions of times on ~10 000 angles).

  install()    replaces math.sin, cos, tan, atan, atan2, asin, acos with these (tools/derive does it around every
               step: every derived byte is made with them); uninstall() puts the library's back.
Standard library only.
"""
import functools
import math

_LIB = {n: getattr(math, n) for n in ('sin', 'cos', 'tan', 'atan', 'atan2', 'asin', 'acos')}
GUARD = 100            # bits kept beyond the result's own 53
SLACK = 1 << 12        # the error bound, in units of 2^-P (the true error is a few units)


# ---------------------------------------------------------------- fixed-point pieces (integers scaled by 2^P)
@functools.lru_cache(maxsize=None)
def _pi(p):
    """pi * 2^p (floor, error < 1): Machin's formula with 32 guard bits."""
    q = p + 32
    def atan_inv(n):                     # atan(1/n) * 2^q
        s = t = (1 << q) // n
        n2, k, sign = n * n, 1, -1
        while t:
            t //= n2
            k += 2
            s += sign * (t // k)
            sign = -sign
        return s
    return (16 * atan_inv(5) - 4 * atan_inv(239)) >> 32


def _sincos(r, p):
    """(sin r, cos r) * 2^p for r = R / 2^p, |r| <= ~0.8 (Taylor)."""
    one = 1 << p
    s, c = r, one
    t = r
    k = 1
    while t:
        t = -(t * r >> p) // (k + 1)          # r^(k+1) / (k+1)!   (cos term)
        c += t
        t = (t * r >> p) // (k + 2)           # r^(k+2) / (k+2)!   (sin term)
        s += t
        k += 2
    return s, c


def _atan_small(t, p):
    """atan(t) * 2^p for t = T / 2^p, 0 <= t <= 1: halved until small (atan t = 2 atan(t / (1 + sqrt(1 + t^2)))),
    then Taylor."""
    one = 1 << p
    halvings = 0
    while t > one >> 6:
        root = math.isqrt(one * one + t * t)  # sqrt(1 + t^2) * 2^p
        t = (t << p) // (one + root)
        halvings += 1
    s, term, t2, k = t, t, t * t >> p, 1
    while term:
        term = -(term * t2 >> p)
        k += 2
        s += term // k
    return s << halvings


def _atan_frac(n, d, p):
    """atan(n / d) * 2^p for integers n >= 0, d > 0."""
    if n > d:
        return (_pi(p) >> 1) - _atan_frac(d, n, p)
    return _atan_small((n << p) // d, p)


# ---------------------------------------------------------------- rounding
def _round(value, start):
    """The double nearest value(P) / 2^P, P from `start` up until the error bound cannot change the rounding."""
    p = start
    for _ in range(8):
        v = value(p)
        lo, hi = (v - SLACK) / (1 << p), (v + SLACK) / (1 << p)
        if lo == hi:
            return lo
        p += 64
    return v / (1 << p)


def _bits(lib_result, extra=0):
    """P for a result near lib_result: its exponent plus GUARD fraction bits."""
    e = math.frexp(lib_result)[1] if lib_result else -1074
    return max(64, GUARD + 53 - e + extra)


def _fixed(x, p):
    """x * 2^p as an integer (floor; exact when x has no bits below 2^-p)."""
    n, d = x.as_integer_ratio()
    return (n << p) // d


def _reduce(x, p):
    """(k, r * 2^p) with x = k pi/2 + r, |r| <= pi/4 (pi taken with the bits x's size needs)."""
    q = p + max(0, math.frexp(x)[1]) + 8
    X, half = _fixed(x, q), _pi(q) >> 1
    k = (2 * X + half) // (2 * half)          # round(x / (pi/2))
    return k, (X - k * half) >> (q - p)


def _special(x):
    return x == 0 or not math.isfinite(x)


# ---------------------------------------------------------------- the functions
@functools.lru_cache(maxsize=1 << 16)
def sin(x):
    x = float(x)
    if _special(x):
        return _LIB['sin'](x)
    def v(p):
        k, r = _reduce(x, p)
        s, c = _sincos(r, p)
        return (s, c, -s, -c)[k % 4]
    return _round(v, _bits(_LIB['sin'](x), max(0, -math.frexp(x)[1])))


@functools.lru_cache(maxsize=1 << 16)
def cos(x):
    x = float(x)
    if _special(x):
        return _LIB['cos'](x)
    def v(p):
        k, r = _reduce(x, p)
        s, c = _sincos(r, p)
        return (c, -s, -c, s)[k % 4]
    return _round(v, _bits(_LIB['cos'](x)))


@functools.lru_cache(maxsize=1 << 16)
def tan(x):
    x = float(x)
    if _special(x):
        return _LIB['tan'](x)
    def v(p):
        q = p + 64
        k, r = _reduce(x, q)
        s, c = _sincos(r, q)
        n, d = (s, c) if k % 2 == 0 else (c, -s)
        return (n << p) // d
    return _round(v, _bits(_LIB['tan'](x), max(0, -math.frexp(x)[1])))


@functools.lru_cache(maxsize=1 << 16)
def atan2(y, x):
    y, x = float(y), float(x)
    if _special(y) or _special(x) or math.isnan(x) or math.isnan(y):
        return _LIB['atan2'](y, x)
    (yn, yd), (xn, xd) = abs(y).as_integer_ratio(), abs(x).as_integer_ratio()
    n, d = yn * xd, xn * yd                    # |y/x| = n / d
    def v(p):
        a = _atan_frac(n, d, p)
        if x < 0:
            a = _pi(p) - a
        return a if y > 0 else -a
    return _round(v, _bits(_LIB['atan2'](y, x)))


@functools.lru_cache(maxsize=1 << 16)
def atan(x):
    x = float(x)
    if _special(x) or math.isnan(x):
        return _LIB['atan'](x)
    return atan2(x, 1.0)


def _asin_parts(x, p):
    """(|x|, sqrt(1 - x^2)) * 2^q as integers, q = p + 64 (asin x = atan2(x, sqrt(1-x^2)))."""
    q = p + 64
    n, d = abs(x).as_integer_ratio()
    return (n << q) // d, math.isqrt(((d * d - n * n) << (2 * q)) // (d * d))


@functools.lru_cache(maxsize=1 << 16)
def asin(x):
    x = float(x)
    if _special(x) or abs(x) >= 1:
        return _LIB['asin'](x)                # (asin(+-1) = +-pi/2 rounded, a domain error beyond)
    def v(p):
        s, c = _asin_parts(x, p)
        a = _atan_frac(s, c, p) if c else _pi(p) >> 1
        return a if x > 0 else -a
    return _round(v, _bits(_LIB['asin'](x)))


@functools.lru_cache(maxsize=1 << 16)
def acos(x):
    x = float(x)
    if math.isnan(x) or abs(x) >= 1 or x == 0:
        return _LIB['acos'](x)                # (acos(1) = 0, acos(-1) = pi rounded, acos(0) = pi/2 rounded)
    def v(p):
        s, c = _asin_parts(x, p)
        a = _atan_frac(c, s, p)                # acos |x| = atan(sqrt(1-x^2) / |x|)
        return a if x > 0 else _pi(p) - a
    return _round(v, _bits(_LIB['acos'](x)))


_MINE = {'sin': sin, 'cos': cos, 'tan': tan, 'atan': atan, 'atan2': atan2, 'asin': asin, 'acos': acos}


def install():
    """math.sin ... are these from now on (for code that looks them up at call time: `math.sin(x)`)."""
    for n, f in _MINE.items():
        setattr(math, n, f)


def uninstall():
    for n, f in _LIB.items():
        setattr(math, n, f)


def clear():
    """Forget the cached results (memory: between a build's steps)."""
    for f in _MINE.values():
        f.cache_clear()
