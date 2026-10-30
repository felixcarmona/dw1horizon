#!/usr/bin/env python3
"""The triangle menu's labels in Spanish (FI_INFO.TIM): our 3x6 letters with the label's shadow (pixfont.LABEL6) drawn
in the texture's unused status words (EVOLVE / POOP / DEAD at u 128..191, v 32..63: nothing draws them), and the
GameMenuLabel rows that show them (src/main/game_menu.c GAME_MENU_TEXT_SPRITES, the Spanish build's values).

  build.py FI_INFO.TIM OUT.idx      -> OUT.idx (one palette index per pixel) and prints the C rows
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pixfont
from pixfont import text_mask, stamp
from idx import load

F9 = {k: ['.' * len(v[0])] * 2 + v for k, v in pixfont.LABEL6.items()}   # a word with Ñ: two rows more for the tilde
F9['Ñ'] = ['##.#', '....'] + pixfont.LABEL6['N']
ICON_X = {1: 0x14, 2: 0x38, 3: 0x5b, 4: 0x14, 5: 0x38, 6: 0x5b, 7: 0x14}   # MENU_OPTIONS[i].x, the icons 0x14 wide
LABEL_Y = {1: 0x60, 2: 0x60, 3: 0x60, 4: 0x88, 5: 0x88, 6: 0x88, 7: 0x38}
# entry: (word, u, row); DIGIMON keeps the disc's own label
PLAN = {1: ('OBJETOS', 128, 32), 3: ('JUGADOR', 160, 32), 4: ('ALABAR', 128, 39), 6: ('DORMIR', 160, 39),
        7: ('PESCAR', 128, 46), 5: ('REÑIR', 160, 46)}
if os.environ.get('LOCALIZE_LANGUAGE') == 'pt-br':
    PLAN = {1: ('ITENS', 128, 32), 3: ('JOGADOR', 160, 32), 4: ('ELOGIAR', 128, 39),
            6: ('DORMIR', 160, 39), 7: ('PESCAR', 128, 46), 5: ('BRONCA', 160, 46)}

EN = {1: (0x13, 0x60, 0x18, 7, 0x50, 0x14), 2: (0x35, 0x60, 0x1c, 7, 0x50, 0x1b), 3: (0x5a, 0x60, 0x1c, 7, 0x50, 0x22),
      4: (0x15, 0x88, 0x14, 7, 0x6c, 0x14), 5: (0x39, 0x88, 0x14, 7, 0x6c, 0x1b), 6: (0x60, 0x88, 0x14, 7, 0x6c, 0x22),
      7: (0x17, 0x38, 0x10, 7, 0x50, 0x29)}


def build(tim):
    w, h, px, cl, bpp = load(tim)
    grid = [[px(x, y) for x in range(w)] for y in range(h)]
    for y in range(32, 64):                                  # the unused status words go
        for x in range(128, 192):
            grid[y][x] = 0
    rows = dict(EN)
    for e, (word, u, row) in PLAN.items():
        font = F9 if 'Ñ' in word else pixfont.LABEL6
        m = text_mask(font, word)
        lw, lh = len(m[0]) + 1, len(m) + 1
        assert u + lw <= 192 and row + lh <= 64, word
        def put(x, y, i): grid[y][x] = i
        stamp(put, m, u, row, 15, shadow=1)
        x = ICON_X[e] + 10 - lw // 2
        rows[e] = (x, LABEL_Y[e] - (lh - 7), lw, lh, u, row + 1)
    return grid, rows


if __name__ == '__main__':
    grid, rows = build(sys.argv[1])
    open(sys.argv[2], 'wb').write(bytes(v for r in grid for v in r))
    for e in range(1, 8):
        print('\t{ 0x%04x, 0x%04x, 0x%02x, 0x%02x, 0x%02x, 0x%02x },' % rows[e])
