"""Semantic analysis and code generation: AST -> script assembly (bytecode text) per event.

The language subset that the retired quest compiler had produces the same bytes it did (golden hashes in tools/test_dws.py)."""
import difflib, os, re, sys
from . import backend as BE
from .diag import DwsError, err, Warnings
from .parser import parse, Node
from .alloc import Allocator, TYPE_BITS
from . import registry as R
from .ext import Ext, Elem

REQ = object()
OPS_FLIP = {'==': '!=', '!=': '==', '>=': '<', '<=': '>', '>': '<=', '<': '>='}
ENT_FIXED = {'tamer': 'TAMER', 'player': 'TAMER', 'partner': 'PARTNER', 'narrator': '255', 'camera': '200', 'all': '255'}
STATS = {k.replace(' ', '_'): v for k, v in BE.PARTNER_STATS.items()}
CLOCK = ['year', 'day', 'hour', 'minute']
STORY_MNEMONICS = {'SET_V', 'ADD_V', 'SUB_V', 'COPY_V', 'V_FROM_PSTAT', 'PSTAT_FROM_V', 'ADD_VV', 'SUB_VV', 'MUL_V', 'DIV_V', 'MOD_V'}
WIDE_MNEMONICS = {'SPAWN_ITEM_DAILY', 'SET_WREG', 'STORE_DIGIMON_TYPE_W', 'STORE_MAP_ID_W', 'TELEPORT_W', 'COPY_W', 'ADD_W', 'SUB_W', 'SWITCH_W'}


class V:
    __slots__ = ('type', 'val', 'key')

    def __init__(self, type, val, key=None):
        self.type, self.val, self.key = type, val, key          # key: the text key a `text("k")` value was read from

    def __repr__(self):
        return f'V({self.type},{self.val!r})'


def norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


class Sym:
    def __init__(self, kind, name, node, **kw):
        self.kind, self.name, self.node = kind, name, node
        self.reads = 0; self.writes = 0; self.pub = False; self.unit = None
        self.__dict__.update(kw)


class Env:
    def __init__(self, npcs, self_ent=None, parent=None):
        self.npcs = npcs; self.locals = {}; self.self_ent = self_ent
        self.out = parent.out if parent else []
        self.state = parent.state if parent else {'speaker': None}
        self.pre = parent.pre if parent else []
        self.loops = parent.loops if parent else []
        self.fn_end = None; self.fn_stack = parent.fn_stack if parent else []
        self.section = parent.section if parent else None
        self.ev = parent.ev if parent else None
        self.lab = parent.lab if parent else {'def': {}, 'used': []}
        self.port = parent.port if parent else False
        self.sid = parent.sid if parent else None
        self.sub_name = parent.sub_name if parent else None
        self.in_sub = parent.in_sub if parent else None
        self.sub_ret = parent.sub_ret if parent else None


def is_wide_line(line):
    t = line.strip()
    m = re.match(r'([A-Z_0-9]+)', t)
    if m and (m.group(1).endswith('16') or m.group(1) in WIDE_MNEMONICS): return True
    return bool(re.search(r'\bitem16\b|\bw\d+\s*(==|!=|>=|<=|>|<)', t)) if t.startswith('IF') else False


def is_story_line(line):
    """An instruction of the story-state engine (story variables, docs/mods/story-state-engine.md), also inside an IF."""
    t = line.strip()
    m = re.match(r'([A-Z_0-9]+)', t)
    if m and m.group(1) in STORY_MNEMONICS: return True
    return bool(re.search(r'(^|\s)[vs]\d+\s*(==|!=|>=|<=|>|<)', t)) if t.startswith('IF') else False


