"""The tamer's backpacks: a piece of the torso that any shirt can carry, or none.

The backpack is not an object of its own (the skeleton has none to spare): its polygons belong to the torso. Every
shirt keeps room for one (shirts.PACK_CORNERS leading corners and normals, shirts.PACK_BYTES before the torso's
polygons) and the game copies the chosen backpack there from the backpack's sector when it loads. A backpack is that
sector alone: the palette recipe and the drawing as in any garment (shirts.head), and its geometry at PACK_AT.

Backpack 0 is the tamer's own, with its own colours or dyed (shirts.OWN); backpack 1 is none. With the original hoodie the original
backpack is not copied anywhere: shirt 0 is the disc's torso as it is, so the two together are the original tamer.
With any other shirt the same polygons are used a little narrower, their open side sunk into the body. The others
are that backpack too, in other proportions: they keep its drawing (cloth, seams, shading), draw their own fittings
where it has its emblem, and take any of the cloth colours through its palette row.
"""
import math
import struct

import mmd
from . import shirts
from .shirts import W, rgb15

ROW = 3                                    # the backpack's palette row
POLYGONS = (2, 3, 13, 14, 28, 29, 38, 41, 45, 48, 52)   # the torso's polygons that are the backpack
RECTS = ((0, 56, 32, 32),)                 # what a backpack draws: the original's back and top
TOP, LID = 38, (16, 38)                    # a triangle of its top (its first corner: the top's middle); the shoulders' corners
PACK_AT = 0x400                            # in the sector: u16 polygons, u16 their bytes, u16 corners, u16 0, then data
NONE = 1
RIM = 10                                   # how deep in the body a backpack's open side lies (the back is near 24)
MIDDLE = 12                                # the middle of its height
CENTRE, INK = 15, 15                       # the middle of its drawing; the darkest tone, of outlines

# name, how tall, wide and deep next to the original, drawing. The number is saved: add at the end.
STYLES = (
    ('classic', 1, 1, 1, None),            # the original's drawing, in any colour
    ('school', 1, .94, 1.06, 'school'),
    ('mini', .7, .74, .8, 'mini'),
    ('hiking', 1.16, 1, 1.2, 'hiking'),
    ('round', .82, 1.04, 1.1, 'round'),
)
NAMES = ('original', 'none') + tuple(s[0] for s in STYLES)


def fitted(model):
    """The original backpack for a shirt that is not the hoodie: narrower, its open side inside the body."""
    verts, norms, prims = shirts.part(model, shirts.TORSO)
    verts = [(x, RIM, int(round(z * .68)), w) if y < 30 else (x, y - 3, int(round(z * .84)), w) for x, y, z, w in verts]
    # the hood lay over the top's last triangle: plain cloth of the top closes it
    lid = prims[TOP].decode()
    lid['verts'], lid['norms'] = [LID[0], LID[1], lid['verts'][0]], [lid['norms'][0]] * 3
    lid['uv'] = [(8, 65), (22, 65), (15, 62)]
    c = shirts.cross(*[verts[k][:3] for k in lid['verts']])
    if c[0] * shirts.patterns(model)[2] < 0:           # it faces up
        lid['verts'][:2], lid['uv'][:2] = lid['verts'][1::-1], lid['uv'][1::-1]
    return shirts.compact(verts, norms, [prims[i] for i in POLYGONS] + [mmd.Prim.encode(lid)])


def reshaped(pack, tall, wide, deep):
    """A backpack of other proportions: its corners moved about the middle of its open side."""
    verts, norms, prims = pack
    return [(int(round(MIDDLE + (x - MIDDLE) * tall)), y if y <= RIM else int(round(RIM + (y - RIM) * deep)),
             int(round(z * wide)), w) for x, y, z, w in verts], norms, prims


def paint(idx, drawing):
    """Another drawing on the original backpack's back: its cloth, seams and pockets stay as the disc has them, the
    emblem gives way to plain cloth, and the style's own fittings are drawn in the original's greys."""
    def put(dx, y, tone, both=True):
        idx[y * W + CENTRE + dx] = tone
        if both:
            idx[y * W + CENTRE - dx] = tone
    for y in range(60, 88):
        reach = 8 if y >= 82 else 11
        drawn = [dx for dx in range(-reach, reach + 1) if idx[y * W + CENTRE + dx] >= 6]
        for dx in range(min(drawn), max(drawn) + 1) if drawn else ():
            idx[y * W + CENTRE + dx] = 1 if y <= 62 else 2 if y <= 78 else 3
    if drawing == 'school':                            # a flap with a buckle, over a pocket
        for dx in range(12):
            y = 72 - int(round((dx / 11) ** 2 * 4))
            for k, tone in ((-2, 2), (-1, 1), (0, INK), (1, 4), (2, 3)):
                put(dx, y + k, tone)
        for y in range(70, 77):
            for dx in range(3):
                put(dx, y, INK if dx == 2 or y in (70, 76) else 6 if y == 71 else 9 if y == 75 else 7)
        for y in range(79, 87):
            for dx in range(9):
                put(dx, y, INK if dx == 8 or y == 79 else 2 if y == 80 else 4 if y == 86 else 3)
    elif drawing == 'hiking':                          # a lid, and two straps with their buckles down the back
        for dx in range(11):
            for k, tone in ((-1, 1), (0, INK), (1, 4)):
                put(dx, 66 + k, tone)
        for y in range(60, 88):
            for dx, tone in ((4, INK), (5, 8), (6, 10), (7, INK)):
                put(dx, y, tone)
            if 70 <= y <= 74:
                for dx in (5, 6):
                    put(dx, y, INK if y in (70, 74) else 6)
        for y in range(80, 87):
            for dx in range(4):
                put(dx, y, INK if y == 80 else 2 if y == 81 else 3)
    elif drawing == 'mini':                            # a zip with its pull, and a round badge
        for dx in range(11):
            for k, tone in ((-1, 1), (0, 7), (1, INK), (2, 3)):
                put(dx, 66 + k, tone)
        for y in range(67, 71):
            put(0, y, INK if y == 70 else 6)
        for y in range(72, 85):
            for dx in range(7):
                d = math.hypot(dx, y - 78)
                if d <= 5.6:
                    put(dx, y, INK if d > 4.6 else (7 if y < 78 else 9) if d > 2.9 else INK if d > 2.1 else 1)
    else:                                              # round: a wide ring around a stud
        for y in range(63, 87):
            for dx in range(12):
                d = math.hypot(dx, y - 74.5)
                if d <= 10.8:
                    lit = y < 74.5
                    put(dx, y, INK if d > 9.8 else (7 if lit else 9) if d > 8.8 else (6 if lit else 8) if d > 7.4 else
                        INK if d > 6.5 else INK if 2.4 < d <= 3.4 else (6 if lit else 9) if d <= 2.4 else 1 if lit and d > 4.6 else 2)


