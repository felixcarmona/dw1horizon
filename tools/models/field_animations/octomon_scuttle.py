"""Octomon's field idle, walk, tired walk and run: six legs that walk and a body that breathes (species 278).

The import's four clips (22 ticks each) were one and the same pose cycle with only the root faster, the legs hung from
the body without touching the floor in any rhythm (foot slip 104 to 113 %) and the tentacles did not move. Offline only
(player builds replay the pinned delta): `tools/models/edit.py get 278` on the commit before this change, then
`python3 -m tools.models.field_animations.octomon_scuttle --source THAT.MMD --out AFTER.MMD` and `edit.py put 278 AFTER.MMD`.

The model: bone 1 is the body (and the head, with the tuft 23 on top), bone 2 the disc under it. Six pointed legs hang
from it, three a side: the long front legs (right 14-15-16, left 17-18-19, the tips 300 units ahead), the middle legs
(9-10 and 3-4) and the short hind legs (7-8 and 5-6). Two arms with a club (11-12-13) and a sickle (20-21-22) are
carried up.

- Walk, tired walk and run are tripod gaits: the front right, middle left and hind right legs step together, then the
  other three, each leg a few ticks after the one before it (a ripple from the front to the back). A leg is solved from
  its tip down (`solve`: damped least squares on the bones' own turns): in stance the tip stands on one point of the floor
  while the body passes over it, in swing it rises, comes forward on a path whose speed matches the stance at both ends
  and lands. The lowest vertex of every leg is held at the floor in stance (`CONTACT`), a leg that cannot reach stops the build.
- The body bobs once per footfall of a tripod, sways and rolls to the side that carries the weight, pitches and yaws a
  little; the tuft, the disc and the arms follow a few ticks late, segment after segment.
- Idle (64 ticks): breathing, the two front legs hold their tips off the floor and feel about with slow, unrelated
  rhythms, the other four stay planted, the arms and the tuft drift as waves running from the shoulder out.
- Walk 16 ticks at 15 units, tired walk 20 ticks at 10 (the body sunk low, the tips skim the floor, the arms hang),
  run 10 ticks at 36 (the body lower and pitched forward, long low strides, the arms and tuft streaming back).

Every clip repeats its pose cycle exactly, the root travels the same distance every tick and the programs the idle shared
(slots 1, 0x12 and 0x21) follow it.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet  # noqa: E402
import mmd  # noqa: E402
import motioncyclelayer  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models.field_animations import okuwamon_limbs as ol  # noqa: E402
from tools.models.field_animations.lillymon_flight import Rig  # noqa: E402

SPECIES, NB = 278, 24
SOURCE = '7db03916614b7d6544c083f425d2fa605d6abbb163e889e7a347b58c8455e153'   # edit.py get 278 before this change
SLOTS = (0, 1, 2, 3, 4)
SHARED_WITH_IDLE = (1, 18, 33)
CLIP_OF_SLOT = {0: 'idle', 2: 'walk', 3: 'tired', 4: 'run'}
BODY, DISC, TUFT = 1, 2, 23
ARM_R, ARM_L = (11, 12, 13), (20, 21, 22)
# name: (bones from the hip, side)
LEGS = {'RF': ((14, 15, 16), 1), 'LF': ((17, 18, 19), -1), 'RM': ((9, 10), 1), 'LM': ((3, 4), -1),
        'RR': ((7, 8), 1), 'LR': ((5, 6), -1)}
FRONT = ('RF', 'LF')
# where each foot stands in the middle of its stance, on the floor (x, z; the body at rest is at x 0, z -3)
FOOT = {'RF': (150, -200), 'LF': (-150, -200), 'RM': (150, 28), 'LM': (-158, 26), 'RR': (105, 62), 'LR': (-80, 96)}
ARM_YAW, ARM_FWD = 0., -32.         # degrees the shoulders are turned out (yaw) and carried forward (pitch)
ARM_UP = 10.                      # degrees the shoulders are raised, clear of the front legs
FLOOR = 6.0                       # units a leg may sink in a stance tick
MAX_ERROR = 1.5                   # units a tip may miss its target (a leg that cannot reach stops the build)
DEG = 4096 / 360

#   n: ticks; speed: units a tick; duty: share of the cycle on the floor; start: the cycle's touchdown of each leg;
#   lift/flair: height and sideways bow of the swing; drop: body lowering; bob/sway/roll/pitch/yaw: body terms (units, degrees);
#   lean: the body's mean pitch (forward positive); arm = (swing, raise, mean droop, lag), tuft = (swing, lag, mean)
CLIPS = {
    'idle': dict(n=64, speed=0, drop=10., bob=(3.6, .9), sway=3., roll=1.4, pitch=1.3, yaw=1.8, lean=0.,
                 arm=(7., 6., 0., .7), tuft=(7., .6, 0.), disc=2.5, feelers=True),
    'walk': dict(n=16, speed=15, duty=.56, start=dict(RF=0., LM=.03, RR=.06, LF=.5, RM=.53, LR=.56),
                 lift=dict(RF=42, LF=42, RM=30, LM=30, RR=26, LR=26), flair=12, drop=12., bob=(5.5, 1.4), sway=7., roll=2.6,
                 pitch=1.6, yaw=2.6, lean=1.5, arm=(9., 6., 0., .55), tuft=(8., .5, -1.), disc=2.),
    'tired': dict(n=20, speed=10, duty=.66, start=dict(RF=0., LM=.05, RR=.11, LF=.5, RM=.55, LR=.61),
                  lift=dict(RF=22, LF=22, RM=15, LM=15, RR=12, LR=12), flair=7, drop=30., bob=(4., 1.8), sway=5., roll=3.4,
                  pitch=2.6, yaw=1.6, lean=5., arm=(4., 3., 12., .7), tuft=(4., .8, 7.), disc=2.),
    'run': dict(n=10, speed=35, duty=.42, start=dict(RF=0., LM=.02, RR=.04, LF=.5, RM=.52, LR=.54),
                lift=dict(RF=58, LF=58, RM=42, LM=42, RR=36, LR=36), flair=16, drop=24., bob=(9., 2.), sway=8., roll=3.4,
                pitch=3., yaw=3., lean=11., arm=(9., 5., 0., .5), tuft=(9., .5, -14.), disc=3.),
}


def hermite(p0, p1, m0, m1, u):
    u2, u3 = u * u, u ** 3
    return (2 * u3 - 3 * u2 + 1) * p0 + (u3 - 2 * u2 + u) * m0 + (-2 * u3 + 3 * u2) * p1 + (u3 - u2) * m1


def skew(v):
    return np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])


def rodrigues(v):
    a = float(np.linalg.norm(v))
    if a < 1e-12:
        return np.eye(3)
    k = skew(np.asarray(v) / a)
    return np.eye(3) + math.sin(a) * k + (1 - math.cos(a)) * k @ k


def orthonormal(m):
    u, _, vt = np.linalg.svd(m)
    return u @ vt


def rmat(v):
    return orthonormal(np.array(mmd.rot_matrix(*v[3:6]), float))


class Octomon:
    """The model, its rig and the leg solver."""

    def __init__(self, model, skeleton):
        self.model, self.skeleton = model, skeleton
        self.body = ol.Body(model, skeleton)
        self.parent = [p for _, p in skeleton]
        self.tip = {}                                   # leg -> the last bone's farthest vertex, in its own frame

    def mats(self, pose):
        p = copy.deepcopy(pose)
        p[0] = [4096] * 3 + [0] * 6
        return [np.array(m, float) for m in mmd.bone_matrices(self.model, p)]

    def find_tips(self):
        for name, (chain, _) in LEGS.items():
            lv = self.body.local_vertices(chain[-1])
            self.tip[name] = lv[int(np.argmax(np.linalg.norm(lv, axis=1)))]

    def tip_world(self, pose, name):
        m = self.mats(pose)[LEGS[name][0][-1]]
        return m[:3, :3] @ self.tip[name] + m[:3, 3]

    def solve(self, pose, name, target, mu=(300., 700., 1000.), iters=60):
        """Turn the leg's bones (about their joints, in world axes) until its tip is on `target`; returns the miss."""
        chain = LEGS[name][0]
        mats = self.mats(pose)
        rp, pp = orthonormal(mats[self.parent[chain[0]]][:3, :3]), mats[self.parent[chain[0]]][:3, 3]
        loc = [rmat(pose[b]) for b in chain]
        off = [np.array(pose[b][6:9], float) for b in chain]
        mu = mu[:len(chain)]
        acc = np.zeros((len(chain), 3))
        miss = 0.
        for it in range(iters):
            wr, wp, r = [], [], rp
            p = pp
            for i in range(len(chain)):
                p = p + r @ off[i]
                r = r @ loc[i]
                wr.append(r)
                wp.append(p)
            tip = wr[-1] @ self.tip[name] + wp[-1]
            err = np.asarray(target, float) - tip
            miss = float(np.linalg.norm(err))
            if miss < .05:
                break
            cols = []
            for i in range(len(chain)):
                rad = tip - wp[i]
                for k in range(3):
                    e = np.zeros(3)
                    e[k] = 1
                    cols.append(np.cross(e, rad))
            J = np.array(cols).T
            reg = np.repeat(mu, 3)
            rhs = J.T @ err
            d = np.linalg.solve(J.T @ J + np.diag(reg), rhs).reshape(-1, 3)
            d = d * min(1., 0.35 / max(1e-9, float(np.abs(d).max())))        # at most .35 rad a step
            par = [rp] + wr[:-1]
            for i in range(len(chain)):
                loc[i] = orthonormal(par[i].T @ rodrigues(d[i]) @ wr[i])
            acc += d
        else:
            tip = None
        for i, b in enumerate(chain):
            ang = mmd.matrix_euler(loc[i].tolist(), pose[b][3:6])
            pose[b][3:6] = [round(a) for a in ang]
        return float(np.linalg.norm(np.asarray(target, float) - self.tip_world(pose, name)))


