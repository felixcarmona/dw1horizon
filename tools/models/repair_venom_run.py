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


# The native walk holds both gauntlets out in front of the body like a boxer's;
# only the run keeps that. Walking, the arms hang from the shoulders, the
# forearms bent a little forward, swinging against the legs: each shoulder keeps
# the native swing timing and a smaller range, the elbow bends further as the
# arm comes forward a tick later, and the heavy hand trails the elbow.
WALK_ARMS = {
    2: dict(shoulder=(36, 11), elbow=(-50, 8), hand=(-68, 5), elbow_lag=1.5, hand_lag=2.5, timing='shoulder'),
    3: dict(shoulder=(22, 4), elbow=(-46, 4), hand=(-62, 3), elbow_lag=2.0, hand_lag=3.0, timing='thigh'),
}


def _cyclic(values, t):
    """Linear interpolation of a closed cycle (values[-1] == values[0])."""
    n = len(values) - 1
    t %= n
    i = int(t)
    q = t - i
    return values[i] * (1 - q) + values[i + 1] * q


def polish_walk_arms(data, skeleton):
    """Let the arms hang and swing in the walk (slot 2) and the tired walk (slot 3)."""
    old = mmd.MMD.parse(data, len(skeleton))
    old.type = 212
    new = copy.deepcopy(old)
    n = len(skeleton)
    channels = {(b, c) for b in (3, 4, 5, 6, 7, 8) for c in (3, 4, 5)}
    changed = []
    for slot, cfg in WALK_ARMS.items():
        frames, loop, events = animsheet.slot_frames(old, n, slot)
        period = len(frames) - 1
        assert loop == 0
        poses = [copy.deepcopy(f) for f in frames]
        for shoulder, elbow, hand, thigh in [(3, 4, 5, 21), (6, 7, 8, 24)]:
            # back = +1 .. forward = -1: the native shoulder swing, or (the tired
            # walk's shoulders hardly move) the same side's thigh swing, which
            # the native walk's arms follow
            if cfg['timing'] == 'shoulder':
                native = [f[shoulder][3] * 360 / 4096 for f in frames]
            else:
                native = [-f[thigh][3] * 360 / 4096 for f in frames]
            low, high = min(native), max(native)
            swing = [2 * (v - low) / (high - low) - 1 for v in native]
            for t, pose in enumerate(poses):
                back = swing[t % period]
                ahead = -_cyclic(swing, t - cfg['elbow_lag'])
                ahead_hand = -_cyclic(swing, t - cfg['hand_lag'])
                pose[shoulder][3] = round((cfg["shoulder"][0] + cfg["shoulder"][1] * back) * 4096 / 360)
                pose[elbow][3] = round((cfg['elbow'][0] - cfg['elbow'][1] * ahead) * 4096 / 360)
                pose[hand][3] = round((cfg['hand'][0] - cfg['hand'][1] * ahead_hand) * 4096 / 360)
        poses[-1][1:] = copy.deepcopy(poses[0][1:])
        index = old.anims.table[slot]
        assert old.anims.table.count(index) == 1
        new.anims.anims[index] = replace_channels(old.anims.anims[index], poses, loop, n, {(b, 3) for b in (3, 4, 5, 6, 7, 8)})
        changed.append(slot)
    for anim in new.anims.anims:
        anim.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = mmd.MMD.parse(result, n)
    assert changed_programs(old, actual) == changed
    assert old.tmd.build() == actual.tmd.build()
    for slot in changed:
        before = mmd.AnimPlayer(old.anims.anims[old.anims.table[slot]], n, slot)
        after = mmd.AnimPlayer(actual.anims.anims[actual.anims.table[slot]], n, slot)
        period = len(animsheet.slot_frames(old, n, slot)[0]) - 1
        for tick in range(period * 4):
            assert before.tick() and after.tick()
            assert before.base == after.base
            for bone in range(n):
                for channel in range(9):
                    if (bone, channel) not in {(b, 3) for b in (3, 4, 5, 6, 7, 8)}:
                        assert before.pose[bone][channel] == after.pose[bone][channel]
    motionstorage.require(result, n)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('model', type=Path)
    p.add_argument('out', type=Path)
    a = p.parse_args()
    a.out.write_bytes(polish(a.model.read_bytes(), mmd.exe().skeleton[212]))


if __name__ == '__main__':
    main()
