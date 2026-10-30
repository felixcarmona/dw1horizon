#!/usr/bin/env python3
"""The sixth Overdell Pass screen (screen 335, files OVPS06, the last descent): the canyon floor becomes a broad ramp of
orange rock going down to Overdell, a low cave mouth in the left wall (the ossuary, 336), leaning grave stones, a
plank sign on a shelf at the right; the ramp runs from the top edge (334) to the bottom edge (Overdell's western
screen, DGHA01). A tall screen (640x768). Our art (art/descent-6.png, Nano Banana Pro with the pass's eye, 7000, at
52 degrees down, projection 1000) and our map data (descent-6-data.json, made by author/descent-6-layout.py); the
structure of the map (tile layout, 2 TIMs, Overdell's lights, the day/night palettes derived at import) is DGHA01's,
read from the player's own disc at build time, with the camera set here. Its wild Digimon are placed by the story
(early-game.py).

    python3 descent-6.py OUT_DIR        writes OUT_DIR/OVPS06.MAP and OVPS06.TFS
"""
import json, os, sys
from mapbase import base_map, import_png, MOD, check_arrivals
from foreground import apply as apply_foreground

DATA = os.path.join(MOD, 'maps', 'descent-6-data.json')
ART = os.path.join(MOD, 'art', 'descent-6.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('DGHA01', *d['camera']); m.projection = d['projection']
    m.collision = list(d['collision']); m.warps = d['warps']
    check_arrivals(m, 'OVPS06')
    tfs = os.path.join(out, 'OVPS06.TFS')
    import_png('DGHA01', ART, tfs)
    apply_foreground(m, 'descent-6', tfs)
    open(os.path.join(out, 'OVPS06.MAP'), 'wb').write(m.build())
    print(f'OVPS06: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
