"""Thundermon's short one-link rolling boots and carried boxing guard.

The original96 idle and20 poor gesture remain intact. Field movement keeps
its16/20/20 clocks with two/two/four short strides. Rigid oversized boots
roll while the body follows stance height; each short leg keeps its source
length. Glove counterrotation retains the native guard orientation, with
raised shoulder carries clearing the boots and keeping the eyes visible.
"""
import copy
import hashlib
import math
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
SOURCE = '0b6b17dc39c23e6483a6a012385585890ce152fd6dbbb78f6a669ba4fcccfc68'
OUTPUT = '2224d42ca69ef50f660edcabf15e51e71dee0c93ce1b92ee584afe64d2d82285'
PARENTS = [-1, 0, 1, 1, 3, 4, 1, 6, 7, 1, 9, 1, 11]

def _parse(data, sk):
    mmd.exe().skeleton[252] = sk
    mmd.exe().bone_count[252] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = 252
    return model

def _author(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    ref = copy.deepcopy(animsheet.slot_frames(old, n, 0)[0][0])
    verts = {b: np.array(old.tmd.obj_verts(o))[:, :3] for b, (o, _) in enumerate(sk) if o >= 0}
    reports = []

    def world(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, g))
    rw = world(ref)
    legs = [(9, 10, 1, 0), (11, 12, -1, 0.5)]
    for slot in [2, 3, 4]:
        sourcefs = animsheet.slot_frames(old, n, slot)[0]
        duration = len(sourcefs) - 1
        cycles = {2: 2, 3: 2, 4: 4}[slot]
        period = duration / cycles
        contact = period * (0.4 if slot == 4 else 0.5)
        speed = {2: 9, 3: 7, 4: 21}[slot]
        heel = {2: -15, 3: -10, 4: -15}[slot]
        toe = {2: 2, 3: 1, 4: 2}[slot]
        frames = []
        plans = []
        hist = {}
        errors = []

        def trajectory(t, foot, offset, centre):
            phase = (t + offset * period) % period
            stance = phase <= contact + 1e-08
            _, a, _ = S.rolling_foot(verts[foot].tolist(), np.eye(3).tolist(), heel)
            _, b, _ = S.rolling_foot(verts[foot].tolist(), np.eye(3).tolist(), toe)
            centre -= (a + b) / 2
            if stance:
                pitch = heel + (toe - heel) * phase / contact
                z = centre - speed * contact / 2 + speed * phase
                xout = 0
            else:
                u = (phase - contact) / (period - contact)
                smooth = 6 * u ** 5 - 15 * u ** 4 + 10 * u ** 3
                z = centre + speed * contact / 2 * (1 - 2 * smooth) + (period - contact) * speed * u * (1 - u) * (1 - 2 * u) ** 5
                pitch = toe + (heel - toe) * smooth + (period - contact) * (toe - heel) / contact * u * (1 - u) * (1 - 2 * u)
                xout = 6 * math.sin(math.pi * u) ** 2
            return dict(phase=phase, stance=stance, pitch=pitch, z=z, xout=xout)
        for t, source in enumerate(sourcefs):
            f = copy.deepcopy(source)
            f[1][3:6] = copy.deepcopy(ref[1][3:6])
            f[1][6:9] = [0, 0, 0]
            set_rotation(f, 1, rotation([{2: 2, 3: 5, 4: 7}[slot], 1.5 * math.sin(2 * math.pi * t / period), math.sin(2 * math.pi * t / period)]) @ np.array(mmd.rot_matrix(*ref[1][3:6])), hist)
            for shoulder, elbow, hand, sign in [(3, 4, 5, 1), (6, 7, 8, -1)]:
                f[shoulder][7] = source[shoulder][7] - (12 if shoulder == 3 else 30)
                phase = 2 * math.pi * t / period + (0 if sign == 1 else math.pi)
                amp = {2: 7, 3: 4, 4: 11}[slot]
                set_rotation(f, shoulder, rotation([amp * math.sin(phase), -sign * 25, -sign * 10]) @ np.array(mmd.rot_matrix(*ref[shoulder][3:6])), hist)
                set_rotation(f, elbow, rotation([-12 + 3 * math.sin(phase - 0.5), 0, 0]) @ np.array(mmd.rot_matrix(*ref[elbow][3:6])), hist)
                w = world(f)
                set_rotation(f, hand, w[elbow, :3, :3].T @ rw[hand, :3, :3], hist)
            f[9][6] = 24
            f[11][6] = -24
            f[9][8] = f[11][8] = 0
            w = world(f)
            targets = []
            heights = []
            for hip, foot, sign, offset in legs:
                h = w[hip, :3, 3]
                centre = (rotation([{2: 2, 3: 5, 4: 7}[slot], 0, 0]) @ np.array(mmd.rot_matrix(*ref[1][3:6])) @ np.array(f[hip][6:9]))[2]
                a = trajectory(t, foot, offset, centre)
                rf, dz, bottom = S.rolling_foot(verts[foot].tolist(), np.eye(3).tolist(), a['pitch'])
                a.update(hip=hip, foot=foot, rf=rf, bottom=bottom, x=sign * (33 + a['xout']), z=a['z'] + dz, centre=centre)
                L = np.linalg.norm(f[foot][6:9])
                reach = L * L - (a['x'] - h[0]) ** 2 - (a['z'] - h[2]) ** 2
                assert reach > 0, (slot, t, hip, 'reach', reach, a, h)
                a.update(reach=math.sqrt(reach), hip_without_bodyY=h.tolist())
                if a['stance']:
                    heights.append(-{2: 6, 3: 6, 4: 6}[slot] - bottom - math.sqrt(reach) - h[1])
                targets.append(a)
            assert heights
            f[1][7] = math.floor(min(heights))
            w = world(f)
            row = []
            for a in targets:
                hip, foot = (a['hip'], a['foot'])
                h = w[hip, :3, 3]
                goal = np.array([a['x'], h[1] + a['reach'], a['z']])
                rh = align(np.array(f[foot][6:9]), goal - h)
                set_rotation(f, hip, w[1, :3, :3].T @ rh, hist)
                w = world(f)
                set_rotation(f, foot, w[hip, :3, :3].T @ np.array(a['rf']), hist)
                errors.append(float(np.linalg.norm(world(f)[foot, :3, 3] - goal)))
                row.append(dict(foot=foot, stance=a['stance'], phase=a['phase'], pitch=a['pitch'], x=a['x'], z=a['z'], centre=a['centre'], ankle=goal.tolist(), orientation=a['rf'], up=-goal[1] - a['bottom']))
            frames.append(f)
            plans.append(row)
        frames[-1][1:] = copy.deepcopy(frames[0][1:])
        channels = {(b, c) for b in [1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] for c in [3, 4, 5]} | {(1, c) for c in [6, 7, 8]} | {(9, 6), (9, 8), (11, 6), (11, 8), (3, 7), (6, 7)}
        animation = replace_channels(old.anims.anims[old.anims.table[slot]], frames, 0, n, channels, tolerance=1)
        animation = replace_channels(animation, frames, 0, n, {(1, c) for c in [6, 7, 8]}, tolerance=0)
        temporary = copy.deepcopy(old)
        temporary.anims.table[slot] = len(temporary.anims.anims)
        temporary.anims.anims.append(animation)
        decoded = animsheet.slot_frames(temporary, n, slot)[0]
        fhist = {}
        for tick, f in enumerate(decoded):
            for hip, foot, j in [(9, 10, 0), (11, 12, 1)]:
                w = world(f)
                set_rotation(f, foot, w[hip, :3, :3].T @ np.array(plans[tick][j]['orientation']), fhist)
        decoded[-1][1:] = copy.deepcopy(decoded[0][1:])
        animation = replace_channels(animation, decoded, 0, n, {(b, c) for b in [10, 12] for c in [3, 4, 5]}, tolerance=0)
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
        reports.append(dict(slot=slot, period=duration, gait_period=period, cycles=cycles, speed=speed, contact=contact, heel=heel, toe=toe, channels=sorted(channels), plans=plans, footsteps=steps, maximum_FK_error=max(errors)))
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    return (new.build(), reports)

