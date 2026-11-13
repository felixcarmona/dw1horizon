"""Botamon (type 1) -> YukimiBotamon, round 3: the donor keeps only its skeleton and animations; the mesh (a wide squat
furball with two flat bear ears at the top corners), the UVs and the whole texture page are ours.

Conventions measured on the donor (and checked on PUNI/POYO): stored normals point outward; a front face has
cross(v1-v0, v2-v0) opposite to its normal; the face looks toward -z; y negative is up; object 0 rides bone 2 whose
pivot is 45 above the ground, so the body bottom stays at y=+44 (the squash keys compensate for that height).
Texture: eye frames 24x16 at (48+24k, 0) copied to (8,8); mouth frames at (48+24k, 16) copied to (0,24). CLUT rows:
0 fur, 1 eyes, 2 mouth (CBA = 0x7A00 + row<<6); every row is painted with its own <=16 colours (multiples of 8) so
tex_import keeps them exactly. Row 15's sprite area (u>=224, v>=96) is left alone.
Round 3 (critique): body 148 wide x 96 tall x 0.85 deep, widest at the lower cheeks; ears are flattened discs tilted
outward; scalloped lower rings and painted fur strokes; eyes 19% of the width, wider mouth and blush; thicker
expression strokes; bluer shades."""
from lib import *
import math

b = Baby('YukimiBotamon', 1)
tmd = b.m.tmd

# ---------------------------------------------------------------- body shape
TOP, WIDE_Y, BOT = -52.0, 8.0, 44.0     # pole, the widest ring (60% down), the flat bottom
RX, RZ = 76.0, 0.85                     # half-width (vertices reach 148 wide); depth = RZ * width


def body_r(y):
    """Half-width at height y: superellipses (n 2.6) above and below the widest ring, cut flat at BOT."""
    if y < WIDE_Y:
        t = (WIDE_Y - y) / (WIDE_Y - TOP)
    else:
        t = (y - WIDE_Y) / 38.0
    t = min(1.0, max(0.0, t)); n = 2.6
    return RX * (1 - t ** n) ** (1 / n)


RINGS = [-50, -46, -40, -31, -19, 13, 31, 39, BOT]            # eye cell -19..13 (centre -3), mouth cell 13..31
COLS = [-16, 16, 44, 67, 90, 112.5, 135, 157.5, 180, -157.5, -135, -112.5, -90, -67, -44]   # azimuth from the front
EYE_BAND, MOUTH_BAND = 4, 5
R_EYE, L_EYE, MOUTH = (16, 44), (-44, -16), (-16, 16)
# fur scallops: radial zigzag (amplitude) on the lower rings, away from the face cells
ZIGZAG = {13: (4.0, 67), 31: (4.0, 44), 39: (4.0, 0), BOT: (3.0, 0)}       # ring y -> (amplitude, min |azimuth|)


def body_pt(th, y, j=0):
    r = body_r(y)
    if y in ZIGZAG and abs(th) >= ZIGZAG[y][1] and abs(th) != 180:
        r += ZIGZAG[y][0] * (1 if j % 2 else -1)
    a = math.radians(th)
    return (r * math.sin(a), y, -RZ * r * math.cos(a))


# ---------------------------------------------------------------- texture layout
ROW_FUR, ROW_EYE, ROW_MOUTH = 0, 1, 2
BAND_V0, BAND_V1 = 40, 119              # body band: u 1..223 (front half denser), v 40..119
EAR_U0, EAR_V0 = 192, 0                 # ear patch 64x40: the disc seen from the front
BOT_U0, BOT_V0 = 224, 40                # bottom disc 32x32


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
grid = [[V(body_pt(th, y, j)) for j, th in enumerate(COLS)] for y in RINGS]
bot = V((0, BOT, 0))
NC = len(COLS)


def cell_th(j):
    a, c = COLS[j], COLS[(j + 1) % NC]
    if a == 180 and c < 0: a = -180
    return a, c


def bot_uv(th, r):
    a = math.radians(th)
    return (BOT_U0 + 16 + r / 40.0 * 15 * math.sin(a), BOT_V0 + 16 - r / 40.0 * 15 * math.cos(a))


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
    # flat bottom: its own disc patch
    rb = body_r(BOT)
    quad([bot, grid[-1][j1], grid[-1][j]], [bot_uv(0, 0), bot_uv(c, rb), bot_uv(a, rb)], ROW_FUR, (0, BOT - 10, 0))

# ---------------------------------------------------------------- ears: flattened discs on the top corners, leaning outward
EAR_R, EAR_T = 28.0, 14.0               # rim radius, half thickness (half the diameter: a puff, not a fin)
EAR_C = (42.0, -47.0, -3.0)             # centre (x mirrored for the left ear)
EAR_OUT, EAR_BACK = 25.0, 6.0           # tilt outward (about z) and back (about x), degrees
EAR_NC = 12
EAR_LATS = [45, 0, -45]                 # latitude from the disc plane; poles at +-90 (front, back)


