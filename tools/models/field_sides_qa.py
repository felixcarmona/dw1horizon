#!/usr/bin/env python3
"""Cheap bilateral mid-plane detector, with optional exact mesh confirmation.

Sweep final provider records, never the imported base MMD with its source rig:
  python3 tools/models/field_sides_qa.py BUILD/imported-species --json report.json

Pairs are inferred from reflected idle joint positions and paired ancestry.
This is a candidate detector, not an anatomy classifier: intentional crossed
poses and asymmetric rigs need review. Triangle confirmation excludes mere
AABB overlap; coplanar and contained surfaces remain a limitation.
"""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.models import battle_qa as q


def pairs(rig):
    """(positive-x bone, negative-x bone, shared ancestor) in stable order."""
    idle = q.Clip(rig, *rig.frames(0))
    xyz = idle.Wf[0, :, :3, 3].copy()
    h = max(np.ptp(np.concatenate([v[0] for v in idle.V.values()])[:, 1]), 1)
    # Joint anchors preserve side identity even when the feather itself has
    # already crossed the middle. Centroids help pieces attached at the middle.
    for b in rig.meshed:
        if abs(xyz[b, 0]) < .01 * h:
            xyz[b] = idle.V[b][0].mean(0)
    ancestors = {}
    for b in range(rig.nb):
        chain, p = [], b
        while p >= 0:
            chain.append(p)
            p = rig.parent[p]
        ancestors[b] = chain
    nearest = {}
    for a in rig.meshed:
        reflected = xyz[a] * [-1, 1, 1]
        options = [b for b in rig.meshed if xyz[a, 0] * xyz[b, 0] < 0
                   and min(abs(xyz[a, 0]), abs(xyz[b, 0])) > .01 * h
                   and len(ancestors[a]) == len(ancestors[b])
                   and .4 < len(rig.local[a]) / len(rig.local[b]) < 2.5
                   and (not rig.proportion_groups or
                        rig.proportion_groups.get(a) == rig.proportion_groups.get(b))]
        if options:
            b = min(options, key=lambda b: np.linalg.norm(reflected - xyz[b]))
            if np.linalg.norm(reflected - xyz[b]) < .18 * h:
                nearest[a] = b
    result = []
    def meshed_parent(b):
        p = rig.parent[b]
        while p > 0 and p not in rig.local:
            p = rig.parent[p]
        return p

    for a, b in nearest.items():
        if xyz[a, 0] <= 0 or nearest.get(b) != a:
            continue
        common = next(c for c in ancestors[a] if c in ancestors[b])
        pa, pb = meshed_parent(a), meshed_parent(b)
        if pa == pb or nearest.get(pa) == pb:
            result.append((a, b, common))
    # An outer feather can strike the opposite shoulder without striking its
    # matching feather. Include cross-segment pairs within the paired chains.
    expanded = set(result)
    for a, b, body in result:
        for c, d, _ in result:
            if a in ancestors[c] and b in ancestors[d]:
                expanded.update(((a, d, body), (c, b, body)))
    return sorted(expanded)


def measure(clip, paired=None, triangles=False):
    """Per sample world distances to a moving body mid-plane, in model units.

    The plane passes through the common ancestor; its idle-world +x normal
    follows that ancestor's rotation (including the root). Positive depth is
    a vertex on the wrong side. This handles body sway, lean and root turns.
    """
    rig = clip.rig
    paired = pairs(rig) if paired is None else paired
    idle = q.Clip(rig, *rig.frames(0))
    out = []
    for a, b, body in paired:
        normal0 = np.linalg.solve(idle.Wf[0, body, :3, :3], [1., 0., 0.])
        normal = clip.Wf[:, body, :3, :3] @ normal0
        normal /= np.linalg.norm(normal, axis=1)[:, None]
        origin = clip.Wf[:, body, :3, 3]
        da = np.einsum('fvi,fi->fv', clip.V[a] - origin[:, None], normal)
        db = np.einsum('fvi,fi->fv', clip.V[b] - origin[:, None], normal)
        depth = np.maximum(0, np.maximum(-da.min(1), db.max(1)))
        centroid = np.maximum(0, np.maximum(-da.mean(1), db.mean(1)))
        row = dict(bones=[a, b], body=body, depth=depth.tolist(), centroid=centroid.tolist(),
                   max_depth=float(depth.max()), max_centroid=float(centroid.max()))
        if triangles:
            from tools.models.field_animations import meshclash
            counts = []
            for f in range(clip.n):
                A, B = clip.V[a][f], clip.V[b][f]
                if (A.min(0) > B.max(0)).any() or (B.min(0) > A.max(0)).any():
                    counts.append(0)
                else:
                    counts.append(int(meshclash.crossing(A[rig.tris[a]], B[rig.tris[b]], depth=False)[0]))
            row['triangles'] = counts
        out.append(row)
    return out


def samples(rig, slot, subframes=3):
    from motiontailspace import interpolate_pose
    frames, loop = rig.frames(slot)
    poses = [interpolate_pose(a, b, k * 4096 // subframes)
             for a, b in zip(frames, frames[1:]) for k in range(subframes)] + [frames[-1].tolist()]
    return q.Clip(rig, np.array(poses, float), loop)


def candidate(row, height):
    """A deep wrong-side vertex and an intersection at the same sample,
    or a centroid that has completely exchanged sides (even without contact)."""
    threshold = .025 * height
    return bool(np.any((np.array(row['depth']) > threshold) & (np.array(row['triangles']) > 0)) or
                row['max_centroid'] > threshold)


def sweep(directory, subframes=3):
    rows = []
    for path in sorted(Path(directory).glob('*.json')):
        record = json.loads(path.read_text())
        if 'model' not in record or 'skeleton' not in record['model']:
            continue
        model = Path(record['model']['file'])
        rig = q.Rig.from_mmd(model.read_bytes(), record['model']['skeleton'], path.name.split('-')[0])
        paired = pairs(rig)
        h = max(np.ptp(np.concatenate([v[0] for v in q.Clip(rig, *rig.frames(0)).V.values()])[:, 1]), 1)
        slots = {}
        for slot in range(5):
            if rig.frames(slot) is None:
                slots[slot] = dict(missing=True)
                continue
            clip = samples(rig, slot, subframes)
            measured = measure(clip, paired, triangles=True)
            for row in measured:
                # Ignore tiny attachment seams. Keep actual intersections and
                # separated pieces that have completely exchanged sides.
                row['candidate'] = candidate(row, h)
            slots[slot] = measured
        rows.append(dict(species=path.stem, height=h, pairs=paired, slots=slots))
    return dict(subframes=subframes, species=len(rows), rows=rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('records', type=Path)
    p.add_argument('--json', type=Path, required=True)
    p.add_argument('--subframes', type=int, choices=(1, 3), default=3)
    args = p.parse_args()
    report = sweep(args.records, args.subframes)
    args.json.write_text(json.dumps(report, indent=2) + '\n')
    for row in report['rows']:
        flagged = {s: [r['bones'] for r in rs if r['candidate']] for s, rs in row['slots'].items() if isinstance(rs, list)}
        if any(flagged.values()):
            print(row['species'], {s: v for s, v in flagged.items() if v})
    print(f"Checked {report['species']} species; full per-sample measurements: {args.json}")


if __name__ == '__main__':
    main()
