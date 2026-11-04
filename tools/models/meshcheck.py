#!/usr/bin/env python3
"""Mesh audit of species models: see-through views, open edges, winding, detached parts, tears, coplanar faces.

DW1 draws a model as rigid pieces (one TMD object per bone) with back faces culled (libgs' GsTMDfast routines skip a
face whose screen winding is reversed and ignore the TMD double-sided flag), sorted by depth with no z-buffer. A model that the original game only showed from the
front can therefore have no back at all: from behind it is see-through. This tool measures every defect of that
kind on the final model of a species, in its idle pose and over its animations:

  views      software renders from the front, back, both sides, the top and eight directions 30 degrees above (the
             field and battle cameras' side), in the idle pose. `holes` is the share of the model's
             silhouette (every face, both sides) where nothing is drawn once back faces are culled: a missing back,
             a missing side, a face wound the wrong way. Transparent texels (colour 0) are counted apart, as `clear`
             (drawn on purpose for fringes and gaps).
  open       edges of a piece used by one face only (vertices welded by position within the piece), and the longest
             open boundary loop compared with the model's height.
  inverted   the share of each piece's face area wound against its own stored normals: lit as if it faced the other
             way (listed, not flagged: DW1's own models have up to half of a piece so). A face wound inside out
             is culled from outside and shows in `holes`.
  detached   connected parts of a piece far from every other part of the model in the idle pose.
  tears      each piece's distance to the nearest other piece over every frame of every animation, against the idle
             pose: a part skinned to the wrong bone, or a joint that opens, leaves the body.
  zfight     pairs of faces on one plane that overlap with different texture (listed, not flagged: DW1's own models
             have them, and the depth sort keeps their order for most views).

  python3 tools/models/meshcheck.py check MMD TIM --bones JSON [--sheet OUT.png]
            one model (bones: [[object, parent], ...]); the sheet shows the views as drawn and, below, the
            see-through pixels in magenta; exits 1 when something is flagged
  python3 tools/models/meshcheck.py audit DIR [IDS...] [--out REPORT.json] [--sheets DIR] [--jobs N] [--no-anims]
            every <id>.MMD/.TIM in DIR with DIR/index.json ({id: {name, bones}}), as written by `extract`;
            sheets of the flagged species
  python3 tools/models/meshcheck.py extract DIGI.DAT DIR           the final model, texture and skeleton of every
            species of a built archive (record originals and imports) plus the disc's other natives from extracted/

Uses numpy (a developer tool; nothing of the player's build depends on it).
"""
import argparse
import json
import math
import os
import struct
import sys
import zlib

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import mmd  # noqa: E402

VIEWS = (('front', 0.0, 0.0), ('back', math.pi, 0.0), ('left', math.pi / 2, 0.0), ('right', -math.pi / 2, 0.0),
         ('top', 0.0, math.pi / 2))
# the field and battle cameras look down on the model: eight directions around it, 30 degrees above
RING = tuple((f'above{k * 45}', k * math.pi / 4, math.pi / 6) for k in range(8))
SIZE = 160
# thresholds of a defect (fractions; see `flags`)
HOLES_MAX = 0.04          # the share of a view's silhouette that may be see-through
INVERTED_MAX = 0.10       # the share of a piece's face area wound against its own normals
DETACHED_MIN = 0.06       # a part this far from the rest (in heights) is listed
DETACHED_FLAG = 0.10      # ... and flagged from this far (DW1's own models float eyes, gears, flames up to ~0.2)
STRETCH_MAX = 0.08        # a piece that moves this much farther (in heights) from every other piece tears away
ZFIGHT_MIN_AREA = 0.0004  # overlapping coplanar area, in squared heights


