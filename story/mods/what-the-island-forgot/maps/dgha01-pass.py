#!/usr/bin/env python3
"""Overdell, the western clearing (DGHA01, screen 34): the notch in the red cliff on the west side of the sand, between
the boulder and the lower rock, the way up into the Overdell Pass (its last screen, 335).

The notch is our own picture (art/dgha01-pass.png, with transparency; made with Nano Banana on a 5x enlargement of the
cliff's foot and cut out of its answer: only the sand pocket and the gap behind it, feathered). It is laid over the
player's own DGHA01 background at build time; nothing of the game's background is in this folder. Exit 3 of the map
(unused by the game) leads to the pass; the tiles of the pocket and the sand against it trigger it; the arrival from
the pass is on the sand, two tiles out, facing the clearing. Exit 2's tiles (the way to the Great Canyon Entrance)
become step trigger 0: the story (arcs/canyon/stone-bridge.py) leads to screen 36, or to 367 (the stone bridge) once
the Motor is broken (R1).

    python3 dgha01-pass.py OUT_DIR        writes OUT_DIR/DGHA01.MAP and DGHA01.TFS (they replace the disc's)
"""
import os, sys
from mapbase import extracted, Cam, dwmap, MOD, check_arrivals, bg
from maps import reach

PASS_PNG = os.path.join(MOD, 'art', 'dgha01-pass.png')
PASS_AT = (0, 240)                                      # top-left of the picture on the 640x768 background
EXIT_BOX = (40, 330, 104, 395)                          # pixels: the sand pocket of the notch and the first free column of sand beside it
SPAWN_PX = (150, 362)                                   # the arrival from the pass, on the sand, two tiles out
ROTATION = 1024                                         # facing +X: into the clearing
WARP = 3
TARGET = (335, 1)                                       # the last descent's bottom edge
CANYON_WARP, CANYON_STEP = 2, 0                        # the way to the canyon entrance: a step trigger


def main(out):
    os.makedirs(out, exist_ok=True)
    src = extracted('DGHA01')
    bg([src + '.MAP', src + '.TFS', os.path.join(out, 'DGHA01.TFS'),
        '--paste', PASS_PNG, str(PASS_AT[0]), str(PASS_AT[1])])
    m = dwmap.MapFile(open(src + '.MAP', 'rb').read()); cam = Cam(m)
    col = list(m.collision); exit_tiles = []; spawn = None; best = None
    for tx, tz, u, v in cam.tiles():
        if u is None: continue
        if EXIT_BOX[0] <= u <= EXIT_BOX[2] and EXIT_BOX[1] <= v <= EXIT_BOX[3]:
            col[tz * 100 + tx] = 110 + WARP; exit_tiles.append((tx, tz))
        d = (u - SPAWN_PX[0]) ** 2 + (v - SPAWN_PX[1]) ** 2
        if not m.collision[tz * 100 + tx] & 0x80 and (best is None or d < best): best, spawn = d, (tx, tz)
    col = [51 + CANYON_STEP if c == 110 + CANYON_WARP else c for c in col]
    m.collision = col
    sx, sz = (spawn[0] - 50) * 100 + 50, (49 - spawn[1]) * 100 + 50
    m.warps[WARP].update({'x': sx, 'z': sz, 'rotation': ROTATION, 'targetMap': TARGET[0], 'targetExit': TARGET[1]})
    check_arrivals(m, 'DGHA01')
    open(os.path.join(out, 'DGHA01.MAP'), 'wb').write(m.build())
    R = reach.from_spawn_coordinates(m, starts=[(m.warps[0]['x'], m.warps[0]['z'])])          # from the arrival from DGHA02
    if (sx, sz) not in R: sys.exit('the arrival from the pass is not reachable')
    if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in exit_tiles for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
        sys.exit('the notch is not reachable')
    print(f'DGHA01: notch exit tiles {len(exit_tiles)}, spawn tile {spawn} px {cam.pixel(sx, sz)}, reach {len(R)}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
