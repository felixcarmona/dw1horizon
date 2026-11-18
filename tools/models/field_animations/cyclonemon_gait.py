"""Cyclonemon's field clips (species 281): idle, walk, tired walk and run, written from the ground up.

Cyclonemon is a hulking, hunched beast with a heavy left arm that ends in two red claws (bones 2-5: shoulder pad, the arm
column, the two claws), a lighter right arm (6-8), a horned head on a four-bone neck (9-12, the last the jaw), a pelvis
(13) carrying two short, crouched, splayed legs (14-16 right, 17-19 left) and a tail (20-22). The body bone (1) is the
rest pose's sized root: it is scaled by 1.3 and everything under it with it (`quadruped.py`'s profile key `scale`).

The imported clips never planted anything: the claws were dragged along the floor by the walk (slip 100-130 % of the
travel) and the legs hung in the air, 26 units over the floor. Here the heavy arm is a third support: its claws are the
tip of a crutch that is planted ahead of the body, stays put while the body passes over it, lifts and swings forward;
the two legs step in turn with it (a three-beat walk, a bound in the run). The light right arm swings freely against
the crutch. `quadruped.py` plants every sole and solves the three limbs with two-bone IK; this module adds what the
framework has no row for: the torso, hips, neck and head, jaw, tail and right arm (`body`), the second claw following the
first (`extra`), and the idle (slot 0, also the battle idle, slot 33,
which battle-rebuilds.json replaces afterwards with the source game's own idle, repaired).

Offline: `tools/models/edit.py get 281` on the commit before this change, then
`python3 -m tools.models.field_animations.cyclonemon_gait --source THAT.MMD --out AFTER.MMD` and `edit.py put 281 AFTER.MMD`.
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
import animsheet  # noqa: E402
import mmd  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models.field_animations import quadruped  # noqa: E402
from tools.models.field_animations.quadruped import DEG, mul, tr, rot, set_rot, standing  # noqa: E402

SPECIES = 281
SOURCE = '25bb5e0aa47b2d33c1c76b54355c528f1e6b200edfcf76d1f3afdf0abad8d638'   # `edit.py get 281` before this change
TAU = 2 * math.pi
TORSO, CRUTCH, CLAW, CLAW2, ARM, HIPS = 1, 2, 4, 5, 6, 13
NECK, HEAD, JAW = (9, 10), 11, 12
TAIL = (20, 21, 22)
IDLE_TICKS = 48


def turn(rig, pose, bone, degrees, hist):
    """The bone's rest rotation turned by `degrees` (x pitch nose-down, y yaw to the left, z roll to the right) about its
    parent's axes."""
    set_rot(pose, bone, mul(rot(degrees), mmd.rot_matrix(*rig.rest[bone][3:6])), hist)


def wave(phase, lag=0.0, rate=1):
    return math.sin(TAU * rate * (phase - lag))


def trail(phase, lag, rate=1, harmonic=0.0):
    """A sine of the cycle phase with a second harmonic that sharpens it a little, so no swing is a pure sinusoid."""
    return wave(phase, lag, rate) + harmonic * wave(phase, lag + 0.07, 2 * rate)


