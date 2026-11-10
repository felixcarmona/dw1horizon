"""Gomamon's (species 217) idle, walk, condition walk and run: a seal's scoot on four planted flippers, with a blink and a mouth.

Offline authoring only: player builds replay the pinned plain delta. Run with --source, --source-tim, --out and
--out-tim, then store the result with tools/models/edit.py put 217.

Gomamon crawls on its belly-high body: the front limbs (13-14, 15-16) are two stiff posts of 70 units ending in a flat
paw, the rear flippers (17, 18) are paddles at the back, the tail is 20-19. The head (2) carries the mane (3, 4) and
two four-bone ears (5-8, 9-12); the eyes and the mouth are painted on the head's texture, so there is no jaw or lid
bone: the face acts through texture moves (gomamon_face.py: its blink and open-mouth frames live in the texture's free
rows, and each clip copies them over the sprites on a schedule). The head (turn, tilt, nod) and the ears, mane and
tail that answer it a few ticks late do the rest.

- Walk (2): a lateral sequence, left front, right rear, right front, left rear, a quarter cycle apart. Each flipper
  stands on the floor and stays put in the world while the body passes over it, then lifts and swings forward
  along the body. The body rolls onto the standing front flipper, pitches with the strokes and surges and slows with the
  footfalls; the head steadies and glances, the ears, mane and tail follow late.
- Condition walk (3): the same sequence slower, shorter strokes, head and tail low, ears down.
- Run (4): a bound: both front flippers land together, then both rear flippers, with a flight between; the body
  rises and falls, the mane and ears fly.
- Idle (0): breathing, the head looking around with the ears answering, a tail wag and a flipper twitch.

Every clip loops whole. The mesh, the skeleton, the used texture rows and every other slot stay exact.
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
import numeric as np  # noqa: E402
import animsheet  # noqa: E402
import mmd  # noqa: E402
from tools.models.field_animations import gomamon_face  # noqa: E402
import motioncyclelayer  # noqa: E402
import motionsecondary  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models.field_animations.war_greymon import align, rotation, set_rotation  # noqa: E402

SOURCE = 'baaf7732a7d2861d267d8eb0eb57e3e5856866ae292f0153a086baee937adb54'
SPECIES = 217
FLOOR_Y = -2.0          # the soles stand here (the rest pose's mesh floor is -2.49)
FLOOR_LIMIT = 1.0       # no mesh point may be lower than this at a tick or a 60 fps third
HEAD, MANE, CREST = 2, 3, 4
EAR_R, EAR_L = (5, 6, 7, 8), (9, 10, 11, 12)
TAIL = (20, 19)
FORE = {'LF': (15, 16, -1), 'RF': (13, 14, 1)}
REAR = {'LR': (18, -1), 'RR': (17, 1)}
TORSO, PELVIS = 21, 1
DX_MIN = 14.0
VMAX = 67.5
LAT = 17.0              # the rest lateral offset of the wrist from the shoulder: the arm swings fore and aft, it does not splay
LIMBS = (13, 14, 15, 16, 17, 18)


# ------------------------------------------------------------------ small helpers
def rx(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def ry(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rz(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def turn(pitch=0.0, yaw=0.0, roll=0.0):
    """A rotation about the world axes through a joint: nose down, head turned to the animal's left, top tilted to its right."""
    return rz(roll) @ ry(yaw) @ rx(pitch)


def ease(q):
    return q * q * q * (10 + q * (6 * q - 15))


def cyc(t, n, k=1, phase=0.0):
    return math.sin(2 * math.pi * (k * t / n - phase))


def track(keys, t, n):
    """Periodic eased keyframes [(time, value)]: the value at tick t of a loop of n, each move a cosine ease."""
    keys = sorted(keys)
    t = t % n
    for i, (t0, v0) in enumerate(keys):
        t1, v1 = keys[(i + 1) % len(keys)]
        t1 = t1 + (n if i + 1 == len(keys) else 0)
        tt = t + (n if t < keys[0][0] else 0)
        if t0 <= tt < t1:
            q = (tt - t0) / (t1 - t0)
            return v0 + (v1 - v0) * (0.5 - 0.5 * math.cos(math.pi * q))
    return keys[0][1]


