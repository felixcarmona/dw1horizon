"""Keep Nefertimon's sleeping right paw low and start her idle with the tail relaxed.

The complete existing idle is rotated by 66 ticks, without changing its period
or acting. Status resets this clip every draw: starting at its low-tail pose
lets the camera show the body at a readable size above the care rows.
Sleep retains all original channels except the right foreleg's rotations.
Its two-bone solve follows the lowering chest with a softly reaching paw,
using native Garurumon's low forepaw carriage as the visual reference.
"""
import copy
import hashlib

import animsheet
import mmd
import motionstorage
from motiondiscidentity import changed_programs
from tools.models.field_animations.articulation import replace_channels
from tools.models.field_animations.nefertimon import Rig, mul, rot, set_rot, smooth, standing, tr

SOURCE = 'dc34a702a5fcc090f9df3766a6bbe12c09d98d71d25d6c04ffb46f874f83ac8e'
IDLE_PHASE = 66
SLEEP_CHANNELS = {(bone, channel) for bone in (4, 5, 6) for channel in (3, 4, 5)}


def build(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('Nefertimon care requires the reviewed paced model')
    n = len(skeleton)
    mmd.exe().add_type(198, skeleton, name='Nefertimon')
    old = mmd.MMD.parse(data, n)
    old.type = 198
    new = copy.deepcopy(old)
    frames, loop, events = animsheet.slot_frames(old, n, 0)
    assert loop == 0 and not events
    period = len(frames) - 1
    assert all(p[0] == frames[0][0] for p in frames)
    shifted = copy.deepcopy(frames[IDLE_PHASE:period] + frames[:IDLE_PHASE])
    shifted.append(copy.deepcopy(shifted[0]))
    idle_index = old.anims.table[0]
    new.anims.anims[idle_index] = mmd.encode_anim(shifted, n, loop_sample=0, tol=1, repeats=False)

    rig = Rig(old, skeleton)
    frames, loop, events = animsheet.slot_frames(old, n, 9)
    poses = copy.deepcopy(frames)
    history = {}
    worst_reach = 0
    for tick, pose in enumerate(poses):
        ease = smooth(tick / 45)
        world = rot([0, -4 * ease, 0])
        target = standing(rig, 'RF', 68 + 4 * ease, -155 - 12 * ease, world)
        # Keep the inherited chest's breathing and turns. The elbow follows
        # them, and the paw reaches twelve units forward as she settles.
        forearm, reach = rig.solve(pose, 'RF', target, history)
        set_rot(pose, 6, mul(tr(forearm), world), history)
        worst_reach = max(worst_reach, reach)
    index = old.anims.table[9]
    new.anims.anims[index] = replace_channels(old.anims.anims[index], poses, loop, n, SLEEP_CHANNELS)
    result = new.build()
    actual = mmd.MMD.parse(result, n)
    assert old.tmd.build() == actual.tmd.build()
    changed = sorted({9} | {slot for slot, idx in enumerate(old.anims.table) if idx == idle_index})
    assert changed_programs(old, actual) == changed
    assert worst_reach < 1, worst_reach
    return result, dict(species=198, source_sha256=SOURCE,
                        output_sha256=hashlib.sha256(result).hexdigest(),
                        changed_slots=changed, idle_phase=IDLE_PHASE,
                        sleep_rotation_bones=[4, 5, 6],
                        sleep_unreached=worst_reach, mesh_exact=True,
                        storage=motionstorage.require(result, n))
