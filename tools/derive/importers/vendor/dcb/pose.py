"""Bone matrices. A bone's local matrix is T(joint offset + animated offset) ·
R · S with R = Ry·Rx·Rz (what the game's routine 0x8005cbc4 builds; checked
by running it in the source game rotation routine) and S the scale (libgte
ScaleMatrix, columns); world = parent world · local."""
import math
from functools import lru_cache
from tools.derive import arraymath as np

ANGLE = 2 * np.pi / 4096


def rot_x(a):
    c, s = math.cos(float(a)), math.sin(float(a))
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(a):
    c, s = math.cos(float(a)), math.sin(float(a))
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_z(a):
    c, s = math.cos(float(a)), math.sin(float(a))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def rotation(angles):
    x, y, z = (float(a) * ANGLE for a in angles)
    # Bone rotations repeat across frames. Cache immutable values, returning a
    # fresh array so callers may still edit it. Distinguish signed zero, which
    # float equality alone would merge (atan2 can observe its sign).
    signs = sum(1 << i for i, a in enumerate((x, y, z)) if a == 0 and math.copysign(1, a) < 0)
    return np.Array([v for row in _rotation(x, y, z, signs) for v in row], (3, 3), np.float64)


@lru_cache(maxsize=2048)
def _rotation(x, y, z, signs):
    # numpy's tiny matrix products and trig ufuncs differ in the last bit between
    # native BLAS/SIMD and Wasm. Those bits can change an integer MMD key.
    # Use derive's correctly rounded math functions and Python 3.14's sum.
    def multiply(a, b):
        return [[sum((r[0] * b[0][j], r[1] * b[1][j], r[2] * b[2][j])) for j in range(3)] for r in a]
    cx, sx = math.cos(x), math.sin(x)
    cy, sy = math.cos(y), math.sin(y)
    cz, sz = math.cos(z), math.sin(z)
    ry = [[cy, 0., sy], [0., 1., 0.], [-sy, 0., cy]]
    rx = [[1., 0., 0.], [0., cx, -sx], [0., sx, cx]]
    rz = [[cz, -sz, 0.], [sz, cz, 0.], [0., 0., 1.]]
    result = multiply(multiply(ry, rx), rz)
    return tuple(tuple(r) for r in result)


def local_trs(bone, channels=None):
    """(translation, 3x3 rotation, scale) of a bone; channels is one row of
    anim.play() (rx, ry, rz, tx, ty, tz, sx, sy, sz) or None for the rest pose
    (no rotation, unit scale)."""
    off = bone.offset
    if channels is None:
        return np.Array([float(v) for v in off], (3,), np.float64), np.eye(3), np.ones(3)
    ch = list(channels)
    t = np.Array([float(off[i]) + ch[i + 3] for i in range(3)], (3,), np.float64)
    scale = np.Array([ch[i + 6] / 4096 for i in range(3)], (3,), np.float64)
    return t, rotation(ch[:3]), scale


def world_matrices(model, frame=None, unit_scale=False):
    """4x4 model-space matrix of every bone; frame is (nbones, 9) or None."""
    out = [None] * len(model.bones)

    def world(b):
        if out[b.index] is None:
            t, r, s = local_trs(b, None if frame is None else frame[b.index])
            m = np.eye(4)
            m[:3, :3] = r if unit_scale else r * s
            m[:3, 3] = t
            out[b.index] = m if b.parent < 0 else world(model.bones[b.parent]) @ m
        return out[b.index]

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
