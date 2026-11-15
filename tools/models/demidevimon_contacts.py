"""Display-frame clearance for DemiDevimon's aerial victory."""
import copy

import animsheet
import mmd
from motiontailspace import interpolate_pose


def _levels(data, skeleton):
    nb = len(skeleton)
    mmd.exe().add_type(9495, skeleton)
    model = mmd.MMD.parse(data, nb)
    model.type = 9495
    local = {b: [v[:3] for v in model.tmd.obj_verts(o)]
             for b, (o, _) in enumerate(skeleton) if o >= 0}
    frames = animsheet.slot_frames(model, nb, 42)[0]
    levels = []
    for tick, pose in enumerate(frames):
        for alpha in ((0, 1365, 2730) if tick + 1 < len(frames) else (0,)):
            p = copy.deepcopy(pose) if not alpha else interpolate_pose(pose, frames[tick + 1], alpha)
            p[0] = [4096] * 3 + [0] * 6
            world = mmd.bone_matrices(model, p)
            levels.append(max(sum(world[b][1][j] * v[j] for j in range(3)) + world[b][1][3]
                              for b in local for v in local[b]))
    return levels


def audit(data, skeleton, main):
    levels, baseline = [_levels(model, skeleton) for model in (data, main)]
    # A flyer keeps its hover; it needs no planted sole. Check every display blend
    # against the arena floor and the existing victory's highest excursion.
    passed = max(levels) <= 3 and min(levels) >= min(baseline)
    return dict(passed=passed, samples_60fps=len(levels),
                floor=[min(levels), max(levels)], main_floor=[min(baseline), max(baseline)])
