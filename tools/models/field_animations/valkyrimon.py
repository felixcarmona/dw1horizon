"""Author Valkyrimon's resized delta with native Angemon locomotion.

Offline only: player builds replay the pinned delta. Run with --source and --out;
store the result with tools/models/edit.py put 255.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet
import legik
import mmd
import motioncyclelayer
import motionstorage
import motionsecondary
import retarget as R
from motiontailspace import interpolate_pose
from tools.models.resize import resize

SOURCE = '455fe0fc77943c2cb5ec3ca4f552df49921baf0d7cf9641b3ee6a591761b7c19'
DONOR = '4bbdf9a2763dab219bc599f0d9cfa44d93263fc5e00930d405ad055f68c22ed9'
SKELETON = '2d6f7c5001539a82bb92a46a29e2f2186e0d391ea8eb96e14b86d4ec2175706d'
FACTOR = .8
TRAVEL = 1.1
LEGS = [(18, 19, 20, 19, 20, 21), (21, 22, 23, 22, 23, 24)]
MAP = {1: 1, 2: 2, 3: 3, 5: 4, 6: 5, 8: 6, 9: 7, 10: 8, 12: 9,
       13: 14, 14: 15, 15: 16, 16: 17,
       18: 19, 19: 20, 20: 21, 21: 22, 22: 23, 23: 24}


def build(data, donor_data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('requires the reviewed Valkyrimon import')
    if hashlib.sha256(donor_data).hexdigest() != DONOR:
        raise ValueError('requires native Angemon from the registered disc')
    if len(skeleton) != 30 or hashlib.sha256(json.dumps(skeleton).encode()).hexdigest() != SKELETON:
        raise ValueError('requires the reviewed 30-bone skeleton')
    mmd.exe().add_type(255, skeleton)
    nb = len(skeleton)
    model = mmd.MMD.parse(resize(data, nb, FACTOR), nb)
    model.type = 255
    donor = mmd.MMD.parse(donor_data, 26)
    donor.type = 20
    ds = mmd.exe().skeleton[20]
    rest, dr = R.rest_pose(model, nb), R.rest_pose(donor, 26)
    # Remove the insect donor's crouched, twisted carrier reference.
    rest[1][3:9] = [0,0,0,0,0,0]
    rest[2][3:6] = [0,0,0]
    chains = [(h, k, dh, dk) for h,k,f,dh,dk,df in LEGS]
    chains += [(k, f, dk, df) for h,k,f,dh,dk,df in LEGS]
    rest = R.align_reference(skeleton, rest, ds, dr, chains, keep_world=[20,23])
    # Ground the calibrated native reference before transferring locomotion.
    # An arbitrary low carrier forces both knees into a deep squat.
    reference = mmd.bone_matrices(model,rest)
    floor = max(sum(reference[b][1][i]*v[i] for i in range(3))+reference[b][1][3]
                for b in (20,23) for v in model.tmd.obj_verts(skeleton[b][0]))
    rest[1][7] -= round(floor)
    rp, rw = R.world_pos(skeleton, rest), R.world_rots(skeleton, rest)
    dw0 = R.world_rots(ds, dr)
    result = copy.deepcopy(model)
    checks = []
    for slot in (2,3,4):
        native, loop, events = animsheet.slot_frames(donor,26,slot)
        transfer = R.transfer(donor,20,slot,255,rest,
                              {t:(s,1.) for t,s in MAP.items()},(1,1,TRAVEL),TRAVEL)
        frames, history = [], {}
        worst_reach = 0.
        support_drops = []
        for tick, source in enumerate(native):
            pose = copy.deepcopy(rest)
            for bone, seq in transfer['rot'].items():
                pose[bone][3:6] = [round(v) for v in seq[tick]]
            pose[1][6:9] = [round(rest[1][6+i]+transfer['hips'][tick][i]) for i in range(3)]
            pose[0][6:9] = [0,0,0]
            dp = copy.deepcopy(source)
            dp[0] = [4096]*3+[0]*6
            dw, dpos = R.world_rots(ds,dp), R.world_pos(ds,dp)
            dm = mmd.bone_matrices(donor,dp)
            def set_world(bone, world):
                parent = R.world_rots(skeleton,pose)[skeleton[bone][1]]
                angles = mmd.matrix_euler(R.m3mul(R.m3t(parent),world),history.get(bone))
                history[bone] = angles
                pose[bone][3:6] = [round(v) for v in angles]
            goals = []
            for hip,knee,foot,dh,dk,df in LEGS:
                fw = R.m3mul(R.m3mul(dw[df],R.m3t(dw0[df])),rw[foot])
                sole = max(sum(fw[1][j]*v[j] for j in range(3)) for v in model.tmd.obj_verts(skeleton[foot][0]))
                native_sole = max(sum(dm[df][1][j]*v[j] for j in range(3))+dm[df][1][3]
                                  for v in donor.tmd.obj_verts(ds[df][0]))
                target = [TRAVEL*dpos[df][i] for i in range(3)]
                target[1] = -sole + TRAVEL*min(0,native_sole)
                goals.append((hip,knee,foot,fw,target))
            # Fit both stance/swing targets before solving either leg. Preserve
            # a small bend at full extension and lower only as reach requires.
            positions = R.world_pos(skeleton,pose)
            down = 0.
            for hip,knee,foot,fw,target in goals:
                origin = positions[hip]
                length = legik.norm(legik.sub(rp[knee],rp[hip]))+legik.norm(legik.sub(rp[foot],rp[knee]))-2
                horizontal = (target[0]-origin[0])**2+(target[2]-origin[2])**2
                assert horizontal < length**2
                down = max(down,target[1]-origin[1]-math.sqrt(length**2-horizontal))
            pose[1][7] += math.ceil(down)
            support_drops.append(math.ceil(down))
            for hip,knee,foot,fw,target in goals:
                origin = R.world_pos(skeleton,pose)[hip]
                v1,v2 = legik.sub(rp[knee],rp[hip]),legik.sub(rp[foot],rp[knee])
                kn, ac = legik.solve(origin,target,legik.norm(v1),legik.norm(v2),[0,0,-1])
                worst_reach = max(worst_reach,legik.norm(legik.sub(ac,target)))
                hr, kr = motionsecondary.native_plane_rotations(
                    [rp[b] for b in (hip,knee,foot)], [origin,kn,ac], [rw[hip],rw[knee]])
                set_world(hip,hr)
                set_world(knee,kr)
                set_world(foot,fw)
            pose[0][6:9] = [round(v) for v in transfer['root'][tick]]
            frames.append(pose)
        assert worst_reach < 1, (slot, worst_reach)
        mmd.close_loop(frames,loop)
        # Ease the walk over 24 ticks; its native acceleration and body
        # counter-motion remain, at a follow speed just above 15 units/tick.
        duration = {2:24,3:28,4:16}[slot]
        old_frames = frames
        frames = []
        for tick in range(duration+1):
            at = tick*(len(old_frames)-1)/duration
            left = min(int(at),len(old_frames)-2)
            frames.append(interpolate_pose(old_frames[left],old_frames[left+1],round((at-left)*4096)))
        # Clear the complete boots at keys and the renderer's thirds. Spread
        # necessary carrier lift across neighboring keys to avoid hard snaps.
        lifts = [0.] * len(frames)
        for i in range(len(frames)-1):
            for alpha in (0,1365,2730,4096):
                p = interpolate_pose(frames[i],frames[i+1],alpha)
                p[0] = [4096]*3+[0]*6
                mats = mmd.bone_matrices(model,p)
                floor = max(sum(mats[b][1][j]*v[j] for j in range(3))+mats[b][1][3]
                            for b in (20,23) for v in model.tmd.obj_verts(skeleton[b][0]))
                lifts[i] = max(lifts[i],floor+.5)
                lifts[i+1] = max(lifts[i+1],floor+.5)
        duration = len(frames)-1
        lifts[0] = lifts[-1] = max(lifts[0],lifts[-1])
        eased = [max(lifts[j]-2*min((i-j)%duration,(j-i)%duration) for j in range(duration)) for i in range(duration)]
        eased.append(eased[0])
        for pose,lift in zip(frames,eased):
            pose[1][7] -= round(max(0,lift))
        animation = mmd.encode_anim(frames,nb,loop,
                                    [(round(t*duration/(len(native)-1)),k,c) for t,k,c in events if k=='sound'],tol=1,repeats=False)
        result.anims.table[slot] = len(result.anims.anims)
        result.anims.anims.append(animation)
        checks.append(dict(slot=slot,ticks=duration,maximum_ik_error=worst_reach,maximum_support_drop=max(support_drops),maximum_carrier_lift=max(eased)))
    for anim in result.anims.anims:
        anim.tail = b''
    result.anims.anims,result.anims.table = motioncyclelayer.share_identical_streams(result.anims.anims,result.anims.table)
    output = result.build()
    return output,dict(source_sha256=SOURCE,donor_sha256=hashlib.sha256(donor_data).hexdigest(),
                       output_sha256=hashlib.sha256(output).hexdigest(),scale=FACTOR,
                       native_travel_scale=TRAVEL,checks=checks,storage=motionstorage.require(output,nb))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    a = p.parse_args()
    sk = json.loads((ROOT/'content/species/255-valkyrimon.json').read_text())['model']['skeleton']
    data,proof = build(a.source.read_bytes(),(ROOT/'extracted/CHDAT/MMD0/ANGE.MMD').read_bytes(),sk)
    a.out.write_bytes(data)
    a.report.write_text(json.dumps(proof,indent=2)+'\n')


if __name__ == '__main__':
    main()
