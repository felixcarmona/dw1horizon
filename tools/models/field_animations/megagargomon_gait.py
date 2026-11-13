"""MegaGargomon's field gaits (species 335): idle, walk, tired walk and run as a massive, living giant on planted feet.

MegaGargomon is an armoured cyborg bear: bone 1 is the torso (the chest and the back with the backpack), bone 2 the
hips under it with the legs (3-6 on the side x < 0: thigh, shin, foot, toe plate; 8-11 on x > 0) and a small hanging
flap on each hip (7, 12). From the torso hang the two shoulder cannons (13 right, 23 left: a big pod with a bear
face), under each the upper arm (14, 24), the forearm gauntlet (15, 25) and the fist (16, 26), and the head 17 with a
small face plate (18) and the two long white head fins (19 and 22; 20 and 21 are hidden). Forward is -z.

What was wrong. The walk, the tired walk and the run were one clip written three times at three lengths (19, 33 and
11 ticks): the legs swung 46 to 49 degrees and the upper arms 32, and every other bone (torso, hips, shoulder cannons,
forearms, fists, head, fins) stood perfectly still, the body rose and fell by 3 units, so a 590-unit giant was carried
along rigidly on two swinging stilts, the arms moving in lock step with each other. The soles slid by 35 % (walk), 35 %
(tired) and 59 % (run) of the travel on average and the run lasted 11 ticks.

What the clips are now. `quadruped.py` plants each foot (a two-bone solve on thigh and shin, the sole flat on the floor
and the foot keeping its own splay) and the legs step half a cycle apart; `body` writes everything above them from the
same gait phase, as one heavy thing: the hips pitch, turn and roll with each footfall and the body sinks into the loaded
leg and rises over it (a short hard dip, a slow rise), the torso shifts over the loaded foot and turns against the hips,
leans and rolls a little later than they do, the arms swing as pendulums against the legs on their sides with the
forearm and the fist later still, the head steadies against the torso and follows late, the shoulder cannons rock on
their mounts a few ticks behind the body, and the head fins and hip flaps trail. Every walking clip is two cycles long:
cycle B differs from cycle A (one leg lifts higher, lands a touch earlier, the body sinks and leans a little more) and
the clip eases from the one to the other and back, so that no two steps are alike and the loop still closes; then each
loose bone follows through a spring of its own (own delay, own overshoot). The idle (96 ticks) keeps both feet planted:
the weight rolls from one leg to the other, the chest breathes, the head looks aside, a fist opens and closes, and the
cannons and fins settle after every move.

`build` runs the chibi reshaping first (the celebration overlay's base generator is this module) and writes the four
clips on its result; nothing is stored but the recipe name. Offline: `python3 -m tools.models.field_animations.
megagargomon_gait --source SRC.MMD --out AFTER.MMD` with SRC.MMD the model the build gives the overlay (the imported
model with its slot aliases applied).
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

SPECIES = 335
TAU = 2 * math.pi
DEG = 4096 / 360
UPPER, HIPS, HEAD, FACE = 1, 2, 17, 18
FINS = {'R': 22, 'L': 19}
FLAPS = {'R': 12, 'L': 7}
# cannon pod, upper arm, forearm, fist, side (+1 = x > 0)
ARMS = {'R': (13, 14, 15, 16, 1), 'L': (23, 24, 25, 26, -1)}
LEGS = {'LH': (3, 4, 5, -1, False), 'RH': (8, 9, 10, 1, False)}
TOE_OF = {'LH': 6, 'RH': 11}
PARENTS = [-1, 0, 1, 2, 3, 4, 5, 2, 2, 8, 9, 10, 2, 1, 13, 14, 15, 1, 17, 17, 17, 17, 17, 1, 23, 24, 25]


def harm(phase, *terms):
    """A sum of cosines: terms are (amplitude, rate, delay in cycles)."""
    return sum(a * math.cos(TAU * rate * (phase - delay)) for a, rate, delay in terms)


def bump(phase, centre, width):
    """A smooth hump of 1 at `centre` falling to 0 `width` cycles away (cosine-squared, wrapping round the loop)."""
    d = (phase - centre + 0.5) % 1.0 - 0.5
    return math.cos(math.pi * d / width / 2) ** 2 if abs(d) < width else 0.0


def local(pose, rest, hist, bone, delta):
    """The bone turned by `delta` degrees (x, y, z) in its parent's frame on top of its rest rotation."""
    set_rot(pose, bone, mul(rot(delta), mmd.rot_matrix(*rest[bone][3:6])), hist)


