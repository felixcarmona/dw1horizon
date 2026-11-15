"""Preserve a care program when restoring its formerly shared battle slot."""
import copy

import mmd
import motioncyclelayer
from tools.models.field_animations import native_battle


def snapshot(data, skeleton, recipe):
    """Compact the old shared program exactly as the existing recipe did."""
    slots = recipe.get('preserve_aliases', ())
    if not slots:
        return {}
    baseline, _ = native_battle.compact(data, len(skeleton), recipe['compact'])
    model = mmd.MMD.parse(baseline, len(skeleton))
    return {slot: copy.deepcopy(model.anims.anims[model.anims.table[slot]]) for slot in slots}


def restore(data, skeleton, programs):
    """Keep the old decoded care motion when the battle replacement makes it cold."""
    model = mmd.MMD.parse(data, len(skeleton))
    for slot, program in programs.items():
        model.anims.table[slot] = len(model.anims.anims)
        model.anims.anims.append(program)
    used = sorted({i for i in model.anims.table if i is not None})
    renumber = {old: new for new, old in enumerate(used)}
    model.anims.anims = [model.anims.anims[i] for i in used]
    model.anims.table = [renumber.get(i) for i in model.anims.table]
    model.anims.anims, model.anims.table = motioncyclelayer.share_identical_streams(model.anims.anims, model.anims.table)
    return model.build()