# ------------------------------------------------------------------ the model
class Model:
    """A species model posed by its skeleton: per bone its object's vertices and triangles."""

    def __init__(self, data, bones, tim=None):
        self.bones = [tuple(b) for b in bones]
        self.m = mmd.MMD.parse(data, len(self.bones)) if isinstance(data, (bytes, bytearray)) else data
        self.tim = mmd.Tim4(tim) if isinstance(tim, (bytes, bytearray)) else tim
        self.tex = self._texture()
        # triangles: (bone, object, prim, (i0, i1, i2) local vertex indices, (uv0, uv1, uv2) or None, row, double, clear)
        self.tris = []
        for b, (oi, _) in enumerate(self.bones):
            if oi < 0 or oi >= len(self.m.tmd.objects):
                continue
            for pi, p in enumerate(self.m.tmd.objects[oi].prims):
                try:
                    d = p.decode()
                except ValueError:
                    continue
                ids = d['verts']
                row = ((d['cba'] >> 6) - 488) if d['cba'] else 0
                corners = [(0, 1, 2)] + ([(1, 3, 2)] if len(ids) == 4 else [])
                for c in corners:
                    uv = [d['uv'][k] for k in c] if d['uv'] else None
                    col = d['colors'][0][:3] if d['colors'] else (200, 200, 200)
                    self.tris.append((b, oi, pi, tuple(ids[k] for k in c), uv, row, bool(d['flag'] & 2), col))
        self.local = {b: np.array([v[:3] for v in self.m.tmd.obj_verts(oi)], float)
                      for b, (oi, _) in enumerate(self.bones) if 0 <= oi < len(self.m.tmd.objects)}

    def _texture(self):
        if self.tim is None:
            return None
        t = self.tim
        idx = np.frombuffer(bytes(t.idx), np.uint8).reshape(t.h, t.w)
        pal = np.array(t.pal, np.uint16)
        rgb = np.stack([(pal & 31) << 3, (pal >> 5 & 31) << 3, (pal >> 10 & 31) << 3], -1).astype(np.uint8)
        return idx, pal, rgb

    # poses -----------------------------------------------------------
    def slots(self):
        return [s for s, k in enumerate(self.m.anims.table) if k is not None] if self.m.anims else []

    def poses(self, slot, max_ticks=400, step=1):
        an = self.m.anims.anims[self.m.anims.table[slot]]
        p = mmd.AnimPlayer(an, len(self.bones), slot)
        out = []
        while len(out) < max_ticks and p.tick(stop_at_infinite_loop=True):
            if p.ticks % step == 1 or step == 1:
                out.append([list(v) for v in p.pose])
        return out

    def rest(self):
        """The idle pose: the first tick of slot 0 (or the bind pose)."""
        if self.m.anims and self.m.anims.table and self.m.anims.table[0] is not None:
            ps = self.poses(0, 1)
            if ps:
                return ps[0]
        return [[4096, 4096, 4096, 0, 0, 0, 0, 0, 0] for _ in self.bones]

    def matrices(self, pose):
        out = [None] * len(self.bones)

        def get(b):
            if out[b] is None:
                v = pose[b]
                R = np.array(mmd.rot_matrix(*v[3:6])) * (np.array(v[0:3]) / 4096.0)[None, :]
                L = np.eye(4)
                L[:3, :3], L[:3, 3] = R, v[6:9]
                par = self.bones[b][1]
                out[b] = get(par) @ L if par >= 0 else L
            return out[b]
        for b in range(len(self.bones)):
            get(b)
        return out

    def world(self, pose):
        """{bone: (n,3) world vertices}."""
        mats = self.matrices(pose)
        return {b: (v @ mats[b][:3, :3].T + mats[b][:3, 3]) if len(v) else v for b, v in self.local.items()}

    def tri_array(self, W):
        return np.array([[W[t[0]][i] for i in t[3]] for t in self.tris], float).reshape(-1, 3, 3)

    def height(self, W=None):
        W = W if W is not None else self.world(self.rest())
        allv = np.concatenate([v for v in W.values() if len(v)]) if W else np.zeros((1, 3))
        return float(max(np.ptp(allv[:, 1]), 1.0)), allv


# ------------------------------------------------------------------ rendering
def _rotate(P, yaw, pitch):
    cy, sy = math.cos(yaw), math.sin(yaw)
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    X, Z = cy * x + sy * z, -sy * x + cy * z
    cp, sp = math.cos(pitch), math.sin(pitch)
    Y, Z2 = cp * y - sp * Z, sp * y + cp * Z
    return np.stack([X, Y, Z2], -1)


