#!/usr/bin/env python3
"""An arm the donor cannot move copies the other arm, mirrored: per tick its segments point where the partner's do, with x negated.

  armmirror.py MODEL.MMD OUT.MMD TYPE --pairs S,E,W:S2,E2,W2 ... [--slots ...] [--step N] [--flat F]

S,E,W is the arm that is copied (its shoulder, elbow, wrist bones), after the colon the arm that is left unchanged and serves as
the model. Needed when the model's own rest or idle pose holds one arm out (Stingmon's left arm back and up) and the donor has
no arm to drive it: that arm would stay in that pose in every clip. Directions are taken joint to joint as armmatch.py does; the
hand stays under the forearm. A pair whose two arms are the same is not mirrored. --flat F scales the forward
component of the first segment (the shoulder piece) by F (1 = as is).
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mmd, retarget, animsheet, footfix, legik


def run(a):
    m = mmd.MMD.load(a.mmd, a.type); e = mmd.exe(); nb, skel = e.bone_count[a.type], e.skeleton[a.type]
    idle, _, _ = animsheet.slot_frames(m, nb, 0)
    prest = retarget.world_pos(skel, idle[0]); rid = retarget.world_rots(skel, idle[0])
    pairs = []
    for sp in a.pairs:
        l, r = sp.split(':')
        s, el, w = (int(x) for x in l.split(',')); src = [int(x) for x in r.split(',')]
        pairs.append(dict(s=s, e=el, w=w, src=src, d2=legik.sub(prest[el], prest[s]), d3=legik.sub(prest[w], prest[el])))
    a.slots = footfix.drop_looped(m, a.slots)
    footfix.unshare(m, a.slots)
    done = set()
    for slot in a.slots:
        i = m.anims.table[slot] if slot < len(m.anims.table) else None
        if i is None or i in done:
            continue
        done.add(i); an = m.anims.anims[i]
        p = mmd.AnimPlayer(an, nb, slot); poses = []
        while p.tick(stop_at_infinite_loop=True):
            poses.append([list(v) for v in p.pose])
        worlds = [retarget.world_pos(skel, pose) for pose in poses]
        for pr in pairs:
            T2, T3 = [], []
            for pos in worlds:
                a0, a1, a2 = (pos[b] for b in pr['src'])
                flip = pr['src'] != [pr['s'], pr['e'], pr['w']]          # the same arm as itself: not mirrored
                mir = lambda v: [-v[0] if flip else v[0], v[1], v[2]]
                u2 = mir(legik.sub(a1, a0)); u3 = mir(legik.sub(a2, a1))
                u2[2] *= a.flat                                          # the shoulder piece pointing forward: held back
                T2.append(retarget.m3mul(retarget.swing(pr['d2'], u2), rid[pr['s']]))
                T3.append(retarget.m3mul(retarget.swing(pr['d3'], u3), rid[pr['e']]))
            footfix.rewrite_bone(an, nb, skel, slot, pr['s'], lambda t, pose, wr, T=T2: T[min(t, len(T) - 1)], a.step)
            footfix.rewrite_bone(an, nb, skel, slot, pr['e'], lambda t, pose, wr, T=T3: T[min(t, len(T) - 1)], a.step)
    data = m.build()
    assert mmd.MMD.parse(data, nb).build() == data
    open(a.out, 'wb').write(data)
    print(f'{a.out}: {len(data)} bytes')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('mmd'); ap.add_argument('out'); ap.add_argument('type', type=lambda s: int(s, 0))
    ap.add_argument('--pairs', nargs='+', required=True)
    ap.add_argument('--slots', type=lambda s: int(s, 0), nargs='*', default=list(range(0, 0x2e)))
    ap.add_argument('--step', type=int, default=1)
    ap.add_argument('--flat', type=float, default=1.0)
    run(ap.parse_args())


if __name__ == '__main__':
    main()
