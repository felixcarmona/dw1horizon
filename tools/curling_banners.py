#!/usr/bin/env python3
"""The curling cups' banners (docs/mods/curling.md): KARCUP.DAT from content/localized/curling/<lang>.png.

  curling_banners.py OUT               KARCUP.DAT (pack(); the derive step `curling`, no Pillow)
  curling_banners.py --make [SRC]      the developer's: SRC/<lang>.png (the generator's sheets of five bands, default
                                       build/localized-src/curling) -> content/localized/curling/<lang>.png (Pillow)

A committed sheet is 256 x 200 RGB: five bands of 256 x 40, each with at most 128 colours of 15 bits. The file holds,
for each language in the game's order, 26 sectors: five rows of 128 colours (16 bits), then the five bands (8 bits a
pixel). A language with no sheet takes the English one.
"""
import os, struct, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
ART = os.path.join(ROOT, 'content', 'localized', 'curling')
W, H, BANDS, COLOURS, SECTORS = 256, 40, 5, 128, 26


def colour(r, g, b):
    """15 bits; black is kept opaque (0 is the transparent colour)"""
    return (r >> 3) | (g >> 3) << 5 | (b >> 3) << 10 or 0x8000


def section(path):
    from tools import dwmap
    w, h, mode, rows, _ = dwmap.png_read(path)
    if (w, h, mode) != (W, H * BANDS, 'RGB'):
        sys.exit(f'{path}: {w}x{h} {mode}, a sheet is {W}x{H * BANDS} RGB')
    cluts, pixels = b'', bytearray()
    for band in range(BANDS):
        pal = {}
        for row in rows[band * H:(band + 1) * H]:
            for x in range(W):
                pixels.append(pal.setdefault(colour(*row[3 * x:3 * x + 3]), len(pal)))
        if len(pal) > COLOURS:
            sys.exit(f'{path}: band {band + 1} has {len(pal)} colours, {COLOURS} fit')
        cluts += struct.pack(f'<{COLOURS}H', *(list(pal) + [0] * (COLOURS - len(pal))))
    return (cluts + bytes(pixels)).ljust(SECTORS * 2048, b'\0')


def pack():
    from tools.languages import CODES
    out = b''
    for lang in CODES:
        path = os.path.join(ART, lang + '.png')
        out += section(path if os.path.isfile(path) else os.path.join(ART, 'en.png'))
    return out


def make(src):
    from PIL import Image
    from tools.languages import CODES
    for lang in CODES:
        path = os.path.join(src, lang + '.png')
        if not os.path.isfile(path):
            continue
        im = Image.open(path).convert('RGB')
        out = Image.new('RGB', (W, H * BANDS))
        for band in range(BANDS):
            top, bottom = round(im.height * band / BANDS), round(im.height * (band + 1) / BANDS)
            part = im.crop((0, top + 2, im.width, bottom - 2)).resize((W, H), Image.LANCZOS)
            part = part.quantize(COLOURS - 8, method=Image.MEDIANCUT, dither=Image.NONE).convert('RGB')
            out.paste(Image.eval(part, lambda v: v & 0xF8), (0, band * H))
        out.save(os.path.join(ART, lang + '.png'), optimize=True)
        print(os.path.join(ART, lang + '.png'))


if __name__ == '__main__':
    if sys.argv[1] == '--make':
        make(sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'build', 'localized-src', 'curling'))
    else:
        open(sys.argv[1], 'wb').write(pack())
