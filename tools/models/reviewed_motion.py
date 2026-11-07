#!/usr/bin/env python3
"""Author reviewed care and native-donor motion as pinned offline model deltas.

Inputs are the final pre-edit provider models. No generator runs on player builds;
store reviewed outputs with tools/models/edit.py put.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet
import legik
import mmd
import motioncyclelayer
import motionsecondary
import motionstorage
import retarget as R
from tools.models.resize import resize


def load(path, sid):
    if sid >= 180 or sid == 62:
        spec = json.loads(next((ROOT / 'content/species').glob(f'{sid}-*.json')).read_text())
        mmd.exe().add_type(sid, spec['model']['skeleton'])
    return mmd.MMD.load(str(path), sid)


def clean(pose):
    pose = copy.deepcopy(pose)
    pose[0] = [4096] * 3 + [0] * 6
    return pose


def world(model, pose):
    return mmd.bone_matrices(model, clean(pose))


def points(model, pose, bones):
    sk = mmd.exe().skeleton[model.type]
    mats = world(model, pose)
    return [[sum(mats[b][i][j] * v[j] for j in range(3)) + mats[b][i][3]
             for i in range(3)] for b in bones for v in model.tmd.obj_verts(sk[b][0])]


def set_world(pose, sk, bone, desired, history):
    pw = R.world_rots(sk, pose)[sk[bone][1]]
    angles = mmd.matrix_euler(R.m3mul(R.m3t(pw), desired), history.get(bone))
    history[bone] = angles
    pose[bone][3:6] = [round(v) for v in angles]


def install(model, slot, frames, loop, events):
    animation = mmd.encode_anim(frames, len(frames[0]), loop, events, tol=1 if model.type == 246 else 3, repeats=False)
    assert animation is not None
    model.anims.table[slot] = len(model.anims.anims)
    model.anims.anims.append(animation)


def finish(model):
    for a in model.anims.anims:
        a.tail = b''
    model.anims.anims, model.anims.table = motioncyclelayer.share_identical_streams(
        model.anims.anims, model.anims.table)
    data = model.build()
    return data, motionstorage.require(data, mmd.exe().bone_count[model.type])


def ease(t):
    t = max(0, min(1, t))
    return t*t*(3-2*t)


def care(model):
    """Retain native breathing and append staggered, eased reactions."""
    sid = model.type
    nb = mmd.exe().bone_count[sid]
    sk = mmd.exe().skeleton[sid]
    native = animsheet.slot_frames(model, nb, 33)[0]
    rest = clean(animsheet.slot_frames(model, nb, 0)[0][0])
    out = copy.deepcopy(model)
    legs = [(h, h+1, h+2, h+3) for h in (5, 9, 13, 17, 21, 25)] if sid == 246 else []
    reference_world = world(model, rest)
    rw = R.world_rots(sk, rest)
    for slot in (9, 12):
        oldframes, loop, events = animsheet.slot_frames(model, nb, slot)
        n = len(oldframes)-1
        frames, history = [], {}
        for t in range(n+1):
            # Slow the original performance for sleep; preserve its overlapping
            # secondary motion instead of oscillating every part in phase.
            p = clean(native[round(t * (len(native)-1) / n)])
            if sid == 431:
                if slot == 9:
                    weight = ease(t / 14)
                    p[1][7] += round(22*weight)
                    p[1][3] += round(35*weight)
                    for b in (30,31,32):
                        p[b][3] = rest[b][3] + round(18*weight)
                    for root,end in ((2,5),(6,10),(11,14),(15,19),(20,24),(25,29)):
                        for b in range(root,end+1):
                            lag = ease((t-(b-root)*2) / 16)
                            p[b][3] = rest[b][3] + round(16*lag)
                            p[b][5] = rest[b][5] + round((1 if root<15 else -1)*12*lag)
                else:
                    # Withdraw, shiver once, then release with a lagging tip.
                    for b in (1,30,31,32,33):
                        u = t/max(1,n)
                        reaction = math.sin(math.pi*u)**2
                        p[b][3] = rest[b][3] + round((35 if b==1 else 18)*reaction)
                    for root,end in ((2,5),(6,10),(11,14),(15,19),(20,24),(25,29)):
                        for b in range(root,end+1):
                            u = max(0,min(1,(t-(b-root)*1.2)/max(1,n-5)))
                            p[b][3] = rest[b][3] + round(24*math.sin(math.pi*u)**2)
                            p[b][5] = rest[b][5] + round(10*math.sin(2*math.pi*u)*(1 if root<15 else -1))
            else:
                reaction = ease(t/16) if slot == 9 else math.sin(math.pi*t/n)**2
                p[1][7] += round(24*reaction)
                p[2][3] += round(30*reaction)
                # The six feet keep their native idle contact positions as
                # the shell settles. Two rigid links solve independently.
                for h,k,foot,pad in legs:
                    for b in (h,k,foot,pad):
                        p[b] = copy.deepcopy(rest[b])
                    w = world(model,p)
                    origin = [w[h][i][3] for i in range(3)]
                    goal = [reference_world[foot][i][3] for i in range(3)]
                    refpts = [[reference_world[b][i][3] for i in range(3)] for b in (h,k,foot)]
                    pole = motionsecondary.transported_native_pole(*refpts,origin,goal)
                    joint,end = legik.solve(origin,goal,math.dist(refpts[0],refpts[1]),math.dist(refpts[1],refpts[2]),pole)
                    rh,rk = motionsecondary.native_plane_rotations(refpts,[origin,joint,end],[rw[h],rw[k]])
                    set_world(p,sk,h,rh,history)
                    set_world(p,sk,k,rk,history)
                    set_world(p,sk,foot,rw[foot],history)
            frames.append(p)
        install(out,slot,frames,loop,[e for e in events if e[1]=='sound'])
    return out




def support_blends(model, slots, feet, carrier):
    """Clear the floor between encoded keys, preserving the native gait."""
    from motiontailspace import interpolate_pose
    from tools.models.field_animations.diaboromon import replace_channels
    nb=mmd.exe().bone_count[model.type]
    for slot in slots:
        frames,loop,_=animsheet.slot_frames(model,nb,slot)
        lifts=[0.]*len(frames)
        for t in range(len(frames)-1):
            for alpha in (0,1365,2730,4096):
                pose=interpolate_pose(frames[t],frames[t+1],alpha)
                needed=max(0.,max(v[1] for v in points(model,pose,feet))+.5)
                lifts[t]=max(lifts[t],needed)
                lifts[t+1]=max(lifts[t+1],needed)
        if loop==0:lifts[0]=lifts[-1]=max(lifts[0],lifts[-1])
        period=len(frames)-1
        envelope=[]
        for t in range(len(frames)):
            distance=lambda j:min(abs(t-j),period-abs(t-j)) if loop==0 else abs(t-j)
            envelope.append(max(lifts[j]-3*distance(j) for j in range(len(frames))))
        for pose,lift in zip(frames,envelope):pose[carrier][7]-=math.ceil(lift)
        original=model.anims.anims[model.anims.table[slot]]
        animation=replace_channels(original,frames,loop,nb,{(carrier,7)},tolerance=0)
        model.anims.table[slot]=len(model.anims.anims)
        model.anims.anims.append(animation)
    return model


def reverse_hock(origin, target, upper, lower, sign):
    """Keep Diaboromon's reverse-folded supports on one lateral bend branch."""
    lateral=sign*100
    a=math.sqrt(upper*upper-(lateral-origin[0])**2)
    b=math.sqrt(lower*lower-(lateral-target[0])**2)
    dy,dz=target[1]-origin[1],target[2]-origin[2]
    distance=math.hypot(dy,dz)
    assert abs(a-b)<distance<a+b, ('unreachable reverse hock',origin,target,a,b)
    y,z=dy/distance,dz/distance
    along=(a*a-b*b+distance*distance)/(2*distance)
    height=math.sqrt(a*a-along*along)
    return [lateral,origin[1]+along*y-height*z,origin[2]+along*z+height*y],target