class Program(Ext):
    """Collects declarations of all files, then generates every event."""

    def __init__(self, backend, bank, alloc=None, max_opcode_level=0):
        self.b = backend; self.bank = bank; self.alloc = alloc or Allocator()
        self.warn = Warnings(); self.errors = []; self.max_opcode_level = max_opcode_level; self.required_opcode_level = 0
        self.syms = {}; self.script_npcs = {}; self.pending = []; self.loaded = {}
        self.module = None; self.label_n = 0; self.lossless = {}; self.maphead_lossless = None
        self.used_text = set()
        self.ports = {}; self.maphead_port = None; self.enums = {}; self.routines = dict(R.ROUTINE_BY_NAME)
        self.mod_names = set(); self.subs_emitted = {}; self.profile = 'original'; self.xref = []
        self.raws = {}; self.hidden = {}; self.port_texts = {}

    def label(self, hint):
        return self.b.label(hint)

    # ------------------------------------------------------------ loading
    def load(self, path, root=True):
        path = os.path.abspath(path)
        if path in self.loaded: return
        self.loaded[path] = True
        try:
            src = open(path, encoding='utf-8').read()
        except OSError as e:
            raise DwsError(f'cannot read {path}: {e}')
        rel = os.path.relpath(path)
        items = parse(src, path if rel.startswith('..') else rel)
        mod = os.path.splitext(os.path.basename(path))[0]; saved = self.module; self.mod_names.add(mod)
        self.module = mod; self.cur_dir = os.path.dirname(path)
        mods = [it for it in items if it.kind == 'module']                # the namespace first: pinned names belong to it too
        pinned = [it for it in items if it.kind == 'decl' and it.pin is not None and not it.alias]
        enums = [it for it in items if it.kind == 'enum']                # a pinned `var v: E = n` needs its enum first
        for it in mods + enums + pinned + [it for it in items if it not in pinned and it not in enums and it not in mods]:     # pins first: unpinned ones go around them
            try:
                self.declare(it, path, root)
            except DwsError as e:
                self.errors.append(e)
        self.module = saved

    def qname(self, name):
        return f'{self.module}.{name}'

    def is_story_var(self, sym):
        """A variable of the story-state engine (32-bit, saved or scene): instructions SET_V ..., not pstats."""
        return self.profile != 'original' and sym.scope in ('save', 'temp') and not sym.alias

    @staticmethod
    def vref(sym):
        return f's{sym.num - 0x8000}' if sym.num >= 0x8000 else f'v{sym.num}'

    def define(self, name, sym, node):
        if name in self.syms:
            o = self.syms[name]
            raise err(node, f'"{name}" is already declared', f'first declared at {o.node.pos[0]}:{o.node.pos[1]}')
        self.syms[name] = sym
        if getattr(sym, 'module', None) is None: sym.module = self.module

    def declare(self, it, path, root):
        k = it.kind
        if k == 'module': self.module = it.name; self.mod_names.add(it.name)
        elif k == 'import':
            target = os.path.join(os.path.dirname(path), it.path)
            if not os.path.exists(target): raise err(it, f'import "{it.path}": file not found')
            self.load(target, root=False); self.module = os.path.splitext(os.path.basename(path))[0]
        elif k == 'decl':
            self.declare_decl(it, path, root)
        elif k == 'group':
            for d in it.decls:
                if d.kind == 'const': self.declare(d, path, root); continue
                d.group = it.name; self.declare_decl(d, path, root)
        elif k == 'enum':
            if it.name in self.enums: raise err(it, f'enum "{it.name}" is already declared')
            seen = {}
            for vn, vv, tok in it.values:
                if vv in seen: raise err(tok, f'enum {it.name}: {vn} and {seen[vv]} are both {vv}')
                seen[vv] = vn
            self.enums[it.name] = {'values': {vn: vv for vn, vv, _ in it.values}, 'node': it}
        elif k == 'routine':
            if it.name in self.routines and self.routines[it.name] != it.num:
                raise err(it, f'routine "{it.name}" is already {self.routines[it.name]}')
            self.routines[it.name] = it.num
        elif k == 'maphead_port':
            if self.maphead_port or self.maphead_lossless: raise err(it, 'only one maphead block is allowed')
            self.maphead_port = it
        elif k == 'const':
            env = Env({}); v = self.eval(it.expr, env)
            self.define(it.name, Sym('const', it.name, it, value=v, pub=it.pub, root=root), it)
        elif k == 'fn':
            self.define(it.name, Sym('fn', it.name, it, pub=it.pub, root=root, unit=path), it)
        elif k == 'place':
            self.place(it.call)
        elif k == 'city':
            from . import city as CITY
            if self.max_opcode_level < 2 and set(it.spec) - {'presence'}:           # presence rules are MAPHEAD code: every engine runs them
                raise err(it, 'a `city { }` table is read by the story-state engine only (its `presence` rules work on every engine)',
                          'compile with --exe story-state (the original engine keeps the rules in C)')
            self.b.city_table = self.max_opcode_level >= 2
            CITY.check(it.spec, it.pos)
            if self.b.city is None: self.b.city = {}
            for blk in it.spec:
                if blk == 'presence' and blk in self.b.city:       # presence merges by screen, and by slot within a screen
                    for scr, sc in it.spec[blk].items():
                        had = self.b.city[blk].get(scr)
                        if had is None: continue
                        if had['lets'] or sc['lets']: raise err(it, f'screen {scr}: a presence block with `let` names is declared twice')
                        twice = {r[0] for r in had['npcs']} & {r[0] for r in sc['npcs']}
                        if twice: raise err(it, f'screen {scr} slot {min(twice)}: two presence rules')
                    continue
                if blk in self.b.city: raise err(it, f'city: "{blk}" is declared twice (in two city {{ }} declarations)')
            for blk, v in it.spec.items():
                if blk == 'presence' and blk in self.b.city:
                    for scr, sc in v.items():
                        if scr in self.b.city[blk]: self.b.city[blk][scr]['npcs'] = self.b.city[blk][scr]['npcs'] + sc['npcs']
                        else: self.b.city[blk][scr] = sc
                else: self.b.city[blk] = v
        elif k == 'maphead_lossless':
            if self.maphead_lossless: raise err(it, 'only one `maphead lossless` block is allowed')
            self.maphead_lossless = it.text
        elif k == 'script':
            self.script(it, path)

    def declare_decl(self, it, path, root):
        qn = it.name if not it.group else f'{it.group}.{it.name}'
        q = self.qname(qn)
        vt = it.vtype
        if vt in self.enums: it.enum_ok = True
        n = self.alloc.declare(it.what, it.scope, q, it.pin, it.alias, it, count=it.count, vtype=(None if vt in self.enums else vt))
        if not it.alias: n = self.alloc.engine_number(it.what, it.scope, n)    # story-state: trigger 800 + n, scene variable 0x8000 + n
        if it.what == 'var' and vt and vt not in self.enums and vt not in TYPE_BITS:
            raise err(it, f'unknown type "{vt}"', 'types: ' + ', '.join(TYPE_BITS) + ' or an enum declared with `enum`')
        sym = Sym(it.what, qn, it, num=n, scope=it.scope, alias=it.alias, pub=it.pub, root=root, unit=path,
                  count=it.count, vtype=vt, module=self.module)
        self.define(qn, sym, it)

    def script(self, it, path):
        if it.new_for is not None:
            scr = it.new_for
            if any(v['screen'] == scr for v in self.b.new_scripts.values()):
                raise err(it, f'screen {scr} already has a new script')
            sid = BE.FIRST_NEW_SCRIPT + len(self.b.new_scripts)
            self.b.new_scripts[sid] = {'screen': scr, 'empty': it.empty}
        else:
            sid = it.id
        info = self.b.scripts.setdefault(sid, {'entities': {}, 'events': []}) if sid != 'maphead' else {'entities': {}, 'events': []}
        if getattr(it, 'port', None) is not None:
            if sid in self.ports or sid in self.lossless: raise err(it, f'script {sid} already has a whole-script block')
            self.ports[sid] = it; return
        if it.lossless:
            if sid in self.lossless: raise err(it, f'script {sid} already has a lossless block')
            self.lossless[sid] = (it.text, it.line, it.pos[0]); return
        npcs = self.script_npcs.setdefault(sid, {})
        where = self.__dict__.setdefault('npc_files', {}).setdefault(sid, {})
        for n in it.body:
            if n.kind == 'npc':
                # the same name for the same entity in another file is the same NPC (two mods or overrides of one script);
                # twice in one file, or another entity under the name, is an error
                if n.name in npcs and (npcs[n.name] != str(n.num) or where.get(n.name) == path):
                    raise err(n, f'NPC "{n.name}" is declared twice in script {sid}' +
                              (f' (entity {npcs[n.name]} in {os.path.basename(where[n.name])}, {n.num} here)' if npcs[n.name] != str(n.num) else ''))
                where[n.name] = path
                if not 0 <= n.num <= 254: raise err(n, 'entity number out of range')
                npcs[n.name] = str(n.num); info['entities'][n.name.lower()] = str(n.num)
        shared = self.__dict__.setdefault('shared_names', {}).setdefault(sid, {})
        def scan(x):                                   # `shared NAME:` labels inside the events
            if isinstance(x, Node):
                if x.kind == 'label' and getattr(x, 'shared', False): yield x
                for v in x.__dict__.values(): yield from scan(v)
            elif isinstance(x, (list, tuple)):
                for v in x: yield from scan(v)
        for n in it.body:
            for lab in ([n] if n.kind == 'shared' else scan(n.body) if n.kind == 'event' else []):
                if lab.name in shared:
                    raise err(lab, f'shared name "{lab.name}" is defined twice in script {sid}',
                              f'first in {os.path.basename(str(shared[lab.name].pos[0]))} line {shared[lab.name].pos[1]}')
                shared[lab.name] = lab
        ap = os.path.abspath(path)
        if os.sep + os.path.join('story', 'mods') + os.sep in ap and any(n.kind == 'event' for n in it.body) \
                and ap not in self.__dict__.setdefault('deprecated_warned', set()):
            self.deprecated_warned.add(ap)
            self.warn.add(it, "a mod's story in DWS is deprecated: write it in Python (docs/mods/story-language.md); "
                              "DWS stays for what Python has no form for (a `city { }` block, dws(...) hatches)")
        for n in it.body:
            if n.kind in ('event', 'shared'):
                self.pending.append((sid, n, npcs, path, self.module))
            elif n.kind == 'sections':
                orders = self.b.__dict__.setdefault('orders', {})
                if sid in orders: raise err(n, f'script {sid} has two `sections` lists ({os.path.basename(str(orders[sid][1]))} and here)')
                orders[sid] = ([(e[0], e[1]) for e in n.entries], path, n)

    # ------------------------------------------------------------ events
    def section_of(self, n, npcs, sid=None):
        ev = n.ev
        if ev == 'talk':
            if n.arg not in npcs: raise err(n, f'unknown NPC "{n.arg}"', 'declare it in the script block: npc name = 5;' + self.near(n.arg, npcs))
            s = int(npcs[n.arg])
            if not 5 <= s <= 50:                             # (the .MAP's script id is a byte; 51-109 are the step and use tiles)
                raise err(n, f'"{n.arg}" is entity {s}; talk sections of NPCs are 5-50 (slot K answers on 5 + K, or the '
                             '`section:` of its place(...))')
            return s
        if ev == 'enter': return 254
        if ev == 'step':
            if not 0 <= n.arg <= 28: raise err(n, f'step tile {n.arg}: tiles 0-28 (sections 51-79)')
            return 51 + n.arg
        if ev == 'use':
            if not 0 <= n.arg <= 29: raise err(n, f'use tile {n.arg}: tiles 0-29 (sections 80-109)')
            return 80 + n.arg
        if sid == 'maphead': return n.arg
        if sid == 0 and (255 <= n.arg <= 1999 or n.arg == 0): return n.arg      # the unused script 0 (a copy of MAPHEAD): its global sections 1220-1253 and section 0 (replace only, see backend.apply)
        if not 1 <= n.arg <= 254: raise err(n, f'section {n.arg}: ids are 1-254')
        return n.arg

    def generate(self):
        for sid, n, npcs, path, mod in self.pending:
            self.module = mod
            try:
                if n.kind == 'shared':
                    self.gen_shared(sid, n, npcs, path); continue
                if n.mode == 'after':
                    raise err(n, '`after` is not available in original',
                              'the original code of a section ends with END_SECTION: use `before` (the default) or `replace`')
                sec = self.section_of(n, npcs, sid)
                env = Env(npcs, self_ent=npcs.get(n.arg) if n.ev == 'talk' else None)
                env.section = sec; env.ev = n.ev; env.sid = sid
                env.state['ret_ok'] = n.mode == 'replace'        # (a `before` event falls into the base's code: no END_SECTION after it)
                self.block(n.body, env)
                if 'ret' in env.state: env.out += [f'{env.state["ret"]}:', '    END_SECTION']
                if BE.SRCMAP: env.out.append(';@src -')        # the end of this event's code (what follows is not from a source line)
                self.check_labels(env, f'script {sid} section {sec}')
                code = env.out
                if env.pre: raise err(n, 'internal: unflushed condition setup')
                if sid == 'maphead': self.b.__dict__.setdefault('mh_events', []).append((sec, n.mode == 'replace', code, {}, path))
                else: self.b.scripts[sid]['events'].append((sec, n.mode == 'replace', code, {}, path))
            except DwsError as e:
                self.errors.append(e)
        self.generate_ports()
        self.resolve_presence()
        self.lint()

    TERMINAL_OPS = ('END_SECTION', 'END_SCRIPT', 'END', 'JUMP_TO', 'JUMP_RETURN', 'JUMP_TO_FILE')

    def gen_shared(self, sid, n, npcs, path):
        """`shared NAME { }`: compiled once per script, placed after the events under the label sh_NAME (a code block of the
        script that events reach by `goto NAME;` or `gosub NAME;`). It ends like an event (END_SECTION unless it jumps)."""
        env = Env(npcs, self_ent=None)
        env.section = None; env.ev = 'shared'; env.sid = sid; env.sub_name = f'sh_{n.name}'; env.state['ret_ok'] = True
        self.block(n.body, env)
        if 'ret' in env.state: env.out += [f'{env.state["ret"]}:', '    END_SECTION']
        if BE.SRCMAP: env.out.append(';@src -')
        self.check_labels(env, f'script {sid} shared block {n.name}')
        if env.pre: raise err(n, 'internal: unflushed condition setup')
        real = [l for l in env.out if l.strip() and not l.lstrip().startswith(';') and not l.lstrip().startswith('"')]
        code = [f'{self.shared_label(n.name)}:'] + env.out
        # it ends like an event: END_SECTION, unless its last line is a jump or an end (a label there is reached: it falls off)
        if not real or re.match(r'^\w+:', real[-1]) or real[-1].split()[0] not in self.TERMINAL_OPS: code.append('    END_SECTION')
        if sid == 'maphead': self.b.__dict__.setdefault('mh_shared', []).append((n.name, code, path))
        else: self.b.scripts[sid].setdefault('shared', []).append((n.name, code, path))

    @staticmethod
    def shared_label(name):
        """The assembler label of a shared block or a `shared NAME:` label (one namespace per script)."""
        return f'sh_{name}'

    def resolve_presence(self):
        """`flag(name)` in a `city { presence }` condition: the declared flag's trigger (a story flag is 800 + n)."""
        pres = (self.b.city or {}).get('presence') or {}
        def walk(c):
            if c[0] == 'flag':
                s = self.syms.get(c[1])
                if s is None or s.kind != 'flag' or s.count:
                    raise DwsError(f'presence: "{c[1]}" is not a declared flag{self.near(c[1], [k for k, v in self.syms.items() if v.kind == "flag"])}', c[2])
                s.reads += 1
                return ('trig', s.num)
            if c[0] in ('and', 'or'): return (c[0], [walk(x) for x in c[1]])
            if c[0] == 'not': return ('not', walk(c[1]))
            return c
        try:
            for sc in pres.values():
                sc['lets'] = [(nm, walk(f)) for nm, f in sc['lets']]
                sc['npcs'] = [(slot, sp, talk, walk(cnd)) for slot, sp, talk, cnd in sc['npcs']]
        except DwsError as e:
            self.errors.append(e)

    def lint(self):
        for s in self.syms.values():
            if s.kind in ('flag', 'var') and getattr(s, 'root', False) and not s.pub and not s.alias:
                if s.reads == 0 and s.writes == 0:
                    self.warn.add(s.node.ntok, f'{s.kind} "{s.name}" is never used')
                elif s.writes == 0:
                    self.warn.add(s.node.ntok, f'{s.kind} "{s.name}" is read but never set (it is always {"false" if s.kind == "flag" else "0"})')
                elif s.reads == 0:
                    self.warn.add(s.node.ntok, f'{s.kind} "{s.name}" is set but never read')

    @staticmethod
    def near(name, pool):
        m = difflib.get_close_matches(name, list(pool), 1)
        return f' (did you mean "{m[0]}"?)' if m else ''

    # ------------------------------------------------------------ name lookup
    def lookup(self, name, env):
        e = env
        if name in e.locals: return e.locals[name]
        if name in e.npcs: return V('entity', e.npcs[name])
        if name == 'self' and e.self_ent is not None: return V('entity', e.self_ent)
        if name in ENT_FIXED: return V('entity', ENT_FIXED[name])
        s = self.syms.get(name)
        if s is None:
            return self.raw_name(name)
        if s.kind in ('flag', 'var'):
            if s.count: return V('array', s)
            return V(s.kind, s)
        if s.kind == 'const': return s.value
        return V('fn', s)

    def known_names(self, env):
        return list(env.locals) + list(env.npcs) + list(ENT_FIXED) + list(self.syms)

    # ------------------------------------------------------------ expressions
    REGISTRIES = {'item': 'items', 'species': 'digimon', 'tech': 'techs'}

    def resolve_named(self, kind, s, node):
        reg = getattr(self.b, self.REGISTRIES[kind])
        key = s.strip().lower()
        if key in reg: return reg[key]
        cand = {norm(k): v for k, v in reg.items()}
        if norm(s) in cand: return cand[norm(s)]
        m = difflib.get_close_matches(key, list(reg), 3)
        raise err(node, f'no {kind} "{s}"', ('did you mean ' + ', '.join(f'"{x}"' for x in m) + '? ' if m else '') +
                  f'(names are in docs/data/{"digimon" if kind == "species" else kind + "s"}.csv)')

    def eval(self, n, env):
        k = n.kind
        if k == 'num': return V('int', n.v)
        if k == 'dur': return V('ticks', n.v)
        if k == 'str': return V('str', n.v)
        if k == 'bool': return V('bool', n.v)
        if k == 'id':
            v = self.lookup(n.name, env)
            if v is None:
                raise err(n, f'unknown name "{n.name}"', 'declare it with flag/var/const/npc or `let`' + self.near(n.name, self.known_names(env)))
            if v.type in ('flag', 'var'): v.val.reads += 1
            return v
        if k == 'member' and n.obj.kind == 'id' and (f'{n.obj.name}.{n.name}' in self.syms or n.obj.name in self.enums
                                                       or n.obj.name in self.mod_names):
            return self.qualified(n, env)
        if k == 'index': return self.index(n, env)
        if k == 'member':
            if n.obj.kind == 'id' and n.obj.name in ('Item', 'Species', 'Tech'):
                kind = n.obj.name.lower(); return V(kind, self.resolve_named(kind, n.name, n))
            raise err(n, f'"{n.name}" cannot be used as a value here', 'clock.*, partner.* are only valid in conditions')
        if k == 'list': return V('list', [self.eval(x, env) for x in n.items])
        if k == 'tuple': return V('tuple', [self.eval(x, env) for x in n.items])
        if k == 'unary' and n.op == '-':
            v = self.eval(n.e, env); self.need(v, 'int', n); return V('int', -v.val)
        if k == 'binary' and n.op in ('+', '-'):
            a, b = self.eval(n.l, env), self.eval(n.r, env); self.need(a, 'int', n.l); self.need(b, 'int', n.r)
            return V('int', a.val + b.val if n.op == '+' else a.val - b.val)
        if k == 'call': return self.ctor(n, env)
        raise err(n, 'this expression is only valid in a condition', 'conditions are used in if/while')

    def need(self, v, ty, node):
        if v.type != ty: raise err(node, f'expected {ty}, got {v.type}')

    def ctor(self, n, env):
        if n.fn.kind != 'id': raise err(n, 'unknown function')
        f = n.fn.name
        args = [(nm, self.eval(a, env)) for nm, a in n.args]
        if f in ('item', 'species', 'tech'):
            if len(args) != 1: raise err(n, f'{f}() takes one argument: a name in quotes or an id number')
            v = args[0][1]
            if v.type == 'str': return V(f, self.resolve_named(f, v.val, n.args[0][1]))
            if v.type == 'int': return V(f, v.val)
            raise err(n, f'{f}() takes a name in quotes or an id number')
        if f in ('card', 'screen', 'track'):
            if len(args) != 1 or args[0][1].type != 'int': raise err(n, f'{f}() takes an id number')
            return V(f, args[0][1].val)
        if f == 'entity':
            if len(args) != 1 or args[0][1].type != 'int': raise err(n, 'entity() takes an entity number')
            return V('entity', str(args[0][1].val))
        if f == 'text':
            if len(args) != 1 or args[0][1].type != 'str': raise err(n, 'text() takes a key in quotes: text("s002.sec6.u0")')
            key = args[0][1].val; r = self.bank.get(key)
            if r is None:
                msg, hint = self.bank.missing_message(key); raise err(n.args[0][1], msg, hint)
            self.used_text.add(key)
            return V('text', r, key)
        if f == 'page':
            rows = []
            for nm, v in args:
                if v.type == 'str': rows.append(v.val)
                elif v.type == 'text' and v.val[0] == 'wrap': rows.append(v.val[1])
                else: raise err(n, 'page() takes rows: strings or text("key") of one line each')
            return V('text', ('pages', [rows]))
        raise err(n, f'"{f}()" is a statement, not a value' if f in BUILTINS else f'unknown function "{f}"',
                  None if f in BUILTINS else 'functions are declared with fn' + self.near(f, list(BUILTINS) + list(self.syms)))

    # ------------------------------------------------------------ argument binding
    def bind(self, call, spec, env, fname=None):
        fname = fname or call.fn.name
        vals = {}; pos = [s for s in spec]
        for i, (nm, a) in enumerate(call.args):
            if nm is None:
                if i >= len(spec): raise err(a, f'{fname}() takes at most {len(spec)} arguments')
                name = spec[i][0]
            else:
                name = nm
                if name not in [s[0] for s in spec]:
                    raise err(a, f'{fname}() has no argument "{nm}"', 'arguments: ' + ', '.join(s[0] for s in spec))
            if name in vals: raise err(a, f'{fname}(): "{name}" given twice')
            ty = next(s[1] for s in spec if s[0] == name)
            vals[name] = self.coerce(a, ty, env, fname, name)
        for s in spec:
            if s[0] not in vals:
                if s[2] is REQ: raise err(call, f'{fname}(): missing argument "{s[0]}"', f'{fname}({", ".join(x[0] for x in spec)})')
                vals[s[0]] = s[2]
        return vals

    def coerce(self, node, ty, env, fname, pname):
        if ty == 'any': return node
        v = self.eval(node, env)
        bad = lambda: err(node, f'{fname}(): "{pname}" expects {ty}, got {v.type}',
                          {'item': 'write item("Meat")', 'species': 'write species("Greymon")',
                           'tech': 'write tech("Spit Fire")'}.get(ty))
        if ty == 'int':
            if v.type != 'int': raise bad()
            return v.val
        if ty == 'bool':
            if v.type != 'bool': raise bad()
            return v.val
        if ty in ('item', 'species', 'tech'):
            if v.type != ty: raise bad()
            return v.val
        if ty in ('card', 'screen', 'track'):
            if v.type not in (ty, 'int'): raise bad()
            return v.val
        if ty == 'entity':
            if v.type != 'entity': raise bad()
            return v.val
        if ty == 'ticks':
            if v.type not in ('int', 'ticks'): raise bad()
            return v.val
        if ty == 'text':
            if v.type == 'str': return ('wrap', v.val)
            if v.type != 'text': raise bad()
            return v.val
        if ty == 'tuple2':
            if v.type != 'tuple' or len(v.val) != 2 or any(x.type != 'int' for x in v.val): raise bad()
            return (v.val[0].val, v.val[1].val)
        if ty == 'entities':
            if v.type != 'list' or any(x.type != 'entity' for x in v.val): raise bad()
            return [x.val for x in v.val]
        if ty == 'str':
            if v.type != 'str': raise bad()
            return v.val
        if ty == 'ints':                                 # a number or a list of numbers
            if v.type in ('int', 'screen'): return [v.val]
            if v.type != 'list' or not v.val or any(x.type not in ('int', 'screen') for x in v.val): raise bad()
            return [x.val for x in v.val]
        raise AssertionError(ty)

    def wide(self, name, idv, node):
        if int(idv) > 255:
            if self.max_opcode_level < 1:
                raise err(node, f'id {idv} does not fit the original opcode {name}: it needs {name}16 (mod executable)',
                          'compile with --exe mods (or species), or use an id of 255 or less')
            self.required_opcode_level = max(self.required_opcode_level, 1); return name + '16'
        return name

    # ------------------------------------------------------------ statements
    def block(self, n, env):
        dead = False
        for s in n.stmts:
            if dead:
                if s.kind != 'label': self.warn.add(s, 'unreachable code after return/break/continue')
                dead = False
            self.stmt(s, env)
            if s.kind in ('return', 'break', 'continue'): dead = True

    def stmt(self, n, env):
        k = n.kind
        if k == 'block': return self.block(n, env)
        if BE.SRCMAP and getattr(n, 'pos', None) and len(n.pos) >= 2:      # source map: a comment the assembler turns into an offset
            f, ln = str(n.pos[0]), n.pos[1]
            from .py.lower import LINEMAP                                   # a statement lowered from a .py: its line there
            lm = LINEMAP.get(os.path.abspath(f))
            if lm and ln in lm[1]: f, ln = lm[0], lm[1][ln]
            env.out.append(f';@src {os.path.relpath(f, BE.ROOT) if os.path.isabs(f) else f}:{ln}')
        if k == 'expr': return self.call_stmt(n.expr, env)
        h = getattr(self, 'st_' + k)
        if k not in ('expr',): env.state['speaker'] = None
        return h(n, env)

    def st_if(self, n, env):
        out = env.out
        l_else, l_end = self.label('else'), self.label('end')
        conds = self.cond(n.cond, env)
        out += env.pre; env.pre.clear()
        out.append(f'    IF {", ".join(conds)}, else {l_else}')
        env.state['speaker'] = None; self.stmt(n.then, env)
        if n.els is not None: out.append(f'    JUMP_TO {l_end}')
        out.append(f'{l_else}:')
        if n.els is not None:
            env.state['speaker'] = None; self.stmt(n.els, env); out.append(f'{l_end}:')
        env.state['speaker'] = None

    def st_while(self, n, env):
        out = env.out; top, end = self.label('loop'), self.label('endloop')
        out.append(f'{top}:')
        conds = self.cond(n.cond, env)
        out += env.pre; env.pre.clear()
        out.append(f'    IF {", ".join(conds)}, else {end}')
        env.loops.append((top, end)); env.state['speaker'] = None
        self.stmt(n.body, env); env.loops.pop()
        out.append(f'    JUMP_TO {top}'); out.append(f'{end}:'); env.state['speaker'] = None

    def st_break(self, n, env):
        if not env.loops: raise err(n, '`break` outside a loop')
        env.out.append(f'    JUMP_TO {env.loops[-1][1]}')

    def st_continue(self, n, env):
        if not env.loops: raise err(n, '`continue` outside a loop')
        env.out.append(f'    JUMP_TO {env.loops[-1][0]}')

    def st_cutscene(self, n, env):
        # Trigger 44 is the engine's "do not turn the NPC" token: every script event start clears it (scriptPauseGame,
        # decomp/src/main/script_interp.c:2672) and the 14 sections of the original that set it never clear it. So the block sets it
        # and leaves; the engine clears it. (It used to write FADEOUT_HUD 0 and UNSET_TRIGGER 44, which no original section does.)
        env.out.append('    SET_TRIGGER 44')
        self.block(n.body, env); env.state['speaker'] = None

    def st_choice(self, n, env):
        out = env.out; opts = []
        for t, body, both in n.opts:
            v = self.eval(t, env)
            if v.type == 'str': text = v.val
            elif v.type == 'text' and v.val[0] == 'wrap': text = v.val[1]
            elif v.type == 'text' and len(v.val[1]) == 1 and len(v.val[1][0]) == 1: text = v.val[1][0][0]
            else: raise err(t, 'a choice option is one line: a string or text("key") of one row')
            opts.append((text, body, both))
            if '{raw ' not in text and not BE.fits(BE.plain(text)): self.errors.append(self.option_too_wide(t, v, BE.plain(text)))
        labels = [self.label('opt') for _ in opts]; l_end = self.label('end')
        who = 'TAMER'
        if getattr(n, 'who', None) is not None:
            wv = self.eval(n.who, env)
            if wv.type != 'entity': raise err(n.who, 'choice(who): an entity is expected')
            who = wv.val
        rows = 4 if who == '255' else 3                         # the speaker's name takes the box's first row (showTextbox)
        if len(opts) > rows and not getattr(n, 'keep', False):
            self.errors.append(err(n, f'a menu of {len(opts)} options: the box shows {rows} rows'
                                      + (' under the speaker\'s name' if rows == 3 else '') + f', so "{BE.plain(opts[rows][0])}" '
                                      'would not be drawn (the cursor can still go there)',
                                   'narrator.choose(...) has no name row: 4 options; more than that: ask in two menus'
                                   if rows == 3 and len(opts) == 4 else 'ask in two menus (a menu of 3, then another)'))
        if getattr(n, 'keep', False):
            if getattr(n, 'who', None) is not None: raise err(n, '`choice(keep)` keeps the dialog owner that is set: it takes no entity')
            env.state['speaker'] = None
        else: out.append(f'    SET_DIALOG_OWNER {who}')
        out.append(f'    SET_SELECTION {", ".join(labels)}')
        for text, _, _ in opts: out.append('        ' + BE.quote(BE.plain(text)))
        openc = getattr(n, 'openc', False)
        if not openc: out.append('    END_SELECTION')
        cancel = getattr(n, 'cancel', None)
        both = [lab for lab, (_, _, b) in zip(labels, opts) if b]
        if cancel is not None and both: raise err(n, 'a choice has either a `cancel =>` branch or an option marked `or cancel`, not both')
        if len(both) > 1: raise err(n, 'only one option can also be the cancel button')
        # `choice(open)`: no END_SELECTION; the code that follows SET_SELECTION is the first option's, unless the choice has a
        # cancel path (`cancel =>` / `or cancel`), which is then what follows it (some sections of the disc fall into other code)
        if cancel is not None: env.state['speaker'] = None; self.stmt(cancel, env)      # the triangle button
        # (an empty option that is also the cancel goes on after the choice, as one without `or cancel`: the same code for both)
        empty = [lab for lab, (_, b, x) in zip(labels, opts) if x and b.kind == 'block' and not b.stmts]
        if not openc or cancel is not None or both: out.append(f'    JUMP_TO {both[0] if both and not empty else l_end}')
        for lab, (_, body, _) in zip(labels, opts):
            out.append(f'{lab}:'); env.state['speaker'] = None
            self.stmt(body, env); out.append(f'    JUMP_TO {l_end}')
        out.append(f'{l_end}:'); env.state['speaker'] = None

    def option_too_wide(self, node, v, text):
        """A menu option is one row of the box: wider, it is cut at the edge and the rows below it are not drawn (seen in the
        game, 2026-10-14). Said at its line; a translation's names its key and bank."""
        width = f'{BE.text_units(text)} units, {BE.text_px(text)} px'
        where = self.bank.source_of(v.key) if v.key else None
        if where and not os.path.relpath(where).startswith('..'): where = os.path.relpath(where)
        tr = f' ({v.key} in {where})' if where else ''
        return err(node, f'menu option "{text}"{tr} is {width}: a menu row holds {BE.MAX_UNITS} units and {BE.MAX_PX} px; '
                         'a longer one is cut at the box edge and hides the options below it',
                   'shorten it (a menu option is a few words; the line before the menu can say more)')

    def st_let(self, n, env):
        e = n.expr
        if e.kind == 'call' and e.fn.kind == 'id' and self.syms.get(e.fn.name) is not None and self.syms[e.fn.name].kind == 'fn' \
                and self.syms[e.fn.name].node.sub:
            env.locals[n.name] = self.call_stmt(e, env, want=True); return
        if e.kind == 'call' and e.fn.kind == 'id' and e.fn.name in ('spawn', 'walk', 'run'):
            ent = self.call_stmt(e, env, want=True)
            env.locals[n.name] = V('entity', ent)
        else:
            env.locals[n.name] = self.eval(e, env)

    def st_await(self, n, env):
        v = self.eval(n.expr, env)
        if v.type != 'entity': raise err(n.expr, f'await expects an entity, a handle, `camera` or `all`, got {v.type}')
        env.out.append(f'    WAIT_FOR_ENTITY {v.val}')

    def st_assign(self, n, env):
        if getattr(n, 'target', None) is not None: v = self.eval(n.target, env)
        else: v = self.lookup(n.name, env)
        if v is None: raise err(n, f'unknown name "{n.name}"', self.near(n.name, self.known_names(env)).strip())
        if v.type == 'array': raise err(n, f'"{n.name}" is an array: write {n.name}[i] = ...')
        val = self.eval(n.expr, env)
        if v.type == 'flag':
            if n.op != '=' or val.type != 'bool': raise err(n, f'flag "{n.name}" is set with `{n.name} = true;` or `= false;`')
            v.val.writes += 1
            env.out.append(f'    {"SET_TRIGGER" if val.val else "UNSET_TRIGGER"} {v.val.num}'); return
        if v.type == 'var' and self.is_story_var(v.val):
            return self.assign_story(n, v, val, env)
        if v.type == 'var':
            if n.op not in ('=', '+=', '-='):
                raise err(n, f'`{n.op}` needs the story-state engine (the original variables are pstats)', 'compile with --profile extended-save --exe story-state')
            if val.type == 'var' and self.is_story_var(val.val) and n.op == '=':
                val.val.reads += 1; v.val.writes += 1
                env.out.append(f'    PSTAT_FROM_V p{v.val.num}, {self.vref(val.val)}'); return    # clamped to 0..255
            if val.type == 'var' and n.op == '=':           # one pstat into another (last_day = date_day;): COPY_PSTAT from, to
                val.val.reads += 1; v.val.writes += 1
                env.out.append(f'    COPY_PSTAT p{val.val.num}, p{v.val.num}'); return
            if val.type != 'int': raise err(n.expr, f'variable "{n.name}" takes an integer, got {val.type}')
            if not 0 <= val.val <= 255: raise err(n.expr, f'{val.val} does not fit: variables are u8 (0-255)')
            self.check_enum_range(v.val, val.val, n.expr)
            v.val.writes += 1
            op = {'=': 'SET_PSTAT', '+=': 'ADD_TO_PSTAT', '-=': 'REDUCE_PSTAT'}[n.op]
            env.out.append(f'    {op} p{v.val.num}, {val.val}'); return
        raise err(n, f'"{n.name}" is not a flag or a variable; it cannot be assigned')

    VAR_RANGE = {'u8': (0, 255), 'i8': (-128, 127), 'u16': (0, 65535), 'i16': (-32768, 32767),
                 'u32': (0, 0x7FFFFFFF), 'i32': (-0x80000000, 0x7FFFFFFF)}   # u32 values above i32 do not fit the engine's s32

    def require_story_state(self, node):
        if self.max_opcode_level < 2:
            raise err(node, 'story variables (32 bit) need the story-state engine (docs/mods/story-state-engine.md)', 'compile with --exe story-state')
        self.required_opcode_level = max(self.required_opcode_level, 2)

    def assign_story(self, n, v, val, env):
        """Engine story-state: assignment to a story or scene variable (32-bit): SET_V, ADD_V ... with a constant, COPY_V, ADD_VV ... with a variable."""
        self.require_story_state(n)
        name = n.name; ref = self.vref(v.val); v.val.writes += 1
        if val.type == 'var' and self.is_story_var(val.val):
            if n.op not in ('=', '+=', '-='): raise err(n.expr, f'`{n.op}` takes a constant on the right (story-state)')
            val.val.reads += 1
            env.out.append(f'    {"COPY_V" if n.op == "=" else ("ADD_VV" if n.op == "+=" else "SUB_VV")} {ref}, {self.vref(val.val)}')
            return
        if val.type == 'var' and n.op == '=':       # a pstat (raw p7, an alias or a scratch var) into a story variable
            val.val.reads += 1
            env.out.append(f'    V_FROM_PSTAT p{val.val.num}, {ref}'); return
        if val.type == 'bool': val = V('int', 1 if val.val else 0)
        if val.type != 'int': raise err(n.expr, f'variable "{name}" takes an integer or another variable, got {val.type}')
        lo, hi = self.VAR_RANGE.get(v.val.vtype or 'i32', (-0x80000000, 0x7FFFFFFF))
        if v.val.vtype not in self.VAR_RANGE: lo, hi = 0, 0x7FFFFFFF         # an enum: its values
        if not lo <= val.val <= hi:
            raise err(n.expr, f'{val.val} does not fit: "{name}" is {v.val.vtype or "i32"} ({lo}..{hi})')
        self.check_enum_range(v.val, val.val, n.expr)
        op = {'=': 'SET_V', '+=': 'ADD_V', '-=': 'SUB_V', '*=': 'MUL_V', '/=': 'DIV_V', '%=': 'MOD_V'}[n.op]
        if n.op in ('/=', '%=') and val.val == 0: raise err(n.expr, 'division by zero')
        env.out.append(f'    {op} {ref}, {val.val}')

    # ------------------------------------------------------------ calls
    def call_stmt(self, c, env, want=False):
        if c.fn.kind != 'id': raise err(c, 'unknown statement')
        f = c.fn.name
        s = self.syms.get(f)
        if s is not None and s.kind == 'fn':
            env.state['speaker'] = None
            if s.node.sub:
                r = self.call_sub(s, c, env, want=want); env.state['speaker'] = None; return r
            self.inline(s, c, env); env.state['speaker'] = None; return None
        h = BUILTINS.get(f)
        if h is None and self.generic_call(c, env, f): return None
        if h is None:
            raise err(c, f'unknown function "{f}"', 'builtins: ' + ', '.join(sorted(BUILTINS)[:12]) + ', ...' + self.near(f, list(BUILTINS) + list(self.syms)))
        if f != 'say': env.state['speaker'] = None
        spec, fn = h
        if f == 'asm': a = {}
        elif f == 'say':                       # say(who, text, more pages...)
            if len(c.args) < 2: raise err(c, 'say(who, text): the speaker and at least one text are required')
            head = Node('call', c, fn=c.fn, args=c.args[:2])
            a = self.bind(head, spec, env, f)
            a['more'] = [self.coerce(x, 'text', env, f, 'text') for _, x in c.args[2:]]
        else: a = self.bind(c, spec, env, f)
        r = fn(self, env, c, a)
        if want and r is None: raise err(c, f'{f}() gives no value to `let`')
        return r

    def inline(self, sym, c, env):
        fn = sym.node
        if sym in env.fn_stack: raise err(c, f'fn "{sym.name}" calls itself (functions are inlined)')
        spec = [(p[0], p[1], REQ if p[2] is None else self.eval(p[2], Env({})), ) for p in fn.params]
        # evaluate arguments in the caller's environment
        vals = {}
        for i, (nm, a) in enumerate(c.args):
            if nm is None:
                if i >= len(fn.params): raise err(a, f'{fn.name}() takes {len(fn.params)} arguments')
                pn = fn.params[i][0]
            else:
                pn = nm
                if pn not in [p[0] for p in fn.params]: raise err(a, f'{fn.name}() has no argument "{nm}"')
            vals[pn] = self.eval(a, env)
        sub = Env(self.script_npcs_for(env), self_ent=env.self_ent, parent=env)
        sub.fn_end = self.label('fnend'); sub.fn_used = False
        for (pn, pt, pd, ptok) in fn.params:
            if pn in vals:
                v = vals[pn]
                ok = {'int': ('int',), 'bool': ('bool',), 'ticks': ('int', 'ticks'), 'text': ('text', 'str'),
                      'entity': ('entity',), 'item': ('item',), 'species': ('species',), 'tech': ('tech',),
                      'card': ('card', 'int'), 'screen': ('screen', 'int'), 'track': ('track', 'int'),
                      'str': ('str',)}
                if pt not in ok: raise err(ptok, f'unknown parameter type "{pt}"', 'types: ' + ', '.join(ok))
                if v.type not in ok[pt]: raise err(c, f'{fn.name}(): "{pn}" expects {pt}, got {v.type}')
                sub.locals[pn] = v
            elif pd is not None: sub.locals[pn] = self.eval(pd, Env({}))
            else: raise err(c, f'{fn.name}(): missing argument "{pn}"')
        sub.fn_stack = env.fn_stack + [sym]; sub.loops = []
        self.block(fn.body, sub)
        if sub.fn_used: env.out.append(f'{sub.fn_end}:')

    def script_npcs_for(self, env):
        return env.npcs

    # ---- builtins
    def b_say(self, env, c, a):
        ent = a['who']; texts = a['text']; extra = a['more']
        # one SET_DIALOG_OWNER per `say` statement, always: the engine sets the box up again (setupDialogueBox, scriptPauseGame), and two
        # SHOW_TEXTBOX in a row are ONE chained box whose pages go on without closing (showTextbox: the next opcode is SHOW_TEXTBOX), so
        # `say(a, x); say(a, y);` are two boxes and `say(a, x, y);` is one
        env.out.append(f'    SET_DIALOG_OWNER {ent}'); env.state['speaker'] = ent
        nodes = [x for _, x in c.args[1:]]                      # (each page's own node: a warning points at its line)
        for t, node in zip([texts] + extra, nodes):
            self.say(env, ent, t, node)

    def say(self, env, ent, text, node=None):
        lines = 4 if ent == '255' else 3
        kind, val = text
        pages = BE.wrap(val, lines) if kind == 'wrap' else [[BE.plain(r) for r in p] for p in val]
        if kind == 'wrap' and node is not None and len(pages) > 1 and len(pages[-1]) == 1 and len(pages[-1][0].split()) <= 2:
            self.warn.add(node, f'this line fills {len(pages) - 1} box page{"s" if len(pages) > 2 else ""} and leaves only '
                                f'"{pages[-1][0]}" for the last one: shorten it, or split it into pages (say("...", "..."))')
        for page in pages:
            env.out.append('    SHOW_TEXTBOX')
            for l in page: env.out.append('        ' + BE.quote(l))

    def b_give(self, env, c, a):
        it = a['item']; env.out.append(f'    {self.wide("GIVE_ITEM", it, c)} {it}, {self.u8(a["count"], c)}')

    def b_take(self, env, c, a):
        it = a['item']; env.out.append(f'    {self.wide("REMOVE_ITEM", it, c)} {it}, {self.u8(a["count"], c)}')

    def u8(self, n, node):
        if not 0 <= n <= 255: raise err(node, f'{n} does not fit in a byte (0-255)')
        return n

    def b_give_bits(self, env, c, a): env.out.append(f'    ADD_MONEY {a["amount"]}')
    def b_take_bits(self, env, c, a): env.out.append(f'    REDUCE_MONEY {a["amount"]}')
    def b_merit(self, env, c, a): env.out.append(f'    ADD_MERIT {a["amount"]}')
    def b_give_card(self, env, c, a): env.out.append(f'    {self.wide("GIVE_CARD", a["card"], c)} {a["card"]}')
    def b_learn(self, env, c, a): env.out.append(f'    {self.wide("LEARN_MOVE", a["tech"], c)} {a["tech"]}')
    def b_music(self, env, c, a): env.out.append(f'    {self.wide("SET_BGM", a["track"], c)} {a["track"]}')
    def b_sound(self, env, c, a): env.out.append(f'    PLAY_SOUND {a["bank"]}, {a["n"]}')

    def b_warp(self, env, c, a):
        env.out.append(f'    {self.wide("WARP_TO", a["screen"], c)} {a["screen"]}, {a["exit"]}, {a["section"]}')

    def b_wait(self, env, c, a): env.out.append(f'    DELAY {a["ticks"]}')
    def b_animate(self, env, c, a): env.out.append(f'    PLAY_ANIMATION {a["who"]}, {a["anim"]}')
    def b_face(self, env, c, a): env.out.append(f'    ENTITY_LOOK_AT_ENTITY {a["who"]}, {a["target"]}')
    def b_rotate(self, env, c, a): env.out.append(f'    ENTITY_SET_ROTATION {a["who"]}, {a["angle"]}')
    def b_hide_hud(self, env, c, a): env.out.append('    FADEOUT_HUD 0')
    def b_cutscene_start(self, env, c, a): env.out.append('    SET_TRIGGER 44')
    def b_remove(self, env, c, a): env.out.append(f'    UNLOAD_ENTITY {a["who"]}')
    def b_set_trigger(self, env, c, a):
        self.trigger_write(a['n'], c, env); env.out.append(f'    SET_TRIGGER {a["n"]}')
    def b_clear_trigger(self, env, c, a):
        self.trigger_write(a['n'], c, env); env.out.append(f'    UNSET_TRIGGER {a["n"]}')

    def trigger_write(self, n, c, env=None):
        if env is not None and env.port: return
        if not 717 <= n <= 799:
            self.warn.add(c, f'trigger {n} is used by the game', 'only 717-799 are free for new content (docs/mods/dws.md); name a game trigger with `alias flag`')

    def b_walk(self, env, c, a, run=False):
        op = 'ENTITY_WALK_TO_WITH_CAMERA' if a['camera'] else 'ENTITY_WALK_TO'
        env.out.append(f'    {op} {a["who"]}, {a["x"]}, {a["z"]}, {1 if run or a.get("run") else 0}, 0')
        return a['who']

    def b_run(self, env, c, a): return self.b_walk(env, c, a, run=True)

    def b_camera_to(self, env, c, a): env.out.append(f'    MOVE_CAMERA_TO {a["speed"]}, {a["x"]}, {a["z"]}')
    def b_camera_on(self, env, c, a): env.out.append(f'    MOVE_CAMERA_TO_ENTITY {a["who"]}, {a["speed"]}')

    def b_battle(self, env, c, a):
        foes = a['foes']
        if foes is None:
            env.out += ['    FADEOUT_HUD 0', '    DELAY 1', '    START_BATTLE 0']; return
        if len(foes) > 3: raise err(c, 'at most 3 enemies')
        if not foes: raise err(c, 'battle(foes: [...]) needs at least one enemy')
        foes = foes + ['255'] * (3 - len(foes))
        esc = a['escape']
        env.out += ([] if esc else ['    SET_TRIGGER 1']) + ['    SET_PSTAT p250, 1'] + \
                   [f'    SET_PSTAT p{251 + k}, {f}' for k, f in enumerate(foes)] + \
                   ['    FADEOUT_HUD 0', '    DELAY 1', '    START_BATTLE 0'] + \
                   ([] if esc else ['    UNSET_TRIGGER 1']) + ['    SET_PSTAT p250, 0']

    def b_spawn(self, env, c, a):
        dig = a['species']; slot = a['slot']
        top = 15 if self.max_opcode_level >= 2 else 7
        if not 0 <= slot <= top: raise err(c, f'slot is 0-{top} (entities 5-{top + 5})' + ('' if top == 15 else '; --exe story-state has 16 slots'))
        if env.ev == 'talk':
            self.warn.add(c, 'spawn() inside a talk section: a second LOAD_DIGIMON in a talk hangs the game',
                          'spawn from `on enter` (docs/mods/dws.md "Limits")')
        env.out += [f'    {self.wide("LOAD_DIGIMON", dig, c)} {dig}',
                    f'    {self.wide("SET_DIGIMON", dig, c)} {dig}, {slot}, {1 if a["talks"] else 0}']
        return str(5 + slot)

    def b_recruit(self, env, c, a):
        sp = a['species']
        if not 0 <= sp < 112: raise err(c, f'species {sp}: recruit flags exist for types 0-111 (trigger 200+type)')
        env.out.append(f'    SET_TRIGGER {200 + sp}')

    def b_unrecruit(self, env, c, a):
        sp = a['species']
        if not 0 <= sp < 112: raise err(c, f'species {sp}: recruit flags exist for types 0-111 (trigger 200+type)')
        env.out.append(f'    UNSET_TRIGGER {200 + sp}')

    def b_asm(self, env, c, a):
        for nm, node in c.args:
            if node.kind == 'str': env.out.append('    ' + node.v)
            else:
                v = self.eval(node, env)
                if v.type != 'text': raise err(node, 'asm() takes strings (instructions) and text("key") rows')
                k, val = v.val
                rows = [val] if k == 'wrap' else [r for p in val for r in p]
                for r in rows: env.out.append('        ' + BE.quote(BE.plain(r)))

    def b_end_section(self, env, c, a): env.out.append('    END_SECTION')

    def place(self, call):
        if call.fn.name != 'place': raise err(call, 'expected place(...)')
        env = Env({})
        a = self.bind(call, PLACE_SPEC, env, 'place')
        stats = {k: a[k] for k in ('hp', 'mp', 'off', 'def', 'speed', 'brain', 'bits') if a[k] is not None}
        if a['at']: stats['posX'], stats['posZ'] = a['at']
        if a['range'] is not None: stats['trackingRange'] = a['range']   # the chase range (world units; 0 = waits to be touched)
        if a['section'] is not None: stats['section'] = a['section']      # a new slot's talk section (default 5 + slot)
        if a['map'] is not None:                                          # the screen's .MAP is the mod's own file (a new screen)
            # SCREEN_CONTENT is the current build's generated maps. Authored
            # new_screen paths may name a developer's build/what-the-island-forgot-maps folder.
            path = next((os.path.join(BE.ROOT, d, os.path.basename(a['map']))
                         for d in reversed(BE.SCREEN_DIRS)
                         if os.path.isfile(os.path.join(BE.ROOT, d, os.path.basename(a['map'])))),
                        a['map'] if os.path.isabs(a['map']) else os.path.join(BE.ROOT, a['map']))
            if not os.path.exists(path):
                raise err(call, f'place(): map "{a["map"]}" not found (a path from the repository root)', 'build the map file first')
            stats['map'] = path
        dig = a['species']
        if dig >= 180 and BE._species:
            for k, v in BE._species.wild_stats(dig).items(): stats.setdefault(k, v)
        for scr in a['screen']:                        # one screen, or a list (`const TOP = [168, 169];`): the same slot on each
            self.b.placements.append((scr, a['slot'], dig, dict(stats), call.pos, a['like']))

    # ------------------------------------------------------------ conditions
    def cond(self, n, env):
        """Flat IF conditions. IF folds left to right without precedence or grouping."""
        seq = []
        def add(join, x):
            if x.kind == 'binary' and x.op == 'in':      # v in [a, b, c]  ==  v == a || v == b || v == c
                if join == 'and ':
                    raise err(x, '`in [...]` cannot follow `&&`: the IF folds left to right, so the list would not be a group',
                              'put the `in` test first, or nest ifs')
                lst = self.eval(x.r, env)
                if lst.type != 'list' or not lst.val or any(v.type not in ('int', 'item', 'species', 'tech', 'card') for v in lst.val):
                    raise err(x.r, 'the right side of `in` is a non-empty list of numbers or ids: x in [item("Meat"), item("Sirloin")]')
                for k, v in enumerate(lst.val):
                    seq.append((join if k == 0 else 'or ', Node('binary', x, op='==', l=x.l, r=Node('num', x.r, v=int(v.val)))))
            else:
                seq.append((join, x))
        def walk(x, join):
            if x.kind == 'binary' and x.op in ('&&', '||', '~>'):
                walk(x.l, join)
                if x.r.kind == 'binary' and x.r.op in ('&&', '||', '~>'):
                    raise err(x.r, 'a group of conditions on the right of && / || cannot be compiled',
                              'IF evaluates left to right without grouping: nest ifs, or reorder so the longer chain is first')
                add({'&&': 'and ', '||': 'or ', '~>': ''}[x.op], x.r)
            else:
                add('', x)
        walk(n, '')
        out = []
        for join, a in seq:
            out.append(join + self.atom(a, env, False))
        return out

    def atom(self, t, env, neg):
        pre = env.pre
        def addpre(l):
            if l not in pre: pre.append(l)
        if t.kind == 'unary' and t.op == '!':
            return self.atom(t.e, env, not neg)
        if t.kind == 'binary' and t.op in ('&&', '||'):
            raise err(t, 'a parenthesised group cannot be negated or nested here', 'IF has no grouping: split into nested ifs')
        if t.kind in ('index', 'member') and not (t.kind == 'member' and t.obj.kind == 'id' and t.obj.name in ('partner', 'clock')):
            v = self.eval(t, env)
            if v.type == 'flag':
                v.val.reads += 1; return f'{"not " if neg else ""}trigger {v.val.num}'
            raise err(t, f'"{getattr(t, "name", "this")}" is {v.type}, not a condition')
        if t.kind == 'id':
            nm = t.name
            if nm in ('won', 'lost', 'fled'):
                val = {'won': 1, 'lost': 255, 'fled': 0}[nm]
                return f'p255 {"!=" if neg else "=="} {val}'
            v = self.lookup(nm, env)
            if v is None: raise err(t, f'unknown name "{nm}"', self.near(nm, self.known_names(env)).strip() or None)
            if v.type == 'flag':
                v.val.reads += 1; return f'{"not " if neg else ""}trigger {v.val.num}'
            if v.type == 'bool': raise err(t, 'constant condition')
            raise err(t, f'"{nm}" is {v.type}, not a condition', 'compare a variable: x == 1' if v.type == 'var' else None)
        if t.kind == 'call':
            f = t.fn.name if t.fn.kind == 'id' else None
            if t.fn.kind == 'member' and t.fn.obj.kind == 'id' and t.fn.obj.name == 'partner' and t.fn.name == 'is':
                a = self.bind(t, [('species', 'species', REQ)], env, 'partner.is')
                dig = a['species']
                if dig > 255 or getattr(self, 'exe', 'original') in ('species', 'story-state'):     # (a partner past 255 would
                    # read as its low byte in a pstat there: the wide register for every test of the species)
                    self.need_wide(t); addpre(f'    STORE_DIGIMON_TYPE_W w{BE.W_TYPE}')
                    return f'w{BE.W_TYPE} {"!=" if neg else "=="} {dig}'
                addpre(f'    STORE_DIGIMON_TYPE p{BE.P_TYPE}')
                return f'p{BE.P_TYPE} {"!=" if neg else "=="} {dig}'
            if f == 'trigger':
                a = self.bind(t, [('n', 'int', REQ)], env); return f'{"not " if neg else ""}trigger {a["n"]}'
            if f == 'has':
                a = self.bind(t, [('item', 'item', REQ)], env)
                return self.has(a['item'], '>=', 1, neg, t)
            if f == 'is_recruited':
                a = self.bind(t, [('species', 'species', REQ)], env, 'is_recruited')
                if not 0 <= a['species'] < 112: raise err(t, 'recruit flags exist for types 0-111')
                return f'{"not " if neg else ""}trigger {200 + a["species"]}'
            if f == 'knows':
                a = self.bind(t, [('tech', 'tech', REQ)], env, 'knows')
                if a['tech'] > 255:
                    self.need_wide(t); return f'{"not " if neg else ""}move16 {a["tech"]}'
                return f'{"not " if neg else ""}move {a["tech"]}'
            if f == 'condition':
                a = self.bind(t, [('bit', 'int', REQ)], env, 'condition'); return f'{"not " if neg else ""}cond {a["bit"]}'
            if f == 'chance':
                a = self.bind(t, [('percent', 'int', REQ)], env)
                if neg: raise err(t, 'chance() cannot be negated', 'use the complementary percentage: chance(70) instead of !chance(30)')
                addpre(f'    STORE_RANDOM p{BE.P_RANDOM}, 99'); return f'p{BE.P_RANDOM} < {a["percent"]}'
            raise err(t, f'"{f or "call"}" is not a condition',
                      'conditions: flag, !flag, has(item), has(item) >= n, bits >= n, clock.hour >= n, partner.is(species), '
                      'partner.hp >= n, chance(n), won/lost/fled, var == n')
        if t.kind == 'binary' and t.op in ('==', '!=', '<', '<=', '>', '>='):
            op = OPS_FLIP[t.op] if neg else t.op
            l, r = t.l, t.r
            sl = self.story_left(l, env)
            if sl is not None:            # story-state engine: a 32-bit variable against a number or another variable (IF 0x2A / 0x2B)
                self.require_story_state(t)
                rv = self.eval(r, env); sl.reads += 1
                if rv.type == 'var' and self.is_story_var(rv.val):
                    rv.val.reads += 1; return f'{self.vref(sl)} {op} {self.vref(rv.val)}'
                if rv.type == 'bool': rv = V('int', 1 if rv.val else 0)
                if rv.type != 'int': raise err(r, 'the right side of a comparison is a number or a story variable')
                if not -0x80000000 <= rv.val <= 0x7FFFFFFF: raise err(r, f'{rv.val} does not fit the engine\'s signed 32 bits')
                return f'{self.vref(sl)} {op} {rv.val}'
            rv = self.eval(r, env)
            if rv.type != 'int': raise err(r, 'the right side of a comparison is a number')
            n = rv.val
            if l.kind == 'call' and l.fn.kind == 'id' and l.fn.name == 'has':
                a = self.bind(l, [('item', 'item', REQ)], env, 'has')
                return self.has(a['item'], t.op, n, neg, t)
            if l.kind == 'call' and l.fn.kind == 'id' and l.fn.name in ('has_card', 'stat'):
                a = self.bind(l, [('n', 'int', REQ)], env, l.fn.name)
                return f'{"card" if l.fn.name == "has_card" else "stat"} {a["n"]} {op} {n}'
            if l.kind == 'id' and (self.lookup(l.name, env) or V('', 0)).type == 'wreg':
                return f'w{self.lookup(l.name, env).val} {op} {n}'
            if l.kind == 'member' and l.obj.kind == 'id' and (f'{l.obj.name}.{l.name}' in self.syms):
                v = self.eval(l, env)
                if v.type == 'var': v.val.reads += 1; return self.byte_test(v.val.num, op, n, t, f'{l.obj.name}.{l.name}')
            if l.kind == 'index':
                v = self.eval(l, env)
                if v.type == 'var': v.val.reads += 1; return self.byte_test(v.val.num, op, n, t, 'this value')
            if l.kind == 'member' and l.obj.kind == 'id':
                o, m = l.obj.name, l.name
                if o == 'clock' and m in CLOCK:
                    addpre(f'    STORE_DATE p{BE.P_DATE}'); return self.byte_test(BE.P_DATE + CLOCK.index(m), op, n, t, f'clock.{m}')
                if o == 'partner' and m in STATS:
                    return f'stat {STATS[m]} {op} {n}'
                if o == 'partner': raise err(l, f'unknown partner stat "{m}"', 'stats: ' + ', '.join(STATS))
                if o == 'clock': raise err(l, f'unknown clock field "{m}"', 'year, day, hour, minute')
            if l.kind == 'id' and l.name in ('bits', 'money'):
                return f'money {op} {n}'
            if l.kind == 'id':
                v = self.lookup(l.name, env)
                if v is None: raise err(l, f'unknown name "{l.name}"', self.near(l.name, self.known_names(env)).strip() or None)
                if v.type == 'var':
                    v.val.reads += 1; return self.byte_test(v.val.num, op, n, t, l.name)
                raise err(l, f'"{l.name}" is {v.type}: only variables, bits, clock.*, partner.* and has() can be compared')
            raise err(l, 'the left side of a comparison must be a variable, bits, clock.*, partner.* or has(item)')
        raise err(t, 'not a condition')

    def byte_test(self, num, op, n, node, name):
        """`pN OP n`: the IF of the original engine compares a byte (a saved counter, a pstat) with a byte: a number past
        0-255 would make the test always true or always false, so it is an error at its line (the .py one for a story file)."""
        if not 0 <= n <= 255:
            always = {'==': False, '!=': True, '<': n > 255, '<=': n > 255, '>': n < 0, '>=': n < 0}[op]
            raise err(node, f'{name} is a byte on this engine (0-255): `{name} {op} {n}` would always be {"true" if always else "false"}',
                      'count to 255 at most (or keep a second counter); the story-state engine (--exe story-state) has 32-bit story variables')
        return f'p{num} {op} {n}'

    def story_left(self, l, env):
        """The story or scene variable (extended-save profile) a comparison starts with, or None."""
        if self.profile == 'original': return None
        try:
            if l.kind == 'id': v = self.lookup(l.name, env)
            elif l.kind == 'member' and l.obj.kind == 'id' and f'{l.obj.name}.{l.name}' in self.syms: v = self.eval(l, env)
            elif l.kind == 'index': v = self.eval(l, env)
            else: return None
        except DwsError:
            return None
        return v.val if v is not None and v.type == 'var' and self.is_story_var(v.val) else None

    def has(self, it, op, n, neg, node):
        if neg: op = OPS_FLIP[op]
        name = self.wide('item', it, node) if it > 255 else 'item'
        return f'{"item16" if it > 255 else "item"} {it} {op} {n}'

    def need_wide(self, node):
        if self.max_opcode_level < 1:
            raise err(node, 'a species above 255 needs the wide register (mod executable)', 'compile with --exe mods')
        self.required_opcode_level = max(self.required_opcode_level, 1)


