"""Divermon's field gaits (species 304): idle, walk, tired walk and run on planted flippers, with a loose body.

Divermon is a stout diver: a glass helmet on the head (bone 8), a red air tank hung from the back of the head
(10-12), two fin ears at the head's sides (9 left, 13 right), arms 2-4 (x > 0) and 5-7 (x < 0) with the harpoon in the
second hand, the upper body 1 and the hips 14 under it (the legs 18-21 on the x < 0 side, 22-25 on the x > 0 side:
hip, knee, heel, flipper) and a tail 15-17 held out behind. Forward is -z.

What the imported clips did wrong: the model's own rest pose turns the x < 0 flipper 77 degrees outwards (the other one
stands 20 degrees out), the clips never bent the knees (bones 19 and 23 stayed at one angle in all of them), swung the
thighs by up to 64 degrees in a single tick and asked for steps of 230 to 480 units from legs 123 units long, so the
soles slid (110 to 160 % of the travel), the run (66 units a tick) and tired walk (26) were out of their native
speeds, the upper body only yawed back and forth as a straight-edged triangle wave, and the ears and the tail were
not moved at all.

`quadruped.py` plants each flipper (two-bone IK on thigh and shin, the sole flat on the floor, both flippers turned
out by the same small splay) with a step the leg can reach, and `body` writes everything above the legs: a
pelvis that drops on each landing and rises over the planted foot, hips that turn against the shoulders, the upper body
rolling and shifting over the loaded foot, arms that swing against the legs and trail by a pendulum's lag, and the
parts that hang (ears, tank, tail) as damped springs driven by the body's own motion (`follow`: a spring is run over
the closed loop until it settles, so each part trails the body by a tick or two, overshoots a little and closes the
loop). The idle (240 ticks, 8 s) breathes, rolls the weight from one flipper to the other, looks about, twitches an ear
and swishes the tail.

Offline: `tools/models/edit.py get 304` on the commit before this change, then
`python3 -m tools.models.field_animations.divermon_gait --source THAT.MMD --out AFTER.MMD --tex THAT.TIM --out-tex AFTER.TIM`
and `edit.py put 304 AFTER.MMD AFTER.TIM`.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import mmd  # noqa: E402
import motionstorage  # noqa: E402
from tools.models.field_animations import divermon_face as face  # noqa: E402
from tools.models.field_animations import quadruped  # noqa: E402
from tools.models.field_animations.quadruped import mul, tr, rot, set_rot  # noqa: E402

SPECIES = 304
SOURCE = '5930fdaa35c24fbc3598ec84401b8c83f07e586818343ba6d0b692056971dcaf'   # `edit.py get 304` before this change
SOURCE_TIM = 'cbd98827537d5b90e8c96dc4eeba3e79e207442af8cdfcb5f6cbf5f478b1f5ac'   # the texture before this change
TAU = 2 * math.pi
DEG = 4096 / 360
UPPER, HIPS, HEAD = 1, 14, 8
ARMS = {'R': (2, 3, 4, 1), 'L': (5, 6, 7, -1)}       # shoulder, elbow, hand, side (+1 = x > 0)
EARS = {'L': (9, -1), 'R': (13, 1)}                    # bone, sign of its turn about its own vertical axis (outwards)
TANK = (10, 11, 12)
TAIL = (15, 16, 17)
LEGS = {'LH': (18, 19, 20, -1, False), 'RH': (22, 23, 24, 1, False)}
TOE_OF = {'LH': 21, 'RH': 25}
SPLAY = 7           # degrees each flipper points outwards of the travel direction


def harm(phase, *terms):
    """A sum of cosines: terms are (amplitude, rate, delay in cycles)."""
    return sum(a * math.cos(TAU * rate * (phase - delay)) for a, rate, delay in terms)


def bump(phase, centre, width):
    """A smooth hump of 1 at `centre` falling to 0 `width` cycles away (cosine-squared, wrapping round the loop)."""
    d = (phase - centre + 0.5) % 1.0 - 0.5
    return math.cos(math.pi * d / width / 2) ** 2 if abs(d) < width else 0.0


_SPRINGS = {}


def follow(cfg, key, signal, period, zeta, loops=1):
    """What a damped spring (natural period `period` ticks, damping ratio `zeta`) driven by `signal(phase)` does over the
    closed loop of the clip (`loops` cycles of it): the spring is run for many loops until it settles, then the last loop
    is sampled. Returns a function of the phase. Differences from the signal are what a hanging part shows against the
    part that carries it."""
    ident = (cfg['name'], key, loops)
    if ident not in _SPRINGS:
        ticks, sub = cfg['ticks'] * loops, 4
        n = ticks * sub
        wn = TAU / period
        dt = 1.0 / sub
        x = v = 0.0
        samples = []
        for loop in range(40):
            samples = []
            for i in range(n):
                target = signal(i / n)
                v += (wn * wn * (target - x) - 2 * zeta * wn * v) * dt
                x += v * dt
                samples.append(x)
        _SPRINGS[ident] = samples

    def at(phase):
        samples = _SPRINGS[ident]
        n = len(samples)
        u = (phase % 1.0) * n
        i = int(u)
        f = u - i
        return samples[i % n] * (1 - f) + samples[(i + 1) % n] * f
    return at


def lag_of(cfg, key, signal, period, zeta, loops=1):
    """The spring's response minus the signal: how far a hanging part trails what carries it, at a phase."""
    spring = follow(cfg, key, signal, period, zeta, loops)
    return lambda phase: spring(phase) - signal(phase)


