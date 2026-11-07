#!/usr/bin/env python3
"""Bake one uniform size into a model's mesh and every animation translation.

Authoring tool: resize.py MODEL TYPE FACTOR OUT. Store the result with edit.py
put; bake any field overlay first so a later generator cannot restore the old size.
"""
import argparse
import copy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import mmd
import sizes


def resize(data, bones, factor):
    if not 0 < factor <= 4:
        raise ValueError('factor must be positive and at most four')
    model = mmd.MMD.parse(data, bones)
    before = copy.deepcopy(model)
    # sizes.rescale clamps overflowing fields; authored results must refuse them.
    coordinates = [c for v in model.tmd.verts for c in v[:3]]
    for anim in model.anims.anims:
        start = 6 if anim.has_scale else 3
        coordinates += [c for v in anim.pose for c in v[start:start + 3]]
    if any(not -32768 <= round(c * factor) <= 32767 for c in coordinates):
        raise ValueError('scaled vertex or pose exceeds signed 16-bit storage')
    if sizes.rescale(model, factor):
        raise ValueError('scaled animation momentum exceeds signed 16-bit storage')
    assert model.anims.table == before.anims.table
    for old, new in zip(before.anims.anims, model.anims.anims):
        start = 6 if old.has_scale else 3
        for a, b in zip(old.pose, new.pose):
            assert a[:start] == b[:start]
            assert b[start:start + 3] == [round(c * factor) for c in a[start:start + 3]]
        expected = copy.deepcopy(old.instrs)
        for ins in expected:
            if ins['op'] == 'key':
                for block in ins['bones']:
                    for channel in ('tx', 'ty', 'tz'):
                        if channel in block['vals']:
                            block['vals'][channel] = round(block['vals'][channel] * factor)
        assert new.instrs == expected
    result = model.build()
    assert len(result) == len(data)
    return result


def resize_with_pace(data, skeleton, sid, factor):
    """Resize all clips and retime field cycles to retain their follow pace."""
    import animsheet
    import motioncyclelayer
    import motionstorage
    from tools.models.field_animations.pace import _root_channels, _retimed_events
    mmd.exe().add_type(sid, skeleton)
    nb = len(skeleton)
    model = mmd.MMD.parse(resize(data, nb, factor), nb)
    model.type = sid
    for slot in (2, 3, 4):
        frames, loop, events = animsheet.slot_frames(model, nb, slot)
        if loop != 0:
            raise ValueError('paced resizing requires a complete repeating field cycle')
        ticks = max(2, round((len(frames)-1)*factor))
        speed = -(frames[-1][0][8]-frames[0][0][8])/ticks
        samples = _root_channels(frames, ticks, speed)
        mmd.close_loop(samples, 0)
        animation = mmd.encode_anim(samples, nb, 0, _retimed_events(events, len(frames)-1, ticks), tol=1, repeats=False)
        model.anims.table[slot] = len(model.anims.anims)
        model.anims.anims.append(animation)
    for animation in model.anims.anims: animation.tail = b''
    model.anims.anims, model.anims.table = motioncyclelayer.share_identical_streams(model.anims.anims, model.anims.table)
    output = model.build()
    motionstorage.require(output, nb)
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('model', type=Path)
    p.add_argument('type', type=int)
    p.add_argument('factor', type=float)
    p.add_argument('out', type=Path)
    a = p.parse_args()
    a.out.write_bytes(resize(a.model.read_bytes(), mmd.exe().bone_count[a.type], a.factor))


if __name__ == '__main__':
    main()
