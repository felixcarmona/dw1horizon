#!/usr/bin/env python3
"""Authoring of the Brink (screen 322, files IRON06), run by hand (needs numpy, cv2, torch and Segment Anything):
the floor is SAM's mask (two passes: the grass of the red half, the grey blocks of the other) unioned with a generous
traced polygon over both halves, minus what is traced as blocked: the crack (the slab across it stays walkable), the
leaning pylon, the rock rims, the machinery of the left shoulder, the valve and the gears at the bottom left, the
raised block at the bottom right. Writes maps/the-brink-data.json for the build-time recipe maps/the-brink.py, and
OUT_DIR/IRON06-zones.png (green: the real reach, blue: exit tiles, white: arrival points).

    SAM_CHECKPOINT=path/to/sam_vit_h_4b8939.pth python3 author/the-brink-layout.py OUT_DIR
    (SAM_CACHE=1 reuses OUT_DIR/IRON06-sam.npz for polygon, exit or spawn tweaks)
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

ART_FULL = os.path.join(MOD, 'art', 'full', 'iron-hills-6-2304x1856.png')   # the 768x640 art is its middle 6:5
ART = os.path.join(MOD, 'art', 'iron-hills-6.png')
DATA = os.path.join(MOD, 'maps', 'the-brink-data.json')
CHECKPOINT = os.environ.get('SAM_CHECKPOINT', os.path.join(MOD, '..', '..', '..', 'build', 'new-maps', 'models', 'sam_vit_h_4b8939.pth'))
CAMERA = (7000, 39)                                     # GIAS04's family: eye 7000 from the look-at point, 39 degrees down
PROJECTION = 1200
W, H = 768, 640
PASSES = [
    {   # the grass and earth of the red half
        'pos': [(300, 100), (250, 250), (300, 400), (250, 550), (330, 300), (200, 460), (380, 40)],
        'neg': [(80, 100), (260, 60), (150, 350), (60, 560), (500, 300), (600, 200), (440, 580)],
    },
    {   # the grey blocks of the other half
        'pos': [(460, 200), (480, 400), (680, 300), (650, 450), (450, 560), (700, 200), (520, 150)],
        'neg': [(580, 250), (600, 450), (300, 300), (600, 40), (720, 580), (250, 100)],
    },
]
FORCED = {                                              # both halves, all the ground between the rims
    'ground': [(130, 0), (440, 0), (460, 80), (740, 90), (740, 500), (680, 520), (660, 640), (150, 640), (130, 520), (110, 300), (130, 200)],
    'slab': [(510, 275), (660, 270), (665, 340), (515, 345)],
}
BLOCKED = {
    'crack': [(540, 100), (590, 100), (600, 260), (620, 340), (660, 640), (600, 640), (580, 340), (560, 260)],
    'pylon': [(190, 0), (330, 0), (330, 135), (190, 135)],
    'top-right-rim': [(440, 0), (768, 0), (768, 95), (440, 70)],
    'left-shoulder': [(100, 60), (200, 60), (200, 200), (100, 200)],
    'valve': [(80, 290), (230, 290), (240, 440), (90, 440)],
    'gears-bottom-left': [(0, 440), (160, 470), (160, 640), (0, 640)],
    'block-bottom-right': [(640, 500), (768, 500), (768, 640), (640, 640)],
}
EXIT_NW = (320, 0, 440, 22)                             # box: the top edge, back up the slope (321)
EXIT_E = (740, 300, 768, 480)                           # box: the right edge, into the Seam (323, when it exists)
EXITS = [
    {'warp': 0, 'target': (321, 1), 'spawn_px': (380, 60), 'face_px': (400, 350)},     # from the slope: at the top, facing the brink
    {'warp': 1, 'target': (323, 0), 'spawn_px': (700, 390), 'face_px': (450, 350)},    # from the Seam: at the right edge, facing the hills
]


def sam_masks(im, out):
    cache = os.path.join(out, 'IRON06-sam.npz')
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
    n, lbl, st, _ = cv2.connectedComponentsWithStats(1 - floor)                             # small holes (stones, cables, joints) are ground
    for i in range(1, n):
        x, y, w, h = st[i, :4]
        if x > 0 and y > 0 and x + w < W and y + h < H and st[i, cv2.CC_STAT_AREA] < 2500: floor[lbl == i] = 1
    Image.fromarray(floor * 255).save(os.path.join(out, 'IRON06-ground.png'))
    for poly in FORCED.values(): cv2.fillPoly(floor, [np.array(poly, np.int32)], 1)
    for poly in BLOCKED.values(): cv2.fillPoly(floor, [np.array(poly, np.int32)], 0)
    cv2.fillPoly(floor, [np.array(FORCED['slab'], np.int32)], 1)                          # the slab lies over the crack
    n, lbl, st, _ = cv2.connectedComponentsWithStats(floor)
    if n > 1: floor = (lbl == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    print(f'SAM scores {[round(float(s), 3) for s in scores]}, floor pixels {int(floor.sum())}')

    m = base_map('GIAS04', *CAMERA); m.projection = PROJECTION; cam = Cam(m)
    col = [0x80] * 10000
    for tx, tz, u, v in cam.tiles():
        if u is None or not (0 <= u < W and 0 <= v < H): continue
        if floor[v, u]:
            col[tz * 100 + tx] = 0
            for k, (bx0, by0, bx1, by1) in enumerate((EXIT_NW, EXIT_E)):
                if bx0 <= u <= bx1 and by0 <= v <= by1: col[tz * 100 + tx] = 110 + k
    m.collision = col
    for e in EXITS:
        x, z = cam.world(*e['spawn_px']); e['spawn_world'] = (x, z)
        m.warps[e['warp']].update({'x': x, 'z': z, 'rotation': cam.rotation((x, z), cam.world(*e['face_px'])),
                                   'targetMap': e['target'][0], 'targetExit': e['target'][1]})
    check_arrivals(m, 'IRON06')
    R = reach.from_spawn_coordinates(m, starts=[EXITS[0]['spawn_world']])
    for e in EXITS:
        x, z = e['spawn_world']
        if (round(x / 10) * 10, round(z / 10) * 10) not in R: sys.exit(f'the spawn of warp {e["warp"]} at {x},{z} (px {cam.pixel(x, z)}) is not reachable')
    for k in (110, 111):
        tiles = [(i % 100, i // 100) for i, c in enumerate(col) if c == k]
        if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in tiles for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
            sys.exit(f'no exit tile of value {k} is reachable')
    json.dump({'camera': list(CAMERA), 'projection': PROJECTION, 'collision': col, 'warps': m.warps}, open(DATA, 'w'))
    print(f'IRON06: free tiles {col.count(0)}, exit tiles {col.count(110)} north-west + {col.count(111)} east, reach {len(R)}, '
          f'spawns {[(e["spawn_world"], m.warps[e["warp"]]["rotation"]) for e in EXITS]}')
    for name, px in [('enemy a', (300, 250)), ('enemy b', (480, 450)), ('enemy c', (680, 420))]:
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
    Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, 'IRON06-zones.png'))


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
