"""Raijinmon's field gaits (species 333): the native Ogremon trunk, arms and swagger, with the two legs planted on the floor.

Raijinmon wears the native rig and programs of Ogremon (a native binding, `native_binding.py`: donor 34). The bound clips keep
the donor's heavy arm swing and trunk roll, but its legs were made for another body and stride: the soles slid over the floor
(78 % of the body's travel in the walk, 115 % tired and 56 % in the run, 297 / 376 / 159 % at worst), the walk was a frantic
22-tick lunge, the idle a brisk 16-tick loop and the run lifted the feet up to 116 units off the floor.

This stage runs after the bind and writes slots 0, 2, 3 and 4 again, one cycle each: the trunk, head and arms (the
drum pack rides the torso) are the donor's own clip resampled to the new cycle length, their swing kept but eased, with the
phase lined up with the new footfalls; the legs come from `quadruped.py`: each sole stands still in the world through its stance
(two-bone solves on the thigh and shin, the sole flat), swings with a lift on a narrow track, and the body sinks to a leg
that cannot reach. Bones 12-14 are the leg on the right (x > 0: thigh, shin, foot) and 15-17 the leg on the left, 2 the torso,
3 the head, 5-7 and 8-10 the arms, 11 the hips. The idle is the donor's, stretched to a calm loop with the feet standing.

Offline: `python -m tools.models.field_animations.raijinmon_gait --source BOUND.MMD --rig REPORT.json --out OUT.MMD`
(BOUND from `native_binding.bind` up to this stage; the build runs it in place).
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
from tools.models.field_animations import quadruped  # noqa: E402

SPECIES = 9333         # a working id for the donor-shaped rig (the species' own id keeps the skeleton the species file lists)
DEG = quadruped.DEG
LEGS = {'RH': (12, 13, 14, 1, False), 'LH': (15, 16, 17, -1, False)}
TRUNK = tuple(range(1, 12))        # the donor's own channels; the legs come from the solves
PELVIS, TORSO, HEAD, HIPS = 1, 2, 3, 11
DONOR = {}        # slot -> the donor's played frames (filled by `build`)


def donor_at(slot, phase):
    """The donor's pose of `slot` at a cycle phase, interpolated between its ticks (angles the short way)."""
    frames = DONOR[slot]
    n = len(frames) - 1
    x = (phase % 1.0) * n
    i = int(x)
    f = x - i
    a, b = frames[i], frames[i + 1 if i + 1 <= n else 0]
    pose = []
    for ba, bb in zip(a, b):
        row = list(ba)
        for k in range(3, 6):
            row[k] = ba[k] + ((bb[k] - ba[k] + 2048) % 4096 - 2048) * f
        for k in range(6, 9):
            row[k] = ba[k] + (bb[k] - ba[k]) * f
        pose.append(row)
    return pose


def body(rig, cfg, phase, pose, hist):
    """The donor's trunk, head and arms at this phase, eased as the gait row says."""
    rest = rig.rest
    d = donor_at(cfg['slot'], phase + cfg['shift'])
    mean = cfg['mean']
    for b in TRUNK:
        for k in range(3, 6):
            pose[b][k] = d[b][k]
        for k in range(6, 9):
            pose[b][k] = rest[b][k]
    bob = d[PELVIS][7] - mean[PELVIS][7]
    pose[PELVIS][7] = rest[PELVIS][7] - cfg['height'] + cfg['bob'] * bob
    for b in TRUNK:      # every donor swing about its own mean is scaled: what the planted legs and the proportions carry
        if b == PELVIS or b not in cfg['swing']:
            continue
        for k in range(3, 6):
            pose[b][k] = mean[b][k] + cfg['swing'][b] * (d[b][k] - mean[b][k])
    for b, deg in cfg['rx'].items():
        pose[b][3] += deg * DEG
    for b in TRUNK:
        for k in range(3, 6):
            pose[b][k] = round(pose[b][k])
    return pose


PROFILE = dict(
    species=SPECIES, name='Raijinmon', source='',
    parents=[-1, 0, 1, 2, 3, 2, 5, 6, 2, 8, 9, 1, 11, 12, 13, 11, 15, 16],
    pelvis=PELVIS, chest=TORSO, neck=None, head=HEAD, tail=(), loose=(),
    legs=LEGS, pole_world=True, rest_plane=True, pole={False: [0.0, 0.0, -1.0]},
    paw_rest={}, sole={False: [0, 0, 0]},      # read off the rig by `prepare`
    reach={'front': 0, 'hind': 0}, fold={False: 60}, clear=2, floor=9, stance_slip=0.2,
    speed_range={0: (0, 0), 2: (15, 31), 3: (10, 20), 4: (35, 52)},
    body=body, gaits={},
)

