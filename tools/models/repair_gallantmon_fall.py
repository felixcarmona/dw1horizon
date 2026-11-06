#!/usr/bin/env python3
"""Author Gallantmon's collapse onto the shield side and recovery, with trailing cloth and plume.

Input is the reviewed pre-repair model pinned by SOURCE_SHA256. The three cape
panels, helmet plume and shield settle independently after the body falls.
The player build replays the resulting plain model delta.
"""
import argparse
import hashlib
import copy
import math
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import mmd
import animsheet
import motionstorage
from motiontailspace import interpolate_pose
from motiondiscidentity import changed_programs


SOURCE_SHA256 = "b8922062a2313a726551040b0ed3e521782ef98303669c68f47119d1ffc1de46"


def repair(data):
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        raise ValueError("Gallantmon fall requires the reviewed source")
    old = mmd.MMD.parse(data, 28)
    old.type = 318
    rest = animsheet.slot_frames(old, 28, 0)[0][0]
    sk = mmd.exe().skeleton[318]
    from tools.models.field_animations import quadruped as q
    support_rig = q.Rig(old, sk, dict(legs={'R':(20,21,22,1,False),
        'L':(24,25,26,-1,False)}, pole={False:[0.15,0,-1]}))
    anchors = {name:[support_rig.still[paw][i][3] for i in range(3)]
               for name,(_,_,paw,_,_) in support_rig.p['legs'].items()}

    def floor(p):
        """Lowest mesh point; y grows downward and the floor is zero."""
        w = mmd.bone_matrices(old, p)
        return max((sum((w[b][1][k] * v[k] for k in range(3))) + w[b][1][3] for b, (o, _) in enumerate(sk) if o >= 0 for v in old.tmd.obj_verts(o)))

    def pose(lean, knee, arm, hip, roll=0):
        """A grounded key: body lean, folded knees, weapon arm and hip pitch in degrees."""
        p = copy.deepcopy(rest)
        p[0][6:9] = [0, 0, 0]
        rotation=q.mul(q.rot([0,0,roll]),q.rot([lean,0,0]))
        p[1][3:6]=[round(a) for a in mmd.matrix_euler(rotation,rest[1][3:6])]
        for b in (20, 24):
            p[b][3] = round(hip * 4096 / 360)
        for b in (21, 25):
            p[b][3] = round(knee * 4096 / 360)
        for b in (22, 26):
            p[b][3] = round(-knee * 0.45 * 4096 / 360)
        for b in (23, 27):
            p[b][3] = 0
        p[2][3] = rest[2][3] + round(arm * 0.05 * 4096 / 360)
        p[12][3] = rest[12][3] + round(arm * 0.35 * 4096 / 360)
        p[3][3] = rest[3][3] + round(12 * math.sin(arm * math.pi / 180) * 4096 / 360)
        fold=q.smooth((abs(roll)-10)/65)
        p[2][5]+=round(62*q.DEG*fold)
        p[2][3]-=round(45*q.DEG*fold)
        p[24][5]-=round(55*q.DEG*fold)
        # Keep the cape trailing behind the shoulders throughout the fall.
        for b, target in ((16, 55), (17, 22), (18, 1)):
            blend = max(0, min(1, max((-lean - 5) / 65, (knee - 95) / 45)))
            target = target - lean if b == 16 else target
            p[b][3] = round(rest[b][3] * (1 - blend) + target * 4096 / 360 * blend)
        blend = max(0, min(1, (-lean - 10) / 55))
        # Lay the plume along the floor so its tip cannot prop up the body.
        for parent, child in ((7, 8), (8, 9), (9, 10), (10, 11)):
            w = mmd.bone_matrices(old, p)
            carrier = sk[parent][1]
            target = q.rot([math.degrees(math.atan2(p[child][7], p[child][8])), 0, 0])
            rotation = q.mul(q.tr([r[:3] for r in w[carrier][:3]]), target)
            angles = mmd.matrix_euler(rotation, p[parent][3:6])
            p[parent][3:6] = [round(a * (1 - blend) + b * blend) for a, b in zip(p[parent][3:6], angles)]
        w = mmd.bone_matrices(old, p)
        rw = mmd.bone_matrices(old, rest)
        # Roll the shield onto its broad face beside the fallen arm.
        desired = q.mul(q.rot([0, 0, 80]), [r[:3] for r in rw[4][:3]])
        local = q.mul(q.tr([r[:3] for r in w[3][:3]]), desired)
        angles = mmd.matrix_euler(local, p[4][3:6])
        p[4][3:6] = [round(a * (1 - blend) + b * blend) for a, b in zip(p[4][3:6], angles)]
        if knee > 100 and abs(lean) < 40:
            # The compression and push keep both boot soles at their anchors.
            p[1][7] = rest[1][7] + round(min(1,(knee-100)/55)*105)
            p[1][8] = rest[1][8] + round(min(1,(knee-100)/55)*35)
            for name,(_,_,paw,_,_) in support_rig.p['legs'].items():
                rotation, short = support_rig.solve(p,name,anchors[name],{})
                target=[r[:3] for r in support_rig.still[paw][:3]]
                q.set_rot(p,paw,q.mul(q.tr(rotation),target),{})
            p[1][7] -= math.ceil(max(0, floor(p)+2))
        else:
            p[1][7] = 0
            p[1][7] = round(-floor(p) - 2)
        return p
    # Anticipation, loss of balance, impact, recoil, then settle.
    keys = [(0, copy.deepcopy(rest)), (8, pose(21, 148, -12, -101, 3)), (15, pose(-8, 145, 6, -92, 5)), (24, pose(-57, 92, 28, -55, 46)), (30, pose(-89, 35, 48, -20, 90)), (32, pose(-83, 42, 44, -23, 84)), (36, pose(-87, 36, 46, -21, 88))]
    fall = []
    for t in range(37):
        a, b = next(((a, b) for a, b in zip(keys, keys[1:]) if a[0] <= t <= b[0]), (keys[-2], keys[-1]))
        u = (t - a[0]) / (b[0] - a[0])
        u = u * u * (3 - 2 * u)
        p = interpolate_pose(a[1], b[1], round(u * 4096))
        # Cloth and plume recoil after the body; distal pieces follow later.
        if t > 14:
            for bone, lag, amp in ((17, 2, 7), (18, 4, 10), (8, 2, 4), (9, 3, 6), (10, 4, 8), (11, 5, 10)):
                p[bone][3] += round(math.sin(max(0, t - 23 - lag) * 0.5) * math.exp(-max(0, t - 26) / 6) * amp * 4096 / 360)
        p[1][7] -= math.ceil(max(0, floor(p) + 2))
        fall.append(p)
    undelayed = copy.deepcopy(fall)
    for t,p in enumerate(fall):
        for bone,lag in ((6,2),(2,1),(3,2),(12,2),(13,3),(17,2),(18,3)):
            p[bone][3:6] = undelayed[max(0,t-lag)][bone][3:6]
        p[1][7] -= math.ceil(max(0, floor(p) + 2))
    # Roll to a crouch, push up, and settle into the imported idle.
    getkeys = [(0, copy.deepcopy(fall[-1])), (8, pose(-62, 103, 30, -68, 48)), (17, pose(35, 157, 20, -111, -9)), (22, pose(24, 140, 9, -95, -3)), (27, pose(10, 103, -4, -73, 2)), (30, copy.deepcopy(rest))]
    up = []
    for t in range(31):
        a, b = next(((a, b) for a, b in zip(getkeys, getkeys[1:]) if a[0] <= t <= b[0]))
        u = (t - a[0]) / (b[0] - a[0])
        u = u * u * (3 - 2 * u)
        p = interpolate_pose(a[1], b[1], round(u * 4096))
        p[1][7] -= math.ceil(max(0, floor(p) + 2))
        # Load the shield arm while rolling over the knees, then release it
        # after the hips take the weight. The elbow unfolds before the shoulder.
        brace=q.smooth(t/8)*(1-q.smooth((t-18)/8))
        p[2][3]+=round(16*q.DEG*brace)
        p[3][3]-=round(22*q.DEG*brace)
        up.append(p)
    # Equipment must follow the support pose rather than prop the torso up.
    # Fit the equipment hinges against the body's contact plane before grounding.
    def clear_equipment(p):
        def lowest(bones):
            w=mmd.bone_matrices(old,p)
            return max(sum(w[b][1][k]*v[k] for k in range(3))+w[b][1][3]
                       for b in bones for v in old.tmd.obj_verts(sk[b][0]))
        solid=[1,2,3,5,6,12,13,15,19,20,21,22,23,24,25,26,27]
        plane=lowest(solid)
        for hinge,bones in ((14,[14]),(4,[4]),(7,[7,8,9,10,11])):
            if lowest(bones)<=plane:continue
            initial=p[hinge][3]; candidates=[]
            for delta in range(-180,181,3):
                p[hinge][3]=initial+round(delta*4096/360)
                excess=max(0,lowest(bones)-plane)
                candidates.append((excess*100+abs(delta),p[hinge][3]))
            p[hinge][3]=min(candidates)[1]
        p[1][7]-=round(floor(p)+2)
    import retarget as R
    for frames in (fall,up):
        delayed=copy.deepcopy(frames)
        head_history={}
        cloth_history={b:list((fall[-1] if frames is up else rest)[b][3:6]) for b in (16,17,18)}
        for t,p in enumerate(frames):
            # Delay in world space: delaying a constant local neck channel
            # would still lock the helmet to the torso's rotation.
            previous=mmd.bone_matrices(old,delayed[max(0,t-2)])
            current=mmd.bone_matrices(old,p)
            q.set_rot(p,6,q.mul(q.tr([r[:3] for r in current[1][:3]]),
                [r[:3] for r in previous[6][:3]]),head_history)
            if (frames is fall and t<=15) or (frames is up and t>=17):
                curve = [(0,0),(8,105),(15,100)] if frames is fall else [(17,105),(22,76),(27,6),(30,0)]
                a,b=next(((a,b) for a,b in zip(curve,curve[1:]) if a[0]<=t<=b[0]))
                u=q.smooth((t-a[0])/(b[0]-a[0]));drop=a[1]+(b[1]-a[1])*u
                p[1][7]=rest[1][7]+round(drop);p[1][8]=rest[1][8]+round(drop/3)
                for name,(_,_,paw,_,_) in support_rig.p['legs'].items():
                    rotation, short=support_rig.solve(p,name,anchors[name],{})
                    assert short<1,(t,name,short)
                    target=[r[:3] for r in support_rig.still[paw][:3]]
                    q.set_rot(p,paw,q.mul(q.tr(rotation),target),{})
            blend=q.smooth(t/8) if frames is fall else 1-q.smooth((t-23)/7)
            w=mmd.bone_matrices(old,p)
            current=[r[:3] for r in w[14][:3]]
            target=q.rot([-90,20,0])
            desired=q.mul(R.scale_rot(q.mul(target,q.tr(current)),blend),current)
            q.set_rot(p,14,q.mul(q.tr([r[:3] for r in w[13][:3]]),desired),{})
            wbody=mmd.bone_matrices(old,p)[1]
            side=q.smooth((abs(math.degrees(math.asin(max(-1,min(1,wbody[1][0])))))-10)/65)
            p[16][8]+=round(8*side)
            p[17][7]+=round(12*side)
            # Each cloth panel hangs until its next joint reaches the ground;
            # the distal panels fold later, rather than raising the whole cape.
            w=mmd.bone_matrices(old,p)
            plane=max(sum(w[b][1][k]*v[k] for k in range(3))+w[b][1][3]
                for b in (1,2,3,5,6,12,13,15,19,20,21,22,23,24,25,26,27)
                for v in old.tmd.obj_verts(sk[b][0]))-2
            for bone,child,maximum,lag in ((16,17,55,1),(17,18,78,2),(18,None,83,4)):
                dr=mmd.bone_matrices(old,frames[max(0,t-lag)])[1]
                drive=math.degrees(math.atan2(dr[2][1],dr[1][1]))
                amount=q.smooth((-drive-5)/75)
                base=(22-57*amount) if bone==16 else 22+(maximum-22)*amount
                if bone==16:
                    crouch=q.smooth((p[1][7]-rest[1][7])/105)*(1-q.smooth((-drive-8)/40))
                    base+=8*crouch
                if t>25:base+=2*math.sin((t-25-lag)*.55)*math.exp(-(t-25)/7)
                w=mmd.bone_matrices(old,p)
                origin=[w[bone][i][3] for i in range(3)]
                points=[p[child][6:9]] if child else old.tmd.obj_verts(sk[bone][0])
                theta=min(maximum,max(-35 if bone==16 else 15,base))
                while theta<maximum:
                    rotation=q.rot([theta,0,0])
                    bottom=max(origin[1]+q.dot(rotation[1],v[:3]) for v in points)
                    if bottom<=plane-(72 if child else 0):break
                    theta=min(maximum,theta+.5)
                yaw=-{16:90,17:45,18:30}[bone]*q.smooth(abs(math.degrees(math.asin(max(-1,min(1,w[1][1][0])))))/75)
                desired=q.mul(q.rot([0,yaw,0]),q.rot([theta,0,0]))
                q.set_rot(p,bone,q.mul(q.tr([r[:3] for r in w[sk[bone][1]][:3]]),desired),cloth_history)
            clear_equipment(p)
            if frames is up and t >= 26:
                frames[t] = interpolate_pose(p, rest, round(q.smooth((t-26)/4)*4096))
    # Guard the actual Euler interpolation, including the long lance tip.
    for frames in (fall, up):
        for _ in range(3):
            lift = [0.] * len(frames)
            for i,(a,b) in enumerate(zip(frames,frames[1:])):
                excess = max(floor(interpolate_pose(a,b,alpha))+2 for alpha in (0,1365,2730,4096))
                lift[i] = max(lift[i],excess)
                lift[i+1] = max(lift[i+1],excess)
            for p,amount in zip(frames,lift):p[1][7]-=math.ceil(max(0,amount))
    up[0] = copy.deepcopy(fall[-1])
    up[-1] = copy.deepcopy(rest)
    new = copy.deepcopy(old)
    for slot, poses in ((43, fall), (44, up)):
        _, loop, events = animsheet.slot_frames(old, 28, slot)
        new.anims.anims[old.anims.table[slot]] = mmd.encode_anim(poses, 28, loop_sample=None, events=events, tol=1, repeats=False)
    result = new.build()
    actual = mmd.MMD.parse(result, 28)
    actual.type = 318
    assert actual.tmd.build() == old.tmd.build()
    assert changed_programs(old, actual) == [21, 43, 44]
    decoded = {slot: animsheet.slot_frames(actual, 28, slot)[0] for slot in (43, 44)}
    assert decoded[43][-1][1:] == decoded[44][0][1:]
    assert decoded[44][-1][1:] == rest[1:]
    for slot in (43, 44):
        before, loop, events = animsheet.slot_frames(old, 28, slot)
        after, new_loop, new_events = animsheet.slot_frames(actual, 28, slot)
        assert (len(before), loop, events) == (len(after), new_loop, new_events)
    floor_checks = {}
    for slot, frames in decoded.items():
        lowest = max(floor(interpolate_pose(a, b, alpha))
                     for a, b in zip(frames, frames[1:]) for alpha in (0, 1365, 2730))
        assert lowest <= 3, (slot, lowest)
        floor_checks[slot] = round(lowest, 2)
    from tools.models.gallantmon_contacts import audit
    contacts = audit(result)
    assert contacts['passed'], contacts
    return result, dict(contacts=contacts, changed_slots=[21, 43, 44], mesh_exact=True,
                        faint_recovery_join_exact=True, events_duration_exact=True,
                        floor_60fps=floor_checks, storage=motionstorage.require(result, 28))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result, report = repair(args.source.read_bytes())
    args.output.write_bytes(result)
    args.output.with_suffix('.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
