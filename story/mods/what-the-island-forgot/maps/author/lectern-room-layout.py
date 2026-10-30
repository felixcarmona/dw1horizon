#!/usr/bin/env python3
"""Authoring of the lectern room (screen 308, files CRYP02), run by hand (needs numpy, cv2, torch and Segment
Anything): the floor is segmented from our art itself (SAM on the full-resolution picture, positive points on the stone
flags, negative points on the walls, the lectern, the books, the candles and the doorway), the lectern and the space
behind it are blocked by a box traced on the art (the game would draw the player over it), and the doorway in the left
wall is the two westmost free columns of the rows in front of it. Writes maps/lectern-room-data.json (camera, lights,
collision, exits) for the build-time recipe maps/lectern-room.py, and OUT_DIR/CRYP02-zones.png.

    SAM_CHECKPOINT=path/to/sam_vit_h_4b8939.pth python3 author/lectern-room-layout.py OUT_DIR
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

ART_FULL = os.path.join(MOD, 'art', 'full', 'lectern-room-2304x1856.png')
ART = os.path.join(MOD, 'art', 'lectern-room.png')
DATA = os.path.join(MOD, 'maps', 'lectern-room-data.json')
CHECKPOINT = os.environ.get('SAM_CHECKPOINT', os.path.join(MOD, '..', '..', '..', 'build', 'new-maps', 'models', 'sam_vit_h_4b8939.pth'))
CAMERA = (6418, 17)                                     # CHKA01's: eye 6418 from the look-at point, 17 degrees down
PROJECTION = 399
LIGHTS = [{'vx': 100, 'vy': 100, 'vz': 100, 'r': 80, 'g': 80, 'b': 80},      # the Mansion Basement's (CHKA01)
          {'vx': 50, 'vy': 50, 'vz': 50, 'r': 80, 'g': 80, 'b': 80},
          {'vx': 0, 'vy': -10, 'vz': -50, 'r': 20, 'g': 20, 'b': 10}]
W, H = 640, 512
POS = [(320, 460), (150, 420), (500, 430), (200, 330), (450, 330), (120, 300), (560, 300), (400, 270), (240, 270), (320, 390), (600, 480), (40, 480)]
NEG = [(320, 100), (100, 60), (560, 60), (320, 280), (300, 330), (220, 240), (480, 240), (60, 200), (600, 230), (640 - 20, 300),
       (20, 300), (320, 225), (160, 250), (500, 250), (60, 180)]
LECTERN_BOX = (278, 236, 358, 346)                      # traced on the art (the smaller lectern of the edit): the lectern, its book, and the floor behind it (never walkable)
DOOR_POLY = [(8, 306), (138, 306), (138, 262), (60, 262)]      # traced on the art: the floor inside the arched doorway, overlapping the room's floor (SAM's edge is at x about 117: a two-tile gap blocked the way back, found by walking)
DOOR_ROWS = range(57, 68)                               # the rows in front of the doorway's foot (z about -800..-1800: the picture's back wall stands at z about -800, not at the grid's far edge)
DOOR_COLS = 2                                           # the westmost free columns of those rows lead to the corridor
EXITS = [{'warp': 0, 'target': (307, 1), 'rotation': 1024}]   # from the corridor: facing +X, into the room


def main(out):
    os.makedirs(out, exist_ok=True)
    im = np.array(Image.open(ART_FULL).convert('RGB')); h0, w0 = im.shape[:2]; sx, sy = w0 / W, h0 / H
    torch.set_num_threads(16)
    pred = SamPredictor(sam_model_registry['vit_h'](checkpoint=CHECKPOINT)); pred.set_image(im)
    pts = np.array([[x * sx, y * sy] for x, y in POS + NEG]); lab = np.array([1] * len(POS) + [0] * len(NEG))
    masks, scores, _ = pred.predict(point_coords=pts, point_labels=lab, multimask_output=True)
    mk = masks[int(np.argmax(scores))].astype(np.float32)
    floor = (cv2.resize(mk, (W, H), interpolation=cv2.INTER_AREA) > 0.5).astype(np.uint8)
    Image.fromarray(floor * 255).save(os.path.join(out, 'CRYP02-sam.png'))
    floor = cv2.morphologyEx(floor, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    n, lbl, st, _ = cv2.connectedComponentsWithStats(floor)
    if n > 1: floor = (lbl == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(1 - floor)
    for i in range(1, n):
        x, y, w, h = st[i, :4]
        if x > 0 and y > 0 and x + w < W and y + h < H and st[i, cv2.CC_STAT_AREA] < 1500: floor[lbl == i] = 1
    cv2.fillPoly(floor, [np.array(DOOR_POLY, np.int32)], 1)                     # the doorway's own floor (dark, SAM leaves it out)
    bx0, by0, bx1, by1 = LECTERN_BOX; floor[by0:by1, bx0:bx1] = 0
    print(f'floor score {scores.max():.3f}, floor pixels {int(floor.sum())}')
    Image.fromarray(floor * 255).save(os.path.join(out, 'CRYP02-floor.png'))

    m = base_map('LEOM01', *CAMERA); m.projection = PROJECTION; m.lights = LIGHTS; cam = Cam(m)
    col = [0x80] * 10000
    for tx, tz, u, v in cam.tiles():
        if u is None or not (0 <= u < W and 0 <= v < H): continue
        if floor[v, u]: col[tz * 100 + tx] = 0
    west = []
    for tz in DOOR_ROWS:
        free = [tx for tx in range(100) if col[tz * 100 + tx] == 0]
        if free:
            for tx in free[:DOOR_COLS]: col[tz * 100 + tx] = 110
            west.append(free[0])
    wx = int(np.median(west)); mid = DOOR_ROWS[len(DOOR_ROWS) // 2]
    spawn = ((wx + 9 - 50) * 100 + 50, (49 - mid) * 100 + 50)                  # nine columns in from the doorway (on the room's floor), at the door's middle row
    m.collision = col
    e = EXITS[0]; m.warps[0].update({'x': spawn[0], 'z': spawn[1], 'rotation': e['rotation'], 'targetMap': e['target'][0], 'targetExit': e['target'][1]})
    check_arrivals(m, 'CRYP02')
    R = reach.from_spawn_coordinates(m, starts=[spawn])
    tiles = [(i % 100, i // 100) for i, c in enumerate(col) if c == 110]
    if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in tiles for dx in (-50, 0, 50) for dz in (-50, 0, 50)): sys.exit('no door tile is reachable')
    json.dump({'camera': list(CAMERA), 'projection': PROJECTION, 'lights': LIGHTS, 'collision': col, 'warps': m.warps}, open(DATA, 'w'))
    print(f'CRYP02: free tiles {col.count(0)}, door tiles {col.count(110)} (west column {wx}), arrival {spawn} px {cam.pixel(*spawn)}, reach {len(R)}')
    bg = np.array(Image.open(ART).convert('RGB'))
    rp = np.zeros((H, W), np.uint8); ex = np.zeros((H, W), np.uint8)
    for x, z in R:
        p = cam.pixel(x, z)
        if p and 0 <= p[0] < W and 0 <= p[1] < H: rp[p[1], p[0]] = 1
    for tx, tz, u, v in cam.tiles():
        if u is not None and 110 <= col[tz * 100 + tx] < 120 and 0 <= u < W and 0 <= v < H: cv2.circle(ex, (u, v), 3, 1, -1)
    rp = cv2.dilate(rp, np.ones((3, 3), np.uint8)); ov = bg.copy(); ov[rp > 0] = (0, 200, 0); ov[ex > 0] = (0, 80, 255)
    img = (bg * 0.55 + ov * 0.45).astype(np.uint8)
    cv2.circle(img, cam.pixel(*spawn), 4, (255, 255, 255), -1)
    Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, 'CRYP02-zones.png'))


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
