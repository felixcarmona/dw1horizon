"""Koromon -> Motimon (round 3): a round pink mochi ball on a flared skirt, on Koromon's hopping skeleton.

Donor switched from Poyomon (round 1) to Koromon in round 2: Poyomon's one moving bone sits 150 units up and its mesh
hangs under it 145 units above the ground (a floating ghost; sleep and praise rotate about that point), while
Motimon stands on the ground and bounces. Koromon's body bone is inside the body, its walk is a hop with
squash and stretch, it sleeps in place, and its face frames are bigger (eye 40x32, mouth 40x24).

Round 3 (critique/Motimon.md): the body is a SPHERE (head, widest at the eye line) over a waist and a skirt that
flares back out to the sphere's width with six uneven scallops; the skirt widens downward so its outside faces up
and the floor cap (now body pink, from the hem's own vertices) is never seen from the game camera; eyes on the
equator and 18 % of the width; mouth lower and wider; thick tapered arm cones with three grey claw pyramids; warm
pink palette with a gloss on the upper left; sleeping eye frame fully closed.

Everything is rebuilt: object 0 (bone 2) = body, floor cap, both arms with claws; the ear objects 1-4 are collapsed
to a point (one degenerate primitive each). Arms on the ear bones (MOTI_ARMS=ears, objects 1/3) were tried in
round 2 and rejected: those bones turn 7-30 degrees about a pivot at the top of the head, the arms only slide.
Texture: one CLUT row (0) painted with an exact palette (no quantiser), every tex-anim source frame repainted,
the tournament sprite (row 15) drawn by hand.
"""
import math
from lib import *
import mmd

b = Baby(os.environ.get('MOTI_NAME', 'Motimon'), 2)
T = b.m.tmd
H, R, GROUND = 160.0, 66.0, 69.0            # height, sphere radius (widest), ground in bone-2 space (y down)
CBA, TSB = 0x7A00, 0x05                     # CLUT row 0, texture page 5
ARMS_ON = os.environ.get('MOTI_ARMS', 'body')   # 'body': rigid on object 0; 'ears': objects 1/3 (bones 3/5), rejected


# ---------------------------------------------------------------- mesh builder
class Mesh:
    def __init__(self):
        self.v, self.n, self.p = [], [], []

    def vert(self, p, n):
        n = np.asarray(n, float); n = n / (np.linalg.norm(n) or 1.0)
        self.v.append(tuple(float(c) for c in p)); self.n.append(tuple(n))
        return len(self.v) - 1

    def tri(self, a, b_, c, uva, uvb, uvc, both=False):
        """Front face = the side the vertex normals point to (DW1: (v1-v0)x(v2-v0) is opposite the normal)."""
        va, vb, vc = (np.array(self.v[i]) for i in (a, b_, c))
        g = np.cross(vb - va, vc - va)
        n = np.array(self.n[a]) + np.array(self.n[b_]) + np.array(self.n[c])
        if np.dot(g, n) > 0:
            b_, c, uvb, uvc = c, b_, uvc, uvb
        self.p.append((a, b_, c, uva, uvb, uvc))
        if both:
            self.p.append((a, c, b_, uva, uvc, uvb))

    def quad(self, a, b_, c, d, uva, uvb, uvc, uvd):
        """a b c d around the quad; split into two triangles."""
        self.tri(a, b_, c, uva, uvb, uvc); self.tri(a, c, d, uva, uvc, uvd)

    def translate(self, off):
        self.v = [tuple(np.array(v) + off) for v in self.v]


def commit(objs):
    """objs: {object index: Mesh}; the other objects collapse to a point with one degenerate primitive."""
    T.verts, T.norms = [], []
    for oi, ob in enumerate(T.objects):
        m = objs.get(oi)
        if m is None:
            m = Mesh(); m.vert((0, 0, 0), (0, -1, 0)); m.p = [(0, 0, 0, (0, 64), (0, 64), (0, 64))]
        ob.vert_start, ob.norm_start = len(T.verts), len(T.norms)
        ob.nvert = ob.nnorm = len(m.v)
        for v in m.v:
            T.verts.append((int(round(v[0])), int(round(v[1])), int(round(v[2])), 0))
        for n in m.n:
            T.norms.append((int(round(n[0] * 4096)), int(round(n[1] * 4096)), int(round(n[2] * 4096)), 0))
        ob.prims = []
        for (a, b_, c, uva, uvb, uvc) in m.p:
            uv = [(int(round(u)), int(round(v))) for u, v in (uva, uvb, uvc)]
            d = dict(mode=0x34, flag=0, olen=9, uv=uv, cba=CBA, tsb=TSB, uvpad=[0], colors=[],
                     norms=[a, b_, c], verts=[a, b_, c], pad=[])
            ob.prims.append(mmd.Prim.encode(d))


