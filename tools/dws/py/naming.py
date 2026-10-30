"""Names shared by the stub generator (`dws types`), the Python view of the base (`story-base`) and the lowering: one rule
each, so a name a mod imports from `dw.base.<screen>` is the name the view prints and the lowering resolves.

    enum members   Species.Gekomon, Item.SweetNut, Tech.FireTower (CamelCase of the game's name; the id when it repeats)
    screens        Screen.jijimons_house (snake_case of the caption; captions that repeat get the screen id: native_forest_2)
    screen vars    the caption's last word in the script's view (house, forest, bed); `<word>_<id>` when it repeats there
    NPC vars       the species in the slot (lift.Names: `<species><slot>` when it repeats in the script, `slot<k>` unknown)

The screens of each script, the NPCs MAPHEAD places for it and the sections it has are read from story/base (its MAPHEAD's
DWS, maphead/*.dws, and each script's `sections(...)`), our source, not from a disc: the build works on any release's
disc (docs/mods/data-sources.md). `story-base` points BASE at the folder it is generating.
"""
import keyword, os, re
from .. import build as B

ROOT = B.ROOT
BASE = os.path.join(ROOT, 'story', 'base')        # the story the names are read from
_CACHE = {}


def use_base(path):
    """Read the screens, NPCs and sections from another story/base folder (the one `story-base` is writing, a test's). -> the
    previous folder (to restore)."""
    global BASE
    old = BASE; BASE = path
    for k in [k for k in _CACHE if k in ('screens', 'screen_members', 'maphead') or k.startswith('sections')]: del _CACHE[k]
    return old


def camel(name):
    words = re.findall(r'[A-Za-z0-9]+', name)
    s = ''.join(w[:1].upper() + w[1:] for w in words)
    if not s: return None
    if s[0].isdigit(): s = 'N' + s
    return s


def former_names():
    """{former name as a member (Rockmon): [species ids]}: the `_former_name` of content/species (renamed species)."""
    if 'former' in _CACHE: return _CACHE['former']
    import glob, json
    from .. import backend as BE
    out = {}
    for f in sorted(glob.glob(os.path.join(BE.ROOT, 'content', 'species', '*.json'))):
        try: d = json.load(open(f, encoding='utf-8'))
        except ValueError: continue
        m = re.match(r'(\d+)-', os.path.basename(f))
        if d.get('_former_name') and m: out.setdefault(camel(d['_former_name']), []).append(int(m.group(1)))
    _CACHE['former'] = out
    return out


def snake(name):
    s = re.sub(r'[^a-z0-9]+', '_', name.lower().replace("'", '')).strip('_')
    if not s: return None
    if s[0].isdigit(): s = 'n' + s
    if keyword.iskeyword(s): s += '_'
    return s


def unique(pairs, fmt=lambda name, i: f'{name}{i}', first=False):
    """[(id, name)] -> {id: identifier}: a name that repeats gets its id (first=True: all but the first, which is what DWS's
    item("X") / species("X") resolve to)."""
    count = {}
    for i, n in pairs:
        if n: count[n] = count.get(n, 0) + 1
    out = {}; seen = set()
    for i, n in pairs:
        if not n: continue
        out[i] = n if count[n] == 1 or (first and n not in seen) else fmt(n, i)
        seen.add(n)
    return out


def enum_members(kind):
    """{id: member} of Species, Item or Tech, from the game's tables (docs/data/*.csv via bytecode) plus the imported species."""
    if kind in _CACHE: return _CACHE[kind]
    from dws import bytecode
    from .. import backend as BE
    table = dict(bytecode.names()[{'species': 'd', 'item': 'i', 'tech': 'v'}[kind]])
    pairs = sorted((i, camel(n)) for i, n in table.items() if n)
    if kind == 'species':                       # the imported species come after the game's (DWS resolves a name to the first)
        pairs += sorted((t, camel(r['name'])) for t, r in BE.EXTRA_SPECIES.items() if t not in table)
    out = unique(pairs, first=True)
    for i in list(out):
        if keyword.iskeyword(out[i]): out[i] += '_'
    _CACHE[kind] = out
    return out


