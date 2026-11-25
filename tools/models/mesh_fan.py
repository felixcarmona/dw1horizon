"""Join the nine reviewed tail shells to their fan, preserving every packet.

The imported seven end shells were placed on two serial donor tail joints while
all nine proximal shells stayed on the first joint. They are separate tails,
not successive sections of one tail. Fit each end onto its matching proximal
ray and bind the complete fan to its existing swaying joint. The returned
primitive groups permit a cross-tail audit even though they share a bone.
"""
import math
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mmd

# (proximal packets in object 9, end object, contiguous source tail number).
JOINS = (
    ((16, 17, 44, 45, 46, 67), 10, 1),
    ((18, 19, 42, 47, 48, 68), 10, 0),
    ((20, 21, 41, 49, 50, 69), 11, 2),
    ((22, 23, 43, 51, 52, 70), 10, 2),
    ((24, 25, 38, 53, 54, 71), 11, 0),
    ((28, 29, 40, 57, 58, 73), 11, 3),
    ((32, 33, 39, 61, 62, 75), 11, 1),
)
WHOLE = (
    (0, 1, 2, 3, 8, 9, 10, 11, 26, 27, 34, 35, 55, 56, 63, 65, 72, 76, 77, 80, 82),
    (4, 5, 6, 7, 12, 13, 14, 15, 30, 31, 36, 37, 59, 60, 64, 66, 74, 78, 79, 81, 83),
)
# Each tail keeps the source's full width (an earlier fit thinned every tail to
# 45 %, which read as separate spikes); the fan opens a little wider instead.
SPREAD = 1.2


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def sub(a, b):
    return [a[i]-b[i] for i in range(3)]


def add(a, b):
    return [a[i]+b[i] for i in range(3)]


def mul(a, s):
    return [x*s for x in a]


def unit(a):
    length = math.sqrt(dot(a, a))
    if length < 1e-9:
        raise ValueError('tail fit requires a nonzero ray')
    return mul(a, 1/length)


def mean(points):
    return [sum(p[i] for p in points)/len(points) for i in range(3)]


def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def align(a, b, value):
    """Shortest rotation between two unit rays (Rodrigues)."""
    k = cross(a, b)
    c = dot(a, b)
    if c < -.999999:
        raise ValueError('tail fit requires compatible source rays')
    return add(add(value, cross(k, value)), mul(cross(k, cross(k, value)), 1/(1+c)))


def packed(v):
    return tuple(round(x) for x in v)+(0,)


def apply(model):
    obj = model.tmd.objects[9]
    if [len(model.tmd.objects[i].prims) for i in (9, 10, 11)] != [84, 60, 80]:
        raise ValueError('tail fan requires the reviewed packet groups')
    original = [v[:3] for v in model.tmd.obj_verts(9)]
    verts = list(model.tmd.obj_verts(9))
    norms = list(model.tmd.obj_norms(9))[:obj.nnorm]
    prims = list(obj.prims)
    groups, rays = [], []
    for proximal, oi, component in JOINS:
        ids = sorted({v for pi in proximal for v in prims[pi].decode()['verts']})
        points = [original[i] for i in ids]
        root = mean([v for v in points if v[0] < 5])
        axis = unit(sub(mean([v for v in points if v[0] > 50]), root))
        length = max(dot(sub(v, root), axis) for v in points)
        for vi in ids:
            v = original[vi]
            if v[0] > 50:
                verts[vi] = packed(add(v, mul(axis, length-dot(sub(v, root), axis))))
        source = [v[:3] for v in model.tmd.obj_verts(oi)[component*17:(component+1)*17]]
        start = mean(source[8:16])
        direction = unit(sub(mean(source[:8]), start))
        shift = len(verts)-component*17
        for k, v in enumerate(source):
            q = align(direction, axis, sub(v, start))
            verts.append(packed(add(q, add(root, mul(axis, length)))))
        nmap = {}
        source_norms = model.tmd.obj_norms(oi)
        first = len(prims)
        for p in model.tmd.objects[oi].prims[component*20:(component+1)*20]:
            d = p.decode()
            d['verts'] = [v+shift for v in d['verts']]
            for k, ni in enumerate(d['norms']):
                if ni not in nmap:
                    nmap[ni] = len(norms)
                    norms.append(packed(align(direction, axis, source_norms[ni][:3])))
                d['norms'][k] = nmap[ni]
            prims.append(mmd.Prim.encode(d))
        groups.append(list(proximal)+list(range(first, len(prims))))
        rays.append((root, axis))
    for group in WHOLE:
        points = [original[i] for i in sorted({v for pi in group for v in prims[pi].decode()['verts']})]
        root = mean([v for v in points if v[0] < 5])
        rays.append((root, unit(sub(mean([v for v in points if v[0] > 50]), root))))
        groups.append(list(group))
    spread(prims, verts, norms, groups, rays, original)
    pools = [list(model.tmd.obj_verts(i)) for i in range(len(model.tmd.objects))]
    normals = [list(model.tmd.obj_norms(i))[:o.nnorm] for i, o in enumerate(model.tmd.objects)]
    pools[9], normals[9], obj.prims = verts, norms, prims
    for oi in (10, 11):
        pools[oi], normals[oi], model.tmd.objects[oi].prims = [], [], []
    model.tmd.verts, model.tmd.norms = [], []
    for oi, ob in enumerate(model.tmd.objects):
        ob.vert_start, ob.nvert = len(model.tmd.verts), len(pools[oi])
        ob.norm_start, ob.nnorm = len(model.tmd.norms), len(normals[oi])
        model.tmd.verts.extend(pools[oi]); model.tmd.norms.extend(normals[oi])
    return dict(spread=SPREAD, tail_groups=groups, binding_bone=15,
                original_packets=224, final_packets=len(prims))