def body(rig, cfg, phase, pose, hist):
    """Height, sway and the three turns of hips and torso, the cannons, the arms, the head, the fins and the flaps; all
    closed loops."""
    c, W0 = cfg, rig.still
    rest = rig.rest
    bob = harm(phase, (c['bob'], 2, c['high']), (c['bob2'], 4, c['high'] + 0.03), (c['bob_side'], 1, c['high'] + 0.2))
    pose[UPPER][7] = rest[UPPER][7] - c['height'] - bob
    pose[UPPER][6] = rest[UPPER][6] + harm(phase, (c['shift'], 1, c['roll_at']), (c['shift2'], 3, c['roll_at'] + 0.07))
    # the hips: pitch twice a cycle, yaw and roll once; the torso turns against them, a little later
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
    set_rot(pose, UPPER, Wt[UPPER], hist)
    set_rot(pose, HIPS, mul(tr(Wt[UPPER]), Wt[HIPS]), hist)
    # the head keeps most of its gaze: it follows the torso by `steady`, and what it does follows late
    nod = harm(phase - c['nod_lag'], (c['nod'], 2, c['nod_at']), (c['nod2'], 1, c['nod_at'] + 0.1))
    look = c['look'] * harm(phase, (1, 1, c['look_at']), (0.3, 2, c['look_at'] + 0.1))
    gaze = sum(a * bump(phase, at, w) for at, w, a in c['gaze'])            # (centre, width, degrees): looks aside, tilts
    tilt = sum(a * bump(phase, at, w) for at, w, a in c['tilt'])
    head = mul(rot([up - c['steady'] * (up - c['lean']) - c['head'] + nod + c['head_up'],
                    uy * 0.5 + look + gaze, ur * 0.6 + tilt]), rig.R(W0, HEAD))
    set_rot(pose, HEAD, mul(tr(Wt[UPPER]), head), hist)
    # the cannons rock on their mounts, late, against the torso's roll and the arm's swing
    for side, (pod, arm, fore, fist, sd) in ARMS.items():
        leg_at = 0.0 if side == 'R' else 0.5
        a_at = c['arm_at'] + leg_at
        # the pod: pitched by the arm's swing (a little, late), rolled by the torso's roll (late, outwards)
        pitch = c['pod'] * harm(phase, (1, 1, a_at + c['pod_lag']), (0.3, 2, c['pitch_at'] + 0.2))
        roll = sd * c['pod_roll'] * harm(phase, (1, 1, c['roll_at'] + 0.15), (0.3, 2, c['pitch_at'] + 0.25))
        local(pose, rest, hist, pod, [pitch, 0, roll])
        # the arm: a pendulum against the leg on its side, forearm and fist later each
        swing = c['arm'] * harm(phase, (1, 1, a_at), (c['arm2'], 2, a_at + 0.1))
        out = c['arm_out'] * sd + c['arm_roll'] * sd * harm(phase, (1, 2, a_at + 0.05))
        gest = sum(a * bump(phase, at, w) for at, w, a in c['gesture'].get(side, ()))   # a raised arm: (centre, width, degrees)
        local(pose, rest, hist, arm, [swing + c['arm_lift'] + gest, 0, out])
        flex = c['elbow'] * harm(phase, (1, 1, a_at + c['elbow_lag']))
        bend = sum(a * bump(phase, at, w) for at, w, a in c['bend'].get(side, ()))
        local(pose, rest, hist, fore, [flex - c['elbow_extra'] - bend, 0, 0])
        wrist = c['wrist'] * harm(phase, (1, 1, a_at + 2 * c['elbow_lag']))
        hand = c['fist'] * harm(phase, (1, 1, a_at + 3 * c['elbow_lag']))
        local(pose, rest, hist, fist, [0.5 * flex + wrist + hand - c['fist_hold'] - 0.5 * bend, 0, 0])
        # the head fin and the hip flap trail the body
        f = harm(phase - c['fin_lag'], (c['fin'], 2, c['pitch_at']), (c['fin1'], 1, 0.0))
        flick = sum(a * bump(phase - c['fin_lag'], at, w) for at, w, a in c['flick'])
        local(pose, rest, hist, FINS[side], [f + flick, 0, sd * (c['fin_out'] + 0.5 * (f + flick))])
        d = harm(phase - c['flap_lag'], (c['flap'], 2, c['pitch_at']), (c['flap1'], 1, 0.0))
        local(pose, rest, hist, FLAPS[side], [d + c['flap_out'], 0, 0])
    face = harm(phase - c['fin_lag'], (c['face'], 2, c['pitch_at']))
    local(pose, rest, hist, FACE, [face, 0, 0])


