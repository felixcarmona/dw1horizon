#!/usr/bin/env python3
"""The verification campaign: the section sweep (docs/developing.md, "The campaign").

Runs every section of the story scripts of a disc in the emulator, in a state that satisfies what the section needs, with the
tracer of story_test.py, and compares the traces of the original disc with those of a rebuilt disc (code moved inside the scripts).

  tools/dws/testing/sweep.py plan                         the cases (script, section, screen, state variant) -> build/sweep/plan.json
  tools/dws/testing/sweep.py run --disc orig [--scripts 2,3] [--limit N] [--variants]
                                             runs the pending cases on a disc (resumable: every run is appended to
                                             build/sweep/ledger.jsonl); --variants also runs the generated state variants
  tools/dws/testing/sweep.py explore --disc orig          reads the traces of the baseline runs and generates state variants for the
                                             IF branches that were not taken (the state generator)
  tools/dws/testing/sweep.py report                       ledger -> docs/data/story-analysis/verification-sweep.csv and the numbers
  tools/dws/testing/sweep.py discs                        builds the discs `readable` (the beautifier's scripts, recompiled) and `reorder`
  tools/dws/testing/sweep.py classify                     re-reads the ledger and lists every FAIL with its first difference
  tools/dws/testing/sweep.py start [--disc D] [--order main-first|plain]
                                             the campaign as a supervised background service (detached, nice 10): baseline on
                                             orig, then the comparison discs, main route first (see "The service" below)
  tools/dws/testing/sweep.py stop | status [--short]      graceful stop (SIGTERM) | one-screen summary (one line with --short)
  tools/dws/testing/sweep.py cleanup                      deletes the saved states of the screens that are finished on every disc

A case is one section called with `callScriptSection(script, section, 1)` (the engine entry for a talk or a tile) from a saved
state of the screen that loads the script (`warp` on the original disc, saved once, loaded on every disc); the RNGs and the
clock are pinned at the call. One emulator at a time (EMU_PORT=38020).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import argparse, collections, fcntl, hashlib, json, os, re, signal, struct, subprocess, sys, threading, time

os.environ.setdefault('EMU_PORT', '38020')          # the sweep's own emulator; set before dwstest/emu are imported

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from tools.dev import story_test as T; from dws import bytecode

SW = os.path.join(ROOT, 'build/sweep')
PLAN = os.path.join(SW, 'plan.json')
LEDGER = os.environ.get('SWEEP_LEDGER') or os.path.join(SW, 'ledger.jsonl')      # SWEEP_LEDGER / SWEEP_TRACES: the determinism bench writes elsewhere
TRACES = os.environ.get('SWEEP_TRACES') or os.path.join(SW, 'traces')
WORKER = None             # the port of this worker process (tag of its ledger rows)
CSV = os.path.join(ROOT, 'build/story-analysis/verification-sweep.csv')
IDLE_FRAMES = 240         # no traced event for 4 s of game time after the first instruction: the case ends 'idle' (deterministic, counted in frames)
MAX_INS = 4000            # traced instructions per case: a section that loops all run long is cut here, the same way on every disc
MAX_FRAMES = 1500          # traced frames per case (25 s of game time)
ALIAS = {'orig2': 'orig'}   # a second run of the original disc: the flake rate of the harness
BIOS_SEED = 0x8464         # OpenBIOS keeps the rand() seed here (found by diffing low RAM around a call of the BIOS rand)
RUN_UNPLACED = not os.environ.get('SWEEP_SKIP_UNPLACED')      # a section whose NPC no state places is run without it (`unplaced` in the row) instead of skipped
DEFAULT_SCREEN = 218       # the start state: Jijimon's house
RNG = (0x1234567, 0x2345678, 0x3456789)    # BIOS seed, customRandom VAL1, VAL2 pinned at the call


# ---------------------------------------------------------------------------------------------------
# the plan: which section runs where

def maphead_screens():
    """script id -> [screen ids] from the SET_SCRIPT of MAPHEAD."""
    d = T.load_discs()['orig']; sc = T.Scripts(d['dg'], d['maphead']); b = sc.raw[0]; out = {}
    cur = None
    # decode MAPHEAD sections: SET_SCRIPT is opcode with fields '_ s M'? use the text disassembly kept by dwstest's sibling tools
    txt = os.path.join(ROOT, 'build/scn-dis/script_000.scn.txt')
    if not os.path.exists(txt):
        sys.exit('build/scn-dis is missing: python3 tools/dws/bytecode/__main__.py dis extracted/SCN/DG.SCN build/scn-dis')
    for l in open(txt, encoding='utf-8'):
        m = re.match(r'sec(\d+):', l)
        if m: cur = int(m.group(1))
        m = re.match(r'\s+SET_SCRIPT (\d+), (\d+)', l)
        if m and cur is not None: out.setdefault(int(m.group(1)), []).append(int(m.group(2)))
    return out


# Cases written by hand: a section run in a state the generator does not make. Each takes a branch no plain case takes
# (a deliberately broken build that changed Kunemon's food test was caught only by dwstest's give-meat scenario).
EXTRA_CASES = [
    dict(id='2:6:food', script=2, section=6, variant=0, setup={'items': [[38, 2]]}, library=False,
         doc="Kunemon's bed: the tamer has Meat (item 38): yes, the item menu picks it, the food test holds, the battle",
         steps=['talk until ACTIVE_INSTRUCTION==16 max 1500', 'wait 40', 'press CROSS 3', 'until ACTIVE_INSTRUCTION==100 max 300',
                'wait 40', 'press CROSS 3', 'wait 40', 'press CROSS 3']),     # (as dwstest's kunemon-give-meat: `talk` does not drive the item menu)
]


def extra_cases(ms=None):
    ms = ms or maphead_screens()
    return [dict(c, screen=sorted(ms.get(c['script'], [DEFAULT_SCREEN]))[0]) for c in EXTRA_CASES]


def build_plan():
    d = T.load_discs()['orig']; sc = T.Scripts(d['dg'], d['maphead']); ms = maphead_screens()
    cases = []
    for sid in sorted(sc.raw):
        secs = sorted(set(s for _, s in sc.sections(sid)))
        scr = sorted(ms.get(sid, [])) if sid else []
        for sec in secs:
            if sid == 0:
                # a MAPHEAD section is a screen's setup: run it in that screen (sections above 254 are entry points of the C code)
                screen = sec if sec <= 254 else DEFAULT_SCREEN
            else:
                screen = scr[0] if scr else DEFAULT_SCREEN
            cases.append(dict(id=f'{sid}:{sec}:0', script=sid, section=sec, screen=screen, variant=0, setup={},
                              library=(sid != 0 and not scr)))
    cases += extra_cases(ms)
    os.makedirs(SW, exist_ok=True); json.dump(dict(cases=cases), open(PLAN, 'w'), indent=0)
    return cases


def load_plan():
    if not os.path.exists(PLAN): build_plan()
    cases = json.load(open(PLAN))['cases']
    have = {c['id'] for c in cases}
    return cases + [c for c in extra_cases() if c['id'] not in have]          # (a plan made before a hand-written case was added)


# ---------------------------------------------------------------------------------------------------
# static analysis of the disassembly (build/scn-dis): which entities a section needs, which states place them

DIS = os.path.join(ROOT, 'build/scn-dis')
FIELDS = {name: [f for f in spec.split() if f != '_'] for name, spec in bytecode.OPS.values()}
OPNAME = {'SET_SELECTION', 'SWITCH', 'IF', 'SHOW_TEXTBOX', 'DATA'}


class Txt:
    """One script of build/scn-dis as a list of instructions with labels, and the instructions of each section."""

    def __init__(self, sid):
        self.sid = sid; self.items = []; self.sec_label = {}; self.label_at = {}
        path = os.path.join(DIS, f'script_{sid:03d}.scn.txt')
        for l in open(path, encoding='utf-8'):
            l = l.rstrip('\n')
            m = re.match(r'\.section\s+(\d+)\s+(\S+)', l)
            if m: self.sec_label[int(m.group(1))] = m.group(2); continue
            m = re.match(r'(\w+):', l)
            if m: self.label_at[m.group(1)] = len(self.items); self.items.append(('L', m.group(1))); continue
            m = re.match(r'    ([A-Z][A-Z0-9_]*)(?:\s+(.*?))?\s*(?:;\s*0x[0-9a-f]+.*)?$', l)
            if m and not l.startswith('     '):
                mn, ops = m.group(1), (m.group(2) or '')
                ops = re.sub(r';\s*0x[0-9a-f]+.*$', '', ops).strip()
                self.items.append(('I', mn, ops))
        order = sorted(self.sec_label.items(), key=lambda kv: self.label_at.get(kv[1], 1 << 30))
        self.bounds = {}
        starts = sorted(set(self.label_at[lab] for _, lab in order if lab in self.label_at))
        for sec, lab in order:
            if lab not in self.label_at: continue
            a = self.label_at[lab]; b = next((x for x in starts if x > a), len(self.items)); self.bounds[sec] = (a, b)

    def section(self, sec):
        a, b = self.bounds[sec]; return self.items[a:b]


_TXT = {}


def txt(sid):
    if sid not in _TXT: _TXT[sid] = Txt(sid)
    return _TXT[sid]


def needs(sid, sec):
    """NPC entity numbers (scriptId 5..0xC7) the instructions of a section name: the engine finds an entity with
    scriptIdToEntityId, and an absent one reads ENTITY_TABLE[0xFF]: the game hangs (observed in getSpeakerName)."""
    out = set()
    try: items = txt(sid).section(sec)
    except KeyError: return out
    for it in items:
        if it[0] != 'I' or it[1] in OPNAME: continue
        fl = FIELDS.get(it[1]);
        if not fl: continue
        ops = [o.strip() for o in it[2].split(',')]
        for f, o in zip(fl, ops):
            if f == 'e' and o.isdigit() and 5 <= int(o) < 0xC8: out.add(int(o))
    return out


ATOM = re.compile(r'(?:(and|or)\s+)?(not\s+)?(?:(trigger)\s+(\d+)|(cond)\s+(\d+)|p(\d+)\s*(==|!=|>=|<=|>|<)\s*(\d+)|(money)\s*(==|!=|>=|<=|>|<)\s*(\d+)|(item|stat|card|move)\s+(\d+)\s*(==|!=|>=|<=|>|<)\s*(\d+))$')


def parse_if(ops):
    """'trigger 3, and p107 >= 7, else L4' -> ([(joiner, atom)], label); atom = ('t', n, positive) | ('p', n, op, v) | ('?', text)."""
    parts = [x.strip() for x in ops.split(', ')]
    lab = None
    if parts and parts[-1].startswith('else '): lab = parts.pop()[5:].strip()
    atoms = []
    for x in parts:
        m = ATOM.match(x)
        if not m: atoms.append((None, ('?', x))); continue
        j = m.group(1); neg = bool(m.group(2))
        if m.group(3): atoms.append((j, ('t', int(m.group(4)), not neg)))
        elif m.group(7) is not None:
            atoms.append((j, ('p', int(m.group(7)), m.group(8), int(m.group(9)))))
        else: atoms.append((j, ('?', x)))
    return atoms, lab


def pmask(op, v):
    """The set of u8 values satisfying `pN op v` as a bit mask."""
    m = 0
    for x in range(256):
        if {'==': x == v, '!=': x != v, '>=': x >= v, '<=': x <= v, '>': x > v, '<': x < v}[op]: m |= 1 << x
    return m


FULL = (1 << 256) - 1


def mh_paths(screen, limit=400, sid=0):
    """Symbolic run of MAPHEAD section `screen`: every path through its IFs with the constraints on triggers and pstats that
    take it, and the NPC scriptIds it places (SET_DIGIMON slot + 5). -> [dict(cons, placed, free)]"""
    t = txt(sid)
    if screen not in t.bounds: return []
    a, b = t.bounds[screen]; items = t.items; res = []

    def run(pc, trig, pst, known, placed, free, steps, derived=None):
        derived = derived or {}
        while True:
            if len(res) >= limit or steps > 3000: return
            steps += 1
            if pc >= len(items) or pc >= b + 400: break
            it = items[pc]
            if it[0] == 'L': pc += 1; continue
            mn, ops = it[1], it[2]
            if mn in ('END_SECTION', 'END_SCRIPT', 'JUMP_RETURN', 'JUMP_TO_FILE'): break
            if mn == 'JUMP_TO': pc = t.label_at[ops.strip()]; continue
            if mn == 'SET_DIGIMON':
                f = [x.strip() for x in ops.split(',')]
                if len(f) >= 2 and f[1].isdigit(): placed = placed | {5 + int(f[1])}
            elif mn == 'SET_TRIGGER': trig = dict(trig); trig[int(ops)] = True; trig.setdefault(('set', int(ops)), True)
            elif mn == 'UNSET_TRIGGER': trig = dict(trig); trig[int(ops)] = False
            elif mn == 'SET_PSTAT':
                m = re.match(r'p(\d+),\s*(\d+)', ops)
                if m:
                    known = dict(known); known[int(m.group(1))] = int(m.group(2))
                    if int(m.group(1)) in derived: derived = {k: v for k, v in derived.items() if k != int(m.group(1))}
            elif mn in ('ADD_TO_PSTAT', 'REDUCE_PSTAT', 'STORE_RANDOM', 'STORE_DATE', 'COPY_PSTAT', 'STORE_MAP_ID', 'STORE_DIGIMON_TYPE', 'STORE_DIGIMON_VALUE'):
                known = dict(known)
                for q in re.findall(r'p(\d+)', ops): known.pop(int(q), None)
                if mn == 'STORE_RANDOM':
                    derived = dict(derived); derived[int(re.findall(r'p(\d+)', ops)[0])] = 'rand'
                if mn == 'STORE_DATE':
                    base = int(re.findall(r'p(\d+)', ops)[0]); derived = dict(derived)
                    for k, nm in enumerate(('year', 'day', 'hour', 'minute')): derived[base + k] = nm
            elif mn == 'IF':
                if steps > 400: return          # a loop: stop unrolling
                atoms, lab = parse_if(ops)
                # fork over the truth value of each undetermined atom
                def atom_val(at, tr, ps, kn):
                    if at[0] == 't':
                        n = at[1]
                        if n in tr and not isinstance(n, tuple): v = tr[n]; return v == at[2]
                        return None
                    if at[0] == 'p':
                        n = at[1]
                        if n in kn and n not in derived: return bool(pmask(at[2], at[3]) >> kn[n] & 1)
                        return None
                    return None
                def fork(i, tr, ps, res_so_far, free_):
                    if i == len(atoms):
                        yield tr, ps, res_so_far, free_; return
                    j, at = atoms[i]
                    v = atom_val(at, tr, ps, known)
                    choices = []
                    if v is not None: choices = [(v, tr, ps, free_)]
                    elif at[0] == 't':
                        n = at[1]
                        for want in (True, False):
                            tr2 = dict(tr); tr2[n] = want == at[2]       # atom true <=> trigger == positive
                            choices.append((want, tr2, ps, free_))
                    elif at[0] == 'p':
                        n = ('c', derived[at[1]]) if at[1] in derived else at[1]
                        cur = ps.get(n, FULL); mk = pmask(at[2], at[3])
                        for want in (True, False):
                            nm = cur & (mk if want else ~mk & FULL)
                            if nm: ps2 = dict(ps); ps2[n] = nm; choices.append((want, tr, ps2, free_))
                    else:
                        choices = [(True, tr, ps, True), (False, tr, ps, True)]
                    for want, tr2, ps2, fr in choices:
                        r = want if res_so_far is None else ((res_so_far and want) if j == 'and' else (res_so_far or want))
                        yield from fork(i + 1, tr2, ps2, r, fr)
                outs = list(fork(0, trig, pst, None, free))
                seen = set()
                for tr2, ps2, r, fr in outs:
                    key = (r, tuple(sorted((k, v) for k, v in tr2.items() if not isinstance(k, tuple))), tuple(sorted(ps2.items(), key=repr)))
                    if key in seen: continue
                    seen.add(key)
                    npc = pc + 1 if r else t.label_at[lab]
                    run(npc, tr2, ps2, known, placed, fr, steps, derived)
                return
            pc += 1
        res.append(dict(trig={k: v for k, v in trig.items() if not isinstance(k, tuple)}, pst=pst, placed=placed, free=free))

    run(a, {}, {}, {}, frozenset(), False, 0, {})
    return res


def solve_setup(path):
    """Constraints of a path -> a setup dict (triggers, pstats) that takes it."""
    st = {'triggers': {n: int(v) for n, v in path['trig'].items()}, 'pstats': {}}
    for n, m in path['pst'].items():
        if m == FULL: continue
        vals = [x for x in range(256) if m >> x & 1]; v = vals[len(vals) // 2] if vals[len(vals) // 2] - vals[0] < 100 else vals[0]
        if isinstance(n, tuple) and n[1] == 'rand': continue      # drawn by STORE_RANDOM: no state sets it
        if isinstance(n, tuple): st[n[1]] = v          # the pstat was written by STORE_DATE: it is the clock (hour, minute, day, year)
        else: st['pstats'][n] = v
    return {k: v for k, v in st.items() if v or k == 'hour'}


def merge_paths(p, q):
    tr = dict(p['trig'])
    for k, v in q['trig'].items():
        if k in tr and tr[k] != v: return None
        tr[k] = v
    ps = dict(p['pst'])
    for k, m in q['pst'].items():
        ps[k] = ps.get(k, FULL) & m
        if not ps[k]: return None
    return dict(trig=tr, pst=ps, placed=p['placed'] | q['placed'], free=p['free'] or q['free'])


def screen_scripts(screen):
    return [s_ for s_, scr in maphead_screens().items() if screen in scr]


def placing_variants(screen):
    try: return _placing_variants(screen)
    except RecursionError: return {}


def _placing_variants(screen):
    """{frozenset(placed scriptIds): (setup, free)}: the cheapest setup (fewest constraints) for each distinct set of NPCs placed by
    MAPHEAD section `screen` followed by the screen script's load section 254."""
    paths = mh_paths(screen)
    for s_ in screen_scripts(screen):
        q = mh_paths(254, sid=s_)
        if q:
            paths = [m for a in paths for b in q for m in [merge_paths(a, b)] if m]
            break
    best = {}
    for p in paths:
        k = p['placed']; cost = len(p['trig']) + len([1 for m in p['pst'].values() if m != FULL])
        if k not in best or cost < best[k][0]: best[k] = (cost, solve_setup(p), p['free'] or any(isinstance(x, tuple) and x[1] == 'rand' for x in p['pst']))
    return {k: (v[1], v[2]) for k, v in best.items()}


