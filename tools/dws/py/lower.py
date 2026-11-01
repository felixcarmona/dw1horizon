"""The front end of the story language (milestone 4a of docs/mods/story-language.md): a `.py` file of the subset ->
DWS text -> `parser.Node`. The file is read with `ast` and never executed; anything outside the subset is an error with
its line, column and a rewrite hint. The DWS it produces is what the compiler, `flowcmp` and `story-verify` already know.

    python3 tools/dws.py lower FILE.py        # the DWS of a .py file
    python3 tools/dws.py check FILE.py        # parse, lower, compile (a .py and .dws files may be given together)

The lowering is the inverse of the base view's printer (tools/dws/py/view.py): every form the view prints lowers to the
DWS it was printed from. The forms only mods use (guards, quests, flags, new NPCs, inline text) are in `Module.mod_*`."""
from ..targets import profile_pool
import ast, difflib, json, os, re
from ..diag import DwsError
from .. import backend as BE
from . import naming as N

ROOT = BE.ROOT
CORE = [os.path.join(ROOT, 'story', 'core', f) for f in ('engine.dws', 'scene.dws', 'recruit.dws')]


def import_line(path):
    """An `import` of the lowered code: a backslash in a story string is an escape, so paths keep forward slashes."""
    return 'import "' + path.replace(os.sep, '/') + '";'


ROOTS = ('dw', 'dw.text', 'dw.names')
CMP = {ast.Eq: '==', ast.NotEq: '!=', ast.Lt: '<', ast.LtE: '<=', ast.Gt: '>', ast.GtE: '>='}
TICK_MS = 50                                           # the game counts 20 ticks a second
TARGET = {'exe': 'original'}                           # the executable of the run (build.py_sources): which species a partner can be
WIDE_EXES = ('species', 'story-state')                       # the executables whose partner can be a species past 255 (DIGI.DAT)


class PyError(DwsError):
    pass


class PyErrors(PyError):
    """Every error of one file, reported together (a writer fixes them in one go, not one per run)."""
    def __init__(self, errors):
        super().__init__(errors[0].msg, errors[0].pos, errors[0].hint)
        self.errors = errors

    def render(self, kind='error'):
        return '\n'.join(e.render(kind) for e in self.errors)

    __str__ = render


def minimal_cover(on, dc, k):
    """Quine-McCluskey for k <= 4 bits: the fewest products (each {bit: value}) that cover `on` and nothing outside on + dc."""
    import itertools
    cubes = []
    for mask in range(1 << k):                     # bits that a product fixes
        for vals in range(1 << k):
            if vals & ~mask: continue
            cover = [v for v in range(1 << k) if v & mask == vals]
            if all(v in on or v in dc for v in cover) and any(v in on for v in cover):
                cubes.append(({j: (vals >> j) & 1 for j in range(k) if mask >> j & 1}, set(cover)))
    for r in range(1, len(on) + 1):
        best = None
        for combo in itertools.combinations(cubes, r):
            if set(on) <= set().union(*(c for _, c in combo)):
                cost = sum(len(p) for p, _ in combo)
                if best is None or cost < best[0]: best = (cost, [p for p, _ in combo])
        if best: return best[1]
    raise AssertionError('no cover')


class ModLock:
    """The reserved ranges of a mod (`mod.toml [save] flags = "12000-12099"`, `vars = "900-909"`) and its lock
    (`story/mods/<mod>/save.lock`: {"flags": {name: n}, "vars": {...}}, append-only). `mod_dir` is the mod's folder (the
    one that holds src/): the files are read where the mod is, wherever that is."""
    def __init__(self, mod, mods_dir=None, mod_dir=None):
        import json
        from ..minitoml import load_toml
        self.mod = mod
        self.dir = mod_dir or os.path.join(mods_dir or os.path.join(ROOT, 'story', 'mods'), mod)
        self.toml = toml = os.path.join(self.dir, 'mod.toml')
        save = (load_toml(toml).get('save') or {}) if os.path.exists(toml) else {}
        self.has_save = 'save' in (load_toml(toml) if os.path.exists(toml) else {})
        self.ranges = {}
        for k in save:
            if k not in ('flags', 'vars', 'namespace'):          # (namespace: `dws new mod` writes it; DWS mods read it)
                import difflib
                near = difflib.get_close_matches(k, ['flags', 'vars'], 1, 0.5)
                raise PyError(f'{toml}: unknown key `{k}` in [save]' + (f': `{near[0]}`' if near else ''),
                              None, '[save] takes flags = "FIRST-LAST" and vars = "FIRST-LAST"')
        for kind in ('flags', 'vars'):
            v = save.get(kind)
            if v is None: continue
            m = re.fullmatch(r'\s*(\d+)\s*-\s*(\d+)\s*', str(v))
            if not m: raise PyError(f'{toml}: [save] {kind} = "FIRST-LAST" (e.g. "12000-12099")', None)
            self.ranges[kind] = (int(m.group(1)), int(m.group(2)))
        self.path = os.path.join(self.dir, 'save.lock')
        self.data = json.load(open(self.path, encoding='utf-8')) if os.path.exists(self.path) else {}
        self.dirty = False
        self.added = []              # (kind, name, number) this run gave (save writes them)

    def number(self, kind, name, mod, node=None):
        table = self.data.setdefault(kind, {})
        if name in table: return table[name]
        lo, hi = self.ranges[kind]
        used = set(table.values())
        n = next((k for k in range(lo, hi + 1) if k not in used), None)
        if n is None:
            free = free_range(kind, 3)
            pool = ('the original engine\'s free flags are 717-799; on the story-state engine, story flags such as "12100-12199"' if kind == 'flags'
                    else 'the original engine\'s free saved counters are 7-15 and 20; on the story-state engine, story variables')
            err = PyError(f'the {kind} range {lo}-{hi} of {mod.mod} (mod.toml) is full: save.lock gives its numbers to '
                          + ', '.join(sorted(table, key=table.get)),
                          None, f'a name in save.lock that the mod no longer has keeps its number: remove it there if no saved game '
                                f'uses it; or reserve more ({pool}' + (f'; free here: "{free}"' if free else '') + ')')
            raise mod.err(node, err.msg, err.hint) if node is not None else err
        table[name] = n; self.dirty = True; self.added.append((kind, name, n))
        return n

    def save(self):
        if not self.dirty: return
        import json
        open(self.path, 'w', encoding='utf-8').write(json.dumps(self.data, indent=1, sort_keys=True) + '\n'); self.dirty = False


_LOCKS = {}


def mod_lock(mod, mod_dir=None):
    """The lock of the mod whose folder is `mod_dir` (story/mods/<mod>), one per folder."""
    key = os.path.abspath(mod_dir) if mod_dir else mod
    if key not in _LOCKS: _LOCKS[key] = ModLock(mod, mod_dir=mod_dir)
    return _LOCKS[key]


def free_range(kind, size=10):
    """A range of `size` numbers that no mod of story/mods reserves, in the original engine's pool (flags: triggers 717-799;
    vars: the saved pstats 7-15) -> "FIRST-LAST" or None. What `mod.toml [save]` is told to add."""
    import glob
    from ..minitoml import load_toml
    from ..alloc import PROFILES
    pool = [n for n in PROFILES[profile_pool('original')][('flag', 'save') if kind == 'flags' else ('var', 'save')].numbers if n < 16 or kind == 'flags']
    taken = set()
    for t in glob.glob(os.path.join(ROOT, 'story', 'mods', '*', 'mod.toml')):
        m = re.fullmatch(r'\s*(\d+)\s*-\s*(\d+)\s*', str((load_toml(t).get('save') or {}).get(kind, '')))
        if m: taken |= set(range(int(m.group(1)), int(m.group(2)) + 1))
    free = [n for n in pool if n not in taken]
    for size in (size, 5, 2, 1):
        for i in range(len(free) - size + 1):
            if free[i + size - 1] - free[i] == size - 1: return f'{free[i]}-{free[i + size - 1]}'
    return None


def save_locks():
    """Writes the numbers this run gave into each mod's save.lock. rule: a build that only reads (tools/derive, backend
    LOCKS_READ_ONLY: the player's build never writes the mod's committed files) stops instead when a lock would grow."""
    if BE.LOCKS_READ_ONLY:
        grown = [f'{os.path.relpath(l.path, ROOT)}: {kind} {name} = {n}' for l in _LOCKS.values() if l.dirty
                 for kind, name, n in l.added]
        if grown:
            raise PyError('the story gives new save numbers that the mods\' save.lock files do not have (this build only reads '
                          'them): ' + '; '.join(grown[:8]) + (' ...' if len(grown) > 8 else ''), None,
                          'compile the story once with tools/dws.py (a development build writes them) and commit save.lock')
        return
    for l in _LOCKS.values(): l.save()


class Claims:
    """The new NPCs of one run (the files and mods compiled together), in load order: a screen of the game fills its free
    slots in order (`backend.new_slot_entry`), so the second new NPC of a screen takes the slot after the first, whichever
    file or mod declared it; and each new NPC's talk section, so that two NPCs of one script never answer on the same one."""
    def __init__(self):
        self.slots = {}           # screen -> [key] (key: (file, NPC variable))
        self.sections = {}        # script -> {section: key}
        self.section_of = {}      # key -> (section, why or None)

    def slot(self, screen, key, first=None):
        """The slot of the NPC `key` on `screen`: the screen's first free one (`first`: 0 on a screen of the mod's own) plus the
        new NPCs claimed there before it."""
        lst = self.slots.setdefault(screen, [])
        if key not in lst: lst.append(key)
        return (BE.next_free_slot(screen) if first is None else first) + lst.index(key)

    def talk_section(self, sid, screens, slot, key):
        """The talk section of a new slot: 5 + slot (the game's numbering), unless an NPC of another screen of the same script
        answers on it (script 168 serves the two arena lobbies: slot 1 is free on 208 and Airdramon's on 223) or another new
        NPC of this run does; then the first section 5-50 that no NPC of the script uses and the script does not have.
        -> (section, why it is not 5 + slot, or None)"""
        if key in self.section_of: return self.section_of[key]
        mine = self.sections.setdefault(sid, {})
        used = {}
        for s in N.disc_screens()[1].get(sid, screens):
            for d in BE.screen_slots(s):
                used.setdefault(d['entity'], (s, d))
        want = 5 + slot
        if want not in used and want not in mine: n, why = want, None
        else:
            have = script_sections(sid)
            n = next((k for k in range(5, 51) if k not in used and k not in mine and k not in have), None)
            if n is None: raise PyError(f'script {sid}: no free talk section (5-50) for a new NPC', None)
            if want in used:
                s, d = used[want]
                nm = next((x for x, (e, _) in base_npcs(sid).items() if e == want), None)
                sp = N.enum_members('species').get(d['species'], d['species'])
                why = f'section {want} is {nm or sp}\'s, slot {d["slot"]} of screen {s}'
            else:
                why = f'section {want} is a new NPC\'s of another screen of script {sid}'
        mine[n] = key; self.section_of[key] = (n, why)
        return n, why


def script_sections(sid):
    """The section numbers script `sid` of story/base has (its view's `sections(...)`)."""
    return N.script_sections(sid)


_BASE_NPCS = {}


def base_npcs(sid):
    """{name: (entity, species id)} of a base script, as the view and its stub name them."""
    if sid not in _BASE_NPCS:
        from . import stubs
        names = stubs.base_names()
        _BASE_NPCS[sid] = {nm: (e, sp) for e, nm, sp in stubs.base_npcs(sid, names)}
    return _BASE_NPCS[sid]


def enum_ids(kind):
    """{member: id} of Species/Item/Tech."""
    return {m: i for i, m in N.enum_members(kind).items()}


class Handler:
    def __init__(self, kind, arg, fn, node, scene=False, when=None, target=None):
        self.kind, self.arg, self.fn, self.node, self.scene, self.when, self.target = kind, arg, fn, node, scene, when, target


