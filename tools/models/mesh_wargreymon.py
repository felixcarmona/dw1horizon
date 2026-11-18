"""Reviewed final-provider repair of DCB 173's shield and glove sockets.

Called by mesh_cleanup after its TMD identity check. Source/import, chibi and
motion pins stay intact. Object/primitive numbers here refer to that final TMD,
not to the card model or the pre-stability mesh.
"""
import copy

import coldsplit
import mmd
from tools.models import mesh_stability


def apply(model, bones):
    before = len(coldsplit.split(model.build(), len(bones))[0])
    pools = [list(model.tmd.obj_verts(i)) for i in range(len(model.tmd.objects))]
    for oi, side in ((18, 1), (19, -1)):
        # Closed pose has joint X=-6/+6; the old medial X=+5/-5
        # leaves a two-unit crack. Move only the three medial corners.
        pools[oi] = [(side*6, *v[1:]) if v[0] == side*5 else v for v in pools[oi]]
        obj = model.tmd.objects[oi]
        prims, midpoints = [], {}
        for pi, prim in enumerate(obj.prims):
            if pi >= 4:  # keep the inner, opposite-facing surface
                prims.append(prim)
                continue
            # These four outward triangles span the entire shield height.
            # AVSZ3 otherwise puts rear torso/hip packets in front of them.
            # Weld shared midpoints; never create cracks between subdivisions.
            d = prim.decode()
            mids, uvs = [], list(d['uv'])
            for a, b in ((0, 1), (1, 2), (2, 0)):
                va, vb = d['verts'][a], d['verts'][b]
                key = tuple(sorted((va, vb)))
                if key not in midpoints:
                    midpoints[key] = len(pools[oi])
                    pools[oi].append(tuple(round((pools[oi][va][k]+pools[oi][vb][k])/2)
                                           for k in range(4)))
                mids.append(midpoints[key])
                uvs.append(tuple(round((d['uv'][a][k]+d['uv'][b][k])/2) for k in range(2)))
            verts = d['verts'] + mids
            if len(d['norms']) != 1:
                raise ValueError('WarGreymon shield must have flat corner normals')
            for corners in ((0, 3, 5), (3, 1, 4), (5, 4, 2), (3, 4, 5)):
                child = copy.deepcopy(d)
                child['verts'] = [verts[k] for k in corners]
                child['uv'] = [uvs[k] for k in corners]
                prims.append(mmd.Prim.encode(child))
        obj.prims = prims
    for oi in (6, 8):
        obj = model.tmd.objects[oi]
        # Opposing GPU half-facings at the glove socket: 4.68 and 4.08 deg.
        obj.prims = [p for pi, prim in enumerate(obj.prims)
                     for p in (mesh_stability.split_quad(prim) if pi in (36, 37) else [prim])]
    model.tmd.verts = []
    for obj, pool in zip(model.tmd.objects, pools):
        obj.vert_start, obj.nvert = len(model.tmd.verts), len(pool)
        model.tmd.verts.extend(pool)
    after = len(coldsplit.split(model.build(), len(bones))[0])
    if after > (before+2047)//2048*2048:
        raise ValueError('WarGreymon repair exceeded the existing rounded resident read')
    return dict(shield_subdivided=[18, 19], shield_spine_units=1,
                glove_splits=4, resident_before=before, resident_after=after)
