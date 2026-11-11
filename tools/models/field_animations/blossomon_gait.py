"""Blossomon's field clips (idle, walk, condition walk, run), written for what the creature is: a tall green stalk with a
purple flower head and a yellow face, two leaf wings, four vine arms ending in red flowers, and five root feet in a ring
round its base.

Offline authoring only: player builds replay the pinned plain delta. Run with --source (the current field model) and --out,
then store the result with tools/models/edit.py put 274.

The imported clips were one 40-tick performance (slot 0) whose arm swing was copied into the walk, condition walk and run:
the five roots never moved and the whole body glided, only rocking 38 degrees about the hips (the roots slid 110-180 %
of the body's speed). Here every clip is built from a step phase, with whole cycles per loop:

- roots (bones 3-7, single pieces carried by bone 1): each is planted on the floor while it supports, laid flat, and in
  its swing it lifts, runs forward over the ground and lands again. Its local offset and angle are solved every tick from the
  body's pose so that the foot stays where it is in the world: no leg to stretch, no reach to clamp. The five roots step in
  two diagonal groups (front right + mid left, front left + mid right) and the back root half a group behind, with a short
  flight when the groups hand over, so a stance is only a few ticks long and its travel stays inside what the roots can
  reach under the stalk;
- the body (bone 1: stalk top, head, arms and leaves hang from it) bobs with the steps (low at mid stance, highest in
  the flight), leans, rolls and twists about the floor under it, not about its own hip; the trunk (bone 2) counter-turns
  a little;
- the flower head (8) and face (9) follow the body later than the trunk, nodding and rolling with a second harmonic;
- the four vines swing as chains: the upper pair against the lower pair, each segment a little later and wider than the one
  before it, the flower at the end whipping; the two leaves flutter later again.

The idle is a calm 96-tick loop: three slow breaths, the head turning and nodding with its own longer period, the vines and
leaves drifting a beat behind, the roots planted. Slots 1, 18 and 33 share the idle's program and take it too. The blink
(texture moves) of every clip is kept. Mesh, skeleton and every other program stay exact.
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

SPECIES = 274
SOURCE_SHA256 = '9ab0eb3a754c7bd5a098ab86ee5f142d77ee7364e54c0f2dbc18c5bcf6fd6a87'   # the model these clips were authored from
NB = 24
SLOTS = (0, 2, 3, 4)
PEL, TRUNK, HEAD, FACE = 1, 2, 8, 9
FEET = (3, 4, 5, 6, 7)          # front right, mid right, back, mid left, front left
ARMS = {1: ((10, 11, 12), (13, 14, 15)), -1: ((16, 17, 18), (19, 20, 21))}      # side: (upper vine, lower vine)
LEAVES = {1: 22, -1: 23}
UPPER = [TRUNK, HEAD, FACE] + [b for s in ARMS.values() for c in s for b in c] + list(LEAVES.values())
D = 4096 / 360.0
TOL_FEET, TOL_BODY, TOL_REST = 1, 7, 11
FLOOR = 0.0          # the soles' rest height in the model (y down): the roots stand just above it

# per clip: n ticks, cycles of the step, v root speed, duty (fraction of a cycle a root supports), lift of the swing, body
GAITS = {
    2: dict(n=48, cycles=3, v=15., duty=.26, lower_up=6, lift=26, spread=12, back=.25,
            bob=7, lean=4, roll=4.5, yaw=3.5, sway=3, trunk=1.5, tpitch=3.5, tyaw=5, troll=0,
            head_nod=5, head_roll=4, head_yaw=3, head_lag=.13, face=2,
            vrate=1 / 3, vine_swing=9, vine_flap=4, vine_lag=.1, lower_swing=7, leaf=5, leaf_lag=.2, leaf_back=0),
    3: dict(n=60, cycles=3, v=10., duty=.34, lower_up=8, lift=20, spread=16, back=.3,
            bob=4, lean=4, roll=6.5, yaw=2.4, sway=3, trunk=0.8, xout=1.8, tpitch=2.5, tyaw=3.5, troll=0.8,
            head_nod=4, head_roll=3, head_yaw=2, head_lag=.2, face=1.5, head_droop=3, sink=7,
            vrate=1 / 3, vine_swing=6, vine_flap=3, vine_lag=.12, lower_swing=5, leaf=4, leaf_lag=.25, leaf_back=0, droop=10),
    4: dict(n=33, cycles=3, v=36., duty=.17, lower_up=14, lift=44, spread=28, back=.25,
            bob=11, lean=6, roll=4.5, yaw=4.5, sway=3, trunk=0.6, tpitch=4, tyaw=6, troll=0.8,
            head_nod=4, head_roll=3, head_yaw=2, head_lag=.12, face=2, head_back=-14,
            vrate=1 / 3, vine_swing=7, vine_flap=3.5, vine_lag=.08, lower_swing=8, leaf=6, leaf_lag=.16, leaf_back=0),
}
IDLE_TICKS = 96
# the roots' step phases (fraction of a cycle) and where each one's stance is centred relative to its rest place (z, units)
XOUT = {4: 10, 6: 10}   # scaled per clip by 'xout'                         # the middle roots stand wider, so the front root passes beside them
STEP = {3: (0.0, -11), 6: (0.0, 6), 7: (.5, -11), 4: (.5, 8), 5: (None, 2)}


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
    q = min(1.0, max(0.0, q))
    return q * q * q * (q * (6 * q - 15) + 10)


def wave(x, lag=0., second=0., ph=0.):
    """A loose wave of the phase x (radians): the fundamental and a second harmonic, never a pure sinusoid."""
    return math.sin(x - lag) + second * math.sin(2 * (x - lag) + ph)


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
        W = self.worlds(base)
        self.origin = {b: W[b, :3, 3].copy() for b in range(1, NB)}
        # a foot's centre (the mean of its vertices) and its lowest point, as the base pose has them
        self.centre, self.sole_y = {}, {}
        for b in FEET:
            wv = self.verts[b] @ W[b, :3, :3].T + W[b, :3, 3]
            self.centre[b] = wv.mean(0)
            self.sole_y[b] = float(wv[:, 1].max())
            self.rel = getattr(self, 'rel', {})
            self.rel[b] = wv - wv.mean(0)
        self.nominal = np.array(base[PEL][6:9], float)

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


class Roots:
    """The five roots' ground targets: planted while they support, lifted and run forward over the ground in the swing."""

    def __init__(self, rig, g):
        self.rig, self.g = rig, g
        self.P = g['n'] / g['cycles']
        self.v = g['v']
        self.phase = {k: self.P * (g['back'] if STEP[k][0] is None else STEP[k][0]) for k in FEET}

    def at(self, k, t):
        """(offset of the root's centre from its rest place in the model's frame, pitch in degrees, lift) at tick t."""
        g, P, v = self.g, self.P, self.v
        d = g['duty']
        tau = t - self.phase[k]
        m = math.floor(tau / P + 1e-9)
        u = (tau - m * P) / P
        zg = STEP[k][1] - v * (self.phase[k] + (m + d / 2) * P)      # where this stance is on the ground (z)
        side = 1 if self.rig.centre[k][0] > 1 else (-1 if self.rig.centre[k][0] < -1 else 0)
        x = side * (g['spread'] + XOUT.get(k, 0) * g.get('xout', 1))
        if u < d:
            return np.array([x, 0.0, zg + v * t]), 0.0, 0.0
        q = (u - d) / (1 - d)
        z = zg + (-v * P) * smooth(q)
        lift = g['lift'] * math.sin(math.pi * q) ** 0.8 * (1 + .12 * math.sin(2 * math.pi * q))
        pitch = -14 * math.sin(2 * math.pi * q) * math.sin(math.pi * q) ** .5
        xs = x + side * 8 * math.sin(math.pi * q) ** 2
        return np.array([xs, 0.0, z + v * t]), pitch, lift


