"""GranKuwagamon's four supported limbs and free upper pincers.

Each support limb is one rigid hip-to-wrist link plus the entire rigid claw.
Solve the actual mesh heel/toe roll against its footprint, fit a shared carrier
height, and retain the native hunch, head, wing and pincer curves. Torso yaw
is damped for grounded steps. Foreclaw recovery
stays forward of the rear legs; it is not a borrowed human three-joint gait.
"""
import copy
import hashlib
import math
import numeric as np
import mmd
import animsheet
import motionsecondary
import motioncyclelayer
import motionstorage
from tools.models.field_animations.articulation import replace_channels
from motiondiscidentity import changed_programs
from tools.models.field_animations.war_greymon import rotation, set_rotation, align
SOURCE = '7aff3957ff3d24b65db422b36b8dd8394155722a8256cf7f6b3f97ac990dfc66'

def _pack(model):
    for animation in model.anims.anims:
        animation.tail = b''
    model.anims.anims, model.anims.table = motioncyclelayer.share_identical_streams(model.anims.anims, model.anims.table)
    return model.build()

def _parse(data, sk):
    mmd.exe().skeleton[210] = sk
    mmd.exe().bone_count[210] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = 210
    return model

def _locomotion(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)

    def world(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, g))
    rest = animsheet.slot_frames(old, n, 0)[0][0]
    rw = world(rest)
    chains = [(7, 8), (9, 10), (19, 20), (21, 22)]
    vs = {f: np.array(old.tmd.obj_verts(sk[f][0]))[:, :3] for _, f in chains}
    angles = {f: np.linspace(-40, 30, 281) if f < 15 else np.linspace(-35, 35, 281) for _, f in chains}
    flats = {f: rw[f, :3, :3] for _, f in chains}
    roll = {f: [motionsecondary.rolling_foot(vs[f].tolist(), flats[f].tolist(), a) for a in angles[f]] for _, f in chains}
    DZ = {f: np.array([r[1] for r in roll[f]]) for _, f in chains}
    SOLE = {f: np.array([r[2] for r in roll[f]]) for _, f in chains}
    reports = []
    for slot in [2, 3, 4]:
        fs, loop, events = animsheet.slot_frames(old, n, slot)
        duration = len(fs) - 1
        # Keep the native cycle lengths, with a steady pace appropriate to
        # the actual reach of the claws and the heavy torso.
        speed = {2: 16, 3: 10, 4: 40}[slot]
        for tick, frame in enumerate(fs):
            frame[0][8] = -speed * tick
            frame[2][4] = round(frame[2][4] * {2: 0.55, 3: 0.8, 4: 1.0}[slot])
        root = np.array(fs)[:, 0]
        period = duration
        contact = 5 if slot == 4 else 12
        origin = [period / 2 - 2, period - 2, 0, period / 2]
        zero = []
        for f in fs:
            g = copy.deepcopy(f)
            g[1][7] = 0
            zero.append(world(g))
        zero = np.array(zero)

        def at(t, axis):
            cy = math.floor(t / duration)
            phase = t - cy * duration
            i = min(int(phase), duration - 1)
            q = phase - i
            return cy * (root[-1, axis] - root[0, axis]) + root[i, axis] * (1 - q) + root[i + 1, axis] * q - root[0, axis]

        def preferred(foot, q, stance):
            a, b = (-18, 6) if foot < 15 else (-18, 18)
            return a + (b - a) * q if stance else (a + b) / 2 + (b - a) / 2 * math.cos(math.pi * q)

        def rolling(foot, angle):
            return motionsecondary.rolling_foot(vs[foot].tolist(), flats[foot].tolist(), angle)
        cache = {}

        def contact_length(foot):
            return (3 if slot == 4 else 6 if slot == 3 else 6) if foot < 15 else 5 if slot == 4 else 12

        def center(hip, foot, start):
            contact = contact_length(foot)
            key = (foot, start)
            if key not in cache:
                offsets = []
                for phase in np.linspace(0, contact, contact * 8 + 1):
                    _, dz, _ = rolling(foot, preferred(foot, phase / contact, True))
                    offsets.append(-(at(start + phase, 8) - at(start, 8)) + dz)
                cache[key] = float(zero[:-1, hip, 2, 3].mean()) - (min(offsets) + max(offsets)) / 2 + (0 if foot < 15 else 15)
            return cache[key]
        plans = []
        for t in range(len(fs)):
            goals = []
            for c, (hip, foot) in enumerate(chains):
                contact = contact_length(foot)
                start = math.floor((t - origin[c]) / period) * period + origin[c]
                phase = t - start
                hx = float(zero[:-1, hip, 0, 3].mean()) + float(rw[foot, 0, 3] - rw[hip, 0, 3]) + (1 if hip in [7, 19] else -1) * (28 if foot < 15 else 0)
                x = hx - at(t, 6) + at(start, 6)
                cc = center(hip, foot, start)
                if phase <= contact:
                    q = phase / contact
                    z = cc - (at(t, 8) - at(start, 8))
                    up = 0
                    stance = True
                else:
                    q = (phase - contact) / (period - contact)
                    smooth = 6 * q ** 5 - 15 * q ** 4 + 10 * q ** 3
                    a = cc + at(start, 8)
                    b = center(hip, foot, start + period) + at(start + period, 8)
                    z = (1 - smooth) * a + smooth * b - at(t, 8)
                    x += (at(start + period, 6) - at(start, 6)) * smooth
                    up = 16 + 10 * math.sin(math.pi * q) ** 2 if slot == 4 else 14 + 6 * math.sin(math.pi * q) ** 2
                    stance = False
                pref = preferred(foot, q, stance)
                length = float(np.linalg.norm(fs[0][foot][6:9]))
                dx = x - zero[t, hip, 0, 3]
                dz = z + DZ[foot] - zero[t, hip, 2, 3]
                rad = dx * dx + dz * dz
                mask = (rad < length * length) & (abs(angles[foot] - pref) <= 22)
                ys = -SOLE[foot] - np.sqrt(np.maximum(0, length * length - rad)) - zero[t, hip, 1, 3]
                goals.append(dict(hip=hip, foot=foot, x=x, z=z, up=up, stance=stance, preferred=pref, length=length, mask=mask, body_y=ys, phase=phase, contact=contact))
            active = [g for g in goals if g['stance']]
            low = max((float(g['body_y'][g['mask']].min()) if g['mask'].any() else 1000000.0 for g in active), default=-1000000.0)
            high = min((float(g['body_y'][g['mask']].max()) if g['mask'].any() else -1000000.0 for g in active), default=1000000.0)
            wanted = fs[t][1][7] - 10
            if low > high:
                raise ValueError(('No common scarab support height', slot, t, low, high))
            body = float(np.clip(wanted, low + 0.05, high - 0.05)) if high - low > 0.1 else (low + high) / 2
            solved = [dict(hip=g['hip'], foot=g['foot'], stance=g['stance']) for g in goals]
            plans.append(dict(body=body, body_low=low, body_high=high, solved=solved, goals=goals))
        values = np.array([a['body'] for a in plans[:-1]])
        wanted = np.array([f[1][7] - 10 for f in fs[:-1]], float)
        # Cyclic projected smoothing: position weight .05, velocity 1,
        # acceleration 4. Every update stays inside all stance reach limits.
        for iteration in range(160):
            for t in range(duration):
                desired = (17 * (values[(t - 1) % duration] + values[(t + 1) % duration]) - 4 * (values[(t - 2) % duration] + values[(t + 2) % duration]) + 0.05 * wanted[t]) / 26.05
                lo = plans[t]['body_low']
                hi = plans[t]['body_high']
                values[t] = float(np.clip(desired, lo + 0.05, hi - 0.05)) if hi - lo > 0.1 else (lo + hi) / 2
        for t in range(duration):
            body = float(values[t])
            plans[t]['body'] = body
            for ci, g in enumerate(plans[t]['goals']):
                if not g['stance']:
                    continue
                hip = g['hip']
                foot = g['foot']
                delta = g['body_y'] - body
                idx = [i for i in range(len(angles[foot]) - 1) if g['mask'][i] and g['mask'][i + 1] and (delta[i] * delta[i + 1] <= 0)]
                assert idx, (slot, t, foot, 'smoothed support interval has no root')
                i = min(idx, key=lambda i: abs(float(angles[foot][i]) - g['preferred']))
                a = float(angles[foot][i])
                b = float(angles[foot][i + 1])
                fa = float(delta[i])
                hx, hy, hz = zero[t, hip, :3, 3] + np.array([0, body, 0])
                length = g['length']
                for _ in range(24):
                    mid = (a + b) / 2
                    r, dz, sole = rolling(foot, mid)
                    dx = g['x'] - hx
                    zz = g['z'] + dz - hz
                    v = math.sqrt(max(0, length * length - dx * dx - zz * zz))
                    fm = -sole - v - zero[t, hip, 1, 3] - body
                    if fm * fa > 0:
                        a = mid
                        fa = fm
                    else:
                        b = mid
                pitch = (a + b) / 2
                r, dz, sole = rolling(foot, pitch)
                x = g['x']
                z = g['z'] + dz
                vertical = math.sqrt(max(0, length * length - (x - hx) ** 2 - (z - hz) ** 2))
                plans[t]['solved'][ci].update(x=x, z=z, r=np.array(r), vertical=vertical, pitch=pitch)
        for t in range(duration):
            body = plans[t]['body']
            for ci, g in enumerate(plans[t]['goals']):
                if g['stance']:
                    continue
                hip = g['hip']
                foot = g['foot']
                contact = g['contact']
                start = math.floor((t - origin[ci]) / period) * period + origin[ci]
                end = start + contact
                span = period - contact
                q = (t - end) / span
                i0 = int(end) % duration
                i1 = int(start + period) % duration
                p0 = plans[i0]['solved'][ci]['pitch']
                p1 = plans[i1]['solved'][ci]['pitch']
                d0 = p0 - plans[(i0 - 1) % duration]['solved'][ci]['pitch']
                d1 = plans[(i1 + 1) % duration]['solved'][ci]['pitch'] - p1
                v0 = float(np.clip(d0 * span, -20, 20))
                v1 = float(np.clip(d1 * span, -20, 20))
                pitch = (2 * q ** 3 - 3 * q * q + 1) * p0 + (q ** 3 - 2 * q * q + q) * v0 + (-2 * q ** 3 + 3 * q * q) * p1 + (q ** 3 - q * q) * v1
                if foot < 15:
                    fade = min(1.0, q / 0.18, (1 - q) / 0.18)
                    fade = 3 * fade * fade - 2 * fade ** 3
                    pitch += (max(pitch, -8) - pitch) * fade
                r, dz, sole = rolling(foot, pitch)
                hx, hy, hz = zero[t, hip, :3, 3] + np.array([0, body, 0])
                length = g['length']
                dx = g['x'] - hx + (20 * math.sin(math.pi * q) ** 2 * (1 if hip == 7 else -1) if foot < 15 else 0)
                zz = g['z'] + dz - hz + (40 * math.sin(math.pi * q) ** 2 if foot > 15 else 0)
                zz = float(np.clip(zz, -45, 85)) if foot > 15 else float(np.clip(zz, -55, 35))
                if foot < 15:
                    z0 = plans[i0]['solved'][ci]['z'] - zero[i0, hip, 2, 3]
                    z1 = plans[i1]['solved'][ci]['z'] - zero[i1, hip, 2, 3]
                    mid = min(-25.0, z1 + 15)
                    a, b, u = (z0, mid, q * 2) if q <= 0.5 else (mid, z1, (q - 0.5) * 2)
                    u = 6 * u ** 5 - 15 * u ** 4 + 10 * u ** 3
                    zz = (1 - u) * a + u * b
                maxrad = length - 1
                dx = float(np.clip(dx, -maxrad, maxrad))
                zmax = math.sqrt(maxrad ** 2 - dx ** 2)
                zz = float(np.clip(zz, -zmax, zmax))
                vmax = -g['up'] - sole - hy
                minrad = math.sqrt(max(0, length ** 2 - max(0, vmax) ** 2))
                needed = math.sqrt(max(0, min(maxrad, minrad) ** 2 - zz ** 2))
                dx = (1 if hip in [7, 19] else -1) * max(abs(dx), needed)
                dx = float(np.clip(dx, -math.sqrt(maxrad ** 2 - zz ** 2), math.sqrt(maxrad ** 2 - zz ** 2)))
                vertical = math.sqrt(max(0, length ** 2 - dx * dx - zz * zz))
                plans[t]['solved'][ci].update(x=hx + dx, z=hz + zz, r=np.array(r), vertical=vertical, pitch=pitch)
        plans[-1] = copy.deepcopy(plans[0])
        poses = []
        history = {}
        for t, f0 in enumerate(fs):
            f = copy.deepcopy(f0)
            f[0] = [4096] * 3 + [0] * 6
            f[1][7] = round(plans[t]['body']) - 2
            for g in plans[t]['solved']:
                hip = g['hip']
                foot = g['foot']
                w = world(f)
                h = w[hip, :3, 3]
                target = np.array([g['x'], h[1] + g['vertical'], g['z']])
                sw = world(f0)
                ref = sw[foot, :3, 3] - sw[hip, :3, 3]
                rh = align(ref, target - h) @ sw[hip, :3, :3]
                set_rotation(f, hip, w[sk[hip][1], :3, :3].T @ rh, history)
                w = world(f)
                set_rotation(f, foot, w[hip, :3, :3].T @ g['r'], history)
            for jaw in [5, 6]:
                w = world(f)
                set_rotation(f, jaw, w[3, :3, :3].T @ rotation([-14 if slot == 3 else -8, 0, 0]) @ w[jaw, :3, :3], history)
            for hand, sign in [(12, -1), (14, 1)]:
                w = world(f)
                set_rotation(f, hand, w[sk[hand][1], :3, :3].T @ rotation([0, sign * 12, sign * 6]) @ w[hand, :3, :3], history)
            f[0] = copy.deepcopy(f0[0])
            poses.append(f)
        poses[-1][1:] = copy.deepcopy(poses[0][1:])
        poses = motionsecondary.cyclic_euler_branches(poses, [b for pair in chains for b in pair])
        channels = {(1, 7), (2, 4)} | {(b, c) for b in [5, 6, 12, 14] for c in [3, 4, 5]} | {(b, c) for pair in chains for b in pair for c in [3, 4, 5]}
        anim = replace_channels(old.anims.anims[old.anims.table[slot]], poses, loop, n, channels)
        for ins in anim.instrs:
            if ins['op'] == 'key':
                ins['bones'] = [group for group in ins['bones'] if group['bone'] != 0]
        first = next((ins for ins in anim.instrs if ins['op'] == 'key' and ins['frame'] == 1))
        # Root momentum is bone0 in key instructions, not a stored pose row.
        first['bones'].insert(0, dict(bone=0, div=duration, vals={'tz': -speed * duration}))
        new.anims.anims.append(anim)
        new.anims.table[slot] = len(new.anims.anims) - 1
        reports.append(dict(slot=slot, contact=contact, fore_contact=contact_length(8), rear_contact=contact_length(20), origin=origin, body_y_range=[min((g['body'] for g in plans)), max((g['body'] for g in plans))], max_body_step=max((abs(plans[t + 1]['body'] - plans[t]['body']) for t in range(duration)))))
    return (new, reports)