# ---------------------------------------------------------------------------------------------------
# discs with code moved inside the scripts

TERMINATORS = {'END_SECTION', 'END_SCRIPT', 'JUMP_TO', 'JUMP_RETURN', 'JUMP_TO_FILE', 'SWITCH', 'SWITCH_W'}


def chunks_of(lines):
    """Splits the text of a script at its section labels. -> (header lines, [chunk lines])"""
    labs = set(m.group(1) for l in lines for m in [re.match(r'\.section\s+\d+\s+(\S+)', l)] if m)
    first = next((i for i, l in enumerate(lines) if re.match(r'(\w+):', l) and re.match(r'(\w+):', l).group(1) in labs), None)
    if first is None: return lines, []
    head = lines[:first]; ch = []; cur = []
    for l in lines[first:]:
        m = re.match(r'(\w+):', l)
        if m and m.group(1) in labs and cur: ch.append(cur); cur = []
        cur.append(l)
    ch.append(cur)
    return head, ch


def last_mnemonic(chunk):
    for l in reversed(chunk):
        m = re.match(r'    ([A-Z][A-Z0-9_]*)\b', l)
        if m and not l.startswith('     '): return m.group(1)
    return None


def permute_text(text, seed):
    """Code moved inside a script: the chunks that start at a section label and end in a terminator are put in another order
    (a chunk that falls through stays glued to its successor, the last one stays last). Labels are symbolic, so the assembler
    gives every instruction a new offset."""
    import random
    lines = text.split('\n'); head, ch = chunks_of(lines)
    if len(ch) < 3: return text, 0
    units = []; cur = []
    for c in ch:
        cur += c
        if last_mnemonic(c) in TERMINATORS: units.append(cur); cur = []
    if cur: units.append(cur)                                     # a tail that does not end in a terminator: stays last
    fixed = [units.pop()] if cur else []
    rng = random.Random(seed); order = list(range(len(units))); rng.shuffle(order)
    moved = sum(1 for i, o in enumerate(order) if i != o)
    out = head + [l for o in order for l in units[o]] + [l for u in fixed for l in u]
    return '\n'.join(out), moved


def build_reorder(name='reorder', seed=8):
    """Every script (and MAPHEAD) with its chunks shuffled: DG.SCN and MAPHEAD.SCN with other offsets everywhere."""
    import shutil, subprocess
    d = os.path.join(SW, name + '-dis'); shutil.rmtree(d, ignore_errors=True); shutil.copytree(DIS, d)
    moved = 0
    for sid in range(1, 222):
        pth = os.path.join(d, f'script_{sid:03d}.scn.txt'); t = open(pth, encoding='utf-8').read()
        t2, mv = permute_text(t, seed * 1000 + sid); moved += mv
        open(pth, 'w', encoding='utf-8').write(t2)
    mh = os.path.join(SW, name + '-maphead.scn.txt')
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dws/bytecode/__main__.py'), 'dis', os.path.join(ROOT, 'extracted/SCN/MAPHEAD.SCN'), os.path.join(SW, name + '-mh')],
                   check=True, stdout=subprocess.DEVNULL)
    src = os.path.join(SW, name + '-mh', 'maphead.scn.txt'); t = open(src, encoding='utf-8').read(); t2, mv = permute_text(t, seed * 1000); moved += mv
    open(mh, 'w', encoding='utf-8').write(t2)
    dg = os.path.join(SW, name + '-DG.SCN'); mhb = os.path.join(SW, name + '-MAPHEAD.SCN')
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dws/bytecode/__main__.py'), 'asm', d, dg, '--compact'], check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dws/bytecode/__main__.py'), 'asm', mh, mhb], check=True, stdout=subprocess.DEVNULL)
    T.build_disc(name, dg, mhb)
    return moved


def label_refs(lines):
    """Labels named by the instructions of a block of text."""
    refs = set()
    for l in lines:
        if l.startswith('    ') and not l.startswith('     '):
            body = re.sub(r';\s*0x[0-9a-f]+.*$', '', l[4:])
            refs.update(re.findall(r'\b(L\d+|sec\d+|q_\w+|u\d+_\w+|dws_\w+)\b', body))
    return refs


def splice_events(lines, events, genf):
    """Replaces, in the disassembly text `lines`, the body of each section that has a generated event, where nothing jumps into
    that body from another chunk. -> (lines, spliced, kept)"""
    head, ch = chunks_of(lines); spliced = kept = 0
    labs = {m.group(2): int(m.group(1)) for l in lines for m in [re.match(r'\.section\s+(\d+)\s+(\S+)', l)] if m}
    chunk_of = {}
    for i, c in enumerate(ch):
        m = re.match(r'(\w+):', c[0])
        if m: chunk_of.setdefault(labs.get(m.group(1)), i)
    defs = [set(re.match(r'(\w+):', l).group(1) for l in c if re.match(r'(\w+):', l)) for c in ch]
    for sec, rep, code, ents, path in events:
        if sec not in chunk_of or not rep: kept += 1; continue
        gen = genf(sec, rep, code, ents, path)
        if gen and gen[-1].strip() not in ('END_SECTION', 'END'): gen = gen + ['    END_SECTION']
        i = chunk_of[sec]; lab = re.match(r'(\w+):', ch[i][0]).group(1); inner = defs[i] - {lab}
        outside = set(); others = set()
        for j, c in enumerate(ch):
            if j != i: outside |= label_refs(c); others |= defs[j]
        refs_new = label_refs(gen)
        if (inner & outside) or (refs_new & inner) or (refs_new & others) or any(r in labs and r != lab for r in refs_new):
            kept += 1; continue
        ch[i] = [f'{lab}:'] + gen + ['']; defs[i] = {lab}; spliced += 1
    return head + [l for c in ch for l in c], spliced, kept, ch


def build_readable(name='readable', src=None):
    """The readable disc is the story build without mods (since 2026-10-12, docs/mods/dws.md section 3): `dws story-build
    --mods none` makes story/base from this disc when it is stale (the beautifier, every event proven) and builds DG.SCN and
    MAPHEAD.SCN from it alone, every section included (the code sections share is a `shared` block of the script).
    src: another story/base folder (`dws story-base --base DIR`). -> (events spliced, sections that keep the disc's body)"""
    import shutil
    from dws import basebuild as BB
    out = os.path.join(SW, name + '-story', 'DG.SCN'); os.makedirs(os.path.dirname(out), exist_ok=True)
    base = os.path.join(ROOT, src) if src else BB.BASE
    prog, report, run, mh = BB.build([], out, mods=[], base=base, log=lambda m: print(m, file=sys.stderr))
    dg = os.path.join(SW, name + '-DG.SCN'); mhb = os.path.join(SW, name + '-MAPHEAD.SCN')
    shutil.copyfile(out, dg); shutil.copyfile(mh, mhb)
    T.build_disc(name, dg, mhb)
    m = next((re.search(r'MAPHEAD, (\d+) events, nothing of the disc kept', r) for r in report if 'generated from story/base' in r), None)
    return (int(m.group(1)) if m else 0), 0


# ---------------------------------------------------------------------------------------------------
# L1, static: the control-flow graph of a section is the same graph in another layout

NO_FALL = (0x15, 0x16, 0x17, 0xFE, 0xFF, 0x18, 0x93)


def cfg_signature(b, start, limit=20000):
    """Instruction graph reachable from `start`, numbered in discovery order: [(hash of the bytes with the label fields cleared,
    successors...)]. Two layouts of the same code give the same list."""
    ids = {start: 0}; order = [start]; sig = []; i = 0
    while i < len(order):
        p = order[i]; i += 1
        if p >= len(b) or len(order) > limit: sig.append(('end', ())); continue
        if b[p] == 0x12 and p + 1 < len(b) and b[p + 1] == 0: sig.append(('00', ())); continue
        n, tg = bytecode.instr_length(b, p)
        if n is None: sig.append(('?', ())); continue
        ins = bytearray(b[p:p + n])
        for pos in T.label_positions(bytes(ins), 0): ins[pos:pos + 2] = b'\0\0'
        succ = list(tg)
        if b[p] not in NO_FALL: succ.append(p + n)
        out = []
        for q in succ:
            if q not in ids: ids[q] = len(order); order.append(q)
            out.append(ids[q])
        sig.append((hashlib.sha1(bytes(ins)).hexdigest()[:10], tuple(out)))
    return sig


def first_offsets(raw):
    """section id -> offset, the first entry of the header wins (getScriptSection walks the header from the start: a later duplicate is dead)."""
    _, secs = bytecode.parse_header(raw); out = {}
    for s_, off in secs: out.setdefault(s_, off)
    return out


def static_l1(other_disc):
    """Compares every section of the original scripts with the same section of `other_disc` (CFG isomorphism). -> (equal, different list, moved)"""
    o = T.load_discs()['orig']; d = T.load_discs()[other_disc]
    A = T.Scripts(o['dg'], o['maphead']); B = T.Scripts(d['dg'], d['maphead']); same = 0; diff = []; moved = 0
    for sid in sorted(A.raw):
        if sid not in B.raw: continue
        sa = first_offsets(A.raw[sid]); sb = first_offsets(B.raw[sid])
        for sec, off in sa.items():
            if sec not in sb: diff.append((sid, sec, 'missing')); continue
            moved += off != sb[sec]
            if cfg_signature(A.raw[sid], off) == cfg_signature(B.raw[sid], sb[sec]): same += 1
            else: diff.append((sid, sec, 'graph differs'))
    return same, diff, moved


# ---------------------------------------------------------------------------------------------------
# ledger

def ledger():
    rows = []
    if os.path.exists(LEDGER):
        for l in open(LEDGER):
            l = l.strip()
            if l:
                try: rows.append(json.loads(l))
                except ValueError: pass          # a line cut by a power failure
    return rows


def append(row):
    """Append + flush + fsync under an exclusive lock: the workers share one ledger and no line is ever interleaved."""
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    row = dict(row, t=round(time.time(), 1))
    if WORKER: row['w'] = WORKER
    with open(LEDGER, 'ab+') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0, 2)
        if f.tell():
            f.seek(-1, 2)
            if f.read(1) != b'\n': f.write(b'\n')          # the last line was cut (kill -9, power): it stays a dead line, the new row starts clean
        f.write((json.dumps(row) + '\n').encode()); f.flush(); os.fsync(f.fileno())
        fcntl.flock(f, fcntl.LOCK_UN)


def done_set(disc, kind='case'):
    out = set()
    for r in ledger():
        if r.get('kind') == 'reset' and r['disc'] == disc: out.clear(); continue          # the results of the disc before a reset are void (an `enter` run too: the screen is entered again)
        if r['disc'] == disc and r.get('kind', 'case') == kind and not r.get('error'): out.add(r['case'])
    return out


# ---------------------------------------------------------------------------------------------------
# running

def lua_pokes(pairs):
    return [dict(t='poke', a=a, hex=h) for a, h in pairs]


