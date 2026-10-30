#!/usr/bin/env python3
"""Reviewed secondary field acting that preserves source travel and leg channels."""
import os as _model_os
import sys as _model_sys
_model_repo_root = _model_os.path.abspath(_model_os.path.join(_model_os.path.dirname(__file__), '../../..'))
_model_sys.path[:0] = [_model_repo_root, _model_os.path.join(_model_repo_root, 'tools')]
import argparse, copy, hashlib, json, math
from pathlib import Path
import numeric as np
import mmd, animsheet, motionstorage
from tools.models.field_animations.articulation import replace_channels
from motiondiscidentity import changed_programs
from tools.models.field_animations.war_greymon import rotation, set_rotation

PROFILES = {
    187: dict(source='f37cb5a299e02d001e064fd86f36503ba83d8b82779a8998302df79c19603c5b', bones=28, slots=[2], feet=[24,27],
              channels={b for b in [3,4,5,6,7,8,13,14,16,17,18,20]},
              style='supple guarded arms and delayed antennae; original torso, travel and legs retained'),
    190: dict(source='b57233063c512508b7a2fbb487e7a35bc8d166859cec4fdbef6246c85f5f731f', bones=31, slots=[2,4], feet=[26,29], channels=set(range(11,19)),
              style='coherent restrained feather fan instead of a single twisting feather; original body, arms, ribbons and legs retained'),
    191: dict(source='1d90b34ecbd9ac0fa80cc98613b1e43fe1738c096662aaf9504668d6e43cce6c', bones=23, slots=[3], feet=[8,12,18,21], channels={2,3},
              neck_lift=65, head_lift=60, style='less folded tired head with native jaw acting; original mechanical quadruped body, paws, wings and tail retained'),
    199: dict(source='780e2a0ead735377c1c9470546dbeb07db6e83489cdb2fd85e2d7f733b58c071', bones=31, slots=[2,3,4], feet=[14,17], channels={8,11,27,28},
              style='delayed wrists and segmented tail; original body, gait, cannons and wing acting retained'),
}


