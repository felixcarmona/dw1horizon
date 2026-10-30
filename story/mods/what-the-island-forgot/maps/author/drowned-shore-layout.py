#!/usr/bin/env python3
"""Authoring of the Drowned Shore (screen 309, files SHOR01), run by hand (needs numpy, cv2, torch and Segment
Anything): the beach is segmented from our art itself (SAM on the full-resolution picture, positive points on the
pebbles, negative points on the cliff, the sea, the ice plates and the wreck), the wreck is blocked by a polygon traced
on the art. No exit tiles (the way out is Whamon, by script): only the arrival point, warp 0, on the foreshore where
Whamon waits. Writes maps/drowned-shore-data.json (camera, collision, warps) for the build-time recipe
maps/drowned-shore.py, and OUT_DIR/SHOR01-zones.png.

    SAM_CHECKPOINT=path/to/sam_vit_h_4b8939.pth python3 author/drowned-shore-layout.py OUT_DIR
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

ART_FULL = os.path.join(MOD, 'art', 'full', 'drowned-shore-2304x1856.png')   # the 768x640 art is its middle 6:5
ART = os.path.join(MOD, 'art', 'drowned-shore.png')
DATA = os.path.join(MOD, 'maps', 'drowned-shore-data.json')
CHECKPOINT = os.environ.get('SAM_CHECKPOINT', os.path.join(MOD, '..', '..', '..', 'build', 'new-maps', 'models', 'sam_vit_h_4b8939.pth'))
CAMERA = (6000, 65)                                     # FRZL16's pitch, the eye at 6000 (FRZL16's own 5700/1511 sees 2900x2700 units only)
PROJECTION = 1100
W, H = 768, 640
POS = [(90, 160), (390, 145), (640, 165), (70, 350), (110, 500), (290, 520), (540, 420), (690, 290), (40, 600), (200, 460), (620, 240), (720, 200)]
NEG = [(390, 50), (90, 60), (690, 60), (340, 300), (190, 250), (490, 230), (690, 550), (640, 480), (290, 610), (90, 630), (750, 400),
       (710, 470), (590, 520), (210, 600), (560, 580), (730, 340)]
# the beach has two tones (a frosted lighter ring along the cliff and the water, and the darker wet pebbles around the
# wreck): SAM takes one at a time, so a second pass with points on the dark pebbles is joined to the first
DARK_POS = [(90, 430), (180, 520), (330, 545), (470, 490), (120, 330), (60, 380), (250, 470), (400, 460), (540, 440), (620, 330), (650, 220)]
DARK_NEG = [(390, 50), (340, 300), (190, 250), (490, 230), (690, 550), (290, 610), (90, 630), (710, 470), (590, 520), (210, 600), (560, 580),
            (640, 480), (750, 400)]
WRECK = [(70, 170), (300, 160), (570, 185), (590, 330), (450, 430), (180, 420), (100, 370), (50, 250)]    # traced on the art: hull, mast, spars
SPAWN_PX = (480, 455)                                   # the foreshore where Whamon drops the player, facing the beach (on the frosted strip by the ice plates)
ROTATION = 0                                            # facing +Z (up the screen)


def main(out):
    os.makedirs(out, exist_ok=True)
    full = Image.open(ART_FULL).convert('RGB'); w0, h0 = full.size; ww = round(h0 * 6 / 5); x0 = (w0 - ww) // 2
    im = np.array(full.crop((x0, 0, x0 + ww, h0))); sx, sy = ww / W, h0 / H
    cached = os.path.join(out, 'SHOR01-sam.png')
    if os.environ.get('SAM_CACHE') and os.path.exists(cached):                 # tweaking the spawn or the polygon: reuse SAM's masks
        floor = (np.array(Image.open(cached).convert('L')) > 127).astype(np.uint8); scores = np.array([0.0]); print('SAM masks from cache')
    else:
      torch.set_num_threads(16)
      pred = SamPredictor(sam_model_registry['vit_h'](checkpoint=CHECKPOINT)); pred.set_image(im)
      def segment(pos, neg):
          pts = np.array([[x * sx, y * sy] for x, y in pos + neg]); lab = np.array([1] * len(pos) + [0] * len(neg))
          masks, scores, _ = pred.predict(point_coords=pts, point_labels=lab, multimask_output=True)
          mk = masks[int(np.argmax(scores))].astype(np.float32)
          return (cv2.resize(mk, (W, H), interpolation=cv2.INTER_AREA) > 0.5).astype(np.uint8), float(scores.max())
      frost, s1 = segment(POS, NEG); dark, s2 = segment(DARK_POS, DARK_NEG)
      print(f'frost score {s1:.3f} ({int(frost.sum())} px), dark pebbles score {s2:.3f} ({int(dark.sum())} px)')
      floor = np.maximum(frost, dark); scores = np.array([max(s1, s2)])
      Image.fromarray(floor * 255).save(cached)
    floor = cv2.morphologyEx(floor, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    n, lbl, st, _ = cv2.connectedComponentsWithStats(floor)
    if n > 1: floor = (lbl == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(1 - floor)
    for i in range(1, n):
        x, y, w, h = st[i, :4]
        if x > 0 and y > 0 and x + w < W and y + h < H and st[i, cv2.CC_STAT_AREA] < 1500: floor[lbl == i] = 1
    cv2.fillPoly(floor, [np.array(WRECK, np.int32)], 0)
    print(f'beach score {scores.max():.3f}, floor pixels {int(floor.sum())}')
    Image.fromarray(floor * 255).save(os.path.join(out, 'SHOR01-floor.png'))

    m = base_map('FRZL03', *CAMERA); m.projection = PROJECTION; cam = Cam(m)
    col = [0x80] * 10000
    for tx, tz, u, v in cam.tiles():
        if u is None or not (0 <= u < W and 0 <= v < H): continue
        if floor[v, u]: col[tz * 100 + tx] = 0
    m.collision = col
    spawn = cam.world(*SPAWN_PX)
    m.warps[0].update({'x': spawn[0], 'z': spawn[1], 'rotation': ROTATION, 'targetMap': -1, 'targetExit': -1})   # script use: Whamon
    tx, tz = int(spawn[0] / 100) + 50 - (1 if spawn[0] < 0 else 0), 49 - int(spawn[1] / 100) + (1 if spawn[1] < 0 else 0)
    if col[tz * 100 + tx]: sys.exit(f'the arrival at {spawn} (tile {tx},{tz}) is not free')
    check_arrivals(m, 'SHOR01')
    R = reach.from_spawn_coordinates(m, starts=[spawn])
    json.dump({'camera': list(CAMERA), 'projection': PROJECTION, 'collision': col, 'warps': m.warps}, open(DATA, 'w'))
    print(f'SHOR01: free tiles {col.count(0)}, arrival {spawn} px {SPAWN_PX}, reach {len(R)}')
    bg = np.array(Image.open(ART).convert('RGB'))
    rp = np.zeros((H, W), np.uint8)
    for x, z in R:
        p = cam.pixel(x, z)
        if p and 0 <= p[0] < W and 0 <= p[1] < H: rp[p[1], p[0]] = 1
    rp = cv2.dilate(rp, np.ones((3, 3), np.uint8)); ov = bg.copy(); ov[rp > 0] = (0, 200, 0)
    img = (bg * 0.55 + ov * 0.45).astype(np.uint8)
    cv2.circle(img, SPAWN_PX, 4, (255, 255, 255), -1)
    Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, 'SHOR01-zones.png'))


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
