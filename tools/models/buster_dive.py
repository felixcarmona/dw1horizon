"""Give an imported Buster Dive clip the native Patamon dash timing.

The imported-species provider applies this after the reviewed field overlays,
whose size passes can scale root travel. The native model comes from the
player's disc; no native animation data is stored in the repository. Only the
selected technique slot changes, even when its original program is shared
with punches, finishers or field animations.
"""
from copy import deepcopy
from pathlib import Path
import sys
from functools import lru_cache
import hashlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mmd
import motionstorage


@lru_cache(maxsize=1)
def native_dash():
    import species

    originals = species.originals()
    native = mmd.MMD.parse(Path(originals.model_path(31)).read_bytes(),
                           originals.rec[31]['para']['boneCount'])
    return native.anims.anims[native.anims.table[0x30]]


def apply(data, spec, clip=None):
    """Return (final model, optional proof) after aliases and size overlays."""
    if 'Buster Dive' not in (spec.get('techniques') or []):
        return data, None
    slot = 0x2e + spec['techniques'].index('Buster Dive')
    bones = len(spec['model']['skeleton'])
    model = mmd.MMD.parse(data, bones)
    animation = model.anims.anims[model.anims.table[slot]]
    poses, _ = mmd.simulate(animation, bones, slot=slot)
    window = [p[0][8] for p in poses[22:34]]
    travel = round(window[0] - min(window)) if window else 0
    if travel >= 500:
        return data, None
    result = repair(data, bones, slot, native_dash(), clip=clip)
    storage = motionstorage.audit(result, bones)
    proof = dict(species=spec['id'], slot=slot, applied=storage['fits'],
                 original_active_travel=travel, native_species=31,
                 discarded_tail_bytes=sum(len(a.tail) for a in model.anims.anims),
                 bytes=[len(data), len(result)], storage=storage)
    if clip is not None:
        proof['authored_clip'] = clip
        if not storage['fits']:
            raise ValueError('reviewed Buster Dive clip exceeds the fixed animation buffers')
    # Keep tight imports playable on the original console. The report retains
    # the failed candidate's size so a separately authored, smaller clip can
    # be reviewed later; do not alter unrelated animations to make room.
    return (result if storage['fits'] else data), proof


def repair(data, bones, slot, native, clip=None):
    """Keep the attack's body program and replace its entity motion.

    During effect frames 23-33 Buster Dive tests a line from the attacker's
    position to its effect origin. A stationary attack, or a short lunge
    before that window, cannot cover the ranged AI's launch gap.
    Patamon's native clip crosses that gap during the collision window.
    """
    model = mmd.MMD.parse(data, bones)
    source = model.anims.anims[model.anims.table[slot]]
    if any(i['op'].startswith('loop') for i in source.instrs):
        raise ValueError('Buster Dive repair requires a finite, unrolled attack')
    poses, info = mmd.simulate(source, bones, slot=slot)
    if info['tex_quirk']:
        raise ValueError('Buster Dive repair cannot retime texture pre-check instructions')
    roots, _ = mmd.simulate(native, len(native.pose) + 1)
    # Keep each body sample exactly; extend short attacks by holding the last
    # pose so the EFE collision window can finish. Longer clips keep their
    # recovery, with the native root resting at its final position.
    samples = []
    for tick in range(max(len(poses), len(roots))):
        pose = deepcopy(poses[min(tick, len(poses) - 1)])
        pose[0] = [round(v) for v in roots[min(tick, len(roots) - 1)][0]]
        samples.append(pose)
    if clip is None:
        events = mmd.anim_events(source, bones, slot, ('sound', 'tex'))
        attack = mmd.encode_anim(samples, bones, events=events, tol=0)
    else:
        attack = authored_dash_clip(source, poses, roots, bones, slot, clip)
    model.anims.table[slot] = len(model.anims.anims)
    model.anims.anims.append(attack)
    used = sorted({i for i in model.anims.table if i is not None})
    # Aliased imports can carry overwritten, unreachable programs in the
    # bytes after another animation's terminator. Discard those tails and
    # share identical programs to make room for the separate dash. No pose,
    # event, mesh or live program is removed.
    remap, seen, animations = {}, {}, []
    for index in used:
        animation = model.anims.anims[index]
        animation.tail = b''
        program = animation.build()
        if program not in seen:
            seen[program] = len(animations)
            animations.append(animation)
        remap[index] = seen[program]
    model.anims.anims = animations
    model.anims.table = [remap[i] if i is not None else None for i in model.anims.table]
    result = model.build()
    return result


