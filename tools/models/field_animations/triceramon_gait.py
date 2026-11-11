"""Triceramon's field clips, authored from scratch: breathing idle, walk, tired walk and run (slots 0, 2, 3, 4).

The imported clips could not keep their feet on the floor (stance legs slid 88 % of the root speed in the walk, 31 to
41 % in the tired walk, 12 to 90 % in the run), the tired walk was faster than the walk, and the idle was a 34-tick
wobble. The body is a short, wide biped with a heavy head (the frill and the three horns are part of the head piece),
two small arms, a tail of three joints and legs of two links, so there is no native quadruped to borrow: the clips
are written over the model.

Every clip is made with the ground rules first:

- the root travels a whole number of units a tick (walk 16, tired walk 11, run 38) and each stance foot stays flat and
  planted at that pace (the ankle is solved onto a point that moves back in the body's frame by exactly the root's
  travel), with the sole on the floor; the swing arcs the foot over the floor and eases the pitch (toe down as it leaves,
  heel first as it lands); the legs are solved by two-bone IK with the knee pole of the rest pose;
- the body carries the weight: the pelvis sways over the stance foot, dips as the other foot lands and rises over the
  planted one, rolls and turns; the torso counter-turns, the head keeps level with a lag (spring followers evaluated
  at their periodic steady state, so a loop closes), the arms swing opposite their legs, the tail follows the hips'
  turn joint by joint, each a little later and wider than the one before, the jaw opens with the breaths of the tired walk;
- the idle keeps both feet planted, breathes, shifts its weight, and its head, tail and arms drift at their own phases.

Offline: `tools/models/edit.py get 257` on the commit before this change, then
`python3 -m tools.models.field_animations.triceramon_gait --source THAT.MMD --out AFTER.MMD` and `edit.py put 257 AFTER.MMD`.
"""
import cmath
import copy
import hashlib
import math

import animsheet
import mmd
import motionstorage
import numeric as np
from tools.models.field_animations.war_greymon import align, rotation, set_rotation

SPECIES = 257
NB = 21
SOURCE = '68c4d0b6071eed2ce63959310b262eece2f280593502a96a13724234dad8b066'   # edit.py get 257 before this change
PARENTS = [-1, 0, 1, 2, 3, 1, 5, 6, 1, 8, 9, 1, 11, 12, 13, 11, 15, 16, 11, 18, 19]
PI = math.pi
BODY, NECK, HEAD, JAW, PELVIS = 1, 2, 3, 4, 11
ARMS = ((5, 6, 7, 1), (8, 9, 10, -1))             # shoulder, elbow, hand, side (+1 = the model's right, x > 0)
TAIL = (12, 13, 14)
LEGS = ((15, 16, 17, 1), (18, 19, 20, -1))
LEG_CHANNELS = {(b, c) for b in (15, 16, 17, 18, 19, 20) for c in (3, 4, 5)}
POSE_BONES = tuple(range(1, NB))
IDLE_TICKS = 64
ARM_PHASE = PI/2 - 4.6 + PI
# stance: root units a tick, cycle ticks, duty (share of the cycle a foot is planted), swing lift
PROFILE = {
    2: dict(v=16, T=19, duty=.56, lift=30, drop=6, bob=8.5, bobsign=-1, sway=6.0, roll=2.6, yaw=4.5, lean=3, head=1.0, arm=15, tail=1.0,
            toe=6, heel=4, surge=3.0, note=16, nod=0, neck=-1, droop=0, armbase=0, counter=1),
    3: dict(v=11, T=22, duty=.6, lift=13, drop=30, bob=5.8, bobsign=-1, sway=8.5, roll=3.4, yaw=3.4, lean=11, head=.8, arm=7, tail=.75,
            toe=5, heel=3, surge=3.5, note=13, nod=15, neck=7, droop=-8, armbase=-6, counter=1),
    4: dict(v=38, T=15, duty=.30, lift=46, drop=26, bob=14.5, bobsign=1, sway=5.0, roll=3.0, yaw=6.5, lean=15, head=1.5, arm=20, tail=1.5,
            toe=10, heel=6, surge=6.0, note=13, nod=1, neck=3, droop=3, armbase=-30, counter=1),
}


