"""Dragomon's idle, walk, condition walk and run, written for its own 20-bone rig (field slots 0, 2, 3, 4).

Offline only (player builds replay the pinned delta): `tools/models/edit.py get 291` on the commit before this change,
then `python3 -m tools.models.field_animations.dragomon_gait --source THAT.MMD --out AFTER.MMD --report R.json` and
`edit.py put 291 AFTER.MMD`.

What was wrong. The clips came with the import: the walk's hind legs were driven through strides longer than their reach
(one foot slid 125 % of the ground speed), the tired walk and the run folded the body almost onto its hands, and the
wings lay flat. The rig is a hunched, long-armed dragon: bone 1 is the skull (the parent of everything), 2 the chest, 3
the pelvis, 4-5 / 6-7 two-bone legs whose lower piece is a rigid shin with a clawed flat foot, 8 / 9 the wings (one
plate each), 10-13 the left arm (ending in a long blade) and 14-17 the right arm, 18 the jaw and 19 a crest. There is no tail.

What the clips are now. Every pose is built in the model's own rest pose (the first tick of the old idle) with a virtual
tree: pelvis, then chest, then skull, wings and shoulders on the chest, jaw and crest on the skull. The legs are
solved by position (the hip is the pelvis' own point; the thigh and the rigid shin are turned by the shortest rotation to
reach a foot target, the knee toward the side it has at rest), the arms by angles that follow the body late (damped
springs solved over the loop, so every loop closes).
- Both feet plant by the ground's speed while they support (the target moves back at the root speed), swing lifted and
  land again at the ground's speed; the sole's lowest vertex is put on the floor, and the pelvis height follows the legs
  (an inverted pendulum), so the shin stays near vertical and the feet stay flat.
- The pelvis sways over the planted foot and turns with the stride, the chest twists against it, the skull looks around
  a little; the arms swing against the legs, mostly forward (they hang beside the legs), the wings sway late.
- Walk: upright, alternating, arms swinging. Tired walk: lower, slower, heavier with short steps, skull and wings drooping.
  Run: leaning, a flight phase, arms pumping, wings swept back.
- Idle: slow breath, a lazy look-around, weight shifting from foot to foot over planted feet, arms hanging with weight.
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
import legik  # noqa: E402
import mmd  # noqa: E402
import animsheet  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402

SPECIES, NB = 291, 20
SOURCE = '85d68b5c0eb4e02068214e81f797ecfda970269e0f16b4eace9ce41471412806'     # `edit.py get 291` before this change
SLOTS = (0, 2, 3, 4)
PARENTS = [-1, 0, 1, 1, 3, 4, 3, 6, 1, 1, 1, 10, 11, 12, 1, 14, 15, 16, 1, 1]
# the virtual tree the poses are built on: the pelvis leads, the chest hangs from it, the skull is free of the chest's twist
VIRTUAL = {2: 3, 1: 2, 8: 2, 9: 2, 10: 2, 14: 2, 11: 10, 12: 11, 13: 12, 15: 14, 16: 15, 17: 16, 18: 1, 19: 1, 4: 3, 6: 3}
BUILD_ORDER = (3, 2, 1, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19)
LEGS = ((4, 5, 1), (6, 7, -1))                     # hip, shin, side (+1 is the +x side)
ARMK, ABD = 0.9, 12.0
ZETA_S = 0.7                                                    # the lag springs: at most one slow settle at the step rate
ZETA = 1.15                                                     # the secondary motion's springs: over-damped, no overshoot
ARM_L, ARM_R = (10, 11, 12, 13), (14, 15, 16, 17)
TOLERANCE = 1
FLOOR = 0.0

# One row per slot. cycles: gait cycles in the loop (a cycle is two steps); duty: share of a cycle a foot supports;
# sweep is speed * stance; zc: how far the foot centres sit in front of the hips (positive = ahead) during support;
# lift: foot height in swing; hip: the pelvis' height change from the rest pose (negative = higher); bob: its rise over a
# step; lean: forward pitch of the pelvis, spine: of the chest over the pelvis, head: of the skull over the chest
# (degrees, forward positive); roll / twist / sway: pelvis angles (degrees) and sideways travel (units); arm: swing of
# the shoulders (degrees), arm0 their mean (forward positive), elbow, wrist: the arms' bend; wing: the wings' flap.
GAIT = {
    0: dict(n=96, cycles=1, speed=0.0, still=True, drop=13.0),
    2: dict(n=26, cycles=2, speed=15.0, duty=.55, fx=88, zc=0, lift=34, drop=0, air=0, lean=3.0, spine=-3.0, head=3.0,
            roll=5.5, twist=8.0, sway=9.0, sink=7.0, drift=7.0, arm=22, arm0=7, elbow=14, wrist=8, hand=6, wing=7, wing0=0),
    3: dict(n=30, cycles=2, speed=11.0, duty=.62, fx=96, zc=0, lift=24, drop=4, air=0, lean=6.0, spine=9.0, head=16.0,
            roll=6.5, twist=6.0, sway=11.0, sink=11.0, drift=6.0, abd=17.0, arm=9, arm0=3, elbow=22, wrist=16, hand=10, wing=3, wing0=0),
    4: dict(n=20, cycles=2, speed=36.0, duty=.32, fx=88, zc=0, lift=40, drop=0, air=0, bounce=16.0, lean=12.0, spine=4.0, head=-6.0,
            roll=4.0, twist=9.0, sway=5.0, sink=6.0, drift=5.0, abd=19.0, arm=26, arm0=12, elbow=22, wrist=8, hand=6, wing=9, wing0=0),
}


# ---- small linear algebra (rotations are 3x3 numpy arrays; axes are the game's: x right, y down, forward is -z)

def rx(d):
    return np.array(mmd.rot_matrix(d * 4096 / 360, 0, 0))


def ry(d):
    return np.array(mmd.rot_matrix(0, d * 4096 / 360, 0))


def rz(d):
    return np.array(mmd.rot_matrix(0, 0, d * 4096 / 360))


def arc(u, v):
    """The shortest rotation turning the direction u onto the direction v."""
    u = np.asarray(u, float) / np.linalg.norm(u)
    v = np.asarray(v, float) / np.linalg.norm(v)
    c = float(np.dot(u, v))
    if c < -1 + 1e-9:
        axis = np.cross(u, [1, 0, 0])
        if np.linalg.norm(axis) < 1e-6:
            axis = np.cross(u, [0, 1, 0])
        axis /= np.linalg.norm(axis)
        return 2 * np.outer(axis, axis) - np.eye(3)
    k = np.cross(u, v)
    kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + kx + kx @ kx / (1 + c)


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


def harmonics(n, terms):
    """A closed loop from (cycles, amplitude, phase in turns) terms: a loose curve, not a sine."""
    return [sum(a * math.cos(2 * math.pi * (k * t / n - ph)) for k, a, ph in terms) for t in range(n)]


def weight_drop(x):
    """0 -> 1 -> 0 across a step: the body sinks onto the landing foot in a quarter of the step, then recovers slowly."""
    return smooth(x / .28) if x < .28 else 1 - smooth((x - .28) / .72)


def smooth(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


# ---- the rig at rest

class Rig:
    def __init__(self, model, skeleton):
        self.model, self.skeleton = model, skeleton
        self.ref = animsheet.slot_frames(model, NB, 0)[0][0]
        self.R, self.P, self.T = {0: np.eye(3)}, {0: np.zeros(3)}, {}
        for b in range(1, NB):
            f = self.ref[b]
            self.T[b] = np.array(f[6:9], float)
            Rl = np.array(mmd.rot_matrix(*f[3:6]))
            p = PARENTS[b]
            self.R[b] = self.R[p] @ Rl
            self.P[b] = self.P[p] + self.R[p] @ self.T[b]
        self.verts = {b: np.array([v[:3] for v in model.tmd.obj_verts(o)], float) for b, (o, _) in enumerate(skeleton) if o >= 0}
        # a bone's place in its virtual parent's frame at rest
        self.rel_R, self.rel_P = {}, {}
        for b, v in VIRTUAL.items():
            self.rel_R[b] = self.R[v].T @ self.R[b]
            self.rel_P[b] = self.R[v].T @ (self.P[b] - self.P[v])
        # legs: hip links and rigid shin pieces
        self.leg = {}
        for hip, shin, side in LEGS:
            sole = self.verts[shin]
            low = sole[sole[:, 1] > sole[:, 1].max() - 8]                 # the sole's lowest vertices, in the shin's frame
            s_loc = low.mean(0)
            thigh = np.linalg.norm(self.rel_P[shin]) if shin in self.rel_P else np.linalg.norm(self.T[shin])
            self.leg[hip] = dict(shin=shin, side=side, s_loc=s_loc, l1=float(np.linalg.norm(self.T[shin])),
                                 l2=float(np.linalg.norm(s_loc)), foot_ref=self.P[shin] + self.R[shin] @ s_loc)
            self.leg[hip]['pole'] = self.pole(hip)

    def pole(self, hip):
        lg = self.leg[hip] if hip in self.leg else None
        shin = {4: 5, 6: 7}[hip]
        sole = self.verts[shin]
        low = sole[sole[:, 1] > sole[:, 1].max() - 8]
        foot = self.P[shin] + self.R[shin] @ low.mean(0)
        axis = foot - self.P[hip]
        knee = self.P[shin] - self.P[hip]
        u = axis / np.linalg.norm(axis)
        pole = knee - u * float(np.dot(knee, u))
        return pole / np.linalg.norm(pole)

    def lowest(self, bone, R, P):
        w = self.verts[bone] @ R.T + P
        return float(w[:, 1].max())


# ---- foot paths

def foot_cycle(g, i):
    """One foot at a time `i` (ticks into its cycle, 0 as it lands): (z offset about mid support, rise above the ground).
    z forward is negative; in the root's frame the ground runs back (+z) at `speed`. Support is the first `duty` of the
    cycle; the swing leaves and lands at the ground's speed, so the foot never scuffs."""
    period = g['n'] / g['cycles']
    speed = g['speed']
    stance = g['duty'] * period
    swing = period - stance
    i = i % period
    reach = speed * stance / 2
    if i < stance:
        return -reach + 2 * reach * i / stance, 0.0
    q = (i - stance) / swing
    m = speed * swing
    z = ((2 * q ** 3 - 3 * q * q + 1) * reach + (q ** 3 - 2 * q * q + q) * m
         + (3 * q * q - 2 * q ** 3) * -reach + (q ** 3 - q * q) * m)
    lift = g['lift'] * math.sin(math.pi * q) ** .62
    return z, lift


