"""Anatomical foot-frame, amphibian and segmented-larva locomotion authoring."""
import copy
import hashlib
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT/'tools')]

import animsheet
import legik
import mmd
import motioncyclelayer
import motionsecondary
import motionstorage
import retarget as R
from motiontailspace import interpolate_pose
from tools.models.field_animations.native_polish import cyclic_eulers
from tools.models.field_animations.pace import _root_channels, _retimed_events


def digest(data):
    return hashlib.sha256(data).hexdigest()


def set_world(sk, pose, bone, rotation, history):
    parent = R.world_rots(sk, pose)[sk[bone][1]]
    angles = mmd.matrix_euler(R.m3mul(R.m3t(parent), rotation), history.get(bone))
    pose[bone][3:6] = history[bone] = [round(v) for v in angles]


def floor(model, sk, pose, feet):
    pose = copy.deepcopy(pose)
    pose[0] = [4096]*3+[0]*6
    matrices = mmd.bone_matrices(model, pose)
    return max(sum(matrices[b][1][j]*v[j] for j in range(3))+matrices[b][1][3]
               for b in feet for v in model.tmd.obj_verts(sk[b][0]))


def finish(model, additions, nb, charts=True):
    result = copy.deepcopy(model)
    for slot, frames, loop, events in additions:
        if loop is not None:
            mmd.close_loop(frames, loop)
            if charts:cyclic_eulers(frames)
        frames = [[[round(v) for v in bone] for bone in pose] for pose in frames]
        result.anims.table[slot] = len(result.anims.anims)
        result.anims.anims.append(mmd.encode_anim(frames, nb, loop, events, tol=0, repeats=False))
    for animation in result.anims.anims:
        animation.tail = b''
    result.anims.anims, result.anims.table = motioncyclelayer.share_identical_streams(result.anims.anims, result.anims.table)
    data = result.build()
    motionstorage.require(data, nb)
    assert result.tmd.build() == model.tmd.build()
    return data


def solve_leg(sk, pose, reference, chain, goal, foot_rotation, history, pole=None):
    hip, knee, foot = chain
    rp, rw = R.world_pos(sk, reference), R.world_rots(sk, reference)
    origin = R.world_pos(sk, pose)[hip]
    if knee is None:
        rotation = R.m3mul(R.swing(legik.sub(rp[foot], rp[hip]), legik.sub(goal, origin)), rw[hip])
        set_world(sk, pose, hip, rotation, history)
    else:
        bend = pole or motionsecondary.transported_native_pole(rp[hip],rp[knee],rp[foot],origin,goal)
        joint, end = legik.solve(origin, goal, math.dist(rp[hip],rp[knee]),math.dist(rp[knee],rp[foot]),bend)
        rotations = motionsecondary.native_plane_rotations([rp[b] for b in (hip,knee,foot)],
            [origin,joint,end],[rw[b] for b in (hip,knee)])
        set_world(sk,pose,hip,rotations[0],history)
        set_world(sk,pose,knee,rotations[1],history)
    set_world(sk,pose,foot,foot_rotation,history)


