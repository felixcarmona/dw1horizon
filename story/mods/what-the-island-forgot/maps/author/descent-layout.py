#!/usr/bin/env python3
"""Authoring of the Descent (screen 303), run by hand (needs numpy, cv2, torch and Segment Anything): the walkable
ledge is segmented from our art itself (SAM on the full-resolution picture, positive points along the ledge, negative
points on the rock lips between the switchbacks and on the walls), so the collision follows the drawn ledge, not a
hand-typed line. Writes maps/descent-data.json (collision, exits) for the build-time recipe maps/descent.py, and
OUT_DIR/DESC01-zones.png (green: the real reach, blue: exit tiles, white: arrival points).

    SAM_CHECKPOINT=path/to/sam_vit_h_4b8939.pth python3 author/descent-layout.py OUT_DIR
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
from mapbase import base_map, import_png, Cam, reachable, dwmap, MOD
import struct

ART_FULL = os.environ.get('DESCENT_FULL', os.path.join(MOD, '..', '..', '..', 'build', 'new-maps', 'P4-el-descenso', 'el-descenso-1856x2304.jpg'))
ART = os.path.join(MOD, 'art', 'descent.png')                   # 640x768: the middle 768/800 of the full picture
DATA = os.path.join(MOD, 'maps', 'descent-data.json')
CHECKPOINT = os.environ.get('SAM_CHECKPOINT', os.path.join(MOD, '..', '..', '..', 'build', 'new-maps', 'models', 'sam_vit_h_4b8939.pth'))
CAMERA = (7000, 61)
W, H = 640, 768
# points in 640x768 pixels: on the ledge, and on what is not the ledge (the rock lips between the switchbacks, the walls)
POS = [(320, 165), (200, 220), (150, 270), (250, 290), (350, 300), (450, 300), (500, 330), (490, 400), (380, 410),
       (250, 410), (190, 470), (250, 520), (380, 530), (430, 590), (330, 640), (320, 700)]
NEG = [(300, 230), (380, 245), (330, 340), (400, 360), (300, 480), (360, 490), (60, 300), (590, 300), (100, 600),
       (560, 600), (330, 60), (150, 150), (520, 180), (560, 460), (120, 480), (470, 150)]
UP = (280, 40, 370, 150)                                # box: the rock steps at the top lead up to the canyon
# ground SAM leaves out, walkable all the same: the left end of the
# first switchback, the pocket at the right end of the second lip, the strip down the right of the last turn; and the
# pale rock shelf under the steps (walkable behind its picture, below)
EXTRA = [[(112, 150), (215, 145), (220, 235), (118, 240)], [(437, 345), (495, 345), (495, 400), (437, 400)],
         [(430, 540), (462, 540), (462, 632), (430, 632)], [(272, 150), (358, 150), (362, 205), (276, 208)]]
# and what is never walkable although SAM or the polygons above take it: the top rim
# of the first switchback, the shelf itself and the lip under it, the pocket at the right edge of the first switchback,
# the corner at the end of the second lip, the shadowed floor left of the way out
WALLS = [[(112, 110), (222, 110), (222, 150), (112, 183)], [(272, 164), (382, 164), (382, 210), (272, 210)],
         [(203, 203), (232, 203), (232, 242), (203, 242)], [(428, 340), (460, 340), (460, 374), (428, 374)],
         [(214, 590), (328, 590), (300, 688), (214, 688)]]
# and, last, the room that eases the passage: the top band of the first
# switchback, the strip between the steps and the shelf, the pockets under the lips' tips, the corners of the turns,
# the right of the last descent, the left of the way out (a tile wider than the marks: the body box eats a tile)
EXTRA2 = [[(140, 158), (200, 136), (226, 138), (226, 162), (168, 188), (140, 186)], [(258, 146), (345, 146), (345, 178), (258, 178)],
          [(182, 230), (226, 230), (226, 262), (182, 262)], [(448, 322), (476, 322), (476, 390), (448, 390)],
          [(162, 415), (214, 415), (214, 466), (162, 466)], [(193, 468), (226, 468), (226, 504), (193, 504)],
          [(425, 528), (480, 528), (480, 628), (425, 628)], [(286, 616), (344, 616), (344, 698), (286, 698)],
          [(276, 694), (320, 694), (320, 738), (276, 738)]]
# the pale rock shelf under the steps is drawn over the character: a foreground piece, its depth
# at its lower edge, so whoever comes down the steps passes behind it
SHELF = (272, 148, 366, 208)                            # box for SAM, 640x768 px
OPENING = (270, 735, 380, 768)                          # box: the tiles that lead down to the Rift
EXITS = [
    {'warp': 0, 'target': (42, 1), 'spawn': (262, 172), 'rotation': 2048},      # up: Great Canyon Bottom Area, the crack (arriving: past the shelf on its left, facing down the ledge)
    {'warp': 1, 'target': (301, 0), 'spawn': (320, 690), 'rotation': 0},        # down: the Rift, the top of its ramp (arriving: facing up)
]


def main(out):
    os.makedirs(out, exist_ok=True)
    im = np.array(Image.open(ART_FULL).convert('RGB')); h0, w0 = im.shape[:2]
    th = round(h0 * 768 / 800); top = (h0 - th) // 2; sc = w0 / 640
    torch.set_num_threads(16)
    pred = SamPredictor(sam_model_registry['vit_h'](checkpoint=CHECKPOINT)); pred.set_image(im)
    pts = np.array([[x * sc, y * sc + top] for x, y in POS + NEG]); lab = np.array([1] * len(POS) + [0] * len(NEG))
    masks, scores, _ = pred.predict(point_coords=pts, point_labels=lab, multimask_output=True)
    mk = masks[int(np.argmax(scores))].astype(np.float32)[top:top + th, :]
    floor = (cv2.resize(mk, (W, H), interpolation=cv2.INTER_AREA) > 0.5).astype(np.uint8)
    floor = cv2.morphologyEx(floor, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    n, lbl, st, _ = cv2.connectedComponentsWithStats(floor)
    if n > 1: floor = (lbl == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])).astype(np.uint8)   # the ledge, one piece
    for poly in EXTRA: cv2.fillPoly(floor, [np.array(poly, np.int32)], 1)
    for poly in WALLS: cv2.fillPoly(floor, [np.array(poly, np.int32)], 0)
    for poly in EXTRA2: cv2.fillPoly(floor, [np.array(poly, np.int32)], 1)
    print(f'floor score {scores.max():.3f}, pixels {int(floor.sum())}')

    m = base_map('GCAN01', *CAMERA); m.projection = 772; cam = Cam(m)
    ux0, uy0, ux1, uy1 = UP; ox0, oy0, ox1, oy1 = OPENING
    col = [0x80] * 10000
    for tx, tz, u, v in cam.tiles():
        if u is None or not (0 <= u < W and 0 <= v < H): continue
        if ux0 <= u <= ux1 and uy0 <= v <= uy1: col[tz * 100 + tx] = 110
        elif floor[v, u]: col[tz * 100 + tx] = 111 if (ox0 <= u <= ox1 and oy0 <= v <= oy1) else 0
    m.collision = col
    for e in EXITS:
        x, z = cam.world(*e['spawn'])
        m.warps[e['warp']].update({'x': x, 'z': z, 'rotation': e['rotation'], 'targetMap': e['target'][0], 'targetExit': e['target'][1]})
    R = reachable(m)
    for e in EXITS:
        x, z = cam.world(*e['spawn'])
        if (round(x / 10) * 10, round(z / 10) * 10) not in R: sys.exit(f'the spawn of warp {e["warp"]} is not reachable')
    # the shelf as a foreground piece: SAM cut, pixels in sprite TIM 0 (VRAM 384: texX 0..), definition 0, instance 0
    bx0, by0, bx1, by1 = SHELF
    masks, scores, _ = pred.predict(box=np.array([bx0 * sc, by0 * sc + top, bx1 * sc, by1 * sc + top]), multimask_output=True)
    sm = masks[int(np.argmax(scores))].astype(np.float32)[top:top + th, :]
    shelf = (cv2.resize(sm, (W, H), interpolation=cv2.INTER_AREA) > 0.5).astype(np.uint8)
    box = np.zeros_like(shelf); box[by0:by1, bx0:bx1] = 1; shelf &= box
    n, lbl, st, _ = cv2.connectedComponentsWithStats(shelf)
    if n > 1: shelf = (lbl == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    ys, xs = np.nonzero(shelf); x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
    w = x1 - x0 + ((x1 - x0) % 2); h = y1 - y0
    bg = np.array(Image.open(ART).convert('RGB'))
    tfs_tmp = os.path.join(out, '_palette.TFS'); import_png('GCAN01', ART, tfs_tmp)
    tfs = dwmap.TfsFile(open(tfs_tmp, 'rb').read()); rq = dwmap.Requant([dwmap.bgr555_to_rgb(c) for c in tfs.cluts[0]], tfs.cluts[0])
    raw = bytearray(m.tims[0]); clut_len = struct.unpack_from('<I', raw, 8)[0]; p = 8 + clut_len + 12
    pix = np.zeros((256, 256), np.uint8)
    for yy in range(h):
        for xx in range(min(w, W - x0)):
            if shelf[y0 + yy, x0 + xx]: pix[yy, xx] = rq(*(int(c) for c in bg[y0 + yy, x0 + xx]))
    raw[p:p + 256 * 256] = pix.tobytes(); m.tims[0] = bytes(raw)
    gx, gz = cam.world((x0 + x1) // 2, y1 - 1)
    m.sprites[0] = {'texX': 0, 'texY': 0, 'width': w, 'height': h, 'x': gx, 'y': 0, 'z': gz, 'clut': -1, 'transparency': 4}
    m.instances[0] = {'frames': [0, -1, -1, -1, -1, -1, -1, -1], 'times': [0] * 8, 'x': x0, 'y': y0, 'flag': 0}
    print(f'shelf piece: px ({x0},{y0}) {w}x{h}, depth ({gx},{gz}), score {scores.max():.3f}')
    json.dump({'camera': list(CAMERA), 'projection': 772, 'collision': col, 'warps': m.warps, 'sprites': m.sprites,
               'instances': m.instances, 'tims': [list(m.tims[0])]}, open(DATA, 'w'))
    cut = bg[y0:y1, x0:x1].copy(); cut[shelf[y0:y1, x0:x1] == 0] = (255, 0, 255)
    Image.fromarray(cut).resize(((x1 - x0) * 4, (y1 - y0) * 4), Image.NEAREST).save(os.path.join(out, 'DESC01-shelf-piece.png'))
    print(f'DESC01: free tiles {col.count(0)}, up tiles {col.count(110)}, opening tiles {col.count(111)}, reach {len(R)}')
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
    cs, _ = cv2.findContours(shelf, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE); cv2.drawContours(img, cs, -1, (0, 255, 255), 1)
    Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, 'DESC01-zones.png'))


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
