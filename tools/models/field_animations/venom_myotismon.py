"""VenomMyotismon's heavy supported steps and native wing-assisted run.

Keep native chest/head/wing/tail performance. Ground the complete boot and calf
meshes, temper the carrier bounce, clear the tired fists and distal tail, and
retain native airborne leg recovery to keep huge boots behind the gauntlets.
Explicit recipe for the pinned 28-bone source.
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
from tools.models.field_animations.war_greymon import rotation, set_rotation

SOURCE = '9605e5ea9892be856a63e663d159e39c2e67e3f341c8b9a94d1ca5fdfc4cfe7e'
CHAINS = [(21, 22, 23), (24, 25, 26)]

def _forward(animation, distance, period):
    result = copy.deepcopy(animation)
    for instruction in result.instrs:
        if instruction['op'] == 'key':
            for group in instruction['bones']:
                if group['bone'] == 0:
                    group['vals'].pop('tz', None)
            instruction['bones'] = [g for g in instruction['bones'] if g['vals']]
    first = next((i for i in result.instrs if i['op'] == 'key' and i['frame'] == 1))
    first['bones'].append(dict(bone=0, div=period, vals={'tz': distance}))
    return result

def _parse(data, sk):
    mmd.exe().skeleton[212] = sk
    mmd.exe().bone_count[212] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = 212
    return model


def _walk_and_tired(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    rest = animsheet.slot_frames(old, n, 0)[0][0]
    rest[0] = [4096]*3 + [0]*6
    rw = np.array(mmd.bone_matrices(old, rest))
    chains = CHAINS
    vs = {b: np.array(old.tmd.obj_verts(sk[b][0]))[:, :3] for chain in chains for b in chain}
    report = []
    for slot in [2, 3]:
        fs, loop, events = animsheet.slot_frames(old, n, slot)
        duration = len(fs) - 1
        speed = 20 if slot == 2 else 14
        contact = 13 if slot == 2 else 15
        lift = 30 if slot == 2 else 20
        body = 300 if slot == 2 else 304
        amp = 0.2
        width = 95
        center = 20
        rock = 8
        poses = []
        hist = {}
        errs = []
        margin = []
        original_y = np.mean([f[17][7] for f in fs[:-1]])
        root = np.array([f[0][6:9] for f in fs])
        root[:, 2] = -speed * np.arange(len(fs))

        def at(t, axis):
            cy = math.floor(t / duration)
            phase = t - cy * duration
            i = min(int(phase), duration - 1)
            q = phase - i
            return cy * (root[-1, axis] - root[0, axis]) + root[i, axis] * (1 - q) + root[i + 1, axis] * q - root[0, axis]
        for t, source in enumerate(fs):
            f = copy.deepcopy(source)
            f[0] = [4096] * 3 + [0] * 6
            f[17][7] = round(-body + amp * (source[17][7] - original_y))
            for side, (hip, knee, foot) in enumerate(chains):
                start = math.floor((t - side * duration / 2) / duration) * duration + side * duration / 2
                phase = t - start
                travel = at(start, 2) - at(start + contact, 2)
                u = phase / contact
                if phase <= contact:
                    z = center - travel / 2 - (at(t, 2) - at(start, 2))
                    up = 2.0
                    pitch = -rock * math.cos(math.pi * u)
                    x = (1 if side == 0 else -1) * width - at(t, 0) + at(start, 0)
                else:
                    q = (phase - contact) / (duration - contact)
                    h = 6 * q ** 5 - 15 * q ** 4 + 10 * q ** 3
                    a = center + travel / 2 + at(start + contact, 2)
                    b = center - (at(start + duration, 2) - at(start + duration + contact, 2)) / 2 + at(start + duration, 2)
                    z = (1 - h) * a + h * b - at(t, 2)
                    up = 2 + lift * math.sin(math.pi * q) ** 2
                    pitch = rock * math.cos(math.pi * q)
                    x = (1 if side == 0 else -1) * width - at(t, 0) + at(start, 0) + (at(start + duration, 0) - at(start, 0)) * h
                flat = rotation([0, (-1 if side == 0 else 1) * 16, 0])
                rfoot, dz, sole = motionsecondary.rolling_foot(vs[foot].tolist(), flat.tolist(), pitch)
                rfoot = np.array(rfoot)
                z += dz
                w = np.array(mmd.bone_matrices(old, f))
                h = w[hip, :3, 3]
                a = np.linalg.norm(f[knee][6:9])
                b = np.linalg.norm(f[foot][6:9])
                dxz = (x - h[0]) ** 2 + (z - h[2]) ** 2
                reach = (a + b - 0.1) ** 2 - dxz
                assert reach > 0, (slot, t, foot, 'XZreach', reach)
                goal = np.array([x, 0.0, z])
                low = h[1] + 1
                high = h[1] + math.sqrt(reach)
                pole = np.array([0.35 if side == 0 else -0.35, 0.0, -1.0])

                def solve(y):
                    goal[1] = y
                    d = goal - h
                    dist = np.linalg.norm(d)
                    dire = d / dist
                    pp = pole - dire * (pole @ dire)
                    pp /= np.linalg.norm(pp)
                    along = (a * a - b * b + dist * dist) / (2 * dist)
                    joint = h + dire * along + pp * math.sqrt(max(0, a * a - along * along))
                    rhip, rshin = map(np.array, motionsecondary.native_plane_rotations([rw[v, :3, 3].tolist() for v in [hip, knee, foot]], [h.tolist(), joint.tolist(), goal.tolist()], [rw[v, :3, :3].tolist() for v in [hip, knee]]))
                    bottom = max(float((vs[knee] @ rshin.T + joint)[:, 1].max()), float((vs[foot] @ rfoot.T + goal)[:, 1].max()))
                    return (bottom + up, rhip, rshin)
                elo = solve(low)[0]
                ehi = solve(high)[0]
                assert elo <= 0 <= ehi, (slot, t, foot, 'Yreach', elo, ehi, h, goal)
                for _ in range(27):
                    mid = (low + high) / 2
                    if solve(mid)[0] > 0:
                        high = mid
                    else:
                        low = mid
                residual, rhip, rshin = solve((low + high) / 2)
                set_rotation(f, hip, w[sk[hip][1], :3, :3].T @ rhip, hist)
                w = np.array(mmd.bone_matrices(old, f))
                set_rotation(f, knee, w[hip, :3, :3].T @ rshin, hist)
                w = np.array(mmd.bone_matrices(old, f))
                set_rotation(f, foot, w[knee, :3, :3].T @ rfoot, hist)
                w = np.array(mmd.bone_matrices(old, f))
                errs.append(float(np.linalg.norm(w[foot, :3, 3] - goal)))
                margin.append(a + b - np.linalg.norm(goal - h))
            if slot == 3:
                for elbow, hand in [(4, 5), (7, 8)]:
                    w = np.array(mmd.bone_matrices(old, f))
                    desired = w[hand, :3, :3].copy()
                    rf = rotation([0, 0, (-1 if elbow == 4 else 1) * 10]) @ rotation([-65, 0, 0]) @ w[elbow, :3, :3]
                    set_rotation(f, elbow, w[sk[elbow][1], :3, :3].T @ rf, hist)
                    w = np.array(mmd.bone_matrices(old, f))
                    set_rotation(f, hand, w[elbow, :3, :3].T @ desired, hist)
            for hinge, bones, axis, limits in [(9, [9, 10, 11], [0, 0, 1], [-35, 0]), (13, [13, 14, 15], [0, 0, 1], [0, 35]), (20, [20, 27], [1, 0, 0], [0, 65])]:
                w = np.array(mmd.bone_matrices(old, f))
                points = np.concatenate([np.array(old.tmd.obj_verts(sk[b][0]))[:, :3] @ w[b, :3, :3].T + w[b, :3, 3] for b in bones])
                bias = np.array(motionsecondary.clearance_rotation(points.tolist(), w[hinge, :3, 3].tolist(), axis, limits, -12))
                set_rotation(f, hinge, w[sk[hinge][1], :3, :3].T @ bias @ w[hinge, :3, :3], hist)
            f[0] = copy.deepcopy(source[0])
            f[0][8] = -speed * t
            poses.append(f)
        poses[-1][1:] = copy.deepcopy(poses[0][1:])
        channels = {(17, 7)} | {(b, c) for chain in chains for b in chain for c in [3, 4, 5]} | {(b, c) for b in [9, 13, 20] + ([4, 5, 7, 8] if slot == 3 else []) for c in [3, 4, 5]}
        authored = replace_channels(old.anims.anims[old.anims.table[slot]], poses, loop, n, channels)
        authored = _forward(authored, -speed * duration, duration)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
        report.append(dict(slot=slot, maxerr=max(errs), margin=min(margin), root_speed=speed, body=body, contact=contact))
    return new, report

def _rest_and_run(old, new, sk):
    n = len(sk)
    chains = CHAINS
    vs = {b: np.array(old.tmd.obj_verts(sk[b][0]))[:, :3] for chain in chains for b in chain}
    checks = []
    def world(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, g))

    def solveleg(f, hip, knee, foot, x, z, rf, up, hist, reference=None):
        w = world(f)
        h = w[hip, :3, 3]
        a = np.linalg.norm(f[knee][6:9])
        b = np.linalg.norm(f[foot][6:9])
        dxz = (x - h[0]) ** 2 + (z - h[2]) ** 2
        reach = (a + b - 0.1) ** 2 - dxz
        assert reach > 0, ('XZreach', hip, reach)
        goal = np.array([x, 0.0, z])
        low = h[1] + 1
        high = h[1] + math.sqrt(reach)
        pole = np.array([0.35 if hip == 21 else -0.35, 0.0, -1.0]) if reference is None else reference[knee, :3, 3] - reference[hip, :3, 3]
        ref = rw if reference is None else reference

        def solve(y):
            goal[1] = y
            d = goal - h
            dist = np.linalg.norm(d)
            dire = d / dist
            pp = pole - dire * (pole @ dire)
            pp /= np.linalg.norm(pp)
            along = (a * a - b * b + dist * dist) / (2 * dist)
            joint = h + dire * along + pp * math.sqrt(max(0, a * a - along * along))
            rh, rs = map(np.array, motionsecondary.native_plane_rotations([ref[v, :3, 3].tolist() for v in [hip, knee, foot]], [h.tolist(), joint.tolist(), goal.tolist()], [ref[v, :3, :3].tolist() for v in [hip, knee]]))
            bottom = max(float((vs[knee] @ rs.T + joint)[:, 1].max()), float((vs[foot] @ rf.T + goal)[:, 1].max()))
            return (bottom + up, rh, rs)
        elo = solve(low)[0]
        ehi = solve(high)[0]
        assert elo <= 0 <= ehi, ('Yreach', hip, elo, ehi, h, goal, up)
        for _ in range(27):
            mid = (low + high) / 2
            if solve(mid)[0] > 0:
                high = mid
            else:
                low = mid
        residual, rh, rs = solve((low + high) / 2)
        set_rotation(f, hip, w[sk[hip][1], :3, :3].T @ rh, hist)
        w = world(f)
        set_rotation(f, knee, w[hip, :3, :3].T @ rs, hist)
        w = world(f)
        set_rotation(f, foot, w[knee, :3, :3].T @ rf, hist)
        w = world(f)
        return float(np.linalg.norm(w[foot, :3, 3] - goal))

    def clear(f, hist):
        for hinge, bones, axis, limits in [(9, [9, 10, 11], [0, 0, 1], [-35, 0]), (13, [13, 14, 15], [0, 0, 1], [0, 35]), (20, [20, 27], [1, 0, 0], [0, 65])]:
            w = world(f)
            pts = np.concatenate([np.array(old.tmd.obj_verts(sk[b][0]))[:, :3] @ w[b, :3, :3].T + w[b, :3, 3] for b in bones])
            r = np.array(motionsecondary.clearance_rotation(pts.tolist(), w[hinge, :3, 3].tolist(), axis, limits, -12))
            set_rotation(f, hinge, w[sk[hinge][1], :3, :3].T @ r @ w[hinge, :3, :3], hist)
    rw = world(animsheet.slot_frames(old, n, 0)[0][0])
    for slot in [0, 4]:
        fs, loop, events = animsheet.slot_frames(old, n, slot)
        duration = len(fs) - 1
        hist = {}
        poses = []
        errs = []
        armbias = []
        for t, source in enumerate(fs):
            f = copy.deepcopy(source)
            f[0] = [4096] * 3 + [0] * 6
            native = world(f)
            if slot == 4:
                f[17][7] = round(-345 + 0.6 * (source[17][7] + 382))
            for side, (hip, knee, foot) in enumerate(chains):
                if slot == 0:
                    x, z = native[foot, [0, 2], 3]
                    rf = native[foot, :3, :3]
                    up = 2.0
                    reference = native
                else:
                    period = 20
                    contact = 2
                    speed = 52
                    phase = (t - side * 10) % period
                    center = 20
                    half = speed * contact / 2
                    if phase <= contact:
                        z = center - half + speed * phase
                        up = 2
                        pitch = -8 * math.cos(math.pi * phase / contact)
                    else:
                        q = (phase - contact) / (period - contact)
                        span = period - contact
                        a = center + half
                        b = center - half
                        z = (2 * q ** 3 - 3 * q * q + 1) * a + (q ** 3 - 2 * q * q + q) * span * speed + (-2 * q ** 3 + 3 * q * q) * b + (q ** 3 - q * q) * span * speed
                        up = 2 + 65 * math.sin(math.pi * q) ** 2 + max(0, -f[17][7] - 345)
                        pitch = 8 * math.cos(math.pi * q) + 25 * math.sin(math.pi * q) ** 2
                    x = (1 if side == 0 else -1) * 95
                    flat = rotation([0, (-1 if side == 0 else 1) * 16, 0])
                    rf, dz, sole = motionsecondary.rolling_foot(vs[foot].tolist(), flat.tolist(), pitch)
                    rf = np.array(rf)
                    z += dz
                    reference = None
                try:
                    errs.append(solveleg(f, hip, knee, foot, x, z, rf, up, hist, reference))
                except Exception as e:
                    raise ValueError((slot, t, str(e))) from e
                # Preserve the original folded recovery between the brief
                # landing corrections. A full replacement collides with fists.
                if slot == 4:
                    phase = (t - side * 10) % 20
                    if phase <= 2:
                        weight = 1.0
                    elif phase < 5:
                        q = (phase - 2) / 3
                        weight = 1 - (3 * q * q - 2 * q ** 3)
                    elif phase <= 17:
                        weight = 0.0
                    else:
                        q = (phase - 17) / 3
                        weight = 3 * q * q - 2 * q ** 3
                    for b in [hip, knee, foot]:
                        if weight == 0:
                            f[b][3:6] = copy.deepcopy(source[b][3:6])
                            hist[b] = list(source[b][3:6])
                        elif weight < 1:
                            r = mmd.quat_matrix(mmd._slerp(mmd.quat(*source[b][3:6]), mmd.quat(*f[b][3:6]), weight))
                            set_rotation(f, b, np.array(r), hist)
            if slot == 4:
                for elbow, hand in [(4, 5), (7, 8)]:
                    w = world(f)
                    o = w[elbow, :3, 3]
                    rhand = w[hand, :3, :3].copy()
                    ve = np.array(old.tmd.obj_verts(sk[elbow][0]))[:, :3]
                    vh = np.array(old.tmd.obj_verts(sk[hand][0]))[:, :3]

                    def bottom(angle):
                        r = rotation([angle, 0, 0]) @ w[elbow, :3, :3]
                        hw = o + r @ np.array(f[hand][6:9])
                        return max(float((ve @ r.T + o)[:, 1].max()), float((vh @ rhand.T + hw)[:, 1].max()))
                    angles = sorted(range(-30, 31), key=abs)
                    angle = next((a for a in angles if bottom(a) <= -16), None)
                    assert angle is not None, (slot, t, hand, 'floor')
                    rf = rotation([angle, 0, 0]) @ w[elbow, :3, :3]
                    set_rotation(f, elbow, w[sk[elbow][1], :3, :3].T @ rf, hist)
                    w = world(f)
                    set_rotation(f, hand, w[elbow, :3, :3].T @ rhand, hist)
                    armbias.append(angle)
            clear(f, hist)
            f[0] = copy.deepcopy(source[0])
            if slot == 4:
                f[0][8] = -52 * t
            poses.append(f)
        poses[-1][1:] = copy.deepcopy(poses[0][1:])
        bones = [b for c in chains for b in c] + [9, 13, 20] + ([4, 5, 7, 8] if slot == 4 else [])
        channels = {(b, c) for b in bones for c in [3, 4, 5]} | ({(17, 7)} if slot == 4 else set())
        authored = replace_channels(old.anims.anims[old.anims.table[slot]], poses, loop, n, channels)
        if slot == 4:
            authored = _forward(authored, -52 * duration, duration)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
        checks.append(dict(slot=slot, max_ankle_error=max(errs), arm_bias_minmax=[min(armbias), max(armbias)] if armbias else []))
    return new, checks


def _footsteps(animation, period):
    result = copy.deepcopy(animation)
    sounds = [i for i in result.instrs if i['op'] == 'sound']
    assert len(sounds) == 2 and all((s['bank'], s['note']) == (1, 13) for s in sounds)
    result.instrs = [i for i in result.instrs if i['op'] != 'sound']
    for tick, sound in zip([0, period//2], sounds):
        event = dict(sound, frame=tick+1)
        at = next((i for i, ins in enumerate(result.instrs) if ins.get('frame', -1) > tick+1), len(result.instrs)-1)
        result.instrs.insert(at, event)
    return result


def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE or len(sk) != 28:
        raise ValueError('VenomMyotismon recipe requires the pinned reviewed 28-bone source')
    old = _parse(data, sk)
    new, walk_checks = _walk_and_tired(old, sk)
    new, other_checks = _rest_and_run(old, new, sk)
    for slot in [2, 3]:
        original = new.anims.anims[new.anims.table[slot]]
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(_footsteps(original, {2: 22, 3: 26}[slot]))
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = _parse(result, sk)
    assert changed_programs(old, actual) == [0, 2, 3, 4]
    assert old.tmd.build() == actual.tmd.build()
    checks = []
    for slot in [0, 2, 3, 4]:
        before_anim = old.anims.anims[old.anims.table[slot]]
        after_anim = actual.anims.anims[actual.anims.table[slot]]
        source, loop, source_events = animsheet.slot_frames(old, 28, slot)
        decoded, actual_loop, selected_events = animsheet.slot_frames(actual, 28, slot)
        period = len(source)-1
        assert len(decoded) == len(source) and loop == actual_loop == 0
        assert [i for i in before_anim.instrs if i['op'] not in ('key', 'sound')] == [i for i in after_anim.instrs if i['op'] not in ('key', 'sound')]
        assert [(t, kind, event) for t, kind, event in source_events if kind != 'sound'] == [(t, kind, event) for t, kind, event in selected_events if kind != 'sound']
        bones = [b for chain in CHAINS for b in chain] + [9, 13, 20]
        if slot in [3, 4]:
            bones += [4, 5, 7, 8]
        channels = {(b, c) for b in bones for c in [3, 4, 5]}
        if slot:
            channels.add((17, 7))
        before = mmd.AnimPlayer(before_anim, 28, slot)
        after = mmd.AnimPlayer(after_anim, 28, slot)
        cycle_poses, root_steps = [], []
        native_air_error = 0
        for tick in range(period*9+1):
            assert before.tick() and after.tick()
            assert before.base[:2] == after.base[:2]
            for bone in range(28):
                for channel in range(9):
                    if (bone, channel) not in channels:
                        assert before.pose[bone][channel] == after.pose[bone][channel], (slot, tick, bone, channel)
            if tick < period:
                cycle_poses.append(copy.deepcopy(after.pose))
            else:
                assert after.pose == cycle_poses[tick % period], (slot, tick, 'cyclic drift')
            if slot == 4:
                for side, chain in enumerate(CHAINS):
                    phase = (tick-side*10) % 20
                    if 5 <= phase <= 17:
                        for bone in chain:
                            for channel in [3, 4, 5]:
                                delta = (after.pose[bone][channel]-before.pose[bone][channel]+2048) % 4096-2048
                                native_air_error = max(native_air_error, abs(delta))
            root_steps.append(after.base[2])
        if slot:
            speed = {2: 20, 3: 14, 4: 52}[slot]
            assert set(root_steps[1:]) == {-speed}
            assert after.root[2] == -speed*period*9
        else:
            assert before.base == after.base == [0, 0, 0]
        assert native_air_error <= 1, (slot, native_air_error)
        checks.append(dict(slot=slot, period=period, native_air_max_rotation_error_sdk=native_air_error, unselected_channels_limb_translations_scales_exact_nine_cycles=True,
                           exact_repeat_nine_cycles=True, original_root_XY_exact=True,
                           forward_units_per_tick={0: 0, 2: 20, 3: 14, 4: 52}[slot],
                           original_events_except_walk_tired_step_timing_exact=True))
    storage = motionstorage.audit(result, 28)
    assert storage['fits'], storage
    return result, dict(species=212, source_sha256=SOURCE,
                        output_sha256=hashlib.sha256(result).hexdigest(), changed_slots=[0, 2, 3, 4],
                        mesh_skeleton_private33_care_battle_exact=True,
                        checks=checks, walk_solver=walk_checks, rest_run_solver=other_checks, storage=storage)
