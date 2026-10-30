"""Languages supported by the game's optional runtime selector.

The text-source identifier is also the mod bank's language (text/pt-br.json), while
PT_BR is the C preprocessor identifier and LANGPT.BIN is an 8.3 disc filename.
"""
CODES = ('en', 'es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca')
PATCHES = dict(zip(CODES, ('LANGEN.BIN', 'LANGES.BIN', 'LANGPT.BIN', 'LANGFR.BIN', 'LANGDE.BIN', 'LANGIT.BIN', 'LANGJA.BIN', 'LANGCA.BIN')))
COLUMNS = {'es': 1, 'en': 2, 'pt-br': 3, 'fr': 4, 'de': 5, 'it': 6, 'ja': 7, 'ca': 8}
PREFIXES = {'en': 'LE', 'es': 'LE', 'pt-br': 'LP', 'fr': 'LF', 'de': 'LD', 'it': 'LI', 'ja': 'LJ', 'ca': 'LC'}


def selected(env):
    value = env.get('LANGS') or ''
    if not value:
        return ()
    codes = tuple(value.split(','))
    if len(set(codes)) != len(codes) or any(c not in CODES for c in codes):
        raise ValueError(f'LANGS={value}: choose unique languages from {",".join(CODES)}')
    if 'en' not in codes or len(codes) < 2:
        raise ValueError('LANGS needs en and at least one translation (' + ','.join(CODES[1:]) + ')')
    if (env.get('LANG_BASE') or 'en') not in codes:
        raise ValueError('LANG_BASE must be a language included in LANGS')
    return tuple(c for c in CODES if c in codes)


def translations(env):
    return tuple(c for c in selected(env) if c != 'en')
