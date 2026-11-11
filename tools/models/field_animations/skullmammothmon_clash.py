"""SkullMammothmon's walk, tired walk and run with the front legs kept out of the head.

Offline only (player builds replay the pinned delta): `tools/models/edit.py get 268` on the commit before this change,
then `python3 -m tools.models.field_animations.skullmammothmon_clash --source THAT.MMD --out AFTER.MMD` and
`edit.py put 268 AFTER.MMD`.

The model faces -z. Its head is bones 13 to 22: the neck (13), the skull (14), the trunk (15 to 17), the jaw (18), the two
ears (19, 20) and the two tusks (21, 22), which hang down to the floor. The front legs are bones 23 to 25 (left) and 26 to
28 (right) and swing forward under that head, so in the walk, the tired walk and the run their shins and feet went
through the jaw, the tusks and the trunk on nearly every tick (the idle is clean). Only slots 2, 3, 4 and 36 changed
(35 plays slot 2's program):

- the head is carried a little higher and nose-up: a turn of bone 13 about its own x axis and a lift of it, per tick
  (`TABLE`: pitch in degrees, nose up negative, and lift in model units);
- a leg that still crosses is turned at its shoulder (x and z), its knee (x) and its ankle (x), also per tick, only
  while it is in the air or dragging, and never so that its lowest point leaves the floor or sinks into it.

Everything else is the model's own: the timing of the legs, the lengths of the cycles, the root's travel, the other
bones' channels and every other program stay as they were. The table is fitted offline by `fit` (numpy): per tick the
cheapest head and leg turns that leave no crossing, a closed smoothing of them, and the repair of the ticks the smoothing
broke. The script refuses another source; the checks
that the corrected clips cross nothing, keep the body clashes and the feet's floor level, close their loops and fit the
storage budget are in `tools/test_skullmammothmon_clash.py` (the storage budget is also enforced by the build).
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
import retarget as R  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models.field_animations.channels import replace_channels  # noqa: E402

SPECIES, NB = 268, 29
SOURCE = '9d704639e855b455beba16a34df93889343d718e77eab323eee962b0dde910b6'    # edit.py get 268 before this change
HEAD = 13
HEAD_BONES = tuple(range(13, 23))
BODY_BONES = tuple(range(1, 13))
LEGS = {'L': (23, 24, 25), 'R': (26, 27, 28)}
SLOTS = (2, 3, 4, 36)            # walk, tired walk, run, and the run's twin program; slot 35 shares slot 2's program
TABLE_OF = {2: 2, 3: 3, 4: 4, 36: 4}
CHANNELS = {(HEAD, 3), (HEAD, 7)} | {(b, c) for leg in LEGS.values() for b in leg for c in (3, 4, 5)}
AXES = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
TOLERANCE = 2
FLOOR = 6.0              # a foot whose lowest vertex is within this of the floor is on it
MARGIN = (1.5, 5.0)      # how far below / above its own lowest point a foot on the floor may go
JUMP = 2.5               # a joint may turn this many times its median turn in one tick

# per tick (the closing tick repeats the first): head pitch in degrees (nose up negative), head lift in model units,
# then the left and the right leg: shoulder x, shoulder z, knee x, ankle x, in degrees
TABLE = {
    2: (
        (-1.3, 9.5, 2.5, -0.2, 1.0, 1.0, 1.0, -0.2, 0.2, 0.9), (-1.5, 11.2, 1.7, -0.1, 0.6, 0.6, 1.7, 0, 0.6, 1.2),
        (-2.3, 14.8, 1.0, 0, 0.4, 0.2, 2.6, 0.2, 1.0, 1.8), (-3.8, 21.4, 0.6, 0.3, 0.3, 0, 4.0, 0.5, 1.9, 2.6),
        (-4.8, 23.6, 0.4, 0.2, 0.2, 0, 4.7, 0.4, 2.8, 2.2), (-5.6, 24.5, 0.1, 0.2, 0.2, 0, 5.4, 0.2, 3.4, 2.0),
        (-6.4, 24.9, -0.5, 0.7, 0.1, 0, 6.1, 0.1, 4.5, 1.8), (-6.5, 22.1, 0.2, 0.1, -0.2, 0.2, 6.9, -0.4, 2.8, 1.3),
        (-7.1, 19.6, 0.6, 0, -0.3, 0.4, 8.7, -0.3, 1.4, 1.3), (-7.3, 14.8, 0.8, 0.1, -0.3, 0.3, 8.7, -1.0, 0.4, 1.3),
        (-7.4, 13.6, 2.0, 0.4, 0.2, 0.6, 7.3, -1.6, 0, 1.4), (-7.5, 12.6, 4.3, 0.9, 0.8, 1.0, 5.4, -2.0, 0, 1.3),
        (-7.5, 13.5, 7.1, 0.6, 1.9, 1.7, 3.6, -1.4, -0.1, 1.0), (-8.9, 18.9, 11.8, 0.8, 3.4, 2.5, 2.4, -1.0, 0, 0.4),
        (-10.3, 24.3, 16.5, 0.9, 4.8, 3.3, 1.3, -0.6, 0.2, -0.2), (-11.7, 32.6, 16.5, 1.1, 4.3, 3.0, 0.6, -0.3, 0.9, 0.3),
        (-10.0, 31.5, 15.4, 0.8, 3.4, 3.0, 0.1, -0.2, 0.6, -0.1), (-9.9, 30.2, 14.8, 0.9, 2.8, 3.3, 0.4, -0.3, 0.2, -0.2),
        (-9.0, 32.2, 13.9, 0.3, 2.7, 4.2, 0.2, -0.4, 0, 0), (-7.5, 27.7, 11.5, -2.1, 3.9, 4.7, 0.2, 0, 0, 0),
        (-5.6, 27.0, 9.2, -1.8, 4.7, 4.9, -0.5, -0.1, -0.3, 0), (-3.6, 19.6, 6.8, -1.5, 3.4, 3.7, 0, -0.3, 0, 0.2),
        (-2.1, 12.7, 4.8, -0.9, 2.3, 2.6, 0.3, -0.2, 0, 0.5), (-1.3, 9.5, 3.8, -0.2, 1.6, 1.7, 0.6, -0.2, -0.1, 0.9),
    ),
    3: (
        (-4.4, 11.9, 5.9, -0.4, 4.5, 1.7, 1.1, -0.8, 0, -0.3), (-4.5, 11.1, 3.6, -0.5, 2.5, 1.3, 2.1, -1.0, 0.8, 0.4),
        (-5.0, 11.7, 2.0, -0.5, 1.0, 0.7, 3.4, -1.3, 1.5, 1.2), (-5.7, 13.6, 0.7, -0.4, -0.5, 0.3, 4.8, -1.7, 2.5, 2.3),
        (-5.5, 15.6, 0.5, -0.4, -0.4, 0.1, 5.8, 0.5, 5.3, 5.3), (-6.0, 16.9, 0.4, -0.5, -0.4, -0.1, 6.5, 1.9, 6.0, 6.2),
        (-6.8, 21.2, 0.4, -0.7, -0.5, -0.5, 7.1, 3.0, 6.0, 5.8), (-6.6, 22.3, 0.2, -0.2, -0.3, 0.2, 7.9, 3.2, 4.9, 5.5),
        (-6.3, 25.2, 0.3, 0, 0, 0.4, 8.3, 3.0, 4.1, 4.3), (-6.4, 23.6, 0.2, 0.2, 0, 0.4, 6.7, 1.7, 2.6, 3.0),
        (-6.6, 21.9, 0.2, 0.4, 0, 0.6, 4.9, 0.5, 1.2, 1.8), (-7.2, 23.5, 0.4, 0.8, 0, 0.4, 3.3, -0.2, 0, 0.6),
        (-8.0, 25.5, 0.7, 1.0, -0.1, 0.3, 1.7, -0.7, -0.8, -0.7), (-9.8, 32.9, 0.8, 1.3, -0.2, 0.1, 2.5, -1.2, -1.2, -1.6),
        (-12.0, 39.6, 1.5, 2.0, -0.5, 0, 3.6, -1.8, -1.0, -2.7), (-9.3, 28.4, 3.5, 2.2, 0.4, 1.2, 2.1, -1.4, -0.9, -1.6),
        (-7.8, 22.2, 6.0, 2.5, 0.9, 2.6, 1.1, -1.1, -0.7, -1.0), (-7.9, 18.7, 9.2, 3.4, 1.8, 4.7, 0.3, -0.9, -0.6, 0.3),
        (-8.3, 21.1, 11.8, 1.9, 3.4, 6.1, 0.4, -0.4, -0.6, 0.4), (-8.6, 23.4, 14.5, 0.4, 5.1, 7.4, 0.4, 0.1, -0.6, 0.5),
        (-7.9, 20.6, 13.6, 0.9, 4.9, 5.4, 0.2, 0, -0.4, 0.6), (-8.2, 22.9, 14.5, 2.5, 5.1, 3.3, 0.2, 0.1, -0.4, 0.5),
        (-6.9, 21.0, 12.8, -0.5, 8.6, 5.0, 0.3, -0.6, -0.5, -0.1), (-5.7, 16.4, 9.1, -0.5, 7.0, 3.6, 0.7, -0.4, -0.2, -0.1),
    ),
    4: (
        (-13.0, 37.0, -0.2, 0.8, 0.9, 0.3, 3.5, 0.5, 12.0, 7.4), (-16.7, 42.2, 0.1, 0.1, 1.5, -0.3, -0.3, 0.4, 14.2, 6.1),
        (-14.1, 35.6, -0.6, -0.2, 2.1, -0.4, 7.1, 2.1, 12.6, 5.7), (-13.3, 33.0, -0.2, -0.6, 0.9, -0.4, 9.2, 3.1, 10.1, 5.2),
        (-13.2, 30.9, 0, -0.2, 0.7, -0.2, 9.2, 3.7, 8.4, 4.2), (-9.7, 25.2, 0.2, 0.5, 0.2, 0.2, 7.7, 2.5, 6.4, 2.9),
        (-6.8, 17.6, 0.3, 0.7, 0.6, 0.6, 4.4, 1.4, 3.7, 1.4), (-5.9, 15.7, 0.5, 0.9, 0.7, 1.3, 0.4, 0, 0.4, 0),
        (-7.0, 18.1, 0.2, 1.3, 2.5, 2.2, 0.8, -0.2, 0.9, 0.5), (-9.1, 21.1, 3.5, 1.9, 6.0, 6.2, 0.4, -0.3, 0.4, 0.2),
        (-13.4, 30.1, 7.4, 2.3, 10.6, 10.7, -0.1, -0.4, 0.8, -0.3), (-14.2, 38.2, 7.0, 3.1, 11.8, 8.7, 0.1, -0.6, -0.3, 0),
        (-13.5, 34.5, 5.1, 4.3, 8.6, 5.7, -0.1, -0.1, 0, 0.1), (-12.2, 32.5, 4.3, 2.7, 7.0, 4.1, 1.1, -0.2, -0.3, 0),
        (-10.0, 28.9, 3.2, 1.5, 5.4, 2.8, 2.5, -0.5, -0.6, 0.3), (-8.8, 29.8, 2.6, 0.3, 4.2, 1.9, 4.3, -1.1, -0.2, 0.2),
        (-8.7, 33.5, 0.9, -0.1, 2.6, 1.1, 5.6, -2.6, -0.2, 0.2), (-7.6, 26.7, 0.8, -0.2, 1.6, 1.0, 2.5, -1.9, 1.1, -0.1),
        (-7.8, 26.3, 0.4, 0.1, 1.2, 1.0, 2.6, -1.2, 4.0, 2.4), (-9.4, 28.8, 0, 0.4, 1.0, 0.8, 2.7, -0.3, 7.5, 4.8),
    ),
}


def spin(pose, bone, axis, degrees):
    """A turn about `axis` of the bone's parent frame, put in front of its own rotation."""
    local = R.rot_of(pose[bone])
    new = R.m3mul(R.from_axis_angle(axis, math.radians(degrees)), local)
    pose[bone][3:6] = [round(v) for v in mmd.matrix_euler(new, pose[bone][3:6])]


