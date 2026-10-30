"""A second structurer for the beautifier: it builds the statement tree by *unfolding* the control-flow graph instead of
cutting the instruction range into blocks.

The range structurer (`lift.Structurer`) needs every region to be contiguous and every join to be the next block, so a
menu that re-asks, a decision tree whose leaves are shared across branches or a loop with several exits stay `goto`s.
This one follows the graph: a branch whose arms meet again (the immediate post-dominator) is an `if`/`else` and the code
goes on after it; arms that never meet are written out in full (the shared leaf is copied: the code duplicates, the `goto`
does not); a node that a back edge reaches opens a `loop` (`while` when its test is the head), a jump to it is `continue`,
a jump to the loop's exit is `break`. It never writes a `goto` or a label: when the graph needs one it gives up
(`Unfold` is raised) and the section keeps what the range structurer made. It only produces a tree; `lift.verify` proves it
exactly like the other one, so a bug here can only cost readability.
"""
import copy, sys
from .lift import St, TERMINAL, targets, flow_ends


class Unfold(Exception):
    pass


BRANCHY = ('IF', 'JUMP_TO', 'SET_SELECTION', 'SWITCH', 'SWITCH_W', 'JUMP_AND_LINK')
ENDS = ('END_SECTION', 'END_SCRIPT', 'JUMP_RETURN', 'JUMP_TO_FILE')


class Ctx:
    __slots__ = ('loops', 'stops')

    def __init__(self, loops=(), stops=()):
        self.loops = tuple(loops)       # (head, break target or None, set of nodes) from the outermost to the innermost
        self.stops = tuple(stops)       # joins of the enclosing if/choice: reaching the innermost one ends the block

    def with_stop(self, j):
        return Ctx(self.loops, self.stops + (j,))

    def with_loop(self, head, brk, nodes):
        return Ctx(self.loops + ((head, brk, nodes),), ())


