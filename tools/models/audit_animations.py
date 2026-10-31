#!/usr/bin/env python3
"""Audit imported hit reactions and slot-dependent part visibility.

Run after derive imports/overlays: --models build/NAME/imported-models
--overlays build/NAME/imported-species-models. Without --overlays audit base imports.
A visibility finding needs visual review: native scale tracks can intentionally
swap parts, and a zero-scaled helper need not carry a mesh.
"""
import argparse
import json
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet
import mmd


def audit(data, skeleton):
    nb = len(skeleton)
    model = mmd.MMD.parse(data, nb)
    populated = [slot for slot, index in enumerate(model.anims.table) if index is not None]
    hidden = {}
    animated_visibility = {}
    hits = []
    for slot in range(max(len(model.anims.table), 42)):
        if slot not in populated:
            if slot in (0x28, 0x29):
                hits.append(dict(slot=slot, missing=True))
            continue
        clip = model.anims.anims[model.anims.table[slot]]
        frames, loop, _ = animsheet.slot_frames(model, nb, slot)
        if slot in (0x28, 0x29):
            moving = sum(any(p[b][3:9] != frames[0][b][3:9] for b in range(1, nb)) for p in frames)
            rotations = [max(abs((p[b][c] - frames[0][b][c] + 2048) % 4096 - 2048)
                             for b in range(1, nb) for c in range(3, 6)) for p in frames]
            hits.append(dict(slot=slot, ticks=clip.frame_count, samples=len(frames),
                             moving_ticks=moving, loop=loop,
                             peak_rotation_change=max(rotations),
                             first_rotation_tick=next((i for i, value in enumerate(rotations) if value >= 16), None)))
        for bone in range(1, nb):
            states = [p[bone][:3] == [0, 0, 0] for p in frames]
            if all(states):
                hidden.setdefault(bone, []).append(slot)
            elif any(states):
                animated_visibility.setdefault(bone, []).append(slot)
    visibility = []
    for bone in sorted(set(hidden) | set(animated_visibility)):
        slots = hidden.get(bone, [])
        if len(slots) == len(populated):
            continue
        descendants = {bone}
        for _ in skeleton:
            descendants.update(b for b, (_, parent) in enumerate(skeleton) if parent in descendants)
        visibility.append(dict(bone=bone, mesh_object=skeleton[bone][0],
                               mesh_bones=[b for b in sorted(descendants) if skeleton[b][0] >= 0],
                               hidden_slots=slots, visible_slots=[s for s in populated if s not in slots],
                               animated_visibility_slots=animated_visibility.get(bone, [])))
    return dict(hit_reactions=hits, variable_visibility=visibility)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--models', type=Path, required=True)
    p.add_argument('--overlays', type=Path)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    registry = json.loads((ROOT / 'content/models/imports/models.json').read_text())
    loader = importlib.util.spec_from_file_location('imported_animation_registry', ROOT / 'content/models/imports/species.py')
    provider = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(provider)
    recipes = provider.OVERLAYS
    rows = []
    for sid, record in registry.items():
        spec = json.loads(next((ROOT / 'content/species').glob(f'{sid}-*.json')).read_text())
        path = a.models / f'{sid}.MMD'
        if a.overlays and record.get('field_overlay'):
            path = a.overlays / (recipes[record['field_overlay']][2] + '.MMD')
            report = path.with_name(path.stem + '-report.json')
            if report.exists():
                spec['model']['skeleton'] = json.loads(report.read_text()).get('generated_skeleton', spec['model']['skeleton'])
        rows.append(dict(id=int(sid), name=spec['name'], **audit(path.read_bytes(), spec['model']['skeleton'])))
    failures = [r['id'] for r in rows if any(h.get('missing') or h['ticks'] == 0 or h['moving_ticks'] == 0 for h in r['hit_reactions'])]
    result = dict(species=len(rows), missing_zero_or_static_hits=failures,
                  nearly_static_hits=[r['id'] for r in rows if any(not h.get('missing') and h['peak_rotation_change'] < 16 for h in r['hit_reactions'])],
                  variable_mesh_visibility=[r['id'] for r in rows if any(v['mesh_bones'] for v in r['variable_visibility'])], models=rows)
    a.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'models'}))
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
