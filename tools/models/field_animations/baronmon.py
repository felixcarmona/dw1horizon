"""Baronmon's field idle, walk, condition walk and run, authored on its own skeleton.

Offline authoring only: player builds replay the pinned plain delta. Run with --source (the current field model)
and --out, then store the result with tools/models/edit.py put 228.

Baronmon is a robed little walker: a plumed mask, a long green robe over short legs, a cloak and plume behind.
The imported clips were one 94-tick loop for the idle, the walk, the condition walk and the run (only the root's travel
differed). Its two feet moved as one, between 9 and 91 units above the floor and never touching it; the hips went up
and down 108 units, so it bounced through the air and hovered. These clips start from its own bind pose (every
rotation zero: upright, arms down, feet flat) and put it on the ground:

- The pelvis hangs where the leg lets it, never so high that a planted foot is pulled (the leg stays at most 98.5 % of
  its length), and bobs a few units on top: high over the planted foot in the walks, low there in the run.
- Each foot stands where it landed: heel strike, flat, then the heel peels off and the toe leaves last; in the air it
  swings forward on an eased arc and lands on the heel again. Per tick a two-bone solve reaches the ankle. The foot is
  rigid, so the sole's contact point stays still on the floor (the stride length is the root's travel in the stance).
- Pelvis and chest turn against each other, the chest rocks over the planted foot, the head keeps looking ahead and
  nods late, the arms swing against the leg of their side (the elbows bend as the arm comes forward), the robe's skirt,
  the cloak and the plume follow later and wider.
- The robe's skirt is lifted 30 units so its hem stays above the shoes (the legs show under it), the feet swing low
  and flatten early so they pass under the hem, and the skirt itself pitches and rolls with the stride, lifting on the
  side of the leg that swings forward. No shoe vertex ends up inside the skirt in the idle, walk or condition walk.
- The condition walk is the slow, heavy one (slumped, head low, arms hanging); the run is a brisk jog: a short
  flight between steps (the legs cannot reach a longer stance at speed 38), a slight lean, arms bent about 45 degrees
  and held close, swinging a little, the cloak and plume trailing gently.
- The idle stands on both feet, flat and planted: breathing, a slow weight shift from foot to foot with the knees
  taking it up, the head looking around, the arms, cloak and plume answering later.

Every curve is a whole number of cycles over its clip, so the loops are seamless. Root travel per tick is the field
pace (20 walk, 13.3 condition walk, 38 run). The mesh and every other program stay exact.
"""
import argparse
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
import motionstorage  # noqa: E402
import retarget as R  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models.field_animations.upright_gait import (  # noqa: E402
    IDENTITY, apply, lowest, mul, order, positions, rx, ry, rz, side_variation, smooth, to_pose, warp, wave)

SOURCE = 'ecd4774809576ce8b4b41fd7f68ae8376a24281c91d1506464f47c66d2cae870'
SPECIES = 228
NB = 24
PELVIS, CHEST, HEAD = 1, 2, 3
SKIRT = 15
PLUME = (4, 5, 6)
CAPE = (22, 23)
# shoulder pad, upper arm, forearm, hand, side
ARMS = [(7, 8, 9, 10, 1), (11, 12, 13, 14, -1)]
# thigh, shin, foot (ankle at its origin), side
LEGS = [(16, 17, 18, 1), (19, 20, 21, -1)]
FOOT_BONES = (18, 21)
# the ankle's height over the sole; the heel this far behind the ankle and the toe this far ahead of it
ANKLE, HEEL, TOE = 23., 32., 63.
REACH = 0.985
SLOTS = (0, 2, 3, 4)
IDLE_TICKS = 96

