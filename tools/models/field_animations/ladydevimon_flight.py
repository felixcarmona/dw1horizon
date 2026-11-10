"""LadyDevimon's field idle, walk and run as four different flights.

The import kept her field slots (idle 0 and 1, walk 2, condition walk 3, run 4) as one frozen pose: none of her bones
moved, only the root travelled, so the three read as the same statue sliding. This overlay takes her reviewed model
(chibi proportions included) and writes those five slots again (every other slot, the mesh, the rig and the hover height stay):

- Idle: a stationary hover, 60 ticks with two slow wide beats (one bigger every loop). Upright, the legs hanging a little
  apart, the arms a little forward, the head glancing around; hair, cloth and chain drift.
- Walk: a steady glide, one beat per loop with the wings spread wide and held up for part of it. A forward lean of 10
  degrees, one leg ahead, the arms swinging, the hair and cloth streaming back.
- Condition walk: low and heavy. The wings hang low and are lifted slowly, the shoulders hunched, the head and arms
  hanging, the legs limp, a slow sway side to side, the body sitting lower.
- Run: a dash leaning about 23 degrees, the wings swept back and narrowed with two small quick beats, the legs
  straight behind, the arms swept back, the head level, the hair and chain streaming.

Wings flap about a horizontal axis through the shoulder blade, each leaf about its own (the left leaf points sideways
and the right leaf back). Every clip repeats its pose cycle exactly (the last tick equals the first), the wings, body,
arms and legs share the one beat. Tick counts, the root travel (the field speed) and the footstep sounds are kept.
"""
import copy
import hashlib
import math

import animsheet
import mmd
import motioncyclelayer
import motionstorage
from motiondiscidentity import changed_programs
from tools.models.field_animations.lillymon_flight import Rig, swing, wave

SPECIES = 223
NB = 29
SLOTS = (0, 1, 2, 3, 4)
HAIR = (4, 5)
BACK = (8, 9)
CLOTH = 10
WING_L, WING_R = 6, 7
RIGHT_LEG, LEFT_LEG = (11, 12, 13), (14, 15, 16)
ARMS = ((17, 18, 19), (20, 21, 22))
FINGERS = (23, 24, 25, 26, 27)
CHAIN = 28
# the right leaf flaps about a horizontal axis perpendicular to its own sweep: world x and (negative) z components
RIGHT_AXIS = (.87, -.49)

#     per clip: ticks, wing beats per loop, share of the beat the downstroke takes (a little under a half), wing (centre, amplitude in degrees up
#     from the rest, sweep), body (bob in units, sink, lean, pitch and chest dip driven by the stroke, chest, twist, head
#     level, glance, sway, roll), trailing hair / ornament / chain / cloth, arms (lean, swing) and legs (trail,
#     one leg ahead, alternating swing, knee bend and tuck, pointed foot), the root's surge
CLIPS = {
    # a stationary hover: slow wide beats (one bigger every loop), upright, the legs hanging apart, the arms a little forward
    'idle': dict(n=60, beats=2, down=.47, wc=12, wa=15, boost=.35, hold=0, wsweep=0, sweep=5, bob=3, sink=0, lean=0, pitch=0,
                 dip=.8, chest=0, twist=1, head=0, stab=.9, glance=8, sway=3, roll=1.5, stream=0, hair=4, orn=3, chain=5,
                 cloth=4, arm=-5, arm_r=-6, arm_swing=2, trail=0, ahead=4, alt=1, apart=6, knee=10, tuck=2, foot=14, surge=0),
    # a steady glide: the wings spread wide and held up for part of the beat, the body leaning forward, the arms swinging
    'walk': dict(n=None, beats=1, down=.45, wc=24, wa=13, boost=0, hold=1.8, wsweep=0, sweep=5, bob=3, sink=0, lean=10, pitch=0,
                 dip=.8, chest=2, twist=1.5, head=-6, stab=.9, glance=1, sway=0, roll=0, stream=7, hair=6, orn=4, chain=7,
                 cloth=6, arm=6, arm_r=1, arm_swing=6, trail=5, ahead=6, alt=2, apart=0, knee=11, tuck=2, foot=16, surge=.08),
    # low and heavy: the wings fall low and are lifted slowly, the shoulders hunched, the head and arms hanging, the legs limp
    'tired': dict(n=None, beats=1, down=.68, wc=-9, wa=9, boost=0, hold=0, wsweep=0, sweep=2, bob=2, sink=12, lean=3, pitch=0,
                  dip=.8, chest=8, twist=0, head=16, stab=0, glance=0, sway=6, roll=3, stream=0, hair=3, orn=2, chain=3,
                  cloth=3, arm=0, arm_r=-10, arm_swing=1, trail=0, ahead=0, alt=1.5, apart=2, knee=2, tuck=1.5, foot=6, surge=.04),
    # a dash: stretched out, leaning far, the wings swept back and narrowed with quick small beats, the legs straight behind
    'run': dict(n=None, beats=2, down=.47, wc=-3, wa=8, boost=0, hold=0, wsweep=16, sweep=3, bob=1.5, sink=0, lean=23, pitch=0,
                dip=.5, chest=2, twist=.8, head=-20, stab=0, glance=0, sway=0, roll=0, stream=22, hair=5, orn=3, chain=8,
                cloth=5, arm=30, arm_r=10, arm_swing=2, trail=10, ahead=1, alt=2.5, apart=0, knee=2, tuck=1, foot=20, surge=.06),
}
CLIP_OF_SLOT = {0: 'idle', 1: 'idle', 2: 'walk', 3: 'tired', 4: 'run'}


