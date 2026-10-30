#!/usr/bin/env python3
"""Keeps the feet of a walk clip flat: numbers first, then the fix.

  footfix.py check MMD TYPE [--slots 2 3 4] [--feet 4 7]
        per slot and foot: the largest angle (degrees) between the foot's world orientation and the idle's, over the clip,
        and how many ticks it is over 30 degrees; also the toe direction against the idle's (a foot "backwards" is > 90)
  footfix.py plant IN.MMD OUT.MMD TYPE [--slots 2 3 4 0x23 0x24] [--feet 4 7]
        rewrites the feet's keys of those clips so that each foot's world orientation is the idle's; the shin and the body keep their motion
"""
import argparse, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mmd, animsheet, retarget


def trace_angle(A, B):
    t = sum(A[i][j] * B[i][j] for i in range(3) for j in range(3))
    return math.degrees(math.acos(max(-1.0, min(1.0, (t - 1) / 2))))


def m3t(a): return [[a[j][i] for j in range(3)] for i in range(3)]


def foot_dirs(m, nb, skel, pose, b):
    """World rotation of bone b and its toe direction (centroid of its object's vertices from the bone origin)."""
    mats = mmd.bone_matrices(m, pose)
    M = mats[b]
    vs = m.tmd.obj_verts(skel[b][0]) if skel[b][0] >= 0 else []
    if not vs:
        return None
    cx = sum(v[0] for v in vs) / len(vs); cy = sum(v[1] for v in vs) / len(vs); cz = sum(v[2] for v in vs) / len(vs)
    w = [M[i][0] * cx + M[i][1] * cy + M[i][2] * cz for i in range(3)]      # direction, translation left out
    return w


def check(a):
    m = mmd.MMD.load(a.mmd, a.type); e = mmd.exe(); nb, skel = e.bone_count[a.type], e.skeleton[a.type]
    idle, _, _ = animsheet.slot_frames(m, nb, 0)
    rid = retarget.world_rots(skel, idle[0])
    tid = {b: foot_dirs(m, nb, skel, idle[0], b) for b in a.feet}
    for s in a.slots:
        poses, _, _ = animsheet.slot_frames(m, nb, s)
        for b in a.feet:
            ang, toe = [], []
            for p in poses:
                ang.append(trace_angle(retarget.world_rots(skel, p)[b], rid[b]))
                d, d0 = foot_dirs(m, nb, skel, p, b), tid[b]
                if d and d0:
                    n = (math.hypot(*d) * math.hypot(*d0)) or 1
                    toe.append(math.degrees(math.acos(max(-1, min(1, sum(x * y for x, y in zip(d, d0)) / n)))))
            print(f'slot {s:#04x} foot {b}: orientation max {max(ang):5.1f}  mean {sum(ang)/len(ang):5.1f}  ticks>30: '
                  f'{sum(x > 30 for x in ang):2d}/{len(ang)}   toe vs idle max {max(toe or [0]):5.1f}')


UNROLL_TOL = 8                    # the tolerance a clip without its loops is encoded with (the importer used 8 to 14)
MAX_ERR = math.radians(4)        # the most a straight interpolation of the angles may stray from the intended orientation between two keys


def _interp_error(E, t, n):
    """The worst orientation error (radians) of the ticks t+1..t+n-1 when the angles go straight from E[t] to E[t+n]."""
    worst = 0.0
    for k in range(1, n):
        a = [E[t][i] + (E[t + n][i] - E[t][i]) * k / n for i in range(3)]
        R1, R2 = mmd.rot_matrix(*a), mmd.rot_matrix(*E[t + k])
        tr = sum(R1[i][j] * R2[i][j] for i in range(3) for j in range(3))
        worst = max(worst, math.acos(max(-1.0, min(1.0, (tr - 1) / 2))))
    return worst


def unshare(m, slots):
    """Give the slots their own copy of an animation they share with slots that are not in `slots`: the polish tools rewrite the
    bones of an animation in place, and a walk that shares its data with another clip would change that one too."""
    import copy
    slots = set(slots)
    t = m.anims.table
    for i in sorted({t[s] for s in slots if s < len(t) and t[s] is not None}):
        if any(x == i and s not in slots for s, x in enumerate(t)):
            m.anims.anims.append(copy.deepcopy(m.anims.anims[i]))
            j = len(m.anims.anims) - 1
            for s in slots:
                if s < len(t) and t[s] == i:
                    t[s] = j


