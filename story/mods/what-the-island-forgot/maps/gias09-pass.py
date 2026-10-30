#!/usr/bin/env python3
"""Gear Savanna, Leomon's patrol post (GIAS09, screen 78): the way over the hill's crest, left of the gate, into the
Seam Pass (its first screen, 317).

Nothing is painted here: the grass of the hilltop already reaches the crest, so the background stays the player's
own (copied as it is). Exit 1 of the map (unused by the game) leads to the pass; the two rows of tiles at the crest,
left of the gate and away from Leomon's event tiles, trigger it; the arrival from the pass is four rows down the
hill, facing the savanna.

    python3 gias09-pass.py OUT_DIR        writes OUT_DIR/GIAS09.MAP and GIAS09.TFS (they replace the disc's)
"""
import os, shutil, sys
from mapbase import extracted, Cam, dwmap, MOD, check_arrivals
from maps import reach

EXIT_TILES = [(tx, tz) for tz in (16, 17) for tx in range(32, 39)]   # the crest, left of the gate (cols 39-41 carry Leomon's event tiles)
SPAWN = (35, 21)                                        # tile of the arrival from the pass
ROTATION = 2048                                         # facing -Z: down the hill, into the savanna
WARP = 1
TARGET = (317, 0)                                       # the first Iron Hills screen, its bottom edge


def main(out):
    os.makedirs(out, exist_ok=True)
    src = extracted('GIAS09')
    shutil.copyfile(src + '.TFS', os.path.join(out, 'GIAS09.TFS'))
    m = dwmap.MapFile(open(src + '.MAP', 'rb').read()); cam = Cam(m)
    col = list(m.collision)
    for tx, tz in EXIT_TILES: col[tz * 100 + tx] = 110 + WARP
    m.collision = col
    sx, sz = (SPAWN[0] - 50) * 100 + 50, (49 - SPAWN[1]) * 100 + 50
    m.warps[WARP].update({'x': sx, 'z': sz, 'rotation': ROTATION, 'targetMap': TARGET[0], 'targetExit': TARGET[1]})
    check_arrivals(m, 'GIAS09')
    open(os.path.join(out, 'GIAS09.MAP'), 'wb').write(m.build())
    R = reach.from_spawn_coordinates(m, starts=[(m.warps[0]['x'], m.warps[0]['z'])])          # from the arrival from GIAS07
    if (sx, sz) not in R: sys.exit('the arrival from the pass is not reachable')
    if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in EXIT_TILES for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
        sys.exit('the crest is not reachable')
    print(f'GIAS09: crest exit tiles {len(EXIT_TILES)}, spawn px {cam.pixel(sx, sz)}, reach {len(R)}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
