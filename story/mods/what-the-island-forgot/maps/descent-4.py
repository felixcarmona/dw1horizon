#!/usr/bin/env python3
"""The fourth Overdell Pass screen (screen 333, files OVPS04, the narrows): below the terraces the canyon pinches into a
slot of packed sand between close high walls, a fallen slab bridging it overhead, dead trees on a shelf at the left,
valves grown into the rock; the sand runs from the top edge (332) to the bottom edge (334). A tall screen (640x768).
Our art (art/descent-4.png, Nano Banana Pro with the pass's eye, 7000, at 52 degrees down, projection 1000) and our map
data (descent-4-data.json, made by author/descent-4-layout.py); the structure of the map (tile layout, 2 TIMs,
Overdell's lights, the day/night palettes derived at import) is DGHA01's, read from the player's own disc at build
time, with the camera set here. Its wild Digimon are placed by the story (early-game.py).

    python3 descent-4.py OUT_DIR        writes OUT_DIR/OVPS04.MAP and OVPS04.TFS
"""
import json, os, sys
from mapbase import base_map, import_png, MOD, check_arrivals
from foreground_depth_b import apply as apply_foreground

DATA = os.path.join(MOD, 'maps', 'descent-4-data.json')
ART = os.path.join(MOD, 'art', 'descent-4.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('DGHA01', *d['camera']); m.projection = d['projection']
    m.collision = list(d['collision']); m.warps = d['warps']
    check_arrivals(m, 'OVPS04')
    import_png('DGHA01', ART, os.path.join(out, 'OVPS04.TFS'))
    apply_foreground(m, 'descent-4', os.path.join(out, 'OVPS04.TFS'))
    open(os.path.join(out, 'OVPS04.MAP'), 'wb').write(m.build())
    print(f'OVPS04: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
