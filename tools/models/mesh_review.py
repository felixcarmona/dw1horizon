#!/usr/bin/env python3
"""Locate mesh-audit candidates and render matched PSX-rule evidence.

python3 -m tools.models.mesh_review BEFORE AFTER IDS... --out build/review
Orthographic, neutral lighting; not a GTE or on-device visibility proof.
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
from tools.models import meshcheck as MC, mesh_glitch, psx_blend
from tools.models.field_animations import meshclash


def hotspots(model, samples=3):
    """Attribute sampled crossings, including parent/child pairs QA omits.

    Depth is reported alongside count to expose joint contact and distinguish
    it from a part reaching far through another. No new pass/fail threshold.
    """
    worst = {}
    for slot in (0, 2, 3, 4, 33, 34, 35, 36):
        if slot not in model.slots():
            continue
        poses = model.poses(slot, 6000)
        if len(poses) >= 6000:
            raise ValueError(f'slot {slot}: decode guard reached')
        ticks = np.unique(np.linspace(0, len(poses)-1, min(samples, len(poses)), dtype=int))
        for tick in ticks:
            W = model.world(poses[tick])
            tri = {b: np.array([W[b][list(t[3])] for t in model.tris if t[0] == b])
                   for b in model.local}
            tri = {b: t for b, t in tri.items() if len(t)}
            box = {b: (t.min((0, 1)), t.max((0, 1))) for b, t in tri.items()}
            for a in tri:
                for b in tri:
                    if b <= a or (box[a][0] > box[b][1]).any() or (box[b][0] > box[a][1]).any():
                        continue
                    count, depth = meshclash.crossing(tri[a], tri[b])
                    key = (a, b)
                    if count and (depth, count) > (worst.get(key, {}).get('depth', -1), worst.get(key, {}).get('count', -1)):
                        worst[key] = dict(bones=[a, b], count=count, depth=depth, slot=slot, tick=int(tick),
                            adjacent=model.bones[a][1] == b or model.bones[b][1] == a)
    return sorted(worst.values(), key=lambda r: (-r['depth'], -r['count']))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('before', type=Path); p.add_argument('after', type=Path)
    p.add_argument('ids', nargs='+'); p.add_argument('--out', type=Path, required=True)
    args = p.parse_args(); args.out.mkdir(parents=True, exist_ok=True)
    idx = json.loads((args.before/'index.json').read_text())
    report = {}
    for sid in args.ids:
        models = [MC.Model((folder/f'{sid}.MMD').read_bytes(), idx[sid]['bones'],
                          (folder/f'{sid}.TIM').read_bytes()) for folder in (args.before, args.after)]
        details = [dict(coplanar=mesh_glitch.coplanar_details(m), crossings=hotspots(m)) for m in models]
        report[sid] = dict(name=idx[sid]['name'], before=details[0], after=details[1])
        (args.out/'review.json').write_text(json.dumps(report, indent=2)+'\n')
        cases = [(0, 0)]
        # Show the deepest non-adjacent candidate plus the repaired run case.
        for row in details[0]['crossings']:
            if not row['adjacent']:
                cases.append((row['slot'], row['tick'])); break
        if sid == '407':
            cases.append((4, 8))
        images = []
        for slot, tick in dict.fromkeys(cases):
            for yaw in np.arange(8)*math.pi/4:
                poses = [m.poses(slot, 6000) for m in models]
                before, frame = psx_blend.render(models[0], yaw, math.pi/6, size=192, pose=poses[0][tick])
                after, _ = psx_blend.render(models[1], yaw, math.pi/6, size=192, pose=poses[1][tick], frame=frame)
                images.append(np.concatenate([before, after], axis=1))
        MC.png(str(args.out/f'{sid}.png'), np.concatenate(images, axis=0))
        print(sid, idx[sid]['name'], 'cofacing', details[0]['coplanar']['cofacing_pairs'],
              '->', details[1]['coplanar']['cofacing_pairs'], flush=True)
    (args.out/'review.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
