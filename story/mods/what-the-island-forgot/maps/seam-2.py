#!/usr/bin/env python3
"""The second Seam screen (screen 324, files SEAM02, the ice shelf): a wide floor of grey circuit blocks with a round
frozen pool at the left, the seam's ridge of broken heaps along the right wall, and the iron gate of the hunters'
kennel in the top-left wall. Our art (art/seam-2.png, Nano Banana Pro with the pass's eye, 7000, at 45 degrees down,
projection 1000, 768x640) and our map data (seam-2-data.json, made by author/seam-2-layout.py); the structure of the
map (tile layout, TIMs, lights, the day/night palettes derived at import) is MAYO04B's, read from the player's own
disc at build time, with the camera set here. Its wild Digimon are placed by the story (early-game.py).

    python3 seam-2.py OUT_DIR        writes OUT_DIR/SEAM02.MAP and SEAM02.TFS
"""
import json, os, sys
from mapbase import base_map, import_png, MOD, check_arrivals
from foreground_depth_b import apply as apply_foreground

DATA = os.path.join(MOD, 'maps', 'seam-2-data.json')
ART = os.path.join(MOD, 'art', 'seam-2.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('MAYO04B', *d['camera']); m.projection = d['projection']
    m.collision = list(d['collision']); m.warps = d['warps']
    check_arrivals(m, 'SEAM02')
    import_png('MAYO04B', ART, os.path.join(out, 'SEAM02.TFS'))
    apply_foreground(m, 'seam-2', os.path.join(out, 'SEAM02.TFS'))
    open(os.path.join(out, 'SEAM02.MAP'), 'wb').write(m.build())
    print(f'SEAM02: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
