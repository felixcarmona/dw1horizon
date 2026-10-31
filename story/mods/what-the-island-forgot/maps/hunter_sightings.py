#!/usr/bin/env python3
"""Mark ordinary floor near each rumour hunter for its first-sighting line.

Native Forest's south-path recipe calls mark_sighting on its map. This recipe
independently builds Gear Savanna, keeping parallel map builds independent.
"""
from pathlib import Path
import shutil
import sys
from mapbase import extracted, dwmap, check_arrivals

SIGHTINGS = {'MAYO03': (500, 900, 0), 'GIAS01': (500, 200, 1)}
RADIUS = 800


def mark_sighting(m, name):
    """Preserve walls, exits, existing triggers and every other map record."""
    x, z, step = SIGHTINGS[name]
    col = list(m.collision)
    count = 0
    for i, value in enumerate(col):
        tx, tz = i % 100, i // 100
        if value == 0 and (tx * 100 - 4950 - x) ** 2 + (4950 - tz * 100 - z) ** 2 <= RADIUS ** 2:
            col[i] = 51 + step
            count += 1
    if not count:
        raise ValueError(f'{name}: no hunter sighting tiles')
    m.collision = col
    print(f'{name}: {count} hunter sighting tiles, step {step}')


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    name = 'GIAS01'
    m = dwmap.MapFile(Path(extracted(name) + '.MAP').read_bytes())
    mark_sighting(m, name)
    check_arrivals(m, name)
    (out / (name + '.MAP')).write_bytes(m.build())
    shutil.copyfile(extracted(name) + '.TFS', out / (name + '.TFS'))


if __name__ == '__main__':
    main(sys.argv[1])
