"""Armageddemon's field idle, walk, tired walk and run: a six-legged spider scuttle (species 407).

The model: bone 1 is the body, bone 2 the neck with the head 3 and the jaw 4 in front (-z), the four-bone tail 5-8 trails
behind (+z). Six three-bone legs hang from the body, three a side: the front legs (right 15-16-17, left 24-25-26), the
middle legs (12-13-14, 18-19-20) and the rear legs (9-10-11, 21-22-23). The soles are flat paddles on the floor.

Offline only (player builds replay the pinned delta): `tools/models/edit.py get 407` on the commit before this change,
then `python3 -m tools.models.field_animations.armageddemon_gait --source THAT.MMD --out AFTER.MMD` and
`edit.py put 407 AFTER.MMD`. Only slots 0, 2, 3 and 4 change; the gestures and attacks stay.

- A leg is solved from its sole down (damped least squares on the bones' own turns): in stance the sole stands on one
  point of the floor while the body passes over it, in swing it rises high and lands in a quick arc. The lowest vertex of
  every leg is held on the floor in stance.
- Walk, tired walk and run alternate two groups of three (front right, middle left, rear right; then the others) with a
  ripple of a tick or two inside a group; the tired walk steps one leg at a time with the body low and the soles dragged.
- The body bobs twice per stride, sways and rolls to the side that carries it; the neck and head lag its twist, the jaw
  twitches and the tail follows the body with a travelling wave, a beat behind.
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
from tools.models.field_animations.octomon_scuttle import hermite, rodrigues, orthonormal, rmat, bump  # noqa: E402

SPECIES, NB = 407, 27
SOURCE = "528518e0ff289d66eed70630e892b0c904d521387b85b3c0cf343bd834c84c89"   # edit.py get 407 before this change
SLOTS = (0, 2, 3, 4)
TWINS_OF_IDLE = ()
CLIP_OF_SLOT = {0: 'idle', 2: 'walk', 3: 'tired', 4: 'run'}
BODY, NECK, HEAD, JAW = 1, 2, 3, 4
TAIL = (5, 6, 7, 8)
LEGS = {'RF': ((15, 16, 17), 1), 'LF': ((24, 25, 26), -1), 'RM': ((12, 13, 14), 1), 'LM': ((18, 19, 20), -1),
        'RR': ((9, 10, 11), 1), 'LR': ((21, 22, 23), -1)}
FLOOR = 6.0
MAX_ERROR = 1.5
BASE_Y = -175
TAIL_DROOP = 0.

GROUP_A = dict(RF=0., LM=1 / 12, RR=2 / 12)
GROUP_B = dict(LF=.5, RM=.5 + 1 / 12, LR=.5 + 2 / 12)
TRIPODS = {**GROUP_A, **GROUP_B}
STALK = dict(RF=0., LM=1 / 6, RR=2 / 6, LF=3 / 6, RM=4 / 6, LR=5 / 6)
RUN = dict(RF=0., LM=1 / 8, RR=0., LF=.5, RM=.5 + 1 / 8, LR=.5)

CLIPS = {
    'idle': dict(n=72, reps=1, speed=0, h=0., xs=1., breath=2.6, sway=3., roll=.8, pitch=.7, yaw=1.8, lean=0., tail=5.,
                 head=3., jaw=3.),
    'walk': dict(n=12, reps=2, speed=22, duty=7 / 12, start=TRIPODS,
                 lift=dict(RF=110, LF=110, RM=120, LM=120, RR=110, LR=110), flair=20, hold=.15, h=6., xs=1., bob=3., sway=5., roll=1.6,
                 pitch=1., yaw=3., lean=1., tail=8., head=4., jaw=3.),
    'tired': dict(n=18, reps=2, speed=14, duty=12 / 18, start=STALK,
                  lift=dict(RF=40, LF=40, RM=44, LM=44, RR=40, LR=40), flair=8, hold=.15, h=-40., xs=1., bob=2.5, sway=5., roll=2.2,
                  pitch=1.4, yaw=2.4, lean=4., tail=5., head=3., jaw=2.),
    'run': dict(n=8, reps=2, speed=42, duty=3 / 8, start=RUN,
                lift=dict(RF=120, LF=120, RM=130, LM=130, RR=120, LR=120), flair=22, hold=.15, h=2., xs=1., bob=4.5, sway=4., roll=1.8,
                pitch=1.6, yaw=3.4, lean=4.5, tail=10., head=5., jaw=4.),
}
PAWS = dict(RF=(.10, .40, 30., 20.), LF=(.54, .78, 24., 14.), LM=(.80, .96, 14., 8.))


def wv(x, lag=0., second=.3, shift=.9):
    """One beat that is not a pure sine: a second harmonic leans it."""
    return math.sin(x - lag) + second * math.sin(2 * (x - lag) + shift)


class Spider:
    """The model, its rig and the leg solver."""

    def __init__(self, model, skeleton, rest):
        self.model, self.skeleton = model, skeleton
        self.body = ol.Body(model, skeleton)
        self.parent = [p for _, p in skeleton]
        self.tip, self.foot = {}, {}
        mats = self.mats(rest)
        for name, (chain, _) in LEGS.items():
            lv = self.body.local_vertices(chain[-1])
            m = mats[chain[-1]]
            w = lv @ m[:3, :3].T + m[:3, 3]
            sole = w[:, 1] >= w[:, 1].max() - 8
            self.tip[name] = lv[sole].mean(0)
            c = w[sole].mean(0)
            self.foot[name] = (float(c[0]), float(c[2]))

    def mats(self, pose):
        p = copy.deepcopy(pose)
        p[0] = [4096] * 3 + [0] * 6
        return [np.array(m, float) for m in mmd.bone_matrices(self.model, p)]

    def tip_world(self, pose, name):
        m = self.mats(pose)[LEGS[name][0][-1]]
        return m[:3, :3] @ self.tip[name] + m[:3, 3]

    def solve(self, pose, name, target, mu=(300., 500., 700.), iters=80):
        """Turn the leg's bones until its tip is on `target`; returns the miss."""
        chain = LEGS[name][0]
        mats = self.mats(pose)
        rp, pp = orthonormal(mats[self.parent[chain[0]]][:3, :3]), mats[self.parent[chain[0]]][:3, 3]
        loc = [rmat(pose[b]) for b in chain]
        off = [np.array(pose[b][6:9], float) for b in chain]
        for _ in range(iters):
            wr, wp, r, p = [], [], rp, pp
            for i in range(len(chain)):
                p = p + r @ off[i]
                r = r @ loc[i]
                wr.append(r)
                wp.append(p)
            tip = wr[-1] @ self.tip[name] + wp[-1]
            err = np.asarray(target, float) - tip
            if np.linalg.norm(err) < .05:
                break
            cols = []
            for i in range(len(chain)):
                rad = tip - wp[i]
                for k in range(3):
                    e = np.zeros(3)
                    e[k] = 1
                    cols.append(np.cross(e, rad))
            J = np.array(cols).T
            d = np.linalg.solve(J.T @ J + np.diag(np.repeat(mu, 3)), J.T @ err).reshape(-1, 3)
            d = d * min(1., 0.35 / max(1e-9, float(np.abs(d).max())))
            par = [rp] + wr[:-1]
            for i in range(len(chain)):
                loc[i] = orthonormal(par[i].T @ rodrigues(d[i]) @ wr[i])
        for i, b in enumerate(chain):
            pose[b][3:6] = [round(a) for a in mmd.matrix_euler(loc[i].tolist(), pose[b][3:6])]
        return float(np.linalg.norm(np.asarray(target, float) - self.tip_world(pose, name)))

    def lowest(self, pose, leg):
        return float(self.body.points(self.body.world(pose)[1], list(LEGS[leg][0]))[:, 1].max())


