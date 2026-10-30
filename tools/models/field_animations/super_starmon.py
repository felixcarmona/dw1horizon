"""SuperStarmon's supported showboat shuffle and planted poor idle.

Rigid shoulder carries retain forearm, wrist and gauntlet-fringe gestures.
The rear boot keeps its native raised heel and the front boot its sole.
A separate private engine adapter supplies the native streamer clock/path.
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
from tools.models.field_animations.channels import replace_channels, coalesce
from tools.models.field_animations.gliding import _forward
from motiondiscidentity import changed_programs
from tools.models.field_animations.war_greymon import rotation, set_rotation, align
SOURCE = 'becc9dc5f7e8367e572749fd0ea7617fff0c84e01345a0649b822d5248744536'
PARENTS = [-1, 0, 1, 2, 3, 1, 5, 6, 1, 8, 9, 10, 1, 12, 13, 14, 1, 16, 1, 18, 3, 3, 3, 6, 6, 6, 1]
# Authored primary ankle corrections for nominal 60 FPS support, not source curves.
CONTACT_BIAS = {2: {10: {0: [0, 0, 1],
          1: [-1, -1, 1],
          2: [-1, -1, 1],
          3: [0, -4, 1],
          4: [0, -3, 1],
          8: [-1, 0, 0],
          9: [-1, -1, 1],
          10: [-1, 0, 1],
          11: [0, -3, 1],
          12: [0, -4, 2],
          16: [0, 0, 1],
          17: [-1, 0, 1],
          18: [0, -1, 0],
          19: [0, -4, 2],
          20: [0, -3, 1]},
     14: {0: [0, 0, -1],
          4: [0, -1, -1],
          5: [-1, 0, -1],
          7: [0, 1, -1],
          12: [1, 1, 0],
          13: [-1, 0, 0],
          14: [1, 0, 0],
          16: [0, 1, 0],
          20: [1, 0, -1],
          21: [-1, 0, 1],
          22: [1, 0, 0],
          23: [-1, 1, 0]}},
 3: {10: {0: [-1, 0, 1],
          1: [-1, -1, 2],
          2: [-1, 0, 0],
          4: [-1, -2, 2],
          5: [0, -2, 0],
          10: [-1, -1, 0],
          11: [-1, 0, 1],
          12: [0, -1, 0],
          13: [0, -2, 0],
          14: [-1, -2, 1],
          19: [-1, 0, 1],
          21: [0, 0, 1],
          22: [-1, -1, 0],
          23: [-1, -1, 0]},
     14: {0: [-1, 0, 0],
          5: [-1, 0, 0],
          6: [0, 0, -1],
          7: [1, -1, 0],
          8: [2, 0, 0],
          15: [-1, 0, 0],
          16: [1, -1, 0],
          17: [2, 0, 0],
          18: [-1, 0, 0],
          25: [1, -1, -1],
          27: [1, 1, 0]}},
 4: {10: {0: [-4, -7, 6], 1: [-5, -6, 5], 7: [-3, -11, 7], 8: [-3, -9, 4]},
     14: {10: [3, 1, -1], 11: [5, 0, -2], 17: [6, 1, -3], 18: [3, 2, -1]}}}

def _parse(data, sk):
    mmd.exe().skeleton[244] = sk
    mmd.exe().bone_count[244] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = 244
    return model

def _pack(model):
    for animation in model.anims.anims:
        animation.tail = b''
    model.anims.anims, model.anims.table = motioncyclelayer.share_identical_streams(model.anims.anims, model.anims.table)
    return model.build()

def _author(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    vs = {b: np.array(old.tmd.obj_verts(o))[:, :3] for b, (o, _) in enumerate(sk) if o >= 0}

    def bodyguard(f, source):
        # Leave clearance for the lower star points without losing the source sway.
        f[1][3:6] = [round(ref[1][c] + 0.3 * ((source[1][c] - ref[1][c] + 2048) % 4096 - 2048)) for c in [3, 4, 5]]
        f[1][4] += 199 if slot == 2 else 139

    def world(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, g))
    ref = animsheet.slot_frames(old, n, 0)[0][0]
    rw = world(ref)
    reports = []
    for slot in [1, 2, 3, 4]:
        fs, loop, events = animsheet.slot_frames(old, n, slot)
        duration = len(fs) - 1
        cycles = {1: 0, 2: 3, 3: 3, 4: 3}[slot]
        period = duration / (cycles or 1)
        speed = {0: 0, 1: 0, 2: 20, 3: 14, 4: 50}[slot]
        duty = {0: 1, 1: 1, 2: 0.5, 3: 0.55, 4: 0.2}[slot]
        contact = period * duty
        lift = {0: 0, 1: 0, 2: 18, 3: 12, 4: 25}[slot]
        rocks = {0: [0, 0], 1: [0, 0], 2: [4, 6], 3: [3, 5], 4: [3, 4]}[slot]
        alltargets = []
        requirements = []
        # Native compounds retain the raised rear heel and the flat front sole.
        compound = {b: np.concatenate([vs[b], vs[b + 1] @ np.array(mmd.rot_matrix(*ref[b + 1][3:6])).T + np.array(ref[b + 1][6:9])]) for b in [10, 14]}
        for t, source in enumerate(fs[:-1]):
            f = copy.deepcopy(source)
            bodyguard(f, source)
            f[1][7] = 0
            f[1][8] += 14
            w = world(f)
            targets = []
            need = source[1][7] - (30 if slot == 1 else 0)
            for side, (hip, knee, ankle, boot) in enumerate([(8, 9, 10, 11), (12, 13, 14, 15)]):
                sign = 1 if side == 0 else -1
                center = 157.5 if side == 0 else -70 if slot == 1 else -24.5
                rock = rocks[side]
                phase = (t - side * period / 2) % period if cycles else 0
                on = not cycles or phase <= contact
                if not cycles:
                    z = center
                    up = 7
                    pitch = 0
                elif on:
                    z = center - speed * contact / 2 + speed * phase
                    up = 7
                    pitch = -rock + 2 * rock * phase / contact
                else:
                    u = (phase - contact) / (period - contact)
                    ease = 6 * u ** 5 - 15 * u ** 4 + 10 * u ** 3
                    half = speed * contact / 2
                    z = (center + half) * (1 - ease) + (center - half) * ease + (period - contact) * speed * u * (1 - u) * (1 - 2 * u) ** 5
                    up = 7 + lift * math.sin(math.pi * u)
                    pitch = rock * (1 - 2 * (3 * u * u - 2 * u * u * u)) + (period - contact) * (2 * rock / contact) * u * (1 - u) * (1 - 2 * u)
                rf, dz, _ = motionsecondary.rolling_foot(compound[ankle].tolist(), rw[ankle, :3, :3].tolist(), pitch)
                rf = np.array(rf)
                goal = np.array([sign * 133, -up - float((compound[ankle] @ rf.T)[:, 1].max()), z + dz])
                h = w[hip, :3, 3]
                a = np.linalg.norm(f[knee][6:9])
                b = np.linalg.norm(f[ankle][6:9])
                horizontal = (goal[0] - h[0]) ** 2 + (goal[2] - h[2]) ** 2
                reach = (a + b - 1) ** 2 - horizontal
                assert reach > 0, (slot, t, hip, 'horizontal', horizontal)
                need = max(need, goal[1] - h[1] - math.sqrt(reach) + 2)
                targets.append(dict(hip=hip, knee=knee, ankle=ankle, boot=boot, goal=goal, orientation=rf, stance=on, phase=phase, up=up))
            alltargets.append(targets)
            requirements.append(need)
        # Anticipate leg reach with a bounded cyclic body-height envelope.
        heights = [math.ceil(max((requirements[j] - 1.5 * min(abs(t - j), duration - abs(t - j)) for j in range(duration)))) for t in range(duration)]
        poses = []
        hist = {}
        plans = []
        errors = []
        for t in range(duration + 1):
            q = t % duration
            f = copy.deepcopy(fs[t])
            bodyguard(f, fs[t])
            f[0] = [4096] * 3 + [0] * 6
            f[1][7] = heights[q]
            f[1][8] += 14
            aw = world(f)
            # Move each whole arm: wrist and gauntlet-strip relationships stay native.
            for shoulder, rx in [(2, 25), (5, -15)]:
                shift = aw[1, :3, :3].T @ np.array([0 if shoulder == 2 else -15, -20, 20 if shoulder == 2 else 0])
                f[shoulder][6:9] = [round(x) for x in np.array(f[shoulder][6:9]) + shift]
                set_rotation(f, shoulder, aw[1, :3, :3].T @ rotation([rx, 0, 0]) @ aw[shoulder, :3, :3], hist)
            for target in alltargets[q]:
                hip, knee, ankle, boot = [target[k] for k in ['hip', 'knee', 'ankle', 'boot']]
                goal = target['goal']
                rf = target['orientation']
                w = world(f)
                h = w[hip, :3, 3]
                a = np.linalg.norm(f[knee][6:9])
                b = np.linalg.norm(f[ankle][6:9])
                delta = goal - h
                dist = np.linalg.norm(delta)
                assert abs(a - b) < dist < a + b, (slot, t, hip, 'reach', dist, a + b)
                direction = delta / dist
                pole = np.array([1.0 if hip == 8 else -1.0, 0.0, 0.0])
                pole -= direction * (pole @ direction)
                pole /= np.linalg.norm(pole)
                along = (a * a - b * b + dist * dist) / (2 * dist)
                joint = h + direction * along + pole * math.sqrt(max(0, a * a - along * along))
                rh = align(rw[hip, :3, :3] @ np.array(f[knee][6:9]), joint - h) @ rw[hip, :3, :3]
                rk = align(rw[knee, :3, :3] @ np.array(f[ankle][6:9]), goal - joint) @ rw[knee, :3, :3]
                set_rotation(f, hip, w[1, :3, :3].T @ rh, hist)
                w = world(f)
                set_rotation(f, knee, w[hip, :3, :3].T @ rk, hist)
                w = world(f)
                set_rotation(f, ankle, w[knee, :3, :3].T @ rf, hist)
                f[boot][3:6] = ref[boot][3:6].copy()
                w = world(f)
                errors.append(float(np.linalg.norm(w[ankle, :3, 3] - goal)))
                plans.append(dict(tick=t, foot=boot, ankle=goal.tolist(), orientation=rf.tolist(), stance=target['stance'], phase=target['phase'], up=target['up']))
            poses.append(f)
        poses[-1][1:] = copy.deepcopy(poses[0][1:])
        channels = {(1, 7), (1, 8), (1, 3), (1, 4), (1, 5)} | {(b, c) for b in [2, 5] for c in [3, 4, 5, 6, 7, 8]} | {(b, c) for b in range(8, 16) for c in [3, 4, 5]}
        original = old.anims.anims[old.anims.table[slot]]
        a = replace_channels(original, poses, loop, n, channels - {(b, c) for b in [2, 5] for c in [6, 7, 8]}, tolerance=0)
        a = replace_channels(a, poses, loop, n, {(1, 7), (1, 8)} | {(b, c) for b in [2, 5] for c in [6, 7, 8]}, tolerance=0)
        if cycles:
            a = _forward(a, round(-speed * duration), duration)
            for ins in a.instrs:
                if ins['op'] == 'key':
                    for g in ins['bones']:
                        if g['bone'] == 0:
                            g['vals'].pop('tx', None)
                    ins['bones'] = [g for g in ins['bones'] if g['vals']]
            first = next((i for i in a.instrs if i['op'] == 'key' and i['frame'] == 1))
            first['bones'].append(dict(bone=0, div=1, vals={'tx': 0}))
            sound = next((i for i in original.instrs if i['op'] == 'sound'))
            a.instrs = [i for i in a.instrs if i['op'] != 'sound']
            ticks = [round(j * duration / (2 * cycles)) for j in range(2 * cycles)]
            for tick in ticks:
                event = dict(sound, frame=tick + 1)
                at = next((j for j, i in enumerate(a.instrs) if i.get('frame', -1) > tick + 1), len(a.instrs) - 1)
                a.instrs.insert(at, event)
        else:
            ticks = []
        a.instrs = [i for i in a.instrs if i['op'] != 'key' or i['bones']]
        a, merged = coalesce(a)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(a)
        reports.append(dict(slot=slot, duration=duration, cycles=cycles, period=period, speed=speed, contact=contact, duty=duty, lift=lift, rocks=rocks, body_heights=heights, maximum_FK_ankle_error=max(errors), plans=plans, channels=sorted(channels), footstep_ticks=ticks, merged_blocks=merged))
    idle_lifts = []
    for slot in [0]:
        fs, loop, _ = animsheet.slot_frames(old, n, slot)
        poses = copy.deepcopy(fs)
        for f in poses:
            f[1][7] -= 8
        a = replace_channels(old.anims.anims[old.anims.table[slot]], poses, loop, n, {(1, 7)}, tolerance=0)
        a, merged = coalesce(a)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(a)
        idle_lifts.append(dict(slot=slot, body_lift=8, original_other_channels_exact=True, period=len(fs) - 1, merged_blocks=merged))
    return (new, reports, idle_lifts)

def _bias(model, sk):
    for slot, bones in CONTACT_BIAS.items():
        poses, loop, _ = animsheet.slot_frames(model, 27, slot)
        for bone, corrections in bones.items():
            for tick, delta in corrections.items():
                poses[tick][bone][3:6] = [v + d for v, d in zip(poses[tick][bone][3:6], delta)]
            poses[-1][bone][3:6] = poses[0][bone][3:6].copy()
        animation = replace_channels(model.anims.anims[model.anims.table[slot]], poses, loop, 27, {(b, c) for b in bones for c in [3, 4, 5]}, tolerance=0)
        animation, _ = coalesce(animation)
        model.anims.table[slot] = len(model.anims.anims)
        model.anims.anims.append(animation)
    return model

def _verify(old, new, sk, solver):
    assert changed_programs(old, new) == [0, 1, 2, 3, 4]
    assert old.tmd.build() == new.tmd.build()
    assert len(old.anims.table) == len(new.anims.table)
    for slot in range(len(old.anims.table)):
        if slot <= 4:
            continue
        if old.anims.table[slot] is None:
            assert new.anims.table[slot] is None
            continue
        a = copy.deepcopy(old.anims.anims[old.anims.table[slot]])
        b = copy.deepcopy(new.anims.anims[new.anims.table[slot]])
        a.tail = b.tail = b''
        assert a.build() == b.build(), ('protected stream', slot)
    plans = {r['slot']: r for r in solver}
    checks = []
    maximum_shift_error = 0
    maximum_arm_rotation_error = 0
    for slot in range(5):
        source = old.anims.anims[old.anims.table[slot]]
        candidate = new.anims.anims[new.anims.table[slot]]
        sf, sl, se = animsheet.slot_frames(old, 27, slot)
        fs, loop, events = animsheet.slot_frames(new, 27, slot)
        duration = len(fs) - 1
        assert duration == len(sf) - 1 and sl == loop == 0
        assert [(t, k, d) for t, k, d in se if k != 'sound'] == [(t, k, d) for t, k, d in events if k != 'sound']
        assert [i for i in source.instrs if i['op'] not in ['key', 'sound']] == [i for i in candidate.instrs if i['op'] not in ['key', 'sound']]
        channels = {(1, 7)} if slot == 0 else {tuple(c) for c in plans[slot]['channels']}
        before = mmd.AnimPlayer(source, 27, slot)
        after = mmd.AnimPlayer(candidate, 27, slot)
        first = []
        for tick in range(duration * 9 + 1):
            assert before.tick() and after.tick()
            for bone in range(1, 27):
                assert before.pose[bone][:3] == after.pose[bone][:3]
                for c in range(9):
                    if (bone, c) not in channels:
                        assert before.pose[bone][c] == after.pose[bone][c], (slot, tick, bone, c)
            assert before.pose[0] == after.pose[0]
            assert all((before.pose[b] == after.pose[b] for b in [3, 4, 6, 7, 20, 21, 22, 23, 24, 25, 26]))
            if slot == 0:
                assert before.base == after.base
                assert after.pose[1][7] == before.pose[1][7] - 8
            else:
                assert after.root[:2] == [0, 0]
                assert after.base[2] == (0 if tick == 0 else -plans[slot]['speed'])
                assert all((before.pose[b][6:9] == after.pose[b][6:9] for b in range(8, 27)))
                assert all((before.pose[b] == after.pose[b] for b in range(16, 27)))
                if tick < duration:
                    reference = copy.deepcopy(before.pose)
                    reference[1] = copy.deepcopy(after.pose[1])
                    wr = np.array(mmd.bone_matrices(old, reference))
                    wa = np.array(mmd.bone_matrices(new, after.pose))
                    for shoulder, rx, shift in [(2, 25, [0, -20, 20]), (5, -15, [-15, -20, 0])]:
                        maximum_shift_error = max(maximum_shift_error, float(np.linalg.norm(wa[shoulder, :3, 3] - wr[shoulder, :3, 3] - np.array(shift))))
                        maximum_arm_rotation_error = max(maximum_arm_rotation_error, float(np.max(np.abs(wa[shoulder, :3, :3] - rotation([rx, 0, 0]) @ wr[shoulder, :3, :3]))))
            if tick < duration:
                first.append(copy.deepcopy(after.pose))
            else:
                assert after.pose == first[tick % duration], (slot, tick, 'drift')
        if slot >= 2:
            assert after.root[2] == -plans[slot]['speed'] * duration * 9
            cue = next((i for i in source.instrs if i['op'] == 'sound'))
            sounds = [i for i in candidate.instrs if i['op'] == 'sound']
            assert [i['frame'] - 1 for i in sounds] == plans[slot]['footstep_ticks']
            assert all(((i['bank'], i['note']) == (cue['bank'], cue['note']) for i in sounds))
        checks.append(dict(slot=slot, period=duration, nine_cycles_protected_channels_and_all_scales_exact=True, original_leg_joint_translations_exact=True, forearm_wrist_fringe_glasses_local_SRT_exact=True, primary_streamer_SRT_exact=True, pose_repeats_exact_nine_cycles=True, non_sound_controls_exact=True))
    assert maximum_shift_error < 1 and maximum_arm_rotation_error < 0.003, (maximum_shift_error, maximum_arm_rotation_error)
    return (checks, maximum_shift_error, maximum_arm_rotation_error)

def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE or len(sk) != 27 or [b[1] for b in sk] != PARENTS or ([b[0] for b in sk] != list(range(-1, 26))):
        raise ValueError('SuperStarmon requires its reviewed 27-bone showboat field source')
    old = _parse(data, sk)
    authored, solver, idle_lifts = _author(old, sk)
    primary = _pack(authored)
    assert hashlib.sha256(primary).hexdigest() == '58bbf44587ba435dca646799462d020d7ee14961400b0e01d218a5af4079c1bb'
    result = _pack(_bias(_parse(primary, sk), sk))
    assert hashlib.sha256(result).hexdigest() == 'ee1882fc0443b1fd5610604dca288d83728f467de4c08be2623a17be5ef148e5'
    checks, shift_error, rotation_error = _verify(old, _parse(result, sk), sk, solver)
    storage = motionstorage.audit(result, 27)
    assert storage['fits'], storage
    return (result, dict(species=244, source_sha256=SOURCE, output_sha256=hashlib.sha256(result).hexdigest(), changed_slots=[0, 1, 2, 3, 4], solver=solver, idle_lifts=idle_lifts, checks=checks, storage=storage, mesh_private33_care_battle_streams_exact=True, forearm_wrist_fringe_glasses_local_SRT_exact_nine_cycles=True, maximum_rigid_arm_shift_rounding_error=shift_error, maximum_rigid_arm_rotation_matrix_error=rotation_error, maximum_authored_contact_bias_angular_units=14, engine_dependency='Native83 clock from33, only rotations16..19 in field0..4. Rightroot16 VX+228/VY-400 clears raisedrightarm; all primary T/S and other R remain owned by the model.', reference_validation_limits='Triangle/support diagnostics and actual-game capture are separate. No all-terrain/turn/transition/continuous-sweep guarantee.'))
