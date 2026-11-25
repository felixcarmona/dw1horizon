"""MegaGargomon-only final mechanical shell and motion repairs.

Called after the reviewed final-TMD guard in mesh_cleanup. The skeleton and
original channel controls remain authoritative; no other species use this pass.
"""
from tools.models.mesh_cleanup import transform_piece, rotate_clip_bone


# Full-size shoulder pods, seated slightly higher and further back about the
# shoulder mount (units: object space), so the forearm swing passes in front.
POD_OFFSET = (0, -10, -10)
# Field clips whose wider elbow swing still met the pod: (keep, limit) degrees.
ELBOW_SLOTS = {10: (60, 75), 12: (50, 65)}
# Field clips whose head roll or yaw swept the fins into the pod: the head's
# rotation is eased toward the idle pose by this factor (1 = unchanged).
HEAD_SWING = {9: .65, 13: .65, 19: .6, 22: .75, 24: .7}


def apply(model, bones):
    import animsheet
    from tools.models import mesh_pose
    report = {}
    # The imported elbow windups fold the gun back through the shell.
    # A periodic eased arc avoids the half-turn jump of a signed clamp.
    def elbow_arc(slot, tick, poses):
        return {(b, 0): mesh_pose.elbow_pitch(poses[tick][b][3]) for b in (15, 25)}
    report['elbow_arc_slots'] = mesh_pose.edit(model, bones, elbow_arc)
    for slot, (keep, limit) in ELBOW_SLOTS.items():
        mesh_pose.edit(model, bones, lambda s, t, poses: {
            (b, 0): mesh_pose.elbow_pitch(poses[t][b][3], keep, limit) for b in (15, 25)}, slots=[slot])
    report['elbow_slot_arcs'] = {str(k): list(v) for k, v in ELBOW_SLOTS.items()}
    # Keep the source shoulder pods at full size; move them clear instead.
    for oi in (12, 22):
        transform_piece(model, oi, scale=(1, 1, 1), offset=POD_OFFSET)
    report['shoulder_fit'] = 1
    report['shoulder_offset'] = list(POD_OFFSET)
    ref = animsheet.slot_frames(model, len(bones), 0, max_ticks=1)[0][0]
    def wrap(a):
        return (a+2048) % 4096-2048
    for slot, k in HEAD_SWING.items():
        mesh_pose.edit(model, bones, lambda s, t, poses: {
            (17, a): ref[17][3+a]+round(k*wrap(poses[t][17][3+a]-ref[17][3+a])) for a in range(3)},
            slots=[slot])
    report['head_swing'] = {str(k): v for k, v in HEAD_SWING.items()}
    # The remaining mirrored shoulder contact is confined to this attack.
    # Keep its swing and easing with a small constant upper-arm correction.
    rotate_clip_bone(model, 48, 14, (5, 0, 0))
    report['slot_48_upper_arm_pitch_degrees'] = 5
    report.update(finish(model, bones))
    return report


# Skirt taper about the waist ring: radial at the hem, vertical below the ring.
PR, PV = .8, .7


def taper_pelvis(model):
    """Shorten the lower skirt about its intact waist ring, with normal refit."""
    import math
    import mmd
    obj = model.tmd.objects[1]
    vertices = list(model.tmd.obj_verts(1))
    old = list(model.tmd.obj_norms(1))
    pools = [list(model.tmd.obj_norms(i))[:ob.nnorm]
             for i, ob in enumerate(model.tmd.objects)]
    normals, lookup = [], {}
    for pi, prim in enumerate(obj.prims):
        d = prim.decode()
        for k, ni in enumerate(d['norms']):
            points = [vertices[v] for v in d['verts']] if len(d['norms']) == 1 else [vertices[d['verts'][k]]]
            x, y, z = [sum(v[j] for v in points)/len(points) for j in range(3)]
            radial = 1-(1-PR)*max(0, min(1, (y-13)/84))
            slope = -(1-PR)/84 if 13 < y < 97 else 0
            vertical = PV if y > 13 else 1
            n = old[ni]
            q = [n[0]/radial,
                 (n[1]-slope*(x*n[0]+z*n[2])/radial)/vertical,
                 n[2]/radial]
            length = math.sqrt(sum(v*v for v in q))
            normal = tuple(round(v*4096/length) if length else 0 for v in q)+(n[3],)
            if normal not in lookup:
                lookup[normal] = len(normals)
                normals.append(normal)
            d['norms'][k] = lookup[normal]
        obj.prims[pi] = mmd.Prim.encode(d)
    pools[1] = normals
    model.tmd.norms = []
    for ob, pool in zip(model.tmd.objects, pools):
        ob.norm_start, ob.nnorm = len(model.tmd.norms), len(pool)
        model.tmd.norms.extend(pool)
    for i, v in enumerate(vertices):
        radial = 1-(1-PR)*max(0, min(1, (v[1]-13)/84))
        y = 13+(v[1]-13)*PV if v[1] > 13 else v[1]
        model.tmd.verts[obj.vert_start+i] = (round(v[0]*radial), round(y), round(v[2]*radial), v[3])


