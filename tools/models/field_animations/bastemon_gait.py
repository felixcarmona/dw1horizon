"""Bastemon's field idle, walk, tired walk and run (species 432, slots 0, 2, 3 and 4) as one body on planted feet.

Bastemon is a cat-like humanoid on 26 bones: a body (bone 1) with the hips (11) under it, the legs (thigh, shin, ankle,
foot: 12-13-14-15 on the side x > 0, 16-17-18-19 on x < 0), the head (8) with the hair hanging behind it (9-10), the two
arms hung from the body (2-3-4 on x < 0, 5-6-7 on x > 0: shoulder cap, upper arm, forearm with the hand) and two long
ribbons hung from the hips (20-21-22 on x < 0, 23-24-25 on x > 0). Forward is -z.

What was wrong. The arms, the head and the loose parts barely moved against the stride: the stills of the walk and the
run looked almost static and stiff, and the run was faster than the natives' range.

What the clips are now. One gait phase drives the whole body. `quadruped.py` plants each foot (two-bone solve on thigh and
shin, the sole flat on the floor) and the two legs step at half a cycle; `body` writes everything above them from the same
phase: the hips turn and roll against the body, the body winds against the hips, the arms swing from the shoulders against
the legs on their sides with a soft elbow that lags, the head follows late and steady, the hair and the two ribbons each
follow the part before them (a wave runs down each chain) and are then passed through a loose spring, and in the run the
ribbons stream out behind. Every clip is two cycles long: cycle B differs from cycle A and the clip eases from one to the
other and back so that no two steps are alike and the loop still closes. The idle is a loop of 60 ticks (breathing, the
weight shifting between the feet, the head looking about, the hair and the ribbons drifting) with no travel.

`build` runs the species' existing overlay (chibi reshaping, then celebrations) first and writes the four clips on its result;
nothing is stored but the overlay's recipe name in content/models/imports/species.py. Offline: `python3 -m
tools.models.field_animations.bastemon_gait --source EDIT.MMD --out AFTER.MMD` with EDIT.MMD the model `tools/models/edit.py
get 432` makes (the build's own input).
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
from tools.models.field_animations import quadruped  # noqa: E402
from tools.models.field_animations.quadruped import mul, tr, rot, set_rot  # noqa: E402

SPECIES = 432
TAU = 2 * math.pi
DEG = 4096 / 360
UPPER, HIPS, HEAD = 1, 11, 8
HAIR = (9, 10)
# the arms: shoulder cap, upper arm, forearm (with the hand) and the side's sign in x
ARMS = {'R': (5, 6, 7, 1), 'L': (2, 3, 4, -1)}
RIBBONS = {'R': ((23, 24, 25), 1), 'L': ((20, 21, 22), -1)}
LEGS = {'RH': (12, 13, 14, 1, False), 'LH': (16, 17, 18, -1, False)}
TOE_OF = {'RH': 15, 'LH': 19}


def harm(phase, *terms):
    """A sum of cosines: terms are (amplitude, rate, delay in cycles)."""
    return sum(a * math.cos(TAU * rate * (phase - delay)) for a, rate, delay in terms)


def body(rig, cfg, phase, pose, hist):
    """Height, sway and the turns of hips and body, the head, the arms, the hair and the ribbons from one phase; closed loops."""
    c, W0 = cfg, rig.still
    rest = rig.rest
    bob = harm(phase, (c['bob'], 2, c['high']), (c['bob2'], 4, c['high'] + 0.03), (c['bob_side'], 1, c['high'] + 0.2))
    pose[UPPER][7] = rest[UPPER][7] - c['height'] - bob
    pose[UPPER][6] = rest[UPPER][6] + harm(phase, (c['shift'], 1, c['roll_at']), (c['shift2'], 3, c['roll_at'] + 0.07))
    hp = c['hip_tilt'] + harm(phase, (c['hip_pitch'], 2, c['pitch_at']), (c['hip_pitch1'], 1, c['pitch_at'] + 0.12))
    hy = -harm(phase, (c['hip_yaw'], 1, c['yaw_at']), (c['hip_yaw2'], 3, c['yaw_at'] + 0.05))
    hr = harm(phase, (c['hip_roll'], 1, c['roll_at'] + 0.5), (c['hip_roll2'], 3, c['roll_at'] + 0.57))
    lag = c['lag']
    breath = c['breath'] * math.sin(TAU * (phase - 0.1))
    up = c['lean'] + harm(phase - lag, (c['pitch'], 2, c['pitch_at']), (c['pitch1'], 1, c['pitch_at'] + 0.12)) + breath
    uy = -c['counter'] * hy + harm(phase - lag, (c['yaw'], 1, c['yaw_at'] + 0.1))
    ur = harm(phase - lag, (c['roll'], 1, c['roll_at']), (c['roll2'], 3, c['roll_at'] + 0.06)) + harm(phase - 2 * lag, (c['wave'], 1, c['roll_at'] + 0.25))
    Wt = {0: [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}

    def put(bone, parent, delta):
        Wt[bone] = mul(delta, rig.R(W0, bone))
        set_rot(pose, bone, mul(tr(Wt[parent]), Wt[bone]), hist)
    Wt[UPPER] = mul(rot([up, uy, ur]), rig.R(W0, UPPER))
    set_rot(pose, UPPER, Wt[UPPER], hist)
    put(HIPS, UPPER, rot([hp, hy, hr]))
    D1 = rot([up, uy, ur])
    nod = harm(phase - c['nod_lag'], (c['nod'], 2, c['nod_at']), (c['nod2'], 1, c['nod_at'] + 0.1))
    look = c['look'] * harm(phase, (1, 1, c['look_at']))
    put(HEAD, UPPER, rot([up - c['steady'] * (up - c['lean']) - c['head'] + nod,
                          uy * 0.55 + look + c['head_yaw'] * harm(phase - 2 * lag, (1, 1, c['yaw_at'] + 0.1)),
                          ur * 0.6 + c['head_roll'] * harm(phase - 2 * lag, (1, 1, c['roll_at'] + 0.2))]))
    # the hair: each joint follows the one before it, swinging against the head's turn and bobbing with the steps
    for k, b in enumerate(HAIR):
        d = c['hair_lag'] * (k + 1)
        pose[b][3] = rest[b][3] + round((c['hair_out'] * (0.6 + 0.4 * k) + c['hair_pitch'] * (1 + 0.5 * k) * harm(phase - d, (1, 2, c['pitch_at'] + 0.1))
                                         + c['hair_pitch1'] * harm(phase - d, (1, 1, 0.3))) * DEG)
        pose[b][4] = rest[b][4] + round(c['hair_yaw'] * (1 + 0.6 * k) * harm(phase - d, (1, 1, c['yaw_at'] + 0.5)) * DEG)
        pose[b][5] = rest[b][5] + round(c['hair_roll'] * (1 + 0.6 * k) * harm(phase - d - 0.06, (1, 1, c['yaw_at'] + 0.25)) * DEG)
    # the arms: the upper arm swings against the leg on its side, the forearm follows late; the shoulder cap shrugs a little
    for side, (cap, up_arm, fore, sd) in ARMS.items():
        at = c['arm_at'] + (0.5 if side == 'R' else 0.0)
        put(cap, UPPER, rot([c['shrug'] * harm(phase, (1, 1, at + 0.1)), 0, sd * c['shrug_roll'] * harm(phase, (1, 2, at))]))
        swing = c['arm'] * harm(phase, (1, 1, at), (c['arm2'], 2, at + 0.1))
        out = c['arm_out'] * sd + c['arm_roll'] * sd * harm(phase, (1, 2, c['arm_at'] + 0.05))
        spin = sd * c['arm_spin'] * harm(phase, (1, 1, at + c['elbow_lag']))
        put(up_arm, cap, rot([swing + c['arm_lift'], spin, out]))
        flex = c['elbow'] * harm(phase, (1, 1, at + c['elbow_lag']), (c['elbow2'], 2, at + c['elbow_lag'] + 0.1))
        pose[fore][3] = rest[fore][3] + round((flex - c['elbow_extra']) * DEG)
        pose[fore][4] = rest[fore][4] + round(sd * c['wrist'] * harm(phase, (1, 1, at + 2 * c['elbow_lag'])) * DEG)
        pose[fore][5] = rest[fore][5] + round(sd * c['wrist_roll'] * harm(phase, (1, 1, at + 3 * c['elbow_lag'])) * DEG)
    # the ribbons: they hang from the hips, trail the body, stream out in the run and ripple down each chain
    for side, (chain, sd) in RIBBONS.items():
        for k, b in enumerate(chain):
            d = c['rib_lag'] * k
            pose[b][3] = rest[b][3] + round((c['rib_out'] * c['rib_fall'][k] + c['rib_pitch'] * harm(phase - d, (1, 2, c['pitch_at'] + 0.1))
                                             + c['rib_pitch1'] * harm(phase - d, (1, 1, 0.3))) * DEG)
            pose[b][4] = rest[b][4] + round((sd * c['rib_spread'] * c['rib_fall'][k] + c['rib_yaw'] * harm(phase - d, (1, 1, c['yaw_at'] + 0.5 + (side == 'R') * 0.25))) * DEG)
            pose[b][5] = rest[b][5] + round(c['rib_roll'] * harm(phase - d - 0.08, (1, 1, c['yaw_at'] + 0.35 + (side == 'R') * 0.5)) * DEG)


PROFILE = dict(
    species=SPECIES, name='Bastemon', source=None,
    parents=[-1, 0, 1, 2, 3, 1, 5, 6, 1, 8, 9, 1, 11, 12, 13, 14, 11, 16, 17, 18, 11, 20, 21, 11, 23, 24],
    pelvis=UPPER, chest=None, neck=None, head=HEAD, tail=(), loose=(),
    legs=LEGS, pole_world=True, rest_plane=True, pole={False: [0.3, 0.0, -1.0]},
    paw_rest={'LH': [0, 0, 0], 'RH': [0, 0, 0]},
    sole={False: [0, 0, 0]},
    reach={'front': 0, 'hind': 0},
    fold={False: 75}, clear=2,
    speed_range={0: (0, 0), 2: (15, 31), 3: (10, 20), 4: (35, 52)},
    body=body, floor=3, stance_slip=0.2, tol=4,
    gaits={},
)
COMMON = dict(
    kind='walk', snap=False, arc=0.5, clear_ease=0.1, world_ease=True, fold_soft=10, slip=0.0, steps=('LH', 'RH'),
    reach={'front': 0, 'hind': 0}, lift={'front': 0, 'hind': 30}, curl={'front': 0, 'hind': 0}, peel={'front': 0, 'hind': 0},
    out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 0}, track={'front': 0, 'hind': 0}, heel=0,
    high=0.1, bob=3, bob2=0.8, bob_side=0.5, height=-22, shift=5, shift2=0.8, roll_at=0.3,
    hip_tilt=0, hip_pitch=1, hip_pitch1=0.3, hip_yaw=4, hip_yaw2=0.5, hip_roll=2, hip_roll2=0.4,
    lean=0, pitch=1.5, pitch1=0.5, pitch_at=0.15, yaw=1, counter=0.9, roll=2.5, roll2=0.5, yaw_at=0.05, lag=0.07, breath=0,
    steady=0.8, head=0, nod=1, nod2=0.5, nod_at=0.2, nod_lag=0.06, look=0, look_at=0.3, head_yaw=0, head_roll=0,
    arm=14, arm2=0, arm_at=0.0, arm_lift=0, arm_out=0, arm_roll=0, arm_spin=0, shrug=0, shrug_roll=0,
    elbow=6, elbow2=0, elbow_extra=0, elbow_lag=0.05, wrist=0, wrist_roll=0,
    hair_lag=0.07, hair_out=0, hair_pitch=2, hair_pitch1=1, hair_yaw=2, hair_roll=2,
    wave=0, rib_lag=0.07, rib_out=0, rib_fall=(1, 0.6, 0.3), rib_spread=0, rib_pitch=2, rib_pitch1=1, rib_yaw=3, rib_roll=3,
)

FOLLOW = {2: (0.55, 0.5), 3: (0.55, 0.5), 4: (0.5, 0.45),               # left arm: cap, upper arm, forearm
          5: (0.55, 0.5), 6: (0.55, 0.5), 7: (0.5, 0.45),               # right arm
          HEAD: (0.7, 0.55), 9: (0.5, 0.35), 10: (0.42, 0.3),            # head, hair
          20: (0.5, 0.4), 21: (0.42, 0.35), 22: (0.36, 0.3),             # ribbons
          23: (0.5, 0.4), 24: (0.42, 0.35), 25: (0.36, 0.3)}             # (rad per tick, damping)


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


def unwrap(values):
    """Euler angles (4096 to a turn) without the jump at the turn."""
    out = [values[0]]
    for v in values[1:]:
        out.append(out[-1] + (v - out[-1] + 2048) % 4096 - 2048)
    return out


def blend(a, b, w):
    out = []
    for ba, bb in zip(a, b):
        row = list(ba)
        for i in range(3, 6):
            d = (bb[i] - ba[i] + 2048) % 4096 - 2048
            row[i] = ba[i] + d * w
        for i in range(6, 9):
            row[i] = ba[i] + (bb[i] - ba[i]) * w
        out.append(row)
    return out


def compose(rig, cfg, frames_a):
    """Two cycles from cycle A (`frames_a`) and the cycle the gait's `other` settings give, eased into each other."""
    ticks, speed = cfg['ticks'], cfg['speed']
    frames_b, _ = quadruped.gait(rig, dict(cfg, **cfg['other']))
    out = []
    for i in range(2 * ticks):
        w = 0.5 - 0.5 * math.cos(math.pi * i / ticks)
        pose = blend(frames_a[i % ticks], frames_b[i % ticks], w)
        pose[0][8] = -round(speed * i)
        out.append(pose)
    follow = cfg.get('follow', 1.0)
    for b, (rate, damping) in FOLLOW.items():
        for ch in (3, 4, 5):
            seq = unwrap([out[i][b][ch] for i in range(2 * ticks)]) if ch < 6 else [out[i][b][ch] for i in range(2 * ticks)]
            mixed = spring(seq, rate, damping)
            for i in range(2 * ticks):
                out[i][b][ch] = seq[i] + (mixed[i] - seq[i]) * follow
    closing = [list(v) for v in out[0]]
    closing[0][8] = -round(speed * 2 * ticks)
    out.append(closing)
    return out


