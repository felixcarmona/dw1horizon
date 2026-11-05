"""Bind DCB MagnaAngemon geometry to native Angemon's rig and animation set.

Developer-only authoring: no motion curves are synthesized or retargeted.
The player replays a plain delta against the DCB import and native ANGE.MMD.
"""
import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path

import numpy as np
import mmd
import animsheet
import retarget

SPEC = Path('content/imports/specs/MagnaAngemon.json')

def unit(v):return v/np.linalg.norm(v)
def align(a,b):return np.array(retarget.swing(a.tolist(),b.tolist()))
def cloud(model,b,w):
    obj=mmd.exe().skeleton[model.type][b][0]
    return np.array(model.tmd.obj_verts(obj))[:,:3]@w[b,:3,:3].T

def envelope(points, template):
    planes=[]
    for ia,ib,ic in itertools.combinations(range(len(template)),3):
        normal=np.cross(template[ib]-template[ia],template[ic]-template[ia])
        if np.linalg.norm(normal)<1e-6:continue
        normal=unit(normal);distance=normal@template[ia]
        signed=template@normal-distance
        if signed.min()>=-1e-5:normal=-normal;distance=-distance;signed=-signed
        if signed.max()>1e-5:continue
        if not any(np.linalg.norm(normal-n)<1e-5 and abs(distance-d)<1e-4 for n,d in planes):planes.append((normal,distance))
    result=points.copy()
    for _ in range(40):
        for normal,distance in planes:
            over=np.maximum(0,result@normal-distance)
            result-=over[:,None]*normal
    return result

