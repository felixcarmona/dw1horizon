#!/usr/bin/env python3
"""Retarget MMD animations between different skeletons (explicit bone map).

`mmd.py transplant` and `import-anim` need the same skeleton. This moves the motion of
some bones of a SOURCE model onto chosen bones of a TARGET model whose hierarchy, bone
count and rest pose differ (Vegiemon's vines onto Cherrymon's branch arms, say).

How: both models face -Z with Y down, so a motion can be carried as a rotation in model
space. For every tick, each mapped source bone S gives its world-space delta from the
source's reference pose (slot 0, first tick, unless --ref-slot):

    D(S, t) = Wsrc(S, t) · Wsrc_ref(S)^T

and the target bone T is posed so that its world rotation is D · Wtgt_rest(T) (it turns
the way S turned, from its own rest orientation, whatever its local axes and its
parent are). The local rotation written for T is Wtgt(parent)^T · that, with the
target's parents posed first; unmapped target bones keep their rest rotation (or what
the caller layers on top). A weight w (T=S@w) scales the delta's angle (0..1 damps a
whip-like source, >1 exaggerates). T=S1:S2 carries a direction instead of a rotation:
the chord from source joint S1 to joint S2 (several pieces of a vine at once) turns
by the smallest rotation that takes its reference direction to the current one, and
T turns the same way (no twist about the chord). Translations are not carried, except the hips:
--hips T=S*k moves target bone T by k times source bone S's offset from its reference
position (a hop, a squat), and root motion (bone 0) is scaled by --root-scale.

Picking source bones for a shorter chain: map every other source bone (a 6-piece vine
onto a 3-piece arm: 8, 10, 12 -> arm, forearm, claw). World deltas already contain the
rotations of the skipped pieces, so the chain bends as much in total.

Sounds come from the source animation (`--sounds`; bank 4 is the voice of whoever plays
it); texture moves do not (they belong to the source's texture).

Usage (from the repository root):
  python3 tools/retarget.py SRC.MMD TGT.MMD OUT.MMD --slot SRC_SLOT[:TGT_SLOT] [...]
          --map T=S[@W] | T=S1:S2[@W] [...] [--hips T=S*K] [--root-scale K] [--ref-slot N]
          [--sounds] [--tol 1] [--src-type T] [--tgt-type T]

Library: `transfer(src, src_type, slot, tgt_type, tgt_rest, bone_map, ...)` returns
per-tick local rotations (engine units) of the mapped target bones, hips offsets, root
motion, the loop sample and the source events, for callers that layer more motion on
top (content/models/cherrymon/anims.py).

Standard library only (uses tools/mmd.py). Limits: a mapped bone follows its source in
model space, so a target bone whose parent is not mapped moves with that parent's rest
(or layered) rotation underneath; mirrored pairs need their own source bones (left vine
-> left arm); bones that scale are not handled (scale is kept at 1).
"""
import argparse
from collections import OrderedDict
import math
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mmd  # noqa: E402

UNITS = 4096 / (2 * math.pi)


def m3mul(a, b):
    return [[sum((r[0] * b[0][j], r[1] * b[1][j], r[2] * b[2][j])) for j in range(3)] for r in a]


def m3t(a):
    return [[a[j][i] for j in range(3)] for i in range(3)]


def rot_of(v):
    """Rotation matrix of an engine pose entry (sx sy sz rx ry rz tx ty tz), scale ignored."""
    return mmd.rot_matrix(*v[3:6])


def world_rots(skel, pose):
    """World rotation of every bone (bone 0 included: the entity's facing)."""
    out = [None] * len(skel)

    def get(b):
        if out[b] is None:
            R = rot_of(pose[b])
            par = skel[b][1]
            out[b] = m3mul(get(par), R) if par >= 0 else R
        return out[b]
    for b in range(len(skel)):
        get(b)
    return out


def world_pos(skel, pose):
    mats = [None] * len(skel)

    def get(b):
        if mats[b] is None:
            v = pose[b]
            R = rot_of(v)
            L = [R[i] + [v[6 + i]] for i in range(3)] + [[0, 0, 0, 1]]
            par = skel[b][1]
            mats[b] = mmd.mat_mul(get(par), L) if par >= 0 else L
        return mats[b]
    return [[get(b)[i][3] for i in range(3)] for b in range(len(skel))]


