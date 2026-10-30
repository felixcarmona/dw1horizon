#!/usr/bin/env python3
"""MagnaAngemon's supported boots and articulated waist feathers.

Explicit recipe for the reviewed source. Retains upper acting and aerial run;
keeps the compound shin/toe boot above the reference floor, and opens separate
feather panels without rotating the whole skirt into the torso.
"""
import copy
import hashlib
import math
import numeric as np
import mmd
import animsheet
import motioncyclelayer
import motionsecondary
import motionstorage
from tools.models.field_animations.articulation import replace_channels
from tools.models.field_animations.war_greymon import rotation, set_rotation
SOURCE = '6c3a0d4d6c9518614a2eb310039d055710fff9361fceb4e5ea01ee32abf0a7a9'
CHAINS = [(19, 20, 21), (22, 23, 24)]
PANEL_GROUPS = [[2, 3, 4, 5, 6, 12, 13, 14, 18, 20, 21, 24], [7, 8, 9, 10, 11, 15, 16, 17, 19, 22, 23, 25]]
PIVOTS = [[-40, 20, -80], [40, 20, -80]]

def _pack(model):
    for anim in model.anims.anims:
        anim.tail = b''
    model.anims.anims, model.anims.table = motioncyclelayer.share_identical_streams(model.anims.anims, model.anims.table)
    return model.build()

def _parse(data, sk):
    mmd.exe().skeleton[206] = sk
    mmd.exe().bone_count[206] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = 206
    return model

