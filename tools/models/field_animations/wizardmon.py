"""Wizardmon's original field gesture over supported short-legged strides.

Neutral hips and a compensated torso retain the existing 104-tick upper
performance. Both arms carry together around their common shoulder axis;
the separate 20-tick poor idle keeps its bowed posture with a lifted gaze.
Leg segments keep their original lengths and swing their native axes
independently. A precise body carrier avoids vertical boot drift.
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
from tools.models.field_animations.articulation import replace_channels as _replace_channels
from tools.models.field_animations.aero_veedramon import _forward
from motiondiscidentity import changed_programs
from tools.models.field_animations.war_greymon import rotation, set_rotation, align


def replace_channels(original, samples, loop, n, channels, *, tolerance=1):
    # Unselected channels must not force extra shared encoder breakpoints.
    # Their original instructions and initial values remain untouched.
    chosen = copy.deepcopy(samples)
    for f in chosen:
        for b in range(n):
            for c in range(9):
                if (b, c) not in channels:
                    f[b][c] = chosen[0][b][c]
    return _replace_channels(original, chosen, loop, n, channels, tolerance=tolerance)

SOURCE = 'b403f2dca8d9048696e8e41b0ae933d542c708a3582a31bf46dabb0f2dd1ae78'
PARENTS = [-1,13,1,2,3,1,5,6,1,8,9,1,11,0,13,14,15,13,17,18]


def _parse(data, sk):
    mmd.exe().skeleton[241] = sk
    mmd.exe().bone_count[241] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = 241
    return model


def _author(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    native = animsheet.slot_frames(old, n, 0)[0]
    vs = {b: np.array(old.tmd.obj_verts(o))[:, :3] for b, (o, _) in enumerate(sk) if o >= 0}

    def world(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, g))
    ref = copy.deepcopy(native[0])
    ref[13][3:6] = [0,0,0]
    ref[13][8] = 0
    rw = world(ref)
    reports = []
    for slot in [0, 1, 2, 3, 4]:
        template_slot = 1 if slot == 1 else 0
        fs, loop, events = animsheet.slot_frames(old, n, template_slot)
        duration = len(fs) - 1
        cycles = {0: 1, 1: 1, 2: 8, 3: 6, 4: 13}[slot]
        period = duration / cycles
        duty = {0: 1, 1: 1, 2: 0.6, 3: 0.65, 4: 0.3}[slot]
        contact = period * duty
        speed = {0: 0, 1: 0, 2: 8, 3: 6, 4: 22}[slot]
        lift = {0: 0, 1: 0, 2: 8, 3: 5, 4: 9}[slot]
        rock = {0: 0, 1: 0, 2: 3, 3: 2, 4: 5}[slot]
        poses = []
        hist = {}
        errors = []
        plans = []

        def leg(f, hip, knee, foot, x, z, rf, up):
            w = world(f)
            h = w[hip, :3, 3]
            a = np.linalg.norm(f[knee][6:9])
            b = np.linalg.norm(f[foot][6:9])
            reach = (a + b - 0.1) ** 2 - (x - h[0]) ** 2 - (z - h[2]) ** 2
            assert reach > 0, (slot, t, hip, 'XZreach', reach)
            low = h[1] + 1
            high = h[1] + math.sqrt(reach)
            goal = np.array([x, 0.0, z])
            native_direction = rw[foot,:3,3]-rw[hip,:3,3]; native_direction /= np.linalg.norm(native_direction); pole = rw[knee,:3,3]-rw[hip,:3,3]; pole -= native_direction*(pole@native_direction); pole += np.array([10 if hip == 14 else -10,0,0])

            def solve(y):
                goal[1] = y
                delta = goal - h
                dist = np.linalg.norm(delta)
                direction = delta / dist
                pp = pole - direction * (pole @ direction)
                pp /= np.linalg.norm(pp)
                along = (a * a - b * b + dist * dist) / (2 * dist)
                joint = h + direction * along + pp * math.sqrt(max(0, a * a - along * along))
                rh = align(rw[hip,:3,:3]@np.array(f[knee][6:9]),joint-h)@rw[hip,:3,:3]
                rs = align(rw[knee,:3,:3]@np.array(f[foot][6:9]),goal-joint)@rw[knee,:3,:3]
                bottom = max(float((vs[knee] @ rs.T + joint)[:, 1].max()), float((vs[foot] @ rf.T + goal)[:, 1].max()))
                return (bottom + up, rh, rs)
            assert solve(low)[0] <= 0 <= solve(high)[0], (slot, t, hip, 'Yreach', solve(low)[0], solve(high)[0], h, goal)
            for _ in range(27):
                mid = (low + high) / 2
                if solve(mid)[0] > 0:
                    high = mid
                else:
                    low = mid
            residual, rh, rs = solve((low + high) / 2)
            set_rotation(f, hip, w[13, :3, :3].T @ rh, hist)
            w = world(f)
            set_rotation(f, knee, w[hip, :3, :3].T @ rs, hist)
            w = world(f)
            set_rotation(f, foot, w[knee, :3, :3].T @ rf, hist)
            errors.append(float(np.linalg.norm(world(f)[foot, :3, 3] - goal)))
            plans.append(dict(tick=t,foot=foot,ankle=goal.tolist(),orientation=rf.tolist(),up=up,stance=slot in [0,1] or phase<=contact,phase=phase if slot in [2,3,4] else 0))
        for t, source in enumerate(fs):
            f = copy.deepcopy(source)
            f[0] = [4096] * 3 + [0] * 6
            upper = world(f)[1,:3,:3].copy()
            if slot == 3:
                # Keep tired walking distinct while retaining the full gesture.
                upper = rotation([8, 0, 0]) @ upper
            f[13][3:6] = [0,0,0]
            f[13][8] = 0
            set_rotation(f,1,world(f)[13,:3,:3].T@upper,hist)
            f[1][7] = source[1][7]-9
            if slot==1:
                f[2][3]-=round(8*4096/360)
                for b in [11,12]:f[b][3]+=round(1.2*4096/360*math.sin(2*math.pi*t/duration-.4*(b-11)))
            for shoulder in [5,8]:set_rotation(f,shoulder,rotation([-12 if slot==1 else -14,0,0])@np.array(mmd.rot_matrix(*source[shoulder][3:6])),hist)
            if slot in [0, 1]:
                f[13][7] = round(-153)
            if slot in [2, 3, 4]:
                f[13][7] = round({2: -153, 3: -153, 4: -155}[slot])
                if slot in [2, 3]:
                    f[13][7] += round((2 if slot == 2 else 1.5) * math.cos(4 * math.pi * cycles * t / duration))
                if slot == 4:
                    q = 2 * cycles * t % duration / (2 * cycles)
                    half = period / 2
                    f[13][7] += round(2 * math.sin(math.pi * q / contact) ** 2 if q <= contact else -4 * math.sin(math.pi * (q - contact) / (half - contact)) ** 2)
            for side, (hip, knee, foot) in enumerate([(14, 15, 16), (17, 18, 19)]):
                sign = 1 if not side else -1
                center = 0
                if slot in [0, 1]:
                    x = sign * 36
                    z = center
                    up = 4
                    pitch = 0
                else:
                    numerator = (2 * cycles * t - side * duration) % (2 * duration)
                    phase = numerator / (2 * cycles)
                    half = speed * contact / 2
                    if phase <= contact:
                        x = sign * 36
                        z = center - half + speed * phase
                        up = 4
                        pitch = -rock * math.cos(math.pi * phase / contact)
                    else:
                        q = (phase - contact) / (period - contact)
                        smooth = 6 * q ** 5 - 15 * q ** 4 + 10 * q ** 3
                        z = (center + half) * (1 - smooth) + (center - half) * smooth + (period - contact) * speed * q * (1 - q) * (1 - 2 * q) ** 5
                        x = sign * (36 + 3 * math.sin(math.pi * q) ** 2)
                        up = 4 + lift * math.sin(math.pi * q)
                        pitch = rock * math.cos(math.pi * q) + 4 * math.sin(math.pi * q) ** 2
                rf, dz, _ = motionsecondary.rolling_foot(vs[foot].tolist(), rotation([0, 0, 0]).tolist(), pitch)
                leg(f, hip, knee, foot, x, z + dz, np.array(rf), up)
            f[0] = copy.deepcopy(source[0])
            f[0][8] = -speed * t
            poses.append(f)
        for b in range(1, n):
            assert np.max(np.abs(np.array(mmd.rot_matrix(*poses[0][b][3:6])) - np.array(mmd.rot_matrix(*poses[-1][b][3:6])))) < 0.005, (slot, b, 'closure')
        poses[-1][1:] = copy.deepcopy(poses[0][1:])
        channels = {(13,8)} | {(1,7)} | ({(b,3) for b in [2,11,12]} if slot==1 else set()) | {(b,c) for b in [1,5,8,13] for c in [3,4,5]} | {(13, 7)} | {(b,c) for b in range(14,20) for c in [3,4,5]}
        authored = replace_channels(old.anims.anims[old.anims.table[template_slot]], poses, loop, n, channels, tolerance=6)
        # A rounded carrier would introduce vertical boot drift during stance.
        authored = replace_channels(authored,poses,loop,n,{(13,7)},tolerance=0)
        authored.instrs = [i for i in authored.instrs if i['op']!='key' or i['bones']]
        footsteps = []
        if slot in [2, 3, 4]:
            authored = _forward(authored, -speed * duration, duration)
            sound = next((i for i in old.anims.anims[old.anims.table[slot]].instrs if i['op'] == 'sound'))
            footsteps = [round(j * duration / (2 * cycles)) for j in range(2 * cycles)]
            for tick in footsteps:
                event = dict(sound, frame=tick + 1)
                at = next((i for i, k in enumerate(authored.instrs) if k.get('frame', -1) > tick + 1), len(authored.instrs) - 1)
                authored.instrs.insert(at, event)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
        reports.append(dict(slot=slot, source_template=template_slot, duration=duration, cycles=cycles, gait_period=period, contact=contact, speed=speed, footstep_ticks=footsteps, channels=sorted(channels), maximum_FK_ankle_error=max(errors),plans=plans))
    return new, reports


def build(data, sk):
    if (hashlib.sha256(data).hexdigest() != SOURCE or
            [b[1] for b in sk] != PARENTS or [b[0] for b in sk] != list(range(-1,19))):
        raise ValueError('Wizardmon requires the reviewed 20-bone field source')
    old = _parse(data, sk)
    new, solver = _author(old, sk)
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = _parse(result, sk)
    assert changed_programs(old, actual) == [0,1,2,3,4]
    assert old.tmd.build() == actual.tmd.build()
    checks = []
    maximum_grip = 0
    for row in solver:
        slot, template, duration = row['slot'], row['source_template'], row['duration']
        original = old.anims.anims[old.anims.table[template]]
        selected = actual.anims.anims[actual.anims.table[slot]]
        fs, loop, events = animsheet.slot_frames(actual, 20, slot)
        source_fs, source_loop, source_events = animsheet.slot_frames(old,20,template)
        assert len(fs) == len(source_fs) == duration+1 and loop == source_loop == 0
        assert [(t,k,e)for t,k,e in events if k!='sound'] == [(t,k,e)for t,k,e in source_events if k!='sound']
        assert [i for i in original.instrs if i['op']not in ('key','sound')] == [i for i in selected.instrs if i['op']not in ('key','sound')]
        protected = {(b,c)for b in range(1,20)for c in range(9)} - {tuple(c)for c in row['channels']}
        before,after=mmd.AnimPlayer(original,20,template),mmd.AnimPlayer(selected,20,slot)
        cycle=[]
        for tick in range(duration*9+1):
            assert before.tick() and after.tick()
            assert before.root[:2] == after.root[:2] == [0,0]
            for b,c in protected:
                assert before.pose[b][c] == after.pose[b][c], (slot,tick,b,c,'protected')
            assert all(before.pose[b][:3] == after.pose[b][:3] for b in range(1,20))
            assert all(before.pose[b][6:9] == after.pose[b][6:9] for b in range(14,20))
            if tick<duration:
                cycle.append(copy.deepcopy(after.pose))
                wa,wb=[np.array(mmd.bone_matrices(old,f)) for f in [before.pose,after.pose]]
                # Carrying both shoulders about their shared X axis should retain
                # the original glove/staff relation, within encoded angle rounding.
                glove=np.array(old.tmd.obj_verts(sk[7][0]))[:,:3]
                ga=(glove@wa[7,:3,:3].T+wa[7,:3,3]-wa[10,:3,3])@wa[10,:3,:3]
                gb=(glove@wb[7,:3,:3].T+wb[7,:3,3]-wb[10,:3,3])@wb[10,:3,:3]
                maximum_grip=max(maximum_grip,float(np.linalg.norm(ga-gb,axis=1).max()))
            else:
                assert after.pose == cycle[tick%duration],(slot,tick,'repeat')
        assert after.root[2] == -row['speed']*duration*9
        sounds=[i for i in selected.instrs if i['op']=='sound']
        assert [i['frame']-1 for i in sounds] == row['footstep_ticks']
        if slot in [2,3,4]:
            cue=next(i for i in old.anims.anims[old.anims.table[slot]].instrs if i['op']=='sound')
            assert all((i['bank'],i['note'])==(cue['bank'],cue['note'])for i in sounds)
        checks.append(dict(slot=slot,source_template=template,duration=duration,protected_channels_exact_nine_cycles=True,original_scales_and_leg_translations_exact=True,pose_repeats_exact_nine_cycles=True,non_sound_events_and_loop_controls_exact=True,root_cycle_travel=-row['speed']*duration,original_footstep_voice_at_contacts=True))
    assert maximum_grip < 3, maximum_grip
    storage=motionstorage.audit(result,20)
    assert storage['fits'],storage
    return result,dict(species=241,source_sha256=SOURCE,output_sha256=hashlib.sha256(result).hexdigest(),changed_slots=[0,1,2,3,4],checks=checks,solver=solver,storage=storage,mesh_hierarchy_private33_care_battle_exact=True,maximum_encoded_glove_vertices_in_staff_frame_difference=maximum_grip,grip_limits='Per-logical-tick source-relative complete glove vertices in staff10 coordinate frame; original grip geometry retained approximately, no SDK/subframe/transition claim. Source already contains existing intersections.')
