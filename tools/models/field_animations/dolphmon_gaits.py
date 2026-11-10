"""Dolphmon's field idle, walk, condition walk and run as four different dolphin movements.

The earlier overlay (`dolphmon.py`) gave all four clips the one native 73-tick swim, lifted off the ground, so they
differed only in speed. This overlay runs after it, keeps its sleeping clip (slot 1) and writes slots 0, 2, 3 and 4 again
on the reviewed rig (body, head, jaw, two flippers, a five-bone tail ending in the fluke):

- Idle (72 ticks): the dolphin rests on its belly. The body turns slowly left and right, the head looks around, the
  jaw chatters, the flippers paddle along the floor and a soft wave runs along the tail.
- Walk (20 ticks, 22 units a tick): a flipper scoot. The flippers push alternately, each planted on the ground
  while the body turns over it, then skimmed forward just above the floor; the tail wave travels from the body to the
  fluke.
- Condition walk (30 ticks, 14 units): slower and heavier, with short flipper strokes, a small sway and a panting jaw.
- Run (14 ticks, 40 units): the walk's scoot made quicker and bigger: the same strokes, body wave, head and single tail
  beat, with a shorter period, longer flipper strokes, a wider sway and a livelier jaw.

No clip moves vertically: the body bone keeps one height in every tick, every pose is made of turns about the vertical
axis, a little roll and the flipper strokes, with the head turning against the body's turn so that it keeps facing the
camera (turned past about 12 degrees it hides its far eye), and the lowest mesh point stays within a unit of the floor. Each clip
repeats its pose cycle exactly. Footstep sounds keep their share of the loop.
"""
import copy
import hashlib
import json
import math

import numeric as np
import animsheet
import mmd
import motioncyclelayer
import motionstorage
from motiondiscidentity import changed_programs
from tools.models.field_animations import dolphmon
from tools.models.field_animations.lillymon_flight import Rig, swing

SPECIES = 238
NB = 11
SLOTS = (0, 2, 3, 4)
BODY, HEAD, JAW, FLIP_R, FLIP_L = 1, 2, 3, 4, 5
TAIL = (6, 7, 8, 9, 10)
FLIPPERS = (FLIP_R, FLIP_L)
TAU = 2 * math.pi

# ticks, units forward per tick (the root runs along -z)
CLIPS = {
    'idle': dict(n=72, speed=0),
    'walk': dict(n=20, speed=22),
    'tired': dict(n=30, speed=14),
    'run': dict(n=14, speed=40),
}
CLIP_OF_SLOT = {0: 'idle', 2: 'walk', 3: 'tired', 4: 'run'}
SOURCE_PERIOD = 20


def smooth(x):
    x = min(1., max(0., x))
    return x * x * (3 - 2 * x)


