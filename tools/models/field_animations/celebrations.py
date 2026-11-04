"""Overlapping celebrations, authored on the final proportions with planted feet.

The manifest keeps the accepted pose and the anatomical joint map per species.
The preceding recipe still owns every other clip, mesh and proportion. Timing is
sampled with smooth cubic arcs; secondary chains use delayed, damped responses.
Two-bone leg solves let the pelvis shift without sliding the supporting feet.
Only standard-library math is used so the player patcher can replay the recipe.
"""
import copy
import hashlib
import importlib
import json
import math
from pathlib import Path

import animsheet
import legik
import mmd
import motionstorage
import retarget as rt

MANIFEST = Path(__file__).resolve().parents[3] / 'content/models/imports/celebrations.json'


def ease(x):
    x = max(0., min(1., x))
    return x * x * (3 - 2 * x)


def arc(t, n, delay=0., gain=1.):
    # Return begins early enough for the last follower to settle before idle.
    t -= delay
    keys = [(0, 0), (.12*n, -.055), (.32*n, 1.045), (.41*n, .985),
            (.51*n, 1.005), (.66*n, 1), (.84*n, -.025), (n-5, 0)]
    if n < 32:
        # Short celebrations still need an ordered return and three ticks for
        # the hands to follow; a long clip's fixed tail margin would cross keys.
        end = n-4
        keys = [(0, 0), (.12*end, -.055), (.36*end, 1.045), (.46*end, .985),
                (.56*end, 1.005), (.69*end, 1), (.9*end, -.025), (end, 0)]
    for (a, x), (b, y) in zip(keys, keys[1:]):
        if a <= t <= b:
            return gain * (x + (y-x) * ease((t-a)/(b-a)))
    return 0.


def compression(t, n):
    keys = [(0, 0), (.12*n, 4.5), (.32*n, -3.5), (.41*n, -1.4),
            (.53*n, -2.5), (.65*n, -2), (.83*n, 1.2), (n-4, 0), (n, 0)]
    if n < 32:
        end = n-4
        keys = [(0, 0), (.13*end, 4.5), (.36*end, -3.5), (.46*end, -1.4),
                (.59*end, -2.5), (.72*end, -2), (.9*end, 1.2), (end, 0), (n, 0)]
    for (a, x), (b, y) in zip(keys, keys[1:]):
        if a <= t <= b:
            return x + (y-x)*ease((t-a)/(b-a))
    return 0.


def torso(t, count, gain):
    envelope = ease(t/4) * ease((count-1-t)/5)
    phase = 2*math.pi*t/max(18, count*.52)
    sway = math.sin(phase*.65)*envelope
    return [(compression(t, count-1)+1.8*math.sin(phase-.35)*envelope)*gain,
            1.2*sway, 1.6*sway]


def turn(pose, bone, angles):
    extra = mmd.rot_matrix(*(x * 4096 / 360 for x in angles))
    target = rt.m3mul(extra, rt.rot_of(pose[bone]))
    pose[bone][3:6] = [round(x) for x in mmd.matrix_euler(target, prev=pose[bone][3:6])]


def set_world(pose, sk, bone, rotation=None, position=None):
    wr, wp = rt.world_transform(sk, pose)
    parent = sk[bone][1]
    inv = rt.m3t(wr[parent])
    if rotation is not None:
        local = rt.m3mul(inv, rotation)
        pose[bone][3:6] = [round(x) for x in mmd.matrix_euler(local, prev=pose[bone][3:6])]
    if position is not None:
        delta = legik.sub(position, wp[parent])
        pose[bone][6:9] = [round(sum(r[j]*delta[j] for j in range(3))) for r in inv]


def plant(pose, idle, sk, chains, locked):
    w0, p0 = rt.world_transform(sk, idle)
    for hip, knee, ankle in chains:
        _, pos = rt.world_transform(sk, pose)
        d1, d2 = legik.sub(p0[knee], p0[hip]), legik.sub(p0[ankle], p0[knee])
        axis = legik.unit(legik.sub(p0[ankle], p0[hip]))
        pole = legik.sub(d1, legik.mul(axis, legik.dot(d1, axis)))
        if legik.norm(pole) < .01:
            pole = [0, 0, -1]
        k, a = legik.solve(pos[hip], p0[ankle], legik.norm(d1), legik.norm(d2), pole)
        set_world(pose, sk, hip, rt.m3mul(rt.swing(d1, legik.sub(k, pos[hip])), w0[hip]))
        set_world(pose, sk, knee, rt.m3mul(rt.swing(d2, legik.sub(a, k)), w0[knee]))
        # Correct sub-unit rotation quantisation, then preserve the flat sole.
        set_world(pose, sk, ankle, w0[ankle], p0[ankle])
    for bone in locked:
        set_world(pose, sk, bone, w0[bone], p0[bone])


