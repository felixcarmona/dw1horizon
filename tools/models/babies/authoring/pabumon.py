"""Pabumon (Fresh) on Punimon's skeleton and animations (type 15): everything else is new (round 3).

What the donor fixes, and what it cost:
- One TMD object on bone 2; bone 1 carries EVERY squash/stretch/hop (scale 0.45..1.9 in the idle alone), so nothing
  attached to the mesh can escape the squash. The art's free-floating bubbles are therefore not modelled (a detached
  bubble reads as a sprout at game size and would stretch with the body); the two big ones are hemispheres on the body.
- The floor ring sits at local y = 44 (the animations assume it). Slots 9/11 (sleep) roll the body onto its side and
  the bottom faces the camera all night: it is a closed fan painted as a belly (ring gradient + pale blobs).
- Texture-animation rectangles are immovable: eyes dst (8,4) 32x24 with sources at x = 48 (looking down, eating),
  80 (half-lidded), 112 (closed), 144 (pupil up), 176 (happy arch), 208 (open, the default); mouth dst (0,40) 16x24 with
  sources at x = 32..96, y = 32 (slot 8 cycles 96->32->96: the pacifier is pulled in and out).
- Winding: cross(v1-v0, v2-v0) points INWARD (checked on the donor's 234 faces); finish() asserts it on every triangle
  against an explicit per-face reference (the vertex-average reference is ambiguous on the rim's floor ring).
  The studio renderer shades flat per triangle and does not cull, so faceting in the sheets is the renderer's.

Mesh (276 primitives, 268 vertices, one object; Punimon has 234 / 119):
- A lathe with 16 non-uniform columns: three front columns [-40,-10] [-10,10] [10,40] so each eye is ONE cell 30 deg
  wide (34 units) x 24 units tall = the 32x24 eye rectangle mapped 1:1 (a 23 px dot = a 24-unit eye, 13 % of the
  width, centres at +-25 deg = a 1.3-diameter gap); 13 columns of 21.5 deg for the rest.
- Profile: crown leaning to the viewer's left and forward, the lower third convex (the belly bulges to the foot at
  r 73 = 0.8 of the width), then a THICK rounded rim 12 units high reaching 15-20 units beyond the foot, with a
  per-angle lobe table (back-heavy, a long drip right-back, a modest lobe under the pacifier). Closed bottom.
- Bubbles: hemispherical caps (8 segments, 3 bands) R 19 on the left crown and on the right side at eye height, two
  small ones (6 segments, 2 bands) top-right and back-right; rims pushed into the body along the cap axis.
- Pacifier: a shallow disc = spherical cap of R 17.5 up to 49 deg (26 units across, 6 proud) just left of the centre
  line below the eye line, facing forward and a little down; UV = normals projected onto the mouth rectangle, so the
  frames can slide the painted ring; a small knob cap on its upper-right.

Texture: painted procedurally from 3D (surface point + normal -> colour) so islands match; symmetric front-top light
(the eye rectangle is mirrored); a yellow-green ramp (#8FBF6A .. #DCEFC4), big soft white ovals on the upper-left of
the dome, a darker puddle edge; three palette rows chosen here, pixels snapped with a 2x2 ordered dither (kills the
banding of a 13-step ramp). Traps met earlier: mouth frames painted with page coordinates (nothing drawn); a sphere's
equator maps to u = cx + r, so UV radii must stay strictly inside their island; rect-local vs page coordinates.
"""
from lib import *
import math

b = Baby('Pabumon', 15)
tmd = b.m.tmd; ob = tmd.objects[0]
tmd.verts, tmd.norms, ob.prims = [], [], []
ob.vert_start = ob.norm_start = 0

ROW_FACE, ROW_BODY, ROW_BUB = 0, 1, 2
TSB = 5


def cba(row):
    return 0x7A00 + (row << 6)


# ------------------------------------------------------------------ mesh builder
V, NREF, FACES, FACE_REF, VN = [], [], [], [], []


def vert(p, nref):
    V.append(np.array(p, float)); NREF.append(np.array(nref, float)); VN.append(np.zeros(3))
    return len(V) - 1


def face(ids, uvs, row, ref=None):
    """Triangle or quad (quad corners: top-left, top-right, bottom-left, bottom-right; the TMD draws (0,1,2)(1,3,2)).
    ref: explicit outward direction for the orientation test (default: the sum of the vertices' references)."""
    FACES.append((list(ids), [(float(u), float(v)) for u, v in uvs], row))
    FACE_REF.append(None if ref is None else np.array(ref, float))


