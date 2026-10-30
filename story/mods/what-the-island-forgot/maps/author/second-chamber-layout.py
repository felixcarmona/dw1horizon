#!/usr/bin/env python3
"""Authoring of the Second Chamber (screen 304, files SHRN01), run by hand (needs numpy, cv2, torch and Segment
Anything): the walkable platform is segmented from our art itself (SAM on the full-resolution picture, positive points
on the floor, negative points on the back wall, the pedestal, the mist and the crystals), the crystals that rise in
front of the platform's edge are taken out of it by colour, the pedestal's footprint is blocked. Writes
maps/second-chamber-data.json (collision, exits) for the build-time recipe maps/second-chamber.py, and
OUT_DIR/SHRN01-zones.png (green: the real reach, blue: exit tiles, white: arrival points).

    SAM_CHECKPOINT=path/to/sam_vit_h_4b8939.pth python3 author/second-chamber-layout.py OUT_DIR
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
from mapbase import base_map, Cam, reachable, MOD

ART_FULL = os.path.join(MOD, 'art', 'full', 'second-chamber-2304x1856.png')
ART = os.path.join(MOD, 'art', 'second-chamber.png')                 # 640x512
DATA = os.path.join(MOD, 'maps', 'second-chamber-data.json')
CHECKPOINT = os.environ.get('SAM_CHECKPOINT', os.path.join(MOD, '..', '..', '..', 'build', 'new-maps', 'models', 'sam_vit_h_4b8939.pth'))
CAMERA = (4320, 60)                                     # LEOM01's: eye 4320 from the look-at point, 60 degrees down
W, H = 640, 512
# points in 640x512 pixels: on the platform, and on what is not the platform (the back wall, the pedestal, the mist,
# the crystals)
POS = [(320, 300), (150, 230), (480, 230), (220, 420), (430, 400), (560, 320), (90, 330), (320, 195), (610, 300),
       (420, 170), (200, 170), (330, 450), (560, 240)]
NEG = [(320, 70), (120, 60), (540, 60), (40, 100), (318, 140), (318, 180), (30, 490), (600, 490), (320, 500),
       (630, 180), (630, 440), (80, 470), (590, 430), (10, 300), (470, 480), (20, 220)]
PEDESTAL = (282, 150, 358, 202)                         # box: the pedestal's footprint, never walkable
EXIT = (612, 245, 640, 345)                             # box: the tiles that lead back to the hall of the shrine
EXITS = [
    {'warp': 0, 'target': (113, 1), 'spawn': (566, 295), 'rotation': 3072},   # LEOM01's new west exit (arriving: facing the chamber, screen-left)
]


def crystals(bg):
    """the glowing green crystals (by colour), grown a little: they are drawn in front of the platform's edge."""
    hsv = cv2.cvtColor(bg, cv2.COLOR_RGB2HSV)
    m = ((hsv[..., 0] > 40) & (hsv[..., 0] < 90) & (hsv[..., 1] > 90) & (hsv[..., 2] > 110)).astype(np.uint8)
    return cv2.dilate(m, np.ones((7, 7), np.uint8))


def main(out):
    os.makedirs(out, exist_ok=True)
    im = np.array(Image.open(ART_FULL).convert('RGB')); h0, w0 = im.shape[:2]; sx, sy = w0 / W, h0 / H
    torch.set_num_threads(16)
    pred = SamPredictor(sam_model_registry['vit_h'](checkpoint=CHECKPOINT)); pred.set_image(im)
    pts = np.array([[x * sx, y * sy] for x, y in POS + NEG]); lab = np.array([1] * len(POS) + [0] * len(NEG))
    masks, scores, _ = pred.predict(point_coords=pts, point_labels=lab, multimask_output=True)
    mk = masks[int(np.argmax(scores))].astype(np.float32)
    floor = (cv2.resize(mk, (W, H), interpolation=cv2.INTER_AREA) > 0.5).astype(np.uint8)
    floor = cv2.morphologyEx(floor, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    n, lbl, st, _ = cv2.connectedComponentsWithStats(floor)
    if n > 1: floor = (lbl == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])).astype(np.uint8)   # the platform, one piece
    n, lbl, st, _ = cv2.connectedComponentsWithStats(1 - floor)                             # holes (the dark engravings SAM leaves out) are floor
    for i in range(1, n):
        x, y, w, h = st[i, :4]
        if x > 0 and y > 0 and x + w < W and y + h < H: floor[lbl == i] = 1
    bg = np.array(Image.open(ART).convert('RGB'))
    cr = crystals(bg); floor[cr > 0] = 0
    px0, py0, px1, py1 = PEDESTAL; floor[py0:py1, px0:px1] = 0
    print(f'floor score {scores.max():.3f}, pixels {int(floor.sum())}, crystal pixels {int(cr.sum())}')

    m = base_map('LEOM01', *CAMERA); m.projection = 772; cam = Cam(m)
    ex0, ey0, ex1, ey1 = EXIT
    col = [0x80] * 10000
    for tx, tz, u, v in cam.tiles():
        if u is None or not (0 <= u < W and 0 <= v < H): continue
        if floor[v, u]: col[tz * 100 + tx] = 110 if (ex0 <= u <= ex1 and ey0 <= v <= ey1) else 0
    m.collision = col
    for e in EXITS:
        x, z = cam.world(*e['spawn'])
        m.warps[e['warp']].update({'x': x, 'z': z, 'rotation': e['rotation'], 'targetMap': e['target'][0], 'targetExit': e['target'][1]})
    R = reachable(m)
    for e in EXITS:
        x, z = cam.world(*e['spawn'])
        if (round(x / 10) * 10, round(z / 10) * 10) not in R: sys.exit(f'the spawn of warp {e["warp"]} is not reachable')
    json.dump({'camera': list(CAMERA), 'projection': 772, 'collision': col, 'warps': m.warps}, open(DATA, 'w'))
    print(f'SHRN01: free tiles {col.count(0)}, exit tiles {col.count(110)}, reach {len(R)}')
    # the check image
    rp = np.zeros((H, W), np.uint8); ex = np.zeros((H, W), np.uint8)
    for x, z in R:
        p = cam.pixel(x, z)
        if p and 0 <= p[0] < W and 0 <= p[1] < H: rp[p[1], p[0]] = 1
    for tx, tz, u, v in cam.tiles():
        if u is not None and 110 <= col[tz * 100 + tx] < 120 and 0 <= u < W and 0 <= v < H: cv2.circle(ex, (u, v), 4, 1, -1)
    rp = cv2.dilate(rp, np.ones((3, 3), np.uint8)); ov = bg.copy(); ov[rp > 0] = (0, 200, 0); ov[ex > 0] = (0, 80, 255)
    img = (bg * 0.55 + ov * 0.45).astype(np.uint8)
    for e in EXITS: cv2.circle(img, e['spawn'], 4, (255, 255, 255), -1)
    Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, 'SHRN01-zones.png'))


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
