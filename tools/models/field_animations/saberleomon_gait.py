"""SaberLeomon as a big cat: a lateral-sequence walk, a bounding gallop with a flight phase, a flexing spine, a trailing tail.

What the imported clips did (cycle lengths and root speeds are kept):

- Everything moved at the legs' beat. The walk was a trot and the run a pace (same-side legs together, no flight phase),
  the head and neck held still, the chest only bobbed and the tail replayed the idle's swish whatever the gait was: a
  machine walking under a statue.
- The mane (the head's mesh) hangs as a bowl in front of the chest and its lower tufts reach down to ankle height, right
  where the forelegs swing: the paws and forearms went through it on nearly every tick, even in the idle.

Now:

- The legs keep their own foot paths but are re-timed (`TIMING`): the walks step hind, fore, hind, fore on one side after
  the other (lateral sequence); the run is a bound, the hind pair then the fore pair, with the stance squeezed into a few
  ticks so all four paws are in the air for about three ticks of every fourteen. A two-bone IK (`_ik`) bends each leg to
  the re-timed foot with the paw's world rotation held, so the planting stays clean and slides less than before.
- The body answers the feet (`pitch`, `hips_pitch`, `bounce`): the chest pitches and rises with the foot support, the hips
  pitch against it (the spine flexes and extends), the head follows later and smaller with a bob, and the tail is carried
  up in the run and lower in the tired walk, each segment trailing the body on closed periodic lags.
- The forelegs sit `arms_back` units further back, and the head is carried higher and a little forward (`HEAD_TABLE`): a
  lift and a pitch for every tick, found offline by `fit()` as the smallest smoothed carriage that leaves every leg outside
  the mane's and jaw's triangles on the stored (coalesced) clips.

Everything else (the mesh, the skeleton, the jaw, the sounds, root travel, every other program) stays exact. `fit()`
needs numpy and the animation studio's mesh helper; `build()` needs neither.
"""
import copy
import math

import animsheet
import mmd
import motioncyclelayer
import motionstorage
import retarget as R
from motiondiscidentity import changed_programs
from tools.models.field_animations.channels import coalesce, replace_channels

SPECIES = 258
CHEST, NECK, HEAD, JAW = 1, 2, 3, 4
FORE_ROOTS = (5, 8)               # right (+x) and left forelegs: shoulder, forearm, paw
FORE_PAWS = (7, 10)
HIPS = 11
HIND_ROOTS = (15, 19)
TAIL = (12, 13, 14)
SLOTS = (0, 1, 2, 3, 4)           # idle, its variant, walk, condition walk, run
TOLERANCE = 3
# which pose channels are rewritten: rotations of the swaying bones, translations of the head carriage
CHANNELS = {(b, c) for b in (CHEST, HEAD, HIPS, 5, 6, 7, 8, 9, 10, 15, 16, 17, 18, 19, 20, 21, 22) + TAIL for c in (3, 4, 5)} | \
           {(b, c) for b in (NECK, HEAD) + FORE_ROOTS for c in (7, 8)} | {(CHEST, 7)}