def compose_idle(rig, cfg, frames):
    """The idle's one cycle with its loose parts passed through a loose spring each."""
    ticks = cfg['ticks']
    out = [[list(b) for b in pose] for pose in frames[:ticks]]
    for b, (rate, damping) in FOLLOW.items():
        for ch in (3, 4, 5):
            seq = unwrap([out[i][b][ch] for i in range(ticks)])
            mixed = spring(seq, rate, damping)
            for i in range(ticks):
                out[i][b][ch] = round(mixed[i])
    out.append([list(v) for v in out[0]])
    return out


PROFILE['gaits'] = {
    0: dict(COMMON, name='idle', track={'front': 0, 'hind': 38}, ticks=60, speed=0, steps=(), touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 1.0, 'RH': 1.0},
            height=0, bob=0, bob2=0, bob_side=0, shift=5, shift2=0, hip_yaw=2, hip_yaw2=0, hip_roll=3, hip_roll2=0, hip_pitch=0.5,
            hip_pitch1=0, roll=3, roll2=0, wave=2, yaw=1.5, counter=0.5, lean=2, pitch=0.6, pitch1=0, breath=1.2, nod=0.3, nod2=0, look=3, look_at=0.3,
            head_yaw=3, head_roll=1, arm=3, arm_out=-4, elbow=4, wrist=3, wrist_roll=3, shrug=2, shrug_roll=1.5,
            hair_out=8, hair_pitch=2.5, hair_pitch1=1.5, hair_yaw=2.5, hair_roll=1.5, hair_lag=0.1,
            rib_pitch=3, rib_pitch1=1.5, rib_yaw=4, rib_roll=2, rib_lag=0.1, compose=compose_idle, cycles=1),
    2: dict(COMMON, name='walk', track={'front': 0, 'hind': 14}, ticks=12, speed=15, clear=4,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.6, 'RH': 0.6}, lift={'front': 0, 'hind': 28}, arc=0.75,
            height=-30, high=0.27, bob=8, bob2=1.0, bob_side=1.0, lean=2, hip_yaw=10, hip_roll=5, roll=4, wave=3, arm=30, elbow=10, elbow_extra=-20,
            arm_out=2, arm_lift=-8, arm_spin=3, wrist=6, wrist_roll=5, shrug=2, shrug_roll=2, head=3, head_yaw=4, head_roll=2, nod=1,
            hair_out=12, hair_pitch=6, hair_pitch1=2, hair_yaw=6, hair_roll=4, hair_lag=0.09,
            rib_out=20, rib_spread=12, rib_fall=(1, 0.5, 0.2), rib_pitch=5, rib_pitch1=2, rib_yaw=3, rib_roll=2, rib_lag=0.09),
    3: dict(COMMON, name='tired walk', track={'front': 0, 'hind': 18}, ticks=14, speed=10.5, clear=4, arc=0.9,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.62, 'RH': 0.62}, height=-31, high=0.3, bob=5, lift={'front': 0, 'hind': 18},
            lean=12, head=16, arm=8, elbow=3, elbow_extra=-6, hip_yaw=5, hip_roll=4.5, shift=7, roll=4.5, wave=3, bob_side=1.2,
            arm_out=0, arm_lift=-6, arm_spin=3, wrist=3, shrug=3, shrug_roll=1, head_yaw=3, head_roll=4,
            hair_out=14, hair_pitch=3, hair_pitch1=1.5, hair_yaw=4, hair_roll=3, hair_lag=0.1,
            rib_out=10, rib_spread=14, rib_fall=(1, 0.5, 0.2), rib_pitch=2, rib_pitch1=1.5, rib_yaw=6, rib_roll=4, rib_lag=0.1),
    4: dict(COMMON, name='run', track={'front': 0, 'hind': 8}, wide={'front': 0, 'hind': 14}, kind='trot', ticks=10, speed=36, clear=4,
            touchdown={'LH': 0.04, 'RH': 0.54}, duty={'LH': 0.36, 'RH': 0.36}, height=-36, high=0.42, arc=1.3, lift_soft=1.15, lift={'front': 0, 'hind': 36},
            peel={'front': 0, 'hind': 6}, heel=6,
            bob=7, bob2=1.5, lean=18, head=10, wave=3, arm=40, elbow=18, elbow_extra=-40, hip_yaw=8, hip_roll=3, roll=3,
            arm_out=-4, arm_lift=-16, arm_spin=5, arm_at=-0.25, wrist=5, shrug=5, shrug_roll=2, head_roll=3,
            hair_out=22, hair_pitch=7, hair_pitch1=2, hair_yaw=5, hair_roll=3, hair_lag=0.12,
            rib_out=30, rib_fall=(1, 0.7, 0.4), rib_spread=12, rib_pitch=5, rib_pitch1=2, rib_yaw=6, rib_roll=4, rib_lag=0.12),
}
OTHER = {
    2: dict(scale=dict(bob=1.2, lean=1.2, hip_yaw=1.15, roll=1.15, arm=0.8, wave=1.5, rib_yaw=1.3, hair_yaw=1.3, head_roll=-0.8), leg_lift={'LH': 0.9, 'RH': 1.08},
            touchdown={'LH': 0.0, 'RH': 0.5}, settle=0.5, heel=3),
    3: dict(scale=dict(bob=1.15, lean=0.95, arm=1.2, roll=1.1, shift=1.1, wave=1.4, rib_yaw=1.25, head_roll=-0.8), leg_lift={'LH': 0.88, 'RH': 1.1},
            touchdown={'LH': 0.0, 'RH': 0.5}, settle=0.5, heel=3),
    4: dict(scale=dict(lean=1.1, arm=0.9, hip_yaw=1.1, wave=1.5, rib_yaw=1.25, head_roll=-0.8), leg_lift={'LH': 0.7, 'RH': 1.0}, touchdown={'LH': 0.04, 'RH': 0.54}, settle=0.3, heel=6),
}
for slot, spec in OTHER.items():
    cfg = PROFILE['gaits'][slot]
    other = {k: v for k, v in spec.items() if k != 'scale'}
    other.update({k: cfg[k] * f for k, f in spec['scale'].items()})
    cfg.update(cycles=2, compose=compose, other=other)


