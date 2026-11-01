"""Snimon: a mantis carriage over its paced gait, applied after the field pace pass.

The donor's clips hold the blades high and wave them without regard to the legs.
Walk, condition walk and run keep their legs and travel; the arms drop and swing
against the steps, the torso turns with them, and head, tail, wings and each arm
joint follow a little later. The condition walk and the run also lift the body
where their spikes crossed the floor. Mesh, skeleton and other clips stay exact.
"""
import copy
import math

import numeric as np
import animsheet
import mmd
import motioncyclelayer
import motionstorage
from motiondiscidentity import changed_programs
from tools.models.field_animations.articulation import replace_channels
from tools.models.field_animations.pace import _clear_floor, _floors
from tools.models.field_animations.war_greymon import rotation, set_rotation

SPECIES = 328
ARMS = [(27, 28, 29, 1), (24, 25, 26, -1)]      # shoulder, elbow, wrist, side (right +1)
ARM_BONES = [b for arm in ARMS for b in arm[:3]]
TORSO, HEAD, TAIL, WINGS, FOOT = 19, 20, 9, (2, 10), 8
TOLERANCE = 14          # units of 1/4096 turn: what lets the extra keys fit the partner buffer
FLOOR_MARGIN = 1.5
# keep: share of the donor's arm motion; low, lean, turn, sway, arm, tail, wing: degrees; head: share of the torso undone
SLOTS = {
    2: dict(keep=.3, low=14, lean=4, turn=6, sway=3, arm=9, tail=7, head=.8, wing=7, beat=1, lift=False),
    3: dict(keep=.3, low=22, lean=6, turn=4, sway=2, arm=6, tail=4, head=.6, wing=3, beat=1, lift=True),
    4: dict(keep=.3, low=20, lean=7, turn=9, sway=4, arm=14, tail=11, head=.8, wing=16, beat=2, lift=True),
}


def _turn(degrees):
    return np.array(rotation(degrees))


def _world(model, frame):
    pose = copy.deepcopy(frame)
    pose[0] = [4096] * 3 + [0] * 6
    return np.array(mmd.bone_matrices(model, pose))


def _gait(model, frames):
    """(cycles in the clip, phase of the right foot's rearmost point)."""
    ticks = len(frames) - 1
    z = [float(_world(model, frame)[FOOT, 2, 3]) for frame in frames[:-1]]
    centre = sum(z) / ticks
    best = (0, 1, 0)
    for cycles in range(1, 9):
        a = sum((v - centre) * math.cos(2 * math.pi * cycles * t / ticks) for t, v in enumerate(z))
        b = sum((v - centre) * math.sin(2 * math.pi * cycles * t / ticks) for t, v in enumerate(z))
        if a * a + b * b > best[0]:
            best = (a * a + b * b, cycles, math.atan2(b, a))
    return best[1:]


def _carry(model, skeleton, frames, spec):
    parents = [bone[1] for bone in skeleton]
    ticks = len(frames) - 1
    cycles, phase = _gait(model, frames)
    poses = copy.deepcopy(frames)
    mean = {(b, c): sum(f[b][c] for f in frames[:-1]) / ticks for b in ARM_BONES for c in (3, 4, 5)}
    history = {}
    for t, pose in enumerate(poses):
        angle = 2 * math.pi * cycles * t / ticks - phase

        def late(delay):
            return angle - delay

        def spin(bone, turn):
            world = _world(model, pose)
            parent = world[parents[bone], :3, :3]
            set_rotation(pose, bone, parent.T @ turn @ world[bone, :3, :3], history)
        for key, centre in mean.items():
            bone, channel = key
            pose[bone][channel] = round(centre + spec['keep'] * (((pose[bone][channel] - centre + 2048) % 4096) - 2048))
        spin(TORSO, _turn([spec['lean'] + 1.5 * math.cos(2 * late(.9)), math.cos(late(.5)) * spec['turn'],
                           math.sin(late(.5)) * spec['sway']]))
        spin(HEAD, _turn([-spec['lean'] * spec['head'], -math.cos(late(1)) * spec['turn'] * spec['head'],
                          -math.sin(late(.9)) * spec['sway'] * spec['head']]))
        spin(TAIL, _turn([math.cos(2 * late(1.3)) * spec['tail'] * .6, -math.cos(late(1.3)) * spec['tail'], 0]))
        for shoulder, elbow, wrist, side in ARMS:
            spin(shoulder, _turn([math.cos(late(.6)) * spec['arm'] * side, 0, side * spec['low']]))
            spin(elbow, _turn([math.cos(late(1.2)) * spec['arm'] * .8 * side, 0, side * 2 * math.sin(late(1.2))]))
            spin(wrist, _turn([math.cos(late(1.8)) * spec['arm'] * .7 * side, 0, 0]))
        flap = math.sin(2 * math.pi * cycles * spec['beat'] * t / ticks - phase - .4) * spec['wing']
        spin(WINGS[0], _turn([0, 0, flap]))
        spin(WINGS[1], _turn([0, 0, -flap]))
    poses[-1][1:] = copy.deepcopy(poses[0][1:])
    return poses, cycles


def build(data, skeleton):
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = len(skeleton)
    old = mmd.MMD.parse(data, len(skeleton))
    old.type = SPECIES
    new = copy.deepcopy(old)
    channels = {(b, c) for b in ARM_BONES + [TORSO, HEAD, TAIL, *WINGS] for c in (3, 4, 5)}
    checks = []
    for slot, spec in SLOTS.items():
        frames, loop, _ = animsheet.slot_frames(old, len(skeleton), slot)
        poses, cycles = _carry(old, skeleton, frames, spec)
        raised = _clear_floor(old, skeleton, poses, 0) if spec['lift'] else 0
        index = new.anims.table[slot]
        animation = replace_channels(old.anims.anims[index], poses, loop, len(skeleton), channels, tolerance=TOLERANCE)
        if spec['lift']:    # height is kept exact: the spikes would cross the floor again
            animation = replace_channels(animation, poses, loop, len(skeleton), {(1, 7)})
        new.anims.anims[index] = animation
        checks.append(dict(slot=slot, cycles=cycles, raised=raised))
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = mmd.MMD.parse(result, len(skeleton))
    actual.type = SPECIES
    assert old.tmd.build() == actual.tmd.build()
    assert set(changed_programs(old, actual)) >= set(SLOTS)
    for slot in SLOTS:
        frames = animsheet.slot_frames(actual, len(skeleton), slot)[0]
        before = animsheet.slot_frames(old, len(skeleton), slot)[0]
        assert [f[0] for f in frames] == [f[0] for f in before], (slot, 'root')
        lowest = max(_floors(actual, skeleton, frames))
        assert lowest <= FLOOR_MARGIN * 2, (slot, 'floor', lowest)
    return result, dict(species=SPECIES, slots=checks, storage=motionstorage.require(result, len(skeleton)))
