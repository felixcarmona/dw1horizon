
# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
# SPDX-License-Identifier: MIT
from pathlib import Path
"""Tile grid of a map over its art at 4x: each collision tile as its projected quad (green free, blue exit,
yellow trigger; blocked tiles retain the art), with its tile coords. Usage: grid.py MAP ART.png OUT.png [x0 y0 x1 y1 crop in 640 px]"""
import sys, numpy as np, cv2
from tools.image import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dwmap
mp, art, out = sys.argv[1:4]
K = 4
W0, H0 = Image.open(art).size                       # the background's own size (640x512, or 768x640 for MGEN maps)
crop = list(map(int, sys.argv[4:8])) if len(sys.argv) > 4 else [0, 0, W0, H0]
m = dwmap.MapFile(open(mp, 'rb').read()); b = dwmap.camera_basis(m)
bg = np.array(Image.open(art).convert('RGB').resize((W0 * K, H0 * K), Image.LANCZOS))
ov = bg.copy(); lines = []
for i, c in enumerate(m.collision):
    tx, tz = i % 100, i // 100
    pts = [dwmap.project(m, b, ((tx - 50) * 100 + dx, 0, (49 - tz) * 100 + dz)) for dx, dz in ((0, 0), (100, 0), (100, 100), (0, 100))]
    if not all(pts): continue
    q = np.array([(p[0] * K, p[1] * K) for p in pts], np.int32)
    if q[:, 0].max() < 0 or q[:, 0].min() > W0 * K or q[:, 1].max() < 0 or q[:, 1].min() > H0 * K: continue
    if c == 0: col = (0, 220, 0)
    elif 110 <= c < 120: col = (0, 90, 255)
    elif c & 0x80: col = None
    else: col = (255, 255, 0)
    if col: cv2.fillPoly(ov, [q], col)
    lines.append((q, c, tx, tz))
img = (bg * 0.6 + ov * 0.4).astype(np.uint8)
for q, c, tx, tz in lines:
    if c == 0 or 110 <= c < 120:
        cv2.polylines(img, [q], True, (255, 255, 255), 1)
        if (tx % 2 == 0 and tz % 2 == 0):
            cx, cy = q.mean(0).astype(int)
            cv2.putText(img, f'{tx},{tz}', (cx - 14, cy + 3), cv2.FONT_HERSHEY_PLAIN, 0.7, (255, 255, 255), 1)
x0, y0, x1, y1 = [v * K for v in crop]
Image.fromarray(img[y0:y1, x0:x1]).save(out); print(out)