def finish():
    """Orient every face (cross must point inward), accumulate smooth normals, encode."""
    for fi, (ids, uvs, row) in enumerate(FACES):
        tris = [(0, 1, 2)] if len(ids) == 3 else [(0, 1, 2), (1, 3, 2)]
        ref = FACE_REF[fi] if FACE_REF[fi] is not None else sum(NREF[i] for i in ids)
        flips = sum(1 for t in tris if np.cross(V[ids[t[1]]] - V[ids[t[0]]], V[ids[t[2]]] - V[ids[t[0]]]) @ ref > 0)
        if flips == len(tris):
            if len(ids) == 3: ids = [ids[0], ids[2], ids[1]]; uvs = [uvs[0], uvs[2], uvs[1]]
            else: ids = [ids[1], ids[0], ids[3], ids[2]]; uvs = [uvs[1], uvs[0], uvs[3], uvs[2]]
        elif flips:
            raise SystemExit(f'face {fi}: inconsistent winding inside a quad {ids}')
        FACES[fi] = (ids, uvs, row)
        for t in tris:
            a, bb, c = (V[ids[k]] for k in t)
            n = -np.cross(bb - a, c - a)
            assert n @ ref >= 0, f'winding: face {fi} {ids} {t}'
            for k in t: VN[ids[k]] += n
    for fi, (ids, uvs, row) in enumerate(FACES):                  # independent check: side quads face away from the axis
        if len(ids) != 4 or FACE_REF[fi] is None or row == ROW_BUB or fi >= COLS * (len(RINGS) - 1) + COLS: continue
        for t in ((0, 1, 2), (1, 3, 2)):
            a, bb, c = (V[ids[k]] for k in t); cen = (a + bb + c) / 3
            radial = cen - lean_at(cen[1]); radial[1] = 0
            assert -np.cross(bb - a, c - a) @ radial > 0, f'side quad {fi} faces the axis (culled in-game)'
    for p, n in zip(V, VN):
        l = np.linalg.norm(n); n = n / l if l > 1e-9 else np.array([0, -1, 0.])
        tmd.verts.append((int(round(p[0])), int(round(p[1])), int(round(p[2])), 0))
        tmd.norms.append((int(round(4096 * n[0])), int(round(4096 * n[1])), int(round(4096 * n[2])), 0))
    ob.nvert = ob.nnorm = len(V)
    for ids, uvs, row in FACES:
        d = dict(mode=0x34 if len(ids) == 3 else 0x3C, flag=0, cba=cba(row), tsb=TSB, uvpad=[], colors=[], pad=[],
                 uv=[(min(255, max(0, int(round(u)))), min(127, max(0, int(round(v))))) for u, v in uvs],
                 verts=ids, norms=ids)
        ob.prims.append(mmd.Prim.encode(d))


# ------------------------------------------------------------------ body (y negative = up; floor y = 44)
TH = [-40.0, -10.0, 10.0] + [40.0 + k * 280.0 / 13 for k in range(13)]     # 16 column boundaries, deg, 0 = front (-Z)
TH = [((t + 180) % 360) - 180 for t in TH]
COLS = len(TH)
assert all(((TH[(j + 1) % COLS] - TH[j]) % 360) < 180 for j in range(COLS)), 'columns must advance monotonically'
L_EYE_COL, R_EYE_COL = 0, 2                                                # [-40,-10] and [10,40]
# rings crown -> floor: (y, r). Rows 3-4 = the eye cell (24 units of slant = the 24 px of the rectangle)
RINGS = [(-56, 26), (-48, 45), (-38, 58), (-30, 63), (-6, 69), (14, 72), (28, 73), (35, 81), (40, 90), (44, 86)]
POLE_Y, FLOOR_Y = -60, 44
EYE_T, EYE_B = 3, 4
LOBE_W = {7: 0.3, 8: 1.0, 9: 1.0}                                          # rim rings take the lobes
LOBE = [(-180, 1.08), (-150, 1.1), (-120, 0.98), (-90, 0.92), (-60, 0.95), (-35, 1.05), (-10, 0.93), (15, 0.9),
        (45, 0.95), (75, 0.92), (100, 1.08), (122, 1.18), (145, 1.12), (165, 1.05)]
LEAN = {-1: (-8, -4), 0: (-6, -3), 1: (-4, -2), 2: (-2, -1)}               # (x, z) shift of the crown rings


def lobes(th):
    th = (th + 180) % 360 - 180
    pts = LOBE + [(180, LOBE[0][1])]
    for (a, va), (bb_, vb) in zip(pts, pts[1:]):
        if a <= th <= bb_:
            f = (th - a) / (bb_ - a); return va * (1 - f) + vb * f
    return LOBE[0][1]


def dome_mod(th, y):
    t = math.radians(th)
    return 1 + 0.025 * math.sin(3 * t + 0.8) + 0.02 * math.sin(2 * t + 2.3)


def ring_radius(k, th):
    y, r = RINGS[k]
    if k in LOBE_W: return r * (1 + LOBE_W[k] * (lobes(th) - 1))
    return r * dome_mod(th, y)


