"""Deramon's field clips (species 286): a bird on planted feet carrying a flower shell that sways late behind it.

The rig is eight bones: the root (0), the shell (1, which is also the parent of every other bone: its pivot sits at the
front of the shell, at the bird's waist), the body (2), the right and left feet (3, 4: one rigid piece each, no leg
bones), the head with its crown and beak (5) and the right and left wings (6, 7). The imported clips pitched the feet
about their ankle by 45 to 70 degrees (so the sole, a grey texture of its own, faced the camera) while the feet stayed
where they were on the body, slid over the ground at the speed of the body and never lifted; the shell never moved
against the body because it is the body's parent.

Here every clip is written in the world and turned into local bone values at the end (`assemble`):

* the feet are placed, not solved: in stance a foot's sole is flat and still in the world while the root travels past it
  (slip is only the rounding of the stored values), in swing it lifts and travels to its next landing on a path of its
  own, the ankle height following its pitch so that the lowest point of the foot is the sole. Stance length is
  speed x ticks x duty, kept to about 125-145 units: the foot never strays far from the body;
* the body, head and wings move as one group about a point on the floor (roll over the loaded foot, a little yaw
  against the hips, lean, bob twice a cycle, sway), the head then steadies against it and bobs forward like a bird's, the
  wings swing against the foot of their side;
* the shell is the same group motion passed through a damped spring per harmonic (`spring`): it lags behind the body,
  rocks about its own centre by a few degrees, overshoots the bob, and never sinks into the floor (its lowest point is
  kept at the floor).

Every channel is a sum of a few cosines of the cycle phase with their own delays, so each clip loops exactly. Idle (slot
0, shared with slot 33): a 4 second loop with a slow breath, small look-arounds and the original blink. Walk (slot 2):
a waddle, 16 ticks at 16 units a tick. Tired walk (slot 3): 20 ticks at 10, lower, leaning forward, with a hanging
head and wings. Run (slot 4): 10 ticks at 38, a hop with both feet off the ground, leaning forward, wings swept up and
back, the shell bouncing behind. See tools/models/README.md.
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

TAU = 2 * math.pi
DEG = 4096 / 360
SPECIES = 286
SOURCE = '032754b6ebd489e6a143cfbd6c53c7c7f0570352a0ba6a408ce8a54a262e3ad3'
PARENTS = [-1, 0, 1, 1, 1, 1, 1, 1]
SHELL, BODY, FOOT_R, FOOT_L, HEAD, WING_R, WING_L = 1, 2, 3, 4, 5, 6, 7
SPEED_RANGE = {2: (15, 31), 3: (10, 20), 4: (35, 52)}
SHELL_FLOOR = 1.0       # the shell's lowest point may dip this far under the floor


# ------------------------------------------------------------------ small linear algebra
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


def rx(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def ry(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def rz(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def rpy(pitch, yaw, roll):
    """Pitch about x (positive: the top leans forward), yaw about y, roll about z (positive: the top leans right)."""
    return mul(ry(yaw), mul(rx(pitch), rz(roll)))


def harm(phase, terms, const=0.0):
    """const + sum of a cos(2 pi (k phase - delay)); terms are (amplitude, k, delay in cycles of the fundamental k=1)."""
    return const + sum(a * math.cos(TAU * (k * phase - delay)) for a, k, delay in terms)


def spring(terms, fn, zeta):
    """The steady response of a damped spring (natural frequency fn cycles per clip cycle) to a harmonic series:
    every harmonic is scaled and delayed by its transfer function, so the response is as periodic as the drive."""
    out = []
    for a, k, delay in terms:
        r = k / fn
        h = 1 / complex(1 - r * r, 2 * zeta * r)
        out.append((a * abs(h), k, delay + (-math.atan2(h.imag, h.real)) / TAU))
    return out


def smoothstep(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def jerk(u):
    u = max(0.0, min(1.0, u))
    return u ** 3 * (10 - 15 * u + 6 * u * u)


def set_rot(pose, b, m, hist):
    angle = mmd.matrix_euler(m, hist.get(b))
    hist[b] = angle
    pose[b][3:6] = [round(x) for x in angle]


# ------------------------------------------------------------------ the rig
class Rig:
    def __init__(self, model, skeleton):
        self.m, self.sk = model, skeleton
        self.rest = [list(v) for v in animsheet.slot_frames(model, 8, 0)[0][0]]
        self.verts = {b: [list(v[:3]) for v in model.tmd.obj_verts(o)] for b, (o, _) in enumerate(skeleton) if o >= 0}
        W = self.world(self.rest)
        self.R = [[row[:3] for row in W[b][:3]] for b in range(8)]
        self.P = [[W[b][i][3] for i in range(3)] for b in range(8)]
        shell = [add(self.P[SHELL], mv(self.R[SHELL], v)) for v in self.verts[SHELL]]
        self.centre = [sum(p[i] for p in shell) / len(shell) for i in range(3)]

    def world(self, pose):
        p = [list(v) for v in pose]
        p[0] = [4096] * 3 + [0] * 6
        return mmd.bone_matrices(self.m, p)

    def lowest(self, b, R, P):
        """Greatest y (the lowest point, y grows downwards) of bone b's mesh at a world rotation and position."""
        return max(P[1] + sum(R[1][k] * v[k] for k in range(3)) for v in self.verts[b])