class Planted:
    """The roots of the idle: all five stand where the base pose has them."""

    SPREAD = 4                                       # each outer root a little wider than the base pose: they only touch, not cross

    def __init__(self, rig=None):
        self.rig = rig

    def at(self, k, t):
        c = self.rig.centre[k][0] if self.rig else 0
        return np.array([self.SPREAD * (1 if c > 1 else -1 if c < -1 else 0), 0.0, 0.0]), 0.0, 0.0


def vine(seg, side, phase, swing, flap, lag, second=.3):
    """Fore/aft swing (yaw) and flap (roll) of vine segment seg (0 shoulder, 1 elbow, 2 flower): each later and wider."""
    k = 1.0 + .55 * seg
    sw = swing * k * wave(phase, lag * seg, second, .6 + seg)
    fl = flap * k * wave(2 * phase, lag * seg * 2, second, 1.1 + seg)
    return side * sw, side * fl


def walk_terms(slot, t, n, g):
    """The upper body for a stepping clip at tick t: the pelvis offset, the tilt about the floor under it, and the world
    rotations (degrees) of trunk, head, face, vines and leaves."""
    P = n / g['cycles']
    d = g['duty']
    x = 2 * math.pi * t / P                          # the step phase
    mid = 2 * math.pi * d / 2                         # group A's mid stance
    loop = 2 * math.pi * t / n
    rise = .5 - .5 * math.cos(2 * (x - mid)) + .16 * math.sin(2 * (x - mid) - .9)
    off = np.array([g['sway'] * math.cos(x - mid - .25) + .8 * math.sin(loop), g.get('sink', 0) - g['bob'] * rise, 0.0])
    lean = g['lean'] + .12 * g['bob'] * (1 - rise) + .7 * math.sin(loop + 1.0)
    tilt = delta(pitch=lean, yaw=g['yaw'] * math.sin(x - mid) + .4 * g['yaw'] * math.sin(2 * x - 1.0),
                 roll=g['roll'] * math.cos(x - mid) + .3 * g['roll'] * math.sin(2 * x + .6))
    out = {}
    # the trunk lags the pelvis: it twists against it, leans toward the planted roots and pitches on every step
    out[TRUNK] = delta(pitch=-.5 * g['trunk'] * math.cos(2 * (x - mid) - .4) + g['tpitch'] * wave(2 * x, 1.1, .3, .5),
                       yaw=-g['tyaw'] * math.sin(x - mid - .9) + .3 * g['tyaw'] * math.sin(2 * x - 1.6),
                       roll=-g['trunk'] * math.cos(x - mid - .3) - g['troll'] * math.cos(x - mid - .8) + .25 * g['troll'] * math.sin(2 * x - .4))
    hl = 2 * math.pi * g['head_lag']
    droop = g.get('head_droop', 0) + g.get('head_back', 0)
    out[HEAD] = delta(pitch=droop + g['head_nod'] * wave(x, 2 * hl, .3, .8) - .3 * lean * 0,
                      yaw=g['head_yaw'] * math.sin(x - mid - hl - .5) + 1.5 * math.sin(loop + 2.0),
                      roll=-g['head_roll'] * math.cos(x - mid - hl) + .3 * g['head_roll'] * math.sin(2 * x - hl))
    out[FACE] = delta(pitch=g['face'] * wave(2 * x, 2 * hl + .9, .4, 1.4), roll=.6 * g['face'] * math.sin(x - hl - .8))
    vl = 2 * math.pi * g['vine_lag']
    dr = g.get('droop', 0)
    for s in (1, -1):
        for pair, (chain, fwd) in enumerate(zip(ARMS[s], (g['vine_swing'], g['lower_swing']))):
            # the right and left vines swing against each other, the lower pair against the upper one
            ph = (x - mid) * g['vrate'] + (math.pi if pair else 0) + (math.pi if s < 0 else 0)
            for seg, bone in enumerate(chain):
                yaw, roll = vine(seg, s, ph, fwd, g['vine_flap'] * (.8 if pair else 1), vl)
                out[bone] = delta(yaw=yaw, roll=roll - s * (g['lower_up'] if pair else 0) * (1 if seg == 0 else .3) + s * dr * (1 if seg == 0 else .5) * (0 if pair else 1))
    ll = 2 * math.pi * g['leaf_lag']
    for s, bone in LEAVES.items():
        out[bone] = delta(pitch=-g['leaf_back'] * .6 + g['leaf'] * .4 * wave(2 * x, 2 * ll, .3, .7),
                          roll=s * g['leaf'] * (.55 + .45 * wave(x - mid, ll + (.6 if s < 0 else 0), .4, 1.0)))
    return off, tilt, out