# ---------------------------------------------------------------- body
# radius fraction by height fraction h (0 = hem, 1 = top): a sphere centred at h 0.62 (its equator is the eye
# line; 0.40 tall = R wide, so it is round), pinched to 0.86 at the waist (h 0.22-0.28) and flared to 1.03 at the hem; the skirt widens downward, so
# its outside faces up and hides the floor cap from a camera above
PROF = [(0.0, 1.03), (0.05, 1.0), (0.10, 0.955), (0.16, 0.90), (0.22, 0.865), (0.28, 0.855), (0.34, 0.87),
        (0.40, 0.90), (0.46, 0.945), (0.52, 0.98), (0.58, 0.995), (0.62, 1.0), (0.68, 0.985), (0.74, 0.95),
        (0.80, 0.89), (0.86, 0.79), (0.91, 0.67), (0.95, 0.52), (0.975, 0.37), (0.99, 0.22), (1.0, 0.0)]
RINGS = [0.15, 0.26, 0.36, 0.52, 0.72, 0.83, 0.91, 0.96, 0.985]   # 2..3 = mouth band, 3..4 = eye band
# segment boundaries per ring (degrees from the front, segment k = SEG[k]..SEG[k+1], the last wraps to 180):
# the mouth band is 28 wide, the eye band's top edge narrows the inner boundary to 10 so the eyes sit closer
SEG_A = [-180, -150, -120, -92, -66, -40, -14, 14, 40, 66, 92, 120, 150]      # rings 0..3
SEG_B = [-180, -150, -120, -92, -66, -40, -10, 10, 40, 66, 92, 120, 150]      # rings 4..
NSEG = len(SEG_A)
RING_SEG = [SEG_A if i <= 3 else SEG_B for i in range(len(RINGS))]
MOUTH_BAND, EYE_BAND = 2, 3
MOUTH_SEG = SEG_A.index(-14)
EYE_SEG = (SEG_A.index(14), SEG_A.index(-40))
LOBES, LOBE_H, LOBE_R, HEM_N = 6, 0.075, 0.035, 3   # HEM_N hem vertices per segment


def seg_bounds(seg, k):
    return seg[k], (seg[k + 1] if k + 1 < NSEG else seg[0] + 360)


def rad(h):
    return R * float(np.interp(h, [p[0] for p in PROF], [p[1] for p in PROF]))


def body_point(phi, h):
    r = rad(h); a = math.radians(phi)
    return np.array([r * math.sin(a), GROUND - h * H, -r * math.cos(a)])


def body_normal(phi, h):
    e = 0.01
    drdup = (rad(min(1, h + e)) - rad(max(0, h - e))) / (2 * e * H)
    a = math.radians(phi)
    return np.array([math.sin(a), drdup, -math.cos(a)])


def strip_uv(phi, h):
    """Body skin strip: u 8..136 around (front at u=72), v 60 (top) .. 124 (hem)."""
    return (72 + phi * 128 / 360.0, 124 - h * 64)


def lobe(p):
    """Hem scallops: 0 at a lobe tip, 1 at a cusp; lobes of uneven width (the phase wobbles)."""
    q = p + 9 * math.sin(math.radians(2 * p + 40))
    return (1 - math.cos(math.radians(LOBES * q))) / 2


