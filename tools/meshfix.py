#!/usr/bin/env python3
"""Mesh fixes for imported models: piece splitting, bone welding, look-preserving decimation (library).

The import pipeline (tools/import_batch.py, tools/mmdport.py) turns a source game's model into a DW1
partner MMD. DW1's model format has hard budgets (docs/mods/models.md § 6): at most 713 primitives
and 34 bones, at most 172 vertices in one TMD object (one object per bone, the largest of the 178
originals). A model over a budget used to be skipped or had its smallest faces dropped. These are the
automatic rules that bring a model under the budgets, run on the player's own disc data at patch time
(no model data is stored anywhere; a spec only records the parameters):

  split_pieces(model)      a piece over 172 vertices becomes two or more pieces: the faces are cut
                           by position (recursive median cut), each part hangs from a *helper bone*
                           that is a child of the piece's own bone with a zero offset and no
                           rotation, so it moves with it exactly. Vertices on the cut are repeated in
                           both parts (same position, same normal, same UV and palette row): no crack.
  weld_bones(model, n)     the least important bones (small piece, little motion relative to the
                           parent, a leaf) are welded into their parent, in the first idle pose, until
                           the model has at most n bones.
  decimate(model, n)       quadric edge collapse down to n primitives. The faces are triangles
                           (a quad is its two triangles); a collapse moves a vertex onto the other end
                           of an edge, so every surviving corner keeps its own UV, normal and palette
                           row. Vertices on a seam (UV discontinuity, another palette row or blend
                           mode, an open boundary) only collapse along the seam; a vertex where seams
                           meet never moves. The cost is the quadric error plus a texture term
                           (the removed area times its texture detail, and the stretch of the faces
                           that move). Afterwards triangle pairs are merged into quads again: halves of
                           a surviving quad exactly, other pairs by angle, convexity, UVs, normals and
                           palette row, so the primitive count that is budgeted is the final one.
  compare(before, after)   software renders (front, side, 3/4 and back, textured) of both and the
                           measured error (silhouette mismatch, colour difference).

`apply(model, params)` runs the rules in this order: weld, decimate, split. `params` is a dict
(`bones`, `prims`, `decimate`, `quad_angle`, `kappa`, ...) that import_batch.py puts into the spec so a
rebuild from the spec does the same.
"""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import copy
import heapq
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mmd  # noqa: E402
import mmdport  # noqa: E402

MAX_VERTS_PER_OBJECT = mmdport.MAX_VERTS_PER_OBJECT      # 172
MAX_PRIMS = 713
MAX_BONES = 34                                           # a partner: the entity + 33 model bones
MAX_OBJECTS = 30
IDENTITY_Q = mmdport.IDENTITY_Q


# ------------------------------------------------------------------ small vector helpers
def _sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def _add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def _dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def _cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def _len(a): return math.sqrt(_dot(a, a))


def _vkey(v):
    """The identity of a vertex position in the TMD: rounded to the integer units it stores (build_tmd)."""
    return (int(round(v[0])), int(round(v[1])), int(round(v[2])))


def _pkey(v):
    """The identity of a position while editing: two decimals, so the result does not depend on the scale a
    model happens to be loaded at (a spec rebuild loads it at the final scale)."""
    return (round(v[0], 2), round(v[1], 2), round(v[2], 2))


def unique_verts(bone):
    return len({_vkey(v) for v in bone['verts']})


def prim_count(model):
    return sum(len(b['prims']) for b in model.bones)


def vert_count(model):
    return sum(unique_verts(b) for b in model.bones)


# ------------------------------------------------------------------ poses
def _pose_frame(model):
    a = model.anims.get(getattr(model, 'idle', None) or 'anim_00')
    if a is None and model.anims:
        a = next(iter(model.anims.values()))
    return a.frames[0] if a is not None and a.frames else None


def _local(model, i, frame):
    b = model.bones[i]
    if frame is None:
        return b.get('rest', IDENTITY_Q), b['offset'], (1.0, 1.0, 1.0)
    return frame[i]


def _mat(q, t, s):
    R = mmd.quat_matrix(q)
    return [[R[r][c] * s[c] for c in range(3)] + [t[r]] for r in range(3)] + [[0, 0, 0, 1]]


def world_matrices(model, frame='idle'):
    """4x4 matrices (rows) of every bone in the first idle pose (or the rest pose)."""
    fr = _pose_frame(model) if frame == 'idle' else frame
    W = {}

    def get(i):
        if i not in W:
            L = _mat(*_local(model, i, fr))
            p = model.bones[i]['parent']
            W[i] = mmd.mat_mul(get(p), L) if p >= 0 else L
        return W[i]
    return [get(i) for i in range(len(model.bones))]


def _apply(M, v):
    return tuple(M[r][0] * v[0] + M[r][1] * v[1] + M[r][2] * v[2] + M[r][3] for r in range(3))


def model_size(model):
    """Diagonal of the bounding box of the model in its first idle pose (model units)."""
    W = world_matrices(model)
    pts = [_apply(W[i], v) for i, b in enumerate(model.bones) for v in b['verts']]
    if not pts:
        return 1.0
    lo = [min(p[k] for p in pts) for k in range(3)]
    hi = [max(p[k] for p in pts) for k in range(3)]
    return _len([hi[k] - lo[k] for k in range(3)]) or 1.0


# ------------------------------------------------------------------ texture detail
def _rgb(c):
    return ((c & 31) / 31.0, ((c >> 5) & 31) / 31.0, ((c >> 10) & 31) / 31.0)


