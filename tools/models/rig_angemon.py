"""Bind the World 2003 MagnaAngemon mesh to native Angemon's rig and clips.

Developer-only static mesh authoring. Player builds replay the frozen source
mesh and plain deltas; no NumPy or animation retargeting is needed by players.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import mmd
import animsheet
import retarget

SPEC=Path('content/imports/specs/MagnaAngemon.json')

def bind(mesh,texture,donor,donor_texture,spec):
    if hashlib.sha256(mesh).hexdigest()!=spec['mesh']['sha256']:
        raise ValueError('MagnaAngemon: unpinned mesh source')
    if hashlib.sha256(texture).hexdigest()!=spec['mesh']['texture_sha256']:
        raise ValueError('MagnaAngemon: unpinned texture source')
    mmd.exe().add_type(506,spec['mesh']['skeleton'])
    s=mmd.MMD.parse(mesh,len(spec['mesh']['skeleton']));s.type=506
    n=mmd.MMD.parse(donor,26);n.type=spec['source']['type']
    sp=animsheet.slot_frames(s,33,0)[0][0];np0=animsheet.slot_frames(n,26,0)[0][0]
    sp[0]=np0[0]=[4096]*3+[0]*6
    sw=np.array(mmd.bone_matrices(s,sp));nw=np.array(mmd.bone_matrices(n,np0));scale=spec['scale'];nw[:,:3,3]*=scale
    sk=spec['mesh']['skeleton'];nk=mmd.exe().skeleton[20]
    mapping={int(k):v for k,v in spec['map'].items()}
    children={int(k):v for k,v in spec['segments'].items()}
    # Texture the native staff with its original small atlas strip.
    tim=mmd.Tim4(texture);nt=mmd.Tim4(donor_texture)
    used=set();mask=np.zeros((128,256),bool)
    for ob in s.tmd.objects:
     for prim in ob.prims:
      d=prim.decode()
      if d.get('uv'):
       used.add((d['cba']>>6)-488);uv=np.array(d['uv']);lo=uv.min(0);hi=uv.max(0);mask[lo[1]:hi[1]+1,lo[0]:hi[0]+1]=True
    pal=next(i for i in range(15)if i not in used);tim.pal[pal]=list(nt.pal[9])
    spot=None
    for y in range(121):
     for x in range(217):
      if not mask[y:y+8,x:x+40].any():spot=(x,y);break
     if spot:break
    if not spot:raise ValueError('No staff texture space')
    x,y=spot
    for j in range(8):
     for i in range(40):tim.idx[(y+j)*256+x+i]=nt.idx[(72+j)*256+136+i]

    items={i:[]for i in range(26)}
    def cloud(m,b,w,rig):
     return np.array(m.tmd.obj_verts(rig[b][0]))[:,:3]@w[b,:3,:3].T+w[b,:3,3]
    # Native hand envelope excludes the staff's palette.
    hand={}
    for b in (6,9):
     obj=nk[b][0];ids=set(v for p in n.tmd.objects[obj].prims if p.decode()['cba']!=31808 for v in p.decode()['verts'])
     hand[b]=np.array(n.tmd.obj_verts(obj))[sorted(ids),:3]@nw[b,:3,:3].T*scale+nw[b,:3,3]
    for sb,tb in mapping.items():
     obj=sk[sb][0];points=cloud(s,sb,sw,sk);mat=np.eye(3);off=nw[tb,:3,3]-sw[sb,:3,3]
     if sb in children:
      child=children[sb];a=sw[child,:3,3]-sw[sb,:3,3];b=nw[mapping[child],:3,3]-nw[tb,:3,3]
      ua=a/np.linalg.norm(a);mat=np.array(retarget.swing(a.tolist(),b.tolist()))@(np.eye(3)+(np.linalg.norm(b)/np.linalg.norm(a)-1)*np.outer(ua,ua))
      points=(points-sw[sb,:3,3])@mat.T+nw[tb,:3,3]
     elif sb in (4,7,28,31):
      target=hand[tb] if sb in (28,31) else cloud(n,tb,nw,nk)+(cloud(n,tb,nw,nk)-nw[tb,:3,3])*(scale-1)
      ratio=np.ptp(target,axis=0)/np.maximum(np.ptp(points,axis=0),1);mat=np.diag(ratio)
      points=(points-points.min(0))*ratio+target.min(0)
     elif sb==8:
      # The solid chest has a separate vertex island from the long sashes.
      ids=list(range(22))+list(range(33,47));body=points[ids];ratio=np.array([189/np.ptp(body[:,0]),195/np.ptp(body[:,1]),1.35]);mat=np.diag(ratio)
      center=(body.min(0)+body.max(0))/2;dest=np.array([0.,-361.5,33.])
      points=(points-center)*ratio+dest
      upper=np.array([i not in ids for i in range(len(points))])&(points[:,1]<-430)
      points[upper,1]=-430+(points[upper,1]+430)*.2
      # Keep the sash tips above the calves rather than extending into the feet.
      below=points[:,1]>-264;points[below,1]=-264+(points[below,1]+264)*.48
     elif sb==spec['cloth']['source']:
      mat=np.diag(spec['cloth']['scale']);points=(points-sw[1,:3,3])@mat.T+nw[spec['cloth']['donor'],:3,3]
     elif sb in spec['head']['sources']:
      body=cloud(s,8,sw,sk)[list(range(22))+list(range(33,47))]
      center=(body.min(0)+body.max(0))/2;mat=np.diag([189/np.ptp(body[:,0]),195/np.ptp(body[:,1]),1.35])
      offset=np.array(spec['head']['offset'],dtype=float)
      origin=np.array([0.,-361.5,33.+offset[2]])
      points=(points-center)@mat.T+origin
      pivot=(np.array([0.,-490.,-38.])-center)@mat.T+origin
      tilt=np.array(mmd.rot_matrix(spec['head']['tilt'],0,0));points=(points-pivot)@tilt.T+pivot+np.array([offset[0],offset[1],0.]);mat=tilt@mat
     elif sb in spec['wings']['sources']:
      anchor=np.array(spec['wings']['anchor'],dtype=float)
      mat=np.diag(spec['wings']['scale']);points=(points-anchor)@mat.T+nw[tb,:3,3]
     else:points+=off
     local=(points-nw[tb,:3,3])@nw[tb,:3,:3]
     norms=np.array(s.tmd.obj_norms(obj)[:s.tmd.objects[obj].nnorm]).reshape(-1,4)[:,:3]@sw[sb,:3,:3].T@np.linalg.inv(mat)@nw[tb,:3,:3]
     items[tb].append((s,obj,local,norms,None))
     if sb in spec['wings']['sources'] and spec['wings']['mirror_right']:
      mirrored=points.copy();mirrored[:,0]*=-1
      left=spec['wings']['left_donor']
      left_local=(mirrored-nw[left,:3,3])@nw[left,:3,:3]
      left_norms=norms@nw[tb,:3,:3].T@np.diag([-1.,1.,1.])@nw[left,:3,:3]
      prims=[]
      for prim in s.tmd.objects[obj].prims:
       d=prim.decode();order=[0,2,1,3]if len(d['verts'])==4 else[0,2,1]
       for key in ['verts','norms','uv','colors']:
        if isinstance(d.get(key),list)and len(d[key])==len(order):d[key]=[d[key][i]for i in order]
       prims.append(mmd.Prim.encode(d))
      items[left].append((s,obj,left_local,left_norms,prims))
    # Keep just the donor's staff faces; their vertices can be shared with the hand.
    obj=nk[9][0];staff=[]
    for p in n.tmd.objects[obj].prims:
     d=p.decode()
     if d.get('cba')==31808:
      d['uv']=[(u-136+x,v-72+y)for u,v in d['uv']];d['cba']=(488+pal)<<6;staff.append(mmd.Prim.encode(d))
    items[9].append((n,obj,np.array(n.tmd.obj_verts(obj))[:,:3]*scale,np.array(n.tmd.obj_norms(obj)[:n.tmd.objects[obj].nnorm])[:,:3],staff))
    tmd=mmd.TMD();rig=[]
    for b,(old_obj,parent)in enumerate(nk):
     if not items[b]:rig.append([-1,parent]);continue
     ob=mmd.TMDObject();ob.vert_start=len(tmd.verts);ob.norm_start=len(tmd.norms);ob.scale=0;ob.prims=[];nv=nn=0
     for model,obj,pts,norms,prims in items[b]:
      source=model.tmd.objects[obj]
      tmd.verts.extend(tuple([round(v)for v in p]+[0])for p in pts)
      norms=norms/np.maximum(np.linalg.norm(norms,axis=1)[:,None],1)*4096
      tmd.norms.extend(tuple([round(v)for v in p]+[0])for p in norms)
      for p in source.prims if prims is None else prims:
       d=p.decode();d['verts']=[v+nv for v in d['verts']]
       if d.get('norms'):d['norms']=[v+nn for v in d['norms']]
       ob.prims.append(mmd.Prim.encode(d))
      nv+=len(pts);nn+=len(norms)
     ob.nvert=nv;ob.nnorm=nn;rig.append([len(tmd.objects),parent]);tmd.objects.append(ob)
    result=copy.deepcopy(n);result.tmd=tmd
    for a in result.anims.anims:
     for p in a.pose:p[-3:]=[round(v*scale)for v in p[-3:]]
     for ins in a.instrs:
      if ins['op']=='key':
       for g in ins['bones']:
        for k in g['vals']:
         if k in ('tx','ty','tz'):g['vals'][k]=round(g['vals'][k]*scale)
     a.instrs=[i for i in a.instrs if i['op']!='tex'];a.tail=b''
    slots=list(result.anims.table);result.anims.table+=[None]*max(0,61-len(slots))
    for dest,donor in enumerate(spec['technique_slots'],46):result.anims.table[dest]=slots[donor]
    for dest,donor in spec['extra_slots'].items():result.anims.table[int(dest)]=slots[donor]
    return result.build(),tim.to_bytes(),rig

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mesh',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    spec=json.loads(SPEC.read_text())
    donor_texture=mmd.load_tim('extracted/CHDAT/ALLTIM.TIM',spec['source']['type']).to_bytes()
    model,texture,rig=bind(args.mesh.read_bytes(),args.mesh.with_suffix('.TIM').read_bytes(),Path(spec['source']['mmd']).read_bytes(),donor_texture,spec)
    args.output.write_bytes(model)
    args.output.with_suffix('.TIM').write_bytes(texture)
    args.output.with_suffix('.rig.json').write_text(json.dumps(rig,indent=2)+'\n')
    print(f'{args.output}: {len(model)} bytes, {len(rig)} native bones')

if __name__=='__main__':
    main()