# ---- one pose

class Frame:
    """World rotations and origins of every bone for one tick, built on the virtual tree; `frame()` writes them as the
    model's local pose (each bone relative to its real parent)."""

    def __init__(self, rig):
        self.rig = rig
        self.R = {0: np.eye(3)}
        self.P = {0: np.zeros(3)}

    def put(self, b, R, P):
        self.R[b], self.P[b] = R, np.asarray(P, float)

    def hang(self, b, D=None, L=None, at=None):
        """Bone b on its virtual parent: its rest place there, turned by D (in the parent's frame) and L (in its own)."""
        v = VIRTUAL[b]
        r = self.rig
        Rv = self.R[v]
        R = Rv @ (D if D is not None else np.eye(3)) @ r.rel_R[b] @ (L if L is not None else np.eye(3))
        self.put(b, R, self.P[v] + Rv @ r.rel_P[b] if at is None else at)

    def local(self, hist):
        f = [[4096, 4096, 4096, 0, 0, 0, 0, 0, 0]]
        for b in range(1, NB):
            p = PARENTS[b]
            Rl = self.R[p].T @ self.R[b]
            t = self.R[p].T @ (self.P[b] - self.P[p])
            ang = mmd.matrix_euler(Rl, hist.get(b))
            hist[b] = ang
            f.append([4096, 4096, 4096] + [round(a) for a in ang] + [round(float(x)) for x in t])
        return f


