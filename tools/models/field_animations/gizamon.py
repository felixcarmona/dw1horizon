"""Gizamon's supported quadruped bounds with its native head and tail acting.

The short front limbs each have one segment; pin their paired paws through
body-carrier Y/Z instead of stretching them. Native hindleg lengths support
the delayed rear pair. Independent segment swings keep native axial material
orientation steady, and decoded-parent paw counterrotation fixes foot roll.
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
from tools.models.field_animations.gliding import _forward
from motionlab import legik
from tools.models.field_animations.war_greymon import rotation, set_rotation, align
from motiondiscidentity import changed_programs
SOURCE = '8fab6cd94a4d62fb79f945babbfe1882616f4341614e08914c76240f76b24ec8'
PARENTS = [-1, 0, 1, 2, 1, 4, 1, 6, 1, 8, 1, 10, 11, 1, 13, 14]

def _author(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    native = animsheet.slot_frames(old, n, 33)[0]
    vs = {b: np.array(old.tmd.obj_verts(obj))[:, :3] for b, (obj, _) in enumerate(sk) if obj >= 0}

    def world(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, g))
    rw = world(native[0])
    reports = []
    for slot in range(5):
        fs = animsheet.slot_frames(old, n, 1 if slot == 1 else 33)[0]
        duration = len(fs) - 1
        cycles = {0: 0, 1: 0, 2: 7, 3: 5, 4: 8}[slot]
        period = duration / cycles if cycles else duration
        contact = period * {0: 1, 1: 1, 2: 0.6, 3: 0.65, 4: 0.3}[slot]
        oldfs, _, events = animsheet.slot_frames(old, n, slot)
        distance = round({0: 0, 1: 0, 2: 12, 3: 8, 4: 30}[slot] * duration)
        speed = distance / duration
        lift = {0: 0, 1: 0, 2: 18, 3: 14, 4: 28}[slot]
        frames = []
        plan = []
        hist = {}
        errors = []

        def trajectory(t, offset, centre):
            phase = (t + offset * period) % period
            if not cycles:
                return (centre, 6, 0, 0, True)
            if phase <= contact:
                return (centre - speed * contact / 2 + speed * phase, 6, 0, 0, True)
            u = (phase - contact) / (period - contact)
            smooth = 6 * u ** 5 - 15 * u ** 4 + 10 * u ** 3
            half = speed * contact / 2
            z = centre + half * (1 - 2 * smooth) + (period - contact) * speed * u * (1 - u) * (1 - 2 * u) ** 5
            return (z, 6 + lift * math.sin(math.pi * u) ** 2, u, math.sin(math.pi * u) ** 2, False)
        for t, source in enumerate(fs):
            f = copy.deepcopy(source)
            f[0] = [4096] * 3 + [0] * 6
            f[0][8] = -round(speed * t)
            if slot == 1:
                breath = math.sin(2 * math.pi * t / duration)
                f[2][3] += round((4 + 0.7 * breath) * 4096 / 360)
                f[3][3] += round(0.5 * breath * 4096 / 360)
            z, up, u, tuck, stance = trajectory(t, 0, -66)
            body_pitch = 0 if not cycles else 2 * math.sin(2 * math.pi * u) * math.sin(math.pi * u)
            f[1][3] += round(body_pitch * 4096 / 360)
            if not cycles:
                fore_swing = 0
            elif stance:
                fore_swing = -4 + 16 * (t % period) / contact
            else:
                smooth = 6 * u ** 5 - 15 * u ** 4 + 10 * u ** 3
                fore_swing = 12 * (1 - smooth) - 4 * smooth + 8 * tuck + (period - contact) * (16 / contact) * u * (1 - u) * (1 - 2 * u) ** 5
            frontX = 74
            frontRf = rotation([-6 * tuck, 0, 0])
            for hip, foot, sign in [(4, 5, 1), (6, 7, -1)]:
                local = np.array(mmd.rot_matrix(*f[hip][3:6])) @ rotation([fore_swing, 0, 0])
                segment = np.array(f[foot][6:9])
                v = local @ segment
                dx = sign * (frontX - 54)
                radius = math.sqrt(float(segment @ segment) - dx * dx)
                target = np.r_[dx, v[1:] * radius / np.linalg.norm(v[1:])]
                local = align(v, target) @ local
                set_rotation(f, hip, local, hist)
                w = world(f)
                set_rotation(f, foot, w[hip, :3, :3].T @ frontRf, hist)
            w = world(f)
            floor = max((float((vs[b] @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max()) for b in [5, 7]))
            forez = float((w[5, 2, 3] + w[7, 2, 3]) / 2)
            f[1][7] += round(-up - floor)
            f[1][8] += round(z - forez)
            row = [dict(foot=b, stance=stance, phase=t % period, target_X=sign * frontX, target_Z=z, up=up, pitch=-6 * tuck) for b, sign in [(5, 1), (7, -1)]]
            backz, backup, bu, btuck, bstance = trajectory(t, 0.22, 46 if slot == 3 else 40 if cycles else 18)
            for hip, knee, foot, sign in [(10, 11, 12, 1), (13, 14, 15, -1)]:
                rf = rotation([8 * btuck, 0, 0]) @ rotation([0, -sign * (20 if slot == 3 else 15) if cycles else 0, 0]) @ rw[foot, :3, :3]
                bottom = float((vs[foot] @ rf.T)[:, 1].max())
                goal = np.array([sign * (120 if cycles else 116), -backup - bottom, backz])
                w = world(f)
                root = w[hip, :3, 3]
                reference = [rw[b, :3, 3].tolist() for b in [hip, knee, foot]]
                pole = motionsecondary.transported_native_pole(*reference, root.tolist(), goal.tolist())
                pole[0] += sign * 20
                solved = legik.solve(root.tolist(), goal.tolist(), float(np.linalg.norm(f[knee][6:9])), float(np.linalg.norm(f[foot][6:9])), pole)
                rh, rk = map(np.array, motionsecondary.native_plane_rotations(reference, [root.tolist(), *solved], [rw[b, :3, :3].tolist() for b in [hip, knee]]))
                if cycles:
                    joint, end = map(np.array, solved)
                    rh = align(rw[knee, :3, 3] - rw[hip, :3, 3], joint - root) @ rw[hip, :3, :3]
                    rk = align(rw[foot, :3, 3] - rw[knee, :3, 3], end - joint) @ rw[knee, :3, :3]
                set_rotation(f, hip, w[1, :3, :3].T @ rh, hist)
                w = world(f)
                set_rotation(f, knee, w[hip, :3, :3].T @ rk, hist)
                w = world(f)
                set_rotation(f, foot, w[knee, :3, :3].T @ rf, hist)
                w = world(f)
                errors.append(float(np.linalg.norm(w[foot, :3, 3] - goal)))
                row.append(dict(foot=foot, stance=bstance, phase=(t + 0.22 * period) % period, target_X=goal[0], target_Z=backz, up=backup, pitch=8 * btuck))
            frames.append(f)
            plan.append(row)
        needed = []
        for f in frames[:-1]:
            w = world(f)
            points = [v.tolist() for b in [8, 9] for v in vs[b] @ w[b, :3, :3].T + w[b, :3, 3]]
            hinge = np.array(motionsecondary.clearance_rotation(points, w[8, :3, 3].tolist(), w[1, :3, 0].tolist(), [0, 30], -6))
            needed.append(math.degrees(math.acos(np.clip((np.trace(hinge) - 1) / 2, -1, 1))))
        envelope = [max((needed[j] - 2 * min((i - j) % duration, (j - i) % duration) for j in range(duration))) for i in range(duration)]
        for t, f in enumerate(frames):
            set_rotation(f, 8, rotation([envelope[t % duration], 0, 0]) @ np.array(mmd.rot_matrix(*f[8][3:6])), hist)
        frames[-1][1:] = copy.deepcopy(frames[0][1:])
        sound_events = []
        if cycles:
            payload = next((cue for _, kind, cue in events if kind == 'sound'))
            sound_events = [(tick, 'sound', payload) for tick in sorted((round((k + phase) * period) for k in range(cycles) for phase in [0, 0.78]))]
        template = old.anims.anims[old.anims.table[1 if slot == 1 else 33]]
        channels = {(1, 3), (1, 7), (1, 8)} | {(b, c) for b in [4, 5, 6, 7, 10, 11, 12, 13, 14, 15] for c in [3, 4, 5]}
        if slot == 1:
            channels |= {(2, 3), (3, 3)} | {(8, c) for c in [3, 4, 5]}
        else:
            assert max(envelope) == 0
        animation = replace_channels(template, frames, 0, n, channels, tolerance=1)
        animation = replace_channels(animation, frames, 0, n, {(1, 7), (1, 8)}, tolerance=0)
        player = mmd.AnimPlayer(animation, n, slot)
        decoded = []
        while player.tick(stop_at_infinite_loop=True):
            decoded.append(copy.deepcopy(player.pose))
        correction_history = {}
        for tick, pose in enumerate(decoded):
            for info in plan[tick]:
                foot = info['foot']
                rf = rotation([info['pitch'], 0, 0])
                if foot in [12, 15]:
                    rf = rf @ rotation([0, -(1 if foot == 12 else -1) * (20 if slot == 3 else 15) if cycles else 0, 0]) @ rw[foot, :3, :3]
                parent = world(pose)[sk[foot][1], :3, :3]
                set_rotation(pose, foot, parent.T @ rf, correction_history)
        decoded[-1][1:] = copy.deepcopy(decoded[0][1:])
        animation = replace_channels(animation, decoded, 0, n, {(b, c) for b in [5, 7, 12, 15] for c in [3, 4, 5]}, tolerance=0)
        if cycles:
            animation = _forward(animation, -distance, duration)
        mapped_sounds = []
        for tick, kind, payload in sound_events:
            cue = dict(op='sound', frame=tick + 1, bank=payload['bank'], note=payload['note'])
            at = next((j for j, i in enumerate(animation.instrs) if i.get('frame', -1) > tick + 1), len(animation.instrs) - 1)
            animation.instrs.insert(at, cue)
            mapped_sounds.append(cue)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(animation)
        reports.append(dict(channels=sorted(channels), footstep_events=mapped_sounds, back_center_z=46 if slot == 3 else 40 if cycles else 18, rear_yaw_degrees=(20 if slot == 3 else 15) if cycles else 0, slot=slot, period=duration, gait_period=period, cycles=cycles, contact=contact, speed=speed, net_travel=-distance, foreX=frontX, backX=120 if cycles else 116, lift=lift, maximum_ankle_FK_error=max(errors), tail_carry_maximum=max(envelope), plan=plan))
    return (new, reports)

def build(data, sk):
    if (hashlib.sha256(data).hexdigest() != SOURCE
            or [b[1] for b in sk] != PARENTS
            or [b[0] for b in sk] != list(range(-1, 15))):
        raise ValueError('Gizamon requires its reviewed sixteen-bone source')
    n = len(sk)
    mmd.exe().skeleton[239] = sk
    mmd.exe().bone_count[239] = n
    old = mmd.MMD.parse(data, n)
    old.type = 239
    new, solver = _author(old, sk)
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = mmd.MMD.parse(result, n)
    actual.type = 239
    assert changed_programs(old, actual) == [0, 1, 2, 3, 4]
    assert old.tmd.build() == actual.tmd.build()
    checks = []
    for row in solver:
        slot = row['slot']
        period = row['period']
        channels = set(map(tuple, row['channels']))
        source = old.anims.anims[old.anims.table[1 if slot == 1 else 33]]
        selected = actual.anims.anims[actual.anims.table[slot]]
        before = mmd.AnimPlayer(source, n, slot)
        after = mmd.AnimPlayer(selected, n, slot)
        cycle = []
        previous = None
        maximum_step = 0
        for t in range(period * 9 + 1):
            assert before.tick() and after.tick()
            for b in range(1, n):
                for c in range(9):
                    if (b, c) not in channels:
                        assert before.pose[b][c] == after.pose[b][c], (slot, t, b, c, 'protected channel')
            assert list(after.root) == [0, 0, -row['speed'] * t], (slot, t, 'steady navigation')
            if previous is not None:
                maximum_step = max(maximum_step, max((abs(after.pose[b][c] - previous[b][c]) for b in range(1, n) for c in [3, 4, 5])))
            previous = copy.deepcopy(after.pose)
            if t < period:
                cycle.append(copy.deepcopy(after.pose[1:]))
            else:
                assert after.pose[1:] == cycle[t % period], (slot, t, 'cycle drift')
        assert maximum_step < 512, (slot, maximum_step, 'abrupt Euler step or spin')
        sounds = [cue for _, kind, cue in animsheet.slot_frames(actual, n, slot)[2] if kind == 'sound']
        assert sounds == row['footstep_events'], (slot, 'contact sound timing')
        assert all((cue['bank'] == 1 and cue['note'] == 11 for cue in sounds))
        assert [i for i in selected.instrs if i['op'] not in ['key', 'sound']] == [i for i in source.instrs if i['op'] not in ['key', 'sound']]
        checks.append(dict(slot=slot, nine_cycles_pose_repeat_exact=True, protected_source_local_SRT_exact=True, all_scales_and_limb_translations_except_body1YZ_exact=True, full_native83_head_jaw_tail_exact=slot != 1, maximum_raw_logical_rotation_step=maximum_step, source_loop_controls_exact=True, footstep_bank_note_and_fore_rear_contact_phases_verified=True, steady_root_speed=row['speed']))
    storage = motionstorage.audit(result, n)
    assert storage['fits'], storage
    return (result, dict(species=239, source_sha256=SOURCE, output_sha256=hashlib.sha256(result).hexdigest(), changed_slots=[0, 1, 2, 3, 4], checks=checks, solver=solver, storage=storage, mesh_private33_care_battle_exact=True))
