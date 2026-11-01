"""Who is where and why: NPC presence read out of MAPHEAD's setup sections and written as declarations (docs/mods/city-rules.md).

The original decides which Digimon stand on a screen in the screen's MAPHEAD section: `IF` chains over triggers, prosperity,
the clock and a random draw, then LOAD_DIGIMON / SET_DIGIMON. That is code, but a pure function of the state. This module

  * decodes the sections (`parse_maphead`),
  * explores every path of a section symbolically (`explore`): the state is constants (pstats the section sets itself, like the
    counter p42) and symbols (triggers, pstats it reads, the clock after STORE_DATE, a STORE_RANDOM draw, the partner type), a branch
    on a symbol forks the path, a branch on constants does not,
  * gives for each (slot, species) the condition under which it is placed (`presence_rules`), the declaration:

        presence {
            screen(205) {                                   // MAPHEAD section 205, Jijimon's house
                npc Jijimon slot 0 talks;
                npc Angemon slot 1 talks when recruited(Angemon);
            }
        }

  * runs the original instructions on a concrete state (`oracle`) and the declarations on the same state (`evaluate`): `city-verify` compares
    them on a grid of states; `dws why NPC` prints the matching rule and the state it depends on.

Conditions are trees: ('and', [..]) ('or', [..]) ('not', x) ('true',) and atoms ('trig', n), ('cmp', var, op, v) with var one of
`pN` (a pstat, p1 is the prosperity), `clock.year|day|hour|minute`, `rollK` (the K-th STORE_RANDOM of the section, 0..max),
`partner.type`, `statN`."""
import os, re, sys, itertools, random
from .diag import DwsError

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAPHEAD = os.path.join(ROOT, 'extracted', 'SCN', 'MAPHEAD.SCN')
_CACHE = {}


# ------------------------------------------------------------------ decoding
def maphead_text():
    if 'text' not in _CACHE:
        import tempfile
        d = tempfile.mkdtemp(prefix='mh-', dir=os.path.join(ROOT, 'build') if os.path.isdir(os.path.join(ROOT, 'build')) else None)
        if os.path.join(ROOT, 'tools') not in sys.path: sys.path.insert(0, os.path.join(ROOT, 'tools'))
        from dws import bytecode
        r = bytecode.dis(MAPHEAD, d)
        if r.returncode: raise DwsError(f'bytecode dis {MAPHEAD}: {r.stderr.strip()}', None)
        _CACHE['text'] = open(os.path.join(d, 'maphead.scn.txt'), encoding='utf-8').read()
        import shutil; shutil.rmtree(d, ignore_errors=True)
    return _CACHE['text']


INSTR = re.compile(r'^\s+([A-Z][A-Z0-9_]*)\b\s*(.*?)\s*(?:;.*)?$')
LABEL = re.compile(r'^([A-Za-z_][\w.]*):')
SECT = re.compile(r'^\.section\s+(\d+)\s+(\S+)')


class Program:
    """ins: [(mnemonic, argstring)], labels: {name: index}, sections: {id: index}"""
    def __init__(self, text):
        self.ins = []; self.labels = {}; self.sections = {}; names = {}
        for line in text.split('\n'):
            m = SECT.match(line)
            if m: names[m.group(2)] = int(m.group(1)); continue
            if re.match(r'^\s+"', line): continue
            m = LABEL.match(line)
            if m: self.labels[m.group(1)] = len(self.ins); continue
            m = INSTR.match(line)
            if m and not line.lstrip().startswith(('.', ';')): self.ins.append((m.group(1), m.group(2)))
        for nm, sid in names.items():
            if nm in self.labels: self.sections.setdefault(sid, self.labels[nm])


def program():
    if 'prog' not in _CACHE: _CACHE['prog'] = Program(maphead_text())
    return _CACHE['prog']


