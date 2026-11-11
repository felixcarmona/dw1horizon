"""BlackGatomon's field gaits (and Gatomon's, the same rig), applied after the field pace pass.

The pace pass plays the walk and condition walk on a stride-sized cycle (one arm swing
for each pair of steps) and the run on the donor walk's own 16 ticks. This layer:

* run: untouched, the donor walk's gait at the run's travel;
* walk and condition walk: the head, pelvis, arms and gloves keep a share of their swing
  and a short cyclic filter rounds every channel; the legs are written again as a real
  step: each sole is planted where it lands (a short heel strike, a flat foot, a roll over
  the toes at the end) and fixed in the world while the body goes over it, then lifts,
  swings forward and lands, the two feet half a cycle apart. The legs are one segment
  from hip to paw, so a plant is as long as that segment reaches; the cycle is as long as
  the plant at the travel needs. The pelvis rises and falls with the legs.

Idle, the other programs, mesh, skeleton, travel and sounds stay exact.
"""
import copy
import math

import numeric as np
import animsheet
import mmd
import retarget
import motioncyclelayer
import motionstorage
from motiondiscidentity import changed_programs
from tools.models.field_animations.articulation import replace_channels
from tools.models.field_animations.war_greymon import align, rotation, set_rotation

SPECIES = 222
TOLERANCE = 2
UPPER = {
    1: (.45, .5, .5),        # head
    2: (.6, .6, .6),         # pelvis
    5: (.4, .3, .4), 7: (.4, .3, .4),      # arms: forward and back, little sideways
    6: (.4, .4, .4), 8: (.4, .4, .4),      # gloves
}
LEGS = (9, 10, 11, 12)
# slot: filter rounds, duty (share of the cycle a sole is planted), lift (units), heel strike and toe-off pitch (degrees)
GAITS = {
    2: dict(filters=1, duty=.5, span=54, pad=2.5, lift=7, strike=-4, toe=10, push=.72, x=26, near=8, twist=-30),
    3: dict(filters=1, duty=.5, span=50, pad=2.5, lift=6, strike=-4, toe=10, push=.72, x=26, near=8, twist=-30),
}
HIPS = ((9, 10, 1), (11, 12, -1))


def _turn(delta):
    return ((delta + 2048) % 4096) - 2048


def _calm(frames, filters):
    ticks = len(frames) - 1
    poses = copy.deepcopy(frames)
    for bone, shares in UPPER.items():
        for k, share in enumerate(shares):
            c = 3 + k
            values = [frames[t][bone][c] for t in range(ticks)]
            centre = sum(values) / ticks
            swing = [centre + share * _turn(v - centre) for v in values]
            for _ in range(filters):
                swing = [.25 * swing[t - 1] + .5 * swing[t] + .25 * swing[(t + 1) % ticks] for t in range(ticks)]
            for t in range(ticks):
                poses[t][bone][c] = round(swing[t])
            poses[ticks][bone][c] = poses[0][bone][c]
    return poses


def _world(model, pose):
    p = copy.deepcopy(pose)
    p[0] = [4096] * 3 + [0] * 6
    return np.array(mmd.bone_matrices(model, p))


def _smooth(x):
    x = min(1., max(0., x))
    return x * x * (3 - 2 * x)


