"""Pegasusmon's idle, walk, condition walk and run: a winged horse on four planted hooves (quadruped.py).

Offline authoring only: player builds replay the pinned plain delta. Run with --source and --out, then store the
result with tools/models/edit.py put 200.

Pegasusmon (200) is a winged horse: four-bone legs (upper bone, a short joint cap, cannon, hoof: 12-15, 16-19,
20-23, 24-27), the wings on the withers (4-5, 6-7), a three-bone tail (9-11), the neck (2) and the head (3). The
imported idle stood with the right foreleg raised and swung the hindquarters from side to side; its walk and run
crossed the legs over each other and slid the hooves (slip 37-144 % of the body's travel). Every field clip is
written again:

- Idle (slot 0): square on four planted hooves (the right foreleg the left's mirror), 24 ticks of slow breathing:
  the barrel rises and falls, the neck and head answer late, the tail swishes and the wings settle on the back. The
  hindquarters do not sway.
- Walk (slot 2): the horse's four-beat walk (left hind, left fore, right hind, right fore) a quarter cycle apart,
  62 % stance, 16 ticks at 17 units per tick, the head nodding with each step.
- Condition walk (slot 3): the same sequence slower, lower and heavier, 22 ticks at 12 units per tick.
- Run (slot 4): a gallop (hind pair, then the fore pair) with a gathered flight, 12 ticks at 42 units per tick, the
  hooves folding up under the body in the air, the neck reaching forward and the wings lifting with the bound.

The short joint caps (13, 17, 21, 25) keep their standing angle (quadruped.py `links`). The mesh and every other
program stay exact.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet  # noqa: E402
import mmd  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models.field_animations import quadruped  # noqa: E402

SOURCE = '6d1b4b5f8efe4325cc71c997ec941decc50136fc11e7bbdc58f23fbeb64d653e'
DEG = quadruped.DEG
IDLE_TICKS = 24
# the right foreleg is raised in the imported idle: it stands as the left one's mirror
MIRRORED = ((12, 16), (13, 17), (14, 18), (15, 19))

PROFILE = dict(
    species=200, name='Pegasusmon',
    parents=[-1, 8, 1, 2, 1, 4, 1, 6, 0, 8, 9, 10, 1, 12, 13, 14, 1, 16, 17, 18, 8, 20, 21, 22, 8, 24, 25, 26],
    pelvis=8, chest=1, neck=2, head=3,
    # (upper, lower, paw, side (+1 right), front); the cap between the upper bone and the cannon holds its angle
    legs={'RF': (12, 14, 15, 1, True), 'LF': (16, 18, 19, -1, True), 'RH': (20, 22, 23, 1, False),
          'LH': (24, 26, 27, -1, False)},
    links={14: 13, 18: 17, 22: 21, 26: 25},
    tail=(9, 10, 11), loose=((4, 1), (6, -1)),
    pole={True: [0.1, 0, 1], False: [0.1, 0, 1]},     # knees and hocks fold backwards
    sole={True: [0, 31, -28], False: [0, 31, -28]},   # the toe of the hoof (hoof bone space)
    reach={'front': -30, 'hind': -19},
    fold={True: 80, False: 80},
    clear=3,
    gaits={
        2: dict(name='walk', kind='walk', ticks=16, speed=17,
                touchdown={'LH': 0.0, 'LF': 0.25, 'RH': 0.5, 'RF': 0.75},
                duty={'LH': 0.62, 'RH': 0.62, 'RF': 0.62, 'LF': 0.62},
                lift={'front': 40, 'hind': 30}, curl={'front': 60, 'hind': 40}, peel={'front': 25, 'hind': 20},
                reach={'front': 0, 'hind': 0}, out={'front': 20, 'hind': 10}, snap=False, slip=0.05,
                height=-12, tilt=0, chest_up=0, neck=0, nod=3, bob=3, pitch=1, flex=1, roll=1.5, yaw=2,
                head=0.4, tail=5, tail_up=16, loose=3, steps=('LH', 'LF', 'RH', 'RF')),
        3: dict(name='condition walk', kind='walk', ticks=22, speed=12,
                touchdown={'LH': 0.0, 'LF': 0.25, 'RH': 0.5, 'RF': 0.75},
                duty={'LH': 0.66, 'RH': 0.66, 'RF': 0.66, 'LF': 0.66},
                lift={'front': 28, 'hind': 22}, curl={'front': 45, 'hind': 30}, peel={'front': 18, 'hind': 15},
                reach={'front': 0, 'hind': 0}, out={'front': 10, 'hind': 5}, snap=False, slip=0.05,
                height=-18, tilt=0, chest_up=0, neck=0, nod=2, bob=2.5, pitch=1, flex=1, roll=2.5, yaw=1.5,
                head=0.4, tail=3, tail_up=22, loose=1.5, steps=('LH', 'LF', 'RH', 'RF')),
        4: dict(name='run', kind='gallop', ticks=12, speed=42,
                touchdown={'LH': 0.0, 'RH': 0.1, 'RF': 0.42, 'LF': 0.54},
                duty={'LH': 0.3, 'RH': 0.3, 'RF': 0.3, 'LF': 0.3},
                lift={'front': 70, 'hind': 50}, curl={'front': 80, 'hind': 50}, peel={'front': 35, 'hind': 30},
                reach={'front': 0, 'hind': 10}, out={'front': 40, 'hind': 15}, snap=True, slip=0.08,
                height=-8, tilt=0, chest_up=-3, neck=5, nod=2, bob=12, pitch=6, flex=5, roll=1.5, yaw=1.5,
                head=0.6, tail=12, tail_up=15, loose=8, steps=('LH', 'RF')),
    },
)


def mirrored(angles):
    return [angles[0], -angles[1], -angles[2]]


def standing_pose(model, n):
    pose = copy.deepcopy(animsheet.slot_frames(model, n, 0)[0][0])
    for right, left in MIRRORED:
        pose[right][3:6] = mirrored(pose[left][3:6])
    pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
    return pose


def with_idle(model, n, frames, events):
    out = copy.deepcopy(model)
    out.anims.anims[model.anims.table[0]] = mmd.encode_anim(frames, n, loop_sample=0, events=events, tol=1)
    return out


def breathe(rig, rest, phase, history):
    """One tick of the idle: the barrel breathing, neck, head, tail and wings answering late, the hooves planted."""
    pose = copy.deepcopy(rest)
    wave = math.sin(2 * math.pi * phase)
    pose[8][7] = rest[8][7] + 0.8 * wave                                      # the barrel sinks and rises
    pose[1][3] = rest[1][3] + 0.5 * DEG * math.sin(2 * math.pi * phase - 0.4)
    pose[2][3] = rest[2][3] - 1.5 * DEG * math.sin(2 * math.pi * phase - 0.9)
    pose[3][3] = rest[3][3] + 2.0 * DEG * math.sin(2 * math.pi * phase - 1.4)
    for k, b in enumerate((9, 10, 11)):
        pose[b][4] = rest[b][4] + (3 + 2 * k) * DEG * math.sin(2 * math.pi * phase - 1.0 - 0.6 * k)
    for b, side in ((4, 1), (6, -1)):
        pose[b][5] = rest[b][5] + side * 1.5 * DEG * math.sin(2 * math.pi * phase - 0.7)
    for name, (upper, lower, paw, side, front) in PROFILE['legs'].items():
        world = [r[:3] for r in rig.still[paw][:3]]
        wrist = [rig.still[paw][i][3] for i in range(3)]
        wrist[1] -= max(0.0, rig.lowest(paw, world, wrist) + 1)
        rotation, short = rig.solve(pose, name, wrist, history)
        assert short <= 0.5, (name, short)
        quadruped.set_rot(pose, paw, quadruped.mul(quadruped.tr(rotation), world), history)
    return pose


def build(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError("Pegasusmon's field clips require the reviewed source")
    n = len(skeleton)
    sid = PROFILE['species']
    mmd.exe().skeleton[sid] = skeleton
    mmd.exe().bone_count[sid] = n
    old = mmd.MMD.parse(data, n)
    old.type = sid
    source_events = animsheet.slot_frames(old, n, 0)[2]
    events = [(t, kind, e) for t, kind, e in source_events if kind == 'tex' and t == 0]
    rest = standing_pose(old, n)
    still = with_idle(old, n, [rest, rest], events)          # the standing pose the legs are solved from
    rig = quadruped.Rig(still, skeleton, dict(PROFILE, source=None))
    history = {}
    frames = [breathe(rig, rest, t / IDLE_TICKS, history) for t in range(IDLE_TICKS)]
    frames.append(copy.deepcopy(frames[0]))
    frames = [[[round(v) for v in b] for b in p] for p in frames]
    idled = with_idle(old, n, frames, events).build()
    walked, report = quadruped.build(idled, skeleton, dict(PROFILE, source=hashlib.sha256(idled).hexdigest()))
    actual = mmd.MMD.parse(walked, n)
    actual.type = sid
    played = animsheet.slot_frames(actual, n, 0)[0]
    floor = quadruped._floor(rig, played)
    assert floor <= quadruped.FLOOR, floor
    idle_slots = [s for s, i in enumerate(old.anims.table) if i == old.anims.table[0]]
    changed = changed_programs(old, actual)
    assert changed == sorted(set(report['changed_slots'] + idle_slots)), changed
    assert actual.tmd.build() == old.tmd.build()
    report.update(source_sha256=SOURCE, output_sha256=hashlib.sha256(walked).hexdigest(), changed_slots=changed,
                  idle=dict(ticks=IDLE_TICKS, slots=idle_slots, lowest_point=round(floor, 2), planted_hooves=True,
                            hips_still=True),
                  storage=motionstorage.require(walked, n))
    return walked, report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/200-pegasusmon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
