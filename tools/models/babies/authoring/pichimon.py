"""Koromon -> Pichimon (round 3c): every object rebuilt from scratch on Koromon's 7-bone skeleton.

Bone 2 = object 0: a smooth comma body. The head is a 24-segment sphere (R 46, centre y -3) down to el -20; below
it lathe rings bulge forward under the mouth, sweep back and down to a small contact ring on the floor (y +68) and
taper along a Bezier into a plain rounded tail tip that curves up. Normals are computed from the lathe grid
(finite differences), so the game's Gouraud shading is smooth. No beak: a small painted mouth on the face patch
(smile when closed, a small dark open mouth with a pink tongue in the open frames). Two paddle pectoral fins,
three dorsal thorns, eyes on 3x3 sphere patches (az +-45, el +-20) whose background repeats the body's own
skin gradient so the patch does not read as a box.
Bones 3/5 = objects 1/3: feeler bases, tapered round tubes from near the forehead centre line (inside the head)
curving up and back (the tip bones sit 163 units above the floor: far too high for a Fresh, so objects 2/4 are
collapsed and the feelers are rigid rods that still wave with bone 3).
Texture: three explicit CLUT rows (0 skin, 1 eyes, 2 mouth), every eye and mouth frame repainted, the tournament
sprite corner (224..256, 96..128, row 15) redrawn with row 15's own indices.

Traps found: outward normal = cross(v2-v0, v1-v0) (checked against Koromon: 108/108); quad corners are in
strip order (v0 v1 / v2 v3); tex_import keeps a row's colours only if the region holds <= 16 distinct colours and
matches in decoded (low bits replicated) space, so every colour is a c15 round trip and every pixel is snapped
to the palette of the row palette_map gives it; a degenerate UV triangle marks no pixel, so its texels would be
quantised with another row (checked at the end); palette_map gives the uncovered sprite corner row 0, so its
indices are rewritten after tex_import. No double-sided flag: thin fins are two single-sided layers.
"""
from lib import *
import numpy as np, math, sys

NAME = 'Pichimon'
b = Baby(NAME, 2)
m = b.m; tmd = m.tmd
R = 46.0                       # head radius (Fresh size: body ~117 tall with the tail, whole model ~151)
CY = -3.0                      # head centre y (floor at +68)
GROUND = 68.0
ROW_SKIN, ROW_EYE, ROW_MOUTH = 0, 1, 2


# ---------------------------------------------------------------- palettes
def c8(r, g, b_):
    """The colour as the PS1 CLUT stores and the tools decode it (5 bits, low bits replicated): painting with
    these makes tex_import's nearest-colour match exact."""
    return mmd.c15_to_rgba(mmd.rgba_to_c15(r, g, b_))[:3]


SKIN_RAMP = [c8(*c) for c in [(144, 184, 224), (168, 200, 232), (184, 212, 240), (200, 224, 248), (208, 228, 248),
                              (216, 232, 248), (224, 236, 248), (232, 240, 248), (240, 244, 248), (240, 248, 255),
                              (248, 248, 255), (248, 252, 255), (255, 255, 255)]]