def correct(pose, row):
    """Apply one table row to a pose (in place)."""
    pitch, lift = row[0], row[1]
    pose[HEAD][3] += round(pitch * 4096 / 360)
    pose[HEAD][7] -= round(lift)
    for side, d in (('L', row[2:6]), ('R', row[6:10])):
        leg = LEGS[side]
        for bone, axis, degrees in ((leg[0], 0, d[0]), (leg[0], 2, d[1]), (leg[1], 0, d[2]), (leg[2], 0, d[3])):
            if degrees:
                spin(pose, bone, AXES[axis], degrees)


def _parse(data):
    mmd.exe().skeleton[SPECIES] = _rig()
    mmd.exe().bone_count[SPECIES] = NB
    model = mmd.MMD.parse(data, NB)
    model.type = SPECIES
    return model


def _rig():
    path = ROOT / 'content/species/268-skullmammothmon.json'
    return [tuple(b) for b in json.loads(path.read_text())['model']['skeleton']]


def build(data, table=None):
    """The model with the corrected clips: (bytes, report)."""
    table = table or TABLE
    old = _parse(data)
    new = copy.deepcopy(old)
    for slot in SLOTS:
        rows = table[TABLE_OF[slot]]
        frames, loop, _ = animsheet.slot_frames(old, NB, slot)
        n = len(frames) - 1
        assert loop == 0 and len(rows) == n, (slot, n, len(rows))
        poses = copy.deepcopy(frames)
        for t in range(n):
            correct(poses[t], rows[t])
        for bone, chan in CHANNELS:
            poses[n][bone][chan] = poses[0][bone][chan]
        index = new.anims.table[slot]
        new.anims.anims[index] = replace_channels(old.anims.anims[index], poses, loop, NB, CHANNELS, tolerance=TOLERANCE)
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = _parse(result)
    assert old.tmd.build() == actual.tmd.build()
    return result, dict(changed=changed_programs(old, actual), storage=motionstorage.require(result, NB))


