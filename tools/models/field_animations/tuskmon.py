"""Tuskmon's heavy rolling-claw stride and bounded head/arm clearance.

Preserve the native idle's full acting with a small body lift. Retain the
original tired nod, jaw and tail, replacing wildly spinning elbows with a
weighted arm carry. A level pelvis supports the true hind claws while exact
parent-space compensation retains upper-body and tail gestures. The original
field periods and cycle travel are unchanged.
"""
import copy
import math
import hashlib
import numeric as np
import mmd
import animsheet
import motionsecondary as S
import motioncyclelayer
import motionstorage
from tools.models.field_animations.channels import replace_channels, coalesce
from tools.models.field_animations.gliding import _forward
from tools.models.field_animations.war_greymon import rotation, set_rotation, align
from motiondiscidentity import changed_programs
SOURCE = '7710426ff23e65afd5dd4e261c7d1d92a8d3e41f74bae6a47b86fb0ddac173f8'
OUTPUT = '15c4ef58d51004df7316df5b8ddd7690628f6ac8abba04b3249e03b783cb2613'
PARENTS = [-1, 11, 1, 2, 3, 1, 5, 6, 1, 8, 9, 0, 11, 12, 13, 11, 15, 16, 11, 18, 19, 1]

def _parse(data, sk):
    mmd.exe().skeleton[253] = sk
    mmd.exe().bone_count[253] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = 253
    return model