PROFILE = dict(
    species=SPECIES, name='MegaGargomon', source=None, parents=PARENTS,
    pelvis=UPPER, chest=None, neck=None, head=HEAD, tail=(), loose=(),
    legs=LEGS, pole_world=True, rest_plane=True, pole={False: [0.3, 0.0, -1.0]},
    sole={False: [0, 57, -64]},     # the toe plate's point in the foot bone's space (the rest pose's feet are splayed 16 and 66
                                    # degrees: the feet stand flat and straight instead, a little turned out below)
    paw_flat={'LH': [0, 0, 0], 'RH': [0, 0, 0]},
    reach={'front': 0, 'hind': -64},      # the ankle (not the toe plate) stands under the hip
    fold={False: 70}, clear=2, flat_shin={False: 0.4},
    speed_range={0: (0, 0), 2: (15, 31), 3: (10, 20), 4: (35, 52)},
    body=body, floor=3, stance_slip=0.2,
    tol={None: 4, 3: 1, 4: 1, 5: 1, 8: 1, 9: 1, 10: 1},
    gaits={},
)
COMMON = dict(
    kind='walk', clear=4, snap=False, arc=0.5, clear_ease=0.1, world_ease=True, fold_soft=10, slip=0.0, steps=('LH', 'RH'),
    reach={'front': 0, 'hind': 0}, lift={'front': 0, 'hind': 30}, curl={'front': 0, 'hind': 0}, peel={'front': 0, 'hind': 0},
    out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 0}, track={'front': 0, 'hind': 0}, heel=3, settle=1.5,
    high=0.1, bob=3, bob2=0.8, bob_side=0.5, height=-22, shift=5, shift2=0.8, roll_at=0.3,
    hip_tilt=0, hip_pitch=1, hip_pitch1=0.3, hip_yaw=4, hip_yaw2=0.5, hip_roll=2, hip_roll2=0.4,
    lean=0, pitch=1.5, pitch1=0.5, pitch_at=0.15, yaw=1, counter=0.9, roll=2.5, roll2=0.5, yaw_at=0.05, lag=0.07, breath=0,
    steady=0.8, head=0, head_up=0, nod=1, nod2=0.5, nod_at=0.2, nod_lag=0.06, look=0, look_at=0.3,
    pod=3, pod_lag=0.12, pod_roll=2,
    arm=14, arm2=0, arm_at=0.0, arm_lift=0, arm_out=-8, arm_roll=0, elbow=6, elbow_extra=0, elbow_lag=0.05, wrist=0, fist=0, fist_hold=0,
    fin=4, fin1=2, fin_lag=0.08, fin_out=0, face=1, flap=1, flap1=0.5, flap_lag=0.1, flap_out=-4,
    gaze=(), tilt=(), gesture={}, bend={}, flick=(),
)

