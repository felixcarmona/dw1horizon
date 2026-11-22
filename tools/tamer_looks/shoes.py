"""The tamer's shoes: his own feet, redrawn and recoloured, smaller for some kinds, with a leg added for boots.

A pair of shoes is the two foot objects (the tamer's own mesh, scaled for the small kinds), a drawing over the feet's
part of the texture and a recipe for the feet's palette row, so that every pair takes any of the cloth colours. A
boot's leg cannot be part of the foot, which turns at the ankle: it rides on the shin. Trousers with a slim or bare
shin keep room for it (legs.py), and the game copies it there from the shoes' first sector when it loads.
"""
import struct

from . import legs, shirts
from .shirts import FIXED, MAIN, SECOND, W, c15, rgb15

OBJECTS = (10, 13)                         # the left foot and the right foot
ROW = 7                                    # the feet's palette row
# what shoes draw: the top of the foot, its sides with the heel, the sole and the toe
RECTS = ((40, 88, 16, 40), (192, 41, 48, 23), (216, 112, 40, 16), (160, 112, 8, 16))
SEAT = (192, 56, 24, 8)                    # a corner of the sides' rectangle that is the seat's: drawn as it was
SIDES = ((214, 41, 239, 55), (192, 41, 215, 55))
TOP = (40, 88, 55, 127)
HEEL = (216, 56, 239, 63)
TOE = (160, 112, 167, 127)
SOLE = (216, 112, 255, 127)
SHAFT = (42, 90, 54, 105)                  # the cloth of a boot's leg, on the top of the foot's texture
SHAFT_AT = 0x600                           # where a boot's leg lies in the first sector
FWD, UP = (0.894, 0.447), (-0.447, 0.894)  # the foot's own frame: towards the toe, and away from the sole
SOLE_UP = -42                              # where the sole is along UP
PLAIN = 9                                  # the tone of plain shoe cloth
TRIM = 7                                   # tones below this are the laces and the trim, from it on the shoe itself

# name, a boot's leg (height, girth at the ankle, girth at its top, cuff), the drawing, the size (length, height)
STYLES = (
    ('trainers', None, 'own', None),
    ('small trainers', None, 'own', (.78, .85)),
    ('plain', None, 'flat', None),
    ('flats', None, 'bare', (.74, .62)),
    ('mary janes', None, 'strap', (.76, .7)),
    ('ankle boots', (20, 21, 20, 0), 'seams', None),
    ('small ankle boots', (22, 17, 17, 0), 'flat', (.8, .9)),
    ('boots', (44, 21, 21, 0), 'flat', None),
    ('cuffed boots', (45, 21, 25, 1), 'cuff', None),
    ('rain boots', (52, 22, 25, 0), 'flat', None),
    ('sandals', None, 'sandals', (.9, .8)),
)
NAMES = ('original',) + tuple(s[0] for s in STYLES)


def sized(part, size):
    """A smaller foot: shorter and narrower along the sole, lower above it, the sole kept on the ground."""
    verts, norms, prims = part
    if not size:
        return part
    s, h = size
    out = []
    for v in verts:
        f = 6 + (v[0] * FWD[0] + v[1] * FWD[1] - 6) * s
        u = SOLE_UP + (v[0] * UP[0] + v[1] * UP[1] - SOLE_UP) * h
        out.append((int(round(FWD[0] * f + UP[0] * u)), int(round(FWD[1] * f + UP[1] * u)), int(round(v[2] * s))) + tuple(v[3:]))
    return out, norms, prims


