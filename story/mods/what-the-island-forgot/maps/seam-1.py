#!/usr/bin/env python3
"""The first Seam screen (screen 323, files SEAM01): past the Brink, the grey circuit-block floor of the land Analogman
wrote, split by the seam itself (a line of broken heaps where the two lands were welded) with patches of ice that
never melts in its hollows; the last red rock as a wall along the left, grey block walls at the right and the top.
Our art (art/seam-1.png, Nano Banana Pro with the pass's eye, 7000, at 45 degrees down, projection 1000, 768x640) and
our map data (seam-1-data.json, made by author/seam-1-layout.py); the structure of the map (tile layout, TIMs,
lights, the day/night palettes derived at import) is MAYO04B's, read from the player's own disc at build time, with
the camera set here. Its wild Digimon are placed by the story (early-game.py).

    python3 seam-1.py OUT_DIR        writes OUT_DIR/SEAM01.MAP and SEAM01.TFS
"""
import json, os, sys
from mapbase import base_map, import_png, MOD, check_arrivals
from foreground_depth_b import apply as apply_foreground

DATA = os.path.join(MOD, 'maps', 'seam-1-data.json')
ART = os.path.join(MOD, 'art', 'seam-1.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('MAYO04B', *d['camera']); m.projection = d['projection']
    m.collision = list(d['collision']); m.warps = d['warps']
    check_arrivals(m, 'SEAM01')
    import_png('MAYO04B', ART, os.path.join(out, 'SEAM01.TFS'))
    apply_foreground(m, 'seam-1', os.path.join(out, 'SEAM01.TFS'))
    open(os.path.join(out, 'SEAM01.MAP'), 'wb').write(m.build())
    print(f'SEAM01: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
