"""RedOtamamon's (species 233) field clips: a living idle, a claw-pull crawl, a heavy tired crawl and a bounding run.

Offline authoring script (the model it makes is stored with `tools/models/edit.py put 233 MMD`, like Salamon's).
The previous model played one shared pose loop in all four clips (only the travel speed differed). The creature is a
tadpole: a big head-body on two short claw arms, two stub feet under the rear, a tail with a fin. Every clip is built here
from the rest pose, with the two claws solved by a two-bone chain so that a claw on the ground does not slide:

  idle   96 ticks, no travel: breathing (4 breaths), a slow look to one side and then the other, the tail wagging twice,
         a claw tapping the ground now and then, the stub feet shifting
  walk   16 ticks, 20 units a tick: the claws pull in turn (right 0-5, left 8-13) and the body glides between pulls, rolling
         toward the planted claw, nose dipping, tail counter-swinging
  tired  22 ticks, 13 units a tick: a low, slow crawl, the head and tail drooping, short claw strokes, the claws dragging
  run    10 ticks, 38 units a tick: a quick bound, the claws pull in turn for under 3 ticks and the body leaves the ground
         between pulls, a strong nose pitch, the tail streaming up and behind, the claws reaching forward

The native Otamamon's clips were not reused: its rig has 15 bones with another hierarchy and local axes (its body and pelvis
are siblings under a rotated pivot), and it slides on its belly with the feet dragging. Only the claws plant here.

The eyes blink through texture moves (redotamamon_face.py): the idle blinks four times, the walk once a stride, the tired
walk keeps its lids heavy with slow blinks, the run squints. Every clip sets its first face at tick 0.

    python tools/models/field_animations/redotamamon.py --source SRC.MMD --tex SRC.TIM --out-dir DIR
where SRC is the previously stored model and texture (sha256 below).
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
import legik  # noqa: E402
import mmd  # noqa: E402
import motionstorage  # noqa: E402
import retarget as rt  # noqa: E402
from tools.models.field_animations import redotamamon_face as face  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402

SPECIES = 233
SOURCE = '8f56afec7dc4e13c852b2b44c0a7fe485c5b0ffb72e88edd11a0c7cb1fdb80f9'      # the previous model
TEX_SOURCE = '27fccfb458a433bf69d2c723cfeb66381d926e882837bb17fdd41e1802a4bfb5'  # its texture
PARENTS = [-1, 6, 1, 2, 1, 4, 0, 6, 7, 8, 6, 10, 6, 12]
BODY, PELVIS = 1, 6
ARMS = {'R': (2, 3, 1), 'L': (4, 5, -1)}          # shoulder bone, claw bone, side (+1 = x > 0)
TAIL = (7, 8, 9)
FEET = {'R': (10, 11), 'L': (12, 13)}
SLOTS = (0, 2, 3, 4)
FLOOR = -82.0                                     # the claw tips' resting level (the model's own ground)
BELLY = -90.0                                     # the lowest the body may hang: a little above the claws' ground
BODY_BONES = (1, 6, 7, 8, 9, 10, 11, 12, 13)

# --- small matrix helpers (rows; x right, y down, z toward the tail; the creature faces -z) ---


def rx(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def ry(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def rz(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def mul(*ms):
    out = ms[0]
    for m in ms[1:]:
        out = rt.m3mul(out, m)
    return out


def apply(m, v):
    return [sum(m[i][j] * v[j] for j in range(3)) for i in range(3)]


def smooth(x):
    x = max(0., min(1., x))
    return x * x * (3 - 2 * x)


def wave(phase):
    return math.sin(2 * math.pi * phase)


def hold(t, keys):
    """Smooth interpolation through (tick, value) keys (a cubic ease between each pair; flat tangents)."""
    for (a, x), (b, y) in zip(keys, keys[1:]):
        if a <= t <= b:
            return x + (y - x) * smooth((t - a) / (b - a))
    return keys[-1][1]


def _dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


# --- the rig ---


class Rig:
    def __init__(self, old, skeleton):
        self.skel = skeleton
        self.n = len(skeleton)
        self.model = old
        pose = animsheet.slot_frames(old, self.n, 0)[0][0]
        self.rest = [list(b) for b in pose]
        self.rest[0] = [4096] * 3 + [0] * 6
        self.rest_w, self.rest_p = rt.world_transform(skeleton, self.rest)
        self.rest_local = [rt.rot_of(v) for v in self.rest]
        self.offset = [v[6:9] for v in self.rest]
        self.arm = {}
        self.stretch = 0.          # the most any claw target lay beyond the arm's reach
        for name, (sh, cl, side) in ARMS.items():
            verts = [v[:3] for v in old.tmd.obj_verts(skeleton[cl][0])]
            world = [[sum(self.rest_w[cl][i][j] * v[j] for j in range(3)) + self.rest_p[cl][i] for i in range(3)] for v in verts]
            tip = max(world, key=lambda p: _dist(p, self.rest_p[cl]))
            self.arm[name] = dict(sh=sh, cl=cl, side=side, L1=_dist(self.rest_p[cl], self.rest_p[sh]),
                                  L2=_dist(tip, self.rest_p[cl]), tip=tip)

    def pose(self, body, tail, feet, claws, prev):
        """One full pose. body: {'dy','dz','dx', 'pitch','roll','yaw' (pelvis, degrees), 'head': (pitch, yaw, roll)},
        tail: [(pitch, yaw)] per tail bone, feet: {'R': (hip, foot), 'L': ...} in degrees (pitch), claws: {'R': (x, y, z) or None,
        ...} tip targets in the root frame (None keeps the rest orientation of the claw)."""
        sk, rest = self.skel, self.rest
        pose = [list(v) for v in rest]
        local = [list(m) for m in self.rest_local]

        def turn(b, d):
            local[b] = mul(d, self.rest_local[b])
        turn(PELVIS, mul(ry(body.get('yaw', 0)), rx(-body.get('pitch', 0)), rz(body.get('roll', 0))))
        pitch, yaw, roll = body.get('head', (0, 0, 0))
        turn(BODY, mul(ry(yaw), rx(-pitch), rz(roll)))
        for b, (p, y) in zip(TAIL, tail):
            turn(b, mul(ry(y), rx(-p)))
        for name, (hip, foot) in feet.items():
            a, c = FEET[name]
            turn(a, rx(hip))
            turn(c, rx(foot))
        move = [body.get('dx', 0), body.get('dy', 0), body.get('dz', 0)]
        pose[PELVIS][6:9] = [self.offset[PELVIS][i] + move[i] for i in range(3)]
        # the claws: world transforms of the parents first, then the chain solved to the target
        for name, target in claws.items():
            if target is None:
                continue
            a = self.arm[name]
            W, P = self._world(local, pose)
            par = W[sk[a['sh']][1]]
            sh = P[a['sh']]
            wrist, tip = self._chain(a, sh, target)
            Wu = mul(rt.swing([self.rest_p[a['cl']][i] - self.rest_p[a['sh']][i] for i in range(3)],
                              [wrist[i] - sh[i] for i in range(3)]), self.rest_w[a['sh']])
            Wl = mul(rt.swing([a['tip'][i] - self.rest_p[a['cl']][i] for i in range(3)],
                              [tip[i] - wrist[i] for i in range(3)]), self.rest_w[a['cl']])
            local[a['sh']] = mul(rt.m3t(par), Wu)
            local[a['cl']] = mul(rt.m3t(Wu), Wl)
            self.stretch = max(self.stretch, _dist(sh, target) - (a['L1'] + a['L2']))
        for b in range(1, self.n):
            e = mmd.matrix_euler(local[b], prev.get(b))
            prev[b] = e
            pose[b][3:6] = list(e)
        return pose

    @staticmethod
    def _world(local, pose):
        W, P = [None] * len(local), [None] * len(local)

        def get(b):
            if W[b] is not None:
                return
            if PARENTS[b] < 0:
                W[b], P[b] = local[b], [0, 0, 0]
                return
            get(PARENTS[b])
            pw, pp, v = W[PARENTS[b]], P[PARENTS[b]], pose[b]
            W[b] = rt.m3mul(pw, local[b])
            P[b] = [sum(pw[i][j] * v[6 + j] for j in range(3)) + pp[i] for i in range(3)]
        for b in range(len(local)):
            get(b)
        return W, P

    def lowest(self, pose, bones):
        """The lowest (largest y) vertex of the given bones' meshes."""
        mats = mmd.bone_matrices(self.model, pose)
        low = -1e9
        for b in bones:
            M = mats[b]
            for x, y, z, _ in self.model.tmd.obj_verts(self.skel[b][0]):
                low = max(low, M[1][0] * x + M[1][1] * y + M[1][2] * z + M[1][3])
        return low

    def settle(self, body, tail, feet, claws, prev, belly=BELLY, plane=FLOOR):
        """The pose, with the body lifted until nothing but the claws is under `belly`, and each claw target raised until
        its mesh does not sink under `plane` (the claw tips are solved as points; the prongs hang below them)."""
        body = dict(body)
        claws = {k: (list(v) if v else v) for k, v in claws.items()}
        for _ in range(2):
            pose = self.pose(body, tail, feet, claws, dict(prev))
            body['dy'] = body.get('dy', 0) - max(0., self.lowest(pose, BODY_BONES) - belly)
            for name, target in claws.items():
                if target is not None:
                    cl = ARMS[name][1]
                    target[1] -= max(0., self.lowest(pose, [cl]) - plane)
        pose = self.pose(body, tail, feet, claws, prev)
        return pose

    def _chain(self, a, shoulder, target):
        """Wrist and tip of a two-bone arm from the shoulder reaching `target`, the elbow up and outward."""
        pole = [a['side'] * 0.6, -1.0, -0.2]
        wrist, tip = legik.solve(shoulder, target, a['L1'], a['L2'], pole)
        return wrist, tip


