"""Flymon's field idle, walk, condition walk and run as four different flights.

The import played one 29-tick pose sequence in the walk, the condition walk and the run (only the root speed differed)
and the same in the idle: the big wasp read as one animation. This generator writes slots 0 and 1 (idle), 2, 3 and 4
again from the reviewed model (every other slot, the mesh and the rig stay). Flymon hangs from its wings: the legs and
the four small arms dangle, the abdomen trails, the antennae flick, all of it a little later than the body that carries it.

- Idle (30 ticks, as short as the import's: a long idle hides the partner's condition idles): a hover in place. Two slow, small wing beats per loop, the body rises on every downstroke and
  breathes, the abdomen pumps, the legs, arms and antennae dangle behind the rise, the whole body turns a little
  from side to side (the head is the body's root bone, so the head turn is a slight yaw of the body).
- Walk (30 ticks, 18 units per tick): a relaxed flight. Three beats of medium size, the body leaning 11 degrees,
  a gentle bob, the legs trailing behind with the claws lagging the legs, the arms swaying one against the other.
- Condition walk (40 ticks, 13 units per tick): heavy and slow. Two big, slow, labouring beats, the body low (its feet
  nearly touch the ground), the nose dipping and heaving with every beat, the abdomen drooping, the legs and arms hanging
  straight down and swinging lazily.
- Run (20 ticks, 38 units per tick): a fast dash. The body leans 30 degrees into it, four short, quick beats, the legs
  and arms streamlined back, the abdomen streaming behind with a delay, a slight roll and yaw weave.

The wings beat about the front-to-back axis from their own hinge (they stay attached), each beat a quick downstroke
and a slower recovery, the beats of a loop a little unequal, the left wing a little behind the right and the small upper
pair a little behind the large pair; a soft spring chases the stroke so it overshoots. The body's rise, the abdomen, the
legs, the arms and the antennae are chains of springs on that stroke (each link later than the one before). Every cycle
repeats exactly (the last tick equals the first), the root travels the same distance every tick, and the lowest point
of the mesh is held a clearance above the floor.

Changed against the import: the loop lengths (all four were 29 ticks: idle 30, walk 30, condition walk 40, run 20) and the root
speeds rounded to whole units per tick (17.9, 13.2, 38.2 -> 18, 13, 38); the footstep sound stays once per loop.

Offline authoring (the player's build replays the plain delta): `tools/models/edit.py get 262`, then
`python3 -m tools.models.field_animations.flymon_flight --source build/imported-model-edit/edit/262-Flymon.MMD
--out AFTER.MMD` and `tools/models/edit.py put 262 AFTER.MMD`. The source must be the model this module started from.
"""
import copy
import hashlib
import math

import animsheet
import mmd
import motioncyclelayer
import motionstorage
from motiondiscidentity import changed_programs
from tools.models.field_animations.lillymon_flight import Rig, swing
from tools.models.field_animations.quetzalmon_flight import follow

SPECIES = 262
NB = 29
SLOTS = (0, 1, 2, 3, 4)
SOURCE = '74d2ac255768b1de7320fbbb3f087d0b40d38fa83e372f17fd7bc34bee337e5e'
BODY, CHEST, ABDOMEN = 1, 2, 3
WINGS = ((4, -1, 0.), (5, 1, .02), (6, -1, .07), (7, 1, .09))        # bone, down-stroke sign of the z turn, lag in beats
LEGS = ((9, (10, 11, 12)), (14, (15, 16, 17)))                         # thigh, its claws (left, right)
ARMS = ((18, 19), (22, 23), (20, 21), (24, 25))                        # shoulder, forearm (left front/rear, right front/rear)
ANTENNAE = (26, 27, 28)

GAP = 10          # degrees the legs hang behind the rear arms