def _author(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    verts = {b: np.array(old.tmd.obj_verts(o))[:, :3] for b, (o, _) in enumerate(sk) if o >= 0}
    rest = animsheet.slot_frames(old, n, 0)[0][0]
    reports = []

    def world(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, g))

    def orientation(w, b):
        return w[b, :3, :3] / np.linalg.norm(w[b, :3, 0])
    ref = copy.deepcopy(animsheet.slot_frames(old, n, 2)[0][0])
    ref[11][3:6] = [0, 0, 0]
    rw = world(ref)
    restw = world(rest)
    for slot in range(5):
        fs, loop, events = animsheet.slot_frames(old, n, slot)
        duration = len(fs) - 1
        period = duration
        distance = {0: 0, 1: 0, 2: 335, 3: 302, 4: 754}[slot]
        speed = distance / period
        contact = period * {0: 1, 1: 1, 2: 0.5, 3: 0.55, 4: 0.25}[slot]
        lift = {0: 0, 1: 0, 2: 12, 3: 8, 4: 17}[slot]
        rock = {0: 0, 1: 0, 2: 4, 3: 3, 4: 7}[slot]
        frames = []
        plans = []
        hist = {}
        errors = []
        for t, source in enumerate(fs):
            f = copy.deepcopy(source)
            oldw = world(source)
            row = []
            if slot in [0, 1]:
                f[11][7] -= 8
            else:
                oldpelvis = np.array(mmd.rot_matrix(*source[11][3:6]))
                f[11][3:6] = [0, 0, 0]
                f[11][6:9] = [0, round({2: -175, 3: -175, 4: -170}[slot] + 2 * math.cos(4 * math.pi * t / period)), 93]
                for branch in [1, 18]:
                    set_rotation(f, branch, oldpelvis @ np.array(mmd.rot_matrix(*source[branch][3:6])), hist)
                f[1][6:9] = [round(v) for v in oldpelvis @ np.array(source[1][6:9])]
            if slot:
                for shoulder, elbow, hand, sign in [(5, 6, 7, 1), (8, 9, 10, -1)]:
                    f[shoulder][6] = source[shoulder][6] + sign * 12
                    f[shoulder][7] = source[shoulder][7] + 16
                    f[shoulder][8] = source[shoulder][8] - 20
                    wave = math.sin(2 * math.pi * t / period + (0 if sign > 0 else math.pi))
                    lag = math.sin(2 * math.pi * t / period + (0 if sign > 0 else math.pi) - 0.5)
                    amp = {1: 2, 2: 8, 3: 5, 4: 13}[slot]
                    set_rotation(f, shoulder, rotation([-25 + amp * wave, 0, -sign * 4]) @ np.array(mmd.rot_matrix(*rest[shoulder][3:6])), hist)
                    set_rotation(f, elbow, rotation([-8 + 3 * lag, 0, 0]) @ np.array(mmd.rot_matrix(*rest[elbow][3:6])), hist)
                    w = world(f)
                    set_rotation(f, hand, orientation(w, elbow).T @ orientation(restw, hand), hist)
                    w = world(f)
                    points = np.concatenate([verts[b] @ w[b, :3, :3].T + w[b, :3, 3] for b in [shoulder, elbow, hand]])
                    bias = np.array(S.clearance_rotation(points.tolist(), w[shoulder, :3, 3].tolist(), [1, 0, 0], [-50, 0], -20))
                    set_rotation(f, shoulder, orientation(w, 1).T @ bias @ orientation(w, shoulder), hist)
                w = world(f)
                points = np.concatenate([verts[b] @ w[b, :3, :3].T + w[b, :3, 3] for b in [2, 3, 4]])
                bias = np.array(S.clearance_rotation(points.tolist(), w[2, :3, 3].tolist(), [1, 0, 0], [-45, 0], -7))
                set_rotation(f, 2, orientation(w, 1).T @ bias @ orientation(w, 2), hist)
            if slot:
                f[21][7] -= 12
                w = world(f)
                set_rotation(f, 21, orientation(w, 1).T @ rotation([-12, 0, 0]) @ orientation(w, 21), hist)
            if slot > 1:
                f[18][8] += 18
                for hip, knee, foot, sign, offset in [(12, 13, 14, 1, 0), (15, 16, 17, -1, 0.5)]:
                    phase = (t + offset * period) % period
                    stance = phase <= contact
                    if stance:
                        z = 100 - speed * contact / 2 + speed * phase
                        up = 4
                        pitch = -rock * math.cos(math.pi * phase / contact)
                        x = sign * 120
                    else:
                        u = (phase - contact) / (period - contact)
                        smooth = 6 * u ** 5 - 15 * u ** 4 + 10 * u ** 3
                        z = 100 + speed * contact / 2 * (1 - 2 * smooth) + (period - contact) * speed * u * (1 - u) * (1 - 2 * u) ** 5
                        up = 4 + lift * math.sin(math.pi * u) ** 2
                        pitch = rock * math.cos(math.pi * u)
                        x = sign * (120 + 5 * math.sin(math.pi * u) ** 2)
                    rf, dz, _ = S.rolling_foot(verts[foot].tolist(), np.eye(3).tolist(), pitch)
                    rf = np.array(rf)
                    z += dz
                    w = world(f)
                    h = w[hip, :3, 3]
                    la = np.linalg.norm(f[knee][6:9])
                    lb = np.linalg.norm(f[foot][6:9])
                    reach = (la + lb - 0.1) ** 2 - (x - h[0]) ** 2 - (z - h[2]) ** 2
                    assert reach > 0, (slot, t, hip, 'XZreach')
                    lo = h[1] + 1
                    hi = h[1] + math.sqrt(reach)
                    goal = np.array([x, 0, z], float)
                    pole = np.array([sign * 1.6, 0, -1.0])

                    def solve(y):
                        goal[1] = y
                        d = goal - h
                        dist = np.linalg.norm(d)
                        direct = d / dist
                        pp = pole - direct * (pole @ direct)
                        pp /= np.linalg.norm(pp)
                        along = (la * la - lb * lb + dist * dist) / (2 * dist)
                        joint = h + direct * along + pp * math.sqrt(max(0, la * la - along * along))
                        rh = align(rw[hip, :3, :3] @ np.array(f[knee][6:9]), joint - h) @ rw[hip, :3, :3]
                        rk = align(rw[knee, :3, :3] @ np.array(f[foot][6:9]), goal - joint) @ rw[knee, :3, :3]
                        bottom = max(float((verts[knee] @ rk.T + joint)[:, 1].max()), float((verts[foot] @ rf.T + goal)[:, 1].max()))
                        return (bottom + up, rh, rk)
                    assert solve(lo)[0] <= 0 <= solve(hi)[0], (slot, t, hip, 'Yreach', solve(lo)[0], solve(hi)[0])
                    for _ in range(25):
                        mid = (lo + hi) / 2
                        if solve(mid)[0] > 0:
                            hi = mid
                        else:
                            lo = mid
                    _, rh, rk = solve((lo + hi) / 2)
                    set_rotation(f, hip, orientation(w, 11).T @ rh, hist)
                    w = world(f)
                    set_rotation(f, knee, orientation(w, hip).T @ rk, hist)
                    w = world(f)
                    set_rotation(f, foot, orientation(w, knee).T @ rf, hist)
                    errors.append(float(np.linalg.norm(world(f)[foot, :3, 3] - goal)))
                    row.append(dict(foot=foot, stance=stance, phase=phase, ankle=goal.tolist(), orientation=rf.tolist(), up=up))
            frames.append(f)
            plans.append(row)
        frames[-1][1:] = copy.deepcopy(frames[0][1:])
        channels = {(11, 7)}
        if slot:
            channels |= {(b, c) for b in [2, 5, 6, 7, 8, 9, 10, 21] for c in [3, 4, 5]} | {(b, c) for b in [5, 8] for c in [6, 7, 8]} | {(21, 7)}
        if slot > 1:
            channels |= {(b, c) for b in [1, 11, 12, 13, 14, 15, 16, 17, 18] for c in [3, 4, 5]} | {(11, 6), (11, 8)} | {(1, c) for c in [6, 7, 8]} | {(18, 8)}
        original = old.anims.anims[old.anims.table[slot]]
        rotch = {v for v in channels if v[1] in [3, 4, 5]}
        tch = channels - rotch
        animation = replace_channels(original, frames, 0, n, rotch, tolerance=1) if rotch else copy.deepcopy(original)
        animation = replace_channels(animation, frames, 0, n, tch, tolerance=0)
        if slot > 1:
            temporary = copy.deepcopy(old)
            temporary.anims.table[slot] = len(temporary.anims.anims)
            temporary.anims.anims.append(animation)
            decoded = animsheet.slot_frames(temporary, n, slot)[0]
            fhist = {}
            for tick, f in enumerate(decoded):
                for knee, foot, j in [(13, 14, 0), (16, 17, 1)]:
                    w = world(f)
                    set_rotation(f, foot, orientation(w, knee).T @ np.array(plans[tick][j]['orientation']), fhist)
            decoded[-1][1:] = copy.deepcopy(decoded[0][1:])
            animation = replace_channels(animation, decoded, 0, n, {(b, c) for b in [14, 17] for c in [3, 4, 5]}, tolerance=0)
            animation = _forward(animation, -distance, duration)
            for ins in animation.instrs:
                if ins['op'] == 'key':
                    for g in ins['bones']:
                        if g['bone'] == 0:
                            g['vals'].pop('tx', None)
                    ins['bones'] = [g for g in ins['bones'] if g['vals']]
            first = next((i for i in animation.instrs if i['op'] == 'key' and i['frame'] == 1))
            first['bones'].append(dict(bone=0, div=1, vals={'tx': 0}))
            animation.instrs = [i for i in animation.instrs if i['op'] != 'sound']
            cue = next((i for i in original.instrs if i['op'] == 'sound'))
            steps = [0, round(period / 2)]
            for tick in steps:
                e = dict(cue, frame=tick + 1)
                at = next((i for i, x in enumerate(animation.instrs) if x.get('frame', -1) > tick + 1), len(animation.instrs) - 1)
                animation.instrs.insert(at, e)
        else:
            steps = []
        animation, _ = coalesce(animation)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(animation)
        reports.append(dict(slot=slot, period=duration, gait_period=period, speed=speed, distance=distance, contact=contact, channels=sorted(channels), plans=plans, footsteps=steps, maximum_FK_error=max(errors, default=0)))
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    return (new.build(), reports)

