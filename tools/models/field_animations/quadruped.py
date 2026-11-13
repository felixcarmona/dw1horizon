"""A four-legged walk and run written from the paws up, for an imported quadruped's own rig.

The species modules (metal_garurumon.py, armadillomon.py) give the rig (pelvis, chest, head, the three bones of each
leg, tail and loose parts), the paws' soles and where they stand, and one row per field clip: cycle ticks, speed, the
touchdown phase and duty factor of each leg, paw lift, body bob and pitch. This module writes the clips the way
nefertimon.py writes Nefertimon's:

- Each leg has a stance and a swing per cycle. In stance the sole stands on the floor and stays put in the world
  while the body passes over it (the speed and the stance length make the stride); in its last part the heel peels
  and the paw rolls onto its toes. In swing the leg lifts, the paw curls back, reaches forward and flattens again
  just before it lands.
- Every target is a point in the world: a paw's place on the floor, a wrist (hock) over it. Two-bone solves on the
  model's own link lengths reach it, in the bend plane of the reference leg's standing pose (elbows back, knees
  forward). The left legs' reference is the right legs' standing pose mirrored in the world (the meshes and offsets
  of the two sides mirror exactly), so an imported idle that stands with one leg back does not twist the other.
- The pelvis and chest bob and pitch with the footfalls, the head steadies against them, the tail and loose parts
  follow a few ticks late.
- A leg with a short bone between two of its links (a knee cap, a hock spur) names it in `links`; it keeps its
  standing angle. Paws that stand turned out give `paw_flat` per leg ('RF': angles) instead of per front/hind.
  A leg that would swing its elbow (knee) into the leg behind (ahead of) it gives `swing_pole` (front/hind: a bend
  direction): a swinging leg bends towards it, eased in from the standing bend and back out before it lands.
  A lower bone with a long part along it (a forearm blade) gives `aim` (front/hind: that direction in the bone's
  space): standing and swinging, the bone rolls about itself to keep it pointing ahead. A profile with `pole_world` gives its pole directions in the world (x towards the leg's side) instead of the parent bone's
  space, for a leg hung from a bone that stands turned in its rest pose. A profile's `extra` (a function of the rig, the gait row, the cycle phase and the pose) moves the parts the module has no row for (Mammothmon's trunk, ears and jaw). A profile's `toes` ({paw: toe bone}, a toe with no turn of its own in the rest pose) counts the toe's points as the paw's when the paw is put on the floor. A profile's `floor_skip` (bones) leaves out of the floor check the parts the source's own idle hangs under the floor (Mammothmon's trunk tip and tail). A profile's `floor` and `stance_slip` widen the
under-the-floor and sliding-sole bounds for a rig whose leg plates cannot stay both flat and planted (Tortomon). A gait's `arc` (default 0.8) shapes the lift of a swinging paw: 1 rises as a plain half sine, below 1 it leaves the floor faster. A gait's `clear_ease` (fraction of the swing) brings the clearance under the paw in gradually, so a paw peeled at the end of stance does not jump up at the lift-off. A gait's `world_ease` (true, or a share from 0 to 1 of it) eases a swinging paw's fore-aft travel in the world instead of in the body's frame, so it leaves and lands at rest over the floor (its slip is then small even while it is within a few units of the floor). A gait's `fold_soft` (units) replaces the hard minimum distance `fold` of a swinging wrist from its hip by a smooth maximum of that width. A gait's `leg_reach` (per leg: units) moves one leg's stance window fore or aft of the others'. A gait's `wide`
  (front/hind: units) carries a swinging paw out from its track and back in by the landing. A profile's `body` (a function
  of (rig, cfg, phase, pose, hist), default `body` below) writes the trunk and everything above the legs instead, for a rig
  with no chest or head bone and parts of its own (Woodmon's swinging log arms). A profile's `flat_shin` (front/hind: 0 to 1)
  carries the hock that share of the way to straight above the ankle and stretches the links to match, for a leg whose
  shin plate would dig into the floor as it tilts (Grizzlymon's hind legs). A gait with speed 0 is an idle: the feet stay where
  they are and only the body and the parts above it move.

Each clip is rewritten where it is stored, so its battle aliases play it too. Footsteps keep the species' own
sound (bank and note) and land on touchdowns; the clip keeps the eye state (texture events) its source opens with.
The build refuses another source, a mesh point under the floor at a tick or a 60 fps third, a sole that slides in
stance, an open loop, a speed outside the native range, another changed program or the storage budget.
"""
import copy
import hashlib
import math

