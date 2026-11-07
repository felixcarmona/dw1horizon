"""Attach the can to Garbagemon's torso and remove inherited wing cues.

The Piximon retarget mapped an independently moving appendage onto the can. Keep the source
acting, including the arms and face, but bind the can at the idle attachment.
Store the result through the model editor as a plain delta.
"""
import copy
import hashlib

import animsheet
import mmd
import motioncyclelayer
import motionstorage
from tools.models.field_animations.articulation import replace_channels

SOURCE = '3e062e65970fc7674ea86aebb60c79a12ed5181656fd41ff7aa3ee2eb5b52a7f'


def can_floor(model, pose):
    matrix = mmd.bone_matrices(model, pose)[2]
    return max(sum(matrix[1][j] * v[j] for j in range(3)) + matrix[1][3]
               for v in model.tmd.obj_verts(1))


def expand_finite_loops(animation):
    """Keep exact keys while giving repeated eating frames distinct numbers.

    Channel replacement uses elapsed ticks. Finite loops reset the program's
    frame counter, so expand them before adding the support-height keys.
    """
    result = copy.deepcopy(animation)
    output, offset, i = [], 0, 0
    while i < len(animation.instrs):
        cue = animation.instrs[i]
        if cue['op'] == 'loop_start' and cue['count'] != 255:
            end = next(j for j in range(i + 1, len(animation.instrs))
                       if animation.instrs[j]['op'] == 'loop_end')
            closing = animation.instrs[end]
            span = closing['frame'] - closing['jump']
            for repeat in range(cue['count']):
                for instruction in animation.instrs[i + 1:end]:
                    assert instruction['op'] not in ('loop_start', 'loop_end')
                    output.append(dict(copy.deepcopy(instruction),
                                       frame=instruction['frame'] + offset + repeat * span))
            offset += (cue['count'] - 1) * span
            i = end + 1
            continue
        instruction = copy.deepcopy(cue)
        if 'frame' in instruction:
            instruction['frame'] += offset
        output.append(instruction)
        i += 1
    result.frame_count += offset
    result.instrs = output
    return result


def repair(data):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('Garbagemon repair requires the reviewed constant-scale model')
    model = mmd.MMD.parse(data, 22)
    model.type = 269
    original = copy.deepcopy(model)
    attachment = animsheet.slot_frames(original, 22, 1)[0][0][2][3:9]
    channels = {(2, c) for c in range(3, 9)} | {(1, 7)}
    changed = []
    for slot, index in enumerate(original.anims.table):
        if index is None:
            continue
        frames, loop, _ = animsheet.slot_frames(original, 22, slot)
        samples = copy.deepcopy(frames)
        for before, pose in zip(frames, samples):
            floor = can_floor(original, before)
            pose[2][3:9] = attachment
            # Preserve the existing support height, including deliberate hops.
            pose[1][7] -= round(can_floor(original, pose) - floor)
        program = expand_finite_loops(original.anims.anims[index])
        anim = replace_channels(program, samples, loop, 22,
                                channels, tolerance=0)
        anim.instrs = [i for i in anim.instrs if not
                       (i['op'] == 'sound' and i['bank'] == 1 and i['note'] == 15)]
        anim.tail = b''
        model.anims.table[slot] = len(model.anims.anims)
        model.anims.anims.append(anim)
        changed.append(slot)
    model.anims.anims, model.anims.table = motioncyclelayer.share_identical_streams(
        model.anims.anims, model.anims.table)
    result = model.build()
    storage = motionstorage.require(result, 22)
    assert original.tmd.build() == model.tmd.build()
    return result, dict(source_sha256=SOURCE, attachment=attachment,
                        changed_slots=changed, storage=storage)


if __name__ == '__main__':
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result, proof = repair(args.source.read_bytes())
    args.output.write_bytes(result)
    args.output.with_suffix('.json').write_text(json.dumps(proof, indent=2) + '\n')
