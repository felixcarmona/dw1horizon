#!/usr/bin/env python3
"""Anatomy audit and native-rig locomotion experiments. No assets in recipes.

Run with the card-game venv. `audit ID ...` writes local evidence to build/motionlab;
`build RECIPE` generates only the explicitly requested slots, retaining the native rig.
The audit proposes anatomy; it never certifies a locomotion mode from geometry alone.
"""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(HERE / 'review')]
import animsheet
import legik
import mmd
import retarget as R


def digest(data):
    return hashlib.sha256(data).hexdigest()


def skeleton_digest(skel):
    return digest(json.dumps(skel, separators=(',', ':')).encode())


def has_scaled_rest_bones(rest):
    """Ignore at most two Q12 units of decode noise around unit scale."""
    return any(any(abs(scale-4096) > 2 for scale in pose[:3]) for pose in rest)


def species_info(sid):
    files = list((ROOT / 'content/species').glob(f'{sid}-*.json'))
    if len(files) != 1:
        raise ValueError(f'expected one species record for {sid}, got {len(files)}')
    return json.loads(files[0].read_text())


def load(sid, input_path=None):
    sp = species_info(sid)
    path = input_path or ROOT / sp['model']['file']
    data = path.read_bytes()
    mod = mmd.MMD.load(str(path), sid)
    skel = mmd.exe().skeleton[sid]
    pose = animsheet.slot_frames(mod, len(skel), 0)[0][0]
    pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
    return sp, path, data, mod, skel, pose


def branches(shape):
    """Disjoint off-centre subtrees, without guessing arm versus wing versus ornament.

    Unlike the legacy matcher, a joint without mesh stays in its chain. Pairing
    uses attachment and the complete subtree, never a second endpoint in the
    same appendage. Centre-line head/tail/spine remain explicitly unresolved.
    """
    children = {b: [] for b in range(len(shape.parent))}
    for b, parent in enumerate(shape.parent):
        if parent >= 0:
            children[parent].append(b)
    centre = lambda b: abs(shape.joint[b][0]) < .035
    groups = []
    for b in range(1, len(shape.parent)):
        parent = shape.parent[b]
        if centre(b) or parent < 1 or not centre(parent):
            continue
        # Do not start a second appendage inside an existing off-centre branch.
        ancestors_list = shape.ancestors(b)
        if any(not centre(p) for p in ancestors_list if p > 0):
            continue
        subtree, stack = [], [b]
        while stack:
            x = stack.pop()
            subtree.append(x)
            stack.extend(reversed(children[x]))
        mass = sum(shape.mass[x] for x in subtree)
        if not mass:
            continue
        centroid = [sum(shape.mass[x] * shape.tip[x][i] for x in subtree)/mass for i in range(3)]
        reaches_ground = max(shape.tip[x][1] for x in subtree if shape.mass[x]) > -.15
        groups.append(dict(root=b, attachment=parent, bones=subtree, vertices=mass,
                           centroid=centroid, side='positive_x' if centroid[0] > 0 else 'negative_x',
                           role='unresolved_appendage', low_geometry=reaches_ground,
                           paired_root=None))
    for a in groups:
        if a['side'] != 'positive_x' or a['paired_root'] is not None:
            continue
        candidates = [b for b in groups if b['side']=='negative_x' and b['paired_root'] is None
                      and b['attachment']==a['attachment']]
        if not candidates:
            continue
        def cost(b):
            ca, cb = a['centroid'], b['centroid']
            return math.sqrt((ca[0]+cb[0])**2 + (ca[1]-cb[1])**2 + (ca[2]-cb[2])**2)
        mate = min(candidates,key=cost)
        if cost(mate) < .2:
            a['paired_root'],mate['paired_root'] = mate['root'],a['root']
    return groups


def shape_at_pose(mod,skel,pose):
    import import_batch as IB
    world=mmd.bone_matrices(mod,pose);joints=[];tips=[];mass=[];points=[];lows=[]
    for b,(obj,_) in enumerate(skel):
        joints.append([world[b][i][3] for i in range(3)])
        vertices=[[sum(world[b][i][j]*v[j] for j in range(3))+world[b][i][3] for i in range(3)]
                  for v in mod.tmd.obj_verts(obj)] if obj>=0 else []
        points.extend(vertices);mass.append(len(vertices))
        lows.append(max(v[1] for v in vertices) if vertices else None)
        tips.append([sum(v[i] for v in vertices)/len(vertices) for i in range(3)] if vertices else joints[-1])
    return IB.Shape(joints,tips,mass,[parent for _,parent in skel],IB.bbox(points),points,lows)


