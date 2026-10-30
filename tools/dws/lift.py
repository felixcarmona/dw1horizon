"""The beautifier (milestone 6): the literal goto/label form of an original section -> readable DWS, proven.

    sections -> control flow structure (if/else, while, loop, choice, break/continue/return) -> sugar (say, names,
    walk/animate/face, battle, recruit) -> text -> COMPILE it -> flowcmp.compare with the original section.

Nothing is emitted unproven. Every section is tried at four levels, richest first; the first whose compiled form is
bisimilar to the original section (tools/dws/flowcmp.py) is kept:

    3  structure + sugar for dialogue, cutscenes, battles, names and library idioms
    2  structure + dialogue and names
    1  structure only (if/else, loops, choice) with one command per instruction
    0  the literal form: labels, `unless (c) goto L;` (always provable, since it is what the port form does)

A section that cannot be an event at all (it jumps into another section's code, or falls through into the next
section) is `port-only`: it stays in the port form (`decompile`). The result is the list of `Lifted` sections with their
level, so coverage can be measured (`dws coverage-readable`, build/story-analysis/beautifier-coverage.csv)."""
import os, re, tempfile
from . import decomp, flowcmp, anims, build as B
from . import registry as R
from .diag import DwsError

ROOT = B.ROOT
TERMINAL = {'END_SECTION', 'END_SCRIPT', 'JUMP_RETURN', 'JUMP_TO_FILE', 'JUMP_TO'}
KEEPS_OWNER = flowcmp.KEEPS_OWNER
RECRUIT_BASE, RECRUIT_N = 200, 112
CORE = os.path.join(ROOT, 'story', 'core')
KEYWORDS = {'tamer', 'player', 'partner', 'narrator', 'camera', 'all', 'self', 'true', 'false', 'if', 'else', 'while', 'loop', 'let', 'item', 'tech', 'species', 'text', 'page', 'flag', 'var', 'fn', 'sub', 'on', 'section', 'script', 'return', 'break', 'continue', 'choice', 'cancel', 'match', 'for', 'in', 'par', 'repeat', 'say', 'walk', 'run', 'wait', 'face', 'remove', 'give', 'take', 'bits', 'clock', 'won', 'lost', 'fled', 'engine', 'goto', 'gosub', 'unless', 'await'}
import keyword as _kw
from .py.naming import RESERVED as _PY_RESERVED
KEYWORDS |= _PY_RESERVED | set(_kw.kwlist)          # the Python view prints the same names (tools/dws/py/naming.py)


# ------------------------------------------------------------------------------------------------ names
class Names:
    """Names of the things the game already uses: pstats and triggers from `alias` declarations of story/core/*.dws
    and of story/names.toml (names are added as what things are is learnt), npc names by script."""

    def __init__(self, toml_path=None):
        self.vars = {}; self.flags = {}; self.file_of = {}; self.npc = {}; self.extra_vars = {}; self.extra_flags = {}; self.dws_path = None
        self.proposed = {}          # name -> {status, confidence, evidence} of the entries of names.toml written as a table (`status = "proposed"`)
        self.anims = {}
        for fn in sorted(os.listdir(CORE)):
            if fn.endswith('.dws'): self.load_dws(os.path.join(CORE, fn))
        p = toml_path or os.path.join(ROOT, 'story', 'names.toml')
        if os.path.exists(p):
            from .minitoml import load_toml
            d = load_toml(p)
            for tab, dst, extra in (('vars', self.vars, self.extra_vars), ('flags', self.flags, self.extra_flags)):
                for k, v in d.get(tab, {}).items():
                    if isinstance(v, dict): self.proposed[v['name']] = {x: y for x, y in v.items() if x != 'name'}; v = v['name']          # `7 = { name = "x", status = "proposed", ... }`
                    dst[int(k)] = v; extra[int(k)] = v; self.file_of[v] = '@names'
            for k, v in d.get('npc', {}).items(): self.npc[k] = v
        self.used = set(); self.auto = {}; self.species = {}
        for fn, f in (('walk_away', 'scene.dws'), ('join_city', 'recruit.dws'), ('join_city_camera', 'recruit.dws')):
            self.file_of[fn] = os.path.join(CORE, f)

    def load_dws(self, path):
        group = None; rel = os.path.relpath(path, ROOT)
        for line in open(path, encoding='utf-8'):
            m = re.match(r'\s*(?:pub\s+)?group\s+(\w+)\s*\{', line)
            if m: group = m.group(1)
            if re.match(r'\s*pub\s+group\s+anim\s*\{', line): self.file_of['anim'] = path
            if re.match(r'\s*\}\s*$', line): group = None
            m = re.match(r'\s*(?:pub\s+)?alias\s+(flag|var)\s+(\w+)\s*=\s*(\d+)\s*;', line)
            if m:
                name = f'{group}.{m.group(2)}' if group else m.group(2)
                (self.flags if m.group(1) == 'flag' else self.vars)[int(m.group(3))] = name
                self.file_of[name] = path

    def load_npcs(self, mh_text):
        """Default NPC names: the species MAPHEAD places in slot k of the screens that load a script, for the entity the
        script calls that slot by: the slot's script id in the screen's .MAP (usually 5 + k; the Item Shop's four keepers
        share entity 5, and Piximon, slot 4, is entity 6)."""
        from . import backend as BE
        found = {}; scripts = []; sp = []; screen = None; first_slot = {}
        def flush():
            for a in scripts:
                for slot, sid in sp:
                    ent = BE.slot_entity(screen, slot) if screen is not None else 5 + slot
                    found.setdefault((a, ent), set()).add(sid)
                    first_slot[(a, ent)] = min(slot, first_slot.get((a, ent), slot))
        for line in mh_text.split('\n'):
            m = re.match(r'^sec(\d+)\w*:', line)
            if m:
                flush(); scripts = []; sp = []; screen = int(m.group(1)) if int(m.group(1)) <= 254 else None; continue
            m = re.match(r'\s+SET_SCRIPT (\d+), (\d+)', line)
            if m: scripts.append(int(m.group(1)))
            m = re.match(r'\s+SET_DIGIMON (\d+), (\d+), (\d+)', line)
            if m: sp.append((int(m.group(2)), int(m.group(1))))
        flush()
        nm = decomp.namer().names['species']; auto = {}
        self.species = {(a, ent): next(iter(ids)) for (a, ent), ids in found.items() if len(ids) == 1}
        for (a, ent), ids in found.items():
            if len(ids) == 1 and nm.get(next(iter(ids))):
                auto[(a, ent)] = re.sub(r'[^a-z0-9]+', '_', nm[next(iter(ids))].lower()).strip('_')
        count = {}
        for (a, ent), v in auto.items(): count.setdefault((a, v), []).append(ent)
        for (a, ent), v in auto.items():
            # the species; `<species><slot>` when two of a species share the script (the Python view uses the same names)
            if v and not v[0].isdigit() and v not in KEYWORDS and len(count[(a, v)]) == 1: self.auto[f'{a}.{ent}'] = v
            elif v and not v[0].isdigit() and v not in KEYWORDS: self.auto[f'{a}.{ent}'] = f'{v}{first_slot.get((a, ent), ent - 5)}'

    def npc_name(self, sid, n):
        return self.npc.get(f'{sid}.{n}') or self.auto.get(f'{sid}.{n}') or (f'slot{n - 5}' if 5 <= n <= 20 else f'npc{n}')

    def var(self, pn):
        n = self.vars.get(int(pn[1:]))
        if n is None: return pn
        self.used.add(n); return n

    def flag(self, n, neg):
        if RECRUIT_BASE <= n < RECRUIT_BASE + RECRUIT_N:
            return ('!' if neg else '') + f'is_recruited({decomp.namer().typed("species", n - RECRUIT_BASE)})'
        nm = self.flags.get(n)
        if nm is None: return None
        self.used.add(nm); return ('!' if neg else '') + nm

    def import_paths(self, used, with_names=True):
        return sorted({(self.dws_path if self.file_of[n] == '@names' else self.file_of[n]) for n in used
                       if self.file_of.get(n) and (with_names or self.file_of[n] != '@names')})

    def extra_used(self, used):
        return {n for n in used if self.file_of.get(n) == '@names'}


# ------------------------------------------------------------------------------------------------ sections
class Sec:
    def __init__(self, label, sid):
        self.label = label; self.sid = sid; self.ins = []; self.labels = {}; self.keys = []; self.lines = []
        self.owner_in = None; self.all_labels = set(); self.next_label = None; self.ext = []; self.synth = False


def split_sections(text, kind, sid, fname):
    """-> [Sec] with instructions, label indexes, text keys (the keys of the port form) and the original asm lines."""
    from dws.bytecode import parse_script_text
    secs, items, meta = parse_script_text(text, fname)
    ids = {}
    for s, lab, _ in secs: ids.setdefault(lab, s)
    from .textx import Keyer
    out = []; cur = None; kr = Keyer(kind, sid)
    for it in items:
        if it[0] == 'label':
            kr.label(it[1])
            if decomp.LABEL_SEC.match(it[1]):
                cur = Sec(it[1], ids.get(it[1])); out.append(cur)
            if cur is not None: cur.labels.setdefault(it[1], len(cur.ins))
            continue
        ins = it[1]
        if ins.name.startswith('.'): kr.chain = False; ks = []
        else: ks = kr.ins(ins.name, len(ins.strings))
        if cur is None: continue
        cur.ins.append(ins); cur.keys.append(ks)
    # the original asm lines of each section, for the comparison
    lines = text.split('\n'); starts = [(i, re.match(r'^(sec\d+\w*):', l).group(1)) for i, l in enumerate(lines) if re.match(r'^sec\d+\w*:', l)]
    by = {}
    for k, (i, lab) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
        by[lab] = lines[i + 1:end]
    for s in out: s.lines = by.get(s.label, [])
    everywhere = {l for l, _, _ in [(it[1], 0, 0) for it in items if it[0] == 'label']}
    for k, s in enumerate(out):
        s.all_labels = everywhere; s.next_label = out[k + 1].label if k + 1 < len(out) else None
    return out


