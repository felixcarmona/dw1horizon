"""Tanemon -> Yokomon, round 2: the mesh is rebuilt from scratch on Tanemon's skeleton and animations, the page is
hand-painted with palettes chosen by hand (no quantiser, indices written straight into the TIM).

Bone -> object: 2 = the pink onion bulb (plus one static root nub at the front); 3 = neck + the six yellow stamens +
the red curl; 4 / 5 = three petals each (right / left), hinged where Tanemon's leaves were (those bones flap about z, so
every petal extends along +-x and flaps like the leaves did); 6-9 = four root nubs (Tanemon's feet).

Traps found: Baby.save() runs tex_import's quantiser (bypassed here); the game culls back faces but animstudio's sheet
does not, so every primitive is wound from a wanted outward direction and checked with mmd.render(cull=True); bones 4/5
only rotate about z, a petal pointing along z would swing sideways; the eye/mouth frames are moved as indices, so all
frames of one rect must use one CLUT row; palette values are 5 bit (use multiples of 8).
"""
import math, sys
from lib import *

b = Baby('Yokomon', 44)
tmd, tim = b.m.tmd, b.tim
TSB = 5


def cba(row): return (488 + row) << 6


def sub(a, c): return (a[0] - c[0], a[1] - c[1], a[2] - c[2])
def cross(a, c): return (a[1] * c[2] - a[2] * c[1], a[2] * c[0] - a[0] * c[2], a[0] * c[1] - a[1] * c[0])
def dot(a, c): return a[0] * c[0] + a[1] * c[1] + a[2] * c[2]
def unit(a):
    l = math.sqrt(dot(a, a)) or 1.0
    return (a[0] / l, a[1] / l, a[2] / l)


class Part:
    """One TMD object: own vertices and normals; primitives wound so that their outward side faces `want`.
    PS1 front face = clockwise on screen; with y down that means outward = (v2-v0) x (v1-v0)."""
    def __init__(self):
        self.v, self.n, self.prims = [], [], []

    def vert(self, x, y, z):
        self.v.append((float(x), float(y), float(z))); return len(self.v) - 1

    def norm(self, x, y, z):
        self.n.append(unit((x, y, z))); return len(self.n) - 1

    def _outward(self, vs):
        p0, p1, p2 = (self.v[i] for i in vs[:3])
        return cross(sub(p2, p0), sub(p1, p0))

    def tri(self, vs, ns, uvs, row, want=None):
        vs, ns, uvs = list(vs), list(ns), list(uvs)
        if want is None: want = self.n[ns[0]]
        if dot(self._outward(vs), want) < 0:
            vs[1], vs[2] = vs[2], vs[1]; ns[1], ns[2] = ns[2], ns[1]; uvs[1], uvs[2] = uvs[2], uvs[1]
        self.prims.append(dict(mode=0x34, flag=0, olen=9, uv=uvs, cba=cba(row), tsb=TSB, uvpad=[0], colors=[],
                               norms=ns, verts=vs, pad=[]))

    def quad(self, vs, ns, uvs, row, want=None):
        """vs = (top-left, top-right, bottom-left, bottom-right): triangles (0,1,2) and (1,3,2)."""
        vs, ns, uvs = list(vs), list(ns), list(uvs)
        if want is None: want = self.n[ns[0]]
        if dot(self._outward(vs), want) < 0:
            vs = [vs[1], vs[0], vs[3], vs[2]]; ns = [ns[1], ns[0], ns[3], ns[2]]; uvs = [uvs[1], uvs[0], uvs[3], uvs[2]]
        self.prims.append(dict(mode=0x3C, flag=0, olen=12, uv=uvs, cba=cba(row), tsb=TSB, uvpad=[0, 0], colors=[],
                               norms=ns, verts=vs, pad=[]))

    def size(self):
        return 8 * len(self.v) + 8 * len(self.n) + sum(4 + 4 * (8 if p['mode'] == 0x3C else 6) for p in self.prims)


def lathe(p, rings, nseg, th0, row, uvfn, skip=lambda i, k: False, bottom=None, top=None, capuv=None):
    """Surface of revolution: rings = [(y, r)] bottom to top; th0 = angle of vertex k=0 (deg, from +x towards -z).
    Returns (ring vertex ids [i][k], ring normal ids). bottom/top = y of a centre vertex to cap with."""
    ext = [(bottom if bottom is not None else rings[0][0], 0)] + list(rings) + [(top if top is not None else rings[-1][0], 0)]
    ids, nids, prof = [], [], []
    for i, (y, r) in enumerate(rings):
        (y0, r0), (y1, r1) = ext[i], ext[i + 2]
        nr, ny = -(y1 - y0), (r1 - r0)
        if nr < 0: nr, ny = -nr, -ny
        prof.append((nr, ny))
        row_v, row_n = [], []
        for k in range(nseg):
            th = math.radians(th0 + 360.0 * k / nseg)
            row_v.append(p.vert(r * math.cos(th), y, -r * math.sin(th)))
            row_n.append(p.norm(nr * math.cos(th), ny, -nr * math.sin(th)))
        ids.append(row_v); nids.append(row_n)
    for i in range(len(rings) - 1):
        for k in range(nseg):
            if skip(i, k): continue
            k1 = (k + 1) % nseg
            uv = uvfn(i, k)
            p.quad((ids[i + 1][k1], ids[i + 1][k], ids[i][k1], ids[i][k]),
                   (nids[i + 1][k1], nids[i + 1][k], nids[i][k1], nids[i][k]), uv, row)
    if bottom is not None:
        c = p.vert(0, bottom, 0); nc = p.norm(0, 1, 0)
        for k in range(nseg):
            k1 = (k + 1) % nseg
            p.tri((ids[0][k1], ids[0][k], c), (nids[0][k1], nids[0][k], nc), [capuv[0]] * 3, row, want=(0, 1, 0))
    if top is not None:
        c = p.vert(0, top, 0); nc = p.norm(0, -1, 0)
        for k in range(nseg):
            k1 = (k + 1) % nseg
            p.tri((c, ids[-1][k1], ids[-1][k]), (nc, nids[-1][k1], nids[-1][k]), [capuv[1]] * 3, row, want=(0, -1, 0))
    return ids, nids, prof


