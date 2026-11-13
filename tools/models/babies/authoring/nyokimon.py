"""Botamon (type 1) -> Nyokimon, round 4: the same drop, sprout and face on Botamon's skeleton and animations.

Rounds 1-3 used Yuramon (type 43), whose body bone hovers 150 units up: the drop had to float 22 units to survive the
idle bob, and the walk, tired walk and run sank 35, 37 and 3 units. Botamon's body bone rests on the ground (its idle
bob is +-1, its walk and run are hops that leave the ground and land on it), the three field clips measure walk 21.0,
tired 16.7 and run 35.0 units per tick, and the mesh is one object on bone 2 (the other objects of the donor do not
exist), so the whole drop, stem and leaves move with the body bone: the donor's squash and stretch deforms them as a
unit.

Coordinates: everything is designed in GROUND space (world units, y negative = up, the ground at y = 0, the donor's
rest floor) and written into bone 2's local space by subtracting its rest translation (BONE_T, read from the donor;
bone 2 is not rotated at rest). The rest bottom (BOT) is 0: the drop touches the ground at rest and in idle.

Shape: body 100 wide x 100 tall (native Fresh babies are 106-133), the profile measured on the reference (widest at
35 %, a thin neck over the top 18 %); 16 columns x 9 rings + pole, an 8-column stem, two 6-station double-sided
leaves (the long one to the right, tip 0.9 body widths from the axis; the short steep one to the left, tip at 0.6):
sprout span 1.5 x the body width, total 161 tall (the size review then scales the whole model by 0.8, shrink.py), 384
primitives. The donor's other objects (none for Botamon) are collapsed to one degenerate triangle each.

Texture: clear skin baked into the body map (grey-clear neck cone and a thin grey bottom rim, both the same all
around so no seam or wall shows under per-vertex lighting, one small glass highlight at the upper left); short low-contrast
hair strokes radiating from the face centre with hairs sticking out into the pale zones; yellow-green leaves with
darker edges and a pale mid-vein; a 15x15 tournament sprite in CLUT row 15. The face lives in two WINDOWS, the page
rectangles Botamon's texture animations overwrite: the eyes (24x16 at (8, 8): open, looking down, closed, drowsy,
happy, open again) and the mouth (24x16 at (0, 24): none, small, open, big). Each window shows a stretch of the drop
(theta -45..45 degrees between two body rings, so the eyes and the mouth are drawn on the whole face, both eyes in one
frame): solid yellow discs with a darker rim and a grey wavy upper-lip line over a pink tongue. CONFIG says where the
windows and their frames sit and what each frame draws; another donor needs its own entry (three were tried in
the donor review: Botamon, Tsunomon with 32x24 eye frames, Tokomon with one 72x48 window).

Traps: the engine culls back faces (front = clockwise on screen with y down: cross(v1-v0, v2-v0) . n_out < 0),
animstudio does not; the TIM is encoded here directly (fixed palette per region/CLUT row) because palette_map hands
uncovered texels to row 0 by block majority and tex_import would then pollute the face palette; the body map, the
windows, their frames, the leaves and the flat sprite must not overlap (asserted).
"""
from lib import *
import math

DONOR = 1                            # Botamon (MMD0/BOTA): three bones, the whole body one object on bone 2
# Per donor: the rest height of the drop's bottom above the ground (negative = up) and where its texture page keeps the
# face. A face WINDOW is the rectangle of the page that the donor's texture animation overwrites (`dst`) and the frames
# it copies there (`src`, each with the eye and mouth drawing it shows; None = that layer is not in the window). The
# windows are laid over the drop: 'rings' = the body rings (index into RING_S) its top and bottom edge sit on.
# Body, leaves and stem take free rectangles of the page; the flat sprite stays at u 224/240, v 96/112.
CONFIG = {
    1: dict(bot=0.0, body=(0, 192, 41, 103), leaf=(0, 47, 104, 127), stem=(48, 63, 104, 127), windows=[
        dict(rings=(4, 6), dst=(8, 8, 24, 16), base=('open', None), frames=[
            (48, 0, 'open', None), (72, 0, 'down', None), (96, 0, 'closed', None), (120, 0, 'drowsy', None),
            (144, 0, 'happy', None), (168, 0, 'open', None)]),
        dict(rings=(2, 4), dst=(0, 24, 24, 16), base=(None, 'closed'), frames=[
            (48, 16, None, 'closed'), (72, 16, None, 'down'), (96, 16, None, 'open'), (120, 16, None, 'happy')])]),
}
CFG = CONFIG[DONOR]
b = Baby('Nyokimon', DONOR)
m = b.m
rng = np.random.default_rng(11)
NAME = 'Nyokimon'


