"""Ikkakumon's seal scoot: both front flippers plant and press back together while the chest hump surges, lift and swing
forward low and quick, then hold while the body glides and settles; head, horn and mane follow through a tick late.

Fixed forearm segments support rolling paws beneath the thick fur. Field-only fore-root placement clears the coat.
A small periodic carrier correction protects all meshes between logic poses.
"""
import copy
import hashlib
import math
import numeric as np
import mmd
import animsheet
import motionsecondary
import motioncyclelayer
import motionstorage
from tools.models.field_animations.articulation import replace_channels
from tools.models.field_animations.aero_veedramon import _forward, _steps
from motiontailspace import interpolate_pose
from motiondiscidentity import changed_programs
from tools.models.field_animations.war_greymon import rotation, set_rotation
SOURCE = '65d248ab6c95d030e87a44cef70809780cd1e7367a9d617be4773bc1799784f7'

def _parse(data, sk):
    mmd.exe().skeleton[218] = sk
    mmd.exe().bone_count[218] = len(sk)
    m = mmd.MMD.parse(data, len(sk))
    m.type = 218
    return m

IK_BONES = range(7, 13)
LEGS = ((7, 8, 9), (10, 11, 12))
# The belly-scoot: both front flippers reach forward, plant and stay put while they press back (`contact` ticks, the
# chest rising and the belly surging), then lift well off the floor, swing forward in an arc with a relaxed wrist and
# come down again (`recover` ticks) while the body glides and settles; one hump of the chest is the `period`. The left
# one is a few per cent late.
GAITS = {
    2: dict(ticks=32, speed=16, period=16, contact=3, recover=13, amp=0.55, lift=30, spread=8, settle=14, width=145, steps=[0, 16], smooth=1),
    4: dict(ticks=24, speed=38, period=12, contact=3, recover=9, amp=1.0, lift=45, spread=14, settle=30, width=145, steps=[0, 12], smooth=1),
}
FOLLOW = {3: (2, 0.45), 18: (3, 0.35), 5: (2, 0.3), 6: (2, 0.3)}   # bone: (parent whose pitch it follows through, weight)
LAG = 1.0
OUT = 10       # how far the shoulders sit out to the sides of the chest
DROP = 30
WRIST_PLANTED = 40    # most the hand turns from the forearm's own line (degrees) while planted: it tries to lie flat
WRIST_AIR = 25       # ... and while lifted: a relaxed flipper
RECOVER_DRIFT = 0.2   # share of the floor's speed the hand still has as it leaves and lands


def _toward(natural, flat, limit):
    """The hand follows the forearm (its natural pose) but is pulled toward staying `flat` in the world, never turning more than
    `limit` degrees from the natural pose."""
    d = natural.T @ flat
    angle = math.acos(max(-1.0, min(1.0, (float(np.trace(d)) - 1) / 2)))
    if angle < 1e-6:
        return natural
    axis = np.array([d[2, 1] - d[1, 2], d[0, 2] - d[2, 0], d[1, 0] - d[0, 1]])
    axis /= np.linalg.norm(axis)
    return natural @ np.array(motionsecondary.R.from_axis_angle(axis.tolist(), min(angle, math.radians(limit))))


def _cyc(values, u):
    """Linear sample of a closed cycle (values[0] repeated at the end) at fractional index u."""
    n = len(values) - 1
    u %= n
    i = int(u)
    return values[i] + (values[i + 1] - values[i]) * (u - i)


