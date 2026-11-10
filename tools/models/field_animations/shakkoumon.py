"""Shakkoumon's field clips: a breathing idle, a lumbering waddle, a heavier lurching run.

Offline authoring and player replay: the player's build runs `build` on the reviewed imported model, then
celebrations.py adds the salute on top. Shakkoumon is a golden idol on two short vase-shaped legs with a skirt, heavy
sleeved arms, a huge helmet head and a pair of folded wings on its back. Its imported idle, walk, condition walk and run
all replayed one 73-tick wing-and-arm loop, so they looked the same.

Every field clip is now its own gait, made from the model's rest pose, with the root travelling at an even speed:

- idle: the weight settles from one foot to the other and the chest breathes; the arms, head and wings follow the body
  a beat late; the feet stay put;
- walk: a waddle. The body rolls over the foot that carries it and the pelvis twists against the chest; the legs swing
  in short steps with the body riding over them; arms hang heavy and swing late, the head follows last, the wings stir;
- condition walk: the same, slower and drooping, the head low and the steps shorter;
- run: the waddle faster, leaning forward, with a bigger roll and a short moment in the air at each step, the wings
  trailing back.

The body is held on its feet: for every tick the pelvis height is set so the lowest point of the standing leg is on the
floor, and the legs are kept at their own stance width, so the feet do not float or sink. The mesh and every other
program stay exact.
"""
import copy
import hashlib
import math

import animsheet
import mmd
import motioncyclelayer
import motionstorage
from motiondiscidentity import changed_programs

SOURCE = '664c609dc2da9286716aa5cb75b46d23eafe98aac42149e83f5d5a2e3f13dd46'
SPECIES = 214
NB = 23
SLOTS = (0, 2, 3, 4)
PELVIS, CHEST, HEAD = 1, 2, 3
ARMS = ((4, 5), (11, 12))               # shoulder, forearm; the right arm first
FINGERS = ((7, 8, 9, 10), (14, 15, 16, 17))
SKIRT = 18
LEGS = (19, 20)                         # right, left
WINGS = (21, 22)
DEG = 4096 / 360

# Per slot: cycle ticks, root units per tick, share of the cycle each foot is down, swing of the leg forward and back
# (degrees), foot lift, roll of the body over the standing foot, chest counter-roll, pelvis and chest twist, forward
# lean of the chest, bob of the chest, arm swing (shoulder, forearm), arm opening with the roll, head nod, head roll
# lag, flight over the floor, wing flutter.
GAITS = {
    2: dict(ticks=14, speed=20., duty=.6, fore=33, back=27, reach=62, lift=16, roll=5.0, counter=2.6, twist=3.4, lean=3.5,
            bob=3.5, swing=11, elbow=9, open=4.5, nod=2.2, flight=0., flutter=7, arm_lag=.10, head_lag=.16),
    3: dict(ticks=20, speed=12., duty=.64, fore=26, back=22, reach=50, lift=9, roll=3.8, counter=1.6, twist=2.2, lean=8.0,
            bob=2.5, swing=5, elbow=5, open=2.5, nod=1.6, flight=0., flutter=4, arm_lag=.12, head_lag=.20),
    4: dict(ticks=12, speed=42., duty=.46, fore=38, back=34, reach=70, lift=24, roll=6.5, counter=3.0, twist=5.0, lean=11.,
            bob=5.0, swing=17, elbow=15, open=7., nod=3.0, flight=9., flutter=11, arm_lag=.09, head_lag=.15),
}
IDLE = dict(ticks=72, shift=1.6, tilt=1.2, breath=3.6, nod=1.0, flutter=3.2)


def smooth(x):
    x = max(0., min(1., x))
    return x * x * (3 - 2 * x)


def identity_root(pose):
    p = [list(b) for b in pose]
    p[0] = [4096] * 3 + [0] * 6
    return p


