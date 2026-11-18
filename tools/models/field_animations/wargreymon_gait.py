"""WarGreymon's field gaits (species 373): idle, walk, tired walk and run driven by one gait phase on its own two legs.

WarGreymon is a heavy armoured dinosaur warrior. Bone 1 is the pelvis with the two legs (10-12 left, 13-15 right: thigh,
shin, foot; the foot has no toe bone), the loincloth 16 and the two side plates 17 (left) and 18 (right); the chest 2
carries the neck 3, the head 4 with its helmet 5, the shoulders 6 (left) and 8 (right) with the huge clawed forearms 7 and 9
under them, and the two back plates 19 and 20. There is no tail bone. Forward is -z.

The clips this module replaces (`war_greymon.py`, then the chibi proportions) were a single 22-tick cycle of plain sines:
both arms a mirrored 34 degree pendulum locked to the legs, a bob with a quick fourth harmonic that made the body spring,
an upper body that hardly turned, a head that only counter-pitched and back plates that moved 0.6 degrees. Everything
repeated exactly every step, and the 73-tick idle was a few tenths of a degree: a wind-up toy.

Here `quadruped.py` plants each foot (two-bone IK, the sole flat on the floor, the foot rolling over its ball) and the
legs step in turn half a cycle apart; one phase then drives everything above them (`body`): the pelvis shifts over the
loaded foot, turns its hips against the chest (which counter-rotates a little later) and rolls, the body sinks onto
each landing, each arm swings against the leg of its side with the heavy claw late, the head follows the chest late and
stays level, and the back plates, the loincloth and the side plates trail. Each walking clip is two cycles that differ (one
leg lifts higher or lands earlier, the weight sinks deeper, the arm swings looser) and are eased into one another; arms,
claws, head, plates and loincloth are then run through loose springs (a lag and a small overshoot each) and the chest
rides on a spring of the pelvis' height, so it sinks a moment after every landing. The battle idle (slot 33) plays the
source game's own clip, fitted to this rig (battle_idle).

The walk is a long, weighted stride of a warrior in no hurry, the tired walk a slumped, dragging step with the claws
hanging and the head down, the run a leaning charge with both feet off the floor between strides and the claws trailing.

`build` runs the chibi reshaping first and writes the clips on its result; nothing is stored but the overlay's recipe
name in content/models/imports/species.py. Offline: `python3 -m tools.models.field_animations.wargreymon_gait --source
EDIT.MMD --out AFTER.MMD` with EDIT.MMD the model `tools/models/edit.py get 373` makes.
"""
import argparse
import copy
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
from tools.models.field_animations.quadruped import mul, tr, rot, set_rot  # noqa: E402

SPECIES = 373
BATTLE_LEAN = 5                     # degrees the battle idle's chest leans back (battle_idle)
EXACT_SLOTS = {0, 1, 2, 3, 4, 0x21, 0x22, 0x23, 0x24, 0x35}   # field, battle and Buster Dive: never re-encoded
TAU = 2 * math.pi
DEG = 4096 / 360
PELVIS, CHEST, NECK, HEAD, HELMET = 1, 2, 3, 4, 5
CLOTH, TASSET_L, TASSET_R, PLATE_L, PLATE_R = 16, 17, 18, 19, 20
LEGS = {'LH': (10, 11, 12, -1, False), 'RH': (13, 14, 15, 1, False)}
THIGH = {'LH': 10, 'RH': 13}
ARMS = {'L': (6, 7, -1), 'R': (8, 9, 1)}        # shoulder, claw, side (+1 = x > 0)
# Conventions of the rotation matrices: a positive pitch leans forward and swings a hanging arm back; a positive yaw
# turns the left side back; a positive roll lifts the left side.


def harm(phase, *terms):
    """A sum of cosines: terms are (amplitude, rate, delay in cycles)."""
    return sum(a * math.cos(TAU * rate * (phase - delay)) for a, rate, delay in terms)


def bump(phase, centre, width):
    """A smooth hump of 1 at `centre` falling to 0 `width` cycles away (cosine-squared, wrapping round the loop)."""
    d = (phase - centre + 0.5) % 1.0 - 0.5
    return math.cos(math.pi * d / width / 2) ** 2 if abs(d) < width else 0.0


