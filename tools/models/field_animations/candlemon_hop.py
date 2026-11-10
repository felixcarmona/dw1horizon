"""Candlemon's (species 235) field clips: an idle with a flickering flame and a face that acts, and three hopping gaits.

Candlemon is a wax candle with arms, standing in a golden cup on a stem and a round foot, a flame on its wick. It has no
legs, so it travels in little hops on its foot. Bones: 11 the foot (child of the root), 10 the stem, 9 the cup, 1 the
candle (with the face), 2 the flame, 3-4-5 and 6-7-8 the right and left arm (shoulder, forearm, hand).

Every hop has an anticipation, a flight and a landing:
  landing      the foot lands flat and stops; the candle squashes into its cup (the stem sinks into the foot,
               the cup and the candle follow, the candle widens and shortens), rocks back to brake and the arms
               drop late
  rebound      a small bounce back up, then the crouch for the next hop: deeper squash, leaning back a little
  take-off     the candle stretches, pitches forward and leaves the ground; the arms swing up
  flight       a ballistic arc; the flame trails behind and is squashed while rising and stretched while falling, the
               body levels out and reaches down (stretches) just before it lands
The foot never slides while it is down: it stays where it landed until the take-off, and moves only in the air. The root
(what the game follows) moves all the time, slower while the foot is down and faster in the air. The face acts on each
hop through texture moves (candlemon_face.py): a squint when it lands, the mouth wide open in the air.

  walk   4 hops of 14 ticks, 20 units a tick (280 a hop), 52 units high
  tired  3 hops of 18 ticks, 13 units a tick (234 a hop), 20 units high: a long heavy crouch, slouched forward, flame
         drooping, eyes half shut (a slow blink) and the mouth hanging half closed, panting open on each take-off
  run    5 hops of 10 ticks, 38 units a tick (380 a hop), 34 units high: long flat bounds, leaning forward, the flame
         streaming back, arms swept back, the mouth wide open
  idle   96 ticks: breathing (the candle swells and settles in its cup four times), a slow sway, looking right and then
         left, the flame flickering, a blink, a double blink and one more, a little chew and a wide grin

Every channel repeats a whole number of times per clip, so the loops are seamless. Slot 0 gets a clip of its own (its
old program is also the poor-condition idle, a care idle and the battle idle, which stay as they are); slots 2, 3 and 4
are replaced. The mesh, the rig, the other slots and the bone scales at rest (the flame's 4710) do not change. Each clip
sets its face at tick 0, so moving between these four clips never leaves a half-shut eye or a closed mouth behind.

    python -m tools.models.field_animations.candlemon_hop --source SRC.MMD --tex SRC.TIM --out-dir DIR
where SRC is the stored model before this change (sha256 below), from `tools/models/edit.py get 235`; then
`tools/models/edit.py put 235 DIR/235.MMD DIR/235.TIM`.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet  # noqa: E402
import mmd  # noqa: E402
import motioncyclelayer  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models.field_animations import candlemon_face as face  # noqa: E402

SPECIES = 235
NB = 12
SOURCE = '16b0c3beb6c908a27fdab5fa103a939b401e2c5728129db1fe46d9191d6f1ef8'
TEX_SOURCE = '621a2bc93c98ae4f32a464fd7978ebdba6d3344835109bbd72427ca13945bc8c'
PARENTS = [-1, 9, 1, 1, 3, 4, 1, 6, 7, 10, 11, 0]
DEG = 4096 / 360
FOOT, STEM, CUP, CANDLE, FLAME = 11, 10, 9, 1, 2
ARMS = ((3, 4, 5, -1), (6, 7, 8, 1))           # shoulder, forearm, hand, side sign of the spread
SLOTS = (0, 2, 3, 4)

# keys are (tick in the hop, value); the hop lands at tick 0 and leaves the ground at `contact`.
#   squash   1 = the deepest crouch, negative = stretched
#   lean     degrees, positive pitches forward (about the foot)
#   arms     1 = raised and spread, negative = dropped
GAITS = {
    2: dict(name='walk', period=14, hops=4, contact=6, speed=20, height=52, base_lean=2, flame=-8, flame_rise=9,
            squash={0: .6, 1: .95, 2: .35, 3: .7, 4: 1., 5: .3, 6: -.6, 7: -.55, 9: -.2, 12: -.1, 13: -.35},
            lean={0: -4, 2: -2, 4: -2.5, 5: -5, 6: 6, 9: 3, 13: -2},
            arms={0: .5, 2: -.5, 4: -.2, 5: -.6, 6: .2, 8: 1., 11: .8, 13: .7}, arm_swing=22, arm_base=0,
            eyes=[(1, face.HALF), (3, face.OPEN)], mouth=[(6, face.WIDE), (11, face.MHALF), (13, face.REST)],
            blink=36, eye0=face.OPEN, mouth0=face.REST),
    3: dict(name='condition walk', period=18, hops=3, contact=9, speed=13, height=20, base_lean=7, flame=14,
            flame_rise=4, flame_shrink=.9,
            squash={0: .5, 2: .8, 4: .45, 6: .6, 8: .85, 9: .1, 10: -.3, 13: -.15, 17: -.2},
            lean={0: -2, 3: 0, 6: -1, 8: -2, 9: 4, 13: 2, 17: 0},
            arms={0: .1, 3: -.6, 7: -.4, 8: -.6, 9: .1, 12: .45, 17: .3}, arm_swing=12, arm_base=-14,
            eyes=[], mouth=[(9, face.REST), (14, face.MHALF)],
            blink=22, eye0=face.HALF, mouth0=face.MHALF),
    4: dict(name='run', period=10, hops=5, contact=3, speed=38, height=34, base_lean=10, flame=-24, flame_rise=8,
            squash={0: .55, 1: .85, 2: .45, 3: -.55, 4: -.6, 6: -.25, 8: -.15, 9: -.3},
            lean={0: -3, 1: -1, 2: 2, 3: 8, 6: 4, 9: 0},
            arms={0: -.2, 1: -.7, 2: -.5, 3: .3, 5: .9, 8: .6}, arm_swing=18, arm_base=-22,
            eyes=[(1, face.HALF), (2, face.OPEN)], mouth=[(1, face.MHALF), (3, face.WIDE)],
            blink=26, eye0=face.OPEN, mouth0=face.WIDE),
}
IDLE_TICKS = 96
IDLE_EYES = face.blink(8) + face.blink(47) + face.blink(52) + face.blink(86)
IDLE_MOUTH = [(25, face.MHALF), (27, face.MSHUT), (29, face.MHALF), (31, face.MSHUT), (33, face.REST),
              (62, face.MHALF), (63, face.WIDE), (71, face.MHALF), (73, face.REST)]
IDLE_LOOK = [(0, 0), (14, 0), (21, 16), (34, 16), (41, 0), (54, 0), (61, -14), (75, -14), (82, 0), (96, 0)]


# ------------------------------------------------------------------ curves
def periodic(keys, period):
    """A smooth closed curve through (tick, value) keys (Catmull-Rom over the period), evaluated at any real tick."""
    ks = sorted(keys.items())

    def at(t):
        t %= period
        n = len(ks)
        i = max(k for k in range(n) if ks[k][0] <= t) if t >= ks[0][0] else n - 1
        t0, p1 = ks[i]
        t1, p2 = ks[(i + 1) % n]
        _, p0 = ks[(i - 1) % n]
        _, p3 = ks[(i + 2) % n]
        span = (t1 - t0) % period or period
        u = ((t - t0) % period) / span
        return .5 * (2 * p1 + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u
                     + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3)
    return at


def eased(keys):
    """Piecewise cosine-eased steps through (tick, value) keys: holds stay flat, each move eases in and out."""
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
    def __init__(self, old):
        idle, _, _ = animsheet.slot_frames(old, NB, 0)
        mean = [[round(sum(f[b][i] for f in idle[:-1]) / (len(idle) - 1)) for i in range(9)] for b in range(NB)]
        rest = copy.deepcopy(mean)
        for b in (CANDLE, CUP, STEM):
            rest[b][5] = 0                     # the native idle rocks the candle sideways; the rest stands straight
        rest[FLAME][3:6] = [round(20 * DEG), 0, 0]
        rest[FOOT] = list(idle[0][FOOT])
        rest[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
        self.rest = rest
        self.foot = [v[:3] for v in old.tmd.obj_verts(10)]
        self.old = old

    def bottom(self, rx):
        """The lowest point of the foot (y down) with the foot pitched by rx."""
        R = mmd.rot_matrix(rx, 0, 0)
        return max(R[1][0] * x + R[1][1] * y + R[1][2] * z for x, y, z in self.foot)

    def pose(self, squash=0., lean=0., lift=0., flame=(0., 0., 0.), flame_y=1., arms=(0., 0., 0.), look=0.,
             sway=0., lag_lean=(0., 0.)):
        p = copy.deepcopy(self.rest)
        rx = round(lean * DEG)
        p[FOOT][3] = rx
        p[FOOT][7] = round(-lift - self.bottom(rx))
        # squash: the stem sinks into the foot, the cup and the candle settle, the candle widens and shortens
        p[STEM][7] = round(self.rest[STEM][7] + 9 * squash)
        p[CUP][7] = round(self.rest[CUP][7] + 5 * squash)
        p[CANDLE][7] = round(self.rest[CANDLE][7] + 2 * squash)
        p[CANDLE][1] = round(4096 * (1 - .09 * squash))
        p[CANDLE][0] = p[CANDLE][2] = round(4096 * (1 + .045 * squash))
        # the upper body follows the foot's pitch late
        p[STEM][3] += round(lag_lean[0] * DEG)
        p[CANDLE][3] += round(lag_lean[1] * DEG)
        p[CANDLE][4] += round(look * DEG)
        p[CANDLE][5] += round(sway * DEG)
        p[STEM][5] += round(-.6 * sway * DEG)
        # the flame
        p[FLAME][3] += round(flame[0] * DEG)
        p[FLAME][4] += round(flame[1] * DEG)
        p[FLAME][5] += round(flame[2] * DEG)
        p[FLAME][1] = round(self.rest[FLAME][1] * flame_y)
        # the arms: (shoulder lift, forearm, hand), spread sideways with the lift
        up, fore, hand = arms
        for (s, f, h, side) in ARMS:
            p[s][3] += round(-up * DEG)
            p[s][5] += round(side * .5 * up * DEG)
            p[f][3] += round(-fore * DEG)
            p[h][3] += round(-hand * DEG)
        return p


# ------------------------------------------------------------------ the clips
def gait(rig, slot):
    g = GAITS[slot]
    P, hops, c = g['period'], g['hops'], g['contact']
    n = P * hops
    squash, lean, arms = periodic(g['squash'], P), periodic(g['lean'], P), periodic(g['arms'], P)
    hop = g['speed'] * P
    f = P - c

    def height(t):
        tau = t % P
        if tau <= c:
            return 0.
        s = (tau - c) / f
        return 4 * g['height'] * s * (1 - s)

    def foot_z(t):
        """Travel of the foot (units forward): still while down, a slightly eased glide in the air."""
        k, tau = divmod(t, P)
        if tau <= c:
            return k * hop
        s = (tau - c) / f
        return k * hop + hop * (.8 * s + .2 * (3 * s * s - 2 * s ** 3))

    mean_foot = sum(foot_z(t) - g['speed'] * t for t in range(P)) / P

    def root_z(t):
        """The root: half the foot's own travel, half a steady line; the same mean, so the foot stays near the root."""
        return .5 * (foot_z(t) - mean_foot) + .5 * g['speed'] * t

    frames, plan = [], []
    flicker = lambda t, a, b: a * wave(hops * 2 + 1, n, t, .1) + b * wave(hops * 3 + 2, n, t, .4)
    for t in range(n + 1):
        tt = t % n
        tau = tt % P
        lift = height(tt)
        rise = (height(tt) - height(tt - 1)) / max(1., 4 * g['height'] / f)        # -1..1, up positive
        rise_late = (height(tt - 1) - height(tt - 2)) / max(1., 4 * g['height'] / f)
        L = g['base_lean'] + lean(tau)
        flame_x = g['flame'] - g['flame_rise'] * rise_late + 2.5 * flicker(tt, 1, .6)
        flame_y = g.get('flame_shrink', 1.) * (1 - .07 * rise_late + .02 * flicker(tt, 1, .25))
        a1 = g['arm_base'] + g['arm_swing'] * arms(tau - .5)
        a2 = .6 * g['arm_swing'] * arms(tau - 1.5)
        a3 = .5 * g['arm_swing'] * arms(tau - 2.5)
        pose = rig.pose(squash=squash(tau), lean=L, lift=lift, flame=(flame_x, 0, 3 * flicker(tt, .5, -.8)),
                        flame_y=flame_y, arms=(a1, a2 - .4 * a1, a3),
                        lag_lean=(.45 * (lean(tau - 1) - lean(tau)), .4 * (lean(tau - 2) - lean(tau))),
                        sway=1.2 * wave(hops / 2 if hops % 2 == 0 else hops, n, tt))
        world = -foot_z(t)
        root = -root_z(t)
        pose[0][8] = round(root)
        pose[FOOT][8] = round(world - root) + rig.rest[FOOT][8]
        frames.append([[int(round(x)) for x in v] for v in pose])
        plan.append(dict(t=t, lift=round(lift, 1), foot_z=round(world, 1), root_z=round(root, 1),
                         squash=round(squash(tau), 2)))
    # the face: the per-hop moves, then one blink over a quiet stretch
    eyes, mouth = [], []
    for k in range(hops):
        eyes += [(k * P + t, s) for t, s in g['eyes']]
        mouth += [(k * P + t, s) for t, s in g['mouth']]
    blink = face.blink(g['blink'], slow=slot == 3, rest=g['eye0'])
    eyes = [e for e in eyes if not g['blink'] - 1 <= e[0] <= blink[-1][0] + 1] + blink
    eyes.sort()
    if eyes and eyes[-1][1] != g['eye0']:
        eyes.append((n - 1, g['eye0']))
    if mouth and mouth[-1][1] != g['mouth0']:
        mouth.append((n - 1, g['mouth0']))
    events = face.events(eyes, mouth, n, g['eye0'], g['mouth0'])
    return frames, events, plan


