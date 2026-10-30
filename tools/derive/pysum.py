"""sum() as CPython 3.12 adds floats: the same double on every Python from 3.10.

Since 3.12 the builtin sum() keeps a running compensation while it adds floats (Neumaier's improved Kahan-Babuska
summation); 3.10 and 3.11 add them one rounding at a time. The player's build sums floats where the result picks a
byte: the card textures' and the species portraits' nearest-colour searches sum squared float differences
(tools/localize/textures/cards-cups/fr_es.py, fr_erase.py, tools/portraits.py), and one closer colour is another
pixel. On 3.10/3.11 DIGI.DAT, CARD/CARD.ALL and CARD/LE004.ALL came out different.

  sum(iterable, /, start=0)   CPython 3.12's builtin_sum_impl (Python/bltinmodule.c, v3.12.12) step by step: the
                              int loop while the total and the items are ints that fit a C long, then the float loop
                              (compensated for exact floats, ints that fit a long added uncompensated), then plain `+`
                              for the rest; the same results, the same exceptions
  install()                   on Python older than 3.12, makes builtins.sum this one (tools/derive does it around every
                              step, as it installs crmath's sin and cos: every script and module a step runs, ours or a
                              content script, sums the same way); on 3.12 and newer it does nothing (the builtin is it)
  uninstall()                 puts the builtin back

Why not each call site: the spots that change bytes are in tools/localize and tools/portraits.py, and any other float
sum a later script adds would bring the difference back; one replacement covers them all.

Kept as in 3.12, not as in 3.14 (which also compensates the ints of a float sum and converts big ints): the release's
disc is the same with 3.12 and 3.14, so our sums never meet that difference. A C long is 64 bits here (Linux, macOS);
on Windows CPython's own 3.12 uses 32 bits, which only matters for an int of 2^31 or more inside a float sum.
Standard library only.
"""
import builtins
import math
import sys

_BUILTIN = builtins.sum
_MAX = (1 << 63) - 1        # LONG_MAX = PY_SSIZE_T_MAX on a 64-bit Linux or macOS
_MIN = -(1 << 63)
_isfinite = math.isfinite


def sum(iterable, /, start=0):            # noqa: A001 (it is the builtin's replacement)
    it = iter(iterable)
    result = start
    if isinstance(result, str):
        raise TypeError("sum() can't sum strings [use ''.join(seq) instead]")
    if isinstance(result, bytes):
        raise TypeError("sum() can't sum bytes [use b''.join(seq) instead]")
    if isinstance(result, bytearray):
        raise TypeError("sum() can't sum bytearray [use b''.join(seq) instead]")

    # the int loop: an exact int total that fits a long, items exact ints or bools that keep it in a long
    if type(result) is int and _MIN <= result <= _MAX:
        i = result
        for item in it:
            t = type(item)
            if t is int or t is bool:
                if _MIN <= item <= _MAX:
                    s = i + item
                    if _MIN <= s <= _MAX:
                        i = s
                        continue
            result = i + item               # overflowed or not an int: the general addition, once
            break
        else:
            return i

    # the float loop: an exact float total
    if type(result) is float:
        f = result
        c = 0.0
        for item in it:
            t = type(item)
            if t is float:
                x = item
                s = f + x
                if abs(f) >= abs(x):
                    c += (f - s) + x
                else:
                    c += (x - s) + f
                f = s
                continue
            if isinstance(item, int):       # PyLong_Check: ints, bools, int subclasses
                v = int.__int__(item)
                if _MIN <= v <= _MAX:
                    f += float(v)           # (double)value: correctly rounded, as float(int)
                    continue
            if c and _isfinite(c):
                f += c
            result = f + item
            break
        else:
            if c and _isfinite(c):
                f += c
            return f

    # anything else: one addition after another
    for item in it:
        result = result + item
    return result


def needed():
    """True where the builtin is not 3.12's (Python 3.10 and 3.11)."""
    return sys.version_info < (3, 12)


def install():
    if needed():
        builtins.sum = sum


def uninstall():
    builtins.sum = _BUILTIN
