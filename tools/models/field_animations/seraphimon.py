#!/usr/bin/env python3
"""Seraphimon's battle victory kept on screen.

The idle, walk, condition walk and run come with the stored model (seraphimon_native.py: native Angemon's footfalls,
planted feet, calm wings). The victory (0x2A) is the card game's clip cut from a stretch where the angel already
hovers about 1450 units up, so in battle it left the screen from the first tick. Its carrier height is lowered by
that constant: it starts at the battle idle's height and rises about 300, as HolyAngemon's does.
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
SOURCE = 'c3aa5e2e317b6a22c0780f800311f592dbd158f15ae35e0df13eb7c75e4cd4b7'

def _pack(model):
    for anim in model.anims.anims:
        anim.tail = b''
    model.anims.anims, model.anims.table = motioncyclelayer.share_identical_streams(model.anims.anims, model.anims.table)
    return model.build()

def _parse(data, sk):
    mmd.exe().skeleton[207] = sk
    mmd.exe().bone_count[207] = len(sk)
    result = mmd.MMD.parse(data, len(sk))
    result.type = 207
    return result

VICTORY = 0x2A


def _mesh_low(model, sk, frame, vertices):
    pose = copy.deepcopy(frame)
    pose[0] = [4096]*3 + [0]*6
    world = np.array(mmd.bone_matrices(model, pose))
    return max(float((points @ world[bone, :3, :3].T + world[bone, :3, 3])[:, 1].max())
               for bone, points in vertices.items())


def _grounded_victory(old, sk):
    """The victory clip moved down by one constant on the carrier's height (bone 1, channel 7): its first tick at the
    battle idle's height. Every other channel, the timing and the sounds stay."""
    n = len(sk)
    new = copy.deepcopy(old)
    idle = animsheet.slot_frames(old, n, 0x21)[0][0][1][7]
    fs, loop, _ = animsheet.slot_frames(old, n, VICTORY)
    offset = idle - fs[0][1][7]
    assert 1300 < offset < 1600, offset
    poses = copy.deepcopy(fs)
    for f in poses:
        f[1][7] += offset
    new.anims.anims.append(replace_channels(old.anims.anims[old.anims.table[VICTORY]], poses, loop, n, {(1, 7)}))
    new.anims.table[VICTORY] = len(new.anims.anims) - 1
    return new, dict(slot=VICTORY, carrier_offset=offset)


def _verify_victory(original, actual, sk):
    """Only the carrier height of 0x2A moved, by one constant; the first tick touches the ground like the idle and the
    whole clip stays within 500 units of it (it used to start about 1450 up)."""
    before, _, before_events = animsheet.slot_frames(original, 31, VICTORY)
    after, _, after_events = animsheet.slot_frames(actual, 31, VICTORY)
    assert len(before) == len(after) == 54 and before_events == after_events
    offsets = set()
    for b, a in zip(before, after):
        for bone in range(31):
            for channel in range(9):
                if (bone, channel) == (1, 7):
                    offsets.add(a[1][7] - b[1][7])
                else:
                    assert a[bone][channel] == b[bone][channel], (bone, channel)
    assert len(offsets) == 1, offsets
    vertices = {b: np.array(actual.tmd.obj_verts(obj))[:, :3] for b, (obj, _) in enumerate(sk) if obj >= 0}
    idle_low = _mesh_low(actual, sk, animsheet.slot_frames(actual, 31, 0x21)[0][0], vertices)
    lows = [_mesh_low(actual, sk, f, vertices) for f in after]
    rise = max(idle_low - y for y in lows)
    assert abs(lows[0] - idle_low) < 40 and rise < 500, (idle_low, lows[0], rise)
    return dict(slot=VICTORY, carrier_offset=offsets.pop(), first_tick_vs_idle_low=lows[0] - idle_low,
                max_rise_over_idle=rise)


def _verify(original, actual, sk):
    assert changed_programs(original, actual) == [VICTORY]
    assert original.tmd.build() == actual.tmd.build()


def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE or len(sk) != 31:
        raise ValueError('Seraphimon recipe requires the pinned reviewed source')
    original = _parse(data, sk)
    victory, victory_change = _grounded_victory(original, sk)
    result = _pack(victory)
    actual = _parse(result, sk)
    _verify(original, actual, sk)
    victory_check = dict(victory_change, **_verify_victory(original, actual, sk))
    storage = motionstorage.audit(result, 31)
    assert storage['fits'], storage
    return result, dict(species=207, source_sha256=SOURCE, output_sha256=hashlib.sha256(result).hexdigest(),
                        changed_slots=[VICTORY], battle_exact_but_victory_height=True, victory_check=victory_check,
                        storage=storage)
