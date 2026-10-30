#!/usr/bin/env python3
"""Authoring of the terraces (screen 332, files OVPS03, 640x768), run by hand (needs numpy, cv2): the floor is a
polygon traced on our art (all the orange ground between the canyon walls, the three terraces and the low ledges
between them included: a ledge a hand high is a step, not a wall), minus the dead trees, the pipe stub, the boulder
with its stones and the rock knobs that reach into the floor. Exits: the top edge (back to the riverbed, 331) and the
bottom edge (on to 333). Writes maps/descent-3-data.json for the build-time recipe maps/descent-3.py, and
OUT_DIR/OVPS03-zones.png.

    python3 author/descent-3-layout.py OUT_DIR
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

ART = os.path.join(MOD, 'art', 'descent-3.png')
DATA = os.path.join(MOD, 'maps', 'descent-3-data.json')
CAMERA = (7000, 52)                                     # zone 3's camera on a tall screen (DGHA01's structure)
PROJECTION = 1000
W, H = 640, 768
FLOOR = [(170, 0), (470, 0), (520, 120), (560, 300), (580, 480), (570, 640), (560, 768), (90, 768), (80, 600), (60, 450), (70, 300), (110, 150)]
BLOCKED = {
    'dead-trees': [(40, 90), (210, 90), (215, 350), (100, 360), (40, 300)],
    'pipe-valve': [(460, 50), (580, 50), (580, 190), (470, 180)],
    'boulder': [(390, 500), (540, 495), (560, 630), (440, 700), (400, 620)],
    'right-bushes': [(470, 180), (580, 190), (580, 320), (500, 320)],
    'right-rocks': [(520, 300), (640, 300), (640, 500), (560, 500)],
    'right-rocks-low': [(560, 620), (640, 620), (640, 768), (560, 768)],
    'left-rocks': [(0, 350), (100, 360), (90, 500), (0, 520)],
    'left-rocks-low': [(0, 520), (90, 520), (120, 700), (60, 768), (0, 768)],
}
EXIT_N = (220, 0, 400, 22)                              # box: the top edge, back to the riverbed (331)
EXIT_S = (160, 744, 500, 768)                           # box: the bottom edge, on to 333 (when it exists)
EXITS = [
    {'warp': 0, 'target': (331, 1), 'spawn_px': (330, 60), 'face_px': (330, 400)},      # from the riverbed: at the top, facing down
    {'warp': 1, 'target': (333, 0), 'spawn_px': (300, 710), 'face_px': (320, 300)},     # from 333: at the bottom, facing up
]


def main(out):
    os.makedirs(out, exist_ok=True)
    floor = np.zeros((H, W), np.uint8); cv2.fillPoly(floor, [np.array(FLOOR, np.int32)], 1)
    for poly in BLOCKED.values(): cv2.fillPoly(floor, [np.array(poly, np.int32)], 0)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(floor)
    if n > 1: floor = (lbl == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    print(f'floor pixels {int(floor.sum())}')
    m = base_map('DGHA01', *CAMERA); m.projection = PROJECTION; cam = Cam(m)
    col = [0x80] * 10000
    for tx, tz, u, v in cam.tiles():
        if u is None or not (0 <= u < W and 0 <= v < H): continue
        if floor[v, u]:
            col[tz * 100 + tx] = 0
            for k, (bx0, by0, bx1, by1) in enumerate((EXIT_N, EXIT_S)):
                if bx0 <= u <= bx1 and by0 <= v <= by1: col[tz * 100 + tx] = 110 + k
    m.collision = col
    for e in EXITS:
        x, z = cam.world(*e['spawn_px']); e['spawn_world'] = (x, z)
        m.warps[e['warp']].update({'x': x, 'z': z, 'rotation': cam.rotation((x, z), cam.world(*e['face_px'])),
                                   'targetMap': e['target'][0], 'targetExit': e['target'][1]})
    check_arrivals(m, 'OVPS03')
    R = reach.from_spawn_coordinates(m, starts=[EXITS[0]['spawn_world']])
    for e in EXITS:
        x, z = e['spawn_world']
        if (round(x / 10) * 10, round(z / 10) * 10) not in R: sys.exit(f'the spawn of warp {e["warp"]} at {x},{z} (px {cam.pixel(x, z)}) is not reachable')
    for k in (110, 111):
        tiles = [(i % 100, i // 100) for i, c in enumerate(col) if c == k]
        if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in tiles for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
            sys.exit(f'no exit tile of value {k} is reachable')
    json.dump({'camera': list(CAMERA), 'projection': PROJECTION, 'collision': col, 'warps': m.warps}, open(DATA, 'w'))
    print(f'OVPS03: free tiles {col.count(0)}, exit tiles {col.count(110)} north + {col.count(111)} south, reach {len(R)}, '
          f'spawns {[(e["spawn_world"], m.warps[e["warp"]]["rotation"]) for e in EXITS]}')
    for name, px in [('enemy a', (330, 300)), ('enemy b', (250, 600)), ('enemy c', (300, 150))]:
        x, z = cam.world(*px); tx, tz = int(x / 100) + 50 - (1 if x < 0 else 0), 49 - int(z / 100) + (1 if z < 0 else 0)
        print(f'  {name} px {px} -> world ({x}, {z}) tile ({tx},{tz}) {"free" if not col[tz * 100 + tx] & 0x80 else "BLOCKED"}')
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
    Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, 'OVPS03-zones.png'))


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
