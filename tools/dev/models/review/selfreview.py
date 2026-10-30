#!/usr/bin/env python3
"""Sheets for reviewing a Digimon's animations by eye without the web tool: one image per Digimon and donor.

  selfreview.py sheets [ID ...|all] [--donor N] [--jobs 12]   build/review/self/<id>-d<donor>.png (+ .json: the polish report)

Rows: the model's own idle (its source game: the posture to recognise it by), then the variant's idle, walk and run, then the donor's
own walk. Each row is shown at its first tick and halfway through, from the front, the side and three quarters.
The donor is the first in the review's list (the importer's pick) unless --donor is given.
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import argparse, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); TOOLS = str(_DevPath(_DEV_ROOT) / "tools"); ROOT = _DEV_ROOT
sys.path.insert(0, TOOLS); sys.path.insert(0, HERE)
try:
    import numpy  # noqa: F401
except ImportError:
    py = os.path.join(os.environ.get("DCB_ROOT", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), 'digimoncardbattle')), ".venv", "bin", "python")
    os.execv(py, [py, os.path.abspath(__file__)] + sys.argv[1:])
import animstudio as A
from tools.image import Image

OUT = os.path.join(ROOT, 'build/review/self')
PANELS = ['mesh:front', 'mesh:side', 'mesh:three']
SIZE = 200


def strip(spec, size=SIZE):
    """One clip as a strip: its first tick and its middle one, each from the three views."""
    mod = A.Model(spec, 0)
    rows = A.build([mod], PANELS, size)
    n = len(mod.frames)
    a, b = A.frame(rows, 0, size), A.frame(rows, n // 2, size)
    im = Image.new('RGB', (a.width + b.width + 8, a.height), (60, 60, 70))
    im.paste(a, (0, 0)); im.paste(b, (a.width + 8, 0))
    return im


def sheet(sid, donor=None):
    from tools.dev.models.review import lib as lib; import species
    sp = lib.find(sid); t = sp['id']
    ds = lib.donor_ranking(sp)
    d = donor if donor is not None else ds[0]['donor']
    p = lib.build_variant(sp, d)
    O = species.originals(); dn = O.rec[d]['para']['name']
    tex = sp['tex'] or ''
    specs = [f"{sp['model']}:{t}:{tex}:0:{sp['name']} own idle (source game)"]
    import mmd
    m = mmd.MMD.load(p, t)
    for s, nm in ((0, 'idle'), (2, 'walk'), (3, 'run')):
        if s < len(m.anims.table) and m.anims.table[s] is not None:
            specs.append(f"{p}:{t}:{tex}:{s}:{sp['name']} + {dn}  {nm}")
    specs.append(f"{O.model_path(d)}:{d}::2:{dn} (donor) own walk")
    strips = [strip(s) for s in specs]
    W = max(x.width for x in strips)
    im = Image.new('RGB', (W, sum(x.height for x in strips)), (20, 22, 26))
    y = 0
    for x in strips:
        im.paste(x, (0, y)); y += x.height
    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, f'{t}-d{d}.png')
    im.save(out)
    try:
        rep = json.load(open(p + '.rep.json'))
    except OSError:
        rep = {}
    json.dump(dict(id=t, name=sp['name'], donor=d, donor_name=dn, report=rep), open(out[:-4] + '.json', 'w'), indent=1)
    return out


def _one(x):
    sid, donor = x
    try:
        return sheet(sid, donor)
    except Exception as ex:
        return f'{sid}: error {type(ex).__name__}: {ex}'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['sheets'])
    ap.add_argument('ids', nargs='*')
    ap.add_argument('--donor', type=int)
    ap.add_argument('--jobs', type=int, default=12)
    a = ap.parse_args()
    sys.argv = sys.argv[:1]
    from tools.dev.models.review import lib as lib
    if not a.ids or a.ids == ['all']:
        W = lib._walkpolish()
        ids = [s['id'] for s in W.all_species() if os.path.exists(lib.default_model(s))]
    else:
        ids = [int(x) for x in a.ids]
    from multiprocessing import Pool
    with Pool(a.jobs) as pool:
        for r in pool.imap_unordered(_one, [(i, a.donor) for i in ids]):
            print(r, flush=True)


if __name__ == '__main__':
    main()
