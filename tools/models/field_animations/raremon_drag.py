"""Raremon's walk, tired walk and run written as a dragging crawl for its 18-bone rig (field slots 2, 3 and 4).

Offline only (player builds replay the pinned delta): `tools/models/edit.py get 264` on the commit before this change,
then `python3 -m tools.models.field_animations.raremon_drag --source THAT.MMD --out AFTER.MMD --report R.json` and
`edit.py put 264 AFTER.MMD`. The idle (slot 0, shared with slot 33) and the rest pose (slot 1 and its aliases) are untouched.

What was wrong. The three clips came with the import as one pose sequence at three speeds: the upper arms turned a few
degrees while the finger pieces (bones 9-11 and 15-17) swung 30 degrees, so the creature waggled its fingers; the root ran at
40.6, 32.3 and 80.9 units a tick, far beyond what a thing with no legs crawls at, so the hands slid over the ground at 90 to
104 percent of the root speed; the tired walk was the walk's poses again.

What the clips are now. Raremon has no walking legs: a hooded head and jaw, a hump (bone 1), a heavy lower body (bone 2)
and a ragged tail (bone 3), and two big arms (shoulder 6/12, forearm 7/13, hand 8/14 with three finger claws). It hauls
itself along the floor by its arms:
- each hand is a rigid plate. While it is planted its position and orientation are fixed in the world (the clip's frame moves
  it back at exactly the root speed), so it does not slide; in the swing it lifts, fingers curling a little, travels forward
  on an arc and lands palm first. The fingers never wave on their own: they follow the hand, and only flex a few degrees in
  the swing;
- the arm is solved on its two bones (shoulder and elbow turns, `two_bone`): the elbow bends out and up, the target is checked
  to lie inside the arm's reach every tick (no clamping: a target out of reach stops the build);
- the root keeps one constant speed, but the body surges relative to it: it is pulled forward in a burst while an arm
  pulls and stays almost still between pulls (a von Mises shaped speed, two bursts a cycle, mean exactly the root speed),
  so a planted hand travels backward over the body by exactly what the body gained;
- the hump rises while it is pulled and drops after it (heave), swings side to side over the pulling hand (lateral shift,
  roll, a twist that brings the pulling shoulder back), the head and the jaw follow it late on damped springs solved over
  the loop (`spring`), the lower body and the tail trail behind by a lagging twist.
The tired walk is slower, lower and heavier, with a long pause at the end of each pull and the head hanging; the run is short
and frantic, with the body pitched forward, longer lunges and a moment with both hands in the air.
Every clip keeps its two texture moves at tick 0 (the eyes) and sounds a footfall at each landing of a hand.
"""
import argparse
import cmath
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
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402

SPECIES, NB = 264, 18
SOURCE = 'cf2f7bd862baae12ea735d677ccd4782aaae58c698220124bba120dfbb6db646'      # edit.py get 264 before this change
SLOTS = (2, 3, 4)
PARENTS = [-1, 0, 1, 1, 1, 4, 1, 6, 7, 8, 8, 8, 1, 12, 13, 14, 14, 14]
HUMP, LOWER, TAIL, HEAD, JAW = 1, 2, 3, 4, 5
ARMS = ((6, 7, 8, (9, 10, 11), 1), (12, 13, 14, (15, 16, 17), -1))      # shoulder, elbow, hand, fingers, side (+1 is +x)
BODY = (1, 2, 3, 4, 5)
TOLERANCE = 1
LIFT_PLANTED = 0.6              # a planted hand's lowest vertex floats this much over the floor (the stored angles are whole units)
REACH_MARGIN = (10.0, 0.985)    # the arm's target distance must lie in [|l1 - l2| + 10, 0.985 (l1 + l2)]

