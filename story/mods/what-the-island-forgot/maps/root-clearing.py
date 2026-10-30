#!/usr/bin/env python3
"""The Root Clearing (screen 314, files ROOT01): the clearing south of Native Forest's big field where the island's
first road surfaces, pale carved slabs lifted and broken by the roots of a colossal fallen tree. The dirt path at the
top leads back to the field (MAYO03, its new exit 4); the path at the bottom right goes down the cliff to Coela Point
(MAYO05, its new exit 1). Our art (art/root-clearing.png, Nano Banana Pro with MAYO04B's camera: eye 6410 from the
look-at point, 47 degrees down, projection 927, 768x640) and our map data (root-clearing-data.json, made by
author/root-clearing-layout.py: the floor segmented from the art, the exits, the arrivals); the structure of the map
(tile layout, TIMs, lights, the day/night palettes derived at import) is MAYO04B's, read from the player's own disc
at build time, with the camera set here.

    python3 root-clearing.py OUT_DIR        writes OUT_DIR/ROOT01.MAP and ROOT01.TFS
"""
import json, os, sys
from foreground_depth_a2 import apply as apply_foreground
from mapbase import base_map, import_png, MOD, check_arrivals

DATA = os.path.join(MOD, 'maps', 'root-clearing-data.json')
ART = os.path.join(MOD, 'art', 'root-clearing.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('MAYO04B', *d['camera']); m.projection = d['projection']
    m.collision = list(d['collision']); m.warps = d['warps']
    check_arrivals(m, 'ROOT01')
    import_png('MAYO04B', ART, os.path.join(out, 'ROOT01.TFS'))
    apply_foreground(m, 'ROOT01', os.path.join(out, 'ROOT01.TFS'))
    open(os.path.join(out, 'ROOT01.MAP'), 'wb').write(m.build())
    print(f'ROOT01: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
