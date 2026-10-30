"""Selected field curves and exact same-frame key-block packing.

Partitioning tries correlated channel groups without changing untouched source
channels. Coalescing uses an exact common divisor, guarded by signed 16-bit
limits. Callers must verify decoded pose/root equivalence across loops.
"""
import copy
import math
import mmd

def _partitions(items):
    if not items:
        yield []
        return
    first,*rest=items
    for partition in _partitions(rest):
        yield [(first,)]+partition
        for i,group in enumerate(partition):
            yield partition[:i]+[(first,)+group]+partition[i+1:]

def replace_channels(original,samples,loop,n,channels,*,tolerance=1):
    minimum_channel = 0 if original.has_scale else 3
    if (loop != 0 or
            any(not 0 < b < n or not minimum_channel <= c < 9 for b,c in channels)):
        raise ValueError('Channel packing requires loop zero and legal nonroot channels for the stream')
    result=copy.deepcopy(original)
    for b,c in channels:result.pose[b-1][c if result.has_scale else c-3]=samples[0][b][c]
    for ins in result.instrs:
        if ins['op']=='key':
            for g in ins['bones']:g['vals']={k:v for k,v in g['vals'].items()if(g['bone'],mmd.CHANNELS.index(k))not in channels}
            ins['bones']=[g for g in ins['bones']if g['vals']]
    byframe={}
    for bone in range(1,n):
        moving=[c for b,c in sorted(channels)if b==bone and any(f[b][c]!=samples[0][b][c]for f in samples)]
        if not moving:continue
        assert len(moving)<=5,(bone,moving)
        candidates=[]
        for parts in _partitions(moving):
            blocks={}
            for part in parts:
                vs=[[f[bone][c]for f in samples]for c in part]
                for key,vals in mmd._bone_keys(list(part),vs,{loop},tolerance).items():blocks.setdefault(key,{}).update(vals)
            candidates.append(blocks)
        blocks=min(candidates,key=lambda d:sum(4+2*len(vals)for vals in d.values()))
        for (sample,div),values in blocks.items():
            byframe.setdefault(sample+1,[]).append(dict(bone=bone,div=div,vals={mmd.CHANNELS[c]:v for c,v in values.items()}))
    for frame,bones in sorted(byframe.items()):
        old=next((i for i in result.instrs if i['op']=='key'and i['frame']==frame),None)
        if old is not None:old['bones'].extend(bones);continue
        at=len(result.instrs)-1
        for i,ins in enumerate(result.instrs):
            f=ins.get('frame')
            if ins['op']=='loop_start':f=next((x.get('frame')for x in result.instrs[i+1:]if x.get('frame')is not None),None)
            if f is not None and f>frame:at=i;break
        result.instrs.insert(at,dict(op='key',frame=frame,bones=bones))
    return result



def coalesce(animation):
    result=copy.deepcopy(animation);merged=0
    for ins in result.instrs:
        if ins['op']!='key':continue
        groups=ins['bones']
        # Reducing a common fraction preserves the signed per-tick integer sequence.
        for g in groups:
            if g['bone']==0 or g['div']<=0:continue
            factor=math.gcd(g['div'],*(abs(v)for v in g['vals'].values()))
            if factor>1:
                g['div']//=factor;g['vals']={c:v//factor for c,v in g['vals'].items()}
        again=True
        while again:
            again=False
            for i,a in enumerate(groups):
                if a['bone']==0 or a['div']<=0:continue
                for j in range(i+1,len(groups)):
                    b=groups[j]
                    if a['bone']!=b['bone']or b['div']<=0 or set(a['vals'])&set(b['vals']):continue
                    divisor=math.lcm(a['div'],b['div'])
                    if divisor>32767:continue
                    vals={c:v*(divisor//g['div'])for g in [a,b]for c,v in g['vals'].items()}
                    if not all(-32768<=v<=32767 for v in vals.values()):continue
                    a.update(div=divisor,vals=vals);groups.pop(j);merged+=1;again=True;break
                if again:break
    return result,merged
