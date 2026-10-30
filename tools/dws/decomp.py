"""The decompiler (milestone 2): a script of the disc -> DWS in the *port form*, one typed statement per
instruction, labels and gotos kept, text as keys. It compiles back to the original bytes (the proof is
`dws.py roundtrip`); structure (if/else, loops, names, declarations) is added on top of it by later,
optional passes, each checked by the same recompile.

    script 2 port {
        tail;
        entry 254 sec254;
        sec254:
            store_random(p110, 99);
            unless (p110 <= 24) goto L1;
            spawn_item(item("Digimushrm"), 46, 45);
        ...
"""
import os, re, sys, tempfile, subprocess
from . import backend as BE
from dws import bytecode
from . import registry as R

LABEL_SEC = re.compile(r'^sec\d+\w*$')


class NotLiftable(Exception):
    pass


class Namer:
    """Names of items, species and techniques that resolve back to the same id."""
    def __init__(self):
        self.reg = BE.names()
        n = bytecode.names()
        self.names = {'item': n['i'], 'species': n['d'], 'tech': n['v']}

    def typed(self, kind, v):
        nm = self.names[kind].get(v)
        if nm and '"' not in nm and '\\' not in nm and nm.isascii() and self.reg[kind].get(nm.strip().lower()) == v:
            return f'{kind}("{nm}")'
        return f'{kind}({v})'


NAMER = None


def namer():
    global NAMER
    if NAMER is None: NAMER = Namer()
    return NAMER


ENT_HOOK = None           # the beautifier names entities (npc names) through this
NAME_HOOK = None          # ... and flags and pstats (an object with .var(pN) and .flag(n, neg), or None)


def ent(a):
    if ENT_HOOK is not None: return ENT_HOOK(a)
    return {'TAMER': 'tamer', 'PARTNER': 'partner'}.get(a, a)


def field(f, a):
    if f == 'p': return NAME_HOOK.var(a.lower()) if NAME_HOOK else a.lower()
    if f == 'w': return a.lower()
    if f == 'l': return a
    if f == 'e': return ent(a)
    if f == 'c': return '"' + a + '"'
    if f in ('i', 'i16'): return namer().typed('item', int(a))
    if f in ('d', 'd16'): return namer().typed('species', int(a))
    if f in ('v', 'v16'): return namer().typed('tech', int(a))
    return a


def clause(c):
    t = c.split()
    if t and t[0] in ('and', 'or'): join, t = ('&&' if t[0] == 'and' else '||'), t[1:]
    else: join = None
    neg = False
    if t and t[0] == 'not': neg, t = True, t[1:]
    k = t[0]
    if k == 'trigger':
        named = NAME_HOOK.flag(int(t[1]), neg) if NAME_HOOK else None
        if named is not None: return join, named
        s = f'trigger({t[1]})'
    elif re.fullmatch(r'p\d+', k): s = f'{NAME_HOOK.var(k) if NAME_HOOK else k} {t[1]} {t[2]}'
    elif re.fullmatch(r'w\d+', k): s = f'{k} {t[1]} {t[2]}'
    elif k == 'item': s = f'has({namer().typed("item", int(t[1]))}) {t[2]} {t[3]}'
    elif k == 'stat': s = f'stat({t[1]}) {t[2]} {t[3]}'
    elif k == 'card': s = f'has_card({t[1]}) {t[2]} {t[3]}'
    elif k == 'move': s = f'knows({namer().typed("tech", int(t[1]))})'
    elif k == 'cond': s = f'condition({t[1]})'
    elif k == 'money': s = f'bits {t[1]} {t[2]}'
    else: raise NotLiftable(c)
    if neg: s = '!' + s
    return join, s


def condition(clauses):
    cur = None; curop = None
    for c in clauses:
        join, s = clause(c)
        if cur is None: cur = s; continue
        if join is None: join = '~>'
        if curop is None or curop == join: cur = f'{cur} {join} {s}'
        else: cur = f'({cur}) {join} {s}'
        curop = join
    return cur


