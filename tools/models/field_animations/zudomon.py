"""Zudomon's full native performance with grounded hammer-bearing strides.

Restore the unhurried 96-tick private performance to each primary field slot.
Fixed-length leg solving, a higher active hammer carry and minimal appendage
clearance keep its native character without retiming the upper gesture.
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
from tools.models.field_animations.aero_veedramon import _forward
from motiondiscidentity import changed_programs
from tools.models.field_animations.war_greymon import rotation, set_rotation
SOURCE = 'f39e1523a9f478e892830ba74a558aee4c15409dd375d2047d799735293af080'

def _parse(data, sk):
    mmd.exe().skeleton[219] = sk
    mmd.exe().bone_count[219] = len(sk)
    m = mmd.MMD.parse(data, len(sk))
    m.type = 219
    return m

def _author(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    vs = {b: np.array(old.tmd.obj_verts(oi))[:, :3] for b, (oi, _) in enumerate(sk) if oi >= 0}

    def world(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, g))
    # The import compressed this full performance into 20/24-tick field loops.
    native, loop, _ = animsheet.slot_frames(old, n, 33)
    rw = world(native[0])
    mean = np.array(native[:-1])[:, 11, 7].mean()
    reports = []
    for slot in [0, 2, 3, 4]:
        fs = native
        duration = len(fs) - 1
        period = {0: 96, 2: 24, 3: 32, 4: 12}[slot]
        contact = {0: 96, 2: 14, 3: 20, 4: 4}[slot]
        speed = {0: 0, 2: 13, 3: 9, 4: 40}[slot]
        lift = {0: 0, 2: 22, 3: 16, 4: 30}[slot]
        rock = {0: 0, 2: 7, 3: 5, 4: 10}[slot]
        poses = []
        hist = {}
        errs = []

        def leg(f, hip, knee, foot, x, z, rf, up):
            w = world(f)
            h = w[hip, :3, 3]
            a = np.linalg.norm(f[knee][6:9])
            b = np.linalg.norm(f[foot][6:9])
            reach = (a + b - 0.1) ** 2 - (x - h[0]) ** 2 - (z - h[2]) ** 2
            assert reach > 0, (slot, t, hip, 'XZreach', reach)
            low = h[1] - min(20, math.sqrt(reach))
            high = h[1] + math.sqrt(reach)
            goal = np.array([x, 0.0, z])
            pole = np.array([1.0 if hip == 15 else -1.0, 0.0, 0.0])

            def solve(y):
                goal[1] = y
                d = goal - h
                dist = np.linalg.norm(d)
                dire = d / dist
                pp = pole - dire * (pole @ dire)
                pp /= np.linalg.norm(pp)
                along = (a * a - b * b + dist * dist) / (2 * dist)
                joint = h + dire * along + pp * math.sqrt(max(0, a * a - along * along))
                rh, rs = map(np.array, motionsecondary.native_plane_rotations([native_ref[v, :3, 3].tolist() for v in [hip, knee, foot]], [h.tolist(), joint.tolist(), goal.tolist()], [native_ref[v, :3, :3].tolist() for v in [hip, knee]]))
                bottom = max(float((vs[knee] @ rs.T + joint)[:, 1].max()), float((vs[foot] @ rf.T + goal)[:, 1].max()))
                return (bottom + up, rh, rs)
            elo = solve(low)[0]
            ehi = solve(high)[0]
            assert elo <= 0 <= ehi, (slot, t, hip, 'Yreach', elo, ehi, h, goal)
            for _ in range(27):
                mid = (low + high) / 2
                if solve(mid)[0] > 0:
                    high = mid
                else:
                    low = mid
            residual, rh, rs = solve((low + high) / 2)
            axis = rh @ np.array(f[knee][6:9])
            axis /= np.linalg.norm(axis)
            rh = np.array(motionsecondary.R.from_axis_angle(axis.tolist(), math.radians((-20 if slot == 4 else -15) if hip == 15 else 0))) @ rh
            set_rotation(f, hip, w[11, :3, :3].T @ rh, hist)
            w = world(f)
            set_rotation(f, knee, w[hip, :3, :3].T @ rs, hist)
            w = world(f)
            set_rotation(f, foot, w[knee, :3, :3].T @ rf, hist)
            errs.append(float(np.linalg.norm(world(f)[foot, :3, 3] - goal)))
        for t, source in enumerate(fs):
            # Retain the native pose-dependent leg twist around each solved chain.
            native_ref = world(source)
            f = copy.deepcopy(source)
            f[0] = [4096] * 3 + [0] * 6
            if not slot:
                w = world(f)
                bottom = max((float((vs[b] @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max()) for b in [16, 17, 19, 20]))
                f[11][7] -= math.ceil(max(0, bottom + 3))
            else:
                f[11][7] = round({2: -205, 3: -200, 4: -205}[slot] + 0.4 * (source[11][7] - mean))
                if slot == 4:
                    q = t % (period / 2)
                    f[11][7] += round(2 * math.sin(math.pi * q / contact) ** 2 if q <= contact else -6 * math.sin(math.pi * (q - contact) / (period / 2 - contact)) ** 2)
                for side, (hip, knee, foot) in enumerate([(15, 16, 17), (18, 19, 20)]):
                    sign = 1 if side == 0 else -1
                    offset = side * period / 2
                    start = math.floor((t - offset) / period) * period + offset
                    phase = t - start
                    half = speed * contact / 2
                    center = 20
                    if phase <= contact:
                        z = center - half + speed * phase
                        x = sign * 110
                        up = 4
                        pitch = -rock * math.cos(math.pi * phase / contact)
                    else:
                        q = (phase - contact) / (period - contact)
                        sm = 6 * q ** 5 - 15 * q ** 4 + 10 * q ** 3
                        z = (center + half) * (1 - sm) + (center - half) * sm + (period - contact) * speed * q * (1 - q) * (1 - 2 * q) ** 5
                        x = sign * (110 + 8 * math.sin(math.pi * q) ** 2)
                        up = 4 + lift * math.sin(math.pi * q)
                        pitch = rock * math.cos(math.pi * q) + 10 * math.sin(math.pi * q) ** 2
                    rf, dz, _ = motionsecondary.rolling_foot(vs[foot].tolist(), rotation([0, -sign * 10, 0]).tolist(), pitch)
                    leg(f, hip, knee, foot, x, z + dz, np.array(rf), up)
            if slot:
                w = world(f)
                attitude = w[10, :3, :3].copy()
                # Raise the active hammer carry without shortening either arm segment.
                f[9][3] -= round(15 * 4096 / 360)
                f[9][5] += round(30 * 4096 / 360)
                w = world(f)
                set_rotation(f, 10, w[9, :3, :3].T @ attitude, hist)
            for hand in [7, 10]:
                w = world(f)
                points = vs[hand] @ w[hand, :3, :3].T + w[hand, :3, 3]
                bias = np.array(motionsecondary.clearance_rotation(points.tolist(), w[hand, :3, 3].tolist(), [1, 0, 0], [-65, 0], -8 if not slot or hand == 7 else -75))
                set_rotation(f, hand, w[sk[hand][1], :3, :3].T @ bias @ w[hand, :3, :3], hist)
            if slot:
                w = world(f)
                set_rotation(f, 10, w[9, :3, :3].T @ rotation([0, 20, 0]) @ w[10, :3, :3], hist)
            w = world(f)
            points = np.concatenate([vs[b] @ w[b, :3, :3].T + w[b, :3, 3] for b in [12, 13, 14]])
            bias = np.array(motionsecondary.clearance_rotation(points.tolist(), w[12, :3, 3].tolist(), [1, 0, 0], [0, 40], -8))
            set_rotation(f, 12, w[11, :3, :3].T @ bias @ w[12, :3, :3], hist)
            f[0] = copy.deepcopy(source[0])
            f[0][8] = -speed * t
            poses.append(f)
        poses[-1][1:] = copy.deepcopy(poses[0][1:])
        bones = [7, 10, 12] + ([9] if slot else []) + (list(range(15, 21)) if slot else [])
        channels = {(11, 7)} | {(b, c) for b in bones for c in [3, 4, 5]}
        authored = replace_channels(old.anims.anims[old.anims.table[33]], poses, loop, n, channels)
        if slot:
            authored = _forward(authored, -speed * duration, duration)
            event = next((i for i in old.anims.anims[old.anims.table[slot]].instrs if i['op'] == 'sound'))
            for tick in range(0, duration, period // 2):
                e = dict(event, frame=tick + 1)
                at = next((j for j, i in enumerate(authored.instrs) if i.get('frame', -1) > tick + 1), len(authored.instrs) - 1)
                authored.instrs.insert(at, e)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
        reports.append(dict(slot=slot, period=duration, gait=period, contact=contact, speed=speed, channels=sorted(channels), max_ankle_error=max(errs, default=0)))
    return (new, reports)

def build(data, sk):
    if hashlib.sha256(data).hexdigest()!=SOURCE or len(sk)!=22:
        raise ValueError('Zudomon requires the reviewed pinned 22-bone source')
    old = _parse(data,sk)
    new,solver = _author(old,sk)
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims,new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims,new.anims.table)
    result = new.build()
    actual = _parse(result,sk)
    assert changed_programs(old,actual)==[0,2,3,4]
    assert old.tmd.build()==actual.tmd.build()
    native = old.anims.anims[old.anims.table[33]]
    source,loop,events = animsheet.slot_frames(old,22,33)
    assert len(source)==97 and loop==0
    checks = []
    for row in solver:
        slot = row['slot']
        selected = actual.anims.anims[actual.anims.table[slot]]
        decoded,newloop,newevents = animsheet.slot_frames(actual,22,slot)
        assert len(decoded)==97 and newloop==0
        assert [i for i in native.instrs if i['op'] not in ('key','sound')]==[i for i in selected.instrs if i['op'] not in ('key','sound')]
        assert [(t,k,e)for t,k,e in events if k!='sound']==[(t,k,e)for t,k,e in newevents if k!='sound']
        channels = {tuple(c)for c in row['channels']}
        before = mmd.AnimPlayer(native,22,33)
        after = mmd.AnimPlayer(selected,22,slot)
        cycle = []
        for tick in range(96*9+1):
            assert before.tick()and after.tick()
            assert before.base[:2]==after.base[:2]
            for bone in range(22):
                for channel in range(9):
                    if (bone,channel)not in channels:
                        assert before.pose[bone][channel]==after.pose[bone][channel],(slot,tick,bone,channel)
            if tick<96:
                cycle.append(copy.deepcopy(after.pose))
            else:
                assert after.pose==cycle[tick%96],(slot,tick,'cyclic drift')
        assert after.root[2]==-row['speed']*96*9
        sounds=[i for i in selected.instrs if i['op']=='sound']
        assert all((i['bank'],i['note'])==(1,13)for i in sounds)
        assert len(sounds)==(0 if not slot else 96//(row['gait']//2))
        checks.append(dict(slot=slot,source_template_slot=33,duration=96,old_primary_duration=len(animsheet.slot_frames(old,22,slot)[0])-1,gait_period=row['gait'],forward_units_per_tick=row['speed'],root_XY_native=True,unselected_native33_channels_exact_nine_cycles=True,limb_translations_scales_exact=True,changed_pose_repeat_exact_nine_cycles=True,native33_non_sound_controls_exact=True,footstep_ticks=[i['frame']-1 for i in sounds]))
    storage = motionstorage.audit(result,22)
    assert storage['fits'],storage
    return result,dict(species=219,source_sha256=SOURCE,output_sha256=hashlib.sha256(result).hexdigest(),changed_slots=[0,2,3,4],mesh_skeleton_private33_care_battle_exact=True,restored_native_upper_period=96,checks=checks,solver=solver,storage=storage)
