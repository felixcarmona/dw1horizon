"""Kokuwamon's rigid three-prong boots and articulated mechanical arm carries.

Each shin and its hinged centre toe form a rolling support. Keep the native
head/claw performance and short upper-link lengths, move the hip anchors
outward, and solve the body height from the planted boot. Carry each shoulder
cover with its arm so their original articulation stays together.
"""
import copy
import hashlib
import math
import numeric as np
import mmd
import animsheet
import motionsecondary as S
import motioncyclelayer
import motionstorage
from tools.models.field_animations.channels import replace_channels, coalesce
from tools.models.field_animations.gliding import _forward
from tools.models.field_animations.war_greymon import rotation, set_rotation, align
from motiondiscidentity import changed_programs, program
SOURCE = '3fcd95f06d2dd1b68cfc57a56d38da6c0fcc1df6f6e74ca731a66e9515a84ca7'
OUTPUT = 'cf9e380aae3dcdaefebfa012c13da2230d47abee554012483eff510aeb323ff0'
PARENTS = [-1, 0, 1, 2, 3, 3, 1, 6, 7, 1, 9, 10, 2, 2, 13, 14, 14, 2, 2, 18, 19, 19, 1, 22, 23, 1, 25, 26, 2, 2, 2, 2]

def _parse(data, sk):
    mmd.exe().skeleton[247] = sk
    mmd.exe().bone_count[247] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = 247
    return model

