#!/usr/bin/env python3
"""Authoring of the niche corridor (screen 307, files CRYP01), run by hand (needs numpy, cv2, torch and Segment
Anything): the floor is segmented from our art itself (SAM on the full-resolution picture: the stone flags and the
steps at the top end, positive points on them, negative points on the niche walls and the dark ends), and the steps'
band is made sure of with a box traced on the art (the exit up sits on it). Writes maps/crypt-corridor-data.json
(camera, lights, collision, exits) for the build-time recipe maps/crypt-corridor.py, and OUT_DIR/CRYP01-zones.png.

    SAM_CHECKPOINT=path/to/sam_vit_h_4b8939.pth python3 author/crypt-corridor-layout.py OUT_DIR
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

ART_FULL = os.path.join(MOD, 'art', 'full', 'crypt-corridor-1856x2304.png')   # the 640x768 art is its middle 5:6
ART = os.path.join(MOD, 'art', 'crypt-corridor.png')
DATA = os.path.join(MOD, 'maps', 'crypt-corridor-data.json')
CHECKPOINT = os.environ.get('SAM_CHECKPOINT', os.path.join(MOD, '..', '..', '..', 'build', 'new-maps', 'models', 'sam_vit_h_4b8939.pth'))
CAMERA = (4106, 58)                                     # SAIB02's: eye 4106 from the look-at point, 58 degrees down
PROJECTION = 497
LIGHTS = [{'vx': 100, 'vy': 100, 'vz': 100, 'r': 80, 'g': 80, 'b': 80},      # the Mansion Basement's (CHKA01)
          {'vx': 50, 'vy': 50, 'vz': 50, 'r': 80, 'g': 80, 'b': 80},
          {'vx': 0, 'vy': -10, 'vz': -50, 'r': 20, 'g': 20, 'b': 10}]
W, H = 640, 768
POS = [(320, 740), (320, 640), (325, 540), (320, 440), (320, 340), (320, 250), (318, 190), (318, 150), (320, 110), (250, 700), (400, 700)]
NEG = [(100, 400), (540, 400), (60, 200), (580, 200), (150, 650), (490, 650), (320, 30), (200, 100), (440, 100), (120, 750), (520, 750),
       (230, 300), (410, 300), (260, 150), (380, 150)]
STEPS_BOX = (270, 60, 370, 130)                         # the steps at the top end (the way up): walkable, traced on the art
EXIT_UP_ROWS = 3                                        # tile rows 0..2 lead up to the basement's trapdoor
EXIT_DOWN = (0, 724, W, 756)                            # box (pixels, where the tiles are big): rows about 73-74 lead down to the lectern room
EXITS = [
    {'warp': 0, 'target': (66, 1), 'spawn_world': (0, 4250), 'rotation': 2048},    # from the basement: row 7, facing down the corridor
    {'warp': 1, 'target': (308, 0), 'spawn_world': (0, -2050), 'rotation': 0},     # from the lectern room: row 70, facing up the corridor
]


def main(out):
    os.makedirs(out, exist_ok=True)
    full = Image.open(ART_FULL).convert('RGB'); w0, h0 = full.size; hh = round(w0 * 6 / 5); y0 = (h0 - hh) // 2
    im = np.array(full.crop((0, y0, w0, y0 + hh))); sx, sy = w0 / W, hh / H
    torch.set_num_threads(16)
    pred = SamPredictor(sam_model_registry['vit_h'](checkpoint=CHECKPOINT)); pred.set_image(im)
    pts = np.array([[x * sx, y * sy] for x, y in POS + NEG]); lab = np.array([1] * len(POS) + [0] * len(NEG))
    masks, scores, _ = pred.predict(point_coords=pts, point_labels=lab, multimask_output=True)
    mk = masks[int(np.argmax(scores))].astype(np.float32)
    floor = (cv2.resize(mk, (W, H), interpolation=cv2.INTER_AREA) > 0.5).astype(np.uint8)
    Image.fromarray(floor * 255).save(os.path.join(out, 'CRYP01-sam.png'))
    bx0, by0, bx1, by1 = STEPS_BOX
    steps = np.zeros_like(floor); steps[by0:by1, bx0:bx1] = 1
    floor = np.maximum(floor, steps)
    # the glowing circuit lines in the flags are floor too (SAM leaves them out as notches): by colour, grown a little
    bg0 = np.array(Image.open(ART).convert('RGB')).astype(int)
    lines = ((bg0[..., 1] > bg0[..., 0] + 40) & (bg0[..., 1] > bg0[..., 2] + 30) & (bg0[..., 1] > 90)).astype(np.uint8)
    lines = cv2.dilate(lines, np.ones((9, 9), np.uint8))
    floor = np.maximum(floor, lines & cv2.dilate(floor, np.ones((25, 25), np.uint8)))      # only where they touch the floor
    floor = cv2.morphologyEx(floor, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    floor = cv2.morphologyEx(floor, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    n, lbl, st, _ = cv2.connectedComponentsWithStats(floor)
    if n > 1: floor = (lbl == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(1 - floor)
    for i in range(1, n):
        x, y, w, h = st[i, :4]
        if x > 0 and y > 0 and x + w < W and y + h < H and st[i, cv2.CC_STAT_AREA] < 2000: floor[lbl == i] = 1
    print(f'floor score {scores.max():.3f}, floor pixels {int(floor.sum())}')
    Image.fromarray(floor * 255).save(os.path.join(out, 'CRYP01-floor.png'))

    m = base_map('SAIB02', *CAMERA); m.projection = PROJECTION; m.lights = LIGHTS; cam = Cam(m)
    col = [0x80] * 10000
    for tx, tz, u, v in cam.tiles():
        if u is None or not (0 <= u < W and 0 <= v < H): continue
        if floor[v, u]:
            col[tz * 100 + tx] = 0
            if tz < EXIT_UP_ROWS: col[tz * 100 + tx] = 110
            x0, y0_, x1, y1 = EXIT_DOWN
            if x0 <= u <= x1 and y0_ <= v <= y1: col[tz * 100 + tx] = 111
    m.collision = col
    for e in EXITS:
        x, z = e['spawn_world']
        m.warps[e['warp']].update({'x': x, 'z': z, 'rotation': e['rotation'], 'targetMap': e['target'][0], 'targetExit': e['target'][1]})
    check_arrivals(m, 'CRYP01')
    R = reach.from_spawn_coordinates(m, starts=[EXITS[0]['spawn_world']])
    for e in EXITS:
        x, z = e['spawn_world']
        if (round(x / 10) * 10, round(z / 10) * 10) not in R: sys.exit(f'the spawn of warp {e["warp"]} at {x},{z} (px {cam.pixel(x, z)}) is not reachable from the top arrival')
    for k in (110, 111):
        tiles = [(i % 100, i // 100) for i, c in enumerate(col) if c == k]
        if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in tiles for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
            sys.exit(f'no exit tile of value {k} is reachable')
    json.dump({'camera': list(CAMERA), 'projection': PROJECTION, 'lights': LIGHTS, 'collision': col, 'warps': m.warps}, open(DATA, 'w'))
    print(f'CRYP01: free tiles {col.count(0)}, exit tiles {col.count(110)} up + {col.count(111)} down, reach {len(R)}')
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
    Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, 'CRYP01-zones.png'))


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
