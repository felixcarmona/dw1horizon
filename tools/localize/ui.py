"""Audit the actual cropped menu fields in all languages and runtime fonts.

Coordinates refer to game_menu.c. Packed tab positions use the original cells;
ink is then drawn in New, Original or Classic, as drawGlyphPieces does.
"""
import argparse
import functools
import json
from pathlib import Path

from tools import fontgen
from tools.languages import CODES

ROOT = Path(__file__).resolve().parents[2]
FONTS = ('b', 'original', 'classic')
MOVE_LIMIT = 120
FINISHER_LIMIT = 136
ITEM_LIMIT = 93  # Shop lists: 0x69 - 12; inventory and bank allow 96.
YES_NO_LIMIT = 48
CONFIRM_LIMIT = 36
# (screen x, source u, copied width), PLAYER_TAB_CROPS in game_menu.c.
PLAYER_CROPS = {
 'en': [(-134,0,48),(-69,48,44),(-12,92,32),(37,124,44),(102,168,36)],
 'es': [(-140,0,60),(-67,60,40),(-12,100,32),(33,132,52),(94,184,52)],
 'pt-br': [(-140,0,60),(-63,60,32),(-12,92,32),(33,124,52),(94,176,52)],
 'fr': [(-136,0,52),(-67,52,40),(-12,92,32),(33,124,52),(102,176,36)],
 'de': [(-136,0,52),(-67,52,40),(-12,92,32),(33,124,52),(96,176,48)],
 'it': [(-136,0,52),(-67,52,40),(-12,92,32),(37,124,44),(98,168,44)],
 'ja': [(-122,0,24),(-65,24,36),(-14,60,36),(41,96,36),(108,132,24)],
 'ca': [(-140,0,60),(-67,60,40),(-12,100,32),(33,132,52),(94,184,52)],
 'zh-hans': [(-122,0,24),(-65,24,36),(-14,60,36),(41,96,36),(108,132,24)],
}
PLAYER_TABS = [(-145,70),(-76,58),(-19,46),(26,66),(91,58)]
DIGIMON_TABS = [(-145,76),(-70,64)]


@functools.lru_cache(None)
def glyphs(font, language):
    if language == 'zh-hans':
        from tools.chinese import font_glyphs
        from tools.localize.executable.chinese_layout import cell_width
        return {c:(cell_width(c), [''.join('#' if not bits & (1 << (15-i)) else '.'
                                        for i in range(12)) for bits in data[1:]])
                for c,data in font_glyphs().items()}
    codes, base = fontgen.committed_glyphs()
    original = fontgen.by_char(codes, *fontgen.font_tables('original', (codes,base)))
    if font == 'classic':
        out = {c:fontgen.to_pixel(rows, blank_adv=advance) for c,(advance,rows) in original.items()}
        # classicRows centres digits in a fixed seven-pixel advance.
        for c, (advance, rows) in list(out.items()):
            if c.isascii() and c.isdigit():
                shift = int((7 - advance) / 2)
                out[c] = (7, ['.' * shift + row[:12-shift] for row in rows])
        return out
    return original if font == 'original' else fontgen.by_char(codes,*fontgen.font_tables(font,(codes,base)))


def bounds(text, font, language, origin=0, script=False):
    table = glyphs(font, language)
    pen, left, right, previous = origin, None, origin, None
    kern = fontgen.kern('b') if font == 'b' and language != 'zh-hans' else {}
    for char in text:
        advance, rows = table.get(char, table['?'])
        pen += kern.get((previous,char),0)
        x = pen & ~3 if font == 'original' and language != 'zh-hans' else pen
        columns = [i for row in rows for i,ink in enumerate(row) if ink == '#']
        if columns:
            left = x+min(columns) if left is None else min(left,x+min(columns))
            right = max(right,x+max(columns)+1)
        pen += 8 if script and font == 'original' and char == ' ' else advance
        previous = char
    return (origin if left is None else left), right


def fitted_width(text, font, language):
    """fitStringMode's reachable modes; New and Chinese keep their own glyphs."""
    own = bounds(text,font,language)[1]
    if font == 'b' or language == 'zh-hans':
        return own
    modes = [fontgen.fit_layout(text,m,metrics_only=True)[1] for m in (1,2)]
    return min([own,*modes])


def tab_problems(key, value, font, language):
    if key == 'main.MAIN_D_801238A0':
        crops = [(-138,0,60),(-63 if language == 'en' else -68,60,48 if language == 'en' else 60)]
        tabs = DIGIMON_TABS
    elif key == 'main.MAIN_D_80123A18':
        crops, tabs = PLAYER_CROPS[language], PLAYER_TABS
    else:
        return []
    cells = glyphs('original',language)
    active = glyphs(font,language)
    groups = [[] for _ in crops]
    pos = 0
    for char in value:
        piece = max(i for i,(_,u,_) in enumerate(crops) if u <= pos & ~3)
        advance = cells.get(char,cells['?'])[0]
        groups[piece].append((char,pos,advance))
        pos += advance
    errors = []
    for i,(group,(x,u,width),(tab_x,tab_w)) in enumerate(zip(groups,crops,tabs)):
        while group and group[0][0] == ' ':group.pop(0)
        while group and group[-1][0] == ' ':group.pop()
        if not group:
            errors.append(f'tab {i+1} has no label');continue
        text = ''.join(c for c,_,_ in group)
        span = group[-1][1]+group[-1][2]-group[0][1]
        ink = sum(active.get(c,active['?'])[0] for c,_,_ in group)-1
        if font == 'b' and language != 'zh-hans':ink += fontgen.kerning(text,'b')
        pen = group[0][1]+(span-ink)//2
        left,right = bounds(text,font,language,pen)
        screen_left,screen_right = x+left-u,x+right-u
        if left < u or right > u+width or screen_left < tab_x+1 or screen_right > tab_x+tab_w-2:
            errors.append(f'tab {i+1} {text!r} ink {screen_left}:{screen_right} exceeds crop {u}:{u+width} or tab {tab_x+1}:{tab_x+tab_w-2}')
    return errors