def _author(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    ref = copy.deepcopy(animsheet.slot_frames(old, n, 0)[0][0])
    verts = {b: np.array(old.tmd.obj_verts(o))[:, :3] for b, (o, _) in enumerate(sk) if o >= 0}
    legs = [(6, 7, 8, -1, 0), (9, 10, 11, 1, 0.5)]
    reports = []

    def world(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, g))
    rw = world(ref)
    compound = {boot: np.concatenate([verts[boot], verts[toe] @ np.array(mmd.rot_matrix(*ref[toe][3:6])).T + ref[toe][6:9]]) for hip, boot, toe, sign, offset in legs}
    for slot in [0, 1, 2, 3, 4]:
        fs, loop, events = animsheet.slot_frames(old, n, slot)
        duration = len(fs) - 1
        cycles = {0: 0, 1: 0, 2: 2, 3: 2, 4: 3}[slot]
        period = duration / cycles if cycles else duration
        contact = period * 0.5
        speed = {0: 0, 1: 0, 2: 12, 3: 8, 4: 24}[slot]
        heel = {0: 0, 1: 0, 2: -11, 3: -8, 4: -16}[slot]
        toeangle = {0: 0, 1: 0, 2: 7, 3: 5, 4: 10}[slot]
        frames = []
        plan = []
        hist = {}
        errors = []
        clearance = 4

        def trajectory(t, boot, offset):
            phase = (t + offset * period) % period
            stance = not cycles or phase <= contact + 1e-08
            if not cycles:
                return dict(phase=phase, stance=True, pitch=0, z=1, xout=0)
            _, dz0, _ = S.rolling_foot(compound[boot].tolist(), np.eye(3).tolist(), heel)
            _, dz1, _ = S.rolling_foot(compound[boot].tolist(), np.eye(3).tolist(), toeangle)
            centre = 1 - (dz0 + dz1) / 2
            if stance:
                pitch = heel + (toeangle - heel) * phase / contact
                z = centre - speed * contact / 2 + speed * phase
                xout = 0
            else:
                u = (phase - contact) / (period - contact)
                smooth = 6 * u ** 5 - 15 * u ** 4 + 10 * u ** 3
                z = centre + speed * contact / 2 * (1 - 2 * smooth) + (period - contact) * speed * u * (1 - u) * (1 - 2 * u) ** 5
                pitch = toeangle + (heel - toeangle) * smooth + (period - contact) * (toeangle - heel) / contact * u * (1 - u) * (1 - 2 * u)
                xout = 9 * math.sin(math.pi * u) ** 2
            return dict(phase=phase, stance=stance, pitch=pitch, z=z, xout=xout)
        for t, source in enumerate(fs):
            f = copy.deepcopy(source)
            for b in [8, 11]:
                f[b][3:6] = [0, 0, 0]
            if slot > 1:
                for arm, cover, sign in [(13, 12, -1), (18, 17, 1)]:
                    carry = rotation([0, 0, -sign * 8])
                    anchor = np.array(f[arm][6:9])
                    shift = np.array([sign * 16, 4, 0])
                    f[cover][6:9] = [round(v) for v in anchor + carry @ (np.array(f[cover][6:9]) - anchor) + shift]
                    f[arm][6:9] = [round(v) for v in anchor + shift]
                    for b in [arm, cover]:
                        set_rotation(f, b, carry @ np.array(mmd.rot_matrix(*f[b][3:6])), hist)
                for b, degrees in [(22, 20), (25, -20)]:
                    set_rotation(f, b, rotation([0, 0, degrees]) @ np.array(mmd.rot_matrix(*f[b][3:6])), hist)
            f[6][6] = -28
            f[9][6] = 28
            f[1][7] = 0
            w = world(f)
            targets = []
            heights = []
            for hip, boot, toe, sign, offset in legs:
                a = trajectory(t, boot, offset)
                rf, dz, bottom = S.rolling_foot(compound[boot].tolist(), np.eye(3).tolist(), a['pitch'])
                a.update(foot=boot, toe=toe, x=sign * (60 + a['xout']), z=a['z'] + dz, rf=rf, bottom=bottom)
                h = w[hip, :3, 3]
                L = float(np.linalg.norm(f[boot][6:9]))
                reach = L * L - (a['x'] - h[0]) ** 2 - (a['z'] - h[2]) ** 2
                assert reach > 0, (slot, t, hip, 'unreachable', a, reach)
                a.update(reach=math.sqrt(reach), hip_without_bodyY=h.tolist())
                if a['stance']:
                    heights.append(-clearance - bottom - math.sqrt(reach) - h[1])
                targets.append(a)
            assert heights
            f[1][7] = math.floor(min(heights))
            w = world(f)
            row = []
            for (hip, boot, toe, sign, offset), a in zip(legs, targets):
                h = w[hip, :3, 3]
                goal = np.array([a['x'], h[1] + a['reach'], a['z']])
                R = align(rw[boot, :3, 3] - rw[hip, :3, 3], goal - h) @ rw[hip, :3, :3]
                set_rotation(f, hip, w[1, :3, :3].T @ R, hist)
                w = world(f)
                set_rotation(f, boot, w[hip, :3, :3].T @ np.array(a['rf']), hist)
                w = world(f)
                errors.append(float(np.linalg.norm(w[boot, :3, 3] - goal)))
                row.append(dict(foot=boot, toe=toe, phase=a['phase'], stance=a['stance'], pitch=a['pitch'], target=goal.tolist(), up=-goal[1] - a['bottom'], footX=a['x']))
            frames.append(f)
            plan.append(row)
        frames[-1][1:] = copy.deepcopy(frames[0][1:])
        channels = {(1, 7), (6, 6), (9, 6)} | {(b, c) for b in [6, 7, 8, 9, 10, 11] for c in [3, 4, 5]}
        if slot > 1:
            channels |= {(b, c) for b in [12, 13, 17, 18, 22, 25] for c in [3, 4, 5]} | {(b, c) for b in [12, 13, 17, 18] for c in [6, 7, 8]}
        animation = replace_channels(old.anims.anims[old.anims.table[slot]], frames, 0, n, channels, tolerance=1)
        animation = replace_channels(animation, frames, 0, n, {(1, 7)}, tolerance=0)
        animation, _ = coalesce(animation)
        player = mmd.AnimPlayer(animation, n, slot)
        decoded = []
        while player.tick(stop_at_infinite_loop=True):
            decoded.append(copy.deepcopy(player.pose))
        hist2 = {}
        for tick, f in enumerate(decoded):
            for boot in [7, 10]:
                rf = rotation([plan[tick][0 if boot == 7 else 1]['pitch'], 0, 0])
                w = world(f)
                set_rotation(f, boot, w[sk[boot][1], :3, :3].T @ rf, hist2)
        decoded[-1][1:] = copy.deepcopy(decoded[0][1:])
        animation = replace_channels(animation, decoded, 0, n, {(b, c) for b in [7, 10] for c in [3, 4, 5]}, tolerance=0)
        animation, _ = coalesce(animation)
        sounds = []
        if cycles:
            for ins in animation.instrs:
                if ins['op'] == 'key':
                    for g in ins['bones']:
                        if g['bone'] == 0:
                            g['vals'].pop('tx', None)
                    ins['bones'] = [g for g in ins['bones'] if g['vals']]
            animation = _forward(animation, -speed * duration, duration)
            first = next((i for i in animation.instrs if i['op'] == 'key' and i['frame'] == 1))
            first['bones'].append(dict(bone=0, div=1, vals={'tx': 0}))
            cue = next((i for i in old.anims.anims[old.anims.table[slot]].instrs if i['op'] == 'sound'))
            animation.instrs = [i for i in animation.instrs if i['op'] != 'sound']
            for tick in sorted({round((j + offset) * period) % duration for j in range(cycles) for offset in [0, 0.5]}):
                event = dict(cue, frame=tick + 1)
                at = next((i for i, x in enumerate(animation.instrs) if x.get('frame', -1) > tick + 1), len(animation.instrs) - 1)
                animation.instrs.insert(at, event)
                sounds.append(tick)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(animation)
        reports.append(dict(slot=slot, period=duration, gait_period=period, contact=contact, cycles=cycles, speed=speed, heel=heel, toe=toeangle, maximum_boot_FK_error=max(errors), channels=sorted(channels), plan=plan, footsteps=sounds))
    for a in new.anims.anims:
        a.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    data = new.build()
    actual = mmd.MMD.parse(data, n)
    actual.type = 247
    assert old.tmd.build() == actual.tmd.build()
    assert changed_programs(old, actual) == [0, 1, 2, 3, 4]
    return (data, reports)

