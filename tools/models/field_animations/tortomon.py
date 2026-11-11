"""Tortomon's field gaits (species 261), written from the paws up (quadruped.py).

Its short, folded legs reach about 70 units of ankle travel, so each foot is planted for only a quarter of the walk
(duty 0.28, 0.26 and 0.17 in the walk, tired walk and run, each leg's window placed on its own hip with `leg_reach`): the sole stays flat and still on the floor while the shin and
knee turn over the ankle, peels off heel first at the end of the stance and swings in a high arc; no tick asks the IK for more than it can reach. The cycles are short
(16, 22 and 10 ticks) and the profile widens the floor and slip bounds (`floor`, `stance_slip`); see tools/models/README.md.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.models.field_animations import quadruped  # noqa: E402

PROFILE = dict(
    species=261, name='Tortomon',
    source='251b1b7cd1550525b69892e8860c27c6edc262662fe0590d7a23a925db628a1c',
    parents=[-1, 0, 1, 2, 3, 1, 5, 6, 1, 8, 9, 1, 11, 12, 1, 14, 15, 1, 17, 18, 19],
    # bone 1 is the shell and carries every limb; the neck root (17) takes the "chest" turns, so the head chain sways on it
    pelvis=1, chest=17, neck=19, head=20,
    legs={'RF': (5, 6, 7, 1, True), 'LF': (8, 9, 10, -1, True), 'RH': (11, 12, 13, 1, False), 'LH': (14, 15, 16, -1, False)},
    tail=(2, 3, 4), loose=(),
    paw_flat={'RF': [0, -18.8, 0], 'LF': [0, 33.2, 0], 'RH': [0, -11.8, 0], 'LH': [0, 26.3, 0]},
    pole_world=True, rest_plane=True,
    pole={True: [0.25, 1, 0], False: [0.4, -1, 1]},
    sole={True: [0, 30, -55], False: [0, 30, -55]},
    reach={'front': -80, 'hind': -10},
    fold={True: 28, False: 28},
    clear=3,
    speed_range={2: (11, 31), 3: (8, 20), 4: (35, 52)},
    floor=30, stance_slip=0.3,
    gaits={
        2: dict(name='walk', kind='walk', ticks=16, speed=12,
                touchdown={'LF': 0.0, 'RH': 0.06, 'RF': 0.34, 'LH': 0.56},
                duty={'LH': 0.28, 'RH': 0.28, 'RF': 0.28, 'LF': 0.28},
                leg_reach={'RF': -8, 'LF': 6, 'RH': -6, 'LH': -2},
                lift={'front': 28, 'hind': 28}, curl={'front': 10, 'hind': 10}, peel={'front': 8, 'hind': 8},
                reach={'front': 0, 'hind': 0}, out={'front': 5, 'hind': 5}, snap=False, arc=1.3, clear_ease=0.5, fold_soft=12, slip=0.0,
                height=2, tilt=0, chest_up=0, neck=0, nod=1, bob=2, pitch=1, flex=0, roll=3, yaw=3, head=0.6,
                lag=(0.08, 0.16), tail_lag=0.1, tail=8, loose=0, steps=('LF', 'RF')),
        3: dict(name='tired walk', kind='walk', ticks=22, speed=9,
                touchdown={'LF': 0.0, 'RH': 0.06, 'RF': 0.5, 'LH': 0.56},
                duty={'LH': 0.26, 'RH': 0.26, 'RF': 0.26, 'LF': 0.26}, leg_reach={'RF': -12, 'RH': -4},
                lift={'front': 22, 'hind': 22}, curl={'front': 6, 'hind': 6}, peel={'front': 6, 'hind': 6},
                reach={'front': 0, 'hind': 0}, out={'front': 0, 'hind': 0}, snap=False, arc=1.3, clear_ease=0.5, fold_soft=12, slip=0.0,
                height=-6, tilt=0, chest_up=0, neck=-8, nod=2, bob=3, pitch=1.5, flex=0, roll=4, yaw=2, head=0.3,
                lag=(0.1, 0.2), tail_lag=0.12, tail=5, loose=0, steps=('LF', 'RF')),
        4: dict(name='run', kind='trot', ticks=10, speed=36,
                touchdown={'LF': 0.0, 'RH': 0.0, 'RF': 0.5, 'LH': 0.5},
                duty={'LH': 0.17, 'RH': 0.17, 'RF': 0.17, 'LF': 0.17},
                leg_reach={'RF': -6, 'LF': 2, 'RH': -8, 'LH': -8},
                lift={'front': 26, 'hind': 26}, curl={'front': 8, 'hind': 8}, peel={'front': 8, 'hind': 8},
                reach={'front': 0, 'hind': 0}, out={'front': 8, 'hind': 8}, snap=False, arc=1.3, clear_ease=0.5, fold_soft=12, slip=0.1,
                height=-4, tilt=2, chest_up=0, neck=6, nod=1, bob=3, pitch=1.5, flex=0, roll=3, yaw=2, head=0.6,
                lag=(0.08, 0.16), tail_lag=0.1, tail=6, tail_up=8, loose=0, steps=('LF', 'RF')),
    },
)


def build(data, skeleton):
    return quadruped.build(data, skeleton, PROFILE)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/261-tortomon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