def world_transform(skel, pose):
    """World rotations and positions together, with the same sums as above.

    Retargeting with hips or chords needs both. Chaining an affine transform
    requires nine rotation cells and three position cells; the constant bottom
    row need not be multiplied, nor the rotations calculated a second time.
    """
    rotations, positions = [None] * len(skel), [None] * len(skel)

    def get(b):
        if rotations[b] is not None:
            return
        v = pose[b]
        local = rot_of(v)
        par = skel[b][1]
        if par < 0:
            rotations[b], positions[b] = local, v[6:9]
        else:
            get(par)
            parent, origin = rotations[par], positions[par]
            rotations[b] = m3mul(parent, local)
            positions[b] = [sum((r[0] * v[6], r[1] * v[7], r[2] * v[8], origin[i]))
                            for i, r in enumerate(parent)]
    for b in range(len(skel)):
        get(b)
    return rotations, positions


def axis_angle(R):
    tr = R[0][0] + R[1][1] + R[2][2]
    ang = math.acos(max(-1.0, min(1.0, (tr - 1) / 2)))
    if ang < 1e-9:
        return [1.0, 0.0, 0.0], 0.0
    x, y, z = R[2][1] - R[1][2], R[0][2] - R[2][0], R[1][0] - R[0][1]
    n = math.sqrt(x * x + y * y + z * z)
    if n < 1e-9:                       # 180 degrees: axis from the diagonal
        x = math.sqrt(max(0.0, (R[0][0] + 1) / 2))
        y = math.copysign(math.sqrt(max(0.0, (R[1][1] + 1) / 2)), R[0][1] or 1)
        z = math.copysign(math.sqrt(max(0.0, (R[2][2] + 1) / 2)), R[0][2] or 1)
        n = math.sqrt(x * x + y * y + z * z) or 1
    return [x / n, y / n, z / n], ang


