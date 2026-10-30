#!/usr/bin/env python3
"""Leomon Ancestor's Cave, the hall of the lion face (LEOM01, screen 113): the stone walkway off the west edge of the
platform that leads to the Second Chamber (screen 304).

The walkway is our own picture (art/leom01-walkway.png, with transparency; made with Nano Banana on a 5x enlargement
of the platform's west edge and cut out of its answer: only the walkway's pixels). It is laid over the player's own
LEOM01 background at build time; nothing of the game's background is in this folder. Exit 1 of the map (unused by the
game) leads to the Second Chamber, and the tiles of the walkway and of the platform's edge beside it trigger it; the
arrival from the chamber is three tiles inside the platform, facing the hall.

    python3 leom01-passage.py OUT_DIR        writes OUT_DIR/LEOM01.MAP and LEOM01.TFS (they replace the disc's)
"""
import os, sys
from mapbase import extracted, Cam, reachable, dwmap, MOD, bg

WALKWAY_PNG = os.path.join(MOD, 'art', 'leom01-walkway.png')
WALKWAY_AT = (0, 334)                                   # top-left of the picture on the 640x512 background
WALKWAY_BOX = (0, 340, 56, 392)                         # tiles whose centre pixel falls here lead to the chamber
EDGE_TILES = [(tx, tz) for tz in range(28, 33) for tx in (26, 27)]   # the platform's westmost free tiles, too
SPAWN = (30, 30)                                        # tile of the arrival from the chamber
ROTATION = 1024                                         # facing +X: into the hall
TARGET = (304, 0)                                       # the Second Chamber


def main(out):
    os.makedirs(out, exist_ok=True)
    src = extracted('LEOM01')
    # the background: the walkway over the player's own TFS (the palette is kept: unchanged pixels keep their index)
    bg([src + '.MAP', src + '.TFS', os.path.join(out, 'LEOM01.TFS'),
        '--paste', WALKWAY_PNG, str(WALKWAY_AT[0]), str(WALKWAY_AT[1])])
    # the map: exit 1 leads to the chamber; the walkway's tiles and the edge beside it trigger it
    m = dwmap.MapFile(open(src + '.MAP', 'rb').read()); cam = Cam(m)
    x0, y0, x1, y1 = WALKWAY_BOX; col = list(m.collision); n = 0
    for tx, tz, u, v in cam.tiles():
        if u is None: continue
        if (x0 <= u <= x1 and y0 <= v <= y1) or ((tx, tz) in EDGE_TILES and col[tz * 100 + tx] == 0):
            col[tz * 100 + tx] = 111; n += 1
    m.collision = col
    sx, sz = (SPAWN[0] - 50) * 100 + 50, (49 - SPAWN[1]) * 100 + 50
    m.warps[1].update({'x': sx, 'z': sz, 'rotation': ROTATION, 'targetMap': TARGET[0], 'targetExit': TARGET[1]})
    open(os.path.join(out, 'LEOM01.MAP'), 'wb').write(m.build())
    R = reachable(m)
    if (round(sx / 10) * 10, round(sz / 10) * 10) not in R: sys.exit('the arrival from the chamber is not reachable')
    print(f'LEOM01: walkway exit tiles {n}, spawn px {cam.pixel(sx, sz)}, reach {len(R)}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