def _tri_detail(model, p, tri_uv, cache):
    """Texture contrast inside a triangle's UV area: the mean squared distance of its texels' colours
    from their mean, 0 (flat) .. ~0.75 (black/white). Samples a barycentric grid."""
    row = p['row'] or 0
    if row >= len(model.pals):
        return 0.0
    (u0, v0), (u1, v1), (u2, v2) = tri_uv
    key = (row, tri_uv)
    if key in cache:
        return cache[key]
    pal = model.pals[row]
    cols = []
    N = 5
    for i in range(N + 1):
        for j in range(N + 1 - i):
            a, b = i / N, j / N
            c = 1 - a - b
            u = int(round(u0 * c + u1 * a + u2 * b))
            v = int(round(v0 * c + v1 * a + v2 * b))
            if 0 <= u < 256 and 0 <= v < 128:
                ci = model.idx[v * 256 + u]
                cols.append(_rgb(pal[ci]) if pal[ci] else (0.0, 0.0, 0.0))
    if len(cols) < 2:
        d = 0.0
    else:
        mean = [sum(c[k] for c in cols) / len(cols) for k in range(3)]
        d = sum(sum((c[k] - mean[k]) ** 2 for k in range(3)) for c in cols) / len(cols)
    cache[key] = d
    return d


# ------------------------------------------------------------------ triangle mesh of a piece
class Face:
    """A triangle. rule: hashed by its creation index (n), never by its address: the vertex rings (Mesh.vf) are sets of
    faces, and the quadrics and collapse costs add over them in their order, so an address hash made the reduced
    model depend on where Python allocated each face (another model from one run to the next, 2026-10-27)."""
    __slots__ = ('n', 'alive', 'v', 'uv', 'nr', 'mat', 'qid', 'half', 'detail', 'src')

    def __hash__(self):
        return self.n


def _mat_key(p):
    tex = p['uvs'] is not None
    return (p['row'] if tex else None, bool(p.get('semi')), p.get('abr', 0), p['norms'] is not None, tex,
            None if tex else tuple(p.get('color', (128, 128, 128))))


