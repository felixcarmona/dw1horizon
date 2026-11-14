#!/usr/bin/env python3
"""A Digimon World 2 technique effect as a Digimon World effect chunk (ETCHI/EFEDAT.EFE).

A DW2 technique shows up to three cast objects at the caster and up to three hit objects at each target
(docs/reference/dw2-effects.md). Every drawn bone of every object becomes TMD objects of the chunk; its pose
at every engine tick (20 Hz) is a rotation (the effect engine's drawTMDYXZ: Ry * Rx * Rz), a per-axis scale and
a translation in the caster's facing frame, kept once per distinct pose in small tables the chunk's scripts
read. Only a sheared pose (which no rotation times scale can draw) stops the conversion.

What the scripts do (docs/mods/signature-effects.md):
- a controller turns the caster to its target and spawns the cast objects, each at its DW2 anchor: slot 0
  above the caster's head, slot 1 at the launch point of the technique the chunk stands in for, slot 2 at
  the caster's feet;
- a cast object that flies a long way forward (a "traveller") flies to its target: it aims at the target when
  it leaves and its forward travel is stretched when the target is farther than DW2's flight; the first one
  that reaches the target's body deals the hit. Area techniques (`area`) send one per target;
- without a traveller the hit comes when the cast objects end (DW2's cut to the target);
- a hit deals the technique's damage with addAttackObjectToTarget (`hits` times) on the target and plays the
  hit objects there (slot 0 above its head, slot 1 at mid height, slot 2 at its feet), turned to the caster.
  An area technique does this for every other fighter on the field, as Digimon World's own DG Dimension
  does (selectNextTargetEntity).
"""
import math
import os
import struct
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools import dw2effect as D            # noqa: E402
from tools.efescript import Asm, HEADER, CHUNK   # noqa: E402

DW2_FPS, ENGINE_HZ = 30, 20            # a DW2 effect frame is two 60 Hz ticks; the battle logic ticks at 20 Hz
STRIP_W, STRIP_H = 256, 32             # an effect's texture slot (4bpp texels) and its palette rows
PALETTE_ROWS = 6
CLUT_BASE = 0x7a08                     # the loader moves the TMD's palette ids from here to the slot's rows
TSB = 0x19                             # 4bpp; the blend rate goes in bits 5-6; the loader puts in the slot's page
QUAD_MODE, TRI_MODE = 0x2d, 0x25       # flat, textured, unlit (brightness off); | 2 = semi-transparent
INST = 0x78                            # instance size: frame, position, rotation, then the fields below
I_FRAME, I_POS, I_ROT = 0x00, 0x04, 0x10
I_ORIGIN, I_YAW, I_STATE, I_VEC, I_SCALE = 0x1c, 0x28, 0x34, 0x38, 0x44
I_IDX, I_P, I_O, I_KN, I_KD, I_DIST, I_TMP, I_COPY = 0x50, 0x54, 0x58, 0x5c, 0x60, 0x64, 0x68, 0x74
HOME_DISTANCE = 0x2800                 # DW2: between the two rows of fighters
TRAVEL = 0.3                           # a cast object that flies this share of it forward is a traveller
CAST_FRAMES, HIT_FRAMES = 60, 30       # DW2 shows a cast object 120 ticks, a hit object 60
MAX_TARGETS = 3                        # an area technique's other fighters: partner and three enemies at most
OVERHEAD = 0x280                       # DW2 slot 0: this far above the head
SHEAR = 0.01


class Unconvertible(SystemExit):
    pass


def ticks_of(frames):
    """Engine ticks that cover a DW2 clip of `frames` frames."""
    return (frames * ENGINE_HZ + DW2_FPS - 1) // DW2_FPS


def frame_at(tick, frames):
    return min(round(tick * DW2_FPS / ENGINE_HZ), frames - 1)


# ----------------------------------------------------------------- poses

def rot_yxz(a, b, c):
    """libgte RotMatrixYXZ (angles in radians) in right-handed rows: Ry(b) * Rx(a) * Rz(c)."""
    ca, sa, cb, sb, cc, sc = math.cos(a), math.sin(a), math.cos(b), math.sin(b), math.cos(c), math.sin(c)
    return [[cb * cc + sb * sa * sc, -cb * sc + sb * sa * cc, sb * ca],
            [ca * sc, ca * cc, -sa],
            [-sb * cc + cb * sa * sc, sb * sc + cb * sa * cc, cb * ca]]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def decompose(r, where=''):
    """(a, b, c, (sx, sy, sz)) with r = rot_yxz(a, b, c) * diag(s), a scale negative when the pose is mirrored;
    None when the bone is not drawn (all scales zero). Stops on a shear."""
    cols = [[r[i][j] for i in range(3)] for j in range(3)]
    s = [math.sqrt(sum(x * x for x in c)) for c in cols]
    if max(s) < 1e-3:
        return None
    live = [j for j in range(3) if s[j] > 1e-3 * max(s)]
    unit = [[x / s[j] for x in cols[j]] if j in live else None for j in range(3)]
    for i in live:
        for j in live:
            if i < j and abs(sum(x * y for x, y in zip(unit[i], unit[j]))) > SHEAR:
                raise Unconvertible(f'{where}: sheared pose; drawTMDYXZ cannot draw it')
    if len(live) == 1:                      # a line: any axes across it
        k = live[0]
        a = unit[k]
        helper = [1, 0, 0] if abs(a[0]) < 0.9 else [0, 1, 0]
        n = _cross(a, helper)
        ln = math.sqrt(sum(x * x for x in n))
        unit[(k + 1) % 3] = [x / ln for x in n]
        live.append((k + 1) % 3)
    for k in range(3):
        if unit[k] is None:
            unit[k] = _cross(unit[(k + 1) % 3], unit[(k + 2) % 3])
            s[k] = 0.0
    det = sum(unit[0][i] * _cross(unit[1], unit[2])[i] for i in range(3))
    if det < 0:                             # mirrored: turn the smallest axis around
        k = min(range(3), key=lambda j: s[j])
        unit[k] = [-x for x in unit[k]]
        s[k] = -s[k]
    m = [[unit[j][i] for j in range(3)] for i in range(3)]
    sa = max(-1.0, min(1.0, -m[1][2]))
    a = math.asin(sa)
    if math.hypot(m[1][0], m[1][1]) > 1e-6:
        b = math.atan2(m[0][2], m[2][2])
        c = math.atan2(m[1][0], m[1][1])
    else:
        b = math.atan2(-m[2][0], m[0][0])
        c = 0.0
    return a, b, c, s