class Spring:
    """A damped follower, run over three loops so that the last one is the steady cycle: follow-through that closes."""

    def __init__(self, stiff, damp):
        self.k, self.d = stiff, damp

    def run(self, drive, loops=4):
        n = len(drive)
        x = v = 0.0
        out = []
        for i in range(n * loops):
            a = self.k * (drive[i % n] - x) - self.d * v
            v += a
            x += v
            if i >= n * (loops - 1):
                out.append(x)
        return out


# ------------------------------------------------------------------ the gaits
PROFILE = {
    2: dict(name='walk', ticks=40, cycle=10, speed=15, kind='walk', tangent=0.4, steps={'LF': 0.0, 'RR': 0.25, 'RF': 0.5, 'LR': 0.75},
            duty={'LF': 0.3, 'RF': 0.3, 'LR': 0.38, 'RR': 0.38}, lift={'F': 4, 'R': 9}, rock=14, centre={'F': -46, 'R': 40},
            bob=1.5, pitch=1.6, roll=2.5, yaw=1.5, sway=2, surge=1.5, twist=1.5, head=1.0, tail=1.0, ears=1.0, side=0.05),
    3: dict(name='condition walk', ticks=42, cycle=14, speed=10, kind='walk', tangent=0.4, steps={'LF': 0.0, 'RR': 0.25, 'RF': 0.5, 'LR': 0.75},
            duty={'LF': 0.3, 'RF': 0.3, 'LR': 0.36, 'RR': 0.36}, lift={'F': 3, 'R': 6}, rock=14, centre={'F': -46, 'R': 40},
            bob=1.0, pitch=1.0, roll=3.0, yaw=1.2, sway=1.5, surge=1.2, twist=1.2, head=0.6, tail=0.3, ears=0.5, side=0.05),
    4: dict(name='run', ticks=32, cycle=8, speed=35, kind='bound', tangent=0.12, steps={'LF': 0.0, 'RF': 0.06, 'RR': 0.48, 'LR': 0.54},
            duty={'LF': 0.13, 'RF': 0.13, 'LR': 0.17, 'RR': 0.17}, lift={'F': 6, 'R': 14}, rock=18, centre={'F': -46, 'R': 40},
            bob=7, pitch=5, roll=1.5, yaw=2, sway=1, surge=0, twist=2.5, head=1.4, tail=1.5, ears=1.5, side=0.1),
}


def limb_phase(P, name, t):
    """(u, stance) of limb `name` at tick t: u in [0, 1) since its touchdown."""
    u = (t / P['cycle'] - P['steps'][name]) % 1.0
    return u, u < P['duty'][name]


