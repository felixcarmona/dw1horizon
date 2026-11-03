"""Koromon -> Pichimon (round 2): every object rebuilt from scratch on Koromon's 7-bone skeleton.

Bone 2 = object 0: a smooth 16x7 sphere body (R 76, bottom squashed on the floor y=+68) with a tapered tail
fin at the lower back, two pectoral flaps, three dorsal thorns, a dark cone beak. Bones 3/5 = objects 1/3:
the feeler bases, round tubes from the bone origin (inside the head) to the tip bone (30,-55,79), ended by a
hemisphere that covers the joint. Bones 4/6 = objects 2/4: the feeler tips, aimed more upward, rounded ends.
Texture: three explicit CLUT rows (0 skin, 1 eyes, 2 beak/mouth), every eye and mouth frame repainted,
the tournament sprite corner (224..256, 96..128, row 15) redrawn with row 15's own indices.

Traps found: outward normal = cross(v2-v0, v1-v0) (checked against Koromon: 108/108); quad corners are in
strip order (v0 v1 / v2 v3); tex_import keeps a row's colours verbatim only if the region holds <= 16
distinct 5-bit colours, so everything is snapped to the row's palette before saving; palette_map gives the
uncovered sprite corner row 0, so its indices are rewritten after tex_import.
"""
from lib import *
import numpy as np, math, sys

NAME = 'Pichimon'
b = Baby(NAME, 2)
m = b.m; tmd = m.tmd
R = 74.0                       # head radius (x, z)
RY = 82.0                      # head radius (y)
CY = -8.0                      # head centre y (floor at +68)
GROUND = 68.0
ROW_SKIN, ROW_EYE, ROW_MOUTH = 0, 1, 2

# ---------------------------------------------------------------- palettes (multiples of 8)
def c8(r, g, b_):
    """The colour as the PS1 CLUT stores and the tools decode it (5 bits, low bits replicated): painting with
    these makes tex_import's nearest-colour match exact."""
    return mmd.c15_to_rgba(mmd.rgba_to_c15(r, g, b_))[:3]
SKIN_RAMP = [c8(*c) for c in [(136, 184, 224), (152, 196, 232), (168, 208, 240), (184, 216, 240), (200, 224, 248),
                              (208, 232, 248), (216, 236, 248), (224, 240, 248), (232, 240, 248), (240, 248, 248),
                              (240, 248, 255), (248, 248, 255), (255, 255, 255)]]
LINE = [c8(96, 136, 184), c8(72, 104, 152), c8(176, 200, 224)]          # jaw line, fin edges
PAL_SKIN = SKIN_RAMP + LINE                                               # 16
INK = c8(24, 24, 40); INK2 = c8(72, 80, 104); INK3 = c8(136, 152, 184)
WHITE = c8(255, 255, 255); WHITE2 = c8(224, 232, 240)
RED = c8(224, 32, 32); RED2 = c8(176, 16, 24); RED3 = c8(112, 8, 16); PUPIL = c8(16, 8, 16); GREY = c8(192, 200, 216)
PAL_EYE = [c8(*c) for c in [SKIN_RAMP[6], SKIN_RAMP[8], SKIN_RAMP[10], SKIN_RAMP[12], INK, INK2, INK3, WHITE, WHITE2,
                            RED, RED2, RED3, PUPIL, GREY, (160, 184, 216), (200, 216, 232)]]
BEAK = c8(16, 16, 32); BEAK2 = c8(48, 48, 80); BEAK3 = c8(104, 112, 144); BEAK_HI = c8(152, 160, 192)
PAL_MOUTH = [c8(*c) for c in [SKIN_RAMP[6], SKIN_RAMP[8], SKIN_RAMP[10], SKIN_RAMP[12], BEAK, BEAK2, BEAK3, BEAK_HI,
                              RED, RED2, RED3, (232, 96, 96), LINE[0], LINE[1], (200, 216, 232), (176, 200, 224)]]
PALS = {ROW_SKIN: PAL_SKIN, ROW_EYE: PAL_EYE, ROW_MOUTH: PAL_MOUTH}


def snap(img, pal):
    """Nearest palette colour for every pixel of an RGB float image."""
    p = np.array(pal, float)
    d = ((img[..., None, :] - p[None, None]) ** 2).sum(-1)
    return p[d.argmin(-1)].astype(np.uint8)


# ---------------------------------------------------------------- mesh builder
def unit(v):
    v = np.asarray(v, float); n = np.linalg.norm(v)
    return v / n if n else v


