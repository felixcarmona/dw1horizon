"""Candlemon's hovering walk, condition walk and run.

Retain every original upper-body/flame channel, root controller, sound and
clock. Only the pedestal's pitch and Y/Z carrier change: it floats clear of the
ground on a steady forward line, bobbing and swaying gently, like Bakemon.
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

SOURCE = 'db473f38e2e667564c00677b526725895aa13e528f2a72686bb06ea4cf5a3834'
PARENTS = [-1, 9, 1, 1, 3, 4, 1, 6, 7, 10, 11, 0]
CHANNELS = {(11, 3), (11, 7), (11, 8)}
HOVER = {2: 26, 3: 18, 4: 34}      # clearance under the pedestal, by slot
BOB = {2: 6, 3: 4, 4: 8}            # height of the bob
LEAN = {2: 60, 3: 20, 4: 130}       # steady forward lean, 1/4096 turn
SWAY = {2: 35, 3: 25, 4: 45}        # pitch sway with the bob


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

        # The candle floats: the pedestal rides a steady forward line (the loop's net travel, no stepping), bobs once
        # per old hop period and sways a little around a lean that grows with the speed.
        authored, plan = [], []
        rest_pitch = frames[0][11][3]
        for t, source in enumerate(frames):
            phase = 2 * math.pi * ((t - landing) % period) / period
            bob = math.sin(phase)
            clearance = HOVER[slot] + BOB[slot] * bob
            pose = copy.deepcopy(source)
            pose[11][3] = round(rest_pitch + LEAN[slot] + SWAY[slot] * math.cos(phase))
            rotation = np.array(mmd.rot_matrix(*pose[11][3:6]))
            bottom = float((vertices @ rotation.T)[:, 1].max())
            pose[11][7] = round(-clearance - bottom)
            world_z = net * t / duration
            pose[11][8] = round(world_z - root_at(t) + source[11][8])
            authored.append(pose)
            plan.append(dict(t=t, clearance=round(clearance, 1), world_base_z=round(world_z, 1),
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