def orthonormal(m):
    """The nearest rotation to a blend of two rotations (Gram-Schmidt on its columns)."""
    x = quadruped.unit([m[i][0] for i in range(3)])
    y = quadruped.unit(quadruped.sub([m[i][1] for i in range(3)], quadruped.scale(x, quadruped.dot([m[i][1] for i in range(3)], x))))
    z = quadruped.cross(x, y)
    return [[x[i], y[i], z[i]] for i in range(3)]


def body(rig, cfg, phase, pose, hist, vary=None):
    """Height, sway and the turns of hips and upper body, the arms, the head, ears, tank and tail; all closed loops.

    `phase` is the place in one stride cycle. A clip that plays `cycles` strides over has its legs, pelvis and upper
    body identical in each (the feet are planted by them) and its loose parts (head, arms, ears, tank, tail) different:
    `vary` = (u, cycles), u the place in the whole loop, switches that on. Each part then has its own slow swell of
    amplitude and its own drift of timing over the loop, so no two strides look alike, and its spring runs over the
    whole loop. Events (a look, a twitch) are placed in the whole loop."""
    c, W0 = cfg, rig.still
    rest = rig.rest
    K = c.get('cycles', 1)
    u = vary[0] if vary else phase
    V = vary is not None and K > 1
    amount, drift = (c['vary'], c['drift']) if V else (0.0, 0.0)

    def swell(off, amp=1.0, q=None):
        """An amplitude that wanders by +-`amount` over the whole loop, each part at its own offset."""
        return 1 + amount * amp * math.sin(TAU * ((u if q is None else q) + off))

    def slide(off, q=None):
        """A part's timing, in cycles, that drifts over the whole loop."""
        return drift * math.sin(TAU * ((u if q is None else q) + off))

    def spring(key, f, period, zeta):
        """The lag of a spring driven by f(cycle phase, loop place); over the whole loop when the cycles differ."""
        if V:
            return lag_of(cfg, key, lambda q: f((K * q) % 1.0, q), period, zeta, K)(u)
        return lag_of(cfg, key, lambda q: f(q, q), period, zeta)(phase)

    bob_terms = ((c['bob'], 2, c['high']), (c['bob2'], 4, c['high'] + 0.03), (c['bob_side'], 1, c['high'] + 0.2))
    bob = harm(phase, *bob_terms)
    smooth_bob = (bob_terms[0], bob_terms[2])     # what the hanging parts feel: the slow terms, not the sharpening 4x one
    land = sum(a * bump(phase, at, 0.13) for at, a in c['dip'])      # the weight settles into each foot as it lands
    skip = sum(a * bump(phase, at, w) for at, w, a in c['hop'])      # the little hop: an extra rise while both feet are off the floor
    pose[UPPER][7] = (rest[UPPER][7] - c['height'] - bob + land - skip
                      - c['breath_bob'] * math.sin(TAU * c['breaths'] * phase - 0.6) * (1 + 0.3 * math.sin(TAU * phase)))
    weight = sum(a * bump(phase, at, w) for at, w, a in c['weight'])     # the idle's slow shifts of weight
    pose[UPPER][6] = rest[UPPER][6] + weight + harm(phase, (c['shift'], 1, c['roll_at']), (c['shift2'], 3, c['roll_at'] + 0.07))
    hp = c['hip_tilt'] + harm(phase, (c['hip_pitch'], 2, c['pitch_at']), (c['hip_pitch1'], 1, c['pitch_at'] + 0.12))
    hy = harm(phase, (c['hip_yaw'], 1, c['yaw_at']), (c['hip_yaw2'], 3, c['yaw_at'] + 0.05))
    hr = weight * c['weight_roll'] + harm(phase, (c['hip_roll'], 1, c['roll_at'] + 0.5), (c['hip_roll2'], 3, c['roll_at'] + 0.57))
    lag = c['lag']
    up = c['lean'] + harm(phase - lag, (c['pitch'], 2, c['pitch_at']), (c['pitch1'], 1, c['pitch_at'] + 0.12))
    uy = -c['counter'] * hy + harm(phase - lag, (c['yaw'], 1, c['yaw_at'] + 0.1))
    ur = harm(phase - lag, (c['roll'], 1, c['roll_at']), (c['roll2'], 3, c['roll_at'] + 0.06)) - weight * c['weight_roll'] * 0.6
    breath = c['breath'] * math.sin(TAU * c['breaths'] * phase) * (1 + 0.3 * math.sin(TAU * phase + 1))
    up += breath
    Wt = {0: [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}
    Wt[UPPER] = mul(rot([up, uy, ur]), rig.R(W0, UPPER))
    Wt[HIPS] = mul(rot([hp, hy, hr]), rig.R(W0, HIPS))

    def put(bone, parent, delta):
        Wt[bone] = mul(delta, rig.R(W0, bone))
        set_rot(pose, bone, mul(tr(Wt[parent]), Wt[bone]), hist)

    def local(bone, degrees):
        """The bone turned about its own axes from its rest pose by the given degrees."""
        set_rot(pose, bone, mul(mmd.rot_matrix(*rest[bone][3:6]), rot(degrees)), hist)

    if not V:
        set_rot(pose, UPPER, Wt[UPPER], hist)
        put(HIPS, UPPER, rot([hp, hy, hr]))
    else:
        Wt[HIPS] = mul(rot([hp, hy, hr]), rig.R(W0, HIPS))
    # the head keeps most of its gaze: it follows the upper body by `steady`, and nods a beat after the step
    nod = swell(0.1) * harm(phase - c['nod_lag'] - slide(0.3), (c['nod'], 2, c['nod_at']), (c['nod2'], 1, c['nod_at'] + 0.1))
    look = swell(0.4) * c['look'] * harm(phase - slide(0.6), (1, 1, c['look_at']), (0.3, 2, c['look_at'] + 0.1))
    gaze = sum(a * bump(u, at, w) for at, w, a in c['gaze'])
    tilt = sum(a * bump(u, at, w) for at, w, a in c['tilt'])
    head_pitch = up - c['steady'] * (up - c['lean']) - c['head'] + nod + c['head_up']
    head_yaw = uy * 0.5 + look + gaze
    cock = swell(0.7) * c['head_roll'] * harm(phase - slide(0.2), (1, 1, c['roll_at'] + 0.2))      # the head cocks from side to side a beat behind the chest
    put(HEAD, UPPER, rot([head_pitch, head_yaw, ur * 0.6 + tilt + cock]))
    # the ears: loose fins hinged at the head's sides; each trails the head by a spring of its own (the right one a little
    # behind, softer and slower), driven by the pelvis' rise and fall and by the head's own turns; they overshoot and settle
    for side, (bone, sign) in EARS.items():
        late = c['ear_late'] if side == 'R' else 0.0
        slow = 1.0 if side == 'L' else c['ear_slow']
        offset = 0.0 if side == 'L' else 0.37

        def drive(p, q, late=late, offset=offset):
            return ((c['ear_bob'] * swell(0.2 + offset, 1.0, q) * harm(p - late - slide(0.15 + offset, q), *smooth_bob)
                     + c['ear_nod'] * harm(p - late, (c['nod'] + c['pitch'], 2, c['nod_at']))))

        def sway(p, q, late=late, offset=offset):
            return c['ear_sway'] * swell(0.5 + offset, 1.0, q) * harm(p - late - slide(0.45 + offset, q), (c['hip_yaw'], 1, c['yaw_at']), (c['yaw'], 1, c['yaw_at'] + 0.1))
        drop = spring(('ear', side), drive, c['ear_period'] * slow, c['ear_zeta'])
        out = spring(('sway', side), sway, c['ear_period'] * 1.25 * slow, c['ear_zeta'])
        out += sum(a * bump(u - late, at, w) for at, w, a in c['gaze']) * 0.2 * c['ear_sway']
        twitch = sum(a * bump(u - late, at, w) for at, w, a in c['ear_twitch'].get(side, ()))
        local(bone, [c['ear_rest'] - drop - twitch, sign * (out + c['ear_out']), 0])
    # the air tank hangs from the back of the head and swings on after it
    swing = spring('tank', lambda p, q: swell(0.25, 1.0, q) * (harm(p, *smooth_bob) * c['tank_bob'] + c['tank_pitch'] * harm(p, (1, 2, c['pitch_at']))),
                   c['tank_period'], c['tank_zeta'])
    sway_t = spring('tank_y', lambda p, q: swell(0.6, 1.0, q) * c['tank_sway'] * harm(p - slide(0.2, q), (c['hip_yaw'], 1, c['yaw_at'])), c['tank_period'] * 1.15, c['tank_zeta'])
    for k, b in enumerate(TANK):
        local(b, [(swing if k < 2 else 0.6 * swing), (sway_t if k == 0 else 0), 0])
    # the tail, held out and up behind: a chain of springs, each link later, looser and more overshooting than the last
    for k, b in enumerate(TAIL):
        period = c['tail_period'] * (1 + 0.35 * k)
        drive = lambda p, q, k=k: swell(0.35, 1.0, q) * (c['tail_bob'] * harm(p, *smooth_bob) + c['tail_hip'] * harm(p, (c['hip_pitch'], 2, c['pitch_at'])))
        pitch = spring(('tail', k), drive, period, c['tail_zeta'])
        yaw_d = lambda p, q, k=k: swell(0.75, 1.0, q) * c['tail_sway'] * harm(p - slide(0.1, q), (c['hip_yaw'], 1, c['yaw_at'])) + sum(
            a * bump(u if q is None else q, at, w) for at, w, a in c['tail_swish'])
        yaw = spring(('tail_y', k), yaw_d, period, c['tail_zeta'])
        carried = c['tail_up'] if k == 0 else c['tail_up2'] if k == 1 else 0
        local(b, [carried + pitch * (1 + 0.3 * k), yaw * (1 + 0.3 * k), 0])
    # the arms swing against the legs on the shoulders; the elbows and hands trail late like pendulums, the arm that
    # holds the harpoon less than the free one
    for side, (sh, el, hand, sd) in ARMS.items():
        leg = 'LH' if side == 'R' else 'RH'       # an arm goes forward with the opposite leg
        shift = 0.0 if leg == 'LH' else 0.5
        amp = 1.0 if side == 'R' else c['arm_asym']
        off = 0.15 if side == 'R' else 0.55
        sw = lambda p, q=None, shift=shift, amp=amp, off=off: amp * c['arm'] * swell(off, 1.0, q) * harm(p - slide(off + 0.2, q), (1, 1, c['arm_at'] + shift))
        swing_arm = sw(phase)
        flex_lag = spring(('arm', side), lambda p, q: sw(p, q), c['arm_period'] * (1 if side == 'R' else 1.2), 0.35)
        out = c['arm_out'] * sd
        gest = sum(a * bump(u, at, w) for at, w, a in c['gesture'].get(side, ()))
        Wt[sh] = mul(Wt[UPPER], mul(rot([swing_arm + c['arm_lift'] + gest, 0, out]), mul(tr(rig.R(W0, UPPER)), rig.R(W0, sh))))
        set_rot(pose, sh, mul(tr(Wt[UPPER]), Wt[sh]), hist)
        bend = sum(a * bump(u, at, w) for at, w, a in c['bend'].get(side, ()))
        flex = c['elbow'] * swell(off + 0.2) * harm(phase - slide(off + 0.3), (1, 1, c['arm_at'] + 0.1 + shift)) - c['arm_lag'] * flex_lag
        elbow_turn = flex + c['elbow_extra'] + bend
        local(el, [elbow_turn, 0, 0])
        # the hand keeps the weapon's pitch in the world (the harpoon is 450 units long: it would stab the floor if it
        # turned with the arm), only a little of the arm's swing and its pendulum lag reaching it
        Wt[el] = mul(Wt[sh], mul(mmd.rot_matrix(*rest[el][3:6]), rot([elbow_turn, 0, 0])))
        held = c['hold'][side]
        chain = mul(Wt[el], mmd.rot_matrix(*rest[hand][3:6]))
        carried = mul(Wt[UPPER], mul(tr(rig.R(W0, UPPER)), rig.R(W0, hand)))      # as if rigid with the upper body
        wob = rot([-0.3 * c['arm_lag'] * flex_lag - 0.8 * held * up, 0, 0])
        Wt[hand] = mul(wob, [[chain[i][j] * (1 - held) + carried[i][j] * held for j in range(3)] for i in range(3)])
        Wt[hand] = orthonormal(Wt[hand])
        set_rot(pose, hand, mul(tr(Wt[el]), Wt[hand]), hist)


def vary_cycles(rig, cfg, frames):
    """The loose parts of every stride of a clip that plays several, each stride with its own swell and drift; the
    legs, pelvis and upper body are left as they were, and the closing frame repeats the first."""
    ticks, K = cfg['ticks'], cfg.get('cycles', 1)
    hist = {}
    for index in range(ticks * K):
        body(rig, cfg, (index % ticks) / ticks, frames[index], hist, vary=(index / (ticks * K), K))
    for b in range(1, len(frames[0])):
        frames[-1][b] = list(frames[0][b])
    return frames


PROFILE = dict(
    species=SPECIES, name='Divermon', source=SOURCE,
    parents=[-1, 0, 1, 2, 3, 1, 5, 6, 1, 8, 8, 10, 11, 8, 1, 14, 15, 16, 14, 18, 19, 20, 14, 22, 23, 24],
    pelvis=UPPER, chest=None, neck=None, head=HEAD, tail=(), loose=(),
    legs=LEGS, pole_world=True, rest_plane=True, pole={False: [0.3, 0.0, -1.0]},
    paw_flat={},          # filled below: each flipper's world turn
    sole={False: [0, 36, -47]},
    reach={'front': 0, 'hind': 0},
    fold={False: 50}, clear=3,
    speed_range={0: (0, 0), 2: (15, 31), 3: (10, 20), 4: (35, 52)},
    body=body, vary=vary_cycles, floor=3, stance_slip=0.2, events=lambda slot, total: face_events(slot, total),
    gaits={},
)
COMMON = dict(
    kind='walk', snap=False, arc=0.65, clear_ease=0.1, world_ease=True, fold_soft=10, slip=0.0, steps=('LH', 'RH'),
    reach={'front': 0, 'hind': -50}, lift={'front': 0, 'hind': 26}, curl={'front': 0, 'hind': 0}, peel={'front': 0, 'hind': 0},
    out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 0}, track={'front': 0, 'hind': -8}, heel=0,
    high=0.1, bob=6, bob2=0.5, bob_side=0.5, height=0, shift=4, shift2=0, roll_at=0.3,
    hip_tilt=0, hip_pitch=1, hip_pitch1=0.3, hip_yaw=4, hip_yaw2=0, hip_roll=2, hip_roll2=0,
    lean=0, pitch=1.5, pitch1=0.5, pitch_at=0.15, yaw=1, counter=0.9, roll=2.5, roll2=0, yaw_at=0.05, lag=0.07,
    steady=0.8, head=0, head_up=0, nod=1, nod2=0.5, nod_at=0.2, nod_lag=0.06, look=0, look_at=0.3,
    breath=0, breaths=4, breath_bob=0,
    arm=14, arm_at=0.0, arm_lift=0, arm_out=0, elbow=6, elbow_extra=0, arm_period=5, arm_lag=0.35, hold={'R': 0.5, 'L': 0.95},
    ear_rest=0, ear_out=0, ear_bob=0.8, ear_nod=1.0, ear_sway=0.6, ear_period=4.5, ear_zeta=0.25, ear_late=0.035, ear_twitch={},
    tank_bob=0.15, tank_pitch=1.0, tank_sway=0.3, tank_period=5,
    tail_bob=0.5, tail_hip=1.0, tail_sway=0.8, tail_period=4.5, tail_up=8, tail_up2=4, tail_swish=(),
    gaze=(), tilt=(), gesture={}, bend={}, weight=(), weight_roll=0, dip=(), hop=(), head_roll=0, cycles=1, vary=0.25, drift=0.03,
    ear_slow=1.12, tank_zeta=0.35, tail_zeta=0.42, arm_asym=0.8,
)
PROFILE['gaits'] = {
    # the idle is a long loop (8 s) with its looks, twitches and weight shifts at irregular places
    0: dict(COMMON, name='idle', ticks=240, speed=0, steps=(),
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 1.0, 'RH': 1.0}, track={'front': 0, 'hind': 0},
            height=-4, bob=1.0, bob2=0, bob_side=0, shift=2, ear_period=9, tank_period=14, tail_period=12, arm_period=14, hip_yaw=0,
            hip_roll=1.5, hip_pitch=0.5, hip_pitch1=0, roll=1.5, yaw=0, pitch=0.5, pitch1=0, counter=0, breath=1.4, breath_bob=2.2, breaths=4,
            nod=0.6, nod2=0, arm=0, elbow=3,
            weight=((0.12, 0.09, 7), (0.4, 0.11, -6), (0.66, 0.08, 8), (0.88, 0.07, -5)), weight_roll=0.5,
            gaze=((0.08, 0.04, 14), (0.27, 0.05, -10), (0.52, 0.06, 22), (0.59, 0.03, -6), (0.83, 0.04, -16)),
            tilt=((0.52, 0.07, 6), (0.27, 0.05, -4)),
            ear_twitch={'R': ((0.19, 0.02, 9), (0.71, 0.025, 7)), 'L': ((0.45, 0.02, 8), (0.9, 0.018, 6), (0.33, 0.015, 5))}, ear_bob=1.2,
            tail_swish=((0.24, 0.04, 10), (0.61, 0.05, -12), (0.93, 0.03, 8)), tail_sway=0, tail_bob=1.0, tail_hip=0,
            gesture={'R': ((0.3, 0.1, -6), (0.77, 0.07, 5))}, bend={'R': ((0.3, 0.1, 12), (0.77, 0.07, -8))}),
    2: dict(COMMON, name='walk', ticks=16, speed=18, cycles=2, dip=((0.03, 3.5), (0.53, 2.5)), hop=((0.0, 0.15, 3), (0.5, 0.15, 3)),
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.46, 'RH': 0.46}, lift={'front': 0, 'hind': 32},
            height=15, bob=10, bob2=0.8, bob_side=1.8, high=0.28, hip_yaw=8, hip_roll=5.5, roll=6, head_roll=4, arm=18, elbow=8, shift=12, counter=1.25,
            lag=0.1, nod_lag=0.12, pitch=3, pitch1=1.5, nod=2.2, look=3, ear_twitch={'R': ((0.62, 0.03, 8),), 'L': ((0.19, 0.03, 6),)}, tail_swish=((0.45, 0.07, 9),),
            tank_bob=0.5, tank_pitch=2.2, tank_sway=1.0, ear_bob=1.2, ear_sway=1.0, tail_bob=0.8, tail_sway=1.4),
    3: dict(COMMON, name='tired walk', ticks=18, speed=12, cycles=2, dip=((0.03, 3), (0.53, 2)), hop=((0.0, 0.12, 2), (0.5, 0.12, 2)),
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.58, 'RH': 0.58}, lift={'front': 0, 'hind': 22},
            height=0, bob=8, bob_side=1.5, high=0.3, lean=11, head=-8, arm=6, elbow=3, hip_yaw=5.5, hip_roll=4.5, shift=10, roll=5.5, head_roll=3,
            tank_bob=0.4, tank_pitch=1.8, tank_sway=0.8, tail_bob=0.8, tail_sway=1.1,
            counter=1.2, lag=0.12, nod_lag=0.14, pitch=2.5, pitch1=1.2, nod=1.5, look=2, ear_rest=6, ear_bob=1.3, tail_up=12, tail_up2=6, ear_period=6, tank_period=7,
            tail_period=6, arm_period=7, tail_swish=((0.7, 0.08, 7),)),
    4: dict(COMMON, name='run', kind='trot', ticks=12, speed=36, cycles=2, dip=((0.02, 3), (0.52, 2.2)), hop=((0.4, 0.15, 3), (0.9, 0.15, 3)),
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.3, 'RH': 0.3}, height=16, high=0.4, world_ease=True, arc=0.5,
            lift={'front': 0, 'hind': 50}, bob=9, bob2=1.0, bob_side=1.5, lean=17, head=7, arm=32, elbow=10, elbow_extra=20, hip_yaw=8, shift=8, head_roll=4,
            hip_roll=5, roll=6, counter=1.2, tank_bob=0.5, tank_pitch=2.2, tank_sway=1.0, tail_bob=0.8, lag=0.1, nod_lag=0.1, pitch=3, pitch1=1.5, nod=2, look=2.5, ear_bob=2.2, tail_up=14, tail_up2=6, ear_period=3.5, tank_period=4,
            tail_period=3.5, arm_period=4, ear_twitch={'R': ((0.4, 0.03, 8),)}),
}


