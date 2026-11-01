"""Apemon: native hopping idle and planted diagonal knuckle locomotion.

Keep the distinct 93/20/43/20/20-tick performances. Preserve upper gestures,
fit the right hip anchor, carry the rigid staff above the limbs, and bound
running pelvis roll. Walk/condition/run travel 20/14/35 units per tick with four/two/three gait
cycles and 0.4/0.5/0.25 stance duty. Four ordinary MMD limb chains support movement.
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

SOURCE = '94cdb10573b037c25cd9003f03bd5f6c7d41e0fe01c10e229a602a54210d2ba1'
PARENTS = [-1, 9, 1, 1, 3, 4, 1, 6, 7, 0, 9, 10, 11, 9, 13, 14, 1]

def _parse(data, sk):
    mmd.exe().skeleton[227] = sk
    mmd.exe().bone_count[227] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = 227
    return model



def _author(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    native = animsheet.slot_frames(old, n, 33)[0]
    vs = {b: np.array(old.tmd.obj_verts(o))[:, :3] for b, (o, _) in enumerate(sk) if o >= 0}

    def world(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, g))
    ref = copy.deepcopy(native[0])
    for a, b in [(3, 6), (4, 7), (5, 8), (10, 13), (11, 14), (12, 15)]:
        ref[b][3:6] = [ref[a][3], -ref[a][4], -ref[a][5]]
    rw = world(ref)
    reports = []
    for slot in [0, 1, 2, 3, 4]:
        template = 33 if slot == 0 else slot
        fs, loop, events = animsheet.slot_frames(old, n, template)
        duration = len(fs) - 1
        cycles = {0: 1, 1: 1, 2: 4, 3: 2, 4: 3}[slot]
        period = duration / cycles
        duty = {0: 1, 1: 1, 2: 0.4, 3: 0.5, 4: 0.25}[slot]
        contact = period * duty
        speed = {0: 0, 1: 0, 2: 20, 3: 14, 4: 35}[slot]
        poses = []
        hist = {}
        errors = []
        mean = np.mean([f[9][7] for f in fs[:-1]])
        if slot == 0:
            required = []
            for source in fs[:-1]:
                w = world(source)
                ground = max((float((v @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max()) for b, v in vs.items()))
                required.append(max(0, ground + 6))
            envelope = [max((required[j] - 0.8 * min(abs(i - j), duration - abs(i - j)) ** 2 for j in range(duration))) for i in range(duration)]

        def limb(f, hip, knee, foot, x, z, rf, up, front):
            w = world(f)
            h = w[hip, :3, 3]
            a = np.linalg.norm(f[knee][6:9])
            b = np.linalg.norm(f[foot][6:9])
            reach = (a + b - 0.1) ** 2 - (x - h[0]) ** 2 - (z - h[2]) ** 2
            assert reach > 0, (slot, t, hip, 'XZreach', reach)
            low = h[1] + max(1, math.sqrt(max(0, (abs(a - b) + 0.1) ** 2 - (x - h[0]) ** 2 - (z - h[2]) ** 2)))
            high = h[1] + math.sqrt(reach)
            goal = np.array([x, 0.0, z])
            sign = 1 if hip in [3, 10] else -1
            pole = np.array([sign, 0, -0.2 if front else 0 if slot == 2 and hip == 10 else -0.5])

            def solve(y):
                goal[1] = y
                delta = goal - h
                dist = np.linalg.norm(delta)
                direction = delta / dist
                pp = pole - direction * (pole @ direction)
                pp /= np.linalg.norm(pp)
                along = (a * a - b * b + dist * dist) / (2 * dist)
                joint = h + direction * along + pp * math.sqrt(max(0, a * a - along * along))
                rh, rs = map(np.array, motionsecondary.native_plane_rotations([rw[v, :3, 3].tolist() for v in [hip, knee, foot]], [h.tolist(), joint.tolist(), goal.tolist()], [rw[v, :3, :3].tolist() for v in [hip, knee]]))
                bottom = max(float((vs[knee] @ rs.T + joint)[:, 1].max()), float((vs[foot] @ rf.T + goal)[:, 1].max()))
                return (bottom + up, rh, rs)
            assert solve(low)[0] <= 0 <= solve(high)[0], (slot, t, hip, 'Yreach', solve(low)[0], solve(high)[0], h, goal)
            for _ in range(27):
                mid = (low + high) / 2
                if solve(mid)[0] > 0:
                    high = mid
                else:
                    low = mid
            _, rh, rs = solve((low + high) / 2)
            set_rotation(f, hip, w[sk[hip][1], :3, :3].T @ rh, hist)
            w = world(f)
            set_rotation(f, knee, w[hip, :3, :3].T @ rs, hist)
            w = world(f)
            set_rotation(f, foot, w[knee, :3, :3].T @ rf, hist)
            errors.append(float(np.linalg.norm(world(f)[foot, :3, 3] - goal)))
        for t, source in enumerate(fs):
            original_world = world(source)
            f = copy.deepcopy(source)
            f[0] = [4096] * 3 + [0] * 6
            if slot == 0:
                f[9][7] -= math.ceil(envelope[t % duration])
            else:
                f[10][6] += 8
                f[16][8] += 60
                f[16][3:6] = [0, 0, 228]
                f[9][7] = round({1: -150, 2: -145, 3: -141, 4: -138}[slot] + 0.3 * (source[9][7] - mean))
                if slot == 4:
                    f[9][5] = round(170 + 0.4 * (source[9][5] - 170))
                    q = 2 * cycles * t % duration / (2 * cycles)
                    half = period / 2
                    f[9][7] += round(2 * math.sin(math.pi * q / contact) ** 2 if q <= contact else -5 * math.sin(math.pi * (q - contact) / (half - contact)) ** 2)
                for side, (hip, knee, foot, front) in enumerate([(10, 11, 12, False), (13, 14, 15, False), (3, 4, 5, True), (6, 7, 8, True)]):
                    sign = 1 if side % 2 == 0 else -1
                    offset = (side % 2 + (1 if front else 0)) % 2
                    xc = 170 if front else 65
                    zc = -55 if front else 60
                    if slot == 1:
                        x = sign * xc
                        z = zc
                        up = 4
                        pitch = 0
                    else:
                        phase = (2 * cycles * t - offset * duration) % (2 * duration) / (2 * cycles)
                        half = speed * contact / 2
                        rock = {2: 3, 3: 2, 4: 5}[slot] * (0.6 if front else 1)
                        if phase <= contact:
                            x = sign * xc
                            z = zc - half + speed * phase
                            up = 4
                            pitch = -rock * math.cos(math.pi * phase / contact)
                        else:
                            q = (phase - contact) / (period - contact)
                            smooth = 6 * q ** 5 - 15 * q ** 4 + 10 * q ** 3
                            z = zc + half * (1 - smooth) - half * smooth + (period - contact) * speed * q * (1 - q) * (1 - 2 * q) ** 5
                            x = sign * (xc + 3 * math.sin(math.pi * q) ** 2)
                            up = 4 + ({2: 18, 3: 10, 4: 30}[slot] if front else {2: 12, 3: 8, 4: 20}[slot]) * math.sin(math.pi * q)
                            pitch = rock * math.cos(math.pi * q) + 4 * math.sin(math.pi * q) ** 2
                    rf, dz, _ = motionsecondary.rolling_foot(vs[foot].tolist(), rotation([0, 0, 0]).tolist(), pitch)
                    limb(f, hip, knee, foot, x, z + dz, np.array(rf), up, front)
            f[0][6:9] = [0, 0, -speed * t]
            poses.append(f)
        for b in range(1, n):
            assert np.max(np.abs(np.array(mmd.rot_matrix(*poses[0][b][3:6])) - np.array(mmd.rot_matrix(*poses[-1][b][3:6])))) < 0.005, (slot, b, 'closure')
        poses[-1][1:] = copy.deepcopy(poses[0][1:])
        channels = {(9, 7), (0, 6), (0, 7)} | ({(9, 5)} if slot == 4 else set()) | ({(16, c) for c in [3, 4, 5, 8]} | {(10, 6)} if slot else set()) | ({(b, c) for b in [3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15] for c in [3, 4, 5]} if slot else set())
        authored = replace_channels(old.anims.anims[old.anims.table[template]], poses, loop, n, channels)
        footsteps = []
        if slot in [2, 3, 4]:
            authored = _forward(authored, -speed * duration, duration)
            authored.instrs = [i for i in authored.instrs if i['op'] != 'sound']
            sound = next((i for i in old.anims.anims[old.anims.table[slot]].instrs if i['op'] == 'sound'))
            footsteps = [round(j * duration / (2 * cycles)) for j in range(2 * cycles)]
            for tick in footsteps:
                event = dict(sound, frame=tick + 1)
                at = next((i for i, k in enumerate(authored.instrs) if k.get('frame', -1) > tick + 1), len(authored.instrs) - 1)
                authored.instrs.insert(at, event)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
        reports.append(dict(slot=slot, source_template=template, duration=duration, cycles=cycles, gait_period=period, contact=contact, speed=speed, footstep_ticks=footsteps, channels=sorted(channels), maximum_FK_contact_error=max(errors, default=0)))
    return (new, reports)


def build(data, sk):
    if (hashlib.sha256(data).hexdigest() != SOURCE or [b[1] for b in sk] != PARENTS
            or [b[0] for b in sk] != list(range(-1,16))):
        raise ValueError('Apemon requires the reviewed17-bone source')
    old = _parse(data, sk)
    new, solver = _author(old, sk)
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims,new.anims.table)
    result = new.build()
    actual = _parse(result, sk)
    assert changed_programs(old,actual) == [0,1,2,3,4]
    assert old.tmd.build() == actual.tmd.build()
    checks = []
    limbs = [3,4,5,6,7,8,10,11,12,13,14,15]
    for row in solver:
        slot, template, duration = row['slot'],row['source_template'],row['duration']
        src = old.anims.anims[old.anims.table[template]]
        dst = actual.anims.anims[actual.anims.table[slot]]
        channels = {tuple(c) for c in row['channels']}
        fs,loop,events = animsheet.slot_frames(actual,17,slot)
        original,oloop,oevents = animsheet.slot_frames(old,17,template)
        assert len(fs) == len(original) == duration+1 and loop == oloop == 0
        assert [i for i in src.instrs if i['op'] not in ('key','sound')] == [i for i in dst.instrs if i['op'] not in ('key','sound')]
        assert [(t,k,e) for t,k,e in events if k != 'sound'] == [(t,k,e) for t,k,e in oevents if k != 'sound']
        before,after = mmd.AnimPlayer(src,17,template),mmd.AnimPlayer(dst,17,slot)
        cycle = []
        fixed = None
        for tick in range(duration*9+1):
            assert before.tick() and after.tick()
            assert after.root[:2] == [0,0]
            for bone in range(1,17):
                assert before.pose[bone][:3] == after.pose[bone][:3]
                for c in range(9):
                    if (bone,c) not in channels:
                        assert before.pose[bone][c] == after.pose[bone][c],(slot,tick,bone,c)
            translations = [after.pose[b][6:9] for b in limbs]
            if fixed is None: fixed = copy.deepcopy(translations)
            assert translations == fixed
            for b in limbs:
                expected = list(before.pose[b][6:9])
                if slot != 0 and b == 10: expected[0] += 8
                assert after.pose[b][6:9] == expected,(slot,tick,b,'jointT')
            if tick < duration: cycle.append(copy.deepcopy(after.pose))
            else: assert after.pose == cycle[tick % duration],(slot,tick,'cyclic drift')
        assert after.root[2] == -row['speed']*duration*9
        sounds = [i for i in dst.instrs if i['op']=='sound']
        assert [i['frame']-1 for i in sounds] == row['footstep_ticks']
        assert all((i['bank'],i['note'])==(1,16) for i in sounds)
        assert len(sounds) == (0 if slot in [0,1] else 2*row['cycles'])
        checks.append(dict(slot=slot,source_template_slot=template,duration=duration,gait_period=row['gait_period'],forward_units_per_tick=row['speed'],unselected_native_channels_exact_nine_cycles=True,original_scales_exact=True,torso_head_local_gestures_exact=True,upper_lower_limb_segment_lengths_preserved=True,right_hip_anchor_X_offset=0 if slot==0 else 8,no_within_clip_limb_stretch=True,pose_repeat_exact_nine_cycles=True,original_non_sound_controls_exact=True,footstep_ticks=row['footstep_ticks']))
    storage = motionstorage.audit(result,17)
    assert storage['fits'],storage
    return result,dict(species=227,source_sha256=SOURCE,output_sha256=hashlib.sha256(result).hexdigest(),changed_slots=[0,1,2,3,4],mesh_skeleton_hierarchy_private33_care_battle_exact=True,native_idle_period=93,distinct_tired_idle_period=20,original_per_action_gesture_periods_retained={'1':20,'2':43,'3':20,'4':20},checks=checks,solver=solver,storage=storage)
