"""MaloMyotismon 406: reviewed cannon fitting and motion clearance.

This boundary is deliberately species-local. Shared fitting, other species and
alternate source outputs do not depend on this module.
"""


def apply(model, bones):
    from tools.models.mesh_cleanup import transform_piece, translate_bone
    report = {}
    # Both cannon caps cut through the housings. Advance their rear lip
    # eight local units; their separate animation and material stay intact.
    for oi in (2, 9):
        transform_piece(model, oi, offset=(0, 0, -8))
    report['cannon_cap_offset'] = -8
    # The lids were pivoting from inside the housings. Seat their upper
    # rear edge on the mouth instead: their original negative-pitch opening
    # now sweeps outward. Keep all recoil keys and the full opening curve.
    for bone, oi in ((3, 2), (11, 9)):
        translate_bone(model, bone, 1, -15)
        translate_bone(model, bone, 2, -121)
        transform_piece(model, oi, scale=(1, 1, .3), offset=(0, 45, -12))
    report['cannon_hinge_offset'] = [0, -15, -121]
    report['cannon_lid_depth_fit'] = .3
    # The firing program crossed both arms through the mouths. Brace them
    # beside the cannons, retaining a small eased recoil from their authored
    # curves; the chest, cannon opening, effects and firing events stay exact.
    from tools.models import mesh_pose
    def cannon_brace(slot, tick, poses):
        targets = {4: (-20, 0, 20), 12: (-20, 0, -20),
                   5: (-15, 0, 0), 13: (-15, 0, 0)}
        return {(bone, axis): round(deg*4096/360+
                    .15*(poses[tick][bone][3+axis]-poses[0][bone][3+axis]))
                for bone, angles in targets.items() for axis, deg in enumerate(angles)}
    report['cannon_brace_slots'] = mesh_pose.edit(model, bones, cannon_brace, {54, 61})
    report['cannon_brace_recoil_gain'] = .15
    report.update(polish(model, bones))
    return report


# Degrees in local bone axes. Constant offsets preserve each source curve's
# velocity and easing, including absolute keys and positive-divisor increments.
# Slots name canonical programs: aliases are intentionally processed once.
ROTATION_OFFSETS = {3: {12: (0, 0, -20)},
 8: {12: (-20, 0, -20)},
 9: {4: (-40, 0, 20), 12: (-20, 0, 0)},
 12: {4: (40, 0, 0), 5: (20, 0, 0)},
 21: {4: (-20, 0, 20), 12: (-40, 0, 0)},
 27: {4: (0, 0, -20)},
 42: {5: (20, 0, 0)},
 43: {12: (-20, 0, 0)},
 44: {4: (-20, 0, 20), 12: (-40, 0, 0)},
 46: {4: (-20, 0, 40), 5: (20, 0, 0)},
 47: {4: (20, 0, 0), 13: (-20, 0, 0)},
 52: {4: (40, 0, 0), 5: (40, 0, 0)}}


def windup_brace(slot, tick, poses):
    """Keep the left strike; give the right arm an eased counterbalance.

    The source right arm sweeps through the wing. Preserve its timing and curve
    with a 20% excursion about an outward brace, rather than a framewise clamp.
    """
    from tools.models.mesh_pose import smoothstep
    weight = smoothstep(tick/3)*smoothstep((len(poses)-1-tick)/3)
    targets = {12: (30, 0, -30), 13: (0, 0, 0)}
    result = {(bone, axis): round(poses[tick][bone][3+axis]*(1-weight) + weight*(
                degrees*4096/360 + .2*(poses[tick][bone][3+axis]-poses[0][bone][3+axis])))
              for bone, angles in targets.items() for axis, degrees in enumerate(angles)}
    result.update({(4, axis): poses[tick][4][3+axis]+round(degrees*4096/360*weight)
                   for axis, degrees in ((0, -80), (2, 20))})
    return result


def lid_dodge(slot, tick, poses):
    """Open the covers during the tuck, returning to the exact entry/exit pose."""
    # Three exact linear pieces ease in/out without a separate key every tick.
    # Their speeds are 36, 54, 24 angle units per tick; both ends are exactly 0.
    def ramp(t):
        t = max(0, min(9, t))
        if t <= 3:
            return 36*t
        if t <= 6:
            return 108+54*(t-3)
        return 270+24*(t-6)
    angle = min(ramp(tick), ramp(len(poses)-1-tick))
    return {(bone, 0): poses[tick][bone][3]-angle
            for bone in ((3, 11) if slot == 47 else (11,))}


def polish(model, bones):
    """Repair located clip contacts, funding any encoded keys inside model 406."""
    import coldsplit
    from tools.models.mesh_cleanup import rotate_clip_bone
    from tools.models import mesh_pose
    from tools.models.field_animations.channels import coalesce
    if len(bones) != 31 or tuple(bones[13]) != (11, 12):
        raise ValueError('MaloMyotismon repair requires the reviewed 31-bone binding')
    resident_before = len(coldsplit.split(model.build(), len(bones))[0])
    seen = set()
    for slot, changes in ROTATION_OFFSETS.items():
        index = model.anims.table[slot]
        for bone, angles in changes.items():
            if (index, bone) in seen:
                raise ValueError('MaloMyotismon repair would apply an alias twice')
            seen.add((index, bone))
            rotate_clip_bone(model, slot, bone, angles)
    changed = mesh_pose.edit(model, bones, windup_brace, {55})
    lids = mesh_pose.edit(model, bones, lid_dodge, {46, 47, 52})
    # Exact common-divisor and same-frame key packing. This saves this model's
    # own bytes; no budget or provider pin of another species is borrowed.
    merged = 0
    for index, animation in enumerate(model.anims.anims):
        model.anims.anims[index], count = coalesce(animation)
        merged += count
    resident_after = len(coldsplit.split(model.build(), len(bones))[0])
    if resident_after > resident_before:
        raise ValueError(f'MaloMyotismon clip repair grew resident allocation: {resident_before} -> {resident_after}')
    return dict(clearance_offsets=ROTATION_OFFSETS, windup_brace_slots=changed,
                windup_brace_gain=.2, lid_dodge_slots=lids, lid_dodge_angle_units=-342,
                lid_dodge_ramp_ticks=9, coalesced_keys=merged,
                clearance_resident_before=resident_before,
                clearance_resident_after=resident_after)