def targets(x, lab):
    """Label names an instruction refers to."""
    n = x.name
    if n in ('JUMP_TO', 'JUMP_AND_LINK'): return [x.args[0]]
    if n == 'IF': return [x.args[-1][5:]]
    if n == 'SET_SELECTION': return list(x.args)
    if n in ('SWITCH', 'SWITCH_W'): return list(x.args[1:])
    return []


def standalone(sec):
    """Why the section cannot be an event of its own, or None. Prepares the section for the structurer: a jump to a label
    outside it (a tail or a subroutine shared with other sections) becomes a virtual instruction index after the end
    (`sec.ext`, written `goto original(L)`), and falling off the end into the next section becomes such a jump."""
    if sec.sid is None: return 'no section id'
    for x in sec.ins:
        for t in targets(x, sec.labels):
            if t not in sec.labels and t not in sec.all_labels: return 'jumps to a label that does not exist'
    def falls():
        n = len(sec.ins)
        seen = set(); work = [0]
        while work:
            i = work.pop()
            if i in seen: continue
            seen.add(i)
            if i >= n: return True
            x = sec.ins[i]
            if x.name in ('END_SECTION', 'END_SCRIPT', 'JUMP_RETURN', 'JUMP_TO_FILE'): continue
            if x.name == 'JUMP_TO':
                if x.args[0] in sec.labels: work.append(sec.labels[x.args[0]])
                continue
            for t in targets(x, sec.labels):
                if t in sec.labels: work.append(sec.labels[t])
            work.append(i + 1)
        return False
    if falls():
        if not sec.next_label: return 'falls through at the end of the script'
        from dws.bytecode import Instr
        sec.ins.append(Instr('JUMP_TO', [sec.next_label], [], 'fall-through')); sec.keys.append([]); sec.synth = True
        sec.lines = sec.lines + [f'    JUMP_TO {sec.next_label}']
    elif not sec.ins: return 'empty'
    n = len(sec.ins)
    for x in sec.ins:
        for t in targets(x, sec.labels):
            if t not in sec.labels:
                sec.ext.append(t); sec.labels[t] = n + len(sec.ext)         # virtual index, after the end (n itself is "falls off")
    return None


def owner_flow(sec):
    """The dialog owner known when each instruction runs ('?' unknown), merged over paths."""
    n = len(sec.ins); UN = None; st = [UN] * (n + 1); st[0] = '?'; work = [0]
    def put(j, v):
        if j > n: return
        if st[j] is UN: st[j] = v; work.append(j)
        elif st[j] != v and st[j] != '?': st[j] = '?'; work.append(j)
    while work:
        i = work.pop()
        if i >= n: continue
        x = sec.ins[i]; o = st[i]
        out = x.args[0] if x.name == 'SET_DIALOG_OWNER' else (o if x.name in KEEPS_OWNER or x.name == 'JUMP_TO' else '?')
        if x.name in ('END_SECTION', 'END_SCRIPT', 'JUMP_RETURN', 'JUMP_TO_FILE'): continue
        if x.name == 'JUMP_TO': put(sec.labels[x.args[0]], out); continue
        if x.name == 'IF': put(i + 1, out); put(sec.labels[x.args[-1][5:]], out); continue
        for t in targets(x, sec.labels): put(sec.labels[t], '?')
        put(i + 1, out)
    sec.owner_in = [s if s is not None else '?' for s in st]


# ------------------------------------------------------------------------------------------------ structure
class St:
    """A structured statement. kind: i (one instruction), if, while, loop, choice, goto, break, continue, return, unlessj."""
    def __init__(self, kind, start, **kw):
        self.kind = kind; self.start = start; self.labels = []; self.__dict__.update(kw)