# the face (tick, state) plans of each clip: blinks and a mouth that works with the breath; every plan ends in its first
# state (open eyes, the grin as painted), so a clip loops and a cut one is mended by the next
FACE = {
    # three blinks (one a quick double) and a mouth that eases open on each exhale, a yawn and a closed-lips moment
    0: dict(eyes=face.blink(31) + face.blink(97) + face.blink(104) + face.blink(176),
            mouth=[(14, face.AJAR), (40, face.REST), (78, face.AJAR), (103, face.REST), (139, face.AJAR), (146, face.MOPEN),
                   (160, face.AJAR), (170, face.REST), (196, face.MSHUT), (205, face.REST), (226, face.AJAR), (236, face.REST)]),
    2: dict(eyes=face.blink(21), mouth=[(4, face.AJAR), (11, face.REST), (20, face.AJAR), (28, face.REST)]),
    3: dict(eyes=face.blink(5, slow=True) + [(24, face.HALF), (33, face.OPEN)],
            mouth=[(3, face.AJAR), (13, face.MOPEN), (18, face.AJAR), (24, face.MOPEN), (30, face.AJAR), (34, face.REST)]),
    4: dict(eyes=face.blink(15),
            mouth=[(1, face.MOPEN), (4, face.WIDE), (8, face.MOPEN), (10, face.AJAR), (13, face.MOPEN), (16, face.WIDE),
                   (20, face.MOPEN), (22, face.AJAR), (23, face.REST)]),
}


