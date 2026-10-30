"""Togemon's short-legged rolling steps, with the original boxing performance.

A hip-to-ankle link has only 40 units of reach. Keep its length and native
root trajectory, roll each rigid foot over its actual support vertices, and
solve the shared pelvis height. Recovery follows a world-space footprint;
interpolating local ankle positions would make the toes skim after toe-off.
"""
import copy
import hashlib
import math
import numeric as np
import mmd
import animsheet
import motioncyclelayer
import motionstorage
import motionsecondary
from tools.models.field_animations.articulation import replace_channels
from motiondiscidentity import changed_programs
from motiontailspace import interpolate_pose
from tools.models.field_animations.war_greymon import rotation, set_rotation, align
SOURCE = 'ce4e7b0017bcc00350e6fc1832440524ccf51c92e0edfb2a57e1f34101e2846b'

def _pack(model):
    for anim in model.anims.anims:
        anim.tail = b''
    model.anims.anims, model.anims.table = motioncyclelayer.share_identical_streams(model.anims.anims, model.anims.table)
    return model.build()

def _parse(data, sk):
    mmd.exe().skeleton[208] = sk
    mmd.exe().bone_count[208] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = 208
    return model

def _support(old, sk):
    new = copy.deepcopy(old)
    n = len(sk)

    def world(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, g))
    rest = animsheet.slot_frames(old, n, 33)[0][0]
    rw = world(rest)
    feet = [(10, 11), (12, 13)]
    vertices = {f: np.array(old.tmd.obj_verts(sk[f][0]))[:, :3] for _, f in feet}
    flats = {f: rotation([0, math.degrees(math.atan2(rw[f, 0, 2], rw[f, 2, 2])), 0]) for _, f in feet}
    checks = []
    for slot in [2, 3, 4]:
        fs, loop, events = animsheet.slot_frames(old, n, slot)
        duration = len(fs) - 1
        root = np.array(fs)[:, 0]
        period = {2: 16, 3: 12, 4: 8}[slot]
        contact = {2: 6, 3: 4, 4: 2}[slot]
        rock = {2: 25, 3: 15, 4: 25}[slot]
        origin = {2: 2, 3: 1, 4: 0}[slot]
        zero = []
        for f in fs:
            g = copy.deepcopy(f)
            g[9][7] = 0
            zero.append(world(g))
        zero = np.array(zero)

        def at(t, axis):
            cy = math.floor(t / duration)
            phase = t - cy * duration
            i = min(int(phase), duration - 1)
            q = phase - i
            return cy * (root[-1, axis] - root[0, axis]) + root[i, axis] * (1 - q) + root[i + 1, axis] * q - root[0, axis]

        def foot_plan(side, start, phase, foot):
            total = at(start + contact, 8) - at(start, 8)
            frac = (at(start + phase, 8) - at(start, 8)) / total
            pitch = -rock + 2 * rock * frac
            r, dz, sole = motionsecondary.rolling_foot(vertices[foot].tolist(), flats[foot].tolist(), pitch)
            return (np.array(r), dz, sole)
        cache = {}

        def plan(side, start, foot, hip):
            key = (side, start)
            if key in cache:
                return cache[key]
            offsets = []
            for q in np.linspace(0, contact, contact * 8 + 1):
                r, dz, sole = foot_plan(side, start, float(q), foot)
                offsets.append(-(at(start + float(q), 8) - at(start, 8)) + dz)
            center = float(zero[:-1, hip, 2, 3].mean()) - (min(offsets) + max(offsets)) / 2
            cache[key] = center
            return center
        goals = {}
        maxradius = 0
        for side, (hip, foot) in enumerate(feet):
            records = []
            length = np.linalg.norm(fs[0][foot][6:9])
            hx = float(zero[:-1, hip, 0, 3].mean()) + (4 if side == 0 else -4)
            for tick in range(len(fs)):
                start = math.floor((tick - origin + side * period / 2) / period) * period - side * period / 2 + origin
                phase = tick - start
                center = plan(side, start, foot, hip)
                if phase <= contact:
                    r, dz, sole = foot_plan(side, start, phase, foot)
                    z = center - (at(tick, 8) - at(start, 8)) + dz
                    x = hx - at(tick, 6) + at(start, 6)
                    margin = 0.0
                    planted = True
                else:
                    span = period - contact
                    q = (phase - contact) / span
                    # Slower toe-off/landing in walk/run; the tired recovery
                    # needs its wider middle arc to clear the native guard.
                    smooth = 3 * q * q - 2 * q * q * q if slot == 3 else 6 * q ** 5 - 15 * q ** 4 + 10 * q ** 3
                    # Interpolate world footprints, then subtract actor travel.
                    # Keep the rolling pivot offset during recovery as well.
                    a = center + at(start, 8)
                    b = plan(side, start + period, foot, hip) + at(start + period, 8)
                    z = (1 - smooth) * a + smooth * b - at(tick, 8)
                    x = hx - at(tick, 6) + at(start, 6) + (at(start + period, 6) - at(start, 6)) * smooth
                    pitch = rock * math.cos(math.pi * q)
                    r, dz, sole = motionsecondary.rolling_foot(vertices[foot].tolist(), flats[foot].tolist(), pitch)
                    r = np.array(r)
                    z += dz
                    x += (1 if side == 0 else -1) * {2: 28, 3: 22, 4: 30}[slot] * math.sin(math.pi * q) ** 1.5
                    margin = (18 if slot == 3 else 14) + 2 * math.sin(math.pi * q) ** 2
                    planted = False
                dx = x - zero[tick, hip, 0, 3]
                dz = z - zero[tick, hip, 2, 3]
                radius = math.sqrt(dx * dx + dz * dz)
                if not planted:
                    # Only airborne targets may be limited to available reach;
                    # clamping a planted foot would introduce another slide.
                    dx = float(np.clip(dx, -length + 2, length - 2))
                    x = zero[tick, hip, 0, 3] + dx
                    limit = math.sqrt((length - 2) ** 2 - dx * dx)
                    dz = float(np.clip(dz, -limit, limit))
                    z = zero[tick, hip, 2, 3] + dz
                    radius = math.sqrt(dx * dx + dz * dz)
                maxradius = max(maxradius, radius)
                assert radius < length - 0.05, (slot, tick, foot, 'horizontalreach', radius, length)
                vertical = math.sqrt(length * length - radius * radius)
                carrier = -sole - vertical - zero[tick, hip, 1, 3] - margin
                records.append(dict(x=x, z=z, r=r, sole=sole, vertical=vertical, carrier=carrier, planted=planted, margin=margin))
            goals[foot] = records
        poses = []
        history = {}
        errors = []
        body = []
        for i, original in enumerate(fs):
            f = copy.deepcopy(original)
            f[0] = [4096] * 3 + [0] * 6
            # Negative Y is up. Use the higher requirement of the two feet.
            carrier = min((goals[foot][i]['carrier'] for _, foot in feet))
            f[9][7] = round(carrier)
            body.append(carrier)
            for hip, foot in feet:
                w = np.array(mmd.bone_matrices(old, f))
                g = goals[foot][i]
                h = w[hip, :3, 3]
                target = np.array([g['x'], h[1] + g['vertical'], g['z']])
                ref = rw[foot, :3, 3] - rw[hip, :3, 3]
                rhip = align(ref, target - h) @ rw[hip, :3, :3]
                set_rotation(f, hip, w[9, :3, :3].T @ rhip, history)
                w = np.array(mmd.bone_matrices(old, f))
                set_rotation(f, foot, w[hip, :3, :3].T @ g['r'], history)
                w = np.array(mmd.bone_matrices(old, f))
                errors.append(float(np.linalg.norm(w[foot, :3, 3] - target)))
            f[0] = copy.deepcopy(original[0])
            poses.append(f)
        poses[-1][1:] = copy.deepcopy(poses[0][1:])
        channels = {(9, 7)} | {(b, c) for b in [10, 11, 12, 13] for c in [3, 4, 5]}
        anim = replace_channels(old.anims.anims[old.anims.table[slot]], poses, loop, n, channels)
        sound = next((v for v in anim.instrs if v['op'] == 'sound'))
        anim.instrs = [v for v in anim.instrs if v['op'] != 'sound']
        for tick in range(origin, duration, period // 2):
            event = dict(sound, frame=tick + 1)
            j = next((j for j, v in enumerate(anim.instrs) if v.get('frame', -1) > tick + 1), len(anim.instrs) - 1)
            anim.instrs.insert(j, event)
        new.anims.anims.append(anim)
        new.anims.table[slot] = len(new.anims.anims) - 1
        checks.append(dict(slot=slot, period=period, contact=contact, rock=rock, max_authored_ankle_error=max(errors), carrier_y_range=[min(body), max(body)], max_radius=maxradius))
    return (new, checks)

def _wrist(old):
    new = copy.deepcopy(old)
    for slot in [3, 4]:
        fs, loop, _ = animsheet.slot_frames(old, 15, slot)
        poses = copy.deepcopy(fs)
        history = {}
        for f in poses:
            root = copy.deepcopy(f[0])
            f[0] = [4096] * 3 + [0] * 6
            w = np.array(mmd.bone_matrices(old, f))
            set_rotation(f, 8, w[7, :3, :3].T @ rotation([-15, 0, -20 if slot == 4 else 0]) @ w[8, :3, :3], history)
            f[0] = root
        new.anims.anims.append(replace_channels(old.anims.anims[old.anims.table[slot]], poses, loop, 15, {(8, c) for c in [3, 4, 5]}))
        new.anims.table[slot] = len(new.anims.anims) - 1
    return new


def _verify(original, actual, sk):
    assert changed_programs(original, actual) == [2, 3, 4]
    assert original.tmd.build() == actual.tmd.build()
    checks = []
    vertices = {b: np.array(actual.tmd.obj_verts(obj))[:, :3]
                for b, (obj, _) in enumerate(sk) if obj >= 0}
    for slot in [2, 3, 4]:
        before = mmd.AnimPlayer(original.anims.anims[original.anims.table[slot]], 15, slot)
        after = mmd.AnimPlayer(actual.anims.anims[actual.anims.table[slot]], 15, slot)
        frames, loop, events = animsheet.slot_frames(actual, 15, slot)
        duration = len(frames) - 1
        assert loop == 0 and duration == {2: 16, 3: 12, 4: 16}[slot]
        assert [e[0] for e in events] == {2: [2, 10], 3: [1, 7], 4: [0, 4, 8, 12]}[slot]
        assert all(kind == 'sound' and event['bank'] == 1 and event['note'] == 11
                   for _, kind, event in events)
        allowed = {(9, 7)} | {(b, c) for b in [10, 11, 12, 13] for c in [3, 4, 5]}
        if slot in [3, 4]:
            allowed |= {(8, c) for c in [3, 4, 5]}
        for tick in range(duration * 8):
            assert before.tick() and after.tick()
            assert before.base == after.base
            for bone in range(15):
                for channel in range(9):
                    if (bone, channel) not in allowed:
                        assert before.pose[bone][channel] == after.pose[bone][channel], (slot, tick, bone, channel)
        # Match the engine's shortest-Euler local SRT interpolation, including
        # toe-off and landing. Native keys alone missed the source's skimming.
        dense = [interpolate_pose(frames[i], frames[i+1], j*4096//3)
                 for i in range(duration) for j in range(3)] + [frames[-1]]
        feet = {b: [] for b in [11, 13]}
        sole_y, other_y = -float('inf'), -float('inf')
        for frame in dense:
            pose = copy.deepcopy(frame)
            pose[0] = [4096]*3 + [0]*6
            world = np.array(mmd.bone_matrices(actual, pose))
            for bone, points in vertices.items():
                transformed = points @ world[bone, :3, :3].T + world[bone, :3, 3]
                if bone in feet:
                    sole_y = max(sole_y, float(transformed[:, 1].max()))
                    feet[bone].append(transformed + np.array(frame[0][6:9]))
                else:
                    other_y = max(other_y, float(transformed[:, 1].max()))
        travel, contacts = 0., 0
        for points in feet.values():
            for a, b in zip(points, points[1:]):
                near = (abs(a[:, 1]) < 3) & (abs(b[:, 1]) < 3)
                if near.any():
                    contacts += 1
                    travel = max(travel, float(np.linalg.norm((b-a)[near][:, [0, 2]], axis=1).max()))
        assert contacts > 10 and travel < 2 and sole_y < 3 and other_y < 0, (slot, contacts, travel, sole_y, other_y)
        checks.append(dict(slot=slot, duration=duration, sample_hz=60,
                           same_vertex_near_plane_intervals=contacts,
                           max_near_plane_material_vertex_xz_travel=travel,
                           max_full_foot_y=sole_y, max_other_mesh_y=other_y))
    return checks


def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE or len(sk) != 15:
        raise ValueError('Togemon recipe requires the pinned reviewed source')
    original = _parse(data, sk)
    supported, authored = _support(original, sk)
    result = _pack(_wrist(_parse(_pack(supported), sk)))
    actual = _parse(result, sk)
    decoded = _verify(original, actual, sk)
    storage = motionstorage.audit(result, 15)
    assert storage['fits'], storage
    return result, dict(species=208, source_sha256=SOURCE,
                        output_sha256=hashlib.sha256(result).hexdigest(), changed_slots=[2, 3, 4],
                        mesh_skeleton_idle_private_care_battle_exact=True,
                        other_channels_and_root_exact_eight_cycles=True,
                        one_link_lengths_and_native_upper_acting_preserved=True,
                        original_footstep_sample_retimed=True,
                        authored_checks=authored, decoded_checks=decoded, storage=storage)