# ---------------------------------------------------------------------------------------------------------------- fitting
_CTX = {}


def _seg_tri(p0, p1, tri):
    e1, e2 = tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]
    d = p1 - p0
    h = np.cross(d, e2)
    a = (e1 * h).sum(1)
    ok = np.abs(a) > 1e-9
    f = 1 / np.where(ok, a, 1)
    s = p0 - tri[:, 0]
    u = f * (s * h).sum(1)
    q = np.cross(s, e1)
    v = f * (q * d).sum(1)
    t = f * (e2 * q).sum(1)
    return ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t >= 0) & (t <= 1)


def crossings(a, b):
    """Number of crossing triangle pairs between a (n, 3, 3) and b (m, 3, 3): the same count as meshclash.crossing, faster."""
    if not len(a) or not len(b):
        return 0
    near = ((a.min(1)[:, None] <= b.max(1)[None]) & (a.max(1)[:, None] >= b.min(1)[None])).all(2)
    i, j = np.nonzero(near)
    if not len(i):
        return 0
    x, y = a[i], b[j]
    hit = np.zeros(len(i), bool)
    for k in range(3):
        k2 = (k + 1) % 3
        hit |= _seg_tri(x[:, k], x[:, k2], y)
        hit |= _seg_tri(y[:, k], y[:, k2], x)
    return int(hit.sum())


