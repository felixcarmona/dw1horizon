"""Candlemon's supported pedestal landings and smooth airborne travel.

Retain every original upper-body/flame channel, root controller, sound and
clock. Only the pedestal's pitch and Y/Z carrier change: the base holds its
footprint at landing, then carries the unchanged performance to the next.
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
from motiondiscidentity import changed_programs

SOURCE = '1d1a0b35c46d2c264611331be412b3d881925bd32a99154bec3cba1c55565c05'
PARENTS = [-1, 9, 1, 1, 3, 4, 1, 6, 7, 10, 11, 0]
CHANNELS = {(11, 3), (11, 7), (11, 8)}


def _author(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    vertices = np.array(old.tmd.obj_verts(sk[11][0]))[:, :3]
    rows = []
    for slot in [2, 3, 4]:
        frames, loop, events = animsheet.slot_frames(old, n, slot)
        duration = len(frames) - 1
        period = 21 if slot == 3 else 17
        landing = 5 if slot == 3 else 7
        contact = {2: 4, 3: 5, 4: 3}[slot]
        height = {2: 30, 3: 12, 4: 42}[slot]
        net = frames[-1][0][8] - frames[0][0][8]
        hop_net = net / (duration / period)
        assert duration % period == 0 and hop_net == round(hop_net)

        def root_at(t):
            cycle = math.floor(t / duration)
            phase = t - cycle * duration
            index = min(duration - 1, int(phase))
            fraction = phase - index
            return (cycle * net + frames[index][0][8] * (1 - fraction)
                    + frames[index + 1][0][8] * fraction)

        authored, plan = [], []
        for t, source in enumerate(frames):
            pose = copy.deepcopy(source)
            phase = (t - landing) % period
            start = t - phase
            anchor = root_at(start + contact / 2)
            if phase <= contact:
                world_z, up, angle = anchor, 0, 0
            else:
                u = (phase - contact) / (period - contact)
                smooth = 6 * u ** 5 - 15 * u ** 4 + 10 * u ** 3
                world_z = anchor + hop_net * smooth
                up = height * (4 * u * (1 - u)) ** 2
                angle = .75 * source[11][3] * math.sin(math.pi * u) ** 2
            pose[11][3] = round(angle)
            rotation = np.array(mmd.rot_matrix(*pose[11][3:6]))
            bottom = float((vertices @ rotation.T)[:, 1].max())
            pose[11][7] = round(-5 - up - bottom)
            pose[11][8] = round(world_z - source[0][8])
            authored.append(pose)
            plan.append(dict(t=t, phase=phase, hop_start=start,
                             stance=phase <= contact, world_anchor_z=anchor,
                             planned_world_base_z=world_z, clearance=5 + up,
                             pitch_degrees=pose[11][3] * 360 / 4096))
        authored[-1][11] = copy.deepcopy(authored[0][11])
        original = old.anims.anims[old.anims.table[slot]]
        animation = replace_channels(original, authored, loop, n, CHANNELS)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(animation)
        rows.append(dict(slot=slot, duration=duration, hop_period=period,
                         landing_tick=landing, contact=contact, height=height,
                         root_cycle_travel=net, per_hop_travel=hop_net, plan=plan))
    return new, rows


def build(data, sk):
    if (hashlib.sha256(data).hexdigest() != SOURCE
            or [b[1] for b in sk] != PARENTS
            or [b[0] for b in sk] != list(range(-1, 11))):
        raise ValueError('Candlemon requires its reviewed twelve-bone source')
    n = len(sk)
    mmd.exe().skeleton[235] = sk
    mmd.exe().bone_count[235] = n
    old = mmd.MMD.parse(data, n)
    old.type = 235
    new, solver = _author(old, sk)
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = mmd.MMD.parse(result, n)
    actual.type = 235
    assert changed_programs(old, actual) == [2, 3, 4]
    assert old.tmd.build() == actual.tmd.build()
    checks = []
    for row in solver:
        slot, duration = row['slot'], row['duration']
        source = old.anims.anims[old.anims.table[slot]]
        selected = actual.anims.anims[actual.anims.table[slot]]
        assert [i for i in source.instrs if i['op'] != 'key'] == [i for i in selected.instrs if i['op'] != 'key']
        before, after = mmd.AnimPlayer(source, n, slot), mmd.AnimPlayer(selected, n, slot)
        cycle = []
        for t in range(duration * 9 + 1):
            assert before.tick() and after.tick()
            assert before.base == after.base and before.root == after.root
            for bone in range(n):
                for channel in range(9):
                    if (bone, channel) not in CHANNELS:
                        assert before.pose[bone][channel] == after.pose[bone][channel], (slot, t, bone, channel)
            if t < duration:
                cycle.append(copy.deepcopy(after.pose))
            else:
                assert after.pose == cycle[t % duration], (slot, t, 'drift')
        assert before.events == after.events
        checks.append(dict(slot=slot,
                           all_original_roots_velocities_events_controls_and_upper_local_SRT_exact_nine_cycles=True,
                           all_scales_and_joint_translations_except_base11YZ_exact=True))
    storage = motionstorage.audit(result, n)
    assert storage['fits'], storage
    return result, dict(species=235, source_sha256=SOURCE,
                        output_sha256=hashlib.sha256(result).hexdigest(),
                        changed_slots=[2, 3, 4], channels=[[11, 'rx'], [11, 'ty'], [11, 'tz']],
                        checks=checks, solver=solver, storage=storage,
                        mesh_idles_native33_care_battle_exact=True)