#   n ticks, speed (units per tick, forward is -z), beats per loop, sway cycles per loop, wing centre and swing (degrees
#   down from the folded rest), sweep, body rise (units), lean and heave (degrees), roll and yaw weave, abdomen base and
#   trail, legs base, trail and swing, claws, arms base, out, trail and swing, antennae, clearance above the floor.
CLIPS = {
    'idle': dict(n=30, speed=0, beats=2, cyc=1, centre=6, swing=13, sweep=3, bob=15, lean=1.5, heave=2.5, roll=1.5, yaw=3.5,
                 abd=2, abd_trail=7, abd_yaw=4, leg=1, leg_trail=7, leg_swing=3, claw=9, arm=5, arm_out=3, arm_trail=9,
                 arm_swing=4, ant=10, gap=GAP, splay=2, fore_out=14, upper=0, clear=26),
    'walk': dict(n=30, speed=18, beats=3, cyc=1, centre=7, swing=17, sweep=5, bob=12, lean=11, heave=3, roll=2, yaw=2.5,
                 abd=-4, abd_trail=9, abd_yaw=3, leg=10, leg_trail=9, leg_swing=5, claw=12, arm=8, arm_out=3, arm_trail=10,
                 arm_swing=7, ant=12, gap=19, splay=2, fore_out=14, upper=0, clear=24),
    'tired': dict(n=40, speed=13, beats=2, cyc=1, centre=11, swing=21, sweep=4, bob=9, lean=9, heave=7, roll=3, yaw=2,
                  abd=-16, abd_trail=10, abd_yaw=4, leg=-2, leg_trail=6, leg_swing=7, claw=-6, arm=-5, arm_out=1,
                  arm_trail=7, arm_swing=8, ant=-6, gap=GAP, splay=2, fore_out=14, upper=5, clear=7),
    'run': dict(n=20, speed=38, beats=4, cyc=1, centre=3, swing=9, sweep=4, bob=7, lean=30, heave=2, roll=4, yaw=3.5,
                abd=-4, abd_trail=10, abd_yaw=3, leg=9, leg_trail=5, leg_swing=3, claw=14, arm=28, arm_out=6,
                arm_trail=6, arm_swing=3, ant=22, gap=14, splay=14, fore_out=22, upper=0, clear=36),
}
TOL = {0: 1, BODY: 1, None: 7}      # model units on the root and the body's offsets, 1/4096 turns on every other bone (0.6 degrees)
CLIP_OF_SLOT = {0: 'idle', 1: 'idle', 2: 'walk', 3: 'tired', 4: 'run'}


def lagged(values, n, beat, factor, zeta):
    """The periodic samples (n + 1, the last equal to the first) chased by a damped spring about `factor` beats slow."""
    def sig(t):
        k = int(t) % n
        f = t - int(t)
        return values[k] * (1 - f) + values[(k + 1) % n] * f
    out = follow(sig, n, 2 * math.pi / (factor * beat), zeta)
    out[-1] = out[0]
    return out


def stroke(c, u, lag=0.):
    """-1 (up) .. 1 (down): a quick downstroke and a slower recovery with a second harmonic, the beats of a loop unequal."""
    p = c['beats'] * (u - lag / c['beats'])
    w = 2 * math.pi * p
    s = math.sin(w - .55 * math.sin(w)) + .12 * math.sin(2 * w + 1.1)
    return s * (1 + .07 * math.sin(2 * math.pi * (u - lag / c['beats']) * 1 + .6))


def tracks(c):
    n, beat = c['n'], c['n'] / c['beats']
    ts = range(n + 1)
    drive = [stroke(c, t / n) for t in ts]
    wing = {}
    for bone, _, lag in WINGS:
        s = [stroke(c, t / n, lag) for t in ts]
        wing[bone] = lagged(s[:-1], n, beat, .45, .55)
    rise = lagged(drive[:-1], n, beat, 1.5, .45)
    lo, hi = min(rise), max(rise)
    rise = [(x - lo) / (hi - lo) - .5 for x in rise[:-1]]
    rise.append(rise[0])
    vel = [(rise[(k + 1) % n] - rise[k - 1]) / 2 for k in range(n)]
    scale = max(abs(x) for x in vel) or 1.
    vel = [x / scale for x in vel]
    vel.append(vel[0])
    chain = {}
    for name, links, factor, zeta in (('abd', 2, .8, .45), ('leg', 3, .7, .4), ('arm', 3, .65, .4), ('ant', 3, .45, .35)):
        seq = [vel]
        for _ in range(links):
            seq.append(lagged(seq[-1][:-1], n, beat, factor, zeta))
        chain[name] = seq[1:]
    return dict(wing=wing, rise=rise, vel=vel, **chain)


