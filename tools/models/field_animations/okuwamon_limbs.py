"""Okuwamon's field clips: the idle as cleaned before, and a four-legged walk written from the feet up.

Offline only (player builds replay the pinned delta): `tools/models/edit.py get 259` on the commit before this change,
then `python3 -m tools.models.field_animations.okuwamon_limbs --source THAT.MMD --out AFTER.MMD --report R.json` and
`edit.py put 259 AFTER.MMD`.

Slot 0, the idle, keeps what an earlier pass of this file made of it: the two front hips turned a little so no leg cuts
into another (`IDLE_HIPS`, two tables of turns) and the wings and elytra as spring followers of their own turns, closed
over the loop. It is byte for byte the same.

Slots 1 to 4 (the tired rest, walk, tired walk and run) are written new, from the idle's standing pose:

- The four legs (bones 16/17, 18/19 front right and left, 20/21, 22/23 hind right and left) walk as diagonal pairs:
  front right with hind left, then front left with hind right. Every foot has a stance and a swing per cycle. In stance
  the foot stands still on the floor while the body passes over it (the clip's root speed times the stance ticks is the
  length of the step); in swing it rises, comes forward in an arc and lands flat. Each foot is a big flat cone: it is
  put on the floor with its sole level, and the lowest vertex of the leg is held at the floor height at every tick.
- Each leg is solved on its own two bones (`Leg`): a thigh turn about the hip and a lower-leg turn about the knee that
  put the sole's centre on its target, keep the sole level and the leg facing as in the idle (damped Gauss-Newton on
  the bones' own transforms, no clamping: a target the leg cannot reach stops the build).
- The big feet of one side are 250 units across and the hips are 100 apart, so a front and a hind foot of one side
  must never both be at the near ends of their steps: the step is as long as the feet allow (`STEP`), the cycle short
  and the speeds the native ones that go with it.
- The pelvis bobs once per footfall of a pair, sways to the side the weight is on and pitches a little; the chest and
  head keep steadier than it. The pincers (arms 7 to 9 and 10 to 12) are carried forward and slightly open and swing
  gently with the steps, a few ticks late. The wings (13, 14) and the elytra (15) only flutter, as damped followers.
- The root keeps only its travel (a whole number of units a tick); every clip is a closed loop.

The build refuses another source, a limb vertex inside the body or another limb, a foot under the floor or off it at
a stance tick, a leg that does not reach, an open loop, the changed programs outside the five slots (and their
aliases) and the storage budget.
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
import animstudio  # noqa: E402
import mmd  # noqa: E402
import motionsecondary  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402

R = motionsecondary.R
SPECIES, NB = 259, 24
SLOTS = (0, 1, 2, 3, 4)
SOURCE = '06b1ba3deed7c6a8579a83d7cc9ae084423f1605e9fed27667c589ea40f7c8f4'   # edit.py get 259 before this change
FLOOR = 16.0                     # units a leg may sink (the idle's own planted foot reaches 11 below the origin)
SOCKET = 45.0                    # units around a limb's root joint, built inside the body
WING_SOCKET = 110.0              # the same for a wing: its root lies on the back, a hinge flap
# per leg (hip, knee), and the arm chains (shoulder, elbow, claw)
LEGS = ((16, 17), (18, 19), (20, 21), (22, 23))
ARMS = ((7, 8, 9), (10, 11, 12))
WINGS = (13, 14, 15)
BODY = (1, 2, 3, 4, 5, 6)
PELVIS, CHEST = 1, 3
LIMB_BONES = tuple(b for c in ARMS + LEGS for b in c)
DIRS = ([1, .3, .2], [0, 1, .1], [.1, .2, 1], [-.7, .2, .5], [.3, -1, .2])
X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)

# the idle's two front hips (bones 16 and 18): rotation per tick, as an earlier pass of this file made them
IDLE_HIPS = {
    16: [[-747, -238, -436], [-761, -228, -447], [-776, -217, -459], [-791, -206, -471], [-805, -195, -471],
         [-821, -185, -475], [-839, -178, -488], [-858, -173, -512], [-877, -167, -537], [-893, -158, -560],
         [-908, -148, -581], [-922, -138, -598], [-935, -126, -612], [-948, -113, -617], [-952, -101, -621],
         [-958, -94, -622], [-963, -85, -622], [-952, -102, -621], [-939, -119, -619], [-925, -135, -614],
         [-910, -151, -605], [-894, -165, -592], [-876, -178, -570], [-855, -188, -539], [-830, -193, -499],
         [-807, -200, -469], [-788, -212, -455], [-783, -216, -456], [-777, -220, -457], [-771, -224, -458],
         [-765, -228, -459], [-759, -232, -452], [-753, -237, -444], [-747, -238, -436]],
    18: [[-747, 238, 436], [-760, 227, 436], [-774, 216, 436], [-788, 204, 436], [-801, 193, 436], [-816, 182, 446],
         [-831, 172, 459], [-847, 163, 479], [-864, 156, 504], [-882, 148, 526], [-897, 138, 541], [-912, 127, 556],
         [-927, 117, 574], [-942, 105, 591], [-950, 99, 606], [-956, 93, 615], [-963, 85, 616], [-950, 101, 612],
         [-937, 118, 604], [-921, 132, 589], [-903, 145, 568], [-883, 157, 542], [-862, 165, 513], [-838, 172, 480],
         [-818, 181, 461], [-801, 193, 453], [-784, 207, 446], [-779, 211, 438], [-773, 215, 431], [-767, 220, 423],
         [-761, 224, 426], [-755, 229, 429], [-749, 233, 432], [-747, 238, 436]],
}


def inside(points, tris, direction):
    """Points inside the closed mesh `tris` (n, 3, 3) by one ray's parity (Moeller-Trumbore)."""
    a0, a1, a2 = tris[:, 0], tris[:, 1], tris[:, 2]
    e1, e2 = a1 - a0, a2 - a0
    d = np.array(direction, float)
    h = np.cross(d, e2)
    det = (e1 * h).sum(1)
    ok = np.abs(det) > 1e-9
    det = np.where(ok, det, 1)
    s = points[:, None, :] - a0[None]
    u = (s * h[None]).sum(2) / det[None]
    q = np.cross(s, e1[None])
    v = (q * d).sum(2) / det[None]
    t = (e2[None] * q).sum(2) / det[None]
    hit = ok[None] & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-6)
    return hit.sum(1) % 2 == 1


