"""Devidramon's grounded prowl with native head, wing and tail performance.

Walk and run put the whole body on the stride's beat: the legs, pelvis, chest, arms, wings and tail all cycle
at the step count of the loop (the native upper-body clips ran at one beat per loop, a third or half of the legs'),
and each foot's stance moves at the body's own speed once pace.py has retimed the walk.
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
SOURCE = '8a02d368ec11fb19ccbf57db20b11368d0670a87ae23b53f9e060b8d9db2868c'
# The source is the 460-tall prowl's model brought down to 390 (content/modeldelta/import-sizes.json): the
# body heights, foot tracks and lifts below were measured at 460 and shrink with it.
SCALE = 390 / 459.92
# Stride beats per loop (the walk's 72 ticks and the run's 20 are three and two full left+right cycles) and how much of
# each native upper-body channel survives once it is replayed at that beat (its swing was written for one beat per loop).
BEATS = {2: 3, 4: 2}
UPPER = {1: .7, 2: .7, 3: .5, 4: .3, 5: .2, 6: .2, 7: .2, 8: .2, 9: .2, 10: .2, 11: .4, 12: .4, 13: .4, 14: .4,
         16: .5, 17: .5, 18: .5, 19: .4, 20: .4, 21: .4, 22: .4}
# Degrees: pelvis yaw with the leading leg, chest against it, head against the chest, arms opposite the legs.
STRIDE = {2: dict(pelvis=5, chest=7, head=4, arm=7, elbow=6, bend=30), 4: dict(pelvis=7, chest=9, head=5, arm=13, elbow=6, bend=35)}

def _beat(fs, bone, channel, slot, duration):
    """A native upper-body channel replayed at the stride beat: (mean, degrees about it per tick), None if it barely moves.
    Its dominant harmonic k is moved to the loop's beat count by playing the loop BEATS // k times as fast."""
    raw = [fs[t][bone][channel] * 360 / 4096 for t in range(duration)]
    x = [raw[0]]
    for v in raw[1:]:
        x.append(v - 360 * round((v - x[-1]) / 360))
    mean = sum(x) / duration
    if max(x) - min(x) < 3:
        return None
    power = [abs(sum((v - mean) * complex(math.cos(2 * math.pi * k * t / duration), -math.sin(2 * math.pi * k * t / duration)) for t, v in enumerate(x))) for k in range(1, 5)]
    k = power.index(max(power)) + 1
    w = BEATS[slot] // k if BEATS[slot] % k == 0 else 1
    series = [(x[(w * t) % duration] - mean) * UPPER[bone] for t in range(duration)]
    # A swing under 4 degrees is noise at this beat and costs keys: hold the mean.
    return mean, series if max(series) - min(series) >= 4 else [0.0] * duration

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
    # The condition walk (3) is pace.py's retiming of this walk, so it keeps the same beat.
    for slot in [0, 2, 4]:
        fs, loop, events = animsheet.slot_frames(old, n, slot)
        duration = len(fs) - 1
        period = {0: 72, 2: 24, 4: 10}[slot]
        contact = {0: 72, 2: 13, 4: 3}[slot]
        # Walk: 10 a tick here is 20 once pace.py plays the 72 ticks in 36, the field speed, so a planted foot keeps still on the ground.
        speed = {0: 0, 2: 10, 4: 38}[slot]
        lift = {0: 0, 2: 16, 3: 13, 4: 25}[slot] * SCALE
        rock = {0: 0, 2: 6, 3: 5, 4: 8}[slot]
        poses = []
        hist = {}
        beat = {(b, c): _beat(fs, b, c, slot, duration) for b in UPPER for c in (3, 4, 5)} if slot in BEATS else {}
        stride = STRIDE.get(slot)
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
        def turn(f, bone, degrees):
            w = world(f)
            set_rotation(f, bone, w[sk[bone][1], :3, :3].T @ rotation(degrees) @ w[bone, :3, :3], hist)

        # Three walking strides share the 72-tick loop; the upper body beats with them (BEATS).
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
                for (b, c), series in beat.items():
                    if series:
                        f[b][c] = round((series[0] + series[1][t % duration]) * 4096 / 360)
                if stride:
                    # Phase 0 has the right leg forward: the pelvis turns with the leading leg, the chest against it a
                    # little later, the head against the chest last; each turn is in world axes and rides on its parent.
                    ph = 2 * math.pi * BEATS[slot] * t / duration
                    wave = lambda lag, tilt=0: math.cos(ph - 2 * math.pi * lag) + tilt * math.sin(2 * (ph - 2 * math.pi * lag))
                    turn(f, 15, [0, stride['pelvis'] * wave(0, .15), 0])
                    turn(f, 1, [0, -stride['chest'] * wave(.07, .2) - stride['pelvis'] * wave(0, .15), 0])
                    turn(f, 3, [0, stride['head'] * wave(.14) + stride['chest'] * wave(.07, .2), 0])
                f[15][7] = round({2: -96, 3: -94, 4: -96}[slot] * SCALE + (2 * math.sin(2 * math.pi * t / (period / 2)) if slot != 4 else 2 * math.sin(math.pi * q / contact) ** 2 if q <= contact else -8 * math.sin(math.pi * (q - contact) / (period / 2 - contact)) ** 2))
                for side, (hip, knee, foot) in enumerate(chains):
                    offset = side * period / 2
                    start = math.floor((t - offset) / period) * period + offset
                    phase = t - start
                    half = speed * contact / 2
                    center = -20 * SCALE
                    sign = 1 if side == 0 else -1
                    if phase <= contact:
                        z = center - half + speed * phase
                        up = 3
                        pitch = -rock * math.cos(math.pi * phase / contact)
                        x = sign * 48 * SCALE
                    else:
                        q = (phase - contact) / (period - contact)
                        span = period - contact
                        a = center + half
                        b = center - half
                        z = (2 * q ** 3 - 3 * q * q + 1) * a + (q ** 3 - 2 * q * q + q) * span * speed + (-2 * q ** 3 + 3 * q * q) * b + (q ** 3 - q * q) * span * speed
                        up = 3 + lift * math.sin(math.pi * q) ** .6
                        pitch = rock * math.cos(math.pi * q) + 8 * math.sin(math.pi * q) ** 2
                        x = sign * (48 + 4 * math.sin(math.pi * q) ** 2) * SCALE
                    rf, dz, _ = motionsecondary.rolling_foot(vs[foot].tolist(), rotation([0, -sign * 8, 0]).tolist(), pitch)
                    solveleg(f, hip, knee, foot, x, z + dz, np.array(rf), up)
            ph = 2 * math.pi * BEATS[slot] * t / duration if stride else 0
            if slot:
                for shoulder, hand, sign in [(5, 7, 1), (8, 10, -1)]:
                    w = world(f)
                    attitude = w[hand, :3, :3].copy()
                    bias = rotation([0, -sign * (12 if slot == 2 else 30), -sign * (5 if slot == 2 else 12)])
                    if stride:
                        # The arm opposite the leading leg is back: x turns a hanging arm back when positive.
                        bias = rotation([sign * stride['arm'] * math.cos(ph - .3), 0, 0]) @ bias
                    set_rotation(f, shoulder, w[1, :3, :3].T @ bias @ w[shoulder, :3, :3], hist)
                    w = world(f)
                    if slot != 4:      # the run's hands follow their forearms: no world attitude to hold at the wrist
                        set_rotation(f, hand, w[sk[hand][1], :3, :3].T @ attitude, hist)
            if slot in [2, 3, 4]:
                for elbow, hand, sign in [(6, 7, 1), (9, 10, -1)]:
                    w = world(f)
                    attitude = w[hand, :3, :3].copy()
                    # Elbows stay bent (x turns a forearm up and forward when negative) and fold a little deeper as
                    # the arm comes forward, on the shoulder's own cosine.
                    flex = -(stride['bend'] + stride['elbow'] * -sign * math.cos(ph - .3)) if stride else -12
                    set_rotation(f, elbow, w[sk[elbow][1], :3, :3].T @ rotation([flex, 0, -sign * 12 * (slot != 2)]) @ w[elbow, :3, :3], hist)
                    w = world(f)
                    if slot != 4:
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
        bones = [7, 10, 16] + ([5, 8] if slot else []) + ([b for chain in chains for b in chain] if slot else []) + ([6, 9] if slot in [2, 3, 4] else []) + ([15, *UPPER] if stride else [])
        bones = list(dict.fromkeys(bones))
        channels = {(b, c) for b in bones for c in [3, 4, 5]} | {(15, 7)}
        authored = replace_channels(old.anims.anims[old.anims.table[slot]], poses, loop, n, channels, tolerance=6)
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
    steps = {2: list(range(0,72,12)), 4: [0,5,10,15]}
    for slot,ticks in steps.items():
        authored = _steps(new.anims.anims[new.anims.table[slot]],ticks)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims,new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims,new.anims.table)
    result = new.build()
    actual = _parse(result,sk)
    assert changed_programs(old,actual) == [0,2,4]
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
    return result,dict(species=216,source_sha256=SOURCE,output_sha256=hashlib.sha256(result).hexdigest(),changed_slots=[0,2,4],mesh_skeleton_private33_care_battle_exact=True,checks=checks,solver=solver,footstep_ticks=steps,storage=storage)
