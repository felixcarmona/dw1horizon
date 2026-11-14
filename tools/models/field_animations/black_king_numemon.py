"""Slug locomotion and care acting on BlackKingNumemon's own anatomy.

The imported idle supplies the neutral articulation. Eye stalks and the crown
stay in their own local frames instead of receiving Etemon's limb rotations.

The two little front pads are its traction (slots 2, 3 and 4). Each pad plants its sole on the ground, rakes back
over it at the body's speed (the body is pulled forward over the planted pad: no slip), lifts, and reaches forward
again low over the ground with a small arc; the left and right pads do it almost together, the right a few ticks behind
the left (the lag the old pad swing already had), starting as the body begins to rise out of its hump. Only the pads'
own channels (bone 2 and 4: yaw, pitch, height and fore-aft slide) are written; the body, the stalks, the crown and every
other clip are the same bytes as before (`build(..., paddle=False)` makes those older clips).

The battle movements and the victory (slots 35, 36 and 42) are no longer written here: the input carries the source game's own clips for them
(content/models/imports/battle-rebuilds.json), so the slug wave and the care joy that used to stand in for them are gone.
"""
import copy
import hashlib
import math

import numpy as np

import animsheet
import mmd
import motionstorage
from motioncyclelayer import share_identical_streams
from motiondiscidentity import changed_programs

SOURCE = 'fee8456cdfff331cd67bbeeffa82792001da60afba5d1d85fe992880ee73c18d'
# Pad bones: (hip, outer pad) of the left and of the right front pad.
PADS = {'L': (2, 3), 'R': (4, 5)}
FLOOR = -.7      # the encoder keeps each channel within a unit: aim a little above the floor
# Per slot: ticks of the loop, root speed per tick, planted ticks, first planted tick, forward reach of the sole
# (z, in front of the root; the sole goes back by planted * speed over the ground), lift of the swing, ticks the right pad
# trails the left, slide of the hip along the stroke (units per unit of reach).
PADDLE = {
    2: dict(period=32, speed=20, planted=4, start=1, reach=-134, lift=12, lag=2, slide=.6),
    3: dict(period=40, speed=14, planted=4, start=1, reach=-125, lift=12, lag=3, slide=.6),
    4: dict(period=24, speed=38, planted=2, start=1, reach=-130, lift=8, lag=1, slide=.6),
}


# The eyes. They hang on two stalks (bones 7, 8 and 10, 11 under the head; the eyeballs are bones 9 and 12) and act like
# rubber on springs, never closing: each stalk joint follows the body's bob and roll through a damped spring (a chain of
# three, so every joint lags and overshoots a little more than the one under it), the left and right eye have their own
# stiffness and delay, the roll goes the opposite way on each (a see-saw), and the stalk stretches and thins with the bob.
# The two black crescents (13 and 14) are brows: tired ones sag, running ones set. Every term repeats with the clip, so
# the loops close.
EYES, BROWS, STALKS, HEAD = (9, 12), (13, 14), (7, 10), 6
SIDES = ((7, 8, 9, 1., 0., 1.), (10, 11, 12, -1., .9, 1.22))       # lower stalk, upper stalk, eye, roll sign, delay, stiffness ratio
FACE = {
    # spread: how much the right eye's spring differs from the left's (stiffness ratio above, 0 = the same)
    # sway: peak swing of the eye (units, 4096 to the turn); nat: natural period of the springs (ticks); zeta: damping;
    # stretch: stalk stretch with the bob; brow: angle (positive = inner ends down, determined; negative = weary);
    # head: head pitch (positive = down); droop: stalk bias (positive = drooping)
    'idle': dict(sway=80, nat=30., zeta=.4, spread=0., stretch=.03, brow=0., head=0., droop=0.),
    'walk': dict(sway=130, nat=9., zeta=.2, spread=1., stretch=.09, brow=0., head=0., droop=0.),
    'tired': dict(sway=95, nat=16., zeta=.28, spread=1., stretch=.06, brow=-240., head=70., droop=60.),
    'run': dict(sway=165, nat=6., zeta=.24, spread=1., stretch=.14, brow=230., head=-60., droop=-40.),
}
_CACHE = {}


def spring(drive, nat, zeta):
    """The steady state of a damped spring (natural period `nat` ticks) pulled towards a periodic drive: one list per
    loop, found by running the loop until it settles."""
    n = len(drive)
    k = (2 * math.pi / nat) ** 2
    c = 2 * zeta * math.sqrt(k)
    x = v = 0.
    out = [0.] * n
    for cycle in range(40):
        for t in range(n):
            v += (k * (drive[t] - x) - c * v)
            x += v
            out[t] = x
    return out