class Module:
    """One `.py` file: its declarations and handlers, lowered."""

    def __init__(self, path, src=None, base=None, claims=None):
        self.path = path
        self.claims = claims if claims is not None else Claims()     # the new NPCs of the run (slots, talk sections)
        self.notes = []            # what `check` says besides errors (a new NPC's talk section that is not 5 + slot)
        self.src = open(path, encoding='utf-8').read() if src is None else src
        from ..diag import SOURCES
        SOURCES[path] = self.src.split('\n')
        try:
            self.tree = ast.parse(self.src, path)
        except SyntaxError as e:
            raise PyError(f'not valid Python: {e.msg}', (path, e.lineno or 1, e.offset or 1))
        self.screens = {}          # var -> {'ids': [screen ids], 'script': sid, 'new': bool, 'map': str}
        self.npcs = {}             # var -> {'screen': var, 'slot': k, 'species': id|None, 'entity': n, 'kw': {...}}
        self.aliases = {}          # var -> text key prefix ('s077.sec5')
        self.consts = {}           # var -> ast node (compile-time constants)
        self.handlers = []         # Handler
        self.shared = {}           # def name -> FunctionDef (parameterless, undecorated)
        self.fns = {}              # def name -> FunctionDef with parameters (inlined)
        self.order = None          # sections(...) entries
        self.sid = None
        self.base = base
        self.hatch_shared = set()  # `shared L:` labels inside dws(...) blocks of this file
        self.quests = {}           # class name -> {'stages': [names], 'bits': k}
        self.flags = {}            # flag() names; self.vars: counter() names
        self.vars = {}
        self.texts = {}            # key -> new text of this file (a mod's lines: key = <mod>.<sha1 of the text>[:8])
        self.text_where = {}       # key -> 'file:handler' (for `text sync`: an edited line keeps its translation, marked ~fuzzy)
        self.text_info = {}        # key -> {path, line, col, handler, kind ('line'|'option'), who, page, of, option}: in source order
        self.named = {}            # '<mod>:<name>' -> the English of a named line (t("name"): the mod's text/en.json)
        self.named_used = set()    # the names t(...) used in this file
        self._en = None            # the mod's text/en.json (read once)
        self.deps = []             # sibling modules this one imports (their declarations are imported in DWS)
        self.dep_decls = set()     # the deps that declare saved state (a file of constants only has no declarations file)
        self.unresolved = set()    # names an import could not give (their uses are not reported again)
        self.own_decls = set()     # names declared in this file (quests' bits, flags, counters)
        self.errors = []           # every error of the file (raised together at the end: lower_file)
        self.temps = set()         # scratch variables the lowering needs (`temp var`)
        self.aliases_dws = set()   # `alias flag` lines the lowering needs (the shop stock)
        self.story_state = []            # (node, message, hint): forms only the story-state engine runs (engine_errors reports them)
        self.imported = []         # (node, species id): a test of the partner against an imported species (--exe species/story-state)
        m = re.search(r'story[/\\]mods[/\\]([^/\\]+)[/\\]', os.path.abspath(path))
        self.mod = m.group(1) if m else None
        self.mod_dir = os.path.abspath(path)[:m.end() - 1] if m else None      # story/mods/<mod>: its mod.toml and save.lock
        self.module = re.sub(r'\W', '_', self.mod) if self.mod else None
        self.mode = 'base' if base else ('mod' if self.mod else 'plain')

    def en_json(self):
        """The mod's text/en.json (named lines and the snapshot of `text sync`), read once; {} without one."""
        if self._en is None:
            p = os.path.join(self.mod_dir or '', 'text', 'en.json')
            try: self._en = json.load(open(p, encoding='utf-8')) if self.mod_dir and os.path.exists(p) else {}
            except ValueError as e: raise PyError(f'cannot read {os.path.relpath(p)}: {e}', (p, 1, 1))
        return self._en

    # ------------------------------------------------------------ errors
    def err(self, node, msg, hint=None):
        if isinstance(node, ast.match_case): node = node.pattern          # (a `case` has no position of its own: its pattern has)
        return PyError(msg, (self.path, getattr(node, 'lineno', 1), getattr(node, 'col_offset', 0) + 1), hint)

    # ------------------------------------------------------------ module level
    def read(self):
        for st in self.tree.body:
            try:
                self.top(st)
            except PyError as e:
                self.errors.append(e)
        for h in self.handlers:
            self.scan_hatches(h.fn)
        for f in self.shared.values():
            self.scan_hatches(f)
        return self

    def scan_hatches(self, fn):
        for n in ast.walk(fn):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'dws' and n.args and isinstance(n.args[0], ast.Constant):
                for m in re.finditer(r'\bshared\s+(\w+)\s*:', n.args[0].value): self.hatch_shared.add(m.group(1))

    def top(self, st):
        if isinstance(st, ast.ImportFrom):
            mod = ('.' * st.level) + (st.module or '')
            if st.level == 0 and mod not in ROOTS and not mod.startswith('dw.base.'):
                raise self.err(st, f'import from "{mod}": a story file imports only from dw, dw.text, dw.names, dw.base.* and its own mod',
                               'from dw import *')
            if mod.startswith('dw.base.'): self.import_base(st, mod)
            if st.level >= 1: self.import_sibling(st)
            return
        if isinstance(st, ast.Import):
            raise self.err(st, 'plain `import` is not part of the story language', 'from dw import *')
        if isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant) and isinstance(st.value.value, str):
            return                                            # a docstring
        if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name):
            return self.assign(st.targets[0].id, st.value, st)
        if isinstance(st, ast.Expr) and isinstance(st.value, ast.Call) and isinstance(st.value.func, ast.Name) and st.value.func.id == 'sections':
            self.order = []
            for a in st.value.args:
                if isinstance(a, ast.Constant) and isinstance(a.value, int): self.order.append((a.value, None))
                elif isinstance(a, ast.Tuple) and len(a.elts) == 2 and isinstance(a.elts[0], ast.Constant) and isinstance(a.elts[1], ast.Name):
                    self.order.append((a.elts[0].value, a.elts[1].id))
                else: raise self.err(a, 'sections(...) takes section ids and (id, shared_def) pairs')
            return
        if isinstance(st, ast.FunctionDef):
            return self.funcdef(st)
        if isinstance(st, ast.ClassDef):
            return self.mod_class(st)
        what = {'Expr': 'a statement', 'If': 'an `if`', 'For': 'a `for` loop', 'While': 'a `while` loop', 'AugAssign': 'an assignment',
                'AnnAssign': 'an annotated assignment', 'Match': 'a `match`', 'Assign': 'this assignment'}.get(type(st).__name__, type(st).__name__)
        raise self.err(st, f'{what} is not allowed at the top of a story file',
                       'the top of a file declares screens, NPCs, quests, flags, constants and handlers (`@npc.on_talk def ...`)')

    def import_base(self, st, mod):
        """`from dw.base.native_forest_2 import forest, palmon`: a screen or an NPC of the base story, by the screen's module
        (named like its Screen member). A handler on them is guarded (`when=`), or the NPC is owned with `take_over`."""
        name = mod[len('dw.base.'):]
        inv = {m: i for i, m in N.screen_members().items()}
        _, by = N.disc_screens()
        script_of = {scr: sid for sid, ss in by.items() for scr in ss}
        m = re.fullmatch(r's(\d+)', name)
        if name not in inv or inv[name] not in script_of:
            hint = 'the modules are named like the screens (Screen.x): from dw.base.jijimons_house import house, jijimon'
            if m and by.get(int(m.group(1))):
                hint = f'script {int(m.group(1))} is screen ' + ' / '.join(f'dw.base.{N.screen_members()[x]}' for x in by[int(m.group(1))])
            raise self.err(st, f'no module {mod}', hint)
        home = inv[name]; sid = script_of[home]
        scr = {var: s for s, var in N.screen_vars(sid)}
        npcs = base_npcs(sid)
        for al in st.names:
            nm = al.name
            if nm in scr: self.screens[al.asname or nm] = {'ids': [scr[nm]], 'script': sid, 'new': False, 'map': None, 'base': True}
            elif nm in npcs:
                e, sp = npcs[nm]
                at, k = N.npc_home(sid, e, home)          # (a script of several screens: the screen whose .MAP has it)
                self.npcs[al.asname or nm] = {'screen': None, 'slot': k, 'species': sp, 'entity': e, 'kw': {},
                                              'base': True, 'script': sid, 'home': at, 'name': nm}
            else: raise self.err(st, f'{mod} (script {sid}) has no screen or NPC "{nm}"',
                                 'its names: ' + ', '.join(list(scr) + list(npcs)))
            if self.sid is None: self.sid = sid
            elif self.sid != sid: raise self.err(st, f'one file is one script: {self.sid} and {sid} (split the file)')

    def import_sibling(self, st):
        """`from .quests import Horn, invited`: quests, flags, counters and constants of another file of the mod
        (`from ..story.state import x`: of a file in another folder of the same mod)."""
        d = os.path.dirname(os.path.abspath(self.path))
        for _ in range(st.level - 1): d = os.path.dirname(d)
        if st.level > 1 and not (self.mod_dir and (d + os.sep).startswith(self.mod_dir + os.sep) or d == self.mod_dir):
            raise self.err(st, 'an import leaves the mod\'s folder: a story file imports from its own mod',
                           'from .quests import Horn (the same folder), from ..story.state import x (another folder of the mod)')
        p = os.path.join(d, *st.module.split('.')) + '.py'
        if not os.path.exists(p): raise self.err(st, f'no file {os.path.relpath(p, ROOT)}')
        other = Module(p, claims=self.claims).read()
        want = None if any(a.name == '*' for a in st.names) else {a.name for a in st.names}
        for table in ('quests', 'flags', 'vars', 'consts'):
            for k, v in getattr(other, table).items():
                if want is None or k in want: getattr(self, table)[k] = v
        self.deps.append(p)
        if other.own_decls: self.dep_decls.add(p)
        missing = (want or set()) - set(other.quests) - set(other.flags) - set(other.vars) - set(other.consts)
        if missing:
            self.unresolved |= missing
            f = os.path.basename(p)
            kinds = [(f'{x} is an NPC of {f}' if x in other.npcs else f'{x} is a screen of {f}' if x in other.screens
                      else f'{x} is a def of {f}' if x in other.shared or x in other.fns else f'{f} has no {x}') for x in sorted(missing)]
            raise self.err(st, '; '.join(kinds), 'a file imports another\'s quests, flags, counters and constants; an NPC stays in '
                           'the file of its screen, with its handlers, and a def is used in the file that has it')

    def assign(self, name, v, st):
        if name in N.RESERVED and self.mode != 'base':
            raise self.err(st, f'`{name}` is a name of the story language: a name of yours would hide it',
                           f'call it something else ({name}_done, my_{name}...)')
        if isinstance(v, ast.Call):
            f = v.func
            if isinstance(f, ast.Name) and f.id == 'screen': return self.screen(name, v)
            if isinstance(f, ast.Name) and f.id == 'new_screen': return self.screen(name, v, new=True)
            if isinstance(f, ast.Name) and f.id == 'take_over': return self.take_over(name, v)
            if isinstance(f, ast.Name) and f.id == 'script':
                n = self.int_const(v.args[0]) if v.args else None
                self.screens[name] = {'ids': [], 'script': n, 'new': False, 'map': None}; self.set_sid(n, v); return
            if isinstance(f, ast.Attribute) and f.attr == 'npc' and isinstance(f.value, ast.Name) and f.value.id in self.screens:
                return self.npc(name, f.value.id, v)
            if isinstance(f, ast.Attribute) and f.attr == 'npc' and isinstance(f.value, ast.Call):
                raise self.err(v, 'name the screen first: an NPC belongs to a screen variable',
                               f'house = screen(Screen.x), then {name} = house.npc(...) (its handlers need both names)')
            if isinstance(f, ast.Name) and f.id == 'entity' and len(v.args) == 1:
                self.npcs[name] = {'screen': None, 'slot': None, 'species': None, 'entity': self.int_const(v.args[0]), 'kw': {}}; return
            if isinstance(f, ast.Name) and f.id in ('flag', 'counter'): return self.mod_state(name, f.id, v)
        if isinstance(v, ast.Attribute):
            key = self.text_path(v)
            if key is not None: self.aliases[name] = key; return
        self.consts[name] = v

    def text_path(self, v):
        parts = []
        while isinstance(v, ast.Attribute): parts.append(v.attr); v = v.value
        if isinstance(v, ast.Name) and v.id == 'text': return '.'.join(reversed(parts))
        if isinstance(v, ast.Name) and v.id in self.aliases: return '.'.join([self.aliases[v.id]] + list(reversed(parts)))
        return None

    def screen(self, name, v, new=False):
        """`screen(Screen.x)`: a screen of the game; `new_screen(N, map="...")`: a screen of the mod's own."""
        ids = [self.screen_id(a) for a in v.args]
        kw = {k.arg: k.value for k in v.keywords}
        if 'new' in kw: raise self.err(v, 'screen(...) names a screen of the game', f'a new screen is new_screen({ids[0] if ids else "N"}, map="...")')
        if 'map' in kw and not new: raise self.err(v, 'map= is for a new screen', 'new_screen(N, map="build/<mod>/maps/NAME.MAP")')
        if new and len(ids) != 1: raise self.err(v, 'new_screen(N, map="...") makes one screen')
        mp = kw['map'].value if isinstance(kw.get('map'), ast.Constant) else None
        sid = None
        if not new:
            _, by = N.disc_screens()
            inv = {s: k for k, ss in by.items() for s in ss}
            sids = {inv.get(i) for i in ids}
            if None in sids: raise self.err(v, f'screen {ids}: no script of the game loads it', 'a new screen is new_screen(N, map=...)')
            if len(sids) != 1: raise self.err(v, f'screens {ids} load different scripts ({sorted(sids)}): one screen(...) each')
            sid = sids.pop(); self.set_sid(sid, v)
        self.screens[name] = {'ids': ids, 'script': sid, 'new': new, 'map': mp, 'node': v}

    def set_sid(self, sid, node):
        if self.sid is not None and sid is not None and self.sid != sid and self.base:
            raise self.err(node, f'a view of the base is one script: {self.sid} and {sid}')
        if self.sid is None: self.sid = sid

    def screen_id(self, a):
        if isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name) and a.value.id == 'Screen':
            inv = {m: i for i, m in N.screen_members().items()}
            if a.attr not in inv: raise self.err(a, f'no screen "{a.attr}"')
            return inv[a.attr]
        return self.int_const(a)

    def int_const(self, a):
        if isinstance(a, ast.Constant) and isinstance(a.value, int) and not isinstance(a.value, bool): return a.value
        if isinstance(a, ast.UnaryOp) and isinstance(a.op, ast.USub): return -self.int_const(a.operand)
        if isinstance(a, ast.Name) and a.id in self.consts: return self.int_const(self.consts[a.id])
        raise self.err(a, 'a whole number is expected here')

    def npc(self, name, scr, v):
        """`x = house.npc(Species.X, at=..., ...)`: a new NPC in the screen's next free slot (in the order the files and mods of
        the run declare them: Claims); `slot=` may say it, and must be that one. A view (the base) names the slot it prints."""
        if not v.args: raise self.err(v, 'npc(Species.X | None, at=(x, z), ...)')
        if self.mode == 'mod' and self.npcs.get(name, {}).get('base'):
            raise self.err(v, f'{name} is the base\'s NPC imported above: a new NPC needs a name of its own',
                           f'{name}_2 = ..., or own the base\'s: x = take_over({name})')
        sp = None if isinstance(v.args[0], ast.Constant) and v.args[0].value is None else self.enum_id('species', v.args[0])
        kw = {k.arg: k.value for k in v.keywords}
        sc = self.screens[scr]
        game = not sc['new'] and bool(sc['ids'])
        if 'slot' not in kw and (self.mode != 'mod' or not game and not sc['new']):
            raise self.err(v, 'an NPC is in a slot of its screen: npc(Species.X, slot=k)')
        given = self.int_const(kw['slot']) if 'slot' in kw else None
        key = (os.path.abspath(self.path), name)
        if self.mode != 'mod' or not game:
            slot = given if given is not None else self.claims.slot(('new', sc['ids'][0]), key, first=0)    # (a new screen: in order)
        else:
            free = {i: self.claims.slot(i, key) for i in sc['ids']}
            slot = free[sc['ids'][0]]
        self.renamed(kw)
        if 'behaves_like' in kw:
            o = kw['behaves_like']
            d = self.npcs.get(o.id) if isinstance(o, ast.Name) else None
            if d is None or d['slot'] is None: raise self.err(o, 'behaves_like= takes an NPC of this screen (behaves_like=tokomon)')
            if d.get('base') and game and d.get('home') not in sc['ids']:
                raise self.err(o, f'{o.id} stands on screen {d["home"]}, not on this one: behaves_like= takes an NPC of this screen',
                               f'python3 tools/dws.py slots {sc["ids"][0]} lists them')
            kw['like_slot'] = ast.Constant(d['slot'])
        for sid_ in (sc['ids'] if self.mode == 'mod' and game and given is not None else []):      # every screen of screen(a, b, ...)
            used = next((d for d in BE.screen_slots(sid_) if d['slot'] == given), None)
            if used is not None:
                base = next((nm for nm, (e, _) in base_npcs(sc['script']).items() if e == used['entity']), None)
                sp_name = N.enum_members('species').get(used['species'], used['species'])
                where = 'this screen' if len(sc['ids']) == 1 else f'screen {sid_} (Screen.{N.screen_members()[sid_]})'
                raise self.err(v, f'slot {given} of {where} is taken: {sp_name}' + (f' ({base} in the base)' if base else ''),
                               (f'to own it: {name} = take_over({base}, species=...) (imported from dw.base.{N.screen_members()[sid_]}); '
                                if base else '') + f'a new NPC goes in slot {slot}: leave slot= out '
                               f'(python3 tools/dws.py slots {sid_})')
        if self.mode == 'mod' and game and len(set(free.values())) > 1:
            raise self.err(v, f'one npc() on several screens takes the same new slot on each, and here it differs: '
                              + ', '.join(f'screen {i}: slot {k}' for i, k in free.items()),
                           'one screen(...) and one npc() per screen')
        if self.mode == 'mod':
            twin = next((nm for nm, d in self.npcs.items() if not d.get('base') and d.get('screen') is not None
                         and set(self.screens[d['screen']]['ids']) & set(sc['ids']) and d['slot'] == (slot if given is None else given)), None)
            if twin: raise self.err(v, f'slot {given if given is not None else slot} of this screen is already {twin} (line '
                                       f'{self.npcs[twin]["node"].lineno})', 'leave slot= out: a new NPC takes the next free slot')
        if self.mode == 'mod' and game and given is not None and given != slot:
            others = len(self.claims.slots[sc['ids'][0]]) > 1          # (said, and the NPC is declared in its slot: no cascade)
            self.errors.append(self.err(kw['slot'], f'screen {sc["ids"][0]} has {BE.next_free_slot(sc["ids"][0])} placed Digimon; this new NPC goes in '
                                       f'slot {slot} (slots are filled in order' + (', the new NPCs of the files and mods compiled '
                                       'together in their order' if others else '') + ')',
                           'leave slot= out: the compiler takes the next free one'))
        if self.mode == 'mod':
            if 'at' not in kw and not sc['new']:
                raise self.err(v, 'a new NPC needs at=(x, z): where it stands on the screen',
                               f'python3 tools/dws.py slots {sc["ids"][0] if sc["ids"] else "SCREEN"} lists the positions of the NPCs there')
        if self.mode == 'mod' and game and 'behaves_like' not in kw and BE.map_source(sc['ids'][0]):
            import dwmap
            mf = dwmap.MapFile(open(os.path.join(ROOT, BE.map_source(sc['ids'][0])), 'rb').read())
            k = BE.template_slot(mf)                    # (said when no NPC walks a path there: the stub's rule does not apply)
            if k is not None and not any(a in (1, 2) for a in mf.digimon[k]['aiSections']):
                d = mf.digimon[k]
                nm = next((x for x, (e, _) in base_npcs(sc['script']).items() if e == d['scriptId']), None)
                self.notes.append(f'{self.path}:{v.lineno}: note: {name} behaves like the .MAP\'s slot {k} '
                                  f'({N.enum_members("species").get(d["type"], d["type"])}' + (f', {nm}' if nm else '')
                                  + ': no NPC walks a path here, so the last slot); behaves_like= picks another')
        if not game: ent = 5 + slot
        elif self.mode != 'mod' or any(d['slot'] == slot for d in BE.screen_slots(sc['ids'][0])):
            ent = BE.slot_entity(sc['ids'][0], slot)                  # the .MAP slot's script id
        else:
            ent, why = self.claims.talk_section(sc['script'], sc['ids'], slot, key)
            if why:
                self.notes.append(f'{self.path}:{v.lineno}: note: {name} (slot {slot} of screen {sc["ids"][0]}) answers on talk section {ent}: {why}')
        self.npcs[name] = {'screen': scr, 'slot': slot, 'species': sp, 'entity': ent, 'kw': kw, 'node': v}

    RENAMED = {'appears': 'when', 'like_slot': 'behaves_like', 'off': 'offense', 'exit': 'entry', 'ticks': None}

    def renamed(self, kw):
        """A keyword the language renamed (2026-10-13): the error says the new one."""
        for k, v in list(kw.items()):
            if k in self.RENAMED and k not in ('exit', 'ticks'):
                hint = {'like_slot': 'behaves_like=<an NPC of the screen> (it copies that NPC\'s behaviour, range, stats and path)'}.get(k)
                self.errors.append(self.err(v, f'{k}= is now {self.RENAMED[k]}=', hint))     # (reported; the NPC is still declared)
                del kw[k]

    def take_over(self, name, v):
        """`jiji = take_over(jijimon)`: the mod owns a base NPC: its talk is the mod's handlers (the base's no longer runs).
        `species=`, `at=` and the stats change what stands in the slot (a species swap)."""
        if len(v.args) != 1 or not isinstance(v.args[0], ast.Name) or not self.npcs.get(v.args[0].id, {}).get('base'):
            raise self.err(v, 'take_over(npc): an NPC of the base, imported from its screen (from dw.base.jijimons_house import jijimon)')
        if self.mode != 'mod': raise self.err(v, 'take_over is for mods: a mod\'s files live in story/mods/<mod>/src/')
        b = self.npcs[v.args[0].id]
        kw = {k.arg: k.value for k in v.keywords}
        self.renamed(kw)
        bad = [k for k in kw if k not in ('species', 'at', 'hp', 'mp', 'offense', 'defense', 'speed', 'brain', 'bits')]
        if bad: raise self.err(v, f'take_over(...) takes species=, at= and the stats, not {", ".join(bad)}=',
                               'when it is there is the base\'s to decide (its screen setup)')
        if b['slot'] is None: raise self.err(v, f'{v.args[0].id} is in no .MAP slot of this screen: nothing to take over')
        sp = self.enum_id('species', kw['species']) if 'species' in kw else b['species']
        self.npcs[name] = {'screen': None, 'screen_id': b['home'], 'slot': b['slot'], 'species': sp, 'entity': b['entity'], 'kw': kw,
                           'node': v, 'taken': v.args[0].id, 'script': b['script']}
        self.set_sid(b['script'], v)

    def enum_id(self, kind, a):
        enum = {'species': 'Species', 'item': 'Item', 'tech': 'Tech'}[kind]
        if isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name) and a.value.id == enum:
            ids = enum_ids(kind)
            if a.attr not in ids:
                former = next((v for k, v in N.former_names().items() if k.lower() == a.attr.lower()), None) if kind == 'species' else None
                if former:
                    names = list(dict.fromkeys(N.enum_members('species')[i] for i in former if i in N.enum_members('species')))
                    names = [n for n in names if not re.fullmatch(r'.*\D\d+', n)] or names      # (Greymon129: another entry of the same)
                    others = [m for m in ids if m.startswith(a.attr) and m not in names and not re.fullmatch(r'.*\d', m)]
                    raise self.err(a, f'no species "{a.attr}": it was renamed ' + ' / '.join(f'Species.{n}' for n in names)
                                   + (f' (also: {", ".join(f"Species.{o}" for o in others)})' if others else ''),
                                   'the renames are in content/species (each file\'s "_former_name")')
                near = difflib.get_close_matches(a.attr, list(ids), 1)
                raise self.err(a, f'no {kind} "{a.attr}"' + (f' (did you mean {enum}.{near[0]}?)' if near else ''))
            return ids[a.attr]
        if isinstance(a, ast.Call) and isinstance(a.func, ast.Name) and a.func.id == enum and len(a.args) == 1: return self.int_const(a.args[0])
        if isinstance(a, ast.Name) and a.id in self.consts: return self.enum_id(kind, self.consts[a.id])
        raise self.err(a, f'a {enum} is expected here ({enum}.X)')

    def funcdef(self, st):
        if st.args.args or st.args.posonlyargs or st.args.kwonlyargs or st.args.vararg or st.args.kwarg:
            if st.decorator_list: raise self.err(st, 'a handler takes no parameters')
            if st.args.posonlyargs or st.args.kwonlyargs or st.args.vararg or st.args.kwarg:
                raise self.err(st, 'story functions take plain parameters, with optional defaults',
                               'write `def reward(amount=10):`, without `/`, `*` or `**`')
            self.fns[st.name] = st; return
        if not st.decorator_list:
            if self.mode == 'mod' and speaks(st):          # (it speaks as the NPC being talked to: inlined in each talk that calls it)
                self.fns[st.name] = st; return
            self.shared[st.name] = st; return
        if len(st.decorator_list) != 1: raise self.err(st, 'one decorator per handler')
        d = st.decorator_list[0]
        call = d if isinstance(d, ast.Call) else None
        target = call.func if call else d
        kw = {k.arg: k.value for k in call.keywords} if call else {}
        args = call.args if call else []
        if isinstance(target, ast.Name) and target.id == 'hook':
            return self.handlers.append(Handler('maphead', self.int_const(args[0]), st, d))
        if not isinstance(target, ast.Attribute): raise self.err(d, 'a handler is `@npc.on_talk`, `@screen.on_enter`, `@screen.on_step(t)`...')
        obj, meth = target.value, target.attr
        scene = isinstance(kw.get('scene'), ast.Constant) and kw['scene'].value is True
        when = kw.get('when')
        if meth == 'on_load':
            if not (isinstance(obj, ast.Call) and isinstance(obj.func, ast.Name) and obj.func.id == 'screen' and len(obj.args) == 1) \
                    and not (isinstance(obj, ast.Name) and obj.id in self.screens):
                raise self.err(d, '@screen(Screen.x).on_load')
            sc = self.screen_id(obj.args[0]) if isinstance(obj, ast.Call) else self.screens[obj.id]['ids'][0]
            return self.handlers.append(Handler('maphead', sc, st, d, when=when))
        if not isinstance(obj, ast.Name): raise self.err(d, 'the handler belongs to an NPC or a screen variable')
        if scene and meth != 'on_talk':
            raise self.err(d, '`scene=True` only works on on_talk: the game reads it (trigger 44) at the first box of a conversation',
                           'leave it out: on_enter, on_step and on_use never turn the NPC')
        if obj.id in self.unresolved: return                   # (its import failed, and said why)
        if meth not in ('on_talk', 'on_enter', 'on_step', 'on_use', 'section'):
            import difflib
            near = difflib.get_close_matches(meth, ['on_talk', 'on_enter', 'on_step', 'on_use', 'on_load'], 1)
            raise self.err(d, f'unknown handler "{meth}"' + (f' (did you mean {near[0]}?)' if near else ''),
                           'on_talk, on_enter, on_step(t), on_use(t), section(n), on_load')
        if meth == 'on_talk':
            if obj.id not in self.npcs: raise self.err(obj, f'"{obj.id}" is not an NPC of this file')
            return self.handlers.append(Handler('talk', obj.id, st, d, scene, when, target=obj.id))
        if obj.id not in self.screens: raise self.err(obj, f'"{obj.id}" is not a screen of this file')
        if meth == 'on_enter': return self.handlers.append(Handler('enter', None, st, d, scene, when, target=obj.id))
        if meth in ('on_step', 'on_use', 'section'):
            if not args: raise self.err(d, f'@{obj.id}.{meth}(n)')
            if meth in ('on_step', 'on_use') and self.mode == 'mod': self.check_tile(meth, self.int_const(args[0]), obj.id, args[0])
            return self.handlers.append(Handler({'on_step': 'step', 'on_use': 'use', 'section': 'section'}[meth], self.int_const(args[0]), st, d,
                                                scene, when, target=obj.id))
        raise self.err(d, f'unknown handler "{meth}"', 'on_talk, on_enter, on_step(t), on_use(t), section(n), on_load')

    def check_tile(self, meth, t, scr, node):
        """`on_step(t)` / `on_use(t)` on a screen of the game: its .MAP must have that trigger (collision value 51 + t / 80 + t),
        or the handler never runs."""
        sc = self.screens.get(scr)
        if not sc or sc['new'] or not sc['ids']: return
        tiles = map_triggers(sc['ids'][0])
        if tiles is None: return
        lo, hi = (51, 79) if meth == 'on_step' else (80, 109)
        if not lo <= lo + t <= hi: return                              # (the back end says the range)
        have = sorted(v - lo for v in tiles if lo <= v <= hi)
        if t not in have:
            kind = 'step' if meth == 'on_step' else 'use'
            raise self.err(node, f'screen {sc["ids"][0]} has no {kind} trigger {t}: its map triggers ' +
                           (f'{kind} ' + ', '.join(map(str, have)) if have else f'no {kind} tile'),
                           f'python3 tools/dws.py slots {sc["ids"][0]} lists them with where they are')

    def check_entry(self, screen, k, node):
        """`warp(screen, entry=k)`: the screen's .MAP has that entry."""
        import dwmap
        src = BE.map_source(screen)
        if not src: return
        m = map_file(screen)
        used = [i for i, w in enumerate(m.warps) if dwmap.warp_used(w)]
        if k not in used:
            raise self.err(node, f'screen {screen} has no entry {k}: its entries are ' + ', '.join(map(str, used)),
                           f'python3 tools/dws.py slots {screen} lists them with where the tamer arrives')

    # mod-only forms (milestone 4b): quests, flags, counters
    def mod_class(self, st):
        """class Horn(Quest): NONE = auto(); ASKED = auto() ...: the stage number in ceil(log2 n) flags (Horn_b0, Horn_b1...)."""
        if not (len(st.bases) == 1 and isinstance(st.bases[0], ast.Name) and st.bases[0].id == 'Quest') or st.keywords or st.decorator_list:
            raise self.err(st, 'a class is a quest: class Name(Quest): with its stages')
        stages = []
        for x in st.body:
            if isinstance(x, ast.Expr) and isinstance(x.value, ast.Constant) and isinstance(x.value.value, str): continue
            if isinstance(x, ast.Assign) and len(x.targets) == 1 and isinstance(x.targets[0], ast.Name) and isinstance(x.value, ast.Call) \
                    and isinstance(x.value.func, ast.Name) and x.value.func.id == 'auto' and not x.value.args:
                stages.append(x.targets[0].id); continue
            raise self.err(x, 'a quest lists its stages in order: NAME = auto()')
        if len(stages) < 2: raise self.err(st, 'a quest has at least two stages')
        bits = max(1, (len(stages) - 1).bit_length())
        self.quests[st.name] = {'stages': stages, 'bits': bits, 'node': st}
        for j in range(bits): self.own_decls.add(f'{st.name}_b{j}')

    def mod_state(self, name, kind, v):
        if v.args or v.keywords: raise self.err(v, f'{kind}() takes nothing: its name is the variable\'s')
        (self.flags if kind == 'flag' else self.vars)[name] = v; self.own_decls.add(name)

    def stage_index(self, q, node):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == q and node.attr in self.quests[q]['stages']:
            return self.quests[q]['stages'].index(node.attr)
        raise self.err(node, f'a stage of {q} is expected: ' + ', '.join(f'{q}.{x}' for x in self.quests[q]['stages']))

    def stage_tree(self, q, pred, i):
        """The stages v with pred(v, i), as the smallest sum of products over the quest's bits (the stage numbers past the
        last stage are free)."""
        d = self.quests[q]; k = d['bits']; n = len(d['stages'])
        on = [v for v in range(n) if pred(v, i)]; dc = list(range(n, 1 << k))
        if not on: raise PyError(f'quest {q}: no stage matches this condition', None)
        if len(on) == n: raise PyError(f'quest {q}: every stage matches this condition (it is always true)', None)
        prods = minimal_cover(on, dc, k)
        lit = lambda j, b: f'{q}_b{j}' if b else f'!{q}_b{j}'
        terms = []
        for p in prods:
            ls = [('lit', lit(j, b)) for j, b in sorted(p.items())]
            terms.append(ls[0] if len(ls) == 1 else ('and', ls))
        return terms[0] if len(terms) == 1 else ('or', terms)

    # ------------------------------------------------------------ lowering
    def check_owning(self):
        """take_over: the taken NPC answers with this file's handlers (and only them); added handlers do not end the
        screen's own code early."""
        for name, d in self.npcs.items():
            if not d.get('taken'): continue
            if not any(h.kind == 'talk' and h.arg == name for h in self.handlers):
                self.errors.append(self.err(d['node'], f'{name} = take_over({d["taken"]}) owns its talk, but no handler answers it',
                                            f'add @{name}.on_talk (a species swap needs words of its own: the base\'s talk would '
                                            f'not match the new species)'))
            for h in self.handlers:
                if h.kind == 'talk' and h.arg == d['taken']:
                    self.errors.append(self.err(h.node, f'{d["taken"]} is taken over as {name}: write its handlers on {name}'))
        for h in self.handlers:
            if h.kind in ('enter', 'step', 'use') and not self.owned(h) and self.mode == 'mod':
                for n in ast.walk(h.fn):
                    if isinstance(n, ast.Return):
                        self.errors.append(self.err(n, f'`return` in a handler added to the base\'s on_{h.kind} ends the screen\'s '
                                                       f'section: the base\'s own {h.kind} code (its setup) would not run',
                                                    'use if/else; a warp() ends the handler by itself'))

    def lower(self):
        """-> (script DWS text or None, MAPHEAD DWS text or None, declarations DWS text or None)"""
        self.check_owning()
        imports = [import_line(p) for p in CORE]
        names_dws = os.path.abspath(os.path.join(self.base or os.path.join(ROOT, 'story', 'base'), 'names.dws'))
        if os.path.exists(names_dws): imports.append(import_line(names_dws))
        head_mod = [f'module {self.module};'] if self.module else []
        decl = self.decls()
        if decl: imports.append(import_line(lowered_path(self.path, "decl")))
        for d in self.deps:
            if d in self.dep_decls: imports.append(import_line(lowered_path(d, "decl")))     # (constants only: nothing to import)
        script = []; mh = []
        evs = [h for h in self.handlers if h.kind != 'maphead']
        mhs = [h for h in self.handlers if h.kind == 'maphead']
        is_mh = bool(mhs) and not evs and not any(s['script'] is not None or s['new'] for s in self.screens.values())
        top = self.mod_top()                          # place(...) and the presence rules of the mod's NPCs
        new = [v for v in self.screens.values() if v['new']]
        if evs or (self.shared and not is_mh) or (self.order and not is_mh):
            if new:
                if len(new) > 1 or len(self.screens) > 1: raise PyError('a new screen is a file of its own (one script)', (self.path, 1, 1))
                script.append(f'script new for screen {new[0]["ids"][0]} empty {{')
            else:
                if self.sid is None and not evs and self.shared:
                    raise PyError(f'{", ".join(self.shared)}: a def is used in the file that has it, and this file has no screen',
                                  (self.path, self.shared[next(iter(self.shared))].lineno, 1),
                                  'move it into the file of the screen whose handlers call it (a file imports another\'s quests, '
                                  'flags, counters and constants only)')
                if self.sid is None: raise PyError('no screen(...) or script(...) says which script this is', (self.path, 1, 1))
                script.append(f'script {self.sid} {{')
            script += self.npc_decls('    ')
            if self.order: script.append('    sections ' + ', '.join(str(n) if nm is None else f'{n} as {nm}' for n, nm in self.order) + ';')
            for key, hs in self.groups(evs): script += self.guarded(self.events, key, hs)
            for name, fn in self.shared.items(): script += self.shared_block(name, fn)
            script.append('}')
        if mhs or is_mh:
            mh.append('maphead {')
            mh += self.npc_decls('    ')
            if self.order and is_mh: mh.append('    sections ' + ', '.join(str(n) if nm is None else f'{n} as {nm}' for n, nm in self.order) + ';')
            for key, hs in self.groups(mhs): mh += self.guarded(self.events, key, hs)
            if is_mh:
                for name, fn in self.shared.items(): mh += self.shared_block(name, fn)
            mh.append('}')
        head = '\n'.join(imports + head_mod) + '\n'           # (after the imports: an import resets the module name)
        temps = [f'temp var {t};' for t in sorted(self.temps)] + sorted(self.aliases_dws)    # (`clock.day - x`, shop stock)
        sc = head + '\n'.join(temps + top + script) + '\n' if (script or top) else None
        return sc, (head + '\n'.join(mh) + '\n' if mh else None), \
            ('\n'.join([import_line(p) for p in CORE] + head_mod + decl) + '\n' if decl else None)

    def guarded(self, f, *args):
        """f(*args), with its error kept for the report of the whole file."""
        try:
            return f(*args)
        except PyError as e:
            self.errors.append(e); return []

    def ownership(self):
        """What this file owns, for the check across mods: ('npc', screen, slot) of the NPCs it declares, ('screen', n) of new screens."""
        if self.mode != 'mod': return []
        out = []
        for d in self.npcs.values():
            if not d.get('base') and d['screen'] is not None: out += [('npc', i, d['slot']) for i in self.screens[d['screen']]['ids']]
            if d.get('taken'): out.append(('npc', d['screen_id'], d['slot']))
        for v in self.screens.values():
            if v['new']: out.append(('screen', v['ids'][0]))
        return out

    def decls(self):
        """The flags and counters this file declares. A mod with a reserved range (`mod.toml [save] flags = "12000-12099"`) pins
        them there, by the mod's lock (`save.lock`, append-only: a name keeps its number whatever else is installed)."""
        out = []; pin = self.pinner()
        for q, d in self.quests.items():
            if any(f'{q}_b{j}' in self.own_decls for j in range(d['bits'])):
                out += [f'pub flag {q}_b{j}{pin("flags", f"{q}_b{j}", d["node"])};    // quest {q}: bit {j} of the stage '
                        f'({", ".join(f"{k} {x}" for k, x in enumerate(d["stages"]))})    // @py {d["node"].lineno}' for j in range(d['bits'])]
        for f, node in self.flags.items():
            if f in self.own_decls: out.append(f'pub flag {f}{pin("flags", f, node)};    // @py {node.lineno}')
        for v, node in self.vars.items():
            if v in self.own_decls: out.append(f'pub var {v}{pin("vars", v, node)};    // @py {node.lineno}')
        return out

    def pinner(self):
        if self.mode != 'mod': return lambda kind, name, node: ''
        lock = mod_lock(self.mod, self.mod_dir)
        def pin(kind, name, node):
            rng = lock.ranges.get(kind)
            if rng is None:                                  # (reported once per kind; the rest of the file is still checked)
                if kind not in self.__dict__.setdefault('range_errs', set()): self.range_errs.add(kind); self.errors.append(self.no_range(lock, kind, node))
                return ''
            return f' = {lock.number(kind, name, self, node)}'
        return pin

    def no_range(self, lock, kind, node):
        """A mod that saves state reserves its numbers in mod.toml: without it they would depend on the other mods installed."""
        what = {'flags': 'quests and flags', 'vars': 'counters'}[kind]
        rng = free_range(kind, 10 if kind == 'flags' else 3) or 'FIRST-LAST'
        toml = os.path.relpath(lock.toml, ROOT) if lock.toml.startswith(ROOT + os.sep) else lock.toml
        add = f'{kind} = "{rng}"' if lock.has_save else f'[save]\n        {kind} = "{rng}"'
        pool = ('the original engine\'s free flags are 717-799; on the story-state engine, story flags such as "12100-12199"' if kind == 'flags'
                else 'the original engine\'s free saved counters are 7-15 and 20')
        return self.err(node, f'mod {self.mod} reserves no save {kind} in mod.toml: its {what} would get numbers that change with '
                              f'the other mods installed, and a saved game would read the wrong ones',
                        f'add to {toml}{" (under [save])" if lock.has_save else ""}:\n        {add}\n      ({pool}; '
                        f'other mods\' ranges are left out)')

    def npc_decls(self, ind):
        return [f'{ind}npc {n} = {d["entity"]};' for n, d in sorted(self.npcs.items(), key=lambda kv: kv[1]['entity'])]

    def owned(self, h):
        """Does this file own the handler's key (an NPC it declares, a new screen), or does it add a guarded one to the base's?"""
        if self.mode != 'mod': return True
        if h.kind == 'talk': return not self.npcs[h.arg].get('base')
        scr = self.screens.get(h.target)
        return bool(scr and scr['new'])

    def groups(self, hs):
        out = {}
        for h in hs:
            key = (h.kind, h.arg if h.kind in ('talk', 'step', 'use', 'section', 'maphead') else None)
            out.setdefault(key, []).append(h)
        return list(out.items())

    def header(self, h, replace):
        r = ' replace' if replace else ''
        return {'talk': lambda: f'on talk({h.arg}){r}', 'enter': lambda: f'on enter{r}', 'step': lambda: f'on step({h.arg}){r}',
                'use': lambda: f'on use({h.arg}){r}', 'section': lambda: f'section({h.arg}){r}',
                'maphead': lambda: f'section({h.arg}){r}'}[h.kind]()

    def events(self, key, hs):
        """The handlers of one key -> one event. Owned: `replace`, the guards an if/else chain in declaration order (a handler
        without `when=` is the last branch). Added to the base's NPC or screen: a `before` event, each handler `if (when) { ... }`
        (on_talk also returns: the first that matches answers, the base's talk is what runs when none does)."""
        names = ', '.join(h.fn.name for h in hs)
        if self.mode != 'mod' or (len(hs) == 1 and hs[0].when is None and self.owned(hs[0])):
            h = hs[0]
            g = next((x for x in hs if x.when is not None), None)
            if g is not None and self.mode != 'mod':
                raise self.err(g.when, '`when=` guards are for mods, and this file is not in a mod',
                               'a mod\'s files live in story/mods/<mod>/src/ (pyright checks the files under story/mods too)')
            if len(hs) > 1: raise self.err(hs[1].node, f'a second handler for the same {h.kind}: give them `when=` guards')
            b = Body(self, h.arg if h.kind == 'talk' else None, h.kind); b.handler = h.fn.name
            lines = (['        engine.cutscene = true;'] if h.scene else []) + b.block(h.fn.body, 2)
            return [f'    {self.header(h, True)} {{    // {names}    // @py {h.node.lineno}'] + lines + ['    }']
        own = self.owned(hs[0])
        if own:
            out = [f'    {self.header(hs[0], True)} {{    // {names}    // @py {hs[0].node.lineno}']
            for k, h in enumerate(hs):
                if h.when is None and k != len(hs) - 1:
                    raise self.err(h.node, 'a handler without `when=` answers always: it must be the last of its NPC or screen',
                                   'move it after the guarded ones')
                b = Body(self, h.arg if h.kind == 'talk' else None, h.kind); b.handler = h.fn.name
                body = (['engine.cutscene = true;'] if h.scene else []) + [l[8:] if l.startswith('        ') else l for l in b.block(h.fn.body, 2)]
                body = ['            ' + l if l else '' for l in body]
                if h.when is None:
                    out += ['        } else {'] + body; continue
                pre = []; c = self.guard_cond(h, pre)
                out += [f'        {"if" if k == 0 else "} else if"} ({c}) {{    // @py {h.node.lineno}'] + body
            return out + ['        }', '    }']
        out = [f'    {self.header(hs[0], False)} {{    // {names}: added to the base\'s (they run first)    // @py {hs[0].node.lineno}']
        for h in hs:
            own_hint = (f'to answer always, own the NPC: x = take_over({h.arg}), then @x.on_talk' if h.kind == 'talk' else
                        'the base\'s own code runs after yours: a guard says when yours runs')
            if h.when is None:
                raise self.err(h.node, f'{h.fn.name}: a handler on the base\'s NPC or screen needs `when=` (the base\'s own code answers otherwise)',
                               own_hint)
            if isinstance(h.when, ast.Constant) and h.when.value is True:
                raise self.err(h.when, 'when=True: a guard that always holds', own_hint)
            b = Body(self, h.arg if h.kind == 'talk' else None, h.kind); b.before = True; b.handler = h.fn.name
            pre = []; c = self.guard_cond(h, pre)
            body = (['engine.cutscene = true;'] if h.scene else []) + [l[8:] if l.startswith('        ') else l for l in b.block(h.fn.body, 2)]
            if h.kind == 'talk' and not (body and body[-1].strip().split('    //')[0] == 'return;'): body.append('return;')    # (a warp ends with one)
            out += [f'        if ({c}) {{    // @py {h.node.lineno}'] + ['            ' + l if l else '' for l in body] + ['        }']
        return out + ['    }']

    def guard_cond(self, h, pre):
        """A handler's `when=` -> DWS. A guard tests saved state: what the game reads only when a line runs is refused."""
        b = Body(self, None, h.kind); b.guard = True
        c = b.cond(h.when, pre)
        if pre: self.errors.append(self.err(h.when, f'a guard (when=) tests saved state; {read_now(pre)} is read when a line runs',
                                            f'test it with an `if` inside the handler'))
        return c

    def mod_top(self):
        """A mod's NPCs: `place(...)` in the screen's .MAP slot and, with `when=`, a presence rule (story-state engine)."""
        if self.mode != 'mod': return []
        out = []; pres = {}
        sp = N.enum_members('species')
        for name, d in self.npcs.items():
            if d.get('taken'):
                if not d['kw']: continue                            # owning its talk only: nothing changes in the slot
                scr = {'map': None}; screen = d['screen_id']
            elif d.get('base') or d['screen'] is None: continue
            else: scr = self.screens[d['screen']]; screen = scr['ids'][0]
            on = scr['ids'] if scr.get('ids') else [screen]                 # screen(a, b): the same slot on each
            kw = d['kw']
            if d['species'] is None: raise self.err(d['node'], 'a new NPC needs its species')
            args = [f'species({d["species"]})', f'screen: {screen}' if len(on) == 1 else f'screen: [{", ".join(map(str, on))}]', f'slot: {d["slot"]}']
            if 'at' in kw:
                at = kw['at']
                if not (isinstance(at, ast.Tuple) and len(at.elts) == 2): raise self.err(at, 'at=(x, z)')
                args.append(f'at: ({self.int_const(at.elts[0])}, {self.int_const(at.elts[1])})')
            if not d.get('taken') and d['entity'] != 5 + d['slot']: args.append(f'section: {d["entity"]}')    # (Claims.talk_section)
            if 'like_slot' in kw: args.append(f'like: {self.int_const(kw["like_slot"])}')
            if isinstance(kw.get('still'), ast.Constant) and kw['still'].value is True: args.append('still: true')
            for k, dk in (('hp', 'hp'), ('mp', 'mp'), ('offense', 'off'), ('defense', 'def'), ('speed', 'speed'), ('brain', 'brain'), ('bits', 'bits'), ('range', 'range')):
                if k in kw: args.append(f'{dk}: {self.int_const(kw[k])}')
            if scr.get('map'): args.append(f'map: "{scr["map"]}"')
            at_py = f'    // @py {d["node"].lineno}'                 # (the source map: an error of the compiler points at the npc() line)
            out.append(f'place({", ".join(args)});{at_py}')
            if 'when' in kw or 'autotalk' in kw:
                at = isinstance(kw.get('autotalk'), ast.Constant) and kw['autotalk'].value is True
                cond = self.presence(kw['when']) if 'when' in kw else 'always'
                for one in on:
                    pres.setdefault(one, []).append((f'npc species({d["species"]}) slot {d["slot"]}{" autotalk" if at else ""} when {cond};', at_py))
        if pres:
            first = min(pres.items())[1][0][1]
            out.append('city {' + first); out.append('    presence {' + first)
            for scr, rules in sorted(pres.items()):
                out += [f'        screen({scr}) {{' + rules[0][1]] + ['            ' + r + a for r, a in rules] + ['        }']
            out += ['    }', '}']
        return out

    def presence(self, node):
        """An NPC's `when=` -> the presence grammar of `city { presence }` (flag(x), not, and, or, recruited, trigger)."""
        b = Body(self, None, 'presence'); b.guard = True
        t = b.ctree(node, pre := [])
        if [p for p in pre if p != 'store_date(date_year);']:
            raise self.err(node, f'an NPC\'s when= tests flags and the clock only (quest stages, flag(), recruited(...), trigger(n), '
                                 f'clock.hour...); {read_now(pre)} is read when a line runs',
                           'test it with an `if` in a handler; to send the NPC away by it, `npc.leave()` in an on_enter')
        def r(t):
            if t[0] == 'lit':
                s, neg = (t[1][1:], True) if t[1].startswith('!') else (t[1], False)
                c = re.fullmatch(r'date_(year|day|hour|minute) (==|!=|<=|>=|<|>) (\d+)', s)
                if c:                                  # the clock: the setup reads it (STORE_DATE), as the base's shop keepers do
                    x = f'clock.{c.group(1)} {c.group(2)} {c.group(3)}'
                    if neg: x = f'clock.{c.group(1)} {NEG_CMP[c.group(2)]} {c.group(3)}'
                    return x
                if re.fullmatch(r'\w+', s): x = f'flag({s})'
                elif re.fullmatch(r'is_recruited\(species\((\d+)\)\)', s): x = 'recruited(' + s[len('is_recruited('):]
                elif re.fullmatch(r'trigger\(\d+\)', s): x = s
                else: raise self.err(node, f'an NPC\'s when= cannot test `{ast.get_source_segment(self.src, node) or s}`: who stands on '
                                           'the screen is decided by its setup, whose rule tests flags and the clock only (quest stages, '
                                           'flag(), recruited(...), trigger(n), clock.hour...)',
                                     'test items, counters and stats with an `if` in a handler; to send the NPC away by one, '
                                     '`npc.leave()` in an on_enter')
                return f'not {x}' if neg else x
            return '(' + f' {t[0]} '.join(r(x) for x in t[1]) + ')'
        out = r(t)
        return out[1:-1] if out.startswith('(') and out.endswith(')') and t[0] != 'lit' else out

    def engine_errors(self, max_opcode_level, exe, profile='original'):
        """What the target engine cannot run, at the npc() / take_over() line: slots 8-15 and the species beyond the game's
        180 (imported: DIGI.DAT) need the story-state engine; so do the forms of `self.story_state` (`clock.day - last_day`), whose
        counters must be the extended-save profile's variables."""
        out = [self.err(n, msg, hint) for n, msg, hint in self.story_state] if profile == 'original' else []
        if exe not in WIDE_EXES:
            sp_names = N.enum_members('species')
            out += [self.err(n, f'Species.{sp_names.get(sp, sp)} is imported (content/species): the partner can be one only on a disc '
                                f'built with --exe species or --exe story-state (DIGI.DAT)',
                             'compile with --exe species (or story-state); on the original engine the partner is one of the game\'s species')
                    for n, sp in self.imported]
        for name, d in self.npcs.items():
            if d.get('base') or (d['screen'] is None and not (d.get('taken') and d['kw'])): continue
            if d['slot'] is not None and d['slot'] >= 8 and max_opcode_level < 2 and not d.get('taken'):
                out.append(self.err(d['node'], f'slot {d["slot"]}: the original engine has NPC slots 0-7 (a screen\'s new NPC goes in the '
                                               f'first free one); slots 8-15 need the story-state engine',
                                    'compile with --exe story-state, or put it on a screen with a free slot (python3 tools/dws.py slots SCREEN)'))
            sp = d['species']
            if sp is not None and sp >= 180 and exe not in ('species', 'story-state') and not BE.IMPORTED_NPCS:
                out.append(self.err(d['node'], f'Species.{N.enum_members("species").get(sp, sp)} is not one of the original game\'s 180 '
                                               f'species (it is imported: content/species/): it needs the story-state engine',
                                    'compile with --exe story-state (its DIGI.DAT has the imported species), or pick a species of the game'))
        return out

    def shared_block(self, name, fn):
        b = Body(self, None, 'shared')
        return [f'    shared {name} {{'] + b.block(fn.body, 2) + ['    }']


