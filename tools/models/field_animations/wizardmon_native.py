"""Wizardmon (241) on native Angemon's rig and programs, with its cape and hair tail as followers.

native_binding.py (recipe 241) fits the mesh onto Angemon's skeleton and copies every Angemon program. Angemon's
wing bones carry no wings here: the cape hangs from two of them (10 the shoulders, 11 its lower half) and the hair
tail from another (12). Angemon's own wing beat on those bones would flap the cape, so every program replaces their
tracks with followers: each takes part of its driver's turn (the chest for the cape, the head for the hair) a few
ticks late and trails back with the speed the root travels at. The upper arms are held a little further out from the body (ARMS_OUT); every other bone keeps Angemon's track
tick for tick.
"""
import copy
import math

import animsheet
import mmd
import motionstorage
import retarget as R
from motiontailspace import interpolate_pose
from tools.models.field_animations import native_binding

CHEST, HEAD = 2, 3
FIELD = (0, 1, 2, 3, 4)  # idle, its variant, walk, condition walk, run
# follower: (driver, lag in ticks, share of the driver's turn, trailing degrees per unit of root speed, most trailing)
FOLLOWERS = {10: (HEAD, 1.0, .8, .15, 6.0),
             11: (CHEST, 2.2, .1, .4, 14.0),
             12: (HEAD, 1.0, .85, .1, 4.0)}
# in the field clips, upper arms held out from the body by these degrees (about the body's forward axis; + lifts toward -x)
ARMS_OUT = {4: -26.0, 7: 18.0}
# the hair tail's root stays where it hangs from the head, whatever the head does
ROOTED = {12: HEAD}


def _rx(degrees):
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def _rz(degrees):
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def arms_out(frames, rig, rest):
    """Each upper arm turned out from the body by ARMS_OUT about the chest's rest forward axis; the forearm and hand
    keep their own turns under it. A fixed turn in the chest's frame, so an arm held still stays one key."""
    rest_rots = R.world_rots(rig, rest)
    turns = {}
    for bone, degrees in ARMS_OUT.items():
        parent = rest_rots[rig[bone][1]]
        turns[bone] = R.m3mul(R.m3t(parent), R.m3mul(_rz(degrees), parent))
    out = copy.deepcopy(frames)
    for pose in out:
        for bone, turn in turns.items():
            local = R.m3mul(turn, R.rot_of(pose[bone]))
            pose[bone][3:6] = [round(v) for v in mmd.matrix_euler(local, pose[bone][3:6])]
    return out


def _sample(frames, loop, t):
    """The pose `t` ticks into the program (fractional; a loop wraps, a one-shot holds its first pose)."""
    if loop is not None:
        period = len(frames) - 1 - loop
        if t < loop:
            t = loop + (t - loop) % period
    t = max(0.0, t)
    i = min(int(t), len(frames) - 2)
    return interpolate_pose(frames[i], frames[i + 1], round((t - i) * 4096)) if len(frames) > 1 else frames[0]


def _speeds(frames):
    """Root speed per tick in the ground plane, averaged over three ticks."""
    raw = [0.0] + [math.dist((a[0][6], a[0][8]), (b[0][6], b[0][8])) for a, b in zip(frames, frames[1:])]
    return [sum(raw[max(0, i - 2):i + 1]) / len(raw[max(0, i - 2):i + 1]) for i in range(len(raw))]


def follow(frames, loop, rig, rest):
    rest_rots, rest_pos = R.world_rots(rig, rest), R.world_pos(rig, rest)
    # where each rooted follower hangs, in its anchor's frame
    hang = {b: [sum(rest_rots[a][j][i] * (rest_pos[b][j] - rest_pos[a][j]) for j in range(3)) for i in range(3)]
            for b, a in ROOTED.items()}
    out = copy.deepcopy(frames)
    speeds = _speeds(frames)
    for tick, pose in enumerate(out):
        for bone, (driver, lag, share, trail, most) in FOLLOWERS.items():
            now_rots = R.world_rots(rig, pose)
            late = R.world_rots(rig, _sample(frames, loop, tick - lag))
            turn = R.scale_rot(R.m3mul(late[driver], R.m3t(rest_rots[driver])), share)
            facing = now_rots[0]
            back = R.m3mul(facing, R.m3mul(_rx(min(most, trail * speeds[tick])), R.m3t(facing)))
            world = R.m3mul(back, R.m3mul(turn, rest_rots[bone]))
            parent = rig[bone][1]
            angles = mmd.matrix_euler(R.m3mul(R.m3t(now_rots[parent]), world), pose[bone][3:6])
            pose[bone][3:6] = [round(v) for v in angles]
            if bone in ROOTED:
                positions = R.world_pos(rig, pose)
                anchor = ROOTED[bone]
                at = [positions[anchor][i] + sum(now_rots[anchor][i][j] * hang[bone][j] for j in range(3))
                      for i in range(3)]
                local = [sum(now_rots[parent][j][i] * (at[j] - positions[parent][j]) for j in range(3))
                         for i in range(3)]
                pose[bone][6:9] = [round(v) for v in local]
    return out


def build(data, skeleton):
    bound, proof = native_binding.build(data, skeleton)
    rig = proof['generated_skeleton']
    model = mmd.MMD.parse(bound, len(rig))
    model.type = proof['donor']
    rest = animsheet.slot_frames(model, len(rig), 0)[0][0]
    rest[0] = [4096] * 3 + [0] * 6
    done = {}
    for slot, index in enumerate(model.anims.table):
        if index is None or index in done:
            continue
        frames, loop, events = animsheet.slot_frames(model, len(rig), slot)
        if slot in FIELD:
            frames = arms_out(frames, rig, rest)
        frames = follow(frames, loop, rig, rest)
        if loop is not None:
            mmd.close_loop(frames, loop)
        frames = [[[round(v) for v in channels] for channels in pose] for pose in frames]
        done[index] = mmd.encode_anim(frames, len(rig), loop, events, tol=0, repeats=False)
    for index, animation in done.items():
        model.anims.anims[index] = animation
        animation.tail = b''
    output = model.build()
    storage = motionstorage.require(output, len(rig))
    proof.update(output_sha256=native_binding.digest(output), storage=storage,
                 followers={str(b): dict(driver=d, lag=lag, share=s, trail=t, most=m)
                            for b, (d, lag, s, t, m) in FOLLOWERS.items()})
    return output, proof
