#!/usr/bin/env python3
"""Authoring of the Wall of Hearts (screen 310, files VALT01; the melted state 311 shares it), run by hand (needs numpy,
cv2, torch and Segment Anything): the circuit floor is segmented from our art itself (SAM on the full-resolution
picture, positive points on the floor, negative points on the ice wall and the side walls). The only exit is the band at
the bottom edge where the floor leaves the picture towards the hidden hall. Writes maps/wall-of-hearts-data.json
(camera, collision, exits) for the build-time recipe maps/wall-of-hearts.py, and OUT_DIR/VALT01-zones.png.

    SAM_CHECKPOINT=path/to/sam_vit_h_4b8939.pth python3 author/wall-of-hearts-layout.py OUT_DIR
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

ART_FULL = os.path.join(MOD, 'art', 'full', 'wall-of-hearts-2304x1856.png')   # the 768x640 art is its middle 6:5
ART = os.path.join(MOD, 'art', 'wall-of-hearts.png')
DATA = os.path.join(MOD, 'maps', 'wall-of-hearts-data.json')
CHECKPOINT = os.environ.get('SAM_CHECKPOINT', os.path.join(MOD, '..', '..', '..', 'build', 'new-maps', 'models', 'sam_vit_h_4b8939.pth'))
CAMERA = (7224, 62)                                     # ICSA08's: eye 7224 from the look-at point, 62 degrees down
PROJECTION = 927
W, H = 768, 640
POS = [(384, 300), (190, 350), (580, 350), (384, 500), (140, 560), (630, 560), (384, 610), (250, 280), (520, 280), (100, 450), (670, 450)]
NEG = [(384, 100), (90, 150), (690, 150), (30, 400), (740, 400), (20, 600), (750, 600), (384, 20), (60, 250), (710, 250)]
FAR_BAND = [(96, 142), (672, 142), (690, 252), (78, 252)]   # traced on the art: the floor's far band at the wall's foot (brighter glow, SAM leaves it out); the walk stopped at z 650
EXIT_ROWS = range(71, 100)                              # the bottom band: rows 71 and beyond (row 73 is the bottom edge)
EXIT_HALF_WIDTH = 850                                   # ...within +-850 units of the centre (the opening the guide gave)
EXITS = [{'warp': 0, 'target': (104, 1), 'spawn_world': (0, -1850), 'rotation': 0}]   # from the hidden hall: row 68, facing the ice wall


def main(out):
    os.makedirs(out, exist_ok=True)
    full = Image.open(ART_FULL).convert('RGB'); w0, h0 = full.size; ww = round(h0 * 6 / 5); x0 = (w0 - ww) // 2
    im = np.array(full.crop((x0, 0, x0 + ww, h0))); sx, sy = ww / W, h0 / H
    torch.set_num_threads(16)
    pred = SamPredictor(sam_model_registry['vit_h'](checkpoint=CHECKPOINT)); pred.set_image(im)
    pts = np.array([[x * sx, y * sy] for x, y in POS + NEG]); lab = np.array([1] * len(POS) + [0] * len(NEG))
    masks, scores, _ = pred.predict(point_coords=pts, point_labels=lab, multimask_output=True)
    mk = masks[int(np.argmax(scores))].astype(np.float32)
    floor = (cv2.resize(mk, (W, H), interpolation=cv2.INTER_AREA) > 0.5).astype(np.uint8)
    Image.fromarray(floor * 255).save(os.path.join(out, 'VALT01-sam.png'))
    floor = cv2.morphologyEx(floor, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    n, lbl, st, _ = cv2.connectedComponentsWithStats(floor)
    if n > 1: floor = (lbl == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(1 - floor)
    for i in range(1, n):
        x, y, w, h = st[i, :4]
        if x > 0 and y > 0 and x + w < W and y + h < H and st[i, cv2.CC_STAT_AREA] < 3000: floor[lbl == i] = 1
    cv2.fillPoly(floor, [np.array(FAR_BAND, np.int32)], 1)
    print(f'floor score {scores.max():.3f}, floor pixels {int(floor.sum())}')
    Image.fromarray(floor * 255).save(os.path.join(out, 'VALT01-floor.png'))

    m = base_map('ICSA08', *CAMERA); m.projection = PROJECTION; cam = Cam(m)
    col = [0x80] * 10000
    for tx, tz, u, v in cam.tiles():
        if u is None or not (0 <= u < W and 0 <= v < H): continue
        if floor[v, u]:
            col[tz * 100 + tx] = 0
            if tz in EXIT_ROWS and abs((tx - 50) * 100 + 50) <= EXIT_HALF_WIDTH: col[tz * 100 + tx] = 110
    m.collision = col
    for e in EXITS:
        x, z = e['spawn_world']
        m.warps[e['warp']].update({'x': x, 'z': z, 'rotation': e['rotation'], 'targetMap': e['target'][0], 'targetExit': e['target'][1]})
    check_arrivals(m, 'VALT01')
    R = reach.from_spawn_coordinates(m, starts=[EXITS[0]['spawn_world']])
    tiles = [(i % 100, i // 100) for i, c in enumerate(col) if c == 110]
    if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in tiles for dx in (-50, 0, 50) for dz in (-50, 0, 50)): sys.exit('no exit tile is reachable')
    json.dump({'camera': list(CAMERA), 'projection': PROJECTION, 'collision': col, 'warps': m.warps}, open(DATA, 'w'))
    print(f'VALT01: free tiles {col.count(0)}, exit tiles {col.count(110)}, reach {len(R)}')
    bg = np.array(Image.open(ART).convert('RGB'))
    rp = np.zeros((H, W), np.uint8); ex = np.zeros((H, W), np.uint8)
    for x, z in R:
        p = cam.pixel(x, z)
        if p and 0 <= p[0] < W and 0 <= p[1] < H: rp[p[1], p[0]] = 1
    for tx, tz, u, v in cam.tiles():
        if u is not None and 110 <= col[tz * 100 + tx] < 120 and 0 <= u < W and 0 <= v < H: cv2.circle(ex, (u, v), 4, 1, -1)
    rp = cv2.dilate(rp, np.ones((3, 3), np.uint8)); ov = bg.copy(); ov[rp > 0] = (0, 200, 0); ov[ex > 0] = (0, 80, 255)
    img = (bg * 0.55 + ov * 0.45).astype(np.uint8)
    for e in EXITS: cv2.circle(img, cam.pixel(*e['spawn_world']), 4, (255, 255, 255), -1)
    Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, 'VALT01-zones.png'))


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