def lowest(model, skeleton, pose, bones):
    """Greatest world y (the lowest point, y points down) of the given bones' meshes."""
    mats = mmd.bone_matrices(model, identity_root(pose))
    return max(sum(mats[b][1][j] * v[j] for j in range(3)) + mats[b][1][3]
               for b in bones for v in model.tmd.obj_verts(skeleton[b][0]))


def foot_centre(model, skeleton, pose, leg):
    """World x and z of the leg's lowest vertices (the sole)."""
    mats = mmd.bone_matrices(model, identity_root(pose))
    pts = [[sum(mats[leg][r][j] * v[j] for j in range(3)) + mats[leg][r][3] for r in range(3)]
           for v in model.tmd.obj_verts(skeleton[leg][0])]
    low = max(p[1] for p in pts)
    sole = [p for p in pts if p[1] > low - 12]
    return sum(p[0] for p in sole) / len(sole), sum(p[2] for p in sole) / len(sole)


def sines(phase, harmonic=1, delay=0., offset=0.):
    return math.sin(2 * math.pi * harmonic * (phase - delay - offset))


def leg_pitch(g, u):
    """Pitch of one leg (degrees, negative = foot forward) and its swing lift (0..1) at its own phase u."""
    d = g['duty']
    if u < d:       # on the ground: the foot is carried from in front to behind at an even rate
        return -g['fore'] + (g['fore'] + g['back']) * u / d, 0.
    s = (u - d) / (1 - d)
    return g['back'] - (g['fore'] + g['back']) * smooth(s), math.sin(math.pi * s) ** 1.2


def gait_frame(rest, g, t, phase):
    """The pose at `phase` of a gait cycle, before the pelvis is set on the ground. Right foot lands at phase 0."""
    p = copy.deepcopy(rest)
    r = 2 * math.pi * phase
    # the right foot is down from 0 to duty: the body rolls over it in the middle of its stance
    centre = g['duty'] / 2
    roll = g['roll'] * math.cos(2 * math.pi * (phase - centre))
    twist = math.sin(2 * math.pi * (phase - centre) - .6)
    p[PELVIS][5] = round(roll * DEG)
    p[PELVIS][4] = round(-g['twist'] * twist * DEG)
    # the chest turns against the pelvis and rights itself against the roll, a beat late; its bob is two a cycle
    p[CHEST][5] = round(-g['counter'] * math.cos(2 * math.pi * (phase - centre - g['arm_lag'])) * DEG)
    p[CHEST][4] = round(1.6 * g['twist'] * twist * DEG)
    p[CHEST][3] = round((g['lean'] + .45 * g['nod'] * math.cos(2 * r - .7)) * DEG)
    p[CHEST][7] += round(g['bob'] * math.cos(2 * r + 2.2) / 2)
    # the head follows last and carries its weight a beat behind the chest
    late = phase - g['head_lag']
    p[HEAD][3] = round((-.55 * g['lean'] + g['nod'] * math.cos(2 * math.pi * 2 * late - .7)) * DEG)
    p[HEAD][5] = round(-.5 * g['roll'] * math.cos(2 * math.pi * (late - centre)) * DEG)
    p[HEAD][4] = round(-.7 * g['twist'] * math.sin(2 * math.pi * (late - centre) - .6) * DEG)
    # legs
    for k, leg in enumerate(LEGS):
        u = (phase - .5 * k) % 1.
        pitch, up = leg_pitch(g, u)
        sign = 1 if k == 0 else -1
        p[leg][3] = round(pitch * DEG)
        # keep the sole level under the rolling body, and let the swinging foot open a little
        p[leg][5] = round((-roll * (1 - .7 * up) + sign * 5 * up) * DEG)
        p[leg][7] = rest[leg][7] - round(g['lift'] * up)
    # arms hang heavy: each swings against its own leg, late, and opens with the roll of the body
    for k, (arm, fore) in enumerate(ARMS):
        sign = 1 if k == 0 else -1
        u = (phase - .5 * k - g['arm_lag']) % 1.
        pitch, _ = leg_pitch(g, u)
        swing = -pitch / (g['fore'] if pitch < 0 else g['back']) * (g['swing'])
        p[arm][3] = rest[arm][3] + round(swing * DEG * (1 if pitch < 0 else .8))
        p[arm][5] = rest[arm][5] + round(sign * g['open'] * math.cos(2 * math.pi * (phase - centre - 2 * g['arm_lag'])) * DEG)
        late_u = (phase - .5 * k - 2.2 * g['arm_lag']) % 1.
        pitch2, _ = leg_pitch(g, late_u)
        p[fore][3] = rest[fore][3] + round(-pitch2 / (g['fore'] if pitch2 < 0 else g['back']) * g['elbow'] * DEG)
        for j, finger in enumerate(FINGERS[k]):
            p[finger][3] = rest[finger][3] + round(.35 * swing * DEG * (1 + .12 * j))
    # wings stir late, folding back as the body leans
    for k, wing in enumerate(WINGS):
        sign = 1 if k == 0 else -1
        p[wing][4] = rest[wing][4] + sign * round((g['flutter'] * math.sin(2 * math.pi * 2 * (phase - .3) - .3)
                                                   + .5 * g['lean']) * DEG)
    return p


