"""Bake Yokomon's field cadence into its baby delta, after petals and neck.

Build SRC.MMD and TIM from the current tools.models.babies.build_species(477, extracted).
Run with SRC.MMD OUT.MMD, then `python3 -m tools.models.babies encode 477 OUT.MMD TIM`
and `python3 tools/models/edit.py repin 477 OUT.MMD TIM`.
Encode re-centres the resampled poses: rebuild 477 into OUT.MMD before repinning
so the input matches the canonical builder output (pass --games if needed).
The planted roots keep their donor's uneven travel through each stride. Both
travel and every bone's clock change together; the petals retain their lag.
Walk: 17 ticks -> 14, condition: 21 -> 25, run: 17 -> 15. The stride lengths
change by only 3.5%, 1.6%, 1.6% respectively to reach 17 / 11.5 / 38.
"""
import copy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]

import animsheet
import mmd
import motionstorage
from motiondiscidentity import changed_programs
from motiontailspace import interpolate_pose
from tools.models.field_animations.pace import _retimed_events

SLOTS = {2: (17, 14, 17), 3: (21, 25, 11.5), 4: (17, 15, 38)}


def build(data):
    old = mmd.MMD.parse(data, 10)
    new = copy.deepcopy(old)
    for slot, (source_ticks, ticks, speed) in SLOTS.items():
        frames, loop, events = animsheet.slot_frames(old, 10, slot)
        assert loop == 0 and len(frames) - 1 == source_ticks
        start = int(frames[0][0][8])
        travel = start - frames[-1][0][8]
        samples = []
        for t in range(ticks + 1):
            i, rest = divmod(t * source_ticks * 4096 // ticks, 4096)
            pose = (copy.deepcopy(frames[i]) if not rest else
                    interpolate_pose(frames[i], frames[i + 1], rest))
            pose = [[int(v) for v in bone] for bone in pose]
            pose[0][8] = start + round((pose[0][8] - start) * speed * ticks / travel)
            samples.append(pose)
        animation = mmd.encode_anim(samples, 10, loop_sample=0,
                                    events=_retimed_events(events, source_ticks, ticks), tol=1)
        # Replace the shared stream so the donor's field aliases follow it.
        new.anims.anims[new.anims.table[slot]] = animation
    result = new.build()
    actual = mmd.MMD.parse(result, 10)
    assert actual.tmd.build() == old.tmd.build()
    assert changed_programs(old, actual) == [2, 3, 4, 27, 35, 36]
    motionstorage.require(result, 10)
    return result


if __name__ == '__main__':
    Path(sys.argv[2]).write_bytes(build(Path(sys.argv[1]).read_bytes()))
