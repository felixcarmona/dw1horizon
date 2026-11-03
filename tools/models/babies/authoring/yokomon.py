"""Tanemon -> Yokomon, round 5: the mesh is rebuilt from scratch on Tanemon's skeleton and animations, the page is
hand-painted with palettes chosen by hand (no quantiser, indices written straight into the TIM). Shapes follow the
encyclopedia art, the Toei model sheet and the New Century render (ref/more/Yokomon): six broad drooping blades
tilted to face the viewer, a dominant crown of six thick hooked yellow stamens and a tall orange-red curl, eight soft
root tendrils lying outward on the ground with up-curled tips (octopus style) under a bulb that sits low on them, a
plain bulb with a faintly darker top. Judge it with kit/gouraud.py (per-vertex lighting like the game).

Bone -> object: 2 = the pink onion bulb + four static root tendrils; 3 = neck + six stamen tubes + the red hook + the
front and back petals; 4 / 5 = two blades each at +-30 degrees from x (those bones flap about z, so a petal must run
mostly along +-x to lift like the leaves did); 6-9 = four root tendrils on Tanemon's foot bones (they paddle in the
walk). Petal edges are jagged by texture cut-outs (colour 0).

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
STAM = (152, 48, 160, 96)     # strip along a stamen tube: olive at the base, yellow, pale at the hook
CURL = (176, 48, 184, 96)
FOOT = (184, 48, 200, 64)
EYE_SRC = {'open': 168, 'angry': 40, 'half': 72, 'happy': 136, 'shut': 104}
MOUTH_SRC = {'closed': 128, 'slight': 104, 'open': 80, 'wide': 56}

# ------------------------------------------------------------------ geometry
# bulb (bone 2, world-ish coordinates: ground at y = 0, up = -y, front = -z)
NSEG = 10
RINGS = [(-7, 44), (-22, 68), (-46, 81), (-70, 87), (-97, 82), (-118, 66), (-142, 29)]   # 174 wide, sits low on the roots
Y_TOP, Y_BOT = -142, -4


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
                        bottom=Y_BOT, top=Y_TOP - 2, capuv=[(32, 95), (32, 48)])
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


def tendril(p, origin, alpha_deg, r_in=24, r_out=84, r_tip=106, lift=26):
    """One root: a soft 3-sided tube that starts under the bulb, lies outward along the ground and curls up at the
    tip (an octopus arm). World points, then moved into the part's bone space by subtracting its origin."""
    a = math.radians(alpha_deg)
    d = (math.cos(a), 0.0, -math.sin(a))
    pts = [(d[0] * r_in - origin[0], -10 - origin[1], d[2] * r_in - origin[2]),
           (d[0] * r_out - origin[0], -9 - origin[1], d[2] * r_out - origin[2]),
           (d[0] * r_tip - origin[0], -7 - lift - origin[1], d[2] * r_tip - origin[2])]
    tube(p, pts, [10.0, 8.5, 0], 3, R_SKIN, (FOOT[0], FOOT[2] - 1), lambda i: FOOT[1] + min(15, 7 * i), tip=True)


for alpha in (0, 90, 180, 270):            # static roots between Tanemon's four feet: a ring of eight
    tendril(body, (0.0, 0.0, 0.0), alpha)

# neck + stamens + curl + the front and back petals (bone 3: origin at world y -165, 23 above the bulb's top). The
# petal hinges (bones 4/5) are 62 above that; the receptacle sits at local -33 (world -198), 29 below the hinges.
neck = Part()
TOP = -45.0
NRINGS = [(36, 36), (10, 25), (-18, 18), (-45, 14)]


def neck_uv(i, k):
    u0, u1 = NECK[0] + 15 * ((k + 1) % 6) // 6, NECK[0] + 15 * k // 6
    if k == 5: u0 = NECK[2] - 1
    vfn = lambda y: int(round(NECK[1] + (NECK[3] - 1 - NECK[1]) * (y - TOP) / (36 - TOP)))
    return [(u0, vfn(NRINGS[i + 1][0])), (u1, vfn(NRINGS[i + 1][0])), (u0, vfn(NRINGS[i][0])), (u1, vfn(NRINGS[i][0]))]


lathe(neck, NRINGS, 6, 90, R_SKIN, neck_uv, top=TOP - 2, capuv=[None, (NECK[0] + 8, NECK[1])])


