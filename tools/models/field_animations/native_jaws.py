"""Mouths for a native-donor binding whose source opened and closed its jaws.

A donor's clips have no jaw work for a mouth that is not its own (and the heads on the hands have no bone at all on
them). The recipe names, for each source jaw bone, the donor bone that carries its piece (a head's jaw bone, a finger
bone of the hand for a hand head) and, for every slot listed, a calm curve for each jaw: `peak` degrees at the
widest, `cycles` openings per loop, `offset` (a fraction of a cycle, so the heads open one after another instead of
together) and `base` (degrees the mouth always hangs open); a jaw given `{"replay": 1.0}` instead plays the
source's own jaw turns of the same clip (stretched over the new clip by phase, the same openings per loop), scaled. The curve is a raised cosine, so the jaw eases out of
and into every turn and never chatters; its length is the clip's own, so the loop closes on the same ticks.

* the jaw turns about the axis the source's own jaw turned about (read from the source's idle, a horizontal one:
  the mouth opens and closes vertically), carried with the donor bone through every pose of the clip;
* it turns about the source jaw's hinge carried onto the fitted piece, and the bone's origin moves to keep the hinge
  fixed, so a piece fitted anywhere on the bone still opens about its hinge.

Nothing else in a clip changes: only the jaw bones' rotation and origin are written.
"""
import copy
import math

import numeric as np
import animsheet
import mmd
import retarget as R
from tools.models.field_animations import animal_refine as A


def _rotvec(matrix):
    angle = math.acos(max(-1.0, min(1.0, (np.trace(matrix) - 1) / 2)))
    axis = np.array([matrix[2, 1] - matrix[1, 2], matrix[0, 2] - matrix[2, 0], matrix[1, 0] - matrix[0, 1]])
    length = np.linalg.norm(axis)
    return axis / length * angle if length > 1e-9 else np.zeros(3)


def _rotation(vector):
    angle = np.linalg.norm(vector)
    if angle < 1e-9:
        return np.eye(3)
    k = vector / angle
    cross = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) * math.cos(angle) + math.sin(angle) * cross + (1 - math.cos(angle)) * np.outer(k, k)


def _relative(sk, pose, bone):
    world = R.world_rots(sk, pose)
    return np.array(world[sk[bone][1]]).T @ np.array(world[bone])


def source_axes(mesh, skeleton, bind_pose, bones):
    """{source bone: unit axis (in the bone's own frame) the source's jaw turned about, read at its widest in the idle}"""
    frames = animsheet.slot_frames(mesh, len(skeleton), 0)[0]
    out = {}
    for b in bones:
        rest = _relative(skeleton, bind_pose, b)
        vectors = [_rotvec(rest.T @ _relative(skeleton, f, b)) for f in frames]
        widest = max(vectors, key=lambda v: float(np.linalg.norm(v)))
        out[b] = widest / np.linalg.norm(widest)
    return out


def source_motion(mesh, skeleton, bind_pose, slot, bones):
    """{source bone: [rotation vector of its parent-relative turn away from the bind pose, per tick of the source clip]}"""
    frames = animsheet.slot_frames(mesh, len(skeleton), slot)[0]
    rest = {b: _relative(skeleton, bind_pose, b) for b in bones}
    return {b: [_rotvec(rest[b].T @ _relative(skeleton, f, b)) for f in frames] for b in bones}


def _sample(series, phase):
    ticks = len(series) - 1
    x = (phase % 1.0) * ticks
    i = int(math.floor(x))
    k = x - i
    return series[i] * (1 - k) + series[i + 1] * k


def opening(curve, phase):
    """Degrees of the jaw at `phase` (0..1) of the loop: base + peak * a raised cosine that starts and ends closed."""
    x = phase * curve['cycles'] + curve.get('offset', 0)
    return curve.get('base', 0) + curve['peak'] * (0.5 - 0.5 * math.cos(2 * math.pi * x))


def run_jaws(model, rig, spec, mesh, skeleton, bind_pose, placements):
    """`model` with the jaw bones of the recipe's slots re-posed; returns the built bytes."""
    n = len(rig)
    jaws = {int(k): v for k, v in spec['bones'].items()}
    rest_new = animsheet.slot_frames(model, n, 0)[0][0]
    rest_new[0] = [4096] * 3 + [0] * 6
    rest_world, rest_pos = R.world_rots(rig, rest_new), R.world_pos(rig, rest_new)
    rest_old = R.world_rots(skeleton, bind_pose)
    pos_old = R.world_pos(skeleton, bind_pose)
    axes = source_axes(mesh, skeleton, bind_pose, jaws)
    plan = {}
    for sb, db in jaws.items():
        anchor, transform, destination = placements[sb]
        hinge = (np.array(pos_old[sb]) - anchor) @ transform.T + destination
        plan[sb] = dict(
            bone=db, hinge=hinge, old=np.array(rest_old[sb]), new=np.array(rest_world[db]),
            origin=np.array(rest_pos[db]) if len(rest_pos[db]) == 3 else np.array(rest_pos[db])[:3])
    additions = []
    for slot_key, aliases in spec['slots'].items():
        slot = int(slot_key)
        curves = spec['curves'][slot_key]
        motion = source_motion(mesh, skeleton, bind_pose, slot, jaws)
        frames, loop, events = animsheet.slot_frames(model, n, slot)
        frames = copy.deepcopy(frames)
        ticks = len(frames) - 1
        history = {plan[sb]['bone']: frames[0][plan[sb]['bone']][3:6] for sb in jaws}
        for t in range(ticks):
            pose = frames[t]
            for sb in sorted(jaws, key=lambda b: plan[b]['bone']):
                p = plan[sb]
                db = p['bone']
                curve = curves[str(sb)]
                if 'replay' in curve:
                    delta_old = _rotation(_sample(motion[sb], t / ticks) * curve['replay'])
                else:
                    delta_old = _rotation(axes[sb] * math.radians(opening(curve, t / ticks)))
                delta_world = p['old'] @ delta_old @ p['old'].T          # about the world axes of the bind pose
                rots, mats = R.world_rots(rig, pose), R.world_pos(rig, pose)
                parent = rig[db][1]
                w_parent = np.array(rots[parent])
                w_now = np.array(rots[db])
                origin = np.array(mats[db])[:3]
                parent_origin = np.array(mats[parent])[:3]
                body = w_now @ p['new'].T                                  # how far the body has carried the rest frame
                local_hinge = p['new'].T @ (p['hinge'] - p['origin'])
                hinge_now = origin + w_now @ local_hinge
                turn = body @ delta_world @ body.T                         # the opening, in the world of this tick
                new_origin = hinge_now + turn @ (origin - hinge_now)
                A.set_world(rig, pose, db, turn @ w_now, history)
                local = w_parent.T @ (new_origin - parent_origin)
                pose[db][6:9] = [round(float(v)) for v in local]
        for sb in jaws:
            db = plan[sb]['bone']
            frames[ticks][db][3:9] = frames[0][db][3:9]
        additions.append((slot, frames, loop, events))
        additions += [(alias, frames, loop, events) for alias in aliases]
    return A.finish(model, additions, n, charts=False)