def seed_pokes():
    return lua_pokes([(BIOS_SEED, struct.pack('<I', RNG[0]).hex()), (T.phys('CUSTOM_RNG_VAL1'), struct.pack('<I', RNG[1]).hex()),
                      (T.phys('CUSTOM_RNG_VAL2'), struct.pack('<I', RNG[2]).hex())])


def clock_steps(h=9, m=12):
    return T.parse_step('clock %d %d' % (h, m))['steps']


def case_steps(case, max_frames=MAX_FRAMES):
    steps = [T.parse_step('wait 20'), dict(t='trace', on=True)]
    steps += [s for s in clock_steps()]
    steps += seed_pokes()
    steps += [T.parse_step(f'call {case["script"]} {case["section"]} 1')] + [T.parse_step(x) for x in case.get('steps', [])]
    steps += [T.parse_step(f'talk until free max {max_frames}'),
              dict(t='mark', name='final'), dict(t='end')]
    return steps


def enter_steps(screen, setup=None):
    su = setup or {}
    steps = clock_steps(su.get('hour', 9), su.get('minute', 12)) + seed_pokes()
    if su.get('day') is not None: steps.append(dict(t='poke', a=T.phys('DAY'), hex=struct.pack('<h', su['day']).hex()))
    steps += [dict(t='trace', on=True), T.parse_step(f'warp {screen} 0'), T.parse_step(f'talk until screen=={screen} and free max 3000'),
              T.parse_step('wait 60'), dict(t='mark', name='final'), dict(t='end')]
    return steps


def state_path(screen):
    return os.path.join(SW, f'w-{screen}.state') if screen != DEFAULT_SCREEN else T.BOOT_STATE


CTL = None                  # the supervisor of the service (class Ctl below); None in the foreground commands


class Abandon(Exception):
    """SIGTERM arrived: the current case is given up (nothing is written to the ledger for it) and the service exits."""


def emu_alive():
    st = T.emu_mod().state()
    return bool(st and T.emu_mod().alive(st))


class Runner:
    def __init__(self, disc):
        self.disc = disc; self.d = T.load_discs()[ALIAS.get(disc, disc)]; self.sc = T.Scripts(self.d['dg'], self.d['maphead']); self.fresh = False
        T.ensure_boot()

    def emulator(self):
        T.start_emulator(self.d['cue'])

    def run(self, steps, start_state, out, setup=None, max_frames=2500, stop_on_battle=True, pre=None, save_state=None, hang_after=20, want_present=False, max_ins=MAX_INS, idle_frames=IDLE_FRAMES, extra=None):
        self.hang_at = None; hung = False; self.present = None
        """One run: load `start_state`, put the disc's scripts in RAM, apply `setup`, run `steps`, return the raw trace text."""
        self.emulator(); A = T.addresses(); out = os.path.abspath(out)
        T.pause(); T.load_state(start_state); T.sync_scripts(self.d)
        if setup: T.apply_setup(setup, self.d)
        if pre: pre()
        watch = [dict(name=n, addr=T.phys(e), len=ln, digest=dg) for n, e, ln, dg in T.WATCH]
        final = out; out = f'{final}.part{os.getpid()}'          # traced under another name and renamed when the run is over: an abandoned run (the service stopped, a kill) must not delete the trace of the
        S = dict(out=out, A=A, steps=steps, watch=watch, trace=False, max_frames=max_frames, stop_on_battle=stop_on_battle, max_ins=max_ins, idle_frames=idle_frames)
        if os.environ.get('SWEEP_PIN_RANDOM'):          # STORE_RANDOM draws from a generator set by the instruction count (story_trace.lua); `start` sets it for a new campaign
            S['pin'] = dict(bios=BIOS_SEED, v1=T.phys('CUSTOM_RNG_VAL1'), v2=T.phys('CUSTOM_RNG_VAL2'))
        if extra: S.update(extra)          # optional keys for story_trace.lua (tools/dws/testing/checkpoints.py: battle)
        S = {k: v for k, v in S.items() if v is not None}          # a Lua table has no None (idle_frames=None: no idle rule)
        if os.path.exists(out): os.remove(out)
        try: return self._run(out, final, S, steps, start_state, hang_after, want_present, save_state, max_frames, A)
        finally:
            if os.path.exists(out): os.remove(out)

    def _run(self, out, final, S, steps, start_state, hang_after, want_present, save_state, max_frames, A):
        hung = False
        r = T.lua_file(f'dofile("{T.LUA}")\nreturn DT.start({T.lua_value(S)})', 'start')
        if r != 'started': raise RuntimeError('lua: ' + r)
        T.resume(); t0 = time.time(); limit = (max_frames / T.FPS * 2.5 + 90) * host_slowdown(); last = (-1, time.time())
        if CTL: hang_after = max(hang_after, CTL.cap())
        while True:
            time.sleep(0.4)
            if CTL:
                CTL.beat(frame=last[0], case_secs=round(time.time() - t0))
                if CTL.stop: raise Abandon()
                if not emu_alive(): raise RuntimeError('the emulator died')
            st = T.lua_file('return tostring(DT.done) .. " " .. tostring(DT.pending_finish) .. " " .. tostring(DT.frame)', 'poll').split()
            if st[0] == 'true': break
            if st[1] != 'nil':
                T.lua_file(f'DT.finish("{st[1]}")', 'fin'); break
            fr = int(st[2])
            if fr != last[0]: last = (fr, time.time())
            elif time.time() - last[1] > hang_after:      # no gameLoop for that long: the game is stuck in a loop (or loads forever)
                pc = int(T.lua_file('return tostring(PCSX.getRegisters().pc)', 'pc').split('.')[0].replace('ULL', '') or 0); self.hang_at = symbol_at(pc)
                T.lua_file('DT.finish("hang")', 'fin'); hung = True; break
            if time.time() - t0 > limit:
                T.lua_file('DT.finish("host timeout")', 'fin'); time.sleep(1); break
        T.pause()
        text = open(out).read(); os.replace(out, final)
        battle = bool(re.search(r'^E \d+ battle', text, re.M))
        if want_present and not battle and not hung: self.present = present_ids()
        if save_state and not battle and not hung:
            import urllib.parse
            tmp = save_state + f'.part{os.getpid()}'          # saved under another name and renamed: a kill in the middle leaves no half state
            r = T.emu_mod().api('/api/v1/lua/save?file=' + urllib.parse.quote(tmp), timeout=120).decode()
            if not r.startswith('ok'): raise RuntimeError('save: ' + r)
            os.replace(tmp, save_state)
        if battle or hung: T.emu_mod().stop()          # a frozen battle leaves the CD busy: the next run needs a new process
        return text


def host_slowdown():
    """The host-time limit of a run is for an emulator that has a core: when the machine is loaded past its cores (20 emulators on 16) a run is
    slower by about that factor; a run that hits the limit anyway ends `host` (no result: retried, never compared)."""
    try: return min(4.0, max(1.0, os.getloadavg()[0] / (os.cpu_count() or 8)))
    except OSError: return 1.0


_SYMS = None


def symbol_at(pc):
    global _SYMS
    from tools.dev import symbols as dwsyms
    if _SYMS is None: _SYMS = sorted((a, n) for n, a in dwsyms.table('orig').items())
    import bisect
    pc &= 0xFFFFFFFF; k = bisect.bisect_right([a for a, _ in _SYMS], pc) - 1
    return f'{_SYMS[k][1]}+{pc - _SYMS[k][0]:#x}' if k >= 0 else hex(pc)


def analyse(text, sc, case=None):
    ev = T.parse_trace(text, sc)
    ins = [e for e in ev if e['kind'] == 'I']
    end = next((e['key'] for e in ev if e['kind'] == 'E'), '?').replace('E ', '')
    row = dict(end=end, n=len(ins), nev=len(ev), digest=T.digest(ev) if ev else '', rdigest=relaxed_digest(ev), rv=RV,
               frames=next((e['frame'] for e in ev if e['kind'] == 'E'), None))
    if case is not None:
        row['reached'] = bool(ins) and ins[0]['sid'] == case['script'] and first_section_matches(ins[0], case, sc)
    return ev, row


def first_section_matches(e, case, sc):
    secs = first_offsets(sc.raw[case['script']])
    return case['section'] in secs and e['rel'] == 0 and e['sec'] in [s for s, o in secs.items() if o == secs[case['section']]]


# ---------------------------------------------------------------------------------------------------
# the layout-free form: what the trace says when code was moved inside a script

LAYOUT_ONLY = (0x16, 0x19)     # JUMP_TO: moving code adds, removes or threads them (flowcmp: "jump threading is layout"); IF: a pure test (the engine's
                               # scriptIfInstruction reads, never writes): one test split over two IFs, or written negated with its branches swapped, is
                               # the same program (flowcmp, one node per clause); which way an IF went shows in the next instruction and the state


def script_sound(ev, n):
    """Is the `S bank id` event ev[n] the script's? The UI sounds of the text box (bank 0: open, advance, cancel) and the sound that a PLAY_SOUND
    instruction makes (the event right after it) are. The others (bank 1 and 3: a footstep or a breath every 5-6 frames of an entity's animation, `S 3 52`) come from
    timers that run all the time: two runs of the same section from the same state differ in their phase by a frame or two (found by the
    sweep: 72 `FLAKE-ORIG` cases of the original disc against itself, every one of them only in these sounds, none in an instruction, a state write or a text sound)."""
    e = ev[n]
    if e['key'].split()[1] == '0': return True
    p = ev[n - 1] if n else None
    return bool(p and p['kind'] == 'I' and p['op'] == 0x5A)


RULES = ('jump', 'owner', 'ambient', 'rand', 'dcheck')          # the relaxations of relaxed_events, each can be turned off (the audit: which of them a case needs)


def relaxed_events(ev, off=()):
    """The normalized trace (what `vs_<disc>` compares; the strict one is the trace as it is). Dropped, because moving code makes or removes
    them and the engine does nothing different: the position of every instruction and its branch targets, JUMP_TO, and a SET_DIALOG_OWNER
    to the owner already set (flowcmp's owner model), and IF (a pure test: which way it went shows in what runs next; since RV 5). Kept: every other instruction with its operands and text rows, in order,
    every state write, script sound (see script_sound), music and battle event, the checkpoints of money, merit, screen, inventory, partner and battles. A branch taken the wrong way shows in the next
    instruction or in them.
    Not compared, because the original disc differs from itself in them (the 72 `FLAKE-ORIG` cases): the phase of the entity timers (sounds, `script_sound`); the count of
    `rand()` draws (the entities' AI draws one a frame or so, so it moves with the frame phase; what a script does with a draw shows in the STORE_RANDOM result, the
    state write and the branch after it, which are compared); and the final checkpoint of `script_saved`/`script_session` (it holds the bytes of the START state that the
    case never wrote, and a state made again after a clean-up differs there; every write the case makes is a `W` event, and the last `diff()` runs before the checkpoint).
    The strict digest keeps all of them.
    One exception: what stands between two SHOW_TEXTBOX is kept as a `BREAK` token. The engine chains two SHOW_TEXTBOX in a row into ONE box
    whose pages go on with no close (showTextbox: the opcode after the text is SHOW_TEXTBOX), while any instruction between them (a JUMP_TO, a
    SET_DIALOG_OWNER, which sets the box up again) makes two boxes: a dropped JUMP_TO or SET_DIALOG_OWNER there is not layout (found by this
    sweep: 163:6:0, 164:5:0 on `readable`)."""
    out = []; first = None; owner = 0xFD; prev = None; brk = False          # callScriptSection starts with the tamer as the dialogue owner
    for n, e in enumerate(ev):
        k = e['kind']
        if k == 'E': continue
        if k == 'S' and 'ambient' not in off and not script_sound(ev, n): continue          # ambient sound of an entity's animation timer: its phase is not the script's
        if k == 'I':
            if first is None: first = e['rand']
            dropped = e['op'] in LAYOUT_ONLY and 'jump' not in off
            if e['op'] == 0x1B and len(e['raw']) > 1:        # SET_DIALOG_OWNER to the owner already set: flowcmp calls it redundant
                dropped = dropped or (e['raw'][1] == owner and 'owner' not in off)
                owner = e['raw'][1]
            if dropped:
                if prev == 0x1A: brk = True
                continue
            if e['op'] == 0x1A and brk: out.append('BREAK')
            brk = False; prev = e['op']
            key = re.sub(r'^I (\d+):\S+ ', r'I \1 ', e['key']); key = re.sub(r' ->.*$', '', key)
            out.append(key + (f' r={e["rand"] - first}' if 'rand' in off else ''))          # the count of rand() draws is not in it: see the docstring
        elif k in 'SM' and first is None: continue
        elif k == 'D' and 'dcheck' not in off and e['key'].split()[1] in ('script_saved', 'script_session'): continue          # the start state's bytes that the script never wrote (see the docstring)
        else: out.append(e['key'])
    return out


def relaxed_digest(ev, off=()):
    return hashlib.sha1('\n'.join(relaxed_events(ev, off)).encode()).hexdigest() if ev else ''


RV = 5             # the version of relaxed_events: 2 = SHOW_TEXTBOX chaining kept (BREAK), 3 = ambient sounds dropped, 4 = no draw count, no checkpoint of the script state, 5 = IF dropped like JUMP_TO. Rows record it as `rv`; older rows are recomputed from their trace
_RD = {}


def latest_enter_digest(disc, key):
    d = None
    for r in ledger():
        if r.get('kind') == 'enter' and r['disc'] == disc and r['case'] == key and not r.get('error'): d = r.get('digest')
    return d


def rdig(row):
    """The normalized digest of a ledger row, in the current definition: stored when the row has it, else recomputed from the saved trace (only if the
    trace is the one of that row: its strict digest equals the row's), else the stored one of the old definition."""
    if row.get('rv') == RV or not row.get('digest'): return row.get('rdigest')
    key = (row['disc'], row['case'], row['digest'])
    if key not in _RD:
        _RD[key] = row.get('rdigest')
        try:
            path = os.path.join(TRACES, 'enter-' + row['enter'].replace(':', '-') + f'.{row["disc"]}.trace') if row.get('via') == 'enter' else trace_path(row['case'], row['disc'])
            ev = T.parse_trace(open(path).read(), scripts_of(row['disc']))
            # an `enter` case row copies the enter row of its time, and a rerun that was killed after it wrote the trace (25 screens of File City, 0:165..0:203) left a trace that no row has: for
            # an enter case the trace on disk, the latest run of that screen on that disc, is what is compared
            if ev and (T.digest(ev) == row['digest'] or row.get('via') == 'enter'): _RD[key] = relaxed_digest(ev)
        except (OSError, ValueError, KeyError, IndexError): pass
    return _RD[key]


# ---------------------------------------------------------------------------------------------------
# the state generator: from the IFs a baseline trace executed, the states that take the other branch

SS_TRIG = 245          # SCRIPT_STATE offsets: trigger bits, then the pstats
SS_PSTAT = 345