def shaft(model, height, r0, r1, cuff):
    """A boot's leg on the shin, whose x runs down to the ankle at 66: two rings of five and a lid."""
    import math
    quad, tri, sign = shirts.patterns(model)
    me = shirts.Mesh(quad, tri, sign)
    ids = [[me.add((x, r * math.cos(2 * math.pi * j / 5 + math.pi / 5), 1 + r * .92 * math.sin(2 * math.pi * j / 5 + math.pi / 5)))
            for j in range(5)] for x, r in ((70, r0), (66 - height, r1))]
    u0, v0, u1, v1 = SHAFT
    for j in range(5):
        vs = (ids[0][j], ids[0][(j + 1) % 5], ids[1][j], ids[1][(j + 1) % 5])
        me.face(vs, [(u0, v1), (u1, v1), (u0, v0), (u1, v0)], ROW, lambda c: (0, c[1], c[2] - 1))
    lid = me.add((66 - height + 2, 0, 1))
    for j in range(5):
        me.face((ids[1][j], ids[1][(j + 1) % 5], lid), [(u0 + 2, v0 + (2 if cuff else 6))] * 3, ROW, (-1, 0, 0))
    verts, norms, prims = me.close()
    if len(verts) != legs.SHAFT_CORNERS or sum(len(p.raw) for p in prims) != legs.SHAFT_BYTES:
        raise SystemExit('shoes: a boot leg is not the size trousers keep for it')
    return verts, norms, prims


def fill(idx, r, f):
    u0, v0, u1, v1 = r
    for y in range(v0, v1 + 1):
        for x in range(u0, u1 + 1):
            c = f(x, y) if inside(x, y) else None
            if c is not None:
                idx[y * W + x] = c


def inside(x, y):
    if SEAT[0] <= x < SEAT[0] + SEAT[2] and SEAT[1] <= y < SEAT[1] + SEAT[3]:
        return False
    return any(u <= x < u + w and v <= y < v + h for u, v, w, h in RECTS)


def paint(model, idx, drawing, boot):
    if drawing in ('flat', 'bare', 'strap', 'cuff'):     # the laces and the trim go
        for p in model.tmd.objects[OBJECTS[0]].prims:
            d = p.decode()
            us, vs = [q[0] for q in d['uv']], [q[1] for q in d['uv']]
            fill(idx, (min(us) - 1, min(vs) - 1, max(us) + 1, max(vs) + 1),
                 lambda x, y: PLAIN if inside(x, y) and idx[y * W + x] < TRIM else None)
    if drawing in ('bare', 'strap'):                     # low shoes: the top of the foot bare, a strap across it
        strap = drawing == 'strap'
        fill(idx, (40, 88, 55, 108), lambda x, y: PLAIN if (strap and 99 <= y <= 102) or y > 106 else 2)
        fill(idx, HEEL, lambda x, y: 2 if y <= 58 else None)
    if drawing == 'sandals':                             # a sole, the foot over it, three straps
        for r in SIDES:
            fill(idx, r, lambda x, y: (3 if y >= 54 else 2) if y >= 49 else (4 if 210 <= x <= 216 else PLAIN))
        fill(idx, (239, 42, 239, 55), lambda x, y: 2 if y >= 49 else PLAIN)
        fill(idx, HEEL, lambda x, y: 4 if 58 <= y <= 61 else PLAIN)
        fill(idx, TOP, lambda x, y: 4 if (97 <= y <= 101 or 113 <= y <= 117) else (10 if y > 121 and x in (43, 47, 51) else 8))
        fill(idx, TOE, lambda x, y: 2 if y >= 122 else (11 if x in (162, 165) and y > 115 else PLAIN))
        fill(idx, SOLE, lambda x, y: 4)
    if boot:
        u0, v0, u1, v1 = SHAFT

        def leg(x, y):
            if drawing == 'cuff' and y <= v0 + 3:
                return 2 if y == v0 + 3 else 1
            return 3 if drawing == 'seams' and (y - v0) % 5 == 0 else PLAIN
        fill(idx, (u0 - 1, v0 - 1, u1 + 1, v1 + 1), leg)


def recipe(texture, drawing):
    """The feet's palette row: the shoe in the colour, and its trim in the second colour, as skin or as the colour."""
    ways, levels, fixed = [shirts.KEEP] * 16, [0] * 16, [0] * 16
    skin = rgb15(texture.pal[shirts.SKIN_ROW][texture.idx[shirts.SKIN_AT[1] * W + shirts.SKIN_AT[0]]])

    def bare(i, level):
        ways[i], fixed[i] = shirts.SKINNED, c15(*[min(255, int(c * level)) for c in skin])
    for i in range(TRIM, 16):
        level = 1.1 - .8 * (i - TRIM) / 8
        if drawing == 'sandals':
            bare(i, level)
        else:
            ways[i], levels[i] = shirts.tone(level)
    old = [sum(rgb15(c)) for c in texture.pal[ROW][:TRIM]]
    for i in range(TRIM):
        if drawing in ('bare', 'strap'):
            bare(i, 1.08 - .48 * i / 6)
        elif drawing == 'sandals':
            ways[i], levels[i] = shirts.tone(1.3 - .85 * i / 6)
        elif drawing in ('flat', 'cuff'):
            ways[i], levels[i] = SECOND, int(round(128 * (1.1 - .6 * i / 6)))
        else:
            ways[i], levels[i] = SECOND, int(round(128 * (.45 + .65 * old[i] / (max(old) or 1))))
    return ways, levels, fixed


