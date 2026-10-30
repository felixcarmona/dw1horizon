"""Reviewed steady glides, retaining every native pose channel.

The reviewed species already have native field performances. Explicit
review found irregular forward bursts in selected controllers. Replace only
root TZ momentum, preserving each loop's net travel,
all body instructions, event timing, and private33/care/battle programs.
"""
import copy
import hashlib
import mmd
import animsheet
import motioncyclelayer
import motionstorage
from motiondiscidentity import changed_programs

SOURCE = '10a3edac4524e2cd8a05b169b61502d5e767a1ace7e798a436cb8efb4ed95eba'
SOURCE214 = '8f19f0d472ccf9d6950e0688924344eefe7e68c3e1dc69d82f7bdc11c0840a35'
SOURCE215 = '27704f4248b35285e71c23bdf54d12cfe15a988bf8c17eab070f182aa7de1add'
SOURCE240 = '7c1f9050c9fffa0913388e0c628c1520266516ced0fb47c71bdf7a15acc249ec'
SOURCE248 = 'e60dd8493134a126e2f67b0c6933d3abae99267164cbf45b05571577843c0a48'
SOURCE249 = 'bd9eab32454109719ed2fca0d6db101d5db2a20b737bb6d73938971df8d50fea'
SOURCE251 = 'fea01758a0e16af9d699bd4a47ee5a07d60996176ae817a8e3912a0b0446f59e'
PROFILES = {SOURCE: (211, 18, 88, [2, 3, 4]),
            SOURCE214: (214, 23, 72, [3, 4]),
            SOURCE215: (215, 30, 88, [3]),
            SOURCE240: (240, 29, 83, [4]),
            SOURCE248: (248, 26, {4: 18}, [4]),
            SOURCE249: (249, 16, {2: 24, 3: 28, 4: 20}, [2, 3, 4]),
            SOURCE251: (251, 5, 88, [2, 3, 4])}


def _parse(data, skeleton, sid=211):
    mmd.exe().skeleton[sid] = skeleton
    mmd.exe().bone_count[sid] = len(skeleton)
    model = mmd.MMD.parse(data, len(skeleton))
    model.type = sid
    return model


def _forward(animation, distance, period):
    result = copy.deepcopy(animation)
    # The native loop resets all velocities at frame1. Its body/event order
    # stays exact; append our forward momentum to that existing first key.
    for instruction in result.instrs:
        if instruction['op'] == 'key':
            for group in instruction['bones']:
                if group['bone'] == 0:
                    group['vals'].pop('tz', None)
            instruction['bones'] = [g for g in instruction['bones'] if g['vals']]
    first = next(i for i in result.instrs if i['op'] == 'key' and i['frame'] == 1)
    first['bones'].append(dict(bone=0, div=period, vals={'tz': distance}))
    return result


def build(data, skeleton):
    digest = hashlib.sha256(data).hexdigest()
    if digest not in PROFILES:
        raise ValueError('Steady glide requires an individually reviewed pinned source')
    sid, n, expected_period, slots = PROFILES[digest]
    if len(skeleton) != n:
        raise ValueError('Reviewed glide skeleton has the wrong bone count')
    old = _parse(data, skeleton, sid)
    new = copy.deepcopy(old)
    reports = []
    for slot in slots:
        frames, loop, events = animsheet.slot_frames(old, n, slot)
        period = len(frames) - 1
        expected = expected_period[slot] if isinstance(expected_period, dict) else expected_period
        assert period == expected and loop == 0
        # Keep native lateral wobble; only the forward momentum changes.
        assert all(p[0][:6] == [4096]*3 + [0]*3 and p[0][7] == 0 for p in frames)
        distance = round(frames[-1][0][8] - frames[0][0][8])
        original = old.anims.anims[old.anims.table[slot]]
        assert original.frame_count == period + 1
        assert [i for i in original.instrs if i['op'] == 'loop_end'] == [dict(op='loop_end', frame=period+1, jump=1)]
        authored = _forward(original, distance, period)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
        before = mmd.AnimPlayer(original, n, slot)
        after = mmd.AnimPlayer(authored, n, slot)
        old_steps, new_steps = [], []
        for tick in range(period*9+1):
            assert before.tick() and after.tick()
            assert before.pose == after.pose, (slot, tick)
            assert before.base[:2] == after.base[:2]
            old_steps.append(before.base[2])
            new_steps.append(after.base[2])
        assert before.events == after.events
        assert abs(before.root[2] - after.root[2]) < 1e-9
        steady = new_steps[1:]
        assert max(steady) - min(steady) <= 1
        nets = [sum(new_steps[1+i*period:1+(i+1)*period]) for i in range(9)]
        assert nets == [distance]*9
        decoded, actual_loop, actual_events = animsheet.slot_frames(new, n, slot)
        assert len(decoded) == len(frames) and actual_loop == loop and actual_events == events
        assert [p[1:] for p in decoded] == [p[1:] for p in frames]
        reports.append(dict(slot=slot, period=period, net_travel=distance,
                            original_step_range=[min(old_steps[1:]), max(old_steps[1:])],
                            selected_step_range=[min(steady), max(steady)],
                            native_all_pose_channels_exact_nine_cycles=True,
                            every_loop_travel_exact=nets, events_exact=True))
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = _parse(result, skeleton, sid)
    assert changed_programs(old, actual) == slots
    assert old.tmd.build() == actual.tmd.build()
    storage = motionstorage.audit(result, n)
    assert storage['fits'], storage
    return result, dict(species=sid, source_sha256=digest,
                        output_sha256=hashlib.sha256(result).hexdigest(), changed_slots=slots,
                        changed_channels=[[0, 'tz']], mesh_skeleton_exact=True,
                        idle_native33_care_battle_exact=True, checks=reports, storage=storage)
