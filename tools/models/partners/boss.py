"""Shared helpers for the partner models of Machinedramon, Jijimon and Analogman.

Each of the three is an NPC whose model has only the few animations its scenes play.
Its partner model is a separate file (MUGP/JIJP/ANLP.MMD, loaded only for the partner:
see the partner-only model hook in model.c), so the NPC keeps its original MMD and
its scenes and heap use do not change. The partner file is the NPC's mesh with:

  - the NPC's own animations kept where they serve a partner slot as they are
    (idle, walk; Machinedramon's battle and technique animations);
  - every other slot a partner uses retargeted from a partner Digimon with a similar
    body (tools/retarget.py: each mapped bone turns, in model space, the way the source
    bone turns from its idle pose), with layered per-character touches on top.

Conventions are the engine's (docs/mods/models.md § 2.2): a pose is, per bone,
[sx sy sz rx ry rz tx ty tz]; rotations in 1/4096 of a turn, Y down, facing -Z.
"""
import glob
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import mmd  # noqa: E402
import retarget  # noqa: E402

PARTNER_MODEL_BUFFER = 0x18800
U = 4096 / 360.0          # engine units per degree

# every slot the 64 partner models have (the union), see cherrymon/clips.py
PARTNER_SLOTS = ([0, 1, 2, 3, 4, 5] + list(range(7, 0x14)) + list(range(0x15, 0x1A)) + [0x1B] +
                 list(range(0x21, 0x26)) + list(range(0x28, 0x2D)))


def exe():
    return mmd.exe()


def path_of(name):
    return glob.glob(os.path.join(ROOT, f'extracted/CHDAT/MMD*/{name}.MMD'))[0]


def load(name):
    e = exe()
    return mmd.MMD.load(path_of(name), e.names.index(name))


def play(m, slot):
    """Per-tick samples of a slot (bone 0 tx..tz = accumulated root motion), loop sample,
    events [(tick, 'sound'|'tex', dict)]."""
    e = exe()
    smp, loop, ev = retarget.play(m.anims.anims[m.anims.table[slot]], e.bone_count[m.type], slot)
    events = []
    for k, kind, c in ev:
        if kind == 'sound':
            events.append((k, 'sound', dict(bank=c['bank'], note=c['note'])))
        elif kind == 'tex':
            events.append((k, 'tex', dict(src=c['src'], size=c['size'], dst=c['dst'])))
    return smp, loop, events


def rest(m, slot=0):
    return retarget.rest_pose(m, exe().bone_count[m.type], slot)


def retarget_slot(src, slot, tgt_type, trest, bone_map, hips=None, root_scale=1.0, sounds=True,
                  layer=None, ref_slot=0):
    """Retargets source slot `slot` onto the target skeleton.
    bone_map {target bone: (source bone | (s1, s2), weight)}; hips (target bone, source bone, k).
    layer(t, pose, info) may edit the per-tick pose list in place (engine units); info has
    the source's per-tick poses ('src') and the transfer result ('r').
    Returns (samples, loop sample, events)."""
    r = retarget.transfer(src, src.type, slot, tgt_type, trest, bone_map, hips, root_scale, ref_slot)
    ssmp, _, sev = retarget.play(src.anims.anims[src.anims.table[slot]], exe().bone_count[src.type], slot)
    smp = []
    for t in range(r['n']):
        pose = [list(v) for v in trest]
        for b, seq in r['rot'].items():
            pose[b][3:6] = [round(x) for x in seq[t]]
        if hips:
            hb = hips[0]
            pose[hb][6:9] = [round(trest[hb][6 + i] + r['hips'][t][i]) for i in range(3)]
        pose[0] = [4096, 4096, 4096] + list(ssmp[t][0][3:6]) + [round(x) for x in r['root'][t]]
        if layer:
            layer(t, pose, dict(src=ssmp, r=r, n=r['n']))
        smp.append(pose)
    mmd.close_loop(smp, r['loop'])
    ev = []
    if sounds:
        ev = [(k, 'sound', dict(bank=c['bank'], note=c['note'])) for k, kind, c in r['events']
              if kind == 'sound']
    return smp, r['loop'], ev


