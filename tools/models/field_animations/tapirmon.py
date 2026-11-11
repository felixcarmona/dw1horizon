"""Tapirmon's field clips (species 287): a calm idle, a diagonal walk, a heavy tired walk and a trot, planted foot by foot.

The rig (21 bones, forward is -z): bone 1 is the body (everything hangs from it), 2 the rear block (its own bone, a child
of 1 at the same point: it flexes and flicks like a tail), 13 the head with 14 the short snout and 15/16 the ears (right
x>0, left x<0). There are no knee or paw bones on the four legs: each is two bones that hang from the body, an upper leg
(front 17 right / 19 left, hind 8 right / 3 left) and a lower leg that reaches the floor (front 18/20, hind 9/4), the hind
lower leg carrying a long rear foot plate (10-12 right, 5-7 left) that points backwards. The imported clips swung the upper
legs without ever planting a sole: the feet slid (204/77 % of the body's travel in the walk) and the tired walk turned the
head sideways.

Here every leg is solved from the floor up. The sole of a lower leg is the target (a point in the world that stays put
while the body passes over it); the upper and the lower bone are aimed at it with a two-link solve on the model's own
lengths (upper 74, lower 49), the knee bending forward on the front legs and backwards on the hind ones. In stance the
upper bone may stretch a few units (it overlaps the lower bone's mesh by 16) so the lower leg stays close to upright; the
hind foot plate counter-rotates to lie flat. The body bobs, pitches, rolls and shifts its weight over the planted feet,
the head nods and follows late, the snout swings after the head, the ears and the rear block follow the body late. All
loops are integer-tick and every motion is a sum of harmonics of the cycle, so they close on themselves. See
tools/models/README.md.

    python tools/models/field_animations/tapirmon.py --source SRC.MMD --out OUT.MMD
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
from tools.models.field_animations.quadruped import (  # noqa: E402
    DEG, add, cross, dot, minimum_jerk, mul, norm, rot, scale, set_rot, smooth, sub, tr, turn_to, unit)

SPECIES = 287
SOURCE = 'ee0d0add7ba51da37b5746a021e403dfe8986908043202a3829eccdaa5bbfc97'
PARENTS = [-1, 0, 1, 1, 3, 4, 5, 6, 1, 8, 9, 10, 11, 1, 13, 13, 13, 1, 17, 1, 19]
TAU = 2 * math.pi
SPEED_RANGE = {2: (15, 31), 3: (10, 20), 4: (35, 52)}
FLOOR = 3
BODY, REAR, HEAD, SNOUT, EAR_R, EAR_L = 1, 2, 13, 14, 15, 16
# right side +x; (upper, lower, side, front, bones that touch the floor, rear foot plate or None)
LEGS = {'RF': (17, 18, 1, True, (18,), None), 'LF': (19, 20, -1, True, (20,), None),
        'RH': (8, 9, 1, False, (9, 10, 11, 12), 10), 'LH': (3, 4, -1, False, (4, 5, 6, 7), 5)}
SOLE = {True: [0.0, 49.0, -8.0], False: [0.0, 49.0, -9.0]}      # where a lower leg stands, in its own space
TRACK = {True: 44.0, False: 63.0}
POLE = {True: [0.0, 0.0, -1.0], False: [0.0, 0.0, 1.0]}
SHRINK, STRETCH = 9.0, 4.0     # the upper bone may shrink (into the lower mesh, which overlaps it by 16) or stretch this much in stance
IDLE_TICKS = 64
REACH = 115.0       # how far a hip may be from a sole that is not flat on the floor (the two links are 123 long)


def harm(phase, *terms):
    """A sum of cosines: terms are (amplitude, rate, delay in cycles)."""
    return sum(a * math.cos(TAU * rate * (phase - delay)) for a, rate, delay in terms)


def bump(phase, centre, width):
    """A smooth periodic pulse (0..1) centred on `centre`, as wide as `width` cycles."""
    d = (phase - centre + 0.5) % 1.0 - 0.5
    return math.cos(math.pi * d / width) ** 2 if abs(d) < width / 2 else 0.0


def rotpow(m, k):
    """A rotation matrix taken to the fraction k of its angle."""
    c = max(-1.0, min(1.0, (m[0][0] + m[1][1] + m[2][2] - 1) / 2))
    a = math.acos(c)
    if a < 1e-9:
        return [[1.0 if i == j else 0.0 for j in range(3)] for i in range(3)]
    ax = unit([m[2][1] - m[1][2], m[0][2] - m[2][0], m[1][0] - m[0][1]])
    s, t = math.sin(a * k), math.cos(a * k)
    kx = [[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]]
    return [[t * (i == j) + s * kx[i][j] + (1 - t) * ax[i] * ax[j] for j in range(3)] for i in range(3)]


class Rig:
    def __init__(self, model, skeleton):
        self.m, self.sk, self.n = model, skeleton, len(skeleton)
        self.rest = [list(v) for v in animsheet.slot_frames(model, self.n, 0)[0][0]]
        self.verts = {b: [list(v[:3]) for v in model.tmd.obj_verts(o)] for b, (o, _) in enumerate(skeleton) if o >= 0}

    def world(self, pose):
        p = [list(v) for v in pose]
        p[0] = [4096, 4096, 4096] + p[0][3:6] + [0, 0, 0]
        return mmd.bone_matrices(self.m, p)

    def lowest(self, W, bones):
        """Largest y (the lowest point) of the given bones' meshes."""
        best = -1e9
        for b in bones:
            M = W[b]
            for v in self.verts[b]:
                best = max(best, M[1][0] * v[0] + M[1][1] * v[1] + M[1][2] * v[2] + M[1][3])
        return best