LINE = [c8(104, 144, 192), c8(72, 104, 152), c8(120, 160, 200)]          # fin edge lines
PAL_SKIN = SKIN_RAMP + LINE                                               # 16
INK = c8(24, 24, 40); INK2 = c8(72, 80, 104); INK3 = c8(136, 152, 184)
WHITE = c8(255, 255, 255); WHITE2 = c8(224, 232, 240)
RED = c8(184, 16, 42); RED2 = c8(120, 8, 32); RED3 = c8(80, 16, 32); PUPIL = c8(16, 8, 16)
EYE_COLOURS = [INK, INK2, INK3, WHITE, WHITE2, RED, RED2, RED3, PUPIL]
MOUTH = c8(96, 40, 48); MOUTH2 = c8(48, 24, 40); PINK = c8(232, 144, 160); PINK2 = c8(200, 104, 120)
MOUTH_COLOURS = [INK, INK2, MOUTH, MOUTH2, PINK, PINK2, LINE[1]]


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
MOUTH_DST = (0, 32, 40, 24)              # the face patch under the eyes (az -22.5..22.5), u 0 = left
SKIN_BLOCK = (0, 64, 224, 64)            # lat/long map of the body: u = azimuth (front at 112), v = elevation
GLOSS = (224, 64, 32, 32)                # feeler tube: u around, v along
FIN = (176, 32, 40, 32)                  # pectoral fin paddle: u along the fin, v across (trailing edge at high v)
EYE_SRC = [(56, 0), (96, 0), (136, 0), (176, 0), (216, 0), (216, 32)]
MOUTH_SRC = [(56, 32), (96, 32), (136, 32)]
EYE_EL = (20.0, -20.0)                   # elevation band of the eye patch (top, bottom)
MOUTH_EL = (-20.0, None)                 # top elevation of the mouth patch; the bottom is the first lower ring


def skin_uv(az_deg, el_deg):
    """Body lat/long -> skin block texel. az: 0 front, +x side positive, seam at the back; el: +90 top."""
    u = SKIN_BLOCK[0] + (az_deg + 180.0) / 360.0 * SKIN_BLOCK[2]
    v = SKIN_BLOCK[1] + (90.0 - el_deg) / 180.0 * SKIN_BLOCK[3]
    return (min(SKIN_BLOCK[0] + SKIN_BLOCK[2] - 1, max(SKIN_BLOCK[0], u)), min(SKIN_BLOCK[1] + SKIN_BLOCK[3] - 1, v))


def az_el(p):
    x, y, z = np.asarray(p, float) - np.array([0.0, CY, 0.0])
    return math.degrees(math.atan2(x, -z)), math.degrees(math.atan2(-y, math.hypot(x, z)))


# ---------------------------------------------------------------- body
body = Part()
NSEG = 24
AZ0 = 360.0 / NSEG / 2                                     # vertex azimuths are offset half a step: az 0 and 45 are face centres
HEAD_EL = [90, 72, 54, 36, 20, 7, -7, -20]                 # sphere rings (elevation)
# Below the sphere the body is a round tube along a cubic spine (y, z): down from the head centre, back under the
# belly, then up into the tail. Each ring lies in the plane perpendicular to the spine, so the tail stays round.
SPINE = [(12.7, 0.0), (48.0, 3.0), (66.0, 44.0), (36.0, 90.0)]     # lowest belly point 70.7 -> clamped to the floor
TUBE_S = [0.19, 0.30, 0.42, 0.53, 0.64, 0.76, 0.88, 1.0]
TUBE_R = [39.0, 35.0, 29.0, 22.0, 15.0, 9.5, 5.5, 3.0]
EYE_AZ = 45.0


def spine(sv):
    (y0, z0), (y1, z1), (y2, z2), (y3, z3) = SPINE
    a, b_ = (1 - sv) ** 3, 3 * sv * (1 - sv) ** 2
    c, d = 3 * sv ** 2 * (1 - sv), sv ** 3
    pos = (a * y0 + b_ * y1 + c * y2 + d * y3, a * z0 + b_ * z1 + c * z2 + d * z3)
    tan = (3 * (1 - sv) ** 2 * (y1 - y0) + 6 * (1 - sv) * sv * (y2 - y1) + 3 * sv ** 2 * (y3 - y2),
           3 * (1 - sv) ** 2 * (z1 - z0) + 6 * (1 - sv) * sv * (z2 - z1) + 3 * sv ** 2 * (z3 - z2))
    n = math.hypot(*tan) or 1.0
    return pos, (tan[0] / n, tan[1] / n)


RINGS = [(None,)] + [('sphere', el) for el in HEAD_EL[1:]] + [('tube', sv, r) for sv, r in zip(TUBE_S, TUBE_R)]
NRING = len(RINGS)


