"""Correct weapon use and heavy-body acting in the reported imported clips."""
from copy import deepcopy
import sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parents[2]), str(Path(__file__).resolve().parents[1])]
import mmd
import animsheet
import motioncyclelayer
import motionstorage
from motiondiscidentity import changed_programs



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


def apocalymon(model):
    """Lash all five chain claws, with delayed wrists and a grounded heavy core."""
    out = deepcopy(model)
    frames, loop, events = animsheet.slot_frames(model, 31, 51)
    idle, _, _ = animsheet.slot_frames(model, 31, 33)
    rest = idle[0]; poses = []
    def reach(t, lag=0):
        keys = [(0, 0.), (14 + lag, -.45), (37 + lag, 1.), (45 + lag, .6), (55 + lag, 0.), (60, 0.)]
        if t <= 0: return 0.
        for (a, x), (b, y) in zip(keys, keys[1:]):
            if t <= b:
                u = (t - a) / (b - a)
                return x + (y - x) * u
        return 0.
    chains = [(15, 0, -38, 16, 0, 48, 17, 0, -32),
              (18, 2, 30, 19, 1, 46, 20, 2, -30),
              (21, 2, -32, 22, 1, 43, 23, 2, 30),
              (24, 1, -30, 25, 1, -38, 26, 2, 32),
              (27, 0, 33, 28, 0, -46, 29, 0, 38)]
    for tick in range(len(frames)):
        pose = deepcopy(rest); drive = reach(tick)
        def delta(bone, axis, amount):
            # One local hinge per segment keeps the helical chain's shape.
            pose[bone][3 + axis] += round(amount * 4096 / 360)
        delta(1, 0, -3.5 * drive); delta(3, 0, 10 * drive)
        for root, axis, amount, elbow, ea, em, claw, ca, cm in chains:
            delta(root, axis, amount * drive)
            delta(elbow, ea, em * reach(tick, 1))
            delta(claw, ca, cm * reach(tick, 3))
        for bone, axis, amount in [(6, 2, 28), (9, 2, -28), (12, 0, -7)]:
            delta(bone, axis, amount * reach(tick, 2 if bone >= 12 else 0))
        # All appendages settle into the existing battle stance on the last tick.
        if tick == len(frames) - 1: pose = deepcopy(rest)
        poses.append([[int(round(x)) for x in bone] for bone in pose])
    animation = mmd.encode_anim(poses, 31, loop_sample=loop, events=events, tol=36, repeats=False)
    out.anims.anims.append(animation); out.anims.table[51] = len(out.anims.anims) - 1
    return finish(model, out, 31, [51])


def main():
    import argparse, json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('species', type=int, choices=[400]); parser.add_argument('model', type=Path); parser.add_argument('out', type=Path)
    args = parser.parse_args(); model = mmd.MMD.load(str(args.model), args.species)
    data, proof = apocalymon(model)
    args.out.parent.mkdir(parents=True, exist_ok=True); args.out.write_bytes(data)
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    main()
