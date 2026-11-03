"""uvmap.py DONOR: texture page x4 with every primitive's UV outline (colour by object) and tex-anim rects."""
from lib import *
import sys
b = Baby('uv', int(sys.argv[1]))
S = 4
img = cv2.resize(cv2.cvtColor(b.tex, cv2.COLOR_RGBA2BGR), None, fx=S, fy=S, interpolation=cv2.INTER_NEAREST)
cols = [(0, 255, 0), (255, 0, 255), (0, 255, 255), (255, 128, 0), (0, 128, 255), (255, 255, 0), (128, 255, 128), (255, 128, 255), (128, 128, 255)]
for oi, ob in enumerate(b.m.tmd.objects):
    for p in ob.prims:
        d = p.decode(); uv = d['uv']
        pts = np.array([(u * S + 2, v * S + 2) for u, v in (uv if len(uv) == 3 else [uv[0], uv[1], uv[3], uv[2]])], np.int32)
        cv2.polylines(img, [pts], True, cols[oi % len(cols)], 1)
for (sx, sy, w, h), (dx, dy) in b.tex_anims():
    cv2.rectangle(img, (dx * S, dy * S), ((dx + w) * S, (dy + h) * S), (0, 0, 255), 2)
    cv2.putText(img, f'{sx},{sy}', (dx * S + 2, dy * S + 12), 0, 0.35, (0, 0, 255), 1)
cv2.imwrite(os.path.join(OUT, f'uv-{sys.argv[1]}.png'), img[:int(sys.argv[2]) * S if len(sys.argv) > 2 else None])
print(b.tex_anims())