class Body:
    """The model in a pose: lowest vertex of a leg, and the vertices of a limb inside other parts."""

    def __init__(self, model, sk):
        self.model = model
        self.sk = sk
        self.mesh = animstudio.FastMesh(type('M', (), dict(m=model, skel=sk))())
        self.slices = {b: (a, k) for b, a, k in self.mesh.slices}

    def local_vertices(self, bone):
        a, k = self.slices[bone]
        return self.mesh.V[a:a + k].astype(float)

    def world(self, pose):
        p = copy.deepcopy(pose)
        p[0] = [4096] * 3 + [0] * 6
        mats = mmd.bone_matrices(self.model, p)
        return mats, self.mesh.world(mats).astype(float)

    def points(self, world, bones):
        return world[self.mesh.tri[np.isin(self.mesh.bone, bones)]].reshape(-1, 3)

    def count(self, mats, world, a_bones, b_bones, socket=None, radius=SOCKET):
        mesh = self.mesh
        tri = world[mesh.tri[np.isin(mesh.bone, a_bones)]]
        points = np.vstack([tri.reshape(-1, 3), tri.mean(1)])
        if socket is not None:
            joint = np.array(mats[socket], float)[:3, 3]
            points = points[np.linalg.norm(points - joint, axis=1) > radius]
        tris = world[mesh.tri[np.isin(mesh.bone, b_bones)]]
        votes = sum(inside(points, tris, d).astype(int) for d in DIRS)
        return int((votes >= 3).sum())

    @staticmethod
    def groups():
        g = {'leg%d' % i: l for i, l in enumerate(LEGS)}
        g.update({'arm%d' % i: a for i, a in enumerate(ARMS)})
        g.update({'wing%d' % b: (b,) for b in WINGS})
        return g

    def measure(self, pose, key, cache=None):
        """One entry of the report. A limb or wing: the vertices inside the parts it must not cut (the body, the other
        limbs; a wing is not a part to cut into). `floorN`: the units leg N's lowest vertex is below FLOOR."""
        mats, world = cache or self.world(pose)
        if key.startswith('floor'):
            leg = LEGS[int(key[5:])]
            return max(0.0, float(self.points(world, leg)[:, 1].max()) - FLOOR)
        groups = self.groups()
        chain = groups[key]
        others = tuple(b for n, c in groups.items() if n != key and not n.startswith('wing') for b in c)
        if key.startswith('wing'):
            return self.count(mats, world, chain, BODY + others, chain[0], WING_SOCKET)
        # the first bone of a limb (a hip's thigh, a shoulder) is built into the body: it is only tested against the others
        return self.count(mats, world, chain[1:], BODY + others) + self.count(mats, world, chain[:1], others)

    def report(self, pose):
        cache = self.world(pose)
        keys = list(self.groups()) + ['floor%d' % i for i in range(len(LEGS))]
        return {k: self.measure(pose, k, cache) for k in keys}


