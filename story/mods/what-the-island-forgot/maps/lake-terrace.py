#!/usr/bin/env python3
"""The Lake Terrace (screen 316, files LAKE01): a natural rock terrace above Dragon Eye Lake, up a cleft at the west
end of the sandy shore (MAYO10), with the lake's old water line written in the cliff behind it as a band of fossil
shells. Dead end. Our art (art/lake-terrace.png, Nano Banana Pro at eye 7000 from the look-at point, 45 degrees down,
projection 927, 768x640) and our map data (lake-terrace-data.json, made by author/lake-terrace-layout.py: the terrace
traced on the art, the steps, the exit, the arrival); the structure of the map (tile layout, TIMs, lights, the
day/night palettes derived at import) is MAYO04B's, read from the player's own disc at build time, with the camera
set here.

    python3 lake-terrace.py OUT_DIR        writes OUT_DIR/LAKE01.MAP and LAKE01.TFS
"""
import json, os, sys
from mapbase import base_map, import_png, MOD, check_arrivals

DATA = os.path.join(MOD, 'maps', 'lake-terrace-data.json')
ART = os.path.join(MOD, 'art', 'lake-terrace.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('MAYO04B', *d['camera']); m.projection = d['projection']
    m.collision = list(d['collision']); m.warps = d['warps']
    check_arrivals(m, 'LAKE01')
    open(os.path.join(out, 'LAKE01.MAP'), 'wb').write(m.build())
    import_png('MAYO04B', ART, os.path.join(out, 'LAKE01.TFS'))
    print(f'LAKE01: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
