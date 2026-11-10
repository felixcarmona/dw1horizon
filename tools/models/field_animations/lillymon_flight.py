"""Lillymon's field idle, walk and run as three different flights.

The import kept her flight in a private clip and left the field slots (idle 0 and 1, walk 2, condition walk 3, run 4)
as one frozen pose that only the root travelled through: the three read as the same standing glide. This overlay
writes those five slots again on top of the reviewed celebration overlay (every other slot, the mesh and the rig stay):

- Idle: a hover in place. The wings flutter gently (three beats in 48 ticks), the body rises a little on every beat
  and breathes, the arms, legs, hair and flower sway behind the body with a lag.
- Walk (and the tired condition walk, lower and slower): a cruise. The body leans forward, the wings beat twice per
  loop, the legs trail behind with the knees and feet lagging the thighs, the arms sweep back and the head stays level.
- Run: a calmer faster flight, leaning further, the wings beating twice per loop, the arms and legs streamlined back and steady.

Each clip repeats its pose cycle exactly (the last tick equals the first). Tick counts, the root travel (the field speed)
and the footstep sounds of the earlier walk and run clips are kept.
"""
import copy
import hashlib
import math

import animsheet
import mmd
import motioncyclelayer
import motionstorage
from motiondiscidentity import changed_programs
from motiontailspace import interpolate_pose
from tools.models.field_animations import celebrations

SPECIES = 209
NB = 23
DEG = 4096 / 360
SLOTS = (0, 1, 2, 3, 4)
WINGS = {18: 781, 19: -972, 20: -743, 21: 980}   # spread of each wing leaf, from its folded rest, in 1/4096 turns
LEFT, RIGHT = (9, 10, 11), (6, 7, 8)
LEGS = ((12, 13, 14), (15, 16, 17))

#          ticks, wing beats, wing centre, wing swing, bob, lean, head, thigh, knee, arm back, arm swing, sway
CLIPS = {
    'idle': dict(n=48, beats=3, centre=.30, swing=.13, bob=16, lean=0, head=0, leg_swing=1, thigh=3, knee=4, arm=3, arm_swing=4, sway=5, surge=0),
    'walk': dict(n=None, beats=2, centre=.38, swing=.20, bob=14, lean=12, head=-7, leg_swing=1, thigh=9, knee=9, arm=12, arm_swing=7, sway=7, surge=.15),
    'tired': dict(n=None, beats=2, centre=.28, swing=.15, bob=10, lean=6, head=-3, leg_swing=1, thigh=5, knee=5, arm=5, arm_swing=4, sway=5, surge=.10),
    'run': dict(n=None, beats=2, centre=.45, swing=.25, bob=12, lean=22, head=-14, leg_swing=.3, thigh=10, knee=8, arm=26, arm_swing=6, sway=6, surge=.12),
}
CLIP_OF_SLOT = {0: 'idle', 1: 'idle', 2: 'walk', 3: 'tired', 4: 'run'}


def mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def transpose(a):
    return [list(r) for r in zip(*a)]


def rot(x=0., y=0., z=0.):
    return mmd.rot_matrix(x * DEG, y * DEG, z * DEG)


def worlds(model, pose):
    p = [list(v) for v in pose]
    p[0] = [4096] * 3 + [0] * 6
    return [[row[:3] for row in w[:3]] for w in mmd.bone_matrices(model, p)]


class Rig:
    """Turns bones about the world axes (x across, y down, z back) on a pose, parents before children."""

    def __init__(self, model, skeleton):
        self.m, self.parent = model, [p for _, p in skeleton]
        self.angles = {}

    def turn(self, pose, bone, x=0., y=0., z=0.):
        if not (x or y or z):
            return
        w = worlds(self.m, pose)
        parent = w[self.parent[bone]]
        local = mul(transpose(parent), mul(rot(x, y, z), w[bone]))
        angles = mmd.matrix_euler(local, self.angles.get(bone, pose[bone][3:6]))
        self.angles[bone] = angles
        pose[bone][3:6] = [round(v) for v in angles]


def wave(phase, lag=0.):
    """One smooth beat, quick and then slow, -1..1."""
    u = 2 * math.pi * (phase - lag)
    return math.cos(u + .40 * math.sin(u))


def swing(phase, lag=0.):
    return math.sin(2 * math.pi * (phase - lag))


def eased(x):
    return x * x * (3 - 2 * x)


