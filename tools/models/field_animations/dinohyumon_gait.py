"""Dinohyumon's field gaits (species 308): idle, walk, tired walk and run with planted feet on its own two legs.

Dinohyumon is a lizard warrior with a feather in its headband, a blade in each fist and a broad blade slung across its
back. Bone 1 is the upper body (rest pitched forward 8 degrees) with the shoulders and arms (2-5 right, 9-12 left:
shoulder, upper arm, forearm, fist with its blade), the head 6 with the feather 7 on it, the back blade 8; bone 13 is the
hips under it (it turns the pitch back, so the legs stand upright) with the loincloth 18 and the legs 14-17 right and
19-22 left: thigh, shin, ankle and foot, then the claws. Forward is -z.

The model made by `chibi.py` (the overlay `dinohyumon-chibi`: big head, short thick legs) is what the clips are written
on. Its imported clips drove the legs with rotations from another rig: the feet turned half way round in the walk and
all the way in the run (toe to heel yaw 26 to 167 degrees and -178 to 173), the tired walk slid its soles by 170 % of
the travel, the pelvis dropped 65 units in the run, the root moved by a different step every tick and the arms hardly
moved. Here `quadruped.py` plants each foot (two-bone IK on the thigh and shin, the sole flat on the floor and the foot
keeping its own outward splay), the legs step in turn at half a cycle, and `body` writes everything above them: the
hips turn against the shoulders, the upper body rolls and shifts over the loaded foot, the arms swing as pendulums with
the forearm and the blade late, the head stays level and follows late, and the feather and the loincloth trail.

The character is a wary, light-footed swordsman: the walk leans forward a little with the head forward, the tired walk
is a low drag with the head hung, the run a committed lean with the arms driving and the blades trailing. The idle (96
ticks) keeps both feet planted: the weight rolls from one to the other, the chest breathes, the head looks aside, a
blade hand lifts and turns and the feather and loincloth sway.

`build` runs the chibi reshaping first and writes the four clips on its result; nothing is stored but the overlay's
recipe name in content/models/imports/species.py. Offline: `python3 -m tools.models.field_animations.dinohyumon_gait
--source EDIT.MMD --out AFTER.MMD` with EDIT.MMD the model `tools/models/edit.py get 308` makes.
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

SPECIES = 308
TAU = 2 * math.pi
DEG = 4096 / 360
UPPER, HIPS, HEAD, FEATHER, BACK, CLOTH = 1, 13, 6, 7, 8, 18
ARMS = {'R': (2, 3, 4, 5, 1), 'L': (9, 10, 11, 12, -1)}    # shoulder, upper arm, forearm, fist, side (+1 = x > 0)
LEGS = {'LH': (19, 20, 21, -1, False), 'RH': (14, 15, 16, 1, False)}
TOE_OF = {'LH': 22, 'RH': 17}


def harm(phase, *terms):
    """A sum of cosines: terms are (amplitude, rate, delay in cycles)."""
    return sum(a * math.cos(TAU * rate * (phase - delay)) for a, rate, delay in terms)


def bump(phase, centre, width):
    """A smooth hump of 1 at `centre` falling to 0 `width` cycles away (cosine-squared, wrapping round the loop)."""
    d = (phase - centre + 0.5) % 1.0 - 0.5
    return math.cos(math.pi * d / width / 2) ** 2 if abs(d) < width else 0.0


def body(rig, cfg, phase, pose, hist):
    """Height, sway and the three turns of hips and upper body, the arms, the head, the feather and the loincloth; all
    closed loops."""
    c, W0 = cfg, rig.still
    rest = rig.rest
    bob = harm(phase, (c['bob'], 2, c['high']), (c['bob2'], 4, c['high'] + 0.03), (c['bob_side'], 1, c['high'] + 0.2))
    pose[UPPER][7] = rest[UPPER][7] - c['height'] - bob
    pose[UPPER][6] = rest[UPPER][6] + harm(phase, (c['shift'], 1, c['roll_at']), (c['shift2'], 3, c['roll_at'] + 0.07))
    # the hips: pitch twice a cycle, yaw and roll once; the upper body turns against them
    hp = c['hip_tilt'] + harm(phase, (c['hip_pitch'], 2, c['pitch_at']), (c['hip_pitch1'], 1, c['pitch_at'] + 0.12))
    hy = harm(phase, (c['hip_yaw'], 1, c['yaw_at']), (c['hip_yaw2'], 3, c['yaw_at'] + 0.05))
    hr = harm(phase, (c['hip_roll'], 1, c['roll_at'] + 0.5), (c['hip_roll2'], 3, c['roll_at'] + 0.57))
    lag = c['lag']
    up = c['lean'] + harm(phase - lag, (c['pitch'], 2, c['pitch_at']), (c['pitch1'], 1, c['pitch_at'] + 0.12))
    uy = -c['counter'] * hy + harm(phase - lag, (c['yaw'], 1, c['yaw_at'] + 0.1))
    ur = harm(phase - lag, (c['roll'], 1, c['roll_at']), (c['roll2'], 3, c['roll_at'] + 0.06))
    breath = c['breath'] * math.sin(TAU * (phase - 0.1))
    up += breath
    Wt = {0: [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}
    Wt[UPPER] = mul(rot([up, uy, ur]), rig.R(W0, UPPER))
    Wt[HIPS] = mul(rot([hp, hy, hr]), rig.R(W0, HIPS))

    def put(bone, parent, delta):
        Wt[bone] = mul(delta, rig.R(W0, bone))
        set_rot(pose, bone, mul(tr(Wt[parent]), Wt[bone]), hist)
    set_rot(pose, UPPER, Wt[UPPER], hist)
    put(HIPS, UPPER, rot([hp, hy, hr]))
    # the head keeps most of its gaze: it follows the upper body by `steady`, and what it does follows late
    nod = harm(phase - c['nod_lag'], (c['nod'], 2, c['nod_at']), (c['nod2'], 1, c['nod_at'] + 0.1))
    look = c['look'] * harm(phase, (1, 1, c['look_at']), (0.3, 2, c['look_at'] + 0.1))
    gaze = sum(a * bump(phase, at, w) for at, w, a in c['gaze'])            # (centre, width, degrees): looks aside, tilts
    tilt = sum(a * bump(phase, at, w) for at, w, a in c['tilt'])
    put(HEAD, UPPER, rot([up - c['steady'] * (up - c['lean']) - c['head'] + nod + c['head_up'],
                          uy * 0.5 + look + gaze, ur * 0.6 + tilt]))
    # the arms: the shoulder swings as a pendulum against the leg on its side, the upper arm, forearm and fist follow it
    # a little later each; the blades hang from the fists
    for side, (sh, el, fo, fist, sd) in ARMS.items():
        leg_at = 0.0 if side == 'R' else 0.5
        swing = c['arm'] * harm(phase, (1, 1, c['arm_at'] + leg_at), (c['arm2'], 2, c['arm_at'] + leg_at + 0.1))
        out = c['arm_out'] * sd + c['arm_roll'] * sd * harm(phase, (1, 2, c['arm_at'] + 0.05))
        gest = sum(a * bump(phase, at, w) for at, w, a in c['gesture'].get(side, ()))   # a raised arm: (centre, width, degrees)
        Wt[sh] = mul(Wt[UPPER], mul(rot([swing + c['arm_lift'] + gest, 0, out]), mul(tr(rig.R(W0, UPPER)), rig.R(W0, sh))))
        set_rot(pose, sh, mul(tr(Wt[UPPER]), Wt[sh]), hist)
        flex = c['elbow'] * harm(phase, (1, 1, c['arm_at'] + leg_at + c['elbow_lag']))
        bend = sum(a * bump(phase, at, w) for at, w, a in c['bend'].get(side, ()))
        pose[el][3] = rest[el][3] + round((flex - c['elbow_extra'] - bend) * DEG)
        wrist = c['wrist'] * harm(phase, (1, 1, c['arm_at'] + leg_at + 2 * c['elbow_lag']))
        pose[fo][3] = rest[fo][3] + round((0.5 * flex + wrist - 0.5 * bend) * DEG)
        hand = c['fist'] * harm(phase, (1, 1, c['arm_at'] + leg_at + 3 * c['elbow_lag']))
        pose[fist][3] = rest[fist][3] + round((hand - c['fist_hold'] - 0.3 * bend) * DEG)
    # the feather and the loincloth trail the body: a few ticks later, a little more
    f = harm(phase - c['feather_lag'], (c['feather'], 2, c['pitch_at']), (c['feather1'], 1, 0.0))
    flick = sum(a * bump(phase - c['feather_lag'], at, w) for at, w, a in c['flick'])
    pose[FEATHER][3] = rest[FEATHER][3] + round((f + flick) * DEG)
    pose[FEATHER][5] = rest[FEATHER][5] + round(0.6 * (f + flick) * math.sin(TAU * phase) * DEG)
    d = harm(phase - c['cloth_lag'], (c['cloth'], 2, c['pitch_at']), (c['cloth1'], 1, 0.0))
    pose[CLOTH][3] = rest[CLOTH][3] + round((d + c['cloth_out']) * DEG)


PROFILE = dict(
    species=SPECIES, name='Dinohyumon', source=None,
    parents=[-1, 0, 1, 2, 3, 4, 1, 6, 1, 1, 9, 10, 11, 1, 13, 14, 15, 16, 13, 13, 19, 20, 21],
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
    steady=0.8, head=0, head_up=0, nod=1, nod2=0.5, nod_at=0.2, nod_lag=0.06, look=0, look_at=0.3,
    arm=14, arm2=0, arm_at=0.0, arm_lift=0, arm_out=5, arm_roll=0, elbow=6, elbow_extra=0, elbow_lag=0.05, wrist=0, fist=0, fist_hold=0,
    feather=4, feather1=2, feather_lag=0.08, cloth=2, cloth1=1, cloth_lag=0.1, cloth_out=0,
    gaze=(), tilt=(), gesture={}, bend={}, flick=(),
)

# Hand-keyed feel. Every walking clip is two cycles long: cycle A and cycle B differ (one leg lifts higher, lands
# earlier, a different heel strike, a deeper bob, a looser arm) and the clip eases from the one into the other and back,
# so no two steps are alike and the loop still closes. Then the arms, hands, head, feather and loincloth follow the
# body through a loose spring each (own delay, own overshoot), which the generator's plain sines cannot give them.
FOLLOW = {2: (0.55, 0.5), 3: (0.6, 0.45), 4: (0.5, 0.45), 5: (0.45, 0.4),        # right arm: shoulder, elbow, wrist, fist
          9: (0.55, 0.5), 10: (0.6, 0.45), 11: (0.5, 0.45), 12: (0.45, 0.4),     # left arm
          HEAD: (0.7, 0.55), FEATHER: (0.4, 0.3), 8: (0.5, 0.4), CLOTH: (0.45, 0.35)}   # (rad per tick, damping)


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
            base = sum(seq) / len(seq)
            mixed = spring(seq, rate, damping)
            for i in range(2 * ticks):
                out[i][b][ch] = seq[i] + (mixed[i] - seq[i]) * follow
    closing = [list(v) for v in out[0]]
    closing[0][8] = -round(speed * 2 * ticks)
    out.append(closing)
    return out

PROFILE['gaits'] = {
    0: dict(COMMON, name='idle', ticks=96, speed=0, steps=(),
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 1.0, 'RH': 1.0}, track={'front': 0, 'hind': 24}, height=-12, bob=1.2, bob2=0, bob_side=0, shift=4, shift2=0,
            hip_yaw=0, hip_yaw2=0, hip_roll=1.5, hip_roll2=0, hip_pitch=0.6, hip_pitch1=0, roll=2, roll2=0, yaw=0, pitch=0.6, pitch1=0,
            counter=0, lean=3, head=3, nod=0.8, nod2=0, look=0, arm=0, elbow=4, fist=0, breath=1.6,
            gaze=((0.5, 0.2, 22), (0.88, 0.1, -9)), tilt=((0.5, 0.22, 6),), gesture={"R": ((0.25, 0.3, -9),)}, bend={"R": ((0.25, 0.3, 24),)},
            flick=((0.7, 0.1, 10),)),
    2: dict(COMMON, name='walk', ticks=20, speed=17,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.56, 'RH': 0.56}, lift={'front': 0, 'hind': 30},
            peel={'front': 0, 'hind': 0}, lean=3, head=4, height=-26, high=0.27, bob=7, bob2=1.2, bob_side=1.0, hip_yaw=5, hip_roll=3.5, roll=3, arm=16, elbow=8),
    3: dict(COMMON, name='tired walk', ticks=26, speed=11,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.64, 'RH': 0.64}, height=-32, high=0.3, bob=7.5, lift={'front': 0, 'hind': 26},
            peel={'front': 0, 'hind': -6}, lean=12, head=-9, arm=7, elbow=3, hip_yaw=3.5, hip_roll=3, shift=8, roll=3.5, bob_side=1.2),
    4: dict(COMMON, name='run', kind='trot', ticks=14, speed=38,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.34, 'RH': 0.34}, height=-34, high=0.42, world_ease=True, arc=0.6, clear_ease=0.05, lift={'front': 0, 'hind': 55},
            peel={'front': 0, 'hind': 0}, bob=13, bob2=1.5, lean=16, head=6, arm=28, elbow=12, elbow_extra=12, hip_yaw=7, hip_roll=3, roll=3),
}

# The character. A warrior-beast: low and forward, heavy through the hips, the chest turning against them, the arms bent
# and ready (never pendulums), steps short and weighted. Cycle A and cycle B differ (the leg that lifts higher, the heel
# strike, the landing time, how deep the body sinks, how far the chest leans), see `compose`.
CHARACTER = {
    0: dict(height=-20, lean=8, head=-4, hip_roll=2.2, roll=2.6, shift=6, elbow=4, elbow_extra=8, arm_out=5, bob=1.6, breath=2.2),
    2: dict(ticks=16, height=-36, lean=11, head=-3, bob=8, hip_yaw=9, hip_roll=5, roll=6, yaw=3, counter=1.5, shift=8,
            arm=8, arm_at=0.2, arm_out=4, elbow=9, elbow_extra=24, feather=6, cloth=3, cloth_out=10, lift={'front': 0, 'hind': 26},
            settle=1.5, heel=3, curl={'front': 0, 'hind': 6}, leg_lift={'LH': 1.0, 'RH': 0.88}),
    3: dict(ticks=30, speed=11, height=-42, lean=24, head=-20, bob=5.5, hip_yaw=4, hip_roll=3.5, roll=4, shift=9, arm=3.5,
            arm_at=0.1, arm_out=5, elbow=3, elbow_extra=6, lift={'front': 0, 'hind': 18}, peel={'front': 0, 'hind': -8},
            duty={'LH': 0.68, 'RH': 0.68}, settle=1.5, heel=3, leg_lift={'LH': 1.0, 'RH': 0.85}),
    4: dict(height=-34, lean=23, head=-6, bob=14, hip_yaw=9, hip_roll=4, roll=4.5, yaw=2.5, counter=1.3, arm=14, arm_at=0.25,
            elbow=14, elbow_extra=12, arm_out=3, feather=8, cloth_out=8, leg_lift={'LH': 1.0, 'RH': 0.92}),
}
OTHER = {      # cycle B: what changes from cycle A, as factors on A's numbers or the leg settings
    2: dict(scale=dict(bob=1.15, lean=1.15, hip_yaw=1.15, roll=1.1, arm=0.85, head=1.3),
            leg_lift={'LH': 0.9, 'RH': 1.08}, touchdown={'LH': 0.0, 'RH': 0.53}, settle=2.5, heel=4, curl={'front': 0, 'hind': 12}),
    3: dict(scale=dict(bob=1.15, lean=0.95, arm=1.2, roll=1.1, shift=1.1),
            leg_lift={'LH': 0.88, 'RH': 1.1}, touchdown={'LH': 0.0, 'RH': 0.51}, settle=2.5, heel=4),
    4: dict(scale=dict(lean=1.1, arm=0.9, hip_yaw=1.1), leg_lift={'LH': 0.92, 'RH': 1.0}),
}
for slot, character in CHARACTER.items():
    PROFILE['gaits'][slot].update(character)
for slot, spec in OTHER.items():
    cfg = PROFILE['gaits'][slot]
    other = {k: v for k, v in spec.items() if k != 'scale'}
    other.update({k: cfg[k] * f for k, f in spec['scale'].items()})
    cfg.update(cycles=2, compose=compose, other=other)


def prepare(model, skeleton):
    """Fill what is read off the rig: each foot's toe direction and the pivot of the sole (the claw point)."""
    import animsheet
    pose = animsheet.slot_frames(model, len(skeleton), 0)[0][0]
    for name, toe in TOE_OF.items():
        PROFILE['paw_rest'][name] = list(pose[toe][6:9])     # the claw point in the foot bone's space
    PROFILE['sole'][False] = list(pose[TOE_OF['RH']][6:9])


def build(data, skeleton):
    """The reshaped model with the four clips written on it -> (bytes, proof): chibi's proof (its species patch reaches
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
    skeleton = json.loads((ROOT / 'content/species/308-dinohyumon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof['gait'], indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
