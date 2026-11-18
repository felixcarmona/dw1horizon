"""Maildramon's field gaits (species 324): the native Unimon trunk, neck, wings and tail, with the four legs planted on the floor.

Maildramon wears the native rig and programs of Unimon (a native binding, `native_binding.py`: donor 33), reshaped to
Digimon World's proportions by the chibi stage. The bound clips keep the donor's lively trunk, wings and tail but its legs
were made for another body: the soles slid over the floor (68 % of the body's travel in the walk, 47 % tired and 95 % in the
run, 257 and 400 % at worst), the tired walk was as fast as the walk, the horn pointed backwards with the head hung
forward, the tail stuck up in the run and the trunk jumped (3.4 times the usual step between two ticks in the run).

This stage runs after the chibi stage (so it plants the final leg lengths) and writes slots 2, 3 and 4 again, one cycle
each: the trunk (pelvis height, chest, hips, neck, head, wings and tail) is the donor's own clip, resampled to the new
cycle length, its pelvis bob and its neck and tail swing toned down to what planted legs can carry, with the neck, head
and tail lifted or lowered where the donor's carriage read wrong; the legs come from `quadruped.py`: each sole stands still
in the world through its stance (two-bone solves on the thigh and shin, the claws flat on the floor), swings with a lift,
and the body sinks to a leg that cannot reach. Bones 8-11 and 12-15 are the front legs (thigh, shin, foot, claws), 17-20
and 21-24 the hind legs, 2 the chest, 16 the hips, 3-5 the neck and head, 6 and 7 the wings and 25-26 the tail.
The idle (slot 0) is the donor's and stays.

Offline: `python -m tools.models.field_animations.maildramon_gait --source BOUND.MMD --rig REPORT.json --out OUT.MMD`
(BOUND from `native_binding.bind` up to the chibi stage; the build runs it in place).
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

SPECIES = 9324         # a working id for the donor-shaped rig (the species' own id keeps the skeleton the species file lists)
DEG = quadruped.DEG
LEGS = {'RF': (8, 9, 10, 1, True), 'LF': (12, 13, 14, -1, True), 'RH': (17, 18, 19, 1, False), 'LH': (21, 22, 23, -1, False)}
TOES = {'RF': 11, 'LF': 15, 'RH': 20, 'LH': 24}
TRUNK = (1, 2, 3, 4, 5, 6, 7, 16, 25, 26)       # the donor's own channels; the legs come from the solves
PELVIS, CHEST, NECK, HEAD, HIPS = 1, 2, 3, 5, 16
TAIL = (25, 26)
WINGS = (6, 7)
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


def harm(phase, amp, rate, delay):
    return amp * math.cos(2 * math.pi * rate * (phase - delay))


def body(rig, cfg, phase, pose, hist):
    """The donor's trunk, neck, wings and tail at this phase, softened and carried as the gait row says."""
    rest = rig.rest
    d = donor_at(cfg['slot'], phase + cfg['shift'])
    mean = cfg['mean']
    for b in TRUNK:
        for k in range(3, 6):
            pose[b][k] = d[b][k]
        for k in range(6, 9):
            pose[b][k] = rest[b][k]
    # the pelvis: the donor's bob about its own mean, scaled to what the legs carry, and the carriage
    bob = d[PELVIS][7] - mean[PELVIS][7]
    pose[PELVIS][7] = rest[PELVIS][7] - cfg['height'] + cfg['bob'] * bob
    for b in TRUNK:     # every donor swing about its own mean is scaled: the amplitudes the planted legs and the proportions carry
        if b == PELVIS:
            continue
        k_ = cfg['swing'].get(b, 1.0)
        for k in range(3, 6):
            pose[b][k] = mean[b][k] + k_ * (d[b][k] - mean[b][k]) if b in cfg['swing'] else pose[b][k]
    cap = cfg.get('wing_cap')
    if cap:      # a wing stroke that would sink its tip under the floor is rounded off at the cap (a soft knee, so no kink)
        for b in WINGS:
            v = abs(pose[b][5])
            if v > cap * 0.6:
                knee = cap * 0.4
                v = cap * 0.6 + knee * math.tanh((v - cap * 0.6) / knee)
            pose[b][5] = math.copysign(v, pose[b][5])
    for b, deg in cfg['rx'].items():
        pose[b][3] += deg * DEG
    for b, deg in cfg['rz'].items():
        pose[b][5] += deg * DEG
    for b, k, deg, rate, delay in cfg['osc']:       # spine flex, neck nod and tail stream that follow the stride
        pose[b][k] += harm(phase, deg, rate, delay) * DEG
    # the neck, head and tail follow late by a spring each (set by `soften`); nothing else here
    for b in TRUNK:
        for k in range(3, 6):
            pose[b][k] = round(pose[b][k])
    return pose


