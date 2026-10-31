#!/usr/bin/env python3
"""Measure final imported field clips and voice coverage, using overlay skeletons."""
import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT)]
import animsheet
import mmd
import species


def load(out, record):
    """Load the effective model, including a recipe's generated skeleton."""
    sid = record['id']
    paths = sorted((out / 'imported-species-models').glob(f'{sid}-*.MMD'))
    if len(paths) > 1:
        raise ValueError(f'{sid}: ambiguous final overlays: {[p.name for p in paths]}')
    path = paths[0] if paths else out / 'imported-models' / f'{sid}.MMD'
    if not path.exists():
        path = out / 'record-originals' / f'{sid}.MMD'
    sk = record['model']['skeleton']
    report = path.with_name(path.stem + '-report.json')
    if report.exists():
        sk = json.loads(report.read_text()).get('generated_skeleton', sk)
    model = mmd.MMD.parse(path.read_bytes(), len(sk))
    model.type = sid
    mmd.exe().skeleton[sid] = sk
    mmd.exe().bone_count[sid] = len(sk)
    return model, sk, path


def measure(model, nb, slot):
    frames, loop, events = animsheet.slot_frames(model, nb, slot)
    duration = len(frames) - 1
    travel = math.dist(frames[0][0][6:9], frames[-1][0][6:9])
    return dict(ticks=duration, units_per_tick=travel / duration if duration else 0,
                loop_sample=loop, events=len(events))


def audit(out):
    rows, errors = [], []
    for path in sorted((ROOT / 'content/species').glob('*.json')):
        record = json.loads(path.read_text())
        if 'partner' not in record or record['id'] < 180:
            continue
        try:
            model, sk, _ = load(out, record)
            keys = species.vball_keys(record['voice'])
            if keys is None:
                raise ValueError('voice coverage requires extracted VBALL')
            notes = {i['note'] for ai in set(model.anims.table) - {None}
                     for i in model.anims.anims[ai].instrs if i['op'] == 'sound' and i['bank'] == 4}
            rows.append(dict(id=record['id'], name=record['name'], bones=len(sk),
                             voice=record['voice'], partner_voice=record['partner']['voice'],
                             voice_notes=sorted(notes), missing_voice_notes=sorted(notes - keys),
                             clips={str(s): measure(model, len(sk), s) for s in (2, 3, 4)}))
        except Exception as exc:
            errors.append(dict(id=record['id'], error=str(exc)))
    return dict(species=rows, errors=errors)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from', dest='source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.source)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(f'{len(result["species"])} species; {len(result["errors"])} errors')
    return bool(result['errors'])


if __name__ == '__main__':
    raise SystemExit(main())
