"""Botamon (type 1) -> YukimiBotamon, round 2: the donor keeps only its skeleton and animations; the mesh (a puffy round
body with two round bear ears), the UVs and the whole texture page are ours.

Conventions measured on the donor (and checked on PUNI/POYO): stored normals point outward; a front face has
cross(v1-v0, v2-v0) opposite to its normal; the face looks toward -z; y negative is up; object 0 rides bone 2 whose
pivot is 45 above the ground, so the body bottom stays at y=+44 (the squash keys compensate for that height).
Texture: eye frames 24x16 at (48+24k, 0) copied to (8,8); mouth frames at (48+24k, 16) copied to (0,24). CLUT rows:
0 fur, 1 eyes, 2 mouth (CBA = 0x7A00 + row<<6); every row is painted with its own <=16 colours (multiples of 8) so
tex_import keeps them exactly. Row 15's sprite area (u>=224, v>=96) is left alone."""
from lib import *
import math

b = Baby('YukimiBotamon', 1)
tmd = b.m.tmd

# ---------------------------------------------------------------- body shape (reference: head 1.41 wide : 1 tall,
# widest at the eye line 54% down, mouth 78% down; the bottom rounder than the top)
TOP, EYE_Y, BOT = -56.0, -3.0, 44.0
RX, RZ = 72.0, 0.9                      # half-width; depth = RZ * width


def body_r(y):
    """Half-width at height y: a superellipse (n 2.4, broad top) above the eye line, an ellipse below, cut at BOT."""
    if y < EYE_Y:
        t, n = (EYE_Y - y) / (EYE_Y - TOP), 2.7
    else:
        t, n = (y - EYE_Y) / 49.0, 2.0
    t = min(1.0, max(0.0, t))
    return RX * (1 - t ** n) ** (1 / n)


RINGS = [-55, -52, -47, -40, -31, -18, 12, 32, 40, BOT]          # eye cell -18..12 (centre -3), mouth cell 12..32
COLS = [-17, 17, 45, 67.5, 90, 112.5, 135, 157.5, 180, -157.5, -135, -112.5, -90, -67.5, -45]   # azimuth from the front
EYE_BAND, MOUTH_BAND = 5, 6
R_EYE, L_EYE, MOUTH = (17, 45), (-45, -17), (-17, 17)


def body_pt(th, y):
    r = body_r(y); a = math.radians(th)
    return (r * math.sin(a), y, -RZ * r * math.cos(a))


# ---------------------------------------------------------------- texture layout
ROW_FUR, ROW_EYE, ROW_MOUTH = 0, 1, 2
BAND_V0, BAND_V1 = 40, 119              # body band: u 0..223 (front half denser), v 40..119
EAR_U0, EAR_V0 = 192, 0                 # ear patch 64x40


def band_u(th):
    a = abs(th)
    g = 0.75 * a if a <= 90 else 67.5 + (a - 90) * (43.0 / 90)      # u 1..223: row 15's sprite area (u 224+) untouched
    return 112 + (g if th >= 0 else -g)


def band_v(y):
    return BAND_V0 + (y - TOP) / (BOT - TOP) * (BAND_V1 - BAND_V0)


verts, faces = [], []                   # faces: dict(v=[...], uv=[...], row=r, ref=(x,y,z) the point the face looks away from)


def V(p):
    verts.append((float(p[0]), float(p[1]), float(p[2]))); return len(verts) - 1


def quad(ids, uvs, row, ref):
    faces.append(dict(v=list(ids), uv=[(int(round(u)), int(round(v))) for u, v in uvs], row=row, ref=ref))


top = V((0, TOP, 0))
grid = [[V(body_pt(th, y)) for th in COLS] for y in RINGS]
bot = V((0, BOT, 0))
NC = len(COLS)


def cell_th(j):
    a, c = COLS[j], COLS[(j + 1) % NC]
    if a == 180 and c < 0: a = -180
    return a, c


