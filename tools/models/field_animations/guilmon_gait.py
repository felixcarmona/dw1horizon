"""Guilmon's field gaits (species 433): idle, walk, tired walk and run with planted feet on its own two legs.

Guilmon is a red dinosaur-like biped (forward is -z): a head with long ears and a jaw, short arms with big claws held
forward, a body on two digitigrade legs with four bones each (thigh, shin, ankle, claws) and a three-link tail. Bone 1
is the upper body with the right arm (2, 3, 4: shoulder, elbow, hand) and the left arm (10, 11, 12), the neck 5, the head 6
with the jaw 7 and the ears 8 and 9 on it; bone 13 is the hips with the tail 22-24 and the right leg 14-17 and the left
leg 18-21.

The imported clips drove the legs with rotations from another rig: the soles slid over the floor (up to 70 % mean and
417 % worst in the walk and tired walk), sank below it and the arms flailed out wide. Here `quadruped.py` plants each foot
(two-bone IK, the sole flat on the floor), the legs step in turn at half a cycle, and `body` writes everything above them:
the hips turn against the shoulders, the upper body rolls over the loaded foot, the arms swing a little late with the
elbows bent, the neck, head, jaw, ears and tail follow through by a spring each. Every walking clip is two cycles long
(the second differs a little) so no two steps are alike. Nothing is stored but the delta of the model.

Offline: `tools/models/edit.py get 433` on the commit before this change, then
`python3 -m tools.models.field_animations.guilmon_gait --source THAT.MMD --out AFTER.MMD` and `edit.py put 433 AFTER.MMD`.
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
import motionstorage  # noqa: E402
from tools.models.field_animations import quadruped  # noqa: E402
from tools.models.field_animations import guilmon_face as face  # noqa: E402
from tools.models.field_animations.quadruped import mul, tr, rot, set_rot  # noqa: E402

SPECIES = 433
SOURCE_TIM = '96b1f034dc3b193c6bac14f4e562ad931b0674bc1292b0a6a599c697b6f1f26f'   # the texture before this change
SOURCE = '6df45cb75ee475a109d07f8ad7c2cfc741e9a3008b0083f85f06778fba546d4b'   # `edit.py get 433` before this change
TAU = 2 * math.pi
DEG = 4096 / 360
UPPER, HIPS, NECK, HEAD, JAW = 1, 13, 5, 6, 7
EARS = (8, 9)
TAIL = (22, 23, 24)
ARMS = {'R': (2, 3, 4, 1), 'L': (10, 11, 12, -1)}      # shoulder, elbow (the blade rides on it), hand, side (+1 = x > 0)
LEGS = {'LH': (18, 19, 20, -1, False), 'RH': (14, 15, 16, 1, False)}
TOE_OF = {'LH': 21, 'RH': 17}


def harm(phase, *terms):
    """A sum of cosines: terms are (amplitude, rate, delay in cycles)."""
    return sum(a * math.cos(TAU * rate * (phase - delay)) for a, rate, delay in terms)


def bump(phase, centre, width):
    """A smooth hump of 1 at `centre` falling to 0 `width` cycles away (cosine-squared, wrapping round the loop)."""
    d = (phase - centre + 0.5) % 1.0 - 0.5
    return math.cos(math.pi * d / width / 2) ** 2 if abs(d) < width else 0.0


def body(rig, cfg, phase, pose, hist):
    """Height, sway and the three turns of hips and upper body, the arms, the neck, head and jaw and the tail; all
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
    # neck and head: the neck keeps most of its gaze and follows the chest, the head follows the neck later
    nod = harm(phase - c['nod_lag'], (c['nod'], 2, c['nod_at']), (c['nod2'], 1, c['nod_at'] + 0.1))
    look = c['look'] * harm(phase, (1, 1, c['look_at']), (0.3, 2, c['look_at'] + 0.1))
    gaze = sum(a * bump(phase, at, w) for at, w, a in c['gaze'])
    tilt = sum(a * bump(phase, at, w) for at, w, a in c['tilt'])
    put(NECK, UPPER, rot([up - c['steady'] * (up - c['lean']) - c['head'] * 0.6 + nod * 0.5 + c['head_up'],
                          uy * 0.5 + look * 0.5 + gaze * 0.5, ur * 0.6 + tilt * 0.4]))
    late = c['head_lag']
    pose[HEAD][3] = rest[HEAD][3] + round((-c['head'] * 0.4 + nod * 0.7 + harm(phase - late, (c['head_nod'], 2, c['nod_at'])) ) * DEG)
    pose[HEAD][4] = rest[HEAD][4] + round((look * 0.5 + gaze * 0.5) * DEG)
    pose[HEAD][5] = rest[HEAD][5] + round((tilt * 0.6 + harm(phase - late, (c['head_roll'], 1, c['roll_at']))) * DEG)
    jaw = c['jaw'] + c['jaw_work'] * (0.5 + 0.5 * math.sin(TAU * (c['jaw_rate'] * phase))) + \
        sum(a * bump(phase, at, w) for at, w, a in c['jaw_open'])
    pose[JAW][3] = rest[JAW][3] + round(jaw * DEG)
    # the arms hang bent from the shoulders and swing a little against the leg on their side, the elbow and hand late
    for side, (sh, el, hand, sd) in ARMS.items():
        leg_at = 0.0 if side == 'R' else 0.5
        swing = c['arm'] * harm(phase, (1, 1, c['arm_at'] + leg_at), (c['arm2'], 2, c['arm_at'] + leg_at + 0.1))
        out = c['arm_out'] * sd + c['arm_roll'] * sd * harm(phase, (1, 2, c['arm_at'] + 0.05))
        gest = sum(a * bump(phase, at, w) for at, w, a in c['gesture'].get(side, ()))
        Wt[sh] = mul(Wt[UPPER], mul(rot([swing + c['arm_lift'] + gest, 0, out]), mul(tr(rig.R(W0, UPPER)), rig.R(W0, sh))))
        set_rot(pose, sh, mul(tr(Wt[UPPER]), Wt[sh]), hist)
        flex = c['elbow'] * harm(phase, (1, 1, c['arm_at'] + leg_at + c['elbow_lag']))
        bend = sum(a * bump(phase, at, w) for at, w, a in c['bend'].get(side, ()))
        pose[el][3] = rest[el][3] + round((flex - c['elbow_extra'] - bend) * DEG)
        wrist = c['wrist'] * harm(phase, (1, 1, c['arm_at'] + leg_at + 2 * c['elbow_lag']))
        pose[hand][3] = rest[hand][3] + round((0.5 * flex + wrist - c['hand_hold'] - 0.4 * bend) * DEG)
    # the tail hangs from the hips: each link later than the one before and a little more, against the hips' yaw
    for k, b in enumerate(TAIL):
        late = c['tail_lag'] * (k + 1)
        grow = 0.6 + 0.5 * k
        pitch = harm(phase - late, (c['tail'] * grow, 2, c['pitch_at']), (c['tail1'] * grow, 1, 0.0))
        yaw = -harm(phase - late - 0.02, (c['tail_yaw'] * grow, 1, c['yaw_at']), (c['tail_yaw2'] * grow, 3, c['yaw_at'] + 0.05))
        flick = sum(a * bump(phase - late, at, w) for at, w, a in c['flick'])
        pose[b][3] = rest[b][3] + round((pitch + flick * grow + c['tail_up'] * (1 if k == 0 else 0.6)) * DEG)
        pose[b][4] = rest[b][4] + round((yaw + c['tail_side'] * (k + 1)) * DEG)