# ticks and root travel a tick; duty: of the cycle each foot stands; flat: the stance's share where the sole is flat
# (from, to); heel/toe: degrees of heel strike and toe-off; lift: the swing's clearance; bias: the ankle's z at the
# middle of the flat part (+ is behind the hip). Amplitudes: degrees and units.
GAITS = {
    2: dict(ticks=14, speed=20., duty=0.60, flat=(0.14, 0.62), heel=12, toe=24, lift=10, bias=0, hip=124, bob=4,
            settle=3, sway=4, yaw=5, roll=2.5, rock=2, counter=0.55, lean=3, chest_rock=2, head=0, nod=2, turn=2,
            arm=18, arm_back=0.7, arm_base=3, elbow=14, elbow_swing=10, arm_out=5, lag=0.07, skirt=5, skirt_roll=4,
            cape=6, cape_base=5, plume=7, plume_base=4),
    3: dict(ticks=18, speed=13.3, duty=0.66, flat=(0.14, 0.58), heel=10, toe=20, lift=8, bias=0, hip=118, bob=3,
            settle=4, sway=5, yaw=4, roll=3, rock=1.5, counter=0.45, lean=10, chest_rock=1.5, head=14, nod=2, turn=2,
            arm=8, arm_back=0.8, arm_base=-3, elbow=14, elbow_swing=5, arm_out=4, lag=0.1, skirt=3, skirt_roll=3,
            cape=4, cape_base=2, plume=5, plume_base=9),
    4: dict(ticks=12, speed=38., duty=0.36, flat=(0.2, 0.55), heel=6, toe=30, lift=24, bias=-4, hip=124, bob=8,
            settle=0, sway=3, yaw=5, roll=2.5, rock=2, counter=0.6, lean=7, chest_rock=2, head=5, nod=2, turn=2,
            arm=18, arm_back=1.0, arm_base=-3, elbow=44, elbow_swing=22, arm_out=7, lag=0.06, skirt=5, skirt_roll=5,
            cape=5, cape_base=12, plume=6, plume_base=10),
}
# the skirt is lifted so that its hem stays above the shoes (the legs show under it)
SKIRT_RISE = 30


def rot_to(a, b):
    return R.swing(a, b)


def roll_ankle(pivot_z, drop, ahead, pitch):
    """Ankle height and z (+ behind) when the foot, tipped by `pitch` degrees (+ toe down), touches the floor at
    `pivot_z` with the point that is `drop` under and `ahead` in front of the ankle (ahead is - for the toe)."""
    c, s = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    return drop * c - ahead * s, pivot_z - (drop * s + ahead * c)


def stance(g, t):
    """The ankle's (z in the body's frame, height, pitch) at cycle phase t in [0, duty]: heel strike, flat, toe-off."""
    d, (s1, s2) = g['duty'], g['flat']
    travel = g['speed'] * g['ticks']
    s = t / d
    zf = g['bias'] - travel * d * (s1 + s2) / 2          # the ankle's z in the world while the foot is flat
    heel = zf + HEEL
    toe = heel - (HEEL + TOE)
    if s < s1:
        pitch = -g['heel'] * (1 - smooth(s / s1))
        h, z = roll_ankle(heel, ANKLE, HEEL, pitch)
    elif s < s2:
        pitch, h, z = 0., ANKLE, zf
    else:
        q = (s - s2) / (1 - s2)
        pitch = g['toe'] * smooth(q)
        h, z = roll_ankle(toe, ANKLE, -TOE, pitch)
    return z + travel * t, h, pitch


def foot_at(g, phase, side_lag=0.):
    """(z, height, pitch) of one foot at cycle phase t (it lands at 0): stance, then an eased swing to the next landing."""
    t = (phase - side_lag) % 1.
    d = g['duty']
    if t < d:
        return stance(g, t)
    u = (t - d) / (1 - d)
    e, l = stance(g, d), stance(g, 0.)
    z = e[0] + (l[0] - e[0]) * smooth(warp(u, 0.25))
    h = e[1] + (l[1] - e[1]) * smooth(min(1., u * 2.5)) + g['lift'] * math.sin(math.pi * min(1., u ** 0.85)) ** 1.2
    pitch = e[2] + (l[2] - e[2]) * smooth(min(1., u * 2.2))
    return z, h, pitch


