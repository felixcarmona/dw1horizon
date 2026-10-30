"""make-release side of format 3's code copies (dwpatch.py, docs/patcher.md §9 "Code copies"): how the bytes of
our executable and overlays that equal the USA disc's code are taken from the player's own disc on every base.

Encoder3.encode marks a run of an authored file that equals the USA executable, overlays or scripts as code copy k
(`code[k]` = [USA source, offset, length]). No other release has those files, so each base needs its own source for
every byte of a copy, and a byte some base cannot give is literal (`lit_usa` in audit.txt). relocate() finds, per base
and per USA code file, where each byte is on that base:

  1. runs of 32 bytes or more in the base's executable, overlays and scripts, matched against the whole USA file (a
     short copy at the edge of a run is found through the run it belongs to);
  2. extend a run in both directions while words differ only in candidate address fields (the target of j/jal, the
     16-bit immediate of lui/addiu/ori/a load or store, a pointer 0x80000000-0x801FFFFF). Also check equal-length gaps
     between matches in the base's own counterpart of the file (its executable for SLUS_010.32, the overlay of the
     same name). A differing word is copied with a fix-up: the bits that differ, XORed onto the copied bytes;
  3. bytes no base gives but that a file every base has as the USA one holds (32 bytes or more, found in the whole USA
     file's context): a plain copy of that file ('c'), the same on every base.

What stays literal is code and data the other releases do not have: their own PsyQ library versions, tables that
differ, and the overlays' *_bss_us buffers stored with the USA build's residue (§9).

reuse_outputs() first turns a run that an earlier authored file of the same patched disc already holds into a
copy of that file ('o': translated copies of the overlays carry the overlays' bytes again), and
compact() rebuilds the literal blob with only the bytes still used.

Payload additions (DWP3, read by dwpatch.build_disc3): `fix` {base: {k: [[position in copy k, hex XOR], ...]}};
operation ["o", path, offset, length], bytes of an earlier file of the patched disc.
"""
import struct

BLOCK = 32
# I-type opcodes whose 16-bit immediate is an address part when a moved function is relinked: addi, addiu, ori, lui,
# the loads and stores, lwc2/swc2 (a branch's offset is relative: a different one is different code)
IMM_OPS = {0x08, 0x09, 0x0d, 0x0f, 0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x28, 0x29, 0x2a, 0x2b, 0x2e, 0x32, 0x3a}


def addr_xor(u, v):
    """The XOR that turns word v (the base's) into u (the USA one) when they differ only in a candidate address field, else
    None."""
    x = u ^ v
    if x == 0:
        return 0
    op = u >> 26
    if op == v >> 26:
        if op in (2, 3) and x < 1 << 26:
            return x
        if op in IMM_OPS and x < 1 << 16:
            return x
    if 0x80000000 <= u < 0x80200000 and 0x80000000 <= v < 0x80200000:
        return x
    return None


def _runs(U, pool_U, idx, limit=None):
    """[(start in U, offset in pool_U, length)]: runs of BLOCK bytes or more of U found in pool_U (only below `limit`
    when given), extended both ways (dwpatch._matches over a whole file)."""
    out = []
    p = lit = 0
    e = len(U)
    end = len(pool_U) if limit is None else limit
    while p + BLOCK <= e:
        o = idx.get(hash(U[p:p + BLOCK]))
        if o is None or o + BLOCK > end or pool_U[o:o + BLOCK] != U[p:p + BLOCK]:
            p += 1
            continue
        L = BLOCK
        while p + L + 256 <= e and o + L + 256 <= end and pool_U[o + L:o + L + 256] == U[p + L:p + L + 256]:
            L += 256
        while p + L < e and o + L < end and pool_U[o + L] == U[p + L]:
            L += 1
        while p > lit and o > 0 and pool_U[o - 1] == U[p - 1]:
            p -= 1
            o -= 1
            L += 1
        out.append((p, o, L))
        p += L
        lit = p
    return out


def _split(pool, runs):
    """Pool runs (offset in pool.U) cut at the pool's file boundaries: [(start in U, file index, offset, length)]."""
    import bisect
    out = []
    for p, o, L in runs:
        while L:
            i = bisect.bisect_right(pool.starts, o) - 1
            end = pool.starts[i + 1] if i + 1 < len(pool.starts) else len(pool.U)
            k = min(L, end - o)
            out.append((p, i, o - pool.starts[i], k))
            p += k
            o += k
            L -= k
    return out


class SourceMap:
    """Where each byte of one USA code file is on one base: src[x] = (path on the base, offset) or None; xor[x] the
    fix-up byte (0: copied as it is)."""
    def __init__(self, n):
        self.src = [None] * n
        self.xor = bytearray(n)


