"""Knightmon's tired walk and run (species 321): planted feet, two mirrored strides, an even gait.

Knightmon is an armoured knight on short legs: bone 1 is the upper body (rest pitched forward 7 degrees) with the
shoulders and arms (2-5 right: shoulder, upper arm, forearm, hand; 7-10 left, the hand 10 carrying the giant sword 11),
the head 6, the cloak 12 on the back; bone 13 is the hips under it (it turns the pitch back, so the legs stand upright)
with the scabbard 14, the loincloth 20-21 and the legs 15-19 right and 22-26 left: the thigh (15), a knee guard (16) that
only follows it, the knee (17), the foot (18) and its toe plate (19). Forward is -z.

The imported tired walk and run (kept by the `knightmon-chibi` overlay after `chibi.py`) were written for a rig whose
legs stand differently: in the tired walk the left foot stood on the floor for 10 of 23 ticks while sliding (slip 79 % of
the travel, worst 120 %) and the right one for 5, lifting 74 against 58 units, so the knight limped on one leg; the run
slid its feet (slip 61 and 26 %, worst 203 %), stood 7 ticks on one foot and 3 on the other, 17 ticks a cycle so the two
strides were different. Here `quadruped.py` plants each foot (a two-bone solve on thigh and knee, the knee guard
following, the sole flat), the two legs step half a cycle apart with the same lift, stance and track (the left leg's
rest stands a step behind the right one's: `leg_reach` cancels that), and `body` writes everything above them: hips and
chest turn against each other, the upper body rolls over the loaded foot, the arms swing as pendulums (the sword arm a
little less) with the forearm and the sword late, the head follows late, the cloak, the scabbard and the loincloth
trail. Every channel is a closed sum of harmonics followed by a loose spring, so the curves are smooth.

Only the tired walk (slot 3) and the run (slots 4 and 36) change; the idle and the walk stay byte for byte. `build`
runs the chibi reshaping first (the overlay's base generator); nothing is stored but the overlay's recipe.
Offline: `python3 -m tools.models.field_animations.knightmon_gait --source EDIT.MMD --out AFTER.MMD` with EDIT.MMD the
model `tools/models/edit.py get 321` makes.
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

SPECIES = 321
TAU = 2 * math.pi
DEG = 4096 / 360
UPPER, HIPS, HEAD, CLOAK, SCABBARD, CLOTH, SWORD = 1, 13, 6, 12, 14, 20, 11
ARMS = {'R': (2, 3, 4, 5, 1), 'L': (7, 8, 9, 10, -1)}    # shoulder, upper arm, forearm, hand, side (+1 = x > 0)
LEGS = {'LH': (22, 24, 25, -1, False), 'RH': (15, 17, 18, 1, False)}
TOE_OF = {'LH': 26, 'RH': 19}
LINKS = {17: 16, 24: 23}
PARENTS = [-1, 0, 1, 2, 3, 4, 1, 1, 7, 8, 9, 10, 1, 1, 13, 13, 15, 16, 17, 18, 13, 20, 13, 22, 23, 24, 25]


def harm(phase, *terms):
    """A sum of cosines: terms are (amplitude, rate, delay in cycles)."""
    return sum(a * math.cos(TAU * rate * (phase - delay)) for a, rate, delay in terms)


def body(rig, cfg, phase, pose, hist):
    """Height, sway and the turns of hips and upper body, the arms, the sword, the head, the cloak and the loincloth;
    all closed loops."""
    c, W0 = cfg, rig.still
    rest = rig.rest
    bob = harm(phase, (c['bob'], 2, c['high']), (c['bob2'], 4, c['high'] + 0.03))
    pose[UPPER][7] = rest[UPPER][7] - c['height'] - bob
    pose[UPPER][6] = rest[UPPER][6] + harm(phase, (c['shift'], 1, c['roll_at']))
    hp = c['hip_tilt'] + harm(phase, (c['hip_pitch'], 2, c['pitch_at']))
    hy = harm(phase, (c['hip_yaw'], 1, c['yaw_at']))
    hr = harm(phase, (c['hip_roll'], 1, c['roll_at'] + 0.5))
    lag = c['lag']
    up = c['lean'] + harm(phase - lag, (c['pitch'], 2, c['pitch_at']))
    uy = -c['counter'] * hy
    ur = harm(phase - lag, (c['roll'], 1, c['roll_at']))
    Wt = {0: [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}
    Wt[UPPER] = mul(rot([up, uy, ur]), rig.R(W0, UPPER))
    Wt[HIPS] = mul(rot([hp, hy, hr]), rig.R(W0, HIPS))

    def put(bone, parent, delta):
        Wt[bone] = mul(delta, rig.R(W0, bone))
        set_rot(pose, bone, mul(tr(Wt[parent]), Wt[bone]), hist)
    set_rot(pose, UPPER, Wt[UPPER], hist)
    put(HIPS, UPPER, rot([hp, hy, hr]))
    nod = harm(phase - c['nod_lag'], (c['nod'], 2, c['nod_at']))
    put(HEAD, UPPER, rot([up - c['steady'] * (up - c['lean']) - c['head'] + nod, uy * 0.5, ur * 0.6]))
    for side, (sh, el, fo, hand, sd) in ARMS.items():
        leg_at = 0.0 if side == 'R' else 0.5
        gain = 1.0 if side == 'R' else c['sword_arm']
        swing = gain * c['arm'] * harm(phase, (1, 1, c['arm_at'] + leg_at))
        out = c['arm_out'] * sd
        Wt[sh] = mul(Wt[UPPER], mul(rot([swing + c['arm_lift'], 0, out]), mul(tr(rig.R(W0, UPPER)), rig.R(W0, sh))))
        set_rot(pose, sh, mul(tr(Wt[UPPER]), Wt[sh]), hist)
        flex = gain * c['elbow'] * harm(phase, (1, 1, c['arm_at'] + leg_at + c['elbow_lag']))
        pose[el][3] = rest[el][3] + round((flex - c['elbow_extra']) * DEG)
        wrist = gain * c['wrist'] * harm(phase, (1, 1, c['arm_at'] + leg_at + 2 * c['elbow_lag']))
        pose[fo][3] = rest[fo][3] + round((0.5 * flex + wrist) * DEG)
    sw = c['sword'] * harm(phase, (1, 1, c['arm_at'] + 0.5 + 3 * c['elbow_lag']), (0.4, 2, c['pitch_at'] + 0.2))
    pose[SWORD][3] = rest[SWORD][3] + round(sw * DEG)
    f = harm(phase - c['cloak_lag'], (c['cloak'], 2, c['pitch_at']))
    pose[CLOAK][3] = rest[CLOAK][3] + round((f + c['cloak_out']) * DEG)
    d = harm(phase - c['cloth_lag'], (c['cloth'], 2, c['pitch_at']))
    pose[CLOTH][3] = rest[CLOTH][3] + round((d + c['cloth_out']) * DEG)
    s = harm(phase - c['cloth_lag'], (c['scabbard'], 2, c['pitch_at']))
    pose[SCABBARD][3] = rest[SCABBARD][3] + round(s * DEG)


PROFILE = dict(
    species=SPECIES, name='Knightmon', source=None, parents=PARENTS,
    pelvis=UPPER, chest=None, neck=None, head=HEAD, tail=(), loose=(),
    legs=LEGS, links=LINKS, pole_world=True, rest_plane=True, pole={False: [0.3, 0.0, -1.0]},
    paw_rest={'LH': [0, 0, 0], 'RH': [0, 0, 0]}, sole={False: [0, 0, 0]},
    reach={'front': 0, 'hind': 0}, fold={False: 80}, clear=2,
    speed_range={0: (0, 0), 2: (15, 31), 3: (10, 20), 4: (35, 52)},
    body=body, floor=3, stance_slip=0.2, gaits={},
)
COMMON = dict(
    kind='walk', snap=False, arc=0.5, clear_ease=0.1, world_ease=True, fold_soft=10, slip=0.0, steps=('LH', 'RH'),
    reach={'front': 0, 'hind': 0}, lift={'front': 0, 'hind': 30}, curl={'front': 0, 'hind': 0}, peel={'front': 0, 'hind': 0},
    out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 0}, track={'front': 0, 'hind': 10}, heel=3, settle=1.5,
    touchdown={'LH': 0.0, 'RH': 0.5},
    high=0.3, bob=6, bob2=1.0, height=-40, shift=6, roll_at=0.3,
    hip_tilt=0, hip_pitch=1.0, hip_yaw=4, hip_roll=3, pitch=1.5, pitch_at=0.15, yaw_at=0.05, lean=10, roll=3.5, counter=1.0, lag=0.07,
    steady=0.8, head=-8, nod=1.0, nod_at=0.2, nod_lag=0.06,
    arm=8, sword_arm=0.7, arm_at=0.0, arm_lift=0, arm_out=4, elbow=4, elbow_extra=0, elbow_lag=0.05, wrist=0, sword=3,
    cloak=3, cloak_lag=0.1, cloak_out=0, cloth=2, cloth_lag=0.1, cloth_out=0, scabbard=1.5,
)
FOLLOW = {2: (0.55, 0.5), 3: (0.6, 0.45), 4: (0.5, 0.45), 5: (0.45, 0.4),
          7: (0.55, 0.5), 8: (0.6, 0.45), 9: (0.5, 0.45), 10: (0.45, 0.4), SWORD: (0.4, 0.35),
          HEAD: (0.7, 0.55), CLOAK: (0.4, 0.3), CLOTH: (0.45, 0.35), SCABBARD: (0.5, 0.4)}   # (rad per tick, damping)


def spring(values, rate, damping):
    """A loose second-order follower of a cyclic sequence (run round three times so the loop settles)."""
    n = len(values)
    y, v = values[0], 0.0
    out = []
    for i in range(3 * n):
        x = values[i % n]
        v += (rate * rate * (x - y) - 2 * damping * rate * v)
        y += v
        out.append(y)
    return out[-n:]


def compose(rig, cfg, frames):
    """The cycle with the arms, the sword, the head and the loose parts passed through a loose spring each."""
    ticks = cfg['ticks']
    out = [[list(b) for b in pose] for pose in frames[:ticks]]
    follow = cfg.get('follow', 1.0)
    for b, (rate, damping) in FOLLOW.items():
        for ch in (3, 4, 5):
            seq = [out[i][b][ch] for i in range(ticks)]
            mixed = spring(seq, rate, damping)
            for i in range(ticks):
                out[i][b][ch] = seq[i] + (mixed[i] - seq[i]) * follow
    closing = [list(v) for v in out[0]]
    closing[0][8] = -round(cfg['speed'] * ticks)
    out.append(closing)
    return out


PROFILE['gaits'] = {
    3: dict(COMMON, name='tired walk', ticks=22, speed=11.5, duty={'LH': 0.62, 'RH': 0.62}, height=-26, bob=5, lift={'front': 0, 'hind': 22},
            peel={'front': 0, 'hind': -6}, lean=6, head=-32, arm=4, sword_arm=0.5, arm_out=-12, elbow=2, elbow_extra=0, hip_yaw=3.5, hip_roll=3, shift=7,
            roll=3.5, cloak=2, cloth=1.5, compose=compose, cycles=1),
    4: dict(COMMON, name='run', kind='trot', ticks=16, speed=38, duty={'LH': 0.34, 'RH': 0.34}, height=-34, high=0.42, arc=0.6,
            clear_ease=0.05, lift={'front': 0, 'hind': 50}, bob=10, bob2=1.5, lean=10, head=-16, arm_out=-12, arm=18, sword_arm=0.3, elbow=10, elbow_extra=10,
            hip_yaw=6, hip_roll=3, roll=3.5, cloak=6, cloth=4, sword=2, compose=compose, cycles=1),
}


def prepare(model, skeleton, rig_world):
    """Fill what is read off the rig: each foot's toe direction and the pivot of the sole."""
    import animsheet
    pose = animsheet.slot_frames(model, len(skeleton), 0)[0][0]
    for name, toe in TOE_OF.items():
        PROFILE['paw_rest'][name] = list(pose[toe][6:9])
    PROFILE['sole'][False] = list(pose[TOE_OF['RH']][6:9])


def build(data, skeleton):
    """The reshaped model with the two clips written on it -> (bytes, proof)."""
    from tools.models.field_animations import chibi
    reshaped, proof = chibi.build(data, skeleton)
    exe = mmd.exe()
    kept = exe.skeleton[SPECIES], exe.bone_count[SPECIES]
    try:
        old = mmd.MMD.parse(reshaped, len(skeleton))
        old.type = SPECIES
        exe.skeleton[SPECIES] = skeleton
        exe.bone_count[SPECIES] = len(skeleton)
        prepare(old, skeleton, None)
        profile = dict(PROFILE, source=hashlib.sha256(reshaped).hexdigest())
        result, gait = quadruped.build(reshaped, skeleton, profile)
    finally:
        exe.skeleton[SPECIES], exe.bone_count[SPECIES] = kept
    proof = dict(proof, preceding_recipe=dict(recipe='chibi', output_sha256=proof['output_sha256']),
                 output_sha256=gait['output_sha256'], gait=gait, resident_bytes=[gait['storage']['resident_bytes'],
                                                                                gait['storage']['resident_limit']])
    proof['bytes'] = [proof['bytes'][0], len(result)]
    return result, proof


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/321-knightmon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof['gait'], indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
