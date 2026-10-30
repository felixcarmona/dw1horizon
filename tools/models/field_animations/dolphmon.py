"""Restore Dolphmon's native swimming clock and a quieter exhausted float.

The primary field retarget squeezed a 72-tick performance into 20 ticks and
froze the idle body pitch. Preserve native articulation at its own pace,
carry the complete fish above ground, and retain average navigation speed.
"""
import copy
import hashlib
import mmd
import animsheet
import motioncyclelayer
import motionstorage
from tools.models.field_animations.gliding import _forward
from motiondiscidentity import changed_programs

SOURCE = '3905f16c9ccc1c08d373884671ea430e1191e0df6acb35093c9548b61d670396'
PARENTS = [-1, 0, 1, 2, 1, 1, 1, 6, 7, 8, 9]
LIFT = 36
PERIOD = 72


def _poor(frames):
    poses = []
    for source in frames:
        pose = copy.deepcopy(source)
        for bone in range(1, 11):
            pose[bone][3:6] = [round(a + .45 * (v - a)) for a, v in
                               zip(frames[0][bone][3:6], pose[bone][3:6])]
        pose[1][3] += round(2 * 4096 / 360)
        pose[2][3] += round(3 * 4096 / 360)
        pose[3][3] = round(frames[0][3][3] * .6
                           + (source[3][3] - frames[0][3][3]) * .3)
        pose[1][7] = round(frames[0][1][7]
                           + .45 * (source[1][7] - frames[0][1][7]) - LIFT)
        poses.append(pose)
    poses[-1][1:] = copy.deepcopy(poses[0][1:])
    return poses


def _lateral(animation, original, old_period):
    """Retain each closed swimming weave at its normalized native-gesture phase."""
    result = copy.deepcopy(animation)
    cues = []
    for instruction in original.instrs:
        if instruction['op'] != 'key':
            continue
        for group in instruction['bones']:
            if group['bone'] != 0 or 'tx' not in group['vals']:
                continue
            start = instruction['frame'] - 1
            mapped = round(start * PERIOD / old_period)
            end = round((start + group['div']) * PERIOD / old_period)
            cue = dict(bone=0, div=end - mapped, vals={'tx': group['vals']['tx']})
            key = next((i for i in result.instrs if i['op'] == 'key' and i['frame'] == mapped + 1), None)
            if key is not None:
                key['bones'].append(cue)
            else:
                key = dict(op='key', frame=mapped + 1, bones=[cue])
                at = next((j for j, i in enumerate(result.instrs) if i.get('frame', -1) > mapped + 1), len(result.instrs) - 1)
                result.instrs.insert(at, key)
            cues.append(dict(source_tick=start, target_tick=mapped, duration=end - mapped, delta=group['vals']['tx']))
    return result, cues


