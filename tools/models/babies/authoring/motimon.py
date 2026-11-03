"""Koromon -> Motimon (round 2): a soft pink mochi bell on Koromon's hopping skeleton.

Donor switched from Poyomon (round 1) to Koromon: Poyomon's one moving bone sits 150 units up and its mesh
hangs under it 145 units above the ground (a floating ghost; sleep and praise rotate about that point), while
Motimon stands on the ground and bounces. Koromon's body bone is inside the body, its walk is a hop with
squash and stretch, it sleeps in place, and its face frames are bigger (eye 40x32, mouth 40x24).

Everything is rebuilt: object 0 (bone 2) = body of revolution with a six-lobe skirt and a floor cap, the two
arms with claws; the ear objects 1-4 are collapsed to a point (one degenerate primitive each).
Arms on the ear bones (MOTI_ARMS=ears, objects 1/3) were built and rendered side by side over idle, happy, sleep,
hit and faint: the ear bones turn 7-30 degrees about a pivot at the top of the head, so the arms only slide a few
units and their roots can leave the body; no visible gain, rejected. Rigid arms on the body bone are the delivery.
Texture: one CLUT row (0) painted with an exact 13-colour palette (no quantiser), face frames repainted for
every tex-anim source, the tournament sprite (row 15) drawn by hand.
"""
import math
from lib import *
import mmd

b = Baby(os.environ.get('MOTI_NAME', 'Motimon'), 2)
T = b.m.tmd
H, R, GROUND = 148.0, 61.0, 69.0            # height, widest radius, ground in bone-2 space (y down)
CBA, TSB = 0x7A00, 0x05                     # CLUT row 0, texture page 5
ARMS_ON = os.environ.get('MOTI_ARMS', 'body')   # 'body': rigid on object 0; 'ears': objects 1/3 (bones 3/5), tried and rejected


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
# radius fraction by height fraction h (0 = skirt hem, 1 = apex): a soft bell, widest at a third of the height
# measured on the reference (half-width / max by height): widest at a quarter, a slight waist where the arms
# come out, a round dome that narrows from 0.8 up
PROF = [(0.0, 0.94), (0.07, 0.98), (0.14, 1.0), (0.26, 1.0), (0.35, 0.975), (0.44, 0.945), (0.53, 0.94),
        (0.61, 0.94), (0.68, 0.925), (0.76, 0.88), (0.84, 0.79), (0.90, 0.67), (0.94, 0.55), (0.97, 0.40), (0.985, 0.25), (1.0, 0.0)]
RINGS = [0.14, 0.27, 0.40, 0.50, 0.68, 0.86, 0.91, 0.95, 0.98]   # ring heights; 3..4 = mouth, 4..5 = eyes
SEG = [-180, -150, -120, -92, -66, -41, -15, 15, 41, 66, 92, 120, 150]   # segment k spans SEG[k]..SEG[k+1] (last: 150..180)
NSEG = len(SEG)


def seg_bounds(k):
    return SEG[k], (SEG[k + 1] if k + 1 < NSEG else SEG[0] + 360)
EYE_SEG = (SEG.index(15), SEG.index(-41))               # segments [15,41] and [-41,-15]
MOUTH_SEG = SEG.index(-15)                              # segment [-15,15]
LOBES, LOBE_H, LOBE_R, HEM_N = 6, 0.085, 0.06, 3   # HEM_N hem vertices per segment


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
    """Body skin strip: u 8..136 around (front at u=72), v 60 (apex) .. 124 (hem)."""
    return (72 + phi * 128 / 360.0, 124 - h * 64)


