"""Shadramon's supported claw strides, relaxed gauntlets and four wing lobes.

Keep the full native idle/poor/private performances. Field locomotion uses
its original clocks with separate torso balance and head counterrotation.
Paired shoulder carries clear the helmet; rolling claws keep original link
lengths and unit scales, with an independent phase for each wing lobe.
"""
import copy
import math
import hashlib
import numeric as np
import mmd
import animsheet
import motionsecondary as S
import motioncyclelayer
import motionstorage
from tools.models.field_animations.channels import replace_channels, coalesce
from tools.models.field_animations.gliding import _forward
from tools.models.field_animations.war_greymon import rotation, set_rotation, align
from motiondiscidentity import changed_programs
SOURCE = '1dd2fc111ba172a36df3491b15708e994e9dcac794be15372e173424e3bc645a'
OUTPUT = '51e128a2423e5a6aa1b72a3dff24805951918b142b84c6be04c7a18cd1a6be4b'
PARENTS = [-1, 0, 1, 2, 2, 4, 2, 6, 1, 8, 9, 1, 11, 12, 2, 2, 2, 2]

def _parse(data, sk):
    mmd.exe().skeleton[250] = sk
    mmd.exe().bone_count[250] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = 250
    return model

def _author(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    native = animsheet.slot_frames(old, n, 0)[0]
    verts = {b: np.array(old.tmd.obj_verts(o))[:, :3] for b, (o, _) in enumerate(sk) if o >= 0}
    reports = []

    def world(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, g))
    ref = copy.deepcopy(native[0])
    ref[1][3:6] = [0, 0, 0]
    rw = world(ref)
    upper_ref = world(native[0])[2, :3, :3]
    for slot in [2, 3, 4]:
        native = animsheet.slot_frames(old, n, slot)[0]
        duration = len(native) - 1
        cycles = 1
        period = duration
        speed = {2: 16, 3: 11, 4: 34}[slot]
        duty = {2: 0.56, 3: 0.56, 4: 0.3}[slot]
        contact = period * duty
        lift = {2: 10, 3: 7, 4: 16}[slot]
        rock = {2: 4, 3: 3, 4: 7}[slot]
        frames = []
        plans = []
        hist = {}
        errors = []
        for t, source in enumerate(native):
            f = copy.deepcopy(source)
            oldworld = world(source)
            f[1][3:6] = [0, 0, 0]
            f[1][6:9] = [0, -150 + round(2 * math.cos(4 * math.pi * t / period)), 0]
            upper = rotation([{2: 4, 3: 8, 4: 13}[slot], 4 * math.sin(2 * math.pi * t / period), 1.5 * math.cos(2 * math.pi * t / period)]) @ upper_ref
            set_rotation(f, 2, upper, hist)
            set_rotation(f, 3, world(f)[2, :3, :3].T @ oldworld[3, :3, :3], hist)
            for shoulder, elbow, sign in [(4, 5, -1), (6, 7, 1)]:
                f[shoulder][6] = source[shoulder][6] + sign * 16
                f[shoulder][7] = source[shoulder][7] + 20
                wave = math.sin(2 * math.pi * t / period + (0.0 if sign < 0 else math.pi))
                lag = math.sin(2 * math.pi * t / period + (0.0 if sign < 0 else math.pi) - 0.45)
                amp = {2: 18, 3: 11, 4: 26}[slot]
                set_rotation(f, shoulder, rotation([amp * wave, 0, -sign * 10]) @ np.array(mmd.rot_matrix(*ref[shoulder][3:6])), hist)
                set_rotation(f, elbow, rotation([-4 - 3 * lag, 0, 0]) @ np.array(mmd.rot_matrix(*ref[elbow][3:6])), hist)
            for b, sign, lag in [(14, -1, 0), (16, 1, 0.12), (15, -1, 0.45), (17, 1, 0.57)]:
                wave = math.sin(2 * math.pi * t / period - lag)
                flap = (5 if slot == 3 else 8) * wave * (1.35 if b in [15, 17] else 1)
                set_rotation(f, b, rotation([0, sign * flap, 0]) @ np.array(mmd.rot_matrix(*ref[b][3:6])), hist)
            row = []
            for hip, knee, foot, sign, offset in [(8, 9, 10, -1, 0), (11, 12, 13, 1, 0.5)]:
                phase = (t + offset * period) % period
                stance = phase <= contact
                if stance:
                    z = 24 - speed * contact / 2 + speed * phase
                    up = 4
                    pitch = -rock * math.cos(math.pi * phase / contact)
                    x = sign * 67
                else:
                    u = (phase - contact) / (period - contact)
                    smooth = 6 * u ** 5 - 15 * u ** 4 + 10 * u ** 3
                    z = 24 + speed * contact / 2 * (1 - 2 * smooth) + (period - contact) * speed * u * (1 - u) * (1 - 2 * u) ** 5
                    up = 4 + lift * math.sin(math.pi * u) ** 2
                    pitch = rock * math.cos(math.pi * u)
                    x = sign * (67 + 4 * math.sin(math.pi * u) ** 2)
                rf, dz, _ = S.rolling_foot(verts[foot].tolist(), np.eye(3).tolist(), pitch)
                rf = np.array(rf)
                z += dz
                w = world(f)
                h = w[hip, :3, 3]
                la = np.linalg.norm(f[knee][6:9])
                lb = np.linalg.norm(f[foot][6:9])
                reach = (la + lb - 0.1) ** 2 - (x - h[0]) ** 2 - (z - h[2]) ** 2
                assert reach > 0, (slot, t, hip, 'reach')
                lo = h[1] + 1
                hi = h[1] + math.sqrt(reach)
                goal = np.array([x, 0, z], float)
                pole = np.array([sign * 0.35, 0, -1.0])

                def solve(y):
                    goal[1] = y
                    delta = goal - h
                    dist = np.linalg.norm(delta)
                    direct = delta / dist
                    pp = pole - direct * (pole @ direct)
                    pp /= np.linalg.norm(pp)
                    along = (la * la - lb * lb + dist * dist) / (2 * dist)
                    joint = h + direct * along + pp * math.sqrt(max(0, la * la - along * along))
                    rh = align(rw[hip, :3, :3] @ np.array(f[knee][6:9]), joint - h) @ rw[hip, :3, :3]
                    rk = align(rw[knee, :3, :3] @ np.array(f[foot][6:9]), goal - joint) @ rw[knee, :3, :3]
                    bottom = max(float((verts[knee] @ rk.T + joint)[:, 1].max()), float((verts[foot] @ rf.T + goal)[:, 1].max()))
                    return (bottom + up, rh, rk)
                assert solve(lo)[0] <= 0 <= solve(hi)[0], (slot, t, hip, 'Yreach', solve(lo)[0], solve(hi)[0])
                for _ in range(25):
                    mid = (lo + hi) / 2
                    if solve(mid)[0] > 0:
                        hi = mid
                    else:
                        lo = mid
                _, rh, rk = solve((lo + hi) / 2)
                set_rotation(f, hip, w[1, :3, :3].T @ rh, hist)
                w = world(f)
                set_rotation(f, knee, w[hip, :3, :3].T @ rk, hist)
                w = world(f)
                set_rotation(f, foot, w[knee, :3, :3].T @ rf, hist)
                errors.append(float(np.linalg.norm(world(f)[foot, :3, 3] - goal)))
                row.append(dict(foot=foot, stance=stance, phase=phase, ankle=goal.tolist(), orientation=rf.tolist(), up=up))
            frames.append(f)
            plans.append(row)
        frames[-1][1:] = copy.deepcopy(frames[0][1:])
        channels = {(b, c) for b in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17] for c in [3, 4, 5]} | {(1, c) for c in [6, 7, 8]} | {(4, 6), (6, 6), (4, 7), (6, 7)}
        legs = {(b, c) for b in range(8, 14) for c in [3, 4, 5]}
        animation = replace_channels(old.anims.anims[old.anims.table[slot]], frames, 0, n, channels, tolerance=1)
        animation = replace_channels(animation, frames, 0, n, {(1, c) for c in [6, 7, 8]}, tolerance=0)
        temporary = copy.deepcopy(old)
        temporary.anims.table[slot] = len(temporary.anims.anims)
        temporary.anims.anims.append(animation)
        decoded = animsheet.slot_frames(temporary, n, slot)[0]
        fhist = {}
        for tick, f in enumerate(decoded):
            for knee, foot, j in [(9, 10, 0), (12, 13, 1)]:
                w = world(f)
                set_rotation(f, foot, w[knee, :3, :3].T @ np.array(plans[tick][j]['orientation']), fhist)
        decoded[-1][1:] = copy.deepcopy(decoded[0][1:])
        animation = replace_channels(animation, decoded, 0, n, {(b, c) for b in [10, 13] for c in [3, 4, 5]}, tolerance=0)
        animation = _forward(animation, -speed * duration, duration)
        for ins in animation.instrs:
            if ins['op'] == 'key':
                for g in ins['bones']:
                    if g['bone'] == 0:
                        g['vals'].pop('tx', None)
                ins['bones'] = [g for g in ins['bones'] if g['vals']]
        first = next((i for i in animation.instrs if i['op'] == 'key' and i['frame'] == 1))
        first['bones'].append(dict(bone=0, div=1, vals={'tx': 0}))
        animation.instrs = [i for i in animation.instrs if i['op'] != 'sound']
        cue = next((i for i in old.anims.anims[old.anims.table[slot]].instrs if i['op'] == 'sound'))
        steps = sorted({round(j * period / 2) for j in range(cycles * 2)})
        for tick in steps:
            e = dict(cue, frame=tick + 1)
            at = next((i for i, x in enumerate(animation.instrs) if x.get('frame', -1) > tick + 1), len(animation.instrs) - 1)
            animation.instrs.insert(at, e)
        animation, _ = coalesce(animation)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(animation)
        reports.append(dict(slot=slot, period=duration, gait_period=period, cycles=cycles, speed=speed, contact=contact, channels=sorted(channels), plans=plans, footsteps=steps, maximum_FK_error=max(errors)))
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    return (new.build(), reports)

