#!/usr/bin/env python3
"""Measured QA of an imported species' battle clips (slots 0x21-0x24: battle idle, tired battle idle, the two movements).

A battle clip given back from the source game (`battle_restore.py`) must be the source's own and must not be broken or
odd on our model. This tool measures the FINAL model (what ships: the provider output after the delta, field overlays,
native binding and passes; not the `edit.py get` intermediate) slot by slot against the importer's output of the species
(the baseline: the source game's clip) and against origin/main's final model, and flags with fixed thresholds:

  fidelity   per bone and tick, the local rotation (degrees) and the root's travel (heights) against the baseline clip
             retimed the way `battle_restore.retimed` retimes it (bone offsets and scales are the rig's: the chibi pass
             reshapes them); a slot that differs from main must match it
  liveness   each limb chain (bones from a branching bone to a leaf: leg, arm, wing, tail, head, jaw) moves its tip
             (mesh centroid of its last bone with a mesh) in the frame of the bone it hangs from. A chain moving in the
             baseline must keep half of that motion; in 0x23/0x24 a chain that swings in main's field walk or run (2, 4)
             but is still here while a sibling chain of its kind (leg: its tip is near the floor in the field idle) still
             moves is a missing bone map (a static front leg)
  bonemap    a bone that never rotates over the four battle slots while it rotates in the baseline's battle clips
  mesh       the rigid pieces as the engine draws them (one TMD object per bone): non-finite numbers and scale channels,
             the largest vertex step between ticks, the loop seam (last tick to first; a looping clip only), each piece's
             gap growth to the nearest other piece against the field idle (a foot that leaves its leg, as
             `meshcheck.tears`), triangle crossings per tick between pieces that are not parent and child against the field idle's
  posture    the forward-axis elevation of the body bones (bones in no limb chain: pelvis, chest) against the field idle
             (a torso tipped back or forward), the lowest vertex under the field idle's floor, the body floating
  motion     the movement slots' length against main's (technique timing), the root's excursion, the bones' mean
             angular speed (frantic)

The thresholds are the measured range of the disc's own DW1 species (141 native models, slots 0x21-0x24 against their
own field clips; `tools/test_battle_qa.py` and docs/reference/motion.md give the rates) and catch the known-bad clips
(a foot off its leg, front legs left without a bone map, a torso tipped back 28 and 65 degrees). A flag marks a clip
outside that range or worse than main; `classify` says where it comes from: 'main' (main's own clip, pre-existing),
'source' (the importer's clip on the importer's own rig, measured against its own field idle, has the defect too),
'retime' (ours: the clip's new length) or 'rig' (ours: the source's motion on our reshaped rig). A flagged clip that
is not main's is kept only when no flagged number is worse than main's same slot; otherwise the slot goes back to
main's clip (docs/reference/motion.md).

  tools/models/battle_qa.py check FINAL.MMD BASE.MMD MAIN.MMD SPECIES_JSON [--slots ...] [--polished SLOT ...] [--json OUT]
            FINAL, BASE and MAIN are the species' final model of this tree, its importer output and origin/main's final
            model (the provider's output, e.g. as `edit.py check --species-pins` makes it); exits 1 when a slot fails

Not proven by these numbers: how a clip reads (character, taste), contact with the opponent or the arena, what the engine
interpolates between ticks at 60 fps, and the root's height (the root channels accumulate travel; the model is measured
at the origin). Pieces are rigid, so a triangle stretches only through a scale channel (checked). Uses numpy.
"""
import argparse
import json
import os
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path[:0] = [ROOT, os.path.join(ROOT, 'tools'), os.path.join(ROOT, 'tools', 'models')]

BATTLE = (33, 34, 35, 36)
MOVES = (35, 36)
FIELD_MOVES = (2, 4)

