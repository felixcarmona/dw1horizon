#!/usr/bin/env python3
"""Reviewed rooted steps, with native upper acting retained.

MegaKabuterimon's imported ankles tip its long claws through the ground. Keep
the original clip timing, root, body rotations and upper performance; solve its
mapped legs around planted footprints and retime its original footstep sound.
This is an explicit recipe for the pinned source, not an automatic import pass.
"""
import copy
import hashlib
import math

import numeric as np

import animsheet
import mmd
import motioncyclelayer
import motionsecondary
import motionstorage
from tools.models.field_animations.articulation import replace_channels
from motiondiscidentity import changed_programs
from tools.models.field_animations.war_greymon import rotation, set_rotation

SOURCE = '6a38b5781b4efdda461095f801f96f5d04854c6614f2ea5b241cfb3964b9fc78'
CHAINS = [(17, 18, 19), (20, 21, 22)]
SLOTS = [2, 3, 4]


def _pack(model):
    for anim in model.anims.anims:
        anim.tail = b''
    model.anims.anims, model.anims.table = motioncyclelayer.share_identical_streams(
        model.anims.anims, model.anims.table)
    return model.build()


def _world(model, pose):
    pose = copy.deepcopy(pose)
    pose[0] = [4096] * 3 + [0] * 6
    return np.array(mmd.bone_matrices(model, pose))


def _feet(model, skel):
    return {foot: np.array(model.tmd.obj_verts(skel[foot][0]))[:, :3]
            for _, _, foot in CHAINS}


def _planted_goals(frames, world, rest_world, slot):
    duration = len(frames) - 1
    root = [f[0][8] for f in frames]
    total = root[-1] - root[0]
    period = 10 if slot == 4 else 20
    contact = period * {2: .50, 3: .50, 4: .30}[slot]
    lift = {2: 25, 3: 16, 4: 40}[slot]
    rock = 5 if slot == 2 else 8
    goals, lifts = {}, []

    def at(t):
        cycle = math.floor(t / duration)
        phase = t - cycle * duration
        i = min(int(phase), duration - 1)
        q = phase - i
        return cycle*total + root[i]*(1-q) + root[i+1]*q - root[0]

    def velocity(t):
        return at(t+.001) - at(t)

    for side, (hip, _, foot) in enumerate(CHAINS):
        center = float(np.mean(world[:-1, hip, 2, 3]))
        offset = side * period / 2
        zs, ups, pitches = [], [], []
        for tick in range(len(frames)):
            start = math.floor((tick+offset)/period)*period - offset
            phase = tick - start
            travel = at(start) - at(start+contact)
            next_travel = at(start+period) - at(start+period+contact)
            if phase <= contact:
                # The ankle's Z plus accumulated root Z stays constant.
                z = center - travel/2 - (at(tick)-at(start))
                up = 0.
                pitch = -rock * math.cos(math.pi*phase/contact)
            else:
                span = period - contact
                q = (phase-contact)/span
                a, b = center+travel/2, center-next_travel/2
                v0 = -velocity(start+contact)/.001
                v1 = -velocity(start+period)/.001
                z = ((2*q**3-3*q*q+1)*a + (q**3-2*q*q+q)*span*v0 +
                     (-2*q**3+3*q*q)*b + (q**3-q*q)*span*v1)
                up = lift * math.sin(math.pi*q)**2
                pitch = rock * math.cos(math.pi*q)
            zs.append(z)
            ups.append(up)
            pitches.append(pitch)
        goals[foot] = (np.array([rest_world[foot, 0, 3] - f[0][6] + frames[0][0][6] +
                                      i/duration*(frames[-1][0][6]-frames[0][0][6])
                                      for i, f in enumerate(frames)]),
                       np.array(zs), np.array(ups), np.array(pitches))
        lifts.append(ups)
    return goals, np.min(np.array(lifts), axis=0)


