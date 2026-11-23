"""The banners of the thirteen cups after the original's (cups 23..35): STDDAT/GRADE/NEWCUPS.BIN.

    python3 -m tools.cup_banners build OUT.BIN      # the disc file
    python3 -m tools.cup_banners preview DIR        # PNGs to look at (needs Pillow; the build does not)

The original's banners are one TIM file per cup, with a copy per language. These are ours from the first pixel: a
framed plate in the cup's colour, its name in the game's own redrawn font (tools/font) and a line that says what kind of
cup it is. One file holds them all, a banner per language and cup in the order of include/dw/lang.h and of CUPS, each
SECTORS long, so the arena reads the one it shows with a single file name (STD_initializeTournament).

No Pillow, no downloads: the player's build draws them too.
"""
import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
SECTOR = 2048
SECTORS = 17                    # STD_NEW_CUP_SECTORS
W, H = 256, 128                 # the original banners' size and place in video memory
IMAGE_XY, CLUT_XY = (384, 0), (0, 486)
LANGUAGES = ['en', 'es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca', 'zh-hans']      # include/dw/lang.h

# key (the name's STR_TOURNAMENT_NAME_<key>), family, colour of the plate, English name
CUPS = [
    ('ROOKIE_CUP', 'level', (40, 150, 70), 'Rookie Cup'),
    ('CHAMPION_CUP', 'level', (40, 100, 190), 'Champion Cup'),
    ('ULTIMATE_CUP', 'level', (130, 60, 180), 'Ultimate Cup'),
    ('MEGA_CUP', 'level', (190, 40, 40), 'Mega Cup'),
    ('VACCINE_CUP', 'attribute', (30, 150, 130), 'Vaccine Cup'),
    ('DATA_CUP', 'attribute', (50, 110, 200), 'Data Cup'),
    ('VIRUS_CUP', 'attribute', (150, 40, 110), 'Virus Cup'),
    ('NATURE_SPIRITS_CUP', 'field', (60, 140, 40), 'Nature Spirits Cup'),
    ('DEEP_SAVERS_CUP', 'field', (20, 90, 170), 'Deep Savers Cup'),
    ('NIGHTMARE_SOLDIERS_CUP', 'field', (100, 50, 150), 'Nightmare Soldiers Cup'),
    ('WIND_GUARDIANS_CUP', 'field', (60, 150, 190), 'Wind Guardians Cup'),
    ('METAL_EMPIRE_CUP', 'field', (120, 120, 135), 'Metal Empire Cup'),
    ('VIRUS_BUSTERS_CUP', 'field', (190, 150, 40), 'Virus Busters Cup'),
]
STARS = {'ROOKIE_CUP': 1, 'CHAMPION_CUP': 2, 'ULTIMATE_CUP': 3, 'MEGA_CUP': 4}
FAMILY = {
    'level': dict(zip(LANGUAGES, ['LEVEL CUP', 'COPA DE NIVEL', 'COPA DE NÍVEL', 'COUPE DE NIVEAU', 'STUFEN-POKAL',
                                  'COPPA DI LIVELLO', 'レベルカップ', 'COPA DE NIVELL', '等级杯'])),
    'attribute': dict(zip(LANGUAGES, ['ATTRIBUTE CUP', 'COPA DE ATRIBUTO', 'COPA DE ATRIBUTO', "COUPE D'ATTRIBUT",
                                      'TYP-POKAL', 'COPPA DI ATTRIBUTO', 'ぞくせいカップ', "COPA D'ATRIBUT", '属性杯'])),
    'field': dict(zip(LANGUAGES, ['FIELD CUP', 'COPA DE FIELD', 'COPA DE FIELD', 'COUPE DE FIELD', 'FIELD-POKAL',
                                  'COPPA DI FIELD', 'フィールドカップ', 'COPA DE FIELD', '领域杯'])),
}


