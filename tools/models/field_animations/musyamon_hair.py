"""Musyamon's hair kept off its cape and its back: the step after `musyamon_posture`, on that step's output (species 325).

Offline only (player builds replay the pinned delta): `tools/models/edit.py get 325` on the commit that has the posture step, then
`python3 -m tools.models.field_animations.musyamon_hair --source THAT.MMD --out AFTER.MMD` and `edit.py put 325 AFTER.MMD`.

The hair is bone 24, the dark mane behind the head (a child of the head, bone 23). Every clip leaves it rigid on the head (no channel of
its own), while the cape (bones 25, 26, 27 and 17) hangs from the chest and the chest moves against the head: the mane's triangles cross
the two spikes that rise beside the head (26 and 27) and the cape's back (25), the chest's back (1) and the shoulder plates (16, 18),
about 150 triangle pairs in the idle, more in the walks.

Per tick, the least move of bone 24 (a few units and degrees about its own root: up and a little forward on the head and tilted back)
that leaves the fewest crossings; the series is then filtered over the closed loop (a triangle filter, so it is slow and smooth) and
each tick settled again around the filtered value. The hair's own channels are the only ones this step touches. The mane stays on
the head: its crossings with the head (the root) are kept. The build refuses another source, a change outside bone 24's channels,
the changed programs outside the slots below (and their aliases) and the storage budget.
"""
import argparse
import copy
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet  # noqa: E402
import mmd  # noqa: E402
import motionsecondary  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models.field_animations import meshclash  # noqa: E402
from tools.models.field_animations.articulation import replace_channels  # noqa: E402

R = motionsecondary.R
SPECIES, NB = 325, 28
SOURCE = '77052fcc38067115994fcf49120fda39460f652028d86f6fd6696319d45cc12b'             # the posture step's output
SLOTS = (0, 2, 3, 4)                           # idle, walk, tired walk, run (slot 33 shares the idle's program)
HAIR, HEAD = 24, 23
CAPE = (17, 25, 26, 27)
BACK = (1, 16, 18)                             # chest back, shoulder plates
ARMS = (13, 14, 15, 19, 20, 21, 22)
CHANNELS = {(HAIR, c) for c in range(3, 9)}
WEIGHT = dict(cape=3, back=2, arms=2)
LIMIT_POS = np.array([30., 30., 20.])          # units: x, y, z of the head's frame
LIMIT_ROT = np.array([20., 12., 12.])          # degrees about x, y, z
ATTACH = 12                                    # crossings with the head kept (the hair stays rooted in it): the import has 20


def parse(data):
    m = mmd.MMD.parse(data, NB)
    m.type = SPECIES
    return m


def apply(pose, v):
    """The mane moved by v = (dx, dy, dz, rx, ry, rz): units and degrees in the head's frame, the rotation in front of the bone's own."""
    q = copy.deepcopy(pose)
    local = R.rot_of(q[HAIR])
    turn = R.m3mul(R.m3mul(R.from_axis_angle([1, 0, 0], math.radians(v[3])), R.from_axis_angle([0, 1, 0], math.radians(v[4]))),
                   R.from_axis_angle([0, 0, 1], math.radians(v[5])))
    q[HAIR][3:6] = [round(x) for x in mmd.matrix_euler(R.m3mul(turn, local), q[HAIR][3:6])]
    for i in range(3):
        q[HAIR][6 + i] = round(q[HAIR][6 + i] + v[i])
    return q


def pairs(a, b):
    hit = np.zeros((len(a), len(b)), bool)
    for k in range(3):
        k2 = (k + 1) % 3
        hit |= meshclash._crossings(a[:, k], a[:, k2], b)
        hit |= meshclash._crossings(b[:, k], b[:, k2], a).T
    return int(hit.sum())