def _rest_translation():
    """Bone 2's rest translation (donor world units): the drop is designed in ground space and written into the local space."""
    e = mmd.exe()
    frames, _ = mmd.simulate(m.anims.anims[m.anims.table[0]], e.bone_count[DONOR])
    pose = frames[0]; pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
    M = np.array(mmd.bone_matrices(m, pose)[2], float)
    assert np.allclose(M[:3, :3], np.eye(3)), 'the drop bone is rotated at rest'
    return M[:3, 3]


BONE_T = _rest_translation()

# ---------------------------------------------------------------- the drop profile (ground y, negative = up)
H = 100.0                            # body height
RMAX = 50.0                          # half width
BOT = CFG['bot']                     # rest bottom above the ground (negative = up), tuned per donor
APEX = BOT - H
PROFILE = [(0.0, 0.0), (0.05, 0.52), (0.095, 0.69), (0.137, 0.79), (0.18, 0.88), (0.22, 0.93), (0.26, 0.97), (0.35, 1.0),
           (0.43, 0.98), (0.52, 0.915), (0.56, 0.86), (0.60, 0.79), (0.64, 0.68), (0.68, 0.54), (0.73, 0.40), (0.77, 0.30),
           (0.81, 0.22), (0.85, 0.175), (0.895, 0.14), (0.94, 0.11), (1.0, 0.085)]
_ph = np.array([p[0] for p in PROFILE]); _pw = np.array([p[1] for p in PROFILE])
_dense_s = np.linspace(0, 1, 801)
_raw = np.interp(_dense_s, _ph, _pw)
_k = np.exp(-0.5 * (np.arange(-12, 13) / 5.0) ** 2); _k /= _k.sum()
_pad = np.concatenate([np.full(12, _raw[0]), _raw, np.full(12, _raw[-1])])
_dense_r = RMAX * np.convolve(_pad, _k, 'valid')
_dense_r[:41] = RMAX * 0.52 * np.sqrt(np.clip(1 - ((_dense_s[:41] - 0.05) / 0.05) ** 2, 0, 1))


def radius(s):
    return np.interp(np.clip(np.asarray(s, float), 0, 1), _dense_s, _dense_r)


def y_of_s(s):
    return BOT - np.asarray(s, float) * H


def hy(f):
    """Ground y at height fraction f of the body (0 = bottom, 1 = apex)."""
    return BOT - f * H


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
BODY_U0, BODY_U1, BODY_V0, BODY_V1 = CFG['body']      # the last column duplicates the first <-> theta -180..180; v0 = apex ring, v1 = bottom pole
COLPX = (BODY_U1 - BODY_U0) / 16.0
FACE_HALF_DEG = 45.0
LEAF_U0, LEAF_U1, LEAF_V0, LEAF_V1 = CFG['leaf']
STEM_U0, STEM_U1, STEM_V0, STEM_V1 = CFG['stem']
SEG = 16
RING_S = [0.0, 0.06, 0.15, 0.27, 0.39, 0.51, 0.62, 0.72, 0.84, 1.0]     # 0 = bottom pole, 1 = apex ring (face windows sit on .15 / .39 / .62)
RING_V = [int(round(BODY_V0 + (BODY_V1 - BODY_V0) * t_of_s(s))) for s in RING_S]
ROW_FACE, ROW_BODY, ROW_SPROUT = 0, 1, 2