def stamen(p, psi_deg, h, out, r=8.0):
    """One thick yellow stamen: a 3-sided tube rising from the receptacle, bending outward over the top and hooking
    back down and in (a crook). psi from +x towards -z."""
    ps = math.radians(psi_deg)
    d = (math.cos(ps), 0.0, -math.sin(ps))
    pts = [(d[0] * 6, TOP + 2, d[2] * 6),
           (d[0] * 11, TOP - 0.55 * h, d[2] * 11),
           (d[0] * out * 0.55, TOP - h, d[2] * out * 0.55),
           (d[0] * out, TOP - 0.78 * h, d[2] * out),
           (d[0] * out * 0.88, TOP - 0.5 * h, d[2] * out * 0.88)]
    tube(p, pts, [r, r, r * 0.95, r * 0.85, 0], 3, R_STAMEN, (STAM[0], STAM[2] - 1), lambda i: STAM[1] + min(47, 12 * i), tip=True)


for psi, h, out in ((0, 44, 62), (180, 44, 62), (45, 40, 54), (135, 40, 54), (225, 44, 50), (315, 44, 50)):
    stamen(neck, psi, h, out)


def curl(p):
    """The orange-red tendril: a tall stem up from the centre, then 300 degrees of hook curling inwards in the x/y
    plane facing the front (up the left, over the top to the right, down and in: the Toei sheet's '6')."""
    ZC = -12.0                        # the spiral's plane sits a little forward, in the gap between the front hooks
    pts = [(2, TOP + 2, -3), (3, -62, -9), (3, -74, ZC)]
    r0, r1, sweep, nsp = 25.0, 8.5, 300.0, 6
    C = (3 + r0, -74.0)
    for i in range(1, nsp + 1):
        sgm = i / nsp
        a = math.radians(180 - sweep * sgm)
        r = r0 + (r1 - r0) * sgm
        pts.append((C[0] + r * math.cos(a), C[1] - r * math.sin(a), ZC))
    radii = [9.5, 9.5, 9.5] + [9.5 - 3.5 * (i / nsp) for i in range(1, nsp + 1)]
    radii[-1] = 0
    tube(p, pts, radii, 4, R_STAMEN, (CURL[0], CURL[2] - 1), lambda i: CURL[1] + min(47, 5 * i), tip=True)


curl(neck)


def petal(p, base, phi_deg, L, rise, fall, half_w, cup, tilt, t_rings=(0.36, 0.72)):
    """A lily petal: base = where it grows from (in the part's bone space); phi from +x towards -z; rise = how much it
    lifts first, fall = how far the tip droops (positive = down), cup = edges lifted, tilt = the front edge lower
    than the back edge (turns the face towards the viewer). t_rings: one ring = a kite, two = a waisted blade. Both
    sides are emitted; the jagged edge is a cut-out in the texture."""
    ph = math.radians(phi_deg)
    d = (math.cos(ph), 0.0, -math.sin(ph))
    s = (math.sin(ph), 0.0, math.cos(ph))

    def centre(t):
        return (base[0] + d[0] * L * t, base[1] - rise * math.sin(math.pi * t) + fall * t * t, base[2] + d[2] * L * t)

    def width(t): return half_w * math.sin(math.pi * t ** 0.6) ** 0.7     # broad early, pointed tip

    def tangent(t):
        return (d[0] * L, -rise * math.pi * math.cos(math.pi * t) + 2 * fall * t, d[2] * L)

    def normals(t):
        n = unit(cross(tangent(t), s)); n = n if n[1] < 0 else (-n[0], -n[1], -n[2])
        return p.norm(*n), p.norm(-n[0], -n[1], -n[2])

    vb = p.vert(*centre(0.02)); nb_t, nb_b = normals(0.02)
    rings = []
    for t in t_rings:
        c = centre(t); w = width(t); lift = cup * (w / half_w)
        e = []
        for sg in (-1, 1):
            z_edge = c[2] + sg * s[2] * w
            dz = (z_edge - c[2]) / max(w, 1e-6)                 # -1 .. 1, negative = towards the front
            e.append(p.vert(c[0] + sg * s[0] * w, c[1] - lift + tilt * (-dz), z_edge))
        vc = p.vert(*c)
        nt, nbt = normals(t)
        rings.append(((e[0], vc, e[1]), nt, nbt))
    vt = p.vert(*centre(1.0)); nt_t, nt_b = normals(1.0)
    u0, uc, u1 = PETAL[0], (PETAL[0] + PETAL[2]) // 2, PETAL[2] - 1
    vv = lambda t: int(round(PETAL[1] + (PETAL[3] - 1 - PETAL[1]) * t))
    for side in (0, 1):
        nb = (nb_t, nb_b)[side]; ntip = (nt_t, nt_b)[side]
        (a0, ac, a1), na = rings[0][0], rings[0][1 + side]
        p.tri((vb, a0, ac), (nb, na, na), [(uc, vv(0)), (u0, vv(t_rings[0])), (uc, vv(t_rings[0]))], R_PETAL, want=p.n[na])
        p.tri((vb, ac, a1), (nb, na, na), [(uc, vv(0)), (uc, vv(t_rings[0])), (u1, vv(t_rings[0]))], R_PETAL, want=p.n[na])
        for i in range(1, len(rings)):
            (c0_, cc, c1), nc = rings[i][0], rings[i][1 + side]
            ta, tc = t_rings[i - 1], t_rings[i]
            p.quad((c0_, cc, a0, ac), (nc, nc, na, na), [(u0, vv(tc)), (uc, vv(tc)), (u0, vv(ta)), (uc, vv(ta))], R_PETAL, want=p.n[na])
            p.quad((cc, c1, ac, a1), (nc, nc, na, na), [(uc, vv(tc)), (u1, vv(tc)), (uc, vv(ta)), (u1, vv(ta))], R_PETAL, want=p.n[na])
            (a0, ac, a1), na = (c0_, cc, c1), nc
        tl = t_rings[-1]
        p.tri((a0, ac, vt), (na, na, ntip), [(u0, vv(tl)), (uc, vv(tl)), (uc, vv(1))], R_PETAL, want=p.n[na])
        p.tri((ac, a1, vt), (na, na, ntip), [(uc, vv(tl)), (u1, vv(tl)), (uc, vv(1))], R_PETAL, want=p.n[na])