# Thresholds. Heights: the species' field idle height. Pairs: (idles 0x21/0x22, movements 0x23/0x24). The native rate is
# the share of the 564 native battle clips over the limit alone (measured 2026-11-13).
FID_ROT = 1.5          # fidelity: rotation error of any bone and tick against the retimed baseline (degrees)
FID_TR = 0.01          # ... root travel error (heights)
LIVE_FLOOR = 0.03      # a chain moves when its tip travels this far from its mean (heights)
LIVE_KEEP = 0.5        # ... and keeps at least this share of the baseline's motion
FIELD_SWING = 0.08     # 0x23/0x24: a chain that swings this far in main's field walk or run
STILL_RATIO = 0.25     # ... moving under this share of it
SIBLING_RATIO = 0.3    # ... and under this share of a sibling of its kind (native rate 1 %)
BONEMAP_DEG = 5.0      # a bone rotating this much in the baseline's battle clips must rotate in ours
STILL_DEG = 0.5
SCALE_MAX = 0.02       # a scale channel off main's (and off 1.0) by this much
JUMP_MAX = (0.43, 1.21)  # largest vertex step between ticks (native 99th percentile)
SEAM_MAX = 0.05        # loop seam (native rate 0.4 %)
TEAR_MAX = 0.08        # a piece's gap growth (meshcheck.STRETCH_MAX; native maximum 0.09, 99th percentile 0.044)
CROSS_RATIO = 2.1      # crossings per tick over the field idle's x this + CROSS_ADD (native 99th percentile 2.07)
CROSS_ADD = 10
BODY_MAX = 25.0        # body bone elevation off the field idle (degrees; native rate 9 %: crouches, lunges)
BODY_WORSE = 10.0      # ... and this much more than main's same slot
BODY_ABS = (41.0, 57.0)  # ... or beyond any native clip (the native maximum), whatever main does
SINK_MAX = 0.30        # lowest vertex under the field idle's floor (native 99th percentile 0.29 of the movements)
FLOAT_MAX = 0.20       # the lowest vertex of the whole clip above that floor (native 99th percentile 0.18)
WORSE = 0.10           # ... and this much more than main's same slot
LUNGE_MAX = 4.0        # 0x23/0x24 root excursion (heights; native rate 1 %), and LUNGE_WORSE over main's
LUNGE_WORSE = 1.0
SPEED_MAX = (5.4, 13.5)  # mean angular speed (degrees per tick; native 99th percentile), and FRANTIC times main's
FRANTIC = 2.5

# slots whose restored clip was leaned on purpose (`battle_restore.py pitch`: the torso back to the species' stance), so
# fidelity to the source does not apply: ShellNumemon's and Okuwamon's tired battle idles; WarGreymon's battle idle (its
# chest leaned back 5 degrees, the hip plates riding on the thighs, the back plates as in the field idle:
# tools/models/field_animations/wargreymon_gait.py)
POLISHED = {231: (34,), 259: (34,), 305: (36,), 373: (33,)}


def polished_slots(sid):
    """POLISHED's slots of species `sid` and the slots rebuilt from the source's clip with repairs
    (content/models/imports/battle-rebuilds.json, `battle_restore.py rebuild`): fidelity does not apply to them; every
    liveness, mesh, posture and motion check does."""
    path = os.path.join(ROOT, 'content', 'models', 'imports', 'battle-rebuilds.json')
    rebuilt = ()
    if os.path.exists(path):
        with open(path) as fh:
            rebuilt = tuple(int(k) for k in json.load(fh).get(str(sid), {}))
    return tuple(sorted(set(POLISHED.get(sid, ())) | set(rebuilt)))


# ------------------------------------------------------------------ geometry
def euler(P):
    """Rotation matrices (..., 3, 3) of libgte RotMatrix (Rx.Ry.Rz) for angles (..., 3) in 1/4096 turn."""
    k = 2 * np.pi / 4096
    cx, sx = np.cos(P[..., 0] * k), np.sin(P[..., 0] * k)
    cy, sy = np.cos(P[..., 1] * k), np.sin(P[..., 1] * k)
    cz, sz = np.cos(P[..., 2] * k), np.sin(P[..., 2] * k)
    return np.stack([np.stack([cy * cz, -cy * sz, sy], -1),
                     np.stack([sx * sy * cz + cx * sz, -sx * sy * sz + cx * cz, -sx * cy], -1),
                     np.stack([-cx * sy * cz + sx * sz, cx * sy * sz + sx * cz, cx * cy], -1)], -2)


def angle(A, B):
    """Angle (degrees) between rotation matrices A and B (broadcast)."""
    tr = np.einsum('...ij,...ij->...', A, B)
    return np.degrees(np.arccos(np.clip((tr - 1) / 2, -1, 1)))