def build_body(m):
    rings = []
    for h in RINGS:
        rings.append([m.vert(body_point(p, h), body_normal(p, h)) for p in SEG])
    apex = m.vert((0, GROUND - H, 0), (0, -1, 0))
    # skirt hem: two vertices per segment (boundary + middle), six lobes (lowest at the front)
    hem_phi = []
    for k in range(NSEG):
        a, b_ = seg_bounds(k)
        hem_phi += [a + (b_ - a) * j / HEM_N for j in range(HEM_N)]
    hem, cap = [], []
    for p in hem_phi:
        w = (1 - math.cos(math.radians(LOBES * p))) / 2          # 0 at a lobe tip, 1 at a cusp
        h = LOBE_H * w
        r = R * (PROF[0][1] + LOBE_R * (1 - w) - 0.02 * w)
        a = math.radians(p)
        pt = (r * math.sin(a), GROUND - h * H, -r * math.cos(a))
        hem.append((m.vert(pt, (math.sin(a) * 0.8, 0.6 - 0.4 * w, -math.cos(a) * 0.8)), p, h))
        cap.append((m.vert((pt[0], pt[1] - 2, pt[2]), (0, 1, 0)), p))
    centre = m.vert((0, GROUND - 0.05 * H, 0), (0, 1, 0))
    # shell quads
    for i in range(len(RINGS) - 1):
        for k in range(NSEG):
            k2 = (k + 1) % NSEG
            p0, p1 = seg_bounds(k)
            lo, hi = RINGS[i], RINGS[i + 1]
            A, B, C, D = rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]
            if i == 3 and k == MOUTH_SEG:            # mouth frame, u 0..40 left->right, v 32 top .. 56 bottom
                m.quad(A, B, C, D, (0, 56), (40, 56), (40, 32), (0, 32))
            elif i == 4 and k == EYE_SEG[0]:         # right eye (phi 14..38): inner edge u 8, outer u 48
                m.quad(A, B, C, D, (8, 32), (48, 32), (48, 0), (8, 0))
            elif i == 4 and k == EYE_SEG[1]:         # left eye (phi -38..-14): inner edge (-14) u 8
                m.quad(A, B, C, D, (48, 32), (8, 32), (8, 0), (48, 0))
            else:
                m.quad(A, B, C, D, strip_uv(p0, lo), strip_uv(p1, lo), strip_uv(p1, hi), strip_uv(p0, hi))
    # apex fan
    top = rings[-1]
    for k in range(NSEG):
        k2 = (k + 1) % NSEG
        p0, p1 = seg_bounds(k)
        m.tri(apex, top[k], top[k2], strip_uv((p0 + p1) / 2, 1.0), strip_uv(p0, RINGS[-1]), strip_uv(p1, RINGS[-1]))
    # hem to the first ring: HEM_N hem vertices under each segment, fanned from the ring's two vertices
    r1 = rings[0]
    for k in range(NSEG):
        k2 = (k + 1) % NSEG
        hv = [hem[(HEM_N * k + j) % len(hem)] for j in range(HEM_N + 1)]
        hv = [(i, q + 360 if j and q < hv[0][1] else q, h) for j, (i, q, h) in enumerate(hv)]
        p0, p1 = seg_bounds(k)
        half = HEM_N // 2 + 1
        for j in range(half):
            (a, qa, ha), (b_, qb, hb) = hv[j], hv[j + 1]
            m.tri(r1[k], a, b_, strip_uv(p0, RINGS[0]), strip_uv(qa, ha), strip_uv(qb, hb))
        (a, qa, ha) = hv[half]
        m.tri(r1[k], a, r1[k2], strip_uv(p0, RINGS[0]), strip_uv(qa, ha), strip_uv(p1, RINGS[0]))
        for j in range(half, HEM_N):
            (a, qa, ha), (b_, qb, hb) = hv[j], hv[j + 1]
            m.tri(r1[k2], a, b_, strip_uv(p1, RINGS[0]), strip_uv(qa, ha), strip_uv(qb, hb))
    # floor cap (dark underside)
    for k in range(len(cap)):
        (c0, _), (c1, _) = cap[k], cap[(k + 1) % len(cap)]
        m.tri(centre, c0, c1, (155, 111), (142, 100), (168, 100))
    return m


