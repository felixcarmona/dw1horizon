"""Render both OT phases from one raster preparation, with packet provenance.

The arithmetic and rules mirror psx_blend.render. Tests compare the complete
RGB buffers with that reference, including transparency, blend state and GPU
quad culling. This is an offline evidence optimization, not a runtime change.
"""
import math
import numpy as np
from tools.models import meshcheck as MC, psx_blend


def phases(model, yaw, pitch, size=160, pose=None, frame=None):
    points = MC._rotate(model.tri_array(model.world(model.rest() if pose is None else pose)), yaw, pitch)
    if frame is None:
        low, high = points[..., :2].reshape(-1, 2).min(0), points[..., :2].reshape(-1, 2).max(0)
        scale = (size-24)/max(high-low)
        frame = scale, size/2-(low+high)/2*scale
    scale, offset = frame
    xy = points[..., :2]*scale+offset
    yy, xx = np.mgrid[:size, :size]
    checker = ((xx//24+yy//24)%2)[..., None]
    background = np.broadcast_to(np.where(checker, [7, 11, 14], [14, 17, 20]), (size, size, 3)).astype(np.uint8)
    groups = {}
    for k, tri in enumerate(model.tris):
        groups.setdefault(tri[:3], []).append(k)
    packets, conservative = [], set()
    for ordinal, (key, indices) in enumerate(groups.items()):
        first = xy[indices[0]]
        a, b = first[1]-first[0], first[2]-first[0]
        if a[0]*b[1]-a[1]*b[0] <= 1e-9:
            continue
        z = points[indices[0], :, 2]
        if len(indices) == 2:
            z = np.append(z, points[indices[1], 1, 2])
        draws = []
        for k in indices:
            tri = model.tris[k]
            p = xy[k].copy()
            corner_order = [0, 1, 2]
            a, b = p[1]-p[0], p[2]-p[0]
            area = a[0]*b[1]-a[1]*b[0]
            if abs(area) <= 1e-9:
                continue
            if area < 0:
                corner_order = [0, 2, 1]
                p = p[corner_order]
                area = -area
            lo = np.maximum(np.floor(p.min(0)).astype(int), 0)
            hi = np.minimum(np.ceil(p.max(0)).astype(int), size-1)
            if np.any(hi < lo):
                conservative.add(key)  # never prune out-of-frame surfaces
                continue
            if (p < 0).any() or (p >= size).any():
                conservative.add(key)
            px, py = np.meshgrid(np.arange(lo[0], hi[0]+1), np.arange(lo[1], hi[1]+1))
            x, y = px+.5, py+.5
            weights, inside = [], np.ones(x.shape, bool)
            for a, b in ((p[1], p[2]), (p[2], p[0]), (p[0], p[1])):
                edge = (b[0]-a[0])*(y-a[1])-(b[1]-a[1])*(x-a[0])
                top_left = b[1] < a[1] or (b[1] == a[1] and b[0] > a[0])
                inside &= (edge > 1e-8) | ((np.abs(edge) <= 1e-8) & top_left)
                weights.append(edge/area)
            prim = model.m.tmd.objects[tri[1]].prims[tri[2]]
            d = prim.decode()
            if tri[4] is None:
                colors = d['colors']
                if len(colors) > 1:
                    corners = [d['verts'].index(vi) for vi in tri[3]]
                    rgb = np.asarray([colors[c][:3] for c in corners])[corner_order]
                    rgb = np.einsum('ihw,ij->hwj', np.asarray(weights), rgb)
                else:
                    rgb = np.broadcast_to(colors[0][:3], (*x.shape, 3))
                rgb = rgb.clip(0, 255).astype(np.uint16) >> 3
                words = rgb[..., 0] | (rgb[..., 1] << 5) | (rgb[..., 2] << 10) | 0x8000
            else:
                uv = np.asarray(tri[4])[corner_order]
                texcoord = np.einsum('ihw,ij->hwj', np.asarray(weights), uv).astype(int)
                texels, palettes, _ = model.tex
                u = texcoord[..., 0].clip(0, texels.shape[1]-1)
                v = texcoord[..., 1].clip(0, texels.shape[0]-1)
                words = palettes[tri[5], texels[v, u]]
            valid = inside & (words != 0)
            abe, abr = bool(prim.mode & 2), ((d['tsb'] or 0) >> 5) & 3
            draws.append((py[valid]*size+px[valid], words[valid], abe, abr))
        packets.append((float(z.mean()), ordinal, key, draws))
    images, visible = [], set(conservative)
    for phase in (0, 2):
        image = background.copy().reshape(-1, 3)
        ids = np.full(size*size, -1, np.int16)
        keys = {p[1]:p[2] for p in packets}
        order = sorted(packets, key=lambda p:(int(math.floor((p[0]+phase)/4)), p[1]), reverse=True)
        for _, ordinal, key, draws in order:
            for pixels, words, abe, abr in draws:
                image[pixels] = psx_blend.composite(image[pixels], words, abe, abr)
                blended = abe & ((words & 0x8000) != 0)
                if blended.any():
                    visible.add(key)  # conservatively retain later-occluded ABE packets
                ids[pixels[~blended]] = ordinal
        visible.update(keys[i] for i in np.unique(ids) if i >= 0)
        images.append((image.reshape(size, size, 3).astype(np.uint16)*255//31).astype(np.uint8))
    return images, frame, visible
