"""SYSTEM_W source rectangles shared by the localized texture and C crop tables.

The 11-row translated glyphs need taller cells than Spanish's 5-row header font.
The atlas slots below were checked against the original texture: x>=128,y>=110
and x=96..211,y=84..95 contain no native sprite. Keep shop headers in their old
cells. C tables are exported by the developer crop generator, not at runtime.
"""


# Care-only native-cap frames, in unused atlas holes (coordinates relative to SYSTEM_W.TIM).
# These must remain free in every localized label set; the C header uses v + 128.
CARE_BUTTON_RECTS = ((240, 27, 16, 12), (240, 39, 16, 12), (192, 96, 16, 12))
CARE_BUTTON_GUARD_RECTS = ((239, 27, 1, 12), (239, 39, 1, 12))
CARE_BUTTON_CLUT_RECT = (128, 124, 64, 1)  # VRAM words (352,252), 16 colors


CHINESE_MENU_CELLS = {
    1: ('道具', 56, 95), 2: ('状态', 80, 96), 3: ('玩家', 104, 96),
    4: ('表扬', 208, 96), 5: ('训斥', 232, 96),
    6: ('睡觉', 232, 110), 7: ('钓鱼', 176, 70),
}
CHINESE_MENU_SIZE = (24, 13)


def check_chinese_menu_cells():
    from tools.localize.fi_info import overlaps
    from tools.localize.status_art import TAG_RECT
    protected = [(128,110,38,12), (166,110,28,12), (194,110,34,12),
                 (96,84,64,12), (160,84,38,12), (144,96,37,9), (144,72,29,8)]
    protected += list(CARE_BUTTON_RECTS) + list(CARE_BUTTON_GUARD_RECTS) + [CARE_BUTTON_CLUT_RECT]
    protected.append(TAG_RECT)
    used = []
    for _, u, v in CHINESE_MENU_CELLS.values():
        rect = (u, v, *CHINESE_MENU_SIZE)
        if not (0 <= u <= 256-24 and 0 <= v <= 128-13) or any(overlaps(rect,r) for r in protected+used):
            raise ValueError(f'Chinese menu label overlaps another SYSTEM_W crop: {rect}')
        used.append(rect)


from tools.localize.tech_rows_art import other_cell
from tools.localize.catalog import word
from tools.localize.labels import columns