class Unfolder:
    def __init__(self, sec, budget_factor=12):
        self.sec = sec; self.ins = sec.ins; self.n = len(sec.ins); self.lab = sec.labels
        self.extname = {v: k for k, v in sec.labels.items() if v > self.n}
        self.budget = int(budget_factor * self.n) + 40
        for x in self.ins:
            if x.name == 'SWITCH_W' or (x.name == 'JUMP_AND_LINK' and self.lab[x.args[0]] <= self.n): raise Unfold('switch/gosub')
        self.succ = {}
        for i, x in enumerate(self.ins): self.succ[i] = self.succs(i)
        self.reach_nodes()
        self.preds = {i: [] for i in self.nodes}
        for i in self.nodes:
            for s in self.succ[i]:
                if s in self.preds: self.preds[s].append(i)
        self.find_loops()
        self.postdom()
        self.forward_reach()

    # ---- graph
    def resolve(self, t):
        seen = set()
        while t < self.n and self.ins[t].name == 'JUMP_TO' and t not in seen:
            seen.add(t); t = self.lab[self.ins[t].args[0]]
        return t

    def succs(self, i):
        x = self.ins[i]; nm = x.name
        if nm in ENDS: return []
        if nm == 'JUMP_TO': return [self.resolve(self.lab[x.args[0]])]
        out = [self.resolve(self.lab[t]) for t in targets(x, self.lab)] if nm != 'JUMP_AND_LINK' else []
        if nm == 'IF': out = [self.resolve(i + 1)] + out
        else: out = out + [self.resolve(i + 1)]
        return out

    def reach_nodes(self):
        seen = set(); work = [self.resolve(0)]; order = []
        while work:
            i = work.pop()
            if i in seen or i >= self.n: continue
            seen.add(i); order.append(i)
            work.extend(self.succ[i])
        self.nodes = seen

    def find_loops(self):
        # retreating edges by an iterative DFS
        start = self.resolve(0); color = {}; heads = {}; back = {}
        stack = [(start, iter(self.succ[start]))]; color[start] = 1
        while stack:
            u, it = stack[-1]
            for v in it:
                if v >= self.n: continue
                if color.get(v) == 1: back.setdefault(v, []).append(u)
                elif v not in color:
                    color[v] = 1; stack.append((v, iter(self.succ[v]))); break
            else:
                color[u] = 2; stack.pop()
        self.heads = {}
        for h, us in back.items():
            nodes = {h}; work = [u for u in us if u != h]
            nodes.update(work)
            while work:
                v = work.pop()
                for p in self.preds[v]:
                    if p not in nodes: nodes.add(p); work.append(p)
            self.heads[h] = nodes

    def forward_reach(self):
        """reach[u]: a bitset of the nodes reachable from u without taking a retreating edge (back to a loop head)."""
        self.bit = {u: 1 << k for k, u in enumerate(sorted(self.nodes))}
        back = {(u, h) for h, ns in self.heads.items() for u in self.preds[h] if u in ns}
        reach = {}
        sys.setrecursionlimit(max(10000, 4 * self.n))
        def go(u):
            if u in reach: return reach[u]
            reach[u] = self.bit[u]          # a cycle through a non-retreating edge cannot happen in a reducible graph
            r = self.bit[u]
            for v in self.succ[u]:
                if v < self.n and (u, v) not in back: r |= go(v)
            reach[u] = r; return r
        for u in sorted(self.nodes): go(u)
        self.reach = reach
        self.size = {u: bin(r).count('1') for u, r in reach.items()}

    def best_join(self, starts, ctx):
        """The node where the most branches meet again, the biggest shared tail first: the join of an if/choice/switch when
        no node is on every path (a branch returns early)."""
        if ctx.loops:
            mask = 0
            for u in ctx.loops[-1][2]: mask |= self.bit.get(u, 0)
        else: mask = -1
        cnt = {}
        for t in starts:
            if t >= self.n: continue
            if ctx.loops and (t == ctx.loops[-1][0] or t == ctx.loops[-1][1] or t not in ctx.loops[-1][2]): continue
            if ctx.stops and t == ctx.stops[-1]: continue
            r = self.reach[t] & mask
            for u in self.nodes:
                if r & self.bit[u]: cnt[u] = cnt.get(u, 0) + 1
        best = None; score = 0
        for u, c in cnt.items():
            if c < 2 or self.ins[u].name == 'END_SECTION': continue
            if ctx.loops and u == ctx.loops[-1][0]: continue
            sc = (c - 1) * self.size[u]
            if sc > score or (sc == score and best is not None and u < best): best, score = u, sc
        return best

    def postdom(self):
        EXIT = self.n + 10 ** 6
        nodes = sorted(self.nodes)
        ex = {}
        for i in nodes:
            ss = [s if s < self.n else EXIT for s in self.succ[i]]
            ex[i] = ss or [EXIT]
        # nodes that cannot reach the exit (an endless loop) get an edge to it
        rev = {}
        for i in nodes:
            for s in ex[i]: rev.setdefault(s, []).append(i)
        can = {EXIT}; work = [EXIT]
        while work:
            v = work.pop()
            for p in rev.get(v, []):
                if p not in can: can.add(p); work.append(p)
        for i in nodes:
            if i not in can: ex[i] = ex[i] + [EXIT]
        idx = {v: k for k, v in enumerate(nodes)}; full = (1 << (len(nodes) + 1)) - 1
        eb = len(nodes)
        pd = {i: full for i in nodes}; pd[EXIT] = 1 << eb
        bit = lambda v: 1 << (eb if v == EXIT else idx[v])
        changed = True
        while changed:
            changed = False
            for i in reversed(nodes):
                m = full
                for s in ex[i]: m &= pd[s]
                m |= bit(i)
                if m != pd[i]: pd[i] = m; changed = True
        self.ipdom = {}
        for i in nodes:
            rest = pd[i] & ~bit(i)
            best = None; bsz = -1
            for j in nodes:
                if j != i and rest & bit(j):
                    sz = bin(pd[j]).count('1')
                    if sz > bsz: best, bsz = j, sz
            self.ipdom[i] = best            # None: only the exit

    # ---- statements
    def spend(self, k=1):
        self.budget -= k
        if self.budget < 0: raise Unfold('too much duplicated code')

    def jump_stmt(self, i, t, ctx):
        """The statement for reaching node t from the block being built, or None when it just falls (a join) -> ('fall') ."""
        if t > self.n: return St('extgoto', i, label=self.extname[t])
        if t == self.n: return St('return', i)
        if ctx.loops:
            h, brk, nodes = ctx.loops[-1]
            if t == h: return St('continue', i)
            if brk is not None and t == brk: return St('break', i)
        return None

    def trivial(self, t, i, ctx):
        """A statement standing for the whole code from t (a jump, a return), or None."""
        t = self.resolve(t)
        s = self.jump_stmt(i, t, ctx)
        if s is not None: return s
        if t < self.n and self.ins[t].name == 'END_SECTION' and not (ctx.stops and ctx.stops[-1] == t): return St('return', i)
        return None

    def build(self, i, ctx, entering=False):
        out = []
        while True:
            i = self.resolve(i)
            first = entering; entering = False
            if i >= self.n:
                s = self.jump_stmt(i, i, ctx)
                out.append(s if s is not None else St('return', i)); return out
            if ctx.stops and i == ctx.stops[-1] and not first: return out
            if ctx.loops and not first:
                h, brk, nodes = ctx.loops[-1]
                if i == h: out.append(St('continue', i)); return out
                if brk is not None and i == brk: out.append(St('break', i)); return out
                for (hh, _, _) in ctx.loops[:-1]:
                    if i == hh: raise Unfold('jump to an outer loop')
            if i in self.heads and not first:
                lp, nxt = self.loop(i, ctx)
                out.append(lp)
                if nxt is None: return out
                i = nxt; continue
            x = self.ins[i]; nm = x.name
            self.spend()
            if nm == 'END_SECTION':
                out.append(St('return', i)); return out
            if nm in ENDS:
                out.append(St('i', i, idx=i)); return out
            if nm == 'IF':
                r = self.branch(i, ctx, out)
                if r is None: return out
                i = r; continue
            if nm == 'SET_SELECTION':
                r = self.select(i, ctx, out)
                if r is None: return out
                i = r; continue
            if nm == 'SWITCH':
                r = self.switch(i, ctx, out)
                if r is None: return out
                i = r; continue
            if nm in BRANCHY and nm != 'JUMP_AND_LINK': raise Unfold(nm)
            out.append(St('i', i, idx=i)); i += 1

    def join_of(self, i, ctx, starts):
        j = self.ipdom.get(i)
        if j is not None and ctx.loops:
            h, brk, nodes = ctx.loops[-1]
            if j not in nodes or j == h: j = None
        if j is None: j = self.best_join(starts, ctx)
        return j

    def branch(self, i, ctx, out):
        x = self.ins[i]
        t = self.resolve(self.lab[x.args[-1][5:]]); f = self.resolve(i + 1); cond = x.args[:-1]
        if t == f:                  # the test has no effect on the flow, but it is an instruction of the original
            out.append(St('if', i, cond=cond, then=[], els=None)); return f
        J = self.join_of(i, ctx, [f, t])
        tj = self.trivial(t, i, ctx)
        if J is None:
            if tj is not None:                       # the guard: leaves the block when the condition fails
                out.append(St('unlessj', i, cond=cond, jump=tj)); return f
            fj = self.trivial(f, i, ctx)
            then = self.build(f, ctx); els = self.build(t, ctx)
            if then and flow_ends(then[-1], self.sec) and not (len(els) == 1 and els[0].kind == 'if'):
                out.append(St('if', i, cond=cond, then=then, els=None))
                out.extend(els); return None
            out.append(St('if', i, cond=cond, then=then, els=els or None))
            return None
        c2 = ctx.with_stop(J)
        then = self.build(f, c2) if f != J else []
        els = self.build(t, c2) if t != J else []
        if not then and not els: return J
        if not els: out.append(St('if', i, cond=cond, then=then, els=None))
        else: out.append(St('if', i, cond=cond, then=then, els=els))
        return J

    def select(self, i, ctx, out):
        openc = self.ins[i + 1].name != 'END_SELECTION'
        x = self.ins[i]; ts = [self.resolve(self.lab[t]) for t in x.args]
        J = self.join_of(i, ctx, ts + ([] if openc else [self.resolve(i + 2)]))
        c2 = ctx.with_stop(J) if J is not None else ctx
        cancel_t = self.resolve(i + 1) if openc else self.resolve(i + 2)
        plain_open = openc and ts[0] == cancel_t
        opts = []
        for k, t in enumerate(ts):
            opts.append((k, [] if t == J else self.build(t, c2)))
        also = None
        ends = lambda t: t < self.n and self.ins[t].name == 'END_SECTION' and t != J
        cancel = []
        if not plain_open:
            for k, t in enumerate(ts):
                if t == cancel_t or (ends(t) and ends(cancel_t)): also = k; break
            else:
                cancel = [] if cancel_t == J else self.build(cancel_t, c2)
        if out and out[-1].kind == 'i' and out[-1].idx == i - 1 and self.ins[i - 1].name == 'SET_DIALOG_OWNER':
            out.pop()
        out.append(St('choice', i, ins=i, opts=opts, cancel=cancel, also=also, who=self.sec.owner_in[i], openc=openc,
                         cancel_empty=bool(openc and not plain_open and also is None and not cancel)))
        return J

    def switch(self, i, ctx, out):
        x = self.ins[i]; ts = [self.resolve(self.lab[t]) for t in x.args[1:]]
        if len(ts) < 2 or ts[0] != self.resolve(i + 1): raise Unfold('switch whose first case does not follow it')
        J = self.join_of(i, ctx, ts)
        c2 = ctx.with_stop(J) if J is not None else ctx
        arms = [(k, [] if t == J else self.build(t, c2)) for k, t in enumerate(ts)]
        out.append(St('switch', i, ins=i, var=x.args[0], arms=arms))
        return J

    def loop(self, h, ctx):
        nodes = self.heads[h]
        exits = []
        for u in sorted(nodes):
            for s in self.succ[u]:
                if s not in nodes and s not in exits: exits.append(s)
        cond = None
        k = h
        while k < self.n and self.ins[k].name not in BRANCHY and self.ins[k].name not in ENDS and k + 1 in nodes \
                and (k == h or len(self.preds.get(k, [])) == 1): k += 1
        if k < self.n and self.ins[k].name == 'IF' and (k == h or len(self.preds.get(k, [])) == 1):
            tt = self.resolve(self.lab[self.ins[k].args[-1][5:]]); ff = self.resolve(k + 1)
            if ff in nodes and tt not in nodes:
                cond = self.ins[k].args[:-1]; brk = tt; pre_end = k
        self.spend()
        if cond is None:
            real = [e for e in exits if e < self.n and self.ins[e].name != 'END_SECTION']
            brk = real[0] if real else None
            body = self.build(h, ctx.with_loop(h, brk, nodes), entering=True)
            return St('loop', h, body=body), brk
        ctx2 = ctx.with_loop(h, brk, nodes)
        pre = []
        for q in range(h, pre_end):
            self.spend(); pre.append(St('i', q, idx=q))
        body = self.build(pre_end + 1, ctx2)
        return St('while', h, cond=cond, body=body, pre=pre), brk


