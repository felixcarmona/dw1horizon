"""Restore Phantomon's native cloak/scythe clock while retaining travel pace.

The existing idle contains the complete104-tick levitation performance.
Movement retargets compressed it into24/28/20ticks. Use the original idle
program for those three field states, retaining the distinct30-tick poor
idle, private33, care and battle. Keep each existing sound cue at the same
normalized gesture phase, with its original bank/note and sample pitch.
"""
import copy
import hashlib
import mmd
import animsheet
import motioncyclelayer
import motionstorage
from tools.models.field_animations.gliding import _forward
from motiondiscidentity import changed_programs

SOURCE = '0230bae9eb490d788e110dece9e742fcea8569cdaabbef6b74d05b8bea6d43fc'
PARENTS = [-1,0,1,1,3,4,1,6,7,1,9,10,1,11,13,14,15,8,17,18]


def _parse(data, sk):
    mmd.exe().skeleton[229] = sk
    mmd.exe().bone_count[229] = len(sk)
    model = mmd.MMD.parse(data,len(sk))
    model.type = 229
    return model


def build(data, sk):
    if (hashlib.sha256(data).hexdigest()!=SOURCE or [b[1] for b in sk]!=PARENTS
            or [b[0] for b in sk]!=list(range(-1,19))):
        raise ValueError('Phantomon needs its reviewed20-bone source')
    old = _parse(data,sk)
    new = copy.deepcopy(old)
    native = old.anims.anims[old.anims.table[0]]
    fs,loop,events = animsheet.slot_frames(old,20,0)
    assert len(fs)==105 and loop==0
    assert fs==animsheet.slot_frames(old,20,33)[0]
    assert not [i for i in native.instrs if i['op']=='sound']
    checks = []
    for slot,source_period in [(2,24),(3,28),(4,20)]:
        original = old.anims.anims[old.anims.table[slot]]
        before,_,_ = animsheet.slot_frames(old,20,slot)
        assert len(before)==source_period+1 and before[-1][0][:8]==before[0][0][:8]
        original_distance = round(before[-1][0][8]-before[0][0][8])
        period = 104
        distance = round(original_distance*period/source_period)
        selected = _forward(native,distance,period)
        sounds = []
        for cue in original.instrs:
            if cue['op']!='sound': continue
            mapped = dict(cue,frame=1+round((cue['frame']-1)*period/source_period))
            sounds.append(mapped)
            at = next((j for j,i in enumerate(selected.instrs) if i.get('frame',-1)>mapped['frame']),len(selected.instrs)-1)
            selected.instrs.insert(at,mapped)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(selected)
        checks.append(dict(slot=slot,source_period=source_period,period=period,source_loop_distance=original_distance,source_units_per_tick=original_distance/source_period,loop_distance=distance,selected_units_per_tick=distance/period,sound_cues=sounds))
    for animation in new.anims.anims: animation.tail=b''
    new.anims.anims,new.anims.table=motioncyclelayer.share_identical_streams(new.anims.anims,new.anims.table)
    result = new.build()
    actual = _parse(result,sk)
    assert changed_programs(old,actual)==[2,3,4]
    assert old.tmd.build()==actual.tmd.build()
    for row in checks:
        slot,period,distance = row['slot'],row['period'],row['loop_distance']
        decoded,l,ev = animsheet.slot_frames(actual,20,slot)
        assert l==loop and len(decoded)==len(fs)
        assert [f[1:] for f in decoded]==[f[1:] for f in fs]
        source_player=mmd.AnimPlayer(native,20,0)
        selected_player=mmd.AnimPlayer(actual.anims.anims[actual.anims.table[slot]],20,slot)
        cycle=[];steps=[]
        for t in range(period*9+1):
            assert source_player.tick() and selected_player.tick()
            assert selected_player.pose[1:]==source_player.pose[1:]
            assert selected_player.root[:2]==[0,0]
            if t<period: cycle.append(copy.deepcopy(selected_player.pose[1:]))
            else: assert selected_player.pose[1:]==cycle[t%period]
            steps.append(selected_player.base[2])
        assert selected_player.root[2]==distance*9
        assert [sum(steps[1+i*period:1+(i+1)*period]) for i in range(9)]==[distance]*9
        assert max(steps[1:])-min(steps[1:])<=1
        encoded=actual.anims.anims[actual.anims.table[slot]]
        assert [i for i in encoded.instrs if i['op']=='sound']==row['sound_cues']
        assert [i for i in encoded.instrs if i['op'] not in ('key','sound')]==[i for i in native.instrs if i['op'] not in ('key','sound')]
        row.update(full_native_SRT_exact_nine_cycles=True,pose_repeat_exact_nine_cycles=True,loop_travel_exact_nine_cycles=True,maximum_one_unit_integer_step_variation=True,no_dynamic_stretch=True,original_mesh_scales_joint_translations_exact=True)
    storage = motionstorage.audit(result,20)
    assert storage['fits'],storage
    return result,dict(species=229,source_sha256=SOURCE,output_sha256=hashlib.sha256(result).hexdigest(),changed_slots=[2,3,4],preserved_slots=[0,1,33,17,18],mesh_skeleton_hierarchy_other_programs_exact=True,native_period=104,poor_idle_period=30,checks=checks,storage=storage)