class Scene:
    """One clip of the model, posed per tick, with the counts the corrected clip must not exceed."""

    def __init__(self, model, slot):
        from tools.models.field_animations import meshclash
        self.clash = meshclash.Clash(model, _rig())
        self.frames = animsheet.slot_frames(model, NB, slot)[0][:-1]
        self.n = len(self.frames)
        self.slack = 1.5         # while fitting, the floor limits are this much tighter than the stored clips are held to
        self.base = [self.measure(p) for p in self.frames]

    def tris(self, world, bones):
        return self.clash.tris(world, list(bones))

    def measure(self, pose):
        """Per leg: crossings with the head, with the rest of the body and the other leg, and the lowest vertex of the foot;
        and the head's crossings with the body."""
        w = self.clash.world(pose)
        head, body = self.tris(w, HEAD_BONES), self.tris(w, BODY_BONES)
        out = dict(hb=crossings(head, body))
        for side, leg in LEGS.items():
            other = LEGS['R' if side == 'L' else 'L']
            t = self.tris(w, leg)
            out[side] = dict(head=crossings(t, head), rest=crossings(t, self.tris(w, BODY_BONES + other)),
                             low=float(self.tris(w, leg[2:]).reshape(-1, 3)[:, 1].max()))
        return out

    def leg_status(self, pose, t, side, head=None):
        """Why the leg is not acceptable on this tick: 'head' (crosses it), 'body' (crosses the body or the other leg more
        than before), 'sunk' or 'raised' (the foot left the floor level of the original), or '' when it is fine."""
        w = self.clash.world(pose)
        leg = LEGS[side]
        other = LEGS['R' if side == 'L' else 'L']
        mine = self.tris(w, leg)
        head = self.tris(w, HEAD_BONES) if head is None else head
        if crossings(mine, head):
            return 'head'
        base = self.base[t][side]
        if crossings(mine, self.tris(w, BODY_BONES + other)) > base['rest']:
            return 'body'
        low = float(self.tris(w, leg[2:]).reshape(-1, 3)[:, 1].max())
        if low > max(base['low'], 1.5) + 0.01 - self.slack * .5:
            return 'sunk'
        if base['low'] > -FLOOR and low < base['low'] - 4.0 + self.slack:
            return 'raised'
        return ''

    def leg_ok(self, pose, t, side, head=None):
        return not self.leg_status(pose, t, side, head)

    def head_ok(self, pose, t):
        w = self.clash.world(pose)
        return crossings(self.tris(w, HEAD_BONES), self.tris(w, BODY_BONES)) <= self.base[t]['hb']

    def row_pose(self, t, row):
        q = copy.deepcopy(self.frames[t])
        correct(q, row)
        return q

    def failures(self, t, row):
        """The sides whose leg is not clear."""
        q = self.row_pose(t, row)
        w = self.clash.world(q)
        head = self.tris(w, HEAD_BONES)
        return [s for s in 'LR' if not self.leg_ok(q, t, s, head)]


