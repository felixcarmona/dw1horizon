#!/usr/bin/env python3
"""Beelzemon's field gait (tools/models/field_animations/gaits.py, profile 403) and its aimed finisher.

The finisher (slot 0x3C, Dark Shot) plays the source's somersault clip (0x34). The source never points the cannon at
anything: on landing it holds it 45 degrees down. Here the cannon arm (bone 21, which carries the barrel bones 22 and
23) turns to point straight ahead through the landing hold, with one recoil kick on the shot, and goes back to the
source pose for the recovery. Every other bone and channel, the timing and the sounds stay the source's.
"""
import copy
import hashlib
import math
import numeric as np
import mmd
import animsheet
import motioncyclelayer
import motionstorage
from motiondiscidentity import changed_programs
from tools.models.field_animations import gaits
from tools.models.field_animations.articulation import replace_channels
from tools.models.field_animations.war_greymon import align, set_rotation

SID = 403
FINISHER = 0x3C
CANNON = 21
FORWARD = [0., 0.05, -1.]        # straight ahead, a touch down (y down+, forward -z)
AIM = (24, 29, 37, 41)           # ramp in from, fully aimed at, ramp out from, back to the source at
SHOT = 30                        # the tick the recoil kicks
RECOIL = 14                      # degrees the barrel kicks up on the shot
ENCODING_DRIFT = 12              # 4096ths of a turn the re-encoded cannon channel may move outside the window


def _weight(tick):
    a0, a1, b0, b1 = AIM
    if tick <= a0 or tick >= b1:
        return 0.
    if tick < a1:
        u = (tick - a0) / (a1 - a0)
    elif tick <= b0:
        return 1.
    else:
        u = 1 - (tick - b0) / (b1 - b0)
    return u * u * (3 - 2 * u)


def _kick(tick):
    d = tick - SHOT
    if d < 0 or d > 4:
        return 0.
    return RECOIL * (1 - d / 4) ** 2 if d else RECOIL * .6


def _aimed_finisher(model, sk):
    n = len(sk)
    new = copy.deepcopy(model)
    frames, loop, _ = animsheet.slot_frames(model, n, FINISHER)
    poses = copy.deepcopy(frames)
    history = {}
    aims = []
    for tick, p in enumerate(poses):
        w = _weight(tick)
        if w == 0:
            continue
        pose = copy.deepcopy(p)
        pose[0] = [4096] * 3 + [0] * 6
        world = np.array(mmd.bone_matrices(model, pose))
        current = world[CANNON, :3, :3]
        axis = current @ np.array([0., 1., 0.])
        pitch = math.atan2(FORWARD[1], -FORWARD[2]) - math.radians(_kick(tick))   # down+; the kick lifts it
        target = np.array([0., math.sin(pitch), -math.cos(pitch)])
        q = mmd.quat(*mmd.matrix_euler(align(axis, target)))
        partial = np.array(mmd.quat_matrix(mmd._slerp((0, 0, 0, 1), q, w)))
        desired = partial @ current
        parent = world[sk[CANNON][1], :3, :3]
        set_rotation(p, CANNON, parent.T @ desired, history)
        aims.append(tick)
    anim = replace_channels(model.anims.anims[model.anims.table[FINISHER]], poses, loop, n, {(CANNON, c) for c in [3, 4, 5]})
    new.anims.anims.append(anim)
    new.anims.table[FINISHER] = len(new.anims.anims) - 1
    return new, aims


def _check(before, after, sk):
    """Only bone 21's rotation moves, inside the aim window; at full weight the barrel points ahead."""
    n = len(sk)
    a, _, ea = animsheet.slot_frames(before, n, FINISHER)
    b, _, eb = animsheet.slot_frames(after, n, FINISHER)
    assert len(a) == len(b) and ea == eb
    worst = 0.
    for tick, (x, y) in enumerate(zip(a, b)):
        for bone in range(n):
            for channel in range(9):
                if bone == CANNON and channel in (3, 4, 5):
                    if AIM[0] < tick < AIM[3]:
                        continue
                    drift = abs((y[bone][channel] - x[bone][channel] + 2048) % 4096 - 2048)
                    assert drift <= ENCODING_DRIFT, (tick, channel, drift)   # the re-encoded channel's tolerance
                    continue
                assert x[bone][channel] == y[bone][channel], (tick, bone, channel)
        if AIM[1] <= tick <= AIM[2] and _kick(tick) == 0:
            pose = copy.deepcopy(y)
            pose[0] = [4096] * 3 + [0] * 6
            axis = np.array(mmd.bone_matrices(after, pose))[CANNON, :3, :3] @ np.array([0., 1., 0.])
            target = np.array(FORWARD) / np.linalg.norm(FORWARD)
            worst = max(worst, math.degrees(math.acos(max(-1., min(1., float(axis @ target))))))
    assert worst < 3, worst
    return dict(slot=FINISHER, aim_window=list(AIM), shot_tick=SHOT, recoil_degrees=RECOIL, worst_aim_error_degrees=round(worst, 2))


def build(data, sk):
    walked, proof = gaits.build(data, sk)
    n = len(sk)
    mmd.exe().skeleton[SID] = sk
    mmd.exe().bone_count[SID] = n
    before = mmd.MMD.parse(walked, n)
    before.type = SID
    aimed, _ = _aimed_finisher(before, sk)
    for anim in aimed.anims.anims:
        anim.tail = b''
    aimed.anims.anims, aimed.anims.table = motioncyclelayer.share_identical_streams(aimed.anims.anims, aimed.anims.table)
    result = aimed.build()
    after = mmd.MMD.parse(result, n)
    after.type = SID
    assert changed_programs(before, after) == [FINISHER] and before.tmd.build() == after.tmd.build()
    check = _check(before, after, sk)
    storage = motionstorage.audit(result, n)
    assert storage['fits'], storage
    return result, dict(proof, output_sha256=hashlib.sha256(result).hexdigest(), changed_slots=proof['changed_slots'] + [FINISHER],
                        gait_output_sha256=proof['output_sha256'], finisher_check=check, storage=storage)


def humanoid_walk(data, sk):
    """An upright, relaxed walk on the baked chibi model; Devimon is the visual reference."""
    profile = dict(gaits.PROFILES[SID],
        source='3c07b7fe613d426df67ff8fb772a6b982aec1ee2453c321ba1368b4518a6ae7d',
        slots=[2], periods={2: 24}, macro_periods={2: 24}, speeds={2: 15},
        lifts={2: 18}, tracks=32, height_bias=-7, leans={2: 2},
        gaze_pitch_by_slot={2: 0}, bounce={2: 2}, sway={2: 3},
        arm_amplitudes={2: 17}, arm_bends={2: 20}, arm_base=3, arm_spread=10,
        steady_arm_amp=.55, steady_arm_bends={2: 16}, encoding_tol=1, validate_ik=True,
        style='upright humanoid steps, soft elbows, delayed torso and wing/tail acting')
    return gaits.build_profile(data, sk, SID, profile)