def spin(pose, bone, axis, degrees):
    """A turn about `axis` of the bone's parent frame, put in front of its own rotation."""
    local = R.rot_of(pose[bone])
    new = R.m3mul(R.from_axis_angle(axis, math.radians(degrees)), local)
    pose[bone][3:6] = [round(v) for v in mmd.matrix_euler(new, pose[bone][3:6])]


def log_so3(r):
    r = np.array(r, float)
    c = max(-1., min(1., (r[0, 0] + r[1, 1] + r[2, 2] - 1) / 2))
    angle = math.acos(c)
    if angle < 1e-9:
        return np.zeros(3)
    return angle / (2 * math.sin(angle)) * np.array([r[2, 1] - r[1, 2], r[0, 2] - r[2, 0], r[1, 0] - r[0, 1]])


def exp_so3(v):
    angle = float(np.linalg.norm(v))
    if angle < 1e-12:
        return np.eye(3)
    x, y, z = np.array(v, float) / angle
    k = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    return np.eye(3) + math.sin(angle) * k + (1 - math.cos(angle)) * (k @ k)


def mean_rotation(rots):
    mean = np.array(rots[0], float)
    for _ in range(20):
        mean = mean @ exp_so3(sum(log_so3(mean.T @ r) for r in rots) / len(rots))
    return mean


def spring_closed(target, period, zeta):
    """The response of a spring to a periodic target (n samples of a vector), settled: three loops are run and the last
    one is returned, so it begins where it ends."""
    n = len(target)
    w = 2 * math.pi / period
    x = np.zeros(3)
    v = np.zeros(3)
    out = []
    for loop in range(4):
        out = []
        for i in range(n):
            a = w * w * (target[i] - x) - 2 * zeta * w * v
            v = v + a
            x = x + v
            out.append(x.copy())
    return out


def put_rotation(pose, bone, matrix):
    pose[bone][3:6] = [round(v) for v in mmd.matrix_euler([list(r) for r in matrix], pose[bone][3:6])]


# ---------------------------------------------------------------------------------------------------- the idle
IDLE_SPRING = {13: (6.0, .45), 14: (6.0, .45), 15: (7.0, .5)}     # natural period in ticks, damping ratio
ELYTRA, ELYTRA_LAG = 15, 2


def idle_clip(frames):
    """Slot 0: the original idle with its wings and elytra as spring followers, and the front hips of IDLE_HIPS."""
    n = len(frames) - 1
    out = copy.deepcopy(frames)
    mean, dev = {}, {}
    for b in IDLE_SPRING:
        rots = [np.array(R.rot_of(f[b]), float) for f in frames[:n]]
        mean[b] = mean_rotation(rots)
        dev[b] = [log_so3(mean[b].T @ r) for r in rots]
    for b, (period, zeta) in IDLE_SPRING.items():
        target = dev[b]
        if b == ELYTRA:
            lead = dev[13]
            target = [target[i] + np.array([lead[(i - ELYTRA_LAG) % n][0], 0, 0]) for i in range(n)]
        for i, d in enumerate(spring_closed(target, period, zeta)):
            put_rotation(out[i], b, mean[b] @ exp_so3(d))
    for hip, table in IDLE_HIPS.items():
        for i, rot in enumerate(table):
            out[i][hip][3:6] = list(rot)
    out[-1][1:] = copy.deepcopy(out[0][1:])
    return out


# ---------------------------------------------------------------------------------------------------- the legs
def local_matrix(v, rotation=None):
    """The bone's own transform of a pose entry: T · R · S (scales in 4.12), as `mmd.bone_matrices` makes it."""
    r = np.array(mmd.rot_matrix(*v[3:6]) if rotation is None else rotation, float) * (np.array(v[:3], float) / 4096)
    m = np.eye(4)
    m[:3, :3] = r
    m[:3, 3] = v[6:9]
    return m


