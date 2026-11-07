#!/usr/bin/env python3
"""Author imported locomotion from anatomically mapped native performances.

This offline tool bakes the final reviewed proportions and acting into a plain
model delta. The player build needs no additional runtime animation layer.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet
import legik
import mmd
import motioncyclelayer
import motionstorage
import motionsecondary
import retarget as rt
from motiondiscidentity import changed_programs
from motiontailspace import interpolate_pose


def digest(data):
    return hashlib.sha256(data).hexdigest()


def cyclic_eulers(frames):
    """Choose a continuous Euler chart around a complete repeating stride.

    Equivalent Euler triples can interpolate along very different paths. Fit
    the whole cycle against rotation-space midpoints, including its seam.
    """
    count = len(frames)-1
    for bone in range(1, len(frames[0])):
        choices = []
        for pose in frames[:-1]:
            a = mmd.matrix_euler(mmd.rot_matrix(*pose[bone][3:6]))
            choices.append([a, [a[0]+2048, 2048-a[1], a[2]+2048]])
        def cost(a, b):
            delta = [(y-x+2048)%4096-2048 for x,y in zip(a,b)]
            ra, rb = mmd.rot_matrix(*a), mmd.rot_matrix(*b)
            middle = rt.m3mul(rt.scale_rot(rt.m3mul(rb, rt.m3t(ra)), .5), ra)
            linear = mmd.rot_matrix(*[x+d*.5 for x,d in zip(a,delta)])
            return 1e8*sum((linear[i][j]-middle[i][j])**2 for i in range(3) for j in range(3))+sum(d*d for d in delta)
        best = None
        for start in (0, 1):
            states = {start: (0., [start])}
            for tick in range(1, count):
                states = {n: min((value+cost(choices[tick-1][p],choices[tick][n]), path+[n])
                                  for p,(value,path) in states.items()) for n in (0,1)}
            candidate = min((value+cost(choices[-1][end],choices[0][start]),path)
                            for end,(value,path) in states.items())
            if best is None or candidate[0] < best[0]: best = candidate
        previous = None
        for pose, options, choice in zip(frames, choices, best[1]):
            angles = options[choice]
            if previous is not None:
                angles = [x+4096*round((p-x)/4096) for x,p in zip(angles,previous)]
            pose[bone][3:6] = previous = [round(v) for v in angles]
        frames[-1][bone] = copy.deepcopy(frames[0][bone])


def proportions(data, skeleton, cfg):
    """Bake explicit local fits into mesh pieces and every child translation."""
    model = mmd.MMD.parse(data, len(skeleton))
    for key, factor in cfg.get('local_scales', {}).items():
        bone = int(key)
        obj = model.tmd.objects[skeleton[bone][0]]
        for index in range(obj.vert_start, obj.vert_start+obj.nvert):
            vertex = model.tmd.verts[index]
            model.tmd.verts[index] = tuple([round(v*factor) for v in vertex[:3]]+[vertex[3]])
        children = [b for b, (_, parent) in enumerate(skeleton) if parent == bone]
        for anim in model.anims.anims:
            first = 6 if anim.has_scale else 3
            for child in children:
                anim.pose[child-1][first:first+3] = [round(v*factor) for v in anim.pose[child-1][first:first+3]]
            for ins in anim.instrs:
                if ins['op'] == 'key':
                    for group in ins['bones']:
                        if group['bone'] in children:
                            for channel in ('tx', 'ty', 'tz'):
                                if channel in group['vals']:
                                    group['vals'][channel] = round(group['vals'][channel]*factor)
    return model.build()


def author(data, skeleton, sid, cfg):
    """Transfer native timing and trajectories, solving imported limb lengths."""
    mmd.exe().add_type(sid, skeleton)
    nb = len(skeleton)
    old = mmd.MMD.parse(data, nb)
    old.type = sid
    donor_id = cfg['donor']
    donor_data = (ROOT / cfg['model']).read_bytes()
    if cfg.get('donor_sha256') and digest(donor_data) != cfg['donor_sha256']:
        raise ValueError('Native donor differs from the reviewed disc model')
    donor = mmd.MMD.parse(donor_data, mmd.exe().bone_count[donor_id])
    donor.type = donor_id
    ds = mmd.exe().skeleton[donor_id]
    dn = len(ds)
    if cfg.get('mirror_free_arm'):
        # Leomon's left arm carries a sword. Map its free shoulder, elbow and
        # wrist across the sagittal plane for an unarmed bilateral performance.
        reflect = [[-1, 0, 0], [0, 1, 0], [0, 0, 1]]
        for slot in (0, 2, 3, 4):
            samples, loop, events = animsheet.slot_frames(donor, dn, slot)
            original_samples = copy.deepcopy(samples)
            history = {}
            for tick, pose in enumerate(samples):
                # Opposite arms accompany opposite legs. Reflection alone
                # would make both free arms swing forward at the same time.
                phase = tick if slot == 0 else (tick+(len(samples)-1)//2) % (len(samples)-1)
                source_pose = original_samples[phase]
                rotations = rt.world_rots(ds, source_pose)
                current_rotations = rt.world_rots(ds, pose)
                positions = rt.world_pos(ds, source_pose)
                for target, source in ((8, 5), (9, 6), (10, 7)):
                    if target in (8, 9):
                        child, source_child = target+1, source+1
                        current = [sum(current_rotations[target][i][j]*pose[child][6+j] for j in range(3)) for i in range(3)]
                        chord = [positions[source_child][i]-positions[source][i] for i in range(3)]
                        chord[0] = -chord[0]
                        desired = rt.m3mul(rt.swing(current, chord), current_rotations[target])
                    else:
                        desired = rt.m3mul(rt.m3mul(reflect, rotations[source]), reflect)
                    parent = rt.world_rots(ds, pose)[ds[target][1]]
                    angles = mmd.matrix_euler(rt.m3mul(rt.m3t(parent), desired), history.get(target))
                    history[target] = angles
                    pose[target][3:6] = [round(v) for v in angles]
            donor.anims.table[slot] = len(donor.anims.anims)
            donor.anims.anims.append(mmd.encode_anim(samples, dn, loop, events, tol=1, repeats=False))
    rest = rt.rest_pose(old, nb, cfg.get('rest_slot', 33))
    dr = rt.rest_pose(donor, dn)
    mapping = {int(k): (v, 1.) for k, v in cfg['map'].items()}
    for key, weight in cfg.get('rotation_weights', {}).items():
        mapping[int(key)] = (mapping[int(key)][0], weight)
    chains = cfg['chains']
    feet = cfg['feet']
    rest = rt.align_reference(skeleton, rest, ds, dr, chains,
                              keep_world=cfg.get('keep_world', feet))
    if cfg.get('anatomical_terminals'):
        def set_reference_world(bone, desired):
            rotations = rt.world_rots(skeleton, rest)
            local = rt.m3mul(rt.m3t(rotations[skeleton[bone][1]]), desired)
            rest[bone][3:6] = [round(v) for v in mmd.matrix_euler(local)]

        def direction(model, sk, bone, rotations):
            vertices = model.tmd.obj_verts(sk[bone][0])
            center = [sum(v[i] for v in vertices)/len(vertices) for i in range(3)]
            return [sum(rotations[bone][i][j]*center[j] for j in range(3)) for i in range(3)]

        # End joints have no descendant chord. Calibrate their mesh direction
        # explicitly instead of inheriting an asymmetric imported guard pose.
        for bone, donor_bone in cfg.get('hands', []):
            rotations = rt.world_rots(skeleton, rest)
            turn = rt.swing(direction(old, skeleton, bone, rotations), [0, 1, 0])
            set_reference_world(bone, rt.m3mul(turn, rotations[bone]))
        ankles = set()
        for _, _, ankle, foot, _, _ in cfg['legs']:
            if ankle == foot:
                continue
            ankles.add(ankle)
            positions = rt.world_pos(skeleton, rest)
            toe = [positions[foot][i]-positions[ankle][i] for i in range(3)]
            rotations = rt.world_rots(skeleton, rest)
            turn = rt.from_axis_angle([0, 1, 0], math.atan2(toe[0], -toe[2]))
            set_reference_world(ankle, rt.m3mul(turn, rotations[ankle]))
        for bone in set(feet)-ankles:
            rotations = rt.world_rots(skeleton, rest)
            toe = direction(old, skeleton, bone, rotations)
            # Meshes extend from the ankle toward the toes. Preserve sole
            # pitch while calibrating the anatomical forward axis to -Z.
            yaw = math.atan2(toe[0], -toe[2])
            turn = rt.from_axis_angle([0, 1, 0], yaw)
            set_reference_world(bone, rt.m3mul(turn, rotations[bone]))
    carrier = cfg['carrier']
    def ground(pose):
        p = copy.deepcopy(pose)
        p[0] = [4096]*3 + [0]*6
        mats = mmd.bone_matrices(old, p)
        return max(sum(mats[b][1][j]*v[j] for j in range(3)) + mats[b][1][3]
                   for b in feet for v in old.tmd.obj_verts(skeleton[b][0]))
    rest[carrier][7] -= round(ground(rest))
    rp, rw = rt.world_pos(skeleton, rest), rt.world_rots(skeleton, rest)
    dp0, dw0 = rt.world_pos(ds, dr), rt.world_rots(ds, dr)
    result = copy.deepcopy(old)
    reports = []
    for slot in cfg.get('slots', [2, 3, 4]):
        scale = cfg.get('scales', {}).get(str(slot), cfg['scale'])
        donor_slot = cfg.get('donor_slots', {}).get(str(slot), slot)
        moved = rt.transfer(donor, donor_id, donor_slot, sid, rest, mapping,
                            (carrier, 1, scale), scale)
        source_frames = animsheet.slot_frames(old, nb, 33)[0]
        native_frames = animsheet.slot_frames(donor, dn, donor_slot)[0]
        auxiliary = None
        if cfg.get('wing_map'):
            wing = mmd.MMD.load(str(ROOT / 'extracted/CHDAT/MMD0/ANGE.MMD'), 20)
            auxiliary = rt.transfer(wing, 20, donor_slot, sid, rest,
                                    {int(t): (s, 1.) for t, s in cfg['wing_map'].items()})
        frames, previous = [], {}
        for tick in range(moved['n']):
            p = copy.deepcopy(rest)
            for b in cfg.get('secondary', []):
                p[b][3:6] = source_frames[round(tick*(len(source_frames)-1)/(moved['n']-1))][b][3:6]
            for b, seq in moved['rot'].items():
                delay = cfg.get('rotation_delays', {}).get(str(b), 0)
                sample = (tick-delay) % (moved['n']-1) if delay else tick
                p[b][3:6] = [round(v) for v in seq[sample]]
            if auxiliary:
                sample = round(tick*(auxiliary['n']-1)/(moved['n']-1))
                for b, seq in auxiliary['rot'].items():
                    p[b][3:6] = [round(v) for v in seq[sample]]
            p[carrier][6:9] = [round(rest[carrier][6+i]+moved['hips'][tick][i]) for i in range(3)]
            if 'vertical_motion' in cfg:
                p[carrier][7] = round(rest[carrier][7]+moved['hips'][tick][1]*cfg['vertical_motion'])
            dp = copy.deepcopy(native_frames[tick]); dp[0][6:9] = [0, 0, 0]
            dw, positions = rt.world_transform(ds, dp)
            def world_rotation(b, rotation):
                parent = skeleton[b][1]
                inv = rt.m3t(rt.world_rots(skeleton, p)[parent])
                euler = mmd.matrix_euler(rt.m3mul(inv, rotation), previous.get(b))
                previous[b] = euler
                p[b][3:6] = [round(v) for v in euler]
            for hip, knee, ankle, foot, donor_ankle, donor_foot in cfg['legs']:
                fw = rt.m3mul(rt.m3mul(dw[donor_foot], rt.m3t(dw0[donor_foot])), rw[foot])
                aw = rt.m3mul(rt.m3mul(dw[donor_ankle], rt.m3t(dw0[donor_ankle])), rw[ankle])
                target = [rp[foot][i]+scale*(positions[donor_foot][i]-dp0[donor_foot][i]) for i in range(3)]
                vertices = old.tmd.obj_verts(skeleton[foot][0])
                sole = max(sum(fw[1][j]*v[j] for j in range(3)) for v in vertices)
                target[1] = min(target[1], -sole)
                if cfg.get('contact_height'):
                    dv = donor.tmd.obj_verts(ds[donor_foot][0])
                    bottom = max(sum(dw[donor_foot][1][j]*v[j] for j in range(3))
                                 + positions[donor_foot][1] for v in dv)
                    target[1] = -sole + min(0, bottom)*scale*cfg.get('foot_lift', 1.)
                offset = [sum(aw[i][j]*rest[foot][6+j] for j in range(3)) for i in range(3)] if ankle != foot else [0]*3
                goal = [target[i]-offset[i] for i in range(3)]
                origin = rt.world_pos(skeleton, p)[hip]
                v1, v2 = legik.sub(rp[knee], rp[hip]), legik.sub(rp[ankle], rp[knee])
                pole = cfg.get('pole', [0, 0, -1])
                if cfg.get('native_bend'):
                    pole = motionsecondary.transported_native_pole(rp[hip], rp[knee], rp[ankle], origin, goal)
                kn, ac = legik.solve(origin, goal, legik.norm(v1), legik.norm(v2), pole)
                if cfg.get('native_bend'):
                    rotations = motionsecondary.native_plane_rotations(
                        [rp[b] for b in (hip, knee, ankle)], [origin, kn, ac], [rw[b] for b in (hip, knee)])
                    world_rotation(hip, rotations[0])
                    world_rotation(knee, rotations[1])
                else:
                    world_rotation(hip, rt.m3mul(rt.swing(v1, legik.sub(kn, origin)), rw[hip]))
                    world_rotation(knee, rt.m3mul(rt.swing(v2, legik.sub(ac, kn)), rw[knee]))
                world_rotation(ankle, aw)
                world_rotation(foot, fw)
            p[0][6:9] = [round(v) for v in moved['root'][tick]]
            if cfg.get('ground_contact') and not cfg.get('sole_contacts'):
                p[carrier][7] -= round(ground(p))
            gap = cfg.get('maximum_support_gap', {}).get(str(slot))
            if gap is not None and not cfg.get('sole_contacts') and ground(p) < -gap:
                p[carrier][7] += round(-gap-ground(p))
            frames.append(p)
        mmd.close_loop(frames, moved['loop'])
        if cfg.get('ground_contact') or cfg.get('maximum_support_gap'):
            frames[-1][1:] = copy.deepcopy(frames[0][1:])
            cyclic_eulers(frames)
        # Clearance includes the engine's interpolated poses, with an eased
        # cyclic envelope so adjacent keys never create a height snap.
        lifts = [0.] * len(frames)
        for tick in range(len(frames)-1):
            for alpha in (0, 1365, 2730, 4096):
                lift = max(0., ground(interpolate_pose(frames[tick], frames[tick+1], alpha))+.5)
                lifts[tick] = max(lifts[tick], lift)
                lifts[tick+1] = max(lifts[tick+1], lift)
        period = len(frames)-1
        lifts[0] = lifts[-1] = max(lifts[0], lifts[-1])
        lifts = [max(lifts[j]-1.5*min((i-j)%period, (j-i)%period)**2 for j in range(period)) for i in range(period)]
        lifts.append(lifts[0])
        if not cfg.get('sole_contacts'):
            for p, lift in zip(frames, lifts):
                p[carrier][7] -= round(lift)
        if cfg.get('sole_contacts'):
            from tools.models.field_animations.sole_contacts import bake
            frames = bake(old, frames, skeleton, cfg, slot)
        events = [(t, kind, ins) for t, kind, ins in moved['events'] if kind == 'sound']
        if str(slot) in cfg.get('retime', {}):
            from tools.models.field_animations.pace import _root_channels, _retimed_events
            timing = cfg['retime'][str(slot)]
            events = _retimed_events(events, len(frames)-1, timing['ticks'])
            frames = _root_channels(frames, timing['ticks'], timing['speed'])
            mmd.close_loop(frames, moved['loop'])
        animation = mmd.encode_anim(frames, nb, moved['loop'], events, tol=cfg.get('tolerance', 2), repeats=False)
        result.anims.table[slot] = len(result.anims.anims)
        result.anims.anims.append(animation)
        reports.append(dict(slot=slot, samples=len(frames), native_timing=str(slot) not in cfg.get('retime', {}), scale=scale, max_lift=max(lifts)))
    for anim in result.anims.anims:
        anim.tail = b''
    result.anims.anims, result.anims.table = motioncyclelayer.share_identical_streams(result.anims.anims, result.anims.table)
    output = result.build()
    parsed = mmd.MMD.parse(output, nb)
    assert parsed.tmd.build() == old.tmd.build()
    assert changed_programs(old, parsed) == cfg.get('slots', [2, 3, 4])
    storage = motionstorage.audit(output, nb)
    return output, dict(species=sid, source_sha256=digest(data), donor_sha256=digest(donor_data),
                        output_sha256=digest(output), checks=reports, storage=storage,
                        mesh_exact=True, other_programs_exact=True)


def build(data, cfg):
    """Replay the same anatomical recipe on a verified source-release model."""
    sid = cfg['species']
    output, report = author(data, cfg['skeleton'], sid, cfg)
    if cfg.get('local_scales'):
        # Apply a local neck fit after authoring, so the native head motion is
        # retained and the shortened attachment is identical in every clip.
        output = proportions(output, cfg['skeleton'], cfg)
        report['local_scales'] = cfg['local_scales']
    if cfg.get('resize'):
        from tools.models.resize import resize
        n = len(cfg['skeleton'])
        unscaled = mmd.MMD.parse(output, n); unscaled.type = sid
        scaled = mmd.MMD.parse(resize(output, n, cfg['resize']), n); scaled.type = sid
        # Scaling packed momentum rounds each velocity independently. Sample
        # the authored field loops before scaling to keep exact seam closure.
        for slot in cfg.get('slots', [2, 3, 4]):
            frames, loop, events = animsheet.slot_frames(unscaled, n, slot)
            for pose in frames:
                for bone in pose:
                    bone[6:9] = [round(v*cfg['resize']) for v in bone[6:9]]
            mmd.close_loop(frames, loop)
            scaled.anims.table[slot] = len(scaled.anims.anims)
            scaled.anims.anims.append(mmd.encode_anim(frames, n, loop, events, tol=1, repeats=False))
        scaled.anims.anims, scaled.anims.table = motioncyclelayer.share_identical_streams(scaled.anims.anims, scaled.anims.table)
        output = scaled.build()
        report['resize'] = cfg['resize']
    if cfg.get('appendage_clearance'):
        from tools.models.field_animations.sole_contacts import clear_appendages
        output, report['appendage_clearance'] = clear_appendages(output, sid, cfg['skeleton'], cfg)
    report['output_sha256'] = digest(output)
    report['storage'] = motionstorage.require(output, len(cfg['skeleton']))
    return output, report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('recipe', type=Path)
    p.add_argument('source', type=Path)
    p.add_argument('out', type=Path)
    a = p.parse_args()
    cfg = json.loads(a.recipe.read_text())
    data = a.source.read_bytes()
    if digest(data) != cfg['source_sha256']:
        raise SystemExit('Source differs from the reviewed model')
    output, report = build(data, cfg)
    if cfg.get('output_sha256') and report['output_sha256'] != cfg['output_sha256']:
        raise SystemExit('Authored model differs from the reviewed output')
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_bytes(output)
    a.out.with_suffix('.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