def snap_name(screen, key): return os.path.join(SW, f'snap-{screen}-{key}.json')


def take_snapshot(path):
    """Loads a saved state and records what the IF conditions read: triggers, pstats, money, inventory."""
    T.pause(); T.load_state(path)
    ram = T.emu_mod().api('/api/v1/cpu/ram/raw'); ss = T.phys('SCRIPT_STATE')
    inv = T.phys('INVENTORY')
    return dict(trig=ram[ss + SS_TRIG:ss + SS_PSTAT].hex(), pstat=ram[ss + SS_PSTAT:ss + SS_PSTAT + 256].hex(),
                money=struct.unpack_from('<I', ram, T.phys('MONEY'))[0], inventory=ram[inv:inv + 0x5B].hex())


def cmd_snapshots(a):
    R = Runner('orig'); R.emulator(); n = 0
    names = [(os.path.basename(f)[2:-6], f) for f in sorted(os.listdir(SW)) if f.startswith('w-') and f.endswith('.state')
             for f in [os.path.join(SW, f)]]
    names.append(('218-0', T.BOOT_STATE))
    for nm, f in names:
        scr, _, key = nm.partition('-'); out = snap_name(scr, key or '0')
        if os.path.exists(out) and os.path.getmtime(out) > os.path.getmtime(f): continue
        json.dump(take_snapshot(f), open(out, 'w')); n += 1
    T.emu_mod().stop(); print(n, 'snapshots')


