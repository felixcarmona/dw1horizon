#!/usr/bin/env python3
"""The fifth Seam road screen (screen 329, files SEAM07, the great weld): where the grey written land ends against the
orange sandstone of Overdell: a floor half grey circuit blocks with frost, half orange rock, joined along a ragged
diagonal lip of crushed blocks and rock with a gap in it; an opening in the right wall leads on (330). Our art
(art/seam-5.png, Nano Banana Pro with the pass's eye, 7000, at 45 degrees down, projection 1000, 768x640) and our map
data (seam-5-data.json, made by author/seam-5-layout.py); the structure of the map (tile layout, TIMs, lights, the
day/night palettes derived at import) is MAYO04B's, read from the player's own disc at build time, with the camera set
here. Its wild Digimon are placed by the story (early-game.py).

    python3 seam-5.py OUT_DIR        writes OUT_DIR/SEAM07.MAP and SEAM07.TFS
"""
import json, os, sys
from mapbase import base_map, import_png, MOD, check_arrivals
from foreground_depth_b import apply as apply_foreground

DATA = os.path.join(MOD, 'maps', 'seam-5-data.json')
ART = os.path.join(MOD, 'art', 'seam-5.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('MAYO04B', *d['camera']); m.projection = d['projection']
    m.collision = list(d['collision']); m.warps = d['warps']
    check_arrivals(m, 'SEAM07')
    import_png('MAYO04B', ART, os.path.join(out, 'SEAM07.TFS'))
    apply_foreground(m, 'seam-5', os.path.join(out, 'SEAM07.TFS'))
    open(os.path.join(out, 'SEAM07.MAP'), 'wb').write(m.build())
    print(f'SEAM07: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
