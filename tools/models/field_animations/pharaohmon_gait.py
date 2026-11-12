"""Pharaohmon's field tired walk and run (species 319, slots 3 and 4) on its own two legs with planted feet.

Pharaohmon is a golden golem-pharaoh: a heavy torso with a broad collar and a cape down its back (bone 1, rest pitch
-6 degrees), a big head with the headdress (5), long arms ending in huge fists (2-3-4 on the side x < 0, 8-9-10 on the
side x > 0: upper arm, forearm, fist), a loose cape (6-7) and under the torso the hips (11) with the loincloth (16-17)
and the legs, thigh, shin, ankle block and claws (12-13-14-15 right, 18-19-20-21 left). Forward is -z.

What was wrong. The chibi build keeps the import's tired walk and run, retargeted: the tired walk slid its soles over
the floor by 138 % of the travel on average (466 % at worst), the torso leant 42 degrees past the idle's stance, and the
run threw the torso 65 degrees forward with the legs folded up behind it and the feet off the floor all but a tick or
two of 24. Nobody walks that way: the pharaoh looked like a bent statue dragged over the ground. The walk (slot 2) and
the idle are the chibi build's own and stay byte for byte as they are; they set the character, a low heavy lumber with
a modest forward lean, and the two clips here are written to be the same creature slower and faster.

What the clips are now. `quadruped.py` plants each foot (two-bone solve on the thigh and shin, the sole flat on the
floor), and `body` writes everything above: the hips turn and roll against the torso, the torso leans a controlled
amount and breathes, the head follows late, the arms swing as pendulums (the forearm and the fist a little later each, the
two sides against the legs), the cape and the loincloth trail. Every clip is two cycles long: cycle B differs from cycle
A (one leg lifts higher, lands a touch earlier, the torso sinks and leans a little more) and the clip eases from one to
the other and back, so no two steps are alike and the loop still closes; the arms, hands, head, cape and loincloth then
follow through a loose spring each.

The tired walk is slow (11 units a tick, two cycles of 28 ticks), the body low and the torso rolling with each heavy
step, the head hung, the arms hanging and swaying late. The run is a controlled forward lean with a drive phase (the
stance is a third of the cycle, both feet are off the floor between), the arms bent and pumping against the legs and the
cape streaming.

`build` runs the celebrations recipe (and so the chibi reshaping) first and writes the two clips on its result; nothing
is stored but the overlay's recipe name in content/models/imports/species.py. Offline: `python3 -m
tools.models.field_animations.pharaohmon_gait --source EDIT.MMD --out AFTER.MMD` with EDIT.MMD the model
`tools/models/edit.py get 319` makes.
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

SPECIES = 319
TAU = 2 * math.pi
DEG = 4096 / 360
UPPER, HEAD, CAPE, HIPS, CLOTH = 1, 5, (6, 7), 11, (16, 17)
# shoulder, upper arm's elbow, fist; side's sign in x
ARMS = {'R': ((8, 9, 10), 1), 'L': ((2, 3, 4), -1)}
LEGS = {'RH': (12, 13, 14, 1, False), 'LH': (18, 19, 20, -1, False)}
TOE_OF = {'RH': 15, 'LH': 21}


def harm(phase, *terms):
    """A sum of cosines: terms are (amplitude, rate, delay in cycles)."""
    return sum(a * math.cos(TAU * rate * (phase - delay)) for a, rate, delay in terms)


def body(rig, cfg, phase, pose, hist):
    """Height, sway and the turns of hips and torso, the head, the arms, the cape and the loincloth; closed loops."""
    c, rest = cfg, rig.rest
    W0 = rig.still
    bob = harm(phase, (c['bob'], 2, c['high']), (c['bob2'], 4, c['high'] + 0.03), (c['bob_side'], 1, c['high'] + 0.2))
    pose[UPPER][7] = rest[UPPER][7] - c['height'] - bob
    pose[UPPER][6] = rest[UPPER][6] + harm(phase, (c['shift'], 1, c['roll_at']), (c['shift2'], 3, c['roll_at'] + 0.07))
    hp = c['hip_tilt'] + harm(phase, (c['hip_pitch'], 2, c['pitch_at']), (c['hip_pitch1'], 1, c['pitch_at'] + 0.12))
    hy = harm(phase, (c['hip_yaw'], 1, c['yaw_at']), (c['hip_yaw2'], 3, c['yaw_at'] + 0.05))
    hr = harm(phase, (c['hip_roll'], 1, c['roll_at'] + 0.5), (c['hip_roll2'], 3, c['roll_at'] + 0.57))
    lag = c['lag']
    breath = c['breath'] * math.sin(TAU * (phase - 0.1))
    up = c['lean'] + harm(phase - lag, (c['pitch'], 2, c['pitch_at']), (c['pitch1'], 1, c['pitch_at'] + 0.12)) + breath
    uy = -c['counter'] * hy + harm(phase - lag, (c['yaw'], 1, c['yaw_at'] + 0.1))
    ur = harm(phase - lag, (c['roll'], 1, c['roll_at']), (c['roll2'], 3, c['roll_at'] + 0.06))
    D = {}                                   # each bone's world delta from its rest world rotation
    D[UPPER] = rot([up, uy, ur])
    D[HIPS] = rot([hp, hy, hr])
    Wt = {0: [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}

    def put(bone, delta):
        Wt[bone] = mul(delta, rig.R(W0, bone))
        set_rot(pose, bone, mul(tr(Wt[rig.sk[bone][1]]), Wt[bone]), hist)
    put(UPPER, D[UPPER])
    put(HIPS, D[HIPS])
    # the head keeps most of its gaze: it follows the torso by 1 - `steady`, and what it does follows late
    nod = harm(phase - c['nod_lag'], (c['nod'], 2, c['nod_at']), (c['nod2'], 1, c['nod_at'] + 0.1))
    roll = harm(phase - c['nod_lag'], (c['head_roll'], 1, c['roll_at'] + 0.2))
    put(HEAD, rot([up - c['steady'] * (up - c['lean']) - c['head'] + nod, uy * 0.5 + c['look'] * harm(phase, (1, 1, c['look_at'])),
                   ur * 0.6 + roll]))
    # the arms: each side against its leg; the upper arm swings from the shoulder as a pendulum, the forearm and the fist follow
    for side, ((sh, el, fi), sd) in ARMS.items():
        at = c['arm_at'] + (0.0 if side == 'R' else 0.5)
        swing = c['arm'] * harm(phase, (1, 1, at), (c['arm2'], 2, at + 0.1))
        out = c['arm_out'] * sd + c['arm_roll'] * sd * harm(phase, (1, 2, c['arm_at'] + 0.05))
        sh_d = mul(D[UPPER], rot([swing + c['arm_lift'], 0, out]))
        put(sh, sh_d)
        flex = c['elbow'] * harm(phase, (1, 1, at + c['elbow_lag'])) - c['elbow_extra']
        put(el, mul(sh_d, rot([flex, 0, 0])))
        hand = c['fist'] * harm(phase, (1, 1, at + 2 * c['elbow_lag'])) - c['fist_hold']
        put(fi, mul(mul(sh_d, rot([flex, 0, 0])), rot([hand, 0, 0])))
    # the cape and the loincloth trail the body: a few ticks later, a little more
    for k, b in enumerate(CAPE):
        lagged = c['lean'] + harm(phase - c['cape_lag'] * (k + 1), (c['pitch'], 2, c['pitch_at']))
        put(b, rot([c['cape_out'] + c['cape'] * harm(phase - c['cape_lag'] * (k + 1), (1, 2, c['pitch_at']), (0.5, 1, 0.0)) + 0.4 * (lagged - up), 0,
                    c['cape_roll'] * harm(phase - c['cape_lag'] * (k + 1), (1, 1, c['roll_at']))]))
    for k, b in enumerate(CLOTH):
        put(b, rot([c['cloth_out'] + c['cloth'] * harm(phase - c['cloth_lag'] * (k + 1), (1, 2, c['pitch_at'])), 0, 0]))


PROFILE = dict(
    species=SPECIES, name='Pharaohmon', source=None,
    parents=[-1, 0, 1, 2, 3, 1, 1, 6, 1, 8, 9, 1, 11, 12, 13, 14, 11, 16, 11, 18, 19, 20],
    pelvis=UPPER, chest=None, neck=None, head=HEAD, tail=(), loose=(),
    legs=LEGS, pole_world=True, rest_plane=True, pole={False: [0.3, 0.0, -1.0]},
    paw_rest={'LH': [0, 0, 0], 'RH': [0, 0, 0]},     # filled from the rig below
    sole={False: [0, 0, 0]},
    reach={'front': 0, 'hind': 0},
    fold={False: 75}, clear=2,
    speed_range={0: (0, 0), 2: (15, 31), 3: (10, 20), 4: (35, 52)},
    body=body, floor=3, stance_slip=0.2,
    gaits={},
)
COMMON = dict(
    kind='walk', snap=False, arc=0.5, clear_ease=0.1, world_ease=True, fold_soft=10, slip=0.0, steps=('LH', 'RH'),
    reach={'front': 0, 'hind': 0}, lift={'front': 0, 'hind': 30}, curl={'front': 0, 'hind': 0}, peel={'front': 0, 'hind': 0},
    out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 0}, track={'front': 0, 'hind': 0}, heel=0,
    high=0.1, bob=3, bob2=0.8, bob_side=0.5, height=-22, shift=5, shift2=0.8, roll_at=0.3,
    hip_tilt=0, hip_pitch=1, hip_pitch1=0.3, hip_yaw=4, hip_yaw2=0.5, hip_roll=2, hip_roll2=0.4,
    lean=0, pitch=1.5, pitch1=0.5, pitch_at=0.15, yaw=1, counter=0.9, roll=2.5, roll2=0.5, yaw_at=0.05, lag=0.07, breath=0,
    steady=0.8, head=0, nod=1, nod2=0.5, nod_at=0.2, nod_lag=0.06, look=0, look_at=0.3, head_roll=0,
    arm=14, arm2=0, arm_at=0.0, arm_lift=0, arm_out=0, arm_roll=0, elbow=6, elbow_extra=0, elbow_lag=0.05, fist=0, fist_hold=0,
    cape=4, cape_lag=0.08, cape_out=0, cape_roll=0, cloth=2, cloth_lag=0.1, cloth_out=0,
)
FOLLOW = {2: (0.55, 0.5), 3: (0.6, 0.45), 4: (0.5, 0.45), 8: (0.55, 0.5), 9: (0.6, 0.45), 10: (0.5, 0.45),
          HEAD: (0.7, 0.55), 6: (0.45, 0.35), 7: (0.4, 0.3), 16: (0.45, 0.35), 17: (0.4, 0.3)}   # (rad per tick, damping)


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
    3: dict(COMMON, name='tired walk', ticks=28, speed=11,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.58, 'RH': 0.58}, height=-8, high=0.3, bob=3, arc=1.2,
            lift={'front': 0, 'hind': 22}, peel={'front': 0, 'hind': -8}, lean=25, head=-10, arm=9, arm_at=0.1, elbow=5, shift=8,
            arm_out=-14, wide={'front': 0, 'hind': 10}, track={'front': 0, 'hind': 20}, roll=3.5, hip_roll=3, hip_yaw=4, settle=1.5, heel=3, leg_lift={'LH': 1.0, 'RH': 0.9}),
    4: dict(COMMON, name='run', kind='trot', ticks=12, speed=36,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.31, 'RH': 0.31}, height=0, high=0.42, arc=0.6, clear_ease=0.05,
            peel={'front': 0, 'hind': -30}, lift={'front': 0, 'hind': 45}, bob=11, lean=30, head=4, arm=26, arm_at=0.25, elbow=12,
            elbow_extra=10, arm_out=-10, wide={'front': 0, 'hind': 18}, track={'front': 0, 'hind': 10}, hip_yaw=6, hip_roll=3, roll=3, leg_lift={'LH': 1.0, 'RH': 0.93}),
}
# Cycle B: what changes from cycle A, as factors on A's numbers or the leg settings; the clip eases from A to B and back.
OTHER = {
    3: dict(scale=dict(bob=1.25, lean=0.9, arm=1.25, roll=1.15, shift=1.1, head=1.2), leg_lift={'LH': 0.88, 'RH': 1.08},
            touchdown={'LH': 0.0, 'RH': 0.51}),
    4: dict(scale=dict(lean=1.08, arm=0.9, hip_yaw=1.1, bob=1.1), leg_lift={'LH': 0.93, 'RH': 1.0}),
}
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
    """The celebrations build with the two clips written on it -> (bytes, proof)."""
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
                 output_sha256=gait['output_sha256'], gait=gait, resident_bytes=[gait['storage']['resident_bytes'],
                                                                                gait['storage']['resident_limit']])
    proof['bytes'] = [proof['bytes'][0], len(result)] if 'bytes' in proof else [len(data), len(result)]
    return result, proof


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/319-pharaohmon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof['gait'], indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