def stance_of(cfg, name, phase):
    u = (phase - cfg['td'][name]) % 1.0
    return (True, u / cfg['duty']) if u < cfg['duty'] else (False, (u - cfg['duty']) / (1 - cfg['duty']))


def breath(p):
    """One breath, 0 (empty) to 1 (full): a quicker inhale, a short hold, a slower exhale, a short rest."""
    p %= 1.0
    if p < 0.34:
        return smooth(p / 0.34)
    if p < 0.42:
        return 1.0
    if p < 0.92:
        return 1.0 - smooth((p - 0.42) / 0.5)
    return 0.0


def body_pose(rig, cfg, phase, pose, hist, ofs=0.0, bphase=None):
    """The body, rear block, head, snout and ears of one tick (the legs are placed after it)."""
    rest = rig.rest
    c = cfg
    bob = harm(phase, (c['bob'], 2, c['high']), (c['bob'] * c['bob2'], 4, c['high'] + 0.02), (c['bob_side'], 1, c['high'] + 0.15))
    roll = harm(phase, (c['roll'], 1, c['roll_at']), (c['roll2'], 3, c['roll_at'] + 0.07))
    yaw = harm(phase, (c['yaw'], 1, c['yaw_at']), (c['yaw2'], 2, c['yaw_at'] + 0.1))
    pitch = c['tilt'] + harm(phase, (c['pitch'], 2, c['pitch_at']), (c['pitch1'], 1, c['pitch_at'] + 0.2), (c['pitch3'], 4, c['pitch_at'] + 0.05))
    shift = harm(phase, (c['shift'], 1, c['roll_at'] + 0.03), (c['shift2'], 3, c['roll_at'] + 0.12))
    B = cfg.get('breath')
    if B and bphase is not None:
        br = lambda lag=0.0: breath(bphase + B['at'] - lag) - 0.5
        pitch -= B['chest'] * br()                    # the chest rises on the inhale (nose up)
    pose[BODY][6] = rest[BODY][6] + shift
    pose[BODY][7] = rest[BODY][7] + ofs - bob
    set_rot(pose, BODY, mul(mmd.rot_matrix(*rest[BODY][3:6]), rot([pitch, yaw, roll])), hist)
    # the rear block flexes a little behind the body and flicks sideways like a tail
    flex = c.get('rear1', 0.0) * math.cos(TAU * (phase - c.get('rear1_at', 0.0))) + (B['flank'] * br(0.04) if B and bphase is not None else 0.0) + harm(phase, (c['rear'], 2, c['pitch_at'] + c['rear_lag']), (c['rear'] * 0.4, 4, c['pitch_at'] + c['rear_lag'] + 0.06))
    flick = harm(phase, (c['flick'], 1, 0.3), (c['flick'] * 0.5, 2, 0.45)) + c.get('flick_extra', lambda p: 0.0)(phase)
    set_rot(pose, REAR, mul(mmd.rot_matrix(*rest[REAR][3:6]), rot([flex + c.get('rear_tilt', 0.0), flick, -0.4 * roll])), hist)
    # head: keeps most of its gaze while the body pitches, nods a little, looks about with the cycle, follows late
    h = c['head']
    hp = c['head_tilt'] + harm(phase, (h['nod'], 2, c['pitch_at'] + h['lag']), (h['nod'] * 0.35, 4, c['pitch_at'] + h['lag'] + 0.05), (h['nod1'], 1, h['lag'] + 0.3)) \
        - h['steady'] * (pitch - c['tilt']) + h.get('extra', lambda p: 0.0)(phase)
    hy = harm(phase, (h['yaw'], 1, h['yaw_at']), (h['yaw2'], 2, h['yaw_at'] + 0.2)) - h['against'] * yaw + h.get('look', lambda p: 0.0)(phase)
    hr = harm(phase, (h['roll'], 1, h['yaw_at'] + 0.1)) - 0.5 * roll
    if B and bphase is not None:
        hp -= B['head'] * br(B['lag'])                # the head follows the chest a little late
        pose[REAR][1] = round(4096 * (1 + B['belly'] * (br(0.03) + 0.5)))   # the flanks swell
    set_rot(pose, HEAD, mul(mmd.rot_matrix(*rest[HEAD][3:6]), rot([hp, hy, hr])), hist)
    sn = c['snout']
    sp = harm(phase, (sn['pitch'], 2, c['pitch_at'] + h['lag'] + sn['lag']), (sn['pitch'] * 0.4, 4, c['pitch_at'] + h['lag'] + sn['lag'] + 0.04)) \
        + sn.get('sniff', lambda p: 0.0)(phase) + sn['down'] + (-B['snout'] * br(B['lag'] + 0.04) if B and bphase is not None else 0.0)
    sy = harm(phase, (sn['yaw'], 1, h['yaw_at'] + sn['lag'] + 0.1))
    set_rot(pose, SNOUT, mul(mmd.rot_matrix(*rest[SNOUT][3:6]), rot([sp, sy, 0])), hist)
    e = c['ears']
    for bone, side, off in ((EAR_R, 1, 0.0), (EAR_L, -1, 0.07)):
        fl = harm(phase, (e['flap'], 2, c['pitch_at'] + e['lag'] + off), (e['flap'] * 0.4, 4, c['pitch_at'] + e['lag'] + off + 0.05))
        sway = harm(phase, (e['sway'], 1, 0.2 + off))
        tw = e.get('twitch', lambda p, s: 0.0)(phase, side)
        # z roll swings the leaf out (+) or in; x pitch folds it back
        set_rot(pose, bone, mul(mmd.rot_matrix(*rest[bone][3:6]), rot([e['back'] + 0.5 * fl + 0.6 * tw, 0, side * (e['out'] + fl + sway) + side * tw])), hist)


