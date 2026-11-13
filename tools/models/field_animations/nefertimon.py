"""Nefertimon's feline walk, run and standing idle, written from the paws up.

Nefertimon (198) is a sphinx-cat: short shoulder plates, gauntleted forearms ending in big flat paws, and hind legs
whose last bone is the whole hind foot. The imported walk and run slid both forearms flat along the floor. This
recipe writes them again as a cat moves:

- Each leg has a stance and a swing per cycle. In stance the paw stands on the floor and stays put in the world while
  the body passes over it; in its last part the heel peels and the paw rolls onto its toes. In swing the leg lifts,
  the wrist (or the hind foot) curls back under it, reaches forward and flattens again just before it lands.
- The run is a rotary gallop (left hind, right hind, right fore, left fore) with a short gathered flight after the
  forelegs push off; the walk is the lateral sequence of a walking cat (left hind, left fore, right hind, right fore).
- Two-bone solves keep the bend plane the leg has in the idle (elbows back, knees forward), so the gauntlet keeps
  its roll; a front paw never bends back from its forearm further than the gauntlet allows (it stays seated).
- The pelvis and chest bob and pitch with the footfalls (the spine gathers in the flight, stretches when the hind
  legs push), the head steadies against them, and the wings and tail follow a few ticks late.
- The idle keeps the imported body, head, wings and tail; its forelegs stand on the floor through the breathing
  instead of riding along with it, the weight drifts between them and one forepaw is lifted and set down again.

The walk is slot 2 (also 0x1B and 0x23), the run slot 4 (also the battle movement 0x24), the idle slot 0 (also the
battle idle 0x21): each is rewritten where it is stored, so its aliases play it too. The condition walk (slot 3) is
the field pace pass's: this walk played 1.5 times slower at 2/3 of its speed (content/models/imports/pace.json).
The build refuses any other source, a paw or foot under the floor, a sole that slides in stance, an open loop, a
speed outside the native range, another changed program or the storage budget.
"""
import copy
import hashlib
import math

import animsheet
import mmd
import motionstorage
from motiondiscidentity import changed_programs

SPECIES = 198
SOURCE = '3b99a5f920b7dd4e473d2314ebad55c5b185d6687b4a3ab6884c8c1afa98cae9'
PARENTS = [-1, 10, 1, 2, 1, 4, 5, 1, 7, 8, 0, 10, 11, 12, 10, 14, 15, 1, 1, 10, 19, 20, 21, 22]
PELVIS, CHEST, NECK, HEAD = 10, 1, 2, 3
WINGS = (17, 18)
TAIL = (19, 20, 21, 22, 23)
DEG = 4096 / 360

# (upper, lower, paw, side (+1 right), front)
LEGS = {'RF': (4, 5, 6, 1, True), 'LF': (7, 8, 9, -1, True), 'RH': (11, 12, 13, 1, False), 'LH': (14, 15, 16, -1, False)}
MIRROR = {'LF': 'RF', 'LH': 'RH'}
POLE = {True: [0.6, -0.4, 1], False: [0.3, 0.3, -1]}   # elbow / knee side of the shoulder-paw line (y down, z back)

# One row per field clip: cycle ticks, speed (units per tick), the touchdown phase and duty factor of each leg,
# paw lift, body bob and pitch, how far the heel peels, and the paw's curl in swing.
GAITS = {
    4: dict(name='run', ticks=15, speed=41,
            touchdown={'LH': 0.0, 'RH': 0.1, 'RF': 0.42, 'LF': 0.54},
            duty={'LH': 0.36, 'RH': 0.36, 'RF': 0.36, 'LF': 0.36},
            lift={'front': 40, 'hind': 34}, curl={'front': 45, 'hind': 50}, peel={'front': 40, 'hind': 40},
            reach={'front': 5, 'hind': 45}, out={'front': 55, 'hind': 10}, snap=True,
            height=28, tilt=0, chest_up=-4, neck=6, bob=8, pitch=6, flex=8, slip=0.1, head=0.6, wing=10, tail=9),
    2: dict(name='walk', ticks=16, speed=18,
            touchdown={'LH': 0.0, 'LF': 0.25, 'RH': 0.5, 'RF': 0.75},
            duty={'LH': 0.62, 'RH': 0.62, 'RF': 0.62, 'LF': 0.62},
            lift={'front': 30, 'hind': 32}, curl={'front': 35, 'hind': 30}, peel={'front': 30, 'hind': 20},
            reach={'front': 5, 'hind': 30}, out={'front': 30, 'hind': 5}, snap=False,
            height=22, tilt=0, chest_up=-2, neck=4, bob=2.5, pitch=1.2, flex=1.5, slip=0.1, head=0.5, wing=2, tail=5),
}


