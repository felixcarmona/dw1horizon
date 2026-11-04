"""Supported field cycles on an import's own articulated limbs.

Profiles specify anatomical chains and footfall phases. Soles follow stance tracks calibrated to native foot slip; eased swings lift, curl and reach before touchdown.
Body weight shifts lead the arms, head and trailing parts. Intermediate joints
retain their reference articulation, so four-joint chains need no stretched
bones. Every generated clip is replayed to check loop closure and storage.
"""
import copy
import hashlib
import math

import animsheet
import mmd
import motioncyclelayer
import motionstorage
from motiondiscidentity import changed_programs
from tools.models.field_animations.war_greymon import align, rotation, set_rotation
import numeric as np


def build(data, skeleton, profile):
    sid = profile['species']
    assert hashlib.sha256(data).hexdigest() == profile['source']
    assert [p for _, p in skeleton] == profile['parents']
    n = len(skeleton)
    mmd.exe().skeleton[sid] = skeleton
    mmd.exe().bone_count[sid] = n
    old = mmd.MMD.parse(data, n)
    old.type = sid
    new = copy.deepcopy(old)
    rest = copy.deepcopy(animsheet.slot_frames(old, n, 0)[0][0])
    rest[0] = [4096] * 3 + [0] * 6
    for b, angles in profile.get('rest', {}).items():
        rest[b][3:6] = [round(v + d * 4096 / 360) for v, d in zip(rest[b][3:6], angles)]
    verts = {b: np.array(old.tmd.obj_verts(o))[:, :3] for b, (o, _) in enumerate(skeleton) if o >= 0}

    def world(f):
        p = copy.deepcopy(f)
        p[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(old, p))

    reference = world(rest)
    checks = []
    for slot, cfg in profile['slots'].items():
        ticks, speed = cfg['ticks'], cfg['speed']
        looping = cfg.get('loop', True)
        if slot in (0, 1):
            assert ticks + 1 <= 25, 'field idle must keep every needs-timer draw reachable'
        if slot in (2, 3, 4):
            low, high = {2: (15, 31), 3: (10, 21), 4: (35, 52)}[slot]
            assert low <= speed <= high, (sid, slot, 'native pace', speed)
        legs = [(up, lo, foot, cfg.get('phases', {}).get(foot, phase))
                for up, lo, foot, phase in profile['legs']]
        frames, errors = [], []
        hist = {}
        for t in range(ticks + 1):
            theta = 2 * math.pi * t / ticks
            gain = 1.0 if looping else math.sin(math.pi * t / ticks) ** 2
            f = copy.deepcopy(rest)
            f[0][8] = -round(speed * t)
            body = profile['body']
            f[body][7] += round(gain * (cfg.get('drop', 0) + cfg['bob'] * math.cos((2 if speed else 1) * theta)))
            set_rotation(f, body, np.array(mmd.rot_matrix(*rest[body][3:6])) @ rotation([
                gain * (cfg.get('pitch_bias', 0) + cfg['pitch'] * math.sin(2 * theta - .3)),
                gain * cfg['yaw'] * math.sin(theta - .4),
                gain * cfg['roll'] * math.sin(theta)]), hist)
            # Serial joints trail their carrier; the phase offsets also soften holds.
            for b, amp, delay in profile.get('secondary', []):
                amp *= gain * cfg.get('secondary_scale', 1)
                set_rotation(f, b, np.array(mmd.rot_matrix(*rest[b][3:6])) @ rotation([
                    amp * math.sin(theta - delay),
                    amp * .5 * math.sin(theta - delay - .4),
                    amp * .25 * math.cos(theta - delay)]), hist)
            for up, lo, foot, phase in legs:
                u = (t / ticks - phase) % 1
                duty = cfg['duty']
                stance = not speed or u < duty
                centre = reference[foot, :3, 3].copy()
                offset = profile.get('foot_centres', {}).get(foot, (0, 0))
                centre[0] += offset[0]
                centre[2] += offset[1]
                up_amount, pitch = 0, 0
                if speed:
                    stride = speed * ticks * duty * (1 - cfg.get('slip', 0))
                    if stance:
                        z = -stride / 2 + stride * u / duty
                        pitch = cfg.get('roll_foot', 8) * max(0, (u / duty - .65) / .35) ** 2
                    else:
                        q = (u - duty) / (1 - duty)
                        ease = q * q * (3 - 2 * q)
                        z = stride / 2 - stride * ease
                        up_amount = cfg.get('lifts', {}).get(foot, cfg['lift']) * math.sin(math.pi * q) ** 1.5
                        pitch = cfg.get('curl', 20) * math.sin(math.pi * q) ** 2
                    centre[2] += z
                attitude = rotation([pitch, 0, 0]) @ reference[foot, :3, :3]
                bottom = float((verts[foot] @ attitude.T)[:, 1].max())
                centre[1] = -profile.get('clear', 4) - up_amount - bottom
                w = world(f)
                h = w[up, :3, 3]
                a = reference[lo, :3, 3] - reference[up, :3, 3]
                b = reference[foot, :3, 3] - reference[lo, :3, 3]
                la, lb = np.linalg.norm(a), np.linalg.norm(b)
                delta = centre - h
                length = np.linalg.norm(delta)
                reach = max(abs(la - lb) + .1, min(la + lb - .1, length))
                direction = delta / length
                # Transport the original bend plane without changing axial material orientation.
                rest_direction = (a + b) / np.linalg.norm(a + b)
                native = a - (a @ rest_direction) * rest_direction
                native -= (native @ direction) * direction
                if np.linalg.norm(native) < .01:
                    native = np.array([.2, -.3, 1.0])
                    native -= (native @ direction) * direction
                pole = native / np.linalg.norm(native)
                along = (la * la - lb * lb + reach * reach) / (2 * reach)
                joint = h + direction * along + pole * math.sqrt(max(0, la * la - along * along))
                end = h + direction * reach
                ru = align(a, joint - h) @ reference[up, :3, :3]
                set_rotation(f, up, w[skeleton[up][1], :3, :3].T @ ru, hist)
                w = world(f)
                rl = align(b, end - joint) @ reference[lo, :3, :3]
                set_rotation(f, lo, w[skeleton[lo][1], :3, :3].T @ rl, hist)
                w = world(f)
                set_rotation(f, foot, w[skeleton[foot][1], :3, :3].T @ attitude, hist)
                error = float(np.linalg.norm(world(f)[foot, :3, 3] - centre))
                errors.append(error)
            frames.append(f)
        frames[-1][1:] = copy.deepcopy(frames[0][1:])
        # Rounding and interpolated rotations can put a sole just below the floor.
        # Raise the complete cycle by the same small amount, preserving weight shifts.
        from motiontailspace import interpolate_pose
        floor = -1e9
        floor_bone = None
        for t in range(ticks):
            for alpha in (0, 1365, 2730):
                w = world(interpolate_pose(frames[t], frames[t+1], alpha))
                for b, v in verts.items():
                    bottom = float((v @ w[b,:3,:3].T + w[b,:3,3])[:,1].max())
                    if bottom > floor:
                        floor, floor_bone = bottom, b
        raised = max(0, math.ceil(floor + 1))
        assert raised <= 4, (sid, slot, 'authored pose needs a clearance repair', raised)
        for f in frames:
            f[body][7] -= raised
        original_events = animsheet.slot_frames(old, n, slot)[2]
        old_ticks = len(animsheet.slot_frames(old, n, slot)[0]) - 1
        events = [(min(ticks - 1, round(t * ticks / old_ticks)), kind, cue)
                  for t, kind, cue in original_events
                  if kind == 'tex' or (not looping and kind == 'sound' and cue['bank'] in (3, 4))]
        if speed:
            for tick in sorted({round(phase * ticks) % ticks for _,_,_,phase in legs}):
                events.append((tick, 'sound', dict(bank=1, note=profile['step'])))
        animation = mmd.encode_anim(frames, n, loop_sample=0 if looping else None, events=events, tol=1, repeats=False)
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(animation)
        player = mmd.AnimPlayer(animation, n, slot)
        played = []
        for t in range(ticks * 4 if looping else ticks + 1):
            assert player.tick()
            if t < ticks or not looping:
                played.append(copy.deepcopy(player.pose))
            else:
                assert player.pose == played[t % ticks], (sid, slot, t, 'loop drift')
        if not looping:
            assert not player.tick(), (sid, slot, 'gesture did not finish')
        decoded_floor = -1e9
        for t in range(ticks):
            for alpha in (0, 1365, 2730):
                w = world(interpolate_pose(played[t], played[(t + 1) % ticks] if looping else played[t + 1], alpha))
                decoded_floor = max(decoded_floor, max(float((v @ w[b,:3,:3].T + w[b,:3,3])[:,1].max()) for b,v in verts.items()))
        assert decoded_floor <= 1.5, (sid, slot, 'floor', decoded_floor)
        checks.append(dict(slot=slot, ticks=ticks, speed=speed, max_target_error=max(errors), raised=raised, floor_bone=floor_bone,
                           four_cycles_exact=looping, finite_gesture_ends=not looping, decoded_floor=decoded_floor, footsteps=[e[0] for e in events if e[1]=='sound' and e[2]['bank']==1]))
        assert max(errors) < profile.get('target_error', 8), (sid, slot, max(errors))
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    result = new.build()
    parsed = mmd.MMD.parse(result, n)
    assert parsed.tmd.build() == old.tmd.build()
    assert changed_programs(old, parsed) == sorted(profile['slots'])
    storage = motionstorage.require(result, n)
    return result, dict(species=sid, source_sha256=profile['source'], output_sha256=hashlib.sha256(result).hexdigest(),
                        changed_slots=sorted(profile['slots']), mesh_exact=True, checks=checks, storage=storage)
