"""Tokomon (type 30) -> Nyaromon, round 3: geometry rebuilt from scratch on the donor's skeleton.

Parts -> bones (the donor's animations are untouched):
  object 0 (bone 2, the body)  : the rounded cat head AND the whole tail (static relative to the head: every free
                                 bone of the donor swings 50 deg in the walk hop, which flailed round 1's tail)
                                 and the ears, a thick cone each (8-vertex elliptical base, mid ring, apex), rigid
                                 with the head: on the ear bones they left the head in the donor's big flop slots
  objects 1-8 (ear segments, feet): collapsed to a point (one degenerate triangle each)
Size: "a little smaller than Koromon" (DA sheet): head 166 wide x 122 tall x 140 deep (Koromon's body is 178 x 137).
Texture: face on the mirrored 72x48 block (u=0 is the centre line) with its three animation frames
(0,48) = restore, (72,0) = half-open mouth, (144,0) = wide-open mouth; body / ears / tail strips on the free part of
the page.  Every CLUT row is painted with its own <=16 colours so tex_import keeps them exact.
Conventions found in the donor: y negative is UP, the model faces -z, x>0 is the viewer's right in the front view,
face winding cross(v1-v0, v2-v0) points INWARD (opposite to the outward normal), normals 4.12 outward.
Trap: a collapsed object's degenerate triangle must not carry UV (0,0): palette_map would hand that face texel to
the body row and the face draws it with its own row (a red dot on the forehead in round 2).
"""
from lib import *
import math

b = Baby('Nyaromon', 30)
m = b.m; tmd = m.tmd

# ---------------------------------------------------------------- palette (5-bit exact values)
def q(c): return tuple(int(v) >> 3 << 3 for v in c)

Y0 = q((248, 232, 80)); Y1 = q((255, 248, 160)); Y2 = q((216, 184, 48))       # lemon, highlight, shade
YI = q((232, 208, 64)); YO = q((168, 136, 40))                                 # inner ear: one step darker + rim
INK = q((24, 16, 16)); WHITE = q((255, 255, 255))
I0 = q((144, 32, 32)); I1 = q((192, 64, 48)); PUP = q((40, 10, 14))             # iris dark red, lower iris, pupil
M0 = q((200, 80, 112)); M1 = q((240, 160, 176))                                # inner mouth, pink
PB = q((152, 128, 216)); PD = q((104, 88, 176)); PT = q((184, 168, 232)); PT2 = q((144, 128, 200))   # bands, shade, lavender tip
ROW_FACE, ROW_BODY, ROW_TAIL, ROW_SPRITE = 0, 1, 2, 15
CBA = lambda row: (488 + row) << 6

# ---------------------------------------------------------------- geometry helpers
class Part:
    """Vertices (bone-local), normals and faces of one TMD object. face = (vert ids, norm ids, uvs, row)."""
    def __init__(self):
        self.v, self.n, self.f = [], [], []

    def vert(self, p):
        self.v.append(np.array(p, float)); return len(self.v) - 1

    def norm(self, n):
        n = np.array(n, float); l = np.linalg.norm(n)
        self.n.append(n / l if l else np.array([0, -1.0, 0])); return len(self.n) - 1

    def face(self, vids, nids, uvs, row):
        """Winding is fixed here: cross(v1-v0, v2-v0) must point against the (mean) outward normal."""
        vids, nids, uvs = list(vids), list(nids), list(uvs)
        a, b_, c = self.v[vids[0]], self.v[vids[1]], self.v[vids[2]]
        out = sum(self.n[k] for k in nids)
        if np.cross(b_ - a, c - a) @ out > 0:
            vids[1], vids[2] = vids[2], vids[1]; nids[1], nids[2] = nids[2], nids[1]; uvs[1], uvs[2] = uvs[2], uvs[1]
        self.f.append((vids, nids, uvs, row))

    def prims(self):
        out = []
        for vids, nids, uvs, row in self.f:
            quad = len(vids) == 4
            d = dict(mode=0x3C if quad else 0x34, flag=0, olen=12 if quad else 9,
                     uv=[(int(round(u)) & 255, int(round(v)) & 255) for u, v in uvs], cba=CBA(row), tsb=5,
                     uvpad=[0, 0] if quad else [0], colors=[], norms=nids, verts=vids, pad=[])
            out.append(mmd.Prim.encode(d))
        return out


