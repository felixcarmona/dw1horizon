"""Plant Diaboromon's hands while retaining its pinned crouched locomotion.

Only forearm/hand rotations 8/9 and 12/13 change. Joint translations, scales,
upper arms, torso, legs, root travel and original clocks/events remain.
"""
import copy
import hashlib
import math

import animsheet
import mmd
import retarget as R
from tools.models.field_animations.diaboromon import replace_channels

SOURCE = 'f489b9daef2829ab9b2657ebab2c8274be7e7273814ee1962563b8733300de88'
ARMS = ((8, 9, 1), (12, 13, -1))


def unit(v):
    length=math.sqrt(sum(x*x for x in v))
    return [x/length for x in v]


def cross(a,b):
    return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]


def flat_hand(sign, forward):
    # The broad palm and finger pads share the positive-X side (mirrored left).
    # The curled claw tips stay above this support plane.
    normal=unit([sign,-.15,.12])
    along=unit([int(i==1)-normal[i]*normal[1] for i in range(3)])
    local=[normal,along,cross(normal,along)]
    down=[0,1,0]
    forward=unit([forward[0],0,forward[2]])
    desired=[down,forward,cross(down,forward)]
    return [[sum(desired[k][i]*local[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def build(data):
    if hashlib.sha256(data).hexdigest()!=SOURCE:
        raise ValueError('hand contacts require the pinned crouched Diaboromon')
    from tools.models.reviewed_motion import world,set_world
    model=mmd.MMD.parse(data,24);model.type=237
    sk=mmd.exe().skeleton[237]
    for slot in range(5):
        frames,loop,_=animsheet.slot_frames(model,24,slot)
        corrected=[];history={}
        close_contact=set()
        if loop==0:
            # The source run's wrist-clearance envelope differs at its endpoints.
            # A contact at either endpoint needs one shared planted hand pose.
            first,last=world(model,frames[0]),world(model,frames[-1])
            for _,hand,_ in ARMS:
                heights=[first[hand][1][3],last[hand][1][3]]
                if max(heights)>=-80 and min(heights)>=-120:
                    close_contact.add(hand)
        for tick,original in enumerate(frames):
            p=copy.deepcopy(original)
            matrices=world(model,p)
            rotations=R.world_rots(sk,[([4096]*3+[0]*6) if i==0 else b for i,b in enumerate(p)])
            for elbow,hand,sign in ARMS:
                wrist=[matrices[hand][i][3] for i in range(3)]
                origin=[matrices[elbow][i][3] for i in range(3)]
                # Keep the pad facing down through landing and early lift-off;
                # release it towards its native curl once the wrist is clear.
                u=max(0.,min(1.,(220+wrist[1])/80))
                weight=u*u*(3-2*u)
                closing=hand in close_contact and tick in (0,len(frames)-1)
                if closing:weight=1.
                if not weight:
                    for b in (elbow,hand):set_world(p,sk,b,rotations[b],history)
                    continue
                direction=[wrist[i]-origin[i] for i in range(3)]
                flat=flat_hand(sign,[sign*.2,0,-1])
                delta=R.m3mul(flat,R.m3t(rotations[hand]))
                desired=R.m3mul(R.scale_rot(delta,weight),rotations[hand])
                vertices=model.tmd.obj_verts(sk[hand][0])
                low=max(sum(desired[1][j]*v[j] for j in range(3)) for v in vertices)
                # Preserve the swing arc: lift for clearance, never pull a raised
                # hand down to the floor. The loop contact is the one exception.
                height=-low-2 if closing else min(wrist[1],-low-2)
                length=math.sqrt(sum(v*v for v in direction))
                dy=height-origin[1]
                dy=max(-length+1,min(length-1,dy))
                reach=math.sqrt(length*length-dy*dy)
                planar=math.hypot(direction[0],direction[2])
                target=[direction[0]*reach/planar,dy,direction[2]*reach/planar]
                set_world(p,sk,elbow,R.m3mul(R.swing(direction,target),rotations[elbow]),history)
                set_world(p,sk,hand,desired,history)
            corrected.append(p)
        if loop==0:
            # Choose equivalent Euler branches continuously through the seam.
            for bone in (8,9,12,13):
                previous=corrected[-2][bone][3:6]
                for p in corrected:
                    angles=mmd.matrix_euler(mmd.rot_matrix(*p[bone][3:6]),previous)
                    p[bone][3:6]=[round(v) for v in angles];previous=angles
                corrected[-1][bone][3:6]=corrected[0][bone][3:6]
        animation=replace_channels(model.anims.anims[model.anims.table[slot]],corrected,loop,24,
                                   {(b,c) for b in (8,9,12,13) for c in (3,4,5)},tolerance=0)
        model.anims.table[slot]=len(model.anims.anims)
        model.anims.anims.append(animation)
    from tools.models.reviewed_motion import finish
    return finish(model)[0]