def drives(mood, period, side):
    """(pitch drive, roll drive) of one eye over the loop: the body's bob and roll, or slow different-rate sways when
    the body is still."""
    t = np.arange(period)
    ph = 2 * math.pi * t / period
    delay = SIDES[side][4]
    if mood == 'idle':
        if side == 0:
            return np.sin(2 * ph) + .25 * np.sin(4 * ph + 1), np.sin(3 * ph + .4)
        return np.sin(3 * ph + .7) + .2 * np.sin(5 * ph), np.sin(2 * ph + 1.9)
    return -np.cos(ph - delay * .5) + .3 * np.sin(2 * ph - delay), np.sin(ph - .4 - delay)


def eye_tracks(mood, period):
    """{side: (pitch chain, roll chain, stretch)}: three springs each, from the drives."""
    key = mood, period
    if key not in _CACHE:
        m = FACE[mood]
        out = []
        for side, (_, _, _, sign, _, ratio) in enumerate(SIDES):
            nat = m['nat'] * (1 + (ratio - 1) * m['spread'])
            dp, dr = drives(mood, period, side)
            chains = []
            for d in (dp, dr * sign):
                chain, x = [], list(d)
                for _ in range(3):
                    x = spring(x, nat, m['zeta'])
                    chain.append(x)
                chains.append(chain)
            out.append((chains[0], chains[1]))
        _CACHE[key] = out
    return _CACHE[key]


def face_pose(f, mood, tick, period):
    """Write the face channels of pose `f` for `mood` at `tick` of a loop of `period` ticks (additive on the pose)."""
    m = FACE[mood]
    sway = m['sway']
    for side, (lo, hi, eye, _, _, _) in enumerate(SIDES):
        pitch, roll = eye_tracks(mood, period)[side]
        i = tick % period
        f[lo][3] += round(.35 * sway * pitch[0][i])
        f[hi][3] += round(.6 * sway * pitch[1][i])
        f[eye][3] += round(sway * pitch[2][i])
        f[lo][5] += round(.3 * sway * roll[0][i])
        f[hi][5] += round(.5 * sway * roll[1][i])
        f[eye][5] += round(.8 * sway * roll[2][i])
        grow = 1 + m['stretch'] * pitch[0][i]
        f[lo][1] = round(f[lo][1] * grow)
        f[lo][0] = round(f[lo][0] / math.sqrt(grow))
        f[lo][2] = round(f[lo][2] / math.sqrt(grow))
        f[lo][3] += round(m['droop'])
        f[hi][3] += round(m['droop'] * .5)
    f[BROWS[0]][5] += round(m['brow'])
    f[BROWS[1]][5] -= round(m['brow'])
    f[HEAD][3] += round(m['head'])


def _smootherstep(u):
    u = min(1., max(0., u))
    return u * u * u * (u * (6 * u - 15) + 10)


def sole_path(period, speed, planted, start, lift, tick, kick=.63, arrive=.6):
    """(position of the sole along z relative to its forward reach, its height above the floor) at `tick` of the loop.

    Planted: the sole stays still on the ground, so in the body's frame it runs back at `speed`. Then it leaves the ground
    with most of that speed (a short recoil that is over in a tick), rises, eases forward and comes down already moving
    back at `arrive` of the speed (so the stroke starts from a glide, not from a standstill)."""
    swing = period - planted
    t = (tick - start) % period
    if t <= planted:
        return speed * t, 0.
    tau, u = t - planted, (t - planted) / swing
    back = speed * planted
    ease = _smootherstep(u)
    come = arrive * speed / 3 * ((1 - math.exp(-3 * (swing - tau))) - (1 - math.exp(-3 * swing)) * (1 - ease))
    return (back + kick * speed * (1 - math.exp(-3 * tau)) - (planted * speed + kick * speed) * ease - come,
            lift * math.sin(math.pi * u) ** .25)


