#!/usr/bin/env python3
"""Native Forest, the big field (MAYO03, screen 2): the way south to the Root Clearing (screen 314), through the gap
between the bushes on the field's bottom edge.

Nothing is painted here: the field's grass already reaches the bottom edge between the bush at the left and the
hedge, so the background stays the player's own (copied as it is). Exit 4 of the map (unused by the game) leads to the
clearing; the two bottom rows of the gap trigger it; the arrival from the clearing is four rows inside the field,
facing north.

    python3 mayo03-south.py OUT_DIR        writes OUT_DIR/MAYO03.MAP and MAYO03.TFS (they replace the disc's)
"""
import os, shutil, sys
from mapbase import extracted, Cam, dwmap, MOD, check_arrivals
from maps import reach
from hunter_sightings import mark_sighting

EXIT_TILES = [(tx, tz) for tz in (71, 72) for tx in range(39, 43)]   # the bottom of the gap, right of the tuft of grass
SPAWN = (39, 67)                                        # tile of the arrival from the clearing
ROTATION = 0                                            # facing +Z: into the field
WARP = 4                                                # the first unused slot
TARGET = (314, 0)                                       # the Root Clearing's north path


def main(out):
    os.makedirs(out, exist_ok=True)
    src = extracted('MAYO03')
    shutil.copyfile(src + '.TFS', os.path.join(out, 'MAYO03.TFS'))
    m = dwmap.MapFile(open(src + '.MAP', 'rb').read()); cam = Cam(m)
    col = list(m.collision)
    for tx, tz in EXIT_TILES: col[tz * 100 + tx] = 110 + WARP
    m.collision = col
    sx, sz = (SPAWN[0] - 50) * 100 + 50, (49 - SPAWN[1]) * 100 + 50
    m.warps[WARP].update({'x': sx, 'z': sz, 'rotation': ROTATION, 'targetMap': TARGET[0], 'targetExit': TARGET[1]})
    mark_sighting(m, 'MAYO03')
    check_arrivals(m, 'MAYO03')
    open(os.path.join(out, 'MAYO03.MAP'), 'wb').write(m.build())
    R = reach.from_spawn_coordinates(m, starts=[(m.warps[0]['x'], m.warps[0]['z'])])          # from the arrival from MAYO01
    if (sx, sz) not in R: sys.exit('the arrival from the clearing is not reachable')
    if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in EXIT_TILES for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
        sys.exit('the south gap is not reachable')
    print(f'MAYO03: south exit tiles {len(EXIT_TILES)}, spawn px {cam.pixel(sx, sz)}, reach {len(R)}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
