"""Yuramon (type 43) -> Nyokimon, round 2: the geometry and the texture page are rebuilt from scratch.

Shape: a teardrop lathe (16 segments, 11 rings; the profile is measured from the reference, widest at 35 % of the
height, a thin neck over the top 18 %) pinched into a leaning stem, two curved double-sided leaves (the long nearly
horizontal one to the right, the short steep one to the left, as in the art), all on object 0 (bone 2, the body).
The tuft bones 3..8 swing 15-100 degrees in the donor's animations and their pivots sit 85 units from the sprout's
fork, so anything on them either flaps or detaches: objects 1..6 are reduced to one degenerate triangle each.
The clear skin is baked into the body texture (white neck cone, pale bottom rim, a pale gap at the lower left and a
narrower one up the right side that whitens into the highlight near the neck); the fuzz is short low-contrast hair
strokes radiating from the face centre, darkest around the mouth, greyer towards the top, with hairs sticking out into
the pale zones. The eyes and mouths are painted in the donor's nine 24x24 face frames (dst 0,0 and the 8 sources the
texture instructions copy from); the frame is the right half of the face, mirrored.

Traps found: the engine culls back faces (front = clockwise on screen with y down: cross(v1-v0, v2-v0) . n_out < 0),
animstudio does not; palette_map hands uncovered texels to row 0 by 8x8 block majority, so the body-map texels under
the face patch would pollute the face palette through tex_import: the TIM is encoded here directly, one fixed
palette per region/CLUT row.
"""
from lib import *
import math

b = Baby('Nyokimon', 43)
m = b.m
rng = np.random.default_rng(11)
NAME = 'Nyokimon'

# ---------------------------------------------------------------- the drop profile (world y, negative = up)
BOT, APEX = -97.0, -227.0
H = BOT - APEX                       # 130
RMAX = 65.0
# half-width / RMAX against the height fraction from the bottom, measured on the reference (outline included)
PROFILE = [(0.0, 0.0), (0.05, 0.52), (0.095, 0.69), (0.137, 0.79), (0.18, 0.88), (0.22, 0.93), (0.26, 0.97), (0.35, 1.0),
           (0.43, 0.98), (0.52, 0.915), (0.56, 0.86), (0.60, 0.79), (0.64, 0.68), (0.68, 0.54), (0.73, 0.40), (0.77, 0.30),
           (0.81, 0.22), (0.85, 0.175), (0.895, 0.14), (0.94, 0.11), (1.0, 0.085)]
_ph = np.array([p[0] for p in PROFILE]); _pw = np.array([p[1] for p in PROFILE])
_dense_s = np.linspace(0, 1, 801)
_raw = np.interp(_dense_s, _ph, _pw)
_k = np.exp(-0.5 * (np.arange(-12, 13) / 5.0) ** 2); _k /= _k.sum()
_pad = np.concatenate([np.full(12, _raw[0]), _raw, np.full(12, _raw[-1])])
_dense_r = RMAX * np.convolve(_pad, _k, 'valid')
_dense_r[:41] = RMAX * 0.52 * np.sqrt(np.clip(1 - ((_dense_s[:41] - 0.05) / 0.05) ** 2, 0, 1))   # round bottom


def radius(s):
    """Half-width of the drop at s = (BOT - y) / H in 0..1 (smoothed measured profile)."""
    return np.interp(np.clip(np.asarray(s, float), 0, 1), _dense_s, _dense_r)


def y_of_s(s):
    return BOT - np.asarray(s, float) * H


_ss = np.linspace(0, 1, 2001)
_rr = radius(_ss); _yy = y_of_s(_ss)
_seg = np.sqrt(np.diff(_rr) ** 2 + np.diff(_yy) ** 2)
_arc = np.concatenate([[0], np.cumsum(_seg)])
_t_of_s = (_arc[-1] - _arc) / _arc[-1]                  # t: 0 apex .. 1 bottom pole


def t_of_s(s):
    return np.interp(s, _ss, _t_of_s)


def s_of_t(t):
    return np.interp(t, _t_of_s[::-1], _ss[::-1])


def y_of_t(t):
    return y_of_s(s_of_t(t))


def r_of_y(y):
    return radius((BOT - np.asarray(y, float)) / H)


