#!/usr/bin/env python3
"""Digimon species as JSON: one complete file per species (docs/mods/species.md).

content/species/<id>-<name>.json describes every species the game knows: the 180 of the disc (0..179, with what the
C patch series changes, e.g. the NPC Digimon made partners) and the imported ones (180..1023), each file complete
(nothing is inherited at load time). This tool is the one reader of those files:

  * the tables of the executable (DIGIMON_DATA, RAISE_DATA, voices, training rows, ...) are written from the files
    of species 0..179 after linking (tools/balance.py build), and `verify` proves the C and the files agree;
  * DIGI.DAT, the archive the mod executable reads species 180..1023 from (records, models, textures, icons,
    evolution links), is built from the files (`build`).

Usage:
  species.py disc-tables [--exe-dir DIR]
                                    content/tables/disc-species.json, content/tables/skeletons.json, docs/data/species.csv:
                                    the disc's 180 species as numbers (the executable's rows, skeletons, names) from
                                    extracted/ (the USA disc), what the build reads instead of the disc's executable
  species.py extract [-o build/species-original] [--exe-dir DIR]
                                    the 180 files of the disc's species from extracted/ (original values), or from a
                                    compiled executable folder (the mod's effective values)
  species.py sync [--exe-dir DIR] [ID ... | --all]
                                    rewrite the table-made fields of content/species 0..179 from a linked build
                                    (default build/decomp-int/...): when a C patch changed a table on purpose; it
                                    refuses to overwrite edited files unless told which (ID ...) or --all
  species.py verify [--exe-dir DIR] the files of 0..179 encoded == the tables of a linked build (the drift check)
  species.py diff [DIR]             every field where content/species differs from DIR (default build/species-original)
  species.py materialize FILE|DIR ...
                                    convert files of the old sparse format ("base", "para", "partner.base") to
                                    complete files (today's effective values), in place
  species.py fmt [--check] [FILE ...] rewrite (or check) files in the canonical layout
  species.py add ID NAME --base TYPE [--hue DEG | --swap bgr | --texture FILE[:ENTRY]] [--model FILE.MMD]
                 [--set FIELD=VALUE ...] [--moves T T ...] [--partner [PARTNER_BASE]] [--evolves-from T ...] [-o FILE]
                                    a new species: a complete copy of TYPE's file with changes
  species.py build [-o build/species/DIGI.DAT] [--species SEL]
                                    DIGI.DAT (SEL: which species >= 180 it carries, see `select`)
  species.py select SEL -o DIR [--models M]
                                    a build's species folder: every original + the selected imports (SEL: ids,
                                    "all", folders; comma or space separated), model/texture paths under build/models,
                                    build/dcb, build/dw2 pointed to M
  species.py [--content DIR] disc-files
                                    the build-disc.py --file/--add arguments of the originals' replaced models
  species.py lint [--files] [--quiet]
                                    what the game cannot handle (errors) or probably not meant (warnings), with the
                                    file, field, value and why; build-full.sh runs it
  species.py list | show ID | check [DIGI.DAT] | maxmodel | disc NAME

Every key of the format is in docs/mods/species.md. Other tools read species through load_content(),
species_record(), table_rows(), extra_rows(), model_size(), wild_stats().
"""
import argparse, collections, csv, glob, json, os, re, struct, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
EXTRACTED = os.path.join(ROOT, 'extracted')
EXE_PATH = os.path.join(EXTRACTED, 'SLUS_010.32')
ALLTIM = os.path.join(EXTRACTED, 'CHDAT', 'ALLTIM.TIM')
CONTENT_DEFAULT = os.path.join(ROOT, 'content', 'species')
CONTENT = CONTENT_DEFAULT          # SPECIES_CONTENT=dirA:dirB: more content folders (tests); configure() sets it
ORIGINAL_DIR = os.path.join(ROOT, 'build', 'species-original')
OUT = os.path.join(ROOT, 'build', 'species', 'DIGI.DAT')
SPECIES_EXE_DIR = 'build/decomp-int/build/us/psx/gcc'     # the integration worktree: the series holds the species scale (patch 0065, DIGI.DAT v2)
INT_EXE_DIR = os.path.join(ROOT, 'build/decomp-int/build/us/psx/gcc')

EXE_BASE = 0x80090000
NUM_ORIGINAL = 180
NUM_DIGIMON = 1024               # capacity of the executable (include/dw/ids.h)
NUM_PARTNER = 66
RECORD_SIZE = 0x200
SECTOR = 0x800
TEX_SIZE = 0x4800                # one ALLTIM.TIM entry, 9 sectors
MAX_PARTNER_BONES = 34           # PARTNER_POSITION_DATA
MAX_BONES = 64
DEFAULT_SELECTION = '180,181,182,373'    # the integrated disc: Veemon, Puppetmon, Kimeramon, WarGreymon


# ------------------------------------------------------------------ the settings of a build (configure)
# rule: a setting that changes DIGI.DAT or its checks is a module global set by configure(), never read from the
# environment where it is used: the command line configures from its environment at import, a caller in the same
# process (tools/derive) calls configure() with the values of its build, so two builds in one process do not share them.
def configure(env=None, **kw):
    """Every setting from an environment (default os.environ, as the command line), then the keywords over it:
      content          SPECIES_CONTENT: the species folders (dirA:dirB), default content/species
      cold             COLD=1: cold animations (tools/coldsplit.py, patch 0113): the partners' rare animations are read
                       from the disc when they start
      partner_mmd_max  PARTNER_MMD_MAX of the executable (include/dw/memmap.h; default 0x20000)
      portraits        SPECIES_PORTRAITS=0: no icons (the game draws its fallback)
      ram_mb           SPECIES_RAM_MB: the RAM the disc is built for, 2 (console) or 8 (tier 2 build-full: one
                       executable, both)
      shard_scratch    EVL_SHARD_SCRATCH_SIZE: the evolution's shard scratch (include/dw/evl.h, the same in 2 MB and
                       8 MB mode: it is part of the EVL overlay; tools/build-full.sh exports the worktree's value): a
                       partner species must fit it (docs/mods/models.md "Digivolution shard buffer")
      shard_warn       SHARD_SCRATCH_WARN: an executable from before the bigger scratch: a partner past it is a warning"""
    global CONTENT, COLD, PARTNER_MMD_MAX, PORTRAITS, RAM_MB, SHARD_SCRATCH, SHARD_SCRATCH_WARN
    e = os.environ if env is None else env
    v = dict(content=e.get('SPECIES_CONTENT') or CONTENT_DEFAULT, cold=e.get('COLD') == '1',
             partner_mmd_max=int(e.get('PARTNER_MMD_MAX') or '0x20000', 0),
             portraits=e.get('SPECIES_PORTRAITS', '1') != '0', ram_mb=int(e.get('SPECIES_RAM_MB') or '2'),
             shard_scratch=int(e.get('EVL_SHARD_SCRATCH_SIZE') or '0x3000', 0),
             shard_warn=bool(e.get('SHARD_SCRATCH_WARN')))
    bad = set(kw) - set(v)
    if bad: raise TypeError(f'configure: no setting {", ".join(sorted(bad))}')
    v.update(kw)
    CONTENT, COLD, PARTNER_MMD_MAX, PORTRAITS = v['content'], v['cold'], v['partner_mmd_max'], v['portraits']
    RAM_MB, SHARD_SCRATCH, SHARD_SCRATCH_WARN = v['ram_mb'], v['shard_scratch'], v['shard_warn']
    return v


configure()

# the disc's species as committed numbers (`species.py disc-tables` makes them from a disc's extracted/)
DISC_SPECIES = os.path.join(ROOT, 'content', 'tables', 'disc-species.json')
DISC_SKELETONS = os.path.join(ROOT, 'content', 'tables', 'skeletons.json')
SPECIES_CSV = os.path.join(ROOT, 'docs', 'data', 'species.csv')
# the USA executable, read only by `disc-tables` (decomp/config/us/symbols.txt)
SYM = dict(NAMES=0x80133B44, SKELETONS=0x8011CE60)

FLAG_DEFINED, FLAG_PARTNER, FLAG_COND_FX, FLAG_EFFECT_DEFAULT = 1, 2, 4, 8
MAX_EFFECT_ORIGINS = 8
ANY_OFFSET = -0x8000
TEX_ALLTIM, TEX_ARCHIVE = 0, 1

# struct layouts (include/dw/params.h, partner.h, evl.h)
PARA_FIELDS = [('name', '20s'), ('boneCount', 'i'), ('radius', 'h'), ('height', 'h'), ('type', 'B'),
               ('level', 'B'), ('special', '3B'), ('dropItem', 'B'), ('dropChance', 'B'),
               ('moves', '16B'), ('padding', 'B')]
RAISE_FIELDS = [('hungerTimes', '8b'), ('energyCap', 'B'), ('energyThreshold', 'B'), ('energyUsage', 'B'),
                ('pad', 'x'), ('poopTimer', 'h'), ('unk2', 'h'), ('poopSize', 'B'), ('favoriteFood', 'B'),
                ('sleepCycle', 'B'), ('favoredRegion', 'B'), ('trainingType', 'B'), ('defaultWeight', 'B'),
                ('viewX', 'h'), ('viewY', 'h'), ('viewZ', 'h')]
REQ_FIELDS = [(k, 'h') for k in ('digimon', 'hp', 'mp', 'offense', 'defense', 'speed', 'brain', 'care',
                                  'weight', 'discipline', 'happiness', 'battles', 'techs')] + \
             [('flags', 'b'), ('padding', 'B')]
GAIN_FIELDS = [(k, 'h') for k in ('hp', 'mp', 'offense', 'defense', 'speed', 'brains', 'targetDigimon')]
STAT_KEYS = ('hp', 'mp', 'offense', 'defense', 'speed', 'brains')

# ------------------------------------------------------------------ names of the values (docs/mods/species.md)
LEVELS = ['none', 'fresh', 'in-training', 'rookie', 'champion', 'ultimate', 'mega']        # include/dw/level.h
ATTRIBUTES = ['none', 'data', 'vaccine', 'virus']                   # FLEE_CHANCES rows (btl.c)
ELEMENTS = ['fire', 'battle', 'air', 'nature', 'ice', 'mech', 'filth']                     # TYPE_FACTORS rows
SLEEP_CYCLES = ['16:00-01:00', '19:00-04:00', '22:00-07:00', '02:00-11:00', '07:00-16:00', '10:00-19:00',
                'fresh', 'in-training']                             # SLEEP_PATTERN rows (partner_impl.c)
TRAINING_TYPES = ['even', 'offense-speed', 'mp-brains', 'hp-defense', 'all-low']   # TRN_calculateTrainingMultiplier
BATTLE_MUSIC = ['event-battle', 'normal-battle', 'normal-battle-2', 'last-battle']  # font 0x21 tracks (BGM_TRACK_NAMES)


def _fmt(fields):
    return '<' + ''.join(f for _, f in fields)


def unpack(fields, data, off=0):
    vals = list(struct.unpack_from(_fmt(fields), data, off)); out = {}
    for name, f in fields:
        if f == 'x': continue
        n = int(f[:-1]) if f[:-1].isdigit() else 1
        if f.endswith('s'):
            # surrogateescape: a byte >= 0x80 (a Shift-JIS or F0xx glyph of another text source's name) round-trips through pack
            out[name] = vals.pop(0).split(b'\0')[0].decode('ascii', 'surrogateescape')
        elif n > 1:
            out[name] = [vals.pop(0) for _ in range(n)]
        else:
            out[name] = vals.pop(0)
    return out


def pack(fields, d):
    vals = []
    for name, f in fields:
        if f == 'x': continue
        n = int(f[:-1]) if f[:-1].isdigit() else 1
        v = d[name]
        if f.endswith('s'):
            b = v.encode('ascii', 'surrogateescape') if isinstance(v, str) else v
            if len(b) >= n: raise SystemExit(f'{name} "{v}" is longer than {n - 1} characters')
            vals.append(b)
        elif n > 1:
            if len(v) != n: raise SystemExit(f'{name} needs {n} values, got {len(v)}')
            vals.extend(v)
        else:
            vals.append(v)
    return struct.pack(_fmt(fields), *vals)


def zero_row(fields):
    return {n: ('' if f.endswith('s') else [0] * int(f[:-1]) if f[:-1].isdigit() else 0) for n, f in fields if f != 'x'}


def _csv_names(name):
    p = os.path.join(ROOT, 'docs', 'data', name)
    if not os.path.exists(p): return {}
    return {int(r['id']): r['name'] for r in csv.DictReader(open(p, newline=''))}


_NAMES = {}


def names(kind):
    """{id: name} of techniques or items (docs/data/techs.csv, items.csv: made from the disc by tools/dwtables.py)."""
    if kind not in _NAMES: _NAMES[kind] = _csv_names(kind + '.csv')
    return _NAMES[kind]


def name_of(kind, i):
    """A technique or item id as the files write it: its name, "Name (id)" for a name shared by several ids, the
    number for an id without a name."""
    n = names(kind)
    if i not in n: return i
    return n[i] if list(n.values()).count(n[i]) == 1 else f'{n[i]} ({i})'


def id_of(kind, v, where):
    if isinstance(v, int) and not isinstance(v, bool): return v
    n = names(kind)
    if not isinstance(v, str): raise SystemExit(f'{where}: {v!r} is not a {kind[:-1]} name or number')
    m = re.fullmatch(r'(.*) \((\d+)\)', v)
    if m:
        i = int(m.group(2))
        if n.get(i) != m.group(1): raise SystemExit(f'{where}: {kind[:-1]} {i} is "{n.get(i)}", not "{m.group(1)}"')
        return i
    label = {'techs': 'technique', 'items': 'item'}.get(kind, kind)
    hits = [i for i, x in n.items() if x == v]
    if not hits:
        import difflib
        close = [x for x in n.values() if x.lower() == v.lower()] or difflib.get_close_matches(v, list(n.values()), 1)
        hint = f' (did you mean "{close[0]}"?)' if close else ''
        raise SystemExit(f'{where}: no {label} "{v}"{hint} (docs/data/{kind}.csv)')
    if len(hits) > 1:
        raise SystemExit(f'{where}: "{v}" names the {label}s {", ".join(map(str, hits))}: write "{v} ({hits[0]})"')
    return hits[0]


def enum_value(table, v, where, key):
    if isinstance(v, int) and not isinstance(v, bool): return v
    if v in table: return table.index(v)
    raise SystemExit(f'{where}: {key} "{v}" is not one of {", ".join(table)}')


def enum_name(table, i):
    return table[i] if 0 <= i < len(table) else i


# ------------------------------------------------------------------ the disc's species (original values)
def disc_record(t, rows, model_name, bones):
    """The record of the disc's species t (the shape of DIGI.DAT's records and of what tools read: para, bones, raise,
    evoReqs, ...) from its rows of the executable's tables (disc-species.json), the shape the game's tables give it:
    the partner block only for 1..65, evolution requirements for 1..62, paths for 1..62, training rows for 0..66."""
    r = dict(id=t, para=rows['para'], modelName=model_name, modelSector=0, modelSize=0, texFile=TEX_ALLTIM,
             texSector=t * 9, texSectors=9, originalType=rows['originalType'], vball=rows['vball'], vlall=15,
             flags=FLAG_DEFINED, bones=[list(b) for b in bones])
    if 1 <= t < NUM_PARTNER:
        r['flags'] |= FLAG_PARTNER
        r['vlall'] = rows['vlall']
        r['raise'] = rows['raise']
        r['evoReqs'] = rows['evoReqs'] if t < 63 else None
        r['evoGains'] = rows['evoGains']
        if t - 1 < 62: r['evoPaths'] = rows['evoPaths']
        r['itemTakeDistance'] = rows['itemTakeDistance']
    if t < 67: r['trainingAnims'] = rows['trainingAnims']
    return r


class Originals:
    """The 180 species of the disc, as records (used by `extract`, the models, the skeletons, the records DIGI.DAT keeps
    of the disc), from the committed tables: content/tables/disc-species.json (every per-species row of the executable
    and its overlays, the model file names, the rows the code holds as immediates) and content/tables/skeletons.json
    (DIGIMON_SKELETONS). rule: the build reads no executable of the disc: a European disc has another one, with the same
    species (docs/mods/data-sources.md); `species.py disc-tables` makes both files from a disc's extracted/."""

    def __init__(self):
        doc = json.load(open(DISC_SPECIES)); sk = json.load(open(DISC_SKELETONS))
        if len(doc['species']) != NUM_ORIGINAL or len(sk['species']) != NUM_ORIGINAL:
            raise SystemExit(f'{DISC_SPECIES}, {DISC_SKELETONS}: {NUM_ORIGINAL} species each')
        self.rows = {}
        self.skeleton_name = list(sk['species'])     # DIGIMON_SKELETONS: a shared name is a shared array (one skeleton)
        self.rec = []
        for t, d in enumerate(doc['species']):
            if d['id'] != t: raise SystemExit(f'{DISC_SPECIES}: species {t} has id {d["id"]}')
            self.rows[t] = {k: v for k, v in d.items() if k not in ('id', 'model')}
            name = self.skeleton_name[t]
            self.rec.append(disc_record(t, self.rows[t], d['model'], sk['skeletons'][name] if name else []))

    def original_type(self, t):
        """getOriginalType (map.c): the type whose technique effects, aura and icons it uses."""
        if t < 0 or t > 0xB0: return -1
        ot = self.rec[t]['originalType']
        return t if ot < 0 else ot

    def model_path(self, t):
        name = self.rec[t]['modelName']
        p = glob.glob(os.path.join(EXTRACTED, 'CHDAT', 'MMD*', name + '.MMD'))
        return p[0] if p else None


_ORIG = None


def originals():
    global _ORIG
    if _ORIG is None: _ORIG = Originals()
    return _ORIG


