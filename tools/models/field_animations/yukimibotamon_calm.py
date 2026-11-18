"""Yukimibotamon's (species 472) field clips: a calm idle and three soft hops.

Yukimibotamon keeps Botamon's three-bone rig: 0 the root, 1 a fixed lift, 2 the body object (scaled to squash and stretch, it
holds the whole mesh, sprout included). Botamon's own clips lunge hard (a 30 % squash, a 60-unit jump). These are slower
and smaller:

  idle   96 ticks: two slow breaths, a slow look to each side, a gentle sway, three blinks (lid, four closed ticks, lid); walk one, tired two slow ones, run one
  walk   2 hops of 22 ticks (a left and a right one, 17 units a tick), 11 units high: a soft landing, a slow rebound
  tired  2 hops of 30 ticks, 11 units a tick, 4 units high: a long low crouch, leaning forward, drowsy eyes
  run    3 hops of 16 ticks, 38 units a tick, 18 units high: long low bounds leaning forward

The body lands and stays where it landed until it takes off (no slide while it is down); the root, which the game
follows, moves steadily. After every pose the body is lowered or raised so the lowest point of the mesh is exactly on the
floor on the ground and `lift` units above it in the air. Slots 2, 3 and 4 are replaced; slot 0 gets a clip of its own
when its program is shared with other poses. The mesh, the texture and the other slots do not change.

    python -m tools.models.field_animations.yukimibotamon_calm SRC.MMD OUT.MMD
where SRC is the baby as built by `tools.models.babies` before this change.
"""
import copy
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import mmd  # noqa: E402
import motioncyclelayer  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402

SPECIES = 472
DONOR = 1
NB = 3
BODY = 2
DEG = 4096 / 360
SLOTS = (0, 2, 3, 4)
EYES = {'open': (42, 0), 'down': (30, 0), 'lid': (30, 0), 'closed': (36, 0)}   # (source x in words, y) of the 6x16 eye rectangle at (2, 8)
MOUTHS = {'shut': (12, 16), 'down': (12, 16), 'open': (18, 16)}  # the 6x16 mouth rectangle at (0, 24)

# (tick in the hop, value); the body lands at tick 0 and leaves the ground at `contact`.
#   squash  1 = the deepest crouch, negative = stretched    pitch  degrees, positive leans forward
GAITS = {
    2: dict(name='walk', period=22, hops=2, contact=10, speed=17, height=11, base_pitch=2.5,
            squash={0: .45, 1: .8, 3: .55, 5: .2, 7: .3, 8: .7, 9: .35, 10: -.2, 11: -.4, 14: -.2, 18: -.3, 20: -.1},
            pitch={0: -2, 2: -3, 6: -1, 9: -3, 10: 0, 12: 4, 17: 2, 21: -1}, roll=2.2, yaw=3.5,
            eyes=[(0, 'open')], mouth=[(0, 'shut'), (11, 'open'), (19, 'shut')]),
    3: dict(name='tired', period=30, hops=2, contact=16, speed=11, height=5, base_pitch=7,
            squash={0: .55, 2: .9, 5: .6, 9: .45, 13: .8, 15: .85, 16: .3, 17: .05, 21: .15, 26: .25, 28: .4},
            pitch={0: 0, 3: -2, 8: 0, 13: -2, 16: 2, 20: 3, 26: 1, 29: 0}, roll=2.5, yaw=3,
            eyes=[(0, 'down')], mouth=[(0, 'down')]),
    4: dict(name='run', period=16, hops=3, contact=6, speed=38, height=18, base_pitch=8,
            squash={0: .5, 1: .85, 3: .5, 4: .6, 5: .2, 6: -.2, 7: -.4, 10: -.25, 13: -.3, 15: -.05},
            pitch={0: -2, 2: -2, 5: -2, 6: 1, 8: 5, 12: 3, 15: 0}, roll=1.5, yaw=2,
            eyes=[(0, 'open')], mouth=[(0, 'shut'), (7, 'open'), (13, 'shut')]),
}
IDLE_TICKS = 96
IDLE_LOOK = [(0, 0), (16, 0), (26, 13), (44, 13), (54, 0), (64, 0), (74, -11), (90, -11), (96, 0)]


