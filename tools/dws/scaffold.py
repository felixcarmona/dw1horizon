"""`dws new` (scaffolding) and `dws doctor` (layout checks) for the story/ tree.
The layout and its rules are in docs/mods/dws.md section 2."""
import os, re, sys
try:
    import tomllib
except ImportError:                      # pragma: no cover
    tomllib = None

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STORY = os.path.join(ROOT, 'story')
KEBAB = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')
FILE_OK = re.compile(r'^(?:[a-z0-9]+(?:-[a-z0-9]+)*|s\d{3}(?:-\d+)*|sec\d{3}-[a-z0-9-]+|screen\d{3}|global-\d{4}|script|maphead|head|dup-[a-z0-9-]+)(?:\.[a-z]+)?$')
WARN_LINES, ERROR_LINES = 400, 2500          # a hand-written file; generated port chunks may be big (warning only)
SUBDIRS = ('npcs', 'quests', 'cutscenes', 'shops', 'events')


def snake(s):
    return re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_')


def camel(s):
    return ''.join(w.capitalize() for w in re.split(r'[^A-Za-z0-9]+', s) if w)


def check_name(kind, name):
    if not KEBAB.match(name):
        raise ValueError(f'{kind} name "{name}": use lower-case words joined by "-" (kunemon-bed), letters and digits only')


def write_new(path, text, force=False):
    if os.path.exists(path) and not force: raise ValueError(f'{os.path.relpath(path, ROOT)} already exists')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'w', encoding='utf-8').write(text); return path


def readme(path, text):
    if not os.path.exists(path): open(path, 'w', encoding='utf-8').write(text)


def base_dir(mod):
    return os.path.join(STORY, 'mods', mod, 'src') if mod else os.path.join(STORY, 'base')


QUEST = '''// Quest "{name}" of zone {zone}. One file per quest: its state, its rules and its text keys live here.
// Other files read this quest through its stage (`{cc}.stage`), never through its flags.
enum {cc}Stage {{ NotStarted, Started, Done }}

pub group {cc} {{
    persistent var stage: {cc}Stage;      // the only state of the quest; name each step in the enum
}}

// script <N> {{                          // the screen script that hosts the quest
//     npc giver = 5;
//     on talk(giver) {{
//         if ({cc}.stage == {cc}Stage.NotStarted) {{ {cc}.stage = {cc}Stage.Started; }}
//     }}
// }}
'''
NPC = '''// NPC "{name}" of zone {zone}. One file per NPC: who it is and its dialogue sets. Where and when it appears is
// decided in ONE place (the presence rule of this file, design in story-system.md section 6).
// npc {cc} {{ species: species("Agumon"); appears_at: screen(1) when {cc}Quest.stage >= 1; }}
'''
ZONE = '''# Zone: {name}

Everything that happens on the screens of this zone. One folder per kind of thing:

| folder | holds |
|---|---|
| `npcs/` | one file per NPC: species, presence rule, dialogue sets |
| `quests/` | one file per quest: stages, rewards |
| `cutscenes/` | one file per scripted sequence |
| `shops/` | one file per shop |
| `events/` | step/use tiles, enter hooks, time events |
'''
SUB_README = '# {sub}\n\nOne file per {one}; the file name is its id (lower-case, words joined by "-").\n'
ONE = {'npcs': 'NPC', 'quests': 'quest', 'cutscenes': 'cutscene', 'shops': 'shop', 'events': 'event'}
MOD_TOML = '''name = "{name}"
version = "0.1.0"
description = ""
authors = []
requires = ["base >= 1.0"]        # mods and the base game this one needs
load_after = []                   # explicit load order (only needed when two mods hook the same thing)
conflicts = []                    # mods that cannot be combined with this one

[save]
namespace = "{name}"              # prefix of every flag and variable of this mod in story.lock
flags = "{flags}"                  # its flags and quests: a range no other mod reserves (save.lock keeps the numbers)
vars = "{vars}"                     # its counters
'''


def mod_toml(name):
    """mod.toml of a new mod, with save ranges no other mod of story/mods reserves (the compiler requires them once the
    mod declares a flag, quest or counter)."""
    from .py.lower import free_range
    return MOD_TOML.format(name=name, flags=free_range('flags') or '717-726', vars=free_range('vars', 3) or '9-11')


