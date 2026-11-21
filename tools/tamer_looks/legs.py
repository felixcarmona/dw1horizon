"""The tamer's trousers: his thighs and shins as tubes of cloth (or of skin under shorts and skirts), any colour.

The four leg objects leave every model (shirts.strip) and a pair of trousers brings them, read behind the model like a
shirt. Trousers 0 are the original ones. The others draw their cloth on the legs' own part of the texture and colour it
through the legs' palette row; the seat, which is part of the torso and so of every shirt (its first SEAT polygons),
is then drawn with one plain texel of that cloth (SEAT_AT): the game rewrites those polygons when it loads.

The shins of slim trousers (SLIM: a narrow or bare shin) start with SHAFT_CORNERS corners and normals that are a
boot's (shoes.py) and have room for the boot's polygons right before their own: the game copies them in when the shoes
have a leg. Wide trousers fall over a boot and keep no room: only its foot shows under them.
"""
import math

import mmd
from . import shirts
from .shirts import MAIN, SECOND, SKIN_QUAD, SKIN_ROW, SKIN_TRI, W, c15, rgb15

THIGH, SHIN = (8, 11), (9, 12)
OBJECTS = (8, 9, 11, 12)                   # left thigh, left shin, right thigh, right shin
ROW = 5                                    # the legs' palette row
SEAT_AT = (100, 100)                       # a texel of plain cloth: the whole seat is drawn with it
SEAT_IN_HEAD = 0x3C                        # where the first sector says it (u, v), after the object table
SLIM = 1                                   # a flag in the first sector: the shins keep room for a boot's leg
SHAFT_CORNERS = 11                         # a boot's leg: two rings of five and the middle of its top
SHAFT_BYTES = 5 * 36 + 5 * 28              # its five quads and five triangles
RECTS = ((56, 88, 16, 24), (88, 88, 80, 24))  # what trousers draw: u, v, width, height (the hands lie between)
CLOTH = (90, 89, 114, 110)                 # plain cloth with folds
STRIPE = (118, 89, 130, 110)               # cloth with a stripe of the second colour down its middle
CUFF = (58, 89, 69, 110)                  # the second colour
POCKET = (134, 89, 158, 110)              # cloth with a pocket
TONES = ((3, 58), (4, 77), (5, 105), (6, 128), (7, 143))   # the cloth's tones and how bright each is (128 = the colour)
DARK2, LIGHT2 = 11, 12                     # the second colour and its shade
LENGTH = 132                               # a whole leg: the cloth's texture runs from the hip to the ankle


def patch(p, a=0.0, b=1.0):
    u0, v0, u1, v1 = p
    va, vb = int(round(v0 + (v1 - v0) * a)), int(round(v0 + (v1 - v0) * b))
    return [(u0, va), (u1, va), (u0, vb), (u1, vb)]


def leg(mesh, rings, ns, phase, outer, x0):
    """A tube along the bone. rings: (x, ry, rz, kind of the band that ends there): c cloth, s skin, h a hem seen
    from below, t cloth with the stripe on the outer side, p cloth with the pocket on the outer side."""
    ids = [[mesh.add((x, ry * math.cos(2 * math.pi * j / ns + phase), 1 + rz * math.sin(2 * math.pi * j / ns + phase)))
            for j in range(ns)] for x, ry, rz, _ in rings]

    def radial(c):
        return (0, c[1], c[2] - 1)
    for i in range(len(rings) - 1):
        kind = rings[i + 1][3]
        a = max(0, min(1, (x0 + rings[i][0]) / LENGTH))
        b = max(0, min(1, (x0 + rings[i + 1][0]) / LENGTH))
        for j in range(ns):
            vs = (ids[i][j], ids[i][(j + 1) % ns], ids[i + 1][j], ids[i + 1][(j + 1) % ns])
            if kind == 's':
                mesh.face(vs, SKIN_QUAD, SKIN_ROW, radial)
            elif kind == 'h':
                mesh.face(vs, patch(CUFF, .4, .6), ROW, (1, 0, 0))
            elif kind == 't' and j == outer:
                mesh.face(vs, patch(STRIPE, a, b), ROW, radial)
            elif kind == 'p' and j == outer:
                mesh.face(vs, patch(POCKET), ROW, radial)
            else:
                mesh.face(vs, patch(CLOTH, a, b), ROW, radial)
    skin = rings[-1][3] == 's'
    end = mesh.add((rings[-1][0], 0, 1))
    for j in range(ns):
        mesh.face((ids[-1][j], ids[-1][(j + 1) % ns], end), SKIN_TRI if skin else patch(CLOTH, .1, .3)[:3],
                  SKIN_ROW if skin else ROW, (1, 0, 0))