def mean_rotation(R):
    u, _, vt = np.linalg.svd(R.sum(0))
    if np.linalg.det(u @ vt) < 0:
        u[:, -1] *= -1
    return u @ vt


def elevation(R):
    """Elevation (degrees) of each matrix's forward axis (-z; y is down): how far the bone's front tips up or down."""
    return np.degrees(np.arcsin(np.clip(R[..., 1, 2], -1, 1)))


class Rig:
    """A skeleton (parent per bone), its rigid pieces (local vertices and triangles per bone) and its clips."""

    def __init__(self, parents, local, tris, clips):
        self.parent = list(parents)
        self.nb = len(self.parent)
        self.children = {b: [c for c in range(self.nb) if self.parent[c] == b] for b in range(self.nb)}
        self.order, seen = [], set()

        def visit(b):
            if b not in seen:
                if self.parent[b] >= 0:
                    visit(self.parent[b])
                seen.add(b)
                self.order.append(b)
        for b in range(self.nb):
            visit(b)
        self.local = {b: np.asarray(v, float) for b, v in local.items() if len(v)}
        self.meshed = sorted(self.local)
        self.tris = {b: np.array([t for bb, t in tris if bb == b], int).reshape(-1, 3) for b in self.meshed}
        self._clips = clips              # {slot: (frames (F, nb, 9), loop)} or a callable slot -> that or None

    @classmethod
    def from_mmd(cls, data, bones):
        import animsheet
        import meshcheck
        mc = meshcheck.Model(data, [tuple(b) for b in bones])
        nb = len(bones)

        def clips(slot):
            t = mc.m.anims.table if mc.m.anims else []
            if slot >= len(t) or t[slot] is None:
                return None
            fr, loop, _ = animsheet.slot_frames(mc.m, nb, slot)
            return np.array(fr, float), loop
        return cls([p for _, p in bones], mc.local, [(t[0], t[3]) for t in mc.tris], clips)

    def frames(self, slot):
        return self._clips(slot) if callable(self._clips) else self._clips.get(slot)

    def chains(self):
        out = []
        for leaf in range(1, self.nb):
            if self.children[leaf]:
                continue
            chain, b = [leaf], leaf
            while self.parent[b] > 1 and len(self.children[self.parent[b]]) == 1:
                b = self.parent[b]
                chain.insert(0, b)
            tip = next((c for c in reversed(chain) if c in self.local), None)
            if self.parent[b] >= 0 and tip is not None:
                out.append(dict(bones=chain, base=self.parent[chain[0]], tip=tip))
        return out


class Clip:
    """One slot: per tick the bones' world matrices (body frame and model frame) and the pieces' vertices."""

    def __init__(self, rig, frames, loop=0):
        self.rig, self.P, self.loop, self.n = rig, frames, loop, len(frames)
        self.local_rot = euler(frames[..., 3:6])
        L = np.zeros((self.n, rig.nb, 4, 4))
        L[..., :3, :3] = self.local_rot * (frames[:, :, None, 0:3] / 4096.0)
        L[..., :3, 3], L[..., 3, 3] = frames[..., 6:9], 1
        self.root = frames[:, 0, 6:9].copy()
        body = L.copy()
        body[:, 0] = np.eye(4)            # the root's turn and travel taken out
        full = L.copy()
        full[:, 0, :3, 3] = 0             # the model at the origin with the root's turn (its channels accumulate travel)
        self.Wb, self.Wf = self._chain(body), self._chain(full)
        self.V = {b: np.einsum('fij,nj->fni', self.Wf[:, b, :3, :3], v) + self.Wf[:, b, None, :3, 3]
                  for b, v in rig.local.items()}

    def _chain(self, L):
        W = np.zeros_like(L)
        for b in self.rig.order:
            p = self.rig.parent[b]
            W[:, b] = L[:, b] if p < 0 else W[:, p] @ L[:, b]
        return W


def _nearest_gaps(rig, V, f):
    out = {}
    for b in rig.meshed:
        others = [V[c][f] for c in rig.meshed if c != b]
        if not others:
            return {}
        o = np.concatenate(others)
        out[b] = float(np.sqrt(((V[b][f][:, None] - o[None]) ** 2).sum(-1)).min())
    return out


