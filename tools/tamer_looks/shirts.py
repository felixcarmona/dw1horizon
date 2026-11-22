"""The tamer's shirts: the torso and the arms as pieces of their own, worn with any head.

A shirt is the five objects a top covers (the torso, the upper arms and the forearms), built from nothing over the
tamer's skeleton: rings around the trunk, tubes along the arms, and a small texture drawn for it. Only the crotch of the
trousers is kept from the tamer's own torso. The original clothes (the hoodie and the backpack) are shirt 0: the same
five objects as the disc has them.

The backpack is part of the torso and a choice of its own (backpacks.py). Every shirt but shirt 0 keeps room for one:
PACK_CORNERS corners and normals at the start of the torso's, PACK_BYTES before its polygons (ROOM in the first
sector's flags), and a third rectangle of pixels, the trunk again with the straps on it (STRAPS), which the game draws
when a backpack is worn. Shirt 0 with another backpack, or with none, is one of two more shirts kept after the ones
that can be chosen: the hoodie without the backpack's polygons, its back closed (bare), as it is drawn (its straps
stay) and with the straps painted out.

One texture serves every colour: the cloth is drawn with the tones 1..6 of the torso's palette row, and the game
writes that row for the chosen colour (RECIPE below). The drawing replaces two rectangles of the tamer's texture that
only the hoodie and the backpack used.
"""
import colorsys
import math
import struct

import mmd

W = 256
TORSO = 0
OBJECTS = (0, 2, 3, 5, 6)                  # the torso, the upper arms (2, 5) and the forearms (3, 6)
UPPER, FORE = (2, 5), (3, 6)
PELVIS = (1, 4, 5, 6, 7, 8, 20, 21, 22, 23, 24, 35, 36, 37, 39, 46)   # the torso's polygons that are trousers
# The trousers' top corners reached the hoodie's hem: under a shirt they sit closer to the body.
PELVIS_MOVED = {10: (-31, 12, -26), 34: (-31, 12, 26), 24: (-29, -25, -28), 35: (-29, -25, 28), 23: (-30, -30, 0)}
QUAD, TRI = 3, 38                          # a quad and a triangle of the torso, the patterns of every new polygon
ROW, SKIN_ROW = 2, 6                       # palette rows: the cloth's and the skin's
NC, NS = 8, 6                              # corners around the trunk and around an arm
U0, V0, US, VH = 0, 88, 10, 39             # half the trunk, unrolled: u = front middle .. back middle, v = collar .. hem
SLEEVE = (32, 60, 47, 72)                  # a sleeve's cloth, on the arms' texture: u0, v0 (shoulder), u1, v1 (its end)
SKIN = (16, 25, 22, 31)                    # a patch of plain skin on the face's texture
UMAX = 39                                  # the back's middle: the shoes' texture starts right after it
TRUNK = (0, 88, 40, 40)
RECTS = (TRUNK, (32, 60, 24, 13))          # what a shirt draws: u, v, width, height (u and width in whole bytes)
BARE = (48, 60, 13)                        # bare skin, drawn beside the sleeve's cloth: u, v, height (skin_strips)
PACK_CORNERS, PACK_BYTES = 16, 400         # the room a torso keeps for a backpack
ROOM, STRAPS = 2, 4                        # flags in the first sector
OWN, SLEEVES = 16, 32                      # more: with colour 0 it keeps its own colours; its cloth is in the arms' row too
STRAP, STRAP_DARK, STRAP_EDGE = 11, 12, 13  # tones of a backpack's straps
BACK = (68, 57, 95, 86)                    # folds of the hoodie's cloth on the arms' texture: the back without a backpack
PACK = (2, 3, 13, 14, 28, 29, 38, 41, 45, 48, 52)   # the torso's polygons that are the backpack (backpacks.POLYGONS)
WHITE, GREY, SK, SK2, SK3 = 7, 8, 9, 10, 14  # tones besides the cloth's 1..6: a second colour and its shade; skin, lit to shaded
SUN = (.45, -.5, -.74)                     # where bare skin is lit from as he stands: his side, above (y is down), his front (-z)
CLOTH_LEVELS = (255, 192, 128, 85, 43, 0)  # the cloth's tones 1..6, as the hoodie's own lie between its light and its shade
SKIN_AT = (19, 28)                         # where the skin's colour is read

# The trunk's rings, hem to shoulders: height, half width, front, back and, on some, how far the bust comes out.
BODY = {
    'tee': ((-35, 33, -33, 16), (-37, 41, -41, 23), (-10, 42, -44, 25), (22, 42, -40, 25), (46, 40, -30, 19),
            (58, 27, -23, 14)),
    'hoodie': ((-37, 36, -36, 18), (-40, 45, -47, 26), (-12, 47, -52, 29), (22, 46, -45, 28), (46, 42, -32, 21),
               (59, 29, -25, 16)),
    'fit': ((-34, 30, -30, 14), (-36, 37, -37, 20), (-8, 33, -33, 19), (15, 35, -35, 21), (30, 38, -41, 23, 12),
            (46, 37, -29, 18), (58, 25, -22, 13)),
    'peplum': ((-40, 38, -38, 20), (-43, 47, -46, 28), (-14, 33, -33, 19), (15, 35, -35, 21), (30, 38, -41, 23, 12),
               (46, 37, -29, 18), (58, 25, -22, 13)),
}
# The collar's ring: height, half width, front, back, and how far it dips at the front.
COLLAR = {'tee': (64, 16, -21, 9, 7), 'hoodie': (66, 17, -22, 10, 5), 'fit': (64, 16, -21, 9, 10),
          'peplum': (64, 16, -21, 9, 10)}
