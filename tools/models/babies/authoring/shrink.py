#!/usr/bin/env python3
"""shrink.py OUTDIR (build/babies-authoring): scale three finished babies down (size review 2026-11-03), in place, after their own scripts ran.

Every vertex is scaled about the ground point under the model in the rest pose (slot 0, tick 0): world = M_b v,
world' = P + s (world - P), v' = M_b^-1 world'. Animations and normals are untouched (uniform scale keeps directions).
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../../tools'))
import mmd  # noqa: E402

SCALES = {'Nyokimon': (1, 0.80), 'Nyaromon': (30, 0.85), 'Yokomon': (44, 0.88)}


def shrink(path, t, s):
    m = mmd.MMD.load(path, t)
    e = mmd.exe()
    frames, _ = mmd.simulate(m.anims.anims[m.anims.table[0]], e.bone_count[t])
    pose = frames[0]; pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
    mats = [np.array(M, float) for M in mmd.bone_matrices(m, pose)]
    objs = [(b, oi) for b, (oi, _) in enumerate(e.skeleton[t]) if oi >= 0]
    world = {oi: np.array([v[:3] for v in m.tmd.obj_verts(oi)], float) @ mats[b][:3, :3].T + mats[b][:3, 3]
             for b, oi in objs}
    allw = np.concatenate(list(world.values()))
    P = np.array([(allw[:, 0].min() + allw[:, 0].max()) / 2, allw[:, 1].max(), (allw[:, 2].min() + allw[:, 2].max()) / 2])
    done = set()
    for b, oi in objs:
        if oi in done: continue
        done.add(oi)
        ob = m.tmd.objects[oi]
        W = P + s * (world[oi] - P)
        L = (W - mats[b][:3, 3]) @ np.linalg.inv(mats[b][:3, :3]).T
        for k, i in enumerate(range(ob.vert_start, ob.vert_start + ob.nvert)):
            pad = m.tmd.verts[i][3]
            m.tmd.verts[i] = tuple(int(round(max(-32768, min(32767, c)))) for c in L[k]) + (pad,)
    open(path, 'wb').write(m.build())


if __name__ == '__main__':
    out = sys.argv[1]
    for name, (t, s) in SCALES.items():
        shrink(os.path.join(out, name + '.MMD'), t, s)
        print(name, s)
