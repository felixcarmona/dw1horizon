"""Language extensions of milestone 1b, mixed into gen.Program:

* generic commands: every instruction of the interpreter is a typed command (registry.py), so asm() is
  never needed: `entity_walk_to(5, 100, -20, 0, 0)`, `set_obj_visibility(3, 1)`, `call_routine(routine("shop"))`;
* labels and jumps: `name:`, `goto L;`, `gosub L;`, `unless (cond) goto L;`;
* subroutines: `sub name(a: u8) -> u8 { }` compiled once per script as a JUMP_AND_LINK target;
* loops: `loop { }`, `repeat (n) { }`, `for i in 0..n { }`; `par { }` (start several walks, await all);
* `match (var) { 0 => ..., 1 => ..., _ => ... }` (SWITCH when the cases are 0..n-1, else an IF chain);
* arrays, groups, enums, qualified names (`Group.name`, `module.name`, `Enum.Value`, `flags[3]`);
* whole scripts: `script N port { ... }` and `maphead port { ... }`, the output of the decompiler.
"""
import re
from . import backend as BE
from dws import bytecode
from .diag import DwsError, err
from .parser import Node
from . import registry as R

INT_RANGE = {'u8': (0, 255), 'u16': (0, 65535), 's16': (-32768, 32767), 's32': (-2 ** 31, 2 ** 31 - 1)}
INT_FIELDS = {'m': 'u8', 'u8': 'u8', 'M': 'u16', 'm16': 'u16', 's': 'u16', 'S': 'u16', 'k16': 'u16', 'u16': 'u16',
              's16': 's16', 's32': 's32', 'i16': 'u16', 'd16': 'u16', 'v16': 'u16'}


def is_original(node):
    """`original(L)`: the label L of the original script (outside the event being written)."""
    return node.kind == 'call' and node.fn.kind == 'id' and node.fn.name == 'original' and len(node.args) == 1 \
        and node.args[0][0] is None and node.args[0][1].kind == 'id'


class Elem:
    """One element of a flag/var array; counters go to the array."""
    def __init__(self, parent, idx):
        self.parent = parent; self.idx = idx; self.num = parent.num + idx; self.kind = parent.kind
        self.name = f'{parent.name}[{idx}]'; self.node = parent.node; self.vtype = parent.vtype; self.count = None
        self.pub = parent.pub; self.alias = parent.alias; self.scope = parent.scope

    reads = property(lambda s: s.parent.reads, lambda s, v: setattr(s.parent, 'reads', v))
    writes = property(lambda s: s.parent.writes, lambda s, v: setattr(s.parent, 'writes', v))