# ---------------------------------------------------------------- texture page layout
BODY_U0, BODY_U1 = 0, 192            # u 0..192 (193 columns, the last duplicates the first) <-> theta -180..180
BODY_V0, BODY_V1 = 25, 103           # v 25 (apex ring) .. 103 (bottom pole)
FACE_HALF_DEG = 45.0                 # the face frame covers theta in [-45, 45] (mirrored)
FRAME = 24
LEAF_U0, LEAF_U1, LEAF_V0, LEAF_V1 = 0, 47, 104, 127
STEM_U0, STEM_U1, STEM_V0, STEM_V1 = 48, 63, 104, 127
SEG = 16
RING_S = [0.0, 0.05, 0.13, 0.22, 0.35, 0.48, 0.58, 0.66, 0.74, 0.82, 0.90, 1.0]   # 0 = bottom pole, 1 = apex ring
FACE_RING_BOT, FACE_RING_TOP = 2, 7  # rings bounding the face patch (y -114 and -183)
RING_V = [int(round(BODY_V0 + (BODY_V1 - BODY_V0) * t_of_s(s))) for s in RING_S]
V_BOT_FACE, V_TOP_FACE = RING_V[FACE_RING_BOT], RING_V[FACE_RING_TOP]

ROW_FACE, ROW_BODY, ROW_SPROUT = 0, 1, 2


class Mesh:
    def __init__(self):
        self.v, self.n, self.prims = [], [], []

    def vert(self, p, n):
        n = np.asarray(n, float); n = n / (np.linalg.norm(n) or 1)
        self.v.append(tuple(int(round(c)) for c in p) + (0,))
        self.n.append(tuple(int(round(c * 4096)) for c in n) + (0,))
        return len(self.v) - 1

    def tri(self, a, bb, c, uv, row):
        """Textured Gouraud triangle (mode 0x34). Winding fixed so the engine's back-face cull keeps it:
        cross(v1-v0, v2-v0) . outward < 0 (PS1 screen y is down)."""
        P = [np.array(self.v[i][:3], float) for i in (a, bb, c)]
        N = sum(np.array(self.n[i][:3], float) for i in (a, bb, c))
        cr = np.cross(P[1] - P[0], P[2] - P[0])
        ids, uvs = [a, bb, c], list(uv)
        if cr @ N > 0:
            ids = [a, c, bb]; uvs = [uv[0], uv[2], uv[1]]
        d = dict(mode=0x34, flag=0, olen=9, uv=[(int(u), int(v)) for u, v in uvs], cba=0x7A00 + (row << 6), tsb=5,
                 uvpad=[0], colors=[], norms=ids, verts=ids, pad=[])
        self.prims.append(mmd.Prim.encode(d))

    def quad(self, a, bb, c, d, uva, uvb, uvc, uvd, row):
        self.tri(a, bb, c, (uva, uvb, uvc), row)
        self.tri(a, c, d, (uva, uvc, uvd), row)


body = Mesh()

# ---- the drop
ring_ids = []
for ri, s in enumerate(RING_S):
    y = float(y_of_s(s)); r = float(radius(s))
    ds = 2e-3
    dr = (float(radius(min(1, s + ds))) - float(radius(max(0, s - ds)))) / (2 * ds)
    nr, ny = H, dr                                       # outward normal in the (radial, y) plane
    nl = math.hypot(nr, ny); nr, ny = nr / nl, ny / nl
    ids = []
    if ri == 0:
        ids = [body.vert((0, y, 0), (0, 1, 0))] * (SEG + 1)
    else:
        for k in range(SEG + 1):
            th = math.radians(-180 + 360 * k / SEG)
            ids.append(body.vert((r * math.sin(th), y, -r * math.cos(th)), (nr * math.sin(th), ny, -nr * math.cos(th))))
    ring_ids.append(ids)


def body_uv(k, ri):
    return (BODY_U0 + 12 * k, RING_V[ri])


def face_uv(k, ri):
    th = -180 + 360 * k / SEG
    return (int(round(23 * abs(th) / FACE_HALF_DEG)), int(round(23 * (RING_V[ri] - V_TOP_FACE) / (V_BOT_FACE - V_TOP_FACE))))


def in_face(k, ri):
    th = -180 + 360 * k / SEG
    return FACE_RING_BOT <= ri <= FACE_RING_TOP and -FACE_HALF_DEG - 1e-6 <= th <= FACE_HALF_DEG + 1e-6


for k in range(SEG):
    body.tri(ring_ids[0][k], ring_ids[1][k], ring_ids[1][k + 1],
             ((BODY_U0 + 12 * k + 6, BODY_V1), body_uv(k, 1), body_uv(k + 1, 1)), ROW_BODY)
for ri in range(1, len(RING_S) - 1):
    for k in range(SEG):
        a, bb = ring_ids[ri][k], ring_ids[ri][k + 1]
        c, d = ring_ids[ri + 1][k + 1], ring_ids[ri + 1][k]
        if in_face(k, ri) and in_face(k + 1, ri + 1):
            body.quad(a, bb, c, d, face_uv(k, ri), face_uv(k + 1, ri), face_uv(k + 1, ri + 1), face_uv(k, ri + 1), ROW_FACE)
        else:
            body.quad(a, bb, c, d, body_uv(k, ri), body_uv(k + 1, ri), body_uv(k + 1, ri + 1), body_uv(k, ri + 1), ROW_BODY)

