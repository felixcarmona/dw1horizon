#!/usr/bin/env python3
"""Read-only text audit for every playable language and both runtime fonts.

Run ``python3 -m tools.localize.check --json build/text-audit.json``.
Dialogue uses TextBank.fit/wrap, including the unpacked MAPHEAD windows and
indexed page counts. Runtime references are compared with our English; repeated
speaker headers are allowed only when the English has a standalone header.
Executable records use exe_bank's byte/condensed-list checks. Pixel bounds for
other C UI strings need a renderer-specific limit; they are not inferred from
character counts. The report retains the widest dialogue rows for emulation.
"""
import argparse
import collections
import functools
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from dws import backend as BE
from dws.text.profiles import NAMED_PAGE_ROWS, header_row, maphead_page_too_tall, merged_name_rows, named_keys, narrator_keys
from dws.textbank import TextBank
from dws.text.jaspace import kinsoku_problems, problems as ja_space_problems
from dws.py.lower import escape_problems, font_problems, literal_escapes, resolve_escapes
from tools.localize.executable.bank import exe_bank, FORMAT, encoded_len, list_width, VERBATIM
from tools.fontgen import text_width
from tools.localize.places import problems as place_problems

from tools.languages import CODES as LANGUAGES
FONTS = ('b', 'original')
REFERENCE = re.compile(r'\{[^{}]+\}|[○□△×]')
HEADER = re.compile(r'^\{color [67]\}.*?\{color 1\}[.!?]*$')
# These entries are arrays consumed by the trade/tournament UI, not box-0 pages.
TABLE = re.compile(r'^(?:s(?:102|168|209|213)\.sec10\.u\d+|(?:s000\.sec|m)1238\.u(?:7|12))$')
CHOICE = re.compile(r'\.m\d+\.o\d+$')


def curling_menu_problems(value, font, language):
    """KAR_tickYesNoPrompt copies 82 px at 0 and 92 px at 83.

    DRAW_STRING_PIECES assigns glyphs using their original cells rounded down
    to four pixels, so the second label must start at cell 84.
    """
    cells = c_cells(language)
    pieces = ['', '']
    second = None
    for word in re.finditer(r'\S+', value):
        start = sum(cells.get(c, cells['?']) for c in value[:word.start()])
        end = start + sum(cells.get(c, cells['?']) for c in word[0])
        if start < 84 < end:
            return ['curling option crosses the row boundary at cell 84']
        slot = int(start >= 84)
        if slot and second is None:
            second = start
        pieces[slot] += (' ' if pieces[slot] else '') + word[0]
    if not all(pieces) or second != 84:
        return ['curling needs two option rows, with the second label at cell 84']
    def width(label):
        if language == 'zh-hans':
            return ui_width(label, font, language)
        if font == 'b':
            # The first glyph is centred inside its original cell (at most
            # six pixels of inset); these rows never use item-list condensation.
            return list_width(label, font) + 6
        glyphs = c_glyphs(language)
        pen, right = 0, 0
        for char in label:
            advance, rows = glyphs.get(char, glyphs['?'])
            if char != ' ':
                right = max(right, (pen & ~3) + max(r.rfind('#') for r in rows) + 1)
            pen += advance
        from tools.fontgen import fit_layout
        # CLASSIC uses these same bitmaps with their natural proportional
        # advances. Check its uncondensed width as well as ORIGINAL's cells.
        return max(right, fit_layout(label, 0, metrics_only=True)[1] + 6)
    return [f'curling option {label!r} exceeds its {limit}-px row'
            for label, limit in zip(pieces, (82, 91)) if width(label) > limit]


# Packed player rows are cut at these original-cell offsets in game_menu.c.
# C spaces have a 4-pixel cell; dialogue's text_width deliberately uses 8.
PLAYER_STRIPS = {
    'main.MAIN_D_80123A60': ((0, 56, 120), (52, 64, 84)),
    'main.MAIN_D_80123A7C': ((0, 96), (72, 72)),
    'main.MAIN_D_80123A98': ((0, 84), (84, 72)),
}


def c_cells(language):
    from tools.fontgen import metrics
    if language == 'zh-hans':
        from tools.localize.executable.chinese_layout import cell_width
        from tools.chinese import font_glyphs
        return {c: cell_width(c) for c in font_glyphs()} | {c: 12 for c in '○□△×'}
    return metrics('original')


