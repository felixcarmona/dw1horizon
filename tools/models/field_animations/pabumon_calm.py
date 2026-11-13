"""Pabumon's (species 470) field clips: a calm baby blob that bounces softly, in four clips of its own.

Pabumon is a one-bone squash-and-stretch blob on Punimon's skeleton (bone 1 is the body pivot, 45 units above the
floor; bone 2 carries the mesh). Punimon's own clips squash it to half its height and stretch it to one and a half
times, spin it and throw it 200 units sideways in a tick, which reads as frantic, and the slides of its ground phase
carry the blob along with the root. These four replace slots 0, 2, 3 and 4:

  idle   96 ticks: four breaths, two curious look-arounds (to the right, then to the left with the head tipped up and the
         body rolling into the look), a crouch and a small hop with a soft landing that overshoots, two blinks
  walk   2 hops of 20 ticks, 16 units a tick (320 a hop), 22 units high: lands squashed, rebounds a little, crouches
         (anticipation) and stretches into the air; the body leans into the movement and rolls from side to side; a blink
  tired  2 slow hops of 24 ticks, 12 units a tick, 6 units high: a heavy droop (low, wide, leaning far forward) with
         half-shut eyes and one slow blink
  run    4 hops of 12 ticks, 38 units a tick (456 a hop), 24 units high: flatter, longer bounds leaning forward

Blinks: the eye texture is moved to the half-lidded frame, then the closed (an arc) for three ticks (six in the tired
clip), half, and open again. They are not tied to the hops. The studio renders a static texture; judge them with the
texture moves applied.

The body never slides while it is down: it stays where it landed until the take-off (the root, which the game
follows, moves steadily and the body's own bone takes up the difference). Its lowest point stays on the floor, the
bone's height is solved every tick from the squashed, rolled mesh. Every channel repeats a whole number of times per clip.

    python -m tools.models.field_animations.pabumon_calm --out DIR/470.MMD     (the MMD of `python -m tools.models.babies`)
"""
import argparse
import copy
import hashlib
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet  # noqa: E402
import mmd  # noqa: E402
import motioncyclelayer  # noqa: E402
import motionstorage  # noqa: E402
from tools.models.field_animations.candlemon_hop import eased, periodic, wave  # noqa: E402

SPECIES = 470
SOURCE = 'c8e8df005a3b074fef2895976618e1f94f210b25d582beae97c9561dac249de3'              # the model before this change (the delta's old result)
DONOR = 15
NB = 3
BODY = 1
DEG = 4096 / 360
SLOTS = (0, 2, 3, 4)
EYE, EYE_SIZE, EYE_AT = {'open': (208, 0), 'half': (80, 0), 'shut': (112, 0)}, (32, 24), (8, 4)
MOUTH_REST = ((96, 32), (16, 24), (0, 40))
SOUND = dict(bank=1, note=10)
REST_Y = -45                                       # the body pivot above the floor, as Punimon rests

# squash 1 = squashed (low and wide), negative = stretched; lean degrees, positive pitches the top forward
GAITS = {
    2: dict(name='walk', period=20, hops=2, contact=8, speed=16, height=22, squash_gain=.26, base_lean=5, follow=.4,
            squash={0: .5, 2: 1., 4: -.15, 6: .55, 8: .9, 10: -.9, 13: -.6, 16: -.4, 19: -.15},
            lean={0: -4, 3: -3, 6: -5, 8: -3, 11: 7, 15: 5, 19: -1}, roll=4., yaw=5., blinks=(27,)),
    3: dict(name='tired', period=24, hops=2, contact=16, speed=12, height=6, squash_gain=.22, base_lean=13, follow=.4,
            squash={0: .9, 3: 1.1, 8: .8, 13: 1., 16: .6, 18: -.3, 21: -.15, 23: .5},
            lean={0: -2, 4: -4, 10: -1, 15: -4, 17: 3, 21: 4, 23: 0}, roll=3., yaw=4., blinks=(30,)),
    4: dict(name='run', period=12, hops=4, contact=4, speed=38, height=24, squash_gain=.24, base_lean=12, follow=.4,
            squash={0: .6, 1: 1., 2: .3, 3: .8, 4: -.6, 5: -.7, 8: -.35, 10: -.3, 11: -.05},
            lean={0: -3, 2: -3, 4: 2, 6: 6, 10: 4, 11: 0}, roll=3., yaw=3., blinks=(31,)),
}
IDLE_TICKS = 96
BLINK_HOLD = 3                                      # ticks with the eyes shut (about a tenth of a second)


