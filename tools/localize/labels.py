"""Small localized UI labels, rendered from the committed bitmap fonts.

Most labels use the established Spanish cells. Chinese triangle-menu labels
use larger SYSTEM_W cells. No Pillow, downloads or subprocesses.
"""
from collections import Counter
from functools import lru_cache
import json
import os

from tools.localize.catalog import LANGUAGES, UI, word

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LATIN = ('fr', 'de', 'it', 'ca')
BATTLE = dict(fr='COMBAT!', de='KAMPF!', it='LOTTA!', ja='バトル!', ca='COMBAT!', **{'zh-hans':'战斗！'})


@lru_cache(None)
def glyphs():
    import sys
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    import fontgen
    table = {ch: rows for ch, _, rows in fontgen.load_extra()}
    table.update({ch: rows for ch, (_, rows) in fontgen.load_font_txt(os.path.join(ROOT, 'tools/font/b.txt')).items()})
    return table


class LabelOverflow(ValueError):
    """A label's letters at their own size do not fit its cell (labels are never scaled)."""


def native(text, maxh=11):
    """-> the label's letters in font B (Chinese: the 8x8 UI font for a cell under 12 rows, else the 12-row one) at
    their own size, empty rows above and below cropped"""
    chinese = any('\u3400' <= char <= '\u9fff' for char in text)
    if chinese:
        from tools.chinese import read_json
        data = read_json(os.path.join(ROOT, 'tools/font/chinese-ui.json' if maxh < 12 else 'tools/font/chinese.json'))['glyphs']
        table = {char:[''.join('#' if not (bits & (0x8000 >> x)) else '.' for x in range(row[0]))
                       for bits in row[1:]] for char,row in data.items()}
    else:
        table = glyphs()
    height = len(next(iter(table.values())))
    rows = [[] for _ in range(height)]
    for char in text:
        if char == ' ':
            cell = ['....'] * height
        else:
            cell = table[char]
            if not chinese:
                width = max((row.rfind('#') + 1 for row in cell), default=1)
                cell = [row[:max(1, width)] + '.' for row in cell]
        for out, row in zip(rows, cell):
            out.extend(c == '#' for c in row)
    if not rows[0]:
        return [[False]]
    occupied = [y for y, row in enumerate(rows) if any(row)]
    if occupied:
        rows = rows[occupied[0]:occupied[-1] + 1]
    return rows


def mask(text, maxw, maxh):
    """-> the label's bitmap at its own size; LabelOverflow when it is wider than maxw or taller than maxh"""
    rows = native(text, maxh)
    if len(rows) > maxh or len(rows[0]) > maxw:
        raise LabelOverflow(f'{text!r} is {len(rows[0])}x{len(rows)}, the room is {maxw}x{maxh}')
    return rows


def compose(font, text, gap=1):
    """-> a committed pixel font's word (tools/localize/textures/*: '#' ink), bottom-aligned, as a bitmap"""
    missing = sorted({c for c in text if c not in font})
    if missing:
        raise LabelOverflow(f'{text!r}: no {"".join(missing)} in this font')
    glyphs_ = [font[c] for c in text]
    h = max(len(g) for g in glyphs_)
    rows = [[] for _ in range(h)]
    for i, g in enumerate(glyphs_):
        w = max(len(r) for r in g)
        for y in range(h):
            r = g[y - (h - len(g))] if y >= h - len(g) else ''
            rows[y].extend(c == '#' for c in r.ljust(w + (gap if i < len(text) - 1 else 0), '.'))
    return rows


