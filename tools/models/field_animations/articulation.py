#!/usr/bin/env python3
"""Mapped upper-body field acting, preserving the original leg and root programs."""
import os as _model_os
import sys as _model_sys
_model_repo_root = _model_os.path.abspath(_model_os.path.join(_model_os.path.dirname(__file__), '../../..'))
_model_sys.path[:0] = [_model_repo_root, _model_os.path.join(_model_repo_root, 'tools')]
import argparse,copy,hashlib,json,math
from pathlib import Path
import numeric as np
import mmd,animsheet,motionstorage
from motiondiscidentity import changed_programs
from tools.models.field_animations.war_greymon import rotation, set_rotation


def replace_channels(original,samples,loop,nb,channels,*,tolerance=1):
    encoded=mmd.encode_anim(samples,nb,loop_sample=loop,tol=tolerance,repeats=False)
    result=copy.deepcopy(original)
    for b,c in channels:result.pose[b-1][c if result.has_scale else c-3]=encoded.pose[b-1][c if encoded.has_scale else c-3]
    for ins in result.instrs:
        if ins['op']=='key':
            for group in ins['bones']:group['vals']={k:v for k,v in group['vals'].items()if(group['bone'],mmd.CHANNELS.index(k))not in channels}
            ins['bones']=[g for g in ins['bones']if g['vals']]
    for ins in encoded.instrs:
        if ins['op']!='key':continue
        key=copy.deepcopy(ins)
        for group in key['bones']:group['vals']={k:v for k,v in group['vals'].items()if(group['bone'],mmd.CHANNELS.index(k))in channels}
        key['bones']=[g for g in key['bones']if g['vals']]
        if not key['bones']:continue
        existing=next((i for i in result.instrs if i['op']=='key'and i['frame']==key['frame']),None)
        if existing is not None:existing['bones'].extend(key['bones']);continue
        at=len(result.instrs)-1
        for j,other in enumerate(result.instrs):
            f=other.get('frame')
            if other['op']=='loop_start':f=next((x.get('frame')for x in result.instrs[j+1:]if x.get('frame')is not None),None)
            if f is not None and f>key['frame']:at=j;break
        result.instrs.insert(at,key)
    return result


def build(data,sk):
    digest=hashlib.sha256(data).hexdigest()
    if digest!='2834a5f401362586a350ab6c4839c9231542dbfdec420b594fad964f13753572':raise ValueError('Puppetmon recipe requires its reviewed effective imported source')
    sid=181;nb=len(sk);assert nb==18;mmd.exe().skeleton[sid]=sk;mmd.exe().bone_count[sid]=nb
    old=mmd.MMD.parse(data,nb);old.type=sid;new=copy.deepcopy(old);report=[]
    channels={(b,c)for b in [2,3,4,5,6,7,8,9,10,11]for c in [3,4,5]}
    for slot in [2,3,4]:
        fs,loop,events=animsheet.slot_frames(old,nb,slot);duration=len(fs)-1;assert loop==0
        worlds=np.array([mmd.bone_matrices(old,p)for p in fs]);sep=worlds[:,14,2,3]-worlds[:,17,2,3]
        drive=sep[:-1]-np.mean(sep[:-1]);drive/=max(1,np.max(np.abs(drive)))
        theta=2*np.pi*np.arange(duration)/duration
        a,b=np.linalg.lstsq(np.column_stack([np.sin(theta),np.cos(theta)]),drive,rcond=None)[0];phase=math.atan2(b,a)
        frames=[];hist={};running=slot==4;tired=slot==3
        for tick,source in enumerate(fs):
            theta=2*math.pi*tick/duration+phase;p=copy.deepcopy(source)
            original=np.array(mmd.bone_matrices(old,source))
            chest=np.array(mmd.rot_matrix(*source[2][3:6]))@rotation([.6*math.sin(2*theta-.4),4*math.sin(theta),1.5*math.cos(theta-.2)])
            set_rotation(p,2,chest,hist)
            for clavicle in [4,8]:p[clavicle][3:6]=[0,0,0]
            for shoulder,elbow,sign in [(5,6,1),(9,10,-1)]:
                heavy=sign<0;amp=(18 if running else 9 if tired else 14)*(.45 if heavy else 1)
                swing=sign*math.cos(theta-.2);lag=sign*math.cos(theta-.8)
                p[shoulder][3:6]=[round((-8+amp*swing)*4096/360),0,round(-sign*20*4096/360)]
                p[elbow][3:6]=[round((-(57 if heavy else 42)+(4 if heavy else 7)*lag)*4096/360),0,0]
            # Keep the original weapon orientation; the wrists counter the arm's swing.
            for hand in [7,11]:
                parent=np.array(mmd.bone_matrices(old,p))[sk[hand][1],:3,:3]
                set_rotation(p,hand,parent.T@original[hand,:3,:3],hist)
            parent=np.array(mmd.bone_matrices(old,p))[sk[3][1],:3,:3]
            set_rotation(p,3,parent.T@original[3,:3,:3]@rotation([.8*math.cos(2*theta-.6),0,1.2*math.sin(theta-.7)]),hist)
            frames.append(p)
        frames[-1][1:]=copy.deepcopy(frames[0][1:])
        anim=replace_channels(old.anims.anims[old.anims.table[slot]],frames,loop,nb,channels)
        new.anims.anims.append(anim);new.anims.table[slot]=len(new.anims.anims)-1
        before=mmd.AnimPlayer(old.anims.anims[old.anims.table[slot]],nb,slot);after=mmd.AnimPlayer(anim,nb,slot)
        for tick in range(duration*4):
            assert before.tick()and after.tick();assert before.base==after.base
            for bone in range(nb):
                for c in range(9):
                    if(bone,c)not in channels:assert before.pose[bone][c]==after.pose[bone][c],(slot,tick,bone,c)
        report.append(dict(slot=slot,period=duration,root_and_leg_channels_exact_for_four_cycles=True,original_events_and_controls_preserved=True))
    import motioncyclelayer
    for a in new.anims.anims:a.tail=b''
    new.anims.anims,new.anims.table=motioncyclelayer.share_identical_streams(new.anims.anims,new.anims.table)
    result=new.build();parsed=mmd.MMD.parse(result,nb);assert changed_programs(old,parsed)==[2,3,4];assert old.tmd.build()==parsed.tmd.build()
    storage=motionstorage.audit(result,nb);assert storage['fits'],storage
    return result,dict(species=sid,source_sha256=digest,output_sha256=hashlib.sha256(result).hexdigest(),changed_slots=[2,3,4],mesh_exact=True,other_programs_exact=True,checks=report,storage=storage)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--specimen',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();import species
    s=json.loads(a.specimen.read_text());s['_path']=str(a.specimen);raw,_=species.species_model(s);data,report=build(raw,s['model']['skeleton']);a.out.mkdir(parents=True,exist_ok=False)
    model=a.out/f'{s["id"]}-acting.MMD';model.write_bytes(data);s['model']['file']=str(model.resolve());s['model'].pop('slot_aliases',None);s.pop('_path',None)
    (a.out/'specimen.json').write_text(json.dumps(s,indent=2)+'\n');(a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