# ---------------------------------------------------------------- arms
def build_arm(m, root, dirn, length, r0, r1, up, claw_angles, bend=(0, 0, 0)):
    """A rounded stub: three 6-sided rings along dirn (root inside the body) and a cap, three claw fins at the tip.
    Texture: arm patch u 140..200 (root->tip) x v 60..92 (around; v 60 = top), claws at u 204..216, v 60..72."""
    d = np.asarray(dirn, float); d /= np.linalg.norm(d)
    u = np.cross(d, up); u /= np.linalg.norm(u)
    w = np.cross(d, u)                                   # w points "down-ish" if up is up
    root = np.asarray(root, float); bend = np.asarray(bend, float)
    stations = [(0.0, r0, 0.0), (0.45, r0 * 0.97, 0.1), (0.8, r1, 0.3), (1.0, r1 * 0.78, 0.7)]
    rings = []
    for t, r, tilt in stations:
        c = root + d * (t * length) + bend * t * t
        ring = []
        for k in range(6):
            al = math.radians(60 * k - 90)                # k=0 at the top (-w)
            off = math.cos(al) * u + math.sin(al) * w
            ring.append(m.vert(c + r * off, off * (1 - tilt) + d * tilt))
        rings.append(ring)
    capv = m.vert(root + d * (length + r1 * 0.5) + bend, d)
    for i in range(3):
        t0, t1 = stations[i][0], stations[i + 1][0]
        for k in range(6):
            k2 = (k + 1) % 6
            v0, v1 = 60 + 32 * k / 6.0, 60 + 32 * (k + 1) / 6.0
            m.quad(rings[i][k], rings[i + 1][k], rings[i + 1][k2], rings[i][k2],
                   (140 + 60 * t0, v0), (140 + 60 * t1, v0), (140 + 60 * t1, v1), (140 + 60 * t0, v1))
    for k in range(6):
        k2 = (k + 1) % 6
        v0, v1 = 60 + 32 * k / 6.0, 60 + 32 * (k + 1) / 6.0
        m.tri(capv, rings[3][k], rings[3][k2], (199, (v0 + v1) / 2), (197, v0), (197, v1))
    # claws: small dark fins splayed from the tip
    tip = root + d * length + bend
    for al_deg in claw_angles:
        al = math.radians(al_deg - 90)
        off = math.cos(al) * u + math.sin(al) * w
        base = tip + off * (r1 * 0.75)
        side = np.cross(d, off); side /= np.linalg.norm(side)
        p0 = m.vert(base + side * 2.8 - d * 1.5, off)
        p1 = m.vert(base - side * 2.8 - d * 1.5, off)
        p2 = m.vert(base + off * 2.5 + d * 6.0, off + d * 0.5)
        m.tri(p0, p1, p2, (206, 62), (214, 62), (210, 70), both=True)
    return m


ARM_R0, ARM_R1 = 14.5, 12.0
# raised arm (x < 0, the viewer's left in the front view): up and outward, claws on top
ARM_L = dict(root=(-40, GROUND - 0.55 * H, -12), dirn=(-0.72, -0.68, -0.15), length=55, r0=ARM_R0, r1=ARM_R1,
             up=(0.3, -1, 0), claw_angles=(-55, 0, 55), bend=(5, -3, -3))
# stretched arm (x > 0): sideways, a little down and forward, claws forward/down
ARM_R = dict(root=(38, GROUND - 0.50 * H, -10), dirn=(0.93, 0.14, -0.34), length=58, r0=ARM_R0, r1=ARM_R1,
             up=(0, -1, 0), claw_angles=(-55, 0, 55), bend=(0, 5, -4))

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
    check_winding(body, lambda c: c - np.array([0, GROUND - H / 2, 0])),
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
# ten-step skin ramp (white bloom .. deep pink under the hem); the reference's side pink is (250,209,215)
PINK = [(248, 248, 248), (248, 240, 240), (248, 232, 236), (248, 224, 228), (248, 216, 224), (248, 208, 216),
        (240, 192, 204), (232, 176, 192), (224, 160, 184), (208, 136, 168)]
SKIN = PINK[5]
K = (16, 16, 24); G1 = (88, 88, 96); G2 = (168, 168, 176)
R1 = (232, 40, 56); R2 = (152, 24, 40)
t = b.tex
t[..., :3] = SKIN; t[..., 3] = 255


def light(phi, h):
    """Soft shading of the skin: a white bloom on the lower front, darker hem and back."""
    phi = (phi + 180) % 360 - 180
    L = 0.50 + 0.48 * np.exp(-((phi / 70.0) ** 2 + ((h - 0.40) / 0.36) ** 2))
    L -= 0.10 * np.clip((0.12 - h) / 0.12, 0, 1)
    L -= 0.07 * np.clip((np.abs(phi) - 100) / 80.0, 0, 1)
    L += 0.05 * np.clip((h - 0.8) / 0.2, 0, 1)
    return L


def ramp_fill(sub, L):
    L = np.broadcast_to(np.asarray(L, float), sub.shape[:2])
    idx = np.clip(np.round((1 - L) * (len(PINK) - 1)), 0, len(PINK) - 1).astype(int)
    pal = np.array(PINK, np.uint8)
    sub[..., :3] = pal[idx]


# body strip u 8..136, v 60..124
vv, uu = np.mgrid[60:124, 8:136]
ramp_fill(t[60:124, 8:136], light((uu + 0.5 - 72) * 360 / 128.0, (124 - (vv + 0.5)) / 64.0))
# arm patch u 140..200 x v 60..92: light on top, shade below; a touch darker at the root
vv, uu = np.mgrid[60:92, 140:200]
ramp_fill(t[60:92, 140:200], 0.62 + 0.25 * np.cos((vv + 0.5 - 60) / 32.0 * 2 * np.pi) - 0.08 * (1 - (uu - 140) / 60.0))
t[60:72, 204:216, :3] = G1                      # claws
t[96:126, 140:170, :3] = PINK[9]                # floor cap