def body(rig, cfg, phase, pose, hist):
    """Pelvis height, sway and turns, the chest, neck and head, arms, back plates, all as closed loops of `phase`."""
    c, W0, rest = cfg, rig.still, rig.rest
    R0 = lambda b: rig.R(W0, b)  # noqa: E731
    td = c['touchdown']
    left_at, right_at = td['LH'], td['RH']                   # touchdown phases (the weight lands on that side)
    mid_l = left_at + c['duty']['LH'] / 2                    # middle of the left stance
    mid_r = right_at + c['duty']['RH'] / 2
    bob = harm(phase, (c['bob'], 2, c['high']), (c['bob2'], 4, c['high'] + 0.02), (c['bob1'], 1, c['high'] + 0.18))
    pose[PELVIS][7] = rest[PELVIS][7] - c['height'] - bob
    # the pelvis slides over the loaded foot (left stance: x < 0), each side a little differently
    over = (-c['shift'] * math.cos(TAU * (phase - mid_l)) * (1 if math.cos(TAU * (phase - mid_l)) > 0 else c['shift_r'])
            + c['shift3'] * math.cos(3 * TAU * (phase - mid_l - 0.04)))
    pose[PELVIS][6] = rest[PELVIS][6] + over
    # hips: pitch twice a cycle, yaw (the leg that lands is the hip that leads) and roll once
    hp = c['tilt'] + harm(phase, (c['hip_pitch'], 2, c['pitch_at']), (c['hip_pitch1'], 1, c['pitch_at'] + 0.1))
    hy = -harm(phase, (c['hip_yaw'], 1, left_at + c['yaw_at']), (c['hip_yaw3'], 3, left_at + c['yaw_at'] + 0.03))
    hr = harm(phase, (c['hip_roll'], 1, mid_l), (c['hip_roll3'], 3, mid_l + 0.05))
    lag = c['lag']
    # chest: counter-turns against the hips and a little later; leans; rolls the other way; breathes
    cp = (c['lean'] + harm(phase - lag, (c['pitch'], 2, c['pitch_at'] + 0.03), (c['pitch1'], 1, c['pitch_at'] + 0.14))
          + c['breath'] * math.sin(TAU * (phase - 0.1)))
    cy = -c['counter'] * hy + harm(phase - lag, (c['yaw'], 1, left_at + c['yaw_at'] + 0.55))
    cr = -c['counter_roll'] * hr + harm(phase - lag, (c['roll'], 1, mid_l + 0.5), (c['roll3'], 3, mid_l + 0.55))
    Wt = {0: [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}
    Wt[PELVIS] = mul(rot([hp, hy, hr]), R0(PELVIS))
    set_rot(pose, PELVIS, Wt[PELVIS], hist)

    def put(bone, parent, delta):
        """Give `bone` a world rotation of `delta` on its rest one; its local rotation follows from the parent's."""
        Wt[bone] = mul(delta, R0(bone))
        set_rot(pose, bone, mul(tr(Wt[parent]), Wt[bone]), hist)

    def follow(bone, parent):
        """A bone that keeps its rest rotation under its parent."""
        Wt[bone] = mul(Wt[parent], mul(tr(R0(parent)), R0(bone)))

    put(CHEST, PELVIS, rot([cp, cy, cr]))
    follow(NECK, CHEST)
    # the head holds most of its gaze: it follows the chest by `steady`, nods late, looks about and tilts
    nod = harm(phase - c['nod_lag'], (c['nod'], 2, c['pitch_at'] + 0.1), (c['nod1'], 1, c['pitch_at'] + 0.3))
    look = c['look'] * harm(phase - c['nod_lag'], (1, 1, left_at + c['yaw_at'] + 0.5))
    gaze = sum(a * bump(phase, at, w) for at, w, a in c['gaze'])
    head_tilt = sum(a * bump(phase, at, w) for at, w, a in c['head_tilt'])
    put(HEAD, NECK, rot([cp - c['steady'] * (cp - c['lean']) - c['lean'] * c['head_lean'] + nod + c['head_up'],
                         cy * (1 - c['steady']) + look + gaze, cr * (1 - c['steady']) * 0.5 + head_tilt]))
    follow(HELMET, HEAD)
    # arms: each swings against the leg of its side from the shoulder; the claw lags and bends at the elbow
    for side, (sh, claw, sd) in ARMS.items():
        mine = left_at if side == 'L' else right_at            # this arm swings back as its own leg lands
        amp = c['arm'] * c['arm_side'][side]
        swing = -harm(phase, (amp, 1, mine + 0.5 + c['arm_at']), (c['arm2'], 2, mine + 0.5 + c['arm_at'] + 0.12))
        out = c['arm_out'] * sd + c['arm_roll'] * sd * harm(phase, (1, 2, mine + c['arm_at']))
        gest = sum(a * bump(phase, at, w) for at, w, a in c['gesture'].get(side, ()))
        put_arm = mul(Wt[CHEST], mul(rot([swing + c['arm_lift'] + gest, 0, out]), mul(tr(R0(CHEST)), R0(sh))))
        Wt[sh] = put_arm
        set_rot(pose, sh, mul(tr(Wt[CHEST]), Wt[sh]), hist)
        flex = c['elbow'] * c['arm_side'][side] * harm(phase, (1, 1, mine + 0.5 + c['arm_at'] + c['elbow_lag']))
        bend = sum(a * bump(phase, at, w) for at, w, a in c['bend'].get(side, ()))
        pose[claw][3] = rest[claw][3] + round((-flex + c['elbow_extra'] + bend) * DEG)
        pose[claw][5] = rest[claw][5] + round(sd * (c['claw_roll'] * harm(phase, (1, 1, mine + 0.6)) + 0.4 * bend) * DEG)
    # the back plates: hinged armour that lifts as the chest pitches, flares in the run and settles late
    for plate, sd in ((PLATE_L, -1), (PLATE_R, 1)):
        flap = harm(phase - c['plate_lag'], (c['plate'], 2, c['pitch_at']), (c['plate1'], 1, left_at + 0.2 + (0.0 if sd < 0 else 0.5)))
        pose[plate][3] = rest[plate][3] + round((c['plate_open'] + flap) * DEG)
        pose[plate][5] = rest[plate][5] + round(sd * 0.7 * (c['plate_open'] + flap) * DEG)


def extra(rig, cfg, phase, pose):
    """The loincloth and the side plates move out of the way of the thighs (after the legs are solved)."""
    rest = rig.rest
    d = {name: pose[b][3] - rest[b][3] for name, b in THIGH.items()}
    pose[CLOTH][3] = rest[CLOTH][3] + round(min(0, d['LH'], d['RH']) * 0.8 - cfg['cloth_out'] * DEG)
    pose[TASSET_L][3] = rest[TASSET_L][3] + round(d['LH'] * cfg['tass'])
    pose[TASSET_R][3] = rest[TASSET_R][3] + round(d['RH'] * cfg['tass'])


PROFILE = dict(
    species=SPECIES, name='WarGreymon', source=None,
    parents=[-1, 0, 1, 2, 3, 4, 2, 6, 2, 8, 1, 10, 11, 1, 13, 14, 1, 1, 1, 2, 2],
    pelvis=PELVIS, chest=CHEST, neck=NECK, head=HEAD, tail=(), loose=(),
    legs=LEGS, pole_world=True, rest_plane=True, pole={False: [0.2, 0.0, -1.0]},
    paw_rest={'LH': [0, 0, -1], 'RH': [0, 0, -1]},
    sole={False: [0, 29, -45]},                                    # the foot's ball: read off the mesh in `prepare`
    reach={'front': 0, 'hind': 0},
    fold={False: 85}, clear=2,
    speed_range={0: (0, 0), 2: (15, 31), 3: (10, 20), 4: (35, 52)},
    body=body, extra=extra, tol={None: 3, 16: 7, 17: 7, 18: 7, 19: 7, 20: 7, 3: 7, 5: 7, 7: 5, 9: 5, 6: 4, 8: 4}, stance_slip=0.25,
    gaits={},
)
COMMON = dict(
    kind='walk', snap=False, arc=1.0, plateau=0.7, clear_ease=0.1, world_ease=True, fold_soft=10, slip=0.0, steps=('LH', 'RH'),
    reach={'front': 0, 'hind': 0}, lift={'front': 0, 'hind': 30}, curl={'front': 0, 'hind': 0}, peel={'front': 0, 'hind': 10},
    out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 5}, track={'front': 0, 'hind': 4}, heel=3, settle=0,
    leg_lift={'LH': 1.0, 'RH': 1.0},
    height=-10, high=0.3, bob=4, bob2=1, bob1=0.6, shift=6, shift_r=1.0, shift3=0.6,
    tilt=0, hip_pitch=1, hip_pitch1=0.4, hip_yaw=6, hip_yaw3=0.6, hip_roll=3, hip_roll3=0.5, pitch_at=0.1, yaw_at=0.05,
    lean=8, pitch=1.2, pitch1=0.6, yaw=1.5, counter=1.3, roll=1.2, roll3=0.4, counter_roll=0.8, lag=0.07, breath=0,
    steady=0.7, head_lean=0.3, head_up=0, nod=1.5, nod1=0.7, nod_lag=0.08, look=1.5, gaze=(), head_tilt=(),
    arm=14, arm2=3, arm_at=0.04, arm_side={'L': 1.0, 'R': 1.0}, arm_lift=0, arm_out=4, arm_roll=1.5,
    elbow=10, elbow_extra=0, elbow_lag=0.08, claw_roll=3, gesture={}, bend={},
    plate=3, plate1=1.5, plate_lag=0.1, plate_open=0, cloth_out=4, tass=0.5,
    follow=1.0, chest_spring=0.5,
)

