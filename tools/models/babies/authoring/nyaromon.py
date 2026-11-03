"""Tokomon (type 30) -> Nyaromon, round 2: geometry rebuilt from scratch on the donor's skeleton.

Parts -> bones (the donor's animations are untouched):
  object 0 (bone 2, the body)  : the wide rounded cat head AND the whole tail (static relative to the head: the
                                 feet bones swing 50 deg in the walk hop, which flailed round 1's tail)
  objects 1 / 3 (bones 3 / 5)  : the ears, one wedge each; the inner ear is painted on the front faces
  objects 2 / 4 (ear tips), 5-8 (feet): collapsed to a point (one degenerate triangle each)
Texture: face on the mirrored 72x48 block (u=0 is the centre line) with its three animation frames
(0,48) = restore, (72,0) = half-open mouth, (144,0) = wide-open mouth; body / ears / tail strips on the free part of
the page.  Every CLUT row is painted with its own <=16 colours so tex_import keeps them exact.
Conventions found in the donor: y negative is UP, the model faces -z, x>0 is the viewer's right in the front view,
face winding cross(v1-v0, v2-v0) points INWARD (opposite to the outward normal), normals 4.12 outward.
"""
from lib import *
import math

b = Baby('Nyaromon', 30)
m = b.m; tmd = m.tmd

# ---------------------------------------------------------------- palette (5-bit exact values)
def q(c): return tuple(int(v) >> 3 << 3 for v in c)

Y0 = q((248, 220, 88)); Y1 = q((255, 240, 150)); Y2 = q((232, 186, 60)); Y3 = q((210, 150, 48))
INK = q((24, 16, 16)); WHITE = q((255, 255, 255)); SOFT = q((255, 232, 232))
I0 = q((120, 32, 24)); I1 = q((196, 72, 36)); I2 = q((232, 128, 64)); PUP = q((40, 14, 14))
M0 = q((128, 32, 44)); M1 = q((236, 120, 132))
O0 = q((232, 168, 64)); O1 = q((244, 196, 92)); O2 = q((184, 120, 40))
P0 = q((150, 136, 214)); P1 = q((190, 180, 240)); P2 = q((104, 88, 176)); P3 = q((72, 56, 136))
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


def smooth_normals(part, vids):
    """Per-vertex normals from the faces already added that use only these vertices (area weighted, outward by
    construction of the faces' order being irrelevant: we orient each face normal along the stored face normal)."""
    acc = {v: np.zeros(3) for v in vids}
    for f_vids, f_nids, _, _ in part.f:
        a, b_, c = part.v[f_vids[0]], part.v[f_vids[1]], part.v[f_vids[2]]
        n = np.cross(b_ - a, c - a)
        if n @ sum(part.n[k] for k in f_nids) > 0: n = -n       # should not happen: faces are oriented inward-cross
        n = -n                                                    # inward cross -> outward
        for v in f_vids:
            if v in acc: acc[v] += n
    return acc


def install(oi, part):
    ob = tmd.objects[oi]
    ob._v = [(int(round(p[0])), int(round(p[1])), int(round(p[2])), 0) for p in part.v]
    ob._n = [(int(round(n[0] * 4096)), int(round(n[1] * 4096)), int(round(n[2] * 4096)), 0) for n in part.n]
    ob.prims = part.prims()


def point_object(oi):
    p = Part(); p.vert((0, 0, 0)); p.norm((0, -1, 0))
    p.f.append(([0, 0, 0], [0, 0, 0], [(BODY[0] + 8, BODY[1] + 8)] * 3, ROW_BODY))   # never (0,0): palette_map would hand that face texel to the body row
    install(oi, p)


def repack():
    verts, norms = [], []
    for ob in tmd.objects:
        ob.vert_start, ob.nvert = len(verts), len(ob._v); verts += ob._v
        ob.norm_start, ob.nnorm = len(norms), len(ob._n); norms += ob._n
    tmd.verts, tmd.norms = verts, norms


