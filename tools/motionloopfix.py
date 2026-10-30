#!/usr/bin/env python3
"""Close imported delta-animation loops locally, preserving duration and events.

Only a short closing interval changes. Generated MMDs remain local assets.
"""
import argparse
import copy
import json
import math
from pathlib import Path
import motionlab as M
import motionloops as L


def repair_animation(mod,skel,slot,window=3,continuous_channels=()):
    before=L.audit_animation(mod,skel,slot,continuous_channels=continuous_channels)
    if before['status']!='drifting':return None,dict(before=before,changed=False)
    original=mod.anims.anims[mod.anims.table[slot]]
    starts=[i for i in original.instrs if i['op']=='loop_start']
    ends=[i for i in original.instrs if i['op']=='loop_end']
    if len(starts)!=1 or starts[0]['count']!=255 or len(ends)!=1:
        raise ValueError('only simple infinite loops are supported')
    frames,start,events=M.animsheet.slot_frames(mod,len(skel),slot,max_ticks=1200)
    span=min(window,max(1,before['period_ticks']//4))
    end_frame=ends[0]['frame'];key_frame=end_frame-span
    if end_frame!=original.frame_count:raise ValueError('loop must end at the stream boundary')
    first,last=frames[start],frames[-1];anchor=frames[-1-span]
    corrections={}
    for bone in range(len(skel)):
        for channel in range(9):
            if (bone,channel) in continuous_channels:continue
            if bone==0 and channel>=6:continue
            target=first[bone][channel]
            if 3<=channel<6:target+=4096*round((last[bone][channel]-target)/4096)
            if target!=last[bone][channel]:corrections[bone,channel]=round(target-anchor[bone][channel])
    if not corrections:raise ValueError('physical drift has no supported channel correction')
    reset={(b['bone'],M.mmd.CHANNELS.index(name)) for i in original.instrs
           if i['op']=='key' and i['frame']==start+1 for b in i['bones'] for name in b['vals']}
    missing=set(corrections)-reset
    if missing:
        player=M.mmd.AnimPlayer(original,len(skel),slot)
        for _ in range(start+1):player.tick()
        if any(player.mom[b][channel][0] or player.mom[b][channel][1] for b,channel in missing):
            raise ValueError('nonzero intro momentum requires a separate reset treatment')
    repaired=copy.deepcopy(original)
    for instruction in repaired.instrs:
        if instruction['op']=='key' and key_frame<instruction['frame']<end_frame:
            for bone in instruction['bones']:
                bone['vals']={name:value for name,value in bone['vals'].items()
                              if (bone['bone'],M.mmd.CHANNELS.index(name)) not in corrections}
            instruction['bones']=[b for b in instruction['bones'] if b['vals']]
            # Keep empty keyframes: removing one could expose a texture opcode
            # to the engine's loop-start pre-check.
    grouped={}
    for (bone,channel),value in corrections.items():grouped.setdefault(bone,{})[M.mmd.CHANNELS[channel]]=value
    closing=dict(op='key',frame=key_frame,bones=[dict(bone=b,div=span,vals=v) for b,v in sorted(grouped.items())])
    index=next(i for i,ins in enumerate(repaired.instrs) if ins['op']=='end' or ins.get('frame',0)>key_frame)
    repaired.instrs.insert(index,closing)
    if missing:
        zero={}
        for bone,channel in sorted(missing):zero.setdefault(bone,{})[M.mmd.CHANNELS[channel]]=0
        reset_key=dict(op='key',frame=start+1,bones=[dict(bone=b,div=1,vals=v) for b,v in zero.items()])
        index=next(i for i,ins in enumerate(repaired.instrs) if ins['op']=='end' or ins.get('frame',0)>start+1)
        repaired.instrs.insert(index,reset_key)
    shadow=copy.copy(mod);shadow.anims=copy.copy(mod.anims);shadow.anims.anims=list(mod.anims.anims)
    shadow.anims.anims[mod.anims.table[slot]]=repaired
    after=L.audit_animation(shadow,skel,slot,continuous_channels=continuous_channels)
    if after['status']!='stable':raise ValueError(f'closure still drifts: {after}')
    decoded,new_start,new_events=M.animsheet.slot_frames(shadow,len(skel),slot,max_ticks=1200)
    if len(decoded)!=len(frames) or new_start!=start:raise ValueError('duration or loop phase changed')
    if events!=new_events:raise ValueError('animation events changed')
    for tick,(old,new) in enumerate(zip(frames,decoded)):
        for bone in range(len(skel)):
            for channel in range(9):
                if (bone,channel) not in corrections or tick<=len(frames)-1-span:
                    if abs(old[bone][channel]-new[bone][channel])>1e-7:
                        raise ValueError(f'untouched sample changed: {tick}/{bone}/{channel}')
    affected={b for b,j in corrections if 3<=j<6};rates={};flags=[]
    for b in affected:
        maxima=[]
        for poses in [frames,decoded]:
            rotations=[M.R.rot_of(p[b]) for p in poses]
            maxima.append(max(math.degrees(M.R.axis_angle(M.R.m3mul(z,M.R.m3t(a)))[1]) for a,z in zip(rotations,rotations[1:])))
        rates[b]=dict(before=maxima[0],after=maxima[1])
        if maxima[1]>maxima[0]*1.25+5:flags.append(b)
    if flags:
        if window!=1:return repair_animation(mod,skel,slot,window=1,continuous_channels=continuous_channels)
        raise ValueError(f'closure exceeds original angular envelope for bones {flags}; needs behavior-specific repair')
    return repaired,dict(changed=True,before=before,after=after,closing_ticks=span,
                         corrected_channels=len(corrections),events_unchanged=True,duration_unchanged=True,
                         zero_momentum_resets=len(missing),
                         angular_rates=rates,declared_continuous_channels=sorted(continuous_channels),
                         root_travel_unchanged=True,bytes_delta=len(repaired.build())-len(original.build()))


def repair_selected_slots(mod,skel,slots,window=3):
    """Repair explicit slot streams while protecting every unselected alias."""
    if not slots or any(type(s) is not int or not 0<=s<len(mod.anims.table) for s in slots) or len(set(slots))!=len(slots):
        raise ValueError('explicit unique populated slots required')
    if type(window) is not int or not 1<=window<=8:raise ValueError('closing window must be1..8 ticks')
    selected=set(slots)
    indices={mod.anims.table[s] for s in slots}
    if None in indices:raise ValueError('selected slot is empty')
    if any(i in indices for s,i in enumerate(mod.anims.table) if s not in selected):
        raise ValueError('selected stream aliases an unselected slot')
    result=copy.deepcopy(mod);reports={}
    for index in sorted(indices):
        slot=next(s for s in slots if mod.anims.table[s]==index)
        animation,report=repair_animation(result,skel,slot,window=window)
        if animation is None:raise ValueError('selected slot does not require closure')
        result.anims.anims[index]=animation;reports[str(slot)]=report
    return result,reports


def repair_pinned_recipe(recipe,source,out):
    """Rebuild an asset-free, hash-pinned closure recipe into a fresh local file."""
    import coldsplit
    if out.exists() or out.with_suffix('.report.json').exists():raise ValueError('choose a fresh output file')
    cfg=json.loads(recipe.read_text())
    if cfg.get('schema')!=1 or cfg.get('operation')!='motionloopfix.repair_animation':raise ValueError('unsupported closure recipe')
    data=source.read_bytes()
    if M.digest(data)!=cfg['input_sha256']:raise ValueError('source hash differs from recipe')
    sid=cfg['species'];sk=M.mmd.exe().skeleton[sid]
    if M.skeleton_digest(sk)!=cfg['skeleton_sha256']:raise ValueError('skeleton hash differs from recipe')
    original=M.mmd.MMD.load(str(source),sid)
    result,reports=repair_selected_slots(original,sk,cfg['slots'],cfg['window'])
    rebuilt=result.build();parsed=M.mmd.MMD.parse(rebuilt,len(sk))
    if M.digest(rebuilt)!=cfg['expected_output_sha256']:raise ValueError('rebuilt hash differs from recipe')
    if parsed.tmd.build()!=original.tmd.build() or parsed.anims.table!=original.anims.table:raise ValueError('mesh or slot table changed')
    selected=set(cfg['slots'])
    for slot,index in enumerate(original.anims.table):
        if index is not None and slot not in selected and original.anims.anims[index].build()!=parsed.anims.anims[index].build():
            raise ValueError('unselected animation changed')
    cycles=cfg['verification']['replay_cycles']
    if type(cycles) is not int or not 8<=cycles<=32:raise ValueError('verification requires8..32 repeats')
    audits={str(s):L.audit_animation(parsed,sk,s,cycles=cycles) for s in cfg['slots']}
    if any(a['status']!='stable' for a in audits.values()):raise ValueError('serialized repaired clip drifts')
    resident=len(coldsplit.split(rebuilt,len(sk))[0])
    if resident>min(cfg['verification']['resident_limit'],0x18800):raise ValueError('resident storage exceeds limit')
    report=dict(species=sid,input_sha256=M.digest(data),output_sha256=M.digest(rebuilt),recipe_sha256=M.digest(recipe.read_bytes()),
                generator_sha256=M.digest(Path(__file__).read_bytes()),repairs=reports,serialized_audits=audits,
                resident_bytes=resident,mesh_and_unselected_slots_exact=True,selected=False,production_approved=False,
                runtime_tested=False,status='reproduced_unselected_closure_candidate')
    out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(rebuilt)
    out.with_suffix('.report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(output=str(out),output_sha256=report['output_sha256'],resident_bytes=resident)),flush=True)
    return report


def repair_model(sid,source,out):
    import coldsplit
    if source.resolve()==out.resolve():raise ValueError('choose a separate output; source assets must remain unchanged')
    data=source.read_bytes();mod=M.mmd.MMD.load(str(source),sid);skel=M.mmd.exe().skeleton[sid]
    import motionloopcontracts
    continuous=motionloopcontracts.load(sid,mod,skel)
    continuous_by_stream={mod.anims.table[s]:channels for s,channels in continuous.items()}
    before_mesh=mod.tmd.build();streams={};errors=[]
    for slot,index in enumerate(mod.anims.table):
        if index is None or index in streams:continue
        try:
            animation,report=repair_animation(mod,skel,slot,continuous_channels=continuous_by_stream.get(index,()))
            if animation is not None:mod.anims.anims[index]=animation
            streams[index]=dict(slot=slot,**report)
        except Exception as error:
            errors.append(dict(slot=slot,stream=index,error=str(error)));streams[index]=dict(changed=False,error=str(error))
    result=mod.build();resident=len(coldsplit.split(result,len(skel))[0])
    if mod.tmd.build()!=before_mesh:raise ValueError('mesh changed')
    if M.mmd.MMD.parse(result,len(skel)).build()!=result:raise ValueError('MMD roundtrip failed')
    report=dict(species=sid,input_sha256=M.digest(data),output_sha256=M.digest(result),
        skeleton_sha256=M.skeleton_digest(skel),generator_sha256=M.digest(Path(__file__).read_bytes()),
        input_model=str(source),dependencies_sha256={name:M.digest((M.ROOT/name).read_bytes()) for name in
            ['tools/motionloops.py','tools/motionloopcontracts.py','content/motion-loop-contracts.json']},
        resident_bytes=resident,fits=resident<=0x18800,errors=errors,streams=streams,
        changed_streams=sum(s.get('changed',False) for s in streams.values()),visual_status='requires_review')
    out.parent.mkdir(parents=True,exist_ok=True)
    out.with_suffix('.report.json').write_text(json.dumps(report,indent=2)+'\n')
    if errors or not report['fits']:raise ValueError(f'repair rejected; inspect {out.with_suffix(".report.json")}')
    out.write_bytes(result)
    print(json.dumps({k:report[k] for k in ['species','changed_streams','resident_bytes','fits']}),flush=True)
    return report


def repair_catalog(catalog,out):
    records=json.loads(catalog.read_text())['species'];results=[]
    out.mkdir(parents=True,exist_ok=True)
    for record in records:
        sid=record['species'];source=Path(record['model'])
        if sid<180:continue
        if not source.is_absolute():source=M.ROOT/source
        try:
            if M.digest(source.read_bytes())!=record['input_sha256']:raise ValueError('catalogue source hash changed')
            if M.skeleton_digest(M.mmd.exe().skeleton[sid])!=record['skeleton_sha256']:raise ValueError('catalogue rig hash changed')
            report=repair_model(sid,source,out/f'{sid}-{record["name"]}.MMD')
            results.append(dict(species=sid,status='technical_pass',changed_streams=report['changed_streams'],
                                resident_bytes=report['resident_bytes'],output_sha256=report['output_sha256']))
        except Exception as error:
            results.append(dict(species=sid,status='rejected',error=str(error)))
            print(sid,error,flush=True)
        (out/'catalog-results.json').write_text(json.dumps(results,indent=2)+'\n')
    return results


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);commands=p.add_subparsers(dest='command',required=True)
    model=commands.add_parser('model');model.add_argument('species',type=int)
    model.add_argument('source',type=Path);model.add_argument('out',type=Path)
    batch=commands.add_parser('catalog');batch.add_argument('catalog',type=Path);batch.add_argument('out',type=Path)
    pinned=commands.add_parser('recipe');pinned.add_argument('recipe',type=Path);pinned.add_argument('source',type=Path);pinned.add_argument('out',type=Path)
    a=p.parse_args()
    if a.command=='model':repair_model(a.species,a.source,a.out)
    elif a.command=='recipe':repair_pinned_recipe(a.recipe,a.source,a.out)
    else:
        results=repair_catalog(a.catalog,a.out)
        if any(r['status']=='rejected' for r in results):raise SystemExit(1)
