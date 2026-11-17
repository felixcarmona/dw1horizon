"""Exhaustive Omnimon frame/view evidence using the repository PSX renderer.

Each row covers one decoded frame and eight azimuths at 30 degrees. Models
must already be atlas-stamped. The renderer uses GPU diagonals, primitive
NCLIP, four-unit OT bins and reversed insertion ties. These orthographic
measurements are not a claim about perspective GTE or emulator visibility.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from tools.models import mesh_round4, omnimon_render


class _CachedPrim:
    """Immutable render-only view; decoding does not depend on a pose."""
    def __init__(self, prim):
        self.value, self.mode = prim.decode(), prim.mode

    def decode(self):
        return self.value


def identity(model, folder, slot, size):
    """Bind a checkpoint to all inputs affecting these rendered frames."""
    h = hashlib.sha256()
    for data in (model.m.tmd.build(),
                 model.m.anims.anims[model.m.anims.table[slot]].build(),
                 json.dumps(model.bones).encode(), (Path(folder)/'461.TIM').read_bytes(),
                 str(size).encode(), Path(omnimon_render.__file__).read_bytes()):
        h.update(len(data).to_bytes(8, 'little'))
        h.update(data)
    return h.hexdigest()


def _render_slot(job):
    before_dir, after_dir, out, slot, size = job
    before, after = (mesh_round4.load(Path(p), 461) for p in (before_dir, after_dir))
    inputs = [identity(m, p, slot, size) for m, p in zip((before, after), (before_dir, after_dir))]
    for model in (before, after):
        for obj in model.m.tmd.objects:
            obj.prims = [_CachedPrim(p) for p in obj.prims]
    poses = [m.poses(slot, 6000) for m in (before, after)]
    if len(poses[0]) != len(poses[1]) or len(poses[0]) >= 6000:
        raise ValueError('Omnimon rendering requires equal, complete clip coverage')
    rows, visible, cache = [], set(), {}
    for tick, (pa, pb) in enumerate(zip(*poses)):
        key = np.asarray([pa, pb], np.int64).tobytes()
        if key in cache:
            for row in cache[key]:
                rows.append([slot, tick]+row[2:])
            continue
        start = len(rows)
        for view in range(8):
            yaw = view*math.pi/4
            (a, ap), frame, _ = omnimon_render.phases(before, yaw, math.pi/6, size=size, pose=pa)
            (b, bp), _, contributors = omnimon_render.phases(after, yaw, math.pi/6, size=size,
                                                           pose=pb, frame=frame)
            visible.update(contributors)
            rows.append([slot, tick, view, int(np.any(a != b, axis=2).sum()),
                         int(np.any(a != ap, axis=2).sum()), int(np.any(b != bp, axis=2).sum()),
                         hashlib.sha256(a.tobytes()).hexdigest(), hashlib.sha256(b.tobytes()).hexdigest()])
        cache[key] = rows[start:]
    path = Path(out)/f'{slot}.csv.gz'
    with gzip.open(path, 'wt', newline='') as f:
        w = csv.writer(f)
        w.writerow(['slot', 'frame', 'view', 'changed_pixels', 'before_phase_pixels',
                    'after_phase_pixels', 'before_rgb_sha256', 'after_rgb_sha256'])
        w.writerows(rows)
    return dict(slot=slot, frames=len(poses[0]), views=len(rows), inputs=inputs,
                rendered_unique_frames=len(cache),
                changed_pixels=sum(r[3] for r in rows), before_phase_pixels=sum(r[4] for r in rows),
                after_phase_pixels=sum(r[5] for r in rows),
                visible_packets=sorted(visible), ledger_sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def render_all(before, after, out, jobs=4, size=160):
    out.mkdir(parents=True, exist_ok=True)
    models = [mesh_round4.load(p, 461) for p in (before, after)]
    slots = models[0].slots()
    if slots != models[1].slots():
        raise ValueError('Omnimon render slot coverage differs')
    inputs = {s:[identity(m, p, s, size) for m, p in zip(models, (before, after))] for s in slots}
    signatures = {s:hashlib.sha256(np.asarray([m.poses(s, 6000) for m in models], np.int64).tobytes()).hexdigest()
                  for s in slots}
    cached, completed = {}, {}
    progress = out/'progress.json'
    if progress.exists():
        for row in json.loads(progress.read_text())['slots']:
            s = row['slot']
            path = out/f'{s}.csv.gz'
            if (s in inputs and row.get('inputs') == inputs[s] and path.exists()
                    and hashlib.sha256(path.read_bytes()).hexdigest() == row['ledger_sha256']):
                cached[signatures[s]] = row
    canonical = {}
    for s in slots:
        canonical.setdefault(signatures[s], s)
    work = [(str(before), str(after), str(out), s, size)
            for sig, s in canonical.items() if sig not in cached]
    completed.update(cached)
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        for future in as_completed([pool.submit(_render_slot, j) for j in work]):
            row = future.result()
            completed[signatures[row['slot']]] = row
            print(f"slot {row['slot']}: {row['frames']} frames / {row['views']} views", flush=True)
            # An interrupted run has an explicitly incomplete manifest.
            progress.write_text(json.dumps(dict(complete=False, slots=list(completed.values())), indent=2)+'\n')
    rows = []
    for s in slots:
        original = completed[signatures[s]]
        row = dict(original, slot=s, inputs=inputs[s])
        if original['slot'] != s:
            with gzip.open(out/f"{original['slot']}.csv.gz", 'rt', newline='') as f:
                data = list(csv.reader(f))
            for record in data[1:]:
                record[0] = str(s)
            with gzip.open(out/f'{s}.csv.gz', 'wt', newline='') as f:
                csv.writer(f).writerows(data)
            row.update(reused_from_slot=original['slot'],
                       ledger_sha256=hashlib.sha256((out/f'{s}.csv.gz').read_bytes()).hexdigest())
        rows.append(row)
    result = dict(complete=True, model=461, size=size, azimuths=8, elevation_degrees=30,
                  depth_bin_units=4, phase_offset_units=2,
                  frames=sum(r['frames'] for r in rows), views=sum(r['views'] for r in rows),
                  slots=sorted(rows, key=lambda r: r['slot']))
    result['unique_clip_pose_sequences'] = len(canonical)
    result['rendered_unique_frames'] = sum(r.get('rendered_unique_frames', r['frames']) for r in completed.values())
    all_packets = {t[:3] for t in models[1].tris}
    visible = {tuple(p) for r in rows for p in r['visible_packets']}
    result['conservative_hidden_packets'] = sorted(all_packets-visible)
    for key in ('changed_pixels', 'before_phase_pixels', 'after_phase_pixels'):
        result[key] = sum(r[key] for r in rows)
    result['hashes'] = {stage: {ext: hashlib.sha256((folder/f'461.{ext}').read_bytes()).hexdigest()
                               for ext in ('MMD', 'TIM')}
                        for stage, folder in zip(('before', 'after'), (before, after))}
    (out/'metrics.json').write_text(json.dumps(result, indent=2)+'\n')
    progress.write_text(json.dumps(result, indent=2)+'\n')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('before', type=Path)
    p.add_argument('after', type=Path)
    p.add_argument('out', type=Path)
    p.add_argument('--jobs', type=int, default=4)
    p.add_argument('--size', type=int, default=160)
    a = p.parse_args()
    if a.jobs < 1 or a.size < 32:
        p.error('jobs must be positive and size at least 32')
    render_all(a.before, a.after, a.out, a.jobs, a.size)


if __name__ == '__main__':
    main()
