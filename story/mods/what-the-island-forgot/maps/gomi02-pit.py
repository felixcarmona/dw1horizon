#!/usr/bin/env python3
"""Trash Mountain, the top (GOMI02, screen 165, King of Sukamon's): the easternmost edge of the upper slope, where today the
rubbish only piles up, is a pit down into the Galleries arc's rubbish mouth (screen 353): an iron ladder in a hole among the
rubbish, our cut-out art/gomi02-pit.png laid over the player's own background at build time. Exit 1 of
the map (unused by the game) leads down; its tiles are the slope's eastern edge; the arrival from the mine is three tiles
west of them, facing the slope.

    python3 gomi02-pit.py OUT_DIR        writes OUT_DIR/GOMI02.MAP and GOMI02.TFS (they replace the disc's)
"""
import os, shutil, sys
from mapbase import extracted, Cam, dwmap, MOD, bg
from maps import reach

EXIT_TILES = [(64, 45), (64, 46), (65, 46), (64, 47), (65, 47)]
SPAWN = (61, 47)                                        # tile of the arrival from the mine
ROTATION = 2560
WARP = 1
TARGET = (353, 1)


def main(out):
    os.makedirs(out, exist_ok=True)
    src = extracted('GOMI02')
    # our cut-out (gomi02-pit.png, with transparency: a Nano Banana edit of a 4x enlargement of this spot, cut out and feathered) laid over the
    # player's own background at build time; nothing of the game's background is in this folder
    bg([src + '.MAP', src + '.TFS', os.path.join(out, 'GOMI02.TFS'),
        '--paste', os.path.join(MOD, 'art', 'gomi02-pit.png'), '440', '80'])
    m = dwmap.MapFile(open(src + '.MAP', 'rb').read()); cam = Cam(m)
    col = list(m.collision)
    for tx, tz in EXIT_TILES: col[tz * 100 + tx] = 110 + WARP
    m.collision = col
    sx, sz = (SPAWN[0] - 50) * 100 + 50, (49 - SPAWN[1]) * 100 + 50
    m.warps[WARP].update({'x': sx, 'z': sz, 'rotation': ROTATION, 'targetMap': TARGET[0], 'targetExit': TARGET[1]})
    # only our warp is checked: the original's own exit 0 has its arrival beside its exit tiles (the game's layout)
    tx, tz = SPAWN
    if col[tz * 100 + tx] & 0x80: sys.exit('GOMI02: the arrival from the mine is not on a free tile')
    if any(col[(tz + dz) * 100 + tx + dx] == 110 + WARP for dx in (-1, 0, 1) for dz in (-1, 0, 1)): sys.exit('GOMI02: the arrival from the mine stands beside its exit tiles')
    open(os.path.join(out, 'GOMI02.MAP'), 'wb').write(m.build())
    R = reach.from_spawn_coordinates(m, starts=[(m.warps[0]['x'], m.warps[0]['z'])])          # from the arrival from the tunnel
    if (sx, sz) not in R: sys.exit('the arrival from the mine is not reachable')
    if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in EXIT_TILES for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
        sys.exit('the mouth is not reachable')
    print(f'GOMI02: mouth exit tiles {len(EXIT_TILES)}, spawn px {cam.pixel(sx, sz)}, reach {len(R)}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