class _Pads:
    """Forward kinematics of the pads: hip chain root, body, hip, outer pad; the sole is the middle of the pad's lowest face."""

    def __init__(self, model, rest, vertices):
        self.rest = rest
        self.vertices = dict(vertices)
        self.model = model
        self.sole = {}
        self.worst = 0.
        for side, (hip, pad) in PADS.items():
            matrix = self.chain(rest, (0, 1, hip, pad))[pad]
            world = np.array(self.vertices[pad], float)[:, :3] @ matrix[:3, :3].T + matrix[:3, 3]
            point = world[np.argsort(-world[:, 1])[:4]].mean(0)
            self.sole[side] = (np.linalg.inv(matrix) @ np.append(point, 1))[:3]

    @staticmethod
    def local(bone):
        r = np.array(mmd.rot_matrix(*bone[3:6]), float)
        m = np.eye(4)
        m[:3, :3] = r * (np.array(bone[:3], float) / 4096)[None, :]
        m[:3, 3] = bone[6:9]
        return m

    def chain(self, pose, bones):
        m, out = np.eye(4), {}
        for b in bones:
            m = m @ self.local(pose[b])
            out[b] = m.copy()
        return out

    def place(self, pose, side, z, height, previous):
        """Set the pad's yaw and height so that its sole is at world z (root motion included) and `height` above the floor."""
        hip, pad = PADS[side]
        sole = self.sole[side]
        base = np.array([self.rest[hip][4], self.rest[hip][7]], float)
        values = np.array(previous if previous is not None else base, float)
        trial = copy.deepcopy(pose)
        trial[hip][3] = 0

        def error(v):
            trial[hip][4], trial[hip][7] = v
            trial[pad][4] = round(base[0] - v[0])      # the outer pad keeps its heading while the hip pad turns
            m = self.chain(trial, (0, 1, hip, pad))[pad]
            p = m[:3, :3] @ sole + m[:3, 3]
            return np.array([p[1] + height, p[2] - z])
        for _ in range(8):
            r = error(values)
            jac = np.stack([(error(values + e) - r) for e in np.eye(2)], axis=1)
            values = values + np.clip(np.linalg.solve(jac.T @ jac + 1e-4 * np.eye(2), -jac.T @ r), -80, 80)
        self.error = float(np.abs(error(values)).max())
        # no corner of the pad goes into the floor (the body's own roll tilts the pad a little): lift it by what is left
        error(values)
        low = max((np.array(self.vertices[b], float)[:, :3] @ m[:3, :3].T + m[:3, 3])[:, 1].max()
                  for b, m in self.chain(trial, (0, 1, hip, pad)).items() if b in (hip, pad))
        values[1] -= max(0., low - FLOOR)
        return values


def paddle_clip(pads, frames, slot):
    """Rewrite the pads' channels of one clip's poses (frames[0..period]); the last pose repeats the first."""
    spec = PADDLE[slot]
    period = spec['period']
    mid = spec['planted'] * spec['speed'] / 2
    for side, (hip, pad) in PADS.items():
        lag = 0 if side == 'L' else spec['lag']
        values = None
        for tick in range(period):
            along, up = sole_path(period, spec['speed'], spec['planted'], spec['start'], spec['lift'], (tick - lag) % period)
            f = frames[tick]
            f[hip][3] = 0
            f[hip][8] = pads.rest[hip][8] + round(spec['slide'] * (along - mid))
            values = pads.place(f, side, spec['reach'] + along + f[0][8], up, values)
            f[hip][4], f[hip][7] = (round(v) for v in values)
            f[pad][4] = round(pads.rest[hip][4] - values[0])
    for bones in PADS.values():        # the loop closes: the last pose is the first (the root travel apart)
        for b in bones:
            frames[period][b] = list(frames[0][b])


MOODS = {2: 'walk', 3: 'tired', 4: 'run'}
IDLE_SLOTS = (0, 1, 18)


