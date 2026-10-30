#!/usr/bin/env python3
"""The hunters' kennel (screen 325, files SEAM03): the dead-end chamber behind the iron gate of the ice shelf (324):
three empty cages of light along the back wall (the story puts the erased Digimon in them), a heap of bones and
collars in the corner, frost. Our art (art/kennel.png, Nano Banana Pro with the pass's eye, 7000, at 45 degrees down,
projection 1000, 768x640) and our map data (kennel-data.json, made by author/kennel-layout.py); the structure of the
map (tile layout, TIMs, lights, the day/night palettes derived at import) is MAYO04B's, read from the player's own
disc at build time, with the camera set here. Its guard is placed by the story (early-game.py).

    python3 kennel.py OUT_DIR        writes OUT_DIR/SEAM03.MAP and SEAM03.TFS
"""
import json, os, sys
from mapbase import base_map, import_png, MOD, check_arrivals
from foreground_depth_b import apply as apply_foreground

DATA = os.path.join(MOD, 'maps', 'kennel-data.json')
ART = os.path.join(MOD, 'art', 'kennel.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('MAYO04B', *d['camera']); m.projection = d['projection']
    m.collision = list(d['collision']); m.warps = d['warps']
    check_arrivals(m, 'SEAM03')
    import_png('MAYO04B', ART, os.path.join(out, 'SEAM03.TFS'))
    apply_foreground(m, 'kennel', os.path.join(out, 'SEAM03.TFS'))
    open(os.path.join(out, 'SEAM03.MAP'), 'wb').write(m.build())
    print(f'SEAM03: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
