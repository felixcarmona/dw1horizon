#!/usr/bin/env python3
"""Reviewed, species-specific field acting profiles for imported bipeds.

Each profile pins an effective source model and maps its actual skeleton. Shared
math handles support, weight and delayed articulation; weapon/armor/cape acting
is selected per character. No automatic profile selection for unreviewed models.
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
from pathlib import Path
import numeric as np
import mmd
import animsheet
import motionstorage
from motiondiscidentity import changed_programs
from tools.models.field_animations.war_greymon import rotation, align, set_rotation

PROFILES={
 404:dict(source='a356b6ba345710ced8e66d49e7f1192e008c849b517360c9e16ccb0e7aead249',bones=24,
          carrier=1,pelvis=2,chest=1,head=15,
          legs=[(5,6,7,[7,8],-1,0),(9,10,11,[11,12],1,.5)],
          arms=[(18,19,-1),(20,21,1)],wings=[(14,1),(17,-1)],front=4,sides=[(13,5,-1),(3,9,1)],
          tracks=70,height_bias=-8,front_out=16,front_follow=.92,style='heavy armored stride'),
 461:dict(source='7d0bdcdbc5c758535753676dbe8c50edaced855466f8e4bd0a7abf2eb14930f7',bones=25,
          carrier=14,pelvis=14,chest=1,head=2,
          legs=[(15,16,17,[17,18],1,0),(19,20,21,[21,22],-1,.5)],
          arms=[(3,4,1),(9,10,-1)],cape=[23,24],
          tracks=70,style='steady cannon arm, heavier sword swing and delayed cape'),
}

PROFILES.update({
 203:dict(source='e1d4c6ba6085661d315a2922120c126f999e31e95f1f6357678e6bde730dd747',bones=21,
          carrier=11,pelvis=11,chest=1,head=3,
          legs=[(15,16,17,[17],1,0),(18,19,20,[20],-1,.5)],arms=[(5,6,1),(8,9,-1)],
          slots=[2,3,4],periods={2:14,3:18,4:8},duties={4:.38},lifts={2:14,3:10,4:24},
          tracks=62,height_bias=-8,support_blend=.5,knee_out_by_slot={4:1.0},validate_ik=True,
          arm_base=20,arm_spread=15,arm_amplitudes={2:18,3:11,4:25},arm_bends={2:20,3:15,4:35},
          native_aux=[2,4,7,10,12,13,14],source_aux=[4],native_head=True,gaze_pitch=3,aux_translation={3:[0,-8,0]},
          native_world_rest={7:[45,-8,0],10:[45,8,0]},native_rest_gain=.2,leans={2:4,3:8,4:14},
          style='upright dragon steps and relaxed claw arms; native neck, jaw, hands and tail acting retained; original idle preserved'),
 180:dict(source='db9d7b42f0384f1fbb0fd008cacb0fff894b1b0f659de33d481ebaf6a81c110c',bones=20,
          carrier=1,pelvis=1,chest=2,head=3,
          legs=[(14,15,16,[16],1,0),(17,18,19,[19],-1,.5)],arms=[(5,6,1),(8,9,-1)],
          slots=[2,3,4],periods={2:10,3:14,4:6},speeds={2:20,3:14,4:50},duties={4:.38},
          lifts={2:12,3:8,4:20},tracks=43,height_bias=-10,sway={2:3,3:3,4:2},bounce={2:2,3:2,4:4},
          arm_amplitudes={2:17,3:11,4:25},arm_bends={2:27,3:30,4:65},wrists=[(7,1),(10,-1)],
          support_blend=.65,arm_spread=28,validate_ik=True,
          style='light short steps and relaxed delayed arms; original idle and engine native tail layer retained'),
 194:dict(source='fbb4d26917623605f5b876019c94f972698114088528ac73370583b716ce4eb3',bones=27,
          carrier=17,pelvis=17,chest=1,head=3,
          legs=[(18,19,20,[20],1,0),(21,22,23,[23],-1,.5)],arms=[(5,6,1),(9,10,-1)],
          slots=[2,3,4],periods={2:12,3:16,4:8},macro_periods={2:36,3:48,4:32},duties={4:.30},
          lifts={2:14,3:14,4:22},tracks=65,height_bias=-8,arm_spread=20,
          native_aux=[2,4,7,8,11,12,13,14,15,16,24,25,26],native_head=True,gaze_pitch=2,support_blend=.35,
          aux_translation={3:[0,-25,0]},native_world_rest={24:[45,0,0]},native_local_rest={25:[-20,0,0],26:[-5,0,0]},native_rest_gain=.2,validate_ik=True,
          style='grounded dragon stride with relaxed claws, native neck/wings/tail acting; original idle preserved'),
 195:dict(source='1a06d92267cbdaa1f79154e0bc5dee99bb7349d79abb4ed816e140e455046c55',bones=20,
          carrier=8,pelvis=8,chest=1,head=2,
          legs=[(12,13,14,[14,15],1,0),(16,17,18,[18,19],-1,.5)],arms=[(4,5,1),(6,7,-1)],
          slots=[2,3,4],periods={2:14,3:18,4:8},duties={4:.38},lifts={2:18,3:12,4:28},
          tracks=55,height_bias=-8,arm_spread=22,arm_amplitudes={2:17,3:11,4:24},arm_bends={2:22,3:27,4:40},
          secondary_sway=[(9,3,.5),(10,2,1),(11,1.5,1.5)],support_blend=.4,validate_ik=True,
          static_offsets={2:[0,0,-10]},
          leans={2:3,3:8,4:22},
          style='upright armored stride, relaxed claw arms and delayed tail; original idle preserved'),
 432:dict(source='1c6dc946b8e1dbb74034f7e4c0df3d6bd0bbd6c29556d755f505e8fcaf93e89d',bones=26,carrier=1,pelvis=11,chest=1,head=8,
          legs=[(12,13,14,[14,15],1,0),(16,17,18,[18,19],-1,.5)],arms=[(2,3,-1),(5,6,1)],
          slots=[2,3,4],periods={2:16,3:20,4:10},duties={4:.36},
          lifts={2:16,3:10,4:30},tracks=50,height_bias=-10,sway={2:7,3:5,4:5},bounce={2:3,3:3,4:6},
          leans={2:2,3:6,4:12},arm_amplitudes={2:12,3:8,4:25},arm_bends={2:15,3:23,4:35},arm_spread=25,
          native_aux=[4,7,9,10,20,21,22,23,24,25],native_head=True,gaze_pitch=0,support_blend=.5,
          aux_rotation_offsets={9:[30,0,0]},
          style='supple feline weight transfer with native hair, wrists and streamers; original idle preserved'),
 354:dict(source='2ed6036bb45479090f9417bd62f041928d516dffb65b4daeae30b5d9e33d604b',bones=22,
          carrier=1,pelvis=2,chest=1,head=15,
          legs=[(3,4,5,[5,6],1,0),(7,8,9,[9,10],-1,.5)],arms=[(16,17,-1),(19,20,1)],
          slots=[2,3,4],periods={2:12,3:16,4:8},speeds={2:20,3:14,4:52},duties={4:.36},
          lifts={2:18,3:12,4:38},tracks=28,sway={2:5,3:4,4:3},bounce={2:3.5,3:3,4:6},
          leans={2:3,3:7,4:20},trailing_run=True,tail_run_lift={11:12},arm_amplitudes={2:16,3:12,4:20},arm_bends={2:24,3:28,4:48},
          native_aux=[11,12,13,14,18,21],native_head=True,gaze_pitch=6,support_blend=.65,
          style='light fox steps, native tail/wrist/head acting; original idle preserved'),
 197:dict(source='46822d642739663627522e502cc4dbe20cc92f898b7140e2fa06434ebb483597',bones=25,
          carrier=1,pelvis=1,chest=2,head=4,
          legs=[(5,6,7,[7],-1,0),(9,10,11,[11],1,.5)],arms=[(13,14,-1),(18,19,1)],
          periods={2:14,3:20,4:8},lifts={2:24,3:16,4:45},tracks=50,
          native_aux=[3,15,16,17,20,21,22,23,24],aux_translation={17:[-28,0,0],22:[28,0,0]},
          arm_spread=20,native_head=True,gaze_pitch=1,support_blend=.45,macro_floor=True,encoding_tol=2,
          style='compact armored stride, native head/hand/armor acting'),
 403:dict(source='d2de28df42d0b31422e04d03da0b1519114b404001f2085a48e35ff73488c980',bones=31,
          carrier=1,pelvis=2,chest=1,head=28,
          legs=[(3,4,5,[5,6],1,0),(8,9,10,[10,11],-1,.5)],arms=[(16,17,1),(20,21,-1)],
          slots=[2,3,4],periods={2:14,3:24,4:8},lifts={2:24,3:16,4:48},tracks=48,height_bias=-6,encoding_tol=3,
          native_aux=[12,13,14,15,18,22,23,24,25,26,27,29,30],native_head=True,gaze_pitch=-2,steady_arm=-1,support_blend=.4,
          run_arm_spread={1:25},arm_spread_by_slot={3:{1:25}},
          style='steady gun arm, natural support and native wings/tail/wrist acting; original idle preserved'),
})

SLOTS=[0,2,3,4]


def support_cloud(model,sk,pose,foot,bones):
    w=np.array(mmd.bone_matrices(model,pose));inv=np.linalg.inv(w[foot]);points=[]
    for b in bones:
        r=inv@w[b];v=np.array(model.tmd.obj_verts(sk[b][0]))[:,:3];points.extend(v@r[:3,:3].T+r[:3,3])
    return np.array(points)


def trajectory(u,stride,lift,duty):
    if u<duty:return -stride+2*stride*u/duty,0.
    v=(u-duty)/(1-duty);h=3*v*v-2*v*v*v;velocity=2*stride*(1-duty)/duty
    return stride*(1-2*h)+velocity*(2*v*v*v-3*v*v+v),lift*math.sin(math.pi*v)**2


def rotation_gain(delta,gain):
    q=mmd.quat(*mmd.matrix_euler(delta))
    return np.array(mmd.quat_matrix(mmd._slerp((0,0,0,1),q,gain)))


def build(data,sk):
    digest=hashlib.sha256(data).hexdigest();matches=[(sid,p)for sid,p in PROFILES.items()if p['source']==digest]
    if len(matches)!=1:raise ValueError('No reviewed field-acting profile for this effective source model')
    sid,cfg=matches[0];n=len(sk);assert n==cfg['bones'];mmd.exe().skeleton[sid]=sk;mmd.exe().bone_count[sid]=n
    old=mmd.MMD.parse(data,n);old.type=sid;new=copy.deepcopy(old)
    native=copy.deepcopy(animsheet.slot_frames(old,n,33)[0][0]);bind=copy.deepcopy(native);bind[0]=[4096]*3+[0]*6
    selected={cfg[k]for k in ['carrier','pelvis','chest','head']}
    selected.update(b for hip,knee,foot,_,_,_ in cfg['legs']for b in [hip,knee,foot])
    selected.update(b for a,e,_ in cfg['arms']for b in [a,e]);selected.update(b for b,_ in cfg.get('wings',[]));selected.update(cfg.get('cape',[]))
    if cfg.get('front'):selected.add(cfg['front']);selected.update(b for b,_,_ in cfg['sides'])
    for b in selected:bind[b][3:6]=[0,0,0]
    for b in range(n):assert bind[b][:3]==[4096]*3 or(sk[b][0]<0 and bind[b][:3]==[0]*3)
    first_side=cfg['legs'][0][4]
    carrier,pelvis,chest=cfg['carrier'],cfg['pelvis'],cfg['chest'];bind[carrier][6:9]=[0,0,0]
    neutral=np.array(mmd.bone_matrices(old,bind));clouds={foot:support_cloud(old,sk,bind,foot,bones)for _,_,foot,bones,_,_ in cfg['legs']}
    native_world_head=np.array(mmd.bone_matrices(old,native))[cfg['head'],:3,:3]
    native_frames,_,_=animsheet.slot_frames(old,n,33)
    slots=cfg.get('slots',SLOTS);report=[]
    for slot in slots:
        source_frames,_,events=animsheet.slot_frames(old,n,slot);idle=slot==0;tired=slot==3;running=slot==4
        if any(kind!='sound'for _,kind,_ in events):raise ValueError(f'{sid} slot{slot} needs an explicit non-audio event policy')
        period=len(source_frames)-1 if idle else cfg.get('periods',{}).get(slot,12 if running else 24 if tired else 20)
        duration=period if not cfg.get('native_aux') else period*max(1,(math.floor if cfg.get('macro_floor')else round)((len(native_frames)-1)/period))
        duration=cfg.get('macro_periods',{}).get(slot,duration);assert duration%period==0
        speed=0 if idle else cfg.get('speeds',{}).get(slot,52 if running else 15 if tired else 22);duty=cfg.get('duties',{}).get(slot,.42 if running else .64 if tired else .56)
        stride=speed*period*duty/2;lift=0 if idle else cfg.get('lifts',{}).get(slot,62 if running else 22 if tired else 32)
        sound=next((i for _,kind,i in events if kind=='sound'),None)
        authored_events=[]if idle or sound is None else[(tick,'sound',dict(sound,frame=tick+1))for tick in range(0,duration,period//2)]
        hip,knee,foot,_,_,_=cfg['legs'][0];la=np.linalg.norm(bind[knee][6:9]);lb=np.linalg.norm(bind[foot][6:9]);length=la+lb
        sole=float(clouds[foot][:,1].max());offset_y=float(neutral[hip,1,3])
        height=length-18+offset_y+sole if idle else math.sqrt((length-(14 if running else 4))**2-stride**2)+offset_y+sole+3
        height+=cfg.get('height_bias',0)
        frames=[];hist={};unreachable=0;max_foot_error=0.
        for tick in range(duration+1):
            theta=2*math.pi*tick/period;wave=math.sin(theta);p=copy.deepcopy(bind)
            for b,offset in cfg.get('static_offsets',{}).items():
                p[b][6:9]=[v+delta for v,delta in zip(p[b][6:9],offset)]
            if cfg.get('native_aux'):
                from motiontailspace import interpolate_pose
                t=tick*(len(native_frames)-1)/duration;i=min(int(t),len(native_frames)-2)
                reference=interpolate_pose(native_frames[i],native_frames[i+1],round((t-i)*4096))
                for b in cfg['native_aux']:p[b][3:6]=reference[b][3:6]
                for b,offset in cfg.get('aux_translation',{}).items():
                    p[b][6:9]=[v+delta for v,delta in zip(p[b][6:9],offset)]
                for b,offset in cfg.get('aux_rotation_offsets',{}).items():
                    p[b][3:6]=[v+round(delta*4096/360)for v,delta in zip(p[b][3:6],offset)]
                if running:
                    for b,degrees in cfg.get('tail_run_lift',{}).items():p[b][3]+=round(degrees*4096/360)
            if cfg.get('source_aux'):
                from motiontailspace import interpolate_pose
                source_t=tick*(len(source_frames)-1)/duration
                source_i=min(int(source_t),len(source_frames)-2)
                source_pose=interpolate_pose(source_frames[source_i],source_frames[source_i+1],round((source_t-source_i)*4096))
                for b in cfg['source_aux']:p[b][3:6]=source_pose[b][3:6]
            sway=cfg.get('sway',{}).get(slot,1.3 if idle else 5 if running else 7 if tired else 9)*math.sin(theta-.18)
            bounce=2*math.cos(theta-.2)if idle else cfg.get('bounce',{}).get(slot,9 if running else 5 if tired else 6)*math.cos(2*theta-(.9 if running else .25))+1.5*math.cos(4*theta-.5)
            p[carrier][6:9]=[round(first_side*sway),round(-height+bounce),0]
            lean=cfg.get('leans',{}).get(slot,2 if idle else 10 if running else 8 if tired else 4)
            pelvis_r=rotation([0,(.5 if idle else first_side*4)*math.cos(theta),(.5 if idle else -first_side*2.5)*wave])
            chest_yaw=(1 if idle else -first_side*6)*math.cos(theta-.12);chest_pitch=lean+(1 if idle else 1.5)*math.sin(2*theta-.65)
            chest_r=rotation([chest_pitch,chest_yaw,(first_side*.25 if idle else first_side*1.5)*math.sin(theta-.35)])
            if carrier==chest:
                set_rotation(p,chest,chest_r,hist);set_rotation(p,pelvis,chest_r.T@pelvis_r,hist)
            else:
                set_rotation(p,pelvis,pelvis_r,hist);set_rotation(p,chest,pelvis_r.T@chest_r,hist)
            if cfg.get('native_head'):
                reference_world=np.array(mmd.bone_matrices(old,reference))[cfg['head'],:3,:3]
                desired=reference_world@native_world_head.T@rotation([cfg.get('gaze_pitch',2),0,0])
                parent=np.array(mmd.bone_matrices(old,p))[sk[cfg['head']][1],:3,:3]
                set_rotation(p,cfg['head'],parent.T@desired,hist)
            else:set_rotation(p,cfg['head'],rotation([-chest_pitch*.7,-chest_yaw*.7,.4*math.sin(theta-.6)]),hist)
            for shoulder,elbow,sign in cfg['arms']:
                # Positive Z spreads a left arm (-X); cannon/sword have distinct inertia.
                left=sign<0;spread=-sign;phase=math.cos(theta-.18)*sign*first_side;lag=math.cos(theta-.8)*sign*first_side
                amp=cfg.get('arm_amplitudes',{}).get(slot,1.2 if idle else 23 if running else 13 if tired else 19)
                bend=cfg.get('arm_bends',{}).get(slot,62 if running else 40)
                if sid==461:amp*=.65 if left else .85;bend+=8 if left else 0
                if cfg.get('steady_arm')==sign:amp*=.6;bend+=20
                if running and cfg.get('trailing_run'):
                    p[shoulder][3:6]=[round((40+4*phase)*4096/360),0,round(spread*5*4096/360)]
                    p[elbow][3:6]=[round((-15+3*lag)*4096/360),0,round(spread*4*4096/360)]
                else:
                    arm_spread=cfg.get('run_arm_spread',{}).get(sign,cfg.get('arm_spread',12))if running else cfg.get('arm_spread',12)
                    arm_spread=cfg.get('arm_spread_by_slot',{}).get(slot,{}).get(sign,arm_spread)
                    p[shoulder][3:6]=[round((cfg.get('arm_base',-8)+amp*phase)*4096/360),0,round(spread*arm_spread*4096/360)]
                    p[elbow][3:6]=[round((-bend+(2 if idle else 8)*lag)*4096/360),0,round(spread*12*4096/360)]
            for b,sign in cfg.get('wings',[]):
                p[b][3:6]=[round((26+.7*math.sin(theta-.9))*4096/360),round(-sign*14*4096/360),0]
            for b,sign in cfg.get('wrists',[]):
                base=np.array(mmd.rot_matrix(*bind[b][3:6]));set_rotation(p,b,base@rotation([sign*2*math.sin(theta-1.1),0,sign*.8*math.cos(theta-.9)]),hist)
            for b,amplitude,lag in cfg.get('secondary_sway',[]):
                p[b][3]+=round(amplitude*(1.5 if running else 1)*math.sin(theta-lag)*4096/360)
            for b,rest in cfg.get('native_local_rest',{}).items():
                delta=np.array(mmd.rot_matrix(*reference[b][3:6]))@np.array(mmd.rot_matrix(*native[b][3:6])).T
                set_rotation(p,b,rotation_gain(delta,cfg['native_rest_gain'])@rotation(rest),hist)
            for b,rest in cfg.get('native_world_rest',{}).items():
                parent=np.array(mmd.bone_matrices(old,p))[sk[b][1],:3,:3]
                delta=np.array(mmd.bone_matrices(old,reference))[b,:3,:3]@np.array(mmd.bone_matrices(old,native))[b,:3,:3].T
                desired=rotation_gain(delta,cfg['native_rest_gain'])@rotation(rest)
                set_rotation(p,b,parent.T@desired,hist)
            if cfg.get('cape'):
                a,b=cfg['cape'];p[a][8]+=12;p[a][3:6]=[round((25+2*math.sin(theta-.8))*4096/360),round(2*math.sin(theta-.8)*4096/360),0];p[b][3:6]=[round((18+(5 if running else 3)*math.sin(theta-1.4))*4096/360),0,0]
            if cfg.get('support_blend')and not idle:
                world=np.array(mmd.bone_matrices(old,p));limits=[]
                for hip,knee,foot,bones,sign,phase in cfg['legs']:
                    u=(tick/period+phase)%1;z,up=trajectory(u,stride,lift,duty)
                    if u<.1:pitch=-8*(1-u/.1)**2
                    elif duty-.1<u<duty:pitch=18*((u-duty+.1)/.1)**2
                    elif u>=duty:pitch=18*math.cos(math.pi*(u-duty)/(1-duty)/2)**2
                    else:pitch=0.
                    foot_r=rotation([pitch,-sign*cfg.get('toe_out',4),0]);floor=float((clouds[foot]@foot_r.T)[:,1].max())
                    h=world[hip,:3,3];dx=sign*cfg['tracks']-h[0];dz=z-h[2]
                    length=np.linalg.norm(bind[knee][6:9])+np.linalg.norm(bind[foot][6:9]);vertical=math.sqrt(max(1,(length-4)**2-dx*dx-dz*dz))
                    limits.append(vertical+(h[1]-p[carrier][7])+floor+up)
                current=-p[carrier][7];weight=cfg['support_blend'];p[carrier][7]=-round((1-weight)*current+weight*min(limits))
            for hip,knee,foot,bones,sign,phase in cfg['legs']:
                u=(tick/period+phase)%1;z,up=trajectory(u,stride,lift,duty)if not idle else(0,0)
                if idle:pitch=0.
                elif u<.1:pitch=-8*(1-u/.1)**2
                elif duty-.1<u<duty:pitch=18*((u-duty+.1)/.1)**2
                elif u>=duty:pitch=18*math.cos(math.pi*(u-duty)/(1-duty)/2)**2
                else:pitch=0.
                target_r=rotation([pitch,-sign*cfg.get('toe_out',4),0]);floor=float((clouds[foot]@target_r.T)[:,1].max());goal=np.array([sign*cfg['tracks'],-floor-up,z],float)
                w=np.array(mmd.bone_matrices(old,p));h=w[hip,:3,3];a=np.array(bind[knee][6:9],float);b=np.array(bind[foot][6:9],float);la=np.linalg.norm(a);lb=np.linalg.norm(b)
                d=goal-h;distance=np.linalg.norm(d)
                if cfg.get('validate_ik')and distance<abs(la-lb)+.5:unreachable+=1
                if distance>la+lb-.5:unreachable+=1;d*=(la+lb-.5)/distance;goal=h+d;distance=np.linalg.norm(d)
                direction=d/distance;pole=np.array([sign*cfg.get('knee_out_by_slot',{}).get(slot,.3 if running else .2),0,-1.]);pole-=direction*(pole@direction);pole/=np.linalg.norm(pole)
                along=(la*la-lb*lb+distance*distance)/(2*distance);joint=h+direction*along+pole*math.sqrt(max(0,la*la-along*along))
                upper_r=align(a,joint-h);lower_r=align(b,goal-joint)
                set_rotation(p,hip,w[sk[hip][1],:3,:3].T@upper_r,hist);set_rotation(p,knee,upper_r.T@lower_r,hist);set_rotation(p,foot,lower_r.T@target_r,hist)
                if cfg.get('validate_ik'):
                    actual=np.array(mmd.bone_matrices(old,p))[foot,:3,3];max_foot_error=max(max_foot_error,float(np.linalg.norm(actual-goal)))
            if cfg.get('front'):
                left_hip,right_hip=[leg[0]for leg in cfg['legs']];p[cfg['front']][3]=round(min(0,p[left_hip][3],p[right_hip][3])*cfg.get('front_follow',.8)-4*4096/360);p[cfg['front']][8]=bind[cfg['front']][8]-cfg.get('front_out',8)
                for plate,thigh,sign in cfg['sides']:p[plate][3]=round(p[thigh][3]*.85);p[plate][5]=round(-sign*3*4096/360)
            p[0][6:9]=[0,0,-speed*tick];frames.append(p)
        frames[-1][1:]=copy.deepcopy(frames[0][1:]);assert unreachable==0,(sid,slot,unreachable,height)
        if cfg.get('validate_ik'):assert max_foot_error<1,(sid,slot,max_foot_error)
        anim=mmd.encode_anim(frames,n,loop_sample=0,events=authored_events,tol=cfg.get('encoding_tol',1),repeats=False)
        new.anims.anims.append(anim);new.anims.table[slot]=len(new.anims.anims)-1
        player=mmd.AnimPlayer(anim,n,slot)
        for tick in range(duration*4):
            assert player.tick()
            if tick>0:assert player.base==[0,0,-speed]
            for b in range(n):assert player.pose[b][:3]==bind[b][:3]
        max_codec_foot_error=0.
        if cfg.get('validate_ik'):
            decoded=animsheet.slot_frames(new,n,slot)[0];assert len(decoded)==len(frames)
            feet=[leg[2]for leg in cfg['legs']]
            for authored,encoded in zip(frames,decoded):
                a=np.array(mmd.bone_matrices(old,authored))[feet,:3,3];e=np.array(mmd.bone_matrices(old,encoded))[feet,:3,3]
                max_codec_foot_error=max(max_codec_foot_error,float(np.linalg.norm(a-e,axis=1).max()))
            assert max_codec_foot_error<2.5,(sid,slot,max_codec_foot_error)
        report.append(dict(slot=slot,period=period,macro_period=duration,speed=speed,stride=stride,duty=duty,lift=lift,carrier_height=height,unreachable_targets=unreachable))
        if cfg.get('validate_ik'):report[-1].update(max_authored_foot_target_error=max_foot_error,max_encoded_foot_position_error=max_codec_foot_error)
    import motioncyclelayer
    for a in new.anims.anims:a.tail=b''
    new.anims.anims,new.anims.table=motioncyclelayer.share_identical_streams(new.anims.anims,new.anims.table)
    result=new.build();parsed=mmd.MMD.parse(result,n);assert changed_programs(old,parsed)==slots and old.tmd.build()==parsed.tmd.build()
    storage=motionstorage.audit(result,n);assert storage['fits'],storage
    return result,dict(species=sid,profile_style=cfg['style'],source_sha256=digest,output_sha256=hashlib.sha256(result).hexdigest(),changed_slots=slots,mesh_exact=True,other_programs_exact=True,checks=report,storage=storage)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--specimen',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    import species
    s=json.loads(a.specimen.read_text());s['_path']=str(a.specimen);raw,_=species.species_model(s);data,report=build(raw,s['model']['skeleton']);a.out.mkdir(parents=True,exist_ok=False)
    model=a.out/f'{s["id"]}-acting.MMD';model.write_bytes(data);s['model']['file']=str(model.resolve());s['model'].pop('slot_aliases',None);s.pop('_path',None)
    (a.out/'specimen.json').write_text(json.dumps(s,indent=2)+'\n');(a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
