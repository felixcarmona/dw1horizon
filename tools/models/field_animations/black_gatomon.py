"""BlackGatomon's forward gaze and controlled heavy glove swing.

Use with the separately validated native-tail private engine adapter. The
visible grooming idle, tired action, feet, torso and root remain original.
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

SOURCE = '711f533c858a75fa638b74f11e0e525908a22d7b85f04507bc1ff68c74d1dfda'
PARENTS = [-1, 2, 0, 1, 1, 2, 5, 2, 7, 2, 9, 2, 11, 2, 13, 14, 15, 16, 17]


def build(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('BlackGatomon requires the reviewed source')
    if [b[1] for b in skeleton] != PARENTS:
        raise ValueError('BlackGatomon rig differs')
    n = len(skeleton)
    mmd.exe().skeleton[222] = skeleton
    mmd.exe().bone_count[222] = n
    old = mmd.MMD.parse(data, n)
    old.type = 222
    new = copy.deepcopy(old)
    channels = {(1, 3)} | {(b, c) for b in [5, 6, 7, 8] for c in [3, 4, 5]}
    checks = []
    for slot in [2, 4]:
        frames, loop, _ = animsheet.slot_frames(old, n, slot)
        period = len(frames) - 1
        assert loop == 0
        for bone in [5, 6, 7, 8]:
            values = np.array([f[bone][3:6] for f in frames])
            centre = (values.max(0) + values.min(0)) / 2
            factor = ({2: .7, 4: .6}[slot] if bone in [5, 7] else .5)
            for frame in frames:
                frame[bone][3:6] = [round(c + (v - c) * factor)
                                      for v, c in zip(frame[bone][3:6], centre)]
        for frame in frames:
            frame[1][3] += 256
            if slot == 2:
                frame[5][5] -= 128
                frame[7][5] += 128
        original = old.anims.anims[old.anims.table[slot]]
        animation = replace_channels(original, frames, loop, n, channels)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(animation)
        before = mmd.AnimPlayer(original, n, slot)
        after = mmd.AnimPlayer(animation, n, slot)
        for tick in range(period * 8):
            assert before.tick() and after.tick()
            assert before.base == after.base
            for bone in range(n):
                for channel in range(9):
                    if (bone, channel) not in channels:
                        assert before.pose[bone][channel] == after.pose[bone][channel], (slot, tick, bone, channel)
        checks.append(dict(slot=slot, period=period, eight_cycles_protected_channels_exact=True,
                           root_feet_body_scale_translation_and_original_events_preserved=True))
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    parsed = mmd.MMD.parse(result, n)
    assert changed_programs(old, parsed) == [2, 4]
    assert old.tmd.build() == parsed.tmd.build()
    storage = motionstorage.audit(result, n)
    assert storage['fits'], storage
    return result, dict(species=222, source_sha256=SOURCE,
                        output_sha256=hashlib.sha256(result).hexdigest(), changed_slots=[2, 4],
                        mesh_exact=True, other_programs_exact=True, checks=checks, storage=storage,
                        required_private_engine='blackgatomon222_native_appendages_private_engine_v1.py')
