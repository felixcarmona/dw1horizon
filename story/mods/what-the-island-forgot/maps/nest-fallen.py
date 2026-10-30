#!/usr/bin/env python3
"""Birdramon's nest fallen in (screen 366, files NEST02): the top of the Great Canyon (GCAN10, screen 129) after the
Motor is broken (R1, story-bible.md §3.2): the rock under the nest has sunk, the woven nest is torn in two across a
crack and its scrap scattered. The story's canyon elevators bring the tamer here instead of to 129 once R1 is set
(arcs/canyon/nest-fallen.py).

The fallen nest is our own picture (art/gcan10-nest-fallen.png, with transparency: one Nano Banana edit of a 4x
enlargement of the nest, design/prompts/nest-fallen/, cut out where the answer differs from the player's background).
It is laid over the player's own GCAN10 background at build time; nothing of the game's background is in this folder.
The map is GCAN10's with the nest's foreground pieces hidden (they would draw the old nest over the new one), the crack
and the sunk half of the nest beyond it made walls, and no Digimon.

    python3 nest-fallen.py OUT_DIR        writes OUT_DIR/NEST02.MAP and NEST02.TFS (a new screen's files)
"""
import os, sys
from mapbase import extracted, Cam, dwmap, MOD, bg
from maps import reach

NEST_PNG = os.path.join(MOD, 'art', 'gcan10-nest-fallen.png')
NEST_AT = (0, 125)                                      # top-left of the picture on the 640x768 background
SUNK_PX = [(40, 215), (150, 215), (150, 360), (40, 360)]   # the crack and the sunk half of the nest beyond it (background pixels)


def inside(poly, u, v):
    n, c = len(poly), False
    for i in range(n):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
        if (y0 > v) != (y1 > v) and u < x0 + (v - y0) * (x1 - x0) / (y1 - y0): c = not c
    return c


def main(out):
    os.makedirs(out, exist_ok=True)
    src = extracted('GCAN10')
    bg([src + '.MAP', src + '.TFS', os.path.join(out, 'NEST02.TFS'),
        '--paste', NEST_PNG, str(NEST_AT[0]), str(NEST_AT[1])])
    m = dwmap.MapFile(open(src + '.MAP', 'rb').read()); cam = Cam(m)
    w, h, mode, rows, _ = dwmap.png_read(NEST_PNG, alpha=True)
    alpha = [[r[4 * x + 3] > 127 for x in range(w)] for r in rows]
    X, Y = NEST_AT; hidden = []
    for k in dwmap.covering_instances(m, X, Y, X + w, Y + h):
        inst = m.instances[k]; sp = m.sprites[inst['frames'][0]]
        x0, y0, x1, y1 = max(inst['x'], X), max(inst['y'], Y), min(inst['x'] + sp['width'], X + w), min(inst['y'] + sp['height'], Y + h)
        if sum(alpha[y][x] for y in range(y0 - Y, y1 - Y) for x in range(x0 - X, x1 - X)) >= 50: inst['flag'] = 1; hidden.append(k)
    col = list(m.collision); n = 0
    for tx, tz, u, v in cam.tiles():
        if u is not None and col[tz * 100 + tx] == 0 and inside(SUNK_PX, u, v): col[tz * 100 + tx] = 0x80; n += 1
    m.collision = col
    for d in m.digimon: d['type'] = -1                  # Birdramon is gone
    from district_foreground import apply
    apply(m, 'nest-fallen', os.path.join(out, 'NEST02.TFS'))
    open(os.path.join(out, 'NEST02.MAP'), 'wb').write(m.build())
    sp = (m.warps[0]['x'], m.warps[0]['z']); R = reach.from_spawn_coordinates(m, starts=[sp])
    print(f'NEST02: sunk wall tiles {n}, hidden pieces {hidden}, reach from the elevator {len(R)}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