class Body:
    """Statements of one handler or shared block."""

    def __init__(self, mod, self_npc, kind):
        self.m = mod; self.self_npc = self_npc; self.kind = kind
        self.recruit_visible = False
        self.recruit_battle = False
        self.before = False                 # a handler added before the base's code: a warp ends it (`return` after it)
        self.guard = False                  # a `when=` (the messages say what to write there)
        self.picks = set()                  # names given to pick_item(): `pick = pick_item()`
        self.rolls = set()                  # the name given to a random draw: `roll = random.roll(n)`

    def err(self, node, msg, hint=None):
        return self.m.err(node, msg, hint)

    # ------------------------------------------------------------ values
    def ent(self, a, verb='this'):
        """An entity expression -> DWS (`tamer`, `kunemon`, `entity(5)`, `camera` for entity 200)."""
        if isinstance(a, ast.Name):
            if a.id in ('tamer', 'partner', 'narrator'): return a.id
            if a.id in self.m.npcs or a.id in self.m.unresolved: return a.id      # (an import that failed has said it)
        if isinstance(a, ast.Call) and isinstance(a.func, ast.Name) and a.func.id == 'entity' and len(a.args) == 1:
            n = self.m.int_const(a.args[0])
            return 'camera' if n == 200 else f'entity({n})'
        if isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name) and a.value.id == 'Species':
            raise self.err(a, f'{verb}: someone on the screen is expected (an NPC, tamer, partner or narrator), not a species',
                           f'an NPC of a species is declared first: x = screen.npc(Species.{a.attr}, at=(x, z)), then {verb}(x)')
        raise self.err(a, f'{verb}: an NPC, tamer, partner or narrator is expected')

    def who(self, call):
        """The entity a verb is said of: `x.say(...)` -> x; `say(...)` -> the NPC being talked to."""
        f = call.func
        if isinstance(f, ast.Attribute): return self.ent(f.value, f.attr)
        if self.self_npc: return self.self_npc
        raise self.err(call, f'`{f.id}(...)` without a speaker is only for `on_talk` (the NPC being talked to)',
                       f'write narrator.{f.id}(...), tamer.{f.id}(...) or npc.{f.id}(...)')

    def key(self, a):
        p = self.m.text_path(a) if isinstance(a, ast.Attribute) else None
        if p is None: raise self.err(a, 'a text key is expected (text.s002.sec6.u0, or an alias of a section: t6.u0)')
        return p

    def page_arg(self, a, ctx=None):
        """say argument -> DWS: a key is an utterance (`text(k)`: its pages, or its words wrapped), page(...) rows, a string is new
        text, t("name") a named line of the mod. ctx: what the line is (`text sync` tells the translator: who says it, which page)."""
        if isinstance(a, ast.Call) and isinstance(a.func, ast.Name) and a.func.id == 'page':
            return 'page(' + ', '.join(self.row(r, ctx) for r in a.args) + ')'
        if isinstance(a, ast.Constant) and isinstance(a.value, str): return self.string(a, ctx)
        if isinstance(a, ast.JoinedStr): raise self.err(a, 'f-strings are not text: the words are fixed when the game is built', 'write the line out')
        if isinstance(a, ast.Name) and a.id in self.m.consts: return self.page_arg(self.m.consts[a.id], ctx)
        if self.is_named(a): return self.named(a, ctx)
        return f'text("{self.key(a)}")'

    def row(self, r, ctx=None):
        if isinstance(r, ast.Constant) and isinstance(r.value, str): return self.string(r, ctx)
        if self.is_named(r): return self.named(r, ctx)
        return f'text("{self.key(r)}")'

    def is_named(self, a):
        return isinstance(a, ast.Call) and isinstance(a.func, ast.Name) and a.func.id == 't'

    def named(self, a, ctx=None):
        """t("intro.hello"): a named line of the mod, its English in the mod's text/en.json under that name (the translations
        by the same name). A name used and not there is an error here, with the nearest names."""
        m = self.m
        if m.mode != 'mod': raise self.err(a, 't("name") is a named line of a mod (its text/en.json): this file is not in a mod',
                                           'write the line itself, say("..."), or put the file in story/mods/<mod>/src/')
        if len(a.args) != 1 or a.keywords or not isinstance(a.args[0], ast.Constant) or not isinstance(a.args[0].value, str):
            raise self.err(a, 't() takes the line\'s name in quotes: t("intro.hello")')
        name = a.args[0].value; en = m.en_json(); names = named_keys(en, m.mod)
        if name not in names:
            near = difflib.get_close_matches(name, list(names), 3, 0.6)
            rel_en = os.path.relpath(os.path.join(m.mod_dir, 'text', 'en.json'))
            raise self.err(a.args[0], f'no line "{name}" in the text/en.json of {m.mod}' + (f': did you mean {", ".join(near)}?' if near else ''),
                           f'add it there: "{name}": "The words." (named lines are written in en.json; a line written in place, '
                           'say("..."), needs no name)')
        v = en[name]
        if not isinstance(v, str): raise self.err(a, f'"{name}" in text/en.json: a named line is one string (the compiler wraps it into pages)')
        node = ast.Constant(v); ast.copy_location(node, a)
        self.font_check(node)
        key = f'{m.mod}:{name}'; m.named[key] = v; m.named_used.add(name)
        self.record(key, a, ctx)
        return f'text("{key}")'

    def record(self, key, a, ctx):
        """Where a line of a mod is and what it is (for `text sync`'s `_where` and the checks of a translation)."""
        info = {'path': self.m.path, 'line': a.lineno, 'col': a.col_offset + 1, 'handler': getattr(self, 'handler', self.kind)}
        info.update(ctx or {})
        self.m.text_info.setdefault(key, info)

    def string(self, a, ctx=None):
        """New text. In a mod it is a key of the mod's bank, the hash of the words (`text sync` writes the bank; a translation
        stays with its words wherever they move); elsewhere the words themselves."""
        self.font_check(a)
        self.escape_check(a)
        if self.m.mode == 'mod':
            key = text_key(self.m.mod, a.value)
            self.m.texts[key] = a.value
            self.m.text_where.setdefault(key, f'{os.path.basename(self.m.path)}:{getattr(self, "handler", self.kind)}')
            self.record(key, a, ctx)
            return f'text("{key}")'
        return '"' + a.value.replace('\\', '\\\\').replace('"', '\\"') + '"'

    def escape_check(self, a):
        """The escapes of a new line ({player}, {item Item.X}...) are the game's: one it does not know is an error here, at the
        line (not at a generated assembly line)."""
        for e in escape_problems(a.value):
            self.m.errors.append(self.err(a, e, 'the escapes: {player} {partner} {item Item.X} (its name, as the inventory shows '
                                                'it, renamed or translated) {money} {color N} (docs/mods/story-language.md "Text")'))

    def font_check(self, a):
        """Every character of a new line has a glyph in the target's font (`font_problems`): one it lacks is an error here, at
        the .py line, not at the assembler's; one with a plain form (an accent, … as ..., – — as -) is a note (drawn plain)."""
        errs, plain = font_problems(a.value)
        for msg, hint in errs: self.m.errors.append(self.err(a, msg, hint))
        if plain:
            note = f'{self.m.path}:{a.lineno}: note: {plain_note(plain)}'
            if note not in self.m.notes: self.m.notes.append(note)

    def val(self, a):
        """An argument value -> DWS."""
        m = self.m
        if isinstance(a, ast.Constant):
            if isinstance(a.value, bool): return 'true' if a.value else 'false'
            if isinstance(a.value, int): return str(a.value)
            if isinstance(a.value, str): return self.string(a)
        if isinstance(a, ast.UnaryOp) and isinstance(a.op, ast.USub): return str(-m.int_const(a.operand))
        if isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name):
            o = a.value.id
            if o == 'Species': return f'species({m.enum_id("species", a)})'
            if o == 'Item': return f'item({m.enum_id("item", a)})'
            if o == 'Tech': return f'tech({m.enum_id("tech", a)})'
            if o == 'Screen': return str(m.screen_id(a))
            if o in ('Routine', 'DigimonRoutine'): return f'routine("{a.attr}")'
            if o == 'anim': return f'anim.{a.attr}'
            if o in m.aliases: return f'text("{self.key(a)}")'
            return self.state(a)
        if isinstance(a, ast.Attribute) and self.m.text_path(a): return f'text("{self.key(a)}")'
        if isinstance(a, ast.Call) and isinstance(a.func, ast.Name):
            f = a.func.id
            if f in ('Species', 'Item', 'Tech'): return f'{f.lower()}({m.int_const(a.args[0])})'
            if f == 'entity': return self.ent(a)
            if f in ('pstat', 'trigger'): return self.state(a)
            if f == 'Card': return str(m.int_const(a.args[0]))
        if isinstance(a, ast.Name):
            if a.id in ('tamer', 'partner', 'narrator') or a.id in m.npcs: return self.ent(a)
            if a.id in self.picks: return 'engine.arg'                  # the item pick_item() chose
            if a.id in self.rolls: return 'random_roll'                 # the last random draw
            if a.id in m.consts: return self.val(m.consts[a.id])
            return self.state(a)
        raise self.err(a, 'this value is not part of the story language')

    def state(self, a):
        """A saved or engine value: `pstat(110)` -> p110, `trigger(56)` -> trigger(56), `random_roll`, `engine.arg`, `tournament.day`."""
        if isinstance(a, ast.Call) and isinstance(a.func, ast.Name) and a.func.id == 'pstat': return f'p{self.m.int_const(a.args[0])}'
        if isinstance(a, ast.Call) and isinstance(a.func, ast.Name) and a.func.id == 'trigger': return f'trigger({self.m.int_const(a.args[0])})'
        if isinstance(a, ast.Name): return 'random_roll' if a.id in self.rolls else a.id
        if isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name): return f'{a.value.id}.{a.attr}'
        raise self.err(a, 'a flag or a variable is expected')

    # ------------------------------------------------------------ conditions
    def cond(self, c, pre):
        """A condition -> DWS; `pre` collects statements that must run before the test (STORE_RANDOM, STORE_DATE, a battle)."""
        return self.render(self.ctree(c, pre), c)

    def render(self, t, node):
        """A condition tree -> DWS. The game's IF folds left to right, so a group (an `or` inside an `and`, or the reverse) must
        come first: a commutative reorder puts it there; two groups at one level cannot be written as one IF."""
        if t[0] == 'lit': return t[1]
        op = ' && ' if t[0] == 'and' else ' || '
        kids = list(t[1])
        groups = [k for k, x in enumerate(kids) if x[0] != 'lit']
        if len(groups) > 1:
            raise self.err(node, 'this condition has two groups the game cannot test in one go',
                           'split the guard: two handlers with the same body, `when=a and b` and `when=c and d` (a def they both call)'
                           if self.guard else 'split it: `if a or b:` then an inner `if c or d:`, or use fewer quest stages')
        if groups and groups[0] != 0: kids.insert(0, kids.pop(groups[0]))
        out = []
        for k, x in enumerate(kids):
            r = self.render(x, node)
            out.append(f'({r})' if x[0] != 'lit' else r)
        return op.join(out)

    def ctree(self, c, pre):
        if isinstance(c, ast.BoolOp):
            op = 'and' if isinstance(c.op, ast.And) else 'or'
            kids = []
            for v in c.values:
                t = self.ctree(v, pre)
                kids += t[1] if t[0] == op else [t]              # a and (b and c) is a and b and c: the same IF
            return (op, kids) if len(kids) > 1 else kids[0]
        if isinstance(c, ast.UnaryOp) and isinstance(c.op, ast.Not):
            t = self.ctree(c.operand, pre)
            if t[0] == 'lit':
                if re.fullmatch(r'(.+?) (==|!=|<=|>=|<|>) ([^=<>!]+)', t[1]): return self.negate(t)    # not has(x, 2): has(x) < 2
                return ('lit', t[1][1:] if t[1].startswith('!') and not t[1].startswith('!(') else f'!{t[1]}')
            try:
                return self.negate(t)
            except ValueError:
                raise self.err(c, '`not` of an `in` test inside a group cannot be written as one IF', 'test the members one by one: x != a and x != b')
        st = self.stage_compare(c)
        if st is not None: return st
        q = self.quest_cond(c)
        if q is not None: return q
        pt = self.partner_tree(c)
        if pt is not None: return pt
        if isinstance(c, ast.Compare) and len(c.ops) == 1 and isinstance(c.left, ast.Call) and self.is_fight(c.left):
            r = c.comparators[0]
            if not (isinstance(r, ast.Constant) and r.value in ('won', 'lost', 'fled')) or not isinstance(c.ops[0], (ast.Eq, ast.NotEq)):
                raise self.err(c, 'fight(...) == "won" / "lost" / "fled"')
            pre.extend(l.strip() for l in self.call(c.left, 0))
            return ('lit', ('' if isinstance(c.ops[0], ast.Eq) else '!') + r.value)
        return ('lit', self.atom(c, pre))

    def negate(self, t):
        """not t: De Morgan; a comparison flips its operator; ValueError for `x in [...]` (no negated form)."""
        if t[0] != 'lit': return ('or' if t[0] == 'and' else 'and', [self.negate(x) for x in t[1]])
        x = t[1]
        if x.startswith('!') and not x.startswith('!('): return ('lit', x[1:])
        if ' in [' in x: raise ValueError('in')
        m = re.fullmatch(r'(.+?) (==|!=|<=|>=|<|>) ([^=<>!]+)', x)
        if m: return ('lit', f'{m.group(1)} {NEG_CMP[m.group(2)]} {m.group(3)}')
        return ('lit', f'!{x}')

    def is_fight(self, c):
        return isinstance(c.func, ast.Name) and c.func.id == 'fight'

    def quest_cond(self, c):
        """`Horn.ASKED` (at), `Horn.before(Horn.FOUND)`, `Horn.reached(Horn.FOUND)` -> a tree over the quest's bits."""
        m = self.m
        if isinstance(c, ast.Attribute) and isinstance(c.value, ast.Name) and c.value.id in m.quests:
            return m.stage_tree(c.value.id, lambda v, i: v == i, m.stage_index(c.value.id, c))
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and isinstance(c.func.value, ast.Name) and c.func.value.id in m.quests \
                and c.func.attr in ('before', 'reached') and len(c.args) == 1:
            q = c.func.value.id; i = m.stage_index(q, c.args[0])
            return m.stage_tree(q, (lambda v, i: v < i) if c.func.attr == 'before' else (lambda v, i: v >= i), i)
        return None

    def stage_compare(self, c):
        """`Horn.stage == Horn.DONE` is `Horn.DONE` (`!=`: not); `Horn.stage` is read in a `match` or compared so."""
        m = self.m
        def is_stage(x): return isinstance(x, ast.Attribute) and x.attr == 'stage' and isinstance(x.value, ast.Name) and x.value.id in m.quests
        if is_stage(c):
            q = c.value.id
            raise self.err(c, f'{q}.stage is a stage, not a yes/no', f'{q}.{m.quests[q]["stages"][-1]} (true at that stage), or match {q}.stage:')
        if not (isinstance(c, ast.Compare) and len(c.ops) == 1 and is_stage(c.left)): return None
        q = c.left.value.id
        if not isinstance(c.ops[0], (ast.Eq, ast.NotEq)):
            raise self.err(c, f'stages are compared with == and !=',
                           f'{q}.before({q}.X) / {q}.reached({q}.X) for "earlier" and "this one or later"')
        t = m.stage_tree(q, lambda v, i: v == i, m.stage_index(q, c.comparators[0]))
        return t if isinstance(c.ops[0], ast.Eq) else self.negate(t)

    def atom(self, c, pre):
        if isinstance(c, ast.Compare):
            if len(c.ops) != 1: raise self.err(c, 'one comparison at a time: a < b and b < c')
            if isinstance(c.left, ast.Name) and c.left.id == 'partner_type' and TARGET['exe'] in WIDE_EXES:
                # `partner.species` reads a wide register on these engines, so no earlier test can be trusted to have filled p103
                if 'store_digimon_type(partner_type);' not in pre: pre.append('store_digimon_type(partner_type);')
            op, r = c.ops[0], c.comparators[0]
            if isinstance(op, (ast.Is, ast.IsNot)):                      # pick is Picked.EMPTY / Picked.CANCELLED
                if not (isinstance(c.left, ast.Name) and c.left.id in self.picks and isinstance(r, ast.Attribute) and isinstance(r.value, ast.Name)
                        and r.value.id == 'Picked' and r.attr in ('EMPTY', 'CANCELLED')):
                    raise self.err(c, '`is` compares what pick_item() gave with Picked.EMPTY or Picked.CANCELLED')
                neg = isinstance(op, ast.IsNot)
                if r.attr == 'EMPTY': return ('!' if neg else '') + 'engine.picker_mode'
                return f'engine.arg {"!=" if neg else "=="} 255'
            if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(c.left, ast.Name) and c.left.id in self.picks:
                if not (isinstance(r, ast.Attribute) and isinstance(r.value, ast.Name) and r.value.id == 'Item'):
                    raise self.err(c, 'what pick_item() gave is compared with an Item (pick == Item.Medicine), Picked.EMPTY or '
                                      'Picked.CANCELLED (pick is Picked.EMPTY)')
                return f'engine.arg {CMP[type(op)]} {self.m.enum_id("item", r)}'                     # (the item's number)
            if isinstance(op, ast.In):
                if not isinstance(r, (ast.Tuple, ast.List)):
                    if isinstance(r, ast.Name) and r.id in self.m.consts: r = self.m.consts[r.id]
                    else: raise self.err(r, '`x in (a, b)`: a tuple of constants')
                return f'{self.operand(c.left, pre)} in [{", ".join(self.val(x) for x in r.elts)}]'
            if isinstance(op, ast.NotIn):
                raise self.err(c, '`not in` has no form the game can test', 'test the members one by one: x != a and x != b')
            if type(op) not in CMP: raise self.err(c, 'comparisons are == != < <= > >=, `in (a, b)` and `is Picked.X`')
            l = c.left
            if isinstance(l, ast.Call) and isinstance(l.func, ast.Name) and l.func.id == 'has' and len(l.args) == 1:
                it = ast.get_source_segment(self.m.src, l.args[0]) or 'Item.X'
                n = ast.get_source_segment(self.m.src, r) or 'n'
                raise self.err(c, 'has(...) is a yes/no: the count goes inside it', f'has({it}, {n}) (at least {n}); not has({it}, {n}): fewer')
            if (self.is_clock(l) and self.is_saved(r)) or (self.is_clock(r) and self.is_saved(l)):
                raise self.err(c, 'the clock is compared with a number', 'the days since a kept day: clock.day - last_day >= 1 '
                                                                         '(another day), == 0 (the same day), after '
                                                                         'last_day.set(clock.day); the story-state engine')
            if isinstance(l, ast.Attribute) and isinstance(l.value, ast.Name) and l.value.id == 'partner' and l.attr == 'level':
                return self.partner_level(c, op, r, pre)
            if isinstance(l, ast.Attribute) and isinstance(l.value, ast.Name) and l.value.id == 'partner' and l.attr == 'species' \
                    and re.fullmatch(r'species\((\d+)\)', self.val(r)):
                return f'{self.operand(l, pre)} {CMP[type(op)]} {self.val(r)[8:-1]}'      # the species number
            return f'{self.operand(l, pre)} {CMP[type(op)]} {self.operand(r, pre)}'
        if isinstance(c, ast.Call) and self.is_fight(c):
            raise self.err(c, 'a battle\'s outcome is compared: fight(...) == "won" (or "lost", "fled")')
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Name):
            f = c.func.id
            if f == 'trigger': return f'trigger({self.m.int_const(c.args[0])})'
            if f == 'recruited': return f'is_recruited({self.val(c.args[0])})'
            if f == 'has':
                if len(c.args) == 2: return f'has({self.val(c.args[0])}) >= {self.m.int_const(c.args[1])}'
                return f'has({self.val(c.args[0])})'
            if f == 'knows': return f'knows({self.val(c.args[0])})'
            if f in ('condition', 'stat'): raise self.retired(c)
            raise self.err(c, f'{f}() is not a condition',
                           'conditions: has(item, n), recruited(species), knows(tech), condition(n), trigger(n), random.chance(p), '
                           'comparisons, quest stages, flags')
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and isinstance(c.func.value, ast.Name) and c.func.value.id == 'random' \
                and c.func.attr == 'chance':
            return f'chance({self.m.int_const(c.args[0])})'
        if isinstance(c, ast.Name):
            if c.id in ('won', 'lost', 'fled'):
                raise self.err(c, f'"{c.id}" is not a name of the story language', f'test the battle where it is fought: if fight(x) == "{c.id}":')
            if c.id in ('True', 'False'): raise self.err(c, 'a condition that is always the same')
            return self.state(c)
        if isinstance(c, ast.Attribute) and isinstance(c.value, ast.Name) and c.value.id == 'partner':
            from .view import CONDITION_NAMES
            bits = {v: k for k, v in CONDITION_NAMES.items()}
            if c.attr in bits: return f'condition({bits[c.attr]})'
            raise self.err(c, f'partner.{c.attr} is not a yes/no: compare it (partner.{c.attr} >= 100)' if c.attr != 'species' else
                           'partner.species is compared: partner.species == Species.Agumon',
                           'the partner\'s conditions: ' + ', '.join(f'partner.{x}' for x in CONDITION_NAMES.values()))
        if isinstance(c, ast.Attribute): return self.state(c)
        raise self.err(c, 'this is not a condition the game can test')

    LEVELS = ('fresh', 'in_training', 'rookie', 'champion', 'ultimate', 'mega')       # 1-6 (species.LEVELS, include/dw/level.h)

    def partner_level(self, c, op, r, pre):
        """`partner.level >= Level.champion` on the original engine: the partner's species is one of the game's partner
        species (1-62) of those levels, as content/species gives them (`partner_type in [...]`)."""
        ids = self.level_species(c, op, r)
        return f'{self.operand(c.left.__class__(value=c.left.value, attr="species", ctx=ast.Load()), pre)} in [{", ".join(f"species({t})" for t in ids)}]'

    def level_species(self, c, op, r):
        """The partner species of the levels `partner.level OP Level.X` names: the game's 62 on the original engine; on any
        built executable every species of content/species with a `partner` block (the imported partners too)."""
        if not (isinstance(r, ast.Attribute) and isinstance(r.value, ast.Name) and r.value.id == 'Level' and r.attr in self.LEVELS):
            raise self.err(c, 'partner.level is compared with a Level: partner.level == Level.champion',
                           'levels: ' + ', '.join(f'Level.{x}' for x in self.LEVELS))
        want = self.LEVELS.index(r.attr) + 1
        test = {ast.Eq: lambda v: v == want, ast.NotEq: lambda v: v != want, ast.Lt: lambda v: v < want, ast.LtE: lambda v: v <= want,
                ast.Gt: lambda v: v > want, ast.GtE: lambda v: v >= want}.get(type(op))
        if test is None: raise self.err(c, 'partner.level is compared with == != < <= > >=')
        if TARGET['exe'] != 'original':
            ids = [t for t, lv in sorted(partner_levels().items()) if test(lv)]
        else:
            rows = BE.DIGI_DATA
            ids = [t for t in range(1, 63) if t in rows and int(rows[t]['level'] or 0) and test(int(rows[t]['level']))]
        if not ids: raise self.err(c, f'no partner species is at that level: the test is always false')
        return ids

    def partner_tree(self, c):
        """`partner.species == Species.X` (`!=`, `in (...)`) and `partner.level >= Level.Y`: tests of the partner's species. The
        original engine keeps it in a pstat (`partner_type`, the disc's own form: `atom`, None here); on --exe species / story-state
        a partner can be a species past 255, which a pstat would read as its low byte, so there every test reads the wide
        register (`partner.is(species(n))`). An imported species (180 and up) is recorded for `engine_errors`."""
        if not (isinstance(c, ast.Compare) and len(c.ops) == 1 and isinstance(c.left, ast.Attribute) and isinstance(c.left.value, ast.Name)
                and c.left.value.id == 'partner' and c.left.attr in ('species', 'level')): return None
        op, r = c.ops[0], c.comparators[0]
        wide = TARGET['exe'] in WIDE_EXES; neg = False
        if self.guard:                      # (said, and the rest of the file is still checked)
            self.m.errors.append(self.err(c, "a guard (when=) tests saved state; the partner's species is read when a line runs",
                                          'test it with an `if` inside the handler'))
            return ('lit', 'partner_type == 0')
        if c.left.attr == 'level': ids = self.level_species(c, op, r)
        elif isinstance(op, ast.In):
            if isinstance(r, ast.Name) and r.id in self.m.consts: r = self.m.consts[r.id]
            if not isinstance(r, (ast.Tuple, ast.List)): raise self.err(r, '`x in (a, b)`: a tuple of constants')
            ids = [self.m.enum_id('species', x) for x in r.elts]
        else:
            mm = re.fullmatch(r'species\((\d+)\)', self.val(r))
            if not mm: return None
            ids = [int(mm.group(1))]
            if not isinstance(op, (ast.Eq, ast.NotEq)):
                if wide or ids[0] > 255: raise self.err(c, "the partner's species is compared with == or != (or `in (...)`)")
                return None
            neg = isinstance(op, ast.NotEq)
        imp = next((sp for sp in ids if sp >= 180), None)
        if imp is not None and c.left.attr == 'species': self.m.imported.append((c, imp))
        if not wide and all(sp <= 255 for sp in ids): return None            # the original engine: the pstat (atom)
        lits = [('lit', f'{"!" if neg else ""}partner.is(species({sp}))') for sp in ids]
        return lits[0] if len(lits) == 1 else ('and' if neg else 'or', lits)

    def retired(self, c):
        """`stat(n)` / `condition(n)`: one form, the partner's names."""
        from .view import STAT_NAMES, CONDITION_NAMES
        f = c.func.id
        try: n = self.m.int_const(c.args[0]) if len(c.args) == 1 else None
        except PyError: n = None
        names = STAT_NAMES if f == 'stat' else CONDITION_NAMES
        if f == 'stat' and n == 21: return self.err(c, 'stat(21) is tamer.level')
        if n in names: return self.err(c, f'{f}({n}) is partner.{names[n]}')
        return self.err(c, f'{f}(n) is written by name: ' + ', '.join(f'partner.{x}' for x in names.values()))

    def is_clock(self, a):
        return isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name) and a.value.id == 'clock'

    def is_saved(self, a):
        """A counter of the mod or a pstat: a value that is not a constant."""
        return (isinstance(a, ast.Name) and a.id in self.m.vars) or (isinstance(a, ast.Call) and isinstance(a.func, ast.Name)
                                                                       and a.func.id == 'pstat')

    DAYS_A_YEAR = 30                                   # clock.c: DAY counts 0-29, then YEAR + 1

    def days_since(self, a, pre):
        """`clock.day - last_day`: the days since `last_day.set(clock.day)`, counted on the game's 30-day year (right for any
        wait under 30 days). The difference is a scene variable of the story-state engine: the original engine's IF compares a
        saved number with a constant only, so on it this is an error (Module.engine_errors, at this line)."""
        l, r = a.left, a.right
        if not (self.is_clock(l) and l.attr == 'day' and isinstance(r, ast.Name) and r.id in self.m.vars):
            raise self.err(a, 'a difference is `clock.day - last_day`: the days since last_day.set(clock.day) (last_day = counter())',
                           'only days are counted (on the 30-day year: a wait up to 29 days); a year is a quest stage or a flag'
                           if self.is_clock(l) and l.attr != 'day' else None)
        self.m.story_state.append((a, f'`clock.day - {r.id}` needs the story-state engine: the original engine compares a saved number with '
                                'a constant only', 'compile with --exe story-state; on the original engine a story waits for an hour '
                                '(`if clock.hour >= 18:`) or a day of the year (`clock.day == 7`), not for a number of days'))
        t = 'py_days'; self.m.temps.add(t)
        if 'store_date(date_year);' not in pre: pre.append('store_date(date_year);')
        pre += [f'{t} = date_day;', f'{t} -= {self.state(r)};', f'if ({t} < 0) {{ {t} += {self.DAYS_A_YEAR}; }}']
        return t

    def is_roll(self, a):
        return isinstance(a, ast.Call) and isinstance(a.func, ast.Attribute) and isinstance(a.func.value, ast.Name) \
            and a.func.value.id == 'random' and a.func.attr == 'roll' and len(a.args) == 1

    def operand(self, a, pre):
        if isinstance(a, ast.BinOp):
            if isinstance(a.op, ast.Sub): return self.days_since(a, pre)
            if isinstance(a.op, ast.Mod) and self.is_clock(a.left):
                raise self.err(a, 'no `%`: the game tests one value against a number', 'test a fixed day: clock.day == 7')
            raise self.err(a, 'arithmetic is not part of a test: compare one value with a number',
                           'the one difference is `clock.day - last_day` (the days since last_day.set(clock.day))')
        if self.is_roll(a):
            raise self.err(a, 'a random draw is kept before it is compared: roll = random.roll(n), then `if roll == 0:`',
                           f'roll = random.roll({ast.get_source_segment(self.m.src, a.args[0]) or "n"}) on the line above; '
                           'a percentage is random.chance(p)')
        if isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name) and a.value.id == 'clock':
            if a.attr not in ('year', 'day', 'hour', 'minute'): raise self.err(a, 'clock.year, clock.day, clock.hour, clock.minute')
            if 'store_date(date_year);' not in pre: pre.append('store_date(date_year);')
            return f'date_{a.attr}'
        if isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name) and a.value.id == 'partner' and a.attr == 'species':
            if 'store_digimon_type(partner_type);' not in pre: pre.append('store_digimon_type(partner_type);')   # the disc's scratch p103
            return 'partner_type'
        if isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name) and a.value.id == 'tamer' and a.attr == 'level':
            from .view import TAMER_LEVEL
            return f'stat({TAMER_LEVEL})'
        if isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name) and a.value.id == 'partner':
            from .view import STAT_NAMES
            ids = {v: k for k, v in STAT_NAMES.items()}
            if a.attr in ids: return f'stat({ids[a.attr]})'
            raise self.err(a, f'unknown partner stat "{a.attr}"', 'stats: species, ' + ', '.join(ids))
        if isinstance(a, ast.Call) and isinstance(a.func, ast.Name) and a.func.id == 'stat': raise self.retired(a)
        if isinstance(a, ast.Call) and isinstance(a.func, ast.Name) and a.func.id == 'has_card':
            return f'has_card({self.m.int_const(a.args[0])})'
        if isinstance(a, ast.Name) and a.id == 'bits': return 'bits'
        return self.val(a)

    # ------------------------------------------------------------ statements
    def fights_tested(self, s):
        """[(foes, node)] of the battles an if/elif chain tests, in order."""
        out = []
        while isinstance(s, ast.If):
            t = s.test
            for n in ast.walk(t):
                if isinstance(n, ast.Call) and self.is_fight(n):
                    out.append((ast.dump(ast.Tuple(elts=n.args, ctx=ast.Load())), n)); break
            s = s.orelse[0] if len(s.orelse) == 1 and isinstance(s.orelse[0], ast.If) else None
        return out

    def one_battle(self, stmts):
        """Two tests of fight(x) of the same foes, in one if/elif chain or in two `if`s in a row, are two battles where the
        writer meant one (the outcomes of one battle are a `match`): an error at the second."""
        prev = []
        for st in stmts:
            cur = self.fights_tested(st)
            seen = list(prev)
            for sig, n in cur:
                if any(sig == x for x, _ in seen):
                    foes = ', '.join(ast.get_source_segment(self.m.src, a) or '?' for a in n.args)
                    self.m.errors.append(self.err(n, f'a second fight({foes}) right after the first: each fight(...) is a battle of '
                                                     'its own', f'the outcomes of one battle: match fight({foes}): case "won": ... '
                                                     'case "lost": ... case "fled": ...'))
                seen.append((sig, n))
            prev = cur

    def block(self, stmts, ind):
        if self.m.mode != 'base': self.one_battle(stmts)
        out = []
        visible, battled = self.recruit_visible, self.recruit_battle
        try:
            for index, s in enumerate(stmts):
                before = self.recruit_visible
                # A hand-written departure may announce the join after its flag.
                # Look only along this straight-line path, never across another
                # recruit, battle, branch or return. Wild helpers always announce.
                if (isinstance(s, ast.Expr) and isinstance(s.value, ast.Call) and
                        isinstance(s.value.func, ast.Name) and s.value.func.id == 'recruit'):
                    for following in stmts[index + 1:]:
                        if not isinstance(following, ast.Expr) or not isinstance(following.value, ast.Call): break
                        f = following.value.func
                        if isinstance(f, ast.Name) and f.id in ('fight', 'recruit', 'warp'): break
                        if self.departure(following.value):
                            self.recruit_visible = True
                            break
                try:
                    out += self.stmt(s, ind)
                except PyError as e:
                    if e not in self.m.errors: self.m.errors.append(e)
                self.recruit_visible = before
                if isinstance(s, ast.Expr) and isinstance(s.value, ast.Call):
                    f = s.value.func
                    if isinstance(f, ast.Name) and f.id == 'fight':
                        self.recruit_battle = True
                        self.recruit_visible = False
                    elif self.departure(s.value):
                        self.recruit_visible = True
        finally:
            self.recruit_visible, self.recruit_battle = visible, battled
        return out

    def departure(self, call):
        f = call.func
        if isinstance(f, ast.Name) and f.id == 'walk_away': return True
        if not isinstance(f, ast.Attribute): return False
        if f.attr == 'walk_away': return True
        if not (f.attr == 'say' and isinstance(f.value, ast.Name) and f.value.id == 'narrator'):
            return False
        from .. import recruitment
        if not recruitment.ACTIVE.get(): return False
        def words(node):
            if isinstance(node, ast.Constant) and isinstance(node.value, str): return node.value
            if isinstance(node, ast.Name) and node.id in self.m.consts: return words(self.m.consts[node.id])
            if isinstance(node, ast.Call):
                if self.is_named(node): return self.m.en_json().get(node.args[0].value, '')
                return ' '.join(words(arg) for arg in node.args)
            value = recruitment.english_lines().get(self.m.text_path(node), '')
            def flatten(v):
                return v if isinstance(v, str) else ' '.join(flatten(x) for x in v)
            return flatten(value)
        return bool(re.search(r'\bjoined the city\b',
                              ' '.join(words(arg) for arg in call.args), re.I))

    def stmt(self, s, ind):
        """One statement; its first line carries ` // @py N` (the source map points at the .py: `py_linemap`)."""
        out = self.stmt_(s, ind)
        for k, l in enumerate(out):
            if l.strip() and not l.lstrip().startswith('//'):
                out[k] = l + f'    // @py {s.lineno}'; break
        return out

    def stmt_(self, s, ind):
        I = '    ' * ind
        if isinstance(s, ast.Pass): return []
        if isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str): return []   # docstring
        if isinstance(s, ast.Expr) and isinstance(s.value, ast.Call): return self.call(s.value, ind)
        if isinstance(s, ast.If): return self.if_(s, ind)
        if isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name) and isinstance(s.value, ast.Call) \
                and isinstance(s.value.func, ast.Name) and s.value.func.id == 'pick_item':
            self.picks.add(s.targets[0].id); return self.call(s.value, ind)
        if isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name) and self.is_roll(s.value):
            name = s.targets[0].id
            if self.rolls and name not in self.rolls:
                raise self.err(s, f'the game keeps one random draw (the last): draw again into {next(iter(self.rolls))}')
            self.rolls.add(name)                        # `roll = random.roll(n)`: the draw; `roll` reads it until the next one
            return [f'{I}store_random(random_roll, {self.m.int_const(s.value.args[0])});']
        if isinstance(s, ast.While):
            if isinstance(s.test, ast.Constant) and s.test.value is True:
                return [f'{I}loop {{'] + self.block(s.body, ind + 1) + [f'{I}}}']
            pre = []; c = self.cond(s.test, pre)
            if pre: raise self.err(s.test, f'{read_now(pre)} is read in an `if`, not in a `while`')
            return [f'{I}while ({c}) {{'] + self.block(s.body, ind + 1) + [f'{I}}}']
        if isinstance(s, ast.Break): return [f'{I}break;']
        if isinstance(s, ast.Continue): return [f'{I}continue;']
        if isinstance(s, ast.Return):
            if s.value is None: return [f'{I}return;']
            v = s.value
            if isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id in self.m.fns:     # `return closed()`: inlined
                return self.inline(v, ind) + [f'{I}return;']
            return [f'{I}goto {self.jump_target(s.value)};']
        if isinstance(s, ast.Match): return self.match(s, ind)
        what = {'Assign': 'an assignment', 'AugAssign': 'an assignment', 'AnnAssign': 'an assignment', 'For': 'a `for` loop over a run-time value',
                'With': '`with`', 'Try': '`try`', 'FunctionDef': 'a def inside a handler', 'Import': 'an import', 'ImportFrom': 'an import',
                'Global': '`global`', 'Nonlocal': '`nonlocal`', 'Delete': '`del`', 'Assert': '`assert`', 'Raise': '`raise`',
                'ClassDef': 'a class inside a handler', 'AsyncFunctionDef': '`async`'}.get(type(s).__name__, type(s).__name__)
        hint = ('a saved value changes with a method: visits.add(1), visits.set(0), invited.set() (in Python, `visits += 1` inside a '
                'def would make a new local name, which pyright reports as unbound); a name for a constant goes at the top of the file'
                if 'assignment' in what else 'statements are calls (say, walk, give...), if/elif/else, while, match, break, continue, return')
        raise self.err(s, f'{what} is not part of the story language', hint)

    def inlined(self, v):
        """`return closed()` of a def that is inlined (it has parameters, or it speaks as the NPC being talked to)."""
        return isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id in self.m.fns

    def jump_target(self, v):
        """`return L22()` / `return tokomon.talk()` / `return step1()` -> a shared block, or another section's entry."""
        if not (isinstance(v, ast.Call) and not v.args and not v.keywords):
            raise self.err(v, '`return` takes nothing, or the call of a shared def or of another handler (`return tokomon.talk()`)')
        f = v.func
        if isinstance(f, ast.Name):
            if f.id in self.m.shared or f.id in self.m.hatch_shared: return f.id
            m = re.fullmatch(r'(enter|step(\d+)|use(\d+)|sec(\d+))', f.id)
            if m:
                if f.id == 'enter': return 'sec254'
                if m.group(2): return f'sec{51 + int(m.group(2))}'
                if m.group(3): return f'sec{80 + int(m.group(3))}'
                return f'sec{m.group(4)}'
            raise self.err(f, f'"{f.id}" is not a shared def or a handler of this file')
        if isinstance(f, ast.Attribute) and f.attr == 'talk' and isinstance(f.value, ast.Name) and f.value.id in self.m.npcs:
            return f'sec{self.m.npcs[f.value.id]["entity"]}'
        raise self.err(v, 'not a shared def or handler')

    def if_(self, s, ind):
        I = '    ' * ind
        # `if c: pass / else: <one jump>` is the original's `unless (c) jump;`
        if len(s.body) == 1 and isinstance(s.body[0], ast.Pass) and len(s.orelse) == 1 and not isinstance(s.orelse[0], ast.If) \
                and not self.is_ask(s.test):
            j = s.orelse[0]; pre = []
            jt = None
            if isinstance(j, (ast.Break, ast.Continue)): jt = 'break' if isinstance(j, ast.Break) else 'continue'
            elif isinstance(j, ast.Return) and j.value is None: jt = 'return'
            elif isinstance(j, ast.Return) and not self.inlined(j.value): jt = f'goto {self.jump_target(j.value)}'
            if jt:
                c = self.cond(s.test, pre)
                return [I + p for p in pre] + [f'{I}unless ({c}) {jt};']
        # `if c: <one jump>` is `unless (!c) jump;`: one IF that jumps (the base's form, and the smaller code)
        if len(s.body) == 1 and not s.orelse and not self.is_ask(s.test):
            j = s.body[0]; jt = None
            if isinstance(j, (ast.Break, ast.Continue)): jt = 'break' if isinstance(j, ast.Break) else 'continue'
            elif isinstance(j, ast.Return) and not self.inlined(j.value):
                jt = 'return' if j.value is None else f'goto {self.jump_target(j.value)}'
            if jt:
                pre = []; t = self.ctree(s.test, pre)
                try:
                    c = self.render(self.negate(t), s.test)
                except ValueError:
                    c = None                          # (a test with no written negation, `x in (...)`: an ordinary if)
                if c is not None: return [I + p for p in pre] + [f'{I}unless ({c}) {jt};']
        out = []; pre = []
        if self.is_ask(s.test): return self.ask(s, ind)
        c = self.cond(s.test, pre)
        out += [I + p for p in pre] + [f'{I}if ({c}) {{'] + self.block(s.body, ind + 1)
        e = s.orelse
        while e:
            if len(e) == 1 and isinstance(e[0], ast.If) and not self.is_ask(e[0].test) and not self.is_guard(e[0]):
                pre2 = []; c2 = self.cond(e[0].test, pre2)
                pre2 = [p for p in pre2 if not (p in self.HOLDS and p in pre)]    # the clock / species stored for the first test
                if pre2:                      # the stored value is read here: `else { store; if (...) }`
                    out += [f'{I}}} else {{'] + self.block(e, ind + 1); break
                out += [f'{I}}} else if ({c2}) {{'] + self.block(e[0].body, ind + 1); e = e[0].orelse; continue
            out += [f'{I}}} else {{'] + self.block(e, ind + 1); break
        return out + [f'{I}}}']

    # values stored before an if that hold for its elif tests too (nothing runs between the tests; a random draw is new each time)
    HOLDS = ('store_date(date_year);', 'store_digimon_type(partner_type);')

    def is_guard(self, s):
        """`if c: <one jump>` with no else: written `unless` (an `else: if c: return` is not an `else if`)."""
        return len(s.body) == 1 and not s.orelse and isinstance(s.body[0], (ast.Break, ast.Continue, ast.Return))

    def is_ask(self, t):
        """`ask(...)` or `not ask(...)` as an if's test (the menu, with its branches swapped for `not`)."""
        if isinstance(t, ast.UnaryOp) and isinstance(t.op, ast.Not): t = t.operand
        return isinstance(t, ast.Call) and ((isinstance(t.func, ast.Name) and t.func.id == 'ask') or
                                            (isinstance(t.func, ast.Attribute) and t.func.attr == 'ask'))

    def who_label(self, w):
        """Who says a line, for the translator: "the narrator", "courier (Gotsumon)"."""
        if w in ('narrator', 'tamer', 'partner'): return f'the {w}'
        d = self.m.npcs.get(w) or {}
        sp = N.enum_members('species').get(d.get('species')) if d.get('species') is not None else None
        return f'{w} ({sp})' if sp else w

    def opt_ctx(self, call, name):
        owner = self.menu_owner(call)
        return {'kind': 'option', 'option': name, 'who': self.who_label(owner[1:-1]) if owner else 'the tamer'}

    def menu_owner(self, call):
        """`narrator.ask(...)` -> `(narrator)`: whose box the menu is (the tamer's by default)."""
        f = call.func
        if isinstance(f, ast.Attribute):
            e = self.ent(f.value, f.attr)
            return f'({e})' if e != 'tamer' else ''
        return ''

    def ask(self, s, ind):
        I = '    ' * ind; t = s.test; yes, no = s.body, s.orelse
        if isinstance(t, ast.UnaryOp): t = t.operand; yes, no = no, yes          # `if not ask(...)`: the "no" branch first
        kw = {k.arg: k for k in t.keywords}
        if t.args or set(kw) != {'yes', 'no'} or len(t.keywords) != 2:
            other = [k.arg for k in t.keywords if k.arg not in ('yes', 'no')]
            raise self.err(t, 'ask() takes exactly yes= and no= (the menu\'s two options; True when the player picks yes)'
                           + (f': {", ".join(other)}= is not one' if other else ''),
                           'ask(yes="Sure", no="Not now"); more options, or other names: match choose(a="...", b="...")')
        a, b = kw['yes'], kw['no']              # yes is the top option, whatever order the keywords are written in
        out = [f'{I}choice{self.menu_owner(t)} {{',
               f'{I}    {self.page_arg_opt(a.value, self.opt_ctx(t, "yes"))} => {{'] + self.block(yes, ind + 2) + [f'{I}    }}',
               f'{I}    {self.page_arg_opt(b.value, self.opt_ctx(t, "no"))} or cancel => {{'] + self.block(no, ind + 2) + [f'{I}    }}', f'{I}}}']
        return self.tidy_choice(out)

    def page_arg_opt(self, a, ctx=None):
        """A menu option: a key is `text(k)`, a string is new text, t("name") a named line."""
        if isinstance(a, ast.Constant) and isinstance(a.value, str): return self.string(a, ctx)
        if self.is_named(a): return self.named(a, ctx)
        return f'text("{self.key(a)}")'

    def tidy_choice(self, lines):
        """`=> {` + `}` with nothing between -> `=> {}` (the beautifier's form)."""
        out = []
        for l in lines:
            if out and l.strip() == '}' and out[-1].rstrip().endswith('=> {'): out[-1] = out[-1].rstrip() + '}'; continue
            out.append(l)
        return out

    def match(self, s, ind):
        I = '    ' * ind; subj = s.subject
        for case in s.cases:
            if case.guard is not None:
                raise self.err(case.guard, 'a story match case takes no `if`', 'test it inside the case')
        if isinstance(subj, ast.Call) and ((isinstance(subj.func, ast.Name) and subj.func.id == 'choose') or
                                           (isinstance(subj.func, ast.Attribute) and subj.func.attr == 'choose')):
            return self.choose(s, ind)
        if isinstance(subj, ast.Attribute) and isinstance(subj.value, ast.Name) and subj.value.id in self.m.quests and subj.attr == 'stage':
            return self.match_stage(s, subj.value.id, ind)
        if isinstance(subj, ast.Call) and self.is_fight(subj): return self.match_fight(s, ind)
        # match v: case 0: ... case n | _: -> the original's clamped SWITCH
        v = self.operand(subj, [])
        out = [f'{I}match ({v}, clamp) {{']
        for k, case in enumerate(s.cases):
            vals = self.case_values(case.pattern)
            last = k == len(s.cases) - 1
            if vals != ([k, '_'] if last else [k]): raise self.err(case, 'a clamped match is `case 0:` ... `case n | _:` in order (the original\'s SWITCH)')
            body = self.block(case.body, ind + 2)
            out += [f'{I}    {k} => {{}}'] if not body else [f'{I}    {k} => {{'] + body + [f'{I}    }}']
        return out + [f'{I}}}']

    def match_stage(self, s, q, ind):
        """`match Horn.stage: case Horn.NONE | Horn.ASKED: ...` -> an if/else chain over the quest's bits."""
        I = '    ' * ind; out = []; m = self.m; last_else = False
        for k, case in enumerate(s.cases):
            pats = case.pattern.patterns if isinstance(case.pattern, ast.MatchOr) else [case.pattern]
            if any(isinstance(p, ast.MatchAs) and p.pattern is None and p.name is None for p in pats):
                out += [f'{I}}} else {{' if k else f'{I}{{'] + self.block(case.body, ind + 1); last_else = True; break
            idx = []
            for p in pats:
                if not isinstance(p, ast.MatchValue): raise self.err(p, f'a case is a stage of {q} (case {q}.X:)')
                idx.append(m.stage_index(q, p.value))
            t = m.stage_tree(q, lambda v, i: v in i, idx) if len(idx) < len(m.quests[q]['stages']) else None
            c = self.render(t, case) if t else None
            if c is None: out += [f'{I}}} else {{' if k else f'{I}{{'] + self.block(case.body, ind + 1); last_else = True; break
            out += [f'{I}{"if" if k == 0 else "} else if"} ({c}) {{'] + self.block(case.body, ind + 1)
        return out + [f'{I}}}']

    OUTCOMES = ('won', 'lost', 'fled')

    def match_fight(self, s, ind):
        """`match fight(x): case "won": ... case "lost": ... case "fled": ...`: one battle, then its outcome (engine.result) by
        an if/else chain; the case that leaves no other outcome (or `case _:`) is the else."""
        I = '    ' * ind
        out = self.call(s.subject, ind)
        left = list(self.OUTCOMES); k = 0
        for case in s.cases:
            vals = self.case_values(case.pattern)
            bad = [v for v in vals if v != '_' and v not in self.OUTCOMES]
            if bad: raise self.err(case, f'a battle\'s outcome is "won", "lost" or "fled", not {bad[0]!r}')
            if case.guard is not None: raise self.err(case.guard, 'a case of a battle takes no `if`', 'test it inside the case')
            if not left: raise self.err(case, 'every outcome is answered above: this case never runs')
            mine = left if '_' in vals else [v for v in vals if v in left]
            if not mine: raise self.err(case, f'"{vals[0]}" is answered above')
            left = [v for v in left if v not in mine]
            body = self.block(case.body, ind + 1)
            if not left and k: out += [f'{I}}} else {{'] + body; k += 1; break
            if not left: out += body; break                      # (one case for every outcome: no test)
            c = ' || '.join(mine)
            out += [f'{I}{"if" if k == 0 else "} else if"} ({c}) {{'] + body; k += 1
        return out + ([f'{I}}}'] if k else [])

    def case_values(self, p):
        if isinstance(p, ast.MatchOr): return [x for q in p.patterns for x in self.case_values(q)]
        if isinstance(p, ast.MatchValue) and isinstance(p.value, ast.Constant): return [p.value.value]
        if isinstance(p, ast.MatchAs) and p.pattern is None and p.name is None: return ['_']
        raise self.err(p, 'a case is a constant, `_`, or `a | b`')

    def choose(self, s, ind):
        I = '    ' * ind; call = s.subject
        if call.args: raise self.err(call, 'choose(a="...", b="..."): options by keyword')
        names = [k.arg for k in call.keywords]
        bodies = {}; both = None; cancel = None
        for case in s.cases:
            vals = self.case_values(case.pattern)
            labels = [v for v in vals if v != '_']
            if any(v not in names for v in labels): raise self.err(case, f'no option {[v for v in labels if v not in names]} in this choose(...)', f'options: {", ".join(names)}')
            if '_' in vals and labels:
                if len(labels) != 1 or both is not None: raise self.err(case, 'one option is also the cancel: `case "no" | _:`')
                both = labels[0]
            if '_' in vals and not labels:
                if cancel is not None: raise self.err(case, 'cancel is answered above')
                cancel = case.body; continue
            for v in labels:
                if v in bodies: raise self.err(case, f'option "{v}" is answered above')
                bodies[v] = case.body
        out = [f'{I}choice{self.menu_owner(call)} {{']
        for k in call.keywords:
            out += [f'{I}    {self.page_arg_opt(k.value, self.opt_ctx(call, k.arg))}{" or cancel" if k.arg == both else ""} => {{'] + self.block(bodies.get(k.arg, []), ind + 2) + [f'{I}    }}']
        if cancel is not None:
            out += [f'{I}    cancel => {{'] + self.block(cancel, ind + 2) + [f'{I}    }}']
        return self.tidy_choice(out + [f'{I}}}'])

    # ------------------------------------------------------------ calls
    def call(self, c, ind):
        I = '    ' * ind; f = c.func; m = self.m
        kw = {k.arg: k.value for k in c.keywords}
        name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
        recv = f.value if isinstance(f, ast.Attribute) else None
        def W(): return self.who(c)
        # hatches
        if isinstance(f, ast.Name) and name == 'dws':
            if len(c.args) != 1 or not isinstance(c.args[0], ast.Constant) or not isinstance(c.args[0].value, str):
                raise self.err(c, 'dws("""...""") takes one string of DWS statements')
            lines = c.args[0].value.split('\n')
            lines = [l for l in lines]
            while lines and not lines[0].strip(): lines.pop(0)
            while lines and not lines[-1].strip(): lines.pop()
            ind0 = min((len(l) - len(l.lstrip()) for l in lines if l.strip()), default=0)
            return [(I + l[ind0:]) if l.strip() else '' for l in lines]
        if isinstance(recv, ast.Name) and recv.id == 'raw':
            return [f'{I}{name}({", ".join(self.raw_arg(a) for a in c.args)});']
        # a shared def called as a statement: its body in place (a shared block ends like an event, with END_SECTION, so a
        # gosub to it would end the handler there and the code after the call would never run)
        # A routine with jump_return must keep its call frame, even when only one branch returns to the caller.
        # Inlining it would make that return exit the calling event before its remaining statements.
        if (isinstance(f, ast.Name) and name in m.shared and not c.args and not c.keywords
                and not ends_handler(m.shared[name].body) and not returns_to_caller(m.shared[name])):
            return self.inline(c, ind)
        # calls of the other shared defs and of handlers: a subroutine call (gosub)
        if not c.args and not c.keywords and (isinstance(f, ast.Name) and (name in m.shared or re.fullmatch(r'enter|step\d+|use\d+|sec\d+', name or ''))
                                              or (isinstance(f, ast.Attribute) and name == 'talk' and isinstance(recv, ast.Name) and recv.id in m.npcs)):
            return [f'{I}gosub {self.jump_target(c)};']
        if isinstance(f, ast.Name) and name in m.fns: return self.inline(c, ind)
        # object methods
        if isinstance(f, ast.Attribute) and name in ('set', 'clear', 'add', 'sub') and not self.is_entity(recv):
            tgt = self.state(recv)
            if name in ('set', 'clear') and not c.args:
                if tgt.startswith('trigger('): return [f'{I}{"set_trigger" if name == "set" else "clear_trigger"}({tgt[8:-1]});']
                return [f'{I}{tgt} = {"true" if name == "set" else "false"};']
            if len(c.args) != 1: raise self.err(c, f'{name}(n)')
            if self.is_clock(c.args[0]):                       # last_day.set(clock.day): the clock read now, kept in the counter
                if name != 'set': raise self.err(c, f'the clock is kept with .set(clock.{c.args[0].attr})')
                pre = []; v = self.operand(c.args[0], pre)
                return [I + p for p in pre] + [f'{I}{tgt} = {v};']
            return [f'{I}{tgt} {"=" if name == "set" else "+=" if name == "add" else "-="} {self.val(c.args[0])};']
        if isinstance(f, ast.Attribute) and isinstance(recv, ast.Subscript) and isinstance(recv.value, ast.Name) and recv.value.id == 'objects':
            n = m.int_const(recv.slice)
            if name in ('show', 'hide'): return [f'{I}set_obj_visibility({n}, {1 if name == "show" else 0});']
            if name == 'animate' and len(c.args) == 1:
                return [f'{I}engine.object = {n};', f'{I}engine.animation = {m.int_const(c.args[0])};',
                        f'{I}call_routine(routine("reset_object_animation"));']
            raise self.err(c, 'objects[n].show() / .hide() / .animate(k)')
        if isinstance(recv, ast.Name) and recv.id in ('partner', 'tamer') and name in ('set', 'add', 'sub') and kw and not c.args:
            from .view import STAT_NAMES, TAMER_LEVEL
            ids = {v: k for k, v in STAT_NAMES.items()} if recv.id == 'partner' else {'level': TAMER_LEVEL}
            out = []
            for k, v in kw.items():
                if k not in ids: raise self.err(c, f'no {recv.id} stat "{k}"', ', '.join(ids))
                out.append(f'{I}{ {"set": "set_stat", "add": "add_stat", "sub": "reduce_stat"}[name] }({ids[k]}, {self.val(v)});')
            return out
        if isinstance(recv, ast.Name) and recv.id == 'sound' and name == 'jingle' and not c.args:
            return [f'{I}sound(8, 11);']
        if isinstance(recv, ast.Name) and recv.id == 'camera':
            if name == 'arrived': return [f'{I}await camera;']
            if name == 'on': return [f'{I}camera_on({self.ent(c.args[0])}' + (f', speed: {self.val(kw["speed"])}' if 'speed' in kw else '') + ');']
            if name == 'to': return [f'{I}camera_to({self.val(c.args[0])}, {self.val(c.args[1])}' + (f', speed: {self.val(kw["speed"])}' if 'speed' in kw else '') + ');']
        if name == 'say':
            w = W(); n = len(c.args)
            args = [self.page_arg(a, {'kind': 'line', 'who': self.who_label(w), 'page': k + 1, 'of': n}) for k, a in enumerate(c.args)]
            if n > 1 and len({a.lineno for a in c.args}) > 1:       # pages on lines of their own: each keeps its line (a warning points there)
                out = [f'{I}say({w}, {args[0]},']
                out += [f'{I}    {x}{"," if k < n - 2 else ");"}    // @py {a.lineno}' for k, (x, a) in enumerate(zip(args[1:], c.args[1:]))]
                return out
            return [f'{I}say({w}, {", ".join(args)});']
        if name == 'arrived': return [f'{I}await {W()};']
        if name in ('walk', 'run'):
            w = W(); cam = ', camera: true' if isinstance(kw.get('camera'), ast.Constant) and kw['camera'].value is True else ''
            out = [f'{I}{name}({w}, {self.val(c.args[0])}, {self.val(c.args[1])}{cam});']
            if not (isinstance(kw.get('wait'), ast.Constant) and kw['wait'].value is False): out.append(f'{I}await {w};')
            return out
        if name == 'play':
            w = W(); out = [f'{I}animate({w}, {self.val(c.args[0])});']
            if isinstance(kw.get('wait'), ast.Constant) and kw['wait'].value is True: out.append(f'{I}await {w};')
            return out
        if name == 'face': return [f'{I}face({W()}, {self.ent(c.args[0])});']
        if name == 'turn': return [f'{I}rotate({W()}, {self.val(c.args[0])});']
        if name == 'leave': return [f'{I}remove({W()});']
        if name == 'walk_away':
            extra = (f', looks: {self.val(kw["looks"])}' if 'looks' in kw else '') + (f', pause: {self.ms(kw["pause"], c)}' if 'pause' in kw else '')
            return [f'{I}walk_away({W()}, {self.val(c.args[0])}, {self.val(c.args[1])}{extra});']
        if name == 'send_to_city':
            w = W(); sp = self.val(kw['species']) if 'species' in kw else self.own_species(w, c)
            snd = kw.get('sound'); b, n = (self.val(snd.elts[0]), self.val(snd.elts[1])) if isinstance(snd, ast.Tuple) else ('8', '11')
            cam = not (isinstance(kw.get('camera'), ast.Constant) and kw['camera'].value is False)
            pros = f', prosperity: {self.val(kw["prosperity"])}' if 'prosperity' in kw else ''
            return [f'{I}{"join_city_camera" if cam else "join_city"}({w}, {sp}, {b}, {n}, {self.page_arg(kw["line"])}{pros});']
        if isinstance(f, ast.Attribute): raise self.err(c, f'unknown verb "{name}"')
        # module functions
        if name == 'load': return [f'{I}load_digimon({self.val(c.args[0])});']
        if name == 'spawn':
            at = 1 if isinstance(kw.get('autotalk'), ast.Constant) and kw['autotalk'].value is True else 0
            return [f'{I}set_digimon({self.val(c.args[0])}, {m.int_const(kw["slot"])}, {at});']
        if name == 'music': return [f'{I}music({self.val(c.args[0])});']
        if name == 'use_script': return [f'{I}set_script({self.val(c.args[0])}, {self.val(c.args[1])});']
        if name == 'jump_to_script': return [f'{I}jump_to_file({self.val(c.args[0])}, {self.val(c.args[1])});']
        if name == 'spawn_chest':
            if self.kind == 'talk' and self.m.mode == 'mod':
                raise self.err(c, 'a chest is spawned in the screen\'s setup: on_enter (as the game\'s 71 chests)',
                               'set a flag in the talk and spawn the chest in @screen.on_enter(when=that_flag): it is there the '
                               'next time the tamer enters')
            return [f'{I}{self.chest(c, kw)}']
        if name == 'recruitable':
            who = self.ent(c.args[0]); sp = self.val(kw['joins']) if 'joins' in kw else self.own_species(who, c)
            out = [f'{I}say({who}, {self.page_arg(kw["line"])});', f'{I}battle();']
            from .. import recruitment
            if not recruitment.ACTIVE.get(): return out + [f'{I}recruit({sp});']
            return out + (recruitment.announcement(sp, I, won=True)
                          if int(sp[8:-1]) in recruitment.roster() else [])
        if name == 'join_city': raise self.err(c, 'join_city(...) is now recruit(...) (it pairs with recruited(...))')
        if name == 'recruit':
            sp = self.val(c.args[0])
            out = [f'{I}recruit({sp});']
            from .. import recruitment
            if recruitment.ACTIVE.get():
                sid = int(sp[8:-1])
                if sid in recruitment.roster() and not self.recruit_visible:
                    out = recruitment.announcement(sp, I, won=self.recruit_battle)
                elif 0 <= sid < 112 and sid not in recruitment.roster():
                    if int(BE.DIGI_DATA[sid]['level']) >= 3:
                        return []
            if 'prosperity' in kw: out.append(f'{I}engine.prosperity += {self.val(kw["prosperity"])};')
            return out
        if name == 'unrecruit': return [f'{I}unrecruit({self.val(c.args[0])});']
        if name == 'fight':
            if not c.args:
                if 'escape' in kw:     # (the open battle: any Digimon on screen may join it, and it can always be fled)
                    raise self.err(c, 'fight() with no foes named is the open battle: escape= does nothing there, and the other Digimon on screen may join it',
                                   'name the foes: fight(hunter, escape=False)')
                return [f'{I}battle();']
            esc = not (isinstance(kw.get('escape'), ast.Constant) and kw['escape'].value is False)
            return [f'{I}battle(foes: [{", ".join(self.ent(a, "fight") for a in c.args)}]{", escape: true" if esc else ""});']
        if name == 'wait':
            if 'ticks' in kw: raise self.err(c, 'wait(ticks=n) is gone: every time is in ms', f'wait({m.int_const(kw["ticks"]) * TICK_MS})')
            return [f'{I}wait({self.ms(c.args[0], c)});']
        if name == 'sound': return [f'{I}sound({self.val(c.args[0])}, {self.val(c.args[1])});']
        if name in ('give', 'take'):
            out = []
            if c.args:
                n = f', {self.val(c.args[1])}' if len(c.args) > 1 else ''
                a0 = c.args[0]
                if isinstance(a0, ast.Call) and isinstance(a0.func, ast.Name) and a0.func.id == 'Card':
                    out.append(f'{I}{name}_card({m.int_const(a0.args[0])});')
                else: out.append(f'{I}{name}({self.val(a0)}{n});')
            if 'bits' in kw: out.append(f'{I}{name}_bits({self.val(kw["bits"])});')
            return out
        if name == 'learn': return [f'{I}learn({self.val(c.args[0])});']
        if name in ('fade_to_white', 'fade_from_white'):           # (the frames go in engine.arg, as story/core/scene.dws does)
            return [f'{I}engine.arg = {self.ms(c.args[0], c)};', f'{I}call_routine(routine("{name}"));']
        if name == 'hide_hud': return [f'{I}hide_hud();']
        if name == 'warp':
            if 'exit' in kw: raise self.err(kw['exit'], 'warp(..., exit=k) is now entry=k: where the tamer arrives on that screen',
                                            'python3 tools/dws.py slots SCREEN lists the entries')
            then = self.val(kw['then']) if 'then' in kw else '255'
            if self.m.mode == 'mod' and 'entry' in kw and c.args:
                try: target, k = int(self.val(c.args[0])), self.m.int_const(kw['entry'])
                except (PyError, ValueError): target = None
                if target is not None: self.m.check_entry(target, k, kw['entry'])
            to, k = self.val(c.args[0]), self.val(kw["entry"]) if "entry" in kw else "0"
            wide = to.isdigit() and int(to) > 255                       # a new screen (300...): the builtin picks the 16-bit opcode
            return [f'{I}warp({to}, exit: {k}, section: {then});' if wide else f'{I}warp_to({to}, {k}, {then});'] + \
                ([f'{I}return;'] if self.before else [])
        if name == 'advance':
            if len(c.args) != 1 or not isinstance(c.args[0], ast.Attribute) or not isinstance(c.args[0].value, ast.Name) \
                    or c.args[0].value.id not in m.quests:
                raise self.err(c, 'advance(Quest.STAGE)')
            q = c.args[0].value.id; v = m.stage_index(q, c.args[0])
            return [f'{I}{q}_b{j} = {"true" if v >> j & 1 else "false"};' for j in range(m.quests[q]['bits'])]
        if name == 'spawn_item': return [f'{I}{self.ground_item(c, kw)}']
        if name == 'swing_door': return [f'{I}rotate_3d_object({m.int_const(c.args[0])}, 0, 1);']
        if name == 'pick_item': return [f'{I}engine.picker_mode = true;', f'{I}call_routine(routine("choose_item"));']
        if name == 'shop': return self.shop(c, kw, I)
        if name == 'take_picked':
            every = isinstance(kw.get('all'), ast.Constant) and kw['all'].value is True
            return [f'{I}call_routine(routine("{"remove_all_chosen_item" if every else "remove_chosen_item"}"));']
        if name == 'call':
            out = [f'{I}engine.arg = {self.val(kw["arg"])};'] if 'arg' in kw else []
            return out + [f'{I}call_routine({self.val(c.args[0])});']
        raise self.err(c, f'unknown function "{name}"', 'see typings/dw/__init__.pyi (the story language), or raw.<command>(...)')

    SHOP_STOCK = 384                              # trigger 0x180 + item id: the items the shop sells (openShop, script_common.c)

    def shop(self, c, kw, I):
        """`shop(Item.A, Item.B)`: the NPC being talked to opens its shop with these items. The game's own form: the stock
        triggers set, picker mode off (buy, not sell), the routine with the owner's entity in engine.arg (whose box the
        menu's lines are in, and which keeper's lines: SHOPKEEP_DIGIMON_TYPES, the default keeper's otherwise), the
        triggers cleared."""
        if self.self_npc is None:
            raise self.err(c, '`shop(...)` is opened by the NPC being talked to: it goes in an on_talk handler')
        if kw or not c.args: raise self.err(c, 'shop(Item.A, Item.B, ...): the items it sells')
        ids = [self.m.enum_id('item', a) for a in c.args]
        bad = next((a for k, a in enumerate(c.args) if not 0 <= ids[k] < 128), None)
        if bad is not None: raise self.err(bad, 'a shop sells the items 0-127 (Item.X)')
        dup = next((a for k, a in enumerate(c.args) if ids[k] in ids[:k]), None)
        if dup is not None: raise self.err(dup, 'this item is already in the shop')
        ent = self.m.npcs[self.self_npc]['entity']
        tag = re.sub(r'\W', '_', os.path.splitext(os.path.basename(self.m.path))[0])     # (one name per file: two files' shops may share an item)
        for i in ids: self.m.aliases_dws.add(f'alias flag py_stock_{tag}_{i} = {self.SHOP_STOCK + i};')     # (the game's own triggers, named)
        return [f'{I}py_stock_{tag}_{i} = true;' for i in ids] + \
            [f'{I}engine.picker_mode = false;', f'{I}engine.arg = {ent};', f'{I}call_routine(routine("shop"));'] + \
            [f'{I}py_stock_{tag}_{i} = false;' for i in ids]

    CHEST_FACING = (0, 1024, 2048, 3072)          # the four directions spawnChest knows (map_object.c: where it opens)

    def chest(self, c, kw):
        """`spawn_chest(Item.X, at=(x, z), opened=flag, facing=0)` -> SPAWN_CHEST item, x, 0, z, facing, the flag's trigger."""
        form = 'spawn_chest(Item.X, at=(x, z), opened=a_flag, facing=0)'
        if len(c.args) != 1 or set(kw) - {'at', 'opened', 'facing'} or 'at' not in kw or 'opened' not in kw:
            raise self.err(c, f'a chest is {form}', '`opened` is set when it is taken (a flag() of the mod, or trigger(n)); '
                                                    '`facing`: 0, 1024, 2048 or 3072 (4096 = a full turn), 0 when left out')
        at = kw['at']
        if not (isinstance(at, ast.Tuple) and len(at.elts) == 2): raise self.err(at, 'at=(x, z)')
        facing = self.m.int_const(kw['facing']) if 'facing' in kw else 0
        if facing not in self.CHEST_FACING:
            raise self.err(kw['facing'], f'facing={facing}: a chest faces 0, 1024, 2048 or 3072 (4096 = a full turn)')
        o = kw['opened']
        if isinstance(o, ast.Call) and isinstance(o.func, ast.Name) and o.func.id == 'trigger': opened = str(self.m.int_const(o.args[0]))
        elif isinstance(o, ast.Name) and o.id in self.m.flags: opened = o.id
        elif isinstance(o, (ast.Name, ast.Attribute)): opened = self.state(o)
        else: raise self.err(o, 'opened= takes a flag: a flag() of the mod, or trigger(n)')
        return (f'spawn_chest({self.val(c.args[0])}, {self.m.int_const(at.elts[0])}, 0, {self.m.int_const(at.elts[1])}, {facing}, '
                f'{opened});')

    def ground_item(self, c, kw):
        """`spawn_item(Item.X, at=(x, z))`: an item on the ground (picked up when the tamer passes by), at (x, z) in world units
        like every position; SPAWN_ITEM takes the tile, whose centre the item is drawn at (spawnItem, item.c)."""
        import dwmap
        form = 'spawn_item(Item.X, at=(x, z))'
        if len(c.args) != 1 or set(kw) != {'at'}:
            hint = 'at=(x, z) is a point in world units, as npc(at=) and spawn_chest(at=)'
            if len(c.args) == 3 and not kw:
                try:
                    tx, tz = self.m.int_const(c.args[1]), self.m.int_const(c.args[2])
                    if 0 <= tx < 100 and 0 <= tz < 100:
                        hint = f'the tile ({tx}, {tz}) is at={dwmap.tile_to_world(tx, tz)}; ' + hint
                except PyError: pass
            raise self.err(c, f'an item on the ground is {form}', hint)
        at = kw['at']
        if not (isinstance(at, ast.Tuple) and len(at.elts) == 2): raise self.err(at, 'at=(x, z)')
        x, z = self.m.int_const(at.elts[0]), self.m.int_const(at.elts[1])
        tx, tz = dwmap.world_to_tile(x, z)
        if not (0 <= tx < 100 and 0 <= tz < 100): raise self.err(at, f'({x}, {z}) is outside the map (x and z are -5000..4999)')
        return f'spawn_item({self.val(c.args[0])}, {tx}, {tz});'

    def ms(self, a, node):
        """A time in ms -> the game's ticks (20 a second: 50 ms each); a time off that grid is an error."""
        ms = self.m.int_const(a)
        if ms % TICK_MS: raise self.err(node, f'{ms} ms: the game counts time in steps of {TICK_MS} ms (20 ticks a second)',
                                        f'{ms // TICK_MS * TICK_MS} or {ms // TICK_MS * TICK_MS + TICK_MS}')
        return ms // TICK_MS

    def is_entity(self, r):
        return isinstance(r, ast.Name) and (r.id in self.m.npcs or r.id in ('tamer', 'partner', 'narrator'))

    def own_species(self, who, node):
        d = self.m.npcs.get(who)
        if d is None or d['species'] is None:
            raise self.err(node, f'the species of "{who}" is not known here: write species=Species.X')
        return f'species({d["species"]})'

    def raw_arg(self, a):
        if isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name) and a.value.id == 'DigimonRoutine':
            return f'routine("{a.attr}")'
        return self.val(a)

    def inline(self, c, ind):
        """A def is inlined at each call: its body with the arguments in place of the parameters."""
        fn = self.m.fns.get(c.func.id) or self.m.shared[c.func.id]
        params = [a.arg for a in fn.args.args]
        defaults = dict(zip(params[len(params) - len(fn.args.defaults):], fn.args.defaults))
        if len(c.args) > len(params): raise self.err(c, f'{fn.name}() takes {len(params)} argument(s)')
        given = dict(zip(params, c.args))
        for k in c.keywords:
            if k.arg not in params:
                raise self.err(c, f'{fn.name}(): unexpected keyword argument "{k.arg or "**"}"')
            if k.arg in given:
                raise self.err(c, f'{fn.name}(): multiple values for argument "{k.arg}"')
            given[k.arg] = k.value
        for p in params:
            if p not in given:
                if p in defaults: given[p] = defaults[p]
                else: raise self.err(c, f'{fn.name}(): missing argument "{p}"')
        stack = self.__dict__.setdefault('inlining', [])
        if fn.name in stack: raise self.err(c, f'{fn.name}() calls itself: the game has no recursion')
        class Sub(ast.NodeTransformer):
            def visit_Name(self, n):
                return given[n.id] if n.id in given and isinstance(n.ctx, ast.Load) else n
        import copy
        body = [Sub().visit(copy.deepcopy(st)) for st in fn.body]
        # (a shared def's `return` ends the handler, as its gosub'd block always did; a def with parameters must not)
        if fn.name in self.m.fns and any(isinstance(n, ast.Return) and n.value is None for st in body for n in ast.walk(st)):
            raise self.err(c, f'{fn.name}(): `return` inside an inlined def would end the whole handler', 'use if/else instead')
        stack.append(fn.name)
        try: return self.block(body, ind)
        finally: stack.pop()


