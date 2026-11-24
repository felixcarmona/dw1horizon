"""The art of the new technique rows (Darkness, Light, Water, Weapon, Earth) in SYSTEM_W: their Techset icons with
palettes of their own, and the English element names. The translated names are drawn by textures/systemw/build.py and
labels.py. The fourth original row reads NATURE since the earth row came: its old name is the new row's.

Everything sits in atlas cells that no language draws: the icons over the unused gold words at (128,35) and in two
holes at (200,72) and (200,84); the palette in one row of pixels, as the care badge's is; the English names in the
free block at (144,69).

The weapon and earth rows have one tile each and two palettes (the second is the tile's other frame), under the
first palette. Their tiles and the two names the rows brought (the weapon row's, and NATURE) sit in the free corner
at (82,96) and (228,108); Chinese, whose menu words fill that corner, has them where its texture leaves room.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# (u, v) of each row's two tiles (large, small), 12x12; the C side reads the same numbers (TECH_ROW_ICONS)
ICON_CELLS = (((128, 35), (140, 35)), ((152, 35), (164, 35)), ((200, 72), (200, 84)))
CLUT_RECT = (128, 125, 64, 1)       # VRAM words (352,253): 16 colours
CLUT_ID = (128 + CLUT_RECT[1]) << 6 | (320 + CLUT_RECT[0] // 4) >> 4
EN_NAMES = (('DARK', 144, 69), ('LIGHT', 166, 69), ('WATER', 144, 79), ('WEAPON', 90, 96), ('NATURE', 82, 106))
EN_CELL = (22, 10)
# the weapon and earth rows: (u, v) of each one's tile, the same in every language but Chinese
NEW_ICON_CELLS = ((228, 108), (240, 108))
ZH_ICON_CELLS = ((144, 96), (156, 96))
NEW_CLUT_RECT = (128, 126, 64, 2)   # two rows of 16 colours: VRAM (352,254) and (352,255)
NEW_CLUT_IDS = tuple((128 + NEW_CLUT_RECT[1] + i) << 6 | (320 + NEW_CLUT_RECT[0] // 4) >> 4 for i in (0, 1))
# the cells of the two names those rows brought (the earth row itself takes the fourth row's old name)
WIDE_NAMES = (('WEAPON', 'ARMA'), ('NATURE', 'NATURA'))
WIDE_CELLS = {('WEAPON', 'ARMA'): (90, 96, 30, 10), ('NATURE', 'NATURA'): (82, 106, 46, 10)}
ZH_CELLS = {('WEAPON', 'ARMA'): (169, 96, 22, 10), ('NATURE', 'NATURA'): (122, 24, 18, 10)}
# the translated cells: Spanish and Portuguese in their own letters, 8 rows tall, on the row their headers leave free;
# the other languages in the header row they do not use
ES_NAMES = (('DARK', 'SOMBRA'), ('LIGHT', 'LUZ'), ('WATER', 'AGUA'))
ES_ROW = (0, 48, 76, 8)
OTHER_CELLS = {('DARK', 'SOMBRA'): (0, 41, 34, 10), ('LIGHT', 'LUZ'): (34, 41, 34, 10),
               ('WATER', 'AGUA'): (68, 41, 34, 10)}


def icon_cells(language):
    return ZH_ICON_CELLS if language == 'zh-hans' else NEW_ICON_CELLS


def other_cell(key, language):
    """-> the cell a language other than Spanish and Portuguese draws this new name in, or None"""
    if key in WIDE_CELLS:
        return (ZH_CELLS if language == 'zh-hans' else WIDE_CELLS)[key]
    return OTHER_CELLS.get(key)


def new_art():
    """-> (the two palettes, the weapon and earth tiles as 12 rows of 12 indices)"""
    lines = [l for l in (ROOT / 'content/localized/techniques/icons-weapon-earth.txt').read_text().splitlines()
             if l and not l.startswith('#')]
    palettes = [[int(w, 16) for w in line.split()] for line in lines[:2]]
    body = [l for l in lines[2:] if l not in ('weapon', 'earth')]
    if any(len(p) != 16 for p in palettes) or len(body) != 20 or any(len(l) != 10 for l in body):
        raise ValueError('icons-weapon-earth.txt: two palettes of sixteen colours and two tiles of 10x10 expected')
    tiles = []
    for i in range(2):
        rows = ['b' * 11 + 'd'] + ['b' + r + 'd' for r in body[i*10:i*10+10]] + ['b' + 'd' * 11]
        tiles.append([[int(c, 16) for c in r] for r in rows])
    return palettes, tiles


def art():
    """-> (the 16 colours, [[large, small] per row]) with each tile as 12 rows of 12 indices"""
    lines = [l for l in (ROOT / 'content/localized/techniques/icons.txt').read_text().splitlines()
             if l and not l.startswith('#')]
    colours = [int(w, 16) for w in lines[0].split()]
    body = [l for l in lines[1:] if l not in ('dark', 'light', 'water')]
    if len(colours) != 16 or len(body) != 60 or any(len(l) != 10 for l in body):
        raise ValueError('icons.txt: sixteen colours and six tiles of 10x10 expected')
    tiles = []
    for i in range(6):
        rows = ['b' * 11 + 'd'] + ['b' + r + 'd' for r in body[i*10:i*10+10]] + ['b' + 'd' * 11]
        tiles.append([[int(c, 16) for c in r] for r in rows])
    return colours, [tiles[i*2:i*2+2] for i in range(3)]


def english_names():
    """-> [(rows of indices, u, v)] in the letters of the original names"""
    d = str(ROOT / 'tools/localize/textures/systemw')
    saved = sys.path[:]
    try:
        sys.path.insert(0, d)
        import words
    finally:
        sys.path[:] = saved
    out = []
    for word, u, v in EN_NAMES:
        rows = words.r_elem(word)
        if len(rows) != EN_CELL[1] or len(rows[0]) > WIDE_CELLS.get((word, dict(WIDE_NAMES).get(word)), EN_CELL)[0]:
            raise ValueError(f'{word} does not fit its cell')
        out.append((rows, u, v))
    return out


def english_widths():
    return [len(rows[0]) for rows, _, _ in english_names()]


def stamp(data, entry=0, language='en'):
    """Draw the icons and their palettes into this SYSTEM_W; the English one also gets the names."""
    from tools.localize.build import tim_entries, put_indices
    start, bpp, w, h = tim_entries(data)[entry]
    if (bpp, w, h) != (0, 256, 128):
        raise ValueError('the technique rows art requires SYSTEM_W')
    px = [n for b in data[start:start+w*h//2] for n in (b & 15, b >> 4)]

    def put(rows, u, v):
        for y, row in enumerate(rows):
            px[(v+y)*w+u:(v+y)*w+u+len(row)] = row

    colours, tiles = art()
    for cells, pair in zip(ICON_CELLS, tiles):
        for (u, v), tile in zip(cells, pair):
            put(tile, u, v)
    u, v, _, _ = CLUT_RECT
    put([[c >> s & 15 for c in colours for s in (0, 4, 8, 12)]], u, v)
    palettes, tiles = new_art()
    for (u, v), tile in zip(icon_cells(language), tiles):
        put(tile, u, v)
    u, v, _, _ = NEW_CLUT_RECT
    put([[c >> s & 15 for c in palette for s in (0, 4, 8, 12)] for palette in palettes], u, v)
    if language == 'en':
        for rows, u, v in english_names():
            put(rows, u, v)
    put_indices(data, entry, px)
