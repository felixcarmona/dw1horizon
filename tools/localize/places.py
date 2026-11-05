"""Place-name consistency for dialogue, executable labels and story translations.

Each language's places.json records the existing vocabulary, known wrong forms,
and grammatical/short forms. New named references are also checked against the
English source, so an unfamiliar spelling cannot silently become another alias.
"""
import functools
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[2]
OPTIONAL = {'TREASURE_HUNT', 'RESTAURANT', 'ITEM_SHOP', 'ITEM_KEEPER'}
EXTRA = {'MT_PANORAMA': 'Mt. Panorama', 'ICEBERG_BEACH': 'Iceberg Beach',
         'FILE_ISLAND': 'File Island', 'CURLING_CAVE': 'Curling Cave'}


def flatten(value, language):
    if isinstance(value, str):
        return value
    return ('' if language in ('ja', 'zh-hans') else ' ').join(flatten(v, language) for v in value)


@functools.lru_cache(maxsize=65536)
def normalize(text, language):
    text = unicodedata.normalize('NFC', text).translate(str.maketrans('’‘', "''"))
    text = re.sub(r'\{[^{}]*\}', '', text)
    if language in ('ja', 'zh-hans'):
        return re.sub(r'\s+', '', text).casefold()
    return ' '.join(text.split()).casefold()


@functools.lru_cache(None)
def pattern(term, language):
    term = normalize(term, language)
    # CJK names can be directly adjacent to particles or another character.
    edge = '' if re.search(r'[\u3040-\u30ff\u3400-\u9fff]', term) else r'\w'
    if edge and language in ('ja', 'zh-hans'):
        edge = '[a-z0-9_à-ž]'
    return re.compile((f'(?<!{edge})' if edge else '') + re.escape(term) + (f'(?!{edge})' if edge else ''))


def occurrences(term, text, language):
    if normalize(term, language) not in text:
        return []
    return [m.span() for m in pattern(term, language).finditer(text)]


@functools.lru_cache(None)
def english_names(root=ROOT):
    names = json.loads((root / 'text/ours/names.json').read_text())
    english = {k.removeprefix('main.STR_MAP_NAME_'): v for k, v in names.items()
               if k.startswith('main.STR_MAP_NAME_')}
    return english | EXTRA


@functools.lru_cache(None)
def catalog(language, root=ROOT):
    path = root / 'text' / language / 'places.json'
    if not path.exists():
        return {}, {}
    entries = json.loads(path.read_text())['places']
    english = english_names(root)
    if entries.keys() != english.keys():
        raise ValueError(f'{path.name} ({language}): place inventory differs from English: '
                         f'missing {sorted(english.keys() - entries.keys())}, '
                         f'unknown {sorted(entries.keys() - english.keys())}')
    for place, entry in entries.items():
        if not isinstance(entry.get('name'), str) or not entry['name'].strip():
            raise ValueError(f'{path.name} ({language}): {place} needs a name')
    return entries, english


@functools.lru_cache(maxsize=16384)
def source_places(original, root=ROOT):
    # Prefer a complete subarea name over the parent contained inside it:
    # "Great Canyon Entrance" may have a shorter localized map caption.
    english = english_names(root)
    found = [(place, start, end) for place, term in english.items()
             for start, end in occurrences(term, original, 'en')]
    return {place for place, start, end in found
            if not any(a <= start and end <= b and b - a > end - start
                       for _, a, b in found)}


def problems(language, key, value, source=None, root=ROOT):
    entries, english = catalog(language, root)
    text = normalize(flatten(value, language), language)
    original = normalize(flatten(source, 'en'), 'en') if source is not None else ''
    errors = []
    for place, entry in entries.items():
        forms = [entry['name'], *([] if '.STR_BGM_TRACK_' in key else entry.get('accepted', []))]
        good = [span for form in forms for span in occurrences(form, text, language)]
        wrong = entry.get('avoid', []) + ([english[place]] if place in english else [])
        bad = []
        for form in wrong:
            for start, end in occurrences(form, text, language):
                if not any(a <= start and end <= b for a, b in good):
                    bad.append(form)
        if bad:
            errors.append(f'place {place}: use {entry["name"]!r}, found {bad[0]!r}')
        elif (original and place not in OPTIONAL and not good and
              (place in source_places(original, root) or
               (key == 'main.STR_BGM_TRACK_CANYON_THEME' and place == 'GREAT_CANYON'))):
            errors.append(f'place {place}: expected {entry["name"]!r} or a documented grammatical/short form')
    return errors