class Structurer:
    def __init__(self, sec):
        self.sec = sec; self.ins = sec.ins; self.n = len(sec.ins); self.lab = sec.labels
        self.extname = {v: k for k, v in sec.labels.items() if v > self.n}
        self.backs = {}
        for j, x in enumerate(self.ins):
            if x.name == 'JUMP_TO':
                t = self.lab[x.args[0]]
                if t <= j: self.backs.setdefault(t, []).append(j)
        self.keep = {self.lab[t] for x in self.ins for t in targets(x, self.lab) if x.name in ('SET_SELECTION', 'SWITCH', 'SWITCH_W', 'JUMP_AND_LINK')}
        self.refs = set()          # label indexes a remaining jump needs
        self.live = self.reachable()

    def reachable(self):
        seen = set(); work = [0]
        while work:
            i = work.pop()
            if i in seen or i >= self.n: continue
            seen.add(i); x = self.ins[i]
            if x.name in ('END_SECTION', 'END_SCRIPT', 'JUMP_RETURN', 'JUMP_TO_FILE'): continue
            for t in targets(x, self.lab): work.append(self.lab[t])
            if x.name != 'JUMP_TO': work.append(i + 1)
        return seen

    def lastlive(self, t, lo):
        j = t - 1
        while j > lo and j not in self.live: j -= 1
        return j

    def tidx(self, x):
        return self.lab[x.args[-1][5:]] if x.name == 'IF' else self.lab[x.args[0]]

    def resolve(self, t):
        seen = set()
        while t < self.n and self.ins[t].name == 'JUMP_TO' and t not in seen:
            seen.add(t); t = self.lab[self.ins[t].args[0]]
        return t

    def jump(self, start, t, head, exit_):
        """The statement for `goto t` in a loop context."""
        if t > self.n: return St('extgoto', start, label=self.extname[t])
        if head is not None and t == head: return St('continue', start)
        if exit_ is not None and (t == exit_ or self.resolve(t) == self.resolve(exit_)): return St('break', start)
        r = self.resolve(t)
        if r >= self.n or self.ins[r].name == 'END_SECTION': return St('return', start)
        return St('goto', start, target=r)

    def seq(self, lo, hi, head, exit_, eq, skip=None):
        """Statements for ins[lo:hi]. `eq`: the indexes that falling off the end of this block is the same as jumping to."""
        out = []; i = lo
        while i < hi:
            if i not in self.live: i += 1; continue
            x = self.ins[i]; nm = x.name
            if nm == 'END_SECTION' and i not in self.keep and out and flow_ends(out[-1], self.sec) and not self.backs.get(i):
                i += 1; continue                      # only jumps reach it, and they are written `return`
            back = [j for j in self.backs.get(i, []) if lo <= j < hi]
            if back and i != skip:
                j = max(back); E = j + 1
                first = self.ins[i]
                if first.name == 'IF' and self.tidx(first) == E:
                    body = self.seq(i + 1, j, i, E, {j})
                    out.append(St('while', i, cond=first.args[:-1], body=body, pre=[]))
                else:
                    k = i
                    while k < j and self.ins[k].name not in ('IF', 'SET_SELECTION', 'SWITCH', 'SWITCH_W', 'JUMP_AND_LINK') \
                            and self.ins[k].name not in TERMINAL: k += 1
                    if k < j and self.ins[k].name == 'IF' and self.tidx(self.ins[k]) == E and k > i:
                        pre = self.seq(i, k, i, E, {k}, skip=i)
                        body = self.seq(k + 1, j, i, E, {j})
                        out.append(St('while', i, cond=self.ins[k].args[:-1], body=body, pre=pre))
                    else:
                        out.append(St('loop', i, body=self.seq(i, j, i, E, {j}, skip=i)))
                i = E; continue
            if nm == 'IF':
                t = self.tidx(x); cond = x.args[:-1]
                rt = self.resolve(t)
                early = rt < self.n and self.ins[rt].name == 'END_SECTION' and rt not in self.keep and i + 1 < t and t <= hi and \
                    any(self.ins[q].name == 'SET_SELECTION' and any(self.lab[a] > t for a in self.ins[q].args) for q in range(i + 1, t))
                if i + 1 < t and (t < hi or t in eq or (t == hi and hi in eq)) and not early:
                    e = min(t, hi)
                    lt = self.lastlive(e, i)
                    last = self.ins[lt]
                    M = self.lab[last.args[0]] if last.name == 'JUMP_TO' else None
                    if M is not None and t < hi and t < M and (M < hi or M in eq or (M == hi and hi in eq)) and lt > i + 1:
                        e2 = min(M, hi)
                        then = self.seq(i + 1, lt, head, exit_, {lt, M}); els = self.seq(t, e2, head, exit_, {M, e2})
                        out.append(St('if', i, cond=cond, then=then, els=els)); i = e2; continue
                    then = self.seq(i + 1, e, head, exit_, {e, t})
                    out.append(St('if', i, cond=cond, then=then, els=None)); i = e; continue
                # a guard: leaves the block when the condition fails
                j = self.jump(i, t, head, exit_)
                out.append(St('unlessj', i, cond=cond, jump=j)); i += 1; continue
            if nm == 'JUMP_TO':
                t = self.lab[x.args[0]]
                nxt = next((q for q in range(i + 1, hi) if q in self.live), None)
                if (t == i + 1 and (i + 1 < hi or i + 1 in eq)) or (nxt is None and t in eq) or (nxt is not None and t == nxt): pass      # falls to it anyway
                else: out.append(self.jump(i, t, head, exit_))
                i += 1; continue
            if nm == 'END_SECTION':
                out.append(St('return', i)); i += 1; continue
            if nm == 'SET_SELECTION' and self.sec.owner_in[i] != '?':
                ch = self.choice(i, hi, head, exit_, eq)
                if ch is not None:
                    if out and out[-1].kind == 'i' and out[-1].idx == i - 1 and self.ins[i - 1].name == 'SET_DIALOG_OWNER' \
                            and not out[-1].labels:
                        out.pop()
                    out.append(ch[0]); i = ch[1]; continue
            out.append(St('i', i, idx=i)); i += 1
        return out

    def choice_jumps(self, i, hi, head, exit_, eq, ts):
        """A selection whose options all leave the block (they are jumps: `return`, `goto`, `break`): the code after END_SELECTION
        is the cancel path, up to its first jump."""
        if any(t <= i + 2 for t in ts): return None
        f = i + 2
        while f < hi and (f not in self.live or self.ins[f].name not in TERMINAL):
            if f in self.live and self.ins[f].name in ('IF', 'SET_SELECTION', 'SWITCH', 'SWITCH_W', 'JUMP_AND_LINK'): return None
            if f in self.backs: return None
            f += 1
        if f >= hi:
            if hi not in eq: return None                      # the cancel path runs to the end of the block, which leaves it
            f = hi - 1
        opts = [[self.jump(i, t, head, exit_)] for t in ts]
        cancel = self.seq(i + 2, f + 1, head, exit_, set()); also = None
        if len(cancel) == 1 and not cancel[0].labels:
            for k, o in enumerate(opts):
                if same_jump(o[0], cancel[0]): also = k; cancel = []; break
        return St('choice', i, ins=i, opts=list(enumerate(opts)), cancel=cancel, also=also, who=self.sec.owner_in[i]), f + 1

    def choice_tail(self, i, hi, head, exit_, eq, ts, inner):
        """The last option's region is a tail the other options jump or fall into (Kunemon's `declined`): it is written after the
        `choice`, whose options end by leaving the choice (falling out of their block) or by a `goto` to the tail."""
        T = inner[-1]; E = {T}
        def last(a, b): return self.ins[self.lastlive(b, a - 1)]
        for a, b in zip(inner[:-1], inner[1:]):
            if last(a, b).name not in TERMINAL and b != T: return None
        if inner[0] != T and last(i + 2, inner[0]).name not in TERMINAL: return None
        reg = {}
        for a, b in zip(inner[:-1], inner[1:]): reg[a] = self.seq(a, b, head, exit_, E)
        reg[T] = []
        opts = []; used = set()
        for t in ts:
            if t in reg and t not in used: opts.append(reg[t]); used.add(t)
            else: opts.append([self.jump(i, t, head, exit_)])
        cancel = self.seq(i + 2, inner[0], head, exit_, E)
        return St('choice', i, ins=i, opts=list(enumerate(opts)), cancel=cancel, also=None, who=self.sec.owner_in[i]), T

    def choice(self, i, hi, head, exit_, eq):
        """SET_SELECTION at i + END_SELECTION, option bodies as regions in address order. -> (St, index after) or None."""
        x = self.ins[i]; ts = [self.lab[t] for t in x.args]
        if i + 1 >= self.n: return None
        openc = self.ins[i + 1].name != 'END_SELECTION'          # `choice(open)`: no END_SELECTION, the first option follows at once
        if openc and ts[0] != i + 1: return None
        inner = sorted({t for t in ts if i + 1 <= t < hi}) if openc else sorted({t for t in ts if i + 1 < t < hi})
        if not inner and not openc: return self.choice_jumps(i, hi, head, exit_, eq, ts)
        if not inner or (inner[0] < i + 3 and not openc): return None
        T = inner[-1]
        shared = any(j != i and j in self.live and i + 1 < j < T and any(self.lab[q] == T for q in targets(self.ins[j], self.lab)) and self.ins[j].name in ('JUMP_TO', 'IF')
                     for j in range(i + 2, T))
        lt = self.lastlive(T, i + 1)
        if not shared and len(inner) > 1 and self.ins[self.lastlive(T, inner[-2] - 1)].name not in TERMINAL and T == inner[-1]:
            shared = len(inner) > 1                                # the region before the last one falls into it
        if shared and T <= hi and not openc:
            r = self.choice_tail(i, hi, head, exit_, eq, ts, inner)
            if r is not None: return r
        ends = inner[1:] + [None]
        def terminal(a, b):
            l = self.ins[self.lastlive(b, a - 1)]
            return l.name in TERMINAL
        cand = []
        for a, b in zip(inner, ends):
            if b is None: continue
            if not terminal(a, b): return None
            l = self.ins[self.lastlive(b, a - 1)]
            if l.name == 'JUMP_TO' and self.lab[l.args[0]] > inner[-1]: cand.append(self.lab[l.args[0]])
        if not openc:
            if not terminal(i + 2, inner[0]): return None
            cl = self.ins[self.lastlive(inner[0], i + 1)]
            if cl.name == 'JUMP_TO' and self.lab[cl.args[0]] > inner[-1]: cand.append(self.lab[cl.args[0]])
        J = max(cand) if cand else hi
        if J > hi or J <= inner[-1] or (J == hi and hi not in eq and J not in eq) or (J < hi and False): return None
        if J > hi: return None
        if J < hi or J in eq: pass
        else: return None
        reg = {}
        for a, b in zip(inner, ends):
            reg[a] = self.seq(a, b if b is not None else J, head, exit_, {J})
        opts = []; used = set()
        for t in ts:
            if t in reg and t not in used: opts.append(reg[t]); used.add(t)
            else: opts.append([self.jump(i, t, head, exit_)])
        cancel = [] if openc else self.seq(i + 2, inner[0], head, exit_, {J}); also = None
        if len(cancel) == 1 and cancel[0].kind == 'goto' and not cancel[0].labels:       # the same as one of the options
            for k, t in enumerate(ts):
                if t in reg and self.resolve(t) == cancel[0].target and opts[k] is reg[t]: also = k; cancel = []; break
        return St('choice', i, ins=i, opts=list(enumerate(opts)), cancel=cancel, also=also, who=self.sec.owner_in[i], openc=openc), J


def children(s):
    """The statement lists inside a statement."""
    out = []
    for f in ('pre', 'then', 'els', 'body', 'cancel'):
        v = getattr(s, f, None)
        if isinstance(v, list): out.append(v)
    if s.kind == 'choice': out += [ob for _, ob in s.opts]
    if s.kind == 'switch': out += [ob for _, ob in s.arms]
    return out


def flow_ends(s, sec):
    """True if control never continues after the statement."""
    k = s.kind
    if k in ('return', 'goto', 'extgoto', 'break', 'continue'): return True
    if k == 'i': return sec.ins[s.idx].name in ('END_SECTION', 'END_SCRIPT', 'JUMP_RETURN', 'JUMP_TO_FILE')
    if k == 'if': return s.els is not None and bool(s.then) and bool(s.els) and flow_ends(s.then[-1], sec) and flow_ends(s.els[-1], sec)
    return False


def loop_exit(stmts, inside=False):
    """True if the statements hold a `break`/`continue` that belongs to a loop outside them."""
    for s in stmts:
        if s.kind in ('break', 'continue') and not inside: return True
        if s.kind == 'unlessj' and s.jump.kind in ('break', 'continue') and not inside: return True
        for c in children(s):
            if loop_exit(c, inside or s.kind in ('while', 'loop')): return True
    return False


def descendants(stmts):
    out = []
    for s in stmts:
        out.append(s)
        for c in children(s): out += descendants(c)
    return out


def first_at(entries, p):
    """(block, position, statement) of the statement a label at instruction p is placed on (the first one that starts at or after it)."""
    cands = [e for e in entries if e[2].start >= p]
    if not cands: return None
    m = min(e[2].start for e in cands)
    return next(e for e in cands if e[2].start == m)


def peephole(root, sec):
    """`if (c) { goto L; } return; L: ...` is `unless (c) return;` (the same for `break` and `continue`)."""
    for _ in range(500):
        entries = []
        def walk(b):
            for k, s in enumerate(b):
                entries.append((b, k, s))
                for c in children(s): walk(c)
        walk(root)
        hit = False
        for b, k, s in entries:
            if s.kind != 'if' or s.els is not None or len(s.then) != 1 or s.labels or s.then[0].kind != 'goto' or k + 2 >= len(b): continue
            j = b[k + 1]
            if j.kind not in ('return', 'break', 'continue') or j.labels: continue
            t = first_at(entries, s.then[0].target)
            if t is None or t[2] is not b[k + 2]: continue
            b[k:k + 2] = [St('unlessj', s.start, cond=s.cond, jump=j)]; hit = True; break
        if not hit: break


