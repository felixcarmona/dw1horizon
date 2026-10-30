#!/usr/bin/env python3
"""Follow-through: limbs and tails that are rigid with their parent (the donor's arms do not move, an unmapped tail) trail behind it.

  followthrough.py MODEL.MMD OUT.MMD TYPE --chains [tail=|armR=|armL=]B1,B2,B3[:a1,a2,a3] ... [--slots 0 1 2 ...] [--step N] [--sway 0 1]

A chain is the bones of a limb or tail from the root down. Each bone is taken to its rigid pose under its (already trailing) parent and
filtered in time: W(t) = slerp(W(t-1), rigid(t), alpha), run over the clip twice so that a looping clip comes back to where it
started. The deeper bones trail more (default alphas 0.55, 0.40, 0.30...). Bones the clip already moves on their own are left alone
(see `stiff`).
"""
import argparse, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mmd, retarget, animsheet, footfix

ALPHAS = (0.55, 0.40, 0.30, 0.25, 0.2)


def lag(T, alpha):
    """First-order lag of a cyclic series of rotation matrices (two passes: the second is the steady state)."""
    n = len(T)
    W = T[0]; out = [None] * n
    for k in range(2 * n):
        i = k % n
        D = retarget.m3mul(footfix.m3t(W), T[i])
        ax, ang = retarget.axis_angle(D)
        W = retarget.m3mul(W, retarget.from_axis_angle(ax, ang * alpha)) if ang > 1e-9 else W
        if k >= n:
            out[i] = W
    return out


def stiff(an, nb, skel, slot, b, limit=0.12):
    """True when the bone's own rotation against its parent hardly changes in the clip (radians)."""
    p = mmd.AnimPlayer(an, nb, slot); poses = []
    while p.tick(stop_at_infinite_loop=True):
        poses.append([list(v) for v in p.pose])
    R0 = retarget.rot_of(poses[0][b])
    return max(math.acos(max(-1.0, min(1.0, (sum(retarget.m3mul(footfix.m3t(R0), retarget.rot_of(q[b]))[i][i] for i in range(3)) - 1) / 2)))
               for q in poses) < limit


def run(a):
    m = mmd.MMD.load(a.mmd, a.type); e = mmd.exe(); nb, skel = e.bone_count[a.type], e.skeleton[a.type]
    idle, _, _ = animsheet.slot_frames(m, nb, 0)
    rid = retarget.world_rots(skel, idle[0])
    chains = []
    for c in a.chains:
        role = ''
        if c[:1].isalpha():                      # 'tail=11,12,13', 'armR=5,6,7', 'armL=8,9,10': the role decides how an idle sways
            role, _, c = c.partition('=')
        bones, _, al = c.partition(':')
        bones = [int(x) for x in bones.split(',')]
        alphas = [float(x) for x in al.split(',')] if al else [ALPHAS[min(i, len(ALPHAS) - 1)] for i in range(len(bones))]
        chains.append((bones, alphas, role))
    a.slots = footfix.drop_looped(m, a.slots)
    footfix.unshare(m, a.slots)
    done = set()
    for s in a.slots:
        i = m.anims.table[s] if s < len(m.anims.table) else None
        if i is None or i in done:
            continue
        done.add(i); an = m.anims.anims[i]
        for bones, alphas, role in chains:
            for k, (b, al) in enumerate(zip(bones, alphas)):
                if b not in getattr(a, 'force', ()) and (getattr(a, 'rigid', False) or not stiff(an, nb, skel, s, b)):   # a bone the clip already moves is left alone (the ones below it still trail); rigid: only the forced (unmapped) bones, never a mapped one whose idle motion is small
                    continue
                par = skel[b][1]; Lrest = retarget.m3mul(footfix.m3t(rid[par]), rid[b])
                p = mmd.AnimPlayer(an, nb, s); T = []
                while p.tick(stop_at_infinite_loop=True):
                    wr = retarget.world_rots(skel, [list(v) for v in p.pose])
                    T.append(retarget.m3mul(wr[par], Lrest))
                F = lag(T, al)
                if s in getattr(a, 'sway', [0, 1]) and role:                # an idle that hardly moves: a slow sway, one period per loop
                    n = len(F)
                    for i_ in range(n):
                        ph = 2 * math.pi * i_ / n
                        if role == 'tail':
                            ang = (0.16 / len(bones) ** 0.5) * math.sin(ph - 0.7 * k)
                            F[i_] = retarget.m3mul(footfix.ry(ang), F[i_])
                        else:
                            sgn = 1 if role == 'armR' else -1
                            F[i_] = retarget.m3mul(footfix.rx(0.07 * sgn * math.sin(ph - 0.5 * k)), retarget.m3mul(footfix.rz(0.05 * -sgn * math.sin(ph + 1.0 - 0.4 * k)), F[i_]))
                footfix.rewrite_bone(an, nb, skel, s, b, lambda t, pose, wr, F=F: F[min(t, len(F) - 1)], a.step)
    data = m.build()
    assert mmd.MMD.parse(data, nb).build() == data
    open(a.out, 'wb').write(data)
    print(f'{a.out}: {len(data)} bytes')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('mmd'); ap.add_argument('out'); ap.add_argument('type', type=lambda s: int(s, 0))
    ap.add_argument('--chains', nargs='+', required=True)
    ap.add_argument('--slots', type=lambda s: int(s, 0), nargs='*', default=list(range(0, 0x2e)))
    ap.add_argument('--step', type=int, default=1)
    ap.add_argument('--force', type=int, nargs='*', default=[], help='bones whose own motion is replaced (the donor map leaves them out: their motion is a layered idle)')
    ap.add_argument('--sway', type=lambda s: int(s, 0), nargs='*', default=[0, 1], help='the idle slots that get a slow sway on the chains with a role')
    run(ap.parse_args())


if __name__ == '__main__':
    main()
