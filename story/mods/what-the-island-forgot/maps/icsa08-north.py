#!/usr/bin/env python3
"""Ice Sanctuary, the hidden hall (ICSA08, screen 104): the gateway opened in the north edge of the circuit floor, the
way down to the Vault (screen 310).

The gateway is our own picture (art/icsa08-gateway.png, with transparency; made with Nano Banana on a 5x enlargement
of the hall's north edge and cut out of its answer: the opening, its steps and its frame of light, feathered). It is
laid over the player's own ICSA08 background at build time; nothing of the game's background is in this folder. Exit 1
of the map (unused by the game) leads to the Vault; the tiles of the opening, in the two rows beyond the hall's edge
(walls today), trigger it; the arrival from the Vault is three rows inside the hall, facing south. Always open for
now (the story's fourth crystal in ICSA04 is what brings the player here at all).

    python3 icsa08-north.py OUT_DIR        writes OUT_DIR/ICSA08.MAP and ICSA08.TFS (they replace the disc's)
"""
import os, sys
from mapbase import extracted, Cam, dwmap, MOD, check_arrivals, bg
from maps import reach

GATEWAY_PNG = os.path.join(MOD, 'art', 'icsa08-gateway.png')
GATEWAY_AT = (356, 44)                                  # top-left of the picture on the 768x640 background
GATEWAY_TILES = [(tx, tz) for tz in (24, 25) for tx in range(48, 52)]   # the opening: the hall's top row and the row beyond it
SPAWN = (50, 29)                                        # tile of the arrival from the Vault
ROTATION = 2048                                         # facing -Z: into the hall
TARGET = (310, 0)                                       # the Wall of Hearts


def main(out):
    os.makedirs(out, exist_ok=True)
    src = extracted('ICSA08')
    bg([src + '.MAP', src + '.TFS', os.path.join(out, 'ICSA08.TFS'),
        '--paste', GATEWAY_PNG, str(GATEWAY_AT[0]), str(GATEWAY_AT[1])])
    m = dwmap.MapFile(open(src + '.MAP', 'rb').read()); cam = Cam(m)
    col = list(m.collision)
    for tx, tz in GATEWAY_TILES: col[tz * 100 + tx] = 111
    m.collision = col
    sx, sz = (SPAWN[0] - 50) * 100 + 50, (49 - SPAWN[1]) * 100 + 50
    m.warps[1].update({'x': sx, 'z': sz, 'rotation': ROTATION, 'targetMap': TARGET[0], 'targetExit': TARGET[1]})
    check_arrivals(m, 'ICSA08')
    open(os.path.join(out, 'ICSA08.MAP'), 'wb').write(m.build())
    R = reach.from_spawn_coordinates(m, starts=[(m.warps[0]['x'], m.warps[0]['z'])])          # from the script arrival at the centre
    if (sx, sz) not in R: sys.exit('the arrival from the Vault is not reachable')
    if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in GATEWAY_TILES for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
        sys.exit('the gateway is not reachable')
    print(f'ICSA08: gateway exit tiles {len(GATEWAY_TILES)}, spawn px {cam.pixel(sx, sz)}, reach {len(R)}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