# ---- face frames. Eye frame 40x32: dst (8,0); sources (56,0) angry, (96,0) half, (136,0) closed, (176,0) wide,
# (216,0) happy/asleep, (216,32) open. Mouth 40x24: dst (0,32); sources (56,32) open, (96,32) wide, (136,32) rest.
def eye_bg(sub, outer_right=True):
    h_, w_ = sub.shape[:2]
    vv, uu = np.mgrid[0:h_, 0:w_]
    phi = 15 + (uu + 0.5) * 26.0 / w_
    hh = 0.86 - (vv + 0.5) * 0.18 / h_
    ramp_fill(sub, light(phi, hh))


EC, ER = (20, 16), (16, 14)      # eye centre and radii in the frame


def eye_open(sub, lid=0, wide=False, angry=False):
    eye_bg(sub); bg = sub.copy()
    cv2.ellipse(sub, EC, ER, 0, 0, 360, (*K, 255), -1)
    if angry:   # a slanted lid from the inner top (the inner side is u=0)
        msk = np.zeros(sub.shape[:2], np.uint8)
        cv2.fillPoly(msk, [np.array([(0, 0), (40, 0), (40, 5), (0, 14)])], 1)
        sub[msk > 0] = bg[msk > 0]
        cv2.line(sub, (2, 13), (38, 4), (*K, 255), 2)
    if lid:
        sub[:lid] = bg[:lid]
        cv2.line(sub, (4, lid), (36, lid), (*K, 255), 2)
    hy = max(8, lid + 4)
    cv2.circle(sub, (26, hy), 5 if wide else 4, (*W_, 255), -1)       # big highlight top-outer
    sub[23:25, 13:15, :3] = G2                                        # small one bottom-inner


def eye_arc(sub, up):
    eye_bg(sub)
    if up:      # happy / asleep: an arch
        cv2.ellipse(sub, (20, 20), (11, 9), 0, 200, 340, (*K, 255), 3)
    else:       # closed: a gentle downward curve
        cv2.ellipse(sub, (20, 10), (11, 7), 0, 20, 160, (*K, 255), 3)


eye_open(t[0:32, 8:48]); eye_open(t[32:64, 216:256])
eye_open(t[0:32, 96:136], lid=11)
eye_open(t[0:32, 176:216], wide=True)
eye_open(t[0:32, 56:96], angry=True)
eye_arc(t[0:32, 136:176], up=False)
eye_arc(t[0:32, 216:256], up=True)
t[0:32, 48:56, :3] = PINK[3]
t[32:64, 176:216, :3] = SKIN


def mouth_bg(sub):
    h_, w_ = sub.shape[:2]
    vv, uu = np.mgrid[0:h_, 0:w_]
    phi = -15 + (uu + 0.5) * 30.0 / w_
    hh = 0.68 - (vv + 0.5) * 0.18 / h_
    ramp_fill(sub, light(phi, hh))


def mouth(sub, depth, hw=8.5, lw=17):
    """The reference's cat mouth: a thin 'w' lip whose outer ends curl up and whose middle peak rises between two
    valleys; from the valleys hangs the opening, an inverted egg of plain bright red with a black outline."""
    mouth_bg(sub)
    cx, y_end, y_val, y_peak = 20, 2, 7, 3
    # opening polygon: top edge follows the lip between the valleys, sides narrow to a round bottom
    top = []
    for i in range(0, 21):
        x = -hw + 2 * hw * i / 20.0
        u = abs(x) / hw
        top.append((cx + x, y_val - (y_val - y_peak) * (1 - u) ** 1.5))
    side = []
    for i in range(1, 21):
        sgn = i / 20.0
        w = hw * math.sqrt(max(0.0, 1 - sgn ** 1.9)) * (1 - 0.22 * sgn)
        side.append((w, y_val + depth * sgn))
    right = [(cx + w, y) for w, y in side]
    left = [(cx - w, y) for w, y in reversed(side)]
    poly = np.array([(int(round(x)), int(round(y))) for x, y in top + right + left], np.int32)
    cv2.fillPoly(sub, [poly], (*R1, 255))
    cv2.polylines(sub, [poly], True, (*K, 255), 1)
    # lip: polyline through end, valley, peak, valley, end (smooth curve)
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


mouth(t[32:56, 0:40], 14, hw=9.5)         # live
mouth(t[32:56, 136:176], 14, hw=9.5)      # rest: the reference's open smile
mouth(t[32:56, 56:96], 16, hw=11)         # open
mouth(t[32:56, 96:136], 16, hw=12, lw=18) # wide (eating, snoring)
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
