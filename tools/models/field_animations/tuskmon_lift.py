"""Tuskmon stands a little taller and its big back horns stop flexing like rubber.

Written over the model that tuskmon.py produced (its idle, tired idle, walk, tired walk and run keep their cycle lengths
and root speeds). On every tick of the five field clips:

- (idle and the walks and run; the tired idle, slot 1, rests the head on the floor and keeps its posture, only its horns
  change) the pelvis is raised by LIFT units (the claws keep the world position and orientation they had, so nothing floats and
  the foot slide is unchanged); the hips and knees are solved again to the same ankles, the knees keeping the side they
  bent to, so the legs straighten. The chest is pitched up by PITCH degrees about the pelvis, so the head and the
  chin come up too and the body no longer hunches over the floor;
- the horns (bone 21, a rigid piece on the chest) keep FLEX (none) of the rotation they had against the chest: their
  rotation is their mean pose in that clip on every tick, so they turn exactly with the chest, without lag or swing.

Offline: `tools/models/edit.py get 253` on the commit before this change, then
`python3 -m tools.models.field_animations.tuskmon_lift --out AFTER.MMD` and `edit.py put 253 AFTER.MMD`.
"""
import copy
import hashlib
import json
import math

import animsheet
import mmd
import motionstorage
import numeric as np
from tools.models.field_animations.channels import coalesce, replace_channels
from tools.models.field_animations.war_greymon import align, rotation, set_rotation

SPECIES = 253
SOURCE = '774d0043a9f0436718ab5a205dc76b3f17cdea10edf112dbf508dcd728f37212'   # edit.py get 253 before this change
PARENTS = [-1, 11, 1, 2, 3, 1, 5, 6, 1, 8, 9, 0, 11, 12, 13, 11, 15, 16, 11, 18, 19, 1]
LEGS = ((12, 13, 14), (15, 16, 17))
HORN = 21
LIFT = {0: 21, 1: 0, 2: 14, 3: 13, 4: 9}      # units the pelvis rises (the legs of the gaits are nearly straight: no more)
PITCH = {0: 4, 1: 0, 2: 4, 3: 3, 4: 4}          # degrees the chest tips up about the pelvis
FLEX = 0                                        # share of the horns' swing against the chest that stays: none, they are rigid


