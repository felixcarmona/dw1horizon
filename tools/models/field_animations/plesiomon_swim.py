"""Plesiomon's field idle, walk, condition walk and run as four different swimming movements.

The import's four field clips (40 ticks each, slots 0, 2, 3 and 4) were one and the same pose cycle: the body, the long neck,
the head, the four flippers and the tail all repeated the same poses and only the root's speed differed (0, 22, 15.5 and
39 units a tick). This module writes slots 0, 1 and 18 (they share the idle), 2, 3 and 4 again (every other slot, the mesh
and the rig stay):

- the neck (bones 14 to 18) and the head (19) carry a travelling wave: the yaw of every segment is a sine that the body
  starts and every bone further up follows a fixed phase later, growing toward the head, with a weaker second harmonic and a
  vertical wave a quarter behind; the head turns and nods against the neck's wave and a spring lets it trail; the jaw (20)
  breathes. The tail (10 to 13) carries a wave of its own growing to the tip, which hangs on a spring so that it lashes;
- the four flippers (front 6 + 7 and 8 + 9, hind 2 + 3 and 4 + 5) row through springs, the outer joint trailing the inner
  one: a figure of eight in the idle, a rowing stroke (back and down, then forward and up) in the walks, left and right
  half a stroke apart, and a wide stroke in the run with both sides together;
- idle (72 ticks): treading water, the body breathing and the neck swaying slowly; walk (40 ticks, 22 units a tick): a steady
  swim; condition walk (60 ticks, 15): the body low, the neck sagging, the tail dragging, short weak strokes; run (24 ticks,
  39): the body tilted forward, the neck stretched out low and straight, wide quick strokes and a tail that whips.

Every clip repeats its pose cycle exactly (the last tick equals the first), the root travels the same distance every tick
and the eye blink keeps its place in the loop.
"""
import copy
import hashlib
import math

import animsheet
import mmd
import motioncyclelayer
import motionstorage
from motiondiscidentity import changed_programs
from tools.models.field_animations.lillymon_flight import Rig
from tools.models.field_animations.quetzalmon_flight import follow

SPECIES = 271
NB = 21
SOURCE = 'dab75d0b531f76e1c212a8411a013c98e3f3f924ae27bcfbec54526a44f9b33b'   # edit.py get 271 before this change
SLOTS = (0, 1, 2, 3, 4, 18)
WRITTEN = (0, 2, 3, 4)
CLIP_OF_SLOT = {0: 'idle', 1: 'idle', 18: 'idle', 2: 'walk', 3: 'tired', 4: 'run'}
BODY, JAW, HEAD = 1, 20, 19
NECK = (14, 15, 16, 17, 18, 19)
TAIL = (10, 11, 12, 13)
FRONT = ((6, 7, 1), (8, 9, -1))          # (inner joint, outer joint, side: +1 right)
HIND = ((2, 3, 1), (4, 5, -1))

