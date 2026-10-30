"""Cherrymon's partner animations, authored as per-tick poses.

Conventions (the engine's, docs/mods/models.md § 2.2): Y points down, the Digimon faces
-Z, angles are 1/4096 of a turn and a bone's matrix is Rx·Ry·Rz. Cherrymon's rest pose
has no rotations (every piece is modelled in place), so each bone's rotation here is
simply its rotation relative to its parent, about the pivot at the joint. The helpers
take degrees.

Skeleton (bone: parent), JURE.MMD, x < 0 is the side the face's right eye is on:
  1 hips (no mesh)   2 trunk   3, 4, 5 canopy layers (children of the trunk)
  front arms  6-7-8 (x < 0), 9-10-11 (x > 0)      hang down at the sides of the face
  upper arms 12-13-14 (x < 0), 15-16-17 (x > 0)   higher and a bit behind
  roots 18-19 front x < 0, 20-21 front x > 0, 22-23 back x < 0, 24-25 back x > 0
All arms and roots hang from the hips (bone 1), not from the trunk: when the trunk
leans, the arms must follow (TrunkFollow) or they float off the bark.
"""
import math

NB = 26
HIPS, TRUNK = 1, 2
CANOPY = (3, 4, 5)
CANOPY_Y = (-305, -371, -473)   # layer centres in the trunk's frame (scaled model)
CANOPY_PIVOT = -250             # where the trunk forks into branches
ARMS = {'fl': (6, 7, 8, -1), 'fr': (9, 10, 11, 1), 'ul': (12, 13, 14, -1), 'ur': (15, 16, 17, 1)}
ROOTS = {'fl': (18, 19, -1), 'fr': (20, 21, 1), 'bl': (22, 23, -1), 'br': (24, 25, 1)}
U = 4096 / 360.0                      # engine units per degree

# eye and mouth frames (texture moves, the NPC animations' own rectangles; x in 16-bit words)
EYES = {'open': (16, 16), 'narrow': (4, 16), 'half': (8, 16), 'closed': (12, 16)}
MOUTH = {'closed': (12, 0), 'open': (0, 0)}

# every slot the 64 partner models have, plus Cherrymon's nine techniques (0x2E..0x36)
REQUIRED_SLOTS = ([0, 1, 2, 3, 4, 5] + list(range(7, 0x14)) + list(range(0x15, 0x1A)) + [0x1B] +
                  list(range(0x21, 0x26)) + list(range(0x28, 0x2D)) + list(range(0x2E, 0x37)))


def eyes(state):
    return ('tex', dict(src=EYES[state], size=(4, 24), dst=(0, 16)))


def mouth(state):
    return ('tex', dict(src=MOUTH[state], size=(12, 16), dst=(24, 32)))


def sound(bank, note):
    return ('sound', dict(bank=bank, note=note))


# ---------------------------------------------------------------- curves
def smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def keys(t, ks, ease=smooth):
    """Piecewise interpolation through (tick, value) pairs (values may be tuples)."""
    if t <= ks[0][0]:
        return ks[0][1]
    for (t0, v0), (t1, v1) in zip(ks, ks[1:]):
        if t <= t1:
            u = ease((t - t0) / (t1 - t0)) if t1 > t0 else 1.0
            if isinstance(v0, tuple):
                return tuple(a + (b - a) * u for a, b in zip(v0, v1))
            return v0 + (v1 - v0) * u
    return ks[-1][1]


def wave(t, period, phase=0.0):
    return math.sin(2 * math.pi * (t / period + phase))


def bump(x):
    """0 -> 1 -> 0 over x in 0..1 (half sine)."""
    return math.sin(math.pi * max(0.0, min(1.0, x)))