class Leg:
    """One leg, hip bone and knee bone, in the standing pose `base`: the sole's centre, its level, and a solver that
    turns thigh and lower leg together until the centre stands where it is told and the sole is level."""

    def __init__(self, body, base, k):
        self.hip, self.knee = LEGS[k]
        self.base = base
        mats, world = body.world(base)
        self.verts = body.local_vertices(self.knee)
        m = np.array(mats[self.knee], float)
        w = self.verts @ m[:3, :3].T + m[:3, 3]
        sole = self.verts[w[:, 1] > w[:, 1].max() - 6]                  # the flat base of the cone
        self.centre = sole.mean(0)
        self.rest_world = m[:3, :3]                                      # the sole's level in the standing pose
        self.down = self.rest_world.T @ np.array([0, 1., 0])
        self.ahead = self.rest_world.T @ np.array([0, 0, -1.])
        self.ahead_rest = np.array([0, 0, -1.])
        self.rh = np.array(mmd.rot_matrix(*base[self.hip][3:6]), float)
        self.rk = np.array(mmd.rot_matrix(*base[self.knee][3:6]), float)
        self.lh = local_matrix(base[self.hip])
        self.lk = local_matrix(base[self.knee])
        self.scale_h = np.array(base[self.hip][:3], float) / 4096
        self.scale_k = np.array(base[self.knee][:3], float) / 4096
        self.centre_standing = m[:3, :3] @ self.centre + m[:3, 3]
        self.u = np.zeros(6)
        self.level = 60.        # how hard the sole is held level, against the sole's centre being where it is told

    def fk(self, parent, u):
        lh = self.lh.copy()
        lk = self.lk.copy()
        lh[:3, :3] = (exp_so3(u[:3]) @ self.rh) * self.scale_h
        lk[:3, :3] = (exp_so3(u[3:]) @ self.rk) * self.scale_k
        m16 = parent @ lh
        return m16, m16 @ lk

    def residual(self, parent, u, target, tilt):
        _, m17 = self.fk(parent, u)
        centre = m17[:3, :3] @ self.centre + m17[:3, 3]
        down = m17[:3, :3] @ self.down
        ahead = m17[:3, :3] @ self.ahead
        return np.concatenate([centre - target, self.level * (down - tilt), 15. * (ahead - self.ahead_rest), 3. * u])

    def solve(self, parent, target, tilt=(0., 1., 0.), steps=40):
        """The turns (thigh, lower leg) in radians for a centre `target` (body frame) and a down direction `tilt`."""
        tilt = np.array(tilt, float)
        u = self.u.copy()
        r = self.residual(parent, u, target, tilt)
        lam = 1e-2
        for _ in range(steps):
            jac = np.zeros((len(r), 6))
            for j in range(6):
                d = np.zeros(6)
                d[j] = 1e-4
                jac[:, j] = (self.residual(parent, u + d, target, tilt) - r) / 1e-4
            du = np.linalg.solve(jac.T @ jac + lam * np.eye(6), -jac.T @ r)
            r2 = self.residual(parent, u + du, target, tilt)
            if r2 @ r2 < r @ r:
                u, r, lam = u + du, r2, max(lam * .5, 1e-7)
            else:
                lam *= 4
            if np.abs(r[:3]).max() < .02 and lam < 1e-3:
                break
        self.u = u
        return u, float(np.abs(r[:3]).max())

    def lowest(self, parent, u):
        _, m17 = self.fk(parent, u)
        return float((self.verts @ m17[:3, :3].T + m17[:3, 3])[:, 1].max())

    def write(self, pose, u):
        put_rotation(pose, self.hip, exp_so3(u[:3]) @ self.rh)
        put_rotation(pose, self.knee, exp_so3(u[3:]) @ self.rk)


# ---------------------------------------------------------------------------------------------------- the gaits
def smooth(w):
    """Minimum-jerk ease, 0 to 1 with no speed at either end."""
    return w * w * w * (10 - 15 * w + 6 * w * w)