PROFILE = dict(
    species=SPECIES, name='Guilmon', source=SOURCE,
    parents=[-1, 0, 1, 2, 3, 1, 5, 6, 6, 6, 1, 10, 11, 1, 13, 14, 15, 16, 13, 18, 19, 20, 13, 22, 23],
    pelvis=UPPER, chest=None, neck=None, head=HEAD, tail=(), loose=(),
    legs=LEGS, pole_world=True, rest_plane=True, pole={False: [0.3, 0.0, -1.0]},
    paw_rest={'LH': [0, 0, 0], 'RH': [0, 0, 0]},     # filled from the rig below
    sole={False: [0, 0, 0]},                            # filled from the rig below
    reach={'front': 0, 'hind': 0},
    fold={False: 30}, clear=13,
    speed_range={0: (0, 0), 2: (15, 31), 3: (10, 20), 4: (35, 52)},
    body=body, floor=2, stance_slip=0.35, events=lambda slot, total: face_events(slot, total),
    gaits={},
)
COMMON = dict(
    kind='walk', snap=False, arc=0.5, clear_ease=0.1, world_ease=True, fold_soft=10, slip=0.0, steps=('LH', 'RH'),
    reach={'front': 0, 'hind': 0}, lift={'front': 0, 'hind': 30}, curl={'front': 0, 'hind': 0}, peel={'front': 0, 'hind': 0},
    out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 6}, track={'front': 0, 'hind': -13}, heel=0,
    plateau=0.7, high=0.1, bob=3, bob2=0.8, bob_side=0.5, height=-22, shift=5, shift2=0.8, roll_at=0.3,
    hip_tilt=0, hip_pitch=1, hip_pitch1=0.3, hip_yaw=4, hip_yaw2=0.5, hip_roll=2, hip_roll2=0.4,
    lean=0, pitch=1.5, pitch1=0.5, pitch_at=0.15, yaw=1, counter=0.9, roll=2.5, roll2=0.5, yaw_at=0.05, lag=0.07, breath=0,
    steady=0.8, head=0, head_up=0, nod=1, nod2=0.5, nod_at=0.2, nod_lag=0.06, look=0, look_at=0.3, head_lag=0.1, head_nod=1, head_roll=1,
    jaw=0, jaw_work=0, jaw_rate=1, jaw_open=(),
    arm=8, arm2=0, arm_at=0.0, arm_lift=0, arm_out=0, arm_roll=0, elbow=5, elbow_extra=0, elbow_lag=0.05, wrist=0, hand_hold=0,
    tail=3, tail1=1.5, tail_lag=0.05, tail_yaw=6, tail_yaw2=1, tail_up=0, tail_side=0,
    gaze=(), tilt=(), gesture={}, bend={}, flick=(),
)
# Hand-keyed feel. Every walking clip is two cycles long: cycle A and cycle B differ (one leg lifts higher, lands
# earlier, a different bob, a looser arm) and the clip eases from the one into the other and back, so no two steps are
# alike and the loop still closes. Then the arms, hands, neck, head, jaw and tail follow the body through a loose
# spring each (own delay, own overshoot), which the generator's plain sines cannot give them.
FOLLOW = {2: (0.5, 0.5), 3: (0.55, 0.45), 4: (0.45, 0.4),            # right arm
          10: (0.5, 0.5), 11: (0.55, 0.45), 12: (0.45, 0.4),          # left arm
          NECK: (0.6, 0.55), HEAD: (0.5, 0.45), JAW: (0.45, 0.35), 8: (0.35, 0.3), 9: (0.33, 0.3),
          22: (0.45, 0.4), 23: (0.38, 0.33), 24: (0.32, 0.28)}      # the tail


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
    0: dict(COMMON, name='idle', ticks=96, speed=0, steps=(),
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 1.0, 'RH': 1.0}, track={'front': 0, 'hind': -13}, height=-12, bob=1.2, bob2=0, bob_side=0, shift=4, shift2=0,
            hip_yaw=0, hip_yaw2=0, hip_roll=1.5, hip_roll2=0, hip_pitch=0.6, hip_pitch1=0, roll=2, roll2=0, yaw=0, pitch=0.6, pitch1=0,
            counter=0, lean=2, head=0, nod=0.8, nod2=0, look=0, arm=0, elbow=3, breath=1.6, tail=1.5, tail1=1, tail_yaw=3, tail_yaw2=0,
            gaze=((0.5, 0.2, 20), (0.88, 0.1, -8)), tilt=((0.5, 0.22, 5),), jaw_open=((0.62, 0.1, 10),)),
    2: dict(COMMON, name='walk', ticks=12, speed=15, clear=17, reach={'front': 0, 'hind': -30},
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 6.4 / 12, 'RH': 6.5 / 12}, lift={'front': 0, 'hind': 22}, peel={'front': 0, 'hind': -3},
            height=-10, high=0.27, bob=6, bob2=1.0, bob_side=1.0, hip_yaw=5, hip_roll=3.5, roll=3, arm=10, elbow=6, lean=2, head=3),
    3: dict(COMMON, name='tired walk', ticks=16, speed=10, clear=21, reach={'front': 0, 'hind': -30},
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 10.5 / 16, 'RH': 10.5 / 16}, height=-16, high=0.3, bob=6.5, lift={'front': 0, 'hind': 24},
            peel={'front': 0, 'hind': -6}, lean=10, head=-8, arm=5, elbow=3, hip_yaw=3.5, hip_roll=3, shift=8, roll=3.5, bob_side=1.2),
    4: dict(COMMON, name='run', kind='trot', ticks=12, speed=36, reach={'front': 0, 'hind': -18}, curl={'front': 0, 'hind': -10},
            touchdown={'LH': 0.1, 'RH': 0.5}, duty={'LH': 3.8 / 12, 'RH': 3.3 / 12}, height=-14, high=0.42, world_ease=True, arc=0.3, clear_ease=0.05, lift={'front': 0, 'hind': 34},
            bob=11, bob2=1.5, lean=14, head=5, arm=16, elbow=10, elbow_extra=10, hip_yaw=7, hip_roll=3, roll=3),
}


