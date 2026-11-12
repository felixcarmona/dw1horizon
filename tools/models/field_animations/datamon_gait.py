"""Datamon's idle, walk, tired walk and run (species 294, field slots 0, 2, 3, 4), written from the feet up.

Offline authoring script (the model it makes is stored with `tools/models/edit.py put 294`):

    python -m tools.models.field_animations.datamon_gait --source SRC.MMD --out-dir DIR

where SRC is the previously stored model (sha256 below), from `edit.py get 294`.

The rig: a capsule (bone 1: glass dome and torso in one piece) that carries four short boots, each a chain of a hip
piece, two small joint pieces and a flat boot (2-5 front right, 6-9 front left, 10-13 rear right, 14-17 rear left), two
huge arms (19-22 right, 24-27 left: shoulder, upper arm, wrist and a big hand that points forward) and two small
shoulder fins (18, 23). Forward is -z.

What was wrong. The clips were a quick diagonal shuffle of 11, 16 and 9 ticks with the boots sliding 60-70 % of the
ground speed, a torso that only rocked and arms that were a copy of one another's swing: a clockwork loop that repeated
every third of a second.

What the clips are now:
- The torso is placed in the world every tick (height, sway, roll, pitch, yaw) and everything on it (hips, arms, fins)
  follows. Each boot is a point on the floor that stays put while the body passes over it (stance), then lifts, swings
  forward and lands again; the boot rolls heel to toe a little and is kept flat on the floor. The chain of small pieces
  between hip and boot is turned and telescoped to reach it (`EXT` bounds how far the chain may stretch or fold), and
  the torso height is solved from the planted boots, so the weight drops onto a landing (the chain folds) and rises.
- The boots walk as a pace: the two boots of one side step together (the front one a little ahead), which keeps a
  front and a rear boot of one side from meeting and gives a heavy side-to-side rolling carriage. The torso leans
  towards the side it stands on, twists against the stride and nods with each landing.
- The loops hold two strides, and the arms live on that longer beat: heavy pendulums that follow the torso late, each
  joint a little later than the one before it, the left and the right in different phases, so the loop does not repeat
  the same pose twice a second. The fins flutter after the torso.
- The idle breathes slowly over planted boots, shifts the weight from side to side and scans to the left and the
  right, with the arms trailing the turn; the eyes blink as before.
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
import mmd  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402

SPECIES = 294
SOURCE = '15055b10cffc76ca7f4602496a108568d27673f59f356fc9447c229b5a3f7415'   # `edit.py get 294` before this change
PARENTS = [-1, 0, 1, 2, 3, 4, 1, 6, 7, 8, 1, 10, 11, 12, 1, 14, 15, 16, 1, 1, 19, 20, 21, 1, 1, 24, 25, 26]
BODY = 1
LEGS = {'FR': (2, 1, -1), 'FL': (6, -1, -1), 'RR': (10, 1, 1), 'RL': (14, -1, 1)}      # hip bone, side (x > 0 = +1), end (z)
ARMS = {'R': (19, 20, 21, 22, 1), 'L': (24, 25, 26, 27, -1)}      # shoulder, upper arm, wrist, hand, side
FINS = {'R': (18, 1), 'L': (23, -1)}
SLOTS = (0, 2, 3, 4, 33)     # slot 33 (the battle idle) shares the idle's program
PROGRAMS = (0, 2, 3, 4)
FLOOR = -3.0                 # the lowest vertex of the rest boots: the model's own ground
TAU = 2 * math.pi
RESIDENT_LIMIT = 100352
EXT = (-18.0, 28.0)          # how far a leg's chain may fold or stretch against its rest length, in units
IDLE_TICKS = 72
# keyframe tolerances (units of 1/4096 turn or of length): tight for the torso, the legs and the boots, looser for the arms
TOL = {None: 1, **{b: 4 for b in (18, 19, 20, 21, 22, 23, 24, 25, 26, 27)}}
TURN = (0.3, 0.4, 0.5)      # how much of the leg's swing each small piece of its chain turns (keeps the angles away from gimbal lock)


def rx(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def ry(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rz(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def swing(a, b):
    """Shortest rotation taking direction a to direction b."""
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    v = np.cross(a, b)
    c = float(a @ b)
    if c < -1 + 1e-9:
        raise ValueError('a half turn')
    k = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + k + k @ k / (1 + c)


def part(R, f):
    """The rotation R taken a fraction f of the way (about its own axis)."""
    c = max(-1.0, min(1.0, (np.trace(R) - 1) / 2))
    a = math.acos(c)
    if a < 1e-9:
        return np.eye(3)
    axis = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])
    axis = axis / np.linalg.norm(axis)
    k = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    return np.eye(3) + math.sin(f * a) * k + (1 - math.cos(f * a)) * k @ k


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def hold(t, keys):
    """Smooth interpolation through (tick, value) keys, flat tangents."""
    for (a, x), (b, y) in zip(keys, keys[1:]):
        if a <= t <= b:
            return x + (y - x) * smooth((t - a) / (b - a))
    return keys[-1][1]


def wave(phase, lag=0.0, rate=1, harmonic=0.0, h_lag=0.07):
    """A sine of the loop phase (closed for whole `rate`s), with a second harmonic so it is not a pure sinusoid."""
    return math.sin(TAU * rate * (phase - lag)) + harmonic * math.sin(TAU * 2 * rate * (phase - lag - h_lag))


class Rig:
    def __init__(self, model, skeleton):
        self.m = model
        self.n = len(skeleton)
        pose = animsheet.slot_frames(model, self.n, 0)[0][0]
        self.rest = [list(b) for b in pose]
        self.rest[0] = [4096] * 3 + [0] * 6
        self.Rl = [np.array(mmd.rot_matrix(*v[3:6])) for v in self.rest]
        self.off = [np.array(v[6:9], float) for v in self.rest]
        self.verts = {b: np.array([v[:3] for v in model.tmd.obj_verts(o)], float) for b, (o, _) in enumerate(skeleton) if o >= 0}
        self.Wr, self.Pr = self.fk({})
        self.hist = {}
        # per leg: the chain's rest vector hip -> boot, and the sole anchor in the boot's own frame
        self.sole = {}
        for name, (hip, sd, end) in LEGS.items():
            foot = hip + 3
            w = self.verts[foot] @ self.Wr[foot].T + self.Pr[foot]
            lowest = w[:, 1].max()
            S0 = w[w[:, 1] > lowest - 1.5].mean(0)
            self.sole[name] = self.Wr[foot].T @ (S0 - self.Pr[foot])
        self.rest_floor = max(float((self.verts[h + 3] @ self.Wr[h + 3].T + self.Pr[h + 3])[:, 1].max()) for h, _, _ in LEGS.values())
        self.rest_sole = {name: self.Wr[hip + 3] @ self.sole[name] + self.Pr[hip + 3] for name, (hip, _, _) in LEGS.items()}

    def fk(self, driven):
        """World rotations and positions; `driven` {bone: (W, P or None)} replaces the inherited ones."""
        W, P = [None] * self.n, [None] * self.n
        for b in range(self.n):
            par = PARENTS[b]
            if par < 0:
                W[b], P[b] = np.eye(3), np.zeros(3)
                continue
            Wb, Pb = driven.get(b, (None, None))
            W[b] = Wb if Wb is not None else W[par] @ self.Rl[b]
            P[b] = Pb if Pb is not None else P[par] + W[par] @ self.off[b]
        return W, P

    def body(self, ch):
        """Rotation (about the torso's own origin) and origin of the torso for ch = dict(p, yaw, pitch, roll)."""
        Rd = ry(ch.get('yaw', 0)) @ rx(ch.get('pitch', 0)) @ rz(ch.get('roll', 0))
        return Rd, self.Pr[BODY] + np.array(ch['p'], float)

    def hip(self, name, ch):
        Rd, Pc = self.body(ch)
        h = LEGS[name][0]
        return Pc + Rd @ (self.Pr[h] - self.Pr[BODY])

    def place_foot(self, name, spec):
        """The boot whose sole anchor stands at spec['S'] (y moved so its lowest vertex rests on the floor when planted, or is
        lifted when it would sink), pitched spec['phi'] (positive = toe down) and turned spec['yaw']."""
        hip, sd, end = LEGS[name]
        foot = hip + 3
        target = np.array(spec['S'], float)
        for k in range(4):
            R5 = rx(spec['phi']) @ ry(spec.get('yaw', 0.0)) @ self.Wr[foot]
            P5 = target - R5 @ self.sole[name]
            low = float((self.verts[foot] @ R5.T + P5)[:, 1].max())
            if k < 3 and (spec.get('plant') or low > FLOOR) and abs(low - FLOOR) > 0.02:
                target = target + np.array([0.0, FLOOR - low, 0.0])
        return dict(R=R5, P=P5, S=target, plant=bool(spec.get('plant')))

    def pose(self, ch, feet, arms, fins):
        """ch: torso; feet: place_foot results; arms: {'R': [(pitch, yaw, roll) for shoulder, upper arm, wrist, hand]};
        fins: {'R': roll}. Arm angles are turns about the torso's axes at each joint, cumulative down the arm."""
        Rd, Pc = self.body(ch)
        Wb = Rd @ self.Wr[BODY]
        driven = {BODY: (Wb, Pc)}
        ext = {}
        for name, (hip, sd, end) in LEGS.items():
            g = feet[name]
            chain = [hip, hip + 1, hip + 2]
            Ph = Pc + Rd @ (self.Pr[hip] - self.Pr[BODY])
            d = g['P'] - Ph
            D0 = Rd @ (self.Pr[hip + 3] - self.Pr[hip])
            Rs = swing(D0, d)
            a = D0 / np.linalg.norm(D0)
            ratio = np.linalg.norm(d) / np.linalg.norm(D0)
            for b, share in zip(chain, TURN):
                v = Rd @ (self.Pr[b] - self.Pr[hip])
                driven[b] = (part(Rs, share) @ Rd @ self.Wr[b], Ph + Rs @ (v + a * (v @ a) * (ratio - 1)))
            driven[hip + 3] = (g['R'], g['P'])
            ext[name] = float(np.linalg.norm(d) - np.linalg.norm(D0))
        for side, (sh, up, wr, hand, sd) in ARMS.items():
            cum = np.eye(3)
            for b, ang in zip((sh, up, wr, hand), arms[side]):
                cum = rx(ang[0]) @ ry(ang[1]) @ rz(ang[2]) @ cum
                driven[b] = (Rd @ cum @ self.Wr[b], None)
        for side, (b, sd) in FINS.items():
            driven[b] = (Rd @ rz(fins[side]) @ self.Wr[b], None)
        W, P = self.fk(driven)
        return W, P, ext

    def encode(self, W, P, root_z):
        """Engine pose entries from world transforms (euler angles continuous per bone through self.hist)."""
        pose = [[4096] * 3 + [0, 0, 0, 0, 0, root_z]]
        for b in range(1, self.n):
            par = PARENTS[b]
            L = W[par].T @ W[b]
            t = W[par].T @ (P[b] - P[par])
            e = mmd.matrix_euler(L.tolist(), self.hist.get(b))
            self.hist[b] = e
            pose.append([4096] * 3 + [int(round(x)) for x in e] + [int(round(x)) for x in t])
        return pose


# --------------------------------------------------------------------------------------------------------- arms
def arm_angles(ph, side, cfg, body_rock):
    """The four joints of an arm at loop phase `ph` (a fraction of the whole loop): heavy pendulums that follow the torso
    late, each joint later than the one before, the two arms in different phases. Returns [(pitch, yaw, roll)] x 4."""
    sg = side
    lag0 = cfg['arm_lag'] * (1.0 if sg > 0 else 1.45)
    sw = cfg['arm_phase'] * (0.0 if sg > 0 else 1.0)
    out = []
    for j, (gain, lag) in enumerate(((1.0, 0.0), (0.8, 0.045), (0.6, 0.09), (0.7, 0.14))):
        q = ph - lag0 - lag - sw
        pitch = cfg['arm_pitch'][j] * wave(q, 0, cfg['rate'], 0.22) + cfg['arm_pitch0'][j] + (cfg['left_up'] if sg < 0 and j == 0 else 0.0)
        yaw = cfg['arm_yaw'][j] * wave(q - 0.11, 0, cfg['rate'], 0.2) * sg + cfg['arm_yaw0'][j] * sg \
            + (cfg.get('left_yaw', 0.0) if sg < 0 and j == 0 else 0.0)
        roll = cfg['arm_roll'][j] * wave(q - 0.2, 0, cfg['rate'], 0.2) + cfg['arm_roll0'][j] * sg
        out.append((pitch * gain, yaw * gain, roll * gain))
    return out


# --------------------------------------------------------------------------------------------------------- the clips
# T: ticks of one stride (each side steps once); cycles: strides in the loop; v: root speed in units a tick;
# duty: stance share; step: stance sweep in units
GAITS = {
    2: dict(name='walk', T=12, cycles=3, tangent=1.0, hold=0.0, kick=1.0, land=1.0, steep=2.0, v=15, duty=0.38, rear_lag=0.07,
            dy0=14.0, sway=9.0, roll=3.4, roll_lag=0.04, pitch0=1.5, pitch=1.6, yaw=3.0, drop=7.0, surge=3.0,
            lift=19.0, heel=-2.0, push=3.0, spread=15.0, fyaw=3.0, var=0.18,
            rate=1, arm_lag=0.04, arm_phase=0.4,
            arm_pitch=(1.8, 1.5, 1.3, 1.8), arm_pitch0=(-4.0, -1.0, -1.0, 0.0),
            arm_yaw=(6.0, 5.0, 4.0, 6.0), arm_yaw0=(-30.0, -6.0, 0.0, 0.0), left_yaw=6.0,
            arm_roll=(1.5, 1.5, 1.5, 2.0), arm_roll0=(0.0, 0.0, 0.0, 0.0), fin=7.0, left_up=-5.0),
    3: dict(name='tired walk', T=14, cycles=2, tangent=1.0, hold=0.0, kick=2.0, land=1.5, steep=2.0, v=11, duty=0.35, rear_lag=0.07,
            dy0=15.0, sway=7.0, roll=2.6, roll_lag=0.05, pitch0=5.0, pitch=1.2, yaw=2.2, drop=6.0, surge=2.0,
            lift=14.0, heel=-2.0, push=3.0, spread=18.0, fyaw=2.0, var=0.2,
            rate=1, arm_lag=0.06, arm_phase=0.4,
            arm_pitch=(1.5, 1.3, 1.2, 1.5), arm_pitch0=(-1.0, 0.0, 0.0, 0.0),
            arm_yaw=(4.2, 3.5, 3.0, 4.2), arm_yaw0=(-30.0, -6.0, 0.0, 0.0), left_yaw=6.0,
            arm_roll=(1.2, 1.2, 1.2, 1.5), arm_roll0=(0.0, 0.0, 0.0, 0.0), fin=4.0, left_up=-5.0),
    4: dict(name='run', T=7, cycles=3, tangent=0.6, hold=0.0, kick=2.2, land=1.3, steep=0, v=36, duty=0.25, rear_lag=0.0,
            dy0=14.0, sway=6.0, roll=2.6, roll_lag=0.03, pitch0=9.0, pitch=2.4, yaw=3.5, drop=8.0, surge=4.0,
            lift=30.0, heel=-3.0, push=5.0, spread=6.0, fyaw=3.0, var=0.15, flight=14.0,
            rate=1, arm_lag=0.035, arm_phase=0.4,
            arm_pitch=(2.6, 2.2, 2.0, 2.4), arm_pitch0=(-5.0, -1.0, -1.0, -1.0),
            arm_yaw=(7.0, 5.5, 5.0, 6.5), arm_yaw0=(-30.0, -6.0, 0.0, 0.0), left_yaw=6.0,
            arm_roll=(2.5, 2.5, 2.5, 3.0), arm_roll0=(0.0, 0.0, 0.0, 0.0), fin=10.0, left_up=-7.0),
}


def steep(f, p=1.5):
    """0..1 -> 0..1 that is quick at both ends and slow in the middle: a boot leaves and meets the ground fast and hangs high."""
    u = 2 * f - 1
    return 0.5 + 0.5 * math.copysign(abs(u) ** p, u)


def foot_state(duty, ph, td):
    """(planted?, fraction through the stance or swing) of a foot that lands at stride phase `td`."""
    u = (ph - td) % 1.0
    return (True, u / duty) if u < duty else (False, (u - duty) / (1 - duty))


def solve_dy(rig, ch, feet, goal=0.0):
    """Torso height (offset from rest, y down) at which the planted boots' mean chain length is `goal` units off the rest
    length; None when none is planted."""
    planted = [n for n in LEGS if feet[n]['plant']]
    if not planted:
        return None
    lo, hi = -40.0, 80.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        c = dict(ch, p=(ch['p'][0], mid, ch['p'][2]))
        e = np.mean([np.linalg.norm(feet[n]['P'] - rig.hip(n, c)) - np.linalg.norm(rig.Pr[LEGS[n][0] + 3] - rig.Pr[LEGS[n][0]]) for n in planted])
        if e > goal:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def gait(rig, cfg):
    T, C, v, duty = cfg['T'], cfg['cycles'], cfg['v'], cfg['duty']
    L = T * C
    sweep = v * duty * T
    rig.hist = {}
    td = {'FR': 0.0, 'FL': 0.5, 'RR': cfg['rear_lag'], 'RL': 0.5 + cfg['rear_lag']}
    flight = cfg.get('flight', 0.0)
    chs, feet_t = [], []
    for t in range(L):
        ph = (t % T) / T
        c = t // T
        k = 1.0 + cfg['var'] * (1 if c % 2 else -1) * 0.5          # the two strides of the loop differ a little
        # torso: leans to the side it stands on (+1 when the right boots are mid-stance), nods and twists with the stride
        right = math.cos(TAU * (ph - duty / 2))
        sx = cfg['sway'] * k * (right + 0.15 * math.cos(TAU * 3 * (ph - duty / 2 + 0.03)))
        roll = cfg['roll'] * k * (math.cos(TAU * (ph - duty / 2 - cfg['roll_lag'])) + 0.18 * math.cos(TAU * 3 * (ph - duty / 2 - 0.02)))
        pitch = cfg['pitch0'] + cfg['pitch'] * k * math.cos(4 * math.pi * (ph - duty / 2 - 0.03))
        yaw = cfg['yaw'] * k * (-math.cos(TAU * (ph - duty / 2)) + 0.12 * math.cos(TAU * 3 * (ph - 0.02)))
        z = cfg['surge'] * k * math.cos(4 * math.pi * (ph - duty / 2 - 0.06))
        chs.append(dict(p=(sx, 0.0, z), yaw=yaw, pitch=pitch, roll=roll))
        feet = {}
        for name, (hip, sd, end) in LEGS.items():
            planted, f = foot_state(duty, ph, td[name])
            S0 = rig.rest_sole[name]
            x = S0[0] + sd * cfg['spread']
            zc = S0[2]
            if planted:
                z0 = zc - sweep / 2 + sweep * f
                y, phi = FLOOR, cfg['heel'] + (cfg['push'] - cfg['heel']) * f
                yaw_f = 0.0
            else:
                # a Hermite arc that leaves and meets the ground's own speed, so a landing and a lift-off are at rest in the world
                # the boot rises (and lands) while still moving with the ground, then swings across in between: a Hermite arc
                # whose ends match the ground's own speed, so a lift-off and a landing are at rest in the world
                m = cfg['tangent'] * v * (1 - duty) * T
                h = cfg['hold']
                if f < h:
                    z0 = zc + sweep / 2 + m * f
                elif f > 1 - h:
                    z0 = zc - sweep / 2 - m * (1 - f)
                else:
                    u = (f - h) / (1 - 2 * h)
                    p0, p1, kt = zc + sweep / 2 + m * h, zc - sweep / 2 - m * h, m * (1 - 2 * h)
                    z0 = p0 * (2 * u ** 3 - 3 * u ** 2 + 1) + kt * cfg['kick'] * (u ** 3 - 2 * u ** 2 + u) \
                        + p1 * (-2 * u ** 3 + 3 * u ** 2) + kt * cfg.get('land', 1.0) * (u ** 3 - u ** 2)
                # the front boots rise higher than the rear ones, and each stride favours the other side
                share = (1.12 if end < 0 else 0.9) * (1.0 + 0.1 * sd * (1 if c % 2 else -1))
                y = FLOOR - cfg['lift'] * k * share * math.sin(math.pi * (f ** 0.6 if cfg.get('steep', 1.5) == 0 else steep(f, cfg.get('steep', 1.5)))) ** 0.9
                phi = cfg['push'] + (cfg['heel'] - cfg['push']) * smooth(min(1.0, 1.0 * f)) + 6.0 * math.sin(math.pi * f) * (0.4 if flight == 0 else 1.0)
                yaw_f = sd * cfg['fyaw'] * math.sin(math.pi * f)
            feet[name] = rig.place_foot(name, dict(S=(x, y, z0), phi=phi, yaw=yaw_f, plant=planted))
        feet_t.append(feet)
    dys = [(cfg['dy0'] if any(f['plant'] for f in g.values()) else None) for ch, g in zip(chs, feet_t)]
    known = [i for i, x in enumerate(dys) if x is not None]
    if len(known) < L:                      # flight: an arc between the last planted tick and the next one
        for i in range(L):
            if dys[i] is None:
                a = max(k2 for k2 in [(i - j) % L for j in range(1, L)] if dys[k2] is not None)
                b = min((k2 for k2 in [(i + j) % L for j in range(1, L)] if dys[k2] is not None), key=lambda k2: (k2 - i) % L)
                n = (b - a) % L
                u = ((i - a) % L) / n
                dys[i] = dys[a] + (dys[b] - dys[a]) * smooth(u) - flight * math.sin(math.pi * u)
    dys = [0.25 * dys[i - 1] + 0.5 * dys[i] + 0.25 * dys[(i + 1) % L] for i in range(L)]
    frames, rep = [], dict(ext=[99, -99], dy=[min(dys), max(dys)])
    for t in range(L + 1):
        i = t % L
        ph = (t % T) / T
        ph_loop = i / L
        # the weight comes down on a landing (the chain folds) and rises again over the stance
        dip = cfg['drop'] * (0.5 + 0.5 * math.cos(4 * math.pi * (ph - 0.06))) ** 2 * (0.5 if flight else 1.0)
        ch = dict(chs[i], p=(chs[i]['p'][0], dys[i] + dip, chs[i]['p'][2]))
        arms = {s: arm_angles(ph_loop, sg[4], cfg, 0.0) for s, sg in ARMS.items()}
        fins = {s: cfg['fin'] * wave(ph_loop, 0.06 + (0.03 if s == 'L' else 0), cfg['cycles'] * 1, 0.3) for s in FINS}
        W, P, ext = rig.pose(ch, feet_t[i], arms, fins)
        for e in ext.values():
            rep['ext'] = [min(rep['ext'][0], e), max(rep['ext'][1], e)]
        frames.append(rig.encode(W, P, -round(v * t)))
    return frames, rep


def idle(rig, ticks=IDLE_TICKS):
    """Slow breathing over planted boots, the weight shifting from side to side, a scan to each side with the arms
    trailing the turn."""
    rig.hist = {}
    feet = {n: rig.place_foot(n, dict(S=tuple(rig.rest_sole[n]), phi=0.0, plant=True)) for n in LEGS}
    frames, rep = [], dict(ext=[99, -99])
    for t in range(ticks + 1):
        i = t % ticks
        ph = i / ticks
        breath = wave(ph, 0.0, 4, 0.2)
        shift = wave(ph, 0.0, 1, 0.2)
        k96 = i * 96 / ticks          # the scan's key ticks are written for a 96-tick loop
        look = hold(k96, [(0, 0), (16, 0), (32, 1), (50, 1), (64, -0.8), (80, -0.8), (94, 0), (96, 0)])
        look2 = hold(k96, [(0, 0), (22, 0), (38, 1), (50, 1), (70, -0.8), (84, -0.8), (96, 0)])      # the arms trail the scan
        ch = dict(p=(3.5 * shift, 0.0 - 1.5 * breath, 0.0), yaw=6.5 * look, pitch=0.7 * breath, roll=1.4 * shift)
        dy = solve_dy(rig, ch, feet)
        ch['p'] = (ch['p'][0], dy - 1.5 * breath, 0.0)
        arms = {}
        for s, (sh, up, wr, hand, sg) in ARMS.items():
            lag = 0.025 if sg > 0 else 0.045
            b = wave(ph, 0.05 + lag, 4, 0.2)
            sl = wave(ph, 0.1 + lag, 1, 0.2)
            arms[s] = [(2.0 * b * g + 1.6 * sl * g + 2.2 * (look2 - look) * 0.0, sg * (-7.0 * (look2 - look) * g + 1.5 * sl * g) + sg * back + (6.0 if (sg < 0 and j == 0) else 0.0), 1.0 * b * g)
                       for j, (g, back) in enumerate(zip((1.0, 0.85, 0.7, 0.8), (-30.0, -6.0, 0.0, 0.0)))]
        fins = {s: 5.0 * wave(ph, 0.04 + (0.03 if s == 'L' else 0), 4, 0.3) + 6.0 * (look2 - look) * (1 if s == 'R' else -1) for s in FINS}
        W, P, ext = rig.pose(ch, feet, arms, fins)
        for e in ext.values():
            rep['ext'] = [min(rep['ext'][0], e), max(rep['ext'][1], e)]
        frames.append(rig.encode(W, P, 0))
    return frames, rep


FOOT_SOUND = {2: 21, 3: 21, 4: 21}     # the sound note of a footfall, as the previous clips used
BLINKS = ((29, (60, 88)), (30, (51, 76)), (32, (60, 88)), (33, (56, 88)),
          (60, (60, 88)), (61, (51, 76)), (63, (60, 88)), (64, (56, 88)))


def build(data):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError("Datamon's clips require the reviewed source")
    skeleton = [tuple(b) for b in json.loads((ROOT / 'content/species/294-datamon.json').read_text())['model']['skeleton']]
    n = len(skeleton)
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = n
    old = mmd.MMD.parse(data, n)
    old.type = SPECIES
    rig = Rig(old, skeleton)
    new = copy.deepcopy(old)
    out, reach = {0: idle(rig)}, {}
    for slot, cfg in GAITS.items():
        out[slot] = gait(rig, cfg)
    changed = set()
    for slot, (frames, rep) in out.items():
        lo, hi = rep['ext']
        reach[slot] = [round(lo, 1), round(hi, 1)]
        if lo < EXT[0] - 1e-6 or hi > EXT[1] + 1e-6:
            raise ValueError(f'slot {slot}: the legs telescope {lo:.1f}..{hi:.1f}, outside {EXT}')
        frames = [[[round(x) for x in b] for b in pose] for pose in frames]
        index = old.anims.table[slot]
        base = [e for e in mmd.anim_events(old.anims.anims[index], n, slot, ('tex',))]
        eyes = [e for e in base if e[0] == 0]
        if slot == 0:
            events = eyes + [(k, 'tex', dict(src=src, size=(4, 16), dst=(2, 8))) for k, src in BLINKS]
        else:
            events = eyes
            T = (len(frames) - 1) // GAITS[slot]['cycles']
            events += [(k * T + int(round(f * T)), 'sound', dict(bank=1, note=FOOT_SOUND[slot])) for k in range(GAITS[slot]['cycles']) for f in (0.0, 0.5)]
        animation = mmd.encode_anim(frames, n, loop_sample=0, events=events, tol=TOL)
        new.anims.anims[index] = animation
        changed |= {s for s, i in enumerate(old.anims.table) if i == index}
    result = new.build()
    actual = mmd.MMD.parse(result, n)
    actual.type = SPECIES
    assert old.tmd.build() == actual.tmd.build()
    assert changed_programs(old, actual) == sorted(changed), (changed_programs(old, actual), sorted(changed))
    assert sorted(changed) == sorted(SLOTS), sorted(changed)
    storage = motionstorage.require(result, n)
    return result, dict(species=SPECIES, changed_slots=sorted(changed), storage=storage, telescoping=reach,
                        output_sha256=hashlib.sha256(result).hexdigest())


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out-dir', type=Path, required=True)
    a = p.parse_args()
    data, proof = build(a.source.read_bytes())
    a.out_dir.mkdir(parents=True, exist_ok=True)
    (a.out_dir / '294-Datamon.MMD').write_bytes(data)
    print(json.dumps(proof, indent=2, default=str))


if __name__ == '__main__':
    main()
