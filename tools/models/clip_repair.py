"""Repairs of a source game's clip on our rig: the original's poses, timing and arc kept, the bones that break it put right.

A battle clip given back from the source game (`battle_restore.py`, `field_animations/native_battle.py`,
`field_animations/bound_battle.py`) can fail tools/models/battle_qa.py on our rig: a torso tipped further than the
species' stance, a limb through the body, claws crossing, the soles under the floor. A rebuild keeps the original as the
reference of motion, character and timing and changes only what breaks, with these operations on the decoded ticks
(poses of `nb` bones: scale x/y/z, rotation x/y/z in 1/4096 turn, translation x/y/z; bone 0 carries the root's travel):

  {"op": "turn", "bone": B, "axis": "x"|"y"|"z"|[x, y, z], "deg": D [, "ticks": [a, b, c, d]]}
        the bone (and everything hanging from it) turned D degrees about a model axis at its joint (x the side, y down,
        z back: a positive x turn tips the bone's front down). The parent chain's own rotation is taken out, so the
        clip's swing, timing and travel stay. With `ticks`, the turn eases in from tick a to b, holds to c and eases
        out to d (smoothstep): a limb moved out of the body only where it would cross it.
  {"op": "damp", "bone": B, "keep": K [, "to": "mean"|"first", "ticks": [a, b, c, d]]}
        the bone's local rotation pulled toward its own mean (or first) pose of the clip: K = 1 is the clip as it is,
        0 the bone held still. Its children keep their own local motion.
  {"op": "smooth", "bone": B [, "passes": N, "weight": W, "ticks": [a, b, c, d]]}
        the bone's local rotation low-pass filtered along the ticks (each pass: the tick's rotation blended with its two
        neighbours', weights W, 1 - 2W, W; W 0.25 by default; a loop, whose last tick repeats its first, wraps round; the ends of a one-shot keep their own side): a one-tick snap spread over
        its neighbours, where a clip played faster than the source's own speed makes a leg flick. Poses stay on the
        path the clip already takes; with `ticks`, only where the envelope is.
  {"op": "mirror", "bone": B, "from": S, "shift": K}
        bone B takes the local rotation of its mirror twin S (the same leg on the other side of the body), mirrored
        left to right (the Euler y and z negated), K ticks later (wrapping on a loop, whose last tick repeats its first;
        the end tick holds on a one-shot): a leg the source never animated, moving as its twin does half a stride on.
  {"op": "wave", "bone": B, "axis": "x"|"y"|"z"|[x, y, z], "deg": D [, "cycles": N, "phase": P, "ticks": [a, b, c, d]]}
        the bone swung D degrees either way about a model axis, N sways over the clip (1 by default; a loop's last tick
        repeats its first, so a loop closes), starting P of a sway in (0 to 1): a chain the source never animated (a tail
        left stiff) moving as the species' field walk moves it. Everything else as `turn`.
  {"op": "lift", "bone": B, "up": U [, "ticks": [a, b, c, d]]}
        bone B (the body bone under the root; its translation, in its parent's frame) raised U units: the soles back on
        the floor where the original sinks on our rig. The root's own travel is never touched.

  {"op": "retime", "ticks": N}
        the whole clip resampled to N ticks (a slower or faster original: its frantic speed brought into the range of the
        disc's own clips); rotations go through quaternions, offsets and scales linearly. Put it first.
  {"op": "seam", "ticks": K [, "bones": [B, ...]]}
        a looping clip whose last pose is not the first: over its last K ticks the bones (default every bone under the root)
        ease toward the first pose, reaching it one tick after the last (the loop's own step), so the seam closes.

  {"op": "sway", "bone": B, "axis": ..., "deg": D, "cycles": C [, "phase": P]}
        a bone the original never moves (a limb left out of its bone map) swung D degrees about a model axis, C whole
        cycles over the clip (sine from tick 0 to the last tick, P in turns), so it starts and ends where it was.

Operations run in the order given. Only the rotation channels of the bones named (and a lifted bone's height) change; scale
channels (the chibi reshape) and every other bone stay as they were. Standard library only (deterministic under
tools/derive's correctly rounded math), so a derive stage can apply a recipe's repairs.
"""
import math

