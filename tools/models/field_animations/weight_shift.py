#!/usr/bin/env python3
"""Mapped quadruped weight transfer around the source's existing paw trajectories."""
import os as _model_os
import sys as _model_sys
_model_repo_root = _model_os.path.abspath(_model_os.path.join(_model_os.path.dirname(__file__), '../../..'))
_model_sys.path[:0] = [_model_repo_root, _model_os.path.join(_model_repo_root, 'tools')]
import argparse,copy,hashlib,json,math
from pathlib import Path
import numeric as np
import mmd,animsheet,motionstorage,motionsecondary
from tools.models.field_animations.articulation import replace_channels
from motiondiscidentity import changed_programs
from tools.models.field_animations.war_greymon import rotation, set_rotation

PROFILES={
 189:dict(source='f3114202393e99a675e229faaa1e9d87593e7608eb806f8b4ae2d22c0813cf7f',bones=19,body=1,head=3,legs=[(4,5,6),(7,8,9),(10,11,12),(13,14,15)],period=24,
          roll=1.1,yaw=1.4,pitch=.4,sag=2,tail_clearance=dict(root=16,bones=[16,17,18],walk_limit=3,idle_limit=16),
          style='heavy shell weight transfer around existing short steps; native head and tail acting retained, idle club cleared above ground'),
 201:dict(source='8b8ddc1eacd0e0c2d96fa99706d374766e75e99ed30542cfe8202e2cb50b2eeb',bones=25,body=13,head=3,legs=[(6,7,8),(10,11,12),(18,19,20),(22,23,24)],period=24,
          roll=1.6,yaw=2.2,pitch=.6,sag=2,
          style='supple quadruped weight transfer around existing short steps; native cap, head, ear and tail acting retained'),
}


def clear_tail(p,limit,model,sk,cfg,history):
 world=np.array(mmd.bone_matrices(model,p));root=cfg['root'];points=[]
 for b in cfg['bones']:
  verts=np.array(model.tmd.obj_verts(sk[b][0]))[:,:3];points.extend((verts@world[b,:3,:3].T+world[b,:3,3]).tolist())
 correction=np.array(motionsecondary.clearance_rotation(points,world[root,:3,3].tolist(),[1,0,0],[0,limit],-2))
 parent=world[sk[root][1],:3,:3];set_rotation(p,root,parent.T@correction@world[root,:3,:3],history)
 return float(math.degrees(math.acos(min(1,max(-1,(np.trace(correction)-1)/2)))))