def inline_tails(root, sec, max_len=2):
    """A `goto` to a short run of plain statements that ends the section (`warp_to(..); return;`) is that run (a copy); a run
    nothing else reaches is moved to its only `goto`. Fewer labels, no change of behaviour (the proof checks it anyway)."""
    import copy
    for _ in range(200):
        entries = []
        def walk(b):
            for k, s in enumerate(b):
                entries.append((b, k, s))
                for c in children(s): walk(c)
        walk(root)
        refs = {}; other = set()
        for b, k, s in entries:
            if s.kind == 'goto': refs.setdefault(s.target, []).append((b, k, s))
            elif s.kind == 'unlessj' and s.jump.kind == 'goto': other.add(s.jump.target)
            elif s.kind == 'i' and sec.ins[s.idx].name in ('JUMP_AND_LINK', 'SWITCH', 'SWITCH_W', 'SET_SELECTION', 'JUMP_TO', 'IF'):
                other.update(sec.labels[t] for t in targets(sec.ins[s.idx], sec.labels))
            elif s.kind == 'choice': other.update(sec.labels[t] for t in sec.ins[s.ins].args)
        done = False
        for p, rl in sorted(refs.items()):
            if p in other: continue
            cands = [(b, k, s) for b, k, s in entries if s.start >= p]
            if not cands: continue
            m = min(s.start for _, _, s in cands); b, pos, first = next(e for e in cands if e[2].start == m)
            e = next((q for q in range(pos, len(b)) if flow_ends(b[q], sec)), None)
            if e is None and b is not root: continue
            run = b[pos:] if e is None else b[pos:e + 1]
            if not run: continue
            if len(rl) == 1 and pos > 0 and flow_ends(b[pos - 1], sec) and not loop_exit(run) and rl[0][2] not in descendants(run) \
                    and not any(x.kind == 'i' and sec.ins[x.idx].name in ('JUMP_AND_LINK', 'SWITCH', 'SWITCH_W', 'SET_SELECTION', 'JUMP_TO', 'IF') for x in descendants(run)):
                rb, rk, rs = rl[0]
                mv = list(run) + ([] if flow_ends(run[-1], sec) else [St('return', rs.start)])
                del b[pos:pos + len(run)]                         # first out of its place, then into the goto's
                at = rb.index(rs); rb[at:at + 1] = mv; done = True; break
            if any(s.kind not in ('i', 'return') for s in run) or run[0] in [r[2] for r in rl]: continue
            if any(x.kind == 'i' and sec.ins[x.idx].name in ('JUMP_AND_LINK', 'SWITCH', 'SWITCH_W', 'SET_SELECTION', 'JUMP_TO', 'IF') for x in run): continue
            n = len([x for x in run if x.kind != 'return'])
            if n > max_len and len(rl) > 1: continue
            if any(q != p and run[0].start < q <= run[-1].start for q in refs): continue          # another goto lands inside the run
            if any(q != p and run[0].start < q <= run[-1].start for q in other): continue
            for rb, rk, rs in rl:
                at = rb.index(rs); cp = []
                for x in run:
                    y = copy.copy(x); y.start = rs.start; y.labels = []; cp.append(y)
                if not flow_ends(run[-1], sec): cp.append(St('return', rs.start))
                rb[at:at + 1] = cp
            pos = b.index(first)
            if pos > 0 and flow_ends(b[pos - 1], sec): del b[pos:pos + len(run)]
            done = True; break
        if not done: break
    return root


def sink_gotos(root, sec):
    """Fewer `goto`s by moving code into a branch. `if (c) { ...; goto L; } REST` where REST never falls through (it ends in a
    return) is `if (c) { ...; goto L; } else { REST }` (also with the goto in the else branch and REST moved into the then
    branch); then a `goto L` that ends a branch whose falling off would reach L anyway is dropped. Only sections with gotos."""
    def entries():
        out = []
        def walk(b, parent):
            for k, s in enumerate(b):
                out.append((b, k, s, parent))
                for c in children(s): walk(c, (b, k, s))
        walk(root, None)
        return out
    def ends_goto(b): return bool(b) and b[-1].kind == 'goto'
    def falls(b): return not b or not flow_ends(b[-1], sec)
    for _ in range(200):
        es = entries()
        if not any(s.kind == 'goto' for _, _, s, _ in es): return
        targets_at = {s.target for _, _, s, _ in es if s.kind == 'goto'} | {s.jump.target for _, _, s, _ in es if s.kind == 'unlessj' and s.jump.kind == 'goto'}
        hit = False; flat = [(b, q, x) for b, q, x, _ in es]
        for b, k, s, _ in es:
            if s.kind != 'if' or k + 1 >= len(b): continue
            rest = b[k + 1:]
            if not flow_ends(rest[-1], sec) or any(x.kind in ('break', 'continue') for x in descendants(rest)): continue
            inside = set(map(id, descendants(rest)))
            if any(id(t[2]) in inside for t in (first_at(flat, p) for p in targets_at) if t is not None): continue   # a goto lands in it
            if ends_goto(s.then) and (s.els is None or falls(s.els)):
                s.els = (s.els or []) + rest
            elif s.els is not None and ends_goto(s.els) and falls(s.then):
                s.then = s.then + rest
            else: continue
            del b[k + 1:]; hit = True; break
        if hit: continue
        # a goto that ends a branch: falling off would go to the statement after the enclosing if/choice (not out of a loop)
        for b, k, s, parent in es:
            if s.kind != 'goto' or k != len(b) - 1: continue
            t = first_at(flat, s.target)
            up = parent; nxt = None
            while up is not None:
                pb, pk, ps = up
                if ps.kind not in ('if', 'choice'): break
                if pk + 1 < len(pb): nxt = pb[pk + 1]; break
                up = next((p for bb, kk, x, p in es if x is ps), None)
            if nxt is not None and t is not None and t[2] is nxt:
                del b[k]; hit = True; break
        if not hit: return


def negate_clauses(cond):
    """The IF clauses of `not cond` (De Morgan over the engine's left fold: each join flips, each test is negated)."""
    out = []
    for c in cond:
        j, _, t = c.partition(' ') if c.startswith(('and ', 'or ')) else ('', '', c)
        if t.startswith('not '): t = t[4:]
        elif re.fullmatch(r'(trigger|cond|move) \S+', t): t = 'not ' + t
        else:
            m = re.fullmatch(r'(.*) (==|!=|<=|>=|<|>) (\S+)', t)
            if not m: return None
            t = f'{m.group(1)} {flowcmp.FLIP.get(m.group(2)) or {v: k for k, v in flowcmp.FLIP.items()}[m.group(2)]} {m.group(3)}'
        out.append(({'and': 'or ', 'or': 'and '}[j] if j else '') + t)
    return out


def guards(root):
    """`if (c) { return; }` (or break, continue, goto) is `unless (!c) return;`: one IF that jumps, the form the view prints as
    `if c: return` (and the smaller code); `if (c) { } else { X }` is `if (!c) { X }`. Every such if of the section."""
    def walk(b):
        for k, s in enumerate(b):
            if s.kind == 'if' and not s.then and s.els and not any(x.labels for x in s.els[:1]) \
                    and not (len(s.els) == 1 and s.els[0].kind == 'if'):     # if (c) { } else { X }  ->  if (!c) { X } (an else-if chain stays)
                neg = negate_clauses(s.cond)
                if neg is not None: s.cond, s.then, s.els = neg, s.els, None
            if s.kind == 'if' and not s.els and len(s.then) == 1 and not s.then[0].labels \
                    and s.then[0].kind in ('return', 'goto', 'extgoto', 'break', 'continue'):
                neg = negate_clauses(s.cond)
                if neg is not None:
                    g = St('unlessj', s.start, cond=neg, jump=s.then[0]); g.labels = s.labels; b[k] = g; continue
            for c in children(s): walk(c)
    walk(root)


def same_jump(a, b):
    if a.kind != b.kind: return False
    return a.kind in ('return', 'break', 'continue') or (a.kind == 'goto' and a.target == b.target) or (a.kind == 'extgoto' and a.label == b.label)


def place_labels(root, struct, sec):
    """Attaches the names of the needed labels to the first statement that starts at or after their index."""
    flat = []
    def walk(b):
        for s in b:
            flat.append(s)
            for f in ('pre', 'then', 'els', 'body', 'cancel'):
                v = getattr(s, f, None)
                if isinstance(v, list): walk(v)
            if s.kind == 'choice':
                for _, ob in s.opts: walk(ob)
    walk(root)
    # order of emission = order of start
    need = set(); raw = set()
    for s in flat:
        if s.kind == 'goto': need.add(s.target)
        elif s.kind == 'unlessj' and s.jump.kind == 'goto': need.add(s.jump.target)
        elif s.kind == 'i' and sec.ins[s.idx].name in ('JUMP_AND_LINK', 'SWITCH', 'SWITCH_W', 'SET_SELECTION', 'JUMP_TO', 'IF'):
            need.update(sec.labels[t] for t in targets(sec.ins[s.idx], sec.labels) if sec.labels[t] <= len(sec.ins))
            raw.update(sec.labels[t] for t in targets(sec.ins[s.idx], sec.labels))
        elif s.kind == 'choice' and getattr(s, 'also', None) is not None: pass
    end = []; order = {}
    need = sorted(need)
    forward = {p: p not in raw and all(s.start < p for s in flat if (s.kind == 'goto' and s.target == p) or (s.kind == 'unlessj' and s.jump.kind == 'goto' and s.jump.target == p)) for p in need}
    for p in need:
        # first statement in emission order whose start >= p (flat is in emission order, starts are non-decreasing)
        cands = [s for s in flat if s.start >= p]
        tgt = min(cands, key=lambda s: s.start) if cands else None
        order[p] = (f'tail{len(order) + 1}' if forward[p] and all(forward.values()) else f'l{len(order) + 1}')
        (tgt.labels if tgt is not None else end).append(order[p])
    return order, end


# ------------------------------------------------------------------------------------------------ printing
SAY_WIDTH = 108