def ensure_zones(mod):
    z = os.path.join(base_dir(mod), 'zones'); os.makedirs(z, exist_ok=True)
    readme(os.path.join(z, 'README.md'), '# zones\n\nOne folder per zone.\n')
    readme(os.path.join(base_dir(mod), 'README.md'), '# src\n\nSources of this part of the story.\n')


def new(kind, name, mod=None, zone=None):
    """kind: zone | quest | npc | mod. For quest/npc, name is `zone/thing`."""
    out = []
    if kind == 'mod':
        check_name('mod', name)
        d = os.path.join(STORY, 'mods', name)
        out.append(write_new(os.path.join(d, 'mod.toml'), mod_toml(name)))
        out.append(write_new(os.path.join(d, 'README.md'), f'# Mod {name}\n\nWhat this mod adds, in one paragraph.\n\n'
                             'Layout: `src/*.py`, the story in Python (docs/mods/story-language.md), one file per place; `text/<lang>.json`, '
                             f'the translations of its new lines (`python3 tools/dws.py text sync {name}`). Checked as a whole with '
                             f'`python3 tools/dws.py check story/mods/{name}`.\n'))
        for sub in ('src', 'text'):
            os.makedirs(os.path.join(d, sub), exist_ok=True)
        readme(os.path.join(d, 'src', 'README.md'), '# src\n\nThe mod\'s story in Python: one `.py` per place, named after it '
               '(`jijimons_house.py`: `from dw.base.jijimons_house import house, jijimon`); the quests, flags and counters several '
               'files share in one of them (`quests.py`), imported with `from .quests import Horn`.\n')
        readme(os.path.join(d, 'text', 'README.md'), '# text\n\nThe mod\'s own text, one JSON bank per language (committed; it is the mod author\'s).\n')
        return out
    if kind == 'zone':
        check_name('zone', name)
        ensure_zones(mod)
        d = os.path.join(base_dir(mod), 'zones', name)
        out.append(write_new(os.path.join(d, 'README.md'), ZONE.format(name=name.replace('-', ' '))))
        for sub in SUBDIRS:
            os.makedirs(os.path.join(d, sub), exist_ok=True)
            readme(os.path.join(d, sub, 'README.md'), SUB_README.format(sub=sub, one=ONE[sub])); out.append(os.path.join(d, sub, 'README.md'))
        return out
    if kind in ('quest', 'npc'):
        if '/' not in name: raise ValueError(f'{kind}: give zone/name, for example `dws new {kind} kunemons-bed/feed-kunemon`')
        zone, thing = name.split('/', 1)
        check_name('zone', zone); check_name(kind, thing)
        sub = kind + 's'
        d = os.path.join(base_dir(mod), 'zones', zone, sub)
        if not os.path.isdir(os.path.dirname(d)): new('zone', zone, mod)
        os.makedirs(d, exist_ok=True); readme(os.path.join(d, 'README.md'), SUB_README.format(sub=sub, one=ONE[sub]))
        tpl = QUEST if kind == 'quest' else NPC
        out.append(write_new(os.path.join(d, thing + '.dws'), tpl.format(name=thing, zone=zone, cc=camel(thing))))
        return out
    raise ValueError(f'unknown kind "{kind}": zone, quest, npc or mod')


# ---------------------------------------------------------------------------------------------- doctor
def ignored(path):
    """git ignores this folder (made by a tool: build output, caches): not part of the tree the doctor checks."""
    import subprocess
    try: return subprocess.run(['git', 'check-ignore', '-q', path], cwd=ROOT).returncode == 0
    except OSError: return False