def ring_pos(ri, az):
    """Vertex of ring ri at azimuth az (0 front, +x positive)."""
    sa, ca = math.sin(math.radians(az)), math.cos(math.radians(az))
    kind = RINGS[ri][0]
    if kind == 'sphere':
        el = RINGS[ri][1]
        ce, se = math.cos(math.radians(el)), math.sin(math.radians(el))
        return np.array([R * sa * ce, CY - R * se, -R * ca * ce])
    _, sv, r = RINGS[ri]
    (cy, cz), (ty, tz) = spine(sv)
    k = min(1.0, max(0.0, (sv - TUBE_S[0]) / 0.4))   # the upper rings stay horizontal (no fold against the sphere), the tail's tilt with the spine
    ty, tz = (1 - k) * 1.0 + k * ty, k * tz; nrm = math.hypot(ty, tz); ty, tz = ty / nrm, tz / nrm
    q = np.array([0.0, tz, -ty])                    # az 0 direction: the axis turned -90 deg (front -> down -> back)
    return np.array([r * sa, cy, cz]) + r * ca * q


def vaz(si):
    return AZ0 + si * 360.0 / NSEG


# positions first, then normals from the lattice (finite differences), then the vertices
POS = {}
for ri in range(1, NRING):
    for si in range(NSEG):
        POS[(ri, si)] = ring_pos(ri, vaz(si))
pole = np.array([0.0, CY - R, 0.0])
(ty_, tz_), (tty, ttz) = spine(1.0)
tdir = unit(np.array([0.0, tty, ttz]))
tail_tip = np.array([0.0, ty_, tz_]) + tdir * 3.0


def ring_centre(ri):
    return np.mean([POS[(ri, s)] for s in range(NSEG)], 0)


def lattice_normal(ri, si):
    t_az = POS[(ri, (si + 1) % NSEG)] - POS[(ri, (si - 1) % NSEG)]
    up = POS[(ri - 1, si)] if ri > 1 else pole
    dn = POS[(ri + 1, si)] if ri < NRING - 1 else tail_tip
    t_ring = dn - up
    n = unit(np.cross(t_ring, t_az))
    if n @ (POS[(ri, si)] - ring_centre(ri)) < 0: n = -n
    return n


ring = {(0, 0): body.add(pole, (0, -1, 0))}
for ri in range(1, NRING):
    for si in range(NSEG):
        ring[(ri, si)] = body.add(POS[(ri, si)], lattice_normal(ri, si))
tail_c = body.add(tail_tip, tdir)


def vid(ri, si):
    return ring[(0, 0)] if ri == 0 else ring[(ri, si % NSEG)]


EYE_FACES = {'R': [1, 2, 3], 'L': [19, 20, 21]}            # face si whose azimuth range lies in +-(22.5..67.5)
MOUTH_FACES = [22, 23, 0]                                  # az -22.5..22.5
EYE_RINGS = (4, 5, 6)                                      # faces between el 20 and -20
MOUTH_RING = 7                                             # faces between el -20 and the first lower ring


def eye_uv(side, az, el):
    """Planar map of the eye patch into the eye rect (mirrored for the left eye)."""
    d_az = az - EYE_AZ if side == 'R' else -(az + EYE_AZ)
    u = 28 + d_az / 22.5 * 27.5
    v = 16 - el / 20.0 * 15.5
    return (min(55, max(0, u)), min(31, max(0, v)))      # never into the mouth rect below


mouth_el_bottom = az_el(ring_pos(MOUTH_RING + 1, 0))[1]


def mouth_uv(az, el):
    u = (az + 22.5) / 45.0 * 39
    v = 32 + (MOUTH_EL[0] - el) / (MOUTH_EL[0] - mouth_el_bottom) * 23
    return (min(39, max(0, u)), min(55, max(32, v)))


