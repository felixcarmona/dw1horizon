#!/usr/bin/env python3
"""Other releases of Digimon World 2003's battle models: which files the import recipes read on each disc.

The recipes (content/imports/specs, the ones with "dw3") were made from the PAL disc, SLES-03936. Every other release
is read as it is: nothing of one release's models is ever stored to turn it into another's.

- Japan (SLPS-03446) has every recipe model as the PAL disc does: its file holds only the checksums.
- USA (SLUS-01436) keeps the models in AAA/DAT/MODEL/. 15 of the 57 recipe models are other files there. Its list
  holds their own SHA-1 (`own`) and, for a model whose bones come in another order (Renamon), that order
  (`bone_order`: for each PAL bone, 1-based, the USA bone it is). The model is read with its bones put back in the
  PAL order, so every recipe's bone map stays valid; the order is our data, worked out from both discs' tracks.
  Eight of the 15 still differ after that (other meshes or animation keys): they give USA imports of their own,
  pinned separately and finished with our edits carried onto them (content/modeldelta/variants/dw3-us.json,
  tools/models/variants.py).

  dw3release.py make RELEASE     needs both discs ($DW3_ROOT/disc, the PAL one, and $DW3_DISC, the release's);
                                 writes content/imports/releases/dw3-RELEASE.json
  dw3release.py check RELEASE    every model the recipes use, read from $DW3_DISC, must be the release's file
                                 (by SHA-1); needs only the release's disc
"""
import glob
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
DW3_ROOT = os.environ.get('DW3_ROOT', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'digimonworld2003'))
SPECS = os.path.join(ROOT, 'content', 'imports', 'specs')
OUT_DIR = os.path.join(ROOT, 'content', 'imports', 'releases')
PAL_MODELS = os.path.join(DW3_ROOT, 'disc', 'AAA', 'DAT', 'FIGHT', 'MODEL')


def sha1(b):
    return hashlib.sha1(b).hexdigest()


def recipe_models():
    """{model code: Digimon name} of every recipe made from DW2003."""
    out = {}
    for p in sorted(glob.glob(os.path.join(SPECS, '*.json'))):
        j = json.load(open(p))
        if 'dw3' in j:
            out[j['dw3']] = j.get('name', os.path.basename(p)[:-5])
    return out


def list_path(rel):
    return os.path.join(OUT_DIR, f'dw3-{rel}.json')


# ------------------------------------------------------------------ making a list

def _parse(data, code):
    sys.path.insert(0, DW3_ROOT)
    import dw3_extra
    import dw3.model
    dw3_extra.patch()
    return dw3.model.parse_model(data, code)


def bone_order(pal, rel, code):
    """For each PAL bone (1-based) the release's bone with the same animation tracks, when the two files hold the
    same bones in another order; None when the order is the same or the tracks do not pair one to one."""
    mp, mr = _parse(pal, code), _parse(rel, code)
    if len(mp.bones) != len(mr.bones):
        return None
    key = lambda b: (repr(b.translation), repr(b.rotation), repr(b.scale))
    order = []
    for b in mp.bones:
        same = [r.index for r in mr.bones if key(r) == key(b)]
        if b.index in same:
            order.append(b.index)
        elif len(same) == 1:
            order.append(same[0])
        else:
            return None
    if order == list(range(1, len(order) + 1)) or sorted(order) != list(range(1, len(order) + 1)):
        return None
    back = {r: p for p, r in enumerate(order, 1)}
    for b in mp.bones:                          # the hierarchy must be the same once renumbered
        parent = mr.bones[order[b.index - 1] - 1].parent
        if (back[parent] if parent else 0) != b.parent:
            return None
    return order


def cmd_make(rel, rel_models):
    models = recipe_models()
    out = dict(release=rel, note='tools/dw3release.py make: do not edit by hand', recipes={})
    own, orders = {}, {}
    for code, name in sorted(models.items(), key=lambda kv: kv[1]):
        pal = open(os.path.join(PAL_MODELS, code + '.BIN'), 'rb').read()
        rp = os.path.join(rel_models, code + '.BIN')
        if not os.path.exists(rp):
            raise SystemExit(f'{code} ({name}): not on the {rel} disc')
        r = open(rp, 'rb').read()
        out['recipes'][code] = sha1(pal)
        if r == pal:
            continue
        own[code] = sha1(r)
        order = bone_order(pal, r, code)
        if order:
            orders[code] = order
        print(f'{name:16} {code}: own file' + (f', bones in another order {order}' if order else ''))
    if own:
        out['own'] = own
    if orders:
        out['bone_order'] = orders
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(list_path(rel), 'w') as f:
        json.dump(out, f, indent=1)
        f.write('\n')
    print(f'{list_path(rel)}: {len(models)} recipe models, {len(own)} own files, {len(orders)} reordered')


# ------------------------------------------------------------------ reading a release's file

_loaded = {}


def release_list(rel):
    if rel not in _loaded:
        p = list_path(rel)
        if not os.path.exists(p):
            raise SystemExit(f'dw3release: no list for the {rel} release ({p})')
        _loaded[rel] = json.load(open(p))
    return _loaded[rel]


def checked(rel, code, data):
    """`data`, the release's file of model `code`, checked against the release's list (models no recipe uses come
    back unchecked)."""
    pt = release_list(rel)
    if code not in pt['recipes']:
        return data
    want = pt.get('own', {}).get(code, pt['recipes'][code])
    if sha1(data) != want:
        raise SystemExit(f'dw3release: {code} on this disc is not the {rel} release\'s file')
    return data


def reorder(rel, code, model):
    """The parsed `model` with its bones in the PAL order (the list's bone_order), renumbered with their parents."""
    order = release_list(rel).get('bone_order', {}).get(code)
    if not order:
        return model
    if sorted(order) != list(range(1, len(model.bones) + 1)):
        raise SystemExit(f'dw3release: {code}: the bone order does not fit the model')
    back = {r: p for p, r in enumerate(order, 1)}
    bones = []
    for p, r in enumerate(order, 1):
        b = model.bones[r - 1]
        b.index, b.parent = p, (back[b.parent] if b.parent else 0)
        bones.append(b)
    for b in bones:
        if b.parent >= b.index:
            raise SystemExit(f'dw3release: {code}: a bone would come before its parent')
    model.bones = bones
    return model


def variant(rel):
    """The source variant id of a release whose imports are pinned on their own ('dw3-us'), or None."""
    return f'dw3-{rel}' if release_list(rel).get('own') else None


def cmd_check(rel, rel_models):
    pt = release_list(rel)
    for code in sorted(pt['recipes']):
        checked(rel, code, open(os.path.join(rel_models, code + '.BIN'), 'rb').read())
    print(f'{rel}: all {len(pt["recipes"])} recipe models are the release\'s files '
          f'({len(pt.get("own", {}))} its own, {len(pt.get("bone_order", {}))} with bones reordered)')


def main(argv):
    if len(argv) != 2 or argv[0] not in ('make', 'check'):
        print(__doc__)
        return 2
    import dw3mmd
    if 'DW3_DISC' not in os.environ:
        raise SystemExit('dw3release: set DW3_DISC to the extracted disc of the release')
    rel, models_dir = dw3mmd.release()
    if rel != argv[1]:
        raise SystemExit(f'dw3release: {os.environ["DW3_DISC"]} is the {rel} release, not {argv[1]}')
    rel_models = os.path.join(dw3mmd.disc_dir(), models_dir)
    (cmd_make if argv[0] == 'make' else cmd_check)(rel, rel_models)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
