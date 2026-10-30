#!/usr/bin/env python3
"""Authoring of the Mine Head (screen 337, files MINE01, the first screen of the Galleries arc), run by hand (needs
numpy, cv2): the hall's floor and its four galleries are a polygon traced on our art (896x640), minus what stands
on it (the shaft pit with the wrecked cage, the crates and the rope at the left, the lantern post by the entry gallery,
the pick at the lower right, the crate at the right). Four exits: the entry gallery at the bottom edge (from the Old
Gallery's rock fall, 315), the north gallery at the top edge (338), the west gallery at the left edge (341), the east
gallery at the right edge (344). Writes maps/mine-head-data.json (camera, collision, the exits) for the build-time
recipe maps/mine-head.py, and OUT_DIR/MINE01-zones.png (green: the real reach, blue: exit tiles, white: arrivals).

    python3 author/mine-head-layout.py OUT_DIR
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

ART = os.path.join(MOD, 'art', 'mine-head.png')
DATA = os.path.join(MOD, 'maps', 'mine-head-data.json')
CAMERA = (6500, 42)                                     # the Drill Tunnel family: eye 6500 from the look-at point, 42 degrees down
PROJECTION = 1081                                       # TUNN03's (896 wide)
W, H = 896, 640
FLOOR = [(365, 0), (455, 0), (500, 165), (640, 150), (720, 175), (805, 200), (896, 275), (896, 415), (790, 440), (740, 470),
         (700, 520), (650, 560), (615, 640), (330, 640), (300, 560), (240, 490), (215, 480), (70, 480), (0, 440), (0, 335),
         (0, 190), (70, 190), (165, 215), (300, 215), (330, 170)]                          # the hall and the four galleries, traced on the 896x640 art
BLOCKED = {
    'pit': [(500, 200), (560, 185), (640, 190), (700, 175), (722, 230), (722, 302), (640, 312), (560, 308), (503, 282)],   # the shaft, its rim and the cage
    'crates-left': [(65, 325), (165, 325), (165, 485), (65, 485)],
    'rope-left': [(145, 418), (218, 418), (218, 475), (145, 475)],
    'rope-top': [(195, 200), (250, 200), (250, 236), (195, 236)],
    'lantern-post': [(295, 440), (347, 440), (347, 578), (295, 578)],
    'pick': [(598, 556), (662, 556), (662, 606), (598, 606)],
    'crate-right': [(735, 415), (802, 415), (802, 487), (735, 487)],
    'top-post': [(440, 40), (476, 40), (476, 112), (440, 112)],
}
EXIT_BOXES = {0: (335, 600, 610, 640), 1: (365, 0, 455, 45), 2: (0, 190, 40, 335), 3: (856, 275, 896, 415)}   # warp: (x0, y0, x1, y1) px
EXITS = [
    {'warp': 0, 'target': (315, 1), 'spawn_px': (470, 572), 'face_px': (470, 300)},      # from the Old Gallery's rock fall: at the bottom, facing the hall
    {'warp': 1, 'target': (338, 0), 'spawn_px': (410, 62), 'face_px': (410, 300)},       # the north gallery (338): at the top, facing down
    {'warp': 2, 'target': (341, 0), 'spawn_px': (62, 262), 'face_px': (300, 262)},       # the west gallery (341): at the left, facing right
    {'warp': 3, 'target': (344, 0), 'spawn_px': (830, 345), 'face_px': (600, 345)},      # the east gallery (344): at the right, facing left
]


def main(out):
    os.makedirs(out, exist_ok=True)
    floor = np.zeros((H, W), np.uint8); cv2.fillPoly(floor, [np.array(FLOOR, np.int32)], 1)
    for poly in BLOCKED.values(): cv2.fillPoly(floor, [np.array(poly, np.int32)], 0)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(floor)
    if n > 1: floor = (lbl == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    print(f'floor pixels {int(floor.sum())}')

    m = base_map('TUNN02', *CAMERA); m.projection = PROJECTION; cam = Cam(m)
    col = [0x80] * 10000
    for tx, tz, u, v in cam.tiles():
        if u is None or not (0 <= u < W and 0 <= v < H): continue
        if floor[v, u]:
            col[tz * 100 + tx] = 0
            for k, (bx0, by0, bx1, by1) in EXIT_BOXES.items():
                if bx0 <= u <= bx1 and by0 <= v <= by1: col[tz * 100 + tx] = 110 + k
    m.collision = col
    for e in EXITS:
        x, z = cam.world(*e['spawn_px']); e['spawn_world'] = (x, z)
        m.warps[e['warp']].update({'x': x, 'y': 0, 'z': z, 'rotation': cam.rotation((x, z), cam.world(*e['face_px'])),
                                   'targetMap': e['target'][0], 'targetExit': e['target'][1]})
    check_arrivals(m, 'MINE01')
    R = reach.from_spawn_coordinates(m, starts=[EXITS[0]['spawn_world']])
    for e in EXITS:
        tiles = [(i % 100, i // 100) for i, c in enumerate(col) if c == 110 + e['warp']]
        if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in tiles for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
            sys.exit(f'no exit tile of warp {e["warp"]} is reachable from the entry')
    json.dump({'camera': list(CAMERA), 'projection': PROJECTION, 'collision': col, 'warps': m.warps}, open(DATA, 'w'))
    print(f'MINE01: free tiles {col.count(0)}, exit tiles {sum(1 for c in col if 110 <= c < 120)}, reach {len(R)}, '
          + ', '.join(f'warp {e["warp"]} spawn {tuple(round(c) for c in e["spawn_world"])} rot {m.warps[e["warp"]]["rotation"]}' for e in EXITS))
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
    Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, 'MINE01-zones.png'))


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