for ri in range(NRING - 1):
    for si in range(NSEG):
        ids = [vid(ri, si), vid(ri, si + 1), vid(ri + 1, si), vid(ri + 1, si + 1)]
        az0 = vaz(si); az1 = vaz(si + 1)
        azs = [az0, az1, az0, az1]
        if azs[0] >= 180: azs = [a - 360 for a in azs]
        if ri == 0: azs[0] = azs[1] = (az0 + az1) / 2
        els = [az_el(body.v[i])[1] for i in ids]
        row = ROW_SKIN
        side = 'R' if (ri in EYE_RINGS and si in EYE_FACES['R']) else 'L' if (ri in EYE_RINGS and si in EYE_FACES['L']) else None
        if side:
            uvs = [eye_uv(side, a, e) for a, e in zip(azs, els)]; row = ROW_EYE
        elif ri == MOUTH_RING and si in MOUTH_FACES:
            uvs = [mouth_uv(a, e) for a, e in zip(azs, els)]; row = ROW_MOUTH
        else:
            uvs = [skin_uv(a, e) for a, e in zip(azs, els)]
        if ri == 0:
            body.tri([ids[0], ids[2], ids[3]], [uvs[0], uvs[2], uvs[3]], row)
        else:
            body.quad(ids, uvs, row)
# rounded tail tip
for si in range(NSEG):
    i0, i1 = vid(NRING - 1, si), vid(NRING - 1, si + 1)
    body.tri([i0, i1, tail_c], [skin_uv(170, -50), skin_uv(172, -50), skin_uv(171, -52)], ROW_SKIN, outward=tdir)

# ---- pectoral fins: paddles at the lower sides, two single-sided layers each
FIN_OUTLINE = [(0, -9), (0, 9), (12, -11), (12, 11), (24, -9), (24, 9), (34, -2.5), (34, 2.5)]   # (length, width)
for sx in (1, -1):
    rc = np.array([37.0 * sx, 30.0, 2.0])
    w = unit(np.array([-6.0 * sx, 26.0, 12.0]))                  # root edge direction (down and back)
    d0 = np.array([0.5 * sx, 0.62, 0.58]); d = unit(d0 - (d0 @ w) * w)
    n = unit(np.cross(d, w))
    if n @ np.array([sx, 0, 0]) < 0: n = -n
    for layer in (1, -1):
        ids = []
        for k, (ln, wd) in enumerate(FIN_OUTLINE):
            p = rc + d * ln + w * wd + n * layer * 1.0
            nn = unit(n * layer + d * (0.3 if ln >= 34 else 0.0))
            ids.append(body.add(p, nn))
        uvs = [(FIN[0] + 1 + ln / 34 * (FIN[2] - 3), FIN[1] + 1 + (wd + 11) / 22 * (FIN[3] - 3)) for ln, wd in FIN_OUTLINE]
        for k in range(0, 6, 2):
            body.quad([ids[k], ids[k + 1], ids[k + 2], ids[k + 3]], [uvs[k], uvs[k + 1], uvs[k + 2], uvs[k + 3]], ROW_SKIN, outward=n * layer)

# ---- dorsal thorns on the upper back
for el in (55, 35, 15):
    ce, se = math.cos(math.radians(el)), math.sin(math.radians(el))
    base = np.array([0, CY - R * se, R * ce]); n = unit([0, -se, ce])
    back_up = unit(np.array([0, -0.45, 1.0]))
    tipdir = unit(n * 0.5 + back_up * 0.85)
    along = unit(np.cross(np.array([1.0, 0, 0]), n))
    pts = [base + np.array([3, 0, 0]) - n * 1.5, base - np.array([3, 0, 0]) - n * 1.5, base + along * 3.5 - n * 1.5, base - along * 3.5 - n * 1.5]
    apex = base + tipdir * 9
    ids = [body.add(p, unit(n + [s, 0, 0])) for p, s in zip(pts, (0.8, -0.8, 0, 0))] + [body.add(apex, tipdir)]
    uv = [skin_uv(180, 20)] * 5
    for a_, c_ in ((0, 2), (2, 1), (1, 3), (3, 0)):
        body.tri([ids[a_], ids[c_], ids[4]], uv, ROW_SKIN, outward=unit((pts[a_] + pts[c_]) / 2 - base + tipdir * 0.5))
