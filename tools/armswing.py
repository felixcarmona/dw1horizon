#!/usr/bin/env python3
"""Arms that swing when the donor's do not: each arm follows the opposite leg, forward when that foot is forward.

  armswing.py MODEL.MMD OUT.MMD TYPE --arms S,E:H,A ... [--slots 2 3 4 0x1b 0x22 0x23 0x24] [--amp 0.45] [--step 1]

S = the arm's first bone (shoulder), E = the bone below it (elbow); H,A = hip and foot bone of the opposite leg. Per tick the
swing angle is amp (radians, about the world side axis x) times how far that foot is from its mean fore-aft position over the
clip (-1..1); the elbow adds a flex (half the forward swing) so the forearm comes up when the arm goes forward. The body's own
motion above the shoulder is kept. Run after legik/footfix (it reads the legs as they are then).
"""
import argparse, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mmd, retarget, animsheet, footfix


def run(a):
    m = mmd.MMD.load(a.mmd, a.type); e = mmd.exe(); nb, skel = e.bone_count[a.type], e.skeleton[a.type]
    idle, _, _ = animsheet.slot_frames(m, nb, 0)
    rid = retarget.world_rots(skel, idle[0])
    arms = []
    for spec in a.arms:
        l, r = spec.split(':'); s, el = (int(x) for x in l.split(',')); h, ft = (int(x) for x in r.split(','))
        arms.append((s, el, h, ft))
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
        for s, el, h, ft in arms:
            zs = []
            for pose in poses:
                pos = retarget.world_pos(skel, pose)
                zs.append(pos[ft][2] - pos[h][2])
            mean = sum(zs) / len(zs); amp = max(abs(z - mean) for z in zs) or 1.0
            th = [a.amp * (z - mean) / amp for z in zs]            # + = towards the back (+z)
            def target(bone, extra):
                def f(t, pose, wr):
                    par = skel[bone][1]
                    D = retarget.m3mul(wr[par], retarget.m3t(rid[par]))       # the parent's own motion since rest
                    ang = th[min(t, len(th) - 1)]
                    ang += extra(ang)
                    return retarget.m3mul(D, retarget.m3mul(retarget.from_axis_angle([1, 0, 0], ang), rid[bone]))
                return f
            footfix.rewrite_bone(an, nb, skel, slot, s, target(s, lambda g: 0.0), a.step)
            footfix.rewrite_bone(an, nb, skel, slot, el, target(el, lambda g: 0.5 * min(0.0, g)), a.step)
    data = m.build()
    assert mmd.MMD.parse(data, nb).build() == data
    open(a.out, 'wb').write(data)
    print(f'{a.out}: {len(data)} bytes')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('mmd'); ap.add_argument('out'); ap.add_argument('type', type=lambda s: int(s, 0))
    ap.add_argument('--arms', nargs='+', required=True)
    ap.add_argument('--slots', type=lambda s: int(s, 0), nargs='*', default=[2, 3, 4, 0x1b, 0x22, 0x23, 0x24])
    ap.add_argument('--amp', type=float, default=0.45)
    ap.add_argument('--step', type=int, default=1)
    run(ap.parse_args())


if __name__ == '__main__':
    main()
