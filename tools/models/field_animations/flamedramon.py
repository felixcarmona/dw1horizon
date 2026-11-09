"""Flamedramon's field walk, condition walk and run, authored on its own skeleton.

Offline authoring only: player builds replay the pinned plain delta. Run with --source (the reviewed field model
the gaits.py profile made) and --out, then store the result with tools/models/edit.py put 195.

The procedural stride of gaits.py swung and dropped the hips, twisted the chest and held the arms out wide; clips
borrowed from native Leomon kept his hunch and his footfalls on a body that is built differently. These clips start
from Flamedramon's own bind pose instead (every rotation zero): upright, arms hanging at the sides, feet flat under
the hips with the hocks a little bent. On top of it, per tick:

- Each foot's ball stays on its own track under the hip (never across the middle). Down, the ball holds still on
  the floor and the heel peels up at the end of the stance; in the air it travels to the next footprint on an eased
  arc, heel first, and lands flat. A two-bone solve on the thigh and shin reaches the hock, the knee forward and a
  little out, as in the bind pose.
- The pelvis turns a little with the leg that swings forward, drops a little on the side of the lifted foot and
  shifts over the planted one; the chest turns the other way, so the shoulders counter the hips; the head keeps
  looking ahead, level; the arms swing opposite to the legs, a little later than them, further forward than back.
  The tail follows the hips' turn late, joint after joint.
- Nothing moves on a plain sine or in lockstep (a native's joint curves rise, hold and fall unevenly): every curve
  is a warped wave (upright_gait.wave) with its own ease, and the body moves in overlap: the hips lead, the chest
  rocks and counters them a little later, the head later still, the arms swing later than the legs (forward
  quickly, back slowly), the shoulder plates bounce after the chest and the tail whips each joint later and wider.
  The pelvis tips forward at each footfall and rolls over the planted foot; the chest breathes. The two sides
  differ a little (how long each foot stays down, how high it lifts, the left foot slightly late, the arms' swing),
  as no body steps exactly like its mirror. The amplitudes of the pelvis, chest and arms are those of native
  Agumon's and Leomon's walk and run.
- The walk rises over the planted foot and settles at each footfall, with double support; the condition walk is
  slower and heavier, slumped, the head low and the arms hanging; the run leans in, drives the knees, kicks the
  heels up high behind, swings the arms hard and has both feet in the air between steps.

Cycle lengths and root speeds are the reviewed field model's (22, 15 and 52 a tick), so the feet hold still on the
floor. A carrier lift spread over neighbouring ticks keeps every claw out of the floor at the 60 fps thirds. The
idle and every other program, and the mesh, stay exact.
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
import motioncyclelayer  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models.field_animations.upright_gait import (  # noqa: E402
    IDENTITY, apply, leg, lift_off_floor, mul, positions, rx, ry, rz, side_variation, smooth, to_pose, warp, wave)

SOURCE = '4a21fc3df853ae7617e6bffe66f84d5bdbbd56e7c8defd0918d53d56e778245f'
SPECIES = 195
NB = 20
PELVIS, CHEST, HEAD = 8, 1, 2
TAIL = (9, 10, 11)
# thigh, shin, metatarsus (hock), foot (ball and claws), the side's sign in x
LEGS = [(12, 13, 14, 15, 1), (16, 17, 18, 19, -1)]
# shoulder plate, arm, side
ARMS = [(4, 5, 1), (6, 7, -1)]
FLOOR = (13, 14, 15, 17, 18, 19)
# the bind pose's pelvis height: the soles flat on the floor
STAND = -189
# how far the metatarsus leans toward the hip: the hock passes over the toes as the body goes by
META = 0.5

# the left side's steps differ a little from the right's (amplitude) and land a little late (of the cycle)
ASYM = 0.06
LEFT_LAG = 0.015

GAITS = {
    # ticks and travel of one cycle (two steps) are the reviewed model's; duty: of the cycle each foot is down.
    # Amplitudes (degrees, units) are set against native Agumon's and Leomon's walk and run curves.
    2: dict(ticks=14, travel=308, duty=0.58, lift=30, push=22, toe=10, bob=8, settle=4, sway=4, yaw=6, roll=4, rock=4,
            counter=0.55, lean=3, chest_rock=3, hip_lean=2, head=0, nod=3, arm=28, arm_back=0.65, arm_base=2,
            arm_out=4, lag=0.07, tail=7, tail_droop=8, crouch=0),
    3: dict(ticks=18, travel=270, duty=0.64, lift=20, push=16, toe=6, bob=7, settle=6, sway=6, yaw=4, roll=5, rock=3,
            counter=0.45, lean=11, chest_rock=2, hip_lean=4, head=14, nod=3, arm=12, arm_back=0.8, arm_base=-9,
            arm_out=2, lag=0.12, tail=6, tail_droop=16, crouch=6),
    4: dict(ticks=8, travel=416, duty=0.3, lift=70, push=40, toe=12, bob=14, settle=0, sway=3, yaw=7, roll=5, rock=4,
            counter=0.7, lean=26, chest_rock=6, hip_lean=12, head=4, nod=5, arm=54, arm_back=0.75, arm_base=28,
            arm_out=12, lag=0.06, tail=10, tail_droop=2, crouch=12),
}


def feet_track(g, phase, side):
    """Per cycle phase (0..1, the foot lands at 0): the ball's forward offset in the body frame (forward is -z), its
    lift, the push-off (degrees the metatarsus turns past its lean, the hock going over the toes) and how far the
    toes turn up in the air. The two feet differ a little in how long they stay down and how high they lift."""
    duty = g['duty'] * side_variation(side, 0.02)
    stride = g['travel'] * duty
    t = phase % 1.
    if t < duty:
        s = t / duty
        # the heel holds, then peels late and quickly
        return -stride / 2 + stride * s, 0., g['push'] * smooth((s - 0.62) / 0.38) ** 1.3, 0.
    u = (t - duty) / (1 - duty)
    # the foot leaves quickly and reaches gently for the next footprint
    z = stride / 2 - stride * smooth(warp(u, 0.25))
    # the arc peaks early: the foot clears the floor going forward, then reaches down for the next footprint
    lift = g['lift'] * side_variation(side, ASYM) * math.sin(math.pi * min(1., u ** 0.8))
    push = g['push'] * (1 + 0.3 * math.sin(math.pi * min(1., u / 0.3))) * (1 - smooth(u / 0.65))
    return z, lift, push, g['toe'] * math.sin(math.pi * u) ** 1.5


def pose_at(g, slot, t, bind, offsets, skeleton):
    """World rotations and the pelvis position at cycle phase t (the right foot lands at 0, the left just after 0.5).
    The hips lead; the chest, head, shoulder plates, arms and tail follow them later, joint after joint."""
    # one step differs a little from the other
    step = 1 + ASYM * math.cos(2 * math.pi * t)
    # the pelvis turns with the leg going forward, quickly after the footfall and slowly back
    yaw = g['yaw'] * wave(t, 0., 0.2, 0.12)
    late = g['yaw'] * wave(t, 0.07, 0.2, 0.12)
    # high over the planted foot, low just after each footfall (the run: low mid-stance, high in the air)
    w = wave((2 * t) % 1., g['duty'] % 1., 0.25) * step
    bob = g['bob'] * w if slot == 4 else -g['bob'] * w
    bob += g['settle'] * max(0., math.cos(4 * math.pi * (t - 0.06))) ** 4
    # the pelvis tips forward as the weight lands on each foot and back as the body passes over it
    rock = g['rock'] * wave((2 * t) % 1., 0.12, 0.3) * step
    # over the planted foot; the hip of the lifted leg drops quickly and comes back slowly
    sway = g['sway'] * wave(t, 0.28, 0.2)
    roll = -g['roll'] * wave(t, 0.3, 0.35, 0.2)
    pw = mul(ry(yaw), rz(roll), rx(g['hip_lean'] + rock))
    # the shoulders counter the hips a little late; the chest rocks after the pelvis and breathes; the head nods
    # against the bob and keeps looking ahead
    breath = 0.8 * wave(t, 0.4, 0.4)
    turn = ry(-g['counter'] * late)
    cw = mul(turn, rx(g['lean'] + g['chest_rock'] * wave((2 * t) % 1., 0.22, 0.3) * step + breath))
    hw = mul(ry(0.2 * g['yaw'] * wave(t, 0.15, 0.2)), rx(g['head'] + g['nod'] * wave((2 * t) % 1., 0.3, 0.3)))
    worlds = {0: IDENTITY, PELVIS: pw, CHEST: cw, HEAD: hw, 3: hw}
    for plate, arm, side in ARMS:
        # opposite to the leg of the same side, late; forward quickly, back slowly, further forward than back; the
        # shoulder plates bounce after the chest
        # the left arm runs the right one's curve half a cycle later (not mirrored in sign, which would swap its
        # quick and slow halves)
        swing = -wave(t, g['lag'] + (0.5 + LEFT_LAG / 2 if side < 0 else 0.), 0.3, 0.1)
        amount = g['arm'] * side_variation(side, 0.2 * ASYM) * (swing if swing > 0 else g['arm_back'] * swing)
        worlds[plate] = mul(cw, rx(1.5 * wave((2 * t) % 1., 0.35, 0.3)))
        worlds[arm] = mul(turn, rx(-(g['arm_base'] + amount)), rz(-side * g['arm_out']))
    # the tail drags behind the hips' turn and whips, each joint later and wider than the one before
    w = pw
    for i, b in enumerate(TAIL):
        w = mul(w, ry(-g['tail'] * (1 + 0.35 * i) * wave(t, 0.11 + 0.09 * i, 0.3)),
                rx(-(g['tail_droop'] / 3 + 1.5 * wave((2 * t) % 1., 0.13 + 0.07 * i, 0.3))))
        worlds[b] = w
    pelvis = [sway, STAND + g['crouch'] + bob, 0.]
    pos = positions(skeleton, offsets, worlds, PELVIS, pelvis)
    reach = 0.
    for thigh, shin, hock, ball, side in LEGS:
        z, lift, push, toe = feet_track(g, t if side > 0 else t + 0.5 + LEFT_LAG, side)
        b = [bind[ball][0], bind[ball][1] - lift, bind[ball][2] + z]
        hip = pos[thigh]
        lean = math.degrees(math.atan2(hip[2] - b[2], b[1] - hip[1]))
        mw = rx(push - META * lean)
        target = [b[i] - apply(mw, offsets[ball])[i] for i in range(3)]
        l1, l2 = legik.norm(offsets[shin]), legik.norm(offsets[hock])
        reach = max(reach, legik.norm(legik.sub(target, hip)) / (l1 + l2))
        # the knee forward and a little out, as in the bind pose
        pole = apply(pw, [0.45 * side, 0.15, -1])
        worlds[thigh], worlds[shin] = leg(hip, target, l1, l2, pole, [bind[thigh], bind[shin], bind[hock]],
                                          [IDENTITY, IDENTITY])
        worlds[hock], worlds[ball] = mw, rx(-toe)
    return worlds, pelvis, reach


def build(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('requires the reviewed Flamedramon field model')
    mmd.exe().add_type(SPECIES, skeleton)
    model = mmd.MMD.parse(data, NB)
    model.type = SPECIES
    reference = animsheet.slot_frames(model, NB, 2)[0][0]
    offsets = {b: list(reference[b][6:9]) for b in range(1, NB)}
    # the bind pose: every world rotation the identity
    bind = positions(skeleton, offsets, {b: IDENTITY for b in range(NB)}, PELVIS, [0., STAND, 0.])
    result = mmd.MMD.parse(data, NB)
    result.type = SPECIES
    streams, checks = {}, {}
    for slot, g in GAITS.items():
        n = g['ticks']
        history, frames, reach = {}, [], 0.
        for tick in range(n + 1):
            worlds, pelvis, r = pose_at(g, slot, (tick % n) / n, bind, offsets, skeleton)
            reach = max(reach, r)
            frames.append(to_pose(skeleton, reference, worlds, PELVIS, pelvis, g['travel'] * tick / n, history))
        assert reach < 0.9, (slot, reach)
        frames, lift = lift_off_floor(model, skeleton, frames, FLOOR, PELVIS)
        sounds = [(t, 'sound', {'op': 'sound', 'frame': t + 1, 'bank': 1, 'note': 16}) for t in (0, round(n / 2))]
        streams[slot] = len(result.anims.anims)
        result.anims.anims.append(mmd.encode_anim(frames, NB, 0, sounds, tol=1, repeats=False))
        checks[slot] = dict(ticks=n, speed=round(g['travel'] / n, 2), reach=round(reach, 3),
                            maximum_body_lift=round(lift, 1))
    for slot, stream in streams.items():
        result.anims.table[slot] = stream
    result.anims.anims, result.anims.table = motioncyclelayer.share_identical_streams(result.anims.anims,
                                                                                    result.anims.table)
    output = result.build()
    effective = mmd.MMD.parse(output, NB)
    assert effective.tmd.build() == model.tmd.build()
    changed = changed_programs(model, effective)
    assert changed == [2, 3, 4], changed
    return output, dict(source_sha256=hashlib.sha256(data).hexdigest(),
                        output_sha256=hashlib.sha256(output).hexdigest(), changed_slots=changed, checks=checks,
                        storage=motionstorage.require(output, NB))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/195-flamedramon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
