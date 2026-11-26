#!/usr/bin/env python3
"""The curling cups' banners (docs/mods/curling.md): KARCUP.DAT from content/localized/curling/<lang>.png.

  curling_banners.py OUT               KARCUP.DAT (pack(); the derive step `curling`, no Pillow)
  curling_banners.py --make [SRC]      the developer's: SRC/<lang>.png (the generator's sheets of five names on magenta, default
                                       build/localized-src/curling) -> content/localized/curling/<lang>.png (Pillow)

A committed sheet is 256 x 200 RGB: five bands of 256 x 40, each with at most 128 colours of 15 bits, the name alone
on the magenta KEY, which the game does not draw. The file holds,
for each language in the game's order, 26 sectors: five rows of 128 colours (16 bits), then the five bands (8 bits a
pixel). A language with no sheet takes the English one.
"""
import os, struct, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
ART = os.path.join(ROOT, 'content', 'localized', 'curling')
W, H, BANDS, COLOURS, SECTORS = 256, 40, 5, 128, 26
KEY = (248, 0, 248)   # the sheets' background: nothing is drawn there


def colour(r, g, b):
    """15 bits; KEY is the transparent colour (0), black is kept opaque"""
    if (r, g, b) == KEY:
        return 0
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
    """Each name is cut from the generator's flat magenta, scaled into its band and centred; what was magenta is KEY."""
    import numpy as np
    from tools.image import Image
    from tools.languages import CODES

    def gray(a):
        return Image.fromarray(np.ascontiguousarray(a, dtype=np.uint8), 'L')

    def solid(a):
        return a > 128
    for lang in CODES:
        path = os.path.join(src, lang + '.png')
        if not os.path.isfile(path):
            continue
        im = Image.open(path).convert('RGB')
        rgb = np.array(im, dtype=np.int32).reshape(im.height, im.width, 3)
        r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
        key = np.clip(np.minimum(r, b) - g, 0, 255)                     # how much of a pixel is the magenta
        alpha = 255 - np.minimum(255, key * 255 // 200)
        rows = solid(alpha).sum(axis=1)
        for y, n in enumerate(list(rows)):                             # a line across the whole sheet is a divider
            if n >= im.width - 4:
                alpha[max(0, y - 3):min(im.height, y + 4)] = 0
        rows = solid(alpha).sum(axis=1)
        spans, start = [], None
        for y, n in enumerate(list(rows) + [0]):
            if n and start is None:
                start = y
            elif not n and start is not None:
                if y - start > im.height // 40:
                    spans.append((start, y))
                start = None
        if len(spans) != BANDS:
            sys.exit(f'{path}: {len(spans)} names found, a sheet has {BANDS}')
        unmixed = np.stack([np.clip(c - key, 0, 255) if i != 1 else c for i, c in enumerate((r, g, b))], axis=-1)
        unmixed_im = Image.fromarray(unmixed.astype(np.uint8), 'RGB')
        alpha_im = gray(alpha)
        out = Image.new('RGB', (W, H * BANDS), KEY)
        for band, (top, bottom) in enumerate(spans):
            ys, xs = np.nonzero(solid(alpha[top:bottom]))
            box = (int(xs.min()), top + int(ys.min()), int(xs.max()) + 1, top + int(ys.max()) + 1)
            scale = min((W - 4) / (box[2] - box[0]), (H - 2) / (box[3] - box[1]))
            size = (max(1, round((box[2] - box[0]) * scale)), max(1, round((box[3] - box[1]) * scale)))
            mask = alpha_im.crop(box).resize(size, Image.LANCZOS)
            mask = gray(np.where(solid(np.array(mask).reshape(size[1], size[0])), 255, 0))
            part = unmixed_im.crop(box).resize(size, Image.LANCZOS)
            part = part.quantize(COLOURS - 8).convert('RGB')
            part = Image.fromarray((np.array(part).reshape(size[1], size[0], 3) & 0xF8).astype(np.uint8), 'RGB')
            out.paste(part, ((W - size[0]) // 2, band * H + (H - size[1]) // 2), mask)
        out.save(os.path.join(ART, lang + '.png'))
        print(os.path.join(ART, lang + '.png'))


if __name__ == '__main__':
    if sys.argv[1] == '--make':
        make(sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'build', 'localized-src', 'curling'))
    else:
        open(sys.argv[1], 'wb').write(pack())
