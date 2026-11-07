"""Author paired leg gestures on Armageddemon's constant-scale model.

The four supporting feet stay planted while one anatomical pair flexes. Body
breathing, delayed head motion and a travelling tail wave overlap the leg arcs.
The result is baked with models/edit.py; this is an authoring recipe.
"""
import copy
import hashlib
import math

import animsheet
import legik
import mmd
import motioncyclelayer
import motionstorage
import retarget as rt
from tools.models.field_animations.celebrations import set_world, turn

SOURCE = '0203002d79de4b438b7060ee95ae41d9fb7d29f945501c34ac4407dc8aefe050'
PAIRS = ((15, 24), (12, 18), (9, 21))
# Indices in the preceding move list, selected by attack posture: beam, mouth
# discharge, or the stationary program pose. Remap all slots simultaneously.
# Retained moves keep their save-game indices, including the finisher at 14.
ATTACKS = (0, 1, 2, 11, 4, 10, 6, 2, 10, 12, 10, 11, 12, 2, 14, 12)


def build(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('Armageddemon requires the reviewed constant-scale source')
    model = mmd.MMD.parse(data, len(skeleton))
    model.type = 407
    mmd.exe().add_type(407, skeleton)
    rest = copy.deepcopy(animsheet.slot_frames(model, len(skeleton), 0)[0][0])
    world, positions = rt.world_transform(skeleton, rest)
    for slot, ticks, lift in ((0, 24, 12), (11, 60, 80)):
        samples = []
        for tick in range(ticks + 1):
            pose = copy.deepcopy(rest)
            phase = 2 * math.pi * tick / ticks
            envelope = math.sin(math.pi * tick / ticks) ** 2 if slot == 11 else 1
            # Relative to the first pose: continuous position and velocity at wrap.
            pose[1][7] += round(2 * math.sin(phase) * envelope)
            turn(pose, 1, [1.0 * math.sin(phase) * envelope, 0,
                           .65 * math.sin(phase) * envelope])
            turn(pose, 2, [1.6 * (math.sin(phase - .3) - math.sin(-.3)) * envelope, 0, 0])
            for i, bone in enumerate((5, 6, 7, 8)):
                turn(pose, bone, [0, (1.3 + i * .3) *
                                 (math.sin(phase - i * .4) - math.sin(-i * .4)) * envelope, 0])
            for pair, hips in enumerate(PAIRS):
                local = tick / (ticks / 3) - pair
                arc = math.sin(math.pi * local) ** 2 if 0 < local < 1 else 0
                for hip in hips:
                    knee, ankle = hip + 1, hip + 2
                    target = list(positions[ankle])
                    target[1] -= lift * arc
                    target[2] -= lift * .25 * arc
                    _, current = rt.world_transform(skeleton, pose)
                    upper = legik.sub(positions[knee], positions[hip])
                    lower = legik.sub(positions[ankle], positions[knee])
                    axis = legik.unit(legik.sub(positions[ankle], positions[hip]))
                    pole = legik.sub(upper, legik.mul(axis, legik.dot(upper, axis)))
                    k, a = legik.solve(current[hip], target, legik.norm(upper), legik.norm(lower), pole)
                    set_world(pose, skeleton, hip, rt.m3mul(rt.swing(upper, legik.sub(k, current[hip])), world[hip]))
                    set_world(pose, skeleton, knee, rt.m3mul(rt.swing(lower, legik.sub(a, k)), world[knee]))
                    # The foot follows the knee with a small delayed curl, then settles flat.
                    set_world(pose, skeleton, ankle, world[ankle], target)
                    curl = math.sin(math.pi * max(0, min(1, local - .08))) ** 2 if 0 < local < 1 else 0
                    turn(pose, ankle, [4 * curl, 0, 0])
            samples.append(pose)
        samples[0] = copy.deepcopy(rest)
        samples[-1] = copy.deepcopy(rest)
        _, _, events = animsheet.slot_frames(model, len(skeleton), slot)
        events = [(round(t * ticks / 47), kind, event) for t, kind, event in events]
        animation = mmd.encode_anim(samples, len(skeleton), 0 if slot == 0 else None, events, tol=.25)
        model.anims.table[slot] = len(model.anims.anims)
        model.anims.anims.append(animation)
    model.anims.anims, model.anims.table = motioncyclelayer.share_identical_streams(model.anims.anims, model.anims.table)
    preceding = model.anims.table[:]
    for index, source in enumerate(ATTACKS):
        model.anims.table[46 + index] = preceding[46 + source]
    result = model.build()
    return result, motionstorage.require(result, len(skeleton))
