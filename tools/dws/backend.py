"""Patching back end of the DWS compiler: what turns generated event code into a modified game.

Given the events of a program (script, section, assembly text), this module

* inserts them into / replaces sections of the original scripts (the disassembly of DG.SCN, cached in
  build/scn-dis, edited as text and assembled again by tools/dws/bytecode/__main__.py);
* creates new scripts for screens (`script new`) and points MAPHEAD at them;
* places Digimon (`place`): .MAP entries, MAPHEAD setup, default wild battles, memory budget check;
* knows the font (accents only on the mod executable), text wrapping and quoting;
* names the executables a disc can be built with.

`build.py` drives it; `gen.py` produces the events."""
import csv, glob, json, os, re, shutil, sys, unicodedata
from .alloc import FREE_TRIGGERS, FREE_SAVED_PSTATS, FREE_TEMP_PSTATS

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOLS = os.path.join(ROOT, 'tools')
if TOOLS not in sys.path: sys.path.insert(0, TOOLS)
SRCMAP = False                                          # dws --srcmap: statements carry `;@src FILE:LINE` marks (comments to the assembler)
DIS_CACHE = os.path.join(ROOT, 'build/scn-dis')          # disassembly of the original DG.SCN
DIS_DEFAULT = DIS_CACHE
RUN_ROOT = os.environ.get('DWS_RUN_ROOT') or os.path.join(ROOT, 'build/dws')               # one run-* directory per build
DG_SCN = os.path.join(ROOT, 'extracted/SCN/DG.SCN')         # (the disc's scripts: `dws build`, story-base --refresh; not the story build)
DG_SCN_SIZE = 0xC4800                                     # bytes of the USA DG.SCN (FILE_OFFSET_TABLE, file_table_us.c): the story build's container
MODS_EXE_DIR = 'build/decomp-mods/build/us/psx/gcc'           # the mods branch, built with GCC
SPECIES_EXE_DIR = 'build/decomp-int/build/us/psx/gcc'         # species beyond 180 (tools/species.py): the integration worktree (series, patch 0065)
STORY_STATE_EXE_DIR = 'build/decomp-story-state/build/us/psx/gcc'         # the story-state engine (docs/mods/story-state-engine.md)
FIRST_NEW_SCRIPT = 222                                    # DG.SCN has entries 0-221
MAPHEAD_SCN = os.path.join(ROOT, 'extracted/SCN/MAPHEAD.SCN')
MODEL_HEAP_BUDGET = 170 * 1024                            # NPC models per screen (see check_model_heap)
MAPHEAD_LIMIT = 25000                                     # MAPHEAD_SCRIPT_BUFFER of the target (compile_sources sets it)
# MAPHEAD_SCRIPT_BUFFER per executable: the original 25 000; the mod executables 0x8000 (MAPHEAD_SCRIPT_MAX, patch 0091,
# which story-state builds on; docs/reference/memory.md "MAPHEAD buffer"). `story-build --maphead-max` (build-full.sh: the worktree's own) wins.
MAPHEAD_LIMITS = {'original': 25000, 'mods': 0x8000, 'species': 0x8000, 'story-state': 0x8000}
GROUND_PICKUP_MAX = 0                                 # explicit target fact; old targets retain their bytes
MAPHEAD_MAX_GIVEN = None
W_TYPE = 63                                               # scratch wide register: partner type > 255
P_RANDOM, P_TYPE, P_DATE = 94, 95, 96                    # scratch pstats of conditions (96-99: year day hour minute)
PARTNER_STATS = {'off': 0, 'offense': 0, 'def': 1, 'defense': 1, 'speed': 2, 'brain': 3, 'brains': 3,
                 'max hp': 4, 'max mp': 5, 'hp': 6, 'mp': 7, 'tiredness': 8, 'happiness': 9,
                 'discipline': 10, 'energy': 11, 'virus': 12, 'lifetime': 13, 'merit': 14,
                 'battles': 15, 'fled battles': 16, 'tournaments won': 17, 'tournament wins': 18}
ENTITIES = {'player': 'TAMER', 'tamer': 'TAMER', 'partner': 'PARTNER', 'narrator': '255'}
OPS = {'==': '==', '=': '==', '!=': '!=', '>=': '>=', '<=': '<=', '>': '>', '<': '<'}

from .text.profiles import ROW_PIXELS
MAX_PX = ROW_PIXELS        # a line's advance; drawGlyph drops glyphs starting at x >= 244


class BackendError(Exception):
    """An error of the build's back end; `pos` is the (file, line, col) of the source statement it is about, when known."""
    def __init__(self, msg, pos=None, hint=None):
        super().__init__(msg)
        self.msg, self.pos, self.hint = msg, pos, hint


def op16(name, idv):
    """The wide (u16 id) variant of an opcode when the id does not fit in a byte. The wide
    opcodes (docs/mods/dws.md) only run on the mod executable; ids <= 255 keep the
    original opcodes, so existing programs compile to the same bytes."""
    return name + '16' if int(idv) > 255 else name


def load_names(fname, col='name'):
    out = {}
    for r in csv.DictReader(open(os.path.join(ROOT, 'docs/data', fname))):
        out.setdefault(r[col].strip().lower(), int(r['id']))
    return out


# Characters only the mod executables' font has (á é ñ ¿ ¡ ç · « » and ( ) & % / … [ ] # * ~ @ – — ♪, tools/font/extra.txt,
# docs/mods/font.md). A target keeps the ones its executable has: the first FONT['glyphs'] of extra.txt, read from the built
# executable (fontgen.exe_glyphs: one built before a glyph was appended lacks it); the original executable has none. A
# character the target lacks is drawn plain when it has a plain form (accents, … as ..., – — as -) and refused otherwise (it
# would draw as another glyph).
import tempfile
import fontgen; from dws import bytecode
EXTRA_ORDER = list(fontgen.extra_map())              # every extra glyph, in code order (F040, F041...)
EXTRA_CHARS = set(EXTRA_ORDER)
FONT = {'extra': False, 'glyphs': 0, 'chars': frozenset(), 'of': 'the original executable', 'stripped': set(),
        'name': 'original'}                           # set_font; name: the executable's font (original, a, b: fontgen.exe_font)
FONT_GLYPHS_GIVEN = None                              # --font-glyphs N (build-full.sh: the worktree it builds)
FONT_NAME_GIVEN = None                                # --font NAME (build-full.sh: the FONT it builds with)
EXE_DIR_GIVEN = None                                  # --exe-dir DIR: the built executable of --exe mods/species/story-state
EXE_DIRS = {'mods': MODS_EXE_DIR, 'species': SPECIES_EXE_DIR, 'story-state': STORY_STATE_EXE_DIR}


def exe_dir(exe):
    """The folder of the built executable of a mod target (--exe-dir wins)."""
    return os.path.abspath(EXE_DIR_GIVEN) if EXE_DIR_GIVEN else os.path.join(ROOT, EXE_DIRS[exe])


