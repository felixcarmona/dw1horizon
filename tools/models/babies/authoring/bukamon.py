"""Koromon (type 2) -> Bukamon: grey seal pup, round head with a snout, body tapering into a curled tail, two front
flippers, pale blue belly, flame tuft, big blue eyes.

Round 2: the geometry is rebuilt from scratch (the donor's mesh is discarded, only its skeleton and animations stay):
  object 0 (bone 2): head sphere + muzzle loft + body/tail loft + three flame licks
  objects 1 / 3 (bones 3 / 5, Koromon's ear roots at world (+-25,-109,-41), no rest rotation): the flippers, rooted
      inside the chest next to the joint, so the ear animations (idle twitch, droop, wobble) swing them at the root
  objects 2 / 4 (ear tips): collapsed to a point.
Why Koromon and not Tsunomon: bone 1 (the body hop/squash) is channel-for-channel the same in both, and Koromon's two
ear-root bones sit exactly where a seal's front flippers sprout; Koromon also has six eye and three mouth frames.
Texture: repainted entirely with explicit <=16-colour palettes per CLUT row (values multiples of 8: tex_import keeps
them exact), eye/mouth frames in Koromon's rectangle layout (eyes 40x32 at (8,0), mouths 40x24 at (0,32)).
Conventions found on the donor: cross(b-a, c-a) of a front face points INWARD; normals outward, 4.12.
"""
from lib import *
import math

b = Baby('Bukamon', 2)
PAGE_H, PAGE_W = b.tex.shape[:2]

# ------------------------------------------------------------------ palettes (multiples of 8)
G = [(56, 48, 56), (88, 80, 92), (112, 104, 116), (136, 128, 140), (160, 152, 164), (184, 176, 188), (208, 200, 208),
     (232, 224, 232)]                                                     # warm mauve greys dark -> light (#9C9AA3 at G[4])
BELLY = [(176, 208, 224), (208, 240, 248), (232, 248, 248)]               # pale blue belly (#CFEFF6)
INK = (16, 16, 24)
WHITE = (248, 248, 248)
BLUE = [(16, 32, 96), (24, 64, 160), (48, 112, 216), (104, 176, 248), (168, 216, 248)]
MOUTH_DARK, MOUTH_RED, TONGUE = (96, 16, 24), (160, 40, 48), (224, 112, 128)
FLAME = [(184, 16, 16), (224, 48, 16), (248, 88, 16), (248, 128, 24), (248, 168, 40), (248, 208, 64), (248, 240, 128)]
ROW_BODY, ROW_EYE, ROW_MOUTH, ROW_FLAME = 0, 1, 2, 3


# ------------------------------------------------------------------ mesh builder
class Mesh:
    """Vertices in WORLD coordinates (y negative = up, the model faces -z); faces carry per-corner UVs and a CLUT row.
    Winding is fixed at insertion from an 'outward' direction (cross(b-a, c-a) must point inward)."""

    def __init__(self):
        self.v, self.f = [], []            # f: (ia, ib, ic, (uv, uv, uv), row, outward)

    def add(self, p):
        self.v.append(np.array(p, float)); return len(self.v) - 1

    def tri(self, a, b_, c, uva, uvb, uvc, row, outward):
        pa, pb, pc = self.v[a], self.v[b_], self.v[c]
        cr = np.cross(pb - pa, pc - pa)
        if cr @ np.asarray(outward, float) > 0:            # cross points outward: flip
            b_, c, uvb, uvc = c, b_, uvc, uvb
        self.f.append((a, b_, c, (uva, uvb, uvc), row, np.asarray(outward, float)))

    def quad(self, a, b_, c, d, uva, uvb, uvc, uvd, row, outward):
        self.tri(a, b_, c, uva, uvb, uvc, row, outward)
        self.tri(a, c, d, uva, uvc, uvd, row, outward)

    def normals(self):
        """Per-vertex: the mean of the adjacent face normals, each taken as -cross (cross points inward)."""
        n = np.zeros((len(self.v), 3))
        for a, b_, c, _, _, _ in self.f:
            pa, pb, pc = self.v[a], self.v[b_], self.v[c]
            fn = -np.cross(pb - pa, pc - pa)
            l = np.linalg.norm(fn)
            if l > 1e-9:
                fn /= l
                n[a] += fn; n[b_] += fn; n[c] += fn
        l = np.linalg.norm(n, axis=1); l[l == 0] = 1
        return n / l[:, None]

    def merge(self, other):
        off = len(self.v)
        self.v += list(other.v)
        self.f += [(a + off, b_ + off, c + off, uv, row, o) for a, b_, c, uv, row, o in other.f]

    def mirror_x(self):
        m = Mesh()
        m.v = [p * [-1, 1, 1] for p in self.v]
        m.f = [(a, c, b_, (uv[0], uv[2], uv[1]), row, o * [-1, 1, 1]) for a, b_, c, uv, row, o in self.f]   # mirroring flips the winding
        return m


