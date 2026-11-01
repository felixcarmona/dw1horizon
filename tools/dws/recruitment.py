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
    return lines


def announcement(species, indent, won=False):
    guard = f'!is_recruited({species})'
    if won:
        guard = f'engine.result == 1 && {guard}'
    return [f'{indent}if ({guard}) {{',
            f'{indent}    recruit({species});',
            f'{indent}    sound(8, 11);',
            f'{indent}    say(narrator, text("{KEY}", {species}));',
            f'{indent}}}']