# --------------------------------------------------------------------- files
SPEAKER_VERBS = ('say', 'walk', 'run', 'play', 'face', 'turn', 'leave', 'arrived', 'walk_away', 'send_to_city', 'shop')


def returns_to_caller(fn):
    """A shared routine using JUMP_RETURN needs a gosub frame, including returns inside branches or DWS hatches."""
    for n in ast.walk(fn):
        if not isinstance(n, ast.Call): continue
        f = n.func
        if (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
                and f.value.id == 'raw' and f.attr == 'jump_return'): return True
        if (isinstance(f, ast.Name) and f.id == 'dws' and n.args and isinstance(n.args[0], ast.Constant)
                and re.search(r'\bjump_return\s*\(', str(n.args[0].value))): return True
    return False


def ends_handler(body):
    """Does this block always end the handler (its last statement a `return`, a warp or dws("return;"))?"""
    if not body: return False
    st = body[-1]
    if isinstance(st, ast.Return): return True
    if isinstance(st, ast.If): return ends_handler(st.body) and ends_handler(st.orelse)
    if isinstance(st, ast.Expr) and isinstance(st.value, ast.Call) and isinstance(st.value.func, ast.Name):
        f, a = st.value.func.id, st.value.args
        if f == 'warp': return True
        if f == 'dws' and a and isinstance(a[0], ast.Constant) and re.search(r'\breturn\s*;\s*$', str(a[0].value)): return True
    return False


