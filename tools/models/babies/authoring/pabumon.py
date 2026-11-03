"""Pabumon (Fresh) on Punimon's skeleton and animations (type 15): everything else is new (round 2).

What the donor fixes, and what it cost:
- One TMD object on bone 2; bone 1 carries EVERY squash/stretch/hop (scale 0.45..1.9 in the idle alone), so nothing
  attached to the mesh can escape the squash. That is why the art's free-floating bubbles are reduced to two tiny ones
  hugging the crown (the far-left one was dropped): a bubble far from the pivot would visibly stretch and fly.
- The floor ring sits at local y = 44 (the animations assume it). Slots 0xb/0x28 roll the body over: the bottom is a
  closed, dark-painted fan.
- Texture-animation rectangles are immovable: eyes dst (8,4) 32x24 with sources at x = 48 (looking down, eating),
  80 (half-lidded), 112 (closed), 144 (pupil up), 176 (happy arch), 208 (open, the default); mouth dst (0,40) 16x24 with
  sources at x = 32..96, y = 32 (eating cycles 96->80->64->48->32 and back). Every frame is repainted in the same style.
- Winding: cross(v1-v0, v2-v0) points INWARD (checked on the donor's 234 faces); finish() asserts it on every triangle.
  The studio renderer shades flat per triangle and does not cull, so faceting in the sheets is the renderer's.

Mesh (282 vertices, 208 quads + 86 triangles = 294 primitives in one object; the heaviest original object, Punimon
itself, has 234 primitives / 119 vertices):
- A lat-long mass, 16 columns of 22.5 deg, 10 rings + pole: the sides bulge and flow in one concave curve into the
  puddle (thick near the body, a knife edge at the floor, no lip ring), crown leaning to the viewer's left.
- Puddle: per-column radius table LOBE (big drips to the right-back, a lobe under the pacifier), growing to the edge.
- Eyes: one grid cell each (22.5 deg x 17 units, isotropic 1.2 px/unit) mapped to the eye rectangle, the left one
  mirrored in u.
- Pacifier: a protruding spherical cap at the viewer's left, low on the face (theta -27, y 12, R 16, axis tilted to
  the front), UV = its normals projected onto the mouth rectangle (unmirrored, so the frames can move the shield), plus
  a knob cap on its upper-right sampling a small yellow patch.
- Closed bottom (dark fan). Body quads carry an explicit orientation reference (the profile segment's normal): the
  knife-edge floor ring's vertex reference is ambiguous and twisted puddle quads failed the test otherwise.
- Attached bubbles: spherical caps (6-8 segments, 2-3 latitude bands) whose rim ring is pushed into the body along the
  cap axis until inside (no gap, no geometry inside); UV = normal projected onto one lit-sphere patch (glint upper-left).

Texture: painted procedurally from 3D (surface point + normal -> colour), so islands match at their borders; symmetric
key light from the front-top (the eye rectangle is mirrored); white gloss blooms placed in 3D; three palette rows with
their 16 colours chosen here and every pixel snapped to its row's palette (tex_import's quantiser never runs).
Traps met: the mouth frames were first painted with page coordinates (nothing drawn); a full sphere's equator maps to
u = cx + r, so the patch radius must stay strictly inside its island (bleed through the wrong palette otherwise).
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
V, NREF, FACES = [], [], []        # positions, reference outward direction per vertex, (ids, uvs, row)
VN = []                            # accumulated smooth normals


def vert(p, nref):
    V.append(np.array(p, float)); NREF.append(np.array(nref, float)); VN.append(np.zeros(3))
    return len(V) - 1


FACE_REF = []


def face(ids, uvs, row, ref=None):
    """Triangle or quad (quad corners: top-left, top-right, bottom-left, bottom-right, as the TMD draws (0,1,2)(1,3,2)).
    ref: explicit outward direction for the orientation test (default: the sum of the vertices' references)."""
    FACES.append((list(ids), [(float(u), float(v)) for u, v in uvs], row))
    FACE_REF.append(None if ref is None else np.array(ref, float))


def finish():
    """Orient every face by its vertices' reference direction, accumulate smooth normals, encode."""
    ids_all = []
    for fi, (ids, uvs, row) in enumerate(FACES):
        tris = [(0, 1, 2)] if len(ids) == 3 else [(0, 1, 2), (1, 3, 2)]
        ref = FACE_REF[fi] if FACE_REF[fi] is not None else sum(NREF[i] for i in ids)
        flips = 0
        for t in tris:
            a, bb, c = (V[ids[k]] for k in t)
            n = np.cross(bb - a, c - a)
            if n @ ref > 0:          # cross must point inward (donor convention): outward-pointing cross = flip
                flips += 1
        if flips == len(tris):       # flip the whole primitive
            if len(ids) == 3:
                ids = [ids[0], ids[2], ids[1]]; uvs = [uvs[0], uvs[2], uvs[1]]
            else:
                ids = [ids[1], ids[0], ids[3], ids[2]]; uvs = [uvs[1], uvs[0], uvs[3], uvs[2]]
        elif flips:
            raise SystemExit(f'face {fi}: inconsistent winding inside a quad {ids}')
        FACES[fi] = (ids, uvs, row)
        for t in tris:
            a, bb, c = (V[ids[k]] for k in t)
            n = -np.cross(bb - a, c - a)             # outward, area weighted
            for k in t:
                VN[ids[k]] += n
    # hard check: every emitted triangle's cross points inward relative to the vertex references
    for fi2, (ids, uvs, row) in enumerate(FACES):
        tris = [(0, 1, 2)] if len(ids) == 3 else [(0, 1, 2), (1, 3, 2)]
        for t in tris:
            a, bb, c = (V[ids[k]] for k in t)
            ref = FACE_REF[fi2] if FACE_REF[fi2] is not None else sum(NREF[ids[k]] for k in t)
            s = np.cross(bb - a, c - a) @ ref
            assert s <= 0, f'winding: face {fi2} {ids} {t} {s}'
    for p, n in zip(V, VN):
        l = np.linalg.norm(n)
        n = n / l if l > 1e-9 else np.array([0, -1, 0.])
        tmd.verts.append((int(round(p[0])), int(round(p[1])), int(round(p[2])), 0))
        tmd.norms.append((int(round(4096 * n[0])), int(round(4096 * n[1])), int(round(4096 * n[2])), 0))
    ob.nvert = ob.nnorm = len(V)
    for ids, uvs, row in FACES:
        d = dict(mode=0x34 if len(ids) == 3 else 0x3C, flag=0, cba=cba(row), tsb=TSB, uvpad=[], colors=[], pad=[],
                 uv=[(min(255, max(0, int(round(u)))), min(127, max(0, int(round(v))))) for u, v in uvs],
                 verts=ids, norms=ids)
        ob.prims.append(mmd.Prim.encode(d))


# ------------------------------------------------------------------ body profile (y negative = up; floor y = 44)
COLS = 16
TH = [-180 + 22.5 * j for j in range(COLS)]                    # column boundaries (deg); 0 = front (-Z)
# rings from the crown to the floor edge: (y, r). One continuous profile: the sides bulge, then flow in a concave
# curve into the puddle, thick near the body and a knife edge at the floor. Rows 3-4 = eye cell.
RINGS = [(-55, 30), (-47, 48), (-36, 61), (-19, 68.5), (-3, 72), (13, 74), (25, 79), (33, 89), (39, 101), (44, 110)]
POLE_Y, FLOOR_Y = -60, 44
EYE_T, EYE_B = 2, 3                                             # ring indices bounding the eye cell
SKIRT0 = 6                                                      # first ring with lobes
# puddle lobes per column (radius multiplier at the floor edge): big drips to the right-back, one under the pacifier
LOBE = {-180: 0.92, -157.5: 1.02, -135: 0.9, -112.5: 1.03, -90: 0.94, -67.5: 0.9, -45: 1.04, -22.5: 1.14,
        0: 0.97, 22.5: 0.9, 45: 1.0, 67.5: 0.94, 90: 1.12, 112.5: 1.27, 135: 1.1, 157.5: 0.95}
LOBE_W = {6: 0.12, 7: 0.4, 8: 0.75, 9: 1.0}                      # how much of the lobe each puddle ring takes


def lobes(th):
    """Puddle radius multiplier at angle th (linear between the column values)."""
    th = (th + 180) % 360 - 180
    keys = sorted(LOBE)
    for a, b in zip(keys, keys[1:] + [180]):
        if a <= th <= b:
            f = (th - a) / (b - a)
            return LOBE[a] * (1 - f) + LOBE[b if b < 180 else -180] * f
    return LOBE[-180]


def dome_mod(th, y):
    """Gentle lumpiness of the mound."""
    t = math.radians(th)
    return 1 + 0.03 * math.sin(3 * t + 0.8) + 0.025 * math.sin(2 * t + 2.3)


def ring_radius(k, th):
    y, r = RINGS[k]
    if k >= SKIRT0:
        return r * (1 + LOBE_W[k] * (lobes(th) - 1))
    return r * dome_mod(th, y)


def pos(th, y, r):
    t = math.radians(th)
    return np.array([r * math.sin(t), y, -r * math.cos(t)])


def profile_r(y):
    """Body radius at height y (base profile, no modulation), 0 at the pole."""
    pts = [(POLE_Y, 0.0)] + RINGS
    for (y0, r0), (y1, r1) in zip(pts, pts[1:]):
        if y0 <= y <= y1:
            f = (y - y0) / (y1 - y0) if y1 != y0 else 0
            return r0 + f * (r1 - r0)
    return RINGS[-1][1] if y > FLOOR_Y else 0.0


def surface_r(th, y):
    """Modulated body radius at (theta, y): which ring band holds y decides the modulation."""
    pts = [(POLE_Y, 0.0)] + RINGS
    for k, ((y0, r0), (y1, r1)) in enumerate(zip(pts, pts[1:])):
        if y0 <= y <= y1:
            f = (y - y0) / (y1 - y0) if y1 != y0 else 0
            ra = ring_radius(k - 1, th) if k >= 1 else 0.0
            rb = ring_radius(k, th)
            return ra + f * (rb - ra)
    return 0.0


def profile_normal(k):
    """Outward normal of the profile at ring k in (r, y) terms."""
    pts = [(POLE_Y, 0.0)] + RINGS + [(FLOOR_Y, 0.0)]
    i = k + 1
    (ya, ra), (yb, rb) = pts[i - 1], pts[i + 1]
    tr, ty = rb - ra, yb - ya
    n = np.array([ty, -tr], float); n /= np.linalg.norm(n)
    if n[0] < 0: n = -n
    return n


def inside(p, margin=0.0):
    x, y, z = p
    if y < POLE_Y or y > FLOOR_Y: return False
    th = math.degrees(math.atan2(x, -z))
    return math.hypot(x, z) <= surface_r(th, y) - margin


# arc length per ring for the v coordinate of the body band
S = [0.0]
pts = [(POLE_Y, 0.0)] + RINGS
for (y0, r0), (y1, r1) in zip(pts, pts[1:]):
    S.append(S[-1] + math.hypot(r1 - r0, y1 - y0))
S_TOTAL = S[-1]
BAND_V0, BAND_V1 = 64, 127


def ring_v(k):            # k = -1 pole
    return BAND_V0 + (BAND_V1 - BAND_V0) * S[k + 1] / S_TOTAL


def col_u(j):             # u at column boundary j (0..16); front band columns 4..12 -> 0..192, back -> 192..255
    j = j % COLS
    if 4 <= j <= 12:
        return (j - 4) * 24.0
    jj = (j - 12) % COLS
    return 192 + jj * 8.0


def col_u_pair(j):
    """u at the left and right boundary of column j, handling the wrap at the page edge."""
    u0, u1 = col_u(j), col_u(j + 1)
    if u1 < u0: u1 = 255.999
    return u0, u1


# ---- vertices
LEAN = {-1: -7.0, 0: -5.0, 1: -3.0}                   # x shift per ring (crown leans to the viewer's left)
pole = vert((LEAN[-1], POLE_Y, 0), (0, -1, 0))
ring_ids = []
for k, (y, _) in enumerate(RINGS):
    pn = profile_normal(k)
    ids = []
    for j in range(COLS):
        th = TH[j]
        r = ring_radius(k, th)
        p = pos(th, y, r) + np.array([LEAN.get(k, 0.0), 0, 0])
        t = math.radians(th)
        nref = np.array([pn[0] * math.sin(t), pn[1], -pn[0] * math.cos(t)])
        ids.append(vert(p, nref))
    ring_ids.append(ids)
bottom = vert((0, FLOOR_Y, 0), (0, 1, 0))

# ---- faces: pole fan
for j in range(COLS):
    u0, u1 = col_u_pair(j)
    face([pole, ring_ids[0][j], ring_ids[0][(j + 1) % COLS]], [((u0 + u1) / 2, BAND_V0), (u0, ring_v(0)), (u1, ring_v(0))], ROW_BODY, ref=(0, -1, 0))

EYE_R = (8, 4, 39, 27)          # x0 y0 x1 y1 of the eye rectangle (inclusive texels)
MOUTH_R = (0, 40, 15, 63)
R_EYE_COL, L_EYE_COL = 9, 6                       # columns [22.5, 45] and [-45, -22.5]... see TH: 9 -> 22.5 deg

for k in range(len(RINGS) - 1):
    for j in range(COLS):
        a, bb = ring_ids[k][j], ring_ids[k][(j + 1) % COLS]
        c, d = ring_ids[k + 1][j], ring_ids[k + 1][(j + 1) % COLS]
        u0, u1 = col_u_pair(j)
        v0, v1 = ring_v(k), ring_v(k + 1)
        row = ROW_BODY
        uv = [(u0, v0), (u1, v0), (u0, v1), (u1, v1)]
        (ya, ra), (yb, rb) = RINGS[k], RINGS[k + 1]
        sn = np.array([yb - ya, -(rb - ra)], float)
        if sn[0] < 0: sn = -sn
        tm = math.radians(TH[j] + 11.25)
        ref = (sn[0] * math.sin(tm), sn[1], -sn[0] * math.cos(tm))
        if k == EYE_T and j == R_EYE_COL:
            x0, y0, x1, y1 = EYE_R
            uv = [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]; row = ROW_FACE
        elif k == EYE_T and j == L_EYE_COL:                        # mirrored
            x0, y0, x1, y1 = EYE_R
            uv = [(x1, y0), (x0, y0), (x1, y1), (x0, y1)]; row = ROW_FACE
        face([a, bb, c, d], uv, row, ref=ref)

# ---- bottom fan (dark patch)
BOT = (176, 44, 7)              # centre x, y, radius of the underside patch
for j in range(COLS):
    t0, t1 = math.radians(TH[j]), math.radians(TH[(j + 1) % COLS])
    cx, cy, rr = BOT
    face([bottom, ring_ids[-1][j], ring_ids[-1][(j + 1) % COLS]],
         [(cx, cy), (cx + rr * math.sin(t0), cy - rr * math.cos(t0)), (cx + rr * math.sin(t1), cy - rr * math.cos(t1))], ROW_BODY, ref=(0, 1, 0))

# ------------------------------------------------------------------ bubbles
BUB = (136, 48, 15.0)           # bubble patch: centre x, y and UV radius on the page (the island is 32x32: stay inside it)


def bub_uv(n):
    cx, cy, r = BUB
    return (min(cx + 15.4, max(cx - 15.9, cx + r * n[0])), min(cy + 15.4, max(cy - 15.9, cy + r * n[1])))


def surface_normal(th, y):
    k = min(range(len(RINGS)), key=lambda i: abs(RINGS[i][0] - y))
    pn = profile_normal(k); t = math.radians(th)
    n0 = np.array([pn[0] * math.sin(t), pn[1], -pn[0] * math.cos(t)]); return n0 / np.linalg.norm(n0)


def frame_of(axis):
    """Right-handed tangent frame of an axis: t1 = screen-right-ish (horizontal), t2 = down-ish."""
    a = np.array(axis, float); a /= np.linalg.norm(a)
    t1 = np.cross([0, 1.0, 0], a) if abs(a[1]) < 0.9 else np.cross(a, [0, 0, 1.0])
    t1 /= np.linalg.norm(t1); t2 = np.cross(a, t1)
    if t2[1] < 0: t2 = -t2          # +y is down in model space: make t2 point down
    return a, t1, t2


def sphere_part(C, R, axis, polar, segs, snap=False, uvfn=None, row=ROW_BUB, inside_fn=None):
    """Lat-long sphere (or cap) around axis (unit, apex direction); polar = ring angles in deg, the first may be 0 (apex).
    uvfn(n_axis, n_t1, n_t2) gives the UV of a vertex from its normal in the cap's frame."""
    a, t1, t2 = frame_of(axis)
    inside_fn = inside_fn or (lambda p: inside(p, 1.5))
    if uvfn is None: uvfn = lambda na, n1, n2: bub_uv(np.array([n1, n2, 0]))
    uvfn_n = lambda n: uvfn(float(n @ a), float(n @ t1), float(n @ t2))
    rings, nrm = [], []
    for ph in polar:
        ids, ns = [], []
        if ph == 0 or ph == 180:
            n = a if ph == 0 else -a
            ids = [vert(C + R * n, n)] ; ns = [n]
        else:
            for s in range(segs):
                ps = 2 * math.pi * s / segs
                n = math.cos(math.radians(ph)) * a + math.sin(math.radians(ph)) * (math.cos(ps) * t1 + math.sin(ps) * t2)
                p = C + R * n
                if snap and ph == polar[-1]:                   # push the rim into the body along -a
                    for step in range(60):
                        if inside_fn(p): break
                        p = p - 0.5 * a
                ids.append(vert(p, n)); ns.append(n)
        rings.append(ids); nrm.append(ns)
    for k in range(len(rings) - 1):
        A, B, NA, NB = rings[k], rings[k + 1], nrm[k], nrm[k + 1]
        if len(A) == 1:
            for s in range(segs):
                s1 = (s + 1) % segs
                face([A[0], B[s], B[s1]], [uvfn_n(NA[0]), uvfn_n(NB[s]), uvfn_n(NB[s1])], row)
        elif len(B) == 1:
            for s in range(segs):
                s1 = (s + 1) % segs
                face([A[s], A[s1], B[0]], [uvfn_n(NA[s]), uvfn_n(NA[s1]), uvfn_n(NB[0])], row)
        else:
            for s in range(segs):
                s1 = (s + 1) % segs
                face([A[s], A[s1], B[s], B[s1]], [uvfn_n(NA[s]), uvfn_n(NA[s1]), uvfn_n(NB[s]), uvfn_n(NB[s1])], row)


def attach_cap(th, y, R, protrude, segs=8, polar=(0, 40, 75, 105), tilt=None, **kw):
    P0 = pos(th, y, surface_r(th, y))
    n0 = surface_normal(th, y)
    if tilt is not None: n0 = n0 + np.array(tilt, float); n0 /= np.linalg.norm(n0)
    C = P0 + n0 * (protrude * R)
    sphere_part(C, R, n0, polar, segs, snap=True, **kw)
    return C, n0


# attached bubbles: (theta, y, radius, protrude)
TWO, THREE = (0, 52, 105), (0, 38, 72, 105)            # latitude bands: apex fan + 1 or 2 quad rings
attach_cap(70, -22, 20, 0.5, segs=8, polar=THREE)      # big cheek bubble, viewer's right edge
attach_cap(-48, -48, 17, 0.36, segs=8, polar=THREE)    # crown, viewer's left
attach_cap(44, -50, 12, 0.28, segs=6, polar=TWO)       # crown, right
attach_cap(104, -2, 9, 0.45, segs=6, polar=TWO)        # right shoulder, behind the cheek
# one small free bubble hugging the crown (it must squash with bone 1 like everything else)
sphere_part(np.array([22, -76, -12.0]), 8, (0, -1, 0), (0, 60, 120, 180), 6)

# ---- pacifier: a protruding shield cap (mapped to the mouth rectangle by its normals) and a knob cap on it
PAC_TH, PAC_Y, PAC_R = -26, 14, 16
MX0, MY0, MX1, MY1 = MOUTH_R
MCX, MCY, MRU, MRV = (MX0 + MX1 + 1) / 2, (MY0 + MY1 + 1) / 2, 7.5, 11.5


def pac_uv(na, n1, n2):
    return (MCX + MRU * n1, MCY + MRV * n2)


PAC_C, PAC_N = attach_cap(PAC_TH, PAC_Y, PAC_R, 0.38, segs=8, polar=(0, 45, 86), uvfn=pac_uv, row=ROW_FACE, tilt=(0.15, 0.1, -0.6))
_, pt1, pt2 = frame_of(PAC_N)
KNOB = (200, 36, 6)                    # knob patch: centre x, y, radius on the page
KC = PAC_C + PAC_R * (0.74 * PAC_N + 0.46 * pt1 - 0.5 * pt2)
sphere_part(KC, 7.5, PAC_N, (0, 60, 120), 6, snap=True, uvfn=lambda na, n1, n2: (KNOB[0] + KNOB[2] * n1, KNOB[1] + KNOB[2] * n2),
            row=ROW_FACE, inside_fn=lambda p: np.linalg.norm(p - PAC_C) <= PAC_R - 0.5)

finish()

# ------------------------------------------------------------------ texture
W, H = 256, 128
page = np.zeros((H, W, 3), float)
rowmap = np.full((H, W), ROW_BODY, np.int8)

RAMP = [(0, (108, 160, 90)), (0.35, (160, 208, 134)), (0.65, (204, 236, 176)), (0.85, (230, 246, 212)), (1, (244, 252, 236))]
WHITE = np.array([255, 255, 255.])
L = np.array([0.0, -0.8, -0.6]); L /= np.linalg.norm(L)                    # key light: front-top (symmetric: the eye rect is mirrored)
LB = np.array([-0.45, -0.7, -0.55]); LB /= np.linalg.norm(LB)               # bubbles: upper-left glint like the art

BLOOMS = [(40, 4, 19, 0.95), (-50, 12, 14, 0.85), (16, 37, 20, 0.95), (-34, 40, 14, 0.9), (72, 30, 14, 0.8),
          (-8, -50, 22, 0.6), (150, 0, 16, 0.7), (-120, 28, 15, 0.8), (112, 40, 20, 0.9), (-72, 40, 13, 0.8),
          (2, 18, 9, 0.7), (-150, 40, 12, 0.7)]


def smooth(x):
    x = np.clip(x, 0, 1); return x * x * (3 - 2 * x)


def paint_body(th, y, p, n):
    d = max(0.0, float(n @ L))
    t = 0.42 + 0.58 * d ** 0.9
    # nose-bridge shade between the eyes
    dth = (th - 2 + 180) % 360 - 180
    w = smooth(1 - math.hypot(dth / 12.0, (y + 12) / 15.0))
    t -= 0.1 * w
    # the mass gets a little greener where it thickens into the puddle (ambient shadow), never a line
    t -= 0.07 * smooth((y - 10) / 22.0) * smooth((40 - y) / 10.0)
    c = np.array(ramp(np.array([t]), RAMP)[0])
    r_local = max(10.0, profile_r(y))
    for bth, by, br, bs in BLOOMS:
        dd = math.hypot(((th - bth + 180) % 360 - 180) * r_local / 57.3, y - by)
        wgt = min(0.95, 1.1 * bs * smooth(1 - dd / br) ** 2.5)
        c = c * (1 - wgt) + WHITE * wgt
    return c


def ring_interp(s):
    """Arc length from the pole -> (y, base r, normal in (r, y))."""
    pts = [(POLE_Y, 0.0)] + RINGS
    for k in range(len(pts) - 1):
        if S[k] <= s <= S[k + 1]:
            f = (s - S[k]) / max(1e-9, S[k + 1] - S[k])
            (y0, r0), (y1, r1) = pts[k], pts[k + 1]
            na = profile_normal(k - 1) if k >= 1 else np.array([0.0, -1.0])
            nb = profile_normal(k)
            n = na * (1 - f) + nb * f
            return y0 + f * (y1 - y0), r0 + f * (r1 - r0), n / np.linalg.norm(n)
    return RINGS[-1][0], RINGS[-1][1], np.array([1.0, 0.0])


def u_to_th(u):
    if u < 192: return -90 + u / 192 * 180
    return 90 + (u - 192) / 64 * 180


# body band
for yy in range(BAND_V0, 128):
    s = (yy + 0.5 - BAND_V0) / (BAND_V1 + 1 - BAND_V0) * S_TOTAL
    y, r, pn = ring_interp(s)
    for xx in range(W):
        th = u_to_th(xx + 0.5)
        t = math.radians(th)
        n = np.array([pn[0] * math.sin(t), pn[1], -pn[0] * math.cos(t)])
        p = pos(th, y, r)
        page[yy, xx] = paint_body(th, y, p, n)
        rowmap[yy, xx] = ROW_BODY

# fill the rest with mid green (bleed guard), then the islands
page[:BAND_V0] = ramp(np.full((BAND_V0, W), 0.7), RAMP)


def cell_bg(x0, y0, x1, y1, th0, th1, ya, yb, mirror=False):
    """Paint a rectangle with the body colour of the cell it is mapped on."""
    out = np.zeros((y1 - y0 + 1, x1 - x0 + 1, 3))
    for yy in range(y0, y1 + 1):
        fy = (yy + 0.5 - y0) / (y1 + 1 - y0)
        y = ya + fy * (yb - ya)
        for xx in range(x0, x1 + 1):
            fx = (xx + 0.5 - x0) / (x1 + 1 - x0)
            if mirror: fx = 1 - fx
            th = th0 + fx * (th1 - th0)
            r = surface_r(th, y)
            k = min(range(len(RINGS)), key=lambda i: abs(RINGS[i][0] - y))
            pn = profile_normal(k); t = math.radians(th)
            n = np.array([pn[0] * math.sin(t), pn[1], -pn[0] * math.cos(t)])
            out[yy - y0, xx - x0] = paint_body(th, y, pos(th, y, r), n)
    return out


INK = np.array([14, 16, 14.])
GLINT = WHITE
EYE_BG = cell_bg(*EYE_R, TH[R_EYE_COL], TH[R_EYE_COL + 1], RINGS[EYE_T][0], RINGS[EYE_B][0])
PAC_BG = np.zeros((24, 16, 3)); PAC_BG[:] = paint_body(PAC_TH, PAC_Y, pos(PAC_TH, PAC_Y, surface_r(PAC_TH, PAC_Y)), surface_normal(PAC_TH, PAC_Y))


def ellipse(img, cx, cy, rx, ry, col, aa=True):
    h, w = img.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w]
    d = ((xs + 0.5 - cx) / rx) ** 2 + ((ys + 0.5 - cy) / ry) ** 2
    m = d <= 1.0
    img[m] = col
    return m


