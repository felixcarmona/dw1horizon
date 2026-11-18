"""Battle strides with planted field motion and delayed source gestures."""
import copy
import hashlib

import animsheet
import mmd
import motioncyclelayer
import motionstorage
import retarget
from motiontailspace import interpolate_pose
from tools.models import clip_repair
from tools.models.field_animations import quadruped as q

SLOTS = {242: (35,), 430: (36,)}
PROFILES = {
    242: dict(slot=35, base=2, bones=(3, 10, 11, 12, 13), delay=True, rooted={12: 3},
              ops=[dict(op='wave', bone=9, axis='x', deg=.5, cycles=1, phase=.5),
                   dict(op='turn', bone=10, axis='z', deg=-12)]),
    430: dict(slot=36, base=35, bones=tuple(range(18, 24)), delay=False, ops=[]),
}


def _clean(model):
    used = sorted(set(i for i in model.anims.table if i is not None))
    renumber = {old: new for new, old in enumerate(used)}
    model.anims.anims = [model.anims.anims[i] for i in used]
    model.anims.table = [renumber.get(i) for i in model.anims.table]
    model.anims.anims, model.anims.table = motioncyclelayer.share_identical_streams(
        model.anims.anims, model.anims.table)
    return model.build()


def author(data, skeleton, sid, raw):
    profile = PROFILES[sid]
    nb = len(skeleton)
    mmd.exe().add_type(9400, skeleton)
    model, source = [mmd.MMD.parse(blob, nb) for blob in (data, raw)]
    model.type = 9400
    slot = profile['slot']
    original, loop, events = animsheet.slot_frames(model, nb, slot)
    if loop != 0:
        raise ValueError('the reviewed stride must loop from its first frame')
    base = animsheet.slot_frames(model, nb, profile['base'])[0]
    source_frames = animsheet.slot_frames(source, nb, slot)[0]
    n = len(original)
    frames = []
    for tick in range(n):
        position = tick / (n-1) * (len(base)-1)
        index = min(len(base)-2, int(position))
        pose = interpolate_pose(base[index], base[index+1], round((position-index) * 4096))
        for bone in profile['bones']:
            delay = 1 + bone % 3 if profile['delay'] else 0
            position = ((tick-delay) / (n-1) % 1) * (len(source_frames)-1)
            index = min(len(source_frames)-2, int(position))
            reference = interpolate_pose(source_frames[index], source_frames[index+1],
                                         round((position-index) * 4096))
            current = mmd.rot_matrix(*pose[bone][3:6])
            target = mmd.rot_matrix(*reference[bone][3:6])
            rotation = q.mul(retarget.scale_rot(q.mul(target, q.tr(current)), .65), current)
            pose[bone][3:6] = [round(value) for value in mmd.matrix_euler(rotation, pose[bone][3:6])]
        frames.append(pose)
    root_end = copy.deepcopy(frames[-1][0])
    frames[-1] = copy.deepcopy(frames[0])
    frames[-1][0] = root_end
    frames = [[[round(value) for value in bone] for bone in pose] for pose in frames]
    # Fit the final support against the same quantized rotations the engine uses.
    model.anims.table[slot] = len(model.anims.anims)
    model.anims.anims.append(mmd.encode_anim(frames, nb, 0, events, tol=1, repeats=False))
    frames = copy.deepcopy(animsheet.slot_frames(model, nb, slot)[0])
    if profile['ops']:
        frames = clip_repair.apply_ops(frames, [parent for _, parent in skeleton], profile['ops'])
    if profile.get('rooted'):
        rest = animsheet.slot_frames(model, nb, 0)[0][0]
        rest_rotations, rest_positions = retarget.world_rots(skeleton, rest), retarget.world_pos(skeleton, rest)
        for bone, anchor in profile['rooted'].items():
            hang = [sum(rest_rotations[anchor][j][i] * (rest_positions[bone][j]-rest_positions[anchor][j])
                        for j in range(3)) for i in range(3)]
            parent = skeleton[bone][1]
            for pose in frames:
                rotations, positions = retarget.world_rots(skeleton, pose), retarget.world_pos(skeleton, pose)
                at = [positions[anchor][i] + sum(rotations[anchor][i][j] * hang[j] for j in range(3))
                      for i in range(3)]
                pose[bone][6:9] = [round(sum(rotations[parent][j][i] * (at[j]-positions[parent][j])
                                            for j in range(3))) for i in range(3)]
    local = {bone: [v[:3] for v in model.tmd.obj_verts(obj)]
             for bone, (obj, _) in enumerate(skeleton) if obj >= 0}

    def floor(pose):
        pose = copy.deepcopy(pose)
        pose[0] = [4096] * 3 + [0] * 6
        world = mmd.bone_matrices(model, pose)
        return max(sum(world[bone][1][j] * v[j] for j in range(3)) + world[bone][1][3]
                   for bone in local for v in local[bone])

    from tools.models.battle_finishes import _ground_frames
    _ground_frames(frames, floor)
    frames = [[[round(value) for value in bone] for bone in pose] for pose in frames]
    out = mmd.MMD.parse(data, nb)
    out.anims.table[slot] = len(out.anims.anims)
    out.anims.anims.append(mmd.encode_anim(frames, nb, 0, events,
                                          tol={0: 0, 1: 0, None: 1}, repeats=False))
    return _clean(out)


def build(data, skeleton, sid, context):
    from tools.models.field_animations import native_battle
    raw, _ = native_battle.apply(data, context, SLOTS[sid])
    result = author(data, skeleton, sid, raw)
    return result, dict(slots=list(SLOTS[sid]), input_sha256=hashlib.sha256(data).hexdigest(),
                        reference_sha256=hashlib.sha256(raw).hexdigest(),
                        output_sha256=hashlib.sha256(result).hexdigest(),
                        storage=motionstorage.require(result, len(skeleton)))
