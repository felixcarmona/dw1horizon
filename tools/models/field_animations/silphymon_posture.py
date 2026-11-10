"""Silphymon's field idle, walk, condition walk and run from a relaxed, upright posture.

Offline authoring only: player builds replay the pinned plain delta. Run with --source (the reviewed field model)
and --out, then store the result with tools/models/edit.py put 226.

The reviewed clips held both wing-arms out and up at shoulder height (the shoulder bones turned 100-200 degrees from
the rig's rest), the chest hunched 57 degrees over a twisted spine, and the legs slid over the floor (79-99 % of the
ground speed in the walk). In the rig's rest pose (every joint turned 0) the arms hang straight down the body's sides
with the feathers trailing behind, so every clip here is written as small turns from that rest: no joint is more than
a few tens of degrees from it, except the legs, which are solved to the floor.

- Idle (slot 0, 48 ticks): feet planted, a slow weight shift, a breath in the chest, the head drifting a few
  degrees, arms hanging with a slight forward bend and swaying a beat late, the tail following.
- Walk (2), condition walk (3) and run (4): 16 ticks, two steps per loop (the footstep sounds keep their ticks) and
  the whole body on that beat. Each foot is planted over the ground (its stance moves back at the clip's root speed)
  and swings forward in an arc, with a footstep: heel strike (toes up), roll to flat, heel lift pivoting on the ball of
  the foot, toe-off, toes curled down in the swing and the foot flexing up for the next heel strike; the pelvis turns with the leading leg, the chest against it, the head against the
  chest; the free arm swings against its leg with the elbow folding as it comes forward and the wing a beat late.
  The condition walk droops (the head low, the arms hanging, a shallow stride); the run leans forward with the
  elbows bent, bounds with a short flight between the steps and sweeps the tail back.
Tick counts and the root travel (the field speed) of the earlier clips are kept; slot 1 and every other slot too.
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
import animsheet  # noqa: E402
import mmd  # noqa: E402
import motioncyclelayer  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402

SOURCE = 'f9ccc558316989c5c8cb4d2b8167136890a7a8b2bb848ef353ab1b22d6891dcc'
SPECIES = 226
NB = 21
SLOTS = (0, 2, 3, 4)
DEG = 4096 / 360
PARENT = [-1, 0, 1, 2, 3, 3, 2, 6, 7, 2, 9, 10, 1, 12, 13, 14, 1, 16, 17, 18, 1]
PELVIS, CHEST, HEAD, EAR_R, EAR_L = 1, 2, 3, 4, 5
ARMS = ((6, 7, 8, 1), (9, 10, 11, -1))      # shoulder, elbow, hand, side (+1 right: x > 0)
LEGS = ((12, 13, 14, 15, 1), (16, 17, 18, 19, -1))   # hip, knee, ankle, toe, side
TAIL = 20
ANKLE_UP = 0.0

# Clip parameters, degrees unless noted. hp: pelvis height above the floor (units); bob: its rise per step.
# stance: fraction of a foot's 16-tick cycle on the floor; lift: swing height; first: the tick of the right foot's
# landing (the footstep sound). lean_*: forward turns of pelvis, chest, head (head's is added to cancel the rest).
CLIPS = {
    0: dict(n=48, hp=202, width=36, speed=0),
    2: dict(n=16, hp=196, bob=9, width=30, stance=.55, lift=28, first=2, pelvis_yaw=5, chest_yaw=6, head_yaw=3,
            lean_p=5, lean_c=3, head_pitch=0, arm=17, elbow0=30, elbow1=20, out=7, tail_yaw=6, roll=2.5,
            foot=dict(strike=16, roll=.22, heel_up=.5, off=30, mid=-2, curl=14, power=.75)),
    3: dict(n=16, hp=182, bob=6, width=30, stance=.60, lift=22, first=0, pelvis_yaw=4, chest_yaw=5, head_yaw=2,
            lean_p=9, lean_c=8, head_pitch=11, arm=8, elbow0=42, elbow1=12, out=6, tail_yaw=4, roll=3.5,
            foot=dict(strike=9, roll=.25, heel_up=.6, off=22, mid=7, curl=11, power=1.2)),
    4: dict(n=16, hp=176, bob=26, width=26, stance=.22, lift=62, first=2, pelvis_yaw=9, chest_yaw=12, head_yaw=4,
            lean_p=12, lean_c=5, head_pitch=-3, arm=42, elbow0=62, elbow1=24, out=6, tail_yaw=8, roll=3,
            foot=dict(strike=8, roll=.4, heel_up=.55, off=34, mid=16, curl=10, power=.75)),
}


# ---- small matrix helpers (lists of 3 rows) ----
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
    return scale(a, 1 / norm(a))


def rot(x=0., y=0., z=0.):
    """Rx.Ry.Rz in degrees (libgte order): +x leans a standing body forward, +y turns it to its left, +z rolls its
    top towards +x (the right)."""
    return mmd.rot_matrix(x * DEG, y * DEG, z * DEG)


def swing(u0, u1):
    """The shortest turn taking direction u0 to u1."""
    axis = cross(u0, u1)
    s = norm(axis)
    c = dot(u0, u1)
    if s < 1e-9:
        return [[1., 0, 0], [0, 1., 0], [0, 0, 1.]]
    k = unit(axis)
    kx = [[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]]
    kk = mul(kx, kx)
    return [[(1 if i == j else 0) + s * kx[i][j] + (1 - c) * kk[i][j] for j in range(3)] for i in range(3)]


def smooth(x):
    x = min(1., max(0., x))
    return x * x * (3 - 2 * x)


class Rig:
    """Forward kinematics of the rig with unit scales: local rotation matrices and translations."""

    def __init__(self, local_t):
        self.t = local_t
        self.rl = [rot() for _ in range(NB)]

    def fk(self):
        rw, p = [None] * NB, [None] * NB
        for b in range(NB):
            par = PARENT[b]
            if par < 0:
                rw[b], p[b] = rot(), [0., 0., 0.]
            else:
                rw[b] = mul(rw[par], self.rl[b])
                p[b] = add(p[par], mv(rw[par], self.t[b]))
        return rw, p

    def set_world(self, b, rw_b, rw):
        """Give bone b the world rotation rw_b (its parent's is already in rw)."""
        self.rl[b] = mul(tr(rw[PARENT[b]]), rw_b)


def solve_leg(rig, side_info, goal, foot_rot, toe_pitch, pole, verts):
    """Place one leg so the ankle reaches `goal`: thigh, shin and foot world rotations. Returns the reach error."""
    hip, knee, ankle, toe, side = side_info
    rw, p = rig.fk()
    h = p[hip]
    a, b = norm(rig.t[knee]), norm(rig.t[ankle])
    d = sub(goal, h)
    dist = norm(d)
    limit = (a + b) * .995
    if dist > limit:
        d = scale(d, limit / dist)
        dist = limit
    dire = unit(d)
    along = (a * a - b * b + dist * dist) / (2 * dist)
    pp = sub(pole, scale(dire, dot(pole, dire)))
    pp = unit(pp)
    kpos = add(add(h, scale(dire, along)), scale(pp, math.sqrt(max(0., a * a - along * along))))
    r_thigh = swing(unit(rig.t[knee]), unit(sub(kpos, h)))
    rig.set_world(hip, r_thigh, rw)
    rw, p = rig.fk()
    r_shin = swing(unit(rig.t[ankle]), unit(sub(add(h, d), kpos)))
    rig.set_world(knee, r_shin, rw)
    rw, p = rig.fk()
    rig.set_world(ankle, foot_rot, rw)
    rw, p = rig.fk()
    rig.set_world(toe, mul(foot_rot, rot(toe_pitch)), rw)
    return norm(sub(p[ankle], goal))


def sole_depth(rig, ankle, toe, verts):
    """Lowest point (largest y) of the foot and toe meshes relative to the ankle joint."""
    rw, p = rig.fk()
    low = -1e9
    for bone in (ankle, toe):
        for v in verts[bone]:
            w = add(mv(rw[bone], v), p[bone])
            low = max(low, w[1] - p[ankle][1])
    return low


def stance_path(c, rho, speed, f):
    """Foot z in the body frame, along its 16-tick cycle (0 = landing): stance moves back at the ground speed."""
    zf, zb = c - speed * 16 * f / 2, c + speed * 16 * f / 2
    if rho < f:
        return zf + speed * 16 * rho, 0.
    q = (rho - f) / (1 - f)
    span = (1 - f) * 16
    m = speed * span
    h00, h10, h01, h11 = 2 * q ** 3 - 3 * q * q + 1, q ** 3 - 2 * q * q + q, -2 * q ** 3 + 3 * q * q, q ** 3 - q * q
    return h00 * zb + h10 * m + h01 * zf + h11 * m, q


def heel_point(verts, ankle, strike):
    """The heel's lowest point (in the ankle bone's frame) when the foot is raised `strike` degrees at the toes."""
    r = rot(-strike)
    return max(verts[ankle], key=lambda v: mv(r, v)[1])


def foot_cycle(rig, verts, leg, fo, c, rho, z_ref):
    """Pitch of the foot (degrees, + toes down), toe bone relative to the foot, the z shift of the ankle from the
    ground-fixed track and the swing lift, for a foot at cycle phase rho: heel strike, roll to flat, heel lift
    pivoting on the ball of the foot, toe-off, a swing with the toes curled down, the foot flexing up to the next
    heel strike. The contact point (heel, then the flat sole, then the ball) does not move over the floor."""
    hip, knee, ankle, toe, side = leg
    heel = heel_point(verts, ankle, fo['strike'])
    ball_t, ball_b = rig.t[toe], [0., 20., 0.]

    def stance_z(theta, tau, kind):
        ra = rot(theta)
        if kind == 'heel':
            return heel[2] - mv(ra, heel)[2]
        if kind == 'ball':
            rt = mul(ra, rot(tau))
            off = add(mv(ra, ball_t), mv(rt, ball_b))
            return ball_t[2] + ball_b[2] - off[2]
        return 0.

    f = c['stance']
    if rho < f:
        u = rho / f
        if u < fo['roll']:
            theta, kind = -fo['strike'] * (1 - smooth(u / fo['roll'])), 'heel'
        elif u < fo['heel_up']:
            theta, kind = 0., 'flat'
        else:
            theta, kind = fo['off'] * smooth((u - fo['heel_up']) / (1 - fo['heel_up'])), 'ball'
        tau = -theta if kind == 'ball' else 0.
        return theta, tau, stance_z(theta, tau, kind), 0., None
    q = (rho - f) / (1 - f)
    theta = fo['off'] + (fo['mid'] - fo['off']) * smooth(q / .5) if q < .5 else \
        fo['mid'] + (-fo['strike'] - fo['mid']) * smooth((q - .5) / .5)
    world_toe = fo['curl'] * math.sin(math.pi * min(q / .55, 1.))
    tau = (world_toe - theta) * (1 - smooth((q - .55) / .45))
    d0 = stance_z(fo['off'], -fo['off'], 'ball')
    d1 = stance_z(-fo['strike'], 0., 'heel')
    dz = d0 * (1 - smooth(q / .5)) + d1 * smooth((q - .5) / .5)
    return theta, tau, dz, c['lift'] * math.sin(math.pi * q) ** fo['power'], None


def pose_at(model_t, verts, rest_pose, slot, t, c, speed, state):  # noqa: C901
    n = c['n']
    rig = Rig(copy.deepcopy(model_t))
    pose = copy.deepcopy(rest_pose)
    if slot == 0:
        return idle_pose(rig, verts, pose, c, t)
    sig = 2 * math.pi * (t - c['first']) / n       # 0 when the right foot lands, at the front
    cs = lambda lag=0.: math.cos(sig - 2 * math.pi * lag)
    sn = lambda lag=0.: math.sin(sig - 2 * math.pi * lag)
    run = slot == 4
    # the pelvis: height, a turn with the leading leg, a roll over the standing leg, a lean
    if run:
        stance_mid = math.pi * c['stance']
        rise = (1 - math.cos(2 * (sig - stance_mid))) / 2
        height = c['hp'] + c['bob'] * rise
    else:
        height = c['hp'] + c['bob'] * (-math.cos(2 * sig)) * .5 + c['bob'] * .5
    sway = -4.0 * sn() * (0 if run else 1)     # toward the standing foot
    rig.t[PELVIS] = [sway, -height, rig.t[PELVIS][2]]
    lean = c['lean_p']
    if run:
        lean += 1.5 * math.cos(2 * (sig - stance_mid))
    yaw_p = c['pelvis_yaw'] * cs(0.)
    roll_p = -c['roll'] * sn()
    rig.rl[PELVIS] = rot(lean, yaw_p, roll_p)
    # chest against the pelvis, later; head against the chest, later still
    yaw_c = -(c['pelvis_yaw'] + c['chest_yaw']) * cs(.06)
    rig.rl[CHEST] = rot(c['lean_c'] + .8 * (1 if run else .5) * math.cos(2 * sig - .5), yaw_c, -.5 * roll_p)
    yaw_h = (c['chest_yaw'] + c['head_yaw']) * cs(.12) * 1.0 + .3 * c['pelvis_yaw'] * cs(.0)
    rig.rl[HEAD] = rot(c['head_pitch'] - c['lean_p'] - c['lean_c'] + 1.6 * math.sin(2 * sig - .9), yaw_h, .5 * roll_p)
    rig.rl[EAR_R] = rot(2.5 * math.sin(2 * sig - 1.6), 0, 2 * math.sin(sig - 1.6))
    rig.rl[EAR_L] = rot(2.5 * math.sin(2 * sig - 1.6), 0, -2 * math.sin(sig - 1.6))
    # arms: the free arm swings against its leg (the right arm is back when the right foot is forward)
    for shoulder, elbow, hand, side in ARMS:
        ph = sig if side > 0 else sig + math.pi
        back = math.cos(ph - .18)
        fold = .5 - .5 * back             # 1 when the arm is furthest forward
        a_sh = c['arm'] * back + (4 if run else 2)
        rig.rl[shoulder] = rot(a_sh, 0, -side * (c['out'] + 2 * math.sin(ph - .6)))
        rig.rl[elbow] = rot(-(c['elbow0'] + c['elbow1'] * fold) + 2.5 * math.sin(ph - 1.0), 0, 0)
        rig.rl[hand] = rot(-.25 * (c['elbow0'] + c['elbow1'] * fold) * (1 if run else .6) + 4 * math.sin(ph - 1.4), 0, -side * 2 * math.sin(ph - 1.8))
    # tail: sways against the hips, a beat late, and drops a little with the bounce
    rig.rl[TAIL] = rot(-c['lean_p'] * .8 + (12 if run else 2) + 2.2 * math.sin(2 * sig - 1.2), -c['tail_yaw'] * cs(.2), 2 * sn(.3))
    # legs
    errs = []
    root_speed = speed
    for hip, knee, ankle, toe, side in LEGS:
        offset = 0 if side > 0 else .5
        rho = ((t - c['first']) / n - offset) % 1.
        center = 6.
        z, q = stance_path(center, rho, root_speed, c['stance'])
        fo = c['foot']
        theta, tau, dz, lift, pivot_info = foot_cycle(rig, verts, (hip, knee, ankle, toe, side), fo, c, rho, z)
        z += dz
        x = side * (c['width'] + 4 * math.sin(math.pi * q) ** 2 * (rho >= c['stance']))
        foot = rot(theta)
        # the ankle height that puts the lowest sole point on the floor (plus the swing lift)
        goal = [x, 0., z]
        rig_probe = copy.deepcopy(rig)
        solve_leg(rig_probe, (hip, knee, ankle, toe, side), [x, -30., z], foot, tau, [0., 0., -1.], verts)
        depth = sole_depth(rig_probe, ankle, toe, verts)
        goal[1] = -depth - lift
        pole = [side * .18, 0., -1.]
        errs.append(solve_leg(rig, (hip, knee, ankle, toe, side), goal, foot, tau, pole, verts))
        state.setdefault('foot', {})[(t, side)] = (theta, tau, theta + tau)
    state['reach'] = max(state.get('reach', 0), max(errs))
    return rig


def idle_pose(rig, verts, pose, c, t):
    n = c['n']
    sig = 2 * math.pi * t / n
    sn, cs = math.sin, math.cos
    rig.t[PELVIS] = [1.6 * sn(sig - .4), -(c['hp'] + .8 * sn(2 * sig - .3)), rig.t[PELVIS][2]]
    rig.rl[PELVIS] = rot(4 + .7 * sn(2 * sig - 1.2), 1.2 * sn(sig - .2), 1.4 * sn(sig + .6))
    rig.rl[CHEST] = rot(2 + 1.2 * sn(2 * sig - 1.7), -1.2 * sn(sig - .5), -.8 * sn(sig + .6))
    rig.rl[HEAD] = rot(-6 + 1.5 * sn(2 * sig - 2.2), 4.5 * sn(sig - 1.0), .8 * sn(sig - .8))
    rig.rl[EAR_R] = rot(2 * sn(2 * sig - 2.8), 0, 2 * sn(sig - 1.5))
    rig.rl[EAR_L] = rot(2 * sn(2 * sig - 2.8), 0, -2 * sn(sig - 1.5))
    for shoulder, elbow, hand, side in ARMS:
        lag = 0. if side > 0 else .7
        rig.rl[shoulder] = rot(-2 + 2.2 * sn(sig - 1.0 - lag), 0, -side * (7 + 1.5 * sn(2 * sig - 1.4 - lag)))
        rig.rl[elbow] = rot(-(32 + 3 * sn(sig - 1.5 - lag) + 1.5 * sn(2 * sig - 2.0)), 0, 0)
        rig.rl[hand] = rot(-5 + 3 * sn(sig - 2.0 - lag), 0, -side * 2.5 * sn(2 * sig - 2.4 - lag))
    rig.rl[TAIL] = rot(2 + 2 * sn(2 * sig - 2.4), 4 * sn(sig - 1.4), 1.5 * sn(sig - 1.0))
    errs = []
    for hip, knee, ankle, toe, side in LEGS:
        foot = rot(0, 0, 0)
        goal = [side * c['width'], 0., 6.]
        probe = copy.deepcopy(rig)
        solve_leg(probe, (hip, knee, ankle, toe, side), [goal[0], -30., 6.], foot, 0, [0., 0., -1.], verts)
        depth = sole_depth(probe, ankle, toe, verts)
        goal[1] = -depth
        errs.append(solve_leg(rig, (hip, knee, ankle, toe, side), goal, foot, 0, [side * .12, 0., -1.], verts))
    return rig


def author(model, skeleton):
    """`model` with the idle, walk, condition walk and run replaced -> (bytes, checks)."""
    mmd.exe().add_type(SPECIES, [tuple(b) for b in skeleton])
    old = mmd.MMD.parse(model, NB)
    old.type = SPECIES
    rest_frames = animsheet.slot_frames(old, NB, 0)[0]
    rest = [list(v) for v in rest_frames[0]]
    local_t = [[float(x) for x in rest[b][6:9]] for b in range(NB)]
    verts = {b: [list(map(float, v[:3])) for v in old.tmd.obj_verts(skeleton[b][0])] for b in range(1, NB)}
    result = copy.deepcopy(old)
    streams, checks = {}, []
    for slot in SLOTS:
        c = CLIPS[slot]
        frames, loop, events = animsheet.slot_frames(old, NB, slot)
        assert loop == 0, (slot, loop)
        n = c['n']
        if slot:
            assert len(frames) - 1 == n, (slot, len(frames))
            total = frames[-1][0][8] - frames[0][0][8]
            speed = -total / n
        else:
            speed = 0.
        out, prev, state = [], {}, {}
        for t in range(n + 1):
            rig = pose_at(local_t, verts, rest, slot, t % n if t < n else 0, c, speed, state)
            pose = copy.deepcopy(rest)
            for b in range(1, NB):
                pose[b][6:9] = [round(v) for v in rig.t[b]]
                angles = mmd.matrix_euler(rig.rl[b], prev.get(b, [0, 0, 0]))
                prev[b] = angles
                pose[b][3:6] = [round(v) for v in angles]
            pose[0] = list(frames[0][0]) if slot == 0 else list(frames[t][0])
            out.append(pose)
        out = [[[round(x) for x in v] for v in pose] for pose in out]
        mmd.close_loop(out, 0)
        streams[slot] = len(result.anims.anims)
        result.anims.anims.append(mmd.encode_anim(out, NB, 0, list(events), tol=c.get('tol', 2), repeats=False))
        checks.append(dict(slot=slot, ticks=n, reach_error=round(state.get('reach', 0), 2)))
    for slot in SLOTS:
        result.anims.table[slot] = streams[slot]
    for anim in result.anims.anims:
        anim.tail = b''
    result.anims.anims, result.anims.table = motioncyclelayer.share_identical_streams(result.anims.anims,
                                                                                    result.anims.table)
    output = result.build()
    effective = mmd.MMD.parse(output, NB)
    effective.type = SPECIES
    assert effective.tmd.build() == old.tmd.build()
    assert changed_programs(old, effective) == list(SLOTS), changed_programs(old, effective)
    for row in checks:
        samples, loop, _ = animsheet.slot_frames(effective, NB, row['slot'])
        assert loop == 0
        row['decoded_ticks'] = len(samples) - 1
        row['root_per_tick'] = round((samples[-1][0][8] - samples[0][0][8]) / (len(samples) - 1), 2)
    return output, dict(checks=checks, storage=motionstorage.require(output, NB))


def build(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('Silphymon posture requires the reviewed field model')
    output, proof = author(data, skeleton)
    return output, dict(proof, source_sha256=SOURCE, output_sha256=hashlib.sha256(output).hexdigest())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/226-silphymon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    main()