def disc_names():
    """{id: name} of the disc's 180 species (docs/data/species.csv, made with the tables by `disc-tables`): the name of an
    id with no species file (the story that names it still compiles). The file is required (open() raises)."""
    return {int(r['id']): r['name'] for r in csv.DictReader(open(SPECIES_CSV, newline=''))}


def read_disc_tables(exe_dir=None):
    """(disc-species document, skeletons document, [(id, name)]) of the disc of an extracted/ folder (default
    extracted/, the USA disc): the executable's per-species tables decoded as balance.py reads them (DIGIMON_DATA,
    RAISE_DATA, the evolution tables, voices, TRN_REL.BIN's training rows, ...), the reincarnation stats and new-game
    techniques the code holds as immediates, the model file names (char[8][180] at 0x80133B44) and DIGIMON_SKELETONS,
    each array named by its symbol. A developer tool: the build reads the files it makes."""
    exe_dir = exe_dir or EXTRACTED
    rows, exe = exe_files(exe_dir, disc=True)
    d = open(exe.path('SLUS_010.32'), 'rb').read()
    f = lambda a: a - EXE_BASE
    syms = {}
    for line in open(os.path.join(ROOT, 'decomp/config/us/symbols.txt')):
        m = re.match(r'(\w+)\s*=\s*(0x[0-9A-Fa-f]+);', line)
        if m: syms.setdefault(int(m.group(2), 16), m.group(1))
    species, skeletons, names, per = [], collections.OrderedDict(), [], []
    for t in range(NUM_ORIGINAL):
        model = d[f(SYM['NAMES']) + 8 * t:f(SYM['NAMES']) + 8 * t + 8].split(b'\0')[0].decode()
        r = json.loads(json.dumps(rows[t]))
        species.append(collections.OrderedDict([('id', t), ('model', model)] + list(r.items())))
        names.append((t, r['para']['name']))
        sp = struct.unpack_from('<I', d, f(SYM['SKELETONS']) + 4 * t)[0]
        n = r['para']['boneCount']
        if not sp:
            if n: raise SystemExit(f'species {t}: {n} bones and no skeleton')
            per.append(None); continue
        name = syms.get(sp, f'SKELETON_{sp:08X}')
        bones = [list(struct.unpack_from('<bb', d, f(sp) + 2 * i)) for i in range(n)]
        if skeletons.setdefault(name, bones) != bones: raise SystemExit(f'{name}: types with different bone counts')
        per.append(name)
    return ({'species': species}, collections.OrderedDict([('skeletons', skeletons), ('species', per)]), names)


def cmd_disc_tables(a):
    """content/tables/disc-species.json, content/tables/skeletons.json and docs/data/species.csv from a disc."""
    import content as C
    doc, sk, names = read_disc_tables(a.exe_dir)
    C.write(DISC_SPECIES, doc); C.write(DISC_SKELETONS, sk)
    with open(SPECIES_CSV, 'w', newline='') as fh:
        w = csv.writer(fh, lineterminator='\n'); w.writerow(['id', 'name']); w.writerows(names)
    print(f'{len(doc["species"])} species, {len(sk["skeletons"])} skeletons from {os.path.relpath(a.exe_dir or EXTRACTED, ROOT)}: '
          f'{", ".join(os.path.relpath(p, ROOT) for p in (DISC_SPECIES, DISC_SKELETONS, SPECIES_CSV))}')


def original_code_rows(exe_path):
    """The rows the original executable keeps as code, not data: the reincarnation stats (initializeReincarnatedPartner)
    and the new-game techniques (initializePartner), read from the instructions' immediates. Returns
    ({type: [hp, mp, offense, defense, speed, brains]}, {type: (technique, animation)})."""
    d = open(exe_path, 'rb').read()
    syms = {}
    for line in open(os.path.join(ROOT, 'decomp/config/us/symbols.txt')):
        m = re.match(r'(\w+)\s*=\s*(0x[0-9A-Fa-f]+);', line)
        if m: syms[m.group(1)] = int(m.group(2), 16)
    def run(func, callee, n=220):
        regs, stack, typ, last_sb, out = {0: 0}, {}, None, None, []
        pc = syms[func]; end = pc + 4 * n; pending = None
        while pc < end:
            w = struct.unpack_from('<I', d, pc - EXE_BASE)[0]; pc += 4
            op, rs, rt, imm = w >> 26, (w >> 21) & 31, (w >> 16) & 31, w & 0xFFFF
            simm = imm - 0x10000 if imm & 0x8000 else imm
            if op == 0 and (w & 0x3F) in (0x21, 0x25) and rt == 0:          # addu/or rd, rs, $zero: a move
                regs[(w >> 11) & 31] = regs.get(rs)
            elif op == 9 and rs == 0: regs[rt] = simm                       # addiu rt, $zero, imm
            elif op == 0x2B and rs == 29: stack[simm] = regs.get(rt)         # sw rt, off($sp)
            elif op == 0x28: last_sb = regs.get(rt)                          # sb rt, ...
            elif op == 5 and rs == 16 and rt == 1:                           # bne $s0, $at: the type compared, a new block
                typ = regs.get(1); regs = {0: 0}; stack = {}
            elif op == 3:                                                     # jal
                pending = ((w & 0x3FFFFFF) << 2) | (pc & 0xF0000000); continue
            if pending is not None:                                          # the delay slot ran: the call
                if pending == syms[callee]: out.append((typ, dict(regs), dict(stack), last_sb))
                pending = None
        return out
    stats = {t: [r[4], r[5], r[6], r[7], s[0x10], s[0x14]] for t, r, s, _ in run('initializeReincarnatedPartner', 'setReincarnateStats')}
    techs = {t: (r[4], sb) for t, r, _, sb in run('initializePartner', 'learnMove')}
    return stats, techs


# ------------------------------------------------------------------ the per-species rows of the executable tables
TABLE_KEYS = ('para', 'raise', 'itemTakeDistance', 'vlall', 'vball', 'originalType', 'trainingAnims', 'training2Anims',
              'battleMusic', 'reincarnation', 'newGameTechnique')


def is_partner_row(raise_row):
    """A RAISE_DATA row of a partner: anything set but the hours terminator and the status screen position (the
    Tamer's row, type 0, has only those)."""
    if raise_row is None: return False
    h = raise_row['hungerTimes']
    return any(v for k, v in raise_row.items() if k not in ('hungerTimes', 'viewX', 'viewY', 'viewZ')) or \
        not (all(x == 0 for x in h) or all(x == -1 for x in h))     # 62 WereGarurumon: only hours (a placeholder row)


def _hours(v):
    out = []
    for i, h in enumerate(v):
        if h == -1 and all(x == -1 for x in v[i:]): return out
        out.append(h)
    return out


def raise_to_json(r, training, training2, item, vlall):
    p = collections.OrderedDict()
    p['voice'] = vlall
    p['hunger_hours'] = _hours(r['hungerTimes'])
    p['energy_max'] = r['energyCap']; p['energy_fed'] = r['energyThreshold']; p['energy_per_hour'] = r['energyUsage']
    p['poop_timer_10min'] = r['poopTimer']; p['poop_size'] = r['poopSize']
    if r['unk2'] != 1200: p['unk2'] = r['unk2']
    p['favorite_food'] = name_of('items', r['favoriteFood'])
    p['sleep_cycle'] = enum_name(SLEEP_CYCLES, r['sleepCycle'])
    p['favored_region'] = r['favoredRegion']
    p['training_type'] = enum_name(TRAINING_TYPES, r['trainingType'])
    p['birth_weight'] = r['defaultWeight']
    p['status_screen_position'] = [r['viewX'], r['viewY'], r['viewZ']]
    p['item_distance'] = item
    p['training'] = {'animation': training[0], 'hit_tick': training[1]}
    if training2 != training: p['training2'] = {'animation': training2[0], 'hit_tick': training2[1]}
    return p


PARTNER_KEYS = ['voice', 'hunger_hours', 'energy_max', 'energy_fed', 'energy_per_hour', 'poop_timer_10min', 'poop_size',
                'unk2', 'favorite_food', 'sleep_cycle', 'favored_region', 'training_type', 'birth_weight',
                'status_screen_position', 'item_distance', 'training', 'training2']
PARTNER_REQUIRED = ['hunger_hours', 'energy_max', 'energy_fed', 'energy_per_hour', 'poop_timer_10min', 'poop_size',
                    'favorite_food', 'sleep_cycle', 'birth_weight', 'status_screen_position']


def _training(v, where):
    if not isinstance(v, dict) or set(v) - {'animation', 'hit_tick'}:
        raise SystemExit(f'{where}: {{"animation": 46..61, "hit_tick": ticks}}')
    return [v.get('animation', 0x2E), v.get('hit_tick', 10)]


def raise_from_json(p, where):
    """(raise row, training, training2, item distance, vlall) of a partner block."""
    unknown = set(p) - set(PARTNER_KEYS)
    if unknown: raise SystemExit(f'{where}.partner: unknown key {", ".join(sorted(unknown))} (keys: {", ".join(PARTNER_KEYS)})')
    missing = [k for k in PARTNER_REQUIRED if k not in p]
    if missing: raise SystemExit(f'{where}.partner: missing {", ".join(missing)} (required: {", ".join(PARTNER_REQUIRED)})')
    hours = list(p['hunger_hours'])
    if len(hours) > 8: raise SystemExit(f'{where}.partner.hunger_hours: at most 8 hours')
    pos = p['status_screen_position']
    if not (isinstance(pos, list) and len(pos) == 3): raise SystemExit(f'{where}.partner.status_screen_position: [x, y, z]')
    r = dict(hungerTimes=hours + [-1] * (8 - len(hours)), energyCap=p['energy_max'], energyThreshold=p['energy_fed'],
             energyUsage=p['energy_per_hour'], poopTimer=p['poop_timer_10min'], unk2=p.get('unk2', 1200),
             poopSize=p['poop_size'], favoriteFood=id_of('items', p['favorite_food'], f'{where}.partner.favorite_food'),
             sleepCycle=enum_value(SLEEP_CYCLES, p['sleep_cycle'], where, 'partner.sleep_cycle'),
             favoredRegion=p.get('favored_region', 0),
             trainingType=enum_value(TRAINING_TYPES, p.get('training_type', 0), where, 'partner.training_type'),
             defaultWeight=p['birth_weight'], viewX=pos[0], viewY=pos[1], viewZ=pos[2])
    tr = _training(p.get('training', {}), f'{where}.partner.training')
    tr2 = _training(p['training2'], f'{where}.partner.training2') if 'training2' in p else list(tr)
    return r, tr, tr2, p.get('item_distance', 10), p.get('voice', 15)


def techniques_to_json(moves):
    if all(m == 0 for m in moves): return None          # sixteen 0s: the row of the NPC-only species (no techniques)
    ms = list(moves)
    while ms and ms[-1] == 0xFF: ms.pop()
    return [None if m == 0xFF else name_of('techs', m) for m in ms]


def techniques_from_json(v, where):
    if v is None: return [0] * 16
    if not isinstance(v, list) or len(v) > 16: raise SystemExit(f'{where}.techniques: a list of at most 16 techniques (or null)')
    ids = [0xFF if m is None else id_of('techs', m, f'{where}.techniques') for m in v]
    return ids + [0xFF] * (16 - len(ids))


def specialties_to_json(sp):
    return [None if e == 0xFF else enum_name(ELEMENTS, e) for e in sp]


def specialties_from_json(v, where):
    if not isinstance(v, list) or len(v) != 3: raise SystemExit(f'{where}.specialties: three slots (an element or null)')
    return [0xFF if e is None else enum_value(ELEMENTS, e, where, 'specialties') for e in v]


def stats_json(v):
    return collections.OrderedDict(zip(STAT_KEYS, v))


# ------------------------------------------------------------------ the file format: dict <-> JSON
KEY_ORDER = ['id', 'name', '_source', 'level', 'vanilla', 'vanilla_as', 'attribute', 'specialties', 'techniques', 'drop', 'effects_like', 'model',
             'texture', 'voice', 'battle_music', 'reincarnation_stats', 'new_game_technique', 'status_screen_position',
             'partner_voice', 'item_distance', 'training', 'condition_bubble', 'effect_origins', 'effect_origin_fallback', 'wild', 'sizing', 'size', 'needs_ram_mb',
             'partner', 'care', 'evolution']
REQUIRED = ['id', 'name', 'level', 'attribute', 'specialties', 'techniques', 'model', 'voice', 'battle_music']
MODEL_KEYS = ['name', 'bones', 'file', 'partner_file', 'from', 'radius', 'height', 'skeleton', 'slot_aliases']


def ordered_file(s):
    out = collections.OrderedDict()
    for k in KEY_ORDER:
        if k in s: out[k] = s[k]
        for c in [x for x in s if x.startswith('_') and x != '_source' and x not in out]:
            if c[1:] == k: out[c] = s[c]           # a comment "_key" follows its key
    for k in s:
        if k not in out: out[k] = s[k]
    return out


def table_rows(s):
    """The rows of the executable's per-species tables of one file (species 0..179)."""
    w = s.get('_path', f'species {s.get("id")}')
    t = s['id']
    para = para_from_json(s, w)
    rows = dict(para=para, originalType=s.get('effects_like', -1), vball=s['voice'])
    if 'partner' in s:
        r, tr, tr2, item, vlall = raise_from_json(s['partner'], w)
        rows.update(raise_=r, trainingAnims=tr, training2Anims=tr2, itemTakeDistance=item, vlall=vlall)
    else:
        r = zero_row(RAISE_FIELDS)
        if 'status_screen_position' in s:           # not a partner, but a row with a status screen position (the Tamer)
            x, y, z = s['status_screen_position']
            r.update(hungerTimes=[-1] * 8, viewX=x, viewY=y, viewZ=z)
        rows.update(raise_=r, itemTakeDistance=s.get('item_distance', 0), vlall=s.get('partner_voice', 15),
                    trainingAnims=_training(s['training'], f'{w}.training') if 'training' in s else [0, 0])
        rows['training2Anims'] = rows['trainingAnims']
    rows['raise'] = rows.pop('raise_')
    rows['battleMusic'] = enum_value(BATTLE_MUSIC, s['battle_music'], w, 'battle_music') if 'battle_music' in s else None
    rs = s.get('reincarnation_stats')
    rows['reincarnation'] = [rs[k] for k in STAT_KEYS] if rs else None
    if s.get('new_game_technique') is not None:
        tech = id_of('techs', s['new_game_technique'], f'{w}.new_game_technique')
        if tech not in para['moves']: raise SystemExit(f'{w}.new_game_technique: not one of its techniques')
        rows['newGameTechnique'] = (tech, 0x2E + para['moves'].index(tech))
    else:
        rows['newGameTechnique'] = None
    fb = s.get('effect_origin_fallback')
    if fb is not None and not (isinstance(fb, list) and len(fb) == 4 and all(isinstance(v, int) for v in fb)):
        raise SystemExit(f'{w}.effect_origin_fallback: [bone, x, y, z]')
    rows['effectFallback'] = list(fb) if fb is not None else None
    return rows


def para_from_json(s, w):
    m = s['model']
    bones = len(m['skeleton']) if 'skeleton' in m else m['bones']   # a record original: its record's skeleton
    drop = s.get('drop', {})
    if set(drop) - {'item', 'percent'}: raise SystemExit(f'{w}.drop: {{"item": name, "percent": 0..100}}')
    lvl = enum_value(LEVELS, s['level'], w, 'level')
    para = dict(name=s['name'], boneCount=bones, radius=m['radius'], height=m['height'],
                type=enum_value(ATTRIBUTES, s['attribute'], w, 'attribute'), level=lvl,
                special=specialties_from_json(s['specialties'], w),
                dropItem=id_of('items', drop.get('item', 0), f'{w}.drop.item'), dropChance=drop.get('percent', 0),
                moves=techniques_from_json(s['techniques'], w), padding=0)
    return para


REQ_KEYS = [k for k, _ in REQ_FIELDS if k != 'padding']
GAIN_KEYS = ['hp', 'mp', 'offense', 'defense', 'speed', 'brains']


def disc_evolution_to_json(t, reqs, gains, paths):
    """The `evolution` of a species of the executable's tables (0..179, no record): its EVOLUTION_REQS and
    EVOLUTION_STATS_GAINS rows, and for types 1..62 its EVOLUTION_PATHS row, slot by slot (-1 = empty; a slot's position
    decides ties: the first target in "to" wins). The game's own values, the source of the build since 2026-10-15."""
    e = collections.OrderedDict()
    if paths is not None:
        e['from'] = list(paths['from']); e['to'] = list(paths['to'])
    e['requirements'] = collections.OrderedDict((k, reqs[k]) for k in REQ_KEYS)
    g = collections.OrderedDict((k, gains[k]) for k in GAIN_KEYS)
    if gains['targetDigimon'] != t: g['target'] = gains['targetDigimon']
    e['gains'] = g
    return e


def disc_evolution_rows(t, e):
    """(evoReqs, evoGains, evoPaths or None) of a species of the executable's tables, from its `evolution`."""
    r = dict(e['requirements']); r.setdefault('padding', 0)
    g = {k: e['gains'][k] for k in GAIN_KEYS}; g['targetDigimon'] = e['gains'].get('target', t)
    paths = {'from': list(e['from']), 'to': list(e['to'])} if 'from' in e else None
    return r, g, paths


