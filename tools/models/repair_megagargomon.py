#!/usr/bin/env python3
"""Restore MegaGargomon's source head and backpack surfaces.

Authoring only: SOURCE is World 2003 M372SGRG.BIN. MODEL/TEXTURE are the
pinned imported base (edit.py get 335). Store OUT.MMD with edit.py put.
The player build needs only the resulting plain delta, not networkx.
"""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import mmd
import mmdport
import motionstorage
from tools.derive.importers.vendor.dw3.model import parse_model
from tools.models.repair_beelzemon import pair_triangles

# The import puts the torso (source bone 12) first. The remaining source
# indices retain their order. The deleted small polygons include the face
# plates and the rims of the rear vents.
RESTORED = {0: 12, 16: 17}


def restore(source_data, model_data, texture_data):
    source = parse_model(source_data)
    model = mmd.MMD.parse(model_data, 27)
    texture = mmd.Tim4(texture_data)
    assert len(source.bones) == len(model.tmd.objects) == 26
    cluts = sorted({tuple(p.material[3:5]) for b in source.bones for p in b.mesh.prims if p.uvs})
    # Reconstruct the original packing, including every face: dropped faces
    # still own their atlas pixels. Refuse another atlas rather than guessing.
    import dw3mmd
    pixels = source.texture[20:]
    page = [[(pixels[(y*256+x)//2] >> (4*(x%2))) & 15 for x in range(256)] for y in range(256)]
    by_bone, all_faces = {}, []
    for bone in source.bones:
        faces = []
        for p in bone.mesh.prims:
            assert p.uvs and p.normals and not p.state.get(0xe, 0)
            x, y = p.material[0] | p.material[1] << 8, p.material[2]
            face = dict(verts=list(p.verts), norms=list(p.normals),
                        uvs=[(x+u, y+v) for u, v in p.uvs],
                        row=cluts.index(tuple(p.material[3:5])), semi=False)
            faces.append(face)
            all_faces.append(face)
        by_bone[bone.index] = faces
    packed = dw3mmd.repack_page(all_faces, page, log=lambda *a: None)
    assert bytearray(packed.flatten()) == texture.idx, 'source atlas packing differs'
    bones = []
    for oi, obj in enumerate(model.tmd.objects):
        bone = dict(parent=-1, offset=(0, 0, 0), rest=mmdport.IDENTITY_Q,
                    verts=[v[:3] for v in model.tmd.obj_verts(oi)],
                    norms=[v[:3] for v in model.tmd.obj_norms(oi)[:obj.nnorm]], prims=[])
        if oi in RESTORED:
            src = source.bones[RESTORED[oi]-1]
            assert len(src.mesh.vertices) == obj.nvert
            scale = 1.177186439124536
            assert max(abs(a[c]-round(round(b[c]*.084715)*scale))
                       for a, b in zip(bone['verts'], src.mesh.vertices) for c in range(3)) <= 1
            bone['norms'] = src.mesh.normals
            bone['prims'] = by_bone[src.index]
        else:
            for p in obj.prims:
                d = p.decode()
                bone['prims'].append(dict(verts=d['verts'], norms=d['norms'], uvs=d['uv'],
                                          row=(d['cba'] >> 6)-488, semi=bool(p.mode & 2)))
        if oi in RESTORED:
            pair_triangles(bone)
        bones.append(bone)
    # The native maximum of 713 primitives is an importer target, not an
    # engine array bound. Keep the limbs exact instead of deleting surfaces
    # to recover that count; the resident/cold limits still apply.
    mesh = mmdport.Model('MegaGargomon', bones, texture.idx, texture.pal, {})
    model.tmd = mmdport.build_tmd(mesh)
    assert sum(len(o.prims) for o in model.tmd.objects) <= 778
    assert max(o.nvert for o in model.tmd.objects) <= 172
    assert model.anims.build() == mmd.MMD.parse(model_data, 27).anims.build()
    result = model.build()
    motionstorage.require(result, 27)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'model', 'texture', 'out'):
        ap.add_argument(name, type=Path)
    args = ap.parse_args()
    args.out.write_bytes(restore(args.source.read_bytes(), args.model.read_bytes(), args.texture.read_bytes()))


if __name__ == '__main__':
    main()
