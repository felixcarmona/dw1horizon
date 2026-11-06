"""Planted breathing and phase-selected braking steps for the armoured wolf."""
import copy
import math

import animsheet
import mmd
import retarget as R
from motiontailspace import interpolate_pose
from tools.models.field_animations import quadruped as q

# Partner-only, previously absent programs. The selector in partner.c uses this order.
STOP_SLOTS = {2: (6, 20, 26, 28), 4: (29, 30, 31, 32)}


def planted(rig, pose, goals, history, rotations=None):
    worst = 0
    for name, (upper, lower, paw, side, front) in rig.p['legs'].items():
        world = rotations[name] if rotations else q.rot([0, 0, 0])
        wrist = q.sub(goals[name], q.mv(world, rig.p['sole'][front]))
        rotation, short = rig.solve(pose, name, wrist, history)
        worst = max(worst, short)
        q.set_rot(pose, paw, q.mul(q.tr(rotation), world), history)
    return worst


def author(old, rig, idle):
    """Root travel and planted world targets share the same braking curve."""
    neutral = {}
    w = rig.world(idle[0])
    for name, (_, _, paw, _, front) in rig.p['legs'].items():
        neutral[name] = q.add([w[paw][i][3] for i in range(3)], rig.p['sole'][front])
    programs = {}
    metrics = []
    for source, slots in STOP_SLOTS.items():
        frames, _, events = animsheet.slot_frames(old, rig.n, source)
        period = len(frames)-1
        speed = rig.p['gaits'][source]['speed']
        for phase, slot in enumerate(slots):
            first = copy.deepcopy(frames[round(phase*period/4)%period])
            first[0][6:9] = [0, 0, 0]
            w = rig.world(first)
            starts = {name:q.add([w[paw][i][3] for i in range(3)], q.mv([r[:3] for r in w[paw][:3]], rig.p['sole'][front]))
                      for name, (_, _, paw, _, front) in rig.p['legs'].items()}
            # An airborne paw lands first; the other paws follow in lateral order.
            order = sorted(starts, key=lambda name: starts[name][1])
            begin = {name:(i%2)*(1 if source==4 else 2) for i,name in enumerate(order)}
            total = speed*4
            poses=[];history={};worst=0
            for tick in range(13):
                u=q.smooth(tick/12)
                pose=interpolate_pose(first,idle[0],round(u*4096))
                travel=total*(1-(1-min(tick/8,1))**2)
                pose[0][6:9]=[0,0,-round(travel)]
                # Shoulders take the braking load before the hips and head settle.
                load=math.sin(math.pi*min(tick/12,1))
                pose[15][7]+=round(8*load)
                pose[1][3]+=round(2*q.DEG*load)
                goals={}; rotations={}
                for name in starts:
                    swing=max(0,min(1,(tick-begin[name])/6))
                    k=q.smooth(swing)
                    target=list(neutral[name]);target[2]-=total
                    world=[(1-k)*a+k*b for a,b in zip(starts[name],target)]
                    world[1]-=26*math.sin(math.pi*swing)
                    world[2]+=travel
                    goals[name]=world
                    paw=rig.p['legs'][name][2]
                    # Paw orientation releases with the step, never at the program boundary.
                    firstrot=[r[:3] for r in w[paw][:3]]
                    rotations[name]=q.mul(R.scale_rot(q.tr(firstrot), k),firstrot)
                for attempt in range(12):
                    short=planted(rig,pose,goals,history,rotations)
                    if short<0.5: break
                    pose[15][7]+=max(1,round(short))
                worst=max(worst,short)
                poses.append(pose)
            poses[-1]=copy.deepcopy(idle[0]);poses[-1][0][8]=-round(total)
            stop_events=[e for e in events if e[0]==0 and e[1]=='tex']
            sound=next(dict(e) for _,kind,e in events if kind=='sound')
            for landing in (6,7 if source==4 else 8):
                stop_events.append((landing,'sound',dict(sound,frame=landing+1)))
            programs[slot]=mmd.encode_anim(poses,rig.n,loop_sample=None,
                 events=stop_events,tol=1)
            metrics.append(dict(slot=slot,source=source,phase=phase,travel=total,unreached=worst))
    return programs,metrics
