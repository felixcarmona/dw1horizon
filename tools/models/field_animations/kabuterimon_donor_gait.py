"""MegaKabuterimon's field gaits (species 205) on a native Kabuterimon-family rig, with the two feet planted.

MegaKabuterimon wears the skeleton and programs of a native insect Digimon (a native binding, `native_binding.py`: Kabuterimon,
Kuwagamon or Hercules Kabuterimon, which share one body plan: two legs, four arms, a chest, a head and wings). The donors'
own clips keep their lively trunk, four arms, head and wings, but their legs were made for shorter legs than this mesh's:
the soles slid over the floor and sank under it. This stage runs after the binding and writes slots 2, 3 and 4 again, one
cycle each (the battle aliases play them too): everything above the legs is the donor's own clip, resampled to the new
cycle length with its bob toned down to what planted legs can carry; each leg comes from `quadruped.py`: its sole stands
still in the world through the stance (a two-bone solve on the thigh and shin, the foot flat, heel first, rolling over its
ball), swings with a lift, and the body sinks to a leg that cannot reach. The idle (slot 0) is the donor's and stays.

Offline: `python -m tools.models.field_animations.kabuterimon_donor_gait --source BOUND.MMD --rig REPORT.json --out OUT.MMD`
(BOUND from `native_binding.bind`; the build runs it in place).
"""
import argparse
import copy
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet  # noqa: E402
import mmd  # noqa: E402
from tools.models.field_animations import quadruped  # noqa: E402

SPECIES = 9205
DEG = quadruped.DEG
# the donors' rigs, by bone count: pelvis (the trunk's root), hips (the legs' parent), chest, head, legs {side: (thigh, shin, foot,
# side, front)}
DONORS = {
    28: dict(name='Kabuterimon', pelvis=1, hips=21, chest=3, head=4, legs={'R': (22, 23, 24, 1, False), 'L': (25, 26, 27, -1, False)},
             elbows=((6, -1), (9, 1)), lower=(5, 6, 8, 9)),
    30: dict(name='Kuwagamon', pelvis=1, hips=23, chest=3, head=4, legs={'R': (24, 25, 26, 1, False), 'L': (27, 28, 29, -1, False)},
             elbows=((8, -1), (11, 1)), lower=(7, 8, 10, 11)),
    26: dict(name='Hercules Kabuterimon', pelvis=1, hips=19, chest=3, head=4, legs={'R': (20, 21, 22, 1, False), 'L': (23, 24, 25, -1, False)},
             elbows=((6, -1), (8, 1)), lower=(5, 6, 7, 8)),
}
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
    """The donor's trunk, arms, head and wings at this phase, as the gait row says; the legs come from the solves."""
    rest = rig.rest
    d = rig.p['donor']
    legs = {b for leg in d['legs'].values() for b in leg[:3]}
    cur = donor_at(cfg['slot'], phase + cfg['shift'])
    mean = cfg['mean']
    for b in range(1, rig.n):
        if b in legs:
            continue
        for k in range(3, 6):
            m = mean[b][k]
            s = cfg['swing_low'] if b in d['lower'] else cfg['swing_all']
            pose[b][k] = m + s * ((cur[b][k] - m + 2048) % 4096 - 2048) if b != d['pelvis'] else cur[b][k]
        for k in range(6, 9):
            pose[b][k] = rest[b][k]
    p = d['pelvis']
    bob = cur[p][7] - mean[p][7]
    pose[p][7] = rest[p][7] - cfg['height'] + cfg['bob'] * bob
    pose[p][6] = rest[p][6]
    pose[p][8] = rest[p][8]
    tau = 2 * math.pi
    for b, k, deg, freq, lag in cfg['waves']:       # slow overlapped motion on the spine, head (horn) and arms: each lags the one before
        pose[b][k] += cfg['wave_scale'] * deg * DEG * math.sin(tau * (freq * (phase - lag)))
    for b, k, deg in cfg['lean']:
        pose[b][k] += deg * DEG
    for ts, te, b, k, deg in cfg['twitch']:         # a short eased bump (a horn flick) inside the cycle
        x = (phase % 1.0 - ts) / (te - ts)
        if 0 <= x <= 1:
            pose[b][k] += deg * DEG * math.sin(math.pi * x) ** 2
    pose[p][6] += cfg['sway'] * math.sin(tau * (phase - 0.1))
    for b, side in d['elbows']:      # the low arms' hands hang to the floor: the elbows bend a few degrees more (the arms are not mirrored)
        pose[b][4] += side * cfg['elbow_up'] * DEG
    for b in range(1, rig.n):
        if b not in legs:
            for k in range(3, 6):
                pose[b][k] = round(pose[b][k])
    return pose