def build(data, sk):
    digest = hashlib.sha256(data).hexdigest()
    matches = [(sid,cfg) for sid,cfg in PROFILES.items() if cfg.get('source') == digest]
    if len(matches) != 1:
        raise ValueError('No reviewed secondary-acting profile for this effective source')
    sid,cfg = matches[0]; n = len(sk); assert n == cfg['bones']
    mmd.exe().skeleton[sid] = sk; mmd.exe().bone_count[sid] = n
    old = mmd.MMD.parse(data,n); old.type = sid; new = copy.deepcopy(old); checks = []
    channels = {(b,c) for b in cfg['channels'] for c in [3,4,5]}
    for slot in cfg['slots']:
        fs,loop,events = animsheet.slot_frames(old,n,slot); duration = len(fs)-1; assert loop == 0
        world = np.array([mmd.bone_matrices(old,p) for p in fs])
        sep = world[:,cfg['feet'][0],2,3]-world[:,cfg['feet'][1],2,3]
        drive = sep[:-1]-np.mean(sep[:-1]); drive /= max(1,np.max(np.abs(drive)))
        theta = 2*np.pi*np.arange(duration)/duration
        a,b = np.linalg.lstsq(np.column_stack([np.sin(theta),np.cos(theta)]),drive,rcond=None)[0]
        phase = math.atan2(b,a); frames = []; hist = {}
        for tick,source in enumerate(fs):
            p = copy.deepcopy(source); t = 2*math.pi*tick/duration+phase
            def add(b,angles):
                set_rotation(p,b,np.array(mmd.rot_matrix(*source[b][3:6]))@rotation(angles),hist)
            if sid == 187:
                for shoulder,elbow,hand,sign in [(13,14,16,1),(17,18,20,-1)]:
                    add(shoulder,[-6+sign*8*math.cos(t-.2),0,sign*1.5*math.sin(t)])
                    add(elbow,[sign*5*math.cos(t-.8),0,0])
                    add(hand,[-sign*3*math.cos(t-1.1),0,0])
                for chain,sign in [([3,4,5],1),([6,7,8],-1)]:
                    for i,bone in enumerate(chain):add(bone,[1.5*math.sin(t-.5-i*.3),sign*1.2*math.sin(t-.7-i*.3),0])
            elif sid == 190:
                for side,bones in [(1,range(11,15)),(-1,range(15,19))]:
                    for i,bone in enumerate(bones):
                        # The source moves feather14 alone through the otherwise fixed fan.
                        base=fs[0][bone] if bone==14 else source[bone]
                        r=np.array(mmd.rot_matrix(*base[3:6]))
                        set_rotation(p,bone,r@rotation([1.5*math.sin(t-.35*i),side*(2.5+i*.5)*math.sin(t-.4-.25*i),side*1.2*math.cos(t-.2*i)]),hist)
            elif sid == 191:
                original=np.array(mmd.bone_matrices(old,source))
                neck_parent=np.array(mmd.bone_matrices(old,p))[sk[2][1],:3,:3]
                set_rotation(p,2,neck_parent.T@rotation([-cfg['neck_lift'],0,0])@original[2,:3,:3],hist)
                parent=np.array(mmd.bone_matrices(old,p))[sk[3][1],:3,:3]
                set_rotation(p,3,parent.T@rotation([-cfg['head_lift'],0,0])@original[3,:3,:3],hist)
            else:
                for bone,sign in [(8,-1),(11,1)]:add(bone,[sign*2*math.sin(t-.9),0,sign*.8*math.cos(t-.7)])
                for bone,amp,delay in [(27,2.5,.6),(28,4,1.0)]:add(bone,[amp*.4*math.sin(t-delay-.2),amp*math.sin(t-delay),0])
            frames.append(p)
        frames[-1][1:]=copy.deepcopy(frames[0][1:])
        original=old.anims.anims[old.anims.table[slot]]
        anim=replace_channels(original,frames,loop,n,channels)
        new.anims.anims.append(anim); new.anims.table[slot]=len(new.anims.anims)-1
        before=mmd.AnimPlayer(original,n,slot); after=mmd.AnimPlayer(anim,n,slot); max_foot=0.
        for tick in range(duration*4):
            assert before.tick() and after.tick(); assert before.base==after.base
            for bone in range(n):
                for c in range(9):
                    if (bone,c) not in channels:assert before.pose[bone][c]==after.pose[bone][c],(slot,tick,bone,c)
            wa=np.array(mmd.bone_matrices(old,before.pose)); wb=np.array(mmd.bone_matrices(old,after.pose))
            max_foot=max(max_foot,float(np.linalg.norm(wa[cfg['feet'],:3,3]-wb[cfg['feet'],:3,3],axis=1).max()))
        assert max_foot==0,(sid,slot,max_foot)
        checks.append(dict(slot=slot,period=duration,original_root_and_leg_channels_exact_for_four_cycles=True,
                           original_events_and_controls_preserved=True,max_foot_world_error=max_foot))
    import motioncyclelayer
    for anim in new.anims.anims:anim.tail=b''
    new.anims.anims,new.anims.table=motioncyclelayer.share_identical_streams(new.anims.anims,new.anims.table)
    result=new.build(); parsed=mmd.MMD.parse(result,n)
    assert changed_programs(old,parsed)==cfg['slots']; assert old.tmd.build()==parsed.tmd.build()
    storage=motionstorage.audit(result,n); assert storage['fits'],storage
    return result,dict(species=sid,source_sha256=digest,output_sha256=hashlib.sha256(result).hexdigest(),
                       changed_slots=cfg['slots'],profile_style=cfg['style'],mesh_exact=True,other_programs_exact=True,
                       checks=checks,storage=storage)


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--specimen',type=Path,required=True); p.add_argument('--out',type=Path,required=True); a=p.parse_args(); import species
    s=json.loads(a.specimen.read_text()); s['_path']=str(a.specimen); raw,_=species.species_model(s)
    data,report=build(raw,s['model']['skeleton']); a.out.mkdir(parents=True,exist_ok=False)
    model=a.out/f'{s["id"]}-acting.MMD'; model.write_bytes(data); s['model']['file']=str(model.resolve()); s['model'].pop('slot_aliases',None); s.pop('_path',None)
    (a.out/'specimen.json').write_text(json.dumps(s,indent=2)+'\n'); (a.out/'report.json').write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2))

if __name__=='__main__':main()
