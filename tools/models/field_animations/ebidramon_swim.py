"""Ebidramon's field idle, walk, tired walk and run: a shrimp dragon that swims through the air (species 305).

The import's idle, walk, tired walk and run (60 ticks each) were one tail-curl cycle with only the root faster, and the
battle idle (slot 33) was that cycle sunk 40 units into the floor. Offline only (player builds replay the pinned
delta): `tools/models/edit.py get 305` on the commit before this change, then
`python3 -m tools.models.field_animations.ebidramon_swim --source THAT.MMD --out AFTER.MMD` and `edit.py put 305 AFTER.MMD`.

The model: bone 1 is the first body segment, the root of everything. The abdomen curls down and back from it (2, 3 and 4,
the tail fan), the chest (5) carries the head (13, with the jaw 14 and two long antennae 15-16 and 17-18) and two arms:
the right one (6-7-8) ends in a single claw, the left one (9-10, then two pincers 11 and 12). Six small swimmerets
(right 19-24, left 25-30) hang under the body. Nothing of it can reach the floor but the tail fan, so it does not walk:
like Piedmon it hovers (the same convention: the fan skims the floor at its lowest and never goes through it) and
every clip is a way of swimming in the air. Its parts hang and trail, each a little after the one before:

- A stroke: the abdomen flexes, the fan flicks last, the body rises on it, the arms and antennae stream back
  with the speed. The swimmerets row in a wave from front to back.
- Idle (96 ticks): the body floats and breathes once, shifts and glances; the tail sways, the fan fans out; the claws
  pendulum and the right claw closes once, the pincers open and close once; the antennae lag the head.
- Walk (48 ticks, one stroke, 22 units a tick): a steady cruise, the body bobbing once a stroke, rolling over a stroke,
  the arms swinging as delayed pendulums, the antennae streaming.
- Tired walk (64 ticks, one slow stroke, 14 units a tick): low, nose down, the abdomen and the fan dragging, the arms
  hanging, the swimmerets slow, a sigh once a stroke.
- Run (32 ticks, one stroke, 40 units a tick): pitched forward, a high bounce, big abdomen flicks, the arms
  and antennae swept back, the swimmerets blurring.

Every clip repeats its pose cycle exactly, the root travels the same distance every tick, and slots 1 and 18 follow the
idle and slot 36 the run. This generator once made the battle idle (33) a twin of the idle too; the source game's own
battle idle is back in that slot (tools/models/battle_restore.py), and the generator no longer writes it.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet  # noqa: E402
import mmd  # noqa: E402
import motioncyclelayer  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models.field_animations import okuwamon_limbs as ol  # noqa: E402
from tools.models.field_animations.lillymon_flight import Rig  # noqa: E402

SPECIES, NB = 305, 31
SOURCE = "370979059d38866118424d3c887295789afb6d141cfbc1beb6ef204c74655898"   # sha256 of the import this was written over
SLOTS = (0, 1, 2, 3, 4, 18, 36)
TWINS_OF_IDLE = (1, 18)                 # the battle idle (33) is the source game's own again (battle_restore.py)
TWINS_OF_RUN = (36,)
CLIP_OF_SLOT = {0: 'idle', 2: 'walk', 3: 'tired', 4: 'run'}
BODY, CHEST, HEAD, JAW = 1, 5, 13, 14
TAIL = (2, 3, 4)
ARM_R, ARM_L = (6, 7, 8), (9, 10, 11, 12)
ANT_R, ANT_L = (17, 18), (15, 16)
LEGS_R = ((19, 20), (21, 22), (23, 24))
LEGS_L = ((25, 26), (27, 28), (29, 30))
GROUPS = {'tail': TAIL, 'armR': ARM_R, 'armL': ARM_L, 'head': (HEAD, JAW), 'antR': ANT_R, 'antL': ANT_L,
          'legR': tuple(b for c in LEGS_R for b in c), 'legL': tuple(b for c in LEGS_L for b in c)}
CORE = (BODY, CHEST)
TAU = 2 * math.pi
TOL = 8
BASE_Y = -371           # the body bone's height in the import's rest pose

#   n: ticks of the loop; beats: strokes in it; speed: units a tick; clear: the lowest point's height above the floor at
#   its lowest in the loop (units); bob/sway/roll/yaw: body terms (units, degrees); lean: mean pitch (nose down positive),
#   pitch: its swing; tail/fan: abdomen and fan flex (degrees); arm: carry (swept back positive), arm_swing; ant: antennae
#   sweep back, ant_swing; row: swimmeret stroke; row_n: its beats in the loop; head: mean nod, nod: its swing
CLIPS = {
    'idle': dict(n=96, beats=1, speed=0, clear=16., bob=6., sway=3.5, roll=1., yaw=2.2, lean=0., pitch=1.2,
                 tail=4., fan=4., arm=0., arm_swing=3.5, ant=0., ant_swing=4., row=4., row_n=3, head=0., nod=2.),
    'walk': dict(n=48, beats=1, speed=22, clear=22., bob=11., sway=4.5, roll=1.5, yaw=1.4, lean=6., pitch=1.6,
                 tail=8., fan=6., arm=4., arm_swing=7., ant=12., ant_swing=5., row=5., row_n=3, head=-4., nod=2.5),
    'tired': dict(n=64, beats=1, speed=14, clear=8., bob=5., sway=4., roll=2., yaw=1.5, lean=10., pitch=1.4,
                  tail=5., fan=3.5, arm=3., arm_swing=3.5, ant=2., ant_swing=3., row=4., row_n=2, head=12., nod=3.),
    'run': dict(n=32, beats=1, speed=40, clear=34., bob=16., sway=3.5, roll=1.4, yaw=1.2, lean=18., pitch=2.2,
                tail=10., fan=8., arm=8., arm_swing=8., ant=26., ant_swing=5., row=5., row_n=4, head=-10., nod=5.),
}


def wv(x, lag=0., second=.28, shift=.8):
    """One beat that is not a pure sine: a second harmonic leans it."""
    return math.sin(x - lag) + second * math.sin(2 * (x - lag) + shift)


def bump(u):
    return math.sin(math.pi * min(1., max(0., u))) ** 2


class Swimmer:
    def __init__(self, model, skeleton):
        self.model, self.skeleton = model, skeleton
        self.body = ol.Body(model, skeleton)


class Clip:
    def __init__(self, name, rest):
        self.name, self.c, self.rest = name, CLIPS[name], rest
        self.n = self.c['n']
        self.lift = 0.            # hover height gained over the rest pose, set from the lowest point

    def terms(self, t):
        c, n = self.c, self.n
        th = TAU * t / n                      # once a loop
        ph = th * c['beats']                  # once a stroke
        if self.name == 'idle':
            bob = c['bob'] * wv(ph, 0., .22, .7)
            sway = c['sway'] * wv(th, .8, .3, .5)
            roll = c['roll'] * wv(th, 1.8, .2, .3)
            nod = c['pitch'] * wv(ph, 1.0, .25, 1.1)
            yaw = c['yaw'] * wv(th, 2.6, .35, .9) + .8 * math.sin(3 * th + 1.)
        else:
            bob = c['bob'] * (math.sin(ph) + .22 * math.sin(2 * ph + .8)) / 1.2
            sway = c['sway'] * (math.sin(th + .4) + .2 * math.sin(2 * th - .5))
            roll = c['roll'] * (math.sin(ph + 1.0) + .15 * math.sin(3 * ph))
            nod = c['pitch'] * (math.sin(ph - .9) + .2 * math.sin(2 * ph))
            yaw = c['yaw'] * (math.sin(th + 1.6) + .2 * math.sin(3 * th + .3))
        return dict(th=th, ph=ph, bob=bob, sway=sway, roll=roll, nod=nod, yaw=yaw)

    def pose(self, t, rig):
        c = self.c
        pose = copy.deepcopy(self.rest)
        rig.angles = {}
        k = self.terms(t)
        th, ph = k['th'], k['ph']
        moving = self.name != 'idle'
        pose[BODY][6] += round(k['sway'])
        pose[BODY][7] = BASE_Y - round(self.lift + k['bob'])
        rig.turn(pose, BODY, x=c['lean'] + k['nod'], y=k['yaw'], z=k['roll'])
        # the chest and the head follow the body a little late, the head holds level against the pitch
        rig.turn(pose, CHEST, x=-.35 * (c['lean'] + k['nod']) + .8 * c['pitch'] * wv(ph, 1.6, .2, .4))
        head = c['head'] + c['nod'] * wv(ph, 2.4, .3, .6) - .3 * k['nod']
        rig.turn(pose, HEAD, x=head, y=1.6 * c['yaw'] * wv(th, 3.4, .3, .5))
        jaw = (3. + 2.5 * wv(ph, 2.2, .3, .5)) if self.name != 'tired' else (5. + 3. * wv(ph, 2.0, .2, .4))
        if self.name == 'idle':
            jaw += 4. * bump((th / TAU - .30) / .12) + 5. * bump((th / TAU - .72) / .1)
        rig.turn(pose, JAW, x=jaw)
        self.tail(pose, rig, k)
        self.arms(pose, rig, k)
        self.antennae(pose, rig, k)
        self.legs(pose, rig, k)
        return pose

    def tail(self, pose, rig, k):
        """The abdomen flexes as a wave that runs down it, the fan last and widest."""
        c, ph = self.c, k['ph']
        flick = 1.0
        rig.turn(pose, 2, x=c['tail'] * .75 * wv(ph, .9, .3, .6), y=.5 * c['tail'] * wv(k['th'], 1.6, .3, .5))
        rig.turn(pose, 3, x=c['tail'] * 1.0 * wv(ph, 1.8, .3, .8), y=.8 * c['tail'] * wv(k['th'], 2.3, .3, .5))
        rig.turn(pose, 4, x=c['fan'] * flick * wv(ph, 2.7, .3, 1.0), z=.7 * c['fan'] * wv(2 * ph, 3.0, .3, .4))

    def arms(self, pose, rig, k):
        c, ph, th = self.c, k['ph'], k['th']
        idle = self.name == 'idle'
        for chain, side, ph0 in ((ARM_R, 1, 0.), (ARM_L, -1, 1.9)):
            sh, up = chain[0], chain[1]
            sw = c['arm_swing']
            beat = th if idle else ph
            rig.turn(pose, sh, x=c['arm'] * .5 + .6 * sw * wv(beat, ph0 + .3, .25, .8), z=side * (2. + .25 * c['arm']))
            rig.turn(pose, up, x=c['arm'] * .6 + sw * wv(beat, ph0 + .9, .3, 1.0), z=side * .6 * sw * wv(beat, ph0 + 1.5, .3, .5))
            if chain is ARM_R:
                rig.turn(pose, 8, x=.9 * sw * wv(beat, ph0 + 1.6, .3, 1.2), y=-side * (3. + 2.5 * wv(beat, ph0 + 2.4, .3, .5)))
                if idle:
                    rig.turn(pose, 8, y=-9. * bump((th / TAU - .52) / .15) - 7. * bump((th / TAU - .58) / .1))
            else:
                grip = 2.5 + 2. * wv(beat, ph0 + 1.4, .3, .6)
                if idle:
                    grip += 8. * bump((th / TAU - .18) / .2)
                rig.turn(pose, 11, y=grip + .5 * sw * wv(beat, ph0 + 1.6, .3, 1.2))
                rig.turn(pose, 12, y=-grip + .5 * sw * wv(beat, ph0 + 1.9, .3, 1.2))

    def antennae(self, pose, rig, k):
        c, ph, th = self.c, k['ph'], k['th']
        beat = th if self.name == 'idle' else ph
        for chain, side, ph0 in ((ANT_R, 1, 0.), (ANT_L, -1, .7)):
            a, b = chain
            sw = c['ant_swing']
            rig.turn(pose, a, x=c['ant'] * .4 + .5 * sw * wv(beat, ph0 + 1.0, .3, .7), z=side * .6 * sw * wv(beat, ph0 + 1.8, .3, 1.0))
            rig.turn(pose, b, x=c['ant'] * .8 + sw * wv(beat, ph0 + 2.0, .3, 1.1), z=side * 1.1 * sw * wv(beat, ph0 + 2.9, .3, 1.4))

    def legs(self, pose, rig, k):
        """The swimmerets row front to back in a wave, the lower part of each stroke a little after the upper."""
        c, th = self.c, k['th']
        beat = th * c['row_n']
        for legs, side in ((LEGS_R, 1), (LEGS_L, -1)):
            for i, (hip, shin) in enumerate(legs):
                lag = .55 * i + (0. if side > 0 else .15)
                rig.turn(pose, hip, x=c['row'] * wv(beat, lag, .25, .8), z=side * (1.5 + .25 * c['row'] * wv(beat, lag + 1.0, .25, .4)))
                rig.turn(pose, shin, x=.7 * c['row'] * wv(beat, lag + .9, .3, 1.1))


def lowest(swimmer, pose):
    mats, world = swimmer.body.world(pose)
    return float(world[:, 1].max())


def author(data, skeleton):
    if SOURCE and hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError("Ebidramon's swimming clips are written over the reviewed import")
    mmd.exe().add_type(SPECIES, skeleton)
    old = mmd.MMD.parse(data, NB)
    old.type = SPECIES
    s = Swimmer(old, skeleton)
    rest = [[round(x) for x in v] for v in animsheet.slot_frames(old, NB, 0)[0][0]]
    result = copy.deepcopy(old)
    streams, checks = {}, []
    for slot in (0, 2, 3, 4):
        name = CLIP_OF_SLOT[slot]
        frames, loop, events = animsheet.slot_frames(old, NB, slot)
        assert loop == 0, (slot, loop)
        events = [e for e in events if e[1] == 'tex' and e[0] == 0]
        clip = Clip(name, rest)
        rig = Rig(old, skeleton)
        # the hover height: raise the body until the lowest point of the loop clears the floor by `clear`
        for _ in range(3):
            low = max(lowest(s, clip.pose(t, rig)) for t in range(clip.n))
            clip.lift += low + clip.c['clear']
        out = []
        for t in range(clip.n):
            pose = clip.pose(t, rig)
            pose[0] = [4096] * 3 + [0, 0, 0, 0, 0, -round(clip.c['speed'] * t)]
            out.append([[round(x) for x in v] for v in pose])
        out.append(copy.deepcopy(out[0]))
        out[-1][0] = [4096] * 3 + [0, 0, 0, 0, 0, -clip.c['speed'] * clip.n]
        mmd.close_loop(out, 0)
        streams[slot] = len(result.anims.anims)
        result.anims.anims.append(mmd.encode_anim(out, NB, 0, list(events), tol={BODY: 1, None: TOL}))
    for slot in TWINS_OF_IDLE:
        result.anims.table[slot] = streams[0]
    for slot in TWINS_OF_RUN:
        result.anims.table[slot] = streams[4]
    for slot in (0, 2, 3, 4):
        result.anims.table[slot] = streams[slot]
    for anim in result.anims.anims:
        anim.tail = b''
    used = sorted({i for i in result.anims.table if i is not None})
    renumber = {i: k for k, i in enumerate(used)}
    result.anims.anims = [result.anims.anims[i] for i in used]
    result.anims.table = [None if i is None else renumber[i] for i in result.anims.table]
    result.anims.anims, result.anims.table = motioncyclelayer.share_identical_streams(result.anims.anims, result.anims.table)
    output = result.build()
    effective = mmd.MMD.parse(output, NB)
    effective.type = SPECIES
    assert effective.tmd.build() == old.tmd.build()
    changed = changed_programs(old, effective)
    assert set(changed) == set(SLOTS), changed
    for slot in SLOTS:
        samples, loop, _ = animsheet.slot_frames(effective, NB, slot)
        assert loop == 0
        checks.append(dict(slot=slot, ticks=len(samples) - 1,
                           root_per_tick=round((samples[-1][0][8] - samples[0][0][8]) / (len(samples) - 1), 2)))
    return output, dict(checks=checks, storage=motionstorage.require(output, NB), species=SPECIES, changed_slots=changed)


def build(data, skeleton):
    output, report = author(data, skeleton)
    return output, dict(report, output_sha256=hashlib.sha256(output).hexdigest())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    skeleton = json.loads((ROOT / 'content/species/305-ebidramon.json').read_text())['model']['skeleton']
    data, report = build(args.source.read_bytes(), skeleton)
    args.out.write_bytes(data)
    print(args.out, len(data), 'B', report['storage'], report['checks'])


if __name__ == '__main__':
    main()
