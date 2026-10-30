
# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import os, sys, subprocess
from tools.image import Image
sys.path.insert(0, '.')
from jobs import *
only = sys.argv[1:]
def prep(name, crop=None):
    im = Image.open(f'{name}.png').convert('RGB')
    if crop: im = im.crop(crop)
    w, h = im.size
    if True:   # pad to 16:9 (2:1 banners) or 21:9 (the 4:1 grade logos)
        H = round(w * 9 / 16) if crop is None else round(w * 9 / 21); c = Image.new('RGB', (w, H), im.getpixel((0, h - 1))); c.paste(im, (0, (H - h) // 2)); im = c
    im = im.resize((im.width * 4, im.height * 4), Image.LANCZOS); p = f'ref_{name}{"_top" if crop else ""}.png'; im.save(p); return p
def gen(out, prompt, ref, aspect):
    if os.path.exists(out) or (only and out not in only): return
    open(out + '.txt', 'w').write(prompt)
    r = subprocess.run([sys.executable, 'gen.py', out + '.txt', out, '--ref', ref, '--aspect', aspect, '--size', '1K'], capture_output=True, text=True)
    print(out, r.stdout.strip()[:80], r.stderr.strip()[-200:], flush=True)
for k, (style, en, es, lines) in CUPS.items():
    ref = prep(k)
    gen(f'gen_en_{k}.png', CUP_EN.format(style=style, word=en), ref, '16:9')
    ls = '; '.join(f'"{a}" -> "{b}"' for a, b in lines.items())
    gen(f'gen_es_{k}.png', CUP_ES.format(style=style, word=es, lines=ls), ref, '16:9')
for g in GRADES:
    ref = prep(f'GRADE{g}', (0, 0, 256, 64))
    gen(f'gen_en_GRADE{g}.png', GRADE_EN.format(g=g), ref, '21:9')
    gen(f'gen_es_GRADE{g}.png', GRADE_ES.format(g=g), ref, '21:9')
