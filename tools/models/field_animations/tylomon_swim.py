"""Tylomon's field idle, walk, condition walk and run as four different swimming movements.

The import's field clips (17, 27, 21 and 21 ticks) were one stiff pendulum: the body held almost still for half the loop,
then snapped through a yaw of the whole body and tail in nearly the same phase (every bone within three ticks of the
others), and held again, so it read as two beats. The condition walk and the run were the same poses with only the root
faster. This module writes slots 0, 1, 2, 3 and 4 again (every other slot, the mesh and the rig stay):

- the body is straightened (the import's rest pose bent the spine in a zig-zag) and a travelling wave runs down it: the
  yaw of every segment is a sine that the head starts and every bone further back follows a fixed phase later, growing
  toward the tail tip, with a weaker second harmonic that gives the tail a soft lash. A smaller wave in the vertical
  plane trails the side wave by a quarter, the body rolls and sways against the tail, the head counter-turns to keep
  its gaze, and the pectoral and hind fins paddle through springs (the outer joint of each fin trails the inner one);
- idle (60 ticks): hovering and breathing, the wave only a few degrees, the fins sculling slowly at another rate;
- walk (36 ticks, 15 units a tick): a steady swim, the wave about as long as the distance the body covers in a loop;
- condition walk (48 ticks, 14.7 units): the head and the tail sag, the body sinks lower and bobs heavily, short slow
  waves, the fins hang;
- run (18 ticks, 35 units): the body stretched and tilted forward, the fins swept back, a quick, longer wave with a
  strong tail beat.

Every clip repeats its pose cycle exactly (the last tick equals the first), the root travels the same distance every tick
and the footstep sounds keep their place in the loop.
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

SPECIES = 254
NB = 20
SOURCE = '37ea84f657d1ba815408a5637ca638916260e241373daf95d7c418eb9d36c444'   # edit.py get 254 before this change
SLOTS = (0, 1, 2, 3, 4)
CLIP_OF_SLOT = {0: 'idle', 1: 'idle', 2: 'walk', 3: 'tired', 4: 'run'}
# the bones, their depth along the body (rest z of the joint, head first) and their parents
HEAD, JAW, NECK, CHEST, MID, HIPS = 1, 2, 3, 4, 9, 10
SPINE = (HIPS, MID, CHEST, NECK, HEAD)
TAIL = (13, 14, 15, 16, 17, 18, 19)
FIN_R, FIN_R2, FIN_L, FIN_L2 = 5, 6, 7, 8
HIND_R, HIND_L = 11, 12
REST_Z = {1: -190, 3: -157, 4: -118, 9: -76, 10: -87, 13: -48, 14: -14, 15: 21, 16: 67, 17: 122, 18: 179, 19: 227}
Z_HEAD, Z_TIP = -190., 227.
ZERO_ROT = tuple(SPINE) + TAIL + (JAW,)

#   ticks (a loop), the root's units a tick (None: idle, in place), the side wave's amplitude at the tail tip (degrees),
#   the share of it at the head, the wave's total phase lag from head to tail tip (radians), the second harmonic's share
#   and its extra lag, the vertical wave's amplitude and its static droop profile (head, tail: degrees), the roll, the
#   body's sway (units), the bob (units, first and second harmonic), the pitch of the whole body (degrees, nose down
#   positive), the fins (sweep back, flap, their droop in degrees), the jaw (rest, swing), the height of the lowest point
#   of the mesh above the floor, the cycles the fins make in a loop.
CLIPS = {
    'idle': dict(n=60, speed=0, tip=9., head=.35, lag=2.6, h2=.15, h2lag=.9, vert=2.5, droop=(0, 0), roll=1.2, sway=4.,
                 bob=(5., 1.5), pitch=0, fin=(2., 7., 0.), jaw=(9., 3.), clear=108, fincycles=2, headlook=4.),
    'walk': dict(n=36, speed=15., tip=31., head=.28, lag=3.9, h2=.12, h2lag=1.1, vert=5., droop=(0, 0), roll=3., sway=8.,
                 bob=(5., 1.8), pitch=1, fin=(6., 11., 0.), jaw=(8., 3.), clear=108, fincycles=1, headlook=0.),
    'tired': dict(n=48, speed=14., tip=17., head=.45, lag=2.6, h2=.06, h2lag=.7, vert=6., droop=(-14, -10), roll=2., sway=5.,
                  bob=(10., 2.), pitch=0, fin=(-4., 7., 12.), jaw=(15., 5.), clear=62, fincycles=1, headlook=0.),
    'run': dict(n=18, speed=35., tip=27., head=.22, lag=4.6, h2=.14, h2lag=1.4, vert=4., droop=(0, 0), roll=3.5, sway=9.,
                bob=(3., 1.), pitch=-9, fin=(28., 7., -4.), jaw=(5., 2.), clear=118, fincycles=1, headlook=0.),
}
DEG = 4096 / 360


def prof(s, head):
    """Share of the wave's amplitude at the body depth s (0 head .. 1 tail tip): small at the head, growing to the tip."""
    return head + (1 - head) * s ** 1.7