def install(oi, part):
    ob = tmd.objects[oi]
    ob._v = [(int(round(p[0])), int(round(p[1])), int(round(p[2])), 0) for p in part.v]
    ob._n = [(int(round(n[0] * 4096)), int(round(n[1] * 4096)), int(round(n[2] * 4096)), 0) for n in part.n]
    ob.prims = part.prims()


# ---------------------------------------------------------------- texture layout (page 256x128)
FACE = (0, 0, 72, 48)                       # live block; frames at (0,48) (72,0) (144,0)
BODY = (80, 50, 32, 32)                     # plain body swatch
EARF = (120, 50, 32, 44)                    # ear front (inner ear painted)
EARB = (160, 50, 24, 44)                    # ear back
TAIL = (76, 100, 136, 24)                   # u along the tail, v around (v=100 is the top side)
SW = (BODY[0] + 8, BODY[1] + 8)             # a plain body texel


def point_object(oi):
    p = Part(); p.vert((0, 0, 0)); p.norm((0, -1, 0))
    p.f.append(([0, 0, 0], [0, 0, 0], [SW] * 3, ROW_BODY))
    install(oi, p)


def repack():
    verts, norms = [], []
    for ob in tmd.objects:
        ob.vert_start, ob.nvert = len(verts), len(ob._v); verts += ob._v
        ob.norm_start, ob.nnorm = len(norms), len(ob._n); norms += ob._n
    tmd.verts, tmd.norms = verts, norms


# ---------------------------------------------------------------- head: wide rounded blob, widest just under the eyes
HA, HC = 83.0, 70.0                             # x half-width, z half-depth (depth 0.85 x width)
HTOP, HBOT, HYW = -125.0, -3.0, -68.0           # top, floor contact, the widest ring (47 % down)
HB_UP, HB_DN = HYW - HTOP, HBOT - HYW           # 57 / 65


def head_r(y):
    """Horizontal radius factor (0..1) of the head at height y: a dome above the widest ring, a flatter bowl below."""
    if y < HYW: t, e = (HYW - y) / HB_UP, 2.0
    else: t, e = (y - HYW) / HB_DN, 2.3
    t = min(1.0, abs(t))
    return (1 - t ** e) ** (1 / e)


def head_surface_y(x, z):
    """Top surface height of the head above (x, z)."""
    rr = math.hypot(x / HA, z / HC)
    lo, hi = HTOP, HYW
    for _ in range(40):
        mid = (lo + hi) / 2
        if head_r(mid) < rr: lo = mid
        else: hi = mid
    return lo


NAZ = 14
RING_Y = [-121, -113, -102, -88, -74, -60, -46, -32, -20, -10]
FACE_Y0, FACE_Y1 = -113.0, -10.0                # the band of the head the face block covers (ring to ring)
FU = lambda x: min(71.0, 71.0 * abs(x) / HA)
FV = lambda y: min(47.0, max(0.0, 48.0 * (y - FACE_Y0) / (FACE_Y1 - FACE_Y0)))
head = Part()
top = head.vert((0, HTOP, 0)); bot = head.vert((0, HBOT, 0))
rings = []
for y in RING_Y:
    r = head_r(y); ring = []
    for k in range(NAZ):
        az = 2 * math.pi * k / NAZ
        x, z = HA * r * math.sin(az), -HC * r * math.cos(az)
        chin = max(0.0, 1 - abs(y + 24) / 20.0) * max(0.0, math.cos(az))      # a touch of chin under the mouth
        ring.append(head.vert((x, y, z - 5.0 * chin)))
    rings.append(ring)