def stingmon(model, sk):
    additions = []
    def shoe_axes(bone):
        vertices=model.tmd.obj_verts(sk[bone][0])
        cy=sum(v[1] for v in vertices)/len(vertices)
        cz=sum(v[2] for v in vertices)/len(vertices)
        yy=sum((v[1]-cy)**2 for v in vertices)
        zz=sum((v[2]-cz)**2 for v in vertices)
        yz=sum((v[1]-cy)*(v[2]-cz) for v in vertices)
        eigen=(yy+zz-math.sqrt((yy-zz)**2+4*yz*yz))/2
        slope=-(yy-eigen)/yz if abs(yz)>1e-9 else 0.
        normal=1/math.sqrt(1+slope*slope)
        z=normal*slope
        return [[1,0,0],[0,normal,z],[0,z,-normal]]
    # Center the geometry before finding the plantar/forward axes. The left
    # shoe's joint is lower in the mesh; its negative centroid Y is an origin
    # offset, not a reversed sole. Both shoes have the same downward normal.
    shoe_frame=R.m3mul(shoe_axes(24),R.m3t(shoe_axes(27)))
    for slot in (2,3,4):
        original, loop, events = animsheet.slot_frames(model,len(sk),slot)
        frames = copy.deepcopy(original)
        period = len(frames)-1
        history = {}
        for tick, pose in enumerate(frames):
            source = original[(tick+period//2)%period]
            desired = R.m3mul(R.world_rots(sk,source)[24],shoe_frame)
            reference = original[tick]
            positions = R.world_pos(sk,reference)
            sole = max(sum(desired[1][j]*v[j] for j in range(3)) for v in model.tmd.obj_verts(sk[27][0]))
            goal = positions[27][:]
            goal[1] = min(goal[1],-sole-.75)
            solve_leg(sk,pose,reference,(25,26,27),goal,desired,history)
        additions.append((slot,frames,loop,events))
    return finish(model,additions,len(sk),charts=False)


def gizamon(model, sk, donor, ds, cfg):
    reference = R.rest_pose(model,len(sk),33)
    identity = [[1,0,0],[0,1,0],[0,0,1]]
    chains = [(4,None,5),(6,None,7),(10,11,12),(13,14,15)]
    # The long frog thighs fold rearward, outside the torso, while the paws
    # support beneath its flanks. Preserve every source segment length.
    for chain, sign in zip(chains,(1,-1,1,-1)):
        b = chain[-1]
        goal = [sign*(68 if chain[1] is None else 62),-38,-66 if chain[1] is None else 76]
        solve_leg(sk,reference,copy.deepcopy(reference),chain,goal,identity,{},
                  [sign*.35,-.35,1] if chain[1] is not None else None)
    ref_pos,ref_rot = R.world_pos(sk,reference),R.world_rots(sk,reference)
    dr = R.rest_pose(donor,len(ds))
    dp0,dw0 = R.world_pos(ds,dr),R.world_rots(ds,dr)
    additions=[]
    for slot in (0,1,2,3,4,9,11):
        native_slot = 0 if slot==1 else 2 if slot==3 else slot
        native,loop,events = animsheet.slot_frames(donor,len(ds),native_slot)
        care = slot in (9,11)
        base_frames,base_loop,base_events = animsheet.slot_frames(model,len(sk),slot)
        if care:
            native = base_frames
            loop,events = base_loop,base_events
        frames=[];history={}
        for tick, source in enumerate(native):
            pose = copy.deepcopy(source if care else reference)
            if not care:
                source = copy.deepcopy(source);source[0][6:9]=[0,0,0]
                positions,rotations = R.world_pos(ds,source),R.world_rots(ds,source)
                for target,db in ((1,14),(2,3),(3,5),(8,15),(9,16)):
                    delta=R.m3mul(rotations[db],R.m3t(dw0[db]))
                    set_world(sk,pose,target,R.m3mul(delta,ref_rot[target]),history)
                pose[1][7] += round(.2*(source[1][7]-dr[1][7]))
            for chain,db in zip(chains,(10,13,20,23)):
                foot=chain[-1]
                if care:
                    rotation=identity
                    goal=[ref_pos[foot][0],-max(v[1] for v in model.tmd.obj_verts(sk[foot][0])),ref_pos[foot][2]]
                else:
                    rotation=R.m3mul(R.scale_rot(R.m3mul(rotations[db],R.m3t(dw0[db])),.3),ref_rot[foot])
                    goal=[ref_pos[foot][i]+cfg['stride_scale']*(positions[db][i]-dp0[db][i]) for i in range(3)]
                    goal[0]=ref_pos[foot][0]+cfg['transverse_scale']*(positions[db][0]-dp0[db][0])
                    sole=max(sum(rotation[1][j]*v[j] for j in range(3)) for v in model.tmd.obj_verts(sk[foot][0]))
                    bottom=max(sum(rotations[db][1][j]*v[j] for j in range(3))+positions[db][1] for v in donor.tmd.obj_verts(ds[db][0]))
                    goal[1]=-sole+min(0,bottom)*.55
                solve_leg(sk,pose,reference,chain,goal,rotation,history)
            pose[1][7]-=math.ceil(max(0,floor(model,sk,pose,(5,7,12,15))+.5))
            if not care:pose[0][6:9]=native[tick][0][6:9][:]
            frames.append(pose)
        if not care and slot in (2,3,4):
            timing=cfg['retime'][str(slot)]
            frames=_root_channels(frames,timing['ticks'],timing['speed'])
            events=_retimed_events(events,len(native)-1,timing['ticks'])
        additions.append((slot,frames,loop,[(t,k,i) for t,k,i in events if care or k=='sound']))
    return finish(model,additions,len(sk))


def clear_interpolated_paws(model, sk, frames, chains):
    """Lift individual swing arcs that cross the floor between logic keys.

    Correct the limb solve while keeping the canine trunk at one height.
    This avoids turning interpolation clearance into whole-body bouncing.
    """
    for _ in range(5):
        cyclic_eulers(frames)
        lifts=[[0.]*len(chains) for pose in frames]
        worst=0.
        for tick,(a,b) in enumerate(zip(frames,frames[1:])):
            for alpha in (0,1365,2730,4096):
                pose=interpolate_pose(a,b,alpha)
                for j,chain in enumerate(chains):
                    excess=floor(model,sk,pose,[chain[-1]])+.5
                    worst=max(worst,excess)
                    lifts[tick][j]=max(lifts[tick][j],excess)
                    lifts[tick+1][j]=max(lifts[tick+1][j],excess)
        if worst<1.:break
        lifts[0]=lifts[-1]=[max(a,b) for a,b in zip(lifts[0],lifts[-1])]
        history={}
        for pose,needed in zip(frames,lifts):
            reference=copy.deepcopy(pose);positions=R.world_pos(sk,reference);rotations=R.world_rots(sk,reference)
            for chain,lift in zip(chains,needed):
                if lift<=0:continue
                foot=chain[-1];goal=positions[foot][:];goal[1]-=lift+.25
                solve_leg(sk,pose,reference,chain,goal,rotations[foot],history)
    return frames


def level_canine(data, sk):
    model=mmd.MMD.parse(data,len(sk));model.type=409
    additions=[]
    for slot in (2,3,4):
        original,loop,events=animsheet.slot_frames(model,len(sk),slot)
        # Keep the low stance within reach; the highest clearance pose
        # would unnecessarily shorten paw contact throughout the stride.
        body_y=max(p[1][7] for p in original)
        frames=[];history={}
        for reference in original:
            pose=copy.deepcopy(reference);pose[1][7]=body_y
            positions=R.world_pos(sk,reference);rotations=R.world_rots(sk,reference)
            support=floor(model,sk,reference,(5,8,15,18))
            for chain in ((3,4,5),(6,7,8),(13,14,15),(16,17,18)):
                foot=chain[-1];goal=positions[foot][:];goal[1]-=support+2
                solve_leg(sk,pose,reference,chain,goal,rotations[foot],history)
            frames.append(pose)
        frames=clear_interpolated_paws(model,sk,frames,((3,4,5),(6,7,8),(13,14,15),(16,17,18)))
        additions.append((slot,frames,loop,events))
    return finish(model,additions,len(sk))


def wormmon(model, sk, donor, ds, cfg):
    reference=R.rest_pose(model,len(sk),33)
    feet=(11,12,14,15,17,18)
    mapping={int(k):(v,cfg.get('weights',{}).get(k,1.)) for k,v in cfg['map'].items()}
    additions=[]
    for slot in (2,3,4):
        native_slot=2 if slot==3 else slot
        moved=R.transfer(donor,32,native_slot,183,reference,mapping,(16,1,.35),.65)
        frames=[]
        for tick in range(moved['n']):
            pose=copy.deepcopy(reference)
            for bone,seq in moved['rot'].items():pose[bone][3:6]=[round(v) for v in seq[tick]]
            pose[16][7]+=round(.35*moved['hips'][tick][1])
            pose[0][6:9]=[round(v) for v in moved['root'][tick]]
            pose[16][7]-=math.ceil(max(0,floor(model,sk,pose,feet)+.5))
            frames.append(pose)
        timing=cfg['retime'][str(slot)]
        frames=_root_channels(frames,timing['ticks'],timing['speed'])
        events=_retimed_events(moved['events'],moved['n']-1,timing['ticks'])
        additions.append((slot,frames,moved['loop'],[(t,k,i) for t,k,i in events if k=='sound']))
    return finish(model,additions,len(sk))


def build(data,cfg):
    sid=cfg['species'];sk=cfg['skeleton'];mmd.exe().add_type(sid,sk)
    model=mmd.MMD.parse(data,len(sk));model.type=sid
    if sid==187:output=stingmon(model,sk)
    elif sid==409:
        from tools.models.field_animations import native_polish
        output,_=native_polish.build(data,cfg)
        output=level_canine(output,sk)
    else:
        db=(ROOT/cfg['model']).read_bytes()
        if digest(db)!=cfg['donor_sha256']:raise ValueError('Donor pin differs')
        donor=mmd.MMD.load(str(ROOT/cfg['model']),cfg['donor']);ds=mmd.exe().skeleton[cfg['donor']]
        output=gizamon(model,sk,donor,ds,cfg) if sid==239 else wormmon(model,sk,donor,ds,cfg)
        if sid==239:
            from tools.models import delta
            pin=cfg['protected_prior']
            patch=(ROOT/pin['delta']).read_bytes()
            if digest(patch)!=pin['delta_sha256']:raise ValueError('Protected-program delta differs')
            prior=delta.decode(patch,[data])
            if digest(prior)!=pin['sha256']:raise ValueError('Protected-program model differs')
            base=mmd.MMD.parse(prior,len(sk));authored=mmd.MMD.parse(output,len(sk))
            assert base.tmd.build()==authored.tmd.build()
            for slot in (0,1,2,3,4,9,11):
                base.anims.table[slot]=len(base.anims.anims)
                base.anims.anims.append(copy.deepcopy(authored.anims.anims[authored.anims.table[slot]]))
            for animation in base.anims.anims:animation.tail=b''
            base.anims.anims,base.anims.table=motioncyclelayer.share_identical_streams(base.anims.anims,base.anims.table)
            output=base.build()
    return output,dict(source_sha256=digest(data),output_sha256=digest(output),storage=motionstorage.require(output,len(sk)))


if __name__ == '__main__':
    import argparse
    import json
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe',type=Path)
    parser.add_argument('source',type=Path)
    parser.add_argument('out',type=Path)
    args=parser.parse_args()
    cfg=json.loads(args.recipe.read_text())
    data=args.source.read_bytes()
    if digest(data)!=cfg['source_sha256']:raise SystemExit('Source pin differs')
    output,report=build(data,cfg)
    if digest(output)!=cfg['output_sha256']:raise SystemExit('Output pin differs')
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_bytes(output)
    args.out.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