def speaks(fn):
    """Does a def use a verb without a speaker (`say(...)`: the NPC being talked to)? Then it is inlined where it is called
    (a shared block, compiled once, would not know who speaks)."""
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in SPEAKER_VERBS for n in ast.walk(fn))


_MAPS = {}


def map_file(screen):
    """The screen's .MAP of the disc (dwmap.MapFile), or None. A mod that retouches a game screen's map (a new exit, new
    trigger tiles) names the folder of its retouched maps in DWS_MAPS (':'-separated): the checks read those first."""
    if screen not in _MAPS:
        import dwmap
        src = BE.map_source(screen)
        name = os.path.basename(src) if src else None
        for d in BE.MAPS_DIRS:
            if name and os.path.exists(os.path.join(d, name)): src = os.path.join(d, name); break
        _MAPS[screen] = dwmap.MapFile(open(os.path.join(ROOT, src), 'rb').read()) if src else None
    return _MAPS[screen]


def map_triggers(screen):
    """{collision value} of the screen's .MAP (51-79: step triggers, 80-109: use triggers), or None without a map."""
    m = map_file(screen)
    return None if m is None else set(m.collision)


_PARTNER_LEVELS = {}


def partner_levels():
    """{species id: level 1-6} of every species of content/species with a `partner` block (what a partner can be on a
    built executable)."""
    if not _PARTNER_LEVELS:
        import glob, json
        num = {'fresh': 1, 'in-training': 2, 'rookie': 3, 'champion': 4, 'ultimate': 5, 'mega': 6}
        for f in glob.glob(os.path.join(ROOT, 'content', 'species', '*.json')):
            try: d = json.load(open(f, encoding='utf-8'))
            except (OSError, ValueError): continue
            if 'partner' in d and d.get('level') in num and isinstance(d.get('id'), int): _PARTNER_LEVELS[d['id']] = num[d['level']]
    return _PARTNER_LEVELS