petR, petL = Part(), Part()
# Six broad blades at 60 degrees drooping outward and down, their faces tilted towards the viewer; the four leaning
# sideways flap with Tanemon's leaf bones (they run along +-x, which is what an rz hinge can lift), the front and back
# ones hang from the neck bone. Kept modest so the stamens and the curl dominate. (phi, L, rise, fall, half w, cup, tilt)
HINGE_DROP = 17.0                     # the receptacle is this far below the leaf hinges (world -210 vs -227)
for phi, L, rise, fall, hw, cup, tilt in ((30, 104, 8, 56, 38, 8, 22), (-30, 100, 8, 50, 38, 8, 12)):
    petal(petR, (-22.0, HINGE_DROP, 0.0), phi, L, rise, fall, hw, cup, tilt)
    petal(petL, (21.0, HINGE_DROP, 0.0), 180 - phi, L, rise, fall, hw, cup, tilt)
petal(neck, (0.0, TOP, 0.0), 90, 86, 8, 42, 38, 8, 0)        # front: shorter, so the eating nod keeps the eyes clear
petal(neck, (0.0, TOP, 0.0), 270, 98, 8, 50, 38, 8, 0)       # back

feet = []
for (bx, bz), alpha in (((48, -36), 37), ((-48, -36), 143), ((47, 43), 318), ((-47, 43), 222)):
    f = Part()
    tendril(f, (float(bx), -24.0, float(bz)), alpha)       # Tanemon's foot bones: these four paddle in the walk
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
PAL[R_PETAL] = [None, (16, 24, 80), (24, 56, 160), (48, 112, 216), (96, 152, 240), (144, 184, 240), (184, 208, 248),
                (208, 176, 32), (240, 216, 56), (248, 240, 136), (32, 80, 192), (0, 0, 0), (0, 0, 0), (0, 0, 0),
                (0, 0, 0), (0, 0, 0)]
PC = {'line': 1, 'navy': 2, 'dark': 3, 'blue': 4, 'light': 5, 'pale': 6, 'ydark': 7, 'yellow': 8, 'ylight': 9, 'n2': 10}
PAL[R_STAMEN] = [None, (136, 120, 16), (200, 184, 32), (248, 224, 48), (248, 240, 152), (240, 144, 40),
                 (232, 80, 32), (208, 48, 32), (152, 24, 32), (104, 40, 16), (248, 200, 48), (0, 0, 0), (0, 0, 0),
                 (0, 0, 0), (0, 0, 0), (0, 0, 0)]