# ------------------------------------------------------------------ curves
def periodic(keys, period):
    """A smooth closed curve through (tick, value) keys (Catmull-Rom over the period)."""
    ks = sorted(keys.items())
    n = len(ks)

    def at(t):
        t %= period
        i = max(k for k in range(n) if ks[k][0] <= t) if t >= ks[0][0] else n - 1
        t0, p1 = ks[i]
        t1, p2 = ks[(i + 1) % n]
        p0, p3 = ks[(i - 1) % n][1], ks[(i + 2) % n][1]
        span = (t1 - t0) % period or period
        u = ((t - t0) % period) / span
        return .5 * (2 * p1 + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u
                     + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3)
    return at


def eased(keys):
    def at(t):
        for (t0, a), (t1, b) in zip(keys, keys[1:]):
            if t0 <= t <= t1:
                u = (t - t0) / (t1 - t0)
                return a + (b - a) * (1 - math.cos(math.pi * u)) / 2
        return keys[-1][1]
    return at


def wave(cycles, n, t, phase=0.):
    return math.sin(2 * math.pi * (cycles * t / n + phase))


# ------------------------------------------------------------------ the rig
class Rig:
    def __init__(self, model):
        self.model = model
        frames = _slot0(model)
        self.rest = [list(v) for v in frames[0]]
        self.rest[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
        self.skel = mmd.exe().skeleton[SPECIES]
        self.verts = {oi: [v[:3] for v in model.tmd.obj_verts(oi)] for oi, _ in self.skel if oi >= 0}
        self.floor = self._low(self.rest)

    def _low(self, pose):
        mats = mmd.bone_matrices(self.model, pose)
        low = -1e9
        for b, (oi, _) in enumerate(self.skel):
            if oi >= 0:
                M = mats[b]
                low = max(low, max(M[1][0] * x + M[1][1] * y + M[1][2] * z + M[1][3] for x, y, z in self.verts[oi]))
        return low

    def pose(self, squash=0., pitch=0., roll=0., yaw=0., lift=0.):
        p = copy.deepcopy(self.rest)
        b = p[BODY]
        b[1] = round(4096 * (1 - .16 * squash))
        b[0] = b[2] = round(4096 * (1 + .08 * squash))
        b[3], b[4], b[5] = round(pitch * DEG), round(yaw * DEG), round(roll * DEG)
        # the body hangs from its centre: put the lowest point of the mesh on the floor, then lift it
        p[BODY][7] = 0
        p[BODY][7] = math.floor(self.floor - lift - self._low(p))
        return p


def _slot0(model):
    import animsheet
    return animsheet.slot_frames(model, NB, 0)[0]


# ------------------------------------------------------------------ events
def tex(frame_tick, kind, name):
    if kind == 'eye':
        src, size, dst = EYES[name], (6, 16), (2, 8)
    else:
        src, size, dst = MOUTHS[name], (6, 16), (0, 24)
    return (frame_tick, 'tex', dict(op='tex', frame=frame_tick + 1, src=src, size=size, dst=dst))


def blink(t, base, hold=4):
    """Lid coming down (the half-closed frame), shut for `hold` ticks, the lid again, then the base eye."""
    return [tex(t, 'eye', 'lid'), tex(t + 1, 'eye', 'closed'), tex(t + 1 + hold, 'eye', 'lid'), tex(t + 2 + hold, 'eye', base)]


BLINKS = {0: (10, 42, 74), 2: (12,), 3: (8, 38), 4: (20,)}     # start ticks per clip (a blink never crosses a hop start)
HOLD = {0: 4, 2: 4, 3: 4, 4: 3}


# ------------------------------------------------------------------ the clips
def gait(rig, slot, sound):
    g = GAITS[slot]
    P, hops, c = g['period'], g['hops'], g['contact']
    n = P * hops
    squash, pitch = periodic(g['squash'], P), periodic(g['pitch'], P)
    hop = g['speed'] * P
    f = P - c

    def height(t):
        tau = t % P
        if tau <= c:
            return 0.
        s = (tau - c) / f
        return 4 * g['height'] * s * (1 - s)

    def body_z(t):
        k, tau = divmod(t, P)
        if tau <= c:
            return k * hop
        s = (tau - c) / f
        return k * hop + hop * (.1 * s + .9 * (3 * s * s - 2 * s ** 3))

    mean = sum(body_z(t) - g['speed'] * t for t in range(P)) / P
    vmax = max(1., 4 * g['height'] / f)
    frames = []
    for t in range(n + 1):
        tt = t % n
        tau = tt % P
        rise = lambda x: (height(x) - height(x - 1)) / vmax          # -1..1, up positive
        side = 1 if (tt // P) % 2 == 0 else -1
        roll = g['roll'] * side * math.sin(math.pi * min(1., tau / P)) * (1 if tau else 0)
        pose = rig.pose(squash=squash(tau), pitch=g['base_pitch'] + pitch(tau), lift=height(tt),
                        roll=roll, yaw=g['yaw'] * wave(hops / 2 if hops % 2 == 0 else hops, n, tt, .2))
        world = -body_z(t)
        root_line = -(.5 * (body_z(t) + mean) + .5 * g['speed'] * t)
        pose[0][8] = round(root_line)
        pose[BODY][8] = round(world - root_line)
        frames.append([[int(round(x)) for x in v] for v in pose])
    events = [(k * P, 'sound', dict(sound)) for k in range(hops)]
    for k in range(hops):
        events += [tex(k * P + t, 'eye', s) for t, s in g['eyes']]
        events += [tex(k * P + t, 'mouth', s) for t, s in g['mouth']]
    for t in BLINKS[slot]:
        events += blink(t, g['eyes'][0][1], HOLD[slot])
    events.sort(key=lambda e: e[0])
    return frames, events


def idle(rig):
    n = IDLE_TICKS
    look = eased(IDLE_LOOK)
    frames = []
    for t in range(n + 1):
        tt = t % n
        breath = .5 - .5 * math.cos(2 * math.pi * 2 * tt / n)
        pose = rig.pose(squash=.28 * breath - .08, pitch=1.2 * wave(1, n, tt, .1) + 1, roll=1.2 * wave(1, n, tt, .6),
                        yaw=look(tt))
        frames.append([[int(round(x)) for x in v] for v in pose])
    events = [tex(0, 'eye', 'open'), tex(0, 'mouth', 'shut')]
    for t in BLINKS[0]:
        events += blink(t, 'open', HOLD[0])
    return frames, events


# ------------------------------------------------------------------ build
def _parse(data):
    mmd.exe().skeleton[SPECIES] = mmd.exe().skeleton[DONOR]
    mmd.exe().bone_count[SPECIES] = NB
    model = mmd.MMD.parse(data, NB)
    model.type = SPECIES
    return model


def author(data):
    import animsheet
    old = _parse(data)
    rig = Rig(old)
    new = copy.deepcopy(old)
    report = []
    for slot in SLOTS:
        if slot == 0:
            frames, events = idle(rig)
        else:
            _, _, src = animsheet.slot_frames(old, NB, slot)
            sound = next(dict(bank=e[2]['bank'], note=e[2]['note']) for e in src if e[1] == 'sound')
            frames, events = gait(rig, slot, sound)
        mmd.close_loop(frames, 0)
        anim = mmd.encode_anim(frames, NB, 0, events, tol={BODY: 0, None: 1})
        index = old.anims.table[slot]
        if slot == 0 or sum(1 for i in old.anims.table if i == index) > 1:
            new.anims.table[slot] = len(new.anims.anims)
            new.anims.anims.append(anim)
        else:
            new.anims.anims[index] = anim
        n = len(frames) - 1
        report.append(dict(slot=slot, ticks=n, root_per_tick=round((frames[0][0][8] - frames[-1][0][8]) / n, 2)))
    for anim in new.anims.anims:
        anim.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    output = new.build()
    actual = _parse(output)
    assert actual.tmd.build() == old.tmd.build()
    assert changed_programs(old, actual) == list(SLOTS), changed_programs(old, actual)
    return output, report


def build(data):
    output, report = author(data)
    return output, dict(species=SPECIES, clips=report, storage=motionstorage.require(output, NB))


def main():
    out, proof = build(Path(sys.argv[1]).read_bytes())
    Path(sys.argv[2]).write_bytes(out)
    print(proof)


if __name__ == '__main__':
    main()
