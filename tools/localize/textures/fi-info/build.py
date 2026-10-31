#!/usr/bin/env python3
"""Triangle-menu labels in FI_INFO's free cells, preserving all clock frames.

  build.py FI_INFO.TIM OUT.idx -> pixel indices and matching GameMenuLabel C rows
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pathlib import Path
root = next((p for p in Path(__file__).resolve().parents if (p / 'tools').is_dir()), None)
if root is not None:
    sys.path.insert(0, str(root))
from tools.localize.fi_info import CELLS, SHARED_SIZES, check_cells
import pixfont
from pixfont import text_mask, stamp
from idx import load

F9 = {k: ['.' * len(v[0])] * 2 + v for k, v in pixfont.LABEL6.items()}   # a word with Ñ: two rows more for the tilde
F9['Ñ'] = ['##.#', '....'] + pixfont.LABEL6['N']
ICON_X = {1: 0x14, 2: 0x38, 3: 0x5b, 4: 0x14, 5: 0x38, 6: 0x5b, 7: 0x14}   # MENU_OPTIONS[i].x, the icons 0x14 wide
LABEL_Y = {1: 0x60, 2: 0x60, 3: 0x60, 4: 0x88, 5: 0x88, 6: 0x88, 7: 0x38}
# entry: (word, u, row); DIGIMON keeps the disc's own label
PLAN = dict(CELLS)
if os.environ.get('LOCALIZE_LANGUAGE') == 'pt-br':
    words = {1: 'ITENS', 3: 'JOGADOR', 4: 'ELOGIAR', 6: 'DORMIR', 7: 'PESCAR', 5: 'BRONCA'}
    PLAN = {e: (words[e], u, row) for e, (_, u, row) in CELLS.items()}

EN = {1: (0x13, 0x60, 0x18, 7, 0x50, 0x14), 2: (0x35, 0x60, 0x1c, 7, 0x50, 0x1b), 3: (0x5a, 0x60, 0x1c, 7, 0x50, 0x22),
      4: (0x15, 0x88, 0x14, 7, 0x6c, 0x14), 5: (0x39, 0x88, 0x14, 7, 0x6c, 0x1b), 6: (0x60, 0x88, 0x14, 7, 0x6c, 0x22),
      7: (0x17, 0x38, 0x10, 7, 0x50, 0x29)}


def build(tim):
    w, h, px, cl, bpp = load(tim)
    grid = [[px(x, y) for x in range(w)] for y in range(h)]
    # Only these two blocks are free; u128..159, rows32..47 is the night clock.
    for x0, y0, x1, y1 in ((128, 48, 160, 64), (160, 32, 192, 64)):
        for y in range(y0, y1):
            for x in range(x0, x1):
                grid[y][x] = 0
    rows = dict(EN)
    for e, (word, u, row) in PLAN.items():
        font = F9 if 'Ñ' in word else pixfont.LABEL6
        m = text_mask(font, word)
        ink_width = len(m[0]) + 1
        lw, lh = (ink_width if os.environ.get('LOCALIZE_LANGUAGE') == 'pt-br' else SHARED_SIZES[e][0]), len(m) + 1
        assert ink_width <= lw and u + lw <= 192 and row + lh <= 64, word
        def put(x, y, i): grid[y][x] = i
        stamp(put, m, u + (lw - ink_width) // 2, row, 15, shadow=1)
        x = ICON_X[e] + 10 - lw // 2
        rows[e] = (x, LABEL_Y[e] - (lh - 7), lw, lh, u, row + 1)
    check_cells([(r[4], r[5] - 1, r[2], r[3]) for e, r in rows.items() if e != 2])
    return grid, rows


if __name__ == '__main__':
    grid, rows = build(sys.argv[1])
    open(sys.argv[2], 'wb').write(bytes(v for r in grid for v in r))
    for e in range(1, 8):
        print('\t{ 0x%04x, 0x%04x, 0x%02x, 0x%02x, 0x%02x, 0x%02x },' % rows[e])
