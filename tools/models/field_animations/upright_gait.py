"""Shared pieces for field gaits authored on a model's own skeleton (magnamon.py).

A clip is written as world rotations per bone and a carrier (body) position per tick, the legs solved onto
footprints; these helpers turn that into frames the game plays: forward kinematics, a two-bone leg solve that keeps
the leg's neutral twist, local angles with a continuous Euler history, and a body lift for whatever still dips
through the floor at the 60 fps thirds. Axes are the game's: x right, y down, forward is -z.
"""
import copy
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import legik  # noqa: E402
import mmd  # noqa: E402
import motionsecondary  # noqa: E402
import retarget as R  # noqa: E402
from motiontailspace import interpolate_pose  # noqa: E402

IDENTITY = [[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]]


def rx(deg):
    """Turn about the sideways axis: positive tips an upright bone forward (a hanging one backward)."""
    return R.from_axis_angle([1, 0, 0], math.radians(deg))


def ry(deg):
    """Turn about the vertical: positive brings the right side (x > 0) forward."""
    return R.from_axis_angle([0, 1, 0], math.radians(deg))


def rz(deg):
    """Turn about the forward axis: positive lowers the right side."""
    return R.from_axis_angle([0, 0, 1], math.radians(deg))


def mul(*ms):
    out = ms[0]
    for m in ms[1:]:
        out = R.m3mul(out, m)
    return out


def apply(m, v):
    return [sum(m[i][j] * v[j] for j in range(3)) for i in range(3)]


def smooth(u):
    u = min(1., max(0., u))
    return u * u * (3 - 2 * u)


def warp(u, skew):
    """A periodic time warp (|skew| < 1): the cycle runs faster in one half and slower in the other, so a wave built on
    it rises and falls at different rates (an ease that is not a sine) and still closes the loop."""
    return u + skew * math.sin(2 * math.pi * u) / (2 * math.pi)


def wave(t, phase=0., skew=0., second=0., second_phase=0.):
    """A loose periodic curve over the cycle (t in 0..1): a cosine peaking at `phase` on a warped clock, plus a little
    of the second harmonic, so the curve has the uneven rise, hold and fall of a native's joint instead of a sine."""
    u = (t - phase) % 1.
    return math.cos(2 * math.pi * warp(u, skew)) + second * math.cos(4 * math.pi * (u - second_phase))


def side_variation(side, amount):
    """A small fixed difference between the two sides (right +, left -): no body steps exactly like its mirror."""
    return 1 + amount * side


def order(skeleton):
    """Bones with every parent before its children."""
    out, seen = [], set()

    def visit(b):
        if b in seen:
            return
        if skeleton[b][1] >= 0:
            visit(skeleton[b][1])
        seen.add(b)
        out.append(b)
    for b in range(len(skeleton)):
        visit(b)
    return out


def neutral_worlds(skeleton, pose):
    p = copy.deepcopy(pose)
    p[0] = [4096] * 3 + [0] * 6
    return dict(enumerate(R.world_rots(skeleton, p)))


def positions(skeleton, offsets, worlds, carrier, at):
    """World positions of the carrier bone (at `at`) and of every bone below it whose parent's rotation is known."""
    pos = {0: [0., 0., 0.], carrier: list(at)}
    for b in order(skeleton):
        p = skeleton[b][1]
        if b in pos or p < 0 or p not in worlds or p not in pos:
            continue
        pos[b] = [pos[p][i] + v for i, v in enumerate(apply(worlds[p], offsets[b]))]
    return pos


def leg(hip, target, l1, l2, pole, reference, rotations):
    """Thigh and shin world rotations reaching `target` from `hip`, the knee toward `pole`; the limb keeps the twist
    it has in `reference` (hip, knee, ankle) with `rotations` (thigh, shin)."""
    knee, got = legik.solve(hip, target, l1, l2, pole)
    return motionsecondary.native_plane_rotations(reference, [hip, knee, got], rotations)


def to_pose(skeleton, reference, worlds, carrier, at, travel, history):
    """A frame: local angles from world rotations (continuous with `history`), the carrier at `at`, the root at
    `travel` along -z; every other translation is the reference frame's."""
    pose = [list(b) for b in reference]
    pose[0] = [4096] * 3 + [0] * 6
    pose[carrier][6:9] = list(at)
    for b in order(skeleton):
        if b == 0:
            continue
        parent = worlds[skeleton[b][1]] if skeleton[b][1] > 0 else IDENTITY
        angles = mmd.matrix_euler(R.m3mul(R.m3t(parent), worlds[b]), history.get(b))
        history[b] = angles
        pose[b][3:6] = list(angles)
    pose[0][8] = -travel
    return pose


def lowest(model, skeleton, pose, bones):
    """How far the lowest vertex of `bones` is under the floor (y down)."""
    p = copy.deepcopy(pose)
    p[0] = [4096] * 3 + [0] * 6
    mats = mmd.bone_matrices(model, p)
    return max(sum(mats[b][1][j] * v[j] for j in range(3)) + mats[b][1][3]
               for b in bones for v in model.tmd.obj_verts(skeleton[b][0]))


def ticks_floor(model, skeleton, frames, bones):
    """Per tick of a looping clip (len(frames) - 1 ticks), the lowest point there and at the thirds on both sides."""
    n = len(frames) - 1
    low = [-1e9] * n
    for i in range(n):
        for alpha in (0, 1365, 2730, 4096):
            f = lowest(model, skeleton, interpolate_pose(frames[i], frames[i + 1], alpha), bones)
            for k in (i, (i + 1) % n):
                low[k] = max(low[k], f)
    return low


def lift_off_floor(model, skeleton, frames, bones, carrier, clear=.5):
    """Whatever still dips through the floor lifts the whole body there, eased over the neighbouring ticks (two
    units a tick); the frames rounded. Returns the frames and the largest lift."""
    n = len(frames) - 1
    low = ticks_floor(model, skeleton, frames, bones)
    lift = [max(0., max(low[j] + clear - 2 * min((i - j) % n, (j - i) % n) for j in range(n))) for i in range(n)]
    for tick, pose in enumerate(frames):
        pose[carrier][7] -= lift[tick % n]
    frames = [[[round(x) for x in bone] for bone in pose] for pose in frames]
    worst = max(ticks_floor(model, skeleton, frames, bones))
    assert worst <= 1, worst
    return frames, max(lift)