def idle(rig):
    n = IDLE_TICKS
    look = eased(IDLE_LOOK)
    frames = []
    for t in range(n + 1):
        tt = t % n
        breath = .5 - .5 * math.cos(2 * math.pi * 4 * tt / n)                # 0..1, four breaths
        fl = lambda a, b, c_: a * wave(11, n, tt, .1) + b * wave(17, n, tt, .35) + c_ * wave(23, n, tt, .7)
        pose = rig.pose(squash=.3 * breath - .1, lean=.8 * wave(2, n, tt, .25),
                        flame=(3 * fl(1, .6, .3), 4 * fl(.3, .8, .5), 4 * fl(.7, -.4, .6)),
                        flame_y=1 + .03 * fl(.8, .4, 0) + .02 * breath,
                        arms=(-6 + 7 * breath + 3 * wave(2, n, tt, .1), 4 * wave(4, n, tt, .3),
                              5 * wave(4, n, tt, .45)),
                        look=look(tt), sway=3 * wave(2, n, tt))
        frames.append([[int(round(x)) for x in v] for v in pose])
    return frames, face.events(IDLE_EYES, IDLE_MOUTH, n)


# ------------------------------------------------------------------ build
def _parse(data, skeleton):
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = len(skeleton)
    model = mmd.MMD.parse(data, len(skeleton))
    model.type = SPECIES
    return model


