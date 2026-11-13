"""Zanbamon's field gaits (species 430) on planted feet, for a native donor's rig.

The donor is told from its rig (24 bones Monochromon, 26 Garurumon, 27 with bone 16 under bone 1 Centarumon, other 27 Unimon). Bones:
pelvis (a hub), chest, neck, head, tail, and four three-bone legs (thigh, shin, paw; the toes ride the paw). Forward is -z.
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

SPECIES = 9430
RIDER_COUNT = 9
DONORS = {
    24: dict(pelvis=1, chest=2, neck=3, head=4, tail=(14, 15, 16),
             legs={'RF': (7, 8, 9, 1, True), 'LF': (10, 11, 12, -1, True), 'RH': (18, 19, 20, 1, False), 'LH': (21, 22, 23, -1, False)}),
    26: dict(pelvis=1, chest=2, neck=3, head=4, tail=(15, 16, 17), tol=2,
             legs={'RF': (7, 8, 9, 1, True), 'LF': (11, 12, 13, -1, True), 'RH': (19, 20, 21, 1, False), 'LH': (23, 24, 25, -1, False)}),
    'cent': dict(pelvis=1, chest=2, neck=3, head=4, tail=(17, 18),
                 legs={'RF': (10, 11, 12, 1, True), 'LF': (13, 14, 15, -1, True), 'RH': (19, 20, 22, 1, False), 'LH': (23, 24, 26, -1, False)},
                 links={22: 21, 26: 25}, tail_up=40, gaits={2: dict(ticks=14, speed=15), 3: dict(ticks=20, speed=10.5, slip=0.1, roll=4, pitch=0.3, flex=0.3, bob=1.5),
                        4: dict(ticks=12, speed=36, slip=0.1, roll=3, pitch=1, flex=1.5, bob=5)}),
    27: dict(pelvis=1, chest=2, neck=3, head=4, tail=(25, 26),
             legs={'RF': (8, 9, 10, 1, True), 'LF': (12, 13, 14, -1, True), 'RH': (17, 18, 19, 1, False), 'LH': (21, 22, 23, -1, False)}),
}

COMMON = dict(
    kind='walk', snap=False, arc=0.4, clear_ease=0.0, world_ease=True, fold_soft=10, slip=0.0, heel=0,
    reach={'front': 0, 'hind': 0}, lift={'front': 35, 'hind': 35}, curl={'front': 8, 'hind': 8}, peel={'front': 0, 'hind': 0},
    out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 0}, track={'front': 0, 'hind': 0},
    height=0, tilt=0, chest_up=0, neck=0, nod=1, bob=3, pitch=1.0, flex=1.0, roll=1.5, yaw=1.5, head=0.6,
    tail=4, loose=0,
)
GAITS = {
    0: dict(COMMON, name='idle', ticks=34, speed=0, steps=(), touchdown={'LH': 0.0, 'LF': 0.25, 'RH': 0.5, 'RF': 0.75},
            duty={n: 1.0 for n in ('LH', 'LF', 'RH', 'RF')}, lift={'front': 0, 'hind': 0}, curl={'front': 0, 'hind': 0},
            peel={'front': 0, 'hind': 0}, heel=0, bob=2, pitch=0.8, flex=0.8, roll=0.4, yaw=0.5, head=0.5, tail=2.5, neck=2, nod=1.5),
    2: dict(COMMON, name='walk', ticks=14, speed=19, touchdown={'LH': 0.0, 'LF': 0.25, 'RH': 0.5, 'RF': 0.75},
            duty={n: 0.5 for n in ('LH', 'LF', 'RH', 'RF')}, steps=('LH', 'LF', 'RH', 'RF')),
    3: dict(COMMON, name='tired walk', ticks=18, speed=12.5, touchdown={'LH': 0.0, 'LF': 0.25, 'RH': 0.5, 'RF': 0.75},
            duty={n: 0.6 for n in ('LH', 'LF', 'RH', 'RF')}, steps=('LH', 'LF', 'RH', 'RF'),
            bob=2, pitch=0.6, flex=0.6, roll=1.0, yaw=1.0, neck=6, chest_up=2, lift={'front': 16, 'hind': 16}),
    4: dict(COMMON, name='run', kind='gallop', ticks=12, speed=40, snap=True, arc=0.8,
            touchdown={'LH': 0.0, 'RH': 0.1, 'RF': 0.42, 'LF': 0.54}, duty={n: 0.34 for n in ('LH', 'LF', 'RH', 'RF')},
            steps=('LH', 'RF'), lift={'front': 50, 'hind': 45}, curl={'front': 8, 'hind': 8}, peel={'front': 0, 'hind': 0},
            bob=8, pitch=4, flex=5, roll=1.2, yaw=1.0, tail=6, reach={'front': 0, 'hind': 15}),
}


# The human: nine bones of its own on the mount's back (torso, cape, head, two crests, two arms of two bones). Each answers the beat of the
# mount's stride (its bob, pitch, roll and yaw, each scaled to its own swing) through a damped spring, slower and looser further out
# along the body, so the upper body rides the stride with a lag and an overshoot, leans into the run, slumps when tired and breathes
# and looks about in the idle, instead of being cast in one piece with the hips. Degrees:
RIDER = {'torso': 0, 'cape': 1, 'head': 2, 'crestL': 3, 'crestR': 4, 'armRup': 5, 'armRlo': 6, 'armLup': 7, 'armLlo': 8}
RIDER_ROWS = {
    0: dict(lean=0, pitch=0, roll=0, yaw=0, nod=0, cape=0, flap=2, arm=0, hang=0, look=16, breath=1.6),
    2: dict(lean=3, pitch=4, roll=5, yaw=6, nod=4, cape=2, flap=4, arm=6, hang=-3, look=0, breath=0.5),
    3: dict(lean=13, pitch=2, roll=6, yaw=3, nod=3, cape=-4, flap=4, arm=3, hang=-12, look=0, breath=1.2, droop=12),
    4: dict(lean=10, pitch=7, roll=4, yaw=4, nod=6, cape=4, flap=6, arm=9, hang=-6, look=0, breath=0.5),
}


def spring(u, period, damping, cycles=4, sub=8):
    """A damped spring following the loop u (one value a tick) once it has settled: the loop of its answer, lagging and overshooting."""
    n = len(u)
    w = 2 * math.pi / period
    x, v = u[0], 0.0
    for _ in range(cycles):
        out = []
        for t in range(n):
            a, b = u[t], u[(t + 1) % n]
            for k in range(sub):
                v += (w * w * (a + (b - a) * k / sub - x) - 2 * damping * w * v) / sub
                x += v / sub
            out.append(x)
    return out


def unit(values):
    """The loop scaled so its largest swing from the mean is 1 (0 when it hardly moves)."""
    mean = sum(values) / len(values)
    top = max(abs(v - mean) for v in values)
    return [(v - mean) / top if top > 1e-6 else 0.0 for v in values]


def rider_frames(frames, ticks, base_n, row):
    """Writes the human's bones into the loop `frames` (ticks + 1 poses, the last repeating the first)."""
    deg = 4096 / 360
    n = ticks
    phase = [2 * math.pi * t / n for t in range(n)]
    bob = unit([-f[0][7] for f in frames[:n]])          # up is positive
    pit = unit([f[1][3] + f[2][3] for f in frames[:n]])
    rol = unit([f[1][5] + f[2][5] for f in frames[:n]])
    yaw = unit([f[1][4] + f[2][4] for f in frames[:n]])
    breath = [row['breath'] * math.sin(p) for p in phase]
    look = [row['look'] * (math.sin(p) + 0.35 * math.sin(2 * p + 1)) for p in phase]
    # torso: bobs and nods on the stride a beat late, sways against the hips' roll, twists against their yaw
    t_x = spring([row['pitch'] * (0.6 * bob[t] - 0.5 * pit[t]) + breath[t] for t in range(n)], 8, 0.4)
    t_y = spring([-row['yaw'] * yaw[t] for t in range(n)], 9, 0.5)
    t_z = spring([-row['roll'] * rol[t] for t in range(n)], 9, 0.4)
    # head: lags the torso, nods against its bow, turns against its twist, looks about in the idle, bows when tired
    h_x = spring([row['nod'] * (-0.8 * bob[t] + 0.4 * pit[t]) - 0.5 * t_x[t] for t in range(n)], 10, 0.3)
    h_y = spring([-0.8 * t_y[t] + look[t] for t in range(n)], 12, 0.5)
    h_z = spring([-0.7 * t_z[t] for t in range(n)], 11, 0.4)
    # arms: bounce on the stride and trail back with the pace, the forearm after the upper arm, hanging low when tired
    au_x = spring([row['arm'] * (-bob[t] + 0.5 * pit[t]) + breath[t] for t in range(n)], 9, 0.3)
    al_x = spring([1.3 * v for v in au_x], 11, 0.25)
    # cloak: streams back with the pace and flaps on the bob, loosely
    cape = spring([row['cape'] + row['flap'] * (bob[t] - 0.4 * pit[t]) + 0.5 * breath[t] for t in range(n)], 12, 0.2)
    crest = spring([-1.2 * (h_x[t] + row.get('droop', 0)) - 5 * bob[t] for t in range(n)], 7, 0.2)
    crest_y = spring([-0.5 * h_y[t] for t in range(n)], 8, 0.25)
    rows = []
    for t in range(n):
        rows.append(dict(
            torso=(row['lean'] + t_x[t], t_y[t], t_z[t]),
            head=(h_x[t] + row.get('droop', 0), h_y[t], h_z[t]),
            cape=(cape[t], 0, 0),
            crestL=(crest[t], crest_y[t], 0), crestR=(crest[t], -crest_y[t], 0),
            armRup=(au_x[t] + row['hang'], 0, 0), armLup=(au_x[t] + row['hang'], 0, 0),
            armRlo=(al_x[t], 0, 0), armLlo=(al_x[t], 0, 0)))
    for t in range(n + 1):
        for name, (rx, ry, rz) in rows[t % n].items():
            b = base_n + RIDER[name]
            frames[t][b][3], frames[t][b][4], frames[t][b][5] = rx * deg, ry * deg, rz * deg
    return frames