def pos(th, y, r):
    t = math.radians(th)
    return np.array([r * math.sin(t), y, -r * math.cos(t)])


def profile_r(y):
    pts = [(POLE_Y, 0.0)] + RINGS
    for (y0, r0), (y1, r1) in zip(pts, pts[1:]):
        if y0 <= y <= y1:
            return r0 + ((y - y0) / (y1 - y0) if y1 != y0 else 0) * (r1 - r0)
    return RINGS[-1][1] if y > FLOOR_Y else 0.0


def surface_r(th, y):
    pts = [(POLE_Y, 0.0)] + RINGS
    for k, ((y0, r0), (y1, r1)) in enumerate(zip(pts, pts[1:])):
        if y0 <= y <= y1:
            f = (y - y0) / (y1 - y0) if y1 != y0 else 0
            ra = ring_radius(k - 1, th) if k >= 1 else 0.0
            return ra + f * (ring_radius(k, th) - ra)
    return 0.0


def profile_normal(k):
    """Outward normal of the profile at ring k (k = -1 pole) in (r, y) terms."""
    pts = [(POLE_Y, 0.0)] + RINGS + [(FLOOR_Y, 0.0)]
    i = k + 1
    (ya, ra), (yb, rb) = pts[i - 1], pts[i + 1]
    n = np.array([yb - ya, -(rb - ra)], float); n /= np.linalg.norm(n)
    return n if n[0] >= 0 else -n


def surface_normal(th, y):
    k = min(range(len(RINGS)), key=lambda i: abs(RINGS[i][0] - y))
    pn = profile_normal(k); t = math.radians(th)
    n0 = np.array([pn[0] * math.sin(t), pn[1], -pn[0] * math.cos(t)]); return n0 / np.linalg.norm(n0)


def lean_at(y):
    """(x, z) shift of the lathe at height y: the crown rings lean to the viewer's left and forward."""
    ys = [POLE_Y] + [RINGS[k][0] for k in range(3)] + [RINGS[3][0]]
    sx = [LEAN[-1][0], LEAN[0][0], LEAN[1][0], LEAN[2][0], 0.0]
    sz = [LEAN[-1][1], LEAN[0][1], LEAN[1][1], LEAN[2][1], 0.0]
    return np.array([np.interp(y, ys, sx), 0.0, np.interp(y, ys, sz)])


def inside(p, margin=0.0):
    x, y, z = p - lean_at(p[1])
    if y < POLE_Y or y > FLOOR_Y: return False
    th = math.degrees(math.atan2(x, -z))
    return math.hypot(x, z) <= surface_r(th, y) - margin


def push_dir(p):
    """Direction that takes a point into the body by the shortest way: minus the lathe's normal at its own (theta, y);
    straight down above the crown."""
    x, y, z = p
    if y < POLE_Y + 2: return np.array([0, 1.0, 0])
    return -surface_normal(math.degrees(math.atan2(x, -z)), y)


S = [0.0]
_pts = [(POLE_Y, 0.0)] + RINGS
for (y0, r0), (y1, r1) in zip(_pts, _pts[1:]):
    S.append(S[-1] + math.hypot(r1 - r0, y1 - y0))
S_TOTAL = S[-1]
BAND_V0, BAND_V1 = 64, 127


def ring_v(k):
    return BAND_V0 + (BAND_V1 - BAND_V0) * S[k + 1] / S_TOTAL


def th_u(th):
    """Page u of an angle: the front 180 deg get 192 px, the back 180 deg 64 px; continuous and monotonic."""
    th = (th + 180) % 360 - 180
    if abs(th) <= 90: return 96 + th / 90 * 96
    return 192 + ((th - 90) % 360) / 180 * 64


def u_th(u):
    if u < 192: return -90 + u / 192 * 180
    return 90 + (u - 192) / 64 * 180


def col_u_pair(j):
    u0, u1 = th_u(TH[j]), th_u(TH[(j + 1) % COLS])
    if u1 <= u0: u1 = 255.999
    return u0, u1


pole = vert((LEAN[-1][0], POLE_Y, LEAN[-1][1]), (0, -1, 0))
ring_ids = []
for k, (y, _) in enumerate(RINGS):
    pn = profile_normal(k); ids = []
    for j in range(COLS):
        th = TH[j]; t = math.radians(th)
        p = pos(th, y, ring_radius(k, th)) + lean_at(y)
        ids.append(vert(p, (pn[0] * math.sin(t), pn[1], -pn[0] * math.cos(t))))
    ring_ids.append(ids)
bottom = vert((0, FLOOR_Y, 0), (0, 1, 0))

for j in range(COLS):
    u0, u1 = col_u_pair(j)
    face([pole, ring_ids[0][j], ring_ids[0][(j + 1) % COLS]], [((u0 + u1) / 2, BAND_V0), (u0, ring_v(0)), (u1, ring_v(0))],
         ROW_BODY, ref=(0, -1, 0))

