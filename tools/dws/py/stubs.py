"""`dws types`: the stub package `typings/dw/` that gives Pylance/pyright the story language (docs/mods/story-language.md).

    typings/dw/__init__.pyi    the API (template api.pyi.in) + Species, Item, Tech, Screen, Routine, anim, engine, raw
    typings/dw/names.pyi       the names of story/names.toml (pstats and triggers the game already uses)
    typings/dw/text.pyi        the keys of the game's text (text.s002.sec6.u0): keys only, never the words
    typings/dw/base/<screen>.pyi  per screen of the base: its script's screens and NPCs (`from dw.base.jijimons_house import jijimon, house`)

Everything is generated from docs/data/*.csv, story/names.toml, story/core/*.dws, tools/dws/registry.py, story/base (the
screens, the NPCs and the sections of each script: naming.disc_screens, base_npcs) and the player's disc (the key list, from
text/us/), so it is the same on every machine with the same disc. `--check` compares instead of
writing (selftest)."""
import json, os, re
from .. import build as B, registry as R
from . import naming as N

ROOT = B.ROOT
OUT = os.path.join(ROOT, 'typings', 'dw')
HERE = os.path.dirname(os.path.abspath(__file__))
VERSION = '1'


def enum_block(name, members, base='IntEnum', doc=None, docs=None, comments=None):
    """`docs`: {id: text} an attribute docstring per member (what the editor shows on hover and in the completion list)."""
    out = [f'class {name}({base}):']
    if doc: out.append(f'    """{doc}"""')
    for i, m in sorted(members.items()):
        out.append(f'    {m} = {i}' + (f'    # {comments[i]}' if comments and i in comments else ''))
        if docs and docs.get(i): out.append('    """' + docs[i].replace('\\', '\\\\').replace('"', '\\"') + '"""')
    return out


def species_docs():
    """A docstring for a species whose name repeats (Greymon129: another entry of the game's table with that name)."""
    m = N.enum_members('species'); first = {}
    for i, v in sorted(m.items()):
        base = re.sub(r'\d+$', '', v) if re.fullmatch(r'.*\D\d+', v) and v.endswith(str(i)) else v
        first.setdefault(base, i)
    out = {}
    for i, v in m.items():
        if v.endswith(str(i)) and re.sub(r'\d+$', '', v) in first and first[re.sub(r'\d+$', '', v)] != i:
            b = re.sub(r'\d+$', '', v)
            out[i] = (f'Another {b} of the game\'s species table (id {i}; Species.{b} is id {first[b]}): the same name, another entry '
                      '(its model, stats and techniques may differ).')
    for former, ids in N.former_names().items():                # renamed species: the old name on hover (and in a search)
        for i in ids:
            if i in m: out[i] = (out.get(i, '') + ' ' if out.get(i) else '') + f'Formerly {former} (renamed; content/species).'
    return out


def item_docs():
    """{id: the item's optional description and price} (docs/data/items.csv)."""
    import csv
    out = {}
    for r in csv.DictReader(open(os.path.join(ROOT, 'docs', 'data', 'items.csv'), encoding='utf-8')):
        d = (r.get('description') or '').strip()
        out[int(r['id'])] = (d + '. ' if d and not d.endswith('.') else d + ' ' if d else '') + f'Item {r["id"]}, {r["value"]} bits.'
    return out


def anim_block():
    from ..lift import Names
    out = ['class anim:', '    """Animation slots the engine gives a meaning to (story/core/scene.dws); other slots are numbers: `play(29)`."""']
    for line in open(os.path.join(ROOT, 'story', 'core', 'scene.dws'), encoding='utf-8'):
        m = re.match(r'\s*const (\w+) = (\d+);\s*(//.*)?$', line)
        if m: out.append(f'    {m.group(1)}: int = {m.group(2)}' + (f'    # {m.group(3)[2:].strip()}' if m.group(3) else ''))
    return out


def engine_block():
    """`engine.arg`, `engine.cutscene`... (story/core/engine.dws) and the other aliases of story/core."""
    out = ['class _engine:']; extra = []
    group = None
    for fn in sorted(os.listdir(os.path.join(ROOT, 'story', 'core'))):
        if not fn.endswith('.dws'): continue
        for line in open(os.path.join(ROOT, 'story', 'core', fn), encoding='utf-8'):
            m = re.match(r'\s*(?:pub\s+)?group\s+(\w+)\s*\{', line)
            if m: group = m.group(1); continue
            if re.match(r'\s*\}', line): group = None; continue
            m = re.match(r'\s*(?:pub\s+)?alias\s+(flag|var)\s+(\w+)\s*=\s*(\d+)\s*;\s*(//.*)?', line)
            if not m: continue
            t = 'Flag' if m.group(1) == 'flag' else 'Var'
            doc = f'    # {m.group(1)} {m.group(3)}' + (f': {m.group(4)[2:].strip()}' if m.group(4) else '')
            if group == 'engine': out.append(f'    {m.group(2)}: {t}{doc}')
            elif group is None: extra.append(f'{m.group(2)}: {t}{doc}')
    return out + ['engine: _engine'] + extra