class Part:
    """One TMD object: vertices, one normal per vertex, primitives with per-corner UVs and a CLUT row."""
    def __init__(self):
        self.v, self.n, self.prims = [], [], []

    def add(self, p, n):
        self.v.append(tuple(float(x) for x in p)); self.n.append(tuple(unit(n))); return len(self.v) - 1

    def _wind_ok(self, ids, ref):
        a, b_, c = (np.array(self.v[i]) for i in ids[:3])
        return np.cross(c - a, b_ - a) @ ref >= 0

    def tri(self, ids, uvs, row, outward=None):
        ref = np.asarray(outward, float) if outward is not None else sum(np.array(self.n[i]) for i in ids)
        if not self._wind_ok(ids, ref):
            ids, uvs = [ids[0], ids[2], ids[1]], [uvs[0], uvs[2], uvs[1]]
        self.prims.append((0x34, list(ids), [tuple(int(round(x)) for x in uv) for uv in uvs], row))

    def quad(self, ids, uvs, row, outward=None):
        """ids in strip order: v0 v1 on one edge, v2 v3 on the opposite edge (v0-v2 and v1-v3 joined)."""
        a, b_, c, d = (np.array(self.v[i]) for i in ids)
        if abs(np.cross(b_ - a, c - a)).sum() < 1e-6:        # first triangle degenerate: use the second
            ids, uvs = [ids[1], ids[3], ids[0], ids[2]], [uvs[1], uvs[3], uvs[0], uvs[2]]
        ref = np.asarray(outward, float) if outward is not None else sum(np.array(self.n[i]) for i in ids)
        if not self._wind_ok(ids, ref):
            ids, uvs = [ids[0], ids[2], ids[1], ids[3]], [uvs[0], uvs[2], uvs[1], uvs[3]]
        self.prims.append((0x3C, list(ids), [tuple(int(round(x)) for x in uv) for uv in uvs], row))

    def encoded(self):
        out = []
        for mode, ids, uvs, row in self.prims:
            uvs = [(max(0, min(255, u)), max(0, min(127, v))) for u, v in uvs]
            out.append(mmd.Prim.encode(dict(mode=mode, flag=0, uv=uvs, cba=0x7A00 + (row << 6), tsb=5,
                                            uvpad=[0] * (len(ids) - 2), colors=[], norms=list(ids), verts=list(ids), pad=[])))
        return out


def install(parts):
    """Replace every TMD object with the given Parts (object i rides bone skeleton[obj=i])."""
    tmd.verts, tmd.norms = [], []
    for oi, part in enumerate(parts):
        ob = tmd.objects[oi]
        ob.vert_start, ob.nvert = len(tmd.verts), len(part.v)
        ob.norm_start, ob.nnorm = len(tmd.norms), len(part.n)
        for p in part.v:
            tmd.verts.append(tuple(int(round(x)) for x in p) + (0,))
        for n in part.n:
            tmd.norms.append(tuple(int(round(x * 4096)) for x in n) + (0,))
        ob.prims = part.encoded()


# ---------------------------------------------------------------- texture layout
EYE_DST = (8, 0, 40, 32)                 # + margins 0..8 and 48..56 (skin)
MOUTH_DST = (0, 32, 40, 24)              # + margin 40..56
SKIN_BLOCK = (0, 64, 224, 64)            # lat/long map of the body: u = azimuth (front at 112), v = elevation
GLOSS = (224, 64, 32, 32)                # feeler tube: u around, v along
CHIN = (176, 32, 40, 32)                 # lower-front faces (az -45..45, el -15..-40): the jaw line at 1 unit/texel
EYE_SRC = [(56, 0), (96, 0), (136, 0), (176, 0), (216, 0), (216, 32)]
MOUTH_SRC = [(56, 32), (96, 32), (136, 32)]


def skin_uv(az_deg, el_deg):
    """Body lat/long -> skin block texel. az: 0 front, +x side positive, seam at the back; el: +90 top."""
    u = SKIN_BLOCK[0] + (az_deg + 180.0) / 360.0 * SKIN_BLOCK[2]
    v = SKIN_BLOCK[1] + (90.0 - el_deg) / 180.0 * SKIN_BLOCK[3]
    return (min(SKIN_BLOCK[0] + SKIN_BLOCK[2] - 1, max(SKIN_BLOCK[0], u)), min(SKIN_BLOCK[1] + SKIN_BLOCK[3] - 1, v))


def az_el(p, c=(0.0, CY, 0.0)):
    x, y, z = np.asarray(p, float) - np.asarray(c)
    az = math.degrees(math.atan2(x, -z))
    el = math.degrees(math.atan2(-y, math.hypot(x, z)))
    return az, el


