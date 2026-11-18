"""Kyubimon's field gaits on a native donor's rig (species 409, slots 2, 3 and 4): planted paws under the donor's own trunk.

Kyubimon is a nine-tailed fox on four legs. A native binding (`native_binding.py`, recipe 409) puts its rigid pieces on a
native quadruped's skeleton and programs. The donor's clips keep the lively trunk, neck, head and tail, but their legs were
made for another body: the soles slid over the floor and the tired walk was as fast as the walk. This stage runs after the
binding and writes slots 2, 3 and 4 again, one cycle each: the trunk (pelvis height, chest, hips, neck, head and the tail
chain) is the donor's own clip, resampled to the new cycle length with its bob and swing toned down to what planted legs
can carry, and the four legs come from `quadruped.py`: each sole stands still in the world through its stance (two-bone
solves on the thigh and shin, the paw flat on the floor), swings with a lift and a curl, and the body sinks to a leg that
cannot reach. The idle (slot 0) is the donor's and stays.

Offline: `python -m tools.models.field_animations.kyubimon_donor_gait --source BOUND.MMD --rig REPORT.json --out OUT.MMD`
(BOUND is the model `native_binding.bind` writes; the build runs this in place).
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

SPECIES = 9409         # a working id for the donor-shaped rig (the species' own id keeps the skeleton the species file lists)
DEG = quadruped.DEG
DONOR = {}             # slot -> the donor's played frames (filled by `build`)

# per donor rig (keyed by bone count): the legs (thigh, shin, paw, side, front), the trunk bones the donor's own clips drive,
# the pelvis (bone whose height is the bob), chest, neck, head, hips and tail chain
RIGS = {
    26: dict(name='Garurumon', tired_duty=0.68, idle_height=30, run_head=0.0, walk_head=-3.0, legs={'RF': (7, 8, 9, 1, True), 'LF': (11, 12, 13, -1, True),
                                     'RH': (19, 20, 21, 1, False), 'LH': (23, 24, 25, -1, False)},
             trunk=(1, 2, 3, 4, 5, 14, 15, 16, 17), pelvis=1, chest=2, neck=3, head=4, hips=14, tail=(15, 16, 17)),
    27: dict(name='Unimon', legs={'RF': (8, 9, 10, 1, True), 'LF': (12, 13, 14, -1, True),
                                  'RH': (17, 18, 19, 1, False), 'LH': (21, 22, 23, -1, False)},
             trunk=(1, 2, 3, 4, 5, 16, 25, 26), pelvis=1, chest=2, neck=3, head=4, hips=16, tail=(25, 26)),
    24: dict(name='Monochromon', legs={'RF': (7, 8, 9, 1, True), 'LF': (10, 11, 12, -1, True),
                                       'RH': (18, 19, 20, 1, False), 'LH': (21, 22, 23, -1, False)},
             trunk=(1, 2, 3, 4, 5, 13, 14, 15, 16), pelvis=1, chest=2, neck=3, head=4, hips=13, tail=(14, 15, 16)),
}


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


def make_body(spec):
    trunk, pelvis = spec['trunk'], spec['pelvis']

    def body(rig, cfg, phase, pose, hist):
        """The donor's trunk, neck, head and tail at this phase, softened and carried as the gait row says."""
        rest = rig.rest
        d = donor_at(cfg['slot'], phase + cfg['shift'])
        mean = cfg['mean']
        for b in trunk:
            for k in range(6, 9):
                pose[b][k] = rest[b][k]
        bob = d[pelvis][7] - mean[pelvis][7]
        pose[pelvis][7] = rest[pelvis][7] - cfg['height'] + cfg['bob'] * bob
        for b in trunk:        # the carriage is the bound idle's; the donor's swing about its own mean, scaled, rides on it
            if b == pelvis:
                continue
            for k in range(3, 6):
                swing = d[b][k] - mean[b][k]
                swing = (swing + 2048) % 4096 - 2048
                pose[b][k] = rest[b][k] + cfg['swing'].get(b, 0.0) * swing
        for b, deg in cfg['rx'].items():
            pose[b][3] += deg * DEG
        for b, k, deg, rate, delay in cfg['osc']:       # spine flex, neck nod and tail stream that follow the stride
            pose[b][k] += harm(phase, deg, rate, delay) * DEG
        for b in trunk:
            for k in range(3, 6):
                pose[b][k] = round(pose[b][k])
        return pose
    return body


