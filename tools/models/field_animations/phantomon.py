"""Phantomon's field idle, walk, condition walk and run as four different clips.

The import played one 104-tick levitation (cloak, hood, arms, chain and scythe) in the idle, the walk, the condition
walk and the run; only the distance the root travelled differed, so the four read as one animation. This generator
writes slots 0, 2, 3 and 4 again from the reviewed 20-bone import (every other slot, the mesh and the rig stay).
Phantomon has no legs: a hooded robe with a hem, a cloak at the back, a flail ball on a chain in the right hand and a
scythe in the left, so every clip is a hover and a glide, and the root height never changes.

Everything moves on the beat of its clip, with a whole number of cycles per loop on every channel, and what hangs
(cloak, hem, hand chain, scythe chain) follows the body a little later, further down the chain later still:

- Idle (104 ticks): a slow hover in place. Two soft bobs, the hood looking slowly to one side and back, the cloak and
  hem swaying late, the right hand's chain swinging, the scythe hand nearly still.
- Walk (24 ticks): a glide, the body leaning slightly forward, two bobs a loop, the free right arm swinging forward
  and back with a bent elbow, the cloak trailing, the flail chain lagging the hand.
- Condition walk (28 ticks): the same glide lower in energy, the body bowed, the hood hanging, the arms limp and
  small, the cloak hanging.
- Run (20 ticks): leaning far forward, the arms driving forward and back with the elbows folded, the cloak, the
  hem and both chains streaming back and fluttering.

The scythe arm holds the scythe upright in every clip and only swings a little. The loops have the importer's
lengths (24, 28 and 20 ticks), its root speed and its voice cue (bank 1, note 17, once per loop at the importer's frame).

Offline authoring (the player's build replays the plain delta): `tools/models/edit.py get 229`, then
`python3 -m tools.models.field_animations.phantomon --source build/imported-model-edit/edit/229-Phantomon.MMD
--out AFTER.MMD` and `tools/models/edit.py put 229 AFTER.MMD`. The source must be the model this module started from.
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

SPECIES = 229
NB = 20
SLOTS = (0, 2, 3, 4)
SOURCE = '99d0f64e889a05a098601845ce22c47b11ebace16a4e8452d1947ebf18aeb5ce'   # the model before this change
PARENTS = [-1, 0, 1, 1, 3, 4, 1, 6, 7, 1, 9, 10, 1, 11, 13, 14, 15, 8, 17, 18]
DEG = 4096 / 360
WAVE_MEAN = sum(wave(k / 720.) for k in range(720)) / 720   # the bob's mean, so the hover height stays the native one
CLOAK = (3, 4, 5)
RIGHT_ARM = (6, 7)
LEFT_ARM = (9, 10)
BALL_CHAIN = (17, 18, 19)
SCYTHE_CHAIN = (14, 15, 16)

# angles in degrees; positive x pitches the torso forward, swings an arm back and lifts the cloak and chains backward.
CLIPS = {
    'idle': dict(n=104, beats=2, bob=13, lean=0, pitch=.8, roll=1.2, yaw=1.5, look=9, nod=2.0, head=0,
                 cloak=0, cloak_wave=4.5, cloak_roll=2.0, hem=0, hem_wave=3.5,
                 arm=-3, arm_swing=3.5, elbow=-6, elbow_swing=3.5, scythe_arm=0, scythe_swing=1.5,
                 ball=0, ball_swing=7, ball_flutter=0, chain=0, chain_swing=5, chain_flutter=2),
    'walk': dict(n=24, beats=2, bob=15, lean=7, pitch=2.2, roll=2.5, yaw=3.2, look=0, nod=2.5, head=-.55,
                 cloak=11, cloak_wave=8, cloak_roll=3, hem=6, hem_wave=5,
                 arm=-2, arm_swing=24, elbow=-13, elbow_swing=13, scythe_arm=5, scythe_swing=6,
                 ball=6, ball_swing=14, ball_flutter=0, chain=5, chain_swing=7, chain_flutter=0),
    'tired': dict(n=28, beats=2, bob=6, lean=14, pitch=1.4, roll=3.6, yaw=2.0, look=0, nod=1.5, head=.7,
                  cloak=3, cloak_wave=4, cloak_roll=3.5, hem=2, hem_wave=3,
                  arm=3, arm_swing=8, elbow=-5, elbow_swing=5, scythe_arm=1, scythe_swing=2.5,
                  ball=2, ball_swing=7, ball_flutter=0, chain=2, chain_swing=4, chain_flutter=0),
    'run': dict(n=20, beats=2, bob=10, lean=23, pitch=2.0, roll=2.0, yaw=3.5, look=0, nod=1.5, head=-.78,
                cloak=31, cloak_wave=9, cloak_roll=2.5, hem=20, hem_wave=8,
                arm=-6, arm_swing=38, elbow=-34, elbow_swing=20, scythe_arm=9, scythe_swing=6,
                ball=34, ball_swing=14, ball_flutter=5, chain=26, chain_swing=8, chain_flutter=4),
}
CLIP_OF_SLOT = {0: 'idle', 2: 'walk', 3: 'tired', 4: 'run'}
# the importer's voice cue (bank 1, note 17): one per loop, at the frame it had in the original 24, 28 and 20-tick clips
CUE_FRAME = {2: 3, 3: 2, 4: 3}


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
    # the body: bobs on the beat (rising first), leans, rolls and turns once per loop
    pose[1][7] = round(base_y - c['bob'] * (wave(p, .25) - WAVE_MEAN))
    swing1 = lambda lag=0.: swing(u, lag)
    rig.turn(pose, 1, x=lean + c['pitch'] * swing(p, .08), y=c['yaw'] * swing1(.30), z=c['roll'] * swing1(.05))
    # the hood: against the lean (looks ahead), nodding a little later, looking around in the idle
    rig.turn(pose, 2, x=c['head'] * lean + c['nod'] * swing(p, .20), y=-.6 * c['yaw'] * swing1(.30) + c['look'] * swing1(.10))
    # the cloak at the back: lifted by the lean, a wave running down its three pieces
    for k, bone in enumerate(CLOAK):
        lag = .18 + .09 * k
        rig.turn(pose, bone, x=c['cloak'] / 3 + c['cloak_wave'] * (k + 1) / 3 * swing(p, lag),
                 z=c['cloak_roll'] * (k + 1) / 3 * swing1(.20 + .10 * k))
    # the hem trails the body, held down against its lean
    rig.turn(pose, 12, x=c['hem'] - .45 * lean + c['hem_wave'] * swing(p, .30))
    # the free right arm swings forward and back (negative is forward), the forearm folding late
    a, b = RIGHT_ARM
    rig.turn(pose, a, x=c['arm'] + c['arm_swing'] * swing1(.0))
    rig.turn(pose, b, x=c['elbow'] + c['elbow_swing'] * swing1(.12))
    # the flail chain hangs from the hand and follows its swing against it, further down later
    for k, bone in enumerate(BALL_CHAIN):
        rig.turn(pose, bone, x=(c['ball'] - .5 * c['arm_swing'] * swing1(.20 + .08 * k)) / 3 * (1 + .4 * k) + c['ball_swing'] * swing(p, .30 + .09 * k) / 3
                 + c['ball_flutter'] * swing(2 * p, .10 * k))
    # the scythe arm keeps the scythe upright and swings only a little, against the free arm
    a, b = LEFT_ARM
    rig.turn(pose, a, x=c['scythe_arm'] - c['scythe_swing'] * swing1(.0))
    rig.turn(pose, b, x=.5 * c['scythe_swing'] * swing1(.25))
    # the chain on the scythe hangs and sways late
    for k, bone in enumerate(SCYTHE_CHAIN):
        rig.turn(pose, bone, x=c['chain'] / 3 + c['chain_swing'] * (k + 1) / 3 * swing(p, .35 + .10 * k)
                 + c['chain_flutter'] * swing(2 * p, .12 * k))
    return pose


def author(model, skeleton):
    """`model` (the importer's bytes) with the four field slots replaced -> (bytes, proof)."""
    old = _parse(model, skeleton)
    native, _, _ = animsheet.slot_frames(old, NB, 0)
    assert len(native) == 105
    # the mean of the native hover is the rest pose of every channel; the hover height stays the same
    mean = [[round(sum(f[b][i] for f in native[:-1]) / (len(native) - 1)) for i in range(9)] for b in range(NB)]
    base_y = mean[1][7]
    result = copy.deepcopy(old)
    streams, checks = {}, []
    for slot in SLOTS:
        c = CLIPS[CLIP_OF_SLOT[slot]]
        frames, loop, events = animsheet.slot_frames(old, NB, slot)
        assert loop == 0
        n = c['n']
        before = len(frames) - 1
        assert before == 104, (slot, before)
        if slot == 0:
            speed = 0.
        else:
            speed = (frames[-1][0][8] - frames[0][0][8]) / before   # the importer's field speed, per tick
        rig = Rig(old, skeleton)
        out = []
        for t in range(n + 1):
            pose = pose_at(rig, mean, base_y, c, t % n)
            pose[0] = list(frames[0][0])
            pose[0][8] = round(frames[0][0][8] + speed * t)
            out.append([[round(x) for x in v] for v in pose])
        mmd.close_loop(out, 0)
        cues = [(CUE_FRAME[slot] - 1, 'sound', dict(e[2], frame=CUE_FRAME[slot])) for e in events] if slot else []
        assert len(cues) == (slot != 0) and len(events) == len(cues)
        streams[slot] = len(result.anims.anims)
        result.anims.anims.append(mmd.encode_anim(out, NB, 0, cues, tol=1))
        checks.append(dict(slot=slot, ticks=n, root_per_tick=round(speed, 2), cues=len(cues)))
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
            or [b[0] for b in skeleton] != list(range(-1, 19))):
        raise ValueError('Phantomon needs the reviewed 20-bone model it had before this change')
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