# ---------------------------------------------------------------- body
body = Part()
NSEG = 16
ELEV = [90, 65, 40, 15, 0, -15, -40, -65, -90]
EYE_AZ, EYE_EL = 45.0, 0.0


def squash(y):
    """Flatten the underside against the floor."""
    return y if y < 30 else 30 + (y - 30) * 0.80


def sphere_point(az, el):
    ca, sa = math.cos(math.radians(az)), math.sin(math.radians(az))
    ce, se = math.cos(math.radians(el)), math.sin(math.radians(el))
    p = np.array([R * sa * ce, CY - RY * se, -R * ca * ce])
    n = unit(np.array([sa * ce / R, -se / RY, -ca * ce / R]))
    p[1] = squash(p[1])
    if p[1] > 30: n = unit(n * [1, 0.6, 1])
    return p, n


ring = {}                      # (ri, si) -> vertex id; poles: (0, 0) and (8, 0)
for ri, el in enumerate(ELEV):
    if abs(el) == 90:
        p, n = sphere_point(0, el); ring[(ri, 0)] = body.add(p, n); continue
    for si in range(NSEG):
        az = si * 360.0 / NSEG
        p, n = sphere_point(az, el)
        ring[(ri, si)] = body.add(p, n)


def vid(ri, si):
    return ring[(ri, 0)] if abs(ELEV[ri]) == 90 else ring[(ri, si % NSEG)]


def eye_patch(ri, si):
    """Faces around the eye vertices (ring 4 = el 0, si 2 (az 45) and 14 (az -45)): 2x2 quads each."""
    si %= NSEG
    if ri not in (3, 4): return None
    if si in (1, 2): return 'R'
    if si in (13, 14): return 'L'
    return None


def eye_uv(side, az, el):
    """Planar map of the eye patch into the eye rect (mirrored for the left eye)."""
    d_az = az - EYE_AZ if side == 'R' else -(az + EYE_AZ)
    u = 28 + d_az / 22.5 * 27.5
    v = 16 - (el - EYE_EL) / 15.0 * 15.5
    return (min(55, max(0, u)), min(31, max(0, v)))      # never into the mouth rect below


for ri in range(len(ELEV) - 1):
    for si in range(NSEG):
        ids = [vid(ri, si), vid(ri, si + 1), vid(ri + 1, si), vid(ri + 1, si + 1)]
        az0 = si * 360.0 / NSEG; az1 = az0 + 360.0 / NSEG
        azs = [az0, az1, az0, az1]
        if azs[0] >= 180: azs = [a - 360 for a in azs]
        els = [ELEV[ri], ELEV[ri], ELEV[ri + 1], ELEV[ri + 1]]
        if abs(ELEV[ri]) == 90:
            azs[0] = azs[1] = (az0 + az1) / 2
        if abs(ELEV[ri + 1]) == 90:
            azs[2] = azs[3] = (az0 + az1) / 2
        side = eye_patch(ri, si)
        if side:
            uvs = [eye_uv(side, a, e) for a, e in zip(azs, els)]
            row = ROW_EYE
        elif ri == 5 and si % NSEG in (14, 15, 0, 1):
            uvs = [(CHIN[0] + (a + 45) / 90 * (CHIN[2] - 1), CHIN[1] + (-15 - e) / 25 * (CHIN[3] - 1)) for a, e in zip(azs, els)]
            row = ROW_SKIN
        else:
            uvs = [skin_uv(a, e) for a, e in zip(azs, els)]
            row = ROW_SKIN
        if abs(ELEV[ri]) == 90:
            body.tri([ids[0], ids[2], ids[3]], [uvs[0], uvs[2], uvs[3]], row)
        elif abs(ELEV[ri + 1]) == 90:
            body.tri([ids[0], ids[1], ids[2]], [uvs[0], uvs[1], uvs[2]], row)
        else:
            body.quad(ids, uvs, row)

# ---- tail: lofted rings from inside the lower back to a vertical fin edge
TAIL = [((0, 24, 42), 34, 34), ((0, 42, 66), 20, 25), ((0, 57, 84), 7, 14)]
tail_rings = []
for (cx, cy, cz), rx, ry in TAIL:
    ids = []
    for k in range(8):
        a = k * 2 * math.pi / 8
        p = (cx + rx * math.sin(a), cy - ry * math.cos(a), cz)
        n = unit((math.sin(a) / max(rx, 1) * 20, -math.cos(a) / max(ry, 1) * 20, 0.35))
        ids.append(body.add(p, n))
    tail_rings.append(ids)
