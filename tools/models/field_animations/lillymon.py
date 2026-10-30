#!/usr/bin/env python3
"""Open Lillymon's native flight arms without replacing her flying performance.

The game renders private33 plus its existing C limb additive. Primary0/2/3/4
are root controllers, so editing their frozen rotations would have no effect.
Only native shoulders6/9 change; all wing, body, leg and face motion remains.
"""
import copy
import hashlib
import numeric as np
import mmd
import animsheet
import motioncyclelayer
import motionstorage
from tools.models.field_animations.articulation import replace_channels
from motiondiscidentity import changed_programs
from tools.models.field_animations.war_greymon import rotation, set_rotation

SOURCE = '80085c00c157740c0c03c3899fff4010fda7c41d7e69d202df4a2f0e5005e177'
SHOULDERS = {6: [-14, 0, -10], 9: [-8, 0, 10]}


def _parse(data, sk):
    mmd.exe().skeleton[209] = sk
    mmd.exe().bone_count[209] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = 209
    return model


def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE or len(sk) != 23:
        raise ValueError('Lillymon recipe requires the pinned reviewed source')
    old = _parse(data, sk)
    new = copy.deepcopy(old)
    frames, loop, events = animsheet.slot_frames(old, 23, 33)
    assert loop == 0 and len(frames) == 65
    poses, history = [], {}
    for source in frames:
        frame = copy.deepcopy(source)
        frame[0] = [4096]*3 + [0]*6
        world = np.array(mmd.bone_matrices(old, frame))
        for shoulder, bias in SHOULDERS.items():
            desired = rotation(bias) @ world[shoulder, :3, :3]
            set_rotation(frame, shoulder, world[2, :3, :3].T @ desired, history)
        frame[0] = copy.deepcopy(source[0])
        poses.append(frame)
    channels = {(bone, channel) for bone in SHOULDERS for channel in [3, 4, 5]}
    original = old.anims.anims[old.anims.table[33]]
    authored = replace_channels(original, poses, loop, 23, channels)
    # Face texture operations, their timing, and every non-pose instruction
    # remain exact. The engine's existing guarded face cache still owns them.
    assert [i for i in authored.instrs if i['op'] != 'key'] == [i for i in original.instrs if i['op'] != 'key']
    new.anims.anims.append(authored)
    new.anims.table[33] = len(new.anims.anims)-1
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = _parse(result, sk)
    assert changed_programs(old, actual) == [33]
    assert old.tmd.build() == actual.tmd.build()
    decoded, actual_loop, actual_events = animsheet.slot_frames(actual, 23, 33)
    assert len(decoded) == 65 and actual_loop == loop and actual_events == events
    before = mmd.AnimPlayer(original, 23, 33)
    after = mmd.AnimPlayer(actual.anims.anims[actual.anims.table[33]], 23, 33)
    max_error = 0.
    for tick in range(64*8):
        assert before.tick() and after.tick()
        assert before.base == after.base
        for bone in range(23):
            for channel in range(9):
                if (bone, channel) not in channels:
                    assert before.pose[bone][channel] == after.pose[bone][channel], (tick, bone, channel)
        old_world = np.array(mmd.bone_matrices(old, before.pose))
        new_world = np.array(mmd.bone_matrices(actual, after.pose))
        for shoulder, bias in SHOULDERS.items():
            expected = rotation(bias) @ old_world[shoulder, :3, :3]
            max_error = max(max_error, float(np.max(abs(expected-new_world[shoulder, :3, :3]))))
    assert max_error < .005, max_error
    storage = motionstorage.audit(result, 23)
    assert storage['fits'], storage
    return result, dict(species=209, source_sha256=SOURCE,
                        output_sha256=hashlib.sha256(result).hexdigest(), changed_slots=[33],
                        primary_root_controllers_idle_care_battle_mesh_skeleton_exact=True,
                        native_body_head_wings_legs_face_events_exact_eight_cycles=True,
                        existing_engine_additive_retained=True,
                        shoulder_world_bias_degrees=SHOULDERS,
                        max_decoded_world_rotation_matrix_error=max_error,
                        native_period_ticks=64, storage=storage)
