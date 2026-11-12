"""Marsmon's field gaits (species 297): walk, tired walk and run with planted feet on its own two legs.

Marsmon is a caped, armoured biped. Bone 1 is the upper body (rest pitched forward 15 degrees) with the shoulders and
arms (2-4 right, 5-7 left: shoulder, elbow, fist), the head 8 and the cape 9-11 (three links hanging behind); bone 12 is
the hips under it (it turns the pitch back, so the legs stand upright) with the legs 13-16 left and 17-20 right: hip and
thigh, knee and shin, ankle and heel, then the toes. Forward is -z. The hips of both legs sit on the body's centre
line, the thighs open outwards to the knees and the boots splay outwards by 30 degrees.

The imported clips drove the legs with rotations from another rig: the right foot crossed over to the left side of the
body (both soles within 50 units of the left side's own line), the soles slid over the floor, the stride was a few tens
of units. Here `quadruped.py` plants each foot (two-bone IK on the thigh and shin, the heel flat on the floor and the
boot keeping its own outward splay), the legs step in turn at half a cycle with a track wide enough to keep the two
boots apart, and `body` writes everything above them: the hips turn against the shoulders, the upper body rolls and
shifts over the loaded foot, the fists swing against the legs and open at the end of the swing, the head steadies and the
cape trails late. The character is a proud, heavy warlord: the walk is a swagger with the chest out and the chin up, the
tired walk a weary slouch with the head down and the cape hanging, the run a lean-in with the cape streaming. The idle
(150 ticks, 5 s) keeps both boots planted: the weight rolls slowly from one to the other, the chest breathes, the head
looks aside and tilts, one fist rises to the chest and the cape flicks; no beat repeats inside the loop.

Offline: `tools/models/edit.py get 297` on the commit before this change, then
`python3 -m tools.models.field_animations.marsmon_gait --source THAT.MMD --out AFTER.MMD` and `edit.py put 297 AFTER.MMD`.
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

SPECIES = 297
SOURCE = 'c516c2ad02934317d94b25e088f8927c63427dfde8ecb26734b2e7499d25794e'   # `edit.py get 297` before this change
TAU = 2 * math.pi
DEG = 4096 / 360
UPPER, HIPS, HEAD = 1, 12, 8
ARMS = {'R': (2, 3, 4, 1), 'L': (5, 6, 7, -1)}       # shoulder, elbow, fist, side (+1 = x > 0)
CAPE = (9, 10, 11)
LEGS = {'LH': (13, 14, 15, -1, False), 'RH': (17, 18, 19, 1, False)}
TOE_OF = {'LH': 16, 'RH': 20}


def harm(phase, *terms):
    """A sum of cosines: terms are (amplitude, rate, delay in cycles)."""
    return sum(a * math.cos(TAU * rate * (phase - delay)) for a, rate, delay in terms)


def bump(phase, centre, width):
    """A smooth hump of 1 at `centre` falling to 0 `width` cycles away (cosine-squared, wrapping round the loop)."""
    d = (phase - centre + 0.5) % 1.0 - 0.5
    return math.cos(math.pi * d / width / 2) ** 2 if abs(d) < width else 0.0


def body(rig, cfg, phase, pose, hist):
    """Height, sway and the three turns of hips and upper body, the fists, the head and the cape; all closed loops."""
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
    Wt = {0: [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}
    Wt[UPPER] = mul(rot([up, uy, ur]), rig.R(W0, UPPER))
    Wt[HIPS] = mul(rot([hp, hy, hr]), rig.R(W0, HIPS))

    def put(bone, parent, delta):
        Wt[bone] = mul(delta, rig.R(W0, bone))
        set_rot(pose, bone, mul(tr(Wt[parent]), Wt[bone]), hist)
    set_rot(pose, UPPER, Wt[UPPER], hist)
    put(HIPS, UPPER, rot([hp, hy, hr]))
    # the head keeps most of its gaze: it follows the upper body by `steady`
    nod = harm(phase - c['nod_lag'], (c['nod'], 2, c['nod_at']), (c['nod2'], 1, c['nod_at'] + 0.1))
    look = c['look'] * harm(phase, (1, 1, c['look_at']), (0.3, 2, c['look_at'] + 0.1))
    gaze = sum(a * bump(phase, at, w) for at, w, a in c['gaze'])            # (centre, width, degrees): looks aside, tilts
    tilt = sum(a * bump(phase, at, w) for at, w, a in c['tilt'])
    put(HEAD, UPPER, rot([up - c['steady'] * (up - c['lean']) - c['head'] + nod + c['head_up'],
                           uy * 0.5 + look + gaze, ur * 0.6 + tilt]))
    # the fists swing against the legs on the shoulders; the elbows follow
    for side, (sh, el, fist, sd) in ARMS.items():
        leg = 'LH' if side == 'R' else 'RH'       # an arm goes forward with the opposite leg
        swing = c['arm'] * harm(phase, (1, 1, c['arm_at'] + (0.0 if leg == 'LH' else 0.5)))
        out = c['arm_out'] * sd
        gest = sum(a * bump(phase, at, w) for at, w, a in c['gesture'].get(side, ()))   # a raised arm: (centre, width, degrees)
        Wt[sh] = mul(Wt[UPPER], mul(rot([swing + c['arm_lift'] + gest, 0, out]), mul(tr(rig.R(W0, UPPER)), rig.R(W0, sh))))
        set_rot(pose, sh, mul(tr(Wt[UPPER]), Wt[sh]), hist)
        flex = c['elbow'] * harm(phase, (1, 1, c['arm_at'] + 0.1 + (0.0 if leg == 'LH' else 0.5)))
        bend = sum(a * bump(phase, at, w) for at, w, a in c['bend'].get(side, ()))
        pose[el][3] = rest[el][3] + round((flex - c['elbow_extra'] - bend) * DEG)
        hand = c['fist'] * harm(phase, (1, 1, c['arm_at'] + c['fist_lag'] + (0.0 if leg == 'LH' else 0.5)))
        pose[fist][3] = rest[fist][3] + round((0.5 * flex + hand - 0.5 * bend) * DEG)
    # the cape hangs behind and trails the body: each link a little later and a little more
    for k, b in enumerate(CAPE):
        late = c['cape_lag'] * (k + 1.5)
        d = harm(phase - late, (c['cape'] * (0.6 + 0.5 * k), 2, c['pitch_at']), (c['cape1'] * (0.6 + 0.5 * k), 1, 0.0))
        flick = sum(a * bump(phase - c['cape_lag'] * k * 2, at, w) for at, w, a in c['flick'])
        pose[b][3] = rest[b][3] + round((d + flick * (0.7 + 0.3 * k) + (c['cape_out'] if k == 0 else c['cape_drape'])) * DEG)


PROFILE = dict(
    species=SPECIES, name='Marsmon', source=SOURCE,
    parents=[-1, 0, 1, 2, 3, 1, 5, 6, 1, 1, 9, 10, 1, 12, 13, 14, 15, 12, 17, 18, 19],
    pelvis=UPPER, chest=None, neck=None, head=HEAD, tail=(), loose=(),
    legs=LEGS, pole_world=True, rest_plane=True, pole={False: [0.4, 0.0, -1.0]},
    paw_rest={'LH': [0, 0, 0], 'RH': [0, 0, 0]},     # filled from the rig below
    sole={False: [0, 0, 0]},                            # filled from the rig below
    reach={'front': 0, 'hind': 0},
    fold={False: 105}, clear=0,
    speed_range={0: (0, 0), 2: (15, 31), 3: (10, 20), 4: (35, 52)},
    body=body, floor=3, stance_slip=0.2,
    gaits={},
)
COMMON = dict(
    kind='walk', snap=False, arc=0.5, clear_ease=0.1, world_ease=True, fold_soft=10, slip=0.0, steps=('LH', 'RH'),
    reach={'front': 0, 'hind': -30}, lift={'front': 0, 'hind': 30}, curl={'front': 0, 'hind': 0}, peel={'front': 0, 'hind': 0},
    out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 0}, track={'front': 0, 'hind': 14}, heel=0,
    high=0.1, bob=3, bob2=0.8, bob_side=0.5, height=-22, shift=5, shift2=0.8, roll_at=0.3,
    hip_tilt=0, hip_pitch=1, hip_pitch1=0.3, hip_yaw=4, hip_yaw2=0.5, hip_roll=2, hip_roll2=0.4,
    lean=0, pitch=1.5, pitch1=0.5, pitch_at=0.15, yaw=1, counter=0.9, roll=2.5, roll2=0.5, yaw_at=0.05, lag=0.07,
    steady=0.8, head=0, head_up=0, nod=1, nod2=0.5, nod_at=0.2, nod_lag=0.06, look=0, look_at=0.3,
    arm=14, arm_at=0.0, arm_lift=0, arm_out=0, elbow=6, elbow_extra=0,
    cape=4, cape1=2, cape_out=0, cape_drape=0, cape_lag=0.07, fist=0, fist_lag=0.15,
    gaze=(), tilt=(), gesture={}, bend={}, flick=(),
)
PROFILE['gaits'] = {
    # standing: both boots planted, the weight rolling slowly from one to the other, a breath, a proud look aside, one
    # raised hand and a flick of the cape, spread over 5 s so no beat repeats
    0: dict(COMMON, name='idle', ticks=150, speed=0, steps=(),
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 1.0, 'RH': 1.0}, track={'front': 0, 'hind': 26}, height=-24, bob=1.2, bob2=0, bob_side=0, shift=5, shift2=0,
            hip_yaw=0, hip_yaw2=0, hip_roll=1.5, hip_roll2=0, hip_pitch=0.6, hip_pitch1=0, roll=2, roll2=0, yaw=0, pitch=0.6, pitch1=0,
            counter=0, lean=3, head=3, nod=0.8, nod2=0, look=0, arm=0, elbow=5, fist=0, cape=2, cape1=1, cape_lag=0.03, cape_drape=3,
            gaze=((0.55, 0.22, 22), (0.9, 0.12, -9)), tilt=((0.55, 0.25, 6),),
            gesture={'R': ((0.25, 0.2, -10),)}, bend={'R': ((0.25, 0.2, 38),)}, flick=((0.7, 0.12, 10),)),
    # a long unhurried step on a short leg: a bent stance leg, a clear knee lift, flat boots (a toe-up peel at lift-off
    # turned the trailing foot backwards), the pelvis sinking on each landing and rising over the planted foot (two bobs a
    # cycle, 16 / 18 / 21 units peak to peak), the hips turning, the fists swinging against the legs
    2: dict(COMMON, name='walk', ticks=22, speed=16,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.57, 'RH': 0.57}, lift={'front': 0, 'hind': 46},
            peel={'front': 0, 'hind': -8}, lean=2, head=4, height=-32, high=0.27, bob=8, bob2=1.2, bob_side=1.0, hip_yaw=5, hip_roll=3.5, roll=3, arm=18, elbow=8,
            hip_pitch=1.8, shift=7, fist=14, cape=5, cape1=3, cape_lag=0.1, cape_drape=0, cape_out=0),
    3: dict(COMMON, name='tired walk', ticks=26, speed=11,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.64, 'RH': 0.64}, height=-37, high=0.3, bob=8.5, lift={'front': 0, 'hind': 28},
            peel={'front': 0, 'hind': -6}, lean=12, head=-9, arm=7, elbow=3, fist=6, cape_lag=0.12, cape_out=-1, cape_drape=-1, hip_yaw=3.5, hip_roll=3, shift=8, roll=3.5, bob_side=1.2,
            cape=3, cape1=1.5),
    4: dict(COMMON, name='run', kind='trot', ticks=14, speed=38,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.34, 'RH': 0.34}, height=-40, high=0.42, world_ease=0.85, arc=1.0, reach={'front': 0, 'hind': -30}, lift={'front': 0, 'hind': 60},
            peel={'front': 0, 'hind': 0}, bob=10, bob2=1.5, lean=16, head=6, arm=32, elbow=12, elbow_extra=25, hip_yaw=7, hip_roll=3, roll=3, fist=20,
            cape=9, cape1=4, cape_out=14, cape_drape=5, cape_lag=0.09),
}


def prepare(model, skeleton):
    """Fill what is read off the rig: each boot's toe direction and the pivot of the sole (the toe point)."""
    import animsheet
    pose = animsheet.slot_frames(model, len(skeleton), 0)[0][0]
    for name, toe in TOE_OF.items():
        off = pose[toe][6:9]                           # the toe point in the heel bone's space
        PROFILE['paw_rest'][name] = list(off)
    PROFILE['sole'][False] = list(pose[TOE_OF['RH']][6:9])


def build(data, skeleton):
    old = mmd.MMD.parse(data, len(skeleton))
    old.type = SPECIES
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = len(skeleton)
    prepare(old, skeleton)
    return quadruped.build(data, skeleton, PROFILE)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/297-marsmon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
