#!/usr/bin/env python3
"""Check written imports against the target rig used while authoring their clips.

MMD does not store a hierarchy. The species skeleton and the generator's target
context are therefore both required; guessing a rig from the animation bytecode
cannot establish bone order or ancestry. Run with --models IMPORTED_MODELS and
--out DIRECTORY to replay all imports, saving a machine-readable audit and models.
"""
import argparse
import copy
import importlib.util
import importlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet
import mmd
from tools.models.field_animations import native_battle


def compare(written, rest, authored):
    """Compare ordered (object, parent) identities and a common reference tick.

    This is a reference-pose comparison, never a comparison of different clips'
    first frames: those can deliberately start in entirely different poses.
    """
    issues = []
    for family in authored:
        rig, pose = family['skeleton'], family['rest']
        row = dict(slots=family['slots'], bones=[])
        if len(rig) != len(written):
            row['count'] = [len(rig), len(written)]
        for b, (old, new) in enumerate(zip(rig, written)):
            diff = {}
            if old[0] != new[0]:
                diff['object'] = [old[0], new[0]]
            if old[1] != new[1]:
                diff['parent'] = [old[1], new[1]]
            if pose is not None and b and b < min(len(pose), len(rest)):
                for name, a, z in [('scale', 0, 3), ('rotation', 3, 6), ('offset', 6, 9)]:
                    if list(pose[b][a:z]) != list(rest[b][a:z]):
                        diff[name] = [pose[b][a:z], rest[b][a:z]]
            if diff:
                row['bones'].append(dict(bone=b, **diff))
        if row['bones'] or 'count' in row:
            issues.append(row)
    return issues


def audit(data, skeleton, authored):
    model = mmd.MMD.parse(data, len(skeleton))
    occupied = []
    for slot, index in enumerate(model.anims.table):
        if index is None:
            continue
        occupied.append(slot)
        program = model.anims.anims[index]
        if len(program.pose) != len(skeleton) - 1:
            raise ValueError(f'slot {slot}: {len(program.pose)+1} bones, written rig {len(skeleton)}')
        for instruction in program.instrs:
            for group in instruction.get('bones', []):
                if not 0 <= group['bone'] < len(skeleton):
                    raise ValueError(f'slot {slot}: bone {group["bone"]} outside written rig')
    rest = animsheet.slot_frames(model, len(skeleton), 0)[0][0]
    changes = compare(skeleton, rest, authored)
    mismatches = []
    for change in changes:
        row = dict(slots=change['slots'], bones=[])
        if 'count' in change:
            row['count'] = change['count']
        for bone in change['bones']:
            b = bone['bone']
            # Rotations in slot 0 are an animated pose, not a stored mesh bind
            # matrix. Likewise the carrier moves the whole body through space.
            # Preserve those differences for inspection, but do not mistake an
            # arm pump or grounding pass for changed joint lengths.
            difference = {k: v for k, v in bone.items() if k in ('object', 'parent', 'scale')
                          or (k == 'offset' and skeleton[b][1] > 0)}
            if difference:
                row['bones'].append(dict(bone=b, **difference))
        if row['bones'] or 'count' in row:
            mismatches.append(row)
    return dict(occupied=occupied, bones=len(skeleton), mismatches=mismatches,
                reference_pose_changes=changes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--resume', action='store_true', help='reuse completed records in this audit directory')
    parser.add_argument('ids', nargs='*')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location('rig_species', ROOT/'content/models/imports/species.py')
    species = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(species)
    species.BASE_MODELS = str(args.models.resolve())
    records = species.records()
    results = json.loads((args.out/'rig-audit.json').read_text()) if args.resume and (args.out/'rig-audit.json').exists() else {}
    original = native_battle.retarget
    captured = []
    def capture(frames, ctx):
        captured.append(dict(skeleton=copy.deepcopy(ctx['rig']), rest=copy.deepcopy(ctx['rest'])))
        return original(frames, ctx)
    native_battle.retarget = capture
    try:
        for sid in args.ids or sorted(records, key=int):
            if args.resume and sid in results and 'error' not in results[sid]:
                continue
            captured.clear()
            try:
                species.BASE_MODELS = str(args.models.resolve())
                if records[sid].get('builder'):
                    built = args.out/'builder-models'
                    built.mkdir(exist_ok=True)
                    model, texture = importlib.import_module(records[sid]['builder']).build(ROOT/'extracted')
                    (built/f'{sid}.MMD').write_bytes(model)
                    (built/f'{sid}.TIM').write_bytes(texture)
                    species.BASE_MODELS = str(built.resolve())
                _, record = species.species_file(str(args.out/'species'), sid, generate=True)
                data = Path(record['model']['file']).read_bytes()
                skeleton = record['model']['skeleton']
                # Contexts can be reused by many slots and authored finishes. The
                # source-to-target mapping has already happened at this boundary.
                recipes = json.loads((ROOT/'content/models/imports/native-bindings.json').read_text())
                slots = recipes.get(sid, {}).get('battle_originals', {}).get('slots', [])
                families = [dict(c, slots=slots) for c in captured[:1]]
                if not families:
                    # Imports without a runtime skeleton conversion keep the
                    # source species' ordered hierarchy. Rest dimensions are
                    # only compared where the authoring context is available.
                    source = json.loads(next((ROOT/'content/species').glob(f'{sid}-*.json')).read_text())
                    families = [dict(slots=[s for s, i in enumerate(mmd.MMD.parse(data, len(skeleton)).anims.table)
                                           if i is not None], skeleton=source['model']['skeleton'], rest=None)]
                report = audit(data, skeleton, families)
                report['name'] = record['name']
                report['authored_contexts'] = len(captured)
                results[sid] = report
                (args.out/f'{sid}.MMD').write_bytes(data)
                (args.out/f'{sid}-species.json').write_text(json.dumps(record, indent=2)+'\n')
                print(sid, len(report['mismatches']), flush=True)
            except (ValueError, OSError, SystemExit) as error:
                results[sid] = dict(error=str(error))
                print(sid, 'ERROR', error, flush=True)
            (args.out/'rig-audit.json').write_text(json.dumps(results, indent=2)+'\n')
    finally:
        native_battle.retarget = original
    return int(any(r.get('error') or r.get('mismatches') for r in results.values()))


if __name__ == '__main__':
    sys.exit(main())