NECK = (73, -5, 0)
# An arm's rings along it: distance, two radii, what follows ('f' cloth, 's' skin, 'c' the cuff's opening) and the
# sleeve texture's row. Upper arm, then forearm (None: the tamer's own forearm, bare).
ARMS = {
    'short': ([(0, 15, 13, 'f', 0), (24, 16, 14, 'f', 12), (24, 11, 9, 'c', 12), (50, 10, 9, 's', 12)], None),
    'cap': ([(0, 14, 12, 'f', 0), (13, 14, 12, 'f', 12), (13, 10, 9, 'c', 12), (50, 9, 8, 's', 12)], None),
    'bare': ([(0, 11, 10, 's', 0), (50, 9, 8, 's', 0)], None),
    'long': ([(0, 15, 13, 'f', 0), (50, 15, 13, 'f', 6)],
             [(0, 14, 13, 'f', 6), (44, 13, 12, 'f', 12), (44, 10, 9, 'c', 12), (52, 10, 9, 's', 12)]),
    'slim': ([(0, 13, 11, 'f', 0), (50, 12, 11, 'f', 6)],
             [(0, 12, 11, 'f', 6), (44, 11, 10, 'f', 12), (44, 9, 8, 'c', 12), (52, 9, 8, 's', 12)]),
    'puffy': ([(0, 17, 15, 'f', 0), (50, 17, 15, 'f', 6)],
              [(0, 17, 15, 'f', 6), (43, 15, 14, 'f', 12), (43, 10, 9, 'c', 12), (52, 10, 9, 's', 12)]),
}
BARE_FOREARM = 0.76                        # the tamer's forearm without the hoodie's sleeve: this much of its girth
HOOD = ((66, 8, -27), (66, 8, 27), (73, 25, 0), (42, 31, 0), (52, 23, -27), (52, 23, 27))

# name, trunk, arms, hood, drawing, whether the second colour follows the chosen one. The number is saved: add at the end.
STYLES = (
    ('tee', 'tee', 'short', False, 'plain', False),
    ('striped', 'tee', 'short', False, 'stripes', True),
    ('print', 'tee', 'short', False, 'print', True),
    ('long sleeve', 'tee', 'long', False, 'long', False),
    ('hoodie', 'hoodie', 'puffy', True, 'hoodie', False),
    ('jacket', 'hoodie', 'puffy', False, 'jacket', False),
    ('fitted tee', 'fit', 'cap', False, 'fit', False),
    ('top', 'fit', 'bare', False, 'top', False),
    ('cardigan', 'fit', 'slim', False, 'cardigan', False),
    ('blouse', 'peplum', 'cap', False, 'peplum', False),
)
NAMES = ('original',) + tuple(s[0] for s in STYLES)

# The shirt colours: the cloth, and the colour of stripes and prints on it (dark on a light cloth).
LIGHT, DARK = (246, 246, 240), (60, 70, 110)
CLOTH = (
    ('white', (244, 244, 240)), ('grey', (150, 150, 155)), ('black', (40, 40, 46)), ('red', (216, 72, 60)),
    ('burgundy', (140, 35, 55)), ('orange', (232, 136, 56)), ('yellow', (240, 200, 72)), ('lime', (156, 196, 80)),
    ('green', (84, 156, 92)), ('turquoise', (64, 172, 172)), ('blue', (68, 108, 188)), ('navy', (45, 60, 120)),
    ('purple', (144, 96, 184)), ('lavender', (190, 170, 235)), ('pink', (228, 124, 164)), ('brown', (140, 95, 60)),
)
KEEP, MAIN, SECOND, FIXED, DEEP, SKINNED = 0, 1, 2, 3, 4, 5   # how a tone of the cloth's palette row gets its colour (SKINNED: fixed, in the skin's tone)
SHADE_AT, LIGHT_AT = .62, 1.3              # how bright a colour's shade and its light are next to it


def shades(rgb):
    """A cloth colour's shade and its light, as the tamer's own clothes are painted: the shade darker, richer and a
    little towards red or violet, the light paler and a little towards yellow."""
    h, s, v = colorsys.rgb_to_hsv(*[c / 255 for c in rgb])

    def towards(hue, target, most):
        d = (target - hue + .5) % 1 - .5
        return (hue + max(-most, min(most, d))) % 1

    def out(hue, sat, val):
        return tuple(int(round(c * 255)) for c in colorsys.hsv_to_rgb(hue, max(0, min(1, sat)), max(0, min(1, val))))
    k = min(1, s / .25)                                # greys stay grey
    if s < .1:
        shade = out(.64, .1 + s, v * (.74 if v > .6 else .6))
        light = out(h, s * .6, v + (1 - v) * (.5 if v > .3 else .3))
    else:
        shade = out(towards(h, .78 if .1 < h < .55 and h > .2 else .97 if h <= .2 else .72, .035 * k),
                    s + (1 - s) * .55 * k, v * SHADE_AT)
        light = out(towards(h, .15, .02 * k), s * .78, v + (1 - v) * .55)
    return shade, light


def tone(light):
    """How a tone that bright next to the colour (1: the colour itself) is asked of the game: a way and a level."""
    if light >= 1:
        return MAIN, min(255, 128 + int(round((light - 1) / (LIGHT_AT - 1) * 127)))
    if light >= SHADE_AT:
        return MAIN, int(round((light - SHADE_AT) / (1 - SHADE_AT) * 128))
    return DEEP, int(round(light / SHADE_AT * 128))