def flight_height(g, phase, height):
    """Over the floor in the part of the cycle where neither foot is down."""
    d = g['duty']
    ph = phase % .5
    if ph < d:
        return 0.
    return height * math.sin(math.pi * (ph - d) / (.5 - d))


def sole_target(g, u):
    """Where the sole is along the body (z, forward negative) at the leg's own phase u: carried back at the root's own
    speed while it is down (as far as the leg reaches), then brought forward."""
    reach = min(g['speed'] * g['duty'] * g['ticks'] / 2, g['reach'])
    d = g['duty']
    if u < d:
        return -reach + 2 * reach * u / d
    return reach - 2 * reach * smooth((u - d) / (1 - d))


def place_soles(model, skeleton, pose, g, phase, rest_z):
    """Sets each leg's pitch so its sole is at the planned place along the body."""
    for k, leg in enumerate(LEGS):
        want = rest_z[k] + sole_target(g, (phase - .5 * k) % 1.)
        lo, hi = -60 * DEG, 60 * DEG
        for _ in range(24):
            mid = (lo + hi) / 2
            pose[leg][3] = round(mid)
            if foot_centre(model, skeleton, pose, leg)[1] < want:
                lo = mid
            else:
                hi = mid
        pose[leg][3] = round((lo + hi) / 2)


def idle_frame(rest, g, phase):
    p = copy.deepcopy(rest)
    r = 2 * math.pi * phase
    shift = math.sin(r)                    # the weight rocks from one foot to the other, slowly
    breath = (1 - math.cos(2 * r)) / 2     # two breaths to a rock
    p[PELVIS][5] = round(g['tilt'] * shift * DEG)
    p[PELVIS][6] = rest[PELVIS][6] + round(5 * shift)
    p[PELVIS][4] = round(.6 * math.sin(r - .5) * DEG)
    p[CHEST][5] = round(-.8 * g['tilt'] * math.sin(r - .35) * DEG)
    p[CHEST][3] = round((-1.1 * breath + .4) * DEG)
    p[CHEST][7] = rest[CHEST][7] - round(g['breath'] * breath)
    p[HEAD][3] = round((.9 * breath + g['nod'] * math.sin(2 * r - .9)) * DEG)
    p[HEAD][5] = round(-.9 * g['tilt'] * math.sin(r - .8) * DEG)
    p[HEAD][4] = round(1.4 * math.sin(r - 1.4) * DEG)
    for k, (arm, fore) in enumerate(ARMS):
        sign = 1 if k == 0 else -1
        # the arms rise with the breath and fall a beat late; the forearms hang from them
        p[arm][5] = rest[arm][5] + round(sign * (1.6 * math.sin(2 * r - 1.0) + .8 * math.sin(r - .6)) * DEG)
        p[arm][3] = rest[arm][3] + round(1.4 * math.sin(2 * r - 1.3) * DEG)
        p[fore][3] = rest[fore][3] + round(2.2 * math.sin(2 * r - 1.8) * DEG)
        for j, finger in enumerate(FINGERS[k]):
            p[finger][3] = rest[finger][3] + round(1.5 * math.sin(2 * r - 1.8 - .12 * j) * DEG)
    for k, wing in enumerate(WINGS):
        sign = 1 if k == 0 else -1
        p[wing][4] = rest[wing][4] + sign * round(g['flutter'] * math.sin(2 * r - 1.2) * DEG)
    return p