def render(model, T, yaw, pitch=0.0, size=SIZE, frame=None, cull=True):
    """Render triangles T (n,3,3 world) seen along +Z after the rotation. Returns
    (rgb image, any-face mask, culled mask (before transparency), drawn mask (after transparency), id buffer)."""
    P = _rotate(T, yaw, pitch)
    if frame is None:
        allp = P.reshape(-1, 3)
        mn, mx = allp[:, :2].min(0), allp[:, :2].max(0)
        sc = (size - 8) / max(float((mx - mn).max()), 1.0)
        off = size / 2 - (mn + mx) / 2 * sc
        frame = (sc, off)
    sc, off = frame
    S = P[..., :2] * sc + off
    Z = P[..., 2]
    zb = np.full((size, size), np.inf)
    zany = np.full((size, size), np.inf)
    zcull = np.full((size, size), np.inf)
    ids = np.full((size, size), -1, np.int32)
    img = np.zeros((size, size, 3), np.uint8)
    img[:] = (40, 44, 52)
    tex = model.tex
    ys, xs = np.mgrid[0:size, 0:size] + 0.5
    for k, t in enumerate(model.tris):
        p = S[k]
        area = (p[1, 0] - p[0, 0]) * (p[2, 1] - p[0, 1]) - (p[1, 1] - p[0, 1]) * (p[2, 0] - p[0, 0])
        if abs(area) < 1e-9:
            continue
        x0, x1 = max(0, int(p[:, 0].min())), min(size - 1, int(p[:, 0].max()) + 1)
        y0, y1 = max(0, int(p[:, 1].min())), min(size - 1, int(p[:, 1].max()) + 1)
        if x1 < x0 or y1 < y0:
            continue
        px, py = xs[y0:y1 + 1, x0:x1 + 1], ys[y0:y1 + 1, x0:x1 + 1]
        w0 = ((p[1, 0] - px) * (p[2, 1] - py) - (p[1, 1] - py) * (p[2, 0] - px)) / area
        w1 = ((p[2, 0] - px) * (p[0, 1] - py) - (p[2, 1] - py) * (p[0, 0] - px)) / area
        w2 = 1 - w0 - w1
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not inside.any():
            continue
        z = w0 * Z[k, 0] + w1 * Z[k, 1] + w2 * Z[k, 2]
        sub = (slice(y0, y1 + 1), slice(x0, x1 + 1))
        za = zany[sub]
        za[inside] = np.minimum(za[inside], z[inside])
        if area < 0 and cull:
            continue          # a back face: culled like the game does (GsTMDfast ignores the TMD double-sided flag)
        zc = zcull[sub]
        zc[inside] = np.minimum(zc[inside], z[inside])
        color = None
        opaque = inside
        if t[4] is not None and tex is not None:
            idx, pal, rgb = tex
            uv = np.array(t[4], float)
            u = np.clip((w0 * uv[0, 0] + w1 * uv[1, 0] + w2 * uv[2, 0]).astype(int), 0, idx.shape[1] - 1)
            v = np.clip((w0 * uv[0, 1] + w1 * uv[1, 1] + w2 * uv[2, 1]).astype(int), 0, idx.shape[0] - 1)
            row = min(max(t[5], 0), pal.shape[0] - 1)
            ci = idx[v, u]
            opaque = inside & (pal[row][ci] != 0)
            color = rgb[row][ci]
        zz = zb[sub]
        win = opaque & (z < zz)
        if not win.any():
            continue
        zz[win] = z[win]
        ids[sub][win] = k
        if color is None:
            color = np.broadcast_to(np.array(t[7], np.uint8), win.shape + (3,))
        # flat light: facing the camera is bright
        a, b = T[k, 1] - T[k, 0], T[k, 2] - T[k, 0]
        n = np.cross(_rotate(a, yaw, pitch), _rotate(b, yaw, pitch))
        shade = 0.55 + 0.45 * abs(n[2]) / (np.linalg.norm(n) or 1)
        img[sub][win] = (color[win] * shade).astype(np.uint8)
    return img, np.isfinite(zany), np.isfinite(zcull), np.isfinite(zb), ids, frame


def view_stats(model, pose=None, size=SIZE):
    """{view: dict(holes, clear, cover)} and the rendered images (for sheets)."""
    pose = pose if pose is not None else model.rest()
    W = model.world(pose)
    T = model.tri_array(W)
    out, imgs = {}, {}
    for name, yaw, pitch in VIEWS + RING:
        img, anyf, culled, drawn, _, _ = render(model, T, yaw, pitch, size)
        n = int(anyf.sum()) or 1
        holes = anyf & ~culled
        out[name] = dict(holes=round(float(holes.sum()) / n, 4), clear=round(float((culled & ~drawn).sum()) / n, 4))
        mark = img.copy()
        mark[holes] = (255, 0, 255)
        imgs[name] = (img, mark)
    return out, imgs


