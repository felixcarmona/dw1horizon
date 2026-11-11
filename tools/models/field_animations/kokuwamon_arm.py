"""Kokuwamon's carried arm in the idle, walk, condition walk and run, applied after the field pace pass.

The source clips only ever animate the arm on one side: the forearm of the arm chain 18/19 swings together with the
shoulder cover 17, while the arm chain 13/14/15/16 (the one on the -X side, with the claw reaching forward) keeps
its shoulder still, its forearm within three degrees and its claw at the same place relative to the torso for
the whole walk. In the idle it moves a few degrees with the body and nothing more. Only its cover (12) swung, turning
over a stiff arm, at the same moment as the cover on the other side.

Here the stiff arm joins in:

* the forearm 14 carries most of the swing, the way the forearm 19 does on the other side, with the shoulder 13
  following a little behind it and a little less, and the claw following the forearm;
* it alternates with the other arm: its swing is the other forearm's own curve half a clip later, so the arms are
  never forward together; its cover 12 plays its own existing curve half a clip later too, so the cover turns
  with the arm it belongs to instead of against it;
* the forearm trails the shoulder by a fraction of the swing, so the elbow arrives late and the claw last;
* the walk swings loose and the condition walk less, so it tires; the run bends the elbow in and pumps harder;
* the idle follows the body: the torso's slow pitch comes through the shoulder, the forearm and the cover a
  little late, so the arm settles after the body has.

Everything else (the boots, the legs, the body, the other arm, the claws, the travel, the sounds, the other
programs, the mesh and the skeleton) stays exact. Loops close because the swing period is the clip's own.
"""
import copy
import math

import numeric as np
import animsheet
import mmd
import motioncyclelayer
import motionstorage
from motiondiscidentity import changed_programs
from tools.models.field_animations.channels import replace_channels, coalesce
from tools.models.field_animations.war_greymon import rotation, set_rotation

SPECIES = 247
BODY, COVER, SHOULDER, FOREARM = 2, 12, 13, 14
OTHER_FOREARM = 19
TOLERANCE = 1
# slot: swing of the shoulder 13 and the forearm 14 in degrees: `yaw` sweeps the claw forward (positive) and inward about
# the torso's vertical axis, `roll` lifts it about the torso's side axis as it comes forward; `trail` is how late the
# forearm is, as a share of the clip; `bend` raises the forearm for the whole clip (the run's bent elbow)
GAITS = {
    2: dict(sh_yaw=7.0, sh_roll=6.0, fo_yaw=9.0, fo_roll=8.0, trail=.07, bend=0.0, half=True),
    3: dict(sh_yaw=5.0, sh_roll=4.0, fo_yaw=6.0, fo_roll=5.0, trail=.07, bend=0.0, half=True),
    4: dict(sh_yaw=9.0, sh_roll=8.0, fo_yaw=11.0, fo_roll=12.0, trail=.06, bend=10.0, half=True),
    0: dict(sh_yaw=2.5, sh_roll=2.0, fo_yaw=3.5, fo_roll=3.0, trail=.10, bend=0.0, half=False, follow=12),
}
SLOTS = tuple(sorted(GAITS))
CHANNELS = {(b, c) for b in (COVER, SHOULDER, FOREARM) for c in (3, 4, 5)}
YAW = -1.0       # sign of the rotation about the vertical axis that turns the claw forward
ROLL = -1.0      # sign of the rotation about the side axis that lifts it


def _sample(values, x):
    """Linear sample of one cycle (values has no closing frame) at the fractional tick x."""
    n = len(values)
    i = math.floor(x)
    k = x - i
    return values[i % n] * (1 - k) + values[(i + 1) % n] * k


def _driver(frames, slot, ticks):
    """The swing's shape, from -1 to 1, a value per tick of one cycle. Walks: the other forearm's own curve, forward
    positive. Idle: the torso's slow pitch."""
    if slot == 0:
        values = [frames[t][BODY][3] for t in range(ticks)]
        sign = 1.0
    else:
        values = [frames[t][OTHER_FOREARM][3] for t in range(ticks)]
        sign = -1.0
    middle = (max(values) + min(values)) / 2
    half = (max(values) - min(values)) / 2
    return [sign * (v - middle) / half for v in values]


def _swing(poses, frames, slot, spec, report):
    ticks = len(frames) - 1
    drive = _driver(frames, slot, ticks)
    shift = ticks / 2 if spec['half'] else 0
    lag = spec.get('follow', 0)
    trail = spec['trail'] * ticks
    history = {b: [float(x) for x in frames[0][b][3:6]] for b in (COVER, SHOULDER, FOREARM)}
    if spec['half']:        # the cover plays its own curve half a clip later, turning with the arm it belongs to
        for t in range(ticks):
            for c in (3, 4, 5):
                poses[t][COVER][c] = frames[(t + ticks // 2) % ticks][COVER][c]
        poses[ticks][COVER] = copy.deepcopy(poses[0][COVER])
    lead = [_sample(drive, t + shift - lag) for t in range(ticks)]
    late = [_sample(drive, t + shift - lag - trail) for t in range(ticks)]
    # added angles keep the mean pose of the clip: only the swing around it is new
    mean = sum(lead) / ticks, sum(late) / ticks
    lead = [v - mean[0] for v in lead]
    late = [v - mean[1] for v in late]
    angles = []
    for t in range(ticks):
        pose = poses[t]
        top = np.array(mmd.rot_matrix(*pose[SHOULDER][3:6]))
        new_top = rotation([ROLL * spec['sh_roll'] * lead[t], YAW * spec['sh_yaw'] * lead[t], 0]) @ top
        set_rotation(pose, SHOULDER, new_top, history)
        top = np.array(mmd.rot_matrix(*pose[SHOULDER][3:6]))
        fore = np.array(mmd.rot_matrix(*pose[FOREARM][3:6]))
        lift = spec['fo_roll'] * late[t] + spec['bend']
        goal = rotation([ROLL * lift, YAW * spec['fo_yaw'] * late[t], 0]) @ (top @ fore)
        set_rotation(pose, FOREARM, top.T @ goal, history)
    for b in (SHOULDER, FOREARM):
        poses[ticks][b] = copy.deepcopy(poses[0][b])


def build(data, skeleton, species=SPECIES):
    n = len(skeleton)
    mmd.exe().skeleton[species] = skeleton
    mmd.exe().bone_count[species] = n
    old = mmd.MMD.parse(data, n)
    old.type = species
    new = copy.deepcopy(old)
    checks = []
    for slot in SLOTS:
        spec = GAITS[slot]
        frames, loop, _ = animsheet.slot_frames(old, n, slot)
        assert loop == 0
        ticks = len(frames) - 1
        poses = copy.deepcopy(frames)
        report = {}
        _swing(poses, frames, slot, spec, report)
        index = new.anims.table[slot]
        animation = replace_channels(old.anims.anims[index], poses, loop, n, CHANNELS, tolerance=TOLERANCE)
        animation, _ = coalesce(animation)
        new.anims.anims[index] = animation
        checks.append(dict(slot=slot, ticks=ticks, **report))
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = mmd.MMD.parse(result, n)
    actual.type = species
    assert old.tmd.build() == actual.tmd.build()
    assert changed_programs(old, actual) == list(SLOTS), changed_programs(old, actual)
    return result, dict(species=species, checks=checks, storage=motionstorage.require(result, n))


TAKES_SPECIES = True
