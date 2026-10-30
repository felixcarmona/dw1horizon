#!/usr/bin/env python3
"""Legs of a retargeted walk by feet, not by joint angles: a two-bone leg solved so that each ankle follows the donor's ankle.

  legik.py MODEL.MMD OUT.MMD TYPE DONOR.MMD DONORTYPE --legs HIP,KNEE,ANKLE:DHIP,DANKLE[,1] ... [--slots 2 3 4 0x23 0x24] [--k 1.205] [--neutral] [--stance]

Joint angles do not transfer between legs of different proportions (a Tyrannomon whose knee bends 70 degrees lifts a rigid
two-piece leg 90 degrees, and the foot skates). Here, per tick, the ankle's target is the model's own rest ankle plus
k times how far the donor's ankle moved from its rest position relative to the donor's hip; the hip (the bone the leg
hangs from) is where the model's own animation put it. The two bones are turned (shortest rotation from their rest
directions) to reach the target, the knee on the side it has at rest. The feet's own orientation is footfix.py's job.
"""
import argparse, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mmd, animsheet, retarget, footfix


def sub(a, b): return [x - y for x, y in zip(a, b)]
def add(a, b): return [x + y for x, y in zip(a, b)]
def mul(a, k): return [x * k for x in a]
def dot(a, b): return sum(x * y for x, y in zip(a, b))
def norm(a): return math.sqrt(dot(a, a)) or 1e-9
def unit(a): n = norm(a); return [x / n for x in a]


def solve(hip, target, L1, L2, pole):
    """Knee and ankle positions of a two-bone leg from hip reaching `target`, the knee towards `pole` (a direction)."""
    v = sub(target, hip); d = norm(v)
    d = max(abs(L1 - L2) + 1e-3, min(L1 + L2 - 1e-3, d))
    u = unit(v)
    pp = sub(pole, mul(u, dot(pole, u)))
    pp = unit(pp) if norm(pp) > 1e-6 else [0, 0, -1]
    a = (L1 * L1 - L2 * L2 + d * d) / (2 * d)
    h = math.sqrt(max(0.0, L1 * L1 - a * a))
    knee = add(hip, add(mul(u, a), mul(pp, h)))
    return knee, add(hip, mul(u, d))


def _ankle(dm, dskel, dp, dpos, da, tip, tl):
    """The donor's ankle: the joint of its foot bone, or for a one-bone leg the low end of that bone's mesh."""
    if not tip:
        return dpos[da]
    M = mmd.bone_matrices(dm, dp)[da]
    return [sum(M[i][j] * tl[j] for j in range(3)) + M[i][3] for i in range(3)]


def _halfwidth(m, skel, b):
    """Half the sideways size of a bone's own mesh (a foot's width)."""
    oi = skel[b][0]
    xs = [v[0] for v in m.tmd.obj_verts(oi)] if oi >= 0 else []
    return (max(xs) - min(xs)) / 2 if xs else 0.0