class Builder:
    """Collects slot -> animation for one partner model (identical animations shared)."""

    def __init__(self, mesh_mmd, nslots):
        self.m = mesh_mmd
        self.nb = exe().bone_count[mesh_mmd.type]
        self.sec = mmd.AnimSection()
        self.sec.table = [None] * nslots
        self.keys = {}

    def put_anim(self, slot, anim):
        key = anim.build()
        if key not in self.keys:
            self.keys[key] = len(self.sec.anims)
            self.sec.anims.append(anim)
        self.sec.table[slot] = self.keys[key]

    def put(self, slot, samples, loop, events, tol=1):
        anim = mmd.encode_anim(samples, self.nb, loop, events, tol=tol)
        self.put_anim(slot, anim)
        return anim

    def keep(self, slot, src_slot=None):
        """The mesh model's own animation (unchanged bytes)."""
        a = self.m.anims.anims[self.m.anims.table[slot if src_slot is None else src_slot]]
        self.put_anim(slot, a)

    def share(self, slot, other):
        self.sec.table[slot] = self.sec.table[other]

    def write(self, out_path, required, label):
        missing = [s for s in required if self.sec.table[s] is None]
        assert not missing, f'slots without animation: {[hex(s) for s in missing]}'
        out = mmd.MMD()
        out.tmd, out.anims = self.m.tmd, self.sec
        data = out.build()
        if not os.environ.get("NPCC_PREVIEW"):
            assert len(data) <= PARTNER_MODEL_BUFFER, f"{len(data)} bytes > PARTNER_MODEL_BUFFER"
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        open(out_path, 'wb').write(data)
        used = sum(x is not None for x in self.sec.table)
        print(f'{out_path}: {label}, {len(self.sec.anims)} animations in {used} slots, '
              f'{len(data)} bytes (PARTNER_MODEL_BUFFER {PARTNER_MODEL_BUFFER}, '
              f'{PARTNER_MODEL_BUFFER - len(data)} free)')
        return data


def resample(smp, loop, events, factor):
    """Time-stretch per-tick samples by `factor` (> 1 slower), interpolating linearly (root
    motion included); events move with it. Loops keep their start (scaled)."""
    n = len(smp)
    m = max(2, round((n - 1) * factor) + 1)
    out = []
    for i in range(m):
        x = i / factor
        a = min(int(x), n - 1)
        b = min(a + 1, n - 1)
        u = x - a
        out.append([[round(va[c] + (vb[c] - va[c]) * u) for c in range(9)] for va, vb in zip(smp[a], smp[b])])
    lp = None if loop is None else min(m - 2, round(loop * factor))
    ev = [(min(m - 1, round(k * factor)), kind, c) for k, kind, c in events]
    return out, lp, ev


def deg(x):
    return round(x * U)


def report(builder):
    """Bytes per slot (shared animations listed once)."""
    seen = {}
    for s, k in enumerate(builder.sec.table):
        if k is None:
            continue
        seen.setdefault(k, []).append(s)
    for k, slots in sorted(seen.items(), key=lambda kv: -len(builder.sec.anims[kv[0]].build())):
        print(f'  {len(builder.sec.anims[k].build()):6d}  ' + ' '.join(hex(s) for s in slots))



