#!/usr/bin/env python3
"""The fifth Iron Hills screen (screen 321, files IRON05): the far slope down from the ridge, a long grassy slope
between two rock shoulders (a dead tree and a broken valve wheel on the left, a rusted turbine housing on the right)
narrowing towards the bottom right, where the red rock ends and the first grey circuit blocks of the Seam show through
the ground. Our art (art/iron-hills-5.png, Nano Banana Pro at GIAS04's family of camera: eye 7000 from the look-at
point, 39 degrees down, projection 1200, 768x640) and our map data (iron-hills-5-data.json, made by
author/iron-hills-5-layout.py); the structure of the map (tile layout, TIMs, lights, the day/night palettes derived
at import) is GIAS04's, read from the player's own disc at build time, with the camera set here. Its wild Digimon are
placed by the story (early-game.py).

    python3 iron-hills-5.py OUT_DIR        writes OUT_DIR/IRON05.MAP and IRON05.TFS
"""
import json, os, sys
from foreground_depth_a2 import apply as apply_foreground
from mapbase import base_map, import_png, MOD, check_arrivals

DATA = os.path.join(MOD, 'maps', 'iron-hills-5-data.json')
ART = os.path.join(MOD, 'art', 'iron-hills-5.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('GIAS04', *d['camera']); m.projection = d['projection']
    m.collision = list(d['collision']); m.warps = d['warps']
    check_arrivals(m, 'IRON05')
    import_png('GIAS04', ART, os.path.join(out, 'IRON05.TFS'))
    apply_foreground(m, 'IRON05', os.path.join(out, 'IRON05.TFS'))
    open(os.path.join(out, 'IRON05.MAP'), 'wb').write(m.build())
    print(f'IRON05: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
