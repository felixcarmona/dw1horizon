"""Starmon's legs, run lean and hanging ribbons (field slots 0, 2, 3, 4), written over a bone map so SuperStarmon can reuse it.

What the import's clips did wrong, and what this changes (the speeds, the stride length and the planting are kept):

- Legs: the boots are wider than the gap between the ankles (about 80 units against boots 136 wide), so on every step
  one boot went through the other leg. Each ankle is now put `spread` units further out sideways, plus `swing` units
  more while that foot is in the air (the foot swings round the stance leg instead of through it). The pelvis only
  drops as far as the legs need to reach the same ground points; the knee keeps the plane of the old clip.
- Run: the pelvis pitched 71 to 79 degrees (the walk uses 33 to 38), so the star plate and the head looked at the
  floor. The pitch is brought to `pitch` units (4096 = 360 degrees) with half of the old oscillation, the hips keep their
  places.
- Ribbons: the four ribbon bones flailed over 60 to 130 degrees and pointed up and sideways. Each ribbon now hangs
  down and back (a droop direction in world space for each of its two segments) and moves only through a damped
  pendulum driven by the pelvis: a spring of natural frequency `fn` cycles a loop, so the motion lags and is small
  (`amp` degrees at most). The second segment is a hinge about its own x axis, so the ribbon never twists at the joint.

All loops stay exactly periodic: the ribbon response is solved harmonic by harmonic over the loop, not stepped.

Offline: `tools/models/edit.py get 243` on the commit before this change, then
`python3 -m tools.models.field_animations.star_gait_refine --source THAT.MMD --out AFTER.MMD` and `edit.py put 243 AFTER.MMD`.
SuperStarmon (244) has the same 20-bone parent list plus fringe bones 20 to 26; a `RIG` with its own `legs`, `ribbons`
and `profile` values drives the same functions (the droop vectors and `spread` scale with its size).
"""
import cmath
import copy
import hashlib
import math

import animsheet
import mmd
import motionstorage
import numeric as np
from types import SimpleNamespace

from tools.models.field_animations.channels import coalesce, replace_channels
from tools.models.field_animations.war_greymon import align, set_rotation

SPECIES = 243
SOURCE = '2e0ac528493802c4c01fe03576770848bdc2274daf3e10d036309abb76fe3dcb'   # edit.py get 243 before this change
PARENTS = [-1, 0, 1, 2, 3, 1, 5, 6, 1, 8, 9, 10, 1, 12, 13, 14, 1, 16, 1, 18]
PI = math.pi
RIG = dict(
    pelvis=1,
    legs=((8, 9, 10, 1), (12, 13, 14, -1)),          # (hip, knee, ankle, side: +1 is the +x side)
    ribbons=((16, 17, 1.), (18, 19, -1.)),            # (root, tip, side)
    # droop directions in world space (x side, y down, z back), segment 1 then 2, for the ribbon on side +1
    droop=((.5, .35, .8), (.45, .6, .65)),
    arms=((2, 1.), (5, -1.)),                       # (shoulder, side): swung outward about the body's fore-aft axis
)
# per slot: spread and swing of the ankles, pelvis pitch target (None keeps it) and how much of the old pitch motion
# stays, ribbon pendulum (amp degrees, natural frequency in cycles a loop, damping ratio, how much of the base motion
# drives it)
PROFILE = {
    0: dict(hip_drop=65, hip_out=0, arm_out=0, arm_max=44, arm_swing=(1., 1.), spread=0, swing=0, pitch=None, keep=1., amp=14., fn=1.0, zeta=.4, delay=.1, base=3.),
    2: dict(hip_drop=65, hip_out=0, arm_out=6, arm_max=64, arm_swing=(.3, .8), spread=15, swing=25, pitch=200, keep=.5, amp=17., fn=1.6, zeta=.4, delay=.1, base=3.),
    3: dict(hip_drop=65, hip_out=0, arm_out=6, arm_max=64, arm_swing=(.3, .8), spread=15, swing=25, pitch=300, keep=.5, amp=20., fn=1.4, zeta=.4, delay=.1, base=3.),
    4: dict(hip_drop=65, hip_out=0, arm_out=6, arm_max=64, arm_swing=(.3, .8), spread=25, swing=40, pitch=270, keep=.5, amp=30., fn=2.0, zeta=.4, delay=.1, base=3.,
             droop=((.7, .3, .65), (.8, .5, .4)))      # streams further out and back at speed: it clears the swinging thighs,
}
LEG_CHANNELS = {(b, c) for b in (8, 9, 10, 12, 13, 14) for c in (3, 4, 5)} | {(b, c) for b in (8, 12) for c in (6, 7)}
ARM_CHANNELS = {(b, c) for b in (2, 3, 5, 6) for c in (3, 4, 5)}
RIBBON_CHANNELS = {(b, c) for b in (16, 17, 18, 19) for c in (3, 4, 5)}