# ---------------------------------------------------------------- texture layout (page 256x128)
FACE = (0, 0, 72, 48)                       # live block; frames at (0,48) (72,0) (144,0)
BODY = (80, 50, 32, 32)                     # plain body swatch
EARF = (120, 50, 32, 44)                    # ear front (inner ear painted)
EARB = (160, 50, 24, 44)                    # ear back
TAIL = (76, 100, 136, 24)                   # u along the tail, v around (v=100 is the top side)
FACE_Y0, FACE_Y1 = -116.0, -22.0            # the band of the head the face block covers (ring to ring)
FU = lambda x: min(71.0, 0.71 * abs(x))
FV = lambda y: min(47.0, max(0.0, 48.0 * (y - FACE_Y0) / (FACE_Y1 - FACE_Y0)))

# ---------------------------------------------------------------- head: superellipsoid, wider than tall, flat-ish top
HA, HC, HY0, HB = 104.0, 90.0, -74.0, 70.0      # x half-width, z half-depth, centre y, y half-height
HTOP, HBOT = HY0 - HB, HY0 + HB                   # -150 .. -4


def head_r(y):
    """Horizontal radius factor (0..1) of the head at height y."""
    t = (HY0 - y) / HB
    e = 2.05 if t > 0 else 2.2                                    # a little boxier than an ellipse
    t = min(1.0, abs(t))
    return (1 - t ** e) ** (1 / e)


def head_surface_y(x, z):
    """Top surface height of the head above (x, z) (the y where the ring radius reaches that point)."""
    rr = math.hypot(x / HA, z / HC)
    lo, hi = HTOP, HY0
    for _ in range(40):
        mid = (lo + hi) / 2
        if head_r(mid) < rr: lo = mid
        else: hi = mid
    return lo


NAZ = 14
RING_Y = [-139, -129, -116, -100, -84, -66, -48, -34, -22, -12]
head = Part()
top = head.vert((0, HTOP, 0)); bot = head.vert((0, HBOT, 0))
rings = []
for y in RING_Y:
    r = head_r(y); ring = []
    for k in range(NAZ):
        az = 2 * math.pi * k / NAZ
        ring.append(head.vert((HA * r * math.sin(az), y, -HC * r * math.cos(az))))
    rings.append(ring)
# normals: analytic-ish, from the local gradient of the superellipsoid (finite differences on the radius)
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


def ring_face(vids, row_front_ok=True):
    pts = [head.v[v] for v in vids]
    c = sum(pts) / len(pts)
    front = (c[2] < -1) and FACE_Y0 - 1 <= c[1] <= FACE_Y1 + 1 and all(FACE_Y0 - 0.5 <= p[1] <= FACE_Y1 + 0.5 for p in pts)
    uvs = [head_uv(*p, front) for p in pts]
    head.face(vids, [hn[v] for v in vids], uvs, ROW_FACE if front else ROW_BODY)


for k in range(NAZ):
    k2 = (k + 1) % NAZ
    ring_face([top, rings[0][k], rings[0][k2]])
    for i in range(len(rings) - 1):
        ring_face([rings[i][k], rings[i][k2], rings[i + 1][k], rings[i + 1][k2]])
    ring_face([bot, rings[-1][k2], rings[-1][k]])