def set_font(exe):
    """FONT for a target: the original executable has no extra glyph; a mod executable the first N of extra.txt, N from
    --font-glyphs, else from its build (fontgen.exe_glyphs), else (nothing built) all of them."""
    if exe == 'original':
        n, of = 0, 'the original executable'
    elif FONT_GLYPHS_GIVEN is not None:
        n, of = min(FONT_GLYPHS_GIVEN, len(EXTRA_ORDER)), f'the target executable (--font-glyphs {FONT_GLYPHS_GIVEN})'
    else:
        n, src = fontgen.exe_glyphs(exe_dir(exe))
        of = f'the executable of --exe {exe} ({os.path.relpath(src, ROOT) if src else os.path.relpath(exe_dir(exe), ROOT) + ": not built"})'
        if n is None: n = len(EXTRA_ORDER)
    name = 'original' if exe == 'original' else FONT_NAME_GIVEN or fontgen.exe_font(exe_dir(exe))[0] or fontgen.FONT_DEFAULT
    FONT.update({'extra': exe != 'original', 'glyphs': n, 'chars': frozenset(EXTRA_ORDER[:n]), 'of': of, 'stripped': set(),
                 'name': name})


def proportional():
    """Whether the target's font is placed to the pixel (FONT a or b, docs/mods/font.md "Fonts"): its own advances, a
    4-pixel space, and dialogue rows packed one byte a letter (fontgen.ROW_BYTES)."""
    return FONT['name'] in ('a', 'b')


def font_lacks(c):
    """Why the target's font lacks c, which extra.txt has (a newer glyph than its executable), as a phrase."""
    code = fontgen.index_to_code(EXTRA_ORDER.index(c))
    if not FONT['extra']:
        return f'only the mod executables have it (F{code & 0xFFF:03X}: --exe mods, species or story-state)'
    return (f'{FONT["of"]} has {FONT["glyphs"]} extra glyphs and `{c}` is F{code & 0xFFF:03X}: rebuild it with patch 0024 '
            f'as it is since 2026-10-14 (tools/mods.sh prepare/build; docs/mods/font.md)')
TRIMMED_NPCS = False
NPC_SLOTS = {'max': 8}                                # placed Digimon per screen: 8, 16 with --exe story-state (build.compile_sources)


def strip_char(c):
    """The plain form of a character a font lacks: the letter without its accent, … as ..., – — as -; '' to leave it out."""
    c = {'ñ': 'n', 'Ñ': 'N', '¿': '', '¡': '', '·': '.', '«': '"', '»': '"', '–': '-', '—': '-', '♪': ''}.get(c, c)
    return ''.join(x for x in unicodedata.normalize('NFKD', c) if not unicodedata.combining(x))


def plain(text):
    """Keep the characters the target font has; strip accents, ñ, ¿¡... from the rest."""
    out = []
    for c in unicodedata.normalize('NFC', text):
        if c in FONT['chars']:
            out.append(c); continue
        d = strip_char(c)
        if d != c:
            FONT['stripped'].add(c)
        out.append(d)
    return ''.join(out)


# The compiler keeps its target font for compatibility; the layout API takes it explicitly.
from .text import layout as text_layout
from .text.profiles import UNPACKED_KEYS, packed_key, ROW_PIXELS
NAME_PX = text_layout.NAME_PX
MAX_UNITS = text_layout.MAX_UNITS
CODE_UNIT = text_layout.CODE_UNIT
LAST_ROW_PX = text_layout.LAST_ROW_PX


def text_px(s):
    return text_layout.text_px(s, FONT)


def text_units(s):
    return text_layout.text_units(s)


def text_bytes(s):
    return text_layout.text_bytes(s)


def fits(s, last_row=False, packed=True):
    return text_layout.fits(s, FONT, last_row, packed)


def row_limit(packed=True):
    return text_layout.row_limit(FONT, packed)


def row_size(s, packed=True):
    return text_layout.row_size(s, FONT, packed)


def wrap(text, lines_per_page, packed=True):
    return text_layout.wrap(plain(text), lines_per_page, FONT, packed)


