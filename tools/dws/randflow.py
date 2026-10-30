"""Which instructions of a section consume random numbers, and a proof that two builds of a section consume them the same way.

The question: the beautifier (and the reorder build) must never add, remove or reorder an instruction that draws from the generator on any path, because then every random
event after it in a long play (a battle roll, a drop, a STORE_RANDOM) would see another generator state and diverge from the original game.

CONSUMERS are the script opcodes whose handler reaches rand()/customRandom() in the C code of decomp/ (a call graph of decomp/src: script_interp.c's case of each opcode, and
every function that case calls, transitively, down to randomLimit):
  0x24 STORE_RANDOM         randomLimit(n + 1): exactly one rand()
  0x37 ADVANCE_TO_DATE_AT   dailyPStatTrigger(): a draw (randomLimit(0x40)) when the day changes
  0x64 CALL_ROUTINE         createNinjamonEffect, rollCardPack, lostAllLives, scriptStartTournament; the other routines are minigames and shops, taken as consumers too (all of them: the
                            routine number is part of the instruction, so a routine is never confused with another one)
  0x66 START_BATTLE         startBattle, handleItemLoss
Anything else (SHOW_TEXTBOX, SET_PSTAT, jumps...) draws nothing by itself; the entities' own AI draws on every frame whatever the script does (that is "ambient": a function of the
frames, not of the script).

Two checks per section, both static (on the bytes of DG.SCN / MAPHEAD, no emulator):
  multiset(blob, entry)             the instructions reachable from the section's entry that are consumers, as a Counter of (opcode, operand bytes)
  language_equal(a, ea, b, eb)      the sequences of consumers along every path (symbols: a consumer, a call into another file, the end of the section), compared as automata
                                    (subset construction, then lock-step): equal means that every play that draws k numbers on one build draws the same k, from the same instructions, in
                                    the same order, on the other. JUMP_TO, jump threading, duplicated END_SECTIONs, dead code and the redundant SET_DIALOG_OWNER are invisible to it.
A call (JUMP_AND_LINK) runs the callee and then the next instruction, as a stack (depth at most 8; deeper, or a section that calls itself again and again like 211/8, the stack is abstracted to "returns to any call site of the script": more paths than the game has, the same way on both builds, flagged `approx`). JUMP_TO_FILE_AND_LINK into another script is a symbol of its own (that script is
compared as a section of its own)."""
import sys as _sys
if __name__ == '__main__' and _sys.argv[1:2] in (['-h'], ['--help']): print(__doc__); _sys.exit(0)
import collections
from dws import bytecode

CONSUMERS = {0x24: 'STORE_RANDOM', 0x37: 'ADVANCE_TO_DATE_AT', 0x64: 'CALL_ROUTINE', 0x66: 'START_BATTLE'}
TERMINAL = {0x15: 'JUMP_RETURN', 0x17: 'JUMP_TO_FILE', 0xFE: 'END_SECTION', 0xFF: 'END_SCRIPT'}
JTFAL = 0x14
MAXDEPTH = 8


class Violation(Exception): pass


def decode(blob, p):
    """-> (op, length, targets, bytes) of the instruction at p."""
    n, tg = bytecode.instr_length(blob, p)
    if n is None: raise Violation(f'undecodable instruction {blob[p]:#04x} at {p:#06x}')
    if blob[p] == 0x10 and blob[p + n:p + n + 2] == b'\x12\x00': n += 2          # the "12 00" that ends a selection belongs to SET_SELECTION (bytecode.sweep)
    return blob[p], n, tg, bytes(blob[p:p + n])


def multiset(blob, entry):
    """Counter of (op, bytes) of the consumers reachable from entry (by any branch of any condition; a call goes into the callee)."""
    seen = set(); todo = [entry]; out = collections.Counter()
    while todo:
        p = todo.pop()
        if p in seen: continue
        seen.add(p)
        if p >= len(blob): continue
        op, n, tg, raw = decode(blob, p)
        if op in CONSUMERS: out[(op, raw)] += 1
        if op in TERMINAL: continue
        if op == 0x16: todo.append(tg[0]); continue
        todo.append(p + n); todo.extend(tg)
    return out


