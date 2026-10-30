#!/usr/bin/env python3
"""The Descent (screen 303, files DESC01): the inside of the crack of the Great Canyon Bottom Area, a narrow ledge of
layered sandstone winding down in an S between the rock walls, from the rock steps climbing towards a faint light at
the top (the way up to the canyon; the crack itself is not seen) to the green-lit opening at the bottom, where the
Rift's ramp begins. Our art (art/descent.png, Nano Banana Pro with GCAN07's camera: eye 7000 from the look-at point,
61 degrees down, a 640x768 portrait) and our map data (descent-data.json, made by author/descent-layout.py: the ledge
segmented from the art, the exits, the rock shelf under the steps as a foreground piece); the structure of the map (lights, tile layout) is GCAN01's (a 640x768 canyon
screen), read from the player's own disc at build time, with the camera set here.

    python3 descent.py OUT_DIR        writes OUT_DIR/DESC01.MAP and DESC01.TFS
"""
import json, os, sys
from foreground_depth_a import apply as apply_foreground
from mapbase import base_map, import_png, MOD

DATA = os.path.join(MOD, 'maps', 'descent-data.json')
ART = os.path.join(MOD, 'art', 'descent.png')
WARP, STEP = 0, 0                                       # the steps up to the canyon: step trigger 0 (descent story: 42 or 368)


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('GCAN01', *d['camera']); m.projection = d['projection']
    m.collision = [51 + STEP if v == 110 + WARP else v for v in d['collision']]; m.warps = d['warps']   # the steps up: a step trigger
    if d.get('sprites'):                                            # the foreground pieces (the rock shelf under the steps)
        m.sprites = d['sprites']; m.instances = d['instances']
        m.tims = [bytes(t) for t in d['tims']] + list(m.tims[len(d['tims']):])
    import_png('GCAN01', ART, os.path.join(out, 'DESC01.TFS'))
    apply_foreground(m, 'DESC01', os.path.join(out, 'DESC01.TFS'))
    open(os.path.join(out, 'DESC01.MAP'), 'wb').write(m.build())
    print(f'DESC01: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