ARG = {'e': 'Entity | int', 'u8': 'int', 'i': 'Item | int', 'i16': 'Item | int', 'd': 'Species | int', 'd16': 'Species | int', 'v': 'Tech | int',
       'v16': 'Tech | int', 't': 'Flag | int', 'p': 'Var | int', 'm': 'Screen | int', 'm16': 'Screen | int', 'c': 'str', 'l': 'Callable[[], None]'}


def raw_block():
    out = ['class _Raw:', '    """One DWS command by its name (tools/dws/registry.py): `raw.jump_to_file(210, 51)`."""']
    for name, cmd in sorted(R.COMMANDS.items()):
        if name.startswith('unused_') or not name.isidentifier(): continue
        args = ', '.join(f'a{k}: {ARG.get(f, "int")}' for k, f in enumerate(cmd.fields))
        out.append(f'    def {name}(self{", " if args else ""}{args}, /) -> None: ...')
    out += ['    def show_textbox(self, *rows: Key | str) -> None: ...', '    def data(self, *values: int) -> None: ...',
            'raw: _Raw']
    return out


def routines_block():
    return enum_block('Routine', {k: n for k, n in R.ROUTINES.items() if n}, doc='CALL_ROUTINE numbers: `call(Routine.shop)`') + [''] + \
        enum_block('DigimonRoutine', dict(R.DIGIMON_ROUTINES), doc='CALL_DIGIMON_ROUTINE numbers: `raw.call_digimon_routine(DigimonRoutine.toilet)`')


def init_pyi():
    lines = open(os.path.join(HERE, 'api.pyi.in'), encoding='utf-8').read().replace("__version__: str = ...", f"__version__: str = '{VERSION}'").rstrip('\n').split('\n')
    lines += ['', *enum_block('Species', N.enum_members('species'), doc='The species of the game and the imported ones (content/species).',
                              docs=species_docs())]
    lines += ['', *enum_block('Item', N.enum_members('item'), doc='Items (docs/data/items.csv). In a line, "Received a {item Item.Meat}." writes the name the inventory shows (US, ours or a translation): typed by hand it would not follow a rename.', docs=item_docs())]
    lines += ['', *enum_block('Tech', N.enum_members('tech'), doc='Techniques (docs/data/techs.csv).')]
    names, _ = N.disc_screens()
    sm = N.screen_members()
    scr = ['class Screen(IntEnum):', '    """The screens of the game, by caption (a caption that repeats gets the screen number)."""']
    script_of = {s: sid for sid, ss in N.disc_screens()[1].items() for s in ss}
    for i, m in sorted(sm.items()):
        scr.append(f'    {m} = {i}' + (f'    # {names[i]}' if i in names else ''))
        if i in script_of:
            scr.append(f'    """{names.get(i, "")}: screen {i}, script {script_of[i]} (its screen and NPCs: `from dw.base.{m} import ...`)."""'
                       if names.get(i) else f'    """Screen {i}, script {script_of[i]}."""')
    lines += ['', *scr, '', *routines_block(), '', *anim_block(), '', *engine_block(), '', *raw_block()]
    return '\n'.join(lines) + '\n'


def names_pyi():
    from ..lift import Names
    nm = Names()
    out = ['# typings/dw/names.pyi: names of state the game already uses (story/names.toml). Generated by `dws types`.',
           'from dw import Flag, Var', '']
    groups = {}; plain = []
    for kind, table in (('Flag', nm.extra_flags), ('Var', nm.extra_vars)):
        for n, name in sorted(table.items()):
            g, _, leaf = name.rpartition('.')
            line = f'{leaf}: {kind}    # {"trigger" if kind == "Flag" else "pstat"} {n}'
            (groups.setdefault(g, []) if g else plain).append(line)
    out += plain
    for g, lines in sorted(groups.items()):
        cls = '_' + g.replace('.', '_')
        out += ['', f'class {cls}:'] + ['    ' + l for l in lines] + [f'{g}: {cls}']
    return '\n'.join(out) + '\n'


def text_keys():
    from ..textx import BANK as p
    if not os.path.exists(p):
        from .. import basebuild
        basebuild.ensure_text()
    return sorted(json.load(open(p, encoding='utf-8')))