def leg_pose(rig, hip, hip_P, R3, S, tilt=0.0):
    """Thigh and shin for a foot target S: (knee, R4, R5) by the two-bone solve, the knee toward the rest side. Raises
    when the target is out of reach: no clamping hides a slide."""
    lg = rig.leg[hip]
    shin = lg['shin']
    d = float(np.linalg.norm(S - hip_P))
    if not (abs(lg['l1'] - lg['l2']) + 3 < d < .985 * (lg['l1'] + lg['l2'])):
        raise ValueError(f'foot out of reach: hip {hip} distance {d:.1f} of {lg["l1"] + lg["l2"]:.1f}')
    # the knee goes where the shin would stand as at rest (tilted by `tilt` degrees about the sideways axis) if the thigh
    # can reach it, else on the nearest point of the circle the two links allow
    desired = S - rx(tilt) @ (rig.R[shin] @ lg['s_loc']) - hip_P
    knee, _ = legik.solve(list(hip_P), list(S), lg['l1'], lg['l2'], list(desired))
    knee = np.array(knee)
    ref4 = rig.R[hip]
    v4 = ref4 @ rig.T[shin]
    R4 = arc(v4, knee - hip_P) @ ref4
    ref5 = rig.R[shin]
    R5 = arc(ref5 @ lg['s_loc'], S - knee) @ ref5
    return knee, R4, R5


def stance_weight(g, i):
    period = g['n'] / g['cycles']
    stance = g['duty'] * period
    i = i % period
    return min(1.0, max(0.0, stance - i + .5)) * min(1.0, max(0.0, i + .5))