def set_object(oi, mesh, origin):
    """Write a Mesh into TMD object oi, vertices relative to the bone origin (world). Vertex and normal pools are
    rebuilt at the end by repack()."""
    ob = b.m.tmd.objects[oi]
    org = np.asarray(origin, float)
    ob._verts = [tuple(int(round(x)) for x in (p - org)) + (0,) for p in mesh.v]
    ob._norms = [tuple(int(round(x * 4096)) for x in n) + (0,) for n in mesh.normals()]
    prims = []
    for a, b_, c, uv, row, _ in mesh.f:
        p = dict(mode=0x34, flag=0, olen=9, uv=[(int(u), int(v)) for u, v in uv], cba=0x7A00 + (row << 6), tsb=5,
                 uvpad=[0], colors=[], norms=[a, b_, c], verts=[a, b_, c], pad=[])
        prims.append(mmd.Prim.encode(p))
    ob.prims = prims


def repack():
    t = b.m.tmd
    t.verts, t.norms = [], []
    for ob in t.objects:
        ob.vert_start, ob.nvert = len(t.verts), len(ob._verts); t.verts += ob._verts
        ob.norm_start, ob.nnorm = len(t.norms), len(ob._norms); t.norms += ob._norms


def ring_pts(c, rx, ry, tangent, n, phase=0.0, up=(0, -1, 0)):
    """n points of an ellipse (rx across, ry along 'up') in the plane perpendicular to tangent; angle 0 = up."""
    c, tg = np.asarray(c, float), np.asarray(tangent, float); tg /= np.linalg.norm(tg)
    u = np.asarray(up, float); u = u - (u @ tg) * tg
    if np.linalg.norm(u) < 0.05:
        u = np.array([0, 0, -1.0]); u = u - (u @ tg) * tg
    u /= np.linalg.norm(u)
    s = np.cross(tg, u)                                 # sideways
    return [c + ry * math.cos(a) * u + rx * math.sin(a) * s for a in (phase + 2 * math.pi * k / n for k in range(n))]


def loft(mesh, rings, nseg, u0, u1, vs, row, cap_end=None, cap_start=None, phase=0.0, uv_cap=None, transport=False):
    """rings: [(centre, rx, ry, tangent)]; connects them with quads; UV u around (u0..u1), v per ring (vs list).
    cap_end/cap_start: a tip point closing the loft. transport: carry the 'up' axis of the rings along the curve
    (parallel transport) so the texture columns do not twist where the path turns vertical. Returns the ring index table."""
    ids = []
    up = np.array([0, -1.0, 0])
    for (c, rx, ry, tg) in rings:
        tgn = np.asarray(tg, float); tgn /= np.linalg.norm(tgn)
        if transport:
            up = up - (up @ tgn) * tgn; up /= np.linalg.norm(up)
        pts = ring_pts(c, rx, ry, tg, nseg, phase, up=up if transport else (0, -1, 0))
        ids.append([mesh.add(p) for p in pts])
    cs = [np.asarray(r[0], float) for r in rings]
    uu = lambda k: u0 + (u1 - u0) * k / nseg
    for i in range(len(rings) - 1):
        for k in range(nseg):
            k2 = (k + 1) % nseg
            a, b_, c, d = ids[i][k], ids[i][k2], ids[i + 1][k2], ids[i + 1][k]
            cen = (mesh.v[a] + mesh.v[b_] + mesh.v[c] + mesh.v[d]) / 4
            out = cen - (cs[i] + cs[i + 1]) / 2
            mesh.quad(a, b_, c, d, (uu(k), vs[i]), (uu(k + 1), vs[i]), (uu(k + 1), vs[i + 1]), (uu(k), vs[i + 1]), row, out)
    if cap_end is not None:
        tip = mesh.add(cap_end)
        for k in range(nseg):
            k2 = (k + 1) % nseg
            a, b_ = ids[-1][k], ids[-1][k2]
            out = (mesh.v[a] + mesh.v[b_] + mesh.v[tip]) / 3 - cs[-1]
            uvt = uv_cap if uv_cap else ((uu(k) + uu(k + 1)) / 2, vs[-1] + (vs[-1] - vs[-2]) * 0.5)
            mesh.tri(a, b_, tip, (uu(k), vs[-1]), (uu(k + 1), vs[-1]), uvt, row, out)
    if cap_start is not None:
        tip = mesh.add(cap_start)
        for k in range(nseg):
            k2 = (k + 1) % nseg
            a, b_ = ids[0][k], ids[0][k2]
            out = (mesh.v[a] + mesh.v[b_] + mesh.v[tip]) / 3 - cs[0]
            mesh.tri(a, b_, tip, (uu(k), vs[0]), (uu(k + 1), vs[0]), ((uu(k) + uu(k + 1)) / 2, vs[0]), row, out)
    return ids


