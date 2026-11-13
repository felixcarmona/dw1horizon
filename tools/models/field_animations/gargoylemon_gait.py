"""Gargoylemon's field gaits (species 327): idle, walk, tired walk and run with planted feet on its own two legs.

Gargoylemon is a crouching stone gargoyle with a pair of feathered bat wings, long forearms ending in blue claws, a
heavy horned head and a three-link tail. Bone 1 is the waist (it carries the height of the whole body); bone 2 the hips
under it with the tail 3-5 and the legs 6-9 (right: thigh, shin, ankle, toes) and 10-13 (left); bone 14 the chest, also
under the waist, with the arms (15-17 right: shoulder, upper arm, forearm with the claws; 23-25 left), the neck 18, the
head 19 with its chin plate 20, and the two wings 21 (right) and 22 (left), one bone each. Forward is -z.

The model made by `chibi.py` (the overlay `gargoylemon-chibi`: big head, short thick legs) is what the clips are written
on. Its imported clips slid the soles (65 % of the travel in the walk and the tired walk, 94 % in the run, 236 % at
worst), threw the feet 90 to 110 units up, kept the tired walk as fast as the walk (19 against 21 units a tick) and
beat the wings like a loose sheet. Here `quadruped.py` plants each foot (two-bone IK on the thigh and shin with the
knee forward and the sole flat on the floor, keeping its own outward splay) and `body` writes everything above the
legs: the hips turn against the chest, the whole body rolls its weight over the loaded foot, the arms sweep as
pendulums with the forearm and the claws late, the head follows the chest late, the tail trails link by link and the
wings lift on each push-off and sink on each landing, the wing tips behind the roots.

The character is a heavy stone beast: the walk is a slow, wide, crouching tread with the shoulders rolling and the
wings riding up and down behind the body, the tired walk a dragging slump with the wings hung low and the head
down, the run a head-down lunge with the wings swept back and beating once a stride. The idle (120 ticks) keeps both
feet planted: the weight rolls from one foot to the other, the chest breathes, the head turns to look aside, the
wings settle, shrug and stretch once and the tail sways.

`build` runs the chibi reshaping first and writes the four clips on its result; nothing is stored but the overlay's
recipe name in content/models/imports/species.py. Offline: `python3 -m tools.models.field_animations.gargoylemon_gait
--source EDIT.MMD --out AFTER.MMD` with EDIT.MMD the model `tools/models/edit.py get 327` makes.
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

SPECIES = 327
TAU = 2 * math.pi
DEG = 4096 / 360
WAIST, HIPS, CHEST, NECK, HEAD, CHIN = 1, 2, 14, 18, 19, 20
TAIL = (3, 4, 5)
WINGS = {'R': 21, 'L': 22}
ARMS = {'R': (15, 16, 17, 1), 'L': (23, 24, 25, -1)}    # shoulder, upper arm, forearm, side (+1 = x > 0)
LEGS = {'LH': (10, 11, 12, -1, False), 'RH': (6, 7, 8, 1, False)}
TOE_OF = {'LH': 13, 'RH': 9}


def harm(phase, *terms):
    """A sum of cosines: terms are (amplitude, rate, delay in cycles)."""
    return sum(a * math.cos(TAU * rate * (phase - delay)) for a, rate, delay in terms)


def bump(phase, centre, width):
    """A smooth hump of 1 at `centre` falling to 0 `width` cycles away (cosine-squared, wrapping round the loop)."""
    d = (phase - centre + 0.5) % 1.0 - 0.5
    return math.cos(math.pi * d / width / 2) ** 2 if abs(d) < width else 0.0


def body(rig, cfg, phase, pose, hist):
    """Height, sway and the turns of waist, hips and chest, the arms, the wings, the head, the chin and the tail; all
    closed loops. Rotations are written as turns of the bone's world rotation about its own joint, so a child keeps
    the gaze or the span it was given whatever its parent does."""
    c, W0, rest = cfg, rig.still, rig.rest
    bob = harm(phase, (c['bob'], 2, c['high']), (c['bob2'], 4, c['high'] + 0.03), (c['bob_side'], 1, c['high'] + 0.2))
    pose[WAIST][7] = rest[WAIST][7] - c['height'] - bob
    pose[WAIST][6] = rest[WAIST][6] + harm(phase, (c['shift'], 1, c['roll_at']), (c['shift2'], 3, c['roll_at'] + 0.07))
    lag = c['lag']
    hp = c['hip_tilt'] + harm(phase, (c['hip_pitch'], 2, c['pitch_at']), (c['hip_pitch1'], 1, c['pitch_at'] + 0.12))
    hy = harm(phase, (c['hip_yaw'], 1, c['yaw_at']), (c['hip_yaw2'], 3, c['yaw_at'] + 0.05))
    hr = harm(phase, (c['hip_roll'], 1, c['roll_at'] + 0.5), (c['hip_roll2'], 3, c['roll_at'] + 0.57))
    cp = c['lean'] + harm(phase - lag, (c['pitch'], 2, c['pitch_at']), (c['pitch1'], 1, c['pitch_at'] + 0.12))
    cp += c['breath'] * math.sin(TAU * c['breath_rate'] * (phase - 0.1))
    cy = -c['counter'] * hy + harm(phase - lag, (c['yaw'], 1, c['yaw_at'] + 0.1))
    cr = harm(phase - lag, (c['roll'], 1, c['roll_at']), (c['roll2'], 3, c['roll_at'] + 0.06))
    Wt = {0: [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}

    def put(bone, parent, delta):
        Wt[bone] = mul(delta, rig.R(W0, bone))
        set_rot(pose, bone, mul(tr(Wt[parent]), Wt[bone]), hist)
    put(WAIST, 0, rot([0.5 * (hp + cp), 0.5 * (hy + cy), 0.5 * (hr + cr)]))
    put(HIPS, WAIST, rot([hp, hy, hr]))
    put(CHEST, WAIST, rot([cp, cy, cr]))
    chest = rot([cp, cy, cr])
    # the head keeps most of its gaze: it follows the chest by `1 - steady`, and what it does follows late
    nod = harm(phase - c['nod_lag'], (c['nod'], 2, c['nod_at']), (c['nod2'], 1, c['nod_at'] + 0.1))
    look = c['look'] * harm(phase, (1, 1, c['look_at']), (0.3, 2, c['look_at'] + 0.1))
    gaze = sum(a * bump(phase, at, w) for at, w, a in c['gaze'])
    tilt = sum(a * bump(phase, at, w) for at, w, a in c['tilt'])
    dyn = cp - c['lean']
    neck = [c['lean'] + c['neck'] + 0.8 * dyn + 0.4 * nod, cy * 0.7 + 0.4 * (look + gaze), cr * 0.5 + 0.3 * tilt]
    put(NECK, CHEST, rot(neck))
    put(HEAD, NECK, rot([c['lean'] + c['head'] + (1 - c['steady']) * dyn + 0.6 * nod, cy * 0.4 + 0.6 * (look + gaze),
                         cr * 0.3 + 0.7 * tilt]))
    pose[CHIN][3] = rest[CHIN][3] + round((c['chin'] + harm(phase - c['nod_lag'] - 0.06, (c['chin_move'], 2, c['nod_at']))
                                           + sum(a * bump(phase, at, w) for at, w, a in c['chin_open'])) * DEG)
    # the arms: the shoulder sweeps as a pendulum against the leg on its side (yaw swings the long arm fore and aft),
    # the upper arm, forearm and claws follow it a little later each
    for side, (sh, el, fo, sd) in ARMS.items():
        leg_at = 0.0 if side == 'R' else 0.5
        swing = c['arm'] * harm(phase, (1, 1, c['arm_at'] + leg_at), (c['arm2'], 2, c['arm_at'] + leg_at + 0.1))
        drop = c['arm_roll'] * harm(phase, (1, 2, c['arm_at'] + 0.05))
        gest = sum(a * bump(phase, at, w) for at, w, a in c['gesture'].get(side, ()))
        shoulder = mul(rot([c['arm_pitch'] * harm(phase, (1, 1, c['arm_at'] + leg_at + 0.25)), sd * (swing + gest),
                            sd * (c['arm_out'] + drop)]), chest)
        Wt[sh] = mul(shoulder, rig.R(W0, sh))
        set_rot(pose, sh, mul(tr(Wt[CHEST]), Wt[sh]), hist)
        flex = c['elbow'] * harm(phase, (1, 1, c['arm_at'] + leg_at + c['elbow_lag']))
        bend = sum(a * bump(phase, at, w) for at, w, a in c['bend'].get(side, ()))
        pose[el][3] = rest[el][3] + round(sd * (flex - c['elbow_extra'] - bend) * DEG)
        claw = c['wrist'] * harm(phase, (1, 1, c['arm_at'] + leg_at + 2 * c['elbow_lag']))
        pose[fo][4] = rest[fo][4] + round((claw + c['claws']) * DEG)
    # the wings: lift on the push-off, sink on the landing, the span carried back and up by the beat; each beat swings
    # the span about the forward axis (roll), sweeps it (yaw) and tips the leading edge (pitch)
    for side, bone in WINGS.items():
        sd = 1 if side == 'R' else -1
        w = harm(phase - c['wing_lag'], (c['wing'], 2, c['wing_at']), (c['wing1'], 1, c['wing_at'] + 0.1))
        beat = c['beat'] * harm(phase - c['wing_lag'], (1, 1, c['beat_at']), (0.28, 2, c['beat_at'] + 0.16))
        shrug = sum(a * bump(phase - c['wing_lag'], at, wd) for at, wd, a in c['shrug'])
        roll = -sd * (c['wing_up'] + w + beat + shrug)
        sweep = -sd * (c['wing_back'] + 0.45 * (w + beat) + 0.5 * c['flutter'] * harm(phase - c['wing_lag'], (1, 3, 0.1)))
        tip = c['wing_pitch'] + 0.35 * (w + beat)
        Wt[bone] = mul(mul(chest, rot([tip, sweep, roll])), rig.R(W0, bone))
        set_rot(pose, bone, mul(tr(Wt[CHEST]), Wt[bone]), hist)
    # the tail drags behind the hips: each link a little later and a little wider
    for k, b in enumerate(TAIL):
        late = c['tail_lag'] * (k + 1)
        pose[b][3] = rest[b][3] + round((c['tail_up'] * (k == 0) + c['tail'] * (0.6 + 0.4 * k) * harm(phase - late, (1, 2, c['pitch_at'] + 0.2), (0.4, 1, 0.1))
                                         + c['tail_sway'] * 0.3 * k * harm(phase - late, (1, 1, 0.3))) * DEG)
        pose[b][4] = rest[b][4] + round(c['tail_yaw'] * (0.7 + 0.5 * k) * harm(phase - late, (1, 1, 0.05 + 0.5 * c['tail_phase'])) * DEG)


PROFILE = dict(
    species=SPECIES, name='Gargoylemon', source=None,
    parents=[-1, 0, 1, 2, 3, 4, 2, 6, 7, 8, 2, 10, 11, 12, 1, 14, 15, 16, 14, 18, 19, 14, 14, 14, 23, 24],
    pelvis=WAIST, chest=None, neck=None, head=HEAD, tail=(), loose=(),
    legs=LEGS, toes={8: 9, 12: 13}, pole_world=True, rest_plane=True, pole={False: [0.62, 0.0, -0.78]},
    paw_rest={'LH': [0, 0, 0], 'RH': [0, 0, 0]},     # filled from the rig below
    sole={False: [0, 0, 0]},                            # filled from the rig below
    reach={'front': 0, 'hind': -40},
    fold={False: 60}, clear=2,
    speed_range={0: (0, 0), 2: (15, 31), 3: (10, 20), 4: (35, 52)},
    body=body, floor=3, stance_slip=0.2,
    gaits={},
)
COMMON = dict(
    kind='walk', snap=False, arc=0.6, clear_ease=0.1, world_ease=True, fold_soft=10, slip=0.0, steps=('LH', 'RH'),
    reach={'front': 0, 'hind': 0}, lift={'front': 0, 'hind': 30}, curl={'front': 0, 'hind': 0}, peel={'front': 0, 'hind': 0},
    out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 0}, track={'front': 0, 'hind': 72}, heel=0,
    high=0.1, bob=3, bob2=0.8, bob_side=0.5, height=-10, shift=5, shift2=0.8, roll_at=0.3,
    hip_tilt=0, hip_pitch=1, hip_pitch1=0.3, hip_yaw=4, hip_yaw2=0.5, hip_roll=2, hip_roll2=0.4,
    lean=0, breath_rate=1, pitch=1.5, pitch1=0.5, pitch_at=0.15, yaw=1, counter=0.9, roll=2.5, roll2=0.5, yaw_at=0.05, lag=0.07, breath=0,
    steady=0.8, head=0, neck=0, nod=1, nod2=0.5, nod_at=0.2, nod_lag=0.06, look=0, look_at=0.3, chin=0, chin_move=2, chin_open=(),
    arm=12, arm2=0, arm_at=0.0, arm_pitch=3, arm_out=0, arm_roll=0, elbow=6, elbow_extra=0, elbow_lag=0.05, wrist=0, claws=0,
    wing=5, wing1=1, wing_at=0.25, wing_lag=0.1, beat=0, beat_at=0.3, wing_up=0, wing_back=0, wing_pitch=0, flutter=0, shrug=(),
    tail=5, tail_lag=0.08, tail_up=0, tail_sway=0, tail_yaw=4, tail_phase=0,
    gaze=(), tilt=(), gesture={}, bend={},
)

# Hand-keyed feel. Every walking clip is two cycles long: cycle A and cycle B differ (one leg lifts higher, lands
# earlier, a different heel strike, a deeper bob, a wider wing beat) and the clip eases from the one into the other and
# back, so no two steps are alike and the loop still closes. Then the parts above the legs follow the body through a
# loose spring each (own delay, own overshoot), which the generator's plain sines cannot give them.
FOLLOW = {15: (0.55, 0.5), 16: (0.5, 0.45), 17: (0.45, 0.4), 23: (0.55, 0.5), 24: (0.5, 0.45), 25: (0.45, 0.4),    # arms
          NECK: (0.7, 0.55), HEAD: (0.6, 0.5), CHIN: (0.35, 0.3), 21: (0.4, 0.4), 22: (0.4, 0.4),                   # wings
          3: (0.5, 0.4), 4: (0.4, 0.35), 5: (0.35, 0.3)}                                                           # tail  (rad per tick, damping)


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


def quat_matrix(q):
    x, y, z, w = q
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]


def blend(a, b, w, prev=None):
    """Pose a eased towards pose b by w. The turns of b are first written as the Euler solution nearest a's (the same
    turn has two, and blending two different ones swings a limb through the floor), then blended linearly."""
    out = []
    for k, (ba, bb) in enumerate(zip(a, b)):
        row = list(ba)
        if k:
            near = mmd.matrix_euler(mmd.rot_matrix(*bb[3:6]), ba[3:6])
            for i in range(3):
                row[3 + i] = ba[3 + i] + (near[i] - ba[3 + i]) * w
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
    0: dict(COMMON, name='idle', ticks=120, speed=0, steps=(),
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 1.0, 'RH': 1.0}, track={'front': 0, 'hind': 44}),
    2: dict(COMMON, name='walk', ticks=18, speed=16,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.58, 'RH': 0.58}),
    3: dict(COMMON, name='tired walk', ticks=26, speed=10,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.6, 'RH': 0.6}),
    4: dict(COMMON, name='run', kind='trot', ticks=12, speed=36,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.36, 'RH': 0.36}, lift={'front': 0, 'hind': 55}),
}
# The character. A heavy stone beast: low, wide and slow, the chest rolling against the hips, the long arms swinging
# from the shoulder with the claws late, the wings riding the body's rise and fall a beat behind it, a tail that
# drags and flicks. Cycle A and cycle B differ (the leg that lifts higher, the heel strike, the landing time, how deep
# the body sinks, how wide the wings beat), see `compose`.
CHARACTER = {
    0: dict(height=-4, lean=3, bob=1.4, bob2=0, bob_side=0, shift=5, shift2=0, hip_roll=1.8, hip_roll2=0, hip_pitch=0.6, hip_pitch1=0,
            hip_yaw=0, hip_yaw2=0, roll=2.2, roll2=0, pitch=0.6, pitch1=0, counter=0, yaw=0, breath=2.6, breath_rate=2,
            head=-2, nod=1.0, nod2=0, arm=0, arm_pitch=2, elbow=3, wing=3, wing1=0, wing_at=0.1, wing_lag=0.05, flutter=0.6,
            shrug=((0.62, 0.1, 9), (0.74, 0.08, 5)), tail=3, tail_yaw=6, tail_lag=0.07, chin=2, chin_move=0.8,
            gaze=((0.4, 0.14, 16), (0.86, 0.1, -13)), tilt=((0.4, 0.2, 7),), chin_open=((0.42, 0.06, 6),),
            gesture={'R': ((0.25, 0.25, 8),)}),
    2: dict(ticks=18, speed=16, height=-6, lean=5, head=-3, bob=5, bob2=1, bob_side=1.2, hip_yaw=8, hip_roll=4.5, roll=5, yaw=2.2,
            counter=1.5, shift=7, arm=20, arm_at=0.0, arm_pitch=4, elbow=10, elbow_extra=6, arm_out=2,
            wing=6, wing1=1.5, wing_up=4, wing_back=5, beat=3, wing_at=0.3, beat_at=0.4, wing_lag=0.11, flutter=1,
            tail=7, tail_yaw=7, tail_lag=0.09, lift={'front': 0, 'hind': 30}, settle=1.5, heel=7,
            leg_lift={'LH': 1.0, 'RH': 0.9}),
    3: dict(ticks=26, speed=10, height=-12, lean=15, head=7, neck=4, bob=4.5, hip_yaw=4.5, hip_roll=3.5, roll=4.2, yaw=1.2, shift=8,
            arm=8, arm_at=0.1, arm_pitch=2, elbow=4, elbow_extra=4, arm_out=5, wing=3, wing1=1, wing_up=-2, wing_back=3, beat=1.5,
            wing_at=0.3, wing_lag=0.14, tail=4, tail_yaw=5, tail_lag=0.1, lift={'front': 0, 'hind': 20}, peel={'front': 0, 'hind': -6},
            settle=1.5, heel=7, leg_lift={'LH': 1.0, 'RH': 0.85}),
    4: dict(ticks=12, speed=36, height=-14, lean=17, head=14, neck=10, bob=11, bob2=1.5, hip_yaw=9, hip_roll=4, roll=4.5, yaw=2.5, counter=1.3,
            arm=16, arm_at=0.25, arm_pitch=-3, elbow=10, elbow_extra=8, arm_out=4, wing=8, wing1=2, wing_up=10, wing_back=11, beat=14,
            beat_at=0.45, wing_at=0.4, wing_lag=0.1, flutter=2, tail=9, tail_yaw=6, tail_lag=0.07, tail_up=8,
            leg_lift={'LH': 1.0, 'RH': 0.92}, heel=0),
}
OTHER = {      # cycle B: what changes from cycle A, as factors on A's numbers or the leg settings
    2: dict(scale=dict(bob=1.15, lean=1.15, hip_yaw=1.15, roll=1.1, arm=0.85, beat=1.5, wing=1.2, head=1.3),
            leg_lift={'LH': 0.9, 'RH': 1.08}, touchdown={'LH': 0.0, 'RH': 0.53}, settle=2.5, heel=8),
    3: dict(scale=dict(bob=1.15, lean=0.95, arm=1.2, roll=1.1, shift=1.1, wing=1.3),
            leg_lift={'LH': 0.88, 'RH': 1.1}, touchdown={'LH': 0.0, 'RH': 0.51}, settle=2.5, heel=8),
    4: dict(scale=dict(lean=1.1, arm=0.9, hip_yaw=1.1, beat=0.7, wing=0.8), leg_lift={'LH': 0.92, 'RH': 1.0}),
}
for slot, character in CHARACTER.items():
    PROFILE['gaits'][slot].update(character)
for slot, spec in OTHER.items():
    cfg = PROFILE['gaits'][slot]
    other = {k: v for k, v in spec.items() if k != 'scale'}
    other.update({k: cfg[k] * f for k, f in spec['scale'].items()})
    cfg.update(cycles=2, compose=compose, other=other)


def prepare(model, skeleton):
    """Fill what is read off the rig: each foot's toe direction and the pivot of the sole (the toe joint)."""
    import animsheet
    pose = animsheet.slot_frames(model, len(skeleton), 0)[0][0]
    for name, toe in TOE_OF.items():
        PROFILE['paw_rest'][name] = list(pose[toe][6:9])
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
    skeleton = json.loads((ROOT / 'content/species/327-gargoylemon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof['gait'], indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