def build_body(m):
    rings = []
    for i, h in enumerate(RINGS):
        rings.append([m.vert(body_point(p, h), body_normal(p, h)) for p in RING_SEG[i]])
    apex = m.vert((0, GROUND - H, 0), (0, -1, 0))
    # hem: HEM_N vertices per segment, six uneven rounded lobes (a tip at the front)
    hem_phi = []
    for k in range(NSEG):
        a, b_ = seg_bounds(SEG_A, k)
        hem_phi += [a + (b_ - a) * j / HEM_N for j in range(HEM_N)]
    hem = []
    for p in hem_phi:
        w = lobe(p)
        h = LOBE_H * w * (0.85 + 0.3 * math.sin(math.radians(3 * p + 70)))
        r = R * (PROF[0][1] + LOBE_R * (1 - w) - 0.03 * w)
        a = math.radians(p)
        pt = (r * math.sin(a), GROUND - h * H, -r * math.cos(a))
        hem.append((m.vert(pt, (math.sin(a), -0.45 + 0.25 * w, -math.cos(a))), p, h))
    # shell quads
    for i in range(len(RINGS) - 1):
        for k in range(NSEG):
            k2 = (k + 1) % NSEG
            p0, p1 = seg_bounds(RING_SEG[i], k)
            q0, q1 = seg_bounds(RING_SEG[i + 1], k)
            lo, hi = RINGS[i], RINGS[i + 1]
            A, B, C, D = rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]
            if i == MOUTH_BAND and k == MOUTH_SEG:   # mouth frame, u 0..40 left->right, v 32 top .. 56 bottom
                m.quad(A, B, C, D, (0, 56), (40, 56), (40, 32), (0, 32))
            elif i == EYE_BAND and k == EYE_SEG[0]:  # right eye (phi 14..40): inner edge u 8, outer u 48
                m.quad(A, B, C, D, (8, 32), (48, 32), (48, 0), (8, 0))
            elif i == EYE_BAND and k == EYE_SEG[1]:  # left eye (phi -40..-14): inner edge u 8
                m.quad(A, B, C, D, (48, 32), (8, 32), (8, 0), (48, 0))
            else:
                m.quad(A, B, C, D, strip_uv(p0, lo), strip_uv(p1, lo), strip_uv(q1, hi), strip_uv(q0, hi))
    # apex fan
    top = rings[-1]
    for k in range(NSEG):
        k2 = (k + 1) % NSEG
        p0, p1 = seg_bounds(RING_SEG[-1], k)
        m.tri(apex, top[k], top[k2], strip_uv((p0 + p1) / 2, 1.0), strip_uv(p0, RINGS[-1]), strip_uv(p1, RINGS[-1]))
    # hem to the first ring: fanned from the ring's two vertices
    r1 = rings[0]
    for k in range(NSEG):
        k2 = (k + 1) % NSEG
        hv = [hem[(HEM_N * k + j) % len(hem)] for j in range(HEM_N + 1)]
        hv = [(i, q + 360 if j and q < hv[0][1] else q, h) for j, (i, q, h) in enumerate(hv)]
        p0, p1 = seg_bounds(SEG_A, k)
        half = HEM_N // 2 + 1
        for j in range(half):
            (a, qa, ha), (b_, qb, hb) = hv[j], hv[j + 1]
            m.tri(r1[k], a, b_, strip_uv(p0, RINGS[0]), strip_uv(qa, ha), strip_uv(qb, hb))
        (a, qa, ha) = hv[half]
        m.tri(r1[k], a, r1[k2], strip_uv(p0, RINGS[0]), strip_uv(qa, ha), strip_uv(p1, RINGS[0]))
        for j in range(half, HEM_N):
            (a, qa, ha), (b_, qb, hb) = hv[j], hv[j + 1]
            m.tri(r1[k2], a, b_, strip_uv(p1, RINGS[0]), strip_uv(qa, ha), strip_uv(qb, hb))
    # floor cap: the hem's own vertices (duplicated with downward normals) fanned to a centre just above the floor
    cap = [m.vert(m.v[i], (0, 1, 0)) for (i, _, _) in hem]
    centre = m.vert((0, GROUND - 0.03 * H, 0), (0, 1, 0))
    for k in range(len(cap)):
        m.tri(centre, cap[k], cap[(k + 1) % len(cap)], (155, 111), (142, 100), (168, 100))
    return m


