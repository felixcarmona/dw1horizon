#!/usr/bin/env python3
"""HORIZON under DIGIMON WORLD on the title screens, drawn into the player's own title images.

  title_stamp.py OUTDIR [--extracted DIR]          OUTDIR/ETCNA/TITLE256.TIM and OUTDIR/ETCNA/TITLE2.TIM
  title_stamp.py --tim FILE                         stamp one TIM in place (TITLE256's Spanish copy: tools/localize/build.py)

The title word is overlaid on the original images using our hand-drawn
pixel letters (upright, bold 2-px stems, the gold of DIGIMON WORLD with a dark outline). TITLE256 (the Press Start
screen, main.c renderPressStartToContinue draws texture rows 0-239 at the screen's top left) gets the 10-row word at
rows 153-164, between DIGIMON WORLD (ends at 150) and the blinking Press Start Button (screen row 170); TITLE2 (the
title menu and the VS mode's background, renderMainMenuBackground) the 7-row word at rows 228-236, three rows above the
bottom. The Japanese titles (a Japanese base disc: tools/basedisc.py jp1, the katakana logo, no DIGIMON WORLD line) put
the word right under their logo, at these positions: TITLE256 rows 111-122 on the logo's green glow,
TITLE2 rows 205-213 under the logo at the bottom right. Only pixel indices change: each colour is the nearest of the TIM's own CLUT, so the file keeps its header,
CLUT and size.

The European TITLE256 (the same file on the five European discs) sets its Press Start Button in narrower letters, 115
columns, and its language list (English French Spanish Italian German) follows at column 115. Our executable draws the
USA line, u 0..120 of row 241 (main.c PRESS_START_QUAD), which showed that list's E after "Button": press_start_fit
moves the European line to the middle of those 121 columns and clears the rest of them.
"""
import argparse, hashlib, os, struct, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WORD = 'HORIZON'
LETTERS = {
    7: {'H': '##..##|##..##|##..##|######|##..##|##..##|##..##',
        'O': '.####.|##..##|##..##|##..##|##..##|##..##|.####.',
        'R': '#####.|##..##|##..##|#####.|##.##.|##..##|##..##',
        'I': '##|##|##|##|##|##|##',
        'Z': '######|....##|...##.|..##..|.##...|##....|######',
        'N': '##..##|###.##|######|##.###|##..##|##..##|##..##'},
    10: {'H': '##...##|##...##|##...##|##...##|#######|#######|##...##|##...##|##...##|##...##',
         'O': '.#####.|#######|##...##|##...##|##...##|##...##|##...##|##...##|#######|.#####.',
         'R': '######.|#######|##...##|##...##|#######|######.|##.##..|##..##.|##...##|##...##',
         'I': '##|##|##|##|##|##|##|##|##|##',
         'Z': '#######|#######|....###|...###.|..###..|.###...|###....|##.....|#######|#######',
         'N': '##...##|###..##|###..##|####.##|##.#.##|##.####|##..###|##..###|##...##|##...##'},
}
GOLD = [(255, 250, 190), (255, 238, 120), (255, 222, 60), (255, 200, 24), (246, 170, 12), (236, 140, 8), (222, 112, 4)]
OUTLINE = (16, 10, 8)
# file -> (letter height, the word's centre column, its top row with the outline)
PLACES = {'ETCNA/TITLE256.TIM': (10, 158, 153), 'ETCNA/TITLE2.TIM': (7, 233, 228)}
# rule: another release's title image (by the SHA-1 of the file as its disc has it) gets its own place
RELEASE_PLACES = {'f3b60929c58e277def094152586b6bd174ecab4c': (10, 160, 111),     # Japanese TITLE256
                  '93ebd56d3f45b2027677673757a8c3f39fa8319d': (7, 233, 205)}      # Japanese TITLE2
# the Press Start Button line our executable shows (main.c PRESS_START_QUAD: u, v, w, h), and per release (by the SHA-1
# of TITLE256 as its disc has it) the width of that release's own line, which starts at u 0 of the same rows
PRESS_START = (0, 241, 121, 10)
RELEASE_PRESS_START = {'c0d12ef9a5a689798b0b2965d95e574c525ab904': 115}      # European TITLE256
CLEAR = 255     # TITLE256's transparent index, around the line