# --- the clips ---

EASE = smooth


def _claw_path(phase, td, stance, v, ticks, front, lateral, floor, lift, back_swing=0.):
    """Tip target in the root frame for a claw that lands at phase `td` (fraction of the cycle) and stays down `stance`
    ticks while the body travels `v` units a tick. Returns (x, y, z, down?)."""
    t = ((phase - td) % 1.0) * ticks
    if t < stance:                                   # planted: the claw slides back along the body at the body's speed
        z = front + v * t
        return lateral, floor, z, True
    stroke = v * stance
    u = (t - stance) / (ticks - stance)             # swing back to the front of the stroke
    e = EASE(u)
    z = (front + stroke) + (front - (front + stroke) - back_swing * math.sin(math.pi * u)) * e
    y = floor - lift * math.sin(math.pi * u) ** 0.8
    x = lateral + 0.0 * u
    return x, y, z, False


GAITS = {
    2: dict(name='walk', ticks=16, speed=20.0, stance=5.0, td={'R': 0.0, 'L': 0.5}, front=-140.0, lateral=128.0, lift=34.0,
            drop=16.0, bob=3.0, roll=3.5, yaw=4.0, pitch=2.0, pitch_bob=2.5, head=(2.5, 3.0, 2.0), tail_yaw=16.0, tail_pitch=-3.0,
            tail_wave=2, foot=9.0, tail_lag=0.07),
    3: dict(name='condition walk', ticks=22, speed=13.0, stance=7.0, td={'R': 0.0, 'L': 0.5}, front=-130.0, lateral=122.0, lift=14.0,
            drop=30.0, bob=1.2, roll=2.0, yaw=2.5, pitch=-6.0, pitch_bob=1.2, head=(-14.0, 1.5, 3.5), tail_yaw=6.0, tail_pitch=32.0,
            tail_wave=1, foot=4.0, tail_lag=0.12),
    4: dict(name='run', ticks=10, speed=38.0, stance=2.8, td={'R': 0.0, 'L': 0.5}, front=-148.0, lateral=132.0, lift=44.0,
            drop=2.0, bob=15.0, roll=3.0, yaw=3.5, pitch=-2.0, pitch_bob=11.0, head=(-8.0, 2.0, 2.0), tail_yaw=10.0, tail_pitch=-22.0,
            tail_wave=2, foot=14.0, tail_lag=0.05),
}