@functools.lru_cache(None)
def c_glyphs(language):
    if language != 'zh-hans':
        return original_c_glyphs()
    from tools.chinese import font_glyphs
    cells = c_cells(language)
    glyphs = {c: (cells[c], [''.join('.' if bits & (1 << (15-i)) else '#'
                                       for i in range(12)) for bits in data[1:]])
              for c, data in font_glyphs().items()}
    return glyphs | {c: original_c_glyphs()[c] for c in '○□△×'}


def player_strip_problems(key, value, language="en"):
    if key not in PLAYER_STRIPS:
        return []
    offsets, widths = PLAYER_STRIPS[key]
    words = list(re.finditer(r'\S+', value))
    if len(words) != len(offsets):
        return ['packed player row has the wrong number of labels']
    cells = c_cells(language)
    width = lambda text: sum(cells.get(c, cells['?']) for c in text)
    errors = []
    for match, offset, crop in zip(words, offsets, widths):
        pos = width(value[:match.start()])
        if pos & ~3 != offset or (pos & ~3) - offset + width(match[0]) > crop:
            errors.append(f'packed player label {match[0]!r} misses crop {offset}:{offset + crop} (starts {pos})')
    return errors


# The name keyboard's label row (script_menu.c layoutNamingLabels): the title and Back's word, each at most as wide in
# original cells as the column left of the keys; Back's word is followed by OK.
NAMING_LABELS = {'shop.MAIN_D_801345F8': False, 'shop.MAIN_D_80134600': True}
NAMING_LABEL_CELLS = 64


def naming_label_problems(key, value, language="en"):
    if key not in NAMING_LABELS:
        return []
    if NAMING_LABELS[key]:
        if not value.endswith('OK'):
            return ['the name keyboard\'s Back word must be followed by OK (one string: "<Back>OK")']
        value = value[:-2]
    cells = c_cells(language)
    width = sum(cells.get(c, cells['?']) for c in value)
    if width > NAMING_LABEL_CELLS:
        return [f'name keyboard label {value!r} is {width} original cells, wider than its column ({NAMING_LABEL_CELLS})']
    return []


# Fixed original-cell crops from game_menu.c; C spaces advance four pixels.
PACKED_UI = {'main.MAIN_D_801238A0': [[0, 60], [60, 64]],
 'main.MAIN_D_801238B0': [[24, 72, 120, 156, 180, 204], [36, 48, 36, 24, 24, 48]],
 'main.MAIN_D_801238D8': [[0, 48, 96, 144, 192], [48, 48, 48, 48, 52]],
 'main.MAIN_D_80123900': [[0, 72, 108], [72, 36, 64]],
 'main.MAIN_D_80123914': [[0, 48], [40, 24]],
 'main.MAIN_D_80123938': [[0, 32, 76, 124], [28, 44, 48, 40]],
 'main.MAIN_D_80123970': [[0, 113], [113, 110]],
 'main.MAIN_D_80123A3C': [[0, 108, 120, 132, 180], [60, 12, 12, 44, 64]],
 'main.MAIN_D_80123AB0': [[0, 72, 84, 132, 144], [52, 12, 48, 12, 64]],
 'main.MAIN_D_80123AD0': [[0, 12, 72, 84], [12, 60, 12, 64]],
 'main.MAIN_D_80123AE4': [[0, 40, 80], [40, 40, 58]],
 'main.MAIN_D_80123B10': [[0, 52], [52, 60]]}


@functools.lru_cache(None)
def original_c_glyphs():
    from tools.fontgen import committed_glyphs, font_tables, by_char
    codes, base = committed_glyphs()
    return by_char(codes, *font_tables('original', (codes, base)))


def packed_ui_crops(key, language):
    if language == 'zh-hans' and key == 'main.MAIN_D_80123AE4':
        # CHART_TREE_ROW_PIECES and CHART_LEVEL_CROPS, game_menu.c.
        return (0, 40, 88, 204), (40, 48, 60, 40)
    return PACKED_UI[key]


def packed_ui_slices(key, value, language="en"):
    """The characters assigned to each original-cell piece (font.c pieceOf)."""
    if key not in PACKED_UI:
        return []
    offsets, _ = packed_ui_crops(key, language)
    glyphs = c_glyphs(language)
    groups = [''] * len(offsets)
    pos = 0
    for char in value:
        slot = max((i for i, offset in enumerate(offsets) if offset <= pos & ~3), default=0)
        groups[slot] += char
        pos += glyphs.get(char, glyphs['?'])[0]
    return [part.strip() for part in groups]


