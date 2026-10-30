"""Gomamon's low flipper shuffle with its native facial and tail performance.

Foreflippers alternate planted strokes and outward scooping recovery. Fixed
native forearm lengths and complete palm meshes determine the carrier height;
the belly and rear flippers retain the low seal-like posture and native curves.
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
from tools.models.field_animations.war_greymon import rotation, set_rotation, align
SOURCE = 'c9f7ce4211bb231299e066ceb421d3753778b998e667b50272095834618fc51e'

def _parse(data, sk):
    mmd.exe().skeleton[217] = sk
    mmd.exe().bone_count[217] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = 217
    return model

def _author(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    vs = {b: np.array(old.tmd.obj_verts(oi))[:, :3] for b, (oi, _) in enumerate(sk) if oi >= 0}

    def world(f):
        g = copy.deepcopy(f)
        g[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, g))
    rw = world(animsheet.slot_frames(old, n, 0)[0][0])
    flats = {b: rotation([0, math.degrees(math.atan2(rw[b, 0, 2], rw[b, 2, 2])), 8 if b == 14 else -8]) for b in [14, 16]}
    reports = []
    for slot in [0, 2, 3, 4]:
        fs, loop, events = animsheet.slot_frames(old, n, slot)
        duration = len(fs) - 1
        period = {0: 72, 2: 18, 3: 24, 4: 12}[slot]
        contact = {0: 72, 2: 6, 3: 8, 4: 2}[slot]
        speed = {0: 0, 2: 8, 3: 6, 4: 30}[slot]
        rock = {0: 0, 2: 6, 3: 4, 4: 8}[slot]
        poses = []
        hist = {}
        errs = []
        body = []
        for t, source in enumerate(fs):
            f = copy.deepcopy(source)
            f[0] = [4096] * 3 + [0] * 6
            if not slot:
                w = world(f)
                bottom = max((float((v @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max()) for b, v in vs.items()))
                f[1][7] -= math.ceil(max(0, bottom + 2))
            else:
                # Solve in carrier-zero space, then protect belly and rear flippers.
                f[1][7] = 0
                w = world(f)
                floor = max((float((vs[b] @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max()) for b in vs if b not in [13, 14, 15, 16]))
                carrier = -floor - 2
                goals = []
                planted = []
                for side, (hip, foot) in enumerate([(13, 14), (15, 16)]):
                    sign = 1 if side == 0 else -1
                    offset = side * period / 2
                    start = math.floor((t - offset) / period) * period + offset
                    phase = t - start
                    half = speed * contact / 2
                    center = -65
                    planted.append(phase <= contact)
                    if phase <= contact:
                        z = center - half + speed * phase
                        x = sign * 65
                        pitch = -rock * math.cos(math.pi * phase / contact)
                    else:
                        q = (phase - contact) / (period - contact)
                        a = center + half
                        b = center - half
                        span = period - contact
                        # Match planted velocity at both ends without a long reach overshoot.
                        smooth = 6 * q ** 5 - 15 * q ** 4 + 10 * q ** 3
                        z = a * (1 - smooth) + b * smooth + span * speed * q * (1 - q) * (1 - 2 * q) ** 5
                        x = sign * (65 + 24 * math.sin(math.pi * q) ** 2)
                        pitch = rock * math.cos(math.pi * q) + 10 * math.sin(math.pi * q) ** 2
                    # Lift the outer palm during recovery before sweeping it forward.
                    flat = flats[foot] if phase <= contact else rotation([0, math.degrees(math.atan2(rw[foot, 0, 2], rw[foot, 2, 2])), sign * (8 - 18 * math.sin(math.pi * q))])
                    rf, dz, sole = motionsecondary.rolling_foot(vs[foot].tolist(), flat.tolist(), pitch)
                    rf = np.array(rf)
                    z += dz
                    h = w[hip, :3, 3]
                    length = np.linalg.norm(f[foot][6:9])
                    radius = (x - h[0]) ** 2 + (z - h[2]) ** 2
                    assert radius < length ** 2 - 0.1, (slot, t, foot, radius, length)
                    vertical = math.sqrt(length ** 2 - radius)
                    required = -sole - 3 - vertical - h[1]
                    carrier = min(carrier, required)
                    goals.append((hip, foot, np.array([x, h[1] + vertical, z]), rf))
                q = (t % (period / 2) - contact) / (period / 2 - contact)
                if not any(planted):
                    carrier -= {2: 2, 3: 1.5, 4: 6}[slot] * math.sin(math.pi * q) ** 2
                f[1][7] = math.floor(carrier)
                body.append(carrier)
                w = world(f)
                for hip, foot, goal, rf in goals:
                    goal[1] += f[1][7]
                    reference = rw[foot, :3, 3] - rw[hip, :3, 3]
                    rh = align(reference, goal - w[hip, :3, 3]) @ rw[hip, :3, :3]
                    set_rotation(f, hip, w[sk[hip][1], :3, :3].T @ rh, hist)
                    w = world(f)
                    set_rotation(f, foot, w[hip, :3, :3].T @ rf, hist)
                    w = world(f)
                    errs.append(float(np.linalg.norm(w[foot, :3, 3] - goal)))
            f[0] = copy.deepcopy(source[0])
            f[0][8] = -speed * t
            poses.append(f)
        poses[-1][1:] = copy.deepcopy(poses[0][1:])
        channels = {(1, 7)} | ({(b, c) for b in [13, 14, 15, 16] for c in [3, 4, 5]} if slot else set())
        authored = replace_channels(old.anims.anims[old.anims.table[slot]], poses, loop, n, channels)
        if slot:
            authored = _forward(authored, round(-speed * duration), duration)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(authored)
        reports.append(dict(slot=slot, period=duration, gait=period, contact=contact, speed=speed, channels=sorted(channels), max_wrist_error=max(errs, default=0), carrier_y_range=[min(body), max(body)] if body else []))
    return (new, reports)

def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE or len(sk) != 22:
        raise ValueError('Gomamon requires the reviewed pinned 22-bone source')
    old = _parse(data,sk)
    new,solver = _author(old,sk)
    for animation in new.anims.anims:
        animation.tail = b''
    new.anims.anims,new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims,new.anims.table)
    result = new.build()
    actual = _parse(result,sk)
    assert changed_programs(old,actual) == [0,2,3,4]
    assert old.tmd.build() == actual.tmd.build()
    checks = []
    for row in solver:
        slot = row['slot']
        duration = row['period']
        original = old.anims.anims[old.anims.table[slot]]
        selected = actual.anims.anims[actual.anims.table[slot]]
        source,loop,events = animsheet.slot_frames(old,22,slot)
        decoded,selected_loop,selected_events = animsheet.slot_frames(actual,22,slot)
        assert len(source)==len(decoded) and loop==selected_loop==0
        assert events==selected_events
        assert [i for i in original.instrs if i['op']!='key']==[i for i in selected.instrs if i['op']!='key']
        channels = {tuple(c) for c in row['channels']}
        before = mmd.AnimPlayer(original,22,slot)
        after = mmd.AnimPlayer(selected,22,slot)
        cycle = []
        for tick in range(duration*9+1):
            assert before.tick() and after.tick()
            assert before.base[:2]==after.base[:2]
            for bone in range(22):
                for channel in range(9):
                    if (bone,channel) not in channels:
                        assert before.pose[bone][channel]==after.pose[bone][channel],(slot,tick,bone,channel)
            if tick<duration:
                cycle.append(copy.deepcopy(after.pose))
            else:
                assert after.pose==cycle[tick%duration],(slot,tick,'cyclic drift')
        total = -row['speed']*duration
        assert after.root[2]==total*9
        checks.append(dict(slot=slot,duration=duration,gait_period=row['gait'],forward_units_per_tick=row['speed'],source_root_XY_exact=True,unselected_channels_limb_translations_scales_exact_nine_cycles=True,changed_pose_repeat_exact_nine_cycles=True,all_original_events_instructions_exact=True))
    storage = motionstorage.audit(result,22)
    assert storage['fits'],storage
    return result,dict(species=217,source_sha256=SOURCE,output_sha256=hashlib.sha256(result).hexdigest(),changed_slots=[0,2,3,4],mesh_skeleton_private33_care_battle_exact=True,checks=checks,solver=solver,storage=storage)