def native_motion(model, donor, slots):
    """Transfer native acting and solve feet along native contact trajectories."""
    sid, dsid = model.type, donor.type
    sk, dsk = mmd.exe().skeleton[sid], mmd.exe().skeleton[dsid]
    nb = len(sk)
    rest, dr = R.rest_pose(model,nb), R.rest_pose(donor,len(dsk))
    if sid == 237:
        # SkullGreymon's thigh/shin/paw maps to the distal support chain;
        # retain the imported proximal thigh and its silhouette.
        mapping = {15:1,14:15,1:2,2:3,3:4,4:4,5:5,
                   6:7,7:8,8:9,9:10,10:11,11:12,12:13,13:14,
                   16:17,17:17,18:18,19:19,20:21,21:21,22:22,23:23}
        limbs = [(17,18,19,17,18,19),(21,22,23,21,22,23)]
        carrier = 15
    elif sid == 267:
        mapping = {1:2,2:13,13:3,14:4,18:5,3:14,4:15,5:16,6:16,
                   21:10,22:11,23:12,24:7,25:8,26:9,
                   7:18,8:19,9:20,10:21,11:22,12:23}
        limbs = [(24,25,26,7,8,9),(21,22,23,10,11,12),
                 (7,8,9,18,19,20),(10,11,12,21,22,23)]
        carrier = 1
    else:
        mapping = {1:2,2:13,13:3,14:4,15:5,3:14,4:15,5:16,
                   7:18,8:19,9:20,10:21,11:22,12:23,
                   23:10,24:11,25:12,26:7,27:8,28:9}
        limbs = [(26,27,28,7,8,9),(23,24,25,10,11,12),
                 (7,8,9,18,19,20),(10,11,12,21,22,23)]
        carrier = 1
    chords = [(h,k,dh,dk) for h,k,f,dh,dk,df in limbs]
    chords += [(k,f,dk,df) for h,k,f,dh,dk,df in limbs]
    if sid == 237:
        chords = []
        chords += [(7,8,8,9),(8,9,9,10),(11,12,12,13),(12,13,13,14)]
    rest = R.align_reference(sk,rest,dsk,dr,chords,keep_world=[v[2] for v in limbs]+([4,5,9,13] if sid==237 else []),sagittal=True)
    # Ground soles after calibration; paws keep their own world yaw.
    low = max(v[1] for v in points(model,rest,[v[2] for v in limbs]))
    rest[carrier][7] -= round(low)
    rp,dp = R.world_pos(sk,rest), R.world_pos(dsk,dr)
    rw,dw0 = R.world_rots(sk,rest),R.world_rots(dsk,dr)
    ratios = [R.chain_length(sk,rp,h,f)/R.chain_length(dsk,dp,dh,df) for h,k,f,dh,dk,df in limbs]
    ratio = min(ratios)
    out = copy.deepcopy(model)
    for slot in slots:
        transfer = R.transfer(donor,dsid,slot,sid,rest,{b:(s, 1. if sid==237 and b in (16,20) else .35 if sid in (267,268) and b==14 else .5 if sid in (267,268) and b==13 else .2 if sid==268 and b==15 else 1.) for b,s in mapping.items()},
                              (carrier,1,ratio),ratio)
        source,_,_ = animsheet.slot_frames(donor,len(dsk),slot)
        frames,history = [],{}
        for tick,src in enumerate(source):
            p = copy.deepcopy(rest)
            for b,seq in transfer['rot'].items(): p[b][3:6] = [round(v) for v in seq[tick]]
            p[carrier][6:9] = [round(rest[carrier][6+i]+transfer['hips'][tick][i]) for i in range(3)]
            if sid in (267,268) and slot in (0,1,2,3,4,35,36): p[carrier][7] += 45
            dw,dpos = R.world_rots(dsk,clean(src)),R.world_pos(dsk,clean(src))
            for h,k,foot,dh,dk,df in limbs:
                foot_delta=R.m3mul(dw[df],R.m3t(dw0[df]))
                fw = R.m3mul(R.scale_rot(foot_delta,.3) if sid==237 else foot_delta,rw[foot])
                target = [rp[foot][i]+ratio*(dpos[df][i]-dp[df][i]) for i in range(3)]
                verts=model.tmd.obj_verts(sk[foot][0])
                sole=max(sum(fw[1][j]*v[j] for j in range(3)) for v in verts)
                donor_floor = max(v[1] for v in points(donor,src,[df]))
                target[1] = -sole + ratio*min(0,donor_floor)
                origin=R.world_pos(sk,p)[h]
                v1=legik.sub(rp[k],rp[h]);v2=legik.sub(rp[foot],rp[k])
                # The native knee supplies a stable anatomical bend plane.
                pole=motionsecondary.transported_native_pole(rp[h],rp[k],rp[foot],origin,target)
                if sid==237:
                    proximal=sk[h][1]
                    hip=R.world_pos(sk,p)[proximal]
                    direction=legik.sub(origin,hip)
                    turn=R.swing(direction,legik.sub(target,hip))
                    proximal_world=R.world_rots(sk,p)[proximal]
                    sign=1 if foot==19 else -1
                    def feasible(weight):
                        rot=R.scale_rot(turn,weight)
                        candidate=[hip[i]+sum(rot[i][j]*direction[j] for j in range(3)) for i in range(3)]
                        aa=legik.norm(v1)**2-(sign*100-candidate[0])**2
                        bb=legik.norm(v2)**2-(sign*100-target[0])**2
                        if min(aa,bb)<=0:return False
                        distance=math.hypot(target[1]-candidate[1],target[2]-candidate[2])
                        return abs(math.sqrt(aa)-math.sqrt(bb))+6<distance<math.sqrt(aa)+math.sqrt(bb)-12
                    if not feasible(0):
                        lo,hi=0.,next((j/20 for j in range(1,21) if feasible(j/20)),None)
                        assert hi is not None, ('unreachable proximal support',slot,tick,foot)
                        for _ in range(18):
                            mid=(lo+hi)/2
                            if feasible(mid):hi=mid
                            else:lo=mid
                        set_world(p,sk,proximal,R.m3mul(R.scale_rot(turn,hi),proximal_world),history)
                        origin=R.world_pos(sk,p)[h]
                    joint,end=reverse_hock(origin,target,legik.norm(v1),legik.norm(v2),sign)
                else:
                    joint,end=legik.solve(origin,target,legik.norm(v1),legik.norm(v2),pole)
                rh,rk=motionsecondary.native_plane_rotations([rp[b] for b in (h,k,foot)],
                                                             [origin,joint,end],[rw[h],rw[k]])
                set_world(p,sk,h,rh,history);set_world(p,sk,k,rk,history);set_world(p,sk,foot,fw,history)
            # Imported extremities can exceed the donor's floor envelope.
            # Use one common lift, preserving the native weight-shift rhythm.
            floor=max(v[1] for v in points(model,p,[v[2] for v in limbs]))
            if floor > 0: p[carrier][7]-=math.ceil(floor)
            p[0][6:9]=[round(v) for v in transfer['root'][tick]]
            frames.append(p)
        if sid == 237:
            from tools.models.field_animations.war_greymon import rotation
            import numeric as np
            for elbow, hand in ((8,9),(12,13)):
                needed=[]
                for p in frames:
                    w=world(model,p)
                    hinge=np.array(motionsecondary.clearance_rotation(points(model,p,[elbow,hand]),
                        [w[elbow][i][3] for i in range(3)],
                        [w[sk[elbow][1]][i][0] for i in range(3)],[-70,0],-12))
                    needed.append(math.degrees(math.acos(max(-1,min(1,(float(np.trace(hinge))-1)/2)))))
                for t,p in enumerate(frames):
                    lift=max(needed[j]-3*abs(t-j) for j in range(len(frames)))
                    local=R.m3mul(rotation([-lift,0,0]).tolist(),mmd.rot_matrix(*p[elbow][3:6]))
                    p[elbow][3:6]=[round(v) for v in mmd.matrix_euler(local)]
        if transfer['loop'] is not None: mmd.close_loop(frames,transfer['loop'])
        install(out,slot,frames,transfer['loop'],[e for e in transfer['events'] if e[1]=='sound'])
    return support_blends(out,slots,[v[2] for v in limbs],carrier)