def _support(old, skel):
    new = copy.deepcopy(old)
    n = len(skel)
    rest = animsheet.slot_frames(old, n, 33)[0][0]
    rest_world = _world(old, rest)
    # Private33 stretches the claws to 150% along Z. It is an orientation
    # reference, not a rotation matrix until those column scales are removed.
    for _, _, foot in CHAINS:
        r = rest_world[foot, :3, :3]
        r /= np.linalg.norm(r, axis=0)
        assert np.max(np.abs(r.T @ r - np.eye(3))) < 1e-6
    vertices = _feet(old, skel)
    channels = {(1, 7)} | {(bone, channel) for chain in CHAINS
                           for bone in chain for channel in [3, 4, 5]}
    checks = []
    for slot in SLOTS:
        frames, loop, _ = animsheet.slot_frames(old, n, slot)
        assert loop == 0 and len(frames) == 21
        world = np.array([_world(old, frame) for frame in frames])
        goals, rotations, bounds = {}, {}, []
        planted, flight = _planted_goals(frames, world, rest_world, slot)
        for hip, knee, foot in CHAINS:
            gx, gz, up, pitches = planted[foot]
            r = np.array([rotation([pitch, 0, 0]) @ rest_world[foot, :3, :3]
                          for pitch in pitches])
            sole = np.array([float((vertices[foot] @ rr.T)[:, 1].max()) for rr in r])
            goal = world[:, foot, :3, 3].copy()
            goal[:, 0] = gx
            goal[:, 1] = -sole - up
            goal[:, 2] = gz
            goals[foot], rotations[foot] = goal, r
            for i, frame in enumerate(frames):
                h = world[i, hip, :3, 3]
                length = (np.linalg.norm(frame[knee][6:9]) +
                          np.linalg.norm(frame[foot][6:9]))
                dxz = np.sum((goal[i, [0, 2]] - h[[0, 2]]) ** 2)
                assert dxz < (length - 1) ** 2, (slot, i, 'horizontal reach')
                vertical = math.sqrt(max(0, (length - 1) ** 2 - dxz))
                bounds.append((i, goal[i, 1] - h[1] - vertical,
                               goal[i, 1] - h[1] + vertical))
        body_y = []
        for i in range(len(frames)):
            low = max(b[1] for b in bounds if b[0] == i)
            high = min(b[2] for b in bounds if b[0] == i)
            # Include the whole shell, head and arms, not only the soles.
            upper_max = max(float((np.array(old.tmd.obj_verts(obj))[:, :3] @
                                   world[i, bone, :3, :3].T +
                                   world[i, bone, :3, 3])[:, 1].max())
                            for bone, (obj, _) in enumerate(skel)
                            if obj >= 0 and bone <= 16)
            high = min(high, -upper_max - 2)
            assert low < high, (slot, i, 'shell clearance')
            wanted = -225 - world[i, 16, 1, 3] + 3 * math.cos(
                4 * math.pi * i / (10 if slot == 4 else 20)) - .5*flight[i]
            body_y.append(float(np.clip(wanted, low + .1, high - .1)))
        poses, history = [], {}
        max_error, max_rotation_error, margin = 0., 0., 1e9
        for i, original in enumerate(frames):
            pose = copy.deepcopy(original)
            pose[0] = [4096] * 3 + [0] * 6
            pose[1][7] += round(body_y[i])
            for hip, knee, foot in CHAINS:
                w = np.array(mmd.bone_matrices(old, pose))
                h, goal = w[hip, :3, 3], goals[foot][i]
                delta = goal - h
                distance = np.linalg.norm(delta)
                a = np.linalg.norm(pose[knee][6:9])
                b = np.linalg.norm(pose[foot][6:9])
                margin = min(margin, float(min(a + b - distance,
                                              distance - abs(a - b))))
                assert margin > 0, (slot, i, margin)
                direction = delta / distance
                pole = np.array([.35 if hip == 17 else -.35, 0., -1.])
                pole -= direction * (pole @ direction)
                assert np.linalg.norm(pole) > 1e-6
                pole /= np.linalg.norm(pole)
                along = (a*a - b*b + distance*distance) / (2*distance)
                joint = h + direction * along + pole * math.sqrt(
                    max(0, a*a - along*along))
                upper, lower = motionsecondary.native_plane_rotations(
                    [rest_world[b, :3, 3].tolist() for b in [hip, knee, foot]],
                    [h.tolist(), joint.tolist(), goal.tolist()],
                    [rest_world[b, :3, :3].tolist() for b in [hip, knee]])
                set_rotation(pose, hip, w[skel[hip][1], :3, :3].T @
                             np.array(upper), history)
                w = np.array(mmd.bone_matrices(old, pose))
                set_rotation(pose, knee, w[hip, :3, :3].T @ np.array(lower), history)
                w = np.array(mmd.bone_matrices(old, pose))
                set_rotation(pose, foot, w[knee, :3, :3].T @ rotations[foot][i], history)
                actual = np.array(mmd.bone_matrices(old, pose))[foot]
                max_error = max(max_error, float(np.linalg.norm(actual[:3, 3] - goal)))
                max_rotation_error = max(max_rotation_error, float(np.max(np.abs(
                    actual[:3, :3] - rotations[foot][i]))))
            pose[0] = copy.deepcopy(original[0])
            poses.append(pose)
        poses[-1][1:] = copy.deepcopy(poses[0][1:])
        assert max_error < 1 and max_rotation_error < .005, (slot, max_error, max_rotation_error)
        original = old.anims.anims[old.anims.table[slot]]
        new.anims.anims.append(replace_channels(original, poses, loop, n, channels))
        new.anims.table[slot] = len(new.anims.anims) - 1
        checks.append(dict(slot=slot, max_authored_foot_error=max_error,
                           max_authored_foot_rotation_matrix_error=max_rotation_error,
                           minimum_reach_margin=margin,
                           carrier_y_offset_range=[min(body_y), max(body_y)]))
    return _pack(new), checks


