#!/usr/bin/env python3
"""Author Gallantmon's backward collapse and recovery, with trailing cloth and plume.

Input is the accepted model from tools/models/edit.py get 318. The three cape
panels, helmet plume and shield settle independently after the body falls.
The player build replays the resulting plain model delta.
"""
import argparse
import hashlib
import copy
import math
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import mmd
import animsheet
import motionstorage
from motiontailspace import interpolate_pose
from motiondiscidentity import changed_programs


SOURCE_SHA256 = "06a81382dbd91563cc26db6d8be8737752ed77345595aed17fca0784e0567025"


def repair(data):
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        raise ValueError("Gallantmon fall requires the reviewed source")
    old = mmd.MMD.parse(data, 28)
    old.type = 318
    rest = animsheet.slot_frames(old, 28, 0)[0][0]
    sk = mmd.exe().skeleton[318]

    def floor(p):
        """Lowest mesh point; y grows downward and the floor is zero."""
        w = mmd.bone_matrices(old, p)
        return max((sum((w[b][1][k] * v[k] for k in range(3))) + w[b][1][3] for b, (o, _) in enumerate(sk) if o >= 0 for v in old.tmd.obj_verts(o)))

    def pose(lean, knee, arm, hip, roll=0):
        """A grounded key: body lean, folded knees, weapon arm and hip pitch in degrees."""
        p = copy.deepcopy(rest)
        p[0][6:9] = [0, 0, 0]
        p[1][3] = round(lean * 4096 / 360)
        p[1][5] = round(roll * 4096 / 360)
        for b in (20, 24):
            p[b][3] = round(hip * 4096 / 360)
        for b in (21, 25):
            p[b][3] = round(knee * 4096 / 360)
        for b in (22, 26):
            p[b][3] = round(-knee * 0.45 * 4096 / 360)
        for b in (23, 27):
            p[b][3] = 0
        p[2][3] = rest[2][3] + round(arm * 0.05 * 4096 / 360)
        p[12][3] = rest[12][3] + round(arm * 1.5 * 4096 / 360)
        p[3][3] = rest[3][3] + round(12 * math.sin(arm * math.pi / 180) * 4096 / 360)
        # Keep the cape trailing behind the shoulders throughout the fall.
        for b, target in ((16, 58), (17, -8), (18, 5)):
            blend = max(0, min(1, (-lean - 5) / 65))
            target = target - lean if b == 16 else target
            p[b][3] = round(rest[b][3] * (1 - blend) + target * 4096 / 360 * blend)
        from tools.models.field_animations import quadruped as q
        blend = max(0, min(1, (-lean - 10) / 55))
        # Lay the plume along the floor so its tip cannot prop up the body.
        for parent, child in ((7, 8), (8, 9), (9, 10), (10, 11)):
            w = mmd.bone_matrices(old, p)
            carrier = sk[parent][1]
            target = q.rot([math.degrees(math.atan2(p[child][7], p[child][8])), 0, 0])
            rotation = q.mul(q.tr([r[:3] for r in w[carrier][:3]]), target)
            angles = mmd.matrix_euler(rotation, p[parent][3:6])
            p[parent][3:6] = [round(a * (1 - blend) + b * blend) for a, b in zip(p[parent][3:6], angles)]
        w = mmd.bone_matrices(old, p)
        rw = mmd.bone_matrices(old, rest)
        # Roll the shield onto its broad face beside the fallen arm.
        desired = q.mul(q.rot([0, 0, 80]), [r[:3] for r in rw[4][:3]])
        local = q.mul(q.tr([r[:3] for r in w[3][:3]]), desired)
        angles = mmd.matrix_euler(local, p[4][3:6])
        p[4][3:6] = [round(a * (1 - blend) + b * blend) for a, b in zip(p[4][3:6], angles)]
        p[1][7] = 0
        p[1][7] = round(-floor(p) - 2)
        return p
    # Anticipation, loss of balance, impact, recoil, then settle.
    keys = [(0, copy.deepcopy(rest)), (7, pose(15, 105, -8, -68, 2)), (14, pose(-12, 115, 8, -65, -3)), (23, pose(-65, 65, 38, -28, -5)), (29, pose(-88, 22, 55, -12, -4)), (32, pose(-80, 32, 49, -15, -4)), (36, pose(-84, 25, 52, -13, -4))]
    fall = []
    for t in range(37):
        a, b = next(((a, b) for a, b in zip(keys, keys[1:]) if a[0] <= t <= b[0]), (keys[-2], keys[-1]))
        u = (t - a[0]) / (b[0] - a[0])
        u = u * u * (3 - 2 * u)
        p = interpolate_pose(a[1], b[1], round(u * 4096))
        # Cloth and plume recoil after the body; distal pieces follow later.
        if t > 14:
            for bone, lag, amp in ((17, 2, 7), (18, 4, 10), (8, 2, 4), (9, 3, 6), (10, 4, 8), (11, 5, 10)):
                p[bone][3] += round(math.sin(max(0, t - 23 - lag) * 0.5) * math.exp(-max(0, t - 26) / 6) * amp * 4096 / 360)
        p[1][7] -= math.ceil(max(0, floor(p) + 2))
        fall.append(p)
    # Roll to a crouch, push up, and settle into the imported idle.
    getkeys = [(0, copy.deepcopy(fall[-1])), (7, pose(-53, 74, 32, -40, -7)), (16, pose(22, 125, -5, -80, -2)), (24, pose(8, 94, -3, -60, 1)), (30, copy.deepcopy(rest))]
    up = []
    for t in range(31):
        a, b = next(((a, b) for a, b in zip(getkeys, getkeys[1:]) if a[0] <= t <= b[0]))
        u = (t - a[0]) / (b[0] - a[0])
        u = u * u * (3 - 2 * u)
        p = interpolate_pose(a[1], b[1], round(u * 4096))
        p[1][7] -= math.ceil(max(0, floor(p) + 2))
        up.append(p)
    new = copy.deepcopy(old)
    for slot, poses in ((43, fall), (44, up)):
        _, loop, events = animsheet.slot_frames(old, 28, slot)
        new.anims.anims[old.anims.table[slot]] = mmd.encode_anim(poses, 28, loop_sample=None, events=events, tol=1, repeats=False)
    result = new.build()
    actual = mmd.MMD.parse(result, 28)
    actual.type = 318
    assert actual.tmd.build() == old.tmd.build()
    assert changed_programs(old, actual) == [21, 43, 44]
    decoded = {slot: animsheet.slot_frames(actual, 28, slot)[0] for slot in (43, 44)}
    assert decoded[43][-1][1:] == decoded[44][0][1:]
    for slot in (43, 44):
        before, loop, events = animsheet.slot_frames(old, 28, slot)
        after, new_loop, new_events = animsheet.slot_frames(actual, 28, slot)
        assert (len(before), loop, events) == (len(after), new_loop, new_events)
    floor_checks = {}
    for slot, frames in decoded.items():
        lowest = max(floor(interpolate_pose(a, b, alpha))
                     for a, b in zip(frames, frames[1:]) for alpha in (0, 1365, 2730))
        assert lowest <= 3, (slot, lowest)
        floor_checks[slot] = round(lowest, 2)
    return result, dict(changed_slots=[21, 43, 44], mesh_exact=True,
                        faint_recovery_join_exact=True, events_duration_exact=True,
                        floor_60fps=floor_checks, storage=motionstorage.require(result, 28))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result, report = repair(args.source.read_bytes())
    args.output.write_bytes(result)
    args.output.with_suffix('.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