def packed_ui_problems(key, value, language="en"):
    if key not in PACKED_UI:
        return []
    offsets, widths = packed_ui_crops(key, language)
    glyphs = c_glyphs(language)
    pos = 0
    errors = []
    for char in value:
        advance, rows = glyphs.get(char, glyphs['?'])
        if char != ' ':
            slot = max((i for i, offset in enumerate(offsets) if offset <= pos & ~3), default=0)
            # Original glyphs are uploaded at x / 4. Their advance may exceed
            # their last ink column (Gift is 30 cells but 26 ink pixels).
            left = (pos & ~3) + min((r.index('#') for r in rows if '#' in r), default=0)
            right = (pos & ~3) + max(r.rfind('#') for r in rows) + 1
            if left < offsets[slot] or right > offsets[slot] + widths[slot]:
                errors.append(f'packed UI glyph {char!r} at {pos} misses crop {offsets[slot]}:{offsets[slot] + widths[slot]}')
        pos += advance
    return errors


def ui_width(value, font, language):
    if language == 'zh-hans':
        from tools.chinese import row_metrics, font_glyphs
        return row_metrics(value, font_glyphs())[0]
    return text_width(value, font)


def battle_width(value, font, language):
    if language == 'zh-hans':
        return ui_width(value, font, language)
    from tools.fontgen import metrics
    advances = metrics(font)
    return sum(advances.get(c, advances['?']) for c in value)


def battle_mp_problems(names, font, language="en"):
    keys = ['btl.BTL_STR_MP_CONSUMPTION_BONUS', 'btl.BTL_STR_REDUCED_BY',
            'btl.BTL_STR_MP_BONUS_PERCENT']
    if not all(k in names for k in keys):
        return []
    text = names[keys[0]] + names[keys[1]] + '20' + names[keys[2]]
    return ['composed MP bonus exceeds the battle end-box 156-px crop'] if any(
        battle_width(re.sub(r'#C[0-9]', '', row), font, language) > 156
        for row in re.split(r'#[RW]', text)) else []


def strings(value):
    if isinstance(value, str):
        yield value
    else:
        for part in value:
            yield from strings(part)


def pages(value):
    return [[value]] if isinstance(value, str) else [value] if all(isinstance(x, str) for x in value) else value


def runtime_tokens(value, source, include_colors=False):
    """Do not confuse an inline addressee with the name of the speaker."""
    source_pages = pages(source)
    header = source_pages[0][0] if source_pages and source_pages[0] else ''
    speaker = not isinstance(source, str) and HEADER.fullmatch(header)
    rows, speaker_tokens = [], None
    for page in pages(value):
        if speaker and page and HEADER.fullmatch(page[0]):
            current = [t for t in REFERENCE.findall(page[0]) if include_colors or not t.startswith('{color ')]
            if speaker_tokens is None:
                speaker_tokens = current
            elif current != speaker_tokens:
                rows.append(page[0])
            rows.extend(page[1:])
        else:
            rows.extend(page)
    text = resolve_escapes(' '.join(rows))
    return (speaker_tokens or []) + [t for t in REFERENCE.findall(text) if include_colors or not t.startswith('{color ')]



def control_problems(source, value, executable=False):
    if executable:
        return [] if FORMAT.findall(source) == FORMAT.findall(value) else ['executable format codes changed']
    expected, actual = runtime_tokens(source, source), runtime_tokens(value, source)
    problems = [] if expected == actual else [f'runtime references changed: {expected!r} -> {actual!r}']
    flat = lambda v: v if isinstance(v, str) else ' '.join(flat(x) for x in v)
    if literal_escapes(flat(source)) != literal_escapes(flat(value)):     # {item 254} hides which item: compare the names
        problems.append(f'named item or move changed: {literal_escapes(flat(source))!r} -> {literal_escapes(flat(value))!r}')
    expected_colors = [t for t in runtime_tokens(source, source, True) if t.startswith('{color ')]
    actual_colors = [t for t in runtime_tokens(value, source, True) if t.startswith('{color ')]
    if expected_colors != actual_colors:
        problems.append(f'colour controls changed: {expected_colors!r} -> {actual_colors!r}')
    return problems


