"""Raidramon's (species 201, named Lighdramon in game) walk, condition walk and run on four planted feet, written from
the paws up (quadruped.py).

Offline authoring only: player builds replay the pinned plain delta. Run with --source and --out, then store the
result with tools/models/edit.py put 201.

The beast carries its head low on a short neck (2-4), the forelegs (5-8, 9-12) hang from the chest (1) with a shoulder
plate (5, 9) holding still above a short upper arm, the hind legs (17-20, 21-24) hang from the hips with a thigh, a
knee ball (18, 22), a hock bone (19, 23) that holds its angle (`links`) and the paw, and the tail (14-16) trails from
the pelvis (13). The imported walk and run crossed the legs through each other and slid the feet over the floor.
These clips are written from the paws up:

- Walk (slot 2): a lateral sequence (left hind, left fore, right hind, right fore) a quarter cycle apart.
- Condition walk (slot 3): the same sequence slower, the body lower and the head carried low.
- Run (slot 4): a trot (diagonal pairs together) with a short flight, the back held firm.

Every foot stands flat and stays put in the world during its stance. The idle and every other program, and the mesh,
stay exact.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import motionstorage  # noqa: E402
from tools.models.field_animations import quadruped  # noqa: E402

PROFILE = dict(
    species=201, name='Raidramon',
    source='8b8ddc1eacd0e0c2d96fa99706d374766e75e99ed30542cfe8202e2cb50b2eeb',
    parents=[-1, 13, 1, 2, 3, 1, 5, 6, 7, 1, 9, 10, 11, 0, 13, 14, 15, 13, 17, 18, 19, 13, 21, 22, 23],
    pelvis=13, chest=1, neck=2, head=3,
    # (upper, lower, paw, side (+1 right), front); the hock bone between the knee ball and the hind foot holds its angle
    legs={'RF': (6, 7, 8, 1, True), 'LF': (10, 11, 12, -1, True), 'RH': (17, 18, 20, 1, False),
          'LH': (21, 22, 24, -1, False)},
    links={20: 19, 24: 23},
    tail=(14, 15, 16), loose=(), pole_world=True,
    pole={True: [0.1, 0, 1], False: [0.5, 0, -1]},      # elbows back, knees out and forward
    sole={True: [0, 49, -60], False: [0, 43, -45]},     # the ball of the foot (paw bone space)
    reach={'front': -45, 'hind': -10},
    fold={True: 70, False: 60},
    clear=3,
    gaits={
        2: dict(name='walk', kind='walk', ticks=14, speed=16,
                touchdown={'LH': 0.0, 'LF': 0.25, 'RH': 0.5, 'RF': 0.75},
                duty={'LH': 0.62, 'RH': 0.62, 'RF': 0.62, 'LF': 0.62},
                lift={'front': 22, 'hind': 18}, curl={'front': 20, 'hind': 10}, peel={'front': 9, 'hind': 8},
                reach={'front': -45, 'hind': -10}, out={'front': 8, 'hind': 6}, snap=False, slip=0.05,
                height=0, tilt=0, chest_up=0, neck=-10, nod=2.5, bob=3, pitch=1, flex=1, roll=2, yaw=2,
                head=0.5, tail=6, tail_up=8, loose=3, steps=('LH', 'LF', 'RH', 'RF')),
        3: dict(name='condition walk', kind='walk', ticks=22, speed=12,
                touchdown={'LH': 0.0, 'LF': 0.25, 'RH': 0.5, 'RF': 0.75},
                duty={'LH': 0.66, 'RH': 0.66, 'RF': 0.66, 'LF': 0.66},
                lift={'front': 16, 'hind': 14}, curl={'front': 12, 'hind': 8}, peel={'front': 7, 'hind': 6},
                reach={'front': -45, 'hind': -10}, out={'front': 6, 'hind': 4}, snap=False, slip=0.05,
                height=-6, tilt=0, chest_up=0, neck=-3, nod=1.5, bob=2.5, pitch=1, flex=0.5, roll=2.5, yaw=1.5,
                head=0.5, tail=4, tail_up=8, loose=1.5, steps=('LH', 'LF', 'RH', 'RF')),
        4: dict(name='run', kind='trot', ticks=10, speed=40,
                touchdown={'LF': 0.0, 'RH': 0.0, 'RF': 0.5, 'LH': 0.5},
                duty={'LH': 0.36, 'RH': 0.36, 'RF': 0.36, 'LF': 0.36},
                lift={'front': 22, 'hind': 20}, curl={'front': 12, 'hind': 10}, peel={'front': 10, 'hind': 10},
                reach={'front': -45, 'hind': -10}, out={'front': 10, 'hind': 8}, snap=True, slip=0.08,
                height=-6, tilt=3, chest_up=0, neck=-8, nod=2, bob=5, pitch=1.5, flex=0.5, roll=2, yaw=1.5,
                head=0.6, tail=8, tail_up=8, loose=6, steps=('LF', 'RF')),
    },
)


def build(data, skeleton):
    result, report = quadruped.build(data, skeleton, PROFILE)
    report['storage'] = motionstorage.require(result, len(skeleton))
    report['output_sha256'] = hashlib.sha256(result).hexdigest()
    return result, report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/201-lighdramon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