import animsheet
import mmd
import motionstorage
from motiondiscidentity import changed_programs

DEG = 4096 / 360
SPEED_RANGE = {2: (15, 31), 3: (10, 20), 4: (35, 52)}    # the native partners' field speeds (units per tick)
FLOOR = 3            # a mesh point may dip this far under the floor at a tick or a 60 fps third (rounding)
STANCE_SLIP = 0.35   # a standing sole may slide this fraction of the body's travel (natives: 0.1-0.8)
MIRROR = {'LF': 'RF', 'LH': 'RH'}


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


def rot(deg):
    return mmd.rot_matrix(*[d * DEG for d in deg])


def frame(u, n):
    """Columns: u, n (made orthogonal to u), u x n."""
    u = unit(u)
    n = unit(sub(n, scale(u, dot(n, u))))
    w = cross(u, n)
    return [[u[i], n[i], w[i]] for i in range(3)]


def smooth(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def minimum_jerk(v):
    v = max(0.0, min(1.0, v))
    return v * v * v * (10 - 15 * v + 6 * v * v)


def wave(phase, delay=0.0, rate=1):
    return math.cos(2 * math.pi * rate * (phase - delay))


def set_rot(pose, b, m, hist):
    angle = mmd.matrix_euler(m, hist.get(b))
    hist[b] = angle
    pose[b][3:6] = [round(x) for x in angle]


MIRROR_X = [[-1, 0, 0], [0, 1, 0], [0, 0, 1]]


# ------------------------------------------------------------------ the rig
class Rig:
    def __init__(self, model, skeleton, profile):
        self.m = model
        self.sk = skeleton
        self.p = profile
        self.n = len(skeleton)
        self.idle = animsheet.slot_frames(model, self.n, 0)[0]
        self.rest = [list(v) for v in self.idle[0]]
        # `scale` (profile): the uniform size the rest pose gives the body bone and everything under it (an imported
        # model sized by its idle). Rotations are read with it divided out, link offsets and soles multiplied in.
        self.S = profile.get('scale', 1.0)
        self.verts = {b: [[x * self.S for x in v[:3]] for v in model.tmd.obj_verts(o)] for b, (o, _) in enumerate(skeleton) if o >= 0}
        # A profile's `claws` ({foot bone: claws bone}) puts the claws' points (a bone that stays at its rest turn under the foot)
        # into the foot's own, so the floor stands under the claws and not under the foot's sole plate (Maildramon).
        for paw, toe in profile.get('claws', {}).items():
            offset = [x * self.S for x in self.rest[toe][6:9]]
            self.verts[paw] = self.verts[paw] + [add(v, offset) for v in self.verts.pop(toe)]
        for paw, toe in profile.get('toes', {}).items():
            # a toe bone with no turn of its own rides the paw: its points count as the paw's for the sole and the floor
            assert not any(self.rest[toe][3:6]), (paw, toe)
            off = [x * self.S for x in self.rest[toe][6:9]]
            self.verts[paw] = self.verts[paw] + [[v[i] + off[i] for i in range(3)] for v in self.verts[toe]]
        still = [list(v) for v in self.rest]
        still[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
        W = self.world(still)
        self.still = W
        # A paw's flat standing rotation in the world: identity for rigs whose paws are bound sole-down, otherwise
        # the profile's 'paw_flat' angles (degrees) per front/hind. Rolls are pitched on top of it.
        flat = profile.get('paw_flat', {})
        self.flat = {front: rot(flat[front]) if front in flat else rot([0, 0, 0]) for front in (True, False)}
        # 'paw_flat' may also name a leg ('RF': angles), for paws that stand turned out, each side its own way
        self.flat_leg = {name: rot(angles) for name, angles in flat.items() if isinstance(name, str)}
        # 'paw_rest' (profile): paws stand as the rest pose has them, each rolling about its own lateral axis. It names, per
        # leg, the direction of its toes in the paw bone's space; the paw's world rotation at rest is its flat rotation.
        self.toe_turn = {}
        for name, toe in profile.get('paw_rest', {}).items():
            flat_rest = self.R(W, profile['legs'][name][2])
            self.flat_leg[name] = flat_rest
            ahead = mv(flat_rest, toe)
            self.toe_turn[name] = turn_to([0, 0, -1], [ahead[0], 0.0, ahead[2]])
        # 'mirror_paws' (profile): the left paws stand as the right ones mirrored in the world, for a rig whose rest pose
        # (an idle caught mid-stride) tilts the left paws differently from the right ones
        if profile.get('mirror_paws'):
            for left, right in MIRROR.items():
                if right in self.flat_leg:
                    self.flat_leg[left] = mul(mul(MIRROR_X, self.flat_leg[right]), MIRROR_X)
                    if right in self.toe_turn:
                        self.toe_turn[left] = mul(mul(MIRROR_X, self.toe_turn[right]), MIRROR_X)
        # Reference bend planes: each right leg's standing pose; the left legs take it mirrored in the world.
        self.ref = {}
        for name, (up, lo, paw, side, front) in profile['legs'].items():
            src = profile['legs'][MIRROR.get(name, name)]
            worlds = [self.R(W, b) for b in src[:3]]
            if name in MIRROR:
                worlds = [mul(mul(MIRROR_X, w), MIRROR_X) for w in worlds]
            parent = self.R(W, skeleton[up][1])
            self.ref[name] = [mul(tr(parent), worlds[0]), mul(tr(worlds[0]), worlds[1]), mul(tr(worlds[1]), worlds[2])]

    def paw(self, front, pitch, name=None):
        """A paw's world rotation, pitched by the given degrees from flat."""
        flat = self.flat_leg.get(name, self.flat[front])
        if name in self.toe_turn:
            turn = self.toe_turn[name]
            return mul(mul(turn, mul(rot([pitch, 0, 0]), tr(turn))), flat)
        return mul(rot([pitch, 0, 0]), flat)

    def R(self, W, b):
        """A bone's world rotation with the profile's uniform scale divided out."""
        k = 1.0 if b == 0 else 1.0 / self.S
        return [[x * k for x in r[:3]] for r in W[b][:3]]

    def sole(self, front):
        return [x * self.S for x in self.p['sole'][front]]

    def world(self, pose):
        p = [list(v) for v in pose]
        p[0] = [4096, 4096, 4096] + p[0][3:6] + [0, 0, 0]
        return mmd.bone_matrices(self.m, p)

    def lowest(self, b, rot_, origin):
        """Lowest point (largest y) of bone b's mesh at a world rotation and origin."""
        return max(origin[1] + dot(rot_[1], v) for v in self.verts[b])

    def solve(self, pose, name, wrist, hist, pole=None, aim=None):
        """Two-bone solve of a leg for its wrist (hock) position in the reference leg's bend plane (or towards the
        given pole); returns the lower bone's world rotation and how far the target was out of reach. aim (a direction in
        the lower bone's space) rolls the lower bone about its own axis to turn that direction towards the front."""
        up, lo, paw, side, front = self.p['legs'][name]
        W = self.world(pose)
        parent = self.R(W, self.sk[up][1])
        shoulder = [W[up][i][3] for i in range(3)]
        a, via_lo = self.link(pose, lo)
        b, via_paw = self.link(pose, paw)
        ref = self.ref[name]
        ru0 = mul(parent, ref[0])
        rl0 = mul(ru0, ref[1])
        e0 = add(shoulder, mv(ru0, a))
        w0 = add(e0, mv(rl0, b))
        la, lb = norm(a), norm(b)
        d = sub(wrist, shoulder)
        dist = norm(d)
        reach = max(abs(la - lb) + 2, min(la + lb - 2, dist))
        d = scale(unit(d), reach)
        pole = pole or self.p['pole'][front]
        pole = [pole[0] * side] + list(pole[1:])
        if not self.p.get('pole_world'):
            pole = mv(parent, pole)
        pole0 = pole
        pole = unit(sub(pole, scale(unit(d), dot(pole, unit(d)))))
        along = (la * la - lb * lb + reach * reach) / (2 * reach)
        h = math.sqrt(max(0.0, la * la - along * along))
        elbow = add(shoulder, add(scale(unit(d), along), scale(pole, h)))
        wr = add(shoulder, d)
        flat = self.p.get('flat_shin', {}).get(front, 0.0)
        if flat:
            # a lower bone with a broad plate under it (a hock block) would dig its front or rear edge into the floor as soon
            # as it tilts: `flat_shin` carries the elbow (hock) that share of the way to straight above the wrist, and the two
            # links' offsets stretch or shrink with it (the upper mesh overlaps the lower one by far more than that)
            elbow = add(scale(elbow, 1 - flat), scale(add(wr, [0.0, -lb, 0.0]), flat))
        n0 = cross(sub(e0, shoulder), sub(w0, e0))
        n1 = cross(sub(elbow, shoulder), sub(wr, elbow))
        if self.p.get('rest_plane'):
            # A leg that stands almost straight has no usable bend plane of its own (the cross products above are noise
            # and can roll the bone half a turn): take the pole as the plane in both the reference and the target.
            d0 = unit(sub(w0, shoulder))
            p0 = unit(sub(pole0, scale(d0, dot(pole0, d0))))
            n0, n1 = cross(p0, d0), cross(pole, unit(d))
        if norm(n0) < 1e-6 or norm(n1) < 1e-6:     # a straight limb: swing it without twist
            ru = mul(turn_to(sub(e0, shoulder), sub(elbow, shoulder)), ru0)
            rl = mul(turn_to(mv(mul(ru, ref[1]), b), sub(wr, elbow)), mul(ru, ref[1]))
        else:                                       # the bend plane carries the limb's roll
            ru = mul(mul(frame(sub(elbow, shoulder), n1), tr(frame(sub(e0, shoulder), n0))), ru0)
            rl = mul(mul(frame(sub(wr, elbow), n1), tr(frame(sub(w0, e0), n0))), rl0)
        if aim:
            axis = unit(sub(wr, elbow))
            v, ahead = mv(rl, aim), [0.0, 0.0, -1.0]
            v, ahead = sub(v, scale(axis, dot(axis, v))), sub(ahead, scale(axis, dot(axis, ahead)))
            if norm(v) > 1e-6 and norm(ahead) > 1e-6:
                rl = mul(spin(axis, math.atan2(dot(cross(v, ahead), axis), dot(v, ahead))), rl)
        if flat:
            for child, k in ((lo, norm(sub(elbow, shoulder)) / la), (paw, norm(sub(wr, elbow)) / lb)):
                pose[child][6:9] = [x * k for x in pose[child][6:9]]
        set_rot(pose, up, mul(tr(parent), ru), hist)
        set_rot(pose, lo, mul(tr(mul(ru, via_lo)), rl), hist)
        return mul(rl, via_paw), dist - reach

    def link(self, pose, child):
        """The offset of a leg joint from the joint before it in that one's space, and the rotation of a bone between
        them. A profile's `links` names a short bone (a knee cap, a hock spur) that sits between two leg bones and
        holds its standing rotation: {child: bone between}. Without one the child hangs straight off the bone before."""
        offset = [pose[child][6] * self.S, pose[child][7] * self.S, pose[child][8] * self.S]
        via = self.p.get('links', {}).get(child)
        if via is None:
            return offset, [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        turn = mmd.rot_matrix(*self.rest[via][3:6])
        return add(scale(self.rest[via][6:9], self.S), mv(turn, offset)), turn


def spin(u, angle):
    """Rotation by angle (radians) about the unit axis u."""
    c, s = math.cos(angle), math.sin(angle)
    k = [[0, -u[2], u[1]], [u[2], 0, -u[0]], [-u[1], u[0], 0]]
    return [[c * (i == j) + s * k[i][j] + (1 - c) * u[i] * u[j] for j in range(3)] for i in range(3)]


def turn_to(a, b):
    """Shortest rotation taking direction a to direction b."""
    a, b = unit(a), unit(b)
    v = cross(a, b)
    c = dot(a, b)
    k = [[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]]
    kk = mul(k, k)
    return [[(1 if i == j else 0) + k[i][j] + kk[i][j] / (1 + c) for j in range(3)] for i in range(3)]


# ------------------------------------------------------------------ walk and run
def leg_phase(cfg, name, phase):
    u = (phase - cfg['touchdown'][name]) % 1.0
    duty = cfg['duty'][name]
    return (True, u / duty) if u < duty else (False, (u - duty) / (1 - duty))


def standing(rig, name, track, z, world):
    """The wrist (hock) of a paw whose sole pivot stands at z on the floor, at a world rotation."""
    paw, front = rig.p['legs'][name][2], rig.p['legs'][name][4]
    wrist = sub([track, 0.0, z], mv(world, rig.sole(front)))
    wrist[1] = -rig.p['clear'] - rig.lowest(paw, world, [0, 0, 0])
    return wrist


def swing_pitch(cfg, front, s):
    """A swinging paw's world pitch at swing fraction s: rolled on from the lift-off, curled under the leg on the way,
    flat again to land."""
    key = 'front' if front else 'hind'
    peel = cfg['peel'][key]
    curl = cfg['curl'][key] * math.sin(math.pi * min(1.0, s / 0.8)) if s < 0.8 else 0.0
    return peel * (1 - smooth(s / 0.4)) + curl * (1 - smooth((s - 0.55) / 0.3)) - cfg.get('heel', 3) * smooth((s - 0.7) / 0.25)


def body_terms(cfg, phase):
    """The body's bob, spine flex, pitch, roll and yaw (degrees, bob in units) at a cycle phase. Optional loosening
    keys of a gait row (all default to none): `bob2` a second harmonic that sharpens the dips (a landing compression),
    `side` a cycle-rate share added to bob/pitch/roll so the two sides of the stride differ, `rise` an extra pitch."""
    side = cfg.get('side', 0.0)
    if cfg['kind'] == 'gallop':   # high in the gathered flight, low between the hind and fore stances
        bob = cfg['bob'] * (math.cos(2 * math.pi * (phase - cfg.get('high', 0.9))) + 0.3 * math.cos(4 * math.pi * (phase - 0.2)))
        flex = cfg['flex'] * wave(phase, 0.95)
        pitch = cfg['pitch'] * math.sin(2 * math.pi * (phase - 0.35))
        roll = cfg['roll'] * math.sin(2 * math.pi * (phase - 0.2))
        yaw = cfg['yaw'] * math.sin(2 * math.pi * (phase - 0.5))
    else:                          # two dips a cycle, the weight passing from side to side
        high = cfg.get('high', 0.12)
        bob = cfg['bob'] * (math.cos(4 * math.pi * (phase - high)) + cfg.get('bob2', 0.0) * math.cos(8 * math.pi * (phase - high))
                            + side * math.cos(2 * math.pi * (phase - high - 0.1)))
        flex = cfg['flex'] * math.cos(4 * math.pi * (phase - 0.3))
        pitch = cfg['pitch'] * (math.cos(4 * math.pi * (phase - cfg.get('pitch_at', 0.2)))
                                + 0.5 * side * math.sin(2 * math.pi * (phase - 0.15)))
        roll = cfg['roll'] * (math.sin(2 * math.pi * (phase - 0.05)) + 0.35 * side * math.sin(6 * math.pi * (phase - 0.2)))
        yaw = cfg['yaw'] * math.sin(2 * math.pi * (phase - 0.3))
    return bob, flex, pitch, roll, yaw


def body(rig, cfg, phase, pose, hist):
    """Pelvis height and pitch, spine flex, steady head, late tail and loose parts. A gait row may also give `lag`
    ((neck, head) cycle fractions the neck and head follow the body late by, so they swing on after it), `breath`
    (degrees of chest pitch once a cycle), `tail_lag` (cycle fraction between tail joints), `tail_whip` (each joint's
    extra share of swing) and `tail_wag` (a quicker second swing of the tail)."""
    p, rest = rig.p, rig.rest
    pelvis, chest = p['pelvis'], p['chest']
    rate = 1 if cfg['kind'] == 'gallop' else 2
    bob, flex, pitch, roll, yaw = body_terms(cfg, phase)
    pose[pelvis][7] = rest[pelvis][7] - cfg['height'] - bob
    set_rot(pose, pelvis, mul(mmd.rot_matrix(*rest[pelvis][3:6]), rot([cfg['tilt'] + pitch - flex, yaw, roll])), hist)
    breath = cfg.get('breath', 0.0) * math.sin(2 * math.pi * (phase - 0.1))
    set_rot(pose, chest, mul(mmd.rot_matrix(*rest[chest][3:6]), rot([2 * flex - cfg['chest_up'] + breath, -yaw * 1.4, -roll * 0.6])), hist)
    steady = cfg['head']   # the head keeps most of its gaze while the body pitches
    lag_neck, lag_head = cfg.get('lag', (0.0, 0.0))
    _, nflex, npitch, nroll, nyaw = body_terms(cfg, phase - lag_neck)
    _, hflex, hpitch, hroll, hyaw = body_terms(cfg, phase - lag_head)
    if p.get('neck') is not None:
        pose[p['neck']][3] = rest[p['neck']][3] - round((steady * 0.5 * (npitch + nflex) - cfg['neck']) * DEG)
        if lag_neck:
            pose[p['neck']][4] = rest[p['neck']][4] + round(nyaw * 0.5 * DEG)
    pose[p['head']][3] = rest[p['head']][3] - round((steady * 0.5 * (hpitch + hflex) + cfg['nod'] * wave(phase, 0.1, 2)) * DEG)
    pose[p['head']][4] = rest[p['head']][4] + round(hyaw * 0.8 * DEG)
    if lag_head:
        pose[p['head']][5] = rest[p['head']][5] - round(hroll * 0.7 * DEG)
    step = cfg.get('tail_lag', 0.08)
    for k, b in enumerate(p['tail']):
        lag = step * (k + 1)
        whip = 1 + cfg.get('tail_whip', 0.0) * k
        carried = cfg.get('tail_up', 0) if k == 0 else 0    # a tail held up off the ground (degrees at its root)
        wag = cfg.get('tail_wag', 0.0) * whip * wave(phase, 0.9 + 2 * lag, rate * 2)
        pose[b][3] = rest[b][3] + round((carried + whip * cfg['tail'] * (0.5 + 0.2 * k) * wave(phase, 0.9 + lag, rate) + wag) * DEG)
        pose[b][4] = rest[b][4] + round(whip * cfg['tail'] * 0.6 * math.sin(2 * math.pi * (phase - 0.3 - lag)) * DEG)
    for b, sign in p.get('loose', ()):
        pose[b][3] = rest[b][3] + round(cfg['loose'] * wave(phase, 0.15, rate) * DEG)
        pose[b][5] = rest[b][5] + round(sign * 0.5 * cfg['loose'] * wave(phase, 0.25, 1) * DEG)


def gait(rig, cfg):
    p = rig.p
    ticks, speed = cfg['ticks'], cfg['speed']
    rest = rig.rest
    W = rig.still
    centres, tracks = {}, {}
    for name, (up, lo, paw, side, front) in p['legs'].items():
        key = 'front' if front else 'hind'
        ref = p['legs'][MIRROR.get(name, name)]
        centres[name] = W[up][2][3] + p['reach'][key] + cfg['reach'][key] + cfg.get('leg_reach', {}).get(name, 0)
        tracks[name] = side * (abs(W[ref[2]][0][3]) + cfg.get('track', {}).get(key, 0))
    worst = dict(stretch=0.0)

    def stride(name):
        return speed * ticks * cfg['duty'][name] * (1 - cfg['slip'])

    def stand(pose, name, s, hist):
        up, lo, paw, side, front = p['legs'][name]
        key = 'front' if front else 'hind'
        z = centres[name] - stride(name) / 2 + stride(name) * s
        # `settle` (degrees): the paw lands heel first (`heel` degrees heel-down at touchdown, default 3, carried through the end of the swing), slaps onto its toes a little past flat and settles
        landing = -cfg.get('heel', 3) * (1 - smooth(s / 0.12)) + cfg.get('settle', 0.0) * math.sin(math.pi * min(1.0, s / 0.3)) if cfg.get('settle') else 0.0
        world = rig.paw(front, cfg['peel'][key] * smooth((s - 0.55) / 0.45) + landing, name)
        wrist = standing(rig, name, tracks[name], z, world)
        lower, out = rig.solve(pose, name, wrist, hist, None, p.get('aim', {}).get(front))
        set_rot(pose, paw, mul(tr(lower), world), hist)
        return out

    def body_at(phase, drop, hist):
        pose = [list(v) for v in rest]
        pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, -round(speed * phase * ticks)]
        (p.get('body') or body)(rig, cfg, phase, pose, hist)
        pose[p['pelvis']][7] += drop
        return pose

    def folded(pose, name, wrist):
        """A swinging wrist (hock) kept a little away from its shoulder (hip), so the knee does not flip."""
        Wp = rig.world(pose)
        root = [Wp[p['legs'][name][0]][i][3] for i in range(3)]
        d = sub(wrist, root)
        least = p['fold'][p['legs'][name][4]]
        soft = cfg.get('fold_soft')
        if soft:       # a smooth maximum: the wrist's distance eases into `least` instead of being capped at it
            r = norm(d)
            return add(root, scale(unit(d), 0.5 * (r + least + math.sqrt((r - least) ** 2 + soft ** 2))))
        return wrist if norm(d) >= least else add(root, scale(unit(d), least))

    def swung_pole(front, s):
        """A swinging leg's bend direction: eased from the standing pole to the profile's 'swing_pole' and back."""
        turn = p.get('swing_pole', {}).get(front)
        if turn is None:
            return None
        k = math.sin(math.pi * s) ** 2
        return [a + (b - a) * k for a, b in zip(p['pole'][front], turn)]

    def place(t, drop, hist):
        phase = t / ticks
        pose = body_at(phase, drop, hist)
        short = 0.0
        for name, (up, lo, paw, side, front) in p['legs'].items():
            stance, s = leg_phase(cfg, name, phase)
            if stance:
                short = max(short, stand(pose, name, s, hist))
                continue
            key = 'front' if front else 'hind'
            lift_off = standing(rig, name, tracks[name], centres[name] + stride(name) / 2, rig.paw(front, cfg['peel'][key], name))
            landing = standing(rig, name, tracks[name], centres[name] - stride(name) / 2, rig.paw(front, 0, name))
            k = minimum_jerk(s) if cfg['snap'] else smooth(s)
            if cfg.get('jerk'):      # a share of the quicker ease, so the paw leaves late and arrives braking
                k = (1 - cfg['jerk']) * smooth(s) + cfg['jerk'] * minimum_jerk(s)
            mul_ = cfg.get('leg_lift', {}).get(name, 1.0)    # the two sides never step quite alike
            flight = [lift_off[i] + (landing[i] - lift_off[i]) * (k if i == 2 else s) for i in range(3)]
            if cfg.get('world_ease'):     # the ease is made in the world: the paw leaves and lands at rest over the floor
                swing_ticks = ticks * (1 - cfg['duty'][name])
                z_world = lift_off[2] + (landing[2] - speed * swing_ticks - lift_off[2]) * minimum_jerk(s)
                share = 1.0 if cfg['world_ease'] is True else cfg['world_ease']     # a share < 1 keeps the paw nearer the body
                flight[2] = share * (z_world + speed * swing_ticks * s) + (1 - share) * flight[2]
            flight[2] -= mul_ * cfg['out'][key] * 6.75 * s * s * (1 - s)    # reaches past the landing, then settles onto it
            flight[1] -= mul_ * cfg['lift'][key] * math.sin(math.pi * min(1.0, s ** cfg.get('arc', 0.8))) ** cfg.get('plateau', 1.0)
            flight[0] += side * cfg.get('wide', {}).get(key, 0) * math.sin(math.pi * s)    # swings wide of the body
            world = rig.paw(front, swing_pitch(cfg, front, s), name)
            dip = rig.lowest(paw, world, [0, 0, 0])
            if cfg.get('clear_ease'):      # the clearance under the paw comes in over the first part of the swing
                dip *= smooth(s / cfg['clear_ease'])
            wrist = folded(pose, name, [flight[0], min(flight[1], -p['clear'] - dip), flight[2]])
            lower, _ = rig.solve(pose, name, wrist, hist, swung_pole(front, s), p.get('aim', {}).get(front))
            set_rot(pose, paw, mul(tr(lower), world), hist)
        if p.get('extra'):       # a species' own parts (trunk, ears, jaw) follow the body: extra(rig, cfg, phase, pose)
            p['extra'](rig, cfg, phase, pose)
        return pose, short

    # a standing leg that cannot reach brings the body down to it, along a smooth cyclic dip
    need = [0.0] * ticks

    def dip(phase):
        x = phase * ticks
        return max(n - 0.6 * min(abs(x - j), ticks - abs(x - j)) ** 2 for j, n in enumerate(need))
    for _ in range(8):
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
    return frames, worst


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
            for b in rig.verts:
                if b in rig.p.get('floor_skip', ()):     # parts the idle itself lets hang under the floor (a trunk tip, a tail)
                    continue
                worst = max(worst, rig.lowest(b, rig.R(W, b), [W[b][i][3] for i in range(3)]) + height)
    return worst


def _stance_slip(rig, cfg, frames):
    """Per paw: how far its sole pivot moves over the ground while the leg stands, as a fraction of the body's travel."""
    ticks = cfg['ticks']
    out = {}
    for name, (up, lo, paw, side, front) in rig.p['legs'].items():
        moved, travel = 0.0, 0.0
        for t in range(ticks):
            if not (leg_phase(cfg, name, t / ticks)[0] and leg_phase(cfg, name, (t + 1) / ticks)[0]):
                continue
            here = []
            for pose in (frames[t], frames[t + 1]):
                W = rig.world(pose)
                point = add([W[paw][i][3] for i in range(3)], mv(rig.R(W, paw), rig.sole(front)))
                here.append(point[2] + pose[0][8])
            moved += abs(here[1] - here[0])
            travel += abs(frames[t + 1][0][8] - frames[t][0][8])
        out[name] = round(moved / travel, 3) if travel else 0.0
    return out


def build(data, skeleton, profile):
    """The profile's field clips written into the model -> (bytes, report)."""
    sid = profile['species']
    if hashlib.sha256(data).hexdigest() != profile['source']:
        raise ValueError(f'{profile["name"]}\'s gait requires the reviewed source')
    if [b[1] for b in skeleton] != profile['parents']:
        raise ValueError(f'{profile["name"]} rig differs')
    n = len(skeleton)
    mmd.exe().skeleton[sid] = skeleton
    mmd.exe().bone_count[sid] = n
    old = mmd.MMD.parse(data, n)
    old.type = sid
    new = copy.deepcopy(old)
    rig = Rig(old, skeleton, profile)
    checks, changed = [], set()
    for slot, cfg in sorted(profile['gaits'].items()):
        frames, worst = gait(rig, cfg)
        ticks = cfg['ticks']
        cycles = cfg.get('cycles', 1)       # a clip may play its cycle several times over (a blink that spans cycles)
        if cfg.get('compose'):      # the species composes its own loop of `cycles` cycles that differ from each other
            frames = cfg['compose'](rig, cfg, frames)
            assert len(frames) == ticks * cycles + 1, (slot, len(frames))
        elif cycles > 1:
            one, step = frames[:ticks], round(cfg['speed'] * ticks)
            frames = []
            for c in range(cycles):
                for pose in one:
                    pose = [list(b) for b in pose]
                    pose[0][8] -= step * c
                    frames.append(pose)
            closing = [list(b) for b in one[0]]
            closing[0][8] = -step * cycles
            frames.append(closing)
            if profile.get('vary'):         # a species may vary its loose parts from one cycle to the next
                frames = profile['vary'](rig, cfg, frames)
        total = ticks * cycles
        source_events = animsheet.slot_frames(old, n, slot)[2]
        sound = next((dict(e) for _, kind, e in source_events if kind == 'sound'), dict(op='sound', bank=1, note=13))
        events = [(t, kind, e) for t, kind, e in source_events if kind == 'tex' and t == 0]
        if profile.get('events'):           # the species' own texture moves (its face) replace the source's
            events = list(profile['events'](slot, total))
        for c in range(cycles):
            for name in cfg['steps']:
                tick = round(cfg['touchdown'][name] * ticks) % ticks + c * ticks
                events.append((tick, 'sound', dict(sound, frame=tick + 1)))
        events.sort(key=lambda e: e[0])
        frames = [[[round(x) for x in bone] for bone in pose] for pose in frames]
        animation = mmd.encode_anim(frames, n, loop_sample=0, events=events, tol=profile.get('tol', 1))
        index = old.anims.table[slot]
        new.anims.anims[index] = animation          # in place: the slot's aliases play it too
        changed |= {s for s, i in enumerate(old.anims.table) if i == index}
        played, played_events = _played(animation, n, slot, total)
        for tick in range(total, total * 3 + 1, total):
            assert all(abs(a - b) <= 2 for bone, other in zip(played[0][1:], played[tick][1:]) for a, b in zip(bone, other)), \
                (slot, tick, 'loop drift')
        loop = played[:total + 1]
        speed = abs(loop[-1][0][8] - loop[0][0][8]) / total
        floor = _floor(rig, loop)
        assert floor <= profile.get('floor', FLOOR), (slot, 'under the floor', floor)
        if cfg['speed']:
            low, high = profile.get('speed_range', SPEED_RANGE)[slot]
            assert low <= speed <= high and abs(speed - cfg['speed']) <= 0.5, (slot, speed)
        else:                               # an idle: the feet stay where they are
            assert speed == 0, (slot, speed)
        slips = _stance_slip(rig, cfg, loop)
        assert max(slips.values()) <= profile.get('stance_slip', STANCE_SLIP), (slot, slips)
        sounds = sorted({k for k, kind, _ in played_events if kind == 'sound' and k < total})
        assert len(sounds) == len(cfg['steps']) * cycles, (slot, sounds)
        checks.append(dict(slot=slot, gait=cfg['name'], ticks=ticks, cycles=cycles, units_per_tick=round(speed, 2),
                           lowest_point=round(floor, 1), touchdown=cfg['touchdown'], duty=cfg['duty'], stance_slip=slips,
                           body_drop=round(worst['drop'], 1), unreached=round(worst['stretch'], 2), sound_ticks=sounds,
                           stream_bytes=len(animation.build()),
                           aliases=sorted(s for s, i in enumerate(old.anims.table) if i == index)))
    result = new.build()
    actual = mmd.MMD.parse(result, n)
    assert old.tmd.build() == actual.tmd.build()
    assert changed_programs(old, actual) == sorted(changed), (changed_programs(old, actual), sorted(changed))
    storage = motionstorage.require(result, n)
    return result, dict(species=sid, source_sha256=profile['source'], output_sha256=hashlib.sha256(result).hexdigest(),
                        changed_slots=sorted(changed), checks=checks, storage=storage, mesh_exact=True,
                        other_programs_exact=True)