class Mesh:
    def __init__(self):
        self.v, self.n, self.prims = [], [], []

    def vert(self, p, n):
        """p in ground space; stored in bone-2 local space."""
        n = np.asarray(n, float); n = n / (np.linalg.norm(n) or 1)
        self.v.append((int(round(p[0] - BONE_T[0])), int(round(p[1] - BONE_T[1])), int(round(p[2] - BONE_T[2])), 0))
        self.n.append(tuple(int(round(c * 4096)) for c in n) + (0,))
        return len(self.v) - 1

    def tri(self, a, bb, c, uv, row):
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
    nr, ny = H, dr
    nl = math.hypot(nr, ny); nr, ny = nr / nl, ny / nl
    if ri == 0:
        ids = [body.vert((0, y, 0), (0, 1, 0))] * (SEG + 1)
    else:
        ids = []
        for k in range(SEG + 1):
            th = math.radians(-180 + 360 * k / SEG)
            ids.append(body.vert((r * math.sin(th), y, -r * math.cos(th)), (nr * math.sin(th), ny, -nr * math.cos(th))))
    ring_ids.append(ids)


def body_uv(k, ri):
    return (BODY_U0 + int(round(COLPX * k)), RING_V[ri])


def window_of(k, ri):
    """The face window that quad (k, ri) lies in (its rings and its columns inside it), or None."""
    th = -180 + 360 * k / SEG
    if not -FACE_HALF_DEG - 1e-6 <= th <= FACE_HALF_DEG - 22.5 + 1e-6:
        return None
    for w in CFG['windows']:
        if w['rings'][0] <= ri and ri + 1 <= w['rings'][1]:
            return w
    return None


def face_uv(w, k, ri):
    """Page position of vertex (k, ring ri) inside window w: theta and the arc position of the ring spread linearly over
    the window (the texture mapping of the engine is affine, so a window crossing several rings stays straight)."""
    th = -180 + 360 * k / SEG
    x, y, ww, hh = w['dst']
    t0, t1 = float(t_of_s(RING_S[w['rings'][1]])), float(t_of_s(RING_S[w['rings'][0]]))
    return (x + int(round((th + FACE_HALF_DEG) / (2 * FACE_HALF_DEG) * (ww - 1))),
            y + int(round((float(t_of_s(RING_S[ri])) - t0) / (t1 - t0) * (hh - 1))))


for k in range(SEG):
    body.tri(ring_ids[0][k], ring_ids[1][k], ring_ids[1][k + 1],
             ((BODY_U0 + int(round(COLPX * (k + 0.5))), BODY_V1), body_uv(k, 1), body_uv(k + 1, 1)), ROW_BODY)
for ri in range(1, len(RING_S) - 1):
    for k in range(SEG):
        a, bb = ring_ids[ri][k], ring_ids[ri][k + 1]
        c, d = ring_ids[ri + 1][k + 1], ring_ids[ri + 1][k]
        win = window_of(k, ri)
        if win:
            body.quad(a, bb, c, d, face_uv(win, k, ri), face_uv(win, k + 1, ri), face_uv(win, k + 1, ri + 1), face_uv(win, k, ri + 1), ROW_FACE)
        else:
            body.quad(a, bb, c, d, body_uv(k, ri), body_uv(k + 1, ri), body_uv(k + 1, ri + 1), body_uv(k, ri + 1), ROW_BODY)

# ---- the stem: 8 columns (every other apex vertex), leaning to the viewer's left like the art
STEM_LEN = 22.0
LEAN = np.array([-10.0, 0.0, -2.0])
STEM = [(0.0, 0.0), (0.5, 3.3), (1.0, 2.8)]                   # (fraction, radius); ring 0 = the apex ring
stem_rings = [[ring_ids[-1][k] for k in range(0, SEG + 1, 2)]]
for (q, r) in STEM[1:]:
    ids = []
    for k in range(0, SEG + 1, 2):
        th = math.radians(-180 + 360 * k / SEG)
        p = np.array([r * math.sin(th), APEX - STEM_LEN * q, -r * math.cos(th)]) + LEAN * q
        ids.append(body.vert(p, (math.sin(th), -0.2, -math.cos(th))))
    stem_rings.append(ids)