COMMON = dict(
    kind='walk', snap=False, arc=0.8, plateau=0.8, clear_ease=0.1, world_ease=True, fold_soft=10, slip=0.0, heel=4,
    reach={'front': 0, 'hind': 0}, lift={'front': 0, 'hind': 44}, curl={'front': 0, 'hind': 14}, peel={'front': 0, 'hind': 16},
    out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 0}, track={'front': 0, 'hind': 0}, settle=3,
    height=10, bob=0.6, shift=0.0, swing_all=1.0, swing_low=0.5, elbow_up=30, waves=(), wave_scale=1.0, lean=(), twitch=(), sway=0,
)
GAITS = {
    0: dict(COMMON, slot=0, name='idle', ticks=60, speed=0, touchdown={'L': 0.0, 'R': 0.5}, duty={'L': 1.0, 'R': 1.0}, steps=(),
            lift={'front': 0, 'hind': 0}, peel={'front': 0, 'hind': 0}, curl={'front': 0, 'hind': 0}, heel=0, settle=0, height=6,
            bob=1.0, elbow_up=25,
            waves=((2, 5, 1.2, 1, 0.0), (3, 5, 1.5, 1, 0.08), (4, 5, 2.2, 1, 0.2), (4, 4, 2.5, 1, 0.45), (6, 5, 2.0, 1, 0.1), (9, 5, 2.0, 1, 0.22)),
            twitch=((0.58, 0.68, 4, 4, 7), (0.60, 0.70, 4, 3, -4), (0.2, 0.27, 4, 4, -5)), sway=5),
    2: dict(COMMON, slot=2, name='walk', ticks=20, speed=16, touchdown={'L': 0.0, 'R': 0.5}, duty={'L': 0.52, 'R': 0.52},
            steps=('L', 'R'), height=26, elbow_up=80, lift={'front': 0, 'hind': 40}, peel={'front': 0, 'hind': 8}, curl={'front': 0, 'hind': 6},
            arc=0.7, plateau=0.7, swing_all=0.7, swing_low=0.4, wave_scale=0.6,
            waves=((2, 5, 1.5, 2, 0.05), (3, 5, 2.0, 2, 0.1), (4, 5, 3.0, 2, 0.22), (3, 4, 3.0, 1, 0.0), (4, 4, 2.0, 1, 0.12), (6, 5, 3.0, 2, 0.15), (9, 5, 3.0, 2, 0.3)),
            lean=((2, 5, -2), (4, 5, 2)), sway=3),
    3: dict(COMMON, slot=3, name='tired walk', ticks=22, speed=11, touchdown={'L': 0.0, 'R': 0.5}, duty={'L': 0.62, 'R': 0.62},
            steps=('L', 'R'), lift={'front': 0, 'hind': 40}, peel={'front': 0, 'hind': 12}, curl={'front': 0, 'hind': 8},
            height=26, settle=4, elbow_up=85,
            waves=((2, 5, 1.0, 2, 0.05), (3, 5, 1.5, 2, 0.12), (4, 5, 2.0, 2, 0.3), (3, 4, 2.0, 1, 0.0), (6, 5, 2.0, 2, 0.2), (9, 5, 2.0, 2, 0.35)),
            lean=((2, 5, -3), (3, 5, -2), (4, 5, -5)), sway=4),
    4: dict(COMMON, slot=4, name='run', kind='trot', ticks=14, speed=38, touchdown={'L': 0.0, 'R': 0.5}, duty={'L': 0.45, 'R': 0.45},
            steps=('L', 'R'), lift={'front': 0, 'hind': 46}, peel={'front': 0, 'hind': 6}, curl={'front': 0, 'hind': 0}, heel=2,
            swing_all=0.7, swing_low=0.4, wave_scale=0.6, arc=0.9, clear_ease=0.05, height=24, reach={'front': 0, 'hind': 8}, snap=True, elbow_up=105,
            waves=((2, 5, 1.5, 2, 0.05), (3, 5, 2.5, 2, 0.1), (4, 5, 3.5, 2, 0.25), (3, 4, 3.5, 1, 0.0), (4, 4, 2.0, 1, 0.1), (6, 5, 4.0, 2, 0.15), (9, 5, 4.0, 2, 0.3)),
            lean=((2, 5, -7), (3, 5, -3), (4, 5, -1)), sway=2),
}