EYE_R = (8, 4, 39, 27)          # x0 y0 x1 y1 of the eye rectangle (inclusive texels)
MOUTH_R = (0, 40, 15, 63)
for k in range(len(RINGS) - 1):
    for j in range(COLS):
        a, bb = ring_ids[k][j], ring_ids[k][(j + 1) % COLS]
        c, d = ring_ids[k + 1][j], ring_ids[k + 1][(j + 1) % COLS]
        u0, u1 = col_u_pair(j); v0, v1 = ring_v(k), ring_v(k + 1)
        row = ROW_BODY; uv = [(u0, v0), (u1, v0), (u0, v1), (u1, v1)]
        (ya, ra), (yb, rb) = RINGS[k], RINGS[k + 1]
        sn = np.array([yb - ya, -(rb - ra)], float); sn = sn if sn[0] >= 0 else -sn
        tm = math.radians(TH[j] + ((TH[(j + 1) % COLS] - TH[j]) % 360) / 2)      # wrap-aware column centre
        ref = (sn[0] * math.sin(tm), sn[1], -sn[0] * math.cos(tm))
        if k == EYE_T and j == R_EYE_COL:
            x0, y0, x1, y1 = EYE_R; uv = [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]; row = ROW_FACE
        elif k == EYE_T and j == L_EYE_COL:                        # same orientation: both glints upper-left
            x0, y0, x1, y1 = EYE_R; uv = [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]; row = ROW_FACE
        face([a, bb, c, d], uv, row, ref=ref)

BOT = (176, 48, 15)             # underside patch: centre x, y and UV radius (island 160..191 x 32..63)
for j in range(COLS):
    t0, t1 = math.radians(TH[j]), math.radians(TH[(j + 1) % COLS])
    cx, cy, rr = BOT
    face([bottom, ring_ids[-1][j], ring_ids[-1][(j + 1) % COLS]],
         [(cx, cy), (cx + rr * math.sin(t0), cy - rr * math.cos(t0)), (cx + rr * math.sin(t1), cy - rr * math.cos(t1))],
         ROW_BODY, ref=(0, 1, 0))

# ------------------------------------------------------------------ caps (bubbles, pacifier)
BUB = (136, 48, 15.0)           # bubble patch: centre and UV radius (island 120..151 x 32..63)


def bub_uv(na, n1, n2):
    cx, cy, r = BUB
    return (min(cx + 15.4, max(cx - 15.9, cx + r * n1)), min(cy + 15.4, max(cy - 15.9, cy + r * n2)))


def frame_of(axis):
    """Tangent frame of an axis: t1 horizontal (screen-right-ish), t2 down-ish (+y)."""
    a = np.array(axis, float); a /= np.linalg.norm(a)
    t1 = np.cross([0, 1.0, 0], a) if abs(a[1]) < 0.9 else np.cross(a, [0, 0, 1.0])
    t1 /= np.linalg.norm(t1); t2 = np.cross(a, t1)
    if t2[1] < 0: t2 = -t2
    return a, t1, t2


def sphere_part(C, R, axis, polar, segs, snap=False, uvfn=bub_uv, row=ROW_BUB, inside_fn=None, push_fn=None):
    """Lat-long sphere/cap around axis; polar = ring angles (deg), 0 = apex, 180 = antipode. uvfn(n.a, n.t1, n.t2).
    snap: the last ring is pushed into the host (inside_fn) along push_fn(p) in 0.5 steps (the host's inward normal: a
    push along the cap axis slid rim vertices 20 units down the face and the cap's wall covered an eye)."""
    a, t1, t2 = frame_of(axis)
    inside_fn = inside_fn or (lambda p: inside(p, 1.5))
    push_fn = push_fn or push_dir
    uvn = lambda n: uvfn(float(n @ a), float(n @ t1), float(n @ t2))
    rings, nrm = [], []
    for ph in polar:
        ids, ns = [], []
        if ph in (0, 180):
            n = a if ph == 0 else -a; ids, ns = [vert(C + R * n, n)], [n]
        else:
            for s in range(segs):
                ps = 2 * math.pi * s / segs
                n = math.cos(math.radians(ph)) * a + math.sin(math.radians(ph)) * (math.cos(ps) * t1 + math.sin(ps) * t2)
                p = C + R * n
                if snap and ph == polar[-1]:
                    for _ in range(30):
                        if inside_fn(p): break
                        p = p + 0.5 * push_fn(p)
                ids.append(vert(p, n)); ns.append(n)
        rings.append(ids); nrm.append(ns)
    for k in range(len(rings) - 1):
        A, B, NA, NB = rings[k], rings[k + 1], nrm[k], nrm[k + 1]
        for s in range(segs):
            s1 = (s + 1) % segs
            if len(A) == 1: face([A[0], B[s], B[s1]], [uvn(NA[0]), uvn(NB[s]), uvn(NB[s1])], row)
            elif len(B) == 1: face([A[s], A[s1], B[0]], [uvn(NA[s]), uvn(NA[s1]), uvn(NB[0])], row)
            else: face([A[s], A[s1], B[s], B[s1]], [uvn(NA[s]), uvn(NA[s1]), uvn(NB[s]), uvn(NB[s1])], row)


