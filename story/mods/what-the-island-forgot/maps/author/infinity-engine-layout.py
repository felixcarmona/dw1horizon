#!/usr/bin/env python3
"""Authoring of the Infinity Engine room (screen 312, files INFE01; the dark state 313 shares it), run by hand (needs
numpy, cv2, torch and Segment Anything): the circuit floor is segmented from our art itself (SAM on the
full-resolution picture, positive points on the floor, negative points on the walls, the consoles, the door frame and
the passage), the six consoles are blocked by boxes traced on the art. Exits: the band at the bottom edge (south, to
Megadramon's screen) and the foot of the dark passage at the back left (north, to MetalGreymon's screen). Writes
maps/infinity-engine-data.json (camera, collision, exits) for the build-time recipe maps/infinity-engine.py, and
OUT_DIR/INFE01-zones.png.

    SAM_CHECKPOINT=path/to/sam_vit_h_4b8939.pth python3 author/infinity-engine-layout.py OUT_DIR
"""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import json, os, sys
import numpy as np, cv2, torch
from tools.image import Image
from tools.maps.sam import sam_model_registry, SamPredictor
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from mapbase import base_map, Cam, MOD, check_arrivals
from maps import reach

ART_FULL = os.path.join(MOD, 'art', 'full', 'infinity-engine-2304x1856.png')   # the 768x640 art is its middle 6:5
ART = os.path.join(MOD, 'art', 'infinity-engine.png')
DATA = os.path.join(MOD, 'maps', 'infinity-engine-data.json')
CHECKPOINT = os.environ.get('SAM_CHECKPOINT', os.path.join(MOD, '..', '..', '..', 'build', 'new-maps', 'models', 'sam_vit_h_4b8939.pth'))
CAMERA = (11270, 51)                                    # MGEN10's: eye 11270 from the look-at point, 51 degrees down
PROJECTION = 927
W, H = 768, 640
POS = [(384, 400), (250, 300), (520, 300), (384, 560), (200, 500), (560, 500), (300, 230), (470, 230), (384, 300), (150, 600), (600, 600), (384, 210)]
NEG = [(384, 60), (80, 100), (690, 100), (384, 130), (205, 100), (170, 240), (130, 315), (40, 510), (595, 240), (645, 320), (700, 470), (20, 200), (750, 200)]
CONSOLES = [(140, 212, 204, 265), (90, 281, 169, 350), (0, 426, 90, 600), (560, 212, 629, 265), (605, 281, 689, 366), (645, 426, 768, 520)]   # traced on the art
EXIT_N = (172, 183, 247, 212)                           # box: the floor at the foot of the dark passage, back left
EXIT_S_ROWS = range(86, 100); EXIT_S_HALF_WIDTH = 700   # the bottom band
EXITS = [
    {'warp': 0, 'target': (254, 0), 'spawn_px': (384, 592), 'rotation': 0},      # from Megadramon's screen: facing into the hall
    {'warp': 1, 'target': (222, 0), 'spawn_px': (236, 246), 'rotation': 2048},   # from MetalGreymon's screen: out of the passage, facing south (the floor's left edge is at x 213 there)
]