PROFILE = dict(
    species=SPECIES, name='Maildramon', source='',
    parents=[-1, 0, 1, 2, 3, 4, 2, 2, 2, 8, 9, 10, 2, 12, 13, 14, 2, 16, 17, 18, 19, 16, 21, 22, 23, 16, 25],
    pelvis=PELVIS, chest=CHEST, neck=None, head=HEAD, tail=(), loose=(),
    legs=LEGS, claws={10: 11, 14: 15, 19: 20, 23: 24}, pole_world=True, rest_plane=True,
    pole={True: [0.0, 0.0, -1.0], False: [0.0, 0.0, 1.0]},
    paw_rest={}, sole={True: [0, 0, 0], False: [0, 0, 0]},      # read off the rig by `prepare`
    reach={'front': 0, 'hind': 0}, fold={True: 60, False: 60}, clear=2, floor=9, stance_slip=0.2,
    speed_range={2: (15, 31), 3: (10, 20), 4: (35, 52)},
    body=body, gaits={},
)

COMMON = dict(
    kind='walk', snap=False, arc=0.4, clear_ease=0.0, world_ease=True, fold_soft=10, slip=0.12, heel=2,
    reach={'front': -15, 'hind': 15}, lift={'front': 40, 'hind': 40}, curl={'front': 10, 'hind': 10}, peel={'front': 10, 'hind': 10},
    out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 0}, track={'front': 0, 'hind': 0},
    bob=0.3, swing={}, rx={}, rz={}, osc=(), height=0, shift=0.0,
)
PROFILE['gaits'] = {
    2: dict(COMMON, slot=2, name='walk', bob=0.2, ticks=16, speed=16,
            touchdown={'LH': 0.0, 'LF': 0.25, 'RH': 0.5, 'RF': 0.75},
            duty={'LH': 0.6, 'RH': 0.6, 'RF': 0.6, 'LF': 0.6}, steps=('LH', 'LF', 'RH', 'RF'),
            swing={3: 0.6, 5: 0.6, 6: 0.5, 7: 0.5, 25: 0.4, 26: 0.4},
            osc=((3, 3, 4.0, 1, 0.1), (5, 3, 3.0, 1, 0.2), (CHEST, 3, 1.0, 2, 0.0))),
    3: dict(COMMON, slot=3, name='tired walk', ticks=20, speed=10.5,
            touchdown={'LH': 0.0, 'LF': 0.25, 'RH': 0.5, 'RF': 0.75},
            duty={'LH': 0.6, 'RH': 0.6, 'RF': 0.6, 'LF': 0.6}, steps=('LH', 'LF', 'RH', 'RF'),
            swing={3: 0.5, 5: 0.6, 6: 0.5, 7: 0.5, 25: 0.5, 26: 0.5}, rx={3: -35.0, 5: -8.0}),
    4: dict(COMMON, slot=4, name='run', kind='gallop', bob=0.2, ticks=12, speed=37, snap=True, arc=0.8,
            touchdown={'LH': 0.0, 'RH': 0.1, 'RF': 0.42, 'LF': 0.54},
            duty={'LH': 0.3, 'RH': 0.3, 'RF': 0.3, 'LF': 0.3}, steps=('LH', 'RF'), wing_cap=800, lift={'front': 60, 'hind': 60},
            swing={3: 0.6, 5: 0.6, 6: 0.5, 7: 0.5, 25: 0.4, 26: 0.4}, rx={25: -48.0, 26: -13.0},
            osc=((3, 3, 6.0, 1, 0.1), (5, 3, 4.0, 1, 0.2), (CHEST, 3, 3.0, 1, 0.0), (HIPS, 3, -3.0, 1, 0.0), (25, 3, 5.0, 1, 0.3))),
}


def prepare(model, rig):
    """Read off the rig what the legs need: each claw's direction and the sole pivot (the claws' tip), and give each foot bone
    the claws' points too, so the floor sits under the claws."""
    pose = animsheet.slot_frames(model, len(rig), 0)[0][0]
    for name, toe in TOES.items():
        PROFILE['paw_rest'][name] = list(pose[toe][6:9])
    PROFILE['sole'][True] = list(pose[TOES['RF']][6:9])
    PROFILE['sole'][False] = list(pose[TOES['RH']][6:9])


def build(data, rig, profile=None):
    """The three field gaits written into the bound, chibi-shaped model -> (bytes, report)."""
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
    profile['paw_rest'], profile['sole'] = PROFILE['paw_rest'], PROFILE['sole']
    DONOR.clear()
    for slot in profile['gaits']:
        DONOR[slot] = animsheet.slot_frames(old, n, slot)[0]
    rest = animsheet.slot_frames(old, n, 0)[0][0]
    for slot, cfg in profile['gaits'].items():
        frames = DONOR[slot][:-1]
        cfg['mean'] = [[sum(f[b][k] for f in frames) / len(frames) for k in range(9)] for b in range(n)]
    return quadruped.build(data, rig, profile)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--rig', type=Path, required=True, help='the 324-report.json of the bound model (generated_skeleton)')
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
