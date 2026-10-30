"""Authored semantic exceptions to pose-periodicity, bound to mesh and rig hashes."""
import json
from pathlib import Path
import motionlab as M


def load(sid,mod,skel,path=None):
    path=Path(path) if path else M.ROOT/'content/motion-loop-contracts.json'
    if not path.exists():return {}
    document=json.loads(path.read_text())
    if document.get('schema')!=1:raise ValueError('unknown loop contract schema')
    contract=document.get('species',{}).get(str(sid))
    if not contract:return {}
    if contract['mesh_sha256']!=M.digest(mod.tmd.build()) or contract['skeleton_sha256']!=M.skeleton_digest(skel):
        raise ValueError('loop contract mesh/rig identity changed; review the anatomy')
    result={}
    for slot,spec in contract['slots'].items():
        channels=set()
        for item in spec['continuous_rotations']:
            bone=item['bone'];channel=M.mmd.CHANNELS.index(item['channel'])
            if not 0<=bone<len(skel) or not 3<=channel<6 or not item.get('basis'):
                raise ValueError('continuous channels require a reviewed rotation part')
            channels.add((bone,channel))
        result[int(slot,0)]=channels
    return result


def verify_winding(player,frames,channels,cycles=8):
    """Check every phase against the declared per-loop angular advance."""
    period=len(frames)-1
    if period<1 or not channels:raise ValueError('continuous rotation requires a cycle and channels')
    winding={(b,c):frames[-1][b][c]-frames[0][b][c] for b,c in channels}
    baseline=[]
    import copy
    for tick in range(period*(cycles+1)):
        if not player.tick():raise ValueError('continuous rotation playback stopped')
        cycle,phase=divmod(tick,period)
        if cycle==0:baseline.append(copy.deepcopy(player.pose));continue
        if any((player.pose[b][c]-baseline[phase][b][c]-cycle*delta)%4096 for (b,c),delta in winding.items()):
            raise ValueError('continuous rotation differs from declared winding per cycle')
    return [dict(bone=b,channel=c,delta=d) for (b,c),d in sorted(winding.items())]


def audit_native_rotation(sid,mod,skel,slot,source_slot,cycles=8):
    """Opt-in audit of a copied native rotor, retaining strict body checks."""
    import motionloops
    if type(source_slot) is not int:raise ValueError('explicit native contract source slot required')
    channels=load(sid,mod,skel).get(source_slot,())
    if not channels:raise ValueError('no mesh/rig-bound native rotation contract')
    native,start,_=M.animsheet.slot_frames(mod,len(skel),source_slot)
    frames,loop,_=M.animsheet.slot_frames(mod,len(skel),slot)
    if start!=0 or loop!=0:raise ValueError('full native/field loop required')
    if any((frames[-1][b][c]-frames[0][b][c]-native[-1][b][c]+native[0][b][c])%4096 for b,c in channels):
        raise ValueError('field rotor winding differs from native source cycle')
    audit=motionloops.audit_animation(mod,skel,slot,cycles=cycles,continuous_channels=channels)
    if audit['status']!='stable':raise ValueError('noncontinuous body channels drift')
    player=M.mmd.AnimPlayer(mod.anims.anims[mod.anims.table[slot]],len(skel),slot)
    winding=verify_winding(player,frames,channels,cycles)
    audit.update(native_contract_source_slot=source_slot,declared_native_continuous_channels=sorted(channels),native_rotation_winding_per_cycle=winding,continuous_rotation_checked_every_phase=True,whole_pose_is_periodic=False)
    return audit