def _verify(old, new, sk, solver):
    n = len(sk)
    spec = {'solver': solver}
    assert old.tmd.build() == new.tmd.build() and changed_programs(old, new) == [0, 1, 2, 3, 4]
    checks = []
    for slot in range(len(old.anims.table)):
        if slot in range(5):
            continue
        i, j = (old.anims.table[slot], new.anims.table[slot])
        assert (i is None) == (j is None)
        if i is not None:
            assert program(old.anims.anims[i]) == program(new.anims.anims[j]), slot
    for row in spec['solver']:
        slot = row['slot']
        duration = row['period']
        channels = {tuple(c) for c in row['channels']}
        a = old.anims.anims[old.anims.table[slot]]
        b = new.anims.anims[new.anims.table[slot]]
        before = mmd.AnimPlayer(a, n, slot)
        after = mmd.AnimPlayer(b, n, slot)
        sf, sl, se = animsheet.slot_frames(old, n, slot)
        fs, loop, events = animsheet.slot_frames(new, n, slot)
        assert len(fs) == len(sf) and loop == sl == 0
        first = []
        for tick in range(duration * 9 + 1):
            assert before.tick() and after.tick()
            for bone in range(n):
                assert before.pose[bone][:3] == after.pose[bone][:3]
                if bone == 0:
                    continue
                for c in range(9):
                    if (bone, c) in channels:
                        continue
                    if c in [3, 4, 5]:
                        assert (before.pose[bone][c] - after.pose[bone][c]) % 4096 == 0, (slot, tick, bone, c)
                    else:
                        assert before.pose[bone][c] == after.pose[bone][c], (slot, tick, bone, c)
            assert after.pose[6][6] == before.pose[6][6] - 14 and after.pose[9][6] == before.pose[9][6] + 14
            assert after.pose[7][6:9] == before.pose[7][6:9] and after.pose[10][6:9] == before.pose[10][6:9]
            for bone in [8, 11]:
                assert after.pose[bone][3:6] == [0, 0, 0] and after.pose[bone][6:9] == before.pose[bone][6:9]
            for bone in [2, 3, 4, 5, 14, 15, 16, 19, 20, 21, 23, 24, 26, 27, 28, 29, 30, 31]:
                assert before.pose[bone] == after.pose[bone], (slot, tick, bone)
            assert before.pose[1][:7] == after.pose[1][:7] and before.pose[1][8] == after.pose[1][8]
            if slot < 2:
                assert before.base == after.base
            else:
                assert after.base[:2] == [0, 0] and after.base[2] == (0 if tick == 0 else -{2: 12, 3: 8, 4: 24}[slot]), (slot, tick, after.base)
            if tick < duration:
                first.append(copy.deepcopy(after.pose))
            else:
                assert all(((after.pose[bone][c] - first[tick % duration][bone][c]) % 4096 == 0 if c in [3, 4, 5] else after.pose[bone][c] == first[tick % duration][bone][c] for bone in range(n) for c in range(9))), (slot, tick, 'drift')
        assert [i for i in a.instrs if i['op'] not in ['key', 'sound']] == [i for i in b.instrs if i['op'] not in ['key', 'sound']]
        assert [(t, k, d) for t, k, d in se if k != 'sound'] == [(t, k, d) for t, k, d in events if k != 'sound']
        assert {(i['bank'], i['note']) for i in a.instrs if i['op'] == 'sound'} == {(i['bank'], i['note']) for i in b.instrs if i['op'] == 'sound'}
        if slot > 1:
            sounds = [i['frame'] - 1 for i in b.instrs if i['op'] == 'sound']
            assert sounds == row['footsteps']
        checks.append(dict(slot=slot, period=duration, nine_cycles_protected_local_SRT_and_all_scales_exact=True, nine_cycles_pose_stable=True, original_upperleg_lengths_and_compoundboot_geometry_exact=True, hip_anchor_X_offsets=[-14, 14], head_horns_forearm_claws_appendage_children_exact=True, torso_local_R_X_Z_exact=True, non_sound_events_controls_exact=True, original_footstep_voices_at_landings=True))
    return checks