def face_events(slot, total):
    plan = FACE[slot]
    return face.events(plan['eyes'], plan['mouth'], total)


def prepare(model, skeleton):
    """Each flipper's flat standing turn in the world: the same small splay outwards on both sides (the model's own rest
    pose turns the x < 0 one 77 degrees out)."""
    flat = {}
    for name, (up, lo, paw, side, front) in LEGS.items():
        flat[name] = [0, -side * SPLAY, 0]
    PROFILE['paw_flat'] = flat


def build(data, skeleton):
    old = mmd.MMD.parse(data, len(skeleton))
    old.type = SPECIES
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = len(skeleton)
    prepare(old, skeleton)
    _SPRINGS.clear()
    result, proof = quadruped.build(data, skeleton, PROFILE)
    # slot 33 (the battle idle) was a second copy of the old idle: it plays the new idle too, and the copy goes
    model = mmd.MMD.parse(result, len(skeleton))
    model.type = SPECIES
    model.anims.table[33] = model.anims.table[0]
    used = sorted({i for i in model.anims.table if i is not None})
    renumber = {i: k for k, i in enumerate(used)}
    model.anims.anims = [model.anims.anims[i] for i in used]
    model.anims.table = [None if i is None else renumber[i] for i in model.anims.table]
    result = model.build()
    proof['output_sha256'] = hashlib.sha256(result).hexdigest()
    proof['changed_slots'] = sorted(set(proof['changed_slots']) | {33})
    proof['storage'] = motionstorage.require(result, len(skeleton))
    return result, proof


def texture(tim):
    """The texture before this change (SOURCE_TIM) -> the same with the eye and mouth frames in their spare texels."""
    if hashlib.sha256(tim).hexdigest() != SOURCE_TIM:
        raise ValueError('Divermon needs the texture it had before this change')
    t = mmd.Tim4(tim)
    face.stamp(t)
    out = t.to_bytes()
    assert len(out) == len(tim)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    p.add_argument('--tex', type=Path, help='the texture before this change (edit.py get 304), with --out-tex')
    p.add_argument('--out-tex', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/304-divermon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    if a.tex:
        a.out_tex.write_bytes(texture(a.tex.read_bytes()))
    text = json.dumps(proof, indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