class Printer:
    def __init__(self, sec, st, labmap, endlabels, names, level, sid, kind):
        self.sec = sec; self.st = st; self.lm = labmap; self.end = endlabels; self.names = names; self.level = level
        self.sid = sid; self.kind = kind; self.lines = []; self.used_npc = set(); self.sugar = level >= 2
        decomp.ENT_HOOK = self.ent if self.sugar else None
        decomp.NAME_HOOK = names if self.sugar else None
        self.cache = {}

    # --- entities
    def ent(self, a):
        if a == 'TAMER': return 'tamer'
        if a == 'PARTNER': return 'partner'
        if a == '255': return 'narrator'
        if a == '200': return 'camera'
        if a.isdigit() and 5 <= int(a) <= 12:
            self.used_npc.add(int(a)); return self.names_npc(int(a))
        if a.isdigit(): return f'entity({a})'
        return a

    def names_npc(self, n):
        return self.names.npc_name(self.sid, n)

    # --- one raw instruction as a typed statement
    def raw(self, idx):
        x = self.sec.ins[idx]
        if x.name in ('JUMP_TO', 'JUMP_AND_LINK', 'IF', 'SET_SELECTION', 'SWITCH', 'SWITCH_W'):
            x = self.relabel(x)
        s = decomp.lift(x, self.sec.keys[idx])
        return s

    def relabel(self, x):
        import copy
        y = copy.copy(x); n = x.name
        m = lambda t: f'original({t})' if self.sec.labels[t] > len(self.sec.ins) else self.lm.get(self.sec.labels[t], t)
        if n in ('JUMP_TO', 'JUMP_AND_LINK'): y.args = [m(x.args[0])]
        elif n == 'IF': y.args = list(x.args[:-1]) + ['else ' + m(x.args[-1][5:])]
        elif n == 'SET_SELECTION': y.args = [m(t) for t in x.args]
        else: y.args = [x.args[0]] + [m(t) for t in x.args[1:]]
        return y

    def cond(self, clauses, at=None):
        parts = []; i = 0
        battle = self.level >= 3 and at is not None and any(x.name == 'START_BATTLE' for x in self.sec.ins[:at])
        # after the item picker (CALL_ROUTINE 0) p254 holds an item id (255: nothing chosen): the numbers it is compared with are items
        picked = self.level >= 3 and at is not None and any(x.name == 'CALL_ROUTINE' and x.args == ['0'] for x in self.sec.ins[:at])
        def num(var, v):
            if picked and var == 'p254' and v.isdigit() and int(v) != 255: return decomp.namer().typed('item', int(v))
            return v
        while i < len(clauses):
            c = clauses[i]
            m = re.fullmatch(r'(?:(and|or) )?(p\d+) == (\d+)', c) if self.sugar else None
            if m and m.group(1) in (None, 'or'):
                j = i + 1; vals = [num(m.group(2), m.group(3))]
                while j < len(clauses):
                    m2 = re.fullmatch(r'or (p\d+) == (\d+)', clauses[j])
                    if not (m2 and m2.group(1) == m.group(2)): break
                    vals.append(num(m2.group(1), m2.group(2))); j += 1
                if len(vals) >= 2:
                    parts.append(('||' if m.group(1) == 'or' else None, f'{self.names.var(m.group(2))} in [{", ".join(vals)}]'))
                    i = j; continue
            mb = re.fullmatch(r'(?:(and|or) )?p255 (==|!=) (0|1|255)', c) if battle else None
            if mb:
                word = {'1': 'won', '255': 'lost', '0': 'fled'}[mb.group(3)]
                parts.append(({'and': '&&', 'or': '||'}.get(mb.group(1)), ('!' if mb.group(2) == '!=' else '') + word)); i += 1; continue
            mi = re.fullmatch(r'(?:(and|or) )?(p254) (==|!=) (\d+)', c) if picked else None
            if mi and int(mi.group(4)) != 255:
                parts.append(({'and': '&&', 'or': '||'}.get(mi.group(1)), f'{self.names.var(mi.group(2))} {mi.group(3)} {num("p254", mi.group(4))}')); i += 1; continue
            parts.append(decomp.clause(c)); i += 1
        cur = None; curop = None
        for join, s in parts:
            if cur is None: cur = s; continue
            if join is None: join = '~>'
            if curop is None or curop == join: cur = f'{cur} {join} {s}'
            else: cur = f'({cur}) {join} {s}'
            curop = join
        return cur

    # --- output
    def emit(self, indent, s):
        self.lines.append('    ' * indent + s)

    def block(self, stmts, indent, tail=None):
        n = len(stmts); k = 0
        runs = []; skip = 0
        for k, s in enumerate(stmts):
            if skip: skip -= 1; continue
            if isinstance(s, St) and s.kind == 'while' and s.pre and self.level >= 3:
                m = self.walk_away_match(s, stmts[k + 1] if k + 1 < len(stmts) else None)
                if m:
                    if s.labels:
                        self.flush(runs, indent); runs = []
                        for l in s.labels: self.emit(indent, l + ':')
                    self.flush(runs, indent); runs = []
                    w, x, z, looks, pause = m
                    self.names.used.add('walk_away'); self.names.used.add('glances')
                    self.emit(indent, f'walk_away({w}, {x}, {z}, looks: {looks}' + ('' if pause == 20 else f', pause: {pause}') + ');')
                    skip = 1; continue
            if isinstance(s, St) and s.labels:
                self.flush(runs, indent); runs = []
                for l in s.labels: self.emit(indent, l + ':')
            if isinstance(s, St) and s.kind == 'i':
                runs.append(s); continue
            self.flush(runs, indent); runs = []
            self.stmt(s, indent)
        self.flush(runs, indent)

    def stmt(self, s, indent):
        k = s.kind; e = lambda t: self.emit(indent, t)
        if k == 'if':
            self.emit_if(s, indent, 'if')
        elif k == 'while':
            c = self.cond(s.cond, s.start)
            if not s.pre:
                e(f'while ({c}) {{'); self.block(s.body, indent + 1); e('}')
            else:
                e('loop {'); self.block(s.pre, indent + 1)
                self.emit(indent + 1, f'unless ({c}) break;'); self.block(s.body, indent + 1); e('}')
        elif k == 'loop':
            e('loop {'); self.block(s.body, indent + 1); e('}')
        elif k == 'choice': self.emit_choice(s, indent)
        elif k == 'switch':
            e(f'match ({self.names.var(s.var)}, clamp) {{')
            for q, body in s.arms:
                if not body: self.emit(indent + 1, f'{q} => {{}}'); continue
                self.emit(indent + 1, f'{q} => {{'); self.block(body, indent + 2); self.emit(indent + 1, '}')
            e('}')
        elif k == 'goto': e(f'goto {self.lm[s.target]};')
        elif k == 'extgoto': e(f'goto original({s.label});')
        elif k == 'break': e('break;')
        elif k == 'continue': e('continue;')
        elif k == 'return': e('return;')
        elif k == 'unlessj':
            c = self.cond(s.cond, s.start); j = s.jump
            if j.kind == 'goto': e(f'unless ({c}) goto {self.lm[j.target]};')
            elif j.kind == 'extgoto': e(f'unless ({c}) goto original({j.label});')
            else: e(f'unless ({c}) {j.kind};')

    def emit_if(self, s, indent, word):
        c = self.cond(s.cond, s.start)
        self.emit(indent, f'{word} ({c}) {{'); self.block(s.then, indent + 1)
        els = s.els
        if els is None: self.emit(indent, '}'); return
        if len(els) == 1 and isinstance(els[0], St) and els[0].kind == 'if' and not els[0].labels:
            self.lines.append('    ' * indent + '} else')
            self.lines[-1] += ' '; self.chain(els[0], indent)
        else:
            self.emit(indent, '} else {'); self.block(els, indent + 1); self.emit(indent, '}')

    def chain(self, s, indent):
        n0 = len(self.lines)
        self.emit_if(s, indent, 'if')
        first = self.lines[n0].lstrip(); self.lines[n0 - 1] += first; del self.lines[n0]

    def emit_choice(self, s, indent):
        op = getattr(s, 'openc', False)
        args = (['keep'] if s.who == '?' else [] if s.who == 'TAMER' else [self.ent(s.who)]) + (['open'] if op else [])
        self.emit(indent, 'choice' + (f'({", ".join(args)})' if args else '') + ' {')
        x = self.sec.ins[s.ins]
        keys = self.sec.keys[s.ins]
        for (k, body), key in zip(s.opts, keys):
            head = f'text("{key}")' + (' or cancel' if s.also == k else '') + ' => {'
            if not body: self.emit(indent + 1, head + '}'); continue
            self.emit(indent + 1, head); self.block(body, indent + 2); self.emit(indent + 1, '}')
        if s.cancel:
            self.emit(indent + 1, 'cancel => {'); self.block(s.cancel, indent + 2); self.emit(indent + 1, '}')
        elif getattr(s, 'cancel_empty', False): self.emit(indent + 1, 'cancel => {}')
        self.emit(indent, '}')

    # --- runs of plain instructions
    def flush(self, runs, indent):
        if not runs: return
        idxs = [s.idx for s in runs]; ins = self.sec.ins
        k = 0
        while k < len(idxs):
            r = self.sugar_at(idxs, k, indent)
            if r is None:
                st = self.raw(idxs[k]); k += 1
                if st is not None: self.emit(indent, st)          # None: a page the utterance's first page already gives
            else:
                k = r

    def utterance(self, idxs):
        """`text("key")` of the utterance the SHOW_TEXTBOX run idxs is: the run must be the whole utterance (textx.Keyer)."""
        ks = self.sec.keys; i, j = idxs[0], idxs[-1]
        if not ks[i] or any(ks[x] for x in idxs[1:]) or (j + 1 < len(ks) and self.sec.ins[j + 1].name == 'SHOW_TEXTBOX' and not ks[j + 1]):
            raise ValueError('a say that is not one whole utterance')
        return f'text("{ks[i][0]}")'

    def say(self, who, idxs, indent):
        self.emit(indent, f'say({who}, {self.utterance(idxs)});')

    def sugar_at(self, idxs, k, indent):
        """Emits the sugar statement that starts at idxs[k]; returns the next k, or None for no sugar."""
        if not self.sugar: return None
        ins = self.sec.ins; i = idxs[k]; x = ins[i]; nm = x.name

        def same(j, name, args=None):       # idxs[j] is that instruction (and consecutive in the original)
            return j < len(idxs) and idxs[j] == i + (j - k) and ins[idxs[j]].name == name and (args is None or ins[idxs[j]].args == args)
        # dialogue
        if nm == 'SET_DIALOG_OWNER' and same(k + 1, 'SHOW_TEXTBOX'):
            j = k + 1
            while same(j, 'SHOW_TEXTBOX'): j += 1
            self.say(self.ent(x.args[0]), idxs[k + 1:j], indent); return j
        if nm == 'SHOW_TEXTBOX' and self.sec.owner_in[i] not in ('?',):
            j = k
            while same(j, 'SHOW_TEXTBOX'): j += 1
            self.say(self.ent(self.sec.owner_in[i]), idxs[k:j], indent); return j
        if self.level >= 3:
            r = self.sugar3(idxs, k, indent, same)
            if r is not None: return r
        # one to one
        s = self.one(x)
        if s is not None: self.emit(indent, s); return k + 1
        return None

    def sugar3(self, idxs, k, indent, same):
        ins = self.sec.ins; i = idxs[k]; x = ins[i]
        # battle(): FADEOUT_HUD 0, DELAY 1, START_BATTLE 0   (with predefined foes: SET_TRIGGER 1? , p250 = 1, p251..253, ...)
        j = k; noesc = False
        if same(j, 'SET_TRIGGER', ['1']): noesc = True; j += 1
        if same(j, 'SET_PSTAT', ['p250', '1']) and same(j + 1, 'SET_PSTAT') and same(j + 2, 'SET_PSTAT') and same(j + 3, 'SET_PSTAT') and \
                [ins[idxs[j + q]].args[0] for q in (1, 2, 3)] == ['p251', 'p252', 'p253'] and same(j + 4, 'FADEOUT_HUD', ['0']) and \
                same(j + 5, 'DELAY', ['1']) and same(j + 6, 'START_BATTLE', ['0']):
            e = j + 7
            ok = True
            if noesc:
                ok = same(e, 'UNSET_TRIGGER', ['1']); e += 1
            if ok and same(e, 'SET_PSTAT', ['p250', '0']):
                foes = [ins[idxs[j + q]].args[1] for q in (1, 2, 3)]
                while foes and foes[-1] == '255': foes.pop()
                if foes and all(f != '255' for f in foes):
                    fs = ', '.join(self.ent(f) if f.isdigit() else f for f in foes)
                    self.emit(indent, f'battle(foes: [{fs}]{"" if noesc else ", escape: true"});'); return e + 1
        if x.name == 'UNLOAD_ENTITY' and same(k + 1, 'SET_PSTAT', ['p101', '0']) and same(k + 2, 'PLAY_SOUND') and \
                same(k + 3, 'SET_DIALOG_OWNER', ['255']) and same(k + 4, 'SHOW_TEXTBOX'):
            j = k + 5; cam = False
            if same(j, 'MOVE_CAMERA_TO_ENTITY', ['TAMER', '10']) and same(j + 1, 'WAIT_FOR_ENTITY', ['200']): cam = True; j += 2
            if same(j, 'SET_TRIGGER') and RECRUIT_BASE <= int(ins[idxs[j]].args[0]) < RECRUIT_BASE + RECRUIT_N and same(j + 1, 'ADD_TO_PSTAT') \
                    and ins[idxs[j + 1]].args[0] == 'p1':
                sp = decomp.namer().typed('species', int(ins[idxs[j]].args[0]) - RECRUIT_BASE)
                snd = ins[idxs[k + 2]].args; pr = ins[idxs[j + 1]].args[1]
                self.names.used.update(('join_city_camera' if cam else 'join_city', 'glances', 'engine.prosperity'))
                self.emit(indent, f'{"join_city_camera" if cam else "join_city"}({self.ent(x.args[0])}, {sp}, {snd[0]}, {snd[1]}, '
                                  f'{self.utterance([idxs[k + 4]])}' + ('' if pr == '1' else f', prosperity: {pr}') + ');')
                return j + 2
        if same(k, 'FADEOUT_HUD', ['0']) and same(k + 1, 'DELAY', ['1']) and same(k + 2, 'START_BATTLE', ['0']):
            self.emit(indent, 'battle();'); return k + 3
        return None

    def one(self, x):
        n = x.name; a = x.args; e = self.ent
        if n == 'PLAY_ANIMATION':
            kind = {'TAMER': 'tamer', 'PARTNER': 'partner'}.get(a[0], 'npc' if a[0].isdigit() and 5 <= int(a[0]) <= 12 else None)
            an = anims.name_of(kind, int(a[1])) if kind and a[1].isdigit() else None
            if an: self.names.used.add('anim'); return f'animate({e(a[0])}, anim.{an});'
            hint = anims.HINTS.get((kind, int(a[1]))) if kind and a[1].isdigit() else None
            return f'animate({e(a[0])}, {a[1]});' + (f'    // slot {a[1]}: {hint}' if hint else '')
        if n == 'ENTITY_LOOK_AT_ENTITY': return f'face({e(a[0])}, {e(a[1])});'
        if n == 'DELAY':
            v = int(a[0]); return f'wait({v // 20}s);' if v >= 20 and v % 20 == 0 else f'wait({v});'
        if n in ('ENTITY_WALK_TO', 'ENTITY_WALK_TO_WITH_CAMERA') and len(a) == 5 and a[4] == '0' and a[3] in ('0', '1'):
            f = 'run' if a[3] == '1' else 'walk'
            return f'{f}({e(a[0])}, {a[1]}, {a[2]}' + (', camera: true' if n.endswith('CAMERA') else '') + ');'
        if n == 'WAIT_FOR_ENTITY': return f'await {e(a[0])};'
        if n == 'UNLOAD_ENTITY': return f'remove({e(a[0])});'
        if n == 'MOVE_CAMERA_TO_ENTITY': return f'camera_on({e(a[0])}, speed: {a[1]});'
        if n == 'MOVE_CAMERA_TO': return f'camera_to({a[1]}, {a[2]}, speed: {a[0]});'
        if n == 'PLAY_SOUND': return f'sound({a[0]}, {a[1]});'
        if n == 'ADD_MONEY': return f'give_bits({a[0]});'
        if n == 'REDUCE_MONEY': return f'take_bits({a[0]});'
        if n == 'ADD_MERIT': return f'merit({a[0]});'
        if n in ('SET_TRIGGER', 'UNSET_TRIGGER'):
            t = int(a[0]); on = n == 'SET_TRIGGER'
            if on and RECRUIT_BASE <= t < RECRUIT_BASE + RECRUIT_N and self.level >= 3:
                return f'recruit({decomp.namer().typed("species", t - RECRUIT_BASE)});'
            if not on and RECRUIT_BASE <= t < RECRUIT_BASE + RECRUIT_N and self.level >= 3:
                return f'unrecruit({decomp.namer().typed("species", t - RECRUIT_BASE)});'
            nm = self.names.flags.get(t)
            if nm: self.names.used.add(nm); return f'{nm} = {"true" if on else "false"};'
            return None
        if n in ('SET_PSTAT', 'ADD_TO_PSTAT', 'REDUCE_PSTAT'):
            nm = self.names.var(a[0])
            if nm != a[0]: return f'{nm} {"=" if n == "SET_PSTAT" else "+=" if n == "ADD_TO_PSTAT" else "-="} {a[1]};'
        return None

    def walk_away_match(self, s, nxt):
        """`walk away looking back`: run, then `looks` times turn to watch, then wait for arrival (55 loops in the original)."""
        ins = self.sec.ins
        def plain(t, name): return isinstance(t, St) and t.kind == 'i' and not t.labels and ins[t.idx].name == name
        if len(s.pre) != 1 or not plain(s.pre[0], 'ENTITY_WALK_TO'): return None
        w = ins[s.pre[0].idx].args
        if len(w) != 5 or w[3] != '1' or w[4] != '0' or len(s.cond) != 1 or len(s.body) != 4: return None
        m = re.fullmatch(r'p101 < (\d+)', s.cond[0])
        b = s.body
        if not m or not (plain(b[0], 'ADD_TO_PSTAT') and plain(b[1], 'DELAY') and plain(b[2], 'ENTITY_LOOK_AT_ENTITY') and
                         plain(b[3], 'ENTITY_LOOK_AT_ENTITY') and plain(nxt, 'WAIT_FOR_ENTITY')): return None
        if ins[b[0].idx].args != ['p101', '1'] or ins[b[2].idx].args != ['TAMER', w[0]] or ins[b[3].idx].args != ['PARTNER', w[0]]: return None
        if ins[nxt.idx].args != [w[0]] or s.labels: return None
        return self.ent(w[0]), w[1], w[2], m.group(1), int(ins[b[1].idx].args[0])


