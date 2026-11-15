"""Decoded display blends and planted feet in Deltamon's victory."""
import copy
import math

import animsheet
import mmd
from motiontailspace import interpolate_pose


def audit(data, skeleton):
    nb = len(skeleton)
    mmd.exe().add_type(9494, skeleton)
    model = mmd.MMD.parse(data, nb)
    model.type = 9494
    local = {b: [v[:3] for v in model.tmd.obj_verts(o)]
             for b, (o, _) in enumerate(skeleton) if o >= 0}
    frames = animsheet.slot_frames(model, nb, 42)[0]
    lows = []
    soles = {foot: [] for foot in (23, 26)}
    positions = {foot: [] for foot in soles}
    for tick, pose in enumerate(frames):
        for alpha in ((0, 1365, 2730) if tick + 1 < len(frames) else (0,)):
            p = copy.deepcopy(pose) if not alpha else interpolate_pose(pose, frames[tick + 1], alpha)
            p[0] = [4096] * 3 + [0] * 6
            world = mmd.bone_matrices(model, p)
            lowest = {b: max(sum(world[b][1][j] * v[j] for j in range(3)) + world[b][1][3]
                             for v in vertices) for b, vertices in local.items()}
            lows.append(max(lowest.values()))
            for foot in soles:
                soles[foot].append(lowest[foot])
                positions[foot].append((world[foot][0][3], world[foot][2][3]))
    drift = {foot: max(math.dist(position, rows[0]) for position in rows)
             for foot, rows in positions.items()}
    bands = {foot: [min(rows), max(rows)] for foot, rows in soles.items()}
    passed = (min(lows) >= -8 and max(lows) <= 3
              and all(low >= -8 and high <= 3 for low, high in bands.values())
              and max(drift.values()) <= 3)
    return dict(passed=passed, samples_60fps=len(lows), floor=[min(lows), max(lows)],
                soles=bands, anchor_error_xz=drift)