def flat_rotation(front, pitch):
    """The lower leg's world rotation when the foot stands: upright, pitched by the given degrees (the toes stay down)."""
    return rot([pitch, 0, 0])


def knee_flat(P, front, pitch):
    return sub(P, mv(flat_rotation(front, pitch), SOLE[front]))


def mv(a, v):
    return [sum(a[i][k] * v[k] for k in range(3)) for i in range(3)]


def place_legs(rig, cfg, phase, pose, hist, targets, report):
    """Aim every leg at its sole target (a world point); targets: name -> (point, stance weight, foot curl, foot pitch).

    A standing leg keeps its lower bone upright (pitched by the foot pitch) with the knee over the sole and the upper bone
    stretched a few units to reach it, so the sole lies flat and still; when that does not reach (or in the air) the two
    links are solved to the sole with a knee bend, and the two answers are blended."""
    W = rig.world(pose)
    rest = rig.rest
    Rp = [[W[BODY][i][j] for j in range(3)] for i in range(3)]
    for name, (up, lo, side, front, group, plate) in LEGS.items():
        P, w, curl, fpitch = targets[name]
        hip = [W[up][i][3] for i in range(3)]
        a = rest[lo][6:9]
        La0 = norm(a)
        s = SOLE[front]
        Lb = norm(s)
        pole = POLE[front]
        d = sub(P, hip)
        r0 = norm(d)
        r = max(abs(La0 - Lb) + 2, min(La0 + Lb - 0.5, r0))
        u = unit(d)
        along = (La0 * La0 - Lb * Lb + r * r) / (2 * r)
        h = math.sqrt(max(0.0, La0 * La0 - along * along))
        pp = unit(sub(pole, scale(u, dot(pole, u))))
        knee_ik = add(hip, add(scale(u, along), scale(pp, h)))
        Rl_ik = turn_to(s, sub(P, knee_ik))
        Rl_flat = flat_rotation(front, fpitch)
        kf = knee_flat(P, front, fpitch)
        err = norm(sub(kf, hip)) - La0
        q = 1.0 - smooth(max(err - STRETCH, -err - SHRINK, 0.0) / 5.0)
        m = w * q
        knee = add(scale(knee_ik, 1 - m), scale(kf, m))
        Rl = mul(Rl_ik, rotpow(mul(tr(Rl_ik), Rl_flat), m)) if m > 0 else Rl_ik
        if (r0 - r) * (1 - m) > report['over']:
            report['over'], report['where'] = (r0 - r) * (1 - m), (name, round(phase, 2), round(m, 2), round(r0))
        La = norm(sub(knee, hip))
        report['stretch'] = max(report['stretch'], abs(La - La0))
        Ru = turn_to(a, sub(knee, hip))
        set_rot(pose, up, mul(tr(Rp), Ru), hist)
        pose[lo][6:9] = [x * La / La0 for x in a]
        set_rot(pose, lo, mul(tr(Ru), Rl), hist)
        if plate is not None:      # the rear foot plate lies flat on the floor, curling up in the air
            set_rot(pose, plate, mul(mul(tr(Rl), rot([curl, 0, 0])), mmd.rot_matrix(*rest[plate][3:6])), hist)


