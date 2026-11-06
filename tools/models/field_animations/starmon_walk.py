#!/usr/bin/env python3
"""Author Starmon's field delta from native Leomon's loose biped motion.

Use the pre-edit model from edit.py get as --source, then store --out with
edit.py put 243. This is an offline authoring recipe; the player build replays
only the verified plain delta. Mesh, rig and all programs outside 2..4 stay.
"""
import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet
import legik
import mmd
import motioncyclelayer
import retarget as R
from motiondiscidentity import changed_programs
from motiontailspace import interpolate_pose
from tools.models.field_animations.channels import replace_channels, coalesce

SLOTS = (2, 3, 4)
SOURCE_SHA256 = '6354c084fdd320feb40681a01f97fd21b18c79147a722831044aa8f3b08e4f40'
DONOR_SHA256 = '390092e3b3471adc84645a512f8671b2b036413d72e09d046fc982355f1488c7'
# Target -> donor: body, arms and four-part legs.
BONE_MAP = {1: 2, 2: 5, 3: 6, 4: 7, 5: 8, 6: 9, 7: 10,
            8: 15, 9: 16, 10: 17, 11: 18,
            12: 19, 13: 20, 14: 21, 15: 22}
CHAINS = [(2, 3, 5, 6), (3, 4, 6, 7), (5, 6, 8, 9), (6, 7, 9, 10),
          (8, 9, 15, 16), (9, 10, 16, 17), (10, 11, 17, 18),
          (12, 13, 19, 20), (13, 14, 20, 21), (14, 15, 21, 22)]
LEGS = [(8, 9, 10, 11, 17, 18), (12, 13, 14, 15, 21, 22)]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def mesh_direction(model, skeleton, bone, rotations):
    vertices = model.tmd.obj_verts(skeleton[bone][0])
    center = [sum(v[i] for v in vertices) / len(vertices) for i in range(3)]
    return [sum(rotations[bone][i][j] * center[j] for j in range(3)) for i in range(3)]