def rest_world(model, rig):
    pose = [list(v) for v in animsheet.slot_frames(model, len(rig), 0)[0][0]]
    pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
    return mmd.bone_matrices(model, pose)


def make_profile(model, rig, data, gaits=None):
    n = len(rig)
    d = DONORS[n]
    legs = d['legs']
    profile = dict(
        species=SPECIES, name='MegaKabuterimon', source=hashlib.sha256(data).hexdigest(), parents=[b[1] for b in rig],
        pelvis=d['pelvis'], chest=d['chest'], neck=None, head=d['head'], tail=(), loose=(), donor=d,
        legs=legs, pole_world=True, rest_plane=False, pole={False: [0, -1, -0.3]},
        paw_rest={}, sole={False: [0, 0, 0]}, reach={'front': 0, 'hind': 0}, fold={False: 60},
        clear=3, floor=8, stance_slip=0.25, speed_range={0: (0, 0), 2: (15, 31), 3: (10, 20), 4: (35, 52)},
        floor_skip=(), gaits=copy.deepcopy(gaits or GAITS), body=body)
    W = rest_world(model, rig)
    pos = lambda b: [W[b][i][3] for i in range(3)]
    Rm = lambda b: [list(W[b][i][:3]) for i in range(3)]
    tmp = quadruped.Rig(model, rig, profile)
    up, lo, paw, side, _ = legs['R']
    verts = tmp.verts[paw]
    R = Rm(paw)
    world = [quadruped.add(quadruped.mv(R, v), pos(paw)) for v in verts]
    low = max(w[1] for w in world)
    near = [w for w in world if w[1] > low - 12]
    zc = sum(w[2] for w in near) / len(near)
    sole_w = [0.0, low - pos(paw)[1], zc - pos(paw)[2]]
    profile['sole'][False] = [round(v, 1) for v in quadruped.mv(quadruped.tr(R), sole_w)]
    # one sole point for both legs (no per-leg 'sole' entries): the reviewed clips were made with it
    profile['reach']['hind'] = round(sole_w[2] + 8)
    la = quadruped.norm(quadruped.sub(pos(lo), pos(up)))
    lb = quadruped.norm(quadruped.sub(pos(paw), pos(lo)))
    profile['fold'][False] = round(0.55 * (la + lb))
    for name, (u, l, p_, s, f) in legs.items():
        toe = quadruped.mv(quadruped.tr(Rm(p_)), [0, 0, -1])
        profile['paw_rest'][name] = [round(v, 4) for v in toe]
    return profile


def build(data, rig, tweak=None):
    """The three field gaits written into the bound model -> (bytes, report)."""
    n = len(rig)
    exe = mmd.exe()
    for table in (exe.skeleton, exe.bone_count):
        table.extend([None] * (SPECIES + 1 - len(table)))
    exe.skeleton[SPECIES] = rig
    exe.bone_count[SPECIES] = n
    old = mmd.MMD.parse(data, n)
    old.type = SPECIES
    profile = make_profile(old, rig, data)
    DONOR.clear()
    for slot in profile['gaits']:
        DONOR[slot] = animsheet.slot_frames(old, n, slot)[0]
    for slot, cfg in profile['gaits'].items():
        frames = DONOR[slot][:-1]
        cfg['mean'] = [[frames[0][b][k] + sum((f[b][k] - frames[0][b][k] + 2048) % 4096 - 2048 for f in frames) / len(frames)
                        if 3 <= k < 6 else sum(f[b][k] for f in frames) / len(frames) for k in range(9)] for b in range(n)]
    if tweak:
        tweak(profile)
    return quadruped.build(data, rig, profile)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--rig', type=Path, required=True, help='the 205-report.json of the bound model (generated_skeleton)')
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
