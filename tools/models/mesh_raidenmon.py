"""Raidenmon's gun-arm clearance and identical rigid-piece storage.

Applied after the existing reviewed final repairs. Shared TMD pools contain
identical immutable local coordinates; each object keeps its own joint matrix,
vertex/normal count, packets and corner attributes.
"""
from tools.models import mesh_pose


def gun_arm_detour(tick):
    """Degree offsets for slot 43; smooth ramps follow the original swing."""
    ease = mesh_pose.smoothstep
    yaw = 15*ease((tick-22)/4)*(1-ease((tick-37)/2)*(1-ease((tick-39)/2)))
    roll = 15*(1-ease((tick-7)/3))+15*ease((tick-23)/4)+30*ease((tick-31)/4)
    return (-15*ease((tick-40)/4), yaw, roll)


def share_identical_pools(model):
    """Share equal whole pools, remapping indices without changing corners.

    Pool sets must match exactly, including the fourth SVECTOR component.
    Counts never grow. This does not weld geometry across moving joints.
    """
    report = {}
    for attribute, start, count, getter, corner in (
            ('verts', 'vert_start', 'nvert', model.tmd.obj_verts, 'verts'),
            ('norms', 'norm_start', 'nnorm', model.tmd.obj_norms, 'norms')):
        source = [list(getter(i))[:getattr(ob, count)] for i, ob in enumerate(model.tmd.objects)]
        pools, unique, shared = [], {}, []
        for oi, (ob, values) in enumerate(zip(model.tmd.objects, source)):
            key = (len(values), frozenset(map(tuple, values)))
            if key in unique:
                offset, canonical = unique[key]
                lookup = {tuple(v): i for i, v in enumerate(canonical)}
                mapping = [lookup[tuple(v)] for v in values]
                for pi, prim in enumerate(ob.prims):
                    decoded = prim.decode()
                    decoded[corner] = [mapping[i] for i in decoded[corner]]
                    ob.prims[pi] = type(prim).encode(decoded)
                setattr(ob, start, offset)
                shared.append(oi)
            else:
                unique[key] = (len(pools), values)
                setattr(ob, start, len(pools))
                pools.extend(values)
        old = len(getattr(model.tmd, attribute))
        setattr(model.tmd, attribute, pools)
        report[attribute] = dict(shared_objects=shared, saved_bytes=8*(old-len(pools)))
    return report


def apply(model, bones):
    """Repair this model only; the caller owns its reviewed input guard."""
    if (len(bones) != 24 or tuple(bones[2]) != (1, 1) or
            tuple(bones[3]) != (2, 2) or tuple(bones[10]) != (9, 1)):
        raise ValueError('Raidenmon repair requires the reviewed 24-joint binding')
    if [s for s, index in enumerate(model.anims.table) if index == model.anims.table[43]] != [43]:
        raise ValueError('Raidenmon repair requires independent slot 43')
    if [s for s, index in enumerate(model.anims.table) if index == model.anims.table[61]] != [61]:
        raise ValueError('Raidenmon repair requires independent slot 61')
    import motionstorage
    resident_before = motionstorage.require(model.build(), len(bones))['resident_bytes']
    def mapper(slot, tick, poses):
        return {(2, axis): poses[tick][2][3+axis]+round(degrees*4096/360)
                for axis, degrees in enumerate(gun_arm_detour(tick))}
    changed = mesh_pose.edit(model, bones, mapper, {43})
    from tools.models.mesh_cleanup import rotate_clip_bone
    # The large claw rests inside the leg silhouette in the donor's field
    # programs too. Open its shoulder while keeping the authored swing.
    done = set()
    claw_slots = []
    for slot, index in enumerate(model.anims.table):
        if index is None or index in done:
            continue
        done.add(index)
        rotate_clip_bone(model, slot, 10, (-60, 0, -15) if slot == 61 else (-15, -15, -30))
        claw_slots.append(slot)
    pools = share_identical_pools(model)
    resident_after = motionstorage.require(model.build(), len(bones))['resident_bytes']
    if resident_after > resident_before:
        raise ValueError('Raidenmon must fund its own animation changes')
    return dict(resident_bytes_before_after=[resident_before, resident_after],
                gun_arm_slots=changed, claw_arm_slots=claw_slots,
                claw_arm_degrees=[-15, -15, -30], slot61_claw_degrees=[-60, 0, -15], identical_pools=pools)
