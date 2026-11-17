"""Exhaustive model-406 crossing and matched PSX-rule rendering evidence.

Usage: python -m tools.models.malomyotismon_audit BEFORE AFTER --out OUT
Folders contain the final atlas-stamped 406.MMD, 406.TIM and index.json.
A residual is explicitly unproven; unsuccessful finite searches are not floors.
"""
import argparse
import hashlib
import json
import math
import multiprocessing
from pathlib import Path

import numpy as np
from tools.models import mesh_round4 as ledger, psx_blend, meshcheck


def compare(before, after):
    result = {}
    for key in sorted(before['pairs'].keys() | after['pairs'].keys(),
                      key=lambda key: tuple(map(int, key.split('/')))):
        a, b = before['pairs'].get(key), after['pairs'].get(key)
        result[key] = dict(before_units=a['depth'] if a else 0,
                           after_units=b['depth'] if b else 0,
                           before_witness=a, after_witness=b,
                           status='residual_unproven' if b else 'clear_all_frames',
                           growth_units=(b['depth'] if b else 0)-(a['depth'] if a else 0))
    return result


def preservation(before, after):
    import animsheet
    import motionstorage
    rows = {}
    if before.bones != after.bones or before.m.anims.table != after.m.anims.table:
        raise ValueError('bone binding or slot aliases changed')
    for slot in before.slots():
        a, loop, events = animsheet.slot_frames(before.m, len(before.bones), slot, max_ticks=6000)
        b, got_loop, got_events = animsheet.slot_frames(after.m, len(after.bones), slot, max_ticks=6000)
        if len(a) != len(b) or loop != got_loop or events != got_events:
            raise ValueError(f'slot {slot}: timing, loops or events changed')
        changed = set()
        for x, y in zip(a, b):
            for bone, (u, v) in enumerate(zip(x, y)):
                for channel, (left, right) in enumerate(zip(u, v)):
                    if left == right:
                        continue
                    if bone not in (3, 4, 5, 11, 12, 13) or channel not in (3, 4, 5):
                        raise ValueError(f'slot {slot}: root/scale/offset changed at {bone}/{channel}')
                    changed.add((bone, channel))
        rows[str(slot)] = dict(ticks=len(a), rotation_channels=sorted(changed))
    storage = {name: motionstorage.audit(m.m.build(), len(m.bones))
               for name, m in [('before', before), ('after', after)]}
    if not storage['after']['fits']:
        raise ValueError('resident or cold read overflow')
    if storage['after']['resident_bytes'] > storage['before']['resident_bytes']:
        raise ValueError('model-local resident growth')
    if before.m.tmd.build() != after.m.tmd.build() or before.tim.blob != after.tim.blob:
        raise ValueError('mesh packets or texture changed')
    return dict(slots=rows, ticks=sum(row['ticks'] for row in rows.values()), storage=storage,
                texture_exact=True, mesh_exact=True, leg_poses_exact=True,
                windup_entry_exit_exact=all(before.poses(55, 6000)[t] == after.poses(55, 6000)[t]
                                           for t in (0, -1)))


def _init_render(before, after, out, cases):
    global _before, _after, _out, _cases, _same_surface
    _before, _after = ledger.load(Path(before), 406), ledger.load(Path(after), 406)
    _out, _cases = Path(out), set(map(tuple, cases))
    _same_surface = _before.m.tmd.build() == _after.m.tmd.build() and _before.tim.blob == _after.tim.blob


def render_fingerprint(before, after, slot):
    digest = hashlib.sha256()
    for model in (before, after):
        digest.update(model.m.tmd.build())
        digest.update(json.dumps(model.bones).encode())
        digest.update(model.m.anims.anims[model.m.anims.table[slot]].build())
        digest.update(np.asarray(model.poses(slot, 6000), dtype='<i4').tobytes())
        if model.tex is not None:
            for item in model.tex[:2]:
                digest.update(np.asarray(item).tobytes())
    return digest.hexdigest()


