"""Author a braced cannon attack with weight, recoil and overlapping wing motion.

The mesh and events stay exact. Native ranged attackers provide the acting
reference; the free arm supports the cannon while the feet stay planted.
"""
import os as _os
import sys as _sys
from pathlib import Path
_root = str(Path(__file__).resolve().parents[2])
_sys.path[:0] = [_root, str(Path(_root) / 'tools')]
from copy import deepcopy
import math,json
import mmd,animsheet,motionstorage,motioncyclelayer
import numeric as np
import legik
from tools.models.field_animations.war_greymon import rotation,align,set_rotation
from tools.models.field_animations.articulation import replace_channels
SID=403
PUNCH_SLOTS=(0x2e,0x2f,0x31,0x33)
CAST_SLOTS=(0x32,0x34,0x36,0x37,0x38,0x39,0x3a,0x3b,0x3d)
SLOTS=tuple(sorted(PUNCH_SLOTS+CAST_SLOTS))
CANNON=21
BARE_ARM=(16,17,18,19)

def curve(t,keys):
 if t<=keys[0][0]:return keys[0][1]
 for (a,x),(b,y) in zip(keys,keys[1:]):
  if t<=b:
   u=(t-a)/(b-a);u=u*u*(3-2*u);return x+(y-x)*u
 return keys[-1][1]

def authored(model,sk):
 idle,_,_=animsheet.slot_frames(model,31,33);rest=deepcopy(idle[0]);W=np.array(mmd.bone_matrices(model,rest));hist={}
 result=deepcopy(model)
 def world(p):return np.array(mmd.bone_matrices(model,p))
 def delta(p,b,deg):set_rotation(p,b,np.array(mmd.rot_matrix(*rest[b][3:6]))@rotation(deg),hist)
 def limb(p,h,k,a,target,pole,orient):
  ww=world(p);hip=ww[h,:3,3];d1=W[k,:3,3]-W[h,:3,3];d2=W[a,:3,3]-W[k,:3,3]
  knee,ank=legik.solve(hip,target,np.linalg.norm(d1),np.linalg.norm(d2),pole);knee=np.array(knee);ank=np.array(ank)
  desired=align(d1,knee-hip)@W[h,:3,:3];set_rotation(p,h,ww[sk[h][1],:3,:3].T@desired,hist)
  ww=world(p);desired=align(d2,ank-knee)@W[k,:3,:3];set_rotation(p,k,ww[h,:3,:3].T@desired,hist)
  ww=world(p);set_rotation(p,a,ww[k,:3,:3].T@orient,hist)
 for group in [PUNCH_SLOTS,CAST_SLOTS]:
  source,loop,events=animsheet.slot_frames(model,31,group[0]);n=len(source);shot=6 if n==15 else 18;prep=3 if n==15 else 8
  raise_keys=[(0,0),(prep,.7),(shot-1,1),(shot+3,1),(n-1,0)]
  load_keys=[(0,0),(prep,1),(shot,.35),(shot+2,.65),(shot+5,-.15),(n-1,0)]
  twist_keys=[(0,0),(prep,-10),(shot,7),(shot+2,12),(shot+5,-3),(n-1,0)]
  recoil_keys=[(0,0),(shot,0),(shot+2,1),(shot+5,-.18),(n-1,0)]
  poses=[];hist.clear()
  for t in range(n):
   p=deepcopy(rest);raise_=curve(t,raise_keys);load=curve(t,load_keys);twist=curve(t,twist_keys);kick=curve(t,recoil_keys)
   delta(p,1,[6*load-10*kick,twist,2*load-3*kick]);delta(p,2,[-2*load,-twist*.45,0])
   p[1][7]+=round(11*load+4*max(kick,0));p[1][8]+=round(8*load+11*kick)
   # Plant both feet while the pelvis drops and the shoulders take the kick.
   for h,k,a in [(3,4,5),(8,9,10)]:limb(p,h,k,a,W[a,:3,3],W[k,:3,3]-W[h,:3,3],W[a,:3,:3])
   delta(p,20,[-25*raise_+10*kick,-6*raise_,-7*raise_])
   ww=world(p);axis=ww[21,:3,:3]@np.array([0.,1.,0.]);angle=math.radians(15*kick)
   target=np.array([0.,-math.sin(angle),-math.cos(angle)])
   q=mmd.quat(*mmd.matrix_euler(align(axis,target)));partial=np.array(mmd.quat_matrix(mmd._slerp((0,0,0,1),q,raise_)))
   set_rotation(p,21,ww[20,:3,:3].T@partial@ww[21,:3,:3],hist)
   # The free hand braces below the barrel and follows the weapon's recoil.
   ww=world(p);target=ww[21,:3,3]+np.array([40.,45.,-70.]);target=ww[18,:3,3]*(1-raise_)+target*raise_
   limb(p,16,17,18,target,[1.,.2,.15],W[18,:3,:3]@np.array(rotation([-8*raise_,15*raise_,0])))
   delta(p,28,[-2*load+5*kick,-twist*.55,0])
   for root,tip,sign in [(24,25,1),(29,30,-1)]:
    lag=curve(t-1.5,recoil_keys);delta(p,root,[3*load+3*lag,sign*(7*load-8*lag),sign*4*load]);delta(p,tip,[2*load,sign*(4*load-11*curve(t-2.5,recoil_keys)),0])
   delta(p,12,[3*curve(t-2,load_keys),-twist*.25,0]);delta(p,13,[-4*curve(t-3,recoil_keys),0,0])
   poses.append([[int(round(x)) for x in bone] for bone in p])
  # Re-encode the complete acting, retaining event positions and duration.
  for tolerance in [12]:
   animation=mmd.encode_anim(poses,31,loop_sample=loop,events=events,tol=tolerance,repeats=False)
   # Preserve small weight shifts: angular tolerance is too coarse for translations.
   animation=replace_channels(animation,poses,loop,31,{(1,7),(1,8)},tolerance=1)
  result.anims.anims.append(animation)
  for slot in group:result.anims.table[slot]=len(result.anims.anims)-1
 for a in result.anims.anims:a.tail=b''
 result.anims.anims,result.anims.table=motioncyclelayer.share_identical_streams(result.anims.anims,result.anims.table)
 data = result.build()
 return data