def render(sec, level, names, sid, kind, mode='seq', sink=False):
    """-> (body lines, npc numbers used, labels left (count), names used) of the section at a level."""
    names.used = set()
    if level == 0:
        pr = Printer(sec, None, {}, [], names, 0, sid, kind)
        used = {}
        for x in sec.ins:
            for t in targets(x, sec.labels):
                if sec.labels[t] <= len(sec.ins): used[sec.labels[t]] = True
        lm = {}
        for p in sorted(used): lm[p] = f'l{len(lm) + 1}'
        pr.lm = lm
        at = {}
        for nm, idx in sec.labels.items(): at.setdefault(idx, []).append(nm)
        sh = getattr(sec, 'shared_at', None) or {}
        for i, x in enumerate(sec.ins):
            if i in sh: pr.emit(1, f'shared {sh[i]}:')       # a row a jump table of another section points to
            if i in lm: pr.emit(1, lm[i] + ':')
            st = pr.raw(i)
            if st is not None: pr.emit(1, st)      # None: a page the utterance's first page already gives
        if len(sec.ins) in lm: pr.emit(1, lm[len(sec.ins)] + ':')
        return pr.lines, set(), len(lm), names.used
    owner_flow(sec)
    stt = Structurer(sec)
    if mode == 'unfold':
        from . import unfold
        tree = unfold.unfold_tree(sec)
    else:
        tree = stt.seq(0, len(sec.ins), None, None, {len(sec.ins)})
        if tree and tree[-1].kind == 'return' and sec.ins[-1].name == 'END_SECTION' and not tree[-1].labels:
            tree.pop()
        peephole(tree, sec); inline_tails(tree, sec)
        if sink: sink_gotos(tree, sec)
    guards(tree)
    lm, end = place_labels(tree, stt, sec)
    inv = {p: n for p, n in lm.items()}
    pr = Printer(sec, tree, inv, end, names, level, sid, kind)
    pr.block(tree, 1)
    for l in end: pr.emit(1, l + ':')
    return pr.lines, pr.used_npc, len(lm), set(names.used)