class Body:
    def __init__(self, model):
        self.model = model

    def world(self, pose):
        p = copy.deepcopy(pose)
        p[0] = [4096]*3 + [0]*6
        return np.array(mmd.bone_matrices(self.model, p))


def body_skeleton(model):
    return mmd.exe().skeleton[model.type]


def frames_of(model, slot):
    return animsheet.slot_frames(model, 20, slot)[0]


def reach_need(body, f, goals):
    """Units the pelvis must go down so that every leg can reach its ground point (0 when it already can)."""
    w = body.world(f)
    need = 0.
    for (hip, knee, ankle, _), goal in goals:
        a, b = (float(np.linalg.norm(np.array(f[k][6:9], float))) for k in (knee, ankle))
        h = w[hip, :3, 3]
        horizontal = (goal[0] - h[0])**2 + (goal[2] - h[2])**2
        room = (a + b - 1.5)**2 - horizontal
        if room <= 0:
            raise ValueError('a leg cannot reach its ground point')
        need = max(need, float(goal[1] - h[1]) - math.sqrt(room))
    return need


def solve_leg(body, f, leg, goal, foot, current, pelvis_rotation, history):
    """Hip, knee and ankle rotations that put the ankle on `goal`, the knee in the plane of the old clip."""
    hip, knee, ankle, _ = leg
    w = body.world(f)
    h = w[hip, :3, 3]
    a, b = (float(np.linalg.norm(np.array(f[k][6:9], float))) for k in (knee, ankle))
    d = goal - h
    dist = float(np.linalg.norm(d))
    if not abs(a - b) < dist < a + b - .3:
        raise ValueError('a leg cannot reach its ground point')
    dirn = d/dist
    pole = current[knee, :3, 3] - current[hip, :3, 3]
    pole = pole - dirn*float(pole @ dirn)
    pole = pole/float(np.linalg.norm(pole))
    along = (a*a - b*b + dist*dist)/(2*dist)
    joint = h + dirn*along + pole*math.sqrt(max(0., a*a - along*along))
    rh, rk = current[hip, :3, :3], current[knee, :3, :3]
    new_hip = align(rh @ np.array(f[knee][6:9], float), joint - h) @ rh
    new_knee = align(rk @ np.array(f[ankle][6:9], float), goal - joint) @ rk
    set_rotation(f, hip, pelvis_rotation.T @ new_hip, history)
    w = body.world(f)
    set_rotation(f, knee, w[hip, :3, :3].T @ new_knee, history)
    w = body.world(f)
    set_rotation(f, ankle, w[knee, :3, :3].T @ foot, history)


def lift_curves(body, frames, rig):
    """0..1 per tick and leg: how high the foot is over its lowest point (0 on the ground, 1 at the top of the swing)."""
    curves = []
    for hip, knee, ankle, side in rig['legs']:
        ys = [float(body.world(p)[ankle, 1, 3]) for p in frames]
        low = max(ys)
        lift = [low - y for y in ys]
        top = max(lift) or 1.
        curves.append([v/top for v in lift])
    return curves