def author(data, skeleton):
    old = _parse(data, skeleton)
    rig = Rig(old)
    new = copy.deepcopy(old)
    report = []
    for slot in SLOTS:
        if slot == 0:
            frames, events = idle(rig)
            plan = None
        else:
            frames, events, plan = gait(rig, slot)
            _, _, src_events = animsheet.slot_frames(old, NB, slot)
            sound = next(dict(bank=e[2]['bank'], note=e[2]['note']) for e in src_events if e[1] == 'sound')
            g = GAITS[slot]
            events = events + [(k * g['period'], 'sound', dict(sound)) for k in range(g['hops'])]
            events.sort(key=lambda e: e[0])
        mmd.close_loop(frames, 0)
        anim = mmd.encode_anim(frames, NB, 0, events, tol=1)
        index = old.anims.table[slot]
        if slot == 0 or sum(1 for i in old.anims.table if i == index) > 1:
            new.anims.table[slot] = len(new.anims.anims)
            new.anims.anims.append(anim)
        else:
            new.anims.anims[index] = anim
        n = len(frames) - 1
        report.append(dict(slot=slot, ticks=n, root_per_tick=round((frames[0][0][8] - frames[-1][0][8]) / n, 2),
                           tex_moves=sum(1 for e in events if e[1] == 'tex'),
                           sounds=sum(1 for e in events if e[1] == 'sound'), **({} if slot == 0 else dict(
                               hop_ticks=GAITS[slot]['period'], hops=GAITS[slot]['hops'],
                               hop_height=GAITS[slot]['height'], contact_ticks=GAITS[slot]['contact']))))
    for anim in new.anims.anims:
        anim.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    output = new.build()
    actual = _parse(output, skeleton)
    assert actual.tmd.build() == old.tmd.build()
    assert changed_programs(old, actual) == list(SLOTS), changed_programs(old, actual)
    return output, report


