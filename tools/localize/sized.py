"""Our art scaled to the size the build uses it at (the developer's: signs.py --make-cutouts, build.py --make-deltas;
docs/derive.md, stage 9).

    rgb_at(src, size, folder, make=False, notes=None) -> [(r, g, b)] row-major, size[0] x size[1]

`src` may be PNG or JPEG. Sized copies are keyed by the source SHA-1 and retain
historical decoded pixels and PNG encoding. The local raster module reproduces
8-bit RGB LANCZOS; JPEG decoding uses OpenCV and may vary by codec version. Keep
existing sized copies rather than silently replacing accepted pixels. The game
reads only committed cut-outs/deltas; full art and sized copies stay private in
build/localized-src. --make-sized verifies regenerated pixels against each cached
copy, retaining its exact file bytes, and fails on drift for deliberate review.
"""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _png_read(path):
    if os.path.join(ROOT, 'tools') not in sys.path:
        sys.path.insert(0, os.path.join(ROOT, 'tools'))
    import dwmap
    return dwmap.png_read(path)


def rgb_at(src, size, folder, make=False, notes=None):
    raw = open(src, 'rb').read()
    name = os.path.splitext(os.path.basename(src))[0]
    w, h = size
    path = os.path.join(folder, f'{name}-{hashlib.sha1(raw).hexdigest()[:12]}.png')
    if os.path.isfile(path):
        pw, ph, mode, rows, pal = _png_read(path)
        if (pw, ph) == (w, h) and mode == 'RGB':
            return [tuple(r[3 * x:3 * x + 3]) for r in rows for x in range(w)]
    from tools.image import Image        # (the developer's path only: a sized copy is missing or stale)
    im = Image.open(src).convert('RGB').resize((w, h), Image.LANCZOS)
    if make:
        os.makedirs(folder, exist_ok=True)
        for old in os.listdir(folder):
            if old.rsplit('-', 1)[0] == name and old != os.path.basename(path):
                os.remove(os.path.join(folder, old))
        im.save(path)
    elif notes is not None:
        notes.append(os.path.relpath(src, ROOT))
    return [im.getpixel((x, y)) for y in range(h) for x in range(w)]


def main():
    import argparse
    from pathlib import Path
    from tools.image import Image
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--make-sized', action='store_true', required=True,
                        help='regenerate and verify existing sized rasters, retaining their PNG bytes')
    parser.add_argument('--src', type=Path, default=Path(ROOT)/'build/localized-src')
    args = parser.parse_args()
    checked = 0
    for family in ('signs', 'tournament'):
        base = args.src/family
        for cache in sorted((base/'sized').glob('*/*.png')):
            name, key = cache.stem.rsplit('-', 1)
            sources = [p for p in (base/cache.parent.name).glob(name+'.*')
                       if p.suffix.lower() in ('.png', '.jpg', '.jpeg')
                       and hashlib.sha1(p.read_bytes()).hexdigest()[:12] == key]
            if len(sources) != 1:
                parser.error(f'{cache}: expected one matching source, found {len(sources)}')
            saved = Image.open(cache).convert('RGB')
            regenerated = Image.open(sources[0]).convert('RGB').resize(saved.size, Image.LANCZOS)
            if regenerated.tobytes() != saved.tobytes():
                parser.exit(1, f'{cache}: historical raster differs; retained. Review codec/source history before accepting new art.\n')
            checked += 1
    if not checked: parser.error('no sized copies found')
    print(f'{checked} sized rasters regenerated exactly; existing PNG file bytes retained')


if __name__ == '__main__':
    main()