# per clip: cycle ticks, root units a tick (whole), the stance's share of the cycle, `creep` (the share of the root's
# speed a standing foot is let to slide forward), where the front feet touch down (`zf`) and the hind feet leave the
# floor (`zh`) in the body's frame, how high the swing lifts, the pelvis' height and its bob, sway, pitch and twist, how
# far forward the pincers are carried and how they swing, and the wings' flutter.
CLIPS = {
    1: dict(n=20, v=0, duty=1.0, creep=0, xout=14, zf=0, zh=0, lift=0, y=-300, bob=4, bob_peak=0, sway=0, roll=.4, pitch=.6,
            twist=0, pincer=(10, 0, 8, 2), droop=(10, 5), flutter=.8, breath=True),
    2: dict(n=10, v=15, duty=.5, creep=.1, zf=-198, xout=28, zh=194, lift=46, y=-304, bob=5, bob_peak=2.5, sway=20, roll=5.0,
            pitch=.8, twist=4.0, pincer=(26, 6, 9, 2), droop=(0, 0), flutter=1.0),
    3: dict(n=12, v=10, duty=.5, creep=.1, zf=-198, xout=38, zh=192, lift=34, y=-286, bob=5, bob_peak=3.5, sway=24, roll=6.0,
            pitch=1.0, twist=4.5, pincer=(12, -4, 10, 3), droop=(14, 10), flutter=.8),
    4: dict(n=8, v=36, duty=.27, creep=.12, zf=-198, xout=32, zh=194, lift=44, y=-310, bob=12, bob_peak=2.0, sway=14, roll=4.5,
            pitch=1.6, twist=3.0, pincer=(34, 10, 8, 1), droop=(0, 0), flutter=1.3),
}
PHASE = (0.0, 0.5, 0.5, 0.0)       # front right with hind left, then front left with hind right: diagonal pairs
LEVEL_STANCE, LEVEL_SWING = 60., 11.
ROLL_SIGN = -1
PINCER_SIGN = 1
CHEST_ROLL = .45
MISS_MAX = 3.5          # units a sole's centre may stand off its target (the reach of a level sole near its limits)


def step_length(spec):
    """How far a standing foot moves along the body in one stance."""
    return spec['v'] * (1 - spec['creep']) * spec['duty'] * spec['n']


def leg_targets(legs, spec, t):
    """Per leg, the sole centre's target in the body's frame at tick t, the height the lowest vertex must have and how
    hard the sole is held level. In stance the foot slides back at the root's speed less the creep; in swing it goes
    forward along a Hermite curve that leaves and lands at that same speed, rising in an arc."""
    n, v, duty = spec['n'], spec['v'], spec['duty']
    step = step_length(spec)
    out = []
    for k, leg in enumerate(legs):
        x, y, z = leg.centre_standing
        if k < 2:
            x += math.copysign(spec.get('xout', 0), x)
        if v == 0:
            out.append((np.array([x, y, z]), 0.0, LEVEL_STANCE))
            continue
        z_td = spec['zf'] if k < 2 else spec['zh'] - step
        u = ((t / n) - PHASE[k]) % 1.0
        if u < duty:
            z, h, level = z_td + step * (u / duty), 0.0, LEVEL_STANCE
        else:
            w = (u - duty) / (1 - duty)
            slope = v * (1 - spec['creep']) * (1 - duty) * n          # the stance's speed, per unit of w
            h00, h10, h01, h11 = 2 * w ** 3 - 3 * w * w + 1, w ** 3 - 2 * w * w + w, -2 * w ** 3 + 3 * w * w, w ** 3 - w * w
            z = h00 * (z_td + step) + h10 * slope + h01 * z_td + h11 * slope
            h = spec['lift'] * math.sin(math.pi * w) ** 1.2
            level = LEVEL_STANCE - (LEVEL_STANCE - LEVEL_SWING) * math.sin(math.pi * w) ** 3
        out.append((np.array([x, y - h, z]), -h, level))
    return out