def attach_cap(th, y, R, protrude, segs=8, polar=(0, 38, 72, 105), tilt=None, **kw):
    """A sphere of radius R whose centre sits protrude*R outside the surface point (th, y) along the normal."""
    P0 = pos(th, y, surface_r(th, y)) + lean_at(y); n0 = surface_normal(th, y)
    if tilt is not None: n0 = n0 + np.array(tilt, float); n0 /= np.linalg.norm(n0)
    C = P0 + n0 * (protrude * R)
    sphere_part(C, R, n0, polar, segs, snap=True, **kw)
    return C, n0


TWO = (0, 55, 105)
attach_cap(78, -16, 19, 0.5)                       # big bubble at the right edge, eye height
attach_cap(-58, -50, 19, 0.45)                     # big bubble on the left crown (footprint clear of the eye cell)
attach_cap(42, -52, 11, 0.35, segs=6, polar=TWO)   # small, top-right
attach_cap(135, -30, 11, 0.4, segs=6, polar=TWO)   # small, back-right

# pacifier: shallow disc just left of the centre line, below the eye line, facing forward and a little down
PAC_TH, PAC_Y, PAC_R, PAC_PHI = -14, 5, 17.5, 49
MX0, MY0, MX1, MY1 = MOUTH_R
MCX, MCY, MRU, MRV = 8.0, 12.0, 10.0, 15.0        # rect-local centre and UV radii: rim (sin 49 = .755) -> +-7.5 / +-11.3 px


def pac_uv(na, n1, n2):
    return (min(MX0 + 15.4, max(MX0, MX0 + MCX + MRU * n1)), min(MY0 + 23.4, max(MY0, MY0 + MCY + MRV * n2)))


PAC_C, PAC_N = attach_cap(PAC_TH, PAC_Y, PAC_R, -math.cos(math.radians(PAC_PHI)) + 0.08, segs=8, polar=(0, 25, PAC_PHI),
                          uvfn=pac_uv, row=ROW_FACE, tilt=(0.0, 0.18, -0.45))
_, pt1, pt2 = frame_of(PAC_N)
KNOB = (200, 36, 6.0)           # knob patch: centre and UV radius (island 193..207 x 29..43)
KC = PAC_C + PAC_R * (math.cos(math.radians(24)) * PAC_N + math.sin(math.radians(24)) * (0.7 * pt1 - 0.7 * pt2))
sphere_part(KC, 6.0, PAC_N, (0, 60, 120), 6, snap=True, uvfn=lambda na, n1, n2: (KNOB[0] + KNOB[2] * n1, KNOB[1] + KNOB[2] * n2),
            row=ROW_FACE, inside_fn=lambda p: np.linalg.norm(p - PAC_C) <= PAC_R - 0.5,
            push_fn=lambda p: (PAC_C - p) / np.linalg.norm(PAC_C - p))

finish()

# ------------------------------------------------------------------ texture
W, H = 256, 128
page = np.zeros((H, W, 3), float)
rowmap = np.full((H, W), ROW_BODY, np.int8)
RAMP = [(0, (112, 160, 84)), (0.3, (143, 191, 106)), (0.6, (185, 218, 150)), (0.85, (220, 239, 196)), (1, (238, 248, 222))]
WHITE = np.array([255, 255, 255.])
L = np.array([0.0, -0.8, -0.6]); L /= np.linalg.norm(L)
LB = np.array([-0.45, -0.7, -0.55]); LB /= np.linalg.norm(LB)
# gloss: (theta, y, radius, strength); big soft ovals on the upper-left of the dome, a few on the belly and rim
BLOOMS = [(-22, -52, 15, 0.9), (-2, -57, 11, 0.8), (-56, -20, 14, 0.7), (40, 6, 16, 0.8), (-45, 20, 12, 0.7),
          (20, 38, 16, 0.8), (-25, 40, 12, 0.7), (110, 38, 16, 0.8), (150, 0, 15, 0.6), (-120, 30, 13, 0.7), (75, 30, 12, 0.6)]


def smooth(x):
    x = np.clip(x, 0, 1); return x * x * (3 - 2 * x)


def rgb(t):
    return np.array(ramp(np.array([t]), RAMP)[0])