# ------------------------------------------------------------------ topology
def _weld(V, tol=0.5):
    """Index of each vertex after welding by position."""
    key = np.round(V / tol).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    return inv.reshape(-1)


def topology(model, W, height):
    """Per bone: open edges, the longest open loop (in heights) and its connected parts."""
    res = {}
    by_bone = {}
    for k, t in enumerate(model.tris):
        by_bone.setdefault(t[0], []).append(k)
    parts = []                      # (bone, world vertex array of the part)
    for b, ks in by_bone.items():
        V = W[b]
        if not len(V):
            continue
        weld = _weld(model.local[b])
        F = np.array([[weld[i] for i in model.tris[k][3]] for k in ks])
        F = F[(F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])]
        if not len(F):
            continue
        # one position per welded id
        pos = np.zeros((weld.max() + 1, 3))
        pos[weld] = V
        edges = {}
        for f in F:
            for a, c in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
                key = (min(a, c), max(a, c))
                edges[key] = edges.get(key, 0) + 1
        open_e = [e for e, n in edges.items() if n == 1]
        # boundary loops: connected components of the open edges
        adj = {}
        for a, c in open_e:
            adj.setdefault(a, []).append(c)
            adj.setdefault(c, []).append(a)
        seen, longest = set(), 0.0
        for s in adj:
            if s in seen:
                continue
            stack, comp = [s], []
            seen.add(s)
            while stack:
                x = stack.pop()
                comp.append(x)
                for y in adj[x]:
                    if y not in seen:
                        seen.add(y)
                        stack.append(y)
            cs = set(comp)
            L = sum(np.linalg.norm(pos[a] - pos[c]) for a, c in open_e if a in cs)
            longest = max(longest, L)
        # connected components of faces
        parent = list(range(len(pos)))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        for f in F:
            ra, rb, rc = find(f[0]), find(f[1]), find(f[2])
            parent[rb] = ra
            parent[find(rc)] = ra
        comps = {}
        for f in F:
            comps.setdefault(find(f[0]), []).append(f)
        for cf in comps.values():
            cf = np.array(cf)
            parts.append((b, pos[np.unique(cf)], pos[cf]))
        res[b] = dict(open=len(open_e), loop=round(longest / height, 3), parts=len(comps))
    return res, parts


def inverted(model):
    """Faces whose winding disagrees with their own stored normals (cos > 0.5): drawn from the inside, culled from the
    outside. Returns {bone: share of the bone's face area}. A DW1 face's stored normal points away from
    cross(v1 - v0, v2 - v0) (measured: Agumon, Greymon, Tokomon ... 98-100 % of their faces)."""
    out = {}
    tmd = model.m.tmd
    for b, (oi, _) in enumerate(model.bones):
        if oi < 0 or oi >= len(tmd.objects):
            continue
        V, N = model.local[b], tmd.obj_norms(oi)
        bad = tot = 0.0
        for p in tmd.objects[oi].prims:
            try:
                d = p.decode()
            except ValueError:
                continue
            ids, ns = d['verts'], d['norms']
            if not ns:
                continue
            for c in [(0, 1, 2)] + ([(1, 3, 2)] if len(ids) == 4 else []):
                a, bb, cc = (V[ids[k]] for k in c)
                g = np.cross(bb - a, cc - a)
                ar = float(np.linalg.norm(g))
                if ar < 1e-6:
                    continue
                sn = np.mean([N[ns[k] if len(ns) > 1 else ns[0]][:3] for k in c], axis=0)
                ln = float(np.linalg.norm(sn))
                tot += ar
                if ln and float(np.dot(g, sn)) / ar / ln > 0.5:
                    bad += ar
        if tot:
            out[b] = round(bad / tot, 3)
    return out


