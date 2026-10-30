#!/usr/bin/env python3
"""Authoring of the fifth Iron Hills screen (screen 321, files IRON05), run by hand (needs numpy, cv2, torch and
Segment Anything): the slope is SAM's grass-and-earth mask unioned with a generous traced polygon (all the ground
between the shoulders, the grey circuit blocks at the lower right included), minus what stands on it, traced (the
turbine housing, the valve wheel and its pipe, the dead tree and the machinery of the shoulders, the gears at the
bottom left); the slack cables on the grass stay walkable. Writes maps/iron-hills-5-data.json for the build-time
recipe maps/iron-hills-5.py, and OUT_DIR/IRON05-zones.png (green: the real reach, blue: exit tiles, white: arrival
points).

    SAM_CHECKPOINT=path/to/sam_vit_h_4b8939.pth python3 author/iron-hills-5-layout.py OUT_DIR
    (SAM_CACHE=1 reuses OUT_DIR/IRON05-sam.npz for polygon, exit or spawn tweaks)
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

ART_FULL = os.path.join(MOD, 'art', 'full', 'iron-hills-5-2304x1856.png')   # the 768x640 art is its middle 6:5
ART = os.path.join(MOD, 'art', 'iron-hills-5.png')
DATA = os.path.join(MOD, 'maps', 'iron-hills-5-data.json')
CHECKPOINT = os.environ.get('SAM_CHECKPOINT', os.path.join(MOD, '..', '..', '..', 'build', 'new-maps', 'models', 'sam_vit_h_4b8939.pth'))
CAMERA = (7000, 39)                                     # GIAS04's family: eye 7000 from the look-at point, 39 degrees down
PROJECTION = 1200
W, H = 768, 640
PASSES = [
    {   # the slope's grass and earth
        'pos': [(350, 60), (400, 200), (300, 350), (450, 420), (350, 520), (550, 480), (250, 250), (500, 300), (420, 580), (600, 560)],
        'neg': [(100, 100), (600, 60), (120, 350), (600, 180), (700, 400), (60, 560), (720, 600), (150, 180), (640, 330), (40, 300)],
    },
]
FORCED = {                                              # all the ground between the shoulders
    'ground': [(230, 0), (440, 0), (470, 60), (500, 250), (600, 300), (620, 470), (700, 560), (700, 640), (170, 640), (160, 470),
               (160, 400), (130, 300), (180, 200), (230, 140)],
}
BLOCKED = {
    'turbine': [(500, 120), (700, 110), (720, 250), (640, 290), (520, 240), (500, 180)],
    'valve': [(100, 280), (230, 270), (240, 420), (130, 440), (80, 400)],
    'dead-tree': [(0, 70), (170, 80), (160, 260), (0, 270)],
    'left-shoulder': [(100, 40), (240, 30), (260, 160), (170, 170)],
    'right-rim': [(600, 250), (768, 250), (768, 640), (700, 640), (620, 500), (590, 300)],
    'gears-bottom-left': [(0, 440), (160, 470), (160, 640), (0, 640)],
    'top-right-machinery': [(440, 0), (600, 0), (600, 130), (500, 120)],
}
EXIT_N = (250, 0, 470, 22)                              # box: the top edge, back up to the ridge (320)
EXIT_SE = (560, 616, 768, 640)                          # box: the bottom edge at the right, on to the brink (322, when it exists)
EXITS = [
    {'warp': 0, 'target': (320, 1), 'spawn_px': (360, 55), 'face_px': (400, 300)},     # from the ridge: at the top, facing down the slope
    {'warp': 1, 'target': (322, 0), 'spawn_px': (620, 560), 'face_px': (400, 300)},    # from the brink: at the bottom right, facing up
]


def sam_masks(im, out):
    cache = os.path.join(out, 'IRON05-sam.npz')
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
    full = Image.open(ART_FULL).convert('RGB'); w0, h0 = full.size; ww = round(h0 * 6 / 5); x0 = (w0 - ww) // 2
    im = np.array(full.crop((x0, 0, x0 + ww, h0)))
    masks, scores = sam_masks(im, out)
    floor = np.zeros((H, W), np.uint8)
    for mk in masks:
        floor |= (cv2.resize(mk.astype(np.float32), (W, H), interpolation=cv2.INTER_AREA) > 0.5).astype(np.uint8)
    floor = cv2.morphologyEx(floor, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    floor = cv2.morphologyEx(floor, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    n, lbl, st, _ = cv2.connectedComponentsWithStats(1 - floor)                             # small holes (stones, cables) are ground
    for i in range(1, n):
        x, y, w, h = st[i, :4]
        if x > 0 and y > 0 and x + w < W and y + h < H and st[i, cv2.CC_STAT_AREA] < 2500: floor[lbl == i] = 1
    Image.fromarray(floor * 255).save(os.path.join(out, 'IRON05-ground.png'))
    for poly in FORCED.values(): cv2.fillPoly(floor, [np.array(poly, np.int32)], 1)
    for poly in BLOCKED.values(): cv2.fillPoly(floor, [np.array(poly, np.int32)], 0)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(floor)
    if n > 1: floor = (lbl == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    print(f'SAM scores {[round(float(s), 3) for s in scores]}, floor pixels {int(floor.sum())}')

    m = base_map('GIAS04', *CAMERA); m.projection = PROJECTION; cam = Cam(m)
    col = [0x80] * 10000
    for tx, tz, u, v in cam.tiles():
        if u is None or not (0 <= u < W and 0 <= v < H): continue
        if floor[v, u]:
            col[tz * 100 + tx] = 0
            for k, (bx0, by0, bx1, by1) in enumerate((EXIT_N, EXIT_SE)):
                if bx0 <= u <= bx1 and by0 <= v <= by1: col[tz * 100 + tx] = 110 + k
    m.collision = col
    for e in EXITS:
        x, z = cam.world(*e['spawn_px']); e['spawn_world'] = (x, z)
        m.warps[e['warp']].update({'x': x, 'z': z, 'rotation': cam.rotation((x, z), cam.world(*e['face_px'])),
                                   'targetMap': e['target'][0], 'targetExit': e['target'][1]})
    check_arrivals(m, 'IRON05')
    R = reach.from_spawn_coordinates(m, starts=[EXITS[0]['spawn_world']])
    for e in EXITS:
        x, z = e['spawn_world']
        if (round(x / 10) * 10, round(z / 10) * 10) not in R: sys.exit(f'the spawn of warp {e["warp"]} at {x},{z} (px {cam.pixel(x, z)}) is not reachable')
    for k in (110, 111):
        tiles = [(i % 100, i // 100) for i, c in enumerate(col) if c == k]
        if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in tiles for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
            sys.exit(f'no exit tile of value {k} is reachable')
    json.dump({'camera': list(CAMERA), 'projection': PROJECTION, 'collision': col, 'warps': m.warps}, open(DATA, 'w'))
    print(f'IRON05: free tiles {col.count(0)}, exit tiles {col.count(110)} north + {col.count(111)} south-east, reach {len(R)}, '
          f'spawns {[(e["spawn_world"], m.warps[e["warp"]]["rotation"]) for e in EXITS]}')
    for name, px in [('enemy a', (400, 200)), ('enemy b', (300, 450)), ('enemy c', (560, 520))]:
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
    Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, 'IRON05-zones.png'))


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