def crossings(rig, V, n, step=2):
    """Triangle crossings per tick between pieces that are not parent and child: [mean, max]."""
    from tools.models.field_animations import meshclash
    pairs = [(a, b) for i, a in enumerate(rig.meshed) for b in rig.meshed[i + 1:]
             if rig.parent[a] != b and rig.parent[b] != a and len(rig.tris[a]) and len(rig.tris[b])]
    counts = []
    for f in range(0, n, step):
        tri = {b: V[b][f][rig.tris[b]] for b in rig.meshed if len(rig.tris[b])}
        box = {b: (t.reshape(-1, 3).min(0), t.reshape(-1, 3).max(0)) for b, t in tri.items()}
        total = 0
        for a, b in pairs:
            if (box[a][0] > box[b][1]).any() or (box[b][0] > box[a][1]).any():
                continue
            total += meshclash.crossing(tri[a], tri[b])[0]
        counts.append(total)
    return [float(np.mean(counts)), int(max(counts))] if counts else [0.0, 0]


def reference(rig):
    """The species' field idle (slot 0 of main's model) as the measuring stick: height, floor, gaps, chains, body."""
    c = Clip(rig, *rig.frames(0))
    allv = np.concatenate([c.V[b][0] for b in rig.meshed])
    h = float(max(np.ptp(allv[:, 1]), 1.0))
    floor = float(np.concatenate([c.V[b][:, :, 1] for b in rig.meshed], 1).max(1).mean())
    chains = rig.chains()
    low = {b: c.V[b][0][:, 1].max() for b in rig.meshed}
    for ch in chains:
        ch['kind'] = 'leg' if low[ch['tip']] > max(low.values()) - 0.2 * h else 'limb'
    in_chain = {b for ch in chains for b in ch['bones']}
    body = [b for b in range(1, rig.nb) if b not in in_chain]
    return dict(h=h, floor=floor, gap=_nearest_gaps(rig, c.V, 0), chains=chains, body=body,
                body_elev=elevation(c.Wb[:, body, :3, :3]).mean(0) if body else np.zeros(0),
                cross=crossings(rig, c.V, c.n)[0])


# ------------------------------------------------------------------ per clip measurements
def measure(clip, ref):
    rig, h, V = clip.rig, ref['h'], clip.V
    out = dict(n=clip.n, finite=bool(np.isfinite(clip.P).all()),
               scale=clip.P[..., 0:3].reshape(clip.n, -1))
    out['bone_range'] = [0.0] + [float(angle(clip.local_rot[:, b], mean_rotation(clip.local_rot[:, b])[None]).max())
                                 for b in range(1, rig.nb)]
    out['speed'] = float(angle(clip.local_rot[1:, 1:], clip.local_rot[:-1, 1:]).mean()) if clip.n > 1 else 0.0
    amps = {}
    for ch in ref['chains']:
        tip, base = ch['tip'], ch['base']
        p = clip.Wb[:, tip, :3, :3] @ rig.local[tip].mean(0) + clip.Wb[:, tip, :3, 3]
        Wp = clip.Wb[:, base]
        q = np.einsum('fji,fj->fi', Wp[:, :3, :3], p - Wp[:, :3, 3])
        amps[tip] = float(np.linalg.norm(q - q.mean(0), axis=1).max() / h)
    out['chain_amp'] = amps
    allv = np.concatenate([V[b] for b in rig.meshed], 1)
    out['jump'] = float(np.linalg.norm(np.diff(allv, axis=0), axis=2).max() / h) if clip.n > 1 else 0.0
    out['seam'] = float(np.linalg.norm(allv[-1] - allv[0], axis=1).max() / h)
    lowest = allv[..., 1].max(1)                                    # y is down
    out['sink'] = float((lowest.max() - ref['floor']) / h)
    out['lift_min'] = float((ref['floor'] - lowest.max()) / h)
    worst = [0.0, -1, -1]
    for f in range(0, clip.n, 2):
        for b, d in _nearest_gaps(rig, V, f).items():
            g = (d - ref['gap'][b]) / h
            if g > worst[0]:
                worst = [round(g, 4), b, f]
    out['tear'] = worst
    out['cross'] = crossings(rig, V, clip.n)
    if ref['body']:
        d = np.abs(elevation(clip.Wb[:, ref['body'], :3, :3]).mean(0) - ref['body_elev'])
        out['body_off'], out['body_bone'] = float(d.max()), int(ref['body'][int(d.argmax())])
    else:
        out['body_off'], out['body_bone'] = 0.0, -1
    r = clip.root - clip.root[0]
    out['root_exc'] = float(np.linalg.norm(r[:, [0, 2]], axis=1).max() / h)
    return out