def main(out):
    os.makedirs(out, exist_ok=True)
    full = Image.open(ART_FULL).convert('RGB'); w0, h0 = full.size; ww = round(h0 * 6 / 5); x0 = (w0 - ww) // 2
    im = np.array(full.crop((x0, 0, x0 + ww, h0))); sx, sy = ww / W, h0 / H
    cached = os.path.join(out, 'INFE01-sam.png')
    if os.environ.get('SAM_CACHE') and os.path.exists(cached):
        floor = (np.array(Image.open(cached).convert('L')) > 127).astype(np.uint8); score = 0.0; print('SAM mask from cache')
    else:
        torch.set_num_threads(16)
        pred = SamPredictor(sam_model_registry['vit_h'](checkpoint=CHECKPOINT)); pred.set_image(im)
        pts = np.array([[x * sx, y * sy] for x, y in POS + NEG]); lab = np.array([1] * len(POS) + [0] * len(NEG))
        masks, scores, _ = pred.predict(point_coords=pts, point_labels=lab, multimask_output=True)
        mk = masks[int(np.argmax(scores))].astype(np.float32); score = float(scores.max())
        floor = (cv2.resize(mk, (W, H), interpolation=cv2.INTER_AREA) > 0.5).astype(np.uint8)
        Image.fromarray(floor * 255).save(cached)
    floor = cv2.morphologyEx(floor, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    n, lbl, st, _ = cv2.connectedComponentsWithStats(floor)
    if n > 1: floor = (lbl == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(1 - floor)
    for i in range(1, n):
        x, y, w, h = st[i, :4]
        if x > 0 and y > 0 and x + w < W and y + h < H and st[i, cv2.CC_STAT_AREA] < 3000: floor[lbl == i] = 1
    for bx0, by0, bx1, by1 in CONSOLES: floor[by0:by1, bx0:bx1] = 0
    print(f'floor score {score:.3f}, floor pixels {int(floor.sum())}')
    Image.fromarray(floor * 255).save(os.path.join(out, 'INFE01-floor.png'))

    m = base_map('MGEN10', *CAMERA); m.projection = PROJECTION; cam = Cam(m)
    col = [0x80] * 10000
    nx0, ny0, nx1, ny1 = EXIT_N
    for tx, tz, u, v in cam.tiles():
        if u is None or not (0 <= u < W and 0 <= v < H): continue
        if floor[v, u]:
            col[tz * 100 + tx] = 0
            if tz in EXIT_S_ROWS and abs((tx - 50) * 100 + 50) <= EXIT_S_HALF_WIDTH: col[tz * 100 + tx] = 110
            if nx0 <= u <= nx1 and ny0 <= v <= ny1: col[tz * 100 + tx] = 111
    m.collision = col
    for e in EXITS:
        x, z = cam.world(*e['spawn_px']); e['spawn_world'] = (x, z)
        m.warps[e['warp']].update({'x': x, 'z': z, 'rotation': e['rotation'], 'targetMap': e['target'][0], 'targetExit': e['target'][1]})
    check_arrivals(m, 'INFE01')
    R = reach.from_spawn_coordinates(m, starts=[EXITS[0]['spawn_world']])
    for e in EXITS:
        x, z = e['spawn_world']
        if (round(x / 10) * 10, round(z / 10) * 10) not in R: sys.exit(f'the spawn of warp {e["warp"]} at {x},{z} (px {e["spawn_px"]}) is not reachable from the south arrival')
    for k in (110, 111):
        tiles = [(i % 100, i // 100) for i, c in enumerate(col) if c == k]
        if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in tiles for dx in (-50, 0, 50) for dz in (-50, 0, 50)): sys.exit(f'no exit tile of value {k} is reachable')
    json.dump({'camera': list(CAMERA), 'projection': PROJECTION, 'collision': col, 'warps': m.warps}, open(DATA, 'w'))
    print(f'INFE01: free tiles {col.count(0)}, exit tiles {col.count(110)} south + {col.count(111)} north, reach {len(R)}')
    bg = np.array(Image.open(ART).convert('RGB'))
    rp = np.zeros((H, W), np.uint8); ex = np.zeros((H, W), np.uint8)
    for x, z in R:
        p = cam.pixel(x, z)
        if p and 0 <= p[0] < W and 0 <= p[1] < H: rp[p[1], p[0]] = 1
    for tx, tz, u, v in cam.tiles():
        if u is not None and 110 <= col[tz * 100 + tx] < 120 and 0 <= u < W and 0 <= v < H: cv2.circle(ex, (u, v), 3, 1, -1)
    rp = cv2.dilate(rp, np.ones((3, 3), np.uint8)); ov = bg.copy(); ov[rp > 0] = (0, 200, 0); ov[ex > 0] = (0, 80, 255)
    img = (bg * 0.55 + ov * 0.45).astype(np.uint8)
    for e in EXITS: cv2.circle(img, e['spawn_px'], 4, (255, 255, 255), -1)
    Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, 'INFE01-zones.png'))


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
