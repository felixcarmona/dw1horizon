#!/usr/bin/env python3
"""Proof that the table-driven city rules (story-state engine) equal the original C rules (docs/mods/city-rules.md, "Equivalence").

    tools/dws/testing/city_equivalence.py            build the host harness and run it (the original functions of decomp/src against the shipped
                                   city_rules.c and the call sites of build/decomp-story-state/src), then the table checks
    tools/dws/testing/city_equivalence.py --quick    fewer cases

What it does, in order:
 1. extracts, verbatim, from the unmodified decompilation (decomp/src, branch main) the functions recalculatePPandArena,
    getFileCityTopMap, initializeDefaultSavegame, checkShopMap, checkArenaMap and the revival conditions of murd.c and dooa.c, and
    the same ones from the story-state tree (where they call the table readers);
 2. compiles both next to the real build/decomp-story-state/src/main/city_rules.c with gcc on the host (game functions stubbed:
    tools/dws/testing/city_oracle/) and runs the grids: every species alone x every level, random states, the 32 top-map states, the revival
    rule for every prosperity, every map id, the whole start save slot byte for byte;
 3. checks that the generated header (city_default.h) is what `dws city-compile` writes from story/base/city/city.dws, and that
    city.dws is what `dws city-extract` reads from the original C;
 4. random declarations: Python (tools/dws/city.py, the reference evaluator) against the C reader on tables the compiler wrote.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import os, re, subprocess, sys, tempfile, random, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from dws import city  # noqa: E402

ORIG = os.path.join(ROOT, 'decomp', 'src')
STORY_STATE_SOURCE = os.path.join(ROOT, 'build', 'decomp-story-state', 'src')
HERE = os.path.join(ROOT, 'tools', 'dws', 'testing', 'city_oracle')
OUT = os.path.join(ROOT, 'build', 'citytest')


def read(root, rel):
    with open(os.path.join(root, rel), encoding='utf-8') as f:
        return f.read()


def function(text, name):
    """The definition of `name` (ANSI or K&R style) with its signature, up to the matching brace."""
    for m in re.finditer(r'^[A-Za-z_][\w \*]*\b%s\(' % re.escape(name), text, re.M):
        i = m.end(); depth = 1
        while depth:
            depth += (text[i] == '(') - (text[i] == ')'); i += 1
        j = i
        while text[j] in ' \t\r\n': j += 1
        if text[j] == ';': continue               # a prototype
        k = text.index('{', i); depth = 1; k += 1
        while depth:
            depth += (text[k] == '{') - (text[k] == '}'); k += 1
        return text[m.start():k]
    raise SystemExit(f'city equivalence: {name} not found')


def rename(src, name, new):
    return re.sub(r'\b%s\b' % re.escape(name), new, src)


def snippet(text, first, last_marker):
    i = text.index(first); j = text.index(last_marker, i) + len(last_marker)
    return text[i:j]


def array(text, name):
    m = re.search(r'^[\w ]*\b%s\b[^=;]*=\s*\{.*?\n\};' % re.escape(name), text, re.M | re.S)
    if not m: raise SystemExit(f'city equivalence: array {name} not found')
    return m.group(0)


STUBS = r'''
/* ---- stand-ins for the types and names the extracted functions use */
#define SCREEN_LEGACY_NONE 0xCC
#define VERSION_EQUAL_OR_NEWER(x) 1
#define SCREEN_FLAG_SHOP 0x4
#define SCREEN_FLAG_ARENA 0x8
static uint32_t getScreenFlags(int32_t id) { (void)id; return 0; }  /* an original screen (0..254) has no record flags */
typedef struct { uint8_t map, x, y, size; } PoopPile;
typedef struct { uint8_t array[30]; } InventoryTable;
typedef struct { InventoryTable types, amounts, names; int32_t size; } SavedInventoryStub;
typedef struct { int32_t remainingLifetime; int32_t age; } PartnerParaStub;
typedef struct {
	int32_t mainState;
	PoopPile worldPoop[100];
	int32_t money; int32_t partnerType;
	uint16_t currentFrame; uint16_t lastHandledFrame; int16_t year, day, hour, minute;
	PartnerParaStub partnerPara;
	uint8_t scriptState[0x17C];
	SavedInventoryStub inventory;
	char playerName[20]; char digimonName[20];
	int8_t partnerLives, tamerLevel; uint8_t raisedCount;
	uint8_t currentScreen, currentExit;
	uint8_t pad[0x1000];
} SavegamePayload;
typedef struct { SavegamePayload saves[1]; } SavegameStubFile;
static SavegameStubFile *SAVE_FILE_STUB;
#define SAVE_FILE (*SAVE_FILE_STUB)
static char MAIN_D_801346C4[] = "TAMER";
static char MAIN_D_8013468C[] = "DIGI";
'''


def generate():
    o_main = read(ORIG, 'main/main.c'); t_main = read(STORY_STATE_SOURCE, 'main/main.c')
    o_map = read(ORIG, 'main/map.c'); t_map = read(STORY_STATE_SOURCE, 'main/map.c')
    o_mm = read(ORIG, 'main/main_menu.c'); t_mm = read(STORY_STATE_SOURCE, 'main/main_menu.c')
    o_sc = read(ORIG, 'main/script_common.c'); t_sc = read(STORY_STATE_SOURCE, 'main/script_common.c')
    o_murd = read(ORIG, 'murd/murd.c'); t_murd = read(STORY_STATE_SOURCE, 'murd/murd.c')
    o_dooa = read(ORIG, 'dooa/dooa.c'); t_dooa = read(STORY_STATE_SOURCE, 'dooa/dooa.c')
    out = [STUBS]
    out.append('/* original tables */\n' + array(o_mm, 'DEFAULT_INVENTORY_AMOUNTS') + '\n' + array(o_mm, 'DEFAULT_INVENTORY_TYPES')
               + '\n' + array(o_sc, 'SHOP_MAPS') + '\n' + array(o_sc, 'ARENA_MAPS') + '\n')
    for old, new, srcs in (('recalculatePPandArena', 'recalc', (o_main, t_main)), ('getFileCityTopMap', 'topmap', (o_map, t_map)),
                           ('initializeDefaultSavegame', 'init', (o_mm, t_mm)), ('checkShopMap', 'checkShopMap', (o_sc, t_sc)),
                           ('checkArenaMap', 'checkArenaMap', (o_sc, t_sc))):
        for pre, src in (('o_', srcs[0]), ('t_', srcs[1])):
            out.append(f'/* {"original decomp/src" if pre == "o_" else "build/decomp-story-state/src"}: {old} */\n' + rename(function(src, old), old, pre + new) + '\n')
    # the revival condition: inline in a long function of two overlays
    o_m = snippet(o_murd, 'if ((isTriggerSet(0xdc) == 1)', 'message = 0xda;\n\t\t}')
    t_m = snippet(t_murd, '#if ENGINE_TIER >= 2\n\t\tmessage = cityRevivalScreen()', '#endif')
    o_d = snippet(o_dooa, 'if ((isTriggerSet(0xdc) == 1)', 'messageId = 0xda;\n\t}')
    t_d = snippet(t_dooa, '#if ENGINE_TIER >= 2\n\tmessageId = cityRevivalScreen()', '#endif')
    out.append('int32_t o_revival_murd(void) { int32_t message;\n' + o_m + '\nreturn message; }\n')
    out.append('int32_t t_revival_murd(void) { int32_t message;\n' + t_m + '\nreturn message; }\n')
    out.append('int32_t o_revival_dooa(void) { int32_t messageId;\n' + o_d + '\nreturn messageId; }\n')
    out.append('int32_t t_revival_dooa(void) { int32_t messageId;\n' + t_d + '\nreturn messageId; }\n')
    return '\n'.join(out)


def build():
    os.makedirs(OUT, exist_ok=True)
    gen = os.path.join(OUT, 'equiv_gen.h')
    open(gen, 'w').write(generate())
    exe = os.path.join(OUT, 'equiv')
    cmd = ['gcc', '-std=gnu99', '-O1', '-w', '-DCITY_HOST_TEST', '-DENGINE_TIER=2', f'-I{HERE}', f'-I{OUT}', f'-I{os.path.join(STORY_STATE_SOURCE, "main")}',
           os.path.join(HERE, 'harness_main.c'), os.path.join(STORY_STATE_SOURCE, 'main', 'city_rules.c'), '-o', exe]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit('harness build failed:\n' + r.stderr[-4000:])
    return exe


def check_files():
    """The shipped header is what the compiler writes; the declaration is what the extractor reads."""
    spec = city.extract_original()
    want = city.to_dws(spec)
    have = open(os.path.join(ROOT, 'story/base/city/city.dws'), encoding='utf-8').read()
    assert want == have, 'story/base/city/city.dws is not what `dws city-extract` writes from the original C'
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    from dws import citycli
    spec2 = citycli.load_spec(os.path.join(ROOT, 'story/base/city/city.dws'))
    assert city.encode(spec2) == city.encode(spec), 'parsing city.dws does not give the extracted rules'
    hdr = open(os.path.join(STORY_STATE_SOURCE, 'main', 'city_default.h')).read()
    assert hdr == city.to_c_header(city.encode(spec2)), 'city_default.h is not what `dws city-compile --c-header` writes'
    print('files: city.dws = city-extract of the original C; city_default.h = city-compile of city.dws')


def real_levels_check(exe):
    """All of 3..58 recruited at the levels of the real game (content/species): the prosperity of the finished city."""
    lv = city.State.levels()
    spec = city.extract_original()
    st = city.State(triggers={200 + s for s in range(3, 0x3b)})
    want = city.prosperity_of(spec['prosperity'], st)
    # through the C reader
    line = 'T ' + ' '.join(str(200 + s) for s in range(3, 0x3b)) + ' L ' + ' '.join(str(lv.get(i, 0)) for i in range(1024))
    out = subprocess.run([exe, 'table', os.path.join(OUT, 'default.bin')], input=line + '\n', capture_output=True, text=True).stdout.split()
    got = int(out[2])
    # the original rule, computed by hand from the same CSV
    pp = 0
    for i in range(3, 0x3b):
        if lv[i] >= 3: pp = (pp + (1 if i in (0xb, 0x27, 0x35) else lv[i] - 2)) & 0xFF
    assert want == got == pp, (want, got, pp)
    print(f'prosperity of the whole city (all of 3..58 recruited, the real levels): {pp} (table in C = Python = original formula)')


def random_cond(rng, species_pool):
    cond = []
    for _ in range(rng.randint(0, 3)):
        clause = []
        for _ in range(rng.randint(0, 3)):
            k = rng.choice([city.TRIG_SET, city.TRIG_CLEAR, city.PSTAT_GE, city.PSTAT_LT, city.REC, city.NOT_REC])
            if k in (city.TRIG_SET, city.TRIG_CLEAR): clause.append((k, 0, rng.choice([5, 44, 220, 214, 800, 1000, 17000])))
            elif k in (city.PSTAT_GE, city.PSTAT_LT): clause.append((k, 1, rng.randint(0, 120)))
            else: clause.append((k, 0, rng.choice(species_pool)))
        cond.append(clause)
    return cond


def random_spec(rng):
    pool = [3, 11, 20, 46, 53, 58, 90, 111, 112, 200, 500, 1023]
    spec = {'prosperity': [], 'top_map': {'default': rng.randint(1, 255), 'rows': []}, 'revival': {'default': rng.randint(1, 255), 'rows': []}}
    for _ in range(rng.randint(0, 5)):
        a = rng.choice(pool); b = min(1023, a + rng.randint(0, 40))
        spec['prosperity'].append({'first': a, 'last': b, 'min_level': rng.randint(0, 5), 'add': rng.randint(-3, 3), 'per_level': rng.randint(0, 3)})
    for k in ('top_map', 'revival'):
        for _ in range(rng.randint(0, 6)):
            spec[k]['rows'].append({'screen': rng.randint(1, 1000), 'when': random_cond(rng, pool)})
    return spec


def random_tables(exe, n_specs, n_states):
    rng = random.Random(7); lv = city.State.levels(); n = 0
    for k in range(n_specs):
        spec = random_spec(rng); blob = city.encode(spec)
        path = os.path.join(OUT, 'rand.bin'); open(path, 'wb').write(blob)
        lines = []; states = []
        for _ in range(n_states):
            trig = {t for t in [5, 44, 220, 214, 800, 1000, 17000] if rng.random() < 0.4}
            rec = {s for s in [3, 11, 20, 46, 53, 58, 90, 111, 112, 200, 500, 1023] if rng.random() < 0.5}
            levels = [rng.randint(0, 8) for _ in range(1024)]
            p1 = rng.randint(0, 120)
            st = city.State(triggers=trig | {200 + s for s in rec if s < 0x70}, pstats={1: p1})
            st.triggers |= {('r', s) for s in rec if s >= 0x70}
            states.append((st, levels, trig, rec, p1))
            line = 'T ' + ' '.join(map(str, sorted(trig))) + ' P ' + str(p1) + ' R ' + ' '.join(map(str, sorted(rec))) + ' L ' + ' '.join(map(str, levels))
            lines.append(line)
        out = subprocess.run([exe, 'table', path], input='\n'.join(lines) + '\n', capture_output=True, text=True).stdout.splitlines()
        assert len(out) == n_states, (len(out), n_states)
        for (st, levels, trig, rec, p1), o in zip(states, out):
            city.State.LEVELS = {i: l for i, l in enumerate(levels)}
            exp = (city.top_map_of(spec['top_map'], st), city.top_map_of(spec['revival'], st), city.prosperity_of(spec['prosperity'], st))
            got = tuple(int(x) for x in o.split()[:3])
            if exp != got:
                sys.exit(f'MISMATCH python {exp} vs C {got}\nspec {spec}\nstate triggers {sorted(map(str, st.triggers))} p1 {p1}')
            n += 1
        city.State.LEVELS = None
    print(f'random declarations: {n} (table, state) pairs, the C reader equals the Python evaluator (top map, revival, prosperity)')


def git_show(rel):
    return subprocess.run(['git', '-C', os.path.join(ROOT, 'decomp'), 'show', 'integration:src/' + rel], capture_output=True, text=True, check=True).stdout


def norm(text):
    """Comments and conditional compilation resolved with ENGINE_TIER 0, whitespace collapsed."""
    r = subprocess.run(['cpp', '-P', '-undef', '-DENGINE_TIER=0'], input=text, capture_output=True, text=True)
    return re.sub(r'\s+', ' ', r.stdout).strip()


def original():
    """Original-engine check: with ENGINE_TIER=0 the sources are the integration branch's, function by function (the call sites are `#if ENGINE_TIER >= 2`)."""
    n = 0
    for rel, names in (('main/main.c', ['recalculatePPandArena']), ('main/map.c', ['getFileCityTopMap']),
                       ('main/main_menu.c', ['initializeDefaultSavegame']), ('main/script_common.c', ['checkShopMap', 'checkArenaMap'])):
        a, b = git_show(rel), read(STORY_STATE_SOURCE, rel)
        for nm in names:
            fa, fb = function(a, nm), function(b, nm)
            assert norm(fa) == norm(fb), f'{rel} {nm}: ENGINE_TIER=0 is not the integration branch\'s code'
            n += 1
    for rel, first, last in (('murd/murd.c', 'if ((isTriggerSet(0xdc) == 1)', 'message = 0xda;\n\t\t}'), ('dooa/dooa.c', 'if ((isTriggerSet(0xdc) == 1)', 'messageId = 0xda;\n\t}')):
        a, b = git_show(rel), read(STORY_STATE_SOURCE, rel)
        i = b.index(first if True else '') if first in b else None
        # story-state text: the whole `#if ENGINE_TIER >= 2 ... #else <original> #endif` block
        j = b.rindex('#if ENGINE_TIER >= 2', 0, i); k = b.index('#endif', i) + len('#endif')
        assert norm(b[j:k]) == norm(snippet(a, first, last)), f'{rel}: the original revival condition changed'
        n += 1
    # the declarations that story-state does not need are still there for original
    for rel, nm in (('main/script_common.c', 'SHOP_MAPS'), ('main/script_common.c', 'ARENA_MAPS'), ('main/main_menu.c', 'DEFAULT_INVENTORY_TYPES'),
                    ('main/main_menu.c', 'DEFAULT_INVENTORY_AMOUNTS')):
        b = read(STORY_STATE_SOURCE, rel); i = b.index(nm)
        assert '#if ENGINE_TIER < 2' in b[max(0, i - 400):i], nm
        n += 1
    print(f'original-engine check: {n} functions, conditions and tables are the integration branch\'s code with ENGINE_TIER=0')