def names(language):
    """{key: the cup's name} in a language: the same text the game writes (text/<language>/names.json)."""
    data = json.load(open(os.path.join(ROOT, 'text', 'ours' if language == 'en' else language, 'names.json'), encoding='utf-8'))
    return {key: data['main.STR_TOURNAMENT_NAME_' + key] for key, _, _, _ in CUPS}


def lettering(text, language='en'):
    """The text as rows of on/off pixels in the game's fonts, cropped to the rows it uses."""
    from tools.localize.labels import glyphs, mask
    if language == 'zh-hans':
        return mask(text, 10 ** 6, 12, preserve=True)
    table = glyphs()                                    # Latin, kana and the Japanese kanji: one table
    height = len(next(iter(table.values())))
    rows = [[] for _ in range(height)]
    for char in text:
        cell = ['....'] * height if char == ' ' else table[char]
        if char != ' ':
            width = max((row.rfind('#') + 1 for row in cell), default=1)
            cell = [row[:max(1, width)] + '.' for row in cell]
        for out, row in zip(rows, cell):
            out.extend(c == '#' for c in row)
    used = [y for y, row in enumerate(rows) if any(row)]
    return rows[used[0]:used[-1] + 1]


def breaks(text):
    """The places a name may be cut in two: after a space or a hyphen, before the word for cup in Japanese and Chinese."""
    out = [(text, None)]
    for i, char in enumerate(text):
        if char == ' ':
            out.append((text[:i], text[i + 1:]))
        elif char == '-':
            out.append((text[:i + 1], text[i + 1:]))
    for word in ('カップ', '杯'):
        if text.endswith(word) and len(text) > len(word):
            out.append((text[:-len(word)], word))
    return out


def title_lines(text, room, language):
    """The name as one or two rows of lettering and the scale it is drawn at: the largest that fits, one row first."""
    for scale in (3, 2, 1):
        best = None
        for first, second in breaks(text):
            rows = [lettering(part, language) for part in (first, second) if part]
            width = max(len(row[0]) for row in rows) * scale
            if width <= room and (best is None or (len(rows), width) < best[0]):
                best = (len(rows), width), rows
        if best:
            return best[1], scale
    raise ValueError(f'{text}: does not fit the banner')


def shade(colour, factor):
    return tuple(max(0, min(255, round(c * factor))) for c in colour)


def palette(colour):
    """256 colours: 0..63 the plate from dark to light, 64..79 the gold of the name, 80 white, 81 the shadow."""
    out = [shade(colour, 0.12 + 0.88 * i / 63) for i in range(64)]
    out += [(255 - (15 - i) * 5, 236 - (15 - i) * 9, 96 - (15 - i) * 5) for i in range(16)]
    out += [(248, 248, 248), (8, 8, 16)]
    out += [(8, 8, 16)] * (256 - len(out))
    return out


def star(px, cx, cy, ink, shadow):
    rows = ['.....#.....', '.....#.....', '....###....', '....###....', '###########', '.#########.', '..#######..',
            '...#####...', '..#######..', '..###.###..', '.##.....##.']
    for pass_ink, off in ((shadow, 1), (ink, 0)):
        for y, row in enumerate(rows):
            for x, on in enumerate(row):
                if on == '#':
                    px[(cy + y + off) * W + cx + x + off] = pass_ink


def diamond(px, cx, cy, ink, shadow):
    for pass_ink, off in ((shadow, 1), (ink, 0)):
        for y in range(-4, 5):
            for x in range(-(4 - abs(y)), 5 - abs(y)):
                px[(cy + y + off) * W + cx + x + off] = pass_ink


def stamp(px, bitmap, left, top, scale, ink, shadow):
    """ink: a colour index, or a function of the bitmap row. The shadow falls one scaled pixel down and right."""
    for pass_ink, off in ((shadow, max(1, scale - 1)), (ink, 0)):
        for y, row in enumerate(bitmap):
            index = pass_ink(y) if callable(pass_ink) else pass_ink
            for x, on in enumerate(row):
                if on:
                    for dy in range(scale):
                        start = (top + y * scale + dy + off) * W + left + x * scale + off
                        px[start:start + scale] = [index] * scale