def eye_frame(kind):
    img = EYE_BG.copy()
    # the dot: 14 units -> 14 px wide, 20 px tall; centre at the eye position inside the cell
    cx, cy, rx, ry = 16.0, 12.0, 10.0, 9.6
    if kind == 'open':
        ellipse(img, cx, cy, rx, ry, INK); ellipse(img, cx - 3.0, cy - 4.8, 2.1, 2.9, GLINT)
    elif kind == 'half':
        m = ellipse(img, cx, cy, rx, ry, INK)
        img[:int(cy - 2)] = EYE_BG[:int(cy - 2)]                          # lid
        img[int(cy - 2)] = np.where(m[int(cy - 2)][:, None], INK * 0.5 + EYE_BG[int(cy - 2)] * 0.5, img[int(cy - 2)])
        ellipse(img, cx - 2.5, cy + 0.5, 1.4, 1.6, GLINT)
    elif kind == 'closed':                                                   # a soft smile curve
        for xx in range(int(cx - 7), int(cx + 8)):
            yy = cy + 2 - 0.09 * (xx - cx) ** 2
            img[int(round(yy)), xx] = INK; img[int(round(yy)) + 1, xx] = INK
    elif kind == 'down':
        ellipse(img, cx, cy + 2, rx, ry * 0.9, INK); ellipse(img, cx - 2.5, cy - 2, 1.6, 2.2, GLINT)
    elif kind == 'up':
        ellipse(img, cx, cy - 1, rx * 0.95, ry * 0.95, INK); ellipse(img, cx - 2, cy - 6, 2.4, 3.0, GLINT)
    elif kind == 'happy':                                                    # ^ arch
        for xx in range(int(cx - 7), int(cx + 8)):
            yy = cy - 3 + 0.11 * (xx - cx) ** 2
            for dy in (0, 1, 2):
                if 0 <= int(round(yy)) + dy < img.shape[0]: img[int(round(yy)) + dy, xx] = INK
    return img


