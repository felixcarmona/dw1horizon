#!/usr/bin/env python3
"""Coela Point (MAYO05, screen 5): the stone steps cut into the west cliff, the way up to the Root Clearing (screen
314) and the other end of the loop that starts at Native Forest's big field.

The steps are our own picture (art/mayo05-path.png, with transparency; made with Nano Banana on a 5x enlargement of
the cliff's foot and cut out of its answer: only the staircase, feathered). They are laid over the player's own MAYO05
background at build time; nothing of the game's background is in this folder. Exit 1 of the map (unused by the game)
leads to the clearing; the tiles at the foot of the steps (two in the rock, three on the sand) trigger it; the arrival
from the clearing is three tiles out on the sand, facing east.

    python3 mayo05-path.py OUT_DIR        writes OUT_DIR/MAYO05.MAP and MAYO05.TFS (they replace the disc's)
"""
import os, sys
from mapbase import extracted, Cam, dwmap, MOD, check_arrivals, bg
from maps import reach

PATH_PNG = os.path.join(MOD, 'art', 'mayo05-path.png')
PATH_AT = (120, 120)                                    # top-left of the picture on the 640x384 background
EXIT_TILES = [(tx, tz) for tz in (66, 67, 68) for tx in (41, 42)]   # the foot of the steps: the rock's edge and the sand beside it
SPAWN = (45, 67)                                        # tile of the arrival from the clearing
ROTATION = 1024                                         # facing +X: onto the beach
TARGET = (314, 1)                                       # the Root Clearing's south-east path


def main(out):
    os.makedirs(out, exist_ok=True)
    src = extracted('MAYO05')
    bg([src + '.MAP', src + '.TFS', os.path.join(out, 'MAYO05.TFS'),
        '--paste', PATH_PNG, str(PATH_AT[0]), str(PATH_AT[1])])
    m = dwmap.MapFile(open(src + '.MAP', 'rb').read()); cam = Cam(m)
    col = list(m.collision)
    for tx, tz in EXIT_TILES: col[tz * 100 + tx] = 111
    m.collision = col
    sx, sz = (SPAWN[0] - 50) * 100 + 50, (49 - SPAWN[1]) * 100 + 50
    m.warps[1].update({'x': sx, 'z': sz, 'rotation': ROTATION, 'targetMap': TARGET[0], 'targetExit': TARGET[1]})
    check_arrivals(m, 'MAYO05')
    open(os.path.join(out, 'MAYO05.MAP'), 'wb').write(m.build())
    R = reach.from_spawn_coordinates(m, starts=[(m.warps[0]['x'], m.warps[0]['z'])])          # from the arrival from MAYO04B
    if (sx, sz) not in R: sys.exit('the arrival from the clearing is not reachable')
    if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in EXIT_TILES for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
        sys.exit('the steps are not reachable')
    print(f'MAYO05: steps exit tiles {len(EXIT_TILES)}, spawn px {cam.pixel(sx, sz)}, reach {len(R)}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
