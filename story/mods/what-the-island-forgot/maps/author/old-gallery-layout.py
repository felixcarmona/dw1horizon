#!/usr/bin/env python3
"""Authoring of the Old Gallery (screen 315, files GALL01), run by hand (needs numpy, cv2): the gallery's floor
is a polygon traced on our art (SAM, tried first, took only the rails by the stair: the gravel, the sleepers and the
rock fall are one texture to it), minus what stands on it, traced too (the ore cart, the pick and the bucket, the
fallen timber at the left, the rock fall at the lower right). Writes maps/old-gallery-data.json (camera, collision,
the exit) for the build-time recipe maps/old-gallery.py (the second exit, at the rock fall, is the Galleries arc's: 337), and OUT_DIR/GALL01-zones.png (green: the real reach, blue:
exit tiles, white: the arrival).

    python3 author/old-gallery-layout.py OUT_DIR
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

ART = os.path.join(MOD, 'art', 'old-gallery.png')
DATA = os.path.join(MOD, 'maps', 'old-gallery-data.json')
CAMERA = (6500, 42)                                     # TUNN04's family: eye 6500 from the look-at point, 42 degrees down
PROJECTION = 772
W, H = 640, 512
FLOOR = [(50, 183), (165, 176), (300, 198), (392, 243), (442, 288), (472, 378), (448, 430), (402, 446), (332, 470),
         (302, 512), (212, 512), (128, 330), (58, 296), (40, 240)]                            # the gravel floor with the rails, traced on the 640x512 art
BLOCKED = {
    'cart': [(200, 203), (318, 203), (322, 302), (205, 302)],
    'tools': [(315, 195), (395, 195), (395, 275), (315, 275)],                               # the pick and the bucket against the right wall
    'beam': [(60, 285), (125, 292), (240, 470), (215, 495), (60, 340)],                     # the fallen timber at the left
    'rock-fall': [(430, 290), (640, 280), (640, 512), (290, 512), (330, 470), (400, 440), (445, 430), (470, 380)],
}
EXIT_STAIR = (45, 176, 165, 212)                        # box: the foot of the stair up to Drimogemon's residence (TUNN04)
EXIT_FALL = (290, 318, 368, 394)                        # box: the gap in the rock fall where the rails go into the dark (art v2, 2026-10-22): the Galleries arc (337)
EXITS = [
    {'warp': 0, 'target': (27, 1), 'spawn_px': (135, 262), 'face_px': (300, 380)},        # from the residence: at the stair's foot, facing down the gallery
    {'warp': 1, 'target': (337, 0), 'spawn_px': (255, 328), 'face_px': (150, 260)},       # from the Mine Head: out of the gap, facing back up the gallery
]


def main(out):
    os.makedirs(out, exist_ok=True)
    floor = np.zeros((H, W), np.uint8); cv2.fillPoly(floor, [np.array(FLOOR, np.int32)], 1)
    for poly in BLOCKED.values(): cv2.fillPoly(floor, [np.array(poly, np.int32)], 0)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(floor)
    if n > 1: floor = (lbl == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    print(f'floor pixels {int(floor.sum())}')

    m = base_map('TUNN04', *CAMERA); m.projection = PROJECTION; cam = Cam(m)
    col = [0x80] * 10000
    for tx, tz, u, v in cam.tiles():
        if u is None or not (0 <= u < W and 0 <= v < H): continue
        if floor[v, u]:
            col[tz * 100 + tx] = 0
            for k, (bx0, by0, bx1, by1) in enumerate((EXIT_STAIR, EXIT_FALL)):
                if bx0 <= u <= bx1 and by0 <= v <= by1: col[tz * 100 + tx] = 110 + k
    m.collision = col
    for e in EXITS:
        x, z = cam.world(*e['spawn_px']); e['spawn_world'] = (x, z)
        m.warps[e['warp']].update({'x': x, 'z': z, 'rotation': cam.rotation((x, z), cam.world(*e['face_px'])),
                                   'targetMap': e['target'][0], 'targetExit': e['target'][1]})
    check_arrivals(m, 'GALL01')
    R = reach.from_spawn_coordinates(m, starts=[EXITS[0]['spawn_world']])
    for e in EXITS:
        tiles = [(i % 100, i // 100) for i, c in enumerate(col) if c == 110 + e['warp']]
        if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in tiles for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
            sys.exit(f'no exit tile of warp {e["warp"]} is reachable')
    json.dump({'camera': list(CAMERA), 'projection': PROJECTION, 'collision': col, 'warps': m.warps}, open(DATA, 'w'))
    print(f'GALL01: free tiles {col.count(0)}, exit tiles {sum(1 for c in col if 110 <= c < 120)}, reach {len(R)}, '
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
    Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, 'GALL01-zones.png'))


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
