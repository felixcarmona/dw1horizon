"""Piedmon's field idle, walk, condition walk and run as four different levitating clips.

The card-game model came with one 104-tick floating gesture, played in the idle, the walk, the condition walk and the
run; only the distance the root travelled differed, so the four read as one animation, and the boots (which never touch
the ground) slid along with the body in every one of them. This generator writes slots 0 and 1 (the idle), 2, 3 and 4
again from the reviewed 28-bone model (every other slot, the mesh and the rig stay). Piedmon hovers: the boots hang
from the hips and never take a step on the ground, so the clips are a float and a glide, never a ground gait.

Everything moves on the beat of its clip, with a whole number of cycles per loop on every channel. What hangs (the two
ribbons, the collar, the boots, the free end of each arm) follows the body a little later, and further down the chain
later still, so the motion runs along the limb instead of moving it as a block:

- Idle (104 ticks, the importer's length): a slow levitation breath in place. The body rises and settles, the head
  tilts and turns a little, the arms sway with their hands arriving last, the boots dangle and swing like pendulums,
  the ribbons and the collar drift behind the breath.
- Walk (24 ticks): a glide. The body leans slightly forward and bobs twice a loop, the boots swing softly one against
  the other and lift their knees a little, the arms counter-swing with the hands lagging, the ribbons stream back.
- Condition walk (28 ticks): the same glide heavy and low, the body slumped, the head and the arms drooping, the
  boots dragging behind, the ribbons hanging.
- Run (20 ticks): the body pitched far forward, the arms swept back and pumping, the boots trailing behind the hips,
  the ribbons and the collar streaming back and fluttering.

The hover height is the same in every clip (the mean height of the lowest point of the body above the ground, the ribbons aside); the
bob around it is the levitation. The loops keep the importer's root speed per tick (the model has no voice cue).

Offline authoring (the player's build replays the plain delta): `tools/models/edit.py get 245`, then
`python3 -m tools.models.field_animations.piedmon_levitate --source build/imported-model-edit/edit/245-Piedmon.MMD
--out AFTER.MMD` and `tools/models/edit.py put 245 AFTER.MMD`. The source must be the model this module started from.
"""
import copy
import hashlib
import math

import animsheet
import mmd
import motioncyclelayer
import motionstorage
from motiondiscidentity import changed_programs
from tools.models.field_animations.magnadramon_flight import Rig, swing, wave

SPECIES = 245
NB = 28
SLOTS = (0, 1, 2, 3, 4)
SOURCE = '1337bb904e2378aea6baef81eaac614b973d0ae3ea046d7a8435af4ce35e533d'   # the model before this change
PARENTS = [-1, 0, 1, 2, 2, 4, 5, 6, 2, 8, 9, 10, 2, 12,
           13, 2, 15, 16, 2, 18, 1, 20, 21, 1, 23, 24, 1, 1]
WAVE_MEAN = sum(wave(k / 720.) for k in range(720)) / 720   # the bob's mean, so the hover height stays what we set
HOVER = 44.      # mean height of the lowest vertex above the ground, in units (the import floated 35 to 53)

# the two sides: (shoulder, upper arm, forearm, hand), (hip, knee, boot), (ribbon root, middle, tip)
ARMS = ((4, 5, 6, 7), (8, 9, 10, 11))
LEGS = ((20, 21, 22), (23, 24, 25))
RIBBONS = ((12, 13, 14), (15, 16, 17))
PATCHES = (27, 26)

# angles in degrees about the world axes (x across the body, y down, z back); a positive x pitches the body forward,
# swings an arm or a boot back and lifts a ribbon backward
CLIPS = {
    'idle': dict(n=104, beats=2, bob=10, lean=0, pitch=1.2, roll=1.5, yaw=3.5, spine=2.5, twist=3.0,
                 head=0, nod=4.0, tilt=4.5, look=8, collar=3.5,
                 arm=0, arm_swing=12, arm_opp=0, elbow=0, hand=6.0, arm_out=4,
                 leg=3, leg_swing=3, leg_opp=0, knee=3, knee_swing=2, boot=3, boot_swing=3,
                 rib=12, rib_wave=9, rib_flutter=5, rib_out=3, patch=4),
    'walk': dict(n=24, beats=2, bob=14, lean=5, pitch=1.6, roll=3.0, yaw=4.5, spine=2.0, twist=5.0,
                 head=-.60, nod=2.0, tilt=2.0, look=0, collar=3.5,
                 arm=-4, arm_swing=17, arm_opp=1, elbow=-6, hand=11, arm_out=2,
                 leg=10, leg_swing=13, leg_opp=1, knee=12, knee_swing=9, boot=5, boot_swing=9,
                 rib=14, rib_wave=8, rib_flutter=4, rib_out=3, patch=6),
    'tired': dict(n=28, beats=2, bob=8, lean=9, pitch=1.2, roll=3.5, yaw=2.5, spine=3.0, twist=2.5,
                  head=.55, nod=1.5, tilt=4.0, look=0, collar=2.0,
                  arm=9, arm_swing=7, arm_opp=1, elbow=6, hand=4, arm_out=-3,
                  leg=15, leg_swing=8, leg_opp=1, knee=10, knee_swing=7, boot=9, boot_swing=5,
                  rib=4, rib_wave=4, rib_flutter=1.5, rib_out=0, patch=3),
    'run': dict(n=20, beats=2, bob=10, lean=16, pitch=2.0, roll=2.0, yaw=4.0, spine=2.5, twist=4.0,
                head=-.78, nod=1.5, tilt=1.5, look=0, collar=5.0,
                arm=-22, arm_swing=22, arm_opp=1, elbow=-30, hand=14, arm_out=6,
                leg=16, leg_swing=13, leg_opp=1, knee=20, knee_swing=8, boot=12, boot_swing=10,
                rib=34, rib_wave=9, rib_flutter=6, rib_out=5, patch=9),
}
CLIP_OF_SLOT = {0: 'idle', 1: 'idle', 2: 'walk', 3: 'tired', 4: 'run'}


