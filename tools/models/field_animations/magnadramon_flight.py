"""Magnadramon's field idle, walk and run as three different flights.

The import gave the idle (slots 0 and 1), the walk (2), the condition walk (3) and the run (4) one and the same 89-tick
wave of its wing blades, body and tail; only the distance the root travelled differed, so the three read as one pose.
This overlay writes those five slots again on top of the reviewed steady glide (every other slot, the mesh and the
rig stay). The three pairs of wing blades beat from a folded rest along the back, each blade a little behind the
one before it, so a beat runs along the wing:

- Every clip opens the jaw (bone 5) after each wing downstroke, quickly, and eases it closed more slowly (20 to 28
  degrees; the idle also yawns once per loop, 35); the head lifts a little with the mouth. The run adds a quick pant (5).
- Idle: a hover in place. Two slow, wide beats in the 88 ticks, the body rising on every beat, the head and the
  tail trailing behind with a lag, the arms and legs hanging and swaying.
- Walk (and the tired condition walk, lower and slower): a cruise. The body leans forward, the wings beat three
  times per loop, the tail streams back with a travelling wave, the legs trail behind.
- Run: a faster flight. Leaning further, the wings beat four times per loop and fold closer in between, the tail is
  stretched out, the arms and legs swept back.

Each clip repeats its pose cycle exactly (the last tick equals the first). Tick counts, the root travel (the field
speed) of the earlier clips are kept.
"""
import copy
import hashlib
import math

import animsheet
import mmd
import motioncyclelayer
import motionstorage
from motiondiscidentity import changed_programs
from tools.models.field_animations import gliding

SPECIES = 215
NB = 30
DEG = 4096 / 360
SLOTS = (0, 1, 2, 3, 4)
# wing blades (right, left) from the inner pair outwards: folded and fully open z angle, 1/4096 turns
WINGS = ((12, 974, -85), (13, -981, 134), (15, 889, -238), (16, -879, 198), (18, 776, -249), (19, -695, 225))
ARMS = ((6, 7, 8), (9, 10, 11))
LEGS = ((24, 25, 26), (27, 28, 29))
HEAD_LIFT = .22   # degrees the head lifts per degree of open jaw
JAW_SIGN = 1      # the jaw (bone 5) opens with a positive pitch
SPINE = (1, 2, 3, 4)
TAIL = (20, 21, 22, 23)

