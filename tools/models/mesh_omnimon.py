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


def _unit(v):
    length = math.sqrt(sum(x*x for x in v))
    if length < 1e-9:
        raise ValueError('Omnimon surface fit collapsed a triangle or normal')
    return [x/length for x in v]


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
    # The blade keeps its full tang inside the guard: cutting it opened a
    # visible gap between guard and blade. The cape keeps the source's full panels: an earlier fit narrowed them
    # to a quarter less width and refolded them, which read as a lost cape.
    # Its clearance comes from the clips instead: the reduced flap arcs below
    # and, per program, a slightly higher cape-base pitch in POSES.
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
    report.update(blade_source_tang=True, cape_source_panels=True,
                  clearance_programs=sorted(done))
    # The fold is articulated, not a bent quad controlled by the culling
    # result of its first half. Split both cloth windings along their
    # existing GPU diagonals, retaining all triangle corner attributes.
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
