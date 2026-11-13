"""Garudamon's field gaits (species 460) on planted feet, on native Angemon's rig.

The mesh is bound in a standing pose of its own (native_binding `bind_pose`: the pose the mesh is modelled in, legs a little
apart, knees and elbows eased, wings folded back), so the rest the gaits start from is upright and symmetric with both feet
pointing forward. `quadruped.py` plants each foot (two-bone solve, the sole flat, heel first, rolling over its ball); the body
bobs, pitches, rolls and counter-turns its chest against the hips with the footfalls; each arm swings forward with the leg of
the other side and each wing breathes behind the body, all on springs so that nothing moves in lock-step. Forward is -z.
"""
import copy
import hashlib
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet  # noqa: E402
import mmd  # noqa: E402
from tools.models.field_animations import quadruped  # noqa: E402

SPECIES = 9460
TAU = 2 * math.pi
DEG = 4096 / 360
# Angemon's rig (26 bones). pelvis (the trunk's root), hips (legs and loin), chest, head, tail: the trunk; legs: thigh, shin, foot, side; arms: shoulder, elbow, hand, side;
# wings: bones of each side (root first)
DONORS = {
    26: dict(pelvis=1, hips=18, chest=2, neck=None, head=3, tail=(25,),
             legs={'R': (19, 20, 21, 1, False), 'L': (22, 23, 24, -1, False)},
             arms=((4, 5, 6, 1), (7, 8, 9, -1)), wings={1: (10, 11), -1: (12, 13)}),
}
# arm: degrees each arm swings forward and back (the left arm by `arm_left` as much, the right one `arm_late` of a cycle
# later: the two sides are not mirror images); elbow_bend: degrees the elbows bend on top of the bind pose, elbow: degrees
# they bend more by as the arm swings back, each joint down the arm following `arm_lag` of a cycle later; hand: degrees the
# loose hands flap; arm_out: degrees the arms open from the body; slump: degrees the shoulders roll forward; sway: degrees
# of the idle's slow arm sway; wing, wing_pitch: degrees the wings lift and sweep back, wing_back: degrees they are held
# further back (streaming in the run); shift: units the hips carry over the standing foot; look: the idle's head turns,
# (cycle, yaw, pitch) keys eased one into the next; head_down: degrees the head hangs; height: how far the hips sit below
# the bind pose
COMMON = dict(
    kind='walk', snap=False, arc=0.8, plateau=0.8, clear_ease=0.1, world_ease=True, fold_soft=10, slip=0.0, heel=4,
    reach={'front': 0, 'hind': 0}, lift={'front': 0, 'hind': 44}, curl={'front': 0, 'hind': 14}, peel={'front': 0, 'hind': 16},
    out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 0}, track={'front': 0, 'hind': 0}, settle=3,
    height=10, bob=1.5, side=0.25, high=0.16, shift=3, shift_late=0.04, hip_yaw=3, hip_roll=1.2, chest_yaw=4, chest_roll=1.2,
    lean=0, breath=0, flex=1.5, nod=2, lag=(0.08, 0.16), tail=6, look=(), head_down=0,
    arm_out=2, arm=14, arm_left=0.85, arm_late=0.035, arm_lag=0.09, elbow=26, elbow_bend=30, hand=22, slump=0, sway=0,
    wing=4, wing_pitch=2, wing_back=0, wing_lag=0.14,
)
GAITS = {
    0: dict(COMMON, name='idle', ticks=76, speed=0, touchdown={'L': 0.0, 'R': 0.5}, duty={'L': 1.0, 'R': 1.0}, steps=(),
            lift={'front': 0, 'hind': 0}, peel={'front': 0, 'hind': 0}, curl={'front': 0, 'hind': 0}, heel=0, settle=0,
            height=5, bob=0.8, side=0, shift=4, hip_yaw=1.5, hip_roll=0.8, chest_yaw=2, chest_roll=1, breath=3.5, flex=0,
            nod=0.8, tail=3, arm=0, sway=5, elbow=12, elbow_bend=16, hand=12, arm_out=3, wing=5, wing_pitch=3, lag=(0.05, 0.1),
            look=((0.0, 0, 0), (0.12, 0, 0), (0.32, 13, 2), (0.46, 11, 1), (0.66, -7, -1), (0.76, -8, 1), (0.86, -6, 0), (1.0, 0, 0))),
    2: dict(COMMON, name='walk', ticks=14, speed=18, height=16, bob=2.5, arm=24, lean=2, wing=9, wing_pitch=5,
            touchdown={'L': 0.0, 'R': 0.5}, duty={'L': 0.6, 'R': 0.6}, steps=('L', 'R')),
    3: dict(COMMON, name='tired walk', ticks=22, speed=11, touchdown={'L': 0.0, 'R': 0.5}, duty={'L': 0.62, 'R': 0.62},
            steps=('L', 'R'), lift={'front': 0, 'hind': 22}, peel={'front': 0, 'hind': 12}, curl={'front': 0, 'hind': 8},
            lean=9, head_down=16, height=22, bob=3, hip_yaw=2.5, chest_yaw=3, nod=3, arm=12, arm_left=0.7, arm_lag=0.13,
            elbow=14, elbow_bend=12, hand=26, arm_out=1, slump=14, wing=3, wing_pitch=2, wing_back=-3, settle=4, shift=4,
            lag=(0.12, 0.24)),
    4: dict(COMMON, name='run', kind='trot', ticks=11, speed=44, touchdown={'L': 0.0, 'R': 0.5}, duty={'L': 0.38, 'R': 0.38},
            steps=('L', 'R'), lift={'front': 0, 'hind': 56}, peel={'front': 0, 'hind': 20}, curl={'front': 0, 'hind': 10},
            arc=0.9, clear_ease=0.05, height=20, lean=11, bob=5, hip_yaw=4, hip_roll=1.5, chest_yaw=4, chest_roll=1.5, flex=2,
            nod=2.5, arm=34, arm_lag=0.07, elbow=22, elbow_bend=78, hand=16, arm_out=6, wing=10, wing_pitch=4, wing_back=-4,
            shift=3, head_down=-4, reach={'front': 0, 'hind': 8}, snap=True),
}