def _clear_hands_and_steps(data, skel):
    n = len(skel)
    old = mmd.MMD.parse(data, n)
    old.type = 205
    new = copy.deepcopy(old)
    for slot in SLOTS:
        frames, loop, events = animsheet.slot_frames(old, n, slot)
        assert events and all(kind == 'sound' for _, kind, _ in events)
        sound = next(i for i in old.anims.anims[old.anims.table[slot]].instrs
                     if i['op'] == 'sound')
        assert all((i['bank'], i['note']) == (sound['bank'], sound['note'])
                   for _, _, i in events)
        poses = copy.deepcopy(frames)
        channels = {(5, 3), (8, 3), (6, 3), (5, 5), (8, 5), (7, 5)}
        if slot != 3:
            for pose in poses:
                for bone in [5, 8]:
                    pose[bone][3] -= round(12 * 4096 / 360)
                pose[6][3] -= round(8 * 4096 / 360)
                pose[5][5] -= round(6 * 4096 / 360)
                pose[8][5] += round(6 * 4096 / 360)
        if slot == 4:
            for pose in poses:
                pose[7][5] += round(4 * 4096 / 360)
        original = old.anims.anims[old.anims.table[slot]]
        anim = replace_channels(original, poses, loop, n, channels)
        anim.instrs = [i for i in anim.instrs if i['op'] != 'sound']
        for tick in ([0, 5, 10, 15] if slot == 4 else [0, 10]):
            event = dict(sound, frame=tick+1)
            at = next((i for i, command in enumerate(anim.instrs)
                       if command.get('frame', -1) > tick+1), len(anim.instrs)-1)
            anim.instrs.insert(at, event)
        new.anims.anims.append(anim)
        new.anims.table[slot] = len(new.anims.anims)-1
    return _pack(new)


def _joint_clearance(data, skel):
    n = len(skel)
    old = mmd.MMD.parse(data, n)
    old.type = 205
    new = copy.deepcopy(old)
    for slot in [3, 4]:
        frames, loop, _ = animsheet.slot_frames(old, n, slot)
        poses = copy.deepcopy(frames)
        for pose in poses:
            if slot == 4:
                pose[7][5] += round(6 * 4096 / 360)
                continue
            root = copy.deepcopy(pose[0])
            pose[0] = [4096]*3 + [0]*6
            w = np.array(mmd.bone_matrices(old, pose))
            axis = w[21, :3, 3] - w[20, :3, 3]
            axis /= np.linalg.norm(axis)
            x, y, z = axis
            skew = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
            q = math.radians(-10)
            twist = (np.eye(3)*math.cos(q) + (1-math.cos(q))*np.outer(axis, axis)
                     + math.sin(q)*skew)
            history = {b: pose[b][3:6] for b in [20, 21, 22]}
            set_rotation(pose, 20, w[16, :3, :3].T @ twist @ w[20, :3, :3], history)
            after = np.array(mmd.bone_matrices(old, pose))
            set_rotation(pose, 21, after[20, :3, :3].T @ w[21, :3, :3], history)
            after = np.array(mmd.bone_matrices(old, pose))
            set_rotation(pose, 22, after[21, :3, :3].T @ w[22, :3, :3], history)
            pose[4][5] += round(2 * 4096 / 360)
            pose[0] = root
        channels = ({(7, 5)} if slot == 4 else
                    {(4, 5)} | {(b, c) for b in [20, 21, 22] for c in [3, 4, 5]})
        original = old.anims.anims[old.anims.table[slot]]
        new.anims.anims.append(replace_channels(original, poses, loop, n, channels))
        new.anims.table[slot] = len(new.anims.anims)-1
    return _pack(new)