class Mesh:
    """One piece (bone) as a triangle mesh with per-corner attributes."""

    def __init__(self, model, bi, cache, wb=2.0):
        b = model.bones[bi]
        self.bi = bi
        self.s2 = 0.0           # mean triangle area of the whole model (set by decimate)
        self.kb = 1.0
        self.wb = wb
        self.pos, key = [], {}
        self.faces = []
        self.src = {}
        qid = 0
        for p in b['prims']:
            ids = []
            for k in p['verts']:
                kk = _pkey(b['verts'][k])
                if kk not in key:
                    key[kk] = len(self.pos)
                    self.pos.append(tuple(float(x) for x in b['verts'][k]))
                ids.append(key[kk])
            uv = [tuple(u) for u in p['uvs']] if p['uvs'] is not None else [None] * len(ids)
            nr = [_vkey(b['norms'][k]) for k in p['norms']] if p['norms'] is not None else [None] * len(ids)
            mat = _mat_key(p)
            tris = [((0, 1, 2), 0)] if len(ids) == 3 else [((0, 1, 2), 0), ((1, 3, 2), 1)]
            for corners, half in tris:
                f = Face()
                f.n = len(self.faces)
                f.alive = True
                f.v = [ids[c] for c in corners]
                f.uv = [uv[c] for c in corners]
                f.nr = [nr[c] for c in corners]
                f.mat = mat
                f.qid = qid if len(ids) == 4 else None
                f.half = half
                f.src = p
                f.detail = _tri_detail(model, p, tuple(f.uv), cache) if p['uvs'] is not None else 0.0
                self.faces.append(f)
            qid += 1
        self.vf = [set() for _ in self.pos]
        for f in self.faces:
            for v in f.v:
                self.vf[v].add(f)
        self.alive_v = [True] * len(self.pos)
        self.ntri = len(self.faces)
        self.Q = [(0.0,) * 10 for _ in self.pos]
        self._init_quadrics(wb)

    # geometry
    def tri_normal(self, v):
        a, b, c = (self.pos[k] for k in v)
        return _cross(_sub(b, a), _sub(c, a))                 # length = 2 * area

    def _init_quadrics(self, wb=8.0):
        for f in self.faces:
            n = self.tri_normal(f.v)
            L = _len(n)
            if L < 1e-9:
                continue
            area = L / 2
            n = (n[0] / L, n[1] / L, n[2] / L)
            d = -_dot(n, self.pos[f.v[0]])
            q = _plane_q(n, d, area)
            for v in f.v:
                self.Q[v] = _qadd(self.Q[v], q)
        # penalty planes on feature edges (seams, boundaries): keep the vertex on its line
        seen = set()
        for f in self.faces:
            for i in range(3):
                a, b = f.v[i], f.v[(i + 1) % 3]
                e = (min(a, b), max(a, b))
                if e in seen:
                    continue
                seen.add(e)
                if self.is_feature(a, b):
                    ed = _sub(self.pos[b], self.pos[a])
                    el = _len(ed)
                    if el < 1e-9:
                        continue
                    for g in (self.vf[a] & self.vf[b]):
                        n = self.tri_normal(g.v)
                        nl = _len(n)
                        if nl < 1e-9:
                            continue
                        m = _cross(ed, (n[0] / nl, n[1] / nl, n[2] / nl))
                        ml = _len(m)
                        if ml < 1e-9:
                            continue
                        m = (m[0] / ml, m[1] / ml, m[2] / ml)
                        q = _plane_q(m, -_dot(m, self.pos[a]), wb * el * el)
                        self.Q[a] = _qadd(self.Q[a], q)
                        self.Q[b] = _qadd(self.Q[b], q)

    # topology
    def nbrs(self, v):
        out = set()
        for f in self.vf[v]:
            out.update(f.v)
        out.discard(v)
        return out

    def is_feature(self, a, b):
        fs = self.vf[a] & self.vf[b]
        if len(fs) != 2:
            return True
        f1, f2 = fs
        if f1.mat != f2.mat:
            return True
        for v in (a, b):
            if f1.uv[f1.v.index(v)] != f2.uv[f2.v.index(v)]:
                return True
        return False

    def features(self, v):
        """(feature neighbours, pinned): pinned when the vertex has a non-manifold edge or more than
        two feature edges (a corner where seams meet)."""
        out = []
        for w in self.nbrs(v):
            n = len(self.vf[v] & self.vf[w])
            if n > 2:
                return out, True
            if self.is_feature(v, w):
                out.append(w)
        return out, len(out) > 2

    def collapse_cost(self, a, b, kappa, kmove):
        """Cost of moving vertex a onto vertex b, or None when not allowed."""
        fab = self.vf[a] & self.vf[b]
        if len(fab) not in (1, 2):
            return None
        feats, pinned = self.features(a)
        if pinned:
            return None
        if feats and b not in feats:
            return None
        na, nb = self.nbrs(a), self.nbrs(b)
        opp = set()
        for f in fab:
            opp.update(x for x in f.v if x != a and x != b)
        if (na & nb) != opp:
            return None
        pb = self.pos[b]
        # a boundary vertex moving to a non-boundary one (or the reverse through a seam) is handled by the
        # feature rule above; here the geometric checks
        move2 = 0.0
        det = 0.0
        nf = 0
        for f in self.vf[a]:
            if f in fab:
                continue
            nv = [b if x == a else x for x in f.v]
            n0 = self.tri_normal(f.v)
            n1 = self.tri_normal(nv)
            l0, l1 = _len(n0), _len(n1)
            if l1 < 0.05 * l0 or l1 < 1e-9:
                return None
            if _dot(n0, n1) < 0.25 * l0 * l1:               # flipped or folded over
                return None
            det += f.detail
            nf += 1
        pa = self.pos[a]
        d2 = _dot(_sub(pb, pa), _sub(pb, pa))
        q = _qadd(self.Q[a], self.Q[b])
        err = _qeval(q, pb)
        removed = 0.0
        for f in fab:
            removed += _len(self.tri_normal(f.v)) / 2 * f.detail
        # local two-sided Hausdorff-style error: samples of the old surface around a against the new
        # triangles, and samples of the new triangles against the old ones (area weighted, squared)
        old = [f for f in (self.vf[a] | self.vf[b])]
        new = [[b if x == a else x for x in f.v] for f in self.vf[a] if f not in fab] + [list(f.v) for f in self.vf[b] if f not in fab and a not in f.v]
        NP = [tuple(self.pos[x] for x in t) for t in new]
        OP = [tuple(self.pos[x] for x in f.v) for f in old]
        e_old = 0.0
        pts = [pa] + [((pa[0] + self.pos[w][0]) / 2, (pa[1] + self.pos[w][1]) / 2, (pa[2] + self.pos[w][2]) / 2) for w in na]
        for f in self.vf[a]:
            T = tuple(self.pos[x] for x in f.v)
            pts.append(((T[0][0] + T[1][0] + T[2][0]) / 3, (T[0][1] + T[1][1] + T[2][1]) / 3, (T[0][2] + T[1][2] + T[2][2]) / 3))
        ring_area = sum(_len(self.tri_normal(f.v)) / 2 for f in self.vf[a])
        if NP:
            for pt in pts:
                e_old += min(_pt_tri2(pt, T) for T in NP)
            e_old *= ring_area / len(pts)
        else:
            e_old = ring_area * 1e6
        npts = []
        for T in NP:
            npts.append(((T[0][0] + T[1][0] + T[2][0]) / 3, (T[0][1] + T[1][1] + T[2][1]) / 3, (T[0][2] + T[1][2] + T[2][2]) / 3))
        for w in nb:
            npts.append(((pb[0] + self.pos[w][0]) / 2, (pb[1] + self.pos[w][1]) / 2, (pb[2] + self.pos[w][2]) / 2))
        e_new = 0.0
        if npts and OP:
            for pt in npts:
                e_new += min(_pt_tri2(pt, T) for T in OP)
            e_new *= ring_area / len(npts)
        cost = err + e_old + e_new + self.s2 * (kappa * removed + kmove * d2 * (det / nf if nf else 0.0) * max(nf, 1) * 0.5)
        return cost

    def collapse(self, a, b):
        fa = list(self.vf[a])
        for f in fa:
            if b in f.v:
                f.alive = False
                self.ntri -= 1
                for v in f.v:
                    self.vf[v].discard(f)
            else:
                f.v[f.v.index(a)] = b
                self.vf[a].discard(f)
                self.vf[b].add(f)
        self.Q[b] = _qadd(self.Q[b], self.Q[a])
        self.alive_v[a] = False

    def live_faces(self):
        return [f for f in self.faces if f.alive]


