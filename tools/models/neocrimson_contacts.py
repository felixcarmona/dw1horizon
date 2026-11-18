"""Decoded 60 fps support for NeoCrimson's one-footed victory gesture."""
import copy
import math

import animsheet
import mmd
from motiontailspace import interpolate_pose


def audit(data, skeleton):
    nb = len(skeleton)
    mmd.exe().add_type(9492, skeleton)
    model = mmd.MMD.parse(data, nb)
    model.type = 9492
    local = {b: [v[:3] for v in model.tmd.obj_verts(o)]
             for b, (o, _) in enumerate(skeleton) if o >= 0}
    frames = animsheet.slot_frames(model, nb, 42)[0]
    lows, soles, positions = [], [], []
    for tick, pose in enumerate(frames):
        for alpha in ((0, 1365, 2730) if tick + 1 < len(frames) else (0,)):
            p = copy.deepcopy(pose) if not alpha else interpolate_pose(pose, frames[tick + 1], alpha)
            p[0] = [4096] * 3 + [0] * 6
            world = mmd.bone_matrices(model, p)
            lowest = {b: max(sum(world[b][1][j] * v[j] for j in range(3)) + world[b][1][3]
                             for v in vertices) for b, vertices in local.items()}
            lows.append(max(lowest.values()))
            soles.append(lowest[15])
            positions.append((world[15][0][3], world[15][2][3]))
    anchor = positions[0]
    drift = max(math.hypot(x - anchor[0], z - anchor[1]) for x, z in positions)
    passed = min(lows) >= -8 and max(lows) <= 3 and min(soles) >= -8 and max(soles) <= 3 and drift <= 3
    return dict(passed=passed, samples_60fps=len(lows), floor=[min(lows), max(lows)],
                supporting_sole=[min(soles), max(soles)], anchor_error_xz=drift)
