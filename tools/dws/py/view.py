"""The Python view of the base story (milestone 3b of docs/mods/story-language.md): each generated `script.dws` of
story/base printed as `script.py` in the story language, and MAPHEAD as `maphead/hooks.py`.

The view is a projection of the proven DWS: every form it prints lowers back (tools/dws/py/lower.py) to the very DWS it came
from, so the base is built from it (`story-build`, the default since 2026-10-13; `--from-dws` reads the DWS) and proven again
(`story-base --check`). A statement with no
Python form is printed as `dws(\"\"\"...\"\"\")` with its DWS text (a hatch); a section that keeps labels and jumps (the jump
tables, the few partial sections) is one hatch (`literal`). One command with no sugar is `raw.<command>(...)`.

    verdicts per section (the `py` column of beautifier-coverage.csv): clean, raw, hatch, literal
"""
import os, re
from ..parser import parse, Node
from .. import backend as BE
from . import naming as N

ROOT = BE.ROOT
SEC_LABEL = re.compile(r'^sec(\d+)$')


class Hatch(Exception):
    """This statement has no Python form: print its DWS."""


def py_str(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


class Ctx:
    """What one file needs while it is printed."""
    def __init__(self, sid, src_lines, names, npcs, species_of, entry_of):
        self.sid = sid; self.src = src_lines; self.names = names; self.npcs = npcs      # DWS npc name -> entity
        self.species_of = species_of                    # npc name -> species id (or None)
        self.entry_of = entry_of                        # section label 'secN' -> python call text of its handler
        self.text_alias = {}                            # 'sNNN.secX' -> alias
        self.uses_names = False; self.shared = set()
        self.verdict = 'clean'; self.self_npc = None; self.handler = None
        self.fold = {}                                  # state name -> Python while one condition is printed (random.roll, clock.*)
        self.pick = False                               # printing the tests of what pick_item() gave
        self.rolled = False                             # this handler has drawn (`roll = random.roll(n)`)

    def mark(self, v):
        order = ('clean', 'raw', 'hatch', 'literal')
        if order.index(v) > order.index(self.verdict): self.verdict = v

    # ---------------------------------------------------------------- values
    def key(self, k):
        """s018.sec68.u1 -> t68.u1 (an alias per section: `t68 = text.s018.sec68`); s002.sec6.m1.o0 -> t6.m1.o0; m1230.u0 -> m1230.u0."""
        parts = k.split('.')
        if len(parts) < 2 or not all(p.isidentifier() for p in parts): raise Hatch(f'text key {k}')
        n = 2 if parts[0].startswith('s') or parts[0] == 'm' else 1
        if len(parts) <= n: raise Hatch(f'text key {k}')
        base, leaf = '.'.join(parts[:n]), '.'.join(parts[n:])
        if base not in self.text_alias:
            m = re.fullmatch(r's\d{3}\.sec(\w+)', base)
            alias = f't{m.group(1)}' if m else base.replace('.', '_')
            if alias in self.text_alias.values(): alias = base.replace('.', '_')
            self.text_alias[base] = alias
        return f'{self.text_alias[base]}.{leaf}'

    def typed(self, kind, a):
        """species("X") / item(38) -> Species.X / Item.Meat"""
        if a.kind == 'num': v = a.v
        elif a.kind == 'str':
            v = BE.names()[kind].get(a.v.strip().lower())
            if v is None: raise Hatch(f'{kind} {a.v}')
        else: raise Hatch(kind)
        mem = N.enum_members(kind).get(v)
        enum = {'species': 'Species', 'item': 'Item', 'tech': 'Tech'}[kind]
        return f'{enum}.{mem}' if mem else f'{enum}({v})'

    def text_arg(self, a):
        """A text argument of say: text(k) -> t6.u0 (an utterance); page(text(a), text(b)) -> page(t6.l1, t6.l2); "str" -> "str"."""
        if a.kind == 'call' and a.fn.kind == 'id' and a.fn.name == 'text' and len(a.args) == 1 and a.args[0][1].kind == 'str':
            return self.key(a.args[0][1].v)
        if a.kind == 'call' and a.fn.kind == 'id' and a.fn.name == 'page' and a.args:
            rows = []
            for nm, r in a.args:
                if nm or not (r.kind == 'call' and r.fn.kind == 'id' and r.fn.name == 'text' and len(r.args) == 1 and r.args[0][1].kind == 'str'):
                    raise Hatch('page row')
                rows.append(self.key(r.args[0][1].v))
            return rows[0] if len(rows) == 1 else f'page({", ".join(rows)})'
        if a.kind == 'str': return py_str(a.v)
        raise Hatch('text argument')

    def option(self, a):
        """A menu option: text(k) -> t6.m0.o1, "str" -> "str" (the lowering writes `text(k)` back)."""
        if a.kind == 'call' and a.fn.kind == 'id' and a.fn.name == 'text' and len(a.args) == 1 and a.args[0][1].kind == 'str':
            return self.key(a.args[0][1].v)
        if a.kind == 'str': return py_str(a.v)
        raise Hatch('option')

    def entity(self, a):
        if a.kind == 'id':
            n = a.name
            if n in ('tamer', 'player'): return 'tamer'
            if n in ('partner', 'narrator'): return n
            if n == 'camera': return 'entity(200)'
            if n == 'self': return self.self_npc or (_ for _ in ()).throw(Hatch('self'))
            if n in self.npcs: return n
        if a.kind == 'num': return f'entity({a.v})'
        if a.kind == 'call' and a.fn.kind == 'id' and a.fn.name == 'entity' and len(a.args) == 1 and a.args[0][1].kind == 'num':
            return f'entity({a.args[0][1].v})'
        raise Hatch('entity')

    def who(self, a):
        """The prefix for a verb of `a`: '' when it is the NPC being talked to."""
        e = self.entity(a)
        return '' if self.self_npc and e == self.self_npc else e + '.'

    def name(self, n):
        """A DWS state name -> Python (`random_roll`, `engine.arg`, `p110` -> `pstat(110)`, `tournament.day`); the random draw
        is `roll` once this handler has drawn it (`roll = random.roll(n)`)."""
        if n in self.fold: return self.fold[n]
        if n in ('random_roll', 'p110') and self.rolled: return 'roll'
        m = re.fullmatch(r'p(\d+)', n)
        if m: return f'pstat({m.group(1)})'
        if re.fullmatch(r'w\d+', n): raise Hatch('wide register')
        if n in self.state_names: self.uses_names = self.uses_names or not n.startswith(('engine.', 'glances')); return n
        raise Hatch(f'name {n}')

    def value(self, a):
        """An argument value: a number, a typed id, an entity, an anim slot, a state name."""
        if a.kind == 'num': return str(a.v)
        if a.kind == 'bool': return 'True' if a.v else 'False'
        if a.kind == 'dur': return str(a.v)
        if a.kind == 'unary' and a.op == '-' and a.e.kind == 'num': return f'-{a.e.v}'
        if a.kind == 'call' and a.fn.kind == 'id' and a.fn.name in ('species', 'item', 'tech') and len(a.args) == 1:
            return self.typed(a.fn.name, a.args[0][1])
        if a.kind == 'call' and a.fn.kind == 'id' and a.fn.name == 'text' and len(a.args) == 1 and a.args[0][1].kind == 'str':
            return self.key(a.args[0][1].v)
        if a.kind == 'call' and a.fn.kind == 'id' and a.fn.name == 'routine' and len(a.args) == 1 and a.args[0][1].kind == 'str':
            return f'Routine.{a.args[0][1].v}'
        if a.kind == 'member' and a.obj.kind == 'id' and a.obj.name == 'anim': return f'anim.{a.name}'
        if a.kind == 'id':
            if a.name in ('tamer', 'player', 'partner', 'narrator', 'camera', 'self') or a.name in self.npcs: return self.entity(a)
            return self.name(a.name)
        if a.kind == 'member' and a.obj.kind == 'id': return self.name(f'{a.obj.name}.{a.name}')
        if a.kind == 'call' and a.fn.kind == 'id' and a.fn.name == 'entity': return self.entity(a)
        if a.kind == 'call' and a.fn.kind == 'id' and a.fn.name == 'trigger' and len(a.args) == 1 and a.args[0][1].kind == 'num':
            return f'trigger({a.args[0][1].v})'
        if a.kind == 'call' and a.fn.kind == 'id' and a.fn.name == 'screen' and len(a.args) == 1 and a.args[0][1].kind == 'num':
            return self.screen_member(a.args[0][1].v)
        raise Hatch('value')

    def screen_member(self, n):
        m = N.screen_members().get(n)
        return f'Screen.{m}' if m else str(n)

    # ---------------------------------------------------------------- conditions
    def cond(self, c, top=True):
        k = c.kind
        if self.pick:                                   # what pick_item() gave: Picked.EMPTY, Picked.CANCELLED, an item
            if is_engine(c, 'picker_mode'): return 'pick is Picked.EMPTY'
            if k == 'unary' and c.op == '!' and is_engine(c.e, 'picker_mode'): return 'pick is not Picked.EMPTY'
            if k == 'binary' and c.op in ('==', '!=') and is_engine(c.l, 'arg') and c.r.kind == 'num' and c.r.v == 255:
                return f'pick is {"" if c.op == "==" else "not "}Picked.CANCELLED'
            if k == 'binary' and c.op in ('==', '!=', 'in') and is_engine(c.l, 'arg'):
                r = f'({", ".join(self.operand(x) for x in c.r.items)}{"," if len(c.r.items) == 1 else ""})' if c.op == 'in' else self.operand(c.r)
                return f'pick {c.op} {r}'
            
        if k == 'binary' and c.op in ('&&', '||'):
            op = 'and' if c.op == '&&' else 'or'
            l = self.cond(c.l, False); r = self.cond(c.r, False)
            if c.l.kind == 'binary' and c.l.op in ('&&', '||') and c.l.op != c.op: l = f'({l})'
            if c.r.kind == 'binary' and c.r.op in ('&&', '||'): r = f'({r})'
            return f'{l} {op} {r}'
        if k == 'binary' and c.op == '~>': raise Hatch('~> fold')
        if k == 'unary' and c.op == '!':
            inner = self.cond(c.e, False)
            if c.e.kind == 'binary': inner = f'({inner})'
            return f'not {inner}'
        if k == 'binary' and c.op == 'in':
            if c.r.kind != 'list': raise Hatch('in')
            r = self.species_operand if self.is_species(c.l) else self.operand
            return f'{self.operand(c.l)} in ({", ".join(r(x) for x in c.r.items)}{"," if len(c.r.items) == 1 else ""})'
        if k == 'binary' and c.op in ('==', '!=', '<', '<=', '>', '>='):
            l = c.l
            if l.kind == 'call' and l.fn.kind == 'id' and l.fn.name == 'has':
                if len(l.args) == 1 and c.op == '<' and c.r.kind == 'num' and c.r.v == 1: return f'not has({self.has_arg(l.args[0][1])})'
                if len(l.args) != 1 or c.op != '>=' or c.r.kind != 'num': raise Hatch('has comparison')
                return f'has({self.has_arg(l.args[0][1])}{"" if c.r.v == 1 else f", {c.r.v}"})'
            if l.kind == 'member' and l.obj.kind == 'id' and l.obj.name == 'partner' and l.name == 'is': raise Hatch('partner.is')
            if self.is_species(l) and c.op in ('==', '!='): return f'partner.species {c.op} {self.species_operand(c.r)}'
            return f'{self.operand(l)} {c.op} {self.operand(c.r)}'
        if k == 'call' and c.fn.kind == 'id':
            f = c.fn.name; a = [x for _, x in c.args]
            if f == 'trigger' and len(a) == 1 and a[0].kind == 'num': return f'trigger({a[0].v})'
            if f == 'is_recruited' and len(a) == 1: return f'recruited({self.value(a[0])})'
            if f == 'has' and len(a) == 1: return f'has({self.has_arg(a[0])})'
            if f == 'knows' and len(a) == 1: return f'knows({self.value(a[0])})'
            if f == 'condition' and len(a) == 1 and a[0].kind == 'num' and a[0].v in CONDITION_NAMES:
                return f'partner.{CONDITION_NAMES[a[0].v]}'
            if f == 'chance' and len(a) == 1 and a[0].kind == 'num': return f'random.chance({a[0].v})'
            raise Hatch(f'condition {f}')
        if k == 'call' and c.fn.kind == 'member' and c.fn.obj.kind == 'id' and c.fn.obj.name == 'partner' and c.fn.name == 'is':
            return f'partner.species == {self.value(c.args[0][1])}'
        if k == 'id':
            if c.name in ('won', 'lost', 'fled'): return c.name
            if c.name in ('true', 'false'): raise Hatch('bool')
            return self.name(c.name)
        if k == 'member' and c.obj.kind == 'id': return self.name(f'{c.obj.name}.{c.name}')
        if k == 'bool': return 'True' if c.v else 'False'
        raise Hatch('condition')

    FLIP = {'==': '!=', '!=': '==', '<': '>=', '>=': '<', '>': '<=', '<=': '>'}

    def neg_cond(self, c):
        """Python for `not c`, written out (De Morgan over a chain of one operator, comparisons flipped); Hatch when the lowering
        could not negate it back to the same clauses (a mixed chain, `in`)."""
        k = c.kind
        if k == 'unary' and c.op == '!':
            if c.e.kind == 'binary' and c.e.op in ('&&', '||'): raise Hatch('negated group')
            return self.cond(c.e, False)
        if k == 'binary' and c.op in ('&&', '||'):
            parts = []
            def flat(x):
                if x.kind == 'binary' and x.op == c.op: flat(x.l); flat(x.r)
                elif x.kind == 'binary' and x.op in ('&&', '||', '~>'): raise Hatch('mixed chain')
                else: parts.append(self.neg_cond(x))
            flat(c)
            return f' {"or" if c.op == "&&" else "and"} '.join(parts)
        if k == 'binary' and c.op == '~>': raise Hatch('~> fold')
        if k == 'binary' and c.op in self.FLIP:
            return self.cond(Node('binary', c, op=self.FLIP[c.op], l=c.l, r=c.r), False)
        if k == 'binary': raise Hatch('negation')
        return f'not {self.cond(c, False)}'

    def is_species(self, a):
        return a.kind == 'id' and self.fold.get(a.name) == 'partner.species'

    def species_operand(self, a):
        if a.kind == 'num': return self.typed('species', a)
        if a.kind == 'call' and a.fn.kind == 'id' and a.fn.name == 'species' and len(a.args) == 1: return self.typed('species', a.args[0][1])
        raise Hatch('species')

    def has_arg(self, a):
        if a.kind == 'call' and a.fn.kind == 'id' and a.fn.name == 'item' and len(a.args) == 1: return self.typed('item', a.args[0][1])
        raise Hatch('has')

    def operand(self, a):
        if a.kind == 'call' and a.fn.kind == 'id' and a.fn.name == 'stat' and len(a.args) == 1 and a.args[0][1].kind == 'num' \
                and a.args[0][1].v in STAT_NAMES:
            return f'partner.{STAT_NAMES[a.args[0][1].v]}'
        if a.kind == 'call' and a.fn.kind == 'id' and a.fn.name == 'stat' and len(a.args) == 1 and a.args[0][1].kind == 'num' \
                and a.args[0][1].v == TAMER_LEVEL:
            return 'tamer.level'
        if a.kind == 'call' and a.fn.kind == 'id' and a.fn.name in ('stat', 'has_card') and len(a.args) == 1 and a.args[0][1].kind == 'num':
            return f'{a.fn.name}({a.args[0][1].v})'
        if a.kind == 'id' and a.name == 'bits': return 'bits'
        if a.kind == 'member' and a.obj.kind == 'id' and a.obj.name in ('clock', 'partner'): return f'{a.obj.name}.{a.name}'
        return self.value(a)


# --------------------------------------------------------------------- statements
class Printer:
    def __init__(self, ctx):
        self.c = ctx

    def hatch_text(self, node):
        """The DWS text of one statement, from the file it was parsed from (its lines, re-indented to column 0)."""
        src = self.c.src; i = node.pos[1] - 1
        depth = 0; out = []
        j = i
        while j < len(src):
            line = src[j]; out.append(line)
            depth += strip_strings(line).count('{') - strip_strings(line).count('}')
            nxt = src[j + 1].strip() if j + 1 < len(src) else ''
            if depth <= 0 and (line.rstrip().endswith((';', '}')) or line.rstrip().endswith(':')) and not nxt.startswith('else'):
                break
            j += 1
        ind = min(len(l) - len(l.lstrip()) for l in out if l.strip())
        return [recruit_flags(l[ind:]) for l in out]

    def hatch(self, nodes, ind):
        lines = []
        for n in nodes: lines += self.hatch_text(n)
        self.c.mark('hatch')
        if len(lines) == 1 and '"""' not in lines[0]: return [f'{ind}dws(r"""{lines[0]}""")']
        return [f'{ind}dws(r"""'] + [f'{ind}    {l}' if l else '' for l in lines] + [f'{ind}""")']

    def block(self, stmts, ind):
        out = []; k = 0
        while k < len(stmts):
            s = stmts[k]
            try:
                lines, used = self.stmt(stmts, k, ind)
            except Hatch:
                lines, used = self.hatch([s], ind), 1
            out += lines; k += used
        return out

    def body(self, node, ind):
        st = node.stmts if node.kind == 'block' else [node]
        lines = self.block(st, ind)
        return lines or [f'{ind}pass']

    def stmt(self, sts, k, ind):
        """-> (lines, statements consumed)"""
        s = sts[k]; c = self.c; kd = s.kind
        shop = self.shop(sts, k, ind)
        if shop: return shop
        nxt = sts[k + 1] if k + 1 < len(sts) else None
        nxt2 = sts[k + 2] if k + 2 < len(sts) else None
        if kd == 'expr' and s.expr.kind == 'call':
            if is_call(s, 'store_random') and len(s.expr.args) == 2 and s.expr.args[0][1].kind == 'id' \
                    and s.expr.args[0][1].name in self.ROLL and s.expr.args[1][1].kind == 'num':
                c.rolled = True                    # the draw, kept in `roll` (random_roll): read as `roll` from here on
                return [f'{ind}roll = random.roll({s.expr.args[1][1].v})'], 1
            folded = self.fold_store(s.expr, nxt, ind)
            if folded: return folded, 2
            if is_call(s, 'set_obj_visibility') and len(s.expr.args) == 2 and all(a.kind == 'num' and nm is None for nm, a in s.expr.args) \
                    and s.expr.args[1][1].v in (0, 1):
                return [f'{ind}objects[{s.expr.args[0][1].v}].{"show" if s.expr.args[1][1].v else "hide"}()'], 1
            return self.call(s.expr, nxt, nxt2, ind)
        if is_engine_set(s, 'object') and nxt is not None and is_engine_set(nxt, 'animation') and nxt2 is not None \
                and is_call(nxt2, 'call_routine') and len(nxt2.expr.args) == 1 and is_routine(nxt2.expr.args[0][1], 'reset_object_animation'):
            return [f'{ind}objects[{s.expr.v}].animate({nxt.expr.v})'], 3            # the object's animation k, from its start
        if kd == 'assign' and s.name == 'engine' and getattr(s, 'target', None) is not None and s.target.kind == 'member' \
                and s.target.name == 'arg' and s.op == '=' and s.expr.kind == 'num' and nxt is not None and is_call(nxt, 'call_routine') \
                and len(nxt.expr.args) == 1 and nxt.expr.args[0][1].kind == 'call':
            r = nxt.expr.args[0][1]
            if is_routine(r, 'fade_to_white') or is_routine(r, 'fade_from_white'):       # the frames (ticks) of the fade, in ms
                return [f'{ind}{r.args[0][1].v}({s.expr.v * 50})'], 2
            return [f'{ind}call({c.value(r)}, arg={s.expr.v})'], 2
        if kd == 'assign' and s.name == 'engine' and getattr(s, 'target', None) is not None and s.target.kind == 'member' \
                and s.target.name == 'picker_mode' and s.op == '=' and s.expr.kind == 'bool' and s.expr.v and nxt is not None \
                and is_call(nxt, 'call_routine') and len(nxt.expr.args) == 1 and is_routine(nxt.expr.args[0][1], 'choose_item'):
            # the item menu: `pick = pick_item()` when the next if tests what it gave (engine.picker_mode, engine.arg)
            if nxt2 is not None and nxt2.kind == 'if' and count_names(chain_conds(nxt2), {'engine'}) and picks_only(chain_conds(nxt2)):
                return [f'{ind}pick = pick_item()'] + self.if_chain(nxt2, ind, pick=True), 3
            return [f'{ind}pick_item()'], 2
        if kd == 'assign': return [ind + self.assign(s)], 1
        if kd == 'if':
            return self.if_chain(s, ind), 1
        if kd == 'unless':
            if s.jump in ('break', 'continue', 'return'): j = s.jump
            elif s.jump == 'goto' and not getattr(s, 'ext', False): j = self.goto(s.label)
            else: raise Hatch('unless')
            try:                                     # `unless (c) return;` is `if not c: return`, with the negation written out
                return [f'{ind}if {c.neg_cond(s.cond)}:', f'{ind}    {j}'], 1
            except Hatch:                            # (a test the lowering cannot negate back the same way, e.g. `in`)
                return [f'{ind}if {c.cond(s.cond)}:', f'{ind}    pass', f'{ind}else:', f'{ind}    {j}'], 1
        if kd == 'while':
            return [f'{ind}while {c.cond(s.cond)}:'] + self.body(s.body, ind + '    '), 1
        if kd == 'loop':
            return [f'{ind}while True:'] + self.body(s.body, ind + '    '), 1
        if kd in ('break', 'continue'): return [ind + kd], 1
        if kd == 'return':
            if s.expr is not None: raise Hatch('return value')
            return [ind + 'return'], 1
        if kd == 'goto' and not getattr(s, 'ext', False): return [ind + self.goto(s.label)], 1
        if kd == 'gosub' and not getattr(s, 'ext', False): return [ind + self.call_target(s.label)], 1
        if kd == 'await':
            e = s.expr
            if e.kind == 'id' and e.name == 'camera': return [ind + 'camera.arrived()'], 1
            return [f'{ind}{self.c.who(e)}arrived()'], 1
        if kd == 'choice': return self.choice(s, ind), 1
        if kd == 'match' and s.clamp: return self.match(s, ind), 1
        raise Hatch(kd)

    def stock_flag(self, s, value):
        """`shop_stock.x = true;` / `set_trigger(n);` (value False: the clear) -> the item id of a shop-stock trigger, or None."""
        n = None
        if s.kind == 'assign' and s.op == '=' and s.expr.kind == 'bool' and s.expr.v == value:
            t = s.target if getattr(s, 'target', None) is not None else None
            name = f'{t.obj.name}.{t.name}' if t is not None and t.kind == 'member' and t.obj.kind == 'id' else (s.name if t is None else None)
            n = FLAG_NUMBERS().get(name)
        elif is_call(s, 'set_trigger' if value else 'clear_trigger') and len(s.expr.args) == 1 and s.expr.args[0][1].kind == 'num':
            n = s.expr.args[0][1].v
        return n - 384 if n is not None and 384 <= n < 512 else None

    def shop(self, sts, k, ind):
        """The stock set, picker mode off, `call(Routine.shop, arg=<the NPC being talked to>)`, the same stock cleared in the
        same order -> `shop(Item.A, ...)` (the lowering writes the same instructions). -> (lines, consumed) or None"""
        c = self.c
        if not c.self_npc or c.self_npc not in c.npcs: return None
        items = []; j = k
        while j < len(sts) and self.stock_flag(sts[j], True) is not None: items.append(self.stock_flag(sts[j], True)); j += 1
        if not items or j + 3 + len(items) > len(sts): return None
        a, b, r = sts[j], sts[j + 1], sts[j + 2]
        if not (a.kind == 'assign' and a.name == 'engine' and getattr(a, 'target', None) is not None and a.target.kind == 'member'
                and a.target.name == 'picker_mode' and a.op == '=' and a.expr.kind == 'bool' and not a.expr.v): return None
        if not (is_engine_set(b, 'arg') and b.expr.v == c.npcs[c.self_npc]): return None
        if not (is_call(r, 'call_routine') and len(r.expr.args) == 1 and is_routine(r.expr.args[0][1], 'shop')): return None
        if [self.stock_flag(x, False) for x in sts[j + 3:j + 3 + len(items)]] != items: return None
        names = N.enum_members('item')
        return [f'{ind}shop({", ".join(f"Item.{names[i]}" if i in names else f"Item({i})" for i in items)})'], 3 + 2 * len(items)

    ROLL = ('random_roll', 'p110')
    TYPE = ('partner_type', 'p103')
    DATE = {'date_year': 'clock.year', 'date_day': 'clock.day', 'date_hour': 'clock.hour', 'date_minute': 'clock.minute',
            'p105': 'clock.year', 'p106': 'clock.day', 'p107': 'clock.hour', 'p108': 'clock.minute'}

    def fold_store(self, e, nxt, ind):
        """`store_date(date_year); if (date_hour
        >= 7 ...)` -> `if clock.hour >= 7 ...:` and `store_digimon_type(partner_type); if (partner_type in [3, 5])` -> `if
        partner.species in (Species.Agumon, ...):` when the stored value is read only in that condition. -> lines or None"""
        if nxt is None or nxt.kind not in ('if', 'unless') or e.fn.kind != 'id' or e.fn.name not in ('store_date', 'store_digimon_type'): return None
        args = [a for nm, a in e.args]
        if e.fn.name == 'store_digimon_type':
            if len(args) != 1 or args[0].kind != 'id' or args[0].name not in self.TYPE: return None
            names = set(self.TYPE); fold = {n: 'partner.species' for n in self.TYPE}; most = 99
        else:
            if len(args) != 1 or args[0].kind != 'id' or args[0].name not in ('date_year', 'p105'): return None
            names = set(self.DATE); fold = dict(self.DATE); most = 99
        prev = self.c.fold
        if most > 1 and nxt.kind == 'if' and count_names(nxt.cond, names) and \
                count_names(nxt, names) == sum(count_names(x, names) for x in chain_conds(nxt)):
            try:                    # the clock or the species read by the tests of an if/elif chain (the lowering stores it once)
                self.c.fold = fold; return self.if_chain(nxt, ind)
            finally:
                self.c.fold = prev
        if count_names(nxt, names) != count_names(nxt.cond, names) or not 1 <= count_names(nxt.cond, names) <= most: return None
        if nxt.kind == 'unless':
            try:
                self.c.fold = fold; return self.stmt([nxt], 0, ind)[0]
            finally:
                self.c.fold = prev
        try:
            self.c.fold = fold; first = self.c.cond(nxt.cond)
        finally:
            self.c.fold = prev
        lines = self.if_chain(nxt, ind)
        lines[0] = f'{ind}if {first}:'
        return lines

    def call_target(self, label):
        if label in self.c.shared_labels: raise Hatch('a row of a table')       # `shared L:` inside a literal section: DWS only
        if label in self.c.shared: return f'{label}()'
        if label in self.c.entry_of: return self.c.entry_of[label]
        raise Hatch('jump target')

    def goto(self, label):
        return 'return ' + self.call_target(label)

    def if_chain(self, s, ind, pick=False):
        c = self.c
        def cond(x):
            c.pick = pick
            try: return c.cond(x)
            finally: c.pick = False
        out = [f'{ind}if {cond(s.cond)}:'] + self.body(s.then, ind + '    ')
        e = s.els
        while e is not None:
            if e.kind == 'if':
                out += [f'{ind}elif {cond(e.cond)}:'] + self.body(e.then, ind + '    '); e = e.els; continue
            out += [f'{ind}else:'] + self.body(e, ind + '    '); break
        return out

    def choice(self, s, ind):
        c = self.c
        if s.openc or s.keep: raise Hatch('open/keep choice')
        prefix = ''
        if s.who is not None:
            w = c.entity(s.who)
            prefix = '' if w == 'tamer' else w + '.'
        opts = s.opts
        # ask(yes=, no=): two options, the second also the cancel (or empty: the same code, see gen.st_choice)
        if len(opts) == 2 and s.cancel is None and not opts[0][2] and (opts[1][2] or not getattr(opts[1][1], 'stmts', True)):
            out = [f'{ind}if {prefix}ask(yes={c.option(opts[0][0])}, no={c.option(opts[1][0])}):'] + self.body(opts[0][1], ind + '    ')
            els = self.body(opts[1][1], ind + '    ')
            if els != [f'{ind}    pass']: out += [f'{ind}else:'] + els
            return out
        labels = 'abcdefgh'
        out = [f'{ind}match {prefix}choose({", ".join(f"{labels[i]}={c.option(t)}" for i, (t, _, _) in enumerate(opts))}):']
        for i, (t, body, both) in enumerate(opts):
            lines = self.body(body, ind + '        ')
            if lines == [f'{ind}        pass'] and not both: continue        # an option that does nothing needs no case
            out += [f'{ind}    case "{labels[i]}"{" | _" if both else ""}:'] + lines
        if s.cancel is not None:
            out += [f'{ind}    case _:'] + self.body(s.cancel, ind + '        ')
        if len(out) == 1: out += [f'{ind}    case "a":', f'{ind}        pass']           # (a match needs one case)
        return out

    def match(self, s, ind):
        c = self.c
        subj = c.operand(s.subject)
        out = [f'{ind}match {subj}:']
        for k, (pat, body) in enumerate(s.arms):
            if pat is None or pat.kind != 'num' or pat.v != k: raise Hatch('match pattern')
            last = k == len(s.arms) - 1          # the engine's SWITCH clamps: a value past the end takes the last arm
            out += [f'{ind}    case {pat.v}{" | _" if last else ""}:'] + self.body(body, ind + '        ')
        return out

    def assign(self, s):
        c = self.c
        tgt = f'{s.name}' if getattr(s, 'target', None) is None else None
        if tgt is None:
            t = s.target
            if t.kind == 'member' and t.obj.kind == 'id': tgt = f'{t.obj.name}.{t.name}'
            else: raise Hatch('assign target')
        e = s.expr
        if tgt == 'engine.cutscene' and s.op == '=' and e.kind == 'bool' and e.v and c.handler == 'talk-first':
            raise Hatch('scene')                 # (consumed by the handler header; never reached)
        rolled, c.rolled = c.rolled, False            # (a write to the draw's register keeps its name: random_roll.set(3))
        try: py = c.name(tgt)
        finally: c.rolled = rolled
        if e.kind == 'bool' and s.op == '=': return f'{py}.{"set" if e.v else "clear"}()'
        if e.kind != 'num' and not (e.kind == 'unary' and e.op == '-' and e.e.kind == 'num'): raise Hatch('assign value')
        v = c.value(e)
        return f'{py}.{ {"=": "set", "+=": "add", "-=": "sub"}[s.op] }({v})' if s.op in ('=', '+=', '-=') else (_ for _ in ()).throw(Hatch('op'))

    # ---------------------------------------------------------------- calls
    def call(self, e, nxt, nxt2, ind):
        c = self.c
        if e.fn.kind != 'id': raise Hatch('call')
        f = e.fn.name; pos = [a for nm, a in e.args if nm is None]; kw = {nm: a for nm, a in e.args if nm}
        def awaited(who):
            return nxt is not None and nxt.kind == 'await' and nxt.expr.kind == who.kind and getattr(nxt.expr, 'name', None) == getattr(who, 'name', None) \
                and who.kind == 'id'
        if f == 'say':
            if not pos: raise Hatch('say')
            w = c.who(pos[0])
            if not w and not c.self_npc: raise Hatch('bare say')
            # recruitable: say(self, one key); battle(); recruit(species)
            if not w and len(pos) == 2 and nxt is not None and nxt2 is not None and is_call(nxt, 'battle') and not nxt.expr.args \
                    and is_call(nxt2, 'recruit') and len(nxt2.expr.args) == 1:
                line = c.text_arg(pos[1])
                if not line.startswith('page('):
                    sp = nxt2.expr.args[0][1]; sp = sp.args[0][1] if sp.kind == 'call' else sp
                    joins = c.typed('species', sp); own = c.species_of.get(c.self_npc)
                    own = f'Species.{N.enum_members("species").get(own)}' if own is not None else None
                    return [f'{ind}recruitable({c.self_npc}, line={line}' + ('' if joins == own else f', joins={joins}') + ')'], 3
            return [f'{ind}{w}say({", ".join(c.text_arg(a) for a in pos[1:])})'], 1
        if f == 'battle':
            if not e.args: return [f'{ind}fight()'], 1
            foes = kw.get('foes'); esc = kw.get('escape')
            if foes is None or foes.kind != 'list' or set(kw) - {'foes', 'escape'} or pos: raise Hatch('battle')
            esc_v = esc.v if esc is not None and esc.kind == 'bool' else False if esc is None else None
            if esc_v is None: raise Hatch('battle escape')
            return [f'{ind}fight({", ".join(c.entity(x) for x in foes.items)}{"" if esc_v else ", escape=False"})'], 1
        if f == 'recruit' and len(pos) == 1 and not kw:
            return [f'{ind}recruit({c.typed("species", pos[0].args[0][1]) if pos[0].kind == "call" else c.typed("species", pos[0])})'], 1
        if f == 'unrecruit' and len(pos) == 1 and not kw:
            return [f'{ind}unrecruit({c.typed("species", pos[0].args[0][1]) if pos[0].kind == "call" else c.typed("species", pos[0])})'], 1
        if f in ('walk', 'run') and len(pos) >= 3:
            w = c.who(pos[0]); cam = kw.get('camera')
            if set(kw) - {'camera'} or len(pos) != 3 or (cam is not None and cam.kind != 'bool'): raise Hatch('walk')
            camera = ', camera=True' if cam is not None and cam.v else ''
            if awaited(pos[0]):
                return [f'{ind}{w}{f}({c.value(pos[1])}, {c.value(pos[2])}{camera})'], 2
            return [f'{ind}{w}{f}({c.value(pos[1])}, {c.value(pos[2])}{camera}, wait=False)'], 1
        if f == 'animate' and len(pos) == 2 and not kw:
            w = c.who(pos[0])
            if awaited(pos[0]): return [f'{ind}{w}play({c.value(pos[1])}, wait=True)'], 2
            return [f'{ind}{w}play({c.value(pos[1])})'], 1
        if f == 'face' and len(pos) == 2 and not kw:
            return [f'{ind}{c.who(pos[0])}face({c.entity(pos[1])})'], 1
        if f == 'rotate' and len(pos) == 2 and not kw:
            return [f'{ind}{c.who(pos[0])}turn({c.value(pos[1])})'], 1
        if f == 'remove' and len(pos) == 1 and not kw:
            return [f'{ind}{c.who(pos[0])}leave()'], 1
        if f == 'wait' and len(pos) == 1 and not kw and pos[0].kind in ('num', 'dur'):
            return [f'{ind}wait({pos[0].v * 50})'], 1
        if f == 'sound' and len(pos) == 2 and not kw and all(a.kind == 'num' for a in pos) and (pos[0].v, pos[1].v) == (8, 11):
            return [f'{ind}sound.jingle()'], 1
        if f == 'sound' and len(pos) == 2 and not kw: return [f'{ind}sound({c.value(pos[0])}, {c.value(pos[1])})'], 1
        if f in ('give', 'take') and 1 <= len(pos) <= 2 and not kw and pos[0].kind == 'call' and pos[0].fn.name == 'item':
            n = '' if len(pos) == 1 else f', {c.value(pos[1])}'
            return [f'{ind}{f}({c.value(pos[0])}{n})'], 1
        if f in ('give_bits', 'take_bits') and len(pos) == 1 and not kw:
            return [f'{ind}{f[:4]}(bits={c.value(pos[0])})'], 1
        if f == 'camera_on' and len(pos) == 1 and set(kw) <= {'speed'}:
            return [f'{ind}camera.on({c.entity(pos[0])}' + (f', speed={c.value(kw["speed"])}' if 'speed' in kw else '') + ')'], 1
        if f == 'camera_to' and len(pos) == 2 and set(kw) <= {'speed'}:
            return [f'{ind}camera.to({c.value(pos[0])}, {c.value(pos[1])}' + (f', speed={c.value(kw["speed"])}' if 'speed' in kw else '') + ')'], 1
        if f == 'walk_away' and len(pos) == 3 and set(kw) <= {'looks', 'pause'}:
            if 'pause' in kw and kw['pause'].kind != 'num': raise Hatch('walk_away pause')
            extra = (f', looks={c.value(kw["looks"])}' if 'looks' in kw else '') + (f', pause={kw["pause"].v * 50}' if 'pause' in kw else '')
            return [f'{ind}{c.who(pos[0])}walk_away({c.value(pos[1])}, {c.value(pos[2])}{extra})'], 1
        if f in ('join_city', 'join_city_camera') and len(pos) == 5 and set(kw) <= {'prosperity'}:
            who = pos[0]; w = c.who(who)
            sp = c.typed('species', pos[1].args[0][1]) if pos[1].kind == 'call' else c.typed('species', pos[1])
            own = c.species_of.get(c.entity(who))
            own = f'Species.{N.enum_members("species").get(own)}' if own is not None else None
            parts = [f'line={c.text_arg(pos[4])}']
            if sp != own: parts.append(f'species={sp}')
            snd = (c.value(pos[2]), c.value(pos[3]))
            if snd != ('8', '11'): parts.append(f'sound=({snd[0]}, {snd[1]})')
            if 'prosperity' in kw: parts.append(f'prosperity={c.value(kw["prosperity"])}')
            if f == 'join_city': parts.append('camera=False')
            return [f'{ind}{w}send_to_city({", ".join(parts)})'], 1
        if f in ('fade_to_white', 'fade_from_white') and len(pos) == 1 and not kw and pos[0].kind == 'num':
            return [f'{ind}{f}({pos[0].v * 50})'], 1
        if f == 'hide_hud' and not e.args: return [f'{ind}hide_hud()'], 1
        if f in ('set_trigger', 'clear_trigger') and len(pos) == 1 and pos[0].kind == 'num' and not kw:
            if 200 <= int(pos[0].v) <= 311:
                return [f'{ind}{"recruit" if f == "set_trigger" else "unrecruit"}({c.typed("species", Node("num", pos[0].pos, v=int(pos[0].v) - 200))})'], 1
            return [f'{ind}trigger({pos[0].v}).{"set" if f == "set_trigger" else "clear"}()'], 1
        if f == 'learn' and len(pos) == 1 and not kw: return [f'{ind}learn({c.value(pos[0])})'], 1
        if f == 'warp_to' and len(pos) == 3 and not kw:
            then = '' if pos[2].kind == 'num' and pos[2].v == 255 else f', then={c.value(pos[2])}'
            return [f'{ind}warp({c.screen_member(pos[0].v) if pos[0].kind == "num" else c.value(pos[0])}, entry={c.value(pos[1])}{then})'], 1
        if f == 'spawn_item' and len(pos) == 3 and not kw and pos[1].kind == 'num' and pos[2].kind == 'num':
            import dwmap                                      # (SPAWN_ITEM takes a tile: printed as its centre in world units)
            x, z = dwmap.tile_to_world(pos[1].v, pos[2].v)
            return [f'{ind}spawn_item({c.value(pos[0])}, at=({x}, {z}))'], 1
        if f == 'call_routine' and len(pos) == 1 and not kw:
            if is_routine(pos[0], 'remove_chosen_item'): return [f'{ind}take_picked()'], 1
            if is_routine(pos[0], 'remove_all_chosen_item'): return [f'{ind}take_picked(all=True)'], 1
            return [f'{ind}call({c.value(pos[0])})'], 1
        if f == 'call_digimon_routine' and len(pos) == 1 and not kw and pos[0].kind == 'call' and pos[0].fn.kind == 'id' and pos[0].fn.name == 'routine':
            c.mark('raw'); return [f'{ind}raw.call_digimon_routine(DigimonRoutine.{pos[0].args[0][1].v})'], 1
        if f == 'show_textbox':
            c.mark('raw'); return [f'{ind}raw.show_textbox({", ".join(c.value(a) for a in pos)})'], 1
        # named forms of the frequent engine commands (the rest stays raw.<command>)
        if not kw and all(nm is None for nm, _ in e.args):
            if f == 'load_digimon' and len(pos) == 1: return [f'{ind}load({c.value(pos[0])})'], 1
            if f == 'set_digimon' and len(pos) == 3 and pos[1].kind == 'num' and pos[2].kind == 'num' and pos[2].v in (0, 1):
                return [f'{ind}spawn({c.value(pos[0])}, slot={pos[1].v}' + (', autotalk=True' if pos[2].v else '') + ')'], 1
            if f == 'set_bgm' and len(pos) == 1: return [f'{ind}music({c.value(pos[0])})'], 1
            if f == 'set_script' and len(pos) == 2 and pos[1].kind == 'num': return [f'{ind}use_script({c.value(pos[0])}, {c.screen_member(pos[1].v)})'], 1
            if f == 'entity_set_rotation' and len(pos) == 2: return [f'{ind}{c.who(pos[0])}turn({c.value(pos[1])})'], 1
            if f in ('give_item', 'remove_item') and len(pos) == 2:
                n = '' if pos[1].kind == 'num' and pos[1].v == 1 else f', {c.value(pos[1])}'
                return [f'{ind}{"give" if f == "give_item" else "take"}({c.value(pos[0])}{n})'], 1
            if f == 'jump_to_file' and len(pos) == 2: return [f'{ind}jump_to_script({c.value(pos[0])}, {c.value(pos[1])})'], 1
            if f == 'spawn_chest' and len(pos) == 6 and pos[5].kind == 'num' and pos[2].kind == 'num' and pos[2].v == 0 \
                    and pos[4].kind == 'num' and pos[4].v in (0, 1024, 2048, 3072):
                facing = f', facing={pos[4].v}' if pos[4].v else ''
                return [f'{ind}spawn_chest({c.value(pos[0])}, at=({c.value(pos[1])}, {c.value(pos[3])}), opened=trigger({pos[5].v}){facing})'], 1
            if f == 'rotate_3d_object' and len(pos) == 3 and all(a.kind == 'num' for a in pos) and (pos[1].v, pos[2].v) == (0, 1):
                return [f'{ind}swing_door({pos[0].v})'], 1
            if f == 'fadeout_hud' and len(pos) == 1 and pos[0].kind == 'num' and pos[0].v == 0: return [f'{ind}hide_hud()'], 1
            if f in ('set_stat', 'add_stat', 'reduce_stat') and len(pos) == 2 and pos[0].kind == 'num' and pos[0].v in STAT_NAMES:
                return [f'{ind}partner.{ {"set_stat": "set", "add_stat": "add", "reduce_stat": "sub"}[f] }({STAT_NAMES[pos[0].v]}={c.value(pos[1])})'], 1
            if f in ('set_stat', 'add_stat', 'reduce_stat') and len(pos) == 2 and pos[0].kind == 'num' and pos[0].v == TAMER_LEVEL:
                return [f'{ind}tamer.{ {"set_stat": "set", "add_stat": "add", "reduce_stat": "sub"}[f] }(level={c.value(pos[1])})'], 1
        from .. import registry as R
        cmd = R.COMMANDS.get(f)
        if cmd is not None and not kw and len(pos) == len(cmd.fields) and 'l' not in cmd.fields:
            args = []
            for fld, a in zip(cmd.fields, pos):
                if fld == 'e': args.append(c.entity(a) if a.kind != 'num' else str(a.v))
                elif fld == 'p': args.append(c.value(a) if a.kind != 'num' else str(a.v))
                elif fld in ('m', 'm16') and a.kind == 'num': args.append(c.screen_member(a.v))
                else: args.append(c.value(a))
            c.mark('raw')
            return [f'{ind}raw.{f}({", ".join(args)})'], 1
        raise Hatch(f'call {f}')


def count_names(node, names):
    n = 0
    def walk(x):
        nonlocal n
        if isinstance(x, Node):
            if x.kind == 'id' and x.name in names: n += 1
            for v in x.__dict__.values(): walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x: walk(v)
    walk(node)
    return n


STAT_NAMES = {0: 'offense', 1: 'defense', 2: 'speed', 3: 'brain', 4: 'max_hp', 5: 'max_mp', 6: 'hp', 7: 'mp', 8: 'tiredness', 9: 'happiness',
              10: 'discipline', 11: 'energy', 12: 'virus', 13: 'lifetime', 14: 'merit', 15: 'battles', 16: 'fled_battles',
              17: 'tournaments_won', 18: 'tournament_wins', 19: 'tournaments_lost', 20: 'weight', 22: 'lives'}
TAMER_LEVEL = 21                                         # SCRIPT_STAT_TAMER_LEVEL: `tamer.level`
# the partner's conditions (CONDITION_* of params.h: one bit each), `if partner.sick:` (the IF clause `condition`)
CONDITION_NAMES = {1: 'sleepy', 2: 'tired', 4: 'hungry', 8: 'poopy', 16: 'unhappy', 32: 'injured', 64: 'sick'}


def is_routine(a, name):
    return a.kind == 'call' and a.fn.kind == 'id' and a.fn.name == 'routine' and len(a.args) == 1 and a.args[0][1].kind == 'str' \
        and a.args[0][1].v == name


def is_engine_set(st, field):
    """`engine.<field> = <number>;`"""
    return st.kind == 'assign' and st.name == 'engine' and getattr(st, 'target', None) is not None and st.target.kind == 'member' \
        and st.target.name == field and st.op == '=' and st.expr.kind == 'num'


def is_engine(a, field):
    return a.kind == 'member' and a.obj.kind == 'id' and a.obj.name == 'engine' and a.name == field


def chain_conds(s):
    """The conditions of an if/elif chain (not of its bodies)."""
    out = []
    while s is not None and s.kind == 'if': out.append(s.cond); s = s.els
    return out


def picks_only(conds):
    """Every test of the chain reads engine.picker_mode or engine.arg alone (the item menu's answer)."""
    def ok(c):
        if c.kind == 'unary' and c.op == '!': return ok(c.e)
        if c.kind == 'binary' and c.op in ('&&', '||'): return ok(c.l) and ok(c.r)
        if is_engine(c, 'picker_mode'): return True
        return c.kind == 'binary' and c.op in ('==', '!=', 'in') and is_engine(c.l, 'arg')
    return all(ok(c) for c in conds)


def is_call(st, name):
    return st.kind == 'expr' and st.expr.kind == 'call' and st.expr.fn.kind == 'id' and st.expr.fn.name == name


def strip_strings(line):
    return re.sub(r'"(?:[^"\\]|\\.)*"', '""', line.split('//')[0] if '"' not in line else line)


# --------------------------------------------------------------------- files
_FLAG_NUMBERS = {}


def FLAG_NUMBERS():
    """{named flag: trigger number} (`shop_stock.meat` -> 422)."""
    if not _FLAG_NUMBERS:
        from ..lift import Names
        _FLAG_NUMBERS.update({nm: n for n, nm in Names().flags.items()})
    return _FLAG_NUMBERS


def state_names():
    """Every state name a DWS file of the base may use, as Python sees it (`random_roll`, `engine.arg`, `tournament.day`)."""
    from ..lift import Names
    nm = Names()
    out = set(nm.vars.values()) | set(nm.flags.values())
    return out


def is_literal(ev):
    """A section that keeps labels or raw jumps: one hatch."""
    found = []
    def walk(x):
        if isinstance(x, Node):
            if x.kind == 'label' and not getattr(x, 'shared', False): found.append(x)
            if x.kind in ('goto', 'gosub', 'unless') and getattr(x, 'label', None) and not SEC_LABEL.match(x.label or '') and \
                    not re.match(r'^(L\d+|sec\d+\w*)$', x.label or ''): found.append(x)
            if x.kind == 'label' and getattr(x, 'shared', False): found.append(x)
            if x.kind == 'expr' and x.expr.kind == 'call' and x.expr.fn.kind == 'id' and x.expr.fn.name in ('set_selection', 'switch', 'switch_w', 'end_selection'):
                found.append(x)
            for v in x.__dict__.values(): walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x: walk(v)
    walk(ev.body)
    return bool(found)


class View:
    """The Python view of one DWS file of the base (a script, or MAPHEAD's files together)."""
    def __init__(self, names, states):
        self.names = names; self.states = states; self.verdicts = {}

    def handler_of(self, ev, sid, npcs_inv):
        """-> (decorator, function name, kind) of an event."""
        n = ev.ev
        if n == 'talk': return f'@{ev.arg}.on_talk', 'talk'
        if n == 'enter': return '@{S}.on_enter', 'enter'
        if n == 'step': return f'@{{S}}.on_step({ev.arg})', f'step{ev.arg}'
        if n == 'use': return f'@{{S}}.on_use({ev.arg})', f'use{ev.arg}'
        if sid == 'maphead':
            if ev.arg <= 254: return f'@screen({N.screen_members().get(ev.arg) and "Screen." + N.screen_members()[ev.arg] or ev.arg}).on_load', 'setup'
            return f'@hook({ev.arg})', f'sec{ev.arg}'
        return f'@{{S}}.section({ev.arg})', f'sec{ev.arg}'

    def entry_call(self, ev, sid):
        """The Python expression that runs the event's handler (for `goto secN` / `gosub secN`)."""
        n = ev.ev
        if n == 'talk': return f'{ev.arg}.talk()'
        if n == 'enter': return 'enter()'
        if n == 'step': return f'step{ev.arg}()'
        if n == 'use': return f'use{ev.arg}()'
        return f'sec{ev.arg}()'

    def script_file(self, path, sid, src=None):
        """-> (python text, {section: verdict})"""
        src = open(path, encoding='utf-8').read() if src is None else src
        prog = parse(src, path)
        lines = src.split('\n')
        blocks = [it for it in prog if it.kind == 'script']
        npcs = {}; events = []; shared = []; order = None
        for b in blocks:
            for it in b.body:
                if it.kind == 'npc': npcs[it.name] = it.num
                elif it.kind == 'event': events.append(it)
                elif it.kind == 'shared': shared.append(it)
                elif it.kind == 'sections': order = it.entries
        species_of = {nm: self.names.species.get((sid, e)) for nm, e in npcs.items()} if sid != 'maphead' else {}
        sec_of = {}
        for ev in events:
            sec = section_id(ev, npcs)
            sec_of[sec] = ev
        entry_of = {f'sec{sec}': self.entry_call(ev, sid) for sec, ev in sec_of.items()}
        ctx = Ctx(sid, lines, self.names, npcs, species_of, entry_of)
        ctx.state_names = self.states
        ctx.shared = {s.name for s in shared}; ctx.shared_labels = set()
        for b in blocks:
            for it in b.body:
                if it.kind == 'event':
                    for lab in scan_shared_labels(it.body): ctx.shared_labels.add(lab)
        out_body = []
        scr = N.screen_vars(sid) if sid != 'maphead' else []
        S = scr[0][1] if scr else 'lib'
        verdicts = {}
        for ev in events:
            sec = section_id(ev, npcs)
            deco, fname = self.handler_of(ev, sid, None)
            deco = deco.replace('{S}', S)
            ctx.verdict = 'clean'; ctx.self_npc = ev.arg if ev.ev == 'talk' else None; ctx.rolled = False
            stmts = list(ev.body.stmts)
            scene = False
            if ev.ev == 'talk' and stmts and stmts[0].kind == 'assign' and stmts[0].name == 'engine' and getattr(stmts[0], 'target', None) is not None \
                    and stmts[0].target.kind == 'member' and stmts[0].target.name == 'cutscene' and stmts[0].expr.kind == 'bool' and stmts[0].expr.v:
                scene = True; stmts = stmts[1:]
            pr = Printer(ctx)
            if is_literal(ev):
                body = pr.hatch(ev.body.stmts, '    ') if ev.body.stmts else ['    pass']
                body = whole_hatch(pr, ev.body, '    ')
                ctx.mark('literal'); scene = False
            else:
                body = pr.block(stmts, '    ') or ['    pass']
            if scene:
                deco = deco + '(scene=True)'
            out_body += ['', deco, f'def {fname}():    # section {sec}'] + body
            verdicts[sec] = ctx.verdict
        for sh in shared:
            ctx.verdict = 'clean'; ctx.self_npc = None; ctx.rolled = False
            pr = Printer(ctx)
            if is_literal(sh): body = whole_hatch(pr, sh.body, '    '); ctx.mark('literal')
            else: body = pr.block(list(sh.body.stmts), '    ') or ['    pass']
            out_body += ['', f'def {sh.name}():    # shared code (the disc\'s label {sh.name})'] + body
            verdicts[sh.name] = ctx.verdict
        head = header(sid, scr, npcs, species_of, ctx)
        tail = []
        if order:
            ents = []
            for n, nm, _ in order:
                ents.append(str(n) if nm is None else f'({n}, {nm})')
            tail = ['', '# the section table, in the order of the original header', 'sections(' + ', '.join(ents) + ')']
        return '\n'.join(head + out_body + tail) + '\n', verdicts


def scan_shared_labels(node):
    out = []
    def walk(x):
        if isinstance(x, Node):
            if x.kind == 'label' and getattr(x, 'shared', False): out.append(x.name)
            for v in x.__dict__.values(): walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x: walk(v)
    walk(node)
    return out


def recruit_flags(line):
    """Raw DWS text: the species flags (trigger 200 + type) as `is_recruited(species(n))`, the same bytes."""
    line = re.sub(r'\b(set|clear)_trigger\((2\d\d|30\d|31[01])\)', lambda m: f'{"recruit" if m.group(1) == "set" else "unrecruit"}(species({int(m.group(2)) - 200}))', line)
    return re.sub(r'\btrigger\((2\d\d|30\d|31[01])\)', lambda m: f'is_recruited(species({int(m.group(1)) - 200}))', line)


def whole_hatch(pr, body, ind):
    """The whole body of a section as one `dws` block (the lines between its braces)."""
    st = body.stmts
    if not st: return [f'{ind}pass']
    src = pr.c.src
    start = body.pos[1]                  # the line of the opening brace
    depth = 0; j = start - 1; lines = []
    first = True
    while j < len(src):
        line = src[j]; t = strip_strings(line)
        if first:
            k = line.index('{', body.pos[2] - 1) if '{' in line[body.pos[2] - 1:] else line.index('{')
            depth = 1; first = False; j += 1; continue
        d = depth + t.count('{') - t.count('}')
        if d <= 0: break
        lines.append(line); depth = d; j += 1
    ind0 = min(len(l) - len(l.lstrip()) for l in lines if l.strip())
    pr.c.mark('literal')
    return [f'{ind}dws(r"""'] + [f'{ind}    {recruit_flags(l[ind0:])}' if l.strip() else '' for l in lines] + [f'{ind}""")']


def section_id(ev, npcs):
    if ev.ev == 'talk': return int(npcs[ev.arg])
    if ev.ev == 'enter': return 254
    if ev.ev == 'step': return 51 + ev.arg
    if ev.ev == 'use': return 80 + ev.arg
    return ev.arg


def header(sid, scr, npcs, species_of, ctx):
    names, _ = N.disc_screens()
    title = 'MAPHEAD.SCN (the screens\' setups and the C entry points)' if sid == 'maphead' else \
        f'script {sid} of DG.SCN' + (f': {", ".join(f"screen {s} {names.get(s, chr(63))}" for s, _ in scr)}' if scr else ' (no screen loads it)')
    out = [f'# The Python view of {title}.',
           '# Made from the disc by `dws story-base`; the source of the story since 2026-10-15: edit it (no file = no script). Keys only, never the',
           '# game\'s words. `story-build` reads this file (lowered); the DWS beside it is the proven intermediate; mods import `dw.base`.',
           'from dw import *']
    if ctx.text_alias: out.append('from dw.text import text')
    if ctx.uses_names: out.append('from dw.names import *')
    out.append('')
    if sid == 'maphead':
        for nm, e in sorted(npcs.items(), key=lambda kv: kv[1]):
            out.append(f'{nm} = entity({e})')
    if sid != 'maphead':
        if scr:
            for s, var in scr:
                m = N.screen_members().get(s)
                out.append(f'{var} = screen({"Screen." + m if m else s})')
        else:
            out.append(f'lib = script({sid})')
        sp = N.enum_members('species')
        for nm, e in sorted(npcs.items(), key=lambda kv: kv[1]):
            s = species_of.get(nm)
            # the .MAP slot whose script id is e (usually e - 5), on the screen of the script that has it
            home, k = N.npc_home(sid, e, scr[0][0]) if scr else (None, e - 5)
            if k is None: out.append(f'{nm} = entity({e})'); continue
            out.append(f'{nm} = {dict(scr)[home] if scr else "lib"}.npc({"Species." + sp[s] if s in sp else "None"}, slot={k})'
                       + ('' if s in sp else f'    # {unplaced(home, k)}'))
    for base, alias in sorted(ctx.text_alias.items(), key=lambda kv: kv[1]):
        out.append(f'{alias} = text.{base}')
    return out


def unplaced(screen, slot):
    """Why an NPC of a view has no species (`npc(None, slot=k)`): the screen's setup (MAPHEAD) puts no species in that slot
    (checked 2026-10-13: none of the 105 is a slot MAPHEAD fills with one of several), the script does; and what the .MAP
    has there, as `dws slots` says."""
    d = next((x for x in BE.screen_slots(screen) if x['slot'] == slot), None) if screen is not None else None
    sp = N.enum_members('species').get(d['species']) if d else None
    return (f'the .MAP has {sp} here; ' if sp else 'no NPC of the .MAP in this slot; ') + 'the script spawns what stands here'


# --------------------------------------------------------------------- the base
def maphead_source(base):
    """MAPHEAD's files of story/base as one text (each is `maphead { ... }`): maphead.dws (the table, shared code) last."""
    d = os.path.join(base, 'maphead')
    files = sorted(f for f in os.listdir(d) if f.endswith('.dws'))
    files.sort(key=lambda f: f == 'maphead.dws')
    return '\n'.join(open(os.path.join(d, f), encoding='utf-8').read() for f in files)


def write_base(base, names=None, log=None):
    """script.py beside every script.dws of story/base, and maphead/hooks.py. -> {(script|'maphead', section): verdict}"""
    import glob
    if names is None:
        from .. import readable
        _, mh = readable.disc_texts(); names = readable.make_names(mh)
    v = View(names, state_names())
    verdicts = {}
    for p in sorted(glob.glob(os.path.join(base, 'zones', '*', '*', 'script.dws'))):
        m = re.match(r's(\d+)', os.path.basename(os.path.dirname(p)))
        sid = int(m.group(1))
        text, ver = v.script_file(p, sid)
        open(os.path.join(os.path.dirname(p), 'script.py'), 'w', encoding='utf-8').write(text)
        for k, x in ver.items(): verdicts[(sid, k)] = x
    src = maphead_source(base)
    path = os.path.join(base, 'maphead', 'maphead-all.dws')          # (a name for the messages; the text is the files joined)
    text, ver = v.script_file(path, 'maphead', src=src)
    open(os.path.join(base, 'maphead', 'hooks.py'), 'w', encoding='utf-8').write(text)
    for k, x in ver.items(): verdicts[('maphead', k)] = x
    return verdicts
