"""Arukenimon's field idle, walk, tired walk and run: a woman's body on a spider's six planted legs (species 311).

The import's four clips swung the six legs as rigid posts (the tips slid over the floor: foot slip 100 % in the walk and
the tired walk, 75 to 95 % in the run), the tired walk folded four of them up into the body and left the spider lying on
two legs (rolled 40 degrees, the shins inside the abdomen and the sleeves inside the chest) and the sleeves flailed through
115 to 120 degrees at 30 degrees a tick in every clip, the idle's too. The run (66 units a tick) and the tired walk
(27) were also outside the native speeds. Offline only (player builds replay the pinned delta): `tools/models/edit.py get
311` on the commit before this change, then `python3 -m tools.models.field_animations.arukenimon_gait --source THAT.MMD
--out AFTER.MMD` and `edit.py put 311 AFTER.MMD`.

The model: bone 1 is the pelvis (rest tilt of 16 degrees, undone by the bones under it), bone 12 the spider's abdomen under
it and bone 2 the woman's torso, the head 4 with the jaw 5 and the neck piece 3 beside it, the arms 6-7-8 (left) and 9-10-11
(right): the shoulder, the elbow and the long sleeve's hand. Six two-bone legs hang from the abdomen (the knee up and
out, the shin down to the floor): rear (left 19-20, right 21-22), middle (17-18, 13-14) and front (15-16, 23-24). It faces -z.

- A leg is solved from its tip down (damped least squares on the bones' own turns): in stance the tip stands on one point of
  the floor while the body passes over it, in swing it rises in a quick arc whose speed matches the stance at both ends. The
  lowest vertex of every leg is held at the floor in stance; a leg that cannot reach stops the build. The body rides higher
  than the import's and the feet are set wide.
- Walk, tired walk and run alternate two groups of three legs (front right, middle left and rear right, then the others)
  with a ripple of a tick or two inside a group; the tired walk steps one leg at a time with the body low.
- The woman does not ride rigidly: her torso turns against the pelvis a beat late, bows with the stride and leans into the
  run, her head stays level and lags it, the arms hang from the shoulders as delayed pendulums (the elbow after the shoulder,
  the sleeve after the elbow) and the jaw hardly moves. The tired walk hunches her and lets the arms hang.
- Idle: all six feet planted, the body breathes, the torso sways, she glances to one side and the other, an arm lifts and
  settles, a front leg paws once and a middle leg shifts.

Every clip repeats its pose cycle exactly, the root travels the same distance every tick, the idle's twin slot 33 follows the
idle and the walk's and run's twins (slots 35 and 36) follow them. The battle slots 33, 35 and 36 are then replaced by the
source game's own clips, repaired (battle-rebuilds.json), after this overlay.
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

SPECIES, NB = 311, 25
SOURCE = "f4b1d78f075f39717881b13cdd2ab75056defcb9621cb65e8f17b2370c8f0cdb"   # edit.py get 311 before this change
TWINS = {0: (33,), 2: (35,), 4: (36,)}
SLOTS = (0, 2, 3, 4, 33, 35, 36)
CLIP_OF_SLOT = {0: 'idle', 2: 'walk', 3: 'tired', 4: 'run'}
PELVIS, TORSO, NECK, HEAD, JAW, ABDOMEN = 1, 2, 3, 4, 5, 12
ARM_L, ARM_R = (6, 7, 8), (9, 10, 11)
# name: (bones from the hip, side)
LEGS = {'RF': ((23, 24), 1), 'LF': ((15, 16), -1), 'RM': ((13, 14), 1), 'LM': ((17, 18), -1),
        'RR': ((21, 22), 1), 'LR': ((19, 20), -1)}
# where each tip stands in the middle of its stance, on the floor (x, z; the abdomen at rest is at x 0, z 0, it faces -z)
FOOT = {'RF': (225, -215), 'LF': (-225, -215), 'RM': (292, 0), 'LM': (-292, 0), 'RR': (225, 215), 'LR': (-225, 215)}
FLOOR = 6.0           # units a leg may sink in a stance tick
MAX_ERROR = 1.5       # units a tip may miss its target (a leg that cannot reach stops the build)
BASE_Y = -333         # the pelvis bone's height in the import's rest pose

GROUP_A = dict(RF=0., LM=.03, RR=.06)
GROUP_B = dict(LF=.5, RM=.53, LR=.56)
TRIPODS = {**GROUP_A, **GROUP_B}
STALK = dict(RF=0., LM=1 / 6, RR=2 / 6, LF=3 / 6, RM=4 / 6, LR=5 / 6)
RUN = dict(RF=0., LM=.02, RR=.04, LF=.5, RM=.52, LR=.54)

#   n: ticks of one stride; reps: strides in the loop; speed: units a tick; duty: share of a stride on the floor;
#   start: touchdown phase of each leg; lift/flair: height and sideways bow of the swing; h: body height gain (units);
#   bob/sway/roll/pitch/yaw: pelvis terms (units, degrees); lean: mean pitch of the torso (bow forward positive);
#   twist/bow/side: torso against the pelvis (degrees); head: head nod (degrees); arm: shoulder swing (degrees)
CLIPS = {
    'idle': dict(n=96, reps=1, speed=0, h=14., breath=5., sway=5., roll=1.2, pitch=.8, yaw=2.0, lean=2., twist=7., bow=4.,
                 side=5., head=3., arm=4.),
    'walk': dict(n=12, reps=2, speed=24, duty=.60, start=TRIPODS,
                 lift=dict(RF=70, LF=70, RM=74, LM=74, RR=70, LR=70), flair=12, h=30., bob=6., sway=8., roll=2.4,
                 pitch=2., yaw=5., lean=5., twist=14., bow=7., side=6., head=4., arm=7.),
    'tired': dict(n=18, reps=2, speed=13, duty=.76, start=STALK,
                  lift=dict(RF=34, LF=34, RM=38, LM=38, RR=34, LR=34), flair=6, h=6., bob=5., sway=8., roll=3.4,
                  pitch=2.4, yaw=4., lean=14., twist=8., bow=7., side=9., head=7., arm=3.),
    'run': dict(n=8, reps=2, speed=44, duty=.46, start=RUN,
                lift=dict(RF=84, LF=84, RM=88, LM=88, RR=84, LR=84), flair=14, h=40., bob=8., sway=6., roll=3.,
                pitch=2.6, yaw=6., lean=14., twist=13., bow=8., side=6., head=4., arm=9.),
}
# an idle leg paws in place: leg -> (start, end of the window in loop turns, height, reach forward)
ARM_KEEP = (.6, .5, .6)       # share of the torso's bow, turn and roll the shoulders undo
PAWS = dict(RF=(.12, .38, 18., 12.), LM=(.55, .70, 10., 6.))


def wv(x, lag=0., second=.3, shift=.9):
    """One beat that is not a pure sine: a second harmonic leans it."""
    return math.sin(x - lag) + second * math.sin(2 * (x - lag) + shift)


def glance(f, a, b, peak=1.):
    """0 outside the window (a, b) of a loop turn f, a smooth hump inside it."""
    u = (f - a) / (b - a)
    if not 0. < u < 1.:
        return 0.
    return peak * math.sin(math.pi * u) ** 2


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

    def solve(self, pose, name, target, mu=(400., 700.), iters=80):
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
    pose[PELVIS][7] = BASE_Y - round(CLIPS['idle']['h'])
    contact = {}
    for leg in LEGS:
        for _ in range(3):
            x, z = FOOT[leg]
            o.solve(pose, leg, (x, contact.get(leg, 0.), z), mu=(2., 2.), iters=300)
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

    # ---------------------------------------------------------------- pelvis terms
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
            yaw = c['yaw'] * math.sin(ph + 1.6)
        else:
            ph = th
            bob = c['breath'] * wv(2 * th, 0., .22, .7) + .5 * math.sin(th + 1.2)
            sway = c['sway'] * wv(th, .8, .3, .5)
            roll = c['roll'] * wv(th, 1.8, .2, .3)
            nod = c['pitch'] * wv(2 * th, 1.0, .25, 1.1)
            yaw = c['yaw'] * wv(th, 2.6, .35, .9)
        return dict(th=th, ph=ph, stride=stride, cycle=cycle, bob=bob, sway=sway, roll=roll, nod=nod, yaw=yaw)

    def body_pose(self, t, rig):
        """The pose with the pelvis, torso, head and arms placed (the legs still as in the standing pose)."""
        c = self.c
        pose = copy.deepcopy(self.neutral)
        rig.angles = {}
        k = self.terms(t)
        pose[PELVIS][6] += round(k['sway'])
        pose[PELVIS][7] = BASE_Y - round(c['h'] + k['bob'])
        rig.turn(pose, PELVIS, x=k['nod'], y=k['yaw'], z=k['roll'])
        self.upper(pose, rig, k, t)
        return pose

    def upper(self, pose, rig, k, t):
        c, name = self.c, self.name
        th, ph = k['th'], k['ph']
        s = th if not c['speed'] else ph          # the clip's own phase: a turn of the loop (idle) or of the stride
        two = 2 * s
        f = t / self.n                            # turns of the loop
        # torso: bows with the stride a beat after the pelvis, turns against it, leans forward (bow forward = x positive)
        tw = c['twist'] * wv(s, 1.0, .25, .7)
        bw = c['lean'] + c['bow'] * wv(two, 1.4, .25, .6)
        sd = c['side'] * wv(s, 1.9, .2, .4)
        look = 0.
        if not c['speed']:
            look = 15. * glance(f, .14, .42) - 11. * glance(f, .58, .84)
        rig.turn(pose, TORSO, x=bw, y=-.5 * k['yaw'] + tw, z=-.6 * k['roll'] + sd)
        # neck piece and head: level, lagging the torso; the head looks about in the idle
        rig.turn(pose, NECK, x=-.35 * bw + .3 * c['head'] * wv(two, 2.0, .3, .5))
        rig.turn(pose, HEAD, x=-.5 * bw - .5 * k['nod'] + c['head'] * wv(two, 2.4, .3, .9), y=-.6 * tw + look,
                 z=-.7 * sd + .3 * c['head'] * wv(s, 2.8, .3, .4))
        rig.turn(pose, JAW, x=.4 * c['head'] * wv(two, 3.0, .3, .5))
        # arms: delayed pendulums, shoulder then elbow then sleeve; the weight swings them against the bob
        a = c['arm']
        for chain, side, ph0 in ((ARM_L, -1, 0.), (ARM_R, 1, 2.1)):
            sh, el, wr = chain
            # the shoulders give back part of the torso's turn, roll and bow so the sleeves keep clear of the body
            rig.turn(pose, sh, x=-ARM_KEEP[0] * bw, y=-ARM_KEEP[1] * (tw - .5 * k['yaw']), z=-ARM_KEEP[2] * (-.6 * k['roll'] + sd))
            rig.turn(pose, sh, x=a * wv(s, 1.2 + ph0, .3, .6) - .25 * bw, z=side * (a * .35 * wv(s, 1.8 + ph0, .3, .9)))
            rig.turn(pose, el, x=.9 * a * wv(s, 1.8 + ph0, .3, .8), z=side * .3 * a * wv(s, 2.4 + ph0, .3, 1.1))
            rig.turn(pose, wr, x=1.3 * a * wv(s, 2.5 + ph0, .35, 1.0), z=side * .5 * a * wv(s, 3.0 + ph0, .3, 1.2))
        if not c['speed']:
            lift = glance(f, .46, .80)
            rig.turn(pose, ARM_R[0], x=-16. * lift, z=5. * lift)
            rig.turn(pose, ARM_R[1], x=-20. * lift)
            rig.turn(pose, ARM_R[2], x=-10. * wv(2 * math.pi * f * 2, .5, .3, .7) * lift)

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


def footfall_legs(name):
    """The legs whose touchdowns make a sound: one of each group, so the beat is the stride's pulse."""
    return {'walk': ('RF', 'LF'), 'tired': ('RF', 'LR'), 'run': ('RF', 'LF')}[name]