def base_maps(enc, key, img, Pool):
    """{USA code file: SourceMap} for base `key` (isowriter.Image `img`) and every USA source of enc.code."""
    mp = enc.mappings[key]
    boot = mp['boot']
    names = sorted(q for q in img.files if not img.files[q][2] and (
        q.endswith('_REL.BIN') or q in (boot, 'SYSTEM.CNF') or q.startswith('SCN/') and q.endswith('.SCN')))
    pool = Pool([(q, img.read(q)) for q in names])
    out = {}
    for s in sorted({c[0] for c in enc.code}):
        q = enc.sources[s]
        U = enc.data(q)
        sm = out[q] = SourceMap(len(U))
        runs = _split(pool, _runs(U, pool.U, pool.idx))
        for p, i, o, L in runs:
            nm = pool.names[i]
            for j in range(L):
                sm.src[p + j] = (nm, o + j)
        # 2a. a run continued word by word past its ends while the words differ only in an address field (the rest of
        # a function whose calls and globals moved, wherever the base has it)
        for p, i, o, L in runs:
            if (p - o) % 4:
                continue
            nm = pool.names[i]
            F = pool.U[pool.starts[i]:pool.starts[i + 1] if i + 1 < len(pool.starts) else len(pool.U)]
            for step, w in ((4, (p + L) & ~3), (-4, (p - 1) & ~3)):
                while 0 <= w and w + 4 <= len(U) and 0 <= w - p + o and w - p + o + 4 <= len(F):
                    u, = struct.unpack_from('<I', U, w)
                    v, = struct.unpack_from('<I', F, w - p + o)
                    x = addr_xor(u, v)
                    if x is None:
                        break
                    for j in range(4):
                        if sm.src[w + j] is None:
                            sm.src[w + j] = (nm, w - p + o + j)
                            sm.xor[w + j] = (x >> (8 * j)) & 0xff
                    w += step
        # 2b. the same code moved: the base's counterpart of the file, gaps of the same length between its runs
        cp = boot if q == 'SLUS_010.32' else q
        if cp not in img.files or img.files[cp][2]:
            continue
        B = img.read(cp)
        own = Pool([(cp, B)])
        anchors = [(p, o, L) for p, _, o, L in own.runs(U)] + [(len(U), len(B), 0)]
        pu = pb = 0
        for p, o, L in anchors:
            if p - pu == o - pb and p > pu and (pb - pu) % 4 == 0:
                for w in range((pu + 3) & ~3, p - 3, 4):
                    if all(sm.src[w + j] is not None for j in range(4)):
                        continue
                    wo = w - pu + pb
                    u, = struct.unpack_from('<I', U, w)
                    v, = struct.unpack_from('<I', B, wo)
                    x = addr_xor(u, v)
                    if x is None:
                        continue
                    for j in range(4):
                        if sm.src[w + j] is None:
                            sm.src[w + j] = (cp, wo + j)
                            sm.xor[w + j] = (x >> (8 * j)) & 0xff
            pu, pb = p + L, o + L
    start = dict(zip(pool.names, pool.starts))
    for q, sm in out.items():                           # (every byte checked: copied and fixed it is the USA one)
        U = enc.data(q)
        for x, w in enumerate(sm.src):
            if w is not None and pool.U[start[w[0]] + w[1]] ^ sm.xor[x] != U[x]:
                raise SystemExit(f'reloc {key}: {q}+{x:#x} does not come out as the USA byte')
    return out


def universal_map(enc, q):
    """{offset in USA code file q: (USA source path, offset)} for bytes of q that a file every base has as the USA one
    holds (runs of BLOCK bytes or more, found in the whole file)."""
    pool = enc.pool
    limit = pool.starts[len(enc.universal)] if len(enc.universal) < len(pool.starts) else len(pool.U)
    out = {}
    for p, i, o, L in _split(pool, _runs(enc.data(q), pool.U, pool.idx, limit)):
        nm = pool.names[i]
        for j in range(L):
            out[p + j] = (nm, o + j)
    return out


def _pieces(sm, a, b):
    """[[path, offset, length], ...] and [[position, hex XOR], ...] giving bytes a..b of a USA file from a SourceMap."""
    pieces, fix = [], []
    for x in range(a, b):
        nm, o = sm.src[x]
        if pieces and pieces[-1][0] == nm and pieces[-1][1] + pieces[-1][2] == o:
            pieces[-1][2] += 1
        else:
            pieces.append([nm, o, 1])
        if sm.xor[x]:
            if fix and fix[-1][0] + len(fix[-1][1]) == x - a:
                fix[-1][1].append(sm.xor[x])
            else:
                fix.append([x - a, bytearray([sm.xor[x]])])
    return pieces, [[p, bytes(h).hex()] for p, h in fix]