def _supported_steps(old, sk):
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
    for slot in [2, 3, 4]:
        fs, loop, events = animsheet.slot_frames(old, n, slot)
        duration = len(fs) - 1
        ws = np.array([world(f) for f in fs])
        root = np.array(fs)[:, 0]
        period = 20
        contact = {2: 2, 3: 3, 4: 2}[slot]
        lift = {2: 20, 3: 13, 4: 32}[slot]
        rock = {2: 4, 3: 3, 4: 7}[slot]

        def at(t):
            cy = math.floor(t / duration)
            phase = t - cy * duration
            i = min(int(phase), duration - 1)
            q = phase - i
            return cy * (root[-1, 8] - root[0, 8]) + root[i, 8] * (1 - q) + root[i + 1, 8] * q - root[0, 8]

        def xat(t):
            cy = math.floor(t / duration)
            phase = t - cy * duration
            i = min(int(phase), duration - 1)
            q = phase - i
            return cy * (root[-1, 6] - root[0, 6]) + root[i, 6] * (1 - q) + root[i + 1, 6] * q - root[0, 6]
        goals = {}
        for side, (hip, knee, foot) in enumerate(chains):
            centers = float(ws[:-1, hip, 2, 3].mean())
            gs = []
            upv = []
            rs = []
            for t in range(len(fs)):
                start = math.floor((t + side * period / 2) / period) * period - side * period / 2
                phase = t - start
                travel = at(start) - at(start + contact)
                if phase <= contact:
                    z = centers - travel / 2 - (at(t) - at(start))
                    up = 0
                    pitch = -rock * math.cos(math.pi * phase / contact)
                else:
                    span = period - contact
                    q = (phase - contact) / span
                    a = centers + travel / 2
                    b = centers - (at(start + period) - at(start + period + contact)) / 2
                    # Recovery turns during flight; stance uses exact root deltas.
                    z = (2 * q ** 3 - 3 * q * q + 1) * a + (-2 * q ** 3 + 3 * q * q) * b
                    up = lift * math.sin(math.pi * q) ** 2
                    pitch = rock * math.cos(math.pi * q)
                x = rw[foot, 0, 3] - xat(t) + xat(start)
                if phase > contact:
                    x += (xat(start + period) - xat(start)) * (3 * q * q - 2 * q * q * q)
                gs.append(np.array([x, 0.0, z]))
                upv.append(up)
                rs.append(rotation([pitch, 0, 0]) @ rw[foot, :3, :3])
            goals[foot] = (gs, upv, rs)
        for side, foot in enumerate(goals):
            gs, upv, rs = goals[foot]
            for j in range(len(fs)):
                phase = (j + side * period / 2) % period
                gate = 0.0 if phase <= contact else min(1.0, (phase - contact) / 2, (period - phase) / 2)
                gate = 3 * gate * gate - 2 * gate * gate * gate
                upv[j] += max(0.0, (-184 if slot == 4 else -196) - ws[j, 18, 1, 3]) * gate
        poses = []
        hist = {}
        maxerr = 0
        minmargin = 1000000000.0
        body = []
        lifts = []
        for i, original in enumerate(fs):
            f = copy.deepcopy(original)
            f[0] = [4096] * 3 + [0] * 6
            desired = -182 + {2: 0.6, 3: 0.5}.get(slot, 1) * (ws[i, 18, 1, 3] + 196) if slot != 4 else ws[i, 18, 1, 3] + 18
            offset = desired - ws[i, 18, 1, 3]
            f[18][7] += round(offset)
            body.append(offset)
            for side, (hip, knee, foot) in enumerate(chains):
                w = np.array(mmd.bone_matrices(old, f))
                h = w[hip, :3, 3]
                a = np.linalg.norm(f[knee][6:9])
                b = np.linalg.norm(f[foot][6:9])
                goal, upv, rs = goals[foot]
                target = goal[i].copy()
                rfoot = rs[i]
                dxz = np.sum((target[[0, 2]] - h[[0, 2]]) ** 2)
                assert dxz < (a + b - 0.1) ** 2, (slot, i, hip, 'horizontalreach')
                ymax = h[1] + math.sqrt((a + b - 0.1) ** 2 - dxz)
                ymin = h[1] + 1
                pole = np.array([0.65 if side == 0 else -0.65, 0.0, -1.0])

                def solve(y):
                    target[1] = y
                    delta = target - h
                    dist = np.linalg.norm(delta)
                    direction = delta / dist
                    pp = pole - direction * (pole @ direction)
                    pp /= np.linalg.norm(pp)
                    along = (a * a - b * b + dist * dist) / (2 * dist)
                    joint = h + direction * along + pp * math.sqrt(max(0, a * a - along * along))
                    rots = motionsecondary.native_plane_rotations([rw[v, :3, 3].tolist() for v in [hip, knee, foot]], [h.tolist(), joint.tolist(), target.tolist()], [rw[v, :3, :3].tolist() for v in [hip, knee]])
                    rhip, rshin = map(np.array, rots)
                    sole = max(float((vs[knee] @ rshin.T + joint)[:, 1].max()), float((vs[foot] @ rfoot.T + target)[:, 1].max()))
                    return (sole + upv[i], joint, rhip, rshin)
                low, high = (ymin, ymax)
                elo = solve(low)[0]
                ehi = solve(high)[0]
                assert elo <= 0 <= ehi, (slot, i, foot, 'compoundreach', elo, ehi, h, target)
                for _ in range(30):
                    mid = (low + high) / 2
                    if solve(mid)[0] > 0:
                        high = mid
                    else:
                        low = mid
                residual, joint, rhip, rshin = solve((low + high) / 2)
                minmargin = min(minmargin, float(a + b - np.linalg.norm(target - h)))
                lifts.append(float(target[1]))
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
        channels = {(18, 7)} | {(b, c) for chain in chains for b in chain for c in [3, 4, 5]}
        anim = replace_channels(old.anims.anims[old.anims.table[slot]], poses, loop, n, channels)
        sound = next((v for v in anim.instrs if v['op'] == 'sound'))
        anim.instrs = [v for v in anim.instrs if v['op'] != 'sound']
        for tick in [0, 10]:
            event = dict(sound, frame=tick + 1)
            idx = next((j for j, v in enumerate(anim.instrs) if v.get('frame', -1) > tick + 1), len(anim.instrs) - 1)
            anim.instrs.insert(idx, event)
        new.anims.anims.append(anim)
        new.anims.table[slot] = len(new.anims.anims) - 1
        checks.append(dict(slot=slot, max_ankle_error=maxerr, minimum_reach_margin=minmargin, carrier_offset_range=[min(body), max(body)], ankle_y_range=[min(lifts), max(lifts)]))
    return (new, checks)