def gait_clip(rig, cfg):
    """The ticks of a walking clip (cycle ticks + 1 closing frame)."""
    N, v = cfg['ticks'], cfg['speed']
    R = cfg.get('repeat', 1)          # gait cycles per loop: a breath is longer than a stride
    rest = rig.rest
    still = rig.world([[4096, 4096, 4096, 0, 0, 0, 0, 0, 0]] + [list(r) for r in rest[1:]])
    centre = {}
    for name, (up, lo, side, front, group, plate) in LEGS.items():
        key = 'front' if front else 'hind'
        centre[name] = still[up][2][3] + SOLE[front][2] + cfg['reach'][key] + cfg.get('leg_reach', {}).get(name, 0)
    stride = v * N * cfg['duty']
    report = dict(over=0.0, stretch=0.0)
    hist = {}

    def targets_at(t, dy):
        phase = t / N
        targets = {}
        for name, (up, lo, side, front, group, plate) in LEGS.items():
            key = 'front' if front else 'hind'
            st, s = stance_of(cfg, name, phase)
            x = side * (TRACK[front] + cfg['track'][key])
            if st:
                z = centre[name] - stride / 2 + stride * s
                w = smooth(s / cfg['ramp']) * smooth((1 - s) / cfg['ramp'])
                peel = cfg['peel'][key] * smooth((s - 0.6) / 0.4) - cfg['heel'] * (1 - smooth(s / 0.25))
                targets[name] = ([x, dy[name], z], w, 0.0, peel)
                continue
            T = N * (1 - cfg['duty'])
            z0, z1 = centre[name] + stride / 2, centre[name] - stride / 2
            # the foot is still in the world until it has left the floor, then covers the distance and lands braking
            e = (s - cfg['delay']) / (cfg['land'] - cfg['delay'])
            ease = (1 - cfg['jerk']) * smooth(e) + cfg['jerk'] * minimum_jerk(e)
            lf = cfg.get('leg_lift', {}).get(name, 1.0)
            cv = cfg.get('carry', 1.0) * v * T      # how much of the body's travel the airborne foot lags behind (a gallop's feet stay with the body)
            z = z0 + ((z1 - z0) - cv) * ease + cv * s
            z -= cfg['out'][key] * 6.75 * s * s * (1 - s) * lf
            y = dy[name] - cfg['lift'][key] * lf * smooth(s / cfg['rise']) * smooth((1 - s) / cfg['fall'])
            x += side * cfg['wide'][key] * math.sin(math.pi * s)
            targets[name] = ([x, y, z], 0.0, cfg['curl'] * math.sin(math.pi * s) * smooth((1 - s) / 0.3), 0.0)
        return targets

    def solve_drop(t, dy):
        """The body height (an offset from the rest height) at which every standing leg's upper bone reaches its flat foot."""
        pose = [list(r) for r in rest]
        body_pose(rig, cfg, (t % N) / N, pose, {}, ofs=0.0, bphase=t / (N * R))
        W = rig.world(pose)
        targets = targets_at(t % N, dy)
        legs = []
        for name, (up, lo, side, front, group, plate) in LEGS.items():
            P, w, curl, fpitch = targets[name]
            hip = [W[up][i][3] for i in range(3)]
            legs.append((hip, knee_flat(P, front, fpitch), norm(rest[lo][6:9]), P, w < 0.5))
        best, best_score = None, 9e9
        for k in range(-60, 61):
            d = k * 0.5
            worst = 0.0
            for hip, kf, La0, P, air in legs:
                h = [hip[0], hip[1] + d, hip[2]]
                e = norm(sub(kf, h)) - La0
                worst = max(worst, (norm(sub(P, h)) - REACH) if air else max(e - STRETCH * 0.85, -e - SHRINK * 0.85))
            score = worst * 100 + abs(d - cfg['drop']) * 0.1 + (0 if worst <= 0 else 1000)
            if score < best_score:
                best, best_score = d, score
        return best

    def tick(t, dy, ofs):
        phase = (t % N) / N
        pose = [list(r) for r in rest]
        pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, -round(v * t)]
        body_pose(rig, cfg, phase, pose, hist, ofs=ofs, bphase=t / (N * R))
        place_legs(rig, cfg, phase, pose, hist, targets_at(t % N, dy), report)
        return pose

    M = N * R
    dy = [{n: 0.0 for n in LEGS} for _ in range(M)]
    drops = [cfg['drop']] * M
    for it in range(4):
        raw = [solve_drop(t, dy[t]) for t in range(M)]
        for _ in range(cfg.get('smooth', 1)):
            raw = [(raw[t - 1] + 2 * raw[t] + raw[(t + 1) % M]) / 4 for t in range(M)]
        drops = raw
        hist.clear()
        for t in range(M):
            pose = tick(t, dy[t], drops[t])
            W = rig.world(pose)
            for name, (up, lo, side, front, group, plate) in LEGS.items():
                low = rig.lowest(W, plate_group(name))
                if stance_of(cfg, name, (t % N) / N)[0]:
                    dy[t][name] -= low
                elif low > -cfg['clear']:
                    dy[t][name] -= low + cfg['clear']      # a foot in the air never dips under the floor
    hist.clear()
    frames = [tick(t, dy[t], drops[t]) for t in range(M)]
    report['drops'] = [round(x, 1) for x in drops]
    closing = [list(r) for r in frames[0]]
    closing[0][8] = -round(v * N * R)
    frames.append(closing)
    return frames, report


