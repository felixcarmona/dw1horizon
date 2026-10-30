#!/usr/bin/env python3
"""Authoring of the Lake Terrace (screen 316, files LAKE01), run by hand (needs numpy, cv2): the terrace's floor
is a polygon traced on our art (one clean slab of rock: the drop to the water, the cliff and the steps are its edges),
plus the top of the steps at the right edge, which lead down the cleft to the beach. Writes maps/lake-terrace-data.json
(camera, collision, the exit) for the build-time recipe maps/lake-terrace.py, and OUT_DIR/LAKE01-zones.png (green: the
real reach, blue: exit tiles, white: the arrival).

    python3 author/lake-terrace-layout.py OUT_DIR
"""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import json, os, sys
import numpy as np, cv2
from tools.image import Image
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from mapbase import base_map, Cam, MOD, check_arrivals
from maps import reach

ART = os.path.join(MOD, 'art', 'lake-terrace.png')
DATA = os.path.join(MOD, 'maps', 'lake-terrace-data.json')
CAMERA = (7000, 45)                                     # eye 7000 from the look-at point, 45 degrees down (MAYO01's lens)
PROJECTION = 927
W, H = 768, 640
FLOOR = [(140, 210), (740, 212), (700, 300), (690, 400), (640, 430), (620, 520), (600, 600), (560, 640), (300, 640),
         (285, 600), (230, 520), (185, 440), (150, 360), (105, 280), (95, 240)]                # the terrace's top, traced on the 768x640 art
STEPS = [(620, 420), (700, 420), (768, 480), (768, 590), (700, 590), (610, 520)]              # the steps down the cleft, at the right edge
EXIT_E = (690, 470, 768, 590)                           # box: the steps, towards the beach (MAYO10)
EXITS = [
    {'warp': 0, 'target': (8, 1), 'spawn_px': (640, 470), 'face_px': (400, 400)},         # from the beach: at the top of the steps, facing the terrace
]


def main(out):
    os.makedirs(out, exist_ok=True)
    floor = np.zeros((H, W), np.uint8)
    cv2.fillPoly(floor, [np.array(FLOOR, np.int32)], 1); cv2.fillPoly(floor, [np.array(STEPS, np.int32)], 1)
    print(f'floor pixels {int(floor.sum())}')
    m = base_map('MAYO04B', *CAMERA); m.projection = PROJECTION; cam = Cam(m)
    col = [0x80] * 10000
    for tx, tz, u, v in cam.tiles():
        if u is None or not (0 <= u < W and 0 <= v < H): continue
        if floor[v, u]:
            col[tz * 100 + tx] = 0
            bx0, by0, bx1, by1 = EXIT_E
            if bx0 <= u <= bx1 and by0 <= v <= by1: col[tz * 100 + tx] = 110
    m.collision = col
    for e in EXITS:
        x, z = cam.world(*e['spawn_px']); e['spawn_world'] = (x, z)
        m.warps[e['warp']].update({'x': x, 'z': z, 'rotation': cam.rotation((x, z), cam.world(*e['face_px'])),
                                   'targetMap': e['target'][0], 'targetExit': e['target'][1]})
    check_arrivals(m, 'LAKE01')
    R = reach.from_spawn_coordinates(m, starts=[EXITS[0]['spawn_world']])
    tiles = [(i % 100, i // 100) for i, c in enumerate(col) if c == 110]
    if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in tiles for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
        sys.exit('no exit tile of the steps is reachable')
    json.dump({'camera': list(CAMERA), 'projection': PROJECTION, 'collision': col, 'warps': m.warps}, open(DATA, 'w'))
    print(f'LAKE01: free tiles {col.count(0)}, exit tiles {col.count(110)}, reach {len(R)}, '
          f'spawn {EXITS[0]["spawn_world"]} rot {m.warps[0]["rotation"]}')
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
    Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, 'LAKE01-zones.png'))


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
