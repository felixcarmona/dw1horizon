"""Dokugumon's field idle, walk, tired walk and run: a spider on six planted legs (species 298).

The import's four clips (61, 25, 29 and 21 ticks) hung the legs from a low body and swung them as one block: no leg ever
stood still on the floor (foot slip 90 to 115 %), the pairs moved together like a crab's and the abdomen and the two
palps hardly moved. Offline only (player builds replay the pinned delta): `tools/models/edit.py get 298` on the commit
before this change, then `python3 -m tools.models.field_animations.dokugumon_gait --source THAT.MMD --out AFTER.MMD` and
`edit.py put 298 AFTER.MMD`.

The model: bone 1 is the body, bone 22 the face with the fangs 23, bone 2 the abdomen behind it (+z) with the spinneret 3.
Six three-bone legs hang from the body, three a side: the rear legs (left 4-5-6, right 13-14-15, tips 150 units behind the
body), the middle legs (7-8-9, 16-17-18) and the front legs (10-11-12, 19-20-21). A palp is carried in front of the face
on each side (left 24-25, right 26-27). The spider faces -z.

- A leg is solved from its tip down (damped least squares on the bones' own turns, knee up): in stance the tip stands on one
  point of the floor while the body passes over it, in swing it rises high and lands in a quick arc whose speed matches
  the stance at both ends. The lowest vertex of every leg is held at the floor in stance; a leg that cannot reach stops the
  build. The body rides 50 units higher than the import's and the feet are set wide.
- Walk, tired walk and run alternate two groups of three: the front right, middle left and rear right legs step, then
  the front left, middle right and rear left, with a ripple of a tick or two inside a group. Walk (10 ticks a stride,
  18 units a tick) is quick and small, run (8 ticks, 40) the same scuttle with a flight phase and the body leaning
  forward, tired walk (16 ticks, 12) a stalking one: one leg at a time, the body low, the tips lifted little and dragged.
  Every clip repeats its stride twice per loop and the second differs a little (the palps, the fangs), so it does not feel
  stamped.
- The body stays calm: a small bob twice per stride, a sway and roll to the side that carries it, a twist toward the
  stepping group. The abdomen swings against the twist and a beat late, the spinneret after it; the fangs twitch and the
  palps probe softly.
- Idle (72 ticks): all six feet planted, the body and abdomen breathe, a front leg paws once in place, a middle leg shifts,
  the palps feel about and the fangs flex once.

Every clip repeats its pose cycle exactly, the root travels the same distance every tick and the idle's twin slot 33
follows the idle.
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

SPECIES, NB = 298, 28
SOURCE = "1517385898636504f5824a052cb308a0b18b2c768b4cd8fe4a0f86b99f1b6c01"   # edit.py get 298 before this change
SLOTS = (0, 2, 3, 4, 33)
TWINS_OF_IDLE = (33,)
CLIP_OF_SLOT = {0: 'idle', 2: 'walk', 3: 'tired', 4: 'run'}
BODY, ABDOMEN, SPINNERET, FACE, FANGS = 1, 2, 3, 22, 23
PALP_L, PALP_R = (24, 25), (26, 27)
# name: (bones from the hip, side)
LEGS = {'RF': ((19, 20, 21), 1), 'LF': ((10, 11, 12), -1), 'RM': ((16, 17, 18), 1), 'LM': ((7, 8, 9), -1),
        'RR': ((13, 14, 15), 1), 'LR': ((4, 5, 6), -1)}
# where each tip stands in the middle of its stance, on the floor (x, z; the body at rest is at x 0, z 0, the spider faces -z)
FOOT = {'RF': (200, -155), 'LF': (-200, -155), 'RM': (262, 15), 'LM': (-262, 15), 'RR': (228, 185), 'LR': (-228, 185)}
FLOOR = 6.0           # units a leg may sink in a stance tick
MAX_ERROR = 1.5       # units a tip may miss its target (a leg that cannot reach stops the build)
BASE_Y = -136         # the body bone's height in the import's rest pose

GROUP_A = dict(RF=0., LM=.03, RR=.06)
GROUP_B = dict(LF=.5, RM=.53, LR=.56)
TRIPODS = {**GROUP_A, **GROUP_B}
STALK = dict(RF=0., LM=1 / 6, RR=2 / 6, LF=3 / 6, RM=4 / 6, LR=5 / 6)
RUN = dict(RF=0., LM=.02, RR=.04, LF=.5, RM=.52, LR=.54)

#   n: ticks of one stride; reps: strides in the loop; speed: units a tick; duty: share of a stride on the floor;
#   start: touchdown phase of each leg; lift/flair: height and sideways bow of the swing; h: body height gain (units);
#   bob/sway/roll/pitch/yaw: body terms (units, degrees); lean: mean pitch (nose down positive);
#   abd: abdomen swing (degrees), palp / fang: amplitudes (degrees)
CLIPS = {
    'idle': dict(n=72, reps=1, speed=0, h=46., breath=2.6, sway=3., roll=.8, pitch=.7, yaw=1.8, lean=0., abd=1.6, palp=5.,
                 fang=3.),
    'walk': dict(n=10, reps=2, speed=18, duty=.62, start=TRIPODS,
                 lift=dict(RF=75, LF=75, RM=80, LM=80, RR=75, LR=75), flair=14, h=46., bob=3., sway=5., roll=1.6,
                 pitch=1., yaw=3., lean=1., abd=4., palp=6., fang=3.),
    'tired': dict(n=16, reps=2, speed=12, duty=.76, start=STALK,
                  lift=dict(RF=34, LF=34, RM=38, LM=38, RR=34, LR=34), flair=6, h=24., bob=2.5, sway=5., roll=2.2,
                  pitch=1.4, yaw=2.4, lean=4., abd=3., palp=5., fang=2.),
    'run': dict(n=8, reps=2, speed=40, duty=.46, start=RUN,
                lift=dict(RF=85, LF=85, RM=90, LM=90, RR=85, LR=85), flair=16, h=44., bob=4.5, sway=4., roll=1.8,
                pitch=1.6, yaw=3.4, lean=4.5, abd=5., palp=7., fang=4.),
}
# an idle leg paws in place: leg -> (start, end of the window in loop turns, height, reach forward)
PAWS = dict(RF=(.10, .40, 18., 12.), LF=(.54, .78, 14., 9.), LM=(.80, .96, 8., 5.))


def wv(x, lag=0., second=.3, shift=.9):
    """One beat that is not a pure sine: a second harmonic leans it."""
    return math.sin(x - lag) + second * math.sin(2 * (x - lag) + shift)


class Spider:
    """The model, its rig and the leg solver."""

    def __init__(self, model, skeleton):
        self.model, self.skeleton = model, skeleton
        self.body = ol.Body(model, skeleton)
        self.parent = [p for _, p in skeleton]
        self.tip = {}
        for name, (chain, _) in LEGS.items():
            lv = self.body.local_vertices(chain[-1])
            self.tip[name] = lv[int(np.argmax(np.linalg.norm(lv, axis=1)))]

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
    contact = {}
    for leg in LEGS:
        for _ in range(3):
            x, z = FOOT[leg]
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
        x0, z0 = FOOT[leg]
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
        z = hermite(z0 + half, z0 - half, speed * tsw, speed * tsw, u)
        x = x0 + side * c['flair'] * bump(u)
        y = y0 - c['lift'][leg] * bump(u ** .85)
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
        abd = c['abd']
        # abdomen: against the body's twist and a beat behind its bob; the spinneret follows it
        droop = 3.5 if name == 'tired' else 0.
        rig.turn(pose, ABDOMEN, x=droop - .5 * k['nod'] + .45 * abd * wv(two, 1.2, .25, .6), y=-.9 * k['yaw'] + .3 * abd * wv(s, 1.6, .3, .8),
                 z=-.5 * k['roll'])
        rig.turn(pose, SPINNERET, x=.5 * abd * wv(two, 2.0, .3, 1.0), y=.45 * abd * wv(s, 2.4, .3, 1.2))
        # face and fangs: the face lags the body's nod, the fangs twitch softly (a quick small beat once a loop)
        rig.turn(pose, FACE, x=-.6 * k['nod'] + .6 * c['fang'] * wv(two, .7, .3, .5), y=.5 * k['yaw'])
        f = k['stride'] if c['speed'] and k['cycle'] == 1 else (th / (2 * math.pi) if not c['speed'] else None)
        twitch = 0.
        if f is not None:
            u = (f - .55) / .25 if not c['speed'] else (f - .2) / .5
            if 0. <= u <= 1.:
                twitch = math.sin(math.pi * u * 3) ** 2 * math.sin(math.pi * u)
        rig.turn(pose, FANGS, x=c['fang'] * (1.2 * twitch + .4 * wv(two, 1.3, .3, 1.0)))
        # palps: they probe, left and right unrelated
        level = -.8 * (c['lean'] + k['nod'])
        for chain, side, ph0 in ((PALP_L, -1, 0.), (PALP_R, 1, 2.3)):
            a, b = chain
            amp = c['palp']
            rig.turn(pose, a, x=level + .6 * amp * wv(s, ph0 + .3, .3, .8), y=side * (.5 * amp + .7 * amp * wv(s, ph0 + .9, .25, 1.2)))
            rig.turn(pose, b, x=.8 * amp * wv(two, ph0 + 1.1, .35, 1.0), y=.5 * amp * wv(s, ph0 + 1.8, .3, 1.5))

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
        raise ValueError("Dokugumon's spider clips are written over the reviewed import")
    mmd.exe().add_type(SPECIES, skeleton)
    old = mmd.MMD.parse(data, NB)
    old.type = SPECIES
    o = Spider(old, skeleton)
    base = [[round(x) for x in v] for v in animsheet.slot_frames(old, NB, 0)[0][0]]
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
    skeleton = json.loads((ROOT / 'content/species/298-dokugumon.json').read_text())['model']['skeleton']
    data, report = build(args.source.read_bytes(), skeleton)
    args.out.write_bytes(data)
    print(args.out, len(data), 'B', report['storage'], report['checks'])


if __name__ == '__main__':
    main()