# One row per slot. n: loop ticks (two arm pulls); v: root speed; stance: ticks a hand is planted; reach: the hand's forward
# distance from the shoulder in the middle of its stance (the stance's travel is added around it); kappa/kappa2: how
# peaked the pull's burst of speed is; pull: where the burst peaks inside the stance (share of it); lift: height of the
# lifted hand; arc: how far outward it swings; heave/roll/twist/shift/lean/nod: body channels (units, degrees);
# belly: the lowest body vertex's height over the floor at the loop's lowest; curl/pitch: the hand's swing;
# head/jaw: spring gains. Passive lags are the spring natural frequencies in cycles a loop.
CLIPS = {
    2: dict(n=16, v=15.0, stance=9, reach=105, kappa=1.25, kappa2=.30, pull=.36, lift=34, arc=20, heave=11, roll=4.5, twist=7.0,
            shift=14, lean=5.0, nod=4.0, sink=22, out=8.0, wide=24, curl=8, pitch=3, hang=0.0, jaw=9, tail=9),
    3: dict(n=24, v=10.0, stance=14, reach=100, kappa=1.7, kappa2=.35, pull=.30, lift=22, arc=14, heave=7, roll=3.5, twist=5.0,
            shift=10, lean=11.0, nod=3.0, sink=28, out=8.0, wide=48, curl=6, pitch=5, hang=14.0, jaw=6, tail=7),
    4: dict(n=12, v=35.0, stance=4, reach=100, kappa=.9, kappa2=.25, pull=.45, lift=42, arc=26, heave=14, roll=5.5, twist=9.0,
            shift=15, lean=15.0, nod=5.0, sink=12, out=8.0, wide=12, curl=10, pitch=9, hang=0.0, jaw=11, tail=10),
}
FOOTFALL = dict(bank=1, note=12)


