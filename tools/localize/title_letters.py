"""The title screen's translated "Press Start Button" line (TITLE256.TIM rows 240-250), in the disc's own letters.

Every language's line is set at the disc's native pixel size, never scaled: the letters the disc's own line has
(P r e s S t a B u o n, copied from rows 241-250 of the player's TITLE256) plus letters drawn by hand in the same
style (2-column stems, 1-row bars, the same white and the three grey edge tones). Lowercase letters sit on rows
243-249 (ascenders and capitals from 241), row 240 holds accents and row 250 is the one row under the baseline.
The kana and hanzi are drawn on the same rows, at the size their fonts have (tools/font/japanese.txt,
tools/font/chinese.json), redrawn here with the line's stems.

No Pillow: the misc recipe (tools/localize/textures/misc/build.py title) runs on the player's path.
"""
import sys

TCH = {'V': 0, 'L': 91, '9': 181, '8': 192, ' ': 255}      # the USA and European TITLE256's palette indices


def disc_tch(disc):
    """TCH in the palette indices of this disc's own TITLE256 (the Japanese disc has the same colours in another order)"""
    from tools.title_stamp import disc_index
    return {c: disc_index(disc, i) for c, i in TCH.items()}


# the letters of the disc's own Press Start Button line (rows 241-250): each one's first and last column. The European
# TITLE256 (by its SHA-1; the same file on the five European discs) sets the line in narrower letters
TITLE_LETTERS = dict(P=(0, 6), r=(9, 13), e=(15, 20), s=(23, 27), S=(41, 47), t=(49, 53), a=(55, 60),
                     B=(79, 85), u=(88, 93), o=(107, 112), n=(115, 120))
RELEASE_TITLE_LETTERS = {'c0d12ef9a5a689798b0b2965d95e574c525ab904': dict(
    P=(0, 5), r=(7, 12), e=(14, 19), s=(21, 26), S=(37, 42), t=(44, 49), a=(51, 56),
    B=(74, 79), u=(81, 86), o=(102, 107), n=(109, 114))}

# the line per language, and the width of the quad our executable draws it with (main.c PRESS_START_QUAD: Spanish
# and Brazilian Portuguese have their own, the width of their line in the USA letters; every other translation the
# Spanish 129 at the same place). A line is centred in its quad.
TEXTS = {'es': 'Pulsa el botón START', 'pt-br': 'Aperte START', 'fr': 'Appuyez sur START', 'de': 'START drücken',
         'it': 'Premi START', 'ca': 'Prem START', 'ja': 'START をおして', 'zh-hans': '按START键'}
QUAD = 129

# Letters drawn by hand, one string per row from row 240; V white, L grey, 9 and 8 the dark edge tones.
HAND = {
    'l': ['', 'VV'] + ['VV'] * 8,
    'b': ['', 'VV', 'VV', 'VVVVL', 'VV  VL', 'VV  VV', 'VV  VV', 'VV  VV', 'VV  VL', 'VVVVL'],
    'p': ['', '', '', 'VVVVL', 'VV  VV', 'VV  VV', 'VVVVL', 'VV', 'VV', 'VV'],
    'T': ['', 'VVVVVV'] + ['  VV  '] * 8,
    'A': ['', '  9VV9  ', '  LVVL  ', ' 9VLLV9 ', ' LV  VL ', ' VL  LV ', '9VVVVVV9', 'LV    VL', 'VL    LV', 'VV    VV'],
    'R': ['', 'VVVVL  ', 'VV 9VL ', 'VV  LV ', 'VV 9VL ', 'VVVVL  ', 'VV 8VL ', 'VV  LV ', 'VV  9VL', 'VV   VV'],
    # French, German, Italian and Catalan
    'y': ['', '', '', 'VV  VV', 'VV  VV', 'VV  VV', 'LV  VV', '9LVVVV', '    VV', '    VL', 'VVVVL'],
    'z': ['', '', '', 'VVVVVV', '   9VL', '  9VL ', ' 9VL  ', '9VL   ', 'VL    ', 'VVVVVV'],
    'd': ['', '    VV', '    VV', '9LVVVV', 'LV  VV', 'VV  VV', 'VV  VV', 'VV  VV', 'LV  VV', '9LVVVV'],
    'c': ['', '', '', '9LVVV', 'LV9 8V', 'VV', 'VV', 'VV', 'LV   V', '9LVVV'],
    'k': ['', 'VV', 'VV', 'VV  VL', 'VV VL', 'VVVL', 'VVVV', 'VV LV', 'VV  VL', 'VV  LV'],
    'm': ['', '', '', 'VVVVVVVVL', 'VV  VV  VL', 'VV  VV  VV', 'VV  VV  VV', 'VV  VV  VV', 'VV  VV  VV', 'VV  VV  VV'],
    'i': ['', 'VV', '', 'VV', 'VV', 'VV', 'VV', 'VV', 'VV', 'VV'],
    # Japanese (tools/font/japanese.txt's を お し て, their strokes 2 columns wide)
    'を': ['', '    VV', ' VVVVVVVV', '   VV', '  VVVVL VV', ' VL  LVVL', 'VL 9VVLV', '  LV  VV', '  VV', '   LVVVVVV'],
    'お': ['', '   VV   VL', 'VVVVVVVV LV', '   VV', '  VVVVVVL', ' VLVV   9VL', 'VL VV    VV', 'VV VV    VV', 'VL VV   9VL',
           ' VVV  VVVL'],
    'し': ['', ' VV', ' VV', ' VV', ' VV', ' VV', ' VV     VV', ' VV     VV', ' LV    VL', '  9VVVVL'],
    'て': ['', '', 'VVVVVVVVVV', '     VVL', '    VL', '   VV', '   VV', '   VV', '   LV', '    9VVVV'],
    # Simplified Chinese (tools/font/chinese.json's 按 and 键, rows 240-250, their single-pixel strokes)
    '按': ['.#.....#....', '.#..#######.', '###.#.....#.', '.#.....#....', '.#.....#....', '.##.#######.',
          '##....#..#..', '.#...#...#..', '.#....#.#...', '.#.....##...', '##..###..##.'],
    '键': ['.#......#...', '.####.#####.', '#...#...#.#.', '###.#######.', '.#.#....#.#.', '.#.##.#####.',
          '###.#...#...', '.#..#.#####.', '.#.##...#...', '.##.##..#...', '.#.#..#####.'],
}


