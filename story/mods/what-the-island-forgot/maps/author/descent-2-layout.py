#!/usr/bin/env python3
"""Authoring of the dry riverbed (screen 331, files OVPS02, 640x768), run by hand (needs numpy, cv2, torch and
Segment Anything): the bed is SAM's sand mask unioned with a generous traced polygon (all the sand between the banks),
minus the arch's feet, the boulder with its stones, the dead trees and the pipes and bushes along the banks. Exits:
the top edge under the arch (back to the mouth, 330) and the bottom edge (on to 332). Writes
maps/descent-2-data.json for the build-time recipe maps/descent-2.py, and OUT_DIR/OVPS02-zones.png.

    SAM_CHECKPOINT=path/to/sam_vit_h_4b8939.pth python3 author/descent-2-layout.py OUT_DIR
    (SAM_CACHE=1 reuses OUT_DIR/OVPS02-sam.npz for polygon, exit or spawn tweaks)
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

ART_FULL = os.path.join(MOD, 'art', 'full', 'descent-2-1856x2304.png')   # 4:5; the 640x768 art is its middle 5:6
ART = os.path.join(MOD, 'art', 'descent-2.png')
DATA = os.path.join(MOD, 'maps', 'descent-2-data.json')
CHECKPOINT = os.environ.get('SAM_CHECKPOINT', os.path.join(MOD, '..', '..', '..', 'build', 'new-maps', 'models', 'sam_vit_h_4b8939.pth'))
CAMERA = (7000, 52)                                     # zone 3's camera on a tall screen (DGHA01's structure)
PROJECTION = 1000
W, H = 640, 768
PASSES = [
    {   # the sand of the riverbed
        'pos': [(320, 300), (300, 450), (280, 600), (330, 700), (250, 350), (380, 250), (200, 500), (330, 180)],
        'neg': [(80, 300), (560, 300), (320, 60), (460, 560), (120, 150), (600, 650), (40, 650), (500, 420)],
    },
]
FORCED = {                                              # all the sand between the banks
    'ground': [(230, 165), (430, 165), (480, 260), (520, 400), (540, 540), (560, 768), (110, 768), (90, 600), (90, 450), (110, 300), (160, 200)],
}
BLOCKED = {
    'arch-left-foot': [(150, 60), (250, 60), (260, 200), (180, 230), (140, 200)],
    'arch-right-foot': [(380, 60), (520, 60), (540, 230), (470, 240), (410, 180)],
    'boulder': [(390, 490), (560, 480), (570, 620), (430, 680), (380, 600)],
    'left-bank': [(0, 60), (160, 60), (170, 300), (120, 420), (100, 560), (80, 640), (0, 640)],
    'left-bank-low': [(0, 640), (120, 640), (150, 768), (0, 768)],
    'right-bank': [(520, 230), (640, 230), (640, 480), (560, 480), (520, 400)],
    'right-bank-low': [(560, 600), (640, 600), (640, 768), (590, 768)],
    'bush-right': [(440, 330), (530, 330), (530, 430), (440, 430)],
}
EXIT_N = (240, 160, 420, 185)                           # box: the sand under the arch, back to the mouth (330)
EXIT_S = (160, 744, 560, 768)                           # box: the bottom edge, on to 332 (when it exists)
EXITS = [
    {'warp': 0, 'target': (330, 1), 'spawn_px': (330, 230), 'face_px': (330, 500)},     # from the mouth: under the arch, facing down the bed
    {'warp': 1, 'target': (332, 0), 'spawn_px': (300, 710), 'face_px': (320, 300)},     # from 332: at the bottom, facing up
]


def sam_masks(im, out):
    cache = os.path.join(out, 'OVPS02-sam.npz')
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
    n, lbl, st, _ = cv2.connectedComponentsWithStats(1 - floor)                             # small holes (pebbles, cracks) are ground
    for i in range(1, n):
        x, y, w, h = st[i, :4]
        if x > 0 and y > 0 and x + w < W and y + h < H and st[i, cv2.CC_STAT_AREA] < 2500: floor[lbl == i] = 1
    Image.fromarray(floor * 255).save(os.path.join(out, 'OVPS02-ground.png'))
    for poly in FORCED.values(): cv2.fillPoly(floor, [np.array(poly, np.int32)], 1)
    for poly in BLOCKED.values(): cv2.fillPoly(floor, [np.array(poly, np.int32)], 0)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(floor)
    if n > 1: floor = (lbl == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    print(f'SAM scores {[round(float(s), 3) for s in scores]}, floor pixels {int(floor.sum())}')

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
    check_arrivals(m, 'OVPS02')
    R = reach.from_spawn_coordinates(m, starts=[EXITS[0]['spawn_world']])
    for e in EXITS:
        x, z = e['spawn_world']
        if (round(x / 10) * 10, round(z / 10) * 10) not in R: sys.exit(f'the spawn of warp {e["warp"]} at {x},{z} (px {cam.pixel(x, z)}) is not reachable')
    for k in (110, 111):
        tiles = [(i % 100, i // 100) for i, c in enumerate(col) if c == k]
        if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in tiles for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
            sys.exit(f'no exit tile of value {k} is reachable')
    json.dump({'camera': list(CAMERA), 'projection': PROJECTION, 'collision': col, 'warps': m.warps}, open(DATA, 'w'))
    print(f'OVPS02: free tiles {col.count(0)}, exit tiles {col.count(110)} north + {col.count(111)} south, reach {len(R)}, '
          f'spawns {[(e["spawn_world"], m.warps[e["warp"]]["rotation"]) for e in EXITS]}')
    for name, px in [('enemy a', (320, 350)), ('enemy b', (250, 620)), ('enemy c', (380, 450))]:
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
    Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, 'OVPS02-zones.png'))


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
