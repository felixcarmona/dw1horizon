"""Apply reviewed field boundaries after foreground collision edits.

Each cell records its expected input and a reason. Keeping these final edits
separate from generated layouts preserves them when a layout is reauthored.
"""
import json
from pathlib import Path


def apply(m, name):
    data = json.loads(Path(__file__).with_name('field-walkables.json').read_text())
    edits = data['maps'].get(name)
    if edits is None:
        return
    for edit in edits['collision']:
        x, z = edit['tile']
        index = z * 100 + x
        if m.collision[index] != edit['before']:
            raise ValueError(f'{name}: reviewed boundary changed at {x},{z}')
        m.collision[index] = edit['after']
    for edit in edits.get('warps', []):
        warp = m.warps[edit['slot']]
        if any(warp[k] != v for k, v in edit['before'].items()):
            raise ValueError(f'{name}: reviewed arrival {edit["slot"]} changed')
        warp.update(edit['after'])
