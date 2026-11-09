"""Armadillomon's head carried out of its shell in the field idle, walk, condition walk and run.

Offline authoring only: player builds replay the pinned plain delta. Run with --source and --out, then store the
result with tools/models/edit.py put 185.

The field clips (the idle, and the walk and trot written by armadillomon.py) held the head level or lowered, so the
shell's front rim covered the brow and the head read as sunk into the body. The battle idle carries it higher. These
clips keep every channel and add one constant offset to the head joint: raised 15 degrees, 12 units up and 15
forward, so the face, the brow and the ear fins stand clear of the rim as they do in the battle idle. The offset
is constant, so loops, timing, paws and events stay as they were; the mesh and every other program stay exact.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet  # noqa: E402
import mmd  # noqa: E402
import motioncyclelayer  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402

SOURCE = 'af8301e804da84ebe3c50d6aebb4a9305226961ea13134e1e2656eb5bc89f623'
SPECIES = 185
NB = 23
HEAD = 3
SLOTS = (0, 2, 3, 4)
RAISE = 15           # degrees, about the head joint's own x axis (positive lifts the face)
LIFT = (0, -12, -15)  # units: up and forward in the chest's frame


def build(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('requires the reviewed Armadillomon field model')
    mmd.exe().add_type(SPECIES, skeleton)
    source = mmd.MMD.parse(data, NB)
    source.type = SPECIES
    result = copy.deepcopy(source)
    done = {}
    for slot in SLOTS:
        stream = source.anims.table[slot]
        if stream not in done:
            frames, loop, events = animsheet.slot_frames(source, NB, slot)
            frames = [[[round(v) for v in bone] for bone in pose] for pose in frames]
            for pose in frames:
                pose[HEAD][3] += round(RAISE * 4096 / 360)
                for i in range(3):
                    pose[HEAD][6 + i] += LIFT[i]
            mmd.close_loop(frames, loop)
            done[stream] = len(result.anims.anims)
            result.anims.anims.append(mmd.encode_anim(frames, NB, loop, events, tol=1, repeats=False))
        result.anims.table[slot] = done[stream]
    for anim in result.anims.anims:
        anim.tail = b''
    result.anims.anims, result.anims.table = motioncyclelayer.share_identical_streams(result.anims.anims,
                                                                                    result.anims.table)
    output = result.build()
    effective = mmd.MMD.parse(output, NB)
    assert effective.tmd.build() == source.tmd.build()
    changed = changed_programs(source, effective)
    assert changed == list(SLOTS), changed
    return output, dict(source_sha256=SOURCE, output_sha256=hashlib.sha256(output).hexdigest(), changed_slots=changed,
                        head_raise_degrees=RAISE, head_offset=LIFT, storage=motionstorage.require(output, NB))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/185-armadillomon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