MH_SECTION = re.compile(r'^\s*section\((\d+)\)')
MH_SHARED = re.compile(r'^\s*shared \w+ \{\s*// code of sec(\d+)\b')      # the readable form's shared code: where it stood
MH_SCRIPT = re.compile(r'\bset_script\((\d+),')
MH_DIGIMON = re.compile(r'\bset_digimon\(species\((\d+|"[^"]*")\), (\d+), (\d+)\)')


def maphead_facts(texts=None):
    """{MAPHEAD section: ([script ids it sets], [(species id, slot, x)] it places)} of story/base's MAPHEAD: its DWS
    (maphead/*.dws, the proven intermediate beside hooks.py), the code of a `shared` block counted in the section it stood in
    on the disc (`// code of secN`), as the disc's disassembly did. texts: other DWS texts to read (the build's own check)."""
    import glob
    from .. import backend as BE
    if texts is None:
        files = sorted(glob.glob(os.path.join(BASE, 'maphead', '*.dws')))
        if not files: raise FileNotFoundError(f'{os.path.relpath(BASE, ROOT)}/maphead/*.dws: no MAPHEAD in story/base')
        texts = [open(f, encoding='utf-8').read() for f in files]
    spn = BE.names()['species']
    out = {}; cur = None
    for t in texts:
        for line in t.split('\n'):
            m = MH_SECTION.match(line) or MH_SHARED.match(line)
            if m: cur = out.setdefault(int(m.group(1)), ([], [])); continue
            if cur is None: continue
            cur[0].extend(int(x) for x in MH_SCRIPT.findall(line))
            for sp, slot, x in MH_DIGIMON.findall(line):
                cur[1].append((int(sp) if sp.isdigit() else spn[sp.strip('"').strip().lower()], int(slot), int(x)))
    return out


def base_maphead():
    if 'maphead' not in _CACHE: _CACHE['maphead'] = maphead_facts()
    return _CACHE['maphead']


def maphead_asm():
    """The MAPHEAD facts as the disassembly's lines (secN:, SET_SCRIPT, SET_DIGIMON): what lift.Names.load_npcs reads."""
    lines = []
    for sec, (scripts, digs) in sorted(base_maphead().items()):
        lines.append(f'sec{sec}:')
        lines += [f'    SET_SCRIPT {a}, {sec}' for a in scripts]
        lines += [f'    SET_DIGIMON {sp}, {slot}, {x}' for sp, slot, x in digs]
    return '\n'.join(lines) + '\n'


def disc_screens():
    """{screen: caption} and {script: [screens]}: the script each screen's setup in story/base's MAPHEAD sets (SET_SCRIPT, the
    first), and the caption of docs/data/map_files.csv; a screen without a caption has no name (the game's 239-254), as in
    the disassembly header these were once read from."""
    if 'screens' in _CACHE: return _CACHE['screens']
    from dws import bytecode
    caption = bytecode.names()['m']
    names = {}; by_script = {}
    for sec, (scripts, _) in sorted(base_maphead().items()):
        if sec > 254 or not scripts or not caption.get(sec): continue
        names[sec] = caption[sec]; by_script.setdefault(scripts[0], []).append(sec)
    _CACHE['screens'] = (names, by_script)
    return names, by_script


def script_file(sid):
    """story/base's view of script `sid` (zones/<zone>/sNNN-<screens>/script.py), or None (no file: no script)."""
    import glob
    return next((p for p in sorted(glob.glob(os.path.join(BASE, 'zones', '*', f's{sid:03d}*', 'script.py')))
                 if re.match(rf's{sid:03d}(-|$)', os.path.basename(os.path.dirname(p)))), None)


def script_sections(sid):
    """The section numbers of script `sid` in story/base: its view's `sections(...)` (the section table, with the shared
    blocks' entries); none when it has no view."""
    key = f'sections{sid}'
    if key in _CACHE: return _CACHE[key]
    import ast
    out = set(); p = script_file(sid)
    if p:
        for st in ast.parse(open(p, encoding='utf-8').read(), p).body:
            if isinstance(st, ast.Expr) and isinstance(st.value, ast.Call) and isinstance(st.value.func, ast.Name) \
                    and st.value.func.id == 'sections':
                for a in st.value.args:
                    if isinstance(a, ast.Constant) and isinstance(a.value, int): out.add(a.value)
                    elif isinstance(a, ast.Tuple) and a.elts and isinstance(a.elts[0], ast.Constant): out.add(a.elts[0].value)
    _CACHE[key] = out
    return out