def _pt_tri2(p, T):
    """Squared distance from point p to triangle T (Ericson, Real-Time Collision Detection)."""
    a, b, c = T
    ab, ac, ap = _sub(b, a), _sub(c, a), _sub(p, a)
    d1, d2 = _dot(ab, ap), _dot(ac, ap)
    if d1 <= 0 and d2 <= 0:
        return _dot(ap, ap)
    bp = _sub(p, b)
    d3, d4 = _dot(ab, bp), _dot(ac, bp)
    if d3 >= 0 and d4 <= d3:
        return _dot(bp, bp)
    vc = d1 * d4 - d3 * d2
    if vc <= 0 and d1 >= 0 and d3 <= 0:
        v = d1 / (d1 - d3)
        r = (ap[0] - v * ab[0], ap[1] - v * ab[1], ap[2] - v * ab[2])
        return _dot(r, r)
    cp = _sub(p, c)
    d5, d6 = _dot(ab, cp), _dot(ac, cp)
    if d6 >= 0 and d5 <= d6:
        return _dot(cp, cp)
    vb = d5 * d2 - d1 * d6
    if vb <= 0 and d2 >= 0 and d6 <= 0:
        w = d2 / (d2 - d6)
        r = (ap[0] - w * ac[0], ap[1] - w * ac[1], ap[2] - w * ac[2])
        return _dot(r, r)
    va = d3 * d6 - d5 * d4
    if va <= 0 and (d4 - d3) >= 0 and (d5 - d6) >= 0:
        w = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        bc = _sub(c, b)
        r = (bp[0] - w * bc[0], bp[1] - w * bc[1], bp[2] - w * bc[2])
        return _dot(r, r)
    den = 1.0 / (va + vb + vc) if (va + vb + vc) else 0.0
    v, w = vb * den, vc * den
    r = (ap[0] - ab[0] * v - ac[0] * w, ap[1] - ab[1] * v - ac[1] * w, ap[2] - ab[2] * v - ac[2] * w)
    return _dot(r, r)


# quadrics: symmetric 4x4 as 10 numbers (a2 ab ac ad b2 bc bd c2 cd d2)
def _plane_q(n, d, w):
    a, b, c = n
    return (w * a * a, w * a * b, w * a * c, w * a * d, w * b * b, w * b * c, w * b * d, w * c * c, w * c * d, w * d * d)


def _qadd(p, q):
    return tuple(x + y for x, y in zip(p, q))


def _qeval(q, v):
    x, y, z = v
    return (q[0] * x * x + 2 * q[1] * x * y + 2 * q[2] * x * z + 2 * q[3] * x + q[4] * y * y + 2 * q[5] * y * z
            + 2 * q[6] * y + q[7] * z * z + 2 * q[8] * z + q[9])


# ------------------------------------------------------------------ triangles -> primitives
def _tri_unit_normal(pos, v):
    n = _cross(_sub(pos[v[1]], pos[v[0]]), _sub(pos[v[2]], pos[v[0]]))
    L = _len(n)
    return (n[0] / L, n[1] / L, n[2] / L) if L > 1e-12 else (0.0, 0.0, 0.0)


def _side(P, Q, R, n):
    return _dot(_cross(_sub(Q, P), _sub(R, P)), n)


def remerge(mesh, max_angle=25.0):
    """Primitives of the live triangles: [(corner position ids, uvs, normals, mat, src prim)] with 3 or 4
    corners. Halves of one source quad that still share their diagonal become that quad again (exactly
    what the engine draws); other pairs merge by angle (smallest first), convexity, UVs, normals, material."""
    pos = mesh.pos
    live = mesh.live_faces()
    out = []
    used = set()
    halves = {}
    for f in live:
        if f.qid is not None:
            halves.setdefault(f.qid, {})[f.half] = f
    for qid, h in halves.items():
        if 0 in h and 1 in h:
            f0, f1 = h[0], h[1]
            # f0 = (c0, c1, c2), f1 = (c1, c3, c2): the shared corners must be the same position ids
            if f0.v[1] == f1.v[0] and f0.v[2] == f1.v[2] and f1.v[1] not in f0.v and f0.uv[1] == f1.uv[0] \
                    and f0.uv[2] == f1.uv[2] and f0.nr[1] == f1.nr[0] and f0.nr[2] == f1.nr[2]:
                out.append(([f0.v[0], f0.v[1], f0.v[2], f1.v[1]], [f0.uv[0], f0.uv[1], f0.uv[2], f1.uv[1]],
                            [f0.nr[0], f0.nr[1], f0.nr[2], f1.nr[1]], f0.mat, f0.src))
                used.add(f0)
                used.add(f1)
    rest = [f for f in live if f not in used]
    order = {f: k for k, f in enumerate(rest)}      # rule: ties break by list position, never id() (memory address)
    edge = {}
    for f in rest:
        for i in range(3):
            edge[(f.v[i], f.v[(i + 1) % 3])] = (f, i)
    cos_max = math.cos(math.radians(max_angle))
    cands = []
    for f in rest:
        nf = _tri_unit_normal(pos, f.v)
        for i in range(3):
            b, c = f.v[i], f.v[(i + 1) % 3]
            g = edge.get((c, b))
            if g is None or g[0] is f:
                continue
            g, j = g
            if order[f] > order[g] or g.mat != f.mat:
                continue
            ng = _tri_unit_normal(pos, g.v)
            cs = _dot(nf, ng)
            if cs < cos_max:
                continue
            a = f.v[(i + 2) % 3]
            d = g.v[(j + 2) % 3]
            if a == d:
                continue
            ia, ib, ic = (i + 2) % 3, i, (i + 1) % 3
            jb, jc, jd = (j + 1) % 3, j, (j + 2) % 3       # in g, the edge runs c -> b: g.v[j] = c, g.v[j+1] = b
            if f.uv[ib] != g.uv[jb] or f.uv[ic] != g.uv[jc] or f.nr[ib] != g.nr[jb] or f.nr[ic] != g.nr[jc]:
                continue
            A, B, C, D = pos[a], pos[b], pos[c], pos[d]
            if _side(B, C, A, nf) * _side(B, C, D, nf) >= 0 or _side(A, D, B, nf) * _side(A, D, C, nf) >= 0:
                continue
            cands.append((math.acos(min(1.0, cs)), order[f], order[g], f, g, ia, ib, ic, jd))
    cands.sort(key=lambda x: (x[0], x[1], x[2]))
    for _, _, _, f, g, ia, ib, ic, jd in cands:
        if f in used or g in used:
            continue
        used.add(f)
        used.add(g)
        out.append(([f.v[ia], f.v[ib], f.v[ic], g.v[jd]], [f.uv[ia], f.uv[ib], f.uv[ic], g.uv[jd]],
                    [f.nr[ia], f.nr[ib], f.nr[ic], g.nr[jd]], f.mat, f.src))
    for f in rest:
        if f not in used:
            out.append((list(f.v), list(f.uv), list(f.nr), f.mat, f.src))
    return out