# ------------------------------------------------------------------ texture layout (page 256x128)
# eyes: dst (8,0) 40x32, sources (56,0) (96,0) (136,0) (176,0) (216,0) (216,32); mouths: dst (0,32) 40x24, sources
# (56,32) (96,32) (136,32). Everything else is ours from y = 56 down (the flat sprite keeps (224..256, 96..128)).
EYE_RECT = (8, 0, 40, 32)
EYE_SRC = {'open': (216, 32), 'sad': (56, 0), 'tired': (96, 0), 'closed': (136, 0), 'hurt': (176, 0), 'happy': (216, 0)}
MOUTH_RECT = (0, 32, 40, 24)
MOUTH_SRC = {'closed': (136, 32), 'half': (56, 32), 'open': (96, 32)}
HEAD_U, HEAD_V = (0, 96), (56, 96)          # head sphere: 12 columns x 5 latitude intervals
BODY_U, BODY_V = (96, 176), (56, 104)       # body/tail loft: 10 columns x 7 intervals
FLIP_U, FLIP_V = (176, 200), (56, 104)      # flippers
FLAME_U, FLAME_V = (200, 216), (56, 112)    # flame strip, red at the bottom, yellow at the top
MUZ_U, MUZ_V = (0, 48), (96, 112)           # muzzle side faces (8 columns x 2 intervals)
NOSE_UV = (56, 104)                         # nose cap centre
NOSE_R = 7

# ------------------------------------------------------------------ geometry (world units; ground y = 0)
# Round 3 (critic's list): body on the ground, flat paddle flippers held out to the sides, short blunt muzzle with
# brow ridges and forward-facing eyes, short plump body with a fluke, one swept plume, ~370 primitives.
HEAD_C = np.array([0.0, -106.0, -16.0]); HEAD_R = (54.0, 47.0, 50.0)      # rx, ry, rz: a little wider than tall
LATS = [-70, -38, -4, 30, 54, 76]            # latitude rings (deg, + = up); the eye band is -4..30
LONS = [8, 44, 80, 110, 140, 170, 190, 220, 250, 280, 316, 352]   # columns 0 and 10 (36 deg) carry the eyes, 16 deg apart
NLON = 12
BROW_LONS = {8, 44, 316, 352}                # the eye quads' top corners: pushed out as brow ridges

obj0 = Mesh()


def sphere_pt(lat, lon):
    la, lo = math.radians(lat), math.radians(lon)
    cheek = 1.0 + 0.06 * max(0.0, math.cos(math.radians(lat + 22)) ** 3) * (0.6 + 0.4 * abs(math.sin(lo)))   # fuller cheeks
    flat = 0.94 if lat > 40 else 1.0                                                                       # flatter crown
    face = 1.0 - 0.08 * max(0.0, math.cos(lo)) ** 2 * (1.0 if -12 <= lat <= 42 else 0.4)                  # flatter face
    brow = 1.10 if (lat == 30 and lon in BROW_LONS) else 1.0
    return HEAD_C + brow * np.array([HEAD_R[0] * cheek * math.cos(la) * math.sin(lo), -HEAD_R[1] * flat * math.sin(la),
                                     -HEAD_R[2] * face * math.cos(la) * math.cos(lo)])


# -- head sphere
rings = [[obj0.add(sphere_pt(la, lo)) for lo in LONS] for la in LATS]
top = obj0.add(sphere_pt(90, 0)); bot = obj0.add(sphere_pt(-90, 0))
hu = lambda k: HEAD_U[0] + (HEAD_U[1] - HEAD_U[0]) * k / NLON
hv = lambda i: HEAD_V[1] - (HEAD_V[1] - HEAD_V[0]) * i / (len(LATS) - 1)     # low latitude -> bottom of the strip
EYE_BAND = (2, 3)                            # ring indices -4 .. 30
EYE_COLS = {0: 1, 10: -1}                    # column 0 (8..44 deg) = right eye, column 10 (316..352) = left eye
ex, ey, ew, eh = EYE_RECT
for i in range(len(LATS) - 1):
    for k in range(NLON):
        k2 = (k + 1) % NLON
        a, b_, c, d = rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]
        out = (obj0.v[a] + obj0.v[b_] + obj0.v[c] + obj0.v[d]) / 4 - HEAD_C
        if i == EYE_BAND[0] and k in EYE_COLS:
            # eye quad: a, b_ = lower ring (k, k2), c, d = upper ring. Frame: u 8..47 inner -> outer, v 0 top .. 31 bottom
            if EYE_COLS[k] > 0:    # right eye: k is the inner edge
                uva, uvb, uvc, uvd = (ex, ey + eh - 1), (ex + ew - 1, ey + eh - 1), (ex + ew - 1, ey), (ex, ey)
            else:                  # left eye: k2 is the inner edge
                uva, uvb, uvc, uvd = (ex + ew - 1, ey + eh - 1), (ex, ey + eh - 1), (ex, ey), (ex + ew - 1, ey)
            obj0.quad(a, b_, c, d, uva, uvb, uvc, uvd, ROW_EYE, out)
        else:
            obj0.quad(a, b_, c, d, (hu(k), hv(i)), (hu(k + 1), hv(i)), (hu(k + 1), hv(i + 1)), (hu(k), hv(i + 1)), ROW_BODY, out)
