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
import retarget
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


def _smooth(samples, frames, passes):
    """Round off a clip that keys every second tick: `passes` times a cyclic [1, 2, 1] / 4 filter over each bone's rotation
    and translation channels (an angle is unwrapped first, so it never spins the long way) and over the root's travel
    per tick (the total travel stays). The loop stays closed: the last tick is the first."""
    ticks = len(samples) - 1
    def cyclic(values):
        for _ in range(passes):
            values = [(values[i - 1] + 2 * values[i] + values[(i + 1) % ticks]) / 4 for i in range(ticks)]
        return values
    for bone in range(1, len(samples[0])):
        for c in range(3, 9):
            raw = [samples[t][bone][c] for t in range(ticks)]
            near = [raw[0]]
            for v in raw[1:]:
                near.append(v - 4096 * round((v - near[-1]) / 4096) if c < 6 else v)
            for t, v in enumerate(cyclic(near)):
                samples[t][bone][c] = int(round(v))
            samples[ticks][bone][c] = samples[0][bone][c]
    steps = [frames[min(t * (len(frames) - 1) // ticks, len(frames) - 2)][0][8] - frames[min(t * (len(frames) - 1) // ticks, len(frames) - 2) + 1][0][8]
             for t in range(ticks)]
    total = samples[0][0][8] - samples[ticks][0][8]
    steps = cyclic(steps)
    scale = total / sum(steps)
    z = samples[0][0][8]
    for t in range(ticks + 1):
        samples[t][0][8] = int(round(z))
        if t < ticks:
            z -= steps[t] * scale


def _matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _transpose(m):
    return [list(r) for r in zip(*m)]


def _rigid_inverse(m):
    rot = [[m[j][i] for j in range(3)] for i in range(3)]
    return [rot[i] + [-sum(rot[i][j] * m[j][3] for j in range(3))] for i in range(3)] + [[0, 0, 0, 1]]


def _local_matrix(joint):
    rot = mmd.rot_matrix(*joint[3:6])
    return [rot[i] + [joint[6 + i]] for i in range(3)] + [[0, 0, 0, 1]]


def _apply(rot, v):
    return [sum(rot[i][j] * v[j] for j in range(3)) for i in range(3)]


def _length(v):
    return sum(x * x for x in v) ** .5


def _reach(joint, rot_base, to_mid, rot_mid, to_end, target):
    """A limb's two bones reaching a point: the world rotations of its base and middle bone (their wanted rotations
    swung the least) that put the end joint, `to_end` from the middle joint (itself `to_mid` from the base joint, both
    offsets in their own bone's frame), on `target` or as near as the bone lengths allow, the middle joint on the side
    the wanted rotations put it."""
    upper, lower = _length(to_mid), _length(to_end)
    reach = [t - j for t, j in zip(target, joint)]
    distance = _length(reach)
    clamped = min(max(distance, abs(upper - lower) + 1), upper + lower - 1)
    axis = [r / distance for r in reach]
    along = (upper * upper - lower * lower + clamped * clamped) / (2 * clamped)
    side = _apply(rot_base, to_mid)
    side = [x - sum(a * y for a, y in zip(axis, side)) * a1 for x, a1 in zip(side, axis)]
    side = [x / (_length(side) or 1) for x in side]
    height = max(upper * upper - along * along, 0) ** .5
    knee = [axis[i] * along + side[i] * height for i in range(3)]
    foot = [axis[i] * clamped for i in range(3)]
    rot_base = _matmul(retarget.swing(_apply(rot_base, to_mid), knee), rot_base)
    rot_mid = _matmul(retarget.swing(_apply(rot_mid, to_end), [f - k for f, k in zip(foot, knee)]), rot_mid)
    return rot_base, rot_mid


def _equivalent(angles, near):
    """The same rotation written the other way round (rx + half a turn, ry mirrored, rz + half a turn), each angle
    brought to the whole turn nearest `near`."""
    other = [angles[0] + 2048, 2048 - angles[1], angles[2] + 2048]
    return [a - 4096 * round((a - n) / 4096) for a, n in zip(other, near)]


def _close_euler(poses):
    """A looping bone ends on the rotation it began with, but following the rotation tick by tick can leave it written
    the other way round (the middle angle crossing a quarter turn). Where that happened the rows from one tick on are
    written the other way round so the last row is the first; the tick is the one whose in-between frames (the engine
    blends the angles) stay nearest the turn between its two ticks."""
    first, last = poses[0], poses[-1]
    assert retarget.axis_angle(_matmul(_transpose(mmd.rot_matrix(*first[3:6])), mmd.rot_matrix(*last[3:6])))[1] <= .02, \
        'the loop does not close'
    if all(abs(u - v) <= 2 for u, v in zip(first[3:6], last[3:6])):
        last[3:6] = first[3:6]
        return
    flipped = [list(first[3:6])]
    for pose in reversed(poses[1:-1]):
        flipped.insert(0, _equivalent(pose[3:6], flipped[0]))
    flipped.insert(0, None)
    assert all(abs(u - v) <= 2 for u, v in zip(_equivalent(last[3:6], first[3:6]), first[3:6])), 'the loop does not come back'

    def blend_error(t):
        a, b = poses[t][3:6], flipped[t + 1]
        ra, rb = mmd.rot_matrix(*a), mmd.rot_matrix(*poses[t + 1][3:6])
        turn = _matmul(_transpose(ra), rb)
        return max(retarget.axis_angle(_matmul(_transpose(mmd.rot_matrix(*[x + (y - x) * w for x, y in zip(a, b)])),
                                               _matmul(ra, retarget.scale_rot(turn, w))))[1] for w in (1 / 3, 2 / 3))
    cut = min(range(len(poses) - 1), key=blend_error)
    for t in range(cut + 1, len(poses) - 1):
        poses[t][3:6] = flipped[t]
    last[3:6] = first[3:6]


def _original_run(old, n, spec, source):
    """The species' own run for the bound rig: (poses, events) in place of the donor's. `source` is (the source model's
    bytes, its skeleton); spec['map'] sends each source bone to its donor bone and spec['bind_slot'] is the pose both
    rigs were fitted in. Every tick, a source bone's world motion since that pose is applied to its donor bone's fitted
    world placement (the pieces were fitted there), and the donor bones are solved root to leaves: each mapped bone gets
    the local rotation that gives that world rotation, and a bone whose parent has no source bone (the waist and the
    pelvis, which hang from the height bone) the local offset that puts its joint where that motion took it. A limb
    (spec['limbs'], three donor bones each) keeps its end bone's world rotation and has the donor's own bone lengths
    reach the end joint the motion took, bending to the side the original's rotations bent it. The root keeps the
    source's rotation and travel. Donor bones with no source bone (and the second of two source bones on one donor
    bone) hold their fitted pose under their parent."""
    data, skeleton = source
    sid = 9100 + len(skeleton)
    mmd.exe().add_type(sid, skeleton)
    model = mmd.MMD.parse(data, len(skeleton))
    model.type = sid
    run, loop, run_events = animsheet.slot_frames(model, len(skeleton), spec['slot'])
    assert loop == 0, 'the original run must loop whole'
    held = animsheet.slot_frames(old, n, 0)[0][0]
    rest_source = animsheet.slot_frames(model, len(skeleton), spec['bind_slot'])[0][0]
    held[0] = rest_source[0] = [4096] * 3 + [0] * 6
    assert all(v[:3] == [4096] * 3 for v in held + rest_source), 'a scaled bone cannot be retargeted by its world'
    source_rest = [_rigid_inverse(m) for m in mmd.bone_matrices(model, rest_source)]
    donor_rest = mmd.bone_matrices(old, held)
    parent = [up for _, up in mmd.exe().skeleton[old.type]]
    pairs = {}
    for sb, db in sorted((int(k), v) for k, v in spec['map'].items()):
        pairs.setdefault(db, sb)
    limbs = {base: (mid, end) for base, mid, end in spec['limbs']}
    out, history = [], {}
    for pose in run:
        posed = [[4096] * 3 + v[3:6] + ([0, 0, 0] if b == 0 else v[6:9]) for b, v in enumerate(pose)]
        motion = [mmd.mat_mul(w, inv) for w, inv in zip(mmd.bone_matrices(model, posed), source_rest)]
        driver = {}
        for db in range(n):          # the source bone whose motion carries each donor bone: its own, or its parent's
            driver[db] = pairs.get(db, driver.get(parent[db]) if db else None)
        ideal = [mmd.mat_mul(motion[driver[db]], donor_rest[db]) if driver[db] is not None else donor_rest[db] for db in range(n)]
        row, world, turned = [], [], {}
        for db in range(n):
            joint = list(held[db])
            if db == 0:
                joint[3:9] = pose[0][3:9]
            elif db in pairs or db in turned:
                above = world[parent[db]]
                if parent[db] not in pairs and parent[db] != 0:
                    joint[6:9] = [round(mmd.mat_mul(_rigid_inverse(above), ideal[db])[i][3]) for i in range(3)]
                wanted = turned.get(db) or [r[:3] for r in ideal[db][:3]]
                if db in limbs:
                    mid, end = limbs[db]
                    position = [mmd.mat_mul(above, _local_matrix(joint))[i][3] for i in range(3)]
                    wanted, turned[mid] = _reach(position, wanted, held[mid][6:9], [r[:3] for r in ideal[mid][:3]],
                                                 held[end][6:9], [ideal[end][i][3] for i in range(3)])
                set_rotation([None] * db + [joint], db, _matmul(_transpose([r[:3] for r in above[:3]]), wanted), history)
            row.append(joint)
            local = _local_matrix(joint[:6] + [0, 0, 0] if db == 0 else joint)      # the travel is not in the pose's world
            world.append(mmd.mat_mul(world[parent[db]], local) if db else local)
        out.append(row)
    for bone in range(1, n):
        _close_euler([row[bone] for row in out])
    return out, run_events

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


def _clear_floor(model, skeleton, samples, limit, tight=False):
    """Sampling a foot's arc less often cuts the chord through the ground: raise the root by a smooth cyclic bump."""
    floors = _floors(model, skeleton, samples)
    ticks = len(floors)
    need = [max(0, f - limit) for f in floors]
    carried = [b for b, (_, parent) in enumerate(skeleton) if b and parent == 0]
    for t, pose in enumerate(samples[:-1]):
        bump = ceil(need[t]) if tight else ceil(max(need[j] - 0.8 * min(abs(t - j), ticks - abs(t - j)) ** 2 for j in range(ticks)))
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


def _author(old, skeleton, slot, spec, feet, source=None):
    n = len(skeleton)
    frames, loop, events = animsheet.slot_frames(old, n, spec['from'])
    assert loop == 0, (slot, 'a pace source must loop whole')
    if 'original_run' in spec:
        frames, events = _original_run(old, n, dict(spec['original_run'], slot=slot), source)
    source_ticks = len(frames) - 1
    drift = [frames[-1][0][c] - frames[0][0][c] for c in (6, 7)]
    assert all(abs(d) <= 0.02 * abs(frames[-1][0][8] - frames[0][0][8]) for d in drift), (slot, 'source drifts', drift)
    frames = [[list(bone) for bone in pose] for pose in frames]
    for t, pose in enumerate(frames):
        for c, d in zip((6, 7), drift):
            pose[0][c] -= d * t / source_ticks
    ticks, speed = spec['ticks'], spec['speed']
    assert speed >= SPEED_FLOOR.get(slot, 0), (slot, speed)      # an idle stands: no floor
    if spec['from'] == slot and ticks == source_ticks and 'original_run' not in spec and 'smooth' not in spec and 'lift' not in spec:      # same clock: poses exact, only the travel changes
        return _forward(old.anims.anims[old.anims.table[slot]], -round(speed * ticks), ticks), dict(
            slot=slot, source_slot=slot, source_ticks=ticks, ticks=ticks, units_per_tick=round(speed * ticks) / ticks,
            slip_mean=_checked_slip(old, frames, feet, speed, spec), floor='exact')
    samples = _root_channels(frames, ticks, speed)
    if spec.get('close'):       # a donor loop that closes within a unit or two: the last pose is the first, so the units do not add up loop after loop
        for bone, first in enumerate(samples[0][1:], 1):
            samples[-1][bone] = list(first)
    if spec.get('smooth'):
        _smooth(samples, frames, spec['smooth'])
    for pose in samples:        # a row's `lift`: the whole clip held that much higher (a rig whose native crouch sinks the soles)
        for bone, (_, parent) in enumerate(skeleton):
            if bone and parent == 0:
                pose[bone][7] -= spec.get('lift', 0)
    if 'posture' in spec:
        _keep_posture(old, samples, animsheet.slot_frames(old, n, spec['posture']['from'])[0], spec['posture'])
    before = max(_floors(old, skeleton, frames))
    limit = FLOOR_MARGIN if 'original_run' in spec else max(before, FLOOR_MARGIN)    # an original run is held to the ground rule
    tight = 'original_run' in spec     # the original's feet keep its timing: lift each tick by what it needs, no more
    raised = _clear_floor(old, skeleton, samples, limit, tight)
    raised += _clear_floor(old, skeleton, samples, limit, tight)
    for _ in range(6 if tight else 0):          # a tick's thirds between two lifts: what is left is lifted again
        if max(_floors(old, skeleton, samples)) <= limit:
            break
        raised += _clear_floor(old, skeleton, samples, limit, tight)
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
    mean, worst = slip(old, first_loop, feet) if speed else (0, 0)       # slip is a share of the travel: an idle has none
    assert mean <= spec['slip'][0] and worst <= spec['slip'][1], (slot, mean, worst, spec['slip'])
    after = max(_floors(old, skeleton, first_loop))
    assert after <= limit + FLOOR_MARGIN, (slot, 'floor', before, after)
    return animation, dict(slot=slot, source_slot=spec['from'], source_ticks=source_ticks, ticks=ticks,
                           units_per_tick=measured, slip_mean=mean, slip_worst=worst, floor_source=before, floor=after, raised=raised,
                           events=len(events))


def retime(data, skeleton, sid, slots, source=None):
    """(bytes, checks, changed slots, storage) of `data` with the pinned `slots` rebuilt from the model's own looping
    clips (pace's manifest rows); every other program, the mesh and the skeleton stay exact. `skeleton` is the rig the
    bytes were built on, registered under `sid` for the checks."""
    if sid >= len(mmd.exe().skeleton):          # a scratch type for a rig the executable does not know
        mmd.exe().add_type(sid, skeleton)
    mmd.exe().skeleton[sid] = skeleton
    mmd.exe().bone_count[sid] = len(skeleton)
    old = mmd.MMD.parse(data, len(skeleton))
    old.type = sid
    new = copy.deepcopy(old)
    feet = _feet(old, skeleton)
    checks = []
    for slot, spec in sorted(slots.items(), key=lambda row: int(row[0])):
        animation, check = _author(old, skeleton, int(slot), spec, feet, source)
        new.anims.table[int(slot)] = len(new.anims.anims)
        new.anims.anims.append(animation)
        for alias in spec.get('alias', ()):     # slots that played the same program follow the rebuilt one
            assert old.anims.table[alias] == old.anims.table[int(slot)], (alias, slot)
            new.anims.table[alias] = new.anims.table[int(slot)]
        checks.append(check)
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = mmd.MMD.parse(result, len(skeleton))
    assert old.tmd.build() == actual.tmd.build()
    changed = sorted({int(slot) for slot in slots} | {a for spec in slots.values() for a in spec.get('alias', ())})
    assert changed_programs(old, actual) == changed
    storage = motionstorage.require(result, len(skeleton))
    return result, checks, changed, storage


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
    result, checks, changed, storage = retime(data, skeleton, sid, profile['slots'])
    following = None
    if profile.get('after_generator'):
        after = importlib.import_module(profile['after_generator'])
        result, following = after.build(result, skeleton, **({'species': sid} if getattr(after, 'TAKES_SPECIES', False) else {}))
        storage = following['storage']
    return result, dict(species=sid, source_sha256=digest, output_sha256=hashlib.sha256(result).hexdigest(),
                        preceding_recipe=previous, following_recipe=following, checks=checks, storage=storage, changed_slots=changed,
                        mesh_skeleton_other_slots_exact=True)
