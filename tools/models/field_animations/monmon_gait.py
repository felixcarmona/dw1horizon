"""Monmon's field gaits (species 352): walk, tired walk and run of a springy little monkey, one body on planted feet.

Monmon is a big-headed monkey on short legs. Its rig (21 bones, forward is -z): bone 1 is the chest (a small ball at the
shoulders) with the head 15 and its leaf crown 16, the right arm 12-14 and the left arm 17-19 (shoulder, elbow, boxing
glove) and the forked club carried on the back, 20; bone 2 is the belly under it (same pivot) with the right leg 3-5 and
the left leg 9-11 (thigh, shin, foot; the foot is one flat block, its ankle at the back) and the tail 6-8.

What was wrong. The imported walk, tired walk and run were the same slow 43 to 45 tick cycle three times over, with the
gloves held up in front of the belly: nothing in them drove the arms, head, tail or club, so the upper body stood still
while the feet shuffled, and the soles slid 61 to 244 % of the body's travel on the floor. The run was no faster in the
legs than the walk, and the tired walk looked like the walk.

What the clips are now. `quadruped.py` plants each foot (two-bone solve on thigh and shin, the sole flat on the floor)
and the two legs step at half a cycle on their own wider track, with the weight rolling over the loaded foot: the walk
a bouncy trot with a knee lift and the body sinking on every landing, the tired walk a slumped shuffle with the head
down, the arms hanging and the club heavy, the run a springy lope with a flight phase and the gloves pumping. `body`
writes everything above the feet from the one gait phase: the belly turns against the chest, the arms swing against the
legs on their sides (the elbow follows the shoulder, the glove the elbow, a little later each), the head steadies on the
body and nods late, the leaf crown and the club bob against the body, and the tail's three segments follow each other
in a wave while its root turns against the hips. Every clip is two cycles long: the second differs from the first (a
different lift, a deeper bob, a wider swing, a landing a touch later) and the clip eases from one to the other and back, so
no two steps are alike and the loop still closes; the loose parts then follow through by a spring each. The idle (slot 0)
is a new 3 s (60 tick) loop.

The face. The eye is one ring painted on the head's texture, drawn on both sides of the face (no lid bone, no separate mesh),
so the clips blink by texture moves (`monmon_face.py`): a half-shut and a shut frame sit in the texture's free rows and each
clip copies them over the eye. The idle and the walk blink once a loop, the tired walk blinks slowly and droops, the run keeps its eyes open.

Offline: `tools/models/edit.py get 352` on the commit before this change, then
`python3 -m tools.models.field_animations.monmon_gait --source THAT.MMD --out AFTER.MMD --tex THAT.TIM --out-tex AFTER.TIM`
and `edit.py put 352 AFTER.MMD AFTER.TIM`.
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
from tools.models.field_animations import monmon_face as face  # noqa: E402
from tools.models.field_animations.quadruped import mul, tr, rot, set_rot  # noqa: E402

SPECIES = 352
SOURCE = '371098f2c404da5ee55a2307e9b55c6dce61d7efc648f7e2bb7c747c850086f5'   # `edit.py get 352` before this change
SOURCE_TIM = 'd68cfc46969b2f8cc12d9cc2cd06d225e0672a890a838cc2023396bbfd8e681c'   # its texture before this change
TAU = 2 * math.pi
DEG = 4096 / 360
UPPER, HIPS, HEAD, LEAF, CLUB = 1, 2, 15, 16, 20
ARMS = {'R': (12, 13, 14, 1), 'L': (17, 18, 19, -1)}       # shoulder, elbow, glove, side (+1 = x > 0)
TAIL = (6, 7, 8)
LEGS = {'LH': (9, 10, 11, -1, False), 'RH': (3, 4, 5, 1, False)}
SOLE = [3, 14, -30]        # the ball of the foot, in the foot bone's space: the sole's pivot
MIRRORED = ((3, 9), (4, 10), (5, 11), (12, 17), (13, 18), (14, 19))


def harm(phase, *terms):
    """A sum of cosines: terms are (amplitude, rate, delay in cycles)."""
    return sum(a * math.cos(TAU * rate * (phase - delay)) for a, rate, delay in terms)


def rest_fix(rest):
    """The import's idle is caught mid-move (the left leg and arm are posed differently from the right): the left side
    takes the right one's rotations mirrored."""
    for r, l in MIRRORED:
        rx, ry, rz = rest[r][3:6]
        rest[l][3:6] = [rx, -ry, -rz]
        x, y, z = rest[r][6:9]
        rest[l][6:9] = [-x, y, z]