def group(R, pivot, d, p):
    """A point carried by a rotation R about `pivot`, then moved by d."""
    return add(add(pivot, mv(R, sub(p, pivot))), d)


# ------------------------------------------------------------------ the clips
# Angles in degrees, lengths in game units. Each channel is (terms, const); terms as in `harm`.
def foot_path(cfg, name, phase):
    """A foot's pivot offset from its rest place (dz along the body's axis, dy lift, dx out) and its pitch, in the body's
    frame (the root travels, the stance foot goes back at the speed) -> (z, lift, out, pitch, stance)."""
    td = 0.0 if name == 'R' else 0.5
    d = cfg['duty']
    L = cfg['speed'] * cfg['ticks'] * d
    s = (phase - td) % 1.0
    zc = cfg['foot_z']
    if s < d:
        u = s / d
        return zc - L / 2 + L * u, 0.0, 0.0, 0.0, True
    q = (s - d) / (1 - d)
    # a short push-off before the foot leaves, then the swing: fast, then slowing down for the landing
    z0, z1 = zc + L / 2, zc - L / 2 - cfg.get('reach', 0)
    z = z0 + (z1 - z0) * jerk(q ** cfg.get('swing_ease', 0.9) if q < 1 else 1)
    z += cfg.get('tuck', 0) * math.sin(math.pi * min(1, q * 2)) * (1 - q)
    lift = cfg['lift'] * math.sin(math.pi * q ** cfg.get('arc', 0.85)) ** 0.9
    out = cfg['out'] * math.sin(math.pi * q)
    pitch = cfg['toe_off'] * (1 - smoothstep(q * 3)) - cfg['heel'] * smoothstep((q - 0.55) / 0.45) * (1 - smoothstep((q - 0.93) / 0.07))
    pitch += cfg['swing_pitch'] * math.sin(math.pi * q)
    return z, lift, out, pitch, False


def body_channels(cfg, phase):
    """The group motion of body, head and wings: pitch, yaw, roll (degrees), sway (x), bob (up, y), surge (z), in
    units where bob is up-positive."""
    c = cfg
    a = c['load']            # phase of mid-stance of the right foot
    roll = harm(phase, [(c['roll'], 1, a), (c['roll3'], 3, a + 0.04)], 0)
    sway = harm(phase, [(c['sway'], 1, a + c['sway_at']), (c['sway3'], 3, a + 0.1)], 0)
    yaw = harm(phase, [(-c['yaw'], 1, a + 0.01), (c['yaw3'], 3, a + 0.09)], 0)
    bob = harm(phase, [(c['bob'], 2, 2 * a + c['bob_at']), (c['bob2'], 4, 4 * a + c['bob_at'] + 0.09),
                       (c['bob_side'], 1, a + 0.19)], c['bob'] + c['bob2'] + c['bob_side'] + c['bob_const'])
    pitch = harm(phase, [(c['pitch'], 2, 2 * a + c['pitch_at']), (c['pitch1'], 1, a + 0.13)], c['lean'])
    surge = harm(phase, [(c['surge'], 2, 2 * a + 0.12), (c['surge1'], 1, a + 0.05)])
    return pitch, yaw, roll, sway, bob, surge