# Every walking clip is two cycles long (see `compose`): the loose bones follow the body through a spring each.
FOLLOW = {13: (0.32, 0.3), 23: (0.32, 0.3),                                        # the cannons: heavy, slow, a little overshoot
          14: (0.5, 0.45), 15: (0.45, 0.4), 16: (0.4, 0.35),                       # right arm: upper arm, forearm, fist
          24: (0.5, 0.45), 25: (0.45, 0.4), 26: (0.4, 0.35),
          HEAD: (0.6, 0.5), FACE: (0.4, 0.3), 19: (0.4, 0.3), 22: (0.4, 0.3), 7: (0.45, 0.35), 12: (0.45, 0.35)}   # (rad per tick, damping)


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
    0: dict(COMMON, name='idle', ticks=80, speed=0, steps=(),
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 1.0, 'RH': 1.0}, height=-6, bob=1.0, bob2=0, bob_side=0, shift=5, shift2=0,
            hip_yaw=0, hip_yaw2=0, hip_roll=1.5, hip_roll2=0, hip_pitch=0.5, hip_pitch1=0, roll=1.8, roll2=0, yaw=0, pitch=0.6, pitch1=0,
            counter=0, lean=2, head=0, nod=0.8, nod2=0, look=0, arm=0, elbow=2, fist=0, breath=1.4,
            gaze=((0.5, 0.2, 18), (0.88, 0.1, -8)), tilt=((0.5, 0.22, 5),), gesture={'R': ((0.25, 0.3, -6),)}, bend={'R': ((0.25, 0.3, 14),)},
            flick=((0.7, 0.1, 8),)),
    2: dict(COMMON, name='walk', ticks=20, speed=17,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.6, 'RH': 0.6}, lift={'front': 0, 'hind': 30},
            lean=3, height=-28, high=0.27, bob=6, bob2=1.2, bob_side=1.0, hip_yaw=6, hip_roll=3.5, roll=3, arm=16, elbow=8),
    3: dict(COMMON, name='tired walk', ticks=24, speed=11,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.66, 'RH': 0.66}, height=-34, high=0.3, bob=6, lift={'front': 0, 'hind': 24},
            lean=12, head=-9, arm=7, elbow=3, hip_yaw=3.5, hip_roll=3, shift=8, roll=3.5, bob_side=1.2),
    4: dict(COMMON, name='run', kind='trot', ticks=20, speed=36, clear=7,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.32, 'RH': 0.32}, height=-26, high=0.42, arc=0.9, clear_ease=0.05,
            lift={'front': 0, 'hind': 50}, bob=12, bob2=1.5, lean=14, head=6, arm=26, elbow=12, elbow_extra=12, hip_yaw=7, hip_roll=3, roll=3),
}

# The character: a heavy giant, so the body sinks hard into each footfall and rises slowly, the torso turns and leans
# against the hips, the arms swing wide and late, the cannons rock behind. Cycle A and cycle B differ (the leg that lifts
# higher, the landing time, how deep the body sinks, how far the torso leans), see `compose`.
CHARACTER = {
    2: dict(leg_lift={'LH': 1.0, 'RH': 0.88}),
    3: dict(leg_lift={'LH': 1.0, 'RH': 0.85}),
    4: dict(leg_lift={'LH': 1.0, 'RH': 0.92}),
}
OTHER = {      # cycle B: what changes from cycle A, as factors on A's numbers or the leg settings
    2: dict(scale=dict(bob=1.15, lean=1.15, hip_yaw=1.15, roll=1.1, arm=0.85, head=1.3),
            leg_lift={'LH': 0.9, 'RH': 1.08}, touchdown={'LH': 0.0, 'RH': 0.53}, settle=2.5, heel=4),
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
    """Fill what is read off the rig: the pivot of the sole (the toe plate's point, its x taken as 0)."""
    import animsheet
    pose = animsheet.slot_frames(model, len(skeleton), 0)[0][0]
    PROFILE['sole'][False] = [0.0] + list(pose[TOE_OF['RH']][7:9])


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
    skeleton = json.loads((ROOT / 'content/species/335-megagargomon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof['gait'], indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