def retimed_baseline(frames, slot, n):
    """The baseline clip as `battle_restore` makes it for a final clip of `n` ticks."""
    import battle_restore
    fr = [[list(map(int, b)) for b in f] for f in frames]
    count, tile = battle_restore.plan(slot, len(fr), n)
    if count == len(fr):
        return np.array(fr, float)
    samples, _ = battle_restore.retimed(fr, [], count - 1, tile)
    return np.array(samples, float)


def fidelity(final, base, slot, h):
    """(rotation error in degrees, root travel error in heights) against the retimed baseline, or None."""
    exp = retimed_baseline(base, slot, len(final))
    if exp.shape != final.shape:
        return None
    rot = angle(euler(final[..., 3:6]), euler(exp[..., 3:6]))
    return float(rot.max()), float(np.abs(final[:, 0, 6:9] - exp[:, 0, 6:9]).max() / h)


# ------------------------------------------------------------------ the species check
def _value(key, m, ref, tip=None):
    """The number a flag of `key` is about, larger is worse (for comparing our clip with the source's own)."""
    if key == 'live_field':
        return -m['chain_amp'][tip]
    if key == 'cross':
        return m['cross'][0] / (ref['cross'] + CROSS_ADD)
    if key == 'tear':
        return m['tear'][0]
    if key == 'scale':
        return float(np.abs(m['scale'] / 4096.0 - 1).max())
    return m.get(key, 0.0)