class Flow:
    """The control flow of one script blob: steps over (pc, stack) states. `approx` is set when a call stack had to be abstracted."""

    def __init__(self, blob):
        self.blob = blob; self.approx = False; self._ret = None
        self.depth = 0 if self.recursive() else MAXDEPTH          # a script whose subroutines call each other in a cycle has no bounded stack: the abstraction from the start

    def recursive(self):
        """Is there a cycle in the calls (a subroutine that, by some path, calls itself)? The call graph: callee -> callees of the JUMP_AND_LINKs its own flow reaches."""
        blob = self.blob; edges = {}

        def callees(entry):
            seen = set(); todo = [entry]; out = set()
            while todo:
                p = todo.pop()
                if p in seen or p >= len(blob): continue
                seen.add(p); op, n, tg, raw = decode(blob, p)
                if op == 0x13: out.add(tg[0]); todo.append(p + n); continue          # the callee is its own node; the flow goes on after the call
                if op in TERMINAL: continue
                if op == 0x16: todo.append(tg[0]); continue
                todo.append(p + n); todo.extend(tg)
            return out
        todo = list(section_entries(blob).values()); nodes = set()
        while todo:
            e = todo.pop()
            if e in edges: continue
            edges[e] = callees(e); todo.extend(edges[e])
        state = {}

        def dfs(u):
            state[u] = 1
            for v in edges.get(u, ()):
                if state.get(v) == 1 or (v not in state and dfs(v)): return True
            state[u] = 2; return False
        return any(u not in state and dfs(u) for u in list(edges))

    def retsites(self):
        """Return addresses of every JUMP_AND_LINK reachable from any section entry (what a return may go to once the stack is abstracted)."""
        if self._ret is None:
            seen = set(); todo = list(section_entries(self.blob).values()); ret = set()
            while todo:
                p = todo.pop()
                if p in seen or p >= len(self.blob): continue
                seen.add(p); op, n, tg, raw = decode(self.blob, p)
                if op == 0x13: ret.add(p + n)
                if op in TERMINAL: continue
                if op == 0x16: todo.append(tg[0]); continue
                todo.append(p + n); todo.extend(tg)
            self._ret = sorted(ret)
        return self._ret

    def step(self, state):
        """state = (pc, stack) -> ('sym', symbol, [next states]) for a visible instruction, or ('eps', [next states])."""
        blob = self.blob; p, stack = state
        if p >= len(blob): return 'sym', ('END', 'OFF'), []
        op, n, tg, raw = decode(blob, p)
        if op in CONSUMERS: return 'sym', (op, raw), [(p + n, stack)]
        if op == JTFAL: return 'sym', (op, raw), [(p + n, stack)]
        if op == 0x15:                                          # JUMP_RETURN
            if stack == ('*',): return 'eps', [(r, ('*',)) for r in self.retsites()] + [('END', ())]
            return ('eps', [(stack[-1], stack[:-1])]) if stack else ('sym', ('END', op), [])
        if op in TERMINAL: return 'sym', ('END', op, raw if op == 0x17 else b''), []
        if op == 0x16: return 'eps', [(tg[0], stack)]
        if op == 0x13:
            if stack == ('*',): return 'eps', [(tg[0], stack)]
            if len(stack) >= self.depth: self.approx = True; return 'eps', [(tg[0], ('*',))]
            return 'eps', [(tg[0], stack + (p + n,))]
        return 'eps', [(p + n, stack)] + [(t, stack) for t in tg]

    def closure(self, states):
        """Epsilon closure: the set of visible states (states whose instruction emits a symbol)."""
        seen = set(); todo = list(states); vis = set()
        while todo:
            s = todo.pop()
            if s in seen: continue
            seen.add(s)
            if s[0] == 'END': vis.add(s); continue
            r = self.step(s)
            if r[0] == 'sym': vis.add(s)
            else: todo.extend(r[1])
        return frozenset(vis)

    def moves(self, vis):
        """visible states -> {symbol: closure of the successors}."""
        out = collections.defaultdict(set)
        for s in vis:
            if s[0] == 'END': out[('END', 'RET*')].update(()); continue
            _, sym, nxt = self.step(s); out[sym].update(nxt)
        return {sym: self.closure(nx) for sym, nx in out.items()}


def language_equal(a, ea, b, eb):
    """-> (equal, note): note is 'approx' when a call stack was abstracted, else the reason it differs. a, b: the two blobs, ea, eb: entry offsets of the section."""
    fa, fb = Flow(a), Flow(b); start = (fa.closure([(ea, ())]), fb.closure([(eb, ())])); seen = {start}; todo = [start]
    while todo:
        x, y = todo.pop(); ma = fa.moves(x); mb = fb.moves(y)
        if set(ma) != set(mb):
            only = sorted(set(ma) ^ set(mb), key=repr)[0]
            return False, f'a path continues with {_name(only)} on one build only'
        for sym in ma:
            nxt = (ma[sym], mb[sym])
            if nxt not in seen: seen.add(nxt); todo.append(nxt)
        if len(seen) > 200000: raise Violation('automaton too large')
    return True, ('approx' if fa.approx or fb.approx else '')


def _name(sym):
    if sym[0] == 'END': return 'the end of the section'
    return f'{CONSUMERS.get(sym[0], "JUMP_TO_FILE_AND_LINK")} {sym[1][1:].hex()}'


def section_entries(blob):
    """{section id: entry offset} of a script blob; an id repeated in the table keeps its first entry (what getScriptSection finds)."""
    out = {}
    for sid, off in bytecode.parse_header(blob)[1]: out.setdefault(sid, off)
    return out


def table(blob):
    """{(section id, k): entry offset}: every entry of the section table, the k-th time an id is listed (the later ones of a repeated id are never run by the game, but are code)."""
    out = {}; n = collections.Counter()
    for sid, off in bytecode.parse_header(blob)[1]:
        out[(sid, n[sid])] = off; n[sid] += 1
    return out


def check_script(a, b):
    """Every section of two builds of one script: -> list of (section, kind, detail) for each violation (empty: the multiset and the language of consumers are identical)."""
    bad = []
    for s, ca, cb, same_set, same_seq, note in report(a, b):
        if not same_set: bad.append((s, 'multiset', f'{ca} consumers against {cb}'))
        if not same_seq: bad.append((s, 'sequence', note))
    return bad


def report(a, b):
    """Per section of two builds: [(section key, consumers in a, consumers in b (static counts), multiset equal, sequence equal, note)]; the sequence check is the one that matters
    (see the module docstring), the multiset differs when a build copies code into the arms of an if (the same instruction on several paths)."""
    ta, tb = table(a), table(b); rows = []
    for s in sorted(set(ta) | set(tb)):
        key = s[0] if s[1] == 0 else f'{s[0]}.{s[1]}'
        if s not in ta or s not in tb: rows.append((key, 0, 0, False, False, 'section present on one build only')); continue
        ma, mb = multiset(a, ta[s]), multiset(b, tb[s]); ok, note = language_equal(a, ta[s], b, tb[s])
        rows.append((key, sum(ma.values()), sum(mb.values()), ma == mb, ok, note))
    return rows