def gait(rig, cfg):
    ticks, v = cfg['ticks'], cfg['speed']
    prev = {}
    frames = []
    worst = 0.
    for t in range(ticks):
        ph = t / ticks
        gp = {}
        claws, down = {}, {}
        for name in ARMS:
            x, y, z, d = _claw_path(ph, cfg['td'][name], cfg['stance'], v, ticks, cfg['front'], ARMS[name][2] * cfg['lateral'],
                                    FLOOR, cfg['lift'])
            claws[name], down[name] = [x, y, z], d
        stepping = wave(ph * 2)                       # one step of the cycle: right pull to left pull
        body = dict(
            dy=cfg['drop'] - cfg['bob'] * math.cos(2 * math.pi * ph * 2 + 0.6) ,
            dx=-2.0 * stepping,
            yaw=cfg['yaw'] * stepping,
            roll=-cfg['roll'] * stepping,
            pitch=cfg['pitch'] + cfg['pitch_bob'] * math.cos(2 * math.pi * ph * 2 + 2.6),
            head=(cfg['head'][0] + 1.5 * math.cos(2 * math.pi * ph * 2 - 0.8), cfg['head'][1] * -stepping, cfg['head'][2] * stepping))
        tail = []
        for i, b in enumerate(TAIL):
            lag = cfg['tail_lag'] * (i + 1)
            tail.append((cfg['tail_pitch'] * (0.5 + 0.25 * i) * (0.6 + 0.4 * math.cos(2 * math.pi * (ph * 2 - lag))),
                         -cfg['tail_yaw'] * (0.6 + 0.5 * i) * wave(ph * cfg['tail_wave'] - lag)))
        feet = {}
        for name in ARMS:
            opp = 'L' if name == 'R' else 'R'
            q = ((ph - cfg['td'][name]) % 1.0)
            feet[name] = (cfg['foot'] * wave(q), cfg['foot'] * 1.4 * wave(q - 0.12))
        pose = rig.settle(body, tail, feet, claws, prev)
        pose[0][8] = -v * t
        frames.append(pose)
    closing = [list(b) for b in frames[0]]
    closing[0][8] = -v * ticks
    frames.append(closing)
    return frames