#   n: ticks of the loop; speed: root units a tick (0: in place); kn, kt: waves of the neck and of the tail in a loop;
#   neck: yaw at the head (degrees), the share of it at the base, the wave's lag from base to head (radians), the second
#   harmonic's share, the vertical wave, the counter-turn of the head and its look about (degrees); drop: the neck's static
#   pitch bone by bone (nose down positive); tail: yaw at the tip, lag, vertical wave, the sag of the tip; body: pitch,
#   roll, yaw, sway (units), bob (first and second harmonic, units); fin: the stroke back and forth, the lift, the sweep back
#   and the droop (degrees), the share of the hind pair, the left side's lag in strokes, the hind pair's lag in strokes, the
#   figure-eight flag; jaw (rest, swing); clear: height of the lowest point of the mesh above the floor.
CLIPS = {
    'idle': dict(n=72, speed=0, kn=1, kt=1, neck=(13., .20, 2.6, .18, 3., .45, 4.), drop=(0, 0, 0, 0, 0, 5),
                 tail=(12., 2.4, 5., 0.), body=(0., 1.6, 1.8, 3., 6., 2.), fin=(11., 9., 0., 0., .85, .5, .12, 1),
                 jaw=(2., 3.), clear=46),
    'walk': dict(n=40, speed=22, kn=1, kt=1, neck=(24., .15, 3.3, .14, 4., .5, 0.), drop=(1, 4, 7, 7, 5, 8),
                 tail=(30., 3.6, 9., 0.), body=(1.5, 3.5, 2.5, 8., 4., 3.), fin=(26., 14., 2., 0., .85, .5, .12, 0),
                 jaw=(2., 2.), clear=60),
    'tired': dict(n=60, speed=15, kn=1, kt=1, neck=(14., .30, 2.4, .08, 3., .35, 0.), drop=(1, 8, 16, 23, 28, 34),
                  tail=(16., 2.2, 6., -16.), body=(2., 2., 1.5, 5., 9., 2.), fin=(9., 5., 4., 0., .7, .5, .12, 0),
                  jaw=(10., 3.), clear=24),
    'run': dict(n=24, speed=39, kn=2, kt=2, neck=(5., .30, 1.9, .10, 2., .5, 0.), drop=(2, 14, 26, 34, 38, 44),
                tail=(34., 3.8, 15., 0.), body=(9., 3., 2., 8., 2.5, 3.), fin=(40., 22., 12., 0., .85, 0., .12, 0),
                jaw=(0., 1.5), clear=84),
}
DEG = 4096 / 360


def prof(s, base, power=1.6):
    """Share of a wave's amplitude at the depth s (0 .. 1) along a chain: `base` at the start, all of it at the end."""
    return base + (1 - base) * s ** power


def shape(u):
    """A stroke's phase, quick through the power half and slow through the recovery."""
    return u + .35 * math.sin(u)