for k in range(NLON):
    k2 = (k + 1) % NLON
    a, b_ = rings[-1][k], rings[-1][k2]
    obj0.tri(a, b_, top, (hu(k), hv(5)), (hu(k + 1), hv(5)), ((hu(k) + hu(k + 1)) / 2, HEAD_V[0]), ROW_BODY, (obj0.v[a] + obj0.v[b_]) / 2 + [0, -40, 0] - HEAD_C)
    a, b_ = rings[0][k], rings[0][k2]
    obj0.tri(a, b_, bot, (hu(k), hv(0)), (hu(k + 1), hv(0)), ((hu(k) + hu(k + 1)) / 2, HEAD_V[1]), ROW_BODY, (obj0.v[a] + obj0.v[b_]) / 2 + [0, 40, 0] - HEAD_C)

# -- muzzle: a loft along -z out of the lower front of the head (round 4: longer, the lip line painted along its sides); the nose
# bump is the fan at the tip, the mouth quad fills the lower half of the front, a chin triangle below it
MUZ = [((0, -86, -36), 36, 22, (0, 0, -1)), ((0, -86, -56), 34, 21, (0, 0.05, -1)), ((0, -85, -74), 30, 18, (0, 0.1, -1)),
       ((0, -85, -88), 24, 14, (0, 0.15, -1))]     # a longer, crocodile-like snout (~0.7 head radii beyond the face)
NM = 8
mz = Mesh()
mids = loft(mz, MUZ, NM, MUZ_U[0], MUZ_U[1], [MUZ_V[1], MUZ_V[0] + 10, MUZ_V[0] + 4, MUZ_V[0]], ROW_BODY, phase=0.0)
r3 = mids[3]
nose = mz.add((0, -90, -94))
ang = lambda q: 2 * math.pi * q / NM
for (k, k2) in [(6, 7), (7, 0), (0, 1), (1, 2)]:
    uva = (NOSE_UV[0] + NOSE_R * math.sin(ang(k)), NOSE_UV[1] - NOSE_R * math.cos(ang(k)))
    uvb = (NOSE_UV[0] + NOSE_R * math.sin(ang(k2)), NOSE_UV[1] - NOSE_R * math.cos(ang(k2)))
    mz.tri(r3[k], r3[k2], nose, uva, uvb, NOSE_UV, ROW_BODY, (0, -0.3, -1))
mx, my, mw, mh = MOUTH_RECT
mz.quad(r3[6], r3[2], r3[3], r3[5], (mx, my), (mx + mw - 1, my), (mx + mw - 1 - 8, my + mh - 1), (mx + 8, my + mh - 1), ROW_MOUTH, (0, 0.2, -1))
mz.tri(r3[3], r3[4], r3[5], (MUZ_U[0] + 4, MUZ_V[0] + 2), (MUZ_U[0] + 10, MUZ_V[0] + 2), (MUZ_U[0] + 16, MUZ_V[0] + 2), ROW_BODY, (0, 0.6, -0.8))
obj0.merge(mz)

# -- body: short and plump, resting on the ground, tapering into a short tail that rises ~20 deg and ends in a fluke
BODY = [((0, -44, -30), 36, 27), ((0, -36, -2), 40, 31), ((0, -33, 28), 38, 29), ((0, -35, 52), 30, 24),
        ((0, -41, 68), 20, 16), ((0, -50, 84), 12, 10)]
TAIL_END = (0, -56, 94)
CHEST_CAP = (0, -52, -44)
cs = [np.array(c, float) for c, _, _ in BODY] + [np.array(TAIL_END, float)]
brings = []
for i, (c, rx, ry) in enumerate(BODY):
    tg = cs[i + 1] - (cs[i - 1] if i > 0 else np.array([0, -60, -60.0]))
    brings.append((c, rx, ry, tg))
NB = 10
bv = [BODY_V[0] + (BODY_V[1] - BODY_V[0]) * i / (len(BODY) - 1) for i in range(len(BODY))]
bo = Mesh()
loft(bo, brings, NB, BODY_U[0], BODY_U[1], bv, ROW_BODY, cap_end=TAIL_END, cap_start=CHEST_CAP, phase=math.pi / NB, transport=True)
# fluke: a flat bilobed sheet, both sides (own vertices each, opposite winding)
FL_C, FL_L, FL_R, FL_N = (0, -54, 90), (-18, -58, 111), (18, -58, 111), (0, -57, 103)
fuv = lambda x, z: (BODY_U[0] + 40 + x * 0.6, BODY_V[1] - 4 - (z - 90) * 0.3)
for side in (-1, 1):
    ids_ = [bo.add(p) for p in (FL_C, FL_L, FL_R, FL_N)]
    bo.tri(ids_[0], ids_[1], ids_[3], fuv(0, 96), fuv(-18, 118), fuv(0, 110), ROW_BODY, (0, side, 0))
    bo.tri(ids_[0], ids_[3], ids_[2], fuv(0, 96), fuv(0, 110), fuv(18, 118), ROW_BODY, (0, side, 0))
obj0.merge(bo)

# -- flame: one plume from the crown: a main lick leaning back ~30 deg and two short side licks, each a 4-sided loft
# (base ring, bulge ring, tip). UV v runs base (yellow) -> tip (red-orange) on the flame strip.
FLAME_BASE = np.array([0.0, -150.0, -4.0])