def body(rig, cfg, phase, pose, hist):
    """Height, sway and the turns of belly and chest, the head, the arms, the tail, the leaf crown and the club from one
    phase; closed loops."""
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
    Wt = {0: [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}
    Wt[UPPER] = mul(rot([up, uy, ur]), rig.R(W0, UPPER))
    Wt[HIPS] = mul(rot([hp, hy, hr]), rig.R(W0, HIPS))

    def put(bone, parent, delta):
        Wt[bone] = mul(delta, rig.R(W0, bone))
        set_rot(pose, bone, mul(tr(Wt[parent]), Wt[bone]), hist)
    set_rot(pose, UPPER, Wt[UPPER], hist)
    put(HIPS, UPPER, rot([hp, hy, hr]))
    # the head keeps most of its gaze: it follows the chest by 1 - `steady`, and its own nod comes late
    nod = harm(phase - c['nod_lag'], (c['nod'], 2, c['nod_at']), (c['nod2'], 1, c['nod_at'] + 0.1))
    look = c['look'] * harm(phase, (1, 1, c['look_at']))
    put(HEAD, UPPER, rot([up - c['steady'] * (up - c['lean']) - c['head'] + nod,
                          uy * 0.5 + look, ur * 0.6 + c['head_roll'] * harm(phase - 2 * lag, (1, 1, c['roll_at'] + 0.2))]))
    # the arms: each shoulder swings against the leg on its side, the elbow follows it late and the glove later still
    for side, (sh, el, glove, sd) in ARMS.items():
        at = c['arm_at'] + (0.5 if side == 'R' else 0.0)
        swing = c['arm'] * harm(phase, (1, 1, at), (c['arm2'], 2, at + 0.1))
        out = c['arm_out'] * sd + c['arm_roll'] * sd * harm(phase, (1, 2, c['arm_at'] + 0.05))
        Wt[sh] = mul(Wt[UPPER], mul(rot([swing + c['arm_lift'], 0, out]), mul(tr(rig.R(W0, UPPER)), rig.R(W0, sh))))
        set_rot(pose, sh, mul(tr(Wt[UPPER]), Wt[sh]), hist)
        flex = c['elbow'] * harm(phase, (1, 1, at + c['elbow_lag']), (c['elbow2'], 2, at + c['elbow_lag'] + 0.1))
        pose[el][3] = rest[el][3] + round((flex - c['elbow_extra']) * DEG)
        wrist = c['wrist'] * harm(phase, (1, 1, at + 2 * c['elbow_lag']))
        pose[glove][3] = rest[glove][3] + round((0.5 * flex + wrist - c['wrist_hold']) * DEG)
    # the leaf crown and the club bob against the body, a little later than the head
    for b, key, lead in ((LEAF, 'leaf', 0.1), (CLUB, 'club', 0.14)):
        pose[b][3] = rest[b][3] + round((c[key] * harm(phase - lead, (1, 2, c['high'])) + c[key + '_out']) * DEG)
        pose[b][5] = rest[b][5] + round(0.7 * c[key] * harm(phase - lead, (1, 1, c['roll_at'] + 0.1)) * DEG)
    # the tail: its root turns against the hips and each segment follows the one before it
    for k, b in enumerate(TAIL):
        d = c['tail_lag'] * k
        pose[b][3] = rest[b][3] + round((c['tail_out'] * (1 - 0.3 * k) + c['tail_pitch'] * harm(phase - d, (1, 2, c['pitch_at'] + 0.1))
                                         + c['tail_pitch1'] * harm(phase - d, (1, 1, 0.3))) * DEG)
        pose[b][4] = rest[b][4] + round(c['tail_yaw'] * harm(phase - d, (1, 1, c['yaw_at'] + 0.5)) * DEG)


PROFILE = dict(
    species=SPECIES, name='Monmon', source=SOURCE,
    parents=[-1, 0, 1, 2, 3, 4, 2, 6, 7, 2, 9, 10, 1, 12, 13, 1, 15, 1, 17, 18, 1],
    pelvis=UPPER, chest=None, neck=None, head=HEAD, tail=(), loose=(),
    legs=LEGS, pole_world=True, rest_plane=True, pole={False: [0.3, 0.0, -1.0]},
    paw_rest={'LH': [0, 0, -30], 'RH': [0, 0, -30]},
    sole={False: SOLE},
    reach={'front': 0, 'hind': 0},
    fold={False: 24}, clear=4,
    speed_range={0: (0, 0), 2: (15, 31), 3: (10, 20), 4: (35, 52)},
    body=body, rest_fix=rest_fix, floor=5, stance_slip=0.2, events=lambda slot, total: face_events(slot, total),
    gaits={},
)
COMMON = dict(
    kind='walk', snap=False, arc=0.5, clear_ease=0.1, world_ease=True, fold_soft=8, slip=0.0, steps=('LH', 'RH'),
    reach={'front': 0, 'hind': -30}, lift={'front': 0, 'hind': 30}, curl={'front': 0, 'hind': 0}, peel={'front': 0, 'hind': 0},
    out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 0}, track={'front': 0, 'hind': 10}, heel=0,
    high=0.1, bob=3, bob2=0.8, bob_side=0.5, height=14, shift=5, shift2=0.8, roll_at=0.3,
    hip_tilt=0, hip_pitch=1, hip_pitch1=0.3, hip_yaw=4, hip_yaw2=0.5, hip_roll=2, hip_roll2=0.4,
    lean=0, pitch=1.5, pitch1=0.5, pitch_at=0.15, yaw=1, counter=0.9, roll=2.5, roll2=0.5, yaw_at=0.05, lag=0.07, breath=0,
    steady=0.8, head=0, head_roll=0, nod=1, nod2=0.5, nod_at=0.2, nod_lag=0.06, look=0, look_at=0.3,
    arm=14, arm2=0, arm_at=0.0, arm_lift=0, arm_out=0, arm_roll=0, elbow=6, elbow2=0, elbow_extra=0, elbow_lag=0.05,
    wrist=0, wrist_hold=0,
    leaf=4, leaf_out=0, club=3, club_out=0,
    tail_lag=0.06, tail_out=0, tail_pitch=5, tail_pitch1=2, tail_yaw=6,
)
PROFILE['gaits'] = {
    # standing, both feet planted, spread over 3 s: the weight shifts, the head tilts from side to side and looks about with a
    # little dip now and then, the arms hang loose, the leaf crown, the club and the tail sway
    0: dict(COMMON, name='idle', ticks=60, speed=0, steps=(),
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 1.0, 'RH': 1.0}, lift={'front': 0, 'hind': 0}, height=10, bob=1.2, bob2=0,
            bob_side=0, shift=3, shift2=0, hip_yaw=2.5, hip_yaw2=0, hip_roll=2, hip_roll2=0, hip_pitch=0.6, hip_pitch1=0, roll=2, roll2=0,
            yaw=0, pitch=0.6, pitch1=0, lean=2, breath=1, head=0, nod=2.5, nod2=1.2, look=7, head_roll=9, steady=1.0,
            arm=3, arm_lift=-6, elbow=3, elbow_extra=-10, wrist_hold=6, leaf=5, club=4, tail_out=4, tail_pitch=3, tail_yaw=8, tail_pitch1=2),
    # a bouncy trot: a knee lift, the body sinking on each landing and springing off it, the gloves swinging against the feet
    2: dict(COMMON, name='walk', ticks=12, speed=16,
            touchdown={'LH': 0.0, 'RH': 0.42}, duty={'LH': 0.56, 'RH': 0.56}, lift={'front': 0, 'hind': 30},
            height=12, high=0.27, bob=9, bob2=2.0, bob_side=4.0, shift=6, hip_yaw=6, hip_roll=3, roll=3.5, lean=4, pitch=2, head=2, head_roll=9, look=5, nod=3,
            arm=22, arm_lift=-6, elbow=14, elbow_extra=-16, leaf=8, club=6, tail_out=4, tail_pitch=8, tail_yaw=10, tail_pitch1=3),
    # a slumped shuffle: low feet, a heavy lean, the head down, the arms hanging, the club and the tail dragging
    3: dict(COMMON, name='tired walk', ticks=14, speed=11,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.6, 'RH': 0.6}, lift={'front': 0, 'hind': 14}, peel={'front': 0, 'hind': -5},
            height=4, high=0.3, bob=4, bob2=0.6, bob_side=2.5, head_roll=6, look=3, shift=8, hip_yaw=3.5, hip_roll=3.5, roll=4, lean=15, pitch=1.5, head=-12,
            arm=8, arm_lift=-9, elbow=3, elbow_extra=-16, wrist_hold=10, leaf=4, club=3, club_out=-4, tail_out=4, tail_pitch=4, tail_yaw=5, tail_lag=0.09),
    # a springy lope: short hard landings, a long flight, the gloves pumping, the tail and club streaming
    4: dict(COMMON, name='run', kind='trot', ticks=10, speed=36,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.22, 'RH': 0.22}, lift={'front': 0, 'hind': 44},
            height=14, high=0.42, bob=12, bob2=1.5, bob_side=2.5, head_roll=7, look=4, hip_yaw=8, hip_roll=3, roll=3, lean=14, pitch=3, head=5,
            arm=26, arm_lift=-6, arm_out=6, elbow=4, elbow_extra=-8, leaf=12, club=10, club_out=8, tail_out=-4, tail_pitch=5, tail_yaw=6, tail_lag=0.07),
}
OTHER = {      # cycle B: what changes from cycle A, as factors on A's numbers or the leg settings
    2: dict(scale=dict(bob=1.2, lean=1.2, hip_yaw=1.15, roll=1.1, arm=0.8, tail_yaw=1.2), leg_lift={'LH': 0.92, 'RH': 1.08}),
    3: dict(scale=dict(bob=1.2, lean=0.9, arm=1.3, roll=1.1, shift=1.1), leg_lift={'LH': 0.88, 'RH': 1.12}),
    4: dict(scale=dict(lean=1.12, arm=0.85, hip_yaw=1.1, bob=0.9, tail_yaw=1.3, elbow=0.8)),
}

