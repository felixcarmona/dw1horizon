"""Kotemon's field walk, tired walk and run (species 351, slots 2, 3 and 4) as one small body on planted feet.

Kotemon is a kendo-armoured child: a torso (bone 1) with the face guard and its two horns (17), a shoulder plate on each
side (12, 22) and both arms (right 13-14-15 with the shinai 16 on its hand, left 18-19-20), a wide skirt of armour (2)
under it with the tail (3-4-5) and the legs: a thigh stub (6 right, 9 left), a broad foot block (7, 10) whose sole
spreads forward from the ankle and the claw plate (8, 11). Forward is -z. Bones 21 and 23 are two more copies of the
shinai that the model keeps hidden with a scale of zero (`imported_equipment.repair` writes that).

What was wrong. The clips came with the model from another game and only their legs were its own: the foot blocks
flapped from the ankle (the claw plate swung 285 degrees), the soles slid 46-100 % (walk), 129-278 % (tired walk) and
59-122 % (run) of the travel, the cycles were 17, 21 and 13 ticks at 23, 15 and 46 units a tick. Everything above the
skirt came from a later pass (`articulation.kotemon`) that only rocked the torso by 1-3 degrees and the guard by 3.

What the clips are now. One gait phase drives the whole body. The thighs are only a few units long and the feet are
long, so a planted foot cannot reach by turning the leg alone: each foot is placed first (heel strike, flat on the floor,
then the heel peels while the claw plate stays down; the outer edge lands first, the toe pushes off and the foot flexes up before it lands, and the two feet and cycles lift differently; every touchdown presses the hips and skirt down), and the thigh stub rides forward and back under the skirt to meet
the ankle with a small swing of its own (the skirt hides it). The skirt turns against the torso, the torso against the
skirt and the face guard follows late. Both hands hold the shinai, so the arms and the sword move as one guard,
rigid about the grip, hung from the torso on a loose spring: the tip lags and overshoots the body. The shoulder plates
and the tail follow late. Every clip is two cycles long: the second differs from the first (a different lift, a
touchdown a little earlier or later, a deeper dip, a wider swing) and the clip eases from one into the other so that no
two steps are alike and the loop still closes.

`build_clips` writes the three clips on the reviewed imported model (the one the species record's recipe starts from);
`imported_equipment.build` then restores the hidden equipment on it. Offline: `python3 -m
tools.models.field_animations.kotemon_gait --source EDIT.MMD --out AFTER.MMD` with EDIT.MMD the model
`tools/models/edit.py get 351` makes.
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
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models.field_animations.quadruped import mul, tr, mv, add, sub, rot, set_rot, smooth, minimum_jerk  # noqa: E402

SPECIES = 351
SOURCE = '5b043a68ea1b12698d95ac1296030e80a4c2e8853c9f9d9f3c5d42f9be82fea1'
TAU = 2 * math.pi
DEG = 4096 / 360
BONES = 24
TORSO, SKIRT, HEAD = 1, 2, 17
TAIL = (3, 4, 5)
PADS = (12, 22)
GUARD = (13, 18)                    # the two shoulders; the shinai hangs from the right hand
LEGS = {'RH': (6, 7, 8, 1), 'LH': (9, 10, 11, -1)}      # thigh stub, foot block, claw plate, side (+1 = x > 0)
HEEL = (0.0, 31.0, -3.0)            # in the foot block's space: the back of the sole
ANKLE_TO_HINGE = (0.0, 17.0, -55.0)  # the claw plate's hinge
SOLE = 31.0                         # the sole is this far under the ankle
SPEED = {2: 16, 3: 11, 4: 36}
TICKS = {2: 13, 3: 15, 4: 11}        # one cycle (two steps); a clip is two cycles
STRICT = True
SLIDE = (2.0, 3.0, 10.0)            # how far the thigh stub may leave its rest place under the skirt (x, y, z)
MAX_TILT = 40.0                     # how far the leg may turn from its rest direction to reach a foot (degrees)


def align(u0, d, limit):
    """The rotation that turns direction u0 towards d, by at most `limit` degrees."""
    n = math.sqrt(sum(x * x for x in u0))
    a = [x / n for x in u0]
    c = max(-1.0, min(1.0, sum(x * y for x, y in zip(a, d))))
    ang = min(math.acos(c), math.radians(limit))
    ax = [a[1] * d[2] - a[2] * d[1], a[2] * d[0] - a[0] * d[2], a[0] * d[1] - a[1] * d[0]]
    m = math.sqrt(sum(x * x for x in ax))
    if m < 1e-9:
        return [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    ax = [x / m for x in ax]
    C, S = math.cos(ang), math.sin(ang)
    x, y, z = ax
    return [[C + x * x * (1 - C), x * y * (1 - C) - z * S, x * z * (1 - C) + y * S],
            [y * x * (1 - C) + z * S, C + y * y * (1 - C), y * z * (1 - C) - x * S],
            [z * x * (1 - C) - y * S, z * y * (1 - C) + x * S, C + z * z * (1 - C)]]


def harm(phase, *terms):
    """A sum of cosines: terms are (amplitude, rate, delay in cycles)."""
    return sum(a * math.cos(TAU * rate * (phase - delay)) for a, rate, delay in terms)


def spring(values, rate, damping):
    """A loose second-order follower of a cyclic sequence (run round three times so the loop settles)."""
    n = len(values)
    y, v = values[0], 0.0
    out = []
    for i in range(3 * n):
        x = values[i % n]
        v += rate * rate * (x - y) - 2 * damping * rate * v
        y += v
        out.append(y)
    return out[-n:]


# ------------------------------------------------------------------ the gaits' numbers
# Each clip has cycle A and cycle B; the clip is two cycles long and every number eases from A to B and back.
BASE = dict(
    height=0.0, bob=3.0, bob2=0.5, bob_at=0.05, shift=3.0, shift_at=0.25,
    lean=8.0, pitch=1.2, pitch_at=0.1, hip_yaw=7.0, hip_roll=2.5, hip_pitch=1.0, roll=2.5, yaw=3.0, counter=0.8,
    lag=0.07, breath=0.0, track=31.0, centre=7.0, swing=30.0,
    beta=3.0, gamma=0.0, heel_end=0.16, ball_start=0.62, lift=6.0, arc=0.4, curl=-8.0, out=2.0,
    head=-2.0, steady=0.7, nod=1.0, look=1.5, sword=1.0, sword_rate=0.45, sword_damp=0.5, pads=2.0, tail=6.0, tail_lag=0.09,
    duty=0.55, hold=0.9, flight=0.0, pad_lag=0.1, hop=0.0, hop_at=0.04, hop_rate=0.8, hop_damp=0.42,
    kick=0.0, roll_in=0.0, roll_out=0.0, squash=0.0, sway=0.0, drag=0.0,
)
GAITS = {
    2: dict(name='walk', ticks=13, speed=16,
            a=dict(centre=8.0, duty=0.22, arc=0.6, hop=5.0, squash=2.0, sway=1.5, gamma=2.0, heel_end=0.25, beta=4.0, ball_start=0.5, lift=6.0, kick=1.5, curl=-5.0, roll_in=2.0, roll_out=1.5),
            b=dict(bob=3.8, hop=6.0, lift=7.0, hip_yaw=8.0, shift=3.6, lean=9.0, swing=33.0),
            td=(0.0, 0.0, -0.2, 0.2), st=(-0.3, -0.3, -0.3, -0.3), zc=(0.0, 0.0, 0.0, 0.0), lk=(1.0, 0.82, 1.12, 0.92), tilt=62.0),
    3: dict(name='tired walk', ticks=15, speed=11,
            a=dict(centre=5.0, duty=0.24, arc=0.6, height=1.0, hop=2.0, squash=1.5, sway=1.2, hop_rate=0.5, hop_damp=0.6, bob=2.2, lean=15.0, hip_yaw=4.0, hip_roll=3.0, roll=3.0, shift=4.0, beta=3.0, gamma=1.5, heel_end=0.3, lift=4.0, curl=-4.0, kick=1.0, roll_in=1.5, roll_out=1.0,
                   head=-14.0, nod=1.5, ball_start=0.55, swing=26.0, sword=1.2, tail=4.0),
            b=dict(bob=2.8, lift=5.0, lean=17.0, head=-17.0, shift=4.6),
            td=(0.0, 0.0, -0.4, 0.5), st=(0.0, 0.0, 0.0, 0.0), zc=(0.0, 2.0, -1.5, 2.5), lk=(1.0, 0.8, 1.1, 0.9), tilt=62.0),
    4: dict(name='run', ticks=11, speed=36, tilt=60.0,
            a=dict(height=2.0, bob=5.0, bob2=0.8, lean=17.0, hip_yaw=9.0, hip_roll=3.0, roll=3.0, shift=2.5, beta=3.0, gamma=0.0, lift=8.0, squash=2.4, sway=1.3, kick=0.0, roll_in=1.0, roll_out=1.0, 
                   head=4.0, hop=8.0, duty=0.08, centre=3.0, heel_end=0.12, ball_start=0.5, swing=36.0, sword=1.5, tail=9.0, pads=3.5, counter=1.0,
                   pitch=2.0, arc=0.4, curl=-12.0),
            b=dict(bob=5.8, lift=9.0, lean=19.0, hip_yaw=10.0, swing=39.0),
            td=(0.0, 0.0, -0.2, 0.25), st=(-0.12, -0.08, -0.12, -0.08), zc=(0.0, 2.0, -2.0, 3.0), lk=(1.0, 0.88, 1.1, 0.95)),
}


def params(gait, w):
    """The gait's numbers at weight w of cycle B over cycle A."""
    a = dict(BASE, **gait['a'])
    b = dict(a, **gait['b'])
    return {k: a[k] + (b[k] - a[k]) * w for k in a}


