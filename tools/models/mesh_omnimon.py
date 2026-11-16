"""Omnimon's final surface and articulated-clearance fits, after stability.

Object numbers and offsets refer to the reviewed 25-bone DCB binding. The
caller checks the incoming TMD hash. No other species uses these fits.
"""
import json
import math
from pathlib import Path

import mmd

# Each row names one program through its first occupied slot. Values are
# degrees: arm 3 yaw/roll, arm 9 yaw/roll, cape 23 pitch, cape 24 pitch;
# an optional final triple corrects elbow 10 pitch/yaw/roll.
POSES = Path(__file__).resolve().parents[2] / 'content/models/authoring/omnimon-clearance.json'


def cut_blade(model, start=150):
    """Trim the concealed tang, preserving the tip and texture coordinates.

    Moving only the low ring leaves the blade's existing planes unchanged.
    Interpolate UVs at the cut rather than squeezing the entire inscription
    onto the remaining visible blade. No packet or corner is discarded.
    """
    oi = 6
    obj = model.tmd.objects[oi]
    old = list(model.tmd.obj_verts(oi))
    for pi, prim in enumerate(obj.prims):
        d = prim.decode()
        if d['uv']:
            uv = list(d['uv'])
            for k, vi in enumerate(d['verts']):
                v = old[vi]
                if v[1] >= start:
                    continue
                matches = [j for j, vj in enumerate(d['verts'])
                           if old[vj][0] == v[0] and old[vj][2] == v[2] and old[vj][1] > start]
                if len(matches) != 1:
                    raise ValueError('Omnimon blade cut requires a matching longitudinal edge')
                j = matches[0]
                t = (start-v[1])/(old[d['verts'][j]][1]-v[1])
                uv[k] = tuple(round(a+(b-a)*t) for a, b in zip(d['uv'][k], d['uv'][j]))
            d['uv'] = uv
            obj.prims[pi] = mmd.Prim.encode(d)
    for i, v in enumerate(old):
        model.tmd.verts[obj.vert_start+i] = (v[0], max(start, v[1]), v[2], v[3])


def _cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def _unit(v):
    length = math.sqrt(sum(x*x for x in v))
    if length < 1e-9:
        raise ValueError('Omnimon surface fit collapsed a triangle or normal')
    return [x/length for x in v]


def _normal(vertices, ids):
    a, b, c = (vertices[i] for i in ids)
    return _unit(_cross([b[i]-a[i] for i in range(3)], [c[i]-a[i] for i in range(3)]))


def fit_surface(model, oi, mapper):
    """Move a surface and transport its smooth normals with its GPU triangles.

    Each original normal is rotated with the incident triangles, then their
    contributions are averaged. Hard seams and opposite cloth faces keep
    their separate normal indices. The normal pool and packet sizes stay fixed.
    """
    obj = model.tmd.objects[oi]
    old = list(model.tmd.obj_verts(oi))
    new = [tuple(mapper(*v[:3]))+(v[3],) for v in old]
    normals = model.tmd.obj_norms(oi)[:obj.nnorm]
    total = [[0., 0., 0.] for _ in normals]
    for prim in obj.prims:
        d = prim.decode()
        for corners in ((0, 1, 2), (1, 3, 2)) if len(d['verts']) == 4 else ((0, 1, 2),):
            ids = [d['verts'][i] for i in corners]
            a, b = _normal(old, ids), _normal(new, ids)
            axis = _cross(a, b)
            cosine = sum(x*y for x, y in zip(a, b))
            if cosine < -.999999:
                raise ValueError('Omnimon surface fit reversed a triangle')
            for k in corners:
                ni = d['norms'][k if len(d['norms']) > 1 else 0]
                n = _unit(normals[ni][:3])
                first = _cross(axis, n)
                second = _cross(axis, first)
                for j in range(3):
                    total[ni][j] += n[j]+first[j]+second[j]/(1+cosine)
    model.tmd.verts[obj.vert_start:obj.vert_start+obj.nvert] = new
    for i, v in enumerate(total):
        q = _unit(v) if any(v) else _unit(normals[i][:3])
        model.tmd.norms[obj.norm_start+i] = tuple(round(x*4096) for x in q)+(normals[i][3],)


def fit_cape(model):
    """Seat both panels on a straight fold instead of overlapping folded rings.

    A one-unit seam allowance separates the articulated rigid panels. The
    neckline stays at its socket; the upper panel narrows around the arms,
    while the lower panel retains its length and flared, folded hem.
    """
    def upper(x, y, z):
        if y > 100:
            y, z = 109, 50
        if y < 1:
            z = max(z, 5)
        return round(x*.75), y, z

    def lower(x, y, z):
        if y < 0:
            return round(x*129/90*.75), 1, 0
        return round(x*.9), y, z

    fit_surface(model, 22, upper)
    fit_surface(model, 23, lower)