EYE_FRAMES = {(8, 4): 'open', (208, 0): 'open', (80, 0): 'half', (112, 0): 'closed', (48, 0): 'down', (144, 0): 'up', (176, 0): 'happy'}
for (x, y), kind in EYE_FRAMES.items():
    page[y:y + 24, x:x + 32] = eye_frame(kind)
    rowmap[y:y + 24, x:x + 32] = ROW_FACE

YEL, YEL_D, YEL_L, BROWN = np.array([250, 232, 118.]), np.array([226, 190, 60.]), np.array([255, 250, 205.]), np.array([116, 86, 28.])


def mouth_frame(push):
    """The pacifier shield seen through the cap's normals: (x, y) <-> (n.t1, n.t2). Outline at the rim, lit from the
    upper-left, a gloss spot; push = sucking pulse 0..4 (the yellow disc sinks and the gloss slides)."""
    img = PAC_BG.copy()
    h, w = img.shape[:2]
    for yy in range(h):
        for xx in range(w):
            n1, n2 = (xx + 0.5 - (MCX - MX0)) / MRU, (yy + 0.5 - (MCY - MY0)) / MRV
            q = n1 * n1 + n2 * n2
            if q > 1.0: continue
            na = math.sqrt(1 - q)
            if q > 0.93: img[yy, xx] = BROWN; continue                         # thin outline at the cap's rim
            lit = (-0.5 * n1 - 0.6 * n2 + 0.62 * na)
            c = YEL if lit > 0.12 and q < 0.78 - 0.02 * push else YEL_D
            gx, gy = -0.42, -0.5 + 0.08 * push
            if (n1 - gx) ** 2 + (n2 - gy) ** 2 < 0.05: c = YEL_L
            img[yy, xx] = c
    return img