class Swim:
    def __init__(self, c):
        self.c, self.n = c, c['n']
        n = self.n
        th = lambda t: 2 * math.pi * t / n  # noqa: E731
        self.th = th
        stroke, lift, sweep, droop, hind, lagl, lagh, eight = c['fin']
        w = 2 * math.pi * 2 / n                    # the fins beat twice a loop
        self.w = w
        self.fins = {}
        for key, (inner, outer, side) in enumerate(FRONT + HIND):
            off = (lagl if side < 0 else 0.) + (lagh if inner in (2, 4) else 0.)
            amp = stroke * (hind if inner in (2, 4) else 1.)
            fl = lift * (hind if inner in (2, 4) else 1.)

            def drive(t, off=off, amp=amp, fl=fl):
                u = 2 * math.pi * (2 * t / n - off)
                swing = -amp * math.cos(shape(u))
                up = fl * (1. + (math.sin(2 * u) if eight else -math.sin(u)))   # outward of the rest pose, never into the body
                return swing, up
            swing = follow(lambda t: drive(t)[0], n, w * 2.2, .55)
            up = follow(lambda t: drive(t)[1], n, w * 2.2, .55)
            up2 = follow(lambda t: self.sample(up, t), n, w * 2.0, .5)
            for lst in (swing, up, up2):
                lst[-1] = lst[0]
            self.fins[inner] = (swing, up, up2)
        self.gaze = follow(lambda t: math.sin(th(t) * c['kn'] - c['neck'][2] * .7), n, 2 * math.pi * c['kn'] / (n * .25), .6)
        self.gaze[-1] = self.gaze[0]
        # the head and the tail tip hang on springs behind the waves that drive them
        self.head_yaw = follow(lambda t: self.neck_yaw(5, t, raw=True), n, 2 * math.pi * c['kn'] * 3. / n, .5)
        self.head_pitch = follow(lambda t: self.neck_wave(5, t), n, 2 * math.pi * c['kn'] * 3. / n, .5)
        self.tip_yaw = follow(lambda t: self.tail_yaw(3, t, raw=True), n, 2 * math.pi * c['kt'] * 3. / n, .5)
        self.tip_pitch = follow(lambda t: self.tail_pitch(3, t, raw=True), n, 2 * math.pi * c['kt'] * 3. / n, .5)
        for lst in (self.head_yaw, self.head_pitch, self.tip_yaw, self.tip_pitch):
            lst[-1] = lst[0]

    @staticmethod
    def sample(lst, t):
        n = len(lst) - 1
        i = int(math.floor(t)) % n
        f = t - math.floor(t)
        return lst[i] * (1 - f) + lst[(i + 1) % n] * f

    def neck_yaw(self, i, t, raw=False):
        c = self.c
        amp, base, lag, h2, vert, counter, look = c['neck']
        s, ph = i / 5., self.th(t) * c['kn']
        if i == 5 and not raw:
            return self.sample(self.head_yaw, t) * .85 + look * self.sample(self.gaze, t)
        return amp * prof(s, 0.) * (math.sin(ph - lag * s) + h2 * math.sin(2 * ph - 2 * lag * s - .9))

    def neck_wave(self, i, t):
        c = self.c
        amp, base, lag, h2, vert, counter, look = c['neck']
        s, ph = i / 5., self.th(t) * c['kn']
        return vert * prof(s, 0.) * math.sin(ph - lag * s - math.pi / 2)

    def neck_pitch(self, i, t, raw=False):
        c = self.c
        if i == 5 and not raw:
            # the head nods against the neck's vertical wave, a spring behind it
            return c['drop'][5] - c['neck'][5] * self.sample(self.head_pitch, t)
        return self.neck_wave(i, t) + c['drop'][i]

    def tail_yaw(self, j, t, raw=False):
        c = self.c
        tip, lag, vert, sag = c['tail']
        s, ph = (j + 1) / 4., self.th(t) * c['kt']
        if j == 3 and not raw:
            return self.sample(self.tip_yaw, t)
        return tip * prof(s, .12, 1.5) * (math.sin(ph - lag * s - .5) + .14 * math.sin(2 * ph - 2 * lag * s - 1.3))

    def tail_pitch(self, j, t, raw=False):
        c = self.c
        tip, lag, vert, sag = c['tail']
        s, ph = (j + 1) / 4., self.th(t) * c['kt']
        if j == 3 and not raw:
            return self.sample(self.tip_pitch, t)
        return vert * prof(s, .2, 1.5) * math.sin(ph - lag * s - .5 - math.pi / 2) + sag * s ** 2


def pose_at(rig, rest, sw, c, t, n, rootz):
    th = 2 * math.pi * t / n
    pose = copy.deepcopy(rest)
    pose[0] = [4096] * 3 + [0, 0, 0, 0, 0, rootz]
    pitch, roll, yaw, sway, bob1, bob2 = c['body']
    lag = c['neck'][2]
    pose[BODY][6] = rest[BODY][6] - round(sway * math.sin(th - lag * .4))
    pose[BODY][7] = rest[BODY][7] - round(bob1 * math.sin(th - 1.1) + bob2 * math.sin(2 * th - .4))
    rig.turn(pose, BODY, x=pitch + .8 * math.sin(2 * th - .9) * min(1., c['fin'][0] / 20.),
             y=yaw * math.sin(th - lag * .4 + 1.4), z=roll * math.sin(th - lag * .4 + .8))
    for chain, yaw_of, pitch_of in ((NECK, sw.neck_yaw, sw.neck_pitch), (TAIL, sw.tail_yaw, sw.tail_pitch)):
        py = pp = 0.
        for i, b in enumerate(chain):
            y, p = yaw_of(i, t), pitch_of(i, t)
            rig.turn(pose, b, x=p - pp, y=y - py)
            py, pp = y, p
    # the jaw
    rig.turn(pose, JAW, x=c['jaw'][0] + c['jaw'][1] * math.sin(th - .5 * c['neck'][2] - .6))
    # the fins: stroke (fore and aft), lift and droop; the outer joint chases the inner one through a spring
    stroke, lift, sweep, droop = c['fin'][:4]
    for inner, outer, side in FRONT + HIND:
        swing, up, up2 = sw.fins[inner]
        a, u1, u2 = sw.sample(swing, t), sw.sample(up, t), sw.sample(up2, t)
        rig.turn(pose, inner, x=sweep + a, z=side * (droop - u1))
        rig.turn(pose, outer, x=.4 * a, z=side * -.8 * (u2 - u1))
    return pose