def _prim_dicts(mesh, items):
    """(verts, norms, prims) of a bone from merged primitives."""
    verts, vid, norms, nid, prims = [], {}, [], {}, []
    for ids, uvs, nrs, mat, src in items:
        vi = []
        for k in ids:
            if k not in vid:
                vid[k] = len(verts)
                verts.append(mesh.pos[k])
            vi.append(vid[k])
        p = dict(src)
        p['verts'] = vi
        if src['uvs'] is not None:
            p['uvs'] = [tuple(u) for u in uvs]
        if src['norms'] is not None:
            ni = []
            for n in nrs:
                if n not in nid:
                    nid[n] = len(norms)
                    norms.append(tuple(float(x) for x in n))
                ni.append(nid[n])
            p['norms'] = ni
        prims.append(p)
    return verts, norms, prims


# ------------------------------------------------------------------ decimation
def decimate(model, budget=MAX_PRIMS, kappa=0.3, kmove=0.3, quad_angle=25.0, min_tris=4, kb=0.0, log=print):
    """Quadric edge collapse until the model has at most `budget` primitives (after the triangle pairs are
    merged into quads again). Returns the number of primitives removed. Pieces of at most `min_tris`
    triangles are left alone."""
    n0 = prim_count(model)
    if n0 <= budget:
        return 0
    cache = {}
    meshes = [Mesh(model, i, cache) for i, b in enumerate(model.bones) if b['prims']]
    tri_areas = [_len(m.tri_normal(f.v)) / 2 for m in meshes for f in m.faces]
    for m in meshes:
        m.s2, m.kb = sum(tri_areas) / max(1, len(tri_areas)), kb
    heap, seq = [], 0

    def push(mi, a, b):
        nonlocal seq
        c = meshes[mi].collapse_cost(a, b, kappa, kmove)
        if c is not None:
            seq += 1
            heapq.heappush(heap, (c, seq, mi, a, b))
    for mi, m in enumerate(meshes):
        for a in range(len(m.pos)):
            for b in m.nbrs(a):
                push(mi, a, b)
    total = lambda: sum(m.ntri for m in meshes)          # noqa: E731
    items = [remerge(m, quad_angle) for m in meshes]
    count = sum(len(x) for x in items)
    ratio = total() / max(1, count)
    target = total() - max(1, int((count - budget) * ratio))
    done = 0
    while count > budget and heap:
        while heap and total() > target:
            c, _, mi, a, b = heapq.heappop(heap)
            m = meshes[mi]
            if not (m.alive_v[a] and m.alive_v[b]):
                continue
            if m.ntri <= min_tris:
                continue
            c2 = m.collapse_cost(a, b, kappa, kmove)
            if c2 is None:
                continue
            if c2 > c * 1.0001 + 1e-9:
                seq += 1
                heapq.heappush(heap, (c2, seq, mi, a, b))
                continue
            m.collapse(a, b)
            done += 1
            for w in m.nbrs(b):
                push(mi, b, w)
                push(mi, w, b)
        items = [remerge(m, quad_angle) for m in meshes]
        count = sum(len(x) for x in items)
        if not heap and count > budget:
            break
        ratio = total() / max(1, count)
        target = total() - max(1, int((count - budget) * ratio))
    for m, it in zip(meshes, items):
        b = model.bones[m.bi]
        b['verts'], b['norms'], b['prims'] = _prim_dicts(m, it)
    log(f'  meshfix: {done} edge collapses, primitives {n0} -> {prim_count(model)}, '
        f'vertices {vert_count(model)}')
    return n0 - prim_count(model)


def _frame_lists(model):
    """Every distinct per-tick bone list of every animation (animations may share them: DW2's concatenated fall)."""
    seen, out = set(), []
    for a in model.anims.values():
        for f in a.frames:
            if id(f) not in seen:
                seen.add(id(f))
                out.append(f)
    return out


