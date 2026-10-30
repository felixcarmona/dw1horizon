"""Side-by-side video over several screens of different sizes: the game recording (left) and the zones image of the
screen the player is on (right, padded to a fixed width) with his logged position as a dot and a trail. Usage:
  overlayvideo3.py GAME.mp4 POSLOG.json SCALE:OFFSET_S OUT.mp4 SCREEN=MAP,ZONES.png [...] [--skip A:B] [--step N]
--skip drops the video seconds A..B (a frozen dialog); --step keeps one frame in N (and divides the fps)."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import sys, json, subprocess, tempfile, os
import numpy as np, cv2
from tools.image import Image
import os
sys.path.insert(0, os.path.join(_DEV_ROOT, 'tools'))
import dwmap

args = sys.argv[1:]; skip = None; step = 1
if '--skip' in args: i = args.index('--skip'); skip = tuple(float(v) for v in args[i + 1].split(':')); del args[i:i + 2]
if '--step' in args: i = args.index('--step'); step = int(args[i + 1]); del args[i:i + 2]
game, plog, out = args[0], args[1], args[3]
scale, off = (float(v) for v in args[2].split(':'))      # video time = scale * log time + off
SCR = {}
for a in args[4:]:
    k, v = a.split('='); mp, zp = v.split(',')
    m = dwmap.MapFile(open(mp, 'rb').read())
    SCR[int(k)] = (m, dwmap.camera_basis(m), np.array(Image.open(zp).convert('RGB')))
log = json.load(open(plog))
cap = cv2.VideoCapture(game); fps = cap.get(cv2.CAP_PROP_FPS) or 25
tmp = tempfile.mkdtemp(); k = 0; n = 0; H = 576; RW = 720
while True:
    ok, fr = cap.read()
    if not ok: break
    tv = n / fps; n += 1
    if skip and skip[0] <= tv < skip[1]: continue
    if (n - 1) % step: continue
    t = (tv - off) / scale
    past = [p for p in log if p[0] <= t]
    cur = past[-1] if past else None
    right = np.zeros((H, RW, 3), np.uint8)
    if cur and cur[3] in SCR:
        m, basis, zones = SCR[cur[3]]; z = zones.copy()
        visit = []
        for p in reversed(past):
            if p[3] != cur[3]: break
            visit.append(p)
        pts = [dwmap.project(m, basis, (p[1], 0, p[2])) for p in reversed(visit)]
        pts = [(int(q[0] * 2), int(q[1] * 2)) for q in pts if q]
        for a, b in zip(pts, pts[1:]): cv2.line(z, a, b, (255, 255, 255), 2)
        if pts:
            cv2.circle(z, pts[-1], 10, (255, 0, 255), -1); cv2.circle(z, pts[-1], 10, (0, 0, 0), 2)
        zh, zw = z.shape[:2]; s = min(H / zh, RW / zw); zi = cv2.resize(cv2.cvtColor(z, cv2.COLOR_RGB2BGR), (int(zw * s), int(zh * s)))
        y0 = (H - zi.shape[0]) // 2; x0 = (RW - zi.shape[1]) // 2; right[y0:y0 + zi.shape[0], x0:x0 + zi.shape[1]] = zi
        cv2.putText(right, 'pantalla %d' % cur[3], (16, H - 16), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    elif cur:
        cv2.putText(right, 'SALIDA -> pantalla %d' % cur[3], (120, H // 2), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)
    left = cv2.resize(fr, (int(fr.shape[1] * H / fr.shape[0]), H))
    frame = np.hstack([left, right]); frame = frame[:, :frame.shape[1] // 2 * 2]
    cv2.imwrite(f'{tmp}/{k:05d}.png', frame); k += 1
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-framerate', str(fps / step), '-i', f'{tmp}/%05d.png', '-pix_fmt', 'yuv420p',
                '-crf', '30', out], check=True)
subprocess.run(['rm', '-rf', tmp])
print(out, k, 'frames')