def tube(p, pts, radii, nside, row, uv_u, uv_v, tip=True, want_sign=1.0):
    """A polygonal tube along a polyline (pts), one ring per point (radius radii[i]); optional cone tip at the last
    point. UVs: u = uv_u (u0, u1) across, v = uv_v(t) along."""
    n = len(pts)
    rings, rnorms = [], []
    for i in range(n - (1 if tip else 0)):
        prev = pts[max(i - 1, 0)]; nxt = pts[min(i + 1, n - 1)]
        T = unit(sub(nxt, prev))
        ref = (0, 0, 1) if abs(T[2]) < 0.9 else (1, 0, 0)
        A = unit(cross(T, ref)); B = cross(T, A)
        rv, rn = [], []
        for k in range(nside):
            a = 2 * math.pi * k / nside + math.pi / 2
            d = (A[0] * math.cos(a) + B[0] * math.sin(a), A[1] * math.cos(a) + B[1] * math.sin(a), A[2] * math.cos(a) + B[2] * math.sin(a))
            rv.append(p.vert(pts[i][0] + radii[i] * d[0], pts[i][1] + radii[i] * d[1], pts[i][2] + radii[i] * d[2]))
            rn.append(p.norm(*d))
        rings.append(rv); rnorms.append(rn)
    nr = len(rings)
    for i in range(nr - 1):
        for k in range(nside):
            k1 = (k + 1) % nside
            want = p.n[rnorms[i][k]]
            p.quad((rings[i + 1][k], rings[i + 1][k1], rings[i][k], rings[i][k1]),
                   (rnorms[i + 1][k], rnorms[i + 1][k1], rnorms[i][k], rnorms[i][k1]),
                   [(uv_u[0], uv_v(i + 1)), (uv_u[1], uv_v(i + 1)), (uv_u[0], uv_v(i)), (uv_u[1], uv_v(i))], row, want=want)
    if tip:
        t = p.vert(*pts[-1]); tn = p.norm(*unit(sub(pts[-1], pts[-2])))
        for k in range(nside):
            k1 = (k + 1) % nside
            p.tri((t, rings[-1][k], rings[-1][k1]), (tn, rnorms[-1][k], rnorms[-1][k1]),
                  [(uv_u[0] + 2, uv_v(nr)), (uv_u[0], uv_v(nr - 1)), (uv_u[1], uv_v(nr - 1))], row, want=p.n[rnorms[-1][k]])
    return rings


# ------------------------------------------------------------------ texture layout (u, v) and CLUT rows
R_FACE, R_SKIN, R_PETAL, R_STAMEN, R_SPRITE = 0, 1, 2, 3, 15
SKIN = (0, 48, 64, 96)        # body strip: u 0..63 around (front at 32), v 48 top .. 95 bottom
NECK = (64, 48, 80, 80)
PETAL = (96, 48, 144, 112)    # base at the top (v 48), tip at the bottom
STAM = (160, 48, 168, 96)
CURL = (168, 48, 176, 96)
FOOT = (176, 48, 192, 64)
EYE_SRC = {'open': 168, 'angry': 40, 'half': 72, 'happy': 136, 'shut': 104}
MOUTH_SRC = {'closed': 128, 'slight': 104, 'open': 80, 'wide': 56}

# ------------------------------------------------------------------ geometry
# bulb (bone 2, world-ish coordinates: ground at y = 0, up = -y, front = -z)
NSEG = 10
RINGS = [(-18, 28), (-36, 58), (-58, 79), (-84, 90), (-114, 85), (-138, 68), (-155, 46), (-165, 30)]
Y_TOP, Y_BOT = -165, -12


def skin_v(y): return int(round(48 + 47 * (y - Y_TOP) / (Y_BOT - Y_TOP)))


def skin_u(k):
    th = 72 + 36 * k
    d = ((th - 90) + 180) % 360 - 180
    return 32 + d / 180.0 * 31


body = Part()


def body_uv(i, k):
    k1 = k + 1
    u0, u1 = skin_u(k1), skin_u(k)
    if k == 5: u0 = 63                      # the seam segment at the back
    v1, v0 = skin_v(RINGS[i][0]), skin_v(RINGS[i + 1][0])
    return [(int(u0), v0), (int(u1), v0), (int(u0), v1), (int(u1), v1)]


