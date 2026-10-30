"""Infermon's six rigid leg chains with alternating tripod supports.

Keep every original field clock and shell/head gesture. Replace idle leg
scale warping with the original moving S/T, solve the native upward arches,
and hold each two-mesh paw flat through stance. Rear poles clear the shell.
"""
import copy
import hashlib
import math
import numeric as np
import mmd
import animsheet
import motionsecondary as S
import legik
import motioncyclelayer
import motionstorage
from tools.models.field_animations.channels import replace_channels, coalesce
from tools.models.field_animations.gliding import _forward
from tools.models.field_animations.war_greymon import rotation, set_rotation
from motiondiscidentity import changed_programs, program
SOURCE = '69472e6b75337d6badc746ad61f2093e005432e6e901309d2cd2c44e41f584f6'
OUTPUT = '8957e6fef954d0e593bc23c99996e3fa0b1c84370920dc5f4a4cccf3b61ad6f2'
PARENTS = [-1, 0, 1, 2, 3, 1, 5, 6, 7, 1, 9, 10, 11, 1, 13, 14, 15, 1, 17, 18, 19, 1, 21, 22, 23, 1, 25, 26, 27, 1]

def _parse(data, sk):
    mmd.exe().skeleton[246] = sk
    mmd.exe().bone_count[246] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = 246
    return model