# ---------------------------------------------------------------- arms
def build_arm(m, root, dirn, length, r0, r1, up, claw_angles, bend=(0, 0, 0)):
    """A chubby dough stub (owner, round 4): a tucked-in root, a fat bulge just outside the body, a rounded mitten
    end, three small dark claw nubs. 6-sided rings along dirn.
    Texture: arm patch u 140..200 (root->tip) x v 60..92 (around; v 60 = top), claws at u 204..216, v 60..72."""
    d = np.asarray(dirn, float); d /= np.linalg.norm(d)
    u = np.cross(d, up); u /= np.linalg.norm(u)
    w = np.cross(d, u)                                   # w points "down-ish" if up is up
    root = np.asarray(root, float); bend = np.asarray(bend, float)
    stations = [(0.0, r0 * 0.7, 0.0), (0.3, r0, 0.0), (0.6, r0 * 0.9, 0.2), (0.85, r1, 0.5), (1.0, r1 * 0.62, 0.8)]
    rings = []
    for t, r, tilt in stations:
        c = root + d * (t * length) + bend * t * t
        ring = []
        for k in range(6):
            al = math.radians(60 * k - 90)                # k=0 at the top (-w)
            off = math.cos(al) * u + math.sin(al) * w
            ring.append(m.vert(c + r * off, off * (1 - tilt) + d * tilt))
        rings.append(ring)
    capv = m.vert(root + d * (length + r1 * 0.35) + bend, d)
    for i in range(len(stations) - 1):
        t0, t1 = stations[i][0], stations[i + 1][0]
        for k in range(6):
            k2 = (k + 1) % 6
            v0, v1 = 60 + 32 * k / 6.0, 60 + 32 * (k + 1) / 6.0
            m.quad(rings[i][k], rings[i + 1][k], rings[i + 1][k2], rings[i][k2],
                   (140 + 60 * t0, v0), (140 + 60 * t1, v0), (140 + 60 * t1, v1), (140 + 60 * t0, v1))
    for k in range(6):
        k2 = (k + 1) % 6
        v0, v1 = 60 + 32 * k / 6.0, 60 + 32 * (k + 1) / 6.0
        m.tri(capv, rings[-1][k], rings[-1][k2], (199, (v0 + v1) / 2), (197, v0), (197, v1))
    # claws: three small dark nubs (blunt pyramids) on the end of the mitten, splayed
    tip = root + d * length + bend
    for al_deg in claw_angles:
        al = math.radians(al_deg - 90)
        off = math.cos(al) * u + math.sin(al) * w
        base = tip + off * (r1 * 0.68) + d * 1.5
        side = np.cross(d, off); side /= np.linalg.norm(side)
        axis = d * 0.8 + off * 0.6; axis /= np.linalg.norm(axis)
        b0 = m.vert(base + side * 3.2, side)
        b1 = m.vert(base - side * 3.2, -side)
        b2 = m.vert(base - off * 2.8 - d * 1.2, -off)
        b3 = m.vert(base + off * 2.8, off)
        pk = m.vert(base + axis * 5.0, axis)
        for (x, y) in ((b0, b3), (b3, b1), (b1, b2), (b2, b0)):
            m.tri(x, y, pk, (206, 62), (214, 62), (210, 70))
    return m


ARM_R0, ARM_R1 = 19.0, 12.0      # bulge radius, mitten radius (twice round 3)
# raised arm (x < 0, the viewer's left in the front view): up and outward about 52 degrees, claws on top
ARM_L = dict(root=(-44, GROUND - 0.50 * H, -18), dirn=(-0.62, -0.76, -0.20), length=46, r0=ARM_R0, r1=ARM_R1,
             up=(0.3, -1, 0), claw_angles=(-60, 0, 60), bend=(3, -2, -2))
# stretched arm (x > 0): sideways, slightly down and forward
ARM_R = dict(root=(44, GROUND - 0.44 * H, -16), dirn=(0.93, 0.12, -0.35), length=50, r0=ARM_R0, r1=ARM_R1,
             up=(0, -1, 0), claw_angles=(-60, 0, 60), bend=(0, 4, -2))

body = build_body(Mesh())
arm_l, arm_r = build_arm(Mesh(), **ARM_L), build_arm(Mesh(), **ARM_R)


