"""Angewomon's field walk, condition walk and run, taken from native Angemon's.

Offline authoring only: player builds replay the pinned plain delta. Run with --source and --out, then store the
result with tools/models/edit.py put 190.

The imported walk and run slid the feet over the ground without the legs carrying them, dragged the sash ends
through the floor and swung the arms stiffly away from the body. These clips take Angemon's own
walk, condition walk and run (the same body plan: an angel on two legs with wings on the back) the way
valkyrimon.py does for Valkyrimon:

- The pelvis, torso, chest, head and both legs turn in the world as Angemon's homologous bones turn from his idle
  (his run leans into a crouched sprint; she takes a third of that lean). The wings, hair and sash keep their
  places on the body and follow it.
- Angemon's feet are the targets: each foot moves from her own stance as his moves from his, scaled by her longer
  legs (the run's stride a little shorter so her legs keep it), and lifts as high over his stance as his ankle
  does. A two-bone solve on her own thigh and shin reaches it in the plane the native leg bends in; the body comes
  down only as far as a planted foot needs.
- Angemon carries his staff in one hand, so her arms are her own: each upper arm swings against the opposite thigh
  and the elbow bends as it comes forward, more in the run.
- The sash ends, which hang to the floor, swing back on their roots, and the lowest wing feathers rise sideways,
  only as far as needed to stay off the ground.
- The walk is eased over 22 ticks (Angemon's 16), the condition walk over 30 and the run over 15; a carrier lift
  spread over neighbouring ticks keeps the boots out of the floor at every 60 fps third.

The idle and every other program, and the mesh, stay exact.
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

SOURCE = '6b36232e8f400a4fecbfa927829519990e81365a1639073b1d729365692871d5'
DONOR = '4bbdf9a2763dab219bc599f0d9cfa44d93263fc5e00930d405ad055f68c22ed9'
SPECIES = 190
NB = 31
PELVIS = 23
TRAVEL = 1.15           # her hip-to-ankle leg is about 1.15 times Angemon's
# (hip, knee, foot) of hers, then Angemon's
LEGS = [(24, 25, 26, 19, 20, 21), (27, 28, 29, 22, 23, 24)]
FEET = (26, 29)
# her bone: Angemon's bone
MAP = {23: 18, 1: 2, 2: 2, 3: 3,
       24: 19, 25: 20, 26: 21, 27: 22, 28: 23, 29: 24}
DURATION = {2: 22, 3: 30, 4: 15}
# her stride against Angemon's, scaled by her legs: the run's long sprint stride is shortened so her legs keep it
STRIDE = {2: 1.0, 3: 1.0, 4: 0.8}
# Angemon carries his staff in one hand, so her arms are not his: each upper arm swings against the opposite
# thigh (degrees of arm per degree of thigh) and the elbow bends as it comes forward, plus a constant bend
ARMS = {2: (0.55, 6), 3: (0.45, 6), 4: (0.6, 25)}
ARM = {1: (5, 6, 22), -1: (8, 9, 19)}       # side: (upper arm, forearm, Angemon's opposite thigh)
THIGH_END = {19: 20, 22: 23}
# the sash ends hang to the floor: each swings back on its root as far as it must to stay off the ground
SASH = ((19, 20), (21, 22))
# the lowest feathers of each wing rise sideways when the body's lean would put them in the floor
FEATHERS = (13, 14, 17, 18)
DEAD = 5   # how far an ankle moves in Angemon's stance as the foot rolls; only height above it is a lift
# how much of Angemon's body lean she takes: his run is a crouched sprint, hers stays upright under the wings
LEAN = {2: 1.0, 3: 1.0, 4: 0.35}
BODY = (23, 1, 2, 3)


def boot_floor(model, skeleton, pose):
    p = copy.deepcopy(pose)
    p[0] = [4096] * 3 + [0] * 6
    mats = mmd.bone_matrices(model, p)
    return max(sum(mats[b][1][j] * v[j] for j in range(3)) + mats[b][1][3]
               for b in FEET for v in model.tmd.obj_verts(skeleton[b][0]))


def build(data, donor_data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('requires the reviewed Angewomon import')
    if hashlib.sha256(donor_data).hexdigest() != DONOR:
        raise ValueError('requires native Angemon from the registered disc')
    mmd.exe().add_type(SPECIES, skeleton)
    model = mmd.MMD.parse(data, NB)
    model.type = SPECIES
    donor = mmd.MMD.parse(donor_data, 26)
    donor.type = 20
    ds = mmd.exe().skeleton[20]
    rest, dr = R.rest_pose(model, NB), R.rest_pose(donor, 26)
    chains = [(h, k, dh, dk) for h, k, f, dh, dk, df in LEGS]
    chains += [(k, f, dk, df) for h, k, f, dh, dk, df in LEGS]
    rest = R.align_reference(skeleton, rest, ds, dr, chains, keep_world=list(FEET))
    rest[PELVIS][7] -= round(boot_floor(model, skeleton, rest))
    rp, rw = R.world_pos(skeleton, rest), R.world_rots(skeleton, rest)
    dw0 = R.world_rots(ds, dr)
    dp0 = R.world_pos(ds, dr)
    result = copy.deepcopy(model)
    checks = []
    streams = {}
    for slot in (2, 3, 4):
        native, loop, events = animsheet.slot_frames(donor, 26, slot)
        transfer = R.transfer(donor, 20, slot, SPECIES, rest, {t: (s, LEAN[slot] if t in BODY else 1.) for t, s in MAP.items()},
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
                fw = R.m3mul(R.m3mul(dw[df], R.m3t(dw0[df])), rw[foot])
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
                kn, ac = legik.solve(origin, target, legik.norm(v1), legik.norm(v2), [0, 0, -1])
                worst_reach = max(worst_reach, legik.norm(legik.sub(ac, target)))
                hr, kr = motionsecondary.native_plane_rotations(
                    [rp[b] for b in (hip, knee, foot)], [origin, kn, ac], [rw[hip], rw[knee]])
                set_world(hip, hr)
                set_world(knee, kr)
                set_world(foot, fw)
            torso = R.m3mul(R.world_rots(skeleton, pose)[1], R.m3t(rw[1]))
            gain, bend = ARMS[slot]
            for side, (upper, fore, thigh) in ARM.items():
                def pitch(pos, b=thigh):
                    d = [pos[THIGH_END[b]][i] - pos[b][i] for i in range(3)]
                    return math.degrees(math.atan2(-d[2], d[1]))
                swing = gain * (pitch(dpos) - pitch(dp0))          # forward positive
                curl = bend + 0.5 * max(0.0, swing)
                set_world(upper, R.m3mul(R.m3mul(torso, R.from_axis_angle([1, 0, 0], math.radians(-swing))), rw[upper]))
                set_world(fore, R.m3mul(R.m3mul(torso, R.from_axis_angle([1, 0, 0], math.radians(-swing - curl))), rw[fore]))
            for root, end in SASH:
                mats = mmd.bone_matrices(model, [[4096] * 3 + [0] * 6] + pose[1:])
                points = [[sum(mats[b][i][j] * v[j] for j in range(3)) + mats[b][i][3] for i in range(3)]
                          for b in (root, end) for v in model.tmd.obj_verts(skeleton[b][0])]
                origin = [mats[root][i][3] for i in range(3)]
                correction = motionsecondary.clearance_rotation(points, origin, [1, 0, 0], [0, 80], -4)
                set_world(root, R.m3mul(correction, R.world_rots(skeleton, pose)[root]))
            for bone in FEATHERS:
                mats = mmd.bone_matrices(model, [[4096] * 3 + [0] * 6] + pose[1:])
                points = [[sum(mats[bone][i][j] * v[j] for j in range(3)) + mats[bone][i][3] for i in range(3)]
                          for v in model.tmd.obj_verts(skeleton[bone][0])]
                origin = [mats[bone][i][3] for i in range(3)]
                correction = motionsecondary.clearance_rotation(points, origin, [0, 0, 1], [-45, 45], -4)
                set_world(bone, R.m3mul(correction, R.world_rots(skeleton, pose)[bone]))
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
    skeleton = json.loads((ROOT / 'content/species/190-angewomon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), (ROOT / 'extracted/CHDAT/MMD0/ANGE.MMD').read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