# French, German, Italian and Catalan element names, in the element-name font: the original row (x 0..124, the last
# two columns free) cut again so that the longest of the four languages' names fits each cell (MECHA, MECCA 22 px,
# COMBAT 26), and the filth row's cell widened over the free columns up to the weapon row's name (BRUTÍCIA 28)
LATIN_ELEMENT_CELLS = {
    ('FIRE', 'FUEGO'): (0, 24, 20, 10), ('BATTLE', 'COMBATE'): (20, 24, 26, 10), ('AIR', 'AIRE'): (46, 24, 16, 10),
    ('EARTH', 'TIERRA'): (62, 24, 20, 10), ('ICE', 'HIELO'): (82, 24, 20, 10), ('MECH', 'MECA'): (102, 24, 22, 10),
    ('FILTH', 'MUGRE'): (60, 96, 30, 10),
}
# the technique panel and header cells
TECH_CELLS = {
    ('POWER', 'POTENCIA'): (128, 110, 38, 12),
    ('RANG', 'ALC.'): (166, 110, 28, 12),
    ('SPEC', 'EFECTO'): (194, 110, 34, 12),
    ('TECH. DATA', 'DATOS TÉC.'): (96, 84, 64, 12),
    ('RANG', 'ALCANCE'): (160, 84, 38, 12),
}
# the stat names' cells of the languages drawn by labels.py: as wide as the Spanish ones were before the Spanish words
# were shortened (textures/systemw/build.py ES_WORDS), so that every language keeps its room
STAT_CELLS = {
    ('HAPPINESS', 'FELICIDAD'): (212, 58, 36, 12), ('SPEED', 'VELOCIDAD'): (212, 70, 39, 12),
    ('BRAINS', 'INTELECTO'): (212, 82, 37, 12),
}
# Japanese cells narrowed to the room its words have where the English ones start (STAT_LEFT, TECH_HEADER_LEFT): their
# font B words do not fit at their own size and are drawn narrower (labels.py OPEN), as the Chinese ones are
JA_CELLS = {
    ('SPEED', 'VELOCIDAD'): (212, 70, 35, 12), ('BRAINS', 'INTELECTO'): (212, 82, 35, 12),
    ('POWER', 'POTENCIA'): (128, 110, 34, 12), ('RANG', 'ALC.'): (166, 110, 20, 12),
    ('SPEC', 'EFECTO'): (194, 110, 27, 12),
}
# the row of a technique cell its word's letters stand on (accents and font B's nine rows above it, its shadow and
# outline below), and the lines the English labels stand on: the Techset header's (the Final row's is 67 lower, as
# renderDigimonMovesView draws it at the header's y + 0x43) and the panel's title and rows (MP's is the original's)
TECH_LINE = 9
TECH_HEADER_LINE = -71
TECH_PANEL_LINES = (3, 34, None, 68, 85)
# the technique panel's room for a label: from its x (-0x8c) to the arrow's (-0x6c, as in Spanish)
PANEL_LABEL_ROOM = 0x8c - 0x6c
# its labels end this many columns before the arrow (outlines included), so the two never touch
PANEL_LABEL_GAP = 1
PANEL_CELLS = (('POWER', 'POTENCIA'), ('RANG', 'ALCANCE'), ('SPEC', 'EFECTO'))
# where a list's labels start (screen x from the centre, as the crop tables count it; letters only, without outline or
# shadow), in every translated language: the stat names where the native words of their list start (36 on screen for
# Tired, 185 for Off. and Def., the same gap after the icon: the original's HAPPINESS, SPEED and BRAINS, drawn in a
# smaller font, start three columns nearer their icons), the technique panel's labels where the English ones start,
# and each Techset header (MP included) over the first pixel of its value column below it, as measured on screen:
# the power's digits (17), the dots before the MP cost (54), the range (95) and the effect icon (118). A word ends
# before its bar (the care row's where the English word is cut, the parameters' two columns before the bar's inset,
# the shadow between), a header TECH_HEADER_GAP columns before the next header's letters (two clear columns between
# their outlines) and the last one before the frame (146); a word that would run further is shortened or drawn
# narrower (textures/systemw/build.py ES_WORDS, catalog.py, JA_CELLS), never moved
STAT_LEFT = {'HAPPINESS': -124, 'SPEED': -1, 'BRAINS': -1}
STAT_END = {'HAPPINESS': -88, 'SPEED': 32, 'BRAINS': 32}
PANEL_LEFT = -139
TECH_HEADER_LEFT = (17, 95, 118)    # POWER, RANG, SPEC
TECH_MP_LEFT = 54
TECH_MP = (0x44, 69, 77)            # the original MP header's crop x and its letters' columns (English keeps them)
TECH_HEADER_GAP = 5
TECH_HEADER_END = 143


def s16(x):
    return x - 65536 if x >= 32768 else x


def stat_left(en, span):
    """-> the x of a stat name's letters, given their (first, last) columns: the list's; ValueError past the bar"""
    first, last = span
    if STAT_LEFT[en] + last - first > STAT_END[en]:
        raise ValueError(f'{en}: the letters {span} run past the bar ({STAT_END[en]}) from {STAT_LEFT[en]}')
    return STAT_LEFT[en]


def header_lefts(spans):
    """-> the x of each Techset header's letters (POWER, RANG, SPEC), given each one's (first, last) columns: the
    header's column's; ValueError where a word would come nearer the next header than TECH_HEADER_GAP, or the frame"""
    ends = (TECH_MP_LEFT - TECH_HEADER_GAP, TECH_HEADER_LEFT[2] - TECH_HEADER_GAP, TECH_HEADER_END)
    for left, end, (first, last), name in zip(TECH_HEADER_LEFT, ends, spans, ('POWER', 'RANG', 'SPEC')):
        if left + last - first > end:
            raise ValueError(f'the Techset header {name} {(first, last)} runs past {end} from {left}')
    return TECH_HEADER_LEFT


def relocated_rect(item, language=None):
    key = item['en'], item['es']
    if language == 'ja' and key in JA_CELLS:
        return JA_CELLS[key]
    if language in ('fr', 'de', 'it', 'ja', 'ca', 'zh-hans') and key in STAT_CELLS:
        return STAT_CELLS[key]
    if language in ('fr', 'de', 'it', 'ca') and key in LATIN_ELEMENT_CELLS:
        return LATIN_ELEMENT_CELLS[key]
    return other_cell(key, language) or TECH_CELLS.get(key)


def check_care_button_cells(items):
    """Reject label crops that would overwrite care frames, guard columns or their CLUT."""
    from tools.localize.fi_info import overlaps
    protected = list(CARE_BUTTON_RECTS) + list(CARE_BUTTON_GUARD_RECTS) + [CARE_BUTTON_CLUT_RECT]
    for item in items:
        for rect in ([item[k] for k in ('u', 'v', 'w', 'h')], relocated_rect(item), relocated_rect(item, 'zh-hans')):
            if rect and any(overlaps(rect, reserved) for reserved in protected):
                raise ValueError(f'SYSTEM_W label overlaps the care badge: {item["en"]} {rect}')


