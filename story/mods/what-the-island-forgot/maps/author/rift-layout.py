#!/usr/bin/env python3
"""Authoring of the Rift (screen 301, files RIFT01), run by hand (needs numpy, cv2): the old floor of the Great
Canyon under the plateau, with the hundred-year-old human camp. Our art (art/rift.png, Nano Banana Pro with GCAN07's
camera: eye 7000 from the look-at point, 61 degrees down) and our geometry below. The props' cut-outs (rift-masks.npz,
Segment Anything on our art) say where each prop stands: a prop blocks its whole box, and becomes a foreground piece
only if the player could stand behind it (nobody can here: the camp is against the rock).

    python3 author/rift-layout.py OUT_DIR   writes maps/rift-data.json (our collision, exits and pieces: what the build-time
                                            recipe maps/rift.py merges with the disc's structure) and OUT_DIR/RIFT01-zones.png
"""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import json, os, struct, sys
import numpy as np, cv2
from tools.image import Image
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from mapbase import base_map, import_png, Cam, reachable, dwmap, MOD

ART = os.path.join(MOD, 'art', 'rift.png')
MASKS = os.path.join(MOD, 'maps', 'rift-masks.npz')
DATA = os.path.join(MOD, 'maps', 'rift-data.json')
CAMERA = (7000, 61)                                             # GCAN07's: the player is 22 px tall at the centre
W, H = 640, 512
# the clearing: inside the rock walls, off the fern beds at their foot; the camp corner is inside (the props block)
FLOOR = [(300, 96), (360, 98), (400, 100), (450, 92), (530, 95), (580, 110), (598, 160), (598, 225), (565, 250),
         (560, 300), (545, 335), (520, 360), (500, 395), (470, 415), (430, 425), (400, 432), (330, 440), (290, 440),
         (240, 430), (200, 420), (185, 410), (150, 385), (120, 350), (95, 320), (80, 290), (70, 250), (65, 200),
         (45, 185), (28, 186), (28, 148), (60, 148), (90, 140), (120, 138), (200, 136), (240, 118), (275, 132)]
RAMP = [(300, 96), (304, 30), (356, 30), (360, 96)]             # up the ramp (exit 0, north)
OBJECTS = ['lamp-crate', 'back-crate', 'tent', 'cot', 'sign']   # each blocks its whole box
EXITS = [  # tiles (a box, 640 px), the warp slot, its target, the spawn (px) and heading when arriving through it
    {'box': (300, 30, 360, 56), 'warp': 0, 'target': (303, 1), 'spawn': (330, 88), 'rotation': 2048},    # the ramp: the Descent (arriving: at the top of the ramp, walking down)
    {'box': (28, 148, 58, 186), 'warp': 1, 'target': (300, 1), 'spawn': (95, 170), 'rotation': 1024},    # the tunnel: the Engine Room, its east exit
]
BODY_H, BODY_W = 28, 14                                         # the player's on-screen size (px) at this camera


def poly_mask(poly):
    mk = np.zeros((H, W), np.uint8); cv2.fillPoly(mk, [np.array(poly, np.int32)], 1); return mk


