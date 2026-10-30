"""Story-owned music bindings, applied after assembly at the original instruction offsets."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(path):
    data = json.loads(Path(path).read_text())
    if data['format'] != 1:
        raise ValueError('unknown story audio resource format')
    return data


def rewrite_maphead(src, out, manifest):
    import sound
    data = Path(src).read_bytes()
    lines = []
    for binding in load(manifest)['music']:
        screen, font = binding['screen'], binding['font']
        data, old, offset = sound.set_bgm(data, screen, font)
        lines.append(f'{out}: screen {screen}: SET_BGM {old:#x} -> {font:#x} at {offset:#x}')
    Path(out).write_bytes(data)
    return lines


DEFAULT_MANIFEST = ROOT / 'story/core/audio.json'


def bank_names(manifest=DEFAULT_MANIFEST):
    spec = load(manifest)['banks']
    return (*spec['indexed'], spec['music'])


def bank_commands(out, scratch, manifest=DEFAULT_MANIFEST):
    """The story's font/program policy as commands; the build adapter supplies routing and limits."""
    spec = load(manifest)['banks']
    sources = {key: str(ROOT / path) for key, path in spec['sources'].items()}
    song, pad, bell = (sources[key] for key in ('song', 'pad', 'bell'))
    out, scratch = Path(out), Path(scratch)
    bank = spec['music'] + '.VHB'
    final, first, second = str(out / bank), str(scratch / (spec['music'] + '-fonts.VHB')), str(scratch / (spec['music'] + '-pad.VHB'))
    instruments = hex(spec['instruments_font'])
    return ([['index', name, '-o', str(out / (name + '.VHB'))] for name in spec['indexed']] + [
        ['add-font', song, '--instruments', instruments, '-o', final, '--loop'],
        ['add-font', song, '--instruments', instruments, '--prog-map', spec['program_map'], '--vhb', final,
         '-o', first, '--loop'],
        ['import-wav', first, str(spec['theme_font']), pad, '--program', str(spec['pad_program']), '--keys', '0-120', '-o', second],
        ['import-wav', second, str(spec['theme_font']), bell, '--program', str(spec['bell_program']), '--keys', '0-120', '-o', final]])