FORK = np.array([0.0, APEX - STEM_LEN, 0.0]) + LEAN
cap = body.vert(FORK + [0, -2.5, 0], (0, -1, 0))
SV = [STEM_V1, STEM_V0 + 12, STEM_V0 + 1]


def stem_uv(k, j):
    return (STEM_U0 + int(round(15 * k / 8)), SV[j])


for j in range(len(STEM) - 1):
    for k in range(8):
        body.quad(stem_rings[j][k], stem_rings[j][k + 1], stem_rings[j + 1][k + 1], stem_rings[j + 1][k],
                  stem_uv(k, j), stem_uv(k + 1, j), stem_uv(k + 1, j + 1), stem_uv(k, j + 1), ROW_SPROUT)
for k in range(8):
    body.tri(stem_rings[-1][k], stem_rings[-1][k + 1], cap, (stem_uv(k, 2), stem_uv(k + 1, 2), (stem_uv(k, 2)[0], STEM_V0)), ROW_SPROUT)

# ---- the leaves: 6 stations x 3 vertices (edge, centre, edge), the centre sunk for a V section, bowed along the
# length (up, flat, drooping tip); faces duplicated with flipped normals so both sides draw in the engine
FACING = np.array([0.0, -0.62, -0.78]); FACING /= np.linalg.norm(FACING)


def leaf(base, direction, length, half_width, stations, curl, gutter=2.0):
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


# spoon shapes, width 40 % of the length; the long leaf's tip 0.9 body widths right of the axis, the short one 0.6 left
LEFT_ST = [(0.0, 0.15), (0.2, 0.7), (0.45, 1.0), (0.7, 0.85), (0.9, 0.45), (1.0, 0.0)]
RIGHT_ST = [(0.0, 0.12), (0.22, 0.2), (0.4, 0.8), (0.62, 1.0), (0.85, 0.65), (1.0, 0.0)]
leaf(FORK, (-0.76, -0.64, -0.12), 63, 13, LEFT_ST, lambda s: 4 * math.sin(math.pi * s) - 5 * s ** 3)
leaf(FORK + [1.5, 0.8, 0], (0.99, -0.10, -0.12), 105, 21, RIGHT_ST, lambda s: 9 * math.sin(math.pi * s) - 14 * s ** 3)

# ---- write the objects: 0 = everything, 1..6 = one degenerate triangle each (the tuft bones)
tmd = m.tmd
verts, norms = list(body.v), list(body.n)
ob0 = tmd.objects[0]
ob0.vert_start, ob0.nvert, ob0.norm_start, ob0.nnorm, ob0.prims = 0, len(body.v), 0, len(body.n), list(body.prims)
for oi in range(1, len(tmd.objects)):
    ob = tmd.objects[oi]
    ob.vert_start, ob.nvert, ob.norm_start, ob.nnorm = len(verts), 3, len(norms), 1
    verts += [(0, 0, 0, 0)] * 3; norms += [(0, -4096, 0, 0)]
    ob.prims = [mmd.Prim.encode(dict(mode=0x34, flag=0, olen=9, uv=[(96, 60)] * 3, cba=0x7A00 + (ROW_BODY << 6), tsb=5,
                                     uvpad=[0], colors=[], norms=[0, 0, 0], verts=[0, 1, 2], pad=[]))]
tmd.verts, tmd.norms = verts, norms
V0 = np.array([v[:3] for v in body.v], float)
print(f'body: {len(body.v)} verts, {len(body.prims)} tris (+6); local y {V0[:, 1].min():.0f}..{V0[:, 1].max():.0f} '
      f'(ground {V0[:, 1].min() + BONE_T[1]:.0f}..{V0[:, 1].max() + BONE_T[1]:.0f}), x {V0[:, 0].min():.0f}..{V0[:, 0].max():.0f}; '
      f'MMD {len(m.build())} B', file=sys.stderr)

# ---------------------------------------------------------------- texture page
t = b.tex
t[:] = 0; t[..., 3] = 255

