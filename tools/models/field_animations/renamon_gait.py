"""Renamon's field idle, walk, tired walk and run (species 354, slots 0, 2, 3 and 4) as one body on planted feet.

Renamon is a fox on the Leomon skeleton, 22 bones: a body (bone 1) with the hips (2) under it, the legs (thigh, shin,
ankle, toe: 3-4-5-6 on the side x > 0, 7-8-9-10 on x < 0), the plumed tail (11-12-13-14, hung from the hips), the head
(15) and the two arms hung from the body (16-17-18 on x < 0, 19-20-21 on x > 0: upper arm, forearm, hand). Forward is -z.

What was wrong. The chibi build keeps the import's field clips, retargeted, and only the legs of them were rewritten:
in the walk, the tired walk and the run the tail and the hands play the idle's own loop, copied tick by tick (their
rotation ranges equal the idle's to a tenth of a degree), the head and the two body bones move a few degrees, and each
shoulder and elbow turns in one channel only. So the legs stride on a cycle of their own and the upper body sways on
another that has nothing to do with them: stiff, unrelated to the feet, robotic. The feet themselves were already planted.

What the clips are now. One gait phase drives the whole body. `quadruped.py` plants each foot (two-bone solve on thigh
and shin, the sole flat on the floor) and the two legs step at half a cycle; `body` writes everything above them from
the same phase: the hips turn and roll against the body, the body winds against the hips, the arms swing from the shoulders
against the legs on their sides with a soft elbow and the hand late, the head follows late and steady, and the tail's four
segments each follow the one before (a wave runs down it) while its root turns against the hips. Every clip is two cycles
long: cycle B differs from cycle A (one leg lifts higher, lands a touch earlier, the body sinks and leans a little more) and
the clip eases from one to the other and back so that no two steps are alike and the loop still closes; the loose parts
(arms, head, tail) then follow through a loose second-order spring each. The idle is a gentle loop of 60 ticks (breathing,
the weight shifting between the feet, the head looking about, the tail and the hands drifting) with no translation, only
rotations, so that the integer root steps stay smooth.

`build` runs the chibi reshaping first and writes the four clips on its result; nothing is stored but the overlay's
recipe name in content/models/imports/species.py. Offline: `python3 -m tools.models.field_animations.renamon_gait
--source EDIT.MMD --out AFTER.MMD` with EDIT.MMD the model `tools/models/edit.py get 354` makes with its slot aliases
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

SPECIES = 354
TAU = 2 * math.pi
DEG = 4096 / 360
UPPER, HIPS, HEAD = 1, 2, 15
TAIL = (11, 12, 13, 14)
# shoulder, forearm, hand and the side's sign in x (the model's left arm, 16-18, stands at x < 0)
ARMS = {'R': (19, 20, 21, 1), 'L': (16, 17, 18, -1)}
LEGS = {'RH': (3, 4, 5, 1, False), 'LH': (7, 8, 9, -1, False)}
TOE_OF = {'RH': 6, 'LH': 10}


def harm(phase, *terms):
    """A sum of cosines: terms are (amplitude, rate, delay in cycles)."""
    return sum(a * math.cos(TAU * rate * (phase - delay)) for a, rate, delay in terms)


def body(rig, cfg, phase, pose, hist):
    """Height, sway and the turns of hips and body, the head, the arms, the hands and the tail from one phase; closed loops."""
    c, W0 = cfg, rig.still
    rest = rig.rest
    bob = harm(phase, (c['bob'], 2, c['high']), (c['bob2'], 4, c['high'] + 0.03), (c['bob_side'], 1, c['high'] + 0.2))
    pose[UPPER][7] = rest[UPPER][7] - c['height'] - bob
    pose[UPPER][6] = rest[UPPER][6] + harm(phase, (c['shift'], 1, c['roll_at']), (c['shift2'], 3, c['roll_at'] + 0.07))
    # the hips: pitch twice a cycle, yaw and roll once
    hp = c['hip_tilt'] + harm(phase, (c['hip_pitch'], 2, c['pitch_at']), (c['hip_pitch1'], 1, c['pitch_at'] + 0.12))
    hy = -harm(phase, (c['hip_yaw'], 1, c['yaw_at']), (c['hip_yaw2'], 3, c['yaw_at'] + 0.05))   # the hip of the leg that lands leads
    hr = harm(phase, (c['hip_roll'], 1, c['roll_at'] + 0.5), (c['hip_roll2'], 3, c['roll_at'] + 0.57))
    # the body turns against the hips, a little later, and leans into the stride; it breathes
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
    # the head keeps most of its gaze: it follows the body by 1 - `steady`, and what it does follows late
    nod = harm(phase - c['nod_lag'], (c['nod'], 2, c['nod_at']), (c['nod2'], 1, c['nod_at'] + 0.1))
    look = c['look'] * harm(phase, (1, 1, c['look_at']))
    put(HEAD, UPPER, rot([up - c['steady'] * (up - c['lean']) - c['head'] + nod,
                          uy * 0.55 + look + c['head_yaw'] * harm(phase - 2 * lag, (1, 1, c['yaw_at'] + 0.1)),
                          ur * 0.6 + c['head_roll'] * harm(phase - 2 * lag, (1, 1, c['roll_at'] + 0.2))]))
    # the arms: the shoulder swings against the leg on its side, the forearm and the hand follow late
    for side, (sh, el, hand, sd) in ARMS.items():
        at = c['arm_at'] + (0.5 if side == 'R' else 0.0)
        swing = c['arm'] * harm(phase, (1, 1, at), (c['arm2'], 2, at + 0.1))
        out = c['arm_out'] * sd + c['arm_roll'] * sd * harm(phase, (1, 2, c['arm_at'] + 0.05))
        sh_d = mul(D1, rot([swing + c['arm_lift'], 0, out]))
        Wt[sh] = mul(sh_d, rig.R(W0, sh))
        set_rot(pose, sh, mul(tr(Wt[UPPER]), Wt[sh]), hist)
        flex = c['elbow'] * harm(phase, (1, 1, at + c['elbow_lag']), (c['elbow2'], 2, at + c['elbow_lag'] + 0.1))
        pose[el][3] = rest[el][3] + round((flex - c['elbow_extra']) * DEG)
        wrist = c['wrist'] * harm(phase, (1, 1, at + 2 * c['elbow_lag']))
        flick = c['flick'] * max(0.0, harm(phase, (1, 1, at + 3 * c['elbow_lag'] + 0.3 * (side == 'L')))) ** 3
        pose[hand][3] = rest[hand][3] + round((0.5 * flex + wrist - c['wrist_hold'] + flick) * DEG)
        pose[hand][5] = rest[hand][5] + round(sd * c['wrist_roll'] * harm(phase, (1, 1, at + 3 * c['elbow_lag'])) * DEG)
    # the tail: each segment follows the one before it a little later while its root turns against the hips
    for k, b in enumerate(TAIL):
        d = c['tail_lag'] * k
        pitch = c['tail_out'] * c['tail_fall'][k] + c['tail_pitch'] * harm(phase - d, (1, 2, c['pitch_at'] + 0.1)) + c['tail_pitch1'] * harm(phase - d, (1, 1, 0.3))
        yaw = c['tail_yaw'] * harm(phase - d, (1, 1, c['yaw_at'] + 0.5))
        pose[b][3] = rest[b][3] + round(pitch * DEG)
        pose[b][4] = rest[b][4] + round(yaw * DEG)
        pose[b][5] = rest[b][5] + round(c['tail_roll'] * harm(phase - d - 0.08, (1, 1, c['yaw_at'] + 0.5)) * DEG)


PROFILE = dict(
    species=SPECIES, name='Renamon', source=None,
    parents=[-1, 0, 1, 2, 3, 4, 5, 2, 7, 8, 9, 2, 11, 12, 13, 1, 1, 16, 17, 1, 19, 20],
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
    out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 0}, track={'front': 0, 'hind': 12}, heel=0,
    high=0.1, bob=3, bob2=0.8, bob_side=0.5, height=-22, shift=5, shift2=0.8, roll_at=0.3,
    hip_tilt=0, hip_pitch=1, hip_pitch1=0.3, hip_yaw=4, hip_yaw2=0.5, hip_roll=2, hip_roll2=0.4,
    lean=0, pitch=1.5, pitch1=0.5, pitch_at=0.15, yaw=1, counter=0.9, roll=2.5, roll2=0.5, yaw_at=0.05, lag=0.07, breath=0,
    steady=0.8, head=0, nod=1, nod2=0.5, nod_at=0.2, nod_lag=0.06, look=0, look_at=0.3, head_yaw=0, head_roll=0,
    arm=14, arm2=0, arm_at=0.0, arm_lift=0, arm_out=0, arm_roll=0, elbow=6, elbow2=0, elbow_extra=0, elbow_lag=0.05,
    wrist=0, wrist_hold=0, wrist_roll=0,
    tail_lag=0.05, tail_out=0, tail_fall=(1, 1, 1, 1), wave=0, flick=0, tail_pitch=1.2, tail_pitch1=0.5, tail_yaw=3, tail_roll=3,
)

FOLLOW = {16: (0.55, 0.5), 17: (0.6, 0.45), 18: (0.5, 0.45),          # left arm: shoulder, forearm, hand
          19: (0.55, 0.5), 20: (0.6, 0.45), 21: (0.5, 0.45),          # right arm
          HEAD: (0.7, 0.55),
          11: (0.6, 0.5), 12: (0.55, 0.45), 13: (0.5, 0.4), 14: (0.45, 0.35)}   # tail; (rad per tick, damping)


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
    0: dict(COMMON, name='idle', ticks=60, speed=0, steps=(), touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 1.0, 'RH': 1.0},
            height=0, bob=0, bob2=0, bob_side=0, shift=0, shift2=0, hip_yaw=1.5, hip_yaw2=0, hip_roll=2.5, hip_roll2=0, hip_pitch=0.4,
            hip_pitch1=0, roll=2.5, roll2=0, wave=2, flick=16, yaw=1, counter=0.5, lean=2, pitch=0.5, pitch1=0, breath=1.6, nod=1.2, nod2=0, look=6, look_at=0.3,
            head_yaw=3, head_roll=5, arm=3, arm_out=-8, elbow=4, wrist=4, wrist_roll=4, tail_pitch=2, tail_pitch1=0, tail_yaw=12, tail_roll=8,
            tail_lag=0.1, compose=compose_idle, cycles=1),
    2: dict(COMMON, name='walk', ticks=14, speed=16,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.6, 'RH': 0.6}, lift={'front': 0, 'hind': 34}, arc=0.7, track={'front': 0, 'hind': 6},
            height=-4, high=0.27, bob=9, bob2=1.2, bob_side=1.0, lean=3, hip_yaw=10, hip_roll=5, roll=4, wave=3, flick=22, arm=24, elbow=12, elbow_extra=-32,
            arm_out=-10, arm_lift=-24, wrist=12, wrist_roll=10, tail_out=14, tail_fall=(1, 0.5, 0.2, 0), tail_pitch=2, tail_yaw=8, tail_roll=5, tail_lag=0.09, head_yaw=4, head_roll=4, nod=2),
    3: dict(COMMON, name='tired walk', ticks=20, speed=11, arc=0.7,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.62, 'RH': 0.62}, height=-8, high=0.3, bob=5, lift={'front': 0, 'hind': 24},
            peel={'front': 0, 'hind': -6}, track={'front': 0, 'hind': 6}, lean=12, head=16, arm=12, elbow=4, elbow_extra=-8, hip_yaw=5, hip_roll=4.5, shift=7, roll=4.5, wave=3, bob_side=1.2,
            arm_out=-6, arm_lift=-14, wrist=6, tail_out=12, tail_fall=(1, 0.5, 0.2, 0), tail_pitch=1.5, tail_yaw=7, tail_roll=5, tail_lag=0.09, head_yaw=3, head_roll=4),
    4: dict(COMMON, name='run', kind='trot', ticks=12, speed=40,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.32, 'RH': 0.32}, height=-12, high=0.42, arc=0.45, lift_soft=1.15, lift={'front': 0, 'hind': 46},
            bob=7, bob2=1.5, lean=20, head=10, wave=3, flick=15, arm=34, elbow=14, elbow_extra=-30, hip_yaw=8, hip_roll=3, roll=3,
            arm_out=-10, arm_lift=-26, arm_at=-0.25, wrist=8, tail_out=30, tail_fall=(1, 0.5, 0.2, 0), track={'front': 0, 'hind': 0}, tail_pitch=2, tail_yaw=5, tail_roll=4, tail_lag=0.12, head_roll=3),
}
OTHER = {      # cycle B: what changes from cycle A, as factors on A's numbers or the leg settings
    2: dict(scale=dict(bob=1.2, lean=1.2, hip_yaw=1.15, roll=1.15, arm=0.8, wave=1.5, flick=0.3, tail_yaw=1.3, head_roll=-0.8, wrist_roll=1.3), leg_lift={'LH': 0.9, 'RH': 1.08},
            touchdown={'LH': 0.0, 'RH': 0.52}, settle=0.8, heel=6),
    3: dict(scale=dict(bob=1.15, lean=0.95, arm=1.2, roll=1.1, shift=1.1, wave=1.4, tail_yaw=1.25, head_roll=-0.8), leg_lift={'LH': 0.88, 'RH': 1.1},
            touchdown={'LH': 0.0, 'RH': 0.51}, settle=0.8, heel=6),
    4: dict(scale=dict(lean=1.1, arm=0.9, hip_yaw=1.1, wave=1.5, flick=0.4, tail_yaw=1.25, head_roll=-0.8), leg_lift={'LH': 0.7, 'RH': 1.0}, touchdown={'LH': 0.0, 'RH': 0.5}, settle=0.5, heel=5),
}
for slot, spec in OTHER.items():
    cfg = PROFILE['gaits'][slot]
    other = {k: v for k, v in spec.items() if k != 'scale'}
    other.update({k: cfg[k] * f for k, f in spec['scale'].items()})
    cfg.update(cycles=2, compose=compose, other=other)


# The footfall: a cat's line, the hind feet landing almost in front of each other, a low smooth lift and a quiet heel.
def step_style(slot, other=None, **kw):
    cfg = PROFILE['gaits'][slot]
    cfg.update(kw)
    if other:
        cfg['other'].update(other)
step_style(2, lift={'front': 0, 'hind': 28}, arc=0.75, track={'front': 0, 'hind': 1}, other=dict(settle=0.5, heel=3))
step_style(3, lift={'front': 0, 'hind': 20}, arc=0.75, track={'front': 0, 'hind': 1}, other=dict(settle=0.5, heel=3))
step_style(4, lift={'front': 0, 'hind': 40}, track={'front': 0, 'hind': 0}, other=dict(settle=0.3, heel=4))


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
    skeleton = json.loads((ROOT / 'content/species/354-renamon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof['gait'], indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