class Rig:
    def __init__(self, old, skeleton):
        self.old, self.sk, self.n = old, skeleton, len(skeleton)
        rest = copy.deepcopy(animsheet.slot_frames(old, self.n, 0)[0][0])
        rest[0] = [4096] * 3 + [0] * 6
        self.rest = rest
        self.rw = self.world(rest)
        self.vs = {b: np.array(old.tmd.obj_verts(o))[:, :3] for b, (o, _) in enumerate(skeleton) if o >= 0}
        self.local = {b: np.array(mmd.rot_matrix(*rest[b][3:6])) for b in range(1, self.n)}
        self.hist = {}
        # flat paws: the rest paw's heading, a few degrees of roll to level the sole
        self.flat = {b: self.rw[b, :3, :3] for b in (14, 16)}
        self.length = {b: float(np.linalg.norm(rest[b][6:9])) for b in (14, 16)}
        # rear flipper contact: the lowest outermost vertex, in the world of the rest pose
        self.tip = {}
        for b, sign in ((17, 1), (18, -1)):
            w = self.vs[b] @ self.rw[b, :3, :3].T + self.rw[b, :3, 3]
            low = [i for i in range(len(w)) if w[i][1] > float(w[:, 1].max()) - 9]
            i = max(low, key=lambda k: sign * float(w[k][0]))
            self.tip[b] = w[i]
        self.R = {b: float(np.linalg.norm(self.tip[b] - self.rw[b, :3, 3])) for b in (17, 18)}

    def world(self, f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(self.old, g))

    def spin(self, f, b, d):
        """Bone b turned by the world-axis rotation d from its rest orientation (the parents' own turns carry it on)."""
        rw = self.rw[b, :3, :3]
        set_rotation(f, b, self.local[b] @ (rw.T @ d @ rw), self.hist)

    def solid(self, f, b, rot):
        """Bone b to the world rotation `rot`, whatever its parents do."""
        w = self.world(f)
        set_rotation(f, b, w[self.sk[b][1], :3, :3].T @ rot, self.hist)

    def floor(self, f, skip=()):
        w = self.world(f)
        return max(float((self.vs[b] @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max()) for b in self.vs if b not in skip)


def limb_target(P, rig, name, t):
    """Where the limb's contact goes in the carrier's frame: (z, lift 0..1 swing arc, stance flag, u, pitch)."""
    kind = 'F' if name in FORE else 'R'
    u, stance = limb_phase(P, name, t)
    duty = P['duty'][name]
    T, speed = P['cycle'], P['speed']
    half = speed * duty * T / 2
    # a stronger left or right stroke: the sides are not the same
    gain = 1 + P['side'] * (1 if name[0] == 'L' else -1)
    half *= gain
    centre = P['centre'][kind]
    zf, zb = centre - half, centre + half
    if stance:
        z = zf + speed * u * T
        s = u / duty
        return z, 0.0, True, u, P['rock'] * (-0.35 + 1.35 * s * s) * (0.5 if kind == 'R' else P.get('rock_f', 0.3))
    q = (u - duty) / (1 - duty)
    span = (1 - duty) * T
    m = speed * span * P.get('tangent', 1.0)       # the planted velocity, carried through the lift and the landing
    # velocity-matched Hermite: leave backwards at the planted speed, arrive at it
    h00, h10, h01, h11 = 2 * q ** 3 - 3 * q ** 2 + 1, q ** 3 - 2 * q ** 2 + q, -2 * q ** 3 + 3 * q ** 2, q ** 3 - q ** 2
    z = h00 * zb + h10 * m + h01 * zf + h11 * m
    pitch = (-0.35 + 1.35 * (0.5 + 0.5 * math.cos(math.pi * q))) * P['rock'] * (0.5 if kind == 'R' else P.get('rock_f', 0.3))
    return z, math.sin(math.pi * q) ** 2, False, u, pitch + (8 if kind == 'R' else 2) * math.sin(math.pi * q) ** 2


# ------------------------------------------------------------------ face, ears, mane, tail
def idle_head(t, n):
    """Where the head looks (yaw to the animal's left), tilt (roll to its right) and nods over the idle, in degrees."""
    yaw = track([(0, 0), (8, 0), (15, 22), (26, 22), (33, -2), (42, -14), (50, -14), (56, 6), (62, 6), (70, 0)], t, n)
    roll = track([(0, 0), (12, 0), (18, 6), (26, 6), (34, -1), (44, -7), (52, -7), (58, 0)], t, n)
    nod = track([(0, 0), (10, 0), (15, -6), (26, -6), (34, 4), (42, 0), (50, 7), (58, 0)], t, n)
    return yaw, roll, nod


def author(old, skeleton, slot):
    rig = Rig(old, skeleton)
    sk = skeleton
    rw = rig.rw
    if slot == 0:
        return author_idle(rig, old, skeleton)
    P = PROFILE[slot]
    N, T, speed = P['ticks'], P['cycle'], P['speed']
    tired, run = slot == 3, slot == 4
    reports = dict(min_margin=1e9, floor=-1e9, errors=[])
    # --- the drive signals every soft part follows (periodic over the clip)
    ph = lambda t: 2 * math.pi * t / T  # noqa: E731
    head_pitch = [P['head'] * (2.2 * math.sin(2 * ph(t) - 0.5) + (6 if tired else 0)) for t in range(N)]
    head_yaw = [P['head'] * (4 * math.sin(2 * math.pi * t / N * (N // T) / 2 + 0.3) + 5 * track([(0, 0), (N * 0.2, 0), (N * 0.35, 1), (N * 0.55, 1), (N * 0.7, -0.6), (N * 0.85, 0)], t, N)) for t in range(N)]
    head_roll = [P['head'] * (-2.5 * math.sin(ph(t) - 0.4) + 2.5 * track([(0, 0), (N * 0.3, 0), (N * 0.45, 1), (N * 0.6, 0), (N * 0.8, -1), (N * 0.95, 0)], t, N)) for t in range(N)]
    mane = Spring(0.14, 0.26).run([-3.5 * P['tail'] * math.sin(2 * ph(t) - 0.2) - 1.5 * math.sin(ph(t)) for t in range(N)])
    crest = Spring(0.10, 0.20).run([-5 * P['tail'] * math.sin(2 * ph(t) - 0.2) for t in range(N)])
    tail_yaw = Spring(0.16, 0.22).run([P['tail'] * (-14 * math.sin(ph(t) - 0.1)) for t in range(N)])
    tail2_yaw = Spring(0.12, 0.2).run([P['tail'] * (-14 * math.sin(ph(t) - 0.1)) for t in range(N)])
    tail_pitch = Spring(0.12, 0.25).run([P['tail'] * (5 * math.sin(2 * ph(t) - 0.6) + (-10 if tired else 6)) for t in range(N)])
    ear_flap = Spring(0.13, 0.2).run([P['ears'] * (7 * math.sin(2 * ph(t) - 0.3) + (-14 if tired else 0)) for t in range(N)])
    ear_flap2 = Spring(0.1, 0.18).run([P['ears'] * (9 * math.sin(2 * ph(t) - 0.55)) for t in range(N)])
    ear_out = Spring(0.12, 0.2).run([P['ears'] * (5 * math.sin(ph(t) - 0.2)) for t in range(N)])
    samples = []
    for t in range(N):
        f = copy.deepcopy(rig.rest)
        # ---- body: bob, sway, surge, roll, pitch, yaw
        w1 = ph(t)
        if run:
            bob = P['bob'] * (0.5 - 0.5 * math.cos(2 * w1 - 0.9))          # up in the flights, down on the landings
            pitch = P['pitch'] * math.sin(w1 - 0.9 + 0.9)
        else:
            bob = P['bob'] * (0.5 + 0.5 * math.cos(2 * w1 - 0.3))
            pitch = P['pitch'] * math.sin(2 * w1 + 0.4)
        roll = -P['roll'] * math.sin(w1) if not run else P['roll'] * math.sin(w1 * 2)
        yaw = P['yaw'] * math.sin(w1 + 0.6)
        surge = P['surge'] * math.sin(2 * w1 + 1.0)
        sway = P['sway'] * math.sin(w1 + 1.57)
        rig.spin(f, PELVIS, turn(pitch, yaw, roll))
        rig.spin(f, TORSO, turn(0.6 * -pitch + 0.3 * P['twist'] * math.sin(2 * w1), -P['twist'] * math.sin(w1 + 0.5) * 1.3, -0.5 * roll + 0.4 * math.sin(w1 + 0.8)))
        f[PELVIS][6] += round(sway)
        f[PELVIS][8] += round(surge)
        carrier = -bob
        f[PELVIS][7] = rig.rest[PELVIS][7] + round(carrier)
        # ---- the soft parts (their own spins; limbs come after)
        rig.spin(f, HEAD, turn(head_pitch[t], head_yaw[t], head_roll[t]))
        rig.spin(f, MANE, turn(mane[t], 0, 0.5 * mane[t]))
        rig.spin(f, CREST, turn(crest[t], 0, 0))
        for chain, sg in ((EAR_R, 1), (EAR_L, -1)):
            rig.spin(f, chain[0], turn(0, 0, sg * (-ear_flap[t] * 0.7)))
            rig.spin(f, chain[1], turn(ear_flap2[t] * 0.8, 0, sg * ear_out[t]))
            rig.spin(f, chain[2], turn(ear_flap2[t] * 0.6, 0, sg * ear_out[t] * 0.7))
        rig.spin(f, TAIL[0], turn(tail_pitch[t], tail_yaw[t], 0))
        rig.spin(f, TAIL[1], turn(0.5 * tail_pitch[t], tail2_yaw[t], 0))
        # ---- the floor under the body without its limbs
        up = max(0.0, rig.floor(f, skip=LIMBS) - (FLOOR_LIMIT - 0.5))
        f[PELVIS][7] -= math.ceil(up)
        # ---- the body rises over the planted arms (a post of fixed length is longest when it stands upright)
        vault(rig, P, f, t)
        # ---- four contacts
        solve_limbs(rig, P, f, t, reports)
        f[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, -speed * t]
        samples.append(f)
    return samples, reports


def vault(rig, P, f, t):
    """Lifts the pelvis so that a planted arm reaches the floor with its natural lateral offset: the post is longer
    when it stands upright, so the body rises over it and falls again at the touchdown and the lift-off."""
    raised = 0.0
    for name, (hip, foot, sign) in FORE.items():
        z, lift, stance, u, pitch = limb_target(P, rig, name, t)
        if not stance:
            continue
        sph = u / P['duty'][name]
        window = ease(min(1.0, min(sph, 1 - sph) / 0.25))
        rf, dz, sole = motionsecondary.rolling_foot(rig.vs[foot].tolist(), rig.flat[foot].tolist(), pitch)
        h = rig.world(f)[hip, :3, 3]
        v = math.sqrt(max(rig.length[foot] ** 2 - LAT ** 2 - (z + dz - h[2]) ** 2, 0.0))
        raised = max(raised, window * (h[1] - (FLOOR_Y - sole - v)))
    f[PELVIS][7] -= round(P.get('vault', 1.0) * raised)


def solve_limbs(rig, P, f, t, reports):
    sk = rig.sk
    for name, (hip, foot, sign) in FORE.items():
        z, lift, stance, u, pitch = limb_target(P, rig, name, t)
        lift_h = P['lift']['F'] * lift
        rf, dz, sole = motionsecondary.rolling_foot(rig.vs[foot].tolist(), rig.flat[foot].tolist(), pitch)
        rf = np.array(rf)
        w = rig.world(f)
        h = w[hip, :3, 3]
        L = rig.length[foot]
        wy = FLOOR_Y - sole - lift_h
        v = min(wy - h[1], VMAX)           # a body flying high leaves the paw hanging a little above the floor
        gz = z + dz
        r2 = L * L - v * v
        rad2 = r2 - (gz - h[2]) ** 2
        reports['min_margin'] = min(reports['min_margin'], rad2 - DX_MIN ** 2)
        if rad2 < DX_MIN ** 2:             # out of reach: stop the paw at the edge of it (a slide of a few units)
            reports['errors'].append((name, t, round(rad2 - DX_MIN ** 2, 1)))
            span = math.sqrt(max(r2 - DX_MIN ** 2, 0))
            gz = h[2] + max(-span, min(span, gz - h[2]))
            rad2 = DX_MIN ** 2 if r2 < DX_MIN ** 2 else r2 - (gz - h[2]) ** 2
        dx = sign * math.sqrt(rad2)
        goal = np.array([h[0] + dx, wy, gz])
        ref = rig.rw[foot, :3, 3] - rig.rw[hip, :3, 3]
        rig.solid(f, hip, align(ref, goal - h) @ rig.rw[hip, :3, :3])
        rig.solid(f, foot, rf)
    for name, (b, sign) in REAR.items():
        z, lift, stance, u, pitch = limb_target(P, rig, name, t)
        lift_h = P['lift']['R'] * lift
        w = rig.world(f)
        pivot = w[b, :3, 3]
        R = rig.R[b]
        wy = FLOOR_Y - lift_h
        ref = rig.tip[b] - rig.rw[b, :3, 3]
        for _ in range(3):
            v = wy - pivot[1]
            rad2 = R * R - v * v - (z - pivot[2]) ** 2
            reports['min_margin'] = min(reports['min_margin'], rad2)
            if rad2 < 1:
                reports['errors'].append((name, t, round(rad2, 1)))
                rad2 = 1
            goal = np.array([pivot[0] + sign * math.sqrt(rad2), wy, z])
            base = align(ref, goal - pivot) @ rig.rw[b, :3, :3]
            axis = (goal - pivot) / np.linalg.norm(goal - pivot)
            best = None
            for roll in range(-60, 61, 4):
                rot = axis_turn(axis, roll) @ base
                low = float((rig.vs[b] @ rot.T)[:, 1].max() + pivot[1])
                score = low + 0.01 * abs(roll)
                if best is None or score < best[0]:
                    best = (score, low, rot)
            if best[1] <= FLOOR_Y + 0.5:
                break
            wy -= best[1] - FLOOR_Y
        rig.solid(f, b, best[2])


def axis_turn(a, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    x, y, z = [float(v) for v in a]
    return np.array([[c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
                     [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
                     [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)]])


def author_idle(rig, old, skeleton):
    n = 72
    reports = dict(min_margin=1e9, errors=[])
    samples = []
    drive = [idle_head(t, n) for t in range(n)]
    hy = [d[0] for d in drive]
    hr = [d[1] for d in drive]
    hn = [d[2] for d in drive]
    mane = Spring(0.12, 0.3).run([-0.6 * y for y in hn[:]])
    mane_y = Spring(0.12, 0.3).run([0.2 * y for y in hy])
    crest = Spring(0.09, 0.22).run([-0.9 * x for x in hn])
    ear_perk = [track([(0, 0), (14, 0), (18, 1), (27, 1), (31, 0), (46, 0), (50, -.5), (53, 0)], t, n) for t in range(n)]
    ear_flick = [track([(0, 0), (40, 0), (42, 1), (44, -0.4), (46, 0.6), (49, 0)], t, n) for t in range(n)]
    ear_s = Spring(0.2, 0.22).run(ear_perk)
    flick_s = Spring(0.4, 0.2).run(ear_flick)
    tail_yaw = [track([(0, 0), (6, 12), (12, 0), (18, -12), (24, 0), (30, 14), (36, 0), (60, 0), (64, -10), (68, 8), (71, 0)], t, n) for t in range(n)]
    tail_yaw = Spring(0.1, 0.18).run(tail_yaw)
    tail_pitch = Spring(0.1, 0.25).run([4 * math.sin(2 * math.pi * t / 24 - 0.5) + 3 * math.sin(2 * math.pi * t / n) for t in range(n)])
    for t in range(n):
        f = copy.deepcopy(rig.rest)
        w = 2 * math.pi * t / 24
        breath = math.sin(w)
        rig.spin(f, PELVIS, turn(0.5 * breath, 0.8 * hy[t] / 22 * 1.0, 0.8 * hr[t] / 7))
        rig.spin(f, TORSO, turn(-1.6 * breath + 0.3 * hn[t], 0.25 * hy[t], 0.2 * hr[t]))
        rig.spin(f, HEAD, turn(hn[t] + 1.5 * math.sin(w - 0.8), hy[t], hr[t]))
        rig.spin(f, MANE, turn(mane[t] + 1.5 * math.sin(w - 1.4), mane_y[t], 0))
        rig.spin(f, CREST, turn(crest[t] + 2 * math.sin(w - 1.6), 0, 0))
        for chain, sg, flick in ((EAR_R, 1, 0.0), (EAR_L, -1, 1.0)):
            rig.spin(f, chain[0], turn(0, 0, sg * (4 * ear_s[t] + 3 * math.sin(w - 1.0)) * -1))
            fl = flick_s[t] if flick == 0.0 else 0.3 * flick_s[t]
            rig.spin(f, chain[1], turn(7 * fl, 0, sg * (3 * ear_s[t])))
            rig.spin(f, chain[2], turn(9 * fl, 0, sg * (2 * ear_s[t] - 4 * math.sin(w - 1.8))))
        rig.spin(f, TAIL[0], turn(tail_pitch[t], tail_yaw[t], 0))
        rig.spin(f, TAIL[1], turn(0.6 * tail_pitch[t], 0.7 * tail_yaw[t], 0))
        # breathing and a slow weight shift lift the body a little off the floor, then the soles are put back
        up = max(0.0, rig.floor(f, skip=LIMBS) - (FLOOR_LIMIT - 0.5))
        f[PELVIS][7] -= math.ceil(up)
        # rear flipper twitch: right rear paddle lifts and settles
        tw = track([(0, 0), (52, 0), (56, 1), (60, 0)], t, n)
        tl = track([(0, 0), (20, 0), (23, 1), (26, 0)], t, n)
        for b, g, sg in ((17, tw, 1), (18, tl, -1)):
            w4 = rig.world(f)
            wb = w4[b, :3, :3]
            pivot = w4[b, :3, 3]
            ref = rig.tip[b] - rig.rw[b, :3, 3]
            goal = np.array(rig.tip[b])
            goal = goal - rig.rw[b, :3, 3] + pivot
            goal[1] -= 14 * g
            goal[0] -= sg * 6 * g
            rig.solid(f, b, align(ref, goal - pivot) @ rig.rw[b, :3, :3])
        # the front paws stay planted: the body's tiny roll and pitch are answered by the arms, soles on the floor
        for name, (hip, foot, sign) in FORE.items():
            rf, dz, sole = motionsecondary.rolling_foot(rig.vs[foot].tolist(), rig.flat[foot].tolist(), 0)
            rf = np.array(rf)
            w4 = rig.world(f)
            h = w4[hip, :3, 3]
            L = rig.length[foot]
            lift = 7 * track([(0, 0), (30, 0), (33, 1), (37, 0)], t, n) * (1 if name == 'LF' else 0)
            gz = -66 + dz - 0
            wy = FLOOR_Y - sole - lift
            v = wy - h[1]
            # the paw stays where it stood in the rest pose (x and z)
            gx = rig.rw[foot, 0, 3]
            rad2 = L * L - v * v - (gz - h[2]) ** 2
            dx = sign * math.sqrt(max(rad2, 1))
            goal = np.array([h[0] + dx, wy, gz])
            ref = rig.rw[foot, :3, 3] - rig.rw[hip, :3, 3]
            rig.solid(f, hip, align(ref, goal - h) @ rig.rw[hip, :3, :3])
            rig.solid(f, foot, rf)
        f[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
        samples.append(f)
    return samples, reports


def build(data, skeleton, tex):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('Gomamon scoot requires its pinned 22-bone source')
    n = len(skeleton)
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = n
    old = mmd.MMD.parse(data, n)
    old.type = SPECIES
    new = copy.deepcopy(old)
    report = []
    for slot in (0, 2, 3, 4):
        samples, rep = author(old, skeleton, slot)
        ticks = len(samples)
        speed = PROFILE[slot]['speed'] if slot else 0
        last = copy.deepcopy(samples[0])
        last[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, -speed * ticks]
        samples = samples + [last]
        anim = mmd.encode_anim(samples, n, loop_sample=0, events=gomamon_face.events(slot), tol=1)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(anim)
        report.append(dict(slot=slot, ticks=ticks, **{k: v for k, v in rep.items()}))
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = mmd.MMD.parse(result, n)
    actual.type = SPECIES
    assert old.tmd.build() == actual.tmd.build()
    assert changed_programs(old, actual) == [0, 2, 3, 4], changed_programs(old, actual)
    face = mmd.Tim4(tex)
    gomamon_face.stamp(face)
    new_tex = face.to_bytes()
    used = 8 + face.clen + 12 + 128 * gomamon_face.FRAME_Y      # the header, the palettes and texture rows 0..79
    assert new_tex[:used] == tex[:used], 'the used rows of the texture stay'
    assert len(new_tex) == len(tex)
    storage = motionstorage.require(result, n)
    return result, new_tex, dict(species=SPECIES, source_sha256=SOURCE, output_sha256=hashlib.sha256(result).hexdigest(), changed_slots=[0, 2, 3, 4], clips=report, storage=storage)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--source-tim', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--out-tim', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/217-gomamon.json').read_text())['model']['skeleton']
    data, tex, proof = build(a.source.read_bytes(), skeleton, a.source_tim.read_bytes())
    a.out.write_bytes(data)
    a.out_tim.write_bytes(tex)
    text = json.dumps(proof, indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text[:3000], end='')


if __name__ == '__main__':
    main()