def angle(x):
    return round(x * 2048 / math.pi) & 0xfff


# ----------------------------------------------------------------- texture

def _stp(c):
    return 0 if c == 0 else 2 if c & 0x8000 else 1          # transparent, solid, blending


def _rgb(c):
    return (c & 0x1f, (c >> 5) & 0x1f, (c >> 10) & 0x1f)


def _d2(a, b):
    return sum((x - y) ** 2 for x, y in zip(_rgb(a), _rgb(b)))


def colours(image, clut):
    """The prim's 16 colours. A palette with neither a transparent colour nor a blending one (Metal Fireball's
    ring: a plain gradient) would draw its whole square opaque here, where only colours with the top bit
    blend: its colour 0 (the block's background) becomes transparent and the others blend."""
    row = image[(clut >> 6) % len(image)]
    cols = [row[((clut & 0x3f) * 16 + i) % len(row)] for i in range(16)]
    if 0 not in cols and not any(c & 0x8000 for c in cols):
        cols = [0] + [c | 0x8000 for c in cols[1:]]
    return tuple(cols)


def index_at(image, u, v):
    return (image[v % len(image)][(u >> 2) % len(image[0])] >> (4 * (u & 3))) & 0xF


class Group:
    """A palette row of the new strip and the DW2 palettes that use it."""

    def __init__(self, cols, hist):
        self.cols, self.hist = list(cols), list(hist)


def reduce_palettes(pals, hists, rows=PALETTE_ROWS):
    """Merge palettes until `rows` remain. pals: distinct 16-colour tuples, hists: texels drawn with each
    index. A merge keeps index positions where the two agree on transparency and blending (colours averaged by
    texel count), else maps the indices to the nearest colours of the same kind (texels remapped). Returns
    (rows of colours, per palette (row, index map))."""
    groups = [Group(p, h) for p, h in zip(pals, hists)]
    member = [(i, tuple(range(16))) for i in range(len(pals))]
    while len(groups) > rows:
        best = None
        for i in range(len(groups)):
            for j in range(len(groups)):
                if i == j:
                    continue
                gi, gj = groups[i], groups[j]
                both = [k for k in range(16) if gi.hist[k] and gj.hist[k]]
                if all(_stp(gi.cols[k]) == _stp(gj.cols[k]) for k in both):
                    cost = sum(min(gi.hist[k], gj.hist[k]) * _d2(gi.cols[k], gj.cols[k]) for k in both)
                    cand = (cost, 0, i, j, None)
                else:
                    mp, cost = list(range(16)), 0
                    for k in range(16):
                        if not gj.hist[k]:
                            continue
                        same = [x for x in range(16) if _stp(gi.cols[x]) == _stp(gj.cols[k])
                                and (gi.hist[x] or x == k)]
                        if not same:
                            cost = None
                            break
                        mp[k] = min(same, key=lambda x: _d2(gi.cols[x], gj.cols[k]))
                        cost += gj.hist[k] * _d2(gi.cols[mp[k]], gj.cols[k])
                    if cost is None:
                        continue
                    cand = (cost, 1, i, j, mp)
                if best is None or cand[:2] < best[:2]:
                    best = cand
        if best is None:
            raise Unconvertible(f'effect: {len(groups)} palettes and no two can share a row')
        _cost, kind, i, j, mp = best
        gi, gj = groups[i], groups[j]
        if mp is None:
            for k in range(16):
                if gj.hist[k] and gi.hist[k]:
                    w = gi.hist[k] + gj.hist[k]
                    c = [round((x * gi.hist[k] + y * gj.hist[k]) / w) for x, y in zip(_rgb(gi.cols[k]), _rgb(gj.cols[k]))]
                    v = c[0] | c[1] << 5 | c[2] << 10 | (gi.cols[k] & 0x8000)
                    gi.cols[k] = v if v or not gi.cols[k] else 1
                elif gj.hist[k]:
                    gi.cols[k] = gj.cols[k]
                gi.hist[k] += gj.hist[k]
            mp = list(range(16))
        else:
            for k in range(16):
                gi.hist[mp[k]] += gj.hist[k]
        member = [((i if g == j else g), tuple(mp[x] for x in m) if g == j else m) for g, m in member]
        del groups[j]
        member = [((g - 1 if g > j else g), m) for g, m in member]
    return [tuple(g.cols) for g in groups], member


