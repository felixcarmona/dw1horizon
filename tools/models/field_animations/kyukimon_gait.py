"""Kyukimon's field walk, tired walk and run (species 322, slots 2, 3 and 4) as one body on planted feet.

Kyukimon is a hunched fox-warrior: a body (bone 1) pitched forward, the hips (2) under it with the legs (thigh, shin,
ankle, toe: 3-4-5-6 on the side x > 0, 12-13-14-15 on x < 0) and the long plumed tail (7-11, five segments streaming
backwards), above them the chest (22) with the head and its mane (23), two tiny wing spikes (24-25) and the strap round
the shoulders (26), and the two arms hung from the body: upper arm, forearm and the hand with its long blade (16-17-18
right, 19-20-21 left). Forward is -z.

What was wrong. The chibi build keeps the import's field clips, retargeted, and only the legs of them were rewritten:
in the walk, the tired walk and the run every bone above the hips (body, chest, shoulders, arms, tail) plays the idle's
own loop, copied tick by tick (their rotation ranges equal the idle's to a tenth of a degree), while the head, the
hands, the wing spikes and the strap never move at all. So the legs stride on a cycle of their own and the upper body
sways on another, 74 ticks long, that has nothing to do with them: it looks static and unrelated to the feet. The legs
themselves slid their soles 28 % (walk), 20 % (tired) and 49 % (run) of the travel on average, 136 % / 72 % / 180 % at
worst, and the run kept both feet within 13-18 units of the floor with a 73-tick cycle that was nearly the idle pose.

What the clips are now. One gait phase drives the whole body. `quadruped.py` plants each foot (two-bone solve on thigh
and shin, the sole flat on the floor, the foot keeping its own outward splay) and the two legs step at half a cycle;
`body` writes everything above them from the same phase: the hips turn and roll against the body, the body and the
chest turn against the hips one after the other (the chest a little later: the spine winds and unwinds), the arms swing
from the shoulders against the legs on their sides with the forearm and the blade late, the head steadies against the
chest and follows late, the strap and the wing spikes trail, and the tail's five segments each follow the one before it
(a wave runs down it) while its root turns against the hips. Every clip is two cycles long: cycle B differs from cycle
A (one leg lifts higher, lands a touch earlier, the body sinks and leans a little more) and the clip eases from one to
the other and back so that no two steps are alike and the loop still closes; the upper bones then follow through a loose
spring each. The idle (slot 0, alias 33) is the chibi build's own and is left as it is.

`build` runs the chibi reshaping first and writes the three clips on its result; nothing is stored but the overlay's
recipe name in content/models/imports/species.py. Offline: `python3 -m tools.models.field_animations.kyukimon_gait
--source EDIT.MMD --out AFTER.MMD` with EDIT.MMD the model `tools/models/edit.py get 322` makes with its slot aliases
applied (the build's own input).
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

SPECIES = 322
TAU = 2 * math.pi
DEG = 4096 / 360
UPPER, HIPS, CHEST, HEAD, STRAP = 1, 2, 22, 23, 26
WINGS = (24, 25)
TAIL = (7, 8, 9, 10, 11)
# shoulder, forearm, hand (with the blade) and the side's sign in x
ARMS = {'R': (16, 17, 18, 1), 'L': (19, 20, 21, -1)}
LEGS = {'RH': (3, 4, 5, 1, False), 'LH': (12, 13, 14, -1, False)}
TOE_OF = {'RH': 6, 'LH': 15}


def harm(phase, *terms):
    """A sum of cosines: terms are (amplitude, rate, delay in cycles)."""
    return sum(a * math.cos(TAU * rate * (phase - delay)) for a, rate, delay in terms)


def body(rig, cfg, phase, pose, hist):
    """Height, sway and the turns of hips, body and chest, the head, the arms, the tail, the strap and the wing spikes
    from one phase; closed loops."""
    c, W0 = cfg, rig.still
    rest = rig.rest
    bob = harm(phase, (c['bob'], 2, c['high']), (c['bob2'], 4, c['high'] + 0.03), (c['bob_side'], 1, c['high'] + 0.2))
    pose[UPPER][7] = rest[UPPER][7] - c['height'] - bob
    pose[UPPER][6] = rest[UPPER][6] + harm(phase, (c['shift'], 1, c['roll_at']), (c['shift2'], 3, c['roll_at'] + 0.07))
    # the hips: pitch twice a cycle, yaw and roll once
    hp = c['hip_tilt'] + harm(phase, (c['hip_pitch'], 2, c['pitch_at']), (c['hip_pitch1'], 1, c['pitch_at'] + 0.12))
    hy = -harm(phase, (c['hip_yaw'], 1, c['yaw_at']), (c['hip_yaw2'], 3, c['yaw_at'] + 0.05))   # the hip of the leg that lands leads
    hr = harm(phase, (c['hip_roll'], 1, c['roll_at'] + 0.5), (c['hip_roll2'], 3, c['roll_at'] + 0.57))
    # the body turns against the hips; the chest follows it a little later and goes on a little further
    lag = c['lag']
    breath = c['breath'] * math.sin(TAU * (phase - 0.1))
    up = c['lean'] + harm(phase - lag, (c['pitch'], 2, c['pitch_at']), (c['pitch1'], 1, c['pitch_at'] + 0.12)) + breath
    uy = -c['counter'] * hy + harm(phase - lag, (c['yaw'], 1, c['yaw_at'] + 0.1))
    ur = harm(phase - lag, (c['roll'], 1, c['roll_at']), (c['roll2'], 3, c['roll_at'] + 0.06))
    lag2 = lag + c['chest_lag']
    cp = c['chest_lean'] + harm(phase - lag2, (c['chest_pitch'], 2, c['pitch_at']), (c['chest_pitch1'], 1, c['pitch_at'] + 0.12)) + 0.6 * breath
    cy = -c['chest_counter'] * hy + harm(phase - lag2, (c['chest_yaw'], 1, c['yaw_at'] + 0.1))
    cr = harm(phase - lag2, (c['chest_roll'], 1, c['roll_at']))
    Wt = {0: [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}

    def put(bone, parent, delta):
        Wt[bone] = mul(delta, rig.R(W0, bone))
        set_rot(pose, bone, mul(tr(Wt[parent]), Wt[bone]), hist)
    Wt[UPPER] = mul(rot([up, uy, ur]), rig.R(W0, UPPER))
    set_rot(pose, UPPER, Wt[UPPER], hist)
    put(HIPS, UPPER, rot([hp, hy, hr]))
    D1 = rot([up, uy, ur])
    put(CHEST, UPPER, rot([up + cp, uy + cy, ur + cr]))
    # the head keeps most of its gaze: it follows the chest by 1 - `steady`, and what it does follows late
    nod = harm(phase - c['nod_lag'], (c['nod'], 2, c['nod_at']), (c['nod2'], 1, c['nod_at'] + 0.1))
    look = c['look'] * harm(phase, (1, 1, c['look_at']))
    top = up + cp
    put(HEAD, CHEST, rot([top - c['steady'] * (top - c['lean'] - c['chest_lean']) - c['head'] + nod,
                          (uy + cy) * 0.55 + look + c['head_yaw'] * harm(phase - 2 * lag2, (1, 1, c['yaw_at'] + 0.1)),
                          (ur + cr) * 0.6 + c['head_roll'] * harm(phase - 2 * lag2, (1, 1, c['roll_at'] + 0.2))]))
    # the arms: the shoulder swings against the leg on its side, the forearm and the blade follow late
    for side, (sh, el, hand, sd) in ARMS.items():
        at = c['arm_at'] + (0.5 if side == 'R' else 0.0)    # the arm on the side of the leg that lands swings back
        swing = c['arm'] * harm(phase, (1, 1, at), (c['arm2'], 2, at + 0.1))
        out = c['arm_out'] * sd + c['arm_roll'] * sd * harm(phase, (1, 2, c['arm_at'] + 0.05))
        sh_d = mul(D1, rot([swing + c['arm_lift'], 0, out]))
        Wt[sh] = mul(sh_d, rig.R(W0, sh))
        set_rot(pose, sh, mul(tr(Wt[UPPER]), Wt[sh]), hist)
        flex = c['elbow'] * harm(phase, (1, 1, at + c['elbow_lag']), (c['elbow2'], 2, at + c['elbow_lag'] + 0.1))
        pose[el][3] = rest[el][3] + round((flex - c['elbow_extra']) * DEG)
        wrist = c['wrist'] * harm(phase, (1, 1, at + 2 * c['elbow_lag']))
        pose[hand][3] = rest[hand][3] + round((0.5 * flex + wrist - c['wrist_hold']) * DEG)
    # the tail: its root turns against the hips, and each segment follows the one before it a little later
    for k, b in enumerate(TAIL):
        d = c['tail_lag'] * k
        pitch = c['tail_out'] + c['tail_pitch'] * harm(phase - d, (1, 2, c['pitch_at'] + 0.1)) + c['tail_pitch1'] * harm(phase - d, (1, 1, 0.3))
        yaw = c['tail_yaw'] * harm(phase - d, (1, 1, c['yaw_at'] + 0.5))
        pose[b][3] = rest[b][3] + round(pitch * DEG)
        pose[b][4] = rest[b][4] + round(yaw * DEG)
    # the strap and the wing spikes trail the chest
    pose[STRAP][3] = rest[STRAP][3] + round((c['strap'] * harm(phase - c['strap_lag'], (1, 2, c['pitch_at'])) + c['strap_out']) * DEG)
    for sd, b in zip((1, -1), WINGS):
        pose[b][5] = rest[b][5] + round(sd * (c['wing'] * harm(phase - c['strap_lag'], (1, 2, c['pitch_at'])) + c['wing_out']) * DEG)


PROFILE = dict(
    species=SPECIES, name='Kyukimon', source=None,
    parents=[-1, 0, 1, 2, 3, 4, 5, 2, 7, 8, 9, 10, 2, 12, 13, 14, 1, 16, 17, 1, 19, 20, 1, 22, 22, 22, 22],
    pelvis=UPPER, chest=None, neck=None, head=HEAD, tail=(), loose=(),
    legs=LEGS, pole_world=True, rest_plane=True, pole={False: [0.3, 0.0, -1.0]},
    paw_rest={'LH': [0, 0, 0], 'RH': [0, 0, 0]},     # filled from the rig below
    sole={False: [0, 0, 0]},                            # filled from the rig below
    reach={'front': 0, 'hind': 0},
    fold={False: 75}, clear=2,
    speed_range={0: (0, 0), 2: (15, 31), 3: (10, 20), 4: (35, 52)},
    body=body, floor=3, stance_slip=0.2,
    gaits={},
)
COMMON = dict(
    kind='walk', snap=False, arc=0.5, clear_ease=0.1, world_ease=True, fold_soft=10, slip=0.0, steps=('LH', 'RH'),
    reach={'front': 0, 'hind': 0}, lift={'front': 0, 'hind': 30}, curl={'front': 0, 'hind': 0}, peel={'front': 0, 'hind': 0},
    out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 0}, track={'front': 0, 'hind': 10}, heel=0,
    high=0.1, bob=3, bob2=0.8, bob_side=0.5, height=-22, shift=5, shift2=0.8, roll_at=0.3,
    hip_tilt=0, hip_pitch=1, hip_pitch1=0.3, hip_yaw=4, hip_yaw2=0.5, hip_roll=2, hip_roll2=0.4,
    lean=0, pitch=1.5, pitch1=0.5, pitch_at=0.15, yaw=1, counter=0.9, roll=2.5, roll2=0.5, yaw_at=0.05, lag=0.07, breath=0,
    chest_lag=0.06, chest_lean=0, chest_pitch=1.0, chest_pitch1=0.4, chest_counter=0.6, chest_yaw=1, chest_roll=1.5,
    steady=0.8, head=0, nod=1, nod2=0.5, nod_at=0.2, nod_lag=0.06, look=0, look_at=0.3, head_yaw=0, head_roll=0,
    arm=14, arm2=0, arm_at=0.0, arm_lift=0, arm_out=0, arm_roll=0, elbow=6, elbow2=0, elbow_extra=0, elbow_lag=0.05,
    wrist=0, wrist_hold=0,
    tail_lag=0.05, tail_out=0, tail_pitch=3, tail_pitch1=1, tail_yaw=3,
    strap=3, strap_lag=0.1, strap_out=0, wing=6, wing_out=0,
)

FOLLOW = {16: (0.55, 0.5), 17: (0.6, 0.45), 18: (0.5, 0.45),          # right arm: shoulder, forearm, hand
          19: (0.55, 0.5), 20: (0.6, 0.45), 21: (0.5, 0.45),          # left arm
          HEAD: (0.7, 0.55), STRAP: (0.45, 0.35), 24: (0.4, 0.3), 25: (0.4, 0.3),
          7: (0.6, 0.5), 8: (0.55, 0.45), 9: (0.5, 0.4), 10: (0.45, 0.35), 11: (0.4, 0.3)}   # (rad per tick, damping)


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
            seq = [out[i][b][ch] for i in range(2 * ticks)]
            mixed = spring(seq, rate, damping)
            for i in range(2 * ticks):
                out[i][b][ch] = seq[i] + (mixed[i] - seq[i]) * follow
    closing = [list(v) for v in out[0]]
    closing[0][8] = -round(speed * 2 * ticks)
    out.append(closing)
    return out


PROFILE['gaits'] = {
    2: dict(COMMON, name='walk', ticks=16, speed=18,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.58, 'RH': 0.58}, lift={'front': 0, 'hind': 30},
            height=-4, high=0.27, bob=8, bob2=1.0, bob_side=1.0, lean=2, hip_yaw=7, hip_roll=3.5, roll=3, arm=14, elbow=8, elbow_extra=-10),
    3: dict(COMMON, name='tired walk', ticks=22, speed=13,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.62, 'RH': 0.62}, height=-10, high=0.3, bob=6, lift={'front': 0, 'hind': 24},
            peel={'front': 0, 'hind': -6}, lean=10, head=-8, arm=7, elbow=3, hip_yaw=3.5, hip_roll=3, shift=8, roll=3.5, bob_side=1.2, elbow_extra=-10),
    4: dict(COMMON, name='run', kind='trot', ticks=14, speed=36,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.32, 'RH': 0.32}, height=-8, high=0.42, arc=0.6, clear_ease=0.05, lift={'front': 0, 'hind': 50},
            bob=11, bob2=1.5, lean=12, head=6, arm=22, elbow=12, elbow_extra=-15, hip_yaw=7, hip_roll=3, roll=3),
}
OTHER = {      # cycle B: what changes from cycle A, as factors on A's numbers or the leg settings
    2: dict(scale=dict(bob=1.15, lean=1.15, hip_yaw=1.12, roll=1.1, arm=0.85), leg_lift={'LH': 0.9, 'RH': 1.08},
            touchdown={'LH': 0.0, 'RH': 0.52}, settle=2.0, heel=4),
    3: dict(scale=dict(bob=1.15, lean=0.95, arm=1.2, roll=1.1, shift=1.1), leg_lift={'LH': 0.88, 'RH': 1.1},
            touchdown={'LH': 0.0, 'RH': 0.51}, settle=2.0, heel=4),
    4: dict(scale=dict(lean=1.1, arm=0.9, hip_yaw=1.1), leg_lift={'LH': 0.7, 'RH': 1.0}, touchdown={'LH': 0.0, 'RH': 0.5}, settle=2.0, heel=5),
}
for slot, spec in OTHER.items():
    cfg = PROFILE['gaits'][slot]
    other = {k: v for k, v in spec.items() if k != 'scale'}
    other.update({k: cfg[k] * f for k, f in spec['scale'].items()})
    cfg.update(cycles=2, compose=compose, other=other)


def prepare(model, skeleton):
    """Fill what is read off the rig: each foot's toe direction and the pivot of the sole (the toe point)."""
    import animsheet
    pose = animsheet.slot_frames(model, len(skeleton), 0)[0][0]
    for name, toe in TOE_OF.items():
        PROFILE['paw_rest'][name] = list(pose[toe][6:9])
    PROFILE['sole'][False] = list(pose[TOE_OF['RH']][6:9])


def build(data, skeleton):
    """The reshaped model with the three clips written on it -> (bytes, proof): chibi's proof (its species patch reaches
    the record) with the clips' checks."""
    from tools.models.field_animations import chibi
    reshaped, proof = chibi.build(data, skeleton)
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
    skeleton = json.loads((ROOT / 'content/species/322-kyukimon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof['gait'], indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
