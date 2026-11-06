#!/usr/bin/env python3
"""Restore the source face and recolor Beelzemon Blast Mode irises green.

Authoring only: SOURCE.BIN MODEL.MMD TEXTURE.TIM OUT_STEM. Store with
 tools/models/edit.py put 403 OUT_STEM.MMD OUT_STEM.TIM.
The player build replays the pinned plain deltas.
"""
import argparse
import copy
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import mmd
from tools.derive.importers.vendor.dw3.model import parse_model


def restore(model_data, texture_data, source_data):
    model = mmd.MMD.parse(model_data, 31)
    texture = mmd.Tim4(texture_data)
    source = parse_model(source_data)
    head = model.tmd.objects[26]
    # Repack five pairs of adjacent triangles as quads with the same diagonal.
    # This preserves every triangle and silhouette while freeing six slots.
    pairs = [(16, 14, 15, [2, 0, 1, 0]), (22, 7, 10, [2, 0, 1, 1]),
             (27, 6, 8, [0, 1, 2, 0]), (27, 7, 10, [2, 0, 1, 0]),
             (26, 50, 51, [2, 0, 1, 2]), (0, 76, 77, [1, 2, 0, 1])]
    for oi in sorted({oi for oi, *_ in pairs}):
        obj = model.tmd.objects[oi]
        replacements, dropped = {}, set()
        for ob, i, j, order in pairs:
            if ob != oi:
                continue
            a, b = obj.prims[i].decode(), obj.prims[j].decode()
            a['mode'] |= 8
            a.pop('olen')
            for field in ('verts', 'uv', 'norms'):
                if len(a[field]) == 3:
                    a[field] = [a[field][k] for k in order[:3]] + [b[field][order[3]]]
            replacements[i] = mmd.Prim.encode(a)
            dropped.add(j)
        obj.prims = [replacements.get(i, p) for i, p in enumerate(obj.prims) if i not in dropped]
    old = list(head.prims)
    removed = set()
    # Remove the three collapsed jaw surfaces. Restore all eight source faces.
    removed.update([0, 28, 31])
    assert all((old[i].decode()['cba'] >> 6) - 488 == 2 for i in [0, 28, 31])
    head.prims = [p for i, p in enumerate(old) if i not in removed]
    verts = list(model.tmd.obj_verts(26))
    norms = list(model.tmd.norms[head.norm_start:head.norm_start + head.nnorm])
    source_head = source.bones[27].mesh
    # Fit the existing enlarged head, including its rounded attachment points.
    scale = 0.315
    vertex_map = {}
    for i in sorted({v for j in [0, 1, 66, 67, 68, 69, 70, 71] for v in source_head.prims[j].verts}):
        xyz = tuple(round(v * scale) for v in source_head.vertices[i])
        nearest = min(range(len(verts)), key=lambda k: sum((verts[k][c] - xyz[c]) ** 2 for c in range(3)))
        if sum((verts[nearest][c] - xyz[c]) ** 2 for c in range(3)) <= 9:
            vertex_map[i] = nearest
        else:
            vertex_map[i] = len(verts)
            verts.append((*xyz, 0))
    template = old[31].decode()
    for i in [0, 1, 66, 67, 68, 69, 70, 71]:
        p = source_head.prims[i]
        face = copy.deepcopy(template)
        face.pop('olen')
        face['mode'] = (face['mode'] & ~8) | (8 if len(p.verts) == 4 else 0)
        face['verts'] = [vertex_map[v] for v in p.verts]
        face['uv'] = list(p.uvs)
        face['norms'] = []
        for n in p.normals:
            normal = (*source_head.normals[n], 0)
            if normal not in norms:
                norms.append(normal)
            face['norms'].append(norms.index(normal))
        head.prims.append(mmd.Prim.encode(face))
    # Unoccupied atlas rectangles: jaw 30x24 at (0,0), eyes 48x24 at (30,0), forehead eye 16x24 at (86,0).
    # Full source pixels avoid losing the lip and pupil at the old 2/3 packing.
    for obj in model.tmd.objects:
        for prim in obj.prims:
            if prim in head.prims[-8:]:
                continue
            uv = prim.decode()['uv']
            for x, width in [(0, 30), (30, 48), (86, 16)]:
                assert not uv or min(v for u, v in uv) >= 24 or max(u for u, v in uv) < x or min(u for u, v in uv) >= x + width
    pixels = source.texture[20:]
    assert tuple(texture.pal[2]) == struct.unpack_from('<16H', pixels, 248 * 128)
    assert tuple(texture.pal[5]) == struct.unpack_from('<16H', pixels, 248 * 128 + 16 * 2)
    for sx, sy, dx, w, h in [(120, 80, 0, 30, 24), (176, 0, 30, 48, 24), (32, 144, 86, 16, 24)]:
        for y in range(h):
            for x in range(w):
                n = (sy + y) * 256 + sx + x
                texture.idx[y * 256 + dx + x] = (pixels[n // 2] >> (4 * (n % 2))) & 15
    # Isolate the eye palette. Swap red/green only for the two iris shades;
    # the original gold highlights, eyelids and helmet colors remain exact.
    assert not any(texture.pal[11])
    texture.pal[11] = list(texture.pal[5])
    for index in (0, 1):
        r, g, b, alpha = mmd.c15_to_rgba(texture.pal[5][index])
        texture.pal[11][index] = mmd.rgba_to_c15(g, r, b, alpha)
    eyes = 0
    for i, prim in enumerate(head.prims):
        face = prim.decode()
        if (face['cba'] >> 6) - 488 == 5 and all(67 <= u <= 99 and 89 <= v <= 105 for u, v in face['uv']):
            face['uv'] = [(30 + round((u - 67) * 47 / 32), round((v - 89) * 23 / 16)) for u, v in face['uv']]
            face['cba'] = (488 + 11) << 6
            head.prims[i] = mmd.Prim.encode(face)
            eyes += 1
    # The source forehead eye was completely collapsed by simplification.
    # Restore its two source triangles as one quad over the retained helmet.
    # The shared diagonal, UVs and local vertex positions come from DW3.
    forehead = copy.deepcopy(template)
    forehead.pop('olen')
    forehead['mode'] |= 8
    forehead['cba'] = (488 + 11) << 6
    forehead['verts'], forehead['norms'] = [], []
    for v, n in zip([28, 26, 27, 20], [source_head.prims[26].normals[1],
                                     source_head.prims[26].normals[2],
                                     source_head.prims[26].normals[0],
                                     source_head.prims[25].normals[2]]):
        xyz = tuple(round(c * scale) for c in source_head.vertices[v])
        nearest = min(range(len(verts)), key=lambda k: sum((verts[k][c] - xyz[c]) ** 2 for c in range(3)))
        if sum((verts[nearest][c] - xyz[c]) ** 2 for c in range(3)) > 9:
            nearest = len(verts)
            verts.append((*xyz, 0))
        forehead['verts'].append(nearest)
        normal = (*source_head.normals[n], 0)
        if normal not in norms:
            norms.append(normal)
        forehead['norms'].append(norms.index(normal))
    forehead['uv'] = [(94, 0), (101, 12), (86, 12), (94, 23)]
    head.prims.append(mmd.Prim.encode(forehead))
    # Rebuild pools so every other object's local vertex/normal indices stay exact.
    vp, np = [], []
    for i, obj in enumerate(model.tmd.objects):
        vs = verts if i == 26 else list(model.tmd.obj_verts(i))
        ns = norms if i == 26 else list(model.tmd.norms[obj.norm_start:obj.norm_start + obj.nnorm])
        obj.vert_start, obj.norm_start = len(vp), len(np)
        obj.nvert, obj.nnorm = len(vs), len(ns)
        vp.extend(vs)
        np.extend(ns)
    model.tmd.verts, model.tmd.norms = vp, np
    assert eyes == 6
    assert sum(len(o.prims) for o in model.tmd.objects) == 713
    assert model.anims.build() == mmd.MMD.parse(model_data, 31).anims.build()
    return model.build(), texture.to_bytes()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'model', 'texture', 'out'):
        p.add_argument(name, type=Path)
    a = p.parse_args()
    model, texture = restore(a.model.read_bytes(), a.texture.read_bytes(), a.source.read_bytes())
    a.out.with_suffix('.MMD').write_bytes(model)
    a.out.with_suffix('.TIM').write_bytes(texture)


if __name__ == '__main__':
    main()
