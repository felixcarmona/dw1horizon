#!/usr/bin/env python3
"""The fifth Overdell Pass screen (screen 334, files OVPS05, the standing stones): below the narrows the canyon widens
into a sandy floor with a grove of dead trees against the left wall and the first leaning standing stones of
Overdell's graveyard land, a plank sign on a shelf at the right; the sand runs from the top edge (333) to the bottom
edge (335). A tall screen (640x768). Our art (art/descent-5.png, Nano Banana Pro with the pass's eye, 7000, at 52
degrees down, projection 1000) and our map data (descent-5-data.json, made by author/descent-5-layout.py); the
structure of the map (tile layout, 2 TIMs, Overdell's lights, the day/night palettes derived at import) is DGHA01's,
read from the player's own disc at build time, with the camera set here. Its wild Digimon are placed by the story
(early-game.py).

    python3 descent-5.py OUT_DIR        writes OUT_DIR/OVPS05.MAP and OVPS05.TFS
"""
import json, os, sys
from mapbase import base_map, import_png, MOD, check_arrivals
from foreground_depth_b import apply as apply_foreground

DATA = os.path.join(MOD, 'maps', 'descent-5-data.json')
ART = os.path.join(MOD, 'art', 'descent-5.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('DGHA01', *d['camera']); m.projection = d['projection']
    m.collision = list(d['collision']); m.warps = d['warps']
    check_arrivals(m, 'OVPS05')
    import_png('DGHA01', ART, os.path.join(out, 'OVPS05.TFS'))
    apply_foreground(m, 'descent-5', os.path.join(out, 'OVPS05.TFS'))
    open(os.path.join(out, 'OVPS05.MAP'), 'wb').write(m.build())
    print(f'OVPS05: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