def build(data, donor_data, skeleton):
    if digest(data) != SOURCE_SHA256:
        raise ValueError('Starmon recipe requires the reviewed pre-edit imported model')
    if digest(donor_data) != DONOR_SHA256:
        raise ValueError('Starmon recipe requires native Leomon from the registered disc')
    nb = len(skeleton)
    # Use the imported model's explicit hierarchy.
    mmd.exe().add_type(243, skeleton)
    donor_skeleton = mmd.exe().skeleton[48]
    donor_nb = len(donor_skeleton)
    model = mmd.MMD.parse(data, nb)
    model.type = 243
    donor = mmd.MMD.parse(donor_data, donor_nb)
    donor.type = 48
    rest = R.rest_pose(model, nb)
    rest[1][4:6] = [0, 0]
    donor_rest = R.rest_pose(donor, donor_nb)
    rest = R.align_reference(skeleton, rest, donor_skeleton, donor_rest, CHAINS,
                             keep_world=[4, 7, 11, 15])
    # Let the hands hang naturally rather than retaining the fighting guard.
    for target_bone, source_bone in [(4, 7), (7, 10)]:
        tw = R.world_rots(skeleton, rest)
        sw = R.world_rots(donor_skeleton, donor_rest)
        desired = R.m3mul(R.swing(mesh_direction(model, skeleton, target_bone, tw),
                                  mesh_direction(donor, donor_skeleton, source_bone, sw)), tw[target_bone])
        local = R.m3mul(R.m3t(tw[skeleton[target_bone][1]]), desired)
        rest[target_bone][3:6] = [round(v) for v in mmd.matrix_euler(local)]
    mats = mmd.bone_matrices(model, rest)
    floor = max(sum(mats[b][1][j] * v[j] for j in range(3)) + mats[b][1][3]
                for b in (11, 15) for v in model.tmd.obj_verts(skeleton[b][0]))
    rest[1][7] -= round(floor)
    rp, rw = R.world_pos(skeleton, rest), R.world_rots(skeleton, rest)
    dp0 = R.world_pos(donor_skeleton, donor_rest)
    dw0 = R.world_rots(donor_skeleton, donor_rest)
    result = copy.deepcopy(model)
    checks = []
    for slot in SLOTS:
        transferred = R.transfer(donor, 48, slot, 243, rest,
                                 {t: (s, 1.) for t, s in BONE_MAP.items()}, (1, 1, .65), .65)
        donor_frames, _, _ = animsheet.slot_frames(donor, donor_nb, slot)
        secondary = animsheet.slot_frames(model, nb, 33)[0]
        frames, previous = [], {}
        for tick in range(transferred['n']):
            pose = copy.deepcopy(rest)
            for bone, seq in transferred['rot'].items():
                pose[bone][3:6] = [round(x) for x in seq[tick]]
            pose[1][6:9] = [round(rest[1][6+i] + transferred['hips'][tick][i]) for i in range(3)]
            for bone in (16, 17, 18, 19):
                pose[bone][3:6] = secondary[round(tick*(len(secondary)-1)/(transferred["n"]-1))][bone][3:6]
            # IK is in entity space. Add root travel only after the solve.
            pose[0][6:9] = [0, 0, 0]
            dp = copy.deepcopy(donor_frames[tick])
            dp[0][6:9] = [0, 0, 0]
            dw = R.world_rots(donor_skeleton, dp)
            dpos = R.world_pos(donor_skeleton, dp)

            def set_world(bone, world):
                parent = skeleton[bone][1]
                pw = R.world_rots(skeleton, pose)[parent]
                angles = mmd.matrix_euler(R.m3mul(R.m3t(pw), world), previous.get(bone))
                previous[bone] = angles
                pose[bone][3:6] = [round(x) for x in angles]

            for hip, knee, ankle, foot, donor_ankle, donor_foot in LEGS:
                # Retain native heel/toe roll and the complete foot trajectory;
                # solve for the target's lengths instead of copying knee angles.
                fw = R.m3mul(R.m3mul(dw[donor_foot], R.m3t(dw0[donor_foot])), rw[foot])
                aw = R.m3mul(R.m3mul(dw[donor_ankle], R.m3t(dw0[donor_ankle])), rw[ankle])
                target = [rp[foot][i] + .65 * (dpos[donor_foot][i] - dp0[donor_foot][i]) for i in range(3)]
                vertices = model.tmd.obj_verts(skeleton[foot][0])
                sole = max(sum(fw[1][j] * v[j] for j in range(3)) for v in vertices)
                target[1] = min(target[1], -sole)
                offset = [sum(aw[i][j] * rest[foot][6+j] for j in range(3)) for i in range(3)]
                goal = [target[i] - offset[i] for i in range(3)]
                origin = R.world_pos(skeleton, pose)[hip]
                v1, v2 = legik.sub(rp[knee], rp[hip]), legik.sub(rp[ankle], rp[knee])
                kn, ac = legik.solve(origin, goal, legik.norm(v1), legik.norm(v2), [0, 0, -1])
                set_world(hip, R.m3mul(R.swing(v1, legik.sub(kn, origin)), rw[hip]))
                set_world(knee, R.m3mul(R.swing(v2, legik.sub(ac, kn)), rw[knee]))
                set_world(ankle, aw)
                set_world(foot, fw)
            pose[0][6:9] = [round(x) for x in transferred['root'][tick]]
            frames.append(pose)
        mmd.close_loop(frames, transferred['loop'])
        # The engine blends poses between 20 Hz keys. A rolling oversized toe
        # can cross the floor between two otherwise clear poses. Lift adjacent
        # keys together, then ease the correction around the repeating seam.
        lifts = [0.] * len(frames)
        for tick in range(len(frames)-1):
            for alpha in (0, 1365, 2730, 4096):
                pose = interpolate_pose(frames[tick], frames[tick+1], alpha)
                pose[0][6:9] = [0, 0, 0]
                mats = mmd.bone_matrices(model, pose)
                floor = max(sum(mats[b][1][j] * v[j] for j in range(3)) + mats[b][1][3]
                            for b in (11, 15) for v in model.tmd.obj_verts(skeleton[b][0]))
                correction = max(0., floor + .25)
                lifts[tick] = max(lifts[tick], correction)
                lifts[tick+1] = max(lifts[tick+1], correction)
        assert transferred['loop'] == 0
        lifts[0] = lifts[-1] = max(lifts[0], lifts[-1])
        # Expand each peak with a gentle three-tick envelope; never reduce a
        # clearance correction. This preserves clearance while easing the correction.
        steady = len(frames)-1
        lifts = [max(lifts[j] - 2*min((i-j) % steady, (j-i) % steady)
                     for j in range(steady)) for i in range(steady)]
        lifts.append(lifts[0])
        for pose, lift in zip(frames, lifts):
            pose[1][7] -= round(lift)
        events = [(t, kind, command) for t, kind, command in transferred['events'] if kind == 'sound']
        anim = mmd.encode_anim(frames, nb, transferred['loop'], events, tol=1, repeats=False)
        # Keep support curves precise while fitting the original unsplit
        # resident buffer. The torso, arms and tail permit wider key spacing;
        # only their Euler curves use the larger fitting tolerance.
        scratch = copy.deepcopy(model)
        scratch.anims.anims.append(anim)
        scratch.anims.table[slot] = len(scratch.anims.anims)-1
        encoded, encoded_loop, _ = animsheet.slot_frames(scratch, nb, slot)
        support = set(range(8, 16)) | {1}
        anim = replace_channels(anim, encoded, encoded_loop, nb,
                                {(b, c) for b in range(1, nb) if b not in support for c in range(3, 6)},
                                tolerance=24)
        anim = replace_channels(anim, encoded, encoded_loop, nb,
                                {(b, c) for b in support for c in range(3, 6)}, tolerance=1)
        anim, _ = coalesce(anim)
        result.anims.table[slot] = len(result.anims.anims)
        result.anims.anims.append(anim)
        checks.append(dict(slot=slot, samples=len(frames), loop_sample=transferred['loop'], max_clearance_lift=max(lifts)))
    # Keep consumed programs; discard obsolete streams and unconsumed parse tails.
    for anim in result.anims.anims:
        anim.tail = b''
    result.anims.anims, result.anims.table = motioncyclelayer.share_identical_streams(
        result.anims.anims, result.anims.table)
    output = result.build()
    parsed = mmd.MMD.parse(output, nb)
    parsed.type = 243
    assert changed_programs(model, parsed) == list(SLOTS)
    assert model.tmd.build() == parsed.tmd.build()
    assert parsed.build() == output
    # Validate the encoded result, including the engine's blend samples.
    for check in checks:
        slot = check['slot']
        samples, loop, _ = animsheet.slot_frames(parsed, nb, slot)
        donor_samples, donor_loop, _ = animsheet.slot_frames(donor, donor_nb, slot)
        assert loop == donor_loop and len(samples) == len(donor_samples)
        assert all(abs(p[0][8] - round(q[0][8]*.65)) <= 1 for p, q in zip(samples, donor_samples))
        assert max(abs(p[0][c]-round(q[0][c]*.65)) for p, q in zip(samples, donor_samples) for c in (6, 7)) <= 1
        worst = -float('inf')
        for tick in range(len(samples)-1):
            for alpha in (0, 1365, 2730, 4096):
                pose = interpolate_pose(samples[tick], samples[tick+1], alpha)
                pose[0][6:9] = [0, 0, 0]
                mats = mmd.bone_matrices(parsed, pose)
                worst = max(worst, max(sum(mats[b][1][j] * v[j] for j in range(3)) + mats[b][1][3]
                                       for b in (11, 15) for v in parsed.tmd.obj_verts(skeleton[b][0])))
        assert worst <= 1.5, (slot, worst)
        check['max_sole_y_at_ticks_and_thirds'] = worst
        check['native_scaled_forward_root_and_duration_exact'] = True
        check['lateral_root_quantization_max'] = 1
    import motionstorage
    storage = motionstorage.require(output, nb)
    return output, dict(species=243, source_sha256=digest(data), donor_sha256=digest(donor_data),
                        output_sha256=digest(output), changed_slots=list(SLOTS),
                        mesh_unchanged=True, all_other_programs_exact=True,
                        checks=checks, storage=storage)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', required=True, type=Path)
    p.add_argument('--donor', default=ROOT / 'extracted/CHDAT/MMD1/LEOM.MMD', type=Path)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--report', type=Path)
    args = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/243-starmon.json').read_text())['model']['skeleton']
    output, report = build(args.source.read_bytes(), args.donor.read_bytes(), skeleton)
    args.out.write_bytes(output)
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(f'{args.out}: {len(output)} bytes; SHA-256 {digest(output)}')


if __name__ == '__main__':
    main()