def parse_if(args):
    """`trigger 5, and not trigger 6, or p3 >= 4, else L9` -> ([(join, atom)], label); atom = ('trig', n, neg) | ('cmp', var, op, v)"""
    parts = [p.strip() for p in args.split(', ')]
    m = re.match(r'else (\S+)$', parts[-1]); assert m, args
    out = []
    for p in parts[:-1]:
        join = None
        for j in ('and ', 'or '):
            if p.startswith(j): join = j.strip(); p = p[len(j):]; break
        neg = False
        if p.startswith('not '): neg = True; p = p[4:]
        m = re.match(r'trigger (\d+)$', p)
        if m: out.append((join, ('trig', int(m.group(1)), neg))); continue
        m = re.match(r'p(\d+) (==|!=|>=|<=|>|<) (-?\d+)$', p)
        if m: out.append((join, ('cmp', f'p{m.group(1)}', m.group(2), int(m.group(3)), neg))); continue
        m = re.match(r'stat (\d+) (==|!=|>=|<=|>|<) (-?\d+)$', p)
        if m: out.append((join, ('cmp', f'stat{m.group(1)}', m.group(2), int(m.group(3)), neg))); continue
        raise DwsError(f'presence: unknown IF clause "{p}"')
    return out, parts[-1].split()[1]


OPS = {'==': lambda a, b: a == b, '!=': lambda a, b: a != b, '>=': lambda a, b: a >= b, '<=': lambda a, b: a <= b,
       '>': lambda a, b: a > b, '<': lambda a, b: a < b}
NEG = {'==': '!=', '!=': '==', '>=': '<', '<': '>=', '>': '<=', '<=': '>'}


# ------------------------------------------------------------------ the original, run on a concrete state (the oracle)
class Concrete:
    def __init__(self, triggers=(), pstats=None, clock=(0, 0, 9, 0), rolls=(), partner=0, stats=None):
        self.triggers = set(triggers); self.p = dict(pstats or {}); self.clock = clock; self.rolls = list(rolls)
        self.partner = partner; self.stats = dict(stats or {})


def run_original(sec, st, limit=20000):
    """-> (placements {slot: (species, talk)}, effects [..]) of MAPHEAD section `sec` on the concrete state `st`"""
    prog = program(); i = prog.sections[sec]; p = dict(st.p); trig = set(st.triggers); place = {}; effects = []; roll = 0
    for _ in range(limit):
        op, a = prog.ins[i]; i += 1
        if op == 'END_SECTION' or op == 'END_SCRIPT': break
        elif op == 'JUMP_TO': i = prog.labels[a.split()[0]]
        elif op == 'IF':
            clauses, lab = parse_if(a); res = None
            for join, at in clauses:
                if at[0] == 'trig': v = (at[1] in trig) != at[2]
                else:
                    var = at[1]
                    val = st.stats.get(int(var[4:]), 0) if var.startswith('stat') else p.get(int(var[1:]), 0)
                    v = OPS[at[2]](val, at[3]) != at[4]
                res = v if res is None or join is None else ((res and v) if join == 'and' else (res or v))
            if not res: i = prog.labels[lab]
        elif op == 'SET_PSTAT': m = re.match(r'p(\d+), (-?\d+)', a); p[int(m.group(1))] = int(m.group(2))
        elif op == 'ADD_TO_PSTAT': m = re.match(r'p(\d+), (-?\d+)', a); p[int(m.group(1))] = p.get(int(m.group(1)), 0) + int(m.group(2))
        elif op == 'STORE_DATE':
            b = int(a[1:]); p[b], p[b + 1], p[b + 2], p[b + 3] = st.clock
        elif op == 'STORE_RANDOM':
            m = re.match(r'p(\d+), (\d+)', a); v = st.rolls[roll] if roll < len(st.rolls) else 0; roll += 1
            p[int(m.group(1))] = min(v, int(m.group(2)))
        elif op == 'STORE_DIGIMON_TYPE': p[int(a[1:])] = st.partner
        elif op == 'SET_DIGIMON':
            s, slot, talk = (int(x) for x in a.split(', ')); place[slot] = (s, talk)
        elif op == 'SET_TRIGGER': trig.add(int(a)); effects.append(op + ' ' + a)
        elif op == 'UNSET_TRIGGER': trig.discard(int(a)); effects.append(op + ' ' + a)
        elif op in ('LOAD_DIGIMON',): pass
        else: effects.append(op + ' ' + a)
    else:
        raise DwsError(f'presence: section {sec} did not end in {limit} steps')
    return place, effects


# ------------------------------------------------------------------ the symbolic exploration
class Unsupported(Exception):
    pass


def tnot(c):
    if c[0] == 'true': return ('false',)
    if c[0] == 'false': return ('true',)
    if c[0] == 'not': return c[1]
    return ('not', c)


