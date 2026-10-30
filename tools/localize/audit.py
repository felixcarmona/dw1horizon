"""Read-only checks for Spanish draft leakage in the playable translation banks.

Catalan shares Spanish vocabulary and is deliberately excluded. Portuguese and
Italian legitimately use 'modo'; only the Spanish battle-menu phrase is banned
there. Do not ban shared words such as Portuguese 'guardar' or Italian 'no'.
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
LANGUAGES = ('pt-br', 'fr', 'de', 'it', 'ja', 'ca')
SPANISH_WORDS = (
    'partida', 'ranura', 'ranuras', 'borrar', 'jugar', 'ciudad', 'nuevo',
    'nueva', 'tienes', 'quieres', 'puedes', 'también', 'ahora', 'cuidadito',
)


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def spanish_leaks(value, language):
    if language in ('en', 'es', 'ca'):
        return []
    words = SPANISH_WORDS + (() if language in ('pt-br', 'it') else ('modo',))
    # Latin boundaries also catch Latin leftovers directly beside Japanese kana.
    pattern = r'(?<![a-zÀ-ÿ])(?:' + '|'.join(words) + r')(?![a-zÀ-ÿ])|modo\s+(?:(?:de|di)\s+)?funk'
    return [m.group() for text in strings(value)
            for m in re.finditer(pattern, re.sub(r'\{[^{}]*\}', '', text), re.I)]


def banks(language, root=ROOT):
    yield root / 'text' / language / 'names.json'
    yield from sorted((root / 'text' / language / 'dialogue').glob('*.json'))
    yield root / 'text' / (language + '.json')
    yield from sorted((root / 'story' / 'mods').glob('*/text/' + language + '.json'))


def audit(root=ROOT):
    for language in LANGUAGES:
        for path in banks(language, root):
            for key, value in json.loads(path.read_text()).items():
                if not key.startswith('_'):
                    for word in spanish_leaks(value, language):
                        yield f'{path.relative_to(root)}:{key}: Spanish draft word {word!r}'


if __name__ == '__main__':
    errors = list(audit())
    print('\n'.join(errors) if errors else 'No Spanish draft leakage in playable translation banks.')
    raise SystemExit(bool(errors))