# ------------------------------------------------------------------ piece splitting
def _split_faces(bone, limit):
    """Groups of face indices, each with at most `limit` distinct vertex positions: recursive median cut of
    the face centroids along the widest axis."""
    V = bone['verts']
    faces = list(range(len(bone['prims'])))
    cent = []
    for p in bone['prims']:
        cent.append(tuple(sum(V[k][a] for k in p['verts']) / len(p['verts']) for a in range(3)))

    def nverts(fs):
        return len({_vkey(V[k]) for i in fs for k in bone['prims'][i]['verts']})

    def cut(fs):
        if nverts(fs) <= limit or len(fs) < 2:
            return [fs]
        ext = [max(cent[i][a] for i in fs) - min(cent[i][a] for i in fs) for a in range(3)]
        ax = max(range(3), key=lambda a: ext[a])
        fs = sorted(fs, key=lambda i: (cent[i][ax], i))
        # the cut position that balances the two vertex counts
        best, bk = None, None
        for k in range(max(1, len(fs) // 4), min(len(fs) - 1, 3 * len(fs) // 4) + 1):
            s = max(nverts(fs[:k]), nverts(fs[k:]))
            if best is None or s < best:
                best, bk = s, k
        return cut(fs[:bk]) + cut(fs[bk:])
    return cut(faces)


def split_pieces(model, limit=MAX_VERTS_PER_OBJECT, log=print):
    """Cuts every piece over `limit` vertices into parts hanging from helper bones (appended at the end:
    the existing bone numbers do not change). Returns the number of helper bones made."""
    made = 0
    for i in range(len(model.bones)):
        b = model.bones[i]
        if unique_verts(b) <= limit:
            continue
        n_before = unique_verts(b)
        groups = _split_faces(b, limit)
        if len(groups) < 2:
            raise SystemExit(f'meshfix: bone {i} cannot be split under {limit} vertices')
        parts = []
        for g in groups:
            vmap, nmap, verts, norms, prims = {}, {}, [], [], []
            for pi in g:
                p = dict(b['prims'][pi])
                nv = []
                for k in p['verts']:
                    if k not in vmap:
                        vmap[k] = len(verts)
                        verts.append(b['verts'][k])
                    nv.append(vmap[k])
                p['verts'] = nv
                if p['norms'] is not None:
                    nn = []
                    for k in p['norms']:
                        if k not in nmap:
                            nmap[k] = len(norms)
                            norms.append(b['norms'][k])
                        nn.append(nmap[k])
                    p['norms'] = nn
                prims.append(p)
            parts.append((verts, norms, prims))
        b['verts'], b['norms'], b['prims'] = parts[0]
        for verts, norms, prims in parts[1:]:
            model.bones.append(dict(parent=i, offset=(0.0, 0.0, 0.0), rest=IDENTITY_Q, verts=verts, norms=norms,
                                    prims=prims, helper=True))
            for f in _frame_lists(model):
                f.append((IDENTITY_Q, (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)))
            made += 1
        log(f'  meshfix: bone {i + 1} had {n_before} vertices: now ' + ' + '.join(str(unique_verts(dict(verts=p[0]))) for p in parts))
    return made


# ------------------------------------------------------------------ bone welding
def _motion(model, i):
    """How much bone i moves relative to its parent over all animations (rotation angle and translation
    change from the first idle frame), as a number of radians plus joint-offset change in units / size."""
    base = _pose_frame(model)
    if base is None:
        return 0.0
    worst = 0.0
    for a in model.anims.values():
        for f in a.frames[::3]:
            q0, t0 = base[i][0], base[i][1]
            q1, t1 = f[i][0], f[i][1]
            d = abs(sum(x * y for x, y in zip(q0, q1)))
            ang = 2 * math.acos(min(1.0, d))
            worst = max(worst, ang)
    return worst


def drop_hidden(model, log=print):
    """Effect pieces: a piece that the source hides by a zero scale in every frame of its idle animation (a ball of
    energy kept for an attack, a muzzle flash) cannot be hidden in DW1 (a bone has no scale), so it would hang in the
    air for ever. Its faces (and those of the bones below it) are removed. Returns [(old bone number, faces)]."""
    a = model.anims.get(getattr(model, 'idle', None) or 'anim_00') if getattr(model, 'anims', None) else None
    if a is None or not a.frames:
        return []
    n = len(model.bones)
    hidden = {}

    def hid(i):
        if i not in hidden:
            own = all(min(f[i][2]) < 0.2 for f in a.frames)
            p = model.bones[i]['parent']
            hidden[i] = own or (p >= 0 and hid(p))
        return hidden[i]
    out = []
    for i in range(n):
        b = model.bones[i]
        if hid(i) and b['prims']:
            out.append((i + 1, len(b['prims'])))
            b['prims'], b['verts'], b['norms'] = [], [], []
    for o in out:
        log(f'  meshfix: bone {o[0]} ({o[1]} faces) is hidden by a zero scale in the idle animation: dropped')
    return out


def weld_bones(model, max_bones=MAX_BONES - 1, log=print):
    """Welds bones into their parents until the model has at most `max_bones` bones (the entity is not
    counted). Welded: the leaf with the smallest `faces x (0.3 + motion)` score, its vertices moved into
    the parent's frame in the first idle pose, its faces appended to the parent's. Returns the old bone
    numbers (1-based, as DW1 numbers them) that were welded."""
    welded = []
    while len(model.bones) > max_bones:
        n = len(model.bones)
        kids = {i: 0 for i in range(n)}
        for b in model.bones:
            if b['parent'] >= 0:
                kids[b['parent']] += 1
        cands = [i for i in range(n) if kids[i] == 0 and model.bones[i]['parent'] >= 0 and not model.bones[i].get('helper')]
        if not cands:
            raise SystemExit('meshfix: no leaf bone to weld')
        cands.sort(key=lambda i: (len(model.bones[i]['prims']) * (0.3 + _motion(model, i)), i))
        c = cands[0]
        ch, par = model.bones[c], model.bones[ch_parent(model, c)]
        fr = _pose_frame(model)
        L = _mat(*_local(model, c, fr))
        vbase = len(par['verts'])
        par['verts'] = list(par['verts']) + [_apply(L, v) for v in ch['verts']]
        # normals rotate with the bone; stored as integers 4096 = 1
        R = [row[:3] for row in L[:3]]
        nbase = len(par['norms'])
        par['norms'] = list(par['norms']) + [tuple(sum(R[r][k] * nn[k] for k in range(3)) for r in range(3))
                                            for nn in ch['norms']]
        for p in ch['prims']:
            q = dict(p)
            q['verts'] = [k + vbase for k in p['verts']]
            if p['norms'] is not None:
                q['norms'] = [k + nbase for k in p['norms']]
            par['prims'].append(q)
        welded.append((c + 1, len(ch['prims']), ch_parent(model, c) + 1))
        _remove_bone(model, c)
    for w in welded:
        log(f'  meshfix: bone {w[0]} ({w[1]} faces) welded into bone {w[2]}')
    return [w[0] for w in welded]


def ch_parent(model, c):
    return model.bones[c]['parent']


def _remove_bone(model, c):
    """Deletes bone c (a leaf) and renumbers: bones above it move down by one."""
    del model.bones[c]
    for b in model.bones:
        if b['parent'] > c:
            b['parent'] -= 1
    for f in _frame_lists(model):
        del f[c]
    if getattr(model, 'hub', None) is not None and model.hub > c:
        model.hub -= 1


# ------------------------------------------------------------------ orchestration
CANDIDATES = [dict(kappa=0.3, kmove=0.3, quad_angle=25.0), dict(kappa=1.0, kmove=1.0, quad_angle=25.0),
              dict(kappa=0.3, kmove=0.3, quad_angle=40.0), dict(kappa=1.0, kmove=1.0, quad_angle=40.0),
              dict(kappa=0.0, kmove=0.0, quad_angle=40.0), dict(kappa=3.0, kmove=3.0, quad_angle=40.0)]


def best_decimation(model, budget, log=print):
    """Runs decimate with every candidate parameter set on a copy and returns the set with the smallest measured
    visual error (compare(): silhouette and colour differences in four views)."""
    before = snapshot(model)
    best = None
    for c in CANDIDATES:
        trial = copy.copy(model)
        trial.bones = copy.deepcopy(model.bones)
        decimate(trial, budget, log=lambda *a: None, **c)
        met, _ = compare(before, snapshot(trial), size=160)
        log(f'  meshfix candidate {c}: prims {prim_count(trial)}, error {met["err"]}')
        if prim_count(trial) <= budget and (best is None or met['err'] < best[0]):
            best = (met['err'], c)
    if best is None:
        raise SystemExit('meshfix: no decimation reached the budget')
    return best[1], best[0]


def apply(model, params=None, log=print):
    """The mesh rules in order. `params` (all optional): bones (max model bones + 1, default 34), prims
    (default 713), decimate (False: never), quad_angle, kappa, kmove, split (default True), hidden (False: keep the
    pieces the idle animation hides by a zero scale)."""
    params = dict(params or {})
    info = {}
    if params.get('hidden', True):
        h = drop_hidden(model, log)
        if h:
            info['hidden'] = [x[0] for x in h]
    maxb = int(params.get('bones', MAX_BONES))
    if len(model.bones) + 1 > maxb:
        info['welded'] = weld_bones(model, maxb - 1, log)
    budget = int(params.get('prims', MAX_PRIMS))
    if params.get('decimate', True) and prim_count(model) > budget:
        used = {k: params[k] for k in ('kappa', 'kmove', 'quad_angle') if k in params}
        if len(used) < 3:
            used, err = best_decimation(model, budget, log)
            info['error'] = err
        decimate(model, budget, log=log, **used)
        info['decimated'] = used
    if params.get('split', True) and any(unique_verts(b) > MAX_VERTS_PER_OBJECT for b in model.bones):
        info['split'] = split_pieces(model, log=log)
    return info


def spec_params(info, params=None):
    """What a spec records so a rebuild repeats the same edits without the search: the parameters that were
    used (`apply(model, spec_params(...))` is deterministic)."""
    out = dict(params or {})
    out.update(info.get('decimated') or {})
    return out


def needs_fix(model):
    return (len(model.bones) + 1 > MAX_BONES or prim_count(model) > MAX_PRIMS
            or any(unique_verts(b) > MAX_VERTS_PER_OBJECT for b in model.bones))


def snapshot(model):
    """What the comparison needs, copied: the bones with their meshes, the texture, the palettes and the idle
    pose (the animations are not shared, so a later split does not touch them)."""
    s = mmdport.Model(model.name, copy.deepcopy(model.bones), model.idx, model.pals, {})
    a = (model.anims.get(getattr(model, 'idle', None) or 'anim_00') or (next(iter(model.anims.values())) if model.anims else None))
    if a is not None:
        s.anims = {'idle': mmdport.Anim([list(a.frames[0])], a.fps, False)}
        s.idle = 'idle'
    return s


# ------------------------------------------------------------------ rendering and the visual error
VIEWS = {'front': (0.0, 0.0), 'side': (90.0, 0.0), '3/4': (35.0, 12.0), 'back': (180.0, 0.0)}


def world_tris(model):
    """[(3 world points, 3 uvs | None, prim)] of every primitive (a quad is its two triangles)."""
    W = world_matrices(model)
    out = []
    for i, b in enumerate(model.bones):
        P = [_apply(W[i], v) for v in b['verts']]
        for p in b['prims']:
            ks = p['verts']
            uv = p['uvs']
            for t in ((0, 1, 2),) if len(ks) == 3 else ((0, 1, 2), (1, 3, 2)):
                out.append(([P[ks[c]] for c in t], [tuple(uv[c]) for c in t] if uv is not None else None, p))
    return out


def _camera(yaw, pitch):
    cy, sy, cp, sp = math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), math.cos(math.radians(pitch)), math.sin(math.radians(pitch))

    def proj(P):
        x = P[0] * cy + P[2] * sy
        z = -P[0] * sy + P[2] * cy
        y = P[1] * cp - z * sp
        z2 = P[1] * sp + z * cp
        return x, y, z2
    return proj


def fit_views(model, size, margin=1.12):
    """Per view: (centre x, centre y, scale) that frames the model."""
    tris = world_tris(model)
    out = {}
    for name, (yaw, pitch) in VIEWS.items():
        proj = _camera(yaw, pitch)
        pts = [proj(P) for t, _, _ in tris for P in t]
        lo = [min(p[k] for p in pts) for k in range(2)]
        hi = [max(p[k] for p in pts) for k in range(2)]
        out[name] = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, size / (max(hi[0] - lo[0], hi[1] - lo[1]) * margin or 1.0))
    return out


