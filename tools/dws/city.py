"""The city rules as data (docs/mods/city-rules.md).

A `city { }` declaration holds the rules the original keeps as C code:

    city {
        prosperity {                         // recalculatePPandArena, main.c:3971: for a species the first line that names it counts
            species Numemon, Sukamon, Nanimon: 1 when level >= 3;
            species 3..=58: level - 2 when level >= 3;
        }
        revival {                            // murd.c:769, dooa.c:1690: ordered rows like top_map
            screen(205) when recruited(Angemon) or recruited(Monzaemon) or prosperity >= 50;
            default screen(218);
        }
        top_map {                            // getFileCityTopMap, map.c:5716: ordered rows, the first that holds wins
            screen(179) when recruited(Monzaemon) and recruited(Angemon) and recruited(Birdramon) and recruited(Vegiemon);
            ...
            default screen(168);
        }
        shop_maps: [131, 133, ...];          // SHOP_MAPS, script_common.c:325
        arena_maps: [208, 223];              // ARENA_MAPS, script_common.c:242
        start { screen: 204; exit: 9; ... }  // initializeDefaultSavegame, main_menu.c:3830
    }

`encode()` turns it into the table that the story-state engine reads (`city_rules.c`, the format is in dw/city.h of the
decomp), `decode()` turns a table back into the declaration, `evaluate()` is the reference evaluation in Python (used by
`dws why` and by the tests), `extract_original()` reads the original rules out of the decomp's C sources.

A block that a declaration leaves out is not in the table (its offset is 0): the engine uses its built-in default, which
is the original rule."""
import os, re, struct, subprocess
from .diag import DwsError

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SECTION = 1260
MAGIC = 0x5943
VERSION = 1
BLOCKS = ['prosperity', 'top_map', 'revival', 'start', 'shop_maps', 'arena_maps']
INV_MAX = 30
# atom kinds of the table (dw/city.h)
TRIG_SET, TRIG_CLEAR, PSTAT_GE, PSTAT_LT, REC, NOT_REC = range(6)
PROSPERITY_PSTAT = 1
ORIGINAL_SRC = os.path.join(ROOT, 'decomp', 'src')


# ------------------------------------------------------------------ names
def _species():
    from . import backend
    n = backend.names()['species']
    rev = {}
    for k, v in n.items():
        rev.setdefault(v, k)
    return n, rev


def _items():
    from . import backend
    n = backend.names()['item']
    rev = {}
    for k, v in n.items():
        rev.setdefault(v, k)
    cnt = {}
    for k, v in n.items():
        cnt[k] = cnt.get(k, 0) + 1
    return n, rev, cnt


def species_name(i):
    n, rev = _species()
    for k, v in n.items():
        if v == i and k.isidentifier():
            return k.capitalize() if k.islower() else k
    return str(i)


def species_text(i):
    """A species as it is written in a declaration: its name when the name is a plain word and resolves back, else the number."""
    n, rev = _species()
    nm = rev.get(i)
    if nm and nm.isidentifier() and n.get(nm) == i:
        return nm[0].upper() + nm[1:]
    return str(i)


def item_text(i):
    n, rev, cnt = _items()
    nm = rev.get(i)
    if nm and cnt.get(nm) == 1 and n.get(nm) == i:
        return f'item("{nm}")'
    return f'item({i})'


# ------------------------------------------------------------------ the declaration model
def empty_spec():
    return {}


def cond_always():
    return []


def atom_text(a):
    k, arg, v = a
    if k == TRIG_SET: return f'trigger({v})'
    if k == TRIG_CLEAR: return f'not trigger({v})'
    if k == PSTAT_GE: return 'prosperity >= %d' % v if arg == PROSPERITY_PSTAT else f'pstat({arg}) >= {v}'
    if k == PSTAT_LT: return 'prosperity < %d' % v if arg == PROSPERITY_PSTAT else f'pstat({arg}) < {v}'
    if k == REC: return f'recruited({species_text(v)})'
    if k == NOT_REC: return f'not recruited({species_text(v)})'
    raise ValueError(a)


def cond_text(c):
    if not c: return 'always'
    return ' or '.join(' and '.join(atom_text(a) for a in clause) if clause else 'always' for clause in c)


# ------------------------------------------------------------------ the binary table
# 16-bit little-endian words, so the R3000 reads them aligned (dw/city.h of the decomp has the layout):
#   header  magic, version, then CITY_BLOCKS word offsets (from the start of the table; 0 = block not there)
#   cond    n clauses, each: n atoms, each atom 2 words: kind | pstat << 8, value
def _w(v, what='value'):
    if not 0 <= v <= 0xFFFF: raise DwsError(f'city: {what} {v} does not fit 16 bits')
    return v