def drop_looped(m, slots):
    """The slots whose animation has finite loops are left out of any rewrite: a loop runs the same keys several times, so the keys of a bone
    cannot be written as if each ran once (a limb kept turning like a wheel), and unrolling the loops would grow the clip several times over."""
    out = []
    for s_ in slots:
        i = m.anims.table[s_] if s_ < len(m.anims.table) else None
        if i is not None and any(x['op'] == 'loop_start' and (x.get('count', x.get('raw', 0) & 0xFF) != 0xFF) for x in m.anims.anims[i].instrs):
            continue
        out.append(s_)
    return out


def unroll_loops(m, slots):
    """An animation with finite loops (the encoder stores a movement that repeats as a loop) runs the same keys several times: rewriting the keys of
    a bone as if each ran once makes the bone keep adding its turn on every pass (a limb that goes round like a wheel). Such a clip is encoded
    again from its own ticks without loops before any bone is rewritten."""
    nb = mmd.exe().bone_count[m.type]
    done = set()
    for s_ in slots:
        i = m.anims.table[s_] if s_ < len(m.anims.table) else None
        if i is None or i in done:
            continue
        done.add(i)
        an = m.anims.anims[i]
        if not any(x['op'] == 'loop_start' and (x.get('count', x.get('raw', 0) & 0xFF) != 0xFF) for x in an.instrs):
            continue
        smp, lp, evs = animsheet.slot_frames(m, nb, s_)
        for q in smp:
            q[0][6:9] = [round(x) for x in q[0][6:9]]
        ev = [(k, kind, c) for k, kind, c in evs if kind in ('sound', 'tex')]
        m.anims.anims[i] = mmd.encode_anim(smp, nb, lp, ev, tol=UNROLL_TOL, repeats=False)


def rewrite_bone(an, nb, skel, slot, b, target, step=1):
    """Replaces the keys of bone b in clip `an` so that its world rotation in every tick is target(t, poses, world_rots)
    (a 3x3 matrix; poses = the tick's 9-value pose of every bone, world_rots = their world rotations). The clip is played
    first (the bones above b keep what they have), then b's start pose and its per-frame deltas are written."""
    p = mmd.AnimPlayer(an, nb, slot); poses = []
    while p.tick(stop_at_infinite_loop=True):
        poses.append([list(v) for v in p.pose])
    frames = p.frames[:len(poses)]
    par = skel[b][1]; prev = None; E = []
    for t, pose in enumerate(poses):
        wr = retarget.world_rots(skel, pose)
        loc = retarget.m3mul(m3t(wr[par]), target(t, pose, wr))
        eu = mmd.matrix_euler(loc, prev); prev = eu
        E.append([round(x) for x in eu])
    o = 3 if an.has_scale else 0                  # the clip's start pose: (scale,) rotation, translation
    an.pose[b - 1][o:o + 3] = E[0]
    for ins in an.instrs:
        if ins['op'] == 'key':
            ins['bones'] = [x for x in ins['bones'] if x['bone'] != b]
    first = {}
    for t, f in enumerate(frames):
        first.setdefault(f, t)
    nxt = [0]
    moving = {}
    have = {i['frame'] for i in an.instrs if i['op'] == 'key'}
    for f in sorted(first):                       # a frame the clip has no key for gets an empty one, in frame order
        if f in have:
            continue
        at = next((k for k, i in enumerate(an.instrs) if i['op'] in ('key', 'tex', 'sound', 'loop_end') and i['frame'] > f), None)
        if at is None:
            at = next((k for k, i in enumerate(an.instrs) if i['op'] in ('loop_end', 'end')), len(an.instrs))
        an.instrs.insert(at, dict(op='key', frame=f, bones=[]))
    for ins in an.instrs:
        if ins['op'] != 'key':
            continue
        t = first.get(ins['frame'])               # the sample produced by the tick that runs this key
        if t is None or t + 1 >= len(E):
            continue
        if t < nxt[0]:
            continue                               # keys are spaced by `step` at most, the engine fills the ticks in between
        n = min(step, len(E) - 1 - t)
        while n > 1 and _interp_error(E, t, n) > MAX_ERR:       # the angles are interpolated in a straight line: near a gimbal lock that
            n -= 1                                              # sweeps the limb round; a shorter span until the orientation stays right
        nxt[0] = t + n
        d = [E[t + n][k] - E[t][k] for k in range(3)]
        # a speed keeps running until the channel's next key: a channel that was moving and must now stand still gets an explicit zero
        vals = {ch: v for ch, v in zip(('rx', 'ry', 'rz'), d) if v or moving.get(ch)}
        for ch, v in zip(('rx', 'ry', 'rz'), d):
            moving[ch] = bool(v)
        if vals:
            ins['bones'].append(dict(bone=b, div=n, vals=vals))
            ins['bones'].sort(key=lambda x: x['bone'])