def file_from_rows(t, rows, keep=None, model_name=''):
    """A species file (0..179) from the rows of the tables; keep: the keys the tables do not hold (model.file,
    model.partner_file, comments) taken from the previous file."""
    p = rows['para']; keep = keep or {}
    s = collections.OrderedDict(id=t, name=p['name'])
    s['level'] = enum_name(LEVELS, p['level'])
    s['attribute'] = enum_name(ATTRIBUTES, p['type'])
    s['specialties'] = specialties_to_json(p['special'])
    s['techniques'] = techniques_to_json(p['moves'])
    s['drop'] = collections.OrderedDict(item=name_of('items', p['dropItem']), percent=p['dropChance'])
    if rows['originalType'] != -1: s['effects_like'] = rows['originalType']
    m = collections.OrderedDict(name=model_name, bones=p['boneCount'])
    for k in ('file', 'partner_file'):
        if k in keep.get('model', {}): m[k] = keep['model'][k]
    m['radius'] = p['radius']; m['height'] = p['height']
    s['model'] = m
    s['voice'] = rows['vball']
    if rows.get('battleMusic') is not None: s['battle_music'] = enum_name(BATTLE_MUSIC, rows['battleMusic'])
    if rows.get('reincarnation'): s['reincarnation_stats'] = stats_json(rows['reincarnation'])
    if rows.get('newGameTechnique'): s['new_game_technique'] = name_of('techs', rows['newGameTechnique'][0])
    r = rows.get('raise')
    if is_partner_row(r):
        s['partner'] = raise_to_json(r, rows['trainingAnims'], rows['training2Anims'], rows['itemTakeDistance'], rows['vlall'])
    else:
        if r and (r['viewX'] or r['viewY'] or r['viewZ']):
            s['status_screen_position'] = [r['viewX'], r['viewY'], r['viewZ']]
        if rows.get('vlall') not in (None, 15): s['partner_voice'] = rows['vlall']
        if rows.get('itemTakeDistance'): s['item_distance'] = rows['itemTakeDistance']
        if rows.get('trainingAnims') and rows['trainingAnims'] != [0, 0]:
            s['training'] = {'animation': rows['trainingAnims'][0], 'hit_tick': rows['trainingAnims'][1]}
    if rows.get('evoReqs') is not None:
        s['evolution'] = disc_evolution_to_json(t, rows['evoReqs'], rows['evoGains'], rows.get('evoPaths'))
    for k, v in keep.items():
        if k.startswith('_') and k not in s: s[k] = v
    s = ordered_file(s)
    if p['padding']: raise SystemExit(f'species {t}: DigimonPara.padding is {p["padding"]}, not 0')
    back = table_rows(json.loads(json.dumps(s)))
    for k in ('para', 'originalType', 'vball'):
        if back[k] != rows[k]: raise SystemExit(f'species {t}: {k} does not round-trip ({back[k]} != {rows[k]})')
    if r is not None and back['raise'] != r: raise SystemExit(f'species {t}: the raise row does not round-trip ({r})')
    return s


# ------------------------------------------------------------------ writer: canonical text (decision H)
WIDTH = 116


def _scalar(v):
    return json.dumps(v, ensure_ascii=False)


def _inline(v):
    if isinstance(v, dict): return '{' + ', '.join(f'{_scalar(k)}: {_inline(x)}' for k, x in v.items()) + '}'
    if isinstance(v, list): return '[' + ', '.join(_inline(x) for x in v) + ']'
    return _scalar(v)


def _leaf(v):
    return not isinstance(v, (dict, list)) or (isinstance(v, list) and all(_leaf(x) and not isinstance(x, list) for x in v))


def _wrap_list(items, col):
    """A list whose items are written inline, several to a line, wrapped at WIDTH; col: the column of its "["."""
    lines, cur = [], '['
    for i, it in enumerate(items):
        piece = it + (', ' if i < len(items) - 1 else ']')
        if col + len(cur) + len(piece.rstrip()) > WIDTH and cur.strip() != '[':
            lines.append(cur.rstrip()); cur = ' ' * (col + 1)
        cur += piece
    lines.append(cur)
    return '\n'.join(lines)


def _dump(v, indent, col=0):
    pad = ' ' * indent
    if isinstance(v, dict):
        one = _inline(v)
        if all(not isinstance(x, dict) and _leaf(x) for x in v.values()) and col + len(one) <= WIDTH and indent > 0:
            return one
        items = []
        for k, x in v.items():
            head = f'{pad}  {_scalar(k)}: '
            items.append(head + _dump(x, indent + 2, len(head)))
        return '{\n' + ',\n'.join(items) + '\n' + pad + '}'
    if isinstance(v, list):
        if not v: return '[]'
        if all(not isinstance(x, (dict, list)) for x in v) or all(isinstance(x, list) and _leaf(x) for x in v):
            return _wrap_list([_inline(x) for x in v], col)
        return '[\n' + ',\n'.join(f'{pad}  {_dump(x, indent + 2, indent + 2)}' for x in v) + '\n' + pad + ']'
    return _scalar(v)


def dumps(s):
    s = ordered_file({k: v for k, v in s.items() if k != '_path'})
    return _dump(s, 0) + '\n'


def file_name(s):
    slug = re.sub(r'[^a-z0-9]+', '-', s['name'].lower()).strip('-') or 'unnamed'
    return f'{s["id"]}-{slug}.json'


def write_file(path, s):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    open(path, 'w').write(dumps(s))


# ------------------------------------------------------------------ content
def content_files(content=None):
    content = content or CONTENT
    return sorted((f for d in content.split(os.pathsep) for f in glob.glob(os.path.join(d, '*.json'))),
                  key=lambda p: (int(re.match(r'\d+', os.path.basename(p)).group()) if re.match(r'\d+', os.path.basename(p)) else 1 << 30, p))


def validate(s):
    p = s['_path']
    if 'base' in s or 'para' in s:
        raise SystemExit(f'{p}: the old sparse format ("base", "para"): tools/species.py materialize {os.path.relpath(p, ROOT)}')
    missing = [k for k in REQUIRED if k not in s]
    if missing: raise SystemExit(f'{p}: missing {", ".join(missing)} (required: {", ".join(REQUIRED)})')
    unknown = [k for k in s if not k.startswith('_') and k not in KEY_ORDER]
    if unknown: raise SystemExit(f'{p}: unknown key {", ".join(unknown)} (keys: {", ".join(KEY_ORDER)})')
    t = s['id']
    if not 0 <= t < NUM_DIGIMON: raise SystemExit(f'{p}: id {t} must be 0..{NUM_DIGIMON - 1} (the executable\'s capacity)')
    m = s['model']
    bad = set(m) - set(MODEL_KEYS)
    if bad: raise SystemExit(f'{p}: model: unknown key {", ".join(sorted(bad))} (keys: {", ".join(MODEL_KEYS)})')
    for k in ('radius', 'height'):
        if k not in m: raise SystemExit(f'{p}: model.{k} is required')
    al = m.get('slot_aliases', [])
    if not isinstance(al, list) or any(not (isinstance(a, list) and len(a) == 2 and all(isinstance(x, int) for x in a)
                                            and 0 <= a[0] < 64 and 0 <= a[1] < 64) for a in al):
        raise SystemExit(f'{p}: model.slot_aliases: [[slot, slot of the clip it plays], ...], slots 0..63')
    if t < NUM_ORIGINAL:
        for k in ('name', 'bones'):
            if k not in m: raise SystemExit(f'{p}: model.{k} is required for a species of the disc (0..179)')
    if t < NUM_ORIGINAL and 'skeleton' in m:     # a record original: the disc's model.name/bones and an import's model
        if 'file' not in m: raise SystemExit(f'{p}: model.file is required with model.skeleton (a record original)')
        if 'effects_like' not in s: raise SystemExit(f'{p}: effects_like is required with model.skeleton (a record original)')
        if 'texture' not in s: raise SystemExit(f'{p}: texture is required with model.skeleton (a record original)')
        if 'partner_file' in m: raise SystemExit(f'{p}: model.partner_file: not with model.skeleton (the record holds the model)')
    elif t < NUM_ORIGINAL:
        for k in ('from', 'texture'):
            if k in m or k in s and k == 'texture': raise SystemExit(f'{p}: {k}: only for an imported species (180..) or with model.skeleton')
        e = s.get('evolution')
        if e is not None:                        # the disc's rows (disc_evolution_to_json): slot lists, every field
            if set(e) - {'from', 'to', 'requirements', 'gains'}: raise SystemExit(f'{p}: evolution: keys from, to, requirements, gains')
            if 1 <= t <= 62:
                if not (len(e.get('from', [])) == 5 and len(e.get('to', [])) == 6):
                    raise SystemExit(f'{p}: evolution: from has 5 slots and to 6 (-1 = empty; EVOLUTION_PATHS, types 1..62)')
            elif 'from' in e or 'to' in e:
                raise SystemExit(f'{p}: evolution.from/to: only types 1..62 have paths in the executable (a species reaches '
                                 f'this one through another\'s "to")')
            if [k for k in e.get('requirements', {})] != REQ_KEYS: raise SystemExit(f'{p}: evolution.requirements: {", ".join(REQ_KEYS)}')
            if set(e.get('gains', {})) - set(GAIN_KEYS) - {'target'} or not set(GAIN_KEYS) <= set(e.get('gains', {})):
                raise SystemExit(f'{p}: evolution.gains: {", ".join(GAIN_KEYS)} (+ target)')
    else:
        if 'skeleton' not in m: raise SystemExit(f'{p}: model.skeleton is required for an imported species')
        if 'file' not in m and 'from' not in m: raise SystemExit(f'{p}: model.file (or model.from) is required')
        if 'effects_like' not in s: raise SystemExit(f'{p}: effects_like is required for an imported species')
        if 'texture' not in s: raise SystemExit(f'{p}: texture is required for an imported species')
        for k in ('name', 'bones', 'partner_file'):
            if k in m: raise SystemExit(f'{p}: model.{k}: only for a species of the disc (0..179)')
    if 'vanilla' in s and (s['vanilla'] is not True or s['id'] >= NUM_ORIGINAL):
        raise SystemExit(f'{p}: vanilla: true, for a species the original game raises (left out otherwise)')
    if 'vanilla_as' in s and (s.get('vanilla') or 'partner' not in s or not isinstance(s['vanilla_as'], int)):
        raise SystemExit(f'{p}: vanilla_as: the id of the vanilla species a new partner becomes (tools/vanilla_as.py)')
    if ((s.get('evolution') or {}).get('requirements') or {}).get('digimon') == s['id']:
        raise SystemExit(f'{p}: evolution.requirements.digimon: the species itself (the bonus needs a parent, or -1)')
    para_from_json(s, p)
    if 'partner' in s: raise_from_json(s['partner'], p)
    if 'battle_music' in s: enum_value(BATTLE_MUSIC, s['battle_music'], p, 'battle_music')
    return s


def drop_absent_links(allsp):
    """Evolution links to an id of the disc (0..179) that has no file, when the content has the disc's species: that
    species does not exist (docs/mods/data-sources.md). An import's own links are dropped; a disc species' slot lists
    naming it are an error of the lint (their order is data)."""
    if not any(t < NUM_ORIGINAL for t in allsp): return
    gone = {t for t in range(NUM_ORIGINAL) if t not in allsp}
    for t, s in allsp.items():
        ev = s.get('evolution')
        if ev and (t >= NUM_ORIGINAL or is_record_original(s)):
            for k in ('from', 'to'):
                if k in ev: ev[k] = [o for o in ev[k] if o not in gone]


def load_file(path):
    s = json.load(open(path), object_pairs_hook=collections.OrderedDict)
    s['_path'] = path
    return validate(s)


def load_content(content=None, ids=None):
    """{id: file dict} of every species file of the content folders (0..1023)."""
    out = {}
    for p in content_files(content):
        s = load_file(p)
        t = s['id']
        if ids is not None and t not in ids: continue
        if t in out: raise SystemExit(f'{p}: id {t} is also defined in {out[t]["_path"]}')
        out[t] = s
    return out


def imports(content=None):
    """The imported species (180..) of the content folders."""
    return {t: s for t, s in load_content(content).items() if t >= NUM_ORIGINAL}


def is_record_original(s):
    """An original species (0..179) carried by its DIGI.DAT record (docs/mods/species.md "Record originals"): its file
    has an imported species' model (`model.skeleton`, `model.file`, `texture`). On a disc that carries it, the record
    replaces the disc's species (model, texture, skeleton, partner block, evolution); the executable's rows stay the
    C's, so a disc without it has the disc's species."""
    return s['id'] < NUM_ORIGINAL and 'skeleton' in s['model']


def carried(content=None):
    """The species DIGI.DAT can carry: the imports (180..) and the record originals."""
    return {t: s for t, s in load_content(content).items() if t >= NUM_ORIGINAL or is_record_original(s)}


_DISC_FILES = None


def disc_file(t):
    """The disc's species t as a file (the original values, content/tables/disc-species.json), what a record original is
    when not carried."""
    global _DISC_FILES
    if _DISC_FILES is None:
        O = originals()
        _DISC_FILES = {t: file_from_rows(t, O.rows[t], None, O.rec[t]['modelName']) for t in range(NUM_ORIGINAL)}
    s = json.loads(json.dumps(_DISC_FILES[t]), object_pairs_hook=collections.OrderedDict)
    s['_path'] = f'disc species {t}'
    return s


def resolve_path(p):
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def species_texture(s):
    """The 0x4800-byte texture of a species definition."""
    import mmd
    tex = s.get('texture') or {'from': s['id']}
    if 'file' in tex:
        data = open(resolve_path(tex['file']), 'rb').read()
        e = tex.get('entry', 0)
        blob = data[e * TEX_SIZE:(e + 1) * TEX_SIZE]
    else:
        blob = mmd.alltim_entry(open(ALLTIM, 'rb').read(), tex['from'])
    if len(blob) != TEX_SIZE: raise SystemExit(f'{s["_path"]}: the texture is not a 0x4800-byte ALLTIM entry')
    tim = mmd.Tim4(blob)
    if tex.get('hue') or tex.get('swap'):                 # the same as `mmd.py recolor`
        for r in range(tim.ch):
            pal = tim.pal[r]
            if tex.get('hue'): pal = [mmd.hue_shift(c, tex['hue']) for c in pal]
            if tex.get('swap'):
                sw = tex['swap']
                def f(c):
                    if c == 0: return 0
                    ch = dict(r=c & 31, g=c >> 5 & 31, b=c >> 10 & 31)
                    return (ch[sw[0]] | ch[sw[1]] << 5 | ch[sw[2]] << 10 | (c & 0x8000)) or 0x8000
                pal = [f(c) for c in pal]
            tim.pal[r] = pal
    return tim.to_bytes()


def resident_model(s, r, model):
    """(resident part, cold part) of a partner species' model: the whole model and nothing cold unless COLD=1 (and "cold": false opts out)."""
    if COLD and s['id'] >= NUM_ORIGINAL and r['flags'] & FLAG_PARTNER and s.get('cold', True):   # (the original ids carried by a record keep their file)
        import coldsplit
        return coldsplit.split(model, r['para']['boneCount'])
    return model, b''


def species_model(s):
    m = s['model']
    if 'file' in m: path = resolve_path(m['file'])
    elif 'from' in m: path = originals().model_path(m['from'])
    else: path = originals().model_path(s['id'])
    if not path or not os.path.exists(path): raise SystemExit(f'{s["_path"]}: no model file ({dict(m)})')
    data = open(path, 'rb').read()
    if m.get('slot_aliases'): data = apply_slot_aliases(data, s)
    return data, path


def apply_slot_aliases(data, s):
    """The model with `model.slot_aliases` applied: [slot, source] makes the slot play the source's clip (a table entry
    pointing at the same animation, as Agumon's several slots do), growing the table when the slot is beyond it. The
    file in build/ is not touched, so a rebuilt model keeps its aliases."""
    import mmd
    m = s['model']; nb = len(m['skeleton']) if 'skeleton' in m else m.get('bones')
    mm_ = mmd.MMD.parse(data, nb)
    if mm_.build() != data: raise SystemExit(f'{s["_path"]}: the model does not rebuild byte for byte: slot_aliases cannot be applied')
    tab = mm_.anims.table
    for dst, src in m['slot_aliases']:
        if src >= len(tab) or tab[src] is None: raise SystemExit(f'{s["_path"]}: model.slot_aliases: slot {src} has no animation in the model')
        tab.extend([None] * (dst + 1 - len(tab)))
        tab[dst] = tab[src]
    return mm_.build()


EVOLUTION_KEYS = ['from', 'to', 'requirements', 'gains']