print('# lowest body point before the floor clamp', max(y for x, y, z in body.v), file=sys.stderr)
body.v = [(x, min(y, GROUND), z) for x, y, z in body.v]

# ---------------------------------------------------------------- feelers
BONE4 = np.array([30.0, -55.0, 79.0])          # tip bone origin in the base bone's frame


def tube(part, p0, p1, r0, r1, nseg=8, rings=4, cap=True, uv_v=(64, 88), ctrl=None, cap_r=None):
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
    rc = r1 if cap_r is None else cap_r
    if cap:
        for j, ang in enumerate((35, 65)):
            rr = rc * math.cos(math.radians(ang)); h = rc * math.sin(math.radians(ang))
            ids = []
            for k in range(nseg):
                a = k * 2 * math.pi / nseg
                d = e1 * math.cos(a) + e2 * math.sin(a)
                ids.append((part.add(p1 + d * rr + axis * h, unit(d * math.cos(math.radians(ang)) + axis * math.sin(math.radians(ang)))),
                            (GLOSS[0] + k * GLOSS[2] / nseg, uv_v[1] + 3 + 3 * j)))
            rows.append(ids)
        top = (part.add(p1 + axis * rc, axis), (GLOSS[0] + GLOSS[2] / 2, uv_v[1] + 7))
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
    return rows


# The tip bones (4/6) sit at world y -164, far above a Fresh-sized head: using them would make the model 170+
# tall. The feelers are therefore rigid rods on the base bones (3/5), which still wave in the condition idles and
# the reactions; objects 2/4 are collapsed to a point. Bone 3's origin lies ~15 units outside the small head, so
# the rod's axis is aimed through it to keep the root from sliding when the bone turns.
B3 = np.array([25.0, -40.0, -41.0])                         # base bone origin in body space
FEELER = [np.array([10.0, -10.0, -14.0]), np.array([20.0, -50.0, -36.0]), np.array([27.0, -80.0, -3.0])]   # body space Bezier
feelers = []
for sx in (1, -1):
    base = Part()
    p0, p1, p2 = [(q * [sx, 1, 1]) - B3 * [sx, 1, 1] for q in FEELER]
    tube(base, p0, p2, 6.5, 4.5, rings=5, cap=True, ctrl=p1, uv_v=(64, 86))
    tip = Part()                                   # collapsed, 40 units under its bone so the rest bbox stays honest
    for _ in range(3): tip.add((0, 40, 0), (0, -1, 0))
    tip.prims.append((0x34, [0, 1, 2], [(GLOSS[0], GLOSS[1])] * 3, ROW_SKIN))
    feelers.append((base, tip))

parts = [body, feelers[0][0], feelers[0][1], feelers[1][0], feelers[1][1]]
install(parts)

# ---------------------------------------------------------------- texture
t = b.tex; t[..., 3] = 255
canvas = np.zeros((128, 256, 3), float)
canvas[:] = SKIN_RAMP[9]

# skin block: lat/long map. Ice white on top, pale blue lower half and back, a big gloss oval upper-left.
SKIN_STOPS = [(0, SKIN_RAMP[0]), (0.2, SKIN_RAMP[1]), (0.38, SKIN_RAMP[3]), (0.5, SKIN_RAMP[6]),
              (0.62, SKIN_RAMP[9]), (0.78, SKIN_RAMP[11]), (1, SKIN_RAMP[12])]