def _author(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    legs = [(5, 6, 7, 8, 1, 0), (9, 10, 11, 12, -1, 0.5), (13, 14, 15, 16, 1, 0.5), (17, 18, 19, 20, -1, 0), (21, 22, 23, 24, 1, 0), (25, 26, 27, 28, -1, 0.5)]
    ref = copy.deepcopy(animsheet.slot_frames(old, n, 0)[0][0])
    fixed = animsheet.slot_frames(old, n, 2)[0][0]
    for b in range(5, 29):
        ref[b][:3] = fixed[b][:3].copy()
        ref[b][6:9] = fixed[b][6:9].copy()

    def world(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, g))
    rw = world(ref)
    verts = {b: np.array(old.tmd.obj_verts(o))[:, :3] for b, (o, _) in enumerate(sk) if o >= 0}
    reference = {}
    reports = []
    for h, k, foot, pad, sign, offset in legs:
        yaw = math.atan2(rw[foot, 0, 2], rw[foot, 2, 2])
        rf = rotation([0, math.degrees(yaw), 0])
        reference[foot] = rf
    for slot in [0, 1, 2, 3, 4]:
        template = slot
        fs, loop, events = animsheet.slot_frames(old, n, template)
        duration = len(fs) - 1
        cycles = {0: 0, 1: 0, 2: 1, 3: 1, 4: 1}[slot]
        period = duration / cycles if cycles else duration
        duty = {0: 1, 1: 1, 2: 0.55, 3: 0.62, 4: 0.5}[slot]
        contact = period * duty
        speed = {0: 0, 1: 0, 2: 14, 3: 9, 4: 30}[slot]
        lift = {0: 0, 1: 0, 2: 35, 3: 22, 4: 50}[slot]
        hist = {}
        frames = []
        plan = []
        errors = []
        for t, src in enumerate(fs):
            f = copy.deepcopy(src)
            f[1][7] -= {0: 8, 1: 8, 2: 0, 3: 22, 4: 0}[slot]
            for b in range(5, 29):
                f[b][:3] = fixed[b][:3].copy()
                f[b][6:9] = fixed[b][6:9].copy()
            row = []
            for number, (h, k, foot, pad, sign, offset) in enumerate(legs):
                phase = (t + offset * period) % period
                stance = not cycles or phase <= contact
                x = 32 + sign * [260, 500, 260][number // 2]
                centre = [-275, 60, 385][number // 2]
                up = 5
                if not cycles:
                    z = centre
                elif stance:
                    z = centre - speed * contact / 2 + speed * phase
                else:
                    u = (phase - contact) / (period - contact)
                    smooth = 6 * u ** 5 - 15 * u ** 4 + 10 * u ** 3
                    z = centre + speed * contact / 2 * (1 - 2 * smooth) + (period - contact) * speed * u * (1 - u) * (1 - 2 * u) ** 5
                    up += lift * math.sin(math.pi * u) ** 2
                rf = reference[foot]
                f[pad][3:6] = fixed[pad][3:6].copy()
                rpad = np.array(mmd.rot_matrix(*f[pad][3:6]))
                sf = np.diag(np.array(f[foot][:3]) / 4096)
                sp = np.diag(np.array(f[pad][:3]) / 4096)
                compound = np.concatenate([verts[foot] @ sf.T, (verts[pad] @ (rpad @ sp).T + f[pad][6:9]) @ sf.T])
                bottom = float((compound @ rf.T)[:, 1].max())
                goal = np.array([x, -up - bottom, z])
                w = world(f)
                root = w[h, :3, 3]
                reference_points = [rw[b, :3, 3].tolist() for b in [h, k, foot]]
                pole = S.transported_native_pole(*reference_points, root.tolist(), goal.tolist())
                pole[1] -= 100
                if h in [21, 25]:
                    pole[0] += sign * 200
                joint, end = legik.solve(root.tolist(), goal.tolist(), float(np.linalg.norm(f[k][6:9])), float(np.linalg.norm(f[foot][6:9])), pole)
                rh, rk = map(np.array, S.native_plane_rotations(reference_points, [root.tolist(), joint, end], [rw[b, :3, :3].tolist() for b in [h, k]]))
                set_rotation(f, h, w[1, :3, :3].T @ rh, hist)
                w = world(f)
                set_rotation(f, k, w[h, :3, :3].T @ rk, hist)
                w = world(f)
                set_rotation(f, foot, w[k, :3, :3].T @ rf, hist)
                w = world(f)
                errors.append(float(np.linalg.norm(w[foot, :3, 3] - goal)))
                row.append(dict(foot=foot, pad=pad, phase=phase, stance=stance, target=goal.tolist(), up=up, yaw_degrees=math.degrees(math.atan2(rf[0, 2], rf[2, 2]))))
            frames.append(f)
            plan.append(row)
        frames[-1][1:] = copy.deepcopy(frames[0][1:])
        channels = {(b, c) for b in range(5, 29) for c in range(9)} | {(1, 7)}
        animation = replace_channels(old.anims.anims[old.anims.table[template]], frames, 0, n, channels, tolerance=2)
        animation = replace_channels(animation, frames, 0, n, {(1, 7)}, tolerance=0)
        animation, _ = coalesce(animation)
        player = mmd.AnimPlayer(animation, n, slot)
        decoded = []
        while player.tick(stop_at_infinite_loop=True):
            decoded.append(copy.deepcopy(player.pose))
        assert len(decoded) == duration + 1
        hist2 = {}
        for f in decoded:
            for h, k, foot, pad, sign, offset in legs:
                w = world(f)
                set_rotation(f, foot, w[k, :3, :3].T @ reference[foot], hist2)
        decoded[-1][1:] = copy.deepcopy(decoded[0][1:])
        animation = replace_channels(animation, decoded, 0, n, {(b, c) for b in [7, 11, 15, 19, 23, 27] for c in [3, 4, 5]}, tolerance=0)
        animation, _ = coalesce(animation)
        if cycles:
            for instruction in animation.instrs:
                if instruction['op'] == 'key':
                    for group in instruction['bones']:
                        if group['bone'] == 0:
                            group['vals'].pop('tx', None)
                    instruction['bones'] = [g for g in instruction['bones'] if g['vals']]
            animation = _forward(animation, -speed * duration, duration)
            first = next((i for i in animation.instrs if i['op'] == 'key' and i['frame'] == 1))
            first['bones'].append(dict(bone=0, div=1, vals={'tx': 0}))
        sound_ticks = []
        if cycles:
            original = old.anims.anims[old.anims.table[slot]]
            cue = next((i for i in original.instrs if i['op'] == 'sound'), None)
            if cue:
                animation.instrs = [i for i in animation.instrs if i['op'] != 'sound']
                for tick in sorted({round((j + offset) * period) % duration for j in range(cycles) for offset in [0, 0.5]}):
                    event = dict(cue, frame=tick + 1)
                    at = next((i for i, v in enumerate(animation.instrs) if v.get('frame', -1) > tick + 1), len(animation.instrs) - 1)
                    animation.instrs.insert(at, event)
                    sound_ticks.append(tick)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(animation)
        reports.append(dict(slot=slot, template=template, period=duration, cycles=cycles, gait_period=period, duty=duty, speed=speed, maximum_ankle_FK_error=max(errors), footsteps=sound_ticks, plan=plan))
    for a in new.anims.anims:
        a.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    data = new.build()
    return (data, reports)

def _verify(old, new, sk):
    n = len(sk)
    assert old.tmd.build() == new.tmd.build() and changed_programs(old, new) == [0, 1, 2, 3, 4]
    fixed = animsheet.slot_frames(old, n, 2)[0][0]
    checks = []
    for slot in range(len(old.anims.table)):
        if slot in range(5):
            continue
        i, j = (old.anims.table[slot], new.anims.table[slot])
        assert (i is None) == (j is None)
        if i is not None:
            assert program(old.anims.anims[i]) == program(new.anims.anims[j]), slot
    for slot in range(5):
        a = old.anims.anims[old.anims.table[slot]]
        b = new.anims.anims[new.anims.table[slot]]
        fs, loop, ev = animsheet.slot_frames(old, n, slot)
        duration = len(fs) - 1
        ns, nl, nev = animsheet.slot_frames(new, n, slot)
        assert len(ns) == len(fs) and loop == nl == 0
        before = mmd.AnimPlayer(a, n, slot)
        after = mmd.AnimPlayer(b, n, slot)
        first = []
        for tick in range(duration * 9 + 1):
            assert before.tick() and after.tick()
            for bone in [1, 2, 3, 4, 29]:
                for c in range(9):
                    if c in [3, 4, 5]:
                        assert (before.pose[bone][c] - after.pose[bone][c]) % 4096 == 0, (slot, tick, bone, c)
                    else:
                        assert before.pose[bone][c] - ({0: 8, 1: 8, 2: 0, 3: 22, 4: 0}[slot] if bone == 1 and c == 7 else 0) == after.pose[bone][c], (slot, tick, bone, c)
            for bone in range(5, 29):
                assert after.pose[bone][:3] == fixed[bone][:3] and after.pose[bone][6:9] == fixed[bone][6:9], (slot, tick, bone)
            if slot > 1:
                assert after.base[:2] == [0, 0] and after.base[2] == (0 if tick == 0 else -{2: 14, 3: 9, 4: 30}[slot]), (slot, tick, after.base)
            else:
                assert after.base == before.base
            if tick < duration:
                first.append(copy.deepcopy(after.pose))
            else:
                assert all(((after.pose[b][c] - first[tick % duration][b][c]) % 4096 == 0 if c in [3, 4, 5] else after.pose[b][c] == first[tick % duration][b][c] for b in range(n) for c in range(9))), (slot, tick, 'drift')
        assert [i for i in a.instrs if i['op'] not in ['key', 'sound']] == [i for i in b.instrs if i['op'] not in ['key', 'sound']]
        assert [(t, k, d) for t, k, d in ev if k != 'sound'] == [(t, k, d) for t, k, d in nev if k != 'sound']
        oldvoice = {(i['bank'], i['note']) for i in a.instrs if i['op'] == 'sound'}
        newvoice = {(i['bank'], i['note']) for i in b.instrs if i['op'] == 'sound'}
        assert oldvoice == newvoice
        checks.append(dict(slot=slot, period=duration, nine_cycles_upper_body_head29_SRT_exact_except_declared_bodyY_lift=True, nine_cycles_constant_leg_S_T_original_moving_values=True, nine_cycles_pose_stable=True, non_sound_controls_events_exact=True, original_footstep_voices_exact=True))
    return checks

def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE or len(sk) != 30 or [v[1] for v in sk] != PARENTS or ([v[0] for v in sk] != list(range(-1, 29))):
        raise ValueError('Infermon requires its reviewed 30-bone six-legged source')
    old = _parse(data, sk)
    result, solver = _author(old, sk)
    assert hashlib.sha256(result).hexdigest() == OUTPUT
    checks = _verify(old, _parse(result, sk), sk)
    storage = motionstorage.audit(result, len(sk))
    assert storage['fits'], storage
    return (result, dict(species=246, source_sha256=SOURCE, output_sha256=OUTPUT, changed_slots=[0, 1, 2, 3, 4], solver=solver, checks=checks, storage=storage, mesh_private33_care_battle_streams_exact=True, constant_leg_S_T_basis='Original moving slot2 first pose; removes original idle leg-scale and hip5-anchor warping. Original moving limb dimensions and paw2.5scale retained.', body_Y_lifts={0: 8, 1: 8, 2: 0, 3: 22, 4: 0}, root_X_wobble_removed=True, engine_dependency=None, reference_validation_limits='Complete-mesh/contact diagnostics and actual-game playback are checked separately; no all-terrain, SDK rounding, turn, transition or continuous-sweep guarantee.'))
