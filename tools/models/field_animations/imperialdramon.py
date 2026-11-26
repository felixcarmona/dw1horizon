"""Imperialdramon's walk, condition walk and run on all fours, written from the paws up (quadruped.py).

Offline authoring only: player builds replay the pinned plain delta. Run with --source and --out, then store the
result with tools/models/edit.py put 192.

Imperialdramon (192, Dragon Mode, from Digimon Card Battle) stands on four limbs: the arms (11-13, 14-16) reach the
floor in front of the chest with the hands' claws forward, the short hind legs (21-23, 24-26) stand under the hips
with the feet turned out, the pair of wings rides on the chest (5-7, 8-10) and the tail (18-20) curls up behind.
The imported walk and run swung every limb on its own, the hands thrown up past the head and the feet slid over
the floor (slip 98-128 % of the body's travel). These clips are written from the paws up:

The hips sit right behind the shoulders, so the long forearms and the hind legs of a side share little room: the
knees bend out rather than forward, a lifted arm's elbow swings out past the thigh (`swing_pole`), the hands stand
well ahead and the feet well back, and each hand lands just before the foot behind it, so the two legs of a side
swing together and do not pass through each other. The long blades along the forearms always point ahead (`aim`:
rolled with the swinging elbow they swept through the low head), and the hands swing wide of the head on the way
forward (`wide`).

- Walk (slot 2): left fore and hind, then right fore and hind, 55 % stance, 16 ticks at 15 units per tick; the
  body dips onto each landing pair (two dips a cycle, 24 units at the pelvis), pitches with them and rolls over the
  supporting side, the head steadies, the tail and wings follow late.
- Condition walk (slot 3): the same sequence slower, 22 ticks at 12 units per tick, the head carried low and still
  while the body dips (18 units).
- Run (slot 4): a gallop (hind pair, then the fore pair) with a gathered flight, 12 ticks at 46 units per tick: the
  body sinks onto the fore landing and is thrown up through the push-off (44 units), pitching about 10 degrees,
  the head held up and countering part of it and the wings lifting with each bound.

Each hand and foot stands at its own idle angle (the hands a little and the feet well turned out). The idle (slot 0)
keeps its crouch and roar with every hand and foot planted where it stands at the first tick. Every other program
and the mesh stay exact.
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
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models.field_animations import quadruped  # noqa: E402

CLAWS = {20: (21, 22), 25: (26, 27)}      # each fore paw's two sibling claw bones ride its paw bone


class ClawRig(quadruped.Rig):
    """The claw bones hang from the forearm beside the paw bone: their points count as the paw's for the sole and the
    floor, and `slave` carries them with the paw."""

    def __init__(self, model, skeleton, profile):
        super().__init__(model, skeleton, profile)
        for paw, sides in CLAWS.items():
            for c in sides:
                off = [(self.rest[c][i] - self.rest[paw][i]) * self.S for i in (6, 7, 8)]
                self.verts[paw] = self.verts[paw] + [quadruped.add(v, off) for v in self.verts.pop(c)]


def slave(rig, cfg, phase, pose):
    """Each claw bone turns with its paw about the paw's origin (their own turns stay at rest)."""
    for paw, sides in CLAWS.items():
        turn = mmd.rot_matrix(*pose[paw][3:6])
        for c in sides:
            off = [rig.rest[c][i] - rig.rest[paw][i] for i in (6, 7, 8)]
            pose[c][3:6] = list(pose[paw][3:6])
            pose[c][6:9] = [pose[paw][6 + i] + v for i, v in enumerate(quadruped.mv(turn, off))]


quadruped.Rig = ClawRig

