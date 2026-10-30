"""ShellNumemon: native eye/mouth acting over a separate slug propulsion clock.

Retain the native104-tick face/eye performance and the distinct20-tick rearing
poor idle. Locomotion keeps the original pseudopod waveforms over five/four/six
cycles per104ticks, close to their original cadence. A bounded common-carrier
height envelope gives the shell weight without stretching joints. The snail
slides: its body is not assigned a biped's planted footprints.
"""
import copy
import hashlib
import math
import numeric as np
import mmd
import animsheet
import motioncyclelayer
import motionstorage
from tools.models.field_animations.articulation import replace_channels
from tools.models.field_animations.gliding import _forward
from motiontailspace import interpolate_pose
from motiondiscidentity import changed_programs

SOURCE = 'e1ccebf36cff30e6d2cdf8843ec345b58ae193fdb11d553360da99c3e56c6b12'
PARENTS = [-1, 0, 1, 2, 3, 4, 3, 6, 3, 8, 8, 10, 11, 8, 13, 14]


def _parse(data, sk):
    mmd.exe().skeleton[231] = sk
    mmd.exe().bone_count[231] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = 231
    return model


def _author(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    native = animsheet.slot_frames(old, n, 0)[0]
    vs = {b: np.array(old.tmd.obj_verts(o))[:, :3] for b, (o, _) in enumerate(sk) if o >= 0}
    reports = []

    def bottom(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        w = np.array(mmd.bone_matrices(old, g))
        return max((float((v @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max()) for b, v in vs.items()))
    assert native == animsheet.slot_frames(old, n, 33)[0]
    for slot in [0, 1, 2, 3, 4]:
        template = 1 if slot == 1 else 0
        fs, loop, events = animsheet.slot_frames(old, n, template)
        duration = len(fs) - 1
        poses = copy.deepcopy(fs)
        cycles = {0: 1, 1: 1, 2: 5, 3: 4, 4: 6}[slot]
        source_frames = animsheet.slot_frames(old, n, slot)[0]
        source_period = len(source_frames) - 1
        channels = {(1, 7)}
        distance = 0
        footsteps = []
        if slot in [2, 3, 4]:
            channels |= {(b, c) for b in range(2, 8) for c in [3, 4, 5]}
            distance = round((source_frames[-1][0][8] - source_frames[0][0][8]) * duration / source_period)
            for t, f in enumerate(poses):
                numerator = cycles * t * source_period % (duration * source_period)
                i, remainder = divmod(numerator, duration)
                lower = interpolate_pose(source_frames[i], source_frames[i + 1], remainder * 4096 // duration)
                for b in range(2, 8):
                    assert lower[b][:3] == f[b][:3] and lower[b][6:9] == f[b][6:9]
                    f[b][3:6] = copy.deepcopy(lower[b][3:6])
        offsets = [math.ceil(bottom(f) + 6) for f in poses[:-1]]
        offsets = [max((v - 2 * min((i - j) % duration, (j - i) % duration) for j, v in enumerate(offsets))) for i in range(duration)]
        for t, f in enumerate(poses):
            f[1][7] -= offsets[t % duration]
        poses[-1][1:] = copy.deepcopy(poses[0][1:])
        authored = replace_channels(old.anims.anims[old.anims.table[template]], poses, loop, n, channels)
        if slot in [2, 3, 4]:
            authored = _forward(authored, distance, duration)
            for j in range(cycles):
                for sound in old.anims.anims[old.anims.table[slot]].instrs:
                    if sound['op'] != 'sound':
                        continue
                    tick = round((j + (sound['frame'] - 1) / source_period) * duration / cycles)
                    footsteps.append(dict(sound, frame=tick + 1))
            footsteps.sort(key=lambda s: s['frame'])
            for sound in footsteps:
                at = next((i for i, k in enumerate(authored.instrs) if k.get('frame', -1) > sound['frame']), len(authored.instrs) - 1)
                authored.instrs.insert(at, sound)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
        reports.append(dict(slot=slot, template=template, duration=duration, source_period=source_period, body_cycles=cycles, body_period=duration / cycles, source_distance=source_frames[-1][0][8] - source_frames[0][0][8], distance=distance, source_units_per_tick=(source_frames[-1][0][8] - source_frames[0][0][8]) / source_period, selected_units_per_tick=distance / duration, channels=sorted(channels), carrier_Y_offsets=offsets, maximum_adjacent_Y_correction=max((abs(a - b) for a, b in zip(offsets, offsets[1:] + offsets[:1]))), sounds=footsteps))
    return new, reports


def build(data, sk):
    if (hashlib.sha256(data).hexdigest() != SOURCE or [b[1] for b in sk] != PARENTS
            or [b[0] for b in sk] != list(range(-1, 15))):
        raise ValueError('ShellNumemon requires its reviewed16-bone source')
    old = _parse(data, sk)
    new, solver = _author(old, sk)
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = _parse(result, sk)
    assert changed_programs(old, actual) == [0, 1, 2, 3, 4]
    assert old.tmd.build() == actual.tmd.build()
    checks = []
    for row in solver:
        slot, template, duration = row['slot'], row['template'], row['duration']
        source = old.anims.anims[old.anims.table[template]]
        selected = actual.anims.anims[actual.anims.table[slot]]
        original, loop, events = animsheet.slot_frames(old, 16, template)
        fs, selected_loop, selected_events = animsheet.slot_frames(actual, 16, slot)
        assert len(fs) == len(original) == duration + 1 and selected_loop == loop == 0
        assert [i for i in source.instrs if i['op'] not in ('key','sound')] == [i for i in selected.instrs if i['op'] not in ('key','sound')]
        assert [(t,k,e) for t,k,e in events if k != 'sound'] == [(t,k,e) for t,k,e in selected_events if k != 'sound']
        authored_channels = {tuple(c) for c in row['channels']}
        before, after = mmd.AnimPlayer(source, 16, template), mmd.AnimPlayer(selected, 16, slot)
        cycle, steps = [], []
        for tick in range(duration * 9 + 1):
            assert before.tick() and after.tick()
            assert before.root[:2] == after.root[:2] == [0,0]
            for bone in range(1,16):
                for channel in range(9):
                    if (bone, channel) not in authored_channels:
                        assert before.pose[bone][channel] == after.pose[bone][channel], (slot,tick,bone,channel)
                assert before.pose[bone][:3] == after.pose[bone][:3]
            assert [p[6:9] for p in before.pose[2:]] == [p[6:9] for p in after.pose[2:]]
            if tick < duration:
                cycle.append(copy.deepcopy(after.pose[1:]))
            else:
                assert after.pose[1:] == cycle[tick % duration], (slot,tick,'cyclic drift')
            steps.append(after.base[2])
        assert after.root[2] == row['distance'] * 9
        assert [sum(steps[1+i*duration:1+(i+1)*duration]) for i in range(9)] == [row['distance']] * 9
        assert max(steps[1:]) - min(steps[1:]) <= 1
        sounds = [i for i in selected.instrs if i['op'] == 'sound']
        assert sounds == row['sounds']
        assert all((i['bank'], i['note']) == (1,13) for i in sounds)
        assert len(sounds) == (2*row['body_cycles'] if slot in [2,3,4] else 0)
        lower_error = 0
        if slot in [2,3,4]:
            donor = animsheet.slot_frames(old,16,slot)[0]
            for tick,f in enumerate(fs[:-1]):
                numerator = (row['body_cycles'] * tick * row['source_period']) % (duration * row['source_period'])
                i,remainder = divmod(numerator, duration)
                expected = interpolate_pose(donor[i],donor[i+1],remainder*4096//duration)
                for bone in range(2,8):
                    for channel in [3,4,5]:
                        lower_error = max(lower_error,abs((f[bone][channel]-expected[bone][channel]+2048)%4096-2048))
            assert lower_error <= 3, (slot,'encoded pseudopod waveform',lower_error)
        assert row['maximum_adjacent_Y_correction'] <= 2
        checks.append(dict(slot=slot,template=template,duration=duration,
                           body_cycles=row['body_cycles'],body_period=row['body_period'],
                           source_units_per_tick=row['source_units_per_tick'],selected_units_per_tick=row['selected_units_per_tick'],
                           loop_distance=row['distance'],maximum_encoded_lower_rotation_error_SDK=lower_error,
                           protected_native_SRT_exact_nine_cycles=True,original_scales_exact=True,
                           all_joint_translations_except_global_carrier_Y_exact=True,
                           original_care_battle_private33_mesh_hierarchy_exact=True,
                           native_face_eye_clock_not_retimed=True,pose_and_root_repeat_nine_cycles=True,
                           original_body_waveform_preserved_with_bounded_cadence_change=True,
                           original_sound_bank_note_and_body_phase_retained=True))
    storage = motionstorage.audit(result,16)
    assert storage['fits'],storage
    return result,dict(species=231,source_sha256=SOURCE,output_sha256=hashlib.sha256(result).hexdigest(),
                       changed_slots=[0,1,2,3,4],native_period=104,poor_idle_period=20,
                       solver=solver,checks=checks,storage=storage,
                       preserved_slots='Every slot except0/1/2/3/4, including17/18care,private33andbattle')
