#!/usr/bin/env python3
"""The first Iron Hills screen (screen 317, files IRON01): the entrance of the Seam Pass, over the crest of Leomon's
hill (GIAS09): a track of dry grass climbing between red sandstone slopes with the savanna's buried machinery
showing through them, a huge half-buried gear at the right, a stack of pipes at the left. Our art
(art/iron-hills-1.png, Nano Banana Pro at GIAS04's family of camera: eye 7000 from the look-at point, 39 degrees
down, projection 1200, 768x640) and our map data (iron-hills-1-data.json, made by author/iron-hills-1-layout.py:
the track segmented from the art, the pipes blocked, the exits, the arrivals); the structure of the map (tile layout,
TIMs, lights, the day/night palettes derived at import) is GIAS04's, read from the player's own disc at build time,
with the camera set here. Its wild Digimon are placed by the story (early-game.py).

    python3 iron-hills-1.py OUT_DIR        writes OUT_DIR/IRON01.MAP and IRON01.TFS
"""
import json, os, sys
from foreground_depth_a2 import apply as apply_foreground
from mapbase import base_map, import_png, MOD, check_arrivals

DATA = os.path.join(MOD, 'maps', 'iron-hills-1-data.json')
ART = os.path.join(MOD, 'art', 'iron-hills-1.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('GIAS04', *d['camera']); m.projection = d['projection']
    m.collision = list(d['collision']); m.warps = d['warps']
    check_arrivals(m, 'IRON01')
    import_png('GIAS04', ART, os.path.join(out, 'IRON01.TFS'))
    apply_foreground(m, 'IRON01', os.path.join(out, 'IRON01.TFS'))
    open(os.path.join(out, 'IRON01.MAP'), 'wb').write(m.build())
    print(f'IRON01: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