def word_pixels(rows):
    """-> {(x, y): rgb} of the word with its 1-px outline, (0, 0) its top left"""
    glyphs = LETTERS[rows]
    ink, x = {}, 1
    for ch in WORD:
        g = glyphs[ch].split('|')
        for y, line in enumerate(g):
            for i, v in enumerate(line):
                if v == '#':
                    ink[(x + i, y + 1)] = GOLD[round(y * (len(GOLD) - 1) / (rows - 1))]
        x += len(g[0]) + 1
    out = {}
    for (px, py) in ink:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                out.setdefault((px + dx, py + dy), OUTLINE)
    out.update(ink)
    return out


def stamp(data, path, disc=None):
    """data (bytearray of an 8-bit TIM) with the word of path's place drawn into it; disc: the file as its disc has it,
    when data is already a changed copy of it (the Spanish TITLE256 with its Press Start line), for the place"""
    magic, flag = struct.unpack_from('<II', data, 0)
    if magic != 0x10 or flag & 3 != 1 or not flag & 8:
        sys.exit(f'{path}: not an 8-bit TIM with a CLUT')
    clen, _, _, cw, ch = struct.unpack_from('<IHHHH', data, 8)
    clut = struct.unpack_from(f'<{cw}H', data, 20)
    p = 8 + clen
    _, _, _, w2, h = struct.unpack_from('<IHHHH', data, p)
    w, pix = w2 * 2, p + 12
    cols = [((v & 31) << 3, (v >> 5 & 31) << 3, (v >> 10 & 31) << 3) for v in clut]
    usable = [i for i, v in enumerate(clut) if v != 0]   # 0x0000 draws transparent

    def nearest(rgb):
        return min(usable, key=lambda i: sum((a - b) ** 2 for a, b in zip(cols[i], rgb)))

    rows, cx, top = RELEASE_PLACES.get(hashlib.sha1(disc or data).hexdigest(), PLACES[path])
    px = word_pixels(rows)
    width = max(x for x, _ in px) + 1
    x0 = cx - width // 2
    cache = {}
    for (x, y), rgb in px.items():
        if rgb not in cache:
            cache[rgb] = nearest(rgb)
        X, Y = x0 + x, top + y
        if not (0 <= X < w and 0 <= Y < h):
            sys.exit(f'{path}: the word leaves the image at {X},{Y}')
        data[pix + Y * w + X] = cache[rgb]
    return data


def press_start_fit(data):
    """data (bytearray of a release's own TITLE256 as its disc has it): a narrower Press Start Button line moved to the
    middle of the columns our executable shows, nothing else in them (the European line is followed by its language
    list). Any other file: unchanged."""
    width = RELEASE_PRESS_START.get(hashlib.sha1(data).hexdigest())
    if width is None:
        return data
    p = 8 + struct.unpack_from('<I', data, 8)[0]
    w, pix = struct.unpack_from('<H', data, p + 8)[0] * 2, p + 12
    u, v, qw, qh = PRESS_START
    dx = (qw - width) // 2
    for y in range(v - 1, v + qh + 1):       # one row more above and under: the line's own empty rows
        row = pix + y * w + u
        line = bytes(data[row:row + width])
        data[row:row + qw] = bytes([CLEAR]) * qw
        data[row + dx:row + dx + width] = line
    return data


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('out', nargs='?')
    ap.add_argument('--extracted', default=os.path.join(ROOT, 'extracted'))
    ap.add_argument('--tim', help='stamp this TIM in place (its place: TITLE256)')
    ap.add_argument('--as', dest='as_path', default='ETCNA/TITLE256.TIM', help="with --tim: which title it is")
    a = ap.parse_args()
    if a.tim:
        data = stamp(bytearray(open(a.tim, 'rb').read()), a.as_path)
        open(a.tim, 'wb').write(data)
        return
    if not a.out:
        ap.error('OUTDIR or --tim')
    for path in PLACES:
        data = bytearray(open(os.path.join(a.extracted, path), 'rb').read())
        if path == 'ETCNA/TITLE256.TIM':
            data = press_start_fit(data)
        data = stamp(data, path, disc=open(os.path.join(a.extracted, path), 'rb').read())
        dst = os.path.join(a.out, path)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, 'wb').write(data)
        print(dst)


if __name__ == '__main__':
    main()