def settle(model, skeleton, frames, rest_gap, flight=None):
    """Sets the pelvis height of every tick so the lowest sole is on the floor (or `flight(tick)` above it), and the
    legs at their stance width under the body."""
    n = len(frames) - 1
    out = []
    for t, pose in enumerate(frames):
        p = copy.deepcopy(pose)
        # the legs under the rolling pelvis keep their own stance width
        for _ in range(2):
            for k, leg in enumerate(LEGS):
                x, _z = foot_centre(model, skeleton, p, leg)
                p[leg][6] += round((59 if k == 0 else -59) - x)
        gap = lowest(model, skeleton, p, LEGS)
        rise = (flight(t) if flight else 0.)
        p[PELVIS][7] += round(rest_gap - gap - rise)
        out.append(p)
    return out


def build(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('Shakkoumon requires its reviewed imported model')
    mmd.exe().add_type(SPECIES, skeleton)
    model = mmd.MMD.parse(data, NB)
    model.type = SPECIES
    rest = animsheet.slot_frames(model, NB, 0)[0][0]
    rest = [[int(x) for x in b] for b in rest]
    rest[0] = [4096] * 3 + [0] * 6
    floor = lowest(model, skeleton, rest, LEGS)
    result = copy.deepcopy(model)
    checks = []
    for slot in SLOTS:
        if slot == 0:
            g = IDLE
            n = g['ticks']
            frames = [idle_frame(rest, g, t / n) for t in range(n)]
            flight = None
            speed = 0.
        else:
            g = GAITS[slot]
            n = g['ticks']
            frames = [gait_frame(rest, g, t, t / n) for t in range(n)]
            rest_z = [foot_centre(model, skeleton, rest, leg)[1] for leg in LEGS]
            for t, p in enumerate(frames):
                place_soles(model, skeleton, p, g, t / n, rest_z)
            speed = g['speed']
            fl = g['flight']
            flight = (lambda t, fl=fl, g=g, n=n: flight_height(g, t / n, fl)) if fl else None
        frames = settle(model, skeleton, frames, floor, flight)
        frames.append(copy.deepcopy(frames[0]))
        for t, p in enumerate(frames):
            p[0][8] = -round(speed * t)
        mmd.close_loop(frames, 0)
        result.anims.anims.append(mmd.encode_anim(frames, NB, 0, [], tol=1, repeats=False))
        result.anims.table[slot] = len(result.anims.anims) - 1
        checks.append(dict(slot=slot, ticks=n, speed=speed))
    for animation in result.anims.anims:
        animation.tail = b''
    result.anims.anims, result.anims.table = motioncyclelayer.share_identical_streams(result.anims.anims,
                                                                                    result.anims.table)
    output = result.build()
    effective = mmd.MMD.parse(output, NB)
    effective.type = SPECIES
    assert effective.tmd.build() == model.tmd.build()
    changed = changed_programs(model, effective)
    assert set(changed) <= set(SLOTS), changed
    return output, dict(source_sha256=SOURCE, output_sha256=hashlib.sha256(output).hexdigest(), changed_slots=changed,
                        checks=checks, storage=motionstorage.require(output, NB))