class Kotemon:
    def __init__(self, model):
        self.m = model
        self.rest = [list(v) for v in animsheet.slot_frames(model, BONES, 0)[0][0]]
        self.rest[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
        self.verts = {b: [list(map(float, v[:3])) for v in model.tmd.obj_verts(o)]
                      for b, (o, _) in enumerate(mmd.exe().skeleton[SPECIES]) if o >= 0}
        self.foot_rest = {name: mmd.rot_matrix(*self.rest[bones[0]][3:6]) for name, bones in LEGS.items()}

    def world(self, pose):
        p = [list(v) for v in pose]
        p[0] = [4096, 4096, 4096] + p[0][3:6] + [0, 0, 0]
        return mmd.bone_matrices(self.m, p)

    def dip(self, bone, rot_):
        """How far under its origin a bone's mesh reaches at this world rotation (y grows downwards)."""
        return max(rot_[1][0] * v[0] + rot_[1][1] * v[1] + rot_[1][2] * v[2] for v in self.verts[bone])


def pitch_about(F, deg, roll=0.0):
    """The foot's world rotation turned `deg` (toe down positive) about its own lateral axis, and `roll` about its length."""
    return mul(F, rot([deg, 0, roll]))


# ------------------------------------------------------------------ feet
def step(cfg, gait, n):
    """Step n of the endless loop (any integer; the loop repeats every four): the leg, its touchdown tick, the stance's
    length in ticks, the numbers of its cycle and where its flat foot stands in the world."""
    T, v = cfg['ticks'], cfg['speed']
    k = n % 4
    td = n * T / 2 + gait['td'][k]
    p = params(gait, 0.5 - 0.5 * math.cos(TAU * (n * T / 2) / (2 * T)))
    st = p['duty'] * T + gait['st'][k]
    if gait.get('snap'):
        st = round(td + st - 0.5) + 0.5 - td     # the foot leaves half a tick before a frame, so a frame never shows it half-lifted
    zf = -v * (td + st / 2) + p['centre'] + gait['zc'][k]
    return dict(n=n, leg='LH' if n % 2 == 0 else 'RH', td=td, st=st, p=p, zf=zf)


def stance_pose(p, xs, zf, s):
    """Ankle position, foot-block pitch and claw-plate pitch (degrees, toe down positive, from flat) at fraction s of a stance
    whose flat ankle is (xs, -SOLE, zf): heel strike (the foot turns down about its heel), flat, then the heel peels."""
    flat = [xs, -SOLE, zf]
    if s < p['heel_end']:
        pitch = -p['gamma'] * (1 - smooth(s / p['heel_end']))
        return flat, pitch, pitch, 'heel'
    if s < p['ball_start']:
        return flat, 0.0, 0.0, 'flat'
    pitch = p['beta'] * smooth((s - p['ball_start']) / (1 - p['ball_start']))
    return flat, pitch, 0.0, 'ball'


def placed(F, flat, pitch, phase, roll=0.0):
    """The ankle for a stance pitch: the foot turns about its heel (strike) or the claw plate's hinge (peel)."""
    R = pitch_about(F, pitch, roll)
    if phase == 'heel':
        c = add(flat, mv(F, HEEL))
        return sub(c, mv(R, HEEL)), R
    if phase == 'ball':
        c = add(flat, mv(F, ANKLE_TO_HINGE))
        return sub(c, mv(R, ANKLE_TO_HINGE)), R
    return list(flat), R


def swing_z(cfg, z0, z1, t0, t1, u, drag):
    """The swing's z in the world. The leg is short, so the foot is eased in the body's own frame: it leaves the ground moving
    back with the ground (the body's speed), runs on, comes forward and lands moving back with the ground again, so that it
    arrives planted and never has to be further ahead of the hips than the leg reaches."""
    v = cfg['speed']
    r0, r1 = z0 + v * t0, z1 + v * t1                   # the two ends in the body's frame
    D = t1 - t0
    m0 = m1 = v * D * drag
    h00, h10, h01, h11 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u, -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
    return h00 * r0 + h10 * m0 + h01 * r1 + h11 * m1 - v * (t0 + u * D)


def foot_at(kot, cfg, gait, name, t):
    """One foot at tick t: ankle (world, root travel included), foot-block rotation, claw-plate rotation, and whether it stands."""
    T = cfg['ticks']
    F = kot.foot_rest[name]
    side = LEGS[name][3]
    parity = 0 if name == 'LH' else 1
    base = int(math.floor(t / (T / 2)))
    for n in range(base - 4, base + 5):
        if n % 2 != parity:
            continue
        s, nxt = step(cfg, gait, n), step(cfg, gait, n + 2)
        if not s['td'] <= t < nxt['td']:
            continue
        p = s['p']
        xs = side * p['track']
        if t < s['td'] + s['st']:
            u = (t - s['td']) / s['st']
            flat, pitch, plate, phase = stance_pose(p, xs, s['zf'], u)
            # the outer edge lands first and settles as the heel comes down
            roll = side * p['roll_in'] * (1 - smooth(u / p['heel_end'])) if phase == 'heel' else 0.0
            A, R = placed(F, flat, pitch, phase, roll)
            return A, R, pitch_about(F, plate, roll), True
        # the swing: from the peeled foot at the lift-off to the heel-first foot at the next touchdown, eased in the world
        u = (t - s['td'] - s['st']) / (nxt['td'] - s['td'] - s['st'])
        f0, pit0, _, ph0 = stance_pose(p, xs, s['zf'], 1.0)
        A0, _ = placed(F, f0, pit0, ph0)
        pn = nxt['p']
        f1, pit1, _, ph1 = stance_pose(pn, side * pn['track'], nxt['zf'], 0.0)
        A1, _ = placed(F, f1, pit1, ph1, side * pn['roll_in'])
        lk = gait['lk'][n % 4]                      # the two feet and the two cycles lift a little differently
        A = [A0[0] + (A1[0] - A0[0]) * smooth(u) + side * p['out'] * lk * math.sin(math.pi * u),
             A0[1] + (A1[1] - A0[1]) * smooth(u) - p['lift'] * lk * math.sin(math.pi * u ** p['arc']) ** 1.2,
             0.0]
        if p['drag'] > 0:
            A[2] = swing_z(cfg, A0[2], A1[2], s['td'] + s['st'], nxt['td'], u, p['drag'])
        else:
            A[2] = A0[2] + (A1[2] - A0[2]) * minimum_jerk(minimum_jerk(u))
        # the toe pushes off (kick) and levels, then the foot flexes up (curl) to land heel first; the claw plate trails it
        kick = p['kick'] * math.sin(math.pi * min(u / 0.3, 1.0)) if u < 0.3 else 0.0
        uc = max(0.0, (u - 0.3) / 0.7)
        pitch = pit0 + (pit1 - pit0) * smooth(u) + p['curl'] * math.sin(math.pi * u) * (1 - u) + kick
        flex = -pit0 * (1 - smooth(u / 0.4)) + 0.5 * p['curl'] * math.sin(math.pi * u) + 0.6 * kick
        roll = side * (pn['roll_in'] * smooth(u) ** 2 + p['roll_out'] * math.sin(math.pi * u))
        R, R8 = pitch_about(F, pitch, roll), pitch_about(F, pitch + flex, roll)
        # the lowest point of the foot keeps off the floor, easing in so the lift-off does not jump
        low = max(A[1] + kot.dip(7, R), A[1] + mv(R, ANKLE_TO_HINGE)[1] + kot.dip(8, R8))
        clear = 1.5 + 2.5 * smooth(u / 0.3)
        if low + clear > 0 and u > 0.02:
            A[1] -= (low + clear) * smooth(u / 0.15)
        return A, R, R8, False
    raise AssertionError((name, t))


# ------------------------------------------------------------------ the body
def body_angles(cfg, gait, t, c):
    """Everything above the legs that the gait decides at tick t, as plain numbers: height, sideways shift, the three turns
    of the skirt and of the torso, the head's own pitch."""
    T = cfg['ticks']
    ph = t / T
    w = 0.5 - 0.5 * math.cos(TAU * ph / 2)
    p = params(gait, w)
    out = dict(p=p)
    out['y'] = p['height'] - harm(ph, (p['bob'], 2, p['bob_at']), (p['bob2'], 4, p['bob_at'] + 0.03)) - 0.4 * p['bob'] * math.cos(TAU * (ph / 2 - 0.1))
    out['x'] = harm(ph, (p['shift'], 1, 0.75)) + 0.6 * math.cos(TAU * (ph / 2 - 0.2))
    hp = harm(ph, (p['hip_pitch'], 2, p['pitch_at'] + 0.1))
    hy = harm(ph, (p['hip_yaw'], 1, 0.02), (0.5, 3, 0.05))
    hr = -harm(ph, (p['hip_roll'], 1, 0.7)) + 0.6 * math.sin(TAU * ph / 2)
    out['hips'] = [hp, hy, hr]
    lag = p['lag']
    up = p['lean'] + harm(ph - lag, (p['pitch'], 2, p['pitch_at']), (0.4 * p['pitch'], 1, p['pitch_at'] + 0.1)) + 0.5 * math.sin(TAU * ph / 2)
    uy = -p['counter'] * hy + harm(ph - lag, (p['yaw'], 1, 0.15)) + 0.8 * math.sin(TAU * (ph / 2 - 0.2))
    ur = harm(ph - lag, (p['roll'], 1, 0.75), (0.4 * p['roll'], 3, 0.1)) + 0.7 * math.cos(TAU * (ph / 2 - 0.3))
    out['torso'] = [up, uy, ur]
    return out


def build_frames(kot, cfg, gait):
    """The loop's frames (two cycles plus the closing one) from the gait's numbers."""
    T, v = cfg['ticks'], cfg['speed']
    N = 2 * T
    rest = kot.rest
    seq = [body_angles(cfg, gait, t, None) for t in range(N)]
    # the loose parts follow the body through springs of their own
    def follow(values, rate, damping):
        return spring(values, rate, damping)
    torso = [s['torso'] for s in seq]
    mean = [sum(a[i] for a in torso) / N for i in range(3)]
    dev = [[a[i] - mean[i] for a in torso] for i in range(3)]
    rate, damp = BASE['sword_rate'], BASE['sword_damp']
    sw = [follow(d, rate, damp) for d in dev]
    ybob = [s['y'] for s in seq]
    ymean = sum(ybob) / N
    ysw = follow([y - ymean for y in ybob], rate * 1.2, 0.35)
    head_pitch = follow([s['torso'][0] - mean[0] for s in seq], 0.7, 0.55)
    head_roll = follow(dev[2], 0.7, 0.55)
    pad = follow([y - ymean for y in ybob], 0.55, 0.3)
    # the bounce: the upper body springs on the hips, like a ball landing on each beat (the hips and legs keep their height)
    raw = [p_['hop'] * (abs(math.sin(math.pi * 2 * (t / T - p_['hop_at']))) - 0.6)
           for t, p_ in ((t, seq[t]['p']) for t in range(N))]
    hop = follow(raw, seq[0]['p']['hop_rate'], seq[0]['p']['hop_damp'])
    hop = [max(-4.0, min(9.0, h)) for h in hop]
    # the weight: every touchdown presses the hips down and over the landing foot, then they rebound on a spring
    press, lean_in = [0.0] * N, [0.0] * N
    for n in range(4):
        st = step(cfg, gait, n)
        width = 0.35 * T
        for t in range(N):
            d = (t - st['td']) % N
            if d < width:
                bump = math.sin(math.pi * d / width) ** 2
                press[t] += st['p']['squash'] * (0.8 + 0.2 * gait['lk'][n % 4]) * bump
                lean_in[t] += (1 if st['leg'] == 'LH' else -1) * st['p']['sway'] * bump
    press = follow(press, 0.5, 0.45)
    lean_in = follow(lean_in, 0.5, 0.45)
    frames = []
    hist = {}
    for t in range(N):
        s = seq[t]
        p = s['p']
        ph = t / T
        pose = [list(r) for r in rest]
        pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, -v * t]
        up, uy, ur = s['torso']
        pose[TORSO][6] = round(rest[TORSO][6] + s['x'])
        pose[TORSO][7] = round(rest[TORSO][7] + s['y'] - hop[t] + press[t])
        Wt = {TORSO: rot([up, uy, ur])}
        Wh = rot([s['hips'][0] + 0.5 * press[t], s['hips'][1], s['hips'][2] + lean_in[t]])
        set_rot(pose, TORSO, Wt[TORSO], hist)
        set_rot(pose, SKIRT, mul(tr(Wt[TORSO]), Wh), hist)
        pose[SKIRT][6:9] = [round(x) for x in mv(tr(Wt[TORSO]), [0.0, hop[t], 0.0])]
        # the face guard keeps most of its gaze: it follows the torso by what `steady` leaves, and what it does comes late
        nod = harm(ph - 0.08, (p['nod'], 2, 0.2))
        Wg = rot([mean[0] + head_pitch[t] * (1 - p['steady']) * 0 + (head_pitch[t]) * (1 - p['steady']) + p['head'] + nod - (up - mean[0]) * 0,
                  0.5 * uy + p['look'] * math.sin(TAU * (ph / 2 - 0.1)),
                  head_roll[t] * 0.6 + 0.4 * ur])
        set_rot(pose, HEAD, mul(tr(Wt[TORSO]), Wg), hist)
        # both hands hold the shinai: the guard turns rigidly about the grip, carried by the torso on a spring
        G = rot([sw[0][t] * p['sword'] - p['hold'] * mean[0], sw[1][t] * p['sword'], sw[2][t] * p['sword']])
        guard_back = rot([-dev[0][t] * 0, -dev[1][t] * 0, -dev[2][t] * 0])
        pivot = [(rest[GUARD[0]][6 + i] + rest[GUARD[1]][6 + i]) / 2 for i in range(3)]
        lift = [0.0, ysw[t] * 0.8, 0.0]
        for sh in GUARD:
            base = mmd.rot_matrix(*rest[sh][3:6])
            set_rot(pose, sh, mul(G, base), hist)
            o = [rest[sh][6 + i] - pivot[i] for i in range(3)]
            pose[sh][6:9] = [pivot[i] + mv(G, o)[i] + lift[i] for i in range(3)]
        # shoulder plates and the tail trail the body
        for sd, b in zip((1, -1), PADS):
            pose[b][3] = rest[b][3] + round(p['pads'] * pad[t] * 0.5 * DEG)
            pose[b][5] = rest[b][5] + round(sd * p['pads'] * 0.3 * harm(ph - p['pad_lag'], (1, 2, 0.1)) * DEG)
        for k, b in enumerate(TAIL):
            d = p['tail_lag'] * (k + 1)
            pose[b][3] = rest[b][3] + round(p['tail'] * (0.5 + 0.2 * k) * harm(ph - d, (1, 2, 0.1)) * DEG)
            pose[b][4] = rest[b][4] + round(p['tail'] * 0.7 * math.sin(TAU * (ph - d - 0.1)) * DEG)
        # the legs: feet first, the thigh stub rides under the skirt to the ankle
        Rp = mul(tr(rot([0, 0, 0])), Wh)
        P = add([pose[TORSO][6], pose[TORSO][7], pose[TORSO][8]], mv(Wt[TORSO], pose[SKIRT][6:9]))
        for name, (th, ft, pl, side) in LEGS.items():
            A, Rf, R8, down = foot_at(kot, cfg, gait, name, t)
            A = [A[0], A[1], A[2] + v * t]                    # the root's frame at this tick
            # the thigh stub stays under the skirt: it slides by a few units at most and the leg turns to reach the foot
            F = kot.foot_rest[name]
            u0 = mv(F, rest[ft][6:9])
            want = mv(tr(Rp), sub(sub(A, u0), P))
            limits = (SLIDE[0], SLIDE[1], gait.get('slide', SLIDE[2]))
            slide = [max(-lim, min(lim, want[i] - rest[th][6 + i])) for i, lim in enumerate(limits)]
            pose[th][6:9] = [rest[th][6 + i] + round(slide[i]) for i in range(3)]
            H = add(P, mv(Rp, pose[th][6:9]))
            d = sub(A, H)
            nd = math.sqrt(sum(x * x for x in d)) or 1.0
            d = [x / nd for x in d]
            R6 = mul(align(u0, d, gait.get('tilt', MAX_TILT)), F)
            set_rot(pose, th, mul(tr(Rp), R6), hist)
            set_rot(pose, ft, mul(tr(R6), Rf), hist)
            set_rot(pose, pl, mul(tr(Rf), R8), hist)
        frames.append(pose)
    closing = [list(r) for r in frames[0]]
    closing[0][8] = -v * N
    frames.append(closing)
    return frames