def lick(base, tip, w, bend):
    fl = Mesh()
    base, tip = np.asarray(base, float), np.asarray(tip, float)
    d = tip - base
    r1 = base + d * 0.4 + bend
    rings_ = [(base, w, w * 0.7, d), (r1, w * 0.95, w * 0.62, tip - base)]
    vs = [FLAME_V[1] - 1, FLAME_V[1] - 24]
    loft(fl, rings_, 4, FLAME_U[0], FLAME_U[1], vs, ROW_FLAME, cap_end=tip, phase=math.pi / 4,
         uv_cap=((FLAME_U[0] + FLAME_U[1]) / 2, FLAME_V[0] + 1))
    return fl


obj0.merge(lick(FLAME_BASE + [0, 4, 0], FLAME_BASE + [3, -46, 24], 20, [1, 0, 7]))
obj0.merge(lick(FLAME_BASE + [-4, 4, -2], FLAME_BASE + [-17, -26, 2], 12, [-4, 0, 1]))
obj0.merge(lick(FLAME_BASE + [4, 4, -3], FLAME_BASE + [12, -24, -8], 11, [3, 0, -3]))

set_object(0, obj0, (0, -69, 0))

# -- flippers: 3D paddles held out to the sides (~40 deg down, ~35 deg forward) on the ear-root bones (pivot
# (+-25,-109,-41), the root 3 right / 51 below / 19 ahead of it, buried in the flank). Diamond sections: thick at the
# root, wide in the middle, tapering to a point (the root cap is buried, so none). Right one built in world coordinates.
FLIP_ROOT = np.array([28.0, -58.0, -22.0])
FLIP_D = np.array([0.62, 0.64, -0.45]); FLIP_D /= np.linalg.norm(FLIP_D)
FLIP_LEN = 66.0
FLIP_N = np.array([0.2, -0.65, -0.73]); FLIP_N -= (FLIP_N @ FLIP_D) * FLIP_D; FLIP_N /= np.linalg.norm(FLIP_N)
SECT = [(0.0, 16, 12), (0.4, 30, 9), (0.8, 22, 4)]           # (t along, chord width, thickness)


def flipper():
    m = Mesh()
    ids = []
    for tt, w, th in SECT:
        c = FLIP_ROOT + FLIP_D * FLIP_LEN * tt
        pts = ring_pts(c, w / 2, th / 2, FLIP_D, 4, phase=0.0, up=FLIP_N)      # 0 = +normal face, 90 = edge
        ids.append([m.add(p) for p in pts])
    cs_ = [FLIP_ROOT + FLIP_D * FLIP_LEN * tt for tt, _, _ in SECT]
    fu = lambda k: FLIP_U[0] + (FLIP_U[1] - FLIP_U[0]) * k / 4
    fv = [FLIP_V[0] + (FLIP_V[1] - FLIP_V[0]) * tt for tt, _, _ in SECT]
    for i in range(len(SECT) - 1):
        for k in range(4):
            k2 = (k + 1) % 4
            a, b_, c, dd = ids[i][k], ids[i][k2], ids[i + 1][k2], ids[i + 1][k]
            cen = (m.v[a] + m.v[b_] + m.v[c] + m.v[dd]) / 4
            m.quad(a, b_, c, dd, (fu(k), fv[i]), (fu(k + 1), fv[i]), (fu(k + 1), fv[i + 1]), (fu(k), fv[i + 1]), ROW_BODY,
                   cen - (cs_[i] + cs_[i + 1]) / 2)
    tip = m.add(FLIP_ROOT + FLIP_D * FLIP_LEN)
    for k in range(4):
        k2 = (k + 1) % 4
        a, b_ = ids[-1][k], ids[-1][k2]
        m.tri(a, b_, tip, (fu(k), fv[-1]), (fu(k + 1), fv[-1]), ((fu(k) + fu(k + 1)) / 2, FLIP_V[1] - 1), ROW_BODY,
              (m.v[a] + m.v[b_] + m.v[tip]) / 3 - cs_[-1] + FLIP_D * 4)
    return m


fr = flipper()
set_object(1, fr, (25, -109, -41))
set_object(3, fr.mirror_x(), (-25, -109, -41))
# ear tips: a single degenerate triangle at the joint, UV on body skin (row 0)
for oi in (2, 4):
    z = Mesh(); z.add((0, 0, 0)); z.add((0, 0, 0)); z.add((0, 0, 0))
    z.f.append((0, 1, 2, ((HEAD_U[0] + 20, HEAD_V[0] + 20),) * 3, ROW_BODY, np.array([0, -1.0, 0])))
    set_object(oi, z, (0, 0, 0))
repack()

# ------------------------------------------------------------------ texture
t = b.tex
t[..., :3] = G[4]; t[..., 3] = 255


def fill(x0, y0, w, h, rgb):
    t[y0:y0 + h, x0:x0 + w, :3] = rgb


def vgrad(x0, y0, w, h, stops):
    """Vertical bands: stops = list of colours top -> bottom, equal heights."""
    n = len(stops)
    for i, c in enumerate(stops):
        ya, yb = y0 + h * i // n, y0 + h * (i + 1) // n
        t[ya:yb, x0:x0 + w, :3] = c


