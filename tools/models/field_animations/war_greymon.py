#!/usr/bin/env python3
"""WarGreymon373 anatomical field gait, replacing dinosaur retargeting.

Mesh and non-field clips stay exact. Field stride and root speed are authored
together; original footstep sounds follow the new contact cadence. Leg IK aims feet forward; back plates open clear of
leg swing. This does not add terrain IK or change the field movement engine.
"""
import os as _model_os
import sys as _model_sys
_model_repo_root = _model_os.path.abspath(_model_os.path.join(_model_os.path.dirname(__file__), '../../..'))
_model_sys.path[:0] = [_model_repo_root, _model_os.path.join(_model_repo_root, 'tools')]
import argparse
import copy
import hashlib
import json
import math
import struct
from pathlib import Path
import numeric as np
import mmd
import animsheet
import motionstorage
from motiondiscidentity import changed_programs

SOURCE='67d6d20e00fb34a60e88dd28ad4c171de1e5d21d805603158c8ca7326ec4b51b'
SLOTS=[0,2,3,4]


def rotation(degrees):
    return np.array(mmd.rot_matrix(*[x*4096/360 for x in degrees]))


def align(a,b):
    a=np.array(a,float);a/=np.linalg.norm(a);b=np.array(b,float);b/=np.linalg.norm(b)
    v=np.cross(a,b);c=float(a@b);assert c>-.999
    k=np.array([[0,-v[2],v[1]],[v[2],0,-v[0]],[-v[1],v[0],0]])
    return np.eye(3)+k+k@k/(1+c)


def set_rotation(p,b,r,history):
    angle=mmd.matrix_euler(r,history.get(b));history[b]=angle
    p[b][3:6]=[round(x)for x in angle]


def trajectory(u,stride,lift,duty):
    if u<duty:return -stride+2*stride*u/duty,0.
    v=(u-duty)/(1-duty);h=3*v*v-2*v*v*v
    velocity=2*stride*(1-duty)/duty
    z=stride*(1-2*h)+velocity*(2*v*v*v-3*v*v+v)
    return z,lift*math.sin(math.pi*v)**2