EYE_BANDS = (2, 3)         # rings R2-R3 and R3-R4 carry the eye quads, segments 1 (left) and 9 (right)
ids, nids, prof = lathe(body, RINGS, NSEG, 72, R_SKIN, body_uv,
                        skip=lambda i, k: (i in EYE_BANDS and k in (1, 9)) or (i == 1 and k == 0),
                        bottom=Y_BOT, top=-167, capuv=[(32, 95), (32, 48)])
# eyes: the rect (0,0)-(32,24), u = 0 at the inner edge (towards the nose), v down the face
for k in (1, 9):
    inner, outer = (1, 2) if k == 1 else (0, 9)      # vertex columns: k=1 spans 108..144 deg, k=9 spans 36..72
    for i in EYE_BANDS:
        v0, v1 = (0, 12) if i == 3 else (12, 23)
        tl, tr, bl, br = ids[i + 1][inner], ids[i + 1][outer], ids[i][inner], ids[i][outer]
        ntl, ntr, nbl, nbr = nids[i + 1][inner], nids[i + 1][outer], nids[i][inner], nids[i][outer]
        body.quad((tl, tr, bl, br), (ntl, ntr, nbl, nbr), [(0, v0), (31, v0), (0, v1), (31, v1)], R_FACE)
# mouth: band R1-R2 of the front segment split at the centre line; u = 0 at the centre, mirrored halves
nr, ny = prof[1]; nr2, ny2 = prof[2]
mu = body.vert(0, RINGS[2][0], -(RINGS[2][1]) * math.cos(math.radians(18)))
ml = body.vert(0, RINGS[1][0], -(RINGS[1][1]) * math.cos(math.radians(18)))
nmu, nml = body.norm(0, ny2, -nr2), body.norm(0, ny, -nr)
body.quad((ids[2][1], mu, ids[1][1], ml), (nids[2][1], nmu, nids[1][1], nml), [(23, 24), (0, 24), (23, 47), (0, 47)], R_FACE)
body.quad((mu, ids[2][0], ml, ids[1][0]), (nmu, nids[2][0], nml, nids[1][0]), [(0, 24), (23, 24), (0, 47), (23, 47)], R_FACE)


def nub(p, cx, cz, y_bot, y_top, r_bot, r_top, nseg=5):
    """A root nub: a short lathe at (cx, cz) from y_bot (ground) up to y_top (inside the bulb), capped underneath."""
    bot, top, nb, nt = [], [], [], []
    for k in range(nseg):
        a = 2 * math.pi * k / nseg + math.pi / 2
        c, s = math.cos(a), -math.sin(a)
        bot.append(p.vert(cx + r_bot * c, y_bot, cz + r_bot * s)); nb.append(p.norm(c, 0.6, s))
        top.append(p.vert(cx + r_top * c, y_top, cz + r_top * s)); nt.append(p.norm(c, -0.2, s))
    cv = p.vert(cx, y_bot + 2, cz); cn = p.norm(0, 1, 0)
    for k in range(nseg):
        k1 = (k + 1) % nseg
        u0, u1 = FOOT[0] + 15 * k // nseg, FOOT[0] + 15 * (k + 1) // nseg
        p.quad((top[k1], top[k], bot[k1], bot[k]), (nt[k1], nt[k], nb[k1], nb[k]),
               [(u1, FOOT[1]), (u0, FOOT[1]), (u1, FOOT[3] - 1), (u0, FOOT[3] - 1)], R_SKIN)
        p.tri((bot[k1], bot[k], cv), (nb[k1], nb[k], cn), [(FOOT[0] + 8, FOOT[3] - 1)] * 3, R_SKIN, want=(0, 1, 0))


nub(body, 0, -58, -2, -44, 13, 16)       # the fifth root, static at the front centre

# neck + stamens + curl (bone 3: origin at the bulb top, world y -165; the petal hinges are 62 above)
neck = Part()
NRINGS = [(18, 40), (-6, 29), (-34, 19), (-62, 14)]


def neck_uv(i, k):
    u0, u1 = NECK[0] + 15 * ((k + 1) % 6) // 6, NECK[0] + 15 * k // 6
    if k == 5: u0 = NECK[2] - 1
    vfn = lambda y: int(round(NECK[1] + (NECK[3] - 1 - NECK[1]) * (y + 62) / 80.0))
    return [(u0, vfn(NRINGS[i + 1][0])), (u1, vfn(NRINGS[i + 1][0])), (u0, vfn(NRINGS[i][0])), (u1, vfn(NRINGS[i][0]))]


lathe(neck, NRINGS, 6, 90, R_SKIN, neck_uv, top=-64, capuv=[None, (NECK[0] + 8, NECK[1])])

TOP = -62.0


