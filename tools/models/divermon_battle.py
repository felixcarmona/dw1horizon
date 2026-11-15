"""A loose harpoon stride over Divermon's planted field gait."""
import copy

import animsheet
import mmd
import motioncyclelayer
import retarget
from motiontailspace import interpolate_pose
from tools.models import clip_repair
from tools.models.field_animations import quadruped as q

BONES = (5, 6, 7, 9, 13)


def author(data, skeleton, sid, raw):
    if sid != 304:
        raise ValueError('this harpoon stride belongs to Divermon')
    nb = len(skeleton)
    model, source = [mmd.MMD.parse(blob, nb) for blob in (data, raw)]
    original, loop, events = animsheet.slot_frames(model, nb, 35)
    if loop != 0:
        raise ValueError('the battle stride must loop from its first frame')
    base = animsheet.slot_frames(model, nb, 2)[0]
    source_frames = animsheet.slot_frames(source, nb, 35)[0]
    frames = []
    for tick in range(len(original)):
        position = tick / (len(original)-1) * (len(base)-1)
        index = min(len(base)-2, int(position))
        pose = interpolate_pose(base[index], base[index+1], round((position-index) * 4096))
        for bone in BONES:
            delay = 1 + bone % 3
            position = ((tick-delay) / (len(original)-1) % 1) * (len(source_frames)-1)
            index = min(len(source_frames)-2, int(position))
            reference = interpolate_pose(source_frames[index], source_frames[index+1],
                                         round((position-index) * 4096))
            current, target = [mmd.rot_matrix(*p[bone][3:6]) for p in (pose, reference)]
            rotation = q.mul(retarget.scale_rot(q.mul(target, q.tr(current)), .65), current)
            pose[bone][3:6] = [round(value) for value in mmd.matrix_euler(rotation, pose[bone][3:6])]
        frames.append(pose)
    root_end = copy.deepcopy(frames[-1][0])
    frames[-1] = copy.deepcopy(frames[0])
    frames[-1][0] = root_end
    frames = [[[round(v) for v in bone] for bone in pose] for pose in frames]
    # Lift the harpoon's point clear of the arena without moving either planted foot.
    frames = clip_repair.apply_ops(frames, [parent for _, parent in skeleton],
                                  [dict(op='turn', bone=7, axis='z', deg=12)])
    tolerance = {None: 0, **{bone: 1 for bone in BONES}}
    out = copy.deepcopy(model)
    out.anims.table[35] = len(out.anims.anims)
    out.anims.anims.append(mmd.encode_anim(frames, nb, 0, events, tol=tolerance, repeats=False))
    used = sorted(set(i for i in out.anims.table if i is not None))
    renumber = {old: new for new, old in enumerate(used)}
    out.anims.anims = [out.anims.anims[i] for i in used]
    out.anims.table = [renumber.get(i) for i in out.anims.table]
    out.anims.anims, out.anims.table = motioncyclelayer.share_identical_streams(
        out.anims.anims, out.anims.table)
    return out.build()