def build(data, skel):
    digest = hashlib.sha256(data).hexdigest()
    if digest != SOURCE or len(skel) != 23:
        raise ValueError('Native support recipe requires reviewed MegaKabuterimon source')
    mmd.exe().skeleton[205] = skel
    mmd.exe().bone_count[205] = len(skel)
    old = mmd.MMD.parse(data, len(skel))
    old.type = 205
    supported, checks = _support(old, skel)
    result = _joint_clearance(_clear_hands_and_steps(supported, skel), skel)
    parsed = mmd.MMD.parse(result, len(skel))
    parsed.type = 205
    assert changed_programs(old, parsed) == SLOTS
    assert old.tmd.build() == parsed.tmd.build()
    for slot in SLOTS:
        frames, _, events = animsheet.slot_frames(old, len(skel), slot)
        actual_events = animsheet.slot_frames(parsed, len(skel), slot)[2]
        expected_ticks = [0, 5, 10, 15] if slot == 4 else [0, 10]
        assert [tick for tick, _, _ in actual_events] == expected_ticks
        assert all(kind == 'sound' and event['bank'] == 1 and event['note'] == 16
                   for _, kind, event in actual_events)
        allowed = {(1, 7)} | {(b, c) for chain in CHAINS for b in chain for c in [3, 4, 5]}
        if slot != 3:
            allowed |= {(5, 3), (8, 3), (6, 3), (5, 5), (8, 5)}
        if slot == 4:
            allowed.add((7, 5))
        if slot == 3:
            allowed.add((4, 5))
        before = mmd.AnimPlayer(old.anims.anims[old.anims.table[slot]], len(skel), slot)
        after = mmd.AnimPlayer(parsed.anims.anims[parsed.anims.table[slot]], len(skel), slot)
        for _ in range((len(frames)-1)*8):
            assert before.tick() and after.tick()
            assert before.base == after.base
            for bone in range(len(skel)):
                for channel in range(9):
                    if (bone, channel) not in allowed:
                        assert before.pose[bone][channel] == after.pose[bone][channel]
        sampled = animsheet.slot_frames(parsed, len(skel), slot)[0]
        period, contact = (10, 3) if slot == 4 else (20, 10)
        root_x_drift = (sampled[-1][0][6]-sampled[0][0][6])/(len(sampled)-1)
        plant_error, native_sole = 0., -1e9
        vertices = _feet(parsed, skel)
        for side, (_, _, foot) in enumerate(CHAINS):
            world = [_world(parsed, frame)[foot] for frame in sampled]
            for i, matrix in enumerate(world):
                sole = (vertices[foot] @ matrix[:3, :3].T + matrix[:3, 3])[:, 1]
                native_sole = max(native_sole, float(sole.max()))
                if i == len(world)-1:
                    continue
                phase = (i + side*period/2) % period
                if phase < contact and phase+1 <= contact:
                    for axis, drift in [(0, root_x_drift), (2, 0)]:
                        travel = (world[i+1][axis, 3]-matrix[axis, 3] +
                                  sampled[i+1][0][6+axis]-sampled[i][0][6+axis])
                        plant_error = max(plant_error, abs(float(travel)-drift))
        assert plant_error < .75 and native_sole < 3, (slot, plant_error, native_sole)
        checks[SLOTS.index(slot)].update(max_encoded_plant_travel_error=plant_error,
                                        max_native_sole_y=native_sole)
    storage = motionstorage.audit(result, len(skel))
    assert storage['fits'], storage
    return result, dict(species=205, source_sha256=digest,
                        output_sha256=hashlib.sha256(result).hexdigest(),
                        changed_slots=SLOTS, mesh_exact=True, other_programs_exact=True,
                        source_duration_root_scales_limb_lengths_exact=True,
                        original_footstep_sound_retimed_to_planted_contacts=True,
                        other_channels_exact_eight_cycles=True,
                        profile_style='native beetle acting around rooted steps and supported shell weight',
                        checks=checks, storage=storage)
