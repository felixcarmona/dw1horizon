#!/usr/bin/env python3
"""Authoring of the standing stones (screen 334, files OVPS05, 640x768), run by hand (needs numpy, cv2, torch and
Segment Anything): the sand is SAM's mask unioned with a generous traced polygon (all the sand between the walls),
minus the grove of dead trees at the left, the group of standing stones, the single stone, the boulder, the shelf
with the plank sign at the top right and the walls. Exits: the top edge (back to the narrows, 333) and the bottom
edge (on to 335). Writes maps/descent-5-data.json for the build-time recipe maps/descent-5.py, and
OUT_DIR/OVPS05-zones.png. The enemy spots it prints are more than 1300 from every arrival (a wild Digimon within its
tracking range of an arrival jumps the tamer during the fade-in and the battle spawns empty).

    SAM_CHECKPOINT=path/to/sam_vit_h_4b8939.pth python3 author/descent-5-layout.py OUT_DIR
    (SAM_CACHE=1 reuses OUT_DIR/OVPS05-sam.npz for polygon, exit or spawn tweaks)
"""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import json, math, os, sys
import numpy as np, cv2
from tools.image import Image
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from mapbase import base_map, Cam, MOD, check_arrivals
from maps import reach

ART_FULL = os.path.join(MOD, 'art', 'full', 'descent-5-1856x2304.png')   # 4:5; the 640x768 art is its middle 5:6
ART = os.path.join(MOD, 'art', 'descent-5.png')
DATA = os.path.join(MOD, 'maps', 'descent-5-data.json')
CHECKPOINT = os.environ.get('SAM_CHECKPOINT', os.path.join(MOD, '..', '..', '..', 'build', 'new-maps', 'models', 'sam_vit_h_4b8939.pth'))
CAMERA = (7000, 52)                                     # zone 3's camera on a tall screen (DGHA01's structure)
PROJECTION = 1000
W, H = 640, 768
PASSES = [
    {   # the sand of the floor
        'pos': [(330, 100), (330, 250), (350, 350), (250, 450), (300, 600), (450, 700), (200, 700), (520, 350)],
        'neg': [(150, 200), (420, 480), (600, 100), (620, 500), (40, 600), (160, 580), (470, 710), (520, 120)],
    },
]
FORCED = {                                              # all the sand between the walls
    'ground': [(240, 0), (430, 0), (445, 130), (450, 250), (480, 320), (530, 400), (570, 460), (590, 520), (600, 768), (100, 768), (70, 620), (50, 480), (80, 400), (280, 370), (270, 250), (240, 120)],
}
BLOCKED = {
    'dead-trees': [(0, 60), (290, 60), (300, 380), (80, 420), (0, 420)],
    'stones': [(370, 400), (490, 395), (500, 600), (380, 600)],
    'single-stone': [(110, 520), (210, 515), (215, 660), (115, 665)],
    'boulder': [(430, 670), (510, 665), (515, 745), (435, 750)],
    'right-shelf': [(440, 0), (640, 0), (640, 250), (452, 255), (445, 130)],
    'right-wall': [(445, 240), (640, 240), (640, 768), (605, 768), (595, 520), (575, 460), (535, 400), (485, 320), (452, 255)],   # the wall's sloping face is rock, not sand
    'left-wall-low': [(0, 420), (80, 420), (50, 480), (70, 620), (100, 768), (0, 768)],
}
EXIT_N = (260, 0, 420, 22)                              # box: the top edge, back to the narrows (333)
EXIT_S = (120, 744, 580, 768)                           # box: the bottom edge, on to 335 (when it exists)
EXITS = [
    {'warp': 0, 'target': (333, 1), 'spawn_px': (330, 60), 'face_px': (330, 400)},      # from the narrows: at the top, facing down
    {'warp': 1, 'target': (335, 0), 'spawn_px': (330, 710), 'face_px': (330, 300)},     # from 335: at the bottom, facing up
]
ENEMY_PX = [('enemy a', (330, 340)), ('enemy b', (220, 470)), ('enemy c', (520, 500))]


def sam_masks(im, out):
    cache = os.path.join(out, 'OVPS05-sam.npz')
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
    Image.fromarray(floor * 255).save(os.path.join(out, 'OVPS05-ground.png'))
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
    check_arrivals(m, 'OVPS05')
    R = reach.from_spawn_coordinates(m, starts=[EXITS[0]['spawn_world']])
    for e in EXITS:
        x, z = e['spawn_world']
        if (round(x / 10) * 10, round(z / 10) * 10) not in R: sys.exit(f'the spawn of warp {e["warp"]} at {x},{z} (px {cam.pixel(x, z)}) is not reachable')
    for k in (110, 111):
        tiles = [(i % 100, i // 100) for i, c in enumerate(col) if c == k]
        if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in tiles for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
            sys.exit(f'no exit tile of value {k} is reachable')
    json.dump({'camera': list(CAMERA), 'projection': PROJECTION, 'collision': col, 'warps': m.warps}, open(DATA, 'w'))
    print(f'OVPS05: free tiles {col.count(0)}, exit tiles {col.count(110)} north + {col.count(111)} south, reach {len(R)}, '
          f'spawns {[(e["spawn_world"], m.warps[e["warp"]]["rotation"]) for e in EXITS]}')
    for name, px in ENEMY_PX:
        x, z = cam.world(*px); tx, tz = int(x / 100) + 50 - (1 if x < 0 else 0), 49 - int(z / 100) + (1 if z < 0 else 0)
        dist = min(math.hypot(x - e['spawn_world'][0], z - e['spawn_world'][1]) for e in EXITS)
        print(f'  {name} px {px} -> world ({x}, {z}) tile ({tx},{tz}) {"free" if not col[tz * 100 + tx] & 0x80 else "BLOCKED"}, nearest arrival {dist:.0f}{"" if dist > 1300 else " TOO CLOSE"}')
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
    Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, 'OVPS05-zones.png'))


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
