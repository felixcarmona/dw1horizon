"""BlackWarGreymon's field gaits (species 404): WarGreymon's weighted, planted-sole gait on BlackWarGreymon's own rig.

BlackWarGreymon (an import from the World 3 disc) has the same body as WarGreymon (373: see `wargreymon_gait.py`) but
another bone tree, 24 bones, facing -z. Bone 1 is the torso and the root of everything: under it hang the waist 2 (with
the two legs 5-8 left and 9-12 right: thigh, shin, foot, claws; the front loincloth 4 and the two thigh plates 3 right and
13 left), the neck 15 with the head 16, the two arms (shoulder 18, claw 19 on the left, 20 and 21 on the right) and the two
back plates 14 (right) and 17 (left). The clips it had (the gaits recipe, then the chibi proportions) were the donor's
ones: the feet slid with the body (stance slip 75-87 %) and the speeds were off the native range.

Here the clips are WarGreymon's: `quadruped.py` plants each foot (two-bone IK, the sole flat on the floor), and one gait
phase drives the torso (weight shift, counter-turn against the hips, lag), the head, the arms (swinging against their
legs, claws trailing), the back plates, the loincloth and the thigh plates, with the same springs for follow-through;
walk and run are two cycles each, the tired walk one slumped cycle, the idle 96 ticks. The torso is the parent of the
waist, so the hook turns the torso and the waist each in its own world rotation. The celebrations (slots 11 and 42) are
not touched.

`build` takes the stored model (`SOURCE`) and writes the clips on it; the result is stored as a plain delta (`tools/models/edit.py put 404`). Offline:
`python3 -m tools.models.field_animations.blackwargreymon_gait --source EDIT.MMD --out AFTER.MMD` with EDIT.MMD the model
`tools/models/edit.py get 404` makes.
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
import animsheet  # noqa: E402
import motionstorage  # noqa: E402
from tools.models.field_animations import quadruped  # noqa: E402
from tools.models.field_animations.quadruped import mul, tr, rot, set_rot  # noqa: E402

SPECIES = 404
SOURCE = '1249018ca534b6c44398b6b4ee88c1210d343157dee1ae8fbd2fb07d3bab5be2'     # the stored model before this change
TAU = 2 * math.pi
DEG = 4096 / 360
PELVIS, WAIST, NECK, HEAD = 1, 2, 15, 16        # PELVIS is the torso: the root of the legs' chain for quadruped.py
CLOTH, TASSET_L, TASSET_R, PLATE_L, PLATE_R = 4, 13, 3, 17, 14
LEGS = {'LH': (5, 6, 7, -1, False), 'RH': (9, 10, 11, 1, False)}
THIGH = {'LH': 5, 'RH': 9}
CLAWS = {7: 8, 11: 12}
ARMS = {'L': (18, 19, -1), 'R': (20, 21, 1)}        # shoulder, claw, side (+1 = x > 0)
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
    # the torso (bone 1) is the root and the waist (bone 2, the legs' bone) hangs from it: each takes its own world turn
    Wt[PELVIS] = mul(rot([cp, cy, cr]), R0(PELVIS))
    set_rot(pose, PELVIS, Wt[PELVIS], hist)
    Wt[WAIST] = mul(rot([hp, hy, hr]), R0(WAIST))
    set_rot(pose, WAIST, mul(tr(Wt[PELVIS]), Wt[WAIST]), hist)

    def put(bone, parent, delta):
        """Give `bone` a world rotation of `delta` on its rest one; its local rotation follows from the parent's."""
        Wt[bone] = mul(delta, R0(bone))
        set_rot(pose, bone, mul(tr(Wt[parent]), Wt[bone]), hist)

    def follow(bone, parent):
        """A bone that keeps its rest rotation under its parent."""
        Wt[bone] = mul(Wt[parent], mul(tr(R0(parent)), R0(bone)))

    CHEST = PELVIS
    follow(NECK, CHEST)
    # the head holds most of its gaze: it follows the chest by `steady`, nods late, looks about and tilts
    nod = harm(phase - c['nod_lag'], (c['nod'], 2, c['pitch_at'] + 0.1), (c['nod1'], 1, c['pitch_at'] + 0.3))
    look = c['look'] * harm(phase - c['nod_lag'], (1, 1, left_at + c['yaw_at'] + 0.5))
    gaze = sum(a * bump(phase, at, w) for at, w, a in c['gaze'])
    head_tilt = sum(a * bump(phase, at, w) for at, w, a in c['head_tilt'])
    put(HEAD, NECK, rot([cp - c['steady'] * (cp - c['lean']) - c['lean'] * c['head_lean'] + nod + c['head_up'],
                         cy * (1 - c['steady']) + look + gaze, cr * (1 - c['steady']) * 0.5 + head_tilt]))
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
    species=SPECIES, name='BlackWarGreymon', source=None,
    parents=[-1, 0, 1, 2, 2, 2, 5, 6, 7, 2, 9, 10, 11, 2, 1, 1, 15, 1, 1, 18, 1, 20, 1, 22],
    pelvis=PELVIS, chest=PELVIS, neck=NECK, head=HEAD, tail=(), loose=(),
    legs=LEGS, claws=CLAWS, pole_world=True, rest_plane=True, pole={False: [0.2, 0.0, -1.0]},
    paw_rest={'LH': [0, 0, -1], 'RH': [0, 0, -1]},      # the toe direction in each foot's own space: set in `prepare`
    sole={False: [0, 29, -45]},                                    # the foot's ball: read off the mesh in `prepare`
    reach={'front': 0, 'hind': -150},
    fold={False: 110}, clear=2,
    speed_range={0: (0, 0), 2: (15, 31), 3: (10, 20), 4: (35, 52)},
    body=body, extra=extra, tol={None: 3, 4: 7, 3: 7, 13: 7, 14: 7, 17: 7, 15: 7, 19: 5, 21: 5, 18: 4, 20: 4}, stance_slip=0.25,
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
    arm=14, arm2=3, arm_at=0.04, arm_side={'L': 1.0, 'R': 1.0}, arm_lift=0, arm_out=-4, arm_roll=1.5,
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
            nod=0.6, nod1=0.4, look=0, arm=3, arm2=0.8, arm_out=-6, arm_roll=1.5, elbow=4, elbow_extra=5, claw_roll=2,
            plate=0.8, plate1=1.0, tass=1.0, track={'front': 0, 'hind': 14},
            gaze=((0.3, 0.16, 20), (0.78, 0.12, -14)), head_tilt=((0.3, 0.2, 6),),
            gesture={'R': ((0.55, 0.22, -10),)}, bend={'R': ((0.55, 0.22, 12),)}),
    2: dict(name='walk', ticks=22, speed=16, touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.6, 'RH': 0.6},
            lift={'front': 0, 'hind': 26}, peel={'front': 0, 'hind': 12}, curl={'front': 0, 'hind': 4}, settle=1.5, heel=4,
            leg_lift={'LH': 1.0, 'RH': 0.9}, height=-10, high=0.3, bob=5, bob2=1.8, bob1=1.0, shift=7, shift_r=0.8,
            hip_pitch=1.2, hip_yaw=9, hip_roll=4.5, lean=9, pitch=1.6, yaw=2, counter=1.5, roll=2.5, counter_roll=0.9, lag=0.08,
            nod=2, look=2, arm=22, arm2=4, arm_side={'L': 1.0, 'R': 0.85}, arm_at=0.06, arm_out=-6, elbow=16, elbow_extra=6,
            elbow_lag=0.1, claw_roll=4, plate=3.5, plate1=2, plate_lag=0.12, cloth_out=5),
    3: dict(name='tired walk', ticks=28, speed=10, touchdown={'LH': 0.0, 'RH': 0.515}, duty={'LH': 0.62, 'RH': 0.62},
            lift={'front': 0, 'hind': 21}, peel={'front': 0, 'hind': 6}, curl={'front': 0, 'hind': 3}, settle=1.5, heel=3,
            leg_lift={'LH': 1.0, 'RH': 0.78}, height=-26, high=0.33, bob=5.5, bob2=1.2, bob1=1.4, shift=9, shift_r=0.8,
            hip_pitch=1, hip_yaw=5, hip_roll=5, lean=21, pitch=1.2, yaw=1.2, counter=1.0, roll=3, counter_roll=0.7, lag=0.1,
            steady=0.3, head_lean=0.3, nod=2.5, nod1=1.2, nod_lag=0.12, look=2.5, arm=10, arm2=3, arm_side={'L': 1.0, 'R': 0.8},
            arm_at=0.1, arm_out=-6, elbow=6, elbow_extra=2, elbow_lag=0.14, claw_roll=3, plate=2, plate1=1.5, plate_lag=0.14,
            plate_open=2, cloth_out=2),
    4: dict(name='run', kind='trot', ticks=12, speed=40, touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.32, 'RH': 0.32},
            lift={'front': 0, 'hind': 52}, peel={'front': 0, 'hind': 14}, curl={'front': 0, 'hind': 10}, arc=1.0, plateau=0.7, clear_ease=0.05,
            leg_lift={'LH': 1.0, 'RH': 0.93}, height=-10, high=0.42, bob=9, bob2=2.2, bob1=1.2, shift=5, shift_r=0.9,
            hip_pitch=2, hip_yaw=10, hip_roll=3, lean=12, pitch=2.2, yaw=2.5, counter=1.3, roll=1.5, counter_roll=0.7, lag=0.06,
            steady=0.6, head_lean=0.4, nod=2.5, look=1.5, arm=40, arm2=6, arm_side={'L': 1.0, 'R': 0.9}, arm_at=0.08,
            arm_out=-4, elbow=24, elbow_extra=14, elbow_lag=0.1, claw_roll=5, plate=5, plate1=3, plate_lag=0.1, plate_open=10,
            cloth_out=8, reach={'front': 0, 'hind': 0}),
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
FOLLOW = {18: (0.55, 0.55), 20: (0.55, 0.55), 19: (0.38, 0.32), 21: (0.38, 0.32),     # shoulders, then the heavy claws
          HEAD: (0.6, 0.55), NECK: (0.8, 0.7),
          PLATE_L: (0.42, 0.3), PLATE_R: (0.42, 0.3), CLOTH: (0.5, 0.35), TASSET_L: (0.8, 0.6), TASSET_R: (0.8, 0.6)}