def author(rig, slot):
    """The clip's frames (n + 1, the last equal to the first plus the loop's travel) and its measurements."""
    g = GAIT[slot]
    n, cyc, speed = g['n'], g['cycles'], g['speed']
    still = g.get('still', False)
    period = n / cyc
    # ---- body drivers, one value per tick
    th = [2 * math.pi * t / period for t in range(n)]          # one gait cycle = two steps
    if still:
        ch = idle_channels(n)
    else:
        ch = gait_channels(g, n)
    base = np.array(rig.P[3])
    hip_off = {hip: rig.rel_P[hip] for hip in (4, 6)}
    foot_x = {hip: (math.copysign(g['fx'], rig.leg[hip]['foot_ref'][0]) if 'fx' in g else rig.leg[hip]['foot_ref'][0]) for hip in (4, 6)}
    hip_z0 = base[2] + hip_off[4][2]
    sole_ref = {hip: rig.leg[hip] for hip in (4, 6)}
    # R3 and hip positions (without height) for every tick
    R3s, hips_xz = [], []
    for t in range(n):
        R3 = ry(ch['yaw'][t]) @ rx(ch['pitch'][t]) @ rz(ch['roll'][t])
        R3s.append(R3)
    # ---- feet
    foot = {}
    for hip, shin, side in LEGS:
        z, lift, wgt = [], [], []
        for t in range(n):
            if still:
                z.append(0.0); lift.append(0.0); wgt.append(1.0)
                continue
            i = (t + (0 if side > 0 else period / 2)) % period
            a, b = foot_cycle(g, i)
            z.append(a); lift.append(b); wgt.append(stance_weight(g, i))
        foot[hip] = dict(z=z, lift=lift, w=wgt)
    centre = {hip: (hip_z0 - g['zc'] if not still else rig.leg[hip]['foot_ref'][2]) for hip in (4, 6)}
    # ---- pelvis height: the inverted pendulum's, so the shin stays upright while a foot supports
    need = []
    for t in range(n):
        vals, ws = [], []
        for hip, shin, side in LEGS:
            lg = rig.leg[hip]
            w = foot[hip]['w'][t]
            if w <= 0.001 or still:
                continue
            S = np.array([foot_x[hip], 0.0, centre[hip] + foot[hip]['z'][t]])
            s_ref = lg['foot_ref'] - rig.P[shin]
            Pk = S - s_ref
            hp = base + R3s[t] @ hip_off[hip]
            hp[0] += ch['x'][t]
            hp[2] += ch['z'][t]
            dh = math.hypot(hp[0] - Pk[0], hp[2] - Pk[2])
            r = lg['l1'] ** 2 - dh ** 2
            if r <= 25:
                raise ValueError(f'slot {slot}: support leg {hip} cannot keep the shin upright at tick {t} (sweep too long)')
            hy = Pk[1] - math.sqrt(r)
            vals.append(w * (hy - (base[1] + (R3s[t] @ hip_off[hip])[1]))); ws.append(w)
        need.append(sum(vals) / sum(ws) if ws else None)
    dy = fill_gaps(need, g.get('air', 0.0), still)
    for _ in range(g.get('ease', 2)):                              # a foot taking over from the other must not jolt the pelvis
        dy = [(dy[t - 1] + 2 * dy[t] + dy[(t + 1) % n]) / 4 for t in range(n)]
    dy = [dy[t] + g.get('drop', 0.0) + ch['dy'][t] for t in range(n)]
    # ---- the arms follow the body late
    frames, hist, notes = [], {}, dict(tilt=[], dy=dy, reach=[], floor=[])
    for t in range(n + 1):
        k = t % n
        F = Frame(rig)
        R3 = R3s[k]
        p3 = base + np.array([ch['x'][k], dy[k], ch['z'][k]])
        F.put(3, R3, p3)
        # chest over the pelvis (turns about the pelvis' origin), skull on the chest, the rest on those
        Dsp = ry(ch['spine_yaw'][k]) @ rx(ch['spine'][k]) @ rz(ch['spine_roll'][k])
        F.put(2, R3 @ Dsp @ rig.rel_R[2], p3 + R3 @ Dsp @ rig.rel_P[2])
        Dh = ry(ch['head_yaw'][k]) @ rx(ch['head'][k]) @ rz(ch['head_roll'][k])
        F.hang(1, L=Dh)
        F.hang(18, L=rx(ch['jaw'][k]))
        F.hang(19, L=rx(ch['crest'][k]) @ rz(ch['crest_roll'][k]))
        for b, side in ((8, -1), (9, 1)):
            w = ch['wing'][b]
            F.hang(b, D=ry(side * w['sweep'][k]) @ rz(-side * w['flap'][k]) @ rx(w['fold'][k]))
        for chain, side in ((ARM_L, -1), (ARM_R, 1)):
            a = ch['arm'][side]
            sh, el, wr, hd = chain
            F.hang(sh, D=rx(-a['swing'][k]) @ rz(-side * a['abduct'][k]) @ ry(a['turn'][k]))
            F.hang(el, L=rx(-a['elbow'][k]))
            F.hang(wr, L=rx(-a['wrist'][k]))
            F.hang(hd, L=rx(-a['hand'][k]))
        worst_tilt = 0.0
        for hip, shin, side in LEGS:
            lg = rig.leg[hip]
            hp = p3 + R3 @ hip_off[hip]
            F.put(hip, None, hp)
            f = foot[hip]
            S = np.array([foot_x[hip] + side * ch['splay'][k], -f['lift'][k], centre[hip] + f['z'][k]]) if not still else np.array(lg['foot_ref'], float)
            fixed_y = S[1]
            for _ in range(8):                                     # the lowest sole vertex on the floor (or above it, in swing)
                try:
                    knee, R4, R5 = leg_pose(rig, hip, hp, R3, S)
                except ValueError as e:
                    raise ValueError(f'slot {slot} tick {t}: {e}; S {np.round(S)} hip {np.round(hp)}')
                low = rig.lowest(shin, R5, knee) - FLOOR
                if f['w'][k] > 0.5 or still:
                    S[1] -= low
                elif low > 0:
                    S[1] -= low
                else:
                    break
            F.put(hip, R4, hp)
            F.put(shin, R5, knee)
            dirv = R5 @ lg['s_loc']
            d0 = rig.R[shin] @ lg['s_loc']
            worst_tilt = max(worst_tilt, math.degrees(math.acos(max(-1., min(1., float(dirv @ d0 / np.linalg.norm(dirv) / np.linalg.norm(d0)))))))
            notes.setdefault('pitch' + str(hip), []).append(math.degrees(math.atan2(dirv[2], dirv[1]) - math.atan2(d0[2], d0[1])))
        notes['tilt'].append(worst_tilt)
        fr = F.local(hist)
        fr[0][8] = round(-speed * t)
        frames.append(fr)
    mmd.close_loop(frames, 0)
    return frames, notes