for j in range(NC):
    a, c = cell_th(j); j1 = (j + 1) % NC
    ua, uc = band_u(a), band_u(c)
    # top cap
    quad([top, grid[0][j], grid[0][j1]], [((ua + uc) / 2, band_v(TOP)), (ua, band_v(RINGS[0])), (uc, band_v(RINGS[0]))],
         ROW_FUR, (0, TOP * 0.8, 0))
    for i in range(len(RINGS) - 1):
        ya, yb = RINGS[i], RINGS[i + 1]
        ids = [grid[i][j], grid[i][j1], grid[i + 1][j], grid[i + 1][j1]]
        ref = (0, 0.8 * (ya + yb) / 2, 0)
        if i == EYE_BAND and (a, c) == R_EYE:
            quad(ids, [(8, 8), (31, 8), (8, 23), (31, 23)], ROW_EYE, ref)
        elif i == EYE_BAND and (a, c) == L_EYE:           # mirrored: texel column 31 is the outer edge of both eyes
            quad(ids, [(31, 8), (8, 8), (31, 23), (8, 23)], ROW_EYE, ref)
        elif i == MOUTH_BAND and (a, c) == MOUTH:
            quad(ids, [(0, 24), (23, 24), (0, 39), (23, 39)], ROW_MOUTH, ref)
        else:
            quad(ids, [(ua, band_v(ya)), (uc, band_v(ya)), (ua, band_v(yb)), (uc, band_v(yb))], ROW_FUR, ref)
    # flat bottom
    quad([bot, grid[-1][j1], grid[-1][j]], [((ua + uc) / 2, BAND_V1), (uc, BAND_V1), (ua, BAND_V1)], ROW_FUR, (0, BOT - 10, 0))

# ---------------------------------------------------------------- ears: two spheres sunk into the top corners
EAR_R, EAR_RZ = 28.0, 0.85
EAR_LATS = [60, 30, 0, -30, -60]
EAR_NC = 12


def inside_body(p, margin=1.0):
    x, y, z = p
    if y > BOT or y < TOP: return False
    return math.hypot(x, z / RZ) < body_r(y) - margin


for side in (1, -1):
    C = (43.0 * side, -59.0, -3.0)
    pole = V((C[0], C[1] - EAR_R, C[2]))
    ring = []
    for lat in EAR_LATS:
        row = []
        for k in range(EAR_NC):
            az = math.radians(k * 360.0 / EAR_NC + 15)
            cl = math.cos(math.radians(lat))
            row.append(V((C[0] + EAR_R * cl * math.sin(az), C[1] - EAR_R * math.sin(math.radians(lat)), C[2] - EAR_RZ * EAR_R * cl * math.cos(az))))
        ring.append(row)
    epole = V((C[0], C[1] + EAR_R, C[2]))

    def eu(k): return EAR_U0 + k * 63.0 / EAR_NC
    def ev(lat): return EAR_V0 + 2 + (90 - lat) / 180.0 * 36

    for k in range(EAR_NC):
        k1 = (k + 1) % EAR_NC; ua, uc = eu(k), eu(k + 1)
        quad([pole, ring[0][k], ring[0][k1]], [((ua + uc) / 2, ev(90)), (ua, ev(EAR_LATS[0])), (uc, ev(EAR_LATS[0]))], ROW_FUR, C)
        for i in range(len(EAR_LATS) - 1):
            ids = [ring[i][k], ring[i][k1], ring[i + 1][k], ring[i + 1][k1]]
            if all(inside_body(verts[v]) for v in ids): continue
            la, lb = EAR_LATS[i], EAR_LATS[i + 1]
            quad(ids, [(ua, ev(la)), (uc, ev(la)), (ua, ev(lb)), (uc, ev(lb))], ROW_FUR, C)
        ids = [epole, ring[-1][k1], ring[-1][k]]
        if not all(inside_body(verts[v]) for v in ids):
            quad(ids, [((ua + uc) / 2, ev(-90)), (uc, ev(EAR_LATS[-1])), (ua, ev(EAR_LATS[-1]))], ROW_FUR, C)

# ---------------------------------------------------------------- drop the vertices no face kept (ear poles inside the head)
used = sorted(set(v for f in faces for v in f['v']))
remap = {old: new for new, old in enumerate(used)}
verts = [verts[v] for v in used]
for f in faces:
    f['v'] = [remap[v] for v in f['v']]

# ---------------------------------------------------------------- normals (outward, area weighted) and winding
P = np.array(verts)
nacc = np.zeros((len(verts), 3))
for f in faces:
    ids = f['v']
    corners = [(0, 1, 2)] + ([(1, 3, 2)] if len(ids) == 4 else [])
    for c in corners:
        p0, p1, p2 = (P[ids[k]] for k in c)
        n = np.cross(p1 - p0, p2 - p0)
        centre = (p0 + p1 + p2) / 3
        if n @ (centre - np.array(f['ref'])) < 0: n = -n
        for k in c: nacc[ids[k]] += n