def check(F, A, M, slots=BATTLE, polished=()):
    """{slot: row} for a species: F, A, M are the Rigs of the final model, the baseline and main's final model. A row has
    `flags` (measured reasons), `keys` (the rule of each flag), `notes`, `source` ('main': main's own clip, else
    'changed'), `cause` (classify) and the numbers of the final clip, main's and the baseline's."""
    ref, ref_a = reference(M), reference(A)
    h = ref['h']
    field = {s: measure(Clip(M, *M.frames(s)), ref) for s in FIELD_MOVES if M.frames(s) is not None}
    rng_f, rng_a = np.zeros(F.nb), np.zeros(F.nb)
    rows = {}
    for s in slots:
        fF, fA, fM = F.frames(s), A.frames(s), M.frames(s)
        mF, mM = measure(Clip(F, *fF), ref), measure(Clip(M, *fM), ref)
        mA = measure(Clip(A, *fA), ref_a) if fA is not None else None      # the source's clip on the source's rig
        rng_f = np.maximum(rng_f, mF['bone_range'])
        if mA:
            rng_a = np.maximum(rng_a, mA['bone_range'])
        g = 1 if s in MOVES else 0
        flags, notes = [], []

        def flag(key, msg, tip=None):
            flags.append((key, msg, tip))
        same_main = fF[0].shape == fM[0].shape and np.array_equal(fF[0], fM[0])
        fid = fidelity(fF[0], fA[0], s, h) if fA is not None else None
        faithful = fid is not None and fid[0] <= FID_ROT and fid[1] <= FID_TR
        # 1 fidelity
        if same_main:
            notes.append('same clip as main')
        elif s in polished:
            notes.append('documented polish of the baseline')
        elif not faithful:
            flag('fidelity', f'fidelity: {fid and round(fid[0], 1)} deg, root {fid and round(fid[1], 3)} h off the baseline')
        # 2 liveness
        if mA:
            for tip, a in mA['chain_amp'].items():
                if a > LIVE_FLOOR and mF['chain_amp'][tip] < LIVE_KEEP * a:
                    flag('live_base', f'chain to {tip} still: {mF["chain_amp"][tip]:.3f} h, baseline {a:.3f}')
        if s in MOVES and field:
            for ch in ref['chains']:
                t = ch['tip']
                fa = max(m['chain_amp'][t] for m in field.values())
                sib = [mF['chain_amp'][c['tip']] for c in ref['chains'] if c['tip'] != t and c['kind'] == ch['kind']]
                if (fa > FIELD_SWING and mF['chain_amp'][t] < STILL_RATIO * fa and sib
                        and mF['chain_amp'][t] < SIBLING_RATIO * max(sib)):
                    flag('live_field', f'{ch["kind"]} {ch["bones"]} still: {mF["chain_amp"][t]:.3f} h, field gait '
                         f'{fa:.3f}, sibling {max(sib):.3f}', t)
        # 4 mesh
        if not mF['finite']:
            flag('finite', 'non-finite numbers')
        drawn = np.repeat(np.isin(np.arange(F.nb), F.meshed), 3)      # a bone with no piece draws nothing at any scale
        oF = np.abs(mF['scale'] / 4096.0 - 1).max(0) * drawn
        oM = np.abs(mM['scale'] / 4096.0 - 1).max(0) * drawn
        if ((oF > SCALE_MAX) & (oF > oM + SCALE_MAX)).any():
            b = int(np.argmax(oF - oM)) // 3
            flag('scale', f'scale of bone {b} off by {oF.max():.2f} (main {oM[3 * b:3 * b + 3].max():.2f})')
        if mF['jump'] > JUMP_MAX[g] or (mA and mF['jump'] > 1.25 * mA['jump'] + 0.05):
            flag('jump', f'vertex step {mF["jump"]:.3f} h a tick (source {mA and round(mA["jump"], 3)})')
        if fF[1] is not None and mF['seam'] > SEAM_MAX and mF['seam'] > mM['seam'] + 0.01:   # only a looping clip has a seam
            flag('seam', f'loop seam {mF["seam"]:.3f} h')
        if mF['tear'][0] > TEAR_MAX:
            flag('tear', f'piece {mF["tear"][1]} leaves the body by {mF["tear"][0]:.3f} h at tick {mF["tear"][2]} '
                 f'(source {mA and mA["tear"][0]})')
        if mF['cross'][0] > CROSS_RATIO * ref['cross'] + CROSS_ADD and mF['cross'][0] > mM['cross'][0] + CROSS_ADD:
            flag('cross', f'crossings {mF["cross"][0]:.0f} a tick (field idle {ref["cross"]:.0f}, main '
                 f'{mM["cross"][0]:.0f}; source {mA and round(mA["cross"][0])} against its idle {ref_a["cross"]:.0f})')
        # 5 posture
        if mF['body_off'] > BODY_ABS[g] or (mF['body_off'] > BODY_MAX and mF['body_off'] > mM['body_off'] + BODY_WORSE):
            flag('body_off', f'body bone {mF["body_bone"]} tipped {mF["body_off"]:.0f} deg off the field idle '
                 f'(main {mM["body_off"]:.0f})')
        if mF['sink'] > SINK_MAX and mF['sink'] > mM['sink'] + WORSE:
            flag('sink', f'under the floor {mF["sink"]:.3f} h (main {mM["sink"]:.3f})')
        if mF['lift_min'] > FLOAT_MAX and mF['lift_min'] > mM['lift_min'] + WORSE:
            flag('lift_min', f'floating {mF["lift_min"]:.3f} h (main {mM["lift_min"]:.3f})')
        # 6 motion
        if mF['n'] != mM['n']:
            if s in MOVES:
                flag('length', f'length {mF["n"]} ticks (main {mM["n"]})')
            else:
                notes.append(f'length {mF["n"]} ticks (main {mM["n"]})')
        if s in MOVES and mF['root_exc'] > LUNGE_MAX and mF['root_exc'] > mM['root_exc'] + LUNGE_WORSE:
            flag('root_exc', f'root excursion {mF["root_exc"]:.2f} h (main {mM["root_exc"]:.2f})')
        if mF['speed'] > SPEED_MAX[g] and mF['speed'] > FRANTIC * mM['speed']:
            flag('speed', f'frantic: {mF["speed"]:.1f} deg a tick (main {mM["speed"]:.1f})')
        # what the source's own clip on its own rig says about each flag
        own = []
        for key, _, tip in flags:
            if key in ('fidelity', 'live_base', 'length') or mA is None:
                own.append(False)
            else:
                vF, vA = _value(key, mF, ref, tip), _value(key, mA, ref_a, tip)
                own.append(vA >= (0.8 * vF if vF > 0 else 1.25 * vF - 0.01))
        for m in (mF, mM, mA):
            if m:
                m.pop('scale', None)
        rows[s] = dict(flags=[m for _, m, _ in flags], keys=[k for k, _, _ in flags], own=own, notes=notes,
                       source='main' if same_main else 'changed', fidelity=fid, faithful=faithful,
                       retimed=bool(fA is not None and len(fA[0]) != len(fF[0])), final=mF, main=mM, base=mA)
    # 3 bone map
    still = [b for b in range(1, F.nb) if rng_f[b] < STILL_DEG and rng_a[b] > BONEMAP_DEG]
    if still and set(slots) == set(BATTLE):
        for s in slots:
            rows[s]['flags'].append(f'bones {still} never rotate in the battle clips '
                                    f'(baseline {[round(rng_a[b]) for b in still]} deg)')
            rows[s]['keys'].append('bonemap')
            rows[s]['own'].append(False)
    for r in rows.values():
        r['cause'] = classify(r)
        r['verdict'] = verdict(r)
    return rows


