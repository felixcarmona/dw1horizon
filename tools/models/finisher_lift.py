#!/usr/bin/env python3
"""Check how far a finisher lifts its lowest vertex above its field-idle floor.

  python tools/models/finisher_lift.py check DIGI.DAT [--json OUT]
  python tools/models/finisher_lift.py repair ID INPUT.MMD OUTPUT.MMD

Measure every tick, including root travel, with Y pointing down. The floor is
the mean lowest vertex of field idle (slot 0); the unit h is that idle's first
tick height. The finisher is slot 0x2E plus the index of the first move >= 58
(excluding 255). The bound, 1.13 h, is the rounded 99th percentile of 92 native
DW1 partner finishers: median 0.01, p90 0.46, p95 0.85, p99 1.13, maximum 1.27 h
(MegaSeadramon rearing up). Unchanged disc finishers are reference observations,
not regressions; they are reported but do not fail. Native NPC records that name
a move without having its animation are reported as unavailable references.
Changed models fail above the bound or if their finisher cannot be measured.
Original models require the player's DW1 extraction in extracted/.

Repair applies the declared recipes in content/models/finisher-lift.json to a
reviewed input. Only the body's translation changes: positive lift is scaled
to at most the requested height. An optional hop window eases that lift back
to the floor within a short part of the original gesture. Timing, rotations,
root travel, scales, events and other slots remain exact. Store results using
edit.py put, one species at a time; repair never writes deltas or pins.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]

import numpy as np
from tools.models.battle_qa import Clip, Rig

BOUND = 1.13
RECIPES = ROOT / 'content/models/finisher-lift.json'


def finisher_slot(moves):
    return next((0x2E + i for i, move in enumerate(moves) if 58 <= move < 255), None)


def measure(rig, slot):
    """Return lift per tick and the idle height/floor, using every mesh vertex."""
    idle = Clip(rig, *rig.frames(0))
    vertices = np.concatenate([idle.V[b] for b in rig.meshed], axis=1)
    height = max(float(np.ptp(vertices[0, :, 1])), 1.0)
    floor = float(vertices[..., 1].max(axis=1).mean())
    clip = Clip(rig, *rig.frames(slot))
    lowest = np.maximum.reduce([clip.V[b][..., 1].max(axis=1) for b in rig.meshed]) + clip.root[:, 1]
    return (floor - lowest) / height, height, floor


def archive_model(data, record, sid):
    import coldsplit
    import species
    if not record['modelSize']:
        path = species.originals().model_path(sid)
        if path is None:
            raise ValueError(f'no disc model for species {sid}; prepare extracted/')
        return Path(path).read_bytes(), True
    start = record['modelSector'] * 2048
    model = data[start:start + record['modelSize']]
    if coldsplit.is_split(model):
        cold = start + (len(model) + 2047) // 2048 * 2048
        model = coldsplit.join(model, data[cold:cold + coldsplit.cold_length(model)],
                               len(record['bones']), coldsplit.table_length(model))
    return model, False


def check_archive(path):
    import species
    data, _, records = species.read_archive(path)
    rows = []
    for sid, record in enumerate(records):
        slot = finisher_slot(record['para']['moves'])
        if slot is None:
            continue
        row = dict(id=sid, name=record['para']['name'], slot=slot)
        try:
            model, native = archive_model(data, record, sid)
            rig = Rig.from_mmd(model, record['bones'], sid=str(sid))
            if native and rig.frames(slot) is None:
                row.update(native_reference=True, unavailable='disc model has no finisher slot', failed=False)
                rows.append(row)
                continue
            lifts, height, _ = measure(rig, slot)
            peak = float(lifts.max())
            row.update(peak_heights=peak, peak_units=peak * height, idle_height=height,
                       ticks=len(lifts), ticks_above_half=int((lifts > .5).sum()),
                       native_reference=native, over_bound=peak > BOUND,
                       failed=peak > BOUND and not native)
        except Exception as error:
            row.update(error=f'{type(error).__name__}: {error}', failed=True)
        rows.append(row)
    return dict(bound_heights=BOUND, species=rows, passed=not any(r['failed'] for r in rows))


def cap_lift(rig, slot, max_heights, hop=None):
    """Lower the body in world Y, keeping all other pose channels exact."""
    if not 0 < max_heights <= BOUND:
        raise ValueError('max_heights must be positive and within the check bound')
    bodies = [b for b, parent in enumerate(rig.parent) if parent == 0]
    if len(bodies) != 1 or 0 in rig.meshed:
        raise ValueError('lift repair requires one body bone under an unmeshed root')
    body = bodies[0]
    lifts, height, _ = measure(rig, slot)
    frames, loop = rig.frames(slot)
    target = np.maximum(lifts, 0) * min(1.0, max_heights / max(float(lifts.max()), 1e-9))
    if hop is not None:
        start, end = hop
        if not 0 <= start < end < len(frames):
            raise ValueError('hop window must be within the clip')
        phase = np.clip((np.arange(len(frames)) - start) / (end - start), 0, 1)
        target = np.minimum(target, max_heights * np.sin(np.pi * phase) ** 2)
    down = np.maximum(0, lifts - target) * height
    result = np.array(frames, copy=True)
    clip = Clip(rig, frames, loop)
    for tick, distance in enumerate(down):
        # The inverse root rotation/scale converts world down into body-parent space.
        result[tick, body, 6:9] += np.linalg.solve(clip.Wf[tick, 0, :3, :3], [0, distance, 0])
    return np.round(result).astype(int), loop


def repair(data, bones, slot, max_heights, hop=None):
    import animsheet
    import mmd
    import motioncyclelayer
    import motionstorage
    from tools.models.field_animations.articulation import replace_channels
    model = mmd.MMD.parse(data, len(bones))
    rig = Rig.from_mmd(data, bones)
    body = next(b for b, parent in enumerate(rig.parent) if parent == 0)
    samples, loop = cap_lift(rig, slot, max_heights, hop)
    original = model.anims.anims[model.anims.table[slot]]
    repaired = replace_channels(original, samples.tolist(), loop, len(bones),
                                {(body, c) for c in (6, 7, 8)}, tolerance=0)
    model.anims.anims.append(repaired)
    model.anims.table[slot] = len(model.anims.anims) - 1
    model.anims.anims, model.anims.table = motioncyclelayer.share_identical_streams(model.anims.anims, model.anims.table)
    out = model.build()
    motionstorage.require(out, len(bones))
    after = Rig.from_mmd(out, bones)
    measured = measure(after, slot)[0]
    if float(measured.max()) > max_heights + 2 / measure(after, slot)[1]:
        raise ValueError('encoded repair exceeds target lift')
    # Encoding must preserve every non-body-translation channel and every other slot.
    for other in range(len(model.anims.table)):
        before_frames = rig.frames(other)
        after_frames = after.frames(other)
        if before_frames is None:
            assert after_frames is None
            continue
        a, a_loop = before_frames
        b, b_loop = after_frames
        assert a.shape == b.shape and a_loop == b_loop
        difference = a != b
        if other == slot:
            difference[:, body, 6:9] = False
        assert not difference.any(), f'changed unrelated channels in slot {other}'
    before = mmd.MMD.parse(data, len(bones))
    assert animsheet.slot_frames(before, len(bones), slot)[2] == animsheet.slot_frames(model, len(bones), slot)[2]
    assert before.tmd.build() == model.tmd.build()
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    check = commands.add_parser('check')
    check.add_argument('archive', type=Path)
    check.add_argument('--json', type=Path)
    edit = commands.add_parser('repair')
    edit.add_argument('id', type=int)
    edit.add_argument('input', type=Path)
    edit.add_argument('output', type=Path)
    args = parser.parse_args(argv)
    if args.command == 'repair':
        recipe = json.loads(RECIPES.read_text())[str(args.id)]
        data = args.input.read_bytes()
        if hashlib.sha256(data).hexdigest() != recipe['source_sha256']:
            raise ValueError('repair requires its reviewed input (before this repair)')
        species = json.loads(next((ROOT / 'content/species').glob(f'{args.id}-*.json')).read_text())
        args.output.write_bytes(repair(data, species['model']['skeleton'], recipe['slot'],
                                      recipe['max_heights'], recipe.get('hop')))
        return 0
    report = check_archive(args.archive)
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + '\n')
    for row in report['species']:
        if row.get('over_bound') or row.get('error'):
            value = row.get('error') or f"{row['peak_heights']:.3f} h (slot {row['slot']:#x})"
            status = 'FAIL' if row['failed'] else 'native reference'
            print(f"{row['id']} {row['name']}: {value} [{status}]")
    print(f"{len(report['species'])} finishers; bound {BOUND:.2f} h; "
          f"{'PASS' if report['passed'] else 'FAIL'}")
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