def doctor(root=None):
    """Returns [(severity, message)]; severity is 'error' or 'warning'."""
    root = root or STORY; res = []
    rel = lambda p: os.path.relpath(p, ROOT)
    if not os.path.isdir(root): return [('error', f'{rel(root)} does not exist: run `dws new zone NAME` or see story-system.md section 2')]
    for must in ('README.md', 'core', 'base', 'mods'):
        if not os.path.exists(os.path.join(root, must)): res.append(('error', f'{rel(root)}/{must} is missing'))
    gi = os.path.join(ROOT, '.gitignore')
    if os.path.exists(gi) and '/text/*/' not in open(gi).read():
        res.append(('error', '.gitignore does not list /text/*/ (the text of every disc, text/us/ ...: never committed)'))
    mods = {}
    for dp, dn, fn in os.walk(root):
        dn[:] = sorted(d for d in dn if not d.startswith('.') and d != '__pycache__' and not ignored(os.path.join(dp, d)))
        if os.path.abspath(dp) == os.path.abspath(os.path.join(root, 'base')):
            dn[:] = [d for d in dn if d not in ('zones', 'maphead')]       # made from the disc (`dws story-base`), gitignored
            fn = [f for f in fn if f != 'names.dws']
        override = re.search(r'[\\/]overrides[\\/](script_\d{3}|maphead)$', dp)
        if dp != root and 'README.md' not in fn and not override:
            res.append(('error', f'{rel(dp)} has no README.md (every folder says what it holds)'))
        base = os.path.basename(dp)
        if dp != root and not override and not (KEBAB.match(base) or re.match(r'^s\d{3}(-\d+)*$', base)):
            res.append(('warning', f'folder {rel(dp)}: name it with lower-case words joined by "-"'))
        for f in fn:
            p = os.path.join(dp, f); stem, ext = os.path.splitext(f)
            if ext == '.dws':
                if not FILE_OK.match(stem): res.append(('warning', f'{rel(p)}: file names are lower-case words joined by "-"'))
                n = sum(1 for _ in open(p, encoding='utf-8', errors='replace'))
                if n > ERROR_LINES: res.append(('error', f'{rel(p)} has {n} lines (more than {ERROR_LINES}): split it'))
                elif n > WARN_LINES: res.append(('warning', f'{rel(p)} has {n} lines (more than {WARN_LINES}): consider splitting'))
                txt = open(p, encoding='utf-8', errors='replace').read()
                if re.search(r'^\s*"[^"]{12,}"\s*$', txt, re.M) and '/base/' in p.replace(os.sep, '/'):
                    res.append(('error', f'{rel(p)}: quoted text in a base-game source (use text("key"); the original text is never committed)'))
            elif f == 'mod.toml':
                mods[os.path.basename(dp)] = p
            elif ext in ('.bin', '.cue', '.iso', '.scn', '.SCN'):
                res.append(('error', f'{rel(p)}: build output or game data does not belong under story/ (generated files go to build/)'))
    # manifests
    parsed = {}
    for name, p in mods.items():
        try:
            if tomllib is None: raise ValueError('tomllib is not available (Python 3.11+)')
            m = tomllib.load(open(p, 'rb'))
        except Exception as e:
            res.append(('error', f'{rel(p)}: {e}')); continue
        for k in ('name', 'version'):
            if k not in m: res.append(('error', f'{rel(p)}: "{k}" is required'))
        if m.get('name') != name: res.append(('error', f'{rel(p)}: name "{m.get("name")}" must equal the folder name "{name}"'))
        if not re.match(r'^\d+\.\d+\.\d+$', str(m.get('version', ''))): res.append(('error', f'{rel(p)}: version must look like 1.2.3'))
        parsed[name] = m
    for name, m in parsed.items():
        for dep in m.get('requires', []):
            dn = re.split(r'[ <>=!~]', dep.strip())[0]
            if dn != 'base' and dn not in parsed: res.append(('error', f'mod {name} requires "{dn}", which is not in story/mods/'))
        for c in m.get('conflicts', []):
            if c in parsed: res.append(('error', f'mod {name} conflicts with {c}, and both are present'))
        for a in m.get('load_after', []):
            if a not in parsed: res.append(('warning', f'mod {name}: load_after "{a}" is not present'))
    return res


def run_doctor(root=None):
    res = doctor(root)
    for sev, msg in res: print(f'{sev}: {msg}')
    errs = sum(1 for s, _ in res if s == 'error')
    print(f'doctor: {errs} error(s), {len(res) - errs} warning(s)')
    return errs
