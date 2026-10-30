#!/usr/bin/env python3
"""Mansion Basement (CHKA01, screen 66): the trapdoor beside the rune circle that leads down to the Grey Lord's Crypt
(screen 307).

The trapdoor is our own picture (art/chka01-trapdoor.png, with transparency; made with Nano Banana on a 5x enlargement
of the floor beside the circle and cut out of its answer: only the slab, feathered). It is laid over the player's own
CHKA01 background at build time; nothing of the game's background is in this folder. The slab's left half is step
trigger 1 (9 is the game's post-game section 60): the story (arcs/mansion/basement.py) opens the way down to the Crypt
only after "Let him rest" (R2, §3.4), and before that the slab does not move. Exit 1 of the map (an arrival point for
the scripts) is the arrival from the Crypt, where the game put it: on the slab's right part, facing south.

    python3 chka01-trapdoor.py OUT_DIR        writes OUT_DIR/CHKA01.MAP and CHKA01.TFS (they replace the disc's)
"""
import os, sys
from mapbase import extracted, Cam, dwmap, MOD, check_arrivals, bg
from maps import reach

TRAPDOOR_PNG = os.path.join(MOD, 'art', 'chka01-trapdoor.png')
TRAPDOOR_AT = (190, 305)                                # top-left of the picture on the 640x512 background
TRAPDOOR_TILES = [(tx, tz) for tz in (64, 65, 66, 67) for tx in (42, 43, 44)]   # the slab's left half; the arrival point (46,65) is on its right part
STEP = 1                                                # the slab's step trigger (tile value 51 + STEP)


def main(out):
    os.makedirs(out, exist_ok=True)
    src = extracted('CHKA01')
    bg([src + '.MAP', src + '.TFS', os.path.join(out, 'CHKA01.TFS'),
        '--paste', TRAPDOOR_PNG, str(TRAPDOOR_AT[0]), str(TRAPDOOR_AT[1])])
    m = dwmap.MapFile(open(src + '.MAP', 'rb').read()); cam = Cam(m)
    col = list(m.collision)
    for tx, tz in TRAPDOOR_TILES: col[tz * 100 + tx] = 51 + STEP
    m.collision = col
    w = m.warps[1]                                                            # x, z, rotation: the game's own
    check_arrivals(m, 'CHKA01')
    open(os.path.join(out, 'CHKA01.MAP'), 'wb').write(m.build())
    R = reach.from_spawn_coordinates(m, starts=[(m.warps[0]['x'], m.warps[0]['z'])])          # from the arrival from the mansion
    if (w['x'], w['z']) not in R and (round(w['x'] / 10) * 10, round(w['z'] / 10) * 10) not in R: sys.exit('the arrival from the crypt is not reachable')
    if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in TRAPDOOR_TILES for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
        sys.exit('the trapdoor is not reachable')
    print(f'CHKA01: trapdoor step tiles {len(TRAPDOOR_TILES)}, arrival px {cam.pixel(w["x"], w["z"])}, reach {len(R)}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
