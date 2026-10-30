#!/usr/bin/env python3
"""Seraphimon's grounded walk, tired weight and native wing-assisted run.

The native upper performance and airborne run remain. Correct the source's
sliding walk/tired steps, and adjust just the run landings and one recovery
pose. The existing segmented tabard clears knees and floor without a new rig.
"""
import copy
import hashlib
import math
import numeric as np
import mmd
import animsheet
import motioncyclelayer
import motionstorage
import motionsecondary
from tools.models.field_animations.articulation import replace_channels
from motiondiscidentity import changed_programs
from tools.models.field_animations.war_greymon import rotation, set_rotation
SOURCE = '0224b26e5970794ebdb5511826d5622fdb79c526c5ad5cc441ad56f1aaddb76b'
CHAINS = [(25, 26, 27), (28, 29, 30)]

def _pack(model):
    for anim in model.anims.anims:
        anim.tail = b''
    model.anims.anims, model.anims.table = motioncyclelayer.share_identical_streams(model.anims.anims, model.anims.table)
    return model.build()

def _parse(data, sk):
    mmd.exe().skeleton[207] = sk
    mmd.exe().bone_count[207] = len(sk)
    result = mmd.MMD.parse(data, len(sk))
    result.type = 207
    return result

def _walk_and_tired(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    chains = CHAINS

    def world(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, g))
    rest = animsheet.slot_frames(old, n, 33)[0][0]
    rw = world(rest)
    for b in range(n):
        r = rw[b, :3, :3]
        r /= np.linalg.norm(r, axis=0)
        assert np.max(abs(r.T @ r - np.eye(3))) < 1e-05
    vs = {b: np.array(old.tmd.obj_verts(sk[b][0]))[:, :3] for c in chains for b in c[1:]}
    checks = []
    for slot in [2, 3]:
        fs, loop, events = animsheet.slot_frames(old, n, slot)
        duration = len(fs) - 1
        ws = np.array([world(f) for f in fs])
        root = np.array(fs)[:, 0]
        period = duration
        contact = 6
        lift = {2: 30, 3: 20}[slot]
        rock = {2: 4, 3: 5}[slot]
        origin = 4 if slot == 3 else 0

        def at(t, axis):
            cy = math.floor(t / duration)
            phase = t - cy * duration
            i = min(int(phase), duration - 1)
            q = phase - i
            return cy * (root[-1, axis] - root[0, axis]) + root[i, axis] * (1 - q) + root[i + 1, axis] * q - root[0, axis]
        goals = {}
        for side, (hip, knee, foot) in enumerate(chains):
            center = float(ws[:-1, hip, 2, 3].mean())
            gs = []
            upv = []
            rs = []
            for t in range(len(fs)):
                start = math.floor((t - origin + (1 - side if slot == 2 else side) * period / 2) / period) * period - (1 - side if slot == 2 else side) * period / 2 + origin
                phase = t - start
                travel = at(start, 8) - at(start + contact, 8)
                if phase <= contact:
                    z = center - travel / 2 - (at(t, 8) - at(start, 8))
                    up = 0
                    pitch = -rock * math.cos(math.pi * phase / contact)
                else:
                    span = period - contact
                    q = (phase - contact) / span
                    a = center + travel / 2
                    b = center - (at(start + period, 8) - at(start + period + contact, 8)) / 2
                    z = (2 * q ** 3 - 3 * q * q + 1) * a + (-2 * q ** 3 + 3 * q * q) * b
                    up = lift * math.sin(math.pi * q) ** 2
                    pitch = rock * math.cos(math.pi * q)
                x = rw[foot, 0, 3] - at(t, 6) + at(start, 6)
                if phase > contact:
                    x += (at(start + period, 6) - at(start, 6)) * (3 * q * q - 2 * q * q * q)
                gs.append(np.array([x, 0.0, z]))
                upv.append(up)
                rs.append(rotation([pitch, 0, 0]) @ rw[foot, :3, :3])
            goals[foot] = (gs, upv, rs)
        poses = []
        hist = {}
        maxerr = 0.0
        minmargin = 1000000000.0
        offsets = []
        for i, original in enumerate(fs):
            f = copy.deepcopy(original)
            f[0] = [4096] * 3 + [0] * 6
            wanted = -(276 if slot == 2 else 280) + (0.5 if slot == 2 else 0.35) * (ws[i, 1, 1, 3] + (304 if slot == 2 else 291))
            offset = wanted - ws[i, 1, 1, 3]
            f[1][7] += round(offset)
            offsets.append(offset)
            for side, (hip, knee, foot) in enumerate(chains):
                w = np.array(mmd.bone_matrices(old, f))
                h = w[hip, :3, 3]
                a = np.linalg.norm(f[knee][6:9])
                b = np.linalg.norm(f[foot][6:9])
                gs, upv, rs = goals[foot]
                target = gs[i].copy()
                rfoot = rs[i]
                dxz = np.sum((target[[0, 2]] - h[[0, 2]]) ** 2)
                assert dxz < (a + b - 0.1) ** 2, (slot, i, hip, 'horizontalreach')
                high = h[1] + math.sqrt((a + b - 0.1) ** 2 - dxz)
                low = h[1] + 1
                pole = np.array([0.35 if side == 0 else -0.35, 0.0, -1.0])

                def solve(y):
                    target[1] = y
                    delta = target - h
                    dist = np.linalg.norm(delta)
                    direction = delta / dist
                    pp = pole - direction * (pole @ direction)
                    pp /= np.linalg.norm(pp)
                    along = (a * a - b * b + dist * dist) / (2 * dist)
                    joint = h + direction * along + pp * math.sqrt(max(0, a * a - along * along))
                    rhip, rshin = map(np.array, motionsecondary.native_plane_rotations([rw[v, :3, 3].tolist() for v in [hip, knee, foot]], [h.tolist(), joint.tolist(), target.tolist()], [rw[v, :3, :3].tolist() for v in [hip, knee]]))
                    sole = max(float((vs[knee] @ rshin.T + joint)[:, 1].max()), float((vs[foot] @ rfoot.T + target)[:, 1].max()))
                    return (sole + upv[i], joint, rhip, rshin)
                elo = solve(low)[0]
                ehi = solve(high)[0]
                assert elo <= 0 <= ehi, (slot, i, foot, 'reach', elo, ehi, h, target)
                for _ in range(30):
                    mid = (low + high) / 2
                    if solve(mid)[0] > 0:
                        high = mid
                    else:
                        low = mid
                residual, joint, rhip, rshin = solve((low + high) / 2)
                minmargin = min(minmargin, float(a + b - np.linalg.norm(target - h)))
                set_rotation(f, hip, w[sk[hip][1], :3, :3].T @ rhip, hist)
                w = np.array(mmd.bone_matrices(old, f))
                set_rotation(f, knee, w[hip, :3, :3].T @ rshin, hist)
                w = np.array(mmd.bone_matrices(old, f))
                set_rotation(f, foot, w[knee, :3, :3].T @ rfoot, hist)
                w = np.array(mmd.bone_matrices(old, f))
                maxerr = max(maxerr, float(np.linalg.norm(w[foot, :3, 3] - target)))
            f[0] = copy.deepcopy(original[0])
            poses.append(f)
        poses[-1][1:] = copy.deepcopy(poses[0][1:])
        channels = {(1, 7)} | {(b, c) for chain in chains for b in chain for c in [3, 4, 5]}
        anim = replace_channels(old.anims.anims[old.anims.table[slot]], poses, loop, n, channels)
        sound = next((v for v in anim.instrs if v['op'] == 'sound'))
        anim.instrs = [v for v in anim.instrs if v['op'] != 'sound']
        for tick in [origin, round(origin + period / 2)]:
            event = dict(sound, frame=tick + 1)
            idx = next((j for j, v in enumerate(anim.instrs) if v.get('frame', -1) > tick + 1), len(anim.instrs) - 1)
            anim.instrs.insert(idx, event)
        new.anims.anims.append(anim)
        new.anims.table[slot] = len(new.anims.anims) - 1
        checks.append(dict(slot=slot, max_ankle_error=maxerr, minimum_reach_margin=minmargin, carrier_offset=[min(offsets), max(offsets)]))
    return (new, checks)