COMMON = dict(
    kind='walk', snap=False, arc=0.4, clear_ease=0.0, world_ease=True, fold_soft=10, slip=0.12, heel=2,
    reach={'front': 0, 'hind': 0}, lift={'front': 40, 'hind': 40}, curl={'front': 10, 'hind': 10}, peel={'front': 10, 'hind': 10},
    out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 0}, track={'front': 0, 'hind': 0},
    bob=0.3, swing={}, rx={}, rz={}, osc=(), height=0, shift=0.0,
)


def gaits(spec):
    pelvis, chest, neck, head, hips, tail = (spec[k] for k in ('pelvis', 'chest', 'neck', 'head', 'hips', 'tail'))
    wave = lambda amp, rate: tuple((b, 3, amp * (1 + 0.4 * i), rate, 0.12 * (i + 1)) for i, b in enumerate(tail))
    sw_walk = {chest: 0.3, hips: 0.3, neck: 0.4, head: 0.4, **{b: 0.5 for b in tail}}
    return {
        0: dict(COMMON, slot=0, name='idle', ticks=40, speed=0, steps=(), bob=1.0, peel={'front': 0, 'hind': 0}, curl={'front': 0, 'hind': 0}, heel=0, height=spec.get('idle_height', 0),
                touchdown={'LH': 0.0, 'LF': 0.25, 'RH': 0.5, 'RF': 0.75}, duty={'LH': 1.0, 'LF': 1.0, 'RH': 1.0, 'RF': 1.0},
                swing={**{b: 0.5 for b in (chest, hips, neck, head)}, **{b: 0.0 for b in tail}}, osc=wave(5.0, 1)),
        2: dict(COMMON, slot=2, name='walk', rx={head: spec.get('walk_head', -6.0)}, bob=0.2, ticks=16, speed=17,
                touchdown={'LH': 0.0, 'LF': 0.25, 'RH': 0.5, 'RF': 0.75},
                duty={'LH': 0.58, 'RH': 0.58, 'RF': 0.58, 'LF': 0.58}, steps=('LH', 'LF', 'RH', 'RF'),
                swing=sw_walk, osc=((neck, 3, 1.5, 1, 0.1), (head, 3, 1.5, 1, 0.2), (chest, 3, 1.0, 2, 0.0)) + wave(4.0, 1)),
        3: dict(COMMON, slot=3, name='tired walk', **dict(dict(ticks=22, speed=11.5), **spec.get('tired', {})),
                touchdown={'LH': 0.0, 'LF': 0.25, 'RH': 0.5, 'RF': 0.75},
                duty=dict.fromkeys(('LH', 'RH', 'RF', 'LF'), spec.get('tired_duty', 0.62)), steps=('LH', 'LF', 'RH', 'RF'),
                swing={chest: 0.25, hips: 0.25, neck: 0.5, head: 0.5, **{b: 0.5 for b in tail}}, osc=wave(3.0, 1)),
        4: dict(COMMON, slot=4, name='run', rx={head: spec.get('run_head', -8.0)}, kind='gallop', bob=0.2, height=spec.get('run_height', 0), ticks=14, speed=40, snap=True, arc=0.8,
                touchdown={'LH': 0.0, 'RH': 0.1, 'RF': 0.42, 'LF': 0.54},
                duty={'LH': 0.3, 'RH': 0.3, 'RF': 0.3, 'LF': 0.3}, steps=('LH', 'RF'), lift={'front': 55, 'hind': 50},
                swing={chest: 0.2, hips: 0.2, neck: 0.2, head: 0.2, **{b: 0.5 for b in tail}},
                osc=((neck, 3, 1.5, 1, 0.1), (head, 3, 1.0, 1, 0.2), (chest, 3, 2.0, 1, 0.0), (hips, 3, -2.0, 1, 0.0)) + wave(6.0, 1)),
    }