def inside_body(p, margin=1.0):
    x, y, z = p
    if y > BOT or y < TOP: return False
    return math.hypot(x, z / RZ) < body_r(y) - margin


def ear_world(lx, ly, lz, side):
    """Disc-local (x outward, y up, z toward the viewer) -> world, tilted and placed on its corner."""
    o, k = math.radians(EAR_OUT), math.radians(EAR_BACK)
    x, y = lx * math.cos(o) + ly * math.sin(o), -lx * math.sin(o) + ly * math.cos(o)      # lean the top outward
    y, z = y * math.cos(k) - lz * math.sin(k), y * math.sin(k) + lz * math.cos(k)         # and back
    return (EAR_C[0] * side + x * side, EAR_C[1] - y, EAR_C[2] - z)


def ear_uv(lx, ly):
    return (EAR_U0 + 31.5 + lx / EAR_R * 30, EAR_V0 + 20 - ly / EAR_R * 18)


for side in (1, -1):
    front = V(ear_world(0, 0, EAR_T, side)); back = V(ear_world(0, 0, -EAR_T, side))
    ring, ruv = [], []
    for lat in EAR_LATS:
        row, uvrow = [], []
        for k in range(EAR_NC):
            az = math.radians(k * 360.0 / EAR_NC + 15)
            cl = math.cos(math.radians(lat))
            lx, ly, lz = EAR_R * cl * math.cos(az), EAR_R * cl * math.sin(az), EAR_T * math.sin(math.radians(lat))
            row.append(V(ear_world(lx, ly, lz, side))); uvrow.append(ear_uv(lx, ly))
        ring.append(row); ruv.append(uvrow)
    cuv = ear_uv(0, 0)
    for k in range(EAR_NC):
        k1 = (k + 1) % EAR_NC
        for pole, i in ((front, 0), (back, len(EAR_LATS) - 1)):
            ids = [pole, ring[i][k], ring[i][k1]]
            if not all(inside_body(verts[v]) for v in ids):
                quad(ids, [cuv, ruv[i][k], ruv[i][k1]], ROW_FUR, ear_world(0, 0, 0, side))
        for i in range(len(EAR_LATS) - 1):
            ids = [ring[i][k], ring[i][k1], ring[i + 1][k], ring[i + 1][k1]]
            if all(inside_body(verts[v]) for v in ids): continue
            quad(ids, [ruv[i][k], ruv[i][k1], ruv[i + 1][k], ruv[i + 1][k1]], ROW_FUR, ear_world(0, 0, 0, side))

# ---------------------------------------------------------------- drop the vertices no face kept (ear parts inside the head)
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
FUR = [(248, 248, 248), (240, 240, 248), (232, 240, 248), (216, 232, 248), (200, 216, 240), (184, 208, 240),
       (168, 192, 232), (152, 184, 224)]
PINK = [(248, 232, 232), (248, 216, 224), (248, 200, 208), (248, 184, 200)]
K = [(16, 16, 24), (40, 40, 56), (64, 64, 88), (96, 96, 128)]
WHITE = FUR[0]
MOUTH_IN = [(160, 48, 72), (208, 88, 112), (248, 152, 168)]
BLUSH_TH, BLUSH_Y, BLUSH_RTH, BLUSH_RY = 48.0, 14.0, 16.0, 10.0   # cheek blush in model terms (azimuth, height)


def blush_at(th, y):
    """0..1 blush strength at azimuth th (either side) and height y."""
    return np.clip(1.25 - np.hypot((np.abs(th) - BLUSH_TH) / BLUSH_RTH, (y - BLUSH_Y) / BLUSH_RY), 0, 1)


def band_th(u):
    g = np.abs(u - 112.0)
    a = np.where(g <= 67.5, g / 0.75, 90 + (g - 67.5) * (90.0 / 43))
    return np.where(u >= 112, a, -a)


def band_y(v):
    return TOP + (v - BAND_V0) / (BAND_V1 - BAND_V0) * (BOT - TOP)