def fill_gaps(need, air, still):
    """The pelvis height where no foot supports: a smooth bridge between the heights either side, a little higher in the
    air (the run's flight)."""
    n = len(need)
    if still:
        return [0.0] * n
    idx = [t for t in range(n) if need[t] is not None]
    if len(idx) == n:
        return list(need)
    out = [0.0] * n
    for t in range(n):
        if need[t] is not None:
            out[t] = need[t]
            continue
        a = max(s for s in range(-n, t) if need[s % n] is not None)
        b = min(s for s in range(t + 1, 2 * n) if need[s % n] is not None)
        u = (t - a) / (b - a)
        va, vb = need[a % n], need[b % n]
        out[t] = va + (vb - va) * smooth(u) - air * math.sin(math.pi * u)
    return out


# ---- the body's drivers

def zeros(n):
    return [0.0] * n


def blank(n):
    ch = {k: zeros(n) for k in ('x', 'z', 'dy', 'yaw', 'pitch', 'roll', 'spine', 'spine_yaw', 'spine_roll', 'head', 'head_yaw',
                                'head_roll', 'jaw', 'crest', 'crest_roll', 'splay')}
    ch['wing'] = {b: {k: zeros(n) for k in ('sweep', 'flap', 'fold')} for b in (8, 9)}
    ch['arm'] = {s: {k: zeros(n) for k in ('swing', 'abduct', 'turn', 'elbow', 'wrist', 'hand')} for s in (-1, 1)}
    return ch


def idle_channels(n):
    """A slow breath, weight shifting from foot to foot, a lazy look-around; everything a harmonic of the loop."""
    ch = blank(n)
    H = lambda *terms: harmonics(n, terms)
    ch['x'] = H((1, 4.5, .08), (2, 1.0, .35), (3, .5, .6))
    ch['roll'] = H((1, 1.6, .1), (3, .3, .2))
    ch['yaw'] = H((1, 1.8, .55), (2, .5, .1))
    ch['dy'] = H((1, 1.1, .3), (2, .5, .7))
    ch['pitch'] = H((1, .5, .4))
    ch['spine'] = H((1, 1.0, .35), (2, .4, .15))
    ch['spine_yaw'] = H((1, -1.4, .55))
    ch['spine_roll'] = H((1, -.9, .1))
    ch['head_yaw'] = H((1, 8.0, .72), (2, 2.2, .05), (3, 1.4, .4))
    ch['head'] = H((1, 3.0, .85), (2, 1.2, .3))
    ch['head_roll'] = H((1, 1.8, .3), (3, .6, .1))
    ch['jaw'] = H((1, 1.2, .5), (2, .8, .1))
    ch['crest'] = H((1, 1.6, .5), (2, .6, .2))
    ch['crest_roll'] = H((1, .8, .1))
    for b, side in ((8, -1), (9, 1)):
        w = ch['wing'][b]
        w['flap'] = H((1, 2.2, .4 + .04 * side), (2, 1.0, .85 + .05 * side), (3, .5, .2))
        w['sweep'] = H((1, 1.4, .55 + .05 * side), (2, .6, .1))
        w['fold'] = H((1, 1.0, .7), (2, .5, .3 + .06 * side))
    drive = ch['roll']
    for side in (-1, 1):
        a = ch['arm'][side]
        own = H((1, 2.4, .25 + .08 * side), (2, 1.0, .6 - .1 * side))
        a['swing'] = [20 + spring(own, 3.0, .35)[t] + spring(ch['x'], 2.0, .4)[t] * .25 for t in range(n)]
        a['abduct'] = [1.5 * v for v in spring(drive, 2.4, .4)]
        a['elbow'] = [4.0 + 1.6 * v for v in spring(own, 4.0, .3)]
        a['wrist'] = [3.0 + 1.2 * v for v in spring(own, 5.0, .3)]
        a['hand'] = [2.0 + 1.0 * v for v in spring(own, 6.0, .3)]
    return ch