tip_top = body.add((0, 52, 100), unit((0, -0.6, 0.8)))
tip_bot = body.add((0, 67, 94), unit((0, 0.6, 0.8)))


def tail_uv(k, s):
    """Tail skin: lower-back region of the lat/long map (bluish), azimuth around the tail."""
    az = 180 - (k / 8.0 - 0.5) * 120
    return skin_uv(az if az <= 180 else az - 360, -35 - s * 18)


for s in range(len(tail_rings) - 1):
    r0, r1 = tail_rings[s], tail_rings[s + 1]
    for k in range(8):
        ids = [r0[k], r0[(k + 1) % 8], r1[k], r1[(k + 1) % 8]]
        uvs = [tail_uv(k, s), tail_uv(k + 1, s), tail_uv(k, s + 1), tail_uv(k + 1, s + 1)]
        body.quad(ids, uvs, ROW_SKIN)
last = tail_rings[-1]
for k in range(8):
    tip = tip_top if k in (6, 7, 0, 1) else tip_bot
    if k in (1, 5):          # the quads that bridge top and bottom of the edge
        ids = [last[k], last[k + 1], tip_top, tip_bot] if k == 1 else [last[k], last[k + 1], tip_bot, tip_top]
        uvs = [tail_uv(k, 2), tail_uv(k + 1, 2), tail_uv(k, 3), tail_uv(k + 1, 3)]
        body.quad(ids, uvs, ROW_SKIN)
    else:
        body.tri([last[k], last[(k + 1) % 8], tip], [tail_uv(k, 2), tail_uv(k + 1, 2), tail_uv(k + .5, 3)], ROW_SKIN)

# ---- pectoral flaps (thin: two faces with opposite normals)
for sx in (1, -1):
    root_a = sphere_point(sx * 118, -8)[0] * 0.97 + [0, CY * 0.03, 0]
    root_b = sphere_point(sx * 140, -22)[0] * 0.97 + [0, CY * 0.03, 0]
    out1 = root_a + np.array([sx * 14, 22, 30])
    out2 = (root_a + root_b) / 2 + np.array([sx * 22, 34, 40])
    out3 = root_b + np.array([sx * 12, 24, 30])
    nrm = unit(np.cross(out3 - root_a, out1 - root_b)) * sx
    if nrm @ np.array([sx, 0.3, 0.2]) < 0: nrm = -nrm
    for sign in (1, -1):
        ids = [body.add(p, nrm * sign) for p in (root_a, root_b, out1, out2, out3)]
        uvs = [skin_uv(sx * 120, -15), skin_uv(sx * 140, -28), skin_uv(sx * 128, -40), skin_uv(sx * 136, -50), skin_uv(sx * 146, -42)]
        body.tri([ids[0], ids[2], ids[3]], [uvs[0], uvs[2], uvs[3]], ROW_SKIN, outward=nrm * sign)
        body.tri([ids[0], ids[3], ids[1]], [uvs[0], uvs[3], uvs[1]], ROW_SKIN, outward=nrm * sign)
        body.tri([ids[1], ids[3], ids[4]], [uvs[1], uvs[3], uvs[4]], ROW_SKIN, outward=nrm * sign)

# ---- dorsal thorns on the back ridge
for el in (48, 24, 0):
    base, n = sphere_point(180, el)
    back = unit(np.array([0, -0.35, 1.0]))
    tipdir = unit(n * 0.6 + back * 0.8)
    pts = [base * 0.985 + [0, 0, 0] + np.array([6, 0, 0]) + n * -1, base * 0.985 + np.array([-6, 0, 0]) + n * -1,
           sphere_point(180, el + 9)[0] * 0.985, sphere_point(180, el - 9)[0] * 0.985]
    apex = base + tipdir * 14
    ids = [body.add(p, unit(n + [sx, 0, 0])) for p, sx in zip(pts, (0.8, -0.8, 0, 0))] + [body.add(apex, tipdir)]
    uv = [skin_uv(180, -50)] * 5
    for a, c in ((0, 2), (2, 1), (1, 3), (3, 0)):
        body.tri([ids[a], ids[c], ids[4]], uv, ROW_SKIN, outward=unit((pts[a] + pts[c]) / 2 - base + tipdir * 0.5))