def fur_strokes(out, density, seed, tone=1):
    """Short fur strokes pointing down (2 px, blue-grey) with density(u, v) in 0..1 strokes per ~25 texels."""
    rng = np.random.RandomState(seed)
    h, w = out.shape[:2]
    idx = np.array([list(c) for c in FUR], np.uint8)
    for _ in range(int(w * h / 25)):
        u, v = rng.uniform(0, w), rng.uniform(0, h)
        if rng.uniform() > density(u, v): continue
        ln = rng.uniform(3, 7); sway = rng.uniform(-2.0, 2.0)
        pts = [(u + sway * (k / 3) ** 2, v + ln * k / 3) for k in range(4)]
        shade = out[int(v) % h, int(u) % w]
        base = int(np.argmin(((idx.astype(int) - shade.astype(int)) ** 2).sum(1)))
        col = FUR[min(len(FUR) - 1, base + 2 + tone + (1 if rng.uniform() < 0.25 else 0))]
        cv2.polylines(out, [np.array(pts, np.int32)], False, col, 1 if rng.uniform() < 0.8 else 2)


def paint_fur(x0, y0, w, h, shade, blush=None, density=None, seed=1, tone=1):
    """shade(u, v) in 0..1 -> FUR index; blush(u, v) in 0..1 overrides with PINK where the fur is light;
    density(u, v): fur strokes."""
    vv, uu = np.mgrid[0:h, 0:w].astype(float)
    s = np.clip(shade(uu, vv), 0, 1)
    idx = np.clip(np.round(s * (len(FUR) - 1)), 0, len(FUR) - 1).astype(int)
    out = np.ascontiguousarray(np.array(FUR, np.uint8)[idx])
    if density is not None:
        fur_strokes(out, density, seed, tone)
    if blush is not None:
        bi = np.clip(np.round(blush(uu, vv) * len(PINK)), 0, len(PINK)).astype(int)
        m = (bi > 0) & (idx <= 2)
        out[m] = np.array(PINK, np.uint8)[bi[m] - 1]
    t[y0:y0 + h, x0:x0 + w, :3] = out


def band_shade(u, v):
    """Bright top; blue toward the bottom and the back, a soft shadow at each ear root and under the chin."""
    th, y = band_th(u), band_y(v + BAND_V0)
    bottom = np.clip((y - 16) / 28.0, 0, 1) ** 1.4 * 0.8
    back = 0.15 * np.clip((np.abs(th) - 100) / 60.0, 0, 1)
    ear = 0.3 * np.clip(1 - np.hypot((np.abs(th) - 45) / 22.0, (y + 44) / 8.0), 0, 1)
    chin = 0.25 * np.clip(1 - np.hypot(th / 30.0, (y - 32) / 8.0), 0, 1)
    return np.maximum(np.maximum(bottom, back), np.maximum(ear, chin))


def band_blush(u, v):
    return blush_at(band_th(u), band_y(v + BAND_V0))


def band_density(u, v):                 # strokes: dense low, medium on the cheeks beside the face, few on top
    th, y = band_th(u), band_y(v + BAND_V0)
    low = np.clip((y - 4) / 40.0, 0, 1) ** 1.5 * 0.8
    cheek = 0.4 * np.clip(1 - np.hypot((np.abs(th) - 70) / 30.0, (y - 8) / 30.0), 0, 1)
    return np.clip(np.maximum(low, cheek), 0.04, 1)


paint_fur(0, BAND_V0, 224, BAND_V1 - BAND_V0 + 1, band_shade, band_blush, band_density, seed=3)
# ear patch: a white disc, bluer toward the rim (the base is at the bottom of the patch) with a few rim strokes
def ear_shade(u, v):
    r = np.hypot((u - 31.5) / 30.0, (v - 20) / 18.0)
    return np.clip((r - 0.55) / 0.45, 0, 1) ** 1.6 * 0.55 + 0.25 * np.clip((v - 26) / 14.0, 0, 1)


paint_fur(EAR_U0, EAR_V0, 64, 40, ear_shade, None,
          lambda u, v: 0.25 * (np.hypot((u - 31.5) / 30.0, (v - 20) / 18.0) > 0.8), seed=5, tone=0)
# bottom disc: the darkest fur with strokes
paint_fur(BOT_U0, BOT_V0, 32, 32, lambda u, v: 0.75 + 0.25 * np.clip(np.hypot(u - 16, v - 16) / 16, 0, 1), None,
          lambda u, v: 0.8 + 0 * u, seed=7, tone=0)


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


# frame texel (fu, fv) sits on the eye cell at azimuth 16 + fu*28/23 (outer edge at fu 23) and height -19 + fv*32/15
fv, fu = np.mgrid[0:16, 0:24].astype(float)
_bi = np.clip(np.round(blush_at(16 + fu * 28 / 23, -19 + fv * 32 / 15) * len(PINK)), 0, len(PINK)).astype(int)
EYE_BG = np.where((_bi > 0)[..., None], np.array(PINK, np.uint8)[np.maximum(_bi, 1) - 1], np.array(WHITE, np.uint8)[None, None])
EYE_PAL = K + [WHITE]
cx, cy = 11.5, 7.5                      # eye centre in texels; the cell is 35.6 x 32 units: a texel is 1.48 x 2 units
ERX, ERY = 9.4, 7.0                     # 28 units across