def author(data, skeleton):
    if SOURCE and hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError("Arukenimon's spider clips are written over the reviewed import")
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
        note = {2: 18, 3: 18, 4: 18}.get(slot)
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
                        events.append((t, 'sound', {'op': 'sound', 'frame': t + 1, 'bank': 1, 'note': note}))
            stands_before = stance
        out.append(copy.deepcopy(out[0]))
        out[-1][0] = [4096] * 3 + [0, 0, 0, 0, 0, -clip.c['speed'] * clip.n]
        mmd.close_loop(out, 0)
        streams[slot] = len(result.anims.anims)
        result.anims.anims.append(mmd.encode_anim(out, NB, 0, list(events), tol=1))
    for slot, twins in TWINS.items():
        for twin in twins:
            result.anims.table[twin] = streams[slot]
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


def build(data, skeleton):
    output, report = author(data, skeleton)
    return output, dict(report, output_sha256=hashlib.sha256(output).hexdigest())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    skeleton = json.loads((ROOT / 'content/species/311-arukenimon.json').read_text())['model']['skeleton']
    data, report = build(args.source.read_bytes(), skeleton)
    args.out.write_bytes(data)
    print(args.out, len(data), 'B', report['storage'], report['checks'])


if __name__ == '__main__':
    main()
