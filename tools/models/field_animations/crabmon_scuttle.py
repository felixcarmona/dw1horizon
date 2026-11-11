"""Crabmon's field idle, walk, tired walk and run: six legs that scuttle, two claws that carry on (species 284).

The import's idle, walk, tired walk and run (23, 25, 25 and 25 ticks) were one pose cycle with only the root faster: the
shell lay almost on the floor, the legs did not take a step (every tip slid along with the body, 100 % slip) and the claws
did not move. Offline only (player builds replay the pinned delta): `tools/models/edit.py get 284` on the commit before this
change, then `python3 -m tools.models.field_animations.crabmon_scuttle --source THAT.MMD --out AFTER.MMD` and
`edit.py put 284 AFTER.MMD`.

The model: bone 1 is the shell (the eyes are painted on it, there are no eye bones), bone 21 the flap under its front. Six
two-bone legs hang from it, three a side, and sweep out and back: the rear legs (right 8-9, left 2-3, tips 285 units behind
the shell's middle), the middle legs (10-11, 4-5) and the front legs (12-13, 6-7). The crab faces -z. Two claws are carried
low in front: the small left one (14-15-16, 16 is its movable finger) and the big right one (17-18-19, 20 is its finger,
a flat blade).

- A leg is solved from its tip down (damped least squares on the bones' own turns, knees up): in stance the tip stands on one
  point of the floor while the shell passes over it, in swing it rises, comes forward on a path whose speed matches the stance
  at both ends and lands. The lowest vertex of every leg is held at the floor in stance; a leg that cannot reach stops the build.
  The shell rides 12 to 30 units higher than the import's, so the legs are folded under it instead of lying flat.
- The four clips differ in footfall as well as in numbers. Walk (12 ticks a stride, 15 units a tick): a tetrapod, the legs
  in three pairs, each pair a third of a stride after the one before, a quick scuttle with the shell rocking over the
  carrying side. Tired walk (14 ticks, 10): a wave, one leg at a time, the shell low and leaning forward, claws trailing, feet
  dragged late. Run (8 ticks, 38): two tripods in turn with a flight phase, the shell pitched forward and bobbing high, the
  claws pulled in. Walk, tired walk and run repeat twice per loop and the second stride carries a flourish (a claw snap, a
  sigh, a claw flick), so the loop is longer than one stride and does not feel stamped.
- Idle (84 ticks): all six feet planted, the shell breathes twice a loop and shifts its weight once, glances (yaw) to
  one side and the other, the right claw opens and closes with lag and snaps once, the small claw flexes, the flap breathes.

Every clip repeats its pose cycle exactly, the root travels the same distance every tick and the idle's twin slots 1 and
0x12 follow the idle.
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

SPECIES, NB = 284, 22
SOURCE = "8550d165106d1f64c51b8075f4ac1070276e11a772768bab600f763df88fa8dc"   # sha256 of the import this was written over
SLOTS = (0, 1, 2, 3, 4, 18)
TWINS_OF_IDLE = (1, 18)
CLIP_OF_SLOT = {0: 'idle', 2: 'walk', 3: 'tired', 4: 'run'}
BODY, FLAP = 1, 21
CLAW_L, CLAW_R = (14, 15, 16), (17, 18, 19, 20)
# name: (bones from the hip, side)
LEGS = {'RC': ((12, 13), 1), 'LC': ((6, 7), -1), 'RB': ((10, 11), 1), 'LB': ((4, 5), -1), 'RA': ((8, 9), 1), 'LA': ((2, 3), -1)}
# where each tip stands in the middle of its stance, on the floor (x, z; the shell at rest is at x 0, z 0, the crab faces -z)
FOOT = {'RC': (244, 6), 'LC': (-244, 6), 'RB': (152, 100), 'LB': (-152, 100), 'RA': (196, 262), 'LA': (-196, 262)}
FLOOR = 6.0           # units a leg may sink in a stance tick
MAX_ERROR = 1.5       # units a tip may miss its target (a leg that cannot reach stops the build)
BASE_Y = -46          # the shell bone's height in the import's rest pose

#   n: ticks of one stride; reps: strides in the loop; speed: units a tick; duty: share of a stride on the floor;
#   start: touchdown phase of each leg; lift/flair: height and sideways bow of the swing; h: shell height gain (units);
#   bob/sway/roll/pitch/yaw: shell terms (units, degrees); lean: mean pitch (nose down positive)
PAIRS = dict(RC=0., LB=.0, RB=1 / 3, LA=1 / 3, RA=2 / 3, LC=2 / 3)
WAVE = dict(RC=0., RB=1 / 6, RA=2 / 6, LC=3 / 6, LB=4 / 6, LA=5 / 6)
TRIPODS = dict(RC=0., LB=.01, RA=.02, LC=.5, RB=.51, LA=.52)
CLIPS = {
    'idle': dict(n=84, reps=1, speed=0, h=30., breath=1.8, sway=3.2, roll=1.1, pitch=.9, yaw=3.2, lean=0.),
    'walk': dict(n=11, reps=2, speed=15, duty=.67, start=PAIRS,
                 lift=dict(RC=30, LC=30, RB=34, LB=34, RA=38, LA=38), flair=12, h=30., bob=4.2, sway=6., roll=3.4,
                 pitch=1.6, yaw=3.2, lean=1.5),
    'tired': dict(n=14, reps=2, speed=10, duty=.78, start=WAVE,
                  lift=dict(RC=18, LC=18, RB=20, LB=20, RA=22, LA=22), flair=6, h=13., bob=3., sway=5., roll=3.6,
                  pitch=1.8, yaw=2., lean=5.),
    'run': dict(n=7, reps=2, speed=38, duty=.33, start=TRIPODS,
                lift=dict(RC=40, LC=40, RB=44, LB=44, RA=50, LA=50), flair=14, h=26., bob=8., sway=5., roll=3.,
                pitch=2.4, yaw=2.4, lean=8.),
}


def wv(x, lag=0., second=.3, shift=.9):
    """One beat that is not a pure sine: a second harmonic leans it."""
    return math.sin(x - lag) + second * math.sin(2 * (x - lag) + shift)


class Crab:
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

    def solve(self, pose, name, target, mu=(300., 700.), iters=80):
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
    """The standing pose all clips start from: the base pose with every leg solved onto its foot."""
    pose = copy.deepcopy(base)
    pose[0] = [4096] * 3 + [0] * 6
    contact = {}
    for leg in LEGS:
        for _ in range(3):
            x, z = FOOT[leg]
            o.solve(pose, leg, (x, contact.get(leg, 0.), z), mu=(2., 2.), iters=200)
            contact[leg] = contact.get(leg, 0.) - o.lowest(pose, leg)
    return pose, contact


def snap(u, k=3.):
    """A quick open-and-shut of a claw over u in 0..1: two beats."""
    if not 0. <= u <= 1.:
        return 0.
    return math.sin(math.pi * u * k) ** 2 * math.sin(math.pi * u) if u < 1 else 0.


class Clip:
    def __init__(self, crab, name, neutral, contact):
        self.o, self.name, self.c = crab, name, CLIPS[name]
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
            return (x0, y0, z0), True
        speed, duty, T = c['speed'], c['duty'], c['n']
        half = speed * T * duty / 2
        phase = ((t / T) - c['start'][leg]) % 1.0
        if phase < duty:
            return (x0, y0, z0 - half + 2 * half * phase / duty), True
        u = (phase - duty) / (1 - duty)
        tsw = T * (1 - duty)
        z = hermite(z0 + half, z0 - half, speed * tsw, speed * tsw, u)
        x = x0 + side * c['flair'] * (1.7 if leg[1] == 'C' else 1.) * bump(u)
        y = y0 - c['lift'][leg] * bump(u ** .85)
        return (x, y, z), False

    # ---------------------------------------------------------------- body, claws, flap
    def terms(self, t):
        """Shell offsets and turns, then claw and flap turns, at tick t: dict of numbers."""
        c, n = self.c, self.n
        th = 2 * math.pi * t / n
        T = c['n']
        stride = (t % T) / T
        cycle = t // T
        if c['speed']:
            mid = c['duty'] / 2
            beat = 4 * math.pi * (stride - mid) if self.name != 'tired' else 6 * math.pi * (stride - mid)
            ph = 2 * math.pi * stride
            bob = c['bob'] * (math.cos(beat) + .22 * math.sin(2 * beat + .8)) / 1.2
            sway = c['sway'] * (math.sin(ph + .4) + .2 * math.sin(2 * ph - .5))
            roll = c['roll'] * (math.sin(ph + 1.0) + .15 * math.sin(3 * ph))
            nod = c['pitch'] * (math.cos(beat + .6) + .2 * math.sin(2 * beat))
            yaw = c['yaw'] * (math.sin(ph + 1.6) + .2 * math.sin(3 * ph + .3))
        else:
            ph = th
            bob = c['breath'] * wv(2 * th, 0., .22, .7) + .5 * math.sin(th + 1.2)
            sway = c['sway'] * wv(th, .8, .3, .5)
            roll = c['roll'] * wv(th, 1.8, .2, .3)
            nod = c['pitch'] * wv(2 * th, 1.0, .25, 1.1)
            yaw = c['yaw'] * wv(th, 2.6, .35, .9) + .8 * math.sin(3 * th + 1.)
        return dict(th=th, ph=ph, stride=stride, cycle=cycle, bob=bob, sway=sway, roll=roll, nod=nod, yaw=yaw)

    def body_pose(self, t, rig):
        """The pose with the shell, claws and flap placed (the legs still as in the standing pose)."""
        c = self.c
        pose = copy.deepcopy(self.neutral)
        rig.angles = {}
        k = self.terms(t)
        pose[BODY][6] += round(k['sway'])
        pose[BODY][7] = BASE_Y - round(c['h'] + k['bob'])
        rig.turn(pose, BODY, x=c['lean'] + k['nod'], y=k['yaw'], z=k['roll'])
        self.claws(pose, rig, t, k)
        return pose

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
            known = [t for t in range(n) if row[t] is not None]
            if not known:
                row[:] = [0.] * n
                continue
            for t in range(n):
                if row[t] is not None:
                    continue
                a = next(i for i in range(1, n) if row[(t - i) % n] is not None)
                b = next(i for i in range(1, n) if row[(t + i) % n] is not None)
                u = a / (a + b)
                row[t] = row[(t - a) % n] + (row[(t + b) % n] - row[(t - a) % n]) * u * u * (3 - 2 * u)
        # a leg in the air stays above the floor too (the stretched leg at the lift-off dips its lower edge)
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

    def claws(self, pose, rig, t, k):
        c, n = self.c, self.n
        th, ph, cycle = k['th'], k['ph'], k['cycle']
        name = self.name
        # amplitudes per clip: (carry yaw, carry lift, swing, finger open mean, finger swing)
        big = dict(idle=(0., 0., 2.5, 6., 5.), walk=(8., -2., 6., 8., 5.), tired=(8., 0., 3., 2., 2.), run=(12., -8., 6., 2., 3.))[name]
        small = dict(idle=(0., 0., 2.5, 4., 3.), walk=(0., -2., 3.5, 6., 4.), tired=(5., 0., 2., 2., 2.), run=(2., -8., 4., 3., 2.))[name]
        for chain, side, amp, ph0 in ((CLAW_R, 1, big, 0.), (CLAW_L, -1, small, 2.2)):
            yaw0, lift0, sw, fing0, fsw = amp
            lag = .7
            a, b = chain[0], chain[1]
            if c['speed']:
                w = lambda l, s=.3, sh=.8: wv(ph, ph0 + l, s, sh)
            else:
                w = lambda l, s=.3, sh=.8: wv(th, ph0 + l, s, sh)
            level = -.85 * (c['lean'] + k['nod'])      # the claws stay level while the shell pitches
            rig.turn(pose, a, x=lift0 + level + .6 * sw * w(0.), y=side * yaw0 + sw * w(.5, .25, 1.2))
            rig.turn(pose, b, x=.8 * sw * w(lag, .35, 1.0), y=.9 * sw * w(lag + .6, .3, 1.5))
            if len(chain) == 4:
                rig.turn(pose, chain[2], x=.6 * sw * w(2 * lag, .3, 1.1), y=.5 * sw * w(2 * lag + .8, .3, 1.7))
            finger = chain[-1]
            open_ = fing0 + fsw * w(1.1, .35, .7)
            # flourishes: the second stride (or one beat of the idle) snaps the big claw
            if side > 0 and cycle_flourish(name, k) is not None:
                open_ += 22. * cycle_flourish(name, k)
            rig.turn(pose, finger, y=-side * open_)
        # the flap under the shell's front breathes
        rig.turn(pose, FLAP, x=2. * wv(2 * th if not c['speed'] else 2 * ph, 0.5, .3, .6))


def cycle_flourish(name, k):
    """A bump (0..1) of the big claw's finger in the stride that carries the flourish, None elsewhere."""
    if name == 'idle':
        u = (k['th'] / (2 * math.pi) - .62) / .22
        return snap(u)
    if k['cycle'] == 1:
        u = k['stride'] / 1.0
        return snap(u, 2.) if name != 'run' else bump(u)
    return None


