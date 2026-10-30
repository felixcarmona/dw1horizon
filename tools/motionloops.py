#!/usr/bin/env python3
"""Audit actual repeated playback for joint/scale drift; never approve animation quality."""
import argparse
import copy
import json
import math
from pathlib import Path
import motionlab as M


def audit_animation(mod,skel,slot,max_ticks=1200,cycles=3,continuous_channels=()):
    frames,start,_=M.animsheet.slot_frames(mod,len(skel),slot,max_ticks=max_ticks)
    if start is None:
        return dict(status='bounded_preview' if len(frames)==max_ticks else 'finite',ticks=len(frames))
    period=len(frames)-1-start
    if period<=0:raise ValueError('invalid loop period')
    player=M.mmd.AnimPlayer(mod.anims.anims[mod.anims.table[slot]],len(skel),slot)
    baseline=[]
    deltas=[dict(translation=0,scale=0,rotation_degrees=0.) for _ in range(cycles)]
    for tick in range(start+period*(cycles+1)):
        if not player.tick():raise ValueError('loop stopped during repeated audit')
        if tick<start:continue
        cycle,phase=divmod(tick-start,period)
        if cycle==0:
            baseline.append(copy.deepcopy(player.pose));continue
        first=baseline[phase];pose=player.pose
        translation=max(abs(pose[b][j]-first[b][j]) for b in range(1,len(skel)) for j in range(6,9))
        scale=max(abs(pose[b][j]-first[b][j]) for b in range(len(skel)) for j in range(3))
        changed=[b for b in range(len(skel)) if any((pose[b][j]-first[b][j])%4096 for j in range(3,6) if (b,j) not in continuous_channels)]
        angular=0
        for b in changed:
            current=list(pose[b])
            for j in range(3,6):
                if (b,j) in continuous_channels:current[j]=first[b][j]
            angular=max(angular,math.degrees(M.R.axis_angle(M.R.m3mul(M.R.rot_of(current),M.R.m3t(M.R.rot_of(first[b]))))[1]))
        delta=deltas[cycle-1]
        for key,value in [('translation',translation),('scale',scale),('rotation_degrees',angular)]:delta[key]=max(delta[key],value)
    drifting=any(d['translation'] or d['scale'] or d['rotation_degrees']>1e-4 for d in deltas)
    return dict(status='drifting' if drifting else 'stable',loop_sample=start,period_ticks=period,
                comparison_coverage='every_sample_of_three_repetitions' if cycles==3 else f'every_sample_of_{cycles}_repetitions',cycles=deltas)


def audit_catalog(catalog,out,all_slots=False,contracts=None):
    import species
    records=json.loads(catalog.read_text())['species'];results=[]
    references=[]
    for sid in [3,17,22,34,45]:
        references.append(dict(species=sid,name=M.mmd.exe().names[sid],model=str(species.originals().model_path(sid)),is_original_reference=True))
    out.mkdir(parents=True,exist_ok=True)
    for record in references+records:
        sid=record['species'];model=Path(record['model'])
        if not model.is_absolute():model=M.ROOT/model
        result=dict(species=sid,name=record['name'],reference=record.get('is_original_reference',False),
                    input_sha256=M.digest(model.read_bytes()),slots=[])
        try:
            mod=M.mmd.MMD.load(str(model),sid);skel=M.mmd.exe().skeleton[sid];cache={}
            import motionloopcontracts
            continuous=motionloopcontracts.load(sid,mod,skel,contracts) if contracts else {}
            continuous_by_stream={mod.anims.table[s]:channels for s,channels in continuous.items()}
            result['skeleton_sha256']=M.skeleton_digest(skel)
            slots=range(len(mod.anims.table)) if all_slots else [33]
            for slot in slots:
                if slot>=len(mod.anims.table) or mod.anims.table[slot] is None:continue
                stream=mod.anims.table[slot]
                # Root-X handling differs in battle movement, but accumulated
                # entity translation is intentionally excluded from joint drift.
                if stream not in cache:
                    cache[stream]=audit_animation(mod,skel,slot,continuous_channels=continuous_by_stream.get(stream,()))
                    if stream in continuous_by_stream:cache[stream]['declared_continuous_channels']=sorted(continuous_by_stream[stream])
                result['slots'].append(dict(slot=slot,stream=stream,**cache[stream]))
        except Exception as error:
            result['error']=f'{type(error).__name__}: {error}'
        results.append(result)
        (out/f'{sid}-loops.json').write_text(json.dumps(result,indent=2)+'\n')
        print(sid,record['name'],{s:sum(x['status']==s for x in result['slots']) for s in ['stable','drifting','finite','bounded_preview']},flush=True)
    from collections import Counter
    counts=dict(Counter(slot['status'] for r in results if not r['reference'] for slot in r['slots']))
    report=dict(imported_slot_counts=counts,visual_approvals=0,species=results)
    (out/'loops.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(counts),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('catalog',type=Path);p.add_argument('out',type=Path)
    p.add_argument('--all-slots',action='store_true')
    p.add_argument('--contracts',type=Path)
    a=p.parse_args();audit_catalog(a.catalog,a.out,a.all_slots,a.contracts)
