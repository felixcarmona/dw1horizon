"""Starmon's boxing guard and alternating supported boot shuffle.

The rear boot keeps its native raised heel; the front boot keeps its sole.
Small authored ankle corrections account for the engine's interpolated poses.
A separate engine patch owns only antenna16..19 rotations on the native83 clock.
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
from tools.models.field_animations.war_greymon import set_rotation, align
SOURCE = 'd74966aca46a331cf921a6f6f356f24fb6921d8008c1f1c985bab048367a03c1'
PARENTS = [-1, 0, 1, 2, 3, 1, 5, 6, 1, 8, 9, 10, 1, 12, 13, 14, 1, 16, 1, 18]
# Small authored corrections to primary ankle rotations, fitted against full boot meshes
# at logical contacts and nominal 60 FPS interpolation; no source animation arrays.
CONTACT_BIAS = {2: {10: {0: [0, -1, 0],
          1: [-1, 0, 1],
          2: [-2, -2, 1],
          3: [0, -2, 0],
          8: [-1, -1, 1],
          9: [0, 0, 1],
          10: [-1, -4, 2],
          11: [0, -4, 1],
          15: [-1, -1, 0],
          16: [-2, -2, 1],
          17: [-1, -3, 2],
          18: [1, -3, 1]},
     14: {0: [0, 1, 0],
          4: [-1, 0, 0],
          5: [2, -1, -1],
          6: [2, 1, -1],
          7: [-1, 1, 0],
          11: [-1, 0, 1],
          12: [1, -1, -1],
          14: [0, 1, -1],
          19: [0, -1, 0],
          20: [1, -1, -1],
          21: [2, 1, -1]}},
 3: {10: {2: [0, 0, 1],
          3: [0, 0, -1],
          4: [-1, -1, 0],
          6: [-1, -1, 1],
          7: [1, -1, 0],
          13: [0, 0, 1],
          15: [-1, 1, 0],
          16: [0, 1, 1],
          17: [0, 0, -1],
          18: [0, 0, 1],
          19: [0, -1, 0],
          20: [0, -1, 0]},
     14: {0: [1, 0, 1],
          8: [0, 0, 1],
          9: [-1, 0, 0],
          10: [1, 0, 0],
          11: [-1, 0, 0],
          12: [1, 0, 0],
          21: [0, -1, 0],
          22: [0, -1, 0],
          23: [0, -1, 0],
          24: [1, 0, 0]}},
 4: {10: {0: [-6, -6, 7], 1: [-6, -4, 5], 7: [-4, -14, 9], 8: [-5, -13, 6]},
     14: {10: [3, 1, -2], 11: [5, 2, -2], 17: [5, 2, -2], 18: [3, 2, -2]}}}

def _parse(data, sk):
    mmd.exe().skeleton[243] = sk
    mmd.exe().bone_count[243] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = 243
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
        # The starplate's lower points need room behind the new shins.
        f[1][3:6] = [round(ref[1][c] + 0.3 * ((source[1][c] - ref[1][c] + 2048) % 4096 - 2048)) for c in [3, 4, 5]]
        f[1][4] += 199 if slot == 2 else 139

    def world(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, g))
    ref = animsheet.slot_frames(old, n, 0)[0][0]
    rw = world(ref)
    reports = []
    for slot in [2, 3, 4]:
        fs, loop, events = animsheet.slot_frames(old, n, slot)
        duration = len(fs) - 1
        cycles = {2: 3, 3: 2, 4: 3}[slot]
        period = duration / (cycles or 1)
        speed = {0: 0, 1: 0, 2: 12, 3: 6, 4: 32}[slot]
        duty = {0: 1, 1: 1, 2: 0.5, 3: 0.55, 4: 0.2}[slot]
        contact = period * duty
        lift = {0: 0, 1: 0, 2: 10, 3: 7, 4: 14}[slot]
        rocks = {0: [0, 0], 1: [0, 0], 2: [4, 6], 3: [3, 5], 4: [3, 4]}[slot]
        alltargets = []
        requirements = []
        # Keep the native boot/cuff compounds, including the rear raised heel.
        compound = {b: np.concatenate([vs[b], vs[b + 1] @ np.array(mmd.rot_matrix(*ref[b + 1][3:6])).T + np.array(ref[b + 1][6:9])]) for b in [10, 14]}
        for t, source in enumerate(fs[:-1]):
            f = copy.deepcopy(source)
            bodyguard(f, source)
            f[1][7] = 0
            f[1][8] += 8
            w = world(f)
            targets = []
            need = source[1][7]
            for side, (hip, knee, ankle, boot) in enumerate([(8, 9, 10, 11), (12, 13, 14, 15)]):
                sign = 1 if side == 0 else -1
                center = 90 if side == 0 else -14
                rock = rocks[side]
                phase = (t - side * period / 2) % period if cycles else 0
                on = not cycles or phase <= contact
                if not cycles:
                    z = center
                    up = 4
                    pitch = 0
                elif on:
                    z = center - speed * contact / 2 + speed * phase
                    up = 4
                    pitch = -rock + 2 * rock * phase / contact
                else:
                    u = (phase - contact) / (period - contact)
                    ease = 6 * u ** 5 - 15 * u ** 4 + 10 * u ** 3
                    half = speed * contact / 2
                    z = (center + half) * (1 - ease) + (center - half) * ease + (period - contact) * speed * u * (1 - u) * (1 - 2 * u) ** 5
                    up = 4 + lift * math.sin(math.pi * u)
                    pitch = rock * (1 - 2 * (3 * u * u - 2 * u * u * u)) + (period - contact) * (2 * rock / contact) * u * (1 - u) * (1 - 2 * u)
                rf, dz, _ = motionsecondary.rolling_foot(compound[ankle].tolist(), rw[ankle, :3, :3].tolist(), pitch)
                rf = np.array(rf)
                goal = np.array([sign * 76, -up - float((compound[ankle] @ rf.T)[:, 1].max()), z + dz])
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
        # A cyclic reach envelope anticipates support changes without a body snap.
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
            f[1][8] += 8
            for arm in range(2, 8):
                f[arm][3:6] = [round(ref[arm][c] + 0.35 * ((fs[t][arm][c] - ref[arm][c] + 2048) % 4096 - 2048)) for c in [3, 4, 5]]
            f[5][6] -= 12
            # Keep a boxing guard above the boots while retaining arm lengths.
            aw = world(f)
            for shoulder, elbow, hand in [(2, 3, 4), (5, 6, 7)]:
                h = aw[shoulder, :3, 3]
                e = aw[elbow, :3, 3]
                native_goal = aw[hand, :3, 3]
                goal = native_goal + np.array([25.0 if hand == 4 else 0.0, -10 if hand == 4 else -80 if slot == 3 else -35, -40.0 if hand == 4 else 0.0])
                a = np.linalg.norm(f[elbow][6:9])
                b = np.linalg.norm(f[hand][6:9])
                d = goal - h
                dist = np.linalg.norm(d)
                assert abs(a - b) < dist < a + b, (slot, t, hand, dist, a + b)
                direction = d / dist
                axis = (native_goal - h) / np.linalg.norm(native_goal - h)
                pole = e - h
                pole -= axis * (pole @ axis)
                pole -= direction * (pole @ direction)
                pole /= np.linalg.norm(pole)
                along = (a * a - b * b + dist * dist) / (2 * dist)
                joint = h + direction * along + pole * math.sqrt(max(0, a * a - along * along))
                rs = align(aw[shoulder, :3, :3] @ np.array(f[elbow][6:9]), joint - h) @ aw[shoulder, :3, :3]
                re = align(aw[elbow, :3, :3] @ np.array(f[hand][6:9]), goal - joint) @ aw[elbow, :3, :3]
                w = world(f)
                set_rotation(f, shoulder, w[1, :3, :3].T @ rs, hist)
                w = world(f)
                set_rotation(f, elbow, w[shoulder, :3, :3].T @ re, hist)
                w = world(f)
                set_rotation(f, hand, w[elbow, :3, :3].T @ aw[hand, :3, :3], hist)
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
        channels = {(1, 7), (1, 8), (1, 3), (1, 4), (1, 5), (5, 6)} | {(b, c) for b in range(2, 8) for c in [3, 4, 5]} | {(b, c) for b in range(8, 16) for c in [3, 4, 5]}
        original = old.anims.anims[old.anims.table[slot]]
        a = replace_channels(original, poses, loop, n, channels - {(5, 6)}, tolerance=0)
        a = replace_channels(a, poses, loop, n, {(1, 7), (1, 8), (5, 6)}, tolerance=0)
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
    for slot in [0, 1]:
        fs, loop, _ = animsheet.slot_frames(old, n, slot)
        poses = copy.deepcopy(fs)
        for f in poses:
            f[1][7] -= 4
        a = replace_channels(old.anims.anims[old.anims.table[slot]], poses, loop, n, {(1, 7)}, tolerance=0)
        a, merged = coalesce(a)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(a)
        idle_lifts.append(dict(slot=slot, body_lift=4, original_other_channels_exact=True, period=len(fs) - 1, merged_blocks=merged))
    return (new, reports, idle_lifts)

def _bias(model, sk):
    for slot, bones in CONTACT_BIAS.items():
        poses, loop, _ = animsheet.slot_frames(model, 20, slot)
        for bone, corrections in bones.items():
            for tick, delta in corrections.items():
                poses[tick][bone][3:6] = [v + d for v, d in zip(poses[tick][bone][3:6], delta)]
            poses[-1][bone][3:6] = poses[0][bone][3:6].copy()
        animation = replace_channels(model.anims.anims[model.anims.table[slot]], poses, loop, 20, {(b, c) for b in bones for c in [3, 4, 5]}, tolerance=0)
        animation, _ = coalesce(animation)
        model.anims.table[slot] = len(model.anims.anims)
        model.anims.anims.append(animation)
    return model

def _verify(old, new, solver):
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
    for slot in range(5):
        source = old.anims.anims[old.anims.table[slot]]
        candidate = new.anims.anims[new.anims.table[slot]]
        sf, sl, se = animsheet.slot_frames(old, 20, slot)
        fs, loop, events = animsheet.slot_frames(new, 20, slot)
        duration = len(fs) - 1
        assert duration == len(sf) - 1 and sl == loop == 0
        assert [(t, k, d) for t, k, d in se if k != 'sound'] == [(t, k, d) for t, k, d in events if k != 'sound']
        assert [i for i in source.instrs if i['op'] not in ['key', 'sound']] == [i for i in candidate.instrs if i['op'] not in ['key', 'sound']]
        channels = {(1, 7)} if slot < 2 else {tuple(c) for c in plans[slot]['channels']}
        before = mmd.AnimPlayer(source, 20, slot)
        after = mmd.AnimPlayer(candidate, 20, slot)
        first = []
        for tick in range(duration * 9 + 1):
            assert before.tick() and after.tick()
            for bone in range(1, 20):
                assert before.pose[bone][:3] == after.pose[bone][:3]
                for c in range(9):
                    if (bone, c) not in channels:
                        assert before.pose[bone][c] == after.pose[bone][c], (slot, tick, bone, c)
            assert before.pose[0] == after.pose[0]
            if slot < 2:
                assert before.base == after.base
                assert after.pose[1][7] == before.pose[1][7] - 4
            else:
                assert after.root[:2] == [0, 0]
                assert after.base[2] == (0 if tick == 0 else -plans[slot]['speed'])
                assert all((before.pose[b][6:9] == after.pose[b][6:9] for b in range(8, 20)))
                assert after.pose[5][6] == before.pose[5][6] - 12
                assert all((before.pose[b] == after.pose[b] for b in range(16, 20)))
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
        checks.append(dict(slot=slot, period=duration, nine_cycles_protected_channels_and_all_scales_exact=True, original_leg_joint_translations_exact=True, primary_antenna_SRT_exact=True, pose_repeats_exact_nine_cycles=True, non_sound_controls_exact=True))
    return checks

def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE or len(sk) != 20 or [b[1] for b in sk] != PARENTS or ([b[0] for b in sk] != list(range(-1, 19))):
        raise ValueError('Starmon requires its reviewed 20-bone boxing field source')
    old = _parse(data, sk)
    authored, solver, idle_lifts = _author(old, sk)
    primary = _pack(authored)
    assert hashlib.sha256(primary).hexdigest() == 'e73c948dfee7532d044f712e14d059f218ccb8635879cb99e3d733b00fc2db2c'
    result = _pack(_bias(_parse(primary, sk), sk))
    assert hashlib.sha256(result).hexdigest() == '5bd3db08a8849f4b30c0ed097c945c439dd997c001f4ae92f318e97b0307b2ac'
    checks = _verify(old, _parse(result, sk), solver)
    storage = motionstorage.audit(result, 20)
    assert storage['fits'], storage
    return (result, dict(species=243, source_sha256=SOURCE, output_sha256=hashlib.sha256(result).hexdigest(), changed_slots=[0, 1, 2, 3, 4], solver=solver, idle_lifts=idle_lifts, checks=checks, storage=storage, mesh_private33_care_battle_streams_exact=True, maximum_authored_contact_bias_angular_units=14, engine_dependency='Native83 clock from33; only rotations16..19 in field0..4, all other primary channels remain owned by this model.', reference_validation_limits='Triangle/support diagnostics and actual-game capture are separate. No all-terrain/turn/transition/continuous-sweep guarantee.'))