# The character. A heavy brute: weight over the hips, the chest turning against them, the arms carried bent and ready
# (a small late swing, never pendulums), the head forward on a thick neck with the jaw working, the tail trailing.
CHARACTER = {
    0: dict(height=-8, lean=1, head=-2, hip_roll=2.0, roll=2.4, shift=5, elbow=3, elbow_extra=12, arm_lift=-6, arm_out=5, bob=1.4, breath=2.2,
            jaw=2, jaw_work=2.5, jaw_rate=1,
            tail=2.5, tail1=1.5, tail_yaw=5, flick=((0.66, 0.1, 12), (0.18, 0.08, -9)), head_up=0,
            gesture={'R': ((0.3, 0.12, 14), (0.72, 0.1, -8)), 'L': ((0.55, 0.12, 16),)},
            bend={'R': ((0.3, 0.12, 12),), 'L': ((0.55, 0.12, 14), (0.85, 0.08, 8))},
            gaze=((0.2, 0.12, -16), (0.48, 0.2, 22), (0.88, 0.1, -8)), tilt=((0.5, 0.22, 6), (0.2, 0.12, -4)),
            jaw_open=((0.62, 0.1, 10), (0.9, 0.06, 5)), nod=1.2),
    2: dict(height=10, lean=0, head=-4, bob=7, bob2=1.0, hip_yaw=8, hip_roll=4.5, roll=5, yaw=2.5, counter=1.4, shift=7,
            arm=15, arm2=2.5, arm_at=0.2, arm_lift=-8, arm_out=-16, arm_roll=0, elbow=12, elbow_lag=0.12, elbow_extra=16, wrist=12, hand_hold=6, lift={'front': 0, 'hind': 22},
            tail=5, tail1=2.5, tail_yaw=8, tail_lag=0.07, jaw=2, settle=1.5, heel=3, curl={'front': 0, 'hind': 6},
            leg_lift={'LH': 1.0, 'RH': 0.88}),
    3: dict(height=-4, lean=14, head=-16, bob=5.5, hip_yaw=4, hip_roll=3.5, roll=4, shift=9, arm=5.5, arm2=1.0, arm_at=0.1, arm_lift=-18, arm_out=-18, arm_roll=0,
            elbow=4, elbow_lag=0.14, wrist=6, elbow_extra=6, lift={'front': 0, 'hind': 14}, peel={'front': 0, 'hind': -5}, tail=3, tail1=1.5, tail_yaw=6, tail_up=-6,
            tail_lag=0.09, jaw=4, settle=1.5, heel=3, leg_lift={'LH': 1.0, 'RH': 0.85}),
    4: dict(height=-6, lean=18, head=-4, bob=10, hip_yaw=9, hip_roll=4, roll=4.5, yaw=2.5, counter=1.3, arm=9, arm2=2, arm_at=0.25,
            elbow=10, elbow_lag=0.08, wrist=4, elbow_extra=20, arm_lift=-12, arm_out=-18, arm_roll=2, tail=5.5, tail1=2.5, tail_yaw=9, tail_up=3, tail_lag=0.07, jaw=12, jaw_work=5, jaw_rate=2,
            leg_lift={'LH': 1.0, 'RH': 0.92}),
}
OTHER = {      # cycle B: what changes from cycle A, as factors on A's numbers or the leg settings
    2: dict(scale=dict(bob=1.15, lean=1.15, hip_yaw=1.15, roll=1.1, arm=0.85, head=1.3),
            leg_lift={'LH': 0.9, 'RH': 1.08}, touchdown={'LH': 0.0, 'RH': 0.5}, settle=2.5, heel=2, curl={'front': 0, 'hind': 4}),
    3: dict(scale=dict(bob=1.15, lean=0.95, arm=1.2, roll=1.1, shift=1.1),
            leg_lift={'LH': 0.88, 'RH': 1.1}, touchdown={'LH': 0.0, 'RH': 0.495}, settle=2.5, heel=4),
    4: dict(scale=dict(lean=1.1, arm=0.9, hip_yaw=1.1), leg_lift={'LH': 0.92, 'RH': 1.0}),
}
for slot, character in CHARACTER.items():
    PROFILE['gaits'][slot].update(character)