def plate_group(name):
    """The bones whose lowest point is the foot's: the rear plate (not the shin) behind, the lower leg in front."""
    up, lo, side, front, group, plate = LEGS[name]
    return group if front else group[1:]


# ------------------------------------------------------------------ the clips
def sniff(phase):
    """Two short bursts of quick small snout pitch a cycle."""
    return (3.5 * bump(phase, 0.62, 0.18) * math.cos(TAU * 4 * phase) + 2.5 * bump(phase, 0.85, 0.12) * math.cos(TAU * 3 * phase + 1.0))


def look(phase):
    """The head turns to one side, holds, comes back, then glances the other way a little."""
    return 8.0 * bump(phase, 0.30, 0.2) - 4.5 * bump(phase, 0.78, 0.13)


def ear_twitch(phase, side):
    """A quick soft flick of one ear (the right early, the left later) with a short ring-out."""
    centre, amp = (0.18, 4.5) if side > 0 else (0.52, 4.0)
    return amp * bump(phase, centre, 0.06) * math.cos(TAU * 5 * (phase - centre))


def tail_flick(phase):
    """The rear block swishes once, with a smaller echo."""
    return 7.0 * bump(phase, 0.42, 0.11) * math.sin(TAU * 2 * (phase - 0.42)) + 3.5 * bump(phase, 0.9, 0.08) * math.sin(TAU * 2 * (phase - 0.9))


