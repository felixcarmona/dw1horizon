"""Restore KingEtemon's support and fit native Etemon gestures to its own rig.

Offline authoring only. The accepted result is stored as a plain model delta.
The input is the effective model after its original chibi pass.
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
import footfix
import legik
import mmd
import motioncyclelayer
import motionsecondary
import motionstorage
import retarget as rt
from tools.models.field_animations import chibi, native_polish
from tools.models.resize import resize

RECIPE = ROOT / 'content/models/authoring/kingetemon.json'


def repair(data, cfg=None):
    cfg = cfg or json.loads(RECIPE.read_text())
    if hashlib.sha256(data).hexdigest() != cfg['source_sha256']:
        raise ValueError('KingEtemon requires the reviewed effective source')
    sk = cfg['skeleton']
    nb = len(sk)
    data = resize(data, nb, cfg['resize'])
    original = mmd.MMD.parse(data, nb)
    original.type = 303
    result, proof = native_polish.author(data, sk, 303, cfg)
    model = mmd.MMD.parse(result, nb)
    model.type = 303
    feet = {b: [v[:3] for v in model.tmd.obj_verts(sk[b][0])] for b in cfg['feet']}

    def bottom(pose):
        p = copy.deepcopy(pose)
        p[0] = [4096]*3 + [0]*6
        return max(chibi.bone_lows(model, feet, p).values())

    grounded = []
    # Keep all rotations, scale tracks, travel, events and native timing. Only
    # the carrier height changes where the retarget left bent legs floating.
    for slot in cfg['ground_slots']:
        index = model.anims.table[slot]
        animation = copy.deepcopy(model.anims.anims[index])
        model.anims.table[slot] = len(model.anims.anims)
        model.anims.anims.append(animation)
        for _ in range(3):
            frames, poses, heights, _ = chibi.replay(model, nb, len(model.anims.anims)-1, slot, 1)
            targets = {}
            for frame, pose, height in zip(frames, poses, heights):
                targets[frame] = height-bottom(pose)
            chibi._rewrite_heights(animation, 1, targets, .5)
        grounded.append(slot)

    # A seated sleeper gathers the long lower cape behind the hips. Keep its
    # rigid pieces and lengths, folding successive panels in opposite senses
    # instead of letting the hem prop the feet above the floor.
    for slot in cfg.get('cape_floor_slots', []):
        frames, _, _ = animsheet.slot_frames(model, nb, slot)
        cape = {b: [v[:3] for v in model.tmd.obj_verts(sk[b][0])] for b in (19,20,21,22)}

        def folded(pose, angle):
            p = copy.deepcopy(pose)
            p[20][3] += round(angle*4096/360)
            p[21][3] -= round(angle*4096/720)
            p[22][3] -= round(angle*4096/720)
            return p

        needed = []
        for pose in frames:
            for angle in range(0,122,2):
                p = folded(pose,angle)
                p[0] = [4096]*3+[0]*6
                if max(chibi.bone_lows(model,cape,p).values()) <= 0:
                    needed.append(angle)
                    break
            else:
                raise ValueError('KingEtemon cape cannot settle above the floor')
        angles = [max(needed[j]-2*(i-j)**2 for j in range(len(needed))) for i in range(len(needed))]
        world = [rt.world_rots(sk,folded(p,angle)) for p,angle in zip(frames,angles)]
        animation = model.anims.anims[model.anims.table[slot]]
        for bone in (20,21,22):
            assert not any(i['op']=='key' and any(g['bone']==bone and set(g['vals'])-{'rx','ry','rz'}
                                                 for g in i['bones']) for i in animation.instrs)
            footfix.rewrite_bone(animation,nb,sk,slot,bone,lambda t,p,w,bone=bone:world[t][bone],1)

    # The enlarged crown needs space beside raised gloves. Move the native
    # wrist trajectories outward with a complete two-joint arm solve; retain
    # wrist rotation, elbow bend plane and the native gesture's timing.
    for slot in cfg['slots']:
        frames, loop, events = animsheet.slot_frames(model, nb, slot)
        spacing = cfg.get('arm_spacing', {}).get(str(slot), 0)
        forward = cfg.get('arm_forward', 0)
        lower = cfg.get('arm_lower', 0)
        previous = {}
        for p in frames:
            for shoulder, elbow, hand, sign in ((11,12,13,1), (14,15,16,-1)):
                if not spacing:
                    continue
                rotations, positions = rt.world_transform(sk, p)
                chain = [positions[b] for b in (shoulder, elbow, hand)]
                goal = list(chain[-1]); goal[0] += sign*spacing
                goal[1] += lower
                goal[2] -= forward
                pole = motionsecondary.transported_native_pole(*chain, chain[0], goal)
                joint, end = legik.solve(chain[0], goal, math.dist(chain[0],chain[1]),
                                        math.dist(chain[1],chain[2]), pole)
                turns = motionsecondary.native_plane_rotations(chain, [chain[0],joint,end],
                                                               [rotations[shoulder],rotations[elbow]])
                for b, rotation in ((shoulder,turns[0]),(elbow,turns[1]),(hand,rotations[hand])):
                    parent = rt.world_rots(sk,p)[sk[b][1]]
                    angles = mmd.matrix_euler(rt.m3mul(rt.m3t(parent),rotation),previous.get(b,p[b][3:6]))
                    p[b][3:6] = previous[b] = [round(v) for v in angles]

        # Four cape panels trail the torso with successively slower response.
        # Finite gestures start at rest; cyclic ones settle before recording.
        for bone, alpha in zip((19,20,21,22),(.65,.55,.45,.35)):
            parent = sk[bone][1]
            local = rt.rot_of(frames[0][bone])
            targets = [rt.m3mul(rt.world_rots(sk,p)[parent],local) for p in frames]
            state = targets[0]
            history = []
            count = len(frames)-1 if loop == 0 else len(frames)
            for tick in range(count*(8 if loop == 0 else 1)):
                i = tick % count
                delta = rt.m3mul(rt.m3t(state),targets[i])
                state = rt.m3mul(state,rt.scale_rot(delta,alpha))
                if tick >= count*(7 if loop == 0 else 0):
                    history.append(state)
            if loop == 0:
                history.append(history[0])
            for p, rotation in zip(frames,history):
                parent_rot = rt.world_rots(sk,p)[parent]
                p[bone][3:6] = [round(v) for v in mmd.matrix_euler(rt.m3mul(rt.m3t(parent_rot),rotation),p[bone][3:6])]
        mmd.close_loop(frames,loop)
        model.anims.table[slot] = len(model.anims.anims)
        model.anims.anims.append(mmd.encode_anim(frames,nb,loop,events,tol=cfg['tolerance'],repeats=False))
    for animation in model.anims.anims:
        animation.tail = b''
        for instruction in animation.instrs:
            if instruction['op'] == 'key':
                for block in instruction['bones']:
                    block['vals'] = {k: round(v) for k,v in block['vals'].items()}
    model.anims.anims,model.anims.table = motioncyclelayer.share_identical_streams(model.anims.anims,model.anims.table)
    output = model.build()
    assert model.tmd.build() == original.tmd.build()
    if cfg.get('output_sha256') and hashlib.sha256(output).hexdigest() != cfg['output_sha256']:
        raise ValueError('KingEtemon authoring result differs from the reviewed output')
    proof.update(grounded_slots=grounded,resize=cfg['resize'],
                 output_sha256=hashlib.sha256(output).hexdigest(),
                 storage=motionstorage.require(output,nb))
    return output,proof


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    a = p.parse_args()
    data,proof = repair(a.source.read_bytes())
    a.output.write_bytes(data)
    a.output.with_suffix('.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps(proof['storage'],indent=2))


if __name__ == '__main__':
    main()