def rx(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def deg(d):
    return math.radians(d)


def unit(v):
    return v / np.linalg.norm(v)


def smooth(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def spring(samples, fn, zeta):
    """A damped spring's steady-state response to an endless loop of `samples`: the loop's harmonics one by one, each
    scaled and delayed by the spring (natural frequency `fn` in cycles a loop), so the result closes on itself."""
    n = len(samples)
    spectrum = [sum(samples[t] * cmath.exp(-2j * math.pi * k * t / n) for t in range(n)) for k in range(n)]
    for k in range(n):
        h = min(k, n - k) * (1 if k <= n // 2 else -1)
        r = h / fn
        spectrum[k] /= (1 - r * r + 2j * zeta * r)
    return [sum(spectrum[k] * cmath.exp(2j * math.pi * k * t / n) for k in range(n)).real / n for t in range(n)]


def two_bone(shoulder, target, l1, l2, pole):
    """Elbow position of a two-bone arm whose wrist is at `target`; the bend leans toward `pole`. No clamping: a target out
    of reach raises."""
    d = target - shoulder
    dist = float(np.linalg.norm(d))
    lo, hi = abs(l1 - l2) + REACH_MARGIN[0], REACH_MARGIN[1] * (l1 + l2)
    if not lo <= dist <= hi:
        raise ValueError('arm target out of reach: %.1f not in [%.1f, %.1f]' % (dist, lo, hi))
    axis = d / dist
    a = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist)
    h = math.sqrt(max(l1 * l1 - a * a, 0.0))
    p = pole - axis * float(pole @ axis)
    return shoulder + axis * a + unit(p) * h, dist


def align(a1, n1, a2, n2):
    """The rotation taking the frame (axis a1, plane normal n1) to (a2, n2)."""
    def frame(a, n):
        x = unit(a)
        z = unit(np.cross(x, n))
        return np.column_stack([x, np.cross(z, x), z])
    return frame(a2, n2) @ frame(a1, n1).T


class Rig:
    """The model's rest pose (slot 0, first tick) and its forward kinematics, in the importer's matrix convention
    (a local matrix is T.R.S, scales in 4.12)."""

    def __init__(self, model, skeleton, rest):
        self.model = model
        self.par = [b[1] for b in skeleton]
        if self.par != PARENTS:
            raise ValueError('not the 18-bone Raremon rig')
        self.rest = [list(map(int, r)) for r in rest]
        self.scale = [np.array(r[:3], float) / 4096 for r in rest]
        self.r0 = [np.array(mmd.rot_matrix(*r[3:6])) for r in rest]
        self.t0 = [np.array(r[6:9], float) for r in rest]
        self.verts = {b: np.array([v[:3] for v in model.tmd.obj_verts(o)], float) for b, (o, _) in enumerate(skeleton) if o >= 0}
        self.w0, self.p0 = self.fk(self.r0, self.t0)

    def fk(self, rot, trans):
        """World linear part (rotation times scales, accumulated) and origin of every bone, bone 0 at the origin."""
        w, p = [np.eye(3)] + [None] * (NB - 1), [np.zeros(3)] + [None] * (NB - 1)
        for b in range(1, NB):
            q = self.par[b]
            w[b] = w[q] @ (rot[b] @ np.diag(self.scale[b]))
            p[b] = p[q] + w[q] @ trans[b]
        return w, p

    def world_points(self, rot, trans, bones):
        w, p = self.fk(rot, trans)
        return np.vstack([self.verts[b] @ w[b].T + p[b] for b in bones])

    def hand_extent(self, hand_world, flex, arm):
        """Vertices of the hand plate and its three fingers in the frame of the wrist, the hand turned to `hand_world` and
        the fingers flexed by `flex` radians about x. Returns the points."""
        shoulder, elbow, hand, fingers, side = arm
        w8 = hand_world @ np.diag(self.scale[hand])
        pts = [self.verts[hand] @ w8.T]
        for f in fingers:
            rot = self.r0[f] @ rx(flex)
            wf = w8 @ (rot @ np.diag(self.scale[f]))
            pts.append(self.verts[f] @ wf.T + w8 @ self.t0[f])
        return np.vstack(pts)


def euler(m, history, bone):
    angle = mmd.matrix_euler(m, history.get(bone))
    history[bone] = angle
    return [int(round(v)) for v in angle]




def unitise(x, centred=False):
    """A signal scaled to peak 1 (about its mean when `centred`)."""
    mean = sum(x) / len(x) if centred else 0.0
    peak = max(abs(v - mean) for v in x) or 1.0
    return [(v - mean) / peak for v in x]


def von_mises(n, period, peak, kappa, kappa2):
    """A smooth periodic speed profile (one burst a period, a second harmonic bending its shape), mean 1."""
    g = []
    for t in range(n):
        u = (t - peak) / period
        g.append(math.exp(kappa * math.cos(2 * math.pi * u) + kappa2 * math.cos(4 * math.pi * u + .7)))
    mean = sum(g) / n
    return [x / mean for x in g]


def surge_profile(spec):
    """Body speed per tick (mean exactly the root speed), the body's offset to the root, the pull intensity 0..1."""
    n, v = spec['n'], spec['v']
    g = von_mises(n, n / 2, spec['pull'] * spec['stance'], spec['kappa'], spec['kappa2'])
    s, acc = [], 0.0
    for t in range(n):
        s.append(acc)
        acc += v * g[t] - v
    mean = sum(s) / n
    lo, hi = min(g), max(g)
    return [v * x for x in g], [x - mean for x in s], [(x - lo) / (hi - lo) for x in g]


def body_channels(spec):
    n = spec['n']
    speed, surge, pull = surge_profile(spec)
    peak = spec['pull'] * spec['stance']
    rise = spring(pull, 3.6, .55)                       # the hump rises after the pull
    ch = []
    for t in range(n):
        ph = 2 * math.pi * (t - peak) / n
        ph2 = 2 * ph
        ch.append(dict(
            dy=-spec['heave'] * (rise[t] - .35) + .22 * spec['heave'] * math.cos(ph2 + .9),
            dx=spec['shift'] * (math.cos(ph - .55) + .22 * math.cos(ph2 + .4)),
            roll=deg(spec['roll'] * (math.cos(ph - .3) + .25 * math.sin(ph2 + .5))),
            yaw=deg(-spec['twist'] * (math.cos(ph - .15) + .2 * math.cos(ph2 + 1.1))),
            pitch=deg(spec['lean'] - 2.2 * spec['nod'] * (rise[t] - .45)),
            ds=surge[t], pull=pull[t], speed=speed[t]))
    return ch


def swing_point(spec, i, z_land):
    """A hand's z, lift, pitch, finger curl and outward arc at tick `i` of its own cycle (0 as it lands)."""
    n, v, stance = spec['n'], spec['v'], spec['stance']
    if i < stance:                                       # planted: the ground goes back at the root speed
        return z_land + v * i, 0.0, 0.0, 0.0, 0.0
    q = (i - stance + 1) / (n - stance + 1)              # the swing's ticks lie between its ends
    z0, z1, m = z_land + v * (stance - 1), z_land, v * (n - stance + 1)
    z = (2 * q ** 3 - 3 * q * q + 1) * z0 + (q ** 3 - 2 * q * q + q) * m + (3 * q * q - 2 * q ** 3) * z1 + (q ** 3 - q * q) * m
    lift = spec['lift'] * math.sin(math.pi * q) ** .7 * (1 - .18 * math.cos(2 * math.pi * q + .4))
    pitch = deg(spec['pitch']) * math.sin(2 * math.pi * q ** 1.1) * math.sin(math.pi * q) ** .5
    curl = deg(spec['curl']) * math.sin(math.pi * q) ** 1.2
    arc = spec['arc'] * math.sin(math.pi * q) ** .9
    return z, lift, pitch, curl, arc


class Clip:
    """One slot's tick-by-tick pose: local rotation matrices and translations per bone, and the arms' checks."""

    def __init__(self, rig, slot):
        self.rig, self.slot, self.spec = rig, slot, CLIPS[slot]
        spec, n = self.spec, self.spec['n']
        self.ch = body_channels(spec)
        lean = deg(spec['lean'])
        pull = [c['pull'] for c in self.ch]
        self.head_pitch = spring([c['pitch'] - lean for c in self.ch], 2.4, .38)
        self.head_roll = spring([c['roll'] for c in self.ch], 2.0, .34)
        self.head_yaw = spring([c['yaw'] for c in self.ch], 2.2, .34)
        self.jaw = unitise(spring([pull[(t + 1) % n] - 2 * pull[t] + pull[(t - 1) % n] for t in range(n)], 4.4, .30))
        self.jaw_slack = unitise(spring(pull, 3.0, .45), True)
        self.lower_yaw = spring([-c['yaw'] * .5 + c['roll'] * .6 for c in self.ch], 2.0, .6)
        self.tail_yaw = spring([-c['yaw'] * 1.0 + c['roll'] * 1.3 for c in self.ch], 1.8, .5)
        self.lower_dz = spring([.8 * c['ds'] for c in self.ch], 2.0, .7)
        self.tail_dz = spring([.7 * c['ds'] for c in self.ch], 1.6, .7)
        self.lower_dx = spring([.5 * c['dx'] for c in self.ch], 2.0, .7)
        self.tail_dx = spring([-.8 * c['dx'] for c in self.ch], 1.8, .5)
        self.reach_log = []
        self.build()

    def body_pose(self, t):
        rig, c, spec = self.rig, self.ch[t], self.spec
        rot, trans = list(rig.r0), [x.copy() for x in rig.t0]
        d1 = ry(c['yaw']) @ rx(c['pitch']) @ rz(c['roll'])
        rot[HUMP] = d1 @ rig.r0[HUMP]
        trans[HUMP] = rig.t0[HUMP] + np.array([c['dx'], spec['sink'] + c['dy'], -c['ds']])
        w, p = rig.fk(rot, trans)
        # the heavy lower body and the tail lie on the floor and are dragged: their place in the world is their own, a
        # late follower of the hump's surge, shift and twist, never lifted or tilted
        for bone, yaw, dz, dx in ((LOWER, self.lower_yaw[t], self.lower_dz[t], self.lower_dx[t]),
                                  (TAIL, self.tail_yaw[t], self.tail_dz[t], self.tail_dx[t])):
            want = ry(yaw) @ rig.r0[1] @ rig.r0[bone]
            rot[bone] = rot[HUMP].T @ want
            target = rig.p0[bone] + np.array([dx, 0.0, -dz])
            trans[bone] = np.linalg.solve(w[HUMP], target - p[HUMP])
        rot[HEAD] = ry(.9 * self.head_yaw[t]) @ rx(deg(spec['hang']) + .9 * self.head_pitch[t]) @ rz(.8 * self.head_roll[t]) @ rig.r0[HEAD]
        rot[JAW] = rx(deg(spec['jaw']) * (.6 * self.jaw[t] + .4 * self.jaw_slack[t]) + .35 * deg(spec['hang'])) @ rig.r0[JAW]
        return rot, trans

    def build(self):
        rig, spec = self.rig, self.spec
        n, v, stance = spec['n'], spec['v'], spec['stance']
        self.poses = [self.body_pose(t) for t in range(n)]
        w0, p0 = rig.w0, rig.p0
        self.l1 = float(np.linalg.norm(p0[7] - p0[6]))
        self.l2 = float(np.linalg.norm(p0[8] - p0[7]))
        self.x_stance = abs(float(p0[8][0])) + spec['wide']
        rest_rot = rig.r0[1] @ rig.r0[6] @ rig.r0[7] @ rig.r0[8]
        self.travel = sum(self.ch[i % n]['speed'] for i in range(stance - 1))
        z_land = float(p0[6][2]) - spec['reach'] - self.travel / 2 - self.ch[0]['ds']
        self.z_land = z_land
        self.targets = {}
        for arm in ARMS:
            sh, el, ha, fi, side = arm
            offset = 0 if side > 0 else n // 2
            axis = unit(p0[ha] - p0[sh])
            e = p0[el] - p0[sh]
            pole_world = unit(e - axis * float(e @ axis))
            pole_b = np.linalg.solve(w0[1], pole_world)
            u0 = rig.r0[sh] @ np.diag(rig.scale[sh]) @ rig.t0[el]
            f0 = rig.r0[sh] @ np.diag(rig.scale[sh]) @ rig.r0[el] @ np.diag(rig.scale[el]) @ rig.t0[ha]
            n0 = np.cross(u0, f0)
            yaw_h = -side * deg(8)
            for t in range(n):
                i = (t - offset) % n
                z, lift, pitch, curl, arc = swing_point(spec, i, z_land)
                hand_world = ry(yaw_h) @ rx(pitch) @ rest_rot
                flex = curl
                ext = rig.hand_extent(hand_world, flex, arm)
                y = -(LIFT_PLANTED if i < stance else LIFT_PLANTED + lift) - float(ext[:, 1].max())
                target = np.array([side * (self.x_stance + arc), y, z])
                rot, trans = self.poses[t]
                w, p = rig.fk(rot, trans)
                shoulder = p[sh]
                elbow, dist = two_bone(shoulder, target, self.l1, self.l2, w[1] @ pole_b + side * spec['out'] * np.array([1.0, 0, 0]))
                self.reach_log.append((arm[0], t, dist))
                winv = np.linalg.inv(w[1])
                ub, fb = winv @ (elbow - shoulder), winv @ (target - elbow)
                a_u = align(u0, n0, ub, np.cross(ub, fb))
                a_f = align(f0, n0, fb, np.cross(ub, fb))
                r6 = a_u @ rig.r0[sh]
                o7 = a_f @ rig.r0[sh] @ rig.r0[el]
                rot[sh] = r6
                rot[el] = r6.T @ o7
                r1 = rot[HUMP]
                rot[ha] = o7.T @ (r1.T @ hand_world)
                for k, f in enumerate(fi):
                    rot[f] = rig.r0[f] @ rx(flex * (1.0, 1.15, .9)[k])
                self.targets[(sh, t)] = (target, hand_world, lift, i < stance)

    def rows(self):
        rig, n, v = self.rig, self.spec['n'], self.spec['v']
        hist, frames = {}, []
        for t in range(n):
            rot, trans = self.poses[t]
            row = [[4096, 4096, 4096, 0, 0, 0, 0, 0, int(round(-v * t))]]
            for b in range(1, NB):
                row.append(list(rig.rest[b][:3]) + euler(rot[b], hist, b) + [int(round(x)) for x in trans[b]])
            frames.append(row)
        end = copy.deepcopy(frames[0])
        end[0][8] = int(round(-v * n))
        frames.append(end)
        mmd.close_loop(frames, 0)
        return frames


def hand_points(rig, frame, arm):
    """World points (the clip's own frame, root motion left out) of a hand plate and its fingers, from stored whole-number rows."""
    pose = [list(r) for r in frame]
    pose[0] = [4096] * 3 + [0] * 6
    mats = mmd.bone_matrices(rig.model, pose)
    pts = []
    for b in (arm[2],) + tuple(arm[3]):
        m = np.array(mats[b], float)
        pts.append(rig.verts[b] @ m[:3, :3].T + m[:3, 3])
    return np.vstack(pts), mats


def analyse(rig, frames, slot):
    """Measurements of a stored clip (frames incl. the closing one): per hand its stance, slip (percent of the root speed,
    on the lowest vertices of its first stance tick), lowest point, the wrist's travel in the hump's frame, arm and finger turns."""
    spec = CLIPS[slot]
    n, v = spec['n'], spec['v']
    out = dict(slot=slot, ticks=n, speed=v, hands=[])
    for arm in ARMS:
        pts = [hand_points(rig, f, arm) for f in frames[:n]]
        height = [-float(p[0][:, 1].max()) for p in pts]               # over the floor
        planted = [h <= 2.0 for h in height]
        runs = [t for t in range(n) if planted[t]]
        slips, wrist_z = [], []
        first = next(t for t in range(n) if planted[t] and not planted[t - 1])
        order = [(first + k) % n for k in range(n)]
        low = np.argsort(-pts[first][0][:, 1])[:6]
        prev = None
        for t in order:
            if not planted[t]:
                prev = None
                continue
            here = pts[t][0][low]
            if prev is not None:
                d = here - prev
                slips.append(float(np.mean(np.hypot(d[:, 0], d[:, 2] - v))) / v * 100)
            prev = here
            m = np.array(pts[t][1][1], float)
            m1 = np.array(pts[t][1][1], float)
            body = np.linalg.inv(np.array(pts[t][1][HUMP], float))
            wrist = np.array(pts[t][1][arm[2]], float)[:3, 3]
            wrist_z.append(float((body @ np.append(wrist, 1))[2]))
        # the upper arm's and the fingers' turns from their stored rotation (degrees about their rest)
        rest_u, rest_f = rig.r0[arm[0]], [rig.r0[f] for f in arm[3]]

        def turn(a, b):
            c = max(-1.0, min(1.0, (np.trace(a.T @ b) - 1) / 2))
            return math.degrees(math.acos(c))
        up = [turn(rest_u, np.array(mmd.rot_matrix(*f[arm[0]][3:6]))) for f in frames[:n]]
        fin = [max(turn(r, np.array(mmd.rot_matrix(*f[b][3:6]))) for r, b in zip(rest_f, arm[3])) for f in frames[:n]]
        out['hands'].append(dict(
            arm=arm[0], stance=len(runs), slip_mean=float(np.mean(slips)), slip_max=float(np.max(slips)),
            lowest=-min(height[t] for t in runs), highest=max(height[t] for t in runs), planted_height_range=(min(height[t] for t in runs), max(height[t] for t in runs)),
            wrist_travel=max(wrist_z) - min(wrist_z), arm_swing=max(up) - min(up), finger_swing=max(fin) - min(fin),
            lift=max(height), sink=max(0.0, max(-h for h in height))))
    hump_z = [f[HUMP][8] for f in frames[:n]]
    out['surge'] = max(hump_z) - min(hump_z)
    steps = {}
    for b in range(1, NB):
        d = []
        for t in range(n):
            a = np.array(mmd.rot_matrix(*frames[t][b][3:6]))
            c = np.array(mmd.rot_matrix(*frames[(t + 1) % n if t + 1 < n else 0][b][3:6]))
            d.append(math.degrees(math.acos(max(-1.0, min(1.0, (np.trace(a.T @ c) - 1) / 2)))))
        steps[b] = d
    out['steps'] = steps
    return out


def parse(data, skeleton):
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = len(skeleton)
    model = mmd.MMD.parse(data, len(skeleton))
    model.type = SPECIES
    return model


def landings(slot):
    n = CLIPS[slot]['n']
    return [0, n // 2]


def events_of(model, slot):
    """The clip's texture moves as stored (the eyes) and a footfall at each hand's landing."""
    _, _, events = animsheet.slot_frames(model, NB, slot)
    events = [e for e in events if e[1] != 'sound']
    events += [(t, 'sound', dict(op='sound', bank=FOOTFALL['bank'], note=FOOTFALL['note'], frame=t + 1)) for t in landings(slot)]
    return sorted(events, key=lambda e: e[0])


def build(data, skeleton, clips=None):
    if hashlib.sha256(data).hexdigest() != SOURCE or [b[1] for b in skeleton] != PARENTS:
        raise ValueError("Raremon's drag crawl requires the 18-bone import as `edit.py get 264` gave it before this change")
    model = parse(data, skeleton)
    rest = animsheet.slot_frames(model, NB, 0)[0][0]
    rig = Rig(model, skeleton, rest)
    result = copy.deepcopy(model)
    clips = clips or {slot: Clip(rig, slot) for slot in SLOTS}
    for slot in SLOTS:
        frames = clips[slot].rows()
        program = mmd.encode_anim(frames, NB, 0, events_of(model, slot), tol=TOLERANCE, repeats=False)
        index = model.anims.table[slot]
        if sum(1 for v in model.anims.table if v == index) > 1:
            raise ValueError('slot %d shares its program' % slot)
        result.anims.anims[index] = program
    for animation in result.anims.anims:
        animation.tail = b''
    output = result.build()
    effective = parse(output, skeleton)
    assert effective.tmd.build() == model.tmd.build()
    return output, dict(species=SPECIES, source_sha256=SOURCE, output_sha256=hashlib.sha256(output).hexdigest(),
                        changed_slots=changed_programs(model, effective), storage=motionstorage.require(output, NB)), rig, clips


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, default=ROOT / 'build/imported-model-edit/edit/264-Raremon.MMD')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    sk = json.loads(next((ROOT / 'content/species').glob('264-*.json')).read_text())['model']['skeleton']
    data, proof, _, _ = build(a.source.read_bytes(), sk)
    a.out.write_bytes(data)
    if a.report:
        a.report.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({k: proof[k] for k in ('changed_slots',)}), proof['storage']['resident_bytes'], len(data))


if __name__ == '__main__':
    main()