def profile_for(spec, rig, model):
    parents = [b[1] for b in rig]
    pose = animsheet.slot_frames(model, len(rig), 0)[0][0]
    prof = dict(
        species=SPECIES, name='Kyubimon', source='', parents=parents,
        pelvis=spec['pelvis'], chest=spec['chest'], neck=None, head=spec['head'], tail=(), loose=(),
        legs=spec['legs'], pole_world=True, rest_plane=True,
        pole={True: [0.0, 0.0, 1.0], False: [0.0, 0.0, -1.0]},
        paw_rest={}, sole={True: [0, 0, 0], False: [0, 0, 0]},
        reach={'front': 0, 'hind': 0}, fold={True: 60, False: 60}, clear=-1, floor=9, stance_slip=0.2,
        speed_range={2: (15, 31), 3: (10, 20), 4: (35, 52)},
        body=make_body(spec), gaits=gaits(spec),
    )
    return prof


def prepare(model, rig, prof):
    """Read the paws off the bound rig at rest: the sole pivot (the lowest point of each paw's mesh, under its middle) and the
    direction of its toes, both in the paw bone's space."""
    n = len(rig)
    pose = animsheet.slot_frames(model, n, 0)[0][0]
    pose[0] = [4096] * 3 + [0] * 6
    world = mmd.bone_matrices(model, pose)
    verts = {b: model.tmd.obj_verts(o) for b, (o, _) in enumerate(rig) if o >= 0}
    for name, (up, lo, paw, side, front) in prof['legs'].items():
        w = world[paw]
        rot_ = [[w[i][j] for j in range(3)] for i in range(3)]
        scale = [math.sqrt(sum(rot_[i][j] ** 2 for i in range(3))) for j in range(3)]
        rot_ = [[rot_[i][j] / scale[j] for j in range(3)] for i in range(3)]
        origin = [w[i][3] for i in range(3)]
        pts = [[sum(rot_[i][j] * v[j] for j in range(3)) + origin[i] for i in range(3)] for v in verts[paw]]
        low = max(p[1] for p in pts)
        zs = [p[2] for p in pts]
        centre = [origin[0], low, (min(zs) + max(zs)) / 2]
        d = [centre[i] - origin[i] for i in range(3)]
        local = [sum(rot_[i][j] * d[i] for i in range(3)) for j in range(3)]
        ahead = [sum(rot_[i][j] * (0, 0, -1)[i] for i in range(3)) for j in range(3)]
        prof['paw_rest'][name] = ahead
        prof['sole'][front] = local


def build(data, rig, profile_override=None):
    """The three field gaits written into the bound model -> (bytes, report)."""
    spec = RIGS[len(rig)]
    n = len(rig)
    exe = mmd.exe()
    for table in (exe.skeleton, exe.bone_count):
        table.extend([None] * (SPECIES + 1 - len(table)))
    exe.skeleton[SPECIES] = rig
    exe.bone_count[SPECIES] = n
    old = mmd.MMD.parse(data, n)
    old.type = SPECIES
    profile = profile_for(spec, rig, old)
    if profile_override:
        profile.update(profile_override)
    profile['source'] = hashlib.sha256(data).hexdigest()
    prepare(old, rig, profile)
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
    p.add_argument('--rig', type=Path, required=True, help='the report json of the bound model (generated_skeleton)')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    rig = json.loads(a.rig.read_text())['generated_skeleton']
    data, proof = build(a.source.read_bytes(), rig)
    a.out.write_bytes(data)
    for c in proof['checks']:
        print(c['slot'], c['gait'], c['ticks'], 'speed', c['units_per_tick'], 'floor', c['lowest_point'], 'slip', c['stance_slip'], 'drop', c['body_drop'], 'short', c['unreached'])
    print(proof['storage']['resident_bytes'])


if __name__ == '__main__':
    main()