# ---------------------------------------------------------------- poses
class Pose:
    """Offsets from the rest pose: per bone [rx, ry, rz] in degrees and [dx, dy, dz]."""

    def __init__(self):
        self.rot = [[0.0, 0.0, 0.0] for _ in range(NB)]
        self.off = [[0.0, 0.0, 0.0] for _ in range(NB)]
        self.abs = {}           # bone -> local rotation in engine units (retargeted bones)

    def r(self, b, rx=0.0, ry=0.0, rz=0.0):
        v = self.rot[b]
        v[0] += rx
        v[1] += ry
        v[2] += rz
        return self

    def t(self, b, dx=0.0, dy=0.0, dz=0.0):
        v = self.off[b]
        v[0] += dx
        v[1] += dy
        v[2] += dz
        return self

    # body parts -----------------------------------------------------------
    def hop(self, h):
        """Lift the whole tree (hips, so trunk, arms and roots) by h units."""
        return self.t(HIPS, dy=-h)

    def body(self, lean=0.0, side=0.0, twist=0.0):
        """Tilt the trunk (forward lean > 0, side > 0 towards +x, twist about the vertical)
        and carry the arms with it: they hang from the hips, so each arm root gets the
        trunk's rotation and the offset its shoulder moves by."""
        self.r(TRUNK, lean, twist, side)
        f = getattr(self, 'follow', (0.0, 0.0, 0.0))
        self.follow = (f[0] + lean, f[1] + twist, f[2] + side)
        return self

    def canopy(self, lean=0.0, side=0.0, twist=0.0, spread=1.0):
        """Canopy sway on top of the trunk. The three layers are separate pieces that
        rotate about their own centres; to read as one crown bending above the fork of
        the trunk, each layer gets the same rotation plus the shift that rotation gives
        its centre about the fork (CANOPY_PIVOT), and higher layers bend a bit more."""
        for k, b in enumerate(CANOPY):
            f = 1.0 + 0.12 * k * spread
            rx, ry, rz = lean * f, twist * f, side * f
            self.r(b, rx, ry, rz)
            h = CANOPY_Y[k] - CANOPY_PIVOT
            v = rotate((0.0, h, 0.0), rx, ry, rz)
            self.t(b, v[0], v[1] - h, v[2])
        return self

    def arm(self, name, raise_=0.0, fwd=0.0, twist=0.0, elbow=0.0, wrist=0.0, elbow_fwd=0.0, wrist_fwd=0.0):
        """raise_ > 0 lifts the arm out to its side, fwd > 0 swings it forward, elbow and
        wrist > 0 curl the forearm and the claw upwards (same sense as raise_)."""
        a, b, c, s = ARMS[name]
        self.r(a, twist * -s, s * fwd, -s * raise_)
        self.r(b, 0.0, s * elbow_fwd, -s * elbow)
        self.r(c, 0.0, s * wrist_fwd, -s * wrist)
        return self

    def root(self, name, lift=0.0, fwd=0.0, tip=0.0):
        a, b, s = ROOTS[name]
        self.r(a, 0.0, s * fwd, -s * lift)
        self.r(b, 0.0, 0.0, -s * tip)
        return self


class Rig:
    """Rest pose (bones 1..25: rx ry rz tx ty tz) and the trunk-follow transfer."""

    def __init__(self, rest):
        self.rest = rest

    def pose_list(self, p):
        """Engine pose [sx sy sz rx ry rz tx ty tz] of every bone for a Pose."""
        out = [[4096, 4096, 4096, 0, 0, 0, 0, 0, 0]]
        follow = getattr(p, 'follow', None)
        for b in range(1, NB):
            r0 = self.rest[b - 1]
            rot = list(p.rot[b])
            off = list(p.off[b])
            if b in p.abs:
                # retargeted: its rotation is already the whole local rotation (it follows
                # the source's model-space motion); only the shoulder rides on the trunk
                if follow and b in ARM_ROOTS:
                    lean, twist, side = follow
                    v = rotate((r0[3], r0[4], r0[5]), lean, twist, side)
                    off = [off[i] + v[i] - r0[3 + i] for i in range(3)]
                vals = [round(x) for x in p.abs[b]]
                out.append([4096, 4096, 4096] + vals + [round(r0[3 + i] + off[i]) for i in range(3)])
                continue
            if follow and b in ARM_ROOTS:
                # the arm root sits on the bark: rotate its offset from the hips about the
                # trunk pivot (the hips) and add the trunk's rotation to its own
                lean, twist, side = follow
                v = rotate((r0[3], r0[4], r0[5]), lean, twist, side)
                off = [off[i] + v[i] - r0[3 + i] for i in range(3)]
                rot = compose((lean, twist, side), rot)
            vals = [round(rot[i] * U) for i in range(3)]
            out.append([4096, 4096, 4096] + vals + [round(r0[3 + i] + off[i]) for i in range(3)])
        return out