def shell_channels(cfg, phase):
    """The shell's motion relative to the group: (pitch, yaw, roll, sway, bob, surge) of the damped spring the group
    drives, minus the group's own; plus the shell's own slow rock."""
    c = cfg
    a = c['load']
    fn, zeta = c['shell_fn'], c['shell_zeta']
    g = c['shell_gain']
    drive = {
        'roll': [(c['roll'], 1, a), (c['roll3'], 3, a + 0.04)],
        'pitch': [(c['pitch'], 2, 2 * a + c['pitch_at']), (c['pitch1'], 1, a + 0.13)],
        'bob': [(c['bob'], 2, 2 * a + c['bob_at']), (c['bob2'], 4, 4 * a + c['bob_at'] + 0.09), (c['bob_side'], 1, a + 0.19)],
        'sway': [(c['sway'], 1, a + c['sway_at']), (c['sway3'], 3, a + 0.1)],
    }
    out = {}
    for key, terms in drive.items():
        mine = spring(terms, fn, zeta)
        rel = harm(phase, mine) - harm(phase, terms)
        out[key] = g * rel
    # a slow rock of its own, a little off the body's
    out['roll'] += harm(phase, [(c['shell_roll'], 1, a + 0.35), (c['shell_roll2'], 2, 2 * a + 0.1)])
    out['pitch'] += harm(phase, [(c['shell_pitch'], 1, a + 0.45), (c['shell_pitch2'], 2, 2 * a + 0.3)]) + c['shell_lean']
    return out


def head_channels(cfg, phase):
    """Head motion relative to the group: (pitch, yaw, roll, forward bob dz, dy)."""
    c = cfg
    a = c['load']
    yaw = harm(phase, [(c['head_yaw'], 1, a + c['head_yaw_at']), (c['head_yaw2'], 2, 2 * a + 0.05)]) + c['head_turn_const']
    pitch = harm(phase, [(c['head_nod'], 2, 2 * a + c['head_nod_at']), (c['head_nod1'], 1, a + 0.2)]) + c['head_drop']
    roll = harm(phase, [(c['head_roll'], 1, a + 0.02), (c['head_roll2'], 2, 2 * a + 0.12)])
    peck = harm(phase, [(c['peck'], 2, 2 * a + c['peck_at']), (c['peck2'], 4, 4 * a + c['peck_at'] + 0.06)])
    return pitch, yaw, roll, peck


def wing_channels(cfg, phase, side):
    """A wing's swing (about x, positive swings its tip back), abduction (about z, positive: outwards) and its lag."""
    c = cfg
    a = 0.0 if side == 'R' else 0.5      # a wing is back when the foot of its side is forward (at its touchdown)
    swing = harm(phase, [(c['wing'], 1, a + c['wing_at']), (c['wing2'], 2, 2 * a + c['wing_at'] + 0.1)], c['wing_back'])
    out = harm(phase, [(c['wing_out_a'], 2, 2 * a + c['wing_out_at']), (c['wing_out1'], 1, a + c['wing_at'] + 0.2)], c['wing_out'])
    return swing, out