COMMON = dict(peel={'front': 6, 'hind': 0}, heel=0, reach={'front': 0.0, 'hind': 0.0}, track={'front': 0.0, 'hind': 0.0}, lift={'front': 14, 'hind': 14}, out={'front': 3, 'hind': 3},
              wide={'front': 3, 'hind': 5}, curl=18, delay=0.2, land=0.78, rise=0.2, fall=0.2, jerk=0.3, ramp=0.05, clear=1.5, drop=0, bob=0.8, bob2=0.2, bob_side=0.3, high=0.0,
              roll=2, roll2=0.4, roll_at=0.0, yaw=2, yaw2=0.5, yaw_at=0.2, tilt=0, pitch=0.8, pitch1=0.4, pitch3=0.15, pitch_at=0.1,
              shift=3, shift2=0.5, rear=1.5, rear_lag=0.1, flick=2.5, head_tilt=0,
              head=dict(nod=2.5, lag=0.1, nod1=0.8, steady=0.6, yaw=3, yaw_at=0.1, yaw2=1.0, against=0.6, roll=1.5),
              snout=dict(pitch=3, lag=0.1, yaw=3, down=0),
              ears=dict(flap=5, lag=0.12, sway=2.5, back=0, out=0))
WALK = dict(COMMON, repeat=3, breath=dict(at=0.15, chest=1.6, head=1.2, snout=2.0, flank=1.2, belly=0.03, lag=0.06), name='walk', ticks=9, speed=16, duty=0.52, steps=('LH', 'RF', 'RH', 'LF'), drop=3,
            td={'LH': 0.0, 'RF': 0.06, 'RH': 0.5, 'LF': 0.56})
TIRED = dict(COMMON, repeat=3, breath=dict(at=0.35, chest=1.3, head=3.0, snout=7.0, flank=3.0, belly=0.05, lag=0.07), ears=dict(COMMON['ears'], back=0, out=22, flap=2), head_tilt=14, rear_tilt=-6, bob=1.2, pitch=0.5, roll=3, name='tired walk', ticks=13, speed=10, duty=0.62, steps=('LH', 'RF', 'RH', 'LF'), drop=14,
             td={'LH': 0.0, 'RF': 0.1, 'RH': 0.5, 'LF': 0.6})
RUN = dict(COMMON, repeat=1, breath=dict(at=0.6, chest=0.0, head=0.8, snout=2.5, flank=1.0, belly=0.025, lag=0.05), tilt=1.5, head_tilt=9, rear_tilt=5,
           ears=dict(COMMON['ears'], back=22, flap=3), bob=0.5, high=0.5, pitch=0.0, pitch1=3.0, pitch_at=0.0, rear1=4.0, rear1_at=0.5, flick=3.5,
            track={'front': 6.5, 'hind': 6.5}, lift={'front': 50, 'hind': 40}, rise=0.15, fall=0.6, clear=5.0, carry=0.15, delay=0.2, land=0.9, name='run', ticks=14, speed=38, duty=0.2, steps=('LH', 'RF'), drop=8,
           td={'LH': 0.97, 'RH': 0.97, 'RF': 0.38, 'LF': 0.42})
CLIPS = {2: WALK, 3: TIRED, 4: RUN}


IDLE = dict(COMMON, breath=dict(at=0.0, chest=4.0, head=3.0, snout=4.0, flank=2.5, belly=0.07, lag=0.08), name='idle', ticks=IDLE_TICKS, speed=0, duty=1.0, td={n: 0.0 for n in LEGS}, drop=2,
            bob=0.0, bob2=0.0, bob_side=0.0, roll=0.9, roll2=0.0, yaw=0.7, yaw2=0.0, pitch=0.0, pitch1=0.7, pitch3=0.0,
            shift=0.0, shift2=0.0, rear=0.8, flick=0.8, flick_extra=tail_flick, head_tilt=1.5,
            head=dict(nod=0.0, lag=0.1, nod1=1.6, steady=0.0, yaw=1.0, yaw_at=0.1, yaw2=0.0, against=0.3, roll=1.0, look=look),
            snout=dict(pitch=0.0, lag=0.1, yaw=1.0, down=0, sniff=sniff),
            ears=dict(flap=0.0, lag=0.12, sway=1.2, back=0, out=0, twitch=ear_twitch))