def crop_tables(source, metadata):
    """Regenerate the four C sprite tables using each source recipe's rectangles.

    Language differences stay in data, so LANGxx.BIN can restore them on every
    language switch. The English branch and non-label sprites remain intact.
    """
    import re
    for items in metadata.values():
        check_care_button_cells(items)
        from tools.localize.status_art import check_cells
        check_cells(items)
    for name in ('MOVES_VIEW_TECHSET_TEXT', 'STATS_VIEW_ELEMENTS',
                 'MOVES_VIEW_ELEMENT_NAMES', 'MOVES_SELECTED_LABELS'):
        begin = source.index('IconRect ' + name + '[')
        a = source.index('#if MOD_LANG_BUILD', begin)
        b = source.index('#else', a)
        first = re.split(r'#elif|#else', source[a:b])[0]
        rows = [[int(x, 16) for x in re.findall(r'0x([a-fA-F0-9]+)', line)]
                for line in first.splitlines()[1:] if '{' in line]
        existing = {m.group(1): [[int(x, 16) for x in re.findall(r'0x([a-fA-F0-9]+)', line)]
                                 for line in m.group(2).splitlines() if '{' in line]
                    for m in re.finditer(r'MOD_LANG_BUILD == MOD_LANG_(\w+)\n(.*?)(?=#elif|$)', source[a:b], re.S)}
        variants = []
        for lang, macro in [('es', 'ES'), ('pt-br', 'PT_BR'), ('fr', 'FR'),
                            ('de', 'DE'), ('it', 'IT'), ('ja', 'JA'), ('ca', 'CA'), ('zh-hans', 'ZH')]:
            meta = metadata['pt-br' if lang == 'pt-br' else 'es']
            rr = [r.copy() for r in rows]

            def m_es(en, es=None):
                return next(x for x in meta if x['en'] == en and (es is None or x['es'] == es))['es']

            def put(i, en, es=None, shifted=False):
                m = next(x for x in meta if x['en'] == en and (es is None or x['es'] == es))
                rect = relocated_rect(m, lang) if lang in ('fr', 'de', 'it', 'ja', 'ca', 'zh-hans') else None
                u, v, w, h = rect or [m[k] for k in ('u', 'v', 'w', 'h')]
                rr[i][2:] = [w, h, u, v + (128 if shifted else 0)]
                return w

            def lifted(i, en, y):
                # a Japanese or Chinese word taller than its cell leaves room for above the line goes up with its crop
                from tools.localize.labels import lift
                m = next(x for x in meta if x['en'] == en)
                rect = relocated_rect(m, lang) or [m[k] for k in ('u', 'v', 'w', 'h')]
                rr[i][1] = (y - lift(m, word(m['es'], lang), rect, lang)) & 65535

            if name == 'STATS_VIEW_ELEMENTS':
                for i, en in [(0, 'PROFILE'), (1, 'CONDITION'), (2, 'PARAMETER'),
                              (3, 'NAME'), (4, 'DIGI'), (5, 'WEIGHT'), (6, 'AGE'),
                              (7, 'TYPE'), (8, 'SPECIAL'), (9, 'ACTIVE'),
                              (17, 'HAPPINESS'), (18, 'SPEED'), (19, 'BRAINS')]:
                    put(i, en)
                    if en in STAT_LEFT:
                        # left-aligned in its cell (labels.py): the letters start where the English ones do
                        span = columns(meta, next(x for x in meta if x['en'] == en), lang)
                        rr[i][0] = (stat_left(en, span) - span[0]) & 65535
                    lifted(i, en, rows[i][1] - (rows[i][1] >> 15 << 16))
            elif name == 'MOVES_VIEW_ELEMENT_NAMES' and lang in ('ja', 'zh-hans'):
                # Japanese and Chinese draw their names in font B: their crops were measured on those words (at y 0)
                rr = [r.copy() for r in existing[macro]]
                for i, en in enumerate(('FIRE', 'BATTLE', 'AIR', 'NATURE', 'ICE', 'MECH', 'FILTH',
                                        'DARK', 'LIGHT', 'WATER', 'WEAPON', 'EARTH')):
                    lifted(i, en, 0)
            elif name == 'MOVES_VIEW_ELEMENT_NAMES':
                # labels.py draws a name at its cell's right edge: the cell's right edge goes against the grid
                for i, en in enumerate(('FIRE', 'BATTLE', 'AIR', 'NATURE', 'ICE', 'MECH', 'FILTH',
                                        'DARK', 'LIGHT', 'WATER', 'WEAPON', 'EARTH')):
                    put(i, en, shifted=True)
                    if lang in ('fr', 'de', 'it', 'ca'):
                        # cropped to the letters (labels.py draws the name at its cell's right edge), so the right
                        # column can centre a name as it centres the originals
                        from tools.localize.labels import element_width
                        m = next(x for x in meta if x['en'] == en)
                        ink = element_width(word(m['es'], lang))
                        rr[i][4] += rr[i][2] - ink
                        rr[i][2] = ink
                    rr[i][0] = (-45 - rr[i][2]) & 65535
                    rr[i][1] = 1 if rr[i][3] == 8 else 0    # posY: a name with no blank row on top goes a line lower
            elif name == 'MOVES_VIEW_TECHSET_TEXT':
                headers = [(0, 'POWER', None), (1, 'RANG', 'ALC.'), (2, 'SPEC', None)]
                spans = [columns(meta, next(x for x in meta if x['en'] == en and (es is None or x['es'] == es)), lang)
                         for _, en, es in headers]
                for (i, en, es), left, (first, _) in zip(headers, header_lefts(spans), spans):
                    put(i, en, es)
                    rr[i][0] = (left - first) & 65535
                    if lang in ('fr', 'de', 'it', 'ja', 'ca', 'zh-hans'):
                        rr[i][1] = (TECH_HEADER_LINE - TECH_LINE) & 65535
                rr[3][0] = TECH_MP_LEFT - (TECH_MP[1] - TECH_MP[0])     # the original MP, over its column too
            else:
                for i, en, es in [(0, 'TECH. DATA', None), (1, 'POWER', None),
                                  (2, 'MP', None), (3, 'RANG', 'ALCANCE'), (4, 'SPEC', None)]:
                    put(i, en, es, shifted=True)
                    if i != 2:
                        # the letters start where the English ones do (font B has no outline column on the left)
                        first, _ = columns(meta, next(x for x in meta if x['en'] == en and
                                                      (es is None or x['es'] == es)), lang)
                        rr[i][0] = (PANEL_LEFT - first) & 65535
                    if lang in ('fr', 'de', 'it', 'ja', 'ca', 'zh-hans') and i != 2:
                        # The word sits at its cell's left edge, standing on the English label's line, and the crop
                        # stops where the arrow starts (as in Spanish); MP keeps the original cell, row and arrow.
                        if i in (1, 3, 4):
                            # (a Japanese word wider than that, いりょく, keeps the columns it needs)
                            from tools.localize.labels import native
                            wide = len(native(word(m_es(en, es), lang))[0]) if lang in ('ja', 'zh-hans') else 0
                            rr[i][2] = min(rr[i][2], max(PANEL_LABEL_ROOM - (s16(rr[i][0]) + 0x8c), wide))
                        rr[i][1] = (TECH_PANEL_LINES[i] - TECH_LINE) & 65535
                    elif lang in ('fr', 'de', 'it', 'ja', 'ca', 'zh-hans'):
                        rr[i][1] = 46   # absolute coordinates: regeneration is idempotent
            variants.append(('#if' if not variants else '#elif') +
                            ' MOD_LANG_BUILD == MOD_LANG_' + macro + '\n' +
                            ''.join('\t{ ' + ', '.join('0x%04x' % x for x in r) + ' },\n' for r in rr))
        source = source[:a] + '\n'.join(variants) + '\n' + source[b:]
    from tools.localize.status_art import crop_tables as status_crops
    return status_crops(source)


def main():
    import argparse
    import json
    import tempfile
    from pathlib import Path
    from tools.localize.build import run
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('decomp', type=Path)
    parser.add_argument('--extracted', type=Path, default=Path('extracted'))
    parser.add_argument('--write', action='store_true', help='otherwise verify the generated C tables')
    a = parser.parse_args()
    metadata = {}
    for lang in ('es', 'pt-br'):
        with tempfile.TemporaryDirectory(dir=a.decomp.resolve().parent) as work:
            d = run('systemw', [['build.py']], work, str(a.extracted.resolve()), language=lang)
            metadata[lang] = json.loads(Path(d, 'rects.json').read_text())
    path = a.decomp / 'src/main/game_menu.c'
    old = path.read_text()
    new = crop_tables(old, metadata)
    if a.write:
        path.write_text(new)
    elif old != new:
        raise SystemExit('SYSTEM_W C crops differ from the localized texture metadata; rerun with --write')
    print('SYSTEM_W: all seven localized crop tables match their source rectangles')


if __name__ == '__main__':
    main()