def neutral_pose(o, base):
    """The standing pose all clips start from: the base pose, the body raised, every leg solved onto its foot."""
    pose = copy.deepcopy(base)
    pose[0] = [4096] * 3 + [0] * 6
    pose[BODY][7] = BASE_Y - round(CLIPS['idle']['h'])
    o.solve = o.solve
    contact = {}
    for leg in LEGS:
        for _ in range(3):
            x, z = o.foot[leg]
            o.solve(pose, leg, (x, contact.get(leg, 0.), z), mu=(2., 2., 2.), iters=300)
            contact[leg] = contact.get(leg, 0.) - o.lowest(pose, leg)
    return pose, contact


class Clip:
    def __init__(self, spider, name, neutral, contact):
        self.o, self.name, self.c = spider, name, CLIPS[name]
        self.neutral, self.contact = neutral, contact
        self.n = self.c['n'] * self.c['reps']

    # ---------------------------------------------------------------- legs
    def foot(self, leg, t):
        """Target of the leg's tip at tick t in the root's frame (x across, y down, z back), and whether it stands."""
        c = self.c
        x0, z0 = self.o.foot[leg]
        x0 *= c['xs']
        side = LEGS[leg][1]
        y0 = self.contact[leg]
        if not c['speed']:
            if leg in PAWS:
                a, b, up, reach = PAWS[leg]
                u = (t / self.n - a) / (b - a)
                if 0. < u < 1.:
                    s = math.sin(math.pi * u) ** 2
                    return (x0 - side * 6 * s, y0 - up * s, z0 - reach * s), False
            return (x0, y0, z0), True
        speed, duty, T = c['speed'], c['duty'], c['n']
        half = speed * T * duty / 2
        phase = ((t / T) - c['start'][leg]) % 1.0
        if phase < duty:
            return (x0, y0, z0 - half + 2 * half * phase / duty), True
        u = (phase - duty) / (1 - duty)
        tsw = T * (1 - duty)
        # the foot's travel over the ground is eased and kept for the middle of the swing: it rises first and comes down
        # on its place, so it only moves while it is in the air
        d = c['hold']
        w = min(1., max(0., (u - d) / (1 - 2 * d)))
        e = w * w * (3 - 2 * w)
        z = z0 + half - speed * T * e + speed * tsw * u
        x = x0 + side * c['flair'] * bump(u)
        y = y0 - c['lift'][leg] * math.sin(math.pi * u) ** .7
        return (x, y, z), False

    # ---------------------------------------------------------------- body, abdomen, face, palps
    def terms(self, t):
        c, n = self.c, self.n
        th = 2 * math.pi * t / n
        T = c['n']
        stride = (t % T) / T
        cycle = t // T
        if c['speed']:
            ph = 2 * math.pi * stride
            beat = 2 * ph - 2 * math.pi * c['duty']
            bob = c['bob'] * (math.cos(beat) + .2 * math.sin(2 * beat + .8)) / 1.2
            sway = c['sway'] * (math.sin(ph + .4) + .15 * math.sin(2 * ph - .5))
            roll = c['roll'] * (math.sin(ph + 1.0) + .15 * math.sin(3 * ph))
            nod = c['pitch'] * (math.cos(beat + .6) + .2 * math.sin(2 * beat))
            yaw = c['yaw'] * math.sin(ph + 1.6 + (0. if self.name != 'tired' else .0))
        else:
            ph = th
            bob = c['breath'] * wv(2 * th, 0., .22, .7) + .5 * math.sin(th + 1.2)
            sway = c['sway'] * wv(th, .8, .3, .5)
            roll = c['roll'] * wv(th, 1.8, .2, .3)
            nod = c['pitch'] * wv(2 * th, 1.0, .25, 1.1)
            yaw = c['yaw'] * wv(th, 2.6, .35, .9)
        return dict(th=th, ph=ph, stride=stride, cycle=cycle, bob=bob, sway=sway, roll=roll, nod=nod, yaw=yaw)

    def body_pose(self, t, rig):
        """The pose with the body, abdomen, face and palps placed (the legs still as in the standing pose)."""
        c = self.c
        pose = copy.deepcopy(self.neutral)
        rig.angles = {}
        k = self.terms(t)
        pose[BODY][6] += round(k['sway'])
        pose[BODY][7] = BASE_Y - round(c['h'] + k['bob'])
        rig.turn(pose, BODY, x=c['lean'] + k['nod'], y=k['yaw'], z=k['roll'])
        self.upper(pose, rig, k)
        return pose

    def upper(self, pose, rig, k):
        c, name = self.c, self.name
        th, ph = k['th'], k['ph']
        s = th if not c['speed'] else ph          # the clip's own phase: a turn of the loop (idle) or of the stride
        two = 2 * s
        # neck and head: the neck lags the body's nod, the head looks a little against its twist, the jaw twitches
        rig.turn(pose, NECK, x=-.5 * k['nod'] + .4 * c['head'] * wv(two, .8, .25, .6), y=-.5 * k['yaw'] + .5 * c['head'] * wv(s, 1.4, .3, .8))
        rig.turn(pose, HEAD, x=-.4 * k['nod'] + .5 * c['head'] * wv(two, 1.3, .3, .5), y=-.3 * k['yaw'] + .6 * c['head'] * wv(s, 2.0, .3, 1.0),
                 z=-.4 * k['roll'])
        f = k['stride'] if c['speed'] and k['cycle'] == 1 else (th / (2 * math.pi) if not c['speed'] else None)
        twitch = 0.
        if f is not None:
            u = (f - .55) / .25 if not c['speed'] else (f - .2) / .5
            if 0. <= u <= 1.:
                twitch = math.sin(math.pi * u * 3) ** 2 * math.sin(math.pi * u)
        rig.turn(pose, JAW, x=c['jaw'] * (1.2 * twitch + .4 * wv(two, 1.3, .3, 1.0)))
        # tail: follows the body with a travelling wave, each bone a beat behind the one before; it droops when tired
        droop = TAIL_DROOP if name == 'tired' else 0.
        for i, bone in enumerate(TAIL):
            lag = .7 * (i + 1)
            amp = c['tail'] * (.5 + .25 * i)
            rig.turn(pose, bone, x=droop * (1. if i == 0 else .5) + .5 * amp * wv(two, 1.0 + lag, .25, .6) - .3 * k['nod'] * (1 if i == 0 else 0),
                     y=-.5 * k['yaw'] * (1 if i == 0 else 0) + amp * wv(s, 1.6 + lag, .3, .8))

    def pose_at(self, t, rig, corr):
        """The pose at tick t, miss of each tip, and which legs stand. `corr[leg][t]` lifts the tip target so that the
        leg's lowest vertex, and not only its tip, rests on the floor."""
        o = self.o
        pose = self.body_pose(t, rig)
        miss, stance = {}, {}
        for leg in LEGS:
            (x, y, z), stands = self.foot(leg, t)
            miss[leg] = o.solve(pose, leg, (x, y - corr[leg][t], z))
            stance[leg] = stands
        return pose, miss, stance

    def corrections(self, rig):
        """For every leg and tick: how far the tip target is raised for the leg's lowest vertex to stand on the floor. Found
        in stance (a few solves per tick); a swing eases between the stance before and the stance after it."""
        o, n = self.o, self.n
        corr = {leg: [None] * n for leg in LEGS}
        for t in range(n):
            pose = self.body_pose(t, rig)
            for leg in LEGS:
                (x, y, z), stands = self.foot(leg, t)
                if not stands:
                    continue
                c = corr[leg][(t - 1) % n] or 0.
                for _ in range(4):
                    trial = copy.deepcopy(pose)
                    o.solve(trial, leg, (x, y - c, z))
                    low = o.lowest(trial, leg)
                    if abs(low) < .25:
                        break
                    c += low
                corr[leg][t] = c
        for leg in LEGS:
            row = corr[leg]
            if all(v is None for v in row):
                row[:] = [0.] * n
                continue
            for t in range(n):
                if row[t] is not None:
                    continue
                a = next(i for i in range(1, n) if row[(t - i) % n] is not None)
                b = next(i for i in range(1, n) if row[(t + i) % n] is not None)
                u = a / (a + b)
                row[t] = row[(t - a) % n] + (row[(t + b) % n] - row[(t - a) % n]) * u * u * (3 - 2 * u)
        # a leg in the air stays above the floor too
        for t in range(n):
            pose = None
            for leg in LEGS:
                (x, y, z), stands = self.foot(leg, t)
                if stands:
                    continue
                for _ in range(3):
                    pose = pose or self.body_pose(t, rig)
                    trial = copy.deepcopy(pose)
                    o.solve(trial, leg, (x, y - corr[leg][t], z))
                    low = o.lowest(trial, leg)
                    if low < .5:
                        break
                    corr[leg][t] += low
        return corr


