#!/usr/bin/env python3
"""The lectern room (screen 308, files CRYP02): the chamber at the bottom of the Grey Lord's Crypt where Myotismon reads
the library (M9): the lectern with the open book, the books carried down from the library against the walls, the
relief of the winged skeletal dragon on the back wall, candles. Dead end: its only door, in the left wall, is the
corridor (307). Our art (art/lectern-room.png, Nano Banana Pro with CHKA01's camera: eye 6418 from the look-at point,
17 degrees down, projection 399, 640x512) and our map data (lectern-room-data.json, made by
author/lectern-room-layout.py: the floor segmented from the art, the lectern blocked, the door, CHKA01's lights); the
structure of the map (tile layout, TIMs) is LEOM01's (a 640x512 interior with 2 TIMs and one palette; CHKA01 itself has
no TIMs), read from the player's own disc at build time, with the camera set here.

    python3 lectern-room.py OUT_DIR        writes OUT_DIR/CRYP02.MAP and CRYP02.TFS
"""
import json, os, sys
from foreground_depth_a import apply as apply_foreground
from mapbase import base_map, import_png, MOD, check_arrivals

DATA = os.path.join(MOD, 'maps', 'lectern-room-data.json')
ART = os.path.join(MOD, 'art', 'lectern-room.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('LEOM01', *d['camera']); m.projection = d['projection']; m.lights = d['lights']
    m.collision = list(d['collision']); m.warps = d['warps']
    check_arrivals(m, 'CRYP02')
    import_png('LEOM01', ART, os.path.join(out, 'CRYP02.TFS'))
    apply_foreground(m, 'CRYP02', os.path.join(out, 'CRYP02.TFS'))
    open(os.path.join(out, 'CRYP02.MAP'), 'wb').write(m.build())
    print(f'CRYP02: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