def stamen(p, psi_deg, h=86, out=62, r=7.5):
    """One yellow filament: rises from the receptacle, bows outward and the tip hooks out and down."""
    ps = math.radians(psi_deg)
    d = (math.cos(ps), 0, -math.sin(ps))
    pts = [(d[0] * 6, TOP + 2, d[2] * 6),
           (d[0] * (out * 0.5), TOP - h * 0.9, d[2] * (out * 0.5)),
           (d[0] * (out * 0.9), TOP - h, d[2] * (out * 0.9)),
           (d[0] * out, TOP - h * 0.78, d[2] * out)]
    tube(p, pts, [r, r * 0.95, r * 0.8, 0], 3, R_STAMEN, (STAM[0], STAM[2] - 1), lambda i: STAM[1] + min(47, 16 * i), tip=True)


for psi, h, out in ((0, 84, 66), (180, 84, 66), (52, 92, 52), (128, 92, 52), (232, 100, 44), (308, 100, 44)):
    stamen(neck, psi, h, out)


def curl(p):
    """The red-orange fiddlehead: a stem up from the centre, then 1.25 turns inwards in the x/y plane facing the
    front: up the right side, over the top, down the left and into the middle (as the art draws it)."""
    C = (-6.0, TOP - 100.0, 0.0)
    r0, r1, turns = 42.0, 10.0, 1.2
    pts = [(2, TOP + 2, 0), (4, TOP - 34, 0)]
    nsp = 9
    for i in range(nsp + 1):
        s = i / nsp
        a = math.radians(90 - 360 * turns * s)
        r = r0 + (r1 - r0) * s
        pts.append((C[0] + r * math.cos(a), C[1] + r * math.sin(a), 0.0))
    radii = [12, 12] + [12 - 5.0 * (i / nsp) for i in range(nsp + 1)]
    radii[-1] = 0
    tube(p, pts, radii, 4, R_STAMEN, (CURL[0], CURL[2] - 1), lambda i: CURL[1] + min(47, 4 * i), tip=True)


curl(neck)


def petal(p, hinge_x, phi_deg, L, rise, fall, half_w, cup, tilt):
    """A drooping lily petal in bone 4/5 space. The base is the stalk top (hinge_x back to the centre); phi from +x
    towards -z; rise = how much it lifts first, fall = how far the tip droops (positive = down), tilt = the front edge
    lower than the back edge (so side petals show their top to the viewer). Both sides are emitted."""
    ph = math.radians(phi_deg)
    d = (math.cos(ph), 0.0, -math.sin(ph))
    s = (math.sin(ph), 0.0, math.cos(ph))
    base = (-hinge_x, 0.0, 0.0)

    def centre(t):
        return (base[0] + d[0] * L * t, base[1] - rise * math.sin(math.pi * t) + fall * t * t, base[2] + d[2] * L * t)

    def width(t): return half_w * math.sin(math.pi * t ** 0.7) ** 0.8     # broad early, long pointed tip

    def tangent(t):
        return (d[0] * L, -rise * math.pi * math.cos(math.pi * t) + 2 * fall * t, d[2] * L)

    T_RINGS = (0.30, 0.68)
    c0 = centre(0.02)
    vb = p.vert(*c0)
    n0 = unit(cross(tangent(0.02), s)); n0 = n0 if n0[1] < 0 else (-n0[0], -n0[1], -n0[2])
    nb_t, nb_b = p.norm(*n0), p.norm(-n0[0], -n0[1], -n0[2])
    rings = []
    for t in T_RINGS:
        c = centre(t); w = width(t)
        lift = cup * (w / half_w)
        e = []
        for sg in (-1, 1):
            z_edge = c[2] + sg * s[2] * w
            dz = (z_edge - c[2]) / max(w, 1e-6)                 # -1 .. 1, negative = towards the front
            y = c[1] - lift + tilt * (-dz)
            e.append(p.vert(c[0] + sg * s[0] * w, y, z_edge))
        vc = p.vert(c[0], c[1], c[2])
        n = unit(cross(tangent(t), s)); n = n if n[1] < 0 else (-n[0], -n[1], -n[2])
        ring_t = [p.norm(*n) for _ in range(3)]; ring_b = [p.norm(-n[0], -n[1], -n[2]) for _ in range(3)]
        rings.append(((e[0], vc, e[1]), ring_t, ring_b))
    ct = centre(1.0)
    vt = p.vert(*ct)
    n = unit(cross(tangent(1.0), s)); n = n if n[1] < 0 else (-n[0], -n[1], -n[2])
    nt_t, nt_b = p.norm(*n), p.norm(-n[0], -n[1], -n[2])
    u0, uc, u1 = PETAL[0], (PETAL[0] + PETAL[2]) // 2, PETAL[2] - 1
    vv = lambda t: int(round(PETAL[1] + (PETAL[3] - 1 - PETAL[1]) * t))
    (a0, ac, a1), an_t, an_b = rings[0]
    (c0_, cc, c1), cn_t, cn_b = rings[1]
    for sign, nbase, an, cn, ntip in ((1, nb_t, an_t, cn_t, nt_t), (-1, nb_b, an_b, cn_b, nt_b)):
        want = lambda nid: p.n[nid]
        p.tri((vb, a0, ac), (nbase, an[0], an[1]), [(uc, vv(0)), (u0, vv(T_RINGS[0])), (uc, vv(T_RINGS[0]))], R_PETAL, want=want(an[1]))
        p.tri((vb, ac, a1), (nbase, an[1], an[2]), [(uc, vv(0)), (uc, vv(T_RINGS[0])), (u1, vv(T_RINGS[0]))], R_PETAL, want=want(an[1]))
        p.quad((c0_, cc, a0, ac), (cn[0], cn[1], an[0], an[1]),
               [(u0, vv(T_RINGS[1])), (uc, vv(T_RINGS[1])), (u0, vv(T_RINGS[0])), (uc, vv(T_RINGS[0]))], R_PETAL, want=want(an[1]))
        p.quad((cc, c1, ac, a1), (cn[1], cn[2], an[1], an[2]),
               [(uc, vv(T_RINGS[1])), (u1, vv(T_RINGS[1])), (uc, vv(T_RINGS[0])), (u1, vv(T_RINGS[0]))], R_PETAL, want=want(an[1]))
        p.tri((c0_, cc, vt), (cn[0], cn[1], ntip), [(u0, vv(T_RINGS[1])), (uc, vv(T_RINGS[1])), (uc, vv(1))], R_PETAL, want=want(cn[1]))
        p.tri((cc, c1, vt), (cn[1], cn[2], ntip), [(uc, vv(T_RINGS[1])), (u1, vv(T_RINGS[1])), (uc, vv(1))], R_PETAL, want=want(cn[1]))