# name -> (spec, handler). spec: (argument, type, default)
def _b(spec, h): return (spec, h)
P = Program
BUILTINS = {
    'say': ([('who', 'entity', REQ), ('text', 'text', REQ)], P.b_say),
    'give': ([('item', 'item', REQ), ('count', 'int', 1)], P.b_give),
    'take': ([('item', 'item', REQ), ('count', 'int', 1)], P.b_take),
    'give_bits': ([('amount', 'int', REQ)], P.b_give_bits),
    'take_bits': ([('amount', 'int', REQ)], P.b_take_bits),
    'merit': ([('amount', 'int', REQ)], P.b_merit),
    'give_card': ([('card', 'card', REQ)], P.b_give_card),
    'learn': ([('tech', 'tech', REQ)], P.b_learn),
    'music': ([('track', 'track', REQ)], P.b_music),
    'sound': ([('bank', 'int', REQ), ('n', 'int', REQ)], P.b_sound),
    'warp': ([('screen', 'screen', REQ), ('exit', 'int', 0), ('section', 'int', 255)], P.b_warp),
    'wait': ([('ticks', 'ticks', REQ)], P.b_wait),
    'animate': ([('who', 'entity', REQ), ('anim', 'int', REQ)], P.b_animate),
    'face': ([('who', 'entity', REQ), ('target', 'entity', REQ)], P.b_face),
    'rotate': ([('who', 'entity', REQ), ('angle', 'int', REQ)], P.b_rotate),
    'hide_hud': ([], P.b_hide_hud),
    'cutscene_start': ([], P.b_cutscene_start),
    'remove': ([('who', 'entity', REQ)], P.b_remove),
    'set_trigger': ([('n', 'int', REQ)], P.b_set_trigger),
    'clear_trigger': ([('n', 'int', REQ)], P.b_clear_trigger),
    'walk': ([('who', 'entity', REQ), ('x', 'int', REQ), ('z', 'int', REQ), ('camera', 'bool', False)], P.b_walk),
    'run': ([('who', 'entity', REQ), ('x', 'int', REQ), ('z', 'int', REQ), ('camera', 'bool', False)], P.b_run),
    'camera_to': ([('x', 'int', REQ), ('z', 'int', REQ), ('speed', 'int', 20)], P.b_camera_to),
    'camera_on': ([('who', 'entity', REQ), ('speed', 'int', 10)], P.b_camera_on),
    'battle': ([('foes', 'entities', None), ('escape', 'bool', False)], P.b_battle),
    'spawn': ([('species', 'species', REQ), ('slot', 'int', 3), ('talks', 'bool', False)], P.b_spawn),
    'recruit': ([('species', 'species', REQ)], P.b_recruit),
    'unrecruit': ([('species', 'species', REQ)], P.b_unrecruit),
    'asm': ([], P.b_asm),
    'end_section': ([], P.b_end_section),
}
PLACE_SPEC = [('species', 'species', REQ), ('screen', 'ints', REQ), ('slot', 'int', REQ), ('at', 'tuple2', None), ('section', 'int', None),
              ('like', 'int', None), ('hp', 'int', None), ('mp', 'int', None), ('off', 'int', None), ('def', 'int', None),
              ('speed', 'int', None), ('brain', 'int', None), ('bits', 'int', None), ('range', 'int', None), ('map', 'str', None)]
