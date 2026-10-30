#!/usr/bin/env python3
"""Layer explicit native bones over repeated field cycles with bounded retiming.

Locally extracted assets only. Field cadence and root displacement repeat exactly;
native selected-bone performance is resampled over a nearby integer cycle multiple.
Native events require explicit ownership; optional native texture states retain command order while field sounds repeat.
"""
import argparse,copy,json
from pathlib import Path
import motionlab as M
import motionloops,motionstorage
import motionloopcontracts
from motiontailspace import interpolate_pose


def close_equivalent_field_rotations(poses,roots):
    """Close only equivalent Euler branches; never hide a different end pose."""
    import retarget as R
    changed=[]
    for bone in roots:
        first,last=poses[0][bone],poses[-1][bone]
        if all((last[c]-first[c])%4096==0 for c in range(3,6)):continue
        a,b=R.rot_of(first),R.rot_of(last)
        error=max(abs(a[i][j]-b[i][j]) for i in range(3) for j in range(3))
        if error>.005:raise ValueError('field rotation endpoint is not equivalent')
        changed.append(dict(bone=bone,original_endpoint=last[3:6],closed_endpoint=first[3:6],maximum_matrix_error=error))
        last[3:6]=first[3:6]
    return changed


def share_identical_streams(animations,table):
    """Share only byte-identical programs, preserving every slot's full stream."""
    unique=[];seen={};remap={}
    for i in sorted({i for i in table if i is not None}):
        stream=animations[i].build()
        if stream not in seen:seen[stream]=len(unique);unique.append(animations[i])
        remap[i]=seen[stream]
    return unique,[None if i is None else remap[i] for i in table]


def static_uniform_field_body(skeleton,poses,policy):
    if not policy:return {}
    if set(policy)!={'bone','scale','review_basis'} or not policy['review_basis']:raise ValueError('reviewed static field body required')
    bone,scale=policy['bone'],policy['scale']
    if type(bone) is not int or not 0<bone<len(skeleton) or skeleton[bone][1]!=0:raise ValueError('static field body must be root child')
    if type(scale) is not int or not 0<scale<=32767:raise ValueError('invalid static field body scale')
    if any(p[bone][:3]!=[scale]*3 for p in poses):raise ValueError('static field body scale changed')
    return {bone:scale}


def normalize_field_world_support(model,skeleton,field,native,roots,tolerance,review_basis,static_body=None):
    """Normalize reviewed one-unit scale noise in working poses only."""
    if type(tolerance) is not int or tolerance!=1 or not review_basis or not roots:
        raise ValueError('field support scale normalization requires reviewed one-unit tolerance')
    import retarget as R
    support=set()
    for root in roots:
        if type(root) is not int or not 0<root<len(skeleton):raise ValueError('invalid field support root')
        bone=root
        while bone>=0:support.add(bone);bone=skeleton[bone][1]
    pinned=static_uniform_field_body(skeleton,field+native,static_body)
    if any(b not in support for b in pinned):raise ValueError('static field body must carry support roots')
    copies=copy.deepcopy((field,native));maximum=0;changed=set()
    for original,poses in zip((field,native),copies):
        for before,after in zip(original,poses):
            altered=R.normalize_near_unit_support(after,support-set(pinned),tolerance)
            if not altered:continue
            changed.update(altered);wa=M.mmd.bone_matrices(model,before);wb=M.mmd.bone_matrices(model,after)
            for bone,(obj,_) in enumerate(skeleton):
                if obj<0:continue
                for vertex in model.tmd.obj_verts(obj):
                    a=[sum(wa[bone][i][j]*vertex[j] for j in range(3))+wa[bone][i][3] for i in range(3)]
                    b=[sum(wb[bone][i][j]*vertex[j] for j in range(3))+wb[bone][i][3] for i in range(3)]
                    maximum=max(maximum,sum((x-y)**2 for x,y in zip(a,b))**.5)
            if maximum>1:raise ValueError('field support normalization moves mesh by more than one unit')
    return *copies,dict(bones=sorted(changed),maximum_mesh_vertex_shift=maximum,tolerance=tolerance)