def check_winding(m, outward):
    """Independent of the normals: the DW1 front side (-(v1-v0)x(v2-v0)) must face outward(centroid)."""
    bad = 0
    for (a, b_, c, *_) in m.p:
        va, vb, vc = (np.array(m.v[i]) for i in (a, b_, c))
        front = -np.cross(vb - va, vc - va)
        if np.dot(front, outward((va + vb + vc) / 3)) < 0: bad += 1
    return bad


def arm_outward(spec):
    root, d = np.array(spec['root'], float), np.array(spec['dirn'], float); d /= np.linalg.norm(d)
    return lambda c: (c - root) - d * np.dot(c - root, d) + d * 0.2 * max(0.0, np.dot(c - root, d) - spec['length'])


print('inward-facing triangles: body %d, arm_l %d, arm_r %d' % (
    check_winding(body, lambda c: c - np.array([0, GROUND - H * 0.55, 0])),
    check_winding(arm_l, arm_outward(ARM_L)), check_winding(arm_r, arm_outward(ARM_R))))
if ARMS_ON == 'body':
    for a in (arm_l, arm_r):
        base = len(body.v)
        body.v += a.v; body.n += a.n
        body.p += [(p[0] + base, p[1] + base, p[2] + base, p[3], p[4], p[5]) for p in a.p]
    commit({0: body})
else:   # bones 3 (x>0, object 1) and 5 (x<0, object 3) sit at (+-25, -40, -41) from bone 2
    arm_r.translate(np.array([-25, 40, 41], float)); arm_l.translate(np.array([25, 40, 41], float))
    commit({0: body, 1: arm_r, 3: arm_l})

# ---------------------------------------------------------------- texture (row 0, exact palette)
W_ = (248, 248, 248)
# warm skin ramp: gloss white .. the art's pink #F7C5CE (index 5) .. hem folds #E9A6B4 (7) .. underside
PINK = [(248, 248, 248), (248, 240, 240), (248, 232, 232), (248, 224, 224), (248, 216, 216), (248, 200, 208),
        (240, 184, 192), (232, 168, 176), (224, 152, 168), (208, 128, 152)]
SKIN = PINK[5]
K = (16, 16, 24); G1 = (88, 88, 96); G2 = (168, 168, 176)
R1 = (232, 40, 56); R2 = (152, 24, 40)
t = b.tex
t[..., :3] = SKIN; t[..., 3] = 255


def light(phi, h):
    """Skin lightness in ramp units (0 white .. 1 deepest). The skin is FLAT (one ramp step, index 4) so that no
    quantisation step of a painted gradient can show as a wall or as the face frames' rectangle under the game's
    per-vertex lighting (that lighting does the shading, like DW1's own babies); on top of it only a gloss oval on
    the upper left of the head (above the eye band) and a one-step shadow on the hem's lowest rows."""
    phi = (phi + 180) % 360 - 180
    L = np.full(np.broadcast(phi, h).shape, 5.0 / 9.0)
    L = L + 0.40 * np.exp(-(((phi + 30) / 22.0) ** 2 + ((h - 0.88) / 0.06) ** 2))   # gloss, kept above the eye band
    L = L - 0.15 * np.clip((0.06 - h) / 0.06, 0, 1)
    return L


def ramp_fill(sub, L):
    L = np.broadcast_to(np.asarray(L, float), sub.shape[:2])
    idx = np.clip(np.round((1 - L) * (len(PINK) - 1)), 0, len(PINK) - 1).astype(int)
    pal = np.array(PINK, np.uint8)
    sub[..., :3] = pal[idx]


# body strip u 8..136, v 60..124
vv, uu = np.mgrid[60:124, 8:136]
ramp_fill(t[60:124, 8:136], light((uu + 0.5 - 72) * 360 / 128.0, (124 - (vv + 0.5)) / 64.0))
# arm patch u 140..200 x v 60..92: the same flat skin as the body (the game's lighting shades the stub)
t[60:92, 140:200, :3] = PINK[4]
t[60:72, 204:216, :3] = G1                      # claws
t[96:126, 140:170, :3] = PINK[6]                # floor cap: a mid pink, read as the skirt if ever seen


