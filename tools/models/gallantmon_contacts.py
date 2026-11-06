#!/usr/bin/env python3
"""Check decoded landing support, boot anchors and nonadjacent cape crossings.

Usage: python3 tools/models/gallantmon_contacts.py MODEL.MMD REPORT.json
Surface tests include the game's two intermediate 60 fps Euler samples. The
collar may share its attachment with the torso; all other body parts are tested.
These constraints supplement the culled motion review, rather than certify it.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet
import mmd
from motiontailspace import interpolate_pose

CAPE = (16, 17, 18)
BODY = (1, 2, 3, 5, 6, 12, 13, 15, 19, 20, 21, 22, 23, 24, 25, 26, 27)
ARMOUR = (1, 5, 15, 19)


def sub(a, b):
    return [x-y for x, y in zip(a, b)]


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def pierces(a, b, triangle):
    """Strict segment/triangle crossing; shared edges and coplanar contact pass."""
    c, d, e = triangle
    direction, first, second = sub(b, a), sub(d, c), sub(e, c)
    normal = cross(direction, second)
    determinant = dot(first, normal)
    if abs(determinant) < 1e-7:
        return False
    offset = sub(a, c)
    u = dot(offset, normal) / determinant
    if not .001 < u < .999:
        return False
    v = dot(direction, cross(offset, first)) / determinant
    if v <= .001 or u+v >= .999:
        return False
    t = dot(second, cross(offset, first)) / determinant
    return .001 < t < .999


def bounds(points):
    return tuple((min(p[k] for p in points), max(p[k] for p in points)) for k in range(3))


def separate(a, b):
    return any(x[1] < y[0] or y[1] < x[0] for x, y in zip(a, b))


def audit(data):
    model = mmd.MMD.parse(data, 28)
    model.type = 318
    skeleton = mmd.exe().skeleton[318]
    local, faces = {}, {}
    for bone in set(CAPE + BODY):
        obj = skeleton[bone][0]
        local[bone] = [v[:3] for v in model.tmd.obj_verts(obj)]
        faces[bone] = []
        for primitive in model.tmd.objects[obj].prims:
            ids = primitive.decode()['verts']
            faces[bone].append(ids[:3])
            if len(ids) == 4:
                faces[bone].append([ids[1], ids[3], ids[2]])

    def geometry(pose):
        matrices = mmd.bone_matrices(model, pose)
        points = {b: [[sum(matrices[b][i][k]*v[k] for k in range(3))+matrices[b][i][3]
                       for i in range(3)] for v in vertices] for b, vertices in local.items()}
        return matrices, points

    frames = {s: animsheet.slot_frames(model, 28, s)[0] for s in (43, 44)}
    support = {}
    for tick in (30, 32, 36):
        _, points = geometry(frames[43][tick])
        support[tick] = max(v[1] for b in ARMOUR for v in points[b])
    crossings, samples = [], 0
    for slot, poses in frames.items():
        for tick in range(len(poses)):
            alphas = (0, 1365, 2730) if tick+1 < len(poses) else (0,)
            for alpha in alphas:
                p = poses[tick] if not alpha else interpolate_pose(poses[tick], poses[tick+1], alpha)
                _, points = geometry(p)
                boxes = {b: bounds(v) for b, v in points.items()}
                triangles = {b: [tuple(points[b][i] for i in face) for face in faces[b]] for b in points}
                samples += 1
                for cape in CAPE:
                    for body in BODY:
                        if (cape == 16 and body == 1) or separate(boxes[cape], boxes[body]):
                            continue
                        found = False
                        for a in triangles[cape]:
                            box = bounds(a)
                            for b in triangles[body]:
                                if separate(box, bounds(b)):
                                    continue
                                if any(pierces(a[i], a[(i+1)%3], b) or pierces(b[i], b[(i+1)%3], a)
                                       for i in range(3)):
                                    crossings.append(dict(slot=slot, tick=tick, alpha=alpha, cape=cape, body=body))
                                    found = True
                                    break
                            if found:
                                break
    rest = animsheet.slot_frames(model, 28, 0)[0][0]
    reference = mmd.bone_matrices(model, rest)
    anchors = {}
    for slot, window in ((43, range(16)), (44, range(17, 31))):
        anchors[slot] = max(math.hypot(matrices[b][0][3]-reference[b][0][3],
                                      matrices[b][2][3]-reference[b][2][3])
                            for t in window for matrices in [mmd.bone_matrices(model, frames[slot][t])]
                            for b in (22, 26))
    report = dict(input_sha256=hashlib.sha256(data).hexdigest(), samples_60fps=samples,
                  armour_support_y=support, boot_anchor_error_xz=anchors, cape_crossings=crossings)
    report['passed'] = (not crossings and min(support.values()) >= -8 and
                        max(support.values()) <= 3 and max(anchors.values()) <= 3)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model', type=Path)
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    result = audit(args.model.read_bytes())
    args.report.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