SC = {'olive2': 1, 'olive': 2, 'yellow': 3, 'ylight': 4, 'orange': 5, 'ored': 6, 'red': 7, 'dred': 8, 'brown': 9, 'oyellow': 10}
PAL[R_SPRITE] = [None, (248, 208, 224), (216, 128, 168), (24, 16, 24), (80, 192, 72), (56, 88, 200), (24, 32, 104),
                 (240, 216, 56), (208, 48, 32), (255, 255, 255), (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0)]


def region(x0, y0, x1, y1, row, fill=0):
    rowmap[y0:y1, x0:x1] = row
    page[y0:y1, x0:x1] = fill


# -- body skin strip: gradient top (deep) -> bottom (white), back a shade darker, onion stripes near the top
region(*SKIN, R_SKIN)
ramp = [SK['mid'], SK['mid'], SK['m2'], SK['m3'], SK['pale'], SK['p2'], SK['p3'], SK['white'], SK['hi']]
for v in range(SKIN[1], SKIN[3]):
    t = (v - SKIN[1]) / float(SKIN[3] - 1 - SKIN[1])          # 0 top .. 1 bottom
    for u in range(SKIN[0], SKIN[2]):
        back = abs(u - 32) / 32.0                                 # 0 front .. 1 back
        k = (t ** 0.8) * 8.6 - back * 1.6 + (0.6 if u > 32 else 0.0)
        page[v, u] = ramp[int(max(0, min(8, round(k))))]