def spread(prims, verts, norms, groups, rays, original):
    """Open the fan: turn each whole tail away from the fan's mean ray.

    Every tail keeps its full length and width; only its direction changes,
    by SPREAD times its angle to the mean ray. The shared root apex (x < 5)
    stays where it is. Normals receive the same rotation.
    """
    center = unit(mean([axis for _, axis in rays]))
    output, done = [], set()
    for group, (root, axis) in zip(groups, rays):
        off = sub(axis, mul(center, dot(axis, center)))
        angle = math.atan2(math.sqrt(dot(off, off)), dot(axis, center))
        if dot(off, off) < 1e-12:
            output.append((root, axis))
            continue
        target = add(mul(center, math.cos(angle*SPREAD)), mul(unit(off), math.sin(angle*SPREAD)))
        ids = {v for pi in group for v in prims[pi].decode()['verts']}
        for vi in ids:
            if vi in done or (vi < len(original) and original[vi][0] < 5):
                continue
            done.add(vi)
            verts[vi] = packed(add(root, align(axis, target, sub(verts[vi][:3], root))))
        nmap = {}
        for pi in group:
            d = prims[pi].decode()
            for k, ni in enumerate(d['norms']):
                if ni not in nmap:
                    nmap[ni] = len(norms)
                    norms.append(packed(align(axis, target, norms[ni][:3])))
                d['norms'][k] = nmap[ni]
            prims[pi] = mmd.Prim.encode(d)
        output.append((root, target))
    return output


def packet_groups():
    """Stable provenance for audits after binding all nine tails to one joint."""
    return [list(proximal)+list(range(84+20*k, 104+20*k))
            for k, (proximal, _, _) in enumerate(JOINS)]+[list(p) for p in WHOLE]


def main():
    import argparse
    import json
    from pathlib import Path
    import numpy as np
    from tools.models.mesh_round4 import load, sparse_crossing
    p = argparse.ArgumentParser(description='Audit cross-tail geometry independently of bone assignment.')
    p.add_argument('folder', type=Path)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    model = load(args.folder, 409)
    groups = packet_groups()
    if (len(model.m.tmd.objects[9].prims) != 224 or
            any(model.m.tmd.objects[i].prims for i in (10, 11))):
        raise ValueError('fan audit requires the reviewed complete fan binding')
    triangles = [np.array([t[3] for t in model.tris if t[0] == 15 and t[2] in pis]) for pis in groups]
    rows = []
    for a in range(9):
        for b in range(a+1, 9):
            count, depth = sparse_crossing(model.local[15][triangles[a]], model.local[15][triangles[b]])
            rows.append(dict(tails=[a, b], triangle_pairs=count, depth_units=depth))
    joins = []
    for tail, (proximal, _, _) in enumerate(JOINS):
        end = range(84+20*tail, 104+20*tail)
        left, right = [np.array([t[3] for t in model.tris if t[0] == 15 and t[2] in pis])
                       for pis in (proximal, end)]
        count, depth = sparse_crossing(model.local[15][left], model.local[15][right])
        joins.append(dict(tail=tail, triangle_pairs=count, depth_units=depth))
    ticks = 0
    # Every ancestor remains rigid in every decoded pose. Consequently the
    # local cross-tail depths are invariant under all these world transforms.
    for slot in model.slots():
        poses = model.poses(slot, 6000)
        if len(poses) >= 6000:
            raise ValueError('fan audit exceeded decode guard')
        for pose in poses:
            R = model.matrices(pose)[15][:3, :3]
            if not np.allclose(R.T @ R, np.eye(3), atol=1e-9):
                raise ValueError('fan audit requires rigid ancestry in every tick')
        ticks += len(poses)
    result = dict(slots=len(model.slots()), ticks=ticks, groups=groups, pairs=rows,
                  cross_tail_max_depth_units=max(r['depth_units'] for r in rows),
                  attachment_pairs=joins,
                  max_depth_units=max(r['depth_units'] for r in rows+joins),
                  all_tick_depth_invariance_verified=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2)+'\n')
    print(f'{ticks} ticks: fan-section maximum {result["max_depth_units"]:.6f} units')


if __name__ == '__main__':
    main()
