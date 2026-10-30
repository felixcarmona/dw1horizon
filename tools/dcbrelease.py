#!/usr/bin/env python3
"""Other releases of Digimon Digital Card Battle, read as the USA disc the import recipes are made from.

The recipes (content/imports/specs, the ones with "dcb") were made from the USA disc, SLUS-01328.
tools/dcb2mmd.py reads a model from F.DRV (extracted: <drv>/F/NNN.PAK) and unpacks its animations and textures by
running the game's own routine under unicorn (dcb/decompress.py), at addresses of the disc's executable. Two other
releases carry the same models (2026-10-25):

  eu  Digimon Digital Card Battle (Europe), SLES-03900: all 267 F.DRV models byte-identical to the USA ones
  jp  DigimonWorld: Digital Card Arena (Japan), SLPS-03101, the game the USA one localises: 247 of 268 identical,
      every recipe model among them

Every packed record of the 78 recipe models (624: textures and animations) unpacks to the same bytes on each release:
dcb/unpack.py ($DCB_ROOT) is the game's routine rewritten in plain Python, proven equal to the game's
own code of all three executables run under unicorn (`python -m dcb.decompress check`), so no executable is needed.
(The Japanese Digital Card Battle of 1999, SLPS-02506, is another game: no model in common.)

  dcbrelease.py make RELEASE     needs both discs: $DCB_ROOT/drv (USA) and $DCB_DISC / $DCB_DRV (the release's
                                 extracted disc and DRVs); writes content/imports/releases/dcb-RELEASE.json
                                 with the SHA-1 of F.DRV and the executable (`files`: the web
                                 page checks a cooked image by them) and of every F.DRV model equal to the USA one
                                 (`make us` on the USA disc gives the USA list)
  dcbrelease.py check RELEASE    every recipe model on $DCB_DRV must be one of those
"""
import glob
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
DCB_ROOT = os.environ.get('DCB_ROOT', os.path.join(os.path.dirname(ROOT), 'digimoncardbattle'))
SPECS = os.path.join(ROOT, 'content', 'imports', 'specs')
OUT_DIR = os.path.join(ROOT, 'content', 'imports', 'releases')

def sha1(p):
    return hashlib.sha1(open(p, 'rb').read()).hexdigest()


def list_path(rel):
    return os.path.join(OUT_DIR, f'dcb-{rel}.json')


def recipe_models():
    out = {}
    for p in sorted(glob.glob(os.path.join(SPECS, '*.json'))):
        j = json.load(open(p))
        if 'dcb' in j:
            out[int(j['dcb'])] = j.get('name', os.path.basename(p)[:-5])
    return out


_loaded = {}


def release_list(rel):
    if rel not in _loaded:
        p = list_path(rel)
        if not os.path.exists(p):
            raise SystemExit(f'dcbrelease: nothing known for the {rel} release ({p})')
        _loaded[rel] = json.load(open(p))
    return _loaded[rel]


def check_model(rel, path, fid):
    """Stops unless F.DRV model `fid` of the release is the USA file."""
    want = release_list(rel)['models'].get(f'{int(fid):03d}')
    if want is None:
        raise SystemExit(f'dcbrelease: model {int(fid):03d} differs on the {rel} disc from the USA one (or is absent)')
    if sha1(path) != want:
        raise SystemExit(f'dcbrelease: model {int(fid):03d} on this disc is not the {rel} release\'s file')


def main(argv):
    if len(argv) != 2 or argv[0] not in ('make', 'check'):
        print(__doc__)
        return 2
    import dcb2mmd
    if 'DCB_DISC' not in os.environ:
        raise SystemExit('dcbrelease: set DCB_DISC (and DCB_DRV) to the release\'s extracted disc and DRVs')
    rel = dcb2mmd.release()[0]
    if rel != argv[1]:
        raise SystemExit(f'dcbrelease: {os.environ["DCB_DISC"]} is the {rel} release, not {argv[1]}')
    mine = os.path.join(dcb2mmd.drv_dir(), 'F')
    models = recipe_models()
    if argv[0] == 'make':
        usa = os.path.join(DCB_ROOT, 'drv', 'F')
        same = {}
        for p in sorted(glob.glob(os.path.join(usa, '*.PAK'))):
            q = os.path.join(mine, os.path.basename(p))
            if os.path.exists(q) and sha1(q) == sha1(p):
                same[os.path.basename(p)[:-4]] = sha1(p)
        missing = [f'{f:03d} {n}' for f, n in models.items() if f'{f:03d}' not in same]
        if missing:
            raise SystemExit(f'{rel}: recipe models not equal to the USA ones: {", ".join(missing)}')
        boot = dcb2mmd.release()[1]
        # files: what the web page checks on an image that cannot match redump (a 2048-byte .iso): the models'
        # archive and the executable whose routine unpacks them
        files = {name: sha1(os.path.join(dcb2mmd.disc_dir(), name)) for name in ('F.DRV', boot)}
        out = dict(release=rel, note='tools/dcbrelease.py make: do not edit by hand',
                   files=files, models=same)
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(list_path(rel), 'w') as f:
            json.dump(out, f, indent=1)
            f.write('\n')
        print(f'{list_path(rel)}: {len(same)} F.DRV models equal to the USA ones, all {len(models)} recipe models among them')
    else:
        for fid in sorted(models):
            check_model(rel, os.path.join(mine, f'{fid:03d}.PAK'), fid)
        print(f'{rel}: all {len(models)} recipe models are the USA files')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
