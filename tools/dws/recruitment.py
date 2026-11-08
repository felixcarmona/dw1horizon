"""Extended-story recruitment policy, shared by base and mod Python sources.

The original story and story-base reproduction never enter this context. Text
uses the ordinary named mod bank and text() expansion, with content species names
(the same names the executable and DIGI.DAT use in every language).
"""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import cache
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[2]
MOD = 'what-the-island-forgot'
LINE = 'city.join'
KEY = f'{MOD}:{LINE}'
ACTIVE = ContextVar('extended_recruitment', default=False)


@contextmanager
def story(extended):
    token = ACTIVE.set(extended)
    try:
        yield
    finally:
        ACTIVE.reset(token)


def roster():
    return {r['id'] for r in json.loads((ROOT / 'content/tables/city-residents.json').read_text())}


def install(prog):
    if not ACTIVE.get():
        return
    from .py import modtext, lower
    folder = ROOT / 'story/mods' / MOD
    path = folder / 'text/en.json'
    value = json.loads(path.read_text())[LINE]
    if not isinstance(value, str) or value.count('{species}') != 1:
        raise ValueError(f'{path.name}: {LINE} needs exactly one {{species}}')
    prog.bank.data[KEY] = lower.resolve_escapes(value)
    prog.bank.origin[KEY] = str(path)
    # Base DWS and mod Python sources share the existing named-line loader,
    # including its translation, font and escape diagnostics.
    modtext.load_banks(prog, {MOD: str(folder)}, {})


@cache
def english_lines():
    """Canonical authored words for recognizing existing join narration.

    This is analysis only: emitted text still goes through the normal bank for
    the selected language. A reward or ending narrator box is not a join scene.
    """
    lines = {}
    for path in (ROOT / 'text/ours/dialogue').glob('*.json'):
        lines.update(json.loads(path.read_text()))
    lines.update(json.loads((ROOT / 'text/en.json').read_text()))
    return lines


def announcement(species, indent, won=False, sound=('8', '11')):
    guard = f'!is_recruited({species})'
    if won:
        guard = f'engine.result == 1 && {guard}'
    return [f'{indent}if ({guard}) {{',
            f'{indent}    recruit({species});',
            f'{indent}    sound({sound[0]}, {sound[1]});',
            f'{indent}    say(narrator, text("{KEY}", {species}));',
            f'{indent}}}']


# SET_TRIGGER / UNSET_TRIGGER / IF already carry u16 operands. Patch 0304
# redirects this otherwise unused range to the saved species recruit bits.
RECRUIT_BIT_BASE = 0x8000
SPECIES_LIMIT = 1024


def recruit_trigger(species):
    if not 0 <= species < SPECIES_LIMIT:
        raise ValueError(f'species {species}: recruit flags exist for types 0-1023')
    return 200 + species if species < 112 else RECRUIT_BIT_BASE + species


def species_name(ident, language):
    """Use the same authored species terms as the Chinese runtime name pool."""
    from . import backend as BE
    name = BE.DIGI_DATA[ident]['name']
    if language != 'zh-hans' or not name:
        return name
    glossary = json.loads((ROOT / 'text/zh-hans/glossary.json').read_text())
    terms = {k: v['zh'] for k, v in glossary['species'].items()}
    terms.update(glossary.get('provisional', {}))
    term = terms.get(name, glossary.get('terms', {}).get(name))
    if isinstance(term, dict):
        term = term['zh']
    if term is None:
        raise ValueError('missing Chinese species term: ' + name)
    return term