class Block:
    """Rectangles of a DW2 texture copied into the strip (reduced by `factor`, maybe turned on its side). A
    flipbook's frames (`rects`, all one size) go side by side, `step` texels apart, for a UV animation."""

    def __init__(self, image, rects, pal, imap):
        self.image, self.rects, self.pal, self.imap = image, rects, pal, imap
        self.factor, self.turned, self.at = 1, False, None

    @property
    def rect(self):
        return self.rects[0]

    @property
    def src(self):
        return self.rect[2] - self.rect[0] + 1, self.rect[3] - self.rect[1] + 1

    def frame_size(self, f=None, turned=None):
        f = self.factor if f is None else f
        turned = self.turned if turned is None else turned
        w, h = self.src
        w, h = -(-w // f), -(-h // f)
        return (h, w) if turned else (w, h)

    def fits(self, f, turned, width=STRIP_W):
        w, h = self.frame_size(f, turned)
        n = len(self.rects)
        return h <= STRIP_H and n * w <= width and (n - 1) * w <= 128

    @property
    def step(self):
        return self.frame_size()[0]

    def size(self):
        w, h = self.frame_size()
        return w * len(self.rects), h

    def uv(self, u, v):
        """The strip's (u, v) of a DW2 texel of the first frame."""
        f = self.factor
        du, dv = (u - self.rect[0]) // f, (v - self.rect[1]) // f
        if self.turned:
            du, dv = dv, du
        return self.at[0] + du, self.at[1] + dv

    def texel(self, x, y, cols):
        """The strip's index at (x, y) of the block: the f x f source texels, averaged."""
        k, x = divmod(x, self.step)
        rect = self.rects[k]
        if self.turned:
            x, y = y, x
        f = self.factor
        u0, v0 = rect[0] + x * f, rect[1] + y * f
        idx = [self.imap[index_at(self.image, u, v)] for v in range(v0, min(v0 + f, rect[3] + 1))
               for u in range(u0, min(u0 + f, rect[2] + 1))]
        if not idx:
            return 0
        if len(idx) == 1:
            return idx[0]
        solid = [i for i in idx if cols[i] != 0]
        if len(solid) * 2 < len(idx):
            return next((i for i in idx if cols[i] == 0), 0)
        rgb = [sum(_rgb(cols[i])[k] for i in solid) / len(solid) for k in range(3)]
        return min(solid, key=lambda i: sum((a - b) ** 2 for a, b in zip(_rgb(cols[i]), rgb)))


def pack(blocks, base=2, width=STRIP_W):
    """Factors, turns and places for the blocks in the 256x32 strip: each block reduced `base` times (more when
    it does not fit), turned when that needs less reduction, then the biggest reduced further until they all
    fit."""
    for b in blocks:
        options = []
        for turned in (False, True):
            f = max(1, base)
            while not b.fits(f, turned, width):
                f += 1
            options.append((f, turned))
        b.factor, b.turned = min(options)
    while True:
        places = D.shelf_pack([b.size() for b in blocks], width, STRIP_H)
        if places is not None:
            for b, p in zip(blocks, places):
                b.at = p
            return
        big = max(blocks, key=lambda b: (b.size()[0] * b.size()[1], -b.factor))
        if big.factor >= 8:
            raise Unconvertible('effect: the texture blocks do not fit the 256x32 slot')
        big.factor += 1


# ----------------------------------------------------------------- geometry

class TmdObject:
    def __init__(self, verts, prims):
        self.verts, self.prims = verts, prims       # prims: (vertex indices, uvs, palette row, blend or None)


def own_vertices(verts, prims):
    """Only the vertices the prims use, each position once, and the prims renumbered to them."""
    table, index = [], {}
    out = []
    for vs, *rest in prims:
        ids = []
        for v in vs:
            if verts[v] not in index:
                index[verts[v]] = len(table)
                table.append(verts[v])
            ids.append(index[verts[v]])
        out.append((ids, *rest))
    return table, out


def tmd(objects):
    """A TMD (offsets relative to the object table, as GsMapModelingData wants) of flat textured prims."""
    table = bytearray()
    body = bytearray()
    start = 28 * len(objects)
    for o in objects:
        prim_at = start + len(body)
        for vs, uvs, row, blend in o.prims:
            cba = CLUT_BASE + row * 0x40
            semi = 0 if blend is None else 2
            tsb = TSB | (0 if blend is None else blend) << 5
            if len(vs) == 4:
                body += struct.pack('<4B', 9, 7, 1, QUAD_MODE | semi)
                body += struct.pack('<2BH2BH2BH2BH', *uvs[0], cba, *uvs[1], tsb, *uvs[2], 0, *uvs[3], 0)
                body += struct.pack('<4B4H', 0x80, 0x80, 0x80, 0, *vs)
            else:
                body += struct.pack('<4B', 7, 6, 1, TRI_MODE | semi)
                body += struct.pack('<2BH2BH2BH', *uvs[0], cba, *uvs[1], tsb, *uvs[2], 0)
                body += struct.pack('<4B4H', 0x80, 0x80, 0x80, 0, vs[0], vs[1], vs[2], 0)
        vert_at = start + len(body)
        for v in o.verts:
            body += struct.pack('<4h', *v, 0)
        table += struct.pack('<7I', vert_at, len(o.verts), vert_at, 0, prim_at, len(o.prims), 0)
    return struct.pack('<3I', 0x41, 0, len(objects)) + table + body


def blocks_of(effect, box):
    for r in D.uv_blocks(effect):
        if r[0] <= box[0] and r[1] <= box[1] and box[2] <= r[2] and box[3] <= r[3]:
            return r
    raise Unconvertible(f'uv box {box} is in no block')


def uv_box(p):
    us, vs = [u for u, _ in p.uvs], [v for _, v in p.uvs]
    return min(us), min(vs), max(us), max(vs)


def flat(effect, bone):
    vs = effect.bones[bone].vertices
    return any(len({v[k] for v in vs}) == 1 for k in range(3))


def flips_of(effect):
    """{destination block: (source rects, the move)} of the texture animations."""
    out = {}
    for m in effect.tex_moves:
        dst = (m.dst[0] * 4, m.dst[1], m.dst[0] * 4 + m.size[0] * 4 - 1, m.dst[1] + m.size[1] - 1)
        srcs = [(x * 4, y, x * 4 + m.size[0] * 4 - 1, y + m.size[1] - 1) for x, y in m.frames]
        out[dst] = (srcs, m)
    return out


def flipbook_of(flips, box):
    """The flipbook destination a prim's UV box lies in, or None. A prim need not use its whole destination
    (Pretty Attack's blue squares stop a row short of it), and the texels it shows are the flipbook's frames, not
    what the destination holds before the first copy."""
    for dst in flips:
        if dst[0] <= box[0] and dst[1] <= box[1] and box[2] <= dst[2] and box[3] <= dst[3]:
            return dst
    return None


def flip_ticks(m):
    """Engine ticks per flipbook frame (a DW2 frame lasts two 60 Hz ticks with a period, else eight)."""
    return max(1, round((2 if m.period else 8) / 3))


# ----------------------------------------------------------------- objects

class Part:
    """A drawn bone: its TMD objects (the prims without a flipbook, then one per flipbook, which a UV animation
    moves through the flipbook's frames) and its pose id at each tick from t0."""

    def __init__(self, bone):
        self.bone = bone
        self.ids = []                       # TMD object ids
        self.poses = []                     # pose id per tick from t0, -1 hidden
        self.t0 = 0
        self.moves = False


class Obj:
    """One DW2 effect object of the technique."""

    def __init__(self, kind, slot, effect, scale, name):
        self.kind, self.slot, self.effect, self.scale, self.name = kind, slot, effect, scale, name
        self.parts = []
        self.ticks = 0
        self.traveller = False
        self.lead = None
        self.launch = 0
        self.travel = 0                     # forward travel, this game's units at the fixed scale


def world(effect, f):
    cache = effect.__dict__.setdefault('_world', {})
    if f not in cache:
        cache[f] = D.world(effect, f)
    return cache[f]


def visible_frames(effect):
    vis = []
    for f in range(len(effect.frames)):
        W = world(effect, f)
        vis.append(any(D.scale_of(r) > 1e-3 and bone.prims for (r, _), bone in zip(W, effect.bones)))
    return vis


def invisible(effect, p, rect, srcs):
    """Every texel the prim could show is transparent in every flipbook frame."""
    cols = colours(effect._image, p.clut)
    u0, v0, u1, v1 = uv_box(p)
    for src in srcs:
        du, dv = src[0] - rect[0], src[1] - rect[1]
        for v in range(v0, v1 + 1):
            for u in range(u0, u1 + 1):
                if cols[index_at(effect._image, u + du, v + dv)]:
                    return False
    return True


def build(objs, step=1, quant=1):
    """Pose tables, parts and texture blocks of every object. Returns (poses, prim refs). step: hold each pose
    that many ticks; quant: round translations and scales to multiples of it (and angles to 16 times it): both
    shrink the pose tables of the largest effects."""
    q = lambda x, n=quant: round(x / n) * n
    poses = {}
    uses = []                               # (obj, part, prim, its block, source rects, the flipbook or None)
    for o in objs:
        e = o.effect
        e._image = e._image if hasattr(e, '_image') else D.tim_halfwords(e.tim)
        vis = visible_frames(e)
        if not any(vis):
            continue
        last = len(vis) - 1 - vis[::-1].index(True)
        limit = CAST_FRAMES if o.kind == 'cast' else HIT_FRAMES
        o.ticks = ticks_of(min(limit, last + 1, len(e.frames)))
        flips = flips_of(e)
        for b, bone in enumerate(e.bones):
            if not bone.prims:
                continue
            rows = []
            for t in range(o.ticks):
                f = frame_at(t - t % step, len(e.frames))
                r, tr = world(e, f)[b]
                p = decompose(r, f'{o.name} bone {b} frame {f}')
                rows.append(None if p is None or max(abs(x) for x in p[3]) * o.scale * 4096 < 0.5 else (p, tr))
            if not any(rows):
                continue
            part = Part(b)
            part.t0 = next(t for t, x in enumerate(rows) if x)
            t1 = len(rows) - next(t for t, x in enumerate(reversed(rows)) if x)
            peak = max(abs(x) for row in rows if row for x in row[0][3]) * o.scale * 4096
            part.prescale = max(1, math.ceil(peak / 32000))
            mirrored = any(row and any(x < 0 for x in row[0][3]) for row in rows)
            vmax = max((abs(c) for v in bone.vertices for c in v), default=0)
            if vmax * part.prescale > 32767:
                raise Unconvertible(f'{o.name} bone {b}: scale too large for int16 vertices')
            ts = []
            for row in rows[part.t0:t1]:
                if row is None:
                    part.poses.append(-1)
                    continue
                (a, bb, c, s), tr = row
                key = (*(q(angle(x), 16 * quant) & 0xfff if quant > 1 else angle(x) for x in (a, bb, c)),
                       *(q(x * o.scale * 4096 / part.prescale) for x in s),
                       *(q(x * o.scale) for x in tr))
                if any(abs(x) > 32767 for x in key[3:]):
                    raise Unconvertible(f'{o.name} bone {b}: pose out of int16 range')
                ts.append(key[6:])
                part.poses.append(poses.setdefault(key, len(poses)))
            part.moves = len(set(ts)) > 1 and max(abs(x - y) for t in ts for x, y in zip(t, ts[0])) > 1
            part.both = flat(e, b) or mirrored
            part.travel = max(0, -min(t[2] for t in ts))
            seen = set()
            for p in bone.prims:
                k = (tuple(sorted(p.verts)), tuple(sorted(p.uvs)), p.clut, p.blend)
                if k in seen:                # the same face twice
                    continue
                seen.add(k)
                rect = flipbook_of(flips, uv_box(p)) or blocks_of(e, uv_box(p))
                if invisible(e, p, rect, flips[rect][0] if rect in flips else (rect,)):
                    continue
                if rect in flips:
                    uses.append((o, part, p, rect, tuple(flips[rect][0]), flips[rect][1]))
                else:
                    uses.append((o, part, p, rect, (rect,), None))
            o.parts.append(part)
        # a traveller: flies forward a good part of the way to the other row
        if o.kind == 'cast' and o.parts:
            lead = max(o.parts, key=lambda p: p.travel)
            if lead.travel >= TRAVEL * HOME_DISTANCE * o.scale:
                o.traveller, o.lead, o.travel = True, lead, lead.travel
                inv = {v: k for k, v in poses.items()}
                tz = [inv[i][8] if i >= 0 else 0 for i in lead.poses]
                moved = next((t for t, z in enumerate(tz) if z < -1), 0)
                o.launch = max(1, lead.t0 + moved - 1)
    return poses, uses


# ----------------------------------------------------------------- the chunk

class Chunk:
    def __init__(self):
        self.data = bytearray()

    def put(self, b, align=4):
        while len(self.data) % align:
            self.data.append(0)
        at = len(self.data)
        self.data.extend(b)
        return at


# (pose step, pose quantum, texture width, back faces), finest first: the first that fits the slot is used
LEVELS = ((1, 1, 256, 2), (2, 1, 256, 2), (2, 2, 256, 2), (3, 2, 256, 2), (3, 4, 256, 2), (4, 4, 256, 2),
          (2, 2, 128, 2), (4, 4, 128, 2), (2, 2, 128, 1), (4, 4, 128, 1))


def convert_skill(*args, **kw):
    """_convert_skill at the finest pose detail whose chunk fits the slot; info['detail'] names the level."""
    for n, (step, quant, width, sides) in enumerate(LEVELS):
        try:
            chunk, info = _convert_skill(*args, step=step, quant=quant, width=width, sides=sides, **kw)
        except Unconvertible as e:
            if 'slot has' not in str(e) or n == len(LEVELS) - 1:
                raise
            continue
        info['detail'] = (f'step {step} quant {quant}' + ('' if width == STRIP_W else f' texture {width}')
                          + ('' if sides == 2 else ' one-sided'))
        return chunk, info


def _convert_skill(casts, hits, origin_table, effect_id, scale, hit_scale=None, area=False, n_hits=1,
                   self_target=False, half=True, launch_sound=14, start_sound=2, step=1, quant=1,
                   width=STRIP_W, sides=2):
    """The chunk (0x5000 bytes) and a summary for a technique: casts and hits are lists of (DW2 slot 0-2,
    dw2effect.Effect). hit_scale: the hit objects' own scale (default: scale). area: hit every other fighter
    (DW1 range 3). n_hits: damage events per target. self_target: a support technique; its hit objects play on
    the caster and deal no damage."""
    # a support technique's hit objects play on the caster, seen with the cast: at the cast's scale
    hit_scale = scale if hit_scale is None or self_target else hit_scale
    objs = [Obj('cast', s, e, scale, f'cast slot {s}') for s, e in casts]
    objs += [Obj('hit', s, e, hit_scale, f'hit slot {s}') for s, e in hits]
    poses, uses = build(objs, step, quant)
    objs = [o for o in objs if o.parts]
    cast_objs = [o for o in objs if o.kind == 'cast']
    hit_objs = [o for o in objs if o.kind == 'hit']
    if not poses:
        raise Unconvertible('effect: nothing is ever drawn')

    # palettes: gather, reduce, then the blocks under their palette maps
    pal_list, hist, counted = [], [], set()
    for o, part, p, rect, srcs, m in uses:
        cols = colours(o.effect._image, p.clut)
        if cols not in pal_list:
            pal_list.append(cols)
            hist.append([0] * 16)
        if (o.effect.tim, srcs, cols) in counted:
            continue
        counted.add((o.effect.tim, srcs, cols))
        h = hist[pal_list.index(cols)]
        for src in srcs:
            for v in range(src[1], src[3] + 1):
                for u in range(src[0], src[2] + 1):
                    h[index_at(o.effect._image, u, v)] += 1
    rows, member = reduce_palettes(pal_list, hist)
    blocks = {}
    for o, part, p, rect, srcs, m in uses:
        row, imap = member[pal_list.index(colours(o.effect._image, p.clut))]
        k = (o.effect.tim, srcs, imap)
        if k not in blocks:
            blocks[k] = Block(o.effect._image, list(srcs), row, imap)
    pack(list(blocks.values()), 2 if half else 1, width)

    # TMD objects: per part one for the prims without a flipbook, one per flipbook block (UV-animated)
    objects, uv_anims, shared = [], [], {}              # uv_anims: (object id, frames, step, ticks per frame)
    for o in objs:
        e = o.effect
        for part in o.parts:
            bone = e.bones[part.bone]
            groups = {}
            for u in uses:
                if u[0] is o and u[1] is part:
                    _o, _p, p, rect, srcs, m = u
                    row, imap = member[pal_list.index(colours(e._image, p.clut))]
                    b = blocks[(e.tim, srcs, imap)]
                    groups.setdefault(id(b) if m else None, (b, m, []))[2].append((p, b, row, rect))
            verts = [tuple(c * part.prescale for c in v) for v in bone.vertices]
            for key, (b, m, prims) in sorted(groups.items(), key=lambda kv: kv[0] is not None):
                out = []
                for p, bb, row, rect in prims:
                    uvs = [bb.uv(u - rect[0] + bb.rect[0], v - rect[1] + bb.rect[1]) for u, v in p.uvs]
                    out.append((list(p.verts), uvs, row, p.blend))
                    if part.both and sides == 2:
                        order = [0, 2, 1] if len(p.verts) == 3 else [1, 0, 3, 2]
                        out.append(([p.verts[i] for i in order], [uvs[i] for i in order], row, p.blend))
                obj = TmdObject(*own_vertices(verts, out))
                anim = (len(b.rects), b.step, flip_ticks(m)) if m is not None else None
                k = (tuple(obj.verts), tuple((tuple(v), tuple(u), r, bl) for v, u, r, bl in obj.prims), anim)
                if k not in shared:             # the same card on several bones: one object, drawn by each
                    shared[k] = len(objects)
                    if anim:
                        uv_anims.append((len(objects), *anim))
                    objects.append(obj)
                part.ids.append(shared[k])

    # timing
    travellers = [o for o in cast_objs if o.traveller]
    lead = max(travellers, key=lambda o: o.travel) if travellers else None
    cast_end = max((o.ticks for o in cast_objs), default=1)
    hit_tick = None if lead else max(2, min(cast_end, ticks_of(150 // 2)))
    hit_len = max((o.ticks for o in hit_objs), default=ticks_of(12))
    gap = max(2, hit_len // max(1, n_hits))
    events = [1 + i * gap for i in range(max(1, n_hits))]
    follow_end = lead.launch if lead else (hit_tick or 1)

    c = Chunk()
    put = c.put
    g_out = put(struct.pack('<i', 0))
    g_copy = put(struct.pack('<i', 0))
    v_table = put(origin_table, 2)
    root = put(struct.pack('<i', -1) + bytes(0x18))

    def pool(n):
        return put(b''.join(struct.pack('<i', -1) + bytes(INST - 4) for _ in range(n)))
    n_targets = MAX_TARGETS if area else 1
    ctl_pool = pool(1)
    loop_pool = pool(2) if area else None
    for o in cast_objs:
        o.pool_n = n_targets if o.traveller else 1
        o.pool = pool(o.pool_n)
    for o in hit_objs:
        o.pool_n = n_targets
        o.pool = pool(o.pool_n)
    dmg_n = 0 if self_target else n_targets
    dmg_pool = pool(dmg_n) if dmg_n else None
    n_inst = 1 + (2 if area else 0) + sum(o.pool_n for o in cast_objs + hit_objs) + dmg_n

    # pose fields: a table of the distinct poses, or the value when every pose has it
    sizes = {'pools': len(c.data)}
    pose_rows = sorted(poses, key=poses.get)
    fields = []
    for k in range(9):
        vals = [p[k] for p in pose_rows]
        if len(set(vals)) == 1:
            fields.append(('imm', vals[0]))
        else:
            fields.append(('tab', put(struct.pack(f'<{len(vals)}h', *vals), 2)))

    def table(values):
        w = 'i8' if all(-128 <= v < 128 for v in values) else 'i16'
        at = put(struct.pack(f'<{len(values)}{"b" if w == "i8" else "h"}', *values), 2)
        return at, w
    for o in objs:
        for part in o.parts:
            part.tab = table(part.poses)

    uv = put(bytes(0x20 * len(objects)))
    uv_tab = {}
    for oid, n, step, fpf in uv_anims:
        keys = [(fpf, -(n - 1) * step, 0)] + [(fpf, step, 0)] * (n - 1)
        uv_tab[oid] = put(struct.pack('<i', n) + b''.join(struct.pack('<hbb', *k) for k in keys))
    sizes['tables'] = len(c.data) - sizes['pools']
    a = Asm(0)
    a.origin = (len(c.data) + 3) & ~3
    while len(c.data) % 4:
        c.data.append(0)

    def set_var(off, value, where=0):
        a.ld(value)
        a.op('set', off, where)

    def copy(dst, src):
        a.ldv(src, 0)
        a.op('set', dst, 0)

    def load_field(k, index_off):
        kind, v = fields[k]
        if kind == 'imm':
            a.ld(v)
        else:
            a.ldx(v, index_off, 0, 'i16', 'i32')

    def capture():
        """origin = position; yaw vector = (0, rotation y, 0)."""
        for k in range(3):
            copy(I_ORIGIN + 4 * k, I_POS + 4 * k)
        set_var(I_YAW, 0)
        copy(I_YAW + 4, I_ROT + 4)
        set_var(I_YAW + 8, 0)

    def anchor_caster(slot):
        """position and turn of a cast object's anchor; the context's bone offset is set at spawn."""
        if slot == 1:
            a.sub('setTransformToBoneOffset')
        else:
            a.push(0)
            a.sub('setTransformToSourceBone')
            set_var(I_POS + 4, 0)
            if slot == 0:
                a.pusha(I_TMP, 0)
                a.sub('getSourceDigimonSize')
                a.ld(0)
                a.op('sub', I_POS + 4, 0)
                a.ldv(I_TMP + 4, 0)
                a.op('sub', I_POS + 4, 0)
                a.ld(round(OVERHEAD * scale))
                a.op('sub', I_POS + 4, 0)
        capture()

    def toward_target(dst_yaw, flip):
        """dst_yaw = the turn from the position toward the context target (+ 0x800 when flip: facing back);
        I_DIST = the distance on the ground; I_TMP keeps the target's position."""
        a.pusha(I_VEC, 0)
        a.sub('copyTargetEntityPosition')
        for k in range(3):
            copy(I_TMP + 4 * k, I_ORIGIN + 4 * k)
        a.pusha(I_TMP, 0)
        a.pusha(I_VEC, 0)
        a.sub('subtractVectors')
        set_var(I_TMP + 4, 0)
        a.pusha(I_DIST, 0)
        a.pusha(I_TMP, 0)
        a.sub('vectorLength')
        a.pusha(I_SCALE, 0)
        a.pusha(I_TMP, 0)
        a.sub('vectorEulerAngles')
        copy(dst_yaw, I_SCALE + 4)
        if flip:
            a.ld(0x800)
            a.op('add', dst_yaw, 0)

    # --- start: the controller
    a.label('start')
    a._w(17, 1, ctl_pool, -9555, INST, 0)
    a.pusha(v_table, 1)
    a.sub('checkTechCompatibility')
    a.pusha_label('ctl_update')
    a.pusha_label('nothing')
    a.sub('initializeSubEffectInstructions')
    a.sub('faceTargetEntity')
    a.sub('initializeEFETransform')
    a.push(start_sound)
    a.sub('playSound')
    for oid in uv_tab:                       # the flipbooks: started once, they run while the chunk is loaded
        a.ld(0)
        a.br('!=', uv + 0x20 * oid + 0xc, 1, f'uv{oid}', 'i16')
        a.push(oid)
        a.push(1)
        a.pusha(uv_tab[oid], 1)
        a.sub('initializeUVAnim')
        a.label(f'uv{oid}')
    a.ret()

    a.label('init')
    a._w(0x211, 1, root, -9555, 0x1c, 0)
    a.ret()

    a.label('nothing')
    a.ret()

    def spawn_targets(label):
        """call label once per other fighter (area) or for the technique's target."""
        if not area:
            a.call(label)
            return
        set_var(g_copy, 0, 1)
        a.call(f'each_{label}')

    ctl_end = max([cast_end + 1, (hit_tick or 0) + 1] + [o.launch + 1 for o in travellers])
    a.label('ctl_update')
    a.ld(ctl_end)
    a.br('>=', I_FRAME, 0, 'ctl_kill')
    a.ld(follow_end)
    a.br('>=', I_FRAME, 0, 'ctl_spawn')
    a.sub('faceTargetEntity')
    a.sub('initializeEFETransform')
    a.label('ctl_spawn')
    a.ld(1)
    a.br('!=', I_FRAME, 0, 'ctl_hit')
    for i, o in enumerate(cast_objs):
        if o.traveller:
            spawn_targets(f'cast{i}')
        else:
            a.call(f'cast{i}')
    a.label('ctl_hit')
    if hit_tick is not None:
        a.ld(hit_tick)
        a.br('!=', I_FRAME, 0, 'ctl_done')
        spawn_targets('group')
    a.label('ctl_done')
    a.ret()
    a.label('ctl_kill')
    set_var(I_FRAME, -1)
    a.ret()

    # each_X: a short-lived context that walks the fighters (selectNextTargetEntity starts over at a spawn)
    if area:
        loops = {f'cast{i}' for i, o in enumerate(cast_objs) if o.traveller}
        if hit_tick is not None:
            loops.add('group')
        for label in sorted(loops):
            a.label(f'each_{label}')
            a._w(17, 2, loop_pool, -9555, INST, 0)
            a.pusha_label('loop_update')
            a.pusha_label('nothing')
            a.sub('initializeSubEffectInstructions')
            a.sub('initializeEFETransform')
            a.label(f'each_{label}_next')
            a.pusha(g_out, 1)
            a.sub('selectNextTargetEntity')
            a.ld(0)
            a.br('<', g_out, 1, f'each_{label}_end')
            a.call(label)
            a.ld(1)
            a.op('add', g_copy, 1)
            a.jmp(f'each_{label}_next')
            a.label(f'each_{label}_end')
            a.ret()
        a.label('loop_update')
        set_var(I_FRAME, -1)
        a.ret()

    # --- cast objects
    for i, o in enumerate(cast_objs):
        a.label(f'cast{i}')
        a._w(17, o.pool_n, o.pool, -9555, INST, 0)
        a.pusha(v_table, 1)
        a.sub('checkTechCompatibility')
        a.pusha_label(f'cast{i}_update')
        a.pusha_label(f'cast{i}_render')
        a.sub('initializeSubEffectInstructions')
        a.sub('initializeEFETransform')
        set_var(I_STATE, 0)
        set_var(I_KN, 1)
        set_var(I_KD, 1)
        if o.traveller and area:
            a.ldv(g_copy, 1)
            a.op('set', I_COPY, 0)
        else:
            set_var(I_COPY, 0)
        anchor_caster(o.slot)
        a.ret()

        a.label(f'cast{i}_update')
        a.ld(o.ticks)
        a.br('>=', I_FRAME, 0, f'cast{i}_kill')
        if not o.traveller:
            anchor_caster(o.slot)
            a.ret()
        else:
            a.ld(o.launch)
            a.br('>=', I_FRAME, 0, f'cast{i}_flight')
            anchor_caster(o.slot)
            a.ret()
            a.label(f'cast{i}_flight')
            a.ld(o.launch)
            a.br('!=', I_FRAME, 0, f'cast{i}_flying')
            # leave: aim at the target; stretch the travel when the target is farther than DW2's flight
            toward_target(I_YAW + 4, False)
            set_var(I_KD, max(1, o.travel))
            copy(I_KN, I_DIST)
            a.ld(max(1, o.travel))
            a.br('>=', I_KN, 0, f'cast{i}_far')
            set_var(I_KN, max(1, o.travel))
            a.label(f'cast{i}_far')
            # the hit when the lead's travel reaches the target's body
            a.pusha(I_TMP, 0)
            a.sub('getTargetDigimonSize')
            a.ldv(I_TMP, 0)
            a.op('set', I_TMP + 8, 0)
            a.ld(2)
            a.op('div', I_TMP + 8, 0)
            a.ldv(I_TMP + 8, 0)
            a.op('sub', I_DIST, 0)
            a.ld(0)
            a.br('!=', I_COPY, 0, f'cast{i}_flying')
            a.push(launch_sound)
            a.sub('playSound')
            a.label(f'cast{i}_flying')
            if o is lead:
                p = o.lead
                a.ld(0)
                a.br('!=', I_STATE, 0, f'cast{i}_done')
                a.ld(p.t0 + len(p.poses) - 1)
                a.br('>=', I_FRAME, 0, f'cast{i}_hit')
                copy(I_IDX, I_FRAME)
                a.ld(p.t0)
                a.op('sub', I_IDX, 0)
                a.ld(0)
                a.br('<', I_IDX, 0, f'cast{i}_done')
                a.ldx(p.tab[0], I_IDX, 0, p.tab[1], 'i32')
                a.op('set', I_P, 0)
                a.ld(0)
                a.br('<', I_P, 0, f'cast{i}_done')
                set_var(I_TMP + 8, 0)
                load_field(8, I_P)
                a.op('sub', I_TMP + 8, 0)
                a.ldv(I_KN, 0)
                a.op('mul', I_TMP + 8, 0)
                a.ldv(I_KD, 0)
                a.op('div', I_TMP + 8, 0)
                a.ldv(I_DIST, 0)
                a.br('<', I_TMP + 8, 0, f'cast{i}_done')
                a.label(f'cast{i}_hit')
                set_var(I_STATE, 1)
                set_var(I_ROT, 0)
                copy(I_ROT + 4, I_YAW + 4)
                set_var(I_ROT + 8, 0)
                a.call('group')
                a.label(f'cast{i}_done')
            a.ret()
        a.label(f'cast{i}_kill')
        set_var(I_FRAME, -1)
        a.ret()

    # --- the hit at one target: damage events and the hit objects
    a.label('group')
    if not self_target:
        a.call('dmg')
    for i in range(len(hit_objs)):
        a.call(f'hit{i}')
    a.ret()

    def at_target(slot, scale_):
        """origin = the target's position (the caster's for a support technique), at the slot's height."""
        if self_target:
            a.push(0)
            a.sub('setTransformToSourceBone')
            for k in range(3):
                copy(I_ORIGIN + 4 * k, I_POS + 4 * k)
            set_var(I_ORIGIN + 4, 0)
            a.pusha(I_TMP, 0)
            a.sub('getSourceDigimonSize')
        else:
            a.pusha(I_ORIGIN, 0)
            a.sub('copyTargetEntityPosition')
            a.pusha(I_TMP, 0)
            a.sub('getTargetDigimonSize')
        if slot == 0:
            a.ldv(I_TMP + 4, 0)
            a.op('sub', I_ORIGIN + 4, 0)
            a.ld(round(OVERHEAD * scale_))
            a.op('sub', I_ORIGIN + 4, 0)
        elif slot == 1:
            a.ld(2)
            a.op('div', I_TMP + 4, 0)
            a.ldv(I_TMP + 4, 0)
            a.op('sub', I_ORIGIN + 4, 0)

    if not self_target:
        a.label('dmg')
        a._w(17, dmg_n, dmg_pool, -9555, INST, 0)
        a.pusha_label('dmg_update')
        a.pusha_label('nothing')
        a.sub('initializeSubEffectInstructions')
        a.sub('initializeEFETransform')
        at_target(1, scale)
        for k in range(3):
            copy(I_POS + 4 * k, I_ORIGIN + 4 * k)
        a.ret()
        a.label('dmg_update')
        for n, t in enumerate(events):
            a.ld(t)
            a.br('!=', I_FRAME, 0, f'dmg_e{n}')
            a.sub('addAttackObjectToTarget')
            a.label(f'dmg_e{n}')
        a.ld(events[-1])
        a.br('<', I_FRAME, 0, 'dmg_live')
        set_var(I_FRAME, -1)
        a.label('dmg_live')
        a.ret()

    for i, o in enumerate(hit_objs):
        a.label(f'hit{i}')
        a._w(17, o.pool_n, o.pool, -9555, INST, 0)
        a.pusha_label(f'hit{i}_update')
        a.pusha_label(f'hit{i}_render')
        a.sub('initializeSubEffectInstructions')
        a.sub('initializeEFETransform')
        set_var(I_STATE, 0)
        set_var(I_KN, 1)
        set_var(I_KD, 1)
        set_var(I_COPY, 0)
        # turned toward the caster: the parent's position is the caster's side
        for k in range(3):
            copy(I_ORIGIN + 4 * k, I_POS + 4 * k)
        set_var(I_YAW, 0)
        set_var(I_YAW + 8, 0)
        if self_target:
            copy(I_YAW + 4, I_ROT + 4)
            a.ld(0x800)
            a.op('add', I_YAW + 4, 0)
        else:
            a.pusha(I_VEC, 0)
            a.sub('copyTargetEntityPosition')
            for k in range(3):
                copy(I_TMP + 4 * k, I_ORIGIN + 4 * k)
            a.pusha(I_TMP, 0)
            a.pusha(I_VEC, 0)
            a.sub('subtractVectors')
            set_var(I_TMP + 4, 0)
            a.pusha(I_SCALE, 0)
            a.pusha(I_TMP, 0)
            a.sub('vectorEulerAngles')
            copy(I_YAW + 4, I_SCALE + 4)
            a.ld(0x800)
            a.op('add', I_YAW + 4, 0)
        at_target(o.slot, hit_scale)
        a.ret()
        a.label(f'hit{i}_update')
        a.ld(o.ticks)
        a.br('<', I_FRAME, 0, f'hit{i}_live')
        set_var(I_FRAME, -1)
        a.label(f'hit{i}_live')
        a.ret()

    # --- render: every part through one draw routine
    def render(o, label):
        a.label(label)
        a.ld(0)
        a.br('<', I_FRAME, 0, f'{label}_end')
        a.ld(o.ticks)
        a.br('>=', I_FRAME, 0, f'{label}_end')
        if o.traveller:
            a.ld(0)
            a.br('==', I_COPY, 0, f'{label}_shown')
            a.ld(o.launch)
            a.br('<', I_FRAME, 0, f'{label}_end')
            a.label(f'{label}_shown')
        for n, p in enumerate(o.parts):
            skip = f'{label}_p{n}'
            if o.traveller and p.moves:
                a.ld(0)
                a.br('!=', I_STATE, 0, skip)
            copy(I_IDX, I_FRAME)
            a.ld(p.t0)
            a.op('sub', I_IDX, 0)
            a.ld(0)
            a.br('<', I_IDX, 0, skip)
            a.ld(len(p.poses))
            a.br('>=', I_IDX, 0, skip)
            a.ldx(p.tab[0], I_IDX, 0, p.tab[1], 'i32')
            a.op('set', I_P, 0)
            if -1 in p.poses:
                a.ld(0)
                a.br('<', I_P, 0, skip)
            for oid in p.ids:
                set_var(I_O, oid)
                a.call('draw')
            a.label(skip)
        a.label(f'{label}_end')
        a.ret()

    for i, o in enumerate(cast_objs):
        render(o, f'cast{i}_render')
    for i, o in enumerate(hit_objs):
        render(o, f'hit{i}_render')

    a.label('draw')
    for k in range(3):
        load_field(k, I_P)
        a.op('set', I_ROT + 4 * k, 0)
    a.ldv(I_YAW + 4, 0)
    a.op('add', I_ROT + 4, 0)
    for k in range(3):
        load_field(3 + k, I_P)
        a.op('set', I_SCALE + 4 * k, 0)
    for k in range(3):
        load_field(6 + k, I_P)
        a.op('set', I_VEC + 4 * k, 0)
    a.ldv(I_KN, 0)
    a.op('mul', I_VEC + 8, 0)
    a.ldv(I_KD, 0)
    a.op('div', I_VEC + 8, 0)
    a.pusha(I_YAW, 0)
    a.pusha(I_VEC, 0)
    a.sub('rotateVector')
    for k in range(3):
        a.ldv(I_ORIGIN + 4 * k, 0)
        a.op('set', I_POS + 4 * k, 0)
        a.ldv(I_VEC + 4 * k, 0)
        a.op('add', I_POS + 4 * k, 0)
    a.pushv(I_O, 0)
    a.pusha(I_SCALE, 0)
    a.sub('drawTMDYXZ')
    a.ret()

    code = a.bytes()
    put(code)
    n_sub = n_inst + 2                       # + the init script's root, + one spare
    subs = put(bytes(0x1c * n_sub))
    tmd_bytes = tmd(objects)
    put(tmd_bytes)
    t_at = subs + 0x1c * n_sub
    tmd_end = len(c.data)
    used_w = max(b.at[0] + b.size()[0] for b in blocks.values())
    used_h = max(b.at[1] + b.size()[1] for b in blocks.values())
    tim = strip_tim(blocks.values(), rows, (used_w + 3) & ~3, used_h)
    tim_at = put(tim)
    data_end = len(c.data)
    hdr = struct.pack('<13i', a.labels['start'], a.labels['init'], uv, uv + 0x20 * len(objects), subs, t_at, tmd_end,
                      tim_at, data_end, data_end, 3, n_sub, effect_id)
    chunk = hdr + bytes(c.data)
    sizes.update(code=len(code), tmd=len(tmd_bytes), tim=len(tim))
    if len(chunk) > CHUNK:
        raise Unconvertible(f'effect chunk is {len(chunk):#x} bytes; the slot has {CHUNK:#x} '
                            f'({", ".join(f"{k} {v}" for k, v in sizes.items())})')
    factors = sorted({(b.factor, b.turned) for b in blocks.values()})
    info = dict(sizes=sizes, flipbooks=len(uv_tab), resident=HEADER + tmd_end, chunk=len(chunk), objects=len(objects),
                prims=sum(len(o.prims) for o in objects), poses=len(poses), code=len(code),
                palettes=f'{len(pal_list)}->{len(rows)}', texture=f'{used_w}x{used_h}',
                factors=','.join(f'{f}{"T" if t else ""}' for f, t in factors),
                behaviour=behaviour(cast_objs, area, self_target), launch=lead.launch if lead else None,
                hit_tick=hit_tick, hit_events=events, cast_ticks=cast_end, hit_ticks=hit_len,
                travel=lead.travel if lead else 0, instances=n_inst,
                parts={o.name: {part.bone: list(part.ids) for part in o.parts} for o in objs})
    return chunk + bytes([0xcd]) * (CHUNK - len(chunk)), info


def behaviour(cast_objs, area, self_target):
    if self_target:
        return 'buff'
    tr = [o for o in cast_objs if o.traveller]
    if tr:
        lead = max(tr, key=lambda o: o.travel)
        movers = sum(p.moves for p in lead.parts)
        kind = 'projectile' if movers <= 2 else 'volley'
        return kind + (' x target' if area else '')
    return 'area' if area else 'melee'


def strip_tim(blocks, rows, width, height):
    img = [[0] * width for _ in range(height)]
    for b in blocks:
        w, h = b.size()
        cols = rows[b.pal]
        for y in range(h):
            for x in range(w):
                img[b.at[1] + y][b.at[0] + x] = b.texel(x, y, cols)
    clut = b''.join(struct.pack('<16H', *p) for p in rows)
    pix = bytearray()
    for row in img:
        for x in range(0, width, 4):
            pix += struct.pack('<H', row[x] | row[x + 1] << 4 | row[x + 2] << 8 | row[x + 3] << 12)
    return (struct.pack('<II', 0x10, 0x8) + struct.pack('<I4H', 12 + len(clut), 0, 0, 16, len(rows)) + clut
            + struct.pack('<I4H', 12 + len(pix), 0, 0, width // 4, height) + pix)


def convert(cast, hit, origin_table, effect_id, scale, reach=None, half=True, launch_sound=14, start_sound=2,
            hit_scale=None, area=False, hits=1):
    """One cast object at the launch point and one hit object at mid height (content/battle/own-effects.json's
    first form). reach is no longer used: a traveller flies to its target."""
    return convert_skill([(1, cast)], [(1, hit)], origin_table, effect_id, scale, hit_scale=hit_scale, area=area,
                         n_hits=hits, half=half, launch_sound=launch_sound, start_sound=start_sound)
