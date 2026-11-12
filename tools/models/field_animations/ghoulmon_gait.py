"""Ghoulmon's field gaits (species 329): idle kept; walk, tired walk and run with planted feet and a living body.

Ghoulmon is a small, stocky one-eyed gremlin with bat wings, long claws and a spiked tail. Bone 1 is the whole upper
body (torso, head and horns in one mesh) with the wings 2-3 (left) and 10-11 (right), the arms 4-9 (right: arm,
forearm, hand, three claws) and 12-17 (left), the tail 19-21 and the hips 18, which carry the legs 22-25 right and
26-29 left: thigh, shin, ankle plate, claws of the foot. Forward is -z; every bone stands unrotated at rest.

The imported clips drove the legs with rotations from the donor's rig (another Digimon): the feet barely left the
ground (lift 27 units in 71 ticks, like the idle), the soles slid by 37-44 % of the travel (207 % at worst) and the
stills looked like the idle. Here `quadruped.py` plants each foot (two-bone IK, heel strike and toe-off, the sole flat
on the floor) and `body` writes everything above the legs as one weighted, overlapped motion: the pelvis bobs twice a
cycle and sways over the loaded foot, the hips turn against the shoulders, the torso rolls and pitches a little later
than the hips, the arms swing against the legs with the forearm, hand and claws each a little later, the wings lift
at each push-off and fold at each landing, each joint after the one before, and the three tail links whip behind
the body. The character is a small bouncy gremlin: a quick bobbing walk with the arms out, a slumped, dragging tired
walk (head down, claws trailing, wings drooping) and a forward-leaning run with a flight phase and wings streaming.

Offline: `tools/models/edit.py get 329` on the commit before this change, then
`python3 -m tools.models.field_animations.ghoulmon_gait --source THAT.MMD --out AFTER.MMD` and `edit.py put 329 AFTER.MMD`.
"""
import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import mmd  # noqa: E402
from tools.models.field_animations import quadruped  # noqa: E402
from tools.models.field_animations.quadruped import mul, tr, rot, set_rot  # noqa: E402

SPECIES = 329
SOURCE = '6191cae7cb5e7b632be250acbeb08c114f7c98c929d182d2223571c0529a8743'   # `edit.py get 329` before this change
TAU = 2 * math.pi
DEG = 4096 / 360
UPPER, HIPS = 1, 18
ARMS = {'R': (4, 5, 6, (7, 8, 9), 1), 'L': (12, 13, 14, (15, 16, 17), -1)}     # shoulder, forearm, hand, claws, side
WINGS = {'L': (2, 3, -1), 'R': (10, 11, 1)}                                    # root, membrane, side
TAIL = (19, 20, 21)
LEGS = {'RH': (22, 23, 24, 1, False), 'LH': (26, 27, 28, -1, False)}      # thigh, shin, ankle plate, side, front
TOE_OF = {'RH': 25, 'LH': 29}
PARENTS = [-1, 0, 1, 2, 1, 4, 5, 6, 6, 6, 1, 10, 1, 12, 13, 14, 14, 14, 1, 18, 19, 20, 18, 22, 23, 24, 18, 26, 27, 28]


def harm(phase, *terms):
    """A sum of cosines: terms are (amplitude, rate, delay in cycles)."""
    return sum(a * math.cos(TAU * rate * (phase - delay)) for a, rate, delay in terms)


def bump(phase, centre, width):
    """A smooth hump of 1 at `centre` falling to 0 `width` cycles away (cosine-squared, wrapping round the loop)."""
    d = (phase - centre + 0.5) % 1.0 - 0.5
    return math.cos(math.pi * d / width / 2) ** 2 if abs(d) < width else 0.0


def body(rig, cfg, phase, pose, hist):
    """Height, sway and the turns of hips and torso, the arms, wings and tail; all closed loops."""
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
    set_rot(pose, UPPER, Wt[UPPER], hist)
    set_rot(pose, HIPS, mul(tr(Wt[UPPER]), Wt[HIPS]), hist)
    # the arms: the shoulder swings as a pendulum against the leg on its side; forearm, hand and claws follow later
    for side, (sh, fo, hand, claws, sd) in ARMS.items():
        leg_at = 0.0 if side == 'R' else 0.5
        swing = c['arm'] * harm(phase, (1, 1, c['arm_at'] + leg_at), (c['arm2'], 2, c['arm_at'] + leg_at + 0.1))
        out = c['arm_out'] * sd + c['arm_roll'] * sd * harm(phase, (1, 2, c['arm_at'] + 0.05))
        Wt[sh] = mul(Wt[UPPER], mul(rot([swing + c['arm_lift'], 0, out]), mul(tr(rig.R(W0, UPPER)), rig.R(W0, sh))))
        set_rot(pose, sh, mul(tr(Wt[UPPER]), Wt[sh]), hist)
        flex = c['elbow'] * harm(phase, (1, 1, c['arm_at'] + leg_at + c['elbow_lag']))
        pose[fo][3] = rest[fo][3] + round((flex - c['elbow_extra']) * DEG)
        wrist = c['wrist'] * harm(phase, (1, 1, c['arm_at'] + leg_at + 2 * c['elbow_lag']))
        pose[hand][3] = rest[hand][3] + round((0.5 * flex + wrist) * DEG)
        for k, b in enumerate(claws):
            curl = c['claw'] * harm(phase, (1, 1, c['arm_at'] + leg_at + 3 * c['elbow_lag'] + 0.03 * k))
            pose[b][3] = rest[b][3] + round((curl - c['claw_hold']) * DEG)
    # the wings lift at each push-off and fold at each landing, the membrane after the root
    for side, (root, memb, sd) in WINGS.items():
        flap = harm(phase - c['wing_lag'], (c['wing'], 2, c['pitch_at']), (c['wing1'], 1, 0.0))
        pose[root][5] = rest[root][5] + round((sd * (c['wing_root'] * flap + c['wing_out'])) * DEG)
        late = harm(phase - 2 * c['wing_lag'], (c['wing'] * 0.7, 2, c['pitch_at']), (c['wing1'] * 0.7, 1, 0.0))
        pose[memb][5] = rest[memb][5] + round(sd * c['wing_memb'] * late * DEG)
        pose[root][3] = rest[root][3] + round(c['wing_pitch'] * flap * DEG)
    # the tail: three links, each later and wider than the one before
    for k, b in enumerate(TAIL):
        late = c['tail_lag'] * (k + 1)
        amp = c['tail'] * (0.7 + 0.5 * k)
        pose[b][3] = rest[b][3] + round((harm(phase - late, (amp, 2, c['pitch_at']), (0.5 * amp, 1, 0.1)) + (c['tail_up'] if k == 0 else 0)) * DEG)
        pose[b][4] = rest[b][4] + round(c['tail_sway'] * (0.6 + 0.5 * k) * math.sin(TAU * (phase - 0.2 - late)) * DEG)