def bank_pairs(language, root=ROOT):
    source_dir = root / 'text/ours'
    locale = source_dir if language == 'en' else root / 'text' / language
    for source in sorted((source_dir / 'dialogue').glob('*.json')):
        yield source, locale / 'dialogue' / source.name, False
    yield source_dir / 'names.json', locale / 'names.json', True
    yield root / 'text/en.json', root / 'text' / (language + '.json'), False
    for source in sorted((root / 'story/mods').glob('*/text/en.json')):
        yield source, source.with_name(language + '.json'), False


def custom_boxes(root=ROOT):
    """Explicit taller windows: fishing instructions and Shell News, from story source."""
    result = {}
    pattern = re.compile(r'set_textbox_size\([^,]+,\s*(\d+),\s*(\d+)\);\s*'
                         r'show_textbox\(text\("([^"]+)"\)\)')
    for path in (root / 'story/base').rglob('*.dws'):
        for cols, rows, key in pattern.findall(path.read_text()):
            result[key] = (int(cols) * 12 + 8, int(rows))
    return result


def name_rows(key, value, bank):
    """The speaker's name rows a value of a nameless box writes as a page's first row (`header_row`), as its font shows
    them; a coloured row too wide for a row is text, not a name. (In a named speaker's box such a row is text: the
    caller leaves those keys out.)"""
    if isinstance(value, str):
        return []
    fitted = (bank.fit(key, [[p[0]]]) for p in pages(value) if p and header_row(p[0]))
    return [f[0][0] for f in fitted if not isinstance(f, str)]


def rendered_pages(key, value, bank, row_limit=3):
    # The base game's source loader reflows wide explicit rows. Mod banks are
    # loaded verbatim, so do not hide a mod's overflow by running the fitter.
    value = bank.fit(key, value)
    if isinstance(value, str):
        return [[value]] if CHOICE.search(key) else BE.wrap(value, row_limit, BE.packed_key(key))
    return pages(value)


def dialogue_layout(key, value, bank, boxes, named, is_mod=False, where='', narrated=()):
    """The page rows actually emitted, with the active box's physical capacity."""
    limit = boxes.get(key, (240, 4))[1]
    if is_mod:
        limit = 4 if 'narrator' in where else 3
        rendered = BE.wrap(value, limit) if isinstance(value, str) else pages(value)
    else:
        if key in named and key not in boxes:
            limit = NAMED_PAGE_ROWS
        # show_textbox of string keys uses three rows in the compiler. Explicit
        # narrator/custom pages can use the full capacity of their active box.
        rendered = rendered_pages(key, value, bank, 4 if key in narrated else 3)
    physical = [[part for row in page for part in re.split(r'\{br\}', row, flags=re.I)]
                for page in rendered]
    return physical, limit


def page_problems(key, rendered, limit):
    if TABLE.match(key) or CHOICE.search(key):
        return []
    problems = []
    for index, page in enumerate(rendered, 1):
        capacity = min(limit, NAMED_PAGE_ROWS) if maphead_page_too_tall(key, page) else limit
        if len(page) > capacity:
            problems.append(f'page {index}: {len(page)} rows in a {capacity}-row box')
    return problems


def audit_pages(languages=LANGUAGES, fonts=FONTS, root=ROOT):
    """Audit every dialogue bank's emitted pages, separately from UI/name widths.

    Include English mod fallbacks, both font-specific script banks, physical
    row escapes and MAPHEAD's indexed entries. Counts make coverage reviewable.
    """
    errors, counts = [], {}
    boxes, named, narrated = custom_boxes(root), named_keys(root), narrator_keys(root)
    previous = dict(BE.FONT)
    try:
        for language in languages:
            for font in fonts:
                BE.FONT.update(extra=True, glyphs=len(BE.EXTRA_ORDER), chars=frozenset(BE.EXTRA_ORDER), name=font)
                bank = TextBank(language, 'ours' if language == 'en' else language)
                checked = collections.Counter()
                for source, path, executable in bank_pairs(language, root):
                    if executable or not source.exists():
                        continue
                    if not path.exists() and 'mods' in path.parts:
                        path = source
                    if not path.exists():
                        errors.append(dict(language=language, font=font, file=str(path.relative_to(root)),
                                           key='(bank)', why='translation bank missing'))
                        continue
                    english, data = json.loads(source.read_text()), json.loads(path.read_text())
                    for key, value in data.items():
                        if key.startswith(('_', 'x.')) or TABLE.match(key) or CHOICE.search(key):
                            continue
                        rendered, limit = dialogue_layout(key, value, bank, boxes, named,
                                                         'mods' in path.parts, english.get('_where', {}).get(key, ''), narrated)
                        checked['entries'] += 1
                        checked['pages'] += len(rendered)
                        checked['rows'] += sum(map(len, rendered))
                        problems = page_problems(key, rendered, limit)
                        over = bank.single_page_overflow(key, len(rendered))
                        if over:
                            problems.append(over)
                        for why in problems:
                            errors.append(dict(language=language, font=font, file=str(path.relative_to(root)),
                                               key=key, why=why))
                counts[language + ':' + font] = dict(checked)
    finally:
        BE.FONT.clear()
        BE.FONT.update(previous)
    return dict(errors=errors, coverage=counts)