def body(rig, cfg, phase, pose, hist):
    """Torso bob and lean, hips against the torso, neck and head steadying, jaw, tail and the right arm, all on closed
    loops of the cycle (the lags are fractions of the cycle: every part follows what holds it a little later)."""
    rest = rig.rest
    rate, high = cfg['rate'], cfg['high']
    dip = math.cos(TAU * rate * (phase - high)) + cfg['bob2'] * math.cos(TAU * 2 * rate * (phase - high - 0.04))
    dip += cfg['bob_slow'] * math.cos(TAU * (phase - high - 0.1))
    pose[TORSO][7] = rest[TORSO][7] - cfg['height'] - cfg['bob'] * dip
    pose[TORSO][6] = rest[TORSO][6] + cfg['sway'] * trail(phase, cfg['roll_at'] + 0.1, 1, 0.25)
    pitch = cfg['tilt'] + cfg['pitch'] * trail(phase, cfg['pitch_at'], rate, 0.25)
    yaw = cfg['yaw'] * trail(phase, cfg['yaw_at'], 1, 0.2)
    roll = cfg['roll'] * trail(phase, cfg['roll_at'], 1, 0.3) + cfg['roll2'] * wave(phase, cfg['roll_at'] + 0.1, rate)
    turn(rig, pose, TORSO, [pitch, yaw, roll], hist)
    turn(rig, pose, HIPS, [-0.6 * cfg['pitch'] * trail(phase, cfg['pitch_at'] + 0.06, rate), -1.5 * yaw, -1.1 * roll], hist)
    lag_n, lag_h = cfg['neck_lag'], cfg['head_lag']
    for k, b in enumerate(NECK):
        steady = -cfg['steady'] * (pitch - cfg['tilt']) * (0.4 + 0.2 * k)
        turn(rig, pose, b, [cfg['droop'] * (0.5 + 0.5 * k) + steady - cfg['nod'] * 0.5 * trail(phase, lag_n + 0.05 * k, rate),
                            -0.6 * yaw - cfg['look'] * 0.5 * wave(phase, lag_n + 0.3 + 0.04 * k), 0.4 * roll], hist)
    turn(rig, pose, HEAD, [-cfg['steady'] * (pitch - cfg['tilt']) * 0.8 - cfg['nod'] * trail(phase, lag_h, rate, 0.2)
                           + cfg['head_down'], -0.5 * yaw - cfg['look'] * wave(phase, lag_h + 0.3),
                           -0.6 * roll + 0.7 * cfg['look'] * wave(phase, lag_h + 0.15)], hist)
    turn(rig, pose, JAW, [cfg['jaw'] * (0.5 + 0.5 * wave(phase, 0.2, rate)) * (1 + 0.3 * wave(phase, 0.1, 1)), 0, 0], hist)
    for k, b in enumerate(TAIL):
        lag = cfg['tail_lag'] * (k + 1)
        turn(rig, pose, b, [cfg['tail_up'] * (1 - 0.3 * k) + cfg['tail'] * (0.5 + 0.3 * k) * trail(phase, 0.1 + lag, rate, 0.2),
                            cfg['tail_yaw'] * (0.6 + 0.5 * k) * trail(phase, 0.25 + lag, 1, 0.15), 0], hist)
    # the light right arm swings against the crutch: shoulder, elbow late and wider, wrist later still
    sw, lag = cfg['arm'], cfg['arm_lag']
    turn(rig, pose, ARM, [cfg['arm_hang'] + sw * trail(phase, cfg['arm_at'], 1, 0.2),
                          cfg['arm_out'] * wave(phase, cfg['arm_at'] + 0.1), 0], hist)
    turn(rig, pose, ARM + 1, [cfg['elbow'] * (0.5 + 0.5 * wave(phase, cfg['arm_at'] + lag, 1)) * (1 + 0.25 * wave(phase, 0.2, 2)), 0, 0], hist)
    turn(rig, pose, ARM + 2, [cfg['wrist'] * wave(phase, cfg['arm_at'] + 2 * lag), 0, 0], hist)


def axis_turn(u, a):
    """The rotation matrix of angle `a` about the unit vector `u` (Rodrigues)."""
    c, s_, k = math.cos(a), math.sin(a), 1 - math.cos(a)
    x, y, z = u
    return [[c + x * x * k, x * y * k - z * s_, x * z * k + y * s_],
            [y * x * k + z * s_, c + y * y * k, y * z * k - x * s_],
            [z * x * k - y * s_, z * y * k + x * s_, c + z * z * k]]


def twist_pad(rig, pose):
    """The shoulder pad (bone 2) keeps the way it sits on the body in the rest pose. The arm solve turns the whole shoulder,
    and the pad with it, as far as the elbow needs; turning the shoulder about the line to the elbow moves nothing else,
    so the pad takes the twist that brings it nearest to its place on the torso and the arm column keeps its own turn."""
    W = rig.world(pose)
    r1, r2, r3 = rig.R(W, 1), rig.R(W, 2), rig.R(W, 3)
    want = mul(r1, mul(tr(rig.R(rig.still, 1)), rig.R(rig.still, 2)))
    axis = [W[3][i][3] - W[2][i][3] for i in range(3)]
    length = math.sqrt(sum(x * x for x in axis))
    axis = [x / length for x in axis]
    # The match of the turned pad with its place is a + b cos(t) + c sin(t): its best twist has a closed form, so it moves
    # smoothly from one tick to the next.
    def match(t):
        m = mul(axis_turn(axis, t), r2)
        return sum(m[i][j] * want[i][j] for i in range(3) for j in range(3))
    f0, f1, f2 = match(0.0), match(math.pi / 2), match(math.pi)
    best = math.atan2(f1 - (f0 + f2) / 2, (f0 - f2) / 2)
    twisted = mul(axis_turn(axis, best), r2)
    pose[CRUTCH][3:6] = [round(x) for x in mmd.matrix_euler(mul(tr(r1), twisted), None)]
    pose[CRUTCH + 1][3:6] = [round(x) for x in mmd.matrix_euler(mul(tr(twisted), r3), None)]


def second_claw(rig, cfg, phase, pose):
    """Bone 5 is the first claw's neighbour under the arm column: in the world it keeps the turn it has to the first claw
    in the rest pose, so both claws stand on the floor together."""
    twist_pad(rig, pose)
    W = rig.world(pose)
    delta = mul(rig.R(rig.still, CLAW2), tr(rig.R(rig.still, CLAW)))
    follow = mul(tr(rig.R(W, 3)), mul(delta, rig.R(W, CLAW)))
    pose[CLAW2][3:6] = [round(x) for x in mmd.matrix_euler(follow, None)]