W_LEG = 1 / 8.
HEAD_STEPS = [(p, l) for p in range(0, -31, -2) for l in range(0, 65, 8)]


def _head_cost(p, l):
    return (p / SCALE[0]) ** 2 + (l / SCALE[1]) ** 2


def _legs(sc, t, row, rng, limit=1e9):
    """Fill the leg columns of `row` (head set) with the smallest turns found that clear both legs: the cost, or None."""
    total = 0.
    q0 = sc.row_pose(t, row)
    for side, off in (('L', 2), ('R', 6)):
        if sc.leg_ok(q0, t, side):
            continue
        found = None
        for i in range(220):
            d = np.round(rng.normal(size=4) * rng.choice([3, 6, 10, 16]), 1)
            cost = float(((d * W_LEG) ** 2).sum())
            if (found is not None and cost >= found[0]) or total + cost >= limit:
                continue
            trial = copy.deepcopy(row)
            trial[off:off + 4] = [float(x) for x in d]
            if sc.leg_ok(sc.row_pose(t, trial), t, side):
                found = (cost, d)
        if found is None:
            return None
        # pull each turn toward zero while the leg stays clear
        d = found[1].copy()
        for _ in range(4):
            for k in range(4):
                for f in (0.0, 0.5, 0.75):
                    e = d.copy()
                    e[k] = round(e[k] * f, 1)
                    trial = copy.deepcopy(row)
                    trial[off:off + 4] = [float(x) for x in e]
                    if sc.leg_ok(sc.row_pose(t, trial), t, side):
                        d = e
                        break
        row[off:off + 4] = [float(x) for x in d]
        total += float(((d * W_LEG) ** 2).sum())
    return total