GREYS = [(8, 8, 8), (16, 16, 24), (32, 32, 40), (48, 48, 56), (64, 64, 72), (88, 88, 96), (112, 112, 128)]
PALE = [(144, 148, 160), (176, 180, 192), (200, 206, 216), (224, 228, 236), (248, 248, 248)]
YEL = [(40, 36, 16), (72, 64, 16), (200, 160, 24), (248, 208, 32)]
PINK = [(176, 64, 96), (240, 128, 160)]
WAVE = (160, 160, 168)
GREENS = [(48, 96, 32), (72, 128, 40), (96, 152, 44), (112, 168, 48), (136, 188, 52), (168, 208, 60), (184, 224, 80),
          (208, 232, 112), (224, 240, 152)]
PAL_FACE = np.array(GREYS + YEL + PINK + [WAVE], float)
PAL_BODY = np.array(GREYS + PALE + [(24, 24, 32)], float)
PAL_SPROUT = np.array(GREENS + [(8, 8, 8)], float)
assert len(PAL_FACE) <= 16 and len(PAL_BODY) <= 16 and len(PAL_SPROUT) <= 16


def snap(rgb, pal):
    d = ((rgb[..., None, :] - pal[None, None]) ** 2).sum(-1)
    return pal[d.argmin(-1)]


BALL_C = np.array([0.0, hy(0.45)])        # centre of the fuzz ball on the front (x_u, y)
U_SCALE = H / 130.0                        # stroke sizes were tuned on a 130-unit body


def sigmoid(x):
    return 1 / (1 + np.exp(-np.clip(x, -30, 30)))


def fuzz_top(theta):
    """y of the fuzz ball's upper boundary: higher at the front and back, lower at the sides (an arc from the front)."""
    return hy(0.70) - 0.077 * H * np.cos(np.radians(theta)) ** 2


def fuzz_bot(theta):
    return hy(0.07) - 0.0 * theta


def shell(theta, y):
    """S in 0..1: how pale (clear skin) the surface is at (theta deg, y), and the pale colour there."""
    th = theta
    f = (BOT - y) / H                                        # height fraction
    # only zones that are the same all around the body: the clear neck cone and a thin grey bottom rim (the painted
    # side gaps of round 2 showed as vertical walls under per-vertex lighting); plus one small glass highlight
    s_neck = sigmoid((-y + fuzz_top(th)) / (0.023 * H))
    s_bot = 0.8 * sigmoid((y - fuzz_bot(th)) / (0.02 * H))
    s_gloss = 0.7 * np.exp(-((th + 52) / 6.0) ** 2 - ((f - 0.64) / 0.04) ** 2)       # glass highlight, upper left
    parts = [s_neck, s_bot, s_gloss]
    neck_c = np.stack([np.interp(f, [0.70, 1.0], [196, 236])] * 3, -1) + np.array([0, 6, 16])
    cols = [neck_c, np.full(th.shape + (3,), (184, 190, 202), float), np.full(th.shape + (3,), (248, 248, 248), float)]
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
    k = U_SCALE
    while n < 2600:
        th = rng.uniform(-180, 180); y = rng.uniform(hy(0.885), hy(0.054))
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
        edge = min(1.0, L / (0.385 * H))
        f = (BOT - y) / H
        top = min(1.0, max(0.0, (f - 0.41) / 0.35))
        tr = math.exp(-((th - 40) / 55.0) ** 2 - ((f - 0.68) / 0.215) ** 2)
        bright = (0.12 + 0.22 * edge + 0.22 * top + 0.16 * tr) * rng.uniform(0.6, 1.35)
        out.append((x, y, dx, dy, (rng.uniform(2.5, 5.0) + 2.5 * edge) * k, rng.uniform(0.9, 1.4) * k, min(1.0, bright), 0))
        n += 1
    th = rng.uniform(-180, 180, 50000); y = rng.uniform(APEX + 6, BOT - 3, 50000)
    S, _ = shell(th, y)
    keep = (S > 0.25) & (S < 0.6) & (rng.random(50000) < r_of_y(y) / RMAX)
    th, y, S = th[keep], y[keep], S[keep]
    e = 1.0
    Sx, _ = shell(th + e, y); Sy, _ = shell(th, y + e)
    gx, gy = (Sx - S) / math.radians(e), (Sy - S) / e
    gx = gx / np.maximum(r_of_y(y), 1)
    g = np.hypot(gx, gy) + 1e-6
    for i in range(min(len(th), 800)):
        x = math.radians(th[i]) * float(r_of_y(y[i]))
        dx, dy = gx[i] / g[i], gy[i] / g[i]
        ang = rng.normal(0, 0.3)
        dx, dy = dx * math.cos(ang) - dy * math.sin(ang), dx * math.sin(ang) + dy * math.cos(ang)
        out.append((x - dx * 2.5 * k, float(y[i]) - dy * 2.5 * k, dx, dy, rng.uniform(5, 9) * k, rng.uniform(0.9, 1.4) * k,
                    rng.uniform(0.5, 1.0), 1))
    return out


