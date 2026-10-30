#!/usr/bin/env python3
"""The ossuary (screen 336, files OVPS07): the dead-end cave behind the cave mouth of the last descent (335), where the
Seam's hunters dumped what they caught: heaps of bones and skulls against the walls, a cairn with a cracked grave
slab, rusted collars and chains on the back wall. A wide screen (768x640). Our art (art/ossuary.png, Nano Banana Pro
with the pass's eye, 7000, at 45 degrees down, projection 1000) and our map data (ossuary-data.json, made by
author/ossuary-layout.py); the structure of the map (tile layout, 3 TIMs, the day/night palettes derived at import)
is MAYO04B's, read from the player's own disc at build time, with the camera set here. Its Digimon are placed by the
story (early-game.py).

    python3 ossuary.py OUT_DIR        writes OUT_DIR/OVPS07.MAP and OVPS07.TFS
"""
import json, os, sys
from mapbase import base_map, import_png, MOD, check_arrivals

DATA = os.path.join(MOD, 'maps', 'ossuary-data.json')
ART = os.path.join(MOD, 'art', 'ossuary.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('MAYO04B', *d['camera']); m.projection = d['projection']
    m.collision = list(d['collision']); m.warps = d['warps']
    check_arrivals(m, 'OVPS07')
    open(os.path.join(out, 'OVPS07.MAP'), 'wb').write(m.build())
    import_png('MAYO04B', ART, os.path.join(out, 'OVPS07.TFS'))
    print(f'OVPS07: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