def _point_triangle(P, T):
    """Distance from each point of P (n,3) to the nearest triangle of T (m,3,3)."""
    a, b, c = T[:, 0][None], T[:, 1][None], T[:, 2][None]
    p = P[:, None, :]
    ab, ac, ap = b - a, c - a, p - a
    n = np.cross(ab, ac)
    nn = (n * n).sum(-1)
    ok = nn > 1e-12
    # the projection onto the plane, when it falls inside the triangle
    t = np.where(ok, (ap * n).sum(-1) / np.where(ok, nn, 1), 0)
    q = p - t[..., None] * n
    def inside(u, v, w):
        return (np.cross(v - u, q - u) * n).sum(-1) >= 0
    tri_in = ok & inside(a, b, c) & inside(b, c, a) & inside(c, a, b)
    best = np.where(tri_in, np.abs(t) * np.sqrt(np.where(ok, nn, 1)), np.inf)
    # else the nearest edge
    for u, v in ((a, b), (b, c), (c, a)):
        e = v - u
        k = np.clip(((p - u) * e).sum(-1) / np.maximum((e * e).sum(-1), 1e-12), 0, 1)
        d = np.linalg.norm(p - (u + k[..., None] * e), axis=-1)
        best = np.minimum(best, d)
    return best.min(1)


def detached(parts, height):
    """Parts farther than DETACHED_MIN heights from every other part's surface (the distance, in heights)."""
    out = []
    for i, (b, P, T) in enumerate(parts):
        others = [k for k in range(len(parts)) if k != i]
        if not others:
            break
        OT = np.concatenate([parts[k][2] for k in others])
        OP = np.concatenate([parts[k][1] for k in others])
        best = min(float(_point_triangle(P, OT).min()), float(_point_triangle(OP, T).min()))
        if best >= DETACHED_MIN * height:
            out.append(dict(bone=b, dist=round(best / height, 3), verts=len(P)))
    return out


def tears(model, height, slots=None, step=2, max_ticks=240):
    """Each piece's distance to the nearest other piece, in the idle pose and at its worst over every frame of every
    animation: a piece skinned to the wrong bone, or a joint that opens, leaves the body. [(gap growth in heights,
    bone, slot, tick)], worst first."""
    bones = [b for b, v in model.local.items() if len(v)]
    if len(bones) < 2:
        return []

    def nearest(W):
        out = {}
        for b in bones:
            others = np.concatenate([W[c] for c in bones if c != b])
            d = np.sqrt(((W[b][:, None, :] - others[None, :, :]) ** 2).sum(-1)).min()
            out[b] = float(d)
        return out
    base = nearest(model.world(model.rest()))
    worst = {}
    for s in (slots if slots is not None else model.slots()):
        try:
            poses = model.poses(s, max_ticks)
        except Exception:          # noqa: BLE001 - a slot the player cannot replay
            continue
        for k in range(0, len(poses), step):
            for b, d in nearest(model.world(poses[k])).items():
                g = d - base[b]
                if g > worst.get(b, (0,))[0]:
                    worst[b] = (g, s, k)
    return sorted(((round(g / height, 3), b, s, k) for b, (g, s, k) in worst.items()), reverse=True)


def zfight(model, W, height):
    """Overlapping coplanar face pairs with different texture coordinates: [(bone a, bone b, overlap in heights^2)]."""
    T = model.tri_array(W)
    if not len(T):
        return []
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    ar = np.linalg.norm(n, axis=1)
    ok = ar > 1e-6
    n[ok] /= ar[ok, None]
    d = np.einsum('ij,ij->i', n, T[:, 0])
    c = T.mean(1)
    out = []
    eps = 0.003 * height
    idx = np.nonzero(ok)[0]
    for i in idx:
        cand = idx[idx > i]
        same = cand[(np.abs(np.einsum('j,ij->i', n[i], n[cand])) > 0.998)]
        if not len(same):
            continue
        s = np.sign(np.einsum('j,ij->i', n[i], n[same]))
        same = same[np.abs(d[same] * s - d[i]) < eps]
        same = same[np.linalg.norm(c[same] - c[i], axis=1) < 0.25 * height]
        for j in same:
            if set(model.tris[i][3]) == set(model.tris[j][3]) and model.tris[i][0] == model.tris[j][0]:
                continue       # the same face twice (the two triangles of a double-sided quad)
            a = _overlap(T[i], T[j], n[i])
            if a > ZFIGHT_MIN_AREA * height * height and model.tris[i][4] != model.tris[j][4]:
                out.append((model.tris[i][0], model.tris[j][0], round(a / height / height, 5)))
    return out