def pelvis_pose(base, spec, t):
    """Bone 1 at tick t: height with the footfalls (a quick squash on landing, a slower rise), a shift and a lean to the
    side the weight is on, a small turn the other way, pitch. Returns the pose entry and the (pitch, twist, roll) in
    degrees, which the chest answers."""
    n = spec['n']
    p = list(base[PELVIS])
    ph = 2 * math.pi * t / n
    bob = spec['bob']
    side = ph - math.pi * spec['duty']                     # 0 when the right pair is in the middle of its stance
    if spec.get('breath'):
        up = bob * math.sin(ph)
    else:
        lag = 4 * math.pi * spec['bob_peak'] / n
        up = bob * (math.cos(2 * ph - lag) + .22 * math.cos(4 * ph - 2 * lag + 1.1)) / 1.1
    p[7] = spec['y'] - up
    p[6] = base[PELVIS][6] + spec['sway'] * (math.cos(side) + .12 * math.cos(2 * side + .9))
    pitch = spec['pitch'] * math.cos(2 * ph - 4 * math.pi * spec['bob_peak'] / n + .8)
    twist = -spec['twist'] * math.cos(side - .5) + .25 * spec['twist'] * math.sin(2 * ph + .4)
    roll = spec['roll'] * (math.cos(side - .35) + .15 * math.cos(2 * side + 1.3))
    if spec.get('breath'):                                  # the tired rest keeps its small unrelated lean and turn
        twist, roll = 0.0, spec['roll'] * math.sin(ph + 1.2)
    k = 4096 / 360
    p[3] = round(p[3] + pitch * k)
    p[4] = round(p[4] + twist * k)
    p[5] = round(p[5] + ROLL_SIGN * roll * k)
    return p, pitch, twist, roll


def finish_body(frames, base, spec, idle):
    """Chest, head, pincers and wings of every tick, over the legs and pelvis already in `frames`."""
    n = len(frames) - 1
    pitches = [(frames[i][PELVIS][3] - base[PELVIS][3]) / (4096 / 360) for i in range(n)]
    twists = [(frames[i][PELVIS][4] - base[PELVIS][4]) / (4096 / 360) for i in range(n)]
    rolls = [ROLL_SIGN * (frames[i][PELVIS][5] - base[PELVIS][5]) / (4096 / 360) for i in range(n)]
    for i in range(n):
        f = frames[i]
        lag = (i - 1) % n
        spin(f, CHEST, X, -.7 * pitches[lag])
        spin(f, CHEST, Y, -.6 * twists[lag])
        spin(f, CHEST, Z, -CHEST_ROLL * rolls[(i - 2) % n])             # the chest leans less and after the pelvis
    forward, lift, sway, lag_ticks = spec['pincer']
    d_pitch, d_yaw = spec['droop']
    for a, (sh, el, cl) in enumerate(ARMS):
        side = 1 if a == 0 else -1
        for i in range(n):
            f = frames[i]
            s = side * PINCER_SIGN * math.cos(2 * math.pi * (i - lag_ticks) / n - math.pi * spec['duty'] + .4)
            s += .2 * math.sin(4 * math.pi * (i - lag_ticks) / n + a)
            c = math.cos(4 * math.pi * (i - lag_ticks - spec['bob_peak']) / n)
            spin(f, sh, Y, side * (forward + sway * s))
            spin(f, sh, X, -(lift + 2.5 * c) + d_pitch)
            spin(f, el, Z, -side * d_yaw * .6)
    # the wings flutter as the idle's do (that pattern is known to stay clear of the body), the idle's cycle played over
    # this clip's, as a spring follower that begins where it ends
    m = len(idle) - 1
    shapes = {}
    for b, (period, zeta) in IDLE_SPRING.items():
        rots = [np.array(R.rot_of(idle[i][b]), float) for i in range(m)]
        mean = mean_rotation(rots)
        dev = [log_so3(mean.T @ r) for r in rots]
        shape = []
        for i in range(n):
            x = i * m / n
            j, w = int(x), x - int(x)
            shape.append(spec['flutter'] * ((1 - w) * dev[j] + w * dev[(j + 1) % m]))
        shapes[b] = shape
        if b == ELYTRA:
            shape = [shape[i] + np.array([shapes[13][(i - ELYTRA_LAG) % n][0], 0, 0]) for i in range(n)]
        for i, d in enumerate(spring_closed(shape, period, zeta)):
            put_rotation(frames[i], b, mean @ exp_so3(d))