def resized_supports(data):
    """Compensate integer resize rounding at the six paw anchors, in care only.

    The two-link solve is already baked. Correct only the sub-pixel accumulated
    error at each ankle; preserve all scales and all other programs.
    """
    model=mmd.MMD.parse(data,30)
    model.type=246
    sk=mmd.exe().skeleton[246]
    for slot in (9,12):
        frames,loop,events=animsheet.slot_frames(model,30,slot)
        first=world(model,frames[0])
        for p in frames:
            p[0]=[4096]*3+[0]*6
            for foot in (7,11,15,19,23,27):
                w=world(model,p)
                parent=sk[foot][1]
                goal=[first[foot][i][3] for i in range(3)]
                low=max(v[1] for v in points(model,p,[foot,foot+1]))
                # Compensate the foot/pad compound's current rotated low point.
                goal[1]=w[foot][1][3]-low-2
                delta=[goal[i]-w[parent][i][3] for i in range(3)]
                pr=R.world_rots(sk,p)[parent]
                p[foot][6:9]=[round(sum(pr[j][i]*delta[j] for j in range(3))) for i in range(3)]
        from tools.models.field_animations.diaboromon import replace_channels
        original=model.anims.anims[model.anims.table[slot]]
        channels={(b,c) for b in (7,11,15,19,23,27) for c in (6,7,8)}
        animation=replace_channels(original,frames,loop,30,channels,tolerance=2)
        model.anims.table[slot]=len(model.anims.anims)
        model.anims.anims.append(animation)
    return finish(model)[0]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('species',type=int,choices=(62,237,246,267,268,431))
    parser.add_argument('source',type=Path)
    parser.add_argument('out',type=Path)
    args=parser.parse_args()
    proof=json.loads((ROOT/'content/modeldelta/reviewed-motion.json').read_text())['models'][str(args.species)]
    if hashlib.sha256(args.source.read_bytes()).hexdigest()!=proof['source_sha256']:
        raise ValueError('authoring requires the pinned pre-edit provider model')
    model=load(args.source,args.species)
    if args.species in (246,431): model=care(model)
    elif args.species in (237,267,268):
        donor_id,donor_path=(26,'MMD0/SKUL.MMD') if args.species==237 else (47,'MMD1/MONO.MMD')
        donor_file=ROOT/'extracted/CHDAT'/donor_path
        if hashlib.sha256(donor_file.read_bytes()).hexdigest()!=proof['donor']['source_sha256']:
            raise ValueError('native animation donor checksum changed')
        donor=load(donor_file,donor_id)
        slots=[0,1,2,3,4] if args.species==237 else [0,1,2,3,4,5,7,8,9,10,11,12,13,14,15,16,17,18,19,34,35,36]
        model=native_motion(model,donor,slots)
    data,storage=finish(model)
    factor={62:0.74,246:0.72}.get(args.species,1.)
    if factor!=1: data=resize(data,mmd.exe().bone_count[args.species],factor)
    if args.species==246: data=resized_supports(data)
    storage=motionstorage.require(data,mmd.exe().bone_count[args.species])
    if hashlib.sha256(data).hexdigest()!=proof['output_sha256']:
        raise ValueError('authored result differs from reviewed output: '+hashlib.sha256(data).hexdigest())
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_bytes(data)
    args.out.with_suffix('.json').write_text(json.dumps(dict(species=args.species,
        source_sha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),
        output_sha256=hashlib.sha256(data).hexdigest(),factor=factor,storage=storage),indent=2)+'\n')
    print(args.out,len(data))

if __name__=='__main__': main()