def legs_and_pitch(body, rig, cur, profile):
    """New pelvis and legs for one gait. Returns the poses (loop not closed)."""
    ticks = len(cur) - 1
    pelvis = rig['pelvis']
    lifts = lift_curves(body, cur[:-1], rig)
    mean = sum(p[pelvis][3] for p in cur[:-1])/ticks
    history = {}
    out = []
    for t in range(ticks):
        f = copy.deepcopy(cur[t])
        for hip, _, _, side in rig['legs']:      # the hip joints sit below the star plate: they were built inside it
            f[hip][6] += round(side*profile['hip_out'])
            f[hip][7] += round(profile['hip_drop'])
        current = body.world(cur[t])
        goals = []
        for k, leg in enumerate(rig['legs']):
            ankle = leg[2]
            g = current[ankle, :3, 3].copy()
            g[0] += leg[3]*(profile['spread'] + profile['swing']*lifts[k][t])
            goals.append((leg, g, current[ankle, :3, :3].copy()))
        if profile['pitch'] is not None:
            f[pelvis][3] = round(profile['pitch'] + profile['keep']*(cur[t][pelvis][3] - mean))
        moved = body.world(f)
        for axis in range(3):                    # the hips stay where the old clip had them
            old = sum(current[leg[0], axis, 3] for leg in rig['legs'])/2
            new = sum(moved[leg[0], axis, 3] for leg in rig['legs'])/2
            f[pelvis][6 + axis] = round(f[pelvis][6 + axis] + old - new)
        for _ in range(3):
            need = reach_need(body, f, [(leg, g) for leg, g, _ in goals])
            if need > 0:
                f[pelvis][7] += math.ceil(need)
        out.append((f, goals, current))
    frames = []
    for f, goals, current in out:
        pelvis_rotation = body.world(f)[pelvis, :3, :3]
        for leg, g, foot in goals:
            solve_leg(body, f, leg, g, foot, current, pelvis_rotation, history)
        frames.append(f)
    return frames, [g for _, g, _ in out]


def harmonic_response(signal, fn, zeta, delay=0.):
    """Periodic response of a damped pendulum (natural frequency fn cycles a loop) to a base signal, harmonic by harmonic."""
    n = len(signal)
    out = [0.]*n
    for k in range(1, n//2 + 1):
        c = sum(signal[t]*cmath.exp(-2j*PI*k*t/n) for t in range(n))*2/n
        r = k/fn
        h = cmath.exp(-2j*PI*k*delay)*r*r/(1 - r*r + 2j*zeta*r)             # pendulum driven by base acceleration: the lag and overshoot of a hung limb
        for t in range(n):
            out[t] += (c*h*cmath.exp(2j*PI*k*t/n)).real
    return out


def unit(v):
    return v/float(np.linalg.norm(v))


def hang_ribbons(body, rig, frames, rest, profile):
    """Ribbon rotations: hang down and back, lag a little behind the pelvis. Edits `frames` in place (loop not closed)."""
    ticks = len(frames)
    pelvis = rig['pelvis']
    worlds = [body.world(p) for p in frames]
    # the pendulum hangs from the ribbon root: its world x and z (fore-aft) motion drives it, through the spring
    sway, lag = {}, {}
    for root, _, _ in rig['ribbons']:
        drive = []
        for axis in (0, 2):
            s = [float(w[root, axis, 3]) for w in worlds]
            m = sum(s)/ticks
            drive.append([v - m for v in s])
        sway[root] = [harmonic_response(d, profile['fn'], profile['zeta']) for d in drive]
        lag[root] = [harmonic_response(d, profile['fn']*.7, profile['zeta'], profile['delay']) for d in drive]
    peak = max(abs(v) for r in sway.values() for s in r for v in s) or 1.
    peak2 = max(abs(v) for r in lag.values() for s in r for v in s) or 1.
    gain = math.radians(profile['amp'])/peak
    gain2 = math.radians(profile['amp'])*1.5/peak2
    history = {}
    for t, f in enumerate(frames):
        w = worlds[t]
        for root, tip, side in rig['ribbons']:
            a, b = profile.get('droop', rig['droop'])
            d1 = unit(np.array([side*a[0] + sway[root][0][t]*gain, a[1], a[2] + sway[root][1][t]*gain]))
            d2 = unit(np.array([side*b[0] + lag[root][0][t]*gain2, b[1], b[2] + lag[root][1][t]*gain2]))
            parent = rig['pelvis']
            base = w[parent, :3, :3] @ rest[root]                       # the rest orientation of the root in the body frame
            axis = np.array(f[tip][6:9], float)
            r1 = align(base @ axis, d1) @ base
            set_rotation(f, root, w[parent, :3, :3].T @ r1, history)
            local = mmd_matrix(f[root])
            r1 = w[parent, :3, :3] @ local
            # segment 2 is a hinge about its own x axis: the angle that points it nearest to d2
            v = r1.T @ d2
            along = unit(np.array(f[tip][6:9], float))
            best = None
            for sign in (1, -1):
                angle = sign*math.atan2(float(v[1]), float(v[2]))
                turn = np.array(mmd.rot_matrix(angle*4096/(2*PI), 0, 0))
                miss = float(unit(r1 @ turn @ along) @ d2)
                if best is None or miss > best[0]:
                    best = (miss, angle)
            f[tip][3:6] = [round(best[1]*4096/(2*PI)), 0, 0]


def mmd_matrix(pose_bone):
    return np.array(mmd.rot_matrix(*pose_bone[3:6]))


def inside_mesh(points, tris, directions=((1, .3, .2), (0, 1, .1), (.1, .2, 1), (-.7, .2, .5), (.3, -1, .2))):
    """Which points lie inside the (nearly closed) triangle soup `tris` (n,3,3): the majority of five rays crosses it an odd number of times."""
    import numpy
    a0, e1, e2 = tris[:, 0], tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]
    votes = numpy.zeros(len(points), int)
    for d in directions:
        d = numpy.array(d, float)
        h = numpy.cross(d, e2)
        det = (e1*h).sum(1)
        ok = numpy.abs(det) > 1e-9
        det = numpy.where(ok, det, 1)
        s = points[:, None, :] - a0[None]
        u = (s*h[None]).sum(2)/det[None]
        q = numpy.cross(s, e1[None])
        v = (q*d).sum(2)/det[None]
        t = (e2[None]*q).sum(2)/det[None]
        hit = ok[None] & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-6)
        votes += hit.sum(1) % 2
    return votes >= 3


