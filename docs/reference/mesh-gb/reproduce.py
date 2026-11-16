"""Reproduce the scoped detector, exhaustive crossing and PSX render evidence."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.models import mesh_glitch as G, mesh_round4 as R


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--ledgers', action='store_true')
    parser.add_argument('--renders', action='store_true')
    args = parser.parse_args()
    reference = json.loads(Path(__file__).with_name('audit.json').read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    for sid in (220, 236, 238, 270):
        models = [R.load(folder, sid) for folder in (args.before, args.after)]
        for phase, folder, model in zip(('before', 'after'), (args.before, args.after), models):
            row = G.measure(model, samples=3)
            row.update(G.classify(row, reference['thresholds']))
            row['surface_pairs'] = G.coplanar_details(model)
            (args.out / f'{sid}-{phase}.json').write_text(json.dumps(row, indent=2)+'\n')
            if args.ledgers:
                # Preserve exact object IDs for parts lacking reviewed names.
                R.PART_NAMES.setdefault(sid, {})
                R.scan(folder, sid, args.out / f'ledger-{phase}')
        if args.renders:
            cases = list(dict.fromkeys((r['slot'], r['tick']) for r in
                reference['species'][str(sid)]['renders']['rows']))
            R.render_evidence(*models, cases, args.out / 'renders' / str(sid))


if __name__ == '__main__':
    main()