def _eye(k):
    return dict(src=(EYE[k][0] // 4, EYE[k][1]), size=(EYE_SIZE[0] // 4, EYE_SIZE[1]), dst=(EYE_AT[0] // 4, EYE_AT[1]))


def _mouth():
    src, size, dst = MOUTH_REST
    return dict(src=(src[0] // 4, src[1]), size=(size[0] // 4, size[1]), dst=(dst[0] // 4, dst[1]))


def face(first, blinks, slow=False):
    """Tick-0 face plus blinks [(tick)]: half, shut for BLINK_HOLD ticks (more if slow), half, back to the first eye."""
    out = [(0, 'tex', _eye(first)), (0, 'tex', _mouth())]
    for t in blinks:
        hold = BLINK_HOLD + (3 if slow else 0)
        steps = [(0, 'half'), (1, 'shut'), (1 + hold, 'half'), (2 + hold, first)] if first != 'half' \
            else [(0, 'shut'), (hold + 1, 'half')]
        out += [(t + dt, 'tex', _eye(k)) for dt, k in steps]
    return out


class Rig:
    def __init__(self, model):
        self.model = model
        self.skel = mmd.exe().skeleton[SPECIES]
        idle, _, _ = animsheet.slot_frames(model, NB, 0)
        self.rest = copy.deepcopy(idle[0])

    def lowest(self, pose):
        """The lowest point of the mesh (y down: the largest y) in the root's space."""
        pts = [v for tri in animsheet.world_tris(self.model, pose, self.skel) for v in tri[0]]
        return max(p[1] for p in pts)

    def pose(self, squash=0., gain=.17, lean=0., yaw=0., roll=0., lift=0.):
        p = copy.deepcopy(self.rest)
        sy = 1 - gain * squash
        sxz = 1 + .5 * gain * squash
        b = p[BODY]
        b[0], b[1], b[2] = round(4096 * sxz), round(4096 * sy), round(4096 * sxz)
        b[3], b[4], b[5] = round(lean * DEG), round(yaw * DEG), round(roll * DEG)
        b[7] = 0
        b[7] = round(-lift - 4.5 - self.lowest(p))
        return p


def _frames(rig, n, fn):
    frames = []
    for t in range(n + 1):
        frames.append([[int(round(x)) for x in v] for v in fn(t % n, t)])
    return frames


def gait(rig, slot):
    g = GAITS[slot]
    P, hops, c = g['period'], g['hops'], g['contact']
    n = P * hops
    squash, lean = periodic(g['squash'], P), periodic(g['lean'], P)
    hop, f = g['speed'] * P, P - c

    def height(t):
        tau = t % P
        if tau <= c:
            return 0.
        s = (tau - c) / f
        return 4 * g['height'] * s * (1 - s)

    def foot_z(t):
        k, tau = divmod(t, P)
        if tau <= c:
            return k * hop
        s = (tau - c) / f
        return k * hop + hop * (s ** 3 * (10 - 15 * s + 6 * s * s))           # eased glide, a soft push off and settle

    mean = sum(foot_z(t) - g['speed'] * t for t in range(P)) / P

    def root_z(t):
        w = g['follow']
        return (1 - w) * foot_z(t) + w * (g['speed'] * t + mean)

    def pose_at(tt, t):
        tau = tt % P
        p = rig.pose(squash=squash(tau), gain=g['squash_gain'], lean=g['base_lean'] + lean(tau),
                     yaw=g['yaw'] * wave(1, n, tt, .05) if hops == 2 else g['yaw'] * wave(2, n, tt, .05),
                     roll=g['roll'] * wave(1, n, tt), lift=height(tt))
        p[0][8] = round(-root_z(t))
        p[BODY][8] = round(-foot_z(t) + root_z(t))
        return p
    frames = _frames(rig, n, pose_at)
    events = face('half' if slot == 3 else 'open', list(g['blinks']), slow=slot == 3)
    if slot != 3:
        events += [(k * P, 'sound', dict(SOUND)) for k in range(hops)]
    events.sort(key=lambda e: e[0])
    return frames, events


def idle(rig):
    n = IDLE_TICKS
    # curious look-arounds: yaw, with the head tipped up a little (pitch) and the body rolling toward the look
    look = eased([(0, 0), (8, 0), (20, 20), (36, 20), (46, 0), (54, 0), (66, -17), (82, -17), (94, 0), (96, 0)])
    tip = eased([(0, 0), (8, 0), (20, -3), (36, -3), (46, 0), (54, 0), (66, -4), (82, -4), (94, 0), (96, 0)])
    hop = lambda t: 6 * math.sin(math.pi * (t - 47) / 9) ** 2 if 47 <= t <= 56 else 0.

    def pose_at(tt, t):
        breath = .5 - .5 * math.cos(2 * math.pi * 4 * tt / n)
        crouch = .7 * math.sin(math.pi * (tt - 40) / 7) if 40 <= tt < 47 else 0.          # anticipation of the hop
        settle = .6 * math.sin(math.pi * (tt - 56) / 9) * math.exp(-(tt - 56) / 6) if 56 <= tt <= 65 else 0.
        return rig.pose(squash=.5 * breath - .15 + crouch + settle, gain=.16, lean=tip(tt) + 1.5 * wave(2, n, tt, .25),
                        yaw=look(tt), roll=2.5 * wave(1, n, tt, .1) + .12 * look(tt), lift=hop(tt))
    frames = _frames(rig, n, pose_at)
    return frames, face('open', [26, 76])


def author(data):
    mmd.exe().skeleton[SPECIES] = mmd.exe().skeleton[DONOR]
    mmd.exe().bone_count[SPECIES] = NB
    old = mmd.MMD.parse(data, NB)
    old.type = SPECIES
    rig = Rig(old)
    new = copy.deepcopy(old)
    report = []
    for slot in SLOTS:
        frames, events = idle(rig) if slot == 0 else gait(rig, slot)
        mmd.close_loop(frames, 0)
        anim = mmd.encode_anim(frames, NB, 0, events, tol=0)
        index = old.anims.table[slot]
        if sum(1 for i in old.anims.table if i == index) > 1:
            new.anims.table[slot] = len(new.anims.anims)
            new.anims.anims.append(anim)
        else:
            new.anims.anims[index] = anim
        k = len(frames) - 1
        report.append(dict(slot=slot, ticks=k, root_per_tick=round((frames[0][0][8] - frames[-1][0][8]) / k, 2)))
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    return new.build(), report


def build(data):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('Pabumon needs the model it had before this change')
    out, report = author(data)
    motionstorage.require(out, NB)
    return out, report


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--source', type=Path, required=True, help='the MMD before this change')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    out, report = build(a.source.read_bytes())
    a.out.write_bytes(out)
    for r in report:
        print(r)


if __name__ == '__main__':
    main()
