#!/usr/bin/env python3
"""The second Iron Hills screen (screen 318, files IRON02): the hollow past the first track of the Seam Pass, with a
dry pond of cracked earth in its middle, a fallen water tower on the left slope and a bank of gears on the right; the
track goes on at the top right. Our art (art/iron-hills-2.png, Nano Banana Pro at GIAS04's family of camera: eye 7000
from the look-at point, 39 degrees down, projection 1200, 768x640) and our map data (iron-hills-2-data.json, made by
author/iron-hills-2-layout.py); the structure of the map (tile layout, TIMs, lights, the day/night palettes derived
at import) is GIAS04's, read from the player's own disc at build time, with the camera set here. Its wild Digimon are
placed by the story (early-game.py).

    python3 iron-hills-2.py OUT_DIR        writes OUT_DIR/IRON02.MAP and IRON02.TFS
"""
import json, os, sys
from foreground_depth_a2 import apply as apply_foreground
from mapbase import base_map, import_png, MOD, check_arrivals

DATA = os.path.join(MOD, 'maps', 'iron-hills-2-data.json')
ART = os.path.join(MOD, 'art', 'iron-hills-2.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('GIAS04', *d['camera']); m.projection = d['projection']
    m.collision = list(d['collision']); m.warps = d['warps']
    check_arrivals(m, 'IRON02')
    import_png('GIAS04', ART, os.path.join(out, 'IRON02.TFS'))
    apply_foreground(m, 'IRON02', os.path.join(out, 'IRON02.TFS'))
    open(os.path.join(out, 'IRON02.MAP'), 'wb').write(m.build())
    print(f'IRON02: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