ARM_ROOTS = (6, 9, 12, 15)


def rot_m(rx, ry, rz):
    return mat_deg(rx, ry, rz)


def mat_deg(rx, ry, rz):
    k = math.pi / 180
    cx, sx, cy, sy, cz, sz = (math.cos(rx * k), math.sin(rx * k), math.cos(ry * k), math.sin(ry * k),
                              math.cos(rz * k), math.sin(rz * k))
    return [[cy * cz, -cy * sz, sy],
            [sx * sy * cz + cx * sz, -sx * sy * sz + cx * cz, -sx * cy],
            [-cx * sy * cz + sx * sz, cx * sy * sz + sx * cz, cx * cy]]


def rotate(v, rx, ry, rz):
    M = mat_deg(rx, ry, rz)
    return [sum(M[i][j] * v[j] for j in range(3)) for i in range(3)]


def compose(a, b):
    """Euler (deg) of Rot(a)·Rot(b), M = Rx·Ry·Rz."""
    A, B = mat_deg(*a), mat_deg(*b)
    M = [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    sy = max(-1.0, min(1.0, M[0][2]))
    ry = math.asin(sy)
    rx = math.atan2(-M[1][2], M[2][2])
    rz = math.atan2(-M[0][1], M[0][0])
    d = 180 / math.pi
    return [rx * d, ry * d, rz * d]


# ---------------------------------------------------------------- clips
class Clip:
    """n ticks of animation. fn(t) -> Pose for t = 0..n-1 (sample t = pose after tick t+1).
    loop: the motion repeats from sample 0 (fn must be periodic: fn(n) == fn(0); a closing
    sample fn(n) is appended). root(t) -> (x, y, z) accumulated root motion at sample t,
    in the entity's frame (forward is -z). events: (sample, event)."""

    STEP = 3

    def __init__(self, rig, n, fn, loop=False, root=None, events=(), loop_from=0, step=None):
        self.rig, self.n, self.fn, self.loop, self.root, self.events = rig, n, fn, loop, root, list(events)
        self.loop_from = loop_from
        self.step = step or Clip.STEP

    def keyed(self, ts):
        """Poses at every `step` ticks (and at the first, the loop start and the last),
        linear in between: the engine interpolates linearly between keyframes anyway, and
        one key every 2-3 ticks is what keeps 45 animations inside the partner buffer."""
        last = ts[-1]
        ks = sorted(set([0, last, self.loop_from] + list(range(0, last + 1, self.step))))
        at = {k: self.rig.pose_list(self.fn(k)) for k in ks}
        out = []
        for t in ts:
            if t in at:
                out.append([list(v) for v in at[t]])
                continue
            a = max(k for k in ks if k < t)
            b = min(k for k in ks if k > t)
            u = (t - a) / (b - a)
            out.append([[round(x + (y - x) * u) for x, y in zip(va, vb)] for va, vb in zip(at[a], at[b])])
        return out

    def samples(self):
        ts = list(range(self.n)) + ([self.n] if self.loop else [])
        smp = []
        poses = self.keyed(ts)
        for t in ts:
            pose = poses[t]
            if self.root:
                if self.loop and t == self.n:
                    # the loop body repeats the per-tick deltas: the closing sample moves by
                    # the step of tick loop_from (+1 here) after the last one
                    x = [a + (b - c) for a, b, c in zip(self.root(self.n - 1), self.root(self.loop_from + 1),
                                                         self.root(self.loop_from))]
                else:
                    x = self.root(t)
                pose[0][6:9] = [round(v) for v in x]
            smp.append(pose)
        ev = [(k, kind, dict(c)) for k, (kind, c) in self.events if k < len(smp)]
        return smp, (self.loop_from if self.loop else None), ev


def linear_root(dist, n):
    """Steady forward motion: dist units over n ticks (one per sample, from tick 1)."""
    return lambda t: (0.0, 0.0, -dist * (t + 1) / n)


def face(eye='open', mth='closed', at=0):
    return [(at, eyes(eye)), (at, mouth(mth))]


def partner_clips(rig):
    """slot -> Clip. Filled in by the animation modules."""
    import anims
    return anims.build_all(rig)
