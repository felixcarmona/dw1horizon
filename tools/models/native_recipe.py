#!/usr/bin/env python3
"""Store reviewed source clearance, or retain a native clip when source motion fails.

One species per invocation. This changes the generator recipe, never generated
models or provider pins. Rebuild and store pins with edit.py put afterwards.
"""
import argparse
import json
from pathlib import Path

MANIFEST = Path(__file__).resolve().parents[2]/'content/models/imports/native-bindings.json'
FITS = MANIFEST.with_name('rig-fits.json')


def keep_donor(recipe, slots):
    restored = recipe['battle_originals']
    slots = set(slots)
    if not slots <= set(restored['slots']):
        raise ValueError('only currently restored slots can be withdrawn')
    restored['slots'] = [s for s in restored['slots'] if s not in slots]
    for key in ('ticks', 'repairs'):
        if key in restored:
            restored[key] = {s: value for s, value in restored[key].items() if int(s) not in slots}
    if 'share' in restored:
        restored['share'] = {s: lead for s, lead in restored['share'].items()
                             if int(s) not in slots and int(lead) not in slots}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('species', type=int)
    p.add_argument('slots', type=lambda s: int(s, 0), nargs='+')
    p.add_argument('--reason', required=True)
    p.add_argument('--clearance', type=Path, help='reviewed final placements by slot; keeps restored source clips')
    args = p.parse_args()
    rows = json.loads(MANIFEST.read_text())
    if args.clearance:
        restored = rows[str(args.species)]['battle_originals']['slots']
        if not set(args.slots) <= set(restored):
            raise ValueError('clearance requires currently restored source slots')
        operations = json.loads(args.clearance.read_text())
        fits = json.loads(FITS.read_text())
        for slot in args.slots:
            fits.setdefault(str(args.species), {})[str(slot)] = operations[str(slot)]
        FITS.write_text(json.dumps(fits, indent=1)+'\n')
        print(f'{args.species}: source clearance stored in {args.slots}: {args.reason}')
        return
    keep_donor(rows[str(args.species)], args.slots)
    MANIFEST.write_text(json.dumps(rows, indent=2)+'\n')
    # These placements were reviewed on the restored source motion. The native
    # fallback already fits its mesh and must not inherit source-only repairs.
    if FITS.exists():
        fits = json.loads(FITS.read_text())
        placements = fits.get(str(args.species), {})
        if any(str(slot) in placements for slot in args.slots):
            for slot in args.slots:
                placements.pop(str(slot), None)
            if not placements:
                fits.pop(str(args.species), None)
            FITS.write_text(json.dumps(fits, indent=1)+'\n')
    print(f'{args.species}: donor clips retained in {args.slots}: {args.reason}')


if __name__ == '__main__':
    main()