def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE or [b[1] for b in sk] != PARENTS:
        raise ValueError('Dolphmon requires its reviewed eleven-bone source')
    n = len(sk)
    mmd.exe().skeleton[238] = sk
    mmd.exe().bone_count[238] = n
    old = mmd.MMD.parse(data, n)
    old.type = 238
    new = copy.deepcopy(old)
    native = old.anims.anims[old.anims.table[33]]
    frames, loop, events = animsheet.slot_frames(old, n, 33)
    assert len(frames) == PERIOD + 1 and loop == 0 and not events
    poor = _poor(frames)
    reports = []
    for slot in range(5):
        before, _, events = animsheet.slot_frames(old, n, slot)
        duration = len(before) - 1
        assert duration == 20
        assert all(f[0][:6] == [4096] * 3 + [0] * 3 and f[0][7] == 0 for f in before)
        assert before[-1][0][6] == before[0][0][6] == 0
        net = before[-1][0][8] - before[0][0][8]
        distance = round(net * PERIOD / duration)
        selected = copy.deepcopy(native)
        if slot == 1:
            selected = mmd.encode_anim(poor, n, loop_sample=0, tol=1, repeats=False)
        else:
            # A constant ancestor offset retains every native relative pose.
            selected.pose[0][7 if selected.has_scale else 4] -= LIFT
        if slot > 1:
            selected = _forward(selected, distance, PERIOD)
        selected, lateral = _lateral(selected, old.anims.anims[old.anims.table[slot]], duration)
        sounds = []
        for _, kind, cue in events:
            assert kind == 'sound'
            mapped = dict(cue, frame=1 + round((cue['frame'] - 1) * PERIOD / duration))
            at = next((j for j, i in enumerate(selected.instrs)
                       if i.get('frame', -1) > mapped['frame']), len(selected.instrs) - 1)
            selected.instrs.insert(at, mapped)
            sounds.append(mapped)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(selected)
        reports.append(dict(slot=slot, period=PERIOD, lift=LIFT,
                            source_period=duration, source_net_travel=net,
                            net_travel=distance, speed=distance / PERIOD,
                            source_speed=net / duration, sounds=sounds, lateral=lateral, lateral_bounds=[min(f[0][6] for f in before), max(f[0][6] for f in before)]))
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(
        new.anims.anims, new.anims.table)
    result = new.build()
    actual = mmd.MMD.parse(result, n)
    actual.type = 238
    assert changed_programs(old, actual) == [0, 1, 2, 3, 4]
    assert old.tmd.build() == actual.tmd.build()
    checks = []
    for row in reports:
        slot, distance = row['slot'], row['net_travel']
        source = mmd.AnimPlayer(native, n, 33)
        player = mmd.AnimPlayer(actual.anims.anims[actual.anims.table[slot]], n, slot)
        cycle, steps, lateral_cycle = [], [], []
        maximum_poor_error = 0
        for t in range(PERIOD * 9 + 1):
            assert source.tick() and player.tick()
            for bone in range(1, n):
                for c in range(9):
                    reference = poor[t % PERIOD][bone][c] if slot == 1 else source.pose[bone][c] - (LIFT if (bone, c) == (1, 7) else 0)
                    error = abs(player.pose[bone][c] - reference)
                    if slot == 1 and (c in [3, 4, 5] or (bone, c) == (1, 7)):
                        maximum_poor_error = max(maximum_poor_error, error)
                        assert error <= 1, (slot, t, bone, c, error)
                    else:
                        assert error == 0, (slot, t, bone, c, error)
            assert player.root[1] == 0
            assert row["lateral_bounds"][0] <= player.root[0] <= row["lateral_bounds"][1]
            if t < PERIOD:
                cycle.append(copy.deepcopy(player.pose[1:]))
                lateral_cycle.append(player.root[0])
            else:
                assert player.pose[1:] == cycle[t % PERIOD], (slot, t, 'cycle drift')
                assert player.root[0] == lateral_cycle[t % PERIOD], (slot, t, 'lateral drift')
            steps.append(player.base[2])
        assert player.root[0] == 0
        before = animsheet.slot_frames(old, n, slot)[0]
        for cue in row['lateral']:
            assert lateral_cycle[cue['target_tick']] == before[cue['source_tick']][0][6]
        assert player.root[2] == distance * 9
        assert [sum(steps[1 + i * PERIOD:1 + (i + 1) * PERIOD]) for i in range(9)] == [distance] * 9
        assert max(steps[1:]) - min(steps[1:]) <= 1
        encoded = actual.anims.anims[actual.anims.table[slot]]
        assert [i for i in encoded.instrs if i['op'] == 'sound'] == row['sounds']
        if slot != 1:
            assert [i for i in encoded.instrs if i['op'] not in ['key', 'sound']] == [i for i in native.instrs if i['op'] not in ['key', 'sound']]
        checks.append(dict(slot=slot, nine_cycles_repeat_exact=True,
                           full_native_SRT_exact_except_body1TY_lift=slot != 1,
                           maximum_poor_profile_encoding_error=maximum_poor_error,
                           native_scales_and_joint_translations_except_body1TY_exact=True,
                           nine_loop_travel_exact=True, maximum_root_integer_step_variation=1,
                           source_sounds_at_original_normalized_phase=True, closed_lateral_weave_knots_and_amplitude_preserved=True))
    storage = motionstorage.audit(result, n)
    assert storage['fits'], storage
    return result, dict(species=238, source_sha256=SOURCE,
                        output_sha256=hashlib.sha256(result).hexdigest(),
                        changed_slots=[0, 1, 2, 3, 4], mesh_care_battle_private33_exact=True,
                        native_period=PERIOD, lift=LIFT, checks=checks, solver=reports,
                        storage=storage)
