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


def apply(data, spec):
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
    result = repair(data, bones, slot, native_dash())
    storage = motionstorage.audit(result, bones)
    proof = dict(species=spec['id'], slot=slot, applied=storage['fits'],
                 original_active_travel=travel, native_species=31,
                 discarded_tail_bytes=sum(len(a.tail) for a in model.anims.anims),
                 bytes=[len(data), len(result)], storage=storage)
    # Keep tight imports playable on the original console. The report retains
    # the failed candidate's size so a separately authored, smaller clip can
    # be reviewed later; do not alter unrelated animations to make room.
    return (result if storage['fits'] else data), proof


def repair(data, bones, slot, native):
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
    events = mmd.anim_events(source, bones, slot, ('sound', 'tex'))
    attack = mmd.encode_anim(samples, bones, events=events, tol=0)
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