def relocate(enc, files, Pool, say=print):
    """Every code copy of `files` {path: ops} on each base of enc.bases; rewrites the 'r' operations (bytes some base
    cannot give: a 'c' copy of a file all bases have, else literal) and returns (reloc, fix, bytes literal)."""
    maps = {}
    for key, img in enc.bases.items():
        maps[key] = base_maps(enc, key, img, Pool)
        say(f'  {key}: code copies found in its executable, overlays and scripts')
    # Count occurrences in the output, rather than distinct source bytes: translated overlays can repeat a copy.
    enc.reloc_stats = {}
    for key, mp in maps.items():
        absent = fixed = 0
        for s, o, n in enc.code:
            sm = mp[enc.sources[s]]
            absent += sum(sm.src[x] is None for x in range(o, o + n))
            fixed += sum(v != 0 for v in sm.xor[o:o + n])
        enc.reloc_stats[key] = dict(absent=absent, fixed=fixed)
    univ = {}
    reloc = {key: {} for key in enc.bases}
    fix = {key: {} for key in enc.bases}
    new_code, remap, lost = [], {}, 0
    enc.usa_lit, enc.lost_ranges = set(), []          # (lost_ranges: USA file, start, end of what stays literal)
    for k, (s, o, n) in enumerate(enc.code):
        q = enc.sources[s]
        ok = [all(maps[key][q].src[x] is not None for key in enc.bases) for x in range(o, o + n)]
        ops = []
        p = 0
        while p < n:
            e = p
            while e < n and ok[e] == ok[p]:
                e += 1
            if ok[p]:
                kk = len(new_code)
                new_code.append([s, o + p, e - p])
                ops.append(['r', kk])
                for key in enc.bases:
                    pieces, fx = _pieces(maps[key][q], o + p, o + e)
                    reloc[key][str(kk)] = pieces
                    if fx:
                        fix[key][str(kk)] = fx
            else:
                if q not in univ:
                    univ[q] = universal_map(enc, q)
                um = univ[q]
                x = o + p
                while x < o + e:                        # 3. a file every base has: 'c'; the rest literal
                    y = x
                    if x in um:
                        nm, so = um[x]
                        while y < o + e and um.get(y) == (nm, so + y - x):
                            y += 1
                        ops.append(['c', enc.sid(nm), so, y - x])
                    else:
                        while y < o + e and y not in um:
                            y += 1
                        op = enc.lit(enc.data(q)[x:y])
                        enc.usa_lit.add(op[1])
                        enc.lost_ranges.append((q, x, y))
                        ops.append(op)
                        lost += y - x
                    x = y
            p = e
        remap[k] = ops
    for path in files:
        out = []
        for op in files[path]:
            out += remap[op[1]] if op[0] == 'r' else [op]
        files[path] = out
    enc.code = new_code
    return reloc, fix, lost


def reuse_outputs(enc, files, datas, eligible, targets, Pool):
    """Before relocation, replace matching runs of authored outputs with copies of earlier eligible outputs.

    Match complete files, not just literal operations: translated overlays also repeat source copies, whose
    relocation tables need only be stored once. Split the original operations around those matches, then discard
    code entries no operation uses. Whole source files, holes and the executable's rewritten table cannot supply a
    copy (the caller's eligible set); whole source files and holes cannot be replaced either.
    """
    import bisect
    order = [q for q in files if q in eligible]
    if not order:
        return 0
    pool = Pool([(q, datas[q]) for q in order])
    end = {q: pool.starts[i] + len(datas[q]) for i, q in enumerate(order)}
    saved = limit = 0
    for path in files:
        ops = files[path]
        if path in targets and limit and ops[0][0] not in 'sh':
            starts, pos = [], 0
            for op in ops:
                starts.append(pos)
                pos += enc.code[op[1]][2] if op[0] == 'r' else op[2] if op[0] == 'l' else op[3]

            def original(a, b):
                out = []
                while a < b:
                    i = bisect.bisect_right(starts, a) - 1
                    op = ops[i]
                    stop = min(b, starts[i + 1] if i + 1 < len(starts) else pos)
                    off, length = a - starts[i], stop - a
                    if off == 0 and stop == (starts[i + 1] if i + 1 < len(starts) else pos):
                        out.append(op)
                    elif op[0] == 'r':
                        s, o, _ = enc.code[op[1]]
                        enc.code.append([s, o + off, length])
                        out.append(['r', len(enc.code) - 1])
                    elif op[0] == 'l':
                        out.append(['l', op[1] + off, length])
                    else:
                        out.append([op[0], op[1], op[2] + off, length])
                    a = stop
                return out

            out, at = [], 0
            for p, i, o, length in _split(pool, _runs(datas[path], pool.U, pool.idx, limit)):
                out.extend(original(at, p))
                out.append(['o', pool.names[i], o, length])
                saved += length
                at = p + length
            out.extend(original(at, pos))
            files[path] = out
        if path in eligible:
            limit = end[path]
    # Keep the code table in first-use order. Splitting a copy and removing a duplicate must not leave unused
    # source bytes in relocate's intersection or its audit counts.
    code, ids = [], {}
    for ops in files.values():
        for op in ops:
            if op[0] == 'r':
                old = op[1]
                if old not in ids:
                    ids[old] = len(code)
                    code.append(enc.code[old])
                op[1] = ids[old]
    enc.code = code
    return saved


