"""Scoped repairs for the reviewed 405/407/471/473/477 investigation.

Called behind mesh_cleanup's exact incoming TMD hash guard. Motion edits keep
the decoded root, translations, scales, events, timing and loop information.
"""
import math

import mmd


def ease_rotation(model, bones, slot, bone, axis, degrees):
    """Lift a joint through a clip with zero correction at either endpoint."""
    import animsheet
    index = model.anims.table[slot]
    if [s for s, i in enumerate(model.anims.table) if i == index] != [slot]:
        raise ValueError('eased correction requires an independent clip')
    frames, loop, events = animsheet.slot_frames(model, len(bones), slot)
    frames = [[[int(v) for v in b] for b in pose] for pose in frames]
    for tick, pose in enumerate(frames):
        weight = math.sin(math.pi*tick/(len(frames)-1))**2
        pose[bone][3+axis] += round(degrees*4096/360*weight)
    model.anims.anims[index] = mmd.encode_anim(frames, len(bones), loop, events, tol=0)


def fit_sprout_socket(model):
    """End the stem at its leaf graft instead of protruding into both leaves."""
    obj = model.tmd.objects[0]
    vertices = list(model.tmd.obj_verts(0))
    if len(vertices) != 194 or vertices[161][:3] != (-12, -90, -2):
        raise ValueError('sprout socket requires the reviewed compact mesh')
    # The eight terminal-ring corners move two units down; the cap moves three.
    # The cap then meets the existing leaf centre at (-12, -87, -2).
    shifts = {i: (3 if v[1] == -90 else 2) for i, v in enumerate(vertices[:162])
              if v[1] in (-87, -90)}
    if len(shifts) != 9:
        raise ValueError('sprout terminal ring no longer matches')
    old_normals = list(model.tmd.obj_norms(0))
    normals, lookup = [], {}
    for pi, prim in enumerate(obj.prims):
        d = prim.decode()
        for k, ni in enumerate(d['norms']):
            ids = d['verts'] if len(d['norms']) == 1 else [d['verts'][k]]
            affected = [vi for vi in ids if vi in shifts]
            n = old_normals[ni]
            if affected:
                # Inverse-transpose of the two shortened stem intervals.
                factor = 2/3 if all(vertices[vi][1] < -87 for vi in affected) else 5/6
                q = [n[0], n[1]/factor, n[2]]
                length = math.sqrt(sum(v*v for v in q))
                n = tuple(round(v*4096/length) if length else 0 for v in q)+(n[3],)
            if n not in lookup:
                lookup[n] = len(normals)
                normals.append(n)
            d['norms'][k] = lookup[n]
        obj.prims[pi] = mmd.Prim.encode(d)
    model.tmd.norms = normals
    obj.norm_start, obj.nnorm = 0, len(normals)
    for vi, shift in shifts.items():
        v = vertices[vi]
        model.tmd.verts[obj.vert_start+vi] = (v[0], v[1]+shift, v[2], v[3])


def apply(model, bones, sid):
    from tools.models.mesh_cleanup import rotate_clip_bone
    if sid == 405:
        # Neck tucks in these clips drive the head through the torso. Keep both
        # ends exact and lift the neck during the interior of the existing tuck.
        for slot in (35, 40, 41):
            ease_rotation(model, bones, slot, 3, 0, 15)
        return dict(neck_lift_slots=[35, 40, 41], neck_lift_degrees=15, easing='sin_squared')
    if sid == 407:
        # Open the rear hips while retaining every original swing increment.
        for slot in (2, 3):
            if [s for s, i in enumerate(model.anims.table)
                    if i == model.anims.table[slot]] != [slot]:
                raise ValueError('hip repair requires independent walk clips')
            rotate_clip_bone(model, slot, 15, (0, 8, 0))
            rotate_clip_bone(model, slot, 24, (0, -4, 0))
        # The existing zero-surface mouth removal frees 40 packet bytes; the
        # incoming stability pass left eight more. Spend only those 48 bytes.
        from tools.models import mesh_stability
        chosen, used = {}, 0
        for row in mesh_stability.bent_quads(model):
            oi, pi = row['object'], row['primitive']
            prim = model.tmd.objects[oi].prims[pi]
            halves = mesh_stability.split_quad(prim)
            cost = sum((p.olen+1)*4 for p in halves)-(prim.olen+1)*4
            if used+cost <= 48:
                chosen[oi, pi] = halves
                used += cost
        for oi, obj in enumerate(model.tmd.objects):
            obj.prims = [p for pi, prim in enumerate(obj.prims)
                         for p in chosen.get((oi, pi), [prim])]
        return dict(walk_rear_hip_yaw_degrees=[8, -4],
                    mouth_funded_splits=len(chosen), mouth_funded_packet_bytes=used)
    if sid == 473:
        fit_sprout_socket(model)
        return dict(stem_ring_retraction=2, stem_cap_retraction=3)
    return {}
