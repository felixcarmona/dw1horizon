"""Mummymon's field walk, tired walk and run (species 334, slots 2, 3 and 4) with planted feet on its own two legs.

Mummymon is a bandage-wrapped mummy gunner in a purple bandana whose two long tails hang down its back, with a rifle in
its left hand. Bone 1 is the body (rest pitched forward 12 degrees) with the head 2 (and the bandana 3 on it, and the
two bandana tails 4 and 5 hanging off it), the right arm 6-7-8 (shoulder, forearm, hand), the left arm 9-10-11-12
(shoulder, upper arm, forearm, hand with the rifle) and, turning the pitch back, the hips 13 with the legs: 14-15-16
right (thigh, shin, foot) with the claws 17, and 18-19-20 left with the claws 21. Forward is -z.

What was wrong. The chibi build keeps the import's walk, tired walk and run, retargeted: the feet slid over the
floor by 66 % of the travel in the walk (90 % at worst), 202 % in the tired walk (458 % at worst) and 95 % in the run
(230 %), the tired walk was as fast as the walk and had the same 17-tick cycle, and nothing but the legs and the
arms moved against each other in the one stiff cycle each clip repeated. The mummy looked like a mannequin dragged along.

What the clips are now. `quadruped.py` plants each foot (two-bone solve on the thigh and shin, the sole flat on the floor
with the foot's own outward splay), and `body` writes everything above: the hips turn and roll against the body, the body
leans and breathes, the head follows late, the free right arm dangles and swings as a pendulum (forearm and hand a little
later each) against its leg, the left arm carries the rifle bent and swings only a little with it, and the two bandana
tails hang by gravity in the world, trailing the body's movement by a few ticks and streaming back in the run. Every
clip is two cycles long: cycle B differs from cycle A (one leg lifts higher and drags, lands a touch earlier, the body sinks
and leans a little more) and the clip eases from one to the other and back, so no two steps are alike and the loop still
closes; arms, head, tails and rifle then follow through a loose spring each.

The walk is a heavy shamble, the tired walk a low slow drag with the head hung and the free arm swinging late, the run a
leaning, committed lope with the rifle held. The idle (slot 0 and its alias 33) is the chibi build's own, unchanged.

`build` runs the chibi reshaping first and writes the three clips on its result; nothing is stored but the overlay's
recipe name in content/models/imports/species.py. Offline: `python3 -m tools.models.field_animations.mummymon_gait
--source EDIT.MMD --out AFTER.MMD` with EDIT.MMD the model `tools/models/edit.py get 334` makes.
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

SPECIES = 334
TAU = 2 * math.pi
DEG = 4096 / 360
UPPER, HEAD, HAT, STRIPS, HIPS = 1, 2, 3, (4, 5), 13
ARMS = {'R': ((6, 7, 8), 1), 'L': ((9, 10, 11, 12), -1)}    # shoulder, upper arm, [forearm,] hand; side (+1 = x > 0)
LEGS = {'LH': (18, 19, 20, -1, False), 'RH': (14, 15, 16, 1, False)}
TOE_OF = {'LH': 21, 'RH': 17}
BALL = 0.5            # the planted point of a foot: this share of the way from the ankle to the claw point


def harm(phase, *terms):
    """A sum of cosines: terms are (amplitude, rate, delay in cycles)."""
    return sum(a * math.cos(TAU * rate * (phase - delay)) for a, rate, delay in terms)


def body(rig, cfg, phase, pose, hist):
    """Height, sway and the three turns of hips and body, the head, the arms, the bandana tails; all closed loops."""
    c, W0 = cfg, rig.still
    rest = rig.rest
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
    D = {UPPER: rot([up, uy, ur])}
    Wt = {0: [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}

    def put(bone, delta):
        """Give `bone` the world rotation `delta` from its rest world rotation."""
        Wt[bone] = mul(delta, rig.R(W0, bone))
        set_rot(pose, bone, mul(tr(Wt[rig.sk[bone][1]]), Wt[bone]), hist)
        D[bone] = delta
    put(UPPER, D[UPPER])
    put(HIPS, rot([hp, hy, hr]))
    # the head keeps most of its gaze: it follows the body by 1 - `steady`, and what it does follows late
    nod = harm(phase - c['nod_lag'], (c['nod'], 2, c['nod_at']), (c['nod2'], 1, c['nod_at'] + 0.1))
    look = c['look'] * harm(phase, (1, 1, c['look_at']), (0.3, 2, c['look_at'] + 0.1))
    hd = rot([up - c['steady'] * (up - c['lean']) - c['head'] + nod, uy * 0.5 + look, ur * 0.6 + c['tilt'] * harm(phase - c['nod_lag'], (1, 1, c['roll_at'] + 0.2))])
    put(HEAD, hd)
    put(HAT, hd)
    # the bandana tails hang by gravity: against the head's lean (so they stay near the vertical), then a trailing swing
    # a few ticks late (each tail its own), streaming back a fixed amount, and a sway to the side
    for k, b in enumerate(STRIPS):
        late = c['strip_lag'] * (1 + 0.7 * k)
        back = c['strip_back'] + c['strip'] * harm(phase - late, (1, 2, c['pitch_at']), (0.5, 1, 0.1 + 0.2 * k)) \
            - c['strip_hang'] * (up - c['lean'])
        sway = c['strip_sway'] * harm(phase - late - 0.1, (1, 1, c['roll_at'])) * (1 if k == 0 else -0.8)
        put(b, rot([back, 0, sway]))
    # the arms: the shoulder swings as a pendulum against the leg on its side; each joint after it follows a little later
    for side, (chain, sd) in ARMS.items():
        leg_at = 0.0 if side == 'R' else 0.5
        k = c['arm_r'] if side == 'R' else c['arm_l']          # the carried rifle arm swings less than the dangling one
        at = c['arm_at'] + leg_at
        swing = k * c['arm'] * harm(phase, (1, 1, at), (c['arm2'], 2, at + 0.1))
        out = (c['arm_out'] if side == 'R' else c['arm_out_l']) * sd + c['arm_roll'] * sd * harm(phase, (1, 2, c['arm_at'] + 0.05))
        carry = c['carry'] if side == 'L' else 0.0
        sh_d = mul(D[UPPER], rot([swing + c['arm_lift'] + carry, 0, out]))
        put(chain[0], sh_d)
        flex_at = c['elbow_lag']
        for j, bone in enumerate(chain[1:], 1):
            joint = (c['elbow'] if side == 'R' else c['elbow_l']) * harm(phase, (1, 1, at + j * flex_at)) \
                - (c['elbow_extra'] if side == 'R' else c['elbow_extra_l']) / len(chain[1:])
            sh_d = mul(sh_d, rot([joint, 0, 0]))
            put(bone, sh_d)


PROFILE = dict(
    species=SPECIES, name='Mummymon', source=None,
    parents=[-1, 0, 1, 2, 2, 2, 1, 6, 7, 1, 9, 10, 11, 1, 13, 14, 15, 16, 13, 18, 19, 20],
    pelvis=UPPER, chest=None, neck=None, head=HEAD, tail=(), loose=(),
    legs=LEGS, pole_world=True, rest_plane=True, pole={False: [0.3, 0.0, -1.0]},
    paw_rest={'LH': [0, 0, 0], 'RH': [0, 0, 0]},     # filled from the rig below
    sole={False: [0, 0, 0]},                            # filled from the rig below
    reach={'front': 0, 'hind': 0},
    fold={False: 75}, clear=2,
    speed_range={0: (0, 0), 2: (15, 31), 3: (10, 20), 4: (35, 52)},
    body=body, floor=3.5, stance_slip=0.2,
    # the legs and the body keep the fine fit; the arms, head, tails and rifle are smooth springs that a coarser one holds
    tol={None: 5, 0: 1, 1: 1, 13: 1, 14: 1, 15: 1, 16: 1, 17: 1, 18: 1, 19: 1, 20: 1, 21: 1},
    gaits={},
)
COMMON = dict(
    kind='walk', snap=False, arc=0.5, clear_ease=0.1, world_ease=True, fold_soft=10, slip=0.0, steps=('LH', 'RH'),
    reach={'front': 0, 'hind': 0}, lift={'front': 0, 'hind': 30}, curl={'front': 0, 'hind': 0}, peel={'front': 0, 'hind': 0},
    out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 0}, track={'front': 0, 'hind': 10}, heel=0,
    high=0.1, bob=3, bob2=0.8, bob_side=0.5, height=-22, shift=5, shift2=0.8, roll_at=0.3,
    hip_tilt=0, hip_pitch=1, hip_pitch1=0.3, hip_yaw=4, hip_yaw2=0.5, hip_roll=2, hip_roll2=0.4,
    lean=0, pitch=1.5, pitch1=0.5, pitch_at=0.15, yaw=1, counter=0.9, roll=2.5, roll2=0.5, yaw_at=0.05, lag=0.07, breath=0,
    steady=0.8, head=0, tilt=0, nod=1, nod2=0.5, nod_at=0.2, nod_lag=0.06, look=0, look_at=0.3,
    arm=14, arm_r=1.0, arm_l=0.35, arm2=0, arm_at=0.0, arm_lift=0, carry=0, arm_out=5, arm_out_l=0, arm_roll=0,
    elbow=6, elbow_l=2, elbow_extra=0, elbow_extra_l=0, elbow_lag=0.05,
    strip=6, strip_lag=0.08, strip_back=0, strip_hang=0.8, strip_sway=3,
)

# Two cycles per clip: cycle A and cycle B differ and the clip eases from one into the other and back; then the arms,
# the head, the bandana tails and the rifle follow the body through a loose spring each (own delay, own overshoot).
FOLLOW = {6: (0.55, 0.5), 7: (0.6, 0.45), 8: (0.5, 0.45),                          # right arm
          9: (0.6, 0.5), 10: (0.65, 0.5), 11: (0.6, 0.5), 12: (0.6, 0.5),          # left arm, the rifle held stiffer
          HEAD: (0.7, 0.55), HAT: (0.5, 0.4), 4: (0.4, 0.3), 5: (0.35, 0.3)}        # (rad per tick, damping)


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
            # a rotation channel is an angle: unwrap it round the loop before the spring sees it
            un = [seq[0]]
            for x in seq[1:]:
                un.append(un[-1] + (x - un[-1] + 2048) % 4096 - 2048)
            mixed = spring(un, rate, damping)
            for i in range(2 * ticks):
                out[i][b][ch] = un[i] + (mixed[i] - un[i]) * follow
    closing = [list(v) for v in out[0]]
    closing[0][8] = -round(speed * 2 * ticks)
    out.append(closing)
    return out


PROFILE['gaits'] = {
    2: dict(COMMON, name='walk', ticks=15, speed=16,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.58, 'RH': 0.58}, height=-14, high=0.27, bob=6, bob2=1.0, bob_side=1.5,
            lean=8, hip_tilt=5, head=2, hip_yaw=7, hip_roll=4, roll=4, yaw=2, counter=1.2, shift=7, arm=9, arm_at=0.15, elbow=8, elbow_extra=12,
            carry=0, elbow_extra_l=16, strip=7, strip_back=14, strip_sway=4, settle=1.5, heel=3,
            lift={'front': 0, 'hind': 26}, curl={'front': 0, 'hind': 6}, leg_lift={'LH': 0.85, 'RH': 1.0}),
    3: dict(COMMON, name='tired walk', ticks=20, speed=11,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.62, 'RH': 0.62}, height=-22, high=0.3, bob=5, bob_side=1.5,
            lean=19, hip_tilt=5, head=-16, hip_yaw=4, hip_roll=3.5, roll=4, shift=9, arm=7, arm_at=0.1, elbow=4, elbow_extra=6, carry=0, elbow_extra_l=16,
            strip=5, strip_back=6, strip_sway=3, lift={'front': 0, 'hind': 18}, peel={'front': 0, 'hind': -8},
            settle=1.5, heel=3, leg_lift={'LH': 0.8, 'RH': 1.0}),
    4: dict(COMMON, name='run', kind='trot', ticks=14, speed=38,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.34, 'RH': 0.34}, height=-36, high=0.42, arc=0.6, clear_ease=0.05,
            lift={'front': 0, 'hind': 40}, bob=12, bob2=1.2, lean=20, hip_tilt=14, head=5, hip_yaw=8, hip_roll=3, roll=4, yaw=2, counter=1.2,
            arm=18, arm_at=0.25, elbow=12, elbow_extra=14, carry=0, elbow_extra_l=32, arm_l=0.3, strip=9, strip_back=40, strip_sway=4,
            leg_lift={'LH': 0.85, 'RH': 1.0}, settle=1.5, heel=3),
}
OTHER = {      # cycle B: what changes from cycle A, as factors on A's numbers or the leg settings
    2: dict(scale=dict(bob=1.2, lean=1.15, hip_yaw=1.15, roll=1.1, arm=0.7, head=1.3),
            leg_lift={'LH': 0.95, 'RH': 1.08}, touchdown={'LH': 0.0, 'RH': 0.52}, settle=2.5, heel=4),
    3: dict(scale=dict(bob=1.2, lean=0.92, arm=1.2, roll=1.1, shift=1.1),
            leg_lift={'LH': 0.88, 'RH': 1.1}, touchdown={'LH': 0.0, 'RH': 0.51}, settle=2.5, heel=4),
    4: dict(scale=dict(lean=1.1, arm=0.9, hip_yaw=1.1), leg_lift={'LH': 1.0, 'RH': 0.9}, settle=3, heel=5),
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
        PROFILE['paw_rest'][name] = list(pose[toe][6:9])     # the claw point in the foot bone's space
    toe = pose[TOE_OF['RH']][6:9]
    PROFILE['sole'][False] = [toe[0] * BALL, toe[1] * BALL, toe[2] * BALL]      # the foot stands on its ball, not on its claws


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
    skeleton = json.loads((ROOT / 'content/species/334-mummymon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof['gait'], indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