hn = {}
for v in range(len(head.v)):
    x, y, z = head.v[v]
    if v == top: n = (0, -1, 0)
    elif v == bot: n = (0, 1, 0)
    else:
        # surface F = (x/(A r(y)))^2 + (z/(C r(y)))^2 - 1: grad ~ (x/A^2, -r'(y) r(y), z/C^2), outward
        dy = 1.0
        slope = (head_r(y + dy) - head_r(y - dy)) / (2 * dy)
        n = (x / HA ** 2, -slope * head_r(y), z / HC ** 2)
    hn[v] = head.norm(n)


def head_uv(x, y, z, front):
    if front: return (FU(x), FV(y))
    return (BODY[0] + 1 + 29 * (0.5 + 0.5 * math.sin(math.atan2(x, -z))), BODY[1] + 1 + 29 * (y - HTOP) / (HBOT - HTOP))


def ring_face(vids):
    pts = [head.v[v] for v in vids]
    c = sum(pts) / len(pts)
    front = (c[2] < -1) and all(FACE_Y0 - 0.5 <= p[1] <= FACE_Y1 + 0.5 for p in pts)
    uvs = [head_uv(*p, front) for p in pts]
    head.face(vids, [hn[v] for v in vids], uvs, ROW_FACE if front else ROW_BODY)


for k in range(NAZ):
    k2 = (k + 1) % NAZ
    ring_face([top, rings[0][k], rings[0][k2]])
    for i in range(len(rings) - 1):
        ring_face([rings[i][k], rings[i][k2], rings[i + 1][k], rings[i + 1][k2]])
    ring_face([bot, rings[-1][k2], rings[-1][k]])

# ---------------------------------------------------------------- tail (part of the head object): thin tube on an S
TAIL_PTS = np.array([
    (12, -40, 30),     # inside the lower back of the head
    (36, -46, 62),     # leaving the lower back, slightly to the right
    (56, -62, 88),     # rising
    (72, -98, 102),
    (86, -132, 100),   # over the top
    (108, -138, 88),
    (124, -110, 72),   # coming down
    (128, -72, 58),
    (118, -36, 48),    # the lavender tip hovers off the floor
], float)


def catmull(P, n):
    out = []
    P = np.vstack([P[0], P, P[-1]])
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-2]); return np.array(out)


dense = catmull(TAIL_PTS, 40)
seg = np.linalg.norm(np.diff(dense, axis=0), axis=1); arc = np.concatenate([[0], np.cumsum(seg)])
TAIL_LEN = arc[-1]
NR, NA = 13, 8
TIP_FROM = 0.70                                  # the last 30 % is solid lavender and a little thicker


def tail_radius(s):
    if s < TIP_FROM - 0.06: return 10.0
    if s < TIP_FROM + 0.06: return 10.0 + 2.5 * (s - (TIP_FROM - 0.06)) / 0.12
    return 12.5


centres, tangents = [], []
for i in range(NR):
    s = i / (NR - 1) * 0.985
    j = int(np.searchsorted(arc, s * TAIL_LEN)); j = min(max(j, 1), len(dense) - 2)
    centres.append(dense[j]); t = dense[j + 1] - dense[j - 1]; tangents.append(t / np.linalg.norm(t))
N = np.array([0, -1.0, 0]); N -= tangents[0] * (N @ tangents[0]); N /= np.linalg.norm(N)
frames = []
for i in range(NR):
    T = tangents[i]
    if i: N = N - T * (N @ T); N /= np.linalg.norm(N)
    frames.append((N.copy(), np.cross(T, N)))
tail_rings, tail_n = [], {}
for i in range(NR):
    s = i / (NR - 1); r = tail_radius(s); Nv, Bv = frames[i]; ring = []
    for k in range(NA):
        th = 2 * math.pi * k / NA
        d = math.cos(th) * Nv + math.sin(th) * Bv
        v = head.vert(centres[i] + r * d); ring.append(v); tail_n[v] = head.norm(d)
    tail_rings.append(ring)
