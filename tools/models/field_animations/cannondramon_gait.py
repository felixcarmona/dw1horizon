"""Cannondramon's field gaits (species 405) on planted feet, for a native donor's rig (candidate stage).

The donor is chosen by the rig's bone count (24 Monochromon, 26 Garurumon, 27 Unimon). Bones: pelvis (a hub), chest, neck, head,
tail, and four three-bone legs (thigh, shin, paw; the toes ride the paw). Forward is -z.
"""
import copy
import hashlib
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet  # noqa: E402
import mmd  # noqa: E402
from tools.models.field_animations import quadruped  # noqa: E402

SPECIES = 9405
DONORS = {
    24: dict(pelvis=1, chest=2, neck=3, head=4, tail=(14, 15, 16),
             legs={'RF': (7, 8, 9, 1, True), 'LF': (10, 11, 12, -1, True), 'RH': (18, 19, 20, 1, False), 'LH': (21, 22, 23, -1, False)}),
    26: dict(pelvis=1, chest=2, neck=3, head=4, tail=(15, 16, 17),
             legs={'RF': (7, 8, 9, 1, True), 'LF': (11, 12, 13, -1, True), 'RH': (19, 20, 21, 1, False), 'LH': (23, 24, 25, -1, False)}),
    27: dict(pelvis=1, chest=2, neck=3, head=4, tail=(25, 26),
             legs={'RF': (8, 9, 10, 1, True), 'LF': (12, 13, 14, -1, True), 'RH': (17, 18, 19, 1, False), 'LH': (21, 22, 23, -1, False)}),
}

COMMON = dict(
    kind='walk', snap=False, arc=0.4, clear_ease=0.0, world_ease=True, fold_soft=10, slip=0.1, heel=2,
    reach={'front': 0, 'hind': 0}, lift={'front': 35, 'hind': 35}, curl={'front': 15, 'hind': 15}, peel={'front': 12, 'hind': 12},
    out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 0}, track={'front': 0, 'hind': 0},
    height=0, tilt=0, chest_up=0, neck=0, nod=1, bob=3, pitch=1.0, flex=1.0, roll=1.5, yaw=1.5, head=0.6,
    tail=4, loose=0,
)
GAITS = {
    2: dict(COMMON, name='walk', ticks=14, speed=15, touchdown={'LH': 0.0, 'LF': 0.25, 'RH': 0.5, 'RF': 0.75},
            duty={n: 0.64 for n in ('LH', 'LF', 'RH', 'RF')}, steps=('LH', 'LF', 'RH', 'RF')),
    3: dict(COMMON, name='tired walk', ticks=20, speed=10.5, touchdown={'LH': 0.0, 'LF': 0.25, 'RH': 0.5, 'RF': 0.75},
            duty={n: 0.68 for n in ('LH', 'LF', 'RH', 'RF')}, steps=('LH', 'LF', 'RH', 'RF'),
            bob=2, pitch=0.6, flex=0.6, roll=1.0, yaw=1.0, neck=6, chest_up=2, lift={'front': 22, 'hind': 22}),
    4: dict(COMMON, name='run', kind='gallop', ticks=12, speed=36, snap=True, arc=0.8,
            touchdown={'LH': 0.0, 'RH': 0.1, 'RF': 0.42, 'LF': 0.54}, duty={n: 0.34 for n in ('LH', 'LF', 'RH', 'RF')},
            steps=('LH', 'RF'), lift={'front': 50, 'hind': 45}, curl={'front': 30, 'hind': 22}, peel={'front': 25, 'hind': 22},
            bob=8, pitch=4, flex=5, roll=1.2, yaw=1.0, tail=6, reach={'front': 0, 'hind': 15}),
}


def rest_world(model, rig):
    pose = [list(v) for v in animsheet.slot_frames(model, len(rig), 0)[0][0]]
    pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
    return mmd.bone_matrices(model, pose)


def make_profile(model, rig, data):
    n = len(rig)
    d = DONORS[n]
    legs = d['legs']
    profile = dict(
        species=SPECIES, name='Cannondramon', source=hashlib.sha256(data).hexdigest(), parents=[b[1] for b in rig],
        pelvis=d['pelvis'], chest=d['chest'], neck=d['neck'], head=d['head'], tail=d['tail'], loose=(),
        legs=legs, pole_world=True, rest_plane=True, pole={True: [0, 0, -1], False: [0, 0, 1]},
        paw_rest={}, sole={True: [0, 0, 0], False: [0, 0, 0]}, reach={'front': 0, 'hind': 0}, fold={True: 60, False: 60},
        clear=6, floor=3, stance_slip=0.3, speed_range={2: (15, 31), 3: (10, 20), 4: (35, 52)},
        floor_skip=tuple(d['tail']), gaits=copy.deepcopy(GAITS))
    W = rest_world(model, rig)
    pos = lambda b: [W[b][i][3] for i in range(3)]
    Rm = lambda b: [list(W[b][i][:3]) for i in range(3)]
    tmp = quadruped.Rig(model, rig, profile)
    for front in (True, False):
        name = 'RF' if front else 'RH'
        up, lo, paw, side, _ = legs[name]
        verts = tmp.verts[paw]
        R = Rm(paw)
        world = [quadruped.add(quadruped.mv(R, v), pos(paw)) for v in verts]
        low = max(w[1] for w in world)
        near = [w for w in world if w[1] > low - 12]
        zc = sum(w[2] for w in near) / len(near)
        sole_w = [0.0, low - pos(paw)[1], zc - pos(paw)[2]]
        profile['sole'][front] = [round(v, 1) for v in quadruped.mv(quadruped.tr(R), sole_w)]
        profile['reach']['front' if front else 'hind'] = round(sole_w[2] + (-8 if front else 8))
        la = quadruped.norm(quadruped.sub(pos(lo), pos(up)))
        lb = quadruped.norm(quadruped.sub(pos(paw), pos(lo)))
        profile['fold'][front] = round(0.55 * (la + lb))
        mid = [(a + b) / 2 for a, b in zip(pos(up), pos(paw))]
        knee = quadruped.sub(pos(lo), mid)
        chord = quadruped.unit(quadruped.sub(pos(paw), pos(up)))
        perp = quadruped.sub(knee, quadruped.scale(chord, quadruped.dot(knee, chord)))
        if quadruped.norm(perp) > 12:
            profile['pole'][front] = [round(v, 3) for v in quadruped.unit(perp)]
        else:        # a leg built straight: knees ahead on the hind legs, elbows ahead (a horse's) on the front
            profile['pole'][front] = [0.15, 0.0, -1.0]
    for name, (up, lo, paw, side, front) in legs.items():
        toe = quadruped.mv(quadruped.tr(Rm(paw)), [0, 0, -1])
        profile['paw_rest'][name] = [round(v, 4) for v in toe]
    return profile


def build(data, rig, tweak=None):
    n = len(rig)
    exe = mmd.exe()
    for table in (exe.skeleton, exe.bone_count):
        table.extend([None] * (SPECIES + 1 - len(table)))
    exe.skeleton[SPECIES] = rig
    exe.bone_count[SPECIES] = n
    old = mmd.MMD.parse(data, n)
    old.type = SPECIES
    profile = make_profile(old, rig, data)
    if tweak:
        tweak(profile)
    return quadruped.build(data, rig, profile)
