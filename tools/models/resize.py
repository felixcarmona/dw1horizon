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