def species_record(s):
    """A species file as a DIGI.DAT record dict (also the shape tools read: para, bones, raise, ...)."""
    w = s.get('_path', f'species {s["id"]}'); t = s['id']
    rows = table_rows(s)
    para = rows['para']
    if t < NUM_ORIGINAL and not is_record_original(s):
        O = originals()
        r = dict(id=t, para=para, modelName=s['model']['name'], flags=FLAG_DEFINED, originalType=rows['originalType'],
                 vball=rows['vball'], vlall=15, texFile=TEX_ALLTIM, texSector=t * 9, texSectors=9,
                 bones=[list(b) for b in O.rec[t]['bones']])
        if len(r['bones']) != para['boneCount']:
            raise SystemExit(f'{w}: model.bones is {para["boneCount"]}, the executable\'s skeleton has {len(r["bones"])}')
        if 'partner' in s:      # the evolution rows of the originals are not in the files yet: the disc's (as before)
            r['flags'] |= FLAG_PARTNER
            r.update(raise_=rows['raise'], vlall=rows['vlall'], itemTakeDistance=rows['itemTakeDistance'],
                     trainingAnims=rows['trainingAnims'], training2Anims=rows['training2Anims'])
            r['raise'] = r.pop('raise_')
            o = O.rec[t]
            if o.get('evoReqs'):
                r.update(evoReqs=o['evoReqs'], evoGains=o['evoGains'], evoPaths=o.get('evoPaths'))
    else:
        m = s['model']
        bones = [list(b) for b in m['skeleton']]
        r = dict(id=t, para=para, modelName='', flags=FLAG_DEFINED, originalType=s['effects_like'], vball=rows['vball'],
                 vlall=15, texFile=TEX_ARCHIVE, texSectors=9, bones=bones)
        if r['originalType'] < 0:
            raise SystemExit(f'{w}: effects_like must name a species with technique effect offsets')
        if 'partner' in s:
            r['flags'] |= FLAG_PARTNER
            r.update(raise_=rows['raise'], vlall=rows['vlall'], itemTakeDistance=rows['itemTakeDistance'],
                     trainingAnims=rows['trainingAnims'], training2Anims=rows['training2Anims'])
            r['raise'] = r.pop('raise_')
            ev = s.get('evolution') or {}
            bad = set(ev) - set(EVOLUTION_KEYS)
            if bad: raise SystemExit(f'{w}.evolution: unknown key {", ".join(sorted(bad))} ({", ".join(EVOLUTION_KEYS)})')
            reqs = {k: (-1 if f == 'h' else 0) for k, f in REQ_FIELDS}
            for k, v in (ev.get('requirements') or {}).items():
                if k not in reqs or k == 'padding': raise SystemExit(f'{w}.evolution.requirements.{k}: unknown ({", ".join(k for k, _ in REQ_FIELDS[:-1])})')
                reqs[k] = v
            gains = {k: 0 for k, _ in GAIN_FIELDS}
            for k, v in (ev.get('gains') or {}).items():
                if k not in gains or k == 'targetDigimon': raise SystemExit(f'{w}.evolution.gains.{k}: unknown ({", ".join(STAT_KEYS)})')
                gains[k] = v
            gains['targetDigimon'] = t
            frm, to = list(ev.get('from', [])), list(ev.get('to', []))
            if len(frm) > 5 or len(to) > 6: raise SystemExit(f'{w}.evolution: at most 5 "from" and 6 "to"')
            r.update(evoReqs=reqs, evoGains=gains, evoPaths={'from': frm + [-1] * (5 - len(frm)), 'to': to + [-1] * (6 - len(to))})
            if s.get('vanilla_as'): r['vanillaAs'] = s['vanilla_as']
            if len(bones) > MAX_PARTNER_BONES:
                raise SystemExit(f'{w}: a partner has at most {MAX_PARTNER_BONES} bones')
    if rows['battleMusic'] is not None: r['battleMusic'] = rows['battleMusic']
    if len(r['bones']) > MAX_BONES: raise SystemExit(f'{w}: more than {MAX_BONES} bones')
    eo = []
    for e in s.get('effect_origins', []):
        fb, fx, fy, fz, tb, tx, ty, tz = [ANY_OFFSET if v == 'any' else int(v) for v in e]
        if not 0 <= tb < len(r['bones']): raise SystemExit(f'{w}: effect origin bone {tb} is not a bone')
        eo.append([fb, fx, fy, fz, tb, tx, ty, tz])
    if len(eo) > MAX_EFFECT_ORIGINS: raise SystemExit(f'{w}: at most {MAX_EFFECT_ORIGINS} effect_origins')
    r['effectOrigins'] = eo
    if 'condition_bubble' in s:
        r['conditionFx'] = [int(v) for v in s['condition_bubble']]
        r['flags'] |= FLAG_COND_FX
    if t >= NUM_ORIGINAL or is_record_original(s):
        r['effectDefault'] = effect_default(s)[0]
        if not 0 <= r['effectDefault'][0] < len(r['bones']):
            raise SystemExit(f'{w}: effect origin default bone {r["effectDefault"][0]} is not a bone')
        r['flags'] |= FLAG_EFFECT_DEFAULT
    if (t >= NUM_ORIGINAL or is_record_original(s)) and 'partner' in s and len([m for m in para['moves'] if m != 0xFF]) == 0:
        raise SystemExit(f'{w}: no techniques: it could not fight')
    return r


# ------------------------------------------------------------------ the old sparse format (materialize only)
def _merge(base, over):
    out = json.loads(json.dumps(base))
    for k, v in (over or {}).items():
        out[k] = v
    return out


class _FileBases:
    """The disc's species as records made from their files (content/species: effective values), for new species."""

    def __init__(self):
        files = {t: x for t, x in load_content(CONTENT_DEFAULT).items() if t < NUM_ORIGINAL}
        self.rec = [species_record(files[t]) if t in files else originals().rec[t] for t in range(NUM_ORIGINAL)]

    def original_type(self, t):
        if t < 0 or t > 0xB0: return -1
        ot = self.rec[t]['originalType']
        return t if ot < 0 else ot


def legacy_record(s, from_files=False):
    """A file of the old sparse format as a record dict (the base species' record with the changes): what
    tools/species.py built before 2026-10-13 from the disc's rows (from_files False: the one-time conversion), or
    from the base's file (from_files True: a new species, `add` and import_batch.py)."""
    O = _FileBases() if from_files else originals(); b = s['base']
    if not 0 <= b < NUM_ORIGINAL: raise SystemExit(f'{s["_path"]}: base {b} must be an original species (0..179)')
    base = O.rec[b]
    r = dict(id=s['id'], para=_merge(base['para'], s.get('para')), modelName='', flags=FLAG_DEFINED,
             originalType=s.get('originalType', O.original_type(b)), vball=s.get('vball', base['vball']),
             vlall=s.get('vlall', base['vlall']), texFile=TEX_ARCHIVE, texSectors=9,
             bones=[list(x) for x in s.get('bones', base['bones'])])
    r['para']['name'] = s['name']
    if 'type' not in (s.get('para') or {}): r['para']['type'] = base['para']['type']
    if r['para']['boneCount'] != len(r['bones']):
        raise SystemExit(f'{s["_path"]}: boneCount {r["para"]["boneCount"]} but {len(r["bones"])} bones')
    if r['originalType'] < 0:
        raise SystemExit(f'{s["_path"]}: originalType must name a species with technique effect offsets')
    p = s.get('partner')
    if p is not None:
        pb = O.rec[p.get('base', b)]
        if not pb['flags'] & FLAG_PARTNER:
            raise SystemExit(f'{s["_path"]}: partner base {pb["id"]} is not a partner; give "partner": {{"base": T}}')
        r['flags'] |= FLAG_PARTNER
        r['raise'] = _merge(pb['raise'], p.get('raise'))
        reqs = pb.get('evoReqs') or {k: (-1 if f == 'h' else 0) for k, f in REQ_FIELDS}
        r['evoReqs'] = _merge(reqs, p.get('evoReqs')); r['evoReqs']['digimon'] = s['id']
        r['evoGains'] = _merge(pb.get('evoGains') or {k: 0 for k, _ in GAIN_FIELDS}, p.get('evoGains'))
        r['evoGains']['targetDigimon'] = s['id']
        frm = list(p.get('from', [])) + [-1] * 5; to = list(p.get('to', [])) + [-1] * 6
        r['evoPaths'] = {'from': frm[:5], 'to': to[:6]}
        r['itemTakeDistance'] = p.get('itemTakeDistance', pb['itemTakeDistance'])
        r['trainingAnims'] = p.get('trainingAnims', pb.get('trainingAnims', [0x2E, 0xA]))
        r['training2Anims'] = p.get('training2Anims', r['trainingAnims'])
        r['vlall'] = p.get('vlall', pb['vlall'])
    eo = []
    for e in s.get('effectOrigins', []):
        eo.append([ANY_OFFSET if v == 'any' else int(v) for v in e])
    r['effectOrigins'] = eo
    if 'conditionFx' in s:
        r['conditionFx'] = [int(v) for v in s['conditionFx']]
        r['flags'] |= FLAG_COND_FX
    return r


def materialize(old, from_files=False):
    """A complete file from a file of the old sparse format: the base's disc rows with the changes (from_files False:
    what the build made of it until 2026-10-13), or the base's file with the changes (a new species)."""
    r = legacy_record(old, from_files); p = r['para']; t = old['id']
    s = collections.OrderedDict(id=t, name=old['name'])
    if '_source' in old: s['_source'] = old['_source']
    s['level'] = enum_name(LEVELS, p['level'])
    s['attribute'] = enum_name(ATTRIBUTES, p['type'])
    s['specialties'] = specialties_to_json(p['special'])
    s['techniques'] = techniques_to_json(p['moves'])
    s['drop'] = collections.OrderedDict(item=name_of('items', p['dropItem']), percent=p['dropChance'])
    s['effects_like'] = r['originalType']
    m = collections.OrderedDict()
    mo = old.get('model', {'from': old['base']})
    for k in ('file', 'from'):
        if k in mo: m[k] = mo[k]
    m['radius'] = p['radius']; m['height'] = p['height']; m['skeleton'] = r['bones']
    s['model'] = m
    s['texture'] = old.get('texture', {'from': old['base']})
    s['voice'] = r['vball']
    s['battle_music'] = old.get('battle_music', 'normal-battle')     # what the game played for every import before the field
    if r.get('conditionFx'): s['condition_bubble'] = r['conditionFx']
    if r['effectOrigins']:
        s['effect_origins'] = [['any' if i in (1, 5) and v == ANY_OFFSET else v for i, v in enumerate(e)] for e in r['effectOrigins']]
    for k, v in old.items():
        if k.startswith('_') and k != '_source':
            s['_effect_origins' if k == '_effectOrigins' else k] = v
    for k in ('wild', 'sizing', 'needs_ram_mb'):
        if k in old: s[k] = old[k]
    if r['flags'] & FLAG_PARTNER:
        s['partner'] = raise_to_json(r['raise'], r['trainingAnims'], r['training2Anims'], r['itemTakeDistance'], r['vlall'])
        g = {k: v for k, v in r['evoGains'].items() if k != 'targetDigimon'}
        reqs = {k: v for k, v in r['evoReqs'].items() if k != 'padding'}
        if r['evoReqs']['padding']: raise SystemExit(f'{old["_path"]}: evoReqs.padding is not 0')
        s['evolution'] = collections.OrderedDict([('from', [x for x in r['evoPaths']['from'] if x != -1]),
                                                  ('to', [x for x in r['evoPaths']['to'] if x != -1]),
                                                  ('requirements', reqs), ('gains', g)])
    s = ordered_file(s)
    s['_path'] = old['_path']
    validate(json.loads(json.dumps(s), object_pairs_hook=collections.OrderedDict))
    del s['_path']
    return s


# ------------------------------------------------------------------ DIGI.DAT records
def pack_record(r):
    para = dict(r['para']); para.setdefault('padding', 0)
    b = bytearray(RECORD_SIZE)
    b[0:0x34] = pack(PARA_FIELDS, para)
    struct.pack_into('<8sIIIHHhBBHBB', b, 0x34, r['modelName'].encode(), r.get('modelSector', 0),
                     r.get('modelSize', 0), r['texSector'], r['texFile'], r['texSectors'], r['originalType'],
                     r['vball'], r['vlall'], r['flags'], r.get('battleMusic', 0), 0)
    for i, (o, p) in enumerate(r['bones']):
        struct.pack_into('<bb', b, 0x54 + 2 * i, o, p)
    if r['flags'] & FLAG_PARTNER and r.get('evoReqs'):
        b[0xD4:0xF0] = pack(RAISE_FIELDS, r['raise'])
        b[0xF0:0x10C] = pack(REQ_FIELDS, r['evoReqs'])
        b[0x10C:0x11A] = pack(GAIN_FIELDS, r['evoGains'])
        paths = r.get('evoPaths') or {'from': [-1] * 5, 'to': [-1] * 6}
        struct.pack_into('<5h6h', b, 0x11A, *paths['from'], *paths['to'])
        struct.pack_into('<b2b2b', b, 0x130, r['itemTakeDistance'], *r.get('trainingAnims', [0x2E, 0xA]),
                         *r.get('training2Anims', r.get('trainingAnims', [0x2E, 0xA])))
    elif r['flags'] & FLAG_PARTNER:                      # an original partner without evolution rows
        b[0xD4:0xF0] = pack(RAISE_FIELDS, r['raise'])
    if r.get('conditionFx'):
        struct.pack_into('<4h', b, 0x136, *r['conditionFx'])
    struct.pack_into('<I', b, 0x1C0, r.get('portrait', 0))      # sector | slot << 24 of its icon (tools/portraits.py)
    struct.pack_into('<h', b, 0x1CC, r.get('vanillaAs', 0))     # NEW DIGIMON off: the vanilla species it becomes
    if r['flags'] & FLAG_EFFECT_DEFAULT:                         # where a technique without an origin row starts (efe.c)
        struct.pack_into('<4h', b, 0x1C4, *r['effectDefault'])
    eo = r.get('effectOrigins') or []
    b[0x13E] = len(eo)
    for i, e in enumerate(eo):
        struct.pack_into('<8h', b, 0x140 + 16 * i, *e)
    return bytes(b)


def unpack_record(b, t):
    para = unpack(PARA_FIELDS, b, 0)
    (name, msec, msize, tsec, tfile, tsecs, ot, vball, vlall, flags, music, _) = struct.unpack_from('<8sIIIHHhBBHBB', b, 0x34)
    r = dict(id=t, para=para, modelName=name.split(b'\0')[0].decode(), modelSector=msec, modelSize=msize,
             texSector=tsec, texFile=tfile, texSectors=tsecs, originalType=ot, vball=vball, vlall=vlall, flags=flags,
             bones=[list(struct.unpack_from('<bb', b, 0x54 + 2 * i)) for i in range(max(0, min(para['boneCount'], MAX_BONES)))])
    if music: r['battleMusic'] = music
    if flags & FLAG_PARTNER:
        r['raise'] = unpack(RAISE_FIELDS, b, 0xD4)
        r['evoReqs'] = unpack(REQ_FIELDS, b, 0xF0)
        r['evoGains'] = unpack(GAIN_FIELDS, b, 0x10C)
        p = struct.unpack_from('<5h6h', b, 0x11A)
        r['evoPaths'] = {'from': list(p[:5]), 'to': list(p[5:])}
        r['itemTakeDistance'], a0, a1, c0, c1 = struct.unpack_from('<b2b2b', b, 0x130)
        r['trainingAnims'], r['training2Anims'] = [a0, a1], [c0, c1]
    if flags & FLAG_COND_FX:
        r['conditionFx'] = list(struct.unpack_from('<4h', b, 0x136))
    if b[0x13E] and t >= NUM_ORIGINAL:
        r['effectOrigins'] = [list(struct.unpack_from('<8h', b, 0x140 + 16 * i)) for i in range(b[0x13E])]
    if flags & FLAG_EFFECT_DEFAULT:
        r['effectDefault'] = list(struct.unpack_from('<4h', b, 0x1C4))
    return r


HEADER = '<4sHHHHIIIII'          # magic, version, record size, count, first record, records sector, total sectors, index sector, fallback portrait, chart sector
# the evolution chart's block (include/dw/species.h "chart"): its tabs, the levels each one shows, and its icons
CHART_TABS = [('fresh', 'in-training'), ('rookie',), ('champion',), ('ultimate',), ('mega',)]
CHART_SHEET = 61                 # types 1..61 have the chart sheet's hand-drawn icon (NUM_EVO_CHART_DIGIMON)
CHART_ICON_SIZE, CHART_ICONS_PER_SECTOR = 0xA0, 12   # a 16-colour CLUT and a 16x16 4 bpp image
HEADER_LEVELS = 0x40             # the header sector: the level of each partner species (one byte, partner list order)
HEADER_RECORD_ORIGINALS = 0x20   # the header sector: a bit per original carried by its record (23 bytes)
HEADER_VANILLA = 0x780           # the header sector: a bit per species the original game raises ("vanilla": NEW DIGIMON off)
VERSION = 2
HEADER_CITY = 0x38             # optional sector pointer; record format and existing header offsets stay v2
INDEX_SECTORS = 2                # the partner list and the evolution links (include/dw/species.h)
MAX_PARTNERS, MAX_LINKS = 1022, 510
EXTRA_PARENTS, EXTRA_TARGETS = 4, 12   # a Baby II's Rookies past its 6 "to" slots (species.h SPECIES_EXTRA_*)
LINK_FROM = 0x8000


BIG_MMD_MAX = 0x40000                                     # the 8 MB partner buffer (PARTNER_MMD_MAX_8MB)


def shard_need(model, bones):
    """Bytes EVL_buildShardSet reserves when this model evolves away: 6 * (vern + primn) of the piece of every bone but
    the root, all held until the sequence ends."""
    need = 0
    for b, (obj, parent) in enumerate(bones):
        if b and obj != -1:
            vern, primn = struct.unpack_from('<I', model, 20 + 28 * obj + 4)[0], struct.unpack_from('<I', model, 20 + 28 * obj + 20)[0]
            need += 6 * (vern + primn)
    return need


def for_ram(species, quiet=True):
    """The species a disc for RAM_MB of memory carries: one with "needs_ram_mb": 8 (a partner model that only fits the 8 MB
    buffer, tools/fitfix.py) is left out of a 2 MB disc (an undefined id, as a gap), and must fit the 8 MB buffer."""
    out = {}
    for t, s in species.items():
        need = int(s.get('needs_ram_mb', 2))
        if need > RAM_MB:
            if not quiet: print(f'{s["_path"]}: needs {need} MB of RAM, left out of this {RAM_MB} MB disc (SPECIES_RAM_MB=8 keeps it)')
            continue
        out[t] = s
    return out


def absent_rows(t):
    """The table rows of a species of the disc (0..179) that has no file: the id stays (the tables are indexed by it), the
    species does not exist (docs/mods/data-sources.md): no name, level none, no techniques, no partner, no evolution (the
    shape of the disc's own empty entries)."""
    para = unpack(PARA_FIELDS, bytes(struct.calcsize(_fmt(PARA_FIELDS))))
    para.update(name='', special=[0xFF] * 3, moves=[0xFF] * 16)
    return {'para': para, 'raise': unpack(RAISE_FIELDS, bytes(struct.calcsize(_fmt(RAISE_FIELDS)))),
            'itemTakeDistance': 0, 'vlall': 15, 'vball': 0, 'originalType': -1, 'trainingAnims': [0, 0],
            'training2Anims': [0, 0], 'battleMusic': 0, 'reincarnation': None, 'newGameTechnique': None,
            'evoReqs': unpack(REQ_FIELDS, bytes(struct.calcsize(_fmt(REQ_FIELDS)))),
            'evoGains': unpack(GAIN_FIELDS, bytes(struct.calcsize(_fmt(GAIN_FIELDS)))),
            'evoPaths': {'from': [-1] * 5, 'to': [-1] * 6} if 1 <= t <= 62 else None}


