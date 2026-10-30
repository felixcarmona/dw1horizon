#!/usr/bin/env python3
"""A contact sheet of a walk video: N frames evenly spaced (plus one at every screen change found in the poslog, if
given), each labelled with its time and the screen, so a video can be checked without watching it.
    framesheet.py VIDEO.mp4 OUT.png [N=12] [POSLOG.json] [SCALE:OFFSET=1.0:2.0]"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import json, subprocess, sys, tempfile, os
from tools.image import Image, ImageDraw

video, out = sys.argv[1], sys.argv[2]
n = int(sys.argv[3]) if len(sys.argv) > 3 else 12
plog = sys.argv[4] if len(sys.argv) > 4 else None
scale, off = (float(v) for v in (sys.argv[5] if len(sys.argv) > 5 else '1.0:2.0').split(':'))
dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', video], capture_output=True, text=True).stdout.strip())
times = [dur * (i + 0.5) / n for i in range(n)]
labels = {}
if plog:
    log = json.load(open(plog)); prev = None
    for t, x, z, s in log:
        if s != prev:
            tv = scale * t + off + 4.0                           # four seconds after the change: past the caption
            if 0 < tv < dur: times.append(tv); labels[round(tv, 2)] = f'screen {s}'
            prev = s
times = sorted(set(round(t, 2) for t in times))
tmp = tempfile.mkdtemp(); frames = []
for t in times:
    f = os.path.join(tmp, f'{t:.2f}.png')
    subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(t), '-i', video, '-frames:v', '1', '-y', f])
    if os.path.exists(f): frames.append((t, Image.open(f).convert('RGB')))
if not frames: sys.exit('no frames')
w, h = frames[0][1].size; cols = 4; rows = (len(frames) + cols - 1) // cols
tw = 640 if w > 640 else w; th = round(h * tw / w)
sheet = Image.new('RGB', (cols * tw, rows * th), (0, 0, 0)); d = ImageDraw.Draw(sheet)
for i, (t, im) in enumerate(frames):
    im = im.resize((tw, th), Image.LANCZOS); x, y = (i % cols) * tw, (i // cols) * th
    sheet.paste(im, (x, y)); d.rectangle((x, y, x + 170, y + 16), fill=(0, 0, 0))
    d.text((x + 4, y + 2), f't={t:.0f}s {labels.get(round(t, 2), "")}', fill=(255, 255, 0))
sheet.save(out); print(out, sheet.size, len(frames), 'frames, video', round(dur), 's')