def rest_world(model, rig):
    pose = [list(v) for v in animsheet.slot_frames(model, len(rig), 0)[0][0]]
    pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
    return mmd.bone_matrices(model, pose)


def make_profile(model, rig, data):
    n = len(rig)
    riders = n
    n -= RIDER_COUNT if n - RIDER_COUNT in DONORS or (n - RIDER_COUNT == 27) else 0     # the human's own bones follow the donor's
    d = DONORS['cent' if n == 27 and rig[16][1] == 1 else n]
    legs = d['legs']
    profile = dict(
        species=SPECIES, name='Zanbamon', source=hashlib.sha256(data).hexdigest(), parents=[b[1] for b in rig],
        pelvis=d['pelvis'], chest=d['chest'], neck=d['neck'], head=d['head'], tail=d['tail'], loose=(),
        legs=legs, links=d.get('links', {}), pole_world=True, rest_plane=True, pole={True: [0, 0, -1], False: [0, 0, 1]},
        paw_rest={}, sole={True: [0, 0, 0], False: [0, 0, 0]}, reach={'front': 0, 'hind': 0}, fold={True: 60, False: 60},
        clear=6, floor=3, stance_slip=0.3, speed_range={0: (0, 0), 2: (15, 31), 3: (10, 20), 4: (35, 52)},
        floor_skip=(), tol=d.get('tol', 1), gaits=copy.deepcopy(GAITS))
    for row in profile['gaits'].values():       # the tail held off the ground: the source's hangs to the floor and the donor's swing would bury it
        row['tail_up'] = d.get('tail_up', 25)
    for slot, row in d.get('gaits', {}).items():     # the rig's own sway and pitch, where the stock rows would dip a hoof
        profile['gaits'][slot].update(row)
    if riders != n:
        for slot, row in profile['gaits'].items():
            row['compose'] = (lambda rg, cfg, frames, slot=slot: rider_frames(frames, cfg['ticks'], n, RIDER_ROWS[slot]))
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
        other = legs['LF' if front else 'LH'][2]        # the two sides' meshes differ a little: stand on the deeper sole
        Ro = Rm(other)
        low_o = max((quadruped.add(quadruped.mv(Ro, v), pos(other)))[1] for v in tmp.verts[other])
        sole_w[1] = max(sole_w[1], low_o - pos(other)[1])
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
