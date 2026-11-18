"""Status tags and the filth/virus icon, authored without redistributed disc art.

The tag replaces the unused RAPIDEZ alternative at (108,72); no live sprite
uses that alternative. Native SYSTEM_W CLUT 9 supplies tag ink/outline and
CLUT 10 supplies the icon's black outline and ochre shading.
"""
from functools import lru_cache
import importlib.util
import json
from pathlib import Path
import re

from tools.localize.build import tim_entries, put_indices

ROOT = Path(__file__).resolve().parents[2]
TAG_RECT = (108, 72, 36, 10)
# The BATTLES tag sits in blank SYSTEM_W space (all index 15) above the relocated labels.
BATTLES_RECT = (216, 98, 36, 10)
ICON_RECT = (44, 116, 11, 11)
# A shaded, outlined pile: the native virus gauge measures accumulated filth.
# F is transparent, 1 outline, 2/3/4/5 are native ochre shades (CLUT 10).
VIRUS = tuple((ROOT / 'content/localized/status/virus.txt').read_text().splitlines())


@lru_cache(None)
def tag_font():
    path = ROOT / 'tools/localize/textures/systemw/fonts.py'
    spec = importlib.util.spec_from_file_location('status_tag_fonts', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def wording(language, battles=False):
    if battles:
        return json.loads((ROOT / 'content/localized/status/battles.json').read_text())[language].upper()
    names = json.loads((ROOT / 'text' / ('ours' if language == 'en' else language) / 'names.json').read_text())
    return names['main.CHART_STR_MISTAKES'].upper()


def tag(language, battles=False):
    """A right-aligned 36x10 tag: eight ink rows, full eight-neighbour outline."""
    text = wording(language, battles)
    font = tag_font()
    if language == 'ja':
        from tools.localize.labels import glyphs
        table = glyphs()
        rows = ['.'.join(table[c][y] for c in text) for y in range(11)]
        occupied = [y for y, row in enumerate(rows) if '#' in row]
        rows = rows[occupied[0]:occupied[-1]+1]
        sh, sw = len(rows), len(rows[0])
        width = min(34, round(sw * 8 / sh))
        bitmap = [[any(rows[sy][sx] == '#'
                       for sy in range(y*sh//8, (y+1)*sh//8)
                       for sx in range(x*sw//width, (x+1)*sw//width))
                   for x in range(width)] for y in range(8)]
    elif language == 'zh-hans':
        from tools.localize.labels import mask
        bitmap = mask(text, 34, 8, preserve=True)
    else:
        rows = font.compose(font.TAG_STATUS, text)
        bitmap = [[c == '#' for c in row] for row in rows]
    h, w = len(bitmap), len(bitmap[0])
    if h > 8 or w > 34:
        raise ValueError(f'{language}: status tag does not fit: {text} ({w}x{h})')
    out = [[0] * 36 for _ in range(10)]
    points = {(35-w+x, 1+y) for y, row in enumerate(bitmap) for x, on in enumerate(row) if on}
    for x, y in points:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                out[y+dy][x+dx] = 1
    for x, y in points:
        out[y][x] = 2
    return out


def stamp(data, entry=0, language='en'):
    """Change only the two crops, leaving every palette and allocation intact."""
    start, bpp, w, h = tim_entries(data)[entry]
    if (bpp, w, h) != (0, 256, 128):
        raise ValueError('status art requires SYSTEM_W')
    px = [n for b in data[start:start+w*h//2] for n in (b & 15, b >> 4)]
    for (u, v, rw, rh), rows in ((TAG_RECT, tag(language)), (BATTLES_RECT, tag(language, True)),
                                (ICON_RECT, [[int(c, 16) for c in row] for row in VIRUS])):
        for y, row in enumerate(rows):
            px[(v+y)*w+u:(v+y)*w+u+rw] = row
    put_indices(data, entry, px)


def crop_tables(source):
    """Reuse cap row 10 for mistakes; row 20 becomes the sole care icon.

    Apply to every language branch, including English. The language banks
    restore these existing resident tables; no table or MENU_REL allocation grows.
    """
    a = source.index('IconRect STATS_VIEW_ELEMENTS[21] = {')
    b = source.index('\n};', a)
    lines = source[a:b].splitlines()
    index = 0
    for i, line in enumerate(lines):
        if line.startswith(('#if', '#elif', '#else')):
            index = 0
        if re.match(r'\s*\{ 0x', line):
            if index in (10, 20):
                row = (69, -34, 36, 10, 108, 72) if index == 10 else (-138, 84, 11, 11, 44, 116)
                lines[i] = '\t{ ' + ', '.join(f'0x{n & 65535:04x}' for n in row) + ' },'
            index += 1
    return source[:a] + '\n'.join(lines) + source[b:]


def check_cells(items):
    from tools.localize.fi_info import overlaps
    from tools.localize.systemw import relocated_rect
    for item in items:
        if item['en'] == 'SPEED (alternative)':
            continue  # The unused alternative is deliberately superseded.
        for rect in (tuple(item[k] for k in ('u', 'v', 'w', 'h')), relocated_rect(item)):
            if rect and (overlaps(TAG_RECT, rect) or overlaps(BATTLES_RECT, rect)):
                raise ValueError(f'SYSTEM_W label overlaps status tag: {item["en"]}')


def art_pins():
    """Pin authored index rasters only; never include the player's palettes/art."""
    import hashlib
    from tools.languages import CODES
    digest = lambda rows: hashlib.sha256(bytes(n for row in rows for n in row)).hexdigest()
    return dict(tags={language: digest(tag(language)) for language in CODES},
                battles={language: digest(tag(language, True)) for language in CODES},
                virus=digest([[int(c, 16) for c in row] for row in VIRUS]))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-pins', action='store_true', help='update authored raster pins after visual review')
    args = parser.parse_args()
    path = ROOT / 'content/localized/status/pins.json'
    if args.write_pins:
        path.write_text(json.dumps(art_pins(), ensure_ascii=False, indent=2) + '\n')
    elif json.loads(path.read_text()) != art_pins():
        raise SystemExit('status artwork differs from its reviewed raster pins')
    print('Status art: all nine language tags and the virus icon match their pins')
