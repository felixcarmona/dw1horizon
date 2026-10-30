#!/usr/bin/env python3
"""Authoring of the Bone Field (screen 306, files BONE01), run by hand (needs numpy, cv2, torch and Segment
Anything): the open ground is segmented from our art itself (SAM on the full-resolution picture, positive points on
the cracked earth, negative points on the rim, the skeleton, the wreckage, the craters, the banner and the grave), and
the things standing on the ground are blocked by hand-drawn boxes and ellipses traced on the art (SAM's ground mask
runs under them). Writes maps/bone-field-data.json (camera, collision, exits) for the build-time recipe
maps/bone-field.py, and OUT_DIR/BONE01-zones.png (green: the real reach, blue: exit tiles, white: arrival points).

    SAM_CHECKPOINT=path/to/sam_vit_h_4b8939.pth python3 author/bone-field-layout.py OUT_DIR
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

ART_FULL = os.path.join(MOD, 'art', 'full', 'bone-field-2304x1856.png')   # the 768x640 art is its middle 6:5
ART = os.path.join(MOD, 'art', 'bone-field.png')
DATA = os.path.join(MOD, 'maps', 'bone-field-data.json')
CHECKPOINT = os.environ.get('SAM_CHECKPOINT', os.path.join(MOD, '..', '..', '..', 'build', 'new-maps', 'models', 'sam_vit_h_4b8939.pth'))
CAMERA = (6000, 48)                                     # KODA07's pitch and pixel scale: eye 6000 from the look-at point, 48 degrees down
PROJECTION = 820
W, H = 768, 640
# points in 768x640 pixels: on the cracked earth, and on what is not it
POS = [(384, 320), (300, 200), (500, 150), (400, 450), (600, 560), (200, 560), (120, 300), (650, 420), (380, 600),
       (560, 80), (250, 480), (450, 250), (330, 400), (700, 500), (470, 380)]
NEG = [(200, 100), (100, 160), (330, 70), (700, 250), (740, 330), (480, 300), (210, 430), (200, 330), (610, 470),
       (30, 400), (750, 600), (40, 600), (720, 40), (90, 60), (480, 20), (30, 220), (260, 620), (560, 630)]
BLOCKED = {                                             # traced on the 768x640 art: never walkable
    'skeleton': [(45, 25), (200, 20), (370, 80), (380, 150), (330, 210), (180, 240), (80, 215), (30, 130)],
    'wreckage': [(575, 150), (768, 120), (768, 400), (700, 410), (580, 300)],
    'banner': [(85, 265), (300, 260), (310, 385), (80, 385)],
    'grave': [(545, 405), (680, 405), (690, 530), (545, 530)],
}
ELLIPSES = [((477, 300), 95, 55), ((212, 437), 80, 48)]   # the craters: (centre, rx, ry)
EXIT_S = (280, 616, 480, H)                             # box: the bottom edge, towards the Passage
EXIT_N = (300, 0, 480, 40)                              # box: the gap in the rim at the top, towards the crater (the ground starts at row 22)
EXITS = [
    {'warp': 0, 'target': (305, 1), 'spawn_world': (0, -1950), 'rotation': 0},      # from the Passage: facing into the field
    {'warp': 1, 'target': (86, 1), 'spawn_world': (0, 3850), 'rotation': 2048},    # from the crater: facing into the field
]


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
    floor = cv2.morphologyEx(floor, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    n, lbl, st, _ = cv2.connectedComponentsWithStats(floor)
    if n > 1: floor = (lbl == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(1 - floor)                             # small holes (cracks, pebbles) are ground
    for i in range(1, n):
        x, y, w, h = st[i, :4]
        if x > 0 and y > 0 and x + w < W and y + h < H and st[i, cv2.CC_STAT_AREA] < 2500: floor[lbl == i] = 1
    Image.fromarray(floor * 255).save(os.path.join(out, 'BONE01-ground.png'))
    for poly in BLOCKED.values(): cv2.fillPoly(floor, [np.array(poly, np.int32)], 0)
    for c, rx, ry in ELLIPSES: cv2.ellipse(floor, c, (rx, ry), 0, 0, 360, 0, -1)
    print(f'ground score {scores.max():.3f}, floor pixels {int(floor.sum())}')

    m = base_map('KODA04', *CAMERA); m.projection = PROJECTION; cam = Cam(m)
    col = [0x80] * 10000
    for tx, tz, u, v in cam.tiles():
        if u is None or not (0 <= u < W and 0 <= v < H): continue
        if floor[v, u]:
            col[tz * 100 + tx] = 0
            for k, (bx0, by0, bx1, by1) in enumerate((EXIT_S, EXIT_N)):
                if bx0 <= u <= bx1 and by0 <= v <= by1: col[tz * 100 + tx] = 110 + k
    m.collision = col
    for e in EXITS:
        x, z = e['spawn_world']
        m.warps[e['warp']].update({'x': x, 'z': z, 'rotation': e['rotation'], 'targetMap': e['target'][0], 'targetExit': e['target'][1]})
    check_arrivals(m, 'BONE01')
    R = reach.from_spawn_coordinates(m, starts=[EXITS[0]['spawn_world']])          # from the arrival from the Passage only
    for e in EXITS:
        x, z = e['spawn_world']
        if (round(x / 10) * 10, round(z / 10) * 10) not in R: sys.exit(f'the spawn of warp {e["warp"]} at {x},{z} (px {cam.pixel(x, z)}) is not reachable from the south arrival')
    for k in (110, 111):
        tiles = [(i % 100, i // 100) for i, c in enumerate(col) if c == k]
        if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in tiles for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
            sys.exit(f'no exit tile of value {k} is reachable')
    json.dump({'camera': list(CAMERA), 'projection': PROJECTION, 'collision': col, 'warps': m.warps}, open(DATA, 'w'))
    print(f'BONE01: free tiles {col.count(0)}, exit tiles {col.count(110)} south + {col.count(111)} north, reach {len(R)}')
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
    Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, 'BONE01-zones.png'))


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