nrm = nacc / np.maximum(np.linalg.norm(nacc, axis=1), 1e-9)[:, None]
for f in faces:                         # front face: cross(v1-v0, v2-v0) against the outward normal
    ids = f['v']; p0, p1, p2 = (P[ids[k]] for k in (0, 1, 2))
    if np.cross(p1 - p0, p2 - p0) @ nrm[ids].mean(0) > 0:
        f['v'][1], f['v'][2] = f['v'][2], f['v'][1]
        f['uv'][1], f['uv'][2] = f['uv'][2], f['uv'][1]

# ---------------------------------------------------------------- write the TMD object
ob = tmd.objects[0]
tmd.verts = [(int(round(x)), int(round(y)), int(round(z)), 0) for x, y, z in verts]
tmd.norms = [(int(round(x * 4096)), int(round(y * 4096)), int(round(z * 4096)), 0) for x, y, z in nrm]
ob.vert_start, ob.nvert, ob.norm_start, ob.nnorm = 0, len(verts), 0, len(verts)
ob.prims = []
for f in faces:
    n = len(f['v'])
    ob.prims.append(mmd.Prim.encode(dict(mode=0x3C if n == 4 else 0x34, flag=0, olen=12 if n == 4 else 9, uv=f['uv'],
                                         cba=0x7A00 + (f['row'] << 6), tsb=5, uvpad=[0] * (n - 2), colors=[],
                                         norms=f['v'], verts=f['v'], pad=[])))

# ---------------------------------------------------------------- texture
t = b.tex
t[:] = (248, 248, 248, 255)
FUR = [(248, 248, 248), (240, 240, 248), (232, 240, 248), (224, 232, 248), (208, 224, 248), (192, 208, 240),
       (176, 200, 232), (160, 184, 224)]
PINK = [(248, 232, 232), (248, 216, 224), (248, 200, 208), (248, 184, 200)]
K = [(16, 16, 24), (40, 40, 56), (64, 64, 88), (96, 96, 128)]
WHITE = FUR[0]
MOUTH_IN = [(160, 48, 72), (208, 88, 112), (248, 152, 168)]
BLUSH_TH, BLUSH_Y, BLUSH_RTH, BLUSH_RY = 45.0, 8.0, 14.0, 9.0     # cheek blush in model terms (azimuth, height)


def blush_at(th, y):
    """0..1 blush strength at azimuth th (either side) and height y."""
    return np.clip(1.25 - np.hypot((np.abs(th) - BLUSH_TH) / BLUSH_RTH, (y - BLUSH_Y) / BLUSH_RY), 0, 1)


def band_th(u):
    g = np.abs(u - 112.0)
    a = np.where(g <= 67.5, g / 0.75, 90 + (g - 67.5) * (90.0 / 43))
    return np.where(u >= 112, a, -a)


def band_y(v):
    return TOP + (v - BAND_V0) / (BAND_V1 - BAND_V0) * (BOT - TOP)


def paint_fur(x0, y0, w, h, shade, blush=None, puffs=None, seed=1):
    """shade(u, v) in 0..1 -> FUR index; blush(u, v) in 0..1 overrides with PINK where the fur is light;
    puffs(u, v) in 0..1 scales the cloud-puff shading."""
    rng = np.random.RandomState(seed)
    vv, uu = np.mgrid[0:h, 0:w].astype(float)
    s = shade(uu, vv)
    puff = np.zeros_like(s)             # soft blue along the lower rim of random circles: cloud tufts
    for _ in range(int(w * h / 220)):
        cx, cy, R = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(9, 14)
        d = np.hypot(uu - cx, vv - cy)
        low = np.clip((vv - cy) / R, 0, 1)
        ring = np.clip((d - 0.5 * R) / (0.5 * R), 0, 1) * (d < R) * low
        puff = np.maximum(puff, ring)
    if puffs is not None: puff = puff * puffs(uu, vv)
    s = np.clip(s + 0.22 * puff, 0, 1)
    idx = np.clip(np.round(s * (len(FUR) - 1)), 0, len(FUR) - 1).astype(int)
    out = np.array(FUR, np.uint8)[idx]
    if blush is not None:
        bi = np.clip(np.round(blush(uu, vv) * len(PINK)), 0, len(PINK)).astype(int)
        m = (bi > 0) & (idx <= 2)
        out[m] = np.array(PINK, np.uint8)[bi[m] - 1]
    t[y0:y0 + h, x0:x0 + w, :3] = out