def bump(u):
    return math.sin(math.pi * u) ** 1.6


def wave(x, lag=0., second=.3, shift=.9):
    """One beat that is not a pure sine: a second harmonic leans it."""
    return math.sin(x - lag) + second * math.sin(2 * (x - lag) + shift)


class Clip:
    def __init__(self, oct_, name, neutral, contact):
        self.o, self.name, self.c = oct_, name, CLIPS[name]
        self.neutral, self.contact = neutral, contact
        self.n = self.c['n']

    def foot(self, leg, t):
        """Target of the leg's tip at tick t, in the body's frame of reference (x across, y down, z back), and whether it stands."""
        c, n = self.c, self.n
        x0, z0 = FOOT[leg]
        side = LEGS[leg][1]
        y0 = self.contact[leg]
        if c['speed'] == 0:
            ph = 2 * math.pi * t / n
            if leg in FRONT:
                k = 0 if leg == 'RF' else 1
                h = 15. + 8. * math.sin(ph + 2.1 * k) + 3. * math.sin(2 * ph + 1.0 * k)
                sx = 16. * math.sin(ph * 2 + 1.7 * k + .4) + 5. * math.sin(ph * 3 + 1.0 * k)
                sz = 22. * math.sin(ph + 0.9 + 2.9 * k) + 6. * math.sin(ph * 3 + 2 * k)
                return (x0 + side * 12 + sx, y0 - h, z0 + sz), False
            return (x0, y0, z0), True
        speed, duty = c['speed'], c['duty']
        T = n
        half = speed * T * duty / 2
        phase = ((t / T) - c['start'][leg]) % 1.0
        if phase < duty:
            s = phase / duty
            return (x0, y0, z0 - half + 2 * half * s), True
        u = (phase - duty) / (1 - duty)
        tsw = T * (1 - duty)
        z = hermite(z0 + half, z0 - half, speed * tsw, speed * tsw, u)
        lift = c['lift'][leg]
        x = x0 + side * c['flair'] * bump(u)
        y = y0 - lift * bump(u ** .85)
        return (x, y, z), False

    def pose_at(self, t, rig):
        o, c, n = self.o, self.c, self.n
        pose = copy.deepcopy(self.neutral)
        th = 2 * math.pi * t / n
        rig.angles = {}
        # the body: lowered, bobbing on the footfalls of a tripod, swaying and rolling to the carrying side
        if c['speed']:
            ph = (t / n) % 1.0
            mid = c['duty'] / 2
            beat = 4 * math.pi * (ph - mid)
            bob = c['bob'][0] * (math.cos(beat) + .22 * math.sin(2 * beat + .8)) / 1.2
            sway = c['sway'] * (math.sin(th + .4) + .2 * math.sin(2 * th - .5))
            roll = c['roll'] * (math.sin(th + .4 + .6) + .15 * math.sin(3 * th))
            nod = c['pitch'] * (math.cos(beat + .6) + .2 * math.sin(2 * beat))
            yaw = c['yaw'] * (math.sin(th + 1.6) + .2 * math.sin(3 * th + .3))
        else:
            bob = c['bob'][0] * wave(th, 0., .22, .7) + c['bob'][1] * math.sin(3 * th + 1.2)
            sway = c['sway'] * wave(th, .8, .3, .5)
            roll = c['roll'] * wave(th, 1.8, .2, .3)
            nod = c['pitch'] * wave(th, 1.0, .25, 1.1)
            yaw = c['yaw'] * wave(th, 2.6, .25, .9)
        pose[BODY][6] += round(sway)
        pose[BODY][7] += round(c['drop'] - bob)
        rig.turn(pose, BODY, x=c['lean'] + nod, y=yaw, z=roll)
        # the disc under the body, the tuft on top and the arms follow the body a few ticks late, segment after segment
        sw, rs, droop, lag = c['arm']
        tsw, tlag, tmean = c['tuft']
        rig.turn(pose, DISC, x=-.8 * nod * .3, z=c['disc'] * wave(th, 1.2, .2, .4))
        rig.turn(pose, TUFT, x=tmean + tsw * wave(th, 1.0 + tlag, .3, .6), z=.9 * tsw * wave(th, 2.3 + tlag, .25, 1.4))
        for arm, side, k in ((ARM_R, 1, 0), (ARM_L, -1, 1)):
            a, b, hand = arm
            ph0 = 0. if side > 0 else (math.pi if c['speed'] else 1.7)
            if not c['speed']:
                ph0 = 1.1 * k
            rig.turn(pose, a, x=ARM_FWD + sw * wave(th, ph0, .3, .8), y=side * ARM_YAW,
                     z=side * (droop * .6 - ARM_UP * .7 + rs * wave(th, ph0 + .8, .3, 1.3)))
            rig.turn(pose, b, x=.8 * sw * wave(th, ph0 + lag * 2.2, .35, 1.0),
                     z=side * (droop * .4 - ARM_UP * .3 + .8 * rs * wave(th, ph0 + .8 + lag * 2.2, .3, 1.5)))
            rig.turn(pose, hand, x=1.0 * sw * wave(th, ph0 + lag * 4.4, .4, 1.2),
                     z=side * .8 * rs * wave(th, ph0 + .8 + lag * 4.4, .3, 1.7))
        # the legs, from the tip
        miss = {}
        stance = {}
        for leg in LEGS:
            target, stands = self.foot(leg, t)
            miss[leg] = o.solve(pose, leg, target)
            stance[leg] = stands
        return pose, miss, stance


