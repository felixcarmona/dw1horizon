"""The tamer's backpacks: a piece of the torso that any shirt can carry, or none.

The backpack is not an object of its own (the skeleton has none to spare): its polygons belong to the torso. Every
shirt keeps room for one (shirts.PACK_CORNERS leading corners and normals, shirts.PACK_BYTES before the torso's
polygons) and the game copies the chosen backpack there from the backpack's sector when it loads. A backpack is that
sector alone: the palette recipe and the drawing as in any garment (shirts.head), and its geometry at PACK_AT.

Backpack 0 is the tamer's own, with its own colours; backpack 1 is none. With the original hoodie the original
backpack is not copied anywhere: shirt 0 is the disc's torso as it is, so the two together are the original tamer.
With any other shirt the same polygons are used a little narrower, their open side sunk into the body. The others
draw on the original backpack's part of the texture and take any of the cloth colours through its palette row.
"""
import math
import struct

import mmd
from . import shirts
from .shirts import FIXED, MAIN, SECOND, W, c15, rgb15

ROW = 3                                    # the backpack's palette row
POLYGONS = (2, 3, 13, 14, 28, 29, 38, 41, 45, 48, 52)   # the torso's polygons that are the backpack
RECTS = ((0, 56, 32, 32),)                 # what a backpack draws: the original's back and top
TOP, LID = 38, (16, 38)                    # a triangle of its top (its first corner: the top's middle); the shoulders' corners
PACK_AT = 0x400                            # in the sector: u16 polygons, u16 their bytes, u16 corners, u16 0, then data
NONE = 1
PANEL = (1, 57, 20, 86)                    # a drawn backpack's back
SIDE = (23, 57, 30, 86)                    # its plain cloth, for the sides, the top and the bottom
ROLL = (23, 76, 30, 86)                    # the lower end of the plain cloth: a bedroll's, in the second colour
RIM = 10                                   # how deep in the body a backpack's open side lies (the back is near 24)
TONES = ((1, 1.3), (11, 1.14), (2, 1), (3, .86), (4, .72), (10, .58), (5, .44))   # cloth tones: how bright next to the colour
OUTLINE = 5
TRIM, TRIM_DARK, METAL, DARK = 6, 7, 8, 9  # the second colour and its shade, a buckle, a strap

