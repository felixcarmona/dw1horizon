#!/usr/bin/env python3
"""Restore WarGrowlmon's complete source head without increasing model budgets.

Authoring only (NumPy and NetworkX): SOURCE.BIN SHIPPED.MMD TEXTURE.TIM OUT.MMD.
SHIPPED must include the reviewed chibi overlay. Store OUT with edit.py put
after disabling that overlay: its complete performance is already baked here.
"""
import argparse
import copy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT),str(ROOT/'tools')]
import numpy as np
import mmd
import mmdport
import meshfix
import motionstorage
import dw3mmd
import dw3_extra
from tools.derive.importers.vendor.dw3 import model as source_model
from tools.models.repair_beelzemon import pair_triangles

HEAD, SOURCE_HEAD, BONES = 18, 19, 27


def full_head(source_data,model_data,texture_data):
    previous = source_model.sections_of
    try:
        source_model.sections_of = dw3_extra.sections_of
        source = source_model.parse_model(source_data)
    finally:
        source_model.sections_of = previous
    model = mmd.MMD.parse(model_data,BONES)
    texture = mmd.Tim4(texture_data)
    if len(source.bones) != 26 or len(model.tmd.objects) != 26:
        raise ValueError('WarGrowlmon source/target rig differs')
    cluts = sorted({tuple(p.material[3:5]) for b in source.bones for p in b.mesh.prims if p.uvs})
    pixels = source.texture[20:]
    page = [[(pixels[(y*256+x)//2] >> (4*(x%2))) & 15 for x in range(256)] for y in range(256)]
    faces,head = [],[]
    for bone in source.bones:
        for p in bone.mesh.prims:
            if not p.uvs or not p.normals:
                raise ValueError('unexpected untextured source primitive')
            x,y = p.material[0] | p.material[1]<<8,p.material[2]
            face = dict(verts=list(p.verts),norms=list(p.normals),uvs=[(x+u,y+v) for u,v in p.uvs],
                        row=cluts.index(tuple(p.material[3:5])),semi=bool(p.state.get(0xe,0)))
            faces.append(face)
            if bone.index == SOURCE_HEAD:
                head.append(face)
    packed = dw3mmd.repack_page(faces,page,log=lambda *a:None)
    if bytearray(packed.flatten()) != texture.idx:
        raise ValueError('source atlas differs from the reviewed texture')
    src = source.bones[SOURCE_HEAD-1].mesh
    head_bone = dict(parent=-1,offset=(0,0,0),rest=mmdport.IDENTITY_Q,
                     verts=src.vertices,norms=src.normals,prims=head)
    dw3mmd.merge_normals(head_bone,4)
    tmd = mmdport.build_tmd(mmdport.Model('head',[head_bone],None,None,{}),log=lambda *a:None)
    # Proportions and the final uniform resize transform coordinates, never
    # reorder this vertex pool. Refuse other topology rather than guessing.
    x = np.asarray([v[:3] for v in tmd.obj_verts(0)],float)
    y = np.asarray([v[:3] for v in model.tmd.obj_verts(HEAD)],float)
    if x.shape != y.shape:
        raise ValueError('source head vertex pool differs')
    design = np.column_stack([x,np.ones(len(x))])
    transform,_,rank,_ = np.linalg.lstsq(design,y,rcond=None)
    if rank != 4 or np.max(np.linalg.norm(design@transform-y,axis=1)) > 3:
        raise ValueError('head does not match the reviewed proportion bake')
    return tmd


def restore(source_data,model_data,texture_data):
    head = full_head(source_data,model_data,texture_data)
    model = mmd.MMD.parse(model_data,BONES)
    acting = model.anims.build()
    texture = mmd.Tim4(texture_data)
    bones = []
    for oi,obj in enumerate(model.tmd.objects):
        bone = dict(parent=-1,offset=(0,0,0),rest=mmdport.IDENTITY_Q,
                    verts=[v[:3] for v in model.tmd.obj_verts(oi)],
                    norms=[v[:3] for v in model.tmd.obj_norms(oi)[:obj.nnorm]],prims=[])
        if oi == HEAD:
            bone['norms'] = [v[:3] for v in head.obj_norms(0)[:head.objects[0].nnorm]]
        for p in (head.objects[0].prims if oi == HEAD else obj.prims):
            d = p.decode()
            bone['prims'].append(dict(verts=d['verts'],norms=d['norms'],uvs=d['uv'],
                                      row=(d['cba']>>6)-488,semi=bool(p.mode&2)))
        pair_triangles(bone)
        bones.append(bone)
    # Maximum exact pairing recovers almost all the head's storage. Fit only
    # broad torso panels for the final four slots; keep all six extent anchors.
    total = sum(len(b['prims']) for b in bones)
    if total > 713:
        torso = bones[0]
        referenced = [torso['verts'][i] for p in torso['prims'] for i in p['verts']]
        torso['pinned_positions'] = [extreme(referenced,key=lambda v:v[k])
                                     for k in range(3) for extreme in (min,max)]
        small = mmdport.Model('torso',[torso],texture.idx,texture.pal,{})
        meshfix.decimate(small,len(torso['prims'])-(total-713),quad_angle=89,log=lambda *a:None)
    mesh = mmdport.Model('WarGrowlmon',bones,texture.idx,texture.pal,{})
    if meshfix.prim_count(mesh) > 713:
        raise ValueError('restored head exceeds the primitive budget')
    model.tmd = mmdport.build_tmd(mesh,log=lambda *a:None)
    if max(o.nvert for o in model.tmd.objects) > 172 or model.anims.build() != acting:
        raise ValueError('vertex or animation invariant failed')
    result = model.build()
    motionstorage.require(result,BONES)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('source','model','texture','out'):
        p.add_argument(name,type=Path)
    a = p.parse_args()
    a.out.write_bytes(restore(a.source.read_bytes(),a.model.read_bytes(),a.texture.read_bytes()))


if __name__ == '__main__':
    main()