def _body_cycle(src, ticks, amp, smooth, g):
    """The source's chest-hump cycle resampled to `ticks`, scaled around its mean by `amp` and smoothed.
    Returns poses (floats) for ticks 0..ticks-1."""
    n = len(src) - 1
    poses = []
    for t in range(ticks):
        u = t * n / ticks
        poses.append([[_cyc([f[b][c] for f in src], u) for c in range(9)] for b in range(len(src[0]))])
    for b in range(1, len(src[0])):
        if b in IK_BONES:
            continue
        for c in range(9):
            series = [p[b][c] for p in poses]
            mean = sum(series) / ticks
            series = [mean + amp * (v - mean) for v in series]
            for _ in range(smooth):
                series = [(series[t - 1] + 2 * series[t] + series[(t + 1) % ticks]) / 4 for t in range(ticks)]
            for t in range(ticks):
                poses[t][b][c] = series[t]
    # settle: the chest bounces once, damped, after the paws have let go
    for t in range(ticks):
        u = t % g['period'] - (g['contact'] + 0.6 * g['recover'])
        if u > 0:
            poses[t][2][3] += g['settle'] * math.exp(-u / 1.3) * math.sin(2 * math.pi * u / (0.4 * g['period']))
    # follow-through: a child keeps moving a little after its parent's pitch changed (head, horn, mane)
    pitch = {b: [p[b][3] for p in poses] for b in (2, 3)}
    for bone, (parent, weight) in FOLLOW.items():
        lead = [p[parent][3] for p in poses]
        lag = [_cyc(lead + [lead[0]], t - LAG) for t in range(ticks)]
        for t in range(ticks):
            poses[t][bone][3] -= weight * (lead[t] - lag[t])
    return poses