T0 = ((0, 23, 20), (26, 24, 21), (52, 24, 21))     # the tamer's own thigh and shin: x along the bone, half sizes
S0 = ((0, 24, 21), (33, 28, 24), (66, 33, 27))


def rings(base, scale, kinds, flare=0.0, end=None):
    n = len(base) - 1
    out = [(x, ry * (scale + flare * i / n), rz * (scale + flare * i / n), k)
           for i, ((x, ry, rz), k) in enumerate(zip(base, kinds))]
    if end is not None:
        out[-1] = (end,) + out[-1][1:]
    return out


BARE_THIGH = (54, 15, 14, 's')
BARE_SHIN = ((-2, 15, 14, 's'), (30, 14, 13, 's'), (64, 11, 10, 's'))
# name, thigh, shin (None: a bare one), a drawing, slim (a boot's leg goes over the shin: room is kept for it);
# a thigh with a stripe or a pocket is not the same on both legs
STYLES = (
    ('straight', rings(T0, .95, 'ccc'), rings(S0, .88, 'ccc', -.06, 61), 'plain', False),
    ('baggy', rings(T0, 1.08, 'cpc', .08), rings(S0, 1.12, 'ccc', .1, 61), 'plain', False),
    ('skinny', rings(T0, .82, 'ccc', -.08), rings(S0, .66, 'ccc', -.2, 63), 'plain', True),
    ('tracksuit', rings(T0, 1.0, 'ctt'), rings(S0, .95, 'ttt', -.12, 63), 'cuffed', False),
    ('shorts', [(0, 24, 21, 'c'), (40, 28, 25, 'c'), (41, 16, 15, 'h'), BARE_THIGH], None, 'plain', True),
    ('capri', rings(T0, .95, 'ccc'), [(0, 23, 20, 'c'), (30, 24, 21, 'c'), (31, 13, 12, 'h'), (64, 11, 10, 's')], 'plain', True),
    ('skirt', [(-4, 24, 22, 'c'), (34, 41, 40, 'c'), (35, 17, 16, 'h'), BARE_THIGH], None, 'plain', True),
    ('flared', rings(T0, .9, 'ccc', -.06), rings(S0, .78, 'ccc', .5, 60), 'plain', False),
)
NAMES = ('original',) + tuple(s[0] for s in STYLES)


def original(model):
    """Trousers 0: the tamer's own legs."""
    return {oi: shirts.part(model, oi) for oi in OBJECTS}


def garment(model, thigh, shin, slim):
    quad, tri, sign = shirts.patterns(model)
    sided = any(r[3] in 'tp' for r in thigh + (shin or []))
    room = SHAFT_CORNERS if slim else 0
    parts = {}
    for n in range(2):
        # five sides: turned so that one faces outwards, where a stripe or a pocket goes
        phase = math.radians(18 if n == 0 else -18) if sided else 0
        outer = 3 if n == 0 else 1
        me = shirts.Mesh(quad, tri, sign)
        leg(me, thigh, 5, phase, outer, 0)
        parts[THIGH[n]] = me.close()
        me = shirts.Mesh(quad, tri, sign, base=room)
        if shin:
            leg(me, shin, 5, phase, outer, 66)
        else:
            leg(me, list(BARE_SHIN), 4, math.pi / 4, None, 66)
        verts, norms, prims = me.close()
        parts[SHIN[n]] = ([(0, 0, 0, 0)] * room + verts, [(0, 0, 0, 0)] * room + norms, prims)
    return parts


def geometry(parts, slim=False):
    return shirts.geometry(parts, OBJECTS, {oi: SHAFT_BYTES for oi in SHIN} if slim else None)


