"""Salamon's repaired idle and Garurumon-based canine locomotion.

Transfer the native shoulder, hock, head and four-paw performances onto the
puppy's own rig. Retiming preserves native footstep placement and paw sounds.
The collar stays rigid. A native scolding gesture replaces the imported bow
that buried the face; the mesh and remaining care and battle programs stay intact.
"""
import copy
import hashlib
import math

import animsheet
import mmd
import motioncyclelayer
import motionstorage
from motiondiscidentity import changed_programs
from motiontailspace import interpolate_pose
from tools.models.field_animations.articulation import replace_channels
from tools.models.field_animations import native_polish

SOURCE = '29faa5a38d25bdfc7610aef3d840c6211f3df72568a6284ff9c3ae47e6cabb8e'
DONOR = 'aa30bb3d1994d1c889c660bbd577b8b29971192676d39f4b111a8cdbfa82159f'


def _parse(data, skeleton):
    mmd.exe().add_type(221, skeleton)
    model = mmd.MMD.parse(data, len(skeleton))
    model.type = 221
    return model


def _idle(old, skeleton):
    """Keep the reviewed complete idle and its floor correction unchanged."""
    frames, loop, _ = animsheet.slot_frames(old, len(skeleton), 33)
    poses = copy.deepcopy(frames)
    for pose in poses:
        pose[0] = [4096] * 3 + [0] * 6
        matrices = mmd.bone_matrices(old, pose)
        bottom = max(sum(matrices[b][1][j] * v[j] for j in range(3)) + matrices[b][1][3]
                     for b, (obj, _) in enumerate(skeleton) if obj >= 0
                     for v in old.tmd.obj_verts(obj))
        pose[13][7] -= math.ceil(max(0, bottom + 2))
    poses[-1][1:] = copy.deepcopy(poses[0][1:])
    result = copy.deepcopy(old)
    template = old.anims.anims[old.anims.table[33]]
    result.anims.table[0] = len(result.anims.anims)
    result.anims.anims.append(replace_channels(template, poses, loop, len(skeleton), {(13, 7)}))
    for animation in result.anims.anims:
        animation.tail = b''
    result.anims.anims, result.anims.table = motioncyclelayer.share_identical_streams(result.anims.anims, result.anims.table)
    return result


def build(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE or len(skeleton) != 21:
        raise ValueError('Salamon requires the pinned 21-bone source')
    old = _parse(data, skeleton)
    idle = _idle(old, skeleton)
    cfg = dict(donor=22, model='extracted/CHDAT/MMD0/GARU.MMD', donor_sha256=DONOR,
               carrier=13, scale=.36, rest_slot=0,
               map={'13': 1, '1': 2, '2': 4, '3': 5, '5': 5},
               chains=[[7, 8, 7, 8], [8, 9, 8, 9], [10, 11, 11, 12], [11, 12, 12, 13],
                       [14, 15, 19, 20], [15, 16, 20, 21], [17, 18, 23, 24], [18, 19, 24, 25]],
               legs=[[7, 8, 9, 9, 9, 9], [10, 11, 12, 12, 13, 13],
                     [14, 15, 16, 16, 21, 21], [17, 18, 19, 19, 25, 25]],
               feet=[9, 12, 16, 19], secondary=[4, 6], contact_height=True, native_bend=True,
               vertical_motion=.3, foot_lift=.7,
               maximum_support_gap={'2': 2, '3': 2, '4': 2},
               retime={'2': {'ticks': 6, 'speed': 15}, '3': {'ticks': 10, 'speed': 10},
                       '4': {'ticks': 6, 'speed': 35}},
               rotation_weights={'13': .5, '1': .5, '2': .7, '3': .7, '5': .7})
    output, report = native_polish.author(idle.build(), skeleton, 221, cfg)
    scold = dict(cfg, slots=[12], ground_contact=True, maximum_support_gap={'12': 2})
    output, scold_report = native_polish.author(output, skeleton, 221, scold)
    report['scolding'] = scold_report
    actual = _parse(output, skeleton)
    # Retiming can land two native paw contacts on one logic tick. Play the
    # shared paw cue once rather than restarting it twice on that tick.
    for slot in (2, 3, 4):
        animation = actual.anims.anims[actual.anims.table[slot]]
        seen = set()
        instructions = []
        for instruction in animation.instrs:
            if instruction['op'] == 'sound':
                cue = (instruction['frame'], instruction['bank'], instruction['note'])
                if cue in seen:
                    continue
                seen.add(cue)
            instructions.append(instruction)
        animation.instrs = instructions
    output = actual.build()
    # The shorter puppy cadence creates new between-key poses. Clear each
    # paw after retiming, without lifting the whole body off its contacts.
    from tools.models.field_animations.animal_refine import clear_interpolated_paws, finish
    additions = []
    for slot in (2, 3, 4):
        frames, loop, events = animsheet.slot_frames(actual, len(skeleton), slot)
        frames = clear_interpolated_paws(actual, skeleton, frames,
                                        ((7, 8, 9), (10, 11, 12), (14, 15, 16), (17, 18, 19)))
        additions.append((slot, frames, loop, events))
    output = finish(actual, additions, len(skeleton))
    actual = _parse(output, skeleton)
    assert changed_programs(old, actual) == [0, 2, 3, 4, 12]
    assert old.tmd.build() == actual.tmd.build()
    for slot in (2, 3, 4):
        frames, _, _ = animsheet.slot_frames(actual, len(skeleton), slot)
        assert all(pose[20][3:6] == frames[0][20][3:6] for pose in frames)
        sounds = [i for i in actual.anims.anims[actual.anims.table[slot]].instrs if i['op'] == 'sound']
        assert sounds and all((i['bank'], i['note']) == (1, 12) for i in sounds)
        animation = actual.anims.anims[actual.anims.table[slot]]
        player = mmd.AnimPlayer(animation, len(skeleton), slot)
        duration = cfg['retime'][str(slot)]['ticks']
        cycle = []
        for tick in range(duration * 9 + 1):
            assert player.tick()
            if tick < duration:
                cycle.append(copy.deepcopy(player.pose))
            else:
                assert player.pose == cycle[tick % duration], (slot, tick, 'cyclic drift')
        assert player.root == [0, 0, -cfg['retime'][str(slot)]['speed'] * duration * 9]
    clearance = {}
    for slot in (2, 3, 4, 12):
        frames, _, _ = animsheet.slot_frames(actual, len(skeleton), slot)
        bottom = -1000
        for a, b in zip(frames, frames[1:]):
            for alpha in (0, 1365, 2730, 4096):
                pose = interpolate_pose(a, b, alpha)
                pose[0] = [4096] * 3 + [0] * 6
                matrices = mmd.bone_matrices(actual, pose)
                bottom = max(bottom, max(sum(matrices[bone][1][j] * v[j] for j in range(3)) + matrices[bone][1][3]
                                         for bone, (obj, _) in enumerate(skeleton) if obj >= 0
                                         for v in actual.tmd.obj_verts(obj)))
        assert bottom <= 1.5, (slot, 'interpolated floor', bottom)
        clearance[slot] = bottom
    report.update(species=221, source_sha256=SOURCE, donor=22, donor_sha256=DONOR,
                  output_sha256=hashlib.sha256(output).hexdigest(), changed_slots=[0, 2, 3, 4, 12],
                  mesh_skeleton_other_care_battle_exact=True, collar_rigid=True,
                  interpolated_floor_max=clearance, nine_cycles_stable=True,
                  storage=motionstorage.require(output, len(skeleton)))
    return output, report
