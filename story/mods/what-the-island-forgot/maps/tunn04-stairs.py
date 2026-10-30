#!/usr/bin/env python3
"""Drill Tunnel, Drimogemon's residence (TUNN04, screen 27): the stair at the bottom right of the room, which today
only goes down into the dark, now leads to the Old Gallery (screen 315).

Nothing is painted here: the stair and the darkness below it are already in the game's picture, so the background
stays the player's own (copied as it is). Exit 1 of the map (unused by the game) leads to the gallery; the tiles along
the dark edge of the stair (the first two rows of the pit, blocked today) trigger it; the arrival from the gallery is
on the lit steps three tiles up, facing the room.

    python3 tunn04-stairs.py OUT_DIR        writes OUT_DIR/TUNN04.MAP and TUNN04.TFS (they replace the disc's)
"""
import os, shutil, sys
from mapbase import extracted, Cam, dwmap, MOD, check_arrivals
from maps import reach

EXIT_TILES = [(67, 67), (68, 67), (65, 68), (66, 68), (64, 69), (65, 69), (63, 70), (64, 70), (63, 71), (64, 71)]
SPAWN = (61, 67)                                        # tile of the arrival from the gallery, on the steps
ROTATION = 3584                                         # facing -X +Z: up the stair, into the room
WARP = 1
TARGET = (315, 0)                                       # the Old Gallery's stair foot


def main(out):
    os.makedirs(out, exist_ok=True)
    src = extracted('TUNN04')
    shutil.copyfile(src + '.TFS', os.path.join(out, 'TUNN04.TFS'))
    m = dwmap.MapFile(open(src + '.MAP', 'rb').read()); cam = Cam(m)
    col = list(m.collision)
    for tx, tz in EXIT_TILES: col[tz * 100 + tx] = 110 + WARP
    m.collision = col
    sx, sz = (SPAWN[0] - 50) * 100 + 50, (49 - SPAWN[1]) * 100 + 50
    m.warps[WARP].update({'x': sx, 'z': sz, 'rotation': ROTATION, 'targetMap': TARGET[0], 'targetExit': TARGET[1]})
    check_arrivals(m, 'TUNN04')
    open(os.path.join(out, 'TUNN04.MAP'), 'wb').write(m.build())
    R = reach.from_spawn_coordinates(m, starts=[(m.warps[0]['x'], m.warps[0]['z'])])          # from the arrival from the tunnel
    if (sx, sz) not in R: sys.exit('the arrival from the gallery is not reachable')
    if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in EXIT_TILES for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
        sys.exit('the stair is not reachable')
    print(f'TUNN04: stair exit tiles {len(EXIT_TILES)}, spawn px {cam.pixel(sx, sz)}, reach {len(R)}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
