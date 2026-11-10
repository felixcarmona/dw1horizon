"""Seraphimon's field idle, walk, condition walk and run, taken from native Angemon's.

Offline authoring only: player builds replay the pinned plain delta. Run with --source and --out, then store the
result with tools/models/edit.py put 207.

The imported idle beat all ten wing feathers through 60 degrees every 17 ticks, and the walk and run slid the
feet over the ground (the run striding far past the body). The new clips:

- Walk, condition walk and run take native Angemon's footfalls (same two-legged angel body plan): the pelvis and head
  turn as his turn from his idle (the run with part of his lean), each foot moves from its own stance as his moves
  from his, scaled by Seraphimon's longer legs (the run's stride shortened), and a two-bone solve on thigh and shin
  puts the ankle there. The ankle stays planted for the whole stance, so the feet do not slide.
- The arms swing against the opposite thigh from the shoulder, more bent in the run.
- The wings keep their places on the body and flutter a few degrees, each feather a little behind the one before,
  swept back in the run; the tabard hangs under the body's lean, swings a little late and is kept off the floor.
- The idle is a calm 48-tick breath: wings, head and arms move a few degrees, the feet stay where they are.

The sounds, the mesh, the battle idle and every other program stay exact.
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

SOURCE = '0224b26e5970794ebdb5511826d5622fdb79c526c5ad5cc441ad56f1aaddb76b'
DONOR = '4bbdf9a2763dab219bc599f0d9cfa44d93263fc5e00930d405ad055f68c22ed9'
SPECIES = 207
NB = 31
PELVIS = 1
TRAVEL = 2.2            # hip-to-ankle leg is about 2.2 times Angemon's
# (hip, knee, foot) of his, then Angemon's
LEGS = [(25, 26, 27, 19, 20, 21), (28, 29, 30, 22, 23, 24)]
FEET = (27, 30)
MAP = {1: 2, 2: 3}
BODY = (1, 2)
DURATION = {2: 17, 3: 24, 4: 14}
STRIDE = {2: 0.65, 3: 0.6, 4: 0.55}
LEAN = {2: 0.6, 3: 0.6, 4: 0.45}
# arm: shoulder bone, forearm bone, Angemon's opposite thigh; and the thigh's end for its pitch
ARM = {1: (3, 5, 22), -1: (7, 9, 19)}
THIGH_END = {19: 20, 22: 23}
ARMS = {2: (0.4, 4), 3: (0.35, 4), 4: (0.5, 18)}   # degrees of arm per degree of thigh, constant bend
WINGS_R, WINGS_L = (11, 12, 13, 14, 15), (16, 17, 18, 19, 20)
WING_SWEEP = {0: 0, 2: -25, 3: -15, 4: -90}         # units of 360/4096 degrees, negative opens backwards
WING_BEAT = {0: 34, 2: 22, 3: 18, 4: 55}
WING_LAG = {0: 2.2, 2: 1.5, 3: 1.5, 4: 1.0}         # ticks each feather behind the one before
CLOTH = (22, 23, 24)
DEAD = 5
HIP_BOB = 1.0
# the pelvis rides this much higher than the native proportions put it, so the planted leg is straighter
HIP_RISE = {2: 24, 3: 20, 4: 30}
# how high a foot lifts over its stance, in Angemon's lifts: his full lift scaled by the legs would fold the shin back
LIFT = {2: 1.1, 3: 4.0, 4: 1.5}
IDLE_TICKS = 48


def boot_floor(model, skeleton, pose):
    p = copy.deepcopy(pose)
    p[0] = [4096] * 3 + [0] * 6
    mats = mmd.bone_matrices(model, p)
    return max(sum(mats[b][1][j] * v[j] for j in range(3)) + mats[b][1][3]
               for b in FEET for v in model.tmd.obj_verts(skeleton[b][0]))


def build(data, donor_data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('requires the pinned Seraphimon import')
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
    sound = None
    for a in model.anims.anims:
        for i in a.instrs:
            if i['op'] == 'sound' and sound is None:
                sound = i
    checks = []
    streams = {}

    def set_world(pose, history, bone, world):
        parent = R.world_rots(skeleton, pose)[skeleton[bone][1]]
        angles = mmd.matrix_euler(R.m3mul(R.m3t(parent), world), history.get(bone))
        history[bone] = angles
        pose[bone][3:6] = [round(v) for v in angles]

    def decorate(pose, history, slot, phase, torso_pitch):
        """Wings flutter behind the body and the tabard hangs under it; phase in turns."""
        beat = WING_BEAT[slot]
        for group, sign in ((WINGS_R, 1), (WINGS_L, -1)):
            for i, b in enumerate(group):
                lag = WING_LAG[slot] * i / (len(group) - 1) * 0.15 if slot else WING_LAG[slot] * i * 0.02
                d = WING_SWEEP[slot] + beat * math.sin(2 * math.pi * (phase - lag))
                pose[b][4] = rest[b][4] + round(sign * d)
        mats0 = None
        for k, bone in enumerate(CLOTH):
            swing = (3 + 3 * k) * math.sin(2 * math.pi * (phase - 0.12 * (k + 1))) * (0.3 if slot == 0 else 1.0)
            set_world(pose, history, bone, R.m3mul(R.from_axis_angle([1, 0, 0], math.radians(swing)), rw[bone]))
        mats = mmd.bone_matrices(model, [[4096] * 3 + [0] * 6] + pose[1:])
        points = [[sum(mats[b][i][j] * v[j] for j in range(3)) + mats[b][i][3] for i in range(3)]
                  for b in CLOTH for v in model.tmd.obj_verts(skeleton[b][0])]
        origin = [mats[CLOTH[0]][i][3] for i in range(3)]
        correction = motionsecondary.clearance_rotation(points, origin, [1, 0, 0], [-25, 25], -4)
        set_world(pose, history, CLOTH[0], R.m3mul(correction, R.world_rots(skeleton, pose)[CLOTH[0]]))

    # ---------------------------------------------------------------- the idle
    frames, history = [], {}
    for tick in range(IDLE_TICKS + 1):
        phase = (tick % IDLE_TICKS) / IDLE_TICKS
        pose = copy.deepcopy(rest)
        pose[0][6:9] = [0, 0, 0]
        s = math.sin(2 * math.pi * phase)
        s2 = math.sin(2 * math.pi * (phase - 0.1))
        torso = R.world_rots(skeleton, pose)[1]
        set_world(pose, history, 2, R.m3mul(R.from_axis_angle([1, 0, 0], math.radians(1.2 * s2)), rw[2]))
        for side, (upper, fore, thigh) in ARM.items():
            set_world(pose, history, upper, R.m3mul(R.from_axis_angle([1, 0, 0], math.radians(1.0 * s2)), rw[upper]))
            set_world(pose, history, fore, R.m3mul(R.from_axis_angle([1, 0, 0], math.radians(-1.5 * s2)), rw[fore]))
        decorate(pose, history, 0, phase, 0)
        frames.append([[round(x) for x in bone] for bone in pose])
    frames[-1] = copy.deepcopy(frames[0])
    streams[0] = len(result.anims.anims)
    result.anims.anims.append(mmd.encode_anim(frames, NB, 0, [], tol=0, repeats=False))
    checks.append(dict(slot=0, ticks=IDLE_TICKS))

    # ---------------------------------------------------------------- walk, condition walk, run
    for slot in (2, 3, 4):
        native, loop, events = animsheet.slot_frames(donor, 26, slot)
        transfer = R.transfer(donor, 20, slot, SPECIES, rest, {t: (s, LEAN[slot]) for t, s in MAP.items()},
                              (PELVIS, 1, HIP_BOB), TRAVEL * STRIDE[slot])
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
            goals = []
            for hip, knee, foot, dh, dk, df in LEGS:
                fw = R.m3mul(R.m3mul(dw[df], R.m3t(dw0[df])), rw[foot])
                sole = max(sum(fw[1][j] * v[j] for j in range(3)) for v in model.tmd.obj_verts(skeleton[foot][0]))
                target = [rp[foot][i] + TRAVEL * STRIDE[slot] * (dpos[df][i] - dp0[df][i]) for i in range(3)]
                target[1] = -sole - LIFT[slot] * max(0, ground[df] - dpos[df][1] - DEAD)
                goals.append((hip, knee, foot, fw, target))
            pose[PELVIS][7] -= HIP_RISE[slot]
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
                set_world(pose, history, hip, hr)
                set_world(pose, history, knee, kr)
                set_world(pose, history, foot, fw)
            torso = R.m3mul(R.world_rots(skeleton, pose)[1], R.m3t(rw[1]))
            gain, bend = ARMS[slot]
            for side, (upper, fore, thigh) in ARM.items():
                def pitch(pos, b=thigh):
                    d = [pos[THIGH_END[b]][i] - pos[b][i] for i in range(3)]
                    return math.degrees(math.atan2(-d[2], d[1]))
                swing = gain * (pitch(dpos) - pitch(dp0))
                curl = bend + 0.5 * max(0.0, swing)
                set_world(pose, history, upper, R.m3mul(R.m3mul(torso, R.from_axis_angle([1, 0, 0], math.radians(-swing))), rw[upper]))
                set_world(pose, history, fore, R.m3mul(R.m3mul(torso, R.from_axis_angle([1, 0, 0], math.radians(-swing - curl))), rw[fore]))
            decorate(pose, history, slot, tick / (len(native) - 1), 0)
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
        sounds = [(round(t * duration / (len(native) - 1)), k, dict(sound)) for t, k, c in events if k == 'sound']
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
    assert changed == [0, 2, 3, 4], changed
    return output, dict(source_sha256=hashlib.sha256(data).hexdigest(), donor_sha256=DONOR,
                        output_sha256=hashlib.sha256(output).hexdigest(), changed_slots=changed,
                        native_travel_scale=TRAVEL, checks=checks, storage=motionstorage.require(output, NB))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/207-seraphimon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), (ROOT / 'extracted/CHDAT/MMD0/ANGE.MMD').read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
