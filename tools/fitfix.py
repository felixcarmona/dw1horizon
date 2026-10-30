#!/usr/bin/env python3
"""Fit fixer: makes a partner model that is too big for the partner buffer fit, by automatic rules.

Documented in docs/mods/models.md. Everything here is a
rule that runs on the player's own disc at patch/build time (the same law as the rest of the import
tools: no model is hand-edited, no data derived from the games is committed; a species JSON only
holds parameters). Library + CLI:

  fitfix.py measure FILE.MMD NBONES        what the size is made of (mesh / animation / per slot)
  fitfix.py run LIST.json [--only NAME ..] import_batch plan + build with the fit rules, two-tier result

What dominates the size (measured, docs/mods/models.md): the animation slots, 70-80 % of an MMD
(a partner has about 42 slots of 0.6-10 KB, and every slot repeats the 3-byte-per-bone initial pose);
the mesh is 20-30 KB. So the rules go in this order:

 1. `encode_fit` (replaces mmd.encode_anim while a fit build runs): the keyframe segments may end up to
    `tol` away from the sampled value instead of exactly on it (the segment that follows starts where
    the engine really is), channels that stay within `tol` of their first value are not keyed at all.
    Same error budget as before, fewer keys. Loop starts/ends and the finite-loop joints stay exact
    (an inexact one would drift on every pass).
 2. slot rules (`slot_plan`): identical animations are one (the table points two slots at one), the
    slot the training run plays (0x1b) is cut to its first strides, tolerance per slot class
    (idle/walk/attack look tight; getting-up, victory and the like may be coarser).
 3. mesh rules (`simplify_model`): only if the animation rules are not enough.
 4. two tiers: the console buffer (0x18800) first; if it cannot be reached without a visible loss the
    model is built for the 8 MB buffer (0x40000) and the species gets "needs_ram_mb": 8.
"""
import copy
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import mmd  # noqa: E402

LONG_TICKS = 600
LOOP_TOL = 64
CONSOLE_MAX = 0x18800
BIG_MAX = 0x40000


# ------------------------------------------------------------------ measure
def decompose(data, nb):
    """What an MMD's bytes are made of: {total, tmd: {...}, anim: {...}, slots: {slot: bytes}}."""
    m = mmd.MMD.parse(data, nb)
    t = m.tmd
    prim = sum(len(p.raw) for o in t.objects for p in o.prims)
    anims = [a.build() for a in m.anims.anims]
    pose = sum(2 + 2 * (9 if a.has_scale else 6) * (nb - 1) for a in m.anims.anims)
    slots = {s: len(anims[i]) for s, i in enumerate(m.anims.table) if i is not None}
    shared = len(slots) - len(anims)
    return dict(total=len(data), header=8, tmd=len(t.build()), objects=len(t.objects),
                prims=sum(len(o.prims) for o in t.objects), prim_bytes=prim, vert_bytes=8 * len(t.verts),
                norm_bytes=8 * len(t.norms), anim_section=len(m.anims.build()), table=4 * len(m.anims.table),
                anims=len(anims), slots_used=len(slots), shared=shared, initial_pose=pose,
                keyframes=sum(len(a) for a in anims) - pose, slots=slots)


def print_decompose(d, out=print):
    out(f'total {d["total"]}: mesh {d["tmd"]} ({100 * d["tmd"] / d["total"]:.0f} %: {d["prims"]} primitives {d["prim_bytes"]}, '
        f'vertices {d["vert_bytes"]}, normals {d["norm_bytes"]}), animation section {d["anim_section"]} '
        f'({100 * d["anim_section"] / d["total"]:.0f} %: table {d["table"]}, {d["anims"]} animations for '
        f'{d["slots_used"]} slots, initial poses {d["initial_pose"]}, keyframes/loops/events {d["keyframes"]})')
    top = sorted(((v, s) for s, v in d['slots'].items()), reverse=True)[:6]
    out('  biggest slots: ' + ', '.join(f'{s:#04x}={v}' for v, s in top))


# ------------------------------------------------------------------ pose error
def pose_error(anim, samples, nb, slot=None):
    """Largest and mean error of an encoded animation against the samples it was made from:
    rotation (1/4096 turn, angle between both rotations), translation (units), root motion."""
    p = mmd.AnimPlayer(anim, nb, slot)
    worst_r = worst_t = 0
    tot = cnt = 0
    for i in range(len(samples)):
        if not p.tick():
            break
        for b in range(1, nb):
            u, v = samples[i][b], p.pose[b]
            e = mmd._rot_err(u[3:6], v[3:6])
            worst_r = max(worst_r, e)
            tot += e
            cnt += 1
            worst_t = max(worst_t, max(abs(x - y) for x, y in zip(u[6:9], v[6:9])))
    return dict(rot=worst_r, rot_mean=round(tot / max(1, cnt), 3), pos=worst_t)