def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE or [b[1] for b in sk] != PARENTS or [b[0] for b in sk] != list(range(-1, 17)):
        raise ValueError('Shadramon requires its reviewed 18-bone armored insect source')
    old = _parse(data, sk)
    result, solver = _author(old, sk)
    assert hashlib.sha256(result).hexdigest() == OUTPUT
    actual = _parse(result, sk)
    assert changed_programs(old, actual) == [2, 3, 4] and old.tmd.build() == actual.tmd.build()
    checks = []
    maximum_head_matrix_error = 0
    for row in solver:
        slot = row['slot']
        period = row['period']
        channels = {tuple(c) for c in row['channels']}
        before = mmd.AnimPlayer(old.anims.anims[old.anims.table[slot]], 18, slot)
        after = mmd.AnimPlayer(actual.anims.anims[actual.anims.table[slot]], 18, slot)
        for tick in range(period * 9 + 1):
            assert before.tick() and after.tick()
            for b in range(1, 18):
                for c in range(9):
                    if (b, c) not in channels:
                        assert before.pose[b][c] == after.pose[b][c], (slot, tick, b, c, 'protected')
            assert after.base == [0, 0, -row['speed']] if tick else after.base == [0, 0, 0]
            w0 = np.array(mmd.bone_matrices(old, before.pose))
            w1 = np.array(mmd.bone_matrices(actual, after.pose))
            maximum_head_matrix_error = max(maximum_head_matrix_error, float(abs(w0[3, :3, :3] - w1[3, :3, :3]).max()))
        fs, loop, events = animsheet.slot_frames(actual, 18, slot)
        sourcefs, sourceloop, sourceevents = animsheet.slot_frames(old, 18, slot)
        assert len(fs) == len(sourcefs) == period + 1 and loop == sourceloop == 0
        assert [(t, k, e) for t, k, e in events if k != 'sound'] == [(t, k, e) for t, k, e in sourceevents if k != 'sound']
        assert [t for t, k, e in events if k == 'sound'] == row['footsteps']
        checks.append(dict(slot=slot, nine_cycles_protected_SRT_exact=True, original_period=period, root_speed=row['speed'], root_X_Y_zero=True, source_sound_retimed_to_supports=row['footsteps']))
    assert maximum_head_matrix_error < 0.005, maximum_head_matrix_error
    storage = motionstorage.audit(result, 18)
    assert storage['fits'], storage
    return (result, dict(species=250, source_sha256=SOURCE, output_sha256=OUTPUT, changed_slots=[2, 3, 4], solver=solver, checks=checks, storage=storage, maximum_head_world_rotation_matrix_error=maximum_head_matrix_error, source_idle0_poor1_private33_care_battle_mesh_exact=True, all_scales_and_original_leg_lengths_exact=True, shoulder_anchor_shifts='4/6TX -16/+16, TY+20; original elbow links retained.', limits='Decoded reference protection and storage only. Complete mesh/contact diagnostics, actual game playback and visual approval are separate. No SDK/terrain/turn/transition continuous-sweep guarantee.'))