x0, y0, w, h = SKIN_BLOCK
vv = (np.arange(h)[:, None] / (h - 1)) * np.ones((1, w))
uu = np.ones((h, 1)) * (np.arange(w)[None, :] / (w - 1))
el = 90 - vv * 180; az = (uu * 360 - 180)
base = ramp((el + 90) / 180, SKIN_STOPS)
rim = np.clip((np.abs(az) - 100) / 80, 0, 1) * np.clip((50 - el) / 70, 0, 1)
base = base * (1 - 0.4 * rim[..., None]) + np.array(SKIN_RAMP[1]) * 0.4 * rim[..., None]
gl = np.exp(-(((az + 40) / 30) ** 2 + ((el - 48) / 14) ** 2))
gl = np.clip(gl * 1.6, 0, 1)
base = base * (1 - gl[..., None]) + np.array(WHITE) * gl[..., None]
canvas[y0:y0 + h, x0:x0 + w] = base


def skin_at(el_deg):
    """The body's own skin colour (snapped) at an elevation, for the face patches' backgrounds."""
    c = ramp(np.array([(el_deg + 90) / 180.0]), SKIN_STOPS)[0]
    return tuple(int(x) for x in snap(c[None, None], PAL_SKIN)[0, 0])


# feeler gloss: u around the tube, v along: pale blue sides, white stripe facing front-up
gx, gy, gw, gh = GLOSS
ang = (np.arange(gw)[None, :] / gw) * 2 * np.pi * np.ones((gh, 1))
along = (np.arange(gh)[:, None] / gh) * np.ones((1, gw))
hi = np.exp(-((np.angle(np.exp(1j * (ang - 1.2))) / 0.75) ** 2)) * (0.55 + 0.45 * np.clip(1 - np.abs(along - 0.45) * 1.6, 0, 1))
g = ramp(np.clip(0.55 + 0.45 * np.cos(ang - 1.2), 0, 1), [(0, SKIN_RAMP[1]), (0.5, SKIN_RAMP[5]), (1, SKIN_RAMP[9])])
g = g * (1 - hi[..., None] * 0.9) + np.array(WHITE) * hi[..., None] * 0.9
canvas[gy:gy + gh, gx:gx + gw] = g
# pectoral fin paddle: pale blue, bluer towards the trailing edge, an edge line with two scallops
fx, fy, fw, fh = FIN
S = 4
fin = np.zeros((fh * S, fw * S, 3), np.uint8)
for yy in range(fh * S):
    fin[yy] = ramp(np.array([yy / (fh * S - 1)]), [(0, SKIN_RAMP[9]), (0.5, SKIN_RAMP[6]), (1, SKIN_RAMP[2])])[0]
edge = [(1 * S, (fh - 3) * S), (12 * S, (fh - 2) * S), (16 * S, (fh - 5) * S), (24 * S, (fh - 2) * S), (29 * S, (fh - 6) * S), (fw - 2 * S, (fh - 8) * S)]
cv2.polylines(fin, [np.array(edge, np.int32)], False, LINE[1], int(1.3 * S), cv2.LINE_AA)
cv2.line(fin, (2 * S, 2 * S), ((fw - 2) * S, 6 * S), LINE[2], S, cv2.LINE_AA)
canvas[fy:fy + fh, fx:fx + fw] = cv2.resize(fin, (fw, fh), interpolation=cv2.INTER_AREA)


def band_bg(rows, cols, el_top, el_bottom, S):
    """Background of a face patch: the body's skin gradient over its elevation band (so the patch matches)."""
    bg = np.zeros((rows * S, cols * S, 3), np.uint8)
    for yy in range(rows * S):
        bg[yy] = skin_at(el_top + (el_bottom - el_top) * yy / (rows * S - 1))
    return bg


EYE_BG = band_bg(32, 56, EYE_EL[0], EYE_EL[1], 4)
MOUTH_BG = band_bg(24, 40, MOUTH_EL[0], mouth_el_bottom, 4)
PAL_EYE = sorted(set(map(tuple, EYE_BG.reshape(-1, 3).tolist()))) + EYE_COLOURS
PAL_MOUTH = sorted(set(map(tuple, MOUTH_BG.reshape(-1, 3).tolist()))) + MOUTH_COLOURS
assert len(PAL_EYE) <= 16 and len(PAL_MOUTH) <= 16, (len(PAL_EYE), len(PAL_MOUTH))
PALS = {ROW_SKIN: PAL_SKIN, ROW_EYE: PAL_EYE, ROW_MOUTH: PAL_MOUTH}