# ---------------------------------------------------------------- tail (part of the head object): tube on a spline
TAIL_PTS = np.array([
    (28, -96, 44),     # inside the head
    (84, -108, 84),    # leaving the back-right of the head at eye height
    (128, -132, 116),
    (162, -136, 136),
    (186, -106, 138),
    (188, -62, 126),
    (168, -30, 108),
    (136, -18, 92),
    (108, -18, 80),    # the bulb
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
NR, NA = 17, 8


def tail_radius(s):
    if s < 0.62: return 14.5
    if s < 0.78: return 14.5 + 4.5 * (s - 0.62) / 0.16
    return 19.0


centres, tangents = [], []
for i in range(NR):
    s = i / (NR - 1) * 0.985
    j = int(np.searchsorted(arc, s * TAIL_LEN)); j = min(max(j, 1), len(dense) - 2)
    centres.append(dense[j]); t = dense[j + 1] - dense[j - 1]; tangents.append(t / np.linalg.norm(t))
# parallel-transported frame, N starts pointing up (-y)
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
# rounded cap: two shrinking rings and a pole
cap_rings = []
T = tangents[-1]; Nv, Bv = frames[-1]; r_end = tail_radius(1.0); c_end = centres[-1]
for ang in (38, 68):
    a = math.radians(ang); ring = []
    for k in range(NA):
        th = 2 * math.pi * k / NA
        d = math.cos(th) * Nv + math.sin(th) * Bv
        nrm = math.cos(a) * d + math.sin(a) * T
        v = head.vert(c_end + r_end * (math.sin(a) * T + math.cos(a) * d)); ring.append(v); tail_n[v] = head.norm(nrm)
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
install(0, head)

# ---------------------------------------------------------------- ears: a wedge each on bones 3 / 5
EAR_JOINT = {1: (26, -114, -67), 3: (-25, -114, -67)}
EAR_X0, EAR_X1, EAR_Z = 18.0, 88.0, -42.0          # base inner/outer x, base z (world, right ear): near the joint's z so the ear flaps stay rooted
EAR_TIP = (97.0, -242.0, -34.0)
EAR_THICK, EAR_BURY, EAR_MID = 9.0, 24.0, 0.5


def build_ear(oi, side):
    J = np.array(EAR_JOINT[oi], float); p = Part()
    def W(x, y, z): return np.array([x * side, y, z]) - J     # world (right ear) -> bone local, mirrored for the left
    yb0 = head_surface_y(EAR_X0 * side, EAR_Z) + EAR_BURY
    yb1 = head_surface_y(EAR_X1 * side, EAR_Z) + EAR_BURY
    tip = np.array(EAR_TIP)
    base_c = np.array([(EAR_X0 + EAR_X1) / 2, (yb0 + yb1) / 2, EAR_Z])
    h = EAR_MID
    mi = np.array([EAR_X0, yb0, EAR_Z]) * (1 - h) + tip * h; mo = np.array([EAR_X1, yb1, EAR_Z]) * (1 - h) + tip * h
    mi[0] -= 2; mo[0] += 2                                        # slight bow outward
    V = {}
    for name, (x, y, z), dz in (('bif', (EAR_X0, yb0, EAR_Z), -EAR_THICK), ('bof', (EAR_X1, yb1, EAR_Z), -EAR_THICK),
                                ('bib', (EAR_X0, yb0, EAR_Z), EAR_THICK), ('bob', (EAR_X1, yb1, EAR_Z), EAR_THICK),
                                ('mif', mi, -EAR_THICK * 0.55), ('mof', mo, -EAR_THICK * 0.55),
                                ('mib', mi, EAR_THICK * 0.55), ('mob', mo, EAR_THICK * 0.55), ('tip', tip, 0)):
        V[name] = p.vert(W(x, y, z + dz))
    # normals: front, back, inner edge, outer edge (world, then mirrored x)
    front = np.array([0.12 * side, -0.18, -1.0]); back = np.array([-0.05 * side, -0.1, 1.0])
    ein = np.array([-1.0 * side, -0.3, 0]); eout = np.array([1.0 * side, -0.25, 0])
    nf, nb, ni, no = p.norm(front), p.norm(back), p.norm(ein), p.norm(eout)
    # ear-front texture: base (120..151, 93), tip (136, 50)
    def fuv(fr, hgt):       # fr 0 (inner) .. 1 (outer) across the base, hgt 0 base .. 1 tip
        u0 = EARF[0] + 0.5 + (EARF[2] - 1) * (0.5 * hgt + fr * (1 - hgt))
        return (u0, EARF[1] + EARF[3] - 1 - (EARF[3] - 2) * hgt)
    def buv(fr, hgt):
        return (EARB[0] + 0.5 + (EARB[2] - 1) * (0.5 * hgt + fr * (1 - hgt)), EARB[1] + EARB[3] - 1 - (EARB[3] - 2) * hgt)
    p.face([V['bif'], V['bof'], V['mif'], V['mof']], [nf] * 4, [fuv(0, 0), fuv(1, 0), fuv(0, h), fuv(1, h)], ROW_BODY)
    p.face([V['mif'], V['mof'], V['tip']], [nf] * 3, [fuv(0, h), fuv(1, h), fuv(0.5, 1)], ROW_BODY)
    p.face([V['bib'], V['bob'], V['mib'], V['mob']], [nb] * 4, [buv(0, 0), buv(1, 0), buv(0, h), buv(1, h)], ROW_BODY)
    p.face([V['mib'], V['mob'], V['tip']], [nb] * 3, [buv(0, h), buv(1, h), buv(0.5, 1)], ROW_BODY)
    sw = lambda: (BODY[0] + 8, BODY[1] + 8)
    p.face([V['bif'], V['bib'], V['mif'], V['mib']], [ni] * 4, [sw()] * 4, ROW_BODY)
    p.face([V['mif'], V['mib'], V['tip']], [ni] * 3, [sw()] * 3, ROW_BODY)
    p.face([V['bof'], V['bob'], V['mof'], V['mob']], [no] * 4, [sw()] * 4, ROW_BODY)
    p.face([V['mof'], V['mob'], V['tip']], [no] * 3, [sw()] * 3, ROW_BODY)
    install(oi, p)


build_ear(1, 1); build_ear(3, -1)
for oi in (2, 4, 5, 6, 7, 8):
    point_object(oi)
repack()

# ---------------------------------------------------------------- texture
t = b.tex
t[..., :3] = Y0; t[..., 3] = 255


def rect(x, y, w, h, col):
    t[y:y + h, x:x + w, :3] = col


def face_block(ox, oy, mouth):
    """One 72x48 half-face frame at (ox, oy). mouth: 'closed' | 'half' | 'wide'."""
    blk = np.zeros((48, 72, 3), np.uint8); blk[:] = Y0
    S = 4                                                           # draw at 4x, then take the nearest palette colour
    big = cv2.resize(blk, None, fx=S, fy=S, interpolation=cv2.INTER_NEAREST)
    # eye: almond tilted, top point to the outside. centre (x 46, y -94) -> u 32.7, v 15.4
    cx, cy = 33.0 * S, 14.3 * S                                     # eye centre: x 46, y -88 (41% down the head)
    w_, h_ = 16.0 * S, 14.0 * S                                     # half sizes: 32 x 28 px = 45 x 55 units
    ang = -16                                                        # degrees; negative = top leans to +u (outside)
    def almond(scale, col, dx=0, dy=0):
        pts = []
        for i in range(72):
            a = 2 * math.pi * i / 72
            up = max(0.0, -math.sin(a)); dn = max(0.0, math.sin(a))
            px = w_ * scale * math.cos(a) * (1 - 0.62 * up ** 1.3) * (1 - 0.22 * dn ** 2)   # teardrop: pointed top, round bottom
            py = h_ * scale * math.sin(a)
            r = math.radians(ang); X = px * math.cos(r) - py * math.sin(r); Y = px * math.sin(r) + py * math.cos(r)
            pts.append((cx + dx + X, cy + dy + Y))
        cv2.fillPoly(big, [np.array(pts, np.int32)], col, lineType=cv2.LINE_8)
    almond(1.0, INK)
    almond(0.84, I1, -1.3 * S, 0.3 * S)                              # iris shifted inward: the outer rim stays heavy
    # darker iris at the top / toward the pupil, lighter orange at the bottom-inner
    yy, xx = np.mgrid[0:48 * S, 0:72 * S]
    iris = np.all(big == I1, -1)
    grad = (yy - (cy - h_)) / (2 * h_)
    big[iris & (grad < 0.30)] = I0
    big[iris & (grad > 0.78)] = I2
    # pupil: big dark oval in the upper-middle
    cv2.ellipse(big, (int(cx + 1.2 * S), int(cy - 2.2 * S)), (int(8.3 * S), int(8.8 * S)), ang, 0, 360, PUP, -1)
    # highlights: big one upper-outer, small one lower-inner
    cv2.ellipse(big, (int(cx + 5.0 * S), int(cy - 6.5 * S)), (int(4.2 * S), int(3.4 * S)), ang, 0, 360, WHITE, -1)
    cv2.circle(big, (int(cx - 4.5 * S), int(cy + 5.5 * S)), int(1.8 * S), WHITE, -1)
    # mouth
    if mouth == 'closed':      # half of a 'w': centre peak (u0, v33.6) -> valley (14.2, 43.2) -> corner (28.4, 38.4)
        pts = np.array([(0, 34.5 * S), (16.0 * S, 44.0 * S), (33.0 * S, 38.8 * S)], np.int32)
        cv2.polylines(big, [pts], False, INK, int(1.4 * S), lineType=cv2.LINE_8)
    else:
        if mouth == 'half': ax, ay, vy = 7.0, 4.5, 39.5
        else: ax, ay, vy = 12.5, 7.5, 38.5
        cv2.ellipse(big, (0, int(vy * S)), (int(ax * S), int(ay * S)), 0, 0, 360, M0, -1)
        cv2.ellipse(big, (0, int((vy + ay * 0.55) * S)), (int(ax * 0.6 * S), int(ay * 0.5 * S)), 0, 0, 360, M1, -1)
        cv2.ellipse(big, (0, int(vy * S)), (int(ax * S), int(ay * S)), 0, 0, 360, INK, int(1.3 * S))
    # down-sample by majority of the palette colour per texel
    pal = np.array([Y0, INK, I0, I1, I2, PUP, WHITE, M0, M1], np.int32)
    small = np.zeros((48, 72, 3), np.uint8)
    idx = np.argmin(((big[..., None, :].astype(np.int32) - pal[None, None]) ** 2).sum(-1), -1)
    for y in range(48):
        for x in range(72):
            cell = idx[y * S:(y + 1) * S, x * S:(x + 1) * S].ravel()
            small[y, x] = pal[np.bincount(cell).argmax()]
    t[oy:oy + 48, ox:ox + 72, :3] = small


face_block(0, 0, 'closed'); face_block(0, 48, 'closed'); face_block(72, 0, 'half'); face_block(144, 0, 'wide')

# body swatch: plain yellow with a slightly lighter crown
rect(*BODY, Y0)
t[BODY[1]:BODY[1] + 6, BODY[0]:BODY[0] + BODY[2], :3] = Y1
# ear front: the inner ear (orange triangle with a dark rim) inside the ear triangle; base (120..151, 93), tip (136, 50)
rect(*EARF, Y0)
ex, ey, ew, eh = EARF
S = 4
ear = np.zeros((eh, ew, 3), np.uint8); ear[:] = Y0
tri = np.array([(7, eh - 10), (ew - 8, eh - 10), (ew // 2, 7)], np.int32)
cv2.fillPoly(ear, [tri], O0, lineType=cv2.LINE_8)
tri3 = np.array([(11, eh - 13), (ew - 11, eh - 13), (ew // 2 - 1, 17)], np.int32)
cv2.fillPoly(ear, [tri3], O1, lineType=cv2.LINE_8)
cv2.polylines(ear, [tri], True, O2, 1, lineType=cv2.LINE_8)
t[ey:ey + eh, ex:ex + ew, :3] = ear
rect(*EARB, Y0)
t[EARB[1]:EARB[1] + EARB[3], EARB[0] + EARB[2] - 6:EARB[0] + EARB[2], :3] = Y2

# tail strip: yellow with purple wedges hanging from the top side, then the solid purple end
tx, ty, tw, th = TAIL
rect(tx, ty, tw, th, Y0)
strip = np.zeros((th * S, tw * S, 3), np.uint8); strip[:] = Y0
u_end = int(0.64 * tw * S)
cv2.rectangle(strip, (u_end, 0), (tw * S, th * S), P0, -1)
cv2.rectangle(strip, (u_end, 0), (tw * S, int(0.42 * th * S)), P1, -1)
cv2.rectangle(strip, (u_end, int(0.78 * th * S)), (tw * S, th * S), P2, -1)
cv2.line(strip, (u_end, 0), (u_end, th * S), P3, int(0.8 * S))
for fr in (0.11, 0.26, 0.40, 0.53):
    u = int(fr * tw * S); w2 = int(0.06 * tw * S); d = int(0.62 * th * S)
    for off, col in ((0, P3), (-1.1 * S, P0)):
        pts = np.array([(u - w2, 0), (u + w2, 0), (u + w2 * 0.1, d + off * 0)], np.int32)
        cv2.fillPoly(strip, [pts], col) if col == P3 else None
    pts = np.array([(u - w2 + 1.0 * S, 0), (u + w2 - 1.0 * S, 0), (u + w2 * 0.05, d - 1.2 * S)], np.int32)
    cv2.fillPoly(strip, [pts], P0)
    pts = np.array([(u - w2 + 1.0 * S, 0), (u + w2 * 0.3, 0), (u - w2 * 0.2, d * 0.5)], np.int32)
    cv2.fillPoly(strip, [pts], P1)
    # the wedge wraps: mirror a short stub at the bottom edge (v wraps around the tube)
    pts = np.array([(u - w2, th * S), (u + w2, th * S), (u + w2 * 0.1, th * S - int(0.25 * th * S))], np.int32)
    cv2.fillPoly(strip, [pts], P3)
    pts = np.array([(u - w2 + 1.0 * S, th * S), (u + w2 - 1.0 * S, th * S), (u + w2 * 0.05, th * S - int(0.25 * th * S) + 1.2 * S)], np.int32)
    cv2.fillPoly(strip, [pts], P2)
pal = np.array([Y0, Y1, Y2, P0, P1, P2, P3], np.int32)
idx = np.argmin(((strip[..., None, :].astype(np.int32) - pal[None, None]) ** 2).sum(-1), -1)
for y in range(th):
    for x in range(tw):
        t[ty + y, tx + x, :3] = pal[np.bincount(idx[y * S:(y + 1) * S, x * S:(x + 1) * S].ravel()).argmax()]
t[ty:ty + 2, tx:tx + u_end // S, :3] = Y1                          # a lighter top line along the yellow part

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
    # tail: a purple hook on the right, two poses
    if fi % 2 == 0: tl = [(12, 8), (14, 6), (14, 3)]
    else: tl = [(12, 9), (14, 8), (14, 5)]
    for (x0, y0) in tl: g[y0, x0] = P0 + (255,)
    t[sy:sy + 15, sx:sx + 15] = g

# ---------------------------------------------------------------- save (tex_import, then the sprite row by hand)
mmd.tex_import(m, b.tim, b.tim.w, b.tim.h, bytearray(t.tobytes()))
pm = np.array(mmd.palette_map(m, b.tim)).reshape(b.tim.h, b.tim.w)
for row in sorted(set(pm.flatten().tolist())):
    cols = np.unique(t[pm == row][:, :3] >> 3 << 3, axis=0)
    print('row', row, 'colours', len(cols))
# sprite: its own palette row 15 (palette_map lumps the corner into row 0; re-index it by hand)
spal = [Y0, INK, I1, P0, WHITE]
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
print('MMD bytes', os.path.getsize(mp), 'tail length', round(TAIL_LEN))
if __name__ == '__main__' and '--nosheet' not in sys.argv:
    sheet(OUT + '/Nyaromon-sheet.png', [spec], panels='mesh:front,mesh:three,mesh:side')