def assemble(rig, cfg, phase, hist, tick_info=None):
    """The 8 local bone values of one tick, from the world poses of the shell, the group and the feet."""
    c = cfg
    pitch, yaw, roll, sway, bob, surge = body_channels(c, phase)
    # the group turns about a point on the floor under the body; `bob` is lift (up), so y decreases
    floor_pivot = [0.0, 0.0, c['pivot_z']]
    Ru = rpy(pitch, yaw, roll)
    du = [sway, -bob, surge]
    # shell: the group's motion, then its own relative motion about its centre
    sh = shell_channels(c, phase)
    # the shell only follows part of the body's forward lean (a shell tipped with the lean would lift its back off the floor)
    Rus = rpy(pitch - c['lean'] * (1 - c['shell_follow']), yaw, roll)
    c_after = group(Rus, floor_pivot, du, rig.centre)
    Rrel = rpy(sh['pitch'], 0.0, sh['roll'])
    drel = [sh['sway'], -sh['bob'], c['shell_back']]
    Rs = mul(Rrel, Rus)
    P1 = group(Rrel, c_after, drel, group(Rus, floor_pivot, du, rig.P[SHELL]))
    low = rig.lowest(SHELL, mul(Rs, rig.R[SHELL]), P1)
    if low > SHELL_FLOOR:
        P1 = [P1[0], P1[1] - (low - SHELL_FLOOR), P1[2]]
    Rw = {SHELL: mul(Rs, rig.R[SHELL])}
    Pw = {SHELL: P1}
    # body
    Rw[BODY] = mul(Ru, rig.R[BODY])
    Pw[BODY] = group(Ru, floor_pivot, du, rig.P[BODY])
    # head: steadied against the group, its own nod, turn and forward bob
    hp, hy, hr, peck = head_channels(c, phase)
    Rh = mul(Ru, mul(rpy(hp, hy, hr), tr(Ru)))
    Rw[HEAD] = mul(Rh, mul(Ru, rig.R[HEAD]))
    Pw[HEAD] = add(group(Ru, floor_pivot, du, rig.P[HEAD]), [0.0, -c['head_up'], -peck - c['head_fwd']])
    # wings
    for b, side, sign in ((WING_R, 'R', 1), (WING_L, 'L', -1)):
        swing, out = wing_channels(c, phase, side)
        Rwing = mul(Ru, mul(rpy(swing, 0.0, -sign * out), tr(Ru)))
        Rw[b] = mul(Rwing, mul(Ru, rig.R[b]))
        Pw[b] = group(Ru, floor_pivot, du, rig.P[b])
    # feet
    info = {}
    for b, name, sign in ((FOOT_R, 'R', 1), (FOOT_L, 'L', -1)):
        z, lift, out, p, stance = foot_path(c, name, phase)
        R = mul(rig.R[b], rx(p))
        P = [rig.P[b][0] + sign * (c['foot_out'] + out), 0.0, rig.P[b][2] + z]
        P[1] = -lift - rig.lowest(b, R, [0.0, 0.0, 0.0])    # the lowest point of the foot is `lift` above the floor
        Rw[b], Pw[b] = R, P
        info[name] = (z, lift, stance)
    pose = [[4096] * 3 + [0] * 6 for _ in range(8)]
    pose[0] = [4096] * 3 + [0] * 6
    set_rot(pose, SHELL, Rw[SHELL], hist)
    pose[SHELL][6:9] = [round(x) for x in Pw[SHELL]]
    # children: local = parent^-1 world, evaluated against the stored (rounded) shell so that rounding cannot add slip
    Rp = [[x for x in row] for row in mmd.rot_matrix(*pose[SHELL][3:6])]
    Pp = [float(x) for x in pose[SHELL][6:9]]
    for b in (BODY, FOOT_R, FOOT_L, HEAD, WING_R, WING_L):
        set_rot(pose, b, mul(tr(Rp), Rw[b]), hist)
        pose[b][6:9] = [round(x) for x in mv(tr(Rp), sub(Pw[b], Pp))]
    return pose, info


# ------------------------------------------------------------------ profiles
BASE = dict(
    pivot_z=0.0, foot_z=0.0, foot_out=0.0, out=3.0, reach=0.0, tuck=0.0, swing_ease=0.9, arc=0.85,
    toe_off=10.0, heel=8.0, swing_pitch=0.0,
    load=0.27, roll=4.0, roll3=0.5, sway=5.0, sway_at=0.0, sway3=0.6, yaw=3.0, yaw3=0.4,
    bob=3.0, bob2=0.8, bob_side=0.8, bob_const=0.0, bob_at=0.0, lean=0.0, pitch=1.0, pitch1=0.5, pitch_at=0.0,
    surge=1.0, surge1=0.8,
    shell_fn=3.0, shell_zeta=0.35, shell_gain=1.0, shell_roll=0.6, shell_roll2=0.3, shell_pitch=0.5, shell_pitch2=0.3,
    shell_lean=0.0, shell_follow=1.0, shell_back=0.0, head_up=0.0, head_fwd=0.0,
    head_yaw=4.0, head_yaw2=1.0, head_turn_const=0.0, head_yaw_at=0.0, head_nod=2.0, head_nod_at=0.1, head_nod1=0.8,
    head_drop=0.0, head_roll=2.0, head_roll2=0.5, peck=3.0, peck2=1.0, peck_at=0.2,
    wing=12.0, wing2=2.0, wing_at=0.0, wing_back=0.0, wing_out=3.0, wing_out_a=1.5, wing_out_at=0.1, wing_out1=1.0,
)