# ---- the stem: 22 units, leaning to the left (the viewer's left = -x) like the art, radius 4.5 -> 3.5
STEM_LEN = 34.0
LEAN = np.array([-15.0, 0.0, -3.0])
STEM = [(0.0, float(radius(1.0))), (0.35, 4.4), (0.7, 3.9), (1.0, 3.5)]          # (fraction, radius)
stem_rings = [ring_ids[-1]]
for (q, r) in STEM[1:]:
    ids = []
    for k in range(SEG + 1):
        th = math.radians(-180 + 360 * k / SEG)
        p = np.array([r * math.sin(th), APEX - STEM_LEN * q, -r * math.cos(th)]) + LEAN * q
        ids.append(body.vert(p, (math.sin(th), -0.2, -math.cos(th))))
    stem_rings.append(ids)
FORK = np.array([0.0, APEX - STEM_LEN, 0.0]) + LEAN
cap = body.vert(FORK + [0, -3, 0], (0, -1, 0))
SV = [STEM_V1, 120, 112, 105]


def stem_uv(k, j):
    return (STEM_U0 + int(round(15 * k / SEG)), SV[j])


for j in range(len(STEM) - 1):
    for k in range(SEG):
        body.quad(stem_rings[j][k], stem_rings[j][k + 1], stem_rings[j + 1][k + 1], stem_rings[j + 1][k],
                  stem_uv(k, j), stem_uv(k + 1, j), stem_uv(k + 1, j + 1), stem_uv(k, j + 1), ROW_SPROUT)
for k in range(SEG):
    body.tri(stem_rings[-1][k], stem_rings[-1][k + 1], cap, (stem_uv(k, 3), stem_uv(k + 1, 3), (stem_uv(k, 3)[0], STEM_V0)), ROW_SPROUT)

# ---- the leaves: strips of 7 stations x 3 vertices (edge, centre, edge), the centre sunk for a V section,
# bowed along the length; faces duplicated with flipped normals so both sides draw in the engine
FACING = np.array([0.0, -0.62, -0.78]); FACING /= np.linalg.norm(FACING)


def leaf(base, direction, length, half_width, stations, curl, gutter=2.5):
    d = np.asarray(direction, float); d /= np.linalg.norm(d)
    w = np.cross(d, FACING); w /= np.linalg.norm(w)
    n = np.cross(w, d); n /= np.linalg.norm(n)
    for flip in (1, -1):
        rows = []
        for (s, hw) in stations:
            c = base + d * (length * s) + n * curl(s)
            if hw == 0:
                rows.append([body.vert(c, flip * n)] * 3); continue
            e0, e1, cc = c - w * (hw * half_width), c + w * (hw * half_width), c - n * gutter * hw
            rows.append([body.vert(e0, flip * (n * 0.85 - w * 0.5)), body.vert(cc, flip * n), body.vert(e1, flip * (n * 0.85 + w * 0.5))])
        VL, VC, VR = LEAF_V0 + 1, (LEAF_V0 + LEAF_V1) // 2, LEAF_V1 - 1
        for j in range(len(stations) - 1):
            u0, u1 = LEAF_U0 + int(round(1 + 45 * stations[j][0])), LEAF_U0 + int(round(1 + 45 * stations[j + 1][0]))
            (a0, c0, b0), (a1, c1, b1) = rows[j], rows[j + 1]
            if j == len(stations) - 2:
                body.tri(a0, c0, a1, ((u0, VL), (u0, VC), (u1, VC)), ROW_SPROUT)
                body.tri(c0, b0, a1, ((u0, VC), (u0, VR), (u1, VC)), ROW_SPROUT)
            else:
                body.quad(a0, c0, c1, a1, (u0, VL), (u0, VC), (u1, VC), (u1, VL), ROW_SPROUT)
                body.quad(c0, b0, b1, c1, (u0, VC), (u0, VR), (u1, VR), (u1, VC), ROW_SPROUT)


# each leaf about as long as the body is wide, broad with a rounded tip (the sprout spans more than the body)
LEFT_ST = [(0.0, 0.12), (0.12, 0.55), (0.3, 0.92), (0.5, 1.0), (0.7, 0.9), (0.86, 0.62), (0.95, 0.32), (1.0, 0.0)]
RIGHT_ST = [(0.0, 0.1), (0.18, 0.13), (0.3, 0.62), (0.46, 0.96), (0.64, 1.0), (0.82, 0.7), (0.94, 0.35), (1.0, 0.0)]
leaf(FORK, (-0.76, -0.64, -0.12), 145, 30, LEFT_ST, lambda s: 9 * math.sin(math.pi * s) - 11 * s ** 3)
leaf(FORK + [2, 1, 0], (0.99, -0.10, -0.12), 190, 27, RIGHT_ST, lambda s: 18 * math.sin(math.pi * s) - 28 * s ** 3)