def tand(xs):
    out = []
    for x in xs:
        if x[0] == 'false': return ('false',)
        if x[0] == 'true': continue
        if x[0] == 'and': out += list(x[1])
        else: out.append(x)
    if not out: return ('true',)
    return out[0] if len(out) == 1 else ('and', out)


def tor(xs):
    out = []
    for x in xs:
        if x[0] == 'true': return ('true',)
        if x[0] == 'false': continue
        if x[0] == 'or': out += list(x[1])
        else: out.append(x)
    if not out: return ('false',)
    return out[0] if len(out) == 1 else ('or', out)


def sym_atom(at, env):
    """An IF clause in the symbolic state -> ('true',) | ('false',) | an atom tree"""
    if at[0] == 'trig':
        a = ('trig', at[1]); return tnot(a) if at[2] else a
    _, var, op, v, neg = at
    val = env.get(var, ('sym', var))
    if val[0] == 'const':
        r = OPS[op](val[1], v) != neg; return ('true',) if r else ('false',)
    name = val[1]
    return ('not', ('cmp', name, op, v)) if neg else ('cmp', name, op, v)


def fold(clauses, env):
    res = None
    for join, at in clauses:
        v = sym_atom(at, env)
        res = v if res is None or join is None else (tand([res, v]) if join == 'and' else tor([res, v]))
    return res


