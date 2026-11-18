"""Decoded 60 fps floor, landing and recovery support for authored battle finishes."""
import argparse
import json
from pathlib import Path
import sys
import copy
import math

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]

import animsheet
import mmd
from motiontailspace import interpolate_pose


def audit(data, skeleton, sid):
    nb = len(skeleton)
    # The provider's generated rig, including its merged rigid mesh objects.
    mmd.exe().add_type(9490 + sid, skeleton)
    model = mmd.MMD.parse(data, nb)
    model.type = 9490 + sid
    local = {b: [v[:3] for v in model.tmd.obj_verts(o)]
             for b, (o, _) in enumerate(skeleton) if o >= 0}

    def geometry(pose):
        pose = copy.deepcopy(pose)
        pose[0] = [4096] * 3 + [0] * 6
        world = mmd.bone_matrices(model, pose)
        lowest = {b: max(sum(world[b][1][k] * v[k] for k in range(3)) + world[b][1][3]
                         for v in vertices) for b, vertices in local.items()}
        return world, lowest

    slots = (43, 44) if sid == 260 else (43,)
    floor, samples, decoded = {}, 0, {}
    for slot in slots:
        frames = animsheet.slot_frames(model, nb, slot)[0]
        decoded[slot] = frames
        lows = []
        for tick, pose in enumerate(frames):
            for alpha in ((0, 1365, 2730) if tick + 1 < len(frames) else (0,)):
                p = pose if not alpha else interpolate_pose(pose, frames[tick + 1], alpha)
                _, lowest = geometry(p)
                lows.append(max(lowest.values()))
                samples += 1
        floor[slot] = dict(lowest_y_min=min(lows), lowest_y_max=max(lows))
    body = (2, 3, 4) if sid == 260 else (10,)
    faint = decoded[43]
    landing = [max(geometry(pose)[1][b] for b in body) for pose in faint[-5:]]
    feet = {}
    if 44 in decoded:
        up = decoded[44]
        reference, _ = geometry(up[-1])
        supports = [geometry(pose) for pose in up[math.ceil((len(up) - 1) * .8):]]
        feet = dict(anchor_error_xz=max(math.hypot(world[b][0][3] - reference[b][0][3],
                                                 world[b][2][3] - reference[b][2][3])
                                       for world, _ in supports for b in (23, 26)),
                    sole_y_min=min(lowest[b] for _, lowest in supports for b in (23, 26)),
                    sole_y_max=max(lowest[b] for _, lowest in supports for b in (23, 26)),
                    join_exact=decoded[43][-1] == up[0])
    passed = (all(-8 <= row['lowest_y_min'] and row['lowest_y_max'] <= 3 for row in floor.values())
              and min(landing) >= -8 and max(landing) <= 3
              and (not feet or (feet['anchor_error_xz'] <= 3 and feet['sole_y_min'] >= -8
                                and feet['sole_y_max'] <= 3 and feet['join_exact'])))
    return dict(passed=passed, samples_60fps=samples, floor=floor,
                landing_support_y=landing, feet=feet)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model', type=Path)
    parser.add_argument('species', type=Path)
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    sid = int(args.species.name.split('-')[0])
    skeleton = json.loads(args.species.read_text())['model']['skeleton']
    report = audit(args.model.read_bytes(), skeleton, sid)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