def idle_terms(t, n, g=None):
    a = 2 * math.pi * t / n
    breath = math.sin(3 * a) + .25 * math.sin(6 * a - .8)
    off = np.array([2.2 * math.sin(a - .5), -1.9 * breath, 0.0])
    tilt = delta(pitch=1.2 + .5 * breath + .5 * math.sin(2 * a + .4), yaw=1.6 * math.sin(a + 1.0) + .4 * math.sin(3 * a),
                 roll=1.3 * math.sin(a - .6) + .5 * math.sin(2 * a + .3))
    out = {TRUNK: delta(pitch=.6 * math.sin(3 * a - .7), yaw=2.2 * math.sin(a - .4) + .4 * math.sin(3 * a), roll=-.9 * math.sin(a - .9))}
    out[HEAD] = delta(pitch=2.4 * math.sin(3 * a - .9) + 1.5 * math.sin(2 * a + .2) + .7 * math.sin(5 * a),
                      yaw=9 * math.sin(a - 1.6) + 3 * math.sin(3 * a + .4),
                      roll=2.2 * math.sin(2 * a - .3) + .8 * math.sin(a + 1.4))
    out[FACE] = delta(pitch=1.2 * math.sin(3 * a - 1.6), yaw=1.0 * math.sin(2 * a + .5))
    for s in (1, -1):
        for pair, chain in enumerate(ARMS[s]):
            ph = 2 * a + (1.7 if pair else 0) + (.9 if s < 0 else 0)
            for seg, bone in enumerate(chain):
                yaw, roll = vine(seg, s, ph, 4.0, 2.8, .45, .35)
                out[bone] = delta(yaw=yaw, roll=roll)
    for s, bone in LEAVES.items():
        out[bone] = delta(pitch=1.8 * math.sin(2 * a - 1.2), roll=-s * (2.6 * math.sin(3 * a - 1.3) + 1.2 * math.sin(6 * a - 2.0) + 1.6 * math.sin(a - .4 + (.5 if s < 0 else 0))))
    return off, tilt, out