def mutants():
    """Negative control: a built-in table with one rule changed must be caught by the grids."""
    import copy
    spec = city.extract_original(); H = os.path.join(STORY_STATE_SOURCE, 'main', 'city_default.h'); keep = open(H).read()
    muts = {}
    m = copy.deepcopy(spec); m['top_map']['rows'][3]['screen'] += 1; muts['top map: row 4 gives another screen'] = m
    m = copy.deepcopy(spec); m['top_map']['rows'][0]['when'][0].pop(); muts['top map: row 1 drops Vegiemon'] = m
    m = copy.deepcopy(spec); m['revival']['rows'][0]['when'][2] = [(city.PSTAT_GE, 1, 51)]; muts['revival: prosperity >= 51'] = m
    m = copy.deepcopy(spec); m['prosperity'][3]['add'] = -1; muts['prosperity: level - 1'] = m
    m = copy.deepcopy(spec); m['prosperity'].pop(1); muts['prosperity: Sukamon is not exempt'] = m
    m = copy.deepcopy(spec); m['start']['bits'] = 50001; muts['start: 50001 bits'] = m
    m = copy.deepcopy(spec); m['start']['inventory'][5] = (m['start']['inventory'][5][0], 31); muts['start: one stack differs'] = m
    m = copy.deepcopy(spec); m['shop_maps'][2] = 135; muts['shop maps: 134 -> 135'] = m
    m = copy.deepcopy(spec); m['arena_maps'].pop(); muts['arena maps: one less'] = m
    caught = 0
    try:
        for name, mm in muts.items():
            open(H, 'w').write(city.to_c_header(city.encode(mm)))
            exe = build()
            r = subprocess.run([exe], capture_output=True, text=True)
            ok = r.returncode != 0
            caught += ok
            first = next((l for l in r.stdout.splitlines() if 'mismatch' in l.lower() and not l.endswith(' 0 mismatches')), '')
            print(f'  mutant "{name}": {"caught" if ok else "NOT CAUGHT"}  {first.strip()}')
    finally:
        open(H, 'w').write(keep)
    print(f'{caught} of {len(muts)} mutants caught')
    return 0 if caught == len(muts) else 1


def main():
    if '--mutants' in sys.argv:
        sys.exit(mutants())
    quick = '--quick' in sys.argv
    check_files()
    original()
    exe = build()
    os.makedirs(OUT, exist_ok=True)
    spec = city.extract_original(); open(os.path.join(OUT, 'default.bin'), 'wb').write(city.encode(spec))
    r = subprocess.run([exe]);
    if r.returncode: sys.exit(1)
    # the same grids, with the table that `dws` writes into MAPHEAD instead of the built-in one
    r = subprocess.run([exe, 'table', os.path.join(OUT, 'default.bin')], input='T 220 214 221\n', capture_output=True, text=True)
    top = int(r.stdout.split()[0]); assert top == 177, top
    real_levels_check(exe)
    random_tables(exe, 20 if quick else 150, 40 if quick else 120)
    print('ALL EQUIVALENCE CHECKS PASSED')


if __name__ == '__main__':
    main()
