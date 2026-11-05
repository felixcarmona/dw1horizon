#!/usr/bin/env python3
"""Use Hagurumon's imported DW2 idle, loosen travel and lay it face up to sleep.

Input is tools/models/edit.py get 122. Slot 33 already holds the source DW2 A0
cycle with the correct reparented gear rig and eye events; no disc bytes are
embedded here. The sleeping clip keeps its duration and original events.
"""
import argparse
import copy
import json
import math
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parents[1])]
import animsheet
import mmd
import motioncyclelayer
import motionstorage
from motiondiscidentity import changed_programs
from motiontailspace import interpolate_pose
from tools.models.field_animations.articulation import replace_channels

RIG = [(-1, -1), (0, 0), (1, 1), (2, 1)]


def floor(model, pose):
    matrices = mmd.bone_matrices(model, pose)
    return max(sum(matrices[b][1][c] * v[c] for c in range(3)) + matrices[b][1][3]
               for b in range(1, 4) for v in model.tmd.obj_verts(b - 1))


def repair(data):
    mmd.exe().skeleton[122] = RIG
    mmd.exe().bone_count[122] = 4
    old = mmd.MMD.parse(data, 4)
    old.type = 122
    new = copy.deepcopy(old)
    # Native slow-follow waits for an idle cycle boundary. Keep this cycle
    # within 32 ticks while retaining the complete DW2 acting and blink.
    source, source_loop, events = animsheet.slot_frames(old, 4, 33)
    assert source_loop == 0
    ticks, period = 32, len(source) - 1
    idle = []
    for tick in range(ticks + 1):
        index, fraction = divmod(tick * period * 4096 // ticks, 4096)
        pose = copy.deepcopy(source[index]) if not fraction else interpolate_pose(source[index], source[index + 1], fraction)
        idle.append([[int(v) for v in bone] for bone in pose])
    mapped, previous = [], -1
    for tick, kind, event in events:
        target = max(previous + 1, round(tick * ticks / period))
        assert target < ticks
        mapped.append((target, kind, event))
        previous = target
    new.anims.anims.append(mmd.encode_anim(idle, 4, loop_sample=0, events=mapped, tol=1, repeats=False))
    new.anims.table[0] = len(new.anims.anims) - 1
    report = [dict(slot=0, source_slot=33, source_game='DW2', source_clip='A0', period=ticks, original_period=period)]
    for slot in (2, 3, 4, 9):
        frames, loop, events = animsheet.slot_frames(old, 4, slot)
        poses = copy.deepcopy(frames)
        n = len(frames) - 1
        for tick, pose in enumerate(poses):
            phase = 2 * math.pi * tick / n
            if slot == 9:
                # Ease onto the back, settle, then hold with a tiny winding drift.
                u = min(1, tick / 24)
                ease = u * u * (3 - 2 * u)
                settle = 2 * math.sin((tick - 24) * math.pi / 8) * math.exp(-(tick - 24) / 6) if tick > 24 else 0
                pose[1][3:6] = [round((-90 * ease + settle) * 4096 / 360), 0, round(3 * math.sin(math.pi * u) * 4096 / 360)]
                for bone in (2, 3):
                    pose[bone][3:6] = [0, 0, round((1 if bone == 2 else -1) * 12 * math.sin(math.pi * u) * 4096 / 360)]
                pose[1][7] = 0
                grounded = -floor(old, pose)
                pose[1][7] = round((1 - ease) * frames[0][1][7] + ease * grounded)
            else:
                fast = slot == 4
                pose[1][3] = round((3 if fast else 2) * math.sin(phase - .35) * 4096 / 360)
                pose[1][5] = round((7 if fast else 4) * math.sin(phase) * 4096 / 360)
                for bone, sign, lag in ((2, 1, .45), (3, -1, .85)):
                    pose[bone][3:5] = [round(v * .25) for v in pose[bone][3:5]]
                    pose[bone][5] = round(sign * (38 if fast else 24) * math.sin(phase - lag) * 4096 / 360)
        channels = {(b, c) for b in (1, 2, 3) for c in (3, 4, 5)}
        if slot == 9:
            channels.add((1, 7))
        else:
            poses[-1][1:] = copy.deepcopy(poses[0][1:])
        if slot == 9:
            closed = animsheet.slot_frames(old, 4, 43)[2][0][2]
            animation = mmd.encode_anim(poses, 4, loop_sample=loop, events=events + [(24, 'tex', closed)], tol=1, repeats=False)
        else:
            animation = replace_channels(old.anims.anims[old.anims.table[slot]], poses, loop, 4, channels, tolerance=1)
        new.anims.anims.append(animation)
        new.anims.table[slot] = len(new.anims.anims) - 1
        report.append(dict(slot=slot, ticks=len(frames)))
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = mmd.MMD.parse(result, 4)
    actual.type = 122
    assert actual.tmd.build() == old.tmd.build()
    assert changed_programs(old, actual) == [0, 2, 3, 4, 9]
    for slot in (2, 3, 4, 9):
        before, loop, events = animsheet.slot_frames(old, 4, slot)
        after, newloop, newevents = animsheet.slot_frames(actual, 4, slot)
        assert (len(before), loop) == (len(after), newloop)
        assert all(e in newevents for e in events)
        if slot != 9:
            assert events == newevents
        assert [f[0] for f in before] == [f[0] for f in after]
    sleeping = animsheet.slot_frames(actual, 4, 9)[0]
    assert abs(floor(actual, sleeping[-1])) <= 1
    return result, dict(slots=report, mesh_exact=True, travel_root_events_duration_exact=True,
                        sleep_final_floor=floor(actual, sleeping[-1]), storage=motionstorage.require(result, 4))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    result, report = repair(a.source.read_bytes())
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_bytes(result)
    a.output.with_suffix('.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