def _author(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    vs = {b: np.array(old.tmd.obj_verts(oi))[:, :3] for b, (oi, _) in enumerate(sk) if oi >= 0}

    def world(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, g))
    rw = world(animsheet.slot_frames(old, n, 0)[0][0])
    rel = {foot: rw[knee, :3, :3].T @ rw[foot, :3, :3] for _, knee, foot in LEGS}
    reports = []

    def bottom_of(f, skip=()):
        w = world(f)
        return max(float((v @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max()) for b, v in vs.items() if b not in skip)

    # ---- idle: unchanged (belly on the floor)
    fs, loop, events = animsheet.slot_frames(old, n, 0)
    duration = len(fs) - 1
    poses = []
    for t, source in enumerate(fs):
        f = copy.deepcopy(source)
        f[0] = [4096] * 3 + [0] * 6
        f[13][7] -= math.ceil(max(0, bottom_of(f) + 3))
        f[0] = copy.deepcopy(source[0])
        f[0][6] = 0
        f[0][8] = 0
        poses.append(f)
    poses[-1][1:] = copy.deepcopy(poses[0][1:])
    authored = replace_channels(old.anims.anims[old.anims.table[0]], poses, loop, n, {(13, 7)})
    new.anims.table[0] = len(new.anims.anims)
    new.anims.anims.append(authored)
    reports.append(dict(slot=0, period=duration))

    src_fs = animsheet.slot_frames(old, n, 4)[0]
    for slot, g in GAITS.items():
        ticks, speed, period, contact = g['ticks'], g['speed'], g['period'], g['contact']
        body = _body_cycle(src_fs, ticks, g['amp'], g['smooth'], g)
        errs = []

        def plan(t, side):
            late = 0.35 if side else 0.0                     # the left flipper is a little behind, and a little shorter
            reach = 0.96 if side else 1.0
            phase = (t - late) % period
            c, r = contact, period - contact
            half = speed * c / 2 * reach
            front_z = -22 - half
            back_z = front_z + speed * reach * c
            width = g['width'] + (3 if side else 0)
            if phase < c:                                    # planted: still on the floor, pressing back
                return width, front_z + speed * reach * phase, 15 - 6 * math.cos(math.pi * phase / c), 3, WRIST_PLANTED
            q = (phase - c) / r                              # lifted, swung forward in an arc, lowered onto the plant
            m = RECOVER_DRIFT * speed * r                    # leaves and lands moving back with the floor, so no skid
            h00, h10, h01, h11 = 2 * q ** 3 - 3 * q ** 2 + 1, q ** 3 - 2 * q ** 2 + q, -2 * q ** 3 + 3 * q ** 2, q ** 3 - q ** 2
            z = max(front_z - 4, h00 * back_z + h10 * m + h01 * front_z + h11 * m)
            arc = math.sin(math.pi * q ** 0.8) ** 1.2
            return (width + g['spread'] * math.sin(math.pi * q) ** 2, z, 15 + 10 * math.sin(math.pi * q), 3 + g['lift'] * arc,
                    WRIST_PLANTED + (WRIST_AIR - WRIST_PLANTED) * math.sin(math.pi * q) ** 0.7)

        def front(f, hip, knee, foot, x, z, rf, up, hist, wb):
            w = world(f)
            h = w[hip, :3, 3]
            a = np.linalg.norm(f[knee][6:9])
            b = np.linalg.norm(f[foot][6:9])
            reach = (a + b - 0.1) ** 2 - (x - h[0]) ** 2 - (z - h[2]) ** 2
            assert reach > 0, (slot, hip, 'XZreach', reach, z)
            low = h[1] - min(30, math.sqrt(reach))
            high = h[1] + math.sqrt(reach)
            goal = np.array([x, 0.0, z])
            pole = np.array([(0.5 if hip == 7 else -0.5), 0.0, 1.0])

            def solve(y):
                goal[1] = y
                d = goal - h
                dist = np.linalg.norm(d)
                direction = d / dist
                pp = pole - direction * (pole @ direction)
                pp /= np.linalg.norm(pp)
                along = (a * a - b * b + dist * dist) / (2 * dist)
                joint = h + direction * along + pp * math.sqrt(max(0, a * a - along * along))
                rh, rs = map(np.array, motionsecondary.native_plane_rotations([rw[v, :3, 3].tolist() for v in [hip, knee, foot]], [h.tolist(), joint.tolist(), goal.tolist()], [rw[v, :3, :3].tolist() for v in [hip, knee]]))
                axis = rs @ np.array(f[foot][6:9])
                axis /= np.linalg.norm(axis)
                rs = np.array(motionsecondary.R.from_axis_angle(axis.tolist(), math.radians(15 if hip == 7 else -15))) @ rs
                rfe = _toward(rs @ rel[foot], rf, wb)
                bottom = max(float((vs[knee] @ rs.T + joint)[:, 1].max()), float((vs[foot] @ rfe.T + goal)[:, 1].max()))
                return (bottom + up, rh, rs, rfe)
            elo = solve(low)[0]
            ehi = solve(high)[0]
            if ehi < 0 and up > 3:
                low = high
                ehi = 0
            assert elo <= 0 <= ehi, (slot, hip, 'Yreach', elo, ehi, h, goal)
            for _ in range(27):
                mid = (low + high) / 2
                if solve(mid)[0] > 0:
                    high = mid
                else:
                    low = mid
            residual, rh, rs, rf = solve((low + high) / 2)
            set_rotation(f, hip, w[sk[hip][1], :3, :3].T @ rh, hist)
            w = world(f)
            set_rotation(f, knee, w[hip, :3, :3].T @ rs, hist)
            w = world(f)
            set_rotation(f, foot, w[knee, :3, :3].T @ rf, hist)
            errs.append(float(np.linalg.norm(world(f)[foot, :3, 3] - goal)))

        hist = {}
        out = None
        for lap in range(2):       # the second lap starts from the first lap's last Euler branch: the loop closes smoothly
            out = []
            carriers = []
            for t in range(ticks):
                f = [[round(v) for v in bone] for bone in body[t]]
                f[0] = [4096] * 3 + [0] * 6
                f[7][6] += OUT
                f[10][6] -= OUT
                f[7][7] += DROP
                f[10][7] += DROP
                f[13][7] = 0
                cap = -bottom_of(f, skip=range(7, 13)) - 3
                f[13][7] = math.floor(cap)
                carriers.append(cap)
                for side, (hip, knee, foot) in enumerate(LEGS):
                    sign = 1 if side == 0 else -1
                    x, z, pitch, up, wb = plan(t, side)
                    rf, dz, _ = motionsecondary.rolling_foot(vs[foot].tolist(), rotation([0, -sign * 8, 0]).tolist(), pitch)
                    front(f, hip, knee, foot, sign * x, z + dz, np.array(rf), up, hist, wb)
                f[0] = copy.deepcopy(src_fs[0][0])
                f[0][6] = 0
                f[0][8] = -speed * t
                out.append(f)
        poses = out + [copy.deepcopy(out[0])]
        poses[-1][0][8] = -speed * ticks
        # Protect the complete mesh between logic poses, then bound the carrier slew (as before).
        correction = [0] * ticks
        bounds = []
        for k in range(ticks):
            for q in [0, 1 / 3, 2 / 3]:
                f = interpolate_pose(poses[k], poses[k + 1], round(q * 4096))
                bounds.append((k, q, bottom_of(f) + 2))
        for iteration in range(3):
            for k, q, need in bounds:
                j = (k + 1) % ticks
                deficit = need - (1 - q) * correction[k] - q * correction[j]
                if deficit > 0:
                    add = math.ceil(deficit)
                    correction[k] += add
                    correction[j] += add
        correction = [max((correction[j] - 2 * min((j - i) % ticks, (i - j) % ticks) for j in range(ticks))) for i in range(ticks)]
        for k, f in enumerate(poses):
            f[13][7] -= correction[k % ticks]
        events_ = [(tk, 'sound', dict(op='sound', frame=tk + 1, bank=1, note=13)) for tk in g['steps']]
        authored = mmd.encode_anim(poses, n, loop_sample=0, events=events_, tol=1)
        authored = _forward(authored, round(-speed * ticks), ticks)
        for ins in authored.instrs:
            if ins['op'] == 'key':
                for group in ins['bones']:
                    if group['bone'] == 0:
                        group['vals'].pop('tx', None)
                ins['bones'] = [gr for gr in ins['bones'] if gr['vals']]
        first = next((i for i in authored.instrs if i['op'] == 'key' and i['frame'] == 1))
        first['bones'].append(dict(bone=0, div=ticks, vals={'tx': 0}))
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
        reports.append(dict(slot=slot, period=ticks, gait=period, speed=speed, max_ankle_error=max(errs), whole_body_floor_correction=correction, carrier_y_range=[min(carriers), max(carriers)]))
    return (new, reports)


def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE or len(sk) != 19:
        raise ValueError('Ikkakumon requires the reviewed pinned 19-bone source')
    old = _parse(data, sk)
    new, solver = _author(old, sk)
    for slot, g in GAITS.items():
        authored = _steps(new.anims.anims[new.anims.table[slot]], g['steps'])
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = _parse(result, sk)
    assert changed_programs(old, actual) == [0, 2, 4]
    assert old.tmd.build() == actual.tmd.build()
    checks = []
    for slot, g in GAITS.items():
        ticks = g['ticks']
        selected = actual.anims.anims[actual.anims.table[slot]]
        decoded, newloop, newevents = animsheet.slot_frames(actual, 19, slot)
        assert len(decoded) == ticks + 1 and newloop == 0
        after = mmd.AnimPlayer(selected, 19, slot)
        cycle = []
        for tick in range(ticks * 9 + 1):
            assert after.tick()
            assert after.root[0] == 0
            if tick < ticks:
                cycle.append(copy.deepcopy(after.pose))
            else:
                assert after.pose == cycle[tick % ticks], (slot, tick, 'cyclic drift')
        assert after.root[2] == -g['speed'] * ticks * 9
        checks.append(dict(slot=slot, duration=ticks, forward_units_per_tick=g['speed'], root_X_zero=True, changed_pose_repeat_exact_nine_cycles=True))
    storage = motionstorage.audit(result, 19)
    assert storage['fits'], storage
    return result, dict(species=218, source_sha256=SOURCE, output_sha256=hashlib.sha256(result).hexdigest(), changed_slots=[0, 2, 4], mesh_skeleton_private33_care_battle_exact=True, checks=checks, solver=solver, footstep_ticks={s: g['steps'] for s, g in GAITS.items()}, storage=storage)