# Hand-keyed feel. Each walking clip is two cycles: A is `PROFILE['gaits'][slot]`, B differs in `OTHER` (one leg lifts
# higher, a landing comes earlier, the weight sinks deeper, the swing is looser) and the clip eases from A to B and back,
# so no two steps are alike and the loop still closes.
SLOTS = {
    0: dict(name='idle', ticks=96, speed=0, steps=(), touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 1.0, 'RH': 1.0},
            peel={'front': 0, 'hind': 0}, curl={'front': 0, 'hind': 0}, heel=0, settle=0, lift={'front': 0, 'hind': 0}, height=-12, bob=0.8, bob2=0, bob1=0.9, shift=5, shift_r=1.0, shift3=0, hip_pitch=0.5, hip_pitch1=0, hip_yaw=1.2, hip_yaw3=0,
            hip_roll=1.2, hip_roll3=0, lean=5, pitch=0.5, pitch1=0, yaw=0.8, roll=0.8, roll3=0, counter=0.8, breath=1.4,
            nod=0.6, nod1=0.4, look=0, arm=3, arm2=0.8, arm_out=5, arm_roll=1.5, elbow=4, elbow_extra=5, claw_roll=2,
            plate=0.8, plate1=1.0, tass=1.0, track={'front': 0, 'hind': 14},
            gaze=((0.3, 0.16, 20), (0.78, 0.12, -14)), head_tilt=((0.3, 0.2, 6),),
            gesture={'R': ((0.55, 0.22, -10),)}, bend={'R': ((0.55, 0.22, 12),)}),
    2: dict(name='walk', ticks=22, speed=16, touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.6, 'RH': 0.6},
            lift={'front': 0, 'hind': 26}, peel={'front': 0, 'hind': 12}, curl={'front': 0, 'hind': 4}, settle=1.5, heel=4,
            leg_lift={'LH': 1.0, 'RH': 0.9}, height=-10, high=0.3, bob=5, bob2=1.8, bob1=1.0, shift=7, shift_r=0.8,
            hip_pitch=1.2, hip_yaw=9, hip_roll=4.5, lean=9, pitch=1.6, yaw=2, counter=1.5, roll=2.5, counter_roll=0.9, lag=0.08,
            nod=2, look=2, arm=22, arm2=4, arm_side={'L': 1.0, 'R': 0.85}, arm_at=0.06, arm_out=-2, elbow=16, elbow_extra=6,
            elbow_lag=0.1, claw_roll=4, plate=3.5, plate1=2, plate_lag=0.12, cloth_out=5),
    3: dict(name='tired walk', ticks=28, speed=10, touchdown={'LH': 0.0, 'RH': 0.515}, duty={'LH': 0.62, 'RH': 0.62},
            lift={'front': 0, 'hind': 21}, peel={'front': 0, 'hind': 6}, curl={'front': 0, 'hind': 3}, settle=1.5, heel=3,
            leg_lift={'LH': 1.0, 'RH': 0.78}, height=-26, high=0.33, bob=5.5, bob2=1.2, bob1=1.4, shift=9, shift_r=0.8,
            hip_pitch=1, hip_yaw=5, hip_roll=5, lean=21, pitch=1.2, yaw=1.2, counter=1.0, roll=3, counter_roll=0.7, lag=0.1,
            steady=0.3, head_lean=0.9, nod=2.5, nod1=1.2, nod_lag=0.12, look=2.5, arm=10, arm2=3, arm_side={'L': 1.0, 'R': 0.8},
            arm_at=0.1, arm_out=-2, elbow=6, elbow_extra=2, elbow_lag=0.14, claw_roll=3, plate=2, plate1=1.5, plate_lag=0.14,
            plate_open=-3, cloth_out=2),
    4: dict(name='run', kind='trot', ticks=12, speed=40, touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.36, 'RH': 0.36},
            lift={'front': 0, 'hind': 52}, peel={'front': 0, 'hind': 14}, curl={'front': 0, 'hind': 10}, arc=1.0, plateau=0.7, clear_ease=0.05,
            leg_lift={'LH': 1.0, 'RH': 0.93}, height=-10, high=0.42, bob=9, bob2=2.2, bob1=1.2, shift=5, shift_r=0.9,
            hip_pitch=2, hip_yaw=10, hip_roll=3, lean=17, pitch=2.2, yaw=2.5, counter=1.3, roll=1.5, counter_roll=0.7, lag=0.06,
            steady=0.6, head_lean=0.4, nod=2.5, look=1.5, arm=40, arm2=6, arm_side={'L': 1.0, 'R': 0.9}, arm_at=0.08,
            arm_out=8, elbow=24, elbow_extra=14, elbow_lag=0.1, claw_roll=5, plate=5, plate1=3, plate_lag=0.1, plate_open=10,
            cloth_out=8, reach={'front': 0, 'hind': 8}),
}
OTHER = {      # cycle B: what changes from cycle A; `scale` are factors on A's numbers
    2: dict(scale=dict(bob=1.2, lean=1.15, hip_yaw=1.12, roll=1.15, arm=0.85, nod=1.3, shift=1.1),
            leg_lift={'LH': 0.9, 'RH': 1.08}, touchdown={'LH': 0.0, 'RH': 0.53}, settle=2.5, heel=5),
    4: dict(scale=dict(lean=1.08, arm=0.88, hip_yaw=1.1, bob=1.1), leg_lift={'LH': 0.92, 'RH': 1.0}),
}
for slot, spec in SLOTS.items():
    PROFILE['gaits'][slot] = dict(COMMON, **spec)
