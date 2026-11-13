"""Kurisarimon's field idle, walk, tired walk and run: a chrysalis that hovers on six dangling blade-footed legs (species 431).

The model: bone 1 is the body, an upright shell; the head with its horn and eye 33 crowns it, the abdomen 30-31-32 hangs
below it as a segmented tail. Six thin legs of four or five bones hang from the body's rear, three a side, and every one ends
in a long flat blade: the right ones 20-24, 15-19 and 25-29, the left ones 6-10, 2-5 and 11-14. The import played one 60-tick
pose sequence for the walk, the tired walk and the run, only moved over the floor at three speeds. It floats, so these clips
hover: the legs never step, they dangle and trail.

Offline only (player builds replay the pinned delta): `tools/models/edit.py get 431` on the commit before this change,
then `python3 -m tools.models.field_animations.kurisarimon_gait --source THAT.MMD --out AFTER.MMD` and
`edit.py put 431 AFTER.MMD`. Only slots 0, 1, 2, 3, 4, 18 and 33 change (the four clips, the idle's twins); the rest stay.

- Idle: a slow hover bob with the breath, the head glancing about, the legs hanging and swaying a beat behind the body and
  a blade twitching now and then, the abdomen drifting.
- Walk: a gentle glide, the body leaning a little and bobbing twice per loop, the legs trailing with a soft paddling
  (each bone a beat behind the one above it, each leg a little out of step with the next), the abdomen as a wave.
- Tired walk: a low sagging drift, the body hung close to the floor, a slow bob, the legs drooping straight down and heavy.
- Run: a fast glide with a strong forward lean, the legs and the abdomen streaming back, a quicker bob.
- Each bone's turn is a sum of a few sines at whole multiples of the loop, the second harmonic leaning them off a pure
  sine, with a lag growing along the chain so that the motion follows through. The body is lifted per clip (`clear`) so that
  no vertex of the model, a blade tip or the abdomen included, goes under the floor.
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

SPECIES, NB = 431, 34
SOURCE = "808fe7dcecb47e12d8400b3ab60c7aa3938827a30d17b2b90f295feb8b9753a4"   # edit.py get 431 before this change
SLOTS = (0, 1, 2, 3, 4, 18, 33)
TWINS_OF_IDLE = (1, 18, 33)
CLIP_OF_SLOT = {0: 'idle', 2: 'walk', 3: 'tired', 4: 'run'}
BODY, HEAD = 1, 33
TAIL = (30, 31, 32)
LEGS = {'RF': ((20, 21, 22, 23, 24), 1), 'LF': ((6, 7, 8, 9, 10), -1), 'RM': ((15, 16, 17, 18, 19), 1),
        'LM': ((2, 3, 4, 5), -1), 'RR': ((25, 26, 27, 28, 29), 1), 'LR': ((11, 12, 13, 14), -1)}
BASE_Y = -256
# each leg's own phase (in turns of the leg beat): the two sides in opposite phase, front to rear a third apart
LEG_PHASE = dict(RF=0., RM=.33, RR=.66, LF=.5, LM=.83, LR=.16)

# n ticks of the loop; speed units a tick; clear: height of the lowest vertex over the floor at its lowest tick;
# bob cycles per loop and amplitude; leg beat cycles per loop; leg swing (degrees at the hip, growing along the chain),
# trail (degrees every leg is held back, along the whole chain), lag (radians per bone down the chain)
CLIPS = {
    'idle': dict(n=72, speed=0, clear=14., kb=1, bob=3.2, kl=1, swing=3., side=2.5, trail=0., lag=.7, lean=0., nod=.8, sway=4.,
                 roll=1.2, yaw=2., head=5., tail=7., twitch=True),
    'walk': dict(n=32, speed=18, clear=20., kb=2, bob=4., kl=1, swing=7., side=3.5, trail=2., lag=.8, lean=3., nod=1.2, sway=5.,
                 roll=1.8, yaw=3., head=5., tail=8., twitch=False),
    'tired': dict(n=48, speed=12, clear=6., kb=1, bob=2.6, kl=1, swing=4.5, side=3., trail=-8., lag=.9, lean=9., nod=2.2, sway=4.,
                  roll=3., yaw=2.4, head=3., tail=6., twitch=False),
    'run': dict(n=20, speed=38, clear=24., kb=2, bob=5., kl=2, swing=7., side=4., trail=5., lag=.9, lean=7., nod=1.8, sway=4.,
                roll=2., yaw=3.4, head=7., tail=11., twitch=False),
}
# lean/trail signs (turns about the world x axis): positive leans the top forward, positive trail sweeps the legs back
LEAN_SIGN, TRAIL_SIGN = 1., 1.


def wv(x, lag=0., second=.3, shift=.9):
    """One beat that is not a pure sine: a second harmonic leans it."""
    return math.sin(x - lag) + second * math.sin(2 * (x - lag) + shift)


class Hover:
    """The model and its mesh, for height and penetration checks."""

    def __init__(self, model, skeleton, rest=None):
        self.model, self.skeleton = model, skeleton
        self.body = ol.Body(model, skeleton)

    def lowest(self, pose, bones=None):
        bones = list(range(1, NB)) if bones is None else bones
        return float(self.body.points(self.body.world(pose)[1], bones)[:, 1].max())


Spider = Hover       # the name the tests of the other gaits use


class Clip:
    def __init__(self, hover, name, base):
        self.o, self.name, self.c, self.base = hover, name, CLIPS[name], base
        self.n = self.c['n']
        self.h = 0.

    def pose(self, t, rig):
        c, n = self.c, self.n
        th = 2 * math.pi * t / n
        pose = copy.deepcopy(self.base)
        rig.angles = {}
        kb, kl = c['kb'], c['kl']
        bob = c['bob'] * wv(kb * th, .6, .22, .7)
        pose[BODY][6] += round(c['sway'] * wv(th, .8, .3, .5))
        pose[BODY][7] = BASE_Y - round(self.h + bob)
        nod = c['nod'] * wv(kb * th, 1.4, .25, 1.1)
        yaw = c['yaw'] * wv(th, 2.4, .35, .9)
        roll = c['roll'] * wv(th, 1.8, .2, .3)
        rig.turn(pose, BODY, x=LEAN_SIGN * (c['lean'] + nod), y=yaw, z=roll)
        rig.turn(pose, HEAD, x=-.45 * LEAN_SIGN * (c['lean'] * .6 + nod) + .5 * c['head'] * wv(kb * th, 1.1, .25, .6),
                 y=-.5 * yaw + .7 * c['head'] * wv(th, 1.8, .3, 1.0), z=-.5 * roll)
        for i, bone in enumerate(TAIL):
            lag = .8 * (i + 1)
            amp = c['tail'] * (.6 + .3 * i)
            rig.turn(pose, bone, x=.5 * amp * wv(kb * th, 1. + lag, .25, .6) - .3 * LEAN_SIGN * c['lean'] * (1 if i == 0 else 0),
                     y=-.5 * yaw * (1 if i == 0 else 0) + amp * wv(th, 1.6 + lag, .3, .8))
        for leg, (chain, side) in LEGS.items():
            ph = 2 * math.pi * LEG_PHASE[leg]
            for i, bone in enumerate(chain):
                grow = (i + 1) / len(chain)
                lag = c['lag'] * i + ph
                tw = 0.
                if c['twitch'] and leg in ('RF', 'LM') and i >= len(chain) - 2:
                    u = (t / n - (.15 if leg == 'RF' else .62)) / .24
                    if 0. <= u <= 1.:
                        tw = 3.5 * math.sin(math.pi * u) ** 2 * math.sin(2 * math.pi * u)
                share = 1. if i < 2 else .5
                rig.turn(pose, bone,
                         x=TRAIL_SIGN * c['trail'] * share / 2 + c['swing'] * grow * wv(kl * th, lag, .3, .8) + tw,
                         z=side * (c['side'] * grow * wv(kl * th, lag + 1.3, .25, .5) ))
        return pose

    def lowest(self, pose):
        return self.o.lowest(pose)

    def fit_height(self, rig):
        """Lift the body so that its lowest vertex over the whole loop is `clear` above the floor."""
        self.h = 0.
        worst = max(self.lowest(self.pose(t, rig)) for t in range(self.n))
        self.h = worst + self.c['clear']


def author(data, skeleton):
    if SOURCE and hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError("Kurisarimon's hover clips are written over the reviewed model")
    mmd.exe().add_type(SPECIES, skeleton)
    old = mmd.MMD.parse(data, NB)
    old.type = SPECIES
    base = [[round(x) for x in v] for v in animsheet.slot_frames(old, NB, 0)[0][0]]
    o = Hover(old, skeleton)
    result = copy.deepcopy(old)
    streams, checks = {}, []
    for slot in (0, 2, 3, 4):
        name = CLIP_OF_SLOT[slot]
        frames, loop, events = animsheet.slot_frames(old, NB, slot)
        assert loop == 0, (slot, loop)
        events = [e for e in events if e[1] == 'tex' and e[0] == 0]
        clip = Clip(o, name, base)
        rig = Rig(old, skeleton)
        out = []
        clip.fit_height(rig)
        for t in range(clip.n):
            pose = clip.pose(t, rig)
            pose[0] = [4096] * 3 + [0, 0, 0, 0, 0, -round(clip.c['speed'] * t)]
            out.append([[round(x) for x in v] for v in pose])
        out.append(copy.deepcopy(out[0]))
        out[-1][0] = [4096] * 3 + [0, 0, 0, 0, 0, -clip.c['speed'] * clip.n]
        mmd.close_loop(out, 0)
        streams[slot] = len(result.anims.anims)
        result.anims.anims.append(mmd.encode_anim(out, NB, 0, list(events), tol=1))
    for slot in TWINS_OF_IDLE:
        result.anims.table[slot] = streams[0]
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
    skeleton = json.loads((ROOT / 'content/species/431-kurisarimon.json').read_text())['model']['skeleton']
    data, report = build(args.source.read_bytes(), skeleton)
    args.out.write_bytes(data)
    print(args.out, len(data), 'B', report['storage'], report['checks'])


if __name__ == '__main__':
    main()
