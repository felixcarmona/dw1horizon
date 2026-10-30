#!/usr/bin/env python3
"""Monmon's field torso follows its own stride; legs retain their world poses.

Torso and pelvis move together; hip roots compensate. Relaxed arms have
opposite shoulder swings and delayed elbow/wrist motion. Head and equipment
keep local acting. No mesh,
navigation, event, gait duration or animation outside2/3/4 is changed.
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
from motiontailspace import interpolate_pose


CHANNELS={(b,c)for b in (1,3,9)for c in range(3,9)}|{(b,c)for b in (12,13,14,17,18,19)for c in range(3,6)}


def replace(original, samples, loop, nb):
    encoded=mmd.encode_anim(samples,nb,loop_sample=loop,tol=0,repeats=False)
    result=copy.deepcopy(original)
    for b,c in CHANNELS:
        result.pose[b-1][c if result.has_scale else c-3]=encoded.pose[b-1][c if encoded.has_scale else c-3]
    for ins in result.instrs:
        if ins['op']=='key':
            for group in ins['bones']:
                group['vals']={k:v for k,v in group['vals'].items()if(group['bone'],mmd.CHANNELS.index(k))not in CHANNELS}
            ins['bones']=[g for g in ins['bones']if g['vals']]
    for ins in encoded.instrs:
        if ins['op']!='key':continue
        key=copy.deepcopy(ins)
        for group in key['bones']:
            group['vals']={k:v for k,v in group['vals'].items()if(group['bone'],mmd.CHANNELS.index(k))in CHANNELS}
        key['bones']=[g for g in key['bones']if g['vals']]
        if not key['bones']:continue
        existing=next((i for i in result.instrs if i['op']=='key'and i['frame']==key['frame']),None)
        if existing is not None:existing['bones'].extend(key['bones']);continue
        at=len(result.instrs)-1
        for j,other in enumerate(result.instrs):
            f=other.get('frame')
            if other['op']=='loop_start':
                f=next((x.get('frame')for x in result.instrs[j+1:]if x.get('frame')is not None),None)
            if f is not None and f>key['frame']:at=j;break
        result.instrs.insert(at,key)
    return result


def build(data,skel):
    if hashlib.sha256(data).hexdigest()!='390d5940e40c133029bd169cd59d1a67b42e5a51dcfb7c178437378716056b25':
        raise ValueError('Monmon upper-body recipe requires the reviewed ImportedModels source with aliases applied exactly once')
    nb=len(skel);old=mmd.MMD.parse(data,nb);old.type=352;new=copy.deepcopy(old)
    mmd.exe().skeleton[352]=skel;mmd.exe().bone_count[352]=nb
    assert skel[1][1]==0 and skel[2][1]==1
    report=[]
    for slot,yaw,roll,pitch,period in [(2,6.,3.,2.,8),(3,4.,2.,1.,12),(4,7.,3.5,3.,8)]:
        fs,loop,events=animsheet.slot_frames(old,nb,slot)
        assert loop is not None and loop>0
        worlds=np.array([mmd.bone_matrices(old,p)for p in fs])
        separation=worlds[:,4,2,3]-worlds[:,10,2,3]
        center=float(np.mean(separation[loop:-1]));amp=float(np.max(np.abs(separation[loop:-1]-center)))
        assert amp>1
        drive=(separation-center)/amp;steady=len(fs)-loop-1;out=[];previous={}
        cadence=2*np.pi*np.arange(steady)/period
        sine,cosine=np.linalg.lstsq(np.column_stack([np.sin(cadence),np.cos(cadence)]),drive[loop:-1],rcond=None)[0]
        arm_phase=math.atan2(cosine,sine)
        for tick,source in enumerate(fs):
            p=copy.deepcopy(source)
            # A smooth prefix, followed by the original repeating stride phase.
            u=min(1.,tick/loop);weight=u*u*(3-2*u)
            offset=loop+(tick-loop+period//4)%steady
            side=float(drive[offset])
            angles=[pitch*(1-float(drive[tick])**2),yaw*float(drive[tick]),roll*side]
            delta=np.array(mmd.rot_matrix(*[x*weight*4096/360 for x in angles]))
            r1=np.array(mmd.rot_matrix(*source[1][3:6]))
            assert source[1][:3]==source[2][:3]==[4096]*3
            pivot=np.array(source[2][6:9],float)
            p[1][6:9]=np.round(np.array(source[1][6:9])+r1@(pivot-delta@pivot)).astype(int).tolist()
            for b,rotation in [(1,r1@delta)]:
                angle=mmd.matrix_euler(rotation,previous.get(b));p[b][3:6]=[round(x)for x in angle];previous[b]=angle
            parent=np.array(mmd.bone_matrices(old,p))[2]
            for b in [3,9]:
                local=np.linalg.inv(parent)@worlds[tick,b]
                rotation=local[:3,:3]@np.diag(4096/np.array(source[b][:3],float))
                angle=mmd.matrix_euler(rotation,previous.get(b));p[b][3:6]=[round(x)for x in angle];previous[b]=angle
                p[b][6:9]=np.round(local[:3,3]).astype(int).tolist()
            # Relax the guarded forward-fist stance. Each joint has its own
            # phase: shoulder leads, elbow follows, wrist settles last.
            running=slot==4
            for shoulder,elbow,wrist,sign in [(12,13,14,1),(17,18,19,-1)]:
                theta=2*math.pi*(tick-loop)/period+arm_phase
                phase=math.sin(theta)*sign
                lag=math.sin(theta-.65)*sign
                late=math.sin(theta-1.1)*sign
                target={shoulder:[(30 if running else 22)*phase, 3*side*sign, -sign*((45 if running else 39)+2*side)],
                        elbow:[-(58 if running else 44)+(12 if running else 9)*lag, 0, 0],
                        wrist:[-12+6*late, 2*lag*sign, 0]}
                for b,angles in target.items():
                    # Quaternion interpolation keeps the entry posture continuous.
                    goal=copy.deepcopy(source);goal[b][3:6]=[round(a*4096/360)for a in angles]
                    p[b][3:6]=interpolate_pose(source,goal,round(weight*4096))[b][3:6]
            if tick==0:p=copy.deepcopy(source)
            out.append(p)
        # Preserve the exact native macro seam after Euler quantization.
        out[-1][1:]=copy.deepcopy(out[loop][1:])
        anim=replace(old.anims.anims[old.anims.table[slot]],out,loop,nb)
        new.anims.anims.append(anim);new.anims.table[slot]=len(new.anims.anims)-1
        player=mmd.AnimPlayer(anim,nb,slot);source_player=mmd.AnimPlayer(old.anims.anims[old.anims.table[slot]],nb,slot)
        max_support=0.;max_pelvis=0.
        for tick in range(len(fs)*4):
            assert player.tick()and source_player.tick()
            assert player.root==source_player.root and player.base==source_player.base
            assert player.events==source_player.events
            for b in range(nb):
                for c in range(9):
                    if(b,c)not in CHANNELS:assert player.pose[b][c]==source_player.pose[b][c],(slot,tick,b,c)
            wa=np.array(mmd.bone_matrices(old,source_player.pose));wb=np.array(mmd.bone_matrices(new,player.pose))
            for b in [4,5,10,11]:
                verts=np.array(old.tmd.obj_verts(skel[b][0]))[:,:3]
                a=verts@wa[b,:3,:3].T+wa[b,:3,3];z=verts@wb[b,:3,:3].T+wb[b,:3,3]
                max_support=max(max_support,float(np.linalg.norm(z-a,axis=1).max()))
            max_pelvis=max(max_pelvis,float(np.max(np.abs(wa[2]-wb[2]))))
        assert max_support<1.0,(slot,max_support)
        assert [i for i in anim.instrs if i['op']not in('key',)]==[i for i in old.anims.anims[old.anims.table[slot]].instrs if i['op']not in('key',)]
        report.append(dict(slot=slot,samples=len(fs),loop_sample=loop,own_leg_period=period,yaw_degrees=yaw,roll_degrees=roll,pitch_degrees=pitch,arm_shoulder_swing_degrees=30 if slot==4 else 22,arm_elbow_rest_degrees=-58 if slot==4 else -44,arm_phase_lags_radians=[0,.65,1.1],max_support_vertex_difference=max_support,max_pelvis_matrix_difference=max_pelvis,root_events_and_other_channels_exact=True))
    # Replaced streams can otherwise survive as unconsumed parse tails. Keep
    # every referenced program through END, sharing only identical programs.
    import motioncyclelayer
    for anim in new.anims.anims:anim.tail=b''
    new.anims.anims,new.anims.table=motioncyclelayer.share_identical_streams(new.anims.anims,new.anims.table)
    result=new.build();parsed=mmd.MMD.parse(result,nb)
    assert changed_programs(old,parsed)==[2,3,4]and old.tmd.build()==parsed.tmd.build()
    storage=motionstorage.audit(result,nb);assert storage['fits'],storage
    return result,dict(species=352,source_sha256=hashlib.sha256(data).hexdigest(),output_sha256=hashlib.sha256(result).hexdigest(),generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),changed_slots=[2,3,4],changed_bones=[1,3,9,12,13,14,17,18,19],mesh_unchanged=True,all_other_programs_exact=True,checks=report,storage=storage,limits='Articulated field-gait recipe; hip compensation is quantized and is not foot-planting IK. Other contexts retain their original programs.')


def patch_archive(data,model,skel):
    """Append the new model; preserve all other records, assets and offsets."""
    import species,coldsplit
    header=struct.unpack_from(species.HEADER,data,0);assert header[0]==b'DIGI'and len(data)%2048==0
    nb=len(skel);offset=header[5]*2048+352*species.RECORD_SIZE
    record=species.unpack_record(data[offset:offset+species.RECORD_SIZE],352)
    assert record['bones']==skel and record['para']['boneCount']==nb
    start=record['modelSector']*2048;resident=data[start:start+record['modelSize']]
    cold_start=start+((record['modelSize']+2047)//2048)*2048
    old_cold_len=max(((v&0xffff)*4+((v>>16)&0x7fff)*4 for v in coldsplit.entries(resident).values()),default=0)
    candidate=mmd.MMD.parse(model,nb)
    before=mmd.MMD.parse(coldsplit.join(resident,data[cold_start:cold_start+old_cold_len],nb,len(candidate.anims.table)),nb)
    assert changed_programs(before,candidate)==[2,3,4]
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
    return bytes(result),dict(source_archive_sha256=hashlib.sha256(data).hexdigest(),output_archive_sha256=hashlib.sha256(result).hexdigest(),changed_species=[352],other_records_and_original_assets_exact=True,new_model_sector=sector,new_resident_bytes=len(new_resident),append_bytes=len(payload))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--specimen',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--archive',type=Path);a=p.parse_args()
    import species
    sp=json.loads(a.specimen.read_text());sp['_path']=str(a.specimen)
    data,_=species.species_model(sp);result,report=build(data,sp['model']['skeleton'])
    a.out.mkdir(parents=True,exist_ok=False);path=a.out/'352-upperbody.MMD';path.write_bytes(result)
    sp['model']['file']=str(path.resolve());sp['model'].pop('slot_aliases',None);sp.pop('_path',None)
    if a.archive:
        archive,report['archive_patch']=patch_archive(a.archive.read_bytes(),result,sp['model']['skeleton'])
        (a.out/'DIGI.DAT').write_bytes(archive)
    (a.out/'352-monmon.json').write_text(json.dumps(sp,indent=2)+'\n');(a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