def compact(enc, files):
    """Rebuilds enc.blob with only the literal bytes the operations still use (in their order), the 'l' operations of
    `files` renumbered in place; returns {path: bytes of USA code still literal} (audit's lit_usa)."""
    blob = bytearray()
    lit_usa = {}
    def renumber(path, ops):
        new = []
        for op in ops:
            if op[0] == 'l':
                if op[1] in enc.usa_lit and path is not None:
                    lit_usa[path] = lit_usa.get(path, 0) + op[2]
                new.append(['l', len(blob), op[2]])
                blob.extend(enc.blob[op[1]:op[1] + op[2]])
            else:
                new.append(op)
        return new
    for path in files:
        files[path] = renumber(path, files[path])
    enc.blob = blob
    enc.usa_lit = set()
    return lit_usa


def copy_literal_sources(payload, matches, minimum=16):
    """Replace literals available verbatim on every base with existing 'r' copies.

    Developer audit/refinement pass: matches[base] is a sorted list of
    (blob offset, end offset, source path, source offset), verified against that
    base's own disc files. USA must be present. No new player operation or native
    dependency is needed. Original code/fix tables remain valid. Returns bytes
    removed from the literal blob; mutates payload and compacts its blob.
    """
    import bisect
    keys = list(matches)
    if 'us' not in matches:
        raise ValueError('literal copies require USA source evidence')
    if set(payload.get('reloc', {})) - set(keys):
        raise ValueError('literal copies require evidence for every supported base')
    starts = {}
    for key, spans in matches.items():
        end = 0
        for a, b, path, off in spans:
            if a < end or b <= a or off < 0 or b > len(payload['blob']):
                raise ValueError(f'invalid literal source spans for {key}')
            end = b
        starts[key] = [s[0] for s in spans]
    sources = {q: i for i, q in enumerate(payload['sources'])}
    old = payload['blob']
    blob = bytearray()
    saved = 0

    def literal(ops, a, b):
        if b > a:
            ops.append(['l', len(blob), b - a])
            blob.extend(old[a:b])

    def rewrite(ops):
        nonlocal saved
        out = []
        for op in ops:
            if op[0] != 'l':
                out.append(op)
                continue
            a, stop = op[1], op[1] + op[2]
            pending = a
            while a < stop:
                covering = {}
                end = stop
                next_start = stop
                for key in keys:
                    i = bisect.bisect_right(starts[key], a) - 1
                    spans = matches[key]
                    if i >= 0 and a < spans[i][1]:
                        covering[key] = spans[i]
                        end = min(end, spans[i][1])
                    elif i + 1 < len(spans):
                        next_start = min(next_start, spans[i + 1][0])
                if len(covering) != len(keys):
                    a = max(a + 1, next_start)
                    continue
                if end - a < minimum:
                    a = end
                    continue
                literal(out, pending, a)
                ua, _, q, o = covering['us']
                if q not in sources:
                    sources[q] = len(payload['sources'])
                    payload['sources'].append(q)
                k = len(payload['code'])
                payload['code'].append([sources[q], o + a - ua, end - a])
                out.append(['r', k])
                for key, (lo, _, path, off) in covering.items():
                    if key != 'us':
                        payload['reloc'].setdefault(key, {})[str(k)] = [[path, off + a - lo, end - a]]
                saved += end - a
                a = pending = end
            literal(out, pending, stop)
        return out

    for path in payload['files']:
        payload['files'][path] = rewrite(payload['files'][path])
    payload['license'] = rewrite(payload['license'])
    payload['blob'] = bytes(blob)
    return saved
