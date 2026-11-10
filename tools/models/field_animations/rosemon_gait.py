"""Rosemon's walk, condition walk and run on one step beat, legs and upper body alike.

Runs after pace.py on the paced model (the `after_generator` of its row in content/models/imports/pace.json): the idle
and every other program stay exactly as pace.py left them; slots 2, 3 and 4 are rewritten in place with the same length,
root travel and footstep sounds' count.

What was wrong. The legs of the previous clips stepped five (walk, condition walk) and eight (run) times per loop, while
the pelvis, chest, head, cape, braid and both arms replayed the idle's 83-tick performance (a hand flourish, the left hand
on the hip) squeezed into the loop: one slow beat per loop, in no phase with the feet. The legs had been solved at half the
travel and retimed afterwards, so a planted foot slid at 30-40% of the body's speed.

What the clips are now. Every channel is a harmonic (1x or 2x) of one step phase theta, 0 at the right heel strike, so each
loop holds a whole number of cycles of every channel and closes exactly:
- the legs: each foot stays where it landed while it supports (the foot's speed is the body's), rolls from the heel over the
  sole onto the toes, heel up before it leaves, and swings forward in a lifted arc to land on the heel. The pelvis height is
  chosen per tick so both legs stay a little bent but within reach (the walk is highest as the weight passes over the foot,
  the run lowest at mid-stance, with a flight phase);
- the pelvis turns with the leading leg and drops a little on the swing side, the chest counter-turns a little later and
  leans over the planted foot, the head counters the chest later still and stays level;
- the arms swing in the travel direction against the opposite leg, the elbows bent, the hands in line with the forearms;
- the braid, cape and shoulder leaves follow with a growing lag and a small second harmonic, so nothing moves rigidly.
The run leans forward; the condition walk droops the head and shrinks every swing.
"""
import copy
import hashlib
import math

import numeric as np
import animsheet
import mmd
import motionsecondary
import motionstorage
from motiondiscidentity import changed_programs
from tools.models.field_animations.aero_veedramon import _steps
from tools.models.field_animations.articulation import replace_channels
from tools.models.field_animations.war_greymon import set_rotation

R = motionsecondary.R
SOURCE = '071a0ccd860181240f5e8ef1a13a4244c9c44b8602e34478f15220287400c624'
SPECIES = 230
NB = 27
SLOTS = (0, 2, 3, 4)
PELVIS, CHEST, HEAD, CAPE, CAPE_LOW = 17, 1, 2, 3, 4
LEAVES = ((5, 6, 7), (8, 9, 10))
ARMS = ((11, 12, 13, 1), (14, 15, 16, -1))        # shoulder, elbow, hand, side (x > 0 is the right)
BRAID = (24, 25, 26)
LEGS = ((18, 19, 20, 1), (21, 22, 23, -1))        # hip, knee, ankle, side
TOLERANCE = {'legs': 2, 'arms': 9, 'body': 24}   # key-reduction tolerance (1/4096 turn): the legs keep the planted feet exact
FLOOR = -3.0                                       # the sole's height above the ground plane while it supports
LEG_BONES = {PELVIS, 18, 19, 20, 21, 22, 23}
ARM_BONES = {11, 12, 13, 14, 15, 16}
CHANNELS = {(b, c) for b in range(1, NB) for c in (3, 4, 5)} | {(PELVIS, 6), (PELVIS, 7)}
GROUPS = (('legs', {ch for ch in CHANNELS if ch[0] in LEG_BONES}), ('arms', {ch for ch in CHANNELS if ch[0] in ARM_BONES}),
          ('body', {ch for ch in CHANNELS if ch[0] not in LEG_BONES | ARM_BONES}))

# One row per slot. cycles: strides (right foot's loops) per clip; duty: share of a cycle a foot supports; lift: swing
# ankle clearance; heel / toe: sole pitch at heel strike (toe up) and at toe-off (heel up) in degrees; height: pelvis y at
# its highest (y is down, the rest pose is -234); bob: its swing; offset: the ankle behind the hip at mid-stance; stance_x:
# the ankle's distance from the middle. Angles are degrees, lengths game units.
ARMS_DEFAULT = dict(late=0.18, asym=0.1, skew=0.08, lag=math.pi / 4, elbow_skew=0.0, shrug=0.0, twist=0.0)

