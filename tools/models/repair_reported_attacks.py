"""Correct weapon use and heavy-body acting in the reported imported clips."""
from copy import deepcopy
import math
import sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parents[1])]
import mmd
import animsheet
import motioncyclelayer
import motionstorage
import numeric as np
from motiondiscidentity import changed_programs
from tools.models.field_animations.war_greymon import rotation, set_rotation

OMNIMON_MELEE = (46, 48, 50, 51)


def finish(before, after, bones, slots):
    for a in after.anims.anims:
        a.tail = b''
    after.anims.anims, after.anims.table = motioncyclelayer.share_identical_streams(after.anims.anims, after.anims.table)
    data = after.build()
    result = mmd.MMD.parse(data, bones)
    assert changed_programs(before, result) == list(slots)
    assert before.tmd.build() == result.tmd.build()
    for slot in slots:
        a, loop, events = animsheet.slot_frames(before, bones, slot)
        b, new_loop, new_events = animsheet.slot_frames(result, bones, slot)
        assert (len(a), loop, events) == (len(b), new_loop, new_events)
    return data, dict(changed_slots=list(slots), mesh_exact=True, events_and_duration_exact=True,
                      storage=motionstorage.require(data, bones))


def omnimon(model):
    """Reflect the source physical action onto Grey, keeping both weapon meshes."""
    out = deepcopy(model)
    frames, loop, events = animsheet.slot_frames(model, 25, 46)
    idle, _, _ = animsheet.slot_frames(model, 25, 33)
    pairs = [(3, 9), (4, 10), (5, 11), (6, 12), (7, 13),
             (15, 19), (16, 20), (17, 21), (18, 22)]
    source_of = {a: b for a, b in pairs} | {b: a for a, b in pairs}
    reflection = np.diag([-1., 1., 1.])
    hist = {}; poses = []
    for tick, original in enumerate(frames):
        pose = deepcopy(original)
        weight = min(1., tick / 5, (len(frames) - 1 - tick) / 7)
        weight = weight * weight * (3 - 2 * weight)
        for bone in range(1, 25):
            if bone == 8:  # Garuru's separate shoulder shell has no Grey counterpart.
                continue
            src = source_of.get(bone, bone)
            desired = reflection @ np.array(mmd.rot_matrix(*original[src][3:6])) @ reflection
            ready = np.array(mmd.rot_matrix(*idle[0][bone][3:6]))
            q0 = mmd.quat(*mmd.matrix_euler(ready)); q1 = mmd.quat(*mmd.matrix_euler(desired))
            set_rotation(pose, bone, np.array(mmd.quat_matrix(mmd._slerp(q0, q1, weight))), hist)
        poses.append([[int(round(x)) for x in bone] for bone in pose])
    animation = mmd.encode_anim(poses, 25, loop_sample=loop, events=events, tol=12, repeats=False)
    out.anims.anims.append(animation)
    for slot in OMNIMON_MELEE:
        out.anims.table[slot] = len(out.anims.anims) - 1
    return finish(model, out, 25, OMNIMON_MELEE)


def apocalymon(model):
    """Reach with the forward crane claw while the heavy core counters its weight."""
    out = deepcopy(model)
    frames, loop, events = animsheet.slot_frames(model, 31, 51)
    idle, _, _ = animsheet.slot_frames(model, 31, 33)
    rest = idle[0]; poses = []; hist = {}
    def reach(t):
        keys = [(0, 0.), (18, -.35), (38, 1.), (44, .8), (60, 0.)]
        if t <= 0: return 0.
        for (a, x), (b, y) in zip(keys, keys[1:]):
            if t <= b:
                u = (t - a) / (b - a); u = u * u * (3 - 2 * u)
                return x + (y - x) * u
        return 0.
    for tick in range(len(frames)):
        pose = deepcopy(rest); drive = reach(tick); lag = reach(tick - 2)
        for bone, degrees in [(1, [-4 * drive, 0, 0]),
                              (3, [9 * drive, -3 * drive, 0]),
                              (6, [0, 0, -5 * drive]), (9, [0, 0, 5 * drive]),
                              (15, [-42 * drive, 0, 0]), (16, [40 * drive, 0, 0]),
                              (17, [-24 * lag, 0, 0]), (12, [-3 * lag, 0, 0]), (18, [5 * lag, 0, 0])]:
            set_rotation(pose, bone, np.array(mmd.rot_matrix(*rest[bone][3:6])) @ rotation(degrees), hist)
        pose[1][7] -= round(7 * math.sin(math.pi * tick / (len(frames) - 1)) ** 2)
        poses.append([[int(round(x)) for x in bone] for bone in pose])
    # This dedicated crane gesture fits without changing any beam aliases.
    animation = mmd.encode_anim(poses, 31, loop_sample=loop, events=events, tol=16, repeats=False)
    out.anims.anims.append(animation); out.anims.table[51] = len(out.anims.anims) - 1
    return finish(model, out, 31, [51])


def main():
    import argparse, json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('species', type=int, choices=[400, 461]); parser.add_argument('model', type=Path); parser.add_argument('out', type=Path)
    args = parser.parse_args(); model = mmd.MMD.load(str(args.model), args.species)
    data, proof = (apocalymon if args.species == 400 else omnimon)(model)
    args.out.parent.mkdir(parents=True, exist_ok=True); args.out.write_bytes(data)
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    main()
