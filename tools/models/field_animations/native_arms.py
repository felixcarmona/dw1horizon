"""Run arms for a native-donor binding whose arms are heavier than the donor's.

The donor's run swings its thin arms close to the body; on a bulky armoured body that reads as arms glued to the
torso. For the slots the recipe names, the shoulder and the forearm (with the claws, which are rigid with it) are
re-posed on every tick of the clip:

* the shoulder keeps its idle hang relative to the torso, tipped outward by `out` degrees and pumped front to back
  by `pump` degrees, in opposition to the leg on its side (the arm goes forward with the opposite foot);
* the forearm follows the shoulder, bent forward by `bend` degrees plus up to `bend_swing` more as the arm comes
  forward, `lag` ticks late, so the elbow and the claws arrive after the shoulder (follow-through);
* the whole shoulder pump is raised by `lift` degrees so the claw tips clear the floor.

A slot may carry its own numbers (`per_slot`), its aliases (`alias`).
The clip's period is the clip's own, so the loop closes; legs, tail, head, root travel and every other slot are
untouched.
"""
import copy
import math

import animsheet
import mmd
import retarget as R
from tools.models.field_animations import animal_refine as A

RIGHT = dict(shoulder=5, forearm=6, foot=23, other_foot=26, side=1)
LEFT = dict(shoulder=11, forearm=12, foot=26, other_foot=23, side=-1)


def _matrix(axis, degrees):
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)
    return [[[1, 0, 0], [0, c, -s], [0, s, c]],
            [[c, 0, s], [0, 1, 0], [-s, 0, c]],
            [[c, -s, 0], [s, c, 0], [0, 0, 1]]][axis]


def _smooth(values, ticks, lag):
    """The cyclic series `values` (one per tick) delayed by `lag` ticks, linearly interpolated."""
    out = []
    for t in range(ticks):
        x = (t - lag) % ticks
        i = math.floor(x)
        k = x - i
        out.append(values[i % ticks]*(1-k) + values[(i+1) % ticks]*k)
    return out


def pose_arms(sk, frames, spec):
    """Re-pose the arms of `frames` (one cycle plus its closing frame) in place."""
    ticks = len(frames) - 1
    idle = spec['idle']
    history = {b: frames[0][b][3:6] for b in (5, 6, 11, 12)}  # keeps the angle branches of the source
    foot_z = {b: [R.world_pos(sk, frames[t])[b][2] - R.world_pos(sk, frames[t])[1][2] for t in range(ticks)]
              for b in (23, 26)}
    for arm in (RIGHT, LEFT):
        lead = [(a - b) for a, b in zip(foot_z[arm['other_foot']], foot_z[arm['foot']])]
        mid = (max(lead) + min(lead)) / 2
        half = (max(lead) - min(lead)) / 2
        drive = [(v - mid) / half for v in lead]
        late = _smooth(drive, ticks, spec['lag'])
        forward = [max(0, -v) for v in late]
        for t in range(ticks):
            pose = frames[t]
            rots = R.world_rots(sk, pose)
            torso = rots[sk[arm['shoulder']][1]]
            hang = R.rot_of(idle[arm['shoulder']])
            fore_hang = R.rot_of(idle[arm['forearm']])
            sign = spec['sign']
            swing = _matrix(0, sign * (spec['pump'] * drive[t] + spec['lift']))
            out = _matrix(2, -arm['side'] * spec['out'])
            shoulder = R.m3mul(out, R.m3mul(swing, R.m3mul(torso, hang)))
            A.set_world(sk, pose, arm['shoulder'], shoulder, history)
            elbow = R.m3mul(shoulder, fore_hang)
            bend = _matrix(0, -sign * (spec['bend'] + spec['bend_swing'] * forward[t]))
            A.set_world(sk, pose, arm['forearm'], R.m3mul(bend, elbow), history)
        for bone in (arm['shoulder'], arm['forearm']):
            frames[ticks][bone][3:6] = frames[0][bone][3:6]


def run_arms(model, sk, spec):
    """`model` with the arm program of the recipe's slots rebuilt; returns the built bytes."""
    n = len(sk)
    idle = animsheet.slot_frames(model, n, 0)[0][0]
    additions = []
    for slot in spec['slots']:
        frames, loop, events = animsheet.slot_frames(model, n, slot)
        frames = copy.deepcopy(frames)
        pose_arms(sk, frames, dict(spec, idle=idle, **spec.get('per_slot', {}).get(str(slot), {})))
        additions.append((slot, frames, loop, events))
        # `alias` names the slots that share a slot's program (36 with 4), so they play the re-posed one too
        additions += [(alias, frames, loop, events) for alias in spec.get('alias', {}).get(str(slot), [])]
    return A.finish(model, additions, n, charts=False)