def read_now(pre):
    """What the statements a test needs first read (STORE_RANDOM, STORE_DATE, a battle...), in words."""
    what = []
    for p in pre:
        if p.startswith(('py_', 'if (py_')): continue          # (the arithmetic of `clock.day - x`, after its store_date)
        w = ('a random draw' if p.startswith('store_random') else 'the clock' if p.startswith('store_date') else
             "the partner's species" if p.startswith('store_digimon_type') else 'a battle' if p.startswith('battle') else 'a value')
        if w not in what: what.append(w)
    return ' and '.join(what)


NEG_CMP = {'==': '!=', '!=': '==', '<': '>=', '>=': '<', '>': '<=', '<=': '>'}


def font_problems(text):
    """The characters of a line the target's font (the original executable's 79 glyphs: letters, digits and
    ` . , ? ! ' " : ; + - = \\`; the mod executables add á é ñ ¿ ¡ ç · « » and ( ) & % / … [ ] # * ~ @ – — ♪, as many as the
    target's build has, BE.set_font) lacks -> ([(message, hint)], [characters drawn plain]). Escapes ({player}) are skipped."""
    from dws import bytecode
    words = re.sub(r'\{[^}]*\}', '', text)
    bad = []; plain = []
    for c in words:
        if c.isspace() or c in bytecode.CHAR2SJIS or c in BE.FONT['chars']: continue
        d = BE.strip_char(c)
        if d != c and all(x in bytecode.CHAR2SJIS for x in d): plain.append(c)
        elif c not in bad: bad.append(c)
    newer = [c for c in bad if c in BE.EXTRA_CHARS]; none = [c for c in bad if c not in BE.EXTRA_CHARS]
    has = lambda cs: ' '.join(f'`{c}`' for c in cs) + (' has' if len(cs) == 1 else ' have')
    out = []
    if none:
        out.append((has(none) + ' no glyph in the game\'s font: a line uses letters, digits, spaces and '
                    '. , ? ! \' " : ; + - =, and with --exe mods, species or story-state also ( ) & % / … [ ] # * ~ @ – — ♪ '
                    'and the accents (docs/mods/font.md)',
                    'write "and" for "&"; "..." or … for an ellipsis; ask for a glyph in tools/font/extra.txt'))
    if newer and not BE.FONT['extra']:
        out.append((has(newer) + ' no glyph in the original executable\'s font: the mod executables have '
                    + ('it' if len(newer) == 1 else 'them') + ' (--exe mods, species or story-state)',
                    'write "Join, 500 bits" for "Join (500 bits)", "and" for "&", "50 percent" for "50%"; '
                    'or build for a mod executable (docs/mods/font.md)'))
    elif newer:
        out.append((has(newer) + f' no glyph in {BE.FONT["of"]}: it has {BE.FONT["glyphs"]} extra glyphs, '
                    'built before ' + ('this one was' if len(newer) == 1 else 'these were') + ' added',
                    'rebuild that executable (patch 0024 has ( ) & % / … [ ] # * ~ @ – — ♪ since 2026-10-14: '
                    'tools/mods.sh prepare and build; docs/mods/font.md)'))
    return out, list(dict.fromkeys(plain))


