#!/usr/bin/env python3
"""Great Canyon Bottom Area (GCAN07, screen 42): the crack in the ground that leads down to the Rift (screen 301).

The crack is our own picture (art/gcan07-crack-open.png, with transparency; made with Nano Banana on a 5x enlargement
of the spot and cut out of its answer: only the crack's pixels). It is laid over the player's own GCAN07 background at
build time; nothing of the game's background is in this folder. The tiles under the crack are step trigger 1 (0 is the fall from above, section 51): the story
(canyon/canyon-bottom.py) lets the tamer down to the Descent only once the Motor is broken (flag R1), and before that
turns him back. Exit 1 of the map is the arrival from the Descent's steps, beside the crack, facing north.

Before the Motor is broken the crack is not there: screen 42 keeps the player's own background (GCAN07.MAP only, with
the step tiles, which do nothing then); the open crack is screen 368 (GCAN27), the same place with our picture,
running 42's own script, where the ways in (GCAN06's exit 1, the Descent's steps) lead once R1 is set
(arcs/canyon/canyon-bottom.py, gcan06-way.py, descent.py).

    python3 gcan07-crack.py RETOUCH_DIR SCREENS_DIR   writes RETOUCH_DIR/GCAN07.MAP (it replaces the disc's) and
                                                        SCREENS_DIR/GCAN27.MAP, GCAN27.TFS (screen 368)
"""
import os, sys
from mapbase import extracted, Cam, reachable, dwmap, MOD, bg

CRACK_PNG = os.path.join(MOD, 'art', 'gcan07-crack-open.png')
CRACK_AT = (375, 273)                                   # top-left of the picture on the 640x512 background
CRACK_TILES = ((417, 305), (34, 22))                    # ellipse (centre, radii) of the tiles that lead down
STEP = 1                                                # the step trigger of the crack's tiles (tile value 51 + STEP)


def main(out, screens):
    os.makedirs(out, exist_ok=True); os.makedirs(screens, exist_ok=True)
    src = extracted('GCAN07')
    # the open crack's background: the crack over the player's own TFS (the palette is kept: unchanged pixels keep their index)
    bg([src + '.MAP', src + '.TFS', os.path.join(screens, 'GCAN27.TFS'),
        '--paste', CRACK_PNG, str(CRACK_AT[0]), str(CRACK_AT[1])])
    # the map: the crack's tiles are a step trigger; exit 1 is the arrival from the Descent
    m = dwmap.MapFile(open(src + '.MAP', 'rb').read()); cam = Cam(m)
    (cx, cy), (rx, ry) = CRACK_TILES; col = list(m.collision); n = 0
    for tx, tz, u, v in cam.tiles():
        if col[tz * 100 + tx] != 0 or u is None: continue
        if ((u - cx) / rx) ** 2 + ((v - cy) / ry) ** 2 <= 1.0: col[tz * 100 + tx] = 51 + STEP; n += 1
    m.collision = col
    open(os.path.join(out, 'GCAN07.MAP'), 'wb').write(m.build())
    from district_foreground import apply
    apply(m, 'canyon-crack', os.path.join(screens, 'GCAN27.TFS'))
    open(os.path.join(screens, 'GCAN27.MAP'), 'wb').write(m.build())
    sp = (m.warps[1]['x'], m.warps[1]['z']); R = reachable(m)
    if (round(sp[0] / 10) * 10, round(sp[1] / 10) * 10) not in R: sys.exit('the spawn at the crack is not reachable')
    print(f'GCAN07: crack tiles {n}, spawn px {cam.pixel(*sp)}, reach {len(R)}')


if __name__ == '__main__':
    if len(sys.argv) != 3: sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