def repair(model, skeleton):
    data = authored(model, skeleton)
    after = mmd.MMD.parse(data, len(skeleton)); after.type = SID
    from motiondiscidentity import changed_programs
    assert changed_programs(model, after) == list(SLOTS)
    assert model.tmd.build() == after.tmd.build()
    for slot in SLOTS:
        a, loop, events = animsheet.slot_frames(model, len(skeleton), slot)
        b, new_loop, new_events = animsheet.slot_frames(after, len(skeleton), slot)
        assert (len(a), loop, events) == (len(b), new_loop, new_events)
    from tools.models import buster_dive
    spec = json.loads((Path(_root) / 'content/species/403-beelzemon.json').read_text())
    record = json.loads((Path(_root) / 'content/models/imports/models.json').read_text())[str(SID)]
    consumed, _ = buster_dive.apply(data, spec, clip=record.get('buster_dive_clip'))
    return data, dict(changed_slots=list(SLOTS), cannon_bone=CANNON, mesh_exact=True,
                      events_and_duration_exact=True, planted_feet=True,
                      intermediate_storage=motionstorage.audit(data, len(skeleton)),
                      storage=motionstorage.require(consumed, len(skeleton)))

def main():
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model', type=Path)
    parser.add_argument('out', type=Path)
    args = parser.parse_args()
    model = mmd.MMD.load(str(args.model), SID)
    result, proof = repair(model, mmd.exe().skeleton[SID])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(result)
    import json
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    main()