# ---- write the objects: 0 = everything, 1..6 = one degenerate triangle each (the tuft bones)
tmd = m.tmd
verts, norms = list(body.v), list(body.n)
ob0 = tmd.objects[0]
ob0.vert_start, ob0.nvert, ob0.norm_start, ob0.nnorm, ob0.prims = 0, len(body.v), 0, len(body.n), list(body.prims)
for oi in range(1, 7):
    ob = tmd.objects[oi]
    ob.vert_start, ob.nvert, ob.norm_start, ob.nnorm = len(verts), 3, len(norms), 1
    verts += [(0, 0, 0, 0)] * 3; norms += [(0, -4096, 0, 0)]
    ob.prims = [mmd.Prim.encode(dict(mode=0x34, flag=0, olen=9, uv=[(96, 60)] * 3, cba=0x7A00 + (ROW_BODY << 6), tsb=5,
                                     uvpad=[0], colors=[], norms=[0, 0, 0], verts=[0, 1, 2], pad=[]))]
tmd.verts, tmd.norms = verts, norms
print(f'body: {len(body.v)} verts, {len(body.prims)} tris; MMD {len(m.build())} B', file=sys.stderr)

# ---------------------------------------------------------------- texture page
t = b.tex
t[:] = 0; t[..., 3] = 255

GREYS = [(8, 8, 8), (16, 16, 24), (32, 32, 40), (48, 48, 56), (64, 64, 72), (88, 88, 96), (112, 112, 128)]
PALE = [(144, 148, 160), (176, 180, 192), (208, 212, 220), (232, 236, 240), (248, 248, 248)]
YEL = [(40, 36, 16), (72, 64, 16), (128, 112, 24), (216, 176, 24), (248, 232, 48), (248, 248, 168)]
PINK = [(176, 64, 96), (240, 128, 160), (248, 192, 208)]
GREENS = [(24, 64, 24), (40, 96, 32), (56, 128, 40), (80, 152, 48), (104, 176, 56), (128, 200, 64), (152, 216, 80),
          (184, 232, 104), (208, 240, 136), (232, 248, 176)]
PAL_FACE = np.array(GREYS + YEL + PINK, float)
PAL_BODY = np.array(GREYS + PALE + [(24, 24, 32)], float)
PAL_SPROUT = np.array(GREENS + [(8, 8, 8)], float)
assert len(PAL_FACE) <= 16 and len(PAL_BODY) <= 16 and len(PAL_SPROUT) <= 16


def snap(rgb, pal):
    d = ((rgb[..., None, :] - pal[None, None]) ** 2).sum(-1)
    return pal[d.argmin(-1)]


BALL_C = np.array([0.0, -156.0])          # centre of the fuzz ball on the front (x_u, y)


def sigmoid(x):
    return 1 / (1 + np.exp(-np.clip(x, -30, 30)))


def fuzz_top(theta):
    """y of the fuzz ball's upper boundary: higher at the front and back, lower at the sides (an arc from the front)."""
    return -188 - 10 * np.cos(np.radians(theta)) ** 2


def fuzz_bot(theta):
    return -110 - 13 * np.sin(np.radians(theta)) ** 2


def shell(theta, y):
    """S in 0..1: how pale (clear skin) the surface is at (theta deg, y), and the pale colour there."""
    th = theta
    s_neck = sigmoid((-y + fuzz_top(th)) / 3.0)
    s_bot = sigmoid((y - fuzz_bot(th)) / 3.0)
    rho = np.sqrt(((th + 86) / 27.0) ** 2 + ((y + 132) / 23.0) ** 2)
    s_left = 0.85 * sigmoid((1 - rho) / 0.14)
    thc = 88 - 30 * np.clip((-y - 168) / 25.0, 0, 1)
    s_right = 0.6 * sigmoid((7 - np.abs(th - thc)) / 4.0) * sigmoid((-y - 118) / 6.0)
    white = np.clip((-y - 170) / 20.0, 0, 1)
    s_gloss = 0.18 * np.exp(-((th + 30) / 16.0) ** 2 - ((y + 178) / 11.0) ** 2)
    parts = [s_neck, s_bot, s_left, s_right, s_gloss]
    neck_c = np.stack([np.interp(-y, [190, 227], [226, 250])] * 3, -1) + np.array([0, 2, 6])
    right_c = np.array((224, 228, 236), float) * (1 - white[..., None]) + np.array((250, 250, 250), float) * white[..., None]
    cols = [neck_c, np.full(th.shape + (3,), (222, 226, 234), float), np.full(th.shape + (3,), (232, 236, 240), float),
            right_c, np.full(th.shape + (3,), (208, 212, 224), float)]
    S = 1 - np.prod([1 - p for p in parts], axis=0)
    wsum = sum(parts) + 1e-6
    col = sum(p[..., None] * c for p, c in zip(parts, cols)) / wsum[..., None]
    return S, col


