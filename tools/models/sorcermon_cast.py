"""Keep Sorcermon's casting staff clear while its boots support its weight."""
import copy
import math

import animsheet
import mmd
import retarget
from motiontailspace import interpolate_pose
from tools.models import clip_repair
from tools.models.field_animations.native_battle import scaled_events
from tools.models.authored_battle import _clean
from tools.models.battle_finishes import _ground_frames
from tools.models.field_animations import quadruped as q


def repair(data, skeleton, slot=55, frame_count=107):
    nb = len(skeleton)
    mmd.exe().add_type(9400, skeleton)
    model = mmd.MMD.parse(data, nb)
    model.type = 9400
    frames, loop, events = animsheet.slot_frames(model, nb, slot)
    events = scaled_events(events, len(frames), frame_count)
    frames = clip_repair.retime(copy.deepcopy(frames), frame_count-1)
    frames = [[[round(v) for v in bone] for bone in pose] for pose in frames]
    local = {b: [v[:3] for v in model.tmd.obj_verts(o)]
             for b, (o, _) in enumerate(skeleton) if o >= 0}

    def feet(pose):
        pose = copy.deepcopy(pose)
        pose[0] = [4096]*3 + [0]*6
        world = mmd.bone_matrices(model, pose)
        return max(sum(world[b][1][j]*v[j] for j in range(3))+world[b][1][3]
                   for b in (21, 24) for v in local[b])

    _ground_frames(frames, feet)
    identity = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]

    def clearance(pose, target_level=-6):
        world = mmd.bone_matrices(model, pose)
        rotation = [row[:3] for row in world[9][:3]]
        center = [world[9][i][3] for i in range(3)]
        vectors = [q.mv(rotation, v) for v in local[9]]
        lowest = max(vectors, key=lambda v: v[1])
        if center[1]+lowest[1] <= target_level:
            return identity
        target = [lowest[0], 0, lowest[2]]
        if q.norm(target) < 1e-6:
            target = [1, 0, 0]
        turn = retarget.swing(lowest, target)

        def level(gain):
            adjustment = retarget.scale_rot(turn, gain)
            return max(q.mv(adjustment, v)[1]+center[1] for v in vectors)

        if level(1) > target_level:
            raise ValueError('the casting wrist cannot clear the floor')
        low, high = 0., 1.
        for _ in range(24):
            middle = (low+high)/2
            if level(middle) > target_level:
                low = middle
            else:
                high = middle
        return retarget.scale_rot(turn, high)

    def apply_rotation(pose, adjustment):
        rotations = retarget.world_rots(skeleton, pose)
        parent = skeleton[9][1]
        local_rotation = q.mul(q.tr(rotations[parent]), q.mul(adjustment, rotations[9]))
        pose[9][3:6] = [round(v) for v in mmd.matrix_euler(local_rotation, pose[9][3:6])]

    corrections = [clearance(pose) for pose in frames]
    for _ in range(2):
        corrections = [native_blend(corrections, i) for i in range(len(corrections))]
    for pose, adjustment in zip(frames, corrections):
        apply_rotation(pose, adjustment)
    # Fit the display blends too; the wrist follows an arc between stored keys.
    for _ in range(8):
        worst = -float('inf')
        for i in range(len(frames)-1):
            for alpha in (0, 1365, 2730, 4096):
                pose = interpolate_pose(frames[i], frames[i+1], alpha)
                world = mmd.bone_matrices(model, pose)
                level = max(sum(world[9][1][j]*v[j] for j in range(3))+world[9][1][3]
                            for v in local[9])
                worst = max(worst, level)
                if level <= -1:
                    continue
                adjustment = clearance(pose, -3)
                weight = alpha/4096
                divisor = (1-weight)**2 + weight**2
                for index, share in ((i, 1-weight), (i+1, weight)):
                    if share:
                        apply_rotation(frames[index], retarget.scale_rot(adjustment, share/divisor))
        if worst <= -.5:
            break
    model.anims.table[slot] = len(model.anims.anims)
    model.anims.anims.append(mmd.encode_anim(frames, nb, loop, events,
                                            tol={0: 0, 1: 0, None: 5}, repeats=False))
    return _clean(model)


def native_blend(rotations, tick):
    from tools.models.field_animations.native_battle import mean_rotation
    return mean_rotation([rotations[max(0, tick-1)], rotations[tick],
                          rotations[min(len(rotations)-1, tick+1)]], [.25, .5, .25])