def _overlap(A, B, n):
    """Area of the intersection of two coplanar triangles (projected on their plane)."""
    ax = int(np.argmax(np.abs(n)))
    keep = [k for k in range(3) if k != ax]
    p, q = A[:, keep], B[:, keep]

    def clip(poly, a, b):
        out = []
        side = lambda x: (b[0] - a[0]) * (x[1] - a[1]) - (b[1] - a[1]) * (x[0] - a[0])
        for k in range(len(poly)):
            cur, nxt = poly[k], poly[(k + 1) % len(poly)]
            sc, sn = side(cur), side(nxt)
            if sc >= 0:
                out.append(cur)
            if (sc >= 0) != (sn >= 0):
                t = sc / (sc - sn)
                out.append(cur + t * (nxt - cur))
        return out
    def orient(t):
        return t if (t[1, 0] - t[0, 0]) * (t[2, 1] - t[0, 1]) - (t[1, 1] - t[0, 1]) * (t[2, 0] - t[0, 0]) > 0 else t[::-1]
    p, q = orient(p), orient(q)
    poly = list(p)
    for k in range(3):
        if not poly:
            return 0.0
        poly = clip(poly, q[k], q[(k + 1) % 3])
    if len(poly) < 3:
        return 0.0
    P = np.array(poly)
    scale = np.abs(n[ax]) or 1
    return abs(float(np.dot(P[:, 0], np.roll(P[:, 1], -1)) - np.dot(P[:, 1], np.roll(P[:, 0], -1)))) / 2 / scale


# ------------------------------------------------------------------ the whole check
def analyse(model, anims=True):
    rest = model.rest()
    W = model.world(rest)
    height, _ = model.height(W)
    views, imgs = view_stats(model, rest)
    topo, parts = topology(model, W, height)
    inv = inverted(model)
    report = dict(height=round(height), tris=len(model.tris), views=views,
                  open=sum(t['open'] for t in topo.values()),
                  loop=max((t['loop'] for t in topo.values()), default=0),
                  inverted={b: v for b, v in inv.items() if v > INVERTED_MAX},
                  detached=detached(parts, height),
                  zfight=zfight(model, W, height))
    if anims:
        report['tears'] = tears(model, height)[:5]
    report['flags'] = flags(report)
    return report, imgs


def flags(r):
    f = []
    worst = max(r['views'].items(), key=lambda kv: kv[1]['holes'])
    if worst[1]['holes'] > HOLES_MAX:
        f.append(f'see-through {worst[0]} {worst[1]["holes"]:.0%}')
    far = [d for d in r['detached'] if d['dist'] >= DETACHED_FLAG]
    if far:
        f.append(f'detached parts {[(d["bone"], d["dist"]) for d in far]}')
    st = [s for s in r.get('tears', []) if s[0] > STRETCH_MAX]
    if st:
        f.append(f'piece leaves the body by {st[0][0]:.0%} of height (bone {st[0][1]}, slot {st[0][2]}, tick {st[0][3]})')
    return f


# ------------------------------------------------------------------ sheets
def png(path, img):
    h, w = img.shape[:2]
    raw = b''.join(b'\0' + img[y].tobytes() for y in range(h))
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
                           + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


def sheet(imgs):
    """Two rows: textured views as the game draws them, and the same with see-through pixels in magenta."""
    top = np.concatenate([imgs[v][0] for v, _, _ in VIEWS], 1)
    bot = np.concatenate([imgs[v][1] for v, _, _ in VIEWS], 1)
    return np.concatenate([top, bot], 0)


