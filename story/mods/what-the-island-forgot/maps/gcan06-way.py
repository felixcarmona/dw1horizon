#!/usr/bin/env python3
"""Great Canyon Bottom Area, the first part (GCAN06, screen 41): the way on to the second part (42, or 368 with the crack
open once the Motor is broken). Exit 1's tiles become step trigger 0 (the map has none): the story
(arcs/canyon/gcan06-way.py) picks the screen. No picture: the map only.

    python3 gcan06-way.py OUT_DIR        writes OUT_DIR/GCAN06.MAP (it replaces the disc's)
"""
import os, sys
from mapbase import extracted, dwmap

WARP, STEP = 1, 0


def main(out):
    os.makedirs(out, exist_ok=True)
    m = dwmap.MapFile(open(extracted('GCAN06') + '.MAP', 'rb').read())
    col = [51 + STEP if v == 110 + WARP else v for v in m.collision]
    n = sum(1 for a, b in zip(m.collision, col) if a != b)
    m.collision = col
    open(os.path.join(out, 'GCAN06.MAP'), 'wb').write(m.build())
    print(f'GCAN06: exit {WARP} tiles -> step {STEP}: {n}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