def rest_world(model, rig):
    pose = [list(v) for v in animsheet.slot_frames(model, len(rig), 0)[0][0]]
    pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
    return mmd.bone_matrices(model, pose)


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


def turned(rig, pose, b, parent, turn, base=None):
    """Bone b at its rest turn (or `base`, a local rotation matrix) followed by `turn`, a rotation given in the world of the
    rest pose about the joint. The donor's left limbs are not its right ones mirrored (their axes are turned half a turn about
    the vertical), so swings are written in the world, where mirroring the angle mirrors the motion, and carried into each
    bone's own space."""
    P = rig.R(rig.still, parent)
    local = quadruped.mul(quadruped.mul(quadruped.tr(P), quadruped.mul(turn, P)), base or mmd.rot_matrix(*rig.rest[b][3:6]))
    quadruped.set_rot(pose, b, local, {b: pose[b][3:6]})     # the angles nearest the current ones: no flip between ticks


def about(axis, degrees):
    return quadruped.spin(axis, math.radians(degrees))


X, Y, Z = [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]


def swing_wave(phase):
    """A swing that eases: quicker through the middle of the forward swing, lingering at the back."""
    a = TAU * phase
    return (math.cos(a) + 0.2 * math.cos(2 * a - 0.6)) / 1.1


def keyed(keys, phase):
    """The value of eased (cycle, *values) keys at `phase`: smooth steps from one key to the next, holding between."""
    phase %= 1.0
    for (p0, *v0), (p1, *v1) in zip(keys, keys[1:]):
        if p0 <= phase <= p1:
            s = (phase - p0) / (p1 - p0) if p1 > p0 else 0.0
            s = s * s * (3 - 2 * s)
            return [a + (c - a) * s for a, c in zip(v0, v1)]
    return list(keys[0][1:])


