"""Field pace: bring a partner's walk, condition walk and run into the native ranges.

The game's own species derive their condition walk by playing the walk 1.5 times
slower at 2/3 of its speed, so a gait keeps its look when it is retimed. This pass
does the same for the imported species that fall behind: a pinned slot is rebuilt
from one of the model's own looping field clips, played over a new number of ticks,
with an even forward travel. Every other program, the mesh and the skeleton stay
exact. The preceding field recipe, where present, still owns the performance.
A row's after_generator runs on the paced model for a species whose carriage needs its own layer.

A retimed foot sweeps the same path in less time, so cadence and travel are chosen
together: the build refuses a clip that leaves the speed range, slips more than its
manifest row allows, lowers the mesh under its source, drifts over nine loops or
leaves the storage budget. The manifest is content/models/imports/pace.json.
"""
import copy
import hashlib
import importlib
import json
from math import ceil, cos, pi
from pathlib import Path

import numeric as np
import animsheet
import mmd
import motioncyclelayer
import motionstorage
from motiondiscidentity import changed_programs
from motiontailspace import interpolate_pose
from tools.models.field_animations.gliding import _forward
from tools.models.field_animations.war_greymon import set_rotation

MANIFEST = Path(__file__).resolve().parents[3] / 'content/models/imports/pace.json'
WALK, CONDITION, RUN = 2, 3, 4
SPEED_FLOOR = {WALK: 15, CONDITION: 9.5, RUN: 35}
FLOOR_MARGIN = 1.5      # the ground rule, and what integer rounding may add to a clip's own floor