def idle_clip(rig):
    """The calm idle: feet planted where the rest pose has them while the body breathes, shifts its weight and the head looks about."""
    cfg = IDLE
    N = cfg['ticks']
    rest = rig.rest
    still = rig.world([[4096, 4096, 4096, 0, 0, 0, 0, 0, 0]] + [list(r) for r in rest[1:]])
    report = dict(over=0.0, stretch=0.0)
    hist = {}
    dy = {n: 0.0 for n in LEGS}
    frames = []
    for it in range(4):
        frames = []
        hist.clear()
        for t in range(N):
            phase = t / N
            pose = [list(r) for r in rest]
            pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
            body_pose(rig, cfg, phase, pose, hist, ofs=cfg['drop'], bphase=phase)
            targets = {name: ([side * (TRACK[front] + 0.0), dy[name], still[up][2][3] + SOLE[front][2]], 1.0, 0.0, 0.0)
                       for name, (up, lo, side, front, group, plate) in LEGS.items()}
            place_legs(rig, cfg, phase, pose, hist, targets, report)
            frames.append(pose)
        W = rig.world(frames[0])
        worst = {name: rig.lowest(W, plate_group(name)) for name in LEGS}
        for name in LEGS:
            dy[name] -= worst[name]
    frames.append([list(r) for r in frames[0]])
    return frames, report


def build(data, skeleton):
    """The idle (slots 0 and 33) and the three field gaits written into the model -> (bytes, report)."""
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError("Tapirmon's clips require the reviewed source")
    if [b[1] for b in skeleton] != PARENTS:
        raise ValueError('Tapirmon rig differs')
    n = len(skeleton)
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = n
    old = mmd.MMD.parse(data, n)
    old.type = SPECIES
    new = copy.deepcopy(old)
    rig = Rig(old, skeleton)
    changed, checks = set(), []
    jobs = [(0, IDLE, idle_clip(rig))] + [(slot, cfg, gait_clip(rig, cfg)) for slot, cfg in sorted(CLIPS.items())]
    for slot, cfg, (frames, report) in jobs:
        ticks = cfg['ticks'] * cfg.get('repeat', 1)
        source_events = animsheet.slot_frames(old, n, slot)[2]
        if slot == 0:        # one blink in the long loop, the source's own eye frames
            events = [(t + (0 if t == 0 else 36 - 15), kind, dict(e, frame=t + (0 if t == 0 else 36 - 15) + 1)) for t, kind, e in source_events if kind == 'tex']
        else:
            sound = next((dict(e) for _, kind, e in source_events if kind == 'sound'), dict(op='sound', bank=1, note=12))
            events = [(t, kind, e) for t, kind, e in source_events if kind == 'tex' and t == 0]
            for name in cfg['steps']:
                for k in range(cfg.get('repeat', 1)):
                    tick = round(cfg['td'][name] * cfg['ticks']) % cfg['ticks'] + k * cfg['ticks']
                    events.append((tick, 'sound', dict(sound, frame=tick + 1)))
        events.sort(key=lambda e: e[0])
        frames = [[[round(x) for x in bone] for bone in pose] for pose in frames]
        animation = mmd.encode_anim(frames, n, loop_sample=0, events=events, tol=1)
        index = old.anims.table[slot]
        new.anims.anims[index] = animation
        aliases = sorted(s for s, i in enumerate(old.anims.table) if i == index)
        changed |= set(aliases)
        checks.append(dict(slot=slot, ticks=ticks, over=round(report['over'], 2), aliases=aliases, stream_bytes=len(animation.build())))
    result = new.build()
    actual = mmd.MMD.parse(result, n)
    assert old.tmd.build() == actual.tmd.build()
    assert changed_programs(old, actual) == sorted(changed), (changed_programs(old, actual), sorted(changed))
    storage = motionstorage.require(result, n)
    return result, dict(species=SPECIES, source_sha256=SOURCE, output_sha256=hashlib.sha256(result).hexdigest(),
                        changed_slots=sorted(changed), checks=checks, storage=storage, mesh_exact=True, other_programs_exact=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/287-tapirmon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
