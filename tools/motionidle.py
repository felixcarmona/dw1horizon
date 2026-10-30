#!/usr/bin/env python3
"""Reuse a local native idle with its compound support surfaces grounded."""
import copy
import math
import motionlab as M


def world_matrices(skel,pose):
    """Compose the engine's T-R-S transforms, including inherited source scale."""
    matrices={}
    for b in sorted(range(len(skel)),key=lambda bone:M.R.depth(skel,bone)):
        rotation=M.mmd.rot_scale_matrix(pose[b])
        local=[rotation[i]+[pose[b][6+i]] for i in range(3)]+[[0,0,0,1]]
        parent=skel[b][1]
        matrices[b]=M.mmd.mat_mul(matrices[parent],local) if parent>=0 else local
    return [matrices[b] for b in range(len(skel))]


def align_upper(samples,skel,root,target_rotation):
    result=copy.deepcopy(samples)
    first=M.R.world_rots(skel,samples[0])[root]
    alignment=M.R.m3mul(target_rotation,M.R.m3t(first));previous={}
    for pose,original in zip(result,samples):
        desired=M.R.m3mul(alignment,M.R.world_rots(skel,original)[root])
        M.rotate_local(pose,skel,root,desired,previous)
    return result


def ground(samples,skel,body,vertices,floor):
    if skel[body][1]!=0:raise ValueError('idle grounding requires a root-child body')
    result=copy.deepcopy(samples)
    for pose in result:
        if pose[0][:6]!=[4096,4096,4096,0,0,0] or any(abs(v)>.01 for v in pose[0][6:9]):
            raise ValueError('native field idle must be stationary without entity rotation')
        world=world_matrices(skel,pose)
        low=max(sum(world[b][1][j]*v[j] for j in range(3))+world[b][1][3]
                for b,points in vertices.items() for v in points)
        pose[body][7]+=round(floor-low)
    result[-1][1:]=copy.deepcopy(result[0][1:])
    M.mmd.close_loop(result,0)
    return result


def planted(samples,mod,skel,rest,recipe,config,floor):
    """Keep an own upper-body idle above explicitly placed, stationary native paws."""
    import motionreference as Q
    import motionsecondary as S
    if skel[recipe['body']][1]!=0:raise ValueError('planted idle needs a root-child body')
    slot=int(config['reference_slot'],0)
    if slot not in {int(s,0) for s in recipe['slots']}:raise ValueError('planted idle needs a generated reference gait')
    gait_spec=next(v for k,v in recipe['slots'].items() if int(k,0)==slot)
    cfg=gait_spec.get('reference_motion')
    if not cfg or not cfg.get('pelvis_fit'):raise ValueError('planted idle needs the reference reach constraints')
    gait=M.animsheet.slot_frames(mod,len(skel),slot)[0]
    body=recipe['body'];height=sum(p[body][7] for p in gait[:-1])/(len(gait)-1)
    tp=M.R.world_pos(skel,rest);tw=M.R.world_rots(skel,rest);goals=[]
    for leg in recipe['legs']:
        h,k=leg['chain'][:2];a=leg['chain'][-1];hock=leg['chain'][2] if len(leg['chain'])==4 else None
        rotation=tw[a]
        low=max(sum(rotation[1][j]*v[j] for j in range(3)) for v in mod.tmd.obj_verts(skel[a][0]))
        target=[leg['ankle_x'],floor-low,leg['ankle_z']]
        last=M.legik.sub(tp[a],tp[hock]) if hock is not None else None
        lg=dict(h=h,k=k,a=a,hock=hock,lengths=[math.dist(tp[h],tp[k]),math.dist(tp[k],tp[hock if hock is not None else a])],
            native_last=last,end_offset=last or [0,0,0],pole_mode=leg.get('pole_mode','world'),pole=leg.get('knee_pole',[0,0,1]))
        goals.append((lg,target,rotation,True))
    output=[];previous={};clamps=[]
    for frame in samples:
        if frame[0]!=[4096,4096,4096,0,0,0,0,0,0]:raise ValueError('planted native idle must be stationary')
        p=copy.deepcopy(frame);p[body][7]=round(height+frame[body][7]-samples[0][body][7])
        dy,dz=S.fit_pelvis(**Q.pelvis_parameters(p,goals,mod,skel,body,cfg,floor,recipe['legs']))
        p[body][7]+=dy;p[body][8]+=dz
        Q.apply_leg_goals(p,goals,skel,tp,tw,previous,floor,clamps)
        Q.apply_clearances(p,mod,skel,cfg,floor,previous);output.append(p)
    if max(clamps)>1:raise ValueError('planted idle cannot reach every paw')
    output[-1]=copy.deepcopy(output[0])
    return output


