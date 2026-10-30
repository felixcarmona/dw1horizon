"""BomberNanimon's native boxing guard over reachable short-leg strides.

Retain the complete104-tick glove performance and distinct20-tick poor idle.
World-facing boots roll from heel to toe, while a cyclic body-height envelope
anticipates the reach of both original-length legs. Mirrored reference twist
removes the source left leg's interpolation asymmetry. Care, private33, battle,
mesh, hierarchy and every limb translation/scale stay exact.
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
from tools.models.field_animations.gliding import _forward
from motiondiscidentity import changed_programs
from tools.models.field_animations.war_greymon import rotation, set_rotation

SOURCE = '7fd9c5df4f4375200c88068b32e5e3a0a69a3c8dcf71d11a21b5e2013d39beb1'
PARENTS = [-1, 0, 1, 2, 3, 1, 5, 6, 1, 8, 9, 1, 11, 12, 1]


def _parse(data, sk):
    mmd.exe().skeleton[232] = sk
    mmd.exe().bone_count[232] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = 232
    return model


def _author(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    native = animsheet.slot_frames(old, n, 0)[0]
    vs = {b: np.array(old.tmd.obj_verts(o))[:, :3] for b, (o, _) in enumerate(sk) if o >= 0}

    def world(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, g))
    ref = copy.deepcopy(native[0])
    for r, l in [(8, 11), (9, 12), (10, 13)]:
        ref[l][3:6] = [ref[r][3], -ref[r][4], -ref[r][5]]
    rw = world(ref)
    reports = []
    assert native == animsheet.slot_frames(old, n, 33)[0]
    for slot in [0, 1, 2, 3, 4]:
        template = 1 if slot == 1 else 0
        fs, loop, events = animsheet.slot_frames(old, n, template)
        duration = len(fs) - 1
        cycles = {0: 1, 1: 1, 2: 10, 3: 8, 4: 13}[slot]
        period = duration / cycles
        duty = {0: 1, 1: 1, 2: 0.6, 3: 0.65, 4: 0.3}[slot]
        contact = period * duty
        speed = {0: 0, 1: 0, 2: 16, 3: 10, 4: 36}[slot]
        lift = {0: 0, 1: 0, 2: 10, 3: 6, 4: 8}[slot]
        heel = {0: 0, 1: 0, 2: -10, 3: -8, 4: -14}[slot]
        toe = {0: 0, 1: 0, 2: 22, 3: 16, 4: 22}[slot]
        pitchbase = {0: 0, 1: 0, 2: 2, 3: 4, 4: 6}[slot]
        rollamp = {0: 0, 1: 0, 2: 1.6, 3: 1.1, 4: 2.2}[slot]
        meanY = np.mean([f[1][7] for f in fs[:-1]])
        meanZ = np.mean([f[1][8] for f in fs[:-1]])
        poses = []
        hist = {}
        errors = []
        targets = []
        rawY = []

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
            pole = np.array([0.1 if hip == 8 else -0.1, 0, -1])

            def solve(y):
                goal[1] = y
                delta = goal - h
                dist = np.linalg.norm(delta)
                direction = delta / dist
                pp = pole - direction * (pole @ direction)
                pp /= np.linalg.norm(pp)
                along = (a * a - b * b + dist * dist) / (2 * dist)
                joint = h + direction * along + pp * math.sqrt(max(0, a * a - along * along))
                rh, rs = map(np.array, motionsecondary.native_plane_rotations([rw[v, :3, 3].tolist() for v in [hip, knee, foot]], [h.tolist(), joint.tolist(), goal.tolist()], [rw[v, :3, :3].tolist() for v in [hip, knee]]))
                bottom = max(float((vs[knee] @ rs.T + joint)[:, 1].max()), float((vs[foot] @ rf.T + goal)[:, 1].max()))
                return (bottom + up, rh, rs)
            assert solve(low)[0] <= 0 <= solve(high)[0], (slot, t, hip, 'Yreach', solve(low)[0], solve(high)[0], h, goal)
            for _ in range(27):
                mid = (low + high) / 2
                if solve(mid)[0] > 0:
                    high = mid
                else:
                    low = mid
            residual, rh, rs = solve((low + high) / 2)
            set_rotation(f, hip, w[1, :3, :3].T @ rh, hist)
            w = world(f)
            set_rotation(f, knee, w[hip, :3, :3].T @ rs, hist)
            w = world(f)
            set_rotation(f, foot, w[knee, :3, :3].T @ rf, hist)
            errors.append(float(np.linalg.norm(world(f)[foot, :3, 3] - goal)))
        for t, source in enumerate(fs):
            f = copy.deepcopy(source)
            f[0] = [4096] * 3 + [0] * 6
            theta = 2 * math.pi * cycles * t / duration
            if slot in [2, 3, 4]:
                set_rotation(f, 1, np.array(mmd.rot_matrix(*source[1][3:6])) @ rotation([pitchbase, 0, rollamp * math.sin(theta)]), hist)
                f[1][6] = round(2.5 * math.sin(theta))
            f[1][8] = round(meanZ + 0.25 * (source[1][8] - meanZ))
            wanted = round({0: -149, 1: -148, 2: -149, 3: -148, 4: -151}[slot] + 0.25 * (source[1][7] - meanY))
            f[1][7] = wanted
            w = world(f)
            row = []
            minimum = wanted
            reference = np.array(mmd.rot_matrix(*fs[0][1][3:6])) @ rotation([pitchbase, 0, 0])
            for side, (hip, knee, foot) in enumerate([(8, 9, 10), (11, 12, 13)]):
                sign = 1 if not side else -1
                center = meanZ + (reference @ np.array(source[hip][6:9]))[2] + 10
                if slot in [0, 1]:
                    x = sign * 40
                    z = center
                    up = 4
                    pitch = 0
                else:
                    phase = (2 * cycles * t - side * duration) % (2 * duration) / (2 * cycles)
                    half = speed * contact / 2
                    if phase <= contact:
                        u = phase / contact
                        smooth = u
                        x = sign * 40
                        z = center - half + speed * phase
                        up = 4
                        pitch = heel + (toe - heel) * smooth
                    else:
                        u = (phase - contact) / (period - contact)
                        smooth = 6 * u ** 5 - 15 * u ** 4 + 10 * u ** 3
                        z = (center + half) * (1 - smooth) + (center - half) * smooth + (period - contact) * speed * u * (1 - u) * (1 - 2 * u) ** 5
                        x = sign * (40 + 2 * math.sin(math.pi * u) ** 2)
                        up = 4 + lift * math.sin(math.pi * u)
                        pitch = toe * (1 - (3 * u * u - 2 * u * u * u)) + heel * (3 * u * u - 2 * u * u * u) + (toe - heel) / contact * (period - contact) * u * (1 - u) * (1 - 2 * u)
                rf, dz, bottom = motionsecondary.rolling_foot(vs[foot].tolist(), rotation([0, -sign * 5, 0]).tolist(), pitch)
                rf = np.array(rf)
                z += dz
                h = w[hip, :3, 3]
                length = np.linalg.norm(f[knee][6:9]) + np.linalg.norm(f[foot][6:9])
                reach = (length - 0.75) ** 2 - (x - h[0]) ** 2 - (z - h[2]) ** 2
                assert reach > 0, (slot, t, hip, 'horizontalreach', reach)
                goalY = -up - bottom
                minimum = max(minimum, goalY - (h[1] - f[1][7]) - math.sqrt(reach))
                row.append((hip, knee, foot, float(x), float(z), rf, float(up)))
            poses.append(f)
            targets.append(row)
            rawY.append(math.ceil(minimum))
        heights = [max((v - 2 * min((i - j) % duration, (j - i) % duration) for j, v in enumerate(rawY[:-1]))) for i in range(duration)]
        for t, f in enumerate(poses):
            f[1][7] = heights[t % duration]
            for hip, knee, foot, x, z, rf, up in targets[t]:
                leg(f, hip, knee, foot, x, z, rf, up)
            f[0] = copy.deepcopy(fs[t][0])
            f[0][8] = -speed * t
        for b in range(1, n):
            assert np.max(np.abs(np.array(mmd.rot_matrix(*poses[0][b][3:6])) - np.array(mmd.rot_matrix(*poses[-1][b][3:6])))) < 0.005, (slot, b, 'closure')
        poses[-1][1:] = copy.deepcopy(poses[0][1:])
        channels = {(1, 7), (1, 8)} | {(b, c) for b in range(8, 14) for c in [3, 4, 5]}
        if slot in [2, 3, 4]:
            channels |= {(1, 6)} | {(1, c) for c in [3, 4, 5]}
        authored = replace_channels(old.anims.anims[old.anims.table[template]], poses, loop, n, channels)
        footsteps = []
        if slot in [2, 3, 4]:
            authored = _forward(authored, -speed * duration, duration)
            sound = next((i for i in old.anims.anims[old.anims.table[slot]].instrs if i['op'] == 'sound'))
            footsteps = [round(j * duration / (2 * cycles)) for j in range(2 * cycles)]
            for tick in footsteps:
                event = dict(sound, frame=tick + 1)
                at = next((i for i, k in enumerate(authored.instrs) if k.get('frame', -1) > tick + 1), len(authored.instrs) - 1)
                authored.instrs.insert(at, event)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
        reports.append(dict(slot=slot, source_template=template, duration=duration, cycles=cycles, gait_period=period, contact=contact, speed=speed, heel_pitch=heel, toe_pitch=toe, lift=lift, body_pitch=pitchbase, body_roll=rollamp, meanZ=meanZ, carrier_Y=heights, footstep_ticks=footsteps, channels=sorted(channels), maximum_FK_ankle_error=max(errors)))
    return new, reports


def build(data, sk):
    if (hashlib.sha256(data).hexdigest() != SOURCE or [b[1] for b in sk] != PARENTS
            or [b[0] for b in sk] != list(range(-1,14))):
        raise ValueError('BomberNanimon requires its reviewed15-bone source')
    old = _parse(data, sk)
    new, solver = _author(old, sk)
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = _parse(result, sk)
    assert changed_programs(old,actual) == [0,1,2,3,4]
    assert old.tmd.build() == actual.tmd.build()
    checks = []
    for row in solver:
        slot,template,duration = row['slot'],row['source_template'],row['duration']
        source = old.anims.anims[old.anims.table[template]]
        selected = actual.anims.anims[actual.anims.table[slot]]
        original,loop,events = animsheet.slot_frames(old,15,template)
        fs,actual_loop,actual_events = animsheet.slot_frames(actual,15,slot)
        assert len(fs) == len(original) == duration+1 and loop == actual_loop == 0
        assert [i for i in source.instrs if i['op'] not in ('key','sound')] == [i for i in selected.instrs if i['op'] not in ('key','sound')]
        assert [(t,k,e) for t,k,e in events if k!='sound'] == [(t,k,e) for t,k,e in actual_events if k!='sound']
        channels = {tuple(c) for c in row['channels']}
        before,after = mmd.AnimPlayer(source,15,template),mmd.AnimPlayer(selected,15,slot)
        cycle=[]
        for tick in range(duration*9+1):
            assert before.tick() and after.tick()
            assert before.root[:2] == after.root[:2] == [0,0]
            for bone in range(1,15):
                for channel in range(9):
                    if (bone,channel) not in channels:
                        assert before.pose[bone][channel] == after.pose[bone][channel],(slot,tick,bone,channel)
                assert before.pose[bone][:3] == after.pose[bone][:3]
            assert [f[6:9]for f in before.pose[2:]] == [f[6:9]for f in after.pose[2:]]
            if tick<duration:cycle.append(copy.deepcopy(after.pose[1:]))
            else:assert after.pose[1:] == cycle[tick%duration],(slot,tick,'cyclic drift')
        assert after.root[2] == -row['speed']*duration*9
        sounds=[i for i in selected.instrs if i['op']=='sound']
        assert [i['frame']-1 for i in sounds] == row['footstep_ticks']
        assert all((i['bank'],i['note']) == (1,16)for i in sounds)
        assert len(sounds) == (2*row['cycles']if slot in [2,3,4]else 0)
        planned=row['carrier_Y'];assert max(abs(a-b)for a,b in zip(planned,planned[1:]+planned[:1]))<=2
        checks.append(dict(slot=slot,source_template=template,duration=duration,
                           strides_per_program=row['cycles'],gait_period=row['gait_period'],
                           forward_units_per_tick=row['speed'],
                           protected_native_channels_exact_nine_cycles=True,
                           original_scales_and_all_limb_joint_translations_exact=True,
                           boxing_arm_and_fuse_local_SRT_exact_nine_cycles=True,
                           original_private33_care_battle_mesh_hierarchy_exact=True,
                           no_dynamic_limb_stretch=True,pose_and_root_repeat_exact_nine_cycles=True,
                           original_non_sound_controls_exact=True,footstep_ticks=row['footstep_ticks'],
                           planned_carrier_Y_max_step=2,
                           decoded_carrier_Y_max_step=max(abs(a[1][7]-b[1][7])for a,b in zip(fs,fs[1:]))))
    storage=motionstorage.audit(result,15)
    assert storage['fits'],storage
    return result,dict(species=232,source_sha256=SOURCE,output_sha256=hashlib.sha256(result).hexdigest(),
                       changed_slots=[0,1,2,3,4],native_boxing_period=104,poor_idle_period=20,
                       checks=checks,solver=solver,storage=storage)