def refine(data, skeleton, sid, row):
    model = mmd.MMD.parse(data, len(skeleton))
    model.type = sid
    n = len(skeleton)
    idle = animsheet.slot_frames(model, n, 0x21)[0][0]
    idle = [[round(v) for v in b] for b in idle]
    chains = row.get('legs', [])
    lower = set(row.get('lower', []))
    passive = {b: (i, axis, amp) for chain, axis, amp in row.get('secondary', []) for i, b in enumerate(chain)}
    delays = {int(b): d for b, d in row.get('delays', {}).items()}
    chest, pelvis, head = row['chest'], row['pelvis'], row.get('head')
    w0, positions0 = rt.world_transform(skeleton, idle)
    for slot in row['slots']:
        original = model.anims.anims[model.anims.table[slot]]
        frames, loop, events = animsheet.slot_frames(model, n, slot)
        count = len(frames)
        raised = copy.deepcopy(frames[round((count-1)*.46)])
        for bone, degrees in row.get('outward', []):
            wr = rt.world_rots(skeleton, raised)
            set_world(raised, skeleton, bone, rt.m3mul(mmd.rot_matrix(0, 0, degrees*4096/360), wr[bone]))
        out = []
        for t in range(count):
            p = copy.deepcopy(idle)
            envelope = ease(t/4) * ease((count-1-t)/5)
            phase = 2 * math.pi * t / max(18, count*.52)
            for b in range(1, n):
                if b in lower:
                    continue
                d = delays.get(b, 1.5)
                if b == chest:
                    d = 0
                if b in passive:
                    d = 2.5 + passive[b][0]*.7
                drive = arc(t, count-1, d)
                if b in row.get('no_reverse', []):
                    drive = max(0, drive)
                if b in row.get('early_clearance', []) and 0 < t < .24*(count-1):
                    drive += .13*math.sin(math.pi*t/(.24*(count-1)))**2
                q = mmd._slerp(mmd.quat(*idle[b][3:6]), mmd.quat(*raised[b][3:6]), drive)
                p[b][3:6] = [round(v) for v in mmd.matrix_euler(mmd.quat_matrix(q), prev=p[b][3:6])]
                for c in (6, 7, 8):
                    p[b][c] = round(idle[b][c] + drive*(raised[b][c]-idle[b][c]))
            # Torso breath and compression continue through the pose; the hips
            # arrive before the chest, and the gaze follows the shoulders.
            base_wr = rt.world_rots(skeleton, p)
            breath = math.sin(phase-.35) * envelope
            sway = math.sin(phase*.65) * envelope
            gain = row.get('body_gain', 1)
            turn(p, chest, torso(t, count, gain))
            if pelvis != chest:
                turn(p, pelvis, [.7*breath, .65*sway, -.7*sway])
            # Followers lag the torso in world space as well as lagging their
            # own raise. Merely delaying local keys still moves a whole arm as
            # one rigid piece when its parent breathes or winds up.
            parent_wr = base_wr[skeleton[chest][1]]
            for bone, delay in delays.items():
                if bone in lower or bone in passive or bone == chest:
                    continue
                extra = mmd.rot_matrix(*(a*4096/360 for a in torso(t-delay, count, gain)))
                world_extra = rt.m3mul(rt.m3mul(parent_wr, extra), rt.m3t(parent_wr))
                set_world(p, skeleton, bone, rt.m3mul(world_extra, base_wr[bone]))
            if head and head != chest:
                turn(p, head, [1.6*math.sin(phase-.85)*envelope, 1.2*math.sin(phase*.7-.5)*envelope, -.5*sway])
            for bone, axis, degrees in row.get('clearance_turns', []):
                windup = math.sin(math.pi*t/(.28*(count-1)))**2 if t < .28*(count-1) else 0
                angles = [0., 0., 0.]
                angles[axis] = degrees*windup
                wr = rt.world_rots(skeleton, p)
                extra = mmd.rot_matrix(*(a*4096/360 for a in angles))
                set_world(p, skeleton, bone, rt.m3mul(extra, wr[bone]))
            if row.get('shift', 0):
                # Y grows downward: a short compression, lift, and landing.
                dip = 7*math.exp(-((t-.12*(count-1))/3)**2)
                settle = 2.8*math.exp(-((t-.4*(count-1))/3.5)**2)
                k = row['shift']
                p[pelvis][6] += round(3*k*sway)
                p[pelvis][7] += round(k*(dip + settle + .8*breath)*envelope)
            for b, (i, axis, amp) in passive.items():
                lag = t - 2.5 - i*.7
                velocity = arc(lag+.5, count-1)-arc(lag-.5, count-1)
                landing = max(0, lag-.32*(count-1))
                follow = math.sin(landing*.65)*math.exp(-landing*.12)*ease(landing/2)
                angles = [0., 0., 0.]
                angles[axis] = amp*(.38*math.sin(phase-.6-i*.35) + 2.5*velocity + .25*follow)*envelope
                turn(p, b, angles)
            for bone, axis, bias, amplitude in row.get('hanging', []):
                angles = [0., 0., 0.]
                angles[axis] = (bias + amplitude*math.sin(phase-1-bone*.035))*envelope
                extra = mmd.rot_matrix(*(a*4096/360 for a in angles))
                target = rt.m3mul(extra, w0[bone])
                position = None
                pin = row.get('hang_pins', {}).get(str(bone))
                if pin is not None:
                    # Some imported cloth pivots lie at the middle of the
                    # sheet. Rotate around its collar, not through the arms.
                    parent = skeleton[bone][1]
                    wr, wp = rt.world_transform(skeleton, p)
                    local_parent = [sum(r[j]*(pin[j]-positions0[parent][j]) for j in range(3)) for r in rt.m3t(w0[parent])]
                    local_bone = [sum(r[j]*(pin[j]-positions0[bone][j]) for j in range(3)) for r in rt.m3t(w0[bone])]
                    anchor = [wp[parent][i]+sum(wr[parent][i][j]*local_parent[j] for j in range(3)) for i in range(3)]
                    position = [anchor[i]-sum(target[i][j]*local_bone[j] for j in range(3)) for i in range(3)]
                set_world(p, skeleton, bone, target, position)
            plant(p, idle, skeleton, chains, row.get('locked', []))
            if sid == 318:
                # The long plume must retain its safe hanging world direction.
                set_world(p, skeleton, 7, w0[7])
                for i, b in enumerate((7, 8, 9, 10, 11)):
                    turn(p, b, [1.2*math.sin(phase-.8-i*.4)*envelope, 0, 0])
                # The cape hangs behind the heels independently of torso pitch.
                angle = -6*envelope + 1.0*math.sin(phase-1)*envelope
                set_world(p, skeleton, 16, rt.m3mul(w0[16], mmd.rot_matrix(angle*4096/360, 0, 0)))
                for i, b in enumerate((17, 18)):
                    p[b][3:6] = idle[b][3:6][:]
                    turn(p, b, [1.2*math.sin(phase-1.2-i*.5)*envelope, 0, .6*math.sin(phase-.5-i*.5)*envelope])
            out.append(p)
        out[0], out[-1] = copy.deepcopy(idle), copy.deepcopy(idle)
        updated = mmd.encode_anim(out, n, loop, events, tol=row.get('tolerance', 1))
        updated.tail = original.tail
        model.anims.table[slot] = len(model.anims.anims)
        model.anims.anims.append(updated)
    used = sorted(set(model.anims.table) - {None})
    mapping = {old: new for new, old in enumerate(used)}
    model.anims.anims = [model.anims.anims[i] for i in used]
    model.anims.table = [mapping[i] if i is not None else None for i in model.anims.table]
    result = model.build()
    motionstorage.require(result, n)
    return result