for slot, spec in OTHER.items():
    cfg = PROFILE['gaits'][slot]
    other = {k: v for k, v in spec.items() if k != 'scale'}
    other.update({k: cfg[k] * f for k, f in spec['scale'].items()})
    cfg.update(cycles=2, compose=compose, other=other)


# the eye (tick, state) plans of each clip, irregular on purpose; every plan ends in the open eye
FACE = {
    0: face.blink(9, closed=3) + face.blink(43, closed=4) + face.blink(74, closed=3),
    2: face.blink(4, closed=3) + face.blink(17, closed=4),
    3: face.blink(5, closed=3, heavy=True) + face.blink(23, closed=3, heavy=True),
    4: face.blink(8, closed=3),
}


def face_events(slot, total):
    return face.events(FACE[slot], total)


def texture(tim):
    """The texture before this change (SOURCE_TIM) -> the same with the eye frames in their spare texels."""
    if hashlib.sha256(tim).hexdigest() != SOURCE_TIM:
        raise ValueError('Guilmon needs the texture it had before this change')
    t = mmd.Tim4(tim)
    face.stamp(t)
    out = t.to_bytes()
    assert len(out) == len(tim)
    return out


def prepare(model, skeleton):
    """Fill what is read off the rig: each foot's toe direction and the pivot of the sole (the claw point)."""
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
    # slot 36 was a separate 21-tick copy of the run (38.5 units a tick) and slot 33 a 43-tick copy of the idle: they play the
    # new run and idle too, and the copies go
    model = mmd.MMD.parse(result, len(skeleton))
    model.type = SPECIES
    model.anims.table[36] = model.anims.table[4]
    model.anims.table[33] = model.anims.table[0]
    used = sorted({i for i in model.anims.table if i is not None})
    renumber = {i: k for k, i in enumerate(used)}
    model.anims.anims = [model.anims.anims[i] for i in used]
    model.anims.table = [None if i is None else renumber[i] for i in model.anims.table]
    result = model.build()
    proof['output_sha256'] = hashlib.sha256(result).hexdigest()
    proof['changed_slots'] = sorted(set(proof['changed_slots']) | {33, 36})
    proof['storage'] = motionstorage.require(result, len(skeleton))
    return result, proof


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    p.add_argument('--tex', type=Path, help='the texture before this change (edit.py get 433), with --out-tex')
    p.add_argument('--out-tex', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/433-guilmon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    if a.tex:
        a.out_tex.write_bytes(texture(a.tex.read_bytes()))
    text = json.dumps(proof, indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