# name, shape, drawing. The number is saved: add at the end.
STYLES = (
    ('classic', 'original', None),         # the original's shape and drawing, in any colour
    ('school', ('box', 35, -30, 50, 56), 'school'),
    ('mini', ('box', 26, -8, 44, 46), 'mini'),
    ('hiking', ('tall', 36, -34, 50, 58), 'hiking'),
    ('round', ('round', 35, 10, 54), 'round'),
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


def uv(p, a0=0.0, a1=1.0):
    u0, v0, u1, v1 = p
    va, vb = int(round(v0 + (v1 - v0) * a0)), int(round(v0 + (v1 - v0) * a1))
    return [(u0, va), (u1, va), (u0, vb), (u1, vb)]


def shape(model, kind, *size):
    quad, tri, sign = shirts.patterns(model)
    me = shirts.Mesh(quad, tri, sign)

    def both(x, y, z):
        return me.add((x, y, -z)), me.add((x, y, z))
    if kind in ('box', 'tall'):
        w, x0, x1, deep = size
        centre = ((x0 + x1) / 2, (RIM + deep) / 2)

        def out(c):
            return (c[0] - centre[0], c[1] - centre[1], c[2] * 1.5)
        a, b = both(x0, RIM, w - 2), both(x1, RIM, w - 2)
        c = both(x0 - 2, deep, w)
        if kind == 'box':                              # the top falls away towards the back
            d, e = both(x1 - 14, deep, w), both(x1, deep - 16, w - 2)
            me.face((a[0], a[1], c[0], c[1]), uv(SIDE, 0, .3), ROW, out)
            me.face((d[0], d[1], c[0], c[1]), uv(PANEL, .22, 1), ROW, out)
            me.face((e[0], e[1], d[0], d[1]), uv(PANEL, 0, .22), ROW, out)
            me.face((b[0], b[1], e[0], e[1]), uv(SIDE, 0, .3), ROW, out)
            for s in range(2):
                me.face((b[s], e[s], a[s], c[s]), uv(SIDE), ROW, out)
                me.face((e[s], d[s], c[s]), uv(SIDE, .1, .8)[:3], ROW, out)
        else:                                          # a tall box with a bedroll across its top
            d = both(x1, deep - 3, w)
            me.face((a[0], a[1], c[0], c[1]), uv(SIDE, 0, .3), ROW, out)
            me.face((d[0], d[1], c[0], c[1]), uv(PANEL), ROW, out)
            me.face((b[0], b[1], d[0], d[1]), uv(SIDE, 0, .3), ROW, out)
            for s in range(2):
                me.face((b[s], d[s], a[s], c[s]), uv(SIDE, 0, .6), ROW, out)
            rx, ry, r = x1 + 9, (RIM + deep) / 2 + 8, 11
            ring = [both(rx + r * math.cos(k * math.pi / 2), ry + r * math.sin(k * math.pi / 2), w + 3) for k in range(4)]

            def away(c):
                return (c[0] - rx, c[1] - ry, 0)
            for k in range(4):
                p, q = ring[k], ring[(k + 1) % 4]
                me.face((p[0], p[1], q[0], q[1]), uv(ROLL), ROW, away)
            for s in range(2):
                me.face((ring[0][s], ring[1][s], ring[3][s], ring[2][s]), uv(ROLL, .2, .8), ROW, (0, 0, s * 2 - 1))
    else:                                              # a soft round one: six sides and a domed back
        r, x, deep = size
        rings = [[me.add((x + q * math.cos(k * math.pi / 3 + math.pi / 6), y, q * .95 * math.sin(k * math.pi / 3 + math.pi / 6)))
                  for k in range(6)] for q, y in ((r - 4, RIM), (r, deep - 12))]
        cap = me.add((x, deep, 0))

        def out(c):
            return (c[0] - x, (c[1] - RIM) * .6, c[2])
        pu0, pv0, pu1, pv1 = PANEL
        mu, mv, ru, rv = (pu0 + pu1) / 2, (pv0 + pv1) / 2, (pu1 - pu0) / 2, (pv1 - pv0) / 2

        def on_panel(k):                               # the back's drawing is seen from behind: up is the top of it
            a = k * math.pi / 3 + math.pi / 6
            return (int(round(mu + ru * math.sin(a))), int(round(mv - rv * math.cos(a))))
        for k in range(6):
            j = (k + 1) % 6
            me.face((rings[0][k], rings[0][j], rings[1][k], rings[1][j]), uv(SIDE, .2, .7), ROW, out)
            me.face((rings[1][k], rings[1][j], cap), [on_panel(k), on_panel(j), (int(mu), int(mv))], ROW, (0, 1, 0))
    return me.close()


def shade(light):
    """The cloth tone nearest to a brightness (1 is the colour itself)."""
    return min(TONES, key=lambda t: abs(t[1] - light))[0]


def paint(idx, drawing):
    """Draw a backpack's back and its plain cloth: every part is lit from above and rounds off towards its edges."""
    def box(p, f):
        u0, v0, u1, v1 = p
        for y in range(v0 - 1, v1 + 2):
            for x in range(u0 - 1, u1 + 2):
                idx[y * W + x] = f(x - u0, y - v0, u1 - u0, v1 - v0)

    def form(x, y, w, h, top=0.0, bottom=1.0):
        """How bright the cloth is at a place of a bulging part that runs from top to bottom of the height."""
        a = min(max((y / h - top) / (bottom - top), 0), 1)
        light = 1.2 - .5 * a ** 1.3 - .3 * abs(2 * x / w - 1) ** 3
        if a < .12:
            light -= .12                               # the upper edge turns away
        return light

    def edged(x, y, w, h, tone):
        return OUTLINE if x <= 0 or x >= w or y <= 0 or y >= h else tone

    def school(x, y, w, h):
        flap = h * .4 - (abs(x - w / 2) / (w / 2)) ** 2 * h * .1
        if y <= flap:
            if y > flap - 1.3:
                return TRIM
            return edged(x, y, w, h, shade(form(x, y, w, h, 0, .4) + .12))
        if abs(x - w / 2) < 1.6 and y < flap + 4:
            return METAL if y < flap + 3 else OUTLINE  # the buckle
        if y < flap + 2.2:
            return edged(x, y, w, h, shade(.55))       # the flap's shadow
        top = int(h * .6)
        if 3 <= x <= w - 3 and top <= y <= h - 2:      # the pocket
            if x in (3, w - 3) or y in (top, h - 2):
                return OUTLINE
            return shade(form(x - 3, y, w - 6, h, .6, 1) + (.12 if y == top + 1 else -.05))
        return edged(x, y, w, h, shade(form(x, y, w, h) - .08))

    def mini(x, y, w, h):
        zip_ = h * .3
        if abs(y - zip_) < .8:
            return TRIM if 1 < x < w - 1 else OUTLINE
        if zip_ < y < zip_ + 2.4:
            return edged(x, y, w, h, shade(.58))
        d = math.hypot(x - w / 2, (y - h * .66) * .8)
        if d < 4.8:                                    # a round patch
            return OUTLINE if d > 4 else TRIM_DARK if d < 1.3 or (d > 2.6 and y > h * .66) else TRIM
        if y < zip_:
            return edged(x, y, w, h, shade(form(x, y, w, h, 0, .3) + .1))
        return edged(x, y, w, h, shade(form(x, y, w, h, .3, 1)))

    def hiking(x, y, w, h):
        lid = h * .22 + (abs(x - w / 2) / (w / 2)) ** 2 * h * .04
        if y < lid:
            if y > lid - 1.4 or x <= 0 or x >= w or y <= 0:
                return OUTLINE
            return TRIM if y < lid * .55 and 1 < x < w - 1 else TRIM_DARK
        for strap in (.28, .72):
            if abs(x - w * strap) < 1.3:
                return METAL if abs(y - h * .48) < 1.6 else DARK
        if y < lid + 2.2:
            return edged(x, y, w, h, shade(.55))       # the lid's shadow
        top = int(h * .64)
        if top <= y <= h - 2 and 2 <= x <= w - 2:      # the lower pocket
            if y in (top, h - 2) or x in (2, w - 2):
                return OUTLINE
            return shade(form(x - 2, y, w - 4, h, .64, 1) + (.12 if y == top + 1 else -.04))
        return edged(x, y, w, h, shade(form(x, y, w, h) - .06))

    def round_(x, y, w, h):
        px, py = (x - w / 2) / (w / 2), (y - h / 2) / (h / 2)
        d = math.hypot(px, py)
        if abs(d - .58) < .075 and py < .25:
            return TRIM                                # the zip, an arch
        if .58 < d < .78 and py < .25 and py > -.2 + abs(px) * .1 and abs(d - .7) < .05:
            return shade(.58)
        if d < .3:
            return TRIM_DARK if d < .1 or (d > .19 and py > 0) else TRIM
        if d < .37:
            return OUTLINE
        return shade(1.28 - .62 * d * d - .22 * py)

    def side(x, y, w, h):
        if y % 10 == 9:
            return OUTLINE                             # a seam
        return shade(.92 - .2 * abs(2 * x / w - 1) ** 2 + (.14 if y % 10 == 0 else 0))
    box(SIDE, side)
    box(PANEL, {'school': school, 'mini': mini, 'hiking': hiking, 'round': round_}[drawing])
    if drawing == 'hiking':
        box(ROLL, lambda x, y, w, h: DARK if x in (1, w - 1) else OUTLINE if y in (0, h) else TRIM if y < h * .55 else TRIM_DARK)


def recipe(texture, drawing):
    ways, levels, fixed = [shirts.KEEP] * 16, [0] * 16, [0] * 16
    if drawing is None:                                # the original's tones, as bright as they were
        tones = [rgb15(c) for c in texture.pal[ROW]]
        ref = sum(tones[1])
        for i in tuple(range(6)) + (12, 13, 14):
            ways[i], levels[i] = shirts.tone(sum(tones[i]) / ref)
        return ways, levels, fixed
    for i, light in TONES:
        ways[i], levels[i] = shirts.tone(light)
    ways[TRIM], levels[TRIM] = SECOND, 128
    ways[TRIM_DARK], levels[TRIM_DARK] = SECOND, 90
    ways[METAL], fixed[METAL] = FIXED, c15(200, 200, 205)
    ways[DARK], fixed[DARK] = FIXED, c15(56, 56, 62)
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


def sector(pack, rec=None, drawn=None):
    out = bytearray(shirts.head([], 0, rec, drawn, RECTS))
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
    out = [('original', sector(own), own, None, None), ('none', sector(None), None, None, None)]
    for name, form, drawing in STYLES:
        rec = recipe(texture, drawing)
        if form == 'original':
            out.append((name, sector(own, rec), own, rec, None))
            continue
        pack = shape(model, *form)
        idx = bytearray(texture.idx)
        paint(idx, drawing)
        out.append((name, sector(pack, rec, shirts.pixels(idx, RECTS)), pack, rec, idx))
    return out