def _idle(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    fs, loop, events = animsheet.slot_frames(old, n, 0)
    poses = []
    history = {}
    feet = [8, 10, 20, 22]
    verts = {b: np.array(old.tmd.obj_verts(obj))[:, :3] for b, (obj, _) in enumerate(sk) if obj >= 0}
    lifts = []
    handfold = []
    for i, original in enumerate(fs):
        f = copy.deepcopy(original)
        f[0] = [4096] * 3 + [0] * 6
        w = np.array(mmd.bone_matrices(old, f))
        floor = max((float((verts[b] @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max()) for b in feet))
        lift = math.ceil(max(0, floor + 2))
        f[1][7] -= lift
        lifts.append(lift)
        for jaw in [5, 6]:
            w = np.array(mmd.bone_matrices(old, f))
            set_rotation(f, jaw, w[3, :3, :3].T @ rotation([-8, 0, 0]) @ w[jaw, :3, :3], history)
        for hand, sign in [(12, -1), (14, 1)]:
            w = np.array(mmd.bone_matrices(old, f))
            base = rotation([0, sign * 12, sign * 6]) @ w[hand, :3, :3]
            h = w[hand, :3, 3]
            extra = 0
            for extra in np.arange(0, 25.01, 0.25):
                target = rotation([0, 0, sign * float(extra)]) @ base
                ground = float((verts[hand] @ target.T + h)[:, 1].max())
                if ground <= -6:
                    break
            assert ground <= -6, (i, hand, ground)
            set_rotation(f, hand, w[sk[hand][1], :3, :3].T @ target, history)
            handfold.append(float(extra))
        f[0] = copy.deepcopy(original[0])
        poses.append(f)
    poses[-1][1:] = copy.deepcopy(poses[0][1:])
    poses = motionsecondary.cyclic_euler_branches(poses, [5, 6, 12, 14])
    channels = {(1, 7)} | {(b, c) for b in [5, 6, 12, 14] for c in [3, 4, 5]}
    new.anims.anims.append(replace_channels(old.anims.anims[old.anims.table[0]], poses, loop, n, channels))
    new.anims.table[0] = len(new.anims.anims) - 1
    return (new, dict(body_lift_range=[min(lifts), max(lifts)], max_extra_pincer_roll=max(handfold)))


def _verify(original, actual, sk):
    assert changed_programs(original, actual) == [0, 2, 3, 4]
    assert original.tmd.build() == actual.tmd.build()
    feet = [8, 10, 20, 22]
    vertices = {b: np.array(actual.tmd.obj_verts(obj))[:, :3]
                for b, (obj, _) in enumerate(sk) if obj >= 0}
    checks = []
    from motiontailspace import interpolate_pose
    for slot in [0, 2, 3, 4]:
        frames, loop, events = animsheet.slot_frames(actual, 23, slot)
        source, source_loop, source_events = animsheet.slot_frames(original, 23, slot)
        duration = len(frames)-1
        assert duration == {0: 104, 2: 24, 3: 24, 4: 20}[slot]
        assert loop == source_loop == 0 and events == source_events
        allowed = {(1, 7)} | {(b, c) for b in [5, 6, 12, 14] for c in [3, 4, 5]}
        if slot:
            allowed |= {(2, 4)} | {(b, c) for b in [7, 8, 9, 10, 19, 20, 21, 22] for c in [3, 4, 5]}
        before = mmd.AnimPlayer(original.anims.anims[original.anims.table[slot]], 23, slot)
        after = mmd.AnimPlayer(actual.anims.anims[actual.anims.table[slot]], 23, slot)
        speed = {0: 0, 2: 16, 3: 10, 4: 40}[slot]
        yaw_scale = {0: 1, 2: .55, 3: .8, 4: 1}[slot]
        for tick in range(duration*8+1):
            assert before.tick() and after.tick()
            assert after.base == [0, 0, -speed if tick else 0], (slot, tick, after.base)
            for bone in range(23):
                for channel in range(9):
                    if (bone, channel) not in allowed:
                        assert before.pose[bone][channel] == after.pose[bone][channel], (slot, tick, bone, channel)
            assert abs(after.pose[2][4]-round(before.pose[2][4]*yaw_scale)) <= 1
        assert after.root == [0., 0., float(-speed*duration*8)]
        dense = [interpolate_pose(a, b, j*4096//3)
                 for a, b in zip(frames, frames[1:]) for j in range(3)] + [frames[-1]]
        ground = {b: -float('inf') for b in vertices}
        near_plane_travel, previous = 0., {}
        for frame in dense:
            pose = copy.deepcopy(frame)
            pose[0] = [4096]*3 + [0]*6
            world = np.array(mmd.bone_matrices(actual, pose))
            for bone, points in vertices.items():
                transformed = points @ world[bone, :3, :3].T + world[bone, :3, 3]
                ground[bone] = max(ground[bone], float(transformed[:, 1].max()))
                if bone in feet:
                    transformed += np.array(frame[0][6:9])
                    if bone in previous:
                        old = previous[bone]
                        near = (abs(old[:, 1]) < 3) & (abs(transformed[:, 1]) < 3)
                        if near.any():
                            near_plane_travel = max(near_plane_travel, float(np.linalg.norm((transformed-old)[near][:, [0, 2]], axis=1).max()))
                    previous[bone] = transformed
        sole = max(ground[b] for b in feet)
        other = max(y for b, y in ground.items() if b not in feet)
        assert sole < 2 and other < 0 and near_plane_travel < 4, (slot, sole, other, near_plane_travel)
        checks.append(dict(slot=slot, duration=duration, root_units_per_tick=speed,
                           chest_yaw_scale=yaw_scale, sample_hz=60,
                           full_support_mesh_max_y=sole, other_mesh_max_y=other,
                           max_near_plane_same_material_vertex_xz_travel=near_plane_travel))
    return checks


def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE or len(sk) != 23:
        raise ValueError('GranKuwagamon recipe requires the pinned reviewed source')
    original = _parse(data, sk)
    moving, moving_checks = _locomotion(original, sk)
    resting, idle_checks = _idle(_parse(_pack(moving), sk), sk)
    result = _pack(resting)
    actual = _parse(result, sk)
    decoded = _verify(original, actual, sk)
    storage = motionstorage.audit(result, 23)
    assert storage['fits'], storage
    return result, dict(species=210, source_sha256=SOURCE,
                        output_sha256=hashlib.sha256(result).hexdigest(),
                        changed_slots=[0, 2, 3, 4], storage=storage,
                        mesh_skeleton_private33_care_battle_exact=True,
                        unselected_channels_and_limb_lengths_exact_eight_cycles=True,
                        original_events_exact=True,
                        moving_checks=moving_checks, idle_checks=idle_checks,
                        decoded_checks=decoded)
