"""Fit Gizamon's hind feet beneath its body and retain full limbs in sleep.

The paired front support and source head/tail acting remain intact. Hind
knees use the source rig's bend plane and lengths throughout care and travel.
"""
import copy
import hashlib
import math
import mmd
import animsheet
import legik
import motionsecondary
import motioncyclelayer
import motionstorage
import retarget as R
from motiondiscidentity import changed_programs
from motiontailspace import interpolate_pose

SOURCE = '604544f87b36583d1374adca463a496cb0a9530b1b2cafa725e1db782106d704'


def build(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('Gizamon requires its reviewed effective field model')
    mmd.exe().add_type(239, skeleton)
    model = mmd.MMD.parse(data, len(skeleton)); model.type = 239
    result = copy.deepcopy(model)
    reference = R.rest_pose(model, len(skeleton), 33)
    rw, rp = R.world_transform(skeleton, reference)
    checks = []
    for slot in (0, 1, 2, 3, 4, 9, 11):
        frames, loop, events = animsheet.slot_frames(model, len(skeleton), slot)
        history = {}
        worst = 0
        for pose in frames:
            root = pose[0]
            pose[0] = [4096]*3+[0]*6
            def set_world(b, rotation):
                parent = R.world_rots(skeleton, pose)[skeleton[b][1]]
                angles = mmd.matrix_euler(R.m3mul(R.m3t(parent), rotation), history.get(b))
                history[b] = angles
                pose[b][3:6] = [round(v) for v in angles]
            for hip, knee, foot, sign in ((10, 11, 12, 1), (13, 14, 15, -1)):
                positions = R.world_pos(skeleton, pose)
                rotation = rw[foot]
                vertices = model.tmd.obj_verts(skeleton[foot][0])
                sole = max(sum(rotation[1][j]*v[j] for j in range(3)) for v in vertices)
                if slot in (9, 11):
                    # Keep the paws outside the flank as the body settles;
                    # no scale or translation shortening of the limb chain.
                    goal = [sign*85, -sole, 38]
                else:
                    goal = [sign*85, positions[foot][1], positions[foot][2]]
                goal[1] = min(goal[1], -sole-.5)
                origin = positions[hip]
                ref = [rp[b] for b in (hip, knee, foot)]
                pole = motionsecondary.transported_native_pole(*ref, origin, goal)
                joint, end = legik.solve(origin, goal, math.dist(rp[hip],rp[knee]), math.dist(rp[knee],rp[foot]), pole)
                for b, old_vector, new_vector in ((hip,legik.sub(rp[knee],rp[hip]),legik.sub(joint,origin)),
                                                   (knee,legik.sub(rp[foot],rp[knee]),legik.sub(end,joint))):
                    set_world(b,R.m3mul(R.swing(old_vector,new_vector),rw[b]))
                set_world(foot,rotation)
                worst=max(worst,math.dist(R.world_pos(skeleton,pose)[foot],goal))
            pose[0] = root
        if loop is not None:
            mmd.close_loop(frames,loop)
        frames = [[[round(v) for v in bone] for bone in pose] for pose in frames]
        lifts = [0.]*len(frames)
        for tick in range(len(frames)-1):
            for alpha in (0,1365,2730,4096):
                pose = interpolate_pose(frames[tick],frames[tick+1],alpha)
                pose[0] = [4096]*3+[0]*6
                world = mmd.bone_matrices(model,pose)
                floor = max(sum(world[b][1][j]*v[j] for j in range(3))+world[b][1][3]
                            for b in (5,7,12,15) for v in model.tmd.obj_verts(skeleton[b][0]))
                lifts[tick] = max(lifts[tick],floor+.5)
                lifts[tick+1] = max(lifts[tick+1],floor+.5)
        if loop is not None: lifts[0] = lifts[-1] = max(lifts[0],lifts[-1])
        for pose,lift in zip(frames,lifts): pose[1][7] -= math.ceil(lift)
        result.anims.table[slot]=len(result.anims.anims)
        result.anims.anims.append(mmd.encode_anim(frames,len(skeleton),loop,events,tol=1,repeats=False))
        checks.append(dict(slot=slot,maximum_goal_error=worst,hind_paw_half_width=85))
    for a in result.anims.anims: a.tail=b''
    result.anims.anims,result.anims.table=motioncyclelayer.share_identical_streams(result.anims.anims,result.anims.table)
    output=result.build()
    assert model.tmd.build()==result.tmd.build()
    assert changed_programs(model,result)==[0,1,2,3,4,9,11]
    return output,dict(source_sha256=hashlib.sha256(data).hexdigest(),output_sha256=hashlib.sha256(output).hexdigest(),checks=checks,storage=motionstorage.require(output,len(skeleton)))
