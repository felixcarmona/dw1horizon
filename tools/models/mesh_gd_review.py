"""Compare final atlas-stamped pairs for imports 307, 314, 323 and 326.

The native envelope is unchanged. Crossings include hidden/joint contacts;
orthographic PSX-rule images do not establish runtime visual clearance.
"""
import argparse
import copy
import json
from pathlib import Path

from tools.models import mesh_cleanup, mesh_gd, mesh_glitch, mesh_round4, mesh_stability


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--thresholds', type=Path, default=Path('docs/reference/mesh-glitch-audit.json'))
    parser.add_argument('--ids', nargs='+', type=int, choices=mesh_gd.IDS, default=mesh_gd.IDS)
    parser.add_argument('--crossings', action='store_true', help='exhaustive slot/frame CSV ledgers')
    parser.add_argument('--renders', action='store_true', help='matched eight-azimuth PSX-rule sheets')
    args = parser.parse_args()
    thresholds = json.loads(args.thresholds.read_text())['thresholds']
    for sid in args.ids:
        mesh_round4.PART_NAMES.setdefault(sid, {})
        models = []
        for label, folder in (('before', args.before), ('after', args.after)):
            model = mesh_round4.load(folder, sid)
            models.append(model)
            out = args.out/label
            out.mkdir(parents=True, exist_ok=True)
            row = mesh_glitch.measure(model, samples=3)
            row.update(mesh_glitch.classify(row, thresholds))
            row['surface_pairs'] = mesh_glitch.coplanar_details(model)
            row['exact_duplicate_packets'] = mesh_cleanup.duplicate_surfaces(copy.deepcopy(model.m))
            row['bends'] = mesh_stability.bent_quads(model.m)
            (out/f'{sid}-detector.json').write_text(json.dumps(row, indent=2)+'\n')
            if args.crossings:
                mesh_round4.scan(folder, sid, out)
        if args.renders:
            summary = args.out/'before'/f'{sid}.json'
            if args.crossings:
                pairs = json.loads(summary.read_text())['pairs'].values()
            else:
                pairs = json.loads((args.out/'before'/f'{sid}-detector.json').read_text())['part_intersections']
            pairs = sorted(pairs, key=lambda r: -r['depth'])[:3]
            cases = [(s, 0) for s in (0, 2, 3, 4)] + [(p['slot'], p['tick']) for p in pairs]
            mesh_round4.render_evidence(*models, cases, args.out/'renders'/str(sid))


if __name__ == '__main__':
    main()
