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
from dws.textbank import TextBank
from dws.py.lower import escape_problems, font_problems, resolve_escapes
from tools.localize.executable.bank import exe_bank, FORMAT, encoded_len, list_width, VERBATIM
from tools.fontgen import text_width

LANGUAGES = ('en', 'es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca')
FONTS = ('b', 'original')
REFERENCE = re.compile(r'\{[^{}]+\}|[○□△×]')
HEADER = re.compile(r'^\{color [67]\}.*?\{color 1\}[.!?]*$')
# These entries are arrays consumed by the trade/tournament UI, not box-0 pages.
TABLE = re.compile(r'^(?:s(?:102|168|209|213)\.sec10\.u\d+|(?:s000\.sec|m)1238\.u(?:7|12))$')
CHOICE = re.compile(r'\.m\d+\.o\d+$')


# Packed player rows are cut at these original-cell offsets in game_menu.c.
# C spaces have a 4-pixel cell; dialogue's text_width deliberately uses 8.
PLAYER_STRIPS = {
    'main.MAIN_D_80123A60': ((0, 56, 120), (52, 64, 84)),
    'main.MAIN_D_80123A7C': ((0, 96), (72, 72)),
    'main.MAIN_D_80123A98': ((0, 84), (84, 72)),
}


def player_strip_problems(key, value):
    from tools.fontgen import metrics
    if key not in PLAYER_STRIPS:
        return []
    offsets, widths = PLAYER_STRIPS[key]
    words = list(re.finditer(r'\S+', value))
    if len(words) != len(offsets):
        return ['packed player row has the wrong number of labels']
    cells = metrics('original')
    width = lambda text: sum(cells.get(c, cells['?']) for c in text)
    errors = []
    for match, offset, crop in zip(words, offsets, widths):
        pos = width(value[:match.start()])
        if pos & ~3 != offset or (pos & ~3) - offset + width(match[0]) > crop:
            errors.append(f'packed player label {match[0]!r} misses crop {offset}:{offset + crop} (starts {pos})')
    return errors


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


def packed_ui_slices(key, value):
    """The characters assigned to each original-cell piece (font.c pieceOf)."""
    if key not in PACKED_UI:
        return []
    offsets, _ = PACKED_UI[key]
    glyphs = original_c_glyphs()
    groups = [''] * len(offsets)
    pos = 0
    for char in value:
        slot = max((i for i, offset in enumerate(offsets) if offset <= pos & ~3), default=0)
        groups[slot] += char
        pos += glyphs.get(char, glyphs['?'])[0]
    return [part.strip() for part in groups]


def packed_ui_problems(key, value):
    if key not in PACKED_UI:
        return []
    offsets, widths = PACKED_UI[key]
    glyphs = original_c_glyphs()
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


