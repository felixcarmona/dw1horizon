"""Builds the Spanish versions of the misc baked-text textures. Run from anywhere:
   .venv/bin/python build.py   -> *.es.idx, *.en.png, *.es.png, rects.json, z_*.png previews"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tex import Tex, outline, mask, holes
OUT = os.path.dirname(os.path.abspath(__file__))
PT_BR = os.environ.get('LOCALIZE_LANGUAGE') == 'pt-br'
RECTS = []
PREVIEWS = os.environ.get('LOCALIZE_PREVIEWS') != '0'   # (tools/localize/build.py: a build writes no previews: no Pillow)
WORDS = {}   # key -> dict(en=(tex,clut,rect), es=(tex,clut,rect), bg)


def rect(**k):
    RECTS.append(k)


def save(name, en, es, clut):
    es.save_idx(f'{OUT}/{name}.es.idx')
    if PREVIEWS:
        en.image(clut).save(f'{OUT}/{name}.en.png')
        es.image(clut).save(f'{OUT}/{name}.es.png')


def ink_of(t, x0, x1, y0, y1, inkset):
    return {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) if t.g(x, y) in inkset}


def shift(s, dx, dy):
    return {(x + dx, y + dy) for x, y in s}


# ---------------------------------------------------------------- 1b. FINISH!! -> REMATE! (BI_IN.TIM, the finisher gauge)
# The gauge is the word itself: 8 segments (battle_hud.c BTL_FINISHER_SEGMENT_U/W/X, the same in std_hud.c and vs_hud.c),
# rows 29..43, each a letter in 2-pixel strokes under a 1-pixel outline (index 0xa), its top on the gauge's rising
# slope, filled by row (0xb under the top, 0xc, then 0xd, 0xe and 0xb 0xb at the foot). REMATE! takes 46 of FINISH!!'s
# 48 pixels (the M 9 wide, its middle a V: 7 read as an N); the eighth segment is left empty (width 0).
FINISH_SEGMENTS_ES = [(0, 7), (7, 6), (13, 9), (22, 7), (29, 6), (35, 6), (41, 5), (46, 0)]   # (u, w); x = u


def finish(en, es):
    Y0, Y1 = 29, 43                                    # the strip's rows (v 0x9d..0xab)
    top = {x: min(y for y in range(Y0, Y1 + 1) if en.g(x, y) != 0) for x in range(0, 48) if any(en.g(x, y) for y in range(Y0, Y1 + 1))}
    bang = [[en.g(x, y) for x in range(38, 43)] for y in range(Y0, Y1 + 1)]   # the first "!" (u 38, w 5)
    es.fill(0, Y0, 48, Y1 + 1, 0)

    def glyph(ch, w, T):
        """the ink of a letter w pixels wide (2-pixel stems, 1-row bars) from row T to row 42"""
        H = 42 - T + 1; M = T + (H - 1) // 2          # the middle bar's row
        ink = set()
        for y in range(T, 43):
            for x in range(w):
                on = False
                if ch == 'E':
                    on = x < 2 or y in (T, M, 42)
                elif ch == 'T':
                    on = y == T or x in (1, 2)
                elif ch == 'A':
                    on = x < 2 or x >= w - 2 or y in (T, M)
                elif ch == 'R':
                    on = x < 2 or (y in (T, M) and x < w - 1) or (x >= w - 2 and T < y < M) or (x >= w - 2 and y > M)
                elif ch == 'M':
                    on = x < 2 or x >= w - 2 or (x in (2, w - 3) and y <= T + 2) or (x == w // 2 and T + 1 <= y <= T + 4)
                if on:
                    ink.add((x, y))
        return ink

    def fill_colour(y, T):
        if y >= 41: return 0xb
        if y == 40: return 0xe
        if y == 39: return 0xd
        if y == T: return 0xb
        return 0xc

    for ch, (u, w) in zip('REMATE', FINISH_SEGMENTS_ES):
        c = min(u + w // 2, 47)
        while c not in top:                            # a gap column of the original: the one before it
            c -= 1
        T = top[c] + 1                                 # the letter's top row: the slope's at its middle, under the outline
        ink = {(x + u + 1, y) for x, y in glyph(ch, w - 2, T)}
        for (x, y) in ink:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (x + dx, y + dy)
                    if q not in ink and u <= q[0] < u + w and Y0 <= q[1] <= Y1:
                        es.s(*q, 0xa)
        for y in range(T, 43):                         # the gaps a letter encloses in its row are the outline's colour
            xs = [x for x, yy in ink if yy == y]
            for x in range(min(xs), max(xs) + 1) if xs else ():
                if (x, y) not in ink:
                    es.s(x, y, 0xa)
        for (x, y) in ink:
            es.s(x, y, fill_colour(y, T))
    u, w = FINISH_SEGMENTS_ES[6]
    for j, row in enumerate(bang):
        for i, v in enumerate(row):
            es.s(u + i, Y0 + j, v)
    rect(en='FINISH!!', es='REMATE!', texture='ETCDAT/BI_IN.TIM (+ ETCDAT/ETCTIM.BIN entry 0)', u=0, v=29, w=46, h=15,
         en_rect=[0, 29, 48, 15], drawn_by='btl/battle_hud.c BTL_renderFinisherGaugeSegment (and std/vs): '
         'segments u/w/x per language', segments_es=FINISH_SEGMENTS_ES)
    WORDS['finish'] = dict(en=(en, 2, (0, 29, 48, 15)), es=(es, 2, (0, 29, 48, 15)), bg=(96, 96, 96), cap='FINISH!! -> REMATE! (barra del especial)')


# ---------------------------------------------------------------- 1. ○PUSH -> ○PULSA (BI_IN.TIM, ETCTIM.BIN 0)
def push():
    en = Tex('ETCDAT/BI_IN.TIM'); es = en.copy()
    INK, OL = 10, 1
    # the original letters (ink only), rows 9..15
    P = shift(ink_of(en, 139, 142, 9, 15, {INK}), -139, -9)
    U = shift(ink_of(en, 145, 149, 9, 15, {INK}), -145, -9)
    S = shift(ink_of(en, 152, 156, 9, 15, {INK}), -152, -9)
    L = mask(['#...', '#...', '#...', '#...', '#...', '#...', '####'])
    A = mask(['.###.', '#...#', '#...#', '#####', '#...#', '#...#', '#...#'])
    es.fill(137, 7, 184, 18, 0)  # clear PUSH (cols 165..183 are free, index 0)
    ink = set(); x = 139
    letters = ((P, 4), (U, 5), (L, 4), (S, 5), (A, 5))
    if PT_BR:
        E = mask(['####', '#...', '#...', '###.', '#...', '#...', '####'])
        R = mask(['###.', '#..#', '#..#', '###.', '#.#.', '#..#', '#..#'])
        T = mask(['#####', '..#..', '..#..', '..#..', '..#..', '..#..', '..#..'])
        letters = ((A, 5), (P, 4), (E, 4), (R, 4), (T, 5), (E, 4))
    for g, wd in letters:
        ink |= shift(g, x, 9); x += wd + 2
    for q in outline(ink, 8):
        es.s(*q, OL)
    for q in ink:
        es.s(*q, INK)
    x1 = max(q[0] for q in ink) + 1  # last outline column
    w = x1 - 128 + 1
    finish(en, es)
    save('BI_IN.TIM', en, es, 2)
    es.save_idx(f'{OUT}/ETCTIM.BIN.0.es.idx')
    rect(en='○PUSH', es='○PULSA', texture='ETCDAT/BI_IN.TIM (+ ETCDAT/ETCTIM.BIN entry 0, identical)',
         u=128, v=8, w=w, h=9, en_rect=[128, 8, 37, 9],
         drawn_by='btl/battle_hud.c:1232 BTL_renderFinisherReadyIcon (setUVWH 0x80,0x88,37,9); std/std_hud.c:945; vs/vs_hud.c:1126',
         screen_xy_change=f'quad w 37->{w}; to keep the right edge where it was move x 110->{110 - (w - 37)} '
                          f'and the backing box (108,-76,41,11) -> ({108 - (w - 37)},-76,{41 + w - 37},11); '
                          'same in all three HUD files')
    WORDS['push'] = dict(en=(en, 2, (128, 8, 37, 9)), es=(es, 2, (128, 8, w, 9)), bg=(96, 96, 96), cap='○PUSH -> ○PULSA (especial listo)')


# ---------------------------------------------------------------- 2. LIFE -> VIDA (LIFE.TIM)
def life():
    en = Tex('ETCHI/LIFE.TIM'); es = en.copy()
    INK, SH = 7, 8

    def shade(ink):  # extrusion 2 px to the left and 2 px down
        s = set()
        for x, y in ink:
            for a in range(3):
                for b in range(3):
                    s.add((x - a, y + b))
        return s - ink
    # check the rule on the original L and F
    for x0, x1 in ((51, 64), (77, 90)):
        ink = ink_of(en, x0, x1, 0, 23, {INK}); sh = ink_of(en, x0, x1, 0, 23, {SH})
        assert shade(ink) == sh, (x0, shade(ink) ^ sh)
    # glyph ink masks: 12 wide x 17 tall (texture rows 2..18), x offset +2 inside a 14-px cell
    V = mask(['##........##'] * 8 + ['.##......##.'] * 2 + ['..##....##..'] * 2 + ['...##..##...'] * 2 +
             ['....####....'] * 3)
    D = mask(['##########..'] * 2 + ['##........##'] * 13 + ['##########..'] * 2)
    A = mask(['..########..'] * 2 + ['##........##'] * 6 + ['############'] * 2 + ['##........##'] * 7)
    I_blk = en.block(69, 0, 4, 24)
    es.fill(48, 0, 112, 24, 0)
    for g, cx in ((V, 51), (D, 77), (A, 95)):
        ink = shift(g, cx + 2, 2)
        for q in shade(ink):
            es.s(*q, SH)
        for q in ink:
            es.s(*q, INK)
    es.paste(I_blk, 69, 0)
    save('LIFE.TIM', en, es, 0)
    rect(en='LIFE', es='VIDA', texture='ETCHI/LIFE.TIM', u=48, v=0, w=64, h=24, en_rect=[48, 0, 64, 24],
         drawn_by='murd/murd.c:99-117 MURD_LIVES_BACKDROP (GsSPRITE u48 v0 64x24), drawn by MURD_renderLivesBox (murd.c:708)',
         screen_xy_change='none (same rect, same place)')
    WORDS['life'] = dict(en=(en, 0, (48, 0, 64, 24)), es=(es, 0, (48, 0, 64, 24)), bg=(24, 24, 32), cap='LIFE -> VIDA (vidas)', add=True)


# ---------------------------------------------------------------- 3. Press Start Button -> Pulsa el botón START (TITLE256.TIM)
TCH = {'V': 0, 'L': 91, '9': 181, '8': 192, ' ': 255}
def title_glyphs(en):
    G = {}
    for ch, (a, b) in dict(P=(0, 6), r=(9, 13), e=(15, 20), s=(23, 27), S=(41, 47), t=(49, 53), a=(55, 60),
                           B=(79, 85), u=(88, 93), o=(107, 112), n=(115, 120)).items():
        G[ch] = [[255] * (b - a + 1)] + en.block(a, 241, b - a + 1, 10)   # row 0 = texture row 240 (free)
    def hand(rows):
        rows = rows + [''] * (11 - len(rows)); w = max(len(r) for r in rows)
        return [[TCH[c] for c in r.ljust(w)] for r in rows]
    G['l'] = hand(['', 'VV'] + ['VV'] * 8)
    G['b'] = hand(['', 'VV', 'VV', 'VVVVL', 'VV  VL', 'VV  VV', 'VV  VV', 'VV  VV', 'VV  VL', 'VVVVL'])
    G['ó'] = [r[:] for r in G['o']]
    G['ó'][0] = [TCH[c] for c in '   LV ']; G['ó'][1] = [TCH[c] for c in '  LV  ']
    G['p'] = hand(['', '', '', 'VVVVL', 'VV  VV', 'VV  VV', 'VVVVL', 'VV', 'VV', 'VV'])
    G['T'] = hand(['', 'VVVVVV'] + ['  VV  '] * 8)
    G['A'] = hand(['', '  9VV9  ', '  LVVL  ', ' 9VLLV9 ', ' LV  VL ', ' VL  LV ', '9VVVVVV9', 'LV    VL', 'VL    LV', 'VV    VV'])
    G['R'] = hand(['', 'VVVVL  ', 'VV 9VL ', 'VV  LV ', 'VV 9VL ', 'VVVVL  ', 'VV 8VL ', 'VV  LV ', 'VV  9VL', 'VV   VV'])
    return G

def title_compose(G, text, t, x0):
    x = x0; prev = None
    for ch in text:
        if ch == ' ':
            x += 6 - 2; prev = None; continue
        if prev is not None:
            x += 1 if ('t' in (prev, ch) or 'r' in (prev, ch) or prev.isupper() and ch.isupper()) else 2
        g = G[ch]
        for j, row in enumerate(g):
            for i, v in enumerate(row):
                if v != 255:
                    t.s(x + i, 240 + j, v)
        x += len(g[0]); prev = ch
    return x - x0

def title():
    en = Tex('ETCNA/TITLE256.TIM'); es = en.copy(); alt = en.copy()
    G = title_glyphs(en)
    es.fill(0, 240, 320, 256, 255); alt.fill(0, 240, 320, 256, 255)
    W = title_compose(G, ('Aperte START' if PT_BR else 'Pulsa el botón START'), es, 0)
    Wa = title_compose(G, 'Pulsa START', alt, 0)
    save('TITLE256.TIM', en, es, 0)
    alt.save_idx(f'{OUT}/TITLE256.TIM.alt-pulsa-start.es.idx')
    cx = -54 + 121 / 2
    rect(en='Press Start Button', es='Pulsa el botón START', texture='ETCNA/TITLE256.TIM', u=0, v=240, w=W, h=11,
         en_rect=[0, 241, 121, 10],
         drawn_by='main/main.c:5571-5572 renderPressStartToContinue (setXYWH -0x36,0x32,121,10; setUVWH 0,0xf1,121,10)',
         screen_xy_change=f'quad (-54,50,121,10) -> ({round(cx - W / 2)},49,{W},11), uv (0,241,121,10) -> (0,240,{W},11) '
                          '(one row higher for the accent of ó; letters stay on the same screen rows)')
    WORDS['title'] = dict(en=(en, 0, (0, 240, 121, 11)), es=(es, 0, (0, 240, W, 11)), alt=(alt, 0, (0, 240, Wa, 11)),
                          bg=(0, 0, 0), tint=(0, 1, 0), cap='Press Start Button -> Pulsa el botón START', W=W, Wa=Wa, cx=cx)


# ---------------------------------------------------------------- 4. TIME UP -> ¡TIEMPO! (STDTIM.BIN entry 2)
def timeup():
    en = Tex('STDDAT/STDTIM.BIN', 2); es = en.copy()
    OL = 15
    colour = {y: en.g(10, y) for y in range(9, 31)}          # per-row gradient (T stem)
    spans = dict(T=(0, 21), I=(26, 32), M=(37, 58), E=(62, 79), U=(96, 118), P=(120, 141))
    G = {}
    for k, (a, b) in spans.items():
        G[k] = shift(ink_of(en, a + 1, b - 1, 9, 30, set(range(1, 15))), -(a + 1), 0)
    for k in G:  # gradient really is per row
        a = spans[k][0] + 1
        assert all(en.g(x + a, y) == colour[y] for x, y in G[k]), k
    U = G['U']; uw = max(x for x, y in U) + 1
    O = {(x, y) for x, y in U if y >= 16} | {(x, 39 - y) for x, y in U if y >= 24}   # top = mirrored bottom
    G['O'] = O
    G['!'] = {(x, y) for x in range(5) for y in list(range(9, 24)) + list(range(27, 31))}
    G['¡'] = {(x, y) for x in range(5) for y in list(range(9, 13)) + list(range(16, 31))}
    es.fill(0, 8, 144, 32, 0)
    text = 'TEMPO!' if PT_BR else '¡TIEMPO!'
    widths = {k: max(x for x, y in g) + 1 for k, g in G.items()}
    total = sum(widths[c] + 2 for c in text) + 2 * (len(text) - 1)
    x = (144 - total) // 2 + 1; ink = set()
    for c in text:
        ink |= shift(G[c], x, 0); x += widths[c] + 2 + 2
    for q in outline(ink, 'R'):
        es.s(*q, OL)
    for q in ink:
        es.s(q[0], q[1], colour[q[1]])
    save('STDTIM.BIN.2', en, es, 0)
    rect(en='TIME UP', es='¡TIEMPO!', texture='STDDAT/STDTIM.BIN entry 2', u=0, v=8, w=144, h=24, en_rect=[0, 8, 144, 24],
         drawn_by='std/std_main.c:5481-5490 STD_renderTimeoutText; vs/vs_combat.c:2497 VS__renderTimeoutText',
         screen_xy_change='none (fits the same 144x24 rect at (-72,-12))')
    WORDS['timeup'] = dict(en=(en, 0, (0, 8, 144, 24)), es=(es, 0, (0, 8, 144, 24)), bg=(70, 60, 50), cap='TIME UP -> ¡TIEMPO!')


# ---------------------------------------------------------------- 6. VS MODE -> MODO VS (TAISEN2.TIM)
def vsmode():
    en = Tex('STDDAT/TAISEN2.TIM'); es = en.copy()
    OL, BG = 14, 15
    spans = dict(V=(49, 61), S=(63, 73), M=(79, 90), O=(92, 102), D=(104, 113), E=(115, 123))
    G = {k: {(x - a, y): en.g(x, y) for x in range(a, b + 1) for y in range(0, 14) if en.g(x, y) in (1, 2)}
         for k, (a, b) in spans.items()}
    W = {k: b - a + 1 for k, (a, b) in spans.items()}
    es.fill(48, 0, 127, 14, BG)
    text = 'MODO VS'; x = 49; ink = {}
    for c in text:
        if c == ' ':
            x += 5 - 1; continue
        for (i, y), v in G[c].items():
            ink[(x + i, y)] = v
        x += W[c] + 1
    for q in outline(set(ink), 8):
        es.s(*q, OL)
    for q, v in ink.items():
        es.s(*q, v)
    right = max(q[0] for q in ink) + 1
    assert right <= 126, right
    save('TAISEN2.TIM', en, es, 1)
    rect(en='VS MODE', es='MODO VS', texture='STDDAT/TAISEN2.TIM', u=48, v=0, w=79, h=14, en_rect=[48, 0, 77, 14],
         drawn_by='vs/vs_scene.c:201 VS_VERSUS_TEXT_PIECES[10] (w77 h14 dx113 dy9, u48 v0), drawn by VS_renderVersusText (vs_scene.c:1433)',
         screen_xy_change="VS_VERSUS_TEXT_PIECES[10]: w and uw 77->79, dx 113->112 (x -39 -> -40, stays centred); cols 125-126 of the texture are free (index 15)")
    WORDS['vsmode'] = dict(en=(en, 1, (48, 0, 77, 14)), es=(es, 1, (48, 0, 79, 14)), bg=(40, 40, 56), cap='VS MODE -> MODO VS')

# ---------------------------------------------------------------- 5. VS select box (TAISEN_F.TIM)
def taisen_f():
    en = Tex('STDDAT/TAISEN_F.TIM'); es = en.copy()
    BG, OL = 15, 1

    # --- headers: copy the original letters (cells s..e raw; side outline only next to own ink)
    HINK = {5, 12, 11, 0}
    L1 = dict(B=(122, 127), A=(129, 133), T=(136, 141), L=(152, 155), E=(158, 161), M=(169, 176), O=(179, 183),
              D=(186, 190), S=(204, 209), C=(230, 235))
    L2 = dict(S=(128, 133), T=(136, 141), A=(144, 148), G=(151, 156), E=(159, 162))
    def cell(y0, s, e):
        c = {}
        ink = {(x, y) for x in range(s, e + 1) for y in range(y0, y0 + 13) if en.g(x, y) in HINK}
        for x in range(s - 1, e + 2):
            for y in range(y0, y0 + 13):
                v = en.g(x, y)
                if s <= x <= e:
                    if v != BG: c[(x - s + 1, y - y0)] = v
                elif v == OL and any((x + dx, y + dy) in ink for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                    c[(x - s + 1, y - y0)] = OL
        return c, e - s + 1
    HG = {k: cell(0, *v) for k, v in L1.items()}
    for k, v in L2.items():
        HG.setdefault(k, cell(14, *v))
    rowc = {1: 5, 2: 5, 3: 5, 4: 5, 5: 12, 6: 12, 7: 11, 8: 11, 9: 0, 10: 0, 11: 5}
    def hand(rows):
        ink = {(x + 1, y + 1) for y, r in enumerate(rows) for x, ch in enumerate(r) if ch == '#'}
        c = {q: OL for q in outline(ink, 'R')}
        c.update({q: rowc[q[1]] for q in ink})
        return c, len(rows[0])
    HG['H'] = hand(['##...##'] * 5 + ['#######'] + ['##...##'] * 5)
    HG['I'] = hand(['##'] * 11)
    HG['N'] = hand(['##...##', '###..##', '####.##', '##.####', '##..###', '##...##', '##...##', '##...##', '##...##', '##...##', '##...##'])
    HG['R'] = hand(['####.', '#####', '##.##', '##.##', '#####', '####.', '##.##', '##.##', '##.##', '##.##', '##.##'])
    def header(text, y0, x0, x1):
        widths = [HG[c][1] if c != ' ' else None for c in text]
        total = 0; prev = None
        for c in text:
            if c == ' ': total += 7; prev = None; continue
            if prev: total += 2
            total += HG[c][1]; prev = c
        total += 2
        es.fill(x0, y0, x1 + 1, y0 + 13, BG)
        x = x0 + (x1 - x0 + 1 - total) // 2 + 1; prev = None; first = x - 1
        for c in text:
            if c == ' ': x += 7; prev = None; continue
            if prev: x += 2
            for (i, j), v in HG[c][0].items():
                cur = es.g(x - 1 + i, y0 + j)
                if v == OL and cur not in (BG, OL):
                    continue
                es.s(x - 1 + i, y0 + j, v)
            x += HG[c][1]; prev = c
        return first, x   # first outline col, one past last ink col
    h1 = header('MODO DE COMBATE', 0, 120, 243)
    h2 = header('ESCOLHA A ARENA' if PT_BR else 'ELIGE ESCENARIO', 14, 120, 243)

    # --- mode labels "7 vs 7 / BATTLE" -> "COMBATE / 7 vs 7" (1-px font, ink 3, outline 1)
    def lab_ink(s, e):
        return {(x - s, y - 248) for x in range(s, e + 1) for y in range(248, 255) if en.g(x, y) == 3}
    LG = {k: lab_ink(*v) for k, v in dict(B=(4, 9), A=(12, 17), T=(19, 23), E=(40, 44)).items()}
    LG['C'] = mask(['.####', '#....', '#....', '#....', '#....', '#....', '.####'])
    LG['O'] = mask(['.####.', '#....#', '#....#', '#....#', '#....#', '#....#', '.####.'])
    LG['M'] = mask(['#.....#', '##...##', '#.#.#.#', '#..#..#', '#.....#', '#.....#', '#.....#'])
    wd = {k: max(x for x, y in g) + 1 for k, g in LG.items()}
    word = 'COMBATE'
    total = sum(wd[c] for c in word) + (len(word) - 1) * 1 + 2
    for n in range(3):
        u0 = n * 52
        nums = es.block(u0, 232, 52, 14)          # "7 vs 7" rows 232..245
        es.fill(u0, 232, u0 + 52, 256, BG)
        es.paste(nums, u0, 241)                   # numbers go to rows 241..254
        x = u0 + (52 - total) // 2 + 1; ink = set()
        for c in word:
            ink |= shift(LG[c], x, 233); x += wd[c] + 1
        ol = outline(ink, 'R'); ol |= holes(ink | ol, u0, 232, u0 + 52, 241)
        for q in ol:
            if es.g(*q) == BG: es.s(*q, OL)
        for q in ink: es.s(*q, 3)
    lab_x = (52 - total) // 2

    # --- stage labels: swap the lines, COLISEUM -> COLISEO (raw blocks, the font's outline is hand drawn)
    def stage(u0, v0, w, colspans):
        top = es.block(u0, v0, w, 11); bot = es.block(u0, v0 + 13, w, 11)
        (cs, _), (os_, oe), (es_, ee) = colspans[0], colspans[1], colspans[5]   # C, O, E ink spans
        a = cs - 1 - u0; b = ee - u0                  # COLISE (C left outline .. E ink)
        word = [r[a:b + 1] for r in bot]
        # E's right outline column, only where E's own ink touches it
        col = []
        for j in range(11):
            y = v0 + 13 + j
            touch = any(en.g(ee, y + d) not in (BG, OL) for d in (-1, 0, 1) if 0 <= j + d < 11)
            col.append(OL if (en.g(ee + 1, y) == OL and touch) else BG)
        for j in range(11): word[j].append(col[j])
        ocell = [r[os_ - 1 - u0:oe + 2 - u0] for r in bot]      # O with both outline columns
        for j in range(11): word[j] += ocell[j]
        ww = len(word[0])
        stray = [(x, y, es.g(x, y)) for x in range(u0, u0 + w) for y in range(v0, v0 + 24)
                 if es.g(x, y) not in (BG, OL) and not (x < u0 + w and True) ]
        es.fill(u0, v0, u0 + w, v0 + 24, BG)
        es.paste(top, u0, v0 + 13)                    # BEATWOOD / DIGIMON / EXTRA to the lower line
        xo = u0 + (w - ww) // 2
        es.paste(word, xo, v0)
        return ww
    bspans = [(126, 128), (131, 134), (137, 139), (142, 142), (145, 148), (151, 153), (155, 158), (160, 164)]
    xspans = [(179, 181), (184, 187), (190, 192), (195, 195), (198, 201), (204, 206), (208, 211), (213, 217)]
    keep = (168, 71, en.g(168, 71))
    stage(120, 28, 52, bspans)
    stage(120, 52, 52, bspans)
    stage(172, 28, 48, xspans)
    es.s(*keep)   # an isolated texel of the original, transparent in the CLUT used; left as it was
    save('TAISEN_F.TIM', en, es, 1)
    rect(en='BATTLE MODE SELECT', es='MODO DE COMBATE', texture='STDDAT/TAISEN_F.TIM', u=120, v=0, w=124, h=14, en_rect=[120, 0, 124, 14],
         drawn_by='vs/vs_select.c:191 MODE_SELECT_SPRITES[0], VS__renderSelectModeBox (vs_select.c:1135)', screen_xy_change='none')
    rect(en='STAGE SELECT', es='ELIGE ESCENARIO', texture='STDDAT/TAISEN_F.TIM', u=120, v=14, w=124, h=14, en_rect=[120, 14, 124, 14],
         drawn_by='vs/vs_select.c:202 MAP_SELECT_SPRITES[0], VS__renderSelectMapBox (vs_select.c:1231)', screen_xy_change='none')
    for n, num in enumerate(['7 vs 7', '3 vs 3', '5 vs 5']):
        rect(en=f'{num} / BATTLE', es=f'COMBATE / {num}', texture='STDDAT/TAISEN_F.TIM', u=n * 52, v=232, w=52, h=23,
             en_rect=[n * 52, 232, 52, 23], drawn_by=f'vs/vs_select.c:{195 + n} MODE_SELECT_SPRITES[{4 + n}]',
             screen_xy_change='none (lines swapped inside the same rect: word rows 232-240, numbers 241-254)')
    for en_, es_, r, line in (('BEATWOOD / COLISEUM', 'COLISEO / BEATWOOD', [120, 28, 52, 24], 206),
                              ('DIGIMON / COLISEUM', 'COLISEO / DIGIMON', [120, 52, 52, 24], 205),
                              ('EXTRA / COLISEUM', 'COLISEO / EXTRA', [172, 28, 48, 24], 207)):
        rect(en=en_, es=es_, texture='STDDAT/TAISEN_F.TIM', u=r[0], v=r[1], w=r[2], h=r[3], en_rect=r,
             drawn_by=f'vs/vs_select.c:{line} MAP_SELECT_SPRITES', screen_xy_change='none (lines swapped in the same rect)')
    WORDS['taisen'] = dict(t=(en, es), h1=h1, h2=h2)

# ---------------------------------------------------------------- 7. the BATTLE start banner (155 blocks of 8x12)
BL = dict(
    B=['#####.', '##..##', '##..##', '#####.', '##..##', '##..##', '##..##', '#####.'],
    L=['##....'] * 7 + ['######'],
    U=['##..##'] * 7 + ['.####.'],
    C=['.#####'] + ['##....'] * 6 + ['.#####'],
    H=['##..##'] * 3 + ['######'] + ['##..##'] * 4,
    A=['...##...', '...##...', '..####..', '.##..##.', '.##..##.', '########', '##....##', '##....##'],
    i1=['#', '.', '#', '#', '#', '#', '#', '#'],          # ¡ one column wide
    e1=['#', '#', '#', '#', '#', '#', '.', '#'],          # !
    i2=['##', '..', '##', '##', '##', '##', '##', '##'],
    e2=['##', '##', '##', '##', '##', '##', '..', '##'],
)
BL['T'] = ['#####', '..#..', '..#..', '..#..', '..#..', '..#..', '..#..', '..#..']
def banner_layout(seq):
    """seq: list of (glyph, gap_after). -> list of (col,row) in letter order, width in columns."""
    cells = []; c = 0
    for g, gap in seq:
        rows = BL[g]
        for r, line in enumerate(rows):
            for i, ch in enumerate(line):
                if ch == '#': cells.append((c + i, r))
        c += len(rows[0]) + gap
    return cells, c - seq[-1][1]

def banner():
    en = json.load(open(f'{OUT}/battle-banner-en.json'))
    v = dict(
        main=[('i1', 1), ('L', 2), ('U', 2), ('C', 2), ('H', 2), ('A', 1), ('e1', 0)],
        wide=[('i2', 1), ('L', 1), ('U', 1), ('C', 1), ('H', 1), ('A', 1), ('e2', 0)],
        lucha=[('L', 2), ('U', 2), ('C', 2), ('H', 2), ('A', 0)],
    )
    if PT_BR:
        v = {k: [('L', 2), ('U', 2), ('T', 2), ('A', 1), ('e1', 0)] for k in v}
    res = {}
    for k, seq in v.items():
        cells, wcols = banner_layout(seq)
        x0 = -172 + (44 - wcols) // 2 * 8
        pts = [[x0 + c * 8, -48 + r * 12] for c, r in cells]
        res[k] = dict(n=len(pts), cols=wcols, pts=pts)
    # 155 entries: the main design has 154 blocks, the extra one doubles the last block (same place, no code change)
    m = res['main']; pts = m['pts'] + [m['pts'][-1]] * (155 - m['n'])
    assert len(pts) == 155
    json.dump(dict(text='LUTA!' if PT_BR else '¡LUCHA!', blocks_drawn=m['n'], entries=155,
                   note='[x,y] per block, same units as BTL_BATTLE_START_TEXT_POSITIONS (8x12 blocks); letters in reading order, '
                        'each letter row by row; the last entry repeats the one before it to keep the table at 155',
                   positions=pts), open(f'{OUT}/battle-banner-es.json', 'w'), ensure_ascii=False, indent=0)
    json.dump(dict(text='¡LUCHA! (2-column ¡ !)', blocks=res['wide']['n'], positions=res['wide']['pts']),
              open(f'{OUT}/battle-banner-es-alt-wide.json', 'w'), ensure_ascii=False, indent=0)
    json.dump(dict(text='LUCHA', blocks=res['lucha']['n'], positions=res['lucha']['pts']),
              open(f'{OUT}/battle-banner-es-alt-lucha.json', 'w'), ensure_ascii=False, indent=0)
    WORDS['banner'] = dict(en=[tuple(p) for p in en], main=[tuple(p) for p in pts], wide=res['wide']['pts'], lucha=res['lucha']['pts'],
                           counts={k: (r['n'], r['cols']) for k, r in res.items()})
    print('banner', {k: (r['n'], r['cols']) for k, r in res.items()})
    rect(en='BATTLE (start banner, 155 blocks)', es='¡LUCHA!', texture='ETCDAT/BI_IN.TIM blocks u128..151 v0 (unchanged)',
         u=None, v=None, w=None, h=None, en_rect=None,
         drawn_by='btl/battle_effect.c:586 BTL_BATTLE_START_TEXT_POSITIONS[155][2]; std/std_hud.c:178 STD_..., vs/vs_hud.c:185 VS_... (same table)',
         screen_xy_change='replace the three position tables with battle-banner-es.json (155 entries, 154 distinct blocks)')


if __name__ == '__main__':
    import importlib
    for f in sys.argv[1:] or ['push', 'life']:
        globals()[f]()
    json.dump(RECTS, open(f'{OUT}/rects.part.json', 'w'), ensure_ascii=False, indent=1)