def name_problems(key, value, font, language):
    if not key.startswith('main.MOVE_NAMES.'):
        return []
    move = int(key.rsplit('.',1)[1])
    limit = FINISHER_LIMIT if 58 <= move <= 112 else MOVE_LIMIT
    width = fitted_width(value,font,language)
    return [f'move name {value!r} is {width} px after fitting; field is {limit} px'] if width > limit else []


def answer_problems(value, font, language, width, centred=False):
    words = value.split()
    if len(words) != 2:
        return ['Yes/No row must contain exactly two whole answers']
    errors = []
    table = glyphs(font, language)
    for word in words:
        advance = sum(table.get(c, table['?'])[0] for c in word)
        if font == 'b' and language != 'zh-hans':
            advance += fontgen.kerning(word, 'b')
        # drawString2Pieces centres the glyph advances in each source crop.
        origin = (width - (advance - 1)) // 2 if centred else 0
        left, right = bounds(word, font, language, origin)
        if left < 0 or right > width:
            errors.append(f'answer {word!r} ink {left}:{right} exceeds {width}-px crop')
    return errors


def confirmation_problems(key, value, font, language):
    if key != 'm1240.u0':
        return []
    def rows(value):
        if isinstance(value, str):
            return [value]
        return [row for part in value for row in rows(part)]
    lines = rows(value)
    if len(lines) != 2:
        return ['item/card confirmation must have two physical rows: question, then Yes No']
    errors = answer_problems(lines[1], font, language, CONFIRM_LIMIT, centred=True)
    width = bounds(lines[0], font, language, script=True)[1]
    if width > 96:
        errors.append(f'confirmation question is {width} px; crop is 96 px')
    return errors


# Match modNoticeDraw crops; the renderer adds one shadow pixel outside each field.
NOTICE_FIELDS = {'HEAD1': (254, None), 'FPS': (254, (20, 30, 60)),
                 'RAM': (150, None), 'CPU': (150, None),
                 'MISSING': (120, None), 'READY': (120, None)}


def notice_problems(key, value, font, language):
    field = key.removeprefix('main.MOD_NOTICE_STR_')
    if field not in NOTICE_FIELDS:
        return []
    limit, values = NOTICE_FIELDS[field]
    errors = []
    try:
        rows = [value % number for number in values] if values else [value]
    except (TypeError, ValueError):
        return ['enhancement-popup format must accept exactly one integer']
    from tools.localize.executable.bank import encoded_len
    for row in rows:
        width = fitted_width(row, font, language)
        if width > limit:
            errors.append(f'enhancement-popup text {row!r} is {width} px; field is {limit} px')
        if values and encoded_len(row, font) + 1 > 32:
            errors.append(f'enhancement-popup text {row!r} exceeds its 32-byte buffer')
    return errors


def field_problems(key, value, font, language):
    errors = (tab_problems(key, value, font, language) + name_problems(key, value, font, language)
              + notice_problems(key, value, font, language))
    if key.startswith('main.ITEM_NAMES.'):
        width = fitted_width(value, font, language)
        if width > ITEM_LIMIT:
            errors.append(f'item name {value!r} is {width} px after fitting; shop field is {ITEM_LIMIT} px')
    elif key == 'main.STR_YES_NO_SPACED':
        errors += answer_problems(value, font, language, YES_NO_LIMIT)
    elif key in ('main.MAIN_D_801346AC', 'main.MAIN_D_801346B0'):
        width = bounds(value, font, language)[1]
        # Registration/save prompts use a 48-pixel label slot.
        if width > YES_NO_LIMIT:
            errors.append(f'save/registration answer is {width} px; field is {YES_NO_LIMIT} px')
    return errors


def audit():
    errors, counts = [], {}
    for language in CODES:
        names = json.loads((ROOT/'text'/('ours' if language == 'en' else language)/'names.json').read_text())
        for font in FONTS:
            count = 0
            for key,value in names.items():
                if key in ('main.MAIN_D_801238A0', 'main.MAIN_D_80123A18', 'main.STR_YES_NO_SPACED', 'main.MAIN_D_801346AC', 'main.MAIN_D_801346B0') or key.startswith(('main.MOVE_NAMES.', 'main.ITEM_NAMES.', 'main.MOD_NOTICE_STR_')):
                    if language == 'zh-hans':
                        from tools.localize.executable.chinese_layout import align
                        value = align(key,value)
                    count += 1
                    for why in field_problems(key,value,font,language):
                        errors.append(dict(language=language,font=font,key=key,why=why))
            confirmation = json.loads((ROOT/'text'/('ours' if language == 'en' else language)/'dialogue/maphead.json').read_text())['m1240.u0']
            for why in confirmation_problems('m1240.u0', confirmation, font, language):
                errors.append(dict(language=language,font=font,key='m1240.u0',why=why))
            counts[language+':'+font]=count+1
    return dict(errors=errors,entries=counts)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json',type=Path)
    args=parser.parse_args();result=audit()
    if args.json:
        args.json.parent.mkdir(parents=True,exist_ok=True)
        args.json.write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n')
    for e in result['errors']:print('{language}/{font} {key}: {why}'.format(**e))
    print(f"{sum(result['entries'].values())} UI fields checked; {len(result['errors'])} errors")
    return bool(result['errors'])


if __name__=='__main__':raise SystemExit(main())