def absent_record(t):
    """The DIGI.DAT record of an id 0..179 with no file: the disc's record with an empty para and no flags (undefined)."""
    r = json.loads(json.dumps(originals().rec[t])); a = absent_rows(t)
    r['para'] = a['para']; r['flags'] = 0
    return r


def original_records(content=None, with_imports=True):
    """Records 0..179 of DIGI.DAT: from the files of the disc's species when the content has them (all 180), else
    copied from the disc's executable (sparse developer/test fixtures can omit the native JSON). An archive without
    imports (with_imports False) preserves the disc's records; the game reads this archive only when it contains
    more than 180 species."""
    allsp = load_content(content)
    orig = {t: s for t, s in allsp.items() if t < NUM_ORIGINAL}
    if orig and with_imports:                    # an id without a file is a species the game does not have
        return [(species_record(disc_file(t) if is_record_original(orig[t]) else orig[t]) if t in orig else absent_record(t))
                for t in range(NUM_ORIGINAL)], 'content'
    return [json.loads(json.dumps(r)) for r in originals().rec], 'disc'


def chart_tabs(allsp, species):
    """The species of each tab of the evolution chart (CHART_TABS): every partner species of the build, a level after
    the other, each level in the order of its parents in the level before (a family together), then by id."""
    members = {t: s for t, s in allsp.items() if t > 0 and 'partner' in s and (t < NUM_ORIGINAL or t in species)}
    parents = {t: set() for t in members}
    for t, s in members.items():
        e = s.get('evolution') or {}
        for p in e.get('from') or []:
            if p is not None and p in members: parents[t].add(p)
        for c in e.get('to') or []:
            if c is not None and c in members: parents[c].add(t)
    order, prev = {}, []
    for lv in [lv for tab in CHART_TABS for lv in tab]:
        pos = {p: k for k, p in enumerate(prev)}
        prev = order[lv] = sorted((t for t, s in members.items() if s.get('level') == lv),
                                  key=lambda t: (min([pos.get(p, 1 << 16) for p in parents[t]] or [1 << 16]), t))
    return [[t for lv in tab for t in order[lv]] for tab in CHART_TABS]


