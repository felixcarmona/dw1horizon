"""Vikemon's heavy strides with its full native face and equipment performance.

Fixed-length planted legs, a bounded cloth hinge and small shoulder counter-swing
preserve the 104-tick upper performance while clearing the ground.
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
from tools.models.field_animations.aero_veedramon import _forward
from motiondiscidentity import changed_programs
from tools.models.field_animations.war_greymon import rotation, set_rotation
SOURCE = '126352991e635354d18d20a214da8d5661f6f2b49ee53b75edf7f1158bc848b8'

def _parse(data, sk):
    mmd.exe().skeleton[220] = sk
    mmd.exe().bone_count[220] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = 220
    return model

def _author(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    vs = {b: np.array(old.tmd.obj_verts(oi))[:, :3] for b, (oi, _) in enumerate(sk) if oi >= 0}

    def world(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, g))
    # Retain the full facial, equipment and tail timing. The original private
    # program remains unchanged; only primary field programs are rebuilt.
    native, loop, _ = animsheet.slot_frames(old, n, 33)
    mean = np.array(native[:-1])[:, 11, 7].mean()
    reports = []
    for slot in [0, 2, 3, 4]:
        fs = native
        duration = len(fs) - 1
        period = {0: 104, 2: 26, 3: 26, 4: 13}[slot]
        contact = {0: 104, 2: 16, 3: 17, 4: 4}[slot]
        speed = {0: 0, 2: 14, 3: 10, 4: 42}[slot]
        lift = {0: 0, 2: 24, 3: 18, 4: 36}[slot]
        rock = {0: 0, 2: 7, 3: 5, 4: 10}[slot]
        poses = []
        hist = {}
        errs = []

        def leg(f, hip, knee, foot, x, z, rf, up):
            w = world(f)
            h = w[hip, :3, 3]
            a = np.linalg.norm(f[knee][6:9])
            b = np.linalg.norm(f[foot][6:9])
            reach = (a + b - 0.1) ** 2 - (x - h[0]) ** 2 - (z - h[2]) ** 2
            assert reach > 0, (slot, t, hip, 'XZreach', reach)
            low = h[1] + 1
            high = h[1] + math.sqrt(reach)
            goal = np.array([x, 0.0, z])
            # Separate knee planes clear the right fist and the hanging cloth.
            pole = np.array([0.05 if hip == 12 else -0.35, 0.0, -1.0])

            def solve(y):
                goal[1] = y
                d = goal - h
                dist = np.linalg.norm(d)
                dire = d / dist
                pp = pole - dire * (pole @ dire)
                pp /= np.linalg.norm(pp)
                along = (a * a - b * b + dist * dist) / (2 * dist)
                joint = h + dire * along + pp * math.sqrt(max(0, a * a - along * along))
                rh, rs = map(np.array, motionsecondary.native_plane_rotations([native_ref[v, :3, 3].tolist() for v in [hip, knee, foot]], [h.tolist(), joint.tolist(), goal.tolist()], [native_ref[v, :3, :3].tolist() for v in [hip, knee]]))
                bottom = max(float((vs[knee] @ rs.T + joint)[:, 1].max()), float((vs[foot] @ rf.T + goal)[:, 1].max()))
                return (bottom + up, rh, rs)
            elo = solve(low)[0]
            ehi = solve(high)[0]
            assert elo <= 0 <= ehi, (slot, t, hip, 'Yreach', elo, ehi, h, goal, up)
            for _ in range(27):
                mid = (low + high) / 2
                if solve(mid)[0] > 0:
                    high = mid
                else:
                    low = mid
            residual, rh, rs = solve((low + high) / 2)
            set_rotation(f, hip, w[11, :3, :3].T @ rh, hist)
            w = world(f)
            set_rotation(f, knee, w[hip, :3, :3].T @ rs, hist)
            w = world(f)
            set_rotation(f, foot, w[knee, :3, :3].T @ rf, hist)
            errs.append(float(np.linalg.norm(world(f)[foot, :3, 3] - goal)))
        for t, source in enumerate(fs):
            native_ref = world(source)
            f = copy.deepcopy(source)
            f[0] = [4096] * 3 + [0] * 6
            if not slot:
                w = world(f)
                bottom = max((float((vs[b] @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max()) for b in [13, 14, 16, 17]))
                f[11][7] -= math.ceil(max(0, bottom + 3))
            else:
                f[11][7] = round({2: -225, 3: -220, 4: -230}[slot] + 0.5 * (source[11][7] - mean))
                # Keep a tired head posture over the complete native curve.
                if slot == 3:
                    f[3][3] += round(12 * 4096 / 360)
                # A small stride counter-swing adds weight without speeding
                # up the native upper-body performance.
                swing = math.sin(2 * math.pi * t / period)
                f[1][5] += round(2.0 * 4096 / 360 * swing)
                for arm, sign in [(5, 1), (8, -1)]:
                    f[arm][3] += round(sign * {2: 7, 3: 4, 4: 12}[slot] * 4096 / 360 * swing)
                if slot == 4:
                    q = t % (period / 2)
                    f[11][7] += round(3 * math.sin(math.pi * q / contact) ** 2 if q <= contact else -8 * math.sin(math.pi * (q - contact) / (period / 2 - contact)) ** 2)
                for side, (hip, knee, foot) in enumerate([(12, 13, 14), (15, 16, 17)]):
                    sign = 1 if side == 0 else -1
                    offset = side * period / 2
                    start = math.floor((t - offset) / period) * period + offset
                    phase = t - start
                    half = speed * contact / 2
                    center = 30
                    if phase <= contact:
                        z = center - half + speed * phase
                        x = sign * 175
                        up = 4
                        pitch = -rock * math.cos(math.pi * phase / contact)
                    else:
                        q = (phase - contact) / (period - contact)
                        sm = 6 * q ** 5 - 15 * q ** 4 + 10 * q ** 3
                        z = (center + half) * (1 - sm) + (center - half) * sm + (period - contact) * speed * q * (1 - q) * (1 - 2 * q) ** 5
                        x = sign * (175 + 8 * math.sin(math.pi * q) ** 2)
                        up = 4 + lift * math.sin(math.pi * q)
                        pitch = rock * math.cos(math.pi * q) + 10 * math.sin(math.pi * q) ** 2
                    rf, dz, _ = motionsecondary.rolling_foot(vs[foot].tolist(), rotation([0, -sign * 8, 0]).tolist(), pitch)
                    leg(f, hip, knee, foot, x, z + dz, np.array(rf), up)
            for hand in [7, 10]:
                w = world(f)
                points = vs[hand] @ w[hand, :3, :3].T + w[hand, :3, 3]
                bias = np.array(motionsecondary.clearance_rotation(points.tolist(), w[hand, :3, 3].tolist(), [1, 0, 0], [-50, 0], -8))
                set_rotation(f, hand, w[sk[hand][1], :3, :3].T @ bias @ w[hand, :3, :3], hist)
            w = world(f)
            points = vs[25] @ w[25, :3, :3].T + w[25, :3, 3]
            bias = np.array(motionsecondary.clearance_rotation(points.tolist(), w[25, :3, 3].tolist(), [1, 0, 0], [0, 50], -8))
            set_rotation(f, 25, w[11, :3, :3].T @ bias @ w[25, :3, :3], hist)
            f[0] = copy.deepcopy(source[0])
            f[0][8] = -speed * t
            poses.append(f)
        poses[-1][1:] = copy.deepcopy(poses[0][1:])
        bones = [7, 10, 25] + ([1, 5, 8] + list(range(12, 18)) if slot else []) + ([3] if slot == 3 else [])
        channels = {(11, 7)} | {(b, c) for b in bones for c in [3, 4, 5]}
        authored = replace_channels(old.anims.anims[old.anims.table[33]], poses, loop, n, channels)
        if slot:
            authored = _forward(authored, -speed * duration, duration)
            event = next((i for i in old.anims.anims[old.anims.table[slot]].instrs if i['op'] == 'sound'))
            # Thirteen-tick running alternates six/seven-tick half strides;
            # sound quantization stays within half a logic tick of contact.
            for tick in sorted({round(k * period / 2) for k in range(round(duration / (period / 2)))}):
                e = dict(event, frame=tick + 1)
                at = next((j for j, i in enumerate(authored.instrs) if i.get('frame', -1) > tick + 1), len(authored.instrs) - 1)
                authored.instrs.insert(at, e)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
        reports.append(dict(slot=slot, period=duration, gait=period, contact=contact, speed=speed, channels=sorted(channels), max_ankle_error=max(errs, default=0)))
    return (new, reports)

def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE or len(sk) != 28:
        raise ValueError('Vikemon requires the reviewed pinned 28-bone source')
    old = _parse(data, sk)
    new, solver = _author(old, sk)
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = _parse(result, sk)
    assert changed_programs(old, actual) == [0, 2, 3, 4]
    assert old.tmd.build() == actual.tmd.build()
    native = old.anims.anims[old.anims.table[33]]
    source, loop, events = animsheet.slot_frames(old, 28, 33)
    assert len(source) == 105 and loop == 0
    checks = []
    for row in solver:
        slot = row['slot']
        selected = actual.anims.anims[actual.anims.table[slot]]
        decoded, newloop, newevents = animsheet.slot_frames(actual, 28, slot)
        assert len(decoded) == 105 and newloop == 0
        assert [i for i in native.instrs if i['op'] not in ('key', 'sound')] == [i for i in selected.instrs if i['op'] not in ('key', 'sound')]
        assert [(t, k, e) for t, k, e in events if k != 'sound'] == [(t, k, e) for t, k, e in newevents if k != 'sound']
        channels = {tuple(c) for c in row['channels']}
        before = mmd.AnimPlayer(native, 28, 33)
        after = mmd.AnimPlayer(selected, 28, slot)
        cycle = []
        for tick in range(104 * 9 + 1):
            assert before.tick() and after.tick()
            assert before.base[:2] == after.base[:2]
            for bone in range(28):
                for channel in range(9):
                    if (bone, channel) not in channels:
                        assert before.pose[bone][channel] == after.pose[bone][channel], (slot, tick, bone, channel)
            if tick < 104:
                cycle.append(copy.deepcopy(after.pose))
            else:
                assert after.pose == cycle[tick % 104], (slot, tick, 'cyclic drift')
        assert after.root[2] == -row['speed'] * 104 * 9
        sounds = [i for i in selected.instrs if i['op'] == 'sound']
        original_sounds = [i for i in old.anims.anims[old.anims.table[slot]].instrs if i['op'] == 'sound']
        if slot:
            assert original_sounds
            assert all(((i['bank'], i['note']) == (original_sounds[0]['bank'], original_sounds[0]['note']) for i in sounds))
        expected_ticks = [] if not slot else sorted({round(k * row['gait'] / 2) for k in range(round(104 / (row['gait'] / 2)))})
        assert [i['frame'] - 1 for i in sounds] == expected_ticks
        checks.append(dict(slot=slot, source_template_slot=33, duration=104, old_primary_duration=len(animsheet.slot_frames(old, 28, slot)[0]) - 1, gait_period=row['gait'], forward_units_per_tick=row['speed'], root_XY_native=True, unselected_native33_channels_exact_nine_cycles=True, limb_translations_scales_exact=True, changed_pose_repeat_exact_nine_cycles=True, native33_non_sound_controls_exact=True, footstep_ticks=expected_ticks))
    storage = motionstorage.audit(result, 28)
    assert storage['fits'], storage
    return (result, dict(species=220, source_sha256=SOURCE, output_sha256=hashlib.sha256(result).hexdigest(), changed_slots=[0, 2, 3, 4], mesh_skeleton_private33_care_battle_exact=True, restored_native_upper_period=104, checks=checks, solver=solver, storage=storage))
