#!/usr/bin/env python3
"""The third Seam screen on the road (screen 326, files SEAM04, CAMP 2): north of the ice shelf the floor widens into
a square where the hundred-year-old human camp stands against the left wall (a collapsed plank hut, a rusted
generator, crates and a barrel), the seam's heaps run down the right, and an opening in the back wall leads on. Our
art (art/seam-3.png, Nano Banana Pro with the pass's eye, 7000, at 45 degrees down, projection 1000, 768x640) and our
map data (seam-3-data.json, made by author/seam-3-layout.py); the structure of the map (tile layout, TIMs, lights,
the day/night palettes derived at import) is MAYO04B's, read from the player's own disc at build time, with the
camera set here. Its wild Digimon are placed by the story (early-game.py); the camp's notebook is story work.

    python3 seam-3.py OUT_DIR        writes OUT_DIR/SEAM04.MAP and SEAM04.TFS
"""
import json, os, sys
from mapbase import base_map, import_png, MOD, check_arrivals
from foreground_depth_b import apply as apply_foreground

DATA = os.path.join(MOD, 'maps', 'seam-3-data.json')
ART = os.path.join(MOD, 'art', 'seam-3.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('MAYO04B', *d['camera']); m.projection = d['projection']
    m.collision = list(d['collision']); m.warps = d['warps']
    check_arrivals(m, 'SEAM04')
    import_png('MAYO04B', ART, os.path.join(out, 'SEAM04.TFS'))
    apply_foreground(m, 'seam-3', os.path.join(out, 'SEAM04.TFS'))
    open(os.path.join(out, 'SEAM04.MAP'), 'wb').write(m.build())
    print(f'SEAM04: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