cap = [(SKIN[0], SKIN[1])] + [(u, SKIN[1] + (6 if (u // 4) % 2 else 3)) for u in range(SKIN[0], SKIN[2] + 1, 4)] + [(SKIN[2], SKIN[1])]
cv2.fillPoly(page, [np.array(cap, np.int32)], SK['d3'])          # the onion's darker top, one step deeper pink
for u, du in ((18, -2), (27, -1), (37, 1), (46, 2)):               # four faint lines converging on the neck
    cv2.line(page, (u, SKIN[1] + 4), (u + du, SKIN[1] + 13), SK['d4'], 1)

# -- neck strip: pale pink, darker at the top, dark pink converging stripes
region(*NECK, R_SKIN)
for v in range(NECK[1], NECK[3]):
    t = (v - NECK[1]) / float(NECK[3] - 1 - NECK[1])         # 0 top .. 1 bottom (bulb)
    page[v, NECK[0]:NECK[2]] = [SK['d4'], SK['mid'], SK['m2'], SK['m3'], SK['pale']][int(t * 4.99)]
for u in (66, 70, 74, 78):
    cv2.line(page, (u, NECK[1]), (u, NECK[1] + 7), SK['d3'], 1)

# -- roots: a deeper pink than the bulb so the tendrils read under it, darker towards the tips and along one edge
region(*FOOT, R_SKIN)
for v in range(FOOT[1], FOOT[3]):
    t = (v - FOOT[1]) / float(FOOT[3] - 1 - FOOT[1])
    page[v, FOOT[0]:FOOT[2]] = [SK['mid'], SK['d4'], SK['d4'], SK['d3']][int(t * 3.99)]
page[FOOT[1]:FOOT[3], FOOT[0]:FOOT[0] + 3] = SK['d3']

# -- petal: medium blue, lighter towards the midrib, a light-blue rim, the yellow star at the base, and a jagged
# edge cut out of the outer half (index 0 = transparent)
region(*PETAL, R_PETAL)
pw, ph = PETAL[2] - PETAL[0], PETAL[3] - PETAL[1]
for v in range(PETAL[1], PETAL[3]):
    t = (v - PETAL[1]) / float(ph - 1)
    for u in range(PETAL[0], PETAL[2]):
        e = abs(u - (PETAL[0] + pw / 2.0 - 0.5)) / (pw / 2.0)      # 0 centre .. 1 edge
        k = 3.2 - 1.6 * e * e - 0.8 * t + (0.6 if t < 0.25 else 0) - (0.9 if t < 0.12 else 0)
        page[v, u] = [PC['navy'], PC['dark'], PC['blue'], PC['light'], PC['pale']][int(max(1, min(4, round(k))))]
cv2.rectangle(page, (PETAL[0], PETAL[1]), (PETAL[2] - 1, PETAL[3] - 1), PC['pale'], 2)
cv2.rectangle(page, (PETAL[0], PETAL[1]), (PETAL[2] - 1, PETAL[3] - 1), PC['n2'], 1)
teeth = []
for v in range(PETAL[1] + 28, PETAL[3], 7):                         # notches on both edges, outer half only
    teeth.append(np.array([(PETAL[0] - 1, v), (PETAL[0] + 5, v + 3), (PETAL[0] - 1, v + 6)], np.int32))
    teeth.append(np.array([(PETAL[2], v + 3), (PETAL[2] - 6, v + 6), (PETAL[2], v + 9)], np.int32))
cv2.fillPoly(page, teeth, 0)
cx, cy = PETAL[0] + pw // 2, PETAL[1] + 12
star = []
for i in range(16):
    a = math.pi * 2 * i / 16; r = 14 if i % 2 == 0 else 6
    star.append((int(round(cx + r * math.cos(a))), int(round(cy + r * 0.9 * math.sin(a)))))
cv2.fillPoly(page, [np.array(star, np.int32)], PC['yellow'])
cv2.polylines(page, [np.array(star, np.int32)], True, PC['ydark'], 1)
cv2.line(page, (cx, cy + 10), (cx, PETAL[3] - 20), PC['light'], 1)

# -- stamen strip: olive at the base, bright yellow, pale at the hook; a dark edge line
region(*STAM, R_STAMEN)
for v in range(STAM[1], STAM[3]):
    t = (v - STAM[1]) / float(STAM[3] - 1 - STAM[1])
    page[v, STAM[0]:STAM[2]] = [SC['olive'], SC['yellow'], SC['yellow'], SC['yellow'], SC['ylight']][int(t * 4.99)]
page[STAM[1]:STAM[3], STAM[0]] = SC['olive2']
page[STAM[1] + 6:STAM[3], STAM[0] + 3:STAM[0] + 5] = SC['ylight']
# -- curl strip: orange-red with a yellow inner edge, deeper red towards the spiral's centre
region(*CURL, R_STAMEN)
for v in range(CURL[1], CURL[3]):
    t = (v - CURL[1]) / float(CURL[3] - 1 - CURL[1])
    page[v, CURL[0]:CURL[2]] = [SC['ored'], SC['ored'], SC['ored'], SC['red'], SC['red']][int(t * 4.99)]
page[CURL[1]:CURL[3], CURL[0]] = SC['brown']; page[CURL[1]:CURL[3], CURL[2] - 1] = SC['dred']
page[CURL[1]:CURL[3], CURL[0] + 2:CURL[0] + 4] = SC['oyellow']


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
        # three lashes as the Toei sheet draws them: upper-outer, lower-outer, and a short dash below the inner side
        for (ax, ay, bx, by) in ((cx + 6, cy - 10, cx + 9, cy - 14), (cx + 9, cy + 7, cx + 13, cy + 10), (cx - 4, cy + 11, cx - 5, cy + 15)):
            cv2.line(sub_, (ax, ay), (bx, by), FC['ink'], 2)
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
        cv2.polylines(sub_, [np.array(smile, np.int32)], False, FC['ink'], 3)
        cv2.line(sub_, (0, 15), (2, 11), FC['ink'], 3)       # the notch at the centre line (Tanemon's w)
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
    if '--game' in sys.argv:          # the field camera: above and in front; plus a game-size (x3 nearest) strip
        import animstudio as A
        A.VIEWS['game'] = (25, 40); A.VIEWS['game2'] = (115, 40)
        for slot, tick in ((0, 0), (2, 4), (2, 9), (8, 9)):
            mod = A.Model(f'{mp}:44:{tp}:{slot}:Yokomon', slot)
            rows = A.build([mod], ['mesh:game', 'mesh:game2', 'mesh:top', 'mesh:front'], 220)
            fr = np.asarray(A.frame(rows, tick, 220).convert('RGB'))
            body_ = fr[18:]
            small = cv2.resize(body_, (body_.shape[1] // 4, body_.shape[0] // 4), interpolation=cv2.INTER_AREA)
            small = cv2.resize(small, (small.shape[1] * 3, small.shape[0] * 3), interpolation=cv2.INTER_NEAREST)
            canvas = np.full((fr.shape[0] + small.shape[0] + 4, fr.shape[1], 3), (20, 22, 26), np.uint8)
            canvas[:fr.shape[0]] = fr; canvas[fr.shape[0] + 4:, :small.shape[1]] = small
            cv2.imwrite(OUT + f'/yoko-game-s{slot}-t{tick}.png', cv2.cvtColor(canvas, cv2.COLOR_RGB2BGR))
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
