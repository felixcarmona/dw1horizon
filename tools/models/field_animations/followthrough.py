"""Body-relative insect wings and active small-amphibian locomotion."""
import copy
import hashlib
import json
import math
from pathlib import Path

import animsheet
import mmd
import motionstorage
import retarget as R
from motiontailspace import interpolate_pose
from tools.models.field_animations import animal_refine as A
from tools.models.field_animations.pace import _retimed_events

MANIFEST = Path(__file__).resolve().parents[3] / 'content/models/imports/followthrough.json'


def wings(model, skeleton, cfg):
    # The four membranes are direct children of the thorax, not arms. Their
    # source idle transforms define their open resting plane on the back.
    idle = animsheet.slot_frames(model, len(skeleton), 0)[0]
    reference = idle[0]
    rest_thorax = mmd.matrix_euler(R.world_rots(skeleton, reference)[1])
    additions = []
    for slot in (2, 3, 4):
        frames, loop, events = animsheet.slot_frames(model, len(skeleton), slot)
        original = copy.deepcopy(frames)
        period = len(frames)-1
        history = {}
        for tick, pose in enumerate(frames):
            now = R.world_rots(skeleton, pose)[1]
            for bone in (9, 10, 11, 12):
                pose[bone] = reference[bone][:]
                # Lag the upper/lower membrane orientations behind the thorax
                # while leaving their roots attached to its moving sockets.
                lag = .7 if bone in (9, 11) else 1.2
                t = (tick-lag)%period
                delayed = interpolate_pose(original[int(t)], original[int(t)+1], round((t%1)*4096))
                past = R.world_rots(skeleton, delayed)[1]
                lagged = R.m3mul(now, R.scale_rot(R.m3mul(R.m3t(now), past), .55))
                angles = mmd.matrix_euler(lagged, rest_thorax)
                # Membranes hinge down as the running thorax leans forward;
                # carrying its full pitch would point the wings vertically.
                angles[0] = rest_thorax[0]+.25*(angles[0]-rest_thorax[0])
                angles[2] = rest_thorax[2]+.5*(angles[2]-rest_thorax[2])
                supported = mmd.rot_matrix(*angles)
                side = 1 if bone in (9, 10) else -1
                phase = 2*math.pi*(tick-lag)/period
                flex = mmd.rot_matrix(round(14*math.sin(phase)), 0,
                                      round(side*24*math.sin(phase)))
                resting = mmd.rot_matrix(*reference[bone][3:6])
                desired = R.m3mul(supported, R.m3mul(resting, flex))
                A.set_world(skeleton, pose, bone, desired, history)
        additions.append((slot, frames, loop, events))
    return A.finish(model, additions, len(skeleton), charts=False)