PROFILE = dict(
    species=192, name='Imperialdramon',
    source='a8cd12ea872b30c83574f3d4f481d7115dadf1c8a9185a48a06e9a9f4f945fd2',
    parents=[b[1] for b in json.loads((ROOT / 'content/species/192-imperialdramon.json').read_text())['model']['skeleton']],
    pelvis=1, chest=2, neck=28, head=30,
    # (upper, lower, paw, side (+1 right), front)
    legs={'RF': (23, 24, 25, 1, True), 'LF': (18, 19, 20, -1, True), 'RH': (6, 7, 8, 1, False),
          'LH': (9, 10, 11, -1, False)},
    tail=(3, 4, 5), loose=(),
    # the paws stand as the right ones rest (turned out), the left ones mirrored
    paw_rest={'RF': [0, 0, -1], 'RH': [0, 0, -1]}, mirror_paws=True,
    pole={True: [0.2, 0, 1], False: [1, 0, -0.6]},
    swing_pole={True: [1, 0, 0.5]},
    aim={True: [0, 0, -1]},
    sole={True: [0, 46, -115], False: [0, 0, -100]},
    reach={'front': -215, 'hind': -25},
    fold={True: 80, False: 70},
    clear=8, extra=slave, floor_skip=(14, 17),
    gaits={
        2: dict(name='walk', kind='walk', ticks=12, speed=15,
                touchdown={'LH': 0.0, 'LF': 0.93, 'RH': 0.5, 'RF': 0.43},
                duty={'LH': 0.55, 'RH': 0.55, 'RF': 0.55, 'LF': 0.55},
                lift={'front': 70, 'hind': 34}, curl={'front': 25, 'hind': 25}, peel={'front': 20, 'hind': 20},
                reach={'front': 0, 'hind': 65}, out={'front': 25, 'hind': 10}, wide={'front': 40}, snap=False,
                slip=0.05,
                height=0, tilt=0, chest_up=0, neck=2, nod=1.5, bob=12, high=0.2, pitch=2.5, flex=1.5, roll=2.5,
                yaw=2.5, head=0.5, tail=8, tail_up=10, loose=6, steps=('LF', 'LH', 'RF', 'RH')),
        3: dict(name='condition walk', kind='walk', ticks=16, speed=12,
                touchdown={'LH': 0.0, 'LF': 0.93, 'RH': 0.5, 'RF': 0.43},
                duty={'LH': 0.55, 'RH': 0.55, 'RF': 0.55, 'LF': 0.55},
                lift={'front': 50, 'hind': 26}, curl={'front': 20, 'hind': 20}, peel={'front': 15, 'hind': 15},
                reach={'front': 0, 'hind': 65}, out={'front': 15, 'hind': 6}, wide={'front': 40}, snap=False,
                slip=0.05,
                height=0, tilt=2, chest_up=0, neck=-6, nod=1, bob=9, high=0.25, pitch=2, flex=1, roll=3, yaw=2,
                head=0.5, tail=4, tail_up=10, loose=2, steps=('LF', 'LH', 'RF', 'RH')),
        4: dict(name='run', kind='gallop', ticks=10, speed=40,
                touchdown={'LH': 0.0, 'RH': 0.1, 'RF': 0.42, 'LF': 0.54},
                duty={'LH': 0.3, 'RH': 0.3, 'RF': 0.3, 'LF': 0.3},
                lift={'front': 70, 'hind': 20}, curl={'front': 15, 'hind': 25}, peel={'front': 30, 'hind': 25},
                reach={'front': 60, 'hind': 80}, out={'front': 50, 'hind': 0}, wide={'front': 70}, snap=True,
                slip=0.08, height=0, tilt=4, chest_up=-2, neck=-10, nod=1.5, bob=20, high=0.8, pitch=10, flex=6,
                roll=1.5, yaw=1.5, head=0.8, tail=6, tail_up=10, loose=0, steps=('LH', 'RF')),
    },
)


def plant_idle(data, skeleton):
    """The idle keeps its crouch and roar; every hand and foot stays where it stands at the first tick (the imported
    crouch pushed the hind feet up to 44 units into the floor)."""
    n = len(skeleton)
    old = mmd.MMD.parse(data, n)
    old.type = PROFILE['species']
    new = copy.deepcopy(old)
    rig = quadruped.Rig(old, skeleton, PROFILE)
    frames, loop, events = animsheet.slot_frames(old, n, 0)
    poses = copy.deepcopy(frames)
    history = {}
    spots = {}
    for name, (upper, lower, paw, side, front) in PROFILE['legs'].items():
        still = [r[:3] for r in rig.still[paw][:3]]
        origin = [rig.still[paw][i][3] for i in range(3)]
        spots[name] = quadruped.add(origin, quadruped.mv(still, rig.sole(front, name)))
    for pose in poses:
        for name, (upper, lower, paw, side, front) in PROFILE['legs'].items():
            world = rig.paw(front, 0, name)
            wrist = quadruped.sub(spots[name], quadruped.mv(world, rig.sole(front, name)))
            wrist[1] = -PROFILE['clear'] - rig.lowest(paw, world, [0, 0, 0])
            rotation, short = rig.solve(pose, name, wrist, history, None, PROFILE['aim'].get(front))
            assert short <= 0.5, (name, short)
            quadruped.set_rot(pose, paw, quadruped.mul(quadruped.tr(rotation), world), history)
        slave(rig, None, 0, pose)
    poses = [[[round(v) for v in b] for b in p] for p in poses]
    poses[-1] = copy.deepcopy(poses[0])
    index = old.anims.table[0]
    new.anims.anims[index] = mmd.encode_anim(poses, n, loop_sample=loop, events=events, tol=1)
    result = new.build()
    actual = mmd.MMD.parse(result, n)
    actual.type = PROFILE['species']
    changed = [s for s, i in enumerate(old.anims.table) if i == index]
    assert changed_programs(old, actual) == changed, changed_programs(old, actual)
    floor = quadruped._floor(rig, animsheet.slot_frames(actual, n, 0)[0])
    assert floor <= quadruped.FLOOR, floor
    return result, dict(changed_slots=changed, lowest_point=round(floor, 2), planted_paws=True)


def build(data, skeleton):
    walked, report = quadruped.build(data, skeleton, PROFILE)
    result, idle = plant_idle(walked, skeleton)
    report['idle'] = idle
    report['changed_slots'] = sorted(set(report['changed_slots'] + idle['changed_slots']))
    report['storage'] = motionstorage.require(result, len(skeleton))
    report['output_sha256'] = hashlib.sha256(result).hexdigest()
    return result, report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/192-imperialdramon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