def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE or [b[1] for b in sk] != PARENTS or [b[0] for b in sk] != list(range(-1, 12)):
        raise ValueError('Thundermon requires its reviewed13-bone boxing source')
    old = _parse(data, sk)
    result, solver = _author(old, sk)
    assert hashlib.sha256(result).hexdigest() == OUTPUT
    actual = _parse(result, sk)
    assert changed_programs(old, actual) == [2, 3, 4] and old.tmd.build() == actual.tmd.build()
    checks = []
    max_guard_error = 0
    reference = animsheet.slot_frames(old, 13, 0)[0][0]
    rw = np.array(mmd.bone_matrices(old, reference))
    for row in solver:
        slot = row['slot']
        period = row['period']
        channels = {tuple(c) for c in row['channels']}
        before = mmd.AnimPlayer(old.anims.anims[old.anims.table[slot]], 13, slot)
        after = mmd.AnimPlayer(actual.anims.anims[actual.anims.table[slot]], 13, slot)
        for tick in range(period * 9 + 1):
            assert before.tick() and after.tick()
            for b in range(1, 13):
                for c in range(9):
                    if (b, c) not in channels:
                        assert before.pose[b][c] == after.pose[b][c], (slot, tick, b, c, 'protected')
            assert after.base == [0, 0, -row['speed']] if tick else after.base == [0, 0, 0]
            w = np.array(mmd.bone_matrices(actual, after.pose))
            for hand in [5, 8]:
                max_guard_error = max(max_guard_error, float(abs(w[hand, :3, :3] - rw[hand, :3, :3]).max()))
        fs, loop, events = animsheet.slot_frames(actual, 13, slot)
        sourcefs, sourceloop, sourceevents = animsheet.slot_frames(old, 13, slot)
        assert len(fs) == len(sourcefs) == period + 1 and loop == sourceloop == 0
        assert [(t, k, e) for t, k, e in events if k != 'sound'] == [(t, k, e) for t, k, e in sourceevents if k != 'sound']
        assert [t for t, k, e in events if k == 'sound'] == row['footsteps']
        checks.append(dict(slot=slot, nine_cycles_protected_SRT_exact=True, original_period=period, root_speed=row['speed'], root_X_Y_zero=True, source_sound_retimed_to_supports=row['footsteps']))
    assert max_guard_error < 0.006, max_guard_error
    storage = motionstorage.audit(result, 13)
    assert storage['fits'], storage
    return (result, dict(species=252, source_sha256=SOURCE, output_sha256=OUTPUT, changed_slots=[2, 3, 4], solver=solver, checks=checks, storage=storage, maximum_glove_world_rotation_matrix_error=max_guard_error, source_idle0_poor1_private33_care_battle_mesh_exact=True, all_scales_and_original_short_leg_lengths_exact=True, hip_anchor_shifts='9/11TX+24/-24,TZ0; originalboot10/12 localT retained.', shoulder_anchor_shifts='3TY-12 and6TY-30 for glove/boot clearance; elbow/hand localT retained.', limits='Decoded protection and storage only. Complete mesh/contact diagnostics, actual game and visual approval separate. One-link body follows supportingboot; contralateralsole maylift duringtransfer. No SDK/terrain/turn/transition continuous-sweep guarantee.'))