# ------------------------------------------------------------------ build
def _played(animation, slot, ticks):
    player = mmd.AnimPlayer(animation, BONES, slot)
    played = []
    for _ in range(ticks * 3 + 1):
        assert player.tick()
        pose = [list(r) for r in player.pose]
        pose[0][6:9] = list(player.root)
        played.append(pose)
    return played, player.events


def floor_depth(kot, frames):
    """The lowest mesh point (largest y; the floor is 0) at each tick and its 60 fps thirds."""
    from motiontailspace import interpolate_pose
    worst = -1e9
    for t in range(len(frames) - 1):
        for alpha in (0, 1365, 2730):
            pose = interpolate_pose(frames[t], frames[t + 1], alpha)
            W = kot.world(pose)
            for b in kot.verts:
                if b in (21, 23):
                    continue
                R = [[W[b][i][j] for j in range(3)] for i in range(3)]
                worst = max(worst, W[b][1][3] + pose[0][7] + kot.dip(b, R))
    return worst


def build_clips(data, skeleton):
    """The three clips written into the reviewed imported model -> (bytes, report)."""
    digest = hashlib.sha256(data).hexdigest()
    if digest != SOURCE:
        raise ValueError('Kotemon gait requires the reviewed imported source')
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = BONES
    old = mmd.MMD.parse(data, BONES)
    old.type = SPECIES
    new = copy.deepcopy(old)
    kot = Kotemon(old)
    checks, changed = [], set()
    for slot, gait in sorted(GAITS.items()):
        cfg = dict(ticks=gait['ticks'], speed=gait['speed'], name=gait['name'])
        frames = build_frames(kot, cfg, gait)
        frames = [[[round(x) for x in bone] for bone in pose] for pose in frames]
        total = 2 * cfg['ticks']
        source_events = animsheet.slot_frames(old, BONES, slot)[2]
        sound = next((dict(e) for _, kind, e in source_events if kind == 'sound'), dict(op='sound', bank=1, note=13))
        events = [(t, kind, e) for t, kind, e in source_events if kind == 'tex' and t == 0]
        for n in range(4):
            tick = round(step(cfg, gait, n)['td']) % total
            events.append((tick, 'sound', dict(sound, frame=tick + 1)))
        events.sort(key=lambda e: e[0])
        animation = mmd.encode_anim(frames, BONES, loop_sample=0, events=events, tol=1)
        index = old.anims.table[slot]
        new.anims.anims[index] = animation
        changed |= {s for s, i in enumerate(old.anims.table) if i == index}
        played, _ = _played(animation, slot, total)
        for tick in range(total, total * 3 + 1, total):
            assert all(abs(a - b) <= 2 for bone, other in zip(played[0][1:], played[tick][1:]) for a, b in zip(bone, other)), (slot, tick, 'loop drift')
        loop = played[:total + 1]
        speed = abs(loop[-1][0][8] - loop[0][0][8]) / total
        low, high = {2: (15, 31), 3: (10, 20), 4: (35, 52)}[slot]
        assert low <= speed <= high, (slot, speed)
        floor = floor_depth(kot, loop)
        assert floor <= 3 or not STRICT, (slot, 'under the floor', floor)
        checks.append(dict(slot=slot, gait=cfg['name'], ticks=total, units_per_tick=round(speed, 2), lowest_point=round(floor, 1),
                           stream_bytes=len(animation.build()),
                           aliases=sorted(s for s, i in enumerate(old.anims.table) if i == index)))
    result = new.build()
    actual = mmd.MMD.parse(result, BONES)
    assert old.tmd.build() == actual.tmd.build()
    assert changed_programs(old, actual) == sorted(changed), (changed_programs(old, actual), sorted(changed))
    storage = motionstorage.require(result, BONES)
    return result, dict(species=SPECIES, source_sha256=digest, output_sha256=hashlib.sha256(result).hexdigest(),
                        changed_slots=sorted(changed), checks=checks, storage=storage, mesh_exact=True, other_programs_exact=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/351-kotemon.json').read_text())['model']['skeleton']
    data, report = build_clips(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(report, indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