def idle_pose(t, bind, offsets, skeleton):
    """Cycle phase t in 0..1 over IDLE_TICKS: standing, breathing, weight shift, looking around."""
    tau = 2 * math.pi * t
    shift = math.sin(tau)                        # + over the right foot
    breath = math.sin(tau * 4)                   # a breath every 24 ticks
    look = math.sin(tau) + 0.35 * math.sin(tau * 2 + 0.6)
    pw = mul(rz(-1.6 * shift), ry(1.2 * math.sin(tau - 0.8)), rx(1 + 0.4 * breath))
    cw = mul(ry(-0.8 * math.sin(tau - 0.8)), rz(1.2 * shift), rx(1.5 + 0.9 * breath))
    hw = mul(ry(12 * look), rz(2.5 * math.sin(tau - 0.3)), rx(-1 + 1.6 * math.sin(tau * 2 - 0.4) - 0.6 * breath))
    worlds = {0: IDENTITY, PELVIS: pw, CHEST: cw, HEAD: hw, SKIRT: mul(pw, rx(1.2 * math.sin(tau * 4 - 0.8)))}
    for plate, arm, fore, hand, side in ARMS:
        swing = 3 * math.sin(tau * 2 + (0.5 if side > 0 else 2.4)) + 1.2 * breath
        worlds[plate] = mul(cw, rz(-side * 0.8 * breath))
        worlds[arm] = mul(rx(-(3 + swing)), rz(-side * (4 + 1.2 * breath)))
        worlds[fore] = mul(worlds[arm], rx(-(8 + 2 * swing)))
        worlds[hand] = mul(worlds[fore], rx(-3), rz(side * 3))
    plume_chain(worlds, hw, t, 2, 3, 6, 4)
    cape_chain(worlds, cw, t, 1, 2, 4, 3)
    sway = 6 * shift
    feet = []
    for thigh, shin, foot, side in LEGS:
        feet.append((side, bind[foot][0] + 2 * side, ANKLE, bind[foot][2] + 0., 0.))
    return worlds, [sway, None, 0.], feet, 124 - 2.5 * abs(shift) - 0.6 * breath


def plume_chain(worlds, parent, t, cycles, delay, amount, base):
    w = parent
    for i, b in enumerate(PLUME):
        ph = 2 * math.pi * (cycles * t - (0.07 + 0.06 * i))
        w = mul(w, rx(base / 3 + amount * (1 + 0.3 * i) / 3 * math.sin(ph)), ry(amount * (1 + 0.4 * i) / 3 * math.sin(ph - 1.2)))
        worlds[b] = w


def cape_chain(worlds, parent, t, cycles, delay, amount, base):
    w = parent
    for i, b in enumerate(CAPE):
        ph = 2 * math.pi * (cycles * t - (0.08 + 0.07 * i))
        w = mul(w, rx(base / 2 + amount * (1 + 0.3 * i) / 2 * math.sin(ph)), rz(0.35 * amount * math.sin(ph - 0.9)))
        worlds[b] = w