def stroke(p, down, lag=0.):
    """The wing stroke, 1 at the top and -1 at the bottom: a quick power downstroke taking `down` of the beat and a slower
    recovery, each eased at both ends."""
    f = (p - lag) % 1.0
    u = .5 * f / down if f < down else .5 + .5 * (f - down) / (1 - down)
    return math.cos(2 * math.pi * u)


def pose_at(rig, rest, root, name, c, t, n):
    """The pose of clip `name` at tick t of n; root is the earlier clip's root pose (travel and sway)."""
    p, u = c['beats'] * t / n, t / n
    d = c['down']
    S = lambda lag=0.: stroke(p, d, lag)  # noqa: E731
    pose = copy.deepcopy(rest)
    if root is not None:
        pose[0] = list(root)
    # the downstroke drives the body: it rises with the wings going down, and settles on the recovery
    pose[1][7] = round(rest[1][7] + c['sink'] + c['bob'] * S(.03))
    pose[1][6] = round(rest[1][6] + c['sway'] * swing(u, .1))
    push = -c['pitch'] * S(.03)       # the torso pitches into each downstroke
    dip = -c['dip'] * S(.05)          # and the chest dips with it
    rig.turn(pose, 1, x=c['lean'] + push, y=c['twist'] * swing(p, .0), z=c['roll'] * swing(u, .25))
    rig.turn(pose, 2, x=c['chest'] + dip + 1.2 * swing(u, .0), y=-.8 * c['twist'] * swing(p, .0))
    # the head holds level against the body's motion and looks ahead; the idle glances around now and then
    glance = c['glance'] * (.7 * swing(u, .1) + .4 * swing(2 * u, .3))
    rig.turn(pose, 3, x=c['head'] - c['stab'] * (push + dip + 1.2 * swing(u, .0)), y=glance, z=.3 * glance * swing(u, .3))
    # hair, back ornament and cloth stream back and lag the body, each link a little later
    rig.turn(pose, HAIR[0], x=c['stream'] + c['hair'] * swing(p, .25), z=.3 * c['hair'] * swing(u, .1))
    rig.turn(pose, HAIR[1], x=.7 * c['stream'] + 1.3 * c['hair'] * swing(p, .40), z=.5 * c['hair'] * swing(u, .2))
    rig.turn(pose, BACK[0], x=c['orn'] * swing(p, .30))
    rig.turn(pose, BACK[1], x=1.5 * c['orn'] * swing(p, .45))
    rig.turn(pose, CLOTH, x=c['cloth'] * swing(p, .35))
    # wings: the power stroke, each leaf about its own axis, with a small sweep behind it
    st = S()
    if c['hold'] and st > 0:                       # the glide: the wings stay up for part of the beat
        st = math.tanh(c['hold'] * st) / math.tanh(c['hold'])
    a = c['wc'] + c['wa'] * (1 + c['boost'] * math.cos(2 * math.pi * u)) * st
    s = c['wsweep'] + c['sweep'] * swing(p, .15)
    rig.turn(pose, WING_L, y=s, z=a)
    rig.turn(pose, WING_R, x=RIGHT_AXIS[0] * a, y=-s, z=RIGHT_AXIS[1] * a)
    # arms held with purpose: they swing against the wings, forearms and hands a little behind
    for k, (sh, el, hand) in enumerate(ARMS):
        lean = (c['arm'], c['arm_r'])[k]    # the right arm hangs in front of its wing leaf: it must not sweep back into it
        sw = c['arm_swing'] * (1, .6)[k]
        rig.turn(pose, sh, x=lean - sw * S(.02))
        rig.turn(pose, el, x=.5 * lean - .8 * sw * S(.07))
        rig.turn(pose, hand, x=-.4 * sw * S(.12))
    for k, f in enumerate(FINGERS):
        rig.turn(pose, f, x=.8 * c['arm_swing'] * swing(p, .45 + .02 * k))
    rig.turn(pose, CHAIN, x=1.2 * c['stream'] + c['chain'] * swing(p, .40))
    # legs under control: one ahead of the other, alternating with the beat, the knees tucking on the recovery and
    # stretching on the power stroke, the feet pointed
    for k, (th, kn, ft) in enumerate((RIGHT_LEG, LEFT_LEG)):
        sign = 1 - 2 * k
        rig.turn(pose, th, x=c['trail'] - sign * (c['ahead'] + c['alt'] * swing(p, .0)), z=sign * c['apart'])
        bend = c['knee'] + c['tuck'] * (1 + S(.08 + .04 * k)) / 2
        rig.turn(pose, kn, x=bend)
        rig.turn(pose, ft, x=c['foot'] - .5 * bend)
    return pose


def root_at(frames, c, t, n):
    """The root pose at tick t: the earlier clip's sway, its travel spread smoothly with a surge on every power stroke.
    The distance and the number of ticks (the field speed) are the earlier clip's."""
    if c['n'] is not None:
        return frames[0][0]
    root = list(frames[t][0])
    beats, a, phase = c['beats'], c['surge'], .20
    u = t / n
    total = frames[-1][0][8] - frames[0][0][8]
    k = 2 * math.pi
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
        name = CLIP_OF_SLOT[slot]
        c = CLIPS[name]
        frames, loop, events = animsheet.slot_frames(old, NB, slot)
        assert loop == 0, (slot, loop)
        n = c['n'] or len(frames) - 1
        rig = Rig(old, skeleton)
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
    output, extra = author(data, skeleton)
    return output, dict(field_flight=extra, output_sha256=hashlib.sha256(output).hexdigest())