class Tick:
    """One pose of the source and the others' triangles in it (the mane's moves do not change them)."""

    def __init__(self, clash, pose):
        self.clash, self.pose = clash, pose
        w = clash.world(pose)
        self.cape, self.back, self.arms, self.head = (clash.tris(w, list(g)) for g in (CAPE, BACK, ARMS, (HEAD,)))

    def count(self, v):
        q = apply(self.pose, v)
        hair = self.clash.tris(self.clash.world(q), [HAIR])
        return dict(cape=pairs(hair, self.cape), back=pairs(hair, self.back), arms=pairs(hair, self.arms), head=pairs(hair, self.head))

    def cost(self, v, anchor=None, pull=0.):
        c = self.count(v)
        total = sum(WEIGHT[k] * c[k] for k in WEIGHT) + 4 * max(0, ATTACH - c['head'])
        total += 0.12 * np.linalg.norm(v[:3]) + 0.15 * np.linalg.norm(v[3:])
        if anchor is not None:
            total += pull * (np.linalg.norm(v[:3] - anchor[:3]) + np.linalg.norm(v[3:] - anchor[3:]))
        return total

    def settle(self, v0, steps, anchor=None, pull=0.):
        v = np.array(v0, float)
        best = self.cost(v, anchor, pull)
        for sp, sr in steps:
            improved = True
            while improved:
                improved = False
                for i in range(6):
                    for sign in (-1, 1):
                        w = v.copy()
                        w[i] += sign * (sp if i < 3 else sr)
                        lim = LIMIT_POS[i] if i < 3 else LIMIT_ROT[i - 3]
                        if abs(w[i]) > lim:
                            continue
                        c = self.cost(w, anchor, pull)
                        if c < best - 1e-9:
                            best, v, improved = c, w, True
        return v


def smooth(series):
    """A triangle filter (1 2 3 2 1) over the closed loop, per channel."""
    n = len(series)
    k = (1, 2, 3, 2, 1)
    return np.array([sum(k[j + 2] * series[(i + j) % n] for j in range(-2, 3)) / 9. for i in range(n)])


def solve(clash, frames):
    """Per tick (not the last), the mane's move: a first pass round the loop (each tick starting from the one before), a filter, and
    each tick settled again near the filtered value."""
    ticks = [Tick(clash, f) for f in frames[:-1]]
    v = np.zeros(6)
    first = []
    for _ in range(2):                               # the second lap starts where the first ended: the loop closes
        first = []
        for t in ticks:
            v = t.settle(v, ((8, 4), (4, 2), (2, 1)))
            first.append(v.copy())
    target = smooth(np.array(first))
    final = [t.settle(s, ((2, 1),), anchor=s, pull=0.6) for t, s in zip(ticks, target)]
    return np.array(final), ticks


def build_slot(clash, frames):
    moves, ticks = solve(clash, frames)
    new = []
    for f, v in zip(frames[:-1], moves):
        new.append(apply(f, v))
    closed = frames[0][HAIR] == frames[-1][HAIR]
    new.append(copy.deepcopy(new[0]) if closed else apply(frames[-1], moves[0]))
    return new, moves


def build(data):
    if SOURCE:
        assert hashlib.sha256(data).hexdigest() == SOURCE
    model = parse(data)
    clash = meshclash.Clash(model, mmd.exe().skeleton[SPECIES])
    result = copy.deepcopy(model)
    report = {}
    for slot in SLOTS:
        idx = model.anims.table[slot]
        frames, loop, events = animsheet.slot_frames(model, NB, slot)
        assert loop == 0
        frames = [[list(b) for b in f] for f in frames]
        new, moves = build_slot(clash, frames)
        for f_new, f_old in zip(new, frames):
            for b in range(NB):
                for c in range(9):
                    if (b, c) not in CHANNELS and b != 0:
                        assert f_new[b][c] == f_old[b][c], (slot, b, c)
        result.anims.anims[idx] = replace_channels(model.anims.anims[idx], new, loop, NB, CHANNELS)
        report[slot] = dict(min=[round(float(x), 1) for x in moves.min(0)], max=[round(float(x), 1) for x in moves.max(0)])
    out = result.build()
    effective = parse(out)
    assert effective.tmd.build() == model.tmd.build()
    aliases = sorted(s for s in range(len(model.anims.table)) if model.anims.table[s] in {model.anims.table[t] for t in SLOTS})
    assert changed_programs(model, effective) == aliases
    storage = motionstorage.audit(out, NB)
    assert storage['fits'], storage
    return out, dict(output_sha256=hashlib.sha256(out).hexdigest(), moves=report, storage=storage['resident_bytes'])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    data, report = build(a.source.read_bytes())
    a.out.write_bytes(data)
    print(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