# head skin: a shade darker at the back of the head, light at the cheeks and chin
vgrad(HEAD_U[0], HEAD_V[0], HEAD_U[1] - HEAD_U[0], HEAD_V[1] - HEAD_V[0], [G[4], G[4], G[5], G[5], G[5], G[6]])
hc = lambda k: HEAD_U[0] + (HEAD_U[1] - HEAD_U[0]) * k // NLON
t[HEAD_V[0]:HEAD_V[1], hc(4):hc(7), :3] = G[3]
t[HEAD_V[0]:HEAD_V[1], hc(3):hc(4), :3] = G[4]; t[HEAD_V[0]:HEAD_V[1], hc(7):hc(8), :3] = G[4]
# body: back a shade darker, flanks mid; a big pale belly oval over the lower half (columns 2..7 = angles 90..270
# around the bottom) from the chest to the tail root, with a thin darker rim like the line art
bw = BODY_U[1] - BODY_U[0]; bh = BODY_V[1] - BODY_V[0]
vgrad(BODY_U[0], BODY_V[0], bw, bh, [G[4], G[4], G[5], G[5], G[5], G[5]])
col = lambda k: BODY_U[0] + bw * k // NB
for k in (9, 0):
    t[BODY_V[0]:BODY_V[1], col(k):col(k + 1), :3] = G[3]
belly = np.array([[col(2), BODY_V[0]], [col(8), BODY_V[0]], [col(8) - 2, BODY_V[0] + 18], [col(7), BODY_V[0] + 30],
                  [col(6), BODY_V[0] + 36], [col(4), BODY_V[0] + 36], [col(3), BODY_V[0] + 30], [col(2) + 2, BODY_V[0] + 18]], np.int32)