def lowest_leg(o, pose, leg):
    return o.lowest(pose, leg)


def author(data, skeleton):
    if SOURCE and hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError("Crabmon's scuttling clips are written over the reviewed import")
    mmd.exe().add_type(SPECIES, skeleton)
    old = mmd.MMD.parse(data, NB)
    old.type = SPECIES
    o = Crab(old, skeleton)
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
                if stands and lowest_leg(o, pose, leg) > FLOOR:
                    raise ValueError(f'{name}: leg {leg} is {lowest_leg(o, pose, leg):.1f} units under the floor at tick {t}')
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
    """The legs whose touchdowns make a sound: one of each pair or tripod, so the beat is the stride's pulse."""
    return {'walk': ('RC', 'RB', 'RA'), 'tired': ('RC', 'LC', 'RA'), 'run': ('RC', 'LC')}[name]


def build(data, skeleton):
    output, report = author(data, skeleton)
    return output, dict(report, output_sha256=hashlib.sha256(output).hexdigest())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    skeleton = json.loads((ROOT / 'content/species/284-crabmon.json').read_text())['model']['skeleton']
    data, report = build(args.source.read_bytes(), skeleton)
    args.out.write_bytes(data)
    print(args.out, len(data), 'B', report['storage'], report['checks'])


if __name__ == '__main__':
    main()