cap_rings = []
T = tangents[-1]; Nv, Bv = frames[-1]; r_end = tail_radius(1.0); c_end = centres[-1]
for ang in (38, 68):
    a = math.radians(ang); ring = []
    for k in range(NA):
        th = 2 * math.pi * k / NA
        d = math.cos(th) * Nv + math.sin(th) * Bv
        v = head.vert(c_end + r_end * (math.sin(a) * T + math.cos(a) * d)); ring.append(v)
        tail_n[v] = head.norm(math.cos(a) * d + math.sin(a) * T)
    cap_rings.append(ring)
pole = head.vert(c_end + r_end * T); tail_n[pole] = head.norm(T)
all_rings = tail_rings + cap_rings
TU = lambda i: TAIL[0] + 1 + (TAIL[2] - 3) * min(1.0, i / (NR - 1 + 2.2))
TV = lambda k: TAIL[1] + 0.5 + (TAIL[3] - 1) * k / NA
for i in range(len(all_rings) - 1):
    for k in range(NA):
        k2 = (k + 1) % NA
        vids = [all_rings[i][k], all_rings[i][k2], all_rings[i + 1][k], all_rings[i + 1][k2]]
        uvs = [(TU(i), TV(k)), (TU(i), TV(k + 1)), (TU(i + 1), TV(k)), (TU(i + 1), TV(k + 1))]
        head.face(vids, [tail_n[v] for v in vids], uvs, ROW_TAIL)
last = all_rings[-1]
for k in range(NA):
    k2 = (k + 1) % NA
    vids = [last[k], last[k2], pole]
    head.face(vids, [tail_n[v] for v in vids], [(TU(NR + 1), TV(k)), (TU(NR + 1), TV(k + 1)), (TAIL[0] + TAIL[2] - 2, TV(k + 0.5))], ROW_TAIL)
# ---------------------------------------------------------------- ears: thick cones, rigid on the head (bone 2)
# (on the ear bones 3 / 5 they left the head in the donor's 77-127 deg flop slots: 9 is the asleep loop)
EAR_CX, EAR_CZ = 52.0, -14.0            # base centre (world, right ear): the top corner of the head, just forward of the crown
EAR_AX, EAR_AZ = 26.0, 20.0             # elliptical base: half-width (x), half-depth (z) -> 52 x 40, real volume from every side
EAR_H, EAR_BURY = 82.0, 12.0            # visible height ~65 % of the head, base sunk into the head
EAR_TILT, EAR_BACK = 27.0, 10.0         # degrees outward / backward
EAR_NA, EAR_MID, EAR_MIDR = 8, 0.48, 0.58   # verts around, mid ring height fraction and radius fraction (a little convex)


