"""Hawkmon's own field clips with the feet corrected: the right foot turned forward and no foot under the floor.

Offline authoring only: player builds replay the pinned plain delta. Run with --source and --out, then store the
result with tools/models/edit.py put 184.

The import's right foot was bound turned about 58 degrees outward, so every clip stood and walked on a sideways
foot, and its walk and run (12-tick cycles at 25 and 56 units per tick, the body hopping about 40 and 53 units twice a
cycle) pushed the feet up to 41 units into the floor; the condition walk up to 60. The field idle raised the body
32 units over 81 ticks while the feet stayed down, so it rose onto its tiptoes.

The clips themselves are kept: every body, head, wing, tail and leg channel, the root speed per tick and the hop.
The walk is played over 16 ticks instead of 12 (every channel eased evenly, the hop as high, the stride per cycle
longer), since at 12 the hopping read hurried. The run keeps its 12 ticks and, since the import ran on the walk's
own motion only faster, is made bolder (run_style): the body pitched 15 degrees forward with the head carried
ahead of it, the wings swept back and beating up with each hop, the thighs swinging 1.35 times as far and the top
of each hop raised 22 units, so the body travels about 75 units and both feet leave the floor at every hop. Then
the feet are corrected, per tick, in every clip:

- the right foot turns 58 degrees inward about its own vertical axis, so it points forward as the left one does;
- a foot that would reach under the floor is raised along the world vertical by exactly that depth, inside its
  leg (its own offset from the thigh), so it stands on the floor and the body keeps its bounce;
- the field idle keeps a quarter of its rise, so the feet stay on the floor without standing on their tips.

This applies to the idles (0, 1), walk (2), condition walk (3), run (4), the battle idle (0x21) and the battle
movement that shares the walk and run. The mesh and every other program stay exact.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]

import animsheet  # noqa: E402
import mmd  # noqa: E402
import motioncyclelayer  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
import math  # noqa: E402
from motiontailspace import interpolate_pose  # noqa: E402
from tools.models.field_animations.quadruped import dot, mul, mv, rot, tr  # noqa: E402

SOURCE = 'c49592c572a53bf4f1953ae4aa329665b20d9ed624824c16a9d23e369ceb3ead'
SPECIES = 184
NB = 21
PELVIS, HEAD = 1, 2
WINGS = {-1: (4, 5, 6), 1: (10, 11, 12)}
LEGS = ((16, 17), (18, 19))      # (thigh, foot), left then right
RIGHT_FOOT = 19
TURN = 58                        # degrees the right foot is turned back inward about its own vertical
SPLAY = 6                        # degrees each flat foot turns outward
REACH = (1.0, 0.6, 0.25)         # how a flat stance foot carries into the ticks next to it
STEP = 0.3                       # the most of the way to flat a foot turns in one tick
IDLE_RISE = 0.25                 # the share of the field idle's rise that is kept
SLOTS = (0, 1, 2, 3, 4, 0x21, 0x23, 0x24)
CYCLE = {2: 16}                  # the walk cycle, 12 ticks in the import, played a little slower


class Hawk:
    def __init__(self, model):
        self.m = model
        self.sk = mmd.exe().skeleton[SPECIES]
        self.verts = {b: [v[:3] for v in model.tmd.obj_verts(o)] for b, (o, _) in enumerate(self.sk) if o >= 0}
        self.reach = {}

    def world(self, pose):
        p = [list(v) for v in pose]
        p[0] = [4096, 4096, 4096] + p[0][3:6] + [0, 0, 0]
        return mmd.bone_matrices(self.m, p)

    def depth(self, pose, b):
        """How far the mesh of bone b reaches under the floor (y grows downwards; 0 is the floor)."""
        W = self.world(pose)
        return W[b][1][3] + max(dot(W[b][1][:3], v) for v in self.verts[b])

    def floor(self, pose):
        return max(self.depth(pose, b) for b in self.verts)


def set_world_rotation(hawk, pose, b, world, hist):
    W = hawk.world(pose)
    parent = [r[:3] for r in W[hawk.sk[b][1]][:3]]
    angle = mmd.matrix_euler(mul(tr(parent), world), hist.get(b))
    hist[b] = angle
    pose[b][3:6] = [round(x) for x in angle]


def toward(a, b, s):
    """The rotation s of the way from a to b (about one axis)."""
    r = mul(b, tr(a))
    c = max(-1.0, min(1.0, (r[0][0] + r[1][1] + r[2][2] - 1) / 2))
    angle = math.acos(c)
    if angle < 1e-6:
        return [row[:] for row in a]
    k = [r[2][1] - r[1][2], r[0][2] - r[2][0], r[1][0] - r[0][1]]
    n = math.sqrt(sum(x * x for x in k)) or 1.0
    k = [x / n for x in k]
    t = angle * s
    K = [[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]]
    K2 = mul(K, K)
    R = [[(i == j) + math.sin(t) * K[i][j] + (1 - math.cos(t)) * K2[i][j] for j in range(3)] for i in range(3)]
    return mul(R, a)


def flat(side):
    """A foot standing flat, pointing forward with the splay outward (the foot meshes point along -z, soles level)."""
    R = rot([0, SPLAY, 0])
    if (mv(R, [0, 0, -1])[0] > 0) != (side > 0):
        R = rot([0, -SPLAY, 0])
    return R


def spread(share, t):
    """A foot in the air at tick t turns part of the way toward the flatness of the nearest stance ticks."""
    n = len(share)
    near = [share[(t + d) % n] * w for k, w in enumerate(REACH) if k for d in (k, -k) if share[(t + d) % n] is not None]
    return max([0.0] + near)


def stretch(frames, ticks):
    """The cycle played over `ticks` ticks at the same speed per tick: every channel eased evenly, so the hop keeps its
    height and the stride per cycle grows."""
    n = len(frames) - 1
    speed = frames[-1][0][8] / n
    out = []
    for t in range(ticks + 1):
        at = t * n / ticks
        left = min(int(at), n - 1)
        p = [list(v) for v in interpolate_pose(frames[left], frames[left + 1], round((at - left) * 4096))]
        p[0][6:9] = [0, 0, speed * t]
        out.append(p)
    return out


# the run: the walk's own hop made bolder (the import ran on the same motion, only faster)
LEAN = 15            # degrees the body pitches forward
HEAD_BACK = 3        # of which the head takes back (it still carries forward)
HOP = 22             # units the top of each hop is raised
STRIDE = 1.35        # the legs' swing about their mean
WING_SWEEP = 14      # degrees the wings sweep back
WING_BEAT = (22, 16)  # degrees the wings are raised, and their beat with each hop


def run_style(hawk, frames):
    n = len(frames) - 1
    heights = [p[PELVIS][7] for p in frames[:n]]
    top, low = min(heights), max(heights)
    mean = {b: [sum(p[b][c] for p in frames[:n]) / n for c in (3, 4, 5)] for b, _ in LEGS}
    out, hist = [], {}
    for t, pose in enumerate(frames):
        p = [list(v) for v in pose]
        up = (low - p[PELVIS][7]) / (low - top)          # 0 at the bottom of a hop, 1 at its top
        p[PELVIS][7] -= HOP * up * up
        for thigh, _ in LEGS:
            for i, c in enumerate((3, 4, 5)):
                p[thigh][c] = mean[thigh][i] + STRIDE * (p[thigh][c] - mean[thigh][i])
        W = hawk.world(p)
        set_world_rotation(hawk, p, PELVIS, mul(rot([LEAN, 0, 0]), [r[:3] for r in W[PELVIS][:3]]), hist)
        W = hawk.world(p)
        set_world_rotation(hawk, p, HEAD, mul(rot([-HEAD_BACK, 0, 0]), [r[:3] for r in W[HEAD][:3]]), hist)
        beat = math.cos(4 * math.pi * t / n)              # up at the top of each hop, down as it lands
        for side, bones in WINGS.items():
            W = hawk.world(p)
            b = bones[0]
            k = -side
            set_world_rotation(hawk, p, b, mul(rot([0, k * -WING_SWEEP, k * (WING_BEAT[0] + WING_BEAT[1] * beat)]),
                                               [r[:3] for r in W[b][:3]]), hist)
        out.append(p)
    return out


def fix_feet(hawk, frames, rise=1.0):
    """Per tick: the right foot turned forward; a foot touching the floor laid as flat as it can be while its sole
    still reaches the floor (the ticks next to a stance turning part of the way, so the foot never snaps), and any
    foot under the floor raised inside its leg."""
    rest = frames[0][PELVIS][7]
    posed, hist = [], {}
    for pose in frames:
        p = [list(v) for v in pose]
        p[PELVIS][7] = rest + rise * (p[PELVIS][7] - rest)
        W = hawk.world(p)
        set_world_rotation(hawk, p, RIGHT_FOOT, mul([r[:3] for r in W[RIGHT_FOOT][:3]], rot([0, TURN, 0])), hist)
        posed.append(p)
    n = len(posed) - 1                   # the last tick repeats the first
    reach = {}
    for side, (thigh, foot) in zip((-1, 1), LEGS):
        F = flat(side)
        share = []
        for p in posed[:n]:
            W = hawk.world(p)
            R0, y = [r[:3] for r in W[foot][:3]], W[foot][1][3]
            depth = lambda s: y + max(dot(toward(R0, F, s)[1], v) for v in hawk.verts[foot])  # noqa: E731
            if depth(0) < 0:
                share.append(None)       # in the air
            elif depth(1) >= 0:
                share.append(1.0)
            else:
                lo, hi = 0.0, 1.0
                for _ in range(24):
                    mid = (lo + hi) / 2
                    lo, hi = (mid, hi) if depth(mid) >= 0 else (lo, mid)
                share.append(lo)
        flatness = [s if s is not None else spread(share, t) for t, s in enumerate(share)]
        # no foot turns more than STEP of the way in one tick: a foot next to a flatter one comes part of the way
        for _ in range(n):
            flatness = [max(f, flatness[t - 1] - STEP, flatness[(t + 1) % n] - STEP) for t, f in enumerate(flatness)]
        reach[side] = flatness
        hawk.reach[side] = reach[side]
    out, hist, lifts = [], {}, []
    for t, p in enumerate(posed):
        for side, (thigh, foot) in zip((-1, 1), LEGS):
            W = hawk.world(p)
            R0 = [r[:3] for r in W[foot][:3]]
            set_world_rotation(hawk, p, foot, toward(R0, flat(side), reach[side][t % n]), hist)
            lift = max(0.0, hawk.depth(p, foot))
            if lift:
                W = hawk.world(p)
                d = mv(tr([r[:3] for r in W[thigh][:3]]), [0, -lift, 0])
                p[foot][6:9] = [p[foot][6 + i] + d[i] for i in range(3)]
            lifts.append(lift)
        out.append([[round(x) for x in v] for v in p])
    return out, max(lifts)


def build(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('requires the imported Hawkmon these clips were written for')
    mmd.exe().add_type(SPECIES, skeleton)
    source = mmd.MMD.parse(data, NB)
    source.type = SPECIES
    hawk = Hawk(source)
    result = copy.deepcopy(source)
    fixed, checks = {}, []
    for slot in SLOTS:
        old = source.anims.table[slot]
        if old in fixed:
            continue
        frames, loop, events = animsheet.slot_frames(source, NB, slot)
        before = max(hawk.floor(p) for p in frames)
        if slot in CYCLE:
            frames = stretch(frames, CYCLE[slot])
        if slot == 4:
            frames = run_style(hawk, frames)
        frames, lift = fix_feet(hawk, frames, IDLE_RISE if slot == 0 else 1.0)
        after = max(hawk.floor(p) for p in frames)
        feet = max(hawk.depth(p, foot) for p in frames for _, foot in LEGS)
        assert feet < 1 and after < max(before, 0) + 1, (slot, feet, before, after)
        mmd.close_loop(frames, loop)
        fixed[old] = len(result.anims.anims)
        result.anims.anims.append(mmd.encode_anim(frames, NB, loop, events, tol=1, repeats=False))
        checks.append(dict(slot=slot, ticks=len(frames) - 1, deepest_before=round(before, 1),
                           deepest_after=round(after, 1), deepest_foot=round(feet, 1), largest_foot_lift=round(lift, 1)))
    for slot, stream in enumerate(source.anims.table):
        if stream in fixed:
            result.anims.table[slot] = fixed[stream]
    for anim in result.anims.anims:
        anim.tail = b''
    result.anims.anims, result.anims.table = motioncyclelayer.share_identical_streams(result.anims.anims,
                                                                                    result.anims.table)
    output = result.build()
    effective = mmd.MMD.parse(output, NB)
    assert effective.tmd.build() == source.tmd.build()
    changed = changed_programs(source, effective)
    return output, dict(source_sha256=SOURCE, output_sha256=hashlib.sha256(output).hexdigest(), changed_slots=changed,
                        checks=checks, storage=motionstorage.require(output, NB))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/184-hawkmon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
