"""Keep the salute's cape behind the planted feet after proportion baking."""
import copy
import math

import animsheet
import mmd
from tools.models.field_animations.channels import replace_channels


def clear_salute(data, skeleton, slots, sid):
    model = mmd.MMD.parse(data, len(skeleton))
    model.type = sid
    idle = animsheet.slot_frames(model, len(skeleton), 0x21)[0][0]
    def rotation(pose, bone):
        return [row[:3] for row in mmd.bone_matrices(model, pose)[bone][:3]]
    def mul(a, b):
        return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    hanging = rotation(idle, 16)
    for slot in slots:
        frames, loop, _ = animsheet.slot_frames(model, len(skeleton), slot)
        samples = copy.deepcopy(frames)
        for tick, pose in enumerate(samples):
            angle = -math.radians(7) * math.sin(math.pi * tick / (len(samples) - 1)) ** 2
            c, s = math.cos(angle), math.sin(angle)
            target = mul(hanging, [[1, 0, 0], [0, c, -s], [0, s, c]])
            parent = rotation(pose, skeleton[16][1])
            local = mul(list(map(list, zip(*parent))), target)
            pose[16][3:6] = [round(v) for v in mmd.matrix_euler(local, prev=pose[16][3:6])]
            for bone in (17, 18):
                pose[bone][3:6] = idle[bone][3:6][:]
            if tick in (0, len(samples) - 1):
                for bone in (16, 17, 18):
                    pose[bone][3:6] = idle[bone][3:6][:]
        index = model.anims.table[slot]
        updated = replace_channels(model.anims.anims[index], samples, 0, len(skeleton),
                                   {(b, c) for b in (16, 17, 18) for c in (3, 4, 5)}, tolerance=0)
        model.anims.table[slot] = len(model.anims.anims)
        model.anims.anims.append(updated)
    # Remove orphaned streams while retaining all other slots byte for byte.
    used = sorted(set(model.anims.table) - {None})
    mapping = {old: new for new, old in enumerate(used)}
    model.anims.anims = [model.anims.anims[i] for i in used]
    model.anims.table = [mapping[i] if i is not None else None for i in model.anims.table]
    return model.build()