# ---- face frames. Eye frame 40x32: dst (8,0); sources (56,0) angry, (96,0) sleep/half, (136,0) closed,
# (176,0) wide, (216,0) happy/asleep, (216,32) open. Mouth 40x24: dst (0,32); (56,32) open, (96,32) wide, (136,32) rest.
def eye_bg(sub):
    h_, w_ = sub.shape[:2]
    vv, uu = np.mgrid[0:h_, 0:w_]
    phi = 12 + (uu + 0.5) * 28.0 / w_
    hh = RINGS[EYE_BAND + 1] - (vv + 0.5) * (RINGS[EYE_BAND + 1] - RINGS[EYE_BAND]) / h_
    ramp_fill(sub, light(phi, hh))


EC, ER = (20, 16), (16, 12)      # eye centre and radii in the frame (frame = 31 x 32 units: a 25 x 24 eye)


def eye_open(sub, lid=0, wide=False, angry=False):
    eye_bg(sub); bg = sub.copy()
    cv2.ellipse(sub, EC, ER, 0, 0, 360, (*K, 255), -1)
    if angry:   # a slanted lid from the inner top (the inner side is u=0)
        msk = np.zeros(sub.shape[:2], np.uint8)
        cv2.fillPoly(msk, [np.array([(0, 0), (40, 0), (40, 6), (0, 14)])], 1)
        sub[msk > 0] = bg[msk > 0]
        cv2.line(sub, (2, 13), (38, 5), (*K, 255), 2)
    if lid:
        sub[:lid] = bg[:lid]
        cv2.line(sub, (3, lid), (37, lid), (*K, 255), 2)
    hy = max(9, lid + 4)
    cv2.circle(sub, (25, hy), 5 if wide else 4, (*W_, 255), -1)       # big highlight top-outer
    sub[21:23, 14:16, :3] = G2                                        # small one bottom-inner


def eye_arc(sub, kind):
    eye_bg(sub)
    if kind == 'happy':      # an arch, 3 px
        cv2.ellipse(sub, (20, 20), (12, 9), 0, 200, 340, (*K, 255), 3)
    elif kind == 'closed':   # a gentle downward curve
        cv2.ellipse(sub, (20, 11), (12, 7), 0, 20, 160, (*K, 255), 3)
    else:                    # asleep: a flatter closed line, a little lower
        cv2.ellipse(sub, (20, 13), (12, 4), 0, 20, 160, (*K, 255), 3)


eye_open(t[0:32, 8:48]); eye_open(t[32:64, 216:256])
eye_arc(t[0:32, 96:136], 'asleep')
eye_open(t[0:32, 176:216], wide=True)
eye_open(t[0:32, 56:96], angry=True)
eye_arc(t[0:32, 136:176], 'closed')
eye_arc(t[0:32, 216:256], 'happy')
t[0:32, 48:56, :3] = PINK[3]
t[32:64, 176:216, :3] = SKIN


def mouth_bg(sub):
    h_, w_ = sub.shape[:2]
    vv, uu = np.mgrid[0:h_, 0:w_]
    phi = -14 + (uu + 0.5) * 28.0 / w_
    hh = RINGS[MOUTH_BAND + 1] - (vv + 0.5) * (RINGS[MOUTH_BAND + 1] - RINGS[MOUTH_BAND]) / h_
    ramp_fill(sub, light(phi, hh))