def build_ear(side):
    p = head                                       # the ear's vertices and faces join the head object (bone 2 = world at rest)
    ys = head_surface_y(EAR_CX * side, EAR_CZ)
    tip = np.array([EAR_CX + EAR_H * math.tan(math.radians(EAR_TILT)), ys - EAR_H, EAR_CZ + EAR_H * math.tan(math.radians(EAR_BACK))])
    base_c = np.array([EAR_CX, ys + EAR_BURY, EAR_CZ])
    axis = tip - base_c; axis /= np.linalg.norm(axis)
    alpha = math.atan2(EAR_AX, EAR_H)              # the cone's half angle, for the normals
    ex, ey, ew, eh = EARF; bx, by, bw, bh = EARB
    def uv_of(k, hgt):                             # k may be fractional (the tip uses the face's mid angle)
        th = (k % EAR_NA) * 360.0 / EAR_NA         # 0 = front, 90 = outer side, 180 = back, 270 = inner side
        v = ey + eh - 1 - (eh - 2) * hgt
        if th <= 90 or th >= 270:                  # front half -> EARF (inner ear painted there)
            f = ((th + 90) % 360) / 180.0
            return (ex + 0.5 + (ew - 1) * f, v)
        return (bx + 0.5 + (bw - 1) * (th - 90) / 180.0, v)
    def ring(hgt, rad):
        c = base_c + (tip - base_c) * hgt; out = []
        for k in range(EAR_NA):
            th = 2 * math.pi * k / EAR_NA
            d = np.array([math.sin(th), 0, -math.cos(th)])
            pt = c + np.array([EAR_AX * rad * d[0], 0, EAR_AZ * rad * d[2]])
            if hgt == 0: pt[1] = head_surface_y(pt[0] * side, pt[2]) + EAR_BURY     # the base follows the head's surface
            n = d * math.cos(alpha) + np.array([0, -1.0, 0]) * math.sin(alpha)
            n[0] *= side
            out.append((p.vert(pt * [side, 1, 1]), p.norm(n)))
        return out
    r0, r1 = ring(0.0, 1.0), ring(EAR_MID, EAR_MIDR)
    vt, nt = p.vert(tip * [side, 1, 1]), p.norm(axis * [side, 1, 1])
    for k in range(EAR_NA):
        k2 = (k + 1) % EAR_NA
        kk = k + 1 if k2 else EAR_NA                # the seam vertex at k=0 takes u of 360 on the last face
        p.face([r0[k][0], r0[kk % EAR_NA][0], r1[k][0], r1[kk % EAR_NA][0]], [r0[k][1], r0[kk % EAR_NA][1], r1[k][1], r1[kk % EAR_NA][1]],
               [uv_of(k, 0), uv_of(kk, 0), uv_of(k, EAR_MID), uv_of(kk, EAR_MID)], ROW_BODY)
        p.face([r1[k][0], r1[kk % EAR_NA][0], vt], [r1[k][1], r1[kk % EAR_NA][1], nt],
               [uv_of(k, EAR_MID), uv_of(kk, EAR_MID), uv_of(k + 0.5, 1.0)], ROW_BODY)
    return ys


ys_ = build_ear(1); build_ear(-1)
install(0, head)
for oi in (1, 2, 3, 4, 5, 6, 7, 8):
    point_object(oi)
repack()

# ---------------------------------------------------------------- texture
t = b.tex
t[..., :3] = Y0; t[..., 3] = 255


def rect(x, y, w, h, col):
    t[y:y + h, x:x + w, :3] = col


def quantise_down(big, pal, S):
    """Majority palette colour per texel of a 4x drawing."""
    pal = np.array(pal, np.int32)
    idx = np.argmin(((big[..., None, :].astype(np.int32) - pal[None, None]) ** 2).sum(-1), -1)
    H, Wd = big.shape[0] // S, big.shape[1] // S
    out = np.zeros((H, Wd, 3), np.uint8)
    for y in range(H):
        for x in range(Wd):
            out[y, x] = pal[np.bincount(idx[y * S:(y + 1) * S, x * S:(x + 1) * S].ravel()).argmax()]
    return out


# the eye: a dome leaning outward with a pointed outer-bottom corner (DA sheet), in block texels (u outward)
EYE = [(24, 24), (23, 17), (26, 11), (32, 7), (40, 5.5), (47, 6), (52, 9), (55, 14), (55.5, 20), (53, 25), (47, 28),
       (38, 28.5), (30, 27)]                    # big, round-topped, friendly (the DA dome read angry)
MOUTH = [(0, 36.5), (18, 41.5), (33, 34.5)]  # half of the W: centre peak, valley, corner (the corners curl up)