def cull_sign(model):
    """+1/-1: the screen winding of the faces that face the camera (the engine culls the others): the sign that
    keeps the larger share of the front view's area."""
    proj = _camera(0.0, 0.0)
    tot = 0.0
    for t, _, p in world_tris(model):
        a, b, c = (proj(P) for P in t)
        tot += (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return 1.0 if tot >= 0 else -1.0


def render(model, view, fit, size=256, sign=1.0):
    """(rgb float array size x size x 3 in 0..1, depth, mask) of an orthographic render, textured, flat-lit."""
    import numeric as np
    yaw, pitch = VIEWS[view]
    cx, cy, sc = fit[view]
    proj = _camera(yaw, pitch)
    img = np.zeros((size, size, 3), np.float32)
    zb = np.full((size, size), np.inf, np.float32)
    pals = [[_rgb(c) if c else None for c in pal] for pal in model.pals]
    idx = np.frombuffer(bytes(model.idx), np.uint8).reshape(128, 256)
    for t, uv, p in world_tris(model):
        pr = [proj(P) for P in t]
        xs = [(q[0] - cx) * sc + size / 2 for q in pr]
        ys = [(q[1] - cy) * sc + size / 2 for q in pr]
        zs = [q[2] for q in pr]
        area = (xs[1] - xs[0]) * (ys[2] - ys[0]) - (ys[1] - ys[0]) * (xs[2] - xs[0])
        if abs(area) < 1e-6 or area * sign < 0:
            continue
        x0, x1 = max(0, int(math.floor(min(xs)))), min(size - 1, int(math.ceil(max(xs))))
        y0, y1 = max(0, int(math.floor(min(ys)))), min(size - 1, int(math.ceil(max(ys))))
        if x0 > x1 or y0 > y1:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        w0 = ((xs[1] - gx) * (ys[2] - gy) - (ys[1] - gy) * (xs[2] - gx)) / area
        w1 = ((xs[2] - gx) * (ys[0] - gy) - (ys[2] - gy) * (xs[0] - gx)) / area
        w2 = 1 - w0 - w1
        inside = (w0 >= -0.02) & (w1 >= -0.02) & (w2 >= -0.02)
        if not inside.any():
            continue
        z = w0 * zs[0] + w1 * zs[1] + w2 * zs[2]
        n = _cross(_sub(t[1], t[0]), _sub(t[2], t[0]))
        nl = _len(n) or 1.0
        shade = 0.55 + 0.45 * abs(n[2] * math.cos(math.radians(yaw)) - n[0] * math.sin(math.radians(yaw))) / nl
        if uv is not None:
            u = w0 * uv[0][0] + w1 * uv[1][0] + w2 * uv[2][0]
            v = w0 * uv[0][1] + w1 * uv[1][1] + w2 * uv[2][1]
            ui = np.clip(np.floor(u).astype(int), 0, 255)
            vi = np.clip(np.floor(v).astype(int), 0, 127)
            row = p['row'] or 0
            pal = pals[row] if row < len(pals) else pals[0]
            lut = np.array([c if c else (-1, -1, -1) for c in pal] + [(-1, -1, -1)] * (16 - len(pal)), np.float32)
            col = lut[idx[vi, ui]]
            opaque = col[..., 0] >= 0
            inside = inside & opaque
        else:
            c = tuple(x / 255.0 for x in p.get('color', (128, 128, 128)))
            col = np.empty(gx.shape + (3,), np.float32)
            col[...] = c
        sub = zb[y0:y1 + 1, x0:x1 + 1]
        take = inside & (z < sub)
        if not take.any():
            continue
        sub[take] = z[take]
        img[y0:y1 + 1, x0:x1 + 1][take] = np.clip(col[take] * shade, 0, 1)
    return img, zb, np.isfinite(zb)


def compare(before, after, size=256, sign=None):
    """Renders both in the four views with the same framing. Returns (metrics, {view: (img_before, img_after)}).
    metrics per view: sil = silhouette mismatch (XOR / union), col = mean absolute colour difference on the
    shared silhouette (0..1), and the overall `err` = mean over views of sil + col."""
    import numeric as np
    fit = fit_views(before, size)
    sign = cull_sign(before) if sign is None else sign
    D = model_size(before)
    met, ims = {}, {}
    for v in VIEWS:
        ia, za, ma = render(before, v, fit, size, sign)
        ib, zb, mb = render(after, v, fit, size, sign)
        both = ma & mb
        union = ma | mb
        sil = float((ma ^ mb).sum()) / max(1, int(union.sum()))
        col = float(np.abs(ia - ib)[both].mean()) if both.any() else 1.0
        met[v] = dict(sil=round(sil, 4), col=round(col, 4))
        ims[v] = (ia, ib)
    met['err'] = round(sum(met[v]['sil'] + met[v]['col'] for v in VIEWS) / len(VIEWS), 4)
    return met, ims


def sheet(ims, path, title='', size=256):
    """before / after / difference rows, one column per view, as a PNG."""
    import numpy as np
    from tools.image import Image, ImageDraw
    cols = []
    for v, (a, b) in ims.items():
        d = np.clip(np.abs(a - b) * 3, 0, 1)
        cols.append([a, b, d])
    W, H = size * len(cols), size * 3 + 22
    im = Image.new('RGB', (W, H), (40, 40, 48))
    for ci, col in enumerate(cols):
        for ri, arr in enumerate(col):
            im.paste(Image.fromarray((np.asarray(arr, dtype=np.float32) * 255).astype(np.uint8)), (ci * size, 22 + ri * size))
    dr = ImageDraw.Draw(im)
    dr.text((4, 4), title + '   rows: before / after / difference x3   columns: ' + ', '.join(ims), fill=(235, 235, 235))
    im.save(path)
