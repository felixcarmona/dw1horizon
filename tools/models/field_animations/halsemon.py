"""Halsemon's walk, condition walk and run on four planted feet, written from the paws up (quadruped.py).

Offline authoring only: player builds replay the pinned plain delta. Run with --source and --out, then store the
result with tools/models/edit.py put 196.

Halsemon (196) is an eagle-headed beast on four legs: the forelegs (12-14, 15-17) hang from the chest with the
talons forward, the hind legs (18-21, 22-25) bend like a dog's with a short hock bone (20, 24) above the foot, the
wings ride on the helmet (4-7) and the tail (10-11) trails behind. The imported walk and run threw the feet across
each other and slid them over the floor (slip 131-181 % of the body's travel), and the run bounded like a cat with
the back folding and unfolding. These clips are written from the paws up:

- Walk (slot 2): a lateral sequence (left hind, left fore, right hind, right fore) a quarter cycle apart, 62 %
  stance, 16 ticks at 17 units per tick; the head nods with each step and the tail follows late.
- Condition walk (slot 3): the same sequence slower and lower, 22 ticks at 12 units per tick, the head carried low.
- Run (slot 4): a trot (diagonal pairs together) with a short flight, 12 ticks at 40 units per tick, the back held
  firm, the body pitched a little forward and the wings lifting with each stride.

Every foot stands flat at its own idle angle (the toes turned a little out) and the short hock bones keep their
standing angle (`links`). The idle and every other program, and the mesh, stay exact.
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
    species=196, name='Halsemon',
    source='3a2a21cafd327b548d5bfd9ccd299c11e63541b8883b037a4865b7c5d5c9f392',
    parents=[-1, 3, 1, 8, 1, 4, 1, 6, 9, 0, 9, 10, 8, 12, 13, 8, 15, 16, 9, 18, 19, 20, 9, 22, 23, 24],
    pelvis=9, chest=8, neck=3, head=1,
    # (upper, lower, paw, side (+1 right), front); the hock bone between the shin and the foot holds its angle
    legs={'RF': (15, 16, 17, 1, True), 'LF': (12, 13, 14, -1, True), 'RH': (22, 23, 25, 1, False),
          'LH': (18, 19, 21, -1, False)},
    links={25: 24, 21: 20},
    tail=(10, 11), loose=((4, -1), (6, 1)),
    # the feet stand with the toes turned a little out, each side its own way
    paw_flat={'RF': [-0.3, -16.8, -0.2], 'LF': [-0.1, 17.0, 0.1], 'RH': [-0.2, -14.6, 0.2],
              'LH': [-0.1, 14.4, -0.2]},
    pole={True: [0.8, 0, 1], False: [0.8, 0, -1]},     # elbows out and back, knees out and forward
    sole={True: [0, 32, -70], False: [0, 39, -70]},    # the ball of the foot (paw bone space)
    reach={'front': -12, 'hind': 6},                   # the ball's place ahead of the shoulder / hip, mid-stance
    fold={True: 80, False: 70},
    clear=3,
    gaits={
        2: dict(name='walk', kind='walk', ticks=16, speed=17,
                touchdown={'LH': 0.0, 'LF': 0.25, 'RH': 0.5, 'RF': 0.75},
                duty={'LH': 0.62, 'RH': 0.62, 'RF': 0.62, 'LF': 0.62},
                lift={'front': 22, 'hind': 18}, curl={'front': 20, 'hind': 10}, peel={'front': 18, 'hind': 15},
                reach={'front': 0, 'hind': 0}, out={'front': 12, 'hind': 8}, snap=False, slip=0.05,
                height=-6, tilt=0, chest_up=0, neck=0, nod=2.5, bob=3, pitch=1, flex=1, roll=2, yaw=2,
                head=0.5, tail=6, loose=3, steps=('LH', 'LF', 'RH', 'RF')),
        3: dict(name='condition walk', kind='walk', ticks=22, speed=12,
                touchdown={'LH': 0.0, 'LF': 0.25, 'RH': 0.5, 'RF': 0.75},
                duty={'LH': 0.66, 'RH': 0.66, 'RF': 0.66, 'LF': 0.66},
                lift={'front': 16, 'hind': 14}, curl={'front': 15, 'hind': 8}, peel={'front': 14, 'hind': 12},
                reach={'front': 0, 'hind': 0}, out={'front': 8, 'hind': 5}, snap=False, slip=0.05,
                height=-12, tilt=2, chest_up=0, neck=-5, nod=1.5, bob=2.5, pitch=1, flex=0.5, roll=2.5, yaw=1.5,
                head=0.5, tail=4, loose=1.5, steps=('LH', 'LF', 'RH', 'RF')),
        4: dict(name='run', kind='trot', ticks=12, speed=40,
                touchdown={'LF': 0.0, 'RH': 0.0, 'RF': 0.5, 'LH': 0.5},
                duty={'LH': 0.36, 'RH': 0.36, 'RF': 0.36, 'LF': 0.36},
                lift={'front': 24, 'hind': 22}, curl={'front': 22, 'hind': 15}, peel={'front': 22, 'hind': 18},
                reach={'front': 0, 'hind': 0}, out={'front': 25, 'hind': 12}, snap=True, slip=0.08,
                height=-4, tilt=3, chest_up=0, neck=3, nod=2, bob=5, pitch=1.5, flex=0.5, roll=2, yaw=1.5,
                head=0.6, tail=8, loose=6, steps=('LF', 'RF')),
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
    skeleton = json.loads((ROOT / 'content/species/196-halsemon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
