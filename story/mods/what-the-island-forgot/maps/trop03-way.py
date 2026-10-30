#!/usr/bin/env python3
"""Tropical Jungle (TROP03, screen 14): the way up to the Great Canyon Entrance. Exit 0's tiles become step trigger 1 (0
is the game's own): the story (arcs/canyon/stone-bridge.py) leads to screen 36, or to 367 (the stone bridge) once the
Motor is broken (R1). No picture: the map only.

    python3 trop03-way.py OUT_DIR        writes OUT_DIR/TROP03.MAP (it replaces the disc's)
"""
import os, sys
from mapbase import extracted, dwmap

WARP, STEP = 0, 1


def main(out):
    os.makedirs(out, exist_ok=True)
    src = extracted('TROP03')
    m = dwmap.MapFile(open(src + '.MAP', 'rb').read())
    col = [51 + STEP if v == 110 + WARP else v for v in m.collision]
    n = sum(1 for a, b in zip(m.collision, col) if a != b)
    m.collision = col
    open(os.path.join(out, 'TROP03.MAP'), 'wb').write(m.build())
    print(f'TROP03: exit {WARP} tiles -> step {STEP}: {n}')


if __name__ == '__main__':
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