def lid(img, mask_fn):
    """Cover part of the eye with the background again (a lid), through a mask drawn by mask_fn."""
    mask = np.zeros(img.shape[:2], np.uint8); mask_fn(mask)
    img[mask > 0] = EYE_BG[mask > 0]


def paint_eye(kind):
    """40(+16 margin)x32 eye frame painted at 4x then averaged. u 28 = eye centre, lash on the +u (outer) side."""
    S = 4
    img = EYE_BG.copy()
    cx, cy = 28 * S, 16 * S
    ex, ey = int(19.5 * S), int(13.5 * S)            # outline ellipse radii
    if kind in ('open', 'tired', 'angry', 'sleepy'):
        cv2.ellipse(img, (cx, cy), (ex, ey), 0, 0, 360, INK, -1)
        cv2.ellipse(img, (cx, cy), (ex - int(2.5 * S), ey - int(2.5 * S)), 0, 0, 360, WHITE, -1)
        ix, iy = int(14.0 * S), int(10.0 * S)
        cv2.ellipse(img, (cx - 1 * S, cy + 1 * S), (ix, iy), 0, 0, 360, RED, -1)
        cv2.ellipse(img, (cx - 1 * S, cy + 1 * S), (ix, iy), 0, 0, 180, RED2, -1)      # darker lower half
        cv2.ellipse(img, (cx - 1 * S, cy + 1 * S), (ix - 3 * S, iy - 3 * S), 0, 0, 180, RED, -1)
        cv2.ellipse(img, (cx - 1 * S, cy + 1 * S), (ix, iy), 0, 0, 360, RED3, int(1.2 * S))
        cv2.circle(img, (cx - 1 * S, cy + 2 * S), int(7.5 * S), PUPIL, -1)
        cv2.circle(img, (cx - 6 * S, cy - 2 * S), int(4.8 * S), WHITE, -1)
        cv2.circle(img, (cx + 5 * S, cy + 6 * S), int(2.4 * S), WHITE2, -1)
        if kind == 'tired':        # half lid, a sliver of iris below
            lid(img, lambda mk: cv2.ellipse(mk, (cx, cy - 8 * S), (ex + S, 11 * S), 0, 0, 360, 255, -1))
            cv2.ellipse(img, (cx, cy - 8 * S), (ex, 11 * S), 0, 15, 165, INK, int(2.6 * S))
        elif kind == 'angry':      # strained: both lids narrow the eye (unhappy, toilet, the hatching flash)
            lid(img, lambda mk: cv2.ellipse(mk, (cx, cy - 10 * S), (ex + S, 11 * S), 0, 0, 360, 255, -1))
            cv2.ellipse(img, (cx, cy - 10 * S), (ex, 11 * S), 0, 15, 165, INK, int(2.6 * S))
            lid(img, lambda mk: cv2.ellipse(mk, (cx, cy + 12 * S), (ex + S, 9 * S), 0, 0, 360, 255, -1))
            cv2.ellipse(img, (cx, cy + 12 * S), (ex, 9 * S), 0, 195, 345, INK, int(2.2 * S))
        elif kind == 'sleepy':     # nearly closed
            lid(img, lambda mk: cv2.ellipse(mk, (cx, cy - 6 * S), (ex + S, 14 * S), 0, 0, 360, 255, -1))
            cv2.ellipse(img, (cx, cy - 6 * S), (ex, 14 * S), 0, 15, 165, INK, int(2.8 * S))
        if kind == 'open':
            cv2.ellipse(img, (cx, cy), (ex, ey), 0, 195, 345, INK, int(3.8 * S))      # thick upper lid
    else:
        if kind == 'closed':      # asleep: a bold lid arc bowing down at the outer end
            cv2.ellipse(img, (cx, cy + 8 * S), (ex - S, 12 * S), 0, 200, 335, INK, int(3.6 * S))
        elif kind == 'happy':     # smiling closed eye: a bold U arc
            cv2.ellipse(img, (cx, cy - 7 * S), (ex - 2 * S, 12 * S), 0, 20, 160, INK, int(3.8 * S))
    if kind in ('open', 'tired', 'sleepy', 'closed', 'happy'):      # lash tick at the outer top corner
        cv2.line(img, (cx + 14 * S, cy - 9 * S), (cx + 20 * S, cy - 14 * S), INK, int(2.6 * S))
    small = cv2.resize(img, (56, 32), interpolation=cv2.INTER_AREA).astype(float)
    return snap(small, PAL_EYE)