STROKES = make_strokes()


def hair_fields(theta, y, slicer=None):
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
        cov = np.clip((w * 0.5 + 0.5 - perp) / 0.7, 0, 1) * ((along > -0.5) & (along < L))
        cov = cov * np.clip((L - along) / 1.6, 0, 1)
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
    hin, hedge = hair_fields(theta, y, slicer)
    f = (BOT - y) / H
    top = np.clip((f - 0.41) / 0.35, 0, 1)[..., None]
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

# ---- face frames: solid yellow discs (12 % of the width, gap 1.5 widths), tongue mouth under a grey wave
EYE_Y, EYE_R = hy(0.505), 0.06 * 2 * RMAX
EYE_X = 1.25 * 2 * EYE_R                    # centre offset from the axis: gap 1.5 eye widths
EYE = np.array([EYE_X, EYE_Y])
MOUTH_Y = hy(0.27)


def window_coords(w, sx, sy):
    """(theta, ground y) of every sub-sample of the frame copied to page position (sx, sy) of window w."""
    _, _, ww, hh = w['dst']
    U, V = grid(sx, sx + ww - 1, sy, sy + hh - 1)
    t0, t1 = float(t_of_s(RING_S[w['rings'][1]])), float(t_of_s(RING_S[w['rings'][0]]))
    theta = -FACE_HALF_DEG + (U - sx - 0.5) / (ww - 1) * 2 * FACE_HALF_DEG
    tt = t0 + (V - sy - 0.5) / (hh - 1) * (t1 - t0)
    return theta, y_of_t(np.clip(tt, 0, 1))


def soft(x, w=0.7):
    return np.clip(x / w + 0.5, 0, 1)


def eye_layer(theta, yy, kind):
    xu, yu = unroll(theta, yy)
    dx, dy = np.abs(xu) - EYE[0], yu - EYE[1]
    d = np.hypot(dx, dy)
    yellow = np.array((248, 208, 32), float); rim = np.array((200, 160, 24), float)
    colr = np.full(theta.shape + (3,), yellow)
    if kind in ('open', 'down', 'drowsy', 'blink'):
        if kind == 'down':
            d2 = np.hypot(dx, dy - 1.5)
            shape = soft(EYE_R - d2) * soft(dy + 1.0)
        else:
            shape = soft(EYE_R - d)
            if kind == 'drowsy': shape = shape * soft(dy - 1.0)
            if kind == 'blink': shape = shape * soft(dy + 0.5)
        edge = soft(d - (EYE_R - 1.3))
        colr = yellow * (1 - edge[..., None]) + rim * edge[..., None]
    elif kind == 'closed':
        shape = soft(1.3 - np.abs(d - (EYE_R - 1))) * soft(dy - 1.5)
        colr = np.full(theta.shape + (3,), rim)
    elif kind == 'happy':
        shape = soft(1.8 - np.abs(d - (EYE_R - 0.5))) * soft(-dy - 0.3)
    else:
        ax = EYE[0] - 3.5 if kind == 'strain' else EYE[0] - 2.8
        ay = 0.0 if kind == 'strain' else 0.8
        arm = np.abs((np.abs(xu) - ax) - 0.85 * np.abs(dy - ay))
        shape = soft(1.3 - arm) * soft(5.5 - np.abs(dy - ay)) * soft(np.abs(xu) - ax + 0.4)
    halo = np.clip((1.9 * EYE_R - d) / (0.9 * EYE_R), 0, 1) ** 1.6 * (0.55 if kind not in ('closed', 'drowsy') else 0.3)
    return shape, colr, halo


