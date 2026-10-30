"""Evaluate the bone tracks of a model on the shared animation timeline."""
from tools.derive import arraymath as np
import math
from functools import lru_cache

ANGLE = 2 * np.pi / 4096


def _sample(keys, frame):
    if frame <= keys[0][0]: return tuple(float(v) for v in keys[0][1])
    for (f0, a), (f1, b) in zip(keys, keys[1:]):
        if f0 <= frame < f1:
            t = (frame - f0) / (f1 - f0)
            return tuple(float(x) * (1 - t) + float(y) * t for x, y in zip(a, b))
    return tuple(float(v) for v in keys[-1][1])


def sample(keys, frame):
    return np.Array(list(_sample(keys, frame)), (3,), np.float64)


def rot_x(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_z(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def rotation(angles):
    x, y, z = (float(v) * ANGLE for v in angles)
    signs = sum(1 << i for i, v in enumerate((x, y, z)) if v == 0 and math.copysign(1, v) < 0)
    return np.Array(list(_rotation(x, y, z, signs)), (3, 3), np.float64)


@lru_cache(maxsize=2048)
def _rotation(x, y, z, signs):
    cx, sx = math.cos(x), math.sin(x)
    cy, sy = math.cos(y), math.sin(y)
    cz, sz = math.cos(z), math.sin(z)
    rx = ((1., 0., 0.), (0., cx, -sx), (0., sx, cx))
    ry = ((cy, 0., sy), (0., 1., 0.), (-sy, 0., cy))
    rz = ((cz, -sz, 0.), (sz, cz, 0.), (0., 0., 1.))
    def multiply(a, b):
        return [[((0.0 + r[0]*b[0][j]) + r[1]*b[1][j]) + r[2]*b[2][j] for j in range(3)] for r in a]
    return tuple(v for row in multiply(multiply(rz, ry), rx) for v in row)


def local_trs(bone, frame):
    return (np.Array(list(_sample(bone.translation, frame)), (3,), np.float64),
            rotation(_sample(bone.rotation, frame)),
            np.Array([v / 4096 for v in _sample(bone.scale, frame)], (3,), np.float64))


def local_matrix(bone, frame, unit_scale=False):
    t, r, s = local_trs(bone, frame)
    m = np.eye(4)
    m[:3, :3] = r if unit_scale else r * s
    m[:3, 3] = t
    return m


def world_matrices(model, frame, unit_scale=False):
    """4x4 model-space matrix of every bone (list index = bone.index - 1).
    unit_scale ignores the scale tracks, which some bones set to 0 to hide
    themselves; a bind pose needs invertible matrices."""
    out = [None] * len(model.bones)

    def world(b):
        i = b.index - 1
        if out[i] is None:
            m = local_matrix(b, frame, unit_scale)
            out[i] = m if b.parent == 0 else world(model.bones[b.parent - 1]) @ m
        return out[i]

    for b in model.bones:
        world(b)
    return out


def quaternion(m):
    """xyzw quaternion of a 3x3 rotation matrix."""
    w = np.sqrt(max(0.0, 1 + m[0, 0] + m[1, 1] + m[2, 2])) / 2
    x = np.sqrt(max(0.0, 1 + m[0, 0] - m[1, 1] - m[2, 2])) / 2
    y = np.sqrt(max(0.0, 1 - m[0, 0] + m[1, 1] - m[2, 2])) / 2
    z = np.sqrt(max(0.0, 1 - m[0, 0] - m[1, 1] + m[2, 2])) / 2
    x = np.copysign(x, m[2, 1] - m[1, 2])
    y = np.copysign(y, m[0, 2] - m[2, 0])
    z = np.copysign(z, m[1, 0] - m[0, 1])
    q = np.array([x, y, z, w])
    return q / np.linalg.norm(q)


def animation_frames(anim):
    """Timeline frame for every displayed frame of an animation."""
    frames = []
    for seg in anim.segments:
        if seg.start == seg.end:
            frames += [seg.start] * seg.duration
        else:
            frames += list(range(seg.start, seg.end + 1))
    return frames
