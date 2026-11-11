"""Scorpiomon's field idle, walk, tired walk and run as four different movements of a hovering swimmer (species 275).

The model is an arthropod with no legs: a carapace with dorsal spikes (bone 1) carrying the face plate (2), two mouth
plates (3, 4), the eyes (5, 6), two three-segment grasping claws (7-9 right, 10-12 left), one long side blade on each
flank (13-14 right, 15-16 left) and a tail chain of wide spiky segments ending in a fan (17-22). It hovers about 170
units above the floor and nothing of it ever touches the ground, so there is no foot to plant: the four field clips the
import gave it (30 ticks each) were one and the same body wobble, only the root moved faster. This module writes slots
0, 2, 3 and 4 again, in place (slots 1 and 18 share the idle's stream and follow it; nothing else shares these four):

- idle (64 ticks): hovering and breathing. The body rises and sinks on a slow breath, the side blades ripple slowly
  and out of step, the claws curl and open a little with each segment trailing the one before, the tail sways with a
  wave that grows toward the fan, the mouth plates open and close, the head keeps its gaze against the body.
- walk (32 ticks, 26 units a tick): a steady swim. The blades row in turn (one sweeps forward and down while the other
  pulls back and up, the outer joint trailing the inner), the body rolls and yaws toward the stroking side and sways,
  the claws are carried forward and swing a little late, a vertical and a side wave travel down the tail.
- tired walk (44 ticks, 14 units): the body sinks, the nose and the head hang, the claws droop and barely move, the blades
  hang and paddle short and slow, the tail trails low with a small slow wave, the mouth hangs open.
- run (20 ticks, 42 units): the body stretched and tilted nose down, the blades swept back and rowing fast, the claws
  tucked in and up under the face, the tail raised and lashing in a quick wave.

Each clip repeats its pose cycle exactly (the last frame equals the first), the root travels the same distance every
tick and the footstep sounds of the earlier clips keep their share of the loop. Source: `edit.py get 275`.
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

SPECIES = 275
NB = 23
SOURCE = 'fea39afc76dba5aff74db37b7e31ca0894d69a22c74a5cb36d5c8eb9d21a1ed7'   # edit.py get 275 before this change
SLOTS = (0, 1, 2, 3, 4)
CLIP_OF_SLOT = {0: 'idle', 1: 'idle', 2: 'walk', 3: 'tired', 4: 'run'}
BODY = 1
FACE, MOUTH_R, MOUTH_L, EYE_R, EYE_L = 2, 3, 4, 5, 6
HEAD = (FACE, EYE_R, EYE_L)
CLAW_R, CLAW_L = (7, 8, 9), (10, 11, 12)
BLADE_R, BLADE_L = (13, 14), (15, 16)
TAIL = (17, 18, 19, 20, 21, 22)
PARENT_OF_TAIL = {b: a for a, b in zip(TAIL, TAIL[1:])}

#   n: ticks of the loop, speed: units a tick (None: in place), clear: least height of the mesh above the floor.
#   body: bob (first, second harmonic; units), sway (units), pitch (static, wave; degrees, nose down positive), roll,
#         yaw (degrees), lead: phase of the body's own motion against the strokes (radians)
#   blade: flap (degrees, down positive on the stroke), sweep (forward positive), rest sweep, droop, alt (share of a
#          cycle the left blade is behind the right), cycles per loop, outer (share of the flap the outer joint adds)
#   claw: down (static, degrees, nose down positive), curl (swing, per segment growing), open (pincers, degrees; inward
#         positive), in (static inward), lag (radians per segment), side (share of a cycle the left claw is behind)
#   tail: wave (pitch amplitude at the fan, degrees), yaw (side amplitude), up (static lift of the fan), droop at the
#         root, lag (radians from the first to the last segment), h2 (second harmonic share)
#   mouth: rest, swing (degrees); head: share of the body's turn the head cancels, look (degrees)
CLIPS = {
    'idle': dict(n=64, speed=0, clear=142,
                 body=dict(bob=(7., 2.), sway=3., pitch=(0., 1.0), roll=1.2, yaw=1.6, lead=-1.1),
                 blade=dict(flap=5., sweep=4., rest=0., droop=2., alt=.42, cycles=2, outer=.55),
                 claw=dict(down=5., curl=7., open=5., inward=0., lag=.7, side=.37),
                 tail=dict(wave=15., yaw=12., up=0., droop=0., lag=2.4, h2=.1),
                 mouth=(5., 3.), head=.7, look=2.5),
    'walk': dict(n=32, speed=26, clear=142,
                 body=dict(bob=(9., 3.), sway=8., pitch=(1.5, 1.5), roll=4.2, yaw=3.5, lead=-.9),
                 blade=dict(flap=17., sweep=13., rest=3., droop=3., alt=.5, cycles=1, outer=.7),
                 claw=dict(down=-4., curl=6., open=5., inward=4., lag=.8, side=.5),
                 tail=dict(wave=26., yaw=20., up=3., droop=0., lag=3.6, h2=.15),
                 mouth=(4., 3.), head=.8, look=0.),
    'tired': dict(n=44, speed=14, clear=105,
                  body=dict(bob=(10., 2.), sway=6., pitch=(7., 1.6), roll=3., yaw=2.2, lead=-.7),
                  blade=dict(flap=7., sweep=5., rest=-6., droop=15., alt=.5, cycles=1, outer=.6),
                  claw=dict(down=26., curl=3.5, open=3., inward=-2., lag=.9, side=.5),
                  tail=dict(wave=11., yaw=8., up=-30., droop=-12., lag=2.6, h2=.06),
                  mouth=(13., 4.), head=.3, look=0.),
    'run': dict(n=20, speed=42, clear=132,
                body=dict(bob=(6., 2.), sway=9., pitch=(9., 1.3), roll=4.5, yaw=4., lead=-1.),
                blade=dict(flap=15., sweep=12., rest=0., droop=4., alt=.5, cycles=1, outer=.75),
                claw=dict(down=-45., curl=4., open=4., inward=11., lag=.7, side=.5),
                tail=dict(wave=22., yaw=28., up=14., droop=0., lag=4.4, h2=.15),
                mouth=(3., 2.), head=.55, look=0.),
}


def sg(u, skew=.4):
    """One beat, quick and then slow (the sine, skewed), -1..1."""
    return math.sin(u + skew * math.sin(u))


class Swim:
    def __init__(self, c, n, depth):
        self.c, self.n, self.depth = c, n, depth
        th = lambda t: 2 * math.pi * t / n  # noqa: E731
        self.th = th
        b = c['blade']
        k = b['cycles']
        w = 2 * math.pi * k / n
        # blade drives: the right one on the cycle, the left one `alt` of a cycle behind; the outer joint trails the inner
        self.drive = {s: (lambda t, s=s: sg(k * th(t) - s * 2 * math.pi * (b['alt'] if s else 0), .2)) for s in (0, 1)}
        self.sweepd = {s: (lambda t, s=s: sg(k * th(t) - s * 2 * math.pi * (b['alt'] if s else 0) - 1.35, .15)) for s in (0, 1)}
        self.inner, self.outer, self.sweep = {}, {}, {}
        for s in (0, 1):
            self.inner[s] = follow(self.drive[s], n, w * 2.4, .55)
            self.outer[s] = follow(lambda t, s=s: self.sample(self.inner[s], t), n, w * 2.1, .5)
            self.sweep[s] = follow(self.sweepd[s], n, w * 2.4, .55)
            for lst in (self.inner[s], self.outer[s], self.sweep[s]):
                lst[-1] = lst[0]
        # the head's gaze: a spring on the body's turn, so it lags the body and cancels part of it
        self.gaze = follow(lambda t: math.sin(th(t) + c['body']['lead'] * .6), n, 2 * math.pi / (n * .25), .6)
        self.gaze[-1] = self.gaze[0]
        # claws: a smooth drive per side, the segments chase it one after the other
        cl = c['claw']
        self.claw = {}
        for s in (0, 1):
            drv = lambda t, s=s: sg(th(t) - 2 * math.pi * cl['side'] * s - .3, .2) + .15 * math.sin(2 * th(t) - 1 - s)  # noqa: E731
            lst = [follow(drv, n, 2 * math.pi / (n * .22), .55)]
            for i in range(2):
                prev = lst[-1]
                lst.append(follow(lambda t, p=prev: self.sample(p, t), n, 2 * math.pi / (n * .22), .55))
            for x in lst:
                x[-1] = x[0]
            self.claw[s] = lst

    @staticmethod
    def sample(lst, t):
        n = len(lst) - 1
        i = int(math.floor(t)) % n
        f = t - math.floor(t)
        return lst[i] * (1 - f) + lst[(i + 1) % n] * f

    def prof(self, s):
        return .12 + .88 * s ** 1.8

    def tail_angles(self, t):
        """Absolute pitch and yaw (degrees) of each tail segment along the travelling wave; fan last."""
        c, th = self.c['tail'], self.th(t)
        out = {}
        for b in TAIL:
            s = self.depth[b]
            ph = th - c['lag'] * s
            pitch = c['wave'] * self.prof(s) * (math.sin(ph) + c['h2'] * math.sin(2 * ph - .9))
            yaw = c['yaw'] * self.prof(s) * (math.sin(ph - math.pi / 2) + c['h2'] * math.sin(2 * ph - 2.1))
            static = c['up'] * s ** 1.5 + c['droop'] * (1 - s) ** 2
            out[b] = (pitch + static, yaw)
        return out


def pose_at(rig, rest, sw, c, t, n, rootz):
    th = 2 * math.pi * t / n
    pose = copy.deepcopy(rest)
    pose[0] = [4096] * 3 + [0, 0, 0, 0, 0, rootz]
    bd = c['body']
    lead = bd['lead']
    # the whole body: bob and sway, the pitch, the roll and the yaw toward the stroking side
    pose[BODY][7] = rest[BODY][7] - round(bd['bob'][0] * math.sin(th + lead) + bd['bob'][1] * math.sin(2 * th + lead * .5))
    pose[BODY][6] = rest[BODY][6] + round(bd['sway'] * math.sin(th + lead - .7))
    p_body = bd['pitch'][0] + bd['pitch'][1] * math.sin(2 * th + lead - .4)
    r_body = bd['roll'] * (math.sin(th + lead + .2) + .18 * math.sin(2 * th + 1.1))
    y_body = bd['yaw'] * math.sin(th + lead - .3)
    rig.turn(pose, BODY, x=p_body, y=y_body, z=r_body)
    # head: cancels a share of the body's turn and looks about a little
    g = Swim.sample(sw.gaze, t)
    for b in HEAD:
        rig.turn(pose, b, x=-c['head'] * p_body, y=-c['head'] * y_body - c['look'] * g, z=-c['head'] * r_body)
    # the mouth plates open and close, a little out of step
    mr, ms = c['mouth']
    for b, ph in ((MOUTH_R, 0.), (MOUTH_L, .45)):
        rig.turn(pose, b, x=mr + ms * math.sin(th + lead - 1.0 - ph))
    # the claws
    cl = c['claw']
    for s, (chain, sign) in enumerate(((CLAW_R, 1), (CLAW_L, -1))):
        for i, b in enumerate(chain):
            v = Swim.sample(sw.claw[s][i], t)
            share = (.5, .8, 1.0)[i]
            x = cl['down'] / 3. + cl['curl'] * share * v
            # pincers: the claw closes and opens about its own tip; inward is toward the body's middle
            y = sign * (cl['inward'] / 3. + (cl['open'] * (0.4, 0.7, 1.0)[i]) * Swim.sample(sw.claw[s][i], t - 3))
            rig.turn(pose, b, x=x, y=y)
    # the side blades: rowing in turn, the outer joint trails the inner one
    bl = c['blade']
    for s, (chain, sign) in enumerate(((BLADE_R, 1), (BLADE_L, -1))):
        g1 = Swim.sample(sw.inner[s], t)
        g2 = Swim.sample(sw.outer[s], t)
        sv = Swim.sample(sw.sweep[s], t)
        # z: down positive on the right (mirrored on the left); y: forward positive on the right
        rig.turn(pose, chain[0], y=sign * (bl['rest'] + bl['sweep'] * .6 * sv), z=sign * (bl['droop'] + .6 * bl['flap'] * g1))
        rig.turn(pose, chain[1], y=sign * (.4 * bl['sweep'] * sv), z=sign * (.5 * bl['droop'] + bl['outer'] * bl['flap'] * (g2 - .6 * g1)))
    # the tail: a wave that grows toward the fan; absolute angles, each segment turns by its difference from its parent
    ang = sw.tail_angles(t)
    for b in TAIL:
        pa, ya = ang[b]
        pp, yp = ang[PARENT_OF_TAIL[b]] if b in PARENT_OF_TAIL else (0., 0.)
        rig.turn(pose, b, x=(pa - pp), y=(ya - yp))
    return pose


def lowest(old, skeleton, pose):
    return max(v[1] for tri in animsheet.world_tris(old, [[4096, 4096, 4096, 0, 0, 0, 0, 0, 0]] + pose[1:], skeleton)
               for v in tri[0])


def mean_rest(frames):
    n = len(frames) - 1
    rest = copy.deepcopy(frames[0])
    for b in range(1, len(rest)):
        for k in range(3, 9):
            rest[b][k] = round(sum(f[b][k] for f in frames[:n]) / n)
    return rest


def depths(old, rest):
    q = [list(v) for v in rest]
    q[0] = [4096] * 3 + [0] * 6
    w = mmd.bone_matrices(old, q)
    z0, z1 = w[TAIL[0]][2][3], w[TAIL[-1]][2][3]
    return {b: (w[b][2][3] - z0) / (z1 - z0) for b in TAIL}


def author(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError("Scorpiomon's swimming clips are written over the reviewed import")
    mmd.exe().add_type(SPECIES, skeleton)
    old = mmd.MMD.parse(data, NB)
    old.type = SPECIES
    idle0, _, _ = animsheet.slot_frames(old, NB, 0)
    rest = mean_rest([[[round(x) for x in v] for v in p] for p in idle0])
    depth = depths(old, rest)
    result = copy.deepcopy(old)
    streams = {}
    for slot in (0, 2, 3, 4):
        c = CLIPS[CLIP_OF_SLOT[slot]]
        n = c['n']
        frames, loop, events = animsheet.slot_frames(old, NB, slot)
        period = len(frames) - 1
        ev = [(round(e[0] * n / period), e[1], dict(e[2], frame=round(e[0] * n / period) + 1)) for e in events]
        sw = Swim(c, n, depth)
        rig = Rig(old, skeleton)
        out = [pose_at(rig, rest, sw, c, t, n, -round(c['speed'] * t)) for t in range(n + 1)]
        out = [[[round(x) for x in v] for v in p] for p in out]
        low = max(lowest(old, skeleton, p) for p in out)
        for p in out:
            p[BODY][7] += round(-c['clear'] - low)
        mmd.close_loop(out, 0)
        streams[slot] = result.anims.table[slot]
        result.anims.anims[streams[slot]] = mmd.encode_anim(out, NB, 0, ev, tol=1)
    for anim in result.anims.anims:
        anim.tail = b''
    result.anims.anims, result.anims.table = motioncyclelayer.share_identical_streams(result.anims.anims, result.anims.table)
    output = result.build()
    effective = mmd.MMD.parse(output, NB)
    effective.type = SPECIES
    assert effective.tmd.build() == old.tmd.build()
    changed = changed_programs(old, effective)
    assert set(changed) >= {0, 2, 3, 4}, changed
    checks = []
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
    rig = json.loads(Path('content/species/275-scorpiomon.json').read_text())['model']['skeleton']
    data, report = build(Path(args.source).read_bytes(), rig)
    Path(args.out).write_bytes(data)
    print(args.out, len(data), 'B', report['storage'], report['checks'])


if __name__ == '__main__':
    main()