def bind(mesh, donor, spec):
    if hashlib.sha256(mesh).hexdigest() != spec['mesh']['sha256']:
        raise ValueError('MagnaAngemon: mesh source differs from the pinned DCB import')
    sk=spec['mesh']['skeleton']
    mmd.exe().add_type(506,sk)
    source=mmd.MMD.parse(mesh,len(sk));source.type=506
    native=mmd.MMD.parse(donor,26);native.type=spec['source']['type']
    nsk=mmd.exe().skeleton[native.type]
    scale=spec['scale']
    sp=animsheet.slot_frames(source,len(sk),0)[0][0];sp[0]=[4096]*3+[0]*6
    np0=animsheet.slot_frames(native,26,0)[0][0];np0[0]=[4096]*3+[0]*6
    sw=np.array(mmd.bone_matrices(source,sp));nw=np.array(mmd.bone_matrices(native,np0));nw[:,:3,3]*=scale
    mapping={int(k):v for k,v in spec['map'].items()}
    children={int(k):v for k,v in spec['segments'].items()}
    base=np.array(mmd.rot_matrix(0,spec['heading'],0))
    objects={i:[] for i in range(len(native.tmd.objects))}
    for sb,tb in mapping.items():
        if sb in range(7,11):continue
        obj=sk[sb][0];target_obj=nsk[tb][0]
        vs=np.array(source.tmd.obj_verts(obj))[:,:3].astype(float)
        # Start with the calm native torso heading, then match anatomical segments.
        transform=base@sw[sb,:3,:3]
        offset=np.zeros(3)
        if sb in range(3,11):
            anchor=4 if sb<7 else 8
            offset=base@(sw[sb,:3,3]-sw[anchor,:3,3])
        elif sb in children:
            child=children[sb];target_child=mapping[child]
            a=base@(sw[child,:3,3]-sw[sb,:3,3]);b=nw[target_child,:3,3]-nw[tb,:3,3]
            stretch=np.eye(3)+(np.linalg.norm(b)/np.linalg.norm(a)-1)*np.outer(unit(a),unit(a))
            transform=align(a,b)@stretch@transform
            if sb in [20,23]:
                axis=unit(b)
                own=(vs@transform.T)@axis
                target=(cloud(native,tb,nw)*scale)@axis
                ratio=target.max()/own.max()
                transform=(np.eye(3)+(ratio-1)*np.outer(axis,axis))@transform
        elif sb in [21,24]:
            own=vs@transform.T;target=cloud(native,tb,nw)*scale
            # Boot shapes keep their surfaces while fitting the donor's sole envelope.
            ratios=np.ptp(target,axis=0)/np.maximum(np.ptp(own,axis=0),1)
            transform=np.diag(ratios)@transform
            offset=(target.max(axis=0)+target.min(axis=0)- (own@np.diag(ratios)).max(axis=0)-(own@np.diag(ratios)).min(axis=0))/2
        elif sb==25:
            transform=base@sw[sb,:3,:3]
            offset=base@(sw[sb,:3,3]-sw[2,:3,3])
        # Restore a local mesh on the actual native bone; animation comes only from it.
        local=nw[tb,:3,:3].T@transform
        off=nw[tb,:3,:3].T@offset
        objects[target_obj].append((obj,local,off,False))
        if sb in range(3,7):
            mirror=np.diag([-1.,1.,1.])
            left=16
            left_local=nw[left,:3,:3].T@mirror@transform
            left_off=nw[left,:3,:3].T@(mirror@(offset+nw[tb,:3,3])-nw[left,:3,3])
            objects[nsk[left][0]].append((obj,left_local,left_off,True))

    out=copy.deepcopy(native)
    tmd=mmd.TMD()
    for oi,items in sorted(objects.items()):
        ob=mmd.TMDObject();ob.vert_start=len(tmd.verts);ob.norm_start=len(tmd.norms);ob.scale=0
        ob.prims=[];nv=nn=0
        for source_obj,trans,off,mirrored in items:
            original=source.tmd.objects[source_obj]
            points=np.array(source.tmd.obj_verts(source_obj))[:,:3]@trans.T+off
            if source_obj in [20,23]:
                donor_obj=oi
                points=envelope(points,np.array(native.tmd.obj_verts(donor_obj))[:,:3]*scale)
            norms=np.array(source.tmd.obj_norms(source_obj)[:original.nnorm])[:,:3]@np.linalg.inv(trans)
            norms=norms/np.maximum(np.linalg.norm(norms,axis=1)[:,None],1)*4096
            tmd.verts.extend(tuple([round(v)for v in p]+[0])for p in points)
            tmd.norms.extend(tuple([round(v)for v in p]+[0])for p in norms)
            for prim in original.prims:
                d=prim.decode()
                if mirrored:
                    order=[0,2,1,3] if len(d['verts'])==4 else [0,2,1]
                    for key in ['verts','norms','uv','colors']:
                        if isinstance(d.get(key),list) and len(d[key])==len(order):d[key]=[d[key][i] for i in order]
                d['verts']=[i+nv for i in d['verts']]
                if d.get('norms'):d['norms']=[i+nn for i in d['norms']]
                ob.prims.append(mmd.Prim.encode(d))
            nv+=original.nvert;nn+=original.nnorm
        ob.nvert=nv;ob.nnorm=nn;tmd.objects.append(ob)
    object_map={i:j for j,i in enumerate(i for i,ob in enumerate(tmd.objects) if ob.nvert)}
    tmd.objects=[ob for ob in tmd.objects if ob.nvert]
    rig=[[object_map.get(obj,-1),parent] for obj,parent in nsk]
    out.tmd=tmd
    for a in out.anims.anims:
        for p in a.pose:
            for i in range(3):p[-3+i]=round(p[-3+i]*scale)
        for ins in a.instrs:
            if ins['op']=='key':
                for group in ins['bones']:
                    for k in list(group['vals']):
                        if k in ['tx','ty','tz']:group['vals'][k]=round(group['vals'][k]*scale)
        a.instrs=[ins for ins in a.instrs if ins['op']!='tex'];a.tail=b''
    # Preserve the species' move slots using only native Angemon performances.
    slots=list(out.anims.table)
    tech=spec['technique_slots']
    out.anims.table += [None]*max(0,61-len(out.anims.table))
    for sl,donor in enumerate(tech,46):out.anims.table[sl]=slots[donor]

    for destination,native_slot in spec.get('extra_slots',{}).items():
        out.anims.table[int(destination)]=slots[native_slot]
    return out.build(),rig


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mesh',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    spec=json.loads(SPEC.read_text())
    result,rig=bind(args.mesh.read_bytes(),Path(spec['source']['mmd']).read_bytes(),spec)
    args.output.write_bytes(result)
    args.output.with_suffix('.rig.json').write_text(json.dumps(rig,indent=2)+'\n')
    print(f'{args.output}: {len(result)} bytes, {len(rig)} native bones')


if __name__=='__main__':
    main()