def _split_feathers(old, sk):
    # Rebase two panels at their top edges. Identity hinges preserve every
    # original surface, UV and normal in idle/care/battle programs.
    new = copy.deepcopy(old)
    base = new.tmd.objects[10]
    original = copy.deepcopy(base)
    groups = PANEL_GROUPS
    pivots = PIVOTS
    assert sorted([0, 1] + sum(groups, [])) == list(range(len(original.prims)))
    for ids, pivot in zip(groups, pivots):
        ob = copy.deepcopy(original)
        ob.prims = [original.prims[i] for i in ids]
        verts = old.tmd.obj_verts(10)
        ob.vert_start = len(new.tmd.verts)
        new.tmd.verts.extend((tuple([int(v[j]) - pivot[j] for j in range(3)] + [int(v[3])]) for v in verts))
        new.tmd.objects.append(ob)
    base.prims = [original.prims[i] for i in [0, 1]]
    for a in new.anims.anims:
        for pivot in pivots:
            a.pose.append(([4096] * 3 if a.has_scale else []) + [0, 0, 0] + pivot)
        a.tail = b''
    new.nbones = 28
    return (new, copy.deepcopy(sk) + [[25, 11], [26, 11]])

def _side_response(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    for slot in [2, 3, 4]:
        fs, loop, _ = animsheet.slot_frames(old, n, slot)
        poses = copy.deepcopy(fs)
        hist = {}
        for i, f in enumerate(poses):
            q = 2 * math.pi * i / (len(fs) - 1)
            f[26][3] = f[27][3] = round(-10 * 4096 / 360)
            f[26][5] = round((2 + 2 * math.sin(q) if slot == 3 else 32 + 2 * math.sin(q)) * 4096 / 360)
            f[27][5] = round(((-17 if slot == 3 else -32) + 2 * math.sin(q + math.pi)) * 4096 / 360)
            if slot == 3:
                root = copy.deepcopy(f[0])
                f[0] = [4096] * 3 + [0] * 6
                w = np.array(mmd.bone_matrices(old, f))
                axis = w[20, :3, 3] - w[19, :3, 3]
                axis /= np.linalg.norm(axis)
                x, y, z = axis
                skew = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
                a = math.radians(12)
                twist = np.eye(3) * math.cos(a) + (1 - math.cos(a)) * np.outer(axis, axis) + math.sin(a) * skew
                set_rotation(f, 19, w[18, :3, :3].T @ twist @ w[19, :3, :3], hist)
                after = np.array(mmd.bone_matrices(old, f))
                set_rotation(f, 20, after[19, :3, :3].T @ w[20, :3, :3], hist)
                f[0] = root
        channels = {(b, c) for b in [26, 27] for c in [3, 4, 5]} | ({(b, c) for b in [19, 20] for c in [3, 4, 5]} if slot == 3 else set())
        new.anims.anims.append(replace_channels(old.anims.anims[old.anims.table[slot]], poses, loop, n, channels))
        new.anims.table[slot] = len(new.anims.anims) - 1
    return new

def _front_response(old, sk):
    # Hinge the small front panel around its top edge. Counter the new side
    # children so their previously solved world motion stays in place.
    n = len(sk)
    new = copy.deepcopy(old)
    for slot in [2, 3, 4]:
        fs, loop, _ = animsheet.slot_frames(old, n, slot)
        poses = copy.deepcopy(fs)
        hist = {}
        for i, f in enumerate(poses):
            root = copy.deepcopy(f[0])
            f[0] = [4096] * 3 + [0] * 6
            w = np.array(mmd.bone_matrices(old, f))
            pivot = np.array([0, 30, -109])
            angle = {2: -22, 3: -8, 4: -18}[slot] + 2 * math.sin(2 * math.pi * i / (len(fs) - 1))
            rr = w[11, :3, :3] @ rotation([angle, 0, 0])
            origin = w[11, :3, :3] @ pivot + w[11, :3, 3] - rr @ pivot
            parent = sk[11][1]
            set_rotation(f, 11, w[parent, :3, :3].T @ rr, hist)
            f[11][6:9] = np.rint(w[parent, :3, :3].T @ (origin - w[parent, :3, 3])).astype(int).tolist()
            after = np.array(mmd.bone_matrices(old, f))
            for bone in [26, 27]:
                set_rotation(f, bone, after[11, :3, :3].T @ w[bone, :3, :3], hist)
                f[bone][6:9] = np.rint(after[11, :3, :3].T @ (w[bone, :3, 3] - after[11, :3, 3])).astype(int).tolist()
            if slot == 3:
                w = np.array(mmd.bone_matrices(old, f))
                axis = w[20, :3, 3] - w[19, :3, 3]
                axis /= np.linalg.norm(axis)
                x, y, z = axis
                skew = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
                a = math.radians(-25)
                twist = np.eye(3) * math.cos(a) + (1 - math.cos(a)) * np.outer(axis, axis) + math.sin(a) * skew
                set_rotation(f, 19, w[18, :3, :3].T @ twist @ w[19, :3, :3], hist)
                after = np.array(mmd.bone_matrices(old, f))
                set_rotation(f, 20, after[19, :3, :3].T @ w[20, :3, :3], hist)
            f[0] = root
        channels = {(b, c) for b in [11, 26, 27] for c in range(3, 9)} | ({(b, c) for b in [19, 20] for c in [3, 4, 5]} if slot == 3 else set())
        new.anims.anims.append(replace_channels(old.anims.anims[old.anims.table[slot]], poses, loop, n, channels))
        new.anims.table[slot] = len(new.anims.anims) - 1
    return new

def verify_source_semantics(source, candidate, source_skeleton, skeleton):
    """Check retained programs/channels, topology and original primitive data."""
    assert skeleton == source_skeleton + [[25, 11], [26, 11]]
    assert len(source_skeleton) == 26 and len(candidate.tmd.objects) == 27
    assert source.tmd.verts == candidate.tmd.verts[:len(source.tmd.verts)]
    assert source.tmd.norms == candidate.tmd.norms
    for obj in range(25):
        original, actual = (source.tmd.objects[obj], candidate.tmd.objects[obj])
        assert (original.vert_start, original.nvert, original.norm_start, original.nnorm, original.scale) == (actual.vert_start, actual.nvert, actual.norm_start, actual.nnorm, actual.scale)
        if obj != 10:
            assert [p.raw for p in original.prims] == [p.raw for p in actual.prims]
    cloth = source.tmd.objects[10]
    assert [p.raw for p in candidate.tmd.objects[10].prims] == [cloth.prims[i].raw for i in [0, 1]]
    for obj, ids, pivot in zip([25, 26], PANEL_GROUPS, PIVOTS):
        panel = candidate.tmd.objects[obj]
        assert [p.raw for p in panel.prims] == [cloth.prims[i].raw for i in ids]
        assert panel.norm_start == cloth.norm_start and panel.nnorm == cloth.nnorm
        assert candidate.tmd.obj_verts(obj) == [tuple((v[j] + (-pivot[j] if j < 3 else 0) for j in range(4))) for v in source.tmd.obj_verts(10)]
    preserved, field = ([], [])
    for slot, index in enumerate(source.anims.table):
        if index is None:
            assert candidate.anims.table[slot] is None
            continue
        before = source.anims.anims[index]
        after = candidate.anims.anims[candidate.anims.table[slot]]
        assert before.frame_count == after.frame_count and before.has_scale == after.has_scale
        assert after.pose[25:] == [([4096] * 3 if after.has_scale else []) + [0, 0, 0] + pivot for pivot in PIVOTS] or slot in [2, 3, 4]
        if slot not in [2, 3, 4]:
            assert before.pose == after.pose[:25] and before.instrs == after.instrs
            preserved.append(slot)
            continue
        old_player = mmd.AnimPlayer(before, 26, slot)
        new_player = mmd.AnimPlayer(after, 28, slot)
        allowed = {(18, 7)} | {(11, c) for c in range(3, 9)} | {(b, c) for chain in CHAINS for b in chain for c in [3, 4, 5]}
        for tick in range(20 * 8):
            assert old_player.tick() and new_player.tick()
            assert old_player.base == new_player.base
            for bone in range(26):
                for channel in range(9):
                    if (bone, channel) not in allowed:
                        assert old_player.pose[bone][channel] == new_player.pose[bone][channel], (slot, tick, bone, channel)
        frames, loop, events = animsheet.slot_frames(candidate, 28, slot)
        assert len(frames) == 21 and loop == 0
        assert [e[0] for e in events] == [0, 10]
        assert all((kind == 'sound' and event['bank'] == 1 and (event['note'] == 16) for _, kind, event in events))
        field.append(slot)
    return dict(unchanged_programs=preserved, changed_field_slots=field, original_root_scales_limb_translations_and_upper_acting_exact_eight_cycles=True, original_footstep_sample_retimed=True, original_surfaces_uv_normals_preserved_with_rebased_feather_panels=True)

def _decoded_support(model):
    """Check the final encoded compound boots, after armor and feather edits."""
    vertices = {b: np.array(model.tmd.obj_verts(obj))[:, :3]
                for b, (obj, _) in enumerate(mmd.exe().skeleton[206]) if obj >= 0}
    result = []
    for slot in [2, 3, 4]:
        frames = animsheet.slot_frames(model, 28, slot)[0]
        matrices, sole, other = [], -float('inf'), -float('inf')
        for frame in frames:
            pose = copy.deepcopy(frame)
            pose[0] = [4096] * 3 + [0] * 6
            world = np.array(mmd.bone_matrices(model, pose))
            matrices.append(world)
            for bone, points in vertices.items():
                y = float((points @ world[bone, :3, :3].T + world[bone, :3, 3])[:, 1].max())
                if bone in [20, 21, 23, 24]:
                    sole = max(sole, y)
                else:
                    other = max(other, y)
        error = 0.
        contact = 3 if slot == 3 else 2
        for side, foot in enumerate([21, 24]):
            for tick in range(len(frames) - 1):
                if (tick + side * 10) % 20 < contact:
                    for axis in [0, 2]:
                        travel = (matrices[tick + 1][foot, axis, 3] - matrices[tick][foot, axis, 3] +
                                  frames[tick + 1][0][6 + axis] - frames[tick][0][6 + axis])
                        error = max(error, abs(float(travel)))
        assert error < 1 and sole < 2 and other < 0, (slot, error, sole, other)
        result.append(dict(slot=slot, max_native_full_boot_y=sole,
                           max_other_mesh_y=other, max_planted_ankle_xz_travel=error))
    return result


def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE or len(sk) != 26:
        raise ValueError('Angel recipe requires the pinned reviewed MagnaAngemon source')
    original = _parse(data, sk)
    supported, checks = _supported_steps(original, sk)
    supported = _parse(_pack(supported), sk)
    articulated, skeleton = _split_feathers(supported, sk)
    articulated = _parse(articulated.build(), skeleton)
    sides = _parse(_pack(_side_response(articulated, skeleton)), skeleton)
    result = _pack(_front_response(sides, skeleton))
    parsed = _parse(result, skeleton)
    proof = verify_source_semantics(original, parsed, sk, skeleton)
    storage = motionstorage.audit(result, 28)
    assert storage['fits'], storage
    proof.update(species=206, source_sha256=SOURCE, output_sha256=hashlib.sha256(result).hexdigest(), generated_skeleton=skeleton, checks=checks, decoded_support=_decoded_support(parsed), storage=storage, style='supported compound boots, native wing-assisted run, separate waist feather response')
    return (result, proof)