class Ext:
    # ------------------------------------------------------------ names
    def raw_name(self, name):
        """pN: a raw pstat, wN: a wide register; the engine's own numbers, usable anywhere."""
        from .gen import V, Sym
        m = re.fullmatch(r'p(\d+)', name)
        if m and int(m.group(1)) <= 255:
            key = ('raw', int(m.group(1)))
            if key not in self.raws:
                self.raws[key] = Sym('var', name, None, num=int(m.group(1)), scope='raw', alias=True, count=None, vtype='u8',
                                     root=False)
            return V('var', self.raws[key])
        m = re.fullmatch(r'w(\d+)', name)
        if m and int(m.group(1)) < 64: return V('wreg', int(m.group(1)))
        return None

    def qualified(self, n, env):
        from .gen import V
        o = n.obj.name; key = f'{o}.{n.name}'
        if key in self.syms:
            s = self.syms[key]
            if s.kind in ('flag', 'var'):
                return V('array', s) if s.count else V(s.kind, s)
            if s.kind == 'const': return s.value
            return V('fn', s)
        if o in self.enums:
            vals = self.enums[o]['values']
            if n.name not in vals:
                raise err(n, f'enum {o} has no value "{n.name}"', 'values: ' + ', '.join(vals))
            return V('int', vals[n.name])
        if o in self.mod_names:
            s = self.syms.get(n.name)
            if s is None or getattr(s, 'module', None) != o:
                raise err(n, f'module "{o}" has no "{n.name}"')
            if not s.pub and s.module != self.module: raise err(n, f'"{n.name}" is private to module {o}', 'declare it `pub`')
            return V(s.kind, s) if s.kind in ('flag', 'var') else (s.value if s.kind == 'const' else V('fn', s))
        raise err(n, f'unknown name "{key}"')

    def index(self, n, env):
        from .gen import V
        v = self.eval(n.obj, env)
        if v.type != 'array': raise err(n, f'"{getattr(n.obj, "name", "this")}" is not an array')
        i = self.eval(n.idx, env)
        if i.type != 'int':
            raise err(n.idx, 'the index of an array must be a constant in original',
                      'runtime indexes (flags[i]) need the story-state interpreter; use `match` or a constant')
        sym = v.val
        if not 0 <= i.val < sym.count:
            raise err(n.idx, f'index {i.val} is outside {sym.name}[0..{sym.count - 1}]')
        return V(sym.kind, Elem(sym, i.val))

    def check_enum_range(self, sym, val, node):
        vt = getattr(sym, 'vtype', None)
        if vt in self.enums:
            ok = set(self.enums[vt]['values'].values())
            if val not in ok:
                raise err(node, f'{val} is not a value of enum {vt}', 'values: ' + ', '.join(f'{k}={v}' for k, v in self.enums[vt]['values'].items()))

    # ------------------------------------------------------------ operand conversion
    def pstat_of(self, node, env, what='pstat'):
        v = self.eval(node, env)
        if v.type != 'var': raise err(node, f'expected a {what} (p7 or a declared var), got {v.type}')
        if self.is_story_var(v.val):
            raise err(node, f'"{v.val.name}" is a story variable (32 bit, saved in the extension): this command takes a pstat',
                      'copy it first: `u8_var = story_var;` (a scratch/raw pstat such as p110), or pass a raw pstat p7')
        v.val.reads += 1; v.val.writes += 1
        return f'p{v.val.num}'

    def trigger_of(self, node, env):
        v = self.eval(node, env)
        if v.type == 'flag':
            v.val.reads += 1; v.val.writes += 1; return str(v.val.num)
        if v.type == 'int': return str(v.val)
        raise err(node, f'expected a trigger number or a declared flag, got {v.type}')

    def label_of(self, node, env):
        if is_original(node):                                   # a label of the original script, outside this event
            self.deprecated_original(node, env); return node.args[0][1].name
        if node.kind != 'id': raise err(node, 'a label name is expected')
        return self.resolve_label(env, node.name, node)

    SEC_LABEL = re.compile(r'^sec\d+\w*$')

    def resolve_label(self, env, name, node):
        """A jump target: a label of this event, a shared block or `shared NAME:` label of the script (sh_NAME), or the entry
        of a section of the script (`secN`, as the original's header names it)."""
        if env.port: env.lab['used'].append((name, node)); return self.ulabel(env, name)
        if name in getattr(self, 'shared_names', {}).get(env.sid, {}): return self.shared_label(name)
        if self.SEC_LABEL.match(name): return name
        env.lab['used'].append((name, node))
        return self.ulabel(env, name)

    def deprecated_original(self, node, env):
        if getattr(self, 'quiet_original', False): return
        self.warn.add(node, '`original(L)` is deprecated: the story sources are the whole script now; write the shared code as '
                            '`shared L { ... }` in the script and jump to it with `goto L;` (or `gosub L;`)')

    def ulabel(self, env, name):
        if env.port: return name
        return f'u{env.section}_{name}' if not env.sub_name else f'u_{env.sub_name}_{name}'

    def entity_of(self, node, env):
        v = self.eval(node, env)
        if v.type == 'int': return str(v.val)
        if v.type != 'entity': raise err(node, f'expected an entity (tamer, partner, an npc or its number), got {v.type}')
        return v.val

    def int_of(self, node, env, rng, name):
        v = self.eval(node, env)
        if v.type not in ('int', 'screen', 'card', 'track', 'ticks'): raise err(node, f'{name}: expected a number, got {v.type}')
        lo, hi = INT_RANGE[rng]
        if not lo <= v.val <= hi: raise err(node, f'{name}: {v.val} does not fit ({lo}..{hi})')
        return v.val

    def field_value(self, f, node, env, cname, k):
        if f == 'p': return self.pstat_of(node, env)
        if f == 't': return self.trigger_of(node, env)
        if f == 'l': return self.label_of(node, env)
        if f == 'e': return self.entity_of(node, env)
        if f == 'w':
            v = self.eval(node, env)
            if v.type != 'wreg': raise err(node, f'{cname}: expected a wide register (w3)')
            return f'w{v.val}'
        if f == 'V':
            v = self.eval(node, env)
            if v.type == 'var' and self.is_story_var(v.val):
                v.val.reads += 1; v.val.writes += 1; return self.vref(v.val)
            if v.type == 'int': return str(v.val)       # a raw variable index
            raise err(node, f'{cname}: expected a story variable (a persistent or scene var of the extended-save profile), got {v.type}',
                      'compile with --profile extended-save --exe story-state')
        if f == 'c':
            v = self.eval(node, env)
            if v.type != 'str' or v.val not in bytecode.CMP: raise err(node, f'{cname}: a comparison in quotes: "==" "!=" ">=" "<=" ">" "<"')
            return v.val
        if f in ('i', 'd', 'v', 'i16', 'd16', 'v16'):
            kind = {'i': 'item', 'd': 'species', 'v': 'tech'}[f[0]]
            v = self.eval(node, env)
            if v.type not in (kind, 'int'): raise err(node, f'{cname}(): argument {k + 1} expects {kind}, got {v.type}',
                                                         f'write {kind}("..") or {kind}(number)')
            return str(v.val)
        if f in INT_FIELDS: return str(self.int_of(node, env, INT_FIELDS[f], f'{cname}() argument {k + 1}'))
        raise AssertionError(f)

    # ------------------------------------------------------------ generic commands
    SPECIAL_STMT = {'set_selection', 'end_selection', 'show_textbox', 'switch', 'switch_w', 'data'}

    def generic_call(self, c, env, f):
        """Returns True when `f` was a registry command or a special statement."""
        if f in self.SPECIAL_STMT:
            env.state['speaker'] = None; self.special_stmt(c, env, f); return True
        cmd = R.COMMANDS.get(f)
        if cmd is None: return False
        env.state['speaker'] = None
        if any(nm for nm, _ in c.args): raise err(c, f'{f}() takes positional arguments only')
        if f == 'call_routine' and len(c.args) == 1 and c.args[0][1].kind == 'call':
            c = Node('call', c, fn=c.fn, args=c.args)
        if len(c.args) != len(cmd.fields):
            raise err(c, f'{f}() takes {len(cmd.fields)} argument(s): ' + ', '.join(bytecode.TYPENAME.get(x, x) for x in cmd.fields))
        vals = []
        for k, (fld, (_, a)) in enumerate(zip(cmd.fields, c.args)):
            if f in ('call_routine', 'call_digimon_routine') and a.kind == 'call' and a.fn.kind == 'id' and a.fn.name == 'routine':
                vals.append(str(self.routine_id(a, f))); continue
            vals.append(self.field_value(fld, a, env, f, k))
        mn = cmd.mnemonic
        if cmd.op in bytecode.WIDE and vals and int(vals[0]) > 255: mn = self.wide(mn, vals[0], c)
        env.out.append(f'    {mn}{" " + ", ".join(vals) if vals else ""}')
        return True

    def routine_id(self, a, f):
        if len(a.args) != 1 or a.args[0][1].kind != 'str': raise err(a, 'routine("name") takes a name in quotes')
        nm = a.args[0][1].v
        table = self.routines if f == 'call_routine' else R.DIGIMON_ROUTINE_BY_NAME
        if nm not in table:
            raise err(a, f'no routine "{nm}"', 'known: ' + ', '.join(sorted(table)[:15]) + ', ...')
        return table[nm]

    def check_unpacked(self, node, key, rows, env):
        """A text the engine shows in box 1-3 (BE.UNPACKED_KEYS: the keeper's titles, the card shop's question, the cup
        texts...) keeps two bytes a unit with every font: a row past 31 units or 240 px is an error at the line."""
        if not key or BE.packed_key(key) or env.port: return
        for r in rows:
            if '{raw ' not in r and not BE.fits(BE.plain(r), packed=False):
                self.errors.append(err(node, f'text("{key}") row "{r}" is {BE.row_size(BE.plain(r), False)}: the game shows '
                                             f'this text in a box other than the dialogue box (box 1-3), whose rows are not '
                                             f'packed: {BE.MAX_UNITS} units and {BE.MAX_PX} px a row with every font',
                                       'shorten the row or break it into more rows (docs/mods/font.md "Packed rows")'))

    def row_text(self, v, node, env):
        if v.type == 'str': rows = [v.val]
        elif v.type == 'text' and v.val[0] == 'wrap': rows = [v.val[1]]
        elif v.type == 'text' and len(v.val[1]) == 1: rows = list(v.val[1][0])
        else: raise err(node, 'a row of text is a string or text("key") of one row')
        return [BE.quote(r) if env.port else BE.quote(BE.plain(r)) for r in rows]

    def special_stmt(self, c, env, f):
        out = env.out; args = [a for _, a in c.args]
        if f == 'end_selection':
            out.append('    END_SELECTION'); return
        if f == 'show_textbox':
            if not args: raise err(c, 'show_textbox(text("a"), ...) needs at least one row')
            vals = [self.eval(a, env) for a in args]
            if len(vals) == 1 and vals[0].type == 'text' and (vals[0].val[0] == 'wrap' or len(vals[0].val[1]) > 1):
                # one utterance (text("s002.sec6.u0")): a SHOW_TEXTBOX per page, in a row (one chained box); a string is wrapped
                k, val = vals[0].val
                pages = BE.wrap(val, 3, BE.packed_key(vals[0].key)) if k == 'wrap' else val
                over = vals[0].key and self.bank.single_page_overflow(vals[0].key, len(pages))
                if over: self.errors.append(err(args[0], over, 'shorten it to one box: 3 rows of 31 units and 240 px'))
                self.check_unpacked(args[0], vals[0].key, [r for p in pages for r in p], env)
                for page in pages:
                    out.append('    SHOW_TEXTBOX')
                    for r in page: out.append('        ' + (BE.quote(r) if env.port else BE.quote(BE.plain(r))))
                return
            out.append('    SHOW_TEXTBOX')
            for a, v in zip(args, vals):
                if v.type == 'text' and v.val[0] == 'pages' and len(v.val[1]) == 1:
                    self.check_unpacked(a, getattr(v, 'key', None), v.val[1][0], env)
                for r in self.row_text(v, a, env): out.append('        ' + r)
            return
        if f == 'set_selection':
            labels = []; rows = []
            for a in args:
                if is_original(a) and not rows: labels.append(self.label_of(a, env)); continue
                if a.kind == 'id' and not rows and self.lookup(a.name, env) is None:
                    labels.append(self.label_of(a, env)); continue
                v = self.eval(a, env); rows += self.row_text(v, a, env)
                t = v.val if v.type == 'str' else v.val[1] if v.type == 'text' and v.val[0] == 'wrap' else \
                    v.val[1][0][0] if v.type == 'text' and len(v.val[1]) == 1 and len(v.val[1][0]) == 1 else None
                if isinstance(t, str) and '{raw ' not in t and not env.port and not BE.fits(BE.plain(t)):
                    self.errors.append(self.option_too_wide(a, v, BE.plain(t)))
            if not labels or len(labels) != len(rows):
                raise err(c, 'set_selection(L1, L2, ..., text("a"), text("b"), ...): as many labels as rows')
            out.append('    SET_SELECTION ' + ', '.join(labels))
            for r in rows: out.append('        ' + r)
            return
        if f in ('switch', 'switch_w'):
            if len(args) < 2: raise err(c, f'{f}(register, L1, L2, ...)')
            reg = self.field_value('p' if f == 'switch' else 'w', args[0], env, f, 0)
            labs = [self.label_of(a, env) for a in args[1:]]
            out.append(f'    {f.upper()} {reg}, ' + ', '.join(labs)); return
        if f == 'data':
            vals = [self.int_of(a, env, 'u8', 'data') for a in args]
            if any(v == 255 for v in vals): raise err(c, 'data: 255 is the terminator')
            out.append('    DATA ' + ', '.join(map(str, vals))); return

    # ------------------------------------------------------------ labels and jumps
    def st_label(self, n, env):
        if getattr(n, 'shared', False):
            if env.port: raise err(n, '`shared NAME:` is for events (a port block has raw labels already)')
            env.out.append(f'{self.shared_label(n.name)}:'); env.state['speaker'] = None; return
        if not env.port and self.SEC_LABEL.match(n.name):
            raise err(n, f'"{n.name}" is the name of a section entry (secN): pick another label name')
        if not env.port and n.name in getattr(self, 'shared_names', {}).get(env.sid, {}):
            raise err(n, f'"{n.name}" is a shared name of this script: pick another label name')
        if n.name in env.lab['def']:
            raise err(n, f'label "{n.name}" is defined twice', f'first at line {env.lab["def"][n.name].pos[1]}')
        env.lab['def'][n.name] = n
        env.out.append(f'{self.ulabel(env, n.name)}:'); env.state['speaker'] = None

    def jump_label(self, n, env):
        """The assembler label for a jump: `original(L)` is L itself (a label of the original script), else the event's own."""
        if getattr(n, 'ext', False): self.deprecated_original(n, env); return n.label
        return self.resolve_label(env, n.label, n)

    def st_goto(self, n, env):
        env.out.append(f'    JUMP_TO {self.jump_label(n, env)}')

    def st_gosub(self, n, env):
        env.out.append(f'    JUMP_AND_LINK {self.jump_label(n, env)}')

    def st_unless(self, n, env):
        j = getattr(n, 'jump', 'goto')
        if j in ('break', 'continue'):                  # unless (c) break;  ==  IF c, else <loop exit>
            if not env.loops: raise err(n, f'`{j}` outside a loop')
            conds = self.cond(n.cond, env)
            env.out += env.pre; env.pre.clear()
            env.out.append(f'    IF {", ".join(conds)}, else {env.loops[-1][1 if j == "break" else 0]}'); return
        if j == 'return' and env.in_sub is None and not env.fn_end and env.state.get('ret_ok'):
            # unless (c) return;  ==  IF c, else <the END_SECTION at the end of the event> (one IF, the disc's form)
            env.state.setdefault('ret', self.label('ret'))
            conds = self.cond(n.cond, env)
            env.out += env.pre; env.pre.clear()
            env.out.append(f'    IF {", ".join(conds)}, else {env.state["ret"]}'); return
        if j == 'return':                               # unless (c) return;  ==  if (c) { } else { return; }
            from .parser import Node
            return self.st_if(Node('if', n, cond=n.cond, then=Node('block', n, stmts=[]), els=Node('return', n, expr=None)), env)
        conds = self.cond(n.cond, env)
        env.out += env.pre; env.pre.clear()
        env.out.append(f'    IF {", ".join(conds)}, else {self.jump_label(n, env)}')

    def check_labels(self, env, where):
        for name, node in env.lab['used']:
            if name not in env.lab['def']:
                raise err(node, f'label "{name}" is not defined in {where}',
                          'labels are local to one event (or one port block)' + self.near(name, env.lab['def']))

    # ------------------------------------------------------------ loops
    def hidden_var(self, env, base):
        """A scratch variable for a loop, allocated once per (module, name) from the temp pool."""
        from .gen import Sym
        depth = env.state.setdefault('rdepth', 0)
        owner = env.sub_name or 'ev'
        q = self.qname(f'__{base}{depth}_{owner}')
        if q not in self.hidden:
            class Tok: pos = None
            node = Node('decl', ('', 0, 0), what='var', name=q, pin=None, alias=False, scope='scratch', pub=False, count=None,
                        vtype=None, ntok=None)
            n = self.alloc.declare('var', 'scratch', q, None, False, node)
            self.hidden[q] = Sym('var', q, node, num=n, scope='scratch', alias=False, pub=False, root=False, count=None, vtype='u8')
        return self.hidden[q]

    def loop_body(self, n, env, cont, end, setup=None):
        env.loops.append((cont, end)); env.state['rdepth'] = env.state.get('rdepth', 0) + 1
        env.state['speaker'] = None
        self.stmt(n.body, env)
        env.state['rdepth'] -= 1; env.loops.pop()

    def st_loop(self, n, env):
        top, end = self.label('loop'), self.label('endloop')
        env.out.append(f'{top}:'); env.state['speaker'] = None
        self.loop_body(n, env, top, end)
        env.out += [f'    JUMP_TO {top}', f'{end}:']; env.state['speaker'] = None

    def const_int(self, node, env, what, lo=0, hi=255):
        v = self.eval(node, env)
        if v.type != 'int': raise err(node, f'{what} must be a constant number in original, got {v.type}')
        if not lo <= v.val <= hi: raise err(node, f'{what} {v.val} does not fit ({lo}..{hi})')
        return v.val

    def st_repeat(self, n, env):
        cnt = self.const_int(n.count, env, 'the repeat count')
        sym = self.hidden_var(env, 'rep'); top, cont, end = self.label('rep'), self.label('repnext'), self.label('endrep')
        env.out += [f'    SET_PSTAT p{sym.num}, {cnt}', f'{top}:', f'    IF p{sym.num} >= 1, else {end}']
        self.loop_body(n, env, cont, end)
        env.out += [f'{cont}:', f'    REDUCE_PSTAT p{sym.num}, 1', f'    JUMP_TO {top}', f'{end}:']; env.state['speaker'] = None

    def st_for(self, n, env):
        from .gen import V
        lo = self.const_int(n.lo, env, 'the start of the range'); hi = self.const_int(n.hi, env, 'the end of the range')
        sym = self.hidden_var(env, 'for'); top, cont, end = self.label('for'), self.label('fornext'), self.label('endfor')
        saved = env.locals.get(n.var); env.locals[n.var] = V('var', sym)
        env.out += [f'    SET_PSTAT p{sym.num}, {lo}', f'{top}:', f'    IF p{sym.num} < {hi}, else {end}']
        self.loop_body(n, env, cont, end)
        env.out += [f'{cont}:', f'    ADD_TO_PSTAT p{sym.num}, 1', f'    JUMP_TO {top}', f'{end}:']; env.state['speaker'] = None
        if saved is None: env.locals.pop(n.var, None)
        else: env.locals[n.var] = saved

    def st_par(self, n, env):
        handles = []
        for s in n.body.stmts:
            r = self.stmt(s, env)
            if s.kind == 'expr' and r is not None and s.expr.fn.kind == 'id' and s.expr.fn.name in ('walk', 'run'):
                if r not in handles: handles.append(r)
            elif s.kind != 'expr' or (s.expr.fn.kind == 'id' and s.expr.fn.name in ('walk', 'run')) is False:
                pass
        for h in handles: env.out.append(f'    WAIT_FOR_ENTITY {h}')

    # ------------------------------------------------------------ match
    def st_match(self, n, env):
        v = self.eval(n.subject, env)
        if v.type != 'var': raise err(n.subject, 'match works on a variable (or p7): copy the value to a var first')
        if self.is_story_var(v.val):
            raise err(n.subject, f'match works on a pstat variable; "{v.val.name}" is a story variable',
                      'compare it with if/else, or copy it to a raw pstat first (p110 = story_var;)')
        v.val.reads += 1; p = f'p{v.val.num}'; out = env.out; end = self.label('mend')
        arms = []; default = None
        for pat, body in n.arms:
            if pat is None:
                if default is not None: raise err(body, 'two default arms (_)')
                default = body; continue
            pv = self.eval(pat, env)
            if pv.type != 'int': raise err(pat, 'match patterns are constant numbers or enum values')
            if any(a[0] == pv.val for a in arms): raise err(pat, f'the value {pv.val} appears twice')
            arms.append((pv.val, body))
        clamp = getattr(n, 'clamp', False)
        dense = (len(arms) >= 2 if clamp else len(arms) >= 3) and sorted(a[0] for a in arms) == list(range(len(arms)))
        if clamp and (not dense or default is not None):
            raise err(n, 'match (v, clamp): the arms are exactly 0..n-1 (n >= 2) and there is no `_` arm; the last arm takes every larger value')
        env.state['speaker'] = None
        if clamp:                                  # the original's SWITCH as it is: no bound check, values past the end take the last arm
            by = dict(arms); labs = [self.label('case') for _ in arms]
            out.append(f'    SWITCH {p}, ' + ', '.join(labs))
            for i, lab in enumerate(labs):
                out.append(f'{lab}:'); env.state['speaker'] = None; self.stmt(by[i], env); out.append(f'    JUMP_TO {end}')
        elif dense:
            by = dict(arms); labs = [self.label('case') for _ in arms]; ldef = self.label('mdef')
            out.append(f'    IF {p} < {len(arms)}, else {ldef}')
            out.append(f'    SWITCH {p}, ' + ', '.join(labs))
            for i, lab in enumerate(labs):
                out.append(f'{lab}:'); env.state['speaker'] = None; self.stmt(by[i], env); out.append(f'    JUMP_TO {end}')
            out.append(f'{ldef}:'); env.state['speaker'] = None
            if default is not None: self.stmt(default, env)
        else:
            for val, body in arms:
                nxt = self.label('mnext')
                out.append(f'    IF {p} == {val}, else {nxt}'); env.state['speaker'] = None
                self.stmt(body, env); out.append(f'    JUMP_TO {end}'); out.append(f'{nxt}:')
            env.state['speaker'] = None
            if default is not None: self.stmt(default, env)
        out.append(f'{end}:'); env.state['speaker'] = None

    # ------------------------------------------------------------ subroutines
    def sub_vars(self, sym):
        """Parameter and result variables of a `sub`: u8 temps allocated once, named f.param."""
        from .gen import Sym
        cache = getattr(sym, 'svars', None)
        if cache is not None: return cache
        fn = sym.node; cache = {}
        for (pn, pt, pd, ptok) in fn.params:
            if pt not in ('u8', 'int', 'bool'):
                raise err(ptok, f'sub {fn.name}: parameter "{pn}" is {pt}; a sub receives numbers (u8) in variables',
                          'use `fn` (inlined at each call) for entities, items, species and text')
            cache[pn] = self.sub_alloc(sym, pn, fn)
        if fn.ret:
            if fn.ret not in ('u8', 'int', 'bool'): raise err(fn, f'sub {fn.name}: the result is {fn.ret}; only u8/bool')
            cache['->'] = self.sub_alloc(sym, 'result', fn)
        sym.svars = cache
        return cache

    def sub_alloc(self, sym, name, fn):
        from .gen import Sym
        q = self.qname(f'{sym.name}.{name}')
        node = Node('decl', fn, what='var', name=q, pin=None, alias=False, scope='scratch', pub=False, count=None, vtype=None, ntok=None)
        n = self.alloc.declare('var', 'scratch', q, None, False, node)
        return Sym('var', q, node, num=n, scope='scratch', alias=False, pub=False, root=False, count=None, vtype='u8')

    def call_sub(self, sym, c, env, want=False):
        from .gen import V, Env
        fn = sym.node; sv = self.sub_vars(sym)
        if env.sid is None: raise err(c, 'sub calls need a DG.SCN script (not MAPHEAD)', 'use `fn` there')
        names = [p[0] for p in fn.params]; given = {}
        for i, (nm, a) in enumerate(c.args):
            pn = nm if nm else (names[i] if i < len(names) else None)
            if pn not in names: raise err(a, f'{fn.name}() has no argument "{nm or i}"')
            given[pn] = a
        for pn, pt, pd, ptok in fn.params:
            if pn in given:
                v = self.eval(given[pn], env)
                if v.type == 'bool': v = V('int', 1 if v.val else 0)
                if v.type == 'int':
                    if not 0 <= v.val <= 255: raise err(given[pn], f'{v.val} does not fit a u8 parameter')
                    env.out.append(f'    SET_PSTAT p{sv[pn].num}, {v.val}')
                elif v.type == 'var' and self.is_story_var(v.val):
                    v.val.reads += 1; env.out.append(f'    PSTAT_FROM_V p{sv[pn].num}, {self.vref(v.val)}')   # clamped to 0..255
                elif v.type == 'var':
                    v.val.reads += 1; env.out.append(f'    COPY_PSTAT p{v.val.num}, p{sv[pn].num}')
                else: raise err(given[pn], f'{fn.name}(): "{pn}" takes a number or a variable, got {v.type}')
            elif pd is not None:
                env.out.append(f'    SET_PSTAT p{sv[pn].num}, {self.eval(pd, Env({})).val}')
            else: raise err(c, f'{fn.name}(): missing argument "{pn}"')
        lab = self.emit_sub(sym, env, c)
        env.out.append(f'    JUMP_AND_LINK {lab}'); env.state['speaker'] = None
        if want:
            if '->' not in sv: raise err(c, f'sub {fn.name} gives no value')
            return V('var', sv['->'])

    def emit_sub(self, sym, env, c):
        from .gen import Env, V
        key = (env.sid, sym.name)
        if key in self.subs_emitted: return self.subs_emitted[key]
        lab = f'qsub_{re.sub(r"[^A-Za-z0-9]", "_", sym.name)}_{env.sid}'
        self.subs_emitted[key] = lab
        if sym in env.fn_stack: raise err(c, f'sub "{sym.name}" calls itself', 'recursion is not supported (the call stack has 8 entries)')
        sub = Env(env.npcs, self_ent=None, parent=None)
        sub.out = []; sub.sid = env.sid; sub.section = env.section; sub.sub_name = re.sub(r'\W', '_', sym.name)
        sub.in_sub = sym; sub.fn_stack = env.fn_stack + [sym]; sub.ev = env.ev; sub.lab = {'def': {}, 'used': []}
        sv = self.sub_vars(sym)
        for pn in [p[0] for p in sym.node.params]: sub.locals[pn] = V('var', sv[pn])
        sub.sub_ret = sv.get('->')
        self.block(sym.node.body, sub)
        self.check_labels(sub, f'sub {sym.name}')
        code = [f'{lab}:'] + sub.out + ['    JUMP_RETURN', '']
        self.b.scripts[env.sid].setdefault('subs', []).extend(code)
        return lab

    def st_return(self, n, env):
        if env.in_sub is not None:
            if n.expr is not None:
                if env.sub_ret is None: raise err(n, 'this sub has no result type: sub f() -> u8')
                v = self.eval(n.expr, env)
                if v.type == 'bool': v = V_int(1 if v.val else 0)
                if v.type == 'int': env.out.append(f'    SET_PSTAT p{env.sub_ret.num}, {v.val}')
                elif v.type == 'var' and self.is_story_var(v.val): env.out.append(f'    PSTAT_FROM_V p{env.sub_ret.num}, {self.vref(v.val)}')
                elif v.type == 'var': env.out.append(f'    COPY_PSTAT p{v.val.num}, p{env.sub_ret.num}')
                else: raise err(n.expr, f'return: a number or a variable, got {v.type}')
            env.out.append('    JUMP_RETURN'); return
        if n.expr is not None: raise err(n, '`return value;` is for sub functions', 'a talk/event section just ends: `return;`')
        if env.fn_end: env.out.append(f'    JUMP_TO {env.fn_end}'); env.fn_used = True
        else: env.out.append('    END_SECTION')

    # ------------------------------------------------------------ whole scripts (decompiler output)
    def generate_ports(self):
        from .gen import Env
        for sid, it in list(self.ports.items()) + ([('maphead', self.maphead_port)] if self.maphead_port else []):
            try:
                text = self.port_text(sid, it.port if sid != 'maphead' else it.body)
                self.port_texts[sid] = (text, it.pos[0])
            except DwsError as e:
                self.errors.append(e)

    def port_text(self, sid, body):
        from .gen import Env
        env = Env({}); env.port = True; env.sid = None; env.section = None; env.ev = 'port'
        head = []; tail = False; entries = []
        for st in body:
            if st.kind == 'tail':
                if tail: raise err(st, 'tail; twice')
                tail = True
            elif st.kind == 'entry': entries.append(st)
        if not entries: raise err(body[0] if body else None, 'a port block needs entry lines: entry 254 sec254;')
        if tail and sid != 'maphead': head.append(f'.tail script_{sid:03d}.tail.bin')
        for e in entries: head.append(f'.section {e.sid} {e.label}')
        head.append('')
        for st in body:
            if st.kind in ('tail', 'entry'): continue
            self.stmt(st, env)
        self.check_labels(env, 'this block')
        defined = set(env.lab['def'])
        for e in entries:
            if e.label not in defined: raise err(e, f'entry label "{e.label}" is not defined')
        if env.pre: raise err(None, 'internal: unflushed condition setup')
        return head + self.layout_port(env.out)

    @staticmethod
    def layout_port(lines):
        """Labels at column 0 with a blank line before, like the disassembler."""
        out = []
        for l in lines:
            if re.match(r'^[A-Za-z_]\w*:\s*$', l):
                if out and out[-1] != '': out.append('')
            out.append(l)
        return out


def V_int(v):
    from .gen import V
    return V('int', v)
