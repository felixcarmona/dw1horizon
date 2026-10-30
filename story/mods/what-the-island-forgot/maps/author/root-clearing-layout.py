#!/usr/bin/env python3
"""Authoring of the Root Clearing (screen 314, files ROOT01), run by hand (needs numpy, cv2, torch and Segment
Anything): the clearing's floor is segmented from our art itself (SAM on the full-resolution picture, in three passes
whose union is the floor: the grass with the two dirt paths, the big flat slabs of the old road, the moss and dirt
patches), and what stands on it is blocked by polygons traced on the art (the root pile with the tilted slabs at the
left, the root tendrils over the moss under the root plate, the small stump at the right). Writes
maps/root-clearing-data.json (camera, collision, exits) for the build-time recipe maps/root-clearing.py, and
OUT_DIR/ROOT01-zones.png (green: the real reach, blue: exit tiles, white: arrival points).

    SAM_CHECKPOINT=path/to/sam_vit_h_4b8939.pth python3 author/root-clearing-layout.py OUT_DIR
    (SAM_CACHE=1 reuses OUT_DIR/ROOT01-sam.npz for polygon, exit or spawn tweaks)
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

ART_FULL = os.path.join(MOD, 'art', 'full', 'root-clearing-2304x1856.png')   # the 768x640 art is its middle 6:5
ART = os.path.join(MOD, 'art', 'root-clearing.png')
DATA = os.path.join(MOD, 'maps', 'root-clearing-data.json')
CHECKPOINT = os.environ.get('SAM_CHECKPOINT', os.path.join(MOD, '..', '..', '..', 'build', 'new-maps', 'models', 'sam_vit_h_4b8939.pth'))
CAMERA = (6410, 47)                                     # MAYO04B's: eye 6410 from the look-at point, 47 degrees down
PROJECTION = 927
W, H = 768, 640
# points in 768x640 pixels; each pass: positives, negatives, an optional box
PASSES = [
    {   # the grass of the clearing with the dirt paths at the top and at the bottom right
        'pos': [(600, 100), (700, 200), (560, 110), (650, 480), (600, 540), (300, 500), (200, 420), (480, 540), (400, 30),
                (420, 90), (690, 600), (700, 520), (160, 400), (260, 390), (520, 60)],
        'neg': [(150, 80), (260, 200), (330, 170), (300, 40), (720, 60), (700, 300), (740, 420), (400, 600), (150, 560),
                (40, 300), (60, 480), (300, 250), (120, 300), (520, 330), (470, 160)],
    },
    {   # the big flat slabs of the road
        'pos': [(520, 330), (600, 420), (450, 370), (560, 460), (420, 300), (620, 480)],
        'neg': [(300, 250), (330, 170), (200, 420), (600, 100), (700, 300)],
        'box': (355, 265, 650, 515),
    },
    {   # the moss and dirt under the root plate and the mossy ground at the lower left
        'pos': [(470, 160), (530, 250), (480, 220), (330, 440), (260, 470), (380, 430), (300, 530)],
        'neg': [(330, 170), (300, 250), (150, 560), (520, 330), (600, 100), (60, 480)],
    },
]
BLOCKED = {                                             # traced on the 768x640 art: never walkable
    'root-pile': [(30, 190), (475, 190), (475, 280), (355, 290), (345, 375), (130, 385), (30, 330)],   # the roots and tilted slabs at the left
    'root-band': [(380, 135), (540, 135), (540, 200), (380, 200)],                                    # tendrils over the moss under the root plate
    'stump': [(600, 115), (660, 115), (660, 175), (600, 175)],                                        # the small stump and the post at the right
}
FORCED = {                                              # traced on the art: always walkable (narrow spots the walk test caught, 2026-10-21)
    'top-path': [(360, 0), (452, 0), (452, 140), (360, 140)],                  # the whole dirt path and its mouth (a fern tip at its right side)
    'east-corridor': [(560, 270), (700, 270), (700, 560), (640, 560), (640, 520), (560, 520)],   # the grass and moss between the slabs and the ferns at the right, down to the lower path
}
EXIT_N = (360, 0, 445, 24)                              # box: the top edge, the dirt path to the field (MAYO03)
EXIT_SE = (630, 616, 768, 640)                          # box: the bottom edge at the right, the dirt path down to Coela Point (MAYO05)
EXITS = [
    {'warp': 0, 'target': (2, 4), 'spawn_px': (395, 50), 'face_px': (450, 400)},      # from the field: on the top path, facing the clearing
    {'warp': 1, 'target': (5, 1), 'spawn_px': (690, 565), 'face_px': (500, 400)},     # from Coela Point: on the lower path, facing the clearing
]


def sam_masks(im, out):
    cache = os.path.join(out, 'ROOT01-sam.npz')
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
        box = np.array([p['box'][0] * sx, p['box'][1] * sy, p['box'][2] * sx, p['box'][3] * sy]) if 'box' in p else None
        mk, sc, _ = pred.predict(point_coords=pts, point_labels=lab, box=box, multimask_output=True)
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
    n, lbl, st, _ = cv2.connectedComponentsWithStats(1 - floor)                             # small holes (stones, tufts) are ground
    for i in range(1, n):
        x, y, w, h = st[i, :4]
        if x > 0 and y > 0 and x + w < W and y + h < H and st[i, cv2.CC_STAT_AREA] < 2500: floor[lbl == i] = 1
    Image.fromarray(floor * 255).save(os.path.join(out, 'ROOT01-ground.png'))
    for poly in BLOCKED.values(): cv2.fillPoly(floor, [np.array(poly, np.int32)], 0)
    for poly in FORCED.values(): cv2.fillPoly(floor, [np.array(poly, np.int32)], 1)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(floor)
    if n > 1: floor = (lbl == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    print(f'SAM scores {[round(s, 3) for s in scores]}, floor pixels {int(floor.sum())}')

    m = base_map('MAYO04B', *CAMERA); m.projection = PROJECTION; cam = Cam(m)
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
    check_arrivals(m, 'ROOT01')
    R = reach.from_spawn_coordinates(m, starts=[EXITS[0]['spawn_world']])          # from the arrival from the field only
    for e in EXITS:
        x, z = e['spawn_world']
        if (round(x / 10) * 10, round(z / 10) * 10) not in R: sys.exit(f'the spawn of warp {e["warp"]} at {x},{z} (px {cam.pixel(x, z)}) is not reachable from the north arrival')
    for k in (110, 111):
        tiles = [(i % 100, i // 100) for i, c in enumerate(col) if c == k]
        if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in tiles for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
            sys.exit(f'no exit tile of value {k} is reachable')
    json.dump({'camera': list(CAMERA), 'projection': PROJECTION, 'collision': col, 'warps': m.warps}, open(DATA, 'w'))
    print(f'ROOT01: free tiles {col.count(0)}, exit tiles {col.count(110)} north + {col.count(111)} south-east, reach {len(R)}, '
          f'spawns {[(e["spawn_world"], m.warps[e["warp"]]["rotation"]) for e in EXITS]}')
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
    Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, 'ROOT01-zones.png'))


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