def gait_clip(body, base, spec, idle, report=None):
    """The clip as frames (n + 1, the last the first apart from the root's travel): legs by their solver, then the
    body over them."""
    n, v = spec['n'], spec['v']
    legs = [Leg(body, base, k) for k in range(4)]
    frames = []
    reach = 0.0
    for i in range(n):
        f = copy.deepcopy(base)
        f[0] = [4096] * 3 + [0, 0, 0, 0, 0, round(-v * i)]
        f[PELVIS] = pelvis_pose(base, spec, i)[0]
        # the body's frame is the root's, which rotates nothing: the pelvis' matrix is in it already
        parent = np.array(body.world(f)[0][PELVIS], float)
        for leg, (target, low, level) in zip(legs, leg_targets(legs, spec, i)):
            target = target.copy()
            leg.level = level
            for _ in range(4):
                u, miss = leg.solve(parent, target)
                err = leg.lowest(parent, u) - low
                if abs(err) < .3:
                    break
                target[1] -= err
            reach = max(reach, miss)
            if report is not None:
                report.setdefault('misses', []).append((i, leg.hip, round(miss, 2), [round(float(c), 1) for c in target]))
            if miss > MISS_MAX and (report is None or not report.get('lenient')):
                raise AssertionError(('a leg does not reach', leg.hip, i, miss))
            leg.write(f, u)
        frames.append(f)
    last = copy.deepcopy(frames[0])
    last[0] = [4096] * 3 + [0, 0, 0, 0, 0, round(-v * n)]
    frames.append(last)
    finish_body(frames, base, spec, idle)
    frames = [[[int(round(x)) for x in bone] for bone in pose] for pose in frames]       # whole numbers, as stored
    frames[-1][1:] = copy.deepcopy(frames[0][1:])
    if report is not None:
        report['reach'] = reach
    return frames


# ---------------------------------------------------------------------------------------------------- measuring

STANCE_FLOOR = 1.5       # a foot whose lowest vertex is this close to the floor, at both ends of a tick, is standing
SLIP_MEAN, SLIP_MAX = .25, .45
JUMP = 2.7               # a joint may turn this many times its median turn in one tick (a branch flip is 5 and more)


def _turn(a, b):
    return float(np.linalg.norm(log_so3(np.array(R.rot_of(a), float).T @ np.array(R.rot_of(b), float))))


def clip_report(body, frames, spec, base):
    """What a clip does, in numbers: per leg the stance ticks, how far the sole's centre slides in stance (a share of the
    root's speed), the sole's tilt and the lowest vertex's height over the floor; the largest jump of a joint against its
    median; the limb vertices inside other parts; the pincers' reach; whether it closes."""
    n, v = len(frames) - 1, spec['v']
    out = dict(ticks=n, speed=v, closed=all(frames[0][b] == frames[n][b] for b in range(1, len(frames[0]))))
    legs = []
    for k, (hip, knee) in enumerate(LEGS):
        leg = Leg(body, base, k)
        vertices = body.local_vertices(knee)
        track = []
        for i in range(n + 1):
            mats, _ = body.world(frames[i])
            m = np.array(mats[knee], float)
            world = vertices @ m[:3, :3].T + m[:3, 3]
            down = m[:3, :3] @ leg.down
            track.append(dict(low=float(world[:, 1].max()), tilt=math.degrees(math.acos(min(1., down[1] / np.linalg.norm(down)))),
                              centre=m[:3, :3] @ leg.centre + m[:3, 3] + np.array([0, 0, frames[i][0][8]])))
        stance = [i for i in range(n) if track[i]['low'] > -STANCE_FLOOR and track[i + 1]['low'] > -STANCE_FLOOR]
        slide = [float(np.hypot(*(track[i + 1]['centre'] - track[i]['centre'])[[0, 2]])) / v for i in stance] if v else [0.]
        legs.append(dict(stance=len(stance), slip_mean=float(np.mean(slide)), slip_max=float(max(slide)),
                         tilt=max(t['tilt'] for t in track), lowest=max(t['low'] for t in track[:n]),
                         lift=-min(t['low'] for t in track[:n]),
                         step=(float(np.ptp([track[i]['centre'][2] - frames[i][0][8] for i in stance])) if stance else 0.)))
    out['legs'] = legs
    jumps = {}
    for b in (b for c in LEGS + ARMS for b in c):
        turns = [_turn(frames[i][b], frames[i + 1][b]) for i in range(n)]
        med = float(np.median(turns))
        jumps[b] = max(turns) / med if med > .01 else (0. if max(turns) < .05 else 99.)     # a nearly still joint: absolute
    out['jump'] = max(jumps.values())
    out['jump_bone'] = max(jumps, key=jumps.get)
    penetration = {}
    for i in range(n):
        for key, count in body.report(frames[i]).items():
            if count and not key.startswith('floor'):
                penetration[(i, key)] = count
    out['penetration'] = penetration
    reach = []
    for i in range(n):
        mats, _ = body.world(frames[i])
        reach.append([float(np.array(mats[claw], float)[2, 3]) for claw in (9, 12)])
    out['claw_z'] = (min(min(r) for r in reach), max(max(r) for r in reach))
    return out