# ------------------------------------------------------------------ small linear algebra (lists, no numpy)
def mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def tr(a):
    return [list(r) for r in zip(*a)]


def mv(a, v):
    return [sum(a[i][k] * v[k] for k in range(3)) for i in range(3)]


def add(a, b):
    return [x + y for x, y in zip(a, b)]


def sub(a, b):
    return [x - y for x, y in zip(a, b)]


def scale(a, k):
    return [x * k for x in a]


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def norm(a):
    return math.sqrt(dot(a, a))


def unit(a):
    n = norm(a)
    return [x / n for x in a]


def rx(deg):
    return mmd.rot_matrix(deg * DEG, 0, 0)


def rot(deg):
    return mmd.rot_matrix(*[d * DEG for d in deg])


def frame(u, n):
    """Columns: u, n (made orthogonal to u), u x n."""
    u = unit(u)
    n = unit(sub(n, scale(u, dot(n, u))))
    w = cross(u, n)
    return [[u[i], n[i], w[i]] for i in range(3)]


def to_quat(m):
    t = m[0][0] + m[1][1] + m[2][2]
    if t > 0:
        s = math.sqrt(t + 1) * 2
        return ((m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s, s / 4)
    i = max(range(3), key=lambda k: m[k][k])
    j, k = (i + 1) % 3, (i + 2) % 3
    s = math.sqrt(1 + m[i][i] - m[j][j] - m[k][k]) * 2
    q = [0, 0, 0, 0]
    q[i] = s / 4
    q[j] = (m[j][i] + m[i][j]) / s
    q[k] = (m[k][i] + m[i][k]) / s
    q[3] = (m[k][j] - m[j][k]) / s
    return tuple(q)


def slerp(a, b, u):
    return mmd.quat_matrix(mmd._slerp(to_quat(a), to_quat(b), max(0.0, min(1.0, u))))


def smooth(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def wave(phase, delay=0.0, rate=1):
    return math.cos(2 * math.pi * rate * (phase - delay))


# ------------------------------------------------------------------ the rig
class Rig:
    def __init__(self, model, skeleton):
        self.m = model
        self.sk = skeleton
        self.n = len(skeleton)
        idle = animsheet.slot_frames(model, self.n, 0)[0]
        self.idle = idle
        self.rest = [list(v) for v in idle[0]]
        self.verts = {b: [v[:3] for v in model.tmd.obj_verts(o)] for b, (o, _) in enumerate(skeleton) if o >= 0}
        # The right legs' idle shapes (mirrored for the left) are the reference bend planes and twists.
        self.ref = {}
        for name, (up, lo, paw, side, front) in LEGS.items():
            src = LEGS[MIRROR.get(name, name)]
            locs = [self.rest[b][3:6] for b in src[:3]]
            if side < 0:
                locs = [[a, -b, -c] for a, b, c in locs]
            self.ref[name] = [mmd.rot_matrix(*v) for v in locs]

    def world(self, pose):
        p = [list(v) for v in pose]
        p[0] = [4096, 4096, 4096] + p[0][3:6] + [0, 0, 0]
        return mmd.bone_matrices(self.m, p)

    def lowest(self, b, rot_, origin):
        """Lowest point (largest y) of bone b's mesh at a world rotation and origin."""
        return max(origin[1] + dot(rot_[1], v) for v in self.verts[b])

    def solve(self, pose, name, wrist, hist, pole=None, ref=None):
        """Two-bone solve of a leg for its wrist (ankle) position, in the leg's idle bend plane (elbows back, knees
        forward, the gauntlet's roll kept). Returns the forearm's world rotation and how far the target was out of
        reach."""
        up, lo, paw, side, front = LEGS[name]
        W = self.world(pose)
        parent = [r[:3] for r in W[self.sk[up][1]][:3]]
        shoulder = [W[up][i][3] for i in range(3)]
        a = [pose[lo][6], pose[lo][7], pose[lo][8]]
        b = [pose[paw][6], pose[paw][7], pose[paw][8]]
        ref = ref or self.ref[name]
        ru0 = mul(parent, ref[0])
        rl0 = mul(ru0, ref[1])
        e0 = add(shoulder, mv(ru0, a))
        w0 = add(e0, mv(rl0, b))
        la, lb = norm(a), norm(b)
        d = sub(wrist, shoulder)
        dist = norm(d)
        reach = max(abs(la - lb) + 2, min(la + lb - 2, dist))
        d = scale(unit(d), reach)
        pole = pole or mv(parent, [POLE[front][0] * side] + POLE[front][1:])   # elbows back, knees forward, both out
        pole = unit(sub(pole, scale(unit(d), dot(pole, unit(d)))))
        along = (la * la - lb * lb + reach * reach) / (2 * reach)
        h = math.sqrt(max(0.0, la * la - along * along))
        elbow = add(shoulder, add(scale(unit(d), along), scale(pole, h)))
        wr = add(shoulder, d)
        if front:   # the gauntlet keeps its roll in the bend plane
            n0 = cross(sub(e0, shoulder), sub(w0, e0))
            n1 = cross(sub(elbow, shoulder), sub(wr, elbow))
            ru = mul(mul(frame(sub(elbow, shoulder), n1), tr(frame(sub(e0, shoulder), n0))), ru0)
            rl = mul(mul(frame(sub(wr, elbow), n1), tr(frame(sub(w0, e0), n0))), rl0)
        else:       # the hind leg only swings from its reference: no twist about the thigh or the shin
            ru = mul(turn_to(sub(e0, shoulder), sub(elbow, shoulder)), ru0)
            rl = mul(turn_to(mv(mul(ru, ref[1]), b), sub(wr, elbow)), mul(ru, ref[1]))
        set_rot(pose, up, mul(tr(parent), ru), hist)
        set_rot(pose, lo, mul(tr(ru), rl), hist)
        return rl, dist - reach

    def bend(self, name, forearm, paw_world):
        """Pitch of the paw against its forearm, from the idle's own bend; + = the toes curl down and back."""
        return pitch_of(mul(tr(self.ref[name][2]), mul(tr(forearm), paw_world)))


def pitch_of(m):
    """Angle about x of a rotation (its x axis assumed near x), degrees, + = forward axis (-z) turned down (+y)."""
    fwd = [-m[0][2], -m[1][2], -m[2][2]]
    return math.degrees(math.atan2(fwd[1], -fwd[2]))


def turn_to(a, b):
    """Shortest rotation taking direction a to direction b."""
    a, b = unit(a), unit(b)
    v = cross(a, b)
    c = dot(a, b)
    k = [[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]]
    kk = mul(k, k)
    return [[(1 if i == j else 0) + k[i][j] + kk[i][j] / (1 + c) for j in range(3)] for i in range(3)]


def set_rot(pose, b, m, hist):
    angle = mmd.matrix_euler(m, hist.get(b))
    hist[b] = angle
    pose[b][3:6] = [round(x) for x in angle]


# ------------------------------------------------------------------ walk and run
SOLE = {True: [0, 44, -70], False: [0, 43, -62]}     # the point of the sole a paw rolls about (paw bone space)
REACH = {True: -62, False: -30}   # the sole pivot's place ahead of the shoulder / hip at mid-stance
FOLD = {True: 60, False: 70}   # closest a swinging wrist / hock comes to its shoulder / hip
CLEAR = 1.5              # a standing sole is held this high: a paw rolling on its toes dips between ticks
HIND_TOE = 35            # the hind foot stands on its toes, heel up (degrees), like a cat's
GAUNTLET = (-28, 100)    # how far a front paw may bend from its forearm (from the idle's bend) and stay seated


def standing(rig, name, track, z, world):
    """The wrist (hock) of a paw whose sole pivot stands at z on the floor, at a world rotation."""
    paw = LEGS[name][2]
    wrist = sub([track, 0.0, z], mv(world, SOLE[LEGS[name][4]]))
    wrist[1] = -CLEAR - rig.lowest(paw, world, [0, 0, 0])
    return wrist


def minimum_jerk(v):
    v = max(0.0, min(1.0, v))
    return v * v * v * (10 - 15 * v + 6 * v * v)


def leg_phase(cfg, name, phase):
    u = (phase - cfg['touchdown'][name]) % 1.0
    duty = cfg['duty'][name]
    return (True, u / duty) if u < duty else (False, (u - duty) / (1 - duty))


def swing_paw(cfg, name, s):
    """A swinging paw at swing fraction s: its world pitch, its curl from the forearm and how much it follows the
    forearm (0: the world pitch, rolling on from the lift-off and flat again to land; 1: curled under the forearm).
    The hind foot hangs from the hock in the world: toes trailing down, then flat to land."""
    front = LEGS[name][4]
    key = 'front' if front else 'hind'
    base = 0 if front else HIND_TOE
    peel_end = base + cfg['peel'][key]
    curl = cfg['curl'][key] * math.sin(math.pi * min(1.0, s / 0.85)) if s < 0.85 else 0.0
    if front:
        world = peel_end * (1 - smooth(s / 0.5)) + (base - 6) * smooth((s - 0.6) / 0.35)
        return world, curl, smooth(s / 0.3) * (1 - smooth((s - 0.6) / 0.3))
    hang = peel_end * (1 - smooth(s / 0.35)) + (base + curl) * smooth(s / 0.35)
    return hang * (1 - smooth((s - 0.55) / 0.4)) + (base - 4) * smooth((s - 0.55) / 0.4), curl, 0.0


def body(rig, cfg, phase, pose, hist):
    """Pelvis height and pitch, spine flex, steady head, late wings and tail."""
    rest = rig.rest
    run = cfg['name'] == 'run'
    if run:   # high in the gathered flight, low between the hind and fore stances
        bob = cfg['bob'] * (math.cos(2 * math.pi * (phase - 0.9)) + 0.3 * math.cos(4 * math.pi * (phase - 0.2)))
        flex = cfg['flex'] * wave(phase, 0.95)           # + gathered (back rounds), - stretched
        pitch = cfg['pitch'] * math.sin(2 * math.pi * (phase - 0.35))
        roll = 1.5 * math.sin(2 * math.pi * (phase - 0.2))
        yaw = 1.5 * math.sin(2 * math.pi * (phase - 0.5))
    else:     # two soft dips a cycle, the weight passing from side to side
        bob = cfg['bob'] * math.cos(4 * math.pi * (phase - 0.12))
        flex = cfg['flex'] * math.cos(4 * math.pi * (phase - 0.3))
        pitch = cfg['pitch'] * math.cos(4 * math.pi * (phase - 0.2))
        roll = 2.0 * math.sin(2 * math.pi * (phase - 0.05))
        yaw = 2.5 * math.sin(2 * math.pi * (phase - 0.3))
    pose[PELVIS][7] = rest[PELVIS][7] - cfg['height'] - bob
    set_rot(pose, PELVIS, rot([rest[PELVIS][3] / DEG + cfg['tilt'] + pitch - flex, yaw, roll]), hist)
    base = mmd.rot_matrix(*rest[CHEST][3:6])
    set_rot(pose, CHEST, mul(base, rot([2 * flex - cfg['chest_up'], -yaw * 1.4, -roll * 0.6])), hist)
    head = cfg['head']   # the head keeps most of its gaze while the chest pitches
    pose[NECK][3] = rest[NECK][3] - round((head * 0.5 * (pitch + flex) - cfg['neck']) * DEG)
    pose[HEAD][3] = rest[HEAD][3] - round(head * 0.5 * (pitch + flex) * DEG + (1.5 if run else 1) * wave(phase, 0.1, 2) * DEG)
    pose[HEAD][4] = rest[HEAD][4] + round(yaw * 0.8 * DEG)
    for b, sign in zip(WINGS, (1, -1)):
        pose[b][5] = rest[b][5] + round(sign * cfg['wing'] * wave(phase, 0.12 if run else 0.2, 1 if run else 2) * DEG)
        pose[b][3] = rest[b][3] + round(0.4 * cfg['wing'] * wave(phase, 0.2, 1 if run else 2) * DEG)
    for k, b in enumerate(TAIL):
        lag = 0.08 * (k + 1)
        pose[b][3] = rest[b][3] + round(cfg['tail'] * (0.5 + 0.2 * k) * wave(phase, 0.9 + lag, 1 if run else 2) * DEG)
        pose[b][5] = rest[b][5] + round(cfg['tail'] * 0.6 * math.sin(2 * math.pi * (phase - 0.3 - lag)) * DEG)


def gait(rig, cfg):
    ticks, speed = cfg['ticks'], cfg['speed']
    rest = rig.rest
    still = [list(v) for v in rest]
    still[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
    W = rig.world(still)
    centres, tracks = {}, {}
    for name, (up, lo, paw, side, front) in LEGS.items():
        key = 'front' if front else 'hind'
        ref = LEGS[MIRROR.get(name, name)]
        centres[name] = W[up][2][3] + REACH[front] + cfg['reach'][key]
        tracks[name] = side * abs(W[ref[2]][0][3]) * (0.9 if cfg['name'] == 'run' else 1.0)
    worst = dict(stretch=0.0, clamp=0.0)

    def stand(pose, name, s, hist):
        """Solve a standing leg at stance fraction s (0 = touchdown, 1 = lift-off); how far it stays out of reach."""
        up, lo, paw, side, front = LEGS[name]
        key = 'front' if front else 'hind'
        stride = speed * ticks * cfg['duty'][name] * (1 - cfg['slip'])
        z = centres[name] - stride / 2 + stride * s
        world = rot([(0 if front else HIND_TOE) + cfg['peel'][key] * smooth((s - 0.5) / 0.5), 0, 0])
        forearm, out = rig.solve(pose, name, standing(rig, name, tracks[name], z, world), hist)
        if front:               # the gauntlet stays seated on the paw
            bend = rig.bend(name, forearm, world)
            fix = min(0.0, bend - GAUNTLET[0]) + max(0.0, bend - GAUNTLET[1])
            if abs(fix) > 0.01:
                worst['clamp'] = max(worst['clamp'], abs(fix))
                world = mul(world, rx(-fix))
        set_rot(pose, paw, mul(tr(forearm), world), hist)
        return out

    def body_at(phase, drop, hist):
        pose = [list(v) for v in rest]
        pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, -round(speed * phase * ticks)]
        body(rig, cfg, phase, pose, hist)
        pose[PELVIS][7] += drop
        return pose

    def folded(pose, name, wrist):
        """A swinging wrist (hock) kept FOLD away from its shoulder (hip): a leg folded tighter than that flips its
        knee over."""
        W = rig.world(pose)
        root = [W[LEGS[name][0]][i][3] for i in range(3)]
        d = sub(wrist, root)
        least = FOLD[LEGS[name][4]]
        return wrist if norm(d) >= least else add(root, scale(unit(d), least))

    def place(t, drop, hist):
        """The pose of tick t with the body lowered by drop; how far a standing leg stays out of reach.
        A swinging wrist (hock) flies on an arc from where the paw lifted to where it lands, the paw curling under the
        forearm on the way and opening flat to land."""
        phase = t / ticks
        pose = body_at(phase, drop, hist)
        short = 0.0
        for name, (up, lo, paw, side, front) in LEGS.items():
            stance, s = leg_phase(cfg, name, phase)
            if stance:
                short = max(short, stand(pose, name, s, hist))
                continue
            key = 'front' if front else 'hind'
            stride = speed * ticks * cfg['duty'][name] * (1 - cfg['slip'])
            base = 0 if front else HIND_TOE
            lift_off = standing(rig, name, tracks[name], centres[name] + stride / 2, rot([base + cfg['peel'][key], 0, 0]))
            landing = standing(rig, name, tracks[name], centres[name] - stride / 2, rot([base, 0, 0]))
            k = minimum_jerk(s) if cfg['snap'] else smooth(s)
            flight = [lift_off[i] + (landing[i] - lift_off[i]) * (k if i == 2 else s) for i in range(3)]
            flight[2] -= cfg['out'][key] * 6.75 * s * s * (1 - s)    # reaches past the landing, then settles onto it
            flight[1] -= cfg['lift'][key] * math.sin(math.pi * min(1.0, s ** 0.8))
            pitch, curl, follow = swing_paw(cfg, name, s)
            world = rot([pitch, 0, 0])
            for _ in range(4):  # the paw hangs from its forearm, curled; it never brushes the floor
                wrist = folded(pose, name, [flight[0], min(flight[1], -CLEAR - rig.lowest(paw, world, [0, 0, 0])), flight[2]])
                forearm, _ = rig.solve(pose, name, wrist, hist)
                target = rot([pitch, 0, 0])
                if follow > 0:
                    target = slerp(target, mul(forearm, mul(rig.ref[name][2], rx(curl))), follow)
                if front:       # the gauntlet stays seated on the paw
                    bend = rig.bend(name, forearm, target)
                    fix = min(0.0, bend - GAUNTLET[0]) + max(0.0, bend - GAUNTLET[1])
                    if abs(fix) > 0.01:
                        worst['clamp'] = max(worst['clamp'], abs(fix))
                        target = mul(target, rx(-fix))
                settled = max(abs(x - y) for r, q in zip(target, world) for x, y in zip(r, q)) < 1e-4
                world = target
                if settled:
                    break
            wrist = folded(pose, name, [flight[0], min(flight[1], -CLEAR - rig.lowest(paw, world, [0, 0, 0])), flight[2]])
            forearm, _ = rig.solve(pose, name, wrist, hist)
            set_rot(pose, paw, mul(tr(forearm), world), hist)
        return pose, short

    # a standing leg that cannot reach brings the body down to it, along a smooth cyclic dip
    need = [0.0] * ticks

    def dip(phase):
        x = phase * ticks
        return max(n - 0.6 * min(abs(x - j), ticks - abs(x - j)) ** 2 for j, n in enumerate(need))
    for _ in range(6):
        shorts = [place(t, dip(t / ticks), {})[1] for t in range(ticks)]
        if max(shorts) < 0.5:
            break
        need = [n + s + (1 if s >= 0.5 else 0) for n, s in zip(need, shorts)]
    hist = {}
    drop = [dip(t / ticks) for t in range(ticks)]
    frames = [place(t, drop[t], hist)[0] for t in range(ticks)]
    worst['stretch'] = max(shorts)
    worst['drop'] = max(drop)
    closing = [list(v) for v in frames[0]]
    closing[0][8] = -round(speed * ticks)
    frames.append(closing)
    events = []
    for name in (('LH', 'RF') if cfg['name'] == 'run' else ('LF', 'RF')):   # the gallop's two beats; the walk's forepaws
        tick = round(cfg['touchdown'][name] * ticks) % ticks
        events.append((tick, 'sound', dict(op='sound', frame=tick + 1, bank=1, note=13)))
    return frames, sorted(events, key=lambda e: e[0]), worst


# ------------------------------------------------------------------ idle
IDLE_LIFT = dict(leg='LF', start=0.42, end=0.66, height=14, curl=30, back=6)   # one forepaw lifted and set again
IDLE_SHIFT = dict(sway=3, roll=1.5)
IDLE_RAISE = 7    # the idle stands this much higher than the imported crouch, to meet the walk and run
IDLE_BEND = 60     # the most a lifted forepaw curls from its standing bend


def idle(rig):
    """The imported idle, its body raised a little, with its legs standing: each fore wrist stays where tick 0 has it
    (the left paw lifted and set down once), the hind paws where the imported idle puts them, the elbows and knees
    following the breathing body; the weight drifts a little towards the standing paw."""
    source = rig.idle
    ticks = len(source) - 1
    still = [list(v) for v in source[0]]
    still[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
    W0 = rig.world(still)
    plant = {name: ([W0[LEGS[name][2]][i][3] for i in range(3)], [r[:3] for r in W0[LEGS[name][2]][:3]])
             for name in ('RF', 'LF')}
    own = {name: [mmd.rot_matrix(*source[0][b][3:6]) for b in LEGS[name][:3]] for name in ('RF', 'LF')}
    frames, hist, worst = [], {}, dict(clamp=0.0, stretch=0.0)
    for t in range(ticks):
        phase = t / ticks
        pose = [list(v) for v in source[t]]
        lift = IDLE_LIFT
        u = (phase - lift['start']) / (lift['end'] - lift['start'])
        up = math.sin(math.pi * u) ** 2 if 0 < u < 1 else 0.0
        # weight towards the right paw while the left one is up, a slow drift otherwise
        pose[PELVIS][6] += round(IDLE_SHIFT['sway'] * (math.sin(2 * math.pi * phase) * 0.4 + up))
        pose[CHEST][5] += round(IDLE_SHIFT['roll'] * (math.sin(2 * math.pi * (phase - 0.1)) * 0.4 + up) * DEG)
        # the hind paws stand where the imported idle has them, under a body raised a little towards the walk
        donor = [list(v) for v in source[t]]
        donor[0] = [4096, 4096, 4096] + donor[0][3:6] + [0, 0, 0]
        Wd = rig.world(donor)
        pose[PELVIS][7] -= IDLE_RAISE
        for name in ('RH', 'LH'):
            upper, lower, paw = LEGS[name][:3]
            cur = [list(v) for v in pose]
            cur[0] = donor[0]
            W = rig.world(cur)
            knee = sub([W[lower][i][3] for i in range(3)], [W[upper][i][3] for i in range(3)])
            hock, out = rig.solve(pose, name, [Wd[paw][i][3] for i in range(3)], hist, pole=knee,
                                  ref=[mmd.rot_matrix(*source[t][b][3:6]) for b in (upper, lower, paw)])
            set_rot(pose, paw, mul(tr(hock), [r[:3] for r in Wd[paw][:3]]), hist)
            worst['stretch'] = max(worst['stretch'], out)
        cur = [list(v) for v in pose]
        cur[0] = [4096, 4096, 4096] + cur[0][3:6] + [0, 0, 0]
        W = rig.world(cur)
        for name in ('RF', 'LF'):
            upper, lower, paw = LEGS[name][:3]
            wrist, paw_world = plant[name]
            shoulder = [W[upper][i][3] for i in range(3)]
            elbow = [W[lower][i][3] for i in range(3)]
            pole = sub(elbow, shoulder)
            lifted = up if name == lift['leg'] else 0.0
            world, forearm = paw_world, None
            for _ in range(4 if lifted else 1):   # the lifted paw hangs from its forearm, curled
                if forearm:
                    world = slerp(paw_world, mul(forearm, mul(own[name][2], rx(lift['curl']))), lifted)
                # the sole on the floor (or lifted), whatever the curl
                target = [wrist[0], -lift['height'] * lifted - rig.lowest(paw, world, [0, 0, 0]),
                          wrist[2] + lift['back'] * lifted]
                forearm, out = rig.solve(pose, name, target, hist, pole=pole, ref=own[name])
            # the gauntlet: measured from this leg's own standing bend, as the lift is all it adds
            bend = pitch_of(mul(tr(own[name][2]), mul(tr(forearm), world)))
            fix = min(0.0, bend - GAUNTLET[0]) + max(0.0, bend - IDLE_BEND)
            if abs(fix) > 0.01:
                worst['clamp'] = max(worst['clamp'], abs(fix))
                world = mul(world, rx(-fix))
            set_rot(pose, paw, mul(tr(forearm), world), hist)
            worst['stretch'] = max(worst['stretch'], out)
        frames.append(pose)
    _tail_over_floor(rig, frames)
    closing = [list(v) for v in frames[0]]
    closing[0][6:9] = source[-1][0][6:9]
    frames.append(closing)
    return frames, worst


def _tail_over_floor(rig, frames):
    """The imported idle sweeps the tail tuft up to 63 units through the floor: its first three joints curl it up just
    enough, eased in and out over the neighbouring ticks."""
    def lowest(pose):
        W = rig.world(pose)
        return max(rig.lowest(b, [r[:3] for r in W[b][:3]], [W[b][i][3] for i in range(3)]) for b in TAIL)

    def lifted(pose, degrees):
        p = [list(v) for v in pose]
        for b in TAIL[:3]:
            p[b][3] += round(degrees * DEG)
        return p
    ticks = len(frames)
    need = []
    for pose in frames:
        degrees = 0.0
        while lowest(lifted(pose, degrees)) > -3 and degrees < 60:
            degrees += 1
        need.append(degrees)
    for t, pose in enumerate(frames):
        degrees = max(n - 1.5 * min(abs(t - j), ticks - abs(t - j)) for j, n in enumerate(need))
        if degrees > 0:
            frames[t] = lifted(pose, degrees)


# ------------------------------------------------------------------ the recipe
SPEED_RANGE = {2: (15, 30), 4: (35, 52)}    # the native partners' field speeds (units per tick)
FLOOR = 3            # a mesh point may dip this far under the floor at a tick or a 60 fps third (the imported
                     # hind paws stand 2 units in it; rounding)
STANCE_SLIP = 0.35   # a standing paw may slide this fraction of the body's travel (natives: 0.1-0.8)


def _played(animation, n, slot, ticks):
    player = mmd.AnimPlayer(animation, n, slot)
    played = []
    for _ in range(ticks * 9 + 1):
        assert player.tick()
        pose = [list(v) for v in player.pose]
        pose[0][6:9] = list(player.root)
        played.append(pose)
    return played, player.events


def _floor(rig, frames):
    """Lowest mesh point of each tick and its 60 fps thirds, over the floor at 0 (y grows downwards)."""
    from motiontailspace import interpolate_pose
    worst = -1e9
    for t in range(len(frames) - 1):
        for alpha in (0, 1365, 2730):
            pose = interpolate_pose(frames[t], frames[t + 1], alpha)
            height = pose[0][7]
            W = rig.world(pose)
            for b, verts in rig.verts.items():
                worst = max(worst, rig.lowest(b, [r[:3] for r in W[b][:3]], [W[b][i][3] for i in range(3)]) + height)
    return worst


def _stance_slip(rig, cfg, frames):
    """Per paw: how far its sole pivot moves over the ground while the leg stands, as a fraction of the body's travel."""
    ticks = cfg['ticks']
    out = {}
    for name, (up, lo, paw, side, front) in LEGS.items():
        moved, travel = 0.0, 0.0
        for t in range(ticks):
            if not (leg_phase(cfg, name, t / ticks)[0] and leg_phase(cfg, name, (t + 1) / ticks)[0]):
                continue
            here = []
            for pose in (frames[t], frames[t + 1]):
                W = rig.world(pose)
                point = add([W[paw][i][3] for i in range(3)], mv([r[:3] for r in W[paw][:3]], SOLE[front]))
                here.append(point[2] + pose[0][8])
            moved += abs(here[1] - here[0])
            travel += abs(frames[t + 1][0][8] - frames[t][0][8])
        out[name] = round(moved / travel, 3) if travel else 0.0
    return out


def _bends(rig, frames, names=('RF', 'LF')):
    low, high = 1e9, -1e9
    for pose in frames:
        W = rig.world(pose)
        for name in names:
            lo, paw = LEGS[name][1], LEGS[name][2]
            b = rig.bend(name, [r[:3] for r in W[lo][:3]], [r[:3] for r in W[paw][:3]])
            low, high = min(low, b), max(high, b)
    return round(low, 1), round(high, 1)


def build(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('Nefertimon\'s gait requires the reviewed source')
    if [b[1] for b in skeleton] != PARENTS:
        raise ValueError('Nefertimon rig differs')
    n = len(skeleton)
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = n
    old = mmd.MMD.parse(data, n)
    old.type = SPECIES
    new = copy.deepcopy(old)
    rig = Rig(old, skeleton)
    authored = {}
    for slot, cfg in GAITS.items():
        frames, events, worst = gait(rig, cfg)
        authored[slot] = (frames, events, worst, cfg)
    frames, worst = idle(rig)
    source_events = animsheet.slot_frames(old, n, 0)[2]
    authored[0] = (frames, source_events, worst, None)
    checks, changed = [], set()
    for slot, (frames, events, worst, cfg) in sorted(authored.items()):
        ticks = len(frames) - 1
        frames = [[[round(x) for x in bone] for bone in pose] for pose in frames]
        animation = mmd.encode_anim(frames, n, loop_sample=0, events=events, tol=1)
        index = old.anims.table[slot]
        new.anims.anims[index] = animation          # in place: the slot's aliases play it too
        changed |= {s for s, i in enumerate(old.anims.table) if i == index}
        played, played_events = _played(animation, n, slot, ticks)
        for tick in range(ticks, ticks * 9 + 1, ticks):
            assert all(abs(a - b) <= 2 for bone, other in zip(played[0][1:], played[tick][1:]) for a, b in zip(bone, other)), \
                (slot, tick, 'loop drift')
        loop = played[:ticks + 1]
        speed = abs(loop[-1][0][8] - loop[0][0][8]) / ticks
        floor = _floor(rig, loop)
        assert floor <= FLOOR, (slot, 'under the floor', floor)
        bends = _bends(rig, loop)
        allowed = GAUNTLET if cfg else (min(_bends(rig, rig.idle)[0], GAUNTLET[0]), _bends(rig, rig.idle)[1] + IDLE_BEND)
        assert allowed[0] - 1 <= bends[0] and bends[1] <= allowed[1] + 1, (slot, 'gauntlet', bends, allowed)
        row = dict(slot=slot, ticks=ticks, units_per_tick=round(speed, 2), lowest_point=round(floor, 1),
                   front_paw_bend=bends, sound_ticks=sorted({k for k, kind, _ in played_events if kind == 'sound' and k < ticks}),
                   unreached=round(worst['stretch'], 2), gauntlet_clamp=round(worst['clamp'], 1),
                   stream_bytes=len(animation.build()), aliases=sorted(s for s, i in enumerate(old.anims.table) if i == index))
        if cfg:
            low, high = SPEED_RANGE[slot]
            assert low <= speed <= high and abs(speed - cfg['speed']) <= 0.5, (slot, speed)
            slips = _stance_slip(rig, cfg, loop)
            assert max(slips.values()) <= STANCE_SLIP, (slot, slips)
            assert len(row['sound_ticks']) == 2, (slot, row['sound_ticks'])
            row.update(gait=cfg['name'], touchdown=cfg['touchdown'], duty=cfg['duty'], stance_slip=slips,
                       body_drop=round(worst['drop'], 1))
        else:
            assert speed == 0
        checks.append(row)
    result = new.build()
    actual = mmd.MMD.parse(result, n)
    assert old.tmd.build() == actual.tmd.build()
    assert changed_programs(old, actual) == sorted(changed), (changed_programs(old, actual), sorted(changed))
    storage = motionstorage.require(result, n)
    return result, dict(species=SPECIES, source_sha256=SOURCE, output_sha256=hashlib.sha256(result).hexdigest(),
                        changed_slots=sorted(changed), checks=checks, storage=storage, mesh_exact=True,
                        other_programs_exact=True)