def depth(bone):
    return (REST_Z[bone] - Z_HEAD) / (Z_TIP - Z_HEAD)


class Swim:
    def __init__(self, c, n):
        self.c, self.n = c, n
        th = lambda t: 2 * math.pi * t / n  # noqa: E731
        self.th = th
        # the fins: spring-driven paddles; a periodic drive, the outer joint chasing the inner one
        k = c['fincycles']
        drive = lambda t: math.sin(k * th(t))  # noqa: E731
        sweep = lambda t: math.sin(k * th(t) - 1.2)  # noqa: E731
        w = 2 * math.pi * k / n
        self.flap = follow(drive, n, w * 2.2, .55)
        self.flap2 = follow(lambda t: self.sample(self.flap, t), n, w * 2.0, .5)
        self.sweep = follow(sweep, n, w * 2.2, .55)
        for lst in (self.flap, self.flap2, self.sweep):
            lst[-1] = lst[0]
        # the head's gaze: a spring on the pelvis yaw, so it turns back against the body and lags it
        self.gaze = follow(lambda t: math.sin(th(t) - c['lag'] * .15), n, 2 * math.pi / (n * .22), .6)
        self.gaze[-1] = self.gaze[0]

    def sample(self, lst, t):
        n = len(lst) - 1
        i = int(math.floor(t)) % n
        f = t - math.floor(t)
        return lst[i] * (1 - f) + lst[(i + 1) % n] * f

    def yaw(self, s, t):
        c, th = self.c, self.th(t)
        return c['tip'] * prof(s, c['head']) * (math.sin(th - c['lag'] * s) + c['h2'] * math.sin(2 * th - 2 * c['lag'] * s - c['h2lag']))

    def pitch(self, s, t):
        """Vertical wave (a quarter behind the side wave), the static droop and the tilt of the whole body."""
        c, th = self.c, self.th(t)
        wave = c['vert'] * prof(s, .3) * math.sin(th - c['lag'] * s - math.pi / 2)
        droop = c['droop'][0] * (1 - s) ** 2 + c['droop'][1] * s ** 2
        return wave + droop + c['pitch'] * (1 - .5 * s)


