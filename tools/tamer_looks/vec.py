"""The little vector arithmetic the looks need, in plain Python: the same doubles on every machine, no numpy."""
import math


class Vec(list):
    """A vector of floats: + - * / work by component with another vector or with a number, @ is the dot product."""

    def _each(self, other, op):
        if isinstance(other, (int, float)):
            return Vec(op(a, other) for a in self)
        assert len(other) == len(self)
        return Vec(op(a, b) for a, b in zip(self, other))

    def __add__(self, o): return self._each(o, lambda a, b: a + b)
    def __sub__(self, o): return self._each(o, lambda a, b: a - b)
    def __mul__(self, o): return self._each(o, lambda a, b: a * b)
    def __truediv__(self, o): return self._each(o, lambda a, b: a / b)
    def __rsub__(self, o): return self._each(o, lambda a, b: b - a)
    def __neg__(self): return Vec(-a for a in self)
    def __matmul__(self, o): return dot(self, o)
    __radd__ = __iadd__ = __add__
    __rmul__ = __imul__ = __mul__
    __isub__ = __sub__
    __itruediv__ = __truediv__

    def __getitem__(self, i):
        r = list.__getitem__(self, i)
        return Vec(r) if isinstance(i, slice) else r


def array(values, kind=float):
    """A vector, or a list of vectors when the values are themselves sequences."""
    values = list(values)
    if values and isinstance(values[0], (list, tuple)):
        return [Vec(float(c) for c in v) for v in values]
    return Vec(float(c) for c in values)


def dot(a, b):
    total = 0.0
    for x, y in zip(a, b):
        total += x * y
    return total


def cross(a, b):
    return Vec((a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]))


def norm(a):
    return math.sqrt(dot(a, a))