def expand_references(row, names, species, cards, cache=None):
    """Conservative witnesses for runtime substitution; numbers are pstat IDs.

    In particular {item 110} reads pstat 110, not item 110. p103 is the
    u8 partner-type variable; p249 is the card species. Other item/tech
    variables use their complete name table, so a clean bound covers every
    reachable value without guessing which reward a branch selected.
    """
    cache = {} if cache is None else cache
    def longest(values):
        return max(values, key=BE.text_px, default='')
    def value_for(body):
        words = body[1:-1].split()
        kind = words[0]
        if kind in ('player', 'partner'):
            return 'WWWWWWWW'  # eight allowed player/partner name characters
        if kind == 'digimon' and len(words) == 2:
            allowed = cards if words[1] == '249' else set(range(256))
            return longest(name for ident, name in species.items() if ident in allowed)
        if kind in ('item', 'move'):
            prefix = 'main.' + ('ITEM_NAMES.' if kind == 'item' else 'MOVE_NAMES.')
            named = literal_escapes(body)           # {item Item.SweetNut}: that one item's name, not the longest
            if named and prefix + str(named[0][1]) in names:
                return names[prefix + str(named[0][1])]
            return longest(value for key, value in names.items() if key.startswith(prefix))
        digits = {'money': 6, 'merit': 4, 'pstat': 3, 'shopvar': 5,
                  'cupswon': 3, 'wins': 3, 'losses': 3}
        return '9' * digits[kind] if kind in digits else body
    def replace(match):
        body = match[0]
        if body not in cache:
            cache[body] = value_for(body)
        return cache[body]
    return re.sub(r'\{(?!color )[^{}]+\}', replace, row)


