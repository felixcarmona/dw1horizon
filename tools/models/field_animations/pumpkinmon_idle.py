"""Pumpkinmon's field idle (slot 0): the import's hop with the legs attenuated.

The import's idle is a 27-tick hop in a loop: the pelvis rises, the pumpkin, arms and scarf move, and both legs fold up and
swing, leaving the floor by 33 units. Everything stays as imported (every tick of every bone except the legs, the loop and
the blink events); only the legs (bones 11-14) keep a third of their motion: each of their rotation and position channels
is scaled to `LEG_SCALE` of its distance from the standing pose (the first tick), so the feet swing less; and because
the pelvis still rises, the two hips are lowered in the pelvis' frame (their position channel) just enough that the lowest
point of the legs rises a third as much as it did, instead of the whole 19 units of the pelvis.
The program is new for slot 0 only: slot 33 (the battle idle) shared the old idle's program and keeps it, and slots 2, 3
and 4 are not touched.

Offline: `tools/models/edit.py get 280` on the commit before this change, then
`python3 -m tools.models.field_animations.pumpkinmon_idle --source THAT.MMD --out AFTER.MMD` and `edit.py put 280 AFTER.MMD`.
"""
import copy
import hashlib

import animsheet
import mmd
import motionstorage
from tools.models.field_animations.triceramon_gait import Body

SPECIES = 280
NB = 15
SOURCE = '625e0ec247baa95a1fe8894386cd1363c5f72d36f02d6f419b4b69347c3a24d7'   # edit.py get 280 before this change
PARENTS = [-1, 0, 1, 1, 3, 4, 1, 6, 7, 1, 9, 1, 11, 1, 13]
LEGS = (11, 12, 13, 14)
LEG_SCALE = 1/3


def attenuate(frames, scale=LEG_SCALE):
    """The old idle's poses with the legs' channels (rotation and position) at `scale` of their distance from tick 0."""
    out = copy.deepcopy(frames)
    for pose in out[1:]:
        for b in LEGS:
            for k in range(3, 9):
                pose[b][k] = int(round(frames[0][b][k] + scale*(pose[b][k] - frames[0][b][k])))
    return out


def lower_hips(body, frames, original, scale=LEG_SCALE):
    """The attenuated poses with the hips (bones 11 and 13, channel 7: y, down is positive) lowered so that the legs'
    lowest point is `scale` of what it was in the old poses (never lower than that, never above the standing pose)."""
    out = copy.deepcopy(frames)
    legs = set(LEGS)
    floor = body.lowest(original[0], legs)
    for pose, old in zip(out[1:], original[1:]):
        target = floor + scale*max(0., body.lowest(old, legs) - floor)
        for _ in range(3):
            extra = body.lowest(pose, legs) - target
            for b in (11, 13):
                pose[b][7] += int(round(extra))
    return out


def build(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE or [b[1] for b in skeleton] != PARENTS:
        raise ValueError("Pumpkinmon's idle is written over the model the importer and the reviewed delta produced")
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = len(skeleton)
    model = mmd.MMD.parse(data, NB)
    model.type = SPECIES
    frames, loop, events = animsheet.slot_frames(model, NB, 0)
    attenuated = lower_hips(Body(model, skeleton), attenuate(frames), frames)
    tol = {b: 0 for b in range(1, NB)}
    tol[None] = 0
    program = mmd.encode_anim(attenuated, NB, loop_sample=loop, events=events, tol=tol, repeats=False)
    model.anims.table[0] = len(model.anims.anims)      # slot 33 (the battle idle) keeps the old program
    model.anims.anims.append(program)
    used = sorted({i for i in model.anims.table if i is not None})
    renumber = {old: i for i, old in enumerate(used)}
    model.anims.anims = [model.anims.anims[i] for i in used]
    model.anims.table = [None if i is None else renumber[i] for i in model.anims.table]
    result = model.build()
    return result, dict(species=SPECIES, source_sha256=SOURCE, changed_slots=[0], storage=motionstorage.require(result, NB))


def main():
    import argparse
    import json
    from pathlib import Path
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    rig = json.loads(Path('content/species/280-pumpkinmon.json').read_text())['model']['skeleton']
    data, report = build(Path(args.source).read_bytes(), rig)
    Path(args.out).write_bytes(data)
    print(args.out, len(data), 'B', report['storage'])


if __name__ == '__main__':
    main()