UPPER = (NECK, 14, 17, 18, 20)      # what the torso carries: it sinks a moment after each landing


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
        for b in UPPER:
            out[i][b][7] += (lagged[i] - heights[i]) * cfg['chest_spring']
    closing = [list(b) for b in out[0]]
    closing[0][8] = -round(speed * total)
    out.append(closing)
    if cfg['speed']:
        for pose in out:
            markers(pose)
    return out


MARKERS = {22: 8, 23: 12}               # the two ground markers (no mesh) ride on the claw fans, one on each foot
MODEL = {}
PARENT = {22: PELVIS, 23: 22}


def markers(pose):
    """The ground markers hang from the torso at the floor under it. They follow the feet instead (each on its claw fan's
    own origin), so a viewer that reads them as the feet sees the planted soles, not points sliding with the body."""
    import numpy
    for marker, claw in MARKERS.items():
        mats = mmd.bone_matrices(MODEL['m'], pose)          # the second marker hangs from the first: its parent is new
        parent = numpy.array(mats[PARENT[marker]], float)
        target = numpy.array([mats[claw][i][3] for i in range(3)] + [1.0])
        local = numpy.linalg.inv(parent) @ target
        pose[marker][6:9] = [round(float(v)) for v in local[:3]]


for _cfg in PROFILE['gaits'].values():
    _cfg['compose'] = compose