# name, the shade, the colour, the light, the second colour
COLOURS = tuple((name, shades(rgb)[0], rgb, shades(rgb)[1], DARK if sum(rgb) > 600 else LIGHT) for name, rgb in CLOTH)


def c15(r, g, b):
    return (min(r, 255) >> 3) | ((min(g, 255) >> 3) << 5) | ((min(b, 255) >> 3) << 10)


def rgb15(c):
    return ((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3)


def cross(a, b, c):
    ux, uy, uz = (b[i] - a[i] for i in range(3))
    vx, vy, vz = (c[i] - a[i] for i in range(3))
    return (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)


def set_row(d, row):
    d['cba'] = (d['cba'] & 0x3f) | ((488 + row) << 6)


def prim_row(d):
    return ((d['cba'] >> 6) & 0x1ff) - 488


def ring(x, w, f, b, dip=0, bust=0):
    """One ring of the trunk: a rounded box, lower at the front by dip, its two front corners pushed out by bust."""
    out = []
    for j in range(NC):
        a = 2 * math.pi * j / NC
        c, s = math.cos(a), math.sin(a)

        def e(q):
            return math.copysign(abs(q) ** .75, q)
        push = bust if j in (1, NC - 1) else bust * .3 if j == 0 else 0
        out.append((int(round(x - dip * max(0, c))), int(round((f + b) / 2 - e(c) * (b - f) / 2 - push)),
                    int(round(e(s) * w))))
    return out


class Mesh:
    """Faces with a hint of where outside is; corner order and smooth normals are worked out when it is closed."""

    def __init__(self, quad, tri, sign, base=0, skin=None, sun=None):
        self.pts, self.faces = [], []
        self.quad, self.tri, self.sign, self.base = quad, tri, sign, base
        self.skin, self.sun = skin, sun                # for faces of BARE_SKIN: (u, v, height, palette row), and the light

    def add(self, p):
        self.pts.append(tuple(int(round(q)) for q in p))
        return len(self.pts) - 1

    def face(self, vs, uvs, row, out):
        self.faces.append((list(vs), uvs if uvs is BARE_SKIN else list(uvs), row, out))

    def close(self):
        acc = [[0, 0, 0] for _ in self.pts]
        prims = []
        for vs, uvs, row, out in self.faces:
            pts = [self.pts[k] for k in vs]
            cn = cross(*pts[:3])
            centre = [sum(p[i] for p in pts) / len(pts) for i in range(3)]
            o = out(centre) if callable(out) else out
            if sum(cn[i] * o[i] for i in range(3)) * self.sign < 0:
                def swap(q):
                    return [q[1], q[0]] + ([q[3], q[2]] if len(q) == 4 else [q[2]])
                vs, uvs = swap(vs), uvs if uvs is BARE_SKIN else swap(uvs)
                cn = cross(*[self.pts[k] for k in vs][:3])
            length = sum(q * q for q in cn) ** .5 or 1
            if uvs is BARE_SKIN:
                uvs, row = skin_uv([self.sign * q / length for q in cn], self.sun, self.skin, len(vs))
            for k in vs:
                for i in range(3):
                    acc[k][i] += self.sign * cn[i] / length
            d = dict(self.quad if len(vs) == 4 else self.tri)
            d['verts'] = [self.base + k for k in vs]
            d['norms'] = [self.base + k for k in vs]
            d['uv'] = uvs
            set_row(d, row)
            prims.append(mmd.Prim.encode(d))
        norms = []
        for a in acc:
            length = sum(q * q for q in a) ** .5 or 1
            norms.append(tuple(int(round(4096 * q / length)) for q in a) + (0,))
        return [p + (0,) for p in self.pts], norms, prims


SKIN_TRI = [(SKIN[0], SKIN[1]), (SKIN[2], SKIN[1]), (SKIN[0], SKIN[3])]
SKIN_QUAD = SKIN_TRI + [(SKIN[2], SKIN[3])]
BARE_SKIN = ['bare skin']                  # in place of a face's texture corners: skin, lit by where the face looks


def skin_uv(normal, sun, skin, corners):
    """The texture corners and palette row of a face of bare skin: one of three strips a garment draws (lit, plain,
    shaded: skin_strips) by how the face looks at the light, or the face's plain skin when the garment draws none."""
    if skin is None or sun is None:
        return (SKIN_QUAD if corners == 4 else SKIN_TRI), SKIN_ROW
    u, v, height, row = skin
    lit = sum(a * b for a, b in zip(normal, sun))
    u += 0 if lit > .3 else 3 if lit > -.3 else 6
    quad = [(u, v + 1), (u + 1, v + 1), (u, v + height - 2), (u + 1, v + height - 2)]
    return (quad if corners == 4 else quad[:3]), row


def skin_strips(idx, u, v, height, tones):
    """Draw the three strips of skin_uv, eight pixels wide: under a garment's edge the skin is a tone darker."""
    for y in range(height):
        for x in range(8):
            k = (0 if x < 2 else 1 if x < 5 else 2) + (y < 2)
            idx[(v + y) * W + u + x] = tones[min(k, 2)]


def suns(model):
    """Per object of the model, SUN in the object's own frame while the tamer stands."""
    nbones = mmd.exe().bone_count[model.type]
    frames, _ = mmd.simulate(model.anims.anims[model.anims.table[0]], nbones)
    pose = frames[0]
    pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
    out = {}
    for bone, (oi, _) in enumerate(mmd.exe().skeleton[model.type]):
        if oi < 0:
            continue
        m = mmd.bone_matrices(model, pose)[bone]
        v = [sum(m[i][j] * SUN[i] for i in range(3)) for j in range(3)]
        length = sum(q * q for q in v) ** .5 or 1
        out[oi] = tuple(q / length for q in v)
    return out


def tube(mesh, rings):
    """A limb along x, closed at both ends: a round shoulder, a round elbow or wrist."""
    ids = [[mesh.add((x, ry * math.cos(2 * math.pi * j / NS), rz * math.sin(2 * math.pi * j / NS)))
            for j in range(NS)] for x, ry, rz, _, _ in rings]
    u, v = SLEEVE[0], SLEEVE[1]

    def radial(c):
        return (0, c[1], c[2])
    cap = mesh.add((rings[0][0] - 4, 0, 0))
    end = mesh.add((rings[-1][0] + 6, 0, 0))
    for j in range(NS):
        k = (j + 1) % NS
        if rings[0][3] == 'f':
            mesh.face((ids[0][j], ids[0][k], cap), [(u + 2, v), (u + 6, v), (u + 4, v + 1)], ROW, (-1, 0, 0))
        else:
            mesh.face((ids[0][j], ids[0][k], cap), BARE_SKIN, ROW, (-1, 0, 0))
        if rings[-1][3] == 's':
            mesh.face((ids[-1][j], ids[-1][k], end), BARE_SKIN, ROW, (1, 0, 0))
        else:
            mesh.face((ids[-1][j], ids[-1][k], end), [(u + 2, v + 4), (u + 6, v + 4), (u + 4, v + 5)], ROW, (1, 0, 0))
    for i in range(len(rings) - 1):
        kind = rings[i + 1][3]
        for j in range(NS):
            vs = (ids[i][j], ids[i][(j + 1) % NS], ids[i + 1][j], ids[i + 1][(j + 1) % NS])
            if kind == 's':
                mesh.face(vs, BARE_SKIN, ROW, radial)
            elif kind == 'c':
                mesh.face(vs, [(u + 2, SLEEVE[3] - 2)] * 2 + [(u + 4, SLEEVE[3] - 2)] * 2, ROW, (1, 0, 0))
            else:
                va, vb = v + rings[i][4], v + rings[i + 1][4]
                ua, ub = u + (j % 2) * 7, u + 7 + (j % 2) * 7
                mesh.face(vs, [(ua, va), (ub, va), (ua, vb), (ub, vb)], ROW, radial)


def patterns(model):
    """The quad and the triangle every new polygon copies, and the sign that tells which side of one is drawn."""
    tm = model.tmd
    ob = tm.objects[TORSO]
    quad, tri = ob.prims[QUAD].decode(), ob.prims[TRI].decode()
    if len(quad['verts']) != 4 or len(tri['verts']) != 3:
        raise SystemExit('shirts: the tamer torso is not the expected one')
    c = cross(*[tm.verts[ob.vert_start + k][:3] for k in quad['verts'][:3]])
    n = tm.norms[ob.norm_start + quad['norms'][0]]
    return quad, tri, 1 if sum(c[i] * n[i] for i in range(3)) > 0 else -1


def part(model, oi):
    """An object's corners, normals and polygons as the model has them."""
    tm = model.tmd
    ob = tm.objects[oi]
    return (list(tm.verts[ob.vert_start:ob.vert_start + ob.nvert]),
            list(tm.norms[ob.norm_start:ob.norm_start + ob.nnorm]), list(ob.prims))


def compact(verts, norms, prims):
    """Only the corners and normals the polygons use."""
    new_verts, new_norms, vert_at, norm_at, out = [], [], {}, {}, []
    for p in prims:
        d = p.decode()
        for key, old, new, at in (('verts', verts, new_verts, vert_at), ('norms', norms, new_norms, norm_at)):
            ids = []
            for i in d.get(key, ()):
                if i not in at:
                    at[i] = len(new)
                    new.append(old[i])
                ids.append(at[i])
            if key in d:
                d[key] = ids
        out.append(mmd.Prim.encode(d))
    return new_verts, new_norms, out


def original(model):
    """Shirt 0: the hoodie and the backpack. The seat's polygons come first in the torso, as in every shirt: trousers
    recolour them there (legs.py)."""
    parts = {oi: part(model, oi) for oi in OBJECTS}
    verts, norms, prims = parts[TORSO]
    parts[TORSO] = (verts, norms, [prims[i] for i in PELVIS] + [p for i, p in enumerate(prims) if i not in PELVIS])
    return parts


def garment(model, body, arms, hood):
    """The five objects of a shirt."""
    quad, tri, sign = patterns(model)
    verts, norms, prims = part(model, TORSO)
    for k, p in PELVIS_MOVED.items():
        verts[k] = p + (0,)
    verts, norms, pelvis = compact(verts, norms, [prims[i] for i in PELVIS])
    if len(verts) != len(norms):                      # the new polygons use one number for a corner and its normal
        pad = max(len(verts), len(norms))
        verts += [(0, 0, 0, 0)] * (pad - len(verts))
        norms += [(0, 0, 0, 0)] * (pad - len(norms))
    me = Mesh(quad, tri, sign, len(verts))
    cx, cw, cf, cb, dip = COLLAR[body]
    rings = [ring(*r[:4], bust=(r[4] if len(r) > 4 else 0)) for r in BODY[body]] + [ring(cx, cw, cf, cb, dip)]
    xs = [r[0] for r in BODY[body]] + [cx]
    hs = [0] + [max(.05, (q - xs[1]) / (cx - xs[1])) for q in xs[1:]]
    ids = [[me.add(p) for p in r] for r in rings]

    def uv(i, j):
        k = j if j <= NC // 2 else NC - j
        return (min(UMAX, U0 + k * US), V0 + VH - int(round(VH * hs[i])))

    def around(centre):
        return (0, centre[1] + 8, centre[2])
    for i in range(len(rings) - 1):
        for j in range(NC):
            k = (j + 1) % NC
            me.face((ids[i][j], ids[i][k], ids[i + 1][j], ids[i + 1][k]), [uv(i, j), uv(i, k), uv(i + 1, j), uv(i + 1, k)],
                    ROW, around if i else (-1, 0, 0))
    neck = me.add(NECK)
    for j in range(NC):
        me.face((ids[-1][j], ids[-1][(j + 1) % NC], neck), SKIN_TRI, SKIN_ROW, (1, 0, 0))
    if hood:                                          # the hood, lying on the upper back
        left, right, top, bottom, low_left, low_right = (me.add(p) for p in HOOD)

        def hu(a, b):
            return (min(UMAX, U0 + a), V0 + b)
        up = (.4, 1, 0)
        me.face((left, top, low_left, bottom), [hu(28, 2), hu(40, 0), hu(28, 9), hu(40, 11)], ROW, up)
        me.face((top, right, bottom, low_right), [hu(40, 0), hu(28, 2), hu(40, 11), hu(28, 9)], ROW, up)
        me.face((left, low_left, ids[-2][5]), [hu(28, 2), hu(28, 9), hu(22, 6)], ROW, (0, .3, -1))
        me.face((right, low_right, ids[-2][3]), [hu(28, 2), hu(28, 9), hu(22, 6)], ROW, (0, .3, 1))
        me.face((left, top, ids[-1][4]), [hu(28, 2), hu(40, 0), hu(40, 2)], ROW, (1, .3, 0))
        me.face((top, right, ids[-1][4]), [hu(40, 0), hu(28, 2), hu(40, 2)], ROW, (1, .3, 0))
    pts, nrm, new = me.close()
    parts = {TORSO: roomy((verts + pts, norms + nrm, pelvis + new))}
    upper, fore = ARMS[arms]
    sun, skin = suns(model), BARE + (ROW,)
    for oi in UPPER:
        me = Mesh(quad, tri, sign, skin=skin, sun=sun[oi])
        tube(me, upper)
        parts[oi] = me.close()
    for oi in FORE:
        if fore:
            me = Mesh(quad, tri, sign, skin=skin, sun=sun[oi])
            tube(me, fore)
            parts[oi] = me.close()
            continue
        verts, norms, prims = part(model, oi)
        bare = []
        for p in prims:
            d = p.decode()
            cn = cross(*[verts[k] for k in d['verts'][:3]])
            length = sum(q * q for q in cn) ** .5 or 1
            d['uv'], row = skin_uv([sign * q / length for q in cn], sun[oi], skin, len(d['verts']))
            set_row(d, row)
            bare.append(mmd.Prim.encode(d))
        verts = [(x, int(round(y * BARE_FOREARM)), int(round(z * BARE_FOREARM)), w) for x, y, z, w in verts]
        parts[oi] = compact(verts, norms, bare)
    return parts


def roomy(part):
    """A torso with room for a backpack's corners and normals before its own."""
    verts, norms, prims = part
    n = max(len(verts), len(norms))
    out = []
    for p in prims:
        d = p.decode()
        for key in ('verts', 'norms'):
            if key in d:
                d[key] = [i + PACK_CORNERS for i in d[key]]
        out.append(mmd.Prim.encode(d))
    return ([(0, 0, 0, 0)] * PACK_CORNERS + list(verts) + [(0, 0, 0, 0)] * (n - len(verts)),
            [(0, 0, 0, 0)] * PACK_CORNERS + list(norms) + [(0, 0, 0, 0)] * (n - len(norms)), out)


def bare(model):
    """The original hoodie without the backpack: its polygons gone, the back closed, the hood lying on it."""
    quad, tri, sign = patterns(model)
    parts = {oi: part(model, oi) for oi in OBJECTS}
    verts, norms, prims = parts[TORSO]
    verts = list(verts)
    verts[0] = (44, 31, 0, 0)                         # the hood's tip rested on the backpack
    n = max(len(verts), len(norms))
    verts += [(0, 0, 0, 0)] * (n - len(verts))
    norms = list(norms) + [(0, 0, 0, 0)] * (n - len(norms))
    me = Mesh(quad, tri, sign, n)
    # the hole's edge, bottom to shoulders, and a spine that stands out between its two sides
    low, mid, top = ((me.add(verts[a][:3]), me.add((x, y, 0)), me.add(verts[b][:3]))
                     for a, b, x, y in ((10, 34, -31, 29), (18, 37, 20, 31), (16, 38, 54, 23)))
    tip = me.add(verts[0][:3])
    back = (0, 1, 0)
    u0, um, u1, va, vb, vc = BACK[0], (BACK[0] + BACK[2]) // 2, BACK[2], BACK[1], (BACK[1] + BACK[3]) // 2, BACK[3]
    for s, (ua, ub) in enumerate(((u0, um), (um, u1))):
        me.face((mid[s], mid[s + 1], low[s], low[s + 1]), [(ua, vb), (ub, vb), (ua, vc), (ub, vc)], ROW, back)
        me.face((top[s], top[s + 1], mid[s], mid[s + 1]), [(ua, va), (ub, va), (ua, vb), (ub, vb)], ROW, back)
        me.face((top[s], top[s + 1], tip), [(ua, va), (ub, va), (um, va)], ROW, (.3, 1, 0))
    me.face((low[0], low[1], low[2]), [(u0, vc), (um, vc), (u1, vc)], ROW, (-1, 0, 0))
    pts, nrm, new = me.close()
    kept = [prims[i] for i in PELVIS] + [p for i, p in enumerate(prims) if i not in PELVIS and i not in PACK]
    parts[TORSO] = roomy((verts + pts, norms + nrm, kept + new))
    return parts


def unpack(idx):
    """The hoodie's own drawing without the corner of the backpack that shows under each arm."""
    pack = [(u, v) for v in range(108, 128) for u in range(24, 40) if 11 <= idx[v * W + u] <= 14]
    for u, v in pack:
        for du, dv in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if idx[(v + dv) * W + u + du] == 15 and (u + du) < 40:
                idx[(v + dv) * W + u + du] = 5
    for u, v in pack:
        idx[v * W + u] = (5, 4, 4, 3)[idx[v * W + u] - 11]


def unstrap(idx):
    """The hoodie's own drawing without the backpack's straps: the band of dark tones down each side of the chest."""
    for v in range(88, 118):
        row = [idx[v * W + u] for u in range(44)]
        start = next((u for u in range(13, 30) if row[u] in (9, 10) and row[u - 1] == 15), None)
        if start is None:
            continue
        end = start
        for u in range(start, min(start + 13, 44)):
            if row[u] not in (9, 10, 15):
                break
            if row[u] in (9, 10):
                end = u
        if row[end + 1] == 15:
            end += 1
        first = start if row[start - 2] in (7, 12, 13, 14, 15) and 94 <= v <= 104 else start - 1   # the badge keeps its edge
        for u in range(first, end + 1):
            k = u - first
            tone = 4 if k < 1 or u >= end else 2 if (u * 3 + v * 2) % 11 == 0 else 3
            idx[v * W + u] = tone


FOLDS_AT = (32, 57)                        # the hoodie's sleeves on the tamer's texture: 88 by 17 pixels of nothing but folds
# how much of those folds each drawing keeps: a thin shirt lies flatter than the hoodie
FOLDS_KEPT = {'hoodie': 1.0, 'jacket': .9, 'long': .7, 'cardigan': .7}


def folds(source):
    """The hoodie's own folds: how bright its cloth is at (x, y) of an endless sheet of them, -1 (the shade) .. 1."""
    u0, v0 = FOLDS_AT

    def at(x, y):
        band, y = divmod(y, 17)
        x = (x + 46 * band) % 88
        return 1 - (source[(v0 + y) * W + u0 + x] - 1) / 2.5
    return at


def shape(drawing, a, h):
    """How a trunk's shape lights it at a (0 the front's middle .. 4 the back's) and h (0 the hem .. 1 the collar)."""
    def bump(x, y, x0, y0, rx, ry):
        return math.exp(-((x - x0) / rx) ** 2 - ((y - y0) / ry) ** 2)
    light = .3 * bump(a, h, .5, .62, .9, .22)          # the chest
    light += .25 * bump(a, h, 3.4, .68, .7, .2)        # the shoulder blades
    light -= .55 * bump(a, h, 2.05, .3, .5, .42)       # under the arm
    light -= .3 * bump(a, h, 4.0, .25, .5, .3)         # the small of the back
    light -= .35 * max(0, .12 - h) / .12               # the hem turns under
    light -= .3 * bump(a, h, .0, .9, 1.2, .05)         # under the collar
    if drawing in ('fit', 'top', 'peplum', 'cardigan'):
        light += .3 * bump(a, h, .6, .7, .5, .1) - .45 * bump(a, h, .7, .57, .9, .035)   # the bust and under it
    return light


def paint(idx, drawing, straps=False, source=None):
    """Draw a shirt on the texture's pixels: the unrolled half trunk and the sleeve's cloth, with the folds of the
    hoodie's own cloth (source: the tamer's texture as the disc has it). straps: with a backpack's straps, over the
    shoulder, down the chest and round the side to the back."""
    fold, kept = folds(source or bytes(idx)), FOLDS_KEPT.get(drawing, .55)

    def cloth(light):
        return max(1, min(6, int(round((1 - light) * 2.5 + 1))))
    for v in range(V0, V0 + VH + 1):
        for u in range(U0, UMAX + 1):
            a, h = (u - U0) / US, (V0 + VH - v) / VH
            light = fold(u - U0, v - V0) * kept + shape(drawing, a, h)
            tone = cloth(light)
            if h > .93:
                tone = 5                               # the collar
            elif h > .9:
                tone = min(tone, 2)
            if v >= V0 + VH - 1:
                tone = 5                               # the hem
            elif v == V0 + VH - 2:
                tone = max(tone, 4)
            if drawing == 'stripes' and .08 < h < .9 and (v // 3) % 2 == 0:
                tone = WHITE if tone < 4 else GREY
            if drawing == 'print' and a < .75 and .45 < h < .75 and 3.2 < math.hypot(u - U0, v - (V0 + VH * .4)) < 6.2:
                tone = WHITE                           # a ring on the chest
            if drawing == 'hoodie':
                if a < 1.15 and .1 < h < .36:          # the pocket
                    tone = 5 if (abs(a - 1.15) < .12 or abs(h - .36) < .03 or abs(h - .1) < .03) else max(1, tone - 1)
                if a < .12 and h > .6:
                    tone = 6                           # the collar's slit
                if .25 < a < .4 and .62 < h < .9:
                    tone = WHITE                       # a string
                if v >= V0 + VH - 4:
                    tone = 5 if u % 2 else 4           # the ribbed hem
            if drawing == 'jacket':
                if a < .55:
                    tone = WHITE if h < .9 else GREY   # the shirt under it
                elif a < .72:
                    tone = 6
                if 1.0 < a < 1.5 and .5 < h < .6:
                    tone = 5                           # a chest pocket
            if drawing == 'top':
                if h > .8:
                    tone = SK if h < .93 else SK2      # bare shoulders
                elif h > .76:
                    tone = 5
            if drawing == 'cardigan':
                if a < .5:
                    tone = WHITE if h < .88 else SK    # the shirt under it
                elif a < .62:
                    tone = 5
            if drawing == 'peplum' and .3 < h < .36:
                tone = 5                               # the belt
            if straps:
                # down the chest, then round the side under the arm
                d = a - .8 if h > .44 else None
                if h <= .44 and .8 <= a <= 3.3:
                    d = ((h - .44) + (a - .8) * .09) * 5
                if d is not None and abs(d) < .2 and h < .955:
                    tone = STRAP_EDGE if abs(d) > .13 else STRAP_DARK if d < -.02 else STRAP
            idx[v * W + u] = tone
    skin_strips(idx, *BARE, (SK, SK2, SK3))
    for v in range(SLEEVE[1], SLEEVE[3] + 1):
        for u in range(SLEEVE[0], SLEEVE[2] + 1):
            tone = cloth(fold(u - SLEEVE[0] + 58, v - SLEEVE[1] + 2) * kept + .1)
            if v >= SLEEVE[3] - 2:
                tone = 5 if v == SLEEVE[3] - 2 else 2
            if drawing == 'stripes' and v < SLEEVE[3] - 2 and (v // 3) % 2 == 0:
                tone = WHITE
            if drawing == 'hoodie' and v >= SLEEVE[3] - 2:
                tone = 5 if u % 2 else 4
            idx[v * W + u] = tone


def skin_tones(texture):
    """The tamer's skin as his own face has it: lit, plain and shaded."""
    return texture.pal[SKIN_ROW][1], texture.pal[SKIN_ROW][texture.idx[SKIN_AT[1] * W + SKIN_AT[0]]], texture.pal[0][14]


def recipe(texture, follows):
    """How the game colours the cloth's palette row: per tone a way, a level and a fixed colour (palette below)."""
    ways, levels, fixed = [KEEP] * 16, [0] * 16, [0] * 16
    ways[0], levels[0] = tone(.4)                      # the outline
    for i, level in enumerate(CLOTH_LEVELS):
        ways[i + 1], levels[i + 1] = MAIN, level
    for t, colour in zip((SK, SK2, SK3), skin_tones(texture)):
        ways[t], fixed[t] = SKINNED, colour
    if follows:
        ways[WHITE], levels[WHITE] = SECOND, 128
        ways[GREY], levels[GREY] = SECOND, 107
    else:
        ways[WHITE], fixed[WHITE] = FIXED, c15(*LIGHT)
        ways[GREY], fixed[GREY] = FIXED, c15(205, 205, 200)
    for t, grey in ((STRAP, 92), (STRAP_DARK, 68), (STRAP_EDGE, 44)):
        ways[t], fixed[t] = FIXED, c15(grey, grey, grey + 4)
    return ways, levels, fixed


def own_recipe():
    """The tamer's own hoodie in a cloth colour: its outline and its six tones of cloth; the rest stays (cords, straps
    and the corner of the backpack under each arm). The arms' row has the same tones (SLEEVES)."""
    ways, levels, fixed = [KEEP] * 16, [0] * 16, [0] * 16
    ways[0], levels[0] = tone(.4)
    for i, level in enumerate(CLOTH_LEVELS):
        ways[i + 1], levels[i + 1] = MAIN, level
    return ways, levels, fixed


def palette(rec, cloth, row):
    """A garment's palette row for a cloth colour (its shade, the colour, its light, the second colour): what the
    game computes (lookShirtPalette). A tone of the colour lies between the shade (level 0), the colour (128) and the
    light (255); one of the second colour, or deeper than the shade, between black and that."""
    ways, levels, fixed = rec
    shade, colour, light, second = cloth
    out = list(row)
    for i in range(16):
        w = levels[i]
        if ways[i] in (FIXED, SKINNED):
            out[i] = fixed[i] | 0x8000
            continue
        if ways[i] == KEEP:
            continue
        if ways[i] == MAIN:
            a, b = (shade, colour) if w <= 128 else (colour, light)
            w = w if w <= 128 else w - 128
        else:
            a, b = (0, 0, 0), second if ways[i] == SECOND else shade
        out[i] = c15(*[(p * (128 - w) + q * w) >> 7 for p, q in zip(a, b)]) | 0x8000
    return out


def check_free(model):
    """The rectangles a shirt draws must be used by nothing but the five objects it replaces (the crotch aside)."""
    tm = model.tmd
    for oi, ob in enumerate(tm.objects):
        for pi, p in enumerate(ob.prims):
            if oi in OBJECTS and not (oi == TORSO and pi in PELVIS):
                continue
            d = p.decode()
            if 'uv' not in d:
                continue
            us, vs = [q[0] for q in d['uv']], [q[1] for q in d['uv']]
            for u, v, w, h in RECTS:
                if min(us) < u + w and max(us) >= u and min(vs) < v + h and max(vs) >= v:
                    raise SystemExit(f'shirts: object {oi} polygon {pi} uses the texture a shirt draws on')
            if prim_row(d) == ROW:
                raise SystemExit(f'shirts: object {oi} polygon {pi} is drawn in the cloth palette row')


def strip(model, objects=OBJECTS):
    """Take a garment's objects out of a model: the game links the garment's in their place."""
    tm = model.tmd
    for oi in objects:
        ob = tm.objects[oi]
        for pool, start, count in ((tm.verts, 'vert_start', 'nvert'), (tm.norms, 'norm_start', 'nnorm')):
            s, n = getattr(ob, start), getattr(ob, count)
            for other in tm.objects:
                o = getattr(other, start)
                if other is not ob and s < o + getattr(other, count) and o < s + n:
                    raise SystemExit('shirts: the tamer objects share corners or normals')
            del pool[s:s + n]
            for other in tm.objects:
                if getattr(other, start) > s:
                    setattr(other, start, getattr(other, start) - n)
            setattr(ob, start, 0)
            setattr(ob, count, 0)
        ob.prims = []
    return model


def wear(model, parts, objects=OBJECTS):
    """A stripped model with a garment's objects put back, for pictures and checks (the game does this when it loads)."""
    tm = model.tmd
    for oi in objects:
        verts, norms, prims = parts[oi]
        ob = tm.objects[oi]
        ob.vert_start, ob.nvert = len(tm.verts), len(verts)
        ob.norm_start, ob.nnorm = len(tm.norms), len(norms)
        tm.verts += verts
        tm.norms += norms
        ob.prims = list(prims)
    return model


def geometry(parts, objects=OBJECTS, gaps=None):
    """A garment's polygons, corners and normals as the game reads them behind a model, and where each object's are.
    Objects with the same corners or normals share them. gaps: per object, bytes left free before its polygons."""
    body, table = bytearray(), []
    spans, at = {}, {}
    for oi in objects:
        body += bytes((gaps or {}).get(oi, 0))
        spans[oi] = len(body)
        for p in parts[oi][2]:
            body += p.raw

    def block(rows):
        data = b''.join(struct.pack('<4h', *r) for r in rows)
        if data not in at:
            at[data] = len(body)
            body.extend(data)
        return at[data]
    for oi in objects:
        verts, norms, prims = parts[oi]
        table.append((block(verts), len(verts), block(norms), len(norms), spans[oi], len(prims)))
    return bytes(body), table


def pixels(idx, rects=RECTS):
    """The rectangles a garment draws out of a texture's pixels, packed two to a byte."""
    out = bytearray()
    for u, v, w, h in rects:
        for y in range(v, v + h):
            for x in range(u, u + w, 2):
                out.append(idx[y * W + x] | idx[y * W + x + 1] << 4)
    return bytes(out)


def pack_recipe(out, at, rec):
    ways, levels, fixed = rec
    out[at:at + 16], out[at + 16:at + 32] = bytes(ways), bytes(levels)
    struct.pack_into('<16H', out, at + 32, *fixed)


def head(table, size, rec=None, drawn=None, rects=RECTS, flags=0):
    """A garment's first sector: the size of its geometry, the object table, the palette recipe and the drawing."""
    out = bytearray(0x800)
    struct.pack_into('<HBB', out, 0, size, len(rects) if drawn else 0, flags)
    for i, row in enumerate(table):
        struct.pack_into('<6H', out, 4 + 12 * i, *row)
    if rec:
        pack_recipe(out, 0x40, rec)
    if drawn:
        for i, (u, v, w, h) in enumerate(rects):
            struct.pack_into('<4B', out, 0x90 + 4 * i, u // 2, v, w // 2, h)
        if 0xA0 + len(drawn) > len(out):
            raise SystemExit('shirts: the drawing does not fit in the first sector')
        out[0xA0:0xA0 + len(drawn)] = drawn
    return bytes(out)


def build(model, texture):
    """Every shirt from the tamer's model and texture: [(name, first sector, geometry, parts, recipe, pixels or None,
    pixels with a backpack's straps or None)]. The last two are not chosen: the original hoodie for another backpack
    and for none."""
    check_free(model)
    out = []
    parts = original(model)
    body, table = geometry(parts)
    own = own_recipe()
    out.append(('original', head(table, len(body), own, flags=OWN | SLEEVES), body, parts, own, None, None))
    room = {TORSO: PACK_BYTES}
    for name, trunk, arms, hood, drawing, follows in STYLES:
        parts = garment(model, trunk, arms, hood)
        body, table = geometry(parts, gaps=room)
        idx, strapped = bytearray(texture.idx), bytearray(texture.idx)
        paint(idx, drawing, False, texture.idx)
        paint(strapped, drawing, True, texture.idx)
        rec = recipe(texture, follows)
        drawn = pixels(idx) + pixels(strapped, (TRUNK,))
        first = bytearray(head(table, len(body), rec, drawn, RECTS + (TRUNK,), ROOM | STRAPS))
        first[2] = len(RECTS)                          # the last rectangle is drawn only under a backpack
        out.append((name, bytes(first), body, parts, rec, idx, strapped))
    parts = bare(model)
    body, table = geometry(parts, gaps=room)
    idx = bytearray(texture.idx)
    unpack(idx)
    out.append(('hoodie for a backpack', head(table, len(body), own, pixels(idx, (TRUNK,)), (TRUNK,), ROOM | OWN | SLEEVES), body,
                parts, own, idx, None))
    idx = bytearray(idx)
    unstrap(idx)
    out.append(('hoodie alone', head(table, len(body), own, pixels(idx, (TRUNK,)), (TRUNK,), ROOM | OWN | SLEEVES), body, parts, own,
                idx, None))
    return out