def mouth_layer(theta, yy, kind):
    """The closed mouth is a grey wavy upper-lip line (the 'moustache' of the art). An open mouth REPLACES it (no line
    above it): a dark cavity with a pink tongue at the bottom, so only one mouth is ever on the face."""
    xu, yu = unroll(theta, yy)
    dx, dy = np.abs(xu), yu - MOUTH_Y
    PINKC, DARK = np.array((240, 128, 160), float), np.array((176, 64, 96), float)
    W_HW = 0.15 * 2 * RMAX                                      # wave half width
    wave_y = -0.065 * H + 0.025 * H * np.cos(np.pi * np.clip(dx, 0, W_HW) / W_HW)
    wave = soft(1.4 - np.abs(dy - wave_y), 0.6) * soft(W_HW - dx, 1.2)
    sizes = {'open': (9, 5), 'blink': (9, 5), 'down': (7, 4), 'happy': (11, 7), 'strain': (6, 6), 'strain2': (11, 3.5),
             'drowsy': None, 'closed': None}[kind]
    if sizes is None:
        shape = np.zeros(theta.shape); colr = np.full(theta.shape + (3,), PINKC)
    else:
        rx, ry = sizes
        cy = -0.03 * H                                           # the cavity sits where the line was
        rr = np.hypot(dx / rx, (dy - cy) / ry)
        shape = soft(1 - rr, 0.12)
        if kind == 'happy': shape = shape * soft(dy - cy + 0.8)  # a D: flat top
        tongue = soft(1 - np.hypot(dx / (0.62 * rx), (dy - cy - 0.5 * ry) / (0.5 * ry)), 0.2)
        colr = DARK * (1 - tongue[..., None]) + PINKC * tongue[..., None]
        wave = wave * 0
    return shape, colr, wave


HALO_C = np.array((88, 76, 16), float)
WAVE_C = np.array(WAVE, float)
FACE_RECTS = []                      # every page rectangle that holds face pixels (the windows' own and every frame's)


def paint_window(w, sx, sy, eye_kind, mouth_kind):
    theta, yy = window_coords(w, sx, sy)
    base = paint_body(theta, yy)
    if eye_kind:
        eshape, ecol, halo = eye_layer(theta, yy, eye_kind)
        base = base * (1 - halo[..., None]) + HALO_C * halo[..., None]
        base = base * (1 - eshape[..., None]) + ecol * eshape[..., None]
    if mouth_kind:
        mshape, mcol, wave = mouth_layer(theta, yy, mouth_kind)
        base = base * (1 - wave[..., None]) + WAVE_C * wave[..., None]
        base = base * (1 - mshape[..., None]) + mcol * mshape[..., None]
    _, _, ww, hh = w['dst']
    t[sy:sy + hh, sx:sx + ww, :3] = snap(base.mean(axis=(2, 3)), PAL_FACE).astype(np.uint8)
    FACE_RECTS.append((sx, sx + ww, sy, sy + hh))


for w in CFG['windows']:
    paint_window(w, w['dst'][0], w['dst'][1], *w['base'])
    for sx, sy, ek, mk in w['frames']:
        paint_window(w, sx, sy, ek, mk)

