#!/usr/bin/env python3
"""Authoring of the Passage (screen 305, files PASS01), run by hand (needs numpy, cv2, torch and Segment Anything):
the trail is segmented from our art itself (SAM on the full-resolution picture: the golden dirt, and separately the
grey cracked rock the trail turns into near the top, where the tile grid ends), with positive points on the trail and
negative points on the ferns, the trunks, the stone beside the trail, the spider web and the grey plateau beyond.
Writes maps/passage-data.json (camera, lights, collision, exits) for the build-time recipe maps/passage.py, and
OUT_DIR/PASS01-zones.png (green: the real reach, blue: exit tiles, white: arrival points).

    SAM_CHECKPOINT=path/to/sam_vit_h_4b8939.pth python3 author/passage-layout.py OUT_DIR
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
from mapbase import base_map, Cam, reachable, MOD, check_arrivals

ART_FULL = os.path.join(MOD, 'art', 'full', 'passage-1856x2304.png')   # the 640x768 art is its middle 5:6
ART = os.path.join(MOD, 'art', 'passage.png')
DATA = os.path.join(MOD, 'maps', 'passage-data.json')
CHECKPOINT = os.environ.get('SAM_CHECKPOINT', os.path.join(MOD, '..', '..', '..', 'build', 'new-maps', 'models', 'sam_vit_h_4b8939.pth'))
CAMERA = (4946, 43)                                     # KODA03's: eye 4946 from the look-at point, 43 degrees down
PROJECTION = 618                                        # KODA03's (the same pixel scale: the tamer is the same size)
LIGHTS = [{'vx': 0, 'vy': 100, 'vz': 0, 'r': 255, 'g': 255, 'b': 255},      # the Glacial Region's daylight (KODA03), not
          {'vx': 0, 'vy': -50, 'vz': 70, 'r': 128, 'g': 128, 'b': 128},     # the dim grey light of the donor's region
          {'vx': 1, 'vy': 1, 'vz': -100, 'r': 55, 'g': 55, 'b': 55}]
W, H = 640, 768
# points in 640x768 pixels
DIRT_POS = [(330, 740), (300, 650), (270, 560), (255, 480), (280, 400), (320, 340), (335, 300), (330, 260), (400, 730),
            (250, 520), (300, 450), (360, 700)]
DIRT_NEG = [(100, 500), (80, 300), (150, 700), (60, 650), (550, 500), (500, 350), (600, 250), (560, 700), (450, 600),
            (320, 60), (200, 60), (450, 100), (150, 130), (180, 690), (395, 190), (320, 170), (460, 420), (190, 380)]
ROCK_POS = [(320, 200), (300, 165), (340, 150), (310, 230), (330, 215), (300, 240)]
ROCK_NEG = [(200, 200), (450, 230), (150, 150), (395, 190), (320, 80), (250, 110), (420, 110), (100, 300), (540, 300),
            (265, 150), (430, 170)]
ROCK_BOX = (235, 135, 405, 255)                         # SAM's box prompt: the cracked grey rock between the dirt's end and the plateau
ROCK_BAND = (138, 250)                                  # the rock continuation counts only between these rows (the grid ends at 140)
EXIT_S = (0, 748, W, H)                                 # box: the tiles at the bottom edge lead to the Glacial Region
EXIT_N_ROWS = 3                                         # tile rows 0..2 (z >= 4750) lead to the Bone Field: at the far end 400 units are 12 px, so by rows, not pixels
EXITS = [
    {'warp': 0, 'target': (82, 2), 'spawn_world': (20, -2250), 'rotation': 0},      # from KODA03's new east mouth: facing up the trail
    {'warp': 1, 'target': (306, 0), 'spawn_world': (0, 4250), 'rotation': 2048},    # from the Bone Field: row 7, four rows below the exit rows (at 4550 the arrival stood on them and bounced back)
]


def segment(pred, sx, sy, pos, neg, box=None):
    pts = np.array([[x * sx, y * sy] for x, y in pos + neg]); lab = np.array([1] * len(pos) + [0] * len(neg))
    bx = np.array([box[0] * sx, box[1] * sy, box[2] * sx, box[3] * sy]) if box else None
    masks, scores, _ = pred.predict(point_coords=pts, point_labels=lab, box=bx, multimask_output=True)
    mk = masks[int(np.argmax(scores))].astype(np.float32)
    return (cv2.resize(mk, (W, H), interpolation=cv2.INTER_AREA) > 0.5).astype(np.uint8), float(scores.max())


def main(out):
    os.makedirs(out, exist_ok=True)
    full = Image.open(ART_FULL).convert('RGB'); w0, h0 = full.size; hh = round(w0 * 6 / 5); y0 = (h0 - hh) // 2
    im = np.array(full.crop((0, y0, w0, y0 + hh))); sx, sy = w0 / W, hh / H
    torch.set_num_threads(16)
    pred = SamPredictor(sam_model_registry['vit_h'](checkpoint=CHECKPOINT)); pred.set_image(im)
    dirt, s1 = segment(pred, sx, sy, DIRT_POS, DIRT_NEG)
    rock, s2 = segment(pred, sx, sy, ROCK_POS, ROCK_NEG, ROCK_BOX)
    rock[:ROCK_BAND[0]] = 0; rock[ROCK_BAND[1]:] = 0; rock[:, :ROCK_BOX[0]] = 0; rock[:, ROCK_BOX[2]:] = 0
    Image.fromarray(rock * 255).save(os.path.join(out, 'PASS01-rock.png'))
    floor = np.maximum(dirt, cv2.dilate(rock, np.ones((9, 9), np.uint8)))      # the rock joins the dirt (SAM leaves a seam)
    floor = cv2.morphologyEx(floor, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    n, lbl, st, _ = cv2.connectedComponentsWithStats(floor)
    if n > 1: floor = (lbl == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])).astype(np.uint8)   # the trail, one piece
    n, lbl, st, _ = cv2.connectedComponentsWithStats(1 - floor)                             # small holes are trail
    for i in range(1, n):
        x, y, w, h = st[i, :4]
        if x > 0 and y > 0 and x + w < W and y + h < H and st[i, cv2.CC_STAT_AREA] < 1500: floor[lbl == i] = 1
    print(f'dirt score {s1:.3f}, rock score {s2:.3f}, floor pixels {int(floor.sum())}')
    Image.fromarray(floor * 255).save(os.path.join(out, 'PASS01-floor.png'))

    m = base_map('KODA08', *CAMERA); m.projection = PROJECTION; m.lights = LIGHTS; cam = Cam(m)
    col = [0x80] * 10000
    for tx, tz, u, v in cam.tiles():
        if u is None or not (0 <= u < W and 0 <= v < H): continue
        if floor[v, u]:
            col[tz * 100 + tx] = 0
            x0, y0_, x1, y1 = EXIT_S
            if x0 <= u <= x1 and y0_ <= v <= y1: col[tz * 100 + tx] = 110
            if tz < EXIT_N_ROWS: col[tz * 100 + tx] = 111
    m.collision = col
    for e in EXITS:
        x, z = e['spawn_world']
        m.warps[e['warp']].update({'x': x, 'z': z, 'rotation': e['rotation'], 'targetMap': e['target'][0], 'targetExit': e['target'][1]})
    check_arrivals(m, 'PASS01')
    from maps import reach
    R = reach.from_spawn_coordinates(m, starts=[EXITS[0]['spawn_world']])          # from the arrival from the Glacial Region only
    for e in EXITS:
        x, z = e['spawn_world']
        if (round(x / 10) * 10, round(z / 10) * 10) not in R: sys.exit(f'the spawn of warp {e["warp"]} at {x},{z} (px {cam.pixel(x, z)}) is not reachable from the south arrival')
    for k in (110, 111):
        tiles = [(i % 100, i // 100) for i, c in enumerate(col) if c == k]
        if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in tiles for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
            sys.exit(f'no exit tile of value {k} is reachable')
    json.dump({'camera': list(CAMERA), 'projection': PROJECTION, 'lights': LIGHTS, 'collision': col, 'warps': m.warps}, open(DATA, 'w'))
    print(f'PASS01: free tiles {col.count(0)}, exit tiles {col.count(110)} south + {col.count(111)} north, reach {len(R)}')
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
    Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, 'PASS01-zones.png'))


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