def authored_dash_clip(source, poses, roots, bones, slot, recipe):
    """A few reviewed body poses leave room for the unchanged native dash.

    Only configured tight imports use this path. All other programs, the mesh,
    and the fixed resident/cold buffers retain their existing values.
    """
    if hashlib.sha256(source.build()).hexdigest() != recipe['source_sha256']:
        raise ValueError('Buster Dive body source changed')
    keys = recipe['pose_keys']
    if keys[0] != [0, 0] or keys[-1][0] != len(roots) - 1:
        raise ValueError('Buster Dive pose keys must cover the native dash')
    if any(a[0] >= b[0] or a[1] > b[1] for a, b in zip(keys, keys[1:])) or \
            any(not 0 <= source_index < len(poses) for _, source_index in keys):
        raise ValueError('invalid Buster Dive pose keys')
    samples, mapping = [], []
    for tick, root in enumerate(roots):
        a, b = next((a, b) for a, b in zip(keys, keys[1:]) if a[0] <= tick <= b[0])
        fraction = (tick - a[0]) / (b[0] - a[0])
        mapping.append(a[1] + (b[1] - a[1]) * fraction)
        pose = []
        for bone, (left, right) in enumerate(zip(poses[a[1]], poses[b[1]])):
            values = []
            for channel, (x, y) in enumerate(zip(left, right)):
                delta = y - x
                if 3 <= channel < 6:
                    delta = (delta + 2048) % 4096 - 2048
                value = x + delta * fraction
                if 3 <= channel < 6 and samples:
                    previous = samples[-1][bone][channel]
                    value = previous + (value - previous + 2048) % 4096 - 2048
                values.append(round(value))
            pose.append(values)
        pose[0] = [round(value) for value in root[0]]
        samples.append(pose)
    events = [(min(range(len(mapping)), key=lambda i: abs(mapping[i] - tick)), kind, value)
              for tick, kind, value in mmd.anim_events(source, bones, slot, ('sound', 'tex'))]
    attack = mmd.encode_anim(samples, bones, events=events, tol=1, repeats=False)
    exact = mmd.encode_anim(samples, bones, tol=0, repeats=False)
    # Body interpolation may differ by one encoded unit. Root instructions are
    # copied from the exact track, preserving the native collision-window reach.
    for instruction in attack.instrs:
        if instruction['op'] == 'key':
            instruction['bones'] = [g for g in instruction['bones'] if g['bone'] != 0]
    attack.instrs = [i for i in attack.instrs if i['op'] != 'key' or i['bones']]
    for instruction in exact.instrs:
        if instruction['op'] != 'key':
            continue
        key = deepcopy(instruction)
        key['bones'] = [g for g in key['bones'] if g['bone'] == 0]
        if not key['bones']:
            continue
        existing = next((i for i in attack.instrs if i['op'] == 'key' and i['frame'] == key['frame']), None)
        if existing is not None:
            existing['bones'].extend(key['bones'])
        else:
            at = next((j for j, i in enumerate(attack.instrs) if i.get('frame', 99999) > key['frame']),
                      len(attack.instrs) - 1)
            attack.instrs.insert(at, key)
    return attack


def main():
    import argparse
    import species

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('species', type=int)
    parser.add_argument('input', type=Path, help='model from tools/models/edit.py get')
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    spec = species.load_content()[args.species]
    slot = 0x2e + spec['techniques'].index('Buster Dive')
    import json
    records = json.loads((Path(species.ROOT) / 'content/models/imports/models.json').read_text())
    data = args.input.read_bytes()
    if not records[str(args.species)].get('aliases_applied') and spec['model'].get('slot_aliases'):
        data = species.apply_slot_aliases(data, spec)
    args.output.write_bytes(repair(data, len(spec['model']['skeleton']), slot, native_dash()))


if __name__ == '__main__':
    main()