def paint_mouth(opening):
    """40x24 face patch under the eyes (u 20 = centre line): a small smile when closed, a small dark open
    mouth with a pink tongue when opening > 0 (its half-height in texels). Painted, no geometry."""
    S = 4
    img = MOUTH_BG.copy()
    cx, cy = 20 * S, 7 * S
    if opening:
        hw = (5 + opening) * S
        cv2.ellipse(img, (cx, cy + opening * S // 2), (hw, opening * S), 0, 0, 360, INK, -1)
        cv2.ellipse(img, (cx, cy + opening * S // 2), (hw - S, opening * S - S), 0, 0, 360, MOUTH2, -1)
        cv2.ellipse(img, (cx, cy + opening * S), (hw - 2 * S, max(S, opening * S - 2 * S)), 0, 180, 360, PINK, -1)
    else:
        cv2.ellipse(img, (cx, cy - 2 * S), (7 * S, 4 * S), 0, 20, 160, INK, int(1.6 * S), cv2.LINE_AA)
    small = cv2.resize(img, (40, 24), interpolation=cv2.INTER_AREA).astype(float)
    return snap(small, PAL_MOUTH)


def blit(img, x, y):
    canvas[y:y + img.shape[0], x:x + img.shape[1]] = img


blit(paint_eye('open'), 0, 0)                                        # dst + margins (0..56)
for (sx, sy), kind in zip(EYE_SRC, ('angry', 'tired', 'happy', 'sleepy', 'closed', 'open')):
    blit(paint_eye(kind)[:, 8:48], sx, sy)
blit(paint_mouth(0), 0, 32)
for (sx, sy), op in zip(MOUTH_SRC, (3, 5, 0)):
    blit(paint_mouth(op), sx, sy)

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
    g[10, 6] = 1; g[10, 7] = 1; g[10, 8] = 1
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
        if g @ sum(ns[k] for k in d['norms'][:3]) < 0:
            bad += 1
            if bad <= 3: print('#   winding/normal disagreement obj', oi, 'verts', ids, [tuple(int(q) for q in vs[k]) for k in ids[:3]], file=sys.stderr)
# every texel a primitive samples must carry that primitive's CLUT row (a degenerate UV triangle marks nothing,
# and its pixels would then be quantised with another row's palette)
pm_chk = np.array(mmd.palette_map(m, b.tim)).reshape(128, 256)
thin = 0
for oi, ob in enumerate(tmd.objects):
    if oi in (2, 4): continue
    for p in ob.prims:
        d = p.decode(); row = (d['cba'] >> 6) - 488; uv = d['uv']
        pts_ = list(uv) + [(sum(u for u, v in uv) / len(uv), sum(v for u, v in uv) / len(uv))]
        for u, v in pts_:
            if pm_chk[min(127, int(v)), min(255, int(u))] != row: thin += 1; break
allv = np.array([v[:3] for v in tmd.verts[:tmd.objects[0].nvert]])
print(f'# MMD {nb} bytes, objects', [(ob.nvert, len(ob.prims)) for ob in tmd.objects], 'winding-vs-normal disagreements', bad,
      'prims sampling another row', thin, 'body bbox', allv.min(0).tolist(), allv.max(0).tolist(), file=sys.stderr)
print(spec)
