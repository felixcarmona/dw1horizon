#!/usr/bin/env python3
"""Arms that take the donor's arm posture: per tick the upper arm and the forearm point where the donor's do (world directions, no twist).

  armmatch.py MODEL.MMD OUT.MMD TYPE DONOR.MMD DONORTYPE --arms S,E,W:D1[,D2[,D3]] ... [--slots ...] [--step N]

S,E,W: the model's shoulder (the bone that turns the upper arm), elbow and wrist bones; after the colon, the donor's arm chain (one, two or three
bones: a short chain ends at its last bone's mesh centre). Copying the rotation each donor bone
makes since its rest pose (what retarget.transfer does) twists the hands and keeps the model's rest posture (arms straight down) whatever
the donor does; here the direction of each segment (joint to joint) is taken, as legik.py takes the ankle: the donor's arms held forward
are held forward, and the hand stays as it is under the forearm.
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mmd, retarget, animsheet, footfix, legik


def run(a):
    m = mmd.MMD.load(a.mmd, a.type); e = mmd.exe(); nb, skel = e.bone_count[a.type], e.skeleton[a.type]
    dm = mmd.MMD.load(a.donor, a.dtype); dnb, dskel = e.bone_count[a.dtype], e.skeleton[a.dtype]
    idle, _, _ = animsheet.slot_frames(m, nb, 0)
    prest = retarget.world_pos(skel, idle[0]); rid = retarget.world_rots(skel, idle[0])
    arms = []
    for sp in a.arms:
        l, r = sp.split(':'); s, el, w = (int(x) for x in l.split(',')); chain = [int(x) for x in r.split(',')]
        arms.append(dict(s=s, e=el, d2=legik.sub(prest[el], prest[s]), d3=legik.sub(prest[w], prest[el]), chain=chain))
    a.slots = footfix.drop_looped(m, a.slots)
    footfix.unshare(m, a.slots)
    tips = {}                                                    # a donor bone's mesh centre in its own space: where its limb ends
    for ar in arms:
        for b in ar['chain']:
            vs = dm.tmd.obj_verts(dskel[b][0]) if dskel[b][0] >= 0 else []
            tips[b] = [sum(v[i] for v in vs) / len(vs) for i in range(3)] if vs else [0, 0, 0]

    def points(dp, chain):
        """Shoulder, elbow, wrist of the donor's arm at one tick: the last three joints; a shorter chain ends at its bone's mesh centre."""
        M = mmd.bone_matrices(dm, dp)
        joint = lambda b: [M[b][i][3] for i in range(3)]
        tip = lambda b: [sum(M[b][i][j] * tips[b][j] for j in range(3)) + M[b][i][3] for i in range(3)]
        if len(chain) >= 3:
            return joint(chain[-3]), joint(chain[-2]), joint(chain[-1])
        if len(chain) == 2:
            return joint(chain[0]), joint(chain[1]), tip(chain[1])
        return joint(chain[0]), tip(chain[0]), tip(chain[0])         # one bone: a straight arm
    done = set()
    for slot in a.slots:
        i = m.anims.table[slot] if slot < len(m.anims.table) else None
        if i is None or i in done or slot >= len(dm.anims.table) or dm.anims.table[slot] is None:
            continue
        done.add(i); an = m.anims.anims[i]
        dsm, _, _ = animsheet.slot_frames(dm, dnb, slot)
        n = len(retarget.play(an, nb, slot)[0])
        for ar in arms:
            T2, T3 = [], []
            for t in range(n):
                dp = [list(v) for v in dsm[min(t, len(dsm) - 1)]]; dp[0] = [4096, 4096, 4096] + dp[0][3:6] + [0, 0, 0]
                p0, p1, p2 = points(dp, ar['chain'])
                u2 = legik.sub(p1, p0)
                u3 = legik.sub(p2, p1) if len(ar['chain']) > 1 else u2
                T2.append(retarget.m3mul(retarget.swing(ar['d2'], u2), rid[ar['s']]))
                T3.append(retarget.m3mul(retarget.swing(ar['d3'], u3), rid[ar['e']]))
            footfix.rewrite_bone(an, nb, skel, slot, ar['s'], lambda t, pose, wr, T=T2: T[min(t, len(T) - 1)], a.step)
            footfix.rewrite_bone(an, nb, skel, slot, ar['e'], lambda t, pose, wr, T=T3: T[min(t, len(T) - 1)], a.step)
    data = m.build()
    assert mmd.MMD.parse(data, nb).build() == data
    open(a.out, 'wb').write(data)
    print(f'{a.out}: {len(data)} bytes')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('mmd'); ap.add_argument('out'); ap.add_argument('type', type=lambda s: int(s, 0))
    ap.add_argument('donor'); ap.add_argument('dtype', type=lambda s: int(s, 0))
    ap.add_argument('--arms', nargs='+', required=True)
    ap.add_argument('--slots', type=lambda s: int(s, 0), nargs='*', default=list(range(0, 0x2e)))
    ap.add_argument('--step', type=int, default=1)
    run(ap.parse_args())


if __name__ == '__main__':
    main()