PROFILE = dict(
    species=SPECIES, name='Ghoulmon', source=SOURCE, parents=PARENTS,
    pelvis=UPPER, chest=None, neck=None, head=UPPER, tail=(), loose=(),
    legs=LEGS, pole_world=True, rest_plane=True, pole={False: [0.4, 0.0, -1.0]},
    paw_rest={'RH': [0, 0, 0], 'LH': [0, 0, 0]},     # filled from the rig below
    sole={False: [0, 0, 0]},                            # filled from the rig below
    reach={'front': 0, 'hind': 0},
    fold={False: 90}, clear=0,
    speed_range={0: (0, 0), 2: (15, 31), 3: (10, 20), 4: (35, 52)},
    body=body, floor=3, stance_slip=0.2,
    gaits={},
)
COMMON = dict(
    kind='walk', snap=False, arc=0.5, clear_ease=0.1, world_ease=True, fold_soft=10, slip=0.0, steps=(),
    touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.57, 'RH': 0.57},
    reach={'front': 0, 'hind': -80}, lift={'front': 0, 'hind': 40}, curl={'front': 0, 'hind': 0}, peel={'front': 0, 'hind': -8},
    out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 0}, track={'front': 0, 'hind': 0}, heel=3,
    high=0.1, bob=4, bob2=1, bob_side=0.8, height=-10, shift=5, shift2=0.8, roll_at=0.3,
    hip_tilt=0, hip_pitch=1.5, hip_pitch1=0.4, hip_yaw=6, hip_yaw2=0.8, hip_roll=3, hip_roll2=0.5,
    lean=4, pitch=2, pitch1=0.6, pitch_at=0.15, yaw=2, counter=0.9, roll=3.5, roll2=0.6, yaw_at=0.05, lag=0.07, breath=0,
    arm=24, arm2=0.3, arm_at=0.0, arm_lift=0, arm_out=-12, arm_roll=0, elbow=10, elbow_lag=0.1, elbow_extra=0, wrist=8, claw=10, claw_hold=0,
    wing=7, wing1=3, wing_out=0, wing_root=0, wing_memb=2, wing_pitch=0, wing_lag=0.08, tail=5, tail_lag=0.07, tail_sway=7, tail_up=0,
)
PROFILE['gaits'] = {
    2: dict(COMMON, name='walk', ticks=26, speed=17, height=-14, bob=5, bob_side=1.2, arm=16, arm_lift=-2, elbow=6, wrist=4, claw=4),
    3: dict(COMMON, name='tired walk', ticks=34, speed=11, duty={'LH': 0.64, 'RH': 0.64}, lift={'front': 0, 'hind': 26},
            height=-22, bob=5, bob_side=1.5, lean=14, pitch=2.5, hip_yaw=4, hip_roll=3.5, shift=7, arm=9, elbow=4, wrist=3, claw=4,
            wing=3, wing1=2, wing_out=-8, tail=3, tail_up=0, tail_sway=4, tail_lag=0.1, lag=0.1, arm_lift=-6),
    4: dict(COMMON, name='run', kind='trot', ticks=14, speed=38, duty={'LH': 0.36, 'RH': 0.36}, lift={'front': 0, 'hind': 56},
            height=-4, high=0.42, world_ease=0.85, arc=1.0, bob=8, bob2=1.4, lean=2, pitch=1, hip_yaw=7, hip_roll=3, roll=3,
            arm=16, arm_lift=-4, elbow=6, elbow_extra=0, wrist=4, claw=4, wing=12, wing1=4, tail=9, tail_up=6, tail_lag=0.08),
}


def prepare(model, skeleton):
    """Fill what is read off the rig: each foot's toe direction and the pivot of the sole (the toe point)."""
    import animsheet
    pose = animsheet.slot_frames(model, len(skeleton), 0)[0][0]
    for name, toe in TOE_OF.items():
        PROFILE['paw_rest'][name] = list(pose[toe][6:9])
    PROFILE['sole'][False] = list(pose[TOE_OF['RH']][6:9])


def build(data, skeleton, only=None):
    old = mmd.MMD.parse(data, len(skeleton))
    old.type = SPECIES
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = len(skeleton)
    prepare(old, skeleton)
    profile = dict(PROFILE)
    if only:
        profile['gaits'] = {k: v for k, v in PROFILE['gaits'].items() if k in only}
    return quadruped.build(data, skeleton, profile)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/329-ghoulmon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