def main(out):
    os.makedirs(out, exist_ok=True)
    bg = np.array(Image.open(ART).convert('RGB'))
    m = base_map('OGRE03', *CAMERA); cam = Cam(m)
    sam = np.load(MASKS); floor_sam = sam['_floor'].astype(np.uint8)
    masks, feet = {}, {}
    for name in OBJECTS:
        mk = sam[name].astype(np.uint8) & (1 - floor_sam)
        n, lbl, st, _ = cv2.connectedComponentsWithStats(mk)
        if n > 1:
            big = st[1:, cv2.CC_STAT_AREA].max()
            for i in range(1, n):
                if st[i, cv2.CC_STAT_AREA] < 0.25 * big: mk[lbl == i] = 0
        inv = (1 - mk).astype(np.uint8); ff = np.zeros((H + 2, W + 2), np.uint8); cv2.floodFill(inv, ff, (0, 0), 2); mk[inv == 1] = 1
        masks[name] = mk
        ys, xs = np.nonzero(mk); ft = np.zeros_like(mk); ft[ys.min():ys.max() + 1, xs.min():xs.max() + 1] = 1; feet[name] = ft
    walk = ((poly_mask(FLOOR) > 0) | (poly_mask(RAMP) > 0)).astype(np.uint8)
    walk = cv2.morphologyEx(walk, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    for name in OBJECTS: walk[feet[name] > 0] = 0

    def needs_layer(name):                                  # a walkable point behind the prop's foot with the body over it
        mk = masks[name]; foot_top = np.nonzero(feet[name])[0].min(); ys, xs = np.nonzero(walk); hits = 0
        for y, x in zip(ys[ys < foot_top][::3], xs[ys < foot_top][::3]):
            if mk[max(y - BODY_H, 0):y, max(x - BODY_W // 2, 0):x + BODY_W // 2].sum() > 40: hits += 1
        return hits > 3
    pieces = [name for name in OBJECTS if needs_layer(name)]

    col = [0x80] * 10000
    for tx, tz, u, v in cam.tiles():
        if u is None or not (0 <= u < W and 0 <= v < H) or not walk[v, u]: continue
        col[tz * 100 + tx] = 0
        for e in EXITS:
            x0, y0, x1, y1 = e['box']
            if x0 <= u <= x1 and y0 <= v <= y1: col[tz * 100 + tx] = 110 + e['warp']
    m.collision = col
    for e in EXITS:
        x, z = cam.world(*e['spawn'])
        m.warps[e['warp']].update({'x': x, 'z': z, 'rotation': e['rotation'], 'targetMap': e['target'][0], 'targetExit': e['target'][1]})

    # foreground pieces (none on this map, kept for the recipe): TIM 0 (texX 256..) then TIM 1, shelf-packed
    if pieces:
        tfs_tmp = os.path.join(out, '_palette.TFS'); import_png('OGRE03', ART, tfs_tmp)
        tfs = dwmap.TfsFile(open(tfs_tmp, 'rb').read()); rq = dwmap.Requant([dwmap.bgr555_to_rgb(c) for c in tfs.cluts[0]], tfs.cluts[0])
        areas = [{'tim': 0, 'tex0': 256}, {'tim': 1, 'tex0': 0}]; shelves, placed = [], []
        for name in sorted(pieces, key=lambda n: -int(masks[n].sum())):
            ys, xs = np.nonzero(masks[name]); x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
            w = x1 - x0 + ((x1 - x0) % 2); h = y1 - y0; fy, fx_ = np.nonzero(feet[name]); ground = (int(fx_.mean()), int(fy.max()))
            for a in areas:
                sh = [s for s in shelves if s['area'] is a]; spot = next((s for s in sh if s['x'] + w <= 256 and h <= s['h']), None)
                if spot is None:
                    ytop = sum(s['h'] for s in sh)
                    if ytop + h <= 256 and w <= 256: spot = {'area': a, 'y': ytop, 'h': h, 'x': 0}; shelves.append(spot)
                if spot is not None: placed.append((name, x0, y0, w, h, ground, a, spot['x'], spot['y'])); spot['x'] += w; break
            else: sys.exit(f'no room in the sprite TIMs for {name}')
        for a in areas:
            raw = bytearray(m.tims[a['tim']]); clut_len = struct.unpack_from('<I', raw, 8)[0]; p = 8 + clut_len + 12
            pix = np.zeros((256, 256), np.uint8)
            for name, x0, y0, w, h, ground, aa, tx, ty in placed:
                if aa is not a: continue
                mk = masks[name][y0:y0 + h, x0:x0 + w]; rgb = bg[y0:y0 + h, x0:x0 + w]
                for yy in range(h):
                    for xx in range(min(w, rgb.shape[1])):
                        pix[ty + yy, tx + xx] = rq(*(int(c) for c in rgb[yy, xx])) if mk[yy, xx] else 0
            raw[p:p + 256 * 256] = pix.tobytes(); m.tims[a['tim']] = bytes(raw)
        di, ii = 8, 1
        for name, x0, y0, w, h, ground, a, tx, ty in placed:
            gx, gz = cam.world(*ground)
            m.sprites[di] = {'texX': a['tex0'] + tx, 'texY': ty, 'width': w, 'height': h, 'x': gx, 'y': 0, 'z': gz, 'clut': -1, 'transparency': 4}
            m.instances[ii] = {'frames': [di, -1, -1, -1, -1, -1, -1, -1], 'times': [0] * 8, 'x': int(x0), 'y': int(y0), 'flag': 0}
            di += 1; ii += 1
    json.dump({'camera': list(CAMERA), 'collision': list(m.collision), 'warps': m.warps, 'sprites': m.sprites,
               'instances': m.instances, 'tims': [list(t) for t in m.tims[:2]] if pieces else []}, open(DATA, 'w'))
    R = reachable(m)
    for e in EXITS:
        x, z = cam.world(*e['spawn'])
        if (round(x / 10) * 10, round(z / 10) * 10) not in R: sys.exit(f'the spawn of warp {e["warp"]} is not reachable')
    print(f'RIFT01: free tiles {col.count(0)}, exit tiles {[col.count(110 + e["warp"]) for e in EXITS]}, pieces {pieces or "none"}, reach {len(R)}')
    # the check image: real reach green, props' boxes red, exits blue, spawns white
    rp = np.zeros((H, W), np.uint8)
    for x, z in R:
        p = cam.pixel(x, z)
        if p and 0 <= p[0] < W and 0 <= p[1] < H: rp[p[1], p[0]] = 1
    rp = cv2.dilate(rp, np.ones((3, 3), np.uint8)); ov = bg.copy(); ov[rp > 0] = (0, 200, 0)
    for name in OBJECTS: ov[feet[name] > 0] = (220, 0, 0)
    for e in EXITS:
        x0, y0, x1, y1 = e['box']; ov[y0:y1, x0:x1] = (0, 80, 255)
    img = (bg * 0.55 + ov * 0.45).astype(np.uint8)
    for e in EXITS: cv2.circle(img, e['spawn'], 4, (255, 255, 255), -1)
    Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, 'RIFT01-zones.png'))


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