KEEP_LEGS = FORE_ROOTS + HIND_ROOTS        # world rotation held through the body's sway
# per slot: roll and yaw in degrees of the chest sway, hips yaw against it (share), head follow (ticks late, share of the
# chest's sway), slow head drift (yaw degrees over the whole loop), tail (kept share of the old swish, pitch and yaw
# gains in degrees for the three segments, delays in ticks, slow yaw drift), forelegs set back
PROFILE = {
    0: dict(gait=False, roll=1.0, yaw=1.4, hips=.6, head_lag=3., head_share=.8, head_drift=1.6, pitch=.7, hips_pitch=.8,
            bounce=1.5, mod=0., smooth=0, head_follow=.3, head_bob=0., tail_up=(3., 4., 5.),
            keep=.55, t_pitch=(2., 3.5, 5.), t_yaw=(1.5, 3., 5.), t_lag=(1.5, 3., 4.5), t_drift=4., arms_back=25.),
    1: dict(gait=False, roll=1.0, yaw=1.4, hips=.6, head_lag=3., head_share=.8, head_drift=1.6, pitch=.7, hips_pitch=.8,
            bounce=1.5, mod=0., smooth=0, head_follow=.3, head_bob=0., tail_up=(3., 4., 5.),
            keep=.55, t_pitch=(2., 3.5, 5.), t_yaw=(1.5, 3., 5.), t_lag=(1.5, 3., 4.5), t_drift=4., arms_back=25.),
    2: dict(gait=True, roll=3., yaw=3.5, hips=.6, head_lag=3., head_share=.7, head_drift=2.2, pitch=3.5, hips_pitch=.9,
            bounce=14., mod=.12, smooth=2, head_follow=.5, head_bob=8., tail_up=(3., 5., 7.),
            keep=.45, t_pitch=(4., 6., 8.), t_yaw=(4., 7., 10.), t_lag=(2., 4., 6.), t_drift=5., arms_back=25.),
    3: dict(gait=True, roll=2.5, yaw=2.8, hips=.6, head_lag=3., head_share=.7, head_drift=2.2, pitch=5., hips_pitch=.9,
            bounce=9., mod=.12, smooth=2, head_follow=.5, head_bob=4., tail_up=(-3., -5., -8.),
            keep=.45, t_pitch=(3., 5., 7.), t_yaw=(2.5, 4.5, 6.), t_lag=(2., 4., 6.), t_drift=5., arms_back=25.),
    4: dict(gait=True, roll=1.5, yaw=2., hips=.6, head_lag=2.5, head_share=.7, head_drift=2.2, pitch=9., hips_pitch=.9,
            bounce=34., mod=.12, smooth=2, head_follow=.5, head_bob=14., tail_up=(8., 12., 16.),
            keep=.4, t_pitch=(2., 3., 4.), t_yaw=(2., 3., 4.), t_lag=(2., 4., 6.), t_drift=5., arms_back=25.),
}
# carriage of the head per tick (without the closing tick): (lift, pitch in degrees, nose up negative); filled by fit()
HEAD_FORWARD = 30.
HEAD_TABLE = {
    0: (
        (13.2, 0.0), (14.8, 0.0), (18.8, 0.0), (19.2, 0.0), (20.2, 0.0), (24.8, 0.0),
        (28.8, 0.0), (29.0, 0.0), (32.0, 0.0), (35.0, 0.0), (35.0, 0.0), (35.0, 0.0),
        (32.0, 0.0), (29.0, 0.0), (26.0, 0.0), (22.5, 0.0), (17.0, 0.0), (12.0, 0.0),
        (7.0, 0.0), (4.5, 0.0), (4.0, 0.0), (4.0, 0.0), (4.0, 0.0), (4.0, 0.0),
        (4.0, 0.0), (4.0, 0.0), (4.0, 0.0), (4.0, 0.0), (4.0, 0.0), (4.0, 0.0),
        (4.0, 0.0), (4.0, 0.0), (4.2, 0.0), (5.5, 0.0), (8.0, 0.0), (10.5, 0.0),
        (11.8, 0.0), (12.2, 0.0),
    ),
    1: (
        (64.0, 0.0), (64.0, 0.0), (64.0, 0.0), (64.0, 0.0), (64.0, 0.0), (63.8, 0.0),
        (62.5, 0.0), (59.5, 0.0), (54.8, 0.0), (49.5, 0.0), (46.0, 0.0), (45.8, 0.0),
        (48.0, 0.0), (50.5, 0.0), (54.8, 0.0), (55.0, 0.0), (55.2, 0.0), (56.2, 0.0),
        (58.0, 0.0), (57.0, 0.0), (58.8, 0.0), (59.8, 0.0), (60.0, 0.0), (63.2, 0.0),
        (64.2, 0.0), (65.8, 0.0), (66.8, 0.0), (67.0, 0.0), (64.0, 0.0),
    ),
    2: (
        (45.2, -0.4), (34.8, 0.0), (31.8, 0.0), (34.8, 0.0), (38.2, -0.4), (42.5, -1.9),
        (53.8, -4.1), (70.2, -5.6), (81.2, -6.0), (84.0, -6.0), (84.0, -6.0), (84.0, -6.0),
        (83.0, -6.0), (79.0, -5.6), (71.8, -4.1), (61.8, -1.9), (49.2, -0.4), (38.8, 0.0),
        (35.5, 0.0), (37.5, 0.0), (39.5, 0.0), (41.5, -0.4), (47.5, -1.9), (56.5, -4.1),
        (62.5, -5.6), (64.0, -6.0), (64.0, -6.0), (64.0, -6.0), (64.0, -6.0), (64.0, -5.6),
        (62.8, -4.1), (56.8, -1.9),
    ),
    3: (
        (63.5, -1.9), (70.2, -0.4), (71.0, 0.0), (71.0, 0.0), (71.0, 0.0), (71.0, -0.4),
        (67.5, -1.9), (65.8, -4.1), (63.8, -5.6), (63.2, -6.0), (63.8, -6.0), (64.0, -6.0),
        (64.0, -6.0), (64.0, -6.0), (64.5, -5.6), (66.5, -4.1), (69.5, -1.9), (71.5, -0.4),
        (72.0, 0.0), (72.0, 0.0), (72.0, 0.0), (71.5, -0.4), (68.5, -1.9), (61.2, -4.1),
        (52.2, -5.6), (46.2, -6.0), (44.2, -6.0), (44.0, -6.0), (44.0, -6.0), (44.8, -6.0),
        (48.5, -5.6), (56.0, -4.1),
    ),
    4: (
        (74.5, 0.0), (75.0, 0.0), (75.0, 0.0), (75.0, 0.0), (73.8, 0.0), (63.8, 0.0),
        (48.8, 0.0), (34.5, 0.0), (32.5, 0.0), (42.0, 0.0), (53.2, 0.0), (60.2, 0.0),
        (64.0, 0.0), (66.5, 0.0), (70.8, 0.0), (71.0, 0.0), (71.0, 0.0), (71.0, 0.0),
        (69.8, 0.0), (60.2, 0.0), (47.5, 0.0), (37.0, 0.0), (37.5, 0.0), (47.0, 0.0),
        (57.2, 0.0), (62.8, 0.0), (67.0, 0.0), (70.0, 0.0), (73.0, 0.0), (73.0, 0.0),
        (73.0, 0.0), (70.0, 0.0), (65.8, 0.0), (56.0, 0.0), (42.2, 0.0), (30.2, 0.0),
        (29.8, 0.0), (39.2, 0.0), (50.8, 0.0), (59.2, 0.0), (65.0, 0.0), (69.2, 0.0),
    ),
}
NECK_SHARE = .4                    # share of the lift that the neck carries


