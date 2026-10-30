"""Gatomon's grooming performance and supported short-leg field strides.

The rig has a single segment from hip to paw. Stance height follows that
fixed-length sphere; a lifted paw swings slightly outward rather than
stretching its leg. Native grooming and distinct poor-idle timing remain.
Moving gloves carry forward, the gaze settles and the tail/ears respond.
"""
import copy
import hashlib
import math
import numeric as np
import mmd
import animsheet
import motioncyclelayer
import motionstorage
import motionsecondary
import retarget
from tools.models.field_animations.war_greymon import align, set_rotation, rotation
from motiontailspace import interpolate_pose
from motiondiscidentity import changed_programs
from tools.models.field_animations.articulation import replace_channels

SOURCE = '340afafa4be66741c7e439ba8670103ed3d6546e37f8078f326a4a402e14137c'
PARENTS = [-1, 2, 0, 1, 1, 2, 5, 2, 7, 2, 9, 2, 11, 2, 13, 14, 15, 16, 17]
TWIST = -30


def _author(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    native=animsheet.slot_frames(old,n,0)[0];vs={b:np.array(old.tmd.obj_verts(o))[:,:3] for b,(o,_) in enumerate(sk) if o>=0}
    def world(f):
     g=copy.deepcopy(f);g[0]=[4096]*3+[0]*6;return np.array(mmd.bone_matrices(old,g))
    ref=copy.deepcopy(native[0]);rw=world(ref);reports=[]
    for slot in [0,1,2,3,4]:
     source,_,events=animsheet.slot_frames(old,n,slot);original_period=len(source)-1
     duration=original_period if slot in [0,1] else 48
     period={0:83,1:16,2:8,3:12,4:6}[slot]; speed={0:0,1:0,2:7,3:4,4:13}[slot]
     lift={0:0,1:0,2:6,3:4,4:8}[slot];poses=[];plans=[];hist={};err=[];corrections=[]
     for t in range(duration+1):
      phase=(t%period)/period;theta=2*math.pi*phase
      sample=t if slot in [0,1] else phase*original_period
      j=min(original_period-1,int(sample));f=interpolate_pose(source[j],source[j+1],round((sample-j)*4096));f=[[round(v) for v in b] for b in f];f[0]=[4096]*3+[0]*6
      if slot in [2,3,4]:
       f[2][3:6]=[round(v*4096/360) for v in [{2:35,3:50,4:40}[slot],1*math.sin(theta),1.2*math.sin(theta)]]
       f[2][6:9]=[round(1.5*math.sin(theta)),0,0]
       w=world(f);set_rotation(f,1,w[2,:3,:3].T@rotation([{2:2,3:12,4:-3}[slot]+1.5*math.sin(2*theta),0,0]),hist)
       for hip,hand,sign in [(5,6,1),(7,8,-1)]:
        shoulder=rotation([-15+sign*{2:7,3:4,4:10}[slot]*math.sin(theta),0,sign*1.5*math.sin(theta-.4)])@np.array(mmd.rot_matrix(*ref[hip][3:6]))
        set_rotation(f,hip,shoulder,hist)
        w=world(f);glove=rotation([-25,0,0])@rw[hand,:3,:3]@rotation([-3+2*sign*math.sin(theta-.5),sign*2*math.sin(theta-.8),0]);set_rotation(f,hand,w[hip,:3,:3].T@glove,hist)
       for b in [3,4]:f[b][3]+=round(1.3*4096/360*math.sin(2*math.pi*t/duration-.4*(b-3)))
       for b in range(13,19):
        f[b][3:6]=copy.deepcopy(ref[b][3:6]);f[b][3]+=round(1.4*4096/360*math.sin(2*math.pi*t/duration-.4*(b-13)))
        f[b][4]+=round(2*4096/360*math.sin(2*math.pi*t/duration-.5*(b-13)))
       w=world(f);set_rotation(f,13,w[2,:3,:3].T@rw[13,:3,:3]@rotation([2*math.sin(2*math.pi*t/duration),5*math.sin(2*math.pi*t/duration),0]),hist)
      elif slot==1:
       for b in [4,13,14,15,16,17,18]:f[b][3]+=round((.7 if b==4 else 1.4)*4096/360*math.sin(theta-.3*(b-13)))
      if slot==1:
       w=world(f)
       for hip,hand in [(5,6),(7,8)]:set_rotation(f,hand,w[hip,:3,:3].T@rotation([-20,0,0])@w[hand,:3,:3],hist)
      f[2][7]=0;w=world(f);targets=[];requirements=[]
      for side,(hip,foot) in enumerate([(9,10),(11,12)]):
       sign=1 if side==0 else -1;h=w[hip,:3,3];ph=((t+side*period/2)%period);contact=period/2;stance=slot in [0,1] or ph<=contact
       if slot in [0,1]:z=8;up=4;pitch=0
       elif stance:z=8-speed*contact/2+speed*ph;up=4;pitch=0
       else:
        u=(ph-contact)/(period-contact);smooth=6*u**5-15*u**4+10*u**3;half=speed*contact/2
        z=(8+half)*(1-smooth)+(8-half)*smooth+(period-contact)*speed*u*(1-u)*(1-2*u)**5
        up=4+lift*math.sin(math.pi*u)**2;pitch=4*math.sin(math.pi*u)
       rf=rotation([pitch,-sign*5,0]);bottom=float((vs[foot]@rf.T)[:,1].max());goalY=-up-bottom
       x=sign*38;length=float(np.linalg.norm(f[foot][6:9]));reach=length**2-(x-h[0])**2-(z-h[2])**2
       assert reach>0,(slot,t,hip,'stance reach',reach)
       required=goalY-h[1]-math.sqrt(reach)
       if stance:requirements.append(required)
       targets.append(dict(hip=hip,foot=foot,sign=sign,x=x,z=z,rf=rf,goalY=goalY,stance=stance,phase=ph,up=up,length=length))
      assert requirements
      f[2][7]=round(sum(requirements)/len(requirements));w=world(f);row=[]
      for a in targets:
       hip,foot=a['hip'],a['foot'];h=w[hip,:3,3];z=a['z'];x=a['x'];dy=a['goalY']-h[1]
       if not a['stance']:
        square=a['length']**2-dy**2-(z-h[2])**2
        assert square>=0 and dy>0,(slot,t,hip,'swing reach',square,dy)
        x=h[0]+a['sign']*math.sqrt(square)
       else:
        reach=a['length']**2-(x-h[0])**2-(z-h[2])**2;dy=math.sqrt(reach)
       goal=np.array([x,h[1]+dy,z]);oldvec=rw[hip,:3,:3]@np.array(f[foot][6:9]);rh=align(oldvec,goal-h)@rw[hip,:3,:3]@np.array(retarget.from_axis_angle((np.array(f[foot][6:9])/a['length']).tolist(),math.radians(a['sign']*TWIST)))
       set_rotation(f,hip,w[2,:3,:3].T@rh,hist);actual=world(f);set_rotation(f,foot,actual[hip,:3,:3].T@a['rf'],hist)
       actual=world(f);err.append(float(np.linalg.norm(actual[foot,:3,3]-goal)))
       row.append(dict(foot=foot,stance=a['stance'],phase=a['phase'],ankle=goal.tolist(),orientation=a['rf'].tolist(),up=a['up']))
      w=world(f);points=[v for b in range(13,19) for v in vs[b]@w[b,:3,:3].T+w[b,:3,3]]
      correction=0
      if max(v[1] for v in points)>-4 and slot in [2,3,4]:
       hinge=np.array(motionsecondary.clearance_rotation([v.tolist() for v in points],w[13,:3,3].tolist(),w[2,:3,0].tolist(),[0,30],-4));correction=math.degrees(math.acos(np.clip((np.trace(hinge)-1)/2,-1,1)))
       set_rotation(f,13,w[2,:3,:3].T@hinge@w[13,:3,:3],hist)
      corrections.append(correction);f[0][8]=-speed*t;poses.append(f);plans.append(row)
     poses[-1][1:]=copy.deepcopy(poses[0][1:])
     # Preserve native event payloads; movement sounds are synchronized below.
     if slot in [0,1]:selected_events=events
     else:
      assert all(k=='sound' for _,k,_ in events),events
      payload=copy.deepcopy(events[0][2]);selected_events=[]
      for tick in range(0,duration,period//2):
       e=copy.deepcopy(payload);e['frame']=tick+1;selected_events.append((tick,'sound',e))
     if slot in [0,1]:
      channels={(2,7)}|{(b,c) for b in [9,10,11,12] for c in [3,4,5]}
      if slot==1:channels|={(b,c) for b in [4,6,8,13,14,15,16,17,18] for c in [3,4,5]}
      animation=replace_channels(old.anims.anims[old.anims.table[slot]],poses,0,n,channels)
     else:animation=mmd.encode_anim(poses,n,loop_sample=0,events=selected_events,tol=1,repeats=False)
     new.anims.table[slot]=len(new.anims.anims);new.anims.anims.append(animation)
     reports.append(dict(slot=slot,duration=duration,period=period,speed=speed,maximum_ankle_FK_error=max(err),tail_correction_maximum=max(corrections),plans=plans,carrierY=[f[2][7] for f in poses],selected_events=selected_events))
    return new, reports


def build(data, sk):
    if (hashlib.sha256(data).hexdigest() != SOURCE or [b[1] for b in sk] != PARENTS
            or [b[0] for b in sk] != list(range(-1, 18))):
        raise ValueError('Gatomon requires its reviewed nineteen-bone source')
    n = len(sk)
    mmd.exe().skeleton[234] = sk
    mmd.exe().bone_count[234] = n
    old = mmd.MMD.parse(data, n)
    old.type = 234
    new, solver = _author(old, sk)
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = mmd.MMD.parse(result, n)
    actual.type = 234
    assert old.tmd.build() == actual.tmd.build()
    assert changed_programs(old, actual) == [0, 1, 2, 3, 4]
    checks = []
    for row in solver:
        slot, duration = row['slot'], row['duration']
        original = old.anims.anims[old.anims.table[slot]]
        authored = actual.anims.anims[actual.anims.table[slot]]
        frames, loop, events = animsheet.slot_frames(actual, n, slot)
        assert len(frames) == duration + 1 and loop == 0
        assert events == row['selected_events']
        allowed = {(2, 7)} | {(b, c) for b in [9, 10, 11, 12] for c in [3, 4, 5]}
        if slot == 1:
            allowed |= {(b, c) for b in [4, 6, 8, 13, 14, 15, 16, 17, 18] for c in [3, 4, 5]}
        before = mmd.AnimPlayer(original, n, slot)
        after = mmd.AnimPlayer(authored, n, slot)
        cycle = []
        for t in range(duration * 9 + 1):
            assert before.tick() and after.tick()
            assert after.root == [0, 0, -row['speed'] * t], (slot, t, 'root')
            for b in range(1, n):
                assert before.pose[b][:3] == after.pose[b][:3]
                if b != 2:
                    assert before.pose[b][6:9] == after.pose[b][6:9]
                if slot in [0, 1]:
                    for c in range(9):
                        if (b, c) not in allowed:
                            assert before.pose[b][c] == after.pose[b][c], (slot, t, b, c)
            if t < duration:
                cycle.append(copy.deepcopy(after.pose[1:]))
            else:
                assert after.pose[1:] == cycle[t % duration], (slot, t, 'drift')
        if slot in [0, 1]:
            assert [i for i in original.instrs if i['op'] != 'key'] == [i for i in authored.instrs if i['op'] != 'key']
        checks.append(dict(slot=slot, duration=duration, speed=row['speed'],
                           scales_and_limb_translations_exact_nine_cycles=True,
                           protected_idle_channels_exact_nine_cycles=slot in [0, 1],
                           pose_root_events_and_repetitions_checked_nine_cycles=True))
    storage = motionstorage.audit(result, n)
    assert storage['fits'], storage
    return result, dict(species=234, source_sha256=SOURCE,
                        output_sha256=hashlib.sha256(result).hexdigest(),
                        changed_slots=[0, 1, 2, 3, 4], mesh_exact=True,
                        private33_care_battle_and_other_programs_exact=True,
                        native_grooming_period=83, poor_idle_period=16,
                        checks=checks, solver=solver, storage=storage)