def _parse(data, skeleton):
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = len(skeleton)
    model = mmd.MMD.parse(data, len(skeleton))
    model.type = SPECIES
    return model


def pose_at(rig, mean, base_y, c, t):
    """The pose of clip c at tick t of its loop (the root is added by the caller)."""
    n, u = c['n'], t / c['n']
    p = c['beats'] * u
    pose = copy.deepcopy(mean)
    lean = c['lean']
    sw = lambda lag=0.: swing(u, lag)          # once per loop (the two sides of a stride)
    sb = lambda lag=0.: swing(p, lag)          # once per beat (the bob)
    # the body: rises first on every beat, leans, rolls and turns once a loop
    pose[1][7] = round(base_y - c['bob'] * (wave(p, .25) - WAVE_MEAN))
    rig.turn(pose, 1, x=lean + c['pitch'] * sb(.08), y=c['yaw'] * sw(.30), z=c['roll'] * sw(.05))
    # the chest answers the hips a little later, twisting against them
    rig.turn(pose, 2, x=c['spine'] * sb(.20), y=-c['twist'] * sw(.30), z=-.5 * c['roll'] * sw(.12))
    # the head looks ahead against the lean, nods behind the chest, tilts and looks about
    rig.turn(pose, 3, x=c['head'] * lean + c['nod'] * sb(.30), y=c['look'] * sw(.12) - .5 * c['yaw'] * sw(.30),
             z=c['tilt'] * sw(.22))
    # the collar (neck and ruff) is carried by the head and settles after it
    rig.turn(pose, 18, x=.5 * c['collar'] * sb(.38), z=.5 * c['collar'] * sw(.30))
    rig.turn(pose, 19, x=c['collar'] * sb(.46), z=-.5 * c['collar'] * sw(.40))
    # the arms: a swing that runs from the shoulder out to the hand, each joint later than the one before
    for side, bones in enumerate(ARMS):
        s = 1 if side == 0 else -1                           # right, left
        opp = -1 if (side and c['arm_opp']) else 1           # the walk and run swing the arms against each other
        a, b, f, h = bones
        rig.turn(pose, a, x=c['arm'] + c['arm_swing'] * .55 * opp * sw(.00 + .03 * side),
                 z=s * (c['arm_out'] + .5 * c['arm_swing'] * (1 - c['arm_opp']) * sb(.10)))
        rig.turn(pose, b, x=.4 * c['arm'] + c['arm_swing'] * .45 * opp * sw(.07 + .03 * side))
        rig.turn(pose, f, x=c['elbow'] + c['arm_swing'] * .55 * opp * sw(.15 + .03 * side))
        rig.turn(pose, h, x=.3 * c['elbow'] + c['hand'] * opp * sw(.24 + .03 * side))
    # the boots hang from the hips: pendulums that swing one against the other, knee and boot a beat later
    for side, bones in enumerate(LEGS):
        opp = -1 if (side and c['leg_opp']) else 1
        hip, knee, boot = bones
        base = c['leg'] - .6 * lean                          # hanging down again whatever the body's lean
        rig.turn(pose, hip, x=base + c['leg_swing'] * opp * sw(.00 + .02 * side),
                 z=(1 if side == 0 else -1) * (.4 * c['leg_swing'] * sb(.10) if not c['leg_opp'] else 0))
        rig.turn(pose, knee, x=c['knee'] + c['knee_swing'] * (opp * sw(.13 + .02 * side) + 1) / 2
                 + .5 * c['leg_swing'] * (1 - c['leg_opp']) * sb(.16))
        rig.turn(pose, boot, x=c['boot'] + c['boot_swing'] * opp * sw(.24 + .02 * side))
    # the ribbons stream behind the shoulders: lifted by the glide, a wave running down them, fluttering at the tips
    for side, bones in enumerate(RIBBONS):
        s = 1 if side == 0 else -1
        for k, bone in enumerate(bones):
            lag = .12 + .10 * k + .03 * side
            rig.turn(pose, bone, x=(c['rib'] + c['rib_wave'] * sb(lag) * (1 + .5 * k)) / 3.
                     + c['rib_flutter'] * (k / 2.) * swing(2 * p, .08 * k),
                     z=s * (c['rib_out'] + c['rib_flutter'] * (k + 1) / 3. * sw(.2 + .1 * k)) / 2.)
    # the two small patches on the hips swing behind the hips
    for side, bone in enumerate(PATCHES):
        rig.turn(pose, bone, x=-.4 * lean + c['patch'] * sb(.30 + .04 * side))
    return pose