def screen_members():
    """{screen id: Screen member}"""
    if 'screen_members' in _CACHE: return _CACHE['screen_members']
    names, _ = disc_screens()
    out = unique(sorted((i, snake(n)) for i, n in names.items()), fmt=lambda n, i: f'{n}_{i}')
    out.update(names_toml().get('screens', {}))            # the names story/names.toml [screens] gives
    _CACHE['screen_members'] = out
    return out


def screen_vars(sid):
    """[(screen id, variable)] of a script's view: the last word of each screen's caption, `<word>_<id>` when it repeats."""
    names, by_script = disc_screens()
    scr = by_script.get(sid, [])
    pairs = [(s, (snake(names[s]) or 'screen').split('_')[-1] or 'screen') for s in scr]
    pairs = [(s, w + '_' if keyword.iskeyword(w) or w in RESERVED else w) for s, w in pairs]
    u = unique(pairs, fmt=lambda n, i: f'{n}_{i}')
    return [(s, u[s]) for s, _ in pairs]


def npc_slot(screen, entity):
    """The .MAP slot of `screen` whose Digimon the script calls `entity` (`backend.screen_slots`): the first slot with that
    script id; entity - 5 when the .MAP has no such slot and that slot is free; None when no slot gives that entity (the
    view then writes `entity(n)`)."""
    from .. import backend as BE
    slots = BE.screen_slots(screen)
    k = next((d['slot'] for d in slots if d['entity'] == entity), None)
    if k is not None: return k
    k = entity - 5
    return k if k >= 0 and BE.slot_entity(screen, k) == entity else None


def npc_home(sid, entity, prefer=None):
    """(screen, slot) of the .MAP slot whose script id is `entity` on a screen of script `sid` (`prefer` first): the screen an
    NPC of a script that serves several screens stands on. A script id no .MAP slot has: (prefer or the first screen,
    npc_slot there)."""
    from .. import backend as BE
    screens = disc_screens()[1].get(sid, [])
    for s in ([prefer] if prefer in screens else []) + [s for s in screens if s != prefer]:
        k = next((d['slot'] for d in BE.screen_slots(s) if d['entity'] == entity), None)
        if k is not None: return s, k
    s = prefer if prefer is not None else (screens[0] if screens else None)
    return s, (npc_slot(s, entity) if s is not None else None)


def names_toml():
    if 'toml' not in _CACHE:
        from ..minitoml import load_toml
        d = load_toml(os.path.join(ROOT, 'story', 'names.toml'))
        d['screens'] = {int(k): v for k, v in d.get('screens', {}).items()}
        _CACHE['toml'] = d
    return _CACHE['toml']


# names of the dw API a view or a mod uses unqualified: an NPC or screen variable must not shadow them
RESERVED = {
    'Level', 'Outcome', 'say', 'ask', 'choose', 'page', 'fight', 'won', 'lost', 'fled', 'recruitable', 'join_city', 'recruit', 'unrecruit', 'send_to_city', 'walk_away', 'walk',
    'run', 'arrived', 'face', 'turn', 'play', 'leave', 'wait', 'sound', 'music', 'camera', 'warp', 'hide_hud', 'fade_to_white',
    'fade_from_white', 'spawn_item', 'objects', 'load', 'spawn', 'shop', 'call', 'raw', 'dws', 'give', 'take', 'learn', 'has',
    'bits', 'recruited', 'clock', 'partner', 'tamer', 'narrator', 'random', 'pick_item',
    'take_picked', 'Picked', 'screen', 'new_screen', 'take_over', 'script', 'hook', 'sections', 'flag', 'counter', 'advance', 'Quest', 'trigger', 'pstat',
    'stat', 'condition', 'knows', 'has_card', 'entity', 'text', 'anim', 'engine', 'glances', 'Species', 'Item', 'Tech', 'Screen',
    'Routine', 'Card', 'auto', 'Enum', 'chance', 'use_script', 'jump_to_script', 'spawn_chest', 'DigimonRoutine', 'everyone', 'npc', 'section', 'shared', 'self', 'all', 'any', 'print', 'type',
    'id', 'map', 'input', 'list', 'dict', 'set', 'str', 'int', 'len', 'range', 'object', 'match', 'case', 'next', 'iter',
}