def unroll(theta, y):
    return np.radians(theta) * r_of_y(y), y


def make_strokes():
    """(x0, y0, dx, dy, length, width, brightness, kind) in unrolled space; kind 0 = fuzz hair, 1 = edge hair."""
    out = []
    n = 0
    while n < 3400:
        th = rng.uniform(-180, 180); y = rng.uniform(-212, -104)
        r = float(r_of_y(y))
        if rng.random() > r / RMAX: continue
        x = math.radians(th) * r
        dx, dy = x - BALL_C[0], y - BALL_C[1]
        if abs(th) > 90:
            dx = math.radians(th - math.copysign(180, th)) * r
        L = math.hypot(dx, dy) or 1
        dx, dy = dx / L, dy / L
        ang = rng.normal(0, 0.35)
        dx, dy = dx * math.cos(ang) - dy * math.sin(ang), dx * math.sin(ang) + dy * math.cos(ang)
        edge = min(1.0, L / 50.0)
        top = min(1.0, max(0.0, (-y - 150) / 45.0))
        tr = math.exp(-((th - 40) / 55.0) ** 2 - ((y + 185) / 28.0) ** 2)
        bright = (0.12 + 0.22 * edge + 0.22 * top + 0.16 * tr) * rng.uniform(0.6, 1.35)
        out.append((x, y, dx, dy, rng.uniform(2.5, 5.0) + 2.5 * edge, rng.uniform(0.9, 1.4), min(1.0, bright), 0))
        n += 1
    th = rng.uniform(-180, 180, 50000); y = rng.uniform(APEX + 8, BOT - 4, 50000)
    S, _ = shell(th, y)
    keep = (S > 0.25) & (S < 0.6) & (rng.random(50000) < r_of_y(y) / RMAX)
    th, y, S = th[keep], y[keep], S[keep]
    e = 1.0
    Sx, _ = shell(th + e, y); Sy, _ = shell(th, y + e)
    gx, gy = (Sx - S) / math.radians(e), (Sy - S) / e
    gx = gx / np.maximum(r_of_y(y), 1)
    g = np.hypot(gx, gy) + 1e-6
    for i in range(min(len(th), 1000)):
        x = math.radians(th[i]) * float(r_of_y(y[i]))
        dx, dy = gx[i] / g[i], gy[i] / g[i]
        ang = rng.normal(0, 0.3)
        dx, dy = dx * math.cos(ang) - dy * math.sin(ang), dx * math.sin(ang) + dy * math.cos(ang)
        out.append((x - dx * 3, float(y[i]) - dy * 3, dx, dy, rng.uniform(5, 9), rng.uniform(0.9, 1.4), rng.uniform(0.5, 1.0), 1))
    return out


STROKES = make_strokes()


def hair_fields(theta, y, slicer=None):
    """Per sample: fuzz hair brightness (max over strokes) and edge-hair coverage. slicer(x0, y0, x1, y1) ->
    (row slice, column slice) of the sample grid that can contain the stroke (None = evaluate everywhere)."""
    xu, yu = unroll(theta, y)
    hin = np.zeros(theta.shape); hedge = np.zeros(theta.shape)
    for (x0, y0, dx, dy, L, w, br, kind) in STROKES:
        if slicer is not None:
            sl = slicer(x0, y0, x0 + dx * L, y0 + dy * L)
            if sl is None: continue
            XU, YU, HIN, HED = xu[sl], yu[sl], hin[sl], hedge[sl]
        else:
            XU, YU, HIN, HED = xu, yu, hin, hedge
        px, py = XU - x0, YU - y0
        along = px * dx + py * dy
        perp = np.abs(px * dy - py * dx)
        cov = np.clip((w * 0.5 + 0.6 - perp) / 0.8, 0, 1) * ((along > -0.5) & (along < L))
        cov = cov * np.clip((L - along) / 2.0, 0, 1)
        if kind == 0:
            np.maximum(HIN, cov * br, out=HIN)
        else:
            np.maximum(HED, cov * br, out=HED)
    return hin, hedge


