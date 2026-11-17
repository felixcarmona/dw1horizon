"""Render every Kyubimon tick at eight PSX-rule views, with common framing.

Run from the worktree containing build/before and build/after. Images and
per-frame hashes stay in build; the compact metrics can be archived separately.
--reuse reads existing sheets and repairs views clipped by the changed pose.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import sys,json,math,hashlib,multiprocessing
sys.path[:0]=[str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parents[1])]
import numpy as np
from tools.models.mesh_round4 import load
from tools.models import psx_blend,meshcheck

def init(reuse=False):
 global models,poses,use_existing
 use_existing=reuse
 models=[load(Path('build',stage),409) for stage in ['before','after']]
 poses=[{s:m.poses(s,6000) for s in m.slots()} for m in models]

def render(case):
 s,t=case;rows=[];images=[]
 existing=None
 if use_existing and Path(f'build/all-renders/{s}-{t}.png').exists():
  from tools.image import open_image
  existing=np.asarray(open_image(f'build/all-renders/{s}-{t}.png'))
 xyz=[m.tri_array(m.world(p[s][t])) for m,p in zip(models,poses)]
 for view in range(8):
  points=[meshcheck._rotate(x,view*math.pi/4,math.pi/6) for x in xyz]
  low,high=[getattr(points[0][...,:2].reshape(-1,2),op)(0) for op in ('min','max')]
  scale=72/max(high-low);offset=48-(low+high)/2*scale
  projected=points[1][...,:2]*scale+offset
  clipped=(projected<4).any() or (projected>92).any()
  if clipped:
   union=np.concatenate([x[...,:2].reshape(-1,2) for x in points])
   low,high=union.min(0),union.max(0)
   scale=72/max(high-low);offset=48-(low+high)/2*scale
  frame=(scale,offset)
  if existing is not None and not clipped:
   a=existing[view*96:(view+1)*96,:96].copy()
   b=existing[view*96:(view+1)*96,96:].copy()
  else:
   a,_=psx_blend.render(models[0],view*math.pi/4,math.pi/6,size=96,pose=poses[0][s][t],frame=frame)
   b,_=psx_blend.render(models[1],view*math.pi/4,math.pi/6,size=96,pose=poses[1][s][t],frame=frame)
  rows.append(dict(view=view,changed_pixels=int(np.any(a!=b,axis=2).sum()),before_sha256=hashlib.sha256(a.tobytes()).hexdigest(),after_sha256=hashlib.sha256(b.tobytes()).hexdigest()))
  images.append(np.concatenate([a,b],axis=1))
 meshcheck.png(f'build/all-renders/{s}-{t}.png',np.concatenate(images,axis=0))
 return dict(slot=s,tick=t,views=rows)

def review_cases(before, after, cases, out, size=192):
    """High-resolution matched sheets, with two-unit OT phase controls."""
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    rows=[]
    for slot,tick in cases:
        ps=[m.poses(slot,6000)[tick] for m in (before,after)]
        xyz=[m.tri_array(m.world(p)) for m,p in zip((before,after),ps)]
        sheets=[]
        for view in range(8):
            yaw=view*math.pi/4
            points=[meshcheck._rotate(x,yaw,math.pi/6)[...,:2].reshape(-1,2) for x in xyz]
            union=np.concatenate(points);low,high=union.min(0),union.max(0)
            scale=(size-24)/max(high-low);frame=(scale,size/2-(low+high)/2*scale)
            normal=[psx_blend.render(m,yaw,math.pi/6,size=size,pose=p,frame=frame)[0]
                    for m,p in zip((before,after),ps)]
            phase=[psx_blend.render(m,yaw,math.pi/6,size=size,pose=p,frame=frame,depth_offset=2)[0]
                   for m,p in zip((before,after),ps)]
            rows.append(dict(slot=slot,tick=tick,view=view,
                changed_pixels=int(np.any(normal[0]!=normal[1],axis=2).sum()),
                before_bin_phase_pixels=int(np.any(normal[0]!=phase[0],axis=2).sum()),
                after_bin_phase_pixels=int(np.any(normal[1]!=phase[1],axis=2).sum())))
            sheets.append(np.concatenate(normal,axis=1))
        meshcheck.png(str(out/f'{slot}-{tick}.png'),np.concatenate(sheets,axis=0))
    result=dict(rows=rows)
    for key in ('changed_pixels','before_bin_phase_pixels','after_bin_phase_pixels'):
        result[key]=sum(r[key] for r in rows)
    (out/'metrics.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--reuse',action='store_true')
 parser.add_argument('--workers',type=int,default=8)
 args=parser.parse_args()
 init(args.reuse);Path('build/all-renders').mkdir(exist_ok=True)
 cases=[(s,t) for s in models[0].slots() for t in range(len(poses[0][s]))]
 results=[]
 with multiprocessing.Pool(args.workers,initializer=init,initargs=(args.reuse,)) as pool:
  for r in pool.imap_unordered(render,cases,chunksize=4):
   results.append(r)
   if len(results)%80==0:print(len(results),'/',len(cases),flush=True)
 results.sort(key=lambda r:(r['slot'],r['tick']))
 Path('build/all-renders.json').write_text(json.dumps(dict(size=96,elevation_degrees=30,azimuths=8,frames=len(results),complete=len(results)==1461,rows=results)))
 print('COMPLETE',len(results),flush=True)
