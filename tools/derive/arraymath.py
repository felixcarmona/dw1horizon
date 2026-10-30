"""Small standard-library numeric arrays for the model and texture converters.

This is an internal build helper, not a NumPy replacement for third-party code.
Views share storage; integer writes wrap and float32 writes round at each
operation. No optional runtime package or native extension is used.
"""
import builtins as _b
import itertools as _it
import math as _m
import operator as _op
import struct as _s
from functools import lru_cache


class DType:
    def __init__(self, name, code, bits=0, signed=False):
        self.name, self.code, self.bits, self.signed = name, code, bits, signed
        self.type = self

    def __call__(self, value):
        if isinstance(value, Array):
            return value.astype(self)
        if self.code == '?':
            return bool(value)
        if self.code == 'd':
            return float(value)
        if self.code == 'f':
            try:
                return _s.unpack('<f', _s.pack('<f', value))[0]
            except OverflowError:
                return _m.copysign(_m.inf, value)
        value = int(value) & ((1 << self.bits) - 1)
        return value - (1 << self.bits) if self.signed and value >= 1 << (self.bits - 1) else value

    def __repr__(self):
        return self.name


float64 = DType('float64', 'd')
float32 = DType('float32', 'f')
uint8 = DType('uint8', 'B', 8)
uint16 = DType('uint16', 'H', 16)
uint32 = DType('uint32', 'I', 32)
int16 = DType('int16', 'h', 16, True)
int32 = DType('int32', 'i', 32, True)
int64 = DType('int64', 'q', 64, True)
bool_ = DType('bool', '?')
_DTYPES = {d.name: d for d in (float64, float32, uint8, uint16, uint32, int16, int32, int64, bool_)}
_DTYPES.update({'<u2': uint16, '<i2': int16, '<i4': int32, '<f4': float32, '<f8': float64,
                'u1': uint8, 'i8': int64, '<i8': int64})


def _dtype(d):
    if isinstance(d, DType): return d
    if d is float: return float64
    if d is int: return int64
    if d is bool: return bool_
    return _DTYPES[d]


def _promote(types):
    """Common dtype for concatenated arrays (every operand is a strong type)."""
    types = set(types)
    if float64 in types: return float64
    if float32 in types:
        return float64 if _b.any(t.bits >= 32 for t in types) else float32
    types.discard(bool_)
    if not types: return bool_
    signed = [t.bits for t in types if t.signed]
    unsigned = [t.bits for t in types if not t.signed]
    if not signed: return {8:uint8, 16:uint16, 32:uint32}[_b.max(unsigned)]
    bits = _b.max(_b.max(signed), _b.max(unsigned, default=-1) + 1)
    return next(t for t in (int16, int32, int64) if t.bits >= bits)


def _strides(shape):
    s, out = 1, []
    for n in reversed(shape): out.append(s); s *= n
    return tuple(reversed(out))


def _coords(shape):
    return _it.product(*(range(n) for n in shape))


def _broadcast(*shapes):
    out = []
    for dims in _it.zip_longest(*(reversed(s) for s in shapes), fillvalue=1):
        n = next((d for d in dims if d != 1), 1)
        if _b.any(d not in (1, n) for d in dims):
            raise ValueError(f'incompatible shapes: {shapes}')
        out.append(n)
    return tuple(reversed(out))