def _root_channels(frames, ticks, speed):
    """The pose of tick t of a loop of `ticks`, resampled from frames (one loop plus its closing frame)."""
    n = len(frames) - 1
    out = []
    for t in range(ticks + 1):
        i, rest = divmod(t * n * 4096 // ticks, 4096)
        pose = list(map(list, frames[i])) if not rest else interpolate_pose(frames[i], frames[i + 1], rest)
        pose[0][8] = int(frames[0][0][8]) - round(speed * t)
        out.append([[int(value) for value in bone] for bone in pose])
    return out


def _loosen(pose, phase, loose):
    """Acting over the stride, in degrees. Phase 0 has the leg on the arm's side forward. Arms oppose their legs,
    elbows arrive late, the torso turns against the hips and rolls over the supporting foot, the head follows last."""
    wave = lambda delay, rate=1: cos(2 * pi * rate * (phase - loose['phase'] - delay)) * 4096 / 360
    body, head = loose['body'], loose['head']
    for (arm, elbow), side in zip(loose['arms'], (1, -1)):
        pose[arm][3] += round(side * loose.get('swing', 0) * wave(0))
        pose[elbow][3] += round(side * loose.get('elbow', 0) * wave(0.12))
    pose[body][3] += round(loose.get('lean', 0) * 4096 / 360)
    pose[body][4] -= round(loose.get('yaw', 0) * wave(0))
    pose[body][5] += round(loose.get('roll', 0) * wave(0.25))
    pose[head][3] += round(loose.get('nod', 0) * wave(0.1, 2))
    pose[head][5] -= round(loose.get('sway', 0) * wave(0.35))


def _keep_posture(model, samples, upright, posture):
    """Legs from one clip, everything else from another: every bone above the legs plays the upright clip and each
    hip is solved to keep its world rotation, so the stride survives while the face and the arms stay where they were."""
    ticks, n = len(samples) - 1, len(upright) - 1
    for t, pose in enumerate(samples):
        i, rest = divmod((t % ticks) * n * 4096 // ticks, 4096)
        target = interpolate_pose(upright[i], upright[i + 1], rest)
        still = [list(bone) for bone in pose]
        still[0] = still[0][:6] + [0, 0, 0]
        hips = {hip: np.array(mmd.bone_matrices(model, still))[hip, :3, :3] for hip in posture['hips']}
        pose[0][3:6] = target[0][3:6]
        for bone in posture['upper']:
            pose[bone] = list(target[bone])
        if 'loose' in posture:
            _loosen(pose, t / ticks, posture['loose'])
        still = [list(bone) for bone in pose]
        still[0] = still[0][:6] + [0, 0, 0]
        world = np.array(mmd.bone_matrices(model, still))
        for hip, wanted in hips.items():
            set_rotation(pose, hip, world[posture['carrier'], :3, :3].T @ wanted, {})


def _retimed_events(events, n, ticks):
    return [(min(ticks - 1, k * ticks // n), kind, c) for k, kind, c in events]


def _floors(model, skeleton, frames):
    """Lowest mesh point of each tick of a clip, its 60 fps thirds included (y grows downwards)."""
    verts = {b: np.array(model.tmd.obj_verts(o))[:, :3] for b, (o, _) in enumerate(skeleton) if o >= 0}
    floors = []
    for t in range(len(frames) - 1):
        worst = -1e9
        for alpha in (0, 1365, 2730):
            pose = interpolate_pose(frames[t], frames[t + 1], alpha)
            height = pose[0][7]
            pose[0] = pose[0][:6] + [0, 0, 0]
            world = np.array(mmd.bone_matrices(model, pose))
            for b, v in verts.items():
                worst = max(worst, float((v @ world[b, :3, :3].T + world[b, :3, 3])[:, 1].max()) + height)
        floors.append(worst)
    return floors


def _clear_floor(model, skeleton, samples, limit):
    """Sampling a foot's arc less often cuts the chord through the ground: raise the root by a smooth cyclic bump."""
    floors = _floors(model, skeleton, samples)
    ticks = len(floors)
    need = [max(0, f - limit) for f in floors]
    carried = [b for b, (_, parent) in enumerate(skeleton) if b and parent == 0]
    for t, pose in enumerate(samples[:-1]):
        bump = ceil(max(need[j] - 0.8 * min(abs(t - j), ticks - abs(t - j)) ** 2 for j in range(ticks)))
        for b in carried:                      # root translation is relative: a loop-wide offset of it would be lost
            pose[b][7] -= bump
    for b in carried:
        samples[-1][b][7] = samples[0][b][7]
    return max(need)


def _feet(model, skeleton):
    rest = [list(v) for v in animsheet.slot_frames(model, len(skeleton), 0)[0][0]]
    rest[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
    matrices = mmd.bone_matrices(model, rest)
    return sorted(range(1, len(skeleton)), key=lambda b: -matrices[b][1][3])[:2]


def slip(model, frames, feet):
    """animstudio.metrics: stance foot speed over the ground as a percentage of the root's, as (mean, worst)."""
    n = len(frames)
    speed = abs(frames[-1][0][8] - frames[0][0][8]) / (n - 1)
    mean, worst = 0, 0
    for b in feet:
        ys, zs = [], []
        for pose in frames:
            still = [list(v) for v in pose]
            still[0] = [4096, 4096, 4096] + still[0][3:6] + [0, 0, 0]
            matrix = mmd.bone_matrices(model, still)[b]
            ys.append(matrix[1][3])
            zs.append(matrix[2][3] + pose[0][8])
        low, high = max(ys), min(ys)
        stance = [t for t in range(n - 1) if ys[t] > low - 0.25 * (low - high)]
        rates = [abs(zs[t + 1] - zs[t]) / speed * 100 for t in stance]
        if rates:
            mean, worst = max(mean, sum(rates) / len(rates)), max(worst, max(rates))
    return mean, worst


def _checked_slip(model, frames, feet, speed, spec):
    moved = [[list(bone) for bone in pose] for pose in frames]
    for t, pose in enumerate(moved):
        pose[0][8] = frames[0][0][8] - speed * t
    mean, worst = slip(model, moved, feet)
    assert mean <= spec['slip'][0] and worst <= spec['slip'][1], (spec, mean, worst)
    return mean


def _author(old, skeleton, slot, spec, feet):
    n = len(skeleton)
    frames, loop, events = animsheet.slot_frames(old, n, spec['from'])
    assert loop == 0, (slot, 'a pace source must loop whole')
    source_ticks = len(frames) - 1
    drift = [frames[-1][0][c] - frames[0][0][c] for c in (6, 7)]
    assert all(abs(d) <= 0.02 * abs(frames[-1][0][8] - frames[0][0][8]) for d in drift), (slot, 'source drifts', drift)
    frames = [[list(bone) for bone in pose] for pose in frames]
    for t, pose in enumerate(frames):
        for c, d in zip((6, 7), drift):
            pose[0][c] -= d * t / source_ticks
    ticks, speed = spec['ticks'], spec['speed']
    assert speed >= SPEED_FLOOR[slot], (slot, speed)
    if spec['from'] == slot and ticks == source_ticks:      # same clock: poses exact, only the travel changes
        return _forward(old.anims.anims[old.anims.table[slot]], -round(speed * ticks), ticks), dict(
            slot=slot, source_slot=slot, source_ticks=ticks, ticks=ticks, units_per_tick=round(speed * ticks) / ticks,
            slip_mean=_checked_slip(old, frames, feet, speed, spec), floor='exact')
    samples = _root_channels(frames, ticks, speed)
    if 'posture' in spec:
        _keep_posture(old, samples, animsheet.slot_frames(old, n, spec['posture']['from'])[0], spec['posture'])
    before = max(_floors(old, skeleton, frames))
    limit = max(before, FLOOR_MARGIN)
    raised = _clear_floor(old, skeleton, samples, limit)
    raised += _clear_floor(old, skeleton, samples, limit)
    animation = mmd.encode_anim(samples, n, loop_sample=0, events=_retimed_events(events, source_ticks, ticks),
                                tol=spec.get('tol', 1))
    player = mmd.AnimPlayer(animation, n, slot)
    played = []
    for tick in range(ticks * 9 + 1):
        assert player.tick()
        pose = [list(v) for v in player.pose]
        pose[0][6:9] = list(player.root)
        played.append(pose)
    start = played[0]
    for tick in range(ticks, ticks * 9 + 1, ticks):
        assert all(abs(a - b) <= 2 for bone, other in zip(start[1:], played[tick][1:]) for a, b in zip(bone, other)), (slot, tick, 'loop drift')
    first_loop = played[:ticks + 1]
    measured = abs(first_loop[-1][0][8] - first_loop[0][0][8]) / ticks
    assert abs(measured - speed) <= 0.5, (slot, measured, speed)
    mean, worst = slip(old, first_loop, feet)
    assert mean <= spec['slip'][0] and worst <= spec['slip'][1], (slot, mean, worst, spec['slip'])
    after = max(_floors(old, skeleton, first_loop))
    assert after <= limit + FLOOR_MARGIN, (slot, 'floor', before, after)
    return animation, dict(slot=slot, source_slot=spec['from'], source_ticks=source_ticks, ticks=ticks,
                           units_per_tick=measured, slip_mean=mean, slip_worst=worst, floor_source=before, floor=after, raised=raised,
                           events=len(events))


def build(data, skeleton):
    profiles = json.loads(MANIFEST.read_text())
    digest = hashlib.sha256(data).hexdigest()
    matches = [(int(sid), row) for sid, row in profiles.items() if row['source_sha256'] == digest]
    if len(matches) != 1:
        raise ValueError('Field pace requires an individually pinned source')
    sid, profile = matches[0]
    if len(skeleton) != profile['bones'] or hashlib.sha256(json.dumps(skeleton).encode()).hexdigest() != profile['skeleton_sha256']:
        raise ValueError('Field pace skeleton differs from its pinned source')
    previous = None
    if profile['base_generator'] == __name__:
        raise ValueError('Field pace cannot follow itself')
    if profile['base_generator']:
        data, previous = importlib.import_module(profile['base_generator']).build(data, skeleton)
    if hashlib.sha256(data).hexdigest() != profile['post_source_sha256']:
        raise ValueError('Preceding field recipe differs from the pinned pace input')
    mmd.exe().skeleton[sid] = skeleton
    mmd.exe().bone_count[sid] = len(skeleton)
    old = mmd.MMD.parse(data, len(skeleton))
    old.type = sid
    new = copy.deepcopy(old)
    feet = _feet(old, skeleton)
    checks = []
    for slot, spec in sorted(profile['slots'].items(), key=lambda row: int(row[0])):
        animation, check = _author(old, skeleton, int(slot), spec, feet)
        new.anims.table[int(slot)] = len(new.anims.anims)
        new.anims.anims.append(animation)
        checks.append(check)
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = mmd.MMD.parse(result, len(skeleton))
    assert old.tmd.build() == actual.tmd.build()
    changed = sorted(int(slot) for slot in profile['slots'])
    assert changed_programs(old, actual) == changed
    storage = motionstorage.require(result, len(skeleton))
    following = None
    if profile.get('after_generator'):
        result, following = importlib.import_module(profile['after_generator']).build(result, skeleton)
        storage = following['storage']
    return result, dict(species=sid, source_sha256=digest, output_sha256=hashlib.sha256(result).hexdigest(),
                        preceding_recipe=previous, following_recipe=following, checks=checks, storage=storage, changed_slots=changed,
                        mesh_skeleton_other_slots_exact=True)
