
# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
# SPDX-License-Identifier: MIT
from pathlib import Path
"""Zones image for the overlay video: the background with the real reach (reach.py) green, exit tiles blue, spawns
white, at 2x. Usage: zonesimg.py MAP BG.png OUT.png"""
import sys, os, numpy as np, cv2
from tools.image import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import reach, dwmap
mp, bgp, out = sys.argv[1:4]
m = dwmap.MapFile(open(mp, 'rb').read()); basis = dwmap.camera_basis(m)
bg = np.array(Image.open(bgp).convert('RGB')); H, W = bg.shape[:2]
rp = np.zeros((H, W), np.uint8); ex = np.zeros((H, W), np.uint8)
for x, z in reach.reach(m):
    p = dwmap.project(m, basis, (x, 0, z))
    if p and 0 <= int(p[0]) < W and 0 <= int(p[1]) < H: rp[int(p[1]), int(p[0])] = 1
for i, c in enumerate(m.collision):
    if 110 <= c < 120:
        tx, tz = i % 100, i // 100
        p = dwmap.project(m, basis, ((tx - 50) * 100 + 50, 0, (49 - tz) * 100 + 50))
        if p and 0 <= int(p[0]) < W and 0 <= int(p[1]) < H: cv2.circle(ex, (int(p[0]), int(p[1])), 4, 1, -1)
rp = cv2.dilate(rp, np.ones((3, 3), np.uint8))
ov = bg.copy(); ov[rp > 0] = (0, 200, 0); ov[ex > 0] = (0, 80, 255)
img = (bg * 0.55 + ov * 0.45).astype(np.uint8)
for w in m.warps:
    if w['targetMap'] != -1:
        p = dwmap.project(m, basis, (w['x'], 0, w['z']))
        if p: cv2.circle(img, (int(p[0]), int(p[1])), 4, (255, 255, 255), -1)
Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST).save(out)
print(out)
