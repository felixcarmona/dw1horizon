"""Carry the existing ordinary strike across to Omnimon's sword arm.

Keep anticipation, torso, legs, cape, contact timing and all events. Mirror the
cannon shoulder/elbow's relative motion onto the sword shoulder/elbow, while
the cannon retains its ready pose. Texture and equipment meshes stay intact.
"""
import copy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet
import mmd
import motioncyclelayer
import motionstorage
import retarget as rt
from motiondiscidentity import changed_programs
from tools.models.field_animations.articulation import replace_channels

SLOTS = (46, 51)


def repair(data, skeleton):
    nb = len(skeleton)
    mmd.exe().add_type(461, skeleton)
    old = mmd.MMD.parse(data, nb)
    old.type = 461
    result = copy.deepcopy(old)
    channels = {(b, c) for b in (3, 4, 9, 10) for c in (3, 4, 5)}
    mirror = [[-1, 0, 0], [0, 1, 0], [0, 0, 1]]
    for slot in SLOTS:
        frames, loop, _ = animsheet.slot_frames(old, nb, slot)
        poses = copy.deepcopy(frames)
        previous = {}
        for p, source in zip(poses, frames):
            for cannon, sword in ((9, 3), (10, 4)):
                delta = rt.m3mul(rt.rot_of(source[cannon]), rt.m3t(rt.rot_of(frames[0][cannon])))
                rotation = rt.m3mul(rt.m3mul(rt.m3mul(mirror, delta), mirror), rt.rot_of(frames[0][sword]))
                euler = mmd.matrix_euler(rotation, previous.get(sword))
                previous[sword] = euler
                p[sword][3:6] = [round(v) for v in euler]
                p[cannon][3:6] = frames[0][cannon][3:6]
        anim = replace_channels(old.anims.anims[old.anims.table[slot]], poses, loop, nb, channels, tolerance=1)
        result.anims.table[slot] = len(result.anims.anims)
        result.anims.anims.append(anim)
    for a in result.anims.anims:
        a.tail = b''
    result.anims.anims, result.anims.table = motioncyclelayer.share_identical_streams(result.anims.anims, result.anims.table)
    output = result.build()
    actual = mmd.MMD.parse(output, nb)
    actual.type = 461
    assert old.tmd.build() == actual.tmd.build()
    assert changed_programs(old, actual) == list(SLOTS)
    for slot in SLOTS:
        before, loop, events = animsheet.slot_frames(old, nb, slot)
        after, actual_loop, actual_events = animsheet.slot_frames(actual, nb, slot)
        assert len(before) == len(after) and loop == actual_loop and events == actual_events
        for a, b in zip(before, after):
            for bone in range(nb):
                for c in range(9):
                    if (bone, c) not in channels:
                        assert a[bone][c] == b[bone][c]
    motionstorage.require(output, nb)
    return output


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('out', type=Path)
    a = p.parse_args()
    a.out.write_bytes(repair(a.source.read_bytes(), mmd.exe().skeleton[461]))
