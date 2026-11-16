"""Offline material evidence: affine texture sampling and PSX 5-bit blending.

Neutral lighting; orthographic projection, back-face culling, painter sorting by
primitive mean depth quantised into four-unit OT bins (no z buffer). This is not a cycle-accurate GPU/OT emulator.
The model's ABE, sampled CLUT STP, zero-colour discard and four ABR equations
are respected. NumPy is only an authoring dependency.
"""
import numpy as np
from tools.models import meshcheck


def composite(background, words, abe, abr):
    """RGB5 background and sampled uint16 CLUT words -> RGB5 framebuffer.

    0x0000 discards; 0x8000 is visible black and blends only with ABE.
    """
    words = np.asarray(words, dtype=np.uint16)
    front = np.stack([(words >> shift) & 31 for shift in (0, 5, 10)], -1).astype(np.int16)
    back = np.asarray(background, dtype=np.int16)
    if abr == 0:
        mixed = (back >> 1) + (front >> 1)
    elif abr == 1:
        mixed = back + front
    elif abr == 2:
        mixed = back - front
    elif abr == 3:
        mixed = back + (front >> 2)
    else:
        raise ValueError('ABR must be 0..3')
    result = np.where(((words & 0x8000) != 0)[..., None] & abe, np.clip(mixed, 0, 31), front)
    return np.where((words != 0)[..., None], result, back).astype(np.uint8)


def render(model, yaw=0, pitch=0, size=256, opaque=False, frame=None,
           pose=None, depth_offset=0):
    """Render a meshcheck.Model; `opaque` is a diagnostic ABE-off comparison."""
    xyz = model.tri_array(model.world(model.rest() if pose is None else pose))
    points = meshcheck._rotate(xyz, yaw, pitch)
    if frame is None:
        low, high = points[..., :2].reshape(-1, 2).min(0), points[..., :2].reshape(-1, 2).max(0)
        scale = (size - 24) / max(high - low)
        frame = scale, size / 2 - (low + high) / 2 * scale
    scale, offset = frame
    xy = points[..., :2] * scale + offset
    yy, xx = np.mgrid[:size, :size]
    checker = ((xx // 24 + yy // 24) % 2)[..., None]
    image = np.broadcast_to(np.where(checker, [7, 11, 14], [14, 17, 20]), (size, size, 3)).astype(np.uint8).copy()
    # libgs culls a whole primitive from its FIRST triangle. Quad AVSZ4
    # uses four distinct corners, not the diagonal counted twice. OT insertion
    # prepends packets: later primitives draw first within a depth bin.
    groups = {}
    for k, tri in enumerate(model.tris):
        groups.setdefault(tri[:3], []).append(k)
    visible = []
    for ordinal, (key, indices) in enumerate(groups.items()):
        first = xy[indices[0]]
        a, b = first[1]-first[0], first[2]-first[0]
        if a[0]*b[1]-a[1]*b[0] <= 1e-9:
            continue
        z = points[indices[0], :, 2]
        if len(indices) == 2:
            z = np.append(z, points[indices[1], 1, 2])
        bucket = int(np.floor((float(z.mean()) + depth_offset) / 4))
        visible.append((bucket, ordinal, indices))
    order = [k for _, _, indices in sorted(visible, reverse=True) for k in indices]
    for k in order:
        tri = model.tris[k]
        p = xy[k].copy()
        corner_order = [0, 1, 2]
        a, b = p[1] - p[0], p[2] - p[0]
        area = a[0] * b[1] - a[1] * b[0]
        if abs(area) <= 1e-9:
            continue
        if area < 0:  # GPU draws the second half even with opposite winding
            corner_order = [0, 2, 1]
            p = p[corner_order]
            area = -area
        lo = np.maximum(np.floor(p.min(0)).astype(int), 0)
        hi = np.minimum(np.ceil(p.max(0)).astype(int), size - 1)
        if np.any(hi < lo):
            continue
        x, y = np.meshgrid(np.arange(lo[0], hi[0] + 1) + .5, np.arange(lo[1], hi[1] + 1) + .5)
        edges = [(p[1], p[2]), (p[2], p[0]), (p[0], p[1])]
        weights, inside = [], np.ones(x.shape, bool)
        for a, b in edges:
            e = (b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0])
            top_left = b[1] < a[1] or (b[1] == a[1] and b[0] > a[0])
            inside &= (e > 1e-8) | ((np.abs(e) <= 1e-8) & top_left)
            weights.append(e / area)
        prim = model.m.tmd.objects[tri[1]].prims[tri[2]]
        decoded = prim.decode()
        if tri[4] is None:
            colors = decoded['colors']
            if len(colors) > 1:
                corners = [decoded['verts'].index(vi) for vi in tri[3]]
                rgb = np.asarray([colors[c][:3] for c in corners])[corner_order]
                rgb = np.einsum('ihw,ij->hwj', np.asarray(weights), rgb)
            else:
                rgb = np.broadcast_to(colors[0][:3], (*x.shape, 3))
            rgb = (rgb.clip(0,255).astype(np.uint16) >> 3)
            words = rgb[..., 0] | (rgb[..., 1] << 5) | (rgb[..., 2] << 10) | 0x8000
        else:
            uv = np.asarray(tri[4])[corner_order]
            texcoord = np.einsum('ihw,ij->hwj', np.asarray(weights), uv).astype(int)
            idx, palettes, _ = model.tex
            u, v = texcoord[..., 0].clip(0, idx.shape[1] - 1), texcoord[..., 1].clip(0, idx.shape[0] - 1)
            words = palettes[tri[5], idx[v, u]]
        abr = ((decoded['tsb'] or 0) >> 5) & 3
        sub = image[lo[1]:hi[1]+1, lo[0]:hi[0]+1]
        result = composite(sub, words, bool(prim.mode & 2) and not opaque, abr)
        sub[inside] = result[inside]
    return (image.astype(np.uint16) * 255 // 31).astype(np.uint8), frame
