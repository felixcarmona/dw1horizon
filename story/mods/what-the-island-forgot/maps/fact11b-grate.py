#!/usr/bin/env python3
"""Factorial Town's sewer, its end (FACT11B, screen 220, Numemon and Nanimon): the far north end of the channel, a dead
end today, is a rusted grate that opens on the Galleries arc's drain (screen 356); our cut-out art/fact11b-grate.png laid over the player's own
background at build time. Exit 1 of the map (unused by the
game) leads down into the mine; its tiles are the channel's northern end; the arrival from the mine is three tiles
south of them, facing down the sewer.

    python3 fact11b-grate.py OUT_DIR        writes OUT_DIR/FACT11B.MAP and FACT11B.TFS (they replace the disc's)
"""
import os, shutil, sys
from mapbase import extracted, Cam, dwmap, MOD, bg
from maps import reach

EXIT_TILES = [(60, 20), (61, 20), (62, 20), (63, 20), (64, 20), (60, 21), (61, 21), (62, 21), (63, 21), (64, 21)]
SPAWN = (62, 24)                                        # tile of the arrival from the mine
ROTATION = 2048
WARP = 1
TARGET = (356, 1)


def main(out):
    os.makedirs(out, exist_ok=True)
    src = extracted('FACT11B')
    # our cut-out (fact11b-grate.png, with transparency: a Nano Banana edit of a 4x enlargement of this spot, cut out and feathered) laid over the
    # player's own background at build time; nothing of the game's background is in this folder
    bg([src + '.MAP', src + '.TFS', os.path.join(out, 'FACT11B.TFS'),
        '--paste', os.path.join(MOD, 'art', 'fact11b-grate.png'), '520', '40'])
    m = dwmap.MapFile(open(src + '.MAP', 'rb').read()); cam = Cam(m)
    col = list(m.collision)
    for tx, tz in EXIT_TILES: col[tz * 100 + tx] = 110 + WARP
    m.collision = col
    sx, sz = (SPAWN[0] - 50) * 100 + 50, (49 - SPAWN[1]) * 100 + 50
    m.warps[WARP].update({'x': sx, 'z': sz, 'rotation': ROTATION, 'targetMap': TARGET[0], 'targetExit': TARGET[1]})
    # only our warp is checked: the original's own exit 0 has its arrival beside its exit tiles (the game's layout)
    tx, tz = SPAWN
    if col[tz * 100 + tx] & 0x80: sys.exit('FACT11B: the arrival from the mine is not on a free tile')
    if any(col[(tz + dz) * 100 + tx + dx] == 110 + WARP for dx in (-1, 0, 1) for dz in (-1, 0, 1)): sys.exit('FACT11B: the arrival from the mine stands beside its exit tiles')
    open(os.path.join(out, 'FACT11B.MAP'), 'wb').write(m.build())
    R = reach.from_spawn_coordinates(m, starts=[(m.warps[0]['x'], m.warps[0]['z'])])          # from the arrival from the tunnel
    if (sx, sz) not in R: sys.exit('the arrival from the mine is not reachable')
    if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in EXIT_TILES for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
        sys.exit('the mouth is not reachable')
    print(f'FACT11B: mouth exit tiles {len(EXIT_TILES)}, spawn px {cam.pixel(sx, sz)}, reach {len(R)}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