def band_shade(u, v):
    """Blue toward the bottom and the back, a soft shadow at each ear root and under the chin."""
    u, v = u + 0.0, v + BAND_V0
    th, y = band_th(u), band_y(v)
    bottom = np.clip((y - 18) / 26.0, 0, 1) ** 1.3 * 0.95
    back = 0.18 * np.clip((np.abs(th) - 100) / 60.0, 0, 1)
    ear = 0.4 * np.clip(1 - np.hypot((np.abs(th) - 42) / 22.0, (y + 50) / 9.0), 0, 1)
    chin = 0.25 * np.clip(1 - np.hypot(th / 32.0, (y - 30) / 8.0), 0, 1)
    return np.clip(np.maximum(np.maximum(bottom, back), np.maximum(ear, chin)), 0, 1)


def band_blush(u, v):
    return blush_at(band_th(u), band_y(v + BAND_V0))


def band_puffs(u, v):                   # the face stays flat white so the eye and mouth cells blend in
    th, y = band_th(u), band_y(v + BAND_V0)
    return np.clip(np.hypot(th / 60.0, (y + 5) / 36.0) - 0.75, 0, 1) * 2


paint_fur(0, BAND_V0, 224, BAND_V1 - BAND_V0 + 1, band_shade, band_blush, band_puffs, seed=3)
# ear patch: blue toward the root (bottom of the patch)
paint_fur(EAR_U0, EAR_V0, 64, 40, lambda u, v: np.clip((v - 18) / 20.0, 0, 1) ** 1.4 * 0.8, seed=5)


# ---------------------------------------------------------------- eyes and mouth: 24x16 frames drawn at 4x and snapped to the row's palette
S = 4


def snap(img, palette):
    """Nearest palette colour per pixel (float HxWx3 -> uint8)."""
    pal = np.array(palette, float)
    d = ((img[..., None, :] - pal[None, None]) ** 2).sum(-1)
    return pal[d.argmin(-1)].astype(np.uint8)


def frame(draw, palette, background):
    """A 24x16 RGBA frame: draw(canvas at 4x) over white, area-downsampled and snapped to the ink palette (greys only,
    so no anti-aliased edge turns pink); the background (24x16x3, the blush) shows where nothing was drawn."""
    hi = np.full((16 * S, 24 * S, 3), WHITE, np.uint8)
    draw(hi)
    lo = cv2.resize(hi, (24, 16), interpolation=cv2.INTER_AREA).astype(float)
    ink = snap(lo, palette)
    untouched = (ink == np.array(WHITE, np.uint8)).all(-1)
    f = np.zeros((16, 24, 4), np.uint8); f[..., :3] = np.where(untouched[..., None], background, ink); f[..., 3] = 255
    return f


def pt(x, y): return (int(round((x + 0.5) * S)), int(round((y + 0.5) * S)))
def ax(rx, ry): return (int(round(rx * S)), int(round(ry * S)))


# frame texel (fu, fv) sits on the eye cell at azimuth 17 + fu*28/23 (outer edge at fu 23) and height -18 + fv*2
fv, fu = np.mgrid[0:16, 0:24].astype(float)
_bi = np.clip(np.round(blush_at(17 + fu * 28 / 23, -18 + fv * 2) * len(PINK)), 0, len(PINK)).astype(int)
EYE_BG = np.where((_bi > 0)[..., None], np.array(PINK, np.uint8)[np.maximum(_bi, 1) - 1], np.array(WHITE, np.uint8)[None, None])
EYE_PAL = K + [WHITE]
cx, cy = 11.5, 7.5                      # eye centre in texels


