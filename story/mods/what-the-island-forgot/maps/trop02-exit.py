#!/usr/bin/env python3
"""Open the grass along Tropical Jungle's southwest exit approach.

The original boundary steps inward at rows 79 and 83, catching the tamer's
100-unit body box. These cells contain grass; the stump and plants to the east
retain their collision. Extend the same exit across the newly open edge.
"""
import os
import sys
from mapbase import extracted, dwmap

# (row, first column, last column, value). Every changed cell was a wall.
GRASS = [(z, 23, 24, 0) for z in range(79, 83)] + [(z, 23, 26, 0) for z in range(83, 87)]
EXIT = [(z, 23, 26, 111) for z in (87, 88)]


def repair(data):
    m = dwmap.MapFile(data)
    cells = list(m.collision)
    for z, lo, hi, value in GRASS + EXIT:
        for x in range(lo, hi + 1):
            if cells[z * 100 + x] != 128:
                raise ValueError(f'TROP02: original wall changed at {x},{z}')
            cells[z * 100 + x] = value
    m.collision = cells
    return m.build()


def main(out):
    os.makedirs(out, exist_ok=True)
    with open(extracted('TROP02') + '.MAP', 'rb') as f:
        data = repair(f.read())
    with open(os.path.join(out, 'TROP02.MAP'), 'wb') as f:
        f.write(data)


if __name__ == '__main__':
    main(sys.argv[1])