GAITS = {
    2: dict(BASE, name='walk', ticks=16, speed=16, duty=0.56, lift=26.0, out=4.0, foot_z=0.0, toe_off=10.0, heel=9.0,
            roll=5.0, sway=7.0, yaw=4.0, bob=3.5, bob_const=0.0, lean=2.0, pitch=1.2,
            shell_fn=2.6, shell_gain=1.0, head_yaw=5.0, head_nod=2.5, peck=3.5,
            wing=14.0, wing_back=4.0, wing_out=6.0),
    3: dict(BASE, name='tired walk', ticks=20, speed=10, duty=0.64, lift=15.0, out=3.0, foot_z=-4.0, toe_off=5.0, heel=5.0,
            roll=6.5, sway=8.0, yaw=3.0, bob=2.2, bob_const=0.0, lean=9.0, pitch=1.4, load=0.3,
            shell_fn=2.2, shell_zeta=0.5, shell_follow=0.15, shell_roll=1.0,
            head_drop=12.0, head_up=7.0, head_fwd=4.0, shell_back=3.0, head_yaw=3.0, head_nod=2.0, head_nod1=1.2, peck=1.5,
            wing=7.0, wing_back=-2.0, wing_out=1.0, wing_out_a=0.8),
    4: dict(BASE, name='run', ticks=10, speed=38, duty=0.30, lift=38.0, out=2.0, foot_z=-20.0, shell_back=4.0, toe_off=16.0, heel=6.0, tuck=12.0,
            roll=3.0, sway=4.0, yaw=3.0, bob=9.0, bob2=1.5, bob_side=0.6, bob_const=0.0, lean=12.0, pitch=2.0, pitch_at=0.1,
            load=0.17, bob_at=0.0, shell_fn=3.2, shell_zeta=0.3, shell_gain=1.4, shell_pitch=0.8, shell_follow=0.15,
            head_yaw=2.0, head_nod=3.0, head_drop=-8.0, peck=2.5, surge=2.0,
            wing=9.0, wing_back=8.0, wing_out=34.0, wing_out_a=5.0, wing_out1=2.0),
}

IDLE = dict(ticks=120, breath=2.4, breath_pitch=1.0, sway=2.4, yaw=1.6, roll=1.2, shell_fn=1.6, shell_zeta=0.5,
            head_yaw=11.0, head_pitch=3.5, head_roll=2.2, wing=4.5, wing_out=2.6)
BLINKS = (38, 92)


