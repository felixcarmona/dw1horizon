#!/usr/bin/env python3
"""Ancient Glacial Region, the Tyrannomon path (KODA03, screen 82): the mouth of MasterTyrannomon's secret trail in
the ferns of the east edge, leading to the Passage (screen 305).

The mouth is our own picture (art/koda03-mouth.png, with transparency; made with Nano Banana on a 5x enlargement of
the path's east edge and cut out of its answer: the band where the ferns part and the dirt trail leaves the path,
feathered). It is laid over the player's own KODA03 background at build time; nothing of the game's background is in
this folder. The tiles of the mouth are step trigger 1 (0 is the Tyrannomon's block on the path): the story
(arcs/glacial/glacial-82.py) leads the tamer into the Passage only once MasterTyrannomon has left its post to guide him
("Guide me", §3.1f), and turns him back before. Exit 2 of the map (unused by the game) is the arrival from the Passage,
three tiles inside the path, facing west.

    python3 koda03-passage.py OUT_DIR        writes OUT_DIR/KODA03.MAP and KODA03.TFS (they replace the disc's)
"""
import os, sys
from mapbase import extracted, Cam, dwmap, MOD, check_arrivals, bg
from maps import reach

MOUTH_PNG = os.path.join(MOD, 'art', 'koda03-mouth.png')
MOUTH_AT = (378, 130)                                   # top-left of the picture on the 512x512 background
MOUTH_TILES = [(tx, tz) for tz in range(36, 39) for tx in range(59, 62)]   # the trail's first tiles, in the ferns
SPAWN = (56, 37)                                        # tile of the arrival from the Passage
ROTATION = 3072                                         # facing -X: into the path
STEP = 1                                                # the mouth's step trigger (tile value 51 + STEP)


def main(out):
    os.makedirs(out, exist_ok=True)
    src = extracted('KODA03')
    bg([src + '.MAP', src + '.TFS', os.path.join(out, 'KODA03.TFS'),
        '--paste', MOUTH_PNG, str(MOUTH_AT[0]), str(MOUTH_AT[1])])
    m = dwmap.MapFile(open(src + '.MAP', 'rb').read()); cam = Cam(m)
    col = list(m.collision)
    for tx, tz in MOUTH_TILES: col[tz * 100 + tx] = 51 + STEP
    m.collision = col
    sx, sz = (SPAWN[0] - 50) * 100 + 50, (49 - SPAWN[1]) * 100 + 50
    m.warps[2].update({'x': sx, 'z': sz, 'rotation': ROTATION})
    check_arrivals(m, 'KODA03')
    open(os.path.join(out, 'KODA03.MAP'), 'wb').write(m.build())
    R = reach.from_spawn_coordinates(m, starts=[(m.warps[0]['x'], m.warps[0]['z'])])          # from the arrival from KODA02
    if (sx, sz) not in R: sys.exit('the arrival from the Passage is not reachable')
    if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in MOUTH_TILES for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
        sys.exit('the mouth is not reachable')
    print(f'KODA03: mouth step tiles {len(MOUTH_TILES)}, spawn px {cam.pixel(sx, sz)}, reach {len(R)}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