def audit(sid, outdir):
    import limbmap
    import walkpolish
    sp, path, data, mod, skel, rest = load(sid)
    shape = limbmap.shape_from_mmd(str(path), sid)
    parts = limbmap.parts(shape)
    warnings = ['Geometry and imported battle clips do not establish a locomotion mode.']
    ownership = {}
    for role in ('legs', 'arms', 'wings'):
        for end, chain in parts[role]:
            for b in chain:
                if b in ownership:
                    warnings.append(f'bone {b} belongs to multiple proposed limbs')
                ownership[b] = role
    if len(parts['arms']) > 2:
        warnings.append('more than two arm candidates: inspect wings, ears and ornaments')
    if len(parts['legs']) not in (0, 2, 4, 6, 8):
        warnings.append('unusual support count; manual review required')
    if parts['head'] and shape.tip[parts['head'][-1]][2] > shape.joint[1][2] + .15:
        warnings.append('proposed head lies behind torso: possible tail/ornament confusion')
    if len(parts['legs']) == 4 and parts['arms']:
        warnings.append('quadruped with arm candidates: inspect head ornaments and extra limbs')
    W = mmd.bone_matrices(mod, rest)
    positions = [[M[i][3] for i in range(3)] for M in W]
    bones = []
    for b, (oi, parent) in enumerate(skel):
        vs = mod.tmd.obj_verts(oi) if oi >= 0 else []
        pts = [[sum(W[b][i][j] * v[j] for j in range(3)) + W[b][i][3]
                for i in range(3)] for v in vs]
        bounds = [[min(p[i] for p in pts), max(p[i] for p in pts)] for i in range(3)] if pts else None
        bones.append(dict(bone=b, parent=parent, vertices=len(vs), position=positions[b], bounds=bounds))
    # Evidence only from slots explicitly assigned a source-game clip by the import recipe.
    spec = walkpolish.spec_of(dict(id=sid, model=str(path))) or {}
    evidence = {}
    for slot, clip in spec.get('clips', {}).items():
        s = int(slot, 0)
        if s >= len(mod.anims.table) or mod.anims.table[s] is None:
            continue
        frames, _, _ = animsheet.slot_frames(mod, len(skel), s)
        sample = frames[::max(1, len(frames) // 16)]
        world = [mmd.bone_matrices(mod, f) for f in sample]
        ranges = []
        for b in range(1, len(skel)):
            # Relative to the body: distinguish articulation from a whole-body lunge.
            xyz = [[M[b][i][3] - M[1][i][3] for i in range(3)] for M in world]
            ranges.append(round(math.sqrt(sum((max(p[i] for p in xyz) - min(p[i] for p in xyz))**2
                                              for i in range(3))), 3))
        evidence[slot] = dict(source_clip=clip['anim'], sampled_ticks=len(sample), joint_excursion=ranges)
    native_parts=None;native_branches=None
    if '0x21' in spec.get('clips',{}) or '33' in spec.get('clips',{}):
        frames,_,_=animsheet.slot_frames(mod,len(skel),33)
        native_shape=shape_at_pose(mod,skel,frames[0]);native_parts=limbmap.parts(native_shape)
        native_branches=branches(native_shape)
        endpoints=[end for end,_ in native_parts['legs']]
        if len(endpoints)!=len(set(endpoints)):
            warnings.append('Native geometry classifier repeats a support endpoint; this is not a valid limb map.')
        if any(native_parts[key]!=parts[key] for key in ('legs','arms','head','tail')):
            warnings.append('Role proposals change between donor field rest and native idle; inspect native evidence.')
    report = dict(schema=1, id=sid, name=sp['name'], input=str(path.relative_to(ROOT)),
                  input_sha256=digest(data), skeleton_sha256=skeleton_digest(skel), status='proposal_requires_visual_review',
                  locomotion='unknown', warnings=warnings, bones=bones,
                  independent_branches=branches(shape),
                  legacy_proposed_parts={k: v for k, v in parts.items() if k not in ('pos', 'tip')},
                  native_idle_proposed_parts={k:v for k,v in native_parts.items() if k not in ('pos','tip')} if native_parts else None,
                  native_idle_independent_branches=native_branches,
                  source_clip_evidence=evidence)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / f'{sid}-anatomy.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'{sid} {sp["name"]}: {len(skel)-1} model bones, {len(parts["legs"])} legacy leg / '
          f'{len(parts["arms"])} arm candidates; locomotion UNKNOWN; {len(warnings)} warnings')
    return report


def protected_native_slots(mod,spec):
    declared={int(str(key),0) for key in spec.get('clips',{})}
    streams={mod.anims.table[s] for s in declared if s<len(mod.anims.table) and mod.anims.table[s] is not None}
    return sorted(s for s,index in enumerate(mod.anims.table) if index is not None and index in streams)


def validate(recipe, skel):
    if recipe.get('schema') != 1 or recipe.get('mode') not in ('biped', 'quadruped'):
        raise ValueError('this prototype supports reviewed biped/quadruped recipes only')
    if recipe.get('anatomy_status') != 'reviewed':
        raise ValueError('anatomy must be reviewed before generating motion')
    legs = recipe['legs']
    if len(legs) != (2 if recipe['mode'] == 'biped' else 4):
        raise ValueError('support count disagrees with locomotion mode')
    used = set()
    for leg in legs:
        chain = leg['chain']
        if len(chain) not in (3,4) or any(type(b) is not int or b <= 0 or b >= len(skel) for b in chain):
            raise ValueError('each leg requires a valid three or four-joint chain')
        if len(chain)==4 and (leg.get('heel_on_shin') or any('reference_motion' not in slot for slot in recipe['slots'].values())):
            raise ValueError('four-joint legs require the reference controller and independent paw support')
        if used.intersection(chain):
            raise ValueError('leg chains must be disjoint')
        used.update(chain)
        if any(skel[c][1] != p for p, c in zip(chain, chain[1:])):
            raise ValueError('leg chain is not connected in the native skeleton')
        if not 0 <= leg['phase'] < 1:
            raise ValueError('phase must be in [0, 1)')
        if 'stance_z' in leg and (not math.isfinite(leg['stance_z']) or abs(leg['stance_z']) > .75):
            raise ValueError('stance_z must be finite and within 0.75 leg lengths of the hip')
        if 'stance_x' in leg and (not math.isfinite(leg['stance_x']) or abs(leg['stance_x']) > .75):
            raise ValueError('stance_x must be finite and within 0.75 leg lengths of the hip')
        if 'pole' in leg and (len(leg['pole']) != 3 or not all(math.isfinite(x) for x in leg['pole'])
                              or sum(x*x for x in leg['pole']) < 1e-8):
            raise ValueError('pole must be a finite nonzero direction')
        if 'knee_pole' in leg and (len(leg['knee_pole'])!=3 or not all(math.isfinite(v) for v in leg['knee_pole'])
                                  or sum(v*v for v in leg['knee_pole'])<1e-8):
            raise ValueError('knee_pole must be a finite nonzero direction')
    for arm in recipe.get('arms', []):
        b = arm['root']
        if type(b) is not int or b <= 0 or b >= len(skel) or b in used:
            raise ValueError('arm root invalid or overlaps a leg')
        if not 0 <= arm['phase'] < 1:
            raise ValueError('arm phase must be in [0, 1)')
        if not math.isfinite(arm.get('swing_scale',1)) or not 0 <= arm.get('swing_scale',1) <= 2:
            raise ValueError('arm swing scale must be finite and in 0..2')
    if not recipe['slots']:
        raise ValueError('no slots requested')
    for slot, spec in recipe['slots'].items():
        allowed=(2,3,4,35,36) if recipe.get('include_battle_movement') is True else (2,3,4)
        if int(slot,0) not in allowed:
            raise ValueError('only field locomotion and explicitly enabled battle movement are supported')
        if type(spec['ticks']) is not int or not 4 <= spec['ticks'] <= 120:
            raise ValueError('ticks must be an integer in 4..120')
        if 'reference_motion' in spec:
            if not math.isfinite(spec.get('crouch',0)) or not 0 <= spec.get('crouch',0) <= 100:
                raise ValueError('reference crouch must be finite and within 0..100')
            continue
        if type(spec.get('gait_cycles',1)) is not int or not 1 <= spec.get('gait_cycles',1) <= 4:
            raise ValueError('gait_cycles must be an integer in 1..4')
        if not 0.2 <= spec['duty'] <= 0.8:
            raise ValueError('duty must be in 0.2..0.8')
        for key in ('step_height', 'stride', 'crouch', 'bob'):
            if not math.isfinite(spec[key]) or spec[key] < 0:
                raise ValueError(f'{key} must be finite and non-negative')
        if spec['stride'] == 0:
            raise ValueError('stride must be positive')
        if any(not math.isfinite(spec.get(key,0)) or abs(spec.get(key,0)) > 45
               for key in ('arm_swing','arm_clearance')):
            raise ValueError('arm angles must be finite and within 45 degrees')
        leg_bones = {b for leg in legs for b in leg['chain']}
        if 'leg_phases' in spec and (len(spec['leg_phases']) != len(legs) or
                                     any(not math.isfinite(p) or not 0 <= p < 1 for p in spec['leg_phases'])):
            raise ValueError('leg_phases must provide one phase in 0..1 for each support')
        reference=spec.get('performance',{}).get('reference_pose')
        if reference:
            if any(type(b) is not int or b <= 0 or b >= len(skel) or b in leg_bones for b in reference['bones']):
                raise ValueError('reference pose requires non-leg native bones')
            if not math.isfinite(reference.get('weight',1)) or not 0 <= reference.get('weight',1) <= 1:
                raise ValueError('reference pose weight must be finite and in 0..1')
        for track in spec.get('performance',{}).get('tracks',[]):
            if type(track['bone']) is not int or track['bone'] <= 0 or track['bone'] >= len(skel) or track['bone'] in leg_bones:
                raise ValueError('performance tracks require non-leg native bones')
            if type(track.get('cycles',1)) is not int or not 1 <= track.get('cycles',1) <= 8:
                raise ValueError('track cycles must be an integer in 1..8')
            for field in ('rotation','translation'):
                if field not in track:continue
                keys = track[field]
                if len(keys) < 3 or any(len(key)!=4 or not all(math.isfinite(v) for v in key) for key in keys):
                    raise ValueError('performance curves need at least three finite phase/XYZ keys')
                phases = [key[0] for key in keys]
                if phases != sorted(set(phases)) or phases[0] != 0 or phases[-1] >= 1:
                    raise ValueError('curve phases must increase from 0 and remain below 1')
        for layer in spec.get('performance',{}).get('native_layers',[]):
            if any(b <= 0 or b >= len(skel) or b in leg_bones for b in layer['bones']):
                raise ValueError('native gesture layers require non-leg native bones')
            if not 0 <= layer['weight'] <= 1:
                raise ValueError('native gesture weight must be in 0..1')
            if type(layer.get('cycles',1)) is not int or not 1 <= layer.get('cycles',1) <= 8:
                raise ValueError('native gesture cycles must be an integer in 1..8')


def trajectory(phase, duty, stride, lift):
    """Local stance travels backwards at constant speed; swing has matching endpoint velocity."""
    if phase < duty:
        return stride * (phase / duty - 0.5), 0.0, True
    u = (phase - duty) / (1 - duty)
    # Cubic Hermite, with both endpoints moving at the stance speed.
    tangent = stride * (1 - duty) / duty
    z = (2*u**3 - 3*u**2 + 1) * stride/2 + (-2*u**3 + 3*u**2) * -stride/2
    z += (2*u**3 - 3*u**2 + u) * tangent
    return z, lift * math.sin(math.pi*u)**2, False


def rotate_local(pose, skel, b, desired, previous):
    wr = R.world_rots(skel, pose)
    parent = skel[b][1]
    local = R.m3mul(R.m3t(wr[parent]), desired) if parent >= 0 else desired
    angles = mmd.matrix_euler(local, previous.get(b))
    previous[b] = angles
    pose[b][3:6] = [round(x) for x in angles]


def periodic_curve(keys, phase):
    """Authored cyclic poses, interpolated with continuous first derivatives."""
    phase %= 1
    i = max(k for k,key in enumerate(keys) if key[0] <= phase)
    count = len(keys)
    def key(k):
        item = keys[k % count]
        return item[0] + k//count, item[1:]
    ta,a = key(i);tb,b = key(i+1)
    tp,p = key(i-1);tn,n = key(i+2)
    u = (phase-ta)/(tb-ta)
    return [(2*u**3-3*u*u+1)*a[j] + (-2*u**3+3*u*u)*b[j]
            + (u**3-2*u*u+u)*(b[j]-p[j])/(tb-tp)*(tb-ta)
            + (u**3-u*u)*(n[j]-a[j])/(tn-ta)*(tb-ta) for j in range(3)]


def native_gestures(mod, nb, performance):
    layers=[]
    for layer in performance.get('native_layers',[]):
        slot=int(layer['slot'],0)
        frames,loop,_ = animsheet.slot_frames(mod,nb,slot)
        if loop is None:
            raise ValueError('native gesture layer must reference an original looping clip')
        layers.append((layer,frames[loop:]))
    return layers


def performance_pose(pose, rest, phase, performance, layers):
    """Layer locally extracted native gestures, then authored full-body pose offsets."""
    for layer,frames in layers:
        position=(phase*layer.get('cycles',1)%1)*(len(frames)-1)
        i=min(int(position),len(frames)-2);alpha=position-i
        for b in layer['bones']:
            a,z=R.rot_of(frames[i][b]),R.rot_of(frames[i+1][b])
            interpolated=R.m3mul(R.scale_rot(R.m3mul(z,R.m3t(a)),alpha),a)
            delta=R.m3mul(interpolated,R.m3t(R.rot_of(frames[0][b])))
            value=R.m3mul(R.scale_rot(delta,layer['weight']),R.rot_of(pose[b]))
            pose[b][3:6]=[round(x) for x in mmd.matrix_euler(value,pose[b][3:6])]
    for track in performance.get('tracks',[]):
        b=track['bone'];p=phase*track.get('cycles',1)
        if 'rotation' in track:
            pitch,yaw,roll=periodic_curve(track['rotation'],p)
            offset=mmd.rot_matrix(*(v*4096/360 for v in (pitch,yaw,roll)))
            value=R.m3mul(offset,R.rot_of(pose[b]))
            pose[b][3:6]=[round(x) for x in mmd.matrix_euler(value,pose[b][3:6])]
        if 'translation' in track:
            offset=periodic_curve(track['translation'],p)
            pose[b][6:9]=[round(pose[b][6+j]+offset[j]) for j in range(3)]


def gesture_texture_events(mod, nb, spec, length, target_slot=None):
    performance=spec.get('performance',{})
    if 'texture_slot' not in performance:
        if target_slot is None or target_slot>=len(mod.anims.table) or mod.anims.table[target_slot] is None:return []
        # Reset the source's open eyes/material on entry, without blinking once
        # per short gait cycle or replaying unrelated later texture effects.
        _,_,events=animsheet.slot_frames(mod,nb,target_slot)
        return [(t,kind,dict(c)) for t,kind,c in events if t==0 and kind=='tex']
    slot=int(performance['texture_slot'],0)
    _,_,events=animsheet.slot_frames(mod,nb,slot)
    events=[(t,kind,dict(c)) for t,kind,c in events if kind=='tex']
    later=[t for t,_,_ in events if t>0]
    offset=round((length-1)*.62)-min(later) if later else 0
    output=[(t+offset if t>0 else 0,kind,c) for t,kind,c in events]
    if any(t>=length-1 for t,_,_ in output):raise ValueError('native texture gesture does not fit the cycle')
    return output


def generate(mod, skel, rest, recipe, spec):
    if 'reference_motion' in spec:
        import motionreference
        return motionreference.generate(mod, skel, rest, recipe, spec)
    cycles=spec.get('gait_cycles',1)
    n, duty = spec['ticks']*cycles, spec['duty']
    performance=spec.get('performance',{})
    reference=performance.get('reference_pose')
    if reference:
        rest=copy.deepcopy(rest)
        poses,_,_=animsheet.slot_frames(mod,len(skel),int(reference['slot'],0))
        for b in reference['bones']:
            current=R.rot_of(rest[b]);native=R.rot_of(poses[0][b])
            rotation=R.m3mul(R.scale_rot(R.m3mul(native,R.m3t(current)),reference.get('weight',1)),current)
            rest[b][3:6]=[round(x) for x in mmd.matrix_euler(rotation,rest[b][3:6])]
    layers=native_gestures(mod,len(skel),performance)
    W0 = mmd.bone_matrices(mod, rest)
    P0 = R.world_pos(skel, rest)
    rotations = R.world_rots(skel, rest)
    H = recipe['body']
    legs = []
    for index,leg in enumerate(recipe['legs']):
        h, k, a = leg['chain']
        lengths = [math.dist(P0[h], P0[k]), math.dist(P0[k], P0[a])]
        if min(lengths) < 1:
            raise ValueError('zero-length leg segment; a different solver is required')
        axis = legik.sub(P0[a], P0[h])
        knee = legik.sub(P0[k], P0[h])
        pole = legik.sub(knee, legik.mul(legik.unit(axis), legik.dot(knee, legik.unit(axis))))
        if 'knee_pole' in leg:pole=leg['knee_pole']
        if legik.norm(pole) < 0.1:
            pole = leg.get('pole', [0, 0, -1])
        vs = mod.tmd.obj_verts(skel[a][0])
        if not vs:
            raise ValueError('ankle needs a foot mesh for contact measurement')
        sole = max(sum(W0[a][1][j] * v[j] for j in range(3)) + W0[a][1][3] for v in vs)
        anchor_z = P0[a][2] if 'stance_z' not in leg else P0[h][2] + leg['stance_z'] * sum(lengths)
        anchor_x = P0[a][0] if 'stance_x' not in leg else P0[h][0] + leg['stance_x'] * sum(lengths)
        phase=spec.get('leg_phases',[lg['phase'] for lg in recipe['legs']])[index]
        legs.append(dict(h=h, k=k, a=a, lengths=lengths, pole=pole, sole=sole, phase=phase,
                         anchor_z=anchor_z, anchor_x=anchor_x))
    floor = max(lg['sole'] for lg in legs)
    samples, contacts, clamps = [], [], []
    previous = {}
    for t in range(n + 1):
        p = copy.deepcopy(rest)
        u = t / spec['ticks']
        p[0][8] = round(-spec['stride'] / duty * u)
        p[H][7] += round(spec['crouch'] + spec['bob'] * (1 - math.cos(4*math.pi*u))/2)
        performance_pose(p,rest,t/n,performance,layers)
        tick_contacts = []
        for lg in legs:
            h, k, a = lg['h'], lg['k'], lg['a']
            z, lift, stance = trajectory((u + lg['phase']) % 1, duty, spec['stride'], spec['step_height'])
            target = list(P0[a])
            target[0] = lg['anchor_x']
            target[2] = lg['anchor_z']
            target[1] += floor - lg['sole'] - lift
            # Integer root travel must not become foot sliding. Compensate its
            # sub-unit rounding in the IK target before quantizing joint angles.
            target[2] += z - spec['stride'] / duty * u - p[0][8]
            # Root motion is excluded while solving the local limb.
            local = copy.deepcopy(p)
            local[0][6:9] = [0, 0, 0]
            hip = R.world_pos(skel, local)[h]
            L1, L2 = lg['lengths']
            wanted = math.dist(hip, target)
            clamps.append(max(0, wanted - (L1+L2-0.001), abs(L1-L2)+0.001-wanted))
            knee, ankle = legik.solve(hip, target, L1, L2, lg['pole'])
            rotate_local(p, skel, h, R.m3mul(R.swing(legik.sub(P0[k], P0[h]), legik.sub(knee, hip)), rotations[h]), previous)
            rotate_local(p, skel, k, R.m3mul(R.swing(legik.sub(P0[a], P0[k]), legik.sub(ankle, knee)), rotations[k]), previous)
            rotate_local(p, skel, a, rotations[a], previous)
            tick_contacts.append(stance)
        for arm in recipe.get('arms', []):
            b = arm['root']
            theta = math.radians(spec.get('arm_swing', 0))*arm.get('swing_scale',1) * math.sin(2*math.pi*(u+arm['phase']))
            side = 1 if P0[b][0] > 0 else -1
            clearance = R.from_axis_angle([0, 0, 1], -side*math.radians(spec.get('arm_clearance', 0)))
            # Keep the torso's motion and the native shoulder gesture underneath.
            current = R.world_rots(skel,p)[b]
            desired = R.m3mul(R.from_axis_angle([1, 0, 0], theta), R.m3mul(clearance, current))
            rotate_local(p, skel, b, desired, previous)
        samples.append(p)
        contacts.append(tick_contacts)
    # Identical loop-end pose avoids cumulative Euler drift; root travel stays cumulative.
    samples[-1][1:] = copy.deepcopy(samples[0][1:])
    return samples, contacts, max(clamps), floor


def measure(mod, skel, samples, contacts, legs, floor):
    positions, lows, mesh_low, surfaces = [], [], [], []
    for p in samples:
        W = mmd.bone_matrices(mod, p)
        positions.append([[W[leg['chain'][-1]][i][3] for i in range(3)] for leg in legs])
        low = []
        support_surfaces=[]
        for leg in legs:
            a = leg['chain'][-1]
            support_bones=[a,leg['chain'][1]] if leg.get('heel_on_shin') else [a]
            vertices=[[sum(W[b][i][j]*v[j] for j in range(3))+W[b][i][3] for i in range(3)]
                      for b in support_bones for v in mod.tmd.obj_verts(skel[b][0])]
            low.append(max(v[1] for v in vertices))
            support_surfaces.append(vertices)
        lows.append(low)
        surfaces.append(support_surfaces)
        mesh_low.append(max(sum(W[b][1][j]*v[j] for j in range(3)) + W[b][1][3]
                            for b,(oi,_) in enumerate(skel) if oi >= 0 for v in mod.tmd.obj_verts(oi)))
    slips, contact_errors = [], []
    support_transfers=0
    for t in range(len(samples)-1):
        for j in range(len(legs)):
            if contacts[t][j] and contacts[t+1][j]:
                if legs[j].get('contact_mode')=='surface':
                    # A compound boot transfers support between shin-owned heel
                    # and toe within one tick. Use the same 3-unit contact band
                    # as the encoded ground gate during that transfer.
                    band=3 if legs[j].get('heel_on_shin') else 1
                    candidates=[math.hypot(b[0]-a[0],b[2]-a[2]) for a,b in zip(surfaces[t][j],surfaces[t+1][j])
                                if abs(a[1]-floor)<band and abs(b[1]-floor)<band]
                    if not candidates:
                        import motionsecondary
                        slips.append(motionsecondary.support_transfer_displacement(surfaces[t][j],surfaces[t+1][j],band))
                        support_transfers+=1
                    else:slips.append(min(candidates))
                else:
                    slips.append(math.hypot(positions[t+1][j][0]-positions[t][j][0],
                                            positions[t+1][j][2]-positions[t][j][2]))
            if contacts[t][j]:
                contact_errors.append(abs(lows[t][j]-floor))
    speed = abs(samples[-1][0][8]-samples[0][0][8]) / (len(samples)-1)
    return dict(stance_slip_units_per_tick=sum(slips)/max(1,len(slips)),
                stance_slip_percent_root_speed=100*sum(slips)/max(1,len(slips))/max(speed,1e-9),
                max_stance_height_error=max(contact_errors,default=0),
                max_foot_penetration=max(0,max(max(row)-floor for row in lows)),
                max_mesh_ground_penetration=max(0,max(mesh_low)-floor), root_speed=speed,
                midpoint_support_transfer_samples=support_transfers)


def mesh_ground_limit(baseline_penetration=None, tolerance=3.0):
    """Keep the absolute gate by default; an explicit exact-input baseline may allow a bounded improvement trial."""
    if baseline_penetration is None:
        return 3.0
    if not math.isfinite(baseline_penetration) or baseline_penetration < 0 or not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError('grounding baseline and tolerance must be finite and non-negative')
    return max(3.0, baseline_penetration + tolerance)


def rebuild_source(recipe, outdir):
    """Re-run the existing importer against the user's extracted original discs."""
    upstream = recipe['rebuild']
    tool = upstream['tool']
    if tool not in ('dw2mmd.py','dcb2mmd.py','dw3mmd.py'):
        raise ValueError('unsupported source importer')
    spec = (ROOT / upstream['spec']).resolve()
    if not spec.is_relative_to(ROOT) or digest(spec.read_bytes()) != upstream['spec_sha256']:
        raise ValueError('upstream import recipe changed; review and regenerate the motion recipe')
    source_dir = outdir / 'sources' / str(recipe['species'])
    source_dir.mkdir(parents=True,exist_ok=True)
    env = dict(os.environ)
    # DW2003's root reparenting shares DW2's matrix decomposition helper.
    dw2_root = env.get('DW2_ROOT',str(Path.home()/'Projects/digimonworld2'))
    env['PYTHONPATH'] = os.pathsep.join([dw2_root,env.get('PYTHONPATH','')])
    log = source_dir/'import.log'
    with log.open('w') as stream:
        subprocess.run([sys.executable,str(HERE/tool),'partner',str(spec),str(source_dir.resolve())],
                       cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,check=True)
    name = json.loads(spec.read_text())['name']
    generated = source_dir/f'{name}.MMD'
    skeleton = json.loads(generated.with_suffix('.skeleton.json').read_text())['bones']
    if skeleton_digest(skeleton) != recipe['skeleton_sha256']:
        raise ValueError('rebuilt source skeleton differs from the reviewed anatomy')
    print(f'Rebuilt source from local disc data: {generated} (log {log})')
    return generated


def build(recipe_path, outdir, rebuild=False, input_path=None):
    recipe_bytes = recipe_path.read_bytes()
    recipe = json.loads(recipe_bytes)
    sid = recipe['species']
    if rebuild and input_path is not None:
        raise ValueError('--input and --rebuild-source are mutually exclusive')
    rebuilt = rebuild_source(recipe,outdir) if rebuild else None
    source = rebuilt or input_path
    sp, path, data, mod, skel, rest = load(sid,source)
    validate(recipe, skel)
    # MMD's integer scale is Q12. Permit only quantization-level noise around
    # unit scale; the contact solver still does not support actual scaled bones.
    if has_scaled_rest_bones(rest):
        raise ValueError('scaled rest bones require a solver with scale support')
    if digest(data) != recipe['input_sha256']:
        raise ValueError('input SHA256 differs; rebuild the matching import or review this recipe again')
    if skeleton_digest(skel) != recipe['skeleton_sha256']:
        raise ValueError('native skeleton differs; the MMD hash alone cannot identify its external rig')
    body = recipe['body']
    if type(body) is not int or body <= 0 or body >= len(skel):
        raise ValueError('invalid body bone')
    if any(body in leg['chain'] or body not in [*ancestors(skel,leg['chain'][0])] for leg in recipe['legs']):
        raise ValueError('body must be a common ancestor of the legs')
    if recipe.get('include_battle_movement'):
        upstream=recipe.get('rebuild',{});spec_path=ROOT/upstream.get('spec','')
        if not spec_path.is_file() or digest(spec_path.read_bytes())!=upstream.get('spec_sha256'):
            raise ValueError('battle movement requires a pinned source import recipe')
        protected=protected_native_slots(mod,json.loads(spec_path.read_text()))
        if set(int(k,0) for k in recipe['slots'])&set(protected):raise ValueError('requested movement contains a native clip or native alias')
    before_tmd = mod.tmd.build()
    before_slots = {s: mod.anims.anims[i].build() for s,i in enumerate(mod.anims.table) if i is not None}
    baseline_frames = {}
    for key in recipe['slots']:
        s = int(key, 0)
        if s < len(mod.anims.table) and mod.anims.table[s] is not None:
            baseline_frames[s] = animsheet.slot_frames(mod, len(skel), s)[0]
    report = dict(schema=1, species=sid, name=sp['name'], input_sha256=digest(data),
                  input=str(path), texture=str(path.with_suffix('.TIM') if rebuilt else ROOT/sp['texture']['file']),
                  skeleton_sha256=skeleton_digest(skel), generator_sha256=digest(Path(__file__).read_bytes()),
                  recipe_sha256=digest(recipe_bytes), slots={}, limitations=['offline prototype; in-game validation pending'])
    if any('reference_motion' in spec for spec in recipe['slots'].values()):
        report['reference_generator_sha256']=digest((HERE/'motionreference.py').read_bytes())
        report['secondary_generator_sha256']=digest((HERE/'motionsecondary.py').read_bytes())
    if recipe.get('collision_pairs'):
        report['quality_generator_sha256']=digest((HERE/'motionquality.py').read_bytes())
        report['collision_pairs']=recipe['collision_pairs']
        report['collision_regions']=recipe.get('collision_regions',{})
        report['collision_rationale']=recipe.get('collision_rationale','Explicit disjoint native parts; excludes coplanar cases and touching seams.')
    for slot, spec in recipe['slots'].items():
        s = int(slot, 0)
        input_speed=None
        if spec.get('reference_motion',{}).get('preserve_input_speed'):
            original_frames=animsheet.slot_frames(mod,len(skel),s)[0]
            input_speed=abs(original_frames[-1][0][8]-original_frames[0][0][8])/(len(original_frames)-1)
        samples, contacts, clamp, floor = generate(mod, skel, rest, recipe, spec)
        if clamp > 1:
            raise ValueError(f'slot {slot}: unreachable foot targets ({clamp:.2f} units); reduce stride/lift or adjust crouch')
        intended = measure(mod, skel, samples, contacts, recipe['legs'], floor)
        texture_events=gesture_texture_events(mod,len(skel),spec,len(samples),s)
        if 'reference_motion' in spec:
            import motionreference
            texture_events+=motionreference.sound_events(spec,len(samples))
            texture_events.sort(key=lambda event:event[0])
        anim = mmd.encode_anim(samples, len(skel), loop_sample=0, events=texture_events, tol=0, repeats=False)
        while len(mod.anims.table) <= s:
            mod.anims.table.append(None)
        mod.anims.table[s] = len(mod.anims.anims)
        mod.anims.anims.append(anim)
        decoded, _, _ = animsheet.slot_frames(mod, len(skel), s)
        if len(decoded) != len(samples):
            raise ValueError(f'decoder duration mismatch: {len(decoded)} != {len(samples)}')
        actual = measure(mod, skel, decoded, contacts, recipe['legs'], floor)
        if input_speed is not None and abs(actual['root_speed']-input_speed)>.1:
            raise ValueError(f'slot {slot}: root speed differs from imported gameplay motion')
        angular={}
        if 'reference_motion' in spec:
            import motionreference,species
            cfg=spec['reference_motion'];source=mmd.MMD.load(species.originals().model_path(cfg['species']),cfg['species'])
            if 'gameplay_speed' in cfg:
                requested=cfg['gameplay_speed']
                if not math.isfinite(requested) or requested<=0 or abs(actual['root_speed']-requested)>.1:
                    raise ValueError(f'slot {slot}: root speed differs from authored gameplay target')
            ds=mmd.exe().skeleton[cfg['species']]
            reference_frames=animsheet.slot_frames(source,len(ds),int(cfg['slot'],0))[0]
            if cfg.get('preserve_reference_speed'):
                reference_speed=abs(reference_frames[-1][0][8]-reference_frames[0][0][8])/(len(reference_frames)-1)
                if abs(actual['root_speed']-reference_speed)>.1:
                    raise ValueError(f'slot {slot}: root speed differs from gameplay reference')
            reference_frames=[motionreference.resample(reference_frames,t/(len(decoded)-1)) for t in range(len(decoded))]
            def rates(skeleton,frames,bone):
                rotations=[R.world_rots(skeleton,p)[bone] for p in frames]
                return max(math.degrees(R.axis_angle(R.m3mul(b,R.m3t(a)))[1]) for a,b in zip(rotations,rotations[1:]))
            for target_leg,source_leg in zip(recipe['legs'],cfg['legs']):
                sb=ds[source_leg['ankle']][1]
                reference_bones=[sb]
                if len(target_leg['chain'])==4:
                    # A native thigh/stifle/hock/paw distributes a three-joint
                    # donor's movement over an extra active link. A single
                    # donor shin is not a like-for-like speed benchmark.
                    reference_bones=[ds[sb][1],sb,source_leg['ankle']]
                source_rate=max(rates(ds,reference_frames,b) for b in reference_bones)
                for joint_index,tb in enumerate(target_leg['chain'][1:-1],1):
                    if source_leg.get('chain'):
                        reference_bones=[source_leg['chain'][joint_index]]
                        source_rate=rates(ds,reference_frames,reference_bones[0])
                    target_rate=rates(skel,decoded,tb)
                    angular[str(tb)]=dict(candidate=target_rate,reference=source_rate,reference_bones=reference_bones)
                    if target_rate>source_rate*1.25+5:
                        raise ValueError(f'slot {slot}: knee/hock {tb} changes too sharply compared with reference '
                                         f'({target_rate:.3f} degrees/tick; reference {source_rate:.3f}; '
                                         f'limit {source_rate*1.25+5:.3f})')
                    if len(target_leg['chain'])==4:
                        source_envelope=motionreference.angular_envelope(ds,reference_frames,reference_bones)
                        candidate_envelope=motionreference.angular_envelope(skel,decoded,[tb])
                        angular[str(tb)]['velocity_change']=dict(candidate=candidate_envelope['max_velocity_change_degrees'],reference=source_envelope['max_velocity_change_degrees'])
                        if candidate_envelope['max_velocity_change_degrees']>source_envelope['max_velocity_change_degrees']*1.25+5:
                            raise ValueError(f'slot {slot}: knee/hock {tb} has an abrupt angular velocity change')
        # Simulate the actual infinite loop, including the engine's loop-boundary tick.
        player = mmd.AnimPlayer(anim, len(skel), s)
        repeated = []
        period = len(samples)-1
        for _ in range(period * 3 + 1):
            if not player.tick():
                raise ValueError('generated locomotion stopped instead of looping')
            p = copy.deepcopy(player.pose)
            p[0][6:9] = list(player.root)
            repeated.append(p)
        for t in range(len(repeated)-period):
            if repeated[t][1:] != repeated[t+period][1:]:
                raise ValueError('joint pose drifts across loop repetitions')
        repeated_contacts = [contacts[t % period] for t in range(len(repeated))]
        loop_metrics = measure(mod, skel, repeated, repeated_contacts, recipe['legs'], floor)
        if actual['max_foot_penetration'] > 3 or actual['max_stance_height_error'] > 3:
            raise ValueError(f'slot {slot}: encoded foot contact outside 3-unit tolerance: {actual}')
        grounding_reference = recipe.get('grounding_reference')
        if grounding_reference:
            if grounding_reference.get('mode') != 'not_worse_than_input':
                raise ValueError('unknown grounding reference mode')
            if s not in baseline_frames:
                raise ValueError(f'slot {slot}: no input animation exists for comparative grounding')
            empty_contacts = [[False] * len(recipe['legs']) for _ in baseline_frames[s]]
            baseline_ground = measure(mod, skel, baseline_frames[s], empty_contacts,
                                      recipe['legs'], floor)['max_mesh_ground_penetration']
            ground_limit = mesh_ground_limit(baseline_ground, grounding_reference.get('tolerance', 3.0))
            report.setdefault('grounding_references', {})[slot] = dict(
                mode='not_worse_than_input', input_slot=slot,
                input_max_mesh_ground_penetration=baseline_ground,
                tolerance=grounding_reference.get('tolerance', 3.0), allowed_max=ground_limit)
        else:
            ground_limit = mesh_ground_limit()
        if actual['max_mesh_ground_penetration'] > ground_limit:
            raise ValueError(f'slot {slot}: body or appendage penetrates ground beyond {ground_limit:.2f}-unit gate: {actual}')
        if loop_metrics['stance_slip_percent_root_speed'] > 10:
            raise ValueError(f'slot {slot}: loop contact slip exceeds 10%: {loop_metrics}')
        report['slots'][slot] = dict(intended=intended, decoded=actual, three_cycles=loop_metrics,
                                    max_reach_clamp=clamp, joint_drift=False,period_ticks=period,
                                    native_texture_events=sum(kind=='tex' for _,kind,_ in texture_events),
                                    reference_sound_events=sum(kind=='sound' for _,kind,_ in texture_events),
                                    knee_max_angular_step_degrees=angular)
        if recipe.get('collision_pairs'):
            import motionquality
            hits=motionquality.crossings(mod,motionquality.local_triangles(mod,skel,recipe.get('collision_regions')),decoded[:-1],recipe['collision_pairs'])
            if hits:raise ValueError(f'slot {slot}: non-coplanar mesh crossings: {hits}')
            report['slots'][slot]['checked_collision_pairs']=len(recipe['collision_pairs'])
            report['slots'][slot]['noncoplanar_crossings']={}
    idle_changed=set()
    for slot,spec in recipe.get('native_idles',{}).items():
        s=int(slot,0)
        if s not in (0,1):raise ValueError('native idle replacement only supports field idle slots 0/1')
        import motionidle
        samples,events,floor=motionidle.generate(mod,skel,rest,recipe,spec)
        anim=mmd.encode_anim(samples,len(skel),loop_sample=0,events=events,tol=0,repeats=True)
        mod.anims.table[s]=len(mod.anims.anims);mod.anims.anims.append(anim)
        decoded,loop,_=animsheet.slot_frames(mod,len(skel),s)
        if loop!=0 or len(decoded)!=len(samples):raise ValueError('native idle playback changed duration/loop')
        metrics=measure(mod,skel,decoded,[[False]*len(recipe['legs']) for _ in decoded],recipe['legs'],floor)
        if metrics['max_mesh_ground_penetration']>1:raise ValueError('native idle failed grounding')
        player=mmd.AnimPlayer(anim,len(skel),s);repeated=[];period=len(samples)-1
        for _ in range(period*3+1):
            if not player.tick():raise ValueError('native idle stopped instead of looping')
            repeated.append(copy.deepcopy(player.pose))
        if any(repeated[t][1:]!=repeated[t+period][1:] for t in range(len(repeated)-period)):
            raise ValueError('native idle joint pose drifts across repetitions')
        if recipe.get('collision_pairs'):
            import motionquality
            hits=motionquality.crossings(mod,motionquality.local_triangles(mod,skel,recipe.get('collision_regions')),decoded[:-1],recipe['collision_pairs'])
            if hits:raise ValueError(f'native idle surface crossings: {hits}')
        grounding={key:metrics[key] for key in ('max_foot_penetration','max_mesh_ground_penetration','root_speed')}
        report.setdefault('native_idles',{})[slot]=dict(source=spec['source'],decoded=grounding,
            period_ticks=period,joint_drift=False,contact_slip_status='not_certified_by_grounding_check')
        report['idle_generator_sha256']=digest((HERE/'motionidle.py').read_bytes())
        idle_changed.add(s)
    # Drop orphaned animations, retain untouched slots byte-for-byte, including battle events.
    used = sorted({i for i in mod.anims.table if i is not None})
    remap = {old:new for new,old in enumerate(used)}
    mod.anims.anims = [mod.anims.anims[i] for i in used]
    mod.anims.table = [remap[i] if i is not None else None for i in mod.anims.table]
    if mod.tmd.build() != before_tmd:
        raise ValueError('mesh changed')
    changed = {int(s,0) for s in recipe['slots']}|idle_changed
    for s, original in before_slots.items():
        if s not in changed and mod.anims.anims[mod.anims.table[s]].build() != original:
            raise ValueError(f'untouched slot {s} changed')
    result = mod.build()
    parsed = mmd.MMD.parse(result, len(skel))
    if parsed.build() != result:
        raise ValueError('MMD roundtrip failed')
    import coldsplit
    resident = len(coldsplit.split(result, len(skel))[0])
    if resident > 0x18800:
        raise ValueError(f'resident partner buffer exceeded: {resident}')
    report.update(output_sha256=digest(result), bytes=len(result), resident_bytes=resident,
                  unchanged_slots_verified=len(before_slots)-len(changed), mesh_unchanged=True)
    outdir.mkdir(parents=True, exist_ok=True)
    output = outdir / f'{sid}-{sp["name"]}.MMD'
    output.write_bytes(result)
    output.with_suffix('.report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(output=str(output), **report), indent=2))
    return output


def ancestors(skel, b):
    while skel[b][1] >= 0:
        b = skel[b][1]
        yield b


def texture_move(indices,width,height,event):
    """MoveImage rectangle: X and width are 16-bit VRAM words, four 4bpp pixels each."""
    sx,sy=event['src'];dx,dy=event['dst'];w,h=event['size']
    sx*=4;dx*=4;w*=4
    if min(sx,sy,dx,dy,w,h)<0 or sx+w>width or dx+w>width or sy+h>height or dy+h>height:
        raise ValueError('texture instruction leaves the model texture page')
    source=[list(indices[(sy+y)*width+sx:(sy+y)*width+sx+w]) for y in range(h)]
    for y,row in enumerate(source):indices[(dy+y)*width+dx:(dy+y)*width+dx+w]=row


def preview(sid, output, baseline, outdir, baseline_label='Current donor motion', label='Procedural native rig'):
    """Render actual engine-player ticks, including loop boundaries (20 Hz)."""
    import animstudio as A
    from tools.image import Image
    sp = species_info(sid)
    texture = json.loads(output.with_suffix('.report.json').read_text())['texture']
    selected=json.loads(output.with_suffix('.report.json').read_text())['slots']
    for slot, name in ((2,'walk'),(3,'condition-walk'),(4,'run')):
        if not any(int(s,0)==slot for s in selected):continue
        models = [A.Model(f'{baseline}:{sid}:{texture}:{slot}:{baseline_label}',slot),
                  A.Model(f'{output}:{sid}:{texture}:{slot}:{label}',slot)]
        ticks = 160
        for model in models:
            model.idx=model.idx.copy()
            player = mmd.AnimPlayer(model.m.anims.anims[model.m.anims.table[slot]],model.nb,slot)
            model.frames = []
            model.texture_events={}
            cursor=0
            for _ in range(ticks):
                if not player.tick():
                    raise ValueError('preview input is not a looping locomotion clip')
                p = copy.deepcopy(player.pose)
                p[0][6:9] = list(player.root)
                model.frames.append(p)
                for tick,kind,instruction in player.events[cursor:]:
                    if kind.startswith('tex'):model.texture_events.setdefault(tick,[]).append(instruction)
                cursor=len(player.events)
        rows = A.build(models,['mesh:three','mesh:side','skel:side'],320)
        tmp = Path(tempfile.mkdtemp(prefix='preview-',dir=outdir))
        try:
            shots = []
            for tick in range(ticks):
                for model in models:
                    for event in model.texture_events.get(tick,[]):
                        texture_move(model.idx.reshape(-1),model.tim.w,model.tim.h,event)
                im = A.frame(rows,tick,320)
                im.save(tmp / f'{tick:04d}.png')
                if tick in (0,7,14,21):
                    shots.append(im)
            sheet = Image.new('RGB',(shots[0].width*2,shots[0].height*2))
            for i,im in enumerate(shots):
                sheet.paste(im,((i%2)*im.width,(i//2)*im.height))
            sheet.save(outdir / f'{sp["name"]}-{name}-frames.png')
            video = outdir / f'{sp["name"]}-{name}-comparison.mp4'
            subprocess.run([A.FFMPEG,'-y','-loglevel','error','-framerate','20','-i',str(tmp/'%04d.png'),
                            '-c:v','libx264','-pix_fmt','yuv420p','-crf','20','-movflags','+faststart',str(video)],check=True)
            print(video)
        finally:
            shutil.rmtree(tmp)
    (outdir/f'{sid}-preview.json').write_text(json.dumps(dict(
        ticks=160,fps=20,baseline=str(baseline),baseline_sha256=digest(baseline.read_bytes()),
        generated=str(output),generated_sha256=digest(output.read_bytes())),indent=2)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    a = subs.add_parser('audit')
    a.add_argument('ids', type=int, nargs='+')
    a.add_argument('--preview',action='store_true',help='render textured/parts/numbered-skeleton evidence')
    b = subs.add_parser('build')
    b.add_argument('recipe', type=Path)
    b.add_argument('--rebuild-source',action='store_true',help='reimport from local original disc data; no cached model required')
    b.add_argument('--input',type=Path,help='explicit local MMD input; recipe SHA and native skeleton are still enforced')
    b.add_argument('--preview',action='store_true',help='render actual loop playback against baseline')
    b.add_argument('--baseline',type=Path,help='current reviewed donor MMD; default imported MMD')
    b.add_argument('--baseline-label',default='Current donor motion')
    b.add_argument('--label',default='Procedural native rig')
    for sub in (a,b):
        sub.add_argument('--out', type=Path, default=ROOT / 'build/motionlab')
    args = parser.parse_args()
    if args.command == 'audit':
        for sid in args.ids:
            audit(sid, args.out)
            if args.preview:
                import animstudio as A
                sp = species_info(sid)
                model = A.Model(f'{ROOT/sp["model"]["file"]}:{sid}:{ROOT/sp["texture"]["file"]}:0:{sp["name"]} native idle',0)
                A.frame(A.build([model],['mesh:three','parts:side','skel:front'],300),0,300).save(args.out/f'{sid}-anatomy.png')
    else:
        output = build(args.recipe, args.out,args.rebuild_source,args.input)
        if args.preview:
            sid = json.loads(args.recipe.read_text())['species']
            baseline = args.baseline or Path(json.loads(output.with_suffix('.report.json').read_text())['input'])
            preview(sid,output,baseline,args.out,args.baseline_label,args.label)


if __name__ == '__main__':
    main()
