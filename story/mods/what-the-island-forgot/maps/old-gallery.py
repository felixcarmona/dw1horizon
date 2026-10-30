#!/usr/bin/env python3
"""The Old Gallery (screen 315, files GALL01): the hundred-year-old human mine gallery under Drimogemon's residence
in the Drill Tunnel (TUNN04), down the stair at the bottom right of his room: timber props, a rail with a rusted ore
cart, a lantern, a pick and a bucket, and a rock fall at the end with the island's old carved stone in it. Dead end.
Our art (art/old-gallery.png, Nano Banana Pro at TUNN04's family of camera: eye 6500 from the look-at point, 42
degrees down, projection 772, 640x512) and our map data (old-gallery-data.json, made by author/old-gallery-layout.py:
the floor segmented from the art, the exit, the arrival); the structure of the map (tile layout, the TIM, the lights,
no day/night) is TUNN04's, read from the player's own disc at build time, with the camera set here.

    python3 old-gallery.py OUT_DIR        writes OUT_DIR/GALL01.MAP and GALL01.TFS
"""
import json, os, sys
from foreground_depth_a2 import apply as apply_foreground
from mapbase import base_map, import_png, MOD, check_arrivals

DATA = os.path.join(MOD, 'maps', 'old-gallery-data.json')
ART = os.path.join(MOD, 'art', 'old-gallery.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('TUNN04', *d['camera']); m.projection = d['projection']
    m.collision = list(d['collision']); m.warps = d['warps']
    check_arrivals(m, 'GALL01')
    import_png('TUNN04', ART, os.path.join(out, 'GALL01.TFS'))
    apply_foreground(m, 'GALL01', os.path.join(out, 'GALL01.TFS'))
    open(os.path.join(out, 'GALL01.MAP'), 'wb').write(m.build())
    print(f'GALL01: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