def author(data, skeleton):
    if SOURCE and hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError("Armageddemon's spider clips are written over the reviewed model")
    mmd.exe().add_type(SPECIES, skeleton)
    old = mmd.MMD.parse(data, NB)
    old.type = SPECIES
    base = [[round(x) for x in v] for v in animsheet.slot_frames(old, NB, 0)[0][0]]
    o = Spider(old, skeleton, base)
    neutral, contact = neutral_pose(o, base)
    result = copy.deepcopy(old)
    streams, checks = {}, []
    for slot in (0, 2, 3, 4):
        name = CLIP_OF_SLOT[slot]
        frames, loop, events = animsheet.slot_frames(old, NB, slot)
        assert loop == 0, (slot, loop)
        events = [e for e in events if e[1] == 'tex' and e[0] == 0]
        clip = Clip(o, name, neutral, contact)
        rig = Rig(old, skeleton)
        out, worst = [], 0.
        corr = clip.corrections(rig)
        stands_before = {leg: clip.foot(leg, -1)[1] for leg in LEGS}
        for t in range(clip.n):
            pose, miss, stance = clip.pose_at(t, rig, corr)
            worst = max(worst, max(miss.values()))
            if worst > MAX_ERROR:
                raise ValueError(f'{name}: a leg misses its target by {worst:.1f} units at tick {t} (it cannot reach)')
            for leg, stands in stance.items():
                if stands and o.lowest(pose, leg) > FLOOR:
                    raise ValueError(f'{name}: leg {leg} is {o.lowest(pose, leg):.1f} units under the floor at tick {t}')
            pose[0] = [4096] * 3 + [0, 0, 0, 0, 0, -round(clip.c['speed'] * t)]
            out.append([[round(x) for x in v] for v in pose])
            if clip.c['speed']:
                for leg in footfall_legs(name):
                    if stance[leg] and not stands_before[leg]:
                        events.append((t, 'sound', {'op': 'sound', 'frame': t + 1, 'bank': 1, 'note': 12}))
            stands_before = stance
        out.append(copy.deepcopy(out[0]))
        out[-1][0] = [4096] * 3 + [0, 0, 0, 0, 0, -clip.c['speed'] * clip.n]
        mmd.close_loop(out, 0)
        streams[slot] = len(result.anims.anims)
        result.anims.anims.append(mmd.encode_anim(out, NB, 0, list(events), tol=1))
    for slot in TWINS_OF_IDLE:
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
    assert set(changed) == set(SLOTS), changed
    for slot in SLOTS:
        samples, loop, _ = animsheet.slot_frames(effective, NB, slot)
        assert loop == 0
        checks.append(dict(slot=slot, ticks=len(samples) - 1,
                           root_per_tick=round((samples[-1][0][8] - samples[0][0][8]) / (len(samples) - 1), 2)))
    return output, dict(checks=checks, storage=motionstorage.require(output, NB), species=SPECIES, changed_slots=changed)


def footfall_legs(name):
    """The legs whose touchdowns make a sound: one of each group, so the beat is the stride's pulse."""
    return {'walk': ('RF', 'LF'), 'tired': ('RF', 'LR'), 'run': ('RF', 'LF')}[name]


def build(data, skeleton):
    output, report = author(data, skeleton)
    return output, dict(report, output_sha256=hashlib.sha256(output).hexdigest())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    skeleton = json.loads((ROOT / 'content/species/407-armageddemon.json').read_text())['model']['skeleton']
    data, report = build(args.source.read_bytes(), skeleton)
    args.out.write_bytes(data)
    print(args.out, len(data), 'B', report['storage'], report['checks'])


if __name__ == '__main__':
    main()