petR, petL = Part(), Part()
# (phi, length, rise, fall, half width, cup, tilt): side petal long and drooping, front one shorter and lower,
# back one shorter and rising
PETALS = [(0, 150, 18, 58, 42, 8, 12), (48, 128, 12, 76, 38, 7, 5), (-48, 122, 12, -44, 36, 7, 0)]
for phi, L, rise, fall, hw, cup, tilt in PETALS:
    petal(petR, 22, phi, L, rise, fall, hw, cup, tilt)
    petal(petL, -21, 180 - phi, L, rise, fall, hw, cup, tilt)

feet = []
for bx, bz in ((48, -36), (-48, -36), (47, 43), (-47, 43)):
    f = Part()
    nub(f, 0, 0, 22, -26, 13, 16)          # bone at world y -24: ground at local +22
    feet.append(f)

PARTS = [body, neck, petR, petL] + feet


def assemble(parts):
    tmd.verts, tmd.norms = [], []
    for oi, p in enumerate(parts):
        ob = tmd.objects[oi]
        ob.vert_start, ob.nvert = len(tmd.verts), len(p.v)
        ob.norm_start, ob.nnorm = len(tmd.norms), len(p.n)
        tmd.verts += [(int(round(x)), int(round(y)), int(round(z)), 0) for x, y, z in p.v]
        tmd.norms += [(int(round(x * 4096)), int(round(y * 4096)), int(round(z * 4096)), 0) for x, y, z in p.n]
        ob.prims = [mmd.Prim.encode(d) for d in p.prims]


assemble(PARTS)
for i, p in enumerate(PARTS):
    print(f'obj {i}: {len(p.v)} verts {len(p.n)} norms {len(p.prims)} prims {p.size()} B', file=sys.stderr)

# ------------------------------------------------------------------ texture: index page + palettes
page = np.zeros((128, 256), np.uint8)
rowmap = np.full((128, 256), -1, np.int16)
PAL = {}
PAL[R_SKIN] = [(0, 0, 0), (200, 104, 152), (216, 128, 168), (232, 152, 184), (240, 168, 200), (248, 184, 208),
               (248, 200, 216), (248, 208, 224), (248, 216, 232), (248, 224, 240), (248, 232, 240), (248, 240, 248),
               (176, 80, 128), (152, 64, 112), (255, 248, 248), (255, 255, 255)]
SK = {'deep': 1, 'd2': 2, 'd3': 3, 'd4': 4, 'mid': 5, 'm2': 6, 'm3': 7, 'pale': 8, 'p2': 9, 'p3': 10, 'white': 11,
      'stripe': 12, 'stripe2': 13, 'hi': 14}
PAL[R_FACE] = [(0, 0, 0), (248, 184, 208), (248, 200, 216), (248, 208, 224), (248, 216, 232), (248, 224, 240),
               (248, 232, 240), (248, 240, 248), (24, 16, 24), (255, 255, 255), (16, 56, 24), (40, 128, 48),
               (80, 192, 72), (152, 232, 112), (120, 32, 48), (232, 112, 136)]
FC = {'s1': 1, 's2': 2, 's3': 3, 's4': 4, 's5': 5, 's6': 6, 's7': 7, 'ink': 8, 'white': 9, 'g0': 10, 'g1': 11,
      'g2': 12, 'g3': 13, 'red': 14, 'tongue': 15}
PAL[R_PETAL] = [(0, 0, 0), (16, 16, 56), (24, 32, 112), (40, 64, 168), (64, 104, 216), (96, 144, 240), (136, 176, 248),
                (208, 176, 32), (240, 216, 56), (248, 240, 136), (32, 40, 128), (0, 0, 0), (0, 0, 0), (0, 0, 0),
                (0, 0, 0), (0, 0, 0)]