def paint_body(th, y, p, n):
    d = max(0.0, float(n @ L))
    t = 0.4 + 0.6 * d ** 0.9
    dth = (th + 180) % 360 - 180
    t -= 0.08 * smooth(1 - math.hypot(dth / 9.0, (y + 2) / 14.0))               # faint shade between the eyes (|th| < 9: never inside an eye cell)
    t -= 0.08 * smooth((y - 14) / 20.0) * smooth((40 - y) / 8.0)               # the mass darkens toward the rim
    if y >= 40: t -= 0.22 * smooth((y - 40) / 3.0)                               # darker puddle edge
    c = rgb(t)
    r_local = max(10.0, profile_r(y))
    for bth, by, br, bs in BLOOMS:
        dd = math.hypot(((th - bth + 180) % 360 - 180) * r_local / 57.3, y - by)
        w = min(0.95, 1.1 * bs * smooth(1 - dd / br) ** 2.0)
        c = c * (1 - w) + WHITE * w
    return c


def ring_interp(s):
    pts = [(POLE_Y, 0.0)] + RINGS
    for k in range(len(pts) - 1):
        if S[k] <= s <= S[k + 1]:
            f = (s - S[k]) / max(1e-9, S[k + 1] - S[k])
            (y0, r0), (y1, r1) = pts[k], pts[k + 1]
            na = profile_normal(k - 1) if k >= 1 else np.array([0.0, -1.0]); nb = profile_normal(k)
            n = na * (1 - f) + nb * f
            return y0 + f * (y1 - y0), r0 + f * (r1 - r0), n / np.linalg.norm(n)
    return RINGS[-1][0], RINGS[-1][1], np.array([1.0, 0.0])


# one row of the band = one arc-length step; the shading normal is smoothed along the profile (sigma ~8 units) so the
# lighting has no steps where the lathe's curvature changes between rings
ROWS = [ring_interp((yy + 0.5 - BAND_V0) / (BAND_V1 + 1 - BAND_V0) * S_TOTAL) for yy in range(BAND_V0, 128)]
_pn = np.array([r[2] for r in ROWS]); _k = np.exp(-0.5 * (np.arange(-6, 7) / 2.5) ** 2); _k /= _k.sum()
_pad = np.concatenate([np.repeat(_pn[:1], 6, 0), _pn, np.repeat(_pn[-1:], 6, 0)])
_sm = np.stack([np.convolve(_pad[:, i], _k, 'valid') for i in range(2)], 1)
_sm /= np.linalg.norm(_sm, axis=1, keepdims=True)
ROW_Y = np.array([r[0] for r in ROWS])


def band_normal(y):
    """Smoothed profile normal (r, y components) at height y."""
    return np.array([np.interp(y, ROW_Y, _sm[:, 0]), np.interp(y, ROW_Y, _sm[:, 1])])


for i, yy in enumerate(range(BAND_V0, 128)):
    y, r, _ = ROWS[i]; pn = _sm[i]
    for xx in range(W):
        th = u_th(xx + 0.5); t = math.radians(th)
        page[yy, xx] = paint_body(th, y, pos(th, y, r), np.array([pn[0] * math.sin(t), pn[1], -pn[0] * math.cos(t)]))
page[:BAND_V0] = rgb(0.75)


def cell_bg(x0, y0, x1, y1, th0, th1, ya, yb):
    out = np.zeros((y1 - y0 + 1, x1 - x0 + 1, 3))
    for yy in range(y0, y1 + 1):
        y = ya + (yy + 0.5 - y0) / (y1 + 1 - y0) * (yb - ya)
        for xx in range(x0, x1 + 1):
            th = th0 + (xx + 0.5 - x0) / (x1 + 1 - x0) * (th1 - th0)
            pn = band_normal(y); t = math.radians(th)
            out[yy - y0, xx - x0] = paint_body(th, y, pos(th, y, surface_r(th, y)), np.array([pn[0] * math.sin(t), pn[1], -pn[0] * math.cos(t)]))
    return out


INK, RING, GLINT = np.array([10, 12, 10.]), np.array([34, 52, 32.]), WHITE
EYE_BG = cell_bg(*EYE_R, TH[R_EYE_COL], TH[R_EYE_COL + 1], RINGS[EYE_T][0], RINGS[EYE_B][0])
_pn = band_normal(PAC_Y); _t = math.radians(PAC_TH)
PAC_BG = np.zeros((24, 16, 3)); PAC_BG[:] = paint_body(PAC_TH, PAC_Y, pos(PAC_TH, PAC_Y, surface_r(PAC_TH, PAC_Y)), np.array([_pn[0] * math.sin(_t), _pn[1], -_pn[0] * math.cos(_t)]))


def ellipse(img, cx, cy, rx, ry, col):
    h, w = img.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w]
    m = ((xs + 0.5 - cx) / rx) ** 2 + ((ys + 0.5 - cy) / ry) ** 2 <= 1.0
    img[m] = col
    return m


