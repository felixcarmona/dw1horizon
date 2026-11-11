"""Diaboromon (237): a crouched four-limb idle, walk, condition walk and run.

The SkullGreymon transfer plus the flat-hand contact pass left the field clips jerky: the hand pass switched the
claws between their native curl and a flat pad within one tick (up to 138 degrees a tick), the transfer squeezed
the donor's motion into 16-28 tick clocks (upper arms and hips turning 45-70 degrees a tick in the run), the root
advanced unevenly and swayed sideways, and the planted feet slid.

This pass keeps the mesh, the crouched stance (the first idle pose: hands and feet on the ground) and every other
program, and writes the four field clips again. Every hand and foot is solved each tick: a planted one keeps its
place and orientation in the world, a swinging one follows one smooth curve, and the lowest vertex of a planted one
sits on the floor. Hind legs: the hock (the long link above the foot) keeps its stance slant, tilting a little with
the foot and folding back in the swing; thigh and shin are a two-link solve from the hip to the hock. Arms: the shoulder stays, the upper arm
and forearm are a two-link solve with the elbow out and back as in the stance; the claw keeps its stance orientation
and only tilts its tips up in the swing. The pelvis bobs and sways over the loaded side, the chest counter-turns and
the head looks about on its own. Loops: idle 72 ticks; walk 48 (three strides, 20 a tick); condition walk 60 (three
heavier, lower strides, 13 a tick); run 36 (three gallop strides, 38 a tick).
"""
import copy
import hashlib
import math

import numpy as np

import animsheet
import mmd
import motioncyclelayer
import motionstorage
from motiondiscidentity import changed_programs

SPECIES = 237
NB = 24
SOURCE = 'e85bdf1f63ee58a6c20d7394a1c43152e7cce2a34931cfa3a7f83b2403697e13'   # the model before this pass
PARENTS = [-1, 14, 1, 2, 3, 4, 1, 6, 7, 8, 1, 10, 11, 12, 15, 0, 15, 16, 17, 18, 15, 20, 21, 22]
SLOTS = (0, 2, 3, 4)

# (hip/shoulder, upper, lower, end, front, side)
LEGS = ((16, 17, 18, 19, 1), (20, 21, 22, 23, -1))
ARMS = ((6, 7, 8, 9, 1), (10, 11, 12, 13, -1))

# Gait per slot: loop ticks, strides per loop, root speed, duty (fore, hind), phase offset per limb end,
# swing lift (hand, foot), body height offset (down +), forward lean of the torso (degrees), bob, sway, hock fold in
# the swing (degrees), claw tip tilt in the swing, claws raked back as a hand leaves the ground (degrees).
# The limbs are not in lockstep: the offsets are not quarter or half cycles, and the left limbs (`uneven`: duty and
# lift factors) stay down a little longer and lift a little less than the right ones.
GAIT = {
    2: dict(ticks=48, cycles=3, speed=20, duty=(0.5, 0.5), lift=(34, 26), drop=0, lean=0, bob=4, sway=7, fold=20,
            tip=14, rake=0, offsets={19: 0.0, 9: 0.29, 23: 0.53, 13: 0.81},
            uneven={19: (1.0, 1.0), 9: (1.0, 1.0), 23: (1.05, 0.85), 13: (0.96, 0.88)}),
    3: dict(ticks=60, cycles=3, speed=13, duty=(0.6, 0.6), lift=(20, 14), drop=32, lean=13, bob=6, sway=9, fold=12,
            tip=7, rake=0, offsets={19: 0.0, 9: 0.34, 23: 0.46, 13: 0.83},
            uneven={19: (1.0, 1.0), 9: (1.0, 1.0), 23: (1.07, 0.7), 13: (0.97, 0.8)}),
    4: dict(ticks=36, cycles=3, speed=38, duty=(0.36, 0.36), lift=(46, 36), drop=4, lean=10, bob=12, sway=4, fold=28,
            tip=22, rake=22, offsets={19: 0.0, 23: 0.13, 9: 0.47, 13: 0.63},
            uneven={19: (1.0, 1.0), 9: (1.0, 1.0), 23: (1.04, 0.88), 13: (0.95, 0.9)}),
}
IDLE_TICKS = 72
MAX_STEP = 320   # 28 degrees: the largest change of one Euler angle between two ticks
SLANT = 15      # degrees the hock slants back with the foot behind (forward with it ahead)
HIND_BACK = 12  # the hind feet step a little further back than they stand, clear of the claws
PALM_ROLL = 150  # degrees the planted hands turn about their claws (see Rig)
PALM_PITCH = 35  # degrees the planted claws point down so their tips reach the floor
TANGENT = 0.3  # share of the ground speed a foot keeps as it lifts and lands