def classify(row):
    """'pass'; 'main' (main's own clip, pre-existing); 'source' (the source's clip on its own rig has every flagged defect
    too); 'retime' (ours: the clip's new length); 'rig' (ours: the source's motion on our rig, or a pass after it)."""
    if not row['flags']:
        return 'pass'
    if row['source'] == 'main':
        return 'main'
    if all(row['own']):
        return 'source'
    return 'retime' if row['retimed'] else 'rig'


# how much worse than main's same slot a flagged number may be and still count as no worse (the flag's own units)
SAME_AS_MAIN = dict(cross=CROSS_ADD, tear=0.02, jump=0.05, seam=0.01, sink=0.05, lift_min=0.05, body_off=BODY_WORSE,
                    root_exc=0.5, speed=1.0)


def worse_than_main(row):
    """The flags of a row that main's same slot does not share: a changed clip with any of them goes back to main's.
    A scale flag the source's own clip shares is its effect (a puff, a squash) and counts as kept."""
    out = []
    for key, msg, own in zip(row['keys'], row['flags'], row['own']):
        if key == 'scale' and own:
            continue
        if key in SAME_AS_MAIN:
            f, m = row['final'], row['main']
            vf = f[key][0] if key in ('cross', 'tear') else f[key]
            vm = m[key][0] if key in ('cross', 'tear') else m[key]
            if vf <= vm + SAME_AS_MAIN[key]:
                continue
        out.append(msg)
    return out


def verdict(row):
    """'pass', 'main' (main's own clip), 'kept' (flagged, but no worse than main's) or 'fail'."""
    if not row['flags']:
        return 'pass'
    if row['source'] == 'main':
        return 'main'
    return 'fail' if worse_than_main(row) else 'kept'


def species_check(final, base, main, bones, slots=BATTLE, polished=()):
    """check() on MMD bytes and the species' skeleton ([[object, parent], ...])."""
    return check(Rig.from_mmd(final, bones), Rig.from_mmd(base, bones), Rig.from_mmd(main, bones), slots, polished)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('check')
    c.add_argument('final')
    c.add_argument('base')
    c.add_argument('main')
    c.add_argument('species_json')
    c.add_argument('--slots', nargs='*', type=int, default=list(BATTLE))
    c.add_argument('--polished', nargs='*', type=int, help='leaned or rebuilt slots (default: battle_qa.polished_slots of the species json\'s id)')
    c.add_argument('--json')
    a = ap.parse_args()
    rd = lambda p: open(p, 'rb').read()
    with open(a.species_json) as fh:
        species = json.load(fh)
    bones = species['model']['skeleton']
    sid = int(os.path.basename(a.species_json).split('-')[0])
    polished = a.polished if a.polished is not None else polished_slots(sid)
    rows = species_check(rd(a.final), rd(a.base), rd(a.main), bones, a.slots, polished)
    for s, r in rows.items():
        print(f'slot {s:#x}: {r["verdict"]} ({r["cause"]}) ' + '; '.join(r['flags'] + r['notes']))
    if a.json:
        with open(a.json, 'w') as fh:
            json.dump(rows, fh, indent=1, default=lambda o: o.tolist() if hasattr(o, 'tolist') else str(o))
    sys.exit(1 if any(r['verdict'] == 'fail' for r in rows.values()) else 0)


if __name__ == '__main__':
    main()
