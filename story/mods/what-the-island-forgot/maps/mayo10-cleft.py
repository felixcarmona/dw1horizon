#!/usr/bin/env python3
"""Dragon Eye Lake, the sandy shore (MAYO10, screen 8): the cleft with rock steps in the cliff at the west end of the
strip, the way up to the Lake Terrace (screen 316).

The cleft is our own picture (art/mayo10-cleft.png, with transparency; made with Nano Banana on a 5x enlargement of
the cliff's foot and cut out of its answer: only the notch and its steps, feathered). It is laid over the player's own
MAYO10 background at build time; nothing of the game's background is in this folder. Exit 1 of the map (unused by the
game) leads to the terrace; the tiles at the foot of the cleft (the sand against the rock and the rock's first
column) trigger it; the arrival from the terrace is three tiles out on the sand, facing east.

    python3 mayo10-cleft.py OUT_DIR        writes OUT_DIR/MAYO10.MAP and MAYO10.TFS (they replace the disc's)
"""
import os, sys
from mapbase import extracted, Cam, dwmap, MOD, check_arrivals, bg
from maps import reach

CLEFT_PNG = os.path.join(MOD, 'art', 'mayo10-cleft.png')
CLEFT_AT = (20, 60)                                     # top-left of the picture on the 768x640 background
EXIT_BOX = (104, 170, 168, 210)                         # pixels: the foot of the cleft, the grass tufts and the first free column of sand (the sand's tiles start at u 163)
SPAWN_PX = (205, 190)                                   # the arrival from the terrace, on the sand, three tiles from the exit
ROTATION = 1024                                         # facing +X: along the strip
TARGET = (316, 0)                                       # the Lake Terrace's steps


def main(out):
    os.makedirs(out, exist_ok=True)
    src = extracted('MAYO10')
    bg([src + '.MAP', src + '.TFS', os.path.join(out, 'MAYO10.TFS'),
        '--paste', CLEFT_PNG, str(CLEFT_AT[0]), str(CLEFT_AT[1])])
    m = dwmap.MapFile(open(src + '.MAP', 'rb').read()); cam = Cam(m)
    col = list(m.collision); exit_tiles = []; spawn = None; best = None
    for tx, tz, u, v in cam.tiles():
        if u is None: continue
        if EXIT_BOX[0] <= u <= EXIT_BOX[2] and EXIT_BOX[1] <= v <= EXIT_BOX[3]:
            col[tz * 100 + tx] = 111; exit_tiles.append((tx, tz))
        d = (u - SPAWN_PX[0]) ** 2 + (v - SPAWN_PX[1]) ** 2
        if not m.collision[tz * 100 + tx] & 0x80 and (best is None or d < best): best, spawn = d, (tx, tz)
    m.collision = col
    sx, sz = (spawn[0] - 50) * 100 + 50, (49 - spawn[1]) * 100 + 50
    m.warps[1].update({'x': sx, 'z': sz, 'rotation': ROTATION, 'targetMap': TARGET[0], 'targetExit': TARGET[1]})
    check_arrivals(m, 'MAYO10')
    open(os.path.join(out, 'MAYO10.MAP'), 'wb').write(m.build())
    R = reach.from_spawn_coordinates(m, starts=[(m.warps[0]['x'], m.warps[0]['z'])])          # from the arrival from MAYO01
    if (sx, sz) not in R: sys.exit('the arrival from the terrace is not reachable')
    if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in exit_tiles for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
        sys.exit('the cleft is not reachable')
    print(f'MAYO10: cleft exit tiles {len(exit_tiles)}, spawn tile {spawn} px {cam.pixel(sx, sz)}, reach {len(R)}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
