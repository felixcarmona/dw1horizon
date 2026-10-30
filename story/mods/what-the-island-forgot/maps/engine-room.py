#!/usr/bin/env python3
"""The Engine Room (screen 300, files ENGN01), under the Ogre Fortress. Our art (art/engine-room.png) and our map data
(engine-room-data.json: the collision, the exits, the foreground pieces and the fire animation as sprite TIMs); the
structure of the map (camera, lights, tile layout) is OGRE03's, read from the player's own disc at build time.

    python3 engine-room.py OUT_DIR        writes OUT_DIR/ENGN01.MAP and ENGN01.TFS
"""
import json, os, sys
from mapbase import base_map, import_png, MOD

DATA = os.path.join(MOD, 'maps', 'engine-room-data.json')
ART = os.path.join(MOD, 'art', 'engine-room.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    m = base_map('OGRE03')
    d = json.load(open(DATA))
    m.collision = list(d['collision']); m.warps = d['warps']; m.sprites = d['sprites']; m.instances = d['instances']
    m.tims = [bytes(t) for t in d['tims']] + list(m.tims[len(d['tims']):])
    open(os.path.join(out, 'ENGN01.MAP'), 'wb').write(m.build())
    import_png('OGRE03', ART, os.path.join(out, 'ENGN01.TFS'))
    print(f'ENGN01: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