def recipe(texture):
    """Every tone of the backpack's cloth follows the colour, as bright as the original's was; its greys stay."""
    ways, levels, fixed = [shirts.KEEP] * 16, [0] * 16, [0] * 16
    tones = [rgb15(c) for c in texture.pal[ROW]]
    ref = sum(tones[1])
    for i in tuple(range(6)) + (12, 13, 14):
        ways[i], levels[i] = shirts.tone(sum(tones[i]) / ref)
    return ways, levels, fixed


def palette(texture, rec, cloth):
    """The texture's palette rows for a backpack of a cloth colour, as the game writes them (for pictures)."""
    rows = [list(p) for p in texture.pal]
    if rec:
        rows[ROW] = shirts.palette(rec, cloth, rows[ROW])
    return rows


def carried(parts, pack):
    """A shirt's parts with a backpack where the game copies it (for pictures)."""
    if not pack:
        return parts
    verts, norms, prims = parts[shirts.TORSO]
    pv, pn, pp = pack
    return {**parts, shirts.TORSO: (list(pv) + list(verts[len(pv):]), list(pn) + list(norms[len(pn):]), list(pp) + list(prims))}


def check_free(model):
    """The backpack's drawing and palette row must be the backpack's alone."""
    for oi, ob in enumerate(model.tmd.objects):
        for pi, p in enumerate(ob.prims):
            if oi == shirts.TORSO and pi in POLYGONS:
                continue
            d = p.decode()
            if 'uv' not in d:
                continue
            us, vs = [q[0] for q in d['uv']], [q[1] for q in d['uv']]
            if any(min(us) < u + w and max(us) >= u and min(vs) < v + h and max(vs) >= v for u, v, w, h in RECTS):
                raise SystemExit(f'backpacks: object {oi} polygon {pi} uses the texture a backpack draws on')
            if shirts.prim_row(d) == ROW:
                raise SystemExit(f'backpacks: object {oi} polygon {pi} is drawn in the backpack palette row')


def sector(pack, rec=None, drawn=None, flags=0):
    out = bytearray(shirts.head([], 0, rec, drawn, RECTS, flags))
    if pack:
        verts, norms, prims = pack
        raw = b''.join(p.raw for p in prims)
        if len(verts) > shirts.PACK_CORNERS or len(norms) > shirts.PACK_CORNERS or len(raw) > shirts.PACK_BYTES:
            raise SystemExit(f'backpacks: {len(verts)} corners, {len(norms)} normals, {len(raw)} bytes: more than shirts keep')
        n = max(len(verts), len(norms))
        verts = list(verts) + [(0, 0, 0, 0)] * (n - len(verts))
        norms = list(norms) + [(0, 0, 0, 0)] * (n - len(norms))
        blob = struct.pack('<4H', len(prims), len(raw), n, 0)
        blob += b''.join(struct.pack('<4h', *v) for v in verts) + b''.join(struct.pack('<4h', *v) for v in norms) + raw
        out[PACK_AT:PACK_AT + len(blob)] = blob
    return bytes(out)


def build(model, texture):
    """Every backpack: [(name, its sector, (corners, normals, polygons) or None, recipe or None, pixels or None)]."""
    check_free(model)
    own = fitted(model)
    rec = recipe(texture)
    out = [('original', sector(own, rec, flags=shirts.OWN), own, rec, None), ('none', sector(None), None, None, None)]
    for name, tall, wide, deep, drawing in STYLES:
        pack = reshaped(own, tall, wide, deep)
        if drawing is None:
            out.append((name, sector(pack, rec), pack, rec, None))
            continue
        idx = bytearray(texture.idx)
        paint(idx, drawing)
        out.append((name, sector(pack, rec, shirts.pixels(idx, RECTS)), pack, rec, idx))
    return out