def plain_note(plain):
    drop = [c for c in plain if not BE.strip_char(c)]
    shown = [f'{c} as {BE.strip_char(c)}' for c in plain if BE.strip_char(c) and not BE.strip_char(c).isalpha()]
    what = ('accents' if all(c in BE.EXTRA_ORDER[:29] for c in plain) else 'glyphs for them')
    whose = 'the original executable\'s font' if not BE.FONT['extra'] else f'the font of {BE.FONT["of"]}'
    return (f'{" ".join(plain)}: {whose} has no {what}, so they are drawn plain'
            + (f' ({", ".join(shown + [" ".join(drop) + " left out"] if drop else shown)})' if shown or drop else '')
            + ('; --exe mods, species or story-state keeps them' if not BE.FONT['extra'] else '; a rebuild of it keeps them'))


ESCAPE = re.compile(r'(?<!\\)\{([^{}]*)\}')        # (`\{` is bytecode's literal brace)
ESCAPE_ENUM = {'item': ('Item', 'item'), 'move': ('Tech', 'tech')}


def escape_problems(text):
    """What is wrong with the escapes of a line: [message]. {item Item.X} and {move Tech.X} name the thing; a number is the id."""
    from dws import bytecode
    out = []
    for m in ESCAPE.finditer(text):
        body = m.group(1).strip(); name, _, arg = body.partition(' '); arg = arg.strip()
        if name in ('raw', 'sjis'): continue
        if name not in bytecode.CTRLNAME:
            near = difflib.get_close_matches(name, list(bytecode.CTRLNAME), 1)
            out.append(f'unknown escape {{{body}}}' + (f': did you mean {{{near[0]}{" ..." if bytecode.CTRLNAME[near[0]][1] else ""}}}?' if near else ''))
            continue
        takes = bytecode.CTRLNAME[name][1]
        if not takes:
            if arg: out.append(f'{{{name}}} takes nothing: {{{body}}}')
            continue
        if name in ESCAPE_ENUM and arg.startswith(ESCAPE_ENUM[name][0] + '.'):
            member = arg.split('.', 1)[1]; ids = enum_ids(ESCAPE_ENUM[name][1])
            if member not in ids:
                near = difflib.get_close_matches(member, list(ids), 1)
                out.append(f'no {ESCAPE_ENUM[name][0]}.{member} in {{{body}}}' + (f': did you mean {ESCAPE_ENUM[name][0]}.{near[0]}?' if near else ''))
            continue
        if not re.fullmatch(r'\d+', arg) or int(arg) > 255:
            out.append(f'{{{body}}}: {{{name} N}} takes a number 0-255' + (f' or {ESCAPE_ENUM[name][0]}.X' if name in ESCAPE_ENUM else ''))
    return out


