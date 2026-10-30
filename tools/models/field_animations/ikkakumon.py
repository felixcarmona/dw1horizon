"""Ikkakumon's heavy front-driven shuffle with native head and rear acting.

Fixed forearm segments support rolling paws beneath the thick fur. Field-only
fore-root placement clears the coat; source torso, head and rear curves remain.
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

def _author(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    vs = {b: np.array(old.tmd.obj_verts(oi))[:, :3] for b, (oi, _) in enumerate(sk) if oi >= 0}

    def world(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, g))
    rw = world(animsheet.slot_frames(old, n, 0)[0][0])
    reports = []

    def plan(t, period, contact, speed, offset, width, center, rock, basepitch, spread):
        start = math.floor((t - offset) / period) * period + offset
        phase = t - start
        half = speed * contact / 2
        if phase <= contact:
            z = center - half + speed * phase
            x = width
            pitch = basepitch - rock * math.cos(math.pi * phase / contact)
        else:
            q = (phase - contact) / (period - contact)
            sm = 6 * q ** 5 - 15 * q ** 4 + 10 * q ** 3
            z = (center + half) * (1 - sm) + (center - half) * sm + (period - contact) * speed * q * (1 - q) * (1 - 2 * q) ** 5
            x = width + spread * math.sin(math.pi * q) ** 2
            pitch = basepitch + rock * math.cos(math.pi * q) + 10 * math.sin(math.pi * q) ** 2
        return (x, z, pitch, 3 if phase <= contact else 3 + {2: 16, 3: 10, 4: 12}[slot] * math.sin(math.pi * q))
    for slot in [0, 2, 3, 4]:
        fs, loop, events = animsheet.slot_frames(old, n, slot)
        duration = len(fs) - 1
        period = {0: 104, 2: 22, 3: 22, 4: 11}[slot]
        speed = {0: 0, 2: 8, 3: 6, 4: 26}[slot]
        poses = []
        hist = {}
        errs = []
        body = []

        def front(f, hip, knee, foot, x, z, rf, up):
            w = world(f)
            h = w[hip, :3, 3]
            a = np.linalg.norm(f[knee][6:9])
            b = np.linalg.norm(f[foot][6:9])
            reach = (a + b - 0.1) ** 2 - (x - h[0]) ** 2 - (z - h[2]) ** 2
            assert reach > 0, (slot, t, hip, 'XZreach', reach)
            low = h[1] - min(30, math.sqrt(reach))
            high = h[1] + math.sqrt(reach)
            goal = np.array([x, 0.0, z])
            pole = np.array([{2: 0.4, 3: 1.0, 4: 1.0}[slot] * (1 if hip == 7 else -1), {2: 0.0, 3: -0.2, 4: 0.0}[slot] if slot != 4 or hip == 7 else -0.3, {2: -1.0, 3: -0.25, 4: 0.0}[slot]])

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
                bottom = max(float((vs[knee] @ rs.T + joint)[:, 1].max()), float((vs[foot] @ rf.T + goal)[:, 1].max()))
                return (bottom + up, rh, rs)
            elo = solve(low)[0]
            ehi = solve(high)[0]
            # Recovery may stop at native reach; planted targets must remain reachable.
            if ehi < 0 and up > 3:
                low = high
                ehi = 0
            assert elo <= 0 <= ehi, (slot, t, hip, 'Yreach', elo, ehi, h, goal)
            for _ in range(27):
                mid = (low + high) / 2
                if solve(mid)[0] > 0:
                    high = mid
                else:
                    low = mid
            residual, rh, rs = solve((low + high) / 2)
            set_rotation(f, hip, w[sk[hip][1], :3, :3].T @ rh, hist)
            w = world(f)
            set_rotation(f, knee, w[hip, :3, :3].T @ rs, hist)
            w = world(f)
            set_rotation(f, foot, w[knee, :3, :3].T @ rf, hist)
            errs.append(float(np.linalg.norm(world(f)[foot, :3, 3] - goal)))
        for t, source in enumerate(fs):
            f = copy.deepcopy(source)
            f[0] = [4096] * 3 + [0] * 6
            if not slot:
                w = world(f)
                bottom = max((float((v @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max()) for b, v in vs.items()))
                f[13][7] -= math.ceil(max(0, bottom + 3))
            else:
                f[7][6] += {2: 25, 3: 45, 4: 45}[slot]
                f[10][6] -= {2: 25, 3: 45, 4: 45}[slot]
                f[7][7] += 30
                f[10][7] += 30
                f[13][7] = 0
                w = world(f)
                cap = -max((float((vs[b] @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max()) for b in vs if b not in range(7, 13))) - 3
                f[13][7] = math.floor(cap)
                body.append(cap)
                for side, (hip, knee, foot) in enumerate([(7, 8, 9), (10, 11, 12)]):
                    sign = 1 if side == 0 else -1
                    contact = {2: 8, 3: 10, 4: 3}[slot]
                    x, z, pitch, up = plan(t, period, contact, speed, side * period / 2, 155, -30, 6, 15, 40 if slot == 4 else 10)
                    rf, dz, _ = motionsecondary.rolling_foot(vs[foot].tolist(), rotation([0, -sign * 8, 0]).tolist(), pitch)
                    front(f, hip, knee, foot, sign * x, z + dz, np.array(rf), up)
            f[0] = copy.deepcopy(source[0])
            f[0][6] = 0
            f[0][8] = -speed * t
            poses.append(f)
        poses[-1][1:] = copy.deepcopy(poses[0][1:])
        # Protect the complete mesh between logic poses, then bound carrier slew.
        correction = [0] * duration
        if slot:
            bounds = []
            for k in range(duration):
                for q in [0, 1 / 3, 2 / 3]:
                    f = interpolate_pose(poses[k], poses[k + 1], round(q * 4096))
                    w = world(f)
                    bottom = max((float((v @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max()) for b, v in vs.items()))
                    bounds.append((k, q, bottom + 2))
            for iteration in range(3):
                for k, q, need in bounds:
                    j = (k + 1) % duration
                    deficit = need - (1 - q) * correction[k] - q * correction[j]
                    if deficit > 0:
                        add = math.ceil(deficit)
                        correction[k] += add
                        correction[j] += add
            correction = [max((correction[j] - 2 * min((j - i) % duration, (i - j) % duration) for j in range(duration))) for i in range(duration)]
            for k, f in enumerate(poses):
                f[13][7] -= correction[k % duration]
        poses[-1][1:] = copy.deepcopy(poses[0][1:])
        bones = list(range(7, 13)) if slot else []
        channels = {(13, 7)} | {(b, c) for b in bones for c in [3, 4, 5]} | ({(b, c) for b in [7, 10] for c in [6, 7]} if slot else set())
        authored = replace_channels(old.anims.anims[old.anims.table[slot]], poses, loop, n, channels)
        if slot:
            authored = _forward(authored, round(-speed * duration), duration)
            for ins in authored.instrs:
                if ins['op'] == 'key':
                    for group in ins['bones']:
                        if group['bone'] == 0:
                            group['vals'].pop('tx', None)
                    ins['bones'] = [g for g in ins['bones'] if g['vals']]
            first = next((i for i in authored.instrs if i['op'] == 'key' and i['frame'] == 1))
            first['bones'].append(dict(bone=0, div=duration, vals={'tx': 0}))
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
        reports.append(dict(slot=slot, period=duration, gait=period, speed=speed, channels=sorted(channels), max_ankle_error=max(errs, default=0), whole_body_floor_correction=correction, carrier_y_range=[min(body), max(body)] if body else []))
    return (new, reports)

def build(data, sk):
    if hashlib.sha256(data).hexdigest()!=SOURCE or len(sk)!=19:
        raise ValueError('Ikkakumon requires the reviewed pinned 19-bone source')
    old = _parse(data,sk)
    new,solver = _author(old,sk)
    steps = {2:[0,11],3:[0,11],4:[0,6,11,17]}
    for slot,ticks in steps.items():
        authored = _steps(new.anims.anims[new.anims.table[slot]],ticks)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims,new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims,new.anims.table)
    result = new.build()
    actual = _parse(result,sk)
    assert changed_programs(old,actual)==[0,2,3,4]
    assert old.tmd.build()==actual.tmd.build()
    checks = []
    for row in solver:
        slot = row['slot']
        period = row['period']
        original = old.anims.anims[old.anims.table[slot]]
        selected = actual.anims.anims[actual.anims.table[slot]]
        source,loop,events = animsheet.slot_frames(old,19,slot)
        decoded,newloop,newevents = animsheet.slot_frames(actual,19,slot)
        assert len(source)==len(decoded) and loop==newloop==0
        assert [i for i in original.instrs if i['op'] not in ('key','sound')]==[i for i in selected.instrs if i['op'] not in ('key','sound')]
        assert [(t,k,e)for t,k,e in events if k!='sound']==[(t,k,e)for t,k,e in newevents if k!='sound']
        channels = {tuple(c)for c in row['channels']}
        before = mmd.AnimPlayer(original,19,slot)
        after = mmd.AnimPlayer(selected,19,slot)
        cycle = []
        for tick in range(period*9+1):
            assert before.tick()and after.tick()
            assert before.base[1]==after.base[1]
            assert after.root[0]==0
            for bone in range(19):
                for channel in range(9):
                    if (bone,channel)not in channels:
                        assert before.pose[bone][channel]==after.pose[bone][channel],(slot,tick,bone,channel)
            if tick<period:
                cycle.append(copy.deepcopy(after.pose))
            else:
                assert after.pose==cycle[tick%period],(slot,tick,'cyclic drift')
        assert after.root[2]==-row['speed']*period*9
        checks.append(dict(slot=slot,duration=period,gait_period=row['gait'],forward_units_per_tick=row['speed'],root_X_zero_Y_native=True,unselected_pose_channels_exact_nine_cycles=True,segment_translations_scales_exact=True,fore_root_TX_TY_deliberately_changed=bool(slot),changed_pose_repeat_exact_nine_cycles=True,texture_control_events_exact=True))
    storage = motionstorage.audit(result,19)
    assert storage['fits'],storage
    return result,dict(species=218,source_sha256=SOURCE,output_sha256=hashlib.sha256(result).hexdigest(),changed_slots=[0,2,3,4],mesh_skeleton_private33_care_battle_exact=True,checks=checks,solver=solver,footstep_ticks=steps,storage=storage)