PC = {'line': 1, 'navy': 2, 'dark': 3, 'blue': 4, 'light': 5, 'pale': 6, 'ydark': 7, 'yellow': 8, 'ylight': 9, 'n2': 10}
PAL[R_STAMEN] = [(0, 0, 0), (136, 128, 24), (200, 192, 40), (248, 224, 48), (248, 240, 152), (240, 152, 40),
                 (232, 96, 40), (208, 48, 32), (152, 24, 32), (96, 40, 16), (248, 192, 48), (0, 0, 0), (0, 0, 0),
                 (0, 0, 0), (0, 0, 0), (0, 0, 0)]
SC = {'olive2': 1, 'olive': 2, 'yellow': 3, 'ylight': 4, 'orange': 5, 'ored': 6, 'red': 7, 'dred': 8, 'brown': 9, 'oyellow': 10}
PAL[R_SPRITE] = [None, (248, 208, 224), (216, 128, 168), (24, 16, 24), (80, 192, 72), (56, 88, 200), (24, 32, 104),
                 (240, 216, 56), (208, 48, 32), (255, 255, 255), (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0)]


def region(x0, y0, x1, y1, row, fill=0):
    rowmap[y0:y1, x0:x1] = row
    page[y0:y1, x0:x1] = fill


# -- body skin strip: gradient top (deep) -> bottom (white), back a shade darker, onion stripes near the top
region(*SKIN, R_SKIN)
ramp = [SK['d4'], SK['mid'], SK['m2'], SK['m3'], SK['pale'], SK['p2'], SK['p3'], SK['white'], SK['hi']]
for v in range(SKIN[1], SKIN[3]):
    t = (v - SKIN[1]) / float(SKIN[3] - 1 - SKIN[1])          # 0 top .. 1 bottom
    for u in range(SKIN[0], SKIN[2]):
        back = abs(u - 32) / 32.0                                 # 0 front .. 1 back
        k = (t ** 0.8) * 8.6 - back * 1.6 + (0.6 if u > 32 else 0.0)
        page[v, u] = ramp[int(max(0, min(8, round(k))))]
rng = np.random.RandomState(3)
for u in range(SKIN[0] + 2, SKIN[2], 5):
    ln = 7 + int(rng.randint(0, 6)) - int(3 * abs(u - 32) / 32)
    cv2.line(page, (u, SKIN[1]), (u + (1 if u % 2 else -1), SKIN[1] + ln), SK['stripe'] if abs(u - 32) < 24 else SK['stripe2'], 1)
page[SKIN[1]:SKIN[1] + 2, SKIN[0]:SKIN[2]] = SK['d2']

# -- neck strip: pale pink, darker at the top, dark pink converging stripes
region(*NECK, R_SKIN)
for v in range(NECK[1], NECK[3]):
    t = (v - NECK[1]) / float(NECK[3] - 1 - NECK[1])         # 0 top .. 1 bottom (bulb)
    page[v, NECK[0]:NECK[2]] = [SK['d4'], SK['mid'], SK['m2'], SK['m3'], SK['pale']][int(t * 4.99)]
for u in (65, 69, 73, 77):
    cv2.line(page, (u, NECK[1]), (u + 1, NECK[1] + 20), SK['stripe'], 1)
    cv2.line(page, (u + 2, NECK[1]), (u + 2, NECK[1] + 9), SK['stripe2'], 1)

# -- feet: pink nub, darker underneath
region(*FOOT, R_SKIN)
for v in range(FOOT[1], FOOT[3]):
    t = (v - FOOT[1]) / float(FOOT[3] - 1 - FOOT[1])
    page[v, FOOT[0]:FOOT[2]] = [SK['pale'], SK['m3'], SK['m2'], SK['mid'], SK['d4'], SK['d3']][int(t * 5.99)]

# -- petal: navy edges, blue body, pale centre, yellow midrib and starburst at the base
region(*PETAL, R_PETAL)
pw, ph = PETAL[2] - PETAL[0], PETAL[3] - PETAL[1]
for v in range(PETAL[1], PETAL[3]):
    t = (v - PETAL[1]) / float(ph - 1)
    for u in range(PETAL[0], PETAL[2]):
        e = abs(u - (PETAL[0] + pw / 2.0 - 0.5)) / (pw / 2.0)      # 0 centre .. 1 edge
        k = 2.8 - 2.4 * e * e * e - 1.0 * t + (0.7 if e < 0.3 and t < 0.55 else 0)
        page[v, u] = [PC['navy'], PC['dark'], PC['blue'], PC['light'], PC['pale']][int(max(0, min(4, round(k))))]
cv2.rectangle(page, (PETAL[0], PETAL[1]), (PETAL[2] - 1, PETAL[3] - 1), PC['line'], 1)
cv2.rectangle(page, (PETAL[0] + 1, PETAL[1] + 1), (PETAL[2] - 2, PETAL[3] - 2), PC['navy'], 1)
cv2.line(page, (PETAL[0] + 7, PETAL[1] + 36), (PETAL[0] + 3, PETAL[3] - 3), PC['navy'], 2)
cv2.line(page, (PETAL[2] - 8, PETAL[1] + 36), (PETAL[2] - 4, PETAL[3] - 3), PC['navy'], 2)
cx, cy = PETAL[0] + pw // 2, PETAL[1] + 11
star = []
for i in range(16):
    a = math.pi * 2 * i / 16; r = 11 if i % 2 == 0 else 5
    star.append((int(round(cx + r * math.cos(a))), int(round(cy + r * 0.8 * math.sin(a)))))