def resolve_escapes(text):
    """{item Item.Digimushrm} -> {item 44} (and {move Tech.X}): what the game reads. Anything else is left as it is."""
    def one(m):
        body = m.group(1).strip(); name, _, arg = body.partition(' '); arg = arg.strip()
        if name in ESCAPE_ENUM and arg.startswith(ESCAPE_ENUM[name][0] + '.'):
            i = enum_ids(ESCAPE_ENUM[name][1]).get(arg.split('.', 1)[1])
            if i is not None: return f'{{{name} {i}}}'
        return m.group(0)
    if isinstance(text, str): return ESCAPE.sub(one, text) if '{' in text else text
    return [resolve_escapes(x) for x in text]


HASH_KEY = re.compile(r'^(.+)\.([0-9a-f]{8})$')


def named_keys(en, mod):
    """The named lines of a mod's text/en.json: its keys that are not `_about`-like nor the hash keys `text sync` writes."""
    return {k: v for k, v in (en or {}).items() if not k.startswith('_') and not (HASH_KEY.match(k) and HASH_KEY.match(k).group(1) == mod)}


def text_key(mod, words):
    """The key of a new line of a mod: <mod>.<sha1 of the normalised words>[:8] (spaces collapsed)."""
    import hashlib
    norm = ' '.join(words.split())
    return f'{mod}.{hashlib.sha1(norm.encode("utf-8")).hexdigest()[:8]}'


# (DWS_LOWERED: another folder, for a build that runs several story passes at once: tools/derive's story step)
LOWERED = os.environ.get('DWS_LOWERED') or os.path.join(ROOT, 'build', 'py-lowered')


def lowered_path(path, part):
    """Where the DWS of a .py file goes (its script part, MAPHEAD part, declarations)."""
    tag = re.sub(r'\W+', '_', os.path.relpath(os.path.abspath(path), ROOT))
    return os.path.join(LOWERED, f'{tag}.{part}.dws')


LINEMAP = {}          # lowered DWS path -> (the .py path from the root, {lowered line: .py line}, the .py path as given)


def py_linemap(lowered, py_path, text, given=None):
    """Records which .py line each line of a lowered file comes from (the last `// @py N` at or above it): the source map
    of videos and traces, and of the compiler's errors (build.source_pos: an error is reported at the .py line)."""
    m = {}; cur = None
    for k, l in enumerate(text.split('\n'), 1):
        mm = re.search(r'// @py (\d+)$', l)
        if mm: cur = int(mm.group(1))
        if cur is not None: m[k] = cur
    LINEMAP[os.path.abspath(lowered)] = (py_path, m, given or py_path)


def lower_file(path, src=None, base=None, claims=None):
    """-> (Module, script DWS text or None, MAPHEAD DWS text or None); the declarations, if any, are in m.decl_text.
    `claims`: the new NPCs of the files compiled with it (one Claims per run; a file alone gets its own)."""
    m = Module(path, src, base, claims).read()
    try:
        s, h, d = m.lower()
    except PyError as e:
        m.errors.append(e); s = h = d = None
    if m.errors:
        errs = sorted(m.errors, key=lambda e: (e.pos or ('', 0, 0))[1:])
        raise errs[0] if len(errs) == 1 else PyErrors(errs)
    m.decl_text = d
    return m, s, h


def lower_base(base, out, log=None):
    """Every view of `base` (script.py, maphead/hooks.py) lowered into `out` with the same layout (script.dws, maphead/hooks.dws).
    -> (script files, MAPHEAD files)"""
    import glob
    scripts = []; mhs = []
    for p in sorted(glob.glob(os.path.join(base, 'zones', '*', '*', 'script.py'))):
        rel = os.path.relpath(os.path.dirname(p), base)
        _, s, h = lower_file(p, base=base)
        d = os.path.join(out, rel); os.makedirs(d, exist_ok=True)
        if s: open(os.path.join(d, 'script.dws'), 'w', encoding='utf-8').write(s); scripts.append(os.path.join(d, 'script.dws'))
        if h: raise PyError(f'{p}: MAPHEAD sections belong in maphead/hooks.py', None)
    hp = os.path.join(base, 'maphead', 'hooks.py')
    _, s, h = lower_file(hp, base=base)
    os.makedirs(os.path.join(out, 'maphead'), exist_ok=True)
    if h: open(os.path.join(out, 'maphead', 'hooks.dws'), 'w', encoding='utf-8').write(h); mhs.append(os.path.join(out, 'maphead', 'hooks.dws'))
    return scripts, mhs


def check_base(base, lifted, mhl, log=print):
    """`story-base --check`: every view of `base` lowered and proven against the original sections it was lifted from (the
    beautifier's own proof, readable.check_file: flowcmp of each event and shared block). -> (events proven, [errors])"""
    import glob, shutil, tempfile
    from .. import readable
    tmp = tempfile.mkdtemp(prefix='pycheck-', dir=os.path.join(ROOT, 'build'))
    proven = 0; errors = []
    try:
        scripts, mhs = lower_base(base, tmp)
        by_dir = {os.path.basename(os.path.dirname(p)): p for p in scripts}
        for sid, lst in sorted(lifted.items()):
            d = next((k for k in by_dir if re.match(rf's{sid:03d}(-|$)', k)), None)
            if d is None: errors.append(f'script {sid}: no view'); continue
            try: proven += readable.check_file(by_dir[d], lst, 'script', sid)
            except Exception as e: errors.append(f'script {sid}: {e}')
        if mhl:
            try: proven += readable.check_file(mhs, mhl, 'maphead')
            except Exception as e: errors.append(f'MAPHEAD: {e}')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    log(f'story: the Python view lowered and proven: {proven} events and shared blocks equivalent to the disc'
        + (f'; {len(errors)} script(s) not: ' + '; '.join(errors[:5]) if errors else ''))
    return proven, errors