GAIT = {
    0: dict(still=True, cycles=1, duty=0.5, lift=0, heel=0, toe=0, offset=0, stance_x=34, leg=0.975, height=-231, bob=0.0, rise=1,
            feet=(10.0, -14.0), yaw=4.0, roll=2.6, chest_yaw=4.0, chest_roll=1.6, head_yaw=10.0, lean=5.0, droop=0.0, nod=0.0, sway=5.5,
            arm=6.0, abduct=6.0, elbow=24.0, elbow_swing=5.0, fwd=6.0, hand=3.0, leaf=4.0, braid=5.5, braid_back=0.0, cape=4.0,
            cape_back=0.0, breath=2.0, tilt=3.0, flick=0.0),
    2: dict(cycles=4, duty=0.62, lift=26, heel=10, toe=24, offset=14, stance_x=30, leg=0.975, height=-232, bob=3.0, rise=1,
            yaw=6.5, roll=2.8, chest_yaw=7.0, chest_roll=1.4, head_yaw=2.5, lean=4.5, droop=0.0, nod=0.7, sway=4.5,
            arm=22.0, abduct=9.0, elbow=30.0, elbow_swing=10.0, fwd=8.0, hand=10.0, leaf=3.0, braid=6.0, braid_back=2.0, cape=4.0,
            cape_back=0.0, breath=0.0, tilt=1.5, flick=2.0, shrug=1.6, twist=5.0, skew=0.1),
    3: dict(cycles=5, duty=0.64, lift=17, heel=8, toe=18, offset=14, stance_x=29, leg=0.975, height=-228, bob=2.2, rise=1,
            yaw=3.4, roll=1.6, chest_yaw=4.6, chest_roll=1.1, head_yaw=1.6, lean=8.0, droop=11.0, nod=0.9, sway=2.2,
            arm=11.0, abduct=9.0, elbow=22.0, elbow_swing=6.0, fwd=6.0, hand=6.0, leaf=2.0, braid=4.0, braid_back=1.0, cape=2.5,
            cape_back=0.0, breath=0.0, tilt=1.0, flick=0.0, shrug=1.0, twist=3.0),
    4: dict(cycles=5, duty=0.32, lift=24, kick=0.85, heel=-5, toe=24, offset=24, stance_x=26, leg=0.975, height=-239, bob=4, rise=-1,
            yaw=4.0, roll=1.8, chest_yaw=3.5, chest_roll=1.0, head_yaw=1.5, lean=7.0, droop=0.0, nod=1.0, sway=2.5,
            arm=27.0, abduct=14.0, elbow=58.0, elbow_swing=14.0, fwd=8.0, hand=7.0, leaf=4.0, braid=8.0, braid_back=9.0, cape=7.0,
            cape_back=9.0, breath=0.0, tilt=1.5, flick=0.0, shrug=1.2, twist=5.0, skew=0.1),
}
for _row in GAIT.values():
    for _k, _v in ARMS_DEFAULT.items():
        _row.setdefault(_k, _v)


def mul(*ms):
    out = ms[0]
    for m in ms[1:]:
        out = R.m3mul(out, m)
    return out


def rx(d):
    return R.from_axis_angle([1, 0, 0], math.radians(d))


def ry(d):
    return R.from_axis_angle([0, 1, 0], math.radians(d))


def rz(d):
    return R.from_axis_angle([0, 0, 1], math.radians(d))


def apply(m, v):
    return [sum(m[i][j] * v[j] for j in range(3)) for i in range(3)]


