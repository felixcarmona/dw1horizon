#!/usr/bin/env python3
"""Restore Beelzemon's source helmet, wing tips and belts, with green Blast Mode irises.

Authoring only (requires networkx): SOURCE.BIN MODEL.MMD TEXTURE.TIM IMPORT.MMD OUT.
MODEL is the DW1-proportioned model; IMPORT is the pinned raw importer output.
The player build replays plain deltas and needs no authoring dependencies.
"""
import argparse
import copy
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import mmd
import mmdport
import dw3_extra
import dw3mmd
import motionstorage
import meshfix
from tools.derive.importers.vendor.dw3 import model as source_model
from tools.models.field_animations import chibi

# TMD objects: four belt sections, six wing sections, and the complete head.
RESTORED = frozenset([11, 12, 13, 14, 22, 23, 24, 25, 26, 27, 28])
# The importer makes the torso (source bone 15) the root. Bone 19 is a hidden effect.
BODY_PANELS = frozenset([0, 1, 2, 6, 7])
SOURCE_ORDER = [15, *range(1, 15), 16, 17, 18, *range(20, 31)]
PATCHES = [(120, 80, 0, 30, 24), (176, 0, 30, 48, 24), (32, 144, 86, 16, 24)]


def source_mesh(source_data, imported_data, texture_data):
    """Full source parts with the existing DW1 proportion bake and texture layout."""
    # Empty section-table slots must not truncate the preceding mesh or animation.
    previous = source_model.sections_of
    try:
        source_model.sections_of = dw3_extra.sections_of
        source = source_model.parse_model(source_data)
    finally:
        source_model.sections_of = previous
    assert sum(len(b.mesh.prims) for b in source.bones) == 905
    imported = mmd.MMD.parse(imported_data, 31)
    imported.type = 403
    rig = chibi.Rig(imported, mmd.exe().skeleton[403])
    row = json.loads((ROOT / 'content/models/imports/chibi.json').read_text())['403']
    groups = [row['groups'].get(str(b), 'other') for b in range(31)]
    feet = [b for b in range(31) if groups[b] in ('foot', 'footpart', 'shin', 'thigh', 'hipjoint')]
    standing = rig.bounds(feet)[1]
    scales = chibi.bone_scales(rig, groups, row['factors'], row['fit'])
    chibi._bake(rig, scales)
    top, floor = rig.bounds(feet)
    factor = (row['height'] + standing) / (top + floor)
    unit_scale = json.loads((ROOT / 'content/imports/specs/Beelzemon.json').read_text())['scale']

    cluts = sorted({tuple(p.material[3:5]) for b in source.bones for p in b.mesh.prims if p.uvs})
    pixels = source.texture[20:]
    page = [[(pixels[(y * 256 + x) // 2] >> (4 * (x % 2))) & 15 for x in range(256)] for y in range(256)]
    prims, all_prims = {}, []
    for bone in source.bones:
        prims[bone.index] = []
        for p in bone.mesh.prims:
            assert p.uvs and p.normals
            x, y = p.material[0] | p.material[1] << 8, p.material[2]
            face = dict(verts=list(p.verts), norms=list(p.normals), uvs=[(x + u, y + v) for u, v in p.uvs],
                        row=cluts.index(tuple(p.material[3:5])), semi=False)
            prims[bone.index].append(face)
            all_prims.append(face)
    packed = dw3mmd.repack_page(all_prims, page, log=lambda *a: None)
    texture = mmd.Tim4(texture_data)
    texture.idx = bytearray(packed.flatten())
    # Keep the original full-resolution face patches and isolate only iris shades.
    for p, face in zip(source.bones[27].mesh.prims, prims[28]):
        x, y = p.material[0] | p.material[1] << 8, p.material[2]
        if face['row'] == 2:
            assert (x, y) == (120, 80)
            face['uvs'] = list(p.uvs)
        elif face['row'] == 5 and (x, y) in ((176, 0), (32, 144)):
            dx = 30 if x == 176 else 86
            face['uvs'] = [(dx + u, v) for u, v in p.uvs]
            face['row'] = 11
    for sx, sy, dx, width, height in PATCHES:
        for y in range(height):
            for x in range(width):
                texture.idx[y * 256 + dx + x] = page[sy + y][sx + x]
    texture.pal[11] = list(texture.pal[5])
    for index in (0, 1):
        c = texture.pal[11][index]
        texture.pal[11][index] = (c & 0xFC00) | ((c & 31) << 5) | ((c >> 5) & 31)

    bones = []
    skeleton = mmd.exe().skeleton[403]
    for oi, si in enumerate(SOURCE_ORDER):
        source_bone = source.bones[si - 1]
        bi = next(i for i, (obj, _) in enumerate(skeleton) if obj == oi)
        matrix, anchor = scales.get(bi, (chibi._diagonal(1), [0, 0, 0]))
        verts = []
        for vertex in source_bone.mesh.vertices:
            v = [round(c * unit_scale) - a for c, a in zip(vertex, anchor)]
            v = chibi._apply(matrix, v)
            verts.append(tuple(round(round(c + a) * factor) for c, a in zip(v, anchor)))
        bones.append(dict(parent=-1, offset=(0, 0, 0), rest=mmdport.IDENTITY_Q, verts=verts,
                          norms=list(source_bone.mesh.normals), prims=prims[si]))
    return bones, texture


def pair_triangles(bone):
    """Maximum pairing: same diagonal, shared UVs/normals, material and winding.

    Existing quads are preferred. New convex pairs may span up to 89 degrees; no triangle, vertex, UV or normal is discarded.
    """
    import networkx as nx
    triangles = []
    for pi, p in enumerate(bone['prims']):
        for indices in [(0, 1, 2)] + ([(1, 3, 2)] if len(p['verts']) == 4 else []):
            face = copy.deepcopy(p)
            for field in ('verts', 'norms', 'uvs'):
                face[field] = [p[field][i] for i in indices]
            face['parent_prim'] = pi
            triangles.append(face)

    def normal(face):
        a, b, c = [bone['verts'][v] for v in face['verts']]
        u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
        n = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
        length = math.sqrt(sum(c*c for c in n)) or 1
        return [c / length for c in n]

    normals = [normal(p) for p in triangles]
    graph = nx.Graph()
    graph.add_nodes_from(range(len(triangles)))
    orders = {}
    for i, p in enumerate(triangles):
        for j in range(i):
            q = triangles[j]
            common = set(p['verts']) & set(q['verts'])
            if len(common) != 2 or (p['row'], p.get('semi')) != (q['row'], q.get('semi')):
                continue
            if any(p['uvs'][p['verts'].index(v)] != q['uvs'][q['verts'].index(v)] or
                   bone['norms'][p['norms'][p['verts'].index(v)]] != bone['norms'][q['norms'][q['verts'].index(v)]]
                   for v in common):
                continue
            same = p['parent_prim'] == q['parent_prim']
            if not same and sum(a*b for a, b in zip(normals[i], normals[j])) < math.cos(math.radians(89)):
                continue
            a = next(k for k, v in enumerate(p['verts']) if v not in common)
            b, c = (a + 1) % 3, (a + 2) % 3
            if (q['verts'].index(p['verts'][c]) + 1) % 3 != q['verts'].index(p['verts'][b]):
                continue
            d = next(k for k, v in enumerate(q['verts']) if v not in common)
            if not same:
                points = [bone['verts'][v] for v in (p['verts'][a], p['verts'][b], p['verts'][c], q['verts'][d])]
                def side(x, y, z):
                    u = [y[k] - x[k] for k in range(3)]
                    v = [z[k] - x[k] for k in range(3)]
                    cross = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
                    return sum(x*y for x, y in zip(cross, normals[i]))
                aa, bb, cc, dd = points
                if side(bb, cc, aa) * side(bb, cc, dd) >= 0 or side(aa, dd, bb) * side(aa, dd, cc) >= 0:
                    continue
            graph.add_edge(i, j, weight=10000 if same else 1)
            orders[j, i] = a, b, c, d
    used, out = set(), []
    matches = nx.max_weight_matching(graph, maxcardinality=True)
    for j, i in sorted(tuple(sorted(edge)) for edge in matches):
        p, q = triangles[i], triangles[j]
        a, b, c, d = orders[j, i]
        face = copy.deepcopy(p)
        for field in ('verts', 'norms', 'uvs'):
            face[field] = [p[field][a], p[field][b], p[field][c], q[field][d]]
        out.append(face)
        used.update((i, j))
    bone['prims'] = out + [p for i, p in enumerate(triangles) if i not in used]


def restore(model_data, texture_data, source_data, imported_data):
    model = mmd.MMD.parse(model_data, 31)
    bones, texture = source_mesh(source_data, imported_data, texture_data)
    for oi, bone in enumerate(bones):
        if oi not in RESTORED:
            obj = model.tmd.objects[oi]
            bone['verts'] = [v[:3] for v in model.tmd.obj_verts(oi)]
            bone['norms'] = [v[:3] for v in model.tmd.obj_norms(oi)[:obj.nnorm]]
            bone['prims'] = []
            for prim in obj.prims:
                face = prim.decode()
                bone['prims'].append(dict(verts=face['verts'], norms=face['norms'], uvs=face['uv'],
                                          row=(face['cba'] >> 6) - 488, semi=bool(face['mode'] & 2)))
        pair_triangles(bone)
        # Remove only unreferenced pool entries, keeping every referenced value.
        for field in ('verts', 'norms'):
            used = sorted({v for p in bone['prims'] for v in p[field]})
            remap = {v: i for i, v in enumerate(used)}
            bone[field] = [bone[field][v] for v in used]
            for p in bone['prims']:
                p[field] = [remap[v] for v in p[field]]
    # All silhouette details are protected. Fit only the broad existing body and leg panels.
    mesh = mmdport.Model('Beelzemon', bones, texture.idx, texture.pal, {})
    count = sum(len(b['prims']) for b in bones)
    if count > 713:
        protected = {i: b['prims'] for i, b in enumerate(bones) if i not in BODY_PANELS}
        for i in protected:
            bones[i]['prims'] = []
        budget = 713 - sum(len(ps) for ps in protected.values())
        # Keep the six local extent landmarks: the DW1 proportion bake stays fixed.
        for i in BODY_PANELS:
            vs = bones[i]['verts']
            bones[i]['pinned_positions'] = [select(vs, key=lambda v: v[axis])
                                            for axis in range(3) for select in (min, max)]
        meshfix.decimate(mesh, budget, kappa=3, kmove=3, quad_angle=40, log=lambda *a: None)
        for i, ps in protected.items():
            bones[i]['prims'] = ps
    model.tmd = mmdport.build_tmd(mesh)
    count = sum(len(o.prims) for o in model.tmd.objects)
    assert count <= 713, f'primitive budget: {count} > 713'
    assert max(o.nvert for o in model.tmd.objects) <= 172
    assert model.anims.build() == mmd.MMD.parse(model_data, 31).anims.build()
    result = model.build()
    motionstorage.require(result, 31)
    return result, texture.to_bytes()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'model', 'texture', 'imported', 'out'):
        p.add_argument(name, type=Path)
    a = p.parse_args()
    model, texture = restore(a.model.read_bytes(), a.texture.read_bytes(), a.source.read_bytes(), a.imported.read_bytes())
    a.out.with_suffix('.MMD').write_bytes(model)
    a.out.with_suffix('.TIM').write_bytes(texture)


if __name__ == '__main__':
    main()