def mouth(sub, depth, hw=9.5, lw=18):
    """The reference's cat mouth: a thin 'w' lip whose outer ends curl up and whose middle peak rises between two
    valleys; from the valleys hangs the opening, an inverted egg of plain bright red with a black outline."""
    mouth_bg(sub)
    cx, y_end, y_val, y_peak = 20, 2, 7, 3
    top = []
    for i in range(0, 21):
        x = -hw + 2 * hw * i / 20.0
        u = abs(x) / hw
        top.append((cx + x, y_val - (y_val - y_peak) * (1 - u) ** 1.5))
    side = []
    for i in range(1, 21):
        sgn = i / 20.0
        w = hw * math.sqrt(max(0.0, 1 - sgn ** 2.1)) * (1 - 0.18 * sgn)
        side.append((w, y_val + depth * sgn))
    right = [(cx + w, y) for w, y in side]
    left = [(cx - w, y) for w, y in reversed(side)]
    poly = np.array([(int(round(x)), int(round(y))) for x, y in top + right + left], np.int32)
    cv2.fillPoly(sub, [poly], (*R1, 255))
    cv2.polylines(sub, [poly], True, (*K, 255), 1)
    pts = []
    for i in range(0, 61):
        x = -lw + 2 * lw * i / 60.0
        u = abs(x) / lw
        if u > 0.5:
            v = (u - 0.5) / 0.5
            y = y_val - (y_val - y_end) * v ** 2.2
        else:
            v = u / 0.5
            y = y_peak + (y_val - y_peak) * (1 - (1 - v) ** 1.6)
        pts.append((int(round(cx + x)), int(round(y))))
    cv2.polylines(sub, [np.array(pts, np.int32)], False, (*K, 255), 2)


mouth(t[32:56, 0:40], 14)                  # live
mouth(t[32:56, 136:176], 14)               # rest: the reference's open smile
mouth(t[32:56, 56:96], 16, hw=11)          # open
mouth(t[32:56, 96:136], 16, hw=12.5, lw=18)  # wide (eating, snoring)
t[32:56, 40:56, :3] = PINK[3]

# ---- tournament sprite: four 15x15 faces at u 224/240, v 96/112, CLUT row 15 (written straight into the TIM)
SPR = np.zeros((32, 32, 4), np.uint8)
SPR_PAL = [(0, 0, 0), K, SKIN, W_, R1, PINK[2]]


def sprite(sub, mood):
    cv2.ellipse(sub, (7, 8), (6, 6), 0, 0, 360, (*SKIN, 255), -1)
    cv2.ellipse(sub, (7, 7), (3, 3), 0, 0, 360, (*PINK[2], 255), -1)
    if mood in ('open', 'hurt'):
        for ex in (4, 10): sub[5:8, ex:ex + 2] = (*K, 255); sub[5, ex] = (*W_, 255)
    elif mood == 'happy':
        for ex in (3, 9): cv2.line(sub, (ex, 6), (ex + 2, 5), (*K, 255), 1); cv2.line(sub, (ex + 2, 5), (ex + 4, 6), (*K, 255), 1)
    else:
        for ex in (4, 10): sub[6, ex:ex + 3] = (*K, 255)
    sub[9, 5:10] = (*K, 255) if mood != 'hurt' else (*R1, 255)
    sub[10, 6:9] = (*R1, 255) if mood in ('open', 'happy') else sub[10, 6:9]


for (x, y), mood in zip([(0, 0), (16, 0), (0, 16), (16, 16)], ('open', 'happy', 'closed', 'hurt')):
    sprite(SPR[y:y + 15, x:x + 15], mood)


def save():
    cols = set(map(tuple, (t[..., :3] >> 3 << 3).reshape(-1, 3).tolist()))
    assert len(cols) <= 16, f'row 0 would be quantised: {len(cols)} colours'
    spec = b.save()
    tim = b.tim
    pal = [0] + [mmd.rgba_to_c15(*c) for c in SPR_PAL[1:]]
    tim.pal[15] = pal + [0] * (16 - len(pal))
    for y in range(32):
        for x in range(32):
            r, g, bb, a = SPR[y, x]
            idx = 0 if a < 128 else 1 + min(range(len(SPR_PAL) - 1), key=lambda k: sum((SPR_PAL[k + 1][i] - int((r, g, bb)[i])) ** 2 for i in range(3)))
            tim.idx[(96 + y) * tim.w + 224 + x] = idx
    open(os.path.join(OUT, b.name + '.MMD'), 'wb').write(b.m.build())
    open(os.path.join(OUT, b.name + '.TIM'), 'wb').write(tim.to_bytes())
    return spec


spec = save()
print(spec)
print('MMD bytes', os.path.getsize(os.path.join(OUT, b.name + '.MMD')), 'verts', sum(o.nvert for o in T.objects),
      'prims', sum(len(o.prims) for o in T.objects))
if __name__ == '__main__':
    sheet(OUT + '/' + b.name + '-sheet.png', [spec], panels='mesh:front,mesh:three,mesh:side')