def _legacy_scaled(text, maxw, maxh, preserve=False):
    """The old fit-by-resampling, kept only for the labels in OPEN (whose letters do not fit at their own size)."""
    rows = native(text, maxh)
    h, w = len(rows), len(rows[0])
    height = min(h, maxh)
    width = min(maxw, max(1, round(w * height / h)))
    if preserve:
        return [[any(rows[sy][sx]
                     for sy in range(y*h//height, max(y*h//height+1, (y+1)*h//height))
                     for sx in range(x*w//width, max(x*w//width+1, (x+1)*w//width)))
                 for x in range(width)] for y in range(height)]
    return [[rows[min(h - 1, y * h // height)][min(w - 1, x * w // width)] for x in range(width)] for y in range(height)]


def _load(name, path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(None)
def systemw_fonts():
    """-> (fonts, words): SYSTEM_W's label fonts and their renderers (tools/localize/textures/systemw)"""
    import sys
    base = os.path.join(ROOT, 'tools/localize/textures/systemw')
    fonts = _load('labels_systemw_fonts', os.path.join(base, 'fonts.py'))
    saved = sys.modules.get('fonts')
    sys.modules['fonts'] = fonts
    try:
        words = _load('labels_systemw_words', os.path.join(base, 'words.py'))
    finally:
        if saved is None:
            del sys.modules['fonts']
        else:
            sys.modules['fonts'] = saved
    return fonts, words


@lru_cache(None)
def pixfont():
    """-> FI_INFO's 3x6 / 3x7 fonts (tools/localize/textures/fi-info/pixfont.py)"""
    return _load('labels_fiinfo_pixfont', os.path.join(ROOT, 'tools/localize/textures/fi-info/pixfont.py'))


# Labels whose words do not fit their cell at the letters' own size in any committed font. They keep the look they had
# (font B resampled into the cell) until they get a bigger cell (relocated_rect in tools/localize/systemw.py gives a
# language its own), a shorter word, or letters drawn for that size (Japanese has no kana smaller than font B's nine
# rows); tools/test_label_scale.py fails on any other label that would need resampling.
# (language, text, (u, v, w, h)) -> how big the word is.
OPEN = {
    # the second SPEED cell, which the status tag mostly covers
    ('it', 'VELOCITÀ', (110, 72, 31, 12)): '33 px wide in the stat font',
    ('ca', 'RAPIDESA', (110, 72, 31, 12)): '36 px wide in the stat font',
    ('ja', 'すばやさ', (110, 72, 31, 12)): '39 px wide in font B',
    ('fr', 'GLACE', (86, 24, 18, 10)): '20 px wide in the element-name font',
    ('fr', 'CRASSE', (60, 96, 22, 10)): '24 px wide in the element-name font',
    ('de', 'ALTER', (209, 48, 20, 10)): '23 px wide in the tag font',
    ('de', 'NR.', (48, 34, 10, 7)): '12 px wide in the header font',
    ('de', 'LUFT', (50, 24, 14, 10)): '16 px wide in the element-name font',
    ('de', 'MECHA', (104, 24, 18, 10)): '22 px wide in the element-name font',
    ('it', 'OGGETTO', (0, 34, 25, 7)): '31 px wide in the header font',
    ('it', 'PREZZO', (25, 34, 23, 7)): '25 px wide in the header font',
    ('it', 'MECCA', (104, 24, 18, 10)): '22 px wide in the element-name font',
    ('it', 'SPORCO', (60, 96, 22, 10)): '24 px wide in the element-name font',
    ('ja', 'プロフィール', (0, 75, 53, 11)): 'font B 55x9',
    ('ja', 'しゅるい', (159, 48, 30, 10)): 'font B 38x9',
    ('ja', 'おもさ', (189, 48, 20, 10)): 'font B 28x9',
    ('ja', 'タイプ', (0, 56, 25, 8)): 'font B 28x9',
    ('ja', 'かつどう', (50, 56, 25, 8)): 'font B 39x9',
    ('ja', 'とくい', (144, 72, 29, 8)): 'font B 28x9',
    ('ja', 'はんい', (166, 110, 28, 12)): 'font B 30x9',
    ('ja', 'どうぐ', (0, 34, 25, 7)): 'font B 29x9',
    ('ja', 'ねだん', (25, 34, 23, 7)): 'font B 30x9',
    ('ja', 'ばん', (48, 34, 10, 7)): 'font B 20x9',
    ('ja', 'なまえ', (120, 96, 23, 9)): 'font B 30x9',
    ('ja', 'ばしょ', (58, 34, 22, 7)): 'font B 28x9',
    ('ja', 'てん', (80, 34, 26, 7)): 'font B 20x9',
    ('ja', 'かず', (102, 41, 20, 7)): 'font B 20x9',
    ('ja', 'ほのお', (0, 24, 20, 10)): 'font B 30x9',
    ('ja', 'かくとう', (20, 24, 30, 10)): 'font B 37x9',
    ('ja', 'くうき', (50, 24, 14, 10)): 'font B 28x9',
    ('ja', 'だいち', (64, 24, 22, 10)): 'font B 29x9',
    ('ja', 'こおり', (86, 24, 18, 10)): 'font B 28x9',
    ('ja', 'きかい', (104, 24, 18, 10)): 'font B 30x9',
    ('ja', 'よごれ', (60, 96, 22, 10)): 'font B 29x9',
    ('ja', 'どうぐ', (128, 48, 32, 7)): 'font B 29x9',
    ('ja', 'ひと', (160, 32, 32, 7)): 'font B 19x9',
    ('ja', 'ほめる', (128, 55, 32, 7)): 'font B 30x9',
    ('ja', 'ねる', (160, 39, 32, 7)): 'font B 20x9',
    ('ja', 'つる', (160, 55, 32, 7)): 'font B 20x9',
    ('ja', 'バトル', (0, 248, 51, 8)): 'font B 29x9',
    ('ca', 'INTEL·LECTE', (212, 82, 37, 12)): '42 px wide in the stat font',
    ('ca', 'OBJECTE', (0, 34, 25, 7)): '29 px wide in the header font',
    ('ca', 'NÚM.', (48, 34, 10, 7)): 'no Ú in the header font; font B 24x9',
    ('ca', 'QUANT.', (102, 41, 20, 7)): '24 px wide in the header font',
    ('ca', 'BRUTÍCIA', (60, 96, 22, 10)): '28 px wide in the element-name font',
    ('zh-hans', '编号', (48, 34, 10, 7)): 'UI font 16x7',
    ('zh-hans', '空气', (50, 24, 14, 10)): 'UI font 16x7',
}


ELEMENTS = {'FIRE', 'BATTLE', 'AIR', 'EARTH', 'ICE', 'MECH', 'FILTH', 'DARK', 'LIGHT', 'WATER', 'WEAPON', 'NATURE'}


def kind(en):
    """-> the SYSTEM_W font family of a label (by its English name). Labels of one kind are seen together (the gold
    headers, the status tags, TYPE/ACTIVE/SPECIAL, the stat names, the element names, the small headers of the
    technique page and the shops) and are drawn in one style."""
    if en in ('PROFILE', 'CONDITION', 'PARAMETER'):
        return 'gold'
    if en in ('NAME', 'DIGI', 'WEIGHT', 'AGE'):
        return 'tag'
    if en in ('TYPE', 'ACTIVE', 'SPECIAL'):
        return 'tsa'
    if en in ('HAPPINESS', 'SPEED', 'SPEED (alternative)', 'BRAINS'):
        return 'stat'
    if en in ELEMENTS:
        return 'element'
    return 'small'


def fits_b(text, rect, padding=2):
    """True when the word fits font B at its own size in the cell, with `padding` pixels to spare"""
    try:
        mask(text, rect[2] - padding, rect[3] - padding)
        return True
    except LabelOverflow:
        return False


def font_b_kinds(labelled, language):
    """-> the kinds (kind()) of SYSTEM_W labels [(item, text, rect)] drawn in font B. A word that fits font B at its own
    size keeps it (as before) unless another label of its kind does not: then (French, German, Italian, Catalan) every
    label of that kind takes the Spanish SYSTEM_W font of the kind, so labels seen together have one style (font B's
    nine rows beside the small font's five also ran into the technique page's values)."""
    kinds = {kind(item['en']) for item, _, _ in labelled}
    if language not in LATIN:
        return kinds
    return kinds - {kind(item['en']) for item, text, rect in labelled if not fits_b(text, rect)}


def battle_banner(language):
    """the battle-start banner: one 8x12 block per pixel of the word at its own size (French, German, Italian,
    Catalan: SYSTEM_W's 7-row stat letters; else font B), rows centred on the old seven rows' middle (y -12)"""
    if language in LATIN:
        rows = compose(systemw_fonts()[0].STAT, BATTLE[language])
    else:
        rows = native(BATTLE[language], 7)
    width = len(rows[0])
    if width > 36:
        raise LabelOverflow(f'{language}: battle banner {BATTLE[language]!r} is {width} blocks wide (36 at most)')
    top = -12 - (len(rows) - 1) * 12 // 2
    points = [[-(width * 8) // 2 + x * 8, top + y * 12] for y, row in enumerate(rows) for x, ink in enumerate(row) if ink]
    if not points or len(points) > 155:
        raise ValueError(f'{language}: battle banner has {len(points)} blocks')
    return dict(text=BATTLE[language], blocks_drawn=len(points), entries=155,
                positions=points + [points[-1]] * (155 - len(points)))


def apply(files, language, work):
    if language not in LANGUAGES:
        return
    from tools.localize.build import tim_entries, put_indices
    if language == 'zh-hans':
        for (code,path),data in list(files.items()):
            if code == 'en' and path.startswith('STDDAT/GRADE/'):
                files.setdefault((language,path),bytearray(data))
    col = LANGUAGES.index(language)
    grids = {}

    def grid(path, entry=0):
        key = path, entry
        if key not in grids:
            data = files[language, path]
            start, bpp, w, h = tim_entries(data)[entry]
            if bpp == 0:
                raw = data[start:start + w * h // 2]
                px = [v for b in raw for v in (b & 15, b >> 4)]
            elif bpp == 1:
                px = list(data[start:start + w * h])
            else:
                raise ValueError('indexed texture expected')
            grids[key] = w, h, px
        return grids[key]

    def clear(path, rect, background, entry):
        w, h, px = grid(path, entry)
        u, v, rw, rh = rect
        if not (0 <= u < u + rw <= w and 0 <= v < v + rh <= h):
            raise ValueError((path, rect, w, h))
        bands = [Counter(px[(v+y)*w+u:(v+y)*w+u+rw]).most_common(1)[0][0] for y in range(rh)] if background is None else [background] * rh
        for y in range(rh):
            px[(v+y)*w+u:(v+y)*w+u+rw] = [bands[y]] * rw
        return w, px

    def fit(text, rect, padding, shadow, font=None, gap=1):
        """-> the word's bitmap at its own size for the cell (font B, else the given pixel font), or LabelOverflow.
        Font B keeps its padding where it has the room, and gives it up (down to the drop shadow) where it has not."""
        _, _, rw, rh = rect
        if font is not None:
            bitmap = compose(font, text, gap)
            room = 1 if shadow is not None else 0
            if len(bitmap) + room > rh or len(bitmap[0]) + room > rw:
                raise LabelOverflow(f'{text!r} is {len(bitmap[0])}x{len(bitmap)} (+{room} shadow), the cell {rw}x{rh}')
            return bitmap
        for pad in range(padding, -1, -1):
            try:
                return mask(text, rw - pad, rh - pad)
            except LabelOverflow as error:
                problem = error
        raise problem

    def draw(path, rect, text, ink, background, shadow=None, entry=0, gradient=None, preserve=False, padding=2,
             fonts=(None,), bottom=False):
        """the word in the first of fonts (None = font B; else (pixel font, gap)) whose letters fit the cell at their
        own size, centred (bottom: on the cell's last row, its shadow included); a label in OPEN keeps its old look"""
        u, v, rw, rh = rect
        try:
            for i, font in enumerate(fonts):
                try:
                    bitmap = fit(text, rect, padding, shadow, *(font or (None,)))
                    break
                except LabelOverflow:
                    if i == len(fonts) - 1:
                        raise
        except LabelOverflow as error:
            if (language, text, tuple(rect)) not in OPEN:
                raise LabelOverflow(f'{language}: {path} {rect}: {error}') from None
            bitmap, bottom = _legacy_scaled(text, rw - padding, rh - padding, preserve), False
        w, px = clear(path, rect, background, entry)
        bh, bw = len(bitmap), len(bitmap[0])
        x0, y0 = u + (rw-bw)//2, v + (rh-bh)//2
        if bottom:
            y0 = max(v, v + rh - bh - (shadow is not None))
        points = {(x0+x, y0+y) for y, row in enumerate(bitmap) for x, on in enumerate(row) if on}
        if shadow is not None:
            for x, y in points:
                if x+1 < u+rw and y+1 < v+rh and (x+1,y+1) not in points:
                    px[(y+1)*w+x+1] = shadow
        for x, y in points:
            px[y*w+x] = gradient(y-v) if gradient else ink

    def paste(path, rect, cell, background, entry=0, bottom=False):
        """a word already rendered in its palette indices (SYSTEM_W's renderers), centred in the cell"""
        u, v, rw, rh = rect
        ch, cw = len(cell), len(cell[0])
        if ch > rh or cw > rw:
            raise LabelOverflow(f'{language}: {path} {rect}: {cw}x{ch}')
        w, px = clear(path, rect, background, entry)
        x0, y0 = u + (rw-cw)//2, v + (rh-ch if bottom else (rh-ch)//2)
        for y, row in enumerate(cell):
            px[(y0+y)*w+x0:(y0+y)*w+x0+cw] = row

    # Gold, tag, stat, element and header labels: retain each existing palette.
    from tools.localize.systemw import relocated_rect, check_care_button_cells

    items = json.load(open(os.path.join(work, 'systemw', 'rects.json')))
    check_care_button_cells(items)
    from tools.localize.status_art import check_cells
    check_cells(items)
    elements = ELEMENTS
    F, Wd = systemw_fonts()

    def rendered(item, text, rect):
        """-> (cell in palette indices, background, bottom-aligned) in the Spanish SYSTEM_W font of the item's kind"""
        en, rh = item['en'], rect[3]

        def first(*tries):
            sizes = []
            for make in tries:
                try:
                    cell = make()
                except KeyError as missing:
                    sizes.append(f'no {missing}')
                    continue
                if len(cell) <= rh and len(cell[0]) <= rect[2]:
                    return cell
                sizes.append(f'{len(cell[0])}x{len(cell)}')
            raise LabelOverflow(f'{language}: SYSTEM_W {rect}: {text!r} is {", ".join(sizes)}')

        def small(font):
            rows = Wd.pad(Wd.compose(font, text), 1, 1, 1, 1)
            ol = Wd.outline(rows, '#')
            return [[1 if c == '#' else 12 if c == 'c' else 13 if ol[y][x] else 15 for x, c in enumerate(r)]
                    for y, r in enumerate(rows)]

        def tsa(font, main, acc):
            rows = Wd.compose(font, text)
            return [[0] * len(rows[0])] + [[main if c == '#' else acc if c == 'x' else 0 for c in r] for r in rows] + \
                [[0] * len(rows[0])] * (rh - 1 - len(rows))

        if en in ('NAME', 'DIGI', 'WEIGHT', 'AGE'):
            narrow_compact = dict(F.TAG_NARROW, **{k: F.TAG_COMPACT[k] for k in 'ÂÀÈ'})
            return first(*(lambda f=f: Wd.r_tag(text, f) for f in (F.TAG, F.TAG_COMPACT, F.TAG_NARROW, narrow_compact))), 0, False
        if en in ('TYPE', 'ACTIVE', 'SPECIAL'):
            font, main, acc = dict(TYPE=(F.TSA, 12, 13), ACTIVE=(F.TSA_ACTIVE, 8, 9), SPECIAL=(F.TSA_SPECIAL, 6, 7))[en]
            return first(lambda: tsa(font, main, acc)), 0, False
        if en in ('HAPPINESS', 'SPEED', 'SPEED (alternative)', 'BRAINS'):
            return first(lambda: Wd.r_stat(text, h=rh)), 15, False
        if en in elements:
            return first(lambda: Wd.r_elem(text, h=rh)), 15, False
        return first(lambda: small(F.SMALL), lambda: small(F.SMALL_COMPACT)), 15, rh < 12

    labelled = [(item, word(item['es'], language), relocated_rect(item, language) or [item[k] for k in ('u','v','w','h')])
                for item in items if item['es'] in UI]
    in_b = font_b_kinds(labelled, language)
    for item, text, rect in labelled:
        clut = item['clut_row']
        ink, bg, sh = (1, None, 8) if clut == 8 else (2, 0, 1) if clut == 9 else (14, 15, 13) if item['en'] in ('HAPPINESS', 'SPEED', 'SPEED (alternative)', 'BRAINS') else (10, 15, 13) if item['en'] in elements else (1, 15, 13)
        for path, entry in [('ETCDAT/SYSTEM_W.TIM',0), ('ETCDAT/ETCTIM.BIN',8)]:
            if kind(item['en']) in in_b:
                draw(path, rect, text, ink, bg, sh, entry, preserve=True)
            elif item['en'] in ('PROFILE', 'CONDITION', 'PARAMETER'):
                fonts = [(F.GOLD5, 1), (F.GOLD4, 1)] if item['en'] != 'PARAMETER' else [(F.GOLD4, 1)]
                draw(path, rect, text, ink, bg, sh, entry, fonts=fonts)
            else:
                try:
                    cell, background, bottom = rendered(item, text, rect)
                except LabelOverflow:
                    if (language, text, tuple(rect)) not in OPEN:
                        raise
                    draw(path, rect, text, ink, bg, sh, entry, preserve=True)
                    continue
                paste(path, rect, cell, background, entry, bottom)

    # Triangle-menu cells; the unchanged DIGIMON label uses the disc's lettering.
    from tools.localize.fi_info import CELLS, SHARED_SIZES, check_cells
    # These dimensions are the shared non-English GameMenuLabel rows printed by
    # fi-info/build.py. Include the shadow and the nine-row REÑIR sprite.
    sizes = SHARED_SIZES
    pf = pixfont()
    check_cells([(u, v, *sizes[e]) for e, (_, u, v) in CELLS.items()])
    if language == 'zh-hans':
        from tools.localize.systemw import CHINESE_MENU_CELLS, CHINESE_MENU_SIZE, check_chinese_menu_cells
        check_chinese_menu_cells()
        for text, u, v in CHINESE_MENU_CELLS.values():
            for path, entry in [('ETCDAT/SYSTEM_W.TIM', 0), ('ETCDAT/ETCTIM.BIN', 8)]:
                draw(path, (u, v, *CHINESE_MENU_SIZE), text, 10, 15, 13,
                     entry, preserve=True, padding=0)
    else:
        for e, (text, u, v) in CELLS.items():
            width, height = sizes[e]
            for path, entry in [('ETCDAT/FI_INFO.TIM', 0), ('ETCDAT/ETCTIM.BIN', 4)]:
                # the Spanish labels' 3x6 letters, on the cell's baseline as REÑIR's are
                draw(path, (u, v, width, height), word(text, language), 15, 0, 1,
                     entry, preserve=True, padding=1, bottom=language in LATIN,
                     fonts=[(pf.LABEL6, 1), (pf.LABEL6_COMPACT, 1)] if language in LATIN else (None,))

    if language == 'zh-hans':
        from tools.localize.chinese_catalog import SMALL
        # The partner icon retains its original cell; its Chinese label fits it.
        for path, entry in [('ETCDAT/FI_INFO.TIM', 0), ('ETCDAT/ETCTIM.BIN', 4)]:
            draw(path, (80, 27, 28, 7), SMALL['partner'], 15, 0, 1,
                 entry, preserve=True, padding=1)

    # The four open-tournament captions sit below the AI-generated logo band.
    from tools.localize.build import tim_rgb
    for letter in 'ABCD':
        path = 'STDDAT/GRADE/GRADE' + letter + '.TIM'
        _, _, _, _, palette = tim_rgb(bytes(files[language,path]))
        def nearest(value):
            return min(range(1,len(palette)),key=lambda i: sum((a-b)**2 for a,b in zip(((palette[i]&31)*8,((palette[i]>>5)&31)*8,((palette[i]>>10)&31)*8),value)))
        white,grey = nearest((248,248,248)),nearest((64,64,64))
        captions = [('COLISÉE DIGITALMONSTER','TOURNOI OUVERT','CATÉGORIE '),
                    ('DIGITALMONSTER-KOLOSSEUM','OFFENES TURNIER','KLASSE '),
                    ('COLOSSEO DIGITALMONSTER','TORNEO APERTO','CATEGORIA '),
                    ('デジタルモンスター コロシアム','オープンたいかい','ランク '),
                    ('COLISEU DIGITALMONSTER','TORNEIG OBERT','CATEGORIA '),
                    ('数码宝贝竞技场','公开赛','等级 ')][col]
        draw(path,(0,64,256,14),captions[0],white,0,grey)
        draw(path,(0,78,256,15),captions[1],white,0,grey)
        draw(path,(0,93,256,27),captions[2]+letter,white,0,grey)

    push = ('APPUYEZ','DRÜCKEN','PREMI','おす','PREM','按下')[col]
    finish = ('FINI!','FINALE!','FINALE!','ひっさつ!','FINAL!','必杀！')[col]
    for path, entry in [('ETCDAT/BI_IN.TIM',0), ('ETCDAT/ETCTIM.BIN',0)]:
        draw(path,(139,8,31,9),push,10,0,1,entry,bottom=language in LATIN,
             fonts=[(pf.BUBBLE7,1)] if language in LATIN else (None,))
        draw(path,(0,29,46,15),finish,12,0,10,entry,lambda y: 11 if y >= 12 else 14 if y >= 10 else 12)
    draw('ETCHI/LIFE.TIM',(48,0,64,24),('VIE','LEBEN','VITA','のこり','VIDA','生命')[col],7,0,8)
    # (the title's Press Start line is the misc recipe's, in the disc's own letters: tools/localize/title_letters.py)
    draw('STDDAT/STDTIM.BIN',(0,8,144,24),('TEMPS ÉCOULÉ!','ZEIT UM!','TEMPO!','じかんぎれ!','TEMPS!','时间到！')[col],1,0,15,2)
    draw('STDDAT/TAISEN2.TIM',(48,0,79,14),('MODE VS','VS-MODUS','MODO VS','VS モード','MODE VS','对战模式')[col],1,15,14)
    draw('STDDAT/TAISEN_F.TIM',(120,0,124,13),('MODE COMBAT','KAMPFMODUS','MODO LOTTA','バトルモード','MODE COMBAT','战斗模式')[col],5,15,1)
    draw('STDDAT/TAISEN_F.TIM',(120,14,124,13),('CHOISIR UNE ARÈNE','ARENA WÄHLEN','SCEGLI ARENA','ステージせんたく','TRIA ESCENARI','选择场地')[col],5,15,1)
    draw('STDDAT/TAISEN_F.TIM',(0,248,51,8),('COMBAT','KAMPF','LOTTA','バトル','COMBAT','战斗')[col],3,0,1,
         bottom=language in LATIN, fonts=[(F.STAT,1)] if language in LATIN else (None,))
    if language == 'zh-hans':
        from tools.localize.chinese_catalog import SMALL, VS_ARENAS
        # The mode sprites sample the three baked captions above their numerals.
        for u in (0, 52, 104):
            draw('STDDAT/TAISEN_F.TIM', (u,232,52,9), SMALL['fight'], 3, 15, 1,
                 preserve=True, padding=1)
        for (u,v,w,ink), lines in zip(((120,52,52,11),(120,28,52,11),(172,28,48,8)), VS_ARENAS):
            for row, text in enumerate(lines):
                draw('STDDAT/TAISEN_F.TIM', (u,v+row*12,w,12), text, ink, 15, 1,
                     preserve=True, padding=1)
        from tools.localize.chinese_catalog import CUPS, CAPTIONS
        from tools.chinese import wrap, read_json
        caption_font = read_json(os.path.join(ROOT,'tools/font/chinese.json'))['glyphs']
        for name in [*CUPS, *('GRADE'+rank for rank in 'ABCDRS')]:
            path = 'STDDAT/GRADE/'+name+'.TIM'
            w,h,px = grid(path)
            _,_,_,_,palette = tim_rgb(bytes(files[language,path]))
            def nearest(rgb):
                return min(range(1,len(palette)),key=lambda i:sum((a-b)**2 for a,b in zip(
                    ((palette[i]&31)*8,((palette[i]>>5)&31)*8,((palette[i]>>10)&31)*8),rgb)))
            white,gold,blue = nearest((248,248,248)),nearest((248,216,56)),nearest((24,72,136))
            # A deterministic pixel-lettered notice needs no redistributed logo art.
            background = next((i for i,value in enumerate(palette) if value == 0),nearest((0,0,24)))
            px[:] = [background]*len(px)
            for y in (4,h-5):
                for x in range(8,w-8):px[y*w+x]=blue
            for x in (8,w-9):
                for y in range(4,h-4):px[y*w+x]=blue
            title = CAPTIONS[2]+name[-1] if name.startswith('GRADE') else ''.join(CUPS[name][:2])
            bitmap = mask(title, (w-24)//3, 12)
            bw,bh = len(bitmap[0]),len(bitmap)
            left,top=(w-bw*3)//2,22
            for y,row in enumerate(bitmap):
                for x,on in enumerate(row):
                    if not on:continue
                    for dy in range(3):
                        for dx in range(3):px[(top+y*3+dy)*w+left+x*3+dx]=gold
            lines = [CAPTIONS[0],CAPTIONS[1]] if name.startswith('GRADE') else [row for page in wrap(CUPS[name][2],caption_font,4) for row in page]
            for i,line in enumerate(lines):draw(path,(12,76+i*16,w-24,16),line,white,background,preserve=True,padding=1)
    for (path, entry), (w,h,px) in grids.items():
        put_indices(files[language,path],entry,px)
    json.dump(battle_banner(language),open(os.path.join(work,'battle-banner-es.json'),'w'),ensure_ascii=False)