def clip_failures(report, spec):
    """Why a clip is not acceptable (an empty list when it is)."""
    bad = []
    if not report['closed']:
        bad.append('does not close')
    if report['penetration']:
        bad.append('limbs inside other parts: %s' % sorted(report['penetration'])[:4])
    if report['jump'] > JUMP:
        bad.append('joint %d turns %.1f times its median in a tick' % (report['jump_bone'], report['jump']))
    if spec['v']:
        for k, leg in enumerate(report['legs']):
            if not leg['stance']:
                bad.append('leg %d never stands' % k)
            if leg['slip_mean'] > SLIP_MEAN or leg['slip_max'] > SLIP_MAX:
                bad.append('leg %d slides %.0f%% (max %.0f%%) of the root speed' % (k, 100 * leg['slip_mean'], 100 * leg['slip_max']))
            if leg['lowest'] > 1.0:
                bad.append('leg %d sinks %.1f under the floor' % (k, leg['lowest']))
    return bad


# ---------------------------------------------------------------------------------------------------- building

def _parse(data, sk):
    mmd.exe().skeleton[SPECIES] = sk
    mmd.exe().bone_count[SPECIES] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = SPECIES
    return model


def original(model, slot):
    """The clip as stored: whole-number poses per tick, loop start and events."""
    frames, loop, events = animsheet.slot_frames(model, NB, slot)
    frames = [[[int(round(v)) for v in bone] for bone in pose] for pose in frames]
    return frames, loop, [(k, kind, c) for k, kind, c in events]


def footfalls(spec):
    """The step sounds: one at each pair's touchdown, as the original clip had (note 16 of bank 1)."""
    return [(t, 'sound', {'op': 'sound', 'frame': t + 1, 'bank': 1, 'note': 16}) for t in (0, spec['n'] // 2)]


def new_clips(model, sk):
    """Slot -> (frames, loop, events), every clip of this file."""
    body = Body(model, sk)
    idle = idle_clip(original(model, 0)[0])
    clips = {0: (idle, original(model, 0)[1], original(model, 0)[2])}
    for slot, spec in CLIPS.items():
        frames = gait_clip(body, idle[0], spec, idle)
        events = footfalls(spec) if spec['v'] else original(model, slot)[2]
        clips[slot] = (frames, 0, events)
    return body, clips


def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE or len(sk) != NB:
        raise ValueError("Okuwamon's clips are written over the model as `edit.py get 259` gave it before the first change")
    model = _parse(data, sk)
    body, clips = new_clips(model, sk)
    result = copy.deepcopy(model)
    checks = []
    for slot, (frames, loop, events) in clips.items():
        program = mmd.encode_anim(frames, NB, loop, events, tol=0, repeats=False)
        result.anims.anims[model.anims.table[slot]] = program        # the slots that share a program share the clip
        if slot:
            report = clip_report(body, frames, CLIPS[slot], clips[0][0][0])
            failures = clip_failures(report, CLIPS[slot])
            if failures:
                raise AssertionError((slot, failures))
            checks.append(dict(slot=slot, report=report))
    for animation in result.anims.anims:
        animation.tail = b''
    output = result.build()
    effective = _parse(output, sk)
    assert effective.tmd.build() == model.tmd.build()
    return output, dict(species=SPECIES, source_sha256=SOURCE, output_sha256=hashlib.sha256(output).hexdigest(),
                        changed_slots=changed_programs(model, effective), checks=checks,
                        storage=motionstorage.require(output, NB))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    sk = json.loads((ROOT / 'content/species/259-okuwamon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), sk)
    a.out.write_bytes(data)
    if a.report:
        a.report.write_text(json.dumps(proof, indent=2, default=list) + '\n')
    print(json.dumps({'changed_slots': proof['changed_slots']}), proof['storage']['resident_bytes'], len(data))
    for c in proof['checks']:
        r = c['report']
        print(c['slot'], 'ticks', r['ticks'], 'v', r['speed'], 'jump %.1f' % r['jump'],
              [(l['stance'], round(l['slip_mean'], 2), round(l['slip_max'], 2), round(l['tilt'], 1)) for l in r['legs']])


if __name__ == '__main__':
    main()