# ---- beak: a cone at the lower front, mapped into the mouth rect (u along the beak, v around it)
BEAK_EL = -36.0
bbase, bn = sphere_point(0, BEAK_EL)
bdir = unit(np.array([0, 0.76, -0.65]))
bring = []
for k in range(6):
    a = k * 2 * math.pi / 6
    side = np.array([math.sin(a), 0, 0]); up = np.array([0, -math.cos(a), 0])
    off = side * 10 + up * 9
    p = bbase * 0.98 + off - bn * 2
    bring.append((body.add(p, unit(off + bn * 4)), 44 - 11 * math.cos(a)))
bapex = body.add(bbase + bdir * 28, bdir)
for k in range(6):
    (i0, v0), (i1, v1) = bring[k], bring[(k + 1) % 6]
    body.tri([i0, i1, bapex], [(3, v0), (3, v1), (37, 44)], ROW_MOUTH, outward=unit(bdir + np.array(body.v[i0]) - bbase))

# ---------------------------------------------------------------- feelers
BONE4 = np.array([30.0, -55.0, 79.0])          # tip bone origin in the base bone's frame


def tube(part, p0, p1, r0, r1, nseg=8, rings=4, cap=True, uv_v=(64, 88), start_cap=False, ctrl=None):
    """Round tube from p0 to p1 (a quadratic Bezier through ctrl when given), radius r0 -> r1, optional
    hemisphere at p1. Gloss UVs: u around, v along."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    ctrl = (p0 + p1) / 2 if ctrl is None else np.asarray(ctrl, float)
    bez = lambda t: (1 - t) ** 2 * p0 + 2 * t * (1 - t) * ctrl + t ** 2 * p1
    tan = lambda t: unit(2 * (1 - t) * (ctrl - p0) + 2 * t * (p1 - ctrl))
    axis = tan(1.0)
    ref = np.array([0, 0, 1.0]) if abs(axis @ [0, 0, 1]) < 0.9 else np.array([1.0, 0, 0])
    rows = []
    for ri in range(rings):
        t = ri / (rings - 1)
        c = bez(t); r = r0 + (r1 - r0) * t; ax = tan(t)
        e1 = unit(np.cross(ax, ref)); e2 = np.cross(ax, e1)
        ids = []
        for k in range(nseg):
            a = k * 2 * math.pi / nseg
            d = e1 * math.cos(a) + e2 * math.sin(a)
            ids.append((part.add(c + d * r, d), (GLOSS[0] + k * GLOSS[2] / nseg, uv_v[0] + (uv_v[1] - uv_v[0]) * t)))
        rows.append(ids)
    e1 = unit(np.cross(axis, ref)); e2 = np.cross(axis, e1)
    if cap:
        for j, ang in enumerate((35, 65)):
            rr = r1 * math.cos(math.radians(ang)); h = r1 * math.sin(math.radians(ang))
            ids = []
            for k in range(nseg):
                a = k * 2 * math.pi / nseg
                d = e1 * math.cos(a) + e2 * math.sin(a)
                ids.append((part.add(p1 + d * rr + axis * h, unit(d * math.cos(math.radians(ang)) + axis * math.sin(math.radians(ang)))),
                            (GLOSS[0] + k * GLOSS[2] / nseg, uv_v[1] + 3 + 3 * j)))
            rows.append(ids)
        top = (part.add(p1 + axis * r1, axis), (GLOSS[0] + GLOSS[2] / 2, uv_v[1] + 7))
    for a_, b_ in zip(rows, rows[1:]):
        for k in range(nseg):
            (i0, uv0), (i1, uv1), (i2, uv2), (i3, uv3) = a_[k], a_[(k + 1) % nseg], b_[k], b_[(k + 1) % nseg]
            uv1 = (uv1[0] if (k + 1) % nseg else GLOSS[0] + GLOSS[2], uv1[1]); uv3 = (uv1[0], uv3[1])
            part.quad([i0, i1, i2, i3], [uv0, uv1, uv2, uv3], ROW_SKIN)
    if cap:
        lastr = rows[-1]
        for k in range(nseg):
            (i0, uv0), (i1, uv1) = lastr[k], lastr[(k + 1) % nseg]
            uv1 = (uv1[0] if (k + 1) % nseg else GLOSS[0] + GLOSS[2], uv1[1])
            part.tri([i0, i1, top[0]], [uv0, uv1, top[1]], ROW_SKIN)
    if start_cap:
        first = rows[0]
        cen = (part.add(p0 - axis * 2, -axis), (GLOSS[0] + GLOSS[2] / 2, uv_v[0]))
        for k in range(nseg):
            (i0, uv0), (i1, uv1) = first[k], first[(k + 1) % nseg]
            part.tri([i0, cen[0], i1], [uv0, cen[1], uv1], ROW_SKIN, outward=-axis)
    return rows


TIP_DIR = unit(np.array([0.30, -0.80, 0.50]))
TIP_LEN = 66.0
feelers = []
for sx in (1, -1):
    base = Part()
    tube(base, (0, 0, 0), BONE4 * [sx, 1, 1], 9.0, 10.0, rings=5, cap=True, ctrl=np.array([14.0, -16.0, 50.0]) * [sx, 1, 1])
    tip = Part()
    tube(tip, (0, 0, 0), TIP_DIR * [sx, 1, 1] * TIP_LEN, 10.0, 11.5, rings=3, cap=True, uv_v=(80, 86))     # caps end at v 93: the sprite corner starts at 96
    feelers.append((base, tip))

body.v = [(x, min(y, 67.0), z) for x, y, z in body.v]
parts = [body, feelers[0][0], feelers[0][1], feelers[1][0], feelers[1][1]]
install(parts)

# ---------------------------------------------------------------- texture
t = b.tex; t[..., 3] = 255
canvas = np.zeros((128, 256, 3), float)

# skin block: lat/long map. Vertical gradient (white top -> pale blue bottom) + glossy highlight + jaw line.
x0, y0, w, h = SKIN_BLOCK
vv = (np.arange(h)[:, None] / (h - 1)) * np.ones((1, w))
uu = np.ones((h, 1)) * (np.arange(w)[None, :] / (w - 1))
el = 90 - vv * 180; az = (uu * 360 - 180)
base = ramp((el + 90) / 180, [(0, SKIN_RAMP[0]), (0.22, SKIN_RAMP[2]), (0.42, SKIN_RAMP[6]), (0.58, SKIN_RAMP[9]),
                              (0.78, SKIN_RAMP[11]), (1, SKIN_RAMP[12])])
# bluer edges towards the back (rim), a soft gloss highlight on the upper front-left
rim = np.clip((np.abs(az) - 110) / 70, 0, 1) * np.clip((40 - el) / 60, 0, 1)
base = base * (1 - 0.35 * rim[..., None]) + np.array(SKIN_RAMP[0]) * 0.35 * rim[..., None]
gl = np.exp(-(((az + 38) / 34) ** 2 + ((el - 42) / 20) ** 2))
base = base * (1 - gl[..., None]) + np.array(WHITE) * gl[..., None]
canvas[y0:y0 + h, x0:x0 + w] = base
# chin patch: the same gradient for el -15..-40 plus the jaw line from the beak back and up towards the cheek
cx0, cy0, cw, ch = CHIN
S = 4
chin = np.zeros((ch * S, cw * S, 3), np.uint8)
for yy in range(ch * S):
    e = -15 - yy / (ch * S - 1) * 25
    chin[yy] = ramp(np.array([(e + 90) / 180.0]), [(0, SKIN_RAMP[0]), (0.25, SKIN_RAMP[2]), (0.45, SKIN_RAMP[5]), (0.62, SKIN_RAMP[8]),
                                                   (0.8, SKIN_RAMP[11]), (1, SKIN_RAMP[12])])[0]
for sgn in (1, -1):
    pts = []
    for k in range(40):
        s_ = k / 39.0
        a = sgn * (6 + 36 * s_); e = -36 + 11 * s_ * s_
        pts.append((int((a + 45) / 90 * (cw * S - 1)), int((-15 - e) / 25 * (ch * S - 1))))
    cv2.polylines(chin, [np.array(pts, np.int32)], False, LINE[1], int(1.3 * S), cv2.LINE_AA)
canvas[cy0:cy0 + ch, cx0:cx0 + cw] = cv2.resize(chin, (cw, ch), interpolation=cv2.INTER_AREA)
# the underside (el < -60): plain pale blue
# feeler gloss: u around the tube, v along: pale blue sides, white stripe facing front-up
gx, gy, gw, gh = GLOSS
ang = (np.arange(gw)[None, :] / gw) * 2 * np.pi * np.ones((gh, 1))
along = (np.arange(gh)[:, None] / gh) * np.ones((1, gw))
hi = np.exp(-((np.angle(np.exp(1j * (ang - 1.2))) / 0.75) ** 2)) * (0.55 + 0.45 * np.clip(1 - np.abs(along - 0.45) * 1.6, 0, 1))
g = ramp(np.clip(0.55 + 0.45 * np.cos(ang - 1.2), 0, 1), [(0, SKIN_RAMP[1]), (0.5, SKIN_RAMP[5]), (1, SKIN_RAMP[9])])
g = g * (1 - hi[..., None] * 0.9) + np.array(WHITE) * hi[..., None] * 0.9
canvas[gy:gy + gh, gx:gx + gw] = g


def paint_eye(kind):
    """40(+16 margin)x32 eye frame painted at 4x then averaged. u 28 = eye centre, lash on the +u (outer) side."""
    S = 4
    img = np.zeros((32 * S, 56 * S, 3), np.uint8)
    img[:] = SKIN_RAMP[9]
    cx, cy = 28 * S, 16 * S
    ex, ey = int(18.5 * S), int(15.0 * S)            # outline ellipse radii
    cv2.ellipse(img, (cx, cy), (ex, ey), 0, 0, 360, INK, -1)
    if kind in ('open', 'tired', 'angry', 'sleepy'):
        cv2.ellipse(img, (cx, cy), (ex - int(2.5 * S), ey - int(2.5 * S)), 0, 0, 360, WHITE, -1)
        ix, iy = int(13.0 * S), int(11.0 * S)
        cv2.ellipse(img, (cx - 1 * S, cy + 1 * S), (ix, iy), 0, 0, 360, RED, -1)
        cv2.ellipse(img, (cx - 1 * S, cy + 1 * S), (ix, iy), 0, 0, 360, RED2, int(2.5 * S))
        cv2.ellipse(img, (cx - 1 * S, cy + 1 * S), (ix, iy), 0, 0, 360, RED3, int(1.2 * S))
        cv2.circle(img, (cx - 1 * S, cy + 2 * S), int(6.5 * S), PUPIL, -1)
        cv2.circle(img, (cx - 5 * S, cy - 3 * S), int(4.6 * S), WHITE, -1)
        cv2.circle(img, (cx + 5 * S, cy + 7 * S), int(2.2 * S), WHITE2, -1)
        # lids
        if kind == 'tired':
            cv2.ellipse(img, (cx, cy - 9 * S), (ex + S, 11 * S), 0, 0, 360, SKIN_RAMP[9], -1)
            cv2.ellipse(img, (cx, cy - 9 * S), (ex, 11 * S), 0, 15, 165, INK, int(2.2 * S))
        elif kind == 'angry':     # strained: both lids narrow the eye (unhappy, toilet, also the hatching flash)
            cv2.ellipse(img, (cx, cy - 10 * S), (ex + S, 11 * S), 0, 0, 360, SKIN_RAMP[9], -1)
            cv2.ellipse(img, (cx, cy - 10 * S), (ex, 11 * S), 0, 15, 165, INK, int(2.2 * S))
            cv2.ellipse(img, (cx, cy + 12 * S), (ex + S, 9 * S), 0, 0, 360, SKIN_RAMP[9], -1)
            cv2.ellipse(img, (cx, cy + 12 * S), (ex, 9 * S), 0, 195, 345, INK, int(2.0 * S))
        elif kind == 'sleepy':
            cv2.ellipse(img, (cx, cy - 7 * S), (ex + S, 14 * S), 0, 0, 360, SKIN_RAMP[9], -1)
            cv2.ellipse(img, (cx, cy - 7 * S), (ex, 14 * S), 0, 15, 165, INK, int(2.2 * S))
    else:
        img[:] = SKIN_RAMP[9]
        if kind == 'closed':      # asleep: a lid arc bowing down at the outer end
            cv2.ellipse(img, (cx, cy + 8 * S), (ex, 12 * S), 0, 200, 335, INK, int(2.4 * S))
        elif kind == 'happy':     # smiling closed eye: an arc bowing down like a U
            cv2.ellipse(img, (cx, cy - 6 * S), (ex - S, 11 * S), 0, 20, 160, INK, int(2.6 * S))
    if kind in ('open', 'tired', 'sleepy', 'angry'):
        cv2.ellipse(img, (cx, cy), (ex, ey), 0, 195, 345, INK, int(3.5 * S))
    # lash tick at the outer top corner
    if kind in ('open', 'tired', 'sleepy'):
        cv2.line(img, (cx + 13 * S, cy - 9 * S), (cx + 19 * S, cy - 14 * S), INK, int(2.2 * S))
    small = cv2.resize(img, (56, 32), interpolation=cv2.INTER_AREA).astype(float)
    return snap(small, PAL_EYE)


def paint_mouth(opening):
    """40(+16)x24 beak frame: dark beak with the mouth line at v 12 (row 44); opening = red gap height."""
    S = 4
    img = np.zeros((24 * S, 56 * S, 3), np.uint8)
    img[:] = SKIN_RAMP[9]
    # beak from u 0..40: dark, slightly lighter upper ridge
    cv2.rectangle(img, (0, 0), (40 * S, 24 * S), BEAK, -1)
    cv2.rectangle(img, (0, 0), (40 * S, 5 * S), BEAK2, -1)
    cv2.rectangle(img, (0, 2 * S), (40 * S, 4 * S), BEAK3, -1)
    if opening:
        cv2.rectangle(img, (0, (12 - opening) * S), (40 * S, (12 + opening) * S), RED2, -1)
        cv2.rectangle(img, (0, (12 - opening + 1) * S), (40 * S, (12 + opening - 1) * S), RED, -1)
        cv2.rectangle(img, (30 * S, (12 - opening) * S), (40 * S, (12 + opening) * S), RED3, -1)
    else:
        cv2.line(img, (0, 12 * S), (40 * S, 12 * S), BEAK3, int(1.2 * S))
    small = cv2.resize(img, (56, 24), interpolation=cv2.INTER_AREA).astype(float)
    return snap(small, PAL_MOUTH)


def blit(img, x, y):
    canvas[y:y + img.shape[0], x:x + img.shape[1]] = img


e_open = paint_eye('open')
blit(e_open, 0, 0)                                                   # dst + margins (0..56)
for (sx, sy), kind in zip(EYE_SRC, ('angry', 'tired', 'happy', 'sleepy', 'closed', 'open')):
    blit(paint_eye(kind)[:, 8:48], sx, sy)
mo = paint_mouth(0)
blit(mo, 0, 32)
for (sx, sy), op in zip(MOUTH_SRC, (3, 6, 0)):
    blit(paint_mouth(op)[:, 0:40], sx, sy)

# snap every pixel to the palette of the CLUT row palette_map gives it (prims + tex anims decide the rows,
# uncovered pixels take their block's majority): no row ever holds more than its 16 colours
pm = np.array(mmd.palette_map(m, b.tim)).reshape(128, 256)
canvas_u8 = np.zeros((128, 256, 3), np.uint8)
for row in range(16):
    mask = pm == row
    if mask.any():
        canvas_u8[mask] = snap(canvas[mask][None], PALS.get(row, PAL_SKIN))[0]
t[..., :3] = canvas_u8

# ---------------------------------------------------------------- tournament sprite corner (row 15: 0 white, 1 ink, 2 clear)
def sprite(frame):
    g = np.full((15, 15), 2, np.uint8)
    cv2.circle(g, (7, 8), 5, 1, -1); cv2.circle(g, (7, 8), 4, 0, -1)
    for sx in (-1, 1):
        cv2.line(g, (7 + sx * 2, 3), (7 + sx * 4, 0), 1, 1)
    if frame == 2:
        g[7, 5] = 1; g[7, 9] = 1
    else:
        g[7, 5] = 1; g[7, 9] = 1; g[8, 5] = 1; g[8, 9] = 1
    g[10, 7] = 1; g[11, 7] = 1
    return g


SPRITE = np.zeros((32, 32), np.uint8) + 2
for f, (sx, sy) in enumerate(((0, 0), (16, 0), (0, 16), (16, 16))):
    SPRITE[sy:sy + 15, sx:sx + 15] = sprite(f)


def save():
    spec = b.save()
    idx = np.frombuffer(bytes(b.tim.idx), np.uint8).reshape(128, 256).copy()
    idx[96:128, 224:256] = SPRITE
    b.tim.idx = bytearray(idx.tobytes())
    open(os.path.join(OUT, NAME + '.TIM'), 'wb').write(b.tim.to_bytes())
    return spec


spec = save()
# ---------------------------------------------------------------- checks
nb = len(m.build())
bad = 0
for oi, ob in enumerate(tmd.objects):
    vs = b.verts(oi); ns = np.array([n[:3] for n in m.tmd.obj_norms(oi)], float)
    for p in ob.prims:
        d = p.decode(); ids = d['verts']
        a, b_, c = [vs[k] for k in ids[:3]]
        g = np.cross(c - a, b_ - a)
        if g @ sum(ns[k] for k in d['norms'][:3]) < 0: bad += 1
print(f'# MMD {nb} bytes, objects', [(ob.nvert, len(ob.prims)) for ob in tmd.objects], 'winding-vs-normal disagreements', bad,
      'body y max', max(v[1] for v in tmd.verts[:tmd.objects[0].nvert]), file=sys.stderr)
print(spec)