def body_slicer(x0, y0, x1, y1, margin=3):
    ys = sorted((y0, y1))
    th = [math.degrees(x / max(float(r_of_y(y)), 1.0)) for x, y in ((x0, y0), (x1, y1))]
    u0 = (min(th) + 180) / 360 * (BODY_U1 - BODY_U0) - margin
    u1 = (max(th) + 180) / 360 * (BODY_U1 - BODY_U0) + margin
    v0 = float(t_of_s((BOT - ys[1]) / H)) * (BODY_V1 - BODY_V0) - margin
    v1 = float(t_of_s((BOT - ys[0]) / H)) * (BODY_V1 - BODY_V0) + margin
    us, ue = max(0, int(u0)), min(BODY_U1 - BODY_U0 + 1, int(u1) + 2)
    vs, ve = max(0, int(v0)), min(BODY_V1 - BODY_V0 + 1, int(v1) + 2)
    if us >= ue or vs >= ve: return None
    return (slice(vs, ve), slice(us, ue))


BLACK = np.array((8, 8, 10), float)
BLACK_TOP = np.array((24, 24, 30), float)
TINT = np.array((104, 106, 124), float)


def paint_body(theta, y, slicer=None):
    """Colour of the body surface at (theta, y) without eyes or mouth."""
    hin, hedge = hair_fields(theta, y, slicer)
    top = np.clip((-y - 150) / 45.0, 0, 1)[..., None]
    base = BLACK * (1 - top) + BLACK_TOP * top
    col = base + hin[..., None] * (TINT - base)
    S, pale = shell(theta, y)
    col = col * (1 - S[..., None]) + pale * S[..., None]
    dark = np.where(S[..., None] > 0.5, np.array((26, 26, 32), float), TINT * 0.8)
    col = col * (1 - hedge[..., None]) + dark * hedge[..., None]
    return col


SS = 3


def grid(u0, u1, v0, v1):
    us = np.arange(u0, u1 + 1); vs = np.arange(v0, v1 + 1)
    off = (np.arange(SS) + 0.5) / SS
    U = us[None, :, None, None] + off[None, None, :, None]
    V = vs[:, None, None, None] + off[None, None, None, :]
    return (np.broadcast_to(U, (len(vs), len(us), SS, SS)).astype(float),
            np.broadcast_to(V, (len(vs), len(us), SS, SS)).astype(float))


U, V = grid(BODY_U0, BODY_U1, BODY_V0, BODY_V1)
theta = (U - BODY_U0) / (BODY_U1 - BODY_U0) * 360 - 180
yy = y_of_t(np.clip((V - BODY_V0) / (BODY_V1 - BODY_V0), 0, 1))
col = paint_body(theta, yy, body_slicer).mean(axis=(2, 3))
t[BODY_V0:BODY_V1 + 1, BODY_U0:BODY_U1 + 1, :3] = snap(col, PAL_BODY).astype(np.uint8)

# ---- face frames
EYE_Y, EYE_DEG, EYE_R = -163.0, 20.0, 8.5
EYE = np.array([math.radians(EYE_DEG) * float(r_of_y(EYE_Y)), EYE_Y])
MOUTH_Y = -135.0


def frame_coords(fx):
    U, V = grid(fx, fx + FRAME - 1, 0, FRAME - 1)
    theta = (U - fx) / 23.0 * FACE_HALF_DEG
    vb = V_TOP_FACE + V / 23.0 * (V_BOT_FACE - V_TOP_FACE)
    return theta, y_of_t(np.clip((vb - BODY_V0) / (BODY_V1 - BODY_V0), 0, 1))


def soft(x, w=0.8):
    return np.clip(x / w + 0.5, 0, 1)


def eye_layer(theta, yy, kind):
    xu, yu = unroll(theta, yy)
    dx, dy = xu - EYE[0], yu - EYE[1]
    d = np.hypot(dx, dy)
    core = np.full(theta.shape + (3,), (248, 232, 48), float)
    rim = np.array((216, 176, 24), float)
    colr = core
    if kind in ('open', 'down', 'drowsy', 'blink'):
        if kind == 'down':
            d2 = np.hypot(dx, dy - 2.0)
            shape = soft(EYE_R - d2) * soft(dy + 1.5)              # shifted down, a flat lid cuts the top
        else:
            shape = soft(EYE_R - d)
            if kind == 'drowsy': shape = shape * soft(dy - 1.5)
            if kind == 'blink': shape = shape * soft(dy + 1.0)
        edge = soft(d - (EYE_R - 2.2))
        colr = core * (1 - edge[..., None]) + rim * edge[..., None]
        hl = soft(2.3 - np.hypot(dx + 2.8, dy + 2.8))
        colr = colr * (1 - hl[..., None]) + np.array((248, 248, 168), float) * hl[..., None]
        if kind == 'drowsy': colr = colr * 0.85
    elif kind == 'closed':
        shape = soft(1.5 - np.abs(d - 7.5)) * soft(dy - 2.0)
        colr = np.full(theta.shape + (3,), (216, 176, 24), float)
    elif kind == 'happy':
        shape = soft(2.2 - np.abs(d - 8.0)) * soft(-dy - 0.5)
    else:
        ax = EYE[0] - 5.0 if kind == 'strain' else EYE[0] - 4.0
        ay = 0.0 if kind == 'strain' else 1.0
        arm = np.abs((xu - ax) - 0.85 * np.abs(dy - ay))
        shape = soft(1.6 - arm) * soft(7.5 - np.abs(dy - ay)) * soft(xu - ax + 0.5)
    halo = np.clip((19 - d) / 9.0, 0, 1) ** 1.6 * (0.9 if kind not in ('closed', 'drowsy') else 0.45)
    return shape, colr, halo


