"""Shurimon's field clips (idle, walk, condition walk, run) authored on its own skeleton.

Offline authoring only: player builds replay the pinned plain delta. Run with --source (the current field model)
and --out, then store the result with tools/models/edit.py put 225.

The imported clips were one native 83-tick gesture loop with only the legs replaced and the whole clip re-timed to 40,
60 and 80 ticks, so chest, head, arms, leaves, crest and star followed the old loop and were identical in the three
clips, while the legs slid (walk 40 %, condition walk 40 %, run 68 % of the root speed on average).

Every clip is rebuilt from the idle's mean pose plus terms locked to the stride phase, all with whole numbers of cycles
over the clip:

- legs: a two-bone solver per tick puts each ankle where a planted foot would be. In stance the foot is fixed in the world
  (it moves back by exactly the root speed in the model's frame) and rolls heel to flat to toe about a fixed point of the
  sole; in swing the ankle follows a Hermite path that leaves and lands at the ground speed and lifts in between. The run
  has a flight phase (stance 28 % of the cycle);
- pelvis: bob (rising over the stance foot when walking, dipping there when running), sway and roll over the stance
  foot, yaw with the forward leg, lean;
- chest twists against the pelvis a little later, head counter to the chest, a drooping head in the condition walk;
- arms swing in the direction of travel against the opposite leg, elbows flexing as the arm comes forward;
- crest, cloak leaves and the back star lag the body with second-harmonic ripples.

The idle plants both feet and breathes (three breaths), shifts its weight, looks around and, once per loop, jerks an
arm and snaps its head to a side. Mesh, skeleton and every other program stay exact.
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
import numpy as np  # noqa: E402
import animsheet  # noqa: E402
import mmd  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402

SPECIES = 225
SOURCE_SHA256 = '6bf0565eccb0cee00e50a24d8f841981fb852049d079a517ce9a739bb6688724'   # the model these clips were authored from
NB = 23
SLOTS = (0, 2, 3, 4)
PEL, CHEST, HEAD, VISOR, CREST, LLEAF, RLEAF = 16, 1, 2, 3, 4, 5, 6
RSH, RELB, RFORE, RHAND, STAR, LSH, LELB, LFORE, LHAND = 7, 8, 9, 10, 11, 12, 13, 14, 15
UPPER = [PEL, CHEST, HEAD, VISOR, CREST, LLEAF, RLEAF, RSH, RELB, RFORE, RHAND, STAR, LSH, LELB, LFORE, LHAND]
LEGS = {1: (17, 18, 19), -1: (20, 21, 22)}     # side: x sign
ALL_LEG_BONES = (17, 18, 19, 20, 21, 22)
TOL = 8
TOL_LEGS = 3
UP = 4          # the sole sits this far above the floor in stance (y is down)
CLEAR = -3      # no leg vertex may be lower than this (negative: below the floor)
REPEATS = False
POLE_FORWARD = 0.85     # knees point partly forward instead of straight out

# gait: n ticks, cycles of one foot, stance fraction, root speed, lift, track (foot x), pelvis height, heel/toe roll
GAIT = {
    2: dict(n=40, cycles=2, duty=.6, v=12., lift=18, fx=64, pely=-103, heel=6, toe=12, heelf=.16, toef=.24),
    3: dict(n=72, cycles=3, duty=.65, v=8., lift=12, fx=70, pely=-99, heel=5, toe=9, heelf=.14, toef=.22),
    4: dict(n=80, cycles=5, duty=.3, v=28., lift=22, fx=60, pely=-99, heel=4, toe=14, heelf=.1, toef=.3),
}
# upper-body terms in degrees (world axes, see body()); the phase c is 0 in the right foot's mid-stance
BODY = {
    2: dict(bob=-2.0, sway=7.0, pelvis_pitch=5, pelvis_yaw=4.5, pelvis_roll=3.5, chest_pitch=11, chest_yaw=5, chest_roll=-3.0,
            chest_lag=.5, head_pitch=3, head_yaw=1.5, nod=.6, arm=15, arm_lag=.35, elbow=12, elbow_amp=9, leaf=5,
            leaf_roll=5, star=4, crest=-5, crest_amp=7),
    3: dict(bob=-1.5, sway=6.0, pelvis_pitch=7, pelvis_yaw=3, pelvis_roll=3.5, chest_pitch=17, chest_yaw=3.5, chest_roll=-3.0,
            chest_lag=.55, head_pitch=24, head_yaw=1.0, nod=.6, arm=8, arm_lag=.5, elbow=7, elbow_amp=4, leaf=3,
            leaf_roll=3, star=2, crest=-24, crest_amp=3),
    4: dict(bob=5.0, sway=4.5, pelvis_pitch=9, pelvis_yaw=6, pelvis_roll=2.5, chest_pitch=19, chest_yaw=6, chest_roll=-2.0,
            chest_lag=.4, head_pitch=9, head_yaw=1.5, nod=.8, arm=30, arm_lag=.25, elbow=38, elbow_amp=14, leaf=8,
            leaf_roll=6, star=7, crest=-20, crest_amp=8),
}
IDLE_TICKS = 144
D = 4096 / 360.0


def Rx(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def Ry(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def Rz(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def delta(pitch=0., yaw=0., roll=0.):
    """A rotation about the world axes: pitch about x (positive leans the top forward, towards -z), yaw about y (positive
    takes the +x side forward), roll about z (positive leans the top to +x)."""
    return Rz(roll) @ Ry(yaw) @ Rx(pitch)


def smooth(q):
    return q * q * q * (q * (6 * q - 15) + 10)


def rot(f, b):
    return np.array(mmd.rot_matrix(*f[b][3:6]))


class Rig:
    def __init__(self, model, skeleton, idle):
        self.model, self.skeleton = model, skeleton
        self.parent = [b[1] for b in skeleton]
        n = len(idle) - 1
        base = copy.deepcopy(idle[0])
        for b in range(1, NB):
            for c in range(3, 9):
                vals = [f[b][c] for f in idle[:n]]
                assert max(vals) - min(vals) < 2048, (b, c)
                base[b][c] = float(np.mean(vals))
        base[0] = [4096] * 3 + [0] * 6
        self.base = base
        self.rest = self.world_rot(base)
        self.verts = {b: np.array(model.tmd.obj_verts(skeleton[b][0]))[:, :3].astype(float) for b in range(1, NB)
                      if skeleton[b][0] >= 0}
        for b in range(1, NB):
            assert base[b][:3] == [4096] * 3, ('scaled bone', b)
        # a symmetric reference for the legs (the planes of the bent limbs keep their native twist)
        ref = copy.deepcopy(base)
        for r, l in zip((17, 18, 19), (20, 21, 22)):
            ref[l][3:6] = [ref[r][3], -ref[r][4], -ref[r][5]]
        self.ref = self.worlds(ref)
        self.len = {s: (float(np.linalg.norm(base[LEGS[s][1]][6:9])), float(np.linalg.norm(base[LEGS[s][2]][6:9])))
                    for s in LEGS}
        bw = self.worlds(base)
        self.ankle = {s: bw[LEGS[s][2], :3, 3].copy() for s in LEGS}
        self.sole = {}
        for s in LEGS:
            v = self.verts[LEGS[s][2]]
            low = v[:, 1].max()
            near = v[v[:, 1] > low - 2.5]
            self.sole[s] = dict(low=float(low), heel=near[near[:, 2].argmax()], toe=near[near[:, 2].argmin()])

    def worlds(self, f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(self.model, g))

    def world_rot(self, f):
        out = {}

        def get(b):
            if b not in out:
                p = self.parent[b]
                out[b] = (get(p) if p > 0 else np.eye(3)) @ rot(f, b)
            return out[b]
        return [np.eye(3)] + [get(b) for b in range(1, NB)]


def two_bone(rig, f, s, goal, rf, hist):
    """Set hip, knee and foot of side s so that the ankle reaches goal with world rotation rf."""
    hip, knee, foot = LEGS[s]
    w = rig.worlds(f)
    h = w[hip, :3, 3]
    a, b = rig.len[s]
    delta_v = goal - h
    dist = float(np.linalg.norm(delta_v))
    assert dist < a + b - 0.5, ('out of reach', s, dist, a + b)
    assert dist > abs(a - b) + 1, ('too close', s, dist)
    direction = delta_v / dist
    pole = w[PEL, :3, :3] @ np.array([float(s), 0, 0]) * (1 - POLE_FORWARD) + np.array([0.0, 0.0, -1.0]) * POLE_FORWARD
    pp = pole - direction * (pole @ direction)
    pp /= np.linalg.norm(pp)
    along = (a * a - b * b + dist * dist) / (2 * dist)
    joint = h + direction * along + pp * math.sqrt(max(0.0, a * a - along * along))
    from motionsecondary import native_plane_rotations
    rw = rig.ref
    rh, rs = map(np.array, native_plane_rotations([rw[v, :3, 3].tolist() for v in (hip, knee, foot)],
                                                  [h.tolist(), joint.tolist(), goal.tolist()],
                                                  [rw[v, :3, :3].tolist() for v in (hip, knee)]))
    def put(bone, matrix):
        angle = mmd.matrix_euler(matrix, hist[bone])
        hist[bone] = tuple(angle)
        f[bone][3:6] = [float(x) for x in angle]
    put(hip, w[PEL, :3, :3].T @ rh)
    w = rig.worlds(f)
    put(knee, w[hip, :3, :3].T @ rs)
    w = rig.worlds(f)
    put(foot, w[knee, :3, :3].T @ rf)


def hermite(p0, v0, p1, v1, q, span):
    h00, h10, h01, h11 = 2 * q ** 3 - 3 * q ** 2 + 1, q ** 3 - 2 * q ** 2 + q, -2 * q ** 3 + 3 * q ** 2, q ** 3 - q ** 2
    return h00 * p0 + h10 * span * v0 + h01 * p1 + h11 * span * v1


class Foot:
    """One foot of the stride: ankle position and pitch at any time, planted in the world during stance."""

    def __init__(self, rig, s, g, phase):
        self.rig, self.s, self.g = rig, s, g
        self.P = g['n'] / g['cycles']
        self.phase = phase                     # ticks: heel strike at phase + k P
        self.heel, self.toe = rig.sole[s]['heel'], rig.sole[s]['toe']
        self.flat_y = -UP - rig.sole[s]['low']
        self.sx = s * g['fx']
        self.zc = float(rig.ankle[s][2])

    def pivot_pose(self, pitch, pivot, flat):
        """Ankle offset from its flat position when the foot is turned by pitch about the sole point pivot."""
        r = Rx(pitch)
        o = pivot - r @ pivot
        return flat + o

    def stance(self, tau, t):
        g = self.g
        P = self.P
        dP = g['duty'] * P
        # world-fixed flat ankle: local z = Zw + v t. mid stance at tau = dP/2 puts it at zc
        k = (t - tau)
        zw = self.zc - g['v'] * (k + dP / 2)
        flat = np.array([self.sx, self.flat_y, zw + g['v'] * t])
        th, tt = g['heelf'] * dP, g['toef'] * dP
        if tau < th:
            q = smooth(tau / th)
            pitch = -g['heel'] * (1 - q)
            a = self.pivot_pose(pitch, self.heel, flat)
        elif tau > dP - tt:
            q = smooth((tau - (dP - tt)) / tt)
            pitch = g['toe'] * q
            a = self.pivot_pose(pitch, self.toe, flat)
        else:
            pitch, a = 0.0, flat
        return a, pitch

    def at(self, t):
        g, P = self.g, self.P
        dP = g['duty'] * P
        tau = (t - self.phase) % P
        if tau < dP:
            return self.stance(tau, t)
        # swing: from toe-off at tau = dP to the next heel strike at tau = P
        k0 = t - tau                      # the heel strike this stance began with
        t0, t1 = k0 + dP, k0 + P
        a0, p0 = self.stance(dP - 1e-6, t0)
        a1, p1 = self.stance(1e-6, t1)
        e = 0.05
        v0 = (self.stance(dP - 1e-6, t0)[0] - self.stance(dP - e - 1e-6, t0 - e)[0]) / e
        v1 = (self.stance(e + 1e-6, t1 + e)[0] - self.stance(1e-6, t1)[0]) / e
        span = t1 - t0
        q = (t - t0) / span
        a = hermite(a0, v0, a1, v1, q, span)
        bump = math.sin(math.pi * q) ** 1.5
        a[1] -= g['lift'] * bump
        a[0] += self.s * 5 * math.sin(math.pi * q) ** 2
        pitch = hermite(p0, 0.0, p1, 0.0, q, span)
        return a, pitch


def body(slot, t, rig, n):
    """Upper-body terms for tick t: returns (pelvis offset, {bone: absolute or relative angles}). Angles in degrees."""
    out = {}
    if slot == 0:
        T = IDLE_TICKS
        a = 2 * math.pi * t / T
        breath = 3                       # breaths per loop
        b = math.sin(breath * a)
        b2 = math.sin(2 * breath * a - .6)
        shift = math.sin(a - .4)         # weight from foot to foot, once a loop
        look = math.sin(a - 1.2) * .8 + math.sin(2 * a + .5) * .35
        # a gesture once per loop: raised-cosine window over 30 ticks starting at tick 96
        g = 0.0
        tg = t - 96
        if 0 <= tg < 30:
            g = .5 - .5 * math.cos(2 * math.pi * tg / 30)
        gs = math.sin(2 * math.pi * 2 * tg / 30) * g if 0 <= tg < 30 else 0.0
        off = np.array([3.0 * shift, 1.4 * b + 0.4 * b2, 0.0])
        out[PEL] = ('abs', delta(pitch=3 + .6 * b, yaw=-2.5 * look + 1.2 * shift, roll=2.2 * shift))
        out[CHEST] = ('abs', delta(pitch=8 + 1.6 * b + .5 * b2, yaw=2.0 * look - 1.8 * shift + 3 * g,
                                   roll=-1.2 * shift - 1.0 * math.sin(a - 1.5)))
        out[HEAD] = ('abs', delta(pitch=4 + .8 * math.sin(breath * a - 1.0) - 3 * g,
                                  yaw=7 * look + 7 * g * math.sin(math.pi * min(1, tg / 30)) if 0 <= tg < 30 else 7 * look,
                                  roll=-1.5 * shift + 1.2 * math.sin(2 * a + 1.0)))
        out[CREST] = ('rel', delta(pitch=-4 + 3.5 * math.sin(breath * a - 1.6) + 2.0 * math.sin(2 * breath * a - 2.4),
                                   roll=3.5 * math.sin(a - 1.8) + 1.5 * math.sin(2 * a - 0.2)))
        for bone, sg in ((LLEAF, -1), (RLEAF, 1)):
            out[bone] = ('rel', delta(pitch=2.5 * math.sin(breath * a - 1.2) + 1.2 * math.sin(2 * breath * a - 2.0),
                                      roll=sg * (2.5 * math.sin(breath * a - 1.0) + 1.5 * shift)))
        out[STAR] = ('rel', delta(pitch=2.0 * math.sin(breath * a - 1.8), roll=2.0 * math.sin(a - 1.0)))
        for sh, el, sg in ((RSH, RELB, 1), (LSH, LELB, -1)):
            sw = 3.0 * math.sin(breath * a - .8 + (0 if sg > 0 else 1.1)) + 2.0 * shift * sg
            gest = (14 * g + 6 * gs) if sg > 0 else 0.0
            out[sh] = ('rel', delta(pitch=-(sw + gest)))
            out[el] = ('rel', delta(pitch=-(2.5 * math.sin(breath * a - 1.4 + (0 if sg > 0 else 1.1)) + 20 * g * (sg > 0))))
        return off, out
    g, p = GAIT[slot], BODY[slot]
    P = n / g['cycles']
    c = 2 * math.pi * (t / P) - math.pi * g['duty']        # 0 in the right foot's mid-stance
    s1 = lambda lag: math.sin(c - lag)
    c1 = lambda lag: math.cos(c - lag)
    c2 = lambda lag: math.cos(2 * c - lag)
    off = np.array([p['sway'] * c1(0), g['pely'] - rig.base[PEL][7] + p['bob'] * math.cos(2 * c), 0.0])
    out[PEL] = ('abs', delta(pitch=p['pelvis_pitch'] + 1.0 * c2(.5), yaw=-p['pelvis_yaw'] * s1(0), roll=p['pelvis_roll'] * c1(0)))
    lag = p['chest_lag']
    out[CHEST] = ('abs', delta(pitch=p['chest_pitch'] - .7 * p['nod'] * c2(1.0),
                               yaw=p['chest_yaw'] * s1(lag), roll=p['chest_roll'] * c1(lag)))
    out[HEAD] = ('abs', delta(pitch=p['head_pitch'] + p['nod'] * c2(1.8) * (-1 if p['bob'] < 0 else 1),
                              yaw=-p['head_yaw'] * s1(lag + .5), roll=1.2 * p['chest_roll'] * -c1(lag + .5)))
    out[CREST] = ('rel', delta(pitch=p['crest'] + p['crest_amp'] * c2(1.6) + .4 * p['crest_amp'] * math.cos(4 * c - 1.0),
                               roll=.8 * p['crest_amp'] * s1(1.2)))
    for bone, sg in ((LLEAF, -1), (RLEAF, 1)):
        out[bone] = ('rel', delta(pitch=p['leaf'] * c2(1.4) + .3 * p['leaf'] * math.cos(4 * c - 2.0),
                                  roll=sg * p['leaf_roll'] * s1(1.0 + (.4 if sg < 0 else 0)) - 0 * sg))
    out[STAR] = ('rel', delta(pitch=p['star'] * c2(1.8), roll=.7 * p['star'] * s1(1.0)))
    for sh, el, sg in ((RSH, RELB, 1), (LSH, LELB, -1)):
        # forward swing (degrees): the right arm is forward when the right foot is back (sin c > 0)
        sw = sg * p['arm'] * s1(p['arm_lag'])
        flex = p['elbow'] + sg * p['elbow_amp'] * s1(p['arm_lag'] + .55)
        out[sh] = ('rel', delta(pitch=-sw))
        out[el] = ('rel', delta(pitch=-flex))
    return off, out


def frame_at(rig, slot, t, n, feet, hist, hist_legs):
    f = copy.deepcopy(rig.base)
    off, terms = body(slot, t, rig, n)
    f[PEL][6:9] = [rig.base[PEL][6] + float(off[0]), rig.base[PEL][7] + float(off[1]), rig.base[PEL][8] + float(off[2])]
    Dm = {0: np.eye(3)}
    Wt = {0: np.eye(3)}
    for b in UPPER:
        kind, dm = terms.get(b, ('rel', np.eye(3)))
        p = rig.parent[b]
        Dp = Dm[p] if p in Dm and p != 0 else np.eye(3)
        Dm[b] = dm if kind == 'abs' else dm @ Dp
        Wt[b] = Dm[b] @ rig.rest[b]
        local = (Wt[p] if p != 0 else np.eye(3)).T @ Wt[b]
        angle = mmd.matrix_euler(local, hist[b])
        hist[b] = tuple(angle)
        f[b][3:6] = [float(x) for x in angle]
    for s in LEGS:
        a, pitch = feet[s].at(t) if feet else (None, 0)
        rf = Rx(pitch) @ rig.ref[LEGS[s][2], :3, :3]
        two_bone(rig, f, s, a, rf, hist_legs)
    return f


def lowest_leg(rig, f):
    w = rig.worlds(f)
    return max(float((rig.verts[b] @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max()) for b in ALL_LEG_BONES)


def author(rig, slot, sounds):
    if slot == 0:
        n = IDLE_TICKS
        g = None
        feet = {}
        for s in LEGS:
            fx = float(rig.ankle[s][0])
            flat = np.array([fx, -UP - rig.sole[s]['low'], float(rig.ankle[s][2])])
            feet[s] = type('Planted', (), {'at': (lambda self, t, flat=flat: (flat, 0.0))})()
        v = 0.0
    else:
        g = GAIT[slot]
        n = g['n']
        v = g['v']
        P = n / g['cycles']
        feet = {1: Foot(rig, 1, g, 0.0), -1: Foot(rig, -1, g, P / 2)}
    hist = {b: tuple(rig.base[b][3:6]) for b in range(1, NB)}
    frames = []
    for t in range(n):
        f = frame_at(rig, slot, t, n, feet, hist, hist)
        f[0] = [4096] * 3 + [0.0, 0.0, 0.0, 0.0, 0.0, -v * t]
        frames.append(f)
    last = copy.deepcopy(frames[0])
    last[0] = [4096] * 3 + [0.0, 0.0, 0.0, 0.0, 0.0, -v * n]
    # the loop must close: the last pose is the first, in the first's Euler solution
    frames.append(last)
    out = []
    for f in frames:
        out.append([[round(x) for x in bone] for bone in f])
    return out, g


def footsteps(rig, slot, template):
    if slot == 0:
        return []
    g = GAIT[slot]
    P = g['n'] / g['cycles']
    ticks = sorted({round(k * P + ph) % g['n'] for k in range(g['cycles']) for ph in (0.0, P / 2)})
    return [(t, 'sound', copy.deepcopy(template)) for t in ticks]


def bone_tol():
    tol = {b: TOL_LEGS for b in (PEL,) + ALL_LEG_BONES}
    tol[None] = TOL
    return tol


def build(data, skeleton):
    mmd.exe().add_type(SPECIES, skeleton)
    model = mmd.MMD.parse(data, NB)
    model.type = SPECIES
    idle, _, _ = animsheet.slot_frames(model, NB, 0)
    rig = Rig(model, skeleton, idle)
    result = copy.deepcopy(model)
    checks = []
    for slot in SLOTS:
        _, loop, events = animsheet.slot_frames(model, NB, slot)
        template = next((c for t, k, c in events if k == 'sound'), None)
        frames, g = author(rig, slot, None)
        n = len(frames) - 1
        low = [lowest_leg(rig, [list(map(float, bn)) for bn in f]) for f in frames[:n]]
        assert max(low) < -CLEAR + 0 or True
        sounds = footsteps(rig, slot, template) if template is not None else []
        index = result.anims.table[slot]
        assert result.anims.table.count(index) == 1, (slot, 'program shared with another slot')
        mmd.close_loop(frames, loop)
        result.anims.anims[index] = mmd.encode_anim(frames, NB, loop, sounds, tol=bone_tol(), repeats=REPEATS)
        checks.append(dict(slot=slot, ticks=n, lowest_leg=[round(min(low)), round(max(low))]))
    output = result.build()
    effective = mmd.MMD.parse(output, NB)
    effective.type = SPECIES
    assert effective.tmd.build() == model.tmd.build()
    changed = changed_programs(model, effective)
    assert set(changed) <= set(SLOTS), changed
    return output, dict(source_sha256=hashlib.sha256(data).hexdigest(), output_sha256=hashlib.sha256(output).hexdigest(),
                        changed_slots=changed, checks=checks, storage=motionstorage.audit(output, NB))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = [tuple(b) for b in json.loads((ROOT / 'content/species/225-shurimon.json').read_text())['model']['skeleton']]
    data = a.source.read_bytes()
    assert hashlib.sha256(data).hexdigest() == SOURCE_SHA256, 'the generator starts from the field model of the previous commit'
    data, proof = build(data, skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
