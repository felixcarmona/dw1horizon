"""Piedmon's native floating boots without the amplified advancing-leg swing.

The 104-tick native gesture already has expressive hands and trailing ribbons.
Keep that acting and the original travel speed; restore only the six leg
rotations from its matching native floating cycle. No ground gait is imposed.
"""
import copy
import hashlib

import animsheet
import mmd
import motioncyclelayer
import motionstorage
from tools.models.field_animations.channels import coalesce, replace_channels
from motiondiscidentity import changed_programs

SOURCE = 'e18c13a71d9c83ea4e5bdd10795eb22836c33166df5cf6b5145cd80d222ea869'
OUTPUT = '9f996ef648965a5f1fc0966de0af86c0cfd03c14ab407e258e80a372ce182e98'
PARENTS = [-1, 0, 1, 2, 2, 4, 5, 6, 2, 8, 9, 10, 2, 12,
           13, 2, 15, 16, 2, 18, 1, 20, 21, 1, 23, 24, 1, 1]
CHANNELS = {(bone, channel) for bone in range(20, 26) for channel in (3, 4, 5)}


def _parse(data, skeleton):
    mmd.exe().skeleton[245] = skeleton
    mmd.exe().bone_count[245] = len(skeleton)
    model = mmd.MMD.parse(data, len(skeleton))
    model.type = 245
    return model


def _verify(old, new):
    assert changed_programs(old, new) == [2, 3, 4]
    assert old.tmd.build() == new.tmd.build()
    assert len(old.anims.table) == len(new.anims.table)
    for slot, index in enumerate(old.anims.table):
        if slot in (2, 3, 4):
            continue
        if index is None:
            assert new.anims.table[slot] is None
            continue
        before = copy.deepcopy(old.anims.anims[index])
        after = copy.deepcopy(new.anims.anims[new.anims.table[slot]])
        before.tail = after.tail = b''
        assert before.build() == after.build(), ('protected stream', slot)
    checks = []
    for slot in (2, 3, 4):
        source = old.anims.anims[old.anims.table[slot]]
        target = new.anims.anims[new.anims.table[slot]]
        assert [i for i in source.instrs if i['op'] != 'key'] == [
            i for i in target.instrs if i['op'] != 'key']
        before = mmd.AnimPlayer(source, 28, slot)
        after = mmd.AnimPlayer(target, 28, slot)
        native = mmd.AnimPlayer(old.anims.anims[old.anims.table[33]], 28, 33)
        for tick in range(104 * 9 + 1):
            assert before.tick() and after.tick() and native.tick()
            assert before.base == after.base and before.root == after.root
            for bone in range(28):
                for channel in range(9):
                    if (bone, channel) not in CHANNELS:
                        assert before.pose[bone][channel] == after.pose[bone][channel], (
                            slot, tick, bone, channel)
            assert after.pose[1] == native.pose[1]
            for bone in range(20, 26):
                assert after.pose[bone] == native.pose[bone]
        checks.append(dict(slot=slot, period=104, cycles=9,
                           root_pose_momentum_and_accumulation_exact=True,
                           all_other_local_SRT_exact=True,
                           legs_and_parent_pelvis_exact_to_native33=True,
                           sounds_events_and_nonkey_controls_exact=True))
    return checks


def build(data, skeleton):
    if (hashlib.sha256(data).hexdigest() != SOURCE or len(skeleton) != 28
            or [b[1] for b in skeleton] != PARENTS
            or [b[0] for b in skeleton] != list(range(-1, 27))):
        raise ValueError('Piedmon requires its reviewed 28-bone floating source')
    old = _parse(data, skeleton)
    new = copy.deepcopy(old)
    native, loop, _ = animsheet.slot_frames(old, 28, 33)
    assert loop == 0 and len(native) == 105
    for slot in (2, 3, 4):
        poses, loop, _ = animsheet.slot_frames(old, 28, slot)
        assert loop == 0 and len(poses) == len(native)
        for pose, reference in zip(poses, native):
            for bone in range(20, 26):
                pose[bone][3:6] = reference[bone][3:6].copy()
        animation = replace_channels(old.anims.anims[old.anims.table[slot]],
                                     poses, loop, 28, CHANNELS, tolerance=0)
        animation, _ = coalesce(animation)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(animation)
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(
        new.anims.anims, new.anims.table)
    result = new.build()
    assert hashlib.sha256(result).hexdigest() == OUTPUT
    checks = _verify(old, _parse(result, skeleton))
    storage = motionstorage.audit(result, 28)
    assert storage['fits'], storage
    return result, dict(species=245, source_sha256=SOURCE, output_sha256=OUTPUT,
                        changed_slots=[2, 3, 4], checks=checks, storage=storage,
                        mesh_private33_idles_care_battle_streams_exact=True,
                        engine_dependency=None,
                        reference_validation_limits='Full-mesh reference geometry and actual-game playback are checked separately. Native levitation retained; no ground-support, all-terrain, turn, transition or continuous-sweep guarantee.')
