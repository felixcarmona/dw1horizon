"""Gallantmon's field gaits (species 318): idle, walk, tired walk and run of a heavy royal knight, feet planted.

Gallantmon is a huge armoured knight with a lance on its right arm, a round shield on its left, a long red cape and a
plume of three metal links hanging from the back of its helmet. Bone 1 is the upper body (rest pitched forward 10
degrees) with the shoulders and arms (2-4 right: shoulder, elbow, hand with the lance; 12-14 left: shoulder, elbow, hand
with the shield; the pauldrons 5 and 15 hang on the shoulders), the head 6 with the plume chain 7-11 behind it and the cape
16-18; bone 19 is the pelvis under the upper body (it turns the pitch back so the legs stand upright) with the legs 20-23
right and 24-27 left: thigh (short, pointing forward), shin, ankle block and toes. Forward is -z.

What was wrong. The imported clips drove the legs with rotations from another rig and the root did not move the same
amount each tick: the walk's steps were 6 to 30 units, the tired walk's 8 to 26 and the run's 35 to 67, so the knight
stuttered along; a stance foot slid 80 % (walk, worst 260 %) and 104 / 163 % (tired walk) of the body's travel, 62 / 84 %
in the run; the stance lasted 3 to 9 ticks of a cycle, the run (53 units a tick) was outside the native speeds, the
tired walk's feet crossed the middle, and the arms, the lance, the shield and the plume swung in lockstep.

What it is now. `quadruped.py` plants each foot (two-bone IK on the thigh and shin, the sole flat on the floor, the foot
keeping its own outward splay); the legs step in turn at half a cycle on a track wide enough for the two boots. `body`
writes everything above them, with a knight's weight: the pelvis sinks on each footfall, the hips turn against the
chest, the chest rolls over the loaded foot, the head steadies; the lance arm swings little and the lance tip follows a
beat late, the shield arm stays near the body and rocks with it, the pauldrons ride the shoulders without turning with
the arms; the cape, the plume and the lance hand follow through on loose springs. Walk, tired walk and run are two
cycles long (the second lifts, lands and sinks a little otherwise, eased into and out of the first), so no step repeats.
The idle (4 s) breathes, rolls the weight from one boot to the other, looks aside and lets the cape and the plume
settle. The battle walk and run (slots 35, 36) now play the field walk and run, as the battle idle (33) plays the idle.

Offline only (player builds replay the pinned delta): `tools/models/edit.py get 318` on the commit before this change,
then `python3 -m tools.models.field_animations.gallantmon_gait --source THAT.MMD --out AFTER.MMD` and
`edit.py put 318 AFTER.MMD`.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import mmd  # noqa: E402
import motioncyclelayer  # noqa: E402
import motionstorage  # noqa: E402
from tools.models.field_animations import quadruped  # noqa: E402
from tools.models.field_animations.quadruped import mul, tr, rot, set_rot  # noqa: E402
from tools.models.field_animations.dinohyumon_gait import blend, spring  # noqa: E402

SPECIES = 318
SOURCE = 'ef0a0ec845795c35f7a0d140e17571c5e8cdb50459ab622054c9cc2cf1b8cb1d'   # `edit.py get 318` before this change
TAU = 2 * math.pi
DEG = 4096 / 360
UPPER, HIPS, HEAD = 1, 19, 6
PLUME = (7, 8, 9, 10, 11)
CAPE = (16, 17, 18)
ARMS = {'R': (2, 3, 4, 5, 1), 'L': (12, 13, 14, 15, -1)}    # shoulder, elbow, hand (lance / shield), pauldron, side (+1 = x > 0)
LEGS = {'LH': (24, 25, 26, -1, False), 'RH': (20, 21, 22, 1, False)}
TOE_OF = {'LH': 27, 'RH': 23}
TWINS = {0: 33, 2: 35, 4: 36}          # the battle idle, walk and run play the field clips


def harm(phase, *terms):
    """A sum of cosines: terms are (amplitude, rate, delay in cycles)."""
    return sum(a * math.cos(TAU * rate * (phase - delay)) for a, rate, delay in terms)


def bump(phase, centre, width):
    """A smooth hump of 1 at `centre` falling to 0 `width` cycles away (cosine-squared, wrapping round the loop)."""
    d = (phase - centre + 0.5) % 1.0 - 0.5
    return math.cos(math.pi * d / width / 2) ** 2 if abs(d) < width else 0.0


def body(rig, cfg, phase, pose, hist):
    """Height, sway and the three turns of pelvis and upper body, the arms, the head, the plume and the cape; all
    closed loops."""
    c, W0 = cfg, rig.still
    rest = rig.rest
    bob = harm(phase, (c['bob'], 2, c['high']), (c['bob2'], 4, c['high'] + 0.03), (c['bob_side'], 1, c['high'] + 0.2))
    pose[UPPER][7] = rest[UPPER][7] - c['height'] - bob
    pose[UPPER][6] = rest[UPPER][6] + harm(phase, (c['shift'], 1, c['roll_at']), (c['shift2'], 3, c['roll_at'] + 0.07))
    hp = c['hip_tilt'] + harm(phase, (c['hip_pitch'], 2, c['pitch_at']), (c['hip_pitch1'], 1, c['pitch_at'] + 0.12))
    hy = harm(phase, (c['hip_yaw'], 1, c['yaw_at']), (c['hip_yaw2'], 3, c['yaw_at'] + 0.05))
    hr = harm(phase, (c['hip_roll'], 1, c['roll_at'] + 0.5), (c['hip_roll2'], 3, c['roll_at'] + 0.57))
    lag = c['lag']
    up = c['lean'] + harm(phase - lag, (c['pitch'], 2, c['pitch_at']), (c['pitch1'], 1, c['pitch_at'] + 0.12))
    uy = -c['counter'] * hy + harm(phase - lag, (c['yaw'], 1, c['yaw_at'] + 0.1))
    ur = harm(phase - lag, (c['roll'], 1, c['roll_at']), (c['roll2'], 3, c['roll_at'] + 0.06))
    up += c['breath'] * math.sin(TAU * (phase - 0.1))
    Wt = {0: [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}
    Wt[UPPER] = mul(rot([up, uy, ur]), rig.R(W0, UPPER))
    Wt[HIPS] = mul(rot([hp, hy, hr]), rig.R(W0, HIPS))

    def put(bone, parent, delta):
        Wt[bone] = mul(delta, rig.R(W0, bone))
        set_rot(pose, bone, mul(tr(Wt[parent]), Wt[bone]), hist)
    set_rot(pose, UPPER, Wt[UPPER], hist)
    put(HIPS, UPPER, rot([hp, hy, hr]))
    nod = harm(phase - c['nod_lag'], (c['nod'], 2, c['nod_at']), (c['nod2'], 1, c['nod_at'] + 0.1))
    look = c['look'] * harm(phase, (1, 1, c['look_at']), (0.3, 2, c['look_at'] + 0.1))
    gaze = sum(a * bump(phase, at, w) for at, w, a in c['gaze'])
    tilt = sum(a * bump(phase, at, w) for at, w, a in c['tilt'])
    put(HEAD, UPPER, rot([up - c['steady'] * (up - c['lean']) - c['head'] + nod + c['head_up'],
                          uy * 0.5 + look + gaze, ur * 0.6 + tilt]))
    # the arms: the lance arm and the shield arm each have their own swing; the pauldron keeps its place on the shoulder
    for side, (sh, el, hand, pad, sd) in ARMS.items():
        k = 'r' if side == 'R' else 'l'
        leg_at = 0.0 if side == 'R' else 0.5
        swing = c['arm_' + k] * harm(phase, (1, 1, c['arm_at'] + leg_at), (c['arm2'], 2, c['arm_at'] + leg_at + 0.1))
        out = c['out_' + k] * sd
        gest = sum(a * bump(phase, at, w) for at, w, a in c['gesture'].get(side, ()))
        lift = c['lift_' + k] - c['hold_' + k] * (pose[UPPER][7] - rest[UPPER][7]) / 8.0     # the shield hangs 460 units below the shoulder: 1 degree is 8 units
        Wt[sh] = mul(Wt[UPPER], mul(rot([swing + lift + gest, 0, out]), mul(tr(rig.R(W0, UPPER)), rig.R(W0, sh))))
        set_rot(pose, sh, mul(tr(Wt[UPPER]), Wt[sh]), hist)
        Wt[pad] = mul(Wt[UPPER], mul(rot([0.25 * (swing + lift + gest), 0, 0.3 * out]), mul(tr(rig.R(W0, UPPER)), rig.R(W0, pad))))
        set_rot(pose, pad, mul(tr(Wt[sh]), Wt[pad]), hist)
        flex = c['elbow_' + k] * harm(phase, (1, 1, c['arm_at'] + leg_at + c['elbow_lag']))
        pose[el][3] = rest[el][3] + round((flex - c['bend_' + k]) * DEG)
        wrist = c['wrist_' + k] * harm(phase, (1, 1, c['arm_at'] + leg_at + 2 * c['elbow_lag']))
        pose[hand][3] = rest[hand][3] + round((wrist - c['grip_' + k]) * DEG)
    # the plume and the cape trail the body: each link later and a little more
    for k, b in enumerate(PLUME):
        late = c['plume_lag'] * (k + 1)
        d = harm(phase - late, (c['plume'] * (0.5 + 0.25 * k), 2, c['pitch_at']), (c['plume1'] * (0.5 + 0.25 * k), 1, 0.0))
        pose[b][3] = rest[b][3] + round((d + c['plume_out'] * (1 if k == 0 else 0.3)) * DEG)
        pose[b][4] = rest[b][4] + round(c['plume_side'] * (0.4 + 0.3 * k) * math.sin(TAU * (phase - late - 0.2)) * DEG)
    flick = lambda lag: sum(a * bump(phase - lag, at, w) for at, w, a in c['flick'])
    for k, b in enumerate(CAPE):
        late = c['cape_lag'] * (k + 1.5)
        d = harm(phase - late, (c['cape'] * (0.6 + 0.5 * k), 2, c['pitch_at']), (c['cape1'] * (0.6 + 0.5 * k), 1, 0.0))
        pose[b][3] = rest[b][3] + round((d + flick(c['cape_lag'] * k * 2) * (0.7 + 0.3 * k) + (c['cape_out'] if k == 0 else c['cape_drape'])) * DEG)


PROFILE = dict(
    species=SPECIES, name='Gallantmon', source=SOURCE,
    parents=[-1, 0, 1, 2, 3, 2, 1, 6, 7, 8, 9, 10, 1, 12, 13, 12, 1, 16, 17, 1, 19, 20, 21, 22, 19, 24, 25, 26],
    pelvis=UPPER, chest=None, neck=None, head=HEAD, tail=(), loose=(),
    legs=LEGS, pole_world=True, rest_plane=True, pole={False: [0.58,0.0,-1.0]},
    paw_rest={'LH': [0, 0, 0], 'RH': [0, 0, 0]},     # filled from the rig below
    sole={False: [0, 0, 0]},                            # filled from the rig below
    reach={'front': 0, 'hind': 0},
    fold={False: 105}, clear=3,
    speed_range={0: (0, 0), 2: (15, 31), 3: (10, 20), 4: (35, 52)},
    body=body, floor=3, stance_slip=0.2,
    gaits={},
)
COMMON = dict(
    kind='walk', snap=False, arc=0.5, clear_ease=0.1, world_ease=True, fold_soft=10, slip=0.0, steps=('LH', 'RH'),
    reach={'front': 0, 'hind': 0}, lift={'front': 0, 'hind': 40}, curl={'front': 0, 'hind': 0}, peel={'front': 0, 'hind': 0},
    out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 0}, track={'front': 0, 'hind': 0}, heel=0,
    high=0.1, bob=3, bob2=0.8, bob_side=0.5, height=-22, shift=5, shift2=0.8, roll_at=0.3,
    hip_tilt=0, hip_pitch=1, hip_pitch1=0.3, hip_yaw=4, hip_yaw2=0.5, hip_roll=2, hip_roll2=0.4,
    lean=0, pitch=1.5, pitch1=0.5, pitch_at=0.15, yaw=1, counter=0.9, roll=2.5, roll2=0.5, yaw_at=0.05, lag=0.07, breath=0,
    steady=0.8, head=0, head_up=0, nod=1, nod2=0.5, nod_at=0.2, nod_lag=0.06, look=0, look_at=0.3,
    arm_r=6, arm_l=3, arm2=0, arm_at=0.0, out_r=0, out_l=0, lift_r=0, lift_l=-8, hold_r=0, hold_l=0.9,
    elbow_r=3, elbow_l=2, bend_r=0, bend_l=0, wrist_r=3, wrist_l=1, grip_r=0, grip_l=0, elbow_lag=0.06,
    plume=3, plume1=2, plume_lag=0.04, plume_out=0, plume_side=2,
    cape=4, cape1=2, cape_out=0, cape_drape=0, cape_lag=0.07,
    gaze=(), tilt=(), gesture={}, flick=(),
)
PROFILE['gaits'] = {
    0: dict(COMMON, name='idle', ticks=120, speed=0, steps=(),
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 1.0, 'RH': 1.0}, track={'front': 0, 'hind': 16}, leg_reach={'RH': 0, 'LH': 95}, height=-10,
            bob=1.0, bob2=0, bob_side=0, shift=4, shift2=0, hip_yaw=0, hip_yaw2=0, hip_roll=1.2, hip_roll2=0, hip_pitch=0.5,
            hip_pitch1=0, roll=1.6, roll2=0, yaw=0, pitch=0.5, pitch1=0, counter=0, lean=2, head=2, nod=0.6, nod2=0, look=0,
            arm_r=0, arm_l=0, out_l=3, lift_l=-8, elbow_r=1.5, elbow_l=1, wrist_r=1.5, wrist_l=0.5, breath=1.4,
            gaze=((0.55, 0.2, 18), (0.9, 0.1, -8)), tilt=((0.55, 0.22, 5),), plume=2, plume1=1, plume_lag=0.03,
            cape=2, cape1=1, cape_lag=0.03, flick=((0.72, 0.12, 6),)),
    2: dict(COMMON, name='walk', ticks=24, speed=16,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.58, 'RH': 0.58}, lift={'front': 0, 'hind': 44},
            peel={'front': 0, 'hind': -6}, lean=3, head=3, height=-26, high=0.27, bob=7, bob2=1.0, bob_side=0.8,
            hip_yaw=5, hip_roll=3, roll=3, shift=6, arm_r=6, arm_l=3, cape_out=8),
    3: dict(COMMON, name='tired walk', ticks=30, speed=11,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.64, 'RH': 0.64}, height=-34, high=0.3, bob=7, lift={'front': 0, 'hind': 26},
            peel={'front': 0, 'hind': -6}, lean=11, head=-8, hip_yaw=3.5, hip_roll=3, shift=7, roll=3.5, bob_side=1.0,
            arm_r=3, arm_l=2, cape_out=7),
    4: dict(COMMON, name='run', kind='trot', ticks=18, speed=38,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.35, 'RH': 0.35}, height=-38, high=0.42, world_ease=0.85, arc=1.0,
            lift={'front': 0, 'hind': 60}, peel={'front': 0, 'hind': -4}, bob=11, bob2=1.5, lean=13, head=5, hip_yaw=6, hip_roll=3, roll=3, arm_r=14, arm_l=7,
            elbow_r=6, elbow_l=4, bend_r=6, bend_l=8, lift_l=-18, out_l=-24, plume=6, plume1=3, plume_out=5, cape=8, cape1=4, cape_out=12, cape_drape=4,
            cape_lag=0.09),
}


def prepare(model, skeleton):
    """Fill what is read off the rig: each foot's toe direction and the pivot of the sole (the toe point)."""
    import animsheet
    pose = animsheet.slot_frames(model, len(skeleton), 0)[0][0]
    for name, toe in TOE_OF.items():
        PROFILE['paw_rest'][name] = list(pose[toe][6:9])
    PROFILE['sole'][False] = list(pose[TOE_OF['RH']][6:9])


def build(data, skeleton):
    old = mmd.MMD.parse(data, len(skeleton))
    old.type = SPECIES
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = len(skeleton)
    prepare(old, skeleton)
    result, proof = quadruped.build(data, skeleton, PROFILE)
    new = mmd.MMD.parse(result, len(skeleton))
    for slot, twin in TWINS.items():
        new.anims.table[twin] = new.anims.table[slot]
    for anim in new.anims.anims:
        anim.tail = b''
    used = sorted({i for i in new.anims.table if i is not None})
    renumber = {i: k for k, i in enumerate(used)}
    new.anims.anims = [new.anims.anims[i] for i in used]
    new.anims.table = [None if i is None else renumber[i] for i in new.anims.table]
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    out = new.build()
    proof = dict(proof, output_sha256=hashlib.sha256(out).hexdigest(), storage=motionstorage.require(out, len(skeleton)))
    return out, proof


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/318-gallantmon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
