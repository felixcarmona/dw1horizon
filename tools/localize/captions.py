"""Translate screen captions with the executable text banks and font encoding.

Custom captions live in SCRN.DAT's existing 36-byte field, paged by language.
Shared native area names reuse their normal map-name keys.
"""
import csv
import functools
import json
from pathlib import Path
import re

from tools.languages import CODES

ROOT = Path(__file__).resolve().parents[2]
PREFIX = 'screen.caption.'
# Reviewed proper names and cognates whose translations match English.
UNCHANGED_NATIVE = {
    'es': {'Overdell'}, 'pt-br': {'Overdell'}, 'it': {'Overdell'},
    'fr': {'Overdell', 'Restaurant'}, 'de': {'Overdell', 'Restaurant'},
    'ca': {'Overdell', 'Restaurant'},
}


def names(language, root=ROOT):
    return json.loads((root / 'text' / ('ours' if language == 'en' else language) / 'names.json').read_text())


@functools.lru_cache(maxsize=256)
def caption_key(caption, root=ROOT):
    native = {v: k for k, v in names('en', root).items() if k.startswith('main.STR_MAP_NAME_')}
    return native.get(caption, PREFIX + re.sub(r'[^a-z0-9]+', '_', caption.lower()).strip('_'))


@functools.lru_cache(maxsize=len(CODES))
def font_codes(language):
    # Match gen_text.py: ASCII stays single-byte; extra glyphs use their
    # registered two-byte codes. Never write Latin-1 accents into drawString.
    from tools import fontgen
    font = {c: code for c, (code, _) in fontgen.extra_map().items()}
    if language == 'zh-hans':
        from tools.chinese import encoding, repertoire
        font = encoding(repertoire())
    return font


def encode(caption, language, font_glyphs=None):
    font = font_codes(language)
    result = bytearray()
    for char in caption:
        if char in font:
            if font_glyphs is not None and language != 'zh-hans':
                from tools.fontgen import code_to_index
                if code_to_index(font[char]) >= font_glyphs:
                    raise ValueError(f'{language}: caption glyph {char!r} is missing from the executable font')
            result.extend(font[char].to_bytes(2, 'big'))
        elif 32 <= ord(char) < 127:
            result.append(ord(char))
        else:
            raise ValueError(f'{language}: caption glyph {char!r} is missing from the font')
    if not result or len(result) >= 36:
        raise ValueError(f'{language}: caption {caption!r} takes {len(result)} bytes; limit is 35')
    return bytes(result)


def localize(records, language, root=ROOT, font_glyphs=None):
    bank = names(language, root)
    output = {}
    for ident, record in records.items():
        row = dict(record)
        caption = row.get('caption', 0)
        if isinstance(caption, str):
            key = caption_key(caption, root)
            value = bank.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'{language}: screen {ident} lacks caption translation {key}')
            if language != 'en' and key.startswith(PREFIX) and value.strip() == caption.strip():
                raise ValueError(f'{language}: screen {ident} caption {key} is still English')
            row['_caption_bytes'] = list(encode(value, language, font_glyphs))
        output[ident] = row
    return output


def native_inventory(root=ROOT):
    """The 70 native slots share 68 strings (Freezeland and Basement repeat)."""
    normalize = lambda text: re.sub(r'[^a-z0-9]', '', text.casefold())
    english = {k: v for k, v in names('en', root).items() if k.startswith('main.STR_MAP_NAME_')}
    by_name = {normalize(value): key for key, value in english.items()}
    with (root / 'docs/data/map_names.csv').open() as source:
        rows = list(csv.DictReader(source))
    if {int(row['id']) for row in rows} != set(range(70)):
        raise ValueError('native caption inventory must cover slots 0..69')
    missing = [row['name'] for row in rows if normalize(row['name']) not in by_name]
    if missing:
        raise ValueError(f'native captions lack English text keys: {missing}')
    keys = [by_name[normalize(row['name'])] for row in rows]
    if set(keys) != english.keys():
        raise ValueError('native caption inventory differs from the executable name bank')
    return keys


def audit(root=ROOT):
    from tools import screens
    folders = sorted((root / 'story/mods').glob('*/screens'))
    records = screens.load(folders)
    native_keys = set(native_inventory(root))
    english = names('en', root)
    for language in CODES:
        bank = names(language, root)
        missing = [k for k in native_keys if not isinstance(bank.get(k), str) or not bank[k].strip()]
        if missing:
            raise ValueError(f'{language}: missing native captions: {missing}')
        unchanged = [k for k in native_keys if language != 'en' and bank[k] == english[k]
                     and bank[k] not in UNCHANGED_NATIVE.get(language, set())]
        if unchanged:
            raise ValueError(f'{language}: untranslated native captions: {unchanged}')
        localize(records, language, root)
    return len(records)


if __name__ == '__main__':
    print(f'Caption translations complete: {audit()} extended screens, '
          f'70 native slots (68 names), {len(CODES)} languages')