def generate(mod,skel,rest,recipe,spec):
    source=int(spec['source'],0)
    if source!=33:raise ValueError('native field-idle study requires the own battle idle (0x21)')
    import motionloopcontracts
    if motionloopcontracts.load(recipe['species'],mod,skel).get(source):
        raise ValueError('native idle has intentional continuous rotation; requires a dedicated controller')
    sampling=mod
    if spec.get('plant_legs'):
        import motionloopfix as F
        sampling=copy.deepcopy(mod);closed,_=F.repair_animation(sampling,skel,source)
        if closed is not None:sampling.anims.anims[sampling.anims.table[source]]=closed
    frames,loop,events=M.animsheet.slot_frames(sampling,len(skel),source)
    if loop!=0:raise ValueError('native idle must loop from its first sample')
    supports=set()
    for leg in recipe['legs']:
        supports.add(leg['chain'][-1])
        if leg.get('heel_on_shin'):supports.add(leg['chain'][1])
    vertices={b:mod.tmd.obj_verts(skel[b][0]) for b in sorted(supports)}
    world=M.mmd.bone_matrices(mod,rest)
    floor=max(sum(world[b][1][j]*v[j] for j in range(3))+world[b][1][3]
              for b,points in vertices.items() for v in points)
    alignments=([spec['align_upper']] if spec.get('align_upper') else [])+spec.get('align_parts',[])
    for alignment in alignments:
        if any(channels[:3]!=[4096]*3 for frame in frames for channels in frame):
            raise ValueError('upper alignment requires unit-scale native poses; grounding itself preserves scale')
        root=alignment['root']
        if any(root==b or root in M.ancestors(skel,b) for leg in recipe['legs'] for b in leg['chain']):
            raise ValueError('upper-body alignment cannot rotate a support limb')
        reference=M.animsheet.slot_frames(mod,len(skel),int(alignment['slot'],0))[0][alignment.get('tick',0)]
        frames=align_upper(frames,skel,root,M.R.world_rots(skel,reference)[root])
    samples=(planted(frames,mod,skel,rest,recipe,spec['plant_legs'],floor) if spec.get('plant_legs')
             else ground(frames,skel,recipe['body'],vertices,floor))
    for clearance in spec.get('ground_clearance',[]):
        import motionsecondary
        previous={};root=clearance['root']
        if any(root!=b and root not in M.ancestors(skel,b) for b in clearance['bones']):
            raise ValueError('idle clearance parts must belong to the appendage')
        for pose in samples:
            world=M.mmd.bone_matrices(mod,pose)
            points=[[sum(world[b][i][j]*v[j] for j in range(3))+world[b][i][3] for i in range(3)]
                    for b in clearance['bones'] for v in mod.tmd.obj_verts(skel[b][0])]
            correction=motionsecondary.clearance_rotation(points,[world[root][i][3] for i in range(3)],
                clearance['axis'],clearance['limits'],floor-clearance.get('margin',1))
            M.rotate_local(pose,skel,root,M.R.m3mul(correction,M.R.world_rots(skel,pose)[root]),previous)
    samples[-1][1:]=copy.deepcopy(samples[0][1:])
    return samples,[(t,k,c) for t,k,c in events if k in ('tex','sound')],floor
