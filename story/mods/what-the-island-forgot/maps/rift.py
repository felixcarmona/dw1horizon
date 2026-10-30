#!/usr/bin/env python3
"""The Rift (screen 301, files RIFT01): the old floor of the Great Canyon under the plateau, with the hundred-year-old
human camp. Our art (art/rift.png, Nano Banana Pro with GCAN07's camera: eye 7000 from the look-at point, 61 degrees
down) and our map data (rift-data.json, made by author/rift-layout.py from the art: the collision, the exits, the
foreground pieces); the structure of the map (lights, tile layout) is OGRE03's, read from the player's own disc at
build time, with the camera set here.

    python3 rift.py OUT_DIR        writes OUT_DIR/RIFT01.MAP and RIFT01.TFS
"""
import json, os, sys
from foreground_depth_a import apply as apply_foreground
from mapbase import base_map, import_png, MOD

DATA = os.path.join(MOD, 'maps', 'rift-data.json')
ART = os.path.join(MOD, 'art', 'rift.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('OGRE03', *d['camera'])
    m.collision = list(d['collision']); m.warps = d['warps']; m.sprites = d['sprites']; m.instances = d['instances']
    m.tims = [bytes(t) for t in d['tims']] + list(m.tims[len(d['tims']):])
    import_png('OGRE03', ART, os.path.join(out, 'RIFT01.TFS'))
    apply_foreground(m, 'RIFT01', os.path.join(out, 'RIFT01.TFS'))
    open(os.path.join(out, 'RIFT01.MAP'), 'wb').write(m.build())
    print(f'RIFT01: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