def stroke(img, f, xs, thick=3, col=INK):
    for xx in xs:
        yy = int(round(f(xx)))
        for dy in range(thick):
            if 0 <= yy + dy < img.shape[0]: img[yy + dy, xx] = col


def eye_frame(kind):
    """32x24: the biggest dot the rectangle allows (23 px), a dark ring, one glint upper-left; strokes 3 px."""
    img = EYE_BG.copy()
    cx, cy, r = 16.0, 12.0, 11.3
    if kind == 'open':
        ellipse(img, cx, cy, r + 0.6, r + 0.6, RING); ellipse(img, cx, cy, r - 1, r - 1, INK); ellipse(img, cx - 4, cy - 4.5, 2.6, 3.0, GLINT)
    elif kind == 'half':
        m = ellipse(img, cx, cy, r + 0.6, r + 0.6, RING); ellipse(img, cx, cy, r - 1, r - 1, INK)
        img[:8] = EYE_BG[:8]; img[8] = np.where(m[8][:, None], RING, EYE_BG[8])      # the lid, only across the eye
        ellipse(img, cx - 4, cy - 0.5, 2.2, 2.4, GLINT)
    elif kind == 'closed':                                                   # a soft smiling curve
        stroke(img, lambda x: 13 - 0.045 * (x - cx) ** 2, range(5, 28))
    elif kind == 'down':
        ellipse(img, cx, cy + 2.2, r - 0.4, r - 2.0, RING); ellipse(img, cx, cy + 2.2, r - 2, r - 3.5, INK); ellipse(img, cx - 4, cy - 1, 2.4, 2.6, GLINT)
    elif kind == 'up':
        ellipse(img, cx, cy - 1.5, r, r - 0.5, RING); ellipse(img, cx, cy - 1.5, r - 1.6, r - 2, INK); ellipse(img, cx - 3.5, cy - 6.5, 3.2, 3.4, GLINT)
    elif kind == 'happy':                                                    # ^ arch
        stroke(img, lambda x: 8 + 0.05 * (x - cx) ** 2, range(5, 28))
    return img


EYE_FRAMES = {(8, 4): 'open', (208, 0): 'open', (80, 0): 'half', (112, 0): 'closed', (48, 0): 'down', (144, 0): 'up', (176, 0): 'happy'}
for (x, y), kind in EYE_FRAMES.items():
    page[y:y + 24, x:x + 32] = eye_frame(kind); rowmap[y:y + 24, x:x + 32] = ROW_FACE

YEL, YEL_D, YEL_L, ORANGE = np.array([250, 228, 110.]), np.array([228, 190, 56.]), np.array([255, 248, 196.]), np.array([176, 112, 24.])


def mouth_frame(push):
    """The pacifier ring seen through the cap's normals: (x, y) <-> (n.t1, n.t2); push 0 = rest, 4 = pulled in."""
    img = PAC_BG.copy()
    h, w = img.shape[:2]
    shrink = 1 - 0.05 * push
    ox, oy = -0.08 * push, 0.1 * push                                        # slides down-left as it is pulled in
    for yy in range(h):
        for xx in range(w):
            n1, n2 = ((xx + 0.5 - MCX) / MRU - ox) / shrink, ((yy + 0.5 - MCY) / MRV - oy) / shrink
            n1t = n1 + 0.08 * push * n2                                       # a slight tilt
            q = n1t * n1t + n2 * n2
            if q > 0.60: continue
            if q > 0.42: img[yy, xx] = ORANGE; continue                       # outline ring
            c = YEL_L if q < 0.16 else YEL                                    # light centre, yellow ring
            if (n1t - 0.25) ** 2 + (n2 - 0.25) ** 2 < 0.07 and q >= 0.16: c = YEL_D
            img[yy, xx] = c
    return img


MOUTH_FRAMES = {(0, 40): 0, (96, 32): 0, (80, 32): 1, (64, 32): 2, (48, 32): 3, (32, 32): 4}
for (x, y), push in MOUTH_FRAMES.items():
    page[y:y + 24, x:x + 16] = mouth_frame(push); rowmap[y:y + 24, x:x + 16] = ROW_FACE

# knob patch
kx, ky, kr = KNOB
for yy in range(int(ky) - 7, int(ky) + 8):
    for xx in range(int(kx) - 7, int(kx) + 8):
        n1, n2 = (xx + 0.5 - kx) / kr, (yy + 0.5 - ky) / kr
        q = n1 * n1 + n2 * n2
        if q > 1.3: page[yy, xx] = YEL; rowmap[yy, xx] = ROW_FACE; continue
        if q > 0.86: c = ORANGE
        else:
            lit = -0.5 * n1 - 0.6 * n2 + 0.62 * math.sqrt(max(0, 1 - q))
            c = YEL_L if lit > 0.45 else (YEL if lit > 0.1 else YEL_D)
        page[yy, xx] = c; rowmap[yy, xx] = ROW_FACE