def mouth_layer(theta, yy, kind):
    xu, yu = unroll(theta, yy)
    dx, dy = xu, yu - MOUTH_Y
    PINKC, DARK, LIGHT = np.array((240, 128, 160), float), np.array((176, 64, 96), float), np.array((248, 192, 208), float)
    colr = np.full(theta.shape + (3,), PINKC)
    if kind in ('open', 'blink'):                                 # small smile: a D, flat top, pink
        shape = soft(1 - np.hypot(dx / 10.0, dy / 7.0), 0.12) * soft(dy + 1.5)
        colr = np.where((dy > 3.5)[..., None], DARK, PINKC)
        colr = np.where((dy < 0.0)[..., None], LIGHT, colr)
    elif kind == 'down':
        shape = soft(1 - np.hypot(dx / 7.0, dy / 4.0), 0.15) * soft(dy + 1.0)
    elif kind in ('drowsy', 'closed'):
        shape = soft(1 - np.hypot(dx / 6.0, dy / 1.8), 0.2)
    elif kind == 'happy':                                         # open smile: dark inside, pink tongue, light lip
        shape = soft(1 - np.hypot(dx / 11.0, dy / 8.0), 0.1) * soft(dy + 1.0)
        tongue = soft(1 - np.hypot(dx / 7.0, (dy - 4.5) / 3.0), 0.15)
        colr = DARK * (1 - tongue[..., None]) + PINKC * tongue[..., None]
        lip = soft(dy + 1.0) * soft(-dy + 0.5)
        colr = colr * (1 - lip[..., None]) + LIGHT * lip[..., None]
    elif kind == 'strain':
        rr = np.hypot(dx / 5.5, dy / 6.5)
        shape = soft(1 - rr, 0.12)
        colr = np.where((rr > 0.72)[..., None], PINKC, DARK)
    else:
        rr = np.hypot(dx / 8.0, dy / 4.5)
        shape = soft(1 - rr, 0.12)
        colr = np.where((rr > 0.72)[..., None], PINKC, DARK)
    return shape, colr


FRAMES = {0: 'open', 24: 'down', 48: 'drowsy', 72: 'closed', 96: 'blink', 120: 'happy', 144: 'strain', 168: 'strain2',
          192: 'open'}
HALO_C = np.array((104, 88, 16), float)
for fx, kind in FRAMES.items():
    theta, yy = frame_coords(fx)
    base = paint_body(theta, yy)
    eshape, ecol, halo = eye_layer(theta, yy, kind)
    base = base * (1 - halo[..., None] * 0.9) + HALO_C * (halo[..., None] * 0.9)
    base = base * (1 - eshape[..., None]) + ecol * eshape[..., None]
    mshape, mcol = mouth_layer(theta, yy, kind)
    base = base * (1 - mshape[..., None]) + mcol * mshape[..., None]
    t[0:FRAME, fx:fx + FRAME, :3] = snap(base.mean(axis=(2, 3)), PAL_FACE).astype(np.uint8)

