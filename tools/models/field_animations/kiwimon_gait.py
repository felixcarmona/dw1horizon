"""Kiwimon's field gaits (species 282): walk, tired walk and run with planted feet on its own two legs.

Kiwimon is a long-beaked bird on thin legs. Bone 1 is the body, 2 the rump (it hangs behind the body), 3-6 the left leg
(a short thigh, the long shin, the ankle pad, the toes), 7-10 the right leg the same way, 11 the head with the upper
beak and the leaf crest, 12 the lower beak; the wings are part of the body mesh. Forward is -z.

The imported clips came from a biped with another leg length: the body bobbed 60 units, one leg swung 85 units up and
sideways while the other hung, and the soles slid by up to 100 % of the body's travel. Here `quadruped.py` plants each
foot (two-bone IK on the thigh and shin, the ankle pad flat on the floor with the toes riding on it), the legs step in
turn at half a cycle, and what is above them is written by `body`: the body bobs twice a cycle, rolls and shifts over the
loaded foot, yaws against the hips and leans into the run, the head steadies against it, the rump follows late. The
toes curl in the swing and open before they land (`extra`). Idle and every other slot keep what they have.

Offline: `tools/models/edit.py get 282` on the commit before this change, then
`python3 -m tools.models.field_animations.kiwimon_gait --source THAT.MMD --out AFTER.MMD` and `edit.py put 282 AFTER.MMD`.
"""
import argparse
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
from tools.models.field_animations.quadruped import mul, rot, set_rot  # noqa: E402

SPECIES = 282
SOURCE = '66c0856bd981becda546dbddec04f5f188b5192777d61944bb0bd2230abb5d49'   # `edit.py get 282` before this change
TAU = 2 * math.pi
BODY, RUMP, HEAD, JAW = 1, 2, 11, 12
TOES = {'LH': 6, 'RH': 10}


def harm(phase, *terms):
    """A sum of cosines: terms are (amplitude, rate, delay in cycles)."""
    return sum(a * math.cos(TAU * rate * (phase - delay)) for a, rate, delay in terms)


def turn(rig, pose, bone, degrees, hist):
    """The bone's rest rotation turned by `degrees` (x pitch nose-down, y yaw to the left, z roll to the right)."""
    set_rot(pose, bone, mul(rot(degrees), mmd.rot_matrix(*rig.rest[bone][3:6])), hist)


def saw(u, hold=0.7):
    """A head's thrust cycle in -1..1: it holds still in the world (so it slides back against the body) for most of
    the cycle, then snaps forward. Closed, and nothing like a sine."""
    sm = quadruped.smooth
    return -1 + 2 * sm(u / hold) if u < hold else 1 - 2 * sm((u - hold) / (1 - hold))


def bump(u, width):
    """A smooth one-off dip over the first `width` of the cycle (a peck), zero elsewhere."""
    return math.sin(math.pi * u / width) ** 2 if u < width else 0.0


def head_and_chest(rig, c, phase, pose, hist, pitch, yaw, roll):
    """Head thrust and counter-pitch, pecks, looks, the lower beak, the chest's breath and the rump trailing behind the body."""
    rest = rig.rest
    snap = saw((phase * c['rate'] - c['thrust_at']) % 1.0, c['hold'])
    pose[HEAD][8] = rest[HEAD][8] + c['thrust'] * snap
    peck = c['peck'] * bump((phase - c['peck_at']) % 1.0, c['peck_width'])
    nod = harm(phase - c['nod_lag'], (c['nod'], 2, c['nod_at']), (c['nod2'], 1, c['nod_at'] + 0.1))
    look = c['look'] * harm(phase, (1, 1, c['look_at']), (0.3, 2, c['look_at'] + 0.1))
    turn(rig, pose, HEAD, [-c['steady'] * (pitch - c['tilt']) - c['head'] + nod - c['thrust_pitch'] * snap + peck,
                           -0.6 * yaw + look, -0.6 * roll + 0.5 * look], hist)
    open_ = c['jaw'] * (0.5 + 0.5 * math.cos(TAU * c['rate'] * (phase - c['jaw_at']))) + c['jaw_peck'] * peck
    turn(rig, pose, JAW, [open_, 0, 0], hist)
    lag = c['lag']
    pitch_l = harm(phase - lag, (c['pitch'], 2, c['pitch_at']), (c['pitch1'], 1, c['pitch_at'] + 0.12))
    yaw_l = harm(phase - 1.5 * lag, (c['yaw'], 1, c['yaw_at']), (c['yaw2'], 3, c['yaw_at'] + 0.05))
    roll_l = harm(phase - 1.5 * lag, (c['roll'], 1, c['roll_at']), (c['roll2'], 3, c['roll_at'] + 0.06))
    breath = c['puff'] * math.cos(TAU * (phase - c['puff_at']))        # the chest breathes: the rump rocks a little
    turn(rig, pose, RUMP, [-0.9 * pitch_l - c['rump_up'] + breath, 0.8 * yaw_l, 0.9 * roll_l], hist)


