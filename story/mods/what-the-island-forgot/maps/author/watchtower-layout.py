#!/usr/bin/env python3
"""Authoring of the watchtower (screen 328, files SEAM06), run by hand (needs numpy, cv2): the floor is a polygon
traced on our art (all the block floor between the walls, the dais included), minus the lens's tripod and the two
perches with their droppings. The doorway at the bottom edge is the only exit. Writes maps/watchtower-data.json for
the build-time recipe maps/watchtower.py, and OUT_DIR/SEAM06-zones.png.

    python3 author/watchtower-layout.py OUT_DIR
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

ART = os.path.join(MOD, 'art', 'watchtower.png')
DATA = os.path.join(MOD, 'maps', 'watchtower-data.json')
CAMERA = (7000, 45)                                     # the pass's eye at 45 degrees down (MAYO04B's structure)
PROJECTION = 1000
W, H = 768, 640
FLOOR = [(130, 105), (640, 105), (700, 300), (740, 640), (30, 640), (60, 300)]
BLOCKED = {
    'tripod': [(330, 230), (450, 230), (450, 335), (330, 335)],
    'perch-left': [(0, 110), (130, 110), (135, 440), (60, 470), (20, 420)],
    'perch-right': [(640, 110), (768, 110), (768, 450), (660, 440), (635, 350)],
}
EXIT_S = (300, 616, 470, 640)                           # box: the doorway at the bottom, back down the stair (327)
EXITS = [
    {'warp': 0, 'target': (327, 2), 'spawn_px': (385, 580), 'face_px': (385, 300)},     # from the gallery: inside the doorway, facing the dais
]


def main(out):
    os.makedirs(out, exist_ok=True)
    floor = np.zeros((H, W), np.uint8); cv2.fillPoly(floor, [np.array(FLOOR, np.int32)], 1)
    for poly in BLOCKED.values(): cv2.fillPoly(floor, [np.array(poly, np.int32)], 0)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(floor)
    if n > 1: floor = (lbl == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    print(f'floor pixels {int(floor.sum())}')
    m = base_map('MAYO04B', *CAMERA); m.projection = PROJECTION; cam = Cam(m)
    col = [0x80] * 10000
    for tx, tz, u, v in cam.tiles():
        if u is None or not (0 <= u < W and 0 <= v < H): continue
        if floor[v, u]:
            col[tz * 100 + tx] = 0
            bx0, by0, bx1, by1 = EXIT_S
            if bx0 <= u <= bx1 and by0 <= v <= by1: col[tz * 100 + tx] = 110
    m.collision = col
    for e in EXITS:
        x, z = cam.world(*e['spawn_px']); e['spawn_world'] = (x, z)
        m.warps[e['warp']].update({'x': x, 'z': z, 'rotation': cam.rotation((x, z), cam.world(*e['face_px'])),
                                   'targetMap': e['target'][0], 'targetExit': e['target'][1]})
    check_arrivals(m, 'SEAM06')
    R = reach.from_spawn_coordinates(m, starts=[EXITS[0]['spawn_world']])
    tiles = [(i % 100, i // 100) for i, c in enumerate(col) if c == 110]
    if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in tiles for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
        sys.exit('no exit tile of the doorway is reachable')
    json.dump({'camera': list(CAMERA), 'projection': PROJECTION, 'collision': col, 'warps': m.warps}, open(DATA, 'w'))
    print(f'SEAM06: free tiles {col.count(0)}, exit tiles {col.count(110)}, reach {len(R)}, spawn {EXITS[0]["spawn_world"]} rot {m.warps[0]["rotation"]}')
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
    Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, 'SEAM06-zones.png'))


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