def face_block(ox, oy, mouth):
    """One 72x48 half-face frame at (ox, oy). mouth: 'closed' | 'half' | 'wide'."""
    S = 4
    big = np.zeros((48 * S, 72 * S, 3), np.uint8); big[:] = Y0
    poly = lambda pts: np.array([(u * S, v * S) for u, v in pts], np.int32)
    cv2.fillPoly(big, [poly(EYE)], INK, lineType=cv2.LINE_8)
    c = np.array(EYE).mean(0)
    inner = [(c[0] + (u - c[0]) * 0.87, c[1] + (v - c[1]) * 0.85 + 0.5) for u, v in EYE]     # rim a touch thicker on top
    cv2.fillPoly(big, [poly(inner)], I0, lineType=cv2.LINE_8)
    yy, xx = np.mgrid[0:48 * S, 0:72 * S]
    big[np.all(big == I0, -1) & (yy > 15.5 * S)] = I1                                       # lower iris lighter
    cv2.ellipse(big, (int(39 * S), int(18 * S)), (int(5.6 * S), int(5.2 * S)), 0, 0, 360, PUP, -1)
    cv2.ellipse(big, (int(46 * S), int(11.5 * S)), (int(4.4 * S), int(3.6 * S)), -25, 0, 360, WHITE, -1)
    cv2.circle(big, (int(32 * S), int(22 * S)), int(1.9 * S), WHITE, -1)
    # mouth: the W upper lip in every frame (3 texels thick); open frames hang a pink mouth under it, fangs at the corners
    if mouth != 'closed':
        d = 2.5 if mouth == 'half' else 5.5
        lip = MOUTH
        bottom = [(32, 37), (28, 39.5 + d * 0.5), (20, 41.5 + d), (10, 41.5 + d), (0, 41 + d)]
        cv2.fillPoly(big, [poly(lip + bottom)], M1, lineType=cv2.LINE_8)
        if mouth == 'wide':
            cv2.ellipse(big, (0, int((43 + d * 0.5) * S)), (int(12 * S), int(d * 0.4 * S)), 0, 0, 360, M0, -1)
        else:
            cv2.ellipse(big, (0, int((42.5 + d * 0.5) * S)), (int(8 * S), int(d * 0.35 * S)), 0, 0, 360, M0, -1)
        cv2.polylines(big, [poly(lip + bottom)], True, INK, int(1.2 * S), lineType=cv2.LINE_8)
        cv2.fillPoly(big, [poly([(28.5, 35.5), (33, 35), (31, 40)])], WHITE, lineType=cv2.LINE_8)
    cv2.polylines(big, [poly(MOUTH)], False, INK, int(3.0 * S), lineType=cv2.LINE_8)
    t[oy:oy + 48, ox:ox + 72, :3] = quantise_down(big, [Y0, INK, I0, I1, PUP, WHITE, M0, M1], S)


face_block(0, 0, 'closed'); face_block(0, 48, 'closed'); face_block(72, 0, 'half'); face_block(144, 0, 'wide')