def rx(theta):
    c, s_ = math.cos(theta), math.sin(theta)
    return [[1, 0, 0], [0, c, -s_], [0, s_, c]]


def ry(theta):
    c, s_ = math.cos(theta), math.sin(theta)
    return [[c, 0, s_], [0, 1, 0], [-s_, 0, c]]


def rz(theta):
    c, s_ = math.cos(theta), math.sin(theta)
    return [[c, -s_, 0], [s_, c, 0], [0, 0, 1]]


def plant(a):
    m = mmd.MMD.load(a.mmd, a.type); e = mmd.exe(); nb, skel = e.bone_count[a.type], e.skeleton[a.type]
    ref = mmd.MMD.load(a.ref, a.type) if getattr(a, 'ref', None) else m     # the feet's orientation at rest: the model's own (before any change)
    idle, _, _ = animsheet.slot_frames(ref, nb, 0)
    rid = retarget.world_rots(skel, idle[0])
    lift = getattr(a, 'lift', 0.0)
    a.slots = drop_looped(m, a.slots)
    unshare(m, a.slots)
    done = set()
    for s in a.slots:
        i = m.anims.table[s] if s < len(m.anims.table) else None
        if i is None or i in done:
            continue
        done.add(i)
        for b in a.feet:
            if lift:
                ph = mmd.AnimPlayer(m.anims.anims[i], nb, s); pl = []
                while ph.tick(stop_at_infinite_loop=True):
                    pl.append([list(v) for v in ph.pose])
                ys = [retarget.world_pos(skel, q)[b][1] for q in pl]
                lo, hi = max(ys), min(ys)                       # y down: the lowest point of the foot is the largest y
                par = skel[b][1]

                def tgt(t, pose, wr, b=b, ys=ys, lo=lo, hi=hi, par=par):
                    k = min(t, len(ys) - 1)
                    air = max(0.0, min(1.0, (lo - ys[k]) / (0.4 * (lo - hi) or 1)))      # 0 on the ground, 1 well in the air
                    air = air * air * (3 - 2 * air)
                    R = retarget.m3mul(wr[par], m3t(rid[par]))                          # the shin's motion since rest
                    th = math.atan2(R[2][1], R[1][1])                                  # its pitch about the side axis
                    return retarget.m3mul(rx(lift * air * th), rid[b])
                rewrite_bone(m.anims.anims[i], nb, skel, s, b, tgt, getattr(a, 'step', 1))
            else:
                rewrite_bone(m.anims.anims[i], nb, skel, s, b, lambda t, pose, wr, b=b: rid[b], getattr(a, 'step', 1))
    data = m.build()
    assert mmd.MMD.parse(data, nb).build() == data
    open(a.out, 'wb').write(data)
    print(f'{a.out}: {len(data)} bytes')


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('check'); c.add_argument('mmd'); c.add_argument('type', type=lambda s: int(s, 0))
    p = sub.add_parser('plant'); p.add_argument('mmd'); p.add_argument('out'); p.add_argument('type', type=lambda s: int(s, 0))
    for x in (c, p):
        x.add_argument('--slots', type=lambda s: int(s, 0), nargs='*', default=[2, 3, 4])
        x.add_argument('--feet', type=int, nargs='*', default=[4, 7])
    p.add_argument('--step', type=int, default=1)
    p.add_argument('--lift', type=float, default=0.0, help='how much of the shin\'s pitch the foot follows while in the air (0 = always flat)')
    a = ap.parse_args()
    check(a) if a.cmd == 'check' else plant(a)


if __name__ == '__main__':
    main()
