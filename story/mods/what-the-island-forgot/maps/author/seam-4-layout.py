#!/usr/bin/env python3
"""Authoring of the fourth Seam road screen (screen 327, files SEAM05, the gallery), run by hand (needs numpy, cv2,
our image API, torch and Segment Anything): the floor is SAM's block-floor mask unioned with a generous traced polygon (all the
floor between the rubble and the right wall) plus the treads of the block stair up to the watchtower's doorway, minus
the rubble slope along the left wall. Exits: the bottom edge (back to the camp, 326), the opening in the back wall (on
to 329) and the doorway at the top of the stair (the watchtower, 328). Writes maps/seam-4-data.json for the build-time
recipe maps/seam-4.py, and OUT_DIR/SEAM05-zones.png (green: the real reach, blue: exit tiles, white: arrivals).

    SAM_CHECKPOINT=path/to/sam_vit_h_4b8939.pth python3 author/seam-4-layout.py OUT_DIR
    (SAM_CACHE=1 reuses OUT_DIR/SEAM05-sam.npz for polygon, exit or spawn tweaks)
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

ART_FULL = os.path.join(MOD, 'art', 'full', 'seam-4-2304x1856.png')   # the 768x640 art is its middle 6:5
ART = os.path.join(MOD, 'art', 'seam-4.png')
DATA = os.path.join(MOD, 'maps', 'seam-4-data.json')
CHECKPOINT = os.environ.get('SAM_CHECKPOINT', os.path.join(MOD, '..', '..', '..', 'build', 'new-maps', 'models', 'sam_vit_h_4b8939.pth'))
CAMERA = (7000, 45)                                     # the pass's eye at 45 degrees down (MAYO04B's structure)
PROJECTION = 1000
W, H = 768, 640
PASSES = [
    {   # the block floor of the gallery
        'pos': [(380, 200), (300, 400), (450, 500), (400, 300), (250, 550), (500, 150), (350, 600)],
        'neg': [(100, 300), (650, 300), (380, 40), (700, 500), (60, 550), (720, 120)],
    },
]
FORCED = {                                              # the floor between the rubble and the stair, and the stair's treads
    'ground': [(230, 95), (700, 95), (700, 190), (560, 200), (575, 640), (120, 640), (110, 450), (150, 300), (200, 200)],
    'stair': [(560, 200), (700, 190), (740, 230), (768, 280), (768, 640), (575, 640)],
}
BLOCKED = {
    'rubble': [(0, 60), (230, 60), (240, 150), (215, 300), (180, 450), (170, 640), (0, 640)],
    'right-wall-top': [(700, 0), (768, 0), (768, 190), (700, 190)],
}
EXIT_S = (250, 616, 560, 640)                           # box: the bottom edge, back to the camp (326)
EXIT_N = (300, 93, 450, 118)                            # box: the foot of the opening in the back wall, on to 329 (when it exists)
EXIT_E = (720, 230, 768, 300)                           # box: the top of the stair, into the watchtower (328, when it exists)
EXITS = [
    {'warp': 0, 'target': (326, 1), 'spawn_px': (400, 585), 'face_px': (400, 300)},     # from the camp: at the bottom, facing in
    {'warp': 1, 'target': (329, 0), 'spawn_px': (375, 150), 'face_px': (375, 500)},     # from 329: below the opening, facing down
    {'warp': 2, 'target': (328, 0), 'spawn_px': (660, 330), 'face_px': (400, 400)},     # from the watchtower: on the stair, facing the gallery
]


def sam_masks(im, out):
    cache = os.path.join(out, 'SEAM05-sam.npz')
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
    n, lbl, st, _ = cv2.connectedComponentsWithStats(1 - floor)                             # small holes (joints, frost) are ground
    for i in range(1, n):
        x, y, w, h = st[i, :4]
        if x > 0 and y > 0 and x + w < W and y + h < H and st[i, cv2.CC_STAT_AREA] < 2500: floor[lbl == i] = 1
    Image.fromarray(floor * 255).save(os.path.join(out, 'SEAM05-ground.png'))
    for poly in FORCED.values(): cv2.fillPoly(floor, [np.array(poly, np.int32)], 1)
    for poly in BLOCKED.values(): cv2.fillPoly(floor, [np.array(poly, np.int32)], 0)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(floor)
    if n > 1: floor = (lbl == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    print(f'SAM scores {[round(float(s), 3) for s in scores]}, floor pixels {int(floor.sum())}')

    m = base_map('MAYO04B', *CAMERA); m.projection = PROJECTION; cam = Cam(m)
    col = [0x80] * 10000
    for tx, tz, u, v in cam.tiles():
        if u is None or not (0 <= u < W and 0 <= v < H): continue
        if floor[v, u]:
            col[tz * 100 + tx] = 0
            for k, (bx0, by0, bx1, by1) in enumerate((EXIT_S, EXIT_N, EXIT_E)):
                if bx0 <= u <= bx1 and by0 <= v <= by1: col[tz * 100 + tx] = 110 + k
    m.collision = col
    for e in EXITS:
        x, z = cam.world(*e['spawn_px']); e['spawn_world'] = (x, z)
        m.warps[e['warp']].update({'x': x, 'z': z, 'rotation': cam.rotation((x, z), cam.world(*e['face_px'])),
                                   'targetMap': e['target'][0], 'targetExit': e['target'][1]})
    check_arrivals(m, 'SEAM05')
    R = reach.from_spawn_coordinates(m, starts=[EXITS[0]['spawn_world']])
    for e in EXITS:
        x, z = e['spawn_world']
        if (round(x / 10) * 10, round(z / 10) * 10) not in R: sys.exit(f'the spawn of warp {e["warp"]} at {x},{z} (px {cam.pixel(x, z)}) is not reachable')
    for k in (110, 111, 112):
        tiles = [(i % 100, i // 100) for i, c in enumerate(col) if c == k]
        if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in tiles for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
            sys.exit(f'no exit tile of value {k} is reachable')
    json.dump({'camera': list(CAMERA), 'projection': PROJECTION, 'collision': col, 'warps': m.warps}, open(DATA, 'w'))
    print(f'SEAM05: free tiles {col.count(0)}, exit tiles {col.count(110)} south + {col.count(111)} north + {col.count(112)} tower, reach {len(R)}, '
          f'spawns {[(e["spawn_world"], m.warps[e["warp"]]["rotation"]) for e in EXITS]}')
    for name, px in [('enemy a', (400, 250)), ('enemy b', (300, 500)), ('enemy c', (480, 420))]:
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
    Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, 'SEAM05-zones.png'))


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
