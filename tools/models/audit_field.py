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

# Absolute clearance, not clearance relative to this model's idle (which hides
# a high hover). Native AIRD/BIRD/HOEE/VEDA/POYO/BAKE pass these field limits;
# Birdramon's run reaches 250.2 and Bakemon's idle 190.7 units.
HOVER_LIMITS = {0: 200, 1: 200, 2: 160, 3: 160, 4: 260, 18: 200}
FIELD_SLOTS = (0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19)


def hover_heights(rig, slot):
    """Every engine tick: lowest mesh point and top above floor zero, Y down.

    Root translation accumulates on the entity; retain its Y in world heights,
    but do not use a species' self-normalized idle floor as the ground plane.
    """
    import numeric as np
    from tools.models.battle_qa import Clip
    clip = Clip(rig, *rig.frames(slot))
    lowest = -np.stack([v[:, :, 1].max(1) for v in clip.V.values()]).max(0) - clip.root[:, 1]
    highest = -np.stack([v[:, :, 1].min(1) for v in clip.V.values()]).min(0) - clip.root[:, 1]
    samples = [[round(float(a), 2), round(float(b), 2)] for a, b in zip(lowest, highest)]
    limit = HOVER_LIMITS.get(slot)
    return dict(lowest_min=round(float(lowest.min()), 2), lowest_peak=round(float(lowest.max()), 2),
                mesh_peak=round(float(highest.max()), 2), frames=samples,
                hover_limit=limit, high_hover=limit is not None and float(lowest.max()) > limit)


def hover_audit(out, native_from=None, ids=None):
    """Sweep every imported partner, including grounded winged species and non-air floaters."""
    from tools.models.battle_qa import Rig
    records = [json.loads(p.read_text()) for p in sorted((ROOT / 'content/species').glob('*.json'))]
    rows, errors = [], []
    for record in records:
        if record['id'] < 180 or 'partner' not in record:
            continue
        if ids is not None and record['id'] not in ids:
            continue
        try:
            model, sk, path = load(out, record)
            rig = Rig.from_mmd(path.read_bytes(), sk, record['id'])
            rows.append(dict(id=record['id'], name=record['name'], air='air' in record.get('specialties', []),
                             path=str(path), clips={str(s): hover_heights(rig, s) for s in FIELD_SLOTS
                                                   if rig.frames(s) is not None}))
        except Exception as exc:
            errors.append(dict(id=record['id'], error=str(exc)))
    natives = []
    if native_from:
        for sid in (7, 21, 24, 25, 28, 29, 37):
            try:
                sk = mmd.exe().skeleton[sid]
                path, = native_from.glob(f'CHDAT/MMD*/{mmd.exe().names[sid]}.MMD')
                rig = Rig.from_mmd(path.read_bytes(), sk, sid)
                natives.append(dict(id=sid, name=mmd.exe().names[sid],
                                    clips={str(s): hover_heights(rig, s) for s in FIELD_SLOTS
                                           if rig.frames(s) is not None}))
            except Exception as exc:
                errors.append(dict(id=sid, error=str(exc)))
    return dict(species=rows, natives=natives, errors=errors,
                high_hover=[dict(id=r['id'], name=r['name'], slots=[s for s, c in r['clips'].items()
                                                               if c['high_hover']])
                            for r in rows if any(c['high_hover'] for c in r['clips'].values())])


def load(out, record):
    """Load the effective model, including a recipe's generated skeleton."""
    sid = record['id']
    final_record = None
    for catalogue in ('species', 'imported-species'):
        records = sorted((out / catalogue).glob(f'{sid}-*.json'))
        if len(records) == 1:
            final_record = json.loads(records[0].read_text())
            break
    paths = sorted((out / 'imported-species-models').glob(f'{sid}-*.MMD'))
    selected = (final_record or {}).get('model', {}).get('file')
    if selected:
        path = Path(selected)
        if not path.is_absolute():
            path = ROOT / path
    elif len(paths) > 1:
        raise ValueError(f'{sid}: ambiguous final overlays: {[p.name for p in paths]}')
    else:
        path = paths[0] if paths else out / 'imported-models' / f'{sid}.MMD'
    if not path.exists():
        path = out / 'record-originals' / f'{sid}.MMD'
    sk = record['model']['skeleton']
    # Final care/rig reports need not repeat a native binding's generated rig.
    # The emitted species catalogue does carry that effective skeleton.
    if final_record:
        sk = final_record['model']['skeleton']
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
    parser.add_argument('--hover', action='store_true', help='absolute floor clearance of ALL field/care slots; no voice audit')
    parser.add_argument('--native-from', type=Path, help='extracted native disc for hover calibration')
    parser.add_argument('--ids', nargs='+', type=int, help='scope a hover check to changed species (default: all imports)')
    args = parser.parse_args()
    result = hover_audit(args.source, args.native_from, args.ids) if args.hover else audit(args.source)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(f'{len(result["species"])} species; {len(result["errors"])} errors')
    return bool(result['errors'] or result.get('high_hover'))


if __name__ == '__main__':
    raise SystemExit(main())