def lift(ins, keys):
    """DWS statement text for one instruction; `keys` are its text keys (textx.Keyer). None for a SHOW_TEXTBOX that
    continues an utterance: the `show_textbox(text(key))` of its first page gives all its pages."""
    n = ins.name; a = ins.args
    if n == 'SHOW_TEXTBOX':
        return f'show_textbox(text("{keys[0]}"));' if keys else None
    if n == 'SET_SELECTION':
        return 'set_selection(' + ', '.join(a + [f'text("{k}")' for k in keys]) + ');'
    if n == 'END_SELECTION': return 'end_selection();'
    if n in ('SWITCH', 'SWITCH_W'): return f'{n.lower()}(' + ', '.join([a[0].lower()] + a[1:]) + ');'
    if n == 'DATA': return 'data(' + ', '.join(a) + ');'
    if n == 'JUMP_TO': return f'goto {a[0]};'
    if n == 'JUMP_AND_LINK': return f'gosub {a[0]};'
    if n == 'IF':
        if not a or not a[-1].startswith('else ') or any(x.startswith(('then ', 'else ')) for x in a[:-1]):
            raise NotLiftable('IF shape')
        return f'unless ({condition(a[:-1])}) goto {a[-1][5:]};'
    if n == 'SET_PSTAT': return f'{a[0]} = {a[1]};'
    if n == 'ADD_TO_PSTAT': return f'{a[0]} += {a[1]};'
    if n == 'REDUCE_PSTAT': return f'{a[0]} -= {a[1]};'
    if n == 'SET_TRIGGER': return f'set_trigger({a[0]});'
    if n == 'UNSET_TRIGGER': return f'clear_trigger({a[0]});'
    cmd = R.COMMANDS.get(n.lower())
    if cmd is None: raise NotLiftable(n)
    if len(a) != len(cmd.fields): raise NotLiftable(f'{n} arguments')
    if n in ('CALL_ROUTINE', 'CALL_DIGIMON_ROUTINE'):
        table = R.ROUTINES if n == 'CALL_ROUTINE' else R.DIGIMON_ROUTINES
        nm = table.get(int(a[0]))
        if nm: return f'{cmd.name}(routine("{nm}"));'
    return f'{cmd.name}(' + ', '.join(field(f, x) for f, x in zip(cmd.fields, a)) + ');'


def asm_fallback(ins, keys):
    if ins.strings: raise AssertionError(f'{ins.name}: text rows in an instruction that is not lifted')
    parts = [f'{ins.name} {", ".join(ins.args)}'.strip()]
    return 'asm(' + ', '.join(f'"{p}"' if not p.startswith('text(') else p for p in parts) + ');'


def lift_chunks(text, kind, sid=None, fname='script', stats=None):
    """Lifts one disassembled script. Returns (header lines, chunks, entries): a chunk is
    (names of the entry labels at its start, [lines]); chunks follow the address order, so
    concatenating them gives back the code exactly."""
    secs, items, meta = bytecode.parse_script_text(text, fname)
    head = []
    if 'tail' in meta: head.append('tail;')
    entries = {lab for _, lab, _ in secs}
    for s, lab, _ in secs: head.append(f'entry {s} {lab};')

    from .textx import Keyer
    kr = Keyer(kind, sid)
    chunks = [([], [])]
    for it in items:
        if it[0] == 'label':
            kr.label(it[1])
            names, lines = chunks[-1]
            if it[1] in entries:
                if lines: chunks.append(([it[1]], [])); lines = chunks[-1][1]
                else: names.append(it[1])
            if lines and lines[-1] != '': lines.append('')
            lines.append(f'{it[1]}:'); continue
        ins = it[1]; lines = chunks[-1][1]
        if ins.name in ('.byte', '.align'):
            kr.chain = False
            lines.append('    ' + asm_fallback(ins, [])); fallback(stats, ins.name); continue
        keys = kr.ins(ins.name, len(ins.strings))
        try:
            st = lift(ins, keys)
            if st is not None: lines.append('    ' + st)
            if stats is not None: stats['lifted'] = stats.get('lifted', 0) + 1
        except NotLiftable:
            lines.append('    ' + asm_fallback(ins, keys)); fallback(stats, ins.name)
    if not chunks[0][1] and not chunks[0][0]: chunks.pop(0)
    return head, chunks, secs


def decompile_text(text, kind, sid=None, fname='script', stats=None):
    """text: the bytecode disassembly of one script. Returns DWS source (one file)."""
    head, chunks, _ = lift_chunks(text, kind, sid, fname, stats)
    body = []
    for _, lines in chunks: body += lines
    title = 'maphead port' if kind == 'maphead' else f'script {sid} port'
    return '\n'.join([f'{title} {{'] + ['    ' + h for h in head] + [''] + body + ['}', ''])


def fallback(stats, name):
    if stats is not None:
        stats['asm'] = stats.get('asm', 0) + 1
        stats.setdefault('asm_ops', {}); stats['asm_ops'][name] = stats['asm_ops'].get(name, 0) + 1


def disassemble_disc(tmp, dg=None, maphead=None):
    from . import textx
    return textx.disassemble(tmp, dg, maphead)


def decompile_all(dg=None, maphead=None):
    """{script id: DWS source}, MAPHEAD source, stats."""
    stats = {}
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        d, m = disassemble_disc(tmp, dg, maphead)
        for f in sorted(os.listdir(d)):
            mm = re.match(r'script_(\d+)\.scn\.txt$', f)
            if mm:
                sid = int(mm.group(1))
                out[sid] = decompile_text(open(os.path.join(d, f), encoding='utf-8').read(), 'script', sid, f, stats)
        mh = decompile_text(open(os.path.join(m, 'maphead.scn.txt'), encoding='utf-8').read(), 'maphead', None, 'maphead', stats)
    return out, mh, stats