for slot, spec in OTHER.items():
    cfg = PROFILE['gaits'][slot]
    other = {k: v for k, v in spec.items() if k != 'scale'}
    other.update({k: cfg[k] * f for k, f in spec['scale'].items()})
    cfg.update(cycles=2)
    cfg['other'] = other

# (rate in radians per tick, damping) of each loose follower; slower and less damped is heavier
FOLLOW = {6: (0.55, 0.55), 8: (0.55, 0.55), 7: (0.38, 0.32), 9: (0.38, 0.32),     # shoulders, then the heavy claws
          HEAD: (0.6, 0.55), HELMET: (0.45, 0.35), NECK: (0.8, 0.7),
          PLATE_L: (0.42, 0.3), PLATE_R: (0.42, 0.3), CLOTH: (0.5, 0.35), TASSET_L: (0.8, 0.6), TASSET_R: (0.8, 0.6)}


def spring(values, rate, damping):
    """A loose second-order follower of a cyclic sequence (run round three times so the loop settles)."""
    n = len(values)
    y, v = values[0], 0.0
    out = []
    for i in range(3 * n):
        x = values[i % n]
        v += rate * rate * (x - y) - 2 * damping * rate * v
        y += v
        out.append(y)
    return out[-n:]


def blend(a, b, w):
    out = []
    for ba, bb in zip(a, b):
        row = list(ba)
        for i in range(3, 6):
            row[i] = ba[i] + ((bb[i] - ba[i] + 2048) % 4096 - 2048) * w
        for i in range(6, 9):
            row[i] = ba[i] + (bb[i] - ba[i]) * w
        out.append(row)
    return out


