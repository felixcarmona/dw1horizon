"""Growlmon's field gaits (species 320): idle, walk, tired walk and run with planted feet on its own two legs.

Growlmon is a heavy red dragon-dinosaur: a big head with a lower jaw and a crest, short arms ending in claws with a blade
at each elbow, a thick body on two digitigrade legs and a long three-link tail. Bone 1 is the upper body (rest pitched
forward 1.6 degrees) with the arms (2, 3, 5 right: shoulder, elbow, hand, and the elbow blade 4; 9, 10, 12 left with the
blade 11), the neck 6 with the head 7 on it and the jaw 8; bone 13 is the hips under it (it turns the pitch back) with the
tail 14-16 and the legs 17-20 (left) and 21-24 (right): thigh, shin, ankle and foot (the claws). Forward is -z.

The imported clips drove the legs with rotations from another rig: the soles slid over the floor (98 % and 119 % of the
travel in the walk and tired walk, 340 % at worst), the swinging feet were thrown 80 to 130 units off the floor in
23, 27 and 19 ticks, the tail hardly moved and the arms folded stiffly against the chest. Here `quadruped.py` plants each foot (two-bone IK on
the thigh and shin, the sole flat on the floor and the foot keeping its own outward splay), the legs step in turn at
half a cycle, and `body` writes everything above them: the hips turn against the shoulders, the upper body rolls and
shifts over the loaded foot, the arms hang bent and swing a little late, the neck and head follow the chest by a
spring each, the jaw opens a little with the effort and the tail trails the hips link by link, each a few ticks later
than the one before and a little more.

The character is a heavy brute: the walk is a slow, wide, weighty plod with the chest turning, the tired walk a low drag
with the head hung and the tail near the ground, the run a long committed gallop with real flight between the strides,
the chest leaning in, the head forward with the jaw open and the tail streaming out behind. The idle keeps both feet
planted: the weight rolls from one to the other, the chest breathes, the head looks aside, the jaw works, an arm lifts
and the tail sways.

Every walking clip is two cycles long (cycle A and cycle B differ: another leg lift, heel strike, landing time and bob,
eased into each other) so no two steps are alike; the arms, head, jaw and tail then follow the body through a loose
spring each. Nothing is stored but the delta of the model (content/modeldelta).

Offline: `tools/models/edit.py get 320` on the commit before this change, then
`python3 -m tools.models.field_animations.growlmon_gait --source THAT.MMD --out AFTER.MMD` and `edit.py put 320 AFTER.MMD`.
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
from tools.models.field_animations import growlmon_face as face  # noqa: E402
from tools.models.field_animations import quadruped  # noqa: E402
from tools.models.field_animations.quadruped import mul, tr, rot, set_rot  # noqa: E402

SPECIES = 320
SOURCE_TIM = '609ffd64a3a4144c6ecf66caa0efb92f93dcf2daad4fe2eb3b4ea80104f6617c'   # the texture before this change
SOURCE = 'a407d8adc1f47dab2ffcebd03d6ee568d85930c55bfeb0aa8a7c774b0e764142'   # `edit.py get 320` before this change
TAU = 2 * math.pi
DEG = 4096 / 360
UPPER, HIPS, NECK, HEAD, JAW = 1, 13, 6, 7, 8
TAIL = (14, 15, 16)
ARMS = {'R': (2, 3, 5, 1), 'L': (9, 10, 12, -1)}      # shoulder, elbow (the blade rides on it), hand, side (+1 = x > 0)
LEGS = {'LH': (17, 18, 19, -1, False), 'RH': (21, 22, 23, 1, False)}
TOE_OF = {'LH': 20, 'RH': 24}


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
    species=SPECIES, name='Growlmon', source=SOURCE,
    parents=[-1, 0, 1, 2, 3, 3, 1, 6, 7, 1, 9, 10, 10, 1, 13, 14, 15, 13, 17, 18, 19, 13, 21, 22, 23],
    pelvis=UPPER, chest=None, neck=None, head=HEAD, tail=(), loose=(),
    legs=LEGS, pole_world=True, rest_plane=True, pole={False: [0.3, 0.0, -1.0]},
    paw_rest={'LH': [0, 0, 0], 'RH': [0, 0, 0]},     # filled from the rig below
    sole={False: [0, 0, 0]},                            # filled from the rig below
    reach={'front': 0, 'hind': 0},
    fold={False: 30}, clear=2,
    speed_range={0: (0, 0), 2: (15, 31), 3: (10, 20), 4: (35, 52)},
    body=body, floor=9, stance_slip=0.2, events=lambda slot, total: face_events(slot, total),
    gaits={},
)
COMMON = dict(
    kind='walk', snap=False, arc=0.5, clear_ease=0.1, world_ease=True, fold_soft=10, slip=0.0, steps=('LH', 'RH'),
    reach={'front': 0, 'hind': 0}, lift={'front': 0, 'hind': 30}, curl={'front': 0, 'hind': 0}, peel={'front': 0, 'hind': 0},
    out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 20}, track={'front': 0, 'hind': 10}, heel=0,
    high=0.1, bob=3, bob2=0.8, bob_side=0.5, height=-22, shift=5, shift2=0.8, roll_at=0.3,
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
FOLLOW = {2: (0.5, 0.5), 3: (0.55, 0.45), 5: (0.45, 0.4),            # right arm: shoulder, elbow, hand   (rad per tick, damping)
          9: (0.5, 0.5), 10: (0.55, 0.45), 12: (0.45, 0.4),          # left arm
          NECK: (0.6, 0.55), HEAD: (0.5, 0.45), JAW: (0.45, 0.35),
          14: (0.45, 0.4), 15: (0.38, 0.33), 16: (0.32, 0.28)}      # the tail: each link looser and later


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
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 1.0, 'RH': 1.0}, track={'front': 0, 'hind': 24}, height=-12, bob=1.2, bob2=0, bob_side=0, shift=4, shift2=0,
            hip_yaw=0, hip_yaw2=0, hip_roll=1.5, hip_roll2=0, hip_pitch=0.6, hip_pitch1=0, roll=2, roll2=0, yaw=0, pitch=0.6, pitch1=0,
            counter=0, lean=2, head=0, nod=0.8, nod2=0, look=0, arm=0, elbow=3, breath=1.6, tail=1.5, tail1=1, tail_yaw=3, tail_yaw2=0,
            gaze=((0.5, 0.2, 20), (0.88, 0.1, -8)), tilt=((0.5, 0.22, 5),), jaw_open=((0.62, 0.1, 10),)),
    2: dict(COMMON, name='walk', ticks=16, speed=16, reach={'front': 0, 'hind': -30},
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 9 / 16, 'RH': 8.5 / 16}, lift={'front': 0, 'hind': 22}, peel={'front': 0, 'hind': -3},
            height=-10, high=0.27, bob=6, bob2=1.0, bob_side=1.0, hip_yaw=5, hip_roll=3.5, roll=3, arm=10, elbow=6, lean=2, head=3),
    3: dict(COMMON, name='tired walk', ticks=22, speed=11, reach={'front': 0, 'hind': -30},
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 14 / 22, 'RH': 14 / 22}, height=-16, high=0.3, bob=6.5, lift={'front': 0, 'hind': 24},
            peel={'front': 0, 'hind': -6}, lean=10, head=-8, arm=5, elbow=3, hip_yaw=3.5, hip_roll=3, shift=8, roll=3.5, bob_side=1.2),
    4: dict(COMMON, name='run', kind='trot', ticks=14, speed=36, reach={'front': 0, 'hind': -18}, curl={'front': 0, 'hind': -10},
            touchdown={'LH': 0.1, 'RH': 0.5}, duty={'LH': 4.5 / 14, 'RH': 3.8 / 14}, height=-14, high=0.42, world_ease=True, arc=0.3, clear_ease=0.05, lift={'front': 0, 'hind': 34},
            bob=11, bob2=1.5, lean=14, head=5, arm=16, elbow=10, elbow_extra=10, hip_yaw=7, hip_roll=3, roll=3),
}


# The character. A heavy brute: weight over the hips, the chest turning against them, the arms carried bent and ready
# (a small late swing, never pendulums), the head forward on a thick neck with the jaw working, the tail trailing.
CHARACTER = {
    0: dict(height=-8, lean=1, head=-2, hip_roll=2.0, roll=2.4, shift=5, elbow=3, elbow_extra=12, arm_lift=-6, arm_out=5, bob=1.4, breath=2.2,
            jaw=2, jaw_work=1.5, jaw_rate=1),
    2: dict(height=-10, lean=4, head=-2, bob=6.5, hip_yaw=8, hip_roll=4.5, roll=5, yaw=2.5, counter=1.4, shift=7,
            arm=8, arm_at=0.2, arm_lift=-6, arm_out=5, elbow=8, elbow_extra=14, wrist=6, hand_hold=4, lift={'front': 0, 'hind': 22},
            tail=3.5, tail1=2, tail_yaw=6, tail_lag=0.06, jaw=2, settle=1.5, heel=3, curl={'front': 0, 'hind': 6},
            leg_lift={'LH': 1.0, 'RH': 0.88}),
    3: dict(height=-16, lean=14, head=-16, bob=5.5, hip_yaw=4, hip_roll=3.5, roll=4, shift=9, arm=3.5, arm_at=0.1, arm_lift=-18, arm_out=6,
            elbow=3, elbow_extra=4, lift={'front': 0, 'hind': 14}, peel={'front': 0, 'hind': -5}, tail=2, tail1=1, tail_yaw=5, tail_up=-6,
            tail_lag=0.08, jaw=4, settle=1.5, heel=3, leg_lift={'LH': 1.0, 'RH': 0.85}),
    4: dict(height=-6, lean=18, head=-4, bob=10, hip_yaw=9, hip_roll=4, roll=4.5, yaw=2.5, counter=1.3, arm=14, arm_at=0.25,
            elbow=14, elbow_extra=20, arm_lift=-20, arm_out=4, tail=4, tail1=2, tail_yaw=7, tail_up=3, tail_lag=0.07, jaw=12, jaw_work=5, jaw_rate=2,
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
    # slot 36 was a separate 21-tick copy of the run (39.5 units a tick): it plays the new run too, and the copy goes
    model = mmd.MMD.parse(result, len(skeleton))
    model.type = SPECIES
    model.anims.table[36] = model.anims.table[4]
    used = sorted({i for i in model.anims.table if i is not None})
    renumber = {i: k for k, i in enumerate(used)}
    model.anims.anims = [model.anims.anims[i] for i in used]
    model.anims.table = [None if i is None else renumber[i] for i in model.anims.table]
    result = model.build()
    proof['output_sha256'] = hashlib.sha256(result).hexdigest()
    proof['changed_slots'] = sorted(set(proof['changed_slots']) | {36})
    proof['storage'] = motionstorage.require(result, len(skeleton))
    return result, proof


# the eye (tick, state) plans of each clip, irregular on purpose; every plan ends in the open eye. Idle: three blinks and a
# quick double one; walk and run: one or two; tired: slower and heavier (two ticks to shut, longer shut).
FACE = {
    0: face.blink(11) + face.blink(44, closed=3) + face.blink(53) + face.blink(82),
    2: face.blink(5) + face.blink(19, closed=3),
    3: face.blink(6, closed=3, heavy=True) + face.blink(27, closed=2, heavy=True),
    4: face.blink(9),
}


def face_events(slot, total):
    return face.events(FACE[slot], total)


def texture(tim):
    """The texture before this change (SOURCE_TIM) -> the same with the eye frames in their spare texels."""
    if hashlib.sha256(tim).hexdigest() != SOURCE_TIM:
        raise ValueError('Growlmon needs the texture it had before this change')
    t = mmd.Tim4(tim)
    face.stamp(t)
    out = t.to_bytes()
    assert len(out) == len(tim)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    p.add_argument('--tex', type=Path, help='the texture before this change (edit.py get 320), with --out-tex')
    p.add_argument('--out-tex', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/320-growlmon.json').read_text())['model']['skeleton']
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
