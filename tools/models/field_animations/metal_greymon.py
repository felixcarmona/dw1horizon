"""MetalGreymon's planted dinosaur strides and complete native upper gestures.

Level the pelvis while compensating the torso and tail parent space. Reviewed
fixed ankle attachment offsets clear bulky thigh/foot meshes without stretching
joints during playback. Preserve the distinct tired-idle performance and all
original care/battle programs.
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
import motiontailspace
from tools.models.field_animations.articulation import replace_channels
from tools.models.field_animations.aero_veedramon import _forward
from motiondiscidentity import changed_programs
from tools.models.field_animations.war_greymon import rotation, set_rotation

SOURCE = '1db1618b8978560d8f41cba496e8151923455dfe64fad0248c47a2ea99cbffd5'
PARENTS = [-1, 13, 1, 2, 3, 1, 5, 6, 1, 8, 9, 1, 1, 0, 13, 14, 15, 13, 17, 18, 13, 20, 21]
# Match the reviewed large-partner pace (WarGreymon), including the slower
# condition walk. The same speed drives the planted footprint and entity root:
# increasing just the root would slide the feet through every support phase.
FIELD_SPEEDS = {0: 0, 1: 0, 2: 22, 3: 15, 4: 52}


def _plant(model, anim, slot, vertices, gait, contact):
    """Keep the encoded gait inside the care repair's floor/support band.

    Adjust only the common carrier height: the planted X/Z footprints and
    native limb lengths remain exact. Include engine interpolation thirds.
    """
    from tools.models.field_animations.metal_greymon_care import carrier_offsets
    player = mmd.AnimPlayer(anim, 23, slot)
    decoded = []
    for _ in range(anim.frame_count):
        assert player.tick()
        decoded.append(copy.deepcopy(player.pose))
    for tick, pose in enumerate(decoded):
        pose[0] = [4096] * 3 + [0] * 6
        if slot == 4 and not any((tick - side * gait / 2) % gait <= contact for side in (0, 1)):
            # The run has a real flight phase. Pulling its swinging feet down
            # to the floor turns an otherwise planted run into skating.
            continue
        w = np.array(mmd.bone_matrices(model, pose))
        bottom = max(float((vertices[b] @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max()) for b in (19, 22))
        pose[13][7] -= round(bottom + 1)
    bounds = []
    for tick, (first, second) in enumerate(zip(decoded, decoded[1:])):
        samples = []
        for alpha in (0, 1365, 2730, 4096):
            pose = motiontailspace.interpolate_pose(first, second, alpha)
            w = np.array(mmd.bone_matrices(model, pose))
            lows = {b: float((v @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max()) for b, v in vertices.items()}
            feet = [19, 22]
            if slot == 4:
                time = tick + alpha / 4096
                feet = [foot for side, foot in enumerate(feet)
                        if (time - side * gait / 2) % gait <= contact]
            support = max((lows[b] for b in feet), default=math.inf)
            samples.append((alpha, max(lows.values()), support))
        bounds.append((first[13][7], second[13][7], samples))
    for pose, offset in zip(decoded, carrier_offsets(bounds, 0)):
        pose[13][7] += offset
    return replace_channels(anim, decoded, 0, 23, {(13, 7)}, tolerance=0)


def _parse(data, sk):
    mmd.exe().skeleton[224] = sk
    mmd.exe().bone_count[224] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = 224
    return model

def _author(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    vs = {b: np.array(old.tmd.obj_verts(oi))[:, :3] for b, (oi, _) in enumerate(sk) if oi >= 0}

    def world(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, g))
    # Restore complete native80 gestures; tired idle keeps its own16-tick action.
    native, loop, _ = animsheet.slot_frames(old, n, 33)
    reference = copy.deepcopy(native[0])
    reference[13][3:6] = [204,0,0]
    reference[19][7] += 8
    reference[22][7] += 8
    for right,left in [(17,20),(18,21),(19,22)]:
        reference[left][3:6] = [reference[right][3],-reference[right][4],-reference[right][5]]
    rw = world(reference)
    reports = []
    for slot in [0, 1, 2, 3, 4]:
        fs = animsheet.slot_frames(old,n,1)[0] if slot == 1 else native
        duration = len(fs) - 1
        period = {0: 80, 1: 16, 2: 16, 3: 20, 4: 10}[slot]
        contact = {0: 80, 1: 16, 2: 7, 3: 10, 4: 3}[slot]
        speed = FIELD_SPEEDS[slot]
        lift = {0: 0, 1: 0, 2: 16, 3: 10, 4: 24}[slot]
        rock = {0: 0, 1: 0, 2: 5, 3: 4, 4: 2}[slot]
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
            pole = np.array([1.0 if hip == 17 else -1.0, 0.0, -.6])

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
            set_rotation(f, hip, w[13, :3, :3].T @ rh, hist)
            w = world(f)
            set_rotation(f, knee, w[hip, :3, :3].T @ rs, hist)
            w = world(f)
            set_rotation(f, foot, w[knee, :3, :3].T @ rf, hist)
            errs.append(float(np.linalg.norm(world(f)[foot, :3, 3] - goal)))
        for t, source in enumerate(fs):
            # A mirrored neutral reference matches the reviewed fixed joint spacing.
            native_ref = rw
            f = copy.deepcopy(source)
            f[0] = [4096] * 3 + [0] * 6
            # Level pelvis yaw/roll for forward steps. Preserve the native
            # torso/head/wing attitude through an exact parent-space change.
            original_hip = np.array(mmd.rot_matrix(*source[13][3:6]))
            f[13][3:6] = [204,0,0]
            f[19][7] += 8
            f[22][7] += 8
            neutral_hip = np.array(mmd.rot_matrix(*f[13][3:6]))
            reparent = neutral_hip.T @ original_hip
            for branch in [1,14]:
                set_rotation(f,branch,reparent @ np.array(mmd.rot_matrix(*source[branch][3:6])),hist)
            f[1][6:9] = np.rint(reparent @ np.array(source[1][6:9])).astype(int).tolist()
            f[13][7] = round({0: -220, 1: -220, 2: -224, 3: -224, 4: -216}[slot] + (2 if not slot else 3) * np.sin(2*np.pi*t/duration))
            if slot == 4:
                q = t % (period / 2)
                f[13][7] += round(2 * np.sin(np.pi*q/contact)**2 if q <= contact else -5*np.sin(np.pi*(q-contact)/(period/2-contact))**2)
            if slot in [0,1]:
                for side, (hip, knee, foot) in enumerate([(17,18,19),(20,21,22)]):
                    sign = 1 if side == 0 else -1
                    rf = rotation([0, -sign*20, 0])
                    leg(f, hip, knee, foot, sign*100, 20, np.array(rf), 4)
            else:
                for side, (hip, knee, foot) in enumerate([(17, 18, 19), (20, 21, 22)]):
                    sign = 1 if side == 0 else -1
                    offset = side * period / 2
                    start = math.floor((t - offset) / period) * period + offset
                    phase = t - start
                    half = speed * contact / 2
                    center = 20
                    if phase <= contact:
                        z = center - half + speed * phase
                        x = sign * 100
                        up = 4
                        pitch = -rock * math.cos(math.pi * phase / contact)
                    else:
                        q = (phase - contact) / (period - contact)
                        sm = 6 * q ** 5 - 15 * q ** 4 + 10 * q ** 3
                        z = (center + half) * (1 - sm) + (center - half) * sm + (period - contact) * speed * q * (1 - q) * (1 - 2 * q) ** 5
                        x = sign * (100 + 5 * math.sin(math.pi * q) ** 2)
                        up = 4 + lift * math.sin(math.pi * q)
                        pitch = rock * math.cos(math.pi * q) + 10 * math.sin(math.pi * q) ** 2
                    rf, dz, _ = motionsecondary.rolling_foot(vs[foot].tolist(), rotation([0, -sign * 10, 0]).tolist(), pitch)
                    leg(f, hip, knee, foot, x, z + dz, np.array(rf), up)
            f[14][8] += 8
            if slot in [2,3,4]:
                f[5][5] -= 64
                f[6][3] -= 128
            w = world(f)
            points = vs[7] @ w[7,:3,:3].T + w[7,:3,3]
            bias = np.array(motionsecondary.clearance_rotation(points.tolist(), w[7,:3,3].tolist(), [1,0,0], [-20,0], -4))
            set_rotation(f, 7, w[6,:3,:3].T @ bias @ w[7,:3,:3], hist)
            w = world(f)
            points = np.concatenate([vs[b] @ w[b,:3,:3].T + w[b,:3,3] for b in [14,15,16]])
            bias = np.array(motionsecondary.clearance_rotation(points.tolist(), w[14,:3,3].tolist(), [1,0,0], [0,20], -6))
            set_rotation(f,14,w[13,:3,:3].T @ bias @ w[14,:3,:3],hist)
            f[0] = copy.deepcopy(source[0])
            f[0][8] = -speed * t
            poses.append(f)
        poses[-1][1:] = copy.deepcopy(poses[0][1:])
        bones = [5,6,7,14] + list(range(17,23))
        channels = {(13,7),(14,8),(19,7),(22,7)} | {(13,c)for c in [3,4,5]} | {(1,c)for c in range(3,9)} | {(b,c) for b in bones for c in [3,4,5]}
        authored = replace_channels(old.anims.anims[old.anims.table[1 if slot == 1 else 33]], poses, loop, n, channels)
        if slot in [2,3,4]:
            authored = _forward(authored, -speed * duration, duration)
            event = next((i for i in old.anims.anims[old.anims.table[slot]].instrs if i['op'] == 'sound'))
            for tick in range(0, duration, period // 2):
                e = dict(event, frame=tick + 1)
                at = next((j for j, i in enumerate(authored.instrs) if i.get('frame', -1) > tick + 1), len(authored.instrs) - 1)
                authored.instrs.insert(at, e)
            authored = _plant(old, authored, slot, vs, period, contact)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
        reports.append(dict(slot=slot, period=duration, gait=period, contact=contact, speed=speed, channels=sorted(channels), max_ankle_error=max(errs, default=0)))
    return (new, reports)


def build(data, sk):
    if (hashlib.sha256(data).hexdigest() != SOURCE or [b[1] for b in sk] != PARENTS
            or [b[0] for b in sk] != list(range(-1, 22))):
        raise ValueError('MetalGreymon Vaccine requires the reviewed23-bone source')
    old = _parse(data, sk)
    new, solver = _author(old, sk)
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    actual = _parse(result, sk)
    assert changed_programs(old, actual) == [0, 1, 2, 3, 4]
    assert old.tmd.build() == actual.tmd.build()
    checks = []
    for row in solver:
        slot = row['slot']
        template_slot = 1 if slot == 1 else 33
        template = old.anims.anims[old.anims.table[template_slot]]
        selected = actual.anims.anims[actual.anims.table[slot]]
        original, loop, events = animsheet.slot_frames(old, 23, template_slot)
        decoded, selected_loop, selected_events = animsheet.slot_frames(actual, 23, slot)
        duration = row['period']
        assert len(decoded) == len(original) == duration + 1
        assert loop == selected_loop == 0
        assert [i for i in template.instrs if i['op'] not in ('key', 'sound')] == [i for i in selected.instrs if i['op'] not in ('key', 'sound')]
        assert [(t, k, e) for t, k, e in events if k != 'sound'] == [(t, k, e) for t, k, e in selected_events if k != 'sound']
        channels = {tuple(c) for c in row['channels']}
        before = mmd.AnimPlayer(template, 23, template_slot)
        after = mmd.AnimPlayer(selected, 23, slot)
        cycle = []
        fixed_leg_translations = None
        for tick in range(duration * 9 + 1):
            assert before.tick() and after.tick()
            assert after.root[:2] == before.root[:2] == [0, 0]
            for bone in range(1, 23):
                for channel in range(9):
                    if (bone, channel) not in channels:
                        assert before.pose[bone][channel] == after.pose[bone][channel], (slot, tick, bone, channel)
                assert before.pose[bone][:3] == after.pose[bone][:3]
            assert after.pose[19][7] == before.pose[19][7] + 8
            assert after.pose[22][7] == before.pose[22][7] + 8
            assert after.pose[14][8] == before.pose[14][8] + 8
            leg_translations = [after.pose[b][6:9] for b in range(17, 23)]
            if fixed_leg_translations is None:
                fixed_leg_translations = copy.deepcopy(leg_translations)
            assert leg_translations == fixed_leg_translations
            assert all(after.pose[b][:3] == [4096] * 3 for b in [13, 17, 18, 19, 20, 21, 22])
            if tick < duration:
                cycle.append(copy.deepcopy(after.pose))
            else:
                assert after.pose == cycle[tick % duration], (slot, tick, 'cyclic drift')
        assert after.root[2] == -row['speed'] * duration * 9
        sounds = [i for i in selected.instrs if i['op'] == 'sound']
        assert all((i['bank'], i['note']) == (1, 12) for i in sounds)
        assert len(sounds) == (0 if slot in [0, 1] else duration // (row['gait'] // 2))
        contact_proof = {}
        if slot in (2, 3, 4):
            from tools.models.field_animations.metal_greymon_care import contact
            contact_proof = contact(actual, slot)
            if slot == 4:
                contact_proof['maximum_airborne_clearance'] = contact_proof['maximum_support_clearance']
                floating, airborne = -math.inf, 0
                for tick, pose in enumerate(decoded):
                    for alpha in (0, 1365, 2730):
                        time = tick + alpha / 4096
                        feet = [foot for side, foot in enumerate((19, 22))
                                if (time - side * row['gait'] / 2) % row['gait'] <= row['contact']]
                        if not feet:
                            airborne += 1
                            continue
                        f = motiontailspace.interpolate_pose(pose, decoded[min(tick + 1, duration)], alpha)
                        f[0] = [4096] * 3 + [0] * 6
                        w = np.array(mmd.bone_matrices(actual, f))
                        bottom = max(float((np.array(actual.tmd.obj_verts(sk[b][0]))[:, :3] @
                                            w[b, :3, :3].T + w[b, :3, 3])[:, 1].max()) for b in feet)
                        floating = max(floating, -bottom)
                contact_proof.update(maximum_support_clearance=floating, airborne_samples=airborne)
            assert contact_proof['maximum_floor_y'] <= 2, (slot, contact_proof)
            assert contact_proof['maximum_support_clearance'] <= 4, (slot, contact_proof)
            tracks, bottoms = {}, {}
            for foot in (19, 22):
                vertices = np.array(actual.tmd.obj_verts(sk[foot][0]))[:, :3]
                center = vertices.mean(0)
                tracks[foot], bottoms[foot] = [], []
                for pose in decoded:
                    neutral = copy.deepcopy(pose)
                    neutral[0] = [4096] * 3 + [0] * 6
                    w = np.array(mmd.bone_matrices(actual, neutral))[foot]
                    point = center @ w[:3, :3].T + w[:3, 3]
                    tracks[foot].append(point[[0, 2]] + [pose[0][6], pose[0][8]])
                    bottoms[foot].append(float((vertices @ w[:3, :3].T + w[:3, 3])[:, 1].max()))
            slip = []
            for foot, other in ((19, 22), (22, 19)):
                for tick in range(duration):
                    # Measure actual supporting surfaces, independently of the
                    # authored phase. Otherwise lowering an airborne swing foot
                    # to the floor could hide severe skating outside "stance".
                    if all(bottoms[foot][t] >= -4 and
                           bottoms[foot][t] >= bottoms[other][t] - 1
                           for t in (tick, tick + 1)):
                        slip.append(float(np.linalg.norm(tracks[foot][tick + 1] - tracks[foot][tick])))
            assert slip, slot
            mean_slip = sum(slip) / len(slip)
            assert mean_slip <= max(2, row['speed'] * .08), (slot, mean_slip)
            assert max(slip) <= max(4, row['speed'] * .15), (slot, max(slip))
            contact_proof.update(stance_centroid_mean_units_per_tick=mean_slip,
                                 stance_centroid_max_units_per_tick=max(slip),
                                 stance_samples=len(slip), stance_slip_fraction=mean_slip / row['speed'],
                                 support_selected_from_decoded_surfaces=True)
        maximum_rotation_error = maximum_position_error = 0
        for source, pose in zip(original, decoded):
            a, b = copy.deepcopy(source), copy.deepcopy(pose)
            a[0] = b[0] = [4096] * 3 + [0] * 6
            wa, wb = np.array(mmd.bone_matrices(old, a)), np.array(mmd.bone_matrices(actual, b))
            shift = wb[13, :3, 3] - wa[13, :3, 3]
            for bone in [1, 2, 3, 4, 8, 9, 10, 11, 12]:
                maximum_rotation_error = max(maximum_rotation_error, float(abs(wa[bone, :3, :3] - wb[bone, :3, :3]).max()))
                maximum_position_error = max(maximum_position_error, float(np.linalg.norm(wb[bone, :3, 3] - wa[bone, :3, 3] - shift)))
        assert maximum_rotation_error < .006 and maximum_position_error < 2, (slot, maximum_rotation_error, maximum_position_error)
        checks.append(dict(slot=slot, source_template_slot=template_slot, duration=duration,
                           gait_period=row['gait'], forward_units_per_tick=row['speed'],
                           unselected_template_channels_exact_nine_cycles=True,
                           scales_exact=True, no_within_clip_joint_stretch=True,
                           fixed_joint_translation_offsets={'19.Y': 8, '22.Y': 8, '14.Z': 8},
                           pelvis_rotation=[204, 0, 0], torso_translation_parent_compensated=True,
                           maximum_native_head_wings_metal_arm_world_rotation_error=maximum_rotation_error,
                           maximum_native_upper_joint_position_error_after_carrier_shift=maximum_position_error,
                           pose_repeat_exact_nine_cycles=True,
                           original_non_sound_controls_exact=True,
                           contact=contact_proof,
                           footstep_ticks=[i['frame'] - 1 for i in sounds]))
    storage = motionstorage.audit(result, 23)
    assert storage['fits'], storage
    return result, dict(species=224, source_sha256=SOURCE,
                        output_sha256=hashlib.sha256(result).hexdigest(),
                        changed_slots=[0, 1, 2, 3, 4], mesh_skeleton_private33_care_battle_exact=True,
                        native_upper_period=80, distinct_tired_idle_period=16,
                        checks=checks, solver=solver, storage=storage)
