#!/usr/bin/env python3
"""Cross-check of two glTF exports of the same Digimon World MMD models:
tools/mmd.py (ours) against DW1ModelConverter (Operation-Decoded, MIT; theirs).

  python3 tools/compare_gltf.py OURS_DIR THEIRS_DIR [NAME ...] [--json OUT.json] [-v]

Both directories hold NAME.gltf files (ours: `tools/mmd.py gltf`, with .bin/.png next to
it; theirs: self-contained, base64 buffers and image).  Standard library only (the PNG
reader is borrowed from tools/mmd.py).  For each model it compares

  skeleton   bone count and parent of each bone
  geometry   per bone: the multiset of triangles (positions, UVs in texels, normals,
             vertex colors) and the material flags (double sided, unlit, blended);
             the unique vertex count is reported too
  texture    the decoded RGBA images (size and every pixel)
  world      the world matrices of every bone in the pose of slot 0 at t=0; the axis
             convention between the two is detected (one of the 48 signed permutations)
  anim       slots present, duration, local translation / rotation / scale of every bone at
             every tick of every animation (rotations as the angle between quaternions)
  meta       endless-loop start/end, sounds and texture moves ("extras" in theirs)

and prints per model identical / tolerance / DIFFERS with the first differing thing.
"""
import base64
import bisect
import collections
import itertools
import json
import math
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mmd  # noqa: E402  (png_read only)

FPS = 20.0
TOL_POS = 1e-3          # engine units (positions are integers; anything off is a real difference)
TOL_UV = 0.5            # texels
TOL_NRM = 1 / 2048      # normals are 4.12 fixed point
# The engine keeps rotations/translations/scales as int16 and carries momentum with integer
# remainder counters; theirs integrates in floats.  So up to one engine unit of difference
# (1/4096 turn = 0.088 deg for rotations, 1 for translations, 1/4096 for scales) is expected,
# up to a few units for the three Euler axes combined into one rotation angle.
TOL_ROT = 0.2           # degrees between two rotations
TOL_TRANS = 1.001
TOL_SCALE = 5e-4
TOL_TIME = 1e-4         # seconds
EXACT_ROT = 1e-3        # below this (degrees) a rotation counts as exactly equal (float32 noise)
EXACT_VAL = 1e-4


# ---------------------------------------------------------------- reading glTF
CT = {5120: ('b', 1), 5121: ('B', 1), 5122: ('h', 2), 5123: ('H', 2), 5125: ('I', 4), 5126: ('f', 4)}
NC = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


def read_uri(uri, base_dir):
    if uri.startswith('data:'):
        return base64.b64decode(uri.split(',', 1)[1])
    return open(os.path.join(base_dir, uri), 'rb').read()


class Gltf:
    def __init__(self, path):
        self.path = path
        self.dir = os.path.dirname(path)
        self.j = json.load(open(path))
        self.bufs = [read_uri(b['uri'], self.dir) for b in self.j['buffers']]
        self._cache = {}

    def acc(self, i):
        """Accessor i as a list of tuples (floats; normalized integers are scaled)."""
        if i in self._cache:
            return self._cache[i]
        a = self.j['accessors'][i]
        fmt, size = CT[a['componentType']]
        n = NC[a['type']]
        v = self.j['bufferViews'][a['bufferView']]
        buf = self.bufs[v['buffer']]
        off = v.get('byteOffset', 0) + a.get('byteOffset', 0)
        stride = v.get('byteStride') or size * n
        norm = a.get('normalized')
        scale = {'B': 255.0, 'H': 65535.0, 'b': 127.0, 'h': 32767.0}.get(fmt, 1.0) if norm else 1.0
        out = []
        for k in range(a['count']):
            t = struct.unpack_from('<%d%s' % (n, fmt), buf, off + k * stride)
            out.append(tuple(x / scale for x in t) if norm else t)
        self._cache[i] = out
        return out

    def image_size(self):
        """Width and height of the first image (PNG header); 256x128 without image."""
        if not self.j.get('images'):
            return 256, 128
        d = read_uri(self.j['images'][0]['uri'], self.dir)
        return struct.unpack_from('>II', d, 16)

    def image(self):
        im = self.j['images'][0]
        d = read_uri(im['uri'], self.dir)
        tmp = os.path.join(os.environ.get('TMPDIR', '/var/tmp'), f'cmpgltf_{os.getpid()}.png')
        open(tmp, 'wb').write(d)
        try:
            return mmd.png_read(tmp)
        finally:
            os.remove(tmp)


