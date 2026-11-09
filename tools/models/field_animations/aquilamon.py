"""Aquilamon's field idle, walk and run kept in flight, at a low hover.

Offline authoring only: player builds replay the pinned plain delta. Run with --source and --out, then store the
result with tools/models/edit.py put 188.

The import kept one 89-tick flight clip in the idle, walk, condition walk and run: a crouch with the wings raised, one
big downstroke and a long glide down. The flap reads well, but the downstroke threw the whole bird about 300 units up
and the glide brought it back to the floor, so it climbed far above the camera's reach and then stood on its talons.
Native field flyers hover low and bob a little: Airdramon's lowest point stays 30-50 units off the floor in its idle
and 80-140 in its walk, Birdramon's within about 130 units.

These clips keep every channel of that flight as it was (wings, head, tail, legs tucked, body pitch) and change only
the body's height and the clip's pace:

- Idle (slots 0, 1, 18): the original pace (one beat in 89 ticks), the climb scaled to 15% so it is a gentle bob,
  the whole bird held up so its lowest point never comes nearer than 50 units to the floor.
- Walk (slot 2): the beat played 1.25 times faster (71 ticks), the climb scaled to 20%, 22 units per tick as before.
- Condition walk (slot 3): the original pace, the climb scaled to 15%, 21 units per tick as before.
- Run (slot 4): the beat played twice as fast (44 ticks), the climb scaled to 22%, the body pitched 12 degrees further
  nose-down, 44 units per tick as before.

The battle programs and the mesh stay exact.
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
from motiontailspace import interpolate_pose  # noqa: E402

SOURCE = '9a6fe32113ecef36c603d6a91535b0916d4c575748b1837fff6f962d4e773a4c'
SPECIES = 188
NB = 22
BODY = 1

# slot: (pace, share of the original climb, extra nose-down pitch in degrees, clearance of the lowest point)
FLIGHT = {
    0: (1.0, 0.15, 0, 20),
    2: (1.25, 0.20, 0, 30),
    3: (1.0, 0.15, 0, 20),
    4: (2.0, 0.22, 12, 30),
}
IDLES = (0, 1, 18)


class Bird:
    def __init__(self, model):
        self.m = model
        self.sk = mmd.exe().skeleton[SPECIES]
        self.verts = {b: [v[:3] for v in model.tmd.obj_verts(o)] for b, (o, _) in enumerate(self.sk) if o >= 0}

    def floor(self, pose):
        """The lowest point of the mesh (y grows downwards; 0 is the floor)."""
        p = [list(v) for v in pose]
        p[0] = [4096, 4096, 4096] + p[0][3:6] + [0, 0, 0]
        W = mmd.bone_matrices(self.m, p)
        return pose[0][7] + max(W[b][1][3] + sum(W[b][1][j] * v[j] for j in range(3))
                                for b in self.verts for v in self.verts[b])


def resample(frames, pace):
    """The same cycle played `pace` times faster."""
    n = len(frames) - 1
    ticks = round(n / pace)
    out = []
    for t in range(ticks + 1):
        at = t * n / ticks
        left = min(int(at), n - 1)
        out.append([list(v) for v in interpolate_pose(frames[left], frames[left + 1], round((at - left) * 4096))])
    return out


def flight(bird, frames, pace, climb, pitch, clearance):
    n = len(frames) - 1
    speed = frames[-1][0][8] / n
    rest = frames[0][BODY][7]
    out = resample(frames, pace)
    for t, pose in enumerate(out):
        pose[0][8] = speed * t
        pose[BODY][7] = rest + climb * (pose[BODY][7] - rest)
        pose[BODY][3] -= pitch * 4096 / 360
    lift = max(bird.floor(p) for p in out) + clearance
    for pose in out:
        pose[BODY][7] -= lift
    return [[[round(x) for x in v] for v in pose] for pose in out]


def build(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('requires the imported Aquilamon these clips were written for')
    mmd.exe().add_type(SPECIES, skeleton)
    source = mmd.MMD.parse(data, NB)
    source.type = SPECIES
    bird = Bird(source)
    result = copy.deepcopy(source)
    streams, checks = {}, []
    for slot, (pace, climb, pitch, clearance) in FLIGHT.items():
        frames, loop, events = animsheet.slot_frames(source, NB, slot)
        assert loop == 0 and not events, (slot, loop, events)
        before = [bird.floor(p) for p in frames]
        out = flight(bird, frames, pace, climb, pitch, clearance)
        after = [bird.floor(p) for p in out]
        mmd.close_loop(out, 0)
        streams[slot] = len(result.anims.anims)
        result.anims.anims.append(mmd.encode_anim(out, NB, 0, [], tol=1))
        checks.append(dict(slot=slot, ticks=len(out) - 1, speed=round(out[-1][0][8] / (len(out) - 1), 1),
                           lowest_point_before=[round(-max(before)), round(-min(before))],
                           lowest_point_after=[round(-max(after)), round(-min(after))]))
    for slot in IDLES:
        result.anims.table[slot] = streams[0]
    for slot in (2, 3, 4):
        result.anims.table[slot] = streams[slot]
    for anim in result.anims.anims:
        anim.tail = b''
    result.anims.anims, result.anims.table = motioncyclelayer.share_identical_streams(result.anims.anims,
                                                                                    result.anims.table)
    output = result.build()
    effective = mmd.MMD.parse(output, NB)
    assert effective.tmd.build() == source.tmd.build()
    changed = changed_programs(source, effective)
    return output, dict(source_sha256=SOURCE, output_sha256=hashlib.sha256(output).hexdigest(), changed_slots=changed,
                        checks=checks, storage=motionstorage.require(output, NB))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/188-aquilamon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