class Space:
    """The state space a section looks at: every trigger it tests (2 values) and for every integer variable the intervals between the
    thresholds it is compared with. A set of states is a Python int (one bit per state), so a condition is evaluated for all states at once."""
    def __init__(self, trees, cap=1 << 22):
        trig = set(); cmps = {}

        def walk(c):
            if c[0] in ('and', 'or'):
                for x in c[1]: walk(x)
            elif c[0] == 'not': walk(c[1])
            elif c[0] == 'trig': trig.add(c[1])
            elif c[0] == 'cmp': cmps.setdefault(c[1], set()).add((c[2], c[3]))
        for c in trees: walk(c)
        self.feat = []          # (kind, name, values) with values: for a trigger (False, True); for a variable a list of (lo, hi)
        for n in sorted(trig): self.feat.append(('trig', n, [False, True]))
        for var, cs in sorted(cmps.items()):
            lo, hi = var_domain(var); cuts = set()
            for op, v in cs:
                cuts |= {'>=': {v}, '<=': {v + 1}, '>': {v + 1}, '<': {v}, '==': {v, v + 1}, '!=': {v, v + 1}}[op]
            cuts = sorted(x for x in cuts if lo < x <= hi); edges = [lo] + cuts + [hi + 1]
            self.feat.append(('var', var, [(edges[i], edges[i + 1] - 1) for i in range(len(edges) - 1)]))
        self.N = 1; self.stride = []
        for f in self.feat: self.stride.append(self.N); self.N *= len(f[2])
        if self.N > cap: raise Unsupported(f'{self.N} states to tell apart')
        self.full = (1 << self.N) - 1; self._m = {}; self.index = {(f[0], f[1]): k for k, f in enumerate(self.feat)}

    def value_mask(self, k, vi):
        key = (k, vi)
        if key not in self._m:
            s = self.stride[k]; r = len(self.feat[k][2]); period = s * r
            block = ((1 << s) - 1) << (vi * s)
            reps = (1 << self.N) - 1
            self._m[key] = block * (reps // ((1 << period) - 1)) & self.full
        return self._m[key]

    def atom(self, c):
        if c[0] == 'trig':
            k = self.index.get(('trig', c[1]))
            return self.value_mask(k, 1) if k is not None else 0
        _, var, op, v = c; k = self.index[('var', var)]; m = 0
        for vi, (lo, hi) in enumerate(self.feat[k][2]):
            if OPS[op](lo, v) and OPS[op](hi, v) if op in ('>=', '<=', '>', '<') else (OPS[op](lo, v) if lo == hi else (op == '!=' and not (lo <= v <= hi)) or (op == '==' and lo <= v <= hi and lo == hi)):
                m |= self.value_mask(k, vi)
        return m

    def mask(self, c):
        k = c[0]
        if k == 'true': return self.full
        if k == 'false': return 0
        if k == 'and':
            m = self.full
            for x in c[1]: m &= self.mask(x)
            return m
        if k == 'or':
            m = 0
            for x in c[1]: m |= self.mask(x)
            return m
        if k == 'not': return self.full & ~self.mask(c[1])
        return self.atom(c)

    def state(self, i):
        """-> a Concrete state for state number i"""
        st = Concrete(clock=[0, 0, 9, 0], rolls=[0] * 12); st.clock = list(st.clock)
        for k, f in enumerate(self.feat):
            vi = (i // self.stride[k]) % len(f[2])
            if f[0] == 'trig':
                if f[2][vi]: st.triggers.add(f[1])
            else:
                v = f[2][vi][0]; nm = f[1].split(':')[0]
                if re.fullmatch(r'p\d+', nm): st.p[int(nm[1:])] = v
                elif nm.startswith('stat'): st.stats[int(nm[4:])] = v
                elif nm == 'partner.type': st.partner = v
                elif nm.startswith('clock.'): st.clock['year day hour minute'.split().index(nm[6:])] = v
                elif nm.startswith('roll'): st.rolls[int(nm[4:]) - 1] = v
        st.clock = tuple(st.clock)
        return st

    def cover(self, on):
        """a short sum of products (a condition tree) for the set of states `on`: greedy prime implicants (espresso's expand and cover)"""
        if on == 0: return ('false',)
        if on == self.full: return ('true',)
        cubes = []; left = on
        while left:
            low = left & -left; s = low.bit_length() - 1
            cube = [{(s // self.stride[k]) % len(f[2])} for k, f in enumerate(self.feat)]
            cm = self.full
            for k, vs in enumerate(cube): cm &= self.value_mask(k, next(iter(vs)))
            for k, f in enumerate(self.feat):                    # widen each feature as far as the cube stays inside `on`
                if f[0] == 'trig':
                    alt = self.value_mask(k, 0) | self.value_mask(k, 1)
                    base = self.cube_mask([c if j != k else set(range(len(f[2]))) for j, c in enumerate(cube)])
                    if base & ~on == 0: cube[k] = set(range(len(f[2])))
                else:
                    lo = hi = next(iter(cube[k]))
                    while lo > 0 and self.cube_mask([c if j != k else set(range(lo - 1, hi + 1)) for j, c in enumerate(cube)]) & ~on == 0: lo -= 1
                    while hi < len(f[2]) - 1 and self.cube_mask([c if j != k else set(range(lo, hi + 2)) for j, c in enumerate(cube)]) & ~on == 0: hi += 1
                    cube[k] = set(range(lo, hi + 1))
            cm = self.cube_mask(cube); cubes.append((cube, cm)); left &= ~cm
        # drop a cube that the others cover
        keep = list(cubes)
        for cb in reversed(cubes):
            rest = 0
            for other in keep:
                if other is not cb: rest |= other[1]
            if cb[1] & ~rest == 0: keep.remove(cb)
        terms = [self.cube_tree(c) for c, _ in keep]
        return tor(terms)

    def cube_mask(self, cube):
        m = self.full
        for k, vs in enumerate(cube):
            if len(vs) < len(self.feat[k][2]):
                x = 0
                for vi in vs: x |= self.value_mask(k, vi)
                m &= x
        return m

    def cube_tree(self, cube):
        xs = []
        for k, vs in enumerate(cube):
            f = self.feat[k]
            if len(vs) == len(f[2]): continue
            if f[0] == 'trig':
                xs.append(('trig', f[1]) if True in [f[2][v] for v in vs] else ('not', ('trig', f[1])))
            else:
                lo, hi = f[2][min(vs)][0], f[2][max(vs)][1]; d = var_domain(f[1])
                if lo == hi: xs.append(('cmp', f[1], '==', lo))
                else:
                    if lo > d[0]: xs.append(('cmp', f[1], '>=', lo))
                    if hi < d[1]: xs.append(('cmp', f[1], '<=', hi))
        return tand(xs)


def flow(sec, limit=20000):
    """The section as a graph of states (pc, the symbolic pstats) without loops. -> (Space, {slot: {(species, talk): set of states that place it}}, number of nodes, graph)"""
    prog = program(); start = (prog.sections[sec], (), 0)
    edges = {}; emit = {}; stack = [start]; seen = {start}

    def key(env): return tuple(sorted(env.items()))
    while stack:
        s = stack.pop(); i, ek, nroll = s; env = dict(ek); out = []
        if len(seen) > limit: raise Unsupported('too many states (a loop?)')
        op, a = prog.ins[i]; i += 1
        if op in ('END_SECTION', 'END_SCRIPT'): pass
        elif op == 'JUMP_TO': out.append(((prog.labels[a.split()[0]], ek, nroll), ('true',)))
        elif op == 'IF':
            clauses, lab = parse_if(a); c = fold(clauses, env)
            if c[0] == 'true': out.append(((i, ek, nroll), ('true',)))
            elif c[0] == 'false': out.append(((prog.labels[lab], ek, nroll), ('true',)))
            else:
                out.append(((i, ek, nroll), c)); out.append(((prog.labels[lab], ek, nroll), tnot(c)))
        else:
            if op == 'SET_PSTAT': m = re.match(r'p(\d+), (-?\d+)', a); env[f'p{m.group(1)}'] = ('const', int(m.group(2)))
            elif op == 'ADD_TO_PSTAT':
                m = re.match(r'p(\d+), (-?\d+)', a); k = f'p{m.group(1)}'; cur = env.get(k)
                if cur is None or cur[0] != 'const': raise Unsupported(f'ADD_TO_PSTAT on the unknown {k}')
                env[k] = ('const', cur[1] + int(m.group(2)))
            elif op == 'STORE_DATE':
                b0 = int(a[1:])
                for k, nm in enumerate(('clock.year', 'clock.day', 'clock.hour', 'clock.minute')): env[f'p{b0 + k}'] = ('sym', nm)
            elif op == 'STORE_RANDOM':
                m = re.match(r'p(\d+), (\d+)', a); nroll += 1; env[f'p{m.group(1)}'] = ('sym', f'roll{nroll}:{m.group(2)}')
            elif op == 'STORE_DIGIMON_TYPE': env[f'p{a[1:]}'] = ('sym', 'partner.type')
            elif op == 'SET_DIGIMON':
                sp, slot, talk = (int(x) for x in a.split(', ')); emit.setdefault(s, []).append((slot, sp, talk))
            elif op in ('LOAD_DIGIMON', 'SET_SCRIPT', 'SET_BGM', 'SHOW_TEXTBOX', 'SET_TRIGGER', 'UNSET_TRIGGER', 'WARP_TO', 'SET_DIALOG_OWNER',
                        'SECTION_ON_EXIT', 'PLAY_SOUND', 'CALL_DIGIMON_ROUTINE', 'WAIT_FOR_ENTITY', 'DELAY', 'TELEPORT', 'JUMP_TO_FILE'): pass
            else: raise Unsupported(f'instruction {op}')
            out.append(((i, key(env), nroll), ('true',)))
        edges[s] = out
        for n, _ in out:
            if n not in seen: seen.add(n); stack.append(n)
    space = Space([g for out in edges.values() for _, g in out])
    indeg = {s: 0 for s in seen}
    for out in edges.values():
        for n, _ in out: indeg[n] += 1
    if indeg[start]: raise Unsupported('the section is entered from inside (a loop)')
    gmask = {}
    reach = {start: space.full}; ready = [start]; done = 0
    while ready:
        s = ready.pop(); done += 1; r = reach.get(s, 0)
        for n, g in edges.get(s, []):
            if r:
                gk = repr(g)
                if gk not in gmask: gmask[gk] = space.mask(g)
                reach[n] = reach.get(n, 0) | (r & gmask[gk])
            indeg[n] -= 1
            if indeg[n] == 0: ready.append(n)
    if done != len(seen): raise Unsupported('the section has a loop')
    res = {}
    for s, em in emit.items():
        for slot, sp, talk in em:
            d = res.setdefault(slot, {}); d[(sp, talk)] = d.get((sp, talk), 0) | reach.get(s, 0)
    return space, res, len(seen), (start, edges, emit, reach)


def presence_rules(sec):
    """-> [(slot, species, talk, condition)] sorted by slot, and the number of graph nodes; the condition is where the SET_DIGIMON is reached,
    as a flat sum of products over triggers and intervals"""
    space, res, n, _ = flow(sec); out = []
    for slot in sorted(res):
        for (sp, talk), on in sorted(res[slot].items()):
            if on: out.append((slot, sp, talk, space.cover(on)))
    return out, n


INF = 10 ** 9


def var_domain(var):
    """(lo, hi) of a variable: the clock fields and the random draw are bounded, the rest are bytes/words"""
    if var.startswith('roll'): return (0, int(var.split(':')[1]))
    if var == 'clock.hour': return (0, 23)
    if var == 'clock.minute': return (0, 59)
    if var == 'clock.day': return (0, 29)
    if var == 'clock.year': return (0, 99)
    return (-INF, INF)


def circuit(sec):
    """The section as named conditions: one per branch point that is joined or that places a Digimon, each the OR of (its predecessors' condition AND the branch's test).
    -> (lets [(name, condition)], rules [(slot, species, talk, condition)]); linear in the size of the code, where the flat form can explode"""
    space, res, n, (start, edges, emit, reach) = flow(sec)
    pred = {}
    for s, out in edges.items():
        for nx, g in out: pred.setdefault(nx, []).append((s, g))
    indeg = {s: 0 for s in edges}
    for out in edges.values():
        for nx, _ in out: indeg[nx] = indeg.get(nx, 0) + 1
    order = []; ready = [start]; deg = dict(indeg)
    while ready:
        s = ready.pop(); order.append(s)
        for nx, _ in edges.get(s, []):
            deg[nx] -= 1
            if deg[nx] == 0: ready.append(nx)
    form = {}; lets = []
    for s in order:
        if not reach.get(s): form[s] = ('false',); continue
        if s == start: f = ('true',)
        else:
            f = tor([tand([form[p], g]) for p, g in pred[s] if form[p][0] != 'false'])
        if f[0] not in ('true', 'false') and f[0] != 'ref' and (s in emit or len(pred.get(s, [])) > 1):
            name = f'r{len(lets) + 1}'; lets.append((name, f)); f = ('ref', name)
        form[s] = f
    by = {}
    for s, em in emit.items():
        for slot, sp, talk in em:
            if reach.get(s): by.setdefault((slot, sp, talk), []).append(form[s])
    rules = [(slot, sp, talk, tor(cs)) for (slot, sp, talk), cs in sorted(by.items())]
    used = set()

    def walk(c):
        if c[0] == 'ref': used.add(c[1])
        elif c[0] in ('and', 'or'):
            for x in c[1]: walk(x)
        elif c[0] == 'not': walk(c[1])
    for r in rules: walk(r[3])
    changed = True
    while changed:
        changed = False
        for name, f in reversed(lets):
            if name in used:
                before = len(used); walk(f); changed |= len(used) != before
    return [(nm, f) for nm, f in lets if nm in used], rules


FLAT_LIMIT = 500          # characters of the longest flat condition of a screen; above it the screen is written as named conditions


def screen_form(sid):
    """-> {'lets': [(name, cond)], 'npcs': [(slot, species, talk, cond)], 'form': 'flat' | 'circuit'}"""
    rules, _ = presence_rules(sid)
    if not rules or max(len(cond_text(r[3])) for r in rules) <= FLAT_LIMIT:
        return {'lets': [], 'npcs': rules, 'form': 'flat'}
    lets, crules = circuit(sid)
    return {'lets': lets, 'npcs': crules, 'form': 'circuit'}


# ------------------------------------------------------------------ evaluating a condition tree (declarations) on a concrete state
def var_value(var, st):
    if re.fullmatch(r'p\d+', var): return st.p.get(int(var[1:]), 0)
    if var.startswith('stat'): return st.stats.get(int(var[4:]), 0)
    if var == 'partner.type': return st.partner
    if var.startswith('clock.'): return st.clock[('year', 'day', 'hour', 'minute').index(var[6:])]
    if var.startswith('roll'): k = int(var[4:].split(':')[0]); return st.rolls[k - 1] if k - 1 < len(st.rolls) else 0
    raise DwsError(f'unknown variable {var}')


def holds(c, st, env=None):
    k = c[0]
    if k == 'true': return True
    if k == 'false': return False
    if k == 'and': return all(holds(x, st, env) for x in c[1])
    if k == 'or': return any(holds(x, st, env) for x in c[1])
    if k == 'not': return not holds(c[1], st, env)
    if k == 'ref': return env[c[1]]
    if k == 'trig': return c[1] in st.triggers
    if k == 'cmp': return OPS[c[2]](var_value(c[1].split(':')[0], st), c[3])
    raise DwsError(f'bad condition {c}')


def evaluate(screen, st):
    """a screen ({'lets', 'npcs'}) on a concrete state -> {slot: (species, talk)} (a later rule of the same slot wins, like a later SET_DIGIMON)"""
    env = {}
    for name, f in screen['lets']: env[name] = holds(f, st, env)
    place = {}
    for slot, s, talk, cond in screen['npcs']:
        if holds(cond, st, env): place[slot] = (s, talk)
    return place


# ------------------------------------------------------------------ text
def species_label(s):
    from . import city
    return city.species_text(s)


def atom_text(c):
    from . import city
    if c[0] == 'trig':
        n = c[1]
        if 200 <= n < 312: return f'recruited({city.species_text(n - 200)})'
        if 0x8070 <= n < 0x8400: return f'recruited({city.species_text(n - 0x8000)})'
        return f'trigger({n})'
    _, var, op, v = c
    name = var.split(':')[0]
    if name == 'p1': return f'prosperity {op} {v}'
    if re.fullmatch(r'p\d+', name): return f'pstat({name[1:]}) {op} {v}'
    if name.startswith('stat'): return f'stat({name[4:]}) {op} {v}'
    if name.startswith('roll'): return f'roll({name[4:]}) {op} {v}'
    return f'{name} {op} {v}'


def cond_text(c, top=True):
    k = c[0]
    if k == 'true': return 'always'
    if k == 'false': return 'never'
    if k == 'trig' or k == 'cmp': return atom_text(c)
    if k == 'ref': return c[1]
    if k == 'not':
        x = c[1]
        if x[0] == 'trig': return f'not {atom_text(x)}'
        if x[0] == 'cmp': return atom_text(('cmp', x[1], NEG[x[2]], x[3]))
        return f'not ({cond_text(x, False)})'
    if k == 'and':
        t = ' and '.join(cond_text(x, False) if x[0] != 'or' else f'({cond_text(x, False)})' for x in c[1])
        return t
    if k == 'or':
        return ' or '.join(cond_text(x, False) if x[0] != 'and' else cond_text(x, False) for x in c[1])
    raise DwsError(f'bad condition {c}')


# ------------------------------------------------------------------ the screens
def screens():
    """MAPHEAD section ids < 255 that have a SET_SCRIPT (a screen's setup): {id: name}"""
    from . import city
    from dws import bytecode
    prog = program(); out = []
    for sid, idx in sorted(prog.sections.items()):
        if sid > 254: continue
        # a screen section does SET_SCRIPT near its start (before the first branch)
        for j in range(idx, min(idx + 4, len(prog.ins))):
            if prog.ins[j][0] == 'SET_SCRIPT': out.append(sid); break
    return out


def screen_name(sid):
    from dws import bytecode
    return bytecode.names()['M'].get(sid, '')


# ------------------------------------------------------------------ extraction and verification over the whole disc
def extract_all(only=None):
    """-> ({screen: {'lets', 'npcs', 'form'}}, {screen: reason}) for the screens whose setup section can be read"""
    out = {}; skipped = {}
    for sid in (only or screens()):
        try:
            sc = screen_form(sid)
        except Unsupported as e:
            skipped[sid] = str(e); continue
        except (KeyError, DwsError, AssertionError) as e:
            skipped[sid] = f'{type(e).__name__}: {e}'; continue
        if sc['npcs']: out[sid] = sc          # screens without any placement are not presence declarations
    return out, skipped


def verify_screen(sid, screen, rng, cap=30000):
    """the declarations of one screen against the original instructions, run on states built from every threshold the original code tests
    -> (states compared, all of them?, the first mismatch (state, original, declaration) or None)"""
    space = flow(sid)[0]
    if space.N <= cap: idx = range(space.N)
    else: idx = [rng.randrange(space.N) for _ in range(cap)] + [0, space.N - 1]
    n = 0
    for i in idx:
        st = space.state(i); want, _ = run_original(sid, st); got = evaluate(screen, st); n += 1
        if want != got: return n, False, (st, want, got)
    return n, space.N <= cap, None