# bubble patch: a lit sphere by normal, glint upper-left, darker rim
cx, cy, rr = BUB
for yy in range(int(cy) - 16, int(cy) + 16):
    for xx in range(int(cx) - 16, int(cx) + 16):
        nx, ny = (xx + 0.5 - cx) / 16, (yy + 0.5 - cy) / 16
        q = nx * nx + ny * ny
        if q > 1: q = 1; nx, ny = nx / math.sqrt(nx * nx + ny * ny), ny / math.sqrt(nx * nx + ny * ny)
        n = np.array([nx, ny, -math.sqrt(max(0.0, 1 - nx * nx - ny * ny))])
        t = 0.4 + 0.6 * max(0.0, float(n @ LB)) ** 0.8 - 0.2 * smooth((q - 0.62) / 0.38)
        c = rgb(t)
        g = smooth((float(n @ LB) - 0.88) / 0.12) * 0.95
        page[yy, xx] = c * (1 - g) + WHITE * g; rowmap[yy, xx] = ROW_BUB

# underside patch: a belly, not cardboard (lighter centre, darker rim, pale blobs)
cx, cy, rr = BOT
for yy in range(int(cy) - 16, int(cy) + 16):
    for xx in range(int(cx) - 16, int(cx) + 16):
        d = math.hypot(xx + 0.5 - cx, yy + 0.5 - cy) / 16
        t = 0.55 - 0.35 * smooth(d) ** 1.5
        c = rgb(t)
        for bx, by, br in ((-5, -4, 5), (6, 3, 4), (-2, 7, 3)):
            w = 0.6 * smooth(1 - math.hypot(xx + 0.5 - cx - bx, yy + 0.5 - cy - by) / br)
            c = c * (1 - w) + WHITE * w
        page[yy, xx] = c; rowmap[yy, xx] = ROW_BODY

# ---- palettes (explicit) and snapping with a 2x2 ordered dither
PAL = {ROW_BODY: [tuple(rgb(t)) for t in np.linspace(0, 1, 13)] + [(248, 252, 244), (255, 255, 255), (84, 128, 66)],
       ROW_FACE: [tuple(rgb(t)) for t in np.linspace(0, 1, 13)[6:]] + [(255, 255, 255), tuple(INK), tuple(RING),
                                                                   tuple(YEL), tuple(YEL_D), tuple(YEL_L), tuple(ORANGE), (248, 252, 244), (210, 150, 40)],
       ROW_BUB: [tuple(rgb(t)) for t in np.linspace(0, 1, 11)] + [(246, 251, 240), (252, 254, 250), (255, 255, 255), (90, 138, 76), (120, 170, 100)]}


def c15(c):
    r, g, bb_ = (int(v) >> 3 for v in c)
    return (r | g << 5 | bb_ << 10) or 0x8000


tim = b.tim
idx = np.zeros((H, W), np.uint8)
final = np.zeros((H, W, 4), np.uint8); final[..., 3] = 255
BAYER = np.array([[-0.375, 0.125], [0.375, -0.125]])
dither = np.tile(BAYER, (H // 2, W // 2))[..., None] * 5.0
for row, cols in PAL.items():
    assert len(cols) <= 16
    tim.pal[row] = [c15(c) for c in cols] + [c15(cols[0])] * (16 - len(cols))
    disp = np.array([mmd.c15_to_rgba(c)[:3] for c in tim.pal[row]], float)
    m = rowmap == row
    px = page[m] + dither[m]
    k = ((px[:, None, :] - disp[None, :len(cols), :]) ** 2).sum(-1).argmin(1)
    idx[m] = k; final[m, :3] = disp[k]
tim.idx = bytearray(idx.flatten().tobytes())

os.makedirs(OUT, exist_ok=True)
mp, tp = os.path.join(OUT, 'Pabumon.MMD'), os.path.join(OUT, 'Pabumon.TIM')
blob = b.m.build()
open(mp, 'wb').write(blob); open(tp, 'wb').write(tim.to_bytes())
cv2.imwrite(os.path.join(OUT, 'Pabumon-tex.png'), cv2.resize(cv2.cvtColor(final, cv2.COLOR_RGBA2BGRA), None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST))
nq = sum(1 for f in FACES if len(f[0]) == 4); nt = len(FACES) - nq
Vb = np.array(V); print(f'# verts {len(V)} quads {nq} tris {nt} prims {nq + nt} MMD {len(blob)} B  extent x {Vb[:,0].min():.0f}..{Vb[:,0].max():.0f} y {Vb[:,1].min():.0f}..{Vb[:,1].max():.0f} z {Vb[:,2].min():.0f}..{Vb[:,2].max():.0f}', file=sys.stderr)
print(f'{mp}:15:{tp}:0:Pabumon')
