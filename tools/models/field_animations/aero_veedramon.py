"""AeroVeedramon's planted dragon steps with its native head, wings and tail.

Use the complete calf/claw mesh and native limb lengths. Clear the broad haunches
and forearm blades with explicit axial and carry biases. The native eighty-tick
upper performance keeps its clock while five rooted walking strides accompany it,
and the hips, chest, head, arms, tail and wings are tied to the strides (see UPPER).
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
from motiondiscidentity import changed_programs
from tools.models.field_animations.war_greymon import rotation, set_rotation

SOURCE = '537ddcde347903c488812ebf8137fe8772001c78f341d96e634f9d0986ebb8f2'
CHAINS = [(12, 13, 14), (15, 16, 17)]
# The upper body of the native clips keeps its own slow performance; the strides are authored on top, so it is
# tied to them: a share of the native deviation stays (breathing, wing and tail life), and every limb gets a
# stride-locked part (one cycle per leg period, so the loop stays seamless): the hips twist one way and the chest
# the other, the head keeps calmer, each arm swings against its same-side leg, the tail and wings follow with a lag.
UPPER = [1, 2, 3, 4, 6, 7, 9, 10, 18, 19, 20, 21, 22, 23, 24]
KEEP = {1: .25, 2: .3, 3: .5, 4: .5, 6: .45, 7: .5, 9: .45, 10: .5, 18: .5, 19: .5, 20: .5, 21: .7, 22: .7, 23: .7, 24: .7}
# degrees by slot: hip yaw, chest counter yaw, head share of the chest counter, arm swing, hip roll, tail sway per joint, wing roll
# The walk keeps much less of the slow native performance (it read as a second, unrelated rhythm), and bobs twice per stride.
KEEP_WALK = {1: .1, 2: .15, 3: .2, 4: .2, 6: .2, 7: .25, 9: .2, 10: .25, 18: .25, 19: .25, 20: .25, 21: .45, 22: .45, 23: .45, 24: .45}
BOB = 4.0
GAIT = {2: (6.0, 7.0, .6, 16.0, 3.0, 4.0, 6.0), 3: (3.0, 4.0, .6, 8.0, 1.0, 2.0, 2.0), 4: (7.0, 6.0, .6, 18.0, 2.0, 4.0, 4.0)}
YAW, PITCH = 1, -1
BOBSIGN = 1

def _forward(animation, distance, period):
    result = copy.deepcopy(animation)
    for instruction in result.instrs:
        if instruction['op'] == 'key':
            for group in instruction['bones']:
                if group['bone'] == 0:
                    group['vals'].pop('tz', None)
            instruction['bones'] = [g for g in instruction['bones'] if g['vals']]
    first = next((i for i in result.instrs if i['op'] == 'key' and i['frame'] == 1))
    first['bones'].append(dict(bone=0, div=period, vals={'tz': distance}))
    return result


def _parse(data, sk):
    mmd.exe().skeleton[213] = sk
    mmd.exe().bone_count[213] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = 213
    return model


def _author(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    chains = CHAINS
    vs = {b: np.array(old.tmd.obj_verts(sk[b][0]))[:, :3] for chain in chains for b in chain}
    reports = []
    def world(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, g))

    def solveleg(f, hip, knee, foot, x, z, rf, up, hist, reference=None):
        w = world(f)
        h = w[hip, :3, 3]
        a = np.linalg.norm(f[knee][6:9])
        b = np.linalg.norm(f[foot][6:9])
        dxz = (x - h[0]) ** 2 + (z - h[2]) ** 2
        reach = (a + b - 0.1) ** 2 - dxz
        assert reach > 0, ('XZreach', hip, reach)
        goal = np.array([x, 0.0, z])
        low = h[1] + 1
        high = h[1] + math.sqrt(reach)
        pole = np.array([(-1 if hip == 12 else 1) * 0.35, 0.0, -1.0]) if reference is None else reference[knee, :3, 3] - reference[hip, :3, 3]
        ref = rw if reference is None else reference

        def solve(y):
            goal[1] = y
            d = goal - h
            dist = np.linalg.norm(d)
            dire = d / dist
            pp = pole - dire * (pole @ dire)
            pp /= np.linalg.norm(pp)
            along = (a * a - b * b + dist * dist) / (2 * dist)
            joint = h + dire * along + pp * math.sqrt(max(0, a * a - along * along))
            rh, rs = map(np.array, motionsecondary.native_plane_rotations([ref[v, :3, 3].tolist() for v in [hip, knee, foot]], [h.tolist(), joint.tolist(), goal.tolist()], [ref[v, :3, :3].tolist() for v in [hip, knee]]))
            bottom = max(float((vs[knee] @ rs.T + joint)[:, 1].max()), float((vs[foot] @ rf.T + goal)[:, 1].max()))
            return (bottom + up, rh, rs)
        elo = solve(low)[0]
        ehi = solve(high)[0]
        assert elo <= 0 <= ehi, ('Yreach', hip, elo, ehi, h, goal, up)
        for _ in range(27):
            mid = (low + high) / 2
            if solve(mid)[0] > 0:
                high = mid
            else:
                low = mid
        residual, rh, rs = solve((low + high) / 2)
        # Axial haunch twist preserves the solved hip-knee vector.
        if slot in [2, 4]:
            axis = rh @ np.array(f[knee][6:9])
            axis /= np.linalg.norm(axis)
            bias = np.array(motionsecondary.R.from_axis_angle(axis.tolist(), math.radians((1 if hip == 12 else -1) * (-20 if slot == 4 else 20))))
            rh = bias @ rh
        set_rotation(f, hip, w[sk[hip][1], :3, :3].T @ rh, hist)
        w = world(f)
        set_rotation(f, knee, w[hip, :3, :3].T @ rs, hist)
        w = world(f)
        set_rotation(f, foot, w[knee, :3, :3].T @ rf, hist)
        w = world(f)
        return float(np.linalg.norm(w[foot, :3, 3] - goal))
    def tie_upper(f, source, mean, t, slot, period, hist):
        """Blend the native upper body toward its mean and add the stride-locked twist, swing and follow-through."""
        pyaw, cyaw, head, arm, roll, tail, wing = GAIT[slot]
        phi = 2 * math.pi * t / period
        for b in UPPER:
            f[b][3:6] = [round(m + (KEEP_WALK if slot == 2 else KEEP)[b] * (v - m)) for m, v in zip(mean[b], source[b][3:6])]
        lag = {19: .5, 20: 1.0, 22: .5, 24: .5}
        for b in UPPER:
            w = world(f)
            wp = w[sk[b][1], :3, :3]
            local = np.array(mmd.rot_matrix(*f[b][3:6]))
            ang = [0.0, 0.0, 0.0]
            if b == 1:
                ang = [0, YAW * pyaw * math.cos(phi), roll * math.sin(phi)]
            elif b == 2:
                ang = [0, -YAW * (cyaw + pyaw) * math.cos(phi), -roll * math.sin(phi)]
            elif b in (3, 4):
                ang = [0, YAW * head * (cyaw + pyaw) * math.cos(phi - .4 * (b - 2)) / 2, 0]
            elif b in (6, 9):
                sign = 1 if b == 6 else -1
                ang = [PITCH * sign * arm * math.cos(phi + .66), 0, 0]
            elif b in (7, 10):
                sign = 1 if b == 7 else -1
                ang = [PITCH * sign * .5 * arm * math.cos(phi + .66 - .6), 0, 0]
            elif b in (18, 19, 20):
                ang = [0, -YAW * tail * math.cos(phi - lag.get(b, 0)), 0]
            elif b in (21, 23):
                ang = [0, 0, (1 if b == 21 else -1) * wing * math.sin(phi - .8)]
            elif b in (22, 24):
                ang = [0, 0, (1 if b == 22 else -1) * .5 * wing * math.sin(phi - 1.3)]
            if any(ang):
                d = rotation(ang)
                set_rotation(f, b, wp.T @ d @ wp @ local, hist)
            else:
                set_rotation(f, b, local, hist)

    rw = world(animsheet.slot_frames(old, n, 0)[0][0])
    for slot in [0, 2, 3, 4]:
        fs, loop, events = animsheet.slot_frames(old, n, slot)
        duration = len(fs) - 1
        period = {0: 18, 2: 16, 3: 24, 4: 10}[slot]
        contact = {0: 18, 2: 10, 3: 14, 4: 3}[slot]
        speed = {0: 0, 2: 1175 / 80, 3: 12, 4: 50}[slot]
        lift = {0: 0, 2: 20, 3: 14, 4: 28}[slot]
        rock = {0: 0, 2: 8, 3: 6, 4: 10}[slot]
        poses = []
        hist = {}
        mean = {b: np.mean([v[b][3:6] for v in fs[:-1]], axis=0) for b in UPPER}
        errs = []
        for t, source in enumerate(fs):
            f = copy.deepcopy(source)
            f[0] = [4096] * 3 + [0] * 6
            if slot:
                tie_upper(f, source, mean, t, slot, period, hist)
            native = world(f)
            if slot == 2:
                f[1][7] = round(-170 + BOBSIGN * BOB * math.cos(4 * math.pi * t / period))
            if slot == 3:
                f[1][7] = round(-155 + 0.25 * (source[1][7] - np.mean([v[1][7] for v in fs[:-1]])))
            if slot == 4:
                q = t % (period / 2)
                f[1][7] = round(-170 + (3 * math.sin(math.pi * q / contact) ** 2 if q <= contact else -12 * math.sin(math.pi * (q - contact) / (period / 2 - contact)) ** 2))
            if slot == 0:
                bottom = max((float((vs[b] @ native[b, :3, :3].T + native[b, :3, 3])[:, 1].max()) for b in [13, 14, 16, 17]))
                f[1][7] -= math.ceil(max(0, bottom + 2))
            for side, (hip, knee, foot) in enumerate(chains):
                if slot == 0:
                    continue
                start = math.floor((t - (0 if side == 1 else period / 2)) / period) * period + (0 if side == 1 else period / 2)
                phase = t - start
                half = speed * contact / 2
                center = 25
                if phase <= contact:
                    z = center - half + speed * phase
                    up = 2.0
                    pitch = -rock * math.cos(math.pi * phase / contact)
                    x = (-1 if side == 0 else 1) * 95
                else:
                    q = (phase - contact) / (period - contact)
                    span = period - contact
                    a = center + half
                    b = center - half
                    z = (2 * q ** 3 - 3 * q * q + 1) * a + (q ** 3 - 2 * q * q + q) * span * speed + (-2 * q ** 3 + 3 * q * q) * b + (q ** 3 - q * q) * span * speed
                    up = 2 + lift * math.sin(math.pi * q) ** (1 if slot in [2, 4] else 2)
                    pitch = rock * math.cos(math.pi * q) + 10 * math.sin(math.pi * q) ** 2
                    x = (-1 if side == 0 else 1) * (95 + 8 * math.sin(math.pi * q) ** 2)
                flat = rotation([0, (1 if side == 0 else -1) * 20, 0])
                rf, dz, sole = motionsecondary.rolling_foot(vs[foot].tolist(), flat.tolist(), pitch)
                rf = np.array(rf)
                z += dz
                reference = None
                try:
                    errs.append(solveleg(f, hip, knee, foot, x, z, rf, up, hist, reference))
                except Exception as e:
                    raise ValueError((slot, t, str(e))) from e
            # Open the left running carry without flattening its native curve.
            if slot == 4:
                w = world(f)
                r7 = w[7, :3, :3].copy()
                r8 = w[8, :3, :3].copy()
                set_rotation(f, 6, w[2, :3, :3].T @ rotation([0, -12, 0]) @ w[6, :3, :3], hist)
                w = world(f)
                set_rotation(f, 7, w[6, :3, :3].T @ r7, hist)
                w = world(f)
                set_rotation(f, 8, w[7, :3, :3].T @ r8, hist)
            if slot in [2, 4]:
                for elbow, hand, sign in [(7, 8, 1), (10, 11, -1)]:
                    w = world(f)
                    attitude = w[hand, :3, :3].copy()
                    bias = rotation([0, 0, sign * 25])
                    set_rotation(f, elbow, w[sk[elbow][1], :3, :3].T @ bias @ w[elbow, :3, :3], hist)
                    w = world(f)
                    set_rotation(f, hand, w[elbow, :3, :3].T @ attitude, hist)
            for hand in [8, 11]:
                w = world(f)
                points = np.array(old.tmd.obj_verts(sk[hand][0]))[:, :3] @ w[hand, :3, :3].T + w[hand, :3, 3]
                bias = np.array(motionsecondary.clearance_rotation(points.tolist(), w[hand, :3, 3].tolist(), [1, 0, 0], [-45, 0], -8))
                set_rotation(f, hand, w[sk[hand][1], :3, :3].T @ bias @ w[hand, :3, :3], hist)
            f[0] = copy.deepcopy(source[0])
            f[0][8] = -speed * t
            poses.append(f)
        poses[-1][1:] = copy.deepcopy(poses[0][1:])
        bones = [8, 11]
        if slot:
            bones += [b for chain in chains for b in chain]
        if slot in [2, 4]:
            bones += [7, 10]
        if slot == 4:
            bones += [6]
        if slot:
            bones += UPPER
        channels = {(b, c) for b in bones for c in [3, 4, 5]} | {(1, 7)}
        authored = replace_channels(old.anims.anims[old.anims.table[slot]], poses, loop, n, channels)
        if slot:
            authored = _forward(authored, round(-speed * duration), duration)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
        reports.append(dict(slot=slot, period=period, speed=speed, max_ankle_error=max(errs, default=0)))
    return new, reports


def _steps(animation, ticks):
    result = copy.deepcopy(animation)
    sounds = [i for i in result.instrs if i['op'] == 'sound']
    assert sounds and all((i['bank'], i['note']) == (sounds[0]['bank'], sounds[0]['note']) for i in sounds)
    result.instrs = [i for i in result.instrs if i['op'] != 'sound']
    for tick in ticks:
        event = dict(sounds[0], frame=tick+1)
        at = next((i for i, ins in enumerate(result.instrs) if ins.get('frame', -1) > tick+1), len(result.instrs)-1)
        result.instrs.insert(at, event)
    return result


def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE or len(sk) != 25:
        raise ValueError('AeroVeedramon requires the pinned reviewed 25-bone source')
    old = _parse(data, sk)
    new, solver = _author(old, sk)
    for slot, ticks in [(2, range(0, 80, 8)), (3, [0, 12]), (4, [0, 5, 10, 15])]:
        authored = _steps(new.anims.anims[new.anims.table[slot]], ticks)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = _parse(result, sk)
    assert changed_programs(old, actual) == [0, 2, 3, 4]
    assert old.tmd.build() == actual.tmd.build()
    checks = []
    for slot in [0, 2, 3, 4]:
        original = old.anims.anims[old.anims.table[slot]]
        selected = actual.anims.anims[actual.anims.table[slot]]
        source, loop, source_events = animsheet.slot_frames(old, 25, slot)
        decoded, selected_loop, selected_events = animsheet.slot_frames(actual, 25, slot)
        duration = len(source)-1
        assert len(decoded) == len(source) and loop == selected_loop == 0
        assert [i for i in original.instrs if i['op'] not in ('key', 'sound')] == [i for i in selected.instrs if i['op'] not in ('key', 'sound')]
        assert [(t, k, e) for t, k, e in source_events if k != 'sound'] == [(t, k, e) for t, k, e in selected_events if k != 'sound']
        bones = [8, 11]
        if slot:
            bones += [b for chain in CHAINS for b in chain]
        if slot in [2, 4]:
            bones += [7, 10]
        if slot == 4:
            bones += [6]
        if slot:
            bones += UPPER
        channels = {(b, c) for b in bones for c in [3, 4, 5]} | {(1, 7)}
        before = mmd.AnimPlayer(original, 25, slot)
        after = mmd.AnimPlayer(selected, 25, slot)
        cycle = []
        for tick in range(duration*9+1):
            assert before.tick() and after.tick()
            assert before.base[:2] == after.base[:2]
            for bone in range(25):
                for channel in range(9):
                    if (bone, channel) not in channels:
                        assert before.pose[bone][channel] == after.pose[bone][channel], (slot, tick, bone, channel)
            if tick < duration:
                cycle.append(copy.deepcopy(after.pose))
            else:
                assert after.pose == cycle[tick % duration], (slot, tick, 'cyclic drift')
        total = {0: 0, 2: -1175, 3: -288, 4: -1000}[slot]
        assert after.root[2] == total*9, (slot, after.root[2], total)
        checks.append(dict(slot=slot, duration=duration, gait_period={0:18,2:16,3:24,4:10}[slot],
                           forward_units_per_tick={0:0,2:1175/80,3:12,4:50}[slot],
                           source_root_XY_exact=True, unselected_channels_translations_scales_exact_nine_cycles=True,
                           changed_pose_repeat_exact_nine_cycles=True, original_texture_and_control_instructions_exact=True))
    storage = motionstorage.audit(result, 25)
    assert storage['fits'], storage
    return result, dict(species=213, source_sha256=SOURCE, output_sha256=hashlib.sha256(result).hexdigest(),
                        changed_slots=[0,2,3,4], mesh_skeleton_private33_care_battle_exact=True,
                        checks=checks, solver=solver, storage=storage)