def amphibian(model, sk, cfg):
    # Use the already reviewed low source-length support pose. All care and
    # combat programs remain untouched by this locomotion-only overlay.
    reference = copy.deepcopy(animsheet.slot_frames(model, len(sk), 0)[0][0])
    reference[0] = [4096]*3+[0]*6
    refpos, refrot = R.world_pos(sk, reference), R.world_rots(sk, reference)
    chains = [(4, None, 5), (6, None, 7), (10, 11, 12), (13, 14, 15)]
    feet = [c[-1] for c in chains]
    additions = []
    for slot in (2, 3, 4):
        old, loop, events = animsheet.slot_frames(model, len(sk), slot)
        ticks, speed, lift, bob = cfg['timing'][str(slot)]
        duty = .5 if slot != 4 else .42
        frames, history = [], {}
        for tick in range(ticks+1):
            phase = tick/ticks
            pose = copy.deepcopy(reference)
            pose[1][7] -= round(bob*(.5-.5*math.cos(4*math.pi*phase)))
            pose[1][3] += round(24*math.sin(4*math.pi*phase))
            pose[1][5] += round(18*math.sin(2*math.pi*phase))
            # Head, tail and fins overlap the support changes instead of
            # counteracting them into a static silhouette.
            for bone, amplitude, delay, axis in [(2, 24, .1, 3), (3, 14, .17, 3), (8, 65, .15, 4), (9, 85, .25, 4)]:
                pose[bone][axis] += round(amplitude*math.sin(2*math.pi*(phase-delay)))
            for chain, offset, sign in zip(chains, (0, .5, .5, 0), (1, -1, 1, -1)):
                foot = chain[-1]
                q = (phase+offset)%1
                half = speed*ticks*duty/2
                if q < duty:
                    z = -half+2*half*q/duty
                    height = 0
                    pitch = 0
                else:
                    u = (q-duty)/(1-duty)
                    smooth = u*u*(3-2*u)
                    z = half-2*half*smooth
                    height = lift*math.sin(math.pi*u)**2
                    pitch = -130*math.sin(math.pi*u)
                rotation = R.m3mul(mmd.rot_matrix(pitch, 0, 0), refrot[foot])
                sole = max(sum(rotation[1][j]*v[j] for j in range(3)) for v in model.tmd.obj_verts(sk[foot][0]))
                goal = [refpos[foot][0], -sole-height-1, refpos[foot][2]+z]
                A.solve_leg(sk, pose, reference, chain, goal, rotation, history,
                            [sign*.35, -.35, 1] if chain[1] is not None else None)
            # Settle stance toes onto the floor without stretching the short
            # foreleg or lifting its whole support chain between keys.
            for chain, offset in zip(chains[:2], (0, .5)):
                if (phase+offset)%1 >= duty:continue
                foot=chain[-1]
                foot_y=R.world_pos(sk,pose)[foot][1]
                candidates=[]
                for pitch in range(-240,241,4):
                    rotation=R.m3mul(mmd.rot_matrix(pitch,0,0),refrot[foot])
                    bottom=max(sum(rotation[1][j]*v[j] for j in range(3))for v in model.tmd.obj_verts(sk[foot][0]))+foot_y
                    candidates.append((abs(bottom+1)+abs(pitch)*.0001,rotation))
                A.set_world(sk,pose,foot,min(candidates,key=lambda c:c[0])[1],history)
            pose[1][7]-=math.ceil(max(0,A.floor(model,sk,pose,feet)+.5))
            for chain, offset in zip(chains[2:], (.5,0)):
                if (phase+offset)%1>=duty:continue
                foot=chain[-1]
                A.solve_leg(sk,pose,reference,chain,[R.world_pos(sk,pose)[foot][0],-max(v[1]for v in model.tmd.obj_verts(sk[foot][0]))-1,R.world_pos(sk,pose)[foot][2]],refrot[foot],history,[.35 if foot==12 else -.35,-.35,1])
            pose[1][7] -= 1  # small margin for interpolated toe clearance
            pose[0][8] = -round(speed*tick)
            frames.append(pose)

        events = _retimed_events(events, len(old)-1, ticks)
        additions.append((slot, frames, loop, events))
    return A.finish(model, additions, len(sk))


def build(data, skeleton):
    digest = hashlib.sha256(data).hexdigest()
    recipes = json.loads(MANIFEST.read_text())
    matches = [r for r in recipes.values() if r['source_sha256'] == digest]
    if len(matches) != 1:
        raise ValueError('Follow-through requires a pinned reviewed model')
    cfg = matches[0]
    if skeleton != cfg['skeleton']:
        raise ValueError('Follow-through skeleton differs')
    sid = cfg['species']
    mmd.exe().add_type(sid, skeleton)
    model = mmd.MMD.parse(data, len(skeleton)); model.type = sid
    output = wings(model, skeleton, cfg) if sid == 187 else amphibian(model, skeleton, cfg)
    return output, dict(species=sid, source_sha256=digest,
                        output_sha256=hashlib.sha256(output).hexdigest(),
                        storage=motionstorage.require(output, len(skeleton)))