def chart_block(tabs, icon_of, fallback):
    """The chart block of DIGI.DAT (include/dw/species.h SpeciesChart): a sector with the count of each tab and the ids,
    tab after tab, then the icons in the same order, CHART_ICONS_PER_SECTOR to a sector: the 16x16 idle frame of each
    one's icon and its CLUT (the species of the chart sheet keep theirs: a blank slot)."""
    ids = [t for tab in tabs for t in tab]
    head = bytearray(SECTOR)
    if 2 * (len(tabs) + len(ids)) > SECTOR: raise SystemExit(f'{len(ids)} chart species: the chart sector holds {SECTOR // 2 - len(tabs)}')
    struct.pack_into(f'<{len(tabs)}H', head, 0, *map(len, tabs))
    struct.pack_into(f'<{len(ids)}H', head, 2 * len(tabs), *ids)
    icons = bytearray(-(-len(ids) // CHART_ICONS_PER_SECTOR) * SECTOR)
    for k, t in enumerate(ids):
        ic = None if t <= CHART_SHEET else icon_of.get(t, fallback)
        if ic is None: continue
        o = (k // CHART_ICONS_PER_SECTOR) * SECTOR + (k % CHART_ICONS_PER_SECTOR) * CHART_ICON_SIZE
        icons[o:o + 0x20] = ic[:0x20]
        for y in range(16):                       # frame 0: the top-left 16x16 of the 32x32 tile (16 bytes a row)
            icons[o + 0x20 + y * 8:o + 0x28 + y * 8] = ic[0x20 + y * 16:0x28 + y * 16]
    return bytes(head) + bytes(icons)


def build(out=OUT, content=None, quiet=False, select=None):
    O = originals()
    allsp = load_content(content)
    drop_absent_links(allsp)
    errs = lint({t: x for t, x in allsp.items() if t < NUM_ORIGINAL or select is None or t in select})[0]
    if errs: raise SystemExit('\n'.join('error: ' + e for e in errs) + '\n(tools/species.py lint: docs/mods/species.md)')
    species = for_ram({t: s for t, s in allsp.items() if (t >= NUM_ORIGINAL or is_record_original(s))
                       and (select is None or t in select)}, quiet)
    count = max(max(species) + 1, NUM_ORIGINAL) if species else NUM_ORIGINAL
    orig_recs, _ = original_records(content, bool(species))
    recs = orig_recs + [None] * (count - NUM_ORIGINAL)   # None: undefined
    blobs = []; links = []; shard_bad = []
    # the paths of the originals as the game starts with them, to see which slots are free
    paths = {f: {k: list(O.rec[f]['evoPaths'][k]) for k in ('from', 'to')} for f in range(1, 63) if O.rec[f].get('evoPaths')}
    # what the executable gets (balance.py layered): the disc's rows + the engine layer (the NPC partners' slots; still
    # what a row no species file holds comes from, e.g. a record original's), then the species files' rows (since 2026-10-15)
    eng = os.path.join(ROOT, 'content', 'balance', 'engine', 'tables.json')
    if os.path.exists(eng):
        for f, row in json.load(open(eng)).get('species', {}).items():
            for k, v in row.get('evoPaths', {}).items():
                if int(f) in paths: paths[int(f)][k] = list(v)
    has_disc = any(t < NUM_ORIGINAL for t in allsp)
    for f in list(paths):
        if has_disc and f not in allsp: paths[f] = {'from': [-1] * 5, 'to': [-1] * 6}; continue     # no file: no species
        e = allsp[f].get('evolution') if f in allsp else None
        if e and 'from' in e:
            # Even a record original <= 62 uses the resident path row in C.
            paths[f] = {k: (list(e.get(k, [])) + [-1] * n)[:n] for k, n in (('from', 5), ('to', 6))}
        gone = {t for t in range(NUM_ORIGINAL) if t not in allsp} if any(t < NUM_ORIGINAL for t in allsp) else set()
        paths[f] = {k: [-1 if x in gone else x for x in v] for k, v in paths[f].items()}       # (balance.py: absent ids)
    first_records = 1 + INDEX_SECTORS
    rec_sectors = -(-count * RECORD_SIZE // SECTOR)
    sector = first_records + rec_sectors
    for t in sorted(species):
        s = species[t]; r = species_record(s)
        model, mpath = species_model(s); tex = species_texture(s)
        whole = model
        model, cold = resident_model(s, r, model)           # COLD=1: the part the partner buffer holds, and the part read when needed
        if int(s.get('needs_ram_mb', 2)) > 2 and len(model) <= 0x18800:
            print(f'{s["_path"]}: note: the model ({len(model)} bytes) fits the 2 MB buffer, "needs_ram_mb" is not needed')
        if int(s.get('needs_ram_mb', 2)) > 2 and len(model) > BIG_MMD_MAX:
            raise SystemExit(f'{s["_path"]}: the model ({len(model)} bytes) does not fit the 8 MB buffer ({BIG_MMD_MAX})')
        if r['flags'] & FLAG_PARTNER and len(model) > PARTNER_MMD_MAX:
            raise SystemExit(f'{s["_path"]}: the model ({len(model)} bytes) does not fit the partner model buffer '
                             f'({PARTNER_MMD_MAX} bytes: PARTNER_MMD_MAX in include/dw/memmap.h; PARTNER_MMD_MAX=... overrides it here)')
        if r['flags'] & FLAG_PARTNER and shard_need(whole, r['bones']) > SHARD_SCRATCH:
            shard_bad.append(f'{s["_path"]}: evolving away needs {shard_need(whole, r["bones"])} bytes of shard scratch, '
                             f'more than EVL_SHARD_SCRATCH_SIZE ({SHARD_SCRATCH}, include/dw/evl.h)')
        r['modelSector'], r['modelSize'] = sector, len(model)
        sector += -(-len(model) // SECTOR) + -(-len(cold) // SECTOR)       # the cold part follows the resident one, on a sector
        r['texSector'] = sector
        sector += TEX_SIZE // SECTOR
        blobs.append(model + b'\0' * (-len(model) % SECTOR) + cold + b'\0' * (-len(cold) % SECTOR)); blobs.append(tex)
        recs[t] = r
        if not quiet: print(f'{t:3d} {s["name"]:20s} model {os.path.relpath(mpath, ROOT)} ({len(model)} B), '
                            f'texture, {"partner" if r["flags"] & FLAG_PARTNER else "not a partner"}')
    if shard_bad and SHARD_SCRATCH_WARN:   # an executable from before the bigger scratch: it skips those pieces
        print('warning: ' + '\nwarning: '.join(shard_bad) + '\n(this executable sheds no shards for the pieces past it)')
    elif shard_bad:
        raise SystemExit('\n'.join(shard_bad))
    # icons (tools/portraits.py), three to a sector after the blobs: the first is the fallback of a species without one
    icons = [None]
    chart = chart_tabs(allsp, species)
    from city_residents import city_cell, residents, verify_archive
    city = residents(allsp)
    # the originals of the chart past its sheet's 61 (no hand-drawn chart icon): an icon from their model, in their record
    drawn = sorted({t for t, s in species.items() if 'partner' in s} | {t for tab in chart for t in tab if CHART_SHEET < t < NUM_ORIGINAL}
                   | {r['id'] for r in city if r['id'] > CHART_SHEET})
    icon_of = {}
    if PORTRAITS:
        try:
            import portraits
            icons = [portraits.fallback_icon()]
            for t in drawn:
                s = species.get(t, allsp[t])
                try:
                    icons.append(portraits.species_icon(s))
                except Exception as ex:
                    print(f'warning: {s["name"]} ({t}): no icon ({ex})')
                    icons.append(None)
                if icons[-1] is not None:
                    icon_of[t] = icons[-1]
                    recs[t]['portrait'] =(sector + (len(icons) - 1) // portraits.ICONS_PER_SECTOR) | ((len(icons) - 1) % portraits.ICONS_PER_SECTOR) << 24
        except ImportError as ex:
            print(f'warning: no icons ({ex})')
            icons = [None]
    fallback_ref = 0
    if icons[0] is not None:
        fallback_ref = sector
        n_icons = len(icons)
        pb = bytearray(-(-n_icons // 3) * SECTOR)
        for k, ic in enumerate(icons):
            if ic is not None:
                o = (k // 3) * SECTOR + (k % 3) * len(ic)
                pb[o:o + len(ic)] = ic
        blobs.append(bytes(pb))
        sector += len(pb) // SECTOR
    chart_ref = 0
    if any(chart):
        cb = chart_block(chart, icon_of, icons[0])
        chart_ref = sector
        blobs.append(cb)
        sector += len(cb) // SECTOR
    # City uses the chart block layout with one tab. A cell packs the id, its level and the
    # spoiler bit (city_residents.city_cell); icon order still follows the plain ids.
    city_ref = sector
    if any(r['id'] > CHART_SHEET and r['id'] not in icon_of for r in city):
        raise SystemExit('City: every resident past the chart sheet needs a generated icon')
    cb = bytearray(chart_block([[r['id'] for r in city]], icon_of, icons[0]))
    for k, row in enumerate(city):
        struct.pack_into('<H', cb, 2 + k * 2, city_cell(row, allsp))
    blobs.append(bytes(cb))
    sector += len(cb) // SECTOR
    # links with the 62 original species that have evolution paths: the game applies them at boot, in this order
    extra = {}
    for t in sorted(species):
        r = recs[t]
        if not r['flags'] & FLAG_PARTNER: continue
        for key, other_key, n, flag in (('from', 'to', 6, 0), ('to', 'from', 5, LINK_FROM)):
            for o in r['evoPaths'][key]:
                if o <= 0 or o >= count: continue
                if o >= NUM_ORIGINAL or (o in species and o not in paths):   # an import or a record original 63..179
                    if recs[o] is None or not recs[o]['flags'] & FLAG_PARTNER:
                        print(f'warning: {r["para"]["name"]}: {o} is not a partner species'); continue
                    lst = recs[o]['evoPaths'][other_key]          # new <-> new: inside the records
                    if t not in lst and -1 in lst: lst[lst.index(-1)] = t
                    elif t not in lst: print(f'warning: {recs[o]["para"]["name"]} ({o}) has no free evolution slot for {r["para"]["name"]}')
                    continue
                if o not in paths:
                    # A record parent's forward route already lives in its own row.
                    # Disc children >= 63 have no reverse row to fill.
                    if key == 'to' and recs[o] and recs[o]['flags'] & FLAG_PARTNER:
                        continue
                    print(f'warning: {r["para"]["name"]}: {o} has no evolution paths in the game (types 1..62 and new species)'); continue
                lst = paths[o][other_key]
                if t in lst: continue
                if -1 not in lst and other_key == 'to' and O.rec[o]['para']['level'] == 2:
                    ex = extra.setdefault(o, [])                     # a Baby II's Rookies past its 6 slots (C: addExtraTarget)
                    if t in ex: continue
                    if len(extra) <= EXTRA_PARENTS and len(ex) < EXTRA_TARGETS:
                        ex.append(t); links.append((o, t | flag)); continue
                    print(f'warning: {r["para"]["name"]}: {O.rec[o]["para"]["name"]} ({o}) has no free extra Rookie slot'); continue
                if -1 not in lst:
                    print(f'warning: {r["para"]["name"]}: {O.rec[o]["para"]["name"]} ({o}) has no free evolution slot '
                          f'({n} {other_key} targets): it is not linked (EVOLUTION_TARGET can still force it)'); continue
                lst[lst.index(-1)] = t
                links.append((o, t | flag))
    partners = [t for t in range(count) if (t >= NUM_ORIGINAL or t in species) and recs[t] and recs[t]['flags'] & FLAG_PARTNER]
    if len(partners) > MAX_PARTNERS: raise SystemExit(f'{len(partners)} partner species: at most {MAX_PARTNERS}')
    if len(links) > MAX_LINKS: raise SystemExit(f'{len(links)} evolution links with the original species: at most {MAX_LINKS}')
    first_mega = next((t for t in partners if recs[t]['para']['level'] == 6), 0)
    hdr = bytearray(SECTOR)
    struct.pack_into(HEADER, hdr, 0, b'DIGI', VERSION, RECORD_SIZE, count, 0, first_records, sector, 1, fallback_ref, chart_ref)
    struct.pack_into('<I', hdr, HEADER_CITY, city_ref)
    for i, t in enumerate(partners): hdr[HEADER_LEVELS + i] = recs[t]['para']['level']
    for t in species:                                     # the record originals (include/dw/species.h)
        if t < NUM_ORIGINAL: hdr[HEADER_RECORD_ORIGINALS + t // 8] |= 1 << (t % 8)
    for t, x in allsp.items():                            # the original game's partners (OPTIONS' NEW DIGIMON)
        if x.get('vanilla'): hdr[HEADER_VANILLA + t // 8] |= 1 << (t % 8)
    plist = bytearray(SECTOR); struct.pack_into('<HH', plist, 0, len(partners), first_mega)
    for i, t in enumerate(partners): struct.pack_into('<H', plist, 4 + 2 * i, t)
    llist = bytearray(SECTOR); struct.pack_into('<HH', llist, 0, len(links), 0)
    for i, (o, t) in enumerate(links): struct.pack_into('<HH', llist, 4 + 4 * i, o, t)
    body = b''.join(pack_record(r) if r else bytes(RECORD_SIZE) for r in recs)
    body += b'\0' * (rec_sectors * SECTOR - len(body))
    data = bytes(hdr) + bytes(plist) + bytes(llist) + body + b''.join(blobs)
    assert len(data) == sector * SECTOR
    verify_archive(data)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'wb').write(data)
    if not quiet: print(f'{os.path.relpath(out, ROOT)}: {count} ids ({len(species)} carried species, {len(partners)} partners, '
                        f'{len(links)} links with the originals), {len(data)} bytes')
    return out


def max_partner_model(content=None, select=None):
    """Bytes of the biggest partner species model of the content folder (0 if none)."""
    big = 0
    for t, s in for_ram(carried(content)).items():
        if 'partner' in s and (select is None or t in select):
            model = species_model(s)[0]
            big = max(big, len(resident_model(s, species_record(s), model)[0]))
    return big


def read_archive(path=OUT):
    d = open(path, 'rb').read()
    magic, ver, rsize, count, first, rsec, total, isec, _, _ = struct.unpack_from(HEADER, d, 0)
    assert magic == b'DIGI' and ver == VERSION and rsize == RECORD_SIZE and first == 0, f'not a DIGI.DAT v{VERSION}'
    return d, count, [unpack_record(d[rsec * SECTOR + t * RECORD_SIZE:rsec * SECTOR + (t + 1) * RECORD_SIZE], t)
                      for t in range(count)]


def record_originals(d):
    """The original ids an archive carries by their record (the header bitmap)."""
    return {t for t in range(NUM_ORIGINAL) if d[HEADER_RECORD_ORIGINALS + t // 8] >> (t % 8) & 1}


def read_index(d):
    """(partner ids, first Mega, [(original, new, from?)]) of an archive."""
    isec = struct.unpack_from(HEADER, d, 0)[7]
    n, mega = struct.unpack_from('<HH', d, isec * SECTOR)
    partners = list(struct.unpack_from(f'<{n}H', d, isec * SECTOR + 4))
    k, _ = struct.unpack_from('<HH', d, (isec + 1) * SECTOR)
    links = [(o, t & ~LINK_FROM, bool(t & LINK_FROM)) for o, t in
             (struct.unpack_from('<HH', d, (isec + 1) * SECTOR + 4 + 4 * i) for i in range(k))]
    return partners, mega, links


# ------------------------------------------------------------------ selection (which imports a disc carries)
def parse_selection(sel, content=None):
    """Species ids >= 180 of a selection: ids, "all" (every import of the content), folders (every file in them),
    comma or space separated. Returns (ids, extra folders)."""
    ids, folders = {t for t, s in load_content(content).items() if '_npc_original' in s}, []
    for tok in re.split(r'[,\s]+', (sel or '').strip()):
        if not tok: continue
        if tok == 'all': ids |= set(carried(content))
        elif tok.isdigit(): ids.add(int(tok))
        elif os.path.isdir(tok):
            folders.append(tok)
            ids |= {t for t, s in load_content(tok).items() if t >= NUM_ORIGINAL or is_record_original(s)}
        else: raise SystemExit(f'species selection: "{tok}" is not an id, "all" or a folder')
    return ids, folders


def cmd_select(a):
    print('species', select(a.sel, a.o, a.models, a.content))


def select(sel, out, models=None, content=None):
    """A build's content folder OUT: the 180 originals and the selected imports (SEL as parse_selection), model and
    texture paths under build/models, build/dcb, build/dw2 pointed to MODELS. Returns the ids >= 180 and the record
    originals it carries, sorted."""
    ids, folders = parse_selection(sel, content)
    allsp = {}
    for folder in folders:                       # a selected folder's file wins over content/species' of that id
        for t, s in load_content(folder).items():
            if t in allsp: raise SystemExit(f'{s["_path"]}: id {t} is also defined in {allsp[t]["_path"]}')
            allsp[t] = s
    for t, s in load_content(content).items():
        if (t < NUM_ORIGINAL or t in ids) and t not in allsp: allsp[t] = s
    allsp = {t: s for t, s in allsp.items() if t < NUM_ORIGINAL or t in ids}
    missing = sorted(ids - set(allsp))
    if missing: raise SystemExit(f'species selection: no file for {", ".join(map(str, missing))}')
    absent_records = {t for t, s in allsp.items() if is_record_original(s) and t not in ids}
    os.makedirs(out, exist_ok=True)
    for f in glob.glob(os.path.join(out, '*.json')): os.remove(f)
    for t, s in sorted(allsp.items()):
        if is_record_original(s) and t not in ids:
            s = disc_file(t)                     # not carried: the disc's species
            del s['_path']
        s = json.loads(json.dumps(s), object_pairs_hook=collections.OrderedDict)
        ev = s.get('evolution')
        if ev:                                   # a link to an import this disc does not carry is left out
            for k in ('from', 'to'):
                if k in ev:
                    ev[k] = [o for o in ev[k] if o not in absent_records and (o < NUM_ORIGINAL or o in ids)]
                    if 1 <= t <= 62 and not is_record_original(s):
                        n = 5 if k == 'from' else 6
                        ev[k] = (ev[k] + [-1] * n)[:n]
        for k in ('model', 'texture'):
            for kk in ('file', 'partner_file'):
                f = (s.get(k) or {}).get(kk)
                if models and f and f.startswith(('build/dcb/', 'build/dw2/', 'build/models/')):
                    s[k][kk] = os.path.relpath(os.path.join(models, os.path.basename(f)), ROOT)
        write_file(os.path.join(out, file_name(s)), s)
    return sorted(t for t in allsp if t >= NUM_ORIGINAL or t in ids)


def disc_files(content=None):
    """[(option, disc path, file)] of the replaced (--file) and partner-only (--add) models of the disc's species:
    build-disc.py's arguments; the file as the species file names it (relative to the repository or absolute)."""
    out = []
    for t, s in sorted(load_content(content).items()):
        if t >= NUM_ORIGINAL: break
        m = s['model']
        if is_record_original(s): continue       # its model is in DIGI.DAT
        if 'file' in m:
            out.append(('--file', f'CHDAT/MMD{t // 30}/{m["name"]}.MMD', m['file']))
        if 'partner_file' in m:
            out.append(('--add', os.path.basename(m['partner_file']), m['partner_file']))
    return out


def cmd_disc_files(a):
    """build-disc.py arguments for the replaced and partner-only models of the disc's species."""
    for opt, disc, f in disc_files(a.content):
        print(f'{opt}\t{disc}={resolve_path(f)}')


# ------------------------------------------------------------------ for other tools
def table_row(t, s):
    """One species as a row shaped like the retired digimon.csv (strings)."""
    p = table_rows(s)['para']
    return {'id': str(t), 'name': s['name'], 'bone_count': str(p['boneCount']), 'radius': str(p['radius']),
            'height': str(p['height']), 'type': str(p['type']), 'level': str(p['level']),
            'special': ' '.join(str(x) for x in p['special'] if x != 0xFF),
            'drop_item': str(p['dropItem']), 'drop_chance': str(p['dropChance']),
            'moves': ' '.join(str(x) for x in p['moves'] if x != 0xFF and not (all(m == 0 for m in p['moves']))), 'raw': ''}


def all_rows(content=None):
    """{id: row} of every species (0..179 and the imports), rows shaped like the retired digimon.csv (id, name, bone_count, radius, height, type, level, ...)."""
    try:
        species = load_content(content)
    except SystemExit:
        return {}
    return {t: table_row(t, s) for t, s in species.items() if '_npc_original' not in s}


def extra_rows(content=None):
    """The imported species (ids >= 180) as rows shaped like the retired digimon.csv (id, name, bone_count, radius, height, type, level, ...) (tools/dws/backend.py)."""
    return {t: r for t, r in all_rows(content).items() if t >= NUM_ORIGINAL}


def wild_stats(t, content=None):
    """Default battle stats of a new species placed on a map ("wild" in its definition)."""
    s = load_content(content).get(t)
    return dict(s.get('wild', {})) if s else {}


def model_size(t, content=None):
    """Bytes of the MMD of a new species (0 if unknown)."""
    if t < NUM_ORIGINAL: return 0
    s = load_content(content).get(t)
    if not s: return 0
    try:
        return len(species_model(s)[0])
    except SystemExit:
        return 0


# ------------------------------------------------------------------ extract / sync / verify / diff
def exe_files(exe_dir=None, disc=False):
    """{t: rows} of the 180 species of an executable folder: a linked build (effective values) or, with disc (the
    developer tool `disc-tables`), a disc's extracted/ (the original values; the build reads them from
    content/tables/disc-species.json). Fields the tables do not hold come from `keep` in sync."""
    import balance as B
    if not disc and (exe_dir is None or os.path.abspath(exe_dir) == EXTRACTED):     # rule: the disc's values are the committed table
        O = originals()
        return {t: json.loads(json.dumps(O.rows[t])) for t in range(NUM_ORIGINAL)}, None
    exe = B.Exe(exe_dir)
    doc = B.decode(exe)
    if not exe.compiled:
        stats, techs = original_code_rows(exe.path('SLUS_010.32'))
        for t, v in stats.items(): doc['species'][str(t)]['reincarnation'] = v
        for t, v in techs.items(): doc['species'][str(t)]['newGameTechnique'] = v
    out = {}
    for t in range(NUM_ORIGINAL):
        rows = doc['species'][str(t)]
        evo = {k: rows.get(k) for k in ('evoReqs', 'evoGains', 'evoPaths')}
        rows = {k: rows.get(k) for k in TABLE_KEYS}
        rows.update(evo)                                   # the evolution rows (file_from_rows writes `evolution`)
        out[t] = rows
    return out, exe


def files_from_exe(exe_dir=None, keep=None):
    rows, _ = exe_files(exe_dir)
    O = originals()
    return {t: file_from_rows(t, rows[t], (keep or {}).get(t), O.rec[t]['modelName']) for t in rows}


def cmd_extract(a):
    files = files_from_exe(a.exe_dir)
    os.makedirs(out, exist_ok=True)
    for f in glob.glob(os.path.join(out, '*.json')): os.remove(f)
    for t, s in files.items():
        write_file(os.path.join(a.o, file_name(s)), s)
    print(f'{os.path.relpath(a.o, ROOT)}: {len(files)} species files from {os.path.relpath(a.exe_dir or EXTRACTED, ROOT)}')


def content_originals(content=None):
    out = {}
    for p in content_files(content or CONTENT_DEFAULT):
        m = re.match(r'(\d+)-', os.path.basename(p))
        if m and int(m.group(1)) < NUM_ORIGINAL:
            out[int(m.group(1))] = (p, json.load(open(p), object_pairs_hook=collections.OrderedDict))
    return out


def cmd_sync(a):
    have = content_originals(a.content)
    keep = {t: s for t, (p, s) in have.items()}
    files = files_from_exe(a.exe_dir or INT_EXE_DIR, keep)
    differ = [t for t, s in files.items() if t in have and dumps(s) != dumps(have[t][1]) and not is_record_original(have[t][1])]
    if differ and not a.ids and not a.all:
        sys.exit(f'species {" ".join(map(str, differ))} differ from the C: sync rewrites a file with the C values, so an '
                 f'edit of the file (species.py verify lists them) would be lost. Name the species the C change '
                 f'touched (species.py sync ID ...), or --all to take the C for every one')
    changed = 0
    for t, s in files.items():
        if a.ids and t not in a.ids: continue
        if t in have and is_record_original(have[t][1]):
            continue                             # a record original: its file is the record's, the C rows the disc's
        path = have[t][0] if t in have else os.path.join(a.content or CONTENT_DEFAULT, file_name(s))
        new = dumps(s)
        if not os.path.exists(path) or open(path).read() != new:
            open(path, 'w').write(new); changed += 1
            print(f'{os.path.relpath(path, ROOT)}: {"written" if t in have else "new"}')
    import balance
    balance.write_species_baseline(balance.Exe(a.exe_dir or INT_EXE_DIR))
    print(f'{changed} files changed (from {os.path.relpath(a.exe_dir or INT_EXE_DIR, ROOT)}); '
          f'{os.path.relpath(balance.SPECIES_BASELINE, ROOT)} records its tables')


def flat(d, path=''):
    if isinstance(d, dict):
        for k, v in d.items():
            if not str(k).startswith('_'): yield from flat(v, f'{path}.{k}' if path else k)
    else:
        yield path, d


def cmd_diff(a):
    mine = {t: s for t, s in load_content(a.content).items() if t < NUM_ORIGINAL}
    other = {t: json.load(open(p)) for t, p in ((int(re.match(r'\d+', os.path.basename(p)).group()), p)
                                               for p in content_files(a.dir)) if t < NUM_ORIGINAL}
    n = 0; species = []
    for t in sorted(set(mine) | set(other)):
        x, y = dict(flat(other.get(t, {}))), dict(flat(mine.get(t, {})))
        keys = [k for k in sorted(set(x) | set(y), key=lambda k: (k.split('.')[0] not in KEY_ORDER, k)) if x.get(k, '-') != y.get(k, '-')]
        if not keys: continue
        species.append(t)
        name = (mine.get(t) or other.get(t))['name']
        print(f'{t} {name}:')
        for k in keys:
            print(f'  {k}: {json.dumps(x.get(k, "-"))} -> {json.dumps(y.get(k, "-"))}'); n += 1
    print(f'{n} fields of {len(species)} species differ from {os.path.relpath(a.dir, ROOT)}: {" ".join(map(str, species))}')


def cmd_verify(a):
    import balance as B
    exe = B.Exe(a.exe_dir or INT_EXE_DIR)
    sys.exit(B.verify_species(exe))


def cmd_materialize(a):
    paths = []
    for x in a.paths:
        paths += sorted(glob.glob(os.path.join(x, '*.json'))) if os.path.isdir(x) else [x]
    n = 0
    for p in paths:
        old = json.load(open(p), object_pairs_hook=collections.OrderedDict); old['_path'] = p
        if 'base' not in old: continue
        write_file(p, materialize(old)); n += 1
    print(f'{n} files materialized')


# ------------------------------------------------------------------ lint: what the game can handle
FOOD_FIRST, FOOD_LAST = 38, 70          # items 38 Meat .. 70 Chain melon: what can be eaten (item.c, feeding)
FINISHER_FIRST, FINISHER_LAST = 58, 112  # the finisher is the last technique id in this range (initializePartner)
BABY_FIRST, BABY_LAST = 113, 120         # the Fresh / In-Training bubbles
MAX_AURA_TYPE = 128                      # the aura projectile tables have 129 rows (btl/std/vs effects)
MAX_EFFECTS_LIKE = 0xB0                  # getOriginalType (map.c) returns -1 above it
NUM_VBALL, NUM_VLALL, NUM_REGIONS = 71, 16, 9


# Animation slots the game starts on a partner's entity (startAnimation(entity, slot): anim.c:201 returns when the
# table entry is 0 and reads past the table when the slot is beyond it). 'waits': code that waits for the clip to end
# (animFrame >= frameCount, or the animFlag bit): with an empty slot the old clip goes on and the wait may never end
# (a care or battle sequence that hangs), so an empty slot is an error; otherwise the partner just does not animate
# (warning). Beyond the table is always an error. The technique slots 0x2E+i are checked per technique.
# (slots, what, where in decomp/src, waits)
PARTNER_SLOTS = [
    ((0x00,), 'idle (every entity starts on it; setPartnerIdle)', 'main/model.c:2863, partner.c:338,376,454,506,725', True),
    ((0x01,), 'idle when sick, hungry, tired or unhappy; after evolving and reincarnating',
     'main/partner.c:1071, evl/evl.c:329, dooa/dooa.c:290,352,1687', False),
    ((0x02,), 'walk', 'main/partner.c:274,364,429,567,639,744, trn/*.c', False),
    ((0x03,), 'slow walk while sick or unhappy', 'main/partner.c:998', False),
    ((0x04,), 'happy / waiting stroll (toilet, wild poop, gym, inventory)', 'main/partner.c:544,589,848, trn/*.c', False),
    ((0x08,), 'eating (the feeding sequence waits for the end)', 'main/partner.c:462,703', True),
    ((0x09, 0x0B), 'going to sleep (0x0B lying down, 0x09 asleep: partnerTickSleep waits for each); 0x0B also the praise, the joy after a '
     'favourite food and the end of the evolution and the new egg', 'main/partner.c:295-302, tamer.c:1586, partner_impl.c:1611, evl/evl.c:524, dooa/dooa.c:1112', True),
    ((0x0A,), 'poop: the toilet and the wild poop wait for the end', 'main/partner.c:558,600', True),
    ((0x0C,), 'after pooping; scolded; evolution flash; the new egg', 'main/partner.c:611, tamer.c:1597, evl/evl.c:368, dooa/dooa.c:395', True),
    ((0x0D,), 'refuses the item (waits for the end)', 'main/partner.c:466', True),
    ((0x12,), 'gym: after the training (tired / happy)', 'trn/trn_off.c:163,229, trn_def.c, trn_speed.c, trn_mp.c', False),
    ((0x13,), 'battle: senile (confused loop)', 'btl/battle_main.c:1087', False),
    ((0x16,), 'gym: brain training', 'trn/trn_brain.c:97,103,130', False),
    ((0x19,), 'scolded after an item (the scold flag)', 'main/tamer.c:1594', False),
    ((0x1B,), 'gym: HP training run', 'trn/trn_hp.c:87', False),
    ((0x21, 0x22), 'battle idle (0x21 healthy, 0x22 low HP)', 'main/btl.c:186-194, btl/battle_main.c:1020', False),
    ((0x23, 0x24), 'battle walk / hit when knocked down (healthy / low HP)', 'btl/battle_main.c:1690-1706, main/btl.c:382', False),
    ((0x25,), 'battle and gym: blocking', 'btl/battle_main.c:2220, trn/trn_def.c:111', False),
    ((0x28, 0x29), 'battle: hit, flattened, knocked back', 'btl/battle_main.c:2458-2461,3119', False),
    ((0x2A,), 'battle: victory pose (the end of the fight waits for it)', 'btl/battle_main.c:906-912', True),
    ((0x2B,), 'battle: faint (the revive / game over countdown starts when it ends)', 'btl/battle_main.c:1655, btl/battle_setup.c:365-380', True),
    ((0x2C,), 'getting up after fainting (the item revive waits for it); the new egg', 'btl/battle_setup.c:342, main/item.c:2315, dooa/dooa.c:354', True),
]
# slots a script (partnerStartAnimation: script_interp.c:809,823) or the rest of the code may start; every partner has them
# (import_batch.REQUIRED_SLOTS): the others of 0x00..0x2C belong to the Tamer, the NPCs and the kart race
SCRIPT_SLOTS = [s_ for s_ in range(0x2D) if s_ not in (0x06, 0x14, 0x1A, 0x1C, 0x1D, 0x1E, 0x1F, 0x20, 0x26, 0x27)]
_EFE_ROWS = {}


def efe_rows():
    """{technique chunk: {original type: [rows]}} of EFEDAT.EFE (tools/efe-origins.py finds the tables by shape; a short
    table can be missed), or {} without the extracted disc."""
    if not _EFE_ROWS:
        path = os.path.join(ROOT, 'extracted', 'ETCHI', 'EFEDAT.EFE')
        if not os.path.exists(path): return _EFE_ROWS
        import importlib.util
        sp_ = importlib.util.spec_from_file_location('efe_origins', os.path.join(ROOT, 'tools', 'efe-origins.py'))
        mod = importlib.util.module_from_spec(sp_); sp_.loader.exec_module(mod)
        data = open(path, 'rb').read()
        for c in range(len(data) // 0x5000):
            for _, rs in mod.tables(data[c * 0x5000:(c + 1) * 0x5000]):
                for r in rs: _EFE_ROWS.setdefault(c, {}).setdefault(r[0], []).append(r)
    return _EFE_ROWS


def _donor_types():
    """Species whose technique effects the C hook borrows (content/tables/effect-donors.json, written to efe.c's
    MOD_DONOR_ENTRIES by balance.py): a missing row is meant."""
    p = os.path.join(ROOT, 'content', 'tables', 'effect-donors.json')
    return {d['species'] for d in json.load(open(p))['effectDonors']} if os.path.exists(p) else set()
EFE_DONOR_TYPES = _donor_types()
_EFE_TABLES = {}


def efe_tables():
    """{technique chunk: [table rows, ...]} of EFEDAT.EFE, each table as checkTechCompatibility walks it ({} without the
    extracted disc)."""
    if not _EFE_TABLES:
        path = os.path.join(ROOT, 'extracted', 'ETCHI', 'EFEDAT.EFE')
        if not os.path.exists(path): return _EFE_TABLES
        import importlib.util
        sp_ = importlib.util.spec_from_file_location('efe_origins', os.path.join(ROOT, 'tools', 'efe-origins.py'))
        mod = importlib.util.module_from_spec(sp_); sp_.loader.exec_module(mod)
        data = open(path, 'rb').read()
        for c in range(len(data) // 0x5000):
            _EFE_TABLES[c] = [rs for _, rs in mod.tables(data[c * 0x5000:(c + 1) * 0x5000])]
    return _EFE_TABLES


def has_effect_record(s):
    """The species is carried by its DIGI.DAT record (a new species or a record original): its techniques without an
    origin row still get one (efe.c, "effect origins"); a species of the executable's tables does not."""
    return s['id'] >= NUM_ORIGINAL or is_record_original(s)


def effect_default(s):
    """(origin [bone, x, y, z], how) where a technique whose table has no row for the species' effects type and whose
    rows are mostly on bones (a breath, a shot) starts (the record's effectDefault). "effect_origin_fallback" in the file
    gives it; otherwise its own launch point: of the rows its effects type has on bones (any technique), the place they
    most often start from, moved onto its skeleton by its effect_origins as the game moves them (getSpeciesEffectOrigin);
    without such rows a point in front of its chest (bone 0)."""
    fb = s.get('effect_origin_fallback')
    if fb is not None: return [int(v) for v in fb], 'effect_origin_fallback'
    t = s['id']; et = s.get('effects_like', t); et = t if et is None or et < 0 else et
    counts = collections.Counter()
    for m in range(FINISHER_LAST + 1):
        for r in efe_rows().get(m, {}).get(et, []):
            if r[1] != 0 and abs(r[2]) < 3000: counts[tuple(r[1:])] += 1
    eo = [[ANY_OFFSET if v == 'any' else int(v) for v in e] for e in s.get('effect_origins', [])]
    nb = len(s['model']['skeleton']) if 'skeleton' in s['model'] else int(s['model'].get('bones', 0))
    moved = collections.Counter()
    for row, n in counts.items():
        to = next((e[4:] for e in eo if e[0] == row[0] and (e[1] == ANY_OFFSET or tuple(e[1:4]) == row[1:])), None)
        if to is not None: moved[tuple(to)] += n
        elif row[0] < nb: moved[row] += n                # the game uses the row as it is, on this skeleton's bone
    if moved:
        best = max(moved.items(), key=lambda kv: (kv[1], -kv[0][0]))[0]
        return list(best), f'the most used origin of effects type {et}'
    m_ = s['model']; h = int(m_.get('height', 300)); rad = int(m_.get('radius', 150))
    return [0, 0, -h * 6 // 10, -rad], 'in front of its chest (no bone rows to follow)'


def technique_origin(s, m, radius=None):
    """How technique m's effect finds its origin for species s, as the game does (BTL/STD/VS checkTechCompatibility,
    efe.c getModDonorTechBoneOffset): 'row' (its effects type has a row, or the chunk has no table found by shape: nothing
    is checked), 'donor' (an NPC partner's C donor), 'entity' (a record species: the entity point
    of the row of the species closest in radius, the table being mostly entity points), 'default' (a record species:
    effect_default), or None (dropped: the clip plays, nothing hits)."""
    t = s['id']; et = s.get('effects_like', t); et = t if et is None or et < 0 else et
    rows = efe_rows()
    if m not in rows: return 'row'                                   # no table found: nothing to check
    if et in rows[m]: return 'row'
    if t in EFE_DONOR_TYPES: return 'donor'
    if not has_effect_record(s): return None
    O = originals(); rad = radius if radius is not None else int(s['model'].get('radius', 150))
    main = max(efe_tables().get(m, [[]]), key=len)
    on_entity = [r for r in main if r[1] == 0 and r[0] < NUM_ORIGINAL]
    if on_entity and len(on_entity) >= len(main) - len(on_entity):
        return 'entity'
    return 'default'
_VBALL_KEYS = {}


def vball_keys(chunk):
    """The sound ids (keys) the tones of VBALL chunk `chunk` play, or None without the extracted disc."""
    if not _VBALL_KEYS:
        try:
            import sound
            f = sound.VhbFile(sound.resolve('VBALL'))
            for i, c in enumerate(f.chunks):
                ks = set()
                for p in range(len(c.vab.tones)):
                    for t in c.vab.tones_of(p): ks.update(range(t['min'], t['max'] + 1))
                _VBALL_KEYS[i] = ks
        except Exception:
            _VBALL_KEYS[-1] = None
    return _VBALL_KEYS.get(chunk) if _VBALL_KEYS.get(-1, 1) is not None else None


def audit_model(s, rows, E, W):
    """The model-side checks of a partner (lint --files): every animation slot the game starts on it exists (PARTNER_SLOTS,
    one per technique, the script slots), the animations only name bones the skeleton has, the gym clip is long enough for
    its hit tick, the sounds are in its voice bank, the techniques' effects have origin rows for its effects_like type."""
    para = rows['para']; mm_ = model_mmd(s, para['boneCount'])
    if mm_ is None: return
    tab = mm_.anims.table; anims = mm_.anims.anims
    slot = lambda x: f'model.animation[{x:#04x}]'
    def check(x, what, where, waits):
        if x >= len(tab):
            E(slot(x), x, f'{what}: the model has {len(tab)} animation slots, startAnimation would read past its table ({where})')
        elif tab[x] is None:
            if waits: E(slot(x), x, f'{what}: empty in the model, the old clip goes on and what waits for this one to end may hang ({where})')
            else: W(slot(x), x, f'{what}: empty in the model, the partner does not animate there ({where})')
    for slots, what, where, waits in PARTNER_SLOTS:
        for x in slots: check(x, what, 'decomp/src/' + where.split(',')[0].split(';')[0], waits)
    for x in SCRIPT_SLOTS:
        if x < len(tab) and tab[x] is None and not any(x in sl for sl, _, _, _ in PARTNER_SLOTS):
            W(slot(x), x, 'empty in the model: a script that starts it (partnerStartAnimation, script_interp.c:809,823) animates nothing')
    for i, mv in enumerate(para['moves']):
        if mv != 0xFF:
            check(0x2E + i, f'technique {i} ({names("techs").get(mv, mv)}): its attack', 'main/btl.c:186, btl/battle_main.c:1288,1316', True)
    nb = para['boneCount']
    bad = sorted({x for a in anims for ins in a.instrs if ins['op'] == 'key' for b in ins['bones'] for x in [b['bone']] if x >= nb})
    if bad: E('model.animations', bad, f'bones {bad} are not in the skeleton ({nb} bones): the animation writes past the bone arrays (anim.c)')
    for k, (a, tick) in (('partner.training', rows['trainingAnims']), ('partner.training2', rows['training2Anims'])):
        if a < len(tab) and tab[a] is not None and tick >= anims[tab[a]].frame_count:
            W(k + '.hit_tick', tick, f'the clip of slot {a} lasts {anims[tab[a]].frame_count} ticks: the hit lands after it ended')
    keys = vball_keys(s['voice'])
    if keys is not None:
        notes = sorted({ins['note'] for i, ai in enumerate(sorted({x for x in tab if x is not None})) for ins in anims[ai].instrs
                        if ins['op'] == 'sound' and ins['bank'] == 4 and ins['note'] not in keys})
        if notes:
            W('model.sounds', notes, f'animation sounds (bank 4) that voice {s["voice"]} (VBALL chunk) has no tone for: silent'
              + ('; as on the disc' if s['id'] < NUM_ORIGINAL else ''))
    if efe_rows():
        lacking = [mv for mv in para['moves'] if mv != 0xFF and technique_origin(s, mv) is None]
        if lacking:
            et = s.get('effects_like', s['id']); et = s['id'] if et is None or et < 0 else et
            E('techniques', [names('techs').get(m_, m_) for m_ in lacking],
              f'no effect origin for type {et} (effects_like) in these techniques\' effect and the species is not carried by '
              f'its DIGI.DAT record: checkTechCompatibility drops the effect, the technique never hits '
              f'(tools/efe-origins.py --species {s["id"]})')


def lint(species, check_files=False):
    """(errors, warnings) of a set of species files: values the game cannot handle (errors: the build stops) and
    values that work but are probably not meant (warnings). Each message: file, field, value, why."""
    errs, warns = [], []
    byname = {}
    for t, s in sorted(species.items()):
        w = os.path.relpath(s['_path'], ROOT) if os.path.isabs(s['_path']) else s['_path']
        E = lambda f, v, why: errs.append(f'{w}: {f} = {json.dumps(v)}: {why}')
        W = lambda f, v, why: warns.append(f'{w}: {f} = {json.dumps(v)}: {why}')
        try:
            rows = table_rows(s)
        except SystemExit as ex:
            errs.append(str(ex)); continue
        para = rows['para']; moves = [m for m in para['moves'] if m != 0xFF]
        level = para['level']; partner = s.get('partner')
        placeholder = partner is not None and level == 0 and partner.get('birth_weight') == 0   # 62 WereGarurumon's row
        fights = bool(s['techniques']) and any(m is not None for m in s['techniques'])
        # NPC twins are engine implementation records, never roster members.
        if '_npc_original' in s:
            original = s['_npc_original']
            if not isinstance(original, int) or not 0 <= original < NUM_ORIGINAL:
                E('_npc_original', original, 'a disc species 0..179')
            else:
                disc = disc_file(original)
                if s['voice'] != originals().rec[original]['vball']:
                    E('voice', s['voice'], 'must equal the disc NPC voice')
                if original in species and s['name'] != species[original]['name']:
                    E('name', s['name'], 'must equal its partner species name')
                if partner or moves or s.get('evolution'):
                    E('_npc_original', original, 'an NPC twin has no partner, techniques or evolution')
                if (set(s['model']) != {'from', 'radius', 'height', 'skeleton'} or
                        s['model'].get('from') != original or s.get('texture') != {'from': original}):
                    E('_npc_original', original, 'model and texture must read the unmodified disc species')
                for key in ('radius', 'height'):
                    if s['model'].get(key) != disc['model'][key]:
                        E('model.' + key, s['model'].get(key), 'must equal the disc NPC')
                if s['model'].get('skeleton') != originals().rec[original]['bones']:
                    E('model.skeleton', s['model'].get('skeleton'), 'must equal the disc skeleton')
        # names
        if len(s['name'].encode('ascii', 'replace')) > 19: E('name', s['name'], 'at most 19 characters (DigimonPara.name)')
        if '_npc_original' not in s:
            byname.setdefault(s['name'].lower(), []).append(t)
        # enums and ranges
        if not 0 <= level <= 6: E('level', s['level'], '0..6 (none .. mega)')
        if not 0 <= para['type'] <= 3: E('attribute', s['attribute'], 'none, data, vaccine or virus')
        elif para['type'] == 0 and (partner and not placeholder or fights):
            E('attribute', s['attribute'], 'a species that fights or is a partner needs data, vaccine or virus: the game '
              'indexes FLEE_CHANCES[(attribute - 1) * 3 + ...] (btl.c) and the status screen icon with attribute - 1')
        for i, e in enumerate(para['special']):
            if e != 0xFF and not 0 <= e < len(ELEMENTS): E(f'specialties[{i}]', e, 'an element (fire .. filth) or null')
        if (partner and not placeholder or fights) and para['special'][0] == 0xFF:
            W('specialties[0]', None, 'the main element is empty: learning on evolving and the AI use slot 0')
        for m in moves:
            if m not in names_of_techs(): E('techniques', m, f'technique {m} does not exist (0..{max(names_of_techs())})')
        if level in (1, 2) and partner and any(not BABY_FIRST <= m <= BABY_LAST for m in moves):
            E('techniques', s['techniques'], f'a Fresh/In-Training partner fights with a bubble ({BABY_FIRST}..{BABY_LAST}) only')
        if level >= 3 and any(BABY_FIRST <= m <= BABY_LAST for m in moves):
            W('techniques', s['techniques'], f'a bubble ({BABY_FIRST}..{BABY_LAST}) on a species of level {s["level"]}')
        if level >= 3 and partner and not placeholder and not any(FINISHER_FIRST <= m <= FINISHER_LAST for m in moves):
            W('techniques', s['techniques'], f'no finisher (an id {FINISHER_FIRST}..{FINISHER_LAST}): the partner has none in battle')
        if t >= NUM_ORIGINAL and partner and not moves: E('techniques', s['techniques'], 'an imported species needs a technique')
        if para['dropItem'] not in names('items'): E('drop.item', para['dropItem'], 'not an item (0..127)')
        if not 0 <= para['dropChance'] <= 100: E('drop.percent', para['dropChance'], '0..100')
        for k in ('radius', 'height'):
            if not 0 <= para[k] <= 2000 or (para[k] == 0 and (fights or partner and not placeholder)):
                E(f'model.{k}', para[k], '1..2000 world units (0 only for a species that neither fights nor is a partner)')
        if not 0 <= s['voice'] < NUM_VBALL: E('voice', s['voice'], f'a VBALL chunk 0..{NUM_VBALL - 1}')
        if rows['battleMusic'] is not None and not 0 <= rows['battleMusic'] < len(BATTLE_MUSIC):
            E('battle_music', s['battle_music'], ', '.join(BATTLE_MUSIC))
        ot = s.get('effects_like')
        if ot is not None:
            if not 0 <= ot <= MAX_EFFECTS_LIKE:
                E('effects_like', ot, f'a species 0..{MAX_EFFECTS_LIKE} (getOriginalType gives none above it)')
            elif ot > MAX_AURA_TYPE and (partner and not placeholder or fights):
                E('effects_like', ot, f'the aura rows (BTL/STD/VS_AURA_PROJECTILE_TYPES) have {MAX_AURA_TYPE + 1} entries: a fighter indexes '
                  f'them with its effects_like type, so name a species 0..{MAX_AURA_TYPE}')
            elif (partner or fights) and ot != t and ot in species and species[ot].get('effects_like', ot) not in (ot, -1):
                E('effects_like', ot, f'{species[ot]["name"]} borrows its effects itself (effects_like {species[ot]["effects_like"]}): name that one')
        fb = rows.get('effectFallback')
        if fb is not None:
            nb = len(s['model']['skeleton']) if 'skeleton' in s['model'] else para['boneCount']
            if not 0 <= fb[0] < max(nb, 1): E('effect_origin_fallback', fb, f'bone {fb[0]} is not one of its {nb} bones')
            if not has_effect_record(s):
                E('effect_origin_fallback', fb, 'only a species carried by its DIGI.DAT record (a new species, a record '
                  'original) has one: the record holds it')
        if s.get('reincarnation_stats'):
            if level != 1: E('reincarnation_stats', s['reincarnation_stats'], 'only a Fresh species hatches from the reincarnation egg')
            if any(not 1 <= v <= 9999 for v in rows['reincarnation']): E('reincarnation_stats', s['reincarnation_stats'], 'each 1..9999')
        # the partner block
        if partner and not placeholder:
            r = rows['raise']; P = lambda k: f'partner.{k}'
            anim_table = model_anim_table(s, para['boneCount']) if check_files else None
            if level == 0: E('level', s['level'], 'a partner needs a level (fresh .. mega)')
            if not 0 <= rows['vlall'] < NUM_VLALL: E(P('voice'), rows['vlall'], f'a VLALL chunk 0..{NUM_VLALL - 1}')
            hours = partner['hunger_hours']
            if level >= 3:
                if not hours: E(P('hunger_hours'), hours, 'a Rookie or above needs hunger hours (setFoodTimer)')
                if any(not 0 <= h <= 23 for h in hours): E(P('hunger_hours'), hours, 'hours of the day, 0..23')
                if hours != sorted(set(hours)): E(P('hunger_hours'), hours, 'in increasing order, each once (setFoodTimer takes the next one)')
            elif hours:
                W(P('hunger_hours'), hours, 'Fresh and In-Training eat every 2 / 3 hours: the list is not read')
            if not 1 <= r['energyCap'] <= 255: E(P('energy_max'), r['energyCap'], '1..255')
            if not 0 <= r['energyThreshold'] <= r['energyCap']: E(P('energy_fed'), r['energyThreshold'], f'0..energy_max ({r["energyCap"]})')
            if not 0 <= r['energyUsage'] <= 255: E(P('energy_per_hour'), r['energyUsage'], '0..255')
            if not 1 <= r['poopTimer'] <= 32767: E(P('poop_timer_10min'), r['poopTimer'], '1..32767')
            if not 0 <= r['poopSize'] <= 255: E(P('poop_size'), r['poopSize'], '0..255')
            ff = r['favoriteFood']
            if not (FOOD_FIRST <= ff <= FOOD_LAST or (ff == 0 and level in (1, 2))):
                E(P('favorite_food'), partner['favorite_food'], f'a food (items {FOOD_FIRST}..{FOOD_LAST}: {names("items").get(FOOD_FIRST)} .. '
                  f'{names("items").get(FOOD_LAST)}); sm.recovery (0, none) only for Fresh and In-Training')
            if not 0 <= r['sleepCycle'] < len(SLEEP_CYCLES): E(P('sleep_cycle'), partner['sleep_cycle'], ', '.join(SLEEP_CYCLES))
            elif level >= 3 and r['sleepCycle'] >= 6:
                W(P('sleep_cycle'), partner['sleep_cycle'], 'the Fresh / In-Training pattern on a Rookie or above')
            if not 0 <= r['trainingType'] < len(TRAINING_TYPES): E(P('training_type'), partner.get('training_type'), ', '.join(TRAINING_TYPES))
            if not 0 <= r['favoredRegion'] < NUM_REGIONS: E(P('favored_region'), r['favoredRegion'], f'a region 0..{NUM_REGIONS - 1} (the .MAP files name 0..8)')
            if not 1 <= r['defaultWeight'] <= 99: E(P('birth_weight'), r['defaultWeight'], '1..99 (the game clamps the weight to it)')
            if not 0 <= rows['itemTakeDistance'] <= 127: E(P('item_distance'), rows['itemTakeDistance'], '0..127')
            for k, tr in (('training', rows['trainingAnims']), ('training2', rows['training2Anims'])):
                a, tick = tr
                if not 0x2E <= a <= 0x3D: E(P(k + '.animation'), a, 'a technique slot animation, 46..61')
                elif check_files and anim_table is not None:
                    if a >= len(anim_table):
                        E(P(k + '.animation'), a, f'the model has {len(anim_table)} animation slots: startAnimation '
                          f'would read past its table (anim.c)')
                    elif anim_table[a] is None:
                        W(P(k + '.animation'), a, 'the model has no animation in that slot: the gym plays none')
                if not 1 <= tick <= 120: E(P(k + '.hit_tick'), tick, '1..120 ticks after the animation starts')
            if check_files and anim_table is not None: audit_model(s, rows, E, W)
        elif placeholder:
            W('partner', '...', 'a placeholder row (level none, birth weight 0): the game never makes it a partner')
        # imports and record originals
        if t >= NUM_ORIGINAL or is_record_original(s):
            m = s['model']; bones = m.get('skeleton', [])
            for i, (o, par) in enumerate(bones):
                if i and not (0 <= par < len(bones) and par != i): E('model.skeleton', [o, par], f'bone {i}: its parent must be another bone')
            if partner and len(bones) > MAX_PARTNER_BONES: E('model.skeleton', len(bones), f'a partner has at most {MAX_PARTNER_BONES} bones')
            if len(bones) > MAX_BONES: E('model.skeleton', len(bones), f'at most {MAX_BONES} bones')
            for k in ('from',):
                if k in m and not 0 <= m[k] < NUM_ORIGINAL: E('model.from', m[k], 'a species of the disc, 0..179')
            tex = s.get('texture', {})
            if 'from' in tex and not 0 <= tex['from'] < NUM_ORIGINAL: E('texture.from', tex['from'], 'a species of the disc, 0..179')
            for e in s.get('effect_origins', []):
                if not 0 <= e[4] < len(bones): E('effect_origins', e, f'bone {e[4]} is not one of its {len(bones)} bones')
            cb = s.get('condition_bubble')
            if cb and not 0 <= cb[3] < len(bones): E('condition_bubble', cb, f'bone {cb[3]} is not one of its {len(bones)} bones')
            ev = s.get('evolution') or {}
            has_disc = any(x < NUM_ORIGINAL for x in species)
            for k in ('from', 'to'):
                for o in ev.get(k, []):
                    if o == -1 and t < NUM_ORIGINAL and not is_record_original(s): continue   # an empty slot of a disc row
                    if o in species: is_partner, nm = 'partner' in species[o], species[o]['name']
                    elif 0 <= o < NUM_ORIGINAL and has_disc:     # the content has the disc's species: no file, no species;
                        continue                         # the build leaves it out (a disc row's slot becomes -1)
                    elif 0 <= o < NUM_ORIGINAL:          # a folder of imports only: the disc's species
                        is_partner, nm = bool(originals().rec[o]['flags'] & FLAG_PARTNER), originals().rec[o]['para']['name']
                    else:
                        E(f'evolution.{k}', o, 'no such species'); continue
                    if not is_partner: E(f'evolution.{k}', o, f'{nm} is not a partner')
            if check_files:
                for k, f in (('model.file', m.get('file')), ('texture.file', tex.get('file'))):
                    if f and not os.path.exists(resolve_path(f)): E(k, f, 'the file does not exist (build it first)')
        for k in ('file', 'partner_file'):
            f = s['model'].get(k)
            if t < NUM_ORIGINAL and not is_record_original(s) and check_files and f and not os.path.exists(resolve_path(f)):
                E(f'model.{k}', f, 'the file does not exist (build it first)')
    # names: an import must not share a name with another import; with an original it is ambiguous for name lookups
    for n, ids in byname.items():
        imp = [t for t in ids if t >= NUM_ORIGINAL]
        if len(imp) > 1:
            errs += [f'{os.path.relpath(species[t]["_path"], ROOT)}: name = "{species[t]["name"]}": also the name of '
                     f'{", ".join(str(x) for x in ids if x != t)}' for t in imp]
        elif imp and len(ids) > 1:
            warns.append(f'{os.path.relpath(species[imp[0]]["_path"], ROOT)}: name = "{species[imp[0]]["name"]}": also the '
                         f'name of the disc\'s {", ".join(str(x) for x in ids if x < NUM_ORIGINAL)} (DWS species("...") '
                         f'and other name lookups take the lowest id)')
    models = {}
    for t, s in species.items():
        f = s['model'].get('file')
        if t >= NUM_ORIGINAL and f: models.setdefault(f, []).append(t)
    for f, ids in models.items():
        if len(ids) > 1 and not all(species[t].get('_shared_model') for t in ids):
            warns.append(f'model.file = "{f}": used by {", ".join(map(str, ids))} (add "_shared_model": "why" to each when meant)')
    return errs, warns


def model_mmd(s, nbones):
    """The parsed model of a species as the game loads it for a partner, or None when it cannot be read."""
    try:
        import mmd
        m = s['model']
        if 'partner_file' in m: data = open(resolve_path(m['partner_file']), 'rb').read()   # what it loads as a partner
        elif s['id'] >= NUM_ORIGINAL or 'file' in m: data = species_model(s)[0]
        else: data = open(originals().model_path(s['id']), 'rb').read()
        return mmd.MMD.parse(data, nbones)
    except Exception:
        return None


def model_anim_table(s, nbones):
    """The animation slots of a species' model (index: slot; None: empty), or None when the model cannot be read."""
    m = model_mmd(s, nbones)
    return None if m is None else m.anims.table


def names_of_techs():
    return set(names('techs')) | set(range(0, 122))


def lint_content(content=None, check_files=False):
    """lint() of the content folders; a file that does not load (an unknown key, a wrong name, a duplicate id) is
    an error of its own and the others are still checked."""
    species, errs = {}, []
    for p in content_files(content):
        try:
            s = load_file(p)
        except (SystemExit, ValueError) as ex:
            errs.append(str(ex) if str(ex).startswith(p) or os.path.basename(p) in str(ex) else f'{p}: {ex}'); continue
        if s['id'] in species:
            errs.append(f'{p}: id = {s["id"]}: also the id of {species[s["id"]]["_path"]}'); continue
        species[s['id']] = s
    e, w = lint(species, check_files)
    rel = lambda x: x.replace(ROOT + os.sep, '')
    return species, [rel(x) for x in errs + e], [rel(x) for x in w]


def cmd_lint(a):
    species, errs, warns = lint_content(a.content, a.files)
    for x in warns if not a.quiet else []: print('warning:', x)
    for x in errs: print('error:', x)
    print(f'{len(species)} species: {len(errs)} errors, {len(warns)} warnings')
    sys.exit(1 if errs else 0)


def cmd_fmt(a):
    paths = a.paths or content_files(a.content)
    bad = []
    for p in paths:
        text = open(p).read()
        new = dumps(json.loads(text, object_pairs_hook=collections.OrderedDict))
        if new != text:
            bad.append(p)
            if not a.check: open(p, 'w').write(new)
    if a.check and bad: sys.exit('not in the canonical layout: ' + ' '.join(os.path.relpath(p, ROOT) for p in bad))
    print(f'{len(paths)} files, {len(bad)} {"to rewrite" if a.check else "rewritten"}')


# ------------------------------------------------------------------ commands
def num(s):
    return int(s, 0)


def cmd_add(a):
    """A new species: the old-style description (a copy of TYPE with changes), materialized into a complete file."""
    O = originals()
    if not NUM_ORIGINAL <= a.id < NUM_DIGIMON: sys.exit(f'id must be {NUM_ORIGINAL}..{NUM_DIGIMON - 1}')
    s = {'id': a.id, 'name': a.name, 'base': a.base}
    if a.model: s['model'] = {'file': os.path.relpath(os.path.abspath(a.model), ROOT)}
    if a.texture:
        f, _, e = a.texture.partition(':')
        s['texture'] = {'file': os.path.relpath(os.path.abspath(f), ROOT), 'entry': int(e, 0) if e else 0}
    else:
        s['texture'] = {'from': a.base}
    if a.hue: s['texture']['hue'] = a.hue
    if a.swap: s['texture']['swap'] = a.swap
    para = {}
    if a.moves: para['moves'] = (a.moves + [0xFF] * 16)[:16]
    partner = None
    if a.partner is not None:
        partner = {'base': a.partner if a.partner >= 0 else a.base}
        if a.evolves_from: partner['from'] = a.evolves_from
    for kv in a.set or []:
        k, v = kv.split('=', 1)
        val = [num(x) for x in v.split(',')] if ',' in v else (v if k == 'name' else num(v))
        if k in ('radius', 'height', 'type', 'level', 'special', 'dropItem', 'dropChance', 'boneCount'):
            para[k] = val if k != 'special' or isinstance(val, list) else [val, 0xFF, 0xFF]
        elif k in ('originalType', 'vball', 'vlall'):
            s[k] = val
        elif k.split('.')[0] in ('raise', 'evoReqs', 'evoGains') or k in ('itemTakeDistance',):
            if partner is None: sys.exit(f'{k}: only for a partner (--partner)')
            if '.' in k:
                g, f = k.split('.', 1); partner.setdefault(g, {})[f] = val
            else:
                partner[k] = val
        elif k.startswith('wild.') and k[5:] in ('hp', 'mp', 'off', 'def', 'speed', 'brain', 'bits'):
            s.setdefault('wild', {})[k[5:]] = val
        elif k == 'name':
            s['name'] = val
        else:
            sys.exit(f'unknown field {k}')
    if para: s['para'] = para
    if partner is not None: s['partner'] = partner
    out = a.o or os.path.join(CONTENT, f'{a.id}-{re.sub(r"[^a-z0-9]+", "-", a.name.lower()).strip("-")}.json')
    s['_path'] = out
    full = materialize(s, from_files=True)
    write_file(out, full)
    print(f'{os.path.relpath(out, ROOT)}: {a.name} ({a.id}), a copy of {O.rec[a.base]["para"]["name"]} ({a.base})')


def cmd_maxmodel(a):
    print(max_partner_model(a.content, parse_selection(a.species, a.content)[0] if a.species else None))


def cmd_build(a):
    build(a.o, a.content, select=parse_selection(a.species, a.content)[0] if a.species else None)


def cmd_list(a):
    for t, s in sorted(load_content(a.content).items()):
        if t < NUM_ORIGINAL and not a.all: continue
        r = species_record(s)
        size = len(species_model(s)[0]) if t >= NUM_ORIGINAL else 0
        print(f'{t:3d} {s["name"]:20s} {s["level"]:12s} effects like {r["originalType"]:3d}, model {size} B, '
              f'{"partner" if r["flags"] & FLAG_PARTNER else "NPC"}')


def cmd_show(a):
    s = load_content(a.content).get(a.id)
    if not s: sys.exit(f'no species {a.id}')
    text = dumps(s)
    nm = {t: x['name'] for t, x in load_content(a.content).items()}
    # the names of the species a number refers to, as comments (not in the files: decision A)
    text = re.sub(r'("effects_like": )(\d+)(,?)', lambda m: f'{m.group(1)}{m.group(2)}{m.group(3)}  // {nm.get(int(m.group(2)), "?")}', text)
    print(text, end='')


def cmd_check(a):
    d, count, recs = read_archive(a.path)
    from city_residents import verify_archive
    if struct.unpack_from('<I', d, HEADER_CITY)[0]:
        verify_archive(d)
    carried_orig = record_originals(d)
    want, src = original_records(a.content, count > NUM_ORIGINAL or bool(carried_orig))
    bad = 0
    for t in range(NUM_ORIGINAL):
        if t in carried_orig: continue                                    # a record original: checked below
        mine = unpack_record(pack_record(want[t]), t)
        if mine != recs[t]:
            bad += 1; print(f'record {t} differs from the {"species files" if src == "content" else "disc"}')
    import mmd
    for t in sorted(carried_orig) + list(range(NUM_ORIGINAL, count)):
        r = recs[t]
        if not r['flags'] & FLAG_DEFINED: continue                       # a gap in the ids
        model = d[r['modelSector'] * SECTOR:r['modelSector'] * SECTOR + r['modelSize']]
        tex = d[r['texSector'] * SECTOR:r['texSector'] * SECTOR + TEX_SIZE]
        import coldsplit
        nb = r['para']['boneCount']
        if coldsplit.is_split(model):                                       # COLD=1: the cold part is after the resident one
            n = coldsplit.cold_length(model)
            c0 = r['modelSector'] + -(-r['modelSize'] // SECTOR)
            cold = d[c0 * SECTOR:c0 * SECTOR + n]
            whole = coldsplit.join(model, cold, nb, coldsplit.table_length(model))
            m = mmd.MMD.parse(whole, nb)
            res2, cold2 = coldsplit.split(m.build(), nb)         # (the word padding at the end of the resident part may differ)
            if res2[:len(model)] != model or any(res2[len(model):]) or cold2 != cold: print(f'{t}: the cold split does not come back from the whole model'); bad += 1
        else:
            m = mmd.MMD.parse(model, nb)
            if m.build() != model: print(f'{t}: the model does not rebuild byte for byte'); bad += 1
        mmd.Tim4(tex)
        print(f'{t:3d} {r["para"]["name"]:20s} bones {r["para"]["boneCount"]}, model {r["modelSize"]} B at sector '
              f'{r["modelSector"]}, texture at {r["texSector"]}, originalType {r["originalType"]}, '
              f'{"partner" if r["flags"] & FLAG_PARTNER else "NPC"}')
    partners, mega, links = read_index(d)
    want_p = [t for t in range(count) if (t >= NUM_ORIGINAL or t in carried_orig) and recs[t]['flags'] & FLAG_PARTNER]
    if partners != want_p: print('the partner list differs from the records'); bad += 1
    print(f'{len(partners)} partner species, first Mega {mega or "none"}, {len(links)} evolution links with the originals')
    print(f'{a.path}: {count} ids, records 0..179 ' +
          (f'identical to the {"species files" if src == "content" else "disc"}' if not bad else f'{bad} differ'))
    sys.exit(1 if bad else 0)


def cmd_disc(a):
    path = build(OUT, a.content)
    cmd = [sys.executable, os.path.join(ROOT, 'tools/build-disc.py'), a.name, '--from', a.dirs or SPECIES_EXE_DIR,
           '--relayout', '--add', f'DIGI.DAT={path}'] + sum((['--file', f] for f in a.file or []), [])
    print(' '.join(cmd)); sys.exit(subprocess.call(cmd, cwd=ROOT))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--content', default=None, help='species folders (default content/species; SPECIES_CONTENT)')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('add'); p.add_argument('id', type=num); p.add_argument('name')
    p.add_argument('--base', type=num, required=True); p.add_argument('--model'); p.add_argument('--texture')
    p.add_argument('--hue', type=float); p.add_argument('--swap'); p.add_argument('--moves', type=num, nargs='+')
    p.add_argument('--set', action='append'); p.add_argument('--partner', type=num, nargs='?', const=-1)
    p.add_argument('--evolves-from', type=num, nargs='+'); p.add_argument('-o'); p.set_defaults(f=cmd_add)
    p = sub.add_parser('build'); p.add_argument('-o', default=OUT); p.add_argument('--species'); p.set_defaults(f=cmd_build)
    p = sub.add_parser('maxmodel'); p.add_argument('--species'); p.set_defaults(f=cmd_maxmodel)
    p = sub.add_parser('list'); p.add_argument('--all', action='store_true'); p.set_defaults(f=cmd_list)
    p = sub.add_parser('show'); p.add_argument('id', type=num); p.set_defaults(f=cmd_show)
    p = sub.add_parser('check'); p.add_argument('path', nargs='?', default=OUT); p.set_defaults(f=cmd_check)
    p = sub.add_parser('disc'); p.add_argument('name'); p.add_argument('--from', dest='dirs')
    p.add_argument('--file', action='append'); p.set_defaults(f=cmd_disc)
    p = sub.add_parser('disc-tables'); p.add_argument('--exe-dir'); p.set_defaults(f=cmd_disc_tables)
    p = sub.add_parser('extract'); p.add_argument('-o', default=ORIGINAL_DIR); p.add_argument('--exe-dir'); p.set_defaults(f=cmd_extract)
    p = sub.add_parser('sync'); p.add_argument('--exe-dir'); p.add_argument('--all', action='store_true')
    p.add_argument('ids', type=int, nargs='*'); p.set_defaults(f=cmd_sync)
    p = sub.add_parser('verify'); p.add_argument('--exe-dir'); p.set_defaults(f=cmd_verify)
    p = sub.add_parser('diff'); p.add_argument('dir', nargs='?', default=ORIGINAL_DIR); p.set_defaults(f=cmd_diff)
    p = sub.add_parser('materialize'); p.add_argument('paths', nargs='+'); p.set_defaults(f=cmd_materialize)
    p = sub.add_parser('fmt'); p.add_argument('--check', action='store_true'); p.add_argument('paths', nargs='*'); p.set_defaults(f=cmd_fmt)
    p = sub.add_parser('select'); p.add_argument('sel'); p.add_argument('-o', required=True); p.add_argument('--models')
    p.set_defaults(f=cmd_select)
    p = sub.add_parser('disc-files'); p.set_defaults(f=cmd_disc_files)
    p = sub.add_parser('lint'); p.add_argument('--files', action='store_true', help='also check that model/texture files exist')
    p.add_argument('--quiet', action='store_true', help='errors only'); p.set_defaults(f=cmd_lint)
    a = ap.parse_args(); a.f(a)


if __name__ == '__main__':
    main()