def quote(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


class Backend:
    """The state of one build: scripts with their events, placements, new scripts, rebuilt maps."""
    def __init__(self):
        self.label_n = 0
        n = names()                             # lower-cased name -> id, for item("Meat"), species("Veemon")...
        self.items, self.techs, self.digimon = n['item'], n['tech'], n['species']
        self.scripts = {}                       # script -> {'entities': {}, 'events': [], 'subs': []}
        self.maphead = None                     # MAPHEAD.SCN rebuilt by new_scripts()
        self.city = None                        # the `city { }` declaration (tools/dws/city.py): a table in a MAPHEAD section
        self.placements = []                    # (screen, slot, digimon id, {field: value}, line, like slot)
        self.new_slots = []                     # (screen, slot, digimon id, line): placements into empty slots
        self.default_sections = []              # (screen, section, digimon id): wild battle stubs if missing
        self.grown = {}                         # disc path -> (bytes, sectors, original sectors) when sectors grew
        self.maps = {}                          # disc path -> rebuilt .MAP
        self.new_scripts = {}                   # new script id -> {'screen': N, 'empty': bool}

    def label(self, hint='q'):
        self.label_n += 1; return f'q_{hint}{self.label_n}'

    def gen_event(self, sec, replace, body, ents, path):
        """The events of a DWS program are generated code already: a replaced section only needs its END."""
        out = list(body)
        if replace: out.append('    END_SECTION')
        return out


def names():
    """Lower-cased names -> ids of items, techniques and species (docs/data, plus content/species)."""
    digimon = {}
    rows = dict(DIGI_DATA)
    if _species is not None and any(t < _species.NUM_ORIGINAL for t in rows):
        # an id of the disc without a file keeps its disc name (the story that names it compiles; the species is empty):
        # docs/data/species.csv (species.disc_names), required
        for t, name in _species.disc_names().items():
            if t not in rows and name: rows[t] = {'name': name}
    for t, r in sorted(rows.items()):                        # content/species (tools/species.py), the lowest id first
        digimon.setdefault(r['name'].strip().lower(), t)
    return {'item': load_names('items.csv'), 'tech': load_names('techs.csv'), 'species': digimon}


# ---------------------------------------------------------------- integration
def ensure_dis():
    """The disassembly of the disc's DG.SCN, made again when tools/dws/bytecode/__main__.py changed (its text decoding is in the files: a cache
    made before the 2026-10-14 button fix re-encoded × and △ the other way)."""
    if DIS_CACHE != DIS_DEFAULT:                       # (the story build points it at the text it generated: kept as it is)
        if not os.path.exists(os.path.join(DIS_CACHE, 'dg.scn.lst')):
            dis(DG_SCN, DIS_CACHE)
        return
    stamp = bytecode.source_digest()
    sp = os.path.join(DIS_CACHE, 'bytecode.sha1')
    if os.path.exists(os.path.join(DIS_CACHE, 'dg.scn.lst')) and os.path.exists(sp) and open(sp).read() == stamp: return
    new = f'{DIS_CACHE}.new-{os.getpid()}'; old = f'{DIS_CACHE}.old-{os.getpid()}'
    dis(DG_SCN, new)
    open(os.path.join(new, 'bytecode.sha1'), 'w').write(stamp)
    if os.path.exists(DIS_CACHE): os.replace(DIS_CACHE, old)
    os.replace(new, DIS_CACHE); shutil.rmtree(old, ignore_errors=True)


SEC_RE = re.compile(r'\.section\s+(\d+)\s+(\S+)')


def new_scripts(comp, workdir, mh):
    """Creates the DG.SCN entries of `script new for screen N` and points the
    screens' MAPHEAD sections at them. Returns the edited MAPHEAD text.

    A new script starts as a copy of the screen's current script, or with
    `empty` as a stub END_SECTION for each of its sections: the engine jumps to
    a section by number (talking to slot K, stepping on trigger tiles...) and a
    missing one would run from a NULL pointer (getScriptSection returns 0)."""
    lst = os.path.join(workdir, 'dg.scn.lst')
    for sid, info in sorted(comp.new_scripts.items()):
        scr = info['screen']
        mh = ensure_screen_section(mh, scr)
        pat = re.compile(rf'(SET_SCRIPT\s+)(\d+)(,\s*{scr})\b')
        bases = sorted({int(m.group(2)) for m in pat.finditer(mh)})
        if not bases:
            raise BackendError(f'screen {scr}: no SET_SCRIPT for it in MAPHEAD')
        base = bases[0]
        mh = pat.sub(lambda m: f'{m.group(1)}{sid}{m.group(3)}', mh)
        src = open(os.path.join(workdir, f'script_{base:03d}.scn.txt'), encoding='utf-8').read().splitlines()
        if info['empty']:
            secs = [int(m.group(1)) for m in map(SEC_RE.match, src) if m]
            text = [f'; script {sid}: new, empty, for screen {scr} (sections of script {base} as stubs)'] + \
                   [f'.section {k} stub{k}' for k in secs] + ['']
            for k in secs:
                text += [f'stub{k}:', '    END_SECTION']
        else:
            text = [f'; script {sid}: new, a copy of script {base} for screen {scr}'] + \
                   [l for l in src if not l.startswith('.tail')]
        open(os.path.join(workdir, f'script_{sid:03d}.scn.txt'), 'w', encoding='utf-8').write('\n'.join(text) + '\n')
        with open(lst, 'a') as f:
            f.write(f'.entry {sid} script_{sid:03d}.scn.txt 1\n')
        info['base'] = base
    return mh


try:                                                      # every species (tools/species.py, content/species)
    import species as _species
    DIGI_DATA = _species.all_rows()
except ImportError:
    _species, DIGI_DATA = None, {}
EXTRA_SPECIES = {t: r for t, r in DIGI_DATA.items() if t >= 180}   # ids 180+: need --exe species
DISC_MAP_FILES = {int(r['id']): r['file'] for r in csv.DictReader(open(os.path.join(ROOT, 'docs/data/map_files.csv')))}
DISC_MAP_FLAGS = {int(r['id']): int(r['flags']) & 0xFF for r in csv.DictReader(open(os.path.join(ROOT, 'docs/data/map_files.csv')))}
# the screens >= 255: their files in content/screens (and SCREEN_CONTENT=dir:dir of a mod), tools/screens.py
import screens as SCR                                     # noqa: E402
MAP_FILES, MAP_FLAGS = {}, {}                             # the disc's screens and the new ones (set_screen_dirs)
SCREEN_DIRS, NEW_SCREENS = [], {}


def set_screen_dirs(dirs):
    """The screen files beside content/screens (SCREEN_CONTENT): NEW_SCREENS, and MAP_FILES/MAP_FLAGS with their rows."""
    global SCREEN_DIRS, NEW_SCREENS
    SCREEN_DIRS = [d for d in dirs if d]
    NEW_SCREENS = SCR.load(SCREEN_DIRS)
    MAP_FILES.clear(); MAP_FILES.update(DISC_MAP_FILES); MAP_FLAGS.clear(); MAP_FLAGS.update(DISC_MAP_FLAGS)
    for i, x in NEW_SCREENS.items():
        MAP_FILES[i] = x['file']
        MAP_FLAGS[i] = (x.get('sound_bank', 0) & 0x1F) | (0 if x.get('day_night', True) else 0x40) | (0x80 if x.get('reads_digimon') else 0)


# ---------------------------------------------------------------- the build's settings
# What a build reads from its caller: the command line takes them from the environment (configure() with nothing given,
# at import), tools/derive gives each story pass its own (docs/derive.md, finding 6). rule: nothing
# below reads the environment after configure(); a setting is one of these globals
IMPORTED_NPCS = False    # --imported-npcs: this disc's DIGI.DAT has the imported species, so --exe mods may place them
MAPS_DIRS = []           # DWS_MAPS=dir:dir: a mod's retouched maps (new exits, trigger tiles) the story's placements keep
RELAYOUT = False         # DWS_RELAYOUT=1: the disc is built with --relayout (build-full.sh), so DG.SCN may grow
PACK_ASCII = False       # SCNASM_PACK_ASCII=1: the texts store letters as one byte (bytecode asm --pack-ascii, patch 0145)
LOCKS_READ_ONLY = False  # the mods' save.lock files are only read (tools/derive: a lock that would grow stops the build)


def configure(screen_dirs=None, maps=None, relayout=None, pack_ascii=None, text_zones=None, locks_read_only=False):
    """Sets the build's settings; a setting not given (None) comes from the environment as the command line has it:
    SCREEN_CONTENT, DWS_MAPS, DWS_RELAYOUT, SCNASM_PACK_ASCII, TEXT_ZONES (a test build of some zones of a source)."""
    global MAPS_DIRS, RELAYOUT, PACK_ASCII, LOCKS_READ_ONLY
    env = os.environ.get
    set_screen_dirs(screen_dirs if screen_dirs is not None else env('SCREEN_CONTENT', '').split(os.pathsep))
    MAPS_DIRS = [d for d in (maps if maps is not None else env('DWS_MAPS', '').split(os.pathsep)) if d]
    RELAYOUT = relayout if relayout is not None else env('DWS_RELAYOUT') == '1'
    PACK_ASCII = pack_ascii if pack_ascii is not None else env('SCNASM_PACK_ASCII') == '1'
    LOCKS_READ_ONLY = locks_read_only
    from . import textbank
    textbank.TEXT_ZONES = (text_zones if text_zones is not None else env('TEXT_ZONES', '')).replace(',', ' ').split()


def dis(src, outdir):
    """tools/dws/bytecode/__main__.py dis in this process; a failure raises."""
    r = bytecode.dis(src, outdir)
    if r.returncode: raise BackendError(f'bytecode dis {os.path.relpath(src, ROOT)}: {r.stderr.strip()}')


def ensure_screen_section(mh, scr):
    """MAPHEAD text with a section for screen `scr`: a new screen (>= 255) without one gets the one its screen file
    describes (tools/screens.py synth_section), which the story then edits; tools/screens.py moves it into SCRN.DAT."""
    if re.search(rf'^sec{scr}:', mh, re.M) or not SCR.is_new(scr): return mh
    if scr not in NEW_SCREENS:
        raise BackendError(f'screen {scr} is a new screen (>= 255) without a file: content/screens/{scr}-<name>.json '
                           '(tools/screens.py; SCREEN_CONTENT for a mod\'s own folder)')
    return SCR.add_section(mh, scr, SCR.synth_section(scr, NEW_SCREENS[scr], mh))
_SLOTS = {}


def screen_slots(screen):
    """The placed Digimon of a screen's .MAP on the player's disc: [{'slot', 'species', 'entity', 'x', 'z'}] (a slot with no
    Digimon is left out). `entity` is the slot's script id: the number the screen's script calls it by, and its talk
    section; usually 5 + slot, but some slots share one (the four keepers of the Item Shop are all entity 5). [] when the
    screen has no .MAP on the disc."""
    return _map_slots(screen)[0]


def next_free_slot(screen):
    """The slot a new NPC of `screen` goes in: the .MAP's slots are filled in order (`new_slot_entry`)."""
    return _map_slots(screen)[1]


def _map_slots(screen):
    if screen in _SLOTS: return _SLOTS[screen]
    import dwmap
    src = map_path(MAP_FILES.get(screen))
    out = []; n = 0
    if src:
        m = dwmap.MapFile(open(src, 'rb').read()); n = len(m.digimon)
        for k, d in enumerate(m.digimon):
            if d['type'] in (-1, 255): continue
            out.append({'slot': k, 'species': d['type'], 'entity': d['scriptId'], 'x': d['posX'], 'z': d['posZ']})
    _SLOTS[screen] = (out, n)
    return _SLOTS[screen]


def slot_entity(screen, slot):
    """The entity number of `slot` on `screen` (its .MAP script id), or 5 + slot for a slot the .MAP does not have."""
    return next((d['entity'] for d in screen_slots(screen) if d['slot'] == slot), 5 + slot)


def model_size(dig):
    """Bytes malloc3 takes for a Digimon's model (whole sectors, docs/mods/models.md)."""
    if dig >= 180:
        return (_species.model_size(dig) + 0x7FF) & ~0x7FF if _species else 0
    import membudget                                         # the model of its species file (content/species model.name)
    path, _ = membudget.model_file(dig)
    return (os.path.getsize(path) + 0x7FF) & ~0x7FF if os.path.exists(path) else 0


def check_model_heap(body, dig, screen, ln):
    """NPC models are malloc3'd from a heap of ~193 KB that also holds other
    screen data; measured: Native Forest by day has 80 KB of models and 89 KB
    free. If the models loaded on one path of the screen's setup exceed the
    budget, malloc3 fails and the game hangs on the loading screen."""
    lines = body.splitlines()
    k = next(i for i, l in enumerate(lines) if re.match(rf'\s*SET_DIGIMON\s+{dig},', l))
    lo = k
    while lo > 0 and not re.match(r'^\S.*:', lines[lo - 1]) and 'IF ' not in lines[lo - 1]: lo -= 1
    hi = k
    while hi + 1 < len(lines) and not re.match(r'^\S.*:', lines[hi + 1]) and 'JUMP_TO' not in lines[hi + 1]: hi += 1
    loaded = {int(m.group(1)) for l in lines[lo:hi + 1] for m in [re.match(r'\s*LOAD_DIGIMON\s+(\d+)', l)] if m}
    total = sum(model_size(d) for d in loaded)
    if total > MODEL_HEAP_BUDGET:
        names = ', '.join(f'{DIGI_DATA[d]["name"]} {model_size(d) // 1024} KB' for d in sorted(loaded))
        raise BackendError(f'screen {screen} would load {total // 1024} KB of models ({names}); '
                         f'about {MODEL_HEAP_BUDGET // 1024} KB fit in the heap. Replace the other Digimon of '
                         f'that screen too, or pick a smaller one', ln)


def set_moves(e, dig, ln):
    nmoves = len(DIGI_DATA[dig]['moves'].split()) if DIGI_DATA.get(dig, {}).get('moves') else 0
    # An NPC-only species (a twin such as the big Whamon, id 146) has no techniques: placed, it can talk but not fight.
    for k in range(3):                                      # animation ids 0x2E + index into its technique list
        e[f'move{k}'] = 0x2E + k if k < nmoves else 255
    e['move3'] = 255


def new_slot_entry(m, screen, slot, dig, stats, ln, like, dwmap, section=None):
    """`place` into an empty slot: a new .MAP entry copied from a template slot (`like slot J`,
    otherwise the first one that walks a path), at `at X, Z` with its path shifted along,
    talking/fighting through section 5+slot."""
    used = len(m.digimon)
    if slot != used:
        raise BackendError(f'screen {screen} has {used} placed Digimon (slots 0-{used - 1}); '
                         f'a new one goes in slot {used} (slots are filled in order)', ln)
    if slot >= NPC_SLOTS['max']:
        raise BackendError(f'screen {screen} already has {NPC_SLOTS["max"]} placed Digimon (MAP_DIGIMON_TABLE[{NPC_SLOTS["max"]}]'
                           + ('; --exe story-state has 16 slots)' if NPC_SLOTS['max'] == 8 else ')'), ln)
    if 'posX' not in stats: raise BackendError(f'a new slot needs a position: `at X, Z`', ln)
    if like is not None:
        if like >= used: raise BackendError(f'`like slot {like}`: screen {screen} has slots 0-{used - 1}', ln)
        tpl = m.digimon[like]
    else:
        k = template_slot(m)
        tpl = m.digimon[k] if k is not None else None
    if tpl is None:
        e = {k: 0 for k in dwmap.DIGI_FIELDS}
        e.update({'followMode': 12, 'trackingRange': 1000, 'hp': 500, 'mp': 500, 'currentHP': 500, 'currentMP': 500,
                  'off': 100, 'def': 100, 'speed': 100, 'brain': 100, 'bits': 100, 'prio0': 40, 'prio1': 30, 'prio2': 30})
        e['aiSections'] = [0, -1, -1, -1, -1, -1, -1, -1]; e['waypoints'] = [[60, 0, 0]]
    else:
        e = json.loads(json.dumps(tpl))
    x, z = stats['posX'], stats['posZ']
    if stats.pop('still', None):                        # stands where it is put: the template's path is not copied
        e['aiSections'] = [0, -1, -1, -1, -1, -1, -1, -1]; e['waypoints'] = [[60, 0, 0]]
        tpl = None; e['fleeX'], e['fleeZ'] = x, z
    if tpl is not None:
        dwmap.shift_path(e, x - e['posX'], z - e['posZ'])
    else:
        e['fleeX'], e['fleeZ'] = x, z
    e.update(type=dig, posX=x, posY=0, posZ=z, scriptId=section if section is not None else 5 + slot)
    set_moves(e, dig, ln)
    for k, v in stats.items():
        if k in ('posX', 'posZ'): continue
        e[k] = v
        if k in ('hp', 'mp'): e['current' + k.upper()] = v
    tx, tz = dwmap.world_to_tile(x, z)
    if not (0 <= tx < 100 and 0 <= tz < 100): raise BackendError(f'({x}, {z}) is outside the map', ln)
    if m.collision[tz * 100 + tx] & 0x80:
        near = nearest_walkable(m, x, z)
        raise BackendError(f'({x}, {z}) is a wall tile ({tx},{tz}) of screen {screen}'
                           + (f'; the nearest walkable point is {near}' if near else ''), ln, walk_hint(screen, m))
    for k, w in enumerate(e['waypoints']):
        if k < 8 and e['aiSections'][k] in (1, 2):
            wx, wz = dwmap.world_to_tile(w[0], w[2])
            if not (0 <= wx < 100 and 0 <= wz < 100) or m.collision[wz * 100 + wx] & 0x80:
                raise BackendError(f'its path (copied from the NPC it behaves like) goes to ({w[0]}, {w[2]}), a wall tile', ln,
                                   'move it (at=) or pick another NPC to behave like (behaves_like=); ' + walk_hint(screen, m))
    m.digimon.append(e); m.digimon_count = len(m.digimon)
    return e


def template_slot(m):
    """The .MAP slot a new NPC copies when no `like` is given: the first that walks a path, else the last one (None: none)."""
    k = next((i for i, d in enumerate(m.digimon) if any(a in (1, 2) for a in d['aiSections'])), None)
    return k if k is not None else (len(m.digimon) - 1 if m.digimon else None)


def nearest_walkable(m, x, z):
    """The centre of the walkable tile (no wall bit) nearest to (x, z), in world units, or None."""
    import dwmap
    best = None
    for i, v in enumerate(m.collision):
        if v & 0x80: continue
        wx, wz = dwmap.tile_to_world(i % 100, i // 100)
        d = (wx - x) ** 2 + (wz - z) ** 2
        if best is None or d < best[0]: best = (d, (wx, wz))
    return best[1] if best else None


def map_path(name):
    """The .MAP NAME as the story compiler starts from: the disc's assets with the Digimon list of content/maps
    (tools/content.py built_map_path), or None."""
    src = next(iter(glob.glob(os.path.join(ROOT, f'extracted/MAP/*/{name}.MAP'))), None) if name else None
    if not src: return None
    import content
    return content.built_map_path(os.path.relpath(src, os.path.join(ROOT, 'extracted')))


def map_source(screen):
    """The screen's .MAP on the extracted disc (relative to the repository), or None."""
    src = map_path(MAP_FILES.get(screen))
    return os.path.relpath(src, ROOT) if src else None


def walk_hint(screen, m=None):
    """Where a new NPC can stand on a screen, in words: the box of its walkable tiles and the overlay that draws them."""
    import dwmap
    src = map_source(screen)
    if m is None and src: m = dwmap.MapFile(open(os.path.join(ROOT, src), 'rb').read())
    box = dwmap.walk_box(m) if m is not None else None
    out = (f'the walkable tiles are inside x {box[0]}..{box[1]}, z {box[2]}..{box[3]} (not every point of that box)'
           if box else 'the screen has no walkable tile')
    if src:
        png = os.path.splitext(os.path.basename(src))[0].lower() + '.png'
        out += f'; python3 tools/dwmap.py overlay {src} {png} draws them, with the coordinates every 500'
    return out


def story_state_heap():
    """The malloc3 heap of the story-state executable (docs/mods/story-state-engine.md "Memory"): from the end of its bss to the
    stack limit, minus the 8-byte sentinel. The built executable's link map says; else the link-time minimum."""
    mm = open(os.path.join(ROOT, 'build/decomp-story-state/include/dw/memmap.h'), encoding='utf-8').read()
    stack = int(re.search(r'#define STACK_ADDR\s+(0x[0-9A-Fa-f]+)', mm).group(1), 16) - \
        int(re.search(r'#define STACK_SIZE_KB\s+(0x[0-9A-Fa-f]+)', mm).group(1), 16) * 1024
    try:
        text = open(os.path.join(ROOT, STORY_STATE_EXE_DIR, 'SLUS_010.32.elf.map'), encoding='utf-8', errors='replace').read()
        end = int(re.search(r'(0x[0-9a-f]+)\s+main_BSS_END = \.', text).group(1), 16)
        return stack - end - 8
    except (OSError, AttributeError):
        return int(re.search(r'#define MIN_HEAP\s+(0x[0-9A-Fa-f]+)', mm).group(1), 16)


# the clock in a setup rule: STORE_DATE p105 writes year, day, hour, minute to p105-p108 (the base's MAPHEAD does the same)
P_SETUP_DATE = 105
CLOCK_PSTAT = {f'clock.{f}': f'p{P_SETUP_DATE + k}' for k, f in enumerate(('year', 'day', 'hour', 'minute'))}


def presence_if(c, screen, slot):
    """A presence condition (tools/dws/presence.py tree) as the clauses of a MAPHEAD `IF`, or None for `always`. The IF folds left to
    right without grouping, so a flat `and` or a flat `or` of atoms is what it can say; anything deeper is refused."""
    def atom(a):
        neg = a[0] == 'not'
        if neg: a = a[1]
        if a[0] == 'trig': return ('not ' if neg else '') + f'trigger {a[1]}'
        if a[0] == 'cmp' and (re.fullmatch(r'p\d+', a[1]) or a[1] in CLOCK_PSTAT):
            op = {'==': '!=', '!=': '==', '>=': '<', '<': '>=', '<=': '>', '>': '<='}[a[2]] if neg else a[2]
            return f'{CLOCK_PSTAT.get(a[1], a[1])} {op} {a[3]}'
        raise BackendError(f'presence screen {screen} slot {slot}: only triggers, flags, the clock and pstat comparisons are compiled into MAPHEAD')
    if c[0] == 'true': return None
    if c[0] == 'false': return 'trigger 0, and not trigger 0'
    if c[0] in ('and', 'or'):
        if any(x[0] in ('and', 'or') or (x[0] == 'not' and x[1][0] in ('and', 'or')) for x in c[1]):
            raise BackendError(f'presence screen {screen} slot {slot}: an `and` inside an `or` (or the reverse) does not fit one MAPHEAD IF')
        return f', {c[0]} '.join(atom(x) for x in c[1])
    return atom(c)


def keep_orig(own):
    """own.orig, the map as the recipe made it, made once. rule: story passes run side by side (tools/derive), so a pass
    never sees a half-copied .orig (copied under a name of its own, then linked), and a pass that copied the map after
    another had already edited it never replaces that one's .orig (the link fails when it exists; the first .orig made
    was copied before any pass wrote the map, since a pass writes it only after its .orig exists)."""
    tmp = f'{own}.orig.{os.getpid()}'
    shutil.copyfile(own, tmp)
    try:
        if not hasattr(os, 'link'):                     # (Pyodide: no os.link, and one process: no race)
            raise OSError('no links')
        os.link(tmp, own + '.orig')
    except FileExistsError:
        pass
    except OSError:                                     # (a file system without links)
        if not os.path.isfile(own + '.orig'): os.replace(tmp, own + '.orig')
    finally:
        if os.path.exists(tmp): os.remove(tmp)


def place_digimon(comp, mh, report):
    """`place "X" on screen N slot K ...`: the screen's .MAP gets the new type and
    battle stats in placed-Digimon slot K (AI, waypoints and flee point are kept),
    and MAPHEAD's SET_DIGIMON for that slot loads the new type.

    If slot K is the screen's next free slot (K == number of placed Digimon), the
    .MAP gets a new entry (the file grows), MAPHEAD spawns it unconditionally right
    after SET_SCRIPT, and section 5+K of the screen's script gets a wild battle
    when the script has none (the engine runs that section on touching it; a
    missing one would run from a NULL pointer)."""
    import dwmap
    maps = {}; pending = []; inplace_maps = {}
    pres = (comp.city or {}).get('presence') or {}
    used_rules = set()

    def spawn_lines(screen, slot, dig, ln):
        """LOAD_DIGIMON + SET_DIGIMON of a slot this program adds; with a `city { presence }` rule for the slot, under its condition."""
        rule = next((r for r in (pres.get(screen) or {}).get('npcs', []) if r[0] == slot), None)
        if rule is None:
            return f'    LOAD_DIGIMON {dig}\n    SET_DIGIMON {dig}, {slot}, 1\n'
        _, sp, talk, cnd = rule; used_rules.add((screen, slot))
        if sp != dig:
            raise BackendError(f'screen {screen} slot {slot}: the presence rule names species {sp}, place() puts {dig}', ln)
        if (pres.get(screen) or {}).get('lets'):
            raise BackendError(f'screen {screen}: a presence rule with `let` names is check-only; write the condition in the npc line')
        body = f'    LOAD_DIGIMON {dig}\n    SET_DIGIMON {dig}, {slot}, {talk}\n'
        clauses = presence_if(cnd, screen, slot)
        if clauses is None: return body
        lab = f'dws_presence_{screen}_{slot}'
        date = f'    STORE_DATE p{P_SETUP_DATE}\n' if any(p in clauses.split() for p in CLOCK_PSTAT.values()) else ''
        return f'{date}    IF {clauses}, else {lab}\n{body}{lab}:\n'

    for screen, slot, dig, stats, ln, like in comp.placements:
        own = stats.pop('map', None); inplace = None
        if own:                                             # the mod's own .MAP for a new screen: written where the disc has that file name,
            name = os.path.splitext(os.path.basename(own))[0]   # or, a new file name (the file of a SCREEN_CONTENT screen, MAP/NEW), edited in place
            disc = next(iter(glob.glob(os.path.join(ROOT, f'extracted/MAP/*/{name}.MAP'))), None)
            if not disc:
                rec = NEW_SCREENS.get(screen)
                if not (rec and rec.get('file') == name and os.path.isfile(own)):
                    raise BackendError(f'map {name}.MAP: the disc has no file of that name to replace (an unused one is MGEN06-10, MGEN17) '
                                       f'and it is not the file of screen {screen}\'s screen file (SCREEN_CONTENT)', ln)
                inplace = own
                if not os.path.isfile(own + '.orig'):        # the map as the recipe made it: every compile starts from it
                    keep_orig(own)
                src = own + '.orig'
            else:
                src = own
        else:
            name = MAP_FILES.get(screen)
            disc = next(iter(glob.glob(os.path.join(ROOT, f'extracted/MAP/*/{name}.MAP'))), None) if name else None
            if not disc: raise BackendError(f'screen {screen} has no .MAP (a new screen: `map: "path/NAME.MAP"`)', ln)
            src = map_path(name)                            # its Digimon list from content/maps
        rel = os.path.relpath(disc, os.path.join(ROOT, 'extracted')).replace(os.sep, '/') if disc else f'MAP/NEW/{name}.MAP'
        if inplace: inplace_maps[rel] = inplace
        if rel not in maps:
            m = dwmap.MapFile(open(src, 'rb').read())
            # a mod that retouches the screen (new exits, trigger tiles: DWS_MAPS, as the checks read it) keeps its map;
            # the Digimon list stays the one the compiler starts from (content/maps)
            for d in MAPS_DIRS:
                rp = os.path.join(d, os.path.basename(rel))
                if not own and os.path.exists(rp):
                    r = dwmap.MapFile(open(rp, 'rb').read()); r.digimon = m.digimon; m = r; break
            maps[rel] = m
        m = maps[rel]
        mh = ensure_screen_section(mh, screen)
        sec = re.search(rf'^sec{screen}:.*?(?=^sec\d+:|\Z)', mh, re.S | re.M)
        if not sec: raise BackendError(f'no MAPHEAD section for screen {screen}', ln)
        body = sec.group(0)
        if slot >= len(m.digimon):                          # empty slot: a new entry
            if not own and not MAP_FLAGS.get(screen, 0) & 0x80:
                raise BackendError(f'screen {screen} does not read its placed-Digimon list '
                                 '(MAP_ENTRIES flags lack 0x80)', ln)
            section = stats.pop('section', None)
            if section is not None and not 5 <= section <= 254:
                raise BackendError(f'section {section}: a talk section is 5-254', ln)
            e = new_slot_entry(m, screen, slot, dig, stats, ln, like, dwmap, section)
            ins = spawn_lines(screen, slot, dig, ln)
            body, n = re.subn(r'(^\s*SET_SCRIPT\b.*\n)', lambda q: q.group(1) + ins, body, count=1, flags=re.M)
            if not n: raise BackendError(f'MAPHEAD screen {screen} has no SET_SCRIPT', ln)
            comp.new_slots.append((screen, slot, dig, ln))
            scr_id = re.search(r'SET_SCRIPT\s+(\d+)', body)
            comp.default_sections.append((int(scr_id.group(1)), section if section is not None else 5 + slot, dig, screen))
            pending.append((screen, dig, ln))
            mh = mh[:sec.start()] + body + mh[sec.end():]
            near = [k for k, o in enumerate(m.digimon) if k != slot and o.get('type') not in (-1, 255, None) and 'posX' in o
                    and abs(o['posX'] - e['posX']) < 100 and abs(o['posZ'] - e['posZ']) < 100]
            if near:
                report.append(f'note: screen {screen} slot {slot}: the new {DIGI_DATA[dig]["name"]} at ({e["posX"]}, {e["posZ"]}) stands on the '
                              f'tile of slot {near[0]} ({DIGI_DATA.get(m.digimon[near[0]]["type"], {}).get("name", "?")} at '
                              f'({m.digimon[near[0]]["posX"]}, {m.digimon[near[0]]["posZ"]})): one hides the other; move one at=(x, z) '
                              f'(python3 tools/dws.py slots {screen} lists who stands where)')
            report.append(f'screen {screen} slot {slot}: new {DIGI_DATA[dig]["name"]} at ({e["posX"]}, {e["posZ"]}), '
                          f'section {section if section is not None else 5 + slot}, '
                          f'{"spawned by its presence rule" if (screen, slot) in used_rules else "spawned unconditionally"} {stats or ""}')
            continue
        if like is not None: raise BackendError(f'`like slot` is only for a new (empty) slot', ln)
        if 'section' in stats: raise BackendError(f'`section` is only for a new (empty) slot', ln)
        if m.digimon[slot]['type'] in (-1, 255):
            raise BackendError(f'screen {screen} has no placed Digimon in slot {slot} '
                             f'(slots in use: {[i for i, d in enumerate(m.digimon) if d["type"] not in (-1, 255)]})', ln)
        e = m.digimon[slot]; old = e['type']
        e['type'] = dig
        set_moves(e, dig, ln)
        for k, v in stats.items():
            e[k] = v
            if k in ('hp', 'mp'): e['current' + k.upper()] = v
        if 'posX' in stats:                                 # it appears at its first waypoint
            dx, dz = stats['posX'] - e['waypoints'][0][0], stats['posZ'] - e['waypoints'][0][2]
            e['waypoints'] = [[w[0] + dx, w[1], w[2] + dz] for w in e['waypoints']]
        # MAPHEAD: SET_DIGIMON old, slot, x  ->  new type; load its model in the same block
        pat = re.compile(rf'^(\s*SET_DIGIMON\s+){old}(,\s*{slot},.*)$', re.M)
        if not pat.search(body):
            if re.search(rf'^\s*SET_DIGIMON\s+\d+,\s*{slot},', body, re.M):
                raise BackendError(f'MAPHEAD screen {screen} spawns slot {slot} as another type than {DIGI_DATA[old]["name"]}', ln)
            # a slot of the .MAP that MAPHEAD never spawns (Jijimon's house has one): spawn it unconditionally, like a new slot
            ins = spawn_lines(screen, slot, dig, ln)
            body, n = re.subn(r'(^\s*SET_SCRIPT\b.*\n)', lambda q: q.group(1) + ins, body, count=1, flags=re.M)
            if not n: raise BackendError(f'MAPHEAD screen {screen} has no SET_SCRIPT', ln)
        elif not re.search(rf'^\s*LOAD_DIGIMON\s+{dig}\b', body, re.M):
            body = pat.sub(lambda q: f'    LOAD_DIGIMON {dig}\n{q.group(1)}{dig}{q.group(2)}', body, count=1)
        else:
            body = pat.sub(lambda q: f'{q.group(1)}{dig}{q.group(2)}', body, count=1)
        # the old type's model is no longer needed if no SET_DIGIMON of this screen uses it
        if not re.search(rf'^\s*SET_DIGIMON\s+{old},', body, re.M):
            body = re.sub(rf'^\s*LOAD_DIGIMON\s+{old}\b.*\n', '', body, count=1, flags=re.M)
        pending.append((screen, dig, ln))
        mh = mh[:sec.start()] + body + mh[sec.end():]
        report.append(f'screen {screen} slot {slot}: {DIGI_DATA[old]["name"]} -> {DIGI_DATA[dig]["name"]} {stats or ""}')
    for screen, sc in pres.items():
        for slot, sp, talk, cnd in sc.get('npcs', []):
            if (screen, slot) not in used_rules:
                report.append(f'note: presence screen {screen} slot {slot}: check-only (the slot is not one this program places)')
    checked = set()
    for screen, dig, ln in pending:                         # after all of a screen's changes
        if screen in checked: continue
        checked.add(screen)
        try:
            import membudget                                # measured per screen (docs/data/memory-budget.csv)
            membudget.configure()                           # runner may reuse this module with a new target
            membudget.TRIMMED = TRIMMED_NPCS
            membudget.HEAP_FOR_NPCS = 0x30388
            if NPC_SLOTS['max'] > 8:                        # the story-state engine: its own heap, nothing measured per screen
                membudget.HEAP_FOR_NPCS = story_state_heap()
                # it is built on the integration branch, whose memreclaim trims every NPC model on load (npc_anim_trim.c):
                # without this the estimate used the whole MMD and was ~20 KB high on Jijimon's house (measured: 78.6 KB used, now 78)
                # (a check of --exe story-state only, which reads the story-state tree it targets: no byte of a build depends on it, and
                # the everything disc and tools/derive compile for --exe mods, where it never runs)
                membudget.TRIMMED = os.path.exists(os.path.join(ROOT, 'build/decomp-story-state/src/main/npc_anim_trim.c'))
                b = membudget.screen_budget(screen, maphead_text=mh, sweep_csv=os.devnull)
            else:
                b = membudget.screen_budget(screen, maphead_text=mh)
        except Exception as e:                              # legacy callers may lack extracted models
            if os.environ.get('DW_MODEL_ARCHIVE'):
                raise BackendError(f'screen {screen}: target heap check failed: {e}', ln) from e
            report.append(f'note: membudget unavailable ({e}); using the rough model check')
            sec = re.search(rf'^sec{screen}:.*?(?=^sec\d+:|\Z)', mh, re.S | re.M)
            if re.search(rf'^\s*SET_DIGIMON\s+{dig},', sec.group(0), re.M):
                check_model_heap(sec.group(0), dig, screen, ln)
            continue
        report.append(f'screen {screen} heap: needs {b["peak"] // 1024} KB of {b["available"] // 1024} KB '
                      f'({"measured" if b["measured"] else "estimated"}), margin {b["margin"] // 1024} KB'
                      + (' (tight: it fits on the worst path the setup can take; play the screen once to see it load)'
                         if 0 <= b['margin'] < 8 * 1024 else ''))
        if b['margin'] < 0:
            raise BackendError(f'screen {screen} would need {b["peak"] // 1024} KB of heap for its Digimon '
                             f'({", ".join(b["worst"])}) but only {b["available"] // 1024} KB are free there; '
                             'the loading screen would hang. Replace other Digimon of that screen, or pick a smaller one or one '
                             f'already there (its model is loaded once): python3 tools/dws.py slots {screen} lists both', ln)
        sec = re.search(rf'^sec{screen}:.*?(?=^sec\d+:|\Z)', mh, re.S | re.M).group(0)
        models = {int(t) for t in re.findall(r'^\s*LOAD_DIGIMON\s+(\d+)', sec, re.M)}
        if len(re.findall(r'^\s*LOAD_DIGIMON\s+\d+', sec, re.M)) > NPC_SLOTS['max'] or len(models) > 5:
            report.append(f'warning: MAPHEAD screen {screen} has {len(models)} distinct models; on one path at most '
                          f'5 (NPC_MODELS) and {NPC_SLOTS["max"]} LOAD_DIGIMON (LOADED_DIGIMON_MODELS) can be used')
    out_dir = os.path.join(getattr(comp, 'run_dir', RUN_ROOT), 'maps')
    for rel, m in maps.items():
        own = inplace_maps.get(rel)                         # a new file name: written back beside its screen file (the build's new-files step adds it)
        dst = own or os.path.join(out_dir, rel); os.makedirs(os.path.dirname(dst), exist_ok=True)
        data = m.build(); orig = os.path.getsize(own + '.orig' if own else os.path.join(ROOT, 'extracted', rel))
        if dwmap.MapFile(data).build() != data: raise BackendError(f'{rel}: the rebuilt .MAP does not parse back')
        sn, so = -(-len(data) // 2048), -(-orig // 2048)
        if len(data) != orig:
            report.append(f'{rel}: {orig} -> {len(data)} bytes, {so} -> {sn} sectors'
                          + ('' if sn == so or own else ' (more sectors: the disc needs --exe mods, i.e. --relayout)'))
            if sn != so and not own: comp.grown[rel] = (len(data), sn, so)
        # Concurrent containers may share files while each sees PID 5. Reserve a
        # unique name so one language pass cannot consume another pass's temp map.
        fd, tmp = tempfile.mkstemp(prefix=os.path.basename(dst) + '.', dir=os.path.dirname(dst))
        try:
            with os.fdopen(fd, 'wb') as f:
                f.write(data)
            os.replace(tmp, dst)   # whole, whichever pass writes it last
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        if not own: comp.maps[rel] = dst
    return mh


def build_maphead(comp, workdir, report):
    if not comp.new_scripts and not comp.placements and comp.city is None:
        return None
    mh_dir = os.path.join(workdir, 'maphead')
    dis(MAPHEAD_SCN, mh_dir)
    mh_path = os.path.join(mh_dir, 'maphead.scn.txt')
    mh = open(mh_path, encoding='utf-8').read()
    mh = new_scripts(comp, workdir, mh)
    mh = place_digimon(comp, mh, report)
    if comp.city is not None and getattr(comp, 'city_table', True):     # (below story-state only its presence rules: the IFs above)
        from . import city
        blob = city.encode(comp.city); sec, body = city.to_section_text(blob)
        if re.search(rf'^\.section\s+{city.SECTION}\s', mh, re.M): raise BackendError(f'MAPHEAD already has a section {city.SECTION}')
        last = [m for m in re.finditer(r'^\.section\s.*$', mh, re.M)][-1]
        mh = mh[:last.end()] + '\n' + sec + mh[last.end():] + '\n'.join(body) + '\n'
        report.append(f'city table: MAPHEAD section {city.SECTION}, {len(blob)} bytes')
    open(mh_path, 'w', encoding='utf-8').write(mh)
    out = os.path.join(os.path.dirname(workdir), 'MAPHEAD.SCN')
    r = bytecode.asm(mh_path, out, maphead_max=0xFFFF, pack_ascii=PACK_ASCII)
    if r.returncode:
        raise BackendError('MAPHEAD: ' + (r.stderr.strip() or r.stdout.strip()))
    size = os.path.getsize(out)
    new = [i for i in NEW_SCREENS if re.search(rf'^sec{i}:', mh, re.M)]
    if new:                                                # their sections go to SCRN.DAT (tools/screens.py build): not resident
        rest, _ = SCR.split(mh, new)
        size = len(bytecode.assemble_script(rest, 'maphead.scn.txt', SCR.asm_opts(PACK_ASCII))[0])
        report.append(f'MAPHEAD: sections of the new screens {new} (SCRN.DAT, tools/screens.py build); {size} bytes resident')
    if size > MAPHEAD_LIMIT:
        raise BackendError(f'MAPHEAD.SCN is {size} bytes; the game buffer holds {MAPHEAD_LIMIT}')
    return out


def apply(comp, workdir):
    shutil.rmtree(workdir, ignore_errors=True); shutil.copytree(DIS_CACHE, workdir)
    report = []
    comp.maphead = build_maphead(comp, workdir, report)
    for sid, info in sorted(comp.new_scripts.items()):
        report.append(f'script {sid}: new for screen {info["screen"]} '
                      f'({"empty, sections of" if info["empty"] else "copy of"} script {info["base"]})')
    for script, info in sorted(comp.scripts.items()):
        f = os.path.join(workdir, f'script_{script:03d}.scn.txt')
        if not os.path.exists(f): raise BackendError(f'script {script} does not exist')
        text = open(f, encoding='utf-8').read().splitlines()
        tail = []
        by_sec = {}
        for sec, replace, body, ents, path in info['events']:
            by_sec.setdefault(sec, []).append((replace, os.path.basename(path)))
        for sec, evs in by_sec.items():
            if len(evs) > 1 and any(r for r, _ in evs):
                raise BackendError(f'script {script} section {sec} is replaced by one source and also used by another: '
                                 + ', '.join(f'{p}{" (replace)" if r else ""}' for r, p in evs)
                                 + '; compile them separately or merge them')
        for sec, replace, body, ents, path in info['events']:
            code = comp.gen_event(sec, replace, body, ents, path)
            has = [k for k, l in enumerate(text) if re.match(rf'\.section\s+{sec}\s+(\S+)', l)]
            if sec > 254 and not (has and replace):
                raise BackendError(f'script {script} section {sec}: ids above 254 can only replace a section the script already has')
            if has and not replace:
                lab = re.match(rf'\.section\s+{sec}\s+(\S+)', text[has[0]]).group(1)
                k = next(k for k, l in enumerate(text) if l.split(';')[0].strip() == f'{lab}:')
                text[k + 1:k + 1] = [f'    ; --- dws ({os.path.basename(path)})'] + code + ['    ; --- end dws']
                report.append(f'script {script} section {sec}: inserted at the start ({len(code)} lines)')
            else:
                lab = f'dws_sec{sec}_{comp.label("s")}'
                if has: text[has[0]] = f'.section {sec} {lab}'
                else:
                    last = max(k for k, l in enumerate(text) if l.startswith('.section'))
                    text.insert(last + 1, f'.section {sec} {lab}')
                real = [l for l in code if not l.lstrip().startswith(';')]          # (source-map marks are comments)
                end = code if real and real[-1].strip() in ('END_SECTION', 'END') else code + ['    END_SECTION']
                tail += ['', f'{lab}:', f'    ; --- dws ({os.path.basename(path)})'] + end
                report.append(f'script {script} section {sec}: {"replaced" if has else "new"} ({len(code)} lines)')
        if info.get('subs'): tail += ['', '    ; --- subroutines (JUMP_AND_LINK targets)'] + info['subs']
        for name, code, path in info.get('shared', []):             # `shared NAME { }` blocks of the script
            tail += ['', f'    ; --- dws shared {name} ({os.path.basename(path)})'] + code
        open(f, 'w', encoding='utf-8').write('\n'.join(text + tail) + '\n')
    for script, sec, dig, screen in comp.default_sections:  # new slots: a wild battle unless the program wrote one
        f = os.path.join(workdir, f'script_{script:03d}.scn.txt')
        text = open(f, encoding='utf-8').read().splitlines()
        if any(re.match(rf'\.section\s+{sec}\s', l) for l in text):
            report.append(f'script {script} section {sec}: already there, used by the new slot of screen {screen}')
            continue
        lab = f'dws_wild{sec}_{comp.label("w")}'
        last = max(k for k, l in enumerate(text) if l.startswith('.section'))
        text.insert(last + 1, f'.section {sec} {lab}')
        text += ['', f'{lab}:', f'    ; --- dws: default wild battle for the new {DIGI_DATA[dig]["name"]}',
                 f'    SET_DIALOG_OWNER {sec}', '    SHOW_TEXTBOX', '        "Grrr!"',
                 '    FADEOUT_HUD 0', '    DELAY 1', '    START_BATTLE 0', '    END_SECTION']
        open(f, 'w', encoding='utf-8').write('\n'.join(text) + '\n')
        report.append(f'script {script} section {sec}: new, default wild battle (talk/touch of screen {screen} '
                      f'slot {sec - 5})')
    return report


configure()
