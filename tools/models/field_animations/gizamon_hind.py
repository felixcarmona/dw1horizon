"""Gizamon's hind legs in its walk, condition walk and run.

The frog-like hind leg folds its knee back and out beside the shell. The
earlier solve aimed the knee with a pole almost along the leg, so the thigh
wound round the hip once per stride (the knee went from high behind the hip to
forward of it and back, up to 26 degrees a tick) and the stride was centred so
far forward that the leg had to unfold to reach it.

Here each hind foot is planted heel to toe: the heel strikes with the toes up,
the sole rolls flat, the heel lifts over the planted toes and the foot pushes
off; the swing carries on backwards for a moment, lifts early, travels forward
on an arc and reaches out toes-up for the next strike. The knee stays out
beside the shell, above the hip, and never swings over or in front of it or
circles the hip. Each hind foot steps with
the diagonal front foot, a little ahead of it in the walks; the two hind feet
are half a cycle apart. Timing, root speed, body, head, tail and front legs are
the overlay's own and stay as they were.
"""
import math

import legik
import mmd
import retarget as R
from tools.models.field_animations import animal_refine as A

CHAINS = ((10, 11, 12, 1), (13, 14, 15, -1))
TURN = 4096 / 360


def _ease(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def _hermite(p0, p1, m0, m1, u):
    u2, u3 = u * u, u * u * u
    return (2 * u3 - 3 * u2 + 1) * p0 + (u3 - 2 * u2 + u) * m0 + (-2 * u3 + 3 * u2) * p1 + (u3 - u2) * m1


class Foot:
    """The sole of one hind foot: its heel and toe contact points and its rest orientation."""

    def __init__(self, model, sk, reference, foot):
        self.rest = R.world_rots(sk, reference)[foot]
        self.verts = [v[:3] for v in model.tmd.obj_verts(sk[foot][0])]
        world = [self._apply(self.rest, v) for v in self.verts]
        bottom = max(w[1] for w in world)
        sole = [i for i, w in enumerate(world) if w[1] > bottom - 1.5]
        self.heel = self.verts[max(sole, key=lambda i: world[i][2])]
        self.toe = self.verts[min(sole, key=lambda i: world[i][2])]

    @staticmethod
    def _apply(m, v):
        return [sum(m[i][j] * v[j] for j in range(3)) for i in range(3)]

    def rotation(self, pitch):
        """World rotation of the foot pitched by `pitch` degrees (positive: toes up)."""
        return R.m3mul(mmd.rot_matrix(-pitch * TURN, 0, 0), self.rest)

    def sole(self, pitch):
        """Lowest point of the foot below its ankle at this pitch."""
        m = self.rotation(pitch)
        return max(self._apply(m, v)[1] for v in self.verts)

    def ankle(self, pitch, point, at):
        """Ankle position that puts `point` ('heel' or 'toe') of the foot at world `at`."""
        offset = self._apply(self.rotation(pitch), self.heel if point == 'heel' else self.toe)
        return [at[i] - offset[i] for i in range(3)]


def plan(foot, q, g, stride_ticks, speed, x, ground):
    """Ankle position and foot pitch of a hind foot at gait phase q (0 = heel strike).

    g: duty, centre (heel z of the flat foot in the middle of the planted stretch), land and
    push pitches (degrees), lift, roll (fraction of stance spent rolling onto the sole), rise
    (fraction of stance after which the heel lifts), carry and curl (the swing). Settings live
    under "hind" in content/models/imports/followthrough.json, one set per slot."""
    duty = g['duty']
    stride = speed * stride_ticks * duty          # how far the body passes over a planted foot
    heel0 = g['centre'] - stride / 2               # heel z at the strike (forward is z negative)
    flat = foot.rotation(0)
    toe_dz = foot._apply(flat, foot.toe)[2] - foot._apply(flat, foot.heel)[2]

    def stance(s):
        heel_z = heel0 + stride * s
        if s < g['roll']:
            pitch, point, z = g['land'] * (1 - _ease(s / g['roll'])), 'heel', heel_z
        elif s < g['rise']:
            pitch, point, z = 0.0, 'heel', heel_z
        else:
            pitch, point, z = -g['push'] * ((s - g['rise']) / (1 - g['rise'])) ** 1.5, 'toe', heel_z + toe_dz
        at = foot.ankle(pitch, point, [0, ground, z])
        return [x, min(at[1], ground - foot.sole(pitch)), at[2]], pitch

    if q < duty:
        return stance(q / duty)
    u = (q - duty) / (1 - duty)
    start, p0 = stance(1.0)
    end, p1 = stance(0.0)
    # Leave and arrive moving backwards with the ground, so the foot does not snap round.
    m = speed * stride_ticks * (1 - duty) * g['carry']
    z = _hermite(start[2], end[2], m, m, u)
    pitch = p0 + (p1 - p0) * _ease((u - 0.25) / 0.7) - g['curl'] * math.sin(math.pi * min(1.0, u / 0.7)) ** 2
    lift = g['lift'] * math.sin(math.pi * u ** 0.6)
    y = start[1] + (end[1] - start[1]) * _ease(u) - lift
    y = min(y, ground - foot.sole(pitch) - 3 * math.sin(math.pi * u))   # the swinging sole stays off the ground
    return [x, y, z], pitch


def _leg(sk, pose, reference, chain, goal, foot_rotation, history, pole):
    """Two-bone leg to `goal`, each bone turned from its rest orientation by the smallest rotation that points it
    at its new direction: no roll about its own length (a plane-frame solve rolls thigh and shin round as the
    bend plane turns, up to a full turn per stride on this sprawled leg)."""
    hip, knee, foot = chain
    rp, rw = R.world_pos(sk, reference), R.world_rots(sk, reference)
    origin = R.world_pos(sk, pose)[hip]
    joint, end = legik.solve(origin, goal, math.dist(rp[hip], rp[knee]), math.dist(rp[knee], rp[foot]), pole)
    for bone, child, a, b in ((hip, knee, origin, joint), (knee, foot, joint, end)):
        rest = [rp[child][i] - rp[bone][i] for i in range(3)]
        A.set_world(sk, pose, bone, R.m3mul(R.swing(rest, [b[i] - a[i] for i in range(3)]), rw[bone]), history)
    A.set_world(sk, pose, foot, foot_rotation, history)


def solve(model, sk, pose, reference, phase, ticks, speed, cfg, history):
    """Write the hind-leg rotations of one root-free pose at gait phase `phase`."""
    rp = R.world_pos(sk, reference)
    for (hip, knee, foot, side), offset in zip(CHAINS, cfg['offsets']):
        f = Foot(model, sk, reference, foot)
        q = (phase + offset) % 1
        x = rp[foot][0] + side * cfg.get('spread', 0)
        ankle, pitch = plan(f, q, cfg, ticks, speed, x, -1)
        hip_z = R.world_pos(sk, pose)[hip][2]
        # Aim the knee out beside the shell and well above the hip, sliding back with the foot. A pole near the
        # hip-ankle line (the old one, and a level one when the lifted foot passes beside the hip) leaves the bend
        # plane undefined: the knee then drops under the hip and the thigh circles it.
        out, up, follow, back = cfg['path']
        pole = [side * out, up, follow * (ankle[2] - hip_z) + back]
        _leg(sk, pose, reference, (hip, knee, foot), ankle, f.rotation(pitch), history, pole)


def rest_chart(frames, reference, bones=range(10, 16)):
    """Write each hind bone of a whole cycle in the Euler solution nearest the idle pose. Each angle triple has a
    twin (x + half a turn, half a turn - y, z + half a turn) for the same rotation, and turning a whole cycle into
    its twins changes neither a key nor an in-between frame; the chart picker may still settle on the twin, which
    sits half a turn from the idle angles on two channels (a hip that reads as spun round from idle to walk)."""
    for bone in bones:
        rest = reference[bone][3:6]
        best = None
        for flip in (False, True):
            track = [[p[bone][3] + 2048, 2048 - p[bone][4], p[bone][5] + 2048] if flip else list(p[bone][3:6])
                     for p in frames]
            shift = [4096 * round((r - v) / 4096) for r, v in zip(rest, track[0])]
            track = [[v + s for v, s in zip(t, shift)] for t in track]
            cost = sum(abs(v - r) for v, r in zip(track[0], rest))
            if best is None or cost < best[0]:
                best = (cost, track)
        for pose, angles in zip(frames, best[1]):
            pose[bone][3:6] = angles
