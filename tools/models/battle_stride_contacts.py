"""Arena clearance and loop closure at the decoded display rate."""
import copy
import math

import animsheet
import mmd
from motiontailspace import interpolate_pose


def audit(data, skeleton, slot):
    nb = len(skeleton)
    mmd.exe().add_type(9496, skeleton)
    model = mmd.MMD.parse(data, nb)
    model.type = 9496
    local = {bone: [v[:3] for v in model.tmd.obj_verts(obj)]
             for bone, (obj, _) in enumerate(skeleton) if obj >= 0}
    frames, loop, _ = animsheet.slot_frames(model, nb, slot)

    def points(pose):
        pose = copy.deepcopy(pose)
        pose[0] = [4096] * 3 + [0] * 6
        world = mmd.bone_matrices(model, pose)
        return [(tuple(sum(world[bone][i][j] * v[j] for j in range(3)) + world[bone][i][3]
                       for i in range(3))) for bone in local for v in local[bone]]

    levels = []
    for tick, pose in enumerate(frames):
        for alpha in ((0, 1365, 2730) if tick+1 < len(frames) else (0,)):
            p = pose if not alpha else interpolate_pose(pose, frames[tick+1], alpha)
            levels.append(max(point[1] for point in points(p)))
    gap = max(math.dist(a, b) for a, b in zip(points(frames[loop]), points(frames[-1]))) if loop is not None else 0
    return dict(passed=min(levels) >= -8 and max(levels) <= 3 and gap <= 3,
                samples_60fps=len(levels), floor=[min(levels), max(levels)], loop_gap=gap)


def support_band(data, skeleton, slot, feet):
    """Independent decoded sole levels, including the player's display blends."""
    nb = len(skeleton)
    mmd.exe().add_type(9508, skeleton)
    model = mmd.MMD.parse(data, nb)
    model.type = 9508
    local = {bone: [v[:3] for v in model.tmd.obj_verts(skeleton[bone][0])]
             for bone in feet}
    frames = animsheet.slot_frames(model, nb, slot)[0]
    levels = []
    for tick, pose in enumerate(frames):
        for alpha in ((0, 1365, 2730) if tick+1 < len(frames) else (0,)):
            current = copy.deepcopy(pose) if not alpha else interpolate_pose(pose, frames[tick+1], alpha)
            current[0] = [4096]*3 + [0]*6
            world = mmd.bone_matrices(model, current)
            levels.append(max(sum(world[b][1][j]*v[j] for j in range(3))+world[b][1][3]
                              for b in feet for v in local[b]))
    return [min(levels), max(levels)]