def pose_at(rig, rest, c, tr, t):
    n = c['n']
    u = t / n
    cyc = c['cyc']
    pose = copy.deepcopy(rest)
    pose[0] = list(rest[0])
    pose[0][8] = round(-c['speed'] * t) if c['speed'] else 0
    h = tr['rise'][t]
    pose[BODY][7] = round(rest[BODY][7] - c['bob'] * h)
    pose[BODY][6] = round(rest[BODY][6] + 3 * swing(cyc * u, .15))
    pitch = c['lean'] - c['heave'] * h + .8 * swing(cyc * u, .3)
    roll = c['roll'] * (.7 * swing(cyc * u, .1) + .35 * swing(2 * cyc * u, .4))
    yaw = c['yaw'] * (.75 * swing(cyc * u, .0) + .3 * swing(2 * cyc * u, .35))
    rig.turn(pose, BODY, x=pitch, y=yaw, z=roll)
    rig.turn(pose, CHEST, x=-.35 * (c['lean'] - c['heave'] * h) + 1.2 * swing(cyc * u, .5))
    ab = tr['abd']
    rig.turn(pose, ABDOMEN, x=c['abd'] + c['abd_trail'] * (.6 * ab[0][t] + .4 * ab[1][t]),
             y=c['abd_yaw'] * (swing(cyc * u, .3) + .3 * swing(2 * cyc * u, .1)))
    # wings: down-stroke is a turn of the left wings about -z and of the right wings about +z, from the folded rest
    for bone, sign, lag in WINGS:
        s = tr['wing'][bone][t]
        v = (tr['wing'][bone][(t + 1) % n] - tr['wing'][bone][(t - 1) % n]) / 2
        v *= n / (2 * c['beats'])
        angle = c['centre'] + c['swing'] * s - (c['upper'] if bone in (6, 7) else 0)
        rig.turn(pose, bone, x=c['sweep'] * (s - .3 * v), z=sign * angle)
    # arms first, then the legs a little further back than the rear arms (they hang side by side: the legs trail the arms)
    arm, leg = tr['arm'], tr['leg']
    shoulder = {}
    for k, (sh, fo) in enumerate(ARMS):
        side = 1 if k in (0, 1) else -1        # outward: a turn about z that moves a hanging limb's tip away from the body
        off = .05 * (k % 2) + .07 * (k // 2)
        sway = c['arm_swing'] * (swing(cyc * u, .2 + off) + .3 * swing(2 * cyc * u, .4 + off))
        shoulder[k] = c['arm'] + c['arm_trail'] * arm[0][t] + sway
        rig.turn(pose, sh, x=shoulder[k], z=side * (c['arm_out'] + .1 * c['arm']))
        rig.turn(pose, fo, x=.5 * c['arm'] + 1.3 * c['arm_trail'] * arm[1][t] + .6 * sway, z=side * c['fore_out'] * (1 if k % 2 else .5))
    for k, (thigh, claws) in enumerate(LEGS):
        off = .05 + .07 * k
        sway = c['leg_swing'] * (swing(cyc * u, .12 + off) + .3 * swing(2 * cyc * u, .3 + off))
        base = max(shoulder[2 * k + 1], c['leg'] + c['leg_trail'] * leg[0][t] + sway)
        rig.turn(pose, thigh, x=base + c['gap'], z=(1 if k == 0 else -1) * (1.5 + c['splay']))
        for j, cl in enumerate(claws):
            rig.turn(pose, cl, x=c['claw'] * (.35 + .1 * j) + 1.3 * c['leg_trail'] * leg[1 + j % 2][t] + .6 * sway * (1 + .3 * j))
    ant = tr['ant']
    for k, b in enumerate(ANTENNAE):
        rig.turn(pose, b, x=c['ant'] * (.6 + .15 * k) + 6 * ant[k][t], z=(k - 1) * 3 * swing(cyc * u, .2 + .1 * k))
    return pose


def author(model, skeleton):
    """`model` with the five field slots replaced -> (bytes, checks)."""
    if hashlib.sha256(model).hexdigest() != SOURCE:
        raise ValueError('Flymon flight requires the reviewed pinned source')
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
        n = c['n']
        # the one footstep sound of the earlier clip stays once per loop, at the same share of it
        shift = lambda e: round(e[0] * n / (len(frames) - 1))  # noqa: E731
        events = [(shift(e), e[1], dict(e[2], frame=shift(e))) for e in events]
        rig = Rig(old, skeleton)
        tr = tracks(c)
        out = [pose_at(rig, rest, c, tr, t) for t in range(n + 1)]
        out = [[[round(x) for x in v] for v in pose] for pose in out]
        # one constant lift for the whole loop puts the lowest point of the mesh `clear` units above the floor
        low = max(max(v[1] for tri in animsheet.world_tris(old, [[4096, 4096, 4096, 0, 0, 0, 0, 0, 0]] + pose[1:], skeleton)
                      for v in tri[0]) for pose in out)
        for pose in out:
            pose[BODY][7] += round(-c['clear'] - low)
        mmd.close_loop(out, 0)
        streams[slot] = len(result.anims.anims)
        result.anims.anims.append(mmd.encode_anim(out, NB, 0, list(events), tol=TOL))
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


if __name__ == '__main__':
    import argparse
    import json
    import sys
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--source', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    sys.path.insert(0, 'tools')
    rig = json.load(open('content/species/262-flymon.json'))['model']['skeleton']
    data, proof = build(open(args.source, 'rb').read(), rig)
    open(args.out, 'wb').write(data)
    print(len(data), 'bytes', proof['field_flight'])