def _tick(args):
    slot, t = args
    sc = _CTX[slot]
    rng = np.random.default_rng(1000 * slot + t)
    best = None
    for pitch, lift in sorted(HEAD_STEPS, key=lambda s: _head_cost(*s)):
        hc = _head_cost(pitch, lift)
        if best is not None and hc >= best[0]:
            break
        row = [float(pitch), float(lift)] + [0.] * 8
        total = _legs(sc, t, row, rng, (best[0] if best else 1e9) - hc)
        if total is not None and (best is None or hc + total < best[0]):
            best = (hc + total, row)
    return slot, t, best


def _init(path, slots):
    data = Path(path).read_bytes()
    model = _parse(data)
    for slot in slots:
        _CTX[slot] = Scene(model, slot)


SCALE = np.array([7., 25.] + [8.] * 8)     # what counts as one unit of each column in the cost
SMOOTH = 3.0                                  # weight of the change from one tick to the next against the size of the turn


def _energy(rows, t):
    """The cost of tick t: its own size and the change to its two neighbours (the loop is closed)."""
    n = len(rows)
    x = rows[t] / SCALE
    return float((x ** 2).sum() + SMOOTH * (((rows[t] - rows[t - 1]) / SCALE) ** 2).sum()
                 + SMOOTH * (((rows[t] - rows[(t + 1) % n]) / SCALE) ** 2).sum())


def refine(sc, raw, sweeps=80, seed=5):
    """From the per-tick optimum, smooth the loop without ever leaving the clear ticks: every move that is kept clears
    both legs and lowers the cost (size of the turns plus the change from tick to tick)."""
    rng = np.random.default_rng(seed)
    rows = np.round(np.array(raw, float), 1)
    n = len(rows)
    assert not any(sc.failures(t, list(rows[t])) for t in range(n)), 'the per-tick optimum is not clear'
    for sweep in range(sweeps):
        moved = 0
        for t in rng.permutation(n):
            before = _energy(rows, t) + _energy(rows, (t + 1) % n) + _energy(rows, t - 1)
            mean = (rows[t - 1] + rows[(t + 1) % n]) / 2
            options = [mean, (rows[t] + mean) / 2, rows[t] * .85, rows[t] * .95]
            for _ in range(6):
                options.append(rows[t] + rng.normal(size=10) * SCALE * .08 * (rng.random(10) < .4))
            kept = None
            for cand in options:
                cand = np.round(cand, 1)
                if np.array_equal(cand, rows[t]):
                    continue
                old, rows[t] = rows[t].copy(), cand
                gain = before - (_energy(rows, t) + _energy(rows, (t + 1) % n) + _energy(rows, t - 1))
                rows[t] = old
                if gain > 1e-6 and (kept is None or gain > kept[0]) and not sc.failures(t, list(cand)):
                    kept = (gain, cand)
            if kept:
                rows[t] = kept[1]
                moved += 1
        if not moved:
            break
    return [tuple(float(x) for x in r) for r in rows]


def resolve(sc, rows, count=3, seed=9):
    """A tick can be stuck in a pose the neighbours do not share (a head that drops for one tick): restart the worst few
    with the neighbours' head (and a few near it), solve the legs for it, and keep it if the loop's cost goes down."""
    rng = np.random.default_rng(seed)
    rows = np.array(rows, float)
    n = len(rows)
    for t in sorted(range(n), key=lambda t: -_energy(rows, t))[:count]:
        mean = (rows[t - 1] + rows[(t + 1) % n]) / 2
        near = lambda r: _energy(r, t) + _energy(r, (t + 1) % n) + _energy(r, t - 1)
        best = (near(rows), rows[t].copy())
        for dp, dl in ((0, 0), (-2, 5), (2, -5), (-4, 10), (0, 10), (-2, 0), (-6, 12), (3, 6)):
            row = [round(float(mean[0]) + dp, 1), round(float(mean[1]) + dl, 1)] + [0.] * 8
            if _legs(sc, t, row, rng) is None:
                continue
            old, rows[t] = rows[t].copy(), np.array(row)
            cost = near(rows)
            rows[t] = old
            if cost < best[0]:
                best = (cost, np.array(row))
        rows[t] = best[1]
    return [tuple(float(x) for x in r) for r in rows]