def idle(rig, ticks=96):
    prev = {}
    frames = []
    for t in range(ticks):
        ph = t / ticks
        breath = wave(ph * 4)
        look = hold(t, [(0, 0), (14, 0), (26, 1), (38, 1), (52, -1), (64, -1), (80, 0), (96, 0)])
        tap = lambda start, n: (math.sin(math.pi * (t - start) / n) ** 2 if start <= t < start + n else 0.)
        wag = wave(ph * 2 - 0.1)
        body = dict(dy=1.8 * breath, pitch=1.2 * breath - 0.8, roll=0.6 * wave(ph * 2 + 0.25),
                    yaw=3.0 * look, head=(1.4 * wave(ph * 4 - 0.15) + 1.5 * hold(t, [(0, 0), (30, 0), (34, 2.5), (40, 2.5), (48, 0), (96, 0)]),
                                          9.0 * look, 2.0 * look))
        tail = [(2 + 2 * wave(ph * 4 - 0.2 * i), -(7 + 5 * i) * wag * (0.6 + 0.2 * i)) for i in range(3)]
        feet = {'R': (3 * wave(ph * 2), 5 * wave(ph * 2 - 0.1) + 4 * tap(60, 10)), 'L': (3 * wave(ph * 2 + 0.5), 5 * wave(ph * 2 + 0.4) + 4 * tap(10, 10))}
        claws = {}
        for name, (sh, cl, side) in ARMS.items():
            a = rig.arm[name]
            rest = [rig.rest_p[cl][i] for i in range(3)]
            tip = list(a['tip'])
            tip[0] -= side * 14          # a little inside the rest tip: the rest arm is fully stretched
            tip[2] += 12
            lift = {'R': tap(20, 12), 'L': tap(72, 12)}[name]
            tip[1] -= 20 * lift
            tip[2] += 10 * lift
            tip[0] -= side * 6 * lift
            claws[name] = tip
        pose = rig.settle(body, tail, feet, claws, prev)
        frames.append(pose)
    closing = [list(b) for b in frames[0]]
    frames.append(closing)
    return frames