def build(data,sk):
    if hashlib.sha256(data).hexdigest()!=SOURCE:raise ValueError('WarGreymon field recipe requires the reviewed ImportedModels model, with aliases already applied')
    nb=len(sk);assert nb==21
    old=mmd.MMD.parse(data,nb);old.type=373;new=copy.deepcopy(old)
    mmd.exe().skeleton[373]=sk;mmd.exe().bone_count[373]=nb
    bind=copy.deepcopy(animsheet.slot_frames(old,nb,33)[0][0])
    for b in range(1,nb):assert bind[b][:3]==[4096]*3;bind[b][3:6]=[0,0,0]
    bind[0]=[4096]*3+[0]*6
    report=[]
    for slot in SLOTS:
        fs,loop,events=animsheet.slot_frames(old,nb,slot);assert loop==0
        idle=slot==0;tired=slot==3;running=slot==4
        period=(len(fs)-1) if idle else 10 if running else 20 if tired else 16
        speed=0 if idle else 52 if running else 15 if tired else 22
        lift=0 if idle else 60 if running else 18 if tired else 28
        duty=.42 if running else .64 if tired else .56
        stride=speed*period*duty/2
        height=220 if idle else 192 if running else 205 if tired else 212
        contact=0
        event_data=next((instruction for _,kind,instruction in events if kind=='sound'),None)
        gait_events=[] if idle or event_data is None else [(tick,'sound',dict(event_data,frame=tick+1))for tick in [0,period//2]]
        out=[];history={};clamps=0
        for tick in range(period+1):
            theta=2*math.pi*(tick-contact)/period;wave=math.sin(theta)
            p=copy.deepcopy(bind)
            sway=(1.5 if idle else 5 if running else 7 if tired else 9)*math.sin(theta-.18)
            bounce=2*math.cos(theta-.2) if idle else (9 if running else 5 if tired else 6)*math.cos(2*theta-(.9 if running else .25))+1.5*math.cos(4*theta-.5)
            p[1][6:9]=[round(-sway),round(-height+bounce),16]
            p[1][3:6]=[0,round((.5 if idle else -3 if tired else -4)*math.cos(theta)*4096/360),round((.5 if idle else 2.5)*wave*4096/360)]
            lean=2 if idle else 10 if running else 9 if tired else 4
            chest_pitch=lean+(1 if idle else 1.7)*math.sin(2*theta-.65)
            chest_yaw=(1 if idle else 5 if tired else 7)*math.cos(theta-.12)
            p[2][3:6]=[round(chest_pitch*4096/360),round(chest_yaw*4096/360),round(-(.25 if idle else 1.5)*math.sin(theta-.35)*4096/360)]
            p[3][3:6]=[round(-chest_pitch*.30*4096/360),0,0]
            p[4][3:6]=[round((-chest_pitch*.45+.6*math.sin(2*theta-1.1))*4096/360),round(-chest_yaw*.4*4096/360),0]
            for shoulder,elbow,sign in [(6,7,1),(8,9,-1)]:
                armwave=math.cos(theta-.18)*sign;lag=math.cos(theta-.80)*sign
                amp=1.5 if idle else 24 if running else 14 if tired else 22
                p[shoulder][3:6]=[round((-8+(1.2 if sign==1 else -1.2)+amp*armwave)*4096/360),0,round(sign*12*4096/360)]
                p[elbow][3:6]=[round((-(65 if running else 38)+(2 if idle else 8)*lag)*4096/360),0,round(sign*(14 if running else 10)*4096/360)]
            # These are hinged back-armor plates, not flapping feathered wings.
            for b,sign in [(19,1),(20,-1)]:p[b][3:6]=[round((26+.6*math.sin(theta-.9))*4096/360),round(sign*22*4096/360),round(sign*20*4096/360)]
            for hip,knee,foot,sign,phase in [(10,11,12,-1,0),(13,14,15,1,.5)]:
                u=((tick-contact)/period+phase)%1;z,up=trajectory(u,stride,lift,duty)if not idle else(0,0)
                if idle:ankle_pitch=0.
                elif u<.10:ankle_pitch=-8*(1-u/.10)**2
                elif u>duty-.10 and u<duty:ankle_pitch=18*((u-duty+.10)/.10)**2
                elif u>=duty:ankle_pitch=18*math.cos(math.pi*(u-duty)/(1-duty)/2)**2
                else:ankle_pitch=0.
                foot_rotation=rotation([ankle_pitch,-sign*4,0])
                verts=np.array(old.tmd.obj_verts(sk[foot][0]))[:,:3]
                floor_offset=float((verts@foot_rotation.T)[:,1].max())
                goal=np.array([sign*55.,-floor_offset-up,16.+z])
                w=np.array(mmd.bone_matrices(old,p));h=w[hip,:3,3]
                a=np.array(bind[knee][6:9],float);b=np.array(bind[foot][6:9],float);la=np.linalg.norm(a);lb=np.linalg.norm(b)
                d=goal-h;distance=np.linalg.norm(d)
                if distance>la+lb-.5:clamps+=1;d*=(la+lb-.5)/distance;goal=h+d;distance=np.linalg.norm(d)
                direction=d/distance;pole=np.array([sign*(.32 if running else .20),0,-1.]);pole-=direction*(pole@direction);pole/=np.linalg.norm(pole)
                along=(la*la-lb*lb+distance*distance)/(2*distance)
                joint=h+direction*along+pole*math.sqrt(max(0,la*la-along*along))
                thigh_rotation=align(a,joint-h);calf_rotation=align(b,goal-joint)
                set_rotation(p,hip,w[1,:3,:3].T@thigh_rotation,history)
                set_rotation(p,knee,thigh_rotation.T@calf_rotation,history)
                set_rotation(p,foot,calf_rotation.T@foot_rotation,history)
            # The front and side tassets follow leg clearance instead of staying rigid.
            p[16][3]=round(min(0,p[10][3],p[13][3])*.80-4*4096/360)
            p[16][8]=-53
            for plate,thigh,sign in [(17,10,1),(18,13,-1)]:
                p[plate][3]=round(p[thigh][3]*.85);p[plate][5]=round(sign*3*4096/360)
            p[0][6:9]=[0,0,-speed*tick];out.append(p)
        out[-1][1:]=copy.deepcopy(out[0][1:]);assert clamps==0,(slot,clamps)
        original=old.anims.anims[old.anims.table[slot]];anim=mmd.encode_anim(out,nb,loop_sample=0,events=gait_events,tol=1,repeats=False)
        new.anims.anims.append(anim);new.anims.table[slot]=len(new.anims.anims)-1
        player=mmd.AnimPlayer(anim,nb,slot)
        for tick in range(period*4):
            assert player.tick()
            if tick>0:assert player.base==[0,0,-speed],(slot,tick,player.base)
            for b in range(1,nb):
                assert player.pose[b][:3]==bind[b][:3]
                if b not in [1,16]:assert player.pose[b][6:9]==bind[b][6:9]
        report.append(dict(slot=slot,frames=period+1,loop=loop,stride=stride,lift=lift,duty=duty,hip_height=height,root_units_per_tick=speed,unreachable_targets=clamps,footfall_samples=[]if idle else[0,period//2],stance_foot_speed_matches_root=True))
    import motioncyclelayer
    for anim in new.anims.anims:anim.tail=b''
    new.anims.anims,new.anims.table=motioncyclelayer.share_identical_streams(new.anims.anims,new.anims.table)
    result=new.build();parsed=mmd.MMD.parse(result,nb)
    assert changed_programs(old,parsed)==SLOTS and old.tmd.build()==parsed.tmd.build()
    storage=motionstorage.audit(result,nb);assert storage['fits'],storage
    return result,dict(species=373,recipe='wargreymon-field',generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),source_sha256=SOURCE,output_sha256=hashlib.sha256(result).hexdigest(),changed_slots=SLOTS,mesh_exact=True,all_other_programs_exact=True,checks=report,storage=storage)


def patch_archive(data,model,skel):
    """Append the new model; preserve all other records, assets and offsets."""
    import species,coldsplit
    header=struct.unpack_from(species.HEADER,data,0);assert header[0]==b'DIGI'and len(data)%2048==0
    nb=len(skel);offset=header[5]*2048+373*species.RECORD_SIZE
    record=species.unpack_record(data[offset:offset+species.RECORD_SIZE],373)
    assert record['bones']==skel and record['para']['boneCount']==nb
    start=record['modelSector']*2048;resident=data[start:start+record['modelSize']]
    cold_start=start+((record['modelSize']+2047)//2048)*2048
    old_cold_len=max(((v&0xffff)*4+((v>>16)&0x7fff)*4 for v in coldsplit.entries(resident).values()),default=0)
    candidate=mmd.MMD.parse(model,nb)
    before=mmd.MMD.parse(coldsplit.join(resident,data[cold_start:cold_start+old_cold_len],nb,len(candidate.anims.table)),nb)
    assert changed_programs(before,candidate)==SLOTS
    assert before.tmd.build()==candidate.tmd.build()
    new_resident,new_cold=coldsplit.split(model,nb)
    assert len(new_resident)<=0x18800
    payload=new_resident+b'\0'*(-len(new_resident)%2048)+new_cold
    payload+=b'\0'*(-len(payload)%2048)
    result=bytearray(data);sector=len(result)//2048;result.extend(payload)
    struct.pack_into('<II',result,offset+0x3c,sector,len(new_resident))
    struct.pack_into('<I',result,16,len(result)//2048)
    allowed=set(range(16,20))|set(range(offset+0x3c,offset+0x44))
    assert all(a==b or i in allowed for i,(a,b)in enumerate(zip(data,result)))
    return bytes(result),dict(source_archive_sha256=hashlib.sha256(data).hexdigest(),output_archive_sha256=hashlib.sha256(result).hexdigest(),changed_species=[373],other_records_and_original_assets_exact=True,new_model_sector=sector,new_resident_bytes=len(new_resident),append_bytes=len(payload))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--specimen',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--archive',type=Path);a=p.parse_args()
    import species
    s=json.loads(a.specimen.read_text());s['_path']=str(a.specimen);data,_=species.species_model(s)
    result,report=build(data,s['model']['skeleton']);a.out.mkdir(parents=True,exist_ok=False)
    path=a.out/'373-field.MMD';path.write_bytes(result);s['model']['file']=str(path.resolve());s['model'].pop('slot_aliases',None);s.pop('_path',None)
    if a.archive:
        archive,report['archive_patch']=patch_archive(a.archive.read_bytes(),result,s['model']['skeleton']);(a.out/'DIGI.DAT').write_bytes(archive)
    (a.out/'373-wargreymon.json').write_text(json.dumps(s,indent=2)+'\n');(a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