def _legs(model, skeleton, poses, spec, speed):
    """Write the legs and the pelvis height of poses (one cycle and its closing frame) as a planted step."""
    ticks = len(poses) - 1
    verts = {b: np.array(model.tmd.obj_verts(o))[:, :3] for b, (o, _) in enumerate(skeleton) if o >= 0}
    rest = animsheet.slot_frames(model, len(skeleton), 0)[0][0]
    rw = _world(model, rest)
    length = float(np.linalg.norm(np.array(rest[10][6:9])))
    duty, lift = spec['duty'], spec['lift']
    stance = duty * ticks
    swing = ticks - stance
    foot = {}
    for hip, ankle, side in HIPS:
        foot[ankle] = dict(V=verts[ankle], R0=rw[ankle, :3, :3])
    # toe tip: the vertex that is lowest and furthest forward of the flat foot
    V, R0 = foot[10]['V'], foot[10]['R0']
    flat = V @ R0.T
    low = flat[flat[:, 1] > flat[:, 1].max() - 1.5]
    tip_index = int(np.argmin(np.where(flat[:, 1] > flat[:, 1].max() - 1.5, flat[:, 2], 1e9)))

    def pose_of(ankle, pitch, side):
        return rotation([pitch, -side * 5, 0]) @ foot[ankle]['R0']

    def planted(ankle, side, sigma):
        """pitch, ankle (y, z relative to the flat ankle z) for stance progress sigma in 0..1."""
        push = spec['push']
        if sigma < .18:
            pitch = spec['strike'] * (1 - _smooth(sigma / .18))
        elif sigma < push:
            pitch = 0.
        else:
            pitch = spec['toe'] * _smooth((sigma - push) / (1 - push))
        return pitch

    def bottom(ankle, side, pitch):
        w = foot[ankle]['V'] @ pose_of(ankle, pitch, side).T
        return float(w[:, 1].max())

    # touch-down and lift-off ankle z about the hips, in the pelvis frame: the plant is symmetric
    # in the end, found by simulating the stance and letting the sole's own roll take its share
    def stance_path(side, ankle):
        """z of the ankle in the body frame over the stance, from touch-down; and the world shift from the roll."""
        zs, ys, pitches = [], [], []
        pivot = foot[ankle]['V'][tip_index]
        pivot0 = pivot @ pose_of(ankle, 0, side).T
        n = max(1, round(stance * 4))
        shift0 = None
        for i in range(n + 1):
            sigma = i / n
            pitch = planted(ankle, side, sigma)
            if sigma < spec['push']:
                world_z = 0.
                y = -bottom(ankle, side, pitch) - spec['pad']
            else:
                tip = pivot @ pose_of(ankle, pitch, side).T
                world_z = pivot0[2] - tip[2]
                y = -tip[1] - spec['pad']
            zs.append(world_z + spec['span'] * sigma)
            ys.append(y)
            pitches.append(pitch)
        return zs, ys, pitches

    zs, ys, pitches = stance_path(1, 10)
    span = zs[-1] - zs[0]
    centre = float(rw[9, 2, 3])
    z_front = centre - span / 2

    def lerp(a, k, q):
        return a[k] + (a[min(k + 1, len(a) - 1)] - a[k]) * q

    def sample(table, sigma):
        pos = sigma * (len(table) - 1)
        k = min(int(pos), len(table) - 2)
        return lerp(table, k, pos - k)

    def ankle_goal(side, ankle, t, off):
        u = ((t / ticks) + off) % 1
        time = u * ticks
        if time < stance:
            sigma = time / stance
            return dict(stance=True, z=z_front + sample(zs, sigma) - zs[0], y=sample(ys, sigma), pitch=sample(pitches, sigma), time=time)
        tau = (time - stance) / swing
        z0 = z_front + span
        z1 = z_front
        m = .4 * spec['span'] / stance * swing
        h00, h10, h01, h11 = 2 * tau**3 - 3 * tau**2 + 1, tau**3 - 2 * tau**2 + tau, -2 * tau**3 + 3 * tau**2, tau**3 - tau**2
        z = h00 * z0 + h10 * m + h01 * z1 + h11 * m
        # the ankle leaves on the roll (pitch toe) and lands on the heel (pitch strike)
        pitch = spec['toe'] * (1 - _smooth(tau / .5)) + spec['strike'] * _smooth((tau - .5) / .5)
        up = lift * math.sin(math.pi * tau) ** 2
        rise = ys[-1] * (1 - _smooth(tau / .35)) + ys[0] * _smooth(tau / .35)       # blend between the two grounded heights
        y = rise - up
        return dict(stance=False, z=z, y=y, pitch=pitch, time=time)

    report = dict(reach_min=1e9, ground_err=0., ankle_err=0.)
    history = {}
    for t in range(ticks + 1):
        f = poses[t]
        f[2][7] = 0
        w = _world(model, f)
        goals = []
        needs = []
        for (hip, ankle, side), off in zip(HIPS, (0, .5)):
            g = ankle_goal(side, ankle, t % ticks, off)
            h = w[hip, :3, 3]
            dz = g['z'] - h[2]
            dx = side * spec['x'] - h[0]
            reach = length ** 2 - dx ** 2 - dz ** 2
            report['reach_min'] = min(report['reach_min'], reach)
            assert reach > 0, (t, hip, 'ankle out of reach', reach)
            g['need'] = g['y'] - h[1] - math.sqrt(reach)
            g['dx'] = dx
            goals.append(g)
        planted_goals = [g for g in goals if g['stance']] or goals
        f[2][7] = round(sum(g['need'] for g in planted_goals) / len(planted_goals))
        w = _world(model, f)
        for (hip, ankle, side), g in zip(HIPS, goals):
            h = w[hip, :3, 3]
            dz = g['z'] - h[2]
            dy = g['y'] - h[1]
            if g['stance']:
                dx = side * spec['x'] - h[0]
            else:
                free = length ** 2 - dz ** 2 - spec['near'] ** 2
                assert free > 0, (t, hip, 'swing out of reach', free)
                dy = min(dy, math.sqrt(free))
                square = length ** 2 - dy ** 2 - dz ** 2
                assert square > 0 and dy > 0, (t, hip, 'swing out of reach', square, dy)
                dx = side * math.sqrt(square)
            square = length ** 2 - dx ** 2 - dz ** 2
            dyy = math.sqrt(max(square, 0.)) if g['stance'] else dy
            goal = np.array([h[0] + dx, h[1] + (dyy if g['stance'] else dy), g['z']])
            if g['stance']:
                report['ground_err'] = max(report['ground_err'], abs(h[1] + dyy - g['y']))
            old = rw[hip, :3, :3] @ np.array(rest[ankle][6:9])
            axis = (np.array(rest[ankle][6:9]) / length).tolist()
            twist = np.array(retarget.from_axis_angle(axis, math.radians(side * spec['twist'])))
            wanted = align(old, goal - h) @ rw[hip, :3, :3] @ twist
            set_rotation(f, hip, w[2, :3, :3].T @ wanted, history)
            actual = _world(model, f)
            set_rotation(f, ankle, actual[hip, :3, :3].T @ pose_of(ankle, g['pitch'], side), history)
    for b in LEGS + (2,):
        poses[ticks][b] = copy.deepcopy(poses[0][b])
    return report