def eye_frame(kind):
    def draw(c):
        if kind in ('open', 'wide', 'half', 'squint'):
            rx, ry = {'open': (9, 6), 'wide': (9.4, 6.3), 'half': (9, 6), 'squint': (9, 3)}[kind]
            cv2.ellipse(c, pt(cx, cy), ax(rx, ry), 0, 0, 360, K[1], -1)                 # soft rim
            cv2.ellipse(c, pt(cx, cy), ax(rx - 0.7, ry - 0.7), 0, 0, 360, K[0], -1)
            if kind != 'squint':
                # the reflection: grey toward the lower right and a white gleam there (the reference's)
                cv2.ellipse(c, pt(cx + 3, cy + 2), ax(4, 3), 0, 0, 360, K[1], -1)
                cv2.ellipse(c, pt(cx + 3.5, cy + 2.5), ax(2.2, 1.6), 0, 0, 360, K[2], -1)
                cv2.ellipse(c, pt(cx + 4.5, cy + 2.5), ax(1.4, 1.2), 0, 0, 360, WHITE, -1)
                cv2.ellipse(c, pt(cx - 4, cy - 3), ax(0.8, 0.7), 0, 0, 360, K[3], -1)    # a small upper-left glint
                if kind == 'wide':
                    cv2.ellipse(c, pt(cx - 4, cy - 3), ax(1.1, 1.0), 0, 0, 360, WHITE, -1)
            if kind == 'half':                                                        # the lid covers the upper part
                c[:pt(0, cy - 1.2)[1], :] = WHITE
                cv2.line(c, pt(cx - 8.5, cy - 1.2), pt(cx + 8.5, cy - 1.2), K[1], S)
        elif kind == 'closed':                                                        # a soft downward arc
            cv2.ellipse(c, pt(cx, cy - 2.5), ax(8, 5.5), 0, 25, 155, K[0], int(1.8 * S))
        elif kind == 'happy':                                                         # ^ arc
            cv2.ellipse(c, pt(cx, cy + 3), ax(8, 6.5), 0, 205, 335, K[0], int(1.8 * S))
    return frame(draw, EYE_PAL, EYE_BG)


EYES = {48: 'wide', 72: 'squint', 96: 'happy', 120: 'half', 144: 'closed', 168: 'open'}
for x, kind in EYES.items():
    t[0:16, x:x + 24] = eye_frame(kind)
t[8:24, 8:32] = eye_frame('open')

# mouth: the cell is 42x20 units, so a texel is 1.75 x 1.25 units
MOUTH_PAL = K + [WHITE]
MOUTH_BG = np.tile(np.array(WHITE, np.uint8), (16, 24, 1))
mx = 11.5


def mouth_frame(kind):
    def draw(c):
        if kind == 'closed':                                                          # the ":3" cat mouth: two round lobes
            for ox in (-4.2, 4.2):
                cv2.ellipse(c, pt(mx + ox, 1.5), ax(4.0, 5.2), 0, 0, 180, K[0], int(1.7 * S))
        else:
            rx, ry = {'small': (4, 3), 'mid': (6, 4.5), 'wide': (8, 6.5)}[kind]
            my = 1.5 + ry
            cv2.ellipse(c, pt(mx, my), ax(rx, ry), 0, 0, 360, K[0], -1)
    f = frame(draw, MOUTH_PAL, MOUTH_BG)
    if kind != 'closed':                                                              # the inside, painted after snapping
        rx, ry = {'small': (4, 3), 'mid': (6, 4.5), 'wide': (8, 6.5)}[kind]
        my = 1.5 + ry
        cv2.ellipse(f, (int(round(mx)), int(round(my))), (int(rx - 1), int(ry - 1)), 0, 0, 360, MOUTH_IN[0] + (255,), -1)
        if kind != 'small':
            cv2.ellipse(f, (int(round(mx)), int(round(my + ry * 0.45))), (int(rx - 2.5), max(1, int(ry * 0.45))), 0, 0, 360, MOUTH_IN[2] + (255,), -1)
    return f


MOUTHS = {48: 'closed', 72: 'small', 96: 'mid', 120: 'wide'}
for x, kind in MOUTHS.items():
    t[16:32, x:x + 24] = mouth_frame(kind)
t[24:40, 0:24] = mouth_frame('closed')

print(b.save())
print('verts', len(verts), 'faces', len(faces), 'mmd bytes', os.path.getsize(os.path.join(OUT, 'YukimiBotamon.MMD')))
for r in range(3):
    print('row', r, 'colours', len(set(b.tim.pal[r]) - {0}))
