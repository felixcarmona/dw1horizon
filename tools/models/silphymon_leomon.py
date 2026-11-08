#!/usr/bin/env python3
"""Fit Leomon's feline acting to the already resized Silphymon model.

Offline authoring only. Keep technique clocks/effects and the native dash
trajectory while replacing the bird/insect body language with Leomon's.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet
import mmd
import motioncyclelayer
import motionstorage
import motionsecondary
import retarget as R
import species
from motiontailspace import interpolate_pose
from tools.models.field_animations import native_polish
from tools.models.field_animations.channels import replace_channels

SOURCE = 'ac3609d32e82ec750182619b8be45b4191bb3df0fe2c76a5691f95233887adcc'
DONOR = '390092e3b3471adc84645a512f8671b2b036413d72e09d046fc982355f1488c7'
OUTPUT = 'f9ccc558316989c5c8cb4d2b8167136890a7a8b2bb848ef353ab1b22d6891dcc'
MAP = {1: 11, 2: 2, 3: 3, 6: 5, 7: 6, 8: 7, 9: 8, 10: 9, 11: 10,
       12: 15, 13: 16, 14: 17, 15: 18, 16: 19, 17: 20, 18: 21, 19: 22, 20: 12}
FIELD = [0, 1, 2, 3, 4, 33, 34, 35, 36]
CARE = [5, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 40, 41, 42, 43, 44]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def author(data):
    if digest(data) != SOURCE:
        raise ValueError('requires the pinned 0.80 size revision')
    spec = json.loads((ROOT / 'content/species/226-silphymon.json').read_text())
    sk = spec['model']['skeleton']; nb = len(sk)
    mmd.exe().add_type(226, sk)
    donor_path = ROOT / 'extracted/CHDAT/MMD1/LEOM.MMD'
    if digest(donor_path.read_bytes()) != DONOR:
        raise ValueError('requires the pinned native Leomon')
    cfg = dict(donor=48, model=str(donor_path.relative_to(ROOT)), donor_sha256=DONOR,
               carrier=1, scale=1., map={str(k): v for k, v in MAP.items()},
               # Keep the reviewed crouch, loose guard and head/ear silhouette;
               # solve native foot paths using the original leg lengths.
               chains=[], feet=[14, 15, 18, 19],
               legs=[[12,13,14,15,17,18], [16,17,18,19,21,22]],
               keep_world=[3,8,11,15,19], rest_slot=0, slots=FIELD,
               mirror_free_arm=True, secondary=[4,5], ground_contact=True,
               native_bend=True, tolerance=12)
    field, report = native_polish.author(data, sk, 226, cfg)
    old = mmd.MMD.parse(data, nb); old.type = 226
    out = mmd.MMD.parse(field, nb); out.type = 226
    native = mmd.MMD.load(str(donor_path), 48)
    # The oversized boots need the native foot trajectory solved on their
    # actual limb lengths during the kick, just as during locomotion.
    kick_cfg=copy.deepcopy(cfg)
    kick_cfg.update(slots=[54],donor_slots={'54':47},mirror_free_arm=False,
                    retime={'54':{'ticks':26,'speed':0}})
    kick_data,_=native_polish.author(data,sk,226,kick_cfg)
    kick=mmd.MMD.parse(kick_data,nb);kick.type=226
    frames,_,_=animsheet.slot_frames(kick,nb,54)
    original,_,events=animsheet.slot_frames(old,nb,54)
    for p,q in zip(frames,original):p[0]=q[0]
    out.anims.table[54]=len(out.anims.anims)
    out.anims.anims.append(mmd.encode_anim(frames,nb,None,events,tol=4,repeats=False))
    rest = animsheet.slot_frames(out, nb, 0)[0][0]
    rest[0] = [4096]*3+[0]*6
    originals = species.originals()
    moves = species.techniques_from_json(spec['techniques'], 'Silphymon')
    checks = []
    for slot in CARE + list(range(46,60)):
        if slot==54:
            checks.append(dict(slot=54,donor_slot=47,ticks=26,leg_ik=True))
            continue
        attack = slot >= 46
        # Leomon has the exact physical, Static Elect and Megalo Spark clips.
        # Its projectile fist supplies the remaining Air casts and finisher.
        move = moves[slot-46] if attack else None
        native_slot = (46+originals.rec[48]['para']['moves'].index(move)
                       if attack and move in originals.rec[48]['para']['moves'] else 56 if attack else slot)
        transfer = R.transfer(native,48,native_slot,226,rest,
                              {t:(s,1.) for t,s in MAP.items()}, (1,1,1.), 1.)
        previous, loop, events = animsheet.slot_frames(old,nb,slot)
        count = len(previous) if attack else transfer['n']
        frames = []
        for tick in range(count):
            at = tick*(transfer['n']-1)/(count-1)
            left = min(int(at),transfer['n']-2); alpha = round((at-left)*4096)
            p = copy.deepcopy(rest)
            for bone, seq in transfer['rot'].items():
                if attack and move not in (44, 47) and 12 <= bone <= 19:
                    continue
                a, b = seq[left], seq[left+1]
                p[bone][3:6] = [round(x+((y-x+2048)%4096-2048)*alpha/4096) for x,y in zip(a,b)]
            if attack and move not in (44,47):
                # Silphymon's shorter, bent legs support a lower pelvis than
                # Leomon's. Keep that stance under standing strikes, carrying
                # the native pelvis turn into the chest instead of rolling
                # the support boots or lowering the hands below the floor.
                chest=R.world_rots(sk,p)[2]
                p[1][3:6]=rest[1][3:6]
                p[2][3:6]=[round(v) for v in mmd.matrix_euler(R.m3mul(R.m3t(R.world_rots(sk,p)[1]),chest),p[2][3:6])]
            for j in range(3):
                a,b=transfer['hips'][left][j],transfer['hips'][left+1][j]
                p[1][6+j] = round(rest[1][6+j]+a+(b-a)*alpha/4096)
            # Ears respond after the head, rather than duplicating its curve.
            lag = max(0, tick-2)
            head = frames[lag][3][3] if lag < len(frames) else rest[3][3]
            for ear, sign in ((4,1),(5,-1)):
                p[ear][3] += round(sign*(head-rest[3][3])*.12)
            p[0][6:9] = (previous[tick][0][6:9] if attack else
                             [round(transfer['root'][left][j]+(transfer['root'][left+1][j]-transfer['root'][left][j])*alpha/4096) for j in range(3)])
            # Whole-body collapse must touch the floor; standing attacks use
            # the support boot, including the native kick's one-foot stance.
            p0 = copy.deepcopy(p); p0[0] = [4096]*3+[0]*6
            mats=mmd.bone_matrices(out,p0)
            support = range(1,nb) if slot in (9,43,44) else (14,15,18,19)
            floor=max(sum(mats[b][1][j]*v[j] for j in range(3))+mats[b][1][3]
                      for b in support for v in out.tmd.obj_verts(sk[b][0]))
            p[1][7] -= round(floor)
            frames.append(p)
        target_loop = None if attack else transfer['loop']
        mmd.close_loop(frames,target_loop)
        if target_loop is not None:
            native_polish.cyclic_eulers(frames)
        if not attack:
            events=[e for e in transfer['events'] if e[1]=='sound']
        frames = [[[round(v) for v in bone] for bone in pose] for pose in frames]
        anim=mmd.encode_anim(frames,nb,target_loop,events,tol=12,repeats=False)
        if attack:
            # Entity motion controls the effect collision window. Copy its
            # integer program exactly, independently of the body curve fit.
            for ins in anim.instrs:
                if ins['op']=='key':
                    ins['bones']=[g for g in ins['bones'] if g['bone']!=0]
            for ins in old.anims.anims[old.anims.table[slot]].instrs:
                if ins['op']!='key': continue
                groups=[copy.deepcopy(g) for g in ins['bones'] if g['bone']==0]
                if not groups: continue
                block=next((k for k in anim.instrs if k['op']=='key' and k['frame']==ins['frame']),None)
                if block is None:
                    block=dict(op='key',frame=ins['frame'],bones=[])
                    at=next((i for i,k in enumerate(anim.instrs) if k.get('frame',100000)>ins['frame']),len(anim.instrs)-1)
                    anim.instrs.insert(at,block)
                block['bones'].extend(groups)
        out.anims.table[slot]=len(out.anims.anims); out.anims.anims.append(anim)
        checks.append(dict(slot=slot,donor_slot=native_slot,ticks=count-1))
    for anim in out.anims.anims:
        anim.tail=b''
    # Fit rotations first, then correct the encoded support at keys AND the
    # two intermediate display samples. Keep this one translation exact;
    # fitting it with angular tolerance can put a boot through the floor.
    for slot in FIELD + CARE + list(range(46,60)):
        frames,loop,_=animsheet.slot_frames(out,nb,slot)
        support=range(1,nb) if slot in (9,40,41,43,44,55) else (14,15,18,19)
        def bottom(p):
            p=copy.deepcopy(p);p[0]=[4096]*3+[0]*6
            mats=mmd.bone_matrices(out,p)
            return max(sum(mats[b][1][j]*v[j] for j in range(3))+mats[b][1][3]
                       for b in support for v in out.tmd.obj_verts(sk[b][0]))
        for p in frames:p[1][7]-=round(bottom(p))
        grounded=replace_channels(out.anims.anims[out.anims.table[slot]],frames,0,nb,{(1,7)},tolerance=0)
        out.anims.table[slot]=len(out.anims.anims);out.anims.anims.append(grounded)
        frames,loop,_=animsheet.slot_frames(out,nb,slot)
        if slot not in (9,40,41,43,44,55):
            # Long forearms and tail feathers need room in Leomon's deeper
            # crouches. Apply the smallest eased shoulder/tail turn, rather
            # than lifting the body and leaving the support boots in the air.
            adjusted=set()
            for bone,children,axis in [(6,(6,7,8),[0,0,1]),
                                       (9,(9,10,11),[0,0,1]),(20,(20,),[1,0,0])]:
                period=len(frames)-1 if loop is not None else len(frames)
                choices=[]
                for sign in (-1,1):
                    curve=[]
                    try:
                        def required(p):
                            p=copy.deepcopy(p);p[0]=[4096]*3+[0]*6
                            mats=mmd.bone_matrices(out,p)
                            origin=[mats[bone][i][3] for i in range(3)]
                            points=[[sum(mats[b][i][j]*v[j] for j in range(3))+mats[b][i][3] for i in range(3)]
                                    for b in children for v in out.tmd.obj_verts(sk[b][0])]
                            limit=170 if bone==20 else 85
                            rotation=motionsecondary.clearance_rotation(points,origin,axis,
                                         [-limit,0] if sign<0 else [0,limit],-18)
                            return R.axis_angle(rotation)[1]
                        curve=[required(p) for p in frames[:period]]
                        for i,(a,b) in enumerate(zip(frames,frames[1:])) if slot!=54 else []:
                            angle=max(required(interpolate_pose(a,b,t)) for t in (1365,2730))
                            curve[i]=max(curve[i],angle)
                            end=(i+1)%period
                            curve[end]=max(curve[end],angle)
                    except ValueError:
                        continue
                    def distance(i,j):
                        d=abs(i-j)
                        return min(d,period-d) if loop is not None else d
                    envelope=(curve if slot==54 else
                              [max(0.,*(v-math.radians(3)*distance(i,j)**2 for j,v in enumerate(curve))) for i in range(period)])
                    choices.append((sum(v*v for v in envelope),sign,envelope))
                if not choices:raise ValueError(f'arm/tail cannot clear floor: {slot}, {bone}')
                _,sign,envelope=min(choices)
                if max(envelope)<1e-8:continue
                adjusted.add(bone)
                previous_angles=None
                for i,p in enumerate(frames):
                    rotations=R.world_rots(sk,p)
                    desired=R.m3mul(R.from_axis_angle(axis,sign*envelope[i%period]),rotations[bone])
                    local=R.m3mul(R.m3t(rotations[sk[bone][1]]),desired)
                    previous_angles=mmd.matrix_euler(local,previous_angles or p[bone][3:6])
                    p[bone][3:6]=[round(v) for v in previous_angles]
            if adjusted:
                anim=replace_channels(out.anims.anims[out.anims.table[slot]],frames,0,nb,
                                      {(b,c) for b in adjusted for c in (3,4,5)},tolerance=6)
                out.anims.table[slot]=len(out.anims.anims);out.anims.anims.append(anim)
                frames,loop,_=animsheet.slot_frames(out,nb,slot)
        for p in frames:
            p[1][7]-=round(bottom(p))
        lifts=[0.]*len(frames)
        for i,(a,b) in enumerate(zip(frames,frames[1:])):
            lift=max(0.,*(bottom(interpolate_pose(a,b,t))+.5 for t in (1365,2730)))
            lifts[i]=max(lifts[i],lift);lifts[i+1]=max(lifts[i+1],lift)
        if loop is not None:
            lifts[0]=lifts[-1]=max(lifts[0],lifts[-1])
        for p,lift in zip(frames,lifts):p[1][7]-=round(lift)
        anim=replace_channels(out.anims.anims[out.anims.table[slot]],frames,0,nb,{(1,7)},tolerance=0)
        out.anims.table[slot]=len(out.anims.anims);out.anims.anims.append(anim)
    out.anims.anims,out.anims.table=motioncyclelayer.share_identical_streams(out.anims.anims,out.anims.table)
    result=out.build()
    if digest(result)!=OUTPUT:
        raise ValueError('authored output differs from the reviewed model')
    report.update(source_sha256=SOURCE, output_sha256=digest(result), acting=checks,
                  storage=motionstorage.require(result,nb))
    return result,report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path); p.add_argument('out',type=Path)
    a=p.parse_args()
    data,report=author(a.source.read_bytes())
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_bytes(data)
    a.out.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