class State:
    """What the IFs read, replayed along a trace."""

    def __init__(self, snap):
        self.trig = bytearray(bytes.fromhex(snap['trig'])); self.pst = bytearray(bytes.fromhex(snap['pstat']))
        self.money = snap['money']; self.inv = bytes.fromhex(snap['inventory'])

    def apply_w(self, key):
        m = re.match(r'W (script_saved|script_session)\+(\d+) ([0-9a-f]{2})>([0-9a-f]{2})', key)
        if not m: return
        reg, off, new = m.group(1), int(m.group(2)), int(m.group(4), 16)
        off = off + (380 if reg == 'script_session' else 0)
        if SS_TRIG <= off < SS_PSTAT: self.trig[off - SS_TRIG] = new
        elif SS_PSTAT <= off < SS_PSTAT + 256: self.pst[off - SS_PSTAT] = new

    def tget(self, n): return bool(self.trig[n // 8] >> (n % 8) & 1)

    def tset(self, n, v):
        if v: self.trig[n // 8] |= 1 << (n % 8)
        else: self.trig[n // 8] &= ~(1 << (n % 8)) & 0xFF


def eval_atoms(atoms, get):
    """Left fold of the atoms (and/or), as scriptIfInstruction does; get(atom) -> bool or None (unknown)."""
    res = None
    for j, at in atoms:
        v = get(at)
        if v is None: return None
        res = v if res is None else ((res and v) if j == 'and' else (res or v))
    return res


def cmpv(op, x, v): return {'==': x == v, '!=': x != v, '>=': x >= v, '<=': x <= v, '>': x > v, '<': x < v}[op]


def solve_flip(atoms, st, want):
    """A change of triggers and pstats (the fewest) after which the IF evaluates to `want`. -> setup dict or None."""
    tvars = sorted({a[1] for _, a in atoms if a[0] == 't'}); pvars = sorted({a[1] for _, a in atoms if a[0] == 'p'})
    if any(a[0] == '?' for _, a in atoms): return None
    cands = {}
    for n in pvars:
        cs = {int(st.pst[n])}
        for _, a in atoms:
            if a[0] == 'p' and a[1] == n:
                for d in (-1, 0, 1):
                    if 0 <= a[3] + d <= 255: cs.add(a[3] + d)
        cands[('p', n)] = sorted(cs)
    for n in tvars: cands[('t', n)] = [0, 1]
    keys = list(cands); best = None
    import itertools
    cur = {k: (int(st.pst[k[1]]) if k[0] == 'p' else int(st.tget(k[1]))) for k in keys}
    if len(keys) > 7: return None
    for combo in itertools.product(*[cands[k] for k in keys]):
        asg = dict(zip(keys, combo))
        def get(a):
            if a[0] == 't': return (asg[('t', a[1])] == 1) == a[2]
            return cmpv(a[2], asg[('p', a[1])], a[3])
        if eval_atoms(atoms, get) == want:
            cost = sum(1 for k in keys if asg[k] != cur[k])
            if best is None or cost < best[0]: best = (cost, asg)
    if best is None or best[0] == 0: return None
    setup = {'triggers': {}, 'pstats': {}}
    for k, v in best[1].items():
        if v == cur[k]: continue
        (setup['triggers'] if k[0] == 't' else setup['pstats'])[k[1]] = v
    return {k: v for k, v in setup.items() if v}


def decode_if(raw):
    """Instruction bytes of an IF -> ([(joiner, atom)], else-label text) using the disassembler."""
    lines, _ = bytecode.dis_instr(raw, 0, len(raw), T._Labels())
    txt = lines[0]
    return parse_if(txt[3:].strip())


def if_events(ev, sc):
    """The IFs a trace executed: [(sid, sec, rel, atoms, taken_fallthrough, event index)]."""
    out = []; ins = [(i, e) for i, e in enumerate(ev) if e['kind'] == 'I']
    for k, (i, e) in enumerate(ins):
        if e['op'] != 0x19: continue
        nxt = ins[k + 1][1] if k + 1 < len(ins) else None
        if nxt is None or nxt['sid'] != e['sid']: continue
        try: atoms, lab = decode_if(e['raw'])
        except Exception: continue
        fell = nxt['sec'] == e['sec'] and nxt['rel'] == e['rel'] + len(e['raw'])
        out.append((e['sid'], e['sec'], e['rel'], atoms, fell, i))
    return out


def cmd_explore(a):
    """Reads the baseline traces of the original disc and writes variant cases (a state that takes an IF the other way) into the plan."""
    plan = json.load(open(PLAN))['cases']; have = {c['id'] for c in plan}; new = []; seen = collections.Counter()
    sc = scripts_of('orig'); rows = [r for r in ledger() if r['disc'] == 'orig' and r.get('kind', 'case') == 'case' and not r.get('error')]
    last = {r['case']: r for r in rows}
    cover = collections.defaultdict(set)         # (sid, sec, rel) -> {True, False} taken in any baseline run
    runs = {}
    for c in plan:
        if c['variant']: continue
        r = last.get(c['id'])
        if not r or r.get('via') or r.get('skipped') or r.get('n', 0) == 0: continue
        pth = trace_path(c['id'], 'orig')
        if not os.path.exists(pth): continue
        ev = T.parse_trace(open(pth).read(), sc); runs[c['id']] = (c, r, ev)
        for sid, sec, rel, atoms, fell, i in if_events(ev, sc): cover[(sid, sec, rel)].add(fell)
    for cid, (c, r, ev) in runs.items():
        snp = snap_name(c['screen'], r.get('state', '0') if r.get('state') != 'boot' else '0')
        if not os.path.exists(snp): continue
        st = State(json.load(open(snp))); k = 0
        # replay the W events up to each IF
        wi = {}
        tl = []; 
        for i, e in enumerate(ev):
            if e['kind'] == 'W': st.apply_w(e['key'])
            if e['kind'] == 'I' and e['op'] == 0x19:
                tl.append((i, bytes(st.trig), bytes(st.pst)))
        iff = if_events(ev, sc)
        snapshots = {i: (t, p) for i, t, p in tl}
        for sid, sec, rel, atoms, fell, i in iff:
            if (not fell) in cover[(sid, sec, rel)] or k >= a.per_case: continue
            t, p = snapshots[i]
            s2 = State(json.load(open(snp))); s2.trig = bytearray(t); s2.pst = bytearray(p)
            setup = solve_flip(atoms, s2, not fell)
            if not setup: continue
            vid = f'{c["script"]}:{c["section"]}:{k + 1}'
            if vid in have: k += 1; continue
            new.append(dict(c, id=vid, variant=k + 1, setup=setup, target=f'{sec}+{rel}', want=('fall' if not fell else 'jump'))); have.add(vid); k += 1
            cover[(sid, sec, rel)].add(not fell)
    plan += new; json.dump(dict(cases=plan), open(PLAN, 'w'), indent=0)
    print(f'{len(new)} variants added ({len(plan)} cases); IFs seen: {len(cover)}, with both branches taken in a baseline: {sum(1 for v in cover.values() if len(v) == 2)}')


# ---------------------------------------------------------------------------------------------------
# report

DISCS = ('orig', 'orig2', 'reorder', 'readable', 'compact')


def trace_path(case_id, disc): return os.path.join(TRACES, case_id.replace(':', '_') + f'.{disc}.trace')


_SC = {}


def scripts_of(disc):
    if disc not in _SC:
        d = T.load_discs()[ALIAS.get(disc, disc)]; _SC[disc] = T.Scripts(d['dg'], d['maphead'])
    return _SC[disc]


def load_run(case, disc):
    """Latest ledger row of the case on a disc, with the digests recomputed from the saved trace."""
    row = LAST.get((disc, case['id']))
    if row is None: return None
    if row.get('via') == 'enter':
        er = LAST_ENTER.get((disc, row['enter']))
        if er is None: return None
        path = os.path.join(TRACES, 'enter-' + row['enter'].replace(':', '-') + f'.{disc}.trace'); case = dict(case, section=case['section'])
    else:
        er = None; path = trace_path(case['id'], disc)
    out = dict(row)
    if row.get('skipped'): return out
    if os.path.exists(path):
        ev, r = analyse(open(path).read(), scripts_of(disc), case if row.get('via') != 'enter' else None)
        out.update(r)
        if row.get('via') == 'enter': out['reached'] = r['n'] > 0 and r['end'] in ('end', 'battle') and (er or {}).get('ok', False)
        out['events'] = [e['key'] for e in ev]
    return out


LAST = {}; LAST_ENTER = {}


def verdict(case, runs):
    """-> (status, reason, coverage) from the original run alone: can it be compared at all?"""
    o = runs.get('orig')
    if o is None: return 'PENDING', 'not run yet', ''
    if o.get('skipped'): return 'NOT-RUNNABLE', o['skipped'], ''
    if o.get('error'): return 'NOT-RUNNABLE', 'harness error: ' + o['error'][:80], ''
    end = o.get('end', '?')
    if end == 'hang' and o.get('unplaced'): return 'NOT-RUNNABLE', 'UNPLACED-NPC: ' + o['unplaced'][:90] + ' - run without it the game hangs (a speaker that does not exist); no path of the game places this NPC, so no play reaches the section', ''
    if end == 'hang': return 'HANG', f'the game hangs after {o["n"]} instructions (stuck in {o.get("hang_at")})', ''
    if o['n'] == 0: return 'NOT-RUNNABLE', f'no instruction ran (ends {end})', ''
    if not o.get('reached'): return 'NOT-RUNNABLE', f'the section did not start (first instruction elsewhere, ends {end})', ''
    cov = {'end': 'complete', 'battle': 'to START_BATTLE', 'max_frames': 'truncated at %d frames' % MAX_FRAMES, 'ilimit': 'truncated at %d instructions' % MAX_INS, 'idle': 'complete (idle %d frames)' % IDLE_FRAMES, 'timeout': 'truncated at %d frames (still running)' % MAX_FRAMES, 'steps_done': 'complete'}.get(end, end)
    if end not in ('end', 'battle', 'max_frames', 'steps_done', 'ilimit', 'timeout', 'idle'): return 'NOT-RUNNABLE', f'run ended with {end}', cov
    return 'RUN', '', cov


AUDIT = os.path.join(ROOT, 'build/story-analysis/relaxed-audit.csv')
NOT_PROVEN = set()


def load_audit():
    """(case, disc) of the `relaxed` verdicts that the audit could not justify: they do not count as PASS."""
    import csv
    NOT_PROVEN.clear()
    if os.path.exists(AUDIT):
        for r in csv.DictReader(open(AUDIT)):
            if r['verdict'] != 'PASS': NOT_PROVEN.add((r['case'], r['disc']))


def cmd_report(a):
    load_audit(); plan = load_plan(); rows = ledger()
    for r in rows:
        if r.get('kind') == 'reset':
            for dd in (LAST, LAST_ENTER):
                for key in [k for k in dd if k[0] == r['disc']]: del dd[key]
            continue
        if r.get('error') or r.get('end') == 'host' or r.get('watchdog'): continue          # a host row is no result (see last_rows)
        if r.get('kind') == 'enter': LAST_ENTER[(r['disc'], r['case'])] = r
        elif r.get('kind', 'case') == 'case': LAST[(r['disc'], r['case'])] = r
    discs = [d for d in DISCS if any(k[0] == d for k in LAST)]
    alts = [d for d in discs if d != 'orig']
    ms = maphead_screens()
    out = []; cnt = collections.Counter(); fails = []
    for c in plan:
        runs = {d: load_run(c, d) for d in discs}
        st, why, cov = verdict(c, runs)
        cmp_ = {}
        if st == 'RUN':
            o = runs['orig']
            for d in alts: cmp_[d] = compare(o, runs.get(d))
            req = [cmp_.get(d, '-') for d in REQUIRED]
            if any(v == 'DIFF' or v == 'NOT-REACHED' for v in cmp_.values()): st = 'FAIL'; why = 'trace differs on ' + ','.join(d for d, v in cmp_.items() if v in ('DIFF', 'NOT-REACHED'))
            elif all(v in ('same', 'relaxed') for v in req): st = 'PASS'
            else: st = 'RAN-ORIG-ONLY'
        if st == 'PASS' and any((c['id'], d) in NOT_PROVEN for d in REQUIRED): st = 'NOT-PROVEN'; why = 'a relaxed verdict that the audit (tools/dws/testing/trace_audit.py) could not justify'
        cnt[st] += 1
        row = dict(script=c['script'], section=c['section'], source='MAPHEAD' if c['script'] == 0 else 'DG', screen=c['screen'],
                   state=(runs['orig'] or {}).get('state', (runs['orig'] or {}).get('enter', '')), variant=c['variant'], status=st, reason=why,
                   end=(runs['orig'] or {}).get('end', ''), instructions=(runs['orig'] or {}).get('n', ''), coverage=cov,
                   digest_orig=((runs['orig'] or {}).get('digest') or '')[:12])
        for d in alts: row['vs_' + d] = cmp_.get(d, '-')
        for d in alts: row['strict_' + d] = ('-' if st not in ('PASS', 'FAIL', 'RAN-ORIG-ONLY') or cmp_.get(d, '-') in ('-', 'NOT-REACHED') else 'same' if cmp_[d] == 'same' else 'differs')
        out.append(row)
        if st == 'FAIL': fails.append((c, runs, cmp_))
    cols = ['script', 'section', 'source', 'screen', 'state', 'variant', 'status', 'reason', 'end', 'instructions', 'coverage', 'digest_orig'] + ['vs_' + d for d in alts] + ['strict_' + d for d in alts]
    import csv
    os.makedirs(os.path.dirname(CSV), exist_ok=True)
    with open(CSV, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for r in out: w.writerow(r)
    print(f'{CSV}: {len(out)} rows;', ', '.join(f'{k} {v}' for k, v in sorted(cnt.items())), '; discs', ','.join(discs))
    for d in alts:
        c2 = collections.Counter(r.get('vs_' + d) for r in out if r['status'] not in ('NOT-RUNNABLE', 'HANG'))
        print(f'  vs {d}:', dict(c2))
    for c, runs, cmp_ in fails[:int(a.show)]:
        print('FAIL', c['id'], cmp_)


# ---------------------------------------------------------------------------------------------------
# commands

def cmd_plan(a):
    cases = build_plan(); c = collections.Counter(x['screen'] for x in cases)
    print(f'{len(cases)} cases, {len(c)} screens: {PLAN}')


def pick(cases, a):
    if getattr(a, 'only', None):
        keep = set(a.only.split(',')); cases = [c for c in cases if c['id'] in keep]
        return [c for c in cases]
    if a.scripts:
        keep = {int(x) for x in a.scripts.split(',')}; cases = [c for c in cases if c['script'] in keep]
    if a.screens:
        keep = {int(x) for x in a.screens.split(',')}; cases = [c for c in cases if c['screen'] in keep]
    if not a.variants: cases = [c for c in cases if c['variant'] == 0]
    return cases


def present_ids():
    """scriptIds of the NPCs the engine can find now (scriptIdToEntityId: ENTITY_TABLE[i+2] != 0 and NPC_ENTITIES[i].scriptId)."""
    ram = T.emu_mod().api('/api/v1/cpu/ram/raw'); et = T.phys('ENTITY_TABLE'); npc = T.phys('NPC_ENTITIES'); out = set()
    for i in range(8):
        if struct.unpack_from('<I', ram, et + 4 * (i + 2))[0] != 0: out.add(ram[npc + i * 0x68 + 0x65])
    return out


def vkey(placed): return 'p' + '_'.join(str(x) for x in sorted(placed))


def state_file(screen, key):
    if key == '0': return state_path(screen)
    return os.path.join(SW, f'w-{screen}-{key}.state')


def enter_run(R, screen, key, setup, tag=''):
    """Warp to `screen` from the start state with `setup` applied first (traced). On the original disc the state is saved.
    -> (row, present ids or None)"""
    st = state_file(screen, key); save = st if R.disc == 'orig' else None
    out = os.path.join(TRACES, f'enter-{screen}-{key}.{R.disc}.trace')
    text = R.run(enter_steps(screen, setup), T.BOOT_STATE, out, setup=setup or None, max_frames=5000, stop_on_battle=True, hang_after=90, max_ins=10**9, idle_frames=None,
                 save_state=save, want_present=bool(save))
    ev, row = analyse(text, R.sc)
    ok = R.disc != 'orig' or os.path.exists(st)
    row.update(kind='enter', case=f'{screen}:{key}', disc=R.disc, screen=screen, variant=key, ok=ok, hang_at=R.hang_at,
               present=sorted(R.present) if R.present is not None else None)
    append(row)
    print(f'enter {screen} [{key}] on {R.disc}: {row["n"]} instructions, ends {row["end"]}, state {"saved" if (ok and save) else "-"}', flush=True)
    return row


def get_present(R, screen, key):
    """Present NPC scriptIds of a saved state (from the ledger, or by loading it)."""
    for r in ledger():
        if r.get('kind') == 'enter' and r['disc'] == 'orig' and r['case'] == f'{screen}:{key}' and r.get('present') is not None: return set(r['present'])
    st = state_file(screen, key)
    if not os.path.exists(st): return None
    R.emulator(); T.pause(); T.load_state(st); return present_ids()


def choose_state(R, screen, need):
    """Which saved state of `screen` a section needs: (key, setup, reason). Entities the section names must be placed."""
    if not need: return '0', None, None
    p0 = get_present(R, screen, '0')
    if p0 is not None and need <= p0: return '0', None, None
    best = None
    for placed, (setup, free) in placing_variants(screen).items():
        if need <= placed:
            cost = sum(len(v) if isinstance(v, dict) else 1 for v in setup.values())
            if best is None or (free, cost) < best[0]: best = ((free, cost), placed, setup)
    if best is None:
        return None, None, 'entity %s is placed by no MAPHEAD path of screen %d' % (sorted(need - (p0 or set())), screen)
    return vkey(best[1]), best[2], None


def stop_emulator():
    try: T.emu_mod().stop()
    except BaseException: pass


def run_one(R, c, disc, quiet=False, rerun=False):
    """One case on one disc (the state it needs is made on the way, on the original disc): appends its row(s) to the ledger.
    A harness failure raises; the caller decides what to do (the service retries once, then records a HANG)."""
    screen = c['screen']; t0 = time.time(); tag = {'rerun': 1} if rerun else {}
    say = (lambda *x: None) if quiet else (lambda *x: print(*x, flush=True))
    if c['script'] == 0 and c['section'] <= 254 and not c['variant']:          # a screen's setup: the `enter` run is the case
        key = f'{screen}:0'
        if key not in done_set(disc, 'enter') or rerun:
            try: enter_run(R, screen, '0', None)
            except Exception:
                stop_emulator(); raise
        rows = [r for r in ledger() if r.get('kind') == 'enter' and r['disc'] == disc and r['case'] == key and not r.get('error')]
        append(dict(kind='case', case=c['id'], disc=disc, via='enter', enter=key, secs=round(time.time() - t0, 1), **tag,
                    **{k: rows[-1][k] for k in ('end', 'n', 'nev', 'digest', 'rdigest', 'frames')}, rv=rows[-1].get('rv'),
                    reached=rows[-1]['n'] > 0 and rows[-1]['ok'] and rows[-1]['end'] in ('end', 'battle')))
        return
    need = needs(c['script'], c['section']) if c['script'] else set()
    key, setup, why = choose_state(R, screen, need)
    unplaced = None
    if key is None and RUN_UNPLACED:
        # no path places the NPC the section names: the section is run anyway in the screen's plain state (the NPC is absent: the engine finds no entity, and the same happens
        # on every disc, which is what the comparison is for). The row says so (`unplaced`); a section that then hangs is a HANG, as before.
        unplaced = why; key, setup = '0', None
    if key is None:
        append(dict(kind='case', case=c['id'], disc=disc, skipped=why, n=0, end='not-run', reached=False)); say(f'{c["id"]:12} skipped: {why}')
        return
    st = state_file(screen, key)
    if key != '0' and not os.path.exists(st) and disc == 'orig' or (key == '0' and screen != DEFAULT_SCREEN and not os.path.exists(st) and disc == 'orig'):
        try: enter_run(R, screen, key, setup)
        except Exception:
            stop_emulator(); raise
    if need and os.path.exists(st) and disc == 'orig':
        pres = get_present(R, screen, key)
        if pres is not None and not need <= pres:
            why = f'entity {sorted(need - pres)} not placed in the state made for it (variant {key}: a random draw or a condition the generator does not model)'
            if not RUN_UNPLACED:
                append(dict(kind='case', case=c['id'], disc=disc, skipped=why, n=0, end='not-run', reached=False)); say(f'{c["id"]:12} skipped: {why[:80]}')
                return
            unplaced = why
    if not os.path.exists(st):
        o = last_row('orig', c['id']) if disc != 'orig' else None
        if disc != 'orig' and not (o and o.get('state') == 'boot'): raise RuntimeError(f'no state {os.path.basename(st)} for {c["id"]} on {disc}')
        st = T.BOOT_STATE; key = 'boot'                          # not enterable: run in the start state, said in the CSV (an alternative disc runs where the original ran)
    out = os.path.join(TRACES, c['id'].replace(':', '_') + f'.{disc}.trace')
    t1 = time.time()
    try:
        text = R.run(case_steps(c), st, out, setup=c.get('setup') or None, max_frames=MAX_FRAMES + 600)
    except Exception:
        stop_emulator(); raise
    ev, row = analyse(text, R.sc, c)
    row.update(kind='case', case=c['id'], disc=disc, hang_at=R.hang_at, state=key, secs=round(time.time() - t0, 1), **tag)
    if unplaced: row['unplaced'] = unplaced[:160]
    append(row)
    say(f'{c["id"]:12} {disc:8} {row["n"]:4} ins  ends {row["end"]:10} reached={row["reached"]}  state {key}  {row["secs"]}s')


def cmd_run(a):
    """Foreground, unsupervised (for a few cases by hand); the campaign is `start`."""
    os.makedirs(TRACES, exist_ok=True)
    plan = load_plan(); cases = pick(plan, a); R = Runner(a.disc); done = set() if getattr(a, 'force', False) else {cid for (d, cid) in last_rows()[0] if d == a.disc}          # a host row is no result
    by_screen = collections.OrderedDict()
    for c in cases: by_screen.setdefault(c['screen'], []).append(c)
    n = 0
    for screen, lst in by_screen.items():
        for c in [c for c in lst if c['id'] not in done]:
            if a.limit and n >= a.limit: return
            n += 1
            try: run_one(R, c, a.disc)
            except Exception as e:
                append(dict(kind='case', case=c['id'], disc=a.disc, error=str(e)[:200])); print(f'{c["id"]}: error {e}', flush=True)
    stop_emulator()


# ---------------------------------------------------------------------------------------------------
# the service: a supervised background campaign
#
# The end rules of a case (what makes a run stop), all counted in game frames so that they are the same on every disc:
#   end       the steps finished: the section returned and the tamer is free (`talk until free`); the normal ending
#   battle    START_BATTLE was reached; the battle is not traced (the emulator is restarted afterwards)
#   idle      IDLE_FRAMES (240) frames in a row with no script instruction and no change of a watched byte. Sounds and music do NOT
#             count as activity: the partner's idle animation plays a sound every few seconds, which made a finished section
#             (0:1220..0:1230, two instructions) run to the cap, 83 s each, instead of ending idle after ~15 s
#   ilimit    MAX_INS (4000) instructions: a section that loops all run long
#   timeout   MAX_FRAMES (1500) frames of the `talk until free` step: a section that keeps running (instructions or state keep changing)
#   hang      the game stopped calling gameLoop for CTL.cap() seconds of host time (stuck in a C loop), or the watchdog gave up
# The idle rule cannot change the digest of a case that ended another way (it only adds an end): verified by re-running 18 old
# cases of every kind (end, battle, ilimit, timeout, hang) and comparing their digests with the ledger: all equal.
#
# The watchdog, three layers:
#   1. per case: no frame for max(30, 3 x median seconds per case) s (at most 120) -> the run is finished as `hang`, trace kept; a hard
#      limit on the host time of a run (MAX_FRAMES / 60 * 2.5 + 90 s) ends a run that advances but never finishes. A case that
#      ends `hang`, and a harness failure (emulator died, API error), are retried once on a fresh emulator; the second failure is
#      recorded as HANG (a `hang` row, hang_at says why) and the sweep goes on.
#   2. a thread checks every 10 s that the main loop beats (status.json): 2 minutes without a beat -> the emulator is killed by PID
#      (that unblocks any call into it); 3 minutes -> the process re-executes itself (same PID, the ledger is the memory).
#   3. status.json is rewritten after every case and every few seconds during a run (field `beat` = last main-loop beat,
#      `alive` = last watchdog check): `status` shows both ages.

PIDF = os.path.join(SW, 'sweep.pid'); STATUSF = os.path.join(SW, 'status.json'); LOGF = os.path.join(SW, 'sweep.log')
MAIN_SCREENS = (1, 168, 169, 170, 180, 181, 182, 204, 205, 206, 216, 217, 218, 236, 237, 238)    # the main route: Jijimon's house, File City, the first quests, Kunemon, the shop
REQUIRED = ('reorder', 'readable')        # a section counts PASS when it reached and traced equal on both of these (relaxed = same trace after dropping layout-only jumps)


def log(*x): print(time.strftime('%H:%M:%S'), *x, flush=True)


def read_json(path):
    try: return json.load(open(path))
    except (OSError, ValueError): return None


def write_json_atomic(path, obj):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f: json.dump(obj, f); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def pid_running():
    """PID of the running service, or None (pid file whose process is gone or is not the sweep: stale)."""
    try: pid = int(open(PIDF).read().strip())
    except (OSError, ValueError): return None
    try: cmd = open(f'/proc/{pid}/cmdline', 'rb').read().split(b'\0')
    except OSError: return None
    return pid if any(x.endswith(b'tools/dws/testing/sweep.py') for x in cmd) and b'serve' in cmd else None


def reset_disc(disc, last, classes):
    """A `reset` row says that the results of a disc before it are void (the disc was rebuilt): the cases of that disc are pending again."""
    for key in [k for k in list(last) if k[0] == disc]: del last[key]
    for key in [k for k in list(classes) if k[0] == disc]: del classes[key]
    for key in [k for k in list(HOST_LAST) if k[0] == disc]: del HOST_LAST[key]
    for key in [k for k in list(HOST_N) if k[0] == disc]: del HOST_N[key]


HOST_LAST = {}; HOST_N = collections.Counter()      # (disc, case) -> its latest row when that is a `host` row (no result yet); how many host rows a case has had
HOST_TRIES = 4                                       # a case that ends `host` this many times stays unresolved (reported, never a FAIL)


def last_rows():
    """(disc, case) -> latest row of kind case (errors skipped); and the rows with a duration, in order; and the classes.
    A row that ends `host` (the run hit the host-time limit: the machine was overloaded, the emulated game was not slow) is NOT a result: it is
    left out, so the case stays pending (phase `retry`), and a result from before it (a rerun of a classification) stays the latest one.
    HOST_LAST / HOST_N tell which cases wait for such a retry."""
    last = {}; secs = []; classes = {}; HOST_LAST.clear(); HOST_N.clear()
    for r in ledger():
        k = r.get('kind', 'case')
        if k == 'reset': reset_disc(r['disc'], last, classes); continue
        if k == 'class': classes[(r['disc'], r['case'])] = r; continue
        if k != 'case' or r.get('error'): continue
        key = (r['disc'], r['case'])
        if r.get('end') == 'host' or r.get('watchdog'): HOST_LAST[key] = r; HOST_N[key] += 1; continue          # `watchdog`: the harness failed twice (emulator died, API error): no result either
        HOST_LAST.pop(key, None); last[key] = r
        if r.get('secs') is not None: secs.append(r['secs'])
    for key in HOST_LAST: classes.pop(key, None)         # a class given before the case's latest run failed to run again is not about it
    return last, secs, classes


def compare(o, r):
    """Original row vs another disc's row -> same | relaxed | DIFF | NOT-REACHED | -"""
    if r is None: return '-'
    if r.get('end') == 'host': return '-'               # no result (the run hit the host-time limit): pending, never a difference
    if r.get('skipped') or r.get('error') or r.get('end') == 'hang' or not r.get('reached'): return 'NOT-REACHED'
    if r['digest'] == o['digest']: return 'same'
    if rdig(r) == rdig(o): return 'relaxed'
    if {'ilimit', 'timeout', 'max_frames'} & {o.get('end'), r.get('end')} and common_prefix_equal(o, r): return 'relaxed'
    return 'DIFF'


def common_prefix_equal(o, r):
    """Two runs that were cut (MAX_INS instructions, or the 1 500 frames of a section that keeps running): the cut counts every instruction, JUMP_TO included, and
    a moved code has more or fewer of them; the frame at which the box buttons are pressed differs by a phase. So the two runs end at different points of the same
    loop or dialogue. They are equal when their normalized traces are equal up to the shorter one's last instruction."""
    try:
        ev = [T.parse_trace(open(trace_path(x['case'], x['disc'])).read(), scripts_of(x['disc'])) for x in (o, r)]
        if [T.digest(e) for e in ev] != [o.get('digest'), r.get('digest')]: return False          # the traces on disk are not the rows' runs
    except (OSError, ValueError, KeyError, IndexError): return False
    ra, rb = relaxed_events(ev[0]), relaxed_events(ev[1])
    ia = [i for i, x in enumerate(ra) if x.startswith('I ')]; ib = [i for i, x in enumerate(rb) if x.startswith('I ')]
    k = min(len(ia), len(ib))
    if k == 0: return False
    return ra[:ia[k - 1] + 1] == rb[:ib[k - 1] + 1]


def runnable(o):
    return bool(o) and not o.get('skipped') and not o.get('error') and o.get('end') in ('end', 'battle', 'max_frames', 'steps_done', 'ilimit', 'timeout', 'idle') \
        and o.get('n', 0) > 0 and bool(o.get('reached'))


def summary(plan=None, last=None):
    """Counts from the ledger alone (no trace read): -> dict(status counts, per disc done/left)."""
    plan = plan or [c for c in load_plan() if c['variant'] == 0]; last = last or last_rows()[0]
    cnt = collections.Counter(); left = collections.Counter(); done = collections.Counter(); runn = 0
    for c in plan:
        o = last.get(('orig', c['id']))
        if o is None: cnt['PENDING'] += 1; left['orig'] += 1; continue
        done['orig'] += 1
        if o.get('end') == 'hang': cnt['NOT-RUNNABLE' if o.get('unplaced') else 'HANG'] += 1; continue
        if not runnable(o): cnt['NOT-RUNNABLE'] += 1; continue
        runn += 1; res = []
        for d in REQUIRED:
            r = last.get((d, c['id']))
            if r is not None: done[d] += 1
            else: left[d] += 1
            res.append(compare(o, r))
        if any(v in ('DIFF', 'NOT-REACHED') for v in res): cnt['FAIL'] += 1
        elif all(v in ('same', 'relaxed') for v in res): cnt['PASS'] += 1
        else: cnt['RAN-ORIG-ONLY'] += 1
    return dict(cnt=dict(cnt), left=dict(left), done=dict(done), cases=len(plan), runnable=runn)


class Ctl:
    """The state shared by the threads of one process (a worker or the supervisor): heartbeat, stop flag, per-case limits."""

    def __init__(self, a, path, role):
        self.a = a; self.path = path; self.role = role; self.stop = False; self.stop_t = None; self.t_beat = time.time(); self.t_alive = time.time(); self.t_write = 0
        self.phase = 'starting'; self.case = None; self.disc = None; self.extra = {}; self.started = time.time()
        self.session = collections.Counter(); self.queue_left = 0; self.queue_total = 0; self.lock = threading.Lock()
        self.restarts = int(os.environ.get('SWEEP_RESTARTS', '0')); self.sup = {}

    def cap(self):
        secs = sorted(last_rows()[1][-30:])
        med = secs[len(secs) // 2] if secs else 10
        return min(120, max(30, 3 * med))

    def beat(self, **kw):
        self.t_beat = time.time(); self.extra.update(kw)
        if time.time() - self.t_write > 5: self.write()

    def write(self):
        with self.lock:
            self.t_write = time.time()
            try:
                d = dict(pid=os.getpid(), role=self.role, port=WORKER, phase=self.phase, case=self.case, disc=self.disc, beat=self.t_beat, alive=self.t_alive,
                         time=time.time(), started=self.started, queue_left=self.queue_left, queue_total=self.queue_total,
                         restarts=self.restarts, session=dict(self.session), stopping=self.stop, order=self.a.order, only=self.a.disc)
                d.update(self.extra); d.update(self.sup)
                write_json_atomic(self.path, d)
            except OSError: pass


def watchdog(ctl):
    """Thread of a worker: the loop must beat. 2 minutes without a beat: the emulator is killed by PID (that unblocks any call into it);
    3 minutes: the worker exits and the supervisor starts another (the unfinished cases are still pending in the ledger)."""
    while True:
        time.sleep(10)
        now = time.time(); ctl.t_alive = now
        if ctl.case is None: ctl.t_beat = now          # waiting for work is not a stuck loop
        age = now - ctl.t_beat
        if ctl.stop and ctl.stop_t and now - ctl.stop_t > 60:
            log('watchdog: stop requested 60 s ago and the loop is still busy: killing the emulator'); stop_emulator()
        if age > 120:
            log(f'watchdog: no heartbeat for {age:.0f} s (case {ctl.case} on {ctl.disc}): killing the emulator by PID')
            stop_emulator(); ctl.session['watchdog_kills'] += 1; ctl.t_beat = now - 100
        if age > 180 and not ctl.stop:
            log('watchdog: the loop is stuck: this worker exits, the supervisor restarts it'); stop_emulator(); ctl.write(); os._exit(3)
        ctl.write()


def ensure_state(c, o):
    """The saved state a case runs from, remade (on the original disc) when it was cleaned up. -> path or None."""
    key = o.get('state', '0')
    if key == 'boot' or o.get('via') == 'enter': return None
    st = state_file(c['screen'], key)
    if os.path.exists(st): return st
    Ro = Runner('orig'); need = needs(c['script'], c['section']) if c['script'] else set()
    # the state the original run used, by its key (choose_state alone can pick another variant once the state '0' of the screen is gone, and then the file the case
    # needs is never made: the retry of 180:6:0 failed that way)
    setup = None
    if key != '0':
        for placed, (sup, free) in placing_variants(c['screen']).items():
            if vkey(placed) == key: setup = sup; break
        if setup is None: k, setup, why = choose_state(Ro, c['screen'], need)
    log(f'remaking state {os.path.basename(st)}'); enter_run(Ro, c['screen'], key, setup)
    return st


def last_row(disc, cid):
    return last_rows()[0].get((disc, cid))


def run_supervised(ctl, runners, disc, c):
    """One case with the retry rule of the watchdog. -> row"""
    R = runners.setdefault(disc, Runner(disc)); ctl.case = c['id']; ctl.disc = disc; ctl.beat(frame=0, case_secs=0)
    err = None
    for attempt in (1, 2):
        try:
            if disc != 'orig': ensure_state(c, last_row('orig', c['id']) or {})
            run_one(R, c, disc, quiet=True, rerun=attempt == 2)
            r = last_row(disc, c['id'])
            if r and r.get('end') == 'hang' and attempt == 1:
                log(f'{c["id"]} {disc}: ended hang (stuck in {r.get("hang_at")}), retrying once'); stop_emulator(); err = 'hang'; continue
            return r
        except Abandon: raise
        except BaseException as e:             # includes SystemExit from emu.start, ConnectionError, a dead emulator
            err = f'{type(e).__name__}: {e}'[:160]; ctl.session['retries'] += 1
            log(f'{c["id"]} {disc}: attempt {attempt} failed: {err}'); stop_emulator(); time.sleep(2)
    row = dict(kind='case', case=c['id'], disc=disc, end='host', n=0, nev=0, digest='', rdigest='', frames=None, reached=False, state='?',
               hang_at='harness: ' + (err or '?'), secs=0, watchdog=1)           # not a HANG of the game: no result, retried in the retry phase
    append(row); ctl.session['hangs'] += 1; log(f'{c["id"]} {disc}: harness failure twice, no result, retried later ({err})')
    return None


def classify_inline(ctl, runners, disc, c, o, r):
    """An alternative disc differs from the original: run the alternative again; if it differs the same way run the original again
    (flake or divergence). Writes a `class` row: REAL | FLAKE-ALT | FLAKE-ORIG."""
    verdict = compare(o, r)
    if verdict in ('same', 'relaxed', '-'): return          # '-': no result (host limit, harness failure), nothing to classify
    log(f'{c["id"]} {disc}: {verdict}, running it again')
    R = runners.setdefault(disc, Runner(disc))
    try: run_one(R, c, disc, quiet=True, rerun=True)
    except Abandon: raise
    except BaseException as e: stop_emulator(); log(f'rerun failed: {e}')
    r2 = last_row(disc, c['id'])
    if (disc, c['id']) in HOST_LAST: log(f'{c["id"]} {disc}: the rerun ended host (overload): classified when it is retried'); return
    v2 = compare(o, r2)
    if v2 in ('same', 'relaxed'): cl = 'FLAKE-ALT'
    else:
        Ro = runners.setdefault('orig', Runner('orig'))
        try: run_one(Ro, c, 'orig', quiet=True, rerun=True)
        except Abandon: raise
        except BaseException as e: stop_emulator(); log(f'rerun of orig failed: {e}')
        o2 = last_row('orig', c['id'])
        if ('orig', c['id']) in HOST_LAST: log(f'{c["id"]} orig: the rerun ended host (overload): classified when it is retried'); return
        v3 = compare(o2, r2)
        cl = 'FLAKE-ORIG' if v3 in ('same', 'relaxed') else 'REAL'
    append(dict(kind='class', case=c['id'], disc=disc, verdict=cl, first=verdict, again=v2))
    log(f'CLASS {c["id"]} {disc}: {cl}'); ctl.session[cl] += 1


def phase_items(phase, ctl):
    """The work of a phase, evaluated when it starts. -> [(disc, case)] (screen-major in the comparison phases, so that a finished screen can be cleaned)"""
    a = ctl.a; plan = [c for c in load_plan() if c['variant'] == 0]; last = last_rows()[0]
    main = [c for c in plan if c['screen'] in MAIN_SCREENS]; rest = [c for c in plan if c['screen'] not in MAIN_SCREENS]
    if phase == 'baseline':
        seq = (main + rest) if a.order == 'main-first' else plan
        return [('orig', c) for c in seq if ('orig', c['id']) not in last and ('orig', c['id']) not in HOST_LAST]       # host-limit cases wait for the retry phase
    comps = [d for d in REQUIRED if a.disc in ('all', d)]
    cases = main if phase == 'main' else rest; items = []
    screens = collections.OrderedDict()
    for c in cases: screens.setdefault(c['screen'], []).append(c)
    for screen, lst in screens.items():
        for d in comps:
            for c in lst:
                if ('orig', c['id']) in last and runnable(last[('orig', c['id'])]) and (d, c['id']) not in last and (d, c['id']) not in HOST_LAST: items.append((d, c))
    return items


def host_pending():
    """[(disc, case id)] whose latest run ended `host` and that have tries left."""
    last_rows(); return sorted(k for k in HOST_LAST if HOST_N[k] < HOST_TRIES)


def wait_quiet(ctl, below=14, max_wait=1800):
    """Waits (heartbeating) until the 1-minute load is under `below`: the host-limit cases are retried when the machine has cores for them."""
    t0 = time.time()
    while not ctl.stop and time.time() - t0 < max_wait:
        if os.getloadavg()[0] < below: return True
        ctl.beat(); time.sleep(5)
    return False


def retry_hosts(ctl, pool):
    """The cases that ended `host` (hit the host-time limit under load; no result) are run again after the load has dropped, the original disc first and then
    the comparison discs of the cases that now have an original result; up to HOST_TRIES runs each. They are never a FAIL."""
    ctl.phase = 'retry'
    for rnd in range(HOST_TRIES):
        if ctl.stop: return
        pend = host_pending()
        if not pend: return
        plan = {c['id']: c for c in load_plan()}
        log(f'retry round {rnd + 1}: {len(pend)} cases ended host; waiting for the load to drop'); wait_quiet(ctl)
        items = sorted(((d, plan[cid]) for d, cid in pend), key=lambda x: (x[0] != 'orig', x[1]['screen']))
        ctl.queue_total = len(items); ctl.beat()
        if not ctl.stop: pool.run(make_chunks(items, 'retry'))
        for ph in ('main', 'rest'):
            if ctl.stop: return
            its = phase_items(ph, ctl)
            if its: ctl.phase = ph; ctl.queue_total = len(its); pool.run(make_chunks(its, ph)); ctl.phase = 'retry'
        cleanup_states(verbose=False)


def cleanup_states(comps=REQUIRED, verbose=True):
    """Deletes the saved states of the screens whose runnable cases are done on the original disc and on every comparison disc."""
    import fnmatch
    plan = [c for c in load_plan() if c['variant'] == 0]; last = last_rows()[0]; screens = collections.defaultdict(list)
    for c in plan: screens[c['screen']].append(c)
    freed = n = 0
    for screen, lst in screens.items():
        ok = all(('orig', c['id']) in last and (not runnable(last[('orig', c['id'])]) or all((d, c['id']) in last for d in comps)) for c in lst)
        if not ok: continue
        for f in os.listdir(SW):
            if fnmatch.fnmatch(f, f'w-{screen}.state') or fnmatch.fnmatch(f, f'w-{screen}-*.state') or fnmatch.fnmatch(f, f'w-{screen}*.state.part*'):
                freed += os.path.getsize(os.path.join(SW, f)); os.remove(os.path.join(SW, f)); n += 1
    if verbose: log(f'cleanup: {n} state files deleted, {freed / 1e9:.1f} GB freed')
    return n


def run_report(ctl):
    ctl.phase = 'report'; ctl.write()
    p = subprocess.Popen(['nice', '-n', '10', sys.executable, os.path.abspath(__file__), 'report'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    while p.poll() is None:
        time.sleep(3); ctl.beat()
    out = p.stdout.read().strip().split('\n')[0]; log('report:', out[:200])


def process_item(ctl, runners, disc, c):
    if (disc, c['id']) in last_rows()[0] and (disc, c['id']) not in HOST_LAST: return          # done (a case whose latest run ended `host` is not)
    r = run_supervised(ctl, runners, disc, c); ctl.session['cases'] += 1
    if disc != 'orig' and r is not None:
        o = last_row('orig', c['id'])
        if o: classify_inline(ctl, runners, disc, c, o, r)
    ctl.case = None; ctl.write()


def cmd_worker(a):
    """One worker: its own emulator (EMU_PORT, home dir .tools/emu/home-PORT), jobs on stdin (JSON lines), `done` lines on the protocol pipe."""
    global CTL, WORKER
    WORKER = int(os.environ['EMU_PORT']); proto = os.fdopen(os.dup(1), 'w'); os.dup2(2, 1)       # the emulator tools print on stdout: that goes to the log
    os.makedirs(TRACES, exist_ok=True)
    CTL = ctl = Ctl(a, os.path.join(SW, f'worker-{WORKER}.json'), 'worker')
    def on_term(sig, frm): ctl.stop = True; ctl.stop_t = ctl.stop_t or time.time()
    signal.signal(signal.SIGTERM, on_term); signal.signal(signal.SIGINT, on_term)
    stop_emulator(); threading.Thread(target=watchdog, args=(ctl,), daemon=True).start()
    plan = {c['id']: c for c in load_plan()}; runners = {}
    try:
        for line in sys.stdin:
            job = json.loads(line); ctl.phase = job['phase']; ctl.beat()
            try:
                for disc, cid in job['items']:
                    if ctl.stop: break
                    process_item(ctl, runners, disc, plan[cid])
            except Abandon: log('abandoned', ctl.case); break
            proto.write(json.dumps(dict(done=job['id'])) + '\n'); proto.flush()
            if ctl.stop: break
    finally:
        stop_emulator(); ctl.phase = 'exited'; ctl.case = None; ctl.write()


def mem_avail_gb(): return int([l for l in open('/proc/meminfo') if l.startswith('MemAvailable')][0].split()[1]) / 1048576


class Pool:
    """N worker processes, one emulator each, fed with chunks of cases. Guards: no NEW chunk while MemAvailable < 6 GB or the 1-minute load
    is over 15 (until it is under 12); workers are added back one at a time while the machine has room."""

    def __init__(self, ctl, n, guards=True):
        self.ctl = ctl; self.n = n; self.allowed = n; self.t_ramp = time.time() + 30; self.paused = ''; self.procs = {}; self.lock = threading.Lock()
        self.ports = [38020 + k for k in range(n)]
        threading.Thread(target=self.monitor, daemon=True).start()

    def monitor(self):
        c = self.ctl
        while True:
            time.sleep(10); load = os.getloadavg()[0]; mem = mem_avail_gb()
            if self.paused:
                if load < 24 and mem >= 4: self.paused = ''; log('guards: resumed')
            elif mem < 3 or load > 32:
                self.paused = f'RAM {mem:.1f} GB, load {load:.1f}'; log('guards: new cases paused:', self.paused)
                if self.allowed > 1: self.allowed = max(1, self.allowed - 2); self.t_ramp = time.time() + 120; log(f'guards: shedding 2 workers: allowed {self.allowed}; no ramp for 2 min')
            if (not self.paused and self.allowed < self.n and time.time() >= self.t_ramp and load < 14 and mem >= 8):
                self.allowed += 1; self.t_ramp = time.time() + 30; log(f'guards: all fine (load {load:.1f}, RAM {mem:.0f} GB): ramping to {self.allowed} workers')
            workers = []
            for port in self.ports:
                w = read_json(os.path.join(SW, f'worker-{port}.json'))
                if w: workers.append(dict(port=port, pid=w.get('pid'), case=w.get('case'), disc=w.get('disc'), beat=w.get('beat'), restarts=self.procs.get(port, {}).get('restarts', 0),
                                          session=w.get('session'), phase=w.get('phase')))
            c.sup = dict(workers=workers, allowed=self.allowed, paused=self.paused, load=load, mem_gb=round(mem, 1), n=self.n)
            c.t_beat = time.time(); c.write()

    def spawn(self, port):
        env = dict(os.environ, EMU_PORT=str(port))
        p = subprocess.Popen(['nice', '-n', '10', sys.executable, os.path.abspath(__file__), 'worker', '--disc', self.ctl.a.disc, '--order', self.ctl.a.order], env=env,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=open(LOGF, 'a'), text=True, cwd=ROOT)
        old = self.procs.get(port, {}); self.procs[port] = dict(p=p, restarts=old.get('restarts', -1) + 1)
        with self.lock: write_json_atomic(os.path.join(SW, 'workers.json'), {str(k): v['p'].pid for k, v in self.procs.items()})
        return p

    def slot(self, k, queue, done):
        import select
        c = self.ctl; port = self.ports[k]; p = None
        while not c.stop:
            chunk = None
            with self.lock:
                if k < self.allowed and not self.paused:
                    for ch in queue:
                        if ch['after'] is None or ch['after'] in done: chunk = ch; break
                    if chunk: queue.remove(chunk)
                if chunk is None and not queue: break
            if chunk is None: time.sleep(2); continue
            if p is None or p.poll() is not None: p = self.spawn(port)
            try: p.stdin.write(json.dumps(chunk) + '\n'); p.stdin.flush()
            except OSError: p = None; queue.append(chunk); continue
            while True:
                r, _, _ = select.select([p.stdout], [], [], 5)
                if r:
                    if not p.stdout.readline(): break
                    done.add(chunk['id']); break
                if p.poll() is not None: break
                w = read_json(os.path.join(SW, f'worker-{port}.json')) or {}
                if time.time() - w.get('beat', time.time()) > 240 and w.get('case'):
                    log(f'worker {port}: silent for 4 minutes, killed'); p.kill(); self.kill_emulator(port); break
                if c.stop and time.time() - (c.stop_t or 0) > 90: p.kill(); break
            if p.poll() is not None or c.stop:
                if p.poll() is not None and not c.stop: log(f'worker {port} exited ({p.returncode}) during chunk {chunk["id"]}'); self.kill_emulator(port)
                p = None
                if chunk['id'] not in done and chunk['tries'] < 3 and not c.stop: chunk['tries'] += 1; queue.append(chunk)
        if p is not None:
            try: p.stdin.close(); p.wait(timeout=60)
            except Exception: p.kill()

    def kill_emulator(self, port):
        st = read_json(os.path.join(ROOT, f'build/emu-{port}.json'))
        if st:
            try: os.kill(st['pid'], 9)
            except OSError: pass

    def run(self, chunks):
        queue = list(chunks); done = set(); ths = [threading.Thread(target=self.slot, args=(k, queue, done)) for k in range(self.n)]
        for t in ths: t.start()
        while any(t.is_alive() for t in ths):
            self.ctl.queue_left = sum(len(ch['items']) for ch in queue); self.ctl.t_beat = time.time(); time.sleep(2)
            if self.ctl.stop:
                for v in self.procs.values():
                    if v['p'].poll() is None: v['p'].terminate()
        for t in ths: t.join()

    def shutdown(self):
        for v in self.procs.values():
            if v['p'].poll() is None: v['p'].terminate()
        t0 = time.time()
        while time.time() - t0 < 60 and any(v['p'].poll() is None for v in self.procs.values()): time.sleep(0.5)
        for v in self.procs.values():
            if v['p'].poll() is None: v['p'].kill()


def make_chunks(items, phase, size=6):
    """Items (screen-major) -> chunks of at most `size` cases of one screen and one disc. In the baseline the later chunks of a screen wait for
    its first one (that one makes the saved states of the screen; the others only read them)."""
    groups = collections.OrderedDict()
    for disc, c in items: groups.setdefault((disc, c['screen']), []).append((disc, c['id']))
    chunks = []; n = 0
    for key, lst in groups.items():
        first = None
        for i in range(0, len(lst), size):
            n += 1; ch = dict(id=f'{phase}-{n}', phase=phase, items=lst[i:i + size], after=first if phase == 'baseline' else None, tries=0)
            if first is None: first = ch['id']
            chunks.append(ch)
    return chunks


def kill_orphans():
    """Workers and emulators of the sweep left by a service that was killed: by PID, from the files that name them (never by pattern)."""
    w = read_json(os.path.join(SW, 'workers.json')) or {}
    for pid in w.values():
        try:
            cmd = open(f'/proc/{pid}/cmdline', 'rb').read().split(b'\0')
            if any(x.endswith(b'tools/dws/testing/sweep.py') for x in cmd) and b'worker' in cmd: os.kill(pid, signal.SIGKILL)
        except OSError: pass
    for k in range(40):
        f = os.path.join(ROOT, f'build/emu-{38020 + k}.json'); st = read_json(f)
        if st:
            try: os.kill(st['pid'], 9)
            except OSError: pass
            try: os.remove(f)
            except OSError: pass


def cmd_serve(a):
    global CTL
    os.makedirs(TRACES, exist_ok=True)
    CTL = None; ctl = Ctl(a, STATUSF, 'supervisor')
    open(PIDF, 'w').write(str(os.getpid()))
    def on_term(sig, frm): ctl.stop = True; ctl.stop_t = ctl.stop_t or time.time(); log('SIGTERM: stopping, the running cases are given up')
    signal.signal(signal.SIGTERM, on_term); signal.signal(signal.SIGINT, on_term)
    log(f'service started: pid {os.getpid()}, nice {os.nice(0)}, workers {a.workers}, disc {a.disc}, order {a.order}')
    kill_orphans()
    pool = Pool(ctl, a.workers); phases = []
    if a.disc in ('all', 'orig'): phases.append('baseline')
    if a.disc != 'orig': phases += ['main', 'rest']
    try:
        for phase in phases:
            if ctl.stop: break
            for attempt in range(3):
                ctl.phase = phase; items = phase_items(phase, ctl); ctl.queue_total = len(items); ctl.beat()
                if not items: break
                log(f'phase {phase} pass {attempt + 1}: {len(items)} cases in {len(make_chunks(items, phase))} chunks')
                pool.run(make_chunks(items, phase))
                if phase != 'baseline': cleanup_states(verbose=False)
                if ctl.stop: break
            if ctl.stop: break
            if phase != 'baseline': cleanup_states()
            run_report(ctl)
        if not ctl.stop: retry_hosts(ctl, pool); run_report(ctl)
        ctl.phase = 'stopped' if ctl.stop else 'done'
        if not ctl.stop: log('campaign done')
    except BaseException:
        import traceback; log('service crashed:', traceback.format_exc()); ctl.phase = 'crashed'
    finally:
        pool.shutdown(); kill_orphans(); ctl.write()
        try: os.remove(PIDF)
        except OSError: pass
        log('service exit', ctl.phase)


def cmd_bench(a):
    """Determinism and speed of the pool: 20 finished original-disc cases are run again with N workers into a scratch ledger and the digests
    compared with the main ledger's. Run it with the service stopped (same ports)."""
    import tempfile, shutil
    rows = [r for r in ledger() if r['disc'] == 'orig' and r.get('kind') == 'case' and not r.get('error') and not r.get('skipped') and not r.get('via')
            and r.get('digest') and r.get('end') in ('end', 'battle', 'idle') and r.get('n', 0) > 0 and r.get('state') not in (None, 'boot') and 'secs' in r and r['secs'] < 30]
    rows = [r for r in rows if os.path.exists(state_file(next(c for c in load_plan() if c['id'] == r['case'])['screen'], r['state']))]
    import random; random.Random(5).shuffle(rows); pick = {}
    for r in rows: pick.setdefault(r['case'], r)
    pick = dict(list(pick.items())[:a.count]); want = {k: v['digest'] for k, v in pick.items()}
    d = tempfile.mkdtemp(prefix='sweepbench-', dir=os.path.join(SW))
    led = os.path.join(d, 'ledger.jsonl')
    with open(led, 'w') as f:
        for r in ledger():
            if not (r.get('kind', 'case') == 'case' and r['disc'] == 'orig' and r['case'] in pick): f.write(json.dumps(r) + '\n')
    os.environ['SWEEP_LEDGER'] = led; os.environ['SWEEP_TRACES'] = os.path.join(d, 'traces'); os.makedirs(os.environ['SWEEP_TRACES'])
    t0 = time.time()
    ns = argparse.Namespace(disc='orig', order='plain'); ctl = Ctl(ns, os.path.join(d, 'status.json'), 'supervisor'); ctl.phase = 'bench'
    pool = Pool(ctl, a.workers); items = [('orig', next(c for c in load_plan() if c['id'] == k)) for k in pick]
    ch = make_chunks(items, 'bench', size=a.chunk)
    for c_ in ch: c_['after'] = None
    pool.run(ch); pool.shutdown(); dt = time.time() - t0
    got = {}
    for l in open(led):
        r = json.loads(l)
        if r.get('kind') == 'case' and r['disc'] == 'orig' and r['case'] in pick and r.get('t'): got[r['case']] = r['digest']
    same = sum(1 for k in want if got.get(k) == want[k])
    print(f'bench: {len(pick)} cases, {a.workers} workers: {dt:.0f} s = {len(pick) / dt * 60:.1f} cases/min; digests equal to the ledger: {same}/{len(pick)}; load {os.getloadavg()[0]:.1f}')
    shutil.rmtree(d, ignore_errors=True)


def cmd_start(a):
    if pid_running(): sys.exit(f'already running (pid {pid_running()}); `tools/dws/testing/sweep.py status`')
    if not 1 <= a.workers <= 30: sys.exit('--workers 1..30')
    os.makedirs(SW, exist_ok=True)
    cmd = ['nice', '-n', '10', sys.executable, os.path.abspath(__file__), 'serve', '--disc', a.disc, '--order', a.order, '--workers', str(a.workers)]
    env = dict(os.environ, SWEEP_PIN_RANDOM='1') if a.pin_random else os.environ
    p = subprocess.Popen(cmd, stdout=open(LOGF, 'a'), stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True, cwd=ROOT, env=env)
    for _ in range(50):
        time.sleep(0.2)
        if pid_running(): break
    print(f'started pid {p.pid} (own process group, nice 10, {a.workers} workers, ports 38020..{38019 + a.workers}); log {LOGF}; `tools/dws/testing/sweep.py status`')


def cmd_stop(a):
    pid = pid_running()
    if not pid: print('not running'); kill_orphans(); return
    os.kill(pid, signal.SIGTERM); t0 = time.time()
    while time.time() - t0 < 120 and pid_running(): time.sleep(0.5)
    if pid_running():
        print('did not exit in 120 s: killing it'); os.kill(pid, signal.SIGKILL); kill_orphans()
        try: os.remove(PIDF)
        except OSError: pass
    else: print(f'stopped in {time.time() - t0:.0f} s')


def fmt_dur(s):
    s = int(s)
    return f'{s // 3600}h{s % 3600 // 60:02d}m' if s >= 3600 else f'{s // 60}m{s % 60:02d}s'


def cmd_status(a):
    pid = pid_running(); st = read_json(STATUSF) or {}; last, secs, classes = last_rows(); S_ = summary(last=last)
    now = time.time(); c = S_['cnt']
    rows = [r for r in ledger() if r.get('kind', 'case') == 'case' and not r.get('error') and r.get('secs') is not None]
    def mean(n): x = [r['secs'] for r in rows[-n:]]; return sum(x) / len(x) if x else 0
    m20, m100 = mean(20), mean(100)
    recent = [r for r in rows if r.get('t') and now - r['t'] < 600]; span = min(600, now - min(r['t'] for r in recent)) if recent else 0
    rate = len(recent) / span * 60 if span > 60 else 0                    # cases per minute, whole service, last 10 minutes
    left = S_['left']; orig_pending = left.get('orig', 0)
    share = S_['runnable'] / max(1, S_['done'].get('orig', 1)); alt_left = sum(left.get(d, 0) for d in REQUIRED) + orig_pending * share * len(REQUIRED)
    only = st.get('only', 'all')
    if only == 'orig': alt_left = 0
    elif only in REQUIRED: alt_left = left.get(only, 0) + orig_pending * share
    total_left = orig_pending + alt_left
    eta = total_left / rate * 60 if rate else total_left * (m100 or m20 or 10)
    beat_age = now - st['beat'] if st.get('beat') else None
    ws = st.get('workers', []); nact = sum(1 for w in ws if w.get('case'))
    emus = [k for k in range(40) if (lambda s_: s_ and T.emu_mod().alive(s_))(read_json(os.path.join(ROOT, f'build/emu-{38020 + k}.json')))]
    mem = mem_avail_gb(); import shutil; disk = shutil.disk_usage(ROOT).free / 1e9
    nclass = collections.Counter(v['verdict'] for v in classes.values())
    if a.short:
        print(f'sweep {"RUNNING" if pid else "STOPPED"} {st.get("phase", "?")} {nact}/{st.get("n", "?")} workers | orig {S_["done"].get("orig", 0)}/{S_["cases"]} reorder {S_["done"].get("reorder", 0)} readable {S_["done"].get("readable", 0)} '
              f'| PASS {c.get("PASS", 0)} FAIL {c.get("FAIL", 0)} NR {c.get("NOT-RUNNABLE", 0)} HANG {c.get("HANG", 0)} | {rate:.1f} cases/min | ETA {fmt_dur(eta)} '
              f'| beat {fmt_dur(beat_age) if beat_age is not None else "-"} ago, {len(emus)} emus, load {os.getloadavg()[0]:.1f}, RAM {mem:.0f} GB free{", PAUSED " + st["paused"] if st.get("paused") else ""}')
        return
    print(f'sweep service: {"RUNNING pid %d" % pid if pid else "NOT RUNNING"}; phase {st.get("phase", "?")}; workers {nact} busy of {st.get("allowed", "?")} allowed ({st.get("n", "?")} configured); '
          f'started {fmt_dur(now - st["started"]) + " ago" if st.get("started") else "-"}; guards: load {os.getloadavg()[0]:.1f}, RAM {mem:.0f} GB'
          f'{", PAUSED " + st["paused"] if st.get("paused") else ""}')
    print(f'plan {S_["cases"]} cases (variant 0); original disc: {S_["done"].get("orig", 0)} done, {orig_pending} left; ' + '; '.join(
        f'{d}: {S_["done"].get(d, 0)} done, {left.get(d, 0)} left' for d in REQUIRED))
    print('status of the sections: ' + ', '.join(f'{k} {v}' for k, v in sorted(c.items())) + (f'; flake classification: {dict(nclass)}' if nclass else '')
          + (f'; ended host (overload, retried after the load drops, never a FAIL): {len(HOST_LAST)} cases, {sum(1 for k in HOST_LAST if HOST_N[k] >= HOST_TRIES)} unresolved' if HOST_LAST else ''))
    print(f'rate {rate:.1f} cases/min over the last 10 min; seconds per case (all workers, last 20 / 100): {m20:.1f} / {m100:.1f}; work left ~{total_left:.0f} cases; ETA {fmt_dur(eta)}')
    print(f'service heartbeat {fmt_dur(beat_age) if beat_age is not None else "-"} ago; emulators alive: {len(emus)}; free disk {disk:.0f} GB; log {LOGF}')
    perw = collections.defaultdict(list)
    for r in rows[-300:]:
        if r.get('w'): perw[r['w']].append(r['secs'])
    for w in ws:
        x = perw.get(w['port'], [])
        print(f'  worker {w["port"]}: {(w.get("case") or "idle"):>10} {(w.get("disc") or ""):8} beat {fmt_dur(now - w["beat"]) if w.get("beat") else "-":>6} ago, restarts {w.get("restarts", 0)}, '
              f'{sum(x) / len(x) if x else 0:5.1f} s/case over {len(x)}, {w.get("session") or {}}')


def cmd_cleanup(a): cleanup_states()


def cmd_classify(a):
    """Every FAIL: the class given by the reruns and the first differing events."""
    plan = {c['id']: c for c in load_plan()}; last, _, classes = last_rows(); n = 0
    for (d, cid), r in sorted(last.items()):
        o = last.get(('orig', cid))
        if d in ('orig', 'orig2') or not o or not runnable(o): continue
        v = compare(o, r)
        if v in ('same', 'relaxed'): continue
        n += 1; cl = classes.get((d, cid), {}).get('verdict', 'unclassified')
        print(f'{cid} on {d}: {v} [{cl}]  n {o.get("n")} vs {r.get("n")}, ends {o.get("end")} vs {r.get("end")}')
        try:
            eo = T.parse_trace(open(trace_path(cid, 'orig')).read(), scripts_of('orig')); ea = T.parse_trace(open(trace_path(cid, d)).read(), scripts_of(d))
            ko = [e['key'] for e in eo]; ka = [e['key'] for e in ea]
            i = next((i for i, (x, y) in enumerate(zip(ko, ka)) if x != y), min(len(ko), len(ka)))
            for j in range(max(0, i - 1), i + 2): print('   orig:', ko[j] if j < len(ko) else '(end)', '\n   alt: ', ka[j] if j < len(ka) else '(end)')
        except Exception as e: print('   (no trace diff:', e, ')')
    print(n, 'differences')


def cmd_selftest(a):
    """The normalized comparison (`relaxed_events`) against the layout-only changes it must forgive and the behavior changes it must catch, on
    real traces of the ledger (mutated offline: the same events, one edit). Exit 1 on a failure."""
    import copy
    def load(cid, disc='orig'): return T.parse_trace(open(trace_path(cid, disc)).read(), scripts_of(disc))
    def dg(ev): return relaxed_digest(ev)
    def kind(ev, op, nth=0): return [i for i, e in enumerate(ev) if e['kind'] == 'I' and e['op'] == op][nth]
    results = []
    def check(name, ok): results.append(ok); print(('ok   ' if ok else 'FAIL ') + name)
    base = load('163:6:0'); ref = dg(base)
    # layout-only edits: forgiven
    ev = copy.deepcopy(base); i = kind(ev, 0x1B, 1)                       # the second SET_DIALOG_OWNER (the same owner) sits between the first two boxes
    chained = [e for k, e in enumerate(ev) if k != i]
    check('dropping a SET_DIALOG_OWNER between two SHOW_TEXTBOX is CAUGHT (the engine chains the two boxes)', dg(chained) != ref)
    ev = copy.deepcopy(base); k0 = kind(ev, 0x1A, 0); w0 = next(n for n, e in enumerate(base) if e['kind'] == 'W')
    jmp = dict(kind='I', key='I 163:6+999 JUMP_TO #00000000 ->6+1000', frame=0, rand=ev[k0]['rand'], raw=b'\x16\x00\x00\x00', sid=163, sec=6, rel=999, op=0x16)
    check('a JUMP_TO right after the section start is forgiven', dg(ev[:k0 - 1] + [jmp] + ev[k0 - 1:]) == ref if k0 > 0 else True)
    ev2 = ev[:k0 + 1] + [jmp] + ev[k0 + 1:]
    check('a JUMP_TO inside a box run (SHOW_TEXTBOX, JUMP_TO, SDO, SHOW_TEXTBOX) is neutral where an SDO already stood', dg(ev2) == ref)
    ev3 = [e for k, e in enumerate(base) if k != i]; ev3.insert(i, jmp)
    check('a JUMP_TO instead of the SET_DIALOG_OWNER between two boxes is forgiven (both are not chained)', dg(ev3) == ref)
    redundant = copy.deepcopy(base[kind(base, 0x1B, 0)]); redundant['key'] = 'I 163:6+5 SET_DIALOG_OWNER #deadbeef'
    check('a repeated SET_DIALOG_OWNER outside two SHOW_TEXTBOX (after the first one, before the first box) is forgiven', dg(base[:kind(base, 0x1B, 0) + 1] + [redundant] + base[kind(base, 0x1B, 0) + 1:]) == ref)
    ifx = dict(jmp, key='I 163:6+998 IF #12345678 ->6+1000', raw=b'\x19', op=0x19)
    check('an IF more (a test split over two IFs, or negated) is forgiven', dg(ev[:k0 - 1] + [ifx] + ev[k0 - 1:]) == ref if k0 > 0 else True)
    check('an IF between two boxes still breaks the chain (BREAK kept)', dg([e for k, e in enumerate(base) if k != i][:i] + [ifx] + [e for k, e in enumerate(base) if k != i][i:]) == ref)
    amb = dict(kind='S', key='S 1 11', frame=30)
    check('an ambient sound (an entity timer, bank 1) more, or at another time, is forgiven', dg(base[:k0 + 2] + [amb] + base[k0 + 2:]) == ref and dg([amb] + base[3:]) != 'x')
    # behavior edits: caught
    for what, edit in (('a state write with another value', lambda e: [dict(x, key=x['key'] + '1') if n == w0 else x for n, x in enumerate(e)]),
                       ('a state write missing', lambda e: [x for n, x in enumerate(e) if n != w0]),
                       ('a sound missing', lambda e: [x for n, x in enumerate(e) if not (x['kind'] == 'S' and n == next(m for m, y in enumerate(e) if y['key'].startswith('S 0 ') and m > 5))]),
                       ('an operand changed', lambda e: [dict(x, key=x['key'][:-8] + 'abcdef01') if x['kind'] == 'I' and x['op'] == 0x1C else x for x in e]),
                       ('a text row changed', lambda e: [dict(x, key=x['key'][:-8] + '00000000') if x['kind'] == 'I' and x['op'] == 0x1A else x for x in e]),
                       ('two instructions swapped', lambda e: e[:5] + [e[6], e[5]] + e[7:] if e[5]['kind'] == 'I' and e[6]['kind'] == 'I' else e[:5] + [e[7], e[5], e[6]] + e[8:]),
                       ('an instruction missing', lambda e: [x for n, x in enumerate(e) if n != kind(e, 0x1C)])):
        try: check('caught: ' + what, dg(edit(copy.deepcopy(base))) != ref)
        except Exception as ex: check(f'caught: {what} (edit failed: {ex})', False)
    print('selftest:', 'all passed' if all(results) else 'FAILED'); sys.exit(0 if all(results) else 1)


def cmd_reset(a):
    """After `discs readable` (the disc was rebuilt): the results of that disc so far are void, its cases are pending again. The ledger only grows: a `reset`
    row is appended. Run it with the service stopped, or the cases it is running on that disc are lost (they are recorded after the row and count)."""
    append(dict(kind='reset', disc=a.disc, why=a.why)); print(f'reset: the results of {a.disc} before now are void; `start` runs them again')


def cmd_discs(a):
    if a.which in ('reorder', 'all'):
        print('reorder: %d chunks moved' % build_reorder())
    if a.which in ('readable', 'all'):
        if getattr(a, 'regen', False):          # story/base made again even if its stamp says it is up to date
            subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dws.py'), 'story-base', '--refresh'], check=True)
        print('readable: %d events generated from story/base, %d sections keep the disc\'s code' % build_readable())


def cmd_l1(a):
    same, diff, moved = static_l1(a.disc)
    print(f'{a.disc}: {same} sections with the same graph, {len(diff)} different, {moved} sections at another offset')
    for x in diff[:20]: print('  ', x)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('plan').set_defaults(f=cmd_plan)
    sub.add_parser('snapshots').set_defaults(f=cmd_snapshots)
    p = sub.add_parser('explore'); p.add_argument('--per-case', type=int, default=3); p.set_defaults(f=cmd_explore)
    p = sub.add_parser('report'); p.add_argument('--show', default='20'); p.set_defaults(f=cmd_report)
    p = sub.add_parser('l1'); p.add_argument('disc'); p.set_defaults(f=cmd_l1)
    p = sub.add_parser('discs'); p.add_argument('which', nargs='?', default='all'); p.add_argument('--regen', action='store_true', help='first make story/base again (dws story-base --refresh)'); p.set_defaults(f=cmd_discs)
    p = sub.add_parser('serve'); p.add_argument('--disc', default='all'); p.add_argument('--order', default='main-first'); p.add_argument('--workers', type=int, default=12); p.set_defaults(f=cmd_serve)
    p = sub.add_parser('worker'); p.add_argument('--disc', default='all'); p.add_argument('--order', default='main-first'); p.set_defaults(f=cmd_worker)
    p = sub.add_parser('bench'); p.add_argument('--workers', type=int, default=12); p.add_argument('--count', type=int, default=20); p.add_argument('--chunk', type=int, default=2); p.set_defaults(f=cmd_bench)
    p = sub.add_parser('start'); p.add_argument('--disc', default='all', choices=['all', 'orig', 'reorder', 'readable']); p.add_argument('--order', default='main-first', choices=['main-first', 'plain']); p.add_argument('--workers', type=int, default=12, help='parallel emulators, 1..14 (default 12)'); p.add_argument('--pin-random', action='store_true', help='STORE_RANDOM draws from a generator set by the instruction count (only for a campaign whose original disc is run with it too)'); p.set_defaults(f=cmd_start)
    sub.add_parser('stop').set_defaults(f=cmd_stop)
    p = sub.add_parser('status'); p.add_argument('--short', action='store_true'); p.set_defaults(f=cmd_status)
    p = sub.add_parser('reset'); p.add_argument('disc'); p.add_argument('--why', default='disc rebuilt'); p.set_defaults(f=cmd_reset)
    sub.add_parser('selftest').set_defaults(f=cmd_selftest); sub.add_parser('cleanup').set_defaults(f=cmd_cleanup); sub.add_parser('classify').set_defaults(f=cmd_classify)
    p = sub.add_parser('run'); p.add_argument('--disc', default='orig'); p.add_argument('--scripts'); p.add_argument('--screens'); p.add_argument('--only', help='case ids, e.g. 163:6:0,164:5:0 (also variants)'); p.add_argument('--force', action='store_true', help='also the cases that have a row (a skipped one: run it now)')
    p.add_argument('--limit', type=int, default=0); p.add_argument('--variants', action='store_true'); p.set_defaults(f=cmd_run)
    a = ap.parse_args(); a.f(a)


if __name__ == '__main__':
    main()