# ---- leaf texture: yellow-green, darker edges, pale mid-vein, slightly lighter towards the tip
U, V = grid(LEAF_U0, LEAF_U1, LEAF_V0, LEAF_V1)
s = (U - LEAF_U0 - 1) / 45.0
q = (V - (LEAF_V0 + LEAF_V1 + 1) / 2) / ((LEAF_V1 - LEAF_V0) / 2)
base_c = ramp(np.clip(s, 0, 1), [(0, (84, 136, 40)), (0.4, (160, 204, 58)), (1, (184, 222, 84))])
edge = np.clip((np.abs(q) - 0.55) / 0.45, 0, 1)
col = base_c * (1 - edge[..., None]) + np.array((108, 164, 46), float) * edge[..., None]
rib = np.clip(1 - np.abs(q) / 0.09, 0, 1) * np.clip(s * 4, 0, 1) * np.clip((0.95 - s) * 8, 0, 1)
col = col * (1 - rib[..., None]) + np.array((212, 234, 128), float) * rib[..., None]
col = col * (1 + (np.clip(-q, 0, 1) * 0.06)[..., None])
t[LEAF_V0:LEAF_V1 + 1, LEAF_U0:LEAF_U1 + 1, :3] = snap(col.mean(axis=(2, 3)), PAL_SPROUT).astype(np.uint8)
U, V = grid(STEM_U0, STEM_U1, STEM_V0, STEM_V1)
a = (U - STEM_U0 - 0.5) / 15.0
sh = np.clip(0.55 + 0.45 * np.cos((a - 0.5) * 2 * np.pi), 0.3, 1.0) * (1 - 0.12 * (V - STEM_V0) / 23.0)
col = ramp(np.clip(sh, 0, 1), [(0, (60, 112, 36)), (0.6, (112, 168, 48)), (1, (160, 204, 60))])
t[STEM_V0:STEM_V1 + 1, STEM_U0:STEM_U1 + 1, :3] = snap(col.mean(axis=(2, 3)), PAL_SPROUT).astype(np.uint8)

# ---- encode the TIM ourselves: each region has its own CLUT row and a fixed palette
REGIONS = [(ROW_FACE, PAL_FACE, r) for r in FACE_RECTS] + [(ROW_BODY, PAL_BODY, (BODY_U0, BODY_U1 + 1, BODY_V0, BODY_V1 + 1)),
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
ICON_PAL = {'.': None, 'F': (8, 8, 8), 'f': (48, 48, 56), 'W': (200, 206, 216), 'w': (248, 248, 248), 'Y': (248, 208, 32),
            'o': (88, 76, 16), 'L': (160, 204, 58), 'R': (136, 188, 52), 'S': (72, 128, 40), 'P': (240, 128, 160)}


_used = np.zeros(t.shape[:2], int)
for _row, _pal, (_u0, _u1, _v0, _v1) in REGIONS:
    _used[_v0:_v1, _u0:_u1] += 1
_used[96:128, 224:256] += 1
assert _used.max() == 1, 'two page regions overlap (donor %d)' % DONOR


def encode_tim():
    tim = b.tim; W = tim.w
    tim.idx[:] = bytes(len(tim.idx))
    for row, pal, (u0, u1, v0, v1) in REGIONS:
        tim.pal[row] = [mmd.rgba_to_c15(*[int(c) for c in rgb]) for rgb in pal] + [0] * (16 - len(pal))
        sub = t[v0:v1, u0:u1, :3].astype(float)
        idx = ((sub[..., None, :] - pal[None, None]) ** 2).sum(-1).argmin(-1)
        for dy in range(v1 - v0):
            tim.idx[(v0 + dy) * W + u0:(v0 + dy) * W + u1] = bytes(int(i) for i in idx[dy])
    keys = list(ICON_PAL)
    tim.pal[15] = [0] + [mmd.rgba_to_c15(*ICON_PAL[k]) for k in keys[1:]] + [0] * (16 - len(keys))
    for f, (fu, fv) in enumerate(((224, 96), (240, 96), (224, 112), (240, 112))):
        for yy_, line in enumerate(ICON):
            for xx_, ch in enumerate(line):
                if f % 2 and ch == 'Y': ch = 'o'
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
    return f'{mp}:{DONOR}:{tp}:0:{NAME}'


spec = save()
print(spec)
if __name__ == '__main__' and '--sheet' in sys.argv:
    sheet(OUT + f'/{NAME}-sheet.png', [spec], panels='mesh:front,mesh:three,mesh:side')