def _rx(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def _ry(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def _rz(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def _mul(*ms):
    out = ms[0]
    for m in ms[1:]:
        out = R.m3mul(out, m)
    return out


def _inv3(m):
    (a, b, c), (d, e, f), (g, h, i) = m
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    return [[(e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det],
            [(f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det],
            [(d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det]]


def _polar(m):
    """The rotation nearest to a matrix (Newton iteration of the polar decomposition)."""
    y = m
    for _ in range(12):
        inv_t = R.m3t(_inv3(y))
        y = [[(y[r][c] + inv_t[r][c]) / 2 for c in range(3)] for r in range(3)]
    return y


def _mean_rot(ms):
    n = len(ms)
    return _polar([[sum(m[r][c] for m in ms) / n for c in range(3)] for r in range(3)])


def _wrap(values, x):
    """Linear sample of a periodic list at the fractional tick x."""
    n = len(values)
    i = math.floor(x)
    k = x - i
    return values[i % n] * (1 - k) + values[(i + 1) % n] * k


def _smooth(values, passes=1):
    """Periodic 1-2-1 smoothing."""
    for _ in range(passes):
        n = len(values)
        values = [(values[i - 1] + 2 * values[i] + values[(i + 1) % n]) / 4 for i in range(n)]
    return values


def _norm(values):
    mean = sum(values) / len(values)
    centred = [v - mean for v in values]
    peak = max(abs(v) for v in centred) or 1.
    return [v / peak for v in centred]


def _world_pose(rig, pose, locals_, holds):
    """Set the local rotations in `locals_` ({bone: matrix}); every bone in `holds` ({bone: world rotation}) is
    re-derived so that it keeps that world rotation. Bones go parent first."""
    world = [None] * len(rig)
    for b in range(len(rig)):
        par = rig[b][1]
        if b in holds:
            local = _mul(R.m3t(world[par]) if par >= 0 else _ident(), holds[b])
        elif b in locals_:
            local = locals_[b]
        else:
            local = R.rot_of(pose[b])
        if b in holds or b in locals_:
            pose[b][3:6] = [round(v) for v in mmd.matrix_euler(local, pose[b][3:6])]
            local = R.rot_of(pose[b])           # what the stored angles really give
        world[b] = _mul(world[par], local) if par >= 0 else local
    return world


def _ident():
    return [[1, 0, 0], [0, 1, 0], [0, 0, 1]]


LEGS = ((5, 7, 0), (8, 10, 0), (16, 18, 1), (20, 22, 1))     # chain start, end (paw), 0 fore / 1 hind: side A, B, A, B
THIGHS = (15, 19)
LEG_BONES = (5, 6, 7, 8, 9, 10, 15, 16, 17, 18, 19, 20, 21, 22)
# the stride period, the tick each foot lands on, per slot: (side A fore, side B fore, side A hind, side B hind), and the
# stance length the feet are given (None: the clip's own). The
# imported clips walk as a trot (diagonal pairs in step) and run as a pace; the walks become a lateral-sequence walk
# (hind, same-side fore a quarter later, other hind, other fore) and the run a bound: the forelegs land together, the
# hindlegs next, then every foot is off the ground for a few ticks.
TIMING = {2: (16, (4, 12, 0, 8), None), 3: (16, (4, 12, 0, 8), None), 4: (14, (0, 1, 9, 10), 5)}


def _first_landing(ys, period):
    ground, top = max(ys), min(ys)
    stance = [y > ground - .4 * (ground - top) for y in ys]
    edges = [t for t in range(len(ys)) if stance[t] and not stance[t - 1]]
    return (edges[0] if edges else 0) % period


def _v_sub(a, b):
    return [x - y for x, y in zip(a, b)]


def _v_add(a, b):
    return [x + y for x, y in zip(a, b)]


def _v_mul(a, k):
    return [x * k for x in a]


def _v_dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _v_len(a):
    return math.sqrt(_v_dot(a, a))


def _ik(rig, pose, start, target):
    """Bend the two-bone chain start, start + 1 so that the end bone start + 2 reaches `target` (character frame), the end
    bone keeping its world rotation; the elbow stays on the side it was."""
    q = copy.deepcopy(pose)
    q[0] = [4096] * 3 + [0] * 6
    rots, pos = R.world_rots(rig, q), R.world_pos(rig, q)
    s_, e_, w_ = pos[start], pos[start + 1], pos[start + 2]
    l1, l2 = _v_len(_v_sub(e_, s_)), _v_len(_v_sub(w_, e_))
    d = _v_sub(target, s_)
    dist = min(max(_v_len(d), abs(l1 - l2) * 1.001), (l1 + l2) * .999)
    dirn = _v_mul(d, 1 / (_v_len(d) or 1.))
    wn = _v_add(s_, _v_mul(dirn, dist))
    along = (l1 * l1 - l2 * l2 + dist * dist) / (2 * dist)
    height = math.sqrt(max(l1 * l1 - along * along, 0.))
    off = _v_sub(_v_sub(e_, s_), _v_mul(dirn, _v_dot(_v_sub(e_, s_), dirn)))
    off = _v_mul(off, 1 / (_v_len(off) or 1.))
    en = _v_add(_v_add(s_, _v_mul(dirn, along)), _v_mul(off, height))
    r1 = R.m3mul(R.swing(_v_sub(e_, s_), _v_sub(en, s_)), rots[start])
    r2 = R.m3mul(R.swing(_v_sub(w_, e_), _v_sub(wn, en)), rots[start + 1])
    par = rig[start][1]
    for b, m in ((start, R.m3mul(R.m3t(rots[par]), r1)), (start + 1, R.m3mul(R.m3t(r1), r2)),
                 (start + 2, R.m3mul(R.m3t(r2), rots[start + 2]))):
        pose[b][3:6] = [round(v) for v in mmd.matrix_euler(m, pose[b][3:6])]


def _blend_vec(table, x, b, n):
    i = math.floor(x)
    k = x - i
    a, c = table[i % n][b], table[(i + 1) % n][b]
    return [u * (1 - k) + v * k for u, v in zip(a, c)]


def _blend_rot(table, x, b, n):
    i = math.floor(x)
    k = x - i
    a, c = table[i % n][b], table[(i + 1) % n][b]
    return _polar([[a[r][q] * (1 - k) + c[r][q] * k for q in range(3)] for r in range(3)])


def _clamp01(x):
    return max(0., min(1., x))


def _gait(feet, spec, n):
    """Body signals of a gait from the feet (feet[leg][tick] = (x, y, z), y down): body pitch (nose down +, normalised),
    body height above the ground (0..1), and the sway signals. `feet` is already in the new foot timing."""
    support = []
    for leg in feet:
        ground = max(p[1] for p in leg)
        support.append([_clamp01((p[1] - (ground - 14.)) / 10.) for p in leg])
    fore = [support[0][t] + support[1][t] for t in range(n)]
    hind = [support[2][t] + support[3][t] for t in range(n)]
    sm = spec['smooth']
    pitch = _norm(_smooth([f - h for f, h in zip(fore, hind)], sm))
    high = _norm(_smooth([-(f + h) for f, h in zip(fore, hind)], sm))
    lean = _smooth(_norm([-feet[1][t][1] + feet[0][t][1] for t in range(n)]), 1)
    reach = _smooth(_norm([feet[1][t][2] - feet[0][t][2] for t in range(n)]), 1)
    return pitch, high, lean, reach


def head_step(pose, lift, pitch):
    """The head's carriage: raised by `lift` (the neck takes its share), forward, and nose-up by `pitch` degrees (negative)."""
    pose[NECK][7] -= round(NECK_SHARE * lift)
    pose[HEAD][7] -= round((1 - NECK_SHARE) * lift)
    pose[HEAD][8] -= round(HEAD_FORWARD)
    pose[HEAD][3] += round(pitch * 4096 / 360)


def carriage(poses, rig, n, spec, slot):
    """Apply the legs' timing, the spine's pitch and bounce, the sway, the head and tail followers and the head carriage to
    poses[:n] (in place)."""
    old = [R.world_rots(rig, p) for p in poses[:n]]
    still = []
    for pose in poses[:n]:
        q = copy.deepcopy(pose)
        q[0] = [4096] * 3 + [0] * 6
        still.append(R.world_pos(rig, q))
    rest = [copy.deepcopy(p) for p in poses[:n]]
    owner = {5: 7, 6: 7, 7: 7, 8: 10, 9: 10, 10: 10, 15: 18, 16: 18, 17: 18, 18: 18, 19: 22, 20: 22, 21: 22, 22: 22}
    source = {}                      # per paw: the (fractional) tick of its own clip that plays at each tick
    for (start, end, _), landing in zip(LEGS, TIMING.get(slot, (n, (0, 0, 0, 0), None))[1]):
        if slot not in TIMING:
            source[end] = [float(t) for t in range(n)]
            continue
        period, _, stance = TIMING[slot]
        ys = [still[t][end][1] for t in range(n)]
        ground, top = max(ys), min(ys)
        down = [y > ground - .4 * (ground - top) for y in ys]
        first = _first_landing(ys, period)
        length = sum(down[:period]) or 1
        length_new = stance or length
        row = []
        for t in range(n):
            u = (t - landing) % period
            if u < length_new:
                x = first + length * u / length_new
            else:
                x = first + length + (period - length) * (u - length_new) / (period - length_new)
            row.append(x)
        source[end] = row
    feet = [[_blend_vec(still, source[end][t], end, n) for t in range(n)] for _, end, _ in LEGS]
    if spec['gait']:
        pitch, high, lean, reach = _gait(feet, spec, n)
        roll = [spec['roll'] * v for v in lean]
        yaw = [spec['yaw'] * v for v in reach]
    else:
        # breathing and a slow weight shift over the loop: no stride to follow
        pitch = [math.sin(2 * math.pi * t / n * 2) for t in range(n)]
        high = [math.sin(2 * math.pi * t / n * 2 + .6) for t in range(n)]
        roll = [spec['roll'] * math.sin(2 * math.pi * t / n) for t in range(n)]
        yaw = [spec['yaw'] * math.sin(2 * math.pi * t / n + 1.2) for t in range(n)]
    # slow loop-wide modulation so that two strides never repeat exactly
    modulation = [1 + spec['mod'] * math.sin(2 * math.pi * t / n + .9) + .5 * spec['mod'] * math.sin(4 * math.pi * t / n + 2.1)
                  for t in range(n)]
    body_pitch = [spec['pitch'] * m * v for m, v in zip(modulation, pitch)]
    height = [spec['bounce'] * m * (.5 + .5 * v) for m, v in zip(modulation, high)]
    chest_rest = [R.rot_of(p[CHEST]) for p in poses[:n]]
    # the gaits' own up-and-down follows the new feet (the imported bob followed the old ones); the idles keep theirs
    chest_mean = sum(p[CHEST][7] for p in poses[:n]) / n
    chest_y = [chest_mean if spec['gait'] else p[CHEST][7] for p in poses[:n]]
    hips_rest = [R.rot_of(p[HIPS]) for p in poses[:n]]
    slow = [math.sin(2 * math.pi * t / n) for t in range(n)]
    slow2 = [math.sin(2 * math.pi * t / n + 1.9) for t in range(n)]
    tail_old = {b: [R.rot_of(p[b]) for p in poses[:n]] for b in TAIL}
    tail_mean = {b: _mean_rot(tail_old[b]) for b in TAIL}
    head_roll = [spec['head_share'] * v for v in roll]
    head_yaw = [spec['head_share'] * v + spec['head_drift'] * slow[t] for t, v in enumerate(yaw)]
    roll_unit = _smooth([r / (spec['roll'] or 1.) for r in roll], 1)
    lift_table = HEAD_TABLE.get(slot)
    bobs = [spec['head_bob'] * (.5 - .5 * _wrap(pitch, t - spec['head_lag'])) for t in range(n)]
    for t in range(n):
        pose = poses[t]
        facing = old[t][0]
        to_char = lambda m: _mul(facing, m, R.m3t(facing))        # a rotation about the character's axes, in the world
        p = body_pitch[t]
        locals_ = {CHEST: _mul(_rx(p), _rz(roll[t]), _ry(yaw[t]), chest_rest[t]),
                   HIPS: _mul(_rx(-(1 + spec['hips_pitch']) * p), _ry(-spec['hips'] * yaw[t]), hips_rest[t])}
        hr, hy = _wrap(head_roll, t - spec['head_lag']), _wrap(head_yaw, t - spec['head_lag'])
        hp = spec['head_follow'] * _wrap(body_pitch, t - spec['head_lag'])
        head_turn = to_char(_mul(_rx(hp), _rz(hr), _ry(hy)))
        holds = {HEAD: _mul(head_turn, old[t][HEAD])}
        for b in LEG_BONES:                       # the leg as its own foot's clip has it (shifted in time)
            x = source[owner[b]][t]
            pose[b][3:6] = rest[round(x) % n][b][3:6]
            if b in (5, 8, 15, 19, 7, 10, 18, 22):
                holds[b] = _blend_rot(old, x, b, n)
        for i, b in enumerate(TAIL):
            dev = _mul(R.m3t(tail_mean[b]), tail_old[b][t])
            keep = _mul(tail_mean[b], R.scale_rot(dev, spec['keep']))
            lag = spec['t_lag'][i]
            pitch_t = spec['tail_up'][i] + spec['t_pitch'][i] * _wrap(high, t - lag)
            side = spec['t_yaw'][i] * _wrap(roll_unit, t - lag) + spec['t_drift'] * (i + 1) / 3. * _wrap(slow2, t - lag)
            locals_[b] = (keep, _mul(_rx(pitch_t), _ry(side)))
        pose[CHEST][7] = round(chest_y[t] - height[t])
        for b in FORE_ROOTS:
            pose[b][8] += round(spec['arms_back'])
        body = {k: v for k, v in locals_.items() if k not in TAIL}
        world = _world_pose(rig, pose, body, holds)
        for (start, end, kind) in LEGS:
            goal = list(feet[[e for _, e, _ in LEGS].index(end)][t])
            if kind == 0:
                goal[2] += spec['arms_back']
            _ik(rig, pose, start, goal)
        for b in TAIL:
            keep, extra = locals_[b]
            par = rig[b][1]
            pw = world[par]
            rel = _mul(R.m3t(facing), pw)
            local = _mul(_mul(R.m3t(rel), extra, rel), keep)
            pose[b][3:6] = [round(v) for v in mmd.matrix_euler(local, pose[b][3:6])]
            world[b] = _mul(pw, R.rot_of(pose[b]))
        if lift_table is not None:
            head_step(pose, lift_table[t][0] + bobs[t], lift_table[t][1])
    return bobs


def closing(poses, n):
    """The last pose repeats the first one in every joint (the root keeps its travel)."""
    for b in range(1, len(poses[0])):
        poses[n][b] = copy.deepcopy(poses[0][b])


def build(data, skeleton, species=SPECIES):
    nb = len(skeleton)
    mmd.exe().skeleton[species] = skeleton
    mmd.exe().bone_count[species] = nb
    old = mmd.MMD.parse(data, nb)
    old.type = species
    new = copy.deepcopy(old)
    checks = []
    for slot in SLOTS:
        spec = PROFILE[slot]
        frames, loop, _ = animsheet.slot_frames(old, nb, slot)
        assert loop == 0
        n = len(frames) - 1
        poses = copy.deepcopy(frames)
        carriage(poses, skeleton, n, spec, slot)
        closing(poses, n)
        index = new.anims.table[slot]
        animation = replace_channels(old.anims.anims[index], poses, loop, nb, CHANNELS, tolerance=TOLERANCE)
        animation, _ = coalesce(animation)
        new.anims.anims[index] = animation
        checks.append(dict(slot=slot, ticks=n))
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = mmd.MMD.parse(result, nb)
    actual.type = species
    assert old.tmd.build() == actual.tmd.build()
    return result, dict(species=species, checks=checks, changed=changed_programs(old, actual),
                        storage=motionstorage.require(result, nb))



def _fit_slot(clash, poses, bobs, n, slot, margin, limbs, others, budget):
    """Per tick: the smallest (lift, pitch) that clears the forelegs, then max-filtered and smoothed over the loop."""
    lifts, pitches = [], []
    for t in range(n):
        best = None
        for pitch in (0., -6.):
            for lift in range(0, 101, 4):
                q = copy.deepcopy(poses[t])
                head_step(q, lift + margin + bobs[t], pitch)
                if clash.clash(q, limbs, others)[0] == 0:
                    cost = (lift / budget[0]) ** 2 + (pitch / budget[1]) ** 2
                    if best is None or cost < best[0]:
                        best = (cost, lift, pitch)
                    break
        if best is None:
            best = (0, 100, -6.)
        lifts.append(float(best[1]))
        pitches.append(best[2])
    # a window wide enough to carry the head over the worst tick before and after it, then rounded off; ticks that still
    # cross (a smoothed mix of lifts and pitches is not any single tested one) get more lift around them until none does
    extra = [0.] * n
    for _ in range(12):
        wide = [max(lifts[(t + k) % n] + extra[(t + k) % n] for k in range(-3, 4)) for t in range(n)]
        wide_p = [min(pitches[(t + k) % n] for k in range(-3, 4)) for t in range(n)]
        table = [(round(a + margin, 1), round(b, 1)) for a, b in zip(_smooth(wide, 2), _smooth(wide_p, 2))]
        bad = []
        for t in range(n):
            q = copy.deepcopy(poses[t])
            head_step(q, table[t][0] + bobs[t], table[t][1])
            if clash.clash(q, limbs, others)[0]:
                bad.append(t)
        if not bad:
            return table
        for t in bad:
            for k in range(-2, 3):
                extra[(t + k) % n] += 4.
    raise AssertionError(('the head carriage does not clear the forelegs', slot, bad))


def fit(data, skeleton, species=SPECIES, margin=4, budget=(50., 8.)):
    """Offline: the HEAD_TABLE that clears the forelegs from the mane (and the jaw) on the model `data` (needs numpy)."""
    from tools.models.field_animations import meshclash
    nb = len(skeleton)
    mmd.exe().skeleton[species] = skeleton
    mmd.exe().bone_count[species] = nb
    old = mmd.MMD.parse(data, nb)
    old.type = species
    clash = meshclash.Clash(old, skeleton)
    limbs = (5, 6, 7, 8, 9, 10)
    others = (HEAD, JAW)
    table = {}
    saved = dict(HEAD_TABLE)
    HEAD_TABLE.clear()
    try:
        for slot in SLOTS:
            spec = PROFILE[slot]
            frames, loop, _ = animsheet.slot_frames(old, nb, slot)
            n = len(frames) - 1
            poses = copy.deepcopy(frames)
            bobs = carriage(poses, skeleton, n, spec, slot)
            table[slot] = list(_fit_slot(clash, poses, bobs, n, slot, margin, limbs, others, budget))
        # the stored clips are coalesced (TOLERANCE): measure the real thing and lift the head where it still crosses
        for _ in range(8):
            HEAD_TABLE.clear()
            HEAD_TABLE.update({k: tuple(v) for k, v in table.items()})
            built = mmd.MMD.parse(build(data, skeleton, species)[0], nb)
            built.type = species
            leaks = 0
            for slot in SLOTS:
                frames = animsheet.slot_frames(built, nb, slot)[0]
                for t, pose in enumerate(frames[:-1]):
                    if clash.clash(pose, limbs, others)[0]:
                        leaks += 1
                        n = len(table[slot])
                        for k in range(-2, 3):
                            lift, pitch = table[slot][(t + k) % n]
                            table[slot][(t + k) % n] = (lift + 3., pitch)
            if not leaks:
                break
        else:
            raise AssertionError('the stored head carriage still crosses the forelegs')
    finally:
        HEAD_TABLE.clear()
        HEAD_TABLE.update(saved)
    return table


TAKES_SPECIES = True