MOUTH_FRAMES = {(0, 40): 0, (96, 32): 0, (80, 32): 1, (64, 32): 2, (48, 32): 3, (32, 32): 4}
for (x, y), push in MOUTH_FRAMES.items():
    page[y:y + 24, x:x + 16] = mouth_frame(push)
    rowmap[y:y + 24, x:x + 16] = ROW_FACE

# knob patch (static yellow ball)
kx, ky, kr = KNOB
for yy in range(ky - 7, ky + 8):
    for xx in range(kx - 7, kx + 8):
        n1, n2 = (xx + 0.5 - kx) / kr, (yy + 0.5 - ky) / kr
        q = n1 * n1 + n2 * n2
        if q > 1.3: page[yy, xx] = YEL; rowmap[yy, xx] = ROW_FACE; continue
        if q > 0.9: c = BROWN
        else:
            na = math.sqrt(max(0, 1 - q)); lit = (-0.5 * n1 - 0.6 * n2 + 0.62 * na)
            c = YEL if lit > 0.15 and q < 0.72 else YEL_D
            if (n1 + 0.4) ** 2 + (n2 + 0.45) ** 2 < 0.08: c = YEL_L
        page[yy, xx] = c; rowmap[yy, xx] = ROW_FACE

# bubble patch: a lit sphere by normal, glint upper-left, darker rim
cx, cy, rr = BUB
for yy in range(int(cy - 16), int(cy + 16)):
    for xx in range(int(cx - 16), int(cx + 16)):
        nx, ny = (xx + 0.5 - cx) / 16, (yy + 0.5 - cy) / 16
        q = nx * nx + ny * ny
        if q > 1: q = 1; nx, ny = nx / math.sqrt(q + 1e-9), ny / math.sqrt(q + 1e-9)
        nz = -math.sqrt(max(0.0, 1 - nx * nx - ny * ny))
        n = np.array([nx, ny, nz])
        d = max(0.0, float(n @ LB))
        t = 0.38 + 0.62 * d ** 0.8
        t -= 0.22 * smooth((q - 0.62) / 0.38)                               # darker rim
        c = np.array(ramp(np.array([t]), RAMP)[0])
        g = smooth((float(n @ LB) - 0.9) / 0.1) * 0.95
        c = c * (1 - g) + WHITE * g
        page[yy, xx] = c; rowmap[yy, xx] = ROW_BUB

