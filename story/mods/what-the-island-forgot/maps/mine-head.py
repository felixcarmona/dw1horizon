#!/usr/bin/env python3
"""The Mine Head (screen 337, files MINE01): the first screen of the Galleries arc, the head of the human mine under the
Drill Tunnel: a wide cavern where four galleries meet, a rail turntable, the shaft pit with its wrecked lift cage, the
entry gallery from the Old Gallery's rock fall (315) at the bottom edge, the north (338), west (341) and east (344)
galleries at the other edges. A wide screen (896x640). Our art (art/mine-head.png, Nano Banana Pro with the Drill
Tunnel's eye, 6500, at 42 degrees down, projection 1081) and our map data (mine-head-data.json, made by
author/mine-head-layout.py); the structure of the map (tile layout, 1 TIM, the Drill Tunnel's lights, no day/night) is
TUNN02's, read from the player's own disc at build time, with the camera set here. Its wild Digimon are placed by the
story (early-game.py).

    python3 mine-head.py OUT_DIR        writes OUT_DIR/MINE01.MAP and MINE01.TFS
"""
import json, os, sys
from mapbase import base_map, import_png, MOD, check_arrivals
from foreground import apply as apply_foreground

DATA = os.path.join(MOD, 'maps', 'mine-head-data.json')
ART = os.path.join(MOD, 'art', 'mine-head.png')


def main(out):
    os.makedirs(out, exist_ok=True)
    d = json.load(open(DATA))
    m = base_map('TUNN02', *d['camera']); m.projection = d['projection']
    m.collision = list(d['collision']); m.warps = d['warps']
    check_arrivals(m, 'MINE01')
    tfs = os.path.join(out, 'MINE01.TFS')
    import_png('TUNN02', ART, tfs)
    apply_foreground(m, 'mine-head', tfs)
    open(os.path.join(out, 'MINE01.MAP'), 'wb').write(m.build())
    print(f'MINE01: free tiles {m.collision.count(0)}, exits {[(w["targetMap"], w["targetExit"]) for w in m.warps if w["targetMap"] != -1]}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
