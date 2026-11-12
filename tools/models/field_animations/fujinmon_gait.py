"""Fujinmon's field gaits (species 317): walk, tired walk and run with planted feet on its own two legs.

Fujinmon is a stocky wind warrior with long cannon arms and a great green ring on its back. Bone 1 is the body (rest
pitched forward 10 degrees, it carries the height), with the chest 2 (the ring is its mesh), the shoulders 3 (right) and 7
(left) each with an upper arm 4/8, a drill fist 5/9 and a spiked pauldron 6/10, the head 11 and the scarf 12-15 hanging
from it; the pelvis 16 sits at the body's origin with the legs under it: 17-20 left, 21-24 right (hip and thigh, knee and
shin, ankle, toes). Forward is -z.

The imported clips drove the legs with rotations from another rig: the soles slid over the floor (44 % of the body's
speed on average in the walk, 120 % in the condition walk, 83 % in the run, 460 % at worst), the run kicked the feet 200
units up for a single tick on the ground at 52.8 units a tick, the chest turned 56 degrees against the pelvis and the
pelvis dipped 38 units in a walk. Here `quadruped.py` plants
each foot (two-bone solve on the thigh and shin, the sole flat and still on the floor in stance, the boot keeping its
own splay), the legs step in turn at half a cycle, and `body` writes everything above them: the pelvis turns and rolls
against the chest, the body sinks on each landing and rises over the loaded foot, the spiked pauldrons (bones 6 and 10) are rotors and turn one whole turn a loop about their own axle, the heavy cannon arms swing against
the legs as delayed pendulums (a little behind the shoulder, the pauldron staying put), the head steadies and the scarf
trails late. The idle is the model's own and is not changed.

Offline: `tools/models/edit.py get 317` on the commit before this change, then
`python3 -m tools.models.field_animations.fujinmon_gait --source THAT.MMD --out AFTER.MMD` and `edit.py put 317 AFTER.MMD`.
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
from tools.models.field_animations import quadruped  # noqa: E402
from tools.models.field_animations.quadruped import mul, tr, rot, set_rot  # noqa: E402

SPECIES = 317
SOURCE = 'bba322999fc9542975925c7153ec0d654e5deebc613e9f0135d3683fd496737d'   # `edit.py get 317` before this change
TAU = 2 * math.pi
DEG = 4096 / 360
TURN = 4096
BODY, CHEST, HEAD, PELVIS = 1, 2, 11, 16
ARMS = {'R': (3, 4, 5, 6, 1), 'L': (7, 8, 9, 10, -1)}   # shoulder, upper arm, fist, pauldron, side (+1 = x > 0)
SCARF = (12, 13, 14, 15)
LEGS = {'LH': (17, 18, 19, -1, False), 'RH': (21, 22, 23, 1, False)}
TOE_OF = {'LH': 20, 'RH': 24}


def harm(phase, *terms):
    """A sum of cosines: terms are (amplitude, rate, delay in cycles)."""
    return sum(a * math.cos(TAU * rate * (phase - delay)) for a, rate, delay in terms)


def body(rig, cfg, phase, pose, hist):
    """Height, the pelvis and chest turns, the cannon arms, the head and the scarf; all closed loops."""
    c, W0 = cfg, rig.still
    rest = rig.rest
    bob = harm(phase, (c['bob'], 2, c['high']), (c['bob2'], 4, c['high'] + 0.03), (c['bob_side'], 1, c['high'] + 0.2))
    pose[BODY][7] = rest[BODY][7] - c['height'] - bob
    pose[BODY][6] = rest[BODY][6] + harm(phase, (c['shift'], 1, c['roll_at']), (c['shift2'], 3, c['roll_at'] + 0.07))
    # the body carries the forward lean; the pelvis turns and rolls on its own, the chest turns against it
    hp = c['hip_tilt'] + harm(phase, (c['hip_pitch'], 2, c['pitch_at']), (c['hip_pitch1'], 1, c['pitch_at'] + 0.12))
    hy = harm(phase, (c['hip_yaw'], 1, c['yaw_at']), (c['hip_yaw2'], 3, c['yaw_at'] + 0.05))
    hr = harm(phase, (c['hip_roll'], 1, c['roll_at'] + 0.5), (c['hip_roll2'], 3, c['roll_at'] + 0.57))
    lag = c['lag']
    up = c['lean'] + harm(phase - lag, (c['pitch'], 2, c['pitch_at']), (c['pitch1'], 1, c['pitch_at'] + 0.12))
    uy = -c['counter'] * hy + harm(phase - lag, (c['yaw'], 1, c['yaw_at'] + 0.1))
    ur = harm(phase - lag, (c['roll'], 1, c['roll_at']), (c['roll2'], 3, c['roll_at'] + 0.06))
    Wt = {0: [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}
    Wt[BODY] = mul(rot([c['body_lean'], 0, 0]), rig.R(W0, BODY))
    Wt[PELVIS] = mul(rot([hp, hy, hr]), rig.R(W0, PELVIS))
    Wt[CHEST] = mul(rot([up, uy, ur]), rig.R(W0, CHEST))
    set_rot(pose, BODY, Wt[BODY], hist)
    for bone in (PELVIS, CHEST):
        set_rot(pose, bone, mul(tr(Wt[BODY]), Wt[bone]), hist)
    # the head keeps most of its gaze: it follows the chest by `1 - steady`
    nod = harm(phase - c['nod_lag'], (c['nod'], 2, c['nod_at']), (c['nod2'], 1, c['nod_at'] + 0.1))
    Wt[HEAD] = mul(rot([up - c['steady'] * (up - c['lean']) - c['head'] + nod, uy * 0.5 + c['look'] * harm(phase, (1, 1, 0.3)), ur * 0.6]),
                   rig.R(W0, HEAD))
    set_rot(pose, HEAD, mul(tr(Wt[CHEST]), Wt[HEAD]), hist)
    # the cannon arms swing against the legs about the chest's side axis, each bone a little later than the one above it:
    # a delayed pendulum; the pauldron mostly stays where the chest keeps it
    for side, (sh, upper, fist, pad, sd) in ARMS.items():
        leg = 'LH' if side == 'R' else 'RH'       # an arm goes forward with the opposite leg
        at = c['arm_at'] + (0.0 if leg == 'LH' else 0.5)
        swing = c['arm'] * harm(phase, (1, 1, at))
        flex = c['elbow'] * harm(phase, (1, 1, at + c['elbow_lag'])) + c['elbow_extra']
        hand = c['fist'] * harm(phase, (1, 1, at + 2 * c['elbow_lag']))
        out = c['arm_out'] * sd + c['arm_roll'] * sd * harm(phase, (1, 1, at))
        chain = {sh: rot([swing + c['arm_lift'], 0, out]), upper: rot([swing + c['arm_lift'] - flex, 0, out]),
                 fist: rot([swing + c['arm_lift'] - flex - hand, 0, out]), pad: rot([c['pad'] * swing, 0, out])}
        for bone in (sh, upper, fist, pad):
            parent = rig.sk[bone][1]
            Wt[bone] = mul(Wt[CHEST], mul(chain[bone], mul(tr(rig.R(W0, CHEST)), rig.R(W0, bone))))
            set_rot(pose, bone, mul(tr(Wt[parent]), Wt[bone]), hist)
    # the spiked pauldrons are rotors: they turn about their own axle (the chest's x axis, as in the model's idle and
    # run) one whole turn each loop, so the clip closes; the loop's length makes the rate (18, 13 and 26 degrees a tick)
    for side, (sh, upper, fist, pad, sd) in ARMS.items():
        pose[pad][3:6] = [round(TURN * c['spin'] * phase), 0, 0]
    # the scarf hangs behind the head and trails the body: each link a little later and a little more
    for k, b in enumerate(SCARF):
        late = c['scarf_lag'] * (k + 1)
        d = harm(phase - late, (c['scarf'] * (0.6 + 0.4 * k), 2, c['pitch_at']), (c['scarf1'] * (0.6 + 0.4 * k), 1, 0.0))
        pose[b][3] = rest[b][3] + round((d + (c['scarf_out'] if k == 1 else 0) + (c['scarf_drape'] if k > 1 else 0)) * DEG)


PROFILE = dict(
    species=SPECIES, name='Fujinmon', source=SOURCE,
    parents=[-1, 0, 1, 2, 3, 4, 3, 2, 7, 8, 7, 2, 11, 12, 13, 14, 1, 16, 17, 18, 19, 16, 21, 22, 23],
    pelvis=BODY, chest=None, neck=None, head=HEAD, tail=(), loose=(),
    legs=LEGS, pole_world=True, rest_plane=True, pole={False: [0.3, 0.0, -1.0]},
    paw_rest={'LH': [0, 0, 0], 'RH': [0, 0, 0]},     # filled from the rig below
    sole={False: [0, 0, 0]},                            # filled from the rig below
    reach={'front': 0, 'hind': 0},
    fold={False: 105}, clear=2,
    speed_range={2: (15, 31), 3: (10, 20), 4: (35, 52)},
    body=body, floor=3, stance_slip=0.2,
    gaits={},
)
COMMON = dict(
    kind='walk', snap=False, arc=0.5, clear_ease=0.1, world_ease=True, fold_soft=10, slip=0.0, steps=('LH', 'RH'),
    reach={'front': 0, 'hind': 0}, lift={'front': 0, 'hind': 40}, curl={'front': 0, 'hind': 0}, peel={'front': 0, 'hind': 0},
    out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 0}, track={'front': 0, 'hind': 0}, heel=0,
    high=0.1, bob=3, bob2=0.8, bob_side=0.5, height=0, shift=3, shift2=0.5, roll_at=0.3,
    hip_tilt=0, hip_pitch=1, hip_pitch1=0.3, hip_yaw=4, hip_yaw2=0.5, hip_roll=2, hip_roll2=0.4,
    lean=0, body_lean=0, pitch=1.5, pitch1=0.5, pitch_at=0.15, yaw=1, counter=0.9, roll=2.5, roll2=0.5, yaw_at=0.05, lag=0.07,
    steady=0.8, head=0, nod=1, nod2=0.5, nod_at=0.2, nod_lag=0.06, look=0,
    arm=14, arm_at=0.5, arm_lift=0, arm_out=0, arm_roll=0, spin=1, elbow=6, elbow_extra=0, elbow_lag=0.06, fist=0, pad=0,
    scarf=4, scarf1=2, scarf_out=0, scarf_drape=0, scarf_lag=0.07,
)
PROFILE['gaits'] = {
    # a heavy, unhurried stomp: a bent stance leg, the knee lifting clear, flat boots, the body sinking on each landing and
    # rising over the planted foot, the pelvis turning against the chest, the cannons swinging late
    2: dict(COMMON, name='walk', ticks=20, speed=18,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.6, 'RH': 0.6}, lift={'front': 0, 'hind': 48},
            height=-30, high=0.28, bob=6, bob2=1, bob_side=1.0, hip_yaw=5, hip_roll=3, roll=3, hip_pitch=1.5, shift=4,
            lean=2, head=3, arm=22, elbow=9, fist=4, arm_out=3, pad=0.35, scarf=5, scarf1=3, scarf_lag=0.1),
    3: dict(COMMON, name='tired walk', ticks=28, speed=12,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.66, 'RH': 0.66}, lift={'front': 0, 'hind': 30},
            height=-40, high=0.3, bob=6, bob2=0.8, bob_side=1.2, hip_yaw=3, hip_roll=3, roll=3, shift=5, lean=9, body_lean=3,
            head=-8, arm=7, elbow=3, fist=2, arm_out=4, pad=0.3, scarf=3, scarf1=1.5, scarf_lag=0.12, scarf_drape=-4),
    4: dict(COMMON, name='run', kind='trot', ticks=14, speed=40, world_ease=0.85, arc=1.0,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.38, 'RH': 0.38}, lift={'front': 0, 'hind': 80},
            height=-40, bob=10, bob2=1.5, high=0.44, body_lean=10, lean=8, head=5, hip_yaw=7, hip_roll=3, roll=3,
            arm=34, elbow=10, elbow_extra=28, fist=10, arm_out=4, pad=0.3, scarf=9, scarf1=4, scarf_out=14, scarf_lag=0.09),
}


def prepare(model, skeleton):
    """Fill what is read off the rig: each boot's toe direction and the pivot of the sole (the toe point)."""
    import animsheet
    pose = animsheet.slot_frames(model, len(skeleton), 0)[0][0]
    for name, toe in TOE_OF.items():
        PROFILE['paw_rest'][name] = list(pose[toe][6:9])     # the toe point in the ankle bone's space
    PROFILE['sole'][False] = list(pose[TOE_OF['RH']][6:9])


def build(data, skeleton):
    old = mmd.MMD.parse(data, len(skeleton))
    old.type = SPECIES
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = len(skeleton)
    prepare(old, skeleton)
    return quadruped.build(data, skeleton, PROFILE)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/317-fujinmon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