def pose_at(rig, rest, root, name, c, t, n, side_lag=0.):
    """The pose of clip `name` at tick t of n; root is the earlier clip's root pose (travel and sway), or None."""
    p = c['beats'] * t / n
    pose = copy.deepcopy(rest)
    if root is not None:
        pose[0] = list(root)
    # wings: spread by g between folded rest (0) and open (1), beating about a centre with a skewed, smooth stroke
    g = c['centre'] + c['swing'] * wave(p, .0)
    for bone, spread in WINGS.items():
        pose[bone][4] = round(rest[bone][4] + spread * min(1., max(0., g + .03 * swing(p, .25 + .02 * (bone - 18)))))
    # the body rises with the downstroke and breathes slowly
    breath = swing(t / n, .0)
    pose[1][7] = round(rest[1][7] - c['bob'] * (.5 + .5 * wave(p, .30)) - .25 * c['bob'] * breath)
    lean = c['lean'] + (1.2 + .05 * c['lean']) * swing(p, .1)
    rig.turn(pose, 1, x=lean)
    rig.turn(pose, 2, x=2.0 * breath * (1 if name == 'idle' else .5))
    rig.turn(pose, 3, x=c['head'] + 1.5 * swing(p, .35))
    # hair, flower and sash lag the head and body
    for bone, lag in ((4, .25), (5, .30), (22, .38)):
        rig.turn(pose, bone, x=c['sway'] * swing(p, lag) - .15 * c['lean'], z=.6 * c['sway'] * swing(t / n, lag))
    # arms: swept back with the lean, swinging with the beat, the hands behind the elbows
    for k, (sh, el, hand) in enumerate((RIGHT, LEFT)):
        sgn = 1 if k == 0 else -1
        off = .07 * k
        rig.turn(pose, sh, x=c['arm'] + c['arm_swing'] * swing(p, .10 + off), z=sgn * (3 + .15 * c['arm']))
        rig.turn(pose, el, x=.5 * c['arm'] + c['arm_swing'] * swing(p, .22 + off))
        rig.turn(pose, hand, x=.4 * c['arm_swing'] * swing(p, .34 + off))
    # legs trail behind, knees and feet following the thighs one step later
    for k, (th, kn, ft) in enumerate(LEGS):
        off = .06 * k
        rig.turn(pose, th, x=c['thigh'] + .35 * c['leg_swing'] * c['thigh'] * swing(p, .12 + off))
        rig.turn(pose, kn, x=c['knee'] + .5 * c['leg_swing'] * c['knee'] * swing(p, .24 + off))
        rig.turn(pose, ft, x=-.4 * c['knee'] + .35 * c['leg_swing'] * c['knee'] * swing(p, .36 + off))
    return pose


def root_at(frames, c, t, n):
    """The root pose at tick t: the earlier clip's sway, and its travel spread smoothly instead of in bursts, with a mild
    surge on every wing beat. The distance and the number of ticks (the field speed) are the earlier clip's."""
    if c['n'] is not None:
        return frames[0][0]
    root = list(frames[t][0])
    beats, a, phase = c['beats'], c['surge'], .30
    u = t / n
    total = frames[-1][0][8] - frames[0][0][8]
    k = 2 * math.pi
    root[8] = frames[0][0][8] + total * (u + a / (k * beats) * (math.sin(k * (beats * u - phase)) + math.sin(k * phase)))
    return root


def author(model, skeleton, proof=None):
    """`model` with the five field slots replaced -> (bytes, checks)."""
    mmd.exe().add_type(SPECIES, skeleton)
    old = mmd.MMD.parse(model, NB)
    old.type = SPECIES
    rest = animsheet.slot_frames(old, NB, 0)[0][0]
    rest = [list(v) for v in rest]
    result = copy.deepcopy(old)
    streams, checks = {}, []
    for slot in (0, 2, 3, 4):
        name = CLIP_OF_SLOT[slot]
        c = CLIPS[name]
        frames, loop, events = animsheet.slot_frames(old, NB, slot)
        assert loop == 0, (slot, loop)
        n = c['n'] or len(frames) - 1
        rig = Rig(old, skeleton)
        # a moving clip keeps the earlier clip's root (field speed, sway); the idle stays put
        out = [pose_at(rig, rest, root_at(frames, c, t, n), name, c, t, n) for t in range(n + 1)]
        out = [[[round(x) for x in v] for v in pose] for pose in out]
        mmd.close_loop(out, 0)
        streams[slot] = len(result.anims.anims)
        result.anims.anims.append(mmd.encode_anim(out, NB, 0, list(events), tol=1))
    streams[1] = streams[0]
    for slot in SLOTS:
        result.anims.table[slot] = streams[slot]
    for anim in result.anims.anims:
        anim.tail = b''
    result.anims.anims, result.anims.table = motioncyclelayer.share_identical_streams(result.anims.anims,
                                                                                    result.anims.table)
    output = result.build()
    effective = mmd.MMD.parse(output, NB)
    effective.type = SPECIES
    assert effective.tmd.build() == old.tmd.build()
    assert changed_programs(old, effective) == list(SLOTS), changed_programs(old, effective)
    for slot in SLOTS:
        samples, loop, _ = animsheet.slot_frames(effective, NB, slot)
        assert loop == 0
        checks.append(dict(slot=slot, ticks=len(samples) - 1,
                           root_per_tick=round((samples[-1][0][8] - samples[0][0][8]) / (len(samples) - 1), 1)))
    return output, dict(checks=checks, storage=motionstorage.require(output, NB))


def build(data, skeleton):
    result, proof = celebrations.build(data, skeleton)
    output, extra = author(result, skeleton)
    return output, dict(proof, field_flight=extra, output_sha256=hashlib.sha256(output).hexdigest())