def body(rig, cfg, phase, pose, hist):
    """Body height, sway, pitch, yaw and roll, then the head, beak, chest and rump (`head_and_chest`); all closed loops."""
    rest, c = rig.rest, cfg
    d = c['high']
    bob = harm(phase, (c['bob'], 2, d), (c['bob2'], 4, d + 0.03), (c['bob_side'], 1, d + 0.2))
    pose[BODY][7] = rest[BODY][7] - c['height'] - bob
    pose[BODY][6] = rest[BODY][6] + harm(phase, (c['shift'], 1, c['roll_at']), (c['shift2'], 3, c['roll_at'] + 0.07))
    pitch = c['tilt'] + harm(phase, (c['pitch'], 2, c['pitch_at']), (c['pitch1'], 1, c['pitch_at'] + 0.12))
    yaw = harm(phase, (c['yaw'], 1, c['yaw_at']), (c['yaw2'], 3, c['yaw_at'] + 0.05))
    roll = harm(phase, (c['roll'], 1, c['roll_at']), (c['roll2'], 3, c['roll_at'] + 0.06))
    turn(rig, pose, BODY, [pitch, yaw, roll], hist)
    head_and_chest(rig, c, phase, pose, hist, pitch, yaw, roll)


def toes(rig, cfg, phase, pose):
    """The toes curl under in the swing and open again before the landing."""
    for name, bone in TOES.items():
        stance, s = quadruped.leg_phase(cfg, name, phase)
        if stance:
            pitch = cfg['toe_push'] * quadruped.smooth((s - 0.7) / 0.3)
        else:
            pitch = cfg['toe_curl'] * math.sin(math.pi * min(1.0, s / 0.8)) if s < 0.8 else 0.0
            pitch = pitch * (1 - quadruped.smooth((s - 0.6) / 0.35)) + cfg['toe_push'] * (1 - quadruped.smooth(s / 0.3))
        set_rot(pose, bone, mul(mmd.rot_matrix(*rig.rest[bone][3:6]), rot([pitch, 0, 0])), {})


PROFILE = dict(
    species=SPECIES, name='Kiwimon', source=SOURCE,
    parents=[-1, 0, 1, 1, 3, 4, 5, 1, 7, 8, 9, 1, 11],
    pelvis=BODY, chest=None, neck=None, head=HEAD, tail=(), loose=(),
    legs={'LH': (3, 4, 5, -1, False), 'RH': (7, 8, 9, 1, False)},
    pole_world=True, rest_plane=True, pole={False: [1.0, 0.0, 0.35]},
    paw_rest={'LH': [0, 0, -1], 'RH': [0, 0, -1]},
    sole={False: [0, 13, -32]},
    reach={'front': 0, 'hind': 0},
    fold={False: 60}, clear=0,
    speed_range={2: (15, 31), 3: (10, 20), 4: (35, 52)},
    body=body, extra=toes, floor=3, stance_slip=0.2,
    gaits={},
)
COMMON = dict(
    kind='walk', snap=False, arc=1.0, clear_ease=0.4, fold_soft=10, slip=0.0, steps=('LH', 'RH'),
    reach={'front': 0, 'hind': -20}, lift={'front': 0, 'hind': 26}, curl={'front': 0, 'hind': 0}, peel={'front': 0, 'hind': 0},
    out={'front': 0, 'hind': 3}, wide={'front': 0, 'hind': 6}, heel=0,
    high=0.1, bob=3, bob2=0.8, bob_side=0.5, height=-14, shift=5, shift2=0.8, roll_at=0.3, roll=3, roll2=0.5,
    tilt=0, pitch=1.5, pitch1=0.5, pitch_at=0.15, yaw=3, yaw2=0.6, yaw_at=0.05, lag=0.08,
    steady=0.7, head=0, nod=1, nod2=0.5, nod_at=0.2, nod_lag=0.06, toe_curl=-14, toe_push=0,
    rate=2, thrust=8, thrust_at=0.1, hold=0.7, thrust_pitch=3, peck=0, peck_at=0.5, peck_width=0.3, look=0, look_at=0.3,
    jaw=1, jaw_at=0.2, jaw_peck=0.3, rump_up=0, puff=1.5, puff_at=0.0,
)
PROFILE['gaits'] = {
    # a cheerful waddle: the body rocks over each loaded foot, the head holds and snaps forward every step, one peck a cycle
    2: dict(COMMON, name='walk', ticks=14, speed=17,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.52, 'RH': 0.52}, lift={'front': 0, 'hind': 32},
            roll=5, shift=7, bob_side=1.0, thrust=9, thrust_pitch=4, peck=9, peck_at=0.55, peck_width=0.28, look=3, nod=1.5,
            jaw=1.5, puff=1.5, lag=0.07),
    # heavy: lower and leaning, slow big sways, the beak low and swinging, the jaw panting, a deep slow chest
    3: dict(COMMON, name='tired walk', ticks=18, speed=12,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.62, 'RH': 0.62}, height=-24, tilt=8, lift={'front': 0, 'hind': 18},
            roll=6, shift=6, bob=4, bob_side=1.2, thrust=4, hold=0.78, thrust_pitch=2, look=7, look_at=0.1, nod=1, jaw=4.5,
            jaw_at=0.35, puff=3.0, puff_at=0.2, lag=0.09, rump_up=-3),
    # eager: leaning forward, the beak thrust out with every stride, a bouncy bob
    4: dict(COMMON, name='run', kind='trot', ticks=10, speed=38,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.34, 'RH': 0.34}, height=-14, tilt=12, bob=6, bob2=1.2,
            lift={'front': 0, 'hind': 48}, thrust=8, hold=0.6, thrust_pitch=7, roll=4, shift=5, jaw=3.5, puff=1.5, lag=0.07,
            rump_up=2),
}