def paint(idx, drawing):
    def box(p, f):
        u0, v0, u1, v1 = p
        for y in range(v0 - 1, v1 + 2):
            for x in range(u0 - 2, u1 + 3):
                idx[y * W + x] = f(x - u0, y - v0, u1 - u0, v1 - v0)

    def cloth(x, y, w, h):
        if drawing == 'cuffed' and y >= h - 2:
            return LIGHT2 if y % 2 else DARK2
        if (x * 5 - y * 3) % 31 == 0:
            return 7
        if (x * 3 + y * 2) % 23 in (0, 1) and y % 7 < 4:
            return 5
        return 6

    def stripe(x, y, w, h):
        c = cloth(x, y, w, h)
        return LIGHT2 if abs(x - w / 2) < 2.2 and c in (5, 6, 7) else c

    def pocket(x, y, w, h):
        if (5 < x < w - 5 and y in (6, 16)) or (6 <= y <= 16 and x in (6, w - 6)):
            return 4
        return 5 if 5 < x < w - 5 and 6 < y < 10 else cloth(x, y, w, h)
    box(CLOTH, cloth)
    box(STRIPE, stripe)
    box(CUFF, lambda x, y, w, h: LIGHT2 if y % 4 else DARK2)
    box(POCKET, pocket)


def recipe():
    ways, levels, whites, fixed = [shirts.KEEP] * 16, [0] * 16, [0] * 16, [0] * 16
    for i, level in TONES:
        ways[i], levels[i] = MAIN, level
    ways[DARK2], levels[DARK2] = SECOND, 102
    ways[LIGHT2], levels[LIGHT2] = SECOND, 128
    return ways, levels, whites, fixed


def palette(texture, colour, second):
    """The texture's palette rows for trousers of a colour, as the game writes them (for pictures)."""
    rows = [list(p) for p in texture.pal]
    rows[ROW] = shirts.palette(recipe(), colour, second, rows[ROW])
    return rows


def seat(parts):
    """A shirt's parts with the seat as the game rewrites it under trousers (for pictures)."""
    verts, norms, prims = parts[shirts.TORSO]
    out = []
    for i, p in enumerate(prims):
        if i < len(shirts.PELVIS):
            d = p.decode()
            shirts.set_row(d, ROW)
            d['uv'] = [SEAT_AT] * len(d['uv'])
            p = mmd.Prim.encode(d)
        out.append(p)
    return {**parts, shirts.TORSO: (verts, norms, out)}


def check_free(model):
    """The legs' drawing and palette row must be the legs' alone."""
    tm = model.tmd
    for oi, ob in enumerate(tm.objects):
        for pi, p in enumerate(ob.prims):
            d = p.decode()
            if 'uv' not in d:
                continue
            row = shirts.prim_row(d)
            if oi in OBJECTS:
                continue
            us, vs = [q[0] for q in d['uv']], [q[1] for q in d['uv']]
            if any(min(us) < u + w and max(us) >= u and min(vs) < v + h and max(vs) >= v for u, v, w, h in RECTS):
                raise SystemExit(f'trousers: object {oi} polygon {pi} uses the texture the trousers draw on')
            if row == ROW:
                raise SystemExit(f'trousers: object {oi} polygon {pi} is drawn in the legs palette row')


def build(model, texture):
    """Every pair of trousers: [(name, first sector, geometry, parts, pixels or None, slim)]."""
    check_free(model)
    parts = original(model)
    body, table = geometry(parts)
    out = [('original', shirts.head(table, len(body)), body, parts, None, False)]
    for name, thigh, shin, drawing, slim in STYLES:
        parts = garment(model, list(thigh), list(shin) if shin else None, slim)
        body, table = geometry(parts, slim)
        idx = bytearray(texture.idx)
        paint(idx, drawing)
        if idx[SEAT_AT[1] * W + SEAT_AT[0]] != 6:
            raise SystemExit('trousers: the seat texel is not plain cloth')
        first = bytearray(shirts.head(table, len(body), recipe(), shirts.pixels(idx, RECTS), RECTS, SLIM if slim else 0))
        first[SEAT_IN_HEAD:SEAT_IN_HEAD + 2] = bytes(SEAT_AT)
        first = bytes(first)
        out.append((name, first, body, parts, idx, slim))
    return out
