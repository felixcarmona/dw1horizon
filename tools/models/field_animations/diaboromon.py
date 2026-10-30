"""Diaboromon's native acting with supported reverse-folded hindlegs.

Keep the upper thighs and the native 88-tick performance. Carry the long
claws clear of the feet, solve the two distal leg links on a stable bend
branch, and counterrotate each paw against its decoded parent. Exhaustion
uses a separate stooped breathing loop. Navigation pace is 16/10/32 units
per logical tick so the short distal supports can plant without sliding.
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
from tools.models.field_animations.gliding import _forward
from tools.models.field_animations.war_greymon import rotation, set_rotation
from motiondiscidentity import changed_programs
SOURCE = '1b4979e641c58df07dd19f861aaff8989e36be8a654fa299b0411faa2c0dde34'
PARENTS = [-1, 14, 1, 2, 3, 4, 1, 6, 7, 8, 1, 10, 11, 12, 15, 0, 15, 16, 17, 18, 15, 20, 21, 22]

def replace_channels(original, samples, loop, nb, channels, tolerance=2):
    encoded = mmd.encode_anim(samples, nb, loop_sample=loop, tol=tolerance, repeats=False)
    result = copy.deepcopy(original)
    for b, c in channels:
        result.pose[b - 1][c if result.has_scale else c - 3] = encoded.pose[b - 1][c if encoded.has_scale else c - 3]
    for ins in result.instrs:
        if ins['op'] == 'key':
            for group in ins['bones']:
                group['vals'] = {k: v for k, v in group['vals'].items() if (group['bone'], mmd.CHANNELS.index(k)) not in channels}
            ins['bones'] = [g for g in ins['bones'] if g['vals']]
    for ins in encoded.instrs:
        if ins['op'] != 'key':
            continue
        key = copy.deepcopy(ins)
        for group in key['bones']:
            group['vals'] = {k: v for k, v in group['vals'].items() if (group['bone'], mmd.CHANNELS.index(k)) in channels}
        key['bones'] = [g for g in key['bones'] if g['vals']]
        if not key['bones']:
            continue
        existing = next((i for i in result.instrs if i['op'] == 'key' and i['frame'] == key['frame']), None)
        if existing is not None:
            existing['bones'].extend(key['bones'])
            continue
        at = len(result.instrs) - 1
        for j, other in enumerate(result.instrs):
            f = other.get('frame')
            if other['op'] == 'loop_start':
                f = next((x.get('frame') for x in result.instrs[j + 1:] if x.get('frame') is not None), None)
            if f is not None and f > key['frame']:
                at = j
                break
        result.instrs.insert(at, key)
    return result

def bounded_hock(root, end, a, b, sign):
    """Intersect the two rigid links at a separated, fixed lateral hock plane."""
    root = np.array(root)
    end = np.array(end)
    x = sign * 70
    aa = math.sqrt(a * a - (x - root[0]) ** 2)
    bb = math.sqrt(b * b - (x - end[0]) ** 2)
    axis = end[1:] - root[1:]
    dist = np.linalg.norm(axis)
    assert abs(aa - bb) < dist < aa + bb, ('unreachable fixed hock', root, end, aa, bb)
    axis /= dist
    along = (aa * aa - bb * bb + dist * dist) / (2 * dist)
    height = math.sqrt(aa * aa - along * along)
    centre = root[1:] + axis * along
    normal = np.array([-axis[1], axis[0]])
    points = [np.r_[x, centre + sign2 * height * normal] for sign2 in [-1, 1]]
    # Keep the same bend branch even when the flying paw rises above the knee.
    middle = points[1]
    return (middle, end, 0)

def _author(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    native, loop, native_events = animsheet.slot_frames(old, n, 33)
    assert len(native) == 89 and loop == 0 and (not native_events)
    vs = {b: np.array(old.tmd.obj_verts(o))[:, :3] for b, (o, _) in enumerate(sk) if o >= 0}

    def world(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, g))
    ref = copy.deepcopy(native[0])
    for right, left in [(16, 20), (17, 21), (18, 22), (19, 23)]:
        ref[left][3:6] = [ref[right][3], -ref[right][4], -ref[right][5]]
    rw = world(ref)
    reports = []
    for slot in [0, 1, 2, 3, 4]:
        duration = 24 if slot == 1 else 88
        cycles = {0: 0, 1: 0, 2: 5, 3: 4, 4: 8}[slot]
        period = duration / cycles if cycles else duration
        duty = {0: 1, 1: 1, 2: 0.5, 3: 0.5, 4: 0.35}[slot]
        contact = period * duty
        _, _, events = animsheet.slot_frames(old, n, slot)
        distance = {0: 0, 1: 0, 2: 16 * 88, 3: 10 * 88, 4: 32 * 88}[slot]
        speed = distance / duration
        lift = {0: 0, 1: 0, 2: 18, 3: 10, 4: 18}[slot]
        heel = {0: 0, 1: 0, 2: -8, 3: -6, 4: -6}[slot]
        toe = {0: 0, 1: 0, 2: 14, 3: 10, 4: 10}[slot]
        frames = []
        plan = []
        hist = {}
        errors = []
        for t, source in enumerate(native if slot != 1 else [native[0]] * (duration + 1)):
            f = copy.deepcopy(source)
            if slot == 1:
                breath = math.sin(2 * math.pi * t / duration)
                for bone, degrees in [(1, 5 + breath), (2, 8 + 1.5 * breath), (14, 3 + 0.5 * breath), (15, 3)]:
                    f[bone][3] += round(degrees * 4096 / 360)
                f[15][7] += round(4 + 1.5 * breath)
            for bone, sign in [(7, 1), (11, -1)]:
                f[bone][5] -= sign * round(8 * 4096 / 360)
            row = []
            for side, (hip, knee, hock, foot) in enumerate([(16, 17, 18, 19), (20, 21, 22, 23)]):
                sign = 1 if side == 0 else -1
                phase = (t + side * period / 2) % period
                if not cycles:
                    x = sign * 90
                    z = 100
                    up = 8
                    pitch = 0
                elif phase <= contact:
                    x = sign * 90
                    z = 100 - speed * contact / 2 + speed * phase
                    up = 8
                    pitch = heel + (toe - heel) * phase / contact
                else:
                    u = (phase - contact) / (period - contact)
                    smooth = 6 * u ** 5 - 15 * u ** 4 + 10 * u ** 3
                    half = speed * contact / 2
                    z = (100 + half) * (1 - smooth) + (100 - half) * smooth + (period - contact) * speed * u * (1 - u) * (1 - 2 * u) ** 5
                    x = sign * (90 - 6 * math.sin(math.pi * u) ** 2)
                    up = 8 + lift * math.sin(math.pi * u)
                    blend = 3 * u * u - 2 * u * u * u
                    pitch = toe * (1 - blend) + heel * blend + (toe - heel) / contact * (period - contact) * u * (1 - u) * (1 - 2 * u)
                flat = rotation([0, -sign * 5, 0])
                rf, dz, bottom = motionsecondary.rolling_foot(vs[foot].tolist(), flat.tolist(), pitch)
                rf = np.array(rf)
                z += dz
                goal = np.array([x, -up - bottom, z])
                w = world(f)
                h = w[hip, :3, 3]
                h = w[knee, :3, 3]
                a, b, swivel = bounded_hock(h, goal, float(np.linalg.norm(f[hock][6:9])), float(np.linalg.norm(f[foot][6:9])), sign)
                rk, ra = map(np.array, motionsecondary.native_plane_rotations([rw[v, :3, 3].tolist() for v in [knee, hock, foot]], [v.tolist() for v in [h, a, b]], [rw[v, :3, :3].tolist() for v in [knee, hock]]))
                set_rotation(f, knee, w[hip, :3, :3].T @ rk, hist)
                w = world(f)
                set_rotation(f, hock, w[knee, :3, :3].T @ ra, hist)
                w = world(f)
                set_rotation(f, foot, w[hock, :3, :3].T @ rf, hist)
                w = world(f)
                errors.append(float(np.linalg.norm(w[foot, :3, 3] - goal)))
                row.append(dict(foot=foot, phase=phase, stance=not cycles or phase <= contact, target=goal.tolist(), up=up, pitch=pitch))
            frames.append(f)
            plan.append(row)
        corrections = {}
        for elbow, hand in [(8, 9), (12, 13)]:
            needed = []
            for f in frames[:-1]:
                w = world(f)
                points = [v.tolist() for b in [elbow, hand] for v in vs[b] @ w[b, :3, :3].T + w[b, :3, 3]]
                hinge = np.array(motionsecondary.clearance_rotation(points, w[elbow, :3, 3].tolist(), w[sk[elbow][1], :3, 0].tolist(), [-60, 0], -{0: 20, 1: 40, 2: 65, 3: 65, 4: 85}[slot]))
                needed.append(math.degrees(math.acos(np.clip((np.trace(hinge) - 1) / 2, -1, 1))))
            envelope = [max((needed[j] - 2 * min((i - j) % duration, (j - i) % duration) for j in range(duration))) for i in range(duration)]
            for t, f in enumerate(frames):
                matrix = rotation([-envelope[t % duration], 0, 0]) @ np.array(mmd.rot_matrix(*f[elbow][3:6]))
                set_rotation(f, elbow, matrix, hist)
            corrections[elbow] = envelope
        frames[-1][1:] = copy.deepcopy(frames[0][1:])
        channels = {(b, c) for b in [8, 12, 17, 18, 19, 21, 22, 23] for c in [3, 4, 5]}
        channels |= {(b, 5) for b in [7, 11]}
        if slot == 1:
            channels |= {(15, 7)}
            channels |= {(b, 3) for b in [1, 2, 14, 15]}
        animation = mmd.encode_anim(frames, n, loop_sample=0, tol=1, repeats=False) if slot == 1 else replace_channels(old.anims.anims[old.anims.table[33]], frames, 0, n, channels)
        player = mmd.AnimPlayer(animation, n, slot)
        decoded = []
        while player.tick(stop_at_infinite_loop=True):
            decoded.append(copy.deepcopy(player.pose))
        assert len(decoded) == duration + 1
        correction_history = {}
        for tick, pose in enumerate(decoded):
            for side, foot in enumerate([19, 23]):
                rf, _, _ = motionsecondary.rolling_foot(vs[foot].tolist(), rotation([0, -(1 if side == 0 else -1) * 5, 0]).tolist(), plan[tick][side]['pitch'])
                parent = world(pose)[sk[foot][1], :3, :3]
                set_rotation(pose, foot, parent.T @ np.array(rf), correction_history)
        decoded[-1][1:] = copy.deepcopy(decoded[0][1:])
        animation = replace_channels(animation, decoded, 0, n, {(b, c) for b in [19, 23] for c in [3, 4, 5]}, tolerance=0)
        selected_events = []
        if cycles:
            animation = _forward(animation, -distance, duration)
            payload = copy.deepcopy(next((e for _, kind, e in events if kind == 'sound')))
            for i in range(cycles * 2):
                tick = round(i * duration / (cycles * 2))
                event = dict(payload, frame=tick + 1)
                at = next((j for j, v in enumerate(animation.instrs) if v.get('frame', -1) > tick + 1), len(animation.instrs) - 1)
                animation.instrs.insert(at, event)
                selected_events.append(event)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(animation)
        reports.append(dict(foot_center_x=90, foot_center_z=100, clearance=8, slot=slot, period=duration, gait_period=period, cycles=cycles, contact=contact, speed=speed, root_cycle_travel=-distance, lift=lift, heel=heel, toe=toe, maximum_ankle_FK_error=max(errors), hand_elbow_corrections=corrections, plan=plan, channels=sorted(channels), footstep_events=selected_events))
    return (new, reports)

def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE or [b[1] for b in sk] != PARENTS:
        raise ValueError('Diaboromon requires its reviewed 24-bone source')
    n = len(sk)
    mmd.exe().skeleton[237] = sk
    mmd.exe().bone_count[237] = n
    old = mmd.MMD.parse(data, n)
    old.type = 237
    new, solver = _author(old, sk)
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = mmd.MMD.parse(result, n)
    actual.type = 237
    assert changed_programs(old, actual) == [0, 1, 2, 3, 4]
    assert old.tmd.build() == actual.tmd.build()
    native = old.anims.anims[old.anims.table[33]]
    first = animsheet.slot_frames(old, n, 33)[0][0]
    checks = []
    for row in solver:
        slot = row['slot']
        duration = row['period']
        channels = set(map(tuple, row['channels']))
        before = mmd.AnimPlayer(native, n, 33)
        after = mmd.AnimPlayer(actual.anims.anims[actual.anims.table[slot]], n, slot)
        cycle = []
        for t in range(duration * 9 + 1):
            assert before.tick() and after.tick()
            for bone in range(1, n):
                for c in range(9):
                    if (bone, c) not in channels:
                        reference = first[bone][c] if slot == 1 else before.pose[bone][c]
                        assert after.pose[bone][c] == reference, (slot, t, bone, c, 'protected native channel')
            assert list(after.root) == [0, 0, -row['speed'] * t], (slot, t, after.root)
            if t < duration:
                cycle.append(copy.deepcopy(after.pose))
            else:
                assert all(((after.pose[b][c] - cycle[t % duration][b][c]) % 4096 == 0 if c in [3, 4, 5] else after.pose[b][c] == cycle[t % duration][b][c] for b in range(1, n) for c in range(9))), (slot, t, 'cycle drift')
        events = [e for _, kind, e in animsheet.slot_frames(actual, n, slot)[2] if kind == 'sound']
        expected = row['footstep_events']
        assert events == expected, (slot, 'footstep events', events, expected)
        checks.append(dict(slot=slot, nine_cycles_stable=True, protected_native_channels_exact=True, native33_scales_and_joint_translations_exact_except_poor15TY=True, steady_root_speed=row['speed'], footstep_events_exact=True))
    storage = motionstorage.audit(result, n)
    assert storage['fits'], storage
    return (result, dict(species=237, source_sha256=SOURCE, output_sha256=hashlib.sha256(result).hexdigest(), changed_slots=[0, 1, 2, 3, 4], mesh_care_battle_private33_exact=True, checks=checks, solver=solver, storage=storage))