def enc_cond(c):
    out = [len(c)]
    for clause in c:
        out.append(len(clause))
        for k, arg, v in clause:
            out += [k | (arg << 8), _w(v, 'trigger or value')]
    return out


def enc_block(name, d):
    if name == 'prosperity':
        out = [len(d)]
        for r in d:
            if not -32768 <= r['add'] <= 32767 or not 0 <= r['per_level'] < 256 or not 0 <= r['min_level'] < 256:
                raise DwsError('city: prosperity weight out of range')
            out += [_w(r['first']), _w(r['last']), r['min_level'] | (r['per_level'] << 8), r['add'] & 0xFFFF]
        return out
    if name in ('top_map', 'revival'):
        out = [_w(d['default']), len(d['rows'])]
        for row in d['rows']:
            out += [_w(row['screen'])] + enc_cond(row['when'])
        return out
    if name == 'start':
        inv = d['inventory']
        if len(inv) > INV_MAX: raise DwsError(f'city: the start inventory has {len(inv)} stacks, the savegame holds {INV_MAX}')
        for x in ('exit', 'lives', 'age', 'hour', 'minute'):
            if not 0 <= d[x] < 256: raise DwsError(f'city: start {x} {d[x]} does not fit 8 bits')
        cs = d['card_shop']
        bits = d['bits'] & 0xFFFFFFFF
        out = [_w(d['screen']), d['exit'] | (d['lives'] << 8), _w(d['partner']), _w(d['lifetime']), d['age'] | (d['hour'] << 8),
               d['minute'], bits & 0xFFFF, bits >> 16, cs[0] | (cs[1] << 8), cs[2] | (cs[3] << 8), cs[4] | (cs[5] << 8)]
        for ty, n in list(inv) + [(0xFF, 0)] * (INV_MAX - len(inv)):          # the block always holds 30 stacks
            if not (0 <= ty < 256 and 0 <= n < 256): raise DwsError('city: start inventory item or amount out of range')
            out.append(ty | (n << 8))
        return out
    if name in ('shop_maps', 'arena_maps'):
        return [len(d)] + [_w(x) for x in d]
    raise ValueError(name)


def encode(spec, only_present=True):
    """-> bytes of the table (the contents of the MAPHEAD section). Blocks missing from the spec get offset 0."""
    head = 2 + len(BLOCKS)
    body = []; offs = []
    for b in BLOCKS:
        if b in spec:
            offs.append(head + len(body)); body += enc_block(b, spec[b])
        else:
            offs.append(0)
    return struct.pack('<%dH' % (head + len(body)), MAGIC, VERSION, *offs, *body)


def dec_cond(w, p):
    n = w[p]; p += 1; out = []
    for _ in range(n):
        na = w[p]; p += 1; clause = []
        for _ in range(na):
            clause.append((w[p] & 0xFF, w[p] >> 8, w[p + 1])); p += 2
        out.append(clause)
    return out, p