def strip_tails(block, in_loop=True, top=False):
    """A `continue` at the end of a loop body, and a `return` at the end of the section, are the same as falling off."""
    if not block: return
    last = block[-1]
    if not top and in_loop and last.kind == 'continue' and not last.labels: block.pop(); strip_tails(block, in_loop, top); return
    if top and last.kind == 'return' and not last.labels: block.pop(); strip_tails(block, in_loop, top); return
    if last.kind == 'if':
        strip_tails(last.then, in_loop, top)
        if last.els is not None:
            strip_tails(last.els, in_loop, top)
            if not last.els: last.els = None
    elif last.kind == 'choice':
        for _, ob in last.opts: strip_tails(ob, in_loop, top)
        strip_tails(last.cancel, in_loop, top)
    elif last.kind == 'switch':
        for _, ob in last.arms: strip_tails(ob, in_loop, top)


def tidy(block, top=True, in_loop=False):
    for s in block:
        if s.kind in ('loop', 'while'):
            strip_tails(s.body, True, False)
            tidy(s.body, False, True)
            if s.kind == 'while': tidy(s.pre, False, True)
        else:
            for f in ('then', 'els', 'cancel'):
                v = getattr(s, f, None)
                if isinstance(v, list): tidy(v, False, in_loop)
            if s.kind == 'choice':
                for _, ob in s.opts: tidy(ob, False, in_loop)
            if s.kind == 'switch':
                for _, ob in s.arms: tidy(ob, False, in_loop)
    if top: strip_tails(block, False, True)


def unfold_tree(sec):
    u = Unfolder(sec)
    tree = u.build(0, Ctx())
    tidy(tree)
    return tree