COMMON = dict(
    kind='walk', snap=False, arc=0.8, clear_ease=0.3, world_ease=True, fold_soft=10, slip=0.0, heel=0, steps=('LH', 'RH'),
    reach={'front': 0, 'hind': 0}, lift={'front': 0, 'hind': 34}, curl={'front': 0, 'hind': 0}, peel={'front': 0, 'hind': 0},
    out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 0}, track={'front': 0, 'hind': 0},
    touchdown={'LH': 0.0, 'RH': 0.5}, bob=1.0, swing={}, rx={}, height=0, shift=0.0,
)
PROFILE['gaits'] = {
    0: dict(COMMON, slot=0, name='idle', ticks=60, speed=0, steps=(), duty={'LH': 1.0, 'RH': 1.0}, bob=2.0, height=8,
            swing={2: 3.0, 3: 3.0, 5: 3.0, 6: 3.0, 7: 3.0, 8: 3.0, 9: 3.0, 10: 3.0, 11: 1.5}),
    2: dict(COMMON, slot=2, name='walk', ticks=30, speed=18, duty={'LH': 0.58, 'RH': 0.58}),
    3: dict(COMMON, slot=3, name='tired walk', ticks=36, speed=12, duty={'LH': 0.56, 'RH': 0.56}, lift={'front': 0, 'hind': 18}, track={'front': 0, 'hind': -14},
            swing={5: 0.7, 6: 0.7, 7: 0.7, 8: 0.7, 9: 0.7, 10: 0.7}),
    4: dict(COMMON, slot=4, name='run', kind='trot', ticks=20, speed=40, duty={'LH': 0.4, 'RH': 0.4}, lift={'front': 0, 'hind': 38}, track={'front': 0, 'hind': -14},
            swing={5: 0.85, 6: 0.85, 7: 0.85, 8: 0.85, 9: 0.85, 10: 0.85}),
}


def prepare(model, rig):
    """Read off the rig how each foot stands in the idle: the direction of its toes in the foot bone's space, and the middle of
    its lowest points (the sole)."""
    PROFILE['paw_rest'], PROFILE['sole'] = {}, {False: [0, 0, 0]}
    r = quadruped.Rig(model, rig, PROFILE)
    for name, (up, lo, paw, side, front) in LEGS.items():
        flat = r.R(r.still, paw)
        PROFILE['paw_rest'][name] = list(quadruped.mv(quadruped.tr(flat), [0.0, 0.0, -1.0]))
        pts = r.verts[paw]
        low = max(quadruped.mv(flat, p)[1] for p in pts)
        near = [p for p in pts if quadruped.mv(flat, p)[1] > low - 12]
        if name == 'RH':
            PROFILE['sole'][False] = [sum(p[i] for p in near) / len(near) for i in range(3)]


def build(data, rig, profile=None):
    """The field gaits written into the bound model -> (bytes, report)."""
    profile = copy.deepcopy(profile or PROFILE)
    profile['source'] = hashlib.sha256(data).hexdigest()
    profile['body'] = body
    n = len(rig)
    exe = mmd.exe()
    for table in (exe.skeleton, exe.bone_count):
        table.extend([None] * (SPECIES + 1 - len(table)))
    exe.skeleton[SPECIES] = rig
    exe.bone_count[SPECIES] = n
    old = mmd.MMD.parse(data, n)
    old.type = SPECIES
    prepare(old, rig)
    profile['sole'], profile['paw_rest'] = PROFILE['sole'], PROFILE['paw_rest']
    DONOR.clear()
    for slot in profile['gaits']:
        DONOR[slot] = animsheet.slot_frames(old, n, slot)[0]
    for slot, cfg in profile['gaits'].items():
        frames = DONOR[slot][:-1]
        cfg['mean'] = [[sum(f[b][k] for f in frames) / len(frames) for k in range(9)] for b in range(n)]
    return quadruped.build(data, rig, profile)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--rig', type=Path, required=True, help='the 333-report.json of the bound model (generated_skeleton)')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--loose', action='store_true')
    a = p.parse_args()
    rig = json.loads(a.rig.read_text())['generated_skeleton']
    profile = copy.deepcopy(PROFILE)
    if a.loose:
        profile.update(floor=999, stance_slip=9)
    data, proof = build(a.source.read_bytes(), rig, profile)
    a.out.write_bytes(data)
    for c in proof['checks']:
        print(c['slot'], c['gait'], c['ticks'], 'speed', c['units_per_tick'], 'floor', c['lowest_point'], 'slip', c['stance_slip'], 'drop', c['body_drop'], 'short', c['unreached'])
    print(proof['storage']['resident_bytes'])


if __name__ == '__main__':
    main()