cv2.fillPoly(page, [np.array(star, np.int32)], PC['yellow'])
cv2.polylines(page, [np.array(star, np.int32)], True, PC['ydark'], 1)
cv2.line(page, (cx, cy), (cx, PETAL[1] + 40), PC['yellow'], 2)
cv2.line(page, (cx + 1, cy + 4), (cx + 1, PETAL[1] + 38), PC['ylight'], 1)
for dx in (-7, 7):
    cv2.line(page, (cx + dx, cy + 12), (cx + dx * 2, cy + 22), PC['yellow'], 1)

# -- stamen strip: olive base -> yellow tip, dark edges
region(*STAM, R_STAMEN)
for v in range(STAM[1], STAM[3]):
    t = (v - STAM[1]) / float(STAM[3] - 1 - STAM[1])
    page[v, STAM[0]:STAM[2]] = [SC['olive'], SC['yellow'], SC['yellow'], SC['yellow'], SC['ylight']][int(t * 4.99)]
page[STAM[1]:STAM[3], STAM[0]] = SC['olive2']
page[STAM[1] + 6:STAM[3], STAM[0] + 3:STAM[0] + 5] = SC['ylight']
# -- curl strip: orange-yellow base -> red centre, brown edges
region(*CURL, R_STAMEN)
for v in range(CURL[1], CURL[3]):
    t = (v - CURL[1]) / float(CURL[3] - 1 - CURL[1])
    page[v, CURL[0]:CURL[2]] = [SC['orange'], SC['ored'], SC['red'], SC['red'], SC['dred']][int(t * 4.99)]
page[CURL[1]:CURL[3], CURL[0]] = SC['brown']; page[CURL[1]:CURL[3], CURL[2] - 1] = SC['dred']
page[CURL[1]:CURL[3], CURL[0] + 2] = SC['oyellow']