def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE or len(sk) != 32 or [v[1] for v in sk] != PARENTS or ([v[0] for v in sk] != list(range(-1, 31))):
        raise ValueError('Kokuwamon requires its reviewed 32-bone mechanical beetle source')
    old = _parse(data, sk)
    result, solver = _author(old, sk)
    assert hashlib.sha256(result).hexdigest() == OUTPUT
    checks = _verify(old, _parse(result, sk), sk, solver)
    storage = motionstorage.audit(result, len(sk))
    assert storage['fits'], storage
    return (result, dict(species=247, source_sha256=SOURCE, output_sha256=OUTPUT, changed_slots=[0, 1, 2, 3, 4], solver=solver, checks=checks, storage=storage, mesh_private33_care_battle_streams_exact=True, all_scales_and_original_link_lengths_exact=True, hip_anchor_X_offsets={6: -14, 9: 14}, moving_arm_assembly_carry='Parent-torso Z rotations +8/-8deg; left/right local T shifts -16/+16 X and +4 Y. Covers12/17 follow same rigid carry as arms13/18; forearm/claw local SRT retained.', moving_small_appendage_carry='Roots22/25 local Z +20/-20deg; children unchanged.', reference_validation_limits='Complete compound-boot rolling/contact and mesh diagnostics plus actual-game playback are checked separately. No SDK rounding, all-terrain, turn, transition or continuous-sweep guarantee.'))