def build(data, tex, skeleton):
    if (hashlib.sha256(data).hexdigest() != SOURCE or hashlib.sha256(tex).hexdigest() != TEX_SOURCE
            or [b[1] for b in skeleton] != PARENTS or [b[0] for b in skeleton] != list(range(-1, 11))):
        raise ValueError('Candlemon needs the reviewed twelve-bone model and texture it had before this change')
    output, report = author(data, skeleton)
    tim = mmd.Tim4(tex)
    face.stamp(tim)
    new_tex = tim.to_bytes()
    assert len(new_tex) == len(tex)
    return output, new_tex, dict(species=SPECIES, source_sha256=SOURCE,
                                 output_sha256=hashlib.sha256(output).hexdigest(),
                                 changed_slots=list(SLOTS), clips=report, storage=motionstorage.require(output, NB))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--tex', type=Path, required=True)
    p.add_argument('--out-dir', type=Path, required=True)
    a = p.parse_args()
    skeleton = [(i - 1, parent) for i, parent in enumerate(PARENTS)]
    data, tex, proof = build(a.source.read_bytes(), a.tex.read_bytes(), skeleton)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    (a.out_dir / '235.MMD').write_bytes(data)
    (a.out_dir / '235.TIM').write_bytes(tex)
    print(json.dumps(proof, indent=1, default=str))


if __name__ == '__main__':
    main()