# -- face: eye frames (32x24) and mouth frames (24x24, mirrored half, u = 0 is the centre line)
def face_bg(x0, y0, w, h, shades):
    region(x0, y0, x0 + w, y0 + h, R_FACE)
    for v in range(h):
        page[y0 + v, x0:x0 + w] = shades[min(len(shades) - 1, v * len(shades) // h)]


def draw_eye(x0, kind):
    """Right eye as seen by the viewer, inner side at u = 0; tilted so the top leans towards the nose."""
    face_bg(x0, 0, 32, 24, (FC['s4'], FC['s5'], FC['s6']))
    sub_ = page[0:24, x0:x0 + 32]
    cx, cy = 15, 12
    if kind in ('open', 'angry', 'half'):
        ang = -14
        cv2.ellipse(sub_, (cx, cy), (10, 11), ang, 0, 360, FC['ink'], -1)
        cv2.ellipse(sub_, (cx, cy), (8, 9), ang, 0, 360, FC['g0'], -1)
        cv2.ellipse(sub_, (cx, cy), (6, 7), ang, 0, 360, FC['g1'], -1)
        cv2.ellipse(sub_, (cx - 1, cy - 1), (4, 5), ang, 0, 360, FC['g2'], -1)
        cv2.ellipse(sub_, (cx, cy + 1), (2, 4), ang, 0, 360, FC['ink'], -1)       # pupil
        cv2.ellipse(sub_, (cx - 4, cy - 4), (3, 3), 0, 0, 360, FC['white'], -1)  # big glint, upper inner
        cv2.ellipse(sub_, (cx + 4, cy + 6), (2, 1), 0, 0, 360, FC['white'], -1)  # small glint, lower outer
        sub_[cy + 8, cx + 2] = FC['g3']
        # lashes: short strokes from the rim, upper-inner and lower-outer as in the art
        for (ax, ay, bx, by) in ((cx - 9, cy - 8, cx - 12, cy - 11), (cx - 6, cy - 11, cx - 7, cy - 14), (cx + 9, cy + 8, cx + 12, cy + 11), (cx + 5, cy + 11, cx + 6, cy + 14)):
            cv2.line(sub_, (ax, ay), (bx, by), FC['ink'], 1)
        if kind == 'angry':      # the upper lid slants down towards the nose
            pts = np.array([(cx - 12, cy - 13), (cx + 12, cy - 13), (cx + 12, cy - 9), (cx - 12, cy + 1)], np.int32)
            cv2.fillPoly(sub_, [pts], FC['s4'])
            cv2.line(sub_, (cx - 11, cy + 1), (cx + 11, cy - 8), FC['ink'], 2)
        if kind == 'half':       # the upper lid covers nearly half the eye
            sub_[0:cy - 1, :] = FC['s4']
            cv2.line(sub_, (cx - 11, cy - 1), (cx + 11, cy - 2), FC['ink'], 2)
    elif kind == 'happy':        # closed, curving up
        cv2.ellipse(sub_, (cx, cy + 4), (9, 8), 0, 200, 340, FC['ink'], 2)
    elif kind == 'shut':         # closed, curving down (asleep, hurt)
        cv2.ellipse(sub_, (cx, cy - 4), (9, 7), 0, 20, 160, FC['ink'], 2)


def draw_mouth(x0, kind):
    face_bg(x0, 24, 24, 24, (FC['s7'],))
    sub_ = page[24:48, x0:x0 + 24]
    smile = [(0, 15), (4, 13), (9, 11), (14, 10), (18, 9), (21, 7)]
    if kind == 'closed':
        cv2.polylines(sub_, [np.array(smile, np.int32)], False, FC['ink'], 2)
        cv2.line(sub_, (0, 15), (1, 12), FC['ink'], 2)       # the notch at the centre line
        return
    open_h = {'slight': 4, 'open': 8, 'wide': 12}[kind]
    upper = [(0, 15 - open_h // 3), (6, 13 - open_h // 3), (12, 11 - open_h // 3), (18, 9 - open_h // 3)]
    lower = [(0, 15 + open_h), (6, 14 + open_h * 3 // 4), (12, 12 + open_h // 2), (18, 9 - open_h // 3)]
    poly = np.array(upper + lower[::-1], np.int32)
    cv2.fillPoly(sub_, [poly], FC['red'])
    if kind != 'slight':
        cv2.ellipse(sub_, (3, 15 + open_h - 1), (6, open_h // 2), 0, 180, 360, FC['tongue'], -1)
    cv2.polylines(sub_, [poly], True, FC['ink'], 2 if kind != 'slight' else 1)
    cv2.line(sub_, (0, upper[0][1]), (1, upper[0][1] - 3), FC['ink'], 2)       # the notch stays on the open mouths


draw_eye(0, 'open')
for kind, x in EYE_SRC.items(): draw_eye(x, kind)
draw_mouth(0, 'closed')
for kind, x in MOUTH_SRC.items(): draw_mouth(x, kind)

# -- row 15: the tournament's flat sprite, four 15x15 frames (two with the eyes shut)
for fi, (sx, sy) in enumerate(((224, 96), (240, 96), (224, 112), (240, 112))):
    region(sx, sy, sx + 15, sy + 15, R_SPRITE, 0)
    s = page[sy:sy + 15, sx:sx + 15]
    cv2.circle(s, (7, 10), 4, 1, -1); cv2.circle(s, (7, 10), 4, 2, 1)
    for (px, py) in ((2, 5), (12, 5), (1, 8), (13, 8)): cv2.line(s, (7, 6), (px, py), 5, 2)
    cv2.line(s, (7, 6), (5, 2), 7, 1); cv2.line(s, (7, 6), (9, 2), 7, 1); s[1, 7] = 8; s[0, 7] = 8
    if fi % 2 == 0:
        s[9, 5] = 4; s[9, 9] = 4; s[8, 5] = 3; s[8, 9] = 3
    else:
        s[9, 4:7] = 3; s[9, 8:11] = 3
    s[12, 6:9] = 3

# ------------------------------------------------------------------ write the TIM and the MMD
for row, cols in PAL.items():
    tim.pal[row] = [0 if c is None else mmd.rgba_to_c15(*c) for c in cols]
tim.idx = bytearray(page.tobytes())
rgba = np.zeros((128, 256, 4), np.uint8)
for row in range(16):
    m = rowmap == row
    if not m.any(): continue
    lut = np.array([mmd.c15_to_rgba(c) for c in tim.pal[row]], np.uint8)
    rgba[m] = lut[page[m]]
b.tex = rgba
os.makedirs(OUT, exist_ok=True)
mp, tp = os.path.join(OUT, 'Yokomon.MMD'), os.path.join(OUT, 'Yokomon.TIM')
data = b.m.build()
open(mp, 'wb').write(data); open(tp, 'wb').write(tim.to_bytes())
cv2.imwrite(os.path.join(OUT, 'Yokomon-tex.png'), cv2.resize(cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA), None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST))
print(f'MMD {len(data)} bytes (limit 49152), TMD {len(tmd.build())}', file=sys.stderr)
spec = f'{mp}:44:{tp}:0:Yokomon'
print(spec)

if __name__ == '__main__' and '--nosheet' not in sys.argv:
    sheet(OUT + '/Yokomon-sheet.png', [spec], panels='mesh:front,mesh:three,mesh:side')
    if '--ticks' in sys.argv:
        for slot, ticks in ((0, (0, 6, 12)), (2, (0, 4, 9, 13)), (5, (10, 25, 40)), (8, (10, 24)), (9, (30,))):
            sheet(OUT + f'/yoko-slot{slot}.png', [f'{mp}:44:{tp}:{slot}:Yokomon'], panels='mesh:front,mesh:three', size=200, ticks=ticks)
    if '--cull' in sys.argv:
        import animsheet
        rest, _, _ = animsheet.slot_frames(b.m, 10, 0)
        pose = [list(v) for v in rest[0]]; pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
        tiles = []
        for yaw in (0.0, 0.7, 1.57):
            for cull in (False, True):
                img = mmd.render(b.m, tim, pose, size=200, yaw=yaw, cull=cull)
                tiles.append(np.frombuffer(bytes(img), np.uint8).reshape(200, 200, 4))
        grid = np.vstack([np.hstack(tiles[i:i + 2]) for i in range(0, 6, 2)])
        cv2.imwrite(OUT + '/yoko-cull.png', cv2.cvtColor(grid, cv2.COLOR_RGBA2BGRA))