DEG = 4096 / 360
AXES = {'x': (1.0, 0.0, 0.0), 'y': (0.0, 1.0, 0.0), 'z': (0.0, 0.0, 1.0)}


def _rot(rx, ry, rz):
    """libgte RotMatrix: M = Rx.Ry.Rz, angles in 1/4096 turn (as mmd.rot_matrix)."""
    k = 2 * math.pi / 4096
    cx, sx, cy, sy, cz, sz = (math.cos(rx * k), math.sin(rx * k), math.cos(ry * k), math.sin(ry * k),
                              math.cos(rz * k), math.sin(rz * k))
    return [[cy * cz, -cy * sz, sy],
            [sx * sy * cz + cx * sz, -sx * sy * sz + cx * cz, -sx * cy],
            [-cx * sy * cz + sx * sz, cx * sy * sz + sx * cz, cx * cy]]


def _euler(m, prev):
    """(rx, ry, rz) in 1/4096 turn with m = Rx.Ry.Rz, the solution closest to `prev` (mmd.matrix_euler)."""
    import mmd
    return mmd.matrix_euler(m, prev=prev)


def _mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _tr(a):
    return [[a[j][i] for j in range(3)] for i in range(3)]


def _axis_angle(axis, deg):
    x, y, z = AXES[axis] if isinstance(axis, str) else axis
    n = math.sqrt(x * x + y * y + z * z)
    x, y, z = x / n, y / n, z / n
    k = math.radians(deg)
    c, s, t = math.cos(k), math.sin(k), 1 - math.cos(k)
    return [[t * x * x + c, t * x * y - s * z, t * x * z + s * y],
            [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
            [t * x * z - s * y, t * y * z + s * x, t * z * z + c]]


def _quat(m):
    tr = m[0][0] + m[1][1] + m[2][2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        q = [0.25 * s, (m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s]
    elif m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2
        q = [(m[2][1] - m[1][2]) / s, 0.25 * s, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s]
    elif m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2
        q = [(m[0][2] - m[2][0]) / s, (m[0][1] + m[1][0]) / s, 0.25 * s, (m[1][2] + m[2][1]) / s]
    else:
        s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2
        q = [(m[1][0] - m[0][1]) / s, (m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, 0.25 * s]
    return q


def _matrix(q):
    w, x, y, z = q
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]


def _slerp(a, b, t):
    d = sum(p * q for p, q in zip(a, b))
    if d < 0:
        b, d = [-v for v in b], -d
    if d > 0.9995:
        q = [p + t * (r - p) for p, r in zip(a, b)]
    else:
        th = math.acos(d)
        sa, sb = math.sin((1 - t) * th) / math.sin(th), math.sin(t * th) / math.sin(th)
        q = [sa * p + sb * r for p, r in zip(a, b)]
    n = math.sqrt(sum(v * v for v in q))
    return [v / n for v in q]


def envelope(ticks, t):
    """Weight 0..1 of tick t for a trapezoid [a, b, c, d] eased with smoothstep (None: 1 everywhere)."""
    if not ticks:
        return 1.0
    a, b, c, d = ticks

    def ease(u):
        u = max(0.0, min(1.0, u))
        return u * u * (3 - 2 * u)
    if t < a or t > d:
        return 0.0
    if t < b:
        return ease((t - a) / (b - a)) if b > a else 1.0
    if t <= c:
        return 1.0
    return ease((d - t) / (d - c)) if d > c else 1.0


def _chain(parents, pose, b, cache):
    """World rotation of bone b's parent chain (b included) for `pose`'s original angles."""
    if b < 0:
        return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    if b not in cache:
        cache[b] = _mul(_chain(parents, pose, parents[b], cache), _rot(*pose[b][3:6]))
    return cache[b]


def turn(frames, parents, bone, axis, deg, ticks=None):
    out = []
    for t, pose in enumerate(frames):
        pose = [list(v) for v in pose]
        w = envelope(ticks, t)
        if w > 0:
            parent = _chain(parents, pose, parents[bone], {})
            new = _mul(_tr(parent), _mul(_axis_angle(axis, deg * w), _mul(parent, _rot(*pose[bone][3:6]))))
            pose[bone][3:6] = list(_euler(new, pose[bone][3:6]))
        out.append(pose)
    return out


def wave(frames, parents, bone, axis, deg, cycles=1.0, phase=0.0, ticks=None):
    n = len(frames)
    out = []
    for t, pose in enumerate(frames):
        pose = [list(v) for v in pose]
        w = envelope(ticks, t)
        a = deg * w * math.sin(2 * math.pi * (cycles * t / max(n - 1, 1) + phase))
        if abs(a) > 1e-9:
            parent = _chain(parents, pose, parents[bone], {})
            new = _mul(_tr(parent), _mul(_axis_angle(axis, a), _mul(parent, _rot(*pose[bone][3:6]))))
            pose[bone][3:6] = list(_euler(new, pose[bone][3:6]))
        out.append(pose)
    return out


def sway(frames, parents, bone, axis, deg, cycles, phase=0.0):
    n = len(frames) - 1
    out = []
    for t, pose in enumerate(frames):
        pose = [list(v) for v in pose]
        a = deg * (math.sin(2 * math.pi * (cycles * t / n + phase)) - math.sin(2 * math.pi * phase))
        parent = _chain(parents, pose, parents[bone], {})
        new = _mul(_tr(parent), _mul(_axis_angle(axis, a), _mul(parent, _rot(*pose[bone][3:6]))))
        pose[bone][3:6] = list(_euler(new, pose[bone][3:6]))
        out.append(pose)
    return out


def damp(frames, bone, keep, to='mean', ticks=None):
    qs = [_quat(_rot(*pose[bone][3:6])) for pose in frames]
    if to == 'first':
        ref = qs[0]
    else:
        acc = [0.0] * 4
        for q in qs:
            s = 1 if sum(p * r for p, r in zip(q, qs[0])) >= 0 else -1
            acc = [a + s * v for a, v in zip(acc, q)]
        n = math.sqrt(sum(v * v for v in acc))
        ref = [v / n for v in acc]
    out = []
    for t, pose in enumerate(frames):
        pose = [list(v) for v in pose]
        k = 1 - (1 - keep) * envelope(ticks, t)
        if k < 1:
            pose[bone][3:6] = list(_euler(_matrix(_slerp(ref, qs[t], k)), pose[bone][3:6]))
        out.append(pose)
    return out


def smooth(frames, bone, passes=1, weight=0.25, ticks=None):
    qs = [_quat(_rot(*pose[bone][3:6])) for pose in frames]
    for i in range(1, len(qs)):                      # one hemisphere along the clip
        if sum(p * r for p, r in zip(qs[i], qs[i - 1])) < 0:
            qs[i] = [-v for v in qs[i]]
    closed = len(frames) > 2 and all(a[3:6] == b[3:6] for a, b in zip(frames[0], frames[-1]))
    if closed:                                       # a loop: its last tick repeats its first, the cycle wraps
        qs = qs[:-1]
    n = len(qs)
    for _ in range(passes):
        new = []
        for t in range(n):
            lo, hi = (qs[(t - 1) % n], qs[(t + 1) % n]) if closed else (qs[max(t - 1, 0)], qs[min(t + 1, n - 1)])
            q = [weight * a + (1 - 2 * weight) * c + weight * b for a, c, b in zip(lo, qs[t], hi)]
            m = math.sqrt(sum(v * v for v in q))
            new.append([v / m for v in q])
        qs = new
    if closed:
        qs.append(qs[0])
    out = []
    for t, pose in enumerate(frames):
        pose = [list(v) for v in pose]
        w = envelope(ticks, t)
        if w > 0:
            orig = _quat(_rot(*pose[bone][3:6]))
            if sum(p * r for p, r in zip(orig, qs[t])) < 0:
                orig = [-v for v in orig]
            pose[bone][3:6] = list(_euler(_matrix(_slerp(orig, qs[t], w)), pose[bone][3:6]))
        out.append(pose)
    return out


def mirror(frames, bone, source, shift=0):
    n = len(frames)
    closed = n > 2 and all(a[3:6] == b[3:6] for a, b in zip(frames[0], frames[-1]))
    out = []
    for t in range(n):
        pose = [list(v) for v in frames[t]]
        u = (t + shift) % (n - 1) if closed else min(max(t + shift, 0), n - 1)
        rx, ry, rz = frames[u][source][3:6]
        pose[bone][3:6] = [rx, -ry, -rz]
        out.append(pose)
    return out


def lift(frames, bone, up, ticks=None):
    if bone == 0:
        raise ValueError('clip repair: lift a body bone, not the root (its channels carry the travel)')
    out = []
    for t, pose in enumerate(frames):
        pose = [list(v) for v in pose]
        pose[bone][7] = pose[bone][7] - up * envelope(ticks, t)     # y points down
        out.append(pose)
    return out


def fit_rig(frames, source_pose, rig_pose):
    """`frames` (a source clip) fitted to a rig that was reshaped after the source: the reshaped species' reference pose
    (`rig_pose`) against the source's (`source_pose`), poses of the same reference tick of the same slot.

    Each bone takes the rig's scale channels, and its translation (the bone's offset from its parent, which the reshape
    scales per axis) multiplied by the ratio rig / source at the reference tick (only where the source's offset is at least
    20 units; smaller offsets stay). The body bone (1), whose height the reshape also moves, instead keeps the source's
    motion about the offset between the two reference ticks. Rotations and the root bone (0) are not touched."""
    out = []
    for pose in frames:
        bones = []
        for b, bone in enumerate(pose):
            bone = list(bone)
            if b:
                bone[0:3] = rig_pose[b][0:3]
                for i in range(6, 9):
                    s0, r0 = source_pose[b][i], rig_pose[b][i]
                    if abs(s0) >= 20:
                        bone[i] = bone[i] + (r0 - s0) if (b == 1 and i == 7) else bone[i] * r0 / s0
            bones.append(bone)
        out.append(bones)
    return out


def _mix(a, b, w):
    """Pose bone a toward pose bone b by w: rotation through quaternions, the other channels linearly."""
    out = [x + (y - x) * w for x, y in zip(a, b)]
    out[3:6] = list(_euler(_matrix(_slerp(_quat(_rot(*a[3:6])), _quat(_rot(*b[3:6])), w)), a[3:6]))
    return out


def retime(frames, ticks):
    n = len(frames) - 1
    out = []
    for t in range(ticks + 1):
        x = t * n / ticks
        i = min(int(x), n - 1) if n else 0
        w = x - i
        out.append([list(v) for v in frames[i]] if w == 0 or n == 0 else
                   [_mix(a, b, w) for a, b in zip(frames[i], frames[i + 1])])
    return out


def seam(frames, ticks, bones=None):
    n = len(frames)
    first = frames[0]
    out = [[list(v) for v in pose] for pose in frames]
    for k in range(ticks):
        t = n - ticks + k
        u = (k + 1) / (ticks + 1)
        w = u * u * (3 - 2 * u)
        for b in (bones if bones is not None else range(1, len(first))):
            out[t][b] = _mix(frames[t][b], first[b], w)
    return out


def apply_ops(frames, parents, ops):
    """`frames` (poses per tick) with the repair operations `ops` applied in order, as whole numbers."""
    for op in ops:
        kind = op['op']
        if kind == 'turn':
            frames = turn(frames, parents, op['bone'], op['axis'], op['deg'], op.get('ticks'))
        elif kind == 'wave':
            frames = wave(frames, parents, op['bone'], op['axis'], op['deg'], op.get('cycles', 1.0), op.get('phase', 0.0),
                          op.get('ticks'))
        elif kind == 'damp':
            frames = damp(frames, op['bone'], op['keep'], op.get('to', 'mean'), op.get('ticks'))
        elif kind == 'smooth':
            frames = smooth(frames, op['bone'], op.get('passes', 1), op.get('weight', 0.25), op.get('ticks'))
        elif kind == 'mirror':
            frames = mirror(frames, op['bone'], op['from'], op.get('shift', 0))
        elif kind == 'sway':
            frames = sway(frames, parents, op['bone'], op['axis'], op['deg'], op['cycles'], op.get('phase', 0.0))
        elif kind == 'retime':
            frames = retime(frames, op['ticks'])
        elif kind == 'seam':
            frames = seam(frames, op['ticks'], op.get('bones'))
        elif kind == 'lift':
            frames = lift(frames, op['bone'], op['up'], op.get('ticks'))
        else:
            raise ValueError(f'clip repair: unknown operation {kind!r}')
    return [[[int(round(v)) for v in bone] for bone in pose] for pose in frames]
