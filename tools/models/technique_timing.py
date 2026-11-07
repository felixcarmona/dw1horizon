"""Retime reviewed attack poses to the native technique's collision window.

Recipes live in the imports registry. They select an existing imported clip,
pin its program and map output sample indices to source sample indices. No
native animation fallback, effect, damage or collision parameter is changed.
"""
from copy import deepcopy
import hashlib

import mmd
import motionstorage


def program(source, bones, slot, recipe):
    if hashlib.sha256(source.build()).hexdigest() != recipe['source_sha256']:
        raise ValueError('technique timing source program changed')
    poses, info = mmd.simulate(source, bones, slot=slot)
    if info['loop'] or info['tex_quirk']:
        raise ValueError('technique timing requires a finite ordinary clip')
    knots = recipe['samples']
    end = len(poses) - 1
    duration = recipe.get('ticks', end)
    if not isinstance(duration, int) or duration < 1:
        raise ValueError('technique timing requires a positive tick count')
    if knots[0] != [0, 0] or knots[-1] != [duration, end]:
        raise ValueError('technique timing must preserve the first and last sample')
    if any(a[0] >= b[0] or a[1] >= b[1] for a, b in zip(knots, knots[1:])):
        raise ValueError('technique timing samples must increase')
    mapping = []
    for tick in range(duration + 1):
        a, b = next((a, b) for a, b in zip(knots, knots[1:]) if a[0] <= tick <= b[0])
        mapping.append(round(a[1] + (b[1] - a[1]) * (tick - a[0]) / (b[0] - a[0])))
    samples = [[[round(v) for v in bone] for bone in poses[i]] for i in mapping]
    events = [(min(range(len(mapping)), key=lambda i: abs(mapping[i] - tick)), kind, value)
              for tick, kind, value in mmd.anim_events(source, bones, slot, ('sound', 'tex'))]
    return mmd.encode_anim(samples, bones, events=events, tol=0)


def apply(data, spec, recipes):
    bones = len(spec['model']['skeleton'])
    model = mmd.MMD.parse(data, bones)
    original = deepcopy(model.anims.table)
    changed = []
    for technique, recipe in recipes.items():
        slot = 46 + spec['techniques'].index(technique)
        source_slot = 46 + spec['techniques'].index(recipe['source'])
        source = model.anims.anims[original[source_slot]]
        animation = program(source, bones, source_slot, recipe)
        model.anims.table[slot] = len(model.anims.anims)
        model.anims.anims.append(animation)
        changed.append(slot)
    # Reclaim overwritten programs and unreachable tails; preserve every live
    # animation's instructions, poses and events outside the selected slots.
    animations, remap, seen = [], {}, {}
    for index in sorted(set(i for i in model.anims.table if i is not None)):
        animation = model.anims.anims[index]
        animation.tail = b''
        key = animation.build()
        if key not in seen:
            seen[key] = len(animations)
            animations.append(animation)
        remap[index] = seen[key]
    model.anims.anims = animations
    model.anims.table = [remap[i] if i is not None else None for i in model.anims.table]
    result = model.build()
    return result, dict(changed_slots=changed, storage=motionstorage.require(result, bones))