def own_recipe(texture):
    """The tamer's own shoes in a cloth colour: their four tones of red follow it; white, sole and yellow stay."""
    ways, levels, fixed = [shirts.KEEP] * 16, [0] * 16, [0] * 16
    tones = [sum(rgb15(c)) for c in texture.pal[ROW]]
    for i in range(2, 6):
        ways[i], levels[i] = shirts.tone(tones[i] / tones[3])
    return ways, levels, fixed


def palette(texture, rec, cloth):
    """The texture's palette rows for shoes of a cloth colour, as the game writes them (for pictures)."""
    rows = [list(p) for p in texture.pal]
    rows[ROW] = shirts.palette(rec, cloth, rows[ROW])
    return rows


def booted(parts, leg):
    """Trousers with a boot's leg where the game copies it (for pictures)."""
    if not leg:
        return parts
    out = dict(parts)
    for oi in legs.SHIN:
        verts, norms, prims = parts[oi]
        n = legs.SHAFT_CORNERS
        out[oi] = (list(leg[0]) + list(verts[n:]), list(leg[1]) + list(norms[n:]), list(leg[2]) + list(prims))
    return out


def check_free(model):
    """The feet's drawing and palette row must be the feet's alone."""
    for oi, ob in enumerate(model.tmd.objects):
        if oi in OBJECTS:
            continue
        for pi, p in enumerate(ob.prims):
            d = p.decode()
            if 'uv' not in d:
                continue
            us, vs = [q[0] for q in d['uv']], [q[1] for q in d['uv']]
            if all(inside(*q) is False and SEAT[0] <= q[0] < SEAT[0] + SEAT[2] for q in d['uv']):
                continue
            if any(min(us) < u + w and max(us) >= u and min(vs) < v + h and max(vs) >= v for u, v, w, h in RECTS):
                raise SystemExit(f'shoes: object {oi} polygon {pi} uses the texture the shoes draw on')
            if shirts.prim_row(d) == ROW:
                raise SystemExit(f'shoes: object {oi} polygon {pi} is drawn in the feet palette row')


def build(model, texture):
    """Every pair of shoes: [(name, first sector, geometry, parts, pixels or None, recipe or None, boot leg or None)]."""
    check_free(model)
    parts = {oi: shirts.part(model, oi) for oi in OBJECTS}
    body, table = shirts.geometry(parts, OBJECTS)
    own = own_recipe(texture)
    out = [('original', shirts.head(table, len(body), own, flags=shirts.OWN), body, parts, None, own, None)]
    for name, boot, drawing, size in STYLES:
        parts = {oi: sized(shirts.part(model, oi), size) for oi in OBJECTS}
        body, table = shirts.geometry(parts, OBJECTS)
        idx = bytearray(texture.idx)
        paint(model, idx, drawing, boot)
        rec = recipe(texture, drawing)
        first = bytearray(shirts.head(table, len(body), rec, shirts.pixels(idx, RECTS), RECTS))
        leg = shaft(model, *boot) if boot else None
        if leg:
            verts, norms, prims = leg
            blob = b''.join(struct.pack('<4h', *v) for v in verts) + b''.join(struct.pack('<4h', *n) for n in norms)
            blob += b''.join(p.raw for p in prims)
            struct.pack_into('<HH', first, SHAFT_AT, len(prims), 0)
            first[SHAFT_AT + 4:SHAFT_AT + 4 + len(blob)] = blob
        out.append((name, bytes(first), body, parts, idx, rec, leg))
    return out