def _render(job):
    slot, aliases = job
    fingerprint = render_fingerprint(_before, _after, slot)
    metadata = _out/f'{slot}.json'
    cases = sorted(tick for candidate, tick in _cases if candidate == slot)
    if metadata.exists() and (_out/f'{slot}.npz').exists():
        cached = json.loads(metadata.read_text())
        if cached.get('fingerprint') == fingerprint and set(cases) <= set(cached.get('cases', [])):
            cached['aliases'] = aliases
            metadata.write_text(json.dumps(cached)+'\n')
            return dict(slot=slot, aliases=aliases, ticks=len(_before.poses(slot, 6000)),
                        views=len(cached['rows']), cached=True)
    rows, sheets = [], []
    for tick, (a, b) in enumerate(zip(_before.poses(slot, 6000), _after.poses(slot, 6000))):
        views = []
        for view in range(8):
            yaw = view*math.pi/4
            left, frame = psx_blend.render(_before, yaw, math.pi/6, size=128, pose=a)
            same = _same_surface and a == b
            right = left if same else psx_blend.render(_after, yaw, math.pi/6, size=128, pose=b, frame=frame)[0]
            row = dict(slot=slot, tick=tick, view=view,
                       changed_pixels=int(np.any(left != right, axis=2).sum()),
                       before_sha256=hashlib.sha256(left.tobytes()).hexdigest(),
                       after_sha256=hashlib.sha256(right.tobytes()).hexdigest())
            if (slot, tick) in _cases:
                saved_phase = None
                for stage, model, pose, im in [('before', _before, a, left), ('after', _after, b, right)]:
                    phase = saved_phase if same and saved_phase is not None else psx_blend.render(
                        model, yaw, math.pi/6, size=128, pose=pose, frame=frame, depth_offset=2)[0]
                    saved_phase = phase
                    row[stage+'_phase_pixels'] = int(np.any(im != phase, axis=2).sum())
            rows.append(row)
            views.append(np.concatenate([left, right], axis=1))
        sheet = np.concatenate(views, axis=0)
        sheets.append(sheet)
        if (slot, tick) in _cases:
            meshcheck.png(str(_out/f'{slot}-{tick}.png'), sheet)
    np.savez_compressed(_out/f'{slot}.npz', frames=np.stack(sheets))
    (_out/f'{slot}.json').write_text(json.dumps(dict(aliases=aliases, rows=rows, fingerprint=fingerprint, cases=cases))+'\n')
    return dict(slot=slot, aliases=aliases, ticks=len(sheets), views=len(rows))


def render_all(before, after, out, pairs, jobs):
    out.mkdir(parents=True, exist_ok=True)
    a, b = ledger.load(before, 406), ledger.load(after, 406)
    groups = {}
    for slot in a.slots():
        # Slots 35/36 have interpreter-specific root handling. Equal program
        # bytes alone do not prove equal poses; compare the complete decode too.
        key = (a.m.anims.anims[a.m.anims.table[slot]].build(),
               b.m.anims.anims[b.m.anims.table[slot]].build(),
               hashlib.sha256(np.asarray(a.poses(slot, 6000), dtype='<i4').tobytes()).digest(),
               hashlib.sha256(np.asarray(b.poses(slot, 6000), dtype='<i4').tobytes()).digest())
        groups.setdefault(key, []).append(slot)
    canonical = {slot: group[0] for group in groups.values() for slot in group}
    cases = {(canonical[row[stage]['slot']], row[stage]['tick'])
             for row in pairs.values() for stage in ('before_witness', 'after_witness') if row[stage]}
    cases |= {(canonical[s], 0) for s in (0, 2, 3, 4)}
    with multiprocessing.Pool(jobs, initializer=_init_render,
                              initargs=(str(before), str(after), str(out), sorted(cases))) as pool:
        coverage = []
        for row in pool.imap_unordered(_render, [(group[0], group) for group in groups.values()]):
            coverage.append(row)
            print('render', row, flush=True)
    result = dict(coverage=coverage, slots=sum(len(r['aliases']) for r in coverage),
                  frames=sum(len(r['aliases'])*r['ticks'] for r in coverage),
                  view_cases=sum(len(r['aliases'])*r['views'] for r in coverage),
                  size=128, azimuths=8, elevation_degrees=30,
                  rules='GPU diagonal; whole-quad first-triangle cull; mean primitive depth; '
                        'four-unit OT; reverse insertion ties; affine UV; CLUT discard/blend',
                  limitation='orthographic, neutral light; no GTE/perspective or runtime visibility proof')
    (out/'coverage.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--reuse-ledgers', action='store_true')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    summaries = []
    for stage, folder in [('before', args.before), ('after', args.after)]:
        target = args.out/stage
        summary = (json.loads((target/'406.json').read_text()) if args.reuse_ledgers else
                   ledger.scan(folder, 406, target))
        summaries.append(summary)
    pairs = compare(*summaries)
    result = dict(species=406, complete_clearance=not any(r['after_witness'] for r in pairs.values()),
                  pairs=pairs, preservation=preservation(ledger.load(args.before, 406), ledger.load(args.after, 406)))
    (args.out/'audit.json').write_text(json.dumps(result, indent=2)+'\n')
    result['renders'] = render_all(args.before, args.after, args.out/'renders', pairs, args.jobs)
    (args.out/'audit.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
