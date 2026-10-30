#!/usr/bin/env python3
"""The fourth Iron Hills screen (screen 320, files IRON04): the ridge on top of the hills, a wide plateau of dry grass
and bare rock with a fallen pylon lying across its left half and a pit of gear teeth at the right; the track goes on
at the top. Our art (art/iron-hills-4.png, Nano Banana Pro at GIAS04's family of camera: eye 7000 from the look-at
point, 39 degrees down, projection 1200, 768x640) and our map data (iron-hills-4-data.json, made by
author/iron-hills-4-layout.py); the structure of the map (tile layout, TIMs, lights, the day/night palettes derived
at import) is GIAS04's, read from the player's own disc at build time, with the camera set here. Its wild Digimon are
placed by the story (early-game.py).

    python3 iron-hills-4.py OUT_DIR        writes OUT_DIR/IRON04.MAP and IRON04.TFS
"""
import json, os, sys
from foreground_depth_a2 import apply as apply_foreground
from mapbase import base_map, import_png, MOD, check_arrivals

DATA = os.path.join(MOD, 'maps', 'iron-hills-4-data.json')
ART = os.path.join(MOD, 'art', 'iron-hills-4.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('GIAS04', *d['camera']); m.projection = d['projection']
    m.collision = list(d['collision']); m.warps = d['warps']
    check_arrivals(m, 'IRON04')
    import_png('GIAS04', ART, os.path.join(out, 'IRON04.TFS'))
    apply_foreground(m, 'IRON04', os.path.join(out, 'IRON04.TFS'))
    open(os.path.join(out, 'IRON04.MAP'), 'wb').write(m.build())
    print(f'IRON04: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