class Body:
    def __init__(self, model, skeleton):
        self.model = model
        self.verts = {b: np.array(model.tmd.obj_verts(o))[:, :3] for b, (o, _) in enumerate(skeleton) if o >= 0}

    def world(self, pose):
        p = copy.deepcopy(pose)
        p[0] = [4096]*3 + [0]*6
        return np.array(mmd.bone_matrices(self.model, p))

    def orient(self, w, b):
        return w[b, :3, :3]/np.linalg.norm(w[b, :3, 0])

    def lowest(self, pose, bones=None):
        w = self.world(pose)
        return -max(float((self.verts[b] @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max())
                    for b in self.verts if bones is None or b in bones)


def log_so3(r):
    c = max(-1., min(1., (float(r[0][0] + r[1][1] + r[2][2]) - 1)/2))
    angle = math.acos(c)
    if angle < 1e-9:
        return [0., 0., 0.]
    s = 2*math.sin(angle)
    return [angle*(r[2][1] - r[1][2])/s, angle*(r[0][2] - r[2][0])/s, angle*(r[1][0] - r[0][1])/s]


def exp_so3(v):
    angle = math.sqrt(sum(x*x for x in v))
    if angle < 1e-12:
        return np.eye(3)
    x, y, z = (a/angle for a in v)
    k = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    return np.eye(3) + math.sin(angle)*k + (1 - math.cos(angle))*(k @ k)


def mean_rotation(rots):
    mean = np.array(rots[0], float)
    for _ in range(20):
        step = [sum(log_so3(mean.T @ r)[i] for r in rots)/len(rots) for i in range(3)]
        mean = mean @ exp_so3(step)
    return mean


def horn_angles(frames):
    """Degrees of the horns' rotation against the chest, away from their mean pose in the clip, tick by tick."""
    rots = [np.array(mmd.rot_matrix(*f[HORN][3:6])) for f in frames]
    mean = mean_rotation(rots[:-1])
    return [math.degrees(math.sqrt(sum(x*x for x in log_so3(mean.T @ r)))) for r in rots]


def stiffen_horns(frames, flex):
    rots = [np.array(mmd.rot_matrix(*f[HORN][3:6])) for f in frames]
    mean = mean_rotation(rots[:-1])
    hist = {}
    for f, r in zip(frames, rots):
        deviation = log_so3(mean.T @ r)
        set_rotation(f, HORN, mean @ exp_so3([flex*x for x in deviation]), hist)


def solve_leg(body, w, f, leg, goal):
    """Hip and knee world rotations putting the ankle on goal; the old pose is the start, the knee keeps its side."""
    hip, knee, foot = leg
    h = w[hip, :3, 3]
    la = np.linalg.norm(f[knee][6:9])
    lb = np.linalg.norm(f[foot][6:9])
    delta = goal - h
    dist = np.linalg.norm(delta)
    assert abs(la - lb) < dist < la + lb - .1, ('reach', hip, dist, la + lb)
    direct = delta/dist
    pole = w[knee, :3, 3] - h
    pp = pole - direct*(pole @ direct)
    pp /= np.linalg.norm(pp)
    along = (la*la - lb*lb + dist*dist)/(2*dist)
    joint = h + direct*along + pp*math.sqrt(max(0, la*la - along*along))
    ro = body.orient(w, hip)
    rh = align(ro @ np.array(f[knee][6:9]), joint - h) @ ro
    rk = align(body.orient(w, knee) @ np.array(f[foot][6:9]), goal - joint) @ body.orient(w, knee)
    return rh, rk


def lift_frames(body, frames, slot):
    out, hist, fhist = [], {}, {}
    pitch = rotation([-PITCH[slot], 0, 0])
    for source in frames:
        f = copy.deepcopy(source)
        ws = body.world(source)
        goals = {foot: ws[foot, :3, 3].copy() for _, _, foot in LEGS}
        feet = {foot: body.orient(ws, foot).copy() for _, _, foot in LEGS}
        f[11][7] -= LIFT[slot]
        set_rotation(f, 1, pitch @ np.array(mmd.rot_matrix(*source[1][3:6])), hist)
        w = body.world(f)
        # the pitch must not move the legs' parent: legs hang from the pelvis (bone 11) only
        for leg in LEGS:
            hip, knee, foot = leg
            rh, rk = solve_leg(body, w, f, leg, goals[foot])
            set_rotation(f, hip, body.orient(w, 11).T @ rh, fhist)
            w = body.world(f)
            set_rotation(f, knee, body.orient(w, hip).T @ rk, fhist)
            w = body.world(f)
            set_rotation(f, foot, body.orient(w, knee).T @ feet[foot], fhist)
            w = body.world(f)
        out.append(f)
    out[-1][1:] = copy.deepcopy(out[0][1:])
    return out


FEET = {(b, c) for b in (14, 17) for c in (3, 4, 5)}
LEG_CHANNELS = {(b, c) for b in (12, 13, 15, 16) for c in (3, 4, 5)} | FEET
HORN_CHANNELS = {(HORN, c) for c in (3, 4, 5)}
CHANNELS = {(1, c) for c in (3, 4, 5)} | {(11, 7)}


def build(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE or [b[1] for b in skeleton] != PARENTS:
        raise ValueError("Tuskmon's lift is written over the model with the reviewed claw strides")
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = len(skeleton)
    n = len(skeleton)
    model = mmd.MMD.parse(data, n)
    model.type = SPECIES
    body = Body(model, skeleton)
    done = {}
    for slot in range(5):
        old = model.anims.anims[model.anims.table[slot]]
        frames = animsheet.slot_frames(model, n, slot)[0]
        if LIFT[slot]:
            frames = lift_frames(body, frames, slot)
        stiffen_horns(frames, FLEX)
        animation = replace_channels(old, frames, 0, n, HORN_CHANNELS, tolerance=1)
        if LIFT[slot]:
            animation = replace_channels(animation, frames, 0, n, CHANNELS, tolerance=1)
            animation = replace_channels(animation, frames, 0, n, LEG_CHANNELS - FEET, tolerance=0)
            temporary = copy.deepcopy(model)
            temporary.anims.table[slot] = len(temporary.anims.anims)
            temporary.anims.anims.append(animation)
            decoded = animsheet.slot_frames(temporary, n, slot)[0]
            fhist = {}
            refs = animsheet.slot_frames(model, n, slot)[0]
            for tick, f in enumerate(decoded):        # the claws keep their old world rotation on the decoded knees
                wo = body.world(refs[tick])
                for knee, foot in ((13, 14), (16, 17)):
                    w = body.world(f)
                    set_rotation(f, foot, body.orient(w, knee).T @ body.orient(wo, foot), fhist)
            decoded[-1][1:] = copy.deepcopy(decoded[0][1:])
            animation = replace_channels(animation, decoded, 0, n, FEET, tolerance=0)
        animation, _ = coalesce(animation)
        done[slot] = animation
    for slot, animation in done.items():
        model.anims.table[slot] = len(model.anims.anims)
        model.anims.anims.append(animation)
    used = sorted({i for i in model.anims.table if i is not None})
    renumber = {old: new for new, old in enumerate(used)}
    model.anims.anims = [model.anims.anims[i] for i in used]
    model.anims.table = [None if i is None else renumber[i] for i in model.anims.table]
    result = model.build()
    return result, dict(species=SPECIES, source_sha256=SOURCE, changed_slots=list(range(5)), storage=motionstorage.require(result, n))


def main():
    import argparse
    from pathlib import Path
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', default='build/imported-model-edit/edit/253-Tuskmon.MMD')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    rig = json.loads(Path('content/species/253-tuskmon.json').read_text())['model']['skeleton']
    data, report = build(Path(args.source).read_bytes(), rig)
    Path(args.out).write_bytes(data)
    print(args.out, len(data), 'B', report['storage'])


if __name__ == '__main__':
    main()