# ------------------------------------------------------------------------------------------------ proof
class Lifted:
    def __init__(self, sec, kind, sid):
        self.sec = sec; self.kind = kind; self.sid = sid; self.level = None; self.body = []; self.npcs = set()
        self.imports = []; self.reason = None; self.gotos = 0; self.why = {}; self.same_layout = False; self.extra = set(); self.shared_exit = False

    @property
    def status(self):
        if self.level is None: return 'port-only'
        if self.level == 0: return 'literal'
        return 'readable' if self.gotos == 0 else 'shared-exit' if self.shared_exit else 'partial'


def _header(imports, npcs, names, sid, kind, body, sec_no=1, hdr='section(1) replace'):
    lines = [f'import "{p}";' for p in imports]
    lines.append('maphead {' if kind == 'maphead' else f'script {sid} {{')
    for n in sorted(npcs): lines.append(f'    npc {names.npc_name(sid, n)} = {n};')
    lines.append(f'    {hdr} {{')
    lines += ['    ' + l for l in body]
    lines += ['    }', '}', '']
    return '\n'.join(lines)


def verify(lf, body, npcs, imports, names, tmp):
    """Compiles the body as an event and compares its control flow with the original section. -> (ok, why)"""
    sid = lf.sid
    src = _header(imports, npcs, names, lf.sid, lf.kind, body, hdr=f'section({lf.sec.sid if lf.kind == "maphead" and lf.sec.sid is not None else 1}) replace')
    path = os.path.join(tmp, 'v.dws'); open(path, 'w', encoding='utf-8').write(src)
    try:
        prog = B.compile_sources([path])
        sec, rep, code, ents, p = prog.b.mh_events[0] if lf.kind == 'maphead' else prog.b.scripts[sid]['events'][0]
        got = prog.b.gen_event(sec, rep, code, ents, p)
        r = flowcmp.compare(lf.sec.lines, got); lf._got = got
    except B.DwsErrors as e:
        return False, 'compile: ' + (e.errors[0].message if e.errors and hasattr(e.errors[0], 'message') else str(e.errors[:1]))
    except (DwsError, ValueError, KeyError, IndexError, RecursionError) as e:
        return False, f'{type(e).__name__}: {e}'
    lf.same_layout = flowcmp.same_layout(lf.sec.lines, got) if r['equal'] else False
    return (True, '') if r['equal'] else (False, 'not bisimilar')


def shared_exit(body, nlab):
    """One label that only forward `goto`s reach (a shared exit or tail, like Kunemon's `declined:`), and no raw jump statement."""
    if nlab != 1: return False
    t = '\n'.join(body)
    if re.search(r'\bgosub (?!original)|\bswitch\(|\bset_selection\(', t): return False
    pos = [k for k, l in enumerate(body) if re.fullmatch(r'\s*tail\d+:', l)]
    refs = [k for k, l in enumerate(body) if re.search(r'\bgoto tail\d+;', l)]
    return len(pos) == 1 and bool(refs) and all(k < pos[0] for k in refs)


def snapshot(sec):
    """A copy of a section that standalone() can prepare without touching the original."""
    import copy
    out = copy.copy(sec); out.ins = list(sec.ins); out.keys = list(sec.keys); out.labels = dict(sec.labels)
    out.lines = list(sec.lines); out.ext = list(sec.ext)
    return out


def merge_ifs(sec):
    """A copy of the section whose condition tests split over two IFs are one IF, or None (nothing to merge). Two shapes:
    `IF a, else L; IF b, else L` -> `IF a, and b, else L` (b only `and`s), and `IF a, else L1; T; L1: IF b, else L2; T` with the
    same straight then-code T ending in a jump -> `IF a, or b, else L2; T` (b only `or`s). The engine folds the clauses left to
    right, so these are the same tests in the same order (flowcmp, one node per clause, proves it). Tried only on a section that
    keeps labels otherwise: it is what makes Kunemon (2:6) and Jijimon (178:5) structured."""
    from dws.bytecode import Instr
    at = {}
    for nm, i in sec.labels.items(): at.setdefault(min(i, len(sec.ins)), []).append(nm)
    items = [[at.get(i, []), x, sec.keys[i]] for i, x in enumerate(sec.ins)]     # [labels here, instruction, text keys]
    end = at.get(len(sec.ins), [])
    STOP = ('JUMP_TO', 'IF', 'SET_SELECTION', 'SWITCH', 'SWITCH_W', 'JUMP_AND_LINK', 'END_SECTION', 'END_SCRIPT', 'JUMP_RETURN', 'JUMP_TO_FILE')

    def once():
        pos = {nm: k for k, it in enumerate(items) for nm in it[0]}
        refs = {}
        for _, x, _ in items:
            for t in targets(x, pos): refs[t] = refs.get(t, 0) + 1
        def free(k): return all(not refs.get(nm) for nm in items[k][0])            # only falling in reaches it
        def tgt(x): return x.args[-1][5:]
        def only(x, j): return all(a.startswith(j + ' ') for a in x.args[1:-1])
        for i, (_, x, _) in enumerate(items):
            if x.name != 'IF': continue
            if i + 1 < len(items) and items[i + 1][1].name == 'IF' and free(i + 1):
                y = items[i + 1][1]
                if only(y, 'and') and tgt(x) in pos and pos.get(tgt(x)) == pos.get(tgt(y)):
                    items[i][1] = Instr('IF', x.args[:-1] + ['and ' + y.args[0]] + y.args[1:], x.strings, x.where)
                    del items[i + 1]; return True
            j = i + 1
            while j < len(items) and items[j][1].name not in STOP and free(j): j += 1
            if j >= len(items) or items[j][1].name != 'JUMP_TO' or not free(j): continue
            k = j + 1; n = k - (i + 1)                                   # the then-code: items i+1 .. j
            if pos.get(tgt(x)) != k or refs.get(tgt(x)) != 1 or k + n >= len(items) or items[k][1].name != 'IF': continue
            y = items[k][1]
            if not only(y, 'or') or not all((items[i + 1 + m][1].name, items[i + 1 + m][1].args) == (items[k + 1 + m][1].name, items[k + 1 + m][1].args)
                                             and not items[k + 1 + m][1].strings and free(k + 1 + m) for m in range(n)):
                continue
            items[i][1] = Instr('IF', x.args[:-1] + ['or ' + y.args[0]] + y.args[1:], x.strings, x.where)
            moved = [nm for it in items[k:k + 1 + n] for nm in it[0]]
            del items[k:k + 1 + n]
            if k < len(items): items[k][0] = moved + items[k][0]
            else: end.extend(moved)
            return True
        return False
    changed = False
    while once(): changed = True
    if not changed: return None
    out = snapshot(sec); out.ins = [it[1] for it in items]; out.keys = [it[2] for it in items]; out.labels = {}
    for k, it in enumerate(items):
        for nm in it[0]: out.labels[nm] = k
    for nm in end: out.labels[nm] = len(items)
    return out


UNFOLD_GROWTH = 2.0


def jump_table(sec):
    """A section that starts with two or more `JUMP_TO` in a row (28 of 160 instructions in script 102 section 10, 33 in MAPHEAD section 1238, ...): a table that the
    engine does not run but indexes (`resolveMapHeadEntry`: entry i is the u16 at section + 4 i + 2, which `showMapHeadTextbox` and the shop menus follow to a text). The
    control flow of such a section is its first jump only, so a bisimulation proves a collapsed form equal; the bytes of the table are the section. It is written in the
    literal form (one `goto` per entry) and must compile to the same instruction stream, or it is not lifted.
    (Found by the sweep: 128:5:0 on `readable` hung in drawString2: MAPHEAD section 1238, the Mojyamon shop's texts, had lost its table.)"""
    return len(sec.ins) > 1 and sec.ins[0].name == 'JUMP_TO' and sec.ins[1].name == 'JUMP_TO'


