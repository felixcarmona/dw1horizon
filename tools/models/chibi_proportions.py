#!/usr/bin/env python3
"""The chibi proportions every species with a row in content/models/imports/chibi.json must keep, in every batch.

A row says how a species is reshaped to Digimon World's anatomy (head, hands and feet grow, legs shorten). The reshape
runs as an overlay, or it is baked into the species' delta, or the species wears a native rig (a native binding): in every
case, a later batch that rebuilds the species' clips or rig can lose it without a single check failing. This tool measures
the proportions of each species' final model (chibi.proportions: head, head width, feet, hands and legs as ratios of its
height) and keeps them in content/models/imports/chibi-proportions.json, the approved values. `check` fails when a species'
final model strays from them; a change that is meant (another strength, another rig) rewrites its pins with `write`.

  tools/models/chibi_proportions.py check [ID ...]   measure and compare (exit status 1 on a stray)
  tools/models/chibi_proportions.py write [ID ...]   measure and store the pins (the reference ratios, no exceptions)
  tools/models/chibi_proportions.py accept ID "why"  keep the measured values of the keys that stray, with the reason

A pin holds the REFERENCE ratios (the species as it was approved, before the animation batches); `accepted` lists the keys
whose current value a deliberate decision changed, and why, so a drift that nobody decided stays visible and fails.

The models come from `tools/models/edit.py get ID` (default folder build/imported-model-edit/edit, or --models DIR): the
species' model before its field overlay, which this tool runs as the build does.
"""
import argparse
import glob
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.models.field_animations import chibi, native_binding  # noqa: E402

PINS = ROOT / 'content/models/imports/chibi-proportions.json'
MODELS = ROOT / 'build/imported-model-edit/edit'
KEYS = ('head', 'head_width', 'foot', 'hand', 'legs')
ABSOLUTE, RELATIVE = 0.03, 0.08       # a ratio may stray by the larger of the two before it counts


def _species_module():
    spec = importlib.util.spec_from_file_location('imported_species', ROOT / 'content/models/imports/species.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def final_model(sid, models):
    """(model bytes, skeleton, {bone: group}) of species `sid` as the build makes it, from the `get` output in `models`."""
    species = _species_module()
    records = species.records()
    files = sorted(Path(models).glob(f'{sid}-*.MMD'))
    if not files:
        raise FileNotFoundError(f'{models}: no {sid}-*.MMD (tools/models/edit.py get {sid})')
    with tempfile.TemporaryDirectory() as folder:
        shutil.copy(files[0], Path(folder) / f'{sid}.MMD')
        shutil.copy(files[0].with_suffix('.TIM'), Path(folder) / f'{sid}.TIM')
        donor = json.loads(native_binding.MANIFEST.read_text()).get(sid, {}).get('donor_species')
        if donor:                                    # a native binding whose donor is an imported species: its model too
            donors = sorted(Path(models).glob(f'{donor}-*.MMD'))
            if not donors:
                raise FileNotFoundError(f'{models}: no {donor}-*.MMD, the donor of {sid} (tools/models/edit.py get {donor})')
            shutil.copy(donors[0], Path(folder) / f'{donor}.MMD')
        species.BASE_MODELS = folder
        record = json.loads(Path(next(glob.iglob(str(ROOT / f'content/species/{sid}-*.json')))).read_text())
        skeleton = record['model']['skeleton']
        data = files[0].read_bytes()
        rows = json.loads(chibi.MANIFEST.read_text())
        groups = {int(b): g for b, g in rows[sid]['groups'].items()}
        if records[sid].get('field_overlay'):
            path, proof = species.overlay(Path(folder) / 'out', sid, records)
            data = Path(path).read_bytes()
            if 'generated_skeleton' in proof:           # a native binding: the donor's rig, the groups follow the map
                skeleton = proof['generated_skeleton']
                recipe = json.loads(native_binding.MANIFEST.read_text())[sid]
                groups = chibi.donor_groups(recipe['map'], groups)
    return data, skeleton, groups


def measure(sid, models):
    data, skeleton, groups = final_model(sid, models)
    return chibi.proportions(data, skeleton, groups, 9000 + int(sid))


def expected(pinned):
    """The values a final model must have: the reference ratios, except the keys a deliberate change accepted."""
    return {k: pinned.get('accepted', {}).get(k, pinned[k]) for k in KEYS}


def strays(sid, measured, pinned):
    want = expected(pinned)
    return {k: (measured[k], want[k]) for k in KEYS
            if abs(measured[k] - want[k]) > max(ABSOLUTE, RELATIVE * want[k])}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=('check', 'write', 'accept'))
    parser.add_argument('ids', nargs='*')
    parser.add_argument('--models', default=str(MODELS))
    args = parser.parse_args()
    rows = json.loads(chibi.MANIFEST.read_text())
    pins = json.loads(PINS.read_text()) if PINS.exists() else {}
    ids = (args.ids[:-1] if args.command == 'accept' else args.ids) or sorted(rows, key=int)
    bad = 0
    for sid in ids:
        measured = measure(sid, args.models)
        if args.command == 'accept':
            off = strays(sid, measured, pins[sid])
            pins[sid]['accepted'] = dict(pins[sid].get('accepted', {}), **{k: measured[k] for k in off}, why=args.ids[-1])
            print(sid, 'accepted', sorted(off))
        elif args.command == 'write':
            pins[sid] = {k: measured[k] for k in KEYS}
            print(sid, pins[sid])
        else:
            off = strays(sid, measured, pins[sid])
            bad += bool(off)
            print(sid, 'STRAYS' if off else 'ok', off or '')
    if args.command in ('write', 'accept'):
        PINS.write_text(json.dumps(dict(sorted(pins.items(), key=lambda item: int(item[0]))), indent=1) + '\n')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
