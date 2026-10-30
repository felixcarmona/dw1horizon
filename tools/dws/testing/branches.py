#!/usr/bin/env python3
"""Branch scenarios of the story route : what the main route C19-C33 (tools/dws/testing/route.py) does not walk. Docs: docs/developing.md, "Branches".

  tools/dws/testing/branches.py plan                                  the scenarios, one line each
  tools/dws/testing/branches.py run --disc D --port N --only ID,ID    scenarios on one disc, each from the ORIGINAL's saved state of the route (build/checkpoints/r-*.state);
                                                       rows in build/checkpoints/branch/rows/ID.D.json, traces build/checkpoints/branch/ID.D.trace
  tools/dws/testing/branches.py compare                               every scenario: the original against readable, reorder, mut1 (and orig2), offline from the rows and traces
  tools/dws/testing/branches.py coverage [--candidates]               sections executed per scenario (from the original's traces) -> docs/data/story-analysis/scenario-coverage.csv
  tools/dws/testing/branches.py table                                 docs/data/story-analysis/checkpoints.csv: the old rows stay, one row per scenario is added (replaced when it is there)
  tools/dws/testing/branches.py hangs --port N --part K/M             the sections the sweep could not compare (UNPLACED-NPC, HANG, did not start): run on orig, reorder, readable in a private ledger
  tools/dws/testing/branches.py hangs-report                          -> docs/data/story-analysis/unprovable.csv: does each behave on the rebuilt discs as on the original (same end, same place, same trace)

Kinds of scenario:
  L*  the LOSS branch of a forced battle of the route: the same start state and the same steps up to the battle, the battle lost (`battle='lose'`: at battle frame 90 the
      partner's HP is set to 0), then the scenario reads whatever the game does next until the tamer is free (or the screen changes);
  S*  side content off the main route, chosen by the coverage they add (`coverage --candidates`): the area or the city screens visited from a story state of the route
      (warp, then every NPC that is there talked to, every tile section stepped on, every X-tile pressed), recruitments and quests as the scripts play them, battles won.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import argparse, collections, csv, glob, json, os, re, subprocess, sys, time


def _early_port():
    for i, a in enumerate(sys.argv):
        if a == '--port' and i + 1 < len(sys.argv): os.environ['EMU_PORT'] = sys.argv[i + 1]


_early_port()
os.environ.setdefault('EMU_PORT', '38020')
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from dws.testing import route as R
C = R.C; W = R.W; T = R.T; CK = R.CK
BR = os.path.join(CK, 'branch')
_slow = W.host_slowdown
W.host_slowdown = lambda: max(2.0, _slow())          # the host-time limit of a run: the tours are long (up to 16 000 frames) and 8 emulators run them at 20-30 fps; `host` is no result
ROWS = os.path.join(BR, 'rows')
DISCS = ('orig', 'reorder', 'readable', 'mut1', 'orig2')
DATA = os.path.join(ROOT, 'build/story-analysis')   # tools/story_analysis.py writes scripts.csv and recruits.csv here
os.makedirs(DATA, exist_ok=True)

# ---------------------------------------------------------------------------------------------------
# the scenarios

SCEN = []


def scen(id, doc, start, steps, pre=(), battle='win', lose_nth=None, frames=16000, hang_after=30, kind='side'):
    SCEN.append(dict(id=id, run=id, doc=doc, start=start, steps=list(steps), pre=list(pre), battle=battle, lose_nth=lose_nth, frames=frames, hang_after=hang_after, kind=kind))


def side(id, run, note=''):
    """A side scenario: the area tour RUN of CANDIDATES() (its rows and traces keep that name), chosen by `coverage --all` (the greedy order of the sections it adds)."""
    SCEN.append(dict(id=id, run=run, note=note, kind='side'))


# after a lost battle: whatever the game does next is read (boxes pressed) until the tamer is free, then a while longer in case a scene or a warp follows
AFTER_LOSS = ['talk after battle {n} max 9000', 'talk until free max 9000', 'wait 120', 'talk? until free max 3000', 'wait 60']


def lost(n=1):
    return [x.format(n=n) for x in AFTER_LOSS]


def arrive(screen, mx=4000):
    return [f'warp {screen} 0', f'talk until CURRENT_SCREEN=={screen} and free max {mx}', 'wait 60']


# L: the loss branch of each forced battle of the route (the same start and story state as the won segment)
scen('L19', 'LOSS of the Agumon fight of the Native Forest (105:6; the won one is C19): the battle lost, then what the game does', 'c4-jijimon-talk',
     ['tile 51', 'talk until CURRENT_SCREEN==204 and free max 4000', 'wait 60'] + R.go(112, 1) + R.go(109, 0) + ['npc 6 180', 'wait 20', 'until running press CROSS 3 every 40 max 300'] + lost(),
     battle='lose', kind='loss')
scen('L24', 'LOSS of the bandit ambush (43:51, 3 foes; won in C24)', 'r-c23', arrive(43) + ['tile 51', 'until running max 300'] + lost(), battle='lose', kind='loss')
scen('L26', 'LOSS of Ogremon and the two Agumon (48:52; won in C26): the wild Gabumon on the way won, the second battle of the run lost', 'r-c25',
     ['door 1 46', 'wait 60', 'door 1 47', 'wait 60', 'door 1 48', 'wait 60', 'tile 52', 'until running max 300'] + lost(2), lose_nth=2, kind='loss')
scen('L27', 'LOSS of Greymon by the falls (162:57; won in C27): the same recruits, evolution and Jijimon talk first', 'r-c26',
     arrive(218) + R.talk_npc(5) + ['tile 51', 'talk until CURRENT_SCREEN==169 and free max 4000', 'wait 60', 'tile 57', 'until running max 300'] + lost(),
     pre=R.RECRUITS_B + R.evolve(5), battle='lose', kind='loss')
scen('L28', 'LOSS of Airdramon (162:57 with T354; won in C28): Jijimon opens Mt. Infinity, the upper city walks the tamer to the falls, the battle lost', 'r-c27',
     arrive(218) + R.talk_npc(5) + ['tile 51'] + lost(), pre=R.RECRUITS_C, battle='lose', kind='loss')
scen('L30', 'LOSS of Megadramon (198:53, the second answer: fight; won in C30)', 'r-c29', ['tile 53', 'until running max 300'] + R.choose_second() + lost(), battle='lose', kind='loss')
scen('L31', 'LOSS of MetalGreymon (182:53; won in C31)', 'r-c30', ['doortile 51 222', 'wait 30', 'tile 53', 'until running max 300'] + lost(), battle='lose', kind='loss')
scen('L32', 'LOSS of Machinedramon (184:51, the last battle; won in C32)', 'r-c31',
     ['tile 52', 'talk until CURRENT_SCREEN==225 and free max 4000', 'wait 60', 'tile 51', 'until running max 300'] + lost(), battle='lose', kind='loss')

# S: side content. A visit: warp to the screen, then every NPC whose script id is a section of the screen's script talked to (wherever it stands), every tile section
# stepped on, every X-tile pressed; a script that takes the tamer elsewhere (a warp, a recruit sent to the city) is followed by a warp back (`warpif`).

_DIS = {}


def sections_of(sid):
    """{section: has a WARP_TO in its own code} of a script (build/scn-dis)."""
    if sid not in _DIS:
        out = {}; cur = None
        for l in open(os.path.join(ROOT, f'build/scn-dis/script_{sid:03d}.scn.txt'), encoding='utf-8'):
            m = l.split(':')[0]
            if l.startswith('sec') and m[3:].isdigit(): cur = int(m[3:]); out[cur] = False
            elif cur is not None and 'WARP_TO' in l: out[cur] = True
        _DIS[sid] = out
    return _DIS[sid]


def visit(screen, sid, only=None, warps=True):
    """Steps that visit SCREEN (script SID): its NPCs, its tile sections and its X-tiles; `only` limits it to these sections."""
    secs = sections_of(sid); back = [f'warpif {screen} skip 2', f'talk until CURRENT_SCREEN=={screen} and free max 4000', 'wait 60']
    st = arrive(screen)
    for s in sorted(secs):
        if only is not None and s not in only: continue
        if 1 <= s <= 50:
            st += back + [f'npc? {s} skip 4', 'camera', 'wait 30', 'until? running press CROSS 3 every 40 max 150', 'talk? until free max 2500', 'wait 20']
        elif 51 <= s <= 79 and (warps or not secs[s]):
            st += back + [f'tile? {s} skip 2', 'until? running max 60', 'talk? until free max 600', 'wait 10']
        elif 80 <= s <= 109 and (warps or not secs[s]):
            st += back + [f'tile? {s} skip 2', 'until? running press CROSS 3 every 30 max 120', 'talk? until free max 1500', 'wait 10']
    return st


def tour(screens):
    """[(screen, script)] -> the visits one after the other."""
    return sum((visit(s, sid) for s, sid in screens), [])


# ---------------------------------------------------------------------------------------------------
# running

def spath(name): return os.path.join(CK, name + '.state')


def rows_file(sid, disc): return os.path.join(ROWS, f'{sid}.{disc}.json')


def trace_file(sid, disc): return os.path.join(BR, f'{sid}.{disc}.trace')


def steps_of(s):
    st = [T.parse_step('clock 9 12')] + [T.parse_step(x) for x in s['pre']] + [dict(t='trace', on=True)] + W.seed_pokes()
    st += [T.parse_step(x) for x in s['steps']] + [dict(t='mark', name='final'), dict(t='end')]
    st = [x for z in st for x in (z['steps'] if z['t'] == 'multi' else [z])]
    if s['id'] in ONGRID:
        for x in st:
            if x['t'] == 'approach': x['ongrid'] = True
    return st


# Tours whose `approach` must never put the tamer off the 100x100 tile grid. S63 (V-Ov1): its NPC 7 is parked at z=-15702, the game then reads MAP_COLLISION_DATA far past its end, into
# MAPHEAD's buffer, and a byte of the script layout acts as a tile trigger ("S63: the MAPHEAD difference" in story-testing.md). Seven more tours approach an off-grid NPC; five have the guard
# (rerun on every disc: no DIFF). V-BeLa1 and V-GeSa2 keep the old path (an inert byte on every disc, equal as recorded): with the guard they show the frame drift of the pad
# phase (V-BeLa1 on reorder -28 frames, V-GeSa2 on readable +26), a harness timing that is not understood yet.
ONGRID = {'V-Ov1', 'V-AnGlRe1', 'V-Fr1', 'V-GeSa3', 'V-GrCaToAr1', 'V-MtIn1'}


def find(sid):
    for s in [x for x in SCEN if x['kind'] != 'side'] + CANDIDATES():
        if s['id'] == sid: return s
    raise KeyError(sid)


def run_one(Rn, s, disc):
    t0 = time.time(); extra = R.battle_extra(s['battle'] or 'win')
    if s.get('lose_nth'): extra['battle']['lose_nth'] = s['lose_nth']; extra['battle']['mode'] = 'win'
    text = Rn.run(steps_of(s), spath(s['start']), trace_file(s['id'], disc), max_frames=s['frames'], idle_frames=None, max_ins=400000, stop_on_battle=False,
                  hang_after=s['hang_after'], extra=extra)
    ev, row = W.analyse(text, Rn.sc)
    row.update(secs=round(time.time() - t0), hang_at=Rn.hang_at, disc=disc, case=s['id'], start=s['start'], reached=True,
               battles=[e['key'] for e in ev if e['kind'] == 'Y' and ' battle ' in e['key']])
    row['sections'] = sorted(f'{a}:{b}' for a, b in entered(ev, 'orig' if disc in ('orig', 'orig2') else disc))
    if W.emu_alive() and row['end'] not in ('hang',):
        try: st = R.peek_state(); row['story'] = dict(p1=st['pstats'].get(1, 0), screen=st['screen'], triggers=st['triggers'])
        except Exception: pass
    return ev, row


def cmd_run(a):
    os.makedirs(ROWS, exist_ok=True); Rn = W.Runner(a.disc)
    alias = {x['id']: x['run'] for x in SCEN}
    for sid in a.only.split(','):
        sid = alias.get(sid, sid); s = find(sid)          # S01 -> its tour V-IcSa2 (rows and traces keep the tour's name)
        if os.path.exists(rows_file(sid, a.disc)) and not a.redo: continue
        try: ev, row = run_one(Rn, s, a.disc)
        except Exception as e:
            import traceback; traceback.print_exc()
            R.log(f'{sid} on {a.disc}: error {e}'); W.stop_emulator(); continue
        tmp = rows_file(sid, a.disc) + f'.part{os.getpid()}'; json.dump(row, open(tmp, 'w'), indent=1); os.replace(tmp, rows_file(sid, a.disc))
        R.log(f'{sid} on {a.disc}: {row["n"]} ins, {row["frames"]} frames, ends {row["end"]}, {row["secs"]} s, battles {len(row["battles"])}, {len(row["sections"])} sections, digest {row["digest"][:10]}')
    W.stop_emulator()


def load_row(sid, disc):
    try: return json.load(open(rows_file(sid, disc)))
    except (OSError, ValueError): return None


def collapse_reruns(tokens):
    """The normalized trace with every run of identical, consecutive section runs collapsed to one (`RERUN`): a block that starts with an instruction, contains an
    END_SECTION and is repeated token for token, state writes included (the same old and new value: each repetition starts from the state the last one left and leaves
    it so, it adds nothing). A tile section reruns on every frame the tamer stands on its tile (C24: `tile_scene`), some with a box each time; how many times depends on
    the frames and on the press phase of the boxes, and those move between discs: after a battle or a load the frames of a rebuilt disc differ (its scripts are read from
    other places of the CD: V-IcSa2 ends a battle 42 frames later on `reorder`, L26 a box 28 frames later), and a CROSS press can land one box later (V-BaDi1 on
    `readable`: one more box of 186's tile in the same 56 frames). The count of such idempotent reruns is what this forgives, nothing else."""
    out = []; i = 0; n = len(tokens)
    while i < n:
        done = False
        for L in range(1, 17):
            blk = tokens[i:i + L]
            if len(blk) < L or not blk[0].startswith('I ') or not any(t.startswith('I ') and ' END_SECTION ' in t + ' ' for t in blk): continue
            if tokens[i + L:i + 2 * L] != blk: continue
            j = i + L
            while tokens[j:j + L] == blk: j += L
            out += blk + ['RERUN']; i = j; done = True; break
        if not done: out.append(tokens[i]); i += 1
    return out


def norm(ev):
    """The sweep's normalized trace (sweep.relaxed_events) without the frame number that the harness's own `Y` notes carry (`Y 6213 battle win ...`: the frame is
    in the text of the note, so a battle that ends some frames later on another disc changed the normalized trace; the route never met it: its discs had no drift), and
    without the sounds between a battle's start and the next script instruction (the battle and its results screens: the results are pressed through by the harness
    every 40 vsyncs, and a confirm sound more or less there is the harness's phase, V-AnSpRe1 on `reorder`; the battle's own music and its `B`/`Y` events stay)."""
    return norm_tokens(W.relaxed_events(ev))


def norm_tokens(tokens):
    out = []; battle = False
    for t in tokens:
        if t.startswith('B '): battle = True
        elif t.startswith('I '): battle = False
        if battle and t.startswith('S '): continue          # the sounds of the battle and its results screens (bank 0 too): the C code's, and as many as the harness's presses there
        out.append(re.sub(r'^Y \d+ ', 'Y ', t))
    return out


def verdict(sid, disc):
    """same (strict digests equal) | relaxed (normalized equal; a cut run: up to the shorter one) | relaxed+reruns (also the count of no-op reruns of a tile section
    collapsed: collapse_reruns) | DIFF."""
    o = load_row(sid, 'orig'); r = load_row(sid, disc)
    if o is None or r is None: return None
    strict = 'same' if o['digest'] == r['digest'] else 'differs'
    if strict == 'same': return dict(compare='same', strict=strict)
    eo = T.parse_trace(open(trace_file(sid, 'orig')).read(), W.scripts_of('orig')); er = T.parse_trace(open(trace_file(sid, disc)).read(), W.scripts_of(W.ALIAS.get(disc, disc)))
    na, nb = norm(eo), norm(er); cut = {'ilimit', 'timeout', 'max_frames'} & {o['end'].split(' step')[0], r['end'].split(' step')[0]}
    same_end = o['end'].split(' step')[0] == r['end'].split(' step')[0]
    if na == nb and same_end: v = 'relaxed'
    elif cut and _prefix(na, nb): v = 'relaxed'
    else:
        ca, cb = collapse_reruns(na), collapse_reruns(nb)
        v = 'relaxed+reruns' if (ca == cb and same_end) or (cut and _prefix(ca, cb)) else 'DIFF'
    out = dict(compare=v, strict=strict)
    if v == 'DIFF': out['drift'] = drift_first(eo, er)
    return out


def drift_first(eo, er):
    """For a DIFF: did the two runs drift in frames before they differ in what they do? Over the state writes, music and battle events (in order): the index of the first
    one on another frame and of the first one that is another event. -> 'timing' (a frame drift first: the runs agree on every event up to there, only later), or 'event'."""
    ka = [(e['key'], e['frame']) for e in eo if e['kind'] in 'WMB']; kb = [(e['key'], e['frame']) for e in er if e['kind'] in 'WMB']
    key_at = next((i for i, (x, y) in enumerate(zip(ka, kb)) if x[0] != y[0]), min(len(ka), len(kb)))
    fr_at = next((i for i, (x, y) in enumerate(zip(ka, kb)) if x[1] != y[1]), None)
    return dict(kind='timing' if fr_at is not None and fr_at < key_at else 'event', frame_at=ka[fr_at][1] if fr_at is not None and fr_at < len(ka) else None,
                shift=(kb[fr_at][1] - ka[fr_at][1]) if fr_at is not None and fr_at < min(len(ka), len(kb)) else None, first_event=ka[key_at][0] if key_at < len(ka) else None)


def cmd_selftest(a):
    """The relaxations of the branch comparison (norm_tokens: the frame in `Y` notes, the battle's sounds; collapse_reruns: idempotent reruns) on real traces of the
    original (V-BaDi1, L19): what is forgiven, what is caught."""
    ok = True
    def check(name, x, y, want):
        nonlocal ok
        got = collapse_reruns(norm_tokens(x)) == collapse_reruns(norm_tokens(y)); ok &= got == want
        print(f'{"ok  " if got == want else "FAIL"} {name}: {"equal" if got else "differs"} (expected {"equal" if want else "differs"})')
    t = W.relaxed_events(T.parse_trace(open(trace_file('V-BaDi1', 'orig')).read(), W.scripts_of('orig')))
    k, L = next((i, L) for i in range(len(t)) for L in range(1, 17) if t[i].startswith('I ') and any(' END_SECTION ' in x + ' ' for x in t[i:i + L]) and t[i:i + L] == t[i + L:i + 2 * L])
    check(f'one more idempotent rerun of a section ({L} events)', t, t[:k] + t[k:k + L] + t[k:], True)
    w = next(i for i in range(k, k + L) if t[i].startswith('W ')) if any(x.startswith('W ') for x in t[k:k + L]) else None
    if w is not None: check('the same rerun with another value written', t, t[:k + L] + t[k:w] + [t[w][:-1] + ('0' if t[w][-1] != '0' else '1')] + t[w + 1:k + L] + t[k + L:], False)
    m = next(i for i in range(len(t) - 1) if t[i].startswith('I ') and ' END_SECTION ' not in t[i] + ' ' and t[i + 1].startswith('I ') and t[i] != t[i + 1])
    check('an instruction missing', t, t[:m] + t[m + 1:], False)
    check('two instructions swapped', t, t[:m] + [t[m + 1], t[m]] + t[m + 2:], False)
    b = next(i for i in range(len(t)) if t[i].startswith('B '))
    check('one more sound in a battle\'s results', t, t[:b + 1] + ['S 0 3'] + t[b + 1:], True)
    check('one more text-box sound outside a battle', t, t[:m] + ['S 0 3'] + t[m:], False)
    y = next(i for i in range(len(t)) if t[i].startswith('Y '))
    check('a battle note on another frame', t, t[:y] + [re.sub(r'^Y \d+', 'Y 99999', t[y])] + t[y + 1:], True)
    u = W.relaxed_events(T.parse_trace(open(trace_file('L19', 'orig')).read(), W.scripts_of('orig')))
    ms = next(i for i, x in enumerate(u) if x.startswith('M '))
    check('the music of a screen changed (as mut1 does)', u, u[:ms] + ['M 29 0'] + u[ms + 1:], False)
    print('selftest', 'passed' if ok else 'FAILED'); sys.exit(0 if ok else 1)


def cmd_compare(a):
    bad = 0
    for s in SCEN:
        o = load_row(s['run'], 'orig')
        if o is None: print(f'{s["id"]:5} {s["run"]:12} not run'); continue
        line = [f'{s["id"]:5} {s["run"]:12} orig {o["n"]:6} ins {o["frames"]:6} fr {o["end"]:12}']
        for disc in DISCS[1:]:
            v = verdict(s['run'], disc)
            if v is None: line.append(f'{disc} -'); continue
            line.append(f'{disc} {v["strict"]}/{v["compare"]}' + (f' ({v["drift"]["kind"]} {v["drift"]["shift"]:+d} fr at {v["drift"]["frame_at"]})' if v.get('drift') and v['drift']['shift'] is not None else ''))
            if disc in ('reorder', 'readable', 'orig2') and v['compare'] not in ('same', 'relaxed', 'relaxed+reruns'): bad += 1
        print(' | '.join(line))
    sys.exit(1 if bad else 0)


# ---------------------------------------------------------------------------------------------------
# coverage: which sections the played scenarios executed

def plan_sections():
    return {(c['script'], c['section']) for c in W.load_plan()}


_ENTRY = {}


def entered(ev, disc='orig'):
    """The sections whose ENTRY ran: an instruction at offset 0 of its section (code after a section's entry that another section jumps into, as 212:72 into the tail of 212:73,
    does not count); sections that share their entry offset all count."""
    sc = W.scripts_of(disc); out = set()
    for e in ev:
        if e['kind'] != 'I' or e.get('sec') is None or e.get('rel') != 0: continue
        sid = e['sid']
        if sid not in _ENTRY:
            fo = W.first_offsets(sc.raw[sid]); m = collections.defaultdict(list)
            for k, o in fo.items(): m[o].append(k)
            _ENTRY[sid] = (fo, m)
        fo, m = _ENTRY[sid]
        out |= {(sid, k) for k in m.get(fo.get(e['sec']), [e['sec']])}
    return out


def trace_sections(path, disc='orig'):
    return entered(T.parse_trace(open(path).read(), W.scripts_of(disc)), disc)


def route_coverage():
    """{name: sections} of the original's traces of the route: C2-C3 .. C33."""
    out = {}
    for f in sorted(glob.glob(os.path.join(CK, 'C*.orig.trace'))):
        out[os.path.basename(f).split('.')[0]] = trace_sections(f)
    return out


def branch_coverage():
    out = {}
    for f in sorted(glob.glob(os.path.join(BR, '*.orig.trace'))):
        out[os.path.basename(f).split('.')[0]] = trace_sections(f)
    return out


_SCREENS = None


def script_screens():
    global _SCREENS
    if _SCREENS is None:
        _SCREENS = {}
        for r in csv.DictReader(open(os.path.join(DATA, 'scripts.csv'))):
            if not r['script'].isdigit(): continue
            _SCREENS[int(r['script'])] = [(int(x.split()[0]), ' '.join(x.split()[1:])) for x in r['screens'].split(', ') if x.strip()]
    return _SCREENS


CITY = (set(range(168, 219)) - {210, 212}) | {223, 236, 237, 238}          # File City, its houses and shops: the later state (51 of prosperity, the recruits in the city)
FIRST_SCREEN = {162: 175, 163: 180}          # the upper city as r-c28 has it (p1 >= 50: layout 175); the lower city by its door screen
TOUR = 4          # screens per scenario


def slug(name): return ''.join(w[:2].capitalize() for w in name.replace("'", '').replace('.', '').split())[:8]


def CANDIDATES():
    """Area tours: the screen scripts of one area (scripts.csv: the name of the first screen) in groups of up to TOUR screens, one screen per script, visited one after the
    other (visit()). The start state: in the city r-c27 (the upper city after Greymon) with the recruits of C28 written (51 of prosperity), elsewhere r-c21 (6 recruits: the
    Digimon of the areas are still there). The partner is trained as for Mt. Infinity (route.TRAINED): a rookie that meets the wild Digimon of a late area dies in the
    90 battle frames before the win (seen: the first try of the city tour from r-c28, at Mt. Infinity, ended in the defeat scene 212:72)."""
    plan = plan_sections(); areas = collections.OrderedDict()
    for sid, scr in sorted(script_screens().items(), key=lambda x: x[1][0][0] if x[1] else 999):
        if not scr or sid == 0 or not os.path.exists(os.path.join(ROOT, f'build/scn-dis/script_{sid:03d}.scn.txt')): continue
        if not any((sid, x) in plan for x in sections_of(sid)): continue
        scr_ = FIRST_SCREEN.get(sid, scr[0][0])
        areas.setdefault(scr[0][1] or 'Mt. Infinity top', []).append((scr_, sid))
    out = []
    for name, lst in areas.items():
        for k in range(0, len(lst), TOUR):
            part = lst[k:k + TOUR]; city = part[0][0] in CITY; start = 'r-c27' if city else 'r-c21'
            out.append(dict(id=f'V-{slug(name)}{k // TOUR + 1}', doc=f'{name}: visit of screens {", ".join(str(x) for x, _ in part)} (scripts {", ".join(str(y) for _, y in part)}) from {start}' + (' with the recruits of C28 (p1=51)' if city else ''),
                            start=start, pre=(R.RECRUITS_C if city else []) + R.TRAINED, steps=tour(part) + ['wait 30'], battle='win', lose_nth=None, frames=16000, hang_after=30, kind='candidate',
                            scripts=[y for _, y in part], screens=[x for x, _ in part]))
    return out


def cmd_coverage(a):
    plan = plan_sections(); rc = route_coverage(); bc = branch_coverage()
    base = set().union(*rc.values()) & plan
    print(f'route C2-C33: {len(base)} of {len(plan)} sections ({100 * len(base) / len(plan):.1f} %)')
    if a.candidates:
        cands = CANDIDATES(); est = []
        for c in cands:
            pot = {(sid, x) for sid in c['scripts'] for x in sections_of(sid)} | {(0, x) for x in c['screens']}
            est.append((len((pot & plan) - base), c['id'], c['doc']))
        est.sort(reverse=True)
        for n, i, d in est[:a.top]: print(f'{n:3} {i:6} {d}')
        return
    got = set(base); rows = [dict(scenario=k, sections=len(v & plan), new='', total_after='', new_sections='') for k, v in rc.items()]
    loss = [x['id'] for x in SCEN if x['kind'] == 'loss']; side = [x['run'] for x in SCEN if x['kind'] == 'side']
    pool = {k: v & plan for k, v in bc.items() if (a.all or k in side) and k not in loss}
    order = [k for k in loss if k in bc]
    for k in order:
        new = (bc[k] & plan) - got; got |= new
        rows.append(dict(scenario=k, sections=len(bc[k] & plan), new=len(new), total_after=len(got), new_sections=' '.join(f'{s}:{t}' for s, t in sorted(new))))
    while pool:          # greedy: the scenario that adds the most sections not covered yet, then the next
        k = max(pool, key=lambda x: (len(pool[x] - got), x))
        new = pool.pop(k) - got; got |= new
        lab = next((f'{x["id"]} ({k})' for x in SCEN if x.get('run') == k), k)
        rows.append(dict(scenario=lab, sections=len(bc[k] & plan), new=len(new), total_after=len(got), new_sections=' '.join(f'{s}:{t}' for s, t in sorted(new))))
    by_script = collections.Counter(s for s, _ in got)
    print(f'route + loss + {"all candidates" if a.all else "side"}: {len(got)} of {len(plan)} ({100 * len(got) / len(plan):.1f} %); MAPHEAD {by_script[0]} of {sum(1 for s, _ in plan if s == 0)}')
    for r in rows:
        if r['new'] != '': print(f'  {r["scenario"]:18} {r["sections"]:3} sections, +{r["new"]:3} -> {r["total_after"]}')
    if not a.all:
        path = os.path.join(DATA, 'scenario-coverage.csv')
        with open(path, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['scenario', 'sections', 'new', 'total_after', 'new_sections']); w.writeheader(); [w.writerow(r) for r in rows]
        print(path)


def cmd_pool(a):
    """pool --ports 38020,38021 --jobs ID:DISC,ID:DISC...: the jobs shared out over the ports (one emulator each, nice 10), each port runs its share one after the other;
    a job whose row exists is skipped. Waits for all."""
    ports = a.ports.split(','); jobs = [j.split(':') for j in a.jobs.split(',') if j and not os.path.exists(rows_file(*j.split(':')))]
    procs = []
    for k, port in enumerate(ports):
        mine = jobs[k::len(ports)]
        if not mine: continue
        cmd = ' ; '.join(f'{sys.executable} {os.path.abspath(__file__)} run --port {port} --disc {d} --only {i}' for i, d in mine)
        log = open(os.path.join(BR, 'logs', f'pool-{port}.log'), 'a')
        procs.append(subprocess.Popen(['nice', '-n', '10', 'sh', '-c', cmd], stdout=log, stderr=subprocess.STDOUT))
    for p in procs: p.wait()


_RECRUIT = None


def played(sid, disc='orig'):
    """What a run did, from its raw trace: triggers set (and the recruits among them: T200+species, build/story-analysis/recruits.csv), battles, screens entered, money."""
    global _RECRUIT
    if _RECRUIT is None:          # a species flag that some other script reads (the city's recruit checks); the flags no script reads are the wild NPC's own `beaten` flags
        _RECRUIT = {int(r['trigger']): r['digimon'] for r in csv.DictReader(open(os.path.join(DATA, 'recruits.csv'))) if r['read_by'].strip()}
    trig = []; screens = []; battles = 0; money = 0
    for l in open(trace_file(sid, disc)):
        w = l.split()
        if not w: continue
        if w[0] == 'B': battles += 1
        elif w[0] == 'W' and w[2] == 'script_saved' and 245 <= int(w[3]) < 345:
            o, n = int(w[4], 16), int(w[5], 16)
            trig += [(int(w[3]) - 245) * 8 + b for b in range(8) if n >> b & 1 and not o >> b & 1]
        elif w[0] == 'W' and w[2] == 'screen' and w[3] == '0': screens.append(int(w[5], 16))
        elif w[0] == 'W' and w[2] == 'money': money += 1
    rec = [_RECRUIT[t] for t in trig if t in _RECRUIT]
    return dict(triggers=trig, recruits=rec, battles=battles, screens=screens, money_changes=money)


QUEUE = os.path.join(BR, 'queue')


def cmd_queue(a):
    """queue ID:DISC,...: jobs for the workers (a file each in build/checkpoints/branch/queue; a job whose row exists is not queued)."""
    os.makedirs(QUEUE, exist_ok=True); n = 0
    for k, j in enumerate(x for x in a.jobs.split(',') if x):
        if os.path.exists(rows_file(*j.split(':'))): continue
        open(os.path.join(QUEUE, f'{time.time():.3f}-{k:03d}-{j.replace(":", "@")}'), 'w').close(); n += 1
    print(n, 'queued')


def cmd_worker(a):
    """worker --port N: takes the next job of the queue (an atomic rename: two workers never take the same one) and runs it; stops when the queue is empty."""
    while True:
        jobs = sorted(f for f in os.listdir(QUEUE) if '@' in f and not f.endswith('.taken')) if os.path.isdir(QUEUE) else []
        if not jobs: break
        f = os.path.join(QUEUE, jobs[0])
        try: os.rename(f, f + '.taken')
        except OSError: continue
        sid, disc = jobs[0].split('-', 2)[2].split('@')
        subprocess.run([sys.executable, os.path.abspath(__file__), 'run', '--port', os.environ['EMU_PORT'], '--disc', disc, '--only', sid])


def cmd_table(a):
    path = os.path.join(DATA, 'checkpoints.csv'); old = list(csv.DictReader(open(path, newline=''))) if os.path.exists(path) else []
    ids = {x['id'] for x in SCEN}; keep = [r for r in old if r['checkpoint'] not in ids]
    cols = ['checkpoint', 'description', 'frames', 'instructions', 'orig', 'readable', 'reorder', 'mut1', 'battle', 'story_state']
    new = []
    for s in SCEN:
        o = load_row(s['run'], 'orig')
        if o is None: continue
        doc = s.get('doc') or find(s['run'])['doc']; p = played(s['run'])
        if s['kind'] == 'side':
            doc = f'{s["run"]}: {doc}; {p["battles"]} battles' + (f'; recruits {", ".join(p["recruits"])}' if p['recruits'] else '') + (f'; {s["note"]}' if s.get('note') else '')
        nsec = len(trace_sections(trace_file(s['run'], 'orig')))
        d = dict(checkpoint=s['id'], description=doc, frames=o['frames'], instructions=o['n'], orig=f'ends {o["end"]}' + (f' ({o["hang_at"]})' if o.get('hang_at') else ''),
                 battle=', '.join(b.split(' battle ')[1].split(' enemies')[0] for b in o.get('battles', [])) if s['kind'] == 'loss' else f'{p["battles"]} won',
                 story_state=('ends in screen %s, p1=%s; %d sections entered' % (o['story']['screen'], o['story']['p1'], nsec)) if o.get('story') else f'{nsec} sections entered')
        for disc in ('readable', 'reorder', 'mut1'):
            v = verdict(s['run'], disc); d[disc] = '' if v is None else f'strict {v["strict"]}, normalized {v["compare"]}'
        new.append(d)
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for r in keep + new: w.writerow({k: r.get(k, '') for k in cols})
    print(path, len(keep), '+', len(new))


def cmd_select(a):
    """The side() lines: every candidate tour that adds a section (greedy order of `coverage --all`), numbered S01.. (paste them under SIDE)."""
    plan = plan_sections(); got = set().union(*route_coverage().values()) & plan
    for x in SCEN:
        if x['kind'] == 'loss' and os.path.exists(trace_file(x['id'], 'orig')): got |= trace_sections(trace_file(x['id'], 'orig')) & plan
    pool = {c['id']: trace_sections(trace_file(c['id'], 'orig')) & plan for c in CANDIDATES() if os.path.exists(trace_file(c['id'], 'orig'))}; n = 0
    while pool:
        k = max(pool, key=lambda x: (len(pool[x] - got), x)); new = pool.pop(k) - got
        if not new: break
        n += 1; got |= new; p = played(k)
        note = f'+{len(new)} sections' + (f', recruits {"/".join(p["recruits"])}' if p['recruits'] else '')
        print(f"side('S{n:02d}', {k!r}, {note!r})")


def cmd_plan(a):
    for s in SCEN:
        if s['kind'] == 'side': c = find(s['run']); print(f'{s["id"]:6} side  {s["run"]:12} start {c["start"]:8} {len(c["steps"]):4} steps  {c["doc"]}'); continue
        print(f'{s["id"]:6} {s["kind"]:5} start {s["start"]:16} {len(s["steps"]):4} steps  battle {s["battle"]}{" #%d" % s["lose_nth"] if s["lose_nth"] else ""}  {s["doc"]}')
    if a.candidates:
        for s in CANDIDATES(): print(f'{s["id"]:6} {s["kind"]:5} start {s["start"]:16} {len(s["steps"]):4} steps  {s["doc"]}')


# ---------------------------------------------------------------------------------------------------
# hangs: the sections of the sweep that are not compared

HANG_DIR = os.path.join(BR, 'hangs')


def hang_ids():
    rows = list(csv.DictReader(open(os.path.join(DATA, 'verification-sweep.csv'))))
    return [(f"{r['script']}:{r['section']}:{r['variant']}", r['status'], r['reason']) for r in rows if r['status'] in ('NOT-RUNNABLE', 'HANG')]


def cmd_hangs(a):
    k, m = (int(x) for x in a.part.split('/'))
    ids = [i for n, (i, _, _) in enumerate(hang_ids()) if n % m == k]
    d = os.path.join(HANG_DIR, f'p{k}'); os.makedirs(os.path.join(d, 'traces'), exist_ok=True)
    env = dict(os.environ, SWEEP_LEDGER=os.path.join(d, 'ledger.jsonl'), SWEEP_TRACES=os.path.join(d, 'traces'), SWEEP_PIN_RANDOM='1', EMU_PORT=os.environ['EMU_PORT'])
    for disc in ('orig', 'reorder', 'readable'):
        subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dws/testing/sweep.py'), 'run', '--disc', disc, '--force', '--only', ','.join(ids)], env=env, check=False)


def cmd_hangs_report(a):
    rows = []; main = collections.defaultdict(list)
    for r in W.ledger():
        if r.get('kind') == 'case' and not r.get('error') and not r.get('skipped'): main[(r['disc'], r['case'])].append(r)
    for i, status, reason in hang_ids():
        runs = {}; enters = {}
        for d in glob.glob(os.path.join(HANG_DIR, 'p*')):
            for l in open(os.path.join(d, 'ledger.jsonl')) if os.path.exists(os.path.join(d, 'ledger.jsonl')) else []:
                try: x = json.loads(l)
                except ValueError: continue
                if x.get('kind') == 'case' and x.get('case') == i and not x.get('error'): x['_dir'] = d; runs[x['disc']] = x
                if x.get('kind') == 'enter' and i.startswith('0:') and x.get('case') == i.split(':')[1] + ':0' and not x.get('error'): enters[(d, x['disc'])] = x
        for disc, x in runs.items():          # a MAPHEAD case copies its `enter` row without `hang_at`: take it from there
            if x.get('via') == 'enter' and not x.get('hang_at') and (x['_dir'], disc) in enters: x['hang_at'] = enters[(x['_dir'], disc)].get('hang_at')
        o = runs.get('orig'); out = dict(case=i, sweep_status=status, sweep_reason=reason[:90])
        m = [x for x in main.get(('orig', i), []) if x.get('digest')]
        out['orig_end'] = o and o.get('end'); out['orig_hang_at'] = o and o.get('hang_at'); out['orig_n'] = o and o.get('n')
        out['orig_again'] = '' if not (o and m) else ('same' if m[-1]['digest'] == o['digest'] else 'relaxed' if _rd(m[-1], None) == _rd(o, o['_dir']) else 'differs')
        for disc in ('reorder', 'readable'):
            r = runs.get(disc)
            if not (o and r): out[disc] = 'not run'; continue
            same_end = r.get('end') == o.get('end') and (r.get('hang_at') or '') == (o.get('hang_at') or '')
            eo, er = _ev(o, o['_dir']), _ev(r, r['_dir'])
            if o['digest'] == r['digest'] and same_end: v = 'same'
            elif same_end and eo is not None and er is not None and W.relaxed_events(eo) == W.relaxed_events(er): v = 'relaxed'
            elif same_end and eo is not None and er is not None and _prefix(W.relaxed_events(eo), W.relaxed_events(er)): v = 'relaxed (prefix)'
            else: v = 'DIFF'
            out[disc] = f'{v}: {r.get("end")} {r.get("hang_at") or ""} n={r.get("n")}'.strip()
        rows.append(out)
    cols = ['case', 'sweep_status', 'sweep_reason', 'orig_end', 'orig_hang_at', 'orig_n', 'orig_again', 'reorder', 'readable']
    path = os.path.join(DATA, 'unprovable.csv')
    with open(path, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); [w.writerow(r) for r in rows]
    c = collections.Counter((r['sweep_status'], r['reorder'].split(':')[0], r['readable'].split(':')[0]) for r in rows)
    print(path, len(rows)); [print(' ', n, k) for k, n in c.most_common()]


def _trace_of(row, d):
    base = os.path.join(d, 'traces') if d else W.TRACES
    if row.get('via') == 'enter': return os.path.join(base, 'enter-' + row['enter'].replace(':', '-') + f'.{row["disc"]}.trace')
    return os.path.join(base, row['case'].replace(':', '_') + f'.{row["disc"]}.trace')


def _ev(row, d):
    try:
        ev = T.parse_trace(open(_trace_of(row, d)).read(), W.scripts_of(row['disc']))
        return ev if T.digest(ev) == row['digest'] or row.get('via') == 'enter' else None
    except (OSError, ValueError, KeyError, IndexError): return None


def _rd(row, d):
    ev = _ev(row, d); return W.relaxed_digest(ev) if ev is not None else None


def _prefix(x, y):
    ia = [i for i, e in enumerate(x) if e.startswith('I ')]; ib = [i for i, e in enumerate(y) if e.startswith('I ')]; k = min(len(ia), len(ib))
    return k > 0 and x[:ia[k - 1] + 1] == y[:ib[k - 1] + 1]


# ---------------------------------------------------------------------------------------------------
# the side scenarios: every area tour that adds a section to the route and the losses, in the greedy order of `coverage --all` (written by `select`;
# the note is what it added when chosen, and the recruitments it played: a flag 200+species that the city's scripts read, set by the area's own script)

side('S01', 'V-IcSa2', '+35 sections')
side('S02', 'V-FiCi1', '+29 sections')
side('S03', 'V-ToMa1', '+27 sections, recruits WaruMonzaemon')
side('S04', 'V-FaTo1', '+26 sections')
side('S05', 'V-GrLoMa2', '+25 sections')
side('S06', 'V-GrCaToAr1', '+25 sections')
side('S07', 'V-GeSa2', '+24 sections')
side('S08', 'V-MiTr1', '+22 sections')
side('S09', 'V-GrLoMa3', '+22 sections')
side('S10', 'V-BeLa1', '+22 sections')
side('S11', 'V-BaDi1', '+22 sections')
side('S12', 'V-GeSa1', '+21 sections')
side('S13', 'V-Fr3', '+20 sections')
side('S14', 'V-Fr1', '+20 sections')
side('S15', 'V-NaFo1', '+19 sections')
side('S16', 'V-TrJu1', '+18 sections')
side('S17', 'V-FaTo2', '+17 sections, recruits Giromon')
side('S18', 'V-Fr2', '+15 sections')
side('S19', 'V-AnGlRe1', '+15 sections')
side('S20', 'V-LaCa1', '+14 sections, recruits Tokomon/Meramon')
side('S21', 'V-AnSpRe1', '+14 sections')
side('S22', 'V-TrMo1', '+13 sections, recruits Sukamon')
side('S23', 'V-IcSa1', '+13 sections')
side('S24', 'V-DrTu2nFl1', '+13 sections')
side('S25', 'V-MtInTo1', '+12 sections')
side('S26', 'V-UnLa1', '+11 sections, recruits Myotismon/SkullGreymon')
side('S27', 'V-MtIn1', '+11 sections')
side('S28', 'V-MiTr2', '+11 sections, recruits Gabumon')
side('S29', 'V-GrLoMa1', '+11 sections')
side('S30', 'V-PaThMtPa1', '+10 sections')
side('S31', 'V-JiHo1', '+10 sections')
side('S32', 'V-GrLoMa4', '+10 sections')
side('S33', 'V-GeSa3', '+10 sections')
side('S34', 'V-DrTu1', '+10 sections')
side('S35', 'V-ArLo1', '+10 sections')
side('S36', 'V-MaRe1', '+9 sections')
side('S37', 'V-GrCa1', '+9 sections, recruits Birdramon')
side('S38', 'V-NaFo2', '+8 sections')
side('S39', 'V-MtPaSpAr1', '+8 sections')
side('S40', 'V-VoVi1', '+7 sections')
side('S41', 'V-Se1', '+7 sections')
side('S42', 'V-Re1', '+7 sections')
side('S43', 'V-LeAnCa1', '+7 sections')
side('S44', 'V-GrCaBoAr1', '+7 sections')
side('S45', 'V-GeSw1', '+7 sections')
side('S46', 'V-Fr4', '+7 sections')
side('S47', 'V-FoOfMtPa1', '+7 sections')
side('S48', 'V-DrEyLa1', '+7 sections')
side('S49', 'V-DiBr1', '+7 sections')
side('S50', 'V-UnPo1', '+6 sections')
side('S51', 'V-SeBeCa1', '+6 sections')
side('S52', 'V-RoHo1', '+6 sections')
side('S53', 'V-MoSh1', '+6 sections')
side('S54', 'V-GrGy1', '+6 sections')
side('S55', 'V-FaTo3', '+6 sections')
side('S56', 'V-OgFo1', '+5 sections')
side('S57', 'V-MtPaPl1', '+5 sections')
side('S58', 'V-LaCa2', '+5 sections')
side('S59', 'V-ItKe1', '+5 sections')
side('S60', 'V-DrTuEn1', '+5 sections')
side('S61', 'V-CeCl1', '+5 sections')
side('S62', 'V-OvCe1', '+4 sections')
side('S63', 'V-Ov1', '+4 sections')
side('S64', 'V-MtIn2', '+4 sections')
side('S65', 'V-ItSh1', '+4 sections')
side('S66', 'V-GrCaEn1', '+4 sections')
side('S67', 'V-GrCaBr1', '+4 sections')
side('S68', 'V-DiCu1', '+4 sections')
side('S69', 'V-CoHo1', '+4 sections')
side('S70', 'V-BiTr1', '+4 sections')
side('S71', 'V-AmFo1', '+4 sections')
side('S72', 'V-TrHu1', '+3 sections')
side('S73', 'V-ReAr1', '+3 sections')
side('S74', 'V-KuBe1', '+3 sections')
side('S75', 'V-CoPo1', '+3 sections')
side('S76', 'V-AnDiRe1', '+3 sections')
side('S77', 'V-ToTo1', '+2 sections')
side('S78', 'V-OgFo2', '+2 sections')
side('S79', 'V-ToMa2', '+1 sections, recruits WaruMonzaemon')
side('S80', 'V-SeItSh1', '+1 sections')
side('S81', 'V-MtInTo2', '+1 sections')
side('S82', 'V-MaBa1', '+1 sections')
side('S83', 'V-FoEn1', '+1 sections')
side('S84', 'V-DrTu3rFl1', '+1 sections')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('plan'); p.add_argument('--candidates', action='store_true'); p.set_defaults(f=cmd_plan)
    p = sub.add_parser('run'); p.add_argument('--disc', default='orig'); p.add_argument('--only', required=True); p.add_argument('--redo', action='store_true'); p.add_argument('--port'); p.set_defaults(f=cmd_run)
    p = sub.add_parser('queue'); p.add_argument('jobs'); p.set_defaults(f=cmd_queue)
    p = sub.add_parser('worker'); p.add_argument('--port'); p.set_defaults(f=cmd_worker)
    p = sub.add_parser('pool'); p.add_argument('--ports', required=True); p.add_argument('--jobs', required=True); p.set_defaults(f=cmd_pool)
    sub.add_parser('selftest').set_defaults(f=cmd_selftest); sub.add_parser('select').set_defaults(f=cmd_select); sub.add_parser('compare').set_defaults(f=cmd_compare); sub.add_parser('table').set_defaults(f=cmd_table)
    p = sub.add_parser('coverage'); p.add_argument('--candidates', action='store_true'); p.add_argument('--all', action='store_true'); p.add_argument('--top', type=int, default=60); p.set_defaults(f=cmd_coverage)
    p = sub.add_parser('hangs'); p.add_argument('--port'); p.add_argument('--part', required=True); p.set_defaults(f=cmd_hangs)
    sub.add_parser('hangs-report').set_defaults(f=cmd_hangs_report)
    a = ap.parse_args(); a.f(a)


if __name__ == '__main__':
    main()