def hand(rows, tch):
    """a hand-drawn letter (HAND's rows from row 240) -> rows of palette indices, 11 rows"""
    rows = [r.replace('#', 'V').replace('.', ' ').rstrip() for r in rows]
    rows = rows + [''] * (11 - len(rows))
    w = max(len(r) for r in rows)
    return [[tch[c] for c in r.ljust(w)] for r in rows]


def title_glyphs(en, letters=TITLE_LETTERS, tch=TCH):
    """{letter: rows of palette indices from row 240}: the disc's own letters (en.block: x, y, w, h -> rows), then the
    hand-drawn ones"""
    clear = tch[' ']
    G = {}
    for ch, (a, b) in letters.items():
        G[ch] = [[clear] * (b - a + 1)] + en.block(a, 241, b - a + 1, 10)   # row 0 = texture row 240 (free)
    for ch in ('l', 'b'):
        G[ch] = hand(HAND[ch], tch)
    G['ó'] = [r[:] for r in G['o']]
    G['ó'][0] = [tch[c] for c in '   LV ']; G['ó'][1] = [tch[c] for c in '  LV  ']
    for ch, rows in HAND.items():
        if ch not in G:
            G[ch] = hand(rows, tch)
    G['ü'] = [r[:] for r in G['u']]
    G['ü'][1] = [tch['V'] if i in (0, 1, len(G['u'][0]) - 2, len(G['u'][0]) - 1) else clear for i in range(len(G['u'][0]))]
    return G


def title_compose(G, text, t, x0, space=4, clear=255):
    """text in G's letters into t (t.s(x, y, index)) from column x0 -> its width"""
    x = x0; prev = None
    for ch in text:
        if ch == ' ':
            x += space; prev = None; continue
        if prev is not None:
            x += 1 if ('t' in (prev, ch) or 'r' in (prev, ch) or prev.isupper() and ch.isupper()) else 2
        g = G[ch]
        for j, row in enumerate(g):
            for i, v in enumerate(row):
                if v != clear:
                    t.s(x + i, 240 + j, v)
        x += len(g[0]); prev = ch
    return x - x0


class _Measure:
    """a texture that keeps nothing: title_compose on it only measures"""
    def s(self, x, y, v):
        pass


def title_line(G, text, t, clear=255, width=None):
    """text drawn in G's letters into t, in the middle of its quad: width, or else the width the text has in the USA
    letters (Spanish and Brazilian Portuguese: their quad is that wide); a wider line closes its spaces up, down to 2
    columns -> the quad's width"""
    usa = dict(G, **{ch: [[clear] * (b - a + 1)] for ch, (a, b) in TITLE_LETTERS.items()})
    usa['ó'] = usa['o']
    W = width or title_compose(usa, text, _Measure(), 0, clear=clear)
    space = 4
    while title_compose(G, text, _Measure(), 0, space, clear) > W and space > 2:
        space -= 1
    w = title_compose(G, text, _Measure(), 0, space, clear)
    if w > W:
        sys.exit(f'title: {text!r} is {w} columns in this disc\'s letters, wider than its quad ({W})')
    title_compose(G, text, t, (W - w) // 2, space, clear)
    return W
