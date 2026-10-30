"""Shurimon's native83-tick gestures over planted, springy ninja strides.

Five, four and eight strides close inside the original83-tick performance.
Fractional phases are baked to ordinary integer-frame MMD programs; playback
needs no new runtime code. Original mood1 keeps its distinct16-tick acting.
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

SOURCE = '48260d97ee5cbdc54e76dae549e22bbc36ea6211e3eb455e0212379e355ad3a6'
PARENTS = [-1,16,1,2,2,1,1,1,7,8,9,1,1,12,13,14,0,16,17,18,16,20,21]


def _parse(data, sk):
    mmd.exe().skeleton[225] = sk
    mmd.exe().bone_count[225] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = 225
    return model


def _author(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    native = animsheet.slot_frames(old, n, 33)[0]
    vs = {b: np.array(old.tmd.obj_verts(o))[:, :3] for b, (o, _) in enumerate(sk) if o >= 0}
    def world(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, g))
    ref = copy.deepcopy(native[0])
    for right, left in [(17, 20), (18, 21), (19, 22)]:
        ref[left][3:6] = [ref[right][3], -ref[right][4], -ref[right][5]]
    rw = world(ref)
    reports = []
    for slot in [0, 1, 2, 3, 4]:
        template_slot = 1 if slot == 1 else 33
        fs, loop, events = animsheet.slot_frames(old, n, template_slot)
        duration = len(fs) - 1
        cycles = {0: 1, 1: 1, 2: 5, 3: 4, 4: 8}[slot]
        period = duration / cycles
        duty = {0: 1, 1: 1, 2: 0.6, 3: 0.65, 4: 0.3}[slot]
        contact = period * duty
        speed = {0: 0, 1: 0, 2: 10, 3: 7, 4: 24}[slot]
        lift = {0: 0, 1: 0, 2: 12, 3: 8, 4: 22}[slot]
        rock = {0: 0, 1: 0, 2: 2, 3: 1, 4: 3}[slot]
        mean = np.mean([f[16][7] for f in fs[:-1]])
        poses = []
        hist = {}
        errors = []

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
            pole = w[16, :3, :3] @ np.array([1 if hip == 17 else -1, 0, 0])

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
            set_rotation(f, hip, w[16, :3, :3].T @ rh, hist)
            w = world(f)
            set_rotation(f, knee, w[hip, :3, :3].T @ rs, hist)
            w = world(f)
            set_rotation(f, foot, w[knee, :3, :3].T @ rf, hist)
            errors.append(float(np.linalg.norm(world(f)[foot, :3, 3] - goal)))
        for t, source in enumerate(fs):
            f = copy.deepcopy(source)
            f[0] = [4096] * 3 + [0] * 6
            if slot == 1:
                f[16][7] = -129
            if slot in [2, 3, 4]:
                f[16][7] = round({2: -130, 3: -128, 4: -132}[slot] + 0.5 * (source[16][7] - mean))
                if slot == 4:
                    q = 2 * cycles * t % duration / (2 * cycles)
                    half = period / 2
                    f[16][7] += round(2 * math.sin(math.pi * q / contact) ** 2 if q <= contact else -4 * math.sin(math.pi * (q - contact) / (half - contact)) ** 2)
            for side, (hip, knee, foot) in enumerate([(17, 18, 19), (20, 21, 22)]):
                sign = 1 if not side else -1
                if slot in [0, 1]:
                    x = sign * 100
                    z = 10
                    up = 4
                    pitch = 0
                else:
                    numerator = (2 * cycles * t - side * duration) % (2 * duration)
                    phase = numerator / (2 * cycles)
                    half = speed * contact / 2
                    if phase <= contact:
                        x = sign * 100
                        z = 10 - half + speed * phase
                        up = 4
                        pitch = -rock * math.cos(math.pi * phase / contact)
                    else:
                        q = (phase - contact) / (period - contact)
                        smooth = 6 * q ** 5 - 15 * q ** 4 + 10 * q ** 3
                        z = (10 + half) * (1 - smooth) + (10 - half) * smooth + (period - contact) * speed * q * (1 - q) * (1 - 2 * q) ** 5
                        x = sign * (100 + 4 * math.sin(math.pi * q) ** 2)
                        up = 4 + lift * math.sin(math.pi * q)
                        pitch = rock * math.cos(math.pi * q) + 4 * math.sin(math.pi * q) ** 2
                rf, dz, _ = motionsecondary.rolling_foot(vs[foot].tolist(), rotation([0, 0, 0]).tolist(), pitch)
                leg(f, hip, knee, foot, x, z + dz, np.array(rf), up)
            f[0] = copy.deepcopy(source[0])
            f[0][8] = -speed * t
            poses.append(f)
        for b in range(1, n):
            assert np.max(np.abs(np.array(mmd.rot_matrix(*poses[0][b][3:6])) - np.array(mmd.rot_matrix(*poses[-1][b][3:6])))) < 0.005, (slot, b, 'closure')
        poses[-1][1:] = copy.deepcopy(poses[0][1:])
        channels = {(16, 7)} | {(b, c) for b in range(17, 23) for c in [3, 4, 5]}
        authored = replace_channels(old.anims.anims[old.anims.table[template_slot]], poses, loop, n, channels)
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
        reports.append(dict(slot=slot, source_template=template_slot, duration=duration, cycles=cycles, gait_period=period, contact=contact, speed=speed, footstep_ticks=footsteps, channels=sorted(channels), maximum_FK_ankle_error=max(errors)))
    return new, reports


def build(data, sk):
    if (hashlib.sha256(data).hexdigest() != SOURCE or [b[1] for b in sk] != PARENTS
            or [b[0] for b in sk] != list(range(-1,22))):
        raise ValueError('Shurimon requires the reviewed23-bone source')
    old = _parse(data, sk)
    new, solver = _author(old, sk)
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = _parse(result, sk)
    assert changed_programs(old, actual) == [0,1,2,3,4]
    assert old.tmd.build() == actual.tmd.build()
    checks = []
    for row in solver:
        slot, template_slot, duration = row['slot'], row['source_template'], row['duration']
        source = old.anims.anims[old.anims.table[template_slot]]
        selected = actual.anims.anims[actual.anims.table[slot]]
        channels = {tuple(c) for c in row['channels']}
        fs, loop, events = animsheet.slot_frames(actual, 23, slot)
        original, original_loop, original_events = animsheet.slot_frames(old, 23, template_slot)
        assert len(fs) == len(original) == duration + 1
        assert loop == original_loop == 0
        assert [i for i in source.instrs if i['op'] not in ('key','sound')] == [i for i in selected.instrs if i['op'] not in ('key','sound')]
        assert [(t,k,e) for t,k,e in events if k != 'sound'] == [(t,k,e) for t,k,e in original_events if k != 'sound']
        before, after = mmd.AnimPlayer(source,23,template_slot), mmd.AnimPlayer(selected,23,slot)
        cycle = []
        fixed = None
        for tick in range(duration*9+1):
            assert before.tick() and after.tick()
            assert before.root[:2] == after.root[:2] == [0,0]
            for bone in range(1,23):
                for channel in range(9):
                    if (bone,channel) not in channels:
                        assert before.pose[bone][channel] == after.pose[bone][channel], (slot,tick,bone,channel)
                assert before.pose[bone][:3] == after.pose[bone][:3]
            translations = [after.pose[b][6:9] for b in range(17,23)]
            if fixed is None:
                fixed = copy.deepcopy(translations)
            assert translations == fixed
            assert all(after.pose[b][:3] == [4096]*3 for b in [16,17,18,19,20,21,22])
            if tick < duration:
                cycle.append(copy.deepcopy(after.pose))
            else:
                assert after.pose == cycle[tick % duration], (slot,tick,'cyclic drift')
        assert after.root[2] == -row['speed']*duration*9
        sounds = [i for i in selected.instrs if i['op'] == 'sound']
        assert [i['frame']-1 for i in sounds] == row['footstep_ticks']
        assert all((i['bank'],i['note']) == (1,16) for i in sounds)
        assert len(sounds) == (0 if slot in [0,1] else 2*row['cycles'])
        checks.append(dict(slot=slot, source_template_slot=template_slot, duration=duration,
                           strides_per_program=row['cycles'], gait_period=row['gait_period'],
                           forward_units_per_tick=row['speed'],
                           unselected_native_channels_exact_nine_cycles=True,
                           limb_joint_translations_and_scales_exact=True,
                           original_scales_exact=True, authored_translation_channels=[[16,7]],
                           no_within_clip_limb_stretch=True, pose_repeat_exact_nine_cycles=True,
                           no_native_retiming=True, original_non_sound_controls_exact=True,
                           footstep_ticks=row['footstep_ticks']))
    storage = motionstorage.audit(result,23)
    assert storage['fits'], storage
    return result, dict(species=225, source_sha256=SOURCE,
                        output_sha256=hashlib.sha256(result).hexdigest(),
                        changed_slots=[0,1,2,3,4], mesh_skeleton_private33_care_battle_exact=True,
                        native_upper_period=83, distinct_tired_idle_period=16,
                        checks=checks, solver=solver, storage=storage)