def body(rig, cfg, phase, pose, hist):
    """The trunk, written as world turns. Angemon's pelvis bone sits at the pole of its Euler angles (a turn through it
    makes the angles jump between ticks), and its own axes are not the world's, so it only carries the body: it drops and
    rises twice a stride and carries a few units over the standing foot. The hips (the legs' and loin's parent) turn a few
    degrees about the vertical with the stride and roll a little; the chest turns against them, a little later, leans and
    breathes; the head is held steady in the world (nodding late), hangs or looks about; the loin cloth swings behind."""
    p, rest = rig.p, rig.rest
    d = p['donor']
    pelvis, hips, chest, head = d['pelvis'], d['hips'], d['chest'], d['head']
    lag_chest, lag_head = cfg['lag']
    bob = cfg['bob'] * (math.cos(2 * TAU * (phase - cfg['high'])) + cfg['side'] * math.cos(TAU * (phase - cfg['high'] - 0.1)))
    pose[pelvis][7] = rest[pelvis][7] - cfg['height'] - bob
    a = TAU * (phase - 0.08)
    s = math.sin(a) + cfg['shift_late'] * math.sin(2 * a) * 4
    s = math.copysign(abs(s) ** 0.7, s) * (1.0 if s > 0 else 0.85)
    if not cfg['speed']:       # the idle shifts its weight slowly and unevenly, settling a while on each foot
        s = 0.7 * math.sin(TAU * phase) + 0.3 * math.sin(2 * TAU * phase + 1.1)
    pose[pelvis][6] = rest[pelvis][6] - cfg['shift'] * s          # the left foot (x < 0) stands first: the hips carry to it
    turn = cfg['hip_yaw'] * math.sin(TAU * (phase - 0.3))
    roll = cfg['hip_roll'] * math.sin(TAU * (phase - 0.05))
    turned(rig, pose, hips, pelvis, quadruped.mul(about(Y, turn), about(Z, roll)))
    ct = -cfg['chest_yaw'] * math.sin(TAU * (phase - 0.3 - lag_chest))
    cr = -cfg['chest_roll'] * math.sin(TAU * (phase - 0.05 - lag_chest))
    cp = cfg['lean'] + cfg['breath'] * math.sin(TAU * (phase - 0.1)) + cfg['flex'] * math.cos(2 * TAU * (phase - 0.3 - lag_chest))
    turned(rig, pose, chest, pelvis, quadruped.mul(about(Y, ct), quadruped.mul(about(Z, cr), about(X, -cp))))
    look_yaw, look_pitch = keyed(cfg['look'], phase) if cfg['look'] else (0.0, 0.0)
    nod = cfg['nod'] * math.cos(2 * TAU * (phase - 0.1 - lag_head))
    turned(rig, pose, head, chest, quadruped.mul(about(Y, look_yaw - 0.8 * ct),
                                                 about(X, look_pitch - cfg['head_down'] + 0.6 * cp - nod)))
    for k, b in enumerate(d['tail']):
        swing = cfg['tail'] * math.sin(TAU * (phase - 0.25 - 0.1 * k))
        turned(rig, pose, b, hips, quadruped.mul(about(Y, 0.4 * swing), about(X, swing)))


def extra(rig, cfg, phase, pose):
    """Each arm swings forward with the opposite leg (the left foot lands at phase 0, the right arm is then forward), the
    elbow and then the hand following later, the elbow bending more as the arm swings back; the right arm swings a little
    later and further than the left. In the idle the arms only sway, each at its own time. The wings drift behind the body,
    lifting and sweeping, the outer bone later than the root. The loose springs that make every part trail come in
    `compose`."""
    d = rig.p['donor']
    still = not cfg['speed']
    for sh, el, hand, side in d['arms']:
        amp = cfg['arm'] * (1.0 if side > 0 else cfg['arm_left'])
        ph = phase - (cfg['arm_late'] if side > 0 else 0.0)
        sway = cfg['sway'] * (0.65 * math.sin(TAU * (ph + 0.3 * side)) + 0.35 * math.sin(2 * TAU * (ph + 0.17 * side)))
        swing = side * amp * swing_wave(ph) + sway
        out = cfg['arm_out'] + 0.4 * cfg['sway'] * math.sin(TAU * (ph + 0.3 * side + 0.25))
        # forward is -z: a hanging arm turns forward about -x; outward is +x for the right arm (side 1)
        turned(rig, pose, sh, rig.sk[sh][1], quadruped.mul(about(Z, -side * out), about(X, -(swing + cfg['slump']))))
        # the forearm trails the upper arm: the elbow bends most just after the arm reaches its back, opening again as it
        # swings through, and the loose hand trails the forearm by as much again
        def trail(lag):
            if still:
                return 0.5 + 0.5 * math.sin(TAU * (ph - lag) + 1.9 * side)
            return 0.5 - 0.5 * side * swing_wave(ph - lag)
        bend = cfg['elbow_bend'] + cfg['elbow'] * trail(cfg['arm_lag'])
        turned(rig, pose, el, sh, about(X, -bend))
        flap = cfg['hand'] * (trail(2 * cfg['arm_lag']) - 0.3)
        turned(rig, pose, hand, el, about(X, -flap))
    for side, bones in d['wings'].items():
        for k, b in enumerate(bones):
            lag = cfg['wing_lag'] * k + (0.04 if side > 0 else 0.0)
            if still:      # slow uneven drift: the two wings do not breathe together
                w = 0.6 * math.sin(TAU * (phase - lag - 0.1 * side)) + 0.4 * math.sin(2 * TAU * (phase - lag) + side)
                v = 0.5 * math.sin(TAU * (phase - lag - 0.25)) + 0.5 * math.sin(3 * TAU * (phase - lag) + 0.7 * side)
            else:
                w = math.sin(TAU * (phase - 0.1 - lag))
                v = math.sin(TAU * (phase - 0.3 - lag))
            lift = w * cfg['wing'] * (1 + 0.5 * k)
            sweep = (v + 1) * cfg['wing_pitch'] + cfg['wing_back'] * (1 + 0.3 * k)
            turned(rig, pose, b, rig.sk[b][1], quadruped.mul(about(Z, side * lift), about(Y, side * sweep)))