def build(data, skeleton):
    from tools.models.field_animations.reviewed import reviewed
    digest = hashlib.sha256(data).hexdigest()
    rows = json.loads(MANIFEST.read_text())
    matches = [(int(s), r) for s, r in rows.items() if r['source_sha256'] == reviewed(digest)]
    if len(matches) != 1:
        raise ValueError('Celebrations require an individually reviewed source')
    sid, row = matches[0]
    if hashlib.sha256(json.dumps(skeleton).encode()).hexdigest() != row['skeleton_sha256']:
        raise ValueError('Celebrations: the skeleton differs from the reviewed source')
    proof = {}
    if row.get('base_generator'):
        data, proof = importlib.import_module(row['base_generator']).build(data, skeleton)
    rig = proof.get('generated_skeleton', skeleton)
    result = refine(data, rig, sid, row)
    storage = motionstorage.require(result, len(rig))
    proof = dict(proof, celebration_slots=row['slots'], celebration_bytes=[len(data), len(result)],
                 output_sha256=hashlib.sha256(result).hexdigest())
    if 'bytes' in proof:
        proof['bytes'] = [proof['bytes'][0], len(result)]
    if 'resident_bytes' in proof:
        proof['resident_bytes'] = [storage['resident_bytes'], storage['resident_limit']]
    return result, proof
