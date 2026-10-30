"""Devidramon's grounded prowl with native head, wing and tail performance.

Complete calf/claw support retains native limb lengths. A narrow knee plane
and mirrored axial thigh twist clear the torso. Minimum bounded hand and tail
hinges clear the ground while retaining their native articulated child curves.
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
from tools.models.field_animations.aero_veedramon import _forward, _steps
from motiondiscidentity import changed_programs
from tools.models.field_animations.war_greymon import rotation, set_rotation
SOURCE = '175aef45b792ae1707ee37e49f7eddfb1ad7e4be01945d6b26e1b9a28a5d51f6'

def _parse(data, sk):
    mmd.exe().skeleton[216] = sk
    mmd.exe().bone_count[216] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = 216
    return model

def _author(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    chains = [(23, 24, 25), (26, 27, 28)]
    vs = {b: np.array(old.tmd.obj_verts(oi))[:, :3] for b, (oi, _) in enumerate(sk) if oi >= 0}

    def world(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, g))
    rw = world(animsheet.slot_frames(old, n, 0)[0][0])
    reports = []
    for slot in [0, 2, 3, 4]:
        fs, loop, events = animsheet.slot_frames(old, n, slot)
        duration = len(fs) - 1
        period = {0: 72, 2: 24, 3: 24, 4: 10}[slot]
        contact = {0: 72, 2: 14, 3: 14, 4: 3}[slot]
        speed = {0: 0, 2: 9, 3: 7, 4: 30}[slot]
        lift = {0: 0, 2: 16, 3: 13, 4: 25}[slot]
        rock = {0: 0, 2: 6, 3: 5, 4: 8}[slot]
        poses = []
        hist = {}
        errs = []

        def solveleg(f, hip, knee, foot, x, z, rf, up):
            w = world(f)
            h = w[hip, :3, 3]
            a = np.linalg.norm(f[knee][6:9])
            b = np.linalg.norm(f[foot][6:9])
            reach = (a + b - 0.1) ** 2 - (x - h[0]) ** 2 - (z - h[2]) ** 2
            assert reach > 0, (slot, hip, 'XZreach', reach)
            goal = np.array([x, 0.0, z])
            low = h[1] + 1
            high = h[1] + math.sqrt(reach)
            # Keep the bent knee forward of the hip, clear of the hanging arms.
            pole = np.array([0.1 if hip == 23 else -0.1, 0.0, -1.0])

            def solve(y):
                goal[1] = y
                d = goal - h
                dist = np.linalg.norm(d)
                dire = d / dist
                pp = pole - dire * (pole @ dire)
                pp /= np.linalg.norm(pp)
                along = (a * a - b * b + dist * dist) / (2 * dist)
                joint = h + dire * along + pp * math.sqrt(max(0, a * a - along * along))
                rh, rs = map(np.array, motionsecondary.native_plane_rotations([rw[v, :3, 3].tolist() for v in [hip, knee, foot]], [h.tolist(), joint.tolist(), goal.tolist()], [rw[v, :3, :3].tolist() for v in [hip, knee]]))
                bottom = max(float((vs[knee] @ rs.T + joint)[:, 1].max()), float((vs[foot] @ rf.T + goal)[:, 1].max()))
                return (bottom + up, rh, rs)
            elo = solve(low)[0]
            ehi = solve(high)[0]
            assert elo <= 0 <= ehi, (slot, hip, 'Yreach', elo, ehi, h, goal, up)
            for _ in range(27):
                mid = (low + high) / 2
                if solve(mid)[0] > 0:
                    high = mid
                else:
                    low = mid
            residual, rh, rs = solve((low + high) / 2)
            # Axial twist changes the thigh shell without moving knee or ankle.
            axis = rh @ np.array(f[knee][6:9])
            axis /= np.linalg.norm(axis)
            rh = np.array(motionsecondary.R.from_axis_angle(axis.tolist(), math.radians(-40 if hip == 23 else 40))) @ rh
            set_rotation(f, hip, w[sk[hip][1], :3, :3].T @ rh, hist)
            w = world(f)
            set_rotation(f, knee, w[hip, :3, :3].T @ rs, hist)
            w = world(f)
            set_rotation(f, foot, w[knee, :3, :3].T @ rf, hist)
            errs.append(float(np.linalg.norm(world(f)[foot, :3, 3] - goal)))
        # Three walking strides share the original 72-tick upper performance.
        for t, source in enumerate(fs):
            f = copy.deepcopy(source)
            f[0] = [4096] * 3 + [0] * 6
            # Idle retains native leg rotations and world XZ; lift only enough.
            if slot == 0:
                w = world(f)
                bottom = max((float((vs[b] @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max()) for b in [24, 25, 27, 28]))
                f[15][7] -= math.ceil(max(0, bottom + 2))
            else:
                q = t % (period / 2)
                f[15][7] = round({2: -96, 3: -94, 4: -96}[slot] + (2 * math.sin(2 * math.pi * t / (period / 2)) if slot != 4 else 2 * math.sin(math.pi * q / contact) ** 2 if q <= contact else -8 * math.sin(math.pi * (q - contact) / (period / 2 - contact)) ** 2))
                for side, (hip, knee, foot) in enumerate(chains):
                    offset = side * period / 2
                    start = math.floor((t - offset) / period) * period + offset
                    phase = t - start
                    half = speed * contact / 2
                    center = -20
                    sign = 1 if side == 0 else -1
                    if phase <= contact:
                        z = center - half + speed * phase
                        up = 3
                        pitch = -rock * math.cos(math.pi * phase / contact)
                        x = sign * 48
                    else:
                        q = (phase - contact) / (period - contact)
                        span = period - contact
                        a = center + half
                        b = center - half
                        z = (2 * q ** 3 - 3 * q * q + 1) * a + (q ** 3 - 2 * q * q + q) * span * speed + (-2 * q ** 3 + 3 * q * q) * b + (q ** 3 - q * q) * span * speed
                        up = 3 + lift * math.sin(math.pi * q)
                        pitch = rock * math.cos(math.pi * q) + 8 * math.sin(math.pi * q) ** 2
                        x = sign * (48 + 4 * math.sin(math.pi * q) ** 2)
                    rf, dz, _ = motionsecondary.rolling_foot(vs[foot].tolist(), rotation([0, -sign * 8, 0]).tolist(), pitch)
                    solveleg(f, hip, knee, foot, x, z + dz, np.array(rf), up)
            if slot:
                for shoulder, hand, sign in [(5, 7, 1), (8, 10, -1)]:
                    w = world(f)
                    attitude = w[hand, :3, :3].copy()
                    bias = rotation([0, -sign * (12 if slot == 2 else 30), -sign * (5 if slot == 2 else 12)])
                    set_rotation(f, shoulder, w[1, :3, :3].T @ bias @ w[shoulder, :3, :3], hist)
                    w = world(f)
                    set_rotation(f, hand, w[sk[hand][1], :3, :3].T @ attitude, hist)
            if slot in [3, 4]:
                for elbow, hand, sign in [(6, 7, 1), (9, 10, -1)]:
                    w = world(f)
                    attitude = w[hand, :3, :3].copy()
                    set_rotation(f, elbow, w[sk[elbow][1], :3, :3].T @ rotation([-12, 0, -sign * 12]) @ w[elbow, :3, :3], hist)
                    w = world(f)
                    set_rotation(f, hand, w[elbow, :3, :3].T @ attitude, hist)
            for hand in [7, 10]:
                w = world(f)
                points = vs[hand] @ w[hand, :3, :3].T + w[hand, :3, 3]
                bias = np.array(motionsecondary.clearance_rotation(points.tolist(), w[hand, :3, 3].tolist(), [1, 0, 0], [-70, 0], -6))
                set_rotation(f, hand, w[sk[hand][1], :3, :3].T @ bias @ w[hand, :3, :3], hist)
            w = world(f)
            points = np.concatenate([vs[b] @ w[b, :3, :3].T + w[b, :3, 3] for b in range(16, 23)])
            bias = np.array(motionsecondary.clearance_rotation(points.tolist(), w[16, :3, 3].tolist(), [1, 0, 0], [0, 65], -12))
            set_rotation(f, 16, w[15, :3, :3].T @ bias @ w[16, :3, :3], hist)
            f[0] = copy.deepcopy(source[0])
            f[0][8] = -speed * t
            poses.append(f)
        poses[-1][1:] = copy.deepcopy(poses[0][1:])
        bones = [7, 10, 16] + ([5, 8] if slot else []) + ([b for chain in chains for b in chain] if slot else []) + ([6, 9] if slot in [3, 4] else [])
        channels = {(b, c) for b in bones for c in [3, 4, 5]} | {(15, 7)}
        authored = replace_channels(old.anims.anims[old.anims.table[slot]], poses, loop, n, channels)
        if slot:
            authored = _forward(authored, round(-speed * duration), duration)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
        reports.append(dict(slot=slot, period=duration, gait=period, contact=contact, speed=speed, channels=sorted(channels), max_ankle_error=max(errs, default=0)))
    return (new, reports)

def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE or len(sk) != 29:
        raise ValueError('Devidramon requires the reviewed pinned 29-bone source')
    old = _parse(data,sk)
    new, solver = _author(old,sk)
    steps = {2: list(range(0,72,12)), 3: [0,12], 4: [0,5,10,15]}
    for slot,ticks in steps.items():
        authored = _steps(new.anims.anims[new.anims.table[slot]],ticks)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims,new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims,new.anims.table)
    result = new.build()
    actual = _parse(result,sk)
    assert changed_programs(old,actual) == [0,2,3,4]
    assert old.tmd.build() == actual.tmd.build()
    checks = []
    for row in solver:
        slot = row['slot']
        duration = row['period']
        original = old.anims.anims[old.anims.table[slot]]
        selected = actual.anims.anims[actual.anims.table[slot]]
        source,loop,source_events = animsheet.slot_frames(old,29,slot)
        decoded,selected_loop,selected_events = animsheet.slot_frames(actual,29,slot)
        assert len(decoded) == len(source) and loop == selected_loop == 0
        assert [i for i in original.instrs if i['op'] not in ('key','sound')] == [i for i in selected.instrs if i['op'] not in ('key','sound')]
        assert [(t,k,e) for t,k,e in source_events if k!='sound'] == [(t,k,e) for t,k,e in selected_events if k!='sound']
        channels = {tuple(c) for c in row['channels']}
        before = mmd.AnimPlayer(original,29,slot)
        after = mmd.AnimPlayer(selected,29,slot)
        cycle = []
        for tick in range(duration*9+1):
            assert before.tick() and after.tick()
            assert before.base[:2] == after.base[:2]
            for bone in range(29):
                for channel in range(9):
                    if (bone,channel) not in channels:
                        assert before.pose[bone][channel] == after.pose[bone][channel], (slot,tick,bone,channel)
            if tick < duration:
                cycle.append(copy.deepcopy(after.pose))
            else:
                assert after.pose == cycle[tick%duration], (slot,tick,'cyclic drift')
        total = -row['speed']*duration
        assert after.root[2] == total*9, (slot,after.root[2],total)
        checks.append(dict(slot=slot,duration=duration,gait_period=row['gait'],forward_units_per_tick=row['speed'],source_root_XY_exact=True,unselected_channels_limb_translations_scales_exact_nine_cycles=True,changed_pose_repeat_exact_nine_cycles=True,original_texture_and_control_instructions_exact=True))
    storage = motionstorage.audit(result,29)
    assert storage['fits'], storage
    return result,dict(species=216,source_sha256=SOURCE,output_sha256=hashlib.sha256(result).hexdigest(),changed_slots=[0,2,3,4],mesh_skeleton_private33_care_battle_exact=True,checks=checks,solver=solver,footstep_ticks=steps,storage=storage)
