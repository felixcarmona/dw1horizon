#!/usr/bin/env python3
"""Author VenomMyotismon's long-arm run on its reviewed final field model.

Shoulders lead the swing; elbows and heavy gauntlets follow with separate phase
lags. The native chest, head, wings, feet, root travel and events are retained.
The field provider applies this pass after its supported-leg recipe.
"""
import argparse
import copy
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet
import mmd
import motioncyclelayer
import motionstorage
from motiondiscidentity import changed_programs
from tools.models.field_animations.articulation import replace_channels


def polish(data, skeleton):
    old = mmd.MMD.parse(data, len(skeleton))
    old.type = 212
    new = copy.deepcopy(old)
    frames, loop, events = animsheet.slot_frames(old, len(skeleton), 4)
    period = len(frames) - 1
    assert period == 20 and loop == 0
    poses = []
    channels = {(b, c) for b in (3, 4, 5, 6, 7, 8) for c in (3, 4, 5)}
    for tick, source in enumerate(frames):
        pose = copy.deepcopy(source)
        theta = 2 * math.pi * tick / period
        for shoulder, elbow, hand, side in [(3, 4, 5, 1), (6, 7, 8, -1)]:
            phase = theta + (0 if side == 1 else math.pi)
            # Continuous eased reversals, with the heavy hand trailing the elbow.
            angles = {
                shoulder: [25 + 22 * math.cos(phase), side * 8, -side * 35],
                elbow: [-65 + 13 * math.cos(phase - .6), 0, -side * 5],
                hand: [-15 + 9 * math.cos(phase - 1.0),
                       side * 4 * math.sin(phase - .8),
                       side * 5 * math.cos(phase - 1.2)],
            }
            for bone, degrees in angles.items():
                pose[bone][3:6] = [round(v * 4096 / 360) for v in degrees]
        poses.append(pose)
    poses[-1][1:] = copy.deepcopy(poses[0][1:])
    index = old.anims.table[4]
    assert old.anims.table.count(index) == 1
    new.anims.anims[index] = replace_channels(old.anims.anims[index], poses, loop, len(skeleton), channels)
    for anim in new.anims.anims:
        anim.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = mmd.MMD.parse(result, len(skeleton))
    assert changed_programs(old, actual) == [4]
    assert old.tmd.build() == actual.tmd.build()
    before = mmd.AnimPlayer(old.anims.anims[index], len(skeleton), 4)
    after = mmd.AnimPlayer(actual.anims.anims[actual.anims.table[4]], len(skeleton), 4)
    for tick in range(period * 4):
        assert before.tick() and after.tick()
        assert before.base == after.base
        for bone in range(len(skeleton)):
            for channel in range(9):
                if (bone, channel) not in channels:
                    assert before.pose[bone][channel] == after.pose[bone][channel]
    motionstorage.require(result, len(skeleton))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('model', type=Path)
    p.add_argument('out', type=Path)
    a = p.parse_args()
    a.out.write_bytes(polish(a.model.read_bytes(), mmd.exe().skeleton[212]))


if __name__ == '__main__':
    main()
