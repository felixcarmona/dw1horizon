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
# the technique panel's room for a label: from its x (-0x8c) to the arrow's (-0x6c, as in Spanish)
PANEL_LABEL_ROOM = 0x8c - 0x6c
# its labels end this many columns before the arrow (outlines included), so the two never touch
PANEL_LABEL_GAP = 1
PANEL_CELLS = (('POWER', 'POTENCIA'), ('RANG', 'ALCANCE'), ('SPEC', 'EFECTO'))


def relocated_rect(item, language=None):
    key = item['en'], item['es']
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

            def put(i, en, es=None, shifted=False):
                m = next(x for x in meta if x['en'] == en and (es is None or x['es'] == es))
                rect = relocated_rect(m, lang) if lang in ('fr', 'de', 'it', 'ja', 'ca', 'zh-hans') else None
                u, v, w, h = rect or [m[k] for k in ('u', 'v', 'w', 'h')]
                rr[i][2:] = [w, h, u, v + (128 if shifted else 0)]
                return w

            if name == 'STATS_VIEW_ELEMENTS':
                for i, en in [(0, 'PROFILE'), (1, 'CONDITION'), (2, 'PARAMETER'),
                              (3, 'NAME'), (4, 'DIGI'), (5, 'WEIGHT'), (6, 'AGE'),
                              (7, 'TYPE'), (8, 'SPECIAL'), (9, 'ACTIVE'),
                              (17, 'HAPPINESS'), (18, 'SPEED'), (19, 'BRAINS')]:
                    put(i, en)
            elif name == 'MOVES_VIEW_ELEMENT_NAMES' and lang in ('ja', 'zh-hans'):
                # Japanese and Chinese draw their names in font B, centred: their crops were measured on those words
                rr = existing[macro]
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
                for i, en, es in [(0, 'POWER', None), (1, 'RANG', 'ALC.'), (2, 'SPEC', None)]:
                    put(i, en, es)
                    if lang in ('fr', 'de', 'it', 'ja', 'ca', 'zh-hans'):
                        rr[i][0], rr[i][1] = [14, 82, 112][i], (-80) & 65535
            else:
                for i, en, es in [(0, 'TECH. DATA', None), (1, 'POWER', None),
                                  (2, 'MP', None), (3, 'RANG', 'ALCANCE'), (4, 'SPEC', None)]:
                    put(i, en, es, shifted=True)
                    if lang in ('fr', 'de', 'it', 'ca'):
                        # The word sits at its cell's left edge and the crop stops where the arrow starts (as in
                        # Spanish); MP, the original 7-row cell, on its arrow's middle row as the 12-row cells' words.
                        if i in (1, 3, 4):
                            rr[i][2] = min(rr[i][2], PANEL_LABEL_ROOM)
                        rr[i][1] = [-6, 27, 46, 61, 78][i] & 65535
                    elif lang in ('ja', 'zh-hans'):
                        # Absolute coordinates: regeneration is idempotent.
                        rr[i][1] = [-6, 27, 44, 61, 78][i] & 65535
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
