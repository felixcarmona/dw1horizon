"""Aim Blast Mode's existing cannon during its ordinary hand-attack slots.

The imported Leomon punch drives the bare hand. Keep its body anticipation,
weight shift, timing and events, and aim the cannon with a short recoil instead.
The source mesh puts the cannon on bones 20-23; its side is preserved.
"""
import os as _os
import sys as _sys
_root = _os.path.abspath(_os.path.join(_os.path.dirname(__file__), '../..'))
_sys.path[:0] = [_root, _os.path.join(_root, 'tools')]

from copy import deepcopy
import math

import animsheet
import mmd
import motioncyclelayer
import motionstorage
import numeric as np
from motiondiscidentity import changed_programs
from tools.models.field_animations.articulation import replace_channels
from tools.models.field_animations.war_greymon import align, set_rotation

SID = 403
SLOTS = (0x2e, 0x2f, 0x31, 0x33)  # All four aliases of the imported hand strike.
CANNON = 21
BARE_ARM = (16, 17, 18, 19)


def repair(model, skeleton):
    result = deepcopy(model)
    nb = len(skeleton)
    idle, _, _ = animsheet.slot_frames(model, nb, 0x21)
    channels = {(b, c) for b in (*BARE_ARM, CANNON) for c in (3, 4, 5)}
    proofs = []
    for slot in SLOTS:
        frames, loop, events = animsheet.slot_frames(model, nb, slot)
        if len(frames) != 15 or loop is not None:
            raise ValueError('ordinary cannon attack requires the reviewed 15-tick punch')
        poses = deepcopy(frames)
        history = {}
        for tick, pose in enumerate(poses):
            for bone in BARE_ARM:
                pose[bone][3:6] = idle[tick][bone][3:6]
            # Ease out of the source ready pose, fire at its contact tick,
            # then let the cannon settle before the original recovery.
            weight = min(1., max(0., tick / 4), max(0., (14 - tick) / 4))
            weight = weight * weight * (3 - 2 * weight)
            if not weight:
                continue
            neutral = deepcopy(pose)
            neutral[0] = [4096] * 3 + [0] * 6
            world = np.array(mmd.bone_matrices(model, neutral))
            current = world[CANNON, :3, :3]
            axis = current @ np.array([0., 1., 0.])
            # A small kick after the native contact frame, with a soft settle.
            kick = 10 * max(0., 1 - (tick - 6) / 4) ** 2 if tick >= 6 else 0
            angle = math.radians(kick)
            target = np.array([0., -math.sin(angle), -math.cos(angle)])
            q = mmd.quat(*mmd.matrix_euler(align(axis, target)))
            partial = np.array(mmd.quat_matrix(mmd._slerp((0, 0, 0, 1), q, weight)))
            parent = world[skeleton[CANNON][1], :3, :3]
            set_rotation(pose, CANNON, parent.T @ partial @ current, history)
        original = model.anims.anims[model.anims.table[slot]]
        result.anims.table[slot] = len(result.anims.anims)
        result.anims.anims.append(replace_channels(original, poses, loop, nb, channels, tolerance=6))
        proofs.append(dict(slot=slot, frames=len(frames), contact_tick=6, recoil_degrees=10))
    for animation in result.anims.anims:
        animation.tail = b''
    result.anims.anims, result.anims.table = motioncyclelayer.share_identical_streams(result.anims.anims, result.anims.table)
    data = result.build()
    after = mmd.MMD.parse(data, nb)
    after.type = SID
    assert changed_programs(model, after) == list(SLOTS)
    assert model.tmd.build() == after.tmd.build()
    for slot in SLOTS:
        old, loop, events = animsheet.slot_frames(model, nb, slot)
        new, new_loop, new_events = animsheet.slot_frames(after, nb, slot)
        assert len(old) == len(new) and loop == new_loop and events == new_events
        for a, b in zip(old, new):
            for bone in range(nb):
                for channel in range(9):
                    if (bone, channel) not in channels:
                        assert a[bone][channel] == b[bone][channel], (slot, bone, channel)
    return data, dict(changed_slots=list(SLOTS), cannon_bone=CANNON, checks=proofs,
                      mesh_exact=True, other_channels_exact=True, storage=motionstorage.require(data, nb))


def main():
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model', type=Path)
    parser.add_argument('out', type=Path)
    args = parser.parse_args()
    model = mmd.MMD.load(str(args.model), SID)
    result, proof = repair(model, mmd.exe().skeleton[SID])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(result)
    import json
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    main()