def idle_pose(rig, phase, hist):
    """One tick of the calm idle: the feet stay where the rest pose put them (the standing foot is exact: no entry in
    foot_path), the group breathes and settles, the head looks about slowly, the wings hang and sway late, the shell
    follows the body through the spring."""
    c = dict(BASE, **{k: 0.0 for k in ('roll', 'roll3', 'sway', 'sway3', 'yaw', 'yaw3', 'bob', 'bob2', 'bob_side', 'pitch',
                                       'pitch1', 'surge', 'surge1', 'head_yaw', 'head_yaw2', 'head_nod', 'head_nod1',
                                       'head_roll', 'head_roll2', 'peck', 'peck2', 'wing', 'wing2', 'wing_out',
                                       'wing_out_a', 'wing_out1', 'shell_roll', 'shell_roll2', 'shell_pitch', 'shell_pitch2')})
    i = IDLE
    breath = harm(phase, [(1.0, 2, 0.0), (0.25, 4, 0.08)], 1.25)       # up and down twice a loop, with a quick second part
    sway = harm(phase, [(1.0, 1, 0.2), (0.3, 3, 0.4)])
    drive = {
        'roll': [(i['roll'], 1, 0.2), (i['roll'] * 0.4, 3, 0.55)],
        'pitch': [(i['breath_pitch'], 2, 0.05)],
        'bob': [(i['breath'] / 2.25 * 1.0, 2, 0.0), (i['breath'] / 9, 4, 0.08)],
        'sway': [(i['sway'], 1, 0.2), (i['sway'] * 0.3, 3, 0.4)],
    }
    Ru = rpy(harm(phase, drive['pitch']), harm(phase, [(i['yaw'], 1, 0.35), (i['yaw'] * 0.4, 3, 0.1)]), harm(phase, drive['roll']))
    bob = harm(phase, drive['bob'], i['breath'] / 2.25 + i['breath'] / 9)
    du = [harm(phase, drive['sway']), -bob, 0.0]
    pivot = [0.0, 0.0, 0.0]
    # shell through the spring (relative motion only) plus its slow rock
    rel = {k: 1.3 * (harm(phase, spring(t, i['shell_fn'], i['shell_zeta'])) - harm(phase, t)) for k, t in drive.items()}
    rock_r = harm(phase, [(0.7, 1, 0.45), (0.3, 2, 0.2)])
    rock_p = harm(phase, [(0.6, 1, 0.1), (0.25, 3, 0.3)])
    c_after = group(Ru, pivot, du, rig.centre)
    Rrel = rpy(rel['pitch'] + rock_p, 0.0, rel['roll'] + rock_r)
    Rs = mul(Rrel, Ru)
    P1 = group(Rrel, c_after, [rel['sway'], -rel['bob'], 0.0], group(Ru, pivot, du, rig.P[SHELL]))
    low = rig.lowest(SHELL, mul(Rs, rig.R[SHELL]), P1)
    if low > SHELL_FLOOR:
        P1 = [P1[0], P1[1] - (low - SHELL_FLOOR), P1[2]]
    Rw, Pw = {SHELL: mul(Rs, rig.R[SHELL])}, {SHELL: P1}
    Rw[BODY], Pw[BODY] = mul(Ru, rig.R[BODY]), group(Ru, pivot, du, rig.P[BODY])
    # head: a look to one side, back, the other, a small nod and tilt, each at its own rate; steadied against the body
    yaw = harm(phase, [(i['head_yaw'], 1, 0.12), (i['head_yaw'] * 0.45, 2, 0.3), (i['head_yaw'] * 0.2, 3, 0.65)])
    nod = harm(phase, [(i['head_pitch'], 2, 0.15), (i['head_pitch'] * 0.5, 1, 0.5)])
    roll = harm(phase, [(i['head_roll'], 1, 0.3), (i['head_roll'] * 0.4, 3, 0.2)])
    Rh = mul(Ru, mul(rpy(nod, yaw, roll), tr(Ru)))
    Rw[HEAD], Pw[HEAD] = mul(Rh, mul(Ru, rig.R[HEAD])), group(Ru, pivot, du, rig.P[HEAD])
    # wings hang and sway a little behind the body, the two sides out of step
    for b, sign, off in ((WING_R, 1, 0.0), (WING_L, -1, 0.17)):
        swing = harm(phase, [(i['wing'], 1, 0.3 + off), (i['wing'] * 0.4, 2, 0.1 + off), (i['wing'] * 0.25, 3, 0.55 + off)])
        out = harm(phase, [(i['wing_out'], 2, 0.4 + off), (i['wing_out'] * 0.5, 1, 0.1 + off)], i['wing_out'] * 1.2)
        Rw[b] = mul(mul(Ru, mul(rpy(swing, 0.0, -sign * out), tr(Ru))), mul(Ru, rig.R[b]))
        Pw[b] = group(Ru, pivot, du, rig.P[b])
    for b in (FOOT_R, FOOT_L):
        Rw[b], Pw[b] = rig.R[b], rig.P[b]
    pose = [[4096] * 3 + [0] * 6 for _ in range(8)]
    set_rot(pose, SHELL, Rw[SHELL], hist)
    pose[SHELL][6:9] = [round(x) for x in Pw[SHELL]]
    Rp = mmd.rot_matrix(*pose[SHELL][3:6])
    Pp = [float(x) for x in pose[SHELL][6:9]]
    for b in (BODY, FOOT_R, FOOT_L, HEAD, WING_R, WING_L):
        set_rot(pose, b, mul(tr(Rp), Rw[b]), hist)
        pose[b][6:9] = [round(x) for x in mv(tr(Rp), sub(Pw[b], Pp))]
    return pose


