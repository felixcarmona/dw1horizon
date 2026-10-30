#!/usr/bin/env python3
"""The Second Chamber (screen 304, files SHRN01): the deeper, older chamber of Leomon's ancestors' shrine, behind the
hall of the lion face (LEOM01, screen 113): one carved stone platform over the mist, the back wall with a lion head at
each end and the blank panel between them (the mural goes there), the second stone on its pedestal at the foot of the
wall, and the stone walkway back to the hall off the right edge. Our art (art/second-chamber.png, Nano Banana Pro
with LEOM01's camera: eye 4320 from the look-at point, 60 degrees down) and our map data (second-chamber-data.json,
made by author/second-chamber-layout.py: the platform segmented from the art, the exit); the structure of the map
(lights, tile layout) is LEOM01's, read from the player's own disc at build time, with the camera set here.

    python3 second-chamber.py OUT_DIR        writes OUT_DIR/SHRN01.MAP and SHRN01.TFS
"""
import json, os, sys
from foreground_depth_a import apply as apply_foreground
from mapbase import base_map, import_png, MOD

DATA = os.path.join(MOD, 'maps', 'second-chamber-data.json')
ART = os.path.join(MOD, 'art', 'second-chamber.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('LEOM01', *d['camera']); m.projection = d['projection']
    m.collision = list(d['collision']); m.warps = d['warps']
    import_png('LEOM01', ART, os.path.join(out, 'SHRN01.TFS'))
    apply_foreground(m, 'SHRN01', os.path.join(out, 'SHRN01.TFS'))
    open(os.path.join(out, 'SHRN01.MAP'), 'wb').write(m.build())
    print(f'SHRN01: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