def gait_channels(g, n):
    cyc = g['cycles']
    ch = blank(n)
    period = n / cyc
    u = [t / period for t in range(n)]
    c = lambda x: math.cos(2 * math.pi * x)
    # the right foot lands at u = 0 and supports until u = duty, the left one half a cycle later
    mid = g['duty'] / 2
    H = lambda *terms: harmonics(n, [(k * cyc, a, ph) for k, a, ph in terms])
    sway, roll, twist = g['sway'], g['roll'], g['twist']
    # Character: low-frequency, large, weighted motion. Every part runs at the step rate or slower (the cycle, or the whole
    # two-cycle loop for the drift), with its own phase and a lag spring that may settle once (zeta .6 to .8), no ringing.
    S = lambda *terms: harmonics(n, terms)
    step = lambda x: (2 * x) % 1.0                                      # 0..1 across one step, 0 as a foot lands
    lag = lambda x, f, z=ZETA_S: spring(x, f * cyc, z)
    sink = g['sink']
    bounce = g.get('bounce', 0.0)
    flight = (g['duty'] * 2) % 1.0 if g['duty'] < .5 else None           # a run: the body rises through the flight and sinks on landing
    ch['dy'] = [sink * weight_drop(step(x)) - (bounce * smooth(1 - abs(step(x) - (.5 + flight / 2 if flight is not None else .5)) / .32) if bounce else 0.0)
                for x in u]                                              # the body sinks onto each landing foot, then recovers
    ch['x'] = [a + b for a, b in zip(H((1, sway, mid), (2, .18 * sway, mid + .2)), S((1, .25 * sway, .31)))]
    ch['roll'] = [a + b for a, b in zip(H((1, -roll, mid), (2, .22 * roll, .1)), S((1, .35 * roll, .12)))]
    pelvis_yaw = H((1, twist, 0.0), (2, .2 * twist, .3))
    ch['yaw'] = [a + b for a, b in zip(pelvis_yaw, S((1, .4 * twist, .62)))]
    ch['pitch'] = [g['lean'] + v + w for v, w in zip(lag([-.5 * x for x in ch['dy']], 1.6), S((1, .8, .45)))]
    ch['spine'] = [g['spine'] + v for v in lag([-.35 * x for x in ch['dy']], 1.4)]
    ch['spine_yaw'] = [a + b for a, b in zip(lag([-1.5 * x for x in pelvis_yaw], 1.5), S((1, -.5 * twist, .55)))]
    ch['spine_roll'] = [a + b for a, b in zip(lag(H((1, .8 * roll, mid + .1)), 1.4), S((1, 1.6, .3)))]
    drift = g['drift']
    ch['head_yaw'] = [-.4 * a + b + c for a, b, c in zip(pelvis_yaw, lag([-1.2 * x for x in ch['spine_yaw']], 1.2), S((1, drift, .2), (2, .25 * drift, .5)))]
    ch['head'] = [g['head'] + v + w for v, w in zip(lag([.55 * x for x in ch['dy']], 1.0), S((1, .7 * drift, .5)))]
    ch['head_roll'] = [a + b for a, b in zip(lag(H((1, -.9 * roll, mid)), 1.2), S((1, .3 * drift, .7)))]
    ch['jaw'] = lag(H((1, .8 + g['lean'] * .1, .2)), 1.3)
    ch['crest'] = [a + b for a, b in zip(lag([.6 * x for x in ch['dy']], .9), S((1, 1.5, .1)))]
    ch['crest_roll'] = lag(H((1, 1.6, .3)), 1.0)
    W = g['wing']
    for b, side in ((8, -1), (9, 1)):
        w = ch['wing'][b]
        breath = H((1, 1.0, .15 + .05 * side), (2, .3, .4))
        w['flap'] = [g['wing0'] + v + x for v, x in zip(lag([W * x for x in breath], 1.1 + .1 * side, .6), S((1, .3 * W, .2 + .06 * side)))]
        w['sweep'] = lag([.6 * W * x / twist for x in pelvis_yaw], 1.0, .6)
        w['fold'] = [v + x for v, x in zip(lag([.5 * W * x for x in breath], .9, .6), S((1, .2 * W, .6)))]
    A, A0 = g['arm'], g['arm0']
    for side in (-1, 1):
        heavy = side < 0                                                 # the blade arm: a heavier, slower pendulum
        ph = (0.0 if heavy else .5) + (.04 if heavy else -.03)
        drive = [A * (1.0 - .12 * heavy) * (c(x - ph) + .15 * c(2 * (x - ph) - .2)) for x in u]
        drive = [d + e for d, e in zip(drive, S((1, .3 * A, .15 + .22 * side)))]
        a = ch['arm'][side]
        pend = lag(drive, 1.15 if heavy else 1.4, .55 if heavy else .65)
        a['swing'] = [A0 + .2 * d + .85 * l for d, l in zip(drive, pend)]
        a['abduct'] = [g.get('abd', ABD) + g.get('abd_sway', 3.0) * c(x - ph - .25) for x in u]
        a['elbow'] = [g['elbow'] + .5 * v for v in lag(drive, 1.2, .6)]
        a['wrist'] = [g['wrist'] - .6 * v for v in lag(drive, 1.0, .6)]
        a['hand'] = [g['hand'] - .4 * v for v in lag(drive, .9, .6)]
    return ch