def build(data,sk):
 digest=hashlib.sha256(data).hexdigest();matches=[(sid,cfg)for sid,cfg in PROFILES.items()if cfg.get('source')==digest]
 if len(matches)!=1:raise ValueError('No reviewed weight-transfer profile for this source')
 sid,cfg=matches[0];n=len(sk);assert n==cfg['bones'];mmd.exe().skeleton[sid]=sk;mmd.exe().bone_count[sid]=n
 old=mmd.MMD.parse(data,n);old.type=sid;new=copy.deepcopy(old);slot=2;fs,loop,events=animsheet.slot_frames(old,n,slot);duration=len(fs)-1;assert loop==0 and duration%cfg['period']==0
 feet=[leg[2]for leg in cfg['legs']];world=np.array([mmd.bone_matrices(old,p)for p in fs]);sep=world[:,feet[0],2,3]-world[:,feet[1],2,3]
 theta=2*np.pi*np.arange(duration)/cfg['period'];drive=sep[:-1]-np.mean(sep[:-1]);drive/=max(1,np.max(np.abs(drive)))
 a,b=np.linalg.lstsq(np.column_stack([np.sin(theta),np.cos(theta)]),drive,rcond=None)[0];phase=math.atan2(b,a)
 channels={(cfg['body'],c)for c in [3,4,5,7]}|{(cfg['head'],c)for c in [3,4,5]}|{(b,c)for chain in cfg['legs']for b in chain for c in [3,4,5]}
 if cfg.get('tail_clearance'):channels.update((cfg['tail_clearance']['root'],c)for c in [3,4,5])
 frames=[];hist={};max_error=0.;minimum_margin=1e9
 for tick,source in enumerate(fs):
  p=copy.deepcopy(source);reference=world[tick];t=2*math.pi*tick/cfg['period']+phase;body=cfg['body']
  body_r=np.array(mmd.rot_matrix(*source[body][3:6]))@rotation([cfg['pitch']*math.cos(2*t-.4),cfg['yaw']*math.sin(t-.25),-cfg['roll']*math.sin(t)])
  set_rotation(p,body,body_r,hist);p[body][7]+=cfg['sag']
  parent=np.array(mmd.bone_matrices(old,p))[sk[cfg['head']][1],:3,:3]
  set_rotation(p,cfg['head'],parent.T@reference[cfg['head'],:3,:3],hist)
  if cfg.get('tail_clearance'):
   clear_tail(p,cfg['tail_clearance']['walk_limit'],old,sk,cfg['tail_clearance'],hist)
  for hip,knee,foot in cfg['legs']:
   w=np.array(mmd.bone_matrices(old,p));h=w[hip,:3,3];goal=reference[foot,:3,3];d=goal-h;distance=np.linalg.norm(d)
   la=np.linalg.norm(source[knee][6:9]);lb=np.linalg.norm(source[foot][6:9]);margin=min(la+lb-distance,distance-abs(la-lb));minimum_margin=min(minimum_margin,float(margin));assert margin>.05,(sid,tick,hip,margin)
   direction=d/distance;pole=reference[knee,:3,3]-h;pole-=direction*(pole@direction);assert np.linalg.norm(pole)>1e-5;pole/=np.linalg.norm(pole)
   along=(la*la-lb*lb+distance*distance)/(2*distance);joint=h+direction*along+pole*math.sqrt(max(0,la*la-along*along))
   upper,lower=motionsecondary.native_plane_rotations([reference[b,:3,3].tolist()for b in [hip,knee,foot]], [h.tolist(),joint.tolist(),goal.tolist()], [reference[b,:3,:3].tolist()for b in [hip,knee]])
   set_rotation(p,hip,w[sk[hip][1],:3,:3].T@np.array(upper),hist)
   parent=np.array(mmd.bone_matrices(old,p))[hip,:3,:3];set_rotation(p,knee,parent.T@np.array(lower),hist)
   parent=np.array(mmd.bone_matrices(old,p))[knee,:3,:3];set_rotation(p,foot,parent.T@reference[foot,:3,:3],hist)
   actual=np.array(mmd.bone_matrices(old,p))[foot,:3,3];max_error=max(max_error,float(np.linalg.norm(actual-goal)))
  frames.append(p)
 frames[-1][1:]=copy.deepcopy(frames[0][1:]);assert max_error<1,(sid,max_error)
 original=old.anims.anims[old.anims.table[slot]];anim=replace_channels(original,frames,loop,n,channels);new.anims.anims.append(anim);new.anims.table[slot]=len(new.anims.anims)-1
 before=mmd.AnimPlayer(original,n,slot);after=mmd.AnimPlayer(anim,n,slot);codec_error=0.;max_rot_error=0.
 for tick in range(duration*4):
  assert before.tick()and after.tick();assert before.base==after.base
  for bone in range(n):
   for c in range(9):
    if(bone,c)not in channels:assert before.pose[bone][c]==after.pose[bone][c],(slot,tick,bone,c)
  wa=np.array(mmd.bone_matrices(old,before.pose));wb=np.array(mmd.bone_matrices(old,after.pose));codec_error=max(codec_error,float(np.linalg.norm(wa[feet,:3,3]-wb[feet,:3,3],axis=1).max()));max_rot_error=max(max_rot_error,float(np.abs(wa[feet,:3,:3]-wb[feet,:3,:3]).max()))
 assert codec_error<2,(sid,codec_error)
 import motioncyclelayer
 for a in new.anims.anims:a.tail=b''
 new.anims.anims,new.anims.table=motioncyclelayer.share_identical_streams(new.anims.anims,new.anims.table)
 changed=[2];idle_check=None
 if cfg.get('tail_clearance'):
  idle,loop,_=animsheet.slot_frames(old,n,0);samples=[];idle_hist={};maximum=0.
  for source in idle:
   p=copy.deepcopy(source);angle=clear_tail(p,cfg['tail_clearance']['idle_limit'],old,sk,cfg['tail_clearance'],idle_hist);maximum=max(maximum,angle);samples.append(p)
  samples[-1][1:]=copy.deepcopy(samples[0][1:]);root=cfg['tail_clearance']['root'];ch={(root,c)for c in [3,4,5]};original=old.anims.anims[old.anims.table[0]];idle_anim=replace_channels(original,samples,loop,n,ch)
  new.anims.anims.append(idle_anim);new.anims.table[0]=len(new.anims.anims)-1
  before=mmd.AnimPlayer(original,n,0);after=mmd.AnimPlayer(idle_anim,n,0)
  for tick in range((len(idle)-1)*4):
   assert before.tick()and after.tick();assert before.base==after.base
   for b in range(n):
    for c in range(9):
     if(b,c)not in ch:assert before.pose[b][c]==after.pose[b][c],(sid,0,tick,b,c)
  idle_check=dict(only_tail_root_rotation_changed=True,other_channels_and_events_exact_for_four_cycles=True,maximum_world_pitch_correction_degrees=maximum)
  changed=[0,2]
 result=new.build();parsed=mmd.MMD.parse(result,n);assert changed_programs(old,parsed)==changed;assert old.tmd.build()==parsed.tmd.build();storage=motionstorage.audit(result,n);assert storage['fits'],storage
 return result,dict(species=sid,source_sha256=digest,output_sha256=hashlib.sha256(result).hexdigest(),profile_style=cfg['style'],changed_slots=changed,idle_tail_clearance=idle_check,mesh_exact=True,other_programs_exact=True,original_root_events_scales_and_limb_lengths_exact=True,source_cadence_ticks=cfg['period'],duration=duration,max_authored_foot_position_error=max_error,max_encoded_foot_position_error=codec_error,max_encoded_foot_rotation_matrix_error=max_rot_error,minimum_reach_margin=minimum_margin,storage=storage)


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--specimen',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();import species
 s=json.loads(a.specimen.read_text());s['_path']=str(a.specimen);raw,_=species.species_model(s);data,report=build(raw,s['model']['skeleton']);a.out.mkdir(parents=True,exist_ok=False)
 model=a.out/f'{s["id"]}-acting.MMD';model.write_bytes(data);s['model']['file']=str(model.resolve());s['model'].pop('slot_aliases',None);s.pop('_path',None)
 (a.out/'specimen.json').write_text(json.dumps(s,indent=2)+'\n');(a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