def finish(model, bones):
    """Further fit the pelvis and fund GPU-diagonal splits from invisible fins."""
    import mmd
    import motionstorage
    from tools.models import mesh_stability
    for slot, index in enumerate(model.anims.table):
        if index is None:
            continue
        poses, _ = mmd.simulate(model.anims.anims[index], len(bones), slot=slot)
        if any(any(p[b][c] != 4096 for c in range(3))
               for p in poses for b in range(len(bones)) if b not in (20, 21)):
            raise ValueError('visible scale varies; cannot remove its records')
        if any(any(p[b][c] != 0 for c in range(3)) for p in poses for b in (20, 21)):
            raise ValueError('duplicate fin is visible; cannot use its storage')
    for bone, oi in ((20, 19), (21, 20)):
        if tuple(bones[bone]) != (oi, 17):
            raise ValueError('duplicate fin binding changed')
        model.tmd.objects[oi].prims = []
    # Unit scales are implicit in a non-scale program. The only nonunit
    # scales belonged to the removed fins. Keep every instruction and channel
    # for visible bones, but remove this now-redundant initial-pose storage.
    for anim in model.anims.anims:
        if anim.has_scale:
            if any(any(v != 4096 for v in pose[:3])
                   for b, pose in enumerate(anim.pose, 1) if b not in (20, 21)):
                raise ValueError('visible scale is not unit')
            anim.pose = [pose[3:] for pose in anim.pose]
            anim.has_scale = False
        for ins in anim.instrs:
            if ins['op'] == 'key':
                kept = []
                for key in ins['bones']:
                    for channel in ('sx', 'sy', 'sz'):
                        if channel in key['vals']:
                            expected = 0 if key['bone'] in (20, 21) or key['div'] else 4096
                            if key['vals'][channel] != expected:
                                raise ValueError('scale key is not a constant invariant')
                    key['vals'] = {ch: value for ch, value in key['vals'].items()
                                   if ch not in ('sx', 'sy', 'sz')}
                    if key['vals']:
                        kept.append(key)
                ins['bones'] = kept
    taper_pelvis(model)
    # An exact integer normal test avoids treating floating acos noise as bend.
    selected = set()
    for oi, ob in enumerate(model.tmd.objects):
        vertices = model.tmd.obj_verts(oi)
        for pi, prim in enumerate(ob.prims):
            ids = prim.decode()['verts']
            if len(ids) != 4:
                continue
            a, b, c, d = [vertices[i] for i in ids]
            n, q = mesh_stability._normal(a,b,c), mesh_stability._normal(b,d,c)
            cross = (n[1]*q[2]-n[2]*q[1], n[2]*q[0]-n[0]*q[2], n[0]*q[1]-n[1]*q[0])
            if any(n) and any(q) and (any(cross) or sum(x*y for x,y in zip(n,q)) < 0):
                selected.add((oi, pi))
    for oi, ob in enumerate(model.tmd.objects):
        ob.prims = [p for pi, prim in enumerate(ob.prims)
                    for p in (mesh_stability.split_quad(prim) if (oi,pi) in selected else [prim])]
    mesh_stability.compact_pools(model)
    storage = motionstorage.require(model.build(), len(bones))
    if storage['resident_bytes'] > 97536:
        raise ValueError('MegaGargomon repair exceeded its own previous resident size')
    return dict(hidden_fin_objects=[19,20], pelvis_lower_fit=[PR,PV,PR],
                leg_repair_slots=[],
                additional_quad_splits=len(selected))