def battle_mp_problems(names, font):
    from tools.fontgen import metrics
    keys = ['btl.BTL_STR_MP_CONSUMPTION_BONUS', 'btl.BTL_STR_REDUCED_BY',
            'btl.BTL_STR_MP_BONUS_PERCENT']
    if not all(k in names for k in keys):
        return []
    text = names[keys[0]] + names[keys[1]] + '20' + names[keys[2]]
    advances = metrics(font)
    return ['composed MP bonus exceeds the battle end-box 156-px crop'] if any(
        sum(advances.get(c, advances['?']) for c in re.sub(r'#C[0-9]', '', row)) > 156
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


def rendered_pages(key, value, bank):
    # The base game's source loader reflows wide explicit rows. Mod banks are
    # loaded verbatim, so do not hide a mod's overflow by running the fitter.
    value = bank.fit(key, value)
    if isinstance(value, str):
        return [[value]] if CHOICE.search(key) else BE.wrap(value, 3, BE.packed_key(key))
    return pages(value)


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
            for font in fonts:
                BE.FONT.update(extra=True, glyphs=len(BE.EXTRA_ORDER), chars=frozenset(BE.EXTRA_ORDER), name=font)
                bank = TextBank(language, 'ours' if language == 'en' else language)
                rows = []
                substitutions = {}
                for source, path, executable, english, data in pairs:
                    is_mod = 'mods' in path.parts
                    for key, value in data.items():
                        if key.startswith(('_', 'x.')):
                            continue
                        counts[language + ':' + font] += 1
                        if key in english:
                            for why in control_problems(english[key], value, executable):
                                issue(language, font, path, key, why)
                        for row in strings(value):
                            # C printf/control strings are checked by exe_bank.
                            if not executable:
                                for why in escape_problems(row):
                                    issue(language, font, path, key, why)
                                for why, _ in font_problems(row)[0]:
                                    issue(language, font, path, key, why)
                        if executable:
                            if language != 'en':
                                for why in packed_ui_problems(key, value):
                                    issue(language, font, path, key, why)
                                for why in player_strip_problems(key, value):
                                    issue(language, font, path, key, why)
                            # Fixed cell strips are consumed piece by piece. The
                            # QOL hint uses fitStringMode; TECH_VIEW_LABELS[9]
                            # (801239F4) is unused. Other literal C strings must
                            # at least fit the global text area; narrower crops
                            # are checked below and in the emulator matrix.
                            if key not in VERBATIM and key not in ('main.MAIN_D_801239F4', 'main.QOL_STR_SKIP_EVOLUTION') and not FORMAT.search(value) and text_width(value, font) > 244:
                                issue(language, font, path, key, 'literal UI text exceeds the 244-px drawing area')
                            if key == 'btl.BTL_STR_MP_CONSUMPTION_BONUS':
                                for why in battle_mp_problems(data, font):
                                    issue(language, font, path, key, why)
                            if key.startswith('btl.BTL_STR_') and ('#R' in value or '#W' in value):
                                # End-box fragments use explicit row controls; C spaces
                                # have the original 4-pixel cell, not dialogue's 8.
                                from tools.fontgen import metrics
                                advances = metrics(font)
                                for line in re.split(r'#[RW]', value):
                                    line = re.sub(r'#C[0-9]', '', line)
                                    if sum(advances.get(c, advances['?']) for c in line) > 156:
                                        issue(language, font, path, key, 'battle end-box fragment exceeds its 156-px crop')
                            if key == 'main.MAIN_D_80122D68' and text_width(value, font) > 240:
                                issue(language, font, path, key, 'bag-full pickup message exceeds its 240-px crop')
                            if key.startswith('main.ITEM_DESCS.') and text_width(value, font) > 244:
                                issue(language, font, path, key, 'item effect description exceeds 244 px')
                            if key.startswith('main.MAIN_D_80131') and text_width(value, font) > 244:
                                issue(language, font, path, key, 'save/title message exceeds 244 px')
                            if key in ('main.MAIN_D_8013103C', 'main.MAIN_D_8013104C', 'main.MAIN_D_8013105C') and text_width(value, font) > 144:
                                issue(language, font, path, key, 'slot confirmation title exceeds its 144-px crop')
                            if key in ('main.MAIN_D_80131008', 'main.MAIN_D_80131014',
                                       'main.MAIN_D_80131024', 'main.MAIN_D_80131030') and list_width(value, font) > 164:
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
                            rendered = rendered_pages(key, value, bank)
                        over = bank.single_page_overflow(key, len(rendered))
                        if over:
                            issue(language, font, path, key, over)
                        for page in rendered:
                            max_rows = boxes.get(key, (240, 4))[1]
                            if len(page) > max_rows and not TABLE.match(key):
                                issue(language, font, path, key, f'{len(page)} rows in a {max_rows}-row page')
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
                    built, kept = exe_bank('ours' if language == 'en' else language, exe_font=font)
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
    args = parser.parse_args()
    result = audit()
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=1) + '\n')
    for note in result['notes']:
        print('{language} {file}: {why}'.format(**note))
    for error in result['errors']:
        print('{language}/{font} {file}:{key}: {why}'.format(**error))
    print(f"{sum(result['entries'].values())} entries checked; {len(result['errors'])} errors")
    return bool(result['errors'])


if __name__ == '__main__':
    raise SystemExit(main())