class Pose:
    """One tick's frame from the terms; keeps the Euler solutions continuous from tick to tick."""

    def __init__(self, rig):
        self.rig = rig
        self.hist = {b: tuple(rig.base[b][3:6]) for b in range(1, NB)}

    def put(self, f, bone, matrix):
        angle = mmd.matrix_euler(matrix, self.hist[bone])      # always the solution nearest the base pose: no winding
        f[bone][3:6] = [float(a) for a in angle]

    def frame(self, off, tilt, parts, roots, t, v):
        rig = self.rig
        f = copy.deepcopy(rig.base)
        r1 = tilt @ rig.rest[PEL]
        t1 = tilt @ rig.origin[PEL] + off
        self.put(f, PEL, r1)
        f[PEL][6:9] = [float(a) for a in t1]
        cum, wrot = {PEL: tilt}, {PEL: r1}
        for b in UPPER:
            p = rig.parent[b]
            cum[b] = parts.get(b, np.eye(3)) @ cum[p]
            wrot[b] = cum[b] @ rig.rest[b]
            self.put(f, b, wrot[p].T @ wrot[b])
        if roots is not None:
            for k in FEET:
                shift, pitch, lift = roots.at(k, t)
                side = 1 if rig.centre[k][0] > 1 else (-1 if rig.centre[k][0] < -1 else 0)
                dr = Rx(pitch) @ Ry(side * pitch * .25)
                rel = rig.rel[k]
                lift += max(0.0, float((rel @ dr.T)[:, 1].max() - rel[:, 1].max()))      # a tilted foot's toe or heel stays above the floor
                target = rig.centre[k] + shift + np.array([0.0, -lift, 0.0])
                tw = target - dr @ (rig.centre[k] - rig.origin[k])
                self.put(f, k, r1.T @ (dr @ rig.rest[k]))
                f[k][6:9] = [float(a) for a in r1.T @ (tw - t1)]
        f[0] = [4096] * 3 + [0.0, 0.0, 0.0, 0.0, 0.0, -v * t]
        return f


