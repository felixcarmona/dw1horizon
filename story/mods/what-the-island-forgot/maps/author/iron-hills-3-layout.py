#!/usr/bin/env python3
"""Authoring of the third Iron Hills screen (screen 319, files IRON03, 640x768), run by hand (needs numpy, cv2,
torch and Segment Anything): the zigzag track is segmented from our art itself (SAM on the full-resolution picture,
one pass per leg of the zigzag, unioned: the broad floor at the bottom, the middle leg, the upper leg to the top),
what stands on it is blocked by traced polygons (the boiler, the cogs on the terraces, the gears at the bottom
corners), and the two ends of the track are the exits. Writes maps/iron-hills-3-data.json for the build-time recipe
maps/iron-hills-3.py, and OUT_DIR/IRON03-zones.png (green: the real reach, blue: exit tiles, white: arrival points).

    SAM_CHECKPOINT=path/to/sam_vit_h_4b8939.pth python3 author/iron-hills-3-layout.py OUT_DIR
    (SAM_CACHE=1 reuses OUT_DIR/IRON03-sam.npz for polygon, exit or spawn tweaks)
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

ART_FULL = os.path.join(MOD, 'art', 'full', 'iron-hills-3-1856x2304.png')   # 4:5; the 640x768 art is its middle 5:6
ART = os.path.join(MOD, 'art', 'iron-hills-3.png')
DATA = os.path.join(MOD, 'maps', 'iron-hills-3-data.json')
CHECKPOINT = os.environ.get('SAM_CHECKPOINT', os.path.join(MOD, '..', '..', '..', 'build', 'new-maps', 'models', 'sam_vit_h_4b8939.pth'))
CAMERA = (7000, 46)                                     # the pass's eye and lens, 46 degrees down for the tall screen
PROJECTION = 1200
W, H = 640, 768
PASSES = [
    {   # the broad floor at the bottom and the ramp up its right side
        'pos': [(160, 700), (400, 700), (100, 620), (320, 600), (520, 560), (600, 480), (240, 660), (560, 640)],
        'neg': [(200, 420), (60, 580), (560, 620), (300, 500), (40, 400), (620, 300), (300, 300)],
    },
    {   # the middle leg, from the right side up to the turn at the left
        'pos': [(300, 345), (160, 330), (480, 370), (600, 370), (100, 300), (400, 360)],
        'neg': [(200, 420), (300, 290), (480, 200), (620, 250), (300, 500), (60, 220)],
    },
    {   # the upper leg, from the turn at the left up to the top edge
        'pos': [(260, 190), (340, 160), (480, 100), (560, 60), (200, 230), (420, 30), (120, 260)],
        'neg': [(480, 200), (300, 290), (200, 100), (600, 300), (100, 160), (140, 420)],
    },
]
FORCED = {                                              # the three legs of the zigzag, traced generously (all the ground between the walls)
    'bottom-floor': [(0, 490), (60, 480), (460, 425), (480, 440), (640, 370), (640, 768), (0, 768)],
    'middle-leg': [(40, 300), (180, 245), (480, 285), (600, 320), (640, 330), (640, 380), (480, 440), (460, 425), (60, 480), (40, 470)],
    'upper-leg': [(40, 300), (40, 160), (140, 60), (400, 0), (640, 0), (640, 330), (600, 320), (480, 285), (180, 245)],
}
BLOCKED = {
    'boiler': [(40, 350), (230, 330), (310, 400), (330, 450), (410, 460), (420, 480), (200, 480), (60, 460)],
    'cogs-middle-terrace': [(240, 395), (400, 390), (410, 440), (240, 440)],                   # the two cogs right of the boiler
    'cogwheel': [(400, 140), (570, 140), (585, 270), (480, 280), (400, 245)],
    'cog-upper-terrace': [(230, 200), (320, 200), (320, 250), (230, 250)],
    'upper-left-wall': [(80, 40), (290, 40), (290, 155), (80, 155)],                           # the pipe and plates in the top-left wall
    'gears-bottom-left': [(0, 540), (110, 540), (110, 650), (0, 650)],
    'gears-bottom-right': [(450, 580), (640, 560), (640, 660), (450, 660)],
    'pipe-right-wall': [(590, 260), (640, 260), (640, 400), (590, 400)],
    'wall-a': [(0, 565), (120, 518), (475, 452), (475, 492), (120, 555), (0, 605)],                  # the terrace face between the bottom floor and the middle leg
    'wall-b': [(160, 285), (600, 355), (640, 365), (640, 320), (600, 310), (160, 245)],            # the terrace face between the middle leg and the upper leg
}
EXIT_S = (100, 744, 420, 768)                           # box: the bottom edge, back down to 318
EXIT_N = (400, 0, 620, 22)                              # box: the top edge, on up the pass (320, when it exists)
EXITS = [
    {'warp': 0, 'target': (318, 1), 'spawn_px': (250, 715), 'face_px': (320, 500)},    # from 318: at the bottom, facing the hill
    {'warp': 1, 'target': (320, 0), 'spawn_px': (500, 60), 'face_px': (300, 250)},     # from 320: at the top, facing down
]


def sam_masks(im, out):
    cache = os.path.join(out, 'IRON03-sam.npz')
    if os.environ.get('SAM_CACHE') and os.path.isfile(cache):
        z = np.load(cache); return [z[f'm{i}'] for i in range(len(PASSES))], list(z['scores'])
    import torch
    from tools.maps.sam import sam_model_registry, SamPredictor
    torch.set_num_threads(16)
    pred = SamPredictor(sam_model_registry['vit_h'](checkpoint=CHECKPOINT)); pred.set_image(im)
    h0, w0 = im.shape[:2]; sx, sy = w0 / W, h0 / H
    masks, scores = [], []
    for p in PASSES:
        pts = np.array([[x * sx, y * sy] for x, y in p['pos'] + p['neg']]); lab = np.array([1] * len(p['pos']) + [0] * len(p['neg']))
        mk, sc, _ = pred.predict(point_coords=pts, point_labels=lab, multimask_output=True)
        masks.append(mk[int(np.argmax(sc))]); scores.append(float(sc.max()))
    np.savez_compressed(cache, scores=np.array(scores), **{f'm{i}': m for i, m in enumerate(masks)})
    return masks, scores


def main(out):
    os.makedirs(out, exist_ok=True)
    full = Image.open(ART_FULL).convert('RGB'); w0, h0 = full.size; hh = round(w0 * 6 / 5); y0 = (h0 - hh) // 2
    im = np.array(full.crop((0, y0, w0, y0 + hh)))
    masks, scores = sam_masks(im, out)
    floor = np.zeros((H, W), np.uint8)
    for mk in masks:
        floor |= (cv2.resize(mk.astype(np.float32), (W, H), interpolation=cv2.INTER_AREA) > 0.5).astype(np.uint8)
    floor = cv2.morphologyEx(floor, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    floor = cv2.morphologyEx(floor, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    n, lbl, st, _ = cv2.connectedComponentsWithStats(1 - floor)                             # small holes (stones, tufts) are ground
    for i in range(1, n):
        x, y, w, h = st[i, :4]
        if x > 0 and y > 0 and x + w < W and y + h < H and st[i, cv2.CC_STAT_AREA] < 2500: floor[lbl == i] = 1
    Image.fromarray(floor * 255).save(os.path.join(out, 'IRON03-ground.png'))
    for poly in FORCED.values(): cv2.fillPoly(floor, [np.array(poly, np.int32)], 1)
    for poly in BLOCKED.values(): cv2.fillPoly(floor, [np.array(poly, np.int32)], 0)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(floor)
    if n > 1: floor = (lbl == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    print(f'SAM scores {[round(float(s), 3) for s in scores]}, floor pixels {int(floor.sum())}')

    m = base_map('GIAS07', *CAMERA); m.projection = PROJECTION; cam = Cam(m)
    col = [0x80] * 10000
    for tx, tz, u, v in cam.tiles():
        if u is None or not (0 <= u < W and 0 <= v < H): continue
        if floor[v, u]:
            col[tz * 100 + tx] = 0
            for k, (bx0, by0, bx1, by1) in enumerate((EXIT_S, EXIT_N)):
                if bx0 <= u <= bx1 and by0 <= v <= by1: col[tz * 100 + tx] = 110 + k
    m.collision = col
    for e in EXITS:
        x, z = cam.world(*e['spawn_px']); e['spawn_world'] = (x, z)
        m.warps[e['warp']].update({'x': x, 'z': z, 'rotation': cam.rotation((x, z), cam.world(*e['face_px'])),
                                   'targetMap': e['target'][0], 'targetExit': e['target'][1]})
    check_arrivals(m, 'IRON03')
    R = reach.from_spawn_coordinates(m, starts=[EXITS[0]['spawn_world']])
    for e in EXITS:
        x, z = e['spawn_world']
        if (round(x / 10) * 10, round(z / 10) * 10) not in R: sys.exit(f'the spawn of warp {e["warp"]} at {x},{z} (px {cam.pixel(x, z)}) is not reachable')
    for k in (110, 111):
        tiles = [(i % 100, i // 100) for i, c in enumerate(col) if c == k]
        if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in tiles for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
            sys.exit(f'no exit tile of value {k} is reachable')
    json.dump({'camera': list(CAMERA), 'projection': PROJECTION, 'collision': col, 'warps': m.warps}, open(DATA, 'w'))
    print(f'IRON03: free tiles {col.count(0)}, exit tiles {col.count(110)} south + {col.count(111)} north, reach {len(R)}, '
          f'spawns {[(e["spawn_world"], m.warps[e["warp"]]["rotation"]) for e in EXITS]}')
    for name, px in [('enemy a', (320, 640)), ('enemy b', (300, 345)), ('enemy c', (360, 150))]:
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
    Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, 'IRON03-zones.png'))


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