def _native_run(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    slot = 4
    fs, loop, _ = animsheet.slot_frames(old, n, slot)
    poses = copy.deepcopy(fs)
    ws = []
    for f in fs:
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        ws.append(np.array(mmd.bone_matrices(old, g)))
    checks = []
    history = {}
    for hip, knee, foot, start in [(25, 26, 27, 3), (28, 29, 30, 12)]:
        vertices = {b: np.array(old.tmd.obj_verts(sk[b][0]))[:, :3] for b in [knee, foot]}
        anchor = np.mean([ws[t][foot, :3, 3] + np.array(fs[t][0][6:9]) for t in [start, start + 1]], axis=0)
        changes = []
        for t in [start, start + 1] + ([start + 2] if foot == 30 else []):
            w = ws[t]
            f = poses[t]
            root = copy.deepcopy(f[0])
            f[0] = [4096] * 3 + [0] * 6
            weight = 1.0 if t in [start, start + 1] else 0.0
            h = w[hip, :3, 3]
            a = np.linalg.norm(f[knee][6:9])
            b = np.linalg.norm(f[foot][6:9])
            target = w[foot, :3, 3].copy()
            desired = anchor - np.array(root[6:9])
            target[[0, 2]] = (1 - weight) * target[[0, 2]] + weight * desired[[0, 2]]
            rfoot = w[foot, :3, :3]
            native_sole = max((float((v @ w[vb, :3, :3].T + w[vb, :3, 3])[:, 1].max()) for vb, v in vertices.items()))
            floor = -8.0 if weight == 1 else native_sole - 6
            dxz = np.sum((target[[0, 2]] - h[[0, 2]]) ** 2)
            assert dxz < (a + b - 0.1) ** 2
            low = h[1] + 1
            high = h[1] + math.sqrt((a + b - 0.1) ** 2 - dxz)

            def solve(y):
                target[1] = y
                delta = target - h
                distance = np.linalg.norm(delta)
                direction = delta / distance
                pole = w[knee, :3, 3] - h
                pole -= direction * (pole @ direction)
                pole /= np.linalg.norm(pole)
                along = (a * a - b * b + distance * distance) / (2 * distance)
                joint = h + direction * along + pole * math.sqrt(max(0, a * a - along * along))
                rhip, rshin = map(np.array, motionsecondary.native_plane_rotations([w[v, :3, 3].tolist() for v in [hip, knee, foot]], [h.tolist(), joint.tolist(), target.tolist()], [w[v, :3, :3].tolist() for v in [hip, knee]]))
                sole = max(float((vertices[knee] @ rshin.T + joint)[:, 1].max()), float((vertices[foot] @ rfoot.T + target)[:, 1].max()))
                return (sole - floor, joint, rhip, rshin)
            assert solve(low)[0] <= 0 <= solve(high)[0], (foot, t, solve(low)[0], solve(high)[0])
            for _ in range(30):
                mid = (low + high) / 2
                if solve(mid)[0] > 0:
                    high = mid
                else:
                    low = mid
            residual, joint, rhip, rshin = solve((low + high) / 2)
            set_rotation(f, hip, w[sk[hip][1], :3, :3].T @ rhip, history)
            ww = np.array(mmd.bone_matrices(old, f))
            set_rotation(f, knee, ww[hip, :3, :3].T @ rshin, history)
            ww = np.array(mmd.bone_matrices(old, f))
            set_rotation(f, foot, ww[knee, :3, :3].T @ rfoot, history)
            f[0] = root
            changes.append(dict(tick=t, weight=weight, ankle_delta=(target - w[foot, :3, 3]).tolist(), floor=floor))
        checks.append(dict(foot=foot, contact_ticks=[start, start + 1], changes=changes))
    channels = {(b, c) for b in range(25, 31) for c in [3, 4, 5]}
    anim = replace_channels(old.anims.anims[old.anims.table[slot]], poses, loop, n, channels)
    new.anims.anims.append(anim)
    new.anims.table[slot] = len(new.anims.anims) - 1
    return (new, checks)

def _guard_and_hem(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    cloth = {b: np.array(old.tmd.obj_verts(sk[b][0]))[:, :3] for b in [22, 23, 24]}
    checks = []
    for slot in [2, 3, 4]:
        fs, loop, _ = animsheet.slot_frames(old, n, slot)
        poses = copy.deepcopy(fs)
        history = {}
        folds = []
        for i, f in enumerate(poses):
            root = copy.deepcopy(f[0])
            f[0] = [4096] * 3 + [0] * 6
            w = np.array(mmd.bone_matrices(old, f))
            if slot in [2, 3]:
                set_rotation(f, 8, w[7, :3, :3].T @ rotation([0, 0, 12]) @ w[8, :3, :3], history)
                after = np.array(mmd.bone_matrices(old, f))
                set_rotation(f, 10, after[9, :3, :3].T @ w[10, :3, :3], history)
            if slot == 4:
                points = np.concatenate([v @ w[b, :3, :3].T + w[b, :3, 3] for b, v in cloth.items()])
                rot = np.array(motionsecondary.clearance_rotation(points.tolist(), w[22, :3, 3].tolist(), [1, 0, 0], [-15, 15], -2))
                set_rotation(f, 22, w[1, :3, :3].T @ rot @ w[22, :3, :3], history)
                folds.append(float(np.arccos(np.clip((np.trace(rot) - 1) / 2, -1, 1)) * 180 / np.pi))
            f[0] = root
        channels = {(b, c) for b in [8, 10] for c in [3, 4, 5]} if slot in [2, 3] else {(22, c) for c in [3, 4, 5]}
        new.anims.anims.append(replace_channels(old.anims.anims[old.anims.table[slot]], poses, loop, n, channels))
        new.anims.table[slot] = len(new.anims.anims) - 1
        checks.append(dict(slot=slot, cloth_fold_max=max(folds, default=0)))
    return (new, checks)

def _tabard_and_sound(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    for slot in [2, 3, 4]:
        fs, loop, _ = animsheet.slot_frames(old, n, slot)
        poses = copy.deepcopy(fs)
        history = {}
        if slot == 2:
            for f in poses:
                root = copy.deepcopy(f[0])
                f[0] = [4096] * 3 + [0] * 6
                w = np.array(mmd.bone_matrices(old, f))
                set_rotation(f, 22, w[1, :3, :3].T @ rotation([-20, 0, 0]) @ w[22, :3, :3], history)
                f[0] = root
            anim = replace_channels(old.anims.anims[old.anims.table[slot]], poses, loop, n, {(22, c) for c in [3, 4, 5]})
        else:
            anim = copy.deepcopy(old.anims.anims[old.anims.table[slot]])
        sound = next((i for i in anim.instrs if i['op'] == 'sound'))
        anim.instrs = [i for i in anim.instrs if i['op'] != 'sound']
        for tick in {2: [0, 11], 3: [4, 16], 4: [3, 12]}[slot]:
            event = dict(sound, frame=tick + 1)
            at = next((j for j, v in enumerate(anim.instrs) if v.get('frame', -1) > tick + 1), len(anim.instrs) - 1)
            anim.instrs.insert(at, event)
        new.anims.anims.append(anim)
        new.anims.table[slot] = len(new.anims.anims) - 1
    return new


def _right_wrist(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    slot = 2
    fs, loop, _ = animsheet.slot_frames(old, n, slot)
    poses = copy.deepcopy(fs)
    history = {}
    for f in poses:
        root = copy.deepcopy(f[0])
        f[0] = [4096] * 3 + [0] * 6
        w = np.array(mmd.bone_matrices(old, f))
        set_rotation(f, 6, w[5, :3, :3].T @ rotation([0, 0, 8]) @ w[6, :3, :3], history)
        f[0] = root
    new.anims.anims.append(replace_channels(old.anims.anims[old.anims.table[slot]], poses, loop, n, {(6, c) for c in [3, 4, 5]}))
    new.anims.table[slot] = len(new.anims.anims) - 1
    return new

def _verify(original, actual, sk):
    assert changed_programs(original, actual) == [2, 3, 4]
    assert original.tmd.build() == actual.tmd.build()
    checks = []
    vertices = {b: np.array(actual.tmd.obj_verts(obj))[:, :3]
                for b, (obj, _) in enumerate(sk) if obj >= 0}
    for slot in [2, 3, 4]:
        before = mmd.AnimPlayer(original.anims.anims[original.anims.table[slot]], 31, slot)
        after = mmd.AnimPlayer(actual.anims.anims[actual.anims.table[slot]], 31, slot)
        allowed = {(b, c) for chain in CHAINS for b in chain for c in [3, 4, 5]}
        if slot != 4:
            allowed |= {(1, 7)} | {(b, c) for b in [8, 10] for c in [3, 4, 5]}
        if slot != 3:
            allowed |= {(22, c) for c in [3, 4, 5]}
        if slot == 2:
            allowed |= {(6, c) for c in [3, 4, 5]}
        frames, loop, events = animsheet.slot_frames(actual, 31, slot)
        duration = len(frames) - 1
        assert loop == 0 and duration == {2: 21, 3: 24, 4: 20}[slot]
        assert [e[0] for e in events] == {2: [0, 11], 3: [4, 16], 4: [3, 12]}[slot]
        assert all(kind == 'sound' and event['bank'] == 1 and event['note'] == 16 for _, kind, event in events)
        max_native_run_rotation_residual = 0
        for tick in range(duration*8):
            assert before.tick() and after.tick()
            assert before.base == after.base
            for bone in range(31):
                for channel in range(9):
                    if (bone, channel) not in allowed:
                        assert before.pose[bone][channel] == after.pose[bone][channel], (slot, tick, bone, channel)
            if slot == 4:
                for bone in range(25, 31):
                    changed = [3, 4] if bone < 28 else [12, 13, 14]
                    if tick % duration in changed:
                        continue
                    for channel in [3, 4, 5]:
                        delta = abs((after.pose[bone][channel] - before.pose[bone][channel] + 2048) % 4096 - 2048)
                        max_native_run_rotation_residual = max(max_native_run_rotation_residual, delta)
        assert max_native_run_rotation_residual <= 1, max_native_run_rotation_residual
        worlds, ground, other = [], -float('inf'), -float('inf')
        for frame in frames:
            pose = copy.deepcopy(frame)
            pose[0] = [4096]*3 + [0]*6
            world = np.array(mmd.bone_matrices(actual, pose))
            worlds.append(world)
            for bone, points in vertices.items():
                y = float((points @ world[bone, :3, :3].T + world[bone, :3, 3])[:, 1].max())
                if bone in [26, 27, 29, 30]:
                    ground = max(ground, y)
                else:
                    other = max(other, y)
        error = 0.
        for side, foot in enumerate([27, 30]):
            for tick in range(duration):
                if slot == 4:
                    planted = tick == (3 if side == 0 else 12)
                else:
                    phase = (tick - (4 if slot == 3 else 0) +
                             (1-side if slot == 2 else side)*duration/2) % duration
                    planted = phase < 6 and phase + 1 <= 6
                if planted:
                    for axis in [0, 2]:
                        travel = (worlds[tick+1][foot, axis, 3] - worlds[tick][foot, axis, 3] +
                                  frames[tick+1][0][6+axis] - frames[tick][0][6+axis])
                        error = max(error, abs(float(travel)))
        assert error < 1 and ground < 3 and other < 0, (slot, error, ground, other)
        checks.append(dict(slot=slot, duration=duration, max_planted_ankle_xz_travel=error,
                           max_native_full_boot_y=ground, max_other_mesh_y=other,
                           max_untouched_run_rotation_residual=max_native_run_rotation_residual))
    return checks


def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE or len(sk) != 31:
        raise ValueError('Seraphimon recipe requires the pinned reviewed source')
    original = _parse(data, sk)
    walking, walk_checks = _walk_and_tired(original, sk)
    running, run_checks = _native_run(_parse(_pack(walking), sk), sk)
    guarded, clearance_checks = _guard_and_hem(_parse(_pack(running), sk), sk)
    clothed = _parse(_pack(_tabard_and_sound(_parse(_pack(guarded), sk), sk)), sk)
    result = _pack(_right_wrist(clothed, sk))
    actual = _parse(result, sk)
    checks = _verify(original, actual, sk)
    storage = motionstorage.audit(result, 31)
    assert storage['fits'], storage
    return result, dict(species=207, source_sha256=SOURCE,
                        output_sha256=hashlib.sha256(result).hexdigest(), changed_slots=[2, 3, 4],
                        mesh_skeleton_idle_private_care_battle_exact=True,
                        other_channels_and_root_exact_eight_cycles=True,
                        native_run_flight_retained_with_one_recovery_clearance=True,
                        original_footstep_sample_retimed=True, walk_checks=walk_checks,
                        run_checks=run_checks, clearance_checks=clearance_checks,
                        decoded_checks=checks, storage=storage)