BLINKS = {0: ((29, 2), (72, 1)), 2: ((17, 1),), 3: ((22, 4), (47, 3)), 4: ((11, 1),)}     # (first tick, ticks shut)
CLOSE = ((0, 18), (1, 12))                                  # the lid half way, then shut (texture column of the eye)


def face_events(n, slot, template):
    """The clip's blink as texture moves: the open face at tick 0, then for each blink half shut, shut, half shut, open."""
    moves = {x: dict(op='tex', src=(x, 72), size=(6, 24), dst=(6, 72)) for x in (24, 18, 12)}
    ev = [(0, 'tex', copy.deepcopy(moves[24]))]
    for tk, hold in BLINKS[slot]:
        seq = [18] + [12] * hold + [18, 24]
        ev += [(tk + i, 'tex', copy.deepcopy(moves[x])) for i, x in enumerate(seq)]
    return ev


def steps(slot, template):
    """One footstep sound per cycle, as the group A roots land."""
    g = GAITS[slot]
    P = g['n'] / g['cycles']
    return [(round(k * P), 'sound', copy.deepcopy(template)) for k in range(g['cycles'])]


def author(rig, slot):
    if slot == 0:
        n, g, v, roots = IDLE_TICKS, None, 0.0, Planted(rig)
    else:
        g = GAITS[slot]
        n, v = g['n'], g['v']
        roots = Roots(rig, g)
    pose = Pose(rig)
    frames = []
    for t in range(n):
        if slot == 0:
            off, tilt, parts = idle_terms(t, n)
        else:
            off, tilt, parts = walk_terms(slot, t, n, g)
        frames.append(pose.frame(off, tilt, parts, roots, t, v))
    last = copy.deepcopy(frames[0])
    last[0] = [4096] * 3 + [0.0, 0.0, 0.0, 0.0, 0.0, -v * n]
    frames.append(last)
    return [[[round(x) for x in bone] for bone in f] for f in frames], g


def bone_tol():
    tol = {b: TOL_FEET for b in FEET}
    tol[PEL] = TOL_FEET
    tol.update({b: TOL_BODY for b in (TRUNK, HEAD, FACE)})
    tol[None] = TOL_REST
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
        frames, g = author(rig, slot)
        n = len(frames) - 1
        ev = face_events(n, slot, None) + (steps(slot, template) if slot else [])
        index = result.anims.table[slot]
        mmd.close_loop(frames, loop)
        result.anims.anims[index] = mmd.encode_anim(frames, NB, loop, ev, tol=bone_tol(), repeats=False)
        checks.append(dict(slot=slot, ticks=n))
    output = result.build()
    effective = mmd.MMD.parse(output, NB)
    effective.type = SPECIES
    assert effective.tmd.build() == model.tmd.build()
    changed = changed_programs(model, effective)
    assert set(changed) <= {0, 1, 2, 3, 4, 18, 33}, changed
    return output, dict(source_sha256=hashlib.sha256(data).hexdigest(), output_sha256=hashlib.sha256(output).hexdigest(),
                        changed_slots=changed, checks=checks, storage=motionstorage.audit(output, NB))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = [tuple(b) for b in json.loads((ROOT / 'content/species/274-blossomon.json').read_text())['model']['skeleton']]
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
