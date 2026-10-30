#!/usr/bin/env python3
"""Ancient Speedy Region, Meteormon's crater (KODA07, screen 86): a cleft in the rock of the crater's north rim, the
second mouth of the Bone Field (screen 306), the way back from the field through the fast-time region.

The cleft is our own picture (art/koda07-mouth.png, with transparency; made with Nano Banana on a 5x enlargement of
the rim and cut out of its answer: only the opening and its broken stone sides, feathered). It is laid over the
player's own KODA07 background at build time; nothing of the game's background is in this folder. Exit 1 of the map
(unused by the game) leads to the Bone Field, and the tiles at the foot of the cleft trigger it; the arrival from the
field is three tiles into the crater, facing south. The cleft is always there; the story will decide whether it opens
only after the field has been visited.

    python3 koda07-mouth.py OUT_DIR        writes OUT_DIR/KODA07.MAP and KODA07.TFS (they replace the disc's)
"""
import os, sys
from mapbase import extracted, Cam, dwmap, MOD, check_arrivals, bg
from maps import reach

MOUTH_PNG = os.path.join(MOD, 'art', 'koda07-mouth.png')
MOUTH_AT = (146, 24)                                    # top-left of the picture on the 384x384 background
MOUTH_TILES = [(tx, tz) for tz in range(34, 37) for tx in range(48, 51)]   # the foot of the cleft, in the rim
SPAWN = (49, 39)                                        # tile of the arrival from the Bone Field
ROTATION = 2048                                         # facing -Z: into the crater
TARGET = (306, 1)                                       # the Bone Field's north exit


def main(out):
    os.makedirs(out, exist_ok=True)
    src = extracted('KODA07')
    bg([src + '.MAP', src + '.TFS', os.path.join(out, 'KODA07.TFS'),
        '--paste', MOUTH_PNG, str(MOUTH_AT[0]), str(MOUTH_AT[1])])
    m = dwmap.MapFile(open(src + '.MAP', 'rb').read()); cam = Cam(m)
    col = list(m.collision)
    for tx, tz in MOUTH_TILES: col[tz * 100 + tx] = 111
    m.collision = col
    sx, sz = (SPAWN[0] - 50) * 100 + 50, (49 - SPAWN[1]) * 100 + 50
    m.warps[1].update({'x': sx, 'z': sz, 'rotation': ROTATION, 'targetMap': TARGET[0], 'targetExit': TARGET[1]})
    check_arrivals(m, 'KODA07')
    open(os.path.join(out, 'KODA07.MAP'), 'wb').write(m.build())
    R = reach.from_spawn_coordinates(m, starts=[(m.warps[0]['x'], m.warps[0]['z'])])          # from the arrival from KODA08
    if (sx, sz) not in R: sys.exit('the arrival from the Bone Field is not reachable')
    if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in MOUTH_TILES for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
        sys.exit('the cleft is not reachable')
    print(f'KODA07: cleft exit tiles {len(MOUTH_TILES)}, spawn px {cam.pixel(sx, sz)}, reach {len(R)}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