# ------------------------------------------------------------------ extraction from a build
def extract(digi, out):
    import species as S
    import coldsplit
    os.makedirs(out, exist_ok=True)
    d, count, recs = S.read_archive(digi)
    carried = S.record_originals(d)
    e = mmd.Exe(include_imports=False)
    alltim_path = os.path.join(ROOT, 'extracted/CHDAT/ALLTIM.TIM')
    alltim = open(alltim_path, 'rb').read() if os.path.exists(alltim_path) else None
    idx = {}
    for t in range(count):
        r = recs[t]
        nb = r['para']['boneCount']
        if t >= S.NUM_ORIGINAL or t in carried:
            if not r['flags'] & S.FLAG_DEFINED or not r['modelSize']:
                continue
            model = d[r['modelSector'] * S.SECTOR:r['modelSector'] * S.SECTOR + r['modelSize']]
            if coldsplit.is_split(model):
                n = coldsplit.cold_length(model)
                c0 = r['modelSector'] + -(-r['modelSize'] // S.SECTOR)
                model = coldsplit.join(model, d[c0 * S.SECTOR:c0 * S.SECTOR + n], nb, coldsplit.table_length(model))
            tex = d[r['texSector'] * S.SECTOR:r['texSector'] * S.SECTOR + S.TEX_SIZE]
            bones = r['bones']
        else:
            p = os.path.join(ROOT, f'extracted/CHDAT/MMD{t // 30}/{r["modelName"]}.MMD')
            if not os.path.exists(p):
                continue
            model = open(p, 'rb').read()
            tex = mmd.alltim_entry(alltim, t) if alltim else None
            bones = [list(b) for b in e.skeleton[t]]
        open(os.path.join(out, f'{t}.MMD'), 'wb').write(model)
        if tex:
            open(os.path.join(out, f'{t}.TIM'), 'wb').write(tex)
        idx[t] = dict(name=r['para']['name'], bones=bones, partner=bool(r['flags'] & S.FLAG_PARTNER))
    json.dump(idx, open(os.path.join(out, 'index.json'), 'w'))
    return idx


def load_dir(d, t, row):
    data = open(os.path.join(d, f'{t}.MMD'), 'rb').read()
    tp = os.path.join(d, f'{t}.TIM')
    tim = open(tp, 'rb').read() if os.path.exists(tp) else None
    return Model(data, row['bones'], tim)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('check')
    c.add_argument('mmd'); c.add_argument('tim'); c.add_argument('--bones', required=True)
    c.add_argument('--sheet')
    a = sub.add_parser('audit')
    a.add_argument('dir'); a.add_argument('ids', nargs='*'); a.add_argument('--out'); a.add_argument('--sheets')
    a.add_argument('--no-anims', action='store_true'); a.add_argument('--jobs', type=int, default=1)
    x = sub.add_parser('extract')
    x.add_argument('digi'); x.add_argument('out')
    args = ap.parse_args()
    if args.cmd == 'extract':
        print(len(extract(args.digi, args.out)), 'species')
    elif args.cmd == 'check':
        bones = json.loads(open(args.bones).read()) if os.path.exists(args.bones) else json.loads(args.bones)
        m = Model(open(args.mmd, 'rb').read(), bones, open(args.tim, 'rb').read())
        r, imgs = analyse(m)
        print(json.dumps(r, indent=1))
        if args.sheet:
            png(args.sheet, sheet(imgs))
        sys.exit(1 if r['flags'] else 0)
    elif args.cmd == 'audit':
        idx = json.load(open(os.path.join(args.dir, 'index.json')))
        todo = [t for t in sorted(idx, key=int)
                if not args.ids or t in args.ids or idx[t]['name'] in args.ids]
        work = [(args.dir, t, idx[t], not args.no_anims, args.sheets) for t in todo]
        if args.jobs > 1:
            import multiprocessing
            with multiprocessing.Pool(args.jobs) as pool:
                results = pool.imap(_audit_one, work)
                out = dict(_print(r) for r in results)
        else:
            out = dict(_print(_audit_one(w)) for w in work)
        if args.out:
            json.dump(out, open(args.out, 'w'), indent=1)


def _print(res):
    t, r = res
    print(t, r['name'], 'ERROR ' + r['error'] if 'error' in r else '; '.join(r['flags']) or 'ok', flush=True)
    return t, r


def _audit_one(job):
    d, t, row, anims, sheets = job
    try:
        m = load_dir(d, t, row)
        r, imgs = analyse(m, anims)
    except Exception as ex:          # noqa: BLE001 - one broken model must not stop the audit
        return t, dict(name=row['name'], error=repr(ex)[:200])
    r['name'] = row['name']
    if sheets and r['flags']:
        os.makedirs(sheets, exist_ok=True)
        png(os.path.join(sheets, f'{t}-{r["name"]}.png'), sheet(imgs))
    return t, r

if __name__ == '__main__':
    main()
