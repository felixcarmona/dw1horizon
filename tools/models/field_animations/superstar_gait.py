"""SuperStarmon's (244) field clips: Starmon's refined clips on its larger body (field slots 0, 2, 3, 4).

SuperStarmon has Starmon's 20 bones (same order, same parents) at 1.75 times the size, plus fringe bones 20 to 26
(the finger blades under the hands 3 and 6, a plate on the back under the body 1). The imported clips held a boxer's
guard with wide hunched legs, slid 27 to 65 % and ran at 50 units a tick. Its clips are now Starmon's own
(star_gait_refine.py: legs clear of each other and of the body, arms clear of the torso, head carried up, ribbons
hanging and flowing), mapped bone for bone: rotations as they are, every translation (root travel included) times
`SCALE`. Each cycle is stretched in time to `TICKS` so that the root keeps 244's own speeds (about 20, 13.5 and 38
units a tick) with the feet still planted: the stride is longer by the size, the cadence slower by the same.
Sounds move with the footfalls. The blades and the back plate hold their rest orientation.

Idle: Starmon's idle is a guard with the fists up; SuperStarmon stands upright with its arms hanging (`IDLE`).

Offline: `tools/models/edit.py get 244` (before this change) and `get 243` (Starmon's refined clips, after
star_gait_refine), then
`python3 -m tools.models.field_animations.superstar_gait --source 244.MMD --starmon 243.MMD --out AFTER.MMD` and
`edit.py put 244 AFTER.MMD`.
"""
import copy
import hashlib
import math

import animsheet
import mmd
import motionstorage
import numeric as np

from tools.models.field_animations import star_gait_refine as star
from tools.models.field_animations.channels import coalesce, replace_channels

SPECIES = 244
SOURCE = 'eda099f022f5c62aabffe5c833233123012534c03b49c778c2d0232dd809f24b'    # edit.py get 244 before this change
STARMON = '67a8504a372e94e13a1541f491a03a9ded6a83843920823a680bae9a29361cbc'  # edit.py get 243 with Starmon's clips
PARENTS = star.PARENTS + [3, 3, 3, 6, 6, 6, 1]
SCALE = 1.75
BONES = 27
TICKS = {2: 22, 3: 28, 4: 25}      # cycle lengths: 19.5, 13.5 and 37.9 units a tick on the root
FRINGE = range(20, 27)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def frames_of(model, slot, n):
    return animsheet.slot_frames(model, n, slot)[0]


def unwrapped(series):
    out = [series[0]]
    for v in series[1:]:
        d = (v - out[-1] + 2048) % 4096 - 2048
        out.append(out[-1] + d)
    return out


def catmull(p0, p1, p2, p3, u):
    return p1 + .5*u*(p2 - p0 + u*(2*p0 - 5*p1 + 4*p2 - p3 + u*(3*(p1 - p2) + p3 - p0)))


def retime(frames, n):
    """The cycle (first to last frame) played over `n` frames: rotations and body translations by cubic
    interpolation round the loop, root travel linear between the frames."""
    count = len(frames)
    out = [[[0.]*9 for _ in range(len(frames[0]))] for _ in range(n)]
    for b in range(len(frames[0])):
        for c in range(3, 9):
            series = [float(f[b][c]) for f in frames]
            if c in (3, 4, 5):
                series = unwrapped(series)
            for i in range(n):
                x = i*(count - 1)/(n - 1)
                k = min(int(x), count - 2)
                u = x - k
                if b == 0:
                    out[i][b][c] = series[k] + u*(series[k + 1] - series[k])
                    continue
                a = series[(k - 1) % count]
                d = series[(k + 2) % count]
                out[i][b][c] = catmull(a, series[k], series[k + 1], d, u)
        for i in range(n):
            out[i][b][:3] = [4096]*3
    return out


def scaled(frames, rest):
    """Starmon's frames on SuperStarmon's 27 bones: translations times SCALE, fringe bones at rest."""
    out = []
    for f in frames:
        g = [[*bone[:3], *bone[3:6], *(v*SCALE for v in bone[6:9])] for bone in f[:20]]
        g += [copy.deepcopy(rest[b]) for b in FRINGE]
        out.append(g)
    return out


def integral(frames):
    return [[[round(v) for v in bone] for bone in f] for f in frames]


def template(old, n, notes, frames):
    """The animation `old` emptied: its pose is frame 0, its sounds and loop are set again, the root's travel is keyed
    tick by tick. Channels are keyed on it by replace_channels."""
    a = copy.deepcopy(old)
    loop = next(i for i in old.instrs if i['op'] == 'loop_start')
    instrs = [loop]
    for t in range(1, n):
        group = {c: frames[t][0][i] - frames[t - 1][0][i] for c, i in (('tx', 6), ('tz', 8))}
        group = {c: v for c, v in group.items() if v}
        if group:
            instrs.append(dict(op='key', frame=t, bones=[dict(bone=0, div=1, vals=group)]))
    for frame, bank, note in notes:
        instrs.append(dict(op='sound', frame=frame, bank=bank, note=note))
    instrs.append(dict(op='loop_end', frame=n, jump=1))
    instrs.append(dict(op='end'))
    order = {'loop_start': -1, 'end': 10**7}
    instrs.sort(key=lambda i: (order.get(i['op'], i.get('frame', 0)), i['op'] == 'sound'))
    a.instrs = instrs
    a.pose = [[0]*6 for _ in range(26)]
    a.frame_count = n
    return a