def banner(key, family, language, name):
    px = [0] * (W * H)
    for y in range(H):                                  # the plate: darker at the edges, a soft band behind the name
        for x in range(W):
            level = 10 + 26 * (1 - abs(y - 52) / 76) - 6 * abs(x - W / 2) / (W / 2)
            px[y * W + x] = max(2, min(40, int(level + ((x + y) % 2) * 0.5)))
    for inset, index in ((3, 58), (4, 63), (5, 46), (8, 30)):   # a double frame
        for x in range(inset, W - inset):
            px[inset * W + x] = px[(H - 1 - inset) * W + x] = index
        for y in range(inset, H - inset):
            px[y * W + inset] = px[y * W + W - 1 - inset] = index
    rows, scale = title_lines(name if language in ('ja', 'zh-hans') else name.upper(), W - 32, language)
    gap = 3 * scale
    heights = [len(row) * scale for row in rows]
    top = 12 + (76 - sum(heights) - gap * (len(rows) - 1)) // 2
    for row, height in zip(rows, heights):
        size = len(row)
        stamp(px, row, (W - len(row[0]) * scale) // 2, top, scale, lambda y, size=size: 79 - (y * 11 // size), 81)
        top += height + gap
    caption = lettering(FAMILY[family][language], language)
    width = len(caption[0])
    y = 99 - len(caption) // 2
    stamp(px, caption, (W - width) // 2, y, 1, 80, 81)
    for x in list(range(24, (W - width) // 2 - 22)) + list(range((W + width) // 2 + 22, W - 24)):   # a rule at each side
        px[99 * W + x] = 58
        px[100 * W + x] = 81
    marks = STARS.get(key, 0)
    for i in range(marks):
        star(px, W // 2 - marks * 8 + i * 16 + 2, 108, 76, 81)
    if not marks:
        for cx in (W // 2 - 16, W // 2, W // 2 + 16):
            diamond(px, cx, 113, 76, 81)
    for cx in ((W - width) // 2 - 12, (W + width) // 2 + 11):
        diamond(px, cx, 99, 63, 81)
    return px


def tim(px, colours):
    clut = b''.join(struct.pack('<H', (r >> 3) | (g >> 3) << 5 | (b >> 3) << 10) for r, g, b in colours)
    data = struct.pack('<II', 0x10, 9)
    data += struct.pack('<IHHHH', 12 + len(clut), *CLUT_XY, 256, 1) + clut
    data += struct.pack('<IHHHH', 12 + W * H, *IMAGE_XY, W // 2, H) + bytes(px)
    if len(data) > SECTORS * SECTOR:
        raise ValueError('a banner is larger than its room in the file')
    return data.ljust(SECTORS * SECTOR, b'\0')


def banners(languages=LANGUAGES):
    for language in languages:
        text = names(language)
        for key, family, colour, _ in CUPS:
            yield language, key, banner(key, family, language, text[key]), palette(colour)


def build(out):
    data = b''.join(tim(px, colours) for _, _, px, colours in banners())
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, 'wb') as f:
        f.write(data)
    return len(data)


def preview(folder, languages=LANGUAGES):
    from PIL import Image
    os.makedirs(folder, exist_ok=True)
    for language in languages:
        sheet = Image.new('RGB', (W * 3 + 8, (H + 4) * 5), (0, 0, 0))
        for i, (_, key, px, colours) in enumerate(banners([language])):
            image = Image.new('RGB', (W, H))
            image.putdata([colours[v] for v in px])
            sheet.paste(image, ((i % 3) * (W + 4), (i // 3) * (H + 4)))
        sheet.save(os.path.join(folder, f'cups-{language}.png'))


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'build':
        print(build(sys.argv[2]), 'bytes')
    elif len(sys.argv) == 3 and sys.argv[1] == 'preview':
        preview(sys.argv[2])
    else:
        sys.exit(__doc__)