# ------------------------------------------------------------------ the gaits
COMMON = dict(
    sway=0.0,
    kind='walk', snap=False, arc=1.0, clear_ease=0.4, fold_soft=12, slip=0.0, steps=('LH', 'PF', 'RH'),
    reach={'front': 0, 'hind': 0}, bob2=0.2, bob_slow=0.0, pitch_at=0.1, yaw_at=0.2, roll_at=0.05, roll2=0.0,
    steady=0.5, neck_lag=0.08, head_lag=0.16, tail_lag=0.07, high=0.15,
)
PROFILE = dict(
    species=SPECIES, name='Cyclonemon', source=SOURCE,
    parents=[-1, 0, 1, 2, 3, 3, 1, 6, 7, 1, 9, 10, 11, 1, 13, 14, 15, 13, 17, 18, 13, 20, 21],
    pelvis=TORSO, chest=TORSO, neck=None, head=HEAD,
    legs={'RH': (14, 15, 16, 1, False), 'LH': (17, 18, 19, -1, False), 'PF': (2, 3, 4, -1, True)},
    tail=TAIL, loose=(), scale=1.3,
    pole_world=True, pole={True: [-0.65, -0.48, -0.59], False: [0.8, -0.18, -0.57]},
    sole={True: [-38, 175, -69], False: [0, 35, -20]},
    paw_rest={'RH': [0, 0, -1], 'LH': [0, 0, -1], 'PF': [0, 1, 0]},
    reach={'front': 0, 'hind': 0},
    fold={True: 140, False: 60}, clear=4,
    speed_range={2: (15, 31), 3: (10, 20), 4: (35, 52)},
    body=body, extra=second_claw,
    floor=3, stance_slip=0.2, floor_skip=(),
    gaits={},
)

WALK = dict(
    COMMON, name='walk', ticks=18, speed=15, rate=3,
    touchdown={'LH': 0.0, 'PF': 1 / 3, 'RH': 2 / 3}, duty={'LH': 0.66, 'PF': 0.56, 'RH': 0.66},
    leg_reach={'PF': -320, 'LH': 0, 'RH': 0}, track={'front': 70, 'hind': 0},
    lift={'front': 50, 'hind': 28}, curl={'front': 8, 'hind': 10}, peel={'front': 6, 'hind': 8}, out={'front': 4, 'hind': 4},
    height=8, bob=7, sway=8, tilt=0, pitch=3, yaw=5, roll=4, roll2=1.0, droop=0, head_down=0, nod=3, look=4, jaw=3,
    tail=4, tail_up=0, tail_yaw=10, arm=22, arm_at=0.45, arm_hang=0, arm_out=3, elbow=18, wrist=8, arm_lag=0.06,
)
TIRED = dict(
    COMMON, name='tired walk', ticks=26, speed=11, rate=3,
    touchdown={'LH': 0.0, 'PF': 1 / 3, 'RH': 2 / 3}, duty={'LH': 0.7, 'PF': 0.7, 'RH': 0.7},
    leg_reach={'PF': -350, 'LH': 0, 'RH': 0}, track={'front': 70, 'hind': 0},
    lift={'front': 36, 'hind': 20}, curl={'front': 6, 'hind': 8}, peel={'front': 4, 'hind': 6}, out={'front': 2, 'hind': 2},
    height=-18, bob=5, sway=6, tilt=3, pitch=2, yaw=3, roll=3.5, roll2=1.0, droop=6, head_down=8, nod=2, look=2.5, jaw=1.5,
    tail=3, tail_up=-4, tail_yaw=6, arm=10, arm_at=0.45, arm_hang=4, arm_out=1.5, elbow=10, wrist=4, arm_lag=0.08,
)
RUN = dict(
    COMMON, name='run', kind='gallop', ticks=12, speed=38, rate=2,
    touchdown={'PF': 0.0, 'LH': 0.5, 'RH': 0.56}, duty={'LH': 0.42, 'PF': 0.42, 'RH': 0.42},
    leg_reach={'PF': -350, 'LH': 0, 'RH': 0}, track={'front': 70, 'hind': 0}, steps=('PF', 'LH', 'RH'),
    lift={'front': 60, 'hind': 36}, curl={'front': 12, 'hind': 14}, peel={'front': 8, 'hind': 10}, out={'front': 6, 'hind': 6},
    height=0, bob=10, sway=5, tilt=10, pitch=5, yaw=6, roll=3, roll2=1.5, droop=0, head_down=-4, nod=4, look=2, jaw=4,
    tail=6, tail_up=6, tail_yaw=8, arm=34, arm_at=0.2, arm_hang=0, arm_out=4, elbow=26, wrist=12, arm_lag=0.05, high=0.2,
)
IDLE = dict(
    COMMON, name='idle', ticks=IDLE_TICKS, speed=0, rate=1,
    leg_reach={'PF': -400, 'LH': 0, 'RH': 0}, track={'front': 70, 'hind': 0},
    height=4, bob=1.6, sway=2.5, bob2=0.25, bob_slow=0.0, high=0.05, tilt=0, pitch=1.3, pitch_at=0.0, yaw=1.6, yaw_at=0.3, roll=1.1, roll_at=0.55,
    roll2=0.4, droop=0, head_down=0, nod=2.0, look=5, jaw=1.2, steady=0.4, neck_lag=0.1, head_lag=0.2,
    tail=2, tail_up=0, tail_yaw=7, tail_lag=0.08, arm=3.5, arm_at=0.2, arm_hang=0, arm_out=1.5, elbow=4, wrist=3, arm_lag=0.12,
)
PROFILE['gaits'] = {2: WALK, 3: TIRED, 4: RUN}