def prepare(model, skeleton):
    """Fill what is read off the rig: each foot's toe direction and the pivot of the sole (the toe point)."""
    pose = animsheet.slot_frames(model, len(skeleton), 0)[0][0]
    for name, toe in TOE_OF.items():
        PROFILE['paw_rest'][name] = list(pose[toe][6:9])
    PROFILE['sole'][False] = list(pose[TOE_OF['RH']][6:9])


def build(data, skeleton):
    """The reshaped model (chibi, then the species' celebrations) with the four clips written on it -> (bytes, proof)."""
    from tools.models.field_animations import celebrations
    reshaped, proof = celebrations.build(data, skeleton)
    exe = mmd.exe()
    kept = exe.skeleton[SPECIES], exe.bone_count[SPECIES]       # the clips are built on this rig, then put back
    try:
        old = mmd.MMD.parse(reshaped, len(skeleton))
        old.type = SPECIES
        exe.skeleton[SPECIES] = skeleton
        exe.bone_count[SPECIES] = len(skeleton)
        prepare(old, skeleton)
        profile = dict(PROFILE, source=hashlib.sha256(reshaped).hexdigest())
        result, gait = quadruped.build(reshaped, skeleton, profile)
    finally:
        exe.skeleton[SPECIES], exe.bone_count[SPECIES] = kept
    proof = dict(proof, preceding_recipe=dict(recipe='celebrations', output_sha256=proof['output_sha256']),
                 output_sha256=gait['output_sha256'], gait=gait,
                 resident_bytes=[gait['storage']['resident_bytes'], gait['storage']['resident_limit']])
    if 'bytes' in proof:
        proof['bytes'] = [proof['bytes'][0], len(result)]
    return result, proof


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/432-bastemon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof['gait'], indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
