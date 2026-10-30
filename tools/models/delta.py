"""Plain MD3 copy/add deltas (standard library, CPython and Pyodide).

Only mode zero is supported: the
structured transform can store source bytes literally and must not be shipped.
Source SHA-256 pins live in the provider manifest; MD3 itself pins the target.
"""
import hashlib
import zlib

MAGIC = b'MD3\0'
MINLEN = 12
K = 8


def _wv(out, v):
    while v >= 0x80:
        out.append((v & 0x7f) | 0x80); v >>= 7
    out.append(v)


def _rv(b, i):
    v = s = 0
    while True:
        if i >= len(b) or s >= 64:
            raise ValueError('modeldelta: truncated or oversized varint')
        c = b[i]; i += 1
        v |= (c & 0x7f) << s; s += 7
        if c < 0x80: return v, i


def _zz(v): return (v << 1) ^ (v >> 63) if v >= 0 else ((-v) << 1) - 1
def _uz(u): return (u >> 1) if not u & 1 else -((u + 1) >> 1)


def build_index(pool):
    idx = {}
    for i in range(len(pool) - K + 1):
        k = pool[i:i + K]
        l = idx.get(k)
        if l is None: idx[k] = [i]
        elif len(l) < 6: l.append(i)
    return idx


def ops_for(target, pool, idx=None, minlen=MINLEN, selfref=True):
    """list of (add_start, add_end, copy_pos, copy_len). copy_pos lives in the virtual space  pool + target
    (positions >= len(pool) are earlier bytes of the target itself, VCDIFF's target window)."""
    if idx is None: idx = build_index(pool)
    idx = {k: list(v) for k, v in idx.items()} if selfref else idx
    n = len(target); t = 0; add0 = 0; ops = []; exp = 0
    tb = target; P = len(pool); ins = 0
    while t <= n - K:
        if selfref:
            while ins < t:      # index target positions strictly before t
                if ins + K <= n:
                    k = tb[ins:ins + K]; l = idx.get(k)
                    if l is None: idx[k] = [P + ins]
                    elif len(l) < 8: l.append(P + ins)
                ins += 1
        cands = []
        if exp < P:
            if pool[exp] == tb[t]: cands.append(exp)
        elif selfref and exp - P < t and tb[exp - P] == tb[t]: cands.append(exp)
        l = idx.get(tb[t:t + K])
        if l: cands.extend(l)
        bl = 0; bp = 0
        for p in cands:
            if p < P:
                lim = min(n - t, P - p); m = 0
                while m < lim and tb[t + m] == pool[p + m]: m += 1
            else:
                q = p - P
                if q >= t: continue
                lim = n - t; m = 0
                while m < lim and tb[t + m] == tb[q + m]: m += 1
            if m > bl: bl, bp = m, p
        if bl >= minlen:
            while t > add0 and bp > 0 and bp != P and tb[t - 1] == (pool[bp - 1] if bp <= P else tb[bp - P - 1]):
                t -= 1; bp -= 1; bl += 1
            ops.append((add0, t, bp, bl))
            t += bl; add0 = t; exp = bp + bl
        else:
            t += 1
    ops.append((add0, n, 0, 0))
    return ops



# ---------------------------------------------------------------- generic layer
def _gen_encode(target, pool, idx=None, minlen=MINLEN):
    ops = ops_for(target, pool, idx, minlen)
    blob = bytearray(); adds = bytearray(); exp = 0
    for a0, a1, cp, cl in ops:
        _wv(blob, a1 - a0); _wv(blob, cl); _wv(blob, _zz(cp - exp) if cl else 0)
        adds += target[a0:a1]
        if cl: exp = cp + cl
    body = bytearray(); _wv(body, len(ops)); _wv(body, len(blob)); body += blob; body += adds
    return bytes(body), ops


def encode(target, sources):
    """Encode only the plain copy/add format; never use the structured transform."""
    sources = list(sources)
    body, _ = _gen_encode(target, b''.join(sources))
    header = bytearray(MAGIC)
    header.append(0)
    _wv(header, len(sources))
    for source in sources:
        _wv(header, len(source))
    _wv(header, len(target))
    header += hashlib.sha256(target).digest()
    return bytes(header) + zlib.compress(body, 9)


def decode(delta, sources):
    """Decode and check the target SHA-256. The caller checks source SHA-256 pins."""
    sources = list(sources)
    if delta[:5] != MAGIC + b'\0':
        raise ValueError('modeldelta: expected plain MD3 (mode 0)')
    nsource, pos = _rv(delta, 5)
    if nsource != len(sources):
        raise ValueError('modeldelta: source count differs')
    for source in sources:
        size, pos = _rv(delta, pos)
        if size != len(source):
            raise ValueError('modeldelta: source length differs')
    target_size, pos = _rv(delta, pos)
    sha = delta[pos:pos + 32]
    if len(sha) != 32:
        raise ValueError('modeldelta: truncated SHA-256')
    try:
        body = zlib.decompress(delta[pos + 32:])
    except zlib.error as error:
        raise ValueError('modeldelta: invalid compressed body') from error
    count, pos = _rv(body, 0)
    blob_size, pos = _rv(body, pos)
    if pos + blob_size > len(body):
        raise ValueError('modeldelta: truncated operations')
    blob = body[pos:pos + blob_size]
    adds = memoryview(body)[pos + blob_size:]
    pool = b''.join(sources)
    out = bytearray()
    index = added = expected = 0
    for _ in range(count):
        add_size, index = _rv(blob, index)
        copy_size, index = _rv(blob, index)
        offset, index = _rv(blob, index)
        if added + add_size > len(adds) or len(out) + add_size + copy_size > target_size:
            raise ValueError('modeldelta: operation exceeds data length')
        out += adds[added:added + add_size]
        added += add_size
        if copy_size:
            source = expected + _uz(offset)
            expected = source + copy_size
            if 0 <= source and source + copy_size <= len(pool):
                out += pool[source:source + copy_size]
            else:
                source -= len(pool)
                if not 0 <= source < len(out):
                    raise ValueError('modeldelta: invalid copy reference')
                if source + copy_size <= len(out):
                    out += out[source:source + copy_size]
                else:
                    for _ in range(copy_size):
                        out.append(out[source])
                        source += 1
    if index != len(blob) or added != len(adds):
        raise ValueError('modeldelta: unused operation or literal bytes')
    if len(out) != target_size or hashlib.sha256(out).digest() != sha:
        raise ValueError('modeldelta: target SHA-256 mismatch')
    return bytes(out)