def run(a):
    m = mmd.MMD.load(a.mmd, a.type); e = mmd.exe()
    nb, skel = e.bone_count[a.type], e.skeleton[a.type]
    dm = mmd.MMD.load(a.donor, a.dtype); dnb, dskel = e.bone_count[a.dtype], e.skeleton[a.dtype]
    # the rest pose is the model's own idle; when the input is a donor-retargeted copy (a.rest = the native model), its idle has the donor's stance
    idle, _, _ = animsheet.slot_frames(mmd.MMD.load(a.rest, a.type) if getattr(a, 'rest', None) else m, nb, 0)
    prest = retarget.world_pos(skel, idle[0]); rid = retarget.world_rots(skel, idle[0])
    didle, _, _ = animsheet.slot_frames(dm, dnb, 0)
    dprest = retarget.world_pos(dskel, didle[0])
    span = lambda P: (max(p[1] for p in P[1:]) - min(p[1] for p in P[1:])) or 1
    hr = span(prest) / span(dprest)
    legs = []
    for spec in a.legs:
        left, right = spec.split(':'); h, k, an_ = (int(x) for x in left.split(',')); rr = [int(x) for x in right.split(',')]; dh, da = rr[0], rr[1]
        tip = bool(rr[2]) if len(rr) > 2 else False
        L1, L2 = norm(sub(prest[k], prest[h])), norm(sub(prest[an_], prest[k]))
        axis0 = sub(prest[an_], prest[h]); kv = sub(prest[k], prest[h])
        pole0 = sub(kv, mul(unit(axis0), dot(kv, unit(axis0))))
        tl = [0, 0, 0]
        if tip:                                   # a one-bone donor leg: the foot is the low end of the bone's mesh, not its joint
            vs = sorted(dm.tmd.obj_verts(dskel[da][0]), key=lambda v: -v[1])
            low = vs[:max(1, len(vs) // 4)]
            tl = [sum(v[i] for v in low) / len(low) for i in range(3)]
        dp0 = [list(v) for v in didle[0]]; dp0[0] = [4096, 4096, 4096] + dp0[0][3:6] + [0, 0, 0]
        legs.append(dict(h=h, k=k, a=an_, dh=dh, da=da, tip=tip, tl=tl, hr=hr, fw=_halfwidth(m, skel, an_), dfw=_halfwidth(dm, dskel, da), hx=prest[h][0] - prest[1][0], dhx=dprest[dh][0] - dprest[1][0], ratio=(L1 + L2) / (norm(sub(_ankle(dm, dskel, dp0, dprest, da, tip, tl), dprest[dh])) or 1), L1=L1, L2=L2, axis0=axis0, pole0=pole0,
                         A0=sub(prest[an_], prest[h]), D0=sub(_ankle(dm, dskel, dp0, dprest, da, tip, tl), dprest[dh]),
                         d2=sub(prest[k], prest[h]), d3=sub(prest[an_], prest[k])))
    own_half = sum(abs(lg['hx'] + lg['A0'][0]) for lg in legs) / (len(legs) or 1)       # the model's own stance: half the gap between its feet
    a.slots = footfix.drop_looped(m, a.slots)
    footfix.unshare(m, a.slots)
    done = set()
    for s in a.slots:
        i = m.anims.table[s] if s < len(m.anims.table) else None
        if i is None or i in done:
            continue
        done.add(i); an = m.anims.anims[i]
        dsm, _, _ = animsheet.slot_frames(dm, dnb, s)
        p = mmd.AnimPlayer(an, nb, s); poses = []
        while p.tick(stop_at_infinite_loop=True):
            poses.append([list(v) for v in p.pose])
        for lg in legs:
            T2, T3 = [], []
            for t, pose in enumerate(poses):
                dp = [list(v) for v in dsm[min(t, len(dsm) - 1)]]; dp[0] = [4096, 4096, 4096] + dp[0][3:6] + [0, 0, 0]
                dpos = retarget.world_pos(dskel, dp)
                pos = retarget.world_pos(skel, pose)
                hip = pos[lg['h']]
                A0 = list(lg['A0'])
                if getattr(a, 'stance', False):          # a narrow body on a donor that stands with its legs apart: the stance of the donor, in the model's proportions
                    # measured from the body's centre line, not from the hip (a donor's hips may sit on the centre, the model's apart)
                    # the donor's stance in the model's body size (its height), and its gap between the feet in widths of the model's foot
                    # (thick feet close together read as glued even when the joints are as far apart as the donor's)
                    dcx = abs(lg['dhx'] + lg['D0'][0])
                    cx = lg['hx'] + A0[0]
                    # the donor's width never makes the stance wider than the model's own (mean of its two feet; a narrow body on a wide donor
                    # read as legs too far apart), and only in the walk and the run:
                    # standing clips keep the model's own feet
                    wide = max(dcx * lg['hr'], lg['fw'] * (1 + max(0.0, dcx - lg['dfw']) / (lg['dfw'] or 1)))
                    wide = min(wide, max(own_half, abs(cx)))
                    if abs(cx) < wide and s in getattr(a, 'walk_slots', [s]):
                        A0[0] = math.copysign(wide, cx or lg['D0'][0]) - lg['hx']
                if a.neutral and s in getattr(a, 'walk_slots', [s]):   # (only in the walk and the run: standing clips keep the model's own feet)
                    # the rest pose may stand staggered: walk from the donor's own stance (foot a little ahead of the hip)
                    A0[2] = lg['D0'][2] * a.k
                dl = sub(sub(_ankle(dm, dskel, dp, dpos, lg['da'], lg['tip'], lg['tl']), dpos[lg['dh']]), lg['D0'])
                if getattr(a, 'stance', False):
                    dl = [dl[0] * 0.15, dl[1], dl[2]]
                    if s not in getattr(a, 'walk_slots', [s]):
                        dl = [0.0, dl[1] * 0.2, dl[2] * 0.2]      # standing clips: the legs stay put under the body (the donor's weight shifting reads as swaying)      # the donor's sideways swing of the foot is damped: feet crossing back and forth read as swaying
                tgt = add(hip, add(A0, mul(dl, a.k)))
                ax = sub(tgt, hip)
                pole = [sum(r[j] * lg['pole0'][j] for j in range(3)) for r in retarget.swing(lg['axis0'], ax)]
                knee, ank = solve(hip, tgt, lg['L1'], lg['L2'], pole)
                T2.append(retarget.m3mul(retarget.swing(lg['d2'], sub(knee, hip)), rid[lg['h']]))
                T3.append(retarget.m3mul(retarget.swing(lg['d3'], sub(ank, knee)), rid[lg['k']]))
            footfix.rewrite_bone(an, nb, skel, s, lg['h'], lambda t, pose, wr, T=T2: T[min(t, len(T) - 1)], getattr(a, 'step', 1))
            footfix.rewrite_bone(an, nb, skel, s, lg['k'], lambda t, pose, wr, T=T3: T[min(t, len(T) - 1)], getattr(a, 'step', 1))
    data = m.build()
    assert mmd.MMD.parse(data, nb).build() == data
    open(a.out, 'wb').write(data)
    print(f'{a.out}: {len(data)} bytes')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('mmd'); ap.add_argument('out'); ap.add_argument('type', type=lambda s: int(s, 0))
    ap.add_argument('donor'); ap.add_argument('dtype', type=lambda s: int(s, 0))
    ap.add_argument('--rest', default=None, help='the model whose idle gives the rest pose (default: MODEL.MMD itself)')
    ap.add_argument('--legs', nargs='+', required=True)
    ap.add_argument('--slots', type=lambda s: int(s, 0), nargs='*', default=[2, 3, 4, 0x23, 0x24])
    ap.add_argument('--k', type=float, default=1.0)
    ap.add_argument('--step', type=int, default=1, help='a key every N ticks (smaller files, coarser motion)')
    ap.add_argument('--stance', action='store_true', help='at least the donor\'s stance width, in the model\'s proportions')
    ap.add_argument('--neutral', action='store_true', help='stance front-to-back like the donor, not the rest pose')
    run(ap.parse_args())


if __name__ == '__main__':
    main()