def gait_pose(g, slot, t, bind, offsets, skeleton):
    """World rotations, carrier position, feet and the pelvis' design height at cycle phase t."""
    step = 1 + 0.05 * math.cos(2 * math.pi * t)
    yaw = g['yaw'] * wave(t, 0., 0.2, 0.12)
    late = g['yaw'] * wave(t, 0.07, 0.2, 0.12)
    w2 = wave((2 * t) % 1., g['duty'] % 1., 0.25) * step
    bob = g['bob'] * w2 if slot == 4 else -g['bob'] * w2
    bob += g['settle'] * max(0., math.cos(4 * math.pi * (t - 0.06))) ** 4
    rock = g['rock'] * wave((2 * t) % 1., 0.12, 0.3) * step
    sway = g['sway'] * wave(t, 0.28, 0.2)
    roll = -g['roll'] * wave(t, 0.3, 0.35, 0.2)
    pw = mul(ry(yaw), rz(roll), rx(g['lean'] * 0.5 + rock))
    breath = 0.7 * wave(t, 0.4, 0.4)
    turn = ry(-g['counter'] * late)
    cw = mul(turn, rz(-0.5 * roll), rx(g['lean'] + g['chest_rock'] * wave((2 * t) % 1., 0.22, 0.3) * step + breath))
    hw = mul(ry(0.25 * g['yaw'] * wave(t, 0.15, 0.2)),
             rx(g['head'] - 0.8 * g['lean'] + g['nod'] * wave((2 * t) % 1., 0.3, 0.3)))
    # the hem lifts on the side of the leg that swings forward and trails behind the stride, each beat a little late
    worlds = {0: IDENTITY, PELVIS: pw, CHEST: cw, HEAD: hw,
              SKIRT: mul(pw, rz(-g['skirt_roll'] * wave(t, 0.8, 0.2)),
                         rx(g['skirt'] * wave((2 * t) % 1., 0.3, 0.3) - 0.3 * g['skirt']))}
    for plate, arm, fore, hand, side in ARMS:
        swing = -wave(t, g['lag'] + (0.5 + 0.007 if side < 0 else 0.), 0.3, 0.1)
        amount = g['arm'] * side_variation(side, 0.01) * (swing if swing > 0 else g['arm_back'] * swing)
        worlds[plate] = mul(cw, rx(1.5 * wave((2 * t) % 1., 0.35, 0.3)))
        worlds[arm] = mul(turn, rx(-(g['arm_base'] + amount)), rz(-side * g['arm_out']))
        # the elbow bends more as the arm comes forward
        bend = g['elbow'] + g['elbow_swing'] * (amount / max(1., g['arm']))
        worlds[fore] = mul(worlds[arm], rx(-max(2., bend)))
        worlds[hand] = mul(worlds[fore], rx(-4), rz(side * 3))
    plume_chain(worlds, hw, t, 2, 3, g['plume'], g['plume_base'])
    cape_chain(worlds, cw, t, 2, 3, g['cape'], g['cape_base'])
    feet = []
    for thigh, shin, foot, side in LEGS:
        z, h, pitch = foot_at(g, t, 0. if side > 0 else 0.5)
        feet.append((side, bind[foot][0] + 2 * side, h, z + bind[foot][2], pitch))
    return worlds, [sway, None, 0.], feet, g['hip'] + bob


def fill_worlds(worlds, skeleton):
    for b in order(skeleton):
        if b not in worlds:
            worlds[b] = worlds[skeleton[b][1]] if skeleton[b][1] > 0 else IDENTITY


def solve_frame(pose_fn, args, bind, offsets, skeleton, reference):
    worlds, carrier, feet, hip_design = pose_fn(*args)
    L1 = legik.norm(offsets[17])
    L2 = legik.norm(offsets[18])
    # carrier height is unknown yet: place it at the design, read the hip's horizontal distance to each ankle
    carrier[1] = -(hip_design + offsets[16][1]) if carrier[1] is None else carrier[1]
    pos = positions(skeleton, offsets, worlds, PELVIS, [carrier[0], carrier[1], carrier[2] + bind[PELVIS][2]])
    cap = 1e9
    for (side, x, h, z, pitch), (thigh, shin, foot, s) in zip(feet, LEGS):
        hip = pos[thigh]
        dh = math.hypot(x - hip[0], z - hip[2])
        room = (REACH * (L1 + L2)) ** 2 - dh * dh
        cap = min(cap, h + math.sqrt(max(room, 0.)))
    hip_h = min(hip_design, cap)
    carrier[1] = -(hip_h + offsets[16][1])
    pos = positions(skeleton, offsets, worlds, PELVIS, [carrier[0], carrier[1], carrier[2] + bind[PELVIS][2]])
    reach = 0.
    for (side, x, h, z, pitch), (thigh, shin, foot, s) in zip(feet, LEGS):
        hip = pos[thigh]
        target = [x, -h, z]
        pole = apply(worlds[PELVIS], [0.15 * side, 0.05, -1])
        knee, ankle = legik.solve(hip, target, L1, L2, pole)
        reach = max(reach, legik.norm(legik.sub(target, hip)) / (L1 + L2))
        worlds[thigh] = rot_to(offsets[shin], legik.sub(knee, hip))
        worlds[shin] = rot_to(offsets[foot], legik.sub(ankle, knee))
        worlds[foot] = rx(pitch)
    fill_worlds(worlds, skeleton)
    return worlds, carrier, reach, hip_h