class Clearance:
    """Counts how many sample points of a limb (vertices and triangle centres) sit inside the other parts of the body."""
    SOCKET = 30.          # points this close to the shoulder joint are the joint itself, which the model builds inside the torso

    def __init__(self, model, skeleton):
        import animstudio
        self.model = model
        self.mesh = animstudio.FastMesh(SimpleNamespace(m=model, skel=skeleton))

    def points(self, world, bones):
        import numpy
        tri = world[self.mesh.tri[numpy.isin(self.mesh.bone, bones)]]
        return numpy.vstack([tri.reshape(-1, 3), tri.mean(1)])

    def inside(self, pose, limb, others, socket=None):
        import numpy
        p = copy.deepcopy(pose)
        p[0] = [4096]*3 + [0]*6
        mats = mmd.bone_matrices(self.model, p)
        world = self.mesh.world(mats).astype(float)
        pts = self.points(world, limb)
        if socket is not None:
            pts = pts[numpy.linalg.norm(pts - numpy.array(mats[socket], float)[:3, 3], axis=1) > self.SOCKET]
        tris = world[self.mesh.tri[numpy.isin(self.mesh.bone, others)]]
        return int(inside_mesh(pts, tris).sum())


def open_arms(body, rig, frames, profile, clearance):
    """Swing each arm outward (about the pelvis' fore-aft axis) by the smallest angle that takes it out of the torso, the
    legs and the other arm on every tick: at least `arm_out` degrees, at most `arm_max`. The angles are smoothed round
    the loop (and checked again), and the old swing stays on top, so the arms still move against each other."""
    ticks = len(frames)
    everything = [1] + [b for leg in rig['legs'] for b in range(leg[0], leg[0] + 4)]

    def turned(t, shoulder, side, angle):
        f = copy.deepcopy(frames[t])
        turn = np.array(mmd.rot_matrix(0, 0, -side*angle*4096/360))
        set_rotation(f, shoulder, turn @ mmd_matrix(f[shoulder]), {shoulder: frames[t][shoulder][3:6]})
        return f

    for shoulder, side in rig['arms']:       # a smaller swing round the clip's own mean pose: the extremes are what hit the torso
        for bone, keep in zip((shoulder, shoulder + 1), profile['arm_swing']):
            for k in (3, 4, 5):
                mean = sum(f[bone][k] for f in frames)/ticks
                for f in frames:
                    f[bone][k] = round(mean + keep*(f[bone][k] - mean))
    steps = list(range(int(profile['arm_out']), int(profile['arm_max']) + 1, 4))
    for shoulder, side in rig['arms']:
        limb = [shoulder, shoulder + 1, shoulder + 2]
        others = everything + [b for s, _ in rig['arms'] if s != shoulder for b in (s, s + 1, s + 2)]
        need = []
        for t in range(ticks):
            pick = steps[-1]
            for angle in steps:
                if clearance.inside(turned(t, shoulder, side, angle), limb, others, shoulder) == 0:
                    pick = angle
                    break
            need.append(float(pick))
        for _ in range(3):
            # every angle at least the largest of its neighbours less 4 degrees a tick, then a [1 2 1] smoothing, both cyclic
            need = [max(need[(t + j) % ticks] - 4*abs(j) for j in range(-3, 4)) for t in range(ticks)]
            need = [(need[t - 1] + 2*need[t] + need[(t + 1) % ticks])/4 for t in range(ticks)]
            need = [max(a, 0.) for a in need]
            bad = [t for t in range(ticks) if clearance.inside(turned(t, shoulder, side, need[t]), limb, others, shoulder)]
            if not bad:
                break
            for t in bad:
                need[t] = min(need[t] + 6, float(profile['arm_max']))
        for t in range(ticks):
            f = turned(t, shoulder, side, need[t])
            frames[t][shoulder][3:6] = f[shoulder][3:6]


