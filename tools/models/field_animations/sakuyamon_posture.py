"""Sakuyamon's run stood up: the step between `sakuyamon_gait` (legs) and `sakuyamon_hair` (hair), on the first's output.

Offline only (player builds replay the pinned delta): `tools/models/edit.py get 316` on the commit that has the leg gait,
then `python3 -m tools.models.field_animations.sakuyamon_posture --source THAT.MMD --out AFTER.MMD` and `edit.py put 316 AFTER.MMD`
(then the hair step on that).

The import's run (slot 4) leans the chest 39 degrees forward (bone 1) while the pelvis (bone 2) and the head (bone 14) turn back by
almost as much, so the legs and the head keep straight and the shoulders ride up: it reads as a hump. Each tick the chest's forward lean
(its pitch about the idle's) is cut to `KEEP` of itself, a turn about the same pivot that the pelvis and the head take back in front of
their own rotation, so the pelvis, the legs, the feet and the head keep exactly the world orientation they had (the leg gait is untouched):
only the chest, shoulders and arms (which hang from the chest) stand up. The chest's own sway (yaw, roll) and the timing are the import's.
The build refuses another source, a change outside the rotation channels of bones 1, 2, 14 of the run, a pelvis or head that moved and the
storage budget.
"""
import argparse
import copy
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet  # noqa: E402
import mmd  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models.field_animations.articulation import replace_channels  # noqa: E402
from tools.models.field_animations.war_greymon import set_rotation  # noqa: E402
from tools.models.field_animations import sakuyamon_gait as gait  # noqa: E402
from tools.models.field_animations.sakuyamon_gait import NB, SPECIES, parse  # noqa: E402
import motionsecondary  # noqa: E402

R = motionsecondary.R
SOURCE = '255e96e0dc2bb0076477b94a4d30ae18afaa4a02a7b59881174ab980dccf2172'     # `edit.py get 316` with the leg gait
SLOT = 4
KEEP = 0.3                       # the part of the chest's forward lean (over the idle's) that stays
CHANNELS = {(b, c) for b in (1, 2, 14) for c in (3, 4, 5)}


def stand(frames, idle_pitch):
    out = []
    history = {}
    for f in frames:
        p = copy.deepcopy(f)
        r1 = np.array(R.rot_of(f[1]))
        k = (1 - KEEP) * (f[1][3] - idle_pitch) * 360. / 4096.
        r1n = np.array(R.from_axis_angle([1, 0, 0], math.radians(-k))) @ r1
        back = r1n.T @ r1                    # what the pelvis and the head take, so they keep their world orientation
        set_rotation(p, 1, r1n, history)
        for b in (2, 14):
            set_rotation(p, b, back @ np.array(R.rot_of(f[b])), history)
        out.append(p)
    return out


def build(data):
    assert hashlib.sha256(data).hexdigest() == SOURCE
    model = parse(data)
    idx = model.anims.table[SLOT]
    assert [i for i, v in enumerate(model.anims.table) if v == idx] == [SLOT]
    frames, loop, events = animsheet.slot_frames(model, NB, SLOT)
    assert loop == 0
    idle = animsheet.slot_frames(model, NB, 0)[0]
    idle_pitch = sum(f[1][3] for f in idle) / len(idle)
    frames = [[list(b) for b in f] for f in frames]
    new = stand(frames, idle_pitch)
    new[-1][1:] = copy.deepcopy(new[0][1:])
    for f_new, f_old in zip(new, frames):
        for b in range(NB):
            for c in range(9):
                if (b, c) not in CHANNELS and b != 0:
                    assert f_new[b][c] == f_old[b][c], (b, c)
    result = copy.deepcopy(model)
    result.anims.anims[idx] = replace_channels(model.anims.anims[idx], new, loop, NB, CHANNELS)
    out = result.build()
    effective = parse(out)
    assert changed_programs(model, effective) == [SLOT]
    for f_old, f_new in zip(frames, animsheet.slot_frames(effective, NB, SLOT)[0]):    # the pelvis and head keep their world orientation
        a, b = gait.worlds(model, f_old), gait.worlds(effective, f_new)
        for bone in (2, 14):
            assert np.abs(a[bone, :3, :3] - b[bone, :3, :3]).max() < 0.01, bone
    storage = motionstorage.audit(out, NB)
    assert storage['fits'], storage
    return out, dict(output_sha256=hashlib.sha256(out).hexdigest(), keep=KEEP, idle_pitch=idle_pitch, storage=storage['resident_bytes'])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    data, report = build(a.source.read_bytes())
    a.out.write_bytes(data)
    print(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