# The eye's plan per clip: (tick, state) changes inside the clip, ending in its first face, so a loop closes and a clip
# left mid-blink is repaired by the next clip's tick 0.
FACE = {0: face.blink(10) + face.blink(44) + face.blink(50) + face.blink(80),
        2: face.blink(6),
        3: [(2, face.HALF), (8, face.SHUT), (11, face.HALF), (19, face.OPEN)],
        4: [(1, face.HALF), (8, face.OPEN)]}


def build(data, tex):
    if hashlib.sha256(tex).hexdigest() != TEX_SOURCE:
        raise ValueError('RedOtamamon\'s eyes require the reviewed texture')
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('RedOtamamon\'s gaits require the reviewed source')
    skeleton = [tuple(b) for b in json.loads((ROOT / 'content/species/233-redotamamon.json').read_text())['model']['skeleton']]
    n = len(skeleton)
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = n
    old = mmd.MMD.parse(data, n)
    old.type = SPECIES
    rig = Rig(old, skeleton)
    new = copy.deepcopy(old)
    out, reach = {}, {}
    for slot, make in [(0, idle)] + [(s, lambda r, c=c: gait(r, c)) for s, c in GAITS.items()]:
        rig.stretch = 0.
        out[slot] = make(rig)
        reach[slot] = round(rig.stretch, 2)
    changed = set()
    for slot, frames in out.items():
        frames = [[[round(x) for x in b] for b in pose] for pose in frames]
        animation = mmd.encode_anim(frames, n, loop_sample=0, events=face.events(FACE[slot], len(frames) - 1), tol=1)
        index = old.anims.table[slot]
        new.anims.anims[index] = animation
        changed |= {s for s, i in enumerate(old.anims.table) if i == index}
    result = new.build()
    actual = mmd.MMD.parse(result, n)
    actual.type = SPECIES
    assert old.tmd.build() == actual.tmd.build()
    assert changed_programs(old, actual) == sorted(changed), (changed_programs(old, actual), sorted(changed))
    storage = motionstorage.require(result, n)
    tim = mmd.Tim4(tex)
    face.stamp(tim)
    new_tex = tim.to_bytes()
    assert len(new_tex) == len(tex)
    return result, new_tex, dict(species=SPECIES, changed_slots=sorted(changed), storage=storage, unreached=reach,
                        output_sha256=hashlib.sha256(result).hexdigest())


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--tex', type=Path, required=True)
    p.add_argument('--out-dir', type=Path, required=True)
    a = p.parse_args()
    data, tex, proof = build(a.source.read_bytes(), a.tex.read_bytes())
    a.out_dir.mkdir(parents=True, exist_ok=True)
    (a.out_dir / '233-RedOtamamon.MMD').write_bytes(data)
    (a.out_dir / '233-RedOtamamon.TIM').write_bytes(tex)
    print(json.dumps(proof, indent=2, default=str))


if __name__ == '__main__':
    main()