def smooth(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def softmax(a, b, tau=2.5):
    """A smooth maximum, a little above the larger: the pelvis height never kinks where the reach limit takes over."""
    m = max(a, b)
    return m + tau * math.log(math.exp((a - m) / tau) + math.exp((b - m) / tau))


def _parse(data, sk):
    mmd.exe().skeleton[SPECIES] = sk
    mmd.exe().bone_count[SPECIES] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = SPECIES
    return model


class Rig:
    def __init__(self, model, sk):
        self.model, self.sk = model, sk
        self.verts = {b: np.array(model.tmd.obj_verts(o))[:, :3] for b, (o, _) in enumerate(sk) if o >= 0}
        idle = animsheet.slot_frames(model, NB, 0)[0][0]
        ref = copy.deepcopy(idle)
        for right, left in ((18, 21), (19, 22), (20, 23)):
            ref[left][3:6] = [ref[right][3], -ref[right][4], -ref[right][5]]
        self.ref_world = self.world(ref)
        self.sole = {1: self.verts[20].tolist(), -1: self.verts[23].tolist()}
        # the boot's toe leans outward by about 23 degrees from the heel; the foot is turned back to point nearly
        # straight ahead (the remaining few degrees keep the foot from looking pigeon-toed)
        self.yaw = {side: side * 17.0 for side in (1, -1)}

    def world(self, pose):
        p = copy.deepcopy(pose)
        p[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(self.model, p))

    def foot(self, side, pitch):
        """(foot rotation, ankle shift along z that keeps the contact vertex still, depth of the sole below the ankle)."""
        return motionsecondary.rolling_foot(self.sole[side], ry(self.yaw[side]), pitch)


def _stance_pitch(s, g):
    """Sole pitch over the stance (s = 0..1): toe up at heel strike, flat, then heel up as the weight rolls to the toes."""
    return -g['heel'] * (1 - smooth(s / 0.2)) + g['toe'] * smooth((s - 0.58) / 0.42)


def _swing_pitch(q, g):
    return g['toe'] + (-g['heel'] - g['toe']) * smooth(q / 0.7)


class Gait:
    """The foot of one leg over the cycle, in the body's frame (z forward is negative; the ground moves back at `speed`)."""

    def __init__(self, g, period, speed):
        self.g, self.period, self.speed = g, period, speed
        self.stance = g['duty'] * period
        self.swing = (1 - g['duty']) * period
        self.half = speed * self.stance / 2

    def at(self, phase):
        """(z offset of the flat foot from its mid-stance place, lift above the ground, pitch, supporting)"""
        g = self.g
        if phase < g['duty']:
            s = phase / g['duty']
            return -self.half + self.speed * phase * self.period, 0.0, _stance_pitch(s, g), True
        q = (phase - g['duty']) / (1 - g['duty'])
        m = 0.6 * self.speed * self.swing
        z = ((2 * q ** 3 - 3 * q * q + 1) * self.half + (q ** 3 - 2 * q * q + q) * m
             + (-2 * q ** 3 + 3 * q * q) * -self.half + (q ** 3 - q * q) * m)
        return z, g['lift'] * math.sin(math.pi * q ** g.get('kick', 1.0)) ** 0.8, _swing_pitch(q, g), False


def _author(model, sk, rig, slot, source):
    g = GAIT[slot]
    n = len(source) - 1
    K = g['cycles']
    speed = -(source[-1][0][8] - source[0][0][8]) / n
    still = g.get('still', False)
    gait = None if still else Gait(g, n / K, speed)
    # right midstance, in radians of the step phase
    mid = math.pi * g['duty']
    neutral = copy.deepcopy(source[0])
    neutral[0] = [4096] * 3 + [0] * 6
    set_rotation(neutral, PELVIS, rx(0.5 * g['lean']), {})
    neutral[PELVIS][6:9] = [0, round(g['height']), -45]
    wn = rig.world(neutral)
    hz0 = {hip: float(wn[hip, 2, 3]) for hip, _, _, _ in LEGS}
    out, hist, notes = [], {}, dict(pelvis_y=[], reach=0.0)
    vs = rig.verts
    for t in range(n + 1):
        tt = t % n
        th = 2 * math.pi * K * tt / n
        loop = 2 * math.pi * tt / n
        cosine = lambda lag=0.0, k=1: math.cos(k * (th - lag))
        f = copy.deepcopy(source[tt])
        f[0] = [4096] * 3 + [0] * 6
        # --- pelvis: turns with the leading leg, drops on the swing side
        yaw = g['yaw'] * cosine(0.05)
        roll = -g['roll'] * cosine(mid if not still else 0.0)
        pitch = 0.5 * g['lean'] + 0.5 * g['nod'] * cosine(mid + 0.3, 2)
        Rp = mul(ry(yaw), rx(pitch), rz(roll))
        set_rotation(f, PELVIS, Rp, hist)
        Rp = np.array(mmd.rot_matrix(*f[PELVIS][3:6])).tolist()
        sway = g['sway'] * cosine(mid + 0.1 if not still else 0.5)
        f[PELVIS][6], f[PELVIS][8] = round(sway), -45
        f[PELVIS][7] = round(g['height'])
        w = rig.world(f)
        pos = [float(sway), 0.0, -45.0]
        # --- feet: goals in the world
        goals = []
        for hip, knee, ankle, side in LEGS:
            phase = ((th / (2 * math.pi)) + (0.0 if side == 1 else 0.5)) % 1.0
            if still:
                dz, lift, p, support = g['feet'][0 if side == 1 else 1], 0.0, 0.0, True
            else:
                dz, lift, p, support = gait.at(phase)
            rf, shift, depth = rig.foot(side, p)
            hz = hz0[hip]
            x = side * g['stance_x'] + side * (3.0 * math.sin(math.pi * ((phase - g['duty']) / (1 - g['duty']))) ** 2 if not support else 0.0)
            goals.append(dict(hip=hip, knee=knee, ankle=ankle, side=side, goal=[x, FLOOR - depth - lift, hz + (0.0 if still else g['offset']) + dz + shift], rf=rf, support=support))
        # --- pelvis height: the highest the legs allow, with the walk's bob (the run's dip) on top
        limit = g['leg'] * (np.linalg.norm(f[19][6:9]) + np.linalg.norm(f[20][6:9]))
        bound = -1e9
        for foot in goals:
            h = [float(w[foot['hip'], i, 3]) for i in range(3)]
            d2 = (foot['goal'][0] - h[0]) ** 2 + (foot['goal'][2] - h[2]) ** 2
            assert d2 < limit * limit, (slot, t, foot['side'], 'horizontal reach', d2 ** 0.5, limit)
            drop = h[1] - f[PELVIS][7]
            bound = max(bound, foot['goal'][1] - math.sqrt(limit * limit - d2) - drop)
        preferred = g['height'] - g['rise'] * g['bob'] * cosine(mid, 2) + g['breath'] * 0.6 * cosine(0.0, 3)
        y = softmax(bound, preferred)
        notes['pelvis_y'].append(y)
        f[PELVIS][7] = round(y)
        # --- legs: two-bone solve of each leg onto its foot goal, the knee kept forward and a little out
        for foot in goals:
            hip, knee, ankle, side = foot['hip'], foot['knee'], foot['ankle'], foot['side']
            w = rig.world(f)
            h = w[hip, :3, 3]
            a, b = float(np.linalg.norm(f[knee][6:9])), float(np.linalg.norm(f[ankle][6:9]))
            goal = np.array(foot['goal'])
            delta = goal - h
            dist = float(np.linalg.norm(delta))
            assert dist < a + b - 0.5, (slot, t, side, 'reach', dist, a + b)
            direction = delta / dist
            pole = np.array([0.12 * side, 0.0, -1.0])
            pp = pole - direction * float(pole @ direction)
            pp /= np.linalg.norm(pp)
            along = (a * a - b * b + dist * dist) / (2 * dist)
            joint = h + direction * along + pp * math.sqrt(max(0.0, a * a - along * along))
            rw = rig.ref_world
            rh, rs = map(np.array, motionsecondary.native_plane_rotations(
                [rw[v, :3, 3].tolist() for v in (hip, knee, ankle)], [h.tolist(), joint.tolist(), goal.tolist()],
                [rw[v, :3, :3].tolist() for v in (hip, knee)]))
            set_rotation(f, hip, np.array(Rp).T @ rh, hist)
            w = rig.world(f)
            set_rotation(f, knee, w[hip, :3, :3].T @ rs, hist)
            w = rig.world(f)
            set_rotation(f, ankle, w[knee, :3, :3].T @ np.array(foot['rf']), hist)
            notes['reach'] = max(notes['reach'], float(np.linalg.norm(rig.world(f)[ankle, :3, 3] - goal)))
        # --- chest, head
        def world_turn(bone, parent, target):
            w = rig.world(f)
            set_rotation(f, bone, w[parent, :3, :3].T @ np.array(target), hist)
        lean = g['lean']
        world_turn(CHEST, PELVIS, mul(ry(-g['chest_yaw'] * cosine(0.35)), rx(lean + 0.6 * g['nod'] * cosine(mid + 0.6, 2) + g['breath'] * cosine(0.3, 3)),
                                      rz(0.7 * g['roll'] * cosine(mid + 0.4) * 0 + g['chest_roll'] * cosine(mid + 0.45))))
        world_turn(HEAD, CHEST, mul(ry(g['head_yaw'] * (cosine(0.9) + (0.35 * math.cos(2 * (th - 0.2)) if still else 0.0))),
                                    rx(-0.35 * lean + g['droop'] - 0.6 * g['nod'] * cosine(mid + 1.0, 2) - 0.4 * g['breath'] * cosine(0.5, 3)),
                                    rz(-0.8 * g['chest_roll'] * cosine(mid + 0.8) + g['tilt'] * math.cos(loop - 0.6))))
        # --- arms: a pendulum from the shoulder; the elbow trails the shoulder, the wrist the elbow, the left arm is a
        # little smaller and later than the right, and the upper arm twists and the shoulder lifts with each step
        for shoulder, elbow, hand, side in ARMS:
            if still:      # the idle's relaxed arms, as approved
                back = g['arm'] * math.cos(th - 0.25) * (1 if side == 1 else -1)
                forward = 0.5 - 0.5 * side * math.cos(th - 0.55)
                set_rotation(f, shoulder, mul(rx(back - g['fwd']), rz(-side * (g['abduct'] + 0.12 * g['arm'] * math.cos(th + (0.0 if side == 1 else math.pi) - 1.0)))), hist)
                set_rotation(f, elbow, rx(-(g['elbow'] + g['elbow_swing'] * (forward - 0.5))), hist)
                flick = g['flick'] * (0.5 + 0.5 * math.cos(loop - (0.4 if side == 1 else 2.9))) * math.cos(2 * th - 0.5)
                set_rotation(f, hand, mul(rx(-g['hand'] * (forward - 0.5)), rz(side * flick), ry(0.5 * flick)), hist)
                continue
            sgn = 1 if side == 1 else -1
            late = 0.0 if side == 1 else g['late']
            amp = g['arm'] * (1.0 if side == 1 else 1.0 - g['asym'])
            u = th - 0.25 - late
            back = amp * sgn * (math.cos(u) + g['skew'] * math.sin(2 * u))       # positive swings the arm back
            lead = -sgn * math.cos(u - g['lag'])                                   # 1 as the forearm is most forward
            flex = g['elbow'] + g['elbow_swing'] * lead + g['elbow_skew'] * math.sin(2 * (u - g['lag']))
            wrist = -sgn * math.cos(u - 2 * g['lag'] - 0.2)
            lift = g['shrug'] * math.cos(2 * (th - mid) + (0.0 if side == 1 else 0.6))
            twist = g['twist'] * sgn * math.cos(u - g['lag'] - 0.5)
            local = mul(rx(back - g['fwd']), rz(-side * (g['abduct'] + lift)), ry(twist))
            set_rotation(f, shoulder, local, hist)
            set_rotation(f, elbow, rx(-flex), hist)
            flick = g['flick'] * (0.5 + 0.5 * math.cos(loop - (0.4 if side == 1 else 2.9))) * math.cos(2 * th - 0.5)
            set_rotation(f, hand, mul(rx(-g['hand'] * wrist), rz(side * flick), ry(0.5 * flick)), hist)
        # --- leaves, braid and cape: a lagging follow-through
        for chain, side in zip(LEAVES, (1, -1)):
            for i, bone in enumerate(chain):
                lag = 0.5 + 0.35 * i
                set_rotation(f, bone, mul(rx(g['leaf'] * cosine(lag, 2)), rz(side * g['leaf'] * 0.8 * cosine(mid + lag))), hist)
        for i, bone in enumerate(BRAID):
            lag = 0.6 + 0.6 * i
            set_rotation(f, bone, mul(rx(g['braid_back'] / 3 + g['braid'] * (0.6 + 0.2 * i) * cosine(lag, 2)),
                                      rz(0.9 * g['braid'] * (0.5 + 0.3 * i) * cosine(lag + 0.3))), hist)
        set_rotation(f, CAPE, mul(rx(g['cape_back'] * 0.5 + g['cape'] * cosine(0.8, 2)), rz(0.6 * g['cape'] * cosine(0.3))), hist)
        set_rotation(f, CAPE_LOW, mul(rx(g['cape_back'] * 0.5 + 1.3 * g['cape'] * cosine(1.4, 2)), rz(0.8 * g['cape'] * cosine(0.9))), hist)
        # the lower cape hinges up just enough to clear the ground
        w = rig.world(f)
        points = vs[CAPE_LOW] @ w[CAPE_LOW, :3, :3].T + w[CAPE_LOW, :3, 3]
        bias = np.array(motionsecondary.clearance_rotation(points.tolist(), w[CAPE_LOW, :3, 3].tolist(), w[CAPE_LOW, :3, 0].tolist(), [-45, 0], -8))
        set_rotation(f, CAPE_LOW, w[CAPE, :3, :3].T @ bias @ w[CAPE_LOW, :3, :3], hist)
        f[0] = copy.deepcopy(source[tt][0])
        f[0][8] = source[t][0][8]
        out.append(f)
    # the loop's last frame is the first again
    out[-1][1:] = copy.deepcopy(out[0][1:])
    return out, notes, speed


def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('Rosemon gait requires the paced Rosemon model')
    model = _parse(data, sk)
    rig = Rig(model, sk)
    result = copy.deepcopy(model)
    checks = []
    for slot in SLOTS:
        source, loop, events = animsheet.slot_frames(model, NB, slot)
        assert loop == 0
        frames, notes, speed = _author(model, sk, rig, slot, source)
        index = model.anims.table[slot]
        assert sum(1 for v in model.anims.table if v == index) == 1
        program = model.anims.anims[index]
        for name, channels in GROUPS:
            program = replace_channels(program, frames, loop, NB, channels, tolerance=TOLERANCE[name])
        n = len(source) - 1
        ticks = [] if GAIT[slot].get('still') else [round(i * n / (2 * GAIT[slot]['cycles'])) for i in range(2 * GAIT[slot]['cycles'])]
        result.anims.anims[index] = _steps(program, ticks) if ticks else program
        checks.append(dict(slot=slot, ticks=n, cycles=GAIT[slot]['cycles'], units_per_tick=round(speed, 2), footstep_ticks=ticks,
                           pelvis_y=[round(min(notes['pelvis_y']), 1), round(max(notes['pelvis_y']), 1)],
                           ankle_error=round(notes['reach'], 2)))
    output = result.build()
    effective = _parse(output, sk)
    assert effective.tmd.build() == model.tmd.build()
    changed = changed_programs(model, effective)
    assert changed == list(SLOTS), changed
    return output, dict(species=SPECIES, source_sha256=SOURCE, output_sha256=hashlib.sha256(output).hexdigest(),
                        changed_slots=changed, checks=checks, storage=motionstorage.require(output, NB))