cv2.fillPoly(t, [belly], BELLY[1] + (255,), cv2.LINE_8)
cv2.polylines(t, [belly], True, G[2] + (255,), 1, cv2.LINE_8)
t[BODY_V[0]:BODY_V[0] + 2, col(2) + 1:col(8) - 1, :3] = BELLY[1]        # no rim at the chest cap seam
t[BODY_V[0] + 4:BODY_V[0] + 16, col(4) + 1:col(6) - 1, :3] = BELLY[2]   # lighter centre
# flippers: mid grey with a darker leading edge and a lighter trailing half
fw = FLIP_U[1] - FLIP_U[0]
fill(FLIP_U[0], FLIP_V[0], fw, FLIP_V[1] - FLIP_V[0], G[4])
fill(FLIP_U[0] + fw // 2, FLIP_V[0], fw // 2, FLIP_V[1] - FLIP_V[0], G[5])
fill(FLIP_U[0], FLIP_V[0], 2, FLIP_V[1] - FLIP_V[0], G[3])
fill(FLIP_U[1] - 2, FLIP_V[0], 2, FLIP_V[1] - FLIP_V[0], G[3])
# muzzle: light grey, lighter towards the tip; nose cap with two nostril dots
fill(MUZ_U[0], MUZ_V[0], MUZ_U[1] - MUZ_U[0], MUZ_V[1] - MUZ_V[0], G[5])
fill(MUZ_U[0], MUZ_V[0], MUZ_U[1] - MUZ_U[0], 5, G[6])
for ang_deg in (112, 248):                                           # the lip line along the sides of the snout
    u = MUZ_U[0] + int(round((MUZ_U[1] - MUZ_U[0]) * ang_deg / 360))
    t[MUZ_V[0]:MUZ_V[0] + 11, u - 1:u + 1, :3] = INK
cv2.circle(t, NOSE_UV, NOSE_R + 1, G[6] + (255,), -1, cv2.LINE_8)
t[NOSE_UV[1] - 4, NOSE_UV[0] - 3, :3] = G[2]; t[NOSE_UV[1] - 4, NOSE_UV[0] + 2, :3] = G[2]
# flame strip: yellow core at the base, orange, red-orange tips; the left half (two of the four faces) lighter
vgrad(FLAME_U[0], FLAME_V[0], FLAME_U[1] - FLAME_U[0], FLAME_V[1] - FLAME_V[0],
      [FLAME[1], FLAME[2], FLAME[2], FLAME[3], FLAME[4], FLAME[5], FLAME[6]])
vgrad(FLAME_U[0], FLAME_V[0], (FLAME_U[1] - FLAME_U[0]) // 2, FLAME_V[1] - FLAME_V[0],
      [FLAME[2], FLAME[3], FLAME[4], FLAME[5], FLAME[5], FLAME[6], FLAME[6]])


# ------------------------------------------------------------------ eye and mouth frames
def eye(x0, y0, kind):
    """40x32 frame at (x0,y0): u 0 = inner corner (nose side), u 39 = outer; v 0 = top."""
    fr_ = t[y0:y0 + 32, x0:x0 + 40]
    fr_[..., :3] = G[5]; fr_[..., 3] = 255
    cx, cy = 19, 16
    sub = np.zeros((32, 40, 4), np.uint8); sub[..., :3] = G[5]; sub[..., 3] = 255
    if kind in ('open', 'sad', 'tired', 'hurt'):
        # the eye: a tall oval, black outline; iris fills it with a vertical blue gradient; white highlights
        cv2.ellipse(sub, (cx, cy), (14, 15), 0, 0, 360, INK + (255,), -1, cv2.LINE_8)
        cv2.ellipse(sub, (cx, cy + 1), (12, 13), 0, 0, 360, BLUE[1] + (255,), -1, cv2.LINE_8)
        cv2.ellipse(sub, (cx, cy - 1), (15, 15), 0, 190, 350, INK + (255,), 3, cv2.LINE_8)    # heavy brow / upper lid
        yy, xx = np.mgrid[0:32, 0:40]
        inside = ((xx - cx) / 12.0) ** 2 + ((yy - cy - 1) / 13.0) ** 2 <= 1
        sub[inside & (yy < cy - 5), :3] = BLUE[2]
        sub[inside & (yy < cy - 10), :3] = BLUE[3]
        sub[inside & (yy > cy + 6), :3] = BLUE[0]
        # pupil
        cv2.ellipse(sub, (cx + 1, cy + 2), (7, 8), 0, 0, 360, INK + (255,), -1, cv2.LINE_8)
        cv2.ellipse(sub, (cx + 1, cy + 4), (3, 3), 0, 0, 360, BLUE[1] + (255,), -1, cv2.LINE_8)
        # highlights
        cv2.ellipse(sub, (cx - 6, cy - 6), (4, 3), 0, 0, 360, WHITE + (255,), -1, cv2.LINE_8)
        cv2.ellipse(sub, (cx + 7, cy + 7), (2, 2), 0, 0, 360, BLUE[4] + (255,), -1, cv2.LINE_8)
        if kind == 'sad':        # upper lid down from the outer side
            pts = np.array([[cx - 16, cy - 15], [cx + 16, cy - 15], [cx + 16, cy - 2], [cx - 16, cy - 10]], np.int32)
            cv2.fillPoly(sub, [pts], G[5] + (255,), cv2.LINE_8)
            cv2.line(sub, (cx - 15, cy - 10), (cx + 15, cy - 2), INK + (255,), 2, cv2.LINE_8)
        if kind == 'tired':      # half-closed lid
            cv2.rectangle(sub, (cx - 16, cy - 15), (cx + 16, cy - 2), G[5] + (255,), -1, cv2.LINE_8)
            cv2.line(sub, (cx - 14, cy - 2), (cx + 14, cy - 2), INK + (255,), 2, cv2.LINE_8)
        if kind == 'hurt':       # squint: lids from both sides
            cv2.rectangle(sub, (cx - 16, cy - 15), (cx + 16, cy - 4), G[5] + (255,), -1, cv2.LINE_8)
            cv2.rectangle(sub, (cx - 16, cy + 4), (cx + 16, cy + 15), G[5] + (255,), -1, cv2.LINE_8)
            cv2.line(sub, (cx - 14, cy - 4), (cx + 14, cy - 4), INK + (255,), 2, cv2.LINE_8)
            cv2.line(sub, (cx - 14, cy + 4), (cx + 14, cy + 4), INK + (255,), 2, cv2.LINE_8)
    elif kind == 'closed':       # a soft line
        cv2.ellipse(sub, (cx, cy - 2), (13, 6), 0, 20, 160, INK + (255,), 2, cv2.LINE_8)
    elif kind == 'happy':        # arc ^
        cv2.ellipse(sub, (cx, cy + 6), (13, 10), 0, 200, 340, INK + (255,), 3, cv2.LINE_8)
    fr_[:] = sub


def mouth(x0, y0, kind):
    """40x24 frame: v 0 (top, nose side) .. 23 (chin); u across the lower front of the muzzle. A thin dark line with
    two small fangs rising from the lower jaw."""
    sub = np.zeros((24, 40, 4), np.uint8); sub[..., :3] = G[5]; sub[..., 3] = 255
    ym = 9
    sub[0:ym + 1, :, :3] = G[6]                     # the upper lip as light as the nose above it
    if kind == 'closed':
        cv2.line(sub, (2, ym + 1), (37, ym), INK + (255,), 2, cv2.LINE_8)          # the lip line
        cv2.line(sub, (0, ym - 2), (3, ym + 1), INK + (255,), 2, cv2.LINE_8)
        cv2.line(sub, (36, ym), (39, ym - 2), INK + (255,), 2, cv2.LINE_8)
        for fx in (13, 26):                                                        # two fangs at the front of the upper jaw
            cv2.fillPoly(sub, [np.array([[fx - 3, ym], [fx + 3, ym], [fx, ym + 7]], np.int32)], WHITE + (255,), cv2.LINE_8)
            cv2.polylines(sub, [np.array([[fx - 3, ym + 1], [fx, ym + 7], [fx + 3, ym + 1]], np.int32)], False, INK + (255,), 1, cv2.LINE_8)
    elif kind == 'half':
        cv2.ellipse(sub, (19, ym + 1), (15, 5), 0, 0, 180, MOUTH_DARK + (255,), -1, cv2.LINE_8)
        cv2.ellipse(sub, (19, ym + 1), (15, 5), 0, 0, 180, INK + (255,), 1, cv2.LINE_8)
        cv2.line(sub, (4, ym + 1), (34, ym + 1), INK + (255,), 2, cv2.LINE_8)
        for fx in (13, 26):
            cv2.fillPoly(sub, [np.array([[fx - 3, ym + 1], [fx + 3, ym + 1], [fx, ym + 6]], np.int32)], WHITE + (255,), cv2.LINE_8)
    elif kind == 'open':
        cv2.ellipse(sub, (19, ym + 3), (15, 9), 0, 0, 360, MOUTH_DARK + (255,), -1, cv2.LINE_8)
        cv2.ellipse(sub, (19, ym + 7), (8, 4), 0, 0, 360, TONGUE + (255,), -1, cv2.LINE_8)
        cv2.ellipse(sub, (19, ym + 3), (15, 9), 0, 0, 360, INK + (255,), 2, cv2.LINE_8)
        for fx in (13, 26):
            cv2.fillPoly(sub, [np.array([[fx - 3, ym - 4], [fx + 3, ym - 4], [fx, ym + 3]], np.int32)], WHITE + (255,), cv2.LINE_8)
    t[y0:y0 + 24, x0:x0 + 40] = sub


eye(EYE_RECT[0], EYE_RECT[1], 'open')
for kind, (sx, sy) in EYE_SRC.items():
    eye(sx, sy, kind)
mouth(MOUTH_RECT[0], MOUTH_RECT[1], 'closed')
for kind, (sx, sy) in MOUTH_SRC.items():
    mouth(sx, sy, kind)

# ------------------------------------------------------------------ flat sprite (tournament): four 15x15 frames at
# (224,96) (240,96) (224,112) (240,112), CLUT row 15. Written straight into the TIM after tex_import, with its own palette.
def sprite_frames():
    pal = [G[4], G[6], INK, BLUE[2], WHITE, FLAME[2]]
    idx = {c: i + 1 for i, c in enumerate(pal)}
    frames = []
    for f in range(4):
        im = np.zeros((15, 15, 3), np.uint8); im[:] = 0
        cv2.circle(im, (7, 8), 6, G[4], -1, cv2.LINE_8)
        cv2.ellipse(im, (7, 11), (4, 2), 0, 0, 360, G[6], -1, cv2.LINE_8)
        cv2.fillPoly(im, [np.array([[6, 3], [8, 3], [7, 0]], np.int32)], FLAME[2], cv2.LINE_8)
        if f == 1:
            cv2.line(im, (3, 7), (5, 7), INK, 1, cv2.LINE_8); cv2.line(im, (9, 7), (11, 7), INK, 1, cv2.LINE_8)
        else:
            for x in (4, 10):
                im[6:9, x - 1:x + 2] = BLUE[2]; im[6, x - 1] = WHITE
        im[11, 7] = INK
        frames.append(im)
    return pal, idx, frames


def save():
    tex = b.tex.copy()
    mmd.tex_import(b.m, b.tim, PAGE_W, PAGE_H, bytearray(tex.tobytes()))
    pal, idx, frames = sprite_frames()
    b.tim.pal[15] = [0] + [mmd.rgba_to_c15(*c) for c in pal] + [0] * (15 - len(pal))
    for f, (x0, y0) in enumerate([(224, 96), (240, 96), (224, 112), (240, 112)]):
        for y in range(15):
            for x in range(15):
                c = tuple(int(v) for v in frames[f][y, x])
                b.tim.idx[(y0 + y) * PAGE_W + x0 + x] = idx.get(c, 0)
    os.makedirs(OUT, exist_ok=True)
    mp, tp = os.path.join(OUT, b.name + '.MMD'), os.path.join(OUT, b.name + '.TIM')
    open(mp, 'wb').write(b.m.build()); open(tp, 'wb').write(b.tim.to_bytes())
    cv2.imwrite(os.path.join(OUT, b.name + '-tex.png'),
                cv2.resize(cv2.cvtColor(b.tex, cv2.COLOR_RGBA2BGRA), None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST))
    return f'{mp}:{b.type}:{tp}:0:{b.name}'


# ------------------------------------------------------------------ checks and save
if __name__ == '__main__':
    pm = np.array(mmd.palette_map(b.m, b.tim)).reshape(PAGE_H, PAGE_W)
    for r in range(4):
        sel = pm == r
        cols = np.unique((t[sel][:, :3] >> 3 << 3).reshape(-1, 3), axis=0)
        print(f'row {r}: {sel.sum()} px, {len(cols)} colours' + (' TOO MANY' if len(cols) > 16 else ''))
    nv = sum(ob.nvert for ob in b.m.tmd.objects); npr = sum(len(ob.prims) for ob in b.m.tmd.objects)
    spec = save()
    print('verts', nv, 'prims', npr, 'MMD bytes', os.path.getsize(os.path.join(OUT, 'Bukamon.MMD')))
    print(spec)
    sheet(OUT + '/Bukamon-sheet.png', [spec], panels='mesh:front,mesh:three,mesh:side')