TAKES_SPECIES = True


def build(data, skeleton, species=SPECIES):
    n = len(skeleton)
    mmd.exe().skeleton[species] = skeleton
    mmd.exe().bone_count[species] = n
    old = mmd.MMD.parse(data, n)
    old.type = species
    new = copy.deepcopy(old)
    channels = {(b, c) for b in list(UPPER) + list(LEGS) for c in (3, 4, 5)} | {(2, 7)}
    checks = []
    for slot in sorted(GAITS):
        spec = GAITS[slot]
        frames, loop, _ = animsheet.slot_frames(old, n, slot)
        assert loop == 0
        ticks = len(frames) - 1
        speed = abs(frames[-1][0][8] - frames[0][0][8]) / ticks
        poses = _calm(frames, spec['filters'])
        report = _legs(old, skeleton, poses, spec, speed)
        index = new.anims.table[slot]
        animation = replace_channels(old.anims.anims[index], poses, loop, n, channels, tolerance=TOLERANCE)
        new.anims.anims[index] = animation
        player = mmd.AnimPlayer(animation, n, slot)
        played = []
        for _ in range(ticks * 3 + 1):
            assert player.tick()
            played.append([list(v) for v in player.pose])
        assert all(abs(a - b) <= 2 for x, y in zip(played[0][1:], played[ticks][1:]) for a, b in zip(x, y)), (slot, 'loop')
        checks.append(dict(slot=slot, ticks=ticks, **report))
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = mmd.MMD.parse(result, n)
    actual.type = species
    assert old.tmd.build() == actual.tmd.build()
    assert changed_programs(old, actual) == sorted(GAITS), changed_programs(old, actual)
    return result, dict(species=species, checks=checks, storage=motionstorage.require(result, n))
