#!/usr/bin/env python3
"""Audit every logical gait/native-tail phase combination on a local model.

Independent clocks require a Cartesian check, not just one phase-locked reel.
Triangle diagnostics exclude coplanar/touching cases and are not a complete
collision/containment or visual-quality proof. Generated reports contain only
aggregates and phase indices, never animation arrays or mesh assets.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import numeric as np
import mmd
import animsheet
import motionquality as Q
import motionloops


def interpolate_pose(first,second,alpha):
    """Nominal engine fixed-alpha SRT lerp, including shortest Euler arcs."""
    if not 0<=alpha<=4096 or len(first)!=len(second):raise ValueError('invalid interpolation input')
    result=[]
    for a,b in zip(first,second):
        if len(a)!=9 or len(b)!=9:raise ValueError('expected nine native channels')
        pose=[]
        for j,(old,new) in enumerate(zip(a,b)):
            old=int(old);delta=int(new)-old
            if 3<=j<6:delta=(delta+2048)%4096-2048
            pose.append(old+((delta*alpha+2048)>>12))
        result.append(pose)
    return result


def audit(model_path,recipe_path,slots,coverage='all-body',subframes=1):
    if subframes not in (1,3):raise ValueError('supported subframes: logical ticks1 or nominal60fps3')
    recipe=json.loads(recipe_path.read_text());sid=recipe['species'];model=mmd.MMD.load(str(model_path),sid);sk=mmd.exe().skeleton[sid];body=recipe['body'];donor_count=mmd.exe().bone_count[recipe['rig_rebind']['donor']];tail=sorted(int(b) for b,d in recipe['rig_rebind']['map'].items() if d>=donor_count);legs=sorted({b for leg in recipe['legs'] for b in leg['chain']})
    if not tail or any(sk[b][1] not in tail and sk[b][1]!=body for b in tail):raise ValueError('tail must attach directly to declared body')
    local=Q.local_triangles(model,sk);source,loop,_=animsheet.slot_frames(model,len(sk),33)
    if loop!=0:raise ValueError('expected a simple full native33 loop')
    source=source[:-1];relative=[]
    for subframe in range(subframes):
        phases=[];alpha=subframe*4096//subframes
        for phase in range(len(source)):
            pose=interpolate_pose(source[phase],source[(phase+1)%len(source)],alpha);pose[0]=[4096,4096,4096,0,0,0,0,0,0];world=np.array(mmd.bone_matrices(model,pose));inverse=np.linalg.inv(world[body]);phases.append({b:inverse@world[b] for b in tail})
        relative.append(phases)
    if coverage=='legacy':
        pairs=[(t,leg) for t in tail for leg in legs]+[(t,b) for t in tail[1:] for b in [body,2,3,7,10] if b not in tail]
    elif coverage=='all-body':
        # Directly joined meshes may share their joint surface. Every other
        # body mesh is checked, including tail-base versus hands/forearms.
        pairs=[(t,b) for t in tail for b in local if b not in tail
               and sk[t][1]!=b and sk[b][1]!=t]
    else:raise ValueError('unknown collision coverage')
    reports=[]
    for slot in slots:
        complete,_,_=animsheet.slot_frames(model,len(sk),slot);frames=complete[:-1];crossings={};examples=[];max_y=-float('inf');worst=None
        samples=[(tick,subframe,interpolate_pose(pose,complete[tick+1],subframe*4096//subframes)) for tick,pose in enumerate(frames) for subframe in range(subframes)]
        foot_max={leg['chain'][-1]:-float('inf') for leg in recipe['legs']}
        for tick,subframe,pose in samples:
            pose=copy.deepcopy(pose);pose[0]=[4096,4096,4096,0,0,0,0,0,0];world=np.array(mmd.bone_matrices(model,pose));fixed={b:tris@world[b,:3,:3].T+world[b,:3,3] for b,tris in local.items() if b not in tail}
            for b in foot_max:foot_max[b]=max(foot_max[b],float(fixed[b][:,:,1].max()))
            for phase,rel in enumerate(relative[subframe]):
                triangles={}
                for b in tail:
                    matrix=world[body]@rel[b];triangles[b]=local[b]@matrix[:3,:3].T+matrix[:3,3]
                    y=float(triangles[b][:,:,1].max())
                    if y>max_y:max_y=y;worst=dict(primary_sample=tick,tail_sample=phase,tail_bone=b,subframe=subframe,alpha_fixed=subframe*4096//subframes)
                for a,b in pairs:
                    second=triangles[b] if b in triangles else fixed[b]
                    if Q.collide(triangles[a],second):
                        key=f'{a}-{b}';crossings[key]=crossings.get(key,0)+1
                        if len(examples)<24:examples.append(dict(primary_sample=tick,tail_sample=phase,pair=[a,b],subframe=subframe,alpha_fixed=subframe*4096//subframes))
        reports.append(dict(slot=slot,primary_samples=len(frames),primary_evaluations=len(samples),native_tail_samples=len(source),combinations=len(samples)*len(source),max_tail_y_relative_entity=max_y,max_foot_y_relative_entity=foot_max,worst_floor_phase=worst,triangle_crossings_by_pair=crossings,first_crossing_examples=examples,status='requires_review' if crossings or max_y>0 else 'sampled_tail_diagnostics_clear'))
        print('slot',slot,'pairs',len(samples)*len(source),'maxY',round(max_y,3),'crossings',crossings,flush=True)
    replays={slot:motionloops.audit_animation(model,sk,slot,cycles=8) for slot in sorted(set(slots)|{33})}
    return dict(species=sid,model_sha256=hashlib.sha256(model_path.read_bytes()).hexdigest(),tail_bones=tail,source_slot=33,coverage=coverage,subframes_per_tick=subframes,checked_bone_pairs=pairs,loop_replay_audits=replays,actions=reports,production_approved=False,limitations='Sampled native channels/float hierarchy, every sampled gait-tail phase combination. Subframes use fixed-alpha shortest-angle SRT interpolation; movement/gen/visibility masks and SDK rounding are not modeled. Directly joined meshes excluded in all-body coverage. No continuous sweep, coplanar/containment collisions, event ownership or artistic approval. PlaneY0 is explicit target hypothesis, not original-game invariant; foot bounds are diagnostics, not contact approval.')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['model','recipe','out']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--slots',nargs='+',type=int,default=[2,3,4]);p.add_argument('--coverage',choices=['all-body','legacy'],default='all-body');p.add_argument('--subframes',type=int,choices=[1,3],default=1);a=p.parse_args();r=audit(a.model,a.recipe,a.slots,a.coverage,a.subframes);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,indent=2)+'\n')

if __name__=='__main__':main()
