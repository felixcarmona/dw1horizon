"""Fit a technique's body height without lifting its boots farther than main."""
import copy

import animsheet
import mmd
from motiontailspace import interpolate_pose
from tools.models.authored_battle import _clean


def fit(data, skeleton, slot, feet, baseline):
    nb = len(skeleton)
    mmd.exe().add_type(9507, skeleton)
    model, main = [mmd.MMD.parse(blob, nb) for blob in (data, baseline)]
    model.type = 9507
    local = {b: [v[:3] for v in model.tmd.obj_verts(o)]
             for b, (o, _) in enumerate(skeleton) if o >= 0}

    def levels(pose):
        pose = copy.deepcopy(pose)
        pose[0] = [4096]*3 + [0]*6
        world = mmd.bone_matrices(model, pose)
        values = {b: max(sum(world[b][1][j]*v[j] for j in range(3))+world[b][1][3]
                         for v in local[b]) for b in local}
        return max(values[b] for b in feet), max(values.values())

    original = animsheet.slot_frames(main, nb, slot)[0]
    baseline_floor = min(levels(interpolate_pose(first, second, alpha))[0]
                         for first, second in zip(original, original[1:])
                         for alpha in (0, 1365, 2730, 4096))
    frames, loop, events = animsheet.slot_frames(model, nb, slot)
    frames = copy.deepcopy(frames)
    offsets = [0.] * len(frames)
    constraints = []
    for i, (first, second) in enumerate(zip(frames, frames[1:])):
        for alpha in (0, 1365, 2730, 4096):
            support, whole = levels(interpolate_pose(first, second, alpha))
            low = max(0., baseline_floor+.6-support, -7-whole)
            high = 2-whole
            if low > high:
                raise ValueError(('support cannot meet main and the arena floor', i, alpha, low, high))
            weight = alpha/4096
            constraints.append((i, 1-weight, weight, low, high))
    for _ in range(1000):
        violation = 0.
        for i, a, b, low, high in constraints:
            offset = a*offsets[i]+b*offsets[i+1]
            error = min(high, max(low, offset))-offset
            violation = max(violation, abs(error))
            correction = error/(a*a+b*b)
            offsets[i] += correction*a
            offsets[i+1] += correction*b
        if violation < .01:
            break
    if violation > .25:
        raise ValueError(('support between keys cannot meet the floor', violation))
    for pose, offset in zip(frames, offsets):
        pose[1][7] += round(offset)
    model.anims.table[slot] = len(model.anims.anims)
    model.anims.anims.append(mmd.encode_anim(frames, nb, loop, events,
                                            tol={0: 0, 1: 0, None: 1}, repeats=False))
    return _clean(model)
