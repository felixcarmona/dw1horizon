#!/usr/bin/env python3
"""The third Iron Hills screen (screen 319, files IRON03): the climb out of the hollow, a zigzag track between red
sandstone terraces with a great cogwheel set into the right wall and a rusted boiler on a terrace at the left; the
track goes on over the top. A tall screen (640x768). Our art (art/iron-hills-3.png, Nano Banana Pro at the pass's eye
and lens, 7000 and projection 1200, but 46 degrees down so the top edge stays inside the tile grid) and our map data
(iron-hills-3-data.json, made by author/iron-hills-3-layout.py); the structure of the map (tile layout, 2 TIMs, lights,
the day/night palettes derived at import) is GIAS07's, read from the player's own disc at build time, with the camera
set here. Its wild Digimon are placed by the story (early-game.py).

    python3 iron-hills-3.py OUT_DIR        writes OUT_DIR/IRON03.MAP and IRON03.TFS
"""
import json, os, sys
from foreground_depth_a2 import apply as apply_foreground
from mapbase import base_map, import_png, MOD, check_arrivals

DATA = os.path.join(MOD, 'maps', 'iron-hills-3-data.json')
ART = os.path.join(MOD, 'art', 'iron-hills-3.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('GIAS07', *d['camera']); m.projection = d['projection']
    m.collision = list(d['collision']); m.warps = d['warps']
    check_arrivals(m, 'IRON03')
    import_png('GIAS07', ART, os.path.join(out, 'IRON03.TFS'))
    apply_foreground(m, 'IRON03', os.path.join(out, 'IRON03.TFS'))
    open(os.path.join(out, 'IRON03.MAP'), 'wb').write(m.build())
    print(f'IRON03: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
