#!/usr/bin/env python3
"""The niche corridor (screen 307, files CRYP01): the corridor of the Grey Lord's Crypt descending from the Mansion
Basement's trapdoor, its walls lined with empty body-shaped niches, down to the lectern room (308). Our art
(art/crypt-corridor.png, Nano Banana Pro with SAIB02's camera: eye 4106 from the look-at point, 58 degrees down,
projection 497, a 640x768 portrait) and our map data (crypt-corridor-data.json, made by author/crypt-corridor-layout.py:
the floor segmented from the art, the exits, CHKA01's lights); the structure of the map (tile layout, TIMs) is SAIB02's
(a 640x768 mansion-lab screen, 2 TIMs, one palette), read from the player's own disc at build time, with the camera set
here.

    python3 crypt-corridor.py OUT_DIR        writes OUT_DIR/CRYP01.MAP and CRYP01.TFS
"""
import json, os, sys
from mapbase import base_map, import_png, MOD, check_arrivals

DATA = os.path.join(MOD, 'maps', 'crypt-corridor-data.json')
ART = os.path.join(MOD, 'art', 'crypt-corridor.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('SAIB02', *d['camera']); m.projection = d['projection']; m.lights = d['lights']
    m.collision = list(d['collision']); m.warps = d['warps']
    check_arrivals(m, 'CRYP01')
    open(os.path.join(out, 'CRYP01.MAP'), 'wb').write(m.build())
    import_png('SAIB02', ART, os.path.join(out, 'CRYP01.TFS'))
    print(f'CRYP01: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