def closed(frames):
    out = copy.deepcopy(frames)
    out.append(copy.deepcopy(out[0]))
    return out


def refine_slot(body, rig, model, slot):
    cur = frames_of(model, slot)
    profile = PROFILE[slot]
    frames = cur[:-1]
    if profile['spread'] or profile['swing'] or profile['pitch'] is not None or profile['hip_drop'] or profile['hip_out']:
        frames, _ = legs_and_pitch(body, rig, cur, profile)
    idle0 = frames_of(model, 0)[0]
    pelvis = rig['pelvis']
    w0 = body.world(idle0)
    rest = {root: w0[pelvis, :3, :3].T @ w0[root, :3, :3] for root, _, _ in rig['ribbons']}
    open_arms(body, rig, frames, profile, Clearance(model, body_skeleton(model)))
    hang_ribbons(body, rig, frames, rest, profile)
    return closed(frames)


def pack(body, model, slot, frames, channels):
    old = model.anims.anims[model.anims.table[slot]]
    animation = replace_channels(old, frames, 0, 20, channels, tolerance=1)
    animation = replace_channels(animation, frames, 0, 20, {(1, c) for c in (3, 4, 6, 7, 8)}, tolerance=0)
    animation, _ = coalesce(animation)
    return animation


def build(data, skeleton, rig=RIG):
    if hashlib.sha256(data).hexdigest() != SOURCE or [b[1] for b in skeleton] != PARENTS:
        raise ValueError("Starmon's refined clips are written over the reviewed import")
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = len(skeleton)
    model = mmd.MMD.parse(data, 20)
    model.type = SPECIES
    body = Body(model)
    new = {}
    for slot in PROFILE:
        frames = refine_slot(body, rig, model, slot)
        channels = RIBBON_CHANNELS | ARM_CHANNELS | LEG_CHANNELS
        new[slot] = pack(body, model, slot, frames, channels)
    for slot, animation in new.items():
        old = model.anims.table[slot]
        model.anims.anims.append(animation)
        for i, index in enumerate(model.anims.table):        # aliases of the clip (slots 37 and 38) follow it
            if index == old:
                model.anims.table[i] = len(model.anims.anims) - 1
    used = sorted({i for i in model.anims.table if i is not None})
    renumber = {old: n for n, old in enumerate(used)}
    model.anims.anims = [model.anims.anims[i] for i in used]
    model.anims.table = [None if i is None else renumber[i] for i in model.anims.table]
    result = model.build()
    return result, dict(species=SPECIES, source_sha256=SOURCE, changed_slots=sorted(new), storage=motionstorage.require(result, 20))


def main():
    import argparse
    import json
    from pathlib import Path
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    rig = json.loads(Path('content/species/243-starmon.json').read_text())['model']['skeleton']
    data, report = build(Path(args.source).read_bytes(), rig)
    Path(args.out).write_bytes(data)
    print(args.out, len(data), 'B', report['storage'])


if __name__ == '__main__':
    main()