# the eyes of each clip (tick, state), the clips being 60, 24, 28 and 20 ticks long: one blink in the idle and in the walk, a
# slow blink and then a drooping half-shut stretch in the tired walk, none in the 1 s run; each ends open, so a clip loops and a cut one
# is mended by the next
FACE = {
    0: face.blink(37),
    2: face.blink(13),
    3: face.blink(3, slow=True) + [(15, face.HALF), (23, face.OPEN)],
    4: [],
}


def face_events(slot, total):
    return face.events(FACE[slot], total)


FOLLOW = {12: (0.55, 0.5), 13: (0.6, 0.45), 14: (0.5, 0.45),          # right arm: shoulder, elbow, glove
          17: (0.55, 0.5), 18: (0.6, 0.45), 19: (0.5, 0.45),          # left arm
          HEAD: (0.7, 0.55), LEAF: (0.45, 0.3), CLUB: (0.4, 0.35),
          6: (0.6, 0.5), 7: (0.55, 0.45), 8: (0.5, 0.4)}                # (rad per tick, damping)


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


def finish():
    for slot, spec in OTHER.items():
        cfg = PROFILE['gaits'][slot]
        other = {k: v for k, v in spec.items() if k != 'scale'}
        other.update({k: cfg[k] * f for k, f in spec['scale'].items()})
        cfg.update(cycles=2, compose=compose, other=other)


finish()


def build(data, skeleton):
    """The model with the three clips written on it -> (bytes, report)."""
    old = mmd.MMD.parse(data, len(skeleton))
    old.type = SPECIES
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = len(skeleton)
    return quadruped.build(data, skeleton, PROFILE)


def texture(tim):
    """The texture before this change (SOURCE_TIM) -> the same with the eye frames in its spare rows."""
    if hashlib.sha256(tim).hexdigest() != SOURCE_TIM:
        raise ValueError('Monmon needs the texture it had before this change')
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
    p.add_argument('--tex', type=Path, help='the texture before this change (edit.py get 352), with --out-tex')
    p.add_argument('--out-tex', type=Path)
    a = p.parse_args()
    skeleton = json.loads(next((ROOT / 'content/species').glob('352-*.json')).read_text())['model']['skeleton']
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
