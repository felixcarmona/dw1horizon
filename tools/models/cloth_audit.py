"""Conservative rear clearance of a cape from the legs (model faces -z).

Crossings use field_animations.meshclash, also used by mesh_glitch/battle_qa.
This additional bound ignores x, so positive clearance guarantees separation
across the complete width, including the interiors of the triangles.
"""
import numpy as np


def rear_clearance(cape, legs):
    """Smallest cape z minus leg z over their common y interval, in game units.

    At each height the edges vary linearly. The minimum of the lower cape
    envelope minus upper leg envelope occurs at a vertex height of one mesh.
    Negative values are conservative overlap candidates, not penetration depth.
    """
    a, b = cape.reshape(-1, 3), legs.reshape(-1, 3)
    low, high = max(a[:, 1].min(), b[:, 1].min()), min(a[:, 1].max(), b[:, 1].max())
    if low > high:
        return float('inf')

    def section(tris, height):
        zs = []
        for k in range(3):
            p, q = tris[:, k], tris[:, (k + 1) % 3]
            d = q[:, 1] - p[:, 1]
            valid = ((abs(d) > 1e-8) & (height >= np.minimum(p[:, 1], q[:, 1]) - 1e-6)
                     & (height <= np.maximum(p[:, 1], q[:, 1]) + 1e-6))
            zs.extend(p[valid, 2] + (height - p[valid, 1]) / d[valid] * (q[valid, 2] - p[valid, 2]))
            flat = (abs(d) <= 1e-8) & (abs(height - p[:, 1]) < 1e-6)
            zs.extend(p[flat, 2])
            zs.extend(q[flat, 2])
        return zs

    gaps = []
    for height in np.unique(np.clip(np.r_[a[:, 1], b[:, 1]], low, high)):
        az, bz = section(cape, height), section(legs, height)
        if az and bz:
            gaps.append(min(az) - max(bz))
    return min(gaps, default=float('inf'))


def measure(data, skeleton, cape, feet, legs, slots=range(5)):
    """Every decoded tick, using the shared mesh-glitch triangle detector."""
    from tools.models.meshcheck import Model
    from tools.models.field_animations.meshclash import crossing
    model = Model(data, skeleton)
    bones = np.array([t[0] for t in model.tris])
    clips = {}
    for slot in slots:
        rows = []
        for tick, pose in enumerate(model.poses(slot)):
            pose[0] = [4096] * 3 + [0] * 6
            triangles = model.tri_array(model.world(pose))
            cloth = triangles[np.isin(bones, cape)]
            foot = triangles[np.isin(bones, feet)]
            leg = triangles[np.isin(bones, legs)]
            foot_pairs, foot_depth = crossing(foot, cloth)
            leg_pairs, leg_depth = crossing(leg, cloth)
            rows.append(dict(tick=tick, foot_pairs=foot_pairs, foot_depth=foot_depth,
                             leg_pairs=leg_pairs, leg_depth=leg_depth,
                             rear_clearance=rear_clearance(cloth, leg)))
        clips[slot] = rows
    return clips


def main():
    import argparse
    import hashlib
    import json
    from pathlib import Path
    from tools.models import edit
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--species', type=int, required=True)
    p.add_argument('--model', type=Path, required=True)
    p.add_argument('--cape', type=int, nargs='+', required=True)
    p.add_argument('--feet', type=int, nargs='+', required=True)
    p.add_argument('--legs', type=int, nargs='+', required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    record = json.loads(next((edit.ROOT / 'content/species').glob(f'{a.species}-*.json')).read_text())
    data = a.model.read_bytes()
    result = dict(sha256=hashlib.sha256(data).hexdigest(),
                  clips=measure(data, record['model']['skeleton'], a.cape, a.feet, a.legs))
    a.out.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