# A calm 2 s idle: slow breathing with the chest, a weight shift from foot to foot, the head looking about and one peck.
IDLE = dict(COMMON, name='idle', ticks=60, speed=0, rate=1, height=-8, bob=0.7, bob2=0.2, bob_side=1.4, high=0.0,
            shift=3.5, shift2=0.6, roll=1.4, roll2=0.3, roll_at=0.25, tilt=0, pitch=0.8, pitch1=0.6, yaw=2.0, yaw2=0.5, yaw_at=0.1,
            lag=0.07, thrust=0, thrust_pitch=0, nod=1.2, nod2=0.8, nod_at=0.35, nod_lag=0.1, look=11, look_at=0.35,
            peck=7, peck_at=0.68, peck_width=0.18, jaw=1.2, jaw_at=0.0, jaw_peck=0.25, puff=2.0, puff_at=0.0, steady=0.5)


def idle_frames(rig, cfg):
    """The idle loop: the body breathes and shifts over two planted soles, each solved onto where it stands at rest."""
    W, hist, frames, short = rig.still, {}, [], 0.0
    spots = {}
    for name, (up, lo, paw, side, front) in rig.p['legs'].items():
        world = rig.paw(front, 0, name)
        pivot = quadruped.add([W[paw][i][3] for i in range(3)], quadruped.mv(rig.R(W, paw), rig.sole(front)))
        spots[name] = (pivot[0], pivot[2], world)
    for t in range(cfg['ticks']):
        pose = [list(v) for v in rig.rest]
        pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
        body(rig, cfg, t / cfg['ticks'], pose, hist)
        for name, (up, lo, paw, side, front) in rig.p['legs'].items():
            x, z, world = spots[name]
            lower, out = rig.solve(pose, name, quadruped.standing(rig, name, x, z, world), hist, None, None)
            short = max(short, out)
            set_rot(pose, paw, mul(quadruped.tr(lower), world), hist)
        frames.append(pose)
    frames.append([list(v) for v in frames[0]])
    return frames, short


def build(data, skeleton):
    result, proof = quadruped.build(data, skeleton, PROFILE)
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
    changed = sorted(set(proof['changed_slots']) | set(aliases))
    assert changed_programs(old, actual) == changed, (changed_programs(old, actual), changed)
    storage = motionstorage.require(final, n)
    proof.update(output_sha256=hashlib.sha256(final).hexdigest(), changed_slots=changed, storage=storage)
    proof['checks'].insert(0, dict(slot=0, gait='idle', ticks=cfg['ticks'], lowest_point=round(floor, 1), unreached=round(short, 2),
                                   stream_bytes=len(animation.build()), aliases=aliases))
    return final, proof


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/282-kiwimon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