def compose(rig, cfg, frames_a):
    """The loop of the gait's cycles (A and B eased into each other), then the loose parts run through their springs."""
    ticks, speed, cycles = cfg['ticks'], cfg['speed'], cfg.get('cycles', 1)
    if cycles > 1:
        frames_b, _ = quadruped.gait(rig, dict(cfg, **cfg['other']))
    out = []
    for i in range(ticks * cycles):
        if cycles > 1:
            w = 0.5 - 0.5 * math.cos(math.pi * i / ticks)
            pose = blend(frames_a[i % ticks], frames_b[i % ticks], w)
        else:
            pose = [list(b) for b in frames_a[i]]
        pose[0][8] = -round(speed * i)
        out.append(pose)
    total, follow = ticks * cycles, cfg['follow']
    for b, (rate, damping) in FOLLOW.items():
        for ch in (3, 4, 5):
            seq = [out[i][b][ch] for i in range(total)]
            mixed = spring(seq, rate, damping)
            for i in range(total):
                out[i][b][ch] = seq[i] + (mixed[i] - seq[i]) * follow
    # the chest rides on a spring of the pelvis' height: it sinks a moment after each landing and rises late
    heights = [out[i][PELVIS][7] for i in range(total)]
    lagged = spring(heights, 0.45, 0.4)
    for i in range(total):
        out[i][CHEST][7] += (lagged[i] - heights[i]) * cfg['chest_spring']
    closing = [list(b) for b in out[0]]
    closing[0][8] = -round(speed * total)
    out.append(closing)
    return out