# ---- building, registering and checking

def parse(data, skeleton):
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = len(skeleton)
    model = mmd.MMD.parse(data, len(skeleton))
    model.type = SPECIES
    return model


def landings(slot):
    g = GAIT[slot]
    if g.get('still'):
        return []
    period = g['n'] / g['cycles']
    return sorted({round(c * period + (0.5 * period if h else 0)) % g['n'] for c in range(g['cycles']) for h in (0, 1)})


def build(data, skeleton, slots=SLOTS, check_source=True):
    if check_source and [b[1] for b in skeleton] != PARENTS:
        raise ValueError('not the Dragomon rig')
    model = parse(data, skeleton)
    rig = Rig(model, skeleton)
    result = copy.deepcopy(model)
    notes = {}
    for slot in slots:
        frames, note = author(rig, slot)
        events = [(t, 'sound', dict(op='sound', bank=1, note=11 if slot != 4 else 16, frame=t + 1)) for t in landings(slot)]
        program = mmd.encode_anim(frames, NB, 0, events, tol=TOLERANCE, repeats=False)
        index = model.anims.table[slot]
        result.anims.anims[index] = program
        notes[slot] = note
    for animation in result.anims.anims:
        animation.tail = b''
    return result, notes


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, default=ROOT / 'build/imported-model-edit/edit/291-Dragomon.MMD')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--tim', type=Path, default=ROOT / 'build/imported-model-edit/edit/291-Dragomon.TIM')
    p.add_argument('--tim-out', type=Path, required=True)
    a = p.parse_args()
    sk = json.loads(next((ROOT / 'content/species').glob('291-*.json')).read_text())['model']['skeleton']
    result, notes = build(a.source.read_bytes(), sk)
    data = result.build()
    a.out.write_bytes(data)
    a.tim_out.write_bytes(a.tim.read_bytes())    # the texture is not touched
    print(motionstorage.audit(data, NB)['resident_bytes'], len(data))


# ---- measurements (used by the tests and while tuning)

def measure(model, skeleton, slot):
    """Per clip: ticks, root speed, per foot (5, 7) the stance slip of the shin's origin and of the sole's lowest vertex
    (percent of the root speed, over the ticks the sole is within 1 unit of the floor, (the last step of each contact, the sole rolling off the ground, is left out)), the floor penetration of the
    feet and of the arm tips, the pelvis bob and sway."""
    rig = Rig(model, skeleton)
    frames = animsheet.slot_frames(model, NB, slot)[0]
    n = len(frames)
    speed = abs(frames[-1][0][8] - frames[0][0][8]) / max(1, n - 1)
    out = dict(ticks=n, speed=speed, feet={}, arm_floor=0.0, foot_floor=0.0)
    mats = []
    for f in frames:
        g = copy.deepcopy(f)
        root = g[0][8]
        g[0] = [4096] * 3 + [0] * 6
        mats.append((mmd.bone_matrices(model, g), root))
    for shin in (5, 7):
        low, org = [], []
        for M, root in mats:
            Mb = np.array(M[shin])
            w = rig.verts[shin] @ Mb[:3, :3].T + Mb[:3, 3]
            i = int(w[:, 1].argmax())
            c = Mb[:3, :3] @ np.array(rig.leg[4 if shin == 5 else 6]['s_loc'], float) + Mb[:3, 3]
            low.append((w[i, 1], c[2] + root, w[i, 0], c[1]))
            org.append(Mb[2, 3] + root)
        stance = [t for t in range(n - 1) if low[t][0] > -1 and low[t + 1][0] > -1]
        # the last step of each contact is the sole rolling off the ground (its centre travels with the roll): not counted
        stance = [t for t in stance if (t + 1) in stance or (t + 1) % (n - 1) in stance]
        sl = [abs(low[t + 1][1] - low[t][1]) / speed * 100 for t in stance] if speed else []
        so = [abs(org[t + 1] - org[t]) / speed * 100 for t in stance] if speed else []
        out['feet'][shin] = dict(stance=len(stance), slip_sole=(sum(sl) / len(sl) if sl else 0, max(sl, default=0)),
                                 slip_origin=(sum(so) / len(so) if so else 0, max(so, default=0)))
        out['foot_floor'] = max(out['foot_floor'], max(l[0] for l in low))
    for b in (12, 13, 16, 17):
        for M, root in mats:
            Mb = np.array(M[b])
            w = rig.verts[b] @ Mb[:3, :3].T + Mb[:3, 3]
            out['arm_floor'] = max(out['arm_floor'], float(w[:, 1].max()))
    ys = [np.array(M[3])[1, 3] for M, r in mats]
    xs = [np.array(M[3])[0, 3] for M, r in mats]
    out['bob'] = max(ys) - min(ys)
    out['sway'] = max(xs) - min(xs)
    return out


