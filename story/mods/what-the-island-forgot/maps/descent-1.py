#!/usr/bin/env python3
"""The mouth of the Seam on the Overdell side (screen 330, files OVPS01, zone 3's first screen): a canyon of orange
sandstone whose walls still hold the last grey circuit blocks like teeth, a dead tree on a ledge, a fallen block by
the path, the doorway of the weld hall at the top; the path runs down to 331. A tall screen (640x768). Our art
(art/descent-1.png, Nano Banana Pro with the pass's eye, 7000, at 48 degrees down, projection 927) and our map data
(descent-1-data.json, made by author/descent-1-layout.py); the structure of the map (tile layout, 2 TIMs, Overdell's
lights, the day/night palettes derived at import) is DGHA01's, read from the player's own disc at build time, with the
camera set here. Its wild Digimon are placed by the story (early-game.py).

    python3 descent-1.py OUT_DIR        writes OUT_DIR/OVPS01.MAP and OVPS01.TFS
"""
import json, os, sys
from mapbase import base_map, import_png, MOD, check_arrivals
from foreground_depth_b import apply as apply_foreground

DATA = os.path.join(MOD, 'maps', 'descent-1-data.json')
ART = os.path.join(MOD, 'art', 'descent-1.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('DGHA01', *d['camera']); m.projection = d['projection']
    m.collision = list(d['collision']); m.warps = d['warps']
    check_arrivals(m, 'OVPS01')
    import_png('DGHA01', ART, os.path.join(out, 'OVPS01.TFS'))
    apply_foreground(m, 'descent-1', os.path.join(out, 'OVPS01.TFS'))
    open(os.path.join(out, 'OVPS01.MAP'), 'wb').write(m.build())
    print(f'OVPS01: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