def clip(rig, cfg):
    ticks, speed = cfg['ticks'], cfg['speed']
    hist = {}
    frames = []
    for t in range(ticks):
        pose, _ = assemble(rig, cfg, t / ticks, hist)
        pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, -speed * t]
        frames.append(pose)
    closing = [list(b) for b in frames[0]]
    closing[0][8] = -speed * ticks
    frames.append(closing)
    return frames


def idle_clip(rig):
    ticks = IDLE['ticks']
    hist = {}
    frames = [idle_pose(rig, t / ticks, hist) for t in range(ticks)]
    frames.append([list(b) for b in frames[0]])
    return frames


def blink_events(source, ticks):
    """The model's own blink (half shut, shut, half, open: four texture moves), at the ticks of BLINKS."""
    tex = [(t, e) for t, kind, e in source if kind == 'tex']
    first = tex[0]
    seq = tex[1:]
    out = [(first[0], 'tex', dict(first[1], frame=first[0] + 1))]
    base = seq[0][0]
    for at in BLINKS:
        for t, e in seq:
            tick = at + t - base
            assert 0 < tick < ticks
            out.append((tick, 'tex', dict(e, frame=tick + 1)))
    return out


def build(data, skeleton=None):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('Deramon\'s gaits require the reviewed source')
    skeleton = skeleton or json.loads((ROOT / 'content/species/286-deramon.json').read_text())['model']['skeleton']
    if [b[1] for b in skeleton] != PARENTS:
        raise ValueError('Deramon rig differs')
    n = len(skeleton)
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = n
    old = mmd.MMD.parse(data, n)
    old.type = SPECIES
    new = copy.deepcopy(old)
    rig = Rig(old, skeleton)
    changed = set()
    report = []

    def store(slot, frames, events):
        frames = [[[round(x) for x in bone] for bone in pose] for pose in frames]
        animation = mmd.encode_anim(frames, n, loop_sample=0, events=sorted(events, key=lambda e: e[0]), tol=0 if slot == 0 else 1)
        index = old.anims.table[slot]
        new.anims.anims[index] = animation
        group_ = sorted(s for s, i in enumerate(old.anims.table) if i == index)
        changed.update(group_)
        report.append(dict(slot=slot, ticks=len(frames) - 1, stream_bytes=len(animation.build()), aliases=group_))

    store(0, idle_clip(rig), blink_events(animsheet.slot_frames(old, n, 0)[2], IDLE['ticks']))
    for slot, cfg in sorted(GAITS.items()):
        source = animsheet.slot_frames(old, n, slot)[2]
        events = [(t, k, e) for t, k, e in source if k == 'tex' and t == 0]
        sounds = [e for _, k, e in source if k == 'sound']
        if slot == 3:       # a single sound of its own (bank 3, note 52), once a loop
            at = round(source[0][0] * cfg['ticks'] / 22) if source and source[0][1] == 'sound' else 9
            events += [(at, 'sound', dict(sounds[0], frame=at + 1))]
        else:
            for tick in (0, cfg['ticks'] // 2):      # the two touchdowns
                events.append((tick, 'sound', dict(sounds[0], frame=tick + 1)))
        store(slot, clip(rig, cfg), events)
    result = new.build()
    actual = mmd.MMD.parse(result, n)
    assert old.tmd.build() == actual.tmd.build()
    assert changed_programs(old, actual) == sorted(changed), (changed_programs(old, actual), sorted(changed))
    storage = motionstorage.require(result, n)
    return result, dict(species=SPECIES, source_sha256=SOURCE, output_sha256=hashlib.sha256(result).hexdigest(),
                        changed_slots=sorted(changed), clips=report, storage=storage, mesh_exact=True,
                        other_programs_exact=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    data, proof = build(a.source.read_bytes())
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