def merge_near_normals(model, degrees=4):
    """Fund cloth keys and triangle splits with a bounded lighting approximation.

    Each replacement is an original normal in the same object, within the
    angular threshold. Geometry, UVs, materials and opposing faces survive.
    The common final pool compactor removes the unused entries.
    """
    count, max_angle = 0, 0.
    cosine = math.cos(degrees*math.pi/180)
    for oi, obj in enumerate(model.tmd.objects):
        normals = model.tmd.obj_norms(oi)[:obj.nnorm]
        representatives, mapping = [], {}
        for i, n in enumerate(normals):
            q = _unit(n[:3])
            match = next(((j, v) for j, v in representatives
                          if sum(a*b for a, b in zip(q, v)) >= cosine), None)
            if match is None:
                representatives.append((i, q))
                mapping[i] = i
            else:
                j, v = match
                mapping[i] = j
                max_angle = max(max_angle, math.degrees(math.acos(min(1., sum(a*b for a, b in zip(q, v))))))
                count += 1
        for pi, prim in enumerate(obj.prims):
            d = prim.decode()
            d['norms'] = [mapping[i] for i in d['norms']]
            obj.prims[pi] = mmd.Prim.encode(d)
    return dict(merged_normals=count, max_normal_error_degrees=max_angle)


def apply(model, bones):
    from tools.models import mesh_cleanup as C, mesh_pose
    if len(bones) != 25 or any(tuple(bones[b]) != expected for b, expected in
            ((4, (3, 3)), (7, (6, 4)), (23, (22, 1)), (24, (23, 23)))):
        raise ValueError('Omnimon clearance requires the reviewed DCB binding')
    # Retain the previous face-layer, ankle and toe repairs.
    C.offset_layer(model, 1, range(6), (0, 0, -6))
    for oi in (15, 19):
        C.taper_ankle(model, oi)
    for oi in (17, 21):
        C.fit_toe_lip(model, oi, factor=.53 if oi == 17 else .76)
    report = dict(face_layer_offset=-6, ankle_radial_fit=.6,
                  toe_rear_lip_fit=[.53, .76], left_toe_arc_gain=.5)
    report['left_toe_arc_slots'] = mesh_pose.edit(model, bones,
        lambda slot, tick, poses: {(18, 0): round(poses[tick][18][3]*.5)}, {40, 41})

    # Earlier fits retain oversized source normal slices for landmarks. Keep
    # only referenced entries before transporting or comparing these normals.
    from tools.models import mesh_stability
    mesh_stability.compact_pools(model)
    cut_blade(model)
    fit_cape(model)
    C.translate_bone(model, 24, 2, 30)
    # Scale only the excessive flap arcs. The original per-frame easing is
    # retained; subsequent constant offsets seat the reduced arcs behind the
    # shoulders. These three clips formerly folded the cloth into the body.
    def cape_arc(slot, tick, poses):
        channels = (23, 24) if slot == 43 else (23,)
        return {(bone, 0): round(poses[tick][bone][3]*.4) for bone in channels}
    report['cape_arc_slots'] = mesh_pose.edit(model, bones, cape_arc, {40, 41, 43})
    report['cape_arc_gain'] = .4
    done = set()
    for slot, angles in json.loads(POSES.read_text()).items():
        slot = int(slot)
        index = model.anims.table[slot]
        if index is None or index in done:
            raise ValueError('Omnimon clearance table must name each program exactly once')
        done.add(index)
        for bone, rotation in ((3, (0, *angles[:2])), (9, (0, *angles[2:4])),
                               (23, (angles[4], 0, 0)), (24, (angles[5], 0, 0))):
            C.rotate_clip_bone(model, slot, bone, rotation)
        if len(angles) == 9:
            C.rotate_clip_bone(model, slot, 10, angles[6:9])
        elif len(angles) != 6:
            raise ValueError('Omnimon clearance requires six or nine rotation offsets')
    if done != {i for i in model.anims.table if i is not None}:
        raise ValueError('Omnimon clearance table does not cover every occupied program')
    report.update(blade_start=150, cape_straight_fold=True, cape_tip_socket_z=30,
                  clearance_programs=sorted(done))
    # The newly straight fold is articulated, not a bent quad controlled by
    # the culling result of its first half. Split both cloth windings along
    # their existing GPU diagonals, retaining all triangle corner attributes.
    splits = 0
    for oi in (22, 23):
        obj = model.tmd.objects[oi]
        prims = []
        for prim in obj.prims:
            if len(prim.decode()['verts']) == 4:
                prims.extend(mesh_stability.split_quad(prim))
                splits += 1
            else:
                prims.append(prim)
        obj.prims = prims
    report['cape_quad_splits'] = splits
    report.update(merge_near_normals(model))
    mesh_stability.compact_pools(model)
    import coldsplit
    resident = len(coldsplit.split(model.build(), len(bones))[0])
    if resident > 81566:
        raise ValueError(f'Omnimon clearance exceeded its own 81,566-byte resident budget: {resident}')
    report['own_resident_limit'] = 81566
    return report
