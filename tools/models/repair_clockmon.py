#!/usr/bin/env python3
"""Anchor Clockmon's rider assembly to its clock chassis in field and care clips.

Run on an exported model before storing it with tools/models/edit.py put 290.
The chassis and legs retain their world motion in action clips. Idle plants
those heavy parts while the original head, hands and winding key keep moving.
"""
import argparse
import copy
import json
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parents[1])]
import numpy as np
import animsheet
import mmd
import motioncyclelayer
import motionstorage
from motiondiscidentity import changed_programs
from tools.models.field_animations.articulation import replace_channels
from tools.models.field_animations.war_greymon import set_rotation

SLOTS = (0, 1, 4, 8, 10)


def world(model, pose):
    pose = copy.deepcopy(pose)
    pose[0] = [4096] * 3 + [0] * 6
    return np.array(mmd.bone_matrices(model, pose))


def repair(data):
    old = mmd.MMD.parse(data, 21)
    old.type = 290
    new = copy.deepcopy(old)
    rest = animsheet.slot_frames(old, 21, 0)[0][0]
    baseline = world(old, rest)
    mount = np.linalg.inv(baseline[2]) @ baseline[1]
    report = []
    for slot in SLOTS:
        frames, loop, _ = animsheet.slot_frames(old, 21, slot)
        poses = copy.deepcopy(frames)
        history = {}
        channels = {(b, c) for b in (1, 2) for c in range(3, 9)}
        if slot in (0, 1):
            channels |= {(b, c) for b in range(3, 13) for c in range(3, 9)}
        for pose, source in zip(poses, frames):
            chassis = baseline[2] if slot in (0, 1) else world(old, source)[2]
            upper = chassis @ mount
            set_rotation(pose, 1, upper[:3, :3], history)
            pose[1][6:9] = np.rint(upper[:3, 3]).astype(int).tolist()
            local = np.linalg.inv(upper) @ chassis
            set_rotation(pose, 2, local[:3, :3], history)
            pose[2][6:9] = np.rint(local[:3, 3]).astype(int).tolist()
            if slot in (0, 1):
                for bone in range(3, 13):
                    pose[bone] = copy.deepcopy(rest[bone])
        index = len(new.anims.anims)
        new.anims.anims.append(replace_channels(old.anims.anims[old.anims.table[slot]], poses, loop, 21, channels, tolerance=0))
        new.anims.table[slot] = index
        report.append(dict(slot=slot, ticks=len(frames), planted=slot in (0, 1)))
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = mmd.MMD.parse(result, 21)
    actual.type = 290
    assert actual.tmd.build() == old.tmd.build()
    assert changed_programs(old, actual) == list(SLOTS)
    for row in report:
        slot = row['slot']
        before, loop, events = animsheet.slot_frames(old, 21, slot)
        after, newloop, newevents = animsheet.slot_frames(actual, 21, slot)
        assert (len(before), loop, events) == (len(after), newloop, newevents)
        assert [f[0] for f in before] == [f[0] for f in after]
        errors, gaps = [], []
        for source, pose in zip(before, after):
            w = world(actual, pose)
            expected = baseline if row['planted'] else world(old, source)
            errors.append(float(np.max(np.abs(w[2:13] - expected[2:13]))))
            gaps.append(float(np.linalg.norm(w[1, :3, 3] - (w[2] @ mount)[:3, 3])))
        row.update(max_chassis_and_limb_error=max(errors), max_mount_error=max(gaps))
        assert max(errors) < 3 and max(gaps) < 2, row
    return result, dict(slots=report, mesh_exact=True, root_events_duration_exact=True, storage=motionstorage.require(result, 21))


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
