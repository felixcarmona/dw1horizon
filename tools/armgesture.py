#!/usr/bin/env python3
"""Hands to the mouth: the eating clip of a body whose donor's arms stay still. Per tick the wrist goes from where it hangs to the mouth and
back (as often as the head bites: the peaks of the head's pitch), by a two-bone solve of shoulder and elbow like legik.py's legs.

  armgesture.py MODEL.MMD OUT.MMD TYPE --arms S,E,W ... --head BONE [--slots 8] [--step N]

S, E, W: the arm's shoulder, elbow and wrist bones (the last three bones of its chain); BONE: the head bone. The mouth is the head's
mesh centre, brought forward along the head's own direction.
"""
import argparse, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mmd, retarget, animsheet, footfix, legik


def run(a):
    m = mmd.MMD.load(a.mmd, a.type); e = mmd.exe(); nb, skel = e.bone_count[a.type], e.skeleton[a.type]
    idle, _, _ = animsheet.slot_frames(m, nb, 0)
    prest = retarget.world_pos(skel, idle[0]); rid = retarget.world_rots(skel, idle[0])
    hb = a.head
    # the mouth in the head's own frame: from its joint to the mesh centre of the head bone, brought forward (-z) and a little down
    vs = m.tmd.obj_verts(skel[hb][0]) if skel[hb][0] >= 0 else []
    cx = [sum(v[i] for v in vs) / len(vs) for i in range(3)] if vs else [0, 0, 0]
    zs = [v[2] for v in vs] or [0]
    local = [cx[0], cx[1] + 0.15 * (max(v[1] for v in vs) - min(v[1] for v in vs)) if vs else 0, min(zs) * 0.85]
    arms = []
    for sp in a.arms:
        s, el, w = (int(x) for x in sp.split(','))
        arms.append(dict(s=s, e=el, w=w, L1=legik.norm(legik.sub(prest[el], prest[s])), L2=legik.norm(legik.sub(prest[w], prest[el])),
                         d2=legik.sub(prest[el], prest[s]), d3=legik.sub(prest[w], prest[el]), A0=prest[w], side=1 if prest[w][0] > 0 else -1))
        v = legik.sub(prest[w], prest[s]); k = legik.sub(prest[el], prest[s])
        arms[-1]['axis0'] = v
        arms[-1]['pole0'] = legik.sub(k, legik.mul(legik.unit(v), legik.dot(k, legik.unit(v))))
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
        n = len(poses)
        # how many bites: the peaks of the head's pitch (about the side axis), at least one
        pitch = []
        for q in poses:
            R = retarget.m3mul(retarget.world_rots(skel, q)[hb], footfix.m3t(rid[hb]))
            pitch.append(math.atan2(R[2][1], R[1][1]))
        mean = sum(pitch) / n
        peaks = sum(1 for k in range(n) if pitch[k] > mean + 0.05 and pitch[k] >= pitch[k - 1] and pitch[k] > pitch[(k + 1) % n])
        bites = max(1, min(4, peaks))
        for ar in arms:
            T2, T3 = [], []
            for t, pose in enumerate(poses):
                pos = retarget.world_pos(skel, pose); wr = retarget.world_rots(skel, pose)
                mouth = legik.add(pos[hb], [sum(wr[hb][r][c] * local[c] for c in range(3)) for r in range(3)])
                mouth = legik.add(mouth, [0.35 * ar['side'] * abs(ar['A0'][0]), 0, 0])
                w = 0.5 * (1 - math.cos(2 * math.pi * bites * t / n))
                w = w * w * (3 - 2 * w)
                hip = pos[ar['s']]
                tgt = legik.add(legik.mul(ar['A0'], 1 - w), legik.mul(mouth, w))
                tgt = legik.add(legik.sub(tgt, ar['A0']), legik.add(hip, legik.sub(ar['A0'], prest[ar['s']])))   # the body moves: the hanging spot goes with the shoulder
                tgt = legik.add(legik.mul(tgt, 1 - w), legik.mul(mouth, w))
                pole = [sum(r[j] * ar['pole0'][j] for j in range(3)) for r in retarget.swing(ar['axis0'], legik.sub(tgt, hip))]
                knee, wrist = legik.solve(hip, tgt, ar['L1'], ar['L2'], pole)
                T2.append(retarget.m3mul(retarget.swing(ar['d2'], legik.sub(knee, hip)), rid[ar['s']]))
                T3.append(retarget.m3mul(retarget.swing(ar['d3'], legik.sub(wrist, knee)), rid[ar['e']]))
            footfix.rewrite_bone(an, nb, skel, slot, ar['s'], lambda t, pose, wr, T=T2: T[min(t, len(T) - 1)], a.step)
            footfix.rewrite_bone(an, nb, skel, slot, ar['e'], lambda t, pose, wr, T=T3: T[min(t, len(T) - 1)], a.step)
    data = m.build()
    assert mmd.MMD.parse(data, nb).build() == data
    open(a.out, 'wb').write(data)
    print(f'{a.out}: {len(data)} bytes')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('mmd'); ap.add_argument('out'); ap.add_argument('type', type=lambda s: int(s, 0))
    ap.add_argument('--arms', nargs='+', required=True); ap.add_argument('--head', type=int, required=True)
    ap.add_argument('--slots', type=lambda s: int(s, 0), nargs='*', default=[8]); ap.add_argument('--step', type=int, default=1)
    run(ap.parse_args())


if __name__ == '__main__':
    main()