# underside patch
cx, cy, rr = BOT
for yy in range(cy - 8, cy + 8):
    for xx in range(cx - 8, cx + 8):
        d = math.hypot(xx + 0.5 - cx, yy + 0.5 - cy) / 8
        page[yy, xx] = ramp(np.array([0.12 + 0.12 * d]), RAMP)[0]; rowmap[yy, xx] = ROW_BODY

# ---- palettes (explicit) and snapping
PAL = {}
PAL[ROW_BODY] = [tuple(ramp(np.array([t]), RAMP)[0]) for t in np.linspace(0, 1, 13)] + [(248, 252, 244), (255, 255, 255), (80, 124, 66)]
PAL[ROW_FACE] = [tuple(ramp(np.array([t]), RAMP)[0]) for t in np.linspace(0.3, 1, 8)] + [(255, 255, 255), (14, 16, 14), (72, 76, 72),
                                                                                     tuple(YEL), tuple(YEL_D), tuple(YEL_L), tuple(BROWN), (248, 252, 244)]
PAL[ROW_BUB] = [tuple(ramp(np.array([t]), RAMP)[0]) for t in np.linspace(0, 1, 11)] + [(246, 251, 240), (252, 254, 250), (255, 255, 255), (90, 138, 76), (120, 170, 100)]


