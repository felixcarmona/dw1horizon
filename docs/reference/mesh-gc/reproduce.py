"""Reproduce this four-species review from final atlas-stamped pairs/index.json.

python3 docs/reference/mesh-gc/reproduce.py BEFORE AFTER --out build/gc-review
The input folders must contain the actual final generated skeletons and textures.
"""
import argparse
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet
import motionstorage
from tools.models import mesh_glitch, mesh_round4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    archive = json.loads(Path(__file__).with_name('audit.json').read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    for sid in archive['ids']:
        mesh_round4.PART_NAMES[sid] = {}
        models = [mesh_round4.load(folder, sid) for folder in (args.before, args.after)]
        for stage, folder, model in zip(('before', 'after'), (args.before, args.after), models):
            out = args.out / stage
            out.mkdir(exist_ok=True)
            row = mesh_glitch.measure(model, samples=3)
            row.update(mesh_glitch.classify(row, archive['thresholds']))
            row['surface_pairs'] = mesh_glitch.coplanar_details(model)
            (out / f'{sid}-detector.json').write_text(json.dumps(row, indent=2) + '\n')
            mesh_round4.scan(folder, sid, out)
            storage = motionstorage.audit((folder / f'{sid}.MMD').read_bytes(),
                                          len(model.bones), resident_limit=100256)
            assert storage['fits'], (sid, stage, storage)
            (out / f'{sid}-storage.json').write_text(json.dumps(storage, indent=2) + '\n')
        a, b = models
        assert a.bones == b.bones and a.slots() == b.slots(), sid
        for slot in a.slots():
            assert animsheet.slot_frames(a.m, len(a.bones), slot, max_ticks=6000) == \
                animsheet.slot_frames(b.m, len(b.bones), slot, max_ticks=6000), (sid, slot)
        cases = [(r['slot'], r['tick']) for r in archive['models'][str(sid)]['renders']['rows']]
        mesh_round4.render_evidence(a, b, cases, args.out / 'renders' / str(sid))
        with gzip.open(Path(__file__).with_name(f'{sid}-certificates.json.gz'), 'rt') as source:
            records = json.load(source)
        for record in records:
            result = mesh_round4.certificate(b, record['bones'], record['slot'], record['tick'],
                                            record['relative_translation_limit'])
            assert result['proven'], sid
        print(sid, 'detector, complete ledger, PSX-rule renders, storage, poses/events/loops and floor verified',
              flush=True)


if __name__ == '__main__':
    main()