def layer(field,native,bones,repeats,maximum_retime_fraction,skeleton=None,native_world_roots=(),allow_uniform_ancestors=False,field_world_roots=(),native_anchors=None,static_field_body=None,native_translation_roots=()):
    period=len(field)-1;own=len(native)-1
    if period<2 or own<2 or type(repeats) is not int or not 1<=repeats<=16:
        raise ValueError('invalid cycle lengths or repeat count')
    if len(set(bones))!=len(bones) or not bones or any(type(b) is not int or not 0<b<len(field[0]) for b in bones):
        raise ValueError('explicit unique non-root bones required')
    if any(len(p)!=len(field[0]) for p in field+native):raise ValueError('bone count differs')
    if any(p[0][:6]!=[4096]*3+[0]*3 for p in field):raise ValueError('field root must have unit scale and zero rotation')
    if (len(set(native_translation_roots))!=len(native_translation_roots)
        or any(type(b) is not int or b not in field_world_roots for b in native_translation_roots)):
        raise ValueError('native translations require unique reviewed field support boundaries')
    native_anchors=native_anchors or {}
    if native_anchors:
        if skeleton is None or len(skeleton)!=len(field[0]):raise ValueError('native anchors require matching skeleton')
        for b,anchor in native_anchors.items():
            if type(b) is not int or type(anchor) is not int or not 0<b<len(skeleton) or not 0<anchor<len(skeleton):raise ValueError('invalid native attachment anchor')
            if b not in bones or skeleton[b][1] in bones or b in native_world_roots:raise ValueError('native anchor requires a unique selected branch boundary')
            ancestors=[];parent=skeleton[b][1]
            while parent>=0:ancestors.append(parent);parent=skeleton[parent][1]
            if anchor not in ancestors:raise ValueError('native attachment anchor must be an ancestor')
            if any(parent in native_anchors for parent in ancestors):raise ValueError('nested native attachment roots')
            for ancestor in [b,*ancestors]:
                if any(p[ancestor][:3]!=[4096]*3 for p in field+native):raise ValueError('native attachment requires unit ancestor scales')
        import retarget as R
    if field_world_roots:
        if skeleton is None or len(skeleton)!=len(field[0]) or len(set(field_world_roots))!=len(field_world_roots):
            raise ValueError('field world roots require matching skeleton and unique roots')
        pinned=static_uniform_field_body(skeleton,field+native,static_field_body)
        if any(b not in bones for b in pinned):raise ValueError('static field body must be native acting')
        for b in field_world_roots:
            if type(b) is not int or not 0<b<len(skeleton) or b in bones or skeleton[b][1] not in bones:
                raise ValueError('field world root must border a restored native parent')
            ancestor=b
            while ancestor>=0:
                if ancestor!=b and ancestor in field_world_roots:raise ValueError('nested field world roots')
                if any(p[ancestor][:3]!=[pinned.get(ancestor,4096)]*3 for p in field+native):raise ValueError('field world orientation requires unit ancestor scales')
                ancestor=skeleton[ancestor][1]
        import retarget as R
    if native_world_roots:
        if skeleton is None or len(skeleton)!=len(field[0]) or len(set(native_world_roots))!=len(native_world_roots):
            raise ValueError('world orientation roots require matching skeleton')
        for b in native_world_roots:
            if b not in bones or skeleton[b][1] in bones:raise ValueError('world orientation requires selected branch boundary')
        import retarget as R
        for b in native_world_roots:
            if allow_uniform_ancestors and any(min(p[b][:3])<=0 for p in field+native):raise ValueError('world branch scale must be positive')
            ancestor=skeleton[b][1] if allow_uniform_ancestors else b
            while ancestor>=0:
                if allow_uniform_ancestors:
                    if any(min(p[ancestor][:3])<=0 or len(set(p[ancestor][:3]))!=1 for p in field+native):raise ValueError('world orientation requires positive uniform ancestor scales')
                elif any(p[ancestor][:3]!=[4096]*3 for p in field+native):raise ValueError('world orientation requires unit ancestor scales')
                ancestor=skeleton[ancestor][1]
    duration=period*repeats
    if not 0<=maximum_retime_fraction<=.2 or abs(duration/own-1)>maximum_retime_fraction:
        raise ValueError('native retiming exceeds reviewed bound')
    net=[field[-1][0][c]-field[0][0][c] for c in range(6,9)]
    out=[];previous={};world_error=0;field_world_error=0;anchor_position_error=0;anchor_rotation_error=0
    for t in range(duration+1):
        cycle,phase=divmod(t,period)
        pose=copy.deepcopy(field[phase])
        for axis in range(3):pose[0][6+axis]+=cycle*net[axis]
        numerator=t*own;index,remainder=divmod(numerator,duration)
        ref=native[-1] if index==own else interpolate_pose(native[index],native[index+1],remainder*4096//duration)
        for b in bones:pose[b]=[round(v) for v in ref[b]]
        for b in native_translation_roots:pose[b][6:9]=[round(v) for v in ref[b][6:9]]
        if field_world_roots:
            desired=R.world_rots(skeleton,field[phase])
            for b in field_world_roots:
                parent=skeleton[b][1];current=R.world_rots(skeleton,pose)
                local=R.m3mul(R.m3t(current[parent]),desired[b])
                pose[b][3:6]=[round(v) for v in M.mmd.matrix_euler(local,previous.get(b,pose[b][3:6]))]
                previous[b]=pose[b][3:6]
                actual=R.world_rots(skeleton,pose)[b]
                field_world_error=max(field_world_error,max(abs(actual[i][j]-desired[b][i][j]) for i in range(3) for j in range(3)))
            if field_world_error>.005:raise ValueError('field world orientation drift exceeds integer angle precision')
        if native_world_roots:
            desired=R.world_rots(skeleton,ref)
            for b in native_world_roots:
                parent=skeleton[b][1]
                if parent<0:raise ValueError('world branch must have a parent')
                current=R.world_rots(skeleton,pose)
                local=R.m3mul(R.m3t(current[parent]),desired[b])
                pose[b][3:6]=[round(v) for v in M.mmd.matrix_euler(local,previous.get(b,pose[b][3:6]))]
                previous[b]=pose[b][3:6]
                actual=R.world_rots(skeleton,pose)[b]
                world_error=max(world_error,max(abs(actual[i][j]-desired[b][i][j]) for i in range(3) for j in range(3)))
            if world_error>.005:raise ValueError('native world orientation drift exceeds integer angle precision')
        if native_anchors:
            native_rot=R.world_rots(skeleton,ref);native_pos=R.world_pos(skeleton,ref)
            for b,anchor in native_anchors.items():
                current_rot=R.world_rots(skeleton,pose);current_pos=R.world_pos(skeleton,pose);parent=skeleton[b][1]
                transform=R.m3mul(current_rot[anchor],R.m3t(native_rot[anchor]))
                relative=[native_pos[b][i]-native_pos[anchor][i] for i in range(3)]
                desired_pos=[current_pos[anchor][i]+sum(transform[i][j]*relative[j] for j in range(3)) for i in range(3)]
                desired_rot=R.m3mul(transform,native_rot[b]);inverse=R.m3t(current_rot[parent])
                delta=[desired_pos[i]-current_pos[parent][i] for i in range(3)]
                pose[b][6:9]=[round(sum(inverse[i][j]*delta[j] for j in range(3))) for i in range(3)]
                local=R.m3mul(inverse,desired_rot)
                pose[b][3:6]=[round(v) for v in M.mmd.matrix_euler(local,previous.get(b,pose[b][3:6]))];previous[b]=pose[b][3:6]
                actual_pos=R.world_pos(skeleton,pose)[b];actual_rot=R.world_rots(skeleton,pose)[b]
                anchor_position_error=max(anchor_position_error,sum((a-b)**2 for a,b in zip(actual_pos,desired_pos))**.5)
                anchor_rotation_error=max(anchor_rotation_error,max(abs(actual_rot[i][j]-desired_rot[i][j]) for i in range(3) for j in range(3)))
            if anchor_position_error>1 or anchor_rotation_error>.005:raise ValueError('native attachment compensation exceeds integer precision')
        out.append([[round(v) for v in channels] for channels in pose])
    proof=dict(field_period_ticks=period,native_period_ticks=own,field_cycles=repeats,combined_period_ticks=duration,native_duration_ratio=duration/own,root_net_per_field_cycle=net)
    if native_world_roots:proof.update(native_world_orientation_roots=list(native_world_roots),maximum_world_rotation_matrix_error=world_error)
    if native_world_roots and allow_uniform_ancestors:proof['positive_uniform_world_orientation_ancestors']=True
    if field_world_roots:proof.update(field_world_orientation_roots=list(field_world_roots),maximum_field_world_rotation_matrix_error=field_world_error)
    if native_translation_roots:proof['native_translation_roots']=list(native_translation_roots)
    if native_anchors:proof.update(native_attachment_anchors=native_anchors,maximum_anchor_position_error=anchor_position_error,maximum_anchor_rotation_matrix_error=anchor_rotation_error)
    return out,proof


def repeat_native(native,events,bones,repeats):
    """Repeat closed native poses/events, retaining whole-turn rotations."""
    if type(repeats) is not int or not 1<=repeats<=8:raise ValueError('native cycle count out of bounds')
    if not native or not bones or len(set(bones))!=len(bones) or any(type(b) is not int or not 0<b<len(native[0]) for b in bones):raise ValueError('explicit native non-root bones required')
    if repeats==1:return native,events
    period=len(native)-1
    if period<2:raise ValueError('native cycle too short')
    winding={}
    for b in bones:
        for c in range(9):
            delta=native[-1][b][c]-native[0][b][c]
            if 3<=c<6:
                turns=round(delta/4096)*4096
                if abs(delta-turns)>1:raise ValueError('native rotation does not close')
                winding[b,c]=turns
            elif abs(delta)>1:raise ValueError('native channel does not close')
    poses=[]
    for tick in range(period*repeats+1):
        cycle,phase=divmod(tick,period);pose=copy.deepcopy(native[phase])
        for b in bones:
            for c in range(3,6):
                pose[b][c]+=cycle*winding[b,c]
                if not -32768<=pose[b][c]<32768:raise ValueError('repeated native rotation exceeds signed16 range')
        poses.append(pose)
    repeated=[]
    for cycle in range(repeats):
        for tick,kind,payload in events:
            if not 0<=tick<period:raise ValueError('native closing events need dedicated ownership')
            command=copy.deepcopy(payload);t=tick+cycle*period
            if 'frame' in command:command['frame']=t+1
            repeated.append((t,kind,command))
    return poses,repeated


def combine_events(field,native,field_period,native_period,repeats,policy='field',maximum_texture_shift=1):
    duration=field_period*repeats
    if policy not in ('field','native_texture_with_field_sounds','native_with_field_sounds'):
        raise ValueError('unknown event ownership policy')
    if policy=='field' and native:raise ValueError('native events require explicit ownership')
    if any(t<0 or t>=field_period or kind not in ('sound','tex') for t,kind,_ in field):
        raise ValueError('unsupported field events or closing event')
    native_kinds=('tex','sound') if policy=='native_with_field_sounds' else ('tex',)
    if policy!='field' and (any(kind not in native_kinds or not 0<=t<native_period for t,kind,_ in native)
            or type(maximum_texture_shift) is not int or not 0<=maximum_texture_shift<=1):
        raise ValueError('native events must match explicit ownership policy and <=1tick retiming')
    result=[]
    def add(t,kind,payload):
        c=copy.deepcopy(payload)
        if 'frame' in c:c['frame']=t+1
        result.append((t,kind,c))
    for cycle in range(repeats):
        for t,kind,payload in field:
            if policy!='field' and kind=='tex':continue
            add(t+cycle*field_period,kind,payload)
    mapping=[];previous_source=-1;previous_target=-1
    for t,kind,payload in native:
        if t<previous_source:raise ValueError('native texture events must be ordered')
        target=round(t*duration/native_period)
        if t==previous_source:target=previous_target
        elif target<=previous_target:target=previous_target+1
        if target>=duration or abs(target-t*duration/native_period)>maximum_texture_shift:
            raise ValueError('native texture states cannot fit reviewed event timing')
        add(target,kind,payload);mapping.append(dict(source_tick=t,target_tick=target,**({'kind':kind} if policy=='native_with_field_sounds' else {})))
        previous_source,previous_target=t,target
    result.sort(key=lambda e:(e[0],e[1]!='tex'))
    proof=dict(event_policy=policy,native_texture_event_mapping=mapping,
        original_field_texture_events_replaced=sum(k=='tex' for _,k,_ in field)*repeats if policy!='field' else 0)
    if policy=='native_with_field_sounds':
        proof.update(native_event_mapping=mapping,native_texture_event_mapping=[dict(source_tick=e['source_tick'],target_tick=e['target_tick']) for e in mapping if e['kind']=='tex'],native_sound_events_preserved=sum(k=='sound' for _,k,_ in native),field_sound_events_preserved=sum(k=='sound' for _,k,_ in field)*repeats)
    return result,proof


def require_field_action(slot,source_slot,condition_review_basis=None):
    if type(slot) is not int or slot==source_slot:raise ValueError('explicit separate field slot required')
    if slot in [2,3,4]:return
    if slot in [1,18] and isinstance(condition_review_basis,str) and condition_review_basis.strip():return
    raise ValueError('condition field slots require their own explicit review basis')


def run(recipe,out):
    cfg=json.loads(recipe.read_text())
    if out.exists():raise ValueError('choose new output directory')
    out.mkdir(parents=True);results=[]
    for member in cfg['members']:
        if not member.get('review_basis'):raise ValueError('explicit anatomical review basis required')
        sid=member['species'];path=Path(member['input']);raw=path.read_bytes()
        if M.digest(raw)!=member['input_sha256']:raise ValueError('input differs')
        m=M.mmd.MMD.load(str(path),sid);sk=M.mmd.exe().skeleton[sid]
        if member.get('skeleton_sha256') and M.skeleton_digest(sk)!=member['skeleton_sha256']:raise ValueError('native rig differs from reviewed recipe')
        native,nloop,nevents=M.animsheet.slot_frames(m,len(sk),cfg['source_slot'])
        if nloop!=0:raise ValueError('requires full native loop')
        continuous=()
        if member.get('native_continuous_rotation_contract',False):
            continuous=motionloopcontracts.load(sid,m,sk).get(cfg['source_slot'],())
            if not continuous or any(b not in member['bones'] for b,c in continuous):raise ValueError('reviewed native rotation contract must belong to selected bones')
        old={s:m.anims.anims[i].build() for s,i in enumerate(m.anims.table) if i is not None};mesh=m.tmd.build();proof=[]
        for action in member['actions']:
            slot=action['slot']
            require_field_action(slot,cfg['source_slot'],action.get('condition_slot_review_basis'))
            field,loop,events=M.animsheet.slot_frames(m,len(sk),slot)
            if loop!=0:raise ValueError('field must loop from start')
            native_cycles=action.get('native_repeats',member.get('native_repeats',1))
            translation_roots=member.get('native_translation_roots',())
            if translation_roots and not member.get('native_translation_review_basis'):raise ValueError('native support translation requires explicit review')
            source,source_events=repeat_native(native,nevents,[*member['bones'],*translation_roots],native_cycles)
            scale_proof=None
            if member.get('field_world_support_scale_tolerance',0):
                field,source,scale_proof=normalize_field_world_support(m,sk,field,source,member.get('field_world_orientation_roots',()),member['field_world_support_scale_tolerance'],member.get('field_world_support_scale_review_basis'),member.get('static_field_body'))
            anchors={int(b):anchor for b,anchor in member.get('native_attachment_anchors',{}).items()}
            poses,detail=layer(field,source,member['bones'],action['repeats'],member['maximum_retime_fraction'],sk,member.get('native_world_orientation_roots',()),member.get('allow_uniform_world_orientation_ancestors',False),member.get('field_world_orientation_roots',()),anchors,member.get('static_field_body'),translation_roots)
            if member.get('static_field_body'):detail['static_field_body']=member['static_field_body']
            if member.get('close_equivalent_field_rotations',False):
                if not member.get('equivalent_endpoint_review_basis') or not member.get('field_world_orientation_roots'):raise ValueError('equivalent endpoint closure requires reviewed field roots')
                detail['equivalent_field_endpoint_closures']=close_equivalent_field_rotations(poses,member['field_world_orientation_roots'])
            if scale_proof:detail['field_world_support_scale_normalization']=scale_proof
            detail.update(original_native_period_ticks=len(native)-1,native_cycles=native_cycles)
            if slot in [1,18]:detail['condition_slot_review_basis']=action['condition_slot_review_basis']
            repeated,event_proof=combine_events(events,source_events,len(field)-1,len(source)-1,action['repeats'],member.get('event_policy','field'),member.get('maximum_texture_event_shift_ticks',1))
            detail.update(event_proof)
            animation=M.mmd.encode_anim(poses,len(sk),loop_sample=0,events=repeated,tol=0,repeats=False)
            m.anims.table[slot]=len(m.anims.anims);m.anims.anims.append(animation)
            proof.append((slot,poses,repeated,detail))
        used=sorted({i for i in m.anims.table if i is not None});remap={i:j for j,i in enumerate(used)};m.anims.anims=[m.anims.anims[i] for i in used];m.anims.table=[remap.get(i) for i in m.anims.table]
        if member.get('share_identical_streams',False):m.anims.anims,m.anims.table=share_identical_streams(m.anims.anims,m.anims.table)
        data=m.build();parsed=M.mmd.MMD.parse(data,len(sk));slots={x[0] for x in proof}
        if parsed.tmd.build()!=mesh or any(parsed.anims.anims[parsed.anims.table[s]].build()!=v for s,v in old.items() if s not in slots):raise ValueError('protected data changed')
        actions=[]
        for slot,expected,events,detail in proof:
            actual,loop,decoded_events=M.animsheet.slot_frames(parsed,len(sk),slot)
            if loop!=0 or len(actual)!=len(expected):raise ValueError('serialized cadence differs')
            error=max(abs(v-w) for a,b in zip(actual,expected) for x,y in zip(a,b) for v,w in zip(x,y))
            if error>1:raise ValueError('serialized channel drift')
            event_signature=lambda es:[(t,k,{a:v for a,v in p.items() if a not in ('frame','op')}) for t,k,p in es]
            if event_signature(events)!=event_signature(decoded_events):raise ValueError('field events changed')
            audit=motionloops.audit_animation(parsed,sk,slot,cycles=8,continuous_channels=continuous)
            if audit['status']!='stable':raise ValueError('combined loop drifts')
            if continuous:
                player=M.mmd.AnimPlayer(parsed.anims.anims[parsed.anims.table[slot]],len(sk),slot)
                period=len(expected)-1;baseline=[]
                winding={(b,c):expected[-1][b][c]-expected[0][b][c] for b,c in continuous}
                for tick in range(period*9):
                    if not player.tick():raise ValueError('continuous rotation playback stopped')
                    cycle,phase=divmod(tick,period)
                    if cycle==0:baseline.append(copy.deepcopy(player.pose));continue
                    if any((player.pose[b][c]-baseline[phase][b][c]-cycle*delta)%4096 for (b,c),delta in winding.items()):
                        raise ValueError('continuous rotation differs from native winding per cycle')
                audit.update(declared_native_continuous_channels=sorted(continuous),native_rotation_winding_per_cycle=[dict(bone=b,channel=c,delta=delta) for (b,c),delta in winding.items()],continuous_rotation_checked_every_phase_of_8_cycles=True,whole_pose_is_periodic=False)
            actions.append(dict(slot=slot,**detail,serialized_max_channel_error=error,loops=audit))
        storage=motionstorage.require(data,len(sk));dest=out/f'{sid}-cycle-layer.MMD';dest.write_bytes(data)
        results.append(dict(species=sid,output=str(dest),output_sha256=M.digest(data),actions=actions,storage=storage,mesh_and_unselected_clips_exact=True,production_approved=False))
    (out/'report.json').write_text(json.dumps(dict(recipe_sha256=M.digest(recipe.read_bytes()),generator_sha256=M.digest(Path(__file__).read_bytes()),results=results,production_approved=False),indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('recipe',type=Path);p.add_argument('out',type=Path);a=p.parse_args();run(a.recipe,a.out)
