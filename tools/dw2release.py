#!/usr/bin/env python3
"""Other releases of Digimon World 2's battle models, checked against the USA files the import recipes are made from.

The recipes (content/imports/specs, the ones with "dw2") were made from the USA disc, SLUS-01193.
tools/dw2mmd.py reads a model (AAA/4.AAA/MODEL/MODEL*/M<code>.BIN) and its animation banks (the other letters of
the same code, next to it) from $DW2_DISC; on another release it checks each of those files against the USA
file's SHA-1 kept here, so the import builds the same Digimon from either disc or stops. DigimonWorld 2 (Japan),
SLPS-02844, has every file of the 42 recipes as the USA disc does (2026-10-25): no patch is needed, only the
checksums. A release that differed would need a patch like tools/dw3release.py's.

  dw2release.py make RELEASE     needs both discs ($DW2_ROOT/disc, the USA one, and $DW2_DISC, the release's);
                                 writes content/imports/releases/dw2-RELEASE.json
  dw2release.py check RELEASE    every recipe file on $DW2_DISC must equal the USA file (by SHA-1)
"""
import glob
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
DW2_ROOT = os.environ.get('DW2_ROOT', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'digimonworld2'))
SPECS = os.path.join(ROOT, 'content', 'imports', 'specs')
OUT_DIR = os.path.join(ROOT, 'content', 'imports', 'releases')
MODELS = os.path.join('AAA', '4.AAA', 'MODEL')


def sha1(p):
    return hashlib.sha1(open(p, 'rb').read()).hexdigest()


def patch_path(rel):
    return os.path.join(OUT_DIR, f'dw2-{rel}.json')


def family(disc, code):
    """{path under the models directory: absolute path} of the model `code` and its animation banks."""
    g = glob.glob(os.path.join(disc, MODELS, 'MODEL*', code + '.BIN'))
    if not g:
        raise SystemExit(f'{code}: not on {disc}')
    folder = os.path.dirname(g[0])
    out = {}
    for p in sorted(glob.glob(os.path.join(folder, '?' + code[1:] + '.BIN'))):
        out[os.path.relpath(p, os.path.join(disc, MODELS))] = p
    return out


def recipe_models():
    out = {}
    paths = glob.glob(os.path.join(SPECS, '*.json'))
    paths += glob.glob(os.path.join(ROOT, 'content', 'models', 'dcb-import', '*.json'))
    for p in sorted(paths):
        j = json.load(open(p))
        if 'dw2' in j:
            out[j['dw2']] = j.get('name', os.path.basename(p)[:-5])
    return out


_loaded = {}


def check_model(rel, disc, code):
    """Stops unless every file of model `code` on the release's disc equals the USA file. Models no recipe uses
    are not checked."""
    if rel not in _loaded:
        p = patch_path(rel)
        if not os.path.exists(p):
            raise SystemExit(f'dw2release: no checksums for the {rel} release ({p})')
        _loaded[rel] = json.load(open(p))
    want = _loaded[rel]['recipes'].get(code)
    if want is None:
        return
    got = {k: sha1(v) for k, v in family(disc, code).items()}
    if got != want:
        bad = sorted(k for k in set(want) | set(got) if want.get(k) != got.get(k))
        raise SystemExit(f'dw2release: {code} on the {rel} disc differs from the USA files: {", ".join(bad)}')


def main(argv):
    if len(argv) != 2 or argv[0] not in ('make', 'check'):
        print(__doc__)
        return 2
    import dw2mmd
    if 'DW2_DISC' not in os.environ:
        raise SystemExit('dw2release: set DW2_DISC to the extracted disc of the release')
    rel = dw2mmd.release()
    if rel != argv[1]:
        raise SystemExit(f'dw2release: {os.environ["DW2_DISC"]} is the {rel} release, not {argv[1]}')
    disc = dw2mmd.disc_dir()
    models = recipe_models()
    if argv[0] == 'make':
        usa = os.path.join(DW2_ROOT, 'disc')
        out = dict(release=rel, note='tools/dw2release.py make: do not edit by hand', recipes={})
        for code, name in sorted(models.items(), key=lambda kv: kv[1]):
            u = {k: sha1(v) for k, v in family(usa, code).items()}
            r = {k: sha1(v) for k, v in family(disc, code).items()}
            if r != u:
                raise SystemExit(f'{code} ({name}): differs on the {rel} disc; it needs a patch (see dw3release.py)')
            out['recipes'][code] = u
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(patch_path(rel), 'w') as f:
            json.dump(out, f, indent=1)
            f.write('\n')
        print(f'{patch_path(rel)}: {len(models)} recipe models, every file as on the USA disc')
    else:
        for code in sorted(models):
            check_model(rel, disc, code)
        print(f'{rel}: all {len(models)} recipe models have every file as on the USA disc')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
