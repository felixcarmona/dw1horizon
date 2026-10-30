#!/usr/bin/env python3
"""The watchtower (screen 328, files SEAM06): the dead-end room at the top of the gallery's stair (327), where
Saberdramon watches the pass for Analogman: a round dais with a cracked lens on a tripod, bone perches with black
feathers on the side walls, a slit window in the back wall. Our art (art/watchtower.png, Nano Banana Pro with the
pass's eye, 7000, at 45 degrees down, projection 1000, 768x640) and our map data (watchtower-data.json, made by
author/watchtower-layout.py); the structure of the map (tile layout, TIMs, lights, the day/night palettes derived at
import) is MAYO04B's, read from the player's own disc at build time, with the camera set here. Saberdramon and the
scene are story work: the room is empty until then.

    python3 watchtower.py OUT_DIR        writes OUT_DIR/SEAM06.MAP and SEAM06.TFS
"""
import json, os, sys
from mapbase import base_map, import_png, MOD, check_arrivals
from foreground_depth_b import apply as apply_foreground

DATA = os.path.join(MOD, 'maps', 'watchtower-data.json')
ART = os.path.join(MOD, 'art', 'watchtower.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('MAYO04B', *d['camera']); m.projection = d['projection']
    m.collision = list(d['collision']); m.warps = d['warps']
    check_arrivals(m, 'SEAM06')
    import_png('MAYO04B', ART, os.path.join(out, 'SEAM06.TFS'))
    apply_foreground(m, 'watchtower', os.path.join(out, 'SEAM06.TFS'))
    open(os.path.join(out, 'SEAM06.MAP'), 'wb').write(m.build())
    print(f'SEAM06: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