# ------------------------------------------------------------------ keyframe fitting (rule 1)
def fit_free(Vs, forced=(), tol=0, exact_end=False):
    """Like mmd.fit_segments (linear segments the engine can play, common boundaries) but a segment
    may end up to `tol` away from the sampled value: the next one starts from where the engine
    really is (the error never adds up: every tick of every segment stays within `tol`). Segment
    ends at a `forced` sample (loop start / finite-loop joints) and, with `exact_end`, at the last
    sample are exact. Returns [(start_sample, div, [val per channel])]."""
    n = len(Vs[0]) - 1
    C = len(Vs)
    tols = list(tol) if isinstance(tol, (list, tuple)) else [tol] * C
    forced = sorted(set(f for f in forced if 0 < f < n))
    fset = set(forced)
    P = [V[0] for V in Vs]
    knots = []
    a = 0
    while a < n:
        lim = min([n, a + 0x7FFF] + [f for f in forced if f > a])
        lo, hi = [-1e18] * C, [1e18] * C
        best = None
        for b in range(a + 1, lim + 1):
            D = b - a
            exact = b in fset or (exact_end and b == n)
            ends = []
            for c, V in enumerate(Vs):
                if exact:
                    cand = [V[b]]
                else:
                    e0 = max(V[b] - tols[c], math.ceil(P[c] + D * lo[c] - 1e-9))
                    e1 = min(V[b] + tols[c], math.floor(P[c] + D * hi[c] + 1e-9))
                    cand = sorted(range(e0, e1 + 1), key=lambda e: (abs(e - V[b]), e))
                found = None
                for E in cand:
                    d = E - P[c]
                    if abs(d) > 0x7FFF:
                        continue
                    sg, ad = (1 if d >= 0 else -1), abs(d)
                    if all(abs(P[c] + sg * (k * ad // D) - V[a + k]) <= tols[c] for k in range(1, D)):
                        found = E
                        break
                if found is None:
                    break
                ends.append(found)
            else:
                best = (b, ends)
            stop = False
            for c, V in enumerate(Vs):                       # sample b is an intermediate one for longer segments
                lo[c] = max(lo[c], (V[b] - P[c] - tols[c] - 1) / D)
                hi[c] = min(hi[c], (V[b] - P[c] + tols[c] + 1) / D)
                if lo[c] > hi[c] + 1e-9:
                    stop = True
            if stop:
                break
        if best is None:                                     # cannot happen except out of int16: one tick, exact
            b = a + 1
            best = (b, [V[b] for V in Vs])
        b, ends = best
        knots.append((a, b - a, [E - p for E, p in zip(ends, P)]))
        P = list(ends)
        a = b
    return knots


class Tol:
    """Tolerance per bone and channel, from one number `tol` (1/4096 turn, what the import tools always used).
    Without a model every rotation channel gets `tol` (as before). With one (`Reach`), a rotation error is
    worth what it moves: the same angle displaces the vertices of a bone with a long subtree (the body,
    the wing root) more than those of a fingertip, so the tolerance of a bone is `tol` scaled by
    reference reach / its reach (clamped to tol/2 .. 3 tol): about the same displacement everywhere."""

    def __init__(self, reach=None, trans=1.0):
        self.reach, self.trans = reach, trans

    def of(self, tol, nb):
        out = []
        for b in range(nb):
            r = [tol] * 3 + [tol] * 3 + [max(1, round(tol * self.trans))] * 3
            if self.reach and b < len(self.reach.R) and self.reach.R[b] > 0 and b:
                k = self.reach.ref / self.reach.R[b]
                r[3:6] = [max(max(1, tol // 2), min(3 * tol, round(tol * k)))] * 3
            out.append(r)
        return out


class Reach:
    """How far the geometry hanging from each bone reaches from its joint (DW1 units), at rest: `R[b]`
    for DW1 bone b (0 = entity), `ref` the median. Also the probe points per bone for `world_error`."""

    def __init__(self, skel, bones):
        # skel: [(obj, parent)] of mmdport.skeleton; bones: model bones (verts in the bone's local space)
        n = len(skel)
        self.skel = skel
        self.pts = [[]] + [self._probe(b['verts']) for b in bones]
        self.R = [0.0] * n
        sub = [set([i]) for i in range(n)]
        for i in range(n - 1, 0, -1):
            p = skel[i][1]
            if p >= 0:
                sub[p] |= sub[i]
        # reach of bone b = farthest point of its subtree from its joint, measured in the chain of local frames:
        # sum of the longest chain of joint offsets plus the vertex radius (a bound that is exact for a straight limb)
        off = [0.0] * n
        for i, b in enumerate(bones):
            off[i + 1] = math.sqrt(sum(x * x for x in b['offset'])) if skel[i + 1][1] > 0 else 0.0
        rad = [max([math.sqrt(sum(x * x for x in v)) for v in b['verts']] or [0.0]) for b in bones]
        rad = [0.0] + rad
        down = [0.0] * n
        for i in range(n - 1, 0, -1):
            down[i] = max(down[i], rad[i])
            p = skel[i][1]
            if p > 0:
                down[p] = max(down[p], off[i] + down[i])
        self.R = down
        vals = sorted(x for x in down[1:] if x > 0)
        self.ref = vals[len(vals) // 2] if vals else 1.0

    @staticmethod
    def _probe(verts, k=6):
        if not verts:
            return []
        vs = sorted(verts, key=lambda v: -(v[0] ** 2 + v[1] ** 2 + v[2] ** 2))
        out = vs[:1]
        for v in vs[1:]:
            if len(out) >= k:
                break
            if all(sum((a - b) ** 2 for a, b in zip(v, w)) > 30 ** 2 for w in out):
                out.append(v)
        return out


def world_points(reach, pose):
    """World position of every probe point for a pose (9 values per bone: scale rotation translation)."""
    skel = reach.skel
    M = [None] * len(skel)

    def get(b):
        if M[b] is None:
            v = pose[b]
            R = mmd.rot_matrix(*v[3:6])
            L = [[R[i][j] * v[j] / 4096 for j in range(3)] + [v[6 + i]] for i in range(3)] + [[0, 0, 0, 1]]
            par = skel[b][1]
            M[b] = mmd.mat_mul(get(par), L) if par >= 0 else L
        return M[b]
    out = []
    for b in range(1, len(skel)):
        m = get(b)
        for v in reach.pts[b]:
            out.append([m[i][0] * v[0] + m[i][1] * v[1] + m[i][2] * v[2] + m[i][3] for i in range(3)])
    return out


def world_error(anim, samples, reach, slot=None, ticks=None):
    """Displacement (DW1 units) of the probe points between the animation as encoded and the samples it
    came from, root motion left out (bone 0 is the entity): {max, mean}. This is the number that says
    whether a compression is visible: the model is 180-500 units tall."""
    nb = len(reach.skel)
    p = mmd.AnimPlayer(anim, nb, slot)
    worst, tot, cnt = 0.0, 0.0, 0
    for i in range(min(len(samples), ticks or len(samples))):
        if not p.tick():
            break
        ref = [list(v) for v in samples[i]]
        dec = [list(v) for v in p.pose]
        ref[0][6:9] = dec[0][6:9] = [0, 0, 0]
        for u, v in zip(world_points(reach, ref), world_points(reach, dec)):
            d = math.sqrt(sum((x - y) ** 2 for x, y in zip(u, v)))
            worst = max(worst, d)
            tot += d
            cnt += 1
    return dict(max=round(worst, 2), mean=round(tot / max(1, cnt), 3))


def flatten_static(samples, tols):
    """Channels that never leave their tolerance of their first value become that value (no key at all).
    Returns a copy."""
    out = [[list(v) for v in s] for s in samples]
    nb = len(out[0])
    for b in range(1, nb):
        for j in range(9):
            v0 = out[0][b][j]
            if all(abs(s[b][j] - v0) <= tols[b][j] for s in out) and any(s[b][j] != v0 for s in out):
                for s in out:
                    s[b][j] = v0
    return out


def _cyc(x, y):
    return abs((x - y + 2048) % 4096 - 2048)


def loopify(samples, events, tol, min_len=LONG_TICKS, max_period=96, loop_tol=LOOP_TOL):
    """A very long animation made of one repeated stride (the training run, 0x1b: 225 strides of 20 ticks
    that the original encodes as one finite loop; the retarget adds the layered idle motion of the
    unmapped bones, whose cycle is not a whole number of strides, so mmd.find_repeats cannot see the
    repetition and 4000 ticks cost 200 KB; the old rule cut it to 120 ticks, which freezes the
    Digimon after 6 s) becomes lead-in + one period + an infinite loop: the engine repeats the
    period's per-tick deltas, root travel included. The period is the shortest one after which
    every bone is back within `loop_tol` (1/4096 turn; the slack is spread linearly over the
    period, so the loop closes exactly: a drift would add up on every pass, a snap would show).
    Returns (samples, events, loop_sample) or None."""
    n = len(samples)
    if n < min_len or n < 4 * max_period:
        return None
    nb = len(samples[0])

    def dist(i, j):
        d = 0
        for b in range(nb):
            u, v = samples[i][b], samples[j][b]
            d = max(d, mmd._rot_err(u[3:6], v[3:6]))
            if b:
                d = max(d, max(abs(x - y) for x, y in zip(u[6:9], v[6:9])))
        return d
    for p0 in range(0, 3 * max_period, 4):
        for p in range(4, max_period + 1):
            if p0 + 3 * p >= n:
                break
            if all(dist(i, i + p) <= loop_tol for i in range(p0, p0 + 2 * p + 1, 2)):
                out = [[list(v) for v in s] for s in samples[:p0 + p + 1]]
                first, last = out[p0], out[-1]
                for b in range(nb):
                    for j in range(3, 6):                      # whole turns towards the end, then spread the rest
                        d = first[b][j] - last[b][j]
                        d -= 4096 * round(d / 4096)
                        for k in range(p + 1):
                            out[p0 + k][b][j] += round(d * k / p)
                    if b:
                        for j in range(6, 9):
                            d = first[b][j] - last[b][j]
                            for k in range(p + 1):
                                out[p0 + k][b][j] += round(d * k / p)
                for b in range(nb):                            # the last pose is the loop start's, in the same Euler solution
                    for j in range(3, 6):
                        out[-1][b][j] = first[b][j] + 4096 * round((out[-2][b][j] - first[b][j]) / 4096)
                return out, [e for e in events if e[0] < len(out)], p0
    return None


_orig_encode = mmd.encode_anim
_orig_keys = mmd._bone_keys


def _bone_keys_fit(chans, Vs, forced, tols):
    """mmd._bone_keys with fit_free and a tolerance per channel (same two encodings, the smaller wins)."""
    exact_end = bool(forced)

    def emit(per):
        blocks = {}
        for c, knots in per:
            speed = {}
            for s, div, vals in knots:
                for cc, val in zip(c, vals):
                    q, r = int(val / div), val - int(val / div) * div
                    st = (q, 0) if r == 0 else (val, div)
                    if st == speed.get(cc, (0, 0)) and r == 0 and s not in forced:
                        continue
                    speed[cc] = st
                    blocks.setdefault((s, div), {})[cc] = val
        return blocks
    sep = emit([((c,), fit_free([V], forced, [t], exact_end)) for c, V, t in zip(chans, Vs, tols)]) if len(chans) > 1 else None
    joint = emit([(tuple(chans), fit_free(Vs, forced, tols, exact_end))])
    cost = lambda bl: sum(2 + len(v) for v in bl.values())
    return joint if sep is None or cost(joint) <= cost(sep) else sep


def _encode_fit(samples, nb, loop_sample, events, tols, loops):
    """mmd._encode with per-channel tolerances and fit_free."""
    n = len(samples) - 1
    N = n + 1
    if N > mmd.MAX_FRAME:
        return None
    loop = loop_sample is not None
    if loop and not 0 <= loop_sample < n:
        raise ValueError(f'loop start sample {loop_sample} outside 0..{n - 1}')
    a = mmd.Anim()
    a.frame_count = N
    a.has_scale = any(samples[0][b][0:3] != [4096, 4096, 4096] for b in range(1, nb))
    for b in range(1, nb):
        v = samples[0][b] if a.has_scale else samples[0][b][3:]
        for x in v:
            if not -0x8000 <= x <= 0x7FFF:
                raise ValueError(f'initial pose of bone {b} out of int16: {samples[0][b]}')
        a.pose.append(list(v))
    keys_by_frame = {}
    forced = set([loop_sample] if loop else [])
    for s, p, R in loops:
        forced |= {s, s + p}
    for b in range(nb):
        chans, Vs = [], []
        for j in range(9):
            V = [samples[i][b][j] for i in range(n + 1)]
            if any(x != V[0] for x in V):
                chans.append(j)
                Vs.append(V)
        if not chans:
            continue
        for (s, div), vals in _bone_keys_fit(chans, Vs, forced, [tols[b][j] for j in chans]).items():
            for j, val in vals.items():
                keys_by_frame.setdefault(s + 1, []).append((b, j, val, div))
    ev = {}
    for s, kind, c in events:
        if 0 <= s <= n:
            ev.setdefault(s + 1, []).append((kind, c))
    starts = {s + 1: R for s, p, R in loops}
    ends = {s + p + 1: s + 1 for s, p, R in loops}
    if loop:
        starts[loop_sample + 1] = 0xFF
    instrs = []

    def event(kind, c, f):
        if kind.startswith('tex'):
            instrs.append(dict(op='tex', frame=f, src=tuple(c['src']), size=tuple(c['size']), dst=tuple(c['dst'])))
        else:
            instrs.append(dict(op='sound', frame=f, bank=c['bank'], note=c['note']))

    for f in range(1, N + 1):
        evs = sorted(ev.get(f, []), key=lambda x: not x[0].startswith('tex'))
        if f in ends:
            instrs.append(dict(op='loop_end', frame=f, jump=ends[f]))
        if f in starts:
            instrs.append(dict(op='loop_start', count=starts[f], raw=0x1000 | starts[f]))
        kl = keys_by_frame.get(f, [])
        if kl or evs or f in starts or f in ends or f == 1:
            groups = {}
            for b, j, val, div in kl:
                groups.setdefault((b, div), {})[mmd.CHANNELS[j]] = val
            instrs.append(dict(op='key', frame=f, bones=[dict(bone=b, div=d, vals=groups[(b, d)]) for b, d in sorted(groups)]))
        for kind, c in evs:
            event(kind, c, f)
        if loop and f == N:
            instrs.append(dict(op='loop_end', frame=N, jump=loop_sample + 1))
    instrs.append(dict(op='end'))
    a.instrs = instrs
    return a


def encode_fit(samples, nb, loop_sample=None, events=(), tol=0, repeats=True, tolcfg=None):
    """Drop-in for mmd.encode_anim with rule 1 (`fitted()` swaps it in): free segment ends within the
    tolerance, near-static channels not keyed, per-bone tolerances (`Tol`), a long repeated stride as
    an infinite loop (`loopify`). tol = 0 is the exact encoding (mmd's own)."""
    if tol <= 0:
        return _orig_encode(samples, nb, loop_sample, events, tol, repeats)
    events = list(events)
    tols = (tolcfg or Tol()).of(tol, nb)
    if loop_sample is None and len(samples) >= LONG_TICKS:
        r = loopify(samples, events, tol)
        if r:
            samples, events, loop_sample = r
    samples = flatten_static(samples, tols)
    best = _encode_fit(samples, nb, loop_sample, events, tols, [])
    if repeats:
        loops = mmd.find_repeats(samples, events, loop_sample)
        if loops:
            smp, ev, ls, lp = mmd._compress(samples, events, loop_sample, loops)
            alt = _encode_fit(smp, nb, ls, ev, tols, lp)
            if best is None or len(alt.build()) < len(best.build()):
                best = alt
    if best is None:
        raise ValueError(f'{len(samples)} ticks: the frame field allows {mmd.MAX_FRAME}')
    return best


class fitted:
    """with fitfix.fitted(): ... mmd.encode_anim is `encode_fit` (every encode below, also the one inside
    mmd.import_anims, uses it)."""

    def __init__(self, on=True, record=None, tolcfg=None):
        self.on, self.record, self.tolcfg = on, record, tolcfg

    def __enter__(self):
        self.calls = self.record if self.record is not None else []
        rec = self.calls

        def f(samples, nb, loop_sample=None, events=(), tol=0, repeats=True):
            a = (encode_fit(samples, nb, loop_sample, events, tol, repeats, self.tolcfg) if self.on else
                 _orig_encode(samples, nb, loop_sample, events, tol, repeats))
            rec.append((samples, nb, loop_sample, list(events), tol, a))
            return a
        mmd.encode_anim = f
        return self

    def __exit__(self, *x):
        mmd.encode_anim = _orig_encode


# ------------------------------------------------------------------ slot rules (rule 2)
def dedupe(data, nb):
    """Identical animations are one: the slot table of an MMD points two slots at the same bytes
    (the originals do it for 0x01/0x0e-0x12/0x22 and others). The engine only reads the table.
    Returns (data, slots saved)."""
    m = mmd.MMD.parse(data, nb)
    seen, remap, new = {}, {}, []
    for i, a in enumerate(m.anims.anims):
        key = a.build()
        if key not in seen:
            seen[key] = len(new)
            new.append(a)
        remap[i] = seen[key]
    saved = len(m.anims.anims) - len(new)
    m.anims.anims = new
    m.anims.table = [remap[x] if x is not None else None for x in m.anims.table]
    return m.build(), saved


# ------------------------------------------------------------------ mesh rules (rule 3)
def prim_count(model):
    return sum(len(b['prims']) for b in model.bones)


def _cycle(n):
    return (0, 1, 3, 2) if n == 4 else (0, 1, 2)       # PS1 quad corner order -> polygon cycle


def simplify_model(model, keep, max_edge=None, log=print):
    """Edge-collapse simplification of every piece (own implementation: tools/meshfix.py, the quadric
    decimation, did not exist when this was written; swap `simplify_model` for it when it does).
    Collapses the shortest edges first (a border edge counts double, so silhouettes of open pieces
    stay), the vertex goes to the middle; a quad that loses a corner becomes a triangle, a face that
    loses two disappears; the corner UVs and normals stay as they were. Stops at `keep` x the
    primitive count or when the shortest edge is longer than `max_edge` (default 5 % of the model's height:
    nothing visible is collapsed). Works on a copy: returns (model, report)."""
    import heapq
    m = copy.copy(model)
    m.bones = [dict(b) for b in model.bones]
    n0 = prim_count(m)
    target = int(round(n0 * keep))
    H = getattr(model, 'H', 400.0)
    limit = max_edge if max_edge is not None else 0.05 * H
    st = []
    for bi, b in enumerate(m.bones):
        V = [list(v) for v in b['verts']]
        P = [dict(p, verts=list(p['verts']), norms=list(p['norms']) if p['norms'] else None,
                  uvs=list(p['uvs']) if p['uvs'] else None) for p in b['prims']]
        st.append(dict(V=V, P=P, alive=[True] * len(P), use={}, n=len(P)))
        for pi, p in enumerate(P):
            for v in p['verts']:
                st[-1]['use'].setdefault(v, set()).add(pi)
    total = n0

    def edges(s, pi):
        p = s['P'][pi]
        cyc = [p['verts'][k] for k in _cycle(len(p['verts']))]
        return [(cyc[i], cyc[(i + 1) % len(cyc)]) for i in range(len(cyc))]

    def cost(s, a, b):
        d = math.dist(s['V'][a], s['V'][b])
        shared = len(s['use'][a] & s['use'][b])
        return d * (2.0 if shared < 2 else 1.0)
    heap = []
    for bi, s in enumerate(st):
        seen = set()
        for pi in range(len(s['P'])):
            for a, b in edges(s, pi):
                if a != b and (min(a, b), max(a, b)) not in seen:
                    seen.add((min(a, b), max(a, b)))
                    heapq.heappush(heap, (cost(s, a, b), bi, min(a, b), max(a, b)))
    collapsed = 0
    while heap and total > target:
        c, bi, a, b = heapq.heappop(heap)
        s = st[bi]
        if c / 2.0 > limit:
            break
        if a == b or a not in s['use'] or b not in s['use'] or not (s['use'][a] & s['use'][b]):
            continue
        if abs(cost(s, a, b) - c) > 1e-6:                     # stale: the vertices moved
            heapq.heappush(heap, (cost(s, a, b), bi, a, b))
            continue
        if s['n'] <= 8:                                       # a small piece is left alone
            continue
        V = s['V']
        V[a] = [(x + y) / 2.0 for x, y in zip(V[a], V[b])]
        touched = set()
        for pi in list(s['use'].pop(b)):
            p = s['P'][pi]
            p['verts'] = [a if v == b else v for v in p['verts']]
            s['use'].setdefault(a, set()).add(pi)
            cyc = _cycle(len(p['verts']))
            order = [k for k in cyc]
            keepk = []
            for i, k in enumerate(order):                     # drop consecutive duplicates along the polygon
                if p['verts'][k] != p['verts'][order[i - 1]]:
                    keepk.append(k)
            if len(set(p['verts'][k] for k in keepk)) < 3:
                s['alive'][pi] = False
                s['n'] -= 1
                total -= 1
                for v in set(p['verts']):
                    s['use'][v].discard(pi)
                continue
            if len(keepk) < len(order):                       # a quad lost a corner: a triangle in the same winding
                p['verts'] = [p['verts'][k] for k in keepk]
                if p['norms']:
                    p['norms'] = [p['norms'][k] for k in keepk]
                if p['uvs']:
                    p['uvs'] = [p['uvs'][k] for k in keepk]
            touched.add(pi)
        collapsed += 1
        for pi in touched:
            if s['alive'][pi]:
                for x, y in edges(s, pi):
                    if x != y and a in (x, y):
                        heapq.heappush(heap, (cost(s, x, y), bi, min(x, y), max(x, y)))
    out_prims = 0
    for bi, (b, s) in enumerate(zip(m.bones, st)):
        P = [p for p, al in zip(s['P'], s['alive']) if al]
        used = sorted(set(v for p in P for v in p['verts']))
        vm = {v: i for i, v in enumerate(used)}
        b['verts'] = [tuple(s['V'][v]) for v in used]
        for p in P:
            p['verts'] = [vm[v] for v in p['verts']]
        b['prims'] = P
        out_prims += len(P)
    rep = dict(before=n0, after=out_prims, collapses=collapsed, limit=round(limit, 1), target=target)
    log(f'  mesh: {n0} -> {out_prims} primitives ({collapsed} edge collapses, edges up to {limit:.0f} units)')
    return m, rep


# ------------------------------------------------------------------ the build (rules 1-3 together)
LAST = {}          # numbers of the last build_partner_fit: size, mesh, error (read by rescue, shown in reports)


def build_partner_fit(model, spec, out_mmd, out_tex, workdir, log=print):
    """mmdport.build_partner (the same spec) with the fit rules: spec['fit'] = {tol, tol_clips, mesh_keep, max}
    (mmdport.build_partner calls this when the spec has a "fit"). The size limit is fit['max'] (default
    mmdport.PARTNER_MMD_MAX): a bigger result raises the same SystemExit as the plain builder."""
    import mmdport
    fit = spec['fit']
    sp = {k: v for k, v in spec.items() if k != 'fit'}
    sp['tol'], sp['tol_clips'] = fit['tol'], fit['tol_clips']
    limit = int(fit.get('max', mmdport.PARTNER_MMD_MAX))
    m, mrep = (simplify_model(model, fit['mesh_keep'], log=log) if fit.get('mesh_keep', 1.0) < 1.0
               else (model, None))
    nb = len(m.bones) + 1
    reach = Reach(mmdport.skeleton(m), m.bones)
    builder = mmdport.build_partner
    if getattr(m, 'game', '') == 'dw2':
        import dw2mmd
        builder = dw2mmd.build_partner
    saved_max = mmdport.PARTNER_MMD_MAX
    mmdport.PARTNER_MMD_MAX = BIG_MAX * 4                    # never refuse inside: the limit is checked after the rules
    rec = []
    try:
        with fitted(record=rec, tolcfg=Tol(reach, fit.get('trans', 0.5))):
            data = builder(m, sp, out_mmd, out_tex, workdir, log=lambda *a: None)
    finally:
        mmdport.PARTNER_MMD_MAX = saved_max
    data, shared = dedupe(data, nb)
    errs = [world_error(a, smp, reach, ticks=120) for (smp, n_, ls, ev, t, a) in rec
            if t > 0 and len(smp) < LONG_TICKS]      # (a looped long stride differs from its source by design)
    LAST.clear()
    LAST.update(bytes=len(data), shared_slots=shared, mesh=mrep, tol=fit['tol'], tol_clips=fit['tol_clips'],
                world_err_max=max([e['max'] for e in errs] or [0]),
                world_err_mean=round(sum(e['mean'] for e in errs) / max(1, len(errs)), 3), height=round(getattr(m, 'H', 0)))
    d = decompose(data, nb)
    log(f'{out_mmd}: {len(data)} bytes with the fit rules (tol {fit["tol"]}/{fit["tol_clips"]}, '
        f'mesh {fit.get("mesh_keep", 1.0):g}; limit {limit}); pose error against the source: '
        f'at most {LAST["world_err_max"]} units, mean {LAST["world_err_mean"]} (model {LAST["height"]} tall)')
    print_decompose(d, out=log)
    if len(data) > limit:
        raise SystemExit(f'{out_mmd}: {len(data)} bytes do not fit PARTNER_MODEL_BUFFER ({limit})')
    open(out_mmd, 'wb').write(data)
    return data


# (tol, tol_clips, share of the primitives kept): in order of what it costs the look; tol is 1/4096 turn per rotation
# channel (8 = 0.7 degrees, 16 = 1.4). 16/16 is the loosest the plain size steps of import_batch ever used. Measured on
# Garudamon (docs/mods/models.md "Fit fixer"): tolerance saves more bytes per unit of pose error than anything else, clips (the source
# game's attack animations, 4 until now) can take the same tolerance as the retargeted slots, and a coarser tolerance for
# the seldom-seen slots only saves less than raising all of them; the mesh is last (a face of the model changes).
LADDER = [(8, 4, 1.0), (8, 8, 1.0), (12, 8, 1.0), (12, 12, 1.0), (16, 12, 1.0), (16, 16, 1.0), (16, 16, 0.95), (16, 16, 0.9)]


def rescue(m, spec, sp_species, out_dir, rep, log=print):
    """Last resort of import_batch.build_one when no size rule of its own was enough: the fit rules in the
    order of LADDER for the console buffer (mmdport.PARTNER_MMD_MAX), then the same model for the 8 MB buffer
    ("needs_ram_mb": 8 in the species). Returns the MMD bytes or None (the caller reports hand work)."""
    import mmdport
    console = mmdport.PARTNER_MMD_MAX
    stem = os.path.join(out_dir, spec['name'])
    tries = [dict(tol=t, tol_clips=c, mesh_keep=k, max=console) for t, c, k in LADDER]
    tries.append(dict(tol=LADDER[0][0], tol_clips=LADDER[0][1], mesh_keep=1.0, max=BIG_MAX, ram_mb=8))
    for fit in tries:
        sp = json.loads(json.dumps(spec))
        sp['fit'] = {k: v for k, v in fit.items() if k != 'ram_mb'}
        builder = mmdport.build_partner
        if getattr(m, 'game', '') == 'dw2':
            import dw2mmd
            builder = dw2mmd.build_partner
        lines = []
        try:
            data = builder(m, sp, stem + '.MMD', stem + '.TIM', out_dir, log=lines.append)
        except SystemExit as e:
            if 'PARTNER_MODEL_BUFFER' not in str(e):
                raise
            continue
        what = (f'fit rules: animation keys within tol {fit["tol"]}/{fit["tol_clips"]}'
                + (f', {round(100 * (1 - fit["mesh_keep"]))} % of the primitives merged away' if fit['mesh_keep'] < 1 else '')
                + f' ({LAST["bytes"]} bytes of {console}; pose error at most {LAST["world_err_max"]} units, '
                  f'mean {LAST["world_err_mean"]}, model {LAST["height"]} tall)')
        if fit.get('ram_mb'):
            what = (f'fit rules cannot reach the console buffer ({console}) without a visible loss: the model '
                    f'({LAST["bytes"]} bytes) is for the {BIG_MAX} buffer of 8 MB RAM: needs_ram_mb 8')
            sp_species['needs_ram_mb'] = fit['ram_mb']
        rep['rules'].append(what)
        rep['fit'] = dict(LAST, spec=sp['fit'])
        rep['mmd_bytes'] = len(data)
        spec['fit'] = sp['fit']                       # the spec file (specs/<Name>.json) records the rule parameters
        specdir = os.path.join(ROOT, 'mods', 'experimental', 'batch-import', 'specs')
        os.makedirs(specdir, exist_ok=True)
        json.dump(sp, open(os.path.join(specdir, spec['name'] + '.json'), 'w'), indent=1)
        json.dump(dict(bones=[list(x) for x in mmdport.skeleton(m)]), open(stem + '.skeleton.json', 'w'))
        log('\n'.join(lines))
        return data
    return None


# ------------------------------------------------------------------ command line
def cmd_measure(a):
    nb = int(a.bones)
    print_decompose(decompose(open(a.mmd, 'rb').read(), nb))


def cmd_run(a):
    """import_batch run with the fit rules first: the plain size steps (tolerance, dropped techniques) are not tried
    (a fit species keeps all its techniques and animations), `rescue` runs as soon as the planned build is too big."""
    import import_batch as ib
    ib._venv()
    del ib.BUDGET_STEPS[1:]
    ib.cmd_run(a)


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('measure'); p.add_argument('mmd'); p.add_argument('bones'); p.set_defaults(f=cmd_measure)
    p = sub.add_parser('run'); p.add_argument('list'); p.add_argument('--only', nargs='*'); p.set_defaults(f=cmd_run)
    a = ap.parse_args()
    a.f(a)


if __name__ == '__main__':
    main()