class Dolphin:
    """Poses the rig and measures it: the lowest body point sets the ground, planted flippers are solved onto it."""

    def __init__(self, model, skeleton, rest):
        self.model, self.sk, self.rest = model, skeleton, rest
        self.drop = 0
        self.verts = {b: np.array(model.tmd.obj_verts(oi))[:, :3] for b, (oi, _) in enumerate(skeleton) if oi >= 0}

    def world(self, pose):
        g = copy.deepcopy(pose)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(self.model, g))

    def low(self, pose, bones):
        """Greatest y (lowest point) of the given bones' meshes."""
        w = self.world(pose)
        return max(float((self.verts[b] @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max()) for b in bones)

    def tip(self, pose, bone):
        w = self.world(pose)
        v = self.verts[bone] @ w[bone, :3, :3].T + w[bone, :3, 3]
        return v

    def pose(self, spec):
        """spec: body (pitch, yaw, roll), head (pitch, yaw), jaw, tail [(pitch, yaw)] * 5, flipper [(sweep, roll)] * 2,
        lift (height of the lowest body point above the ground), plant (per flipper: solve onto the ground or not)."""
        rig = Rig(self.model, self.sk)
        pose = copy.deepcopy(self.rest)
        pitch, yaw, roll = spec['body']
        rig.turn(pose, BODY, x=pitch, y=yaw, z=roll)
        rig.turn(pose, HEAD, x=spec['head'][0], y=spec['head'][1])
        rig.turn(pose, JAW, x=spec['jaw'])
        for bone, (a, b) in zip(TAIL, spec['tail']):
            rig.turn(pose, bone, x=a, y=b)
        for side, bone in enumerate(FLIPPERS):
            sweep, rollf = spec['flipper'][side]
            if spec['plant'][side] is None:
                rig.turn(pose, bone, y=sweep if side == 0 else -sweep, z=rollf if side == 0 else -rollf)
        # the ground
            # the lower jaw (and its chatter) is part of the ground contact except in the idle, whose jaw may sink a little
        pose[1][7] = self.rest[1][7] + self.drop
        for side, bone in enumerate(FLIPPERS):
            plant = spec['plant'][side]
            if plant is None:
                continue
            sweep, rollf = spec['flipper'][side]
            sign = 1 if side == 0 else -1
            up = plant  # degrees the flipper is lifted off the planted height

            def at(angle):
                trial = copy.deepcopy(pose)
                r = Rig(self.model, self.sk)
                r.angles = dict(rig.angles)
                r.turn(trial, bone, y=sign * sweep, z=sign * angle)
                return trial
            lo, hi = 0., 75.
            for _ in range(14):
                mid = (lo + hi) / 2
                if self.low(at(mid), (bone,)) < 0:
                    lo = mid
                else:
                    hi = mid
            angle = hi - up
            rig.turn(pose, bone, y=sign * sweep, z=sign * angle)
        return pose


def tail_wave(u, cycles, pitch, yaw, lag, droop=0., yaw_phase=.25):
    out = []
    for i in range(5):
        grow = 1 + .35 * i
        ph = cycles * u - lag * i
        out.append((droop / 5 + pitch * grow * swing(ph), yaw * grow * swing(ph - yaw_phase)))
    return out


def idle_spec(u):
    """Resting on the belly: only turns about the vertical axis, a slow roll and the jaw; nothing rises or sinks."""
    return dict(
        body=(0., 4 * swing(u, .1), 1.2 * swing(2 * u, .3)),
        # the head follows the body's turn backwards, so that it keeps facing the camera and both eyes stay visible
        head=(0., -3.5 * swing(u, .1) + 7 * swing(u) + 2 * swing(3 * u, .4)),
        jaw=-3 * max(0., swing(2 * u, .1)) ** 2,
        tail=tail_wave(u, 1, 0., 5., .1),
        flipper=[(8 * swing(2 * u, k * .5), 0.) for k in (0, 1)],
        plant=[0., 0.])


def walk_spec(u):
    return stroke_spec(u, dict(sweep=46., gap=6.), head=1.2, tail=(0., 5.5, .08, 1), jaw=-3., roll=1.6, sway=7.5)


def tired_spec(u):
    return stroke_spec(u, dict(sweep=30., gap=3.), head=.5, tail=(0., 2.5, .12, 1), jaw=-6., roll=1., sway=2.5,
                       panting=True)


def stroke_spec(u, c, head, tail, jaw, roll, sway, panting=False, counter=None, duty=.5, ease=0., asym=0., hlag=.15):
    """A flipper scoot on the ground: R pushes in the first half of the loop and L in the second (the planted
    flipper's sweep runs from forward to back, the recovering one skims just above the floor and swings forward).
    The body only turns about the vertical axis (a left-right wave) and rolls a little; it never rises or sinks."""
    flipper, plant = [], []
    for side in (0, 1):
        q = (u + .5 * side) % 1.
        th = c['sweep'] * (1 + asym * (1 - 2 * side))
        if q < duty:
            x = q / duty    # the push: even, or quickest in the middle of the stroke
            sweep, up = th * ((1 - ease) * (1 - 2 * x) + ease * math.cos(math.pi * x)), 0.
        else:
            r = (q - duty) / (1 - duty)
            sweep, up = -th + 2 * th * smooth(r), c['gap'] * math.sin(math.pi * r)
        flipper.append((sweep, 0.))
        plant.append(up)
    return dict(
        body=(0., sway * swing(u, .15), -roll * swing(u, .0)),
        head=(0., (-head * sway * swing(u, .25) if counter is None else -counter * sway * swing(u, hlag) + head * swing(u, .4))
               + (5 * swing(3 * u) if panting else 0.)),
        jaw=(jaw * (.5 + .5 * swing(2 * u, .2)) if panting else jaw * max(0., swing(u, .1)) ** 2),
        tail=tail_wave(u, tail[3], tail[0], tail[1], tail[2]),
        flipper=flipper, plant=plant)


def run_spec(u):
    """The walk's scoot, quicker and a little bigger: the same stroke, body wave, head and one tail beat per loop, with
    a shorter period and longer strokes so that the planted tips stay close to the ground at 40 units a tick."""
    return stroke_spec(u, dict(sweep=58., gap=6.), head=1.2, tail=(0., 6.2, .08, 1), jaw=-4., roll=2.2, sway=10.)


SPECS = {'idle': idle_spec, 'walk': walk_spec, 'tired': tired_spec, 'run': run_spec}


def author(source, base, skeleton):
    """`base`: the earlier overlay's output; `source`: the model it came from (its slot 0 supplies the rest pose)."""
    mmd.exe().add_type(SPECIES, skeleton)
    src = mmd.MMD.parse(source, NB)
    src.type = SPECIES
    old = mmd.MMD.parse(base, NB)
    old.type = SPECIES
    rest = [list(v) for v in animsheet.slot_frames(src, NB, 0)[0][0]]
    rest[0] = [4096] * 3 + [0] * 6
    dolphin = Dolphin(old, skeleton, rest)
    # one body height for every clip: the rest pose's lowest point on the ground
    dolphin.drop = round(-dolphin.low(rest, [b for b in dolphin.verts]))
    result = copy.deepcopy(old)
    checks = []
    for slot in SLOTS:
        name = CLIP_OF_SLOT[slot]
        c = CLIPS[name]
        n = c['n']
        frames, loop, events = animsheet.slot_frames(src, NB, slot)
        assert loop == 0 and len(frames) - 1 == SOURCE_PERIOD
        poses = []
        for t in range(n + 1):
            u = (t % n) / n
            pose = dolphin.pose(SPECS[name](u))
            pose[0] = [4096] * 3 + [0] * 6
            pose[0][8] = round(-c['speed'] * t)
            poses.append([[round(x) for x in v] for v in pose])
        mmd.close_loop(poses, 0)
        sounds = []
        for tick, kind, cue in events:
            t = round(tick * n / SOURCE_PERIOD)
            sounds.append((t, kind, dict(cue, frame=t + 1)))
        result.anims.table[slot] = len(result.anims.anims)
        result.anims.anims.append(mmd.encode_anim(poses, NB, 0, sounds, tol=1))
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
    base, _ = dolphmon.build(data, skeleton)
    output, extra = author(data, base, skeleton)
    return output, dict(field_gaits=extra, output_sha256=hashlib.sha256(output).hexdigest())