def audit(languages=LANGUAGES, fonts=FONTS, root=ROOT):
    errors, notes, widest, counts = [], [], {}, collections.Counter()
    boxes = custom_boxes(root)
    named = named_keys(root)
    narrated = narrator_keys(root)
    species = {int(p.name.split('-')[0]): json.loads(p.read_text())['name']
               for p in (root / 'content/species').glob('*.json')}
    card_file = root / 'content/tables/cards.json'
    cards = {row['species'] for row in json.loads(card_file.read_text())['cards']} if card_file.exists() else set()
    previous = dict(BE.FONT)
    def issue(lang, font, path, key, why):
        errors.append(dict(language=lang, font=font, file=str(path.relative_to(root)), key=key, why=why))
    try:
        for language in languages:
            pairs = []
            for source, path, executable in bank_pairs(language, root):
                if not source.exists():
                    continue
                if not path.exists():
                    if 'mods' in path.parts and not executable:
                        # The compiler deliberately falls back to English for a
                        # mod without this bank. Audit that playable text too.
                        notes.append(dict(language=language, file=str(path.relative_to(root)),
                                          why='translation bank absent; English fallback audited'))
                        path = source
                    else:
                        issue(language, 'both', path, '(bank)', 'translation bank missing')
                        continue
                english, data = json.loads(source.read_text()), json.loads(path.read_text())
                for key in english.keys() - data.keys():
                    if not key.startswith(('_', 'x.')):
                        issue(language, 'both', path, key, 'translation key missing')
                pairs.append((source, path, executable, english, data))
            names = next((data for _, _, exe, _, data in pairs if exe), {})
            for source, path, _, english, data in pairs:
                if language != 'en' and path == source:
                    # English-only developer examples retain their vocabulary;
                    # the existing fallback note reports their missing bank.
                    continue
                for key, value in data.items():
                    if not key.startswith(('_', 'x.')):
                        for why in place_problems(language, key, value, english.get(key), root):
                            issue(language, 'both', path, key, why)
            for font in fonts:
                rows = []
                substitutions = {}
                built, kept = (exe_bank('ours' if language == 'en' else language, exe_font=font)
                               if root == ROOT else ({'text': {}}, []))
                BE.FONT.clear()
                BE.FONT.update(previous)
                BE.FONT.update(extra=True, glyphs=len(BE.EXTRA_ORDER), chars=frozenset(BE.EXTRA_ORDER), name=font, chinese=False)
                bank = TextBank(language, 'ours' if language == 'en' else language)
                for source, path, executable, english, data in pairs:
                    is_mod = 'mods' in path.parts
                    for key, value in data.items():
                        if key.startswith(('_', 'x.')):
                            continue
                        counts[language + ':' + font] += 1
                        if executable and language == 'zh-hans':
                            value = built['text'].get(key, value).translate(str.maketrans('×△', '△×'))
                        if key in english:
                            for why in control_problems(english[key], value, executable):
                                issue(language, font, path, key, why)
                        if is_mod and key == 'city.join':
                            # text(key, species) substitutes before wrapping, never a runtime escape.
                            from tools.dws.recruitment import species_name, roster
                            if not isinstance(value, str) or value.count('{species}') != 1:
                                issue(language, font, path, key, 'recruitment template needs exactly one {species}')
                                continue
                            witness = max((species_name(sp, language) for sp in roster()), key=BE.text_px)
                            value = value.replace('{species}', witness)
                        if language == 'ja' and not executable:
                            for why in ja_space_problems(key, value):
                                issue(language, font, path, key, why)
                        for row in strings(value):
                            # C printf/control strings are checked by exe_bank.
                            if not executable:
                                for why in escape_problems(row):
                                    issue(language, font, path, key, why)
                                for why, _ in font_problems(row)[0]:
                                    issue(language, font, path, key, why)
                        if executable:
                            if key == 'kar.KAR_D_8005ABB8':
                                for why in curling_menu_problems(value, font, language):
                                    issue(language, font, path, key, why)
                            if language != 'en':
                                for why in packed_ui_problems(key, value, language):
                                    issue(language, font, path, key, why)
                                for why in player_strip_problems(key, value, language):
                                    issue(language, font, path, key, why)
                                for why in naming_label_problems(key, value, language):
                                    issue(language, font, path, key, why)
                            # Fixed cell strips are consumed piece by piece. The
                            # QOL hint uses fitStringMode; TECH_VIEW_LABELS[9]
                            # (801239F4) is unused. Other literal C strings must
                            # at least fit the global text area; narrower crops
                            # are checked below and in the emulator matrix.
                            if key not in VERBATIM and key not in ('main.MAIN_D_801239F4', 'main.QOL_STR_SKIP_EVOLUTION') and not FORMAT.search(value) and (list_width(value, font) if key in ('main.MOD_NOTICE_STR_HEAD1', 'main.MOD_NOTICE_STR_HEAD2') and language != 'zh-hans' else ui_width(value, font, language)) > 244:
                                issue(language, font, path, key, 'literal UI text exceeds the 244-px drawing area')
                            if key == 'btl.BTL_STR_MP_CONSUMPTION_BONUS':
                                for why in battle_mp_problems(data, font, language):
                                    issue(language, font, path, key, why)
                            if key.startswith('btl.BTL_STR_') and ('#R' in value or '#W' in value):
                                # End-box fragments use explicit row controls; C spaces
                                # have the original 4-pixel cell, not dialogue's 8.
                                for line in re.split(r'#[RW]', value):
                                    line = re.sub(r'#C[0-9]', '', line)
                                    if battle_width(line, font, language) > 156:
                                        issue(language, font, path, key, 'battle end-box fragment exceeds its 156-px crop')
                            if key == 'main.MAIN_D_80122D68' and ui_width(value, font, language) > 240:
                                issue(language, font, path, key, 'bag-full pickup message exceeds its 240-px crop')
                            if key.startswith('main.ITEM_DESCS.') and ui_width(value, font, language) > 244:
                                issue(language, font, path, key, 'item effect description exceeds 244 px')
                            if key.startswith('main.MAIN_D_80131') and ui_width(value, font, language) > 244:
                                issue(language, font, path, key, 'save/title message exceeds 244 px')
                            if key in ('main.MAIN_D_8013103C', 'main.MAIN_D_8013104C', 'main.MAIN_D_8013105C') and ui_width(value, font, language) > 144:
                                issue(language, font, path, key, 'slot confirmation title exceeds its 144-px crop')
                            if key in ('main.MAIN_D_80131008', 'main.MAIN_D_80131014',
                                       'main.MAIN_D_80131024', 'main.MAIN_D_80131030') and (ui_width(value, font, language) if language == 'zh-hans' else list_width(value, font)) > 164:
                                issue(language, font, path, key, 'title menu exceeds its 164-px text crop')
                            continue
                        if is_mod:
                            where = str(english.get('_where', {}).get(key, ''))
                            if 'option ' in where:
                                rendered = pages(value)
                            else:
                                line_count = 4 if 'narrator' in where else 3
                                rendered = BE.wrap(value, line_count) if isinstance(value, str) else pages(value)
                        else:
                            rendered = rendered_pages(key, value, bank, 4 if key in narrated else 3)
                            for row in merged_name_rows([] if key in named else name_rows(key, value, bank), rendered):
                                issue(language, font, path, key, f'a speaker\'s name row is not its own first row: {row}')
                            if language == 'ja':
                                for why in kinsoku_problems(key, rendered):
                                    issue(language, font, path, key, why)
                        over = bank.single_page_overflow(key, len(rendered))
                        if over:
                            issue(language, font, path, key, over)
                        physical, limit = dialogue_layout(key, value, bank, boxes, named, is_mod,
                                                         str(english.get('_where', {}).get(key, '')), narrated)
                        for why in page_problems(key, physical, limit):
                            issue(language, font, path, key, why)
                        for page in rendered:
                            max_rows = boxes.get(key, (240, 4))[1]
                            for i, row in enumerate(page):
                                packed = BE.packed_key(key)
                                pixels = BE.text_px(row)
                                box_width = min(240, boxes.get(key, (240, 4))[0])
                                if pixels > box_width:
                                    issue(language, font, path, key, f'row exceeds its {box_width}-px authored box: {row}')
                                size = BE.text_bytes(row) if font == 'b' and packed else 2 * BE.text_units(row)
                                rows.append(dict(file=str(path.relative_to(root)), key=key, text=row, pixels=pixels, bytes=size))
                                expanded = expand_references(row, names, species, cards, substitutions)
                                if expanded != row and not BE.fits(expanded, packed=packed):
                                    issue(language, font, path, key,
                                          f'runtime name bound overflows: {BE.row_size(expanded, packed)}: {expanded}')
                                if not BE.fits(row, i == max_rows - 1 and max_rows == 4 and not TABLE.match(key), packed):
                                    issue(language, font, path, key, f'row overflows: {BE.row_size(row, packed)}: {row}')
                widest[language + ':' + font] = sorted(rows, key=lambda x: (x['pixels'], x['bytes']), reverse=True)[:20]
                # exe_bank uses repository paths and verifies embedded byte sizes,
                # format codes, glyph support and condensed item names.
                if root == ROOT:
                    for key, value in built['text'].items():
                        if key.startswith('main.ITEM_DESCS.') and encoded_len(value, built['font']) > 62:
                            issue(language, font, root / 'text' / ('ours' if language == 'en' else language) / 'names.json', key, 'item description exceeds the 64-byte textbox row including terminators')
                    for key, why in kept:
                        if not why.startswith('species names come from'):
                            issue(language, font, root / 'text' / ('ours' if language == 'en' else language) / 'names.json', key, why)
    finally:
        BE.FONT.clear()
        BE.FONT.update(previous)
    return dict(errors=errors, notes=notes, entries=dict(counts), widest=widest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', type=pathlib.Path)
    parser.add_argument('--pages-only', action='store_true', help='all dialogue page heights and indexed-page counts')
    args = parser.parse_args()
    result = audit_pages() if args.pages_only else audit()
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=1) + '\n')
    for note in result.get('notes', []):
        print('{language} {file}: {why}'.format(**note))
    for error in result['errors']:
        print('{language}/{font} {file}:{key}: {why}'.format(**error))
    if args.pages_only:
        for pair, count in result['coverage'].items():
            print(f"{pair}: {count['entries']} dialogue entries, {count['pages']} pages, {count['rows']} rows")
    else:
        print(f"{sum(result['entries'].values())} entries checked; {len(result['errors'])} errors")
    print(f"{len(result['errors'])} errors")
    return bool(result['errors'])


if __name__ == '__main__':
    raise SystemExit(main())