def from_axis_angle(a, ang):
    x, y, z = a
    c, s, C = math.cos(ang), math.sin(ang), 1 - math.cos(ang)
    return [[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
            [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
            [z * x * C - y * s, z * y * C + x * s, c + z * z * C]]


def swing(a, b):
    """Smallest rotation taking direction a to direction b."""
    na = math.sqrt(sum(x * x for x in a)) or 1
    nb = math.sqrt(sum(x * x for x in b)) or 1
    a = [x / na for x in a]
    b = [x / nb for x in b]
    ax = [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
    s = math.sqrt(sum(x * x for x in ax))
    c = sum(x * y for x, y in zip(a, b))
    ang = math.atan2(s, c)
    if s < 1e-9:
        return [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    return from_axis_angle([x / s for x in ax], ang)


def scale_rot(R, w):
    if w == 1.0:
        return R
    a, ang = axis_angle(R)
    return from_axis_angle(a, ang * w)


def play(anim, nb, slot, max_ticks=6000):
    """Per-tick poses with bone 0's accumulated root motion (in bone 0's frame), the loop
    sample and the events (sample, kind, instruction)."""
    p = mmd.AnimPlayer(anim, nb, slot)
    out, root = [], [0, 0, 0]
    while len(out) < max_ticks and p.tick(stop_at_infinite_loop=True):
        root = [r + b for r, b in zip(root, p.base)]
        snap = [list(v) for v in p.pose]
        snap[0][6:9] = list(root)
        out.append(snap)
    return out, p.loop_sample(), list(p.events)


def normalize_near_unit_support(pose, bones, tolerance=0):
    """Normalize at most one fixed-point unit of support-chain scale error.

    Validate the complete selection before mutation. Meaningful source scale
    remains unsupported; callers must separately bound actual mesh displacement.
    """
    if tolerance not in (0, 1):
        raise ValueError('support scale tolerance must be zero or one')
    bones = tuple(bones)
    if any(b < 0 or b >= len(pose) for b in bones):
        raise ValueError('invalid support bone')
    if any(abs(v - 4096) > tolerance for b in bones for v in pose[b][:3]):
        raise ValueError('meaningful scale on support chain')
    changed = [b for b in bones if pose[b][:3] != [4096]*3]
    for b in changed:
        pose[b][:3] = [4096]*3
    return changed


def rest_pose(m, nb, slot=0):
    """First-tick pose of a slot (bone 0 cleared)."""
    smp, _, _ = play(m.anims.anims[m.anims.table[slot]], nb, slot, max_ticks=1)
    pose = [list(v) for v in smp[0]]
    pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
    return pose


def transfer(src, src_type, slot, tgt_type, tgt_rest, bone_map, hips=None, root_scale=1.0,
             ref_slot=0, layered=None):
    """Retargets one source slot. bone_map: {target bone: (source bone, weight)}.
    tgt_rest: target pose list (26 entries of 9 values) used as rest. hips: (target bone,
    source bone, k). layered(t) -> {target bone: 3x3 local rotation} for unmapped target
    bones (applied before the mapped children are solved), or None.
    Returns dict(rot={T: [(rx, ry, rz) per tick]}, hips=[(dx, dy, dz)], root=[(x, y, z)],
    loop=loop sample, events=[...], n=ticks)."""
    e = mmd.exe()
    snb, tnb = e.bone_count[src_type], e.bone_count[tgt_type]
    sskel, tskel = e.skeleton[src_type], e.skeleton[tgt_type]
    smp, loop, events = play(src.anims.anims[src.anims.table[slot]], snb, slot)
    ref = rest_pose(src, snb, ref_slot)
    need_positions = hips is not None or any(isinstance(s, tuple) for s, _ in bone_map.values())
    Wref, Pref = world_transform(sskel, ref) if need_positions else (world_rots(sskel, ref), None)
    chord = lambda P, s1, s2: [P[s2][i] - P[s1][i] for i in range(3)]
    Wt_rest = world_rots(tskel, tgt_rest)
    inverse_ref = {s: m3t(Wref[s]) for s, _ in bone_map.values() if not isinstance(s, tuple)}
    rest_local = [rot_of(v) for v in tgt_rest]
    order = sorted(range(tnb), key=lambda b: depth(tskel, b))
    out = dict(rot={b: [] for b in bone_map}, hips=[], root=[], loop=loop, events=events, n=len(smp))
    prev = {b: None for b in bone_map}
    # Long donor strides repeat the same poses thousands of times before the
    # encoder applies its length/loop rules. Cache only identical solver inputs,
    # including the previous Euler solution and any layered motion. Root travel
    # is accumulated separately. Bound this to 128 frames, within one slot.
    frame_cache = OrderedDict()
    for t, pose in enumerate(smp):
        p0 = [list(v) for v in pose]
        root = p0[0][6:9]
        p0[0] = [4096, 4096, 4096] + p0[0][3:6] + [0, 0, 0]
        lay = layered(t) if layered else {}
        key = (tuple(tuple(v[3:9]) for v in p0),
               tuple((b, struct.pack('<9d', *(x for row in matrix for x in row))) for b, matrix in lay.items()),
               tuple(None if prev[b] is None else struct.pack('<3d', *prev[b]) for b in bone_map))
        if key in frame_cache:
            rotations, position = frame_cache[key]
            frame_cache.move_to_end(key)
            for b, eul in rotations:
                prev[b] = eul
                out['rot'][b].append(eul)
            if hips:
                out['hips'].append(position)
            out['root'].append(tuple(root_scale * x for x in root))
            continue
        Ws, Ps = world_transform(sskel, p0) if need_positions else (world_rots(sskel, p0), None)
        Wt = [None] * tnb
        for b in order:
            par = tskel[b][1]
            Wp = Wt[par] if par >= 0 else [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
            if b in bone_map:
                s, w = bone_map[b]
                if isinstance(s, tuple):      # chord: the direction from joint s1 to joint s2
                    D = scale_rot(swing(chord(Pref, *s), chord(Ps, *s)), w)
                else:
                    D = scale_rot(m3mul(Ws[s], inverse_ref[s]), w)
                Wt[b] = m3mul(D, Wt_rest[b])
                L = m3mul(m3t(Wp), Wt[b])
                eul = mmd.matrix_euler(L, prev[b])
                prev[b] = eul
                out['rot'][b].append(tuple(eul))
            else:
                L = lay.get(b) or rest_local[b]
                Wt[b] = m3mul(Wp, L)
        if hips:
            tb, sb, k = hips
            out['hips'].append(tuple(k * (Ps[sb][i] - Pref[sb][i]) for i in range(3)))
        frame_cache[key] = (tuple((b, out['rot'][b][-1]) for b in bone_map),
                            out['hips'][-1] if hips else None)
        if len(frame_cache) > 128:
            frame_cache.popitem(last=False)
        out['root'].append(tuple(root_scale * x for x in root))
    return out


def depth(skel, b):
    d = 0
    while skel[b][1] >= 0:
        b = skel[b][1]
        d += 1
    return d


def chain_length(skel, positions, root, end):
    """Anatomical path length, independent of how flexed the reference limb is."""
    length = 0.0
    child = end
    while child != root:
        parent = skel[child][1]
        if parent < 0:
            raise ValueError('limb endpoint is not a descendant of its root')
        length += math.dist(positions[parent], positions[child])
        child = parent
    return length


def align_reference(tskel, target, sskel, source, chains, keep_world=(), sagittal=False):
    """Calibrate explicit homologous chord directions without changing bone lengths."""
    target = [list(b) for b in target]
    original = world_rots(tskel, target)
    native_positions = world_pos(tskel, target)
    sp = world_pos(sskel, source)
    def set_world(b, desired):
        parent = tskel[b][1]
        rotations = world_rots(tskel, target)
        local = m3mul(m3t(rotations[parent]), desired) if parent >= 0 else desired
        target[b][3:6] = [round(x) for x in mmd.matrix_euler(local)]
    for t, tc, s, sc in sorted(chains, key=lambda x: depth(tskel, x[0])):
        ancestor = tc
        while ancestor >= 0 and ancestor != t:
            ancestor = tskel[ancestor][1]
        if ancestor != t or tc == t:
            raise ValueError('reference target chord must follow a descendant')
        tp = world_pos(tskel, target)
        tv = [tp[tc][i]-tp[t][i] for i in range(3)]
        sv = [sp[sc][i]-sp[s][i] for i in range(3)]
        if sagittal:
            # Match flexion while retaining native lateral stance geometry.
            lateral = native_positions[tc][0]-native_positions[t][0]
            reach = math.sqrt(max(0, sum(x*x for x in tv)-lateral*lateral))
            source_reach = math.hypot(sv[1], sv[2])
            if min(reach, source_reach) < 1e-9:
                raise ValueError('reference chord has no sagittal direction')
            sv = [lateral, sv[1]*reach/source_reach, sv[2]*reach/source_reach]
        tn = math.sqrt(sum(x*x for x in tv))
        sn = math.sqrt(sum(x*x for x in sv))
        if min(tn, sn) < 1e-9:
            raise ValueError('reference chord has zero length')
        cosine = sum(x*y for x, y in zip(tv, sv))/(tn*sn)
        if cosine < -1+1e-9:
            # Antiparallel chords need a defined perpendicular half-turn axis.
            axis_index = min(range(3), key=lambda i: abs(tv[i]))
            basis = [int(i == axis_index) for i in range(3)]
            axis = [tv[1]*basis[2]-tv[2]*basis[1], tv[2]*basis[0]-tv[0]*basis[2], tv[0]*basis[1]-tv[1]*basis[0]]
            norm = math.sqrt(sum(x*x for x in axis))
            rotation = from_axis_angle([x/norm for x in axis], math.pi)
        else:
            rotation = swing(tv, sv)
        desired = m3mul(rotation, world_rots(tskel, target)[t])
        set_world(t, desired)
    for b in sorted(keep_world, key=lambda b: depth(tskel, b)):
        set_world(b, original[b])
    return target


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src')
    ap.add_argument('tgt')
    ap.add_argument('out')
    ap.add_argument('--slot', action='append', required=True, help='SRC_SLOT[:TGT_SLOT]')
    ap.add_argument('--map', action='append', required=True, help='T=S[@W]')
    ap.add_argument('--hips', help='T=S*K')
    ap.add_argument('--root-scale', type=float, default=1.0)
    ap.add_argument('--ref-slot', type=lambda s: int(s, 0), default=0)
    ap.add_argument('--target-ref-slot', type=lambda s: int(s, 0), default=0)
    ap.add_argument('--align-reference', action='append', default=[], help='Target joint:descendant=source joint:descendant')
    ap.add_argument('--keep-reference-world', action='append', type=int, default=[], help='Preserve end-effector reference orientation after chord calibration')
    ap.add_argument('--reference-sagittal', action='store_true', help='Calibrate flexion while preserving native lateral chord components')
    ap.add_argument('--sounds', action='store_true')
    ap.add_argument('--tol', type=int, default=1)
    ap.add_argument('--src-type', type=lambda s: int(s, 0))
    ap.add_argument('--tgt-type', type=lambda s: int(s, 0))
    a = ap.parse_args()
    e = mmd.exe()
    src = mmd.MMD.load(a.src, a.src_type)
    tgt = mmd.MMD.load(a.tgt, a.tgt_type)
    tnb = e.bone_count[tgt.type]
    bone_map = {}
    for spec in a.map:
        t, s = spec.split('=')
        w = 1.0
        if '@' in s:
            s, w = s.split('@')
        if ':' in s:
            s1, s2 = s.split(':')
            bone_map[int(t, 0)] = ((int(s1, 0), int(s2, 0)), float(w))
        else:
            bone_map[int(t, 0)] = (int(s, 0), float(w))
    hips = None
    if a.hips:
        t, rest = a.hips.split('=')
        s, k = rest.split('*')
        hips = (int(t, 0), int(s, 0), float(k))
    trest = rest_pose(tgt, tnb, a.target_ref_slot)
    if a.align_reference:
        chains = [tuple(int(x, 0) for side in item.split('=') for x in side.split(':')) for item in a.align_reference]
        if any(len(chain) != 4 for chain in chains):
            ap.error('reference alignment requires T:TC=S:SC')
        trest = align_reference(e.skeleton[tgt.type], trest, e.skeleton[src.type],
                                rest_pose(src, e.bone_count[src.type], a.ref_slot), chains, a.keep_reference_world, a.reference_sagittal)
    for spec in a.slot:
        ss, _, ts = spec.partition(':')
        ss = int(ss, 0)
        ts = int(ts, 0) if ts else ss
        r = transfer(src, src.type, ss, tgt.type, trest, bone_map, hips, a.root_scale, a.ref_slot)
        smp = []
        for t in range(r['n']):
            pose = [list(v) for v in trest]
            for b, seq in r['rot'].items():
                pose[b][3:6] = [round(x) for x in seq[t]]
            if hips:
                hb = hips[0]
                pose[hb][6:9] = [round(trest[hb][6 + i] + r['hips'][t][i]) for i in range(3)]
            pose[0][6:9] = [round(x) for x in r['root'][t]]
            smp.append(pose)
        mmd.close_loop(smp, r['loop'])
        ev = []
        if a.sounds:
            ev = [(k, 'sound', dict(bank=c['bank'], note=c['note'])) for k, kind, c in r['events'] if kind == 'sound']
        anim = mmd.encode_anim(smp, tnb, r['loop'], ev, tol=a.tol)
        while len(tgt.anims.table) <= ts:
            tgt.anims.table.append(None)
        tgt.anims.table[ts] = len(tgt.anims.anims)
        tgt.anims.anims.append(anim)
        print(f'slot {ss:#x} -> {ts:#x}: {r["n"]} ticks, loop {r["loop"]}')
    # drop animations no slot uses any more
    used = sorted(set(x for x in tgt.anims.table if x is not None))
    remap = {old: new for new, old in enumerate(used)}
    tgt.anims.anims = [tgt.anims.anims[i] for i in used]
    tgt.anims.table = [remap[x] if x is not None else None for x in tgt.anims.table]
    data = tgt.build()
    open(a.out, 'wb').write(data)
    print(f'{a.out}: {len(data)} bytes')


if __name__ == '__main__':
    main()
