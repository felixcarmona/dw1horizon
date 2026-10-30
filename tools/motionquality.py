#!/usr/bin/env python3
"""Triangle crossing diagnostics for reviewed mesh parts and material regions.
Not a complete collision detector: excludes coplanar cases and touching seams.
"""
import numeric as np
import motionlab as M
pairs=[(hand,other) for hand in [7,10] for other in [1,2,3,16,19]]+[(6,1),(6,2),(9,1),(9,2),(16,19)]+[(tail,leg) for tail in [11,12,13] for leg in [14,15,16,17,18,19]]
def edges_cross(a,b):
 a,b=np.asarray(a),np.asarray(b)
 # Non-coplanar segment/triangle crossings. Strict segment interior excludes touching seams.
 for edge in range(3):
  origin=a[edge];direction=a[(edge+1)%3]-origin
  e1=b[:,1]-b[:,0];e2=b[:,2]-b[:,0];h=np.cross(direction,e2);det=np.einsum('ij,ij->i',e1,h)
  ok=np.abs(det)>1e-8;f=np.zeros_like(det);f[ok]=1/det[ok]
  s=origin-b[:,0];u=f*np.einsum('ij,ij->i',s,h);q=np.cross(s,e1);v=f*(q@direction);t=f*np.einsum('ij,ij->i',e2,q)
  if np.any(ok&(u>.001)&(v>.001)&(u+v<.999)&(t>.02)&(t<.98)):return True
 return False
def collide(A,B):
 A,B=np.asarray(A),np.asarray(B)
 # Cache per-triangle bounds once per pair; edge tests and tolerances stay exact.
 amin=A.min(1);amax=A.max(1);bmin=B.min(1);bmax=B.max(1)
 alo=amin.min(0);ahi=amax.max(0);blo=bmin.min(0);bhi=bmax.max(0)
 if np.any(ahi<blo) or np.any(bhi<alo):return False
 for i in np.flatnonzero(np.all(amax>=blo,axis=1)&np.all(amin<=bhi,axis=1)):
  mask=np.all(bmax>=amin[i],axis=1)&np.all(bmin<=amax[i],axis=1)
  if np.any(mask) and edges_cross(A[i],B[mask]):return True
 for i in np.flatnonzero(np.all(bmax>=alo,axis=1)&np.all(bmin<=ahi,axis=1)):
  mask=np.all(amax>=bmin[i],axis=1)&np.all(amin<=bmax[i],axis=1)
  if np.any(mask) and edges_cross(B[i],A[mask]):return True
 return False

class TriangleRegions(dict):
    def __init__(self):
        super().__init__();self.bone_for={}

def local_triangles(mod,skel,regions=None):
    local=TriangleRegions()
    for bone,(oi,_) in enumerate(skel):
        if oi<0:continue
        verts=np.array(mod.tmd.obj_verts(oi))[:,:3];tris=[]
        for prim in mod.tmd.objects[oi].prims:
            v=prim.decode()['verts'];tris.append(verts[v[:3]])
            if len(v)==4:tris.append(verts[[v[1],v[3],v[2]]])
        local[bone]=np.array(tris)
    for name,region in (regions or {}).items():
        bone=region['bone'];palettes=region['palettes']
        if not isinstance(name,str) or not name or name in local or type(bone) is not int or not 0<bone<len(skel):
            raise ValueError('invalid collision region identity')
        if not palettes or any(type(p) is not int or not 0<=p<16 for p in palettes):raise ValueError('invalid collision region palettes')
        oi=skel[bone][0]
        if oi<0:raise ValueError('collision region lacks a mesh')
        verts=np.array(mod.tmd.obj_verts(oi))[:,:3];tris=[]
        for prim in mod.tmd.objects[oi].prims:
            d=prim.decode();pal=((d.get('cba',0)>>6)-488) if d.get('cba') else 0
            if not d.get('uv') or pal not in palettes:continue
            v=d['verts'];tris.append(verts[v[:3]])
            if len(v)==4:tris.append(verts[[v[1],v[3],v[2]]])
        if not tris:raise ValueError('collision region selects no triangles')
        local[name]=np.array(tris);local.bone_for[name]=bone
    return local

def crossings(mod,local,poses,checked_pairs=None):
    hits={}
    for t,p in enumerate(poses):
        W=M.mmd.bone_matrices(mod,p)
        world={}
        for b,tris in local.items():
            bone=getattr(local,'bone_for',{}).get(b,b)
            world[b]=tris@np.array(W[bone])[:3,:3].T+np.array(W[bone])[:3,3]
        for a,b in (pairs if checked_pairs is None else checked_pairs):
            if collide(world[a],world[b]):hits.setdefault(f'{a}-{b}',[]).append(t)
    return hits
