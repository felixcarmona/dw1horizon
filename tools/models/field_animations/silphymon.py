"""Silphymon: planted composite boots/claws with complete native gestures.

Retain native80 upper and20-tick tired idle, level pelvis yaw/roll with
world-space torso compensation, and open the shoulder carry. Original
elbow, wrist, toe and tail local gestures remain exact. No limb stretching.
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

SOURCE = '92807df9ce74f3cd274c040db8ea509279481258bec8c9db7d3d7ada96ab5fc5'
PARENTS = [-1, 0, 1, 2, 3, 3, 2, 6, 7, 2, 9, 10, 1, 12, 13, 14, 1, 16, 17, 18, 1]

def _parse(data, sk):
    mmd.exe().skeleton[226] = sk
    mmd.exe().bone_count[226] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = 226
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
    ref[1][3:6] = [ref[1][3], 0, 0]
    for right, left in [(12, 16), (13, 17), (14, 18), (15, 19)]:
        ref[left][3:6] = [ref[right][3], -ref[right][4], -ref[right][5]]
    rw = world(ref)
    reports = []
    for slot in [0, 1, 2, 3, 4]:
        template_slot = 1 if slot == 1 else 33
        fs, loop, events = animsheet.slot_frames(old, n, template_slot)
        duration = len(fs) - 1
        period = {0: 80, 1: 20, 2: 16, 3: 20, 4: 10}[slot]
        contact = {0: 80, 1: 20, 2: 9, 3: 12, 4: 3}[slot]
        speed = {0: 0, 1: 0, 2: 12, 3: 9, 4: 30}[slot]
        lift = {0: 0, 1: 0, 2: 20, 3: 14, 4: 32}[slot]
        rock = {0: 0, 1: 0, 2: 5, 3: 4, 4: 7}[slot]
        poses = []
        hist = {}
        errors = []

        def leg(f, hip, knee, foot, toe, x, z, rf, up, footverts):
            w = world(f)
            h = w[hip, :3, 3]
            a = np.linalg.norm(f[knee][6:9])
            b = np.linalg.norm(f[foot][6:9])
            reach = (a + b - 0.1) ** 2 - (x - h[0]) ** 2 - (z - h[2]) ** 2
            assert reach > 0, (slot, t, hip, 'XZreach', reach)
            low = h[1] + 1
            high = h[1] + math.sqrt(reach)
            goal = np.array([x, 0.0, z])
            pole = np.array([1 if hip == 12 else -1, 0, -0.45])

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
                bottom = max(float((vs[knee] @ rs.T + joint)[:, 1].max()), float((footverts @ rf.T + goal)[:, 1].max()))
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
            original = np.array(mmd.rot_matrix(*source[1][3:6]))
            f[1][4:6] = [0, 0]
            neutral = np.array(mmd.rot_matrix(*f[1][3:6]))
            reparent = neutral.T @ original
            for branch in [2]:
                set_rotation(f, branch, reparent @ np.array(mmd.rot_matrix(*source[branch][3:6])), hist)
                f[branch][6:9] = np.rint(reparent @ np.array(source[branch][6:9])).astype(int).tolist()
            f[1][7] = round({0: -258, 1: -258, 2: -262, 3: -260, 4: -264}[slot] + (2 if slot in [0, 1] else 3) * math.sin(2 * math.pi * t / duration))
            if slot == 4:
                q = t % (period / 2)
                f[1][7] += round(2 * math.sin(math.pi * q / contact) ** 2 if q <= contact else -6 * math.sin(math.pi * (q - contact) / (period / 2 - contact)) ** 2)
            for shoulder, angle in [(6, -20), (9, 14)]:
                w = world(f)
                bias = np.array(rotation([0, 0, angle])) @ np.array(rotation([3 if shoulder == 9 else 0, 0, 0]))
                set_rotation(f, shoulder, w[2, :3, :3].T @ bias @ w[shoulder, :3, :3], hist)
            for side, (hip, knee, foot, toe) in enumerate([(12, 13, 14, 15), (16, 17, 18, 19)]):
                sign = 1 if not side else -1
                footverts = np.concatenate([vs[foot], vs[toe] @ np.array(mmd.rot_matrix(*f[toe][3:6])).T + np.array(f[toe][6:9])])
                if slot in [0, 1]:
                    x = sign * 115
                    z = 0
                    up = 4
                    pitch = 0
                else:
                    phase = (t - side * period / 2) % period
                    half = speed * contact / 2
                    if phase <= contact:
                        x = sign * 115
                        z = -half + speed * phase
                        up = 4
                        pitch = -rock * math.cos(math.pi * phase / contact)
                    else:
                        q = (phase - contact) / (period - contact)
                        smooth = 6 * q ** 5 - 15 * q ** 4 + 10 * q ** 3
                        z = half * (1 - smooth) - half * smooth + (period - contact) * speed * q * (1 - q) * (1 - 2 * q) ** 5
                        x = sign * (115 + 4 * math.sin(math.pi * q) ** 2)
                        up = 4 + lift * math.sin(math.pi * q)
                        pitch = rock * math.cos(math.pi * q) + 6 * math.sin(math.pi * q) ** 2
                rf, dz, _ = motionsecondary.rolling_foot(footverts.tolist(), rotation([0, -sign * 10, 0]).tolist(), pitch)
                leg(f, hip, knee, foot, toe, x, z + dz, np.array(rf), up, footverts)
            f[0] = copy.deepcopy(source[0])
            f[0][8] = -speed * t
            poses.append(f)
        for b in range(1, n):
            assert np.max(np.abs(np.array(mmd.rot_matrix(*poses[0][b][3:6])) - np.array(mmd.rot_matrix(*poses[-1][b][3:6])))) < 0.005, (slot, b, 'closure')
        poses[-1][1:] = copy.deepcopy(poses[0][1:])
        channels = {(b, c) for b in [6, 9] for c in [3, 4, 5]} | {(1, c) for c in [4, 5, 7]} | {(b, c) for b in [2] for c in [3, 4, 5, 6, 7, 8]} | {(b, c) for b in [12, 13, 14, 16, 17, 18] for c in [3, 4, 5]}
        authored = replace_channels(old.anims.anims[old.anims.table[template_slot]], poses, loop, n, channels)
        footsteps = []
        if slot in [2, 3, 4]:
            authored = _forward(authored, -speed * duration, duration)
            sound = next((i for i in old.anims.anims[old.anims.table[slot]].instrs if i['op'] == 'sound'))
            footsteps = [round(j * period / 2) for j in range(int(2 * duration / period))]
            for tick in footsteps:
                event = dict(sound, frame=tick + 1)
                at = next((i for i, k in enumerate(authored.instrs) if k.get('frame', -1) > tick + 1), len(authored.instrs) - 1)
                authored.instrs.insert(at, event)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
        reports.append(dict(slot=slot, source_template=template_slot, duration=duration, gait_period=period, contact=contact, speed=speed, footstep_ticks=footsteps, channels=sorted(channels), maximum_FK_ankle_error=max(errors)))
    return (new, reports)


def build(data, sk):
    if (hashlib.sha256(data).hexdigest() != SOURCE or [b[1] for b in sk] != PARENTS
            or [b[0] for b in sk] != list(range(-1,20))):
        raise ValueError('Silphymon requires the reviewed21-bone source')
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
        fs, loop, events = animsheet.slot_frames(actual, 21, slot)
        original, original_loop, original_events = animsheet.slot_frames(old, 21, template_slot)
        assert len(fs) == len(original) == duration + 1
        assert loop == original_loop == 0
        assert [i for i in source.instrs if i['op'] not in ('key','sound')] == [i for i in selected.instrs if i['op'] not in ('key','sound')]
        assert [(t,k,e) for t,k,e in events if k != 'sound'] == [(t,k,e) for t,k,e in original_events if k != 'sound']
        before, after = mmd.AnimPlayer(source,21,template_slot), mmd.AnimPlayer(selected,21,slot)
        cycle = []
        fixed = None
        max_world_rotation_error = 0.0
        max_joint_error = 0.0
        for tick in range(duration*9+1):
            assert before.tick() and after.tick()
            assert before.root[:2] == after.root[:2] == [0,0]
            for bone in range(1,21):
                for channel in range(9):
                    if (bone,channel) not in channels:
                        assert before.pose[bone][channel] == after.pose[bone][channel], (slot,tick,bone,channel)
                assert before.pose[bone][:3] == after.pose[bone][:3]
            translations = [after.pose[b][6:9] for b in range(12,20)]
            if fixed is None:
                fixed = copy.deepcopy(translations)
            assert translations == fixed
            assert all(after.pose[b][:3] == [4096]*3 for b in [1,12,13,14,15,16,17,18,19])
            if tick < duration:
                poses = [copy.deepcopy(before.pose), copy.deepcopy(after.pose)]
                for pose in poses:
                    pose[0] = [4096]*3 + [0]*6
                wb = np.array(mmd.bone_matrices(old, poses[0]))
                wa = np.array(mmd.bone_matrices(actual, poses[1]))
                shift = wa[1,:3,3] - wb[1,:3,3]
                for bone in [2,3,4,5]:
                    max_world_rotation_error = max(max_world_rotation_error, float(np.abs(wa[bone,:3,:3]-wb[bone,:3,:3]).max()))
                    max_joint_error = max(max_joint_error, float(np.linalg.norm(wa[bone,:3,3]-wb[bone,:3,3]-shift)))
                cycle.append(copy.deepcopy(after.pose))
            else:
                assert after.pose == cycle[tick % duration], (slot,tick,'cyclic drift')
        assert after.root[2] == -row['speed']*duration*9
        assert max_world_rotation_error < .005 and max_joint_error < 1.2
        sounds = [i for i in selected.instrs if i['op'] == 'sound']
        assert [i['frame']-1 for i in sounds] == row['footstep_ticks']
        assert all((i['bank'],i['note']) == (1,16) for i in sounds)
        assert len(sounds) == (0 if slot in [0,1] else 2*duration/row['gait_period'])
        checks.append(dict(slot=slot, source_template_slot=template_slot, duration=duration,
                           strides_per_program=duration/row['gait_period'], gait_period=row['gait_period'],
                           forward_units_per_tick=row['speed'],
                           maximum_torso_head_ear_world_rotation_error=max_world_rotation_error,
                           maximum_torso_head_ear_joint_error_after_carrier_shift=max_joint_error,
                           unselected_native_channels_exact_nine_cycles=True,
                           limb_joint_translations_and_scales_exact=True,
                           original_scales_exact=True, authored_translation_channels=[[1,7],[2,6],[2,7],[2,8]],
                           no_within_clip_limb_stretch=True, pose_repeat_exact_nine_cycles=True,
                           no_native_retiming=True, original_non_sound_controls_exact=True,
                           footstep_ticks=row['footstep_ticks']))
    storage = motionstorage.audit(result,21)
    assert storage['fits'], storage
    return result, dict(species=226, source_sha256=SOURCE,
                        output_sha256=hashlib.sha256(result).hexdigest(),
                        changed_slots=[0,1,2,3,4], mesh_skeleton_private33_care_battle_exact=True,
                        native_upper_period=80, distinct_tired_idle_period=20,
                        checks=checks, solver=solver, storage=storage)