CLIPS = {
    'idle': dict(n=88, beats=2, centre=.50, swing=.45, bob=24, lean=0, head=0, tail=0, tail_wave=7, arm=0, arm_swing=4,
                 leg=0, leg_swing=3, surge=0, jaw=20, pant=0, yawn=35),
    'walk': dict(n=None, beats=3, centre=.38, swing=.30, bob=17, lean=9, head=-6, tail=2, tail_wave=8, arm=14,
                 arm_swing=5, leg=14, leg_swing=4, surge=.08, jaw=28, pant=0, yawn=0),
    'tired': dict(n=None, beats=2, centre=.28, swing=.22, bob=11, lean=4, head=-3, tail=0, tail_wave=6, arm=7,
                  arm_swing=3, leg=7, leg_swing=3, surge=.06, jaw=20, pant=0, yawn=0),
    'run': dict(n=None, beats=4, centre=.30, swing=.27, bob=14, lean=20, head=-13, tail=12, tail_wave=6, arm=30,
                arm_swing=4, leg=32, leg_swing=3, surge=.07, jaw=28, pant=5, yawn=0),
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


def ease(x):
    x = min(1., max(0., x))
    return x * x * (3 - 2 * x)


def span(u, a, b, c, d):
    """0 before a, rising to 1 by b, held to c, back to 0 by d."""
    return ease((u - a) / (b - a)) * (1 - ease((u - c) / (d - c)))


def bite(u):
    """One mouth cycle, 0..1: open fast (30 % of the cycle), close slowly (50 %), rest shut (the last 20 %)."""
    return span(u, 0., .30, .30, .80)


def pose_at(rig, rest, root, c, t, n):  # noqa: C901
    """The pose of clip c at tick t of n; root is the earlier clip's root pose with the travel."""
    p = c['beats'] * t / n
    q = t / n
    pose = copy.deepcopy(rest)
    pose[0] = list(root)
    # wings: each blade between folded (0) and open (1), a beat behind the inner one
    for k, (bone, fold, opened) in enumerate(WINGS):
        g = c['centre'] + c['swing'] * wave(p, .09 * (k // 2) + .015 * (k % 2))
        pose[bone][5] = round(fold + (opened - fold) * g)
    # the body rises with the wings' downstroke and breathes slowly
    pose[1][7] = round(rest[1][7] - c['bob'] * (.5 + .5 * wave(p, .30)) - .25 * c['bob'] * swing(q))
    pose[1][3] = round(rest[1][3] + DEG * (c['lean'] + (1 + .05 * c['lean']) * swing(p, .1)))
    pose[2][3] = round(rest[2][3] + DEG * 2 * swing(p, .18))
    pose[3][3] = round(rest[3][3] + DEG * (.5 * c['head'] + 1.5 * swing(p, .26)))
    pose[4][3] = round(rest[4][3] + DEG * (.5 * c['head'] + 2.5 * swing(p, .34)))
    # the jaw: opens quickly after every wing downstroke, eases closed more slowly and rests shut a moment; the idle
    # adds one long yawn per loop on top of its breaths and the run a quicker, smaller pant. The head lifts with the
    # mouth and drops as it closes, the neck following a little later.
    mouth = c['jaw'] * bite((p - .30) % 1.) + c['pant'] * (.5 + .5 * swing(2 * p, .1))
    if c['yawn']:
        mouth = max(mouth, c['yawn'] * span(q, .06, .18, .40, .58))
    pose[5][3] = round(rest[5][3] + JAW_SIGN * DEG * mouth)
    pose[4][3] -= round(DEG * HEAD_LIFT * mouth)
    pose[3][3] -= round(DEG * .5 * HEAD_LIFT * mouth)
    pose[2][3] += round(DEG * 1.2 * swing(p, .30))
    # the tail trails the body: a wave running down it
    for k, bone in enumerate(TAIL):
        pose[bone][3] = round(rest[bone][3] + DEG * (c['tail'] / 4 + c['tail_wave'] * (k + 1) / 4 * swing(p, .16 + .10 * k)))
    # arms and legs hang or trail behind with the lean, following the beat a little later
    for k, (a, b, h) in enumerate(ARMS):
        off = .05 * k
        rig.turn(pose, a, x=c['arm'] + c['arm_swing'] * swing(p, .12 + off))
        rig.turn(pose, b, x=.5 * c['arm'] + c['arm_swing'] * swing(p, .22 + off))
        rig.turn(pose, h, x=.4 * c['arm_swing'] * swing(p, .32 + off))
    for k, (a, b, h) in enumerate(LEGS):
        off = .05 * k
        rig.turn(pose, a, x=c['leg'] + c['leg_swing'] * swing(p, .14 + off))
        rig.turn(pose, b, x=.5 * c['leg'] + c['leg_swing'] * swing(p, .24 + off))
        rig.turn(pose, h, x=.4 * c['leg_swing'] * swing(p, .34 + off))
    return pose


def root_at(frames, c, t, n):
    """The root pose at tick t: the travel spread evenly (a mild surge on every wing beat); distance and ticks are the
    earlier clip's. The idle stays where it is."""
    root = list(frames[0][0])
    if c['n'] is not None:
        return root
    beats, a, phase = c['beats'], c['surge'], .30
    u, k = t / n, 2 * math.pi
    total = frames[-1][0][8] - frames[0][0][8]
    root[8] = frames[0][0][8] + total * (u + a / (k * beats) * (math.sin(k * (beats * u - phase)) + math.sin(k * phase)))
    return root


def author(model, skeleton):
    """`model` with the five field slots replaced -> (bytes, checks)."""
    mmd.exe().add_type(SPECIES, skeleton)
    old = mmd.MMD.parse(model, NB)
    old.type = SPECIES
    rest = [list(v) for v in animsheet.slot_frames(old, NB, 0)[0][0]]
    result = copy.deepcopy(old)
    streams, checks = {}, []
    for slot in (0, 2, 3, 4):
        c = CLIPS[CLIP_OF_SLOT[slot]]
        frames, loop, events = animsheet.slot_frames(old, NB, slot)
        assert loop == 0, (slot, loop)
        n = c['n'] or len(frames) - 1
        rig = Rig(old, skeleton)
        out = [pose_at(rig, rest, root_at(frames, c, t, n), c, t, n) for t in range(n + 1)]
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
    result, proof = gliding.build(data, skeleton)
    output, extra = author(result, skeleton)
    return output, dict(proof, field_flight=extra, output_sha256=hashlib.sha256(output).hexdigest())
