"""Mammothmon's field gaits (species 267), written from the paws up (quadruped.py)."""
import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from tools.models.field_animations import quadruped  # noqa: E402

DEG = quadruped.DEG

def secondary(rig, cfg, phase, pose):
    """Trunk, ears and jaw follow the body late: every one is a sine of the cycle phase (two dips a cycle for the nod,
    one for the sway; the trunk only ever lifts forward of its hanging pose, so its tip never sinks deeper than the idle's), each joint further down the chain a little later and wider, so every loop closes on itself."""
    rest = rig.rest
    two = lambda lag: math.sin(4 * math.pi * (phase - lag))
    one = lambda lag: math.sin(2 * math.pi * (phase - lag))
    for k, b in enumerate((15, 16, 17)):
        lag = cfg['trunk_lag'] * (k + 1)
        pose[b][3] = rest[b][3] - round(cfg.get('carry', 0) * (1.0, 0.8, 0.5)[k] * DEG) - round(cfg['trunk'] * (0.6 + 0.4 * k) * (0.5 + 0.5 * two(lag)) * DEG)
        pose[b][5] = rest[b][5] + round(cfg['sway'] * (0.5 + 0.5 * k) * one(lag + 0.1) * DEG)
    for b, side in ((19, 1), (20, -1)):
        pose[b][5] = rest[b][5] + round(side * cfg['ears'] * two(cfg['ear_lag']) * DEG)
        pose[b][3] = rest[b][3] + round(0.5 * cfg['ears'] * two(cfg['ear_lag'] + 0.08) * DEG)
    pose[18][3] = rest[18][3] + round(cfg['jaw'] * two(0.12) * DEG)


PROFILE = dict(
    species=267, name='Mammothmon',
    source='264b775f674f580d9549bb1c44d913322c361a42d05ae5f495a1b2ccfa2e5f9b',
    parents=[-1, 0, 1, 2, 3, 4, 5, 2, 7, 8, 2, 10, 11, 1, 13, 14, 15, 16, 14, 14, 14, 1, 21, 22, 1, 24, 25],
    pelvis=1, chest=2, neck=13, head=14,
    legs={'RF': (24, 25, 26, 1, True), 'LF': (21, 22, 23, -1, True), 'RH': (7, 8, 9, 1, False), 'LH': (10, 11, 12, -1, False)},
    tail=(3, 4, 5, 6), loose=(),
    pole_world=True,
    pole={True: [0, 0, -1], False: [0, 0, -1]},
    sole={True: [0, 75, -15], False: [0, 73, -15]},
    reach={'front': 0, 'hind': 0},
    fold={True: 50, False: 50},
    clear=2,
    speed_range={2: (15, 31), 3: (10, 20), 4: (35, 52)},
    extra=secondary,
    floor=3, stance_slip=0.35, floor_skip=(5, 6, 15, 16, 17),
    gaits={
        2: dict(name='walk', kind='walk', ticks=20, speed=15,
                touchdown={'LH': 0.0, 'LF': 0.25, 'RH': 0.5, 'RF': 0.75},
                duty={'LH': 0.5, 'RH': 0.5, 'RF': 0.5, 'LF': 0.5},
                leg_reach={'RF': -30, 'LF': -30, 'RH': 12, 'LH': 12},
                lift={'front': 30, 'hind': 34}, curl={'front': 8, 'hind': 8}, peel={'front': 8, 'hind': 8},
                reach={'front': 0, 'hind': 0}, out={'front': 4, 'hind': 4}, snap=False, arc=1.0, clear_ease=0.4, fold_soft=12, slip=0.0,
                height=4, tilt=0, chest_up=0, neck=0, nod=1, bob=6, bob2=0.2, pitch=1.5, flex=0.5, roll=3, yaw=2, head=0.6, heel=6, settle=1.5,
                lag=(0.08, 0.16), tail_lag=0.1, tail=6, loose=0, steps=('LH', 'LF', 'RH', 'RF'),
                trunk=9, trunk_lag=0.05, sway=6, ears=4, ear_lag=0.12, jaw=3),
        3: dict(name='tired walk', kind='walk', ticks=24, speed=11,
                touchdown={'LH': 0.0, 'LF': 0.25, 'RH': 0.5, 'RF': 0.75},
                duty={'LH': 0.5, 'RH': 0.5, 'RF': 0.5, 'LF': 0.5},
                leg_reach={'RF': -30, 'LF': -30, 'RH': 12, 'LH': 12},
                lift={'front': 24, 'hind': 28}, curl={'front': 6, 'hind': 6}, peel={'front': 6, 'hind': 6},
                reach={'front': 0, 'hind': 0}, out={'front': 2, 'hind': 2}, snap=False, arc=1.0, clear_ease=0.4, fold_soft=12, slip=0.0,
                height=-14, tilt=0, chest_up=0, neck=3, nod=2, bob=6, bob2=0.2, pitch=2, flex=0.5, roll=4, yaw=2, head=0.3, heel=6, settle=1.5,
                lag=(0.1, 0.2), tail_lag=0.12, tail=4, tail_up=12, loose=0, steps=('LH', 'LF', 'RH', 'RF'),
                trunk=6, carry=10, trunk_lag=0.06, sway=5, ears=2.5, ear_lag=0.14, jaw=2),
        4: dict(name='run', kind='trot', ticks=10, speed=36,
                touchdown={'LF': 0.0, 'RH': 0.0, 'RF': 0.5, 'LH': 0.5},
                duty={'LH': 0.38, 'RH': 0.38, 'RF': 0.38, 'LF': 0.38},
                leg_reach={'RF': -30, 'LF': -30, 'RH': 12, 'LH': 12},
                lift={'front': 30, 'hind': 34}, curl={'front': 8, 'hind': 8}, peel={'front': 8, 'hind': 8},
                reach={'front': 0, 'hind': 0}, out={'front': 6, 'hind': 6}, snap=False, arc=1.0, clear_ease=0.4, fold_soft=12, slip=0.0,
                height=2, tilt=2, chest_up=0, neck=0, nod=1, bob=8, bob2=0.2, pitch=2, flex=0.5, roll=3, yaw=2, head=0.6, heel=6, settle=1.5,
                lag=(0.08, 0.16), tail_lag=0.1, tail=5, tail_up=6, loose=0, steps=('LF', 'RF'),
                trunk=12, carry=5, trunk_lag=0.05, sway=7, ears=6, ear_lag=0.1, jaw=4),
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
    skeleton = json.loads((ROOT / 'content/species/267-mammothmon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