# body swatch: plain lemon with a lighter crown
rect(*BODY, Y0)
t[BODY[1]:BODY[1] + 6, BODY[0]:BODY[0] + BODY[2], :3] = Y1
# ear front: the inner ear, one step darker with a thin rim, inset from the edges and above the buried base
ex, ey, ew, eh = EARF
ear = np.zeros((eh, ew, 3), np.uint8); ear[:] = Y0
tri = np.array([(8, eh - 9), (ew - 9, eh - 9), (ew // 2, 6)], np.int32)     # front-centre of the cone (the strip is the front half)
cv2.fillPoly(ear, [tri], YI, lineType=cv2.LINE_8)
cv2.polylines(ear, [tri], True, YO, 1, lineType=cv2.LINE_8)
t[ey:ey + eh, ex:ex + ew, :3] = ear
rect(*EARB, Y0)
t[EARB[1]:EARB[1] + EARB[3], EARB[0] + EARB[2] - 6:EARB[0] + EARB[2], :3] = Y2

# tail strip: lemon with 3 slanted purple bands of uneven width, then the solid lavender tip
tx, ty, tw, th = TAIL
S = 4
strip = np.zeros((th * S, tw * S, 3), np.uint8); strip[:] = Y0
u_tip = int(TIP_FROM * tw * S)
cv2.rectangle(strip, (u_tip, 0), (tw * S, th * S), PT, -1)
cv2.rectangle(strip, (u_tip, int(0.55 * th * S)), (tw * S, th * S), PT2, -1)
cv2.line(strip, (u_tip, 0), (u_tip, th * S), PD, int(0.9 * S))
for fr, wd in ((0.12, 7), (0.31, 10), (0.50, 6)):
    u0 = fr * tw * S; sl = 0.55 * S                                  # slant: u shifts with v (a helical band)
    pts = np.array([(u0, 0), (u0 + wd * S, 0), (u0 + wd * S + sl * th, th * S), (u0 + sl * th, th * S)], np.int32)
    cv2.fillPoly(strip, [pts], PB)
    cv2.line(strip, (int(u0 + wd * S), 0), (int(u0 + wd * S + sl * th), th * S), PD, int(0.8 * S))
t[ty:ty + th, tx:tx + tw, :3] = quantise_down(strip, [Y0, Y1, Y2, PB, PD, PT, PT2], S)
t[ty:ty + 2, tx:tx + u_tip // S, :3] = np.where(np.all(t[ty:ty + 2, tx:tx + u_tip // S, :3] == Y0, -1)[..., None], Y1, t[ty:ty + 2, tx:tx + u_tip // S, :3])

# tournament sprite (row 15): four 15x15 frames at (224,96) (240,96) (224,112) (240,112), transparent outside
SPR = [(224, 96), (240, 96), (224, 112), (240, 112)]
t[96:128, 224:256, 3] = 0
for fi, (sx, sy) in enumerate(SPR):
    g = np.zeros((15, 15, 4), np.uint8)
    cv2.ellipse(g, (7, 9), (6, 4), 0, 0, 360, Y0 + (255,), -1)
    for side in (-1, 1):
        pts = np.array([(7 + 2 * side, 6), (7 + 6 * side, 6), (7 + 5 * side, 1)], np.int32)
        cv2.fillPoly(g, [pts], Y0 + (255,))
    g[9, 4] = I1 + (255,); g[9, 10] = I1 + (255,); g[8, 4] = INK + (255,); g[8, 10] = INK + (255,)
    g[11, 6] = INK + (255,); g[11, 8] = INK + (255,); g[12, 7] = INK + (255,)
    tl = [(12, 8), (14, 6), (14, 3)] if fi % 2 == 0 else [(12, 9), (14, 8), (14, 5)]
    for (x0, y0) in tl: g[y0, x0] = PB + (255,)
    t[sy:sy + 15, sx:sx + 15] = g

# ---------------------------------------------------------------- save (tex_import, then the sprite row by hand)
mmd.tex_import(m, b.tim, b.tim.w, b.tim.h, bytearray(t.tobytes()))
pm = np.array(mmd.palette_map(m, b.tim)).reshape(b.tim.h, b.tim.w)
for row in sorted(set(pm.flatten().tolist())):
    cols = np.unique(t[pm == row][:, :3] >> 3 << 3, axis=0)
    print('row', row, 'colours', len(cols))
spal = [Y0, INK, I1, PB, WHITE]
b.tim.pal[15] = [0] + [mmd.rgba_to_c15(*c) for c in spal] + [0] * 10
for (sx, sy) in SPR:
    for y in range(15):
        for x in range(15):
            r_, g_, b_, a_ = t[sy + y, sx + x]
            k = 0 if a_ < 128 else 1 + min(range(len(spal)), key=lambda i: sum((spal[i][j] - int((r_, g_, b_)[j])) ** 2 for j in range(3)))
            b.tim.idx[(sy + y) * b.tim.w + sx + x] = k
os.makedirs(OUT, exist_ok=True)
mp, tp = os.path.join(OUT, 'Nyaromon.MMD'), os.path.join(OUT, 'Nyaromon.TIM')
open(mp, 'wb').write(m.build()); open(tp, 'wb').write(b.tim.to_bytes())
cv2.imwrite(os.path.join(OUT, 'Nyaromon-tex.png'), cv2.resize(cv2.cvtColor(t, cv2.COLOR_RGBA2BGRA), None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST))
spec = f'{mp}:30:{tp}:0:Nyaromon'
print(spec)
print('MMD bytes', os.path.getsize(mp), 'tail length', round(TAIL_LEN), 'ear surface y', round(ys_))
if __name__ == '__main__' and '--nosheet' not in sys.argv:
    sheet(OUT + '/Nyaromon-sheet.png', [spec], panels='mesh:front,mesh:three,mesh:side')