def encode_clip(slot, g, bind, offsets, skeleton, reference, model):
    n = IDLE_TICKS if slot == 0 else g['ticks']
    speed = 0. if slot == 0 else g['speed']
    history, frames, reach = {}, [], 0.
    holds = []
    for tick in range(n + 1):
        t = (tick % n) / n
        if slot == 0:
            args = (t, bind, offsets, skeleton)
            fn = idle_pose
        else:
            args = (g, slot, t, bind, offsets, skeleton)
            fn = gait_pose
        worlds, carrier, r, hip_h = solve_frame(fn, args, bind, offsets, skeleton, reference)
        reach = max(reach, r)
        holds.append(hip_h)
        frame = to_pose(skeleton, reference, worlds, PELVIS, [carrier[0], carrier[1], carrier[2] + bind[PELVIS][2]],
                        speed * tick, history)
        frame[SKIRT][7] -= SKIRT_RISE
        frames.append(frame)
    return frames, reach, holds


TOL_LEGS = 2
TOL = 6


def bone_tol():
    # the legs and the carrier keep a fine fit (the planted feet depend on it); the smooth upper body takes the coarse one
    tol = {b: TOL_LEGS for b in (PELVIS,) + tuple(x for leg in LEGS for x in leg[:3])}
    tol[None] = TOL
    return tol


def build(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('requires the reviewed Baronmon field model')
    mmd.exe().add_type(SPECIES, skeleton)
    model = mmd.MMD.parse(data, NB)
    model.type = SPECIES
    reference = animsheet.slot_frames(model, NB, 2)[0][0]
    offsets = {b: list(reference[b][6:9]) for b in range(1, NB)}
    bind = positions(skeleton, offsets, {b: IDENTITY for b in range(NB)}, PELVIS, [0., -225., -3.])
    result = mmd.MMD.parse(data, NB)
    result.type = SPECIES
    checks = {}
    for slot in SLOTS:
        g = GAITS.get(slot, {})
        frames, reach, holds = encode_clip(slot, g, bind, offsets, skeleton, reference, model)
        frames = [[[round(x) for x in bone] for bone in pose] for pose in frames]
        stream = mmd.encode_anim(frames, NB, 0, [], tol=bone_tol(), repeats=False)
        index = result.anims.table[slot]
        if result.anims.table.count(index) == 1:
            result.anims.anims[index] = stream
        else:
            # shared with slots that must stay as they are (slot 1 and 18 keep the old idle)
            result.anims.table[slot] = len(result.anims.anims)
            result.anims.anims.append(stream)
        checks[slot] = dict(ticks=len(frames) - 1, reach=round(reach, 3),
                            hip_height=[round(min(holds)), round(max(holds))])
    output = result.build()
    effective = mmd.MMD.parse(output, NB)
    effective.type = SPECIES
    assert effective.tmd.build() == model.tmd.build()
    changed = changed_programs(model, effective)
    assert set(changed) <= set(SLOTS), changed
    return output, dict(source_sha256=hashlib.sha256(data).hexdigest(), output_sha256=hashlib.sha256(output).hexdigest(),
                        changed_slots=changed, checks=checks, storage=motionstorage.audit(output, NB))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/228-baronmon.json').read_text())['model']['skeleton']
    data = a.source.read_bytes()
    output, proof = build(data, skeleton)
    a.out.write_bytes(output)
    text = json.dumps(proof, indent=2) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