class Array:
    __array_priority__ = 100

    def __init__(self, data, shape, dtype, strides=None, offset=0):
        self._data, self.shape, self.dtype = data, tuple(shape), dtype
        self.strides = _strides(self.shape) if strides is None else tuple(strides)
        self.offset = offset

    @property
    def ndim(self): return len(self.shape)
    @property
    def size(self): return _m.prod(self.shape)
    @property
    def T(self): return self.transpose()
    @property
    def flat(self): return self._values()

    def _values(self):
        if self.strides == _strides(self.shape):
            if self.offset == 0 and self.size == len(self._data): return iter(self._data)
            return iter(self._data[self.offset:self.offset + self.size])
        if self.strides[-1] == 1:
            width = self.shape[-1]
            def rows():
                for k in _coords(self.shape[:-1]):
                    off = self.offset + _b.sum(c * s for c, s in zip(k, self.strides[:-1]))
                    yield from self._data[off:off + width]
            return rows()
        return (self._data[self.offset + _b.sum(c * s for c, s in zip(k, self.strides))]
                for k in _coords(self.shape))

    def _offsets(self):
        if self.strides == _strides(self.shape): return range(self.offset, self.offset + self.size)
        return (self.offset + _b.sum(c * s for c, s in zip(k, self.strides)) for k in _coords(self.shape))

    def _at(self, coord):
        return self._data[self.offset + _b.sum((0 if n == 1 else k) * s
                        for k, n, s in zip(coord[-self.ndim:] if self.ndim else (), self.shape, self.strides))]

    def __len__(self): return self.shape[0]
    def __iter__(self): return self._values() if self.ndim == 1 else (self[i] for i in range(len(self)))
    def __bool__(self):
        if self.size != 1: raise ValueError('array truth requires one value')
        return bool(next(self._values()))
    def __float__(self): return float(next(self._values()))
    def __int__(self): return int(next(self._values()))
    def __index__(self):
        if self.shape or self.dtype.code in 'df?': raise TypeError('integer scalar required')
        return int(self)
    def __repr__(self): return f'array({self.tolist()!r}, {self.dtype})'
    def __bytes__(self): return self.tobytes()

    def _selection(self, key):
        if not isinstance(key, tuple): key = (key,)
        key = tuple(array(k) if isinstance(k, list) else k for k in key)
        used = _b.sum(k is not None and k is not Ellipsis for k in key)
        if _b.any(k is Ellipsis for k in key):
            at = next(i for i, k in enumerate(key) if k is Ellipsis)
            key = key[:at] + (slice(None),) * (self.ndim - used) + key[at + 1:]
        else:
            key += (slice(None),) * (self.ndim - used)
        # Boolean selection consumes all the axes it covers, retaining trailing axes.
        for i, k in enumerate(key):
            if isinstance(k, Array) and k.dtype is bool_:
                non = nonzero(k)
                key = key[:i] + non + key[i + 1:]
                # The initial implicit slices counted the mask as one axis.
                if len(key) > self.ndim: key = key[:self.ndim]
                break
        if not _b.any(isinstance(k, Array) for k in key):
            off, shape, strides, axis = self.offset, [], [], 0
            for k in key:
                if k is None:
                    shape.append(1); strides.append(0); continue
                n, s = self.shape[axis], self.strides[axis]; axis += 1
                if isinstance(k, slice):
                    a, b, step = k.indices(n)
                    shape.append(len(range(a, b, step))); strides.append(s * step); off += a * s
                else:
                    k = _op.index(k); k = k + n if k < 0 else k
                    if not 0 <= k < n: raise IndexError(k)
                    off += k * s
            return Array(self._data, shape, self.dtype, strides, off), None
        # Advanced integer indices broadcast together, as the converters' masks/UVs do.
        fancy = [i for i, k in enumerate(key) if isinstance(k, Array)]
        fs = _broadcast(*(key[i].shape for i in fancy))
        first = fancy[0]
        separated = _b.any(isinstance(key[i], slice) for i in range(first, fancy[-1]))
        dims, axes, axis = [], [], 0
        for i, k in enumerate(key):
            if k is None: dims.append((i, [0], 0)); continue
            n, stride = self.shape[axis], self.strides[axis]; axis += 1
            axes.append((i, k, n, stride))
            if isinstance(k, slice): dims.append((i, range(*k.indices(n)), stride))
        pre = [] if separated else [d for d in dims if d[0] < first]
        post = dims if separated else [d for d in dims if d[0] >= first]
        shape = tuple(len(d[1]) for d in pre) + fs + tuple(len(d[1]) for d in post)
        offsets = []
        for coord in _coords(shape):
            p, f = len(pre), len(fs)
            fc = coord[p:p + f]
            sc = dict((d[0], d[1][c]) for d, c in zip(pre + post, coord[:p] + coord[p + f:]))
            off = self.offset
            for i, k, n, stride in axes:
                v = k._at(fc) if isinstance(k, Array) else sc[i] if isinstance(k, slice) else k
                v = int(v); v = v + n if v < 0 else v
                if not 0 <= v < n: raise IndexError(v)
                off += v * stride
            offsets.append(off)
        return Array([self._data[i] for i in offsets], shape, self.dtype), offsets

    def __getitem__(self, key):
        if isinstance(key, int):
            n = self.shape[0]; key = key + n if key < 0 else key
            if not 0 <= key < n: raise IndexError(key)
            off = self.offset + key * self.strides[0]
            if self.ndim == 1: return self._data[off]
            return Array(self._data, self.shape[1:], self.dtype, self.strides[1:], off)
        if isinstance(key, tuple) and len(key) == self.ndim and _b.all(isinstance(k, int) for k in key):
            off = self.offset
            for k, n, stride in zip(key, self.shape, self.strides):
                k = k + n if k < 0 else k
                if not 0 <= k < n: raise IndexError(k)
                off += k * stride
            return self._data[off]
        result, _ = self._selection(key)
        return result._data[result.offset] if not result.shape else result

    def __setitem__(self, key, value):
        view, indices = self._selection(key)
        value = asarray(value)
        _broadcast(view.shape, value.shape)
        values = value._values() if value.shape == view.shape else (value._at(c) for c in _coords(view.shape))
        for off, v in zip(view._offsets() if indices is None else indices, list(values)):
            self._data[off] = self.dtype(v)

    def copy(self): return Array(list(self._values()), self.shape, self.dtype)
    def astype(self, dtype):
        d = _dtype(dtype)
        return Array([d(v) for v in self._values()], self.shape, d)
    def tolist(self):
        if self.ndim == 1: return list(self._values())
        if self.ndim == 2 and self.strides == _strides(self.shape):
            width = self.shape[1]
            return [list(self._data[i:i + width]) for i in range(self.offset, self.offset + self.size, width)] if width else [[] for _ in range(self.shape[0])]
        vals = iter(self._values())
        def walk(shape): return [walk(shape[1:]) for _ in range(shape[0])] if shape else next(vals)
        return walk(self.shape)
    def tobytes(self):
        return _s.pack('<' + str(self.size) + self.dtype.code, *self._values())
    def reshape(self, *shape):
        if len(shape) == 1 and isinstance(shape[0], (list, tuple)): shape = tuple(shape[0])
        if -1 in shape:
            other = -_m.prod(shape)
            shape = tuple(self.size // other if n == -1 else n for n in shape)
        if _m.prod(shape) != self.size: raise ValueError((self.shape, shape))
        a = self if self.strides == _strides(self.shape) else self.copy()
        return Array(a._data, shape, a.dtype, offset=a.offset)
    def ravel(self): return self.reshape(-1)
    flatten = ravel
    def transpose(self, *axes):
        if not axes: axes = tuple(reversed(range(self.ndim)))
        if len(axes) == 1 and isinstance(axes[0], tuple): axes = axes[0]
        return Array(self._data, [self.shape[i] for i in axes], self.dtype,
                     [self.strides[i] for i in axes], self.offset)
    def view(self, dtype): return frombuffer(self.tobytes(), dtype).reshape(self.shape[:-1] + (-1,))

    def _bin(self, other, op, reverse=False, comparison=False):
        other = asarray(other)
        shape = _broadcast(self.shape, other.shape)
        if comparison: d = bool_
        elif self.dtype is other.dtype: d = self.dtype
        elif not other.shape and other.dtype is int64 and self.dtype is not bool_: d = self.dtype
        elif not self.shape and self.dtype is int64 and other.dtype is not bool_: d = other.dtype
        elif self.dtype.code in 'df' or other.dtype.code in 'df':
            # NumPy scalar operands preserve the array's floating precision.
            d = self.dtype if not other.shape else other.dtype if not self.shape else float64
            if d.code not in 'df': d = float64
        else: d = int64
        if op is _op.truediv and d.code not in 'df': d = float64
        if self.shape == other.shape:
            vals = (op(b, a) if reverse else op(a, b) for a, b in zip(self._values(), other._values()))
        elif not other.shape:
            b = next(other._values())
            if d is float32: b = float32(b)
            vals = (op(b, a) if reverse else op(a, b) for a in self._values())
        elif not self.shape:
            a = next(self._values())
            if d is float32: a = float32(a)
            vals = (op(b, a) if reverse else op(a, b) for b in other._values())
        else:
            vals = (op(other._at(c), self._at(c)) if reverse else op(self._at(c), other._at(c)) for c in _coords(shape))
        if d is float64 and op in (_op.add, _op.sub, _op.mul, _op.truediv, _op.floordiv, _op.pow, _op.mod):
            return Array(list(vals), shape, d)
        return Array([d(v) for v in vals], shape, d)

    def __neg__(self): return self * -1
    def __abs__(self): return _unary(self, _b.abs)
    def __invert__(self): return _unary(self, _op.not_ if self.dtype is bool_ else _op.invert)
    def __matmul__(self, other): return matmul(self, other)
    def __rmatmul__(self, other): return matmul(other, self)
    def sum(self, axis=None, keepdims=False): return _reduce(self, _sum, axis, keepdims, int64 if self.dtype is bool_ else None)
    def mean(self, axis=None, keepdims=False):
        result = self.sum(axis, keepdims) / (self.size if axis is None else self.shape[axis])
        return float32(result) if self.dtype is float32 and not isinstance(result, Array) else result
    def min(self, axis=None, keepdims=False): return _reduce(self, _b.min, axis, keepdims)
    def max(self, axis=None, keepdims=False): return _reduce(self, _b.max, axis, keepdims)
    def any(self, axis=None, keepdims=False): return _reduce(self, _b.any, axis, keepdims, bool_)
    def all(self, axis=None, keepdims=False): return _reduce(self, _b.all, axis, keepdims, bool_)
    def argmin(self, axis=None): return _reduce(self, lambda v: _b.min(range(len(v)), key=v.__getitem__), axis, False, int64)
    def argmax(self, axis=None): return _reduce(self, lambda v: _b.max(range(len(v)), key=v.__getitem__), axis, False, int64)


for _name, _operation in [('add', _op.add), ('sub', _op.sub), ('mul', _op.mul), ('truediv', _op.truediv),
                          ('floordiv', _op.floordiv), ('pow', _op.pow), ('mod', _op.mod),
                          ('and', _op.and_), ('or', _op.or_), ('xor', _op.xor),
                          ('lshift', _op.lshift), ('rshift', _op.rshift),
                          ('lt', _op.lt), ('le', _op.le), ('gt', _op.gt), ('ge', _op.ge),
                          ('eq', _op.eq), ('ne', _op.ne)]:
    def _method(self, other, op=_operation, cmp=_name in ('lt', 'le', 'gt', 'ge', 'eq', 'ne')):
        return self._bin(other, op, comparison=cmp)
    def _reverse(self, other, op=_operation): return self._bin(other, op, reverse=True)
    def _inplace(self, other, op=_operation):
        self[...] = self._bin(other, op)
        return self
    setattr(Array, '__' + _name + '__', _method)
    setattr(Array, '__r' + _name + '__', _reverse)
    setattr(Array, '__i' + _name + '__', _inplace)
ndarray = Array


def array(value, dtype=None):
    if isinstance(value, Array): return value.copy() if dtype is None else value.astype(dtype)
    if hasattr(value, "tolist"): value = value.tolist()
    shape, data = [], []
    def walk(v, depth):
        if isinstance(v, Array): v = v.tolist()
        if isinstance(v, (list, tuple, range)):
            if depth == len(shape): shape.append(len(v))
            elif shape[depth] != len(v): raise ValueError('ragged array')
            for x in v: walk(x, depth + 1)
        else: data.append(v)
    walk(value, 0)
    d = _dtype(dtype) if dtype is not None else (float64 if _b.any(isinstance(v, float) for v in data)
                                                else bool_ if data and _b.all(isinstance(v, bool) for v in data) else int64)
    return Array([d(v) for v in data], shape, d)


def asarray(value, dtype=None):
    return value if isinstance(value, Array) and (dtype is None or value.dtype is _dtype(dtype)) else array(value, dtype)


def full(shape, value, dtype=None):
    if isinstance(shape, int): shape = (shape,)
    d = _dtype(dtype) if dtype is not None else array(value).dtype
    return Array([d(value)] * _m.prod(shape), shape, d)


def zeros(shape, dtype=float64): return full(shape, 0, dtype)
def ones(shape, dtype=float64): return full(shape, 1, dtype)
def empty(shape, dtype=float64): return zeros(shape, dtype)
def zeros_like(a): return zeros(a.shape, a.dtype)
def full_like(a, value): return full(a.shape, value, a.dtype)
def eye(n): return Array([float(i == j) for i in range(n) for j in range(n)], (n, n), float64)
def arange(start, stop=None, step=1, dtype=None):
    if stop is None: start, stop = 0, start
    n = _b.max(0, _m.ceil((stop - start) / step))
    return array([start + i * step for i in range(n)], dtype)
def linspace(start, stop, num=50, endpoint=True):
    den = num - 1 if endpoint else num
    a = array([start + i * ((stop - start) / den) if den else start for i in range(num)])
    if endpoint and num > 1: a[-1] = stop
    return a

def frombuffer(buffer, dtype=float64, count=-1, offset=0):
    d = _dtype(dtype); size = _s.calcsize(d.code)
    if count < 0: count = (len(buffer) - offset) // size
    return Array(list(_s.unpack_from('<' + str(count) + d.code, buffer, offset)), (count,), d)


def _unary(a, fn, dtype=None):
    if not isinstance(a, Array): return fn(a)
    d = dtype or a.dtype
    return Array([d(fn(v)) for v in a._values()], a.shape, d)


def _sum(values, cast=None):
    # NumPy's pairwise float64 reduction: eight parallel accumulators in blocks
    # of at most 128, followed by a balanced reduction. Integer addition is exact.
    n = len(values)
    if n < 8:
        out = -0.0 if values and isinstance(values[0], float) else 0
        for v in values: out = cast(out + v) if cast else out + v
        return out
    if n <= 128:
        r = list(values[:8]); i = 8
        while i <= n - 8:
            for j in range(8): r[j] = cast(r[j] + values[i + j]) if cast else r[j] + values[i + j]
            i += 8
        if cast:
            out = cast(cast(cast(r[0]+r[1]) + cast(r[2]+r[3])) + cast(cast(r[4]+r[5]) + cast(r[6]+r[7])))
        else:
            out = ((r[0]+r[1]) + (r[2]+r[3])) + ((r[4]+r[5]) + (r[6]+r[7]))
        for v in values[i:]: out = cast(out + v) if cast else out + v
        return out
    half = (n // 2) // 8 * 8
    result = _sum(values[:half], cast) + _sum(values[half:], cast)
    return cast(result) if cast else result


def _reduce(a, fn, axis=None, keepdims=False, dtype=None):
    a = asarray(a); d = dtype or a.dtype
    if fn is _sum and a.dtype is float32: fn = lambda values: _sum(values, float32)
    if axis is None:
        result = fn(list(a._values()))
        return full((1,) * a.ndim, result, d) if keepdims else result
    axis %= a.ndim
    shape = a.shape[:axis] + a.shape[axis + 1:]
    vals = []
    if axis == a.ndim - 1 and a.shape[axis]:
        values = a._values()
        vals = [d(fn(row)) for row in zip(*([values] * a.shape[axis]))]
    else:
        for c in _coords(shape):
            values = [a._at(c[:axis] + (i,) + c[axis:]) for i in range(a.shape[axis])]
            vals.append(d(fn(values)))
    if keepdims: shape = a.shape[:axis] + (1,) + a.shape[axis + 1:]
    return Array(vals, shape, d) if shape else vals[0]


abs = lambda a: _unary(a, _b.abs)
sqrt = lambda a: _unary(a, _m.sqrt)
sin = lambda a: _unary(a, _m.sin, float64)
cos = lambda a: _unary(a, _m.cos, float64)
log = lambda a: _unary(a, _m.log, float64)
exp = lambda a: _unary(a, _m.exp, float64)
floor = lambda a: _unary(a, _m.floor)
round = lambda a, decimals=0: _unary(a, lambda v: _b.round(v, decimals))
rint = round
isfinite = lambda a: _unary(a, _m.isfinite, bool_)
arccos = lambda a: _unary(a, _m.acos, float64)
pi, inf = _m.pi, _m.inf
sum = lambda a, axis=None, keepdims=False: asarray(a).sum(axis, keepdims)
mean = lambda a, axis=None, keepdims=False: asarray(a).mean(axis, keepdims)
min = lambda a, axis=None, keepdims=False: asarray(a).min(axis, keepdims)
max = lambda a, axis=None, keepdims=False: asarray(a).max(axis, keepdims)
any = lambda a, axis=None: asarray(a).any(axis)
all = lambda a, axis=None: asarray(a).all(axis)
argmin = lambda a, axis=None: asarray(a).argmin(axis)
argmax = lambda a, axis=None: asarray(a).argmax(axis)
minimum = lambda a, b: asarray(a)._bin(b, _b.min)
maximum = lambda a, b: asarray(a)._bin(b, _b.max)
copysign = lambda a, b: asarray(a)._bin(b, _m.copysign) if isinstance(a, Array) or isinstance(b, Array) else _m.copysign(a, b)
clip = lambda a, lo, hi: minimum(maximum(a, lo), hi)


def matmul(a, b):
    a, b = asarray(a), asarray(b)
    av, bv = a.ndim == 1, b.ndim == 1
    if av: a = a.reshape(1, -1)
    if bv: b = b.reshape(-1, 1)
    if a.shape[-1] != b.shape[-2]: raise ValueError((a.shape, b.shape))
    if a.ndim == b.ndim == 2 and a.shape == b.shape and a.shape in ((3, 3), (4, 4)):
        ad, bd = list(a._values()), list(b._values())
        size = a.shape[0]
        if size == 3:
            vals = [((0.0 + ad[i]*bd[j]) + ad[i+1]*bd[j+3]) + ad[i+2]*bd[j+6]
                    for i in (0, 3, 6) for j in range(3)]
        else:
            vals = [(((0.0 + ad[i]*bd[j]) + ad[i+1]*bd[j+4]) + ad[i+2]*bd[j+8]) + ad[i+3]*bd[j+12]
                    for i in (0, 4, 8, 12) for j in range(4)]
        return Array(vals, a.shape, float64)
    if a.ndim > 2 and b.ndim == 2 and a.shape[-2:] == b.shape and b.shape in ((3, 3), (4, 4)):
        size = b.shape[0]; bd = list(b._values()); values = a._values(); vals = []
        for ad in zip(*([values] * (size * size))):
            if size == 3:
                vals.extend(((0.0 + ad[i]*bd[j]) + ad[i+1]*bd[j+3]) + ad[i+2]*bd[j+6]
                            for i in (0, 3, 6) for j in range(3))
            else:
                vals.extend((((0.0 + ad[i]*bd[j]) + ad[i+1]*bd[j+4]) + ad[i+2]*bd[j+8]) + ad[i+3]*bd[j+12]
                            for i in (0, 4, 8, 12) for j in range(4))
        return Array(vals, a.shape, float64)
    batch = _broadcast(a.shape[:-2], b.shape[:-2])
    m, k, n = a.shape[-2], a.shape[-1], b.shape[-1]
    vals = []
    # Avoid array slicing/temporary arrays inside the small-matrix hot loop.
    for c in _coords(batch):
        ao = a.offset + _b.sum(v * s for v, s, d in zip(c[-(a.ndim - 2):] if a.ndim > 2 else (), a.strides[:-2], a.shape[:-2]) if d != 1)
        bo = b.offset + _b.sum(v * s for v, s, d in zip(c[-(b.ndim - 2):] if b.ndim > 2 else (), b.strides[:-2], b.shape[:-2]) if d != 1)
        for i in range(m):
            for j in range(n):
                total = 0.0
                for t in range(k):
                    total += a._data[ao + i * a.strides[-2] + t * a.strides[-1]] * b._data[bo + t * b.strides[-2] + j * b.strides[-1]]
                vals.append(total)
    shape = batch + (() if av else (m,)) + (() if bv else (n,))
    return Array(vals, shape, float64) if shape else vals[0]


def concatenate(arrays, axis=0):
    arrays = [asarray(a) for a in arrays]; axis %= arrays[0].ndim
    shape = list(arrays[0].shape); shape[axis] = _b.sum(a.shape[axis] for a in arrays)
    out = zeros(shape, _promote(a.dtype for a in arrays)); at = 0
    for a in arrays:
        key = [slice(None)] * out.ndim; key[axis] = slice(at, at + a.shape[axis]); out[tuple(key)] = a
        at += a.shape[axis]
    return out


def stack(arrays, axis=0):
    arrays = [asarray(a) for a in arrays]; axis %= arrays[0].ndim + 1
    return concatenate([a.reshape(a.shape[:axis] + (1,) + a.shape[axis:]) for a in arrays], axis)
def column_stack(arrays): return concatenate([asarray(a).reshape(-1, 1) for a in arrays], 1)
def hstack(arrays): return concatenate(arrays, 1 if asarray(arrays[0]).ndim > 1 else 0)
def outer(a, b): return asarray(a).reshape(-1, 1) * asarray(b).reshape(1, -1)
def trace(a): return _b.sum(a[i, i] for i in range(_b.min(a.shape[-2:])))
def diag(a):
    a = asarray(a)
    if a.ndim == 2: return array([a[i, i] for i in range(_b.min(a.shape))])
    out = zeros((len(a), len(a)), a.dtype)
    for i, v in enumerate(a): out[i, i] = v
    return out

def nonzero(a):
    a = asarray(a); coords = [c for c, v in zip(_coords(a.shape), a._values()) if v]
    return tuple(array([c[i] for c in coords], int64) for i in range(a.ndim))
def flatnonzero(a): return nonzero(asarray(a).ravel())[0]
def where(condition, yes, no):
    condition, yes, no = asarray(condition), asarray(yes), asarray(no)
    shape = _broadcast(condition.shape, yes.shape, no.shape)
    return Array([(yes if condition._at(c) else no)._at(c) for c in _coords(shape)], shape, yes.dtype)
def cross(a, b):
    a, b = asarray(a), asarray(b)
    shape = _broadcast(a.shape, b.shape)
    vals = []
    for c in _coords(shape[:-1]):
        x = [a._at(c + (i,)) for i in range(3)]; y = [b._at(c + (i,)) for i in range(3)]
        vals.extend((x[1]*y[2]-x[2]*y[1], x[2]*y[0]-x[0]*y[2], x[0]*y[1]-x[1]*y[0]))
    return Array(vals, shape, float64)


def einsum(spec, *args):
    args = [asarray(a) for a in args]
    if spec == 'fab,bc->fac': return matmul(*args)
    if spec == 'fij,nj->fni' and args[0].shape[-1] == 4:
        # Rig fitting transforms the same homogeneous point cloud in many
        # frames. Keep point coordinates and matrix rows out of array indexing.
        a, b = args
        points = b.tolist(); vals = []
        for frame in range(a.shape[0]):
            rows = a[frame].tolist()
            for x, y, z, w in points:
                vals.extend((((0.0 + r[0]*x) + r[1]*y) + r[2]*z) + r[3]*w for r in rows)
        return Array(vals, (a.shape[0], b.shape[0], a.shape[1]), float64)
    inputs, output = spec.split('->'); inputs = inputs.split(',')
    sizes = {ch: n for code, a in zip(inputs, args) for ch, n in zip(code, a.shape)}
    reduced = ''.join(dict.fromkeys(ch for code in inputs for ch in code if ch not in output))
    vals = []
    for out_c in _coords(tuple(sizes[ch] for ch in output)):
        env = dict(zip(output, out_c)); total = 0.0
        for rc in _coords(tuple(sizes[ch] for ch in reduced)):
            env.update(zip(reduced, rc)); product = 1.0
            for code, a in zip(inputs, args): product *= a._at(tuple(env[ch] for ch in code))
            total += product
        vals.append(total)
    return Array(vals, tuple(sizes[ch] for ch in output), float64)


class LinAlgError(ValueError):
    pass


class _Linalg:
    LinAlgError = LinAlgError

    @staticmethod
    def norm(a, axis=None, keepdims=False):
        a = asarray(a, float64)
        if axis is None and a.size in (3, 4):
            total = 0.0
            for v in a._values(): total += v*v
            result = _m.sqrt(total)
            return full((1,) * a.ndim, result) if keepdims else result
        if axis is not None and axis % a.ndim == a.ndim - 1 and a.shape[-1] in (3, 4):
            values = a._values()
            if a.shape[-1] == 3:
                vals = [_m.sqrt(((0.0 + x*x) + y*y) + z*z) for x, y, z in zip(values, values, values)]
            else:
                vals = [_m.sqrt((((0.0 + x*x) + y*y) + z*z) + w*w) for x, y, z, w in zip(values, values, values, values)]
            shape = a.shape[:-1] + ((1,) if keepdims else ())
            return Array(vals, shape, float64) if shape else vals[0]
        return sqrt((a * a).sum(axis, keepdims))

    @staticmethod
    def inv(a):
        a = asarray(a, float64); n = len(a)
        rows = [list(a[i]) + [float(i == j) for j in range(n)] for i in range(n)]
        for j in range(n):
            p = _b.max(range(j, n), key=lambda i: _b.abs(rows[i][j]))
            if rows[p][j] == 0: raise LinAlgError('singular matrix')
            rows[p], rows[j] = rows[j], rows[p]
            pivot = rows[j][j]; rows[j] = [x / pivot for x in rows[j]]
            for i in range(n):
                if i == j: continue
                factor = rows[i][j]
                rows[i] = [x - factor * y for x, y in zip(rows[i], rows[j])]
        return array([r[n:] for r in rows])

    @staticmethod
    def det(a):
        rows = asarray(a, float64).tolist(); n = len(rows); result = 1.0
        for j in range(n):
            p = _b.max(range(j, n), key=lambda i: _b.abs(rows[i][j]))
            if rows[p][j] == 0: return 0.0
            if p != j: rows[p], rows[j] = rows[j], rows[p]; result = -result
            pivot = rows[j][j]; result *= pivot
            for i in range(j + 1, n):
                f = rows[i][j] / pivot
                for k in range(j + 1, n): rows[i][k] -= f * rows[j][k]
        return result

    @staticmethod
    def svd(a, full_matrices=True):
        # One-sided Jacobi SVD for the converter's 3x3 rotation/scale keys.
        a = asarray(a, float64); m, n = a.shape
        cols = a.T.tolist(); v = eye(n).tolist()
        for _ in range(40):
            changed = False
            for p in range(n - 1):
                for q in range(p + 1, n):
                    aa = _sum([x*x for x in cols[p]]); bb = _sum([x*x for x in cols[q]])
                    ab = _sum([x*y for x,y in zip(cols[p], cols[q])])
                    if _b.abs(ab) <= 2e-16 * _m.sqrt(aa * bb): continue
                    changed = True
                    tau = (bb - aa) / (2 * ab)
                    t = _m.copysign(1.0, tau) / (_b.abs(tau) + _m.sqrt(1 + tau*tau))
                    c = 1 / _m.sqrt(1 + t*t); s = c*t
                    cols[p], cols[q] = ([c*x-s*y for x,y in zip(cols[p],cols[q])],
                                         [s*x+c*y for x,y in zip(cols[p],cols[q])])
                    v[p], v[q] = ([c*x-s*y for x,y in zip(v[p],v[q])],
                                  [s*x+c*y for x,y in zip(v[p],v[q])])
            if not changed: break
        lengths = [_m.sqrt(_sum([x*x for x in col])) for col in cols]
        # Match the reviewed axis-scale keys' reflection tie order: swap the
        # largest column into place. A stable sort moves tied columns differently
        # after that swap, changing the reflected axis for diag(1,1,-6).
        order = list(range(n))
        for i in range(n - 1):
            j = _b.max(range(i, n), key=lambda k: lengths[order[k]])
            order[i], order[j] = order[j], order[i]
        u = []
        for j in order:
            if lengths[j] > 1e-30: col = [x / lengths[j] for x in cols[j]]
            else:
                # Complete an orthonormal basis for hidden/zero-scale parts.
                candidates = []
                for axis in range(m):
                    candidate = [float(i == axis) for i in range(m)]
                    for prev in u:
                        dot = _sum([x*y for x,y in zip(candidate,prev)])
                        candidate = [x-dot*y for x,y in zip(candidate,prev)]
                    length = _m.sqrt(_sum([x*x for x in candidate])); candidates.append((length,candidate))
                length, col = _b.max(candidates, key=lambda t:t[0]); col = [x/length for x in col]
            u.append(col)
        return array(u).T, array([lengths[j] for j in order]), array([v[j] for j in order])

    @staticmethod
    def pinv(a, rcond=1e-15):
        a = asarray(a, float64)
        values = tuple(a._values())
        signs = _b.sum(1 << i for i, v in enumerate(values) if v == 0 and _m.copysign(1, v) < 0)
        return Array(list(_pinv_values(a.shape, values, rcond, signs)), (a.shape[1], a.shape[0]), float64)

    @staticmethod
    def lstsq(a, b, rcond=None):
        # The field tools fit two sine/cosine columns, never a general regression.
        a, b = asarray(a, float64), asarray(b, float64)
        u, s, vt = _Linalg.svd(a)
        cutoff = (_b.max(a.shape) * 2.220446049250313e-16 if rcond is None else rcond) * s.max()
        rank = _b.sum(x > cutoff for x in s)
        x = vt.T @ (array([1/v if v > cutoff else 0 for v in s]) * (u.T @ b))
        return x, array([((a @ x - b)**2).sum()]), rank, s


@lru_cache(maxsize=256)
def _pinv_values(shape, values, rcond, signs):
    # Rig fitting compares many point groups against the same reference bone.
    # Cache immutable values and hand callers independent arrays.
    a = Array(list(values), shape, float64)
    u, s, vt = _Linalg.svd(a)
    cutoff = s.max() * rcond
    result = (vt.T * array([1/x if x > cutoff else 0.0 for x in s])) @ u.T
    return tuple(result._values())


linalg = _Linalg()


def pad(a, width, mode='constant', constant_values=0):
    a = asarray(a)
    if isinstance(width, int): widths = [(width, width)] * a.ndim
    elif len(width) == 2 and isinstance(width[0], int): widths = [tuple(width)] * a.ndim
    else: widths = width
    out = full(tuple(n + lo + hi for n, (lo, hi) in zip(a.shape, widths)), constant_values, a.dtype)
    out[tuple(slice(lo, lo + n) for n, (lo, hi) in zip(a.shape, widths))] = a
    return out


def roll(a, shift, axis=None):
    a = asarray(a)
    if axis is None: return roll(a.ravel(), shift, 0).reshape(a.shape)
    axis %= a.ndim; n = a.shape[axis]
    key = [slice(None)] * a.ndim; key[axis] = array([(i - shift) % n for i in range(n)])
    return a[tuple(key)]


def ix_(*args):
    return tuple(asarray(a).reshape((1,) * i + (-1,) + (1,) * (len(args) - i - 1)) for i, a in enumerate(args))


def bincount(a, weights=None, minlength=0):
    vals = list(asarray(a)._values()); n = _b.max(minlength, _b.max(vals, default=-1) + 1)
    out = [0] * n
    for i, w in zip(vals, weights if weights is not None else _it.repeat(1)): out[i] += w
    return array(out)


def diff(a, n=1, axis=-1):
    a = asarray(a); axis %= a.ndim
    left, right = [slice(None)] * a.ndim, [slice(None)] * a.ndim
    left[axis], right[axis] = slice(1, None), slice(None, -1)
    for _ in range(n):
        a = a[tuple(left)] != a[tuple(right)] if a.dtype is bool_ else a[tuple(left)] - a[tuple(right)]
    return a


def median(a, axis=None):
    def middle(v):
        v = sorted(v); n = len(v)
        return v[n//2] if n % 2 else (v[n//2-1] + v[n//2]) / 2
    return _reduce(asarray(a), middle, axis, False, float64)


def argsort(a): return array(sorted(range(len(a)), key=asarray(a).__getitem__))
def cumsum(a): return array(list(_it.accumulate(asarray(a)._values())))
def searchsorted(a, v):
    import bisect
    return bisect.bisect_left(list(a), v)
def lexsort(keys): return array(sorted(range(len(keys[0])), key=lambda i: tuple(k[i] for k in reversed(keys))))
def unique(a, axis=None, return_inverse=False):
    a = asarray(a)
    vals = [tuple(row) for row in a.tolist()] if axis == 0 else list(a._values())
    uniq = sorted(set(vals)); out = array(uniq, a.dtype)
    if return_inverse:
        ids = {v:i for i,v in enumerate(uniq)}
        return out, array([ids[v] for v in vals])
    return out

def repeat(a, repeats, axis=None):
    a = asarray(a)
    if axis is not None: raise NotImplementedError('repeat axis')
    reps = _it.repeat(repeats) if isinstance(repeats, int) else repeats
    return array([v for v, n in zip(a._values(), reps) for _ in range(int(n))], a.dtype)
def tile(a, reps):
    a = asarray(a)
    if isinstance(reps, int): reps = (reps,)
    shape = (1,) * _b.max(0, len(reps) - a.ndim) + a.shape
    reps = (1,) * (len(shape) - len(reps)) + tuple(reps)
    a = a.reshape(shape); out = tuple(x*r for x,r in zip(shape,reps))
    return Array([a._at(tuple(c % n for c,n in zip(k,shape))) for k in _coords(out)], out, a.dtype)
def meshgrid(x, y):
    x, y = asarray(x), asarray(y)
    return tile(x, (len(y), 1)), tile(y.reshape(-1, 1), (1, len(x)))
class _Mgrid:
    def __getitem__(self, key): return stack(meshgrid(arange(key[1].start, key[1].stop), arange(key[0].start,key[0].stop))[::-1])
mgrid = _Mgrid()
class _R:
    def __getitem__(self, key): return concatenate([asarray(k).reshape(-1) for k in key])
r_ = _R()
ascontiguousarray = lambda a: asarray(a).copy()
