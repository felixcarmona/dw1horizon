#!/usr/bin/env python3
"""The fourth Seam road screen (screen 327, files SEAM05, the gallery): past the camp a long gallery of grey circuit
blocks, the seam's rubble piled against the left wall, and a broad block stair on the right climbing to the doorway of
the watchtower (328); the road goes on through the opening in the back wall (329). Our art (art/seam-4.png, Nano
Banana Pro with the pass's eye, 7000, at 45 degrees down, projection 1000, 768x640) and our map data (seam-4-data.json,
made by author/seam-4-layout.py); the structure of the map (tile layout, TIMs, lights, the day/night palettes derived
at import) is MAYO04B's, read from the player's own disc at build time, with the camera set here. Its wild Digimon are
placed by the story (early-game.py).

    python3 seam-4.py OUT_DIR        writes OUT_DIR/SEAM05.MAP and SEAM05.TFS
"""
import json, os, sys
from mapbase import base_map, import_png, MOD, check_arrivals
from foreground_depth_b import apply as apply_foreground

DATA = os.path.join(MOD, 'maps', 'seam-4-data.json')
ART = os.path.join(MOD, 'art', 'seam-4.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('MAYO04B', *d['camera']); m.projection = d['projection']
    m.collision = list(d['collision']); m.warps = d['warps']
    check_arrivals(m, 'SEAM05')
    import_png('MAYO04B', ART, os.path.join(out, 'SEAM05.TFS'))
    apply_foreground(m, 'seam-4', os.path.join(out, 'SEAM05.TFS'))
    open(os.path.join(out, 'SEAM05.MAP'), 'wb').write(m.build())
    print(f'SEAM05: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