def plant_points(rig, cfg):
    """Where each sole stands in the world (the middle of its stance in the walk): x, and z."""
    p, W = rig.p, rig.still
    out = {}
    for name, (up, lo, paw, side, front) in p['legs'].items():
        key = 'front' if front else 'hind'
        ref = p['legs'][quadruped.MIRROR.get(name, name)]
        z = W[up][2][3] + p['reach'][key] + cfg['reach'][key] + cfg.get('leg_reach', {}).get(name, 0)
        out[name] = (side * (abs(W[ref[2]][0][3]) + cfg.get('track', {}).get(key, 0)), z)
    return out


def idle_frames(rig, cfg):
    """The idle loop: the body breathes and sways over three planted supports; every sole is solved onto its own spot."""
    ticks, hist, frames, short = cfg['ticks'], {}, [], 0.0
    spots = plant_points(rig, cfg)
    for t in range(ticks):
        phase = t / ticks
        pose = [list(v) for v in rig.rest]
        pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
        body(rig, cfg, phase, pose, hist)
        for name, (up, lo, paw, side, front) in rig.p['legs'].items():
            world = rig.paw(front, 0, name)
            wrist = standing(rig, name, spots[name][0], spots[name][1], world)
            lower, out = rig.solve(pose, name, wrist, hist, None, None)
            short = max(short, out)
            set_rot(pose, paw, mul(tr(lower), world), hist)
        second_claw(rig, cfg, phase, pose)
        frames.append(pose)
    frames.append([list(v) for v in frames[0]])
    return frames, short


def build(data, skeleton):
    result, report = quadruped.build(data, skeleton, PROFILE)
    n = len(skeleton)
    old = mmd.MMD.parse(data, n)
    old.type = SPECIES
    new = mmd.MMD.parse(result, n)
    new.type = SPECIES
    rig = quadruped.Rig(old, skeleton, PROFILE)
    cfg = IDLE
    frames, short = idle_frames(rig, cfg)
    events = [(t, kind, e) for t, kind, e in animsheet.slot_frames(old, n, 0)[2] if kind == 'tex' and t == 0]
    frames = [[[round(x) for x in bone] for bone in pose] for pose in frames]
    animation = mmd.encode_anim(frames, n, loop_sample=0, events=events, tol=1)
    index = old.anims.table[0]
    new.anims.anims[index] = animation
    played, _ = quadruped._played(animation, n, 0, cfg['ticks'])
    for tick in range(cfg['ticks'], cfg['ticks'] * 3 + 1, cfg['ticks']):
        assert all(abs(a - b) <= 2 for bone, other in zip(played[0][1:], played[tick][1:]) for a, b in zip(bone, other)), 'idle drift'
    floor = quadruped._floor(rig, played[:cfg['ticks'] + 1])
    assert floor <= PROFILE['floor'], ('idle under the floor', floor)
    assert short < 0.5, ('idle: a sole cannot reach', short)
    final = new.build()
    actual = mmd.MMD.parse(final, n)
    assert old.tmd.build() == actual.tmd.build()
    aliases = sorted(s for s, i in enumerate(old.anims.table) if i == index)
    changed = sorted(set(report['changed_slots']) | set(aliases))
    assert changed_programs(old, actual) == changed, (changed_programs(old, actual), changed)
    storage = motionstorage.require(final, n)
    report.update(output_sha256=hashlib.sha256(final).hexdigest(), changed_slots=changed, storage=storage)
    report['checks'].insert(0, dict(slot=0, gait='idle', ticks=cfg['ticks'], lowest_point=round(floor, 1), unreached=round(short, 2),
                                    stream_bytes=len(animation.build()), aliases=aliases))
    return final, report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/281-cyclonemon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