def _parse(data, sk):
    mmd.exe().skeleton[SPECIES] = sk
    mmd.exe().bone_count[SPECIES] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = SPECIES
    return model


def _axis(axis, degrees):
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    i, j = [(1, 2), (2, 0), (0, 1)][axis]
    m = np.eye(3)
    m[i, i] = m[j, j] = c
    m[i, j], m[j, i] = -s, s
    return m


def _step(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def _align(a, b):
    a = np.asarray(a, float) / np.linalg.norm(a)
    b = np.asarray(b, float) / np.linalg.norm(b)
    v = np.cross(a, b)
    c = float(a @ b)
    k = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + k + k @ k / (1 + c)


def _frame(axis, normal):
    axis = axis / np.linalg.norm(axis)
    normal = normal - axis * (normal @ axis)
    normal /= np.linalg.norm(normal)
    return np.column_stack([axis, normal, np.cross(axis, normal)])


class Rig:
    def __init__(self, model, sk):
        self.m = model
        self.sk = sk
        self.base = copy.deepcopy(animsheet.slot_frames(model, NB, 0)[0][0])
        self.base[0] = [4096] * 3 + [0] * 6
        # The stance's arms are not mirror images: the right forearm is twisted so far that its claw sits next to
        # Euler gimbal lock (82 degrees), where a small turn of the claw spins two angles by whole turns (the 60 fps
        # interpolation would show the spin). The right arm takes the left arm's pose, mirrored.
        for right, left in zip((6, 7, 8, 9), (10, 11, 12, 13)):
            rx, ry, rz = self.base[left][3:6]
            self.base[right][3:6] = [rx, -ry, -rz]
        self.rw = self.world(self.base)
        self.hist = {}
        # The claws curl towards the hand's local -X side (mirrored on the left), where the thumb claw also sits:
        # that is the palm. The hand pass laid the +X side (the back of the hand) on the floor, so the planted
        # claws curled up, palms to the sky. Each hand turns about its claws until the palm faces the floor (a
        # little inwards, as the SkullGreymon transfer held it) and tips down until the claw points touch it.
        for hand, side in ((9, 1), (13, -1)):
            self.set_world(self.base, hand, _axis(0, PALM_PITCH) @ self.rw[hand, :3, :3] @ _axis(1, side * PALM_ROLL))
        self.rw = self.world(self.base)
        self.vs = {b: np.array(model.tmd.obj_verts(o), float)[:, :3] for b, (o, _) in enumerate(sk) if o >= 0}
        self.hist = {}

    def world(self, f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(self.m, g), float)

    def set_world(self, f, bone, rot, w=None):
        w = self.world(f) if w is None else w
        local = w[self.sk[bone][1], :3, :3].T @ rot
        angles = mmd.matrix_euler(local.tolist(), self.hist.get(bone))
        self.hist[bone] = angles
        f[bone][3:6] = [round(a) for a in angles]

    def turn(self, f, bone, delta):
        """Rotate `bone` by the world rotation `delta` about its own joint."""
        w = self.world(f)
        self.set_world(f, bone, delta @ w[bone, :3, :3], w)

    def bottom(self, bone, rot):
        """How far below its joint the lowest vertex of `bone` lies with the world rotation `rot` (y down)."""
        return float((self.vs[bone] @ rot.T)[:, 1].max())

    def chain(self, f, upper, lower, end, goal, pole, end_rot):
        """Two-link solve: `upper` and `lower` place the joint of `end` at `goal`, the middle joint towards `pole`."""
        w = self.world(f)
        root = w[upper, :3, 3]
        a = float(np.linalg.norm(f[lower][6:9]))
        b = float(np.linalg.norm(f[end][6:9]))
        delta = goal - root
        dist = float(np.linalg.norm(delta))
        assert abs(a - b) + 8 < dist < a + b - 8, ('reach', upper, dist, a, b)
        d = delta / dist
        along = (a * a - b * b + dist * dist) / (2 * dist)
        p = pole - d * (pole @ d)
        p /= np.linalg.norm(p)
        middle = root + d * along + p * math.sqrt(a * a - along * along)
        ref = [self.rw[v, :3, 3] for v in (upper, lower, end)]
        new = [root, middle, goal]
        n_old = np.cross(ref[1] - ref[0], ref[2] - ref[1])
        n_new = np.cross(new[1] - new[0], new[2] - new[1])
        for bone, i in ((upper, 0), (lower, 1)):
            rot = _frame(new[i + 1] - new[i], n_new) @ _frame(ref[i + 1] - ref[i], n_old).T @ self.rw[bone, :3, :3]
            self.set_world(f, bone, rot)
        self.set_world(f, end, end_rot)
        return float(np.linalg.norm(self.world(f)[end, :3, 3] - goal)), middle

    def pole(self, upper, lower, end, body):
        """The stance's bend direction of the middle joint, carried by the body rotation `body`."""
        r = [self.rw[v, :3, 3] for v in (upper, lower, end)]
        d = (r[2] - r[0]) / np.linalg.norm(r[2] - r[0])
        p = (r[1] - r[0]) - d * ((r[1] - r[0]) @ d)
        return body @ (p / np.linalg.norm(p))


def _swing_z(q, z0, z1, v):
    """Quintic Hermite from z0 to z1 with end tangents v (dz/dq) and no end acceleration."""
    h00, h10 = 1 - 10 * q ** 3 + 15 * q ** 4 - 6 * q ** 5, q - 6 * q ** 3 + 8 * q ** 4 - 3 * q ** 5
    h01, h11 = 10 * q ** 3 - 15 * q ** 4 + 6 * q ** 5, -4 * q ** 3 + 7 * q ** 4 - 3 * q ** 5
    return h00 * z0 + h10 * v + h01 * z1 + h11 * v


def pose(rig, slot, t):
    """The pose of `slot` at tick t (root at the origin)."""
    tau = 2 * math.pi
    base, rw = rig.base, rig.rw
    f = copy.deepcopy(base)
    if slot == 0:
        ticks = IDLE_TICKS
        u = t / ticks
        breath = math.sin(tau * 2 * u)
        shift = math.sin(tau * u)
        bob, sway, lean = 1.5 * breath, 5 * shift, 0
        pelvis = _axis(1, 2.5 * math.sin(tau * u + 0.8)) @ _axis(2, -1.2 * shift)
        chest = _axis(1, -2 * math.sin(tau * u + 0.8)) @ _axis(0, 1.5 * breath) @ _axis(2, 1.0 * shift)
        look = 22 * math.sin(tau * u + 0.4) * (0.6 + 0.4 * math.sin(tau * 2 * u + 1.2))
        nod = 4 * math.sin(tau * 2 * u + 0.3) - 2 * breath
        jaw = 6 * _step((u - 0.30) / 0.06) * (1 - _step((u - 0.42) / 0.08))
    else:
        g = GAIT[slot]
        ticks, cycles, speed = g['ticks'], g['cycles'], g['speed']
        u = t / ticks
        c = cycles * u
        loaded = 0
        for end, off in g['offsets'].items():
            p = (c - off) % 1
            duty = g['duty'][0 if end in (9, 13) else 1] * g['uneven'][end][0]
            side = 1 if end in (9, 19) else -1
            loaded += side * (_step(p / 0.1) - _step((p - duty) / 0.1))
        if slot == 4:
            bound = math.cos(tau * (c - 0.3))
            bob = -g['bob'] * bound
            pitch = 5 * math.sin(tau * (c - 0.3))
        else:
            bob = -g['bob'] * math.cos(tau * 2 * c) / 2 + g['bob'] / 2
            pitch = 1.5 * math.sin(tau * 2 * c)
        bob += g['drop']
        sway = g['sway'] * loaded / 2
        lean = g['lean']
        # a second harmonic makes the two halves of the stride differ: the body favours its right side a little
        yaw = (4 * math.sin(tau * c) if slot != 4 else 1.5 * math.sin(tau * c)) + 1.2 * math.sin(tau * 2 * c + 0.6)
        pelvis = _axis(1, yaw) @ _axis(2, -1.5 * loaded) @ _axis(0, 0.4 * pitch)
        chest = _axis(1, -1.6 * yaw) @ _axis(0, lean + pitch) @ _axis(2, 1.2 * loaded)
        look = (6 if slot == 2 else 3 if slot == 3 else 2) * math.sin(tau * c + 1.0)
        nod = {2: 0, 3: 16, 4: -6}[slot] - 0.6 * pitch
        jaw = {2: 0, 3: 4 + 2 * math.sin(tau * 2 * c), 4: 3}[slot]
    # --- body: pelvis (carries legs and chest), chest, torso, neck, jaw
    f[15][6] = base[15][6] + round(sway)
    f[15][7] = base[15][7] + round(bob)
    rig.set_world(f, 15, pelvis @ rw[15, :3, :3])
    w = rig.world(f)
    rig.set_world(f, 14, chest @ rw[14, :3, :3], w)
    rig.set_world(f, 1, chest @ rw[1, :3, :3])
    # the neck holds the head's own direction (half of the body's lean) and looks about
    w = rig.world(f)
    follow = _axis(0, 0.5 * lean)
    rig.set_world(f, 2, _axis(1, look) @ _axis(0, nod) @ follow @ rw[2, :3, :3], w)
    if jaw:
        rig.set_world(f, 5, rig.world(f)[5, :3, :3] @ _axis(0, -jaw))
    body = chest
    # --- limbs
    errors = []
    for hip, upper, lower, end, side in LEGS:
        fx, fz = rw[end, 0, 3], rw[end, 2, 3] + (HIND_BACK if slot else 0)
        up, pitch_e, dz, fold, half = 0.0, 0.0, 0.0, 0.0, 0.0
        if slot == 0:
            pass
        else:
            g = GAIT[slot]
            duty = g['duty'][1] * g['uneven'][end][0]
            period = g['ticks'] / g['cycles']
            half = g['speed'] * period * duty / 2
            p = (g['cycles'] * t / g['ticks'] - g['offsets'][end]) % 1
            if p < duty:
                dz = -half + g['speed'] * period * p
            else:
                q = (p - duty) / (1 - duty)
                dz = _swing_z(q, half, -half, TANGENT * g['speed'] * period * (1 - duty))
                up = g['lift'][1] * g['uneven'][end][1] * math.sin(math.pi * q ** 0.85) ** 1.4
                pitch_e = -10 * math.sin(math.pi * q) ** 2
                fold = g['fold'] * math.sin(math.pi * q ** 0.8)
                fx += side * 6 * math.sin(math.pi * q) ** 2
        rot = _axis(0, pitch_e) @ rw[end, :3, :3]
        goal = np.array([fx, 0.0, fz + dz])
        goal[1] = -rig.bottom(end, rot) - up   # the lowest vertex on the floor
        # The hock (the long upright link above the foot) keeps its stance slant and only folds back in the swing;
        # thigh and shin carry it: a two-link solve from the hip to the hock joint, the knee forward and out.
        meta = _axis(0, fold + SLANT * dz / max(1.0, half)) @ rw[lower, :3, :3]
        hock = goal - meta @ np.array(f[end][6:9], float)
        err, _ = rig.chain(f, hip, upper, lower, hock, rig.pole(hip, upper, lower, pelvis), meta)
        rig.set_world(f, end, rot)
        errors.append(max(err, float(np.linalg.norm(rig.world(f)[end, :3, 3] - goal))))
    for shoulder, upper, lower, end, side in ARMS:
        hx, hz = rw[end, 0, 3], rw[end, 2, 3]
        up, tip, dz = 0.0, 0.0, 0.0
        if slot == 0:
            u = t / IDLE_TICKS
            if side > 0:   # the right claw lifts, its tips rise and it settles back in the same place
                lift = _step((u - 0.55) / 0.08) * (1 - _step((u - 0.72) / 0.08))
                up, tip = 26 * lift, 16 * lift + 4 * lift * math.sin(tau * 3 * u)
            else:          # the left claw only flexes its tips
                tip = 5 * _step((u - 0.12) / 0.06) * (1 - _step((u - 0.24) / 0.06))
        else:
            g = GAIT[slot]
            duty = g['duty'][0] * g['uneven'][end][0]
            period = g['ticks'] / g['cycles']
            half = g['speed'] * period * duty / 2
            p = (g['cycles'] * t / g['ticks'] - g['offsets'][end]) % 1
            if p < duty:
                dz = -half + g['speed'] * period * p
            else:
                q = (p - duty) / (1 - duty)
                dz = _swing_z(q, half, -half, TANGENT * g['speed'] * period * (1 - duty))
                up = g['lift'][0] * g['uneven'][end][1] * math.sin(math.pi * q ** 0.8) ** 1.3
                tip = g['tip'] * math.sin(math.pi * q ** 0.9) - g['rake'] * math.sin(math.pi * q) ** 2 * (1 - q)
                hx += side * 8 * math.sin(math.pi * q) ** 2
        rot = _axis(0, tip) @ rw[end, :3, :3]
        goal = np.array([hx, 0.0, hz + dz])
        goal[1] = -rig.bottom(end, rot) - up   # the lowest vertex on the floor
        err, _ = rig.chain(f, upper, lower, end, goal, rig.pole(upper, lower, end, body), rot)
        errors.append(err)
    return f, max(errors)


def clip(rig, slot):
    ticks = IDLE_TICKS if slot == 0 else GAIT[slot]['ticks']
    speed = 0 if slot == 0 else GAIT[slot]['speed']
    out, worst = [], 0.0
    rig.hist = {}
    for t in range(ticks + 1):
        f, err = pose(rig, slot, t % ticks)
        worst = max(worst, err)
        f[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, -speed * t]
        out.append([[round(x) for x in v] for v in f])
    # the last sample is the first one again: it must already be the same rotation (no branch change)
    for b in range(1, NB):
        for ch in (3, 4, 5):
            assert abs(out[ticks][b][ch] - out[0][b][ch]) % 4096 in (0, 1, 4095), (slot, b, ch, out[ticks][b], out[0][b])
            # every angle moves little per tick (the 60 fps passes interpolate each angle on its own)
            for i in range(ticks):
                assert abs(out[i + 1][b][ch] - out[i][b][ch]) <= MAX_STEP, (slot, i, b, ch, out[i][b], out[i + 1][b])
    mmd.close_loop(out, 0)
    return out, worst


def author(data, sk):
    old = _parse(data, sk)
    rig = Rig(old, sk)
    result = copy.deepcopy(old)
    streams, checks = {}, []
    for slot in SLOTS:
        out, worst = clip(rig, slot)
        ticks = len(out) - 1
        _, _, events = animsheet.slot_frames(old, NB, slot)
        sounds = [e for _, kind, e in events if kind == 'sound']
        cues = []
        if slot:
            g = GAIT[slot]
            # one footfall per hind foot landing (one for the pair when they land together in the gallop)
            ticks_of = set()
            for end in (19, 23):
                tick = round((g['offsets'][end] / g['cycles']) * ticks) % ticks
                for k in range(g['cycles']):
                    s = (tick + round(k * ticks / g['cycles'])) % ticks
                    if not any(min(abs(s - o), ticks - abs(s - o)) < 3 for o in ticks_of):
                        ticks_of.add(s)
            cues = [(s, 'sound', dict(sounds[0], frame=s + 1)) for s in sorted(ticks_of)]
        streams[slot] = len(result.anims.anims)
        result.anims.anims.append(mmd.encode_anim(out, NB, 0, cues, tol=1, repeats=False))
        checks.append(dict(slot=slot, ticks=ticks, root_per_tick=0 if slot == 0 else GAIT[slot]['speed'],
                           cues=[c[0] for c in cues], contact_error=round(worst, 3)))
    for slot in SLOTS:
        result.anims.table[slot] = streams[slot]
    for anim in result.anims.anims:
        anim.tail = b''
    result.anims.anims, result.anims.table = motioncyclelayer.share_identical_streams(result.anims.anims,
                                                                                    result.anims.table)
    output = result.build()
    effective = _parse(output, sk)
    assert effective.tmd.build() == old.tmd.build()
    assert changed_programs(old, effective) == list(SLOTS), changed_programs(old, effective)
    return output, dict(checks=checks, storage=motionstorage.require(output, NB))


def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE or [b[1] for b in sk] != PARENTS:
        raise ValueError('Diaboromon needs the 24-bone model it had before this change')
    output, extra = author(data, sk)
    return output, dict(species=SPECIES, source_sha256=SOURCE, output_sha256=hashlib.sha256(output).hexdigest(),
                        changed_slots=list(SLOTS), field=extra)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--source', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    skeleton = [(i - 1, p) for i, p in enumerate(PARENTS)]
    data, proof = build(open(args.source, 'rb').read(), skeleton)
    open(args.out, 'wb').write(data)
    print(len(data), 'bytes', proof['field'])