# ---------------------------------------------------------------- small linear algebra
def q_mat(q):
    x, y, z, w = q
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]


def mm(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def mv(a, v):
    return [sum(a[i][k] * v[k] for k in range(3)) for i in range(3)]


def trs_mat(t, q, s):
    """(R·S, t) of a node."""
    R = q_mat(q)
    return [[R[i][j] * s[j] for j in range(3)] for i in range(3)], list(t)


def compose(parent, local):
    (Pm, Pt), (Lm, Lt) = parent, local
    m = mm(Pm, Lm)
    t = [a + b for a, b in zip(mv(Pm, Lt), Pt)]
    return m, t


def qnorm(q):
    n = math.sqrt(sum(x * x for x in q)) or 1.0
    return tuple(x / n for x in q)


def q_angle_deg(a, b):
    d = abs(sum(x * y for x, y in zip(qnorm(a), qnorm(b))))
    return math.degrees(2 * math.acos(min(1.0, d)))


def slerp(a, b, u):
    d = sum(x * y for x, y in zip(a, b))
    if d < 0:
        b = tuple(-x for x in b); d = -d
    if d > 0.9995:
        return qnorm(tuple(x + u * (y - x) for x, y in zip(a, b)))
    th = math.acos(d)
    s = math.sin(th)
    wa, wb = math.sin((1 - u) * th) / s, math.sin(u * th) / s
    return tuple(wa * x + wb * y for x, y in zip(a, b))


SIGNED_PERMS = []
for perm in itertools.permutations(range(3)):
    for signs in itertools.product((1, -1), repeat=3):
        SIGNED_PERMS.append([[signs[i] if perm[i] == j else 0 for j in range(3)] for i in range(3)])


# ---------------------------------------------------------------- model abstraction
class Model:
    """Bones in game order; the same for both exporters.  `flip`: the matrix of a root
    node above the skeleton (ours: 180 degrees around X), identity if absent."""

    def __init__(self, g, kind):
        self.g, self.kind = g, kind
        j = g.j
        nodes = j['nodes']
        self.nodes = nodes
        parent = {}
        for i, n in enumerate(nodes):
            for c in n.get('children', []):
                parent[c] = i
        if kind == 'ours':
            assert nodes[0]['name'] == 'dw_root_flip'
            self.first = 1
            self.flip = q_mat(nodes[0]['rotation'])
        else:
            self.first = 0
            self.flip = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        self.nb = len(nodes) - self.first
        self.tex_w, self.tex_h = g.image_size()
        self.parent = [(parent[self.first + b] - self.first if parent.get(self.first + b, -1) >= self.first else -1)
                       for b in range(self.nb)]
        self.mesh = [nodes[self.first + b].get('mesh') for b in range(self.nb)]
        # animations by slot
        self.anims = {}
        for a in j.get('animations', []):
            if kind == 'ours':
                slot = a['extras']['dw_slot']
            else:
                slot = int(a['name'].split('-')[1])
            if not a.get('channels'):
                continue                      # theirs lists empty slots as empty animations
            self.anims[slot] = a
        self._ev = {}

    # -- rest TRS of a node
    def rest(self, b):
        n = self.nodes[self.first + b]
        return (n.get('translation', [0, 0, 0]), n.get('rotation', [0, 0, 0, 1]), n.get('scale', [1, 1, 1]))

    def evaluator(self, slot):
        """Per bone: ((times, values) or None) for translation, rotation, scale."""
        if slot in self._ev:
            return self._ev[slot]
        a = self.anims[slot]
        ev = [dict() for _ in range(self.nb)]
        for ch in a['channels']:
            s = a['samplers'][ch['sampler']]
            b = ch['target']['node'] - self.first
            ev[b][ch['target']['path']] = ([x[0] for x in self.g.acc(s['input'])], self.g.acc(s['output']))
        self._ev[slot] = ev
        return ev

    def trs_at(self, slot, b, t):
        e = self.evaluator(slot)[b]
        rt, rq, rs = self.rest(b)
        out = []
        for path, rest in (('translation', rt), ('rotation', rq), ('scale', rs)):
            if path not in e:
                out.append(tuple(rest)); continue
            times, vals = e[path]
            i = bisect.bisect_right(times, t + 1e-9) - 1
            if i < 0:
                out.append(tuple(vals[0]))
            elif i >= len(times) - 1:
                out.append(tuple(vals[-1]))
            else:
                u = (t - times[i]) / (times[i + 1] - times[i])
                a, b2 = vals[i], vals[i + 1]
                if path == 'rotation':
                    out.append(slerp(qnorm(a), qnorm(b2), u))
                else:
                    out.append(tuple(x + u * (y - x) for x, y in zip(a, b2)))
        return out

    def duration(self, slot):
        a = self.anims[slot]
        return max(self.g.acc(s['input'])[-1][0] for s in a['samplers'])

    def world(self, slot, t):
        """World matrices of every bone (without the flip node) in the pose slot@t."""
        w = [None] * self.nb
        for b in range(self.nb):
            tr, q, s = self.trs_at(slot, b, t)
            loc = trs_mat(tr, q, s)
            p = self.parent[b]
            w[b] = loc if p < 0 else compose(w[p], loc)
        return w

    # -- geometry
    def bone_tris(self, b):
        """Triangles of a bone: list of (corners, flags); a corner is (pos, uv_texels, normal*4096,
        color).  Positions are the engine's integers."""
        m = self.mesh[b]
        if m is None:
            return []
        g = self.g
        out = []
        tex = g.j.get('images')
        for p in g.j['meshes'][m]['primitives']:
            at = p['attributes']
            pos = g.acc(at['POSITION'])
            nrm = g.acc(at['NORMAL']) if 'NORMAL' in at else None
            uv = g.acc(at['TEXCOORD_0']) if 'TEXCOORD_0' in at else None
            col = g.acc(at['COLOR_0']) if 'COLOR_0' in at else None
            mat = g.j['materials'][p['material']]
            flags = (bool(mat.get('doubleSided')), 'KHR_materials_unlit' in mat.get('extensions', {}),
                     mat.get('alphaMode') == 'BLEND', 'baseColorTexture' in mat.get('pbrMetallicRoughness', {}))
            if 'indices' in p:
                idx = [i[0] for i in g.acc(p['indices'])]
            else:
                idx = list(range(len(pos)))
            for k in range(0, len(idx), 3):
                cs = []
                for i in idx[k:k + 3]:
                    cs.append((tuple(int(round(x)) for x in pos[i]),
                               (round(uv[i][0] * self.tex_w), round(uv[i][1] * self.tex_h)) if uv else None,
                               tuple(int(round(x * 4096)) for x in nrm[i]) if nrm else None,
                               tuple(int(round(x * 255)) for x in col[i]) if col else None))
                out.append((cs, flags))
        return out



def canon(cs):
    k = min(range(3), key=lambda i: cs[i])
    return tuple(cs[k:] + cs[:k])


# ---------------------------------------------------------------- comparisons
class Result:
    def __init__(self):
        self.items = []          # (aspect, status, detail)

    def add(self, aspect, status, detail=''):
        self.items.append((aspect, status, detail))

    def status(self):
        s = [i[1] for i in self.items]
        return 'DIFFERS' if 'diff' in s else 'tolerance' if 'tol' in s else 'identical'

    def first_diff(self):
        for a, s, d in self.items:
            if s == 'diff':
                return f'{a}: {d}'
        for a, s, d in self.items:
            if s == 'tol':
                return f'{a}: {d}'
        return ''


def cmp_skeleton(o, t, r):
    if o.nb != t.nb:
        r.add('skeleton', 'diff', f'bones {o.nb} vs {t.nb}')
        return False
    for b in range(o.nb):
        if o.parent[b] != t.parent[b]:
            r.add('skeleton', 'diff', f'parent of bone {b}: {o.parent[b]} vs {t.parent[b]}')
            return False
    mo = [b for b in range(o.nb) if o.mesh[b] is not None]
    mt = [b for b in range(t.nb) if t.mesh[b] is not None]
    if mo != mt:
        r.add('skeleton', 'diff', f'bones with a mesh {mo} vs {mt}')
        return False
    r.add('skeleton', 'same', f'{o.nb} bones')
    return True


def cmp_geometry(o, t, r, notes):
    worst = 'same'
    verts_o = verts_t = 0
    for b in range(o.nb):
        a, c = o.bone_tris(b), t.bone_tris(b)
        if not a and not c:
            continue
        verts_o += len({cs[i][0] for cs, _ in a for i in range(3)})
        verts_t += len({cs[i][0] for cs, _ in c for i in range(3)})
        if len(a) != len(c):
            r.add('geometry', 'diff', f'bone {b}: triangles {len(a)} vs {len(c)}')
            return
        # level 1: positions only, with winding
        for lvl, name in ((lambda cs: tuple(x[0] for x in cs), 'positions'),
                          (lambda cs: tuple((x[0], x[1]) for x in cs), 'positions+UV'),):
            ka = collections.Counter(canon([lvl([x])[0] for x in cs]) for cs, _ in a)
            kc = collections.Counter(canon([lvl([x])[0] for x in cs]) for cs, _ in c)
            if ka != kc:
                # winding?
                kr = collections.Counter(canon([lvl([x])[0] for x in reversed(cs)]) for cs, _ in c)
                if ka == kr:
                    r.add('geometry', 'diff', f'bone {b}: {name} equal only with the winding reversed')
                else:
                    d = next(iter((ka - kc) or (kc - ka)))
                    r.add('geometry', 'diff', f'bone {b}: {name} differ ({sum((ka - kc).values())} triangles only in ours, '
                                              f'{sum((kc - ka).values())} only in theirs), e.g. {d}')
                return
        # level 2: UV tolerance is rounding to texels already; normals / colors / flags
        ka = collections.Counter(canon(cs) for cs, _ in a)
        kc = collections.Counter(canon(cs) for cs, _ in c)
        if ka != kc:
            # which field differs?
            fld = ('normal', 'color')
            diffs = collections.Counter()
            na = collections.defaultdict(list)
            for k in (ka - kc):
                na[tuple(x[0] for x in k)].append(k)
            nc = collections.defaultdict(list)
            for k in (kc - ka):
                nc[tuple(x[0] for x in k)].append(k)
            ex = None
            for pk, lst in na.items():
                for ko in lst:
                    for kt in nc.get(pk, []):
                        for i in range(3):
                            for f, nm in ((2, 'normal'), (3, 'color')):
                                if ko[i][f] != kt[i][f]:
                                    diffs[nm] += 1
                                    ex = ex or f'{nm} ours {ko[i][f]} theirs {kt[i][f]} at {ko[i][0]}'
            nn = sum((ka - kc).values())
            kinds = ', '.join(f'{k} x{v}' for k, v in diffs.items()) or 'unknown'
            # normals within tolerance?
            r.add('geometry', 'diff' if not (len(diffs) == 1 and 'normal' in diffs and nn < 1) else 'tol',
                  f'bone {b}: {nn} triangles differ in {kinds}; e.g. {ex}')
            worst = 'diff'
            notes['normals'] += nn
            continue
        fa = collections.Counter((canon(cs), fl) for cs, fl in a)
        fc = collections.Counter((canon(cs), fl) for cs, fl in c)
        if fa != fc:
            x = next(iter((fa - fc) or (fc - fa)))
            r.add('geometry', 'diff', f'bone {b}: material flags (double sided, unlit, blend, textured) differ: '
                                      f'ours {sorted({f for (_, f) in fa - fc})} theirs {sorted({f for (_, f) in fc - fa})}')
            return
    if worst == 'same':
        notes['verts'] = (verts_o, verts_t)
        r.add('geometry', 'same', f'triangles, positions, UVs, normals, colors, flags; unique vertices {verts_o}/{verts_t}')


def raster(uv, w, h):
    """Texels whose centre lies in the UV triangle (edges inclusive)."""
    xs, ys = [u[0] for u in uv], [u[1] for u in uv]
    for y in range(max(0, min(ys)), min(h - 1, max(ys)) + 1):
        for x in range(max(0, min(xs)), min(w - 1, max(xs)) + 1):
            e = [(uv[(i + 1) % 3][0] - uv[i][0]) * (y + .5 - uv[i][1]) - (uv[(i + 1) % 3][1] - uv[i][1]) * (x + .5 - uv[i][0])
                 for i in range(3)]
            if all(v >= 0 for v in e) or all(v <= 0 for v in e):
                yield x, y


def face_rows(o):
    """texel -> set of CLUT rows of the faces that sample it.  The row of every face is in the
    name of our material (dw_m<mode>_f<flag>_p<row>_t<tsb>); the UVs are identical in both exports."""
    rows = collections.defaultdict(set)
    for b in range(o.nb):
        m = o.mesh[b]
        if m is None:
            continue
        for p in o.g.j['meshes'][m]['primitives']:
            if 'TEXCOORD_0' not in p['attributes']:
                continue
            name = o.g.j['materials'][p['material']]['name']
            row = int(name.split('_p')[1][:2])
            uv = o.g.acc(p['attributes']['TEXCOORD_0'])
            idx = [i[0] for i in o.g.acc(p['indices'])]
            for k in range(0, len(idx), 3):
                tri = [(round(uv[i][0] * o.tex_w), round(uv[i][1] * o.tex_h)) for i in idx[k:k + 3]]
                for xy in raster(tri, o.tex_w, o.tex_h):
                    rows[xy].add(row)
    return rows


def cmp_texture(o, t, r, notes, alltim):
    """Decoded RGBA images.  Colours are compared as 5-bit values (ours replicates the top bits
    when expanding to 8, theirs shifts: 31 -> 255 against 248) and alpha only as zero / non-zero
    (theirs puts the PSX STP bit in alpha: 255 or 127).  Where the two images differ on a texel
    that some face samples, the face's own CLUT row (from ours) decides who is right."""
    try:
        wo, ho, po = o.g.image()
        wt, ht, pt = t.g.image()
    except (KeyError, IndexError) as e:
        r.add('texture', 'diff', f'no image: {e!r}')
        return
    if (wo, ho) != (wt, ht):
        r.add('texture', 'diff', f'size {wo}x{ho} vs {wt}x{ht}')
        return
    kinds = collections.Counter()
    differ = []
    for i in range(wo * ho):
        a, c = bytes(po[4 * i:4 * i + 4]), bytes(pt[4 * i:4 * i + 4])
        if a == c or (a[3] == 0 and c[3] == 0):
            continue
        if (a[3] == 0) == (c[3] == 0) and all(x >> 3 == y >> 3 for x, y in zip(a[:3], c[:3])):
            kinds['expansion' if a[3] == c[3] else 'expansion+stp-alpha'] += 1
        else:
            differ.append(i)
    if not differ:
        notes['tex'] = dict(kinds)
        r.add('texture', 'tol' if kinds else 'same',
              f'{wo}x{ho}; ' + (f'same up to {dict(kinds)} (5-bit colours equal)' if kinds else 'every pixel'))
        return
    # adjudicate with the CLUT of the faces
    tim = mmd.Tim4(mmd.alltim_entry(open(alltim, 'rb').read(), o.g.j['extras']['dw_type']))
    rows = face_rows(o)
    wrong = dict(ours=0, theirs=0)
    unused = 0
    block_rows = collections.defaultdict(set)      # 8x8 block -> CLUT rows of the faces that sample it
    for (bx, by), rs_ in rows.items():
        block_rows[(bx // 8, by // 8)] |= rs_
    in_multi = 0
    ex = {}
    for i in differ:
        xy = (i % wo, i // wo)
        rs = rows.get(xy)
        if not rs:
            unused += 1
            continue
        if len(rs) > 1:
            kinds['shared by faces with different rows'] += 1
            continue
        row = next(iter(rs))
        c15 = tim.pal[min(row, tim.ch - 1)][tim.idx[i]]
        want = mmd.c15_to_rgba(c15)
        for who, px in (('ours', po), ('theirs', pt)):
            got = bytes(px[4 * i:4 * i + 4])
            ok = (got[3] == 0) == (want[3] == 0) and (want[3] == 0 or all(x >> 3 == y >> 3 for x, y in zip(got[:3], want[:3])))
            if not ok:
                wrong[who] += 1
                if who == 'theirs' and len(block_rows[(xy[0] // 8, xy[1] // 8)]) > 1:
                    in_multi += 1       # the block really holds two palettes in the data
                ex.setdefault(who, f'x={xy[0]} y={xy[1]} row {row}: image {tuple(got)}, face CLUT {tuple(want)}')
    notes['tex'] = dict(kinds, unused=unused, wrong_ours=wrong['ours'], wrong_theirs=wrong['theirs'], theirs_in_multirow_block=in_multi)
    used = len(differ) - unused
    base = f'{wo}x{ho}; {len(differ)} texels differ in colour or transparency ({unused} no face samples, {used} sampled)'
    if wrong['ours'] or wrong['theirs']:
        who = 'theirs' if wrong['theirs'] and not wrong['ours'] else 'ours' if wrong['ours'] and not wrong['theirs'] else 'both'
        r.add('texture', 'diff', f'{base}; texels not matching the face\'s own CLUT: ours {wrong["ours"]}, theirs {wrong["theirs"]}'
                                 + ''.join(f'; {k}: {v}' for k, v in ex.items()))
    else:
        r.add('texture', 'tol', f'{base}; all agree with the faces\' CLUT where sampled')


def detect_axes(o, t, r, slot, tm):
    """Find the signed permutation P with  ours_world = flip * world  vs  theirs_world: the global
    axis convention.  Returns the residual."""
    wo, wt = o.world(slot, tm), t.world(slot, tm)
    best = None
    for P in SIGNED_PERMS:
        err = 0.0
        for b in range(o.nb):
            (Mo, to), (Mt, tt) = wo[b], wt[b]
            A = mm(o.flip, Mo)
            Tt = mv(o.flip, to)
            B = mm(P, Mt)
            Bt = mv(P, tt)
            err = max(err, max(abs(A[i][j] - B[i][j]) for i in range(3) for j in range(3)),
                      max(abs(Tt[i] - Bt[i]) for i in range(3)))
        if best is None or err < best[0]:
            best = (err, P)
    return best


def desc_perm(P):
    return ' '.join('+-'[row[j] < 0] + 'xyz'[j] for row in P for j in range(3) if row[j])


def cmp_world(o, t, r, notes):
    if 0 not in o.anims or 0 not in t.anims:
        r.add('world', 'diff', 'no slot 0')
        return
    err, P = detect_axes(o, t, r, 0, 0.0)
    notes['axes'] = desc_perm(P)
    ident = all(P[i][j] == (i == j) for i in range(3) for j in range(3))
    # our export puts a root flip node above the skeleton: ours_world = flip * (our chain) must equal P * theirs.
    if err > 1e-3:
        r.add('world', 'diff', f'world matrices of slot 0 at t=0 do not match under any axis convention (best residual {err:.4g}, {desc_perm(P)})')
    else:
        r.add('world', 'same' if err < 1e-4 else 'tol',
              f'slot 0 pose; theirs x{desc_perm(P)} = ours (with the dw_root_flip node); residual {err:.2g}')


def tick_times(o, t, slot):
    d = min(o.duration(slot), t.duration(slot))
    return [k / FPS for k in range(int(d * FPS + 1e-6) + 1)]


def cmp_anims(o, t, r, notes):
    """Local translation / rotation / scale of every bone at every tick (k/20 s) of every slot.
    Theirs keeps keyframes only (linear between them, quaternions slerped), ours one sample per
    tick; so rotations are judged at their keyframe ticks (where their data is exact) and, apart,
    at the ticks between keyframes (where slerp is not the engine's linear Euler motion)."""
    so, st = set(o.anims), set(t.anims)
    if so != st:
        r.add('anim', 'diff', f'slots only in ours {sorted(so - st)}, only in theirs {sorted(st - so)}')
        return
    key = dict(rot=0.0, tr=0.0, sc=0.0)
    mid = dict(rot=0.0, tr=0.0, sc=0.0)
    first = None
    bad_slots = set()
    n_cmp = 0
    trailing = beyond = 0
    slot_mid = {}
    for slot in sorted(so):
        do, dt = o.duration(slot), t.duration(slot)
        endless = 'loop_jump_frame' in o.anims[slot].get('extras', {})
        if abs(do - dt) > TOL_TIME:
            if endless and dt > do:
                beyond += 1               # theirs goes on with the instructions after an endless loop (the engine never reaches them)
            elif abs(dt - do - 1 / FPS) < TOL_TIME:
                trailing += 1             # theirs has one sample more than the engine plays (tick N + 1)
            else:
                bad_slots.add(slot)
                first = first or f'slot {slot}: duration ours {do:.3f}s theirs {dt:.3f}s ({round(do * FPS) + 1} vs {round(dt * FPS) + 1} samples)'
        key_times = set()
        for e in t.evaluator(slot):
            for path in ('translation', 'rotation', 'scale'):
                if path in e:
                    key_times.update(round(x * FPS) for x in e[path][0])
        for k, tm in enumerate(tick_times(o, t, slot)):
            acc = key if k in key_times else mid
            for b in range(o.nb):
                (to_, qo, so_), (tt_, qt, st_) = o.trs_at(slot, b, tm), t.trs_at(slot, b, tm)
                rot = q_angle_deg(qo, qt)
                tr = max(abs(x - y) for x, y in zip(to_, tt_))
                sc = max(abs(x - y) for x, y in zip(so_, st_))
                n_cmp += 1
                for nm, v in (('rot', rot), ('tr', tr), ('sc', sc)):
                    if v > acc[nm]:
                        acc[nm] = v
                if acc is mid and rot > slot_mid.get(slot, 0):
                    slot_mid[slot] = rot
                if (acc is key and (rot > TOL_ROT or tr > TOL_TRANS or sc > TOL_SCALE)) or tr > TOL_TRANS or sc > TOL_SCALE:
                    bad_slots.add(slot)
                    first = first or (f'slot {slot} tick {k} bone {b}: rot {rot:.3f} deg, translation {tr:.3f}, scale {sc:.4f}'
                                      f'\n      ours   t={tuple(round(x, 3) for x in to_)} q={tuple(round(x, 4) for x in qo)} s={tuple(round(x, 3) for x in so_)}'
                                      f'\n      theirs t={tuple(round(x, 3) for x in tt_)} q={tuple(round(x, 4) for x in qt)} s={tuple(round(x, 3) for x in st_)}')
    notes['anim'] = dict(key=key, mid=mid, slots=len(so), bad=sorted(bad_slots), trailing=trailing, beyond=beyond, n=n_cmp, slot_mid=slot_mid)
    if bad_slots:
        r.add('anim', 'diff', f'{len(bad_slots)} of {len(so)} slots differ; first: {first}')
    elif mid['rot'] > EXACT_ROT or trailing or beyond or key['rot'] > EXACT_ROT or max(key['tr'], key['sc'], mid['tr'], mid['sc']) > EXACT_VAL:
        r.add('anim', 'tol', f'{len(so)} slots; at their keyframes max {key["rot"]:.4f} deg; between keyframes max {mid["rot"]:.3f} deg '
                             f'(slerp vs linear Euler)' + (f'; {trailing} slots have one trailing sample in theirs' if trailing else '')
                             + (f'; {beyond} endless loops continue past the loop end in theirs (unreachable in the engine)' if beyond else ''))
    else:
        r.add('anim', 'same', f'{len(so)} slots, {n_cmp} bone samples')


def cmp_meta(o, t, r, notes):
    """Endless loop, sounds, texture moves.  Theirs: extras endlessStart/End (seconds, strings),
    sounds [{time, vabId, soundId}], textures [{time, srxX, srcY, destX, destY, width, height}].
    Ours: loop_jump_frame/loop_end_frame (1-based frames), sounds [{tick, bank, note}],
    texture_moves [{tick, src, size, dst}]."""
    bad = []
    dropped = 0
    for slot in sorted(set(o.anims) & set(t.anims)):
        eo = o.anims[slot].get('extras', {})
        et = t.anims[slot].get('extras', {})
        # loops: theirs time = (frame - 1) / 20
        lo = (eo['loop_jump_frame'], eo['loop_end_frame']) if 'loop_jump_frame' in eo else None
        lt = None
        if 'endlessStart' in et:
            lt = (round(float(et['endlessStart']) * FPS) + 1, round(float(et['endlessEnd']) * FPS) + 1)
        if lo != lt:
            bad.append(f'slot {slot}: endless loop (start frame, end frame) ours {lo} theirs {lt}')
            continue
        last = round(float(et['endlessEnd']) * FPS) if 'endlessEnd' in et else None   # their events after an endless loop are unreachable
        so = sorted((s['tick'], s['bank'], s['note']) for s in eo.get('sounds', []))
        st = sorted((round(s['time'] * FPS), s['vabId'], s['soundId']) for s in et.get('sounds', []))
        xo = sorted((s['tick'], tuple(s['src']), tuple(s['size']), tuple(s['dst'])) for s in eo.get('texture_moves', []))
        xt = sorted((round(s['time'] * FPS), (s['srxX'], s['srcY']), (s['width'], s['height']), (s['destX'], s['destY']))
                    for s in et.get('textures', []))
        if last is not None:
            # after the loop end theirs goes on with the instructions that follow the loop: drop what is later;
            # an event on the very tick of the loop end that follows the loop_end instruction is not ours either
            st2 = [e for e in st if e[0] < last or (e[0] == last and e in so)]
            xt2 = [e for e in xt if e[0] < last or (e[0] == last and e in xo)]
            if (st2, xt2) != (st, xt):
                dropped += 1
            st, xt = st2, xt2
        if so != st:
            bad.append(f'slot {slot}: sounds (tick, bank, note) ours {so} theirs {st}')
            continue
        if xo != xt:
            bad.append(f'slot {slot}: texture moves (tick, src, size, dst) ours {xo} theirs {xt}')
    notes['meta_bad'] = len(bad)
    if bad:
        r.add('meta', 'diff', f'{len(bad)} slots differ; first: {bad[0]}')
    elif dropped:
        r.add('meta', 'tol', f'loops, sounds, texture moves; {dropped} endless loops are followed by events in theirs the engine never reaches')
    else:
        r.add('meta', 'same', 'loops, sounds, texture moves')


def compare_model(name, odir, tdir, notes, alltim):
    r = Result()
    o = Model(Gltf(os.path.join(odir, name + '.gltf')), 'ours')
    t = Model(Gltf(os.path.join(tdir, name + '.gltf')), 'theirs')
    if cmp_skeleton(o, t, r):
        cmp_geometry(o, t, r, notes)
        cmp_texture(o, t, r, notes, alltim)
        cmp_world(o, t, r, notes)
        cmp_anims(o, t, r, notes)
        cmp_meta(o, t, r, notes)
    return r


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    verbose = '-v' in sys.argv
    outj = None
    alltim = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'extracted', 'CHDAT', 'ALLTIM.TIM')
    if '--alltim' in sys.argv:
        alltim = sys.argv[sys.argv.index('--alltim') + 1]
        args.remove(alltim)
    if '--json' in sys.argv:
        outj = sys.argv[sys.argv.index('--json') + 1]
        args.remove(outj)
    if len(args) < 2:
        raise SystemExit(__doc__)
    odir, tdir, names = args[0], args[1], args[2:]
    if not names:
        names = sorted(os.path.splitext(f)[0] for f in os.listdir(odir) if f.endswith('.gltf'))
        names = [n for n in names if os.path.exists(os.path.join(tdir, n + '.gltf'))]
    summary = collections.Counter()
    per_aspect = collections.defaultdict(collections.Counter)
    axes = collections.Counter()
    tot = collections.defaultdict(float)
    report = {}
    for n in names:
        notes = collections.defaultdict(int)
        try:
            r = compare_model(n, odir, tdir, notes, alltim)
        except Exception as e:  # keep going over the other models
            r = Result(); r.add('error', 'diff', repr(e))
        st = r.status()
        summary[st] += 1
        worst = {}
        for a, s, _ in r.items:
            rank = {'same': 0, 'tol': 1, 'diff': 2}[s]
            if rank >= worst.get(a, (-1, ''))[0]:
                worst[a] = (rank, s)
        for a, (_, s) in worst.items():
            per_aspect[a][s] += 1
        an = notes.get('anim')
        if an:
            tot['anim slots'] += an['slots']; tot['anim slots differing'] += len(an['bad'])
            tot['anim bone samples'] += an['n']
            tot['max rot at keyframes (deg)'] = max(tot['max rot at keyframes (deg)'], an['key']['rot'])
            tot['max rot between keyframes (deg)'] = max(tot['max rot between keyframes (deg)'], an['mid']['rot'])
            tot['max translation (units)'] = max(tot['max translation (units)'], an['key']['tr'], an['mid']['tr'])
            tot['slots with slerp error > 1 deg between keyframes'] += sum(1 for v in an['slot_mid'].values() if v > 1)
            tot['slots with slerp error > 10 deg between keyframes'] += sum(1 for v in an['slot_mid'].values() if v > 10)
            tot['slots with a trailing sample in theirs'] += an['trailing']
            tot['endless loops continued past the end in theirs'] += an['beyond']
        tx = notes.get('tex')
        if tx:
            tot['texels wrong vs the faces CLUT, ours'] += tx.get('wrong_ours', 0)
            tot['texels wrong vs the faces CLUT, theirs'] += tx.get('wrong_theirs', 0)
            tot['  of which in 8x8 blocks that really hold two palettes'] += tx.get('theirs_in_multirow_block', 0)
        if 'verts' in notes:
            tot['unique vertices ours'] += notes['verts'][0]; tot['unique vertices theirs'] += notes['verts'][1]
        if 'axes' in notes:
            axes[notes['axes']] += 1
        report[n] = dict(status=st, items=r.items)
        print(f'{n:6s} {st:9s} {r.first_diff()}' if st != 'identical' else f'{n:6s} identical')
        if verbose:
            for a, s, d in r.items:
                print(f'         {a:9s} {s:5s} {d}')
    print(f'\n{len(names)} models: ' + ', '.join(f'{k} {v}' for k, v in summary.items()))
    for a, c in per_aspect.items():
        print(f'  {a:9s} ' + ', '.join(f'{k} {v}' for k, v in c.items()))
    print('  axis convention (theirs -> ours):', dict(axes))
    for k, v in tot.items():
        print(f'  {k}: {v:.4g}' if isinstance(v, float) and v != int(v) else f'  {k}: {int(v)}')
    if outj:
        json.dump(report, open(outj, 'w'), indent=1)


if __name__ == '__main__':
    main()