# Idle arms, in the body's frame (x to the side of each arm, y down, z forward): the upper arm and the forearm hang
# down and a little forward; the body is wide enough that the fists clear the thighs and each other as they hang
# (checked tick by tick in test_superstarmon_gait).
# `sway` is the breathing: the arm directions move by this much (fractions of a unit vector), the forearm a little
# later than the upper arm, round the 84-tick loop.
IDLE = dict(upper=(.42, .88, .22), lower=(.3, .8, .55), sway=.05, lag=(5, 11))


def neutral_idle(model, frames):
    """Starmon's idle with the arms hanging instead of guarding: legs, body and ribbons are Starmon's."""
    body = star.Body(model)
    ticks = len(frames)
    history = {}
    for t, f in enumerate(frames):
        for shoulder, side in star.RIG['arms']:
            for bone, key, lag in ((shoulder, 'upper', IDLE['lag'][0]), (shoulder + 1, 'lower', IDLE['lag'][1])):
                w = body.world(f)
                x, y, z = IDLE[key]
                phase = 2*math.pi*(t - lag)/ticks
                local = np.array([side*x + IDLE['sway']*math.sin(phase + (side < 0)*math.pi/2), y, z + IDLE['sway']*math.cos(phase)])
                target = w[1, :3, :3] @ (local/np.linalg.norm(local))
                child = bone + 1
                rot = w[bone, :3, :3]
                parent = w[model_parent(bone), :3, :3]
                turned = star.align(rot @ np.array(f[child][6:9], float), target) @ rot
                star.set_rotation(f, bone, parent.T @ turned, history)
    return frames


def model_parent(bone):
    return PARENTS[bone]


def pack(old, frames, notes):
    n = len(frames)
    animation = template(old, n, notes, frames)
    groups = [({(b, c) for b in range(2, BONES) for c in (3, 4, 5)}, 1), ({(b, c) for b in range(2, BONES) for c in (6, 7, 8)}, 1),
              ({(1, c) for c in (3, 4, 6, 7, 8)}, 0), ({(1, 5)}, 0)]
    for channels, tolerance in groups:
        animation = replace_channels(animation, frames, 0, BONES, channels, tolerance=tolerance)
    animation, _ = coalesce(animation)
    return animation


def sounds_of(model, slot):
    a = model.anims.anims[model.anims.table[slot]]
    return [(i['frame'], i['bank'], i['note']) for i in a.instrs if i['op'] == 'sound']


def build(data, skeleton, starmon, idle=neutral_idle):
    if digest(data) != SOURCE or [b[1] for b in skeleton] != PARENTS:
        raise ValueError("SuperStarmon's clips are written over the reviewed import")
    if digest(starmon) != STARMON:
        raise ValueError("SuperStarmon's clips are written over Starmon's refined clips")
    mmd.exe().add_type(SPECIES, skeleton)
    model = mmd.MMD.parse(data, BONES)
    model.type = SPECIES
    donor_rig = [[o, p] for o, p in skeleton[:20]]
    mmd.exe().add_type(943, donor_rig)       # a spare type id for Starmon's 20-bone rig
    donor = mmd.MMD.parse(starmon, 20)
    donor.type = 943
    rest = frames_of(model, 33, BONES)[0]
    new = {}
    for slot in (0, 2, 3, 4):
        source = frames_of(donor, slot, 20)
        frames = scaled(source, rest)
        n = len(frames)
        notes = []
        if slot in TICKS:
            n = TICKS[slot]
            frames = retime(frames, n)
            notes = [(round(f*(n - 1)/(len(source) - 1)), b, nt) for f, b, nt in sounds_of(donor, slot)]
            mine = sounds_of(model, slot)
            notes = [(f, b, mine[0][2] if mine else nt) for f, b, nt in notes]
        if slot == 0 and idle is not None:
            frames = idle(model, frames)
        frames = integral(frames)
        new[slot] = pack(model.anims.anims[model.anims.table[slot]], frames, notes)
    for slot, animation in new.items():
        old = model.anims.table[slot]
        model.anims.anims.append(animation)
        for i, index in enumerate(model.anims.table):
            if index == old:
                model.anims.table[i] = len(model.anims.anims) - 1
    used = sorted({i for i in model.anims.table if i is not None})
    renumber = {old: n for n, old in enumerate(used)}
    model.anims.anims = [model.anims.anims[i] for i in used]
    model.anims.table = [None if i is None else renumber[i] for i in model.anims.table]
    result = model.build()
    return result, dict(species=SPECIES, source_sha256=SOURCE, changed_slots=sorted(new), storage=motionstorage.require(result, BONES))


def main():
    import argparse
    import json
    from pathlib import Path
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', required=True)
    ap.add_argument('--starmon', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    rig = json.loads(Path('content/species/244-superstarmon.json').read_text())['model']['skeleton']
    data, report = build(Path(args.source).read_bytes(), rig, Path(args.starmon).read_bytes())
    Path(args.out).write_bytes(data)
    print(args.out, len(data), 'B', report['storage'])


if __name__ == '__main__':
    main()
