"""Salamon's planted puppy steps, bounding run and stable golden collar.

Keep the native idle and each moving action's facial and ear performance.
Reviewed fixed joint spacing prevents overlapping fur pieces; the collar keeps
its native rigid attachment instead of receiving an imported jaw-like cycle.
Walk/condition/run travel 15/10/35 units per tick with 4/10/4-tick gait
periods and 1.6/2/0.8-tick contacts; program durations remain 16/20/16.
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
from motiontailspace import interpolate_pose
from tools.models.field_animations.aero_veedramon import _forward
from motiondiscidentity import changed_programs
from tools.models.field_animations.war_greymon import rotation, set_rotation
SOURCE = '29faa5a38d25bdfc7610aef3d840c6211f3df72568a6284ff9c3ae47e6cabb8e'

def _parse(data, sk):
    mmd.exe().skeleton[221] = sk
    mmd.exe().bone_count[221] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = 221
    return model

def _author(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    vs = {b: np.array(old.tmd.obj_verts(oi))[:, :3] for b, (oi, _) in enumerate(sk) if oi >= 0}
    chains = [(7, 8, 9), (10, 11, 12), (14, 15, 16), (17, 18, 19)]

    def world(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, g))
    # Restore the complete idle, while retaining the moving actions' own
    # facial and ear curves at their reviewed stride cadences.
    native, loop, _ = animsheet.slot_frames(old, n, 33)
    mean = np.array(native[:-1])[:, 13, 7].mean()
    reports = []
    for slot in [0, 2, 3, 4]:
        period = {0: 91, 2: 4, 3: 10, 4: 4}[slot]
        contact = {0: 91, 2: 1.6, 3: 2, 4: 0.8}[slot]
        speed = {0: 0, 2: 15, 3: 10, 4: 35}[slot]
        lift = {0: 0, 2: 5, 3: 1.5, 4: 8}[slot]
        rock = {0: 0, 2: 4, 3: 3, 4: 6}[slot]
        if slot:
            original = animsheet.slot_frames(old, n, slot)[0]
            own = len(original) - 1
            fs = []
            target = {2: 16, 3: 20, 4: 16}[slot]
            for tick in range(target + 1):
                q = tick * own / target
                i = min(int(q), own - 1)
                ref = interpolate_pose(original[i], original[i + 1], round((q - i) * 4096))
                ref[0] = [4096] * 3 + [0] * 6
                fs.append(ref)
            template = mmd.encode_anim(fs, n, loop_sample=0, tol=0, repeats=False)
        else:
            fs = native
            template = old.anims.anims[old.anims.table[33]]
        duration = len(fs) - 1
        mean = np.array(fs[:-1])[:, 13, 7].mean()
        poses = []
        hist = {}
        errs = []

        def leg(f, hip, knee, foot, x, z, rf, up):
            w = world(f)
            h = w[hip, :3, 3]
            a = np.linalg.norm(f[knee][6:9])
            b = np.linalg.norm(f[foot][6:9])
            reach = (a + b - 0.05) ** 2 - (x - h[0]) ** 2 - (z - h[2]) ** 2
            assert reach > 0, (slot, t, hip, 'XZreach', reach, h.tolist(), x, z)
            low = h[1] + max(0.1, math.sqrt(max(0, (abs(a - b) + 0.05) ** 2 - (x - h[0]) ** 2 - (z - h[2]) ** 2)))
            high = h[1] + math.sqrt(reach)
            goal = np.array([x, 0.0, z])
            pole = np.array([1.0 if hip == 7 else -1.0, 0.0, 0.15] if hip in (7, 10) else [0.35 if hip == 14 else -0.35, 0.0, 1.0])

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
            assert elo <= 0 <= ehi, (slot, t, hip, 'Yreach', elo, ehi, h.tolist(), goal.tolist(), up)
            for _ in range(27):
                mid = (low + high) / 2
                if solve(mid)[0] > 0:
                    high = mid
                else:
                    low = mid
            residual, rh, rs = solve((low + high) / 2)
            if slot == 2 and hip == 10:
                axis = rh @ np.array(f[knee][6:9])
                axis /= np.linalg.norm(axis)
                rh = np.array(motionsecondary.R.from_axis_angle(axis.tolist(), math.radians(30))) @ rh
            set_rotation(f, hip, w[sk[hip][1], :3, :3].T @ rh, hist)
            w = world(f)
            set_rotation(f, knee, w[hip, :3, :3].T @ rs, hist)
            w = world(f)
            set_rotation(f, foot, w[knee, :3, :3].T @ rf, hist)
            error = float(np.linalg.norm(world(f)[foot, :3, 3] - goal))
            assert error < 0.1, (slot, t, foot, error)
            errs.append(error)
        for t, source in enumerate(fs):
            ref = copy.deepcopy(native[0])
            if slot:
                # The IK reference must use the same fixed joint spacing as
                # the authored pose, including the angled rear paw stems.
                for child in [8, 9, 11, 12, 16, 19]:
                    ref[child][7] += 4
                if slot == 4:
                    ref[19][7] += 2
            native_ref = world(ref)
            f = copy.deepcopy(source)
            f[0] = [4096] * 3 + [0] * 6
            if not slot:
                w = world(f)
                bottom = max((float((vs[b] @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max()) for b in vs))
                f[13][7] -= math.ceil(max(0, bottom + 2))
            else:
                for root, sign in [(7, 1), (10, -1), (14, 1), (17, -1)]:
                    f[root][6] += sign * 6
                for child in [8, 9, 11, 12, 16, 19]:
                    f[child][7] += 4
                # Mesh 20 is the golden collar, not a jaw. Retain its native
                # rigid attachment while the head continues its own motion.
                f[20][3:6] = copy.deepcopy(native[0][20][3:6])
                if slot in [3, 4]:
                    for root in [7, 10]:
                        f[root][8] -= 2 if slot == 3 else 4
                if slot == 4:
                    f[14][7] -= 1
                    f[17][7] -= 3
                    f[19][7] += 2
                f[13][7] = round({2: -62, 3: -63, 4: -60}[slot] + 0.35 * (source[13][7] - mean))
                if slot == 4:
                    q = t % (period / 2)
                    f[13][7] += round(2 * (1 - 0.5 * q / contact) if q <= contact else -3 * math.sin(math.pi * (q - contact) / (period / 2 - contact)) ** 2)
                else:
                    f[13][7] += round(0.8 * math.cos(4 * math.pi * t / period))
                for index, (hip, knee, foot) in enumerate(chains):
                    right = index in (0, 2)
                    front = index < 2
                    sign = 1 if right else -1
                    offset = {0: 0, 1: period / 2, 2: 3 * period / 4, 3: period / 4}[index] if slot != 4 else {0: 0, 1: 0.4, 2: period / 2, 3: period / 2 + 0.4}[index]
                    start = math.floor((t - offset) / period) * period + offset
                    phase = t - start
                    half = speed * contact / 2
                    center = {2: -34, 3: -36, 4: -39}[slot] if front else {2: 36, 3: 34, 4: 33}[slot]
                    spanx = 33 if front else 34
                    if phase <= contact:
                        z = center - half + speed * phase
                        x = sign * spanx
                        up = 2
                        pitch = -rock * math.cos(math.pi * phase / contact)
                    else:
                        q = (phase - contact) / (period - contact)
                        sm = 6 * q ** 5 - 15 * q ** 4 + 10 * q ** 3
                        z = (center + half) * (1 - sm) + (center - half) * sm + (period - contact) * speed * q * (1 - q) * (1 - 2 * q) ** 5
                        x = sign * (spanx + 2 * math.sin(math.pi * q) ** 2)
                        up = 2 + lift * math.sin(math.pi * q)
                        pitch = rock * math.cos(math.pi * q) + ({2: 7, 3: 5, 4: 25}[slot] if front or slot != 4 else -25) * math.sin(math.pi * q) ** 2
                    rf, dz, _ = motionsecondary.rolling_foot(vs[foot].tolist(), rotation([0, -sign * 5, 0]).tolist(), pitch)
                    leg(f, hip, knee, foot, x, z + dz, np.array(rf), up)
            f[0] = [4096] * 3 + [0] * 6
            f[0][8] = -speed * t
            poses.append(f)
        poses[-1][1:] = copy.deepcopy(poses[0][1:])
        bones = ([b for chain in chains for b in chain] if slot else []) + ([20] if slot else [])
        channels = {(13, 7)} | {(b, c) for b in bones for c in [3, 4, 5]} | ({(b, 6) for b in [7, 10, 14, 17]} | {(b, 7) for b in [8, 9, 11, 12, 16, 19]} | ({(7, 8), (10, 8)} if slot in [3, 4] else set()) | ({(14, 7), (17, 7)} if slot == 4 else set()) if slot else set())
        authored = replace_channels(template, poses, loop, n, channels)
        authored.instrs = [i for i in authored.instrs if i['op'] != 'sound']
        if slot:
            authored = _forward(authored, -speed * duration, duration)
            event = next((i for i in old.anims.anims[old.anims.table[slot]].instrs if i['op'] == 'sound'))
            sound_offsets = [0, period / 2] if slot == 4 else [0, period / 4, period / 2, 3 * period / 4]
            for tick in sorted({round(cycle * period + offset) for cycle in range(duration // period) for offset in sound_offsets}):
                e = dict(event, frame=tick + 1)
                at = next((j for j, i in enumerate(authored.instrs) if i.get('frame', -1) > tick + 1), len(authored.instrs) - 1)
                authored.instrs.insert(at, e)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
        reports.append(dict(slot=slot, period=duration, gait=period, contact=contact, speed=speed, channels=sorted(channels), max_ankle_error=max(errs, default=0)))
    return (new, reports)

def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE or len(sk) != 21:
        raise ValueError('Salamon requires the reviewed pinned 21-bone source')
    old = _parse(data, sk)
    new, solver = _author(old, sk)
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = _parse(result, sk)
    assert changed_programs(old, actual) == [0, 2, 3, 4]
    assert old.tmd.build() == actual.tmd.build()
    native = animsheet.slot_frames(old, 21, 33)[0]
    assert len(native) == 92
    checks = []
    for row in solver:
        slot = row['slot']
        duration = row['period']
        channels = {tuple(c) for c in row['channels']}
        source = animsheet.slot_frames(old, 21, slot if slot else 33)[0]
        own = len(source) - 1
        expected = []
        for tick in range(duration + 1):
            q = tick * own / duration
            index = min(int(q), own - 1)
            pose = interpolate_pose(source[index], source[index + 1], round((q - index) * 4096))
            pose[0] = [4096] * 3 + [0] * 6
            expected.append(pose)
        selected = actual.anims.anims[actual.anims.table[slot]]
        after = mmd.AnimPlayer(selected, 21, slot)
        before = mmd.AnimPlayer(mmd.encode_anim(expected, 21, loop_sample=0, tol=0, repeats=False), 21, slot)
        cycle = []
        offsets = {}
        maximum = 0
        for tick in range(duration * 9 + 1):
            assert before.tick() and after.tick()
            for bone in range(1, 21):
                for channel in range(9):
                    if (bone, channel) not in channels:
                        error = abs(after.pose[bone][channel] - before.pose[bone][channel])
                        maximum = max(maximum, error)
                        assert error <= 1, (slot, tick, bone, channel, error)
                    elif channel >= 6 and (bone, channel) != (13, 7):
                        delta = after.pose[bone][channel] - before.pose[bone][channel]
                        if tick == 0:
                            offsets[bone, channel] = delta
                        assert delta == offsets[bone, channel], (slot, tick, bone, channel, 'joint spacing changed within a clip')
            if slot:
                assert after.pose[20][3:6] == native[0][20][3:6]
            if tick < duration:
                cycle.append(copy.deepcopy(after.pose))
            else:
                assert after.pose == cycle[tick % duration], (slot, tick, 'cyclic drift')
        assert after.root == [0, 0, -row['speed'] * duration * 9]
        sounds = [i for i in selected.instrs if i['op'] == 'sound']
        assert all(((i['bank'], i['note']) == (1, 20) for i in sounds))
        offsets_sound = [0, row['gait'] / 2] if slot == 4 else [0, row['gait'] / 4, row['gait'] / 2, 3 * row['gait'] / 4]
        expected_ticks = [] if not slot else sorted({round(c * row['gait'] + o) for c in range(duration // row['gait']) for o in offsets_sound})
        assert [i['frame'] - 1 for i in sounds] == expected_ticks
        checks.append(dict(slot=slot, duration=duration, source_slot=slot if slot else 33, source_period=own, gait_period=row['gait'], contact=row['contact'], forward_units_per_tick=row['speed'], unselected_resampled_source_max_channel_error=maximum, original_scales_exact=True, reviewed_fixed_local_translation_offsets=[dict(bone=b, channel=c, delta=v) for (b, c), v in sorted(offsets.items())], no_within_clip_dynamic_joint_stretch=True, root_XY_zero=True, nine_cycles_pose_stable=True, footstep_ticks=expected_ticks, collar_native_rigid_rotation=True if slot else None))
    storage = motionstorage.audit(result, 21)
    assert storage['fits'], storage
    return (result, dict(species=221, source_sha256=SOURCE, output_sha256=hashlib.sha256(result).hexdigest(), changed_slots=[0, 2, 3, 4], mesh_skeleton_hierarchy_private_care_battle_exact=True, checks=checks, solver=solver, storage=storage))
