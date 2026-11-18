"""Sakuyamon's hair kept out of its body: the last step after `sakuyamon_gait` and `sakuyamon_posture`, on that step's output.

Offline only (player builds replay the pinned delta): `tools/models/edit.py get 316` on the commit that has the leg
gait and the posture step, then `python3 -m tools.models.field_animations.sakuyamon_hair --source THAT.MMD --out AFTER.MMD` and
`edit.py put 316 AFTER.MMD`.

The hair is bones 15 (the cap on the head), 16 (the mass down the back) and 17, 18 (the two long locks). Its clips are one
spring-like sway on every slot, written without a look at the body: the mass pitches 20 degrees about its root and the locks
swing 14 degrees on top of it, so the locks cut into the pelvis and the thighs at the forward end of the sway, and the run's
kicked-back legs cut into them. The hair's own channels are the only ones this step touches:

- Per tick, the least shift back (along the chest's back direction, in whole units of the mass's own frame) that clears
  the mass (16) of every other part but the head, then the least extra turn back of each lock (about the parent's sideways
  axis, put in front of the bone's own rotation) that clears it, given the mass's shift.
- That requirement is widened by two ticks and softened with a triangle filter over the closed loop (never below the
  requirement), plus one grid step of margin: the hair turns back smoothly and early and comes forward again with the sway.

The build refuses another source, a hair vertex still inside the body in a measured tick, a change outside bones 16-18's
rotation channels, the changed programs outside the slots below (and their aliases) and the storage budget.
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
from tools.models.field_animations import okuwamon_limbs as ok  # noqa: E402
from tools.models.field_animations.articulation import replace_channels  # noqa: E402

R = motionsecondary.R
SPECIES, NB = 316, 27
SOURCE = '32f74f0069bf222b33841ebbc8ac6efd62d8f21370ae165e87cef3743b1e7ae1'     # the posture step's output (the leg gait's, run stood up)
SLOTS = (0, 2, 3, 4)                        # idle, walk, tired walk, run (slot 33 shares the idle's program)
HAIR = (16, 17, 18)
CAP = 15
# the parts the hair must not cut: chest, pelvis, legs, both arms, the staff. Not the head (the hair grows from it).
BODY = (1, 2) + tuple(range(3, 11)) + (11, 12, 13) + tuple(range(19, 27))
CHANNELS = {(b, c) for b in HAIR for c in (3, 4, 5)} | {(16, 6), (16, 7), (16, 8)}
STEP, LIMIT, MARGIN = 3.0, 15.0, 3.0         # degrees: the search grid, the most a turn may add, the margin kept
SHIFT_STEP, SHIFT_LIMIT, SHIFT_MARGIN = 4.0, 64.0, 4.0     # units: the same for the mass's shift back
PITCH_STEP, PITCH_LIMIT, PITCH_MARGIN = 5.0, 25.0, 5.0     # degrees: the mass's own turn back


def parse(data):
    m = mmd.MMD.parse(data, NB)
    m.type = SPECIES
    return m


def spin(pose, bone, degrees):
    """A turn about the parent's sideways axis, in front of the bone's own rotation (rounded to whole units)."""
    local = R.rot_of(pose[bone])
    new = R.m3mul(R.from_axis_angle([1, 0, 0], math.radians(degrees)), local)
    pose[bone][3:6] = [round(v) for v in mmd.matrix_euler(new, pose[bone][3:6])]


def shift(pose, body, units):
    """The hair's root (bone 16) moved `units` back along the chest's back direction, in whole units of its own frame."""
    mats = np.array(body.world(pose)[0])
    back = mats[1][:3, :3] @ np.array([0., 0., 1.])
    back /= np.linalg.norm(back)
    parent = mats[CAP][:3, :3]
    parent = parent / np.linalg.norm(parent, axis=0)
    local = parent.T @ (back * units)
    for i in range(3):
        pose[16][6 + i] = round(pose[16][6 + i] + local[i])


def hair_count(body, pose, bones):
    mats, world = body.world(pose)
    return body.count(mats, world, list(bones), list(BODY))


def sign_back(body, pose):
    """+1 if a positive turn about the sideways axis moves the locks to the back (z up), else -1."""
    z0 = body.points(body.world(pose)[1], [17, 18])[:, 2].mean()
    q = copy.deepcopy(pose)
    spin(q, 16, 10.)
    z1 = body.points(body.world(q)[1], [17, 18])[:, 2].mean()
    return 1 if z1 > z0 else -1


def need(body, frames, bones, apply, sign, step=STEP, limit=LIMIT):
    """Per tick (not the last), the least turn on `bones` (the angle grid) that leaves them clear; where none does (an arm
    swung into the hair), the one with the fewest vertices inside, the least of them on a tie. `apply(pose, angle)`."""
    out = []
    for f in frames[:-1]:
        best = None
        for k in range(int(limit / step) + 1):
            p = copy.deepcopy(f)
            apply(p, sign * k * step)
            c = hair_count(body, p, bones)
            if best is None or c < best[0]:
                best = (c, k * step)
            if c == 0:
                break
        out.append(best[1])
    return out


def need_mass(body, frames, sign):
    """Per tick (not the last), the cheapest pair (turn back, shift back) that clears the mass: the pairs on a grid taken by
    the turn's share of its limit plus the shift's share of its own; none clear (an arm swung into it), the fewest inside."""
    pairs = sorted(((i * PITCH_STEP, j * SHIFT_STEP) for i in range(int(PITCH_LIMIT / PITCH_STEP) + 1)
                    for j in range(int(SHIFT_LIMIT / SHIFT_STEP) + 1)),
                   key=lambda t: t[0] / PITCH_LIMIT + t[1] / SHIFT_LIMIT)
    turns, shifts = [], []
    for f in frames[:-1]:
        best = None
        for a, u in pairs:
            p = copy.deepcopy(f)
            spin(p, 16, sign * a)
            shift(p, body, u)
            c = hair_count(body, p, [16])
            if best is None or c < best[0]:
                best = (c, a, u)
            if c == 0:
                break
        turns.append(best[1])
        shifts.append(best[2])
    return turns, shifts


def soften(d):
    """Widened by two ticks and filtered with a triangle over the closed loop, so it never falls below `d`."""
    n = len(d)
    wide = [max(d[(i + j) % n] for j in range(-2, 3)) for i in range(n)]
    k = (1, 2, 3, 2, 1)
    return [sum(k[j + 2] * wide[(i + j) % n] for j in range(-2, 3)) / 9. for i in range(n)]


def build_slot(model, body, frames, slot):
    sign = sign_back(body, frames[0])
    frames = [[list(b) for b in f] for f in frames]
    n = len(frames)
    closed = all(frames[0][b] == frames[-1][b] for b in HAIR)
    work = frames if closed else frames + [frames[0]]
    # 1. the mass: the least pair (turn back, shift back) per tick, each series softened over the loop
    d_turn, d_shift = need_mass(body, work, sign)
    s_turn = [min(PITCH_LIMIT, v) for v in soften([min(PITCH_LIMIT, v + PITCH_MARGIN) if v else 0. for v in d_turn])]
    s16 = [min(SHIFT_LIMIT, v) for v in soften([min(SHIFT_LIMIT, v + SHIFT_MARGIN) if v else 0. for v in d_shift])]
    stage = []
    for f, a, u in zip(work, s_turn + [s_turn[0]], s16 + [s16[0]]):
        p = copy.deepcopy(f)
        spin(p, 16, sign * a)
        shift(p, body, u)
        stage.append(p)
    # 2. each lock, given the mass
    final = [copy.deepcopy(p) for p in stage]
    angles = {16: s16, 'turn16': s_turn}
    for lock in (17, 18):
        d = need(body, stage, [lock], lambda p, a, lock=lock: spin(p, lock, a), sign)
        s = soften([min(LIMIT, v + MARGIN) if v else 0. for v in d])
        angles[lock] = s
        for p, a in zip(final, s + [s[0]]):
            spin(p, lock, sign * a)
    final = final[:n]
    if closed:                  # the last tick is the first one's hair (the rest of it stays the clip's own)
        for b in HAIR:
            final[-1][b] = list(final[0][b])
    return final, {b: [round(v, 1) for v in a] for b, a in angles.items()}


def build(data):
    assert hashlib.sha256(data).hexdigest() == SOURCE
    model = parse(data)
    body = ok.Body(model, mmd.exe().skeleton[SPECIES])
    result = copy.deepcopy(model)
    report = {}
    for s in SLOTS:
        idx = model.anims.table[s]
        frames, loop, events = animsheet.slot_frames(model, NB, s)
        assert loop == 0
        new, angles = build_slot(model, body, frames, s)
        for f_new, f_old in zip(new, frames):
            for b in range(NB):
                for c in range(9):
                    if (b, c) not in CHANNELS and b != 0:
                        assert f_new[b][c] == f_old[b][c], (s, b, c)
        result.anims.anims[idx] = replace_channels(model.anims.anims[idx], new, loop, NB, CHANNELS)
        report[s] = {str(b): dict(max=max(a), mean=round(sum(a) / len(a), 1)) for b, a in angles.items()}
    out = result.build()
    effective = parse(out)
    assert effective.tmd.build() == model.tmd.build()
    assert changed_programs(model, effective) == sorted(s for s in range(len(model.anims.table))
                                                       if model.anims.table[s] in {model.anims.table[t] for t in SLOTS})
    storage = motionstorage.audit(out, NB)
    assert storage['fits'], storage
    return out, dict(output_sha256=hashlib.sha256(out).hexdigest(), turns=report, storage=storage)


def measure(model, slot):
    """Per tick, the hair's vertices inside each part group (the numbers the tests bound)."""
    body = ok.Body(model, mmd.exe().skeleton[SPECIES])
    groups = dict(torso=(1, 2), arms=(11, 12, 13, 19, 20, 21), legs=tuple(range(3, 11)), staff=tuple(range(22, 27)))
    rows = []
    for f in animsheet.slot_frames(model, NB, slot)[0]:
        mats, world = body.world(f)
        rows.append({k: body.count(mats, world, [15, 16, 17, 18], list(v)) for k, v in groups.items()})
    return rows


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