def decode(b):
    w = struct.unpack('<%dH' % (len(b) // 2), b)
    if (w[0], w[1]) != (MAGIC, VERSION): raise DwsError('city table: bad magic or version')
    spec = {}
    for name, o in zip(BLOCKS, w[2:2 + len(BLOCKS)]):
        if not o: continue
        if name == 'prosperity':
            rules = []
            for i in range(w[o]):
                f, l, ml, add = w[o + 1 + 4 * i:o + 5 + 4 * i]
                rules.append({'first': f, 'last': l, 'min_level': ml & 0xFF, 'add': add - 65536 if add >= 32768 else add, 'per_level': ml >> 8})
            spec[name] = rules
        elif name in ('top_map', 'revival'):
            n = w[o + 1]; p = o + 2; rows = []
            for _ in range(n):
                scr = w[p]; c, p = dec_cond(w, p + 1); rows.append({'screen': scr, 'when': c})
            spec[name] = {'default': w[o], 'rows': rows}
        elif name == 'start':
            bits = w[o + 6] | (w[o + 7] << 16)
            cs = [w[o + 8] & 0xFF, w[o + 8] >> 8, w[o + 9] & 0xFF, w[o + 9] >> 8, w[o + 10] & 0xFF, w[o + 10] >> 8]
            spec[name] = {'screen': w[o], 'exit': w[o + 1] & 0xFF, 'lives': w[o + 1] >> 8, 'partner': w[o + 2], 'lifetime': w[o + 3],
                          'age': w[o + 4] & 0xFF, 'hour': w[o + 4] >> 8, 'minute': w[o + 5],
                          'bits': bits - (1 << 32) if bits >= 1 << 31 else bits, 'card_shop': cs,
                          'inventory': [(w[o + 11 + i] & 0xFF, w[o + 11 + i] >> 8) for i in range(INV_MAX)]}
        else:
            spec[name] = list(w[o + 1:o + 1 + w[o]])
    return spec


# ------------------------------------------------------------------ reference evaluation
class State:
    """What the rules look at: triggers set, pstats, the Digimon level table (content/species)."""
    LEVELS = None

    def __init__(self, triggers=(), pstats=None):
        self.triggers = set(triggers); self.pstats = dict(pstats or {})

    @classmethod
    def levels(cls):
        if cls.LEVELS is None:
            import species                                  # content/species (tools/species.py)
            cls.LEVELS = {t: int(r['level']) for t, r in species.all_rows().items() if t < species.NUM_ORIGINAL}
        return cls.LEVELS

    def recruited(self, sp):
        return (200 + sp) in self.triggers if sp < 0x70 else ('r', sp) in self.triggers

    def pstat(self, n): return self.pstats.get(n, 0)


def atom_holds(a, s):
    k, arg, v = a
    if k == TRIG_SET: return v in s.triggers
    if k == TRIG_CLEAR: return v not in s.triggers
    if k == PSTAT_GE: return s.pstat(arg) >= v
    if k == PSTAT_LT: return s.pstat(arg) < v
    if k == REC: return s.recruited(v)
    return not s.recruited(v)


def cond_holds(c, s):
    return not c or any(all(atom_holds(a, s) for a in clause) for clause in c)


def prosperity_of(rules, s):
    lv = State.levels(); pp = 0
    if not rules: return 0
    lo = min(r['first'] for r in rules); hi = min(max(r['last'] for r in rules), 1023)
    for i in range(lo, hi + 1):
        for r in rules:
            if r['first'] <= i <= r['last']:
                level = lv.get(i, 0)
                if level >= r['min_level'] and s.recruited(i):
                    pp = (pp + r['add'] + r['per_level'] * level) & 0xFF
                break
    return pp


def top_map_of(d, s):
    for row in d['rows']:
        if cond_holds(row['when'], s): return row['screen']
    return d['default']


def explain_top_map(d, s):
    for i, row in enumerate(d['rows']):
        if cond_holds(row['when'], s): return row['screen'], f'row {i + 1}: when {cond_text(row["when"])}'
    return d['default'], 'no row holds: the default'


def start_state_of(d):
    inv = list(d['inventory']) + [(0xFF, 0)] * (INV_MAX - len(d['inventory']))
    return dict(d, inventory=inv)


# ------------------------------------------------------------------ the declaration as text
def to_dws(spec, header=True):
    L = []
    if header: L += ['// ' + (header if isinstance(header, str) else 'The city rules as data: what the original game keeps in C (docs/mods/city-rules.md).'), '']
    L.append('city {')
    if 'prosperity' in spec:
        L.append('    prosperity {                                   // pstat 1 is recomputed on every save and game start')
        for r in spec['prosperity']:
            sp = f'{species_text(r["first"])}..={species_text(r["last"])}' if r['first'] != r['last'] else species_text(r['first'])
            w = []
            if r['per_level']: w.append('level' if r['per_level'] == 1 else f'{r["per_level"]} * level')
            if r['add'] or not w:
                w.append(str(r['add']) if not w else (f'+ {r["add"]}' if r['add'] > 0 else f'- {-r["add"]}'))
            L.append(f'        species {sp}: {" ".join(w)} when level >= {r["min_level"]};')
        L.append('    }')
    if 'revival' in spec:
        L.append('    revival {                                      // where the partner is reborn: the first row that holds wins (murd.c, dooa.c)')
        for row in spec['revival']['rows']:
            L.append(f'        screen({row["screen"]}) when {cond_text(row["when"])};')
        L.append(f'        default screen({spec["revival"]["default"]});')
        L.append('    }')
    if 'top_map' in spec:
        L.append('    top_map {                                      // the first row that holds wins')
        for row in spec['top_map']['rows']:
            L.append(f'        screen({row["screen"]}) when {cond_text(row["when"])};')
        L.append(f'        default screen({spec["top_map"]["default"]});')
        L.append('    }')
    for nm in ('shop_maps', 'arena_maps'):
        if nm in spec:
            L.append(f'    {nm}: [{", ".join(str(x) for x in spec[nm])}];')
    if 'start' in spec:
        s = spec['start']
        L.append('    start {                                        // the new game\'s first save (initializeDefaultSavegame)')
        L.append(f'        screen: {s["screen"]};')
        L.append(f'        exit: {s["exit"]};')
        L.append(f'        partner: {species_text(s["partner"])};')
        L.append(f'        bits: {s["bits"]};')
        L.append(f'        lives: {s["lives"]};')
        L.append(f'        lifetime: {s["lifetime"]};              // hours')
        L.append(f'        age: {s["age"]};')
        L.append(f'        time: {s["hour"]}:{s["minute"]:02d};')
        L.append(f'        card_shop: [{", ".join(str(x) for x in s["card_shop"])}];')
        L.append('        inventory: [')
        for t, n in s['inventory']:
            L.append(f'            {item_text(t)} x {n},')
        L.append('        ];')
        L.append('    }')
    if spec.get('presence'):
        from . import presence as PR
        L.append('    presence {                                     // who is on which screen, and when (MAPHEAD setup sections, one rule per NPC)')
        for scr in sorted(spec['presence']):
            sc = spec['presence'][scr]
            L.append(f'        screen({scr}) {{                              // {PR.screen_name(scr)}')
            for name, f in sc['lets']:
                L.append(f'            let {name} = {PR.cond_text(f)};')
            for slot, sp, talk, cond in sc['npcs']:
                w = '' if cond == ('true',) else ' when ' + PR.cond_text(cond)
                L.append(f'            npc {species_text(sp)} slot {slot}{" autotalk" if talk else ""}{w};')
            L.append('        }')
        L.append('    }')
    L.append('}')
    return '\n'.join(L) + '\n'


# ------------------------------------------------------------------ the declaration parser (called by parser.py)
def parse_city(p, c):
    """`city { ... }` -> Node('city', spec=...). p is the Parser, c the `city` token."""
    from .parser import Node
    sp_names, _ = _species(); it_names, _, _ = _items()
    spec = {}

    def num():
        t = p.cur
        if t.kind != 'num': raise DwsError(f'a number is expected, found "{t.val}"', t.pos)
        p.i += 1; return t.val

    def species():
        t = p.cur
        if t.kind == 'num': p.i += 1; return t.val
        if t.kind == 'id':
            if t.val == 'species' and p.peek().val == '(':
                p.i += 2; s = p.cur
                if s.kind == 'str': nm = s.val.lower(); p.i += 1
                else: nm = str(num())
                p.expect(')')
                if nm.isdigit(): return int(nm)
                if nm not in sp_names: raise DwsError(f'unknown species "{s.val}"', s.pos)
                return sp_names[nm]
            if t.val.lower() in sp_names: p.i += 1; return sp_names[t.val.lower()]
        raise DwsError(f'a species (name or number) is expected, found "{t.val}"', t.pos)

    def screen():
        p.expect('screen'); p.expect('('); n = num(); p.expect(')'); return n

    def cmp_value(op, v, tok):
        if op == '>=': return PSTAT_GE, v
        if op == '>': return PSTAT_GE, v + 1
        if op == '<': return PSTAT_LT, v
        if op == '<=': return PSTAT_LT, v + 1
        raise DwsError(f'only >= > < <= compare a pstat in a city rule, found "{op}"', tok.pos)

    def atom():
        neg = False
        if p.at('not'): p.i += 1; neg = True
        t = p.cur
        if t.kind != 'id': raise DwsError(f'a condition is expected, found "{t.val}"', t.pos)
        if t.val == 'recruited':
            p.i += 1; p.expect('('); s = species(); p.expect(')'); return (NOT_REC if neg else REC, 0, s)
        if t.val == 'trigger':
            p.i += 1; p.expect('('); n = num(); p.expect(')'); return (TRIG_CLEAR if neg else TRIG_SET, 0, n)
        if t.val in ('prosperity', 'pstat'):
            if neg: raise DwsError('"not" cannot go before a comparison: write the opposite comparison', t.pos)
            p.i += 1; arg = PROSPERITY_PSTAT
            if t.val == 'pstat': p.expect('('); arg = num(); p.expect(')')
            o = p.cur
            if o.kind != 'op': raise DwsError('a comparison is expected', o.pos)
            p.i += 1; k, v = cmp_value(o.val, num(), o); return (k, arg, v)
        raise DwsError(f'unknown condition "{t.val}" (recruited(X), trigger(N), prosperity >= N, pstat(N) >= V)', t.pos)

    def cond():
        if p.at('always'): p.i += 1; return []
        clauses = [[atom()]]
        while True:
            if p.at('and'): p.i += 1; clauses[-1].append(atom())
            elif p.at('or'): p.i += 1; clauses.append([atom()])
            else: break
        return clauses

    def weight():
        """`level`, `level - 2`, `2 * level + 1`, `1` -> (per_level, add)"""
        per, add, t = 0, 0, p.cur
        if t.kind == 'num' and p.peek().val == '*': per = num(); p.i += 1; p.expect('level')
        elif p.at('level'): p.i += 1; per = 1
        else: return 0, num()
        while p.at('+') or p.at('-'):
            sgn = 1 if p.next().val == '+' else -1; add += sgn * num()
        return per, add

    defs = set()                                  # the `let` names of the screen being read

    def pcmp(var, name_tok):
        o = p.cur
        if o.kind != 'op' or o.val not in ('==', '!=', '>=', '<=', '>', '<'): raise DwsError('a comparison is expected', o.pos)
        p.i += 1; neg = p.at('-'); p.i += neg; v = num()
        return ('cmp', var, o.val, -v if neg else v)

    def pcond():                                  # or > and > not > atom; the tree of tools/dws/presence.py
        xs = [pand()]
        while p.at('or'): p.i += 1; xs.append(pand())
        from . import presence as PR
        return PR.tor(xs)

    def pand():
        from . import presence as PR
        xs = [pnot()]
        while p.at('and'): p.i += 1; xs.append(pnot())
        return PR.tand(xs)

    def pnot():
        from . import presence as PR
        if p.at('not'): p.i += 1; return PR.tnot(pnot())
        if p.at('('): p.i += 1; r = pcond(); p.expect(')'); return r
        t0 = p.cur
        if t0.kind == 'id' and t0.val in defs: p.i += 1; return ('ref', t0.val)
        if t0.val == 'always': p.i += 1; return ('true',)
        if t0.val == 'never': p.i += 1; return ('false',)
        if t0.val == 'recruited': p.i += 1; p.expect('('); s = species(); p.expect(')'); return ('trig', 200 + s)
        if t0.val == 'trigger': p.i += 1; p.expect('('); n = num(); p.expect(')'); return ('trig', n)
        if t0.val == 'flag':                      # a flag of the program by name (resolved to its trigger by the compiler)
            p.i += 1; p.expect('('); nm = p.ident('a flag name'); p.expect(')'); return ('flag', nm.val, nm.pos)
        if t0.val == 'prosperity': p.i += 1; return pcmp('p1', t0)
        if t0.val in ('pstat', 'stat', 'roll'):
            p.i += 1; p.expect('('); n = num(); p.expect(')'); return pcmp({'pstat': f'p{n}', 'stat': f'stat{n}', 'roll': f'roll{n}'}[t0.val], t0)
        if t0.val == 'clock':
            p.i += 1; p.expect('.'); f = p.ident('year, day, hour or minute').val; return pcmp('clock.' + f, t0)
        if t0.val == 'partner':
            p.i += 1; p.expect('.'); f = p.ident('type').val; return pcmp('partner.type', t0)
        raise DwsError(f'a presence condition is expected, found "{t0.val}"', t0.pos)

    p.expect('{')
    while not p.at('}'):
        t = p.cur
        if t.kind == 'eof': raise DwsError('city block never closed', c.pos)
        w = p.ident('a city item').val
        if w in spec: raise DwsError(f'city: "{w}" is declared twice', t.pos)
        if w == 'prosperity':
            p.expect('{'); rules = []
            while not p.at('}'):
                p.expect('species'); lst = []
                while True:
                    a = species(); b = a
                    if p.accept('..'): p.accept('='); b = species()
                    lst.append((a, b))
                    if not p.accept(','): break
                p.expect(':'); per, add = weight(); p.expect('when'); p.expect('level'); p.expect('>='); mn = num(); p.expect(';')
                for a, b in lst: rules.append({'first': a, 'last': b, 'min_level': mn, 'add': add, 'per_level': per})
            p.expect('}'); spec[w] = rules
        elif w in ('top_map', 'revival'):
            p.expect('{'); rows = []; default = None
            while not p.at('}'):
                if p.at('default'):
                    p.i += 1; default = screen(); p.expect(';'); continue
                scr = screen(); p.expect('when'); rows.append({'screen': scr, 'when': cond()}); p.expect(';')
            p.expect('}')
            if default is None: raise DwsError(f'{w} needs `default screen(N);`', t.pos)
            spec[w] = {'default': default, 'rows': rows}
        elif w == 'presence':
            p.expect('{'); pres = {}
            while not p.at('}'):
                p.expect('screen'); p.expect('('); scr = num(); last = scr
                if p.accept('..'): p.accept('='); last = num()          # screen(168..=179): the same rules on each
                p.expect(')'); p.expect('{'); lets = []; rules = []; defs.clear()
                while not p.at('}'):
                    if p.at('let'):
                        p.i += 1; nm = p.ident('a name').val; p.expect('='); f = pcond(); p.expect(';'); lets.append((nm, f)); defs.add(nm); continue
                    p.expect('npc'); sp = species(); p.expect('slot'); slot = num(); talk = 0
                    if p.at('autotalk'): p.i += 1; talk = 1
                    cnd = ('true',)
                    if p.at('when'): p.i += 1; cnd = pcond()
                    p.expect(';'); rules.append((slot, sp, talk, cnd))
                p.expect('}')
                for k in range(scr, last + 1): pres[k] = {'lets': list(lets), 'npcs': list(rules), 'form': 'circuit' if lets else 'flat'}
            p.expect('}'); spec[w] = pres
        elif w in ('shop_maps', 'arena_maps'):
            p.expect(':'); p.expect('['); xs = []
            while not p.at(']'):
                xs.append(num())
                if not p.accept(','): break
            p.expect(']'); p.expect(';'); spec[w] = xs
        elif w == 'start':
            p.expect('{'); d = {}
            while not p.at('}'):
                kt = p.ident('a start field'); k = kt.val; p.expect(':')
                if k == 'partner': d[k] = species()
                elif k == 'time': d['hour'] = num(); p.expect(':'); d['minute'] = num()
                elif k == 'card_shop':
                    p.expect('['); xs = []
                    while not p.at(']'):
                        xs.append(num())
                        if not p.accept(','): break
                    p.expect(']')
                    if len(xs) != 6: raise DwsError('card_shop holds 6 cards', kt.pos)
                    d[k] = xs
                elif k == 'inventory':
                    p.expect('['); xs = []
                    while not p.at(']'):
                        p.expect('item'); p.expect('('); a = p.cur
                        if a.kind == 'str':
                            if a.val.lower() not in it_names: raise DwsError(f'unknown item "{a.val}"', a.pos)
                            item = it_names[a.val.lower()]; p.i += 1
                        else: item = num()
                        p.expect(')'); p.expect('x'); xs.append((item, num()))
                        if not p.accept(','): break
                    p.expect(']'); d[k] = xs
                elif k in ('screen', 'exit', 'bits', 'lives', 'lifetime', 'age'): d[k] = num()
                else: raise DwsError(f'unknown start field "{k}"', kt.pos,
                                    'screen, exit, partner, bits, lives, lifetime, age, time, card_shop, inventory')
                p.expect(';')
            p.expect('}')
            if {'screen', 'exit', 'partner', 'bits', 'lives', 'lifetime', 'age', 'hour', 'minute', 'card_shop', 'inventory'} - set(d):
                # the fields a mod leaves out are the original game's
                for k, v in original_start().items(): d.setdefault(k, v)
            spec[w] = d
        else:
            raise DwsError(f'unknown city item "{w}"', t.pos, 'prosperity, revival, top_map, shop_maps, arena_maps, start, presence')
    p.expect('}')
    return Node('city', c, spec=spec)


_BASE_START = {}


def original_start():
    """The start block of story/base/city/city.dws (the original game's), for a `start { }` that names only some fields."""
    if not _BASE_START:
        path = os.path.join(ROOT, 'story', 'base', 'city', 'city.dws')
        if not os.path.exists(path): raise DwsError('a partial `start { }` needs story/base/city/city.dws (dws city-extract writes it)')
        from .parser import Parser
        nodes = Parser(open(path, encoding='utf-8').read(), path).parse_file()
        _BASE_START.update([n for n in nodes if n.kind == 'city'][0].spec['start'])
    return dict(_BASE_START)


def check(spec, where=None):
    """Range checks that the table format needs."""
    try:
        encode(spec)
    except (struct.error, DwsError, ValueError, TypeError) as e:
        raise DwsError(str(e), where)


def to_c_header(blob, name='CITY_DEFAULT'):
    """city_default.h of the engine: the built-in table (the original rules)."""
    words = struct.unpack('<%dH' % (len(blob) // 2), blob)
    L = ['/* generated by `tools/dws.py city-compile --c-header` from story/base/city/city.dws: the original rules as the engine\'s',
         ' * built-in city table (dw/city.h). Do not edit. */',
         '#ifndef CITY_DEFAULT_H', '#define CITY_DEFAULT_H', '', f'static const uint16_t {name}[{len(words)}] = {{']
    for i in range(0, len(words), 8):
        L.append('\t' + ', '.join('0x%04x' % x for x in words[i:i + 8]) + ',')
    L += ['};', '', '#endif', '']
    return '\n'.join(L)


def to_section_text(blob, label='dws_city'):
    """bytecode text of the MAPHEAD section: the table as raw bytes."""
    L = [f'.section {SECTION} {label}']
    return L[0], ['', f'{label}:'] + ['    .byte ' + ' '.join('%02x' % x for x in blob[i:i + 16]) for i in range(0, len(blob), 16)]


# ------------------------------------------------------------------ the original rules, read out of the decompilation's C
def _read(rel, src=None):
    with open(os.path.join(src or ORIGINAL_SRC, rel), encoding='utf-8') as f:
        return f.read()


def c_function(text, name):
    """The text of function `name` (its signature line to the matching brace)."""
    m = re.search(r'^[A-Za-z_][\w \*]*\b%s\([^;{]*\)\s*\{' % re.escape(name), text, re.M)
    if not m: raise DwsError(f'city-extract: function {name} not found in the C source')
    i = m.end(); depth = 1
    while depth:
        ch = text[i]; depth += (ch == '{') - (ch == '}'); i += 1
    return text[m.start():i]


def _trig_atom(t):
    """A test of trigger 200 + type is `recruited(type)` (the convention, ids.h TRIGGER_RECRUITED_BASE; the engine reads both the same)."""
    return (REC, 0, t - 200) if 200 <= t < 200 + 0x70 else (TRIG_SET, 0, t)


def _int(s):
    return int(s.strip().rstrip('uUlL'), 0)


def _expect(cond, what):
    if not cond: raise DwsError(f'city-extract: the C source no longer has the shape this tool reads ({what})')


def _x_prosperity(src):
    f = c_function(_read('main/main.c', src), 'recalculatePPandArena')
    m = re.search(r'for \(i = (\w+); i < (\w+); i\+\+\)', f); _expect(m, 'the species loop')
    first, end = _int(m.group(1)), _int(m.group(2))
    m = re.search(r'level >= (\w+)\) && \(isTriggerSet\(\(uint16_t\)\((\w+) \+ i\)\) != 0\)', f); _expect(m, 'level gate and recruit trigger')
    minlv, base = _int(m.group(1)), _int(m.group(2)); _expect(base == 200, 'the recruit flag is trigger 200 + type')
    m = re.search(r'if \(((?:\(i == \w+\)(?: \|\| )?)+)\) \{\s*pp\+\+;\s*\} else \{\s*pp \+= \(uint8_t\)\(DIGIMON_DATA\[i\]\.level - (\w+)\);', f)
    _expect(m, 'the exempt species and the level - 2 weight')
    exempt = [_int(x) for x in re.findall(r'i == (\w+)', m.group(1))]; sub = _int(m.group(2))
    _expect('writePStat(1, pp)' in f, 'prosperity is pstat 1')
    rules = [{'first': e, 'last': e, 'min_level': minlv, 'add': 1, 'per_level': 0} for e in exempt]
    rules.append({'first': first, 'last': end - 1, 'min_level': minlv, 'add': -sub, 'per_level': 1})
    return rules


def _parse_block(s):
    """The statements of a C block of nested `if (a && b) { ... }` and `return N;` -> a tree."""
    toks = re.findall(r'if \(|return\s+\w+;|\{|\}|\(|\)|[^\s{}()]+', s)
    pos = 0

    def block():
        nonlocal pos
        out = []
        while pos < len(toks) and toks[pos] != '}':
            t = toks[pos]
            if t.startswith('return'):
                out.append(('ret', _int(t.split()[1].rstrip(';')))); pos += 1
            elif t == 'if (':
                pos += 1; ctoks = []
                depth = 1
                while True:
                    if toks[pos] == '(' : depth += 1
                    if toks[pos] == ')':
                        depth -= 1
                        if depth == 0: break
                    ctoks.append(toks[pos]); pos += 1
                pos += 1; _expect(toks[pos] == '{', 'an if with a block'); pos += 1
                body = block(); _expect(toks[pos] == '}', 'a closed block'); pos += 1
                out.append(('if', ' '.join(ctoks), body))
            else:
                raise DwsError(f'city-extract: unexpected C token "{t}" in the top-map function')
        return out
    return block()


def _x_top_map(src):
    f = c_function(_read('main/map.c', src), 'getFileCityTopMap')
    body = f[f.index('{') + 1:f.rindex('}')]
    tree = _parse_block(body)
    rows = []

    def atoms(cond):
        out = []
        for part in cond.split('&&'):
            m = re.search(r'isTriggerSet \( (\w+) \) != 0', part) or re.search(r'isTriggerSet\((\w+)\) != 0', part)
            m = m or re.search(r'isTriggerSet\s*\(\s*(\w+)\s*\)\s*!=\s*0', part.replace(' ', ''))
            if not m:
                t = re.sub(r'\s+', '', part); m = re.search(r'isTriggerSet\((\w+)\)!=0', t)
            _expect(m, f'a trigger test in "{cond}"'); out.append(_int(m.group(1)))
        return out

    def walk(stmts, path):
        for st in stmts:
            if st[0] == 'ret': rows.append((st[1], list(path))); return
            walk(st[2], path + atoms(st[1]))
        _expect(False, 'every block ends in a return')
    walk(tree, [])
    out = []
    for scr, trigs in rows[:-1]:
        _expect(trigs, 'the last row is the default'); out.append({'screen': scr, 'when': [[_trig_atom(t) for t in trigs]]})
    _expect(not rows[-1][1], 'the last row is the default')
    spec = {'default': rows[-1][0], 'rows': out}
    # the tree is a decision cascade: check the rows against a direct evaluation of the tree on every combination of its triggers
    tr = sorted({t for _, ts in rows for t in ts})

    def run(stmts, st):
        for x in stmts:
            if x[0] == 'ret': return x[1]
            if all(t in st for t in atoms(x[1])):
                r = run(x[2], st)
                if r is not None: return r
    for mask in range(1 << len(tr)):
        st = {t for k, t in enumerate(tr) if mask >> k & 1}
        _expect(top_map_of(spec, State(st)) == run(tree, st), 'the rows reproduce the cascade')
    return spec


def _x_revival(src):
    m1 = _read('murd/murd.c', src); m2 = _read('dooa/dooa.c', src)
    pat = (r'if \(\(isTriggerSet\((\w+)\) == 1\) \|\| \(isTriggerSet\((\w+)\) == 1\) \|\| \(readPStat\(1\) >= (\w+)U?\)\) \{\s*'
           r'(?:message|messageId) = (\w+);\s*\} else \{\s*(?:message|messageId) = (\w+);')
    a = re.search(pat, m1); b = re.search(pat, m2)
    _expect(a and b, 'the revival condition in murd.c and dooa.c')
    va = tuple(_int(x) for x in a.groups()); vb = tuple(_int(x) for x in b.groups())
    _expect(va == vb, 'murd.c and dooa.c repeat the same condition')
    t1, t2, p, big, small = va
    cond = [[_trig_atom(t1)], [_trig_atom(t2)], [(PSTAT_GE, PROSPERITY_PSTAT, p)]]
    return {'default': small, 'rows': [{'screen': big, 'when': cond}]}


def _c_array(text, name):
    m = re.search(r'\b%s(?:\[\d*\])?\s*=\s*\{(.*?)\};' % re.escape(name), text, re.S); _expect(m, f'array {name}')
    return [_int(x) for x in re.findall(r'0[xX][0-9a-fA-F]+|\b\d+\b', m.group(1))]


def _x_maps(src):
    sc = _read('main/script_common.c', src)
    return _c_array(sc, 'SHOP_MAPS'), _c_array(sc, 'ARENA_MAPS')


def _x_start(src):
    mm = _read('main/main_menu.c', src); f = c_function(mm, 'initializeDefaultSavegame')
    ids = _read('../include/dw/ids.h', src) if os.path.exists(os.path.join(src, '../include/dw/ids.h')) else ''

    def field(pat, what):
        m = re.search(pat, f); _expect(m, what); return m.group(1)
    scr = field(r'currentScreen = (\w+);', 'start screen')
    if not scr[0].isdigit():
        m = re.search(r'#define\s+%s\s+(\w+)' % scr, ids); _expect(m, 'the screen constant'); scr = m.group(1)
    d = {'screen': _int(scr), 'exit': _int(field(r'currentExit = (\w+);', 'exit')),
         'partner': _int(field(r'partnerType = (\w+);', 'partner type')), 'bits': _int(field(r'money = (\w+);', 'money')),
         'lives': _int(field(r'partnerLives = (\w+);', 'lives')),
         'lifetime': _int(field(r'remainingLifetime = (\w+);', 'lifetime')), 'age': _int(field(r'\.age = (\w+);', 'age')),
         'hour': _int(field(r'savegame->hour = (\w+);', 'hour')), 'minute': _int(field(r'savegame->minute = (\w+);', 'minute'))}
    frame = _int(field(r'lastHandledFrame = savegame->currentFrame = (\w+);', 'the start frame'))
    _expect(frame == d['hour'] * 1200 + d['minute'] * 20, 'the start frame is hour * 1200 + minute * 20')
    _expect(int(field(r'for \(i = 0; i < (\d+); i\+\+\) \{\s*savegame->inventory\.types', 'inventory size')) == 30 and 'inventory.size = 30' in f, '30 stacks')
    m = re.search(r'for \(i = 0; i < 6; i\+\+\) \{\s*savegame->scriptState\[i\] = (\w+) \+ i;', f); _expect(m, 'card shop')
    d['card_shop'] = [_int(m.group(1)) + i for i in range(6)]
    types = _c_array(mm, 'DEFAULT_INVENTORY_TYPES'); amounts = _c_array(mm, 'DEFAULT_INVENTORY_AMOUNTS')
    _expect(len(types) == 30 and len(amounts) == 30, '30 default stacks')
    d['inventory'] = list(zip(types, amounts))
    return d


def extract_original(src=None):
    """The original rules, read from the decompilation's C sources (decomp/src, the unmodified `main` branch)."""
    src = src or ORIGINAL_SRC
    rev = _x_revival(src); shop, arena = _x_maps(src)
    return {'prosperity': _x_prosperity(src), 'revival': rev, 'top_map': _x_top_map(src),
            'shop_maps': shop, 'arena_maps': arena, 'start': _x_start(src)}
