"""Musyamon's walk, tired walk and run stood up: the chest and the head no longer hang forward (species 325, slots 2, 3, 4).

Offline only (player builds replay the pinned delta): `tools/models/edit.py get 325` on the commit before this change, then
`python3 -m tools.models.field_animations.musyamon_posture --source THAT.MMD --out AFTER.MMD` and `edit.py put 325 AFTER.MMD`
(then the hair step, `musyamon_hair`, on that).

What looked wrong ("it walks head down"). The import's three gaits lean the chest (bone 1, the root of the upper body: the head,
shoulders, arms, sword and cape hang from it) forward by 31 to 37 degrees on average against the idle's 13, and the head (bone 23)
on top of that by 17 to 29 against the idle's 9: the line from the hips to the head leans 50 to 55 degrees (the idle's 31), so the
head hangs in front of the feet with the face to the ground. The pelvis (bone 2, with the legs below it) is a child of the chest, so
the import counter-turned it: the legs are straight, the shoulders ride up.

Each tick, as one turn about the world's sideways axis for the whole clip (so the sway, bob and timing of the import stay): the
chest is turned back by the part of its average lean over the idle's that is not wanted, the pelvis takes the opposite turn (it
keeps exactly its world orientation: the legs, feet, stance, slip and root motion are the import's byte for byte), and the head is
turned back about the same sideways axis by the part of its own average lean that is not wanted. The head is a child of the chest, so
it also moves back and up with it. Every other channel and the idle and the other programs are the import's.
The build refuses another source, a change outside the rotation channels of bones 1, 2 and 23 of the three slots, a pelvis that moved
and the storage budget.
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
import motionsecondary  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models.field_animations.articulation import replace_channels  # noqa: E402
from tools.models.field_animations.war_greymon import set_rotation  # noqa: E402

R = motionsecondary.R
SPECIES, NB = 325, 28
SOURCE = '60a4ff152006d22426ba15cc9cfc4e3be7380c7c3f1f45d1b87ba6773b37ba16'     # `edit.py get 325` before this change
SLOTS = (2, 3, 4)
CHEST, PELVIS, HEAD = 1, 2, 23
CAPE = (17, 25, 26, 27)                    # hang from the chest below its pivot: they keep their world orientation, like the pelvis
CHANNELS = {(b, c) for b in (CHEST, PELVIS, HEAD) + CAPE for c in (3, 4, 5)}
# degrees of average lean over the idle's that stay: (chest, head), per slot
KEEP = {2: (3., -3.), 3: (6., 0.), 4: (7., -2.)}


def parse(data):
    m = mmd.MMD.parse(data, NB)
    m.type = SPECIES
    return m


def worlds(model, pose):
    p = copy.deepcopy(pose)
    p[0] = [4096] * 3 + [0] * 6
    return np.array(mmd.bone_matrices(model, p))


def rotation_of(mat):
    r = np.array(mat[:3, :3], float)
    return r / np.linalg.norm(r, axis=0)


def lean(rot):
    """Forward lean (degrees) of a bone's own up axis in the world: the face is to -z, up is -y."""
    v = rot @ np.array([0., -1., 0.])
    return math.degrees(math.atan2(-v[2], -v[1]))


def about_x(deg):
    return np.array(R.from_axis_angle([1, 0, 0], math.radians(deg)))


def leans(model, frames, bone):
    return np.array([lean(rotation_of(worlds(model, f)[bone])) for f in frames])


def sign_of_x():
    """+1 if a positive turn about the world's x lowers the lean, else -1 (found, not assumed)."""
    r = np.eye(3)
    return 1 if lean(about_x(1.) @ r) < lean(r) else -1


def stand(model, frames, keep_chest, keep_head, idle_chest, idle_head):
    s = sign_of_x()
    chest = leans(model, frames, CHEST)
    head = leans(model, frames, HEAD)
    cut_chest = max(0., chest[:-1].mean() - idle_chest - keep_chest)
    cut_head = (head[:-1].mean() - idle_head - keep_head)
    out, history = [], {}
    for f in frames:
        w = worlds(model, f)
        p = copy.deepcopy(f)
        w1 = about_x(s * cut_chest) @ rotation_of(w[CHEST])
        w23 = about_x(s * cut_head) @ rotation_of(w[HEAD])
        set_rotation(p, CHEST, w1, history)
        set_rotation(p, PELVIS, w1.T @ rotation_of(w[PELVIS]), history)
        set_rotation(p, HEAD, w1.T @ w23, history)
        for b in CAPE:
            set_rotation(p, b, w1.T @ rotation_of(w[b]), history)
        out.append(p)
    return out, cut_chest, cut_head


def build(data):
    assert hashlib.sha256(data).hexdigest() == SOURCE
    model = parse(data)
    idle = animsheet.slot_frames(model, NB, 0)[0]
    idle_chest = leans(model, idle, CHEST)[:-1].mean()
    idle_head = leans(model, idle, HEAD)[:-1].mean()
    result = copy.deepcopy(model)
    report = {}
    for slot in SLOTS:
        idx = model.anims.table[slot]
        frames, loop, events = animsheet.slot_frames(model, NB, slot)
        assert loop == 0
        frames = [[list(b) for b in f] for f in frames]
        new, cc, ch = stand(model, frames, *KEEP[slot], idle_chest, idle_head)
        for b in (CHEST, PELVIS, HEAD) + CAPE:
            if frames[0][b][3:6] == frames[-1][b][3:6]:      # a closed loop stays closed
                new[-1][b][3:6] = list(new[0][b][3:6])
        for f_new, f_old in zip(new, frames):
            for b in range(NB):
                for c in range(9):
                    if (b, c) not in CHANNELS and b != 0:
                        assert f_new[b][c] == f_old[b][c], (slot, b, c)
        result.anims.anims[idx] = replace_channels(model.anims.anims[idx], new, loop, NB, CHANNELS)
        report[slot] = dict(chest_cut=round(cc, 1), head_cut=round(ch, 1))
    out = result.build()
    effective = parse(out)
    assert effective.tmd.build() == model.tmd.build()
    aliases = sorted(s for s in range(len(model.anims.table)) if model.anims.table[s] in {model.anims.table[t] for t in SLOTS})
    assert changed_programs(model, effective) == aliases
    for slot in SLOTS:                                       # the pelvis (so the legs) keeps its world orientation
        old = animsheet.slot_frames(model, NB, slot)[0]
        new = animsheet.slot_frames(effective, NB, slot)[0]
        for f_old, f_new in zip(old, new):
            a, b = worlds(model, f_old), worlds(effective, f_new)
            assert np.abs(a[PELVIS, :3, :3] - b[PELVIS, :3, :3]).max() < 0.01, slot
    storage = motionstorage.audit(out, NB)
    assert storage['fits'], storage
    return out, dict(output_sha256=hashlib.sha256(out).hexdigest(), cuts=report, storage=storage['resident_bytes'])


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
