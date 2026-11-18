"""Triangle-against-triangle clash counts between two bone groups of a posed model (needs numpy).

`Clash(model, rig)` poses the model per tick; `clash(pose, limbs, others)` returns the number of crossing triangle
pairs and the deepest crossing: for a pair, how far the limb triangle reaches through the other triangle's plane
(the smaller of its two sides), in model units. Thin shells such as a mane are open, so this counts crossings of the
surface; a point-inside test would see nothing in them.
"""
import copy
from types import SimpleNamespace

import numpy as np

import animstudio
import mmd


def _crossings(p0, p1, tris):
    """Segments (n, 3) from p0 to p1 against triangles (m, 3, 3): boolean (n, m) of crossings (Moeller-Trumbore)."""
    e1, e2 = tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]
    d = p1 - p0
    h = np.cross(d[:, None, :], e2[None])
    a = (e1[None] * h).sum(2)
    ok = np.abs(a) > 1e-9
    f = 1 / np.where(ok, a, 1)
    s = p0[:, None, :] - tris[None, :, 0]
    u = f * (s * h).sum(2)
    q = np.cross(s, e1[None])
    v = f * (q * d[:, None, :]).sum(2)
    t = f * (e2[None] * q).sum(2)
    return ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t >= 0) & (t <= 1)


def crossing(a, b, *, depth=True, symmetric=False):
    """(pairs, deepest) for triangle arrays a (n, 3, 3) and b (m, 3, 3).

    symmetric=True measures penetration through both triangles' planes while
    reusing the same hit mask; the default retains the limb-side depth metric.
    """
    hit = np.zeros((len(a), len(b)), bool)
    for k in range(3):
        k2 = (k + 1) % 3
        hit |= _crossings(a[:, k], a[:, k2], b)
        hit |= _crossings(b[:, k], b[:, k2], a).T
    pairs = int(hit.sum())
    if not pairs or not depth:
        return pairs, 0.0
    ia, ib = np.nonzero(hit)

    def depths(left, right):
        n = np.cross(right[:, 1]-right[:, 0], right[:, 2]-right[:, 0]).astype(float)
        n /= np.linalg.norm(n, axis=1)[:, None] + 1e-9
        dist = np.einsum('nvi,ni->nv', left-right[:, None, 0], n)
        return np.minimum(np.maximum(dist.max(1), 0), np.maximum(-dist.min(1), 0))

    deepest = float(depths(a[ia], b[ib]).max())
    if symmetric:
        deepest = max(deepest, float(depths(b[ib], a[ia]).max()))
    return pairs, deepest



class Clash:
    def __init__(self, model, rig):
        self.model = model
        self.mesh = animstudio.FastMesh(SimpleNamespace(m=model, skel=rig))

    def world(self, pose):
        p = copy.deepcopy(pose)
        p[0] = [4096] * 3 + [0] * 6
        return self.mesh.world(mmd.bone_matrices(self.model, p)).astype(float)

    def tris(self, world, bones):
        return world[self.mesh.tri[np.isin(self.mesh.bone, bones)]]

    def clash(self, pose, limbs, others, world=None):
        world = self.world(pose) if world is None else world
        return crossing(self.tris(world, limbs), self.tris(world, others))
