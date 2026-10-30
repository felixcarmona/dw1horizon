#!/usr/bin/env python3
"""The Brink (screen 322, files IRON06): the last screen of the Iron Hills, where the red hills end and the Seam begins:
the last dry grass and red rock on the left with a leaning pylon, a broken step, and to the right the grey circuit-block
ground of the land beyond with a deep crack and one slab lying across it. The way on is the right edge (the Seam, 323).
Our art (art/iron-hills-6.png, Nano Banana Pro at GIAS04's family of camera: eye 7000 from the look-at point, 39
degrees down, projection 1200, 768x640) and our map data (the-brink-data.json, made by author/the-brink-layout.py);
the structure of the map (tile layout, TIMs, lights, the day/night palettes derived at import) is GIAS04's, read from
the player's own disc at build time, with the camera set here. Its wild Digimon are placed by the story (early-game.py).

    python3 the-brink.py OUT_DIR        writes OUT_DIR/IRON06.MAP and IRON06.TFS
"""
import json, os, sys
from foreground_depth_a2 import apply as apply_foreground
from mapbase import base_map, import_png, MOD, check_arrivals

DATA = os.path.join(MOD, 'maps', 'the-brink-data.json')
ART = os.path.join(MOD, 'art', 'iron-hills-6.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('GIAS04', *d['camera']); m.projection = d['projection']
    m.collision = list(d['collision']); m.warps = d['warps']
    check_arrivals(m, 'IRON06')
    import_png('GIAS04', ART, os.path.join(out, 'IRON06.TFS'))
    apply_foreground(m, 'IRON06', os.path.join(out, 'IRON06.TFS'))
    open(os.path.join(out, 'IRON06.MAP'), 'wb').write(m.build())
    print(f'IRON06: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