def lift_section(sec, kind, sid, names, tmp, levels=(3, 2, 1, 0), prefer_same=False, retry=True):
    """prefer_same: only a form that compiles to the original's instruction stream (the same bytes): the richest level that
    does, down to the literal form (a container that would not fit its buffer otherwise, `fit`)."""
    lf = Lifted(sec, kind, sid)
    sec0 = snapshot(sec) if retry and levels != (0,) and not prefer_same else None     # (standalone() below changes sec)
    piece = getattr(sec, 'piece', False)
    if kind == 'script' and sec.sid is not None and sec.sid > 254 and sid != 0:
        lf.reason = 'section id above 254 outside script 0 (the language writes events 1-254)'; return lf
    if piece: sec.sid = -1                           # a shared piece: proven as an event, written `shared NAME { }`
    why = standalone(sec)
    if piece: sec.sid = None
    if why: lf.reason = why; return lf
    owner_flow(sec)
    table = jump_table(sec) or bool(getattr(sec, 'shared_at', None))     # a jump table, or the data one points into
    if table: levels = (0,)
    for lv in levels:
        best = None
        for mode in (('seq', 'unfold') if lv else ('seq',)):
            try:
                body, npcs, nlab, used = render(sec, lv, names, sid, kind, mode, sink=not retry)
            except Exception as e:                    # a structuring bug must never produce output: fall back
                lf.why[(lv, mode)] = f'internal {type(e).__name__}: {e}'; continue
            finally:
                decomp.ENT_HOOK = None; decomp.NAME_HOOK = None
            ok, w = verify(lf, body, npcs, names.import_paths(used), names, tmp)
            if ok and table and not lf.same_layout: ok, w = False, 'a jump table must keep its bytes'
            if ok and prefer_same and not lf.same_layout: ok, w = False, 'not the original instruction stream (fitting a full buffer)'
            if ok:
                sh = shared_exit(body, nlab)
                cand = (nlab, body, npcs, used, lf.same_layout, sh, lf._got)
                rank = lambda c: (0 if c[0] == 0 else 1 if c[5] else 2, c[0])
                # an unfolded tree copies the code that branches share: it wins over labels only while it stays under twice the size
                if mode == 'unfold' and best is not None and len(body) > (1.1 * len(best[1]) + 4 if best[5] else UNFOLD_GROWTH * len(best[1]) + 12):
                    lf.why[(lv, mode)] = 'too big'
                elif best is None or rank(cand) < rank(best): best = cand
            else:
                lf.why[(lv, mode)] = w
            if best is not None and best[0] == 0: break
        if best is not None:
            nlab, body, npcs, used, same, sh, got = best
            lf.level = lv; lf.body = body; lf.code = got; lf.compact = prefer_same; lf.npcs = npcs; lf.imports = names.import_paths(used, with_names=False)
            lf.extra = names.extra_used(used); lf.gotos = nlab; lf.shared_exit = sh; lf.same_layout = same
            if nlab and sec0 is not None and lv and not table:     # labels left: the tests split over two IFs as one, and gotos sunk into branches
                again = merge_ifs(sec0) or sec0
                other = lift_section(again, kind, sid, names, tmp, tuple(l for l in levels if l), prefer_same, retry=False)
                if other.level is not None and (other.level, -other.gotos) > (lf.level, -lf.gotos): return other
            return lf
    lf.reason = 'a jump table that does not compile to its own bytes' if table else 'no level could be proven'
    return lf


def lift_script_text(text, kind, sid, fname, names, tmp, levels=(3, 2, 1, 0), shared=True, limit=None):
    secs = split_sections(text, kind, sid, fname)
    if shared: secs = share_pieces(secs)
    out = [lift_section(s, kind, sid, names, tmp, levels) for s in secs]
    if limit: fit(out, text, limit, kind, sid, names, tmp, fname)
    return out


FIT_MARGIN = 64


def code_bytes(lines):
    """Bytes of a piece of assembly (labels free)."""
    from dws import bytecode
    _, items, _ = bytecode.parse_script_text('\n'.join(lines), 'fit')
    return sum(bytecode.instr_size(it[1], {'quiet': True}, lambda w: None) for it in items if it[0] == 'ins' and it[1].name != '.align')


def fit(lifted, text, limit, kind, sid, names, tmp, fname):
    """The readable form of a script must fit the engine's buffer (16 384 bytes; MAPHEAD 25 000 in the original executable):
    the story is built from it, nothing of the disc is kept. Where it would not, the sections that grew most are written in
    the richest form that compiles to the original's own instruction stream (same bytes), until the estimate fits."""
    from dws import bytecode
    base = len(bytecode.assemble_script(text, fname, {'quiet': True})[0])
    def growth(lf):
        if lf.level is None or getattr(lf, 'code', None) is None: return 0
        real = [l for l in lf.code if l.strip() and not l.lstrip().startswith(';')]
        end = 0 if real and real[-1].strip() in ('END_SECTION', 'END') else 2
        return code_bytes(lf.code) + end - code_bytes(lf.sec.lines)
    g = {id(lf): growth(lf) for lf in lifted}
    est = base + sum(g.values())
    order = sorted((lf for lf in lifted if lf.level), key=lambda lf: -g[id(lf)])
    for lf in order:
        if est + FIT_MARGIN <= limit or g[id(lf)] <= 0: break
        new = lift_section(lf.sec, kind, sid, names, tmp, tuple(range(lf.level, -1, -1)), prefer_same=True)
        if new.level is None: continue
        ng = growth(new); est += ng - g[id(lf)]
        lf.__dict__.update(new.__dict__); g[id(lf)] = ng
    lifted_fit = est + FIT_MARGIN <= limit
    for lf in lifted: lf.fit = (base, est, limit, lifted_fit)


# ------------------------------------------------------------------------------------------------ shared code
def share_pieces(secs):
    """Code that other sections reach gets a home in the source (the review's step 1: no `goto original(L)`).

    A label L inside section S that another section (or another piece of S) jumps to cuts S at L: the code from L to the
    next cut is a piece of its own, written `shared L { ... }` in the script, and the code before L ends with `goto L;`
    (the fall-through made explicit). A jump to the first instruction of a section is a jump to that section's entry
    (`goto secN;`). The data a jump table points into (MAPHEAD's shop texts, the cups' DATA rows: the engine reads them by
    position, so they must keep their layout) is not cut: its section stays one literal event whose targets are
    `shared L:` labels. -> the list of Secs, pieces after their section (`sec.piece`), each with `sec.canon` (label -> the
    name the source uses for it) and `sec.shared_at` (instruction index -> shared label name, the table data)."""
    owner = {}                                       # label -> (section index, instruction index)
    for i, s in enumerate(secs):
        for nm, p in s.labels.items(): owner.setdefault(nm, (i, p))
    canon = {}
    tables = {i for i, s in enumerate(secs) if jump_table(s)}
    hosts = set()
    for i in tables:
        for x in secs[i].ins:
            for t in targets(x, secs[i].labels):
                if t in owner and owner[t][0] != i: hosts.add(owner[t][0])
    cuts = {i: set() for i in range(len(secs))}
    shared_at = {i: {} for i in range(len(secs))}

    def pieces(i):
        c = sorted(cuts[i] | {0})
        return [(a, c[k + 1] if k + 1 < len(c) else len(secs[i].ins)) for k, a in enumerate(c)]

    def name_at(j, p):
        """The name the source gives to the code at instruction p of section j."""
        s = secs[j]
        if p == 0: return s.label
        if p >= len(s.ins): return s.next_label
        names = sorted((nm for nm, q in s.labels.items() if q == p), key=lambda n: (not re.fullmatch(r'L\d+', n), len(n), n))
        return names[0]

    changed = True
    while changed:
        changed = False
        for i, s in enumerate(secs):
            for a, b in pieces(i):
                for x in s.ins[a:b]:
                    for t in targets(x, s.labels):
                        if t not in owner: continue
                        j, p = owner[t]
                        if j == i and a <= p < b: continue
                        if j == i and p == b and b == len(s.ins): continue      # the end of the section: falls off, as before
                        if p == 0 or p >= len(secs[j].ins):
                            canon[t] = name_at(j, p); continue
                        if j in hosts:
                            canon[t] = name_at(j, p); shared_at[j][p] = canon[t]; continue
                        if p not in cuts[j]:
                            cuts[j].add(p); changed = True
                        canon[t] = name_at(j, p)
    out = []
    for i, s in enumerate(secs):
        s.canon = canon; s.shared_at = shared_at[i]; s.piece = False
        ps = pieces(i)
        if len(ps) == 1: out.append(s); continue
        lines, o_ins, o_keys, o_labels, o_next = s.lines, list(s.ins), list(s.keys), dict(s.labels), s.next_label
        names_at = {k: name_at(i, k) for k in cuts[i]}
        def line_of(p):
            nms = [nm for nm, q in o_labels.items() if q == p]
            ks = [k for k, l in enumerate(lines) for nm in nms if re.match(rf'^{re.escape(nm)}:', l)]
            if not ks: raise DwsError(f'{s.label}: no line for the label at instruction {p}', None)
            return min(ks)
        n = len(o_ins)
        for k, (a, b) in enumerate(ps):
            q = s if k == 0 else Sec(names_at[a], None)
            la = 0 if k == 0 else line_of(a); lb = line_of(b) if b < n else len(lines)
            labs = {nm: p - a for nm, p in o_labels.items() if a <= p < b or (p == b and b == n)}
            q.ins, q.keys, q.labels, q.lines = o_ins[a:b], o_keys[a:b], labs, lines[la:lb]
            q.all_labels = s.all_labels; q.next_label = names_at[b] if b < n else o_next
            q.canon = canon; q.shared_at = {p - a: n for p, n in shared_at[i].items() if a <= p < b}; q.piece = k > 0
            q.of = s.label
            out.append(q)
    return out