def prepare(model, skeleton):
    MODEL['m'] = model
    """The pivot of the sole (the ball of the foot, claws included) read off the right foot's mesh at its rest, and each
    foot's toe direction in its own space (the way the foot points in the world at rest: straight ahead, -z)."""
    import numeric as np
    ankle = LEGS["RH"][2]
    claws = CLAWS[ankle]
    idle = animsheet.slot_frames(model, len(skeleton), 0)[0][0]
    rest = [list(v) for v in idle]
    rest[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
    verts = np.array(model.tmd.obj_verts(skeleton[ankle][0]))[:, :3]
    off = np.array(rest[claws][6:9], float)
    verts = np.concatenate([verts, np.array(model.tmd.obj_verts(skeleton[claws][0]))[:, :3] + off])
    low = verts[verts[:, 1] > verts[:, 1].max() - 4]
    front = low[low[:, 2] < low[:, 2].min() + 20]       # the foot rolls over the front of its claws (they reach 100 units past the ball)
    PROFILE['sole'][False] = [0, float(low[:, 1].mean()), float(front[:, 2].mean())]
    W = mmd.bone_matrices(model, rest)
    for name, (_, _, paw, _, _) in LEGS.items():
        PROFILE['paw_rest'][name] = [-float(W[paw][2][i]) for i in range(3)]


def build(data, skeleton):
    """The model as it is stored (SOURCE) with the four clips written on it -> (bytes, proof)."""
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('BlackWarGreymon needs the model it had before this change (tools/models/edit.py get 404)')
    exe = mmd.exe()
    kept = exe.skeleton[SPECIES], exe.bone_count[SPECIES]      # the clips are built on this rig, then put back
    try:
        old = mmd.MMD.parse(data, len(skeleton))
        old.type = SPECIES
        exe.skeleton[SPECIES] = skeleton
        exe.bone_count[SPECIES] = len(skeleton)
        prepare(old, skeleton)
        result, proof = quadruped.build(data, skeleton, dict(PROFILE, source=SOURCE))
    finally:
        exe.skeleton[SPECIES], exe.bone_count[SPECIES] = kept
    # slot 33 (the battle idle) plays the new idle too, and its own copy goes
    model = mmd.MMD.parse(result, len(skeleton))
    model.type = SPECIES
    model.anims.table[33] = model.anims.table[0]
    used = sorted({i for i in model.anims.table if i is not None})
    renumber = {i: k for k, i in enumerate(used)}
    model.anims.anims = [model.anims.anims[i] for i in used]
    model.anims.table = [None if i is None else renumber[i] for i in model.anims.table]
    result = model.build()
    proof['output_sha256'] = hashlib.sha256(result).hexdigest()
    proof['changed_slots'] = sorted(set(proof['changed_slots']) | {33})
    proof['storage'] = motionstorage.require(result, len(skeleton))
    return result, proof


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/404-blackwargreymon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