def c15(c):
    r, g, bb = (int(v) >> 3 for v in c)
    return (r | g << 5 | bb << 10) or 0x8000


tim = b.tim
idx = np.zeros((H, W), np.uint8)
final = np.zeros((H, W, 4), np.uint8); final[..., 3] = 255
for row, cols in PAL.items():
    assert len(cols) <= 16
    tim.pal[row] = [c15(c) for c in cols] + [c15(cols[0])] * (16 - len(cols))
    disp = np.array([mmd.c15_to_rgba(c)[:3] for c in tim.pal[row]], float)
    m = rowmap == row
    px = page[m]
    dist = ((px[:, None, :] - disp[None, :len(cols), :]) ** 2).sum(-1)
    k = dist.argmin(1)
    idx[m] = k
    final[m, :3] = disp[k]
tim.idx = bytearray(idx.flatten().tobytes())

os.makedirs(OUT, exist_ok=True)
mp, tp = os.path.join(OUT, 'Pabumon.MMD'), os.path.join(OUT, 'Pabumon.TIM')
blob = b.m.build()
open(mp, 'wb').write(blob)
open(tp, 'wb').write(tim.to_bytes())
cv2.imwrite(os.path.join(OUT, 'Pabumon-tex.png'), cv2.resize(cv2.cvtColor(final, cv2.COLOR_RGBA2BGRA), None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST))
nq = sum(1 for f in FACES if len(f[0]) == 4); nt = len(FACES) - nq
print(f'{mp}:15:{tp}:0:Pabumon')
print(f'# verts {len(V)} quads {nq} tris {nt} MMD {len(blob)} B', file=sys.stderr)