def lowest(model, skeleton, pose, skip=(12, 13, 14, 15, 16, 17)):
    """Height of the lowest vertex above the ground at this pose (the root is not applied). The ribbons hang lower than
    the boots at times, so the hover height is that of the body without them (pass skip=() for every vertex)."""
    p = [list(v) for v in pose]
    p[0] = [4096] * 3 + [0] * 6
    mats = mmd.bone_matrices(model, p)
    low = None
    for bone, (obj, _) in enumerate(skeleton):
        if obj < 0 or bone in skip:
            continue
        m = mats[bone]
        for x, y, z, _ in model.tmd.obj_verts(obj):
            h = m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3]
            low = h if low is None else max(low, h)
    return -low


def author(model, skeleton):
    """`model` (the importer's bytes) with the field slots replaced -> (bytes, proof)."""
    old = _parse(model, skeleton)
    native, _, _ = animsheet.slot_frames(old, NB, 0)
    assert len(native) == 105
    # the mean of the native float is the rest pose of every channel
    mean = [[round(sum(f[b][i] for f in native[:-1]) / (len(native) - 1)) for i in range(9)] for b in range(NB)]
    base_y = mean[1][7]
    result = copy.deepcopy(old)
    streams, checks = {}, []
    for slot in (0, 2, 3, 4):
        c = CLIPS[CLIP_OF_SLOT[slot]]
        frames, loop, events = animsheet.slot_frames(old, NB, slot)
        assert loop == 0 and not events
        n = c['n']
        before = len(frames) - 1
        assert before == 104, (slot, before)
        speed = 0. if slot == 0 else (frames[-1][0][8] - frames[0][0][8]) / before   # the importer's speed per tick
        # the same hover height in every clip: lower or raise the whole loop until the lowest vertex averages HOVER
        offset = 0.
        for _ in range(3):
            rig = Rig(old, skeleton)
            heights = [lowest(old, skeleton, pose_at(rig, mean, base_y + offset, c, t)) for t in range(n)]
            offset -= HOVER - sum(heights) / n
        rig = Rig(old, skeleton)
        out = []
        for t in range(n + 1):
            pose = pose_at(rig, mean, base_y + offset, c, t % n)
            pose[0] = list(frames[0][0])
            pose[0][8] = round(frames[0][0][8] + speed * t)
            out.append([[round(x) for x in v] for v in pose])
        mmd.close_loop(out, 0)
        streams[slot] = len(result.anims.anims)
        result.anims.anims.append(mmd.encode_anim(out, NB, 0, [], tol=1))
        checks.append(dict(slot=slot, ticks=n, root_per_tick=round(speed, 2), hover_offset=round(offset, 1)))
    streams[1] = streams[0]
    for slot in SLOTS:
        result.anims.table[slot] = streams[slot]
    for anim in result.anims.anims:
        anim.tail = b''
    result.anims.anims, result.anims.table = motioncyclelayer.share_identical_streams(result.anims.anims,
                                                                                    result.anims.table)
    output = result.build()
    effective = _parse(output, skeleton)
    assert effective.tmd.build() == old.tmd.build()
    assert changed_programs(old, effective) == list(SLOTS), changed_programs(old, effective)
    return output, dict(checks=checks, storage=motionstorage.require(output, NB))


def build(data, skeleton):
    if (hashlib.sha256(data).hexdigest() != SOURCE or [b[1] for b in skeleton] != PARENTS
            or [b[0] for b in skeleton] != list(range(-1, 27))):
        raise ValueError('Piedmon needs the reviewed 28-bone model it had before this change')
    output, extra = author(data, skeleton)
    return output, dict(species=SPECIES, source_sha256=SOURCE, output_sha256=hashlib.sha256(output).hexdigest(),
                        changed_slots=list(SLOTS), field=extra)


if __name__ == '__main__':
    import argparse
    import sys
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--source', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    sys.path.insert(0, 'tools')
    skeleton = [(i - 1, p) for i, p in enumerate(PARENTS)]
    data, proof = build(open(args.source, 'rb').read(), skeleton)
    open(args.out, 'wb').write(data)
    print(len(data), 'bytes', proof['field'])