def compose(rig, cfg, frames):
    """Arms, elbows and wings run through loose springs (a lag and a small overshoot each); the loop stays closed."""
    d = rig.p['donor']
    ticks = cfg['ticks']
    follow = {}
    for sh, el, hand, side in d['arms']:
        follow[sh] = (0.55, 0.5)
        follow[el] = (0.42, 0.33)
        follow[hand] = (0.35, 0.28)
    for side, bones in d['wings'].items():
        for k, b in enumerate(bones):
            follow[b] = (0.38 - 0.08 * k, 0.22)
    if not cfg['speed'] and not cfg.get('spring_idle', True):
        return frames
    out = [[list(b) for b in pose] for pose in frames[:ticks]]
    for b, (rate, damping) in follow.items():
        for ch in (3, 4, 5):
            seq = [out[i][b][ch] for i in range(ticks)]
            mixed = spring(seq, rate, damping)
            for i in range(ticks):
                out[i][b][ch] = mixed[i]
    closing = [list(b) for b in out[0]]
    closing[0][8] = frames[-1][0][8]
    out.append(closing)
    return out


def make_profile(model, rig, data):
    n = len(rig)
    d = DONORS[n]
    legs = d['legs']
    profile = dict(
        species=SPECIES, name='Garudamon', source=hashlib.sha256(data).hexdigest(), parents=[b[1] for b in rig],
        pelvis=d['pelvis'], chest=d['chest'], neck=d['neck'], head=d['head'], tail=d['tail'], loose=(), donor=d,
        legs=legs, pole_world=True, rest_plane=True, pole={False: [0, 0, -1]},
        paw_rest={}, sole={False: [0, 0, 0]}, reach={'front': 0, 'hind': 0}, fold={False: 60},
        clear=4, floor=3, stance_slip=0.25, speed_range={0: (0, 0), 2: (15, 31), 3: (10, 20), 4: (35, 52)},
        floor_skip=tuple(d['tail']), gaits=copy.deepcopy(GAITS), extra=extra, body=body)
    for g in profile['gaits'].values():
        g['compose'] = compose
    W = rest_world(model, rig)
    pos = lambda b: [W[b][i][3] for i in range(3)]
    Rm = lambda b: [list(W[b][i][:3]) for i in range(3)]
    tmp = quadruped.Rig(model, rig, profile)
    up, lo, paw, side, _ = legs['R']
    verts = tmp.verts[paw]
    R = Rm(paw)
    world = [quadruped.add(quadruped.mv(R, v), pos(paw)) for v in verts]
    low = max(w[1] for w in world)
    near = [w for w in world if w[1] > low - 12]
    zc = sum(w[2] for w in near) / len(near)
    sole_w = [0.0, low - pos(paw)[1], zc - pos(paw)[2]]
    profile['sole'][False] = [round(v, 1) for v in quadruped.mv(quadruped.tr(R), sole_w)]
    for name, (u, l, p_, s, f) in legs.items():
        # the same point under each ankle, in each foot bone's own space (the donor's left leg bones are not the right
        # ones mirrored: their axes are turned half a turn about the vertical)
        profile['sole'][name] = [round(v, 1) for v in quadruped.mv(quadruped.tr(Rm(p_)), sole_w)]
    profile['reach']['hind'] = round(sole_w[2] + 8)
    la = quadruped.norm(quadruped.sub(pos(lo), pos(up)))
    lb = quadruped.norm(quadruped.sub(pos(paw), pos(lo)))
    profile['fold'][False] = round(0.55 * (la + lb))
    mid = [(a + b) / 2 for a, b in zip(pos(up), pos(paw))]
    knee = quadruped.sub(pos(lo), mid)
    chord = quadruped.unit(quadruped.sub(pos(paw), pos(up)))
    perp = quadruped.sub(knee, quadruped.scale(chord, quadruped.dot(knee, chord)))
    if quadruped.norm(perp) > 12:
        profile['pole'][False] = [round(v, 3) for v in quadruped.unit(perp)]
    for name, (u, l, p_, s, f) in legs.items():
        toe = quadruped.mv(quadruped.tr(Rm(p_)), [0, 0, -1])
        profile['paw_rest'][name] = [round(v, 4) for v in toe]
    return profile


def build(data, rig, tweak=None):
    n = len(rig)
    exe = mmd.exe()
    for table in (exe.skeleton, exe.bone_count):
        table.extend([None] * (SPECIES + 1 - len(table)))
    exe.skeleton[SPECIES] = rig
    exe.bone_count[SPECIES] = n
    old = mmd.MMD.parse(data, n)
    old.type = SPECIES
    profile = make_profile(old, rig, data)
    if tweak:
        tweak(profile)
    return quadruped.build(data, rig, profile)
