"""Paildramon's field walk, condition walk and run, taken from native Leomon's.

Offline authoring only: player builds replay the pinned plain delta. Run with --source and --out, then store the
result with tools/models/edit.py put 199.

The imported walk and run (kept by the paildramon-field proportions pass) snapped a foot from one place to another
between two ticks of the walk and slid both feet; the run was the walk sped up. These clips take Leomon's own walk,
condition walk and run (an upright warrior on two legs, arms free) the way angewomon.py does for Angewomon:

- The pelvis, spine, neck, head, arms and tail turn in the world as Leomon's homologous bones turn from his idle
  (a part of his lean, as Paildramon already stands leaning forward; the arms a part of his swing, raised at the shoulder only as far as the
  claws need to stay off the ground). The wings and the hip blades keep their places on the body and follow it.
- Leomon's feet are the targets: each foot moves from Paildramon's own wide stance as Leomon's moves from his,
  scaled by the longer legs, and lifts as high over the stance as Leomon's ankle does. A two-bone solve on the
  thigh and shin reaches it in the plane the leg bends in (the bowed stance kept); the body comes down only as far
  as a planted foot needs.
- The walk is eased over 18 ticks and the run over 13 (Leomon's are 16). Leomon's own condition walk slides his
  feet, so the condition walk is his walk over 24 ticks, a shorter stride and the body carried lower; a carrier
  lift spread over neighbouring ticks keeps the feet out of the floor at every 60 fps third.

The source is the paildramon-field proportions output, which this delta bakes in (the overlay is retired). The
idle and every other program, and the mesh, stay exact.
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
import animsheet  # noqa: E402
import legik  # noqa: E402
import mmd  # noqa: E402
import motioncyclelayer  # noqa: E402
import motionsecondary  # noqa: E402
import motionstorage  # noqa: E402
import retarget as R  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from motiontailspace import interpolate_pose  # noqa: E402

SOURCE = '08717642af8a5c67463c49bec57609d079aa73098e17e9d21265b43fa413b8d9'
DONOR = '390092e3b3471adc84645a512f8671b2b036413d72e09d046fc982355f1488c7'
SPECIES = 199
NB = 31
DONOR_TYPE = 48
DNB = 23
PELVIS = 5
TRAVEL = 1.26           # Paildramon's hip-to-ankle reach is about 1.26 times Leomon's
# (hip, knee, foot) of his, then Leomon's
LEGS = [(12, 13, 14, 19, 20, 21), (15, 16, 17, 15, 16, 17)]
FEET = (14, 17)
# his bone: Leomon's bone
ARM = 0.4     # the arms hang wide and forward: they take part of Leomon's swing
# (shoulder, arm bones): in the run's lean an arm swings up only as far as its claws stay off the ground
ARMS = ((6, (6, 7, 8)), (9, (9, 10, 11)))
MAP = {5: 1, 4: 2, 3: 2, 2: 3, 1: 4,
       9: (5, ARM), 10: (6, ARM), 11: (7, ARM), 6: (8, ARM), 7: (9, ARM), 8: (10, ARM),
       26: 12, 27: 13, 28: 14,
       12: 19, 13: 20, 14: 21, 15: 15, 16: 16, 17: 17}
# Leomon's own condition walk slides his feet; the condition walk is his walk, slower, shorter and lower
DONOR_SLOT = {2: 2, 3: 2, 4: 4}
DURATION = {2: 18, 3: 24, 4: 13}
STRIDE = {2: 0.8, 3: 0.8, 4: 0.6}
SAG = {2: 0, 3: 10, 4: 0}       # how much lower the body is carried
# Leomon peels his heel up to 63 degrees; the big clawed feet take a third of his foot's turn
FOOT_TURN = 0.35
DEAD = 5   # how far an ankle moves in Leomon's stance as the foot rolls; only height above it is a lift
# Leomon walks with his chest 21 degrees and runs with it 60 degrees further forward than he stands; Paildramon
# already stands leaning forward and takes only part of it
LEAN = {2: 0.4, 3: 0.55, 4: 0.4}
BODY = (5, 4, 3, 2, 1)


def boot_floor(model, skeleton, pose):
    p = copy.deepcopy(pose)
    p[0] = [4096] * 3 + [0] * 6
    mats = mmd.bone_matrices(model, p)
    return max(sum(mats[b][1][j] * v[j] for j in range(3)) + mats[b][1][3]
               for b in FEET for v in model.tmd.obj_verts(skeleton[b][0]))


def build(data, donor_data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('requires the reviewed Paildramon proportions')
    if hashlib.sha256(donor_data).hexdigest() != DONOR:
        raise ValueError('requires native Leomon from the registered disc')
    mmd.exe().add_type(SPECIES, skeleton)
    model = mmd.MMD.parse(data, NB)
    model.type = SPECIES
    donor = mmd.MMD.parse(donor_data, DNB)
    donor.type = DONOR_TYPE
    ds = mmd.exe().skeleton[DONOR_TYPE]
    rest, dr = R.rest_pose(model, NB), R.rest_pose(donor, DNB)
    chains = [(h, k, dh, dk) for h, k, f, dh, dk, df in LEGS]
    chains += [(k, f, dk, df) for h, k, f, dh, dk, df in LEGS]
    rest = R.align_reference(skeleton, rest, ds, dr, chains, keep_world=list(FEET), sagittal=True)
    rest[PELVIS][7] -= round(boot_floor(model, skeleton, rest))
    rp, rw = R.world_pos(skeleton, rest), R.world_rots(skeleton, rest)
    dw0 = R.world_rots(ds, dr)
    # each knee bends the way it stands: out over the wide stance and a little forward
    knee_out = {}
    for hip, knee, foot, *_ in LEGS:
        axis = legik.unit(legik.sub(rp[foot], rp[hip]))
        offset = legik.sub(rp[knee], rp[hip])
        knee_out[hip] = legik.sub(offset, legik.mul(axis, legik.dot(offset, axis)))
    dp0 = R.world_pos(ds, dr)
    result = copy.deepcopy(model)
    checks = []
    streams = {}
    for slot in (2, 3, 4):
        native, loop, events = animsheet.slot_frames(donor, DNB, DONOR_SLOT[slot])
        transfer = R.transfer(donor, DONOR_TYPE, DONOR_SLOT[slot], SPECIES, rest, {t: s if isinstance(s, tuple) else (s, LEAN[slot] if t in BODY else 1.) for t, s in MAP.items()},
                              (PELVIS, 1, TRAVEL), TRAVEL * STRIDE[slot])
        frames, history = [], {}
        ground = {}
        for source in native:
            dp = copy.deepcopy(source)
            dp[0] = [4096] * 3 + [0] * 6
            for *_, df in LEGS:
                ground[df] = max(ground.get(df, -1e9), R.world_pos(ds, dp)[df][1])
        worst_reach = 0.
        support_drops = []
        for tick, source in enumerate(native):
            pose = copy.deepcopy(rest)
            for bone, seq in transfer['rot'].items():
                pose[bone][3:6] = [round(v) for v in seq[tick]]
            pose[PELVIS][6:9] = [round(rest[PELVIS][6 + i] + transfer['hips'][tick][i]) for i in range(3)]
            pose[PELVIS][7] += SAG[slot]
            pose[0][6:9] = [0, 0, 0]
            dp = copy.deepcopy(source)
            dp[0] = [4096] * 3 + [0] * 6
            dw, dpos = R.world_rots(ds, dp), R.world_pos(ds, dp)

            def set_world(bone, world):
                parent = R.world_rots(skeleton, pose)[skeleton[bone][1]]
                angles = mmd.matrix_euler(R.m3mul(R.m3t(parent), world), history.get(bone))
                history[bone] = angles
                pose[bone][3:6] = [round(v) for v in angles]
            goals = []
            for hip, knee, foot, dh, dk, df in LEGS:
                turn = mmd.matrix_euler(R.m3mul(dw[df], R.m3t(dw0[df])))
                fw = R.m3mul(mmd.rot_matrix(*[FOOT_TURN * a for a in turn]), rw[foot])
                sole = max(sum(fw[1][j] * v[j] for j in range(3)) for v in model.tmd.obj_verts(skeleton[foot][0]))
                # her own stance (track and place under the hip), moved as Angemon's foot moves from his
                target = [rp[foot][i] + TRAVEL * STRIDE[slot] * (dpos[df][i] - dp0[df][i]) for i in range(3)]
                target[1] = -sole - TRAVEL * max(0, ground[df] - dpos[df][1] - DEAD)
                goals.append((hip, knee, foot, fw, target))
            positions = R.world_pos(skeleton, pose)
            down = 0.
            for hip, knee, foot, fw, target in goals:
                origin = positions[hip]
                length = legik.norm(legik.sub(rp[knee], rp[hip])) + legik.norm(legik.sub(rp[foot], rp[knee])) - 2
                horizontal = (target[0] - origin[0]) ** 2 + (target[2] - origin[2]) ** 2
                assert horizontal < length ** 2, (slot, tick, horizontal ** .5, length)
                down = max(down, target[1] - origin[1] - math.sqrt(length ** 2 - horizontal))
            pose[PELVIS][7] += math.ceil(down)
            support_drops.append(math.ceil(down))
            for hip, knee, foot, fw, target in goals:
                origin = R.world_pos(skeleton, pose)[hip]
                v1, v2 = legik.sub(rp[knee], rp[hip]), legik.sub(rp[foot], rp[knee])
                body = R.m3mul(R.world_rots(skeleton, pose)[PELVIS], R.m3t(rw[PELVIS]))
                pole = [sum(body[i][j] * knee_out[hip][j] for j in range(3)) for i in range(3)]
                kn, ac = legik.solve(origin, target, legik.norm(v1), legik.norm(v2), pole)
                worst_reach = max(worst_reach, legik.norm(legik.sub(ac, target)))
                hr, kr = motionsecondary.native_plane_rotations(
                    [rp[b] for b in (hip, knee, foot)], [origin, kn, ac], [rw[hip], rw[knee]])
                set_world(hip, hr)
                set_world(knee, kr)
                set_world(foot, fw)
            for root, chain in ARMS:
                mats = mmd.bone_matrices(model, [[4096] * 3 + [0] * 6] + pose[1:])
                points = [[sum(mats[b][i][j] * v[j] for j in range(3)) + mats[b][i][3] for i in range(3)]
                          for b in chain for v in model.tmd.obj_verts(skeleton[b][0])]
                origin = [mats[root][i][3] for i in range(3)]
                correction = motionsecondary.clearance_rotation(points, origin, [1, 0, 0], [-60, 60], -6)
                set_world(root, R.m3mul(correction, R.world_rots(skeleton, pose)[root]))
            pose[0][6:9] = [round(v) for v in transfer['root'][tick]]
            frames.append(pose)
        assert worst_reach < 1, (slot, worst_reach)
        mmd.close_loop(frames, loop)
        duration = DURATION[slot]
        old_frames = frames
        frames = []
        for tick in range(duration + 1):
            at = tick * (len(old_frames) - 1) / duration
            left = min(int(at), len(old_frames) - 2)
            frames.append(interpolate_pose(old_frames[left], old_frames[left + 1], round((at - left) * 4096)))
        lifts = [0.] * len(frames)
        for i in range(len(frames) - 1):
            for alpha in (0, 1365, 2730, 4096):
                floor = boot_floor(model, skeleton, interpolate_pose(frames[i], frames[i + 1], alpha))
                lifts[i] = max(lifts[i], floor + .5)
                lifts[i + 1] = max(lifts[i + 1], floor + .5)
        lifts[0] = lifts[-1] = max(lifts[0], lifts[-1])
        eased = [max(lifts[j] - 2 * min((i - j) % duration, (j - i) % duration) for j in range(duration))
                 for i in range(duration)]
        eased.append(eased[0])
        for pose, lift in zip(frames, eased):
            pose[PELVIS][7] -= round(max(0, lift))
        frames = [[[round(x) for x in bone] for bone in pose] for pose in frames]
        sounds = [(round(t * duration / (len(native) - 1)), k, c) for t, k, c in events if k == 'sound']
        streams[slot] = len(result.anims.anims)
        result.anims.anims.append(mmd.encode_anim(frames, NB, loop, sounds, tol=1, repeats=False))
        checks.append(dict(slot=slot, ticks=duration, speed=round(abs(frames[-1][0][8] - frames[0][0][8]) / duration, 2),
                           maximum_ik_error=round(worst_reach, 2), maximum_support_drop=max(support_drops),
                           maximum_carrier_lift=round(max(eased), 1)))
    for slot, stream in streams.items():
        result.anims.table[slot] = stream
    for anim in result.anims.anims:
        anim.tail = b''
    result.anims.anims, result.anims.table = motioncyclelayer.share_identical_streams(result.anims.anims,
                                                                                    result.anims.table)
    output = result.build()
    effective = mmd.MMD.parse(output, NB)
    assert effective.tmd.build() == model.tmd.build()
    changed = changed_programs(model, effective)
    assert changed == [2, 3, 4], changed
    return output, dict(source_sha256=hashlib.sha256(data).hexdigest(), donor_sha256=DONOR,
                        output_sha256=hashlib.sha256(output).hexdigest(), changed_slots=changed,
                        native_travel_scale=TRAVEL, checks=checks, storage=motionstorage.require(output, NB))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/199-paildramon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), (ROOT / 'extracted/CHDAT/MMD1/LEOM.MMD').read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