def build(data, skeleton, paddle=True, face=True):
    if hashlib.sha256(data).hexdigest() != SOURCE or len(skeleton) != 18:
        raise ValueError('BlackKingNumemon requires its pinned 18-bone import')
    old = mmd.MMD.parse(data, 18)
    old.type = 307
    mmd.exe().skeleton[307] = skeleton
    mmd.exe().bone_count[307] = 18
    new = copy.deepcopy(old)
    rest = animsheet.slot_frames(old, 18, 33)[0][0]
    reports = []
    pads = None
    vertices = [(b, old.tmd.obj_verts(obj)) for b,(obj,_) in enumerate(skeleton) if obj >= 0]
    for slot in (2, 3, 4, 11, 12, 25, 27):
        source, loop, events = animsheet.slot_frames(old, 18, slot)
        locomotion = slot in (2, 3, 4, 27)
        period = {2: 32, 3: 40, 4: 24, 27: 32}.get(slot, len(source) - 1)
        speed = {2: 20, 3: 14, 4: 38}.get(slot, 0)
        distance = -speed * period
        if slot == 27:
            # The flee controller keep their existing average travel.
            distance = round((source[-1][0][8] - source[0][0][8]) * period / (len(source) - 1))
            speed = -distance / period
        poses = []
        paddled = paddle and slot in PADDLE
        for tick in range(period + 1):
            f = copy.deepcopy(rest)
            phase = 2 * math.pi * tick / period
            # Closed smooth waves: compression travels from the snout to the
            # shell, with delayed crown/eye follow-through rather than a hinge.
            if locomotion:
                f[0][8] = round(distance * tick / period)
                lift = round(10 * (1 - math.cos(phase)))
                f[1][7] -= lift
                # The front pads and rear support stay low while the heavy
                # body rises between them; this avoids lifting the whole slug.
                for b in (2, 4, 15):
                    f[b][7] += lift
                f[1][5] += round(36 * math.sin(phase))
                f[6][3] += round(70 * math.sin(phase - .4))
                f[15][3] += round(60 * math.sin(phase - .8))
                f[16][3] += round(30 * math.sin(phase - 1.1))
                for b, lag in ((2, 0), (4, .4)):
                    f[b][3] += round(110 * math.sin(phase - lag))
                for b, lag in ((7, .5), (10, .8)):
                    f[b][3] += round(50 * math.sin(phase - lag))
            else:
                # Anticipation, two nods/shakes, then a soft settle. Envelope
                # vanishes at both endpoints so care returns to the idle pose.
                envelope = math.sin(math.pi * tick / period) ** 2
                wave = math.sin(phase * 2)
                happy = slot == 11
                lift = round((14 if happy else -4) * envelope)
                f[1][7] -= lift
                for b in (2, 4, 15):
                    f[b][7] += lift
                f[6][3] += round((65 if happy else 90) * envelope * wave)
                f[1][5] += round((35 if happy else 15) * envelope * math.sin(phase))
                for b, lag in ((7, .3), (10, .55)):
                    f[b][3 if happy else 4] += round(65 * envelope * math.sin(phase * 2 - lag))
                f[15][3] += round(25 * envelope * math.sin(phase * 2 - .7))
                f[16][3] += round(18 * envelope * math.sin(phase * 2 - 1))
            if face and slot in MOODS:
                face_pose(f, MOODS[slot], tick, period)
            matrices = mmd.bone_matrices(old, f)
            bottom = max(sum(matrices[b][1][j] * v[j] for j in range(3)) + matrices[b][1][3]
                         for b, verts in vertices for v in verts)
            f[1][7] -= math.ceil(bottom)
            poses.append(f)
        if paddled:
            if pads is None:
                pads = _Pads(old, rest, vertices)
            assert period == PADDLE[slot]['period'] and speed == PADDLE[slot]['speed'], slot
            paddle_clip(pads, poses, slot)
        if locomotion:
            events = [(t, 'sound', dict(bank=1, note=24)) for t in (2, period // 2 + 2)]
            loop = 0
        if slot == 25:
            loop = 0
        authored = mmd.encode_anim(poses, 18, loop_sample=loop, events=events, tol=1, repeats=False)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
        reports.append(dict(slot=slot, period=period, speed=speed, sounds=[t for t,k,_ in events if k=='sound']))
    if face:
        source, loop, events = animsheet.slot_frames(old, 18, 0)
        period = len(source) - 1
        poses = [copy.deepcopy(f) for f in source]
        for tick, f in enumerate(poses):
            face_pose(f, 'idle', tick, period)
        authored = mmd.encode_anim(poses, 18, loop_sample=loop, events=events, tol=0, repeats=False)    # lossless: the other bones keep their keys
        for slot in IDLE_SLOTS:
            assert old.anims.table[slot] == old.anims.table[0]
            new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
        reports.append(dict(slot=0, period=period, speed=0, sounds=[]))
    new.anims.anims, new.anims.table = share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = mmd.MMD.parse(result, 18)
    assert changed_programs(old, actual) == sorted([2, 3, 4, 11, 12, 25, 27] + (list(IDLE_SLOTS) if face else []))
    assert old.tmd.build() == actual.tmd.build()
    for row in reports:
        if row['slot'] not in (2, 3, 4, 27):
            continue
        slot, period = row['slot'], row['period']
        player = mmd.AnimPlayer(actual.anims.anims[actual.anims.table[slot]], 18, slot)
        cycle = []
        for tick in range(period * 9):
            assert player.tick()
            if tick < period:
                cycle.append(copy.deepcopy(player.pose[1:]))
            else:
                assert player.pose[1:] == cycle[tick % period], (slot, tick, 'body drift')
        row['body_repeats_nine_cycles'] = True
    storage = motionstorage.require(result, 18)
    return result, dict(species=307, source_sha256=SOURCE,
                        output_sha256=hashlib.sha256(result).hexdigest(),
                        changed_slots=[r['slot'] for r in reports], checks=reports, storage=storage)