def stored_failures(data, table, scenes):
    """The (slot, tick, side) of every leg that crosses the head in the clips as they are stored (the keys of the stream
    only follow the table within `TOLERANCE`, so the table's own clear ticks can graze)."""
    result, _ = build(data, table)
    model = _parse(result)
    bad = []
    for slot in SLOTS:
        sc = scenes[slot]
        sc.slack = 0.
        frames = animsheet.slot_frames(model, NB, slot)[0][:-1]
        for t, pose in enumerate(frames):
            bad += [(slot, t, side, why) for side in 'LR' for why in [sc.leg_status(pose, t, side)] if why]
    return bad


def harden(data, table, scenes, rounds=30):
    """Raise the head a little around every tick the stored clip still grazes, until none does."""
    table = {k: [list(r) for r in rows] for k, rows in table.items()}
    tries = {}
    for _ in range(rounds):
        bad = stored_failures(data, table, scenes)
        if not bad:
            return {k: [tuple(round(x, 1) for x in r) for r in rows] for k, rows in table.items()}
        for slot, t, side, why in bad:
            rows = table[TABLE_OF[slot]]
            if why != 'head':        # the stored keys grazed the body or the floor: that leg's turns change a little
                off = 2 if side == 'L' else 6
                scale = (1.25, .7, 1.4, .4)[tries.get((slot, t, side), 0) % 4]
                tries[(slot, t, side)] = tries.get((slot, t, side), 0) + 1
                for k in range(off, off + 4):
                    rows[t][k] *= scale
                continue
            for k, w in ((-1, .5), (0, 1.), (1, .5)):
                row = rows[(t + k) % len(rows)]
                row[0] -= .6 * w
                row[1] += 1.5 * w
    raise AssertionError(('the stored clips still graze the head', bad))


def fit(path, slots=(2, 3, 4), jobs=14):
    """Offline: the table that clears the front legs of the model at `path` (several minutes; needs numpy)."""
    from multiprocessing import Pool
    table = {}
    with Pool(jobs, initializer=_init, initargs=(path, slots + (36,))) as pool:
        _init(path, slots + (36,))
        for slot in slots:
            n = _CTX[slot].n
            raw = [None] * n
            for _, t, best in pool.imap_unordered(_tick, [(slot, t) for t in range(n)]):
                assert best is not None, ('no way to clear the legs', slot, t)
                raw[t] = best[1]
            rows = refine(_CTX[slot], raw)
            for _ in range(2):
                rows = refine(_CTX[slot], resolve(_CTX[slot], rows))
            table[slot] = rows
            print(slot, 'fitted', flush=True)
    return harden(Path(path).read_bytes(), table, _CTX)


def report(data):
    """Per tick of every corrected clip: the crossings of the front legs with the head, and how the table moved the joints."""
    model = _parse(data)
    out = {}
    for slot in SLOTS:
        sc = Scene(model, slot)
        out[slot] = [(b['L']['head'], b['R']['head']) for b in sc.base]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', required=True)
    ap.add_argument('--out')
    ap.add_argument('--fit', action='store_true', help='print a new TABLE instead of building')
    args = ap.parse_args()
    data = Path(args.source).read_bytes()
    assert hashlib.sha256(data).hexdigest() == SOURCE, 'another source model'
    if args.fit:
        table = fit(args.source)
        print('TABLE = ' + json.dumps({str(k): v for k, v in table.items()}))
        return
    result, rep = build(data)
    Path(args.out).write_bytes(result)
    print(hashlib.sha256(result).hexdigest(), json.dumps(rep, default=str)[:400])


if __name__ == '__main__':
    main()