for _cfg in PROFILE['gaits'].values():
    _cfg['compose'] = compose


def prepare(model, skeleton):
    """The pivot of the sole (the ball of the foot) read off the foot mesh: the mean of its lowest points, at the middle."""
    import numeric as np
    ankle = LEGS["RH"][2]
    verts = np.array(model.tmd.obj_verts(skeleton[ankle][0]))[:, :3]
    low = verts[verts[:, 1] > verts[:, 1].max() - 4]
    PROFILE['sole'][False] = [0, float(low[:, 1].mean()), float(low[:, 2].mean())]


def battle_idle(data, skeleton):
    """The source game's battle idle (slot 0x21) fitted to this rig: its deep crouch has the thighs raised 50-80 degrees,
    and the hip plates, still in the source, cut through them (as the back plates, at the source's rest, cut through the
    shoulders); the chest, 28 degrees over the field idle's, sits beyond the native range. The hip plates take their
    thigh's turn, the back plates keep the field idle's, the chest leans back 5 degrees; every other channel is the
    source's (tools/models/battle_qa.py lists the slot as polished)."""
    from tools.models import battle_restore
    import animsheet
    nb = len(skeleton)
    model = mmd.MMD.parse(data, nb)
    rest = animsheet.slot_frames(model, nb, 0)[0][0]
    frames, loop, events = animsheet.slot_frames(model, nb, 0x21)
    frames = battle_restore.pitched(frames, skeleton, {CHEST: BATTLE_LEAN})
    for pose in frames:
        for plate, thigh in ((TASSET_L, THIGH['LH']), (TASSET_R, THIGH['RH'])):
            pose[plate][3:6] = pose[thigh][3:6]
        for plate in (PLATE_L, PLATE_R):
            pose[plate][3:6] = [int(v) for v in rest[plate][3:6]]
    if [s for s, i in enumerate(model.anims.table) if i == model.anims.table[0x21]] != [0x21]:
        raise ValueError('WarGreymon: the battle idle shares its program')
    model.anims.anims[model.anims.table[0x21]] = mmd.encode_anim(frames, nb, loop, events, tol=0, repeats=True)
    return model.build()


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
        reshaped = old.build()
        profile = dict(PROFILE, source=hashlib.sha256(reshaped).hexdigest())
        result, gait = quadruped.build(reshaped, skeleton, profile)
    finally:
        exe.skeleton[SPECIES], exe.bone_count[SPECIES] = kept
    # The source game's own battle idle (0x21) is one program more than when it shared the field idle; the room for it
    # and for the Buster Dive dash written after this overlay (tools/models/buster_dive.py, slot 0x35) comes
    # from encoding the care, condition and technique clips again exactly (the same ticks in fewer bytes). Field slots,
    # battle slots and the dash's slot are not touched.
    from tools.models import battle_restore
    result = battle_idle(result, skeleton)
    result, packed = battle_restore.compact(result, len(skeleton), 0, set(range(80)) - EXACT_SLOTS)
    storage = motionstorage.audit(result, len(skeleton))
    proof = dict(proof, preceding_recipe=dict(recipe='chibi', output_sha256=proof['output_sha256']),
                 output_sha256=hashlib.sha256(result).hexdigest(), gait=gait,
                 compacted={str(s): list(v) for s, v in sorted(packed.items())},
                 resident_bytes=[storage['resident_bytes'], gait['storage']['resident_limit']])
    proof['bytes'] = [proof['bytes'][0], len(result)]
    return result, proof


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/373-wargreymon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof['gait'], indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
