"""montage.py OUT.mp4 file:start:dur:caption ... -> captioned concatenation (640x480, 30 fps). Needs OpenCV for captions."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import subprocess, sys, os, tempfile
from tools.image import Image, ImageDraw, ImageFont
out = sys.argv[1]; parts = []
tmp = tempfile.mkdtemp(dir=os.path.dirname(os.path.abspath(out)))
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 17)
for i, spec in enumerate(sys.argv[2:]):
    f, ss, dur, cap = spec.split(':', 3)
    im = Image.new('RGBA', (640, 480), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle((0, 444, 640, 480), fill=(0, 0, 0, 160))
    d.text((12, 450), cap, font=font, fill=(255, 255, 255, 255))
    png = os.path.join(tmp, f'{i:02d}.png'); im.save(png)
    p = os.path.join(tmp, f'{i:02d}.mp4')
    subprocess.check_call(['ffmpeg', '-loglevel', 'error', '-y', '-ss', ss, '-t', dur, '-i', f, '-i', png, '-an',
                           '-filter_complex', '[0:v]scale=640:480,fps=30[v];[v][1:v]overlay=0:0',
                           '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '28', '-preset', 'slow', p])
    os.remove(png); parts.append(p)
lst = os.path.join(tmp, 'list.txt')
open(lst, 'w').write(''.join(f"file '{p}'\n" for p in parts))
subprocess.check_call(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', out])
for p in parts: os.remove(p)
os.remove(lst); os.rmdir(tmp)
print(out)