def eye_frame(kind):
    def draw(c):
        if kind in ('open', 'wide', 'half'):
            rx, ry = (ERX, ERY) if kind != 'wide' else (ERX + 0.4, ERY + 0.3)
            cv2.ellipse(c, pt(cx, cy), ax(rx, ry), 0, 0, 360, K[1], -1)                 # soft rim
            cv2.ellipse(c, pt(cx, cy), ax(rx - 0.7, ry - 0.7), 0, 0, 360, K[0], -1)
            # the reflection: grey toward the lower right and a white gleam there (the reference's)
            cv2.ellipse(c, pt(cx + 3, cy + 2.2), ax(4.2, 3.2), 0, 0, 360, K[1], -1)
            cv2.ellipse(c, pt(cx + 3.5, cy + 2.8), ax(2.4, 1.8), 0, 0, 360, K[2], -1)
            cv2.ellipse(c, pt(cx + 4.5, cy + 2.8), ax(1.6, 1.3), 0, 0, 360, WHITE, -1)
            cv2.ellipse(c, pt(cx - 4.2, cy - 3.4), ax(0.9, 0.8), 0, 0, 360, K[3], -1)    # a small upper-left glint
            if kind == 'wide':
                cv2.ellipse(c, pt(cx - 4.2, cy - 3.4), ax(1.3, 1.1), 0, 0, 360, WHITE, -1)
            if kind == 'half':                                                        # a curved lid covers the upper part
                cv2.ellipse(c, pt(cx, cy - 10.5), ax(14, 10.5), 0, 0, 360, WHITE, -1)
                cv2.ellipse(c, pt(cx, cy - 10.5), ax(14, 10.5), 0, 20, 160, K[1], S)
        elif kind == 'closed':                                                        # sleeping / blink: a soft downward arc
            cv2.ellipse(c, pt(cx, cy - 3), ax(8.5, 6), 0, 25, 155, K[0], int(2.8 * S))
        elif kind == 'happy':                                                         # ^ arc
            cv2.ellipse(c, pt(cx, cy + 3.5), ax(8.5, 7), 0, 205, 335, K[0], int(2.8 * S))
    return frame(draw, EYE_PAL, EYE_BG)


EYES = {48: 'wide', 72: 'closed', 96: 'happy', 120: 'half', 144: 'closed', 168: 'open'}
for x, kind in EYES.items():
    t[0:16, x:x + 24] = eye_frame(kind)
t[8:24, 8:32] = eye_frame('open')

# mouth: the cell is 39 x 18 units, so a texel is 1.63 x 1.13 units; the omega spans 32 units
MOUTH_PAL = K + [WHITE]
MOUTH_BG = np.tile(np.array(WHITE, np.uint8), (16, 24, 1))
mx, LOBE = 11.5, (4.9, 6.5)
STROKE = int(2.4 * S)


def mouth_frame(kind):
    opening = {'small': (3.5, 2.6), 'mid': (6, 4.2), 'wide': (8.5, 6)}.get(kind)

    def draw(c):
        if opening:                                                                   # open: ONE mouth, a rounded bag (the closed lobes are gone)
            rx, ry = opening
            cv2.ellipse(c, pt(mx, 1.8 + ry), ax(rx + 1.1, ry + 1.0), 0, 0, 360, K[0], -1)
            return
        for ox in (-LOBE[0], LOBE[0]):                                               # the ":3" cat mouth, two round lobes
            cv2.ellipse(c, pt(mx + ox, 1.2), ax(*LOBE), 0, 0, 180, K[0], STROKE)
    f = frame(draw, MOUTH_PAL, MOUTH_BG)
    if opening:                                                                       # the inside, painted after snapping
        rx, ry = opening
        cv2.ellipse(f, (int(round(mx)), int(round(1.8 + ry))), (int(rx), int(ry)), 0, 0, 360, MOUTH_IN[0] + (255,), -1)
        if kind != 'small':
            cv2.ellipse(f, (int(round(mx)), int(round(1.8 + ry * 1.45))), (int(rx - 2.5), max(1, int(ry * 0.45))), 0, 0, 360, MOUTH_IN[2] + (255,), -1)
    return f


MOUTHS = {48: 'closed', 72: 'small', 96: 'mid', 120: 'wide'}
for x, kind in MOUTHS.items():
    t[16:32, x:x + 24] = mouth_frame(kind)
t[24:40, 0:24] = mouth_frame('closed')

print(b.save())
print('verts', len(verts), 'faces', len(faces), 'mmd bytes', os.path.getsize(os.path.join(OUT, 'YukimiBotamon.MMD')))
for r in range(3):
    print('row', r, 'colours', len(set(b.tim.pal[r]) - {0}))
