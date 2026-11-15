"""Plant Deltamon's feet while its three heads celebrate."""
import copy
import math

import animsheet
import mmd
import motioncyclelayer
from tools.models.field_animations import quadruped as q


def _clean(model):
    used = sorted(set(i for i in model.anims.table if i is not None))
    renumber = {old: new for new, old in enumerate(used)}
    model.anims.anims = [model.anims.anims[i] for i in used]
    model.anims.table = [renumber.get(i) for i in model.anims.table]
    model.anims.anims, model.anims.table = motioncyclelayer.share_identical_streams(
        model.anims.anims, model.anims.table)
    return model.build()


def plant(data, sk):
    from tools.models.battle_finishes import _ground_frames
    nb = len(sk)
    mmd.exe().add_type(9400, sk)
    model = mmd.MMD.parse(data, nb)
    model.type = 9400
    frames, loop, events = animsheet.slot_frames(model, nb, 42)
    frames = copy.deepcopy(frames)
    rest = copy.deepcopy(frames[0])
    model.anims.anims[model.anims.table[0]] = mmd.encode_anim([rest, rest], nb)
    profile = dict(legs={'L': (21, 22, 23, 1, False), 'R': (24, 25, 26, 1, False)},
                   pole={False: [0, 0, -1]}, pole_world=True)
    rig = q.Rig(model, sk, profile)
    reference = mmd.bone_matrices(model, rest)
    for tick, pose in enumerate(frames):
        # Keep the pelvis square beneath the independently moving chest and heads.
        pose[17][3:6] = rest[17][3:6]
        for hip, knee, foot, _, _ in profile['legs'].values():
            anchor = [reference[foot][i][3] for i in range(3)]
            world = mmd.bone_matrices(model, pose)
            shoulder = [world[hip][i][3] for i in range(3)]
            reach = q.norm(rig.link(pose, knee)[0]) + q.norm(rig.link(pose, foot)[0]) - 4
            horizontal = math.hypot(anchor[0] - shoulder[0], anchor[2] - shoulder[2])
            if horizontal >= reach:
                raise ValueError(('horizontal reach', foot, horizontal, reach))
            gap = anchor[1] - math.sqrt(reach * reach - horizontal * horizontal) - shoulder[1]
            pose[1][7] += round((gap + math.sqrt(gap * gap + 16)) / 2)
        for name, (hip, knee, foot, _, _) in profile['legs'].items():
            anchor = [reference[foot][i][3] for i in range(3)]
            rotation, short = rig.solve(pose, name, anchor, {}, pole=[0, 0, -1])
            if short > 1:
                raise ValueError(('unreached', name, short))
            roll = mmd.rot_matrix(round(5 * q.DEG * math.sin(math.pi * tick / (len(frames)-1)) ** 2), 0, 0)
            target = q.mul(roll, [row[:3] for row in reference[foot][:3]])
            q.set_rot(pose, foot, q.mul(q.tr(rotation), target), {})
    local = {b: [v[:3] for v in model.tmd.obj_verts(o)]
             for b, (o, _) in enumerate(sk) if o >= 0}

    def floor(pose):
        pose = copy.deepcopy(pose)
        pose[0] = [4096] * 3 + [0] * 6
        world = mmd.bone_matrices(model, pose)
        return max(sum(world[b][1][j] * v[j] for j in range(3)) + world[b][1][3]
                   for b in local for v in local[b])

    _ground_frames(frames, floor)
    # Rock onto the toes as weight moves forward, keeping both soles close to the floor.
    for pose in frames:
        for foot in (23, 26):
            parent = sk[foot][1]

            def sole(angle):
                world = mmd.bone_matrices(model, pose)
                target = q.mul(mmd.rot_matrix(round(angle * q.DEG), 0, 0),
                               [row[:3] for row in reference[foot][:3]])
                q.set_rot(pose, foot, q.mul(q.tr([row[:3] for row in world[parent][:3]]), target), {})
                world = mmd.bone_matrices(model, pose)
                return max(sum(world[foot][1][j] * v[j] for j in range(3)) + world[foot][1][3]
                           for v in local[foot])

            low, high = 0., 15.
            if sole(0) < -3:
                for _ in range(12):
                    mid = (low + high) / 2
                    if sole(mid) < -2:
                        low = mid
                    else:
                        high = mid
                sole(high)
    _ground_frames(frames, floor)
    out = mmd.MMD.parse(data, nb)
    out.anims.table[42] = len(out.anims.anims)
    out.anims.anims.append(mmd.encode_anim(frames, nb, loop, events,
                                          tol={1: 0, None: 1}, repeats=False))
    return _clean(out)