def neutral_pose(o, base):
    """The standing pose all clips start from: the base pose with every leg solved onto its foot."""
    o.find_tips()
    pose = copy.deepcopy(base)
    pose[0] = [4096] * 3 + [0, 0, 0, 0, 0, 0]
    contact = {}
    for leg in LEGS:
        for _ in range(2):
            x, z = FOOT[leg]
            o.solve(pose, leg, (x, contact.get(leg, 0.), z), mu=(2., 2., 2.), iters=200)
            lowest = float(o.body.points(o.body.world(pose)[1], list(LEGS[leg][0]))[:, 1].max())
            contact[leg] = contact.get(leg, 0.) - lowest
    return pose, contact


def lowest_leg(o, pose, leg):
    return float(o.body.points(o.body.world(pose)[1], list(LEGS[leg][0]))[:, 1].max())


def author(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError("Octomon's scuttling clips are written over the reviewed import")
    mmd.exe().add_type(SPECIES, skeleton)
    old = mmd.MMD.parse(data, NB)
    old.type = SPECIES
    o = Octomon(old, skeleton)
    base = [[round(x) for x in v] for v in animsheet.slot_frames(old, NB, 0)[0][0]]
    neutral, contact = neutral_pose(o, base)
    result = copy.deepcopy(old)
    streams, checks = {}, []
    for slot in (0, 2, 3, 4):
        name = CLIP_OF_SLOT[slot]
        frames, loop, events = animsheet.slot_frames(old, NB, slot)
        assert loop == 0, (slot, loop)
        clip = Clip(o, name, neutral, contact)
        rig = Rig(old, skeleton)
        out, worst = [], 0.
        for t in range(clip.n):
            pose, miss, stance = clip.pose_at(t, rig)
            worst = max(worst, max(miss.values()))
            if worst > MAX_ERROR:
                raise ValueError(f'{name}: a leg misses its target by {worst:.1f} units at tick {t} (it cannot reach)')
            for leg, stands in stance.items():
                if stands and lowest_leg(o, pose, leg) > FLOOR:
                    raise ValueError(f'{name}: leg {leg} is {lowest_leg(o, pose, leg):.1f} units under the floor at tick {t}')
            pose[0] = [4096] * 3 + [0, 0, 0, 0, 0, -round(clip.c['speed'] * t)]
            out.append([[round(x) for x in v] for v in pose])
        out.append(copy.deepcopy(out[0]))
        out[-1][0] = [4096] * 3 + [0, 0, 0, 0, 0, -clip.c['speed'] * clip.n]
        mmd.close_loop(out, 0)
        streams[slot] = len(result.anims.anims)
        result.anims.anims.append(mmd.encode_anim(out, NB, 0, list(events), tol=1))
    for slot in SHARED_WITH_IDLE:
        result.anims.table[slot] = streams[0]
    for slot in (0, 2, 3, 4):
        result.anims.table[slot] = streams[slot]
    for anim in result.anims.anims:
        anim.tail = b''
    used = sorted({i for i in result.anims.table if i is not None})
    renumber = {i: k for k, i in enumerate(used)}
    result.anims.anims = [result.anims.anims[i] for i in used]
    result.anims.table = [None if i is None else renumber[i] for i in result.anims.table]
    result.anims.anims, result.anims.table = motioncyclelayer.share_identical_streams(result.anims.anims, result.anims.table)
    output = result.build()
    effective = mmd.MMD.parse(output, NB)
    effective.type = SPECIES
    assert effective.tmd.build() == old.tmd.build()
    changed = changed_programs(old, effective)
    assert set(changed) == set(SLOTS) | set(SHARED_WITH_IDLE), changed
    for slot in SLOTS:
        samples, loop, _ = animsheet.slot_frames(effective, NB, slot)
        assert loop == 0
        checks.append(dict(slot=slot, ticks=len(samples) - 1,
                           root_per_tick=round((samples[-1][0][8] - samples[0][0][8]) / (len(samples) - 1), 2)))
    return output, dict(checks=checks, storage=motionstorage.require(output, NB), species=SPECIES, source_sha256=SOURCE,
                        changed_slots=changed)


def build(data, skeleton):
    output, report = author(data, skeleton)
    return output, dict(report, output_sha256=hashlib.sha256(output).hexdigest())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    skeleton = json.loads((ROOT / 'content/species/278-octomon.json').read_text())['model']['skeleton']
    data, report = build(args.source.read_bytes(), skeleton)
    args.out.write_bytes(data)
    print(args.out, len(data), 'B', report['storage'], report['checks'])


if __name__ == '__main__':
    main()