def pose_at(rig, rest, sw, c, t, n, rootz):
    th = 2 * math.pi * t / n
    pose = copy.deepcopy(rest)
    pose[0] = [4096] * 3 + [0, 0, 0, 0, 0, rootz]
    # the body: sway against the tail, bob, a slow roll with the wave
    pose[HIPS][6] = rest[HIPS][6] - round(c['sway'] * math.sin(th - c['lag'] * .5))
    pose[HIPS][7] = rest[HIPS][7] - round(c['bob'][0] * math.sin(th - 1.1) + c['bob'][1] * math.sin(2 * th - .4))
    ya = {HIPS: sw.yaw(depth(HIPS), t)}
    pa = {HIPS: sw.pitch(depth(HIPS), t)}
    roll = c['roll'] * math.sin(th - c['lag'] * .5 + .8)
    rig.turn(pose, HIPS, x=pa[HIPS], y=ya[HIPS], z=roll)
    parent = {MID: HIPS, CHEST: MID, NECK: CHEST, HEAD: NECK, 13: HIPS}
    parent.update({b: a for a, b in zip(TAIL, TAIL[1:])})
    for b in (MID, CHEST, NECK, HEAD) + TAIL:
        s = depth(b)
        y = sw.yaw(s, t)
        p = sw.pitch(s, t)
        if b == HEAD:
            # the head turns back against the neck's yaw and looks about a little
            y = y * .5 - c['headlook'] * sw.sample(sw.gaze, t)
            p = p * .6
        ya[b], pa[b] = y, p
        a = parent[b]
        rig.turn(pose, b, x=p - pa[a], y=y - ya[a], z=0.)
    # the jaw
    rig.turn(pose, JAW, x=c['jaw'][0] + c['jaw'][1] * math.sin(th - .5 * c['lag'] - .6))
    # the fins: flap (paddle), sweep back and droop; the outer joint chases the inner one through a spring
    sweep_back, flap, droop = c['fin']
    sv = sw.sample(sw.sweep, t)
    for sign, b1, b2, lagw in ((1, FIN_R, FIN_R2, 0.), (-1, FIN_L, FIN_L2, .45)):
        g1 = sw.sample(sw.flap, t - lagw * n / 20)
        g2 = sw.sample(sw.flap2, t - lagw * n / 20)
        rig.turn(pose, b1, y=sign * (sweep_back + .3 * flap * sv), z=sign * (droop + flap * g1))
        rig.turn(pose, b2, y=sign * .25 * flap * sv, z=sign * .8 * flap * (g2 - g1))
    for sign, b in ((1, HIND_R), (-1, HIND_L)):
        g = sw.sample(sw.flap2, t - 3 - (0 if sign > 0 else 2))
        rig.turn(pose, b, y=sign * .3 * sweep_back, z=sign * (.45 * flap * g + .3 * droop))
    return pose


def lowest(old, skeleton, pose):
    return max(v[1] for tri in animsheet.world_tris(old, [[4096, 4096, 4096, 0, 0, 0, 0, 0, 0]] + pose[1:], skeleton)
               for v in tri[0])


def author(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError("Tylomon's swimming clips are written over the reviewed import")
    mmd.exe().add_type(SPECIES, skeleton)
    old = mmd.MMD.parse(data, NB)
    old.type = SPECIES
    base = [[round(x) for x in v] for v in animsheet.slot_frames(old, NB, 0)[0][0]]
    rest = copy.deepcopy(base)
    for b in ZERO_ROT:
        rest[b][3:6] = [0, 0, 0]
    result = copy.deepcopy(old)
    new_streams = {}
    checks = []
    for slot in (0, 2, 3, 4):
        c = CLIPS[CLIP_OF_SLOT[slot]]
        n = c['n']
        frames, loop, events = animsheet.slot_frames(old, NB, slot)
        period = len(frames) - 1
        # footstep sounds keep their share of the loop (the earlier walk's two, the condition walk's one, the run's two)
        ev = [(round(e[0] * n / period), e[1], dict(e[2], frame=round(e[0] * n / period) + 1)) for e in events]
        sw = Swim(c, n)
        rig = Rig(old, skeleton)
        out = []
        for t in range(n + 1):
            out.append(pose_at(rig, rest, sw, c, t, n, -round(c['speed'] * t)))
        out = [[[round(x) for x in v] for v in p] for p in out]
        low = max(lowest(old, skeleton, p) for p in out)
        for p in out:
            p[HIPS][7] += round(-c['clear'] - low)
        mmd.close_loop(out, 0)
        new_streams[slot] = len(result.anims.anims)
        result.anims.anims.append(mmd.encode_anim(out, NB, 0, ev, tol=1))
    new_streams[1] = new_streams[0]
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
    assert set(changed) >= {0, 2, 3, 4}, changed
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
    rig = json.loads(Path('content/species/254-tylomon.json').read_text())['model']['skeleton']
    data, report = build(Path(args.source).read_bytes(), rig)
    Path(args.out).write_bytes(data)
    print(args.out, len(data), 'B', report['storage'], report['checks'])


if __name__ == '__main__':
    main()
