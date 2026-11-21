#!/usr/bin/env python3
"""Search once the turns that keep the hands out of the legs and the body, and commit them.

native_hands.clear_hands finds, tick by tick, the smallest turn of the arm and of the hand that leaves the hand outside
the `clear` bones. The search is slow (about a quarter of an hour for KingEtemon) and gives the same turns on every
machine, so the build does not repeat it: it applies the turns of content/models/imports/native-hands-solved.json,
kept under a key of the model, the skeleton and the recipe. A model or recipe the table has not seen is searched
during the build, as before.

    python3 tools/models/solve_hands.py --build build/NAME     # search, write the table, check the replay
    python3 tools/models/solve_hands.py --build build/NAME --check   # the table is current: replay only, no search

--build is a tools/derive output folder holding imported-models and imported-species (the imports step). Nothing is
written into it. After changing a `hands` recipe with `clear`, or anything before it in that species' binding, run
this again and commit the table.
"""
import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def species():
    """The ids of the bindings whose hands recipe searches."""
    rows = json.loads((ROOT / 'content/models/imports/native-bindings.json').read_text())
    return [t for t, r in rows.items() if isinstance(r, dict) and (r.get('hands') or {}).get('clear')]


def overlay(build, sid, mode):
    """The overlay of species `sid` built in a scratch folder with NATIVE_HANDS_SOLVED=mode -> (its bytes, seconds)."""
    from tools.derive.steps import overlays
    os.environ['NATIVE_HANDS_SOLVED'] = mode
    with tempfile.TemporaryDirectory(prefix='solve-hands-') as tmp:
        for name in ('imported-models', 'imported-species', 'record-originals'):
            if (build / name).exists():
                os.symlink(build / name, Path(tmp) / name)
        out = str(Path(tmp) / 'imported-species')
        os.makedirs(out + '-models', exist_ok=True)
        t0 = time.time()
        overlays.make_overlay(out, sid, None)
        made = sorted(Path(out + '-models').glob(f'{sid}-*.MMD'))
        return made[0].read_bytes(), time.time() - t0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--check', action='store_true', help='only check that the table has every species (no search)')
    a = p.parse_args()
    os.chdir(ROOT)
    os.environ.setdefault('SPECIES_PROVIDER', 'imports')
    from tools.models.field_animations import native_hands
    build = a.build.resolve()
    if a.check:
        for sid in species():
            data, seconds = overlay(build, sid, 'require')
            print(f'{sid}: in the table, {hashlib.sha1(data).hexdigest()} in {seconds:.1f} s')
        return
    searched = {}
    for sid in species():
        native_hands.SEARCHED.clear()
        data, seconds = overlay(build, sid, 'search')
        searched[sid] = (data, dict(native_hands.SEARCHED))
        print(f'{sid}: searched in {seconds:.1f} s, {hashlib.sha1(data).hexdigest()}', flush=True)
    table = {}
    for _, found in searched.values():
        table.update(found)
    path = Path(native_hands.SOLVED).resolve()
    path.write_text(json.dumps({'search': native_hands.SEARCH, 'turns': table}, sort_keys=True, separators=(',', ':')) + '\n',
                    encoding='utf-8')
    print(f'{path.relative_to(ROOT)}: {len(table)} keys, {path.stat().st_size} bytes')
    for sid, (data, _) in searched.items():
        again, seconds = overlay(build, sid, 'require')
        if again != data:
            sys.exit(f'{sid}: the replay differs from the search')
        print(f'{sid}: replay identical in {seconds:.1f} s')


if __name__ == '__main__':
    main()