# ---- penetration: vertices of a limb inside the parts it must not cut (point in mesh, as for Okuwamon)

BODY = (1, 2, 3, 18, 19)
GROUPS = {'legL': (4, 5), 'legR': (6, 7), 'armL': ARM_L, 'armR': ARM_R, 'wingL': (8,), 'wingR': (9,)}


def penetration(model, skeleton, pose, body=None):
    """Counts per limb for one pose. Arms and legs against the body and the other limbs; a wing against the body and
    the arms (a wing is not a part to cut into). The first bone of a limb is built into the body, tested against limbs."""
    from tools.models.field_animations import okuwamon_limbs as ok
    body = body or ok.Body(model, skeleton)
    mats, world = body.world(pose)
    limbs = {k: v for k, v in GROUPS.items() if not k.startswith('wing')}
    out = {}
    for key, chain in GROUPS.items():
        others = tuple(b for n, c in limbs.items() if n != key for b in c)
        if key.startswith('wing'):
            out[key] = body.count(mats, world, chain, BODY + others, chain[0], ok.WING_SOCKET)
        else:
            out[key] = body.count(mats, world, chain[1:], BODY + others) + body.count(mats, world, chain[:1], others)
    return out


def penetration_report(model, skeleton, slot):
    from tools.models.field_animations import okuwamon_limbs as ok
    body = ok.Body(model, skeleton)
    frames = animsheet.slot_frames(model, NB, slot)[0]
    worst = {}
    total = 0
    for f in frames[:-1]:
        for k, v in penetration(model, skeleton, f, body).items():
            worst[k] = max(worst.get(k, 0), v)
            total += v
    return worst, total


def angular_rates(model, slot):
    """Per bone (not the root), the largest turn between two ticks around the loop, degrees, from the local eulers."""
    frames = animsheet.slot_frames(model, NB, slot)[0]
    worst = {}
    for t in range(len(frames) - 1):
        a, b = frames[t], frames[(t + 1) % (len(frames) - 1)]
        for k in range(1, NB):
            ra, rb = np.array(mmd.rot_matrix(*a[k][3:6])), np.array(mmd.rot_matrix(*b[k][3:6]))
            c = max(-1.0, min(1.0, (np.trace(ra.T @ rb) - 1) / 2))
            worst[k] = max(worst.get(k, 0.0), math.degrees(math.acos(c)))
    return worst


def jumps(model, skeleton, slot):
    """Largest tick-to-tick mean vertex displacement (root motion removed) over the median, around the loop."""
    from tools.models.field_animations import okuwamon_limbs as ok
    body = ok.Body(model, skeleton)
    frames = animsheet.slot_frames(model, NB, slot)[0]
    worlds = [body.world(f)[1] for f in frames[:-1]]
    d = [float(np.linalg.norm(worlds[(i + 1) % len(worlds)] - worlds[i], axis=1).mean()) for i in range(len(worlds))]
    med = float(np.median(d))
    return max(d) / med if med else 0.0, med


if __name__ == '__main__':
    main()


def fast_share(model, slot, cycles):
    """Per bone that is not a leg, the share of the angle signal's variance above twice the step rate (4 x cycles a loop):
    the quick flutter the clips must not have (foot swing is the legs' own, so legs are left out)."""
    frames = animsheet.slot_frames(model, NB, slot)[0][:-1]
    n = len(frames)
    out = {}
    for k in range(1, NB):
        if k in (4, 5, 6, 7):
            continue
        r0 = np.array(mmd.rot_matrix(*frames[0][k][3:6]))
        sig = np.array([
                        np.degrees(np.arccos(max(-1, min(1, (np.trace(r0.T @ np.array(mmd.rot_matrix(*f[k][3:6]))) - 1) / 2)))) for f in frames])
        sp = np.abs(np.fft.rfft(sig - sig.mean())) ** 2
        total = sp.sum()
        out[k] = float(sp[int(4 * cycles) + 1:].sum() / total) if total > 1e-9 else 0.0
    return out