def lowest_points(m, pose):
    """Lowest world y (largest, Y is down) of the mesh in a pose (bone 0 ignored)."""
    e = exe()
    sk = e.skeleton[m.type]
    nb = len(sk)
    mats = [None] * nb

    def get(b):
        if mats[b] is None:
            v = pose[b] if b else [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
            R = retarget.rot_of(v)
            L = [R[i] + [v[6 + i]] for i in range(3)] + [[0, 0, 0, 1]]
            p = sk[b][1]
            mats[b] = mmd.mat_mul(get(p), L) if p >= 0 else L
        return mats[b]
    low = -1e9
    for b in range(nb):
        o = sk[b][0]
        if o < 0:
            continue
        M = get(b)
        for v in m.tmd.obj_verts(o):
            y = M[1][0] * v[0] + M[1][1] * v[1] + M[1][2] * v[2] + M[1][3]
            low = max(low, y)
    return low


def ground_clamp(m, smp, allow=6, ref=None):
    """Lifts the hips (bone 1) on the ticks where the mesh would go more than `allow`
    units below the ground the rest pose stands on (retargeted lying-down poses from a
    slimmer source sink into the floor)."""
    floor = lowest_points(m, ref if ref is not None else smp[0])
    floor = max(floor, 0)
    lifts = []
    for pose in smp:
        d = lowest_points(m, pose) - floor
        lifts.append(max(0, d - allow))
    # smooth the lift so it does not pop (max with neighbours, then a 3-tap average)
    n = len(lifts)
    lifts = [max(lifts[max(0, i - 2):i + 3]) for i in range(n)]
    lifts = [(lifts[max(0, i - 1)] + 2 * lifts[i] + lifts[min(n - 1, i + 1)]) / 4 for i in range(n)]
    for pose, h in zip(smp, lifts):
        pose[1][7] -= round(h)
    return max(lifts) if lifts else 0


def _world_mats(sk, pose):
    nb = len(sk)
    mats = [None] * nb

    def get(b):
        if mats[b] is None:
            v = pose[b] if b else [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
            R = retarget.rot_of(v)
            L = [R[i] + [v[6 + i]] for i in range(3)] + [[0, 0, 0, 1]]
            p = sk[b][1]
            mats[b] = mmd.mat_mul(get(p), L) if p >= 0 else L
        return mats[b]
    for b in range(nb):
        get(b)
    return mats


def _subtree(sk, root):
    out = {root}
    changed = True
    while changed:
        changed = False
        for b, (_, p) in enumerate(sk):
            if p in out and b not in out:
                out.add(b)
                changed = True
    return out


def _low(m, sk, mats, bones):
    low = -1e9
    for b in bones:
        o = sk[b][0]
        if o < 0:
            continue
        M = mats[b]
        for v in m.tmd.obj_verts(o):
            low = max(low, M[1][0] * v[0] + M[1][1] * v[1] + M[1][2] * v[2] + M[1][3])
    return low


def lift_chains(m, smp, chains, floor=None, allow=4, max_deg=70):
    """Keeps limbs out of the floor: for each chain root (a shoulder, the tail base), on the
    ticks where that limb's mesh goes more than `allow` below the floor, its rotation gets
    the smallest extra turn (about one local axis, the direction that lifts it) that
    clears the floor. The extra turn is eased over neighbouring ticks so it does not pop."""
    sk = exe().skeleton[m.type]
    if floor is None:
        floor = max(0, lowest_points(m, smp[0]))
    for root in chains:
        bones = _subtree(sk, root)
        need = []
        for pose in smp:
            mats = _world_mats(sk, pose)
            if _low(m, sk, mats, bones) <= floor + allow:
                need.append(None)
                continue
            best = None
            for c in range(3):
                for sgn in (1, -1):
                    for d in range(2, max_deg + 1, 2):
                        trial = [list(v) for v in pose]
                        trial[root][3 + c] += sgn * deg(d)
                        if _low(m, sk, _world_mats(sk, trial), bones) <= floor + allow:
                            if best is None or d < best[2]:
                                best = (c, sgn, d)
                            break
            need.append(best)
        # one axis/sign per slot (the commonest), angle per tick, eased
        picks = [x for x in need if x]
        if not picks:
            continue
        # rule: on equal counts the pair needed first (a set's order of tuples follows their hashes, which differ
        # between 64- and 32-bit Pythons: Pyodide's picked the other pair of a tie, MUGP.MMD came out 20 bytes longer)
        c, sgn = max(dict.fromkeys(x[:2] for x in picks), key=lambda k: sum(1 for x in picks if x[:2] == k))
        ang = [0.0] * len(smp)
        for i, pose in enumerate(smp):
            if need[i] is None:
                continue
            for d in range(0, max_deg + 1, 2):
                trial = [list(v) for v in pose]
                trial[root][3 + c] += sgn * deg(d)
                if _low(m, sk, _world_mats(sk, trial), bones) <= floor + allow:
                    break
            ang[i] = d
        n = len(ang)
        ang = [max(ang[max(0, i - 2):i + 3]) for i in range(n)]
        ang = [(ang[max(0, i - 1)] + 2 * ang[i] + ang[min(n - 1, i + 1)]) / 4 for i in range(n)]
        for pose, a in zip(smp, ang):
            pose[root][3 + c] += sgn * deg(a)


def key_every(smp, loop, step, extra=()):
    """Keeps the poses of every `step`-th tick (and the first, the last, the loop start and
    `extra` ticks) and interpolates linearly in between, as an animator's keys: the engine
    interpolates keyframes linearly anyway, and fewer distinct speeds mean fewer bytes."""
    n = len(smp)
    if step <= 1 or n < 3:
        return smp
    ks = sorted(set([0, n - 1] + ([loop] if loop is not None else []) + list(extra) +
                    list(range(0, n, step))))
    out = []
    for t in range(n):
        if t in ks:
            out.append([list(v) for v in smp[t]])
            continue
        a = max(k for k in ks if k < t)
        b = min(k for k in ks if k > t)
        u = (t - a) / (b - a)
        pose = [[round(x + (y - x) * u) for x, y in zip(va, vb)] for va, vb in zip(smp[a], smp[b])]
        pose[0][6:9] = smp[t][0][6:9]          # root motion stays per tick
        out.append(pose)
    return out