# ---- leaf texture: gradient base -> tip, lighter midrib, darker edges
U, V = grid(LEAF_U0, LEAF_U1, LEAF_V0, LEAF_V1)
s = (U - LEAF_U0 - 1) / 45.0
q = (V - (LEAF_V0 + LEAF_V1 + 1) / 2) / ((LEAF_V1 - LEAF_V0) / 2)
base_c = ramp(np.clip(s, 0, 1), [(0, (56, 120, 40)), (0.45, (104, 176, 56)), (1, (200, 236, 120))])
edge = np.clip((np.abs(q) - 0.7) / 0.3, 0, 1)
col = base_c * (1 - 0.22 * edge[..., None])
rib = np.clip(1 - np.abs(q) / 0.1, 0, 1) * np.clip(s * 4, 0, 1) * np.clip((0.95 - s) * 8, 0, 1)
col = col * (1 - rib[..., None]) + np.array((216, 240, 144), float) * rib[..., None]
col = col * (1 + (np.clip(-q, 0, 1) * 0.1)[..., None])
t[LEAF_V0:LEAF_V1 + 1, LEAF_U0:LEAF_U1 + 1, :3] = snap(col.mean(axis=(2, 3)), PAL_SPROUT).astype(np.uint8)
U, V = grid(STEM_U0, STEM_U1, STEM_V0, STEM_V1)
a = (U - STEM_U0 - 0.5) / 15.0
sh = np.clip(0.55 + 0.45 * np.cos((a - 0.5) * 2 * np.pi), 0.3, 1.0) * (1 - 0.12 * (V - STEM_V0) / 23.0)
col = ramp(np.clip(sh, 0, 1), [(0, (40, 96, 32)), (0.6, (96, 168, 56)), (1, (152, 216, 80))])
t[STEM_V0:STEM_V1 + 1, STEM_U0:STEM_U1 + 1, :3] = snap(col.mean(axis=(2, 3)), PAL_SPROUT).astype(np.uint8)

# ---- encode the TIM ourselves: each region has its own CLUT row and a fixed palette
REGIONS = [(ROW_FACE, PAL_FACE, (0, 9 * FRAME, 0, FRAME)), (ROW_BODY, PAL_BODY, (BODY_U0, BODY_U1 + 1, BODY_V0, BODY_V1 + 1)),
           (ROW_SPROUT, PAL_SPROUT, (LEAF_U0, STEM_U1 + 1, LEAF_V0, LEAF_V1 + 1))]


# the tournament's flat sprite (renderFlatDigimon): CLUT row 15, four 15x15 frames at u 224/240, v 96/112
ICON = ['......L........',
        '.....LL....RRR.',
        '......LL.RR..RR',
        '.......SR......',
        '.......S.......',
        '......WWW......',
        '.....WwwwW.....',
        '....WFFFFFW....',
        '...WFFYFYFFW...',
        '...WFFFFFFFW...',
        '...WFFFPPFFW...',
        '...WFFFFFFFW...',
        '....WFFFFFW....',
        '.....WFFFW.....',
        '......WWW......']
ICON_PAL = {'.': None, 'F': (8, 8, 8), 'f': (48, 48, 56), 'W': (208, 212, 220), 'w': (248, 248, 248), 'Y': (248, 232, 48),
            'o': (104, 88, 16), 'L': (104, 176, 56), 'R': (128, 200, 64), 'S': (40, 96, 32), 'P': (240, 128, 160)}


def encode_tim():
    tim = b.tim; W = tim.w
    tim.idx[:] = bytes(len(tim.idx))
    for row, pal, (u0, u1, v0, v1) in REGIONS:
        tim.pal[row] = [mmd.rgba_to_c15(*[int(c) for c in rgb]) for rgb in pal] + [0] * (16 - len(pal))
        sub = t[v0:v1, u0:u1, :3].astype(float)
        idx = ((sub[..., None, :] - pal[None, None]) ** 2).sum(-1).argmin(-1)
        for dy in range(v1 - v0):
            tim.idx[(v0 + dy) * W + u0:(v0 + dy) * W + u1] = bytes(int(i) for i in idx[dy])
    keys = list(ICON_PAL)                                   # index 0 = '.' = transparent
    tim.pal[15] = [0] + [mmd.rgba_to_c15(*ICON_PAL[k]) for k in keys[1:]] + [0] * (16 - len(keys))
    for f, (fu, fv) in enumerate(((224, 96), (240, 96), (224, 112), (240, 112))):
        for yy_, line in enumerate(ICON):
            for xx_, ch in enumerate(line):
                if f % 2 and ch == 'Y': ch = 'o'            # the odd frames blink
                tim.idx[(fv + yy_) * W + fu + xx_] = keys.index(ch)
                if ch != '.':
                    t[fv + yy_, fu + xx_, :3] = ICON_PAL[ch]


def save():
    encode_tim()
    os.makedirs(OUT, exist_ok=True)
    mp, tp = os.path.join(OUT, NAME + '.MMD'), os.path.join(OUT, NAME + '.TIM')
    open(mp, 'wb').write(m.build()); open(tp, 'wb').write(b.tim.to_bytes())
    cv2.imwrite(os.path.join(OUT, NAME + '-tex.png'),
                cv2.resize(cv2.cvtColor(t, cv2.COLOR_RGBA2BGRA), None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST))
    print(f'MMD {os.path.getsize(mp)} B', file=sys.stderr)
    return f'{mp}:43:{tp}:0:{NAME}'


spec = save()
print(spec)
if __name__ == '__main__' and '--sheet' in sys.argv:
    sheet(OUT + f'/{NAME}-sheet.png', [spec], panels='mesh:front,mesh:three,mesh:side')
