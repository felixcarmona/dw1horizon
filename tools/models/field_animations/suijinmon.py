"""Suijinmon's four-legged field gait and standing feeding pose.

The lower body is a centaur rig: the four three-bone legs carry the weight,
while the upright torso, cannon arms and tail follow the footfalls with a lag.
Feeding retains the upper-body acting without the biped donor's crouch.
"""
import copy
import hashlib
import math

import animsheet
import mmd
import motionstorage
from tools.models.field_animations import quadruped as q
from motiondiscidentity import changed_programs
from tools.models.field_animations.pace import _root_channels, _retimed_events

PROFILE = dict(
    species=408, name='Suijinmon',
    source='d22fecd28ed5c3c1b4a39007970e7f34f2040ddad3434159106cf3a4b4fefd96',
    parents=[-1,0,1,2,3,1,5,6,1,8,9,1,11,12,1,14,15,1,17,18,18,18,21,22,23,17,25,25,25,28,29,30],
    pelvis=1, chest=17, neck=None, head=17,
    legs={'RF':(11,12,13,1,True),'LF':(8,9,10,-1,True),
          'RH':(2,3,4,1,False),'LH':(14,15,16,-1,False)},
    tail=(5,6,7), loose=((18,1),(25,-1),(21,1),(28,-1)),
    pole={True:[.3,.2,.4],False:[.2,.2,.5]},sink=3.2,
    sole={True:[0,0,-45],False:[0,0,-25]},
    reach={'front':-10,'hind':20}, fold={True:40,False:40},clear=18,
    gaits={
        2:dict(name='centaur walk',kind='walk',ticks=14,speed=18,
               # diagonal pairs a little apart (left hind, right front; right hind, left front): the thick legs of one
               # side are never at opposite ends of their strides, so they do not pass through each other
               touchdown={'LH':0.,'RF':.22,'RH':.5,'LF':.72},
               duty={k:.6 for k in ('LH','LF','RH','RF')},
               track={'front':-12,'hind':12},wide={'front':25,'hind':25},world_ease=.5,
               lift={'front':30,'hind':30},curl={'front':30,'hind':30},peel={'front':20,'hind':20},
               reach={'front':-30,'hind':30},out={'front':10,'hind':10},snap=False,slip=.05,
               height=5,tilt=0,chest_up=0,neck=0,nod=.8,bob=3,pitch=1.2,flex=1.5,roll=2.4,yaw=1.2,head=.4,
               tail=4,loose=3.5,steps=('LH','RF','RH','LF')),
        4:dict(name='centaur gallop',kind='gallop',ticks=14,speed=40,sink=2.5,
               touchdown={'LH':0.,'RH':.1,'RF':.32,'LF':.44},
               duty={k:.3 for k in ('LH','LF','RH','RF')},
               track={'front':-25,'hind':25},wide={'front':10,'hind':10},
               lift={'front':45,'hind':40},curl={'front':40,'hind':35},peel={'front':25,'hind':25},
               reach={'front':-30,'hind':25},out={'front':20,'hind':15},snap=True,slip=.08,
               height=15,tilt=0,chest_up=-2,neck=0,nod=1.2,bob=8,pitch=3,flex=4,roll=1.5,yaw=1.5,head=.4,
               tail=7,loose=4,steps=('LH','RF')),
    },
)


def build(data, skeleton):
    walked, report = q.build(data, skeleton, PROFILE)
    n=len(skeleton)
    original=mmd.MMD.parse(data,n);original.type=408
    new=mmd.MMD.parse(walked,n);new.type=408
    walk,_,steps=animsheet.slot_frames(new,n,2)
    slow=_root_channels(walk,21,12)
    new.anims.anims[new.anims.table[3]]=mmd.encode_anim(
        slow,n,loop_sample=0,events=_retimed_events(steps,14,21),tol=1)
    idle=animsheet.slot_frames(original,n,0)[0][0]
    frames,loop,events=animsheet.slot_frames(original,n,8)
    for t,pose in enumerate(frames):
        # Keep the donor's arms and torso; its pelvis crouch sinks all four legs.
        pose[:17]=copy.deepcopy(idle[:17])
        # The long cannon hand needs a smaller torso bow than the biped donor.
        pose[17][3]=round(idle[17][3]+.45*(pose[17][3]-idle[17][3]))
        phase=2*math.pi*t/(len(frames)-1)
        pose[1][7]-=4
        for j,b in enumerate((5,6,7)):
            pose[b][4]+=round(1.5*q.DEG*math.sin(phase-.25*j))
    index=new.anims.table[8]
    new.anims.anims[index]=mmd.encode_anim(frames,n,loop_sample=loop,events=events,tol=1)
    result=new.build()
    rig=q.Rig(new,skeleton,PROFILE)
    played=animsheet.slot_frames(new,n,8)[0]
    floor=q._floor(rig,played)
    assert floor<=q.FLOOR, ('feeding',floor)
    report['feeding']=dict(frames=len(frames),upper_body_acting_retained=True,torso_bow_gain=.45,standing_lower_body=True,
                           lowest_point=round(floor,2))
    report['condition_walk']=dict(ticks=21,units_per_tick=12)
    report['output_sha256']=hashlib.sha256(result).hexdigest()
    actual=mmd.MMD.parse(result,n)
    assert original.tmd.build()==actual.tmd.build()
    changed=changed_programs(original,actual)
    assert changed==[2,3,4,8,35,36], changed
    report['changed_slots']=changed
    report['storage']=motionstorage.require(result,n)
    return result,report