def wave(t, period, terms, fn=None, zeta=.5):
    """Sum of amp*sin(k*theta + phase); with `fn` the terms pass a spring of natural frequency fn (cycles a loop):
    the response trails and overshoots near fn, as a limb hung on the body does. Periodic steady state: loops close."""
    theta = 2*PI*t/period
    total = 0.
    for k, amp, phase in terms:
        z = amp*cmath.exp(1j*(k*theta + phase))
        if fn:
            r = k/fn
            z /= (1 - r*r + 2j*zeta*r)
        total += z.imag
    return total


def smooth(u):
    return u*u*u*(10 - 15*u + 6*u*u)


class Body:
    def __init__(self, model, skeleton):
        self.model = model
        self.skeleton = skeleton
        self.verts = {b: np.array(model.tmd.obj_verts(o))[:, :3] for b, (o, _) in enumerate(skeleton) if o >= 0}

    def world(self, pose):
        p = copy.deepcopy(pose)
        p[0] = [4096]*3 + [0]*6
        return np.array(mmd.bone_matrices(self.model, p))

    def lowest(self, pose, bones=None):
        w = self.world(pose)
        return -max(float((self.verts[b] @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max())
                    for b in self.verts if bones is None or b in bones)

    def points(self, pose, bones):
        w = self.world(pose)
        return np.concatenate([self.verts[b] @ w[b, :3, :3].T + w[b, :3, 3] for b in bones])


def rot_y(deg):
    return rotation([0, deg, 0])


class Rig:
    """The rest pose (the import's first idle tick) and what the clips are built from."""

    def __init__(self, body, rest):
        self.body = body
        self.reach = []
        self.rest = copy.deepcopy(rest)
        self.rest[0] = [4096]*3 + [0]*6
        self.w0 = body.world(self.rest)
        self.rm = [np.array(mmd.rot_matrix(*self.rest[b][3:6])) for b in range(NB)]
        self.base = [list(self.rest[b][6:9]) for b in range(NB)]
        self.link = {b: float(np.linalg.norm(self.rest[b][6:9])) for b in range(NB)}
        # knee poles: the way the knee bends at rest (world direction from the hip-ankle line to the knee)
        self.pole = {}
        for hip, knee, foot, side in LEGS:
            h, k, a = (self.w0[i, :3, 3] for i in (hip, knee, foot))
            d = (a - h)/np.linalg.norm(a - h)
            p = (k - h) - d*float((k - h) @ d)
            self.pole[hip] = p/np.linalg.norm(p)
        self.flat = {foot: self.w0[foot, :3, :3].copy() for _, _, foot, _ in LEGS}
        self.ankle0 = {foot: self.w0[foot, :3, 3].copy() for _, _, foot, _ in LEGS}
        self.foot_verts = {foot: self.body.verts[foot] for _, _, foot, _ in LEGS}

    def foot_rotation(self, foot, pitch, yaw):
        """Flat foot turned by `yaw` degrees about the vertical and `pitch` (toe down positive) about its own width axis."""
        flat = self.flat[foot]
        return rot_y(yaw) @ flat @ rotation([pitch, 0, 0])

    def sole(self, foot, rf):
        """How far under the ankle the lowest vertex of the foot is (y down positive)."""
        return float((self.foot_verts[foot] @ rf.T)[:, 1].max())


def solve_legs(rig, f, goals, hist):
    """goals: {foot bone: (ankle world position, foot world rotation)}; f already has body, pelvis and tail."""
    w = rig.body.world(f)
    solved = {}
    for hip, knee, foot, side in LEGS:
        h = w[hip, :3, 3]
        la, lb = rig.link[knee], rig.link[foot]
        goal = np.array(goals[foot][0], float)
        delta = goal - h
        dist = float(np.linalg.norm(delta))
        rig.reach.append((dist/(la + lb), hip))
        if not abs(la - lb) + 1 < dist < (la + lb)*.985:
            raise ValueError(('reach', hip, round(dist, 1), round(la + lb, 1)))
        direct = delta/dist
        pole = rig.pole[hip]
        pp = pole - direct*float(pole @ direct)
        pp /= np.linalg.norm(pp)
        along = (la*la - lb*lb + dist*dist)/(2*dist)
        joint = h + direct*along + pp*math.sqrt(max(0, la*la - along*along))
        rw = rig.w0
        rh = align(rw[hip, :3, :3] @ np.array(rig.rest[knee][6:9]), joint - h) @ rw[hip, :3, :3]
        rk = align(rw[knee, :3, :3] @ np.array(rig.rest[foot][6:9]), goal - joint) @ rw[knee, :3, :3]
        solved[hip] = (rh, rk, np.array(goals[foot][1]), hip, knee, foot)
    for hip, (rh, rk, rf, _, knee, foot) in solved.items():
        set_rotation(f, hip, rig.body.world(f)[PELVIS, :3, :3].T @ rh, hist)
        set_rotation(f, knee, rig.body.world(f)[hip, :3, :3].T @ rk, hist)
        set_rotation(f, foot, rig.body.world(f)[knee, :3, :3].T @ rf, hist)


def set_world(rig, f, bone, world_rotation, hist):
    parent = PARENTS[bone]
    set_rotation(f, bone, rig.body.world(f)[parent, :3, :3].T @ world_rotation, hist)


def place_body(rig, f, x, y, z, delta_body, delta_pelvis, hist):
    """Body bone (carries chest, arms, neck) and pelvis bone (carries legs and tail): rotation deltas in degrees,
    applied in the parent frame over the rest rotation."""
    bx, by, bz = rig.base[BODY]
    f[BODY][6:9] = [round(bx + x), round(by + y), round(bz + z)]
    set_rotation(f, BODY, rotation(delta_body) @ rig.rm[BODY], hist)
    set_rotation(f, PELVIS, rotation(delta_pelvis) @ rig.rm[PELVIS], hist)


def local_delta(rig, f, bone, degrees, hist):
    set_rotation(f, bone, rotation(degrees) @ rig.rm[bone], hist)


def tail_pose(rig, f, yaws, pitches, hist):
    """World yaw/pitch of each tail joint from its rest orientation (a joint's own bend is the difference)."""
    for bone, yaw, pitch in zip(TAIL, yaws, pitches):
        target = rot_y(yaw) @ rotation([pitch, 0, 0]) @ rig.w0[bone, :3, :3]
        set_world(rig, f, bone, target, hist)


def head_pose(rig, f, nod, turn, tilt, hist):
    """Head world orientation: the rest one (level) turned by (nod, turn, tilt) degrees; the neck takes the rest."""
    target = rotation([nod, turn, tilt]) @ rig.w0[HEAD, :3, :3]
    set_world(rig, f, HEAD, target, hist)


def neck_pose(rig, f, nod, turn, tilt, hist):
    target = rotation([nod, turn, tilt]) @ rig.w0[NECK, :3, :3]
    set_world(rig, f, NECK, target, hist)


def arms_pose(rig, f, swing, lift, elbow, hist):
    """swing/lift/elbow: {side: degrees}; the shoulders carry in the parent frame."""
    for shoulder, forearm, hand, side in ARMS:
        local_delta(rig, f, shoulder, [swing[side], 0, -side*lift[side]], hist)
        local_delta(rig, f, forearm, [elbow[side], 0, 0], hist)


# --------------------------------------------------------------------------------------------------------- idle

def author_idle(rig, ticks=IDLE_TICKS):
    n = ticks
    frames = []
    hist, fhist = {}, {}
    # feet stay where the import stood them, flat on the floor
    goals0 = {}
    for hip, knee, foot, side in LEGS:
        rf = rig.foot_rotation(foot, 0, 0)
        a = rig.ankle0[foot].copy()
        a[1] = -rig.sole(foot, rf) - 1.2
        goals0[foot] = (a, rf)
    for t in range(n):
        f = copy.deepcopy(rig.rest)
        f[0] = [4096]*3 + [0]*6

        def b(*terms, **kw):
            return wave(t, n, list(terms), **kw)
        breath = b((1, 1, 0), (2, .18, .8))
        shift = b((1, 1, .4), (2, .25, 1.9))
        place_body(rig, f, 4.5*shift + .6*b((3, 1, .4)), -2.2*breath + 1.4*b((1, 1, 2.0)), 1.2*b((2, 1, 1.3)),
                   [2.2*b((1, 1, -.4)) , 1.6*b((1, 1, 1.9), (2, .3, .6)), 2.0*b((1, 1, .3), (2, .25, 2.0))],
                   [-.8*b((1, 1, .9)), -1.8*b((1, 1, 1.9), (2, .3, .6)), -1.2*b((1, 1, .3))], hist)
        neck_pose(rig, f, 2.2*b((1, 1, .2), (2, .2, 1.4), fn=2.0, zeta=.55) - 1.5*breath,
                  4.0*b((1, 1, 2.1), (2, .3, .4), fn=2.0, zeta=.55), 1.4*b((1, 1, .7), fn=2.0, zeta=.55), hist)
        head_pose(rig, f, 1.6*b((1, 1, .1), (3, .3, 2.2), fn=2.4, zeta=.4) - .8*breath,
                  8.5*b((1, 1, 2.0), (2, .45, .3), fn=2.4, zeta=.4), 2.4*b((1, 1, .9), (2, .5, 2.4), fn=2.4, zeta=.4), hist)
        local_delta(rig, f, JAW, [2.0 + 1.6*b((1, 1, .2 + PI/2)) , 0, 0], hist)
        arms_pose(rig, f,
                  {1: 3.2*b((1, 1, .4), (2, .3, 1.1), fn=2.0, zeta=.5), -1: 2.6*b((1, 1, 2.0), (2, .35, .2), fn=2.0, zeta=.5)},
                  {1: 1.6*b((1, 1, 1.4)), -1: 1.2*b((1, 1, 3.0))},
                  {1: 3.0*b((1, 1, -.2), fn=1.8, zeta=.5), -1: 2.5*b((1, 1, 1.4), fn=1.8, zeta=.5)}, hist)
        tail_pose(rig, f, [5.5*b((1, 1, 1.0), fn=1.5, zeta=.5), 9.0*b((1, 1, .4), (2, .2, 1.0), fn=1.5, zeta=.5),
                           12.5*b((1, 1, -.3), (2, .25, .6), fn=1.5, zeta=.5)],
                  [1.8*b((1, 1, -.2)) - 1.4*breath, 3.0*b((1, 1, -.6)), 4.0*b((1, 1, -1.0))], hist)
        solve_legs(rig, f, goals0, fhist)
        frames.append(f)
    frames.append(copy.deepcopy(frames[0]))
    return frames


# --------------------------------------------------------------------------------------------------------- gaits

def stance_goal(rig, foot, side, z_start, speed, stance_ticks, tau, yaw):
    """Ankle and orientation of a planted foot `tau` ticks into its stance: flat, sole on the floor, moving back in the
    body's frame by the root's travel."""
    rf = rig.foot_rotation(foot, 0, yaw)
    a = rig.ankle0[foot].copy()
    a[1] = -rig.sole(foot, rf) - 1.2
    a[2] = z_start + speed*tau
    return a, rf


def author_gait(rig, slot, ticks_override=None):
    p = PROFILE[slot]
    T, v, duty = p['T'], p['v'], p['duty']
    stance = duty*T
    L = v*stance                                   # how far a stance ankle slides back in the body's frame
    swing = (1 - duty)*T
    # stride centres under the hips (hips' world z at the rest pose); the right foot has the phase offset 0
    yawadj = {17: -12, 20: 12}                     # feet turn in a little from the import's wide toe-out
    side_x = {17: rig.ankle0[17][0], 20: rig.ankle0[20][0]}
    zc = {}
    for hip, knee, foot, side in LEGS:
        zc[foot] = rig.w0[hip, 2, 3] - 10
    frames = []
    hist, fhist = {}, {}
    n = T
    for t in range(n + 1):
        f = copy.deepcopy(rig.rest)
        f[0] = [4096]*3 + [0]*6
        f[0][8] = -v*t

        def b(*terms, **kw):
            return wave(t, n, list(terms), **kw)
        goals = {}
        info = {}
        for hip, knee, foot, side in LEGS:
            phase = ((t + (0 if side > 0 else n/2) + 2) / n) % 1.0
            tick_in_cycle = phase*n
            yaw = yawadj[foot]
            z_in = zc[foot] - L/2
            z_out = zc[foot] + L/2
            if tick_in_cycle < stance:
                a, rf = stance_goal(rig, foot, side, z_in, v, stance, tick_in_cycle, yaw)
                a[0] = side_x[foot]
                info[foot] = ('stance', tick_in_cycle/stance)
            else:
                u = (tick_in_cycle - stance)/swing
                a0, rf0 = stance_goal(rig, foot, side, z_in, v, stance, stance, yaw)
                a1, rf1 = stance_goal(rig, foot, side, z_in, v, stance, 0, yaw)
                a0[0] = a1[0] = side_x[foot]
                # hermite over the swing: the foot leaves moving back with the ground and lands moving back again
                tangent = v*swing*1.0
                h00, h10, h01, h11 = 2*u**3 - 3*u**2 + 1, u**3 - 2*u**2 + u, -2*u**3 + 3*u**2, u**3 - u**2
                z = h00*a0[2] + h10*tangent + h01*a1[2] + h11*tangent
                lift = p['lift']*math.sin(PI*u)**.65
                pitch = p['toe']*math.sin(PI*min(1, u/.5))**2 - p['heel']*math.sin(PI*min(1, max(0, (u - .5)/.5)))**2
                rf = rig.foot_rotation(foot, pitch, yaw)
                x = side_x[foot] + side*5*math.sin(PI*u)
                a = np.array([x, -rig.sole(foot, rf) - lift - 1.2, z])
                info[foot] = ('swing', u)
            goals[foot] = (a, rf)
        phi = t/n
        # body: over the right foot at phase ~duty/2, over the left half a cycle later
        mid = duty/2
        theta = 2*PI*(t + 2)/n                     # right foot's phase angle
        sway = p['sway']*math.cos(theta - 2*PI*mid)
        ph2 = 2*(theta - 2*PI*mid)
        rise = p['bobsign']*p['bob']*math.cos(ph2)        # body highest over each planted foot (y up is negative)
        surge = p['surge']*math.sin(2*(theta - 2*PI*mid))
        # turn: the pelvis follows the swinging foot's hip forward; the torso answers against it
        turn = p['yaw']*math.sin(theta - 2*PI*mid - PI/2)
        rollv = -p['roll']*math.cos(theta - 2*PI*mid)
        place_body(rig, f, 0, p['drop'] + rise, 0,
                   [p['lean'], -.55*turn, -.55*rollv], [-.3*turn, .9*turn, .9*rollv], hist)
        f[BODY][6] = round(rig.base[BODY][0] + sway)
        f[BODY][8] = round(rig.base[BODY][2] + surge)
        # torso and head
        counter = lambda lag: p['bobsign']*p['bob']*math.cos(ph2 - lag)
        neck_pose(rig, f, p['neck'] + p['counter']*.35*counter(.8) + p['head']*1.8*b((2, 1, -.9), (1, .35, 1.2), fn=2.8, zeta=.5),
                  p['head']*2.4*b((1, 1, -PI/2 - 0.8), fn=2.8, zeta=.5), p['head']*1.5*b((1, 1, .6), fn=2.8, zeta=.5), hist)
        head_pose(rig, f, p['nod'] + p['counter']*.3*counter(1.5) + p['head']*2.6*b((2, 1, -1.2), (1, .3, 1.4), fn=2.6, zeta=.4),
                  p['head']*3.6*b((1, 1, -PI/2 - 1.4), fn=2.6, zeta=.4), p['head']*2.2*b((1, 1, .5), (2, .4, 1.8), fn=2.6, zeta=.4), hist)
        local_delta(rig, f, JAW, [(4 + 5*b((2, 1, PI/2 + .3))) if slot == 3 else 2.0 + 1.2*b((2, 1, PI/2 + .3)), 0, 0], hist)
        a = p['arm']
        arms_pose(rig, f,
                  {1: p['armbase'] + a*wave(t, n, [(1, 1, ARM_PHASE)], fn=3.2, zeta=.55) + .5*a*b((2, .2, .6)),
                   -1: p['armbase'] - a*.85*wave(t, n, [(1, 1, ARM_PHASE)], fn=3.2, zeta=.55) + .5*a*b((2, .22, 1.2))},
                  {1: 8 + 2.4*b((1, 1, .9)), -1: 8 + 1.8*b((1, 1, 2.5))},
                  {1: 4 + .45*a*(.5 + .5*b((1, 1, -.4 + PI/2), fn=3.6, zeta=.5)), -1: 4 + .5*a*(.5 + .5*b((1, 1, PI/2 - .8), fn=3.6, zeta=.5))}, hist)
        k = p['tail']
        tail_pose(rig, f, [k*5.5*wave(t, n, [(1, 1, -PI/2 + .5)], fn=2.2, zeta=.5), k*9.5*wave(t, n, [(1, 1, -PI/2 + .2), (2, .25, 1.0)], fn=2.2, zeta=.5),
                           k*13.5*wave(t, n, [(1, 1, -PI/2 - .2), (2, .3, .3)], fn=2.2, zeta=.5)],
                  [k*2.2*wave(t, n, [(2, 1, .4)], fn=3.0, zeta=.5) + p['droop'] + p['counter']*.25*counter(1.4), k*3.4*wave(t, n, [(2, 1, -.1)], fn=3.0, zeta=.5) + p['droop']*1.3 + p['counter']*.4*counter(2.0),
                   k*4.4*wave(t, n, [(2, 1, -.6)], fn=3.0, zeta=.5) + p['droop']*1.5 + p['counter']*.55*counter(2.6)], hist)
        solve_legs(rig, f, goals, fhist)
        frames.append(f)
    frames[-1][1:] = copy.deepcopy(frames[0][1:])
    return frames


# --------------------------------------------------------------------------------------------------------- packing

def events_for(old_events, ticks, sound_ticks=(), note=None, blinks=()):
    """The eye texture moves of the old clip (the first one opens them; `blinks` repeats the old blink at these
    ticks) and a footstep note on each of `sound_ticks`."""
    tex = [e for e in old_events if e[1] == 'tex']
    out = [(tex[0][0], 'tex', dict(tex[0][2]))]
    blink = tex[1:]
    for start in blinks:
        for k, kind, c in blink:
            kk = start + k - blink[0][0]
            out.append((kk, 'tex', dict(c, frame=kk + 1)))
    for k in sound_ticks:
        out.append((k, 'sound', dict(op='sound', frame=k + 1, bank=1, note=note)))
    return sorted(out, key=lambda e: e[0])


TOLERANCE = {15: 1, 16: 1, 17: 1, 18: 1, 19: 1, 20: 1, None: 2}


def pack(frames, events, tol=None):
    samples = [[[int(round(x)) for x in bone] for bone in pose] for pose in frames]
    return mmd.encode_anim(samples, NB, loop_sample=0, events=events, tol=tol or TOLERANCE, repeats=False)


def sound_ticks(slot):
    p = PROFILE[slot]
    n = p['T']
    # a foot lands at its cycle phase 0: tick -2 and n/2 - 2 of the loop
    return sorted({(-2) % n, int(round(n/2 - 2)) % n})


def make_model(data, skeleton):
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = len(skeleton)
    model = mmd.MMD.parse(data, NB)
    model.type = SPECIES
    body = Body(model, skeleton)
    rest = animsheet.slot_frames(model, NB, 0)[0][0]
    return model, body, Rig(body, rest)


def build(data, skeleton, slots=(0, 2, 3, 4)):
    if hashlib.sha256(data).hexdigest() != SOURCE or [b[1] for b in skeleton] != PARENTS:
        raise ValueError("Triceramon's clips are written over the model the importer and the reviewed delta produced")
    model, body, rig = make_model(data, skeleton)
    old_events = {s: animsheet.slot_frames(model, NB, s)[2] for s in (0, 2, 3, 4)}
    new = {}
    for slot in slots:
        if slot == 0:
            frames = author_idle(rig)
            events = events_for(old_events[0], IDLE_TICKS, blinks=(14, 44))
        else:
            frames = author_gait(rig, slot)
            events = events_for(old_events[slot], PROFILE[slot]['T'], sound_ticks(slot), PROFILE[slot]['note'])
        new[slot] = (frames, pack(frames, events))
    for slot, (frames, animation) in new.items():
        model.anims.table[slot] = len(model.anims.anims)
        model.anims.anims.append(animation)
    used = sorted({i for i in model.anims.table if i is not None})
    renumber = {old: i for i, old in enumerate(used)}
    model.anims.anims = [model.anims.anims[i] for i in used]
    model.anims.table = [None if i is None else renumber[i] for i in model.anims.table]
    result = model.build()
    return result, dict(species=SPECIES, source_sha256=SOURCE, changed_slots=sorted(slots), storage=motionstorage.require(result, NB))


def main():
    import argparse
    import json
    from pathlib import Path
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    rig = json.loads(Path('content/species/257-triceramon.json').read_text())['model']['skeleton']
    data, report = build(Path(args.source).read_bytes(), rig)
    Path(args.out).write_bytes(data)
    print(args.out, len(data), 'B', report['storage'])


if __name__ == '__main__':
    main()
