"""Bearmon's idle, walk, tired walk and run (species 353, slots 0 with its alias 33, 2, 3 and 4) as one body on planted feet.

Bearmon is a stocky bear cub on two short legs (forward is -z). Its rig has 18 bones: the body (1, the chest mesh, the
parent of everything) with the hips under it (10: the belly, the two legs 11-13 right and 14-16 left, thigh, shin and
the flat clawed foot, and the stub of a tail 17); on the body the head with its cap and ears (8) and its jaw (9), and
the two arms hung from the shoulders (2-4 right, 5-7 left: upper arm, forearm, the clawed mitt), held bent at the
elbow with the mitts out in front.

What was wrong. The imported walk, tired walk and run only moved the legs and the body bone. Every other bone was
frozen: both arms (all six bones, in all three clips), the jaw and the tail never moved, and the head only copied the
body's pitch in the walk and stood dead still in the run. So the legs worked the way a machine's do (the thigh swung 112
degrees, the shin folded to 120-150 degrees, the soles slid 47 % / 111 % / 59 % of the travel on average and 98 / 277 /
123 % at worst) while the whole upper body was a statue riding on them: two unrelated animations in one model, the hips
turning with the chest instead of against it, no breath, no follow-through.

What the clips are now. One gait phase drives the whole body. `quadruped.py` plants each foot (two-bone solves, the sole
flat on the floor, the toes a little turned in as a cub's are) and the two legs step half a cycle apart; `body` writes
everything above them from the same phase: the weight goes over the planted leg (the body shifts and rolls to its side
and the hips drop the other way, a waddle), the hips yaw with the leg that leads and the chest turns against them a
little later, the arms swing against the legs on their side (the forearm and the mitt a little later still), the head
stays level against the body's roll and follows late, the tail sweeps against the hips. Each clip is two cycles long: the
second differs from the first (one leg lifts higher, the body sinks a little more) and the clip eases from one to the
other and back, so no two steps are alike and the loop still closes; the arms, head, jaw and tail then follow through by
a loose spring each.

Personality (it is a starter, a cheerful, slightly clumsy cub). The waddle is exaggerated (wide sway and roll, a springy
bounce); the arms swing wide and flop on slower springs; the head nods, tilts and looks about; the tail wags. One cycle
of each clip carries an accent the other does not, eased in and out with the cycle blend: a happy hop (the body lifts,
the arms go up, the head tips back, the jaw opens, the tail wags) in the second, a stumble and its recovery (roll, one
arm flung out) in the first. The tired walk droops (head low, arms hanging) and yawns once a step pair. The run flails
its arms wide. The idle is a 96-tick loop of its own: breath, a weight shift, looking round with a curious head tilt, a
quick ear-flick tilt, a burst of tail wag, a happy nod and a paw wave; the legs keep the import's standing pose (the
hips are not turned against the chest there, which would only graze the belly), so it stays within the import's
interpenetration.

Nothing is stored but the clips: the mesh and the texture are exact. Offline: `tools/models/edit.py get 353` on the
commit before this change, then `python3 -m tools.models.field_animations.bearmon_gait --source THAT.MMD --out
AFTER.MMD` and `edit.py put 353 AFTER.MMD`.
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
from tools.models.field_animations.quadruped import mul, rot, set_rot  # noqa: E402

SPECIES = 353
SOURCE = '2e5bb8152b1449599fc4f08e744fd991bf12aacd55b3e3510eaa815b410ff602'     # `edit.py get 353` before this change
TAU = 2 * math.pi
DEG = 4096 / 360
BODY, HEAD, JAW, HIPS, TAIL = 1, 8, 9, 10, 17
ARMS = {'R': (2, 3, 4, 1), 'L': (5, 6, 7, -1)}          # shoulder, forearm, mitt, the side's sign in x
LEGS = {'RH': (11, 12, 13, 1, False), 'LH': (14, 15, 16, -1, False)}


def harm(phase, *terms):
    """A sum of cosines: terms are (amplitude, rate, delay in cycles)."""
    return sum(a * math.cos(TAU * rate * (phase - delay)) for a, rate, delay in terms)


def bell(phase, at, width):
    """A smooth cyclic bump: 1 at `at`, 0 further than `width` cycles away."""
    d = (phase - at + 0.5) % 1.0 - 0.5
    return 0.5 + 0.5 * math.cos(math.pi * d / width) if abs(d) < width else 0.0


def turn(rig, pose, bone, degrees, hist):
    """The bone's rest rotation turned by `degrees` in its parent's frame (x pitch nose-down, y yaw so that the right side
    goes forward, z roll so that the top goes right)."""
    set_rot(pose, bone, mul(rot(degrees), mmd.rot_matrix(*rig.rest[bone][3:6])), hist)


def idle_body(rig, c, ph, pose, hist):
    """A cub standing about on planted feet: it breathes, shifts its weight, looks round with its head tilted, flicks its
    ear (a quick head tilt), wags the tail in bursts, nods happily and waves a paw. Every part has its own rate and
    moment in the loop, so no two of them repeat together."""
    rest = rig.rest
    breath = math.sin(TAU * 3 * ph)
    pose[BODY][7] = rest[BODY][7] - 3.0 - 1.2 * breath - 2.0 * bell(ph, 0.83, 0.1)
    sway = harm(ph, (1, 1, 0.1)) + 0.35 * harm(ph, (1, 2, 0.3))
    pose[BODY][6] = rest[BODY][6] + 3.0 * sway
    roll = 1.0 * sway + 1.2 * bell(ph, 0.3, 0.12)
    pitch = 0.9 * breath + 3.0 * bell(ph, 0.83, 0.08) - 1.5 * bell(ph, 0.62, 0.08)
    yaw = 0.0
    turn(rig, pose, BODY, [c['lean'] + pitch, yaw, roll], hist)
    turn(rig, pose, HIPS, [0, 0, 0], hist)
    look = 20 * bell(ph, 0.15, 0.17) - 16 * bell(ph, 0.55, 0.15) + 4 * math.sin(TAU * 2 * ph)
    tilt = 8 * bell(ph, 0.3, 0.12) - 6 * bell(ph, 0.62, 0.1) + 3.5 * bell(ph, 0.43, 0.025) - 3.5 * bell(ph, 0.47, 0.025)
    nod = 6 * bell(ph, 0.83, 0.05) + 6 * bell(ph, 0.9, 0.05) - 4 * bell(ph, 0.15, 0.2) + 1.2 * breath
    turn(rig, pose, HEAD, [-c['lean'] * 0.8 - pitch * 0.7 + nod, look - 0.8 * yaw, tilt - 0.7 * roll], hist)
    pose[JAW][3] = rest[JAW][3] + round(6 * bell(ph, 0.86, 0.1) * DEG)
    wave = bell(ph, 0.5, 0.2)
    for side, (sh, el, hand, sd) in ARMS.items():
        mine = wave if side == 'R' else 0.0
        swing = 3.0 * breath * (1 if side == 'R' else -1) + 2.0 * sway * sd - 20 * mine
        out = -sd * 3 + sd * 10 * mine
        turn(rig, pose, sh, [swing, 0, out], hist)
        pose[el][3] = rest[el][3] + round((-6 * mine + 2.5 * math.sin(TAU * 3 * ph + (1 if side == 'R' else 2))) * DEG)
        pose[hand][3] = rest[hand][3] + round((10 * mine * math.sin(TAU * 7 * ph) + 3 * math.sin(TAU * 3 * ph + 2)) * DEG)
    burst = bell(ph, 0.72, 0.16)
    pose[TAIL][3] = rest[TAIL][3] + round((3 * breath + 8 * burst) * DEG)
    pose[TAIL][4] = rest[TAIL][4] + round((3 * math.sin(TAU * 2 * ph) + 26 * burst * math.sin(TAU * 8 * ph)) * DEG)
    pose[TAIL][5] = rest[TAIL][5]


def body(rig, cfg, phase, pose, hist):
    """Height, sway and the turns of body and hips, the head and jaw, the arms and the tail from one phase."""
    c, rest = cfg, rig.rest
    if c['kind'] == 'idle':
        return idle_body(rig, c, phase, pose, hist)
    left = c['touchdown']['LH']                    # the left foot lands at this phase; the right one half a cycle later
    ph = phase - left
    bob = harm(ph, (c['bob'], 2, c['high']), (c['bob2'], 4, c['high'] + 0.03), (c['bob_side'], 1, c['high'] + 0.2))
    hop = c['hop'] * bell(ph, c['hop_at'], c['hop_w'])               # a happy hop (one cycle of the two)
    stum = c['stumble'] * bell(ph, c['st_at'], c['st_w'])            # a stumble and its recovery (the other cycle)
    yawn = c['yawn'] * bell(ph, c['yawn_at'], 0.22)                  # the tired walk's yawn
    pose[BODY][7] = rest[BODY][7] - c['height'] - bob - 7 * hop
    # the weight goes over the planted leg: the right foot carries at phase 0.79, the left at 0.29
    over = harm(ph, (1, 1, 0.79 + c['roll_at']))
    pose[BODY][6] = rest[BODY][6] + c['shift'] * over + c['shift2'] * harm(ph, (1, 3, 0.79 + c['roll_at'] + 0.07))
    hy = harm(ph, (c['hip_yaw'], 1, 0.5 + c['yaw_at']), (c['hip_yaw2'], 3, 0.5 + c['yaw_at'] + 0.05))    # the leading hip is forward
    hr = -c['hip_roll'] * over + c['hip_roll2'] * harm(ph, (1, 2, c['pitch_at']))
    breath = c['breath'] * math.sin(TAU * (ph - 0.1))
    lag = c['lag']
    pitch = c['lean'] + harm(ph - lag, (c['pitch'], 2, c['pitch_at']), (c['pitch1'], 1, c['pitch_at'] + 0.12)) + breath + 3 * stum - 2 * hop
    yaw = -c['counter'] * hy + harm(ph - lag, (c['yaw'], 1, 0.5 + c['yaw_at'] + 0.1))
    roll = c['roll'] * harm(ph - lag, (1, 1, 0.79 + c['roll_at'])) + c['roll2'] * harm(ph - lag, (1, 3, 0.79 + c['roll_at'] + 0.06)) + 7 * stum
    turn(rig, pose, BODY, [pitch, yaw, roll], hist)
    # the hips are a child of the body: they get the difference, so that they yaw and roll against it
    hp = c['hip_tilt'] + harm(ph, (c['hip_pitch'], 2, c['pitch_at'] + 0.05)) - 0.5 * (pitch - c['lean'])
    turn(rig, pose, HIPS, [hp, hy - yaw, hr - roll], hist)
    # the head keeps most of its gaze against the body and follows what the body does late
    hl = c['head_lag']
    top = pitch - c['lean']
    nod = harm(ph - hl, (c['nod'], 2, c['pitch_at'] + 0.1), (c['nod1'], 1, 0.3))
    hp = c['head'] - c['steady'] * top + nod + 0.4 * breath - 12 * hop - 5 * stum + 9 * yawn
    hyaw = -c['steady'] * yaw * 0.8 + c['look'] * harm(ph - hl, (1, 1, 0.5 + c['yaw_at'] + 0.2))
    hrl = -c['steady'] * roll + c['head_roll'] * harm(ph - hl, (1, 1, 0.79 + c['roll_at'] + 0.1)) - 6 * stum
    turn(rig, pose, HEAD, [hp, hyaw, hrl], hist)
    pose[JAW][3] = rest[JAW][3] + round((c['jaw'] * (0.5 + 0.5 * math.sin(TAU * (c['jaw_rate'] * ph - 0.1))) - c['jaw_hold'] + 7 * hop + 14 * yawn) * DEG)
    # the arms: the shoulder swings against the leg on its side (the left arm is back when the left foot lands), the
    # forearm and the mitt follow late and flex as the arm comes forward
    for side, (sh, el, hand, sd) in ARMS.items():
        at = 0.0 if side == 'L' else 0.5
        swing = c['arm'] * harm(ph, (1, 1, at), (c['arm2'], 2, at + 0.1)) + c['arm_lift'] - 16 * hop + (6 * stum if side == 'L' else -4 * stum)
        out = -sd * (c['arm_out'] + c['arm_pump'] * harm(ph, (1, 2, at + 0.05))) + c['arm_roll'] * (-over if side == 'L' else over) - sd * (4 * hop + (11 * stum if side == 'R' else -3 * stum))
        turn(rig, pose, sh, [swing, 0, out], hist)
        flex = c['elbow'] * harm(ph, (1, 1, at + 0.5 + c['elbow_lag']), (c['elbow2'], 2, at + c['elbow_lag'] + 0.1))
        pose[el][3] = rest[el][3] + round((flex - c['elbow_extra']) * DEG)
        wrist = c['wrist'] * harm(ph, (1, 1, at + 0.5 + 2 * c['elbow_lag']))
        pose[hand][3] = rest[hand][3] + round((0.5 * flex + wrist - c['wrist_hold']) * DEG)
    # the stub of a tail sweeps against the hips and flicks on every step
    pose[TAIL][3] = rest[TAIL][3] + round((c['tail_out'] + c['tail_pitch'] * harm(ph, (1, 2, c['pitch_at'] + 0.15))
                                           + c['tail_pitch1'] * harm(ph, (1, 1, 0.3))) * DEG)
    pose[TAIL][4] = rest[TAIL][4] + round((c['tail_yaw'] * harm(ph, (1, 1, 0.5 + c['yaw_at'] + 0.22)) + 14 * hop * math.sin(TAU * 4 * ph)) * DEG)
    pose[TAIL][5] = rest[TAIL][5] + round(c['tail_roll'] * harm(ph, (1, 1, 0.79 + c['roll_at'] + 0.15)) * DEG)


def legs_as_imported(rig, cfg, phase, pose):
    """The idle keeps the import's standing legs (one leg a step behind the other, parallel and flat) whatever the body
    does above them: the sway is a few units, so the soles stay where they are within a vertex or two."""
    if cfg['kind'] == 'idle':
        for bone in (11, 12, 13, 14, 15, 16):
            pose[bone][3:9] = rig.idle[0][bone][3:9]


PROFILE = dict(
    species=SPECIES, name='Bearmon', source=SOURCE,
    parents=[-1, 0, 1, 2, 3, 1, 5, 6, 1, 8, 1, 10, 11, 12, 10, 14, 15, 10],
    pelvis=BODY, chest=None, neck=None, head=HEAD, tail=(), loose=(),
    legs=LEGS, pole_world=True, rest_plane=True, pole={False: [0.1, 0.0, -1.0]},
    paw_flat={'RH': [0, 5, 0], 'LH': [0, -5, 0]},        # the toes turned in a little
    sole={False: [0, 17, -29]},                            # the middle of the flat foot, on its bottom
    reach={'front': 0, 'hind': -10},
    fold={False: 36}, clear=4,
    speed_range={0: (0, 0), 2: (15, 31), 3: (10, 20), 4: (35, 52)},
    body=body, extra=legs_as_imported, floor=3, stance_slip=0.2,
    gaits={},
)
COMMON = dict(
    hop=0, hop_at=0.0, hop_w=0.3, stumble=0, st_at=0.0, st_w=0.3, yawn=0, yawn_at=0.4,
    kind='walk', snap=False, arc=0.5, clear_ease=0.1, world_ease=True, fold_soft=8, slip=0.0, steps=('LH', 'RH'),
    reach={'front': 0, 'hind': 0}, lift={'front': 0, 'hind': 26}, curl={'front': 0, 'hind': 0}, peel={'front': 0, 'hind': 0},
    out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 6}, track={'front': 0, 'hind': 4}, heel=3,
    high=0.29, bob=4, bob2=0.8, bob_side=0.8, height=-3, shift=6, shift2=0.8, roll_at=0.0,
    hip_tilt=0, hip_pitch=1, hip_yaw=6, hip_yaw2=0.5, hip_roll=3, hip_roll2=0.6,
    lean=3, pitch=1.5, pitch1=0.5, pitch_at=0.1, yaw=1, counter=0.9, roll=4.5, roll2=0.6, yaw_at=0.03, lag=0.06, breath=0,
    head=0, steady=0.7, nod=1.5, nod1=0.5, look=2, head_lag=0.07, head_roll=1.5,
    jaw=2, jaw_rate=2, jaw_hold=0,
    arm=13, arm2=2, arm_lift=0, arm_out=3, arm_pump=2, arm_roll=2, elbow=8, elbow2=2, elbow_extra=0, elbow_lag=0.06, wrist=5, wrist_hold=0,
    tail_out=0, tail_pitch=4, tail_pitch1=2, tail_yaw=9, tail_roll=2,
)

FOLLOW = {2: (0.42, 0.5), 3: (0.5, 0.45), 4: (0.45, 0.45), 5: (0.42, 0.5), 6: (0.5, 0.45), 7: (0.45, 0.45),
          HEAD: (0.7, 0.55), JAW: (0.6, 0.5), TAIL: (0.5, 0.4)}     # (rad per tick, damping)


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
            mixed = spring(seq, rate * cfg.get('spring', 1.0), damping)
            for i in range(2 * ticks):
                out[i][b][ch] = seq[i] + (mixed[i] - seq[i]) * follow
    closing = [list(v) for v in out[0]]
    closing[0][8] = -round(speed * 2 * ticks)
    out.append(closing)
    return out


PROFILE['gaits'] = {
    0: dict(COMMON, kind='idle', name='idle', ticks=96, speed=0, steps=(), lean=0,
            touchdown={'LH': 0.0, 'RH': 0.0}, duty={'LH': 1.0, 'RH': 1.0}, lift={'front': 0, 'hind': 0}),
    2: dict(COMMON, name='walk', ticks=10, speed=16, stumble=1,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.56, 'RH': 0.56},
            bob=6, bob2=1.0, shift=9, roll=7, hip_yaw=8, hip_roll=5, lean=4, nod=4, look=7, head_roll=4, head_lag=0.1,
            arm=22, arm_out=7, arm_pump=4, elbow=12, wrist=8, tail_yaw=16, tail_roll=4, tail_pitch=6),
    3: dict(COMMON, name='tired walk', ticks=14, speed=10, stumble=0,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.62, 'RH': 0.62}, height=-10, lift={'front': 0, 'hind': 20},
            lean=16, head=4, arm=9, arm_lift=4, arm_out=4, arm_pump=2, elbow=5, elbow_extra=2, wrist=6, bob=3, roll=6.5, shift=8,
            hip_roll=4, arm_roll=2, tail_pitch=2, tail_out=-10, tail_yaw=7, nod=2.5, look=5, head_roll=3, head_lag=0.12, yawn=1),
    4: dict(COMMON, name='run', kind='trot', ticks=8, speed=36, stumble=1,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.3, 'RH': 0.3}, height=-8, arc=0.6, clear_ease=0.05, lift={'front': 0, 'hind': 44},
            bob=10, bob2=1.5, lean=11, head=-5, arm=17, arm_out=12, arm_pump=5, elbow=10, wrist=8, hip_yaw=5.5, hip_roll=2.5, roll=4.5, shift=5,
            wide={'front': 0, 'hind': 3}, tail_out=14, tail_yaw=16, tail_roll=4, nod=4, look=5, head_roll=4),
}
OTHER = {      # cycle B: what changes from cycle A, as factors on A's numbers or the leg settings
    0: None,
    2: dict(scale=dict(bob=1.15, lean=1.15, hip_yaw=1.12, roll=1.1, arm=0.85), leg_lift={'LH': 0.9, 'RH': 1.08},
            touchdown={'LH': 0.0, 'RH': 0.52}, settle=2.0, heel=4, hop=1, stumble=0, hop_at=0.0),
    3: dict(scale=dict(bob=1.15, lean=0.95, arm=1.2, roll=1.1, shift=1.1), leg_lift={'LH': 0.88, 'RH': 1.1},
            touchdown={'LH': 0.0, 'RH': 0.51}, settle=2.0, heel=4),
    4: dict(scale=dict(lean=1.1, arm=0.9, hip_yaw=1.1), leg_lift={'LH': 0.8, 'RH': 1.0}, touchdown={'LH': 0.0, 'RH': 0.5}, settle=2.0, heel=5,
            hop=1, stumble=0),
}
for slot, spec in OTHER.items():
    if spec is None:
        continue
    cfg = PROFILE['gaits'][slot]
    other = {k: v for k, v in spec.items() if k != 'scale'}
    other.update({k: cfg[k] * f for k, f in spec['scale'].items()})
    cfg.update(cycles=2, compose=compose, other=other)


def build(data, skeleton):
    """The model with the three clips written on it -> (bytes, report)."""
    return quadruped.build(data, skeleton, PROFILE)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/353-bearmon.json').read_text())['model']['skeleton']
    data, report = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(report, indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