def text_pyi():
    tree = {}
    for k in text_keys():
        parts = k.split('.')
        if not all(x.isidentifier() for x in parts): continue
        node = tree
        for x in parts[:-1]: node = node.setdefault(x, {})
        node[parts[-1]] = None
    out = ['# typings/dw/text.pyi: the keys of the game\'s text on the player\'s disc (keys only, never the words).',
           '# Generated by `dws types`. `text.s002.sec6.u0` is script 2, section 6, utterance 0 (a text box and its pages); '
           '`text.s002.sec6.m1.o0` option 0 of its menu 1.', 'from dw import Key', '']
    def emit(node, path):
        cls = '_t_' + '_'.join(path) if path else '_Text'
        body = []
        for name, sub in sorted(node.items(), key=lambda kv: [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', kv[0])]):
            if sub is None: body.append(f'    {name}: Key')
            else:
                emit(sub, path + [name]); body.append(f'    {name}: _t_{"_".join(path + [name])}')
        out.extend([f'class {cls}:'] + (body or ['    ...']) + [''])
    emit(tree, [])
    out.append('text: _Text')
    return '\n'.join(out) + '\n'


def base_npcs(sid, names):
    """[(entity, name, species id or None)] of a script: the slots MAPHEAD places and the talk sections the script has (story/base:
    naming.script_sections, base_names)."""
    ents = {s for s in N.script_sections(sid) if 5 <= s <= 12}
    for key in list(names.auto) + list(names.npc):
        a, e = key.split('.')
        if int(a) == sid: ents.add(int(e))
    return [(e, names.npc_name(sid, e), names.species.get((sid, e))) for e in sorted(ents)]


def base_pyi(sid, names, screen):
    """The module of one screen of the base (`from dw.base.jijimons_house import house, jijimon`): the screen(s) of its
    script and the NPCs the script talks to, with the .MAP slot each one is in on this screen."""
    sp = N.enum_members('species')
    allnames, _ = N.disc_screens()
    out = [f'# typings/dw/base/{N.screen_members()[screen]}.pyi: screen {screen} ({allnames.get(screen, "")}) of the base story, '
           f'script {sid}. Generated by `dws types`.',
           '# A handler on these needs `when=` (it is added to the base\'s); `take_over(npc)` owns an NPC (docs/mods/story-language.md).',
           'from dw import ScreenRef, NPC', '']
    if len(N.screen_vars(sid)) > 1:
        out[-2:-2] = [f'# Script {sid} serves {len(N.screen_vars(sid))} screens, all named here (each of their modules exports them all).']
    for s, var in N.screen_vars(sid):
        out.append(f'{var}: ScreenRef    # screen {s}, {allnames.get(s, "")}')
    several = len(N.screen_vars(sid)) > 1
    for e, name, species in base_npcs(sid, names):
        home, k = N.npc_home(sid, e, screen)
        from .view import unplaced
        out.append(f'{name}: NPC    # ' + ((f'slot {k} of screen {home}' if several else f'slot {k}') if k is not None
                                           else f'entity {e} (no slot of this screen)')
                   + (f', {sp[species]}' if species in sp else f' ({unplaced(home, k)})' if k is not None else ''))
    return '\n'.join(out) + '\n'


def base_names():
    """lift.Names with the NPCs of story/base's MAPHEAD (the species each screen's setup places, naming.maphead_asm)."""
    from .. import readable
    return readable.make_names(N.maphead_asm())


def files():
    """{relative path under typings/dw: text}"""
    out = {'__init__.pyi': init_pyi(), 'names.pyi': names_pyi(), 'text.pyi': text_pyi(),
           'base/__init__.pyi': '# typings/dw/base: the base story\'s screens and NPCs, one module per screen, named like the Screen '
                                'member (dw.base.jijimons_house).\n'}
    names = base_names()
    _, by = N.disc_screens(); sm = N.screen_members()
    for sid in sorted(by):                                   # (a script no screen loads has no module: nothing to add to)
        for scr in by[sid]:
            out[f'base/{sm[scr]}.pyi'] = base_pyi(sid, names, scr)
    return out


def stale(out_dir, have):
    """Files under typings/dw/base that the generator no longer makes (the old per-script modules)."""
    d = os.path.join(out_dir, 'base')
    if not os.path.isdir(d): return []
    return [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.endswith('.pyi') and f'base/{f}' not in have]


def write_base_pyi(out_dir=OUT, log=None):
    """Only typings/dw/base/*.pyi (what `story-base` refreshes). -> files written"""
    n = 0; fs = files()
    for rel, text in fs.items():
        if not rel.startswith('base/'): continue
        p = os.path.join(out_dir, rel)
        if os.path.exists(p) and open(p, encoding='utf-8').read() == text: continue
        os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'w', encoding='utf-8').write(text); n += 1
    for p in stale(out_dir, fs): os.remove(p); n += 1
    if log and n: log(f'typings/dw/base: {n} file(s) written')
    return n


def write(out_dir=OUT, check=False, log=print):
    """-> number of files that differ (check) or were written."""
    n = 0; fs = files()
    for rel, text in fs.items():
        p = os.path.join(out_dir, rel)
        old = open(p, encoding='utf-8').read() if os.path.exists(p) else None
        if old == text: continue
        n += 1
        if check: log(f'differs: {os.path.relpath(p, ROOT)}'); continue
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'w', encoding='utf-8').write(text)
    for p in stale(out_dir, fs):
        n += 1
        if check: log(f'no longer generated: {os.path.relpath(p, ROOT)}'); continue
        os.remove(p)
    log(f'typings/dw: {n} file(s) {"differ" if check else "written"}')
    return n
