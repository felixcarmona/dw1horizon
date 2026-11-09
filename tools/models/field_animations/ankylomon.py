"""Ankylomon's run, a heavy trot written from the paws up (quadruped.py).

Offline authoring only: player builds replay the pinned plain delta. Run with --source and --out, then store the
result with tools/models/edit.py put 189.

The imported run threw the legs out sideways and swung the paws far over the ground, the sole of each paw facing
backwards half the time. This clip replaces only the run (slot 4); the idle and the walk, which the partner code
plays at their native 73-frame length, stay as they are.

Ankylomon's paws are bound with their soles along the bone's +z and the toes along +y, so they stand flat at a
world pitch of -90 degrees (`paw_flat`). The run is a trot, diagonal pairs planting in turn, 12 ticks at 38 units
per tick (the speed the pace pass gave the old run). The shell bobs twice a cycle and rolls over the supporting
pair, the head steadies against it and the club tail follows late.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.models.field_animations import quadruped  # noqa: E402

PROFILE = dict(
    species=189, name='Ankylomon',
    source='d2ff04b10d4951092c7279ede9374e8d1cebbb5a10333705471bd5e506694d81',
    parents=[-1, 0, 1, 2, 2, 4, 5, 2, 7, 8, 1, 10, 11, 1, 13, 14, 1, 16, 17],
    pelvis=1, chest=2, neck=None, head=3,
    # (upper, lower, paw, side (+1 right), front)
    legs={'RF': (4, 5, 6, 1, True), 'LF': (7, 8, 9, -1, True), 'RH': (10, 11, 12, 1, False), 'LH': (13, 14, 15, -1, False)},
    tail=(16, 17, 18), loose=(),
    paw_flat={True: [-90, 0, 0], False: [-90, 0, 0]},
    pole={True: [1, -0.3, 0.3], False: [0.6, -0.4, -0.6]},
    sole={True: [0, 70, 26], False: [0, 75, 23]},
    reach={'front': -70, 'hind': -75},
    fold={True: 40, False: 40},
    clear=3,
    gaits={
        4: dict(name='run', kind='trot', ticks=12, speed=38,
                touchdown={'LF': 0.0, 'RH': 0.0, 'RF': 0.5, 'LH': 0.5},
                duty={'LH': 0.32, 'RH': 0.32, 'RF': 0.32, 'LF': 0.32},
                lift={'front': 26, 'hind': 22}, curl={'front': 30, 'hind': 25}, peel={'front': 25, 'hind': 20},
                reach={'front': 0, 'hind': 0}, out={'front': 10, 'hind': 5}, snap=True, slip=0.1,
                height=6, tilt=0, chest_up=0, neck=0, nod=2, bob=3, pitch=1.5, flex=1, roll=3, yaw=2.5, head=0.6,
                tail=6, tail_up=10, loose=0, steps=('LF', 'RF')),
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
    skeleton = json.loads((ROOT / 'content/species/189-ankylomon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
