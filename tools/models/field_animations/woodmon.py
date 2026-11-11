"""Woodmon's field gaits (species 272): a trunk that moves, four short root legs on planted feet, log arms that swing.

The rig is one trunk bone (1) carrying everything: the log arms (2-3 right, 4-5 left: a shoulder piece and a long forearm
log), two small claw hands on the chest (6-8, 9-11) and four three-bone root legs (12-14 right front, 15-17 left front,
18-20 right hind, 21-23 left hind; forward is -z). The imported clips left the trunk bone still, replayed the idle's arm
curve in every gait and slid the feet. Here the legs are written with quadruped.py (a lateral-sequence walk, each foot flat
and still on the floor while the body passes over it) and `trunk` below moves everything above them with the footfalls:
the trunk bobs and rolls over the loaded side and shifts its weight sideways, yaws against the hips, leans into the run and
slouches when tired, and the log arms swing opposite to the legs a little late (shoulder first, the log after it), the
claws on the chest flop after the trunk. The idle (slots 0 and 33) is a calm rewrite: slow breathing, small late sways. See tools/models/README.md.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet  # noqa: E402
import mmd  # noqa: E402
import motionstorage  # noqa: E402
from tools.models.field_animations import quadruped  # noqa: E402
from tools.models.field_animations.quadruped import mul, tr, rot, set_rot  # noqa: E402

TAU = 2 * math.pi
ARMS = {'R': (2, 3, 1), 'L': (4, 5, -1)}
CLAWS = {'R': (6, 7, 8, 1), 'L': (9, 10, 11, -1)}


def harm(phase, *terms):
    """A sum of cosines: terms are (amplitude, rate, delay in cycles)."""
    return sum(a * math.cos(TAU * (rate * (phase - delay))) for a, rate, delay in terms)


def trunk(rig, cfg, phase, pose, hist):
    """Trunk (bone 1), log arms and claw hands for a cycle phase (no leg: quadruped.gait places those)."""
    rest = rig.rest
    c = cfg
    # a landing weight: two dips a cycle, sharper than a sine, and a share of the cycle rate so the sides differ
    bob = harm(phase, (c['bob'], 2, c['high']), (c['bob2'], 4, c['high'] + 0.03), (c['bob_side'], 1, c['high'] + 0.2))
    roll = harm(phase, (c['roll'], 1, c['roll_at']), (c['roll2'], 3, c['roll_at'] + 0.05))
    yaw = harm(phase, (c['yaw'], 1, c['yaw_at']), (c['yaw2'], 2, c['yaw_at'] + 0.1))
    pitch = c['tilt'] + harm(phase, (c['pitch'], 2, c['pitch_at']), (c['pitch1'], 1, c['pitch_at'] + 0.15))
    shift = harm(phase, (c['shift'], 1, c['roll_at'] + 0.02), (c['shift2'], 3, c['roll_at'] + 0.1))
    pose[1][6] = rest[1][6] + shift
    pose[1][7] = rest[1][7] - c['height'] - bob
    set_rot(pose, 1, mul(mmd.rot_matrix(*rest[1][3:6]), rot([pitch, yaw, roll])), hist)
    # arms: opposite to the legs of their side (the right arm goes forward as the left front leg does), the forearm
    # following the shoulder late and folding as the arm goes forward; a little lift keeps the log tips off the floor
    for key, (shoulder, elbow, side) in ARMS.items():
        d = c['arm_at'] + (0.0 if key == 'R' else 0.5 + c['arm_skew'])
        swing = harm(phase, (c['arm'], 1, d), (c['arm2'], 2, d + c['arm2_at']))
        late = harm(phase, (c['arm'] * c['follow'], 1, d + c['arm_lag']), (c['arm2'], 2, d + c['arm_lag'] + c['arm2_at']))
        fold = c['fold'] * (0.5 + 0.5 * harm(phase, (1, 1, d + c['fold_at'])))
        out = side * (c['arm_out'] + c['arm_out_roll'] * math.sin(TAU * (phase - c['roll_at'])) * side)
        s2 = mul(rot([0, 0, out]), rot([swing + c['arm_base'], 0, 0]))
        s3 = mul(rot([late + fold, 0, 0]), s2)
        r2 = mmd.rot_matrix(*rest[shoulder][3:6])
        r3 = mmd.rot_matrix(*rest[elbow][3:6])
        cur2 = mul(s2, r2)
        set_rot(pose, shoulder, cur2, hist)
        set_rot(pose, elbow, mul(tr(cur2), mul(s3, mul(r2, r3))), hist)
    # the claw hands on the chest hang from the trunk and trail its motion: three joints, each a little later
    for key, (a, b, c3, side) in CLAWS.items():
        for k, bone in enumerate((a, b, c3)):
            lag = c['claw_lag'] * (k + 1)
            rest_rot = mmd.rot_matrix(*rest[bone][3:6])
            d = harm(phase - lag, (c['claw'], 2, c['high'] + 0.1), (c['claw'] * 0.4, 1, c['roll_at'] + 0.1))
            e = harm(phase - lag, (c['claw'] * 0.7, 1, c['roll_at'] + 0.3 + (0 if key == 'R' else 0.1)))
            set_rot(pose, bone, mul(rest_rot, rot([d * (1 + 0.5 * k), 0, side * e])), hist)


PROFILE = dict(
    species=272, name='Woodmon',
    source='e7e2d7e6e9a34c41dcb283b3ffb9eb227a16ce7a2eef0bbda11b49ac6907a4e0',
    parents=[-1, 0, 1, 2, 1, 4, 1, 6, 7, 1, 9, 10, 1, 12, 13, 1, 15, 16, 1, 18, 19, 1, 21, 22],
    pelvis=1, chest=None, neck=None, head=None,
    body=trunk,
    legs={'RF': (12, 13, 14, 1, True), 'LF': (15, 16, 17, -1, True), 'RH': (18, 19, 20, 1, False), 'LH': (21, 22, 23, -1, False)},
    tail=(), loose=(),
    paw_flat={'RF': [0, -5.7, 0], 'LF': [0, 12.7, 0], 'RH': [0, -3.7, 0], 'LH': [0, 12.7, 0]},
    pole_world=True, rest_plane=True,
    pole={True: [1, -0.3, 0.2], False: [1, -0.3, -0.2]},
    sole={True: [0, 30, -15], False: [0, 30, -15]},
    reach={'front': -2, 'hind': 2},
    fold={True: 46, False: 51},
    clear=3,
    speed_range={2: (15, 31), 3: (10, 20), 4: (35, 52)},
    floor=6, stance_slip=0.3,
    gaits={},
)

COMMON = dict(reach={'front': 0, 'hind': 0}, snap=False, arc=1.3, clear_ease=0.5, fold_soft=10, slip=0.0,
              lift={'front': 14, 'hind': 10}, curl={'front': 6, 'hind': 6}, peel={'front': 6, 'hind': 6}, out={'front': 3, 'hind': 3}, wide={'front': 12, 'hind': 18},
              steps=('LF', 'RF'), high=0.1, bob=4, bob2=1.0, bob_side=0.8, roll=4, roll2=0.6, roll_at=0.0, yaw=4, yaw2=0.8, yaw_at=0.1,
              tilt=0, pitch=1, pitch1=0.5, pitch_at=0.2, shift=6, shift2=0.8, height=0,
              arm=-18, arm2=-4, arm_base=-6, arm2_at=0.1, arm_at=0.2, arm_skew=0.04, arm_lag=0.08, follow=0.5, fold=-12, fold_at=-0.15,
              arm_out=-10, arm_out_roll=2, claw=8, claw_lag=0.05)
PROFILE['gaits'] = {
    2: dict(COMMON, name='walk', kind='walk', ticks=12, speed=15,
            touchdown={'LH': 0.0, 'LF': 0.2, 'RH': 0.5, 'RF': 0.7}, duty={'LH': 0.31, 'LF': 0.31, 'RH': 0.31, 'RF': 0.31}),
    3: dict(COMMON, name='tired walk', kind='walk', ticks=16, speed=11,
            touchdown={'LH': 0.0, 'LF': 0.2, 'RH': 0.5, 'RF': 0.7}, duty={'LH': 0.3, 'LF': 0.3, 'RH': 0.3, 'RF': 0.3},
            height=0, tilt=11, roll=5, shift=7, bob=4, arm=-9, arm_out=-12, follow=1.0, arm_lag=0.14, fold=-8),
    4: dict(COMMON, name='run', kind='trot', ticks=10, speed=38,
            touchdown={'LF': 0.0, 'RH': 0.0, 'RF': 0.5, 'LH': 0.5}, duty={'LH': 0.14, 'LF': 0.14, 'RH': 0.14, 'RF': 0.14},
            height=0, tilt=9, bob=5, yaw=4, arm=-18, arm_out=-8, fold=-40),
}


IDLE = dict(ticks=40, breath=0.7, sway=1.2, lean=1.1, arm=6.0, arm2=2.0, arm_out=3.0, elbow=9.0, claw=6.0, lag=0.1)


def idle_pose(rig, phase, hist):
    """One tick of the calm idle: the trunk breathes and settles, the log arms and the claws hang from it and follow late
    with small sways; the root legs stay where the rest pose put them (their hips counter the trunk's turn)."""
    rest, c = rig.rest, IDLE
    pose = [list(v) for v in rest]
    pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
    breath = harm(phase, (1.0, 1, 0.0), (0.25, 2, 0.05))
    pose[1][6] = rest[1][6] + c['sway'] * harm(phase, (1, 1, 0.2))
    pose[1][7] = rest[1][7] - c['breath'] * breath
    turn = rot([c['lean'] * harm(phase, (1, 1, 0.02)), c['lean'] * harm(phase, (1, 1, 0.3)), c['lean'] * harm(phase, (1, 1, 0.12))])
    set_rot(pose, 1, mul(mmd.rot_matrix(*rest[1][3:6]), turn), hist)
    for hip in (12, 15, 18, 21):            # the legs stand still on the floor while the trunk turns over them
        set_rot(pose, hip, mul(tr(turn), mmd.rot_matrix(*rest[hip][3:6])), hist)
    for key, (shoulder, elbow, side) in ARMS.items():
        d = 0.0 if key == 'R' else 0.07
        swing = c['arm'] * harm(phase, (1, 1, d + c['lag'])) + c['arm2'] * harm(phase, (1, 2, d + c['lag'] + 0.1)) \
            + c['arm'] * 0.5 * harm(phase, (1, 1, d + c['lag'] + 0.35))
        out = side * c['arm_out'] * harm(phase, (1, 1, d + c['lag'] + 0.25))
        late = c['elbow'] * harm(phase, (1, 1, d + 2 * c['lag'] + 0.05)) + c['arm2'] * harm(phase, (1, 2, d + 2 * c['lag'] + 0.2))
        set_rot(pose, shoulder, mul(mmd.rot_matrix(*rest[shoulder][3:6]), rot([swing, 0, out])), hist)
        set_rot(pose, elbow, mul(mmd.rot_matrix(*rest[elbow][3:6]), rot([late, 0, 0])), hist)
    for key, (a, b, c3, side) in CLAWS.items():
        for k, bone in enumerate((a, b, c3)):
            lag = c['lag'] * (k + 2) + (0.0 if key == 'R' else 0.06)
            d = c['claw'] * (1 + 0.3 * k) * harm(phase, (1, 1, 0.1 + lag)) + 0.4 * c['claw'] * harm(phase, (1, 2, 0.3 + lag))
            e = 0.6 * c['claw'] * harm(phase, (1, 1, 0.35 + lag))
            set_rot(pose, bone, mul(mmd.rot_matrix(*rest[bone][3:6]), rot([d, 0, side * e])), hist)
    return pose


def with_idle(result, skeleton):
    """The calm idle written over slot 0 (and slot 33, which plays the same pose list) of a built model."""
    n = len(skeleton)
    model = mmd.MMD.parse(result, n)
    model.type = PROFILE['species']
    base = mmd.MMD.parse(result, n)
    base.type = PROFILE['species']
    rig = quadruped.Rig(base, skeleton, PROFILE)
    hist = {}
    ticks = IDLE['ticks']
    frames = [idle_pose(rig, t / ticks, hist) for t in range(ticks)]
    frames.append([list(b) for b in frames[0]])
    frames = [[[round(x) for x in bone] for bone in pose] for pose in frames]
    for slot in (0, 33):
        events = [(t, kind, e) for t, kind, e in animsheet.slot_frames(base, n, slot)[2]]
        index = model.anims.table[slot]
        model.anims.anims[index] = mmd.encode_anim(frames, n, loop_sample=0, events=events, tol=1)
    out = model.build()
    assert mmd.MMD.parse(out, n).tmd.build() == base.tmd.build()
    return out


def build(data, skeleton):
    result, proof = quadruped.build(data, skeleton, PROFILE)
    result = with_idle(result, skeleton)
    proof['changed_slots'] = sorted(proof['changed_slots'] + [0, 33])
    proof['storage'] = motionstorage.require(result, len(skeleton))
    proof['output_sha256'] = hashlib.sha256(result).hexdigest()
    return result, proof


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/272-woodmon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