def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE or [b[1] for b in sk] != PARENTS or [b[0] for b in sk] != list(range(-1, 21)):
        raise ValueError('Tuskmon requires its reviewed 22-bone source')
    old = _parse(data, sk)
    result, solver = _author(old, sk)
    assert hashlib.sha256(result).hexdigest() == OUTPUT
    actual = _parse(result, sk)
    assert changed_programs(old, actual) == [0, 1, 2, 3, 4] and old.tmd.build() == actual.tmd.build()
    checks = []
    for row in solver:
        slot = row['slot']
        period = row['period']
        channels = {tuple(c) for c in row['channels']}
        original = old.anims.anims[old.anims.table[slot]]
        selected = actual.anims.anims[actual.anims.table[slot]]
        before = mmd.AnimPlayer(original, 22, slot)
        after = mmd.AnimPlayer(selected, 22, slot)
        roots = []
        steps = []
        for tick in range(period * 9 + 1):
            assert before.tick() and after.tick()
            for b in range(1, 22):
                for c in range(9):
                    if (b, c) not in channels:
                        assert before.pose[b][c] == after.pose[b][c], (slot, tick, b, c, 'protected')
            if slot in [0, 1]:
                assert after.pose[11][7] == before.pose[11][7] - 8 and after.base == [0, 0, 0]
            else:
                assert after.base[:2] == [0, 0]
                steps.append(after.base[2])
                roots.append(after.root[2])
        if slot > 1:
            steady = steps[1:]
            assert max(steady) - min(steady) <= 1
            assert [sum(steady[j * period:(j + 1) * period]) for j in range(9)] == [-row['distance']] * 9
            assert before.root[2] == after.root[2]
        fs, loop, events = animsheet.slot_frames(actual, 22, slot)
        sourcefs, sourceloop, sourceevents = animsheet.slot_frames(old, 22, slot)
        assert len(fs) == len(sourcefs) == period + 1 and loop == sourceloop == 0
        assert [(t, k, e) for t, k, e in events if k != 'sound'] == [(t, k, e) for t, k, e in sourceevents if k != 'sound']
        assert [i for i in original.instrs if i['op'] not in ('key', 'sound')] == [i for i in selected.instrs if i['op'] not in ('key', 'sound')]
        if slot > 1:
            assert [t for t, k, e in events if k == 'sound'] == row['footsteps']
        checks.append(dict(slot=slot, nine_cycles_protected_SRT_exact=True, original_period=period, root_cycle_distance=row['distance'], root_X_Y_zero=True, unchanged_mean_pace=True, source_sound_retimed_to_supports=row['footsteps'] if slot > 1 else 'original'))
    storage = motionstorage.audit(result, 22)
    assert storage['fits'], storage
    return (result, dict(species=253, source_sha256=SOURCE, output_sha256=OUTPUT, changed_slots=[0, 1, 2, 3, 4], solver=solver, checks=checks, storage=storage, private33_care_battle_mesh_skeleton_exact=True, all_scales_and_original_leg_lengths_exact=True, idle0_native_SRT_exact_except_body11_TY_minus8=True, arm_anchor_carry='Field1..4 shoulders5/8 TX+12/-12 TY+16 TZ-20; original elbow/wrist link translations retained.', horn_carry='Field1..4 root21TY-12 and worldX rotation -12degrees, retaining source curves.', tail_attachment='Moving2..4 root18TZ+18; child19/20 localSRT exact.', limits='Decoded reference protection and storage only. Fullmesh/contact diagnostics, actual game playback and visual approval separate. Private33 unchanged retains its original reference-floor dip. No SDK/terrain/turn/transition continuous-sweep guarantee.'))