def lowest(old, skeleton, pose):
    return max(v[1] for tri in animsheet.world_tris(old, [[4096, 4096, 4096, 0, 0, 0, 0, 0, 0]] + pose[1:], skeleton)
               for v in tri[0])


def blink(events, n):
    """The original's eye blink (a tick of the 40 it lasted, then 1, 3 and 4 ticks later) at the same share of the loop."""
    start = round(n * 19 / 40)
    shifts = {19: 0, 20: 1, 22: 3, 23: 4}
    out = []
    for tick, op, d in events:
        t = 0 if tick == 0 else start + shifts[tick]
        out.append((t, op, dict(d, frame=t + 1)))
    return out


def author(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError("Plesiomon's swimming clips are written over the reviewed import")
    mmd.exe().add_type(SPECIES, skeleton)
    old = mmd.MMD.parse(data, NB)
    old.type = SPECIES
    rest = [[round(x) for x in v] for v in animsheet.slot_frames(old, NB, 0)[0][0]]
    result = copy.deepcopy(old)
    new_streams = {}
    checks = []
    for slot in WRITTEN:
        c = CLIPS[CLIP_OF_SLOT[slot]]
        n = c['n']
        frames, loop, events = animsheet.slot_frames(old, NB, slot)
        sw = Swim(c)
        rig = Rig(old, skeleton)
        out = []
        for t in range(n + 1):
            out.append(pose_at(rig, rest, sw, c, t, n, -round(c['speed'] * t)))
        out = [[[round(x) for x in v] for v in p] for p in out]
        low = max(lowest(old, skeleton, p) for p in out)
        for p in out:
            p[BODY][7] += round(-c['clear'] - low)
        mmd.close_loop(out, 0)
        new_streams[slot] = len(result.anims.anims)
        result.anims.anims.append(mmd.encode_anim(out, NB, 0, blink(events, n), tol=1))
    for slot in (1, 18):
        new_streams[slot] = new_streams[0]
    for slot, i in new_streams.items():
        result.anims.table[slot] = i
    for anim in result.anims.anims:
        anim.tail = b''
    used = sorted({i for i in result.anims.table if i is not None})
    renumber = {o: k for k, o in enumerate(used)}
    result.anims.anims = [result.anims.anims[i] for i in used]
    result.anims.table = [None if i is None else renumber[i] for i in result.anims.table]
    result.anims.anims, result.anims.table = motioncyclelayer.share_identical_streams(result.anims.anims, result.anims.table)
    output = result.build()
    effective = mmd.MMD.parse(output, NB)
    effective.type = SPECIES
    assert effective.tmd.build() == old.tmd.build()
    changed = changed_programs(old, effective)
    assert set(changed) >= {0, 1, 2, 3, 4, 18}, changed
    for slot in SLOTS:
        samples, loop, _ = animsheet.slot_frames(effective, NB, slot)
        assert loop == 0
        checks.append(dict(slot=slot, ticks=len(samples) - 1,
                           root_per_tick=round((samples[-1][0][8] - samples[0][0][8]) / (len(samples) - 1), 2)))
    return output, dict(checks=checks, storage=motionstorage.require(output, NB), species=SPECIES, source_sha256=SOURCE,
                        changed_slots=changed)


def build(data, skeleton):
    output, report = author(data, skeleton)
    return output, dict(report, output_sha256=hashlib.sha256(output).hexdigest())


def main():
    import argparse
    import json
    from pathlib import Path
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    rig = json.loads(Path('content/species/271-plesiomon.json').read_text())['model']['skeleton']
    data, report = build(Path(args.source).read_bytes(), rig)
    Path(args.out).write_bytes(data)
    print(args.out, len(data), 'B', report['storage'], report['checks'])


if __name__ == '__main__':
    main()
