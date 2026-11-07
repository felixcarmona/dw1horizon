#!/usr/bin/env python3
"""Check the reported field boundaries and their complete arrival/exit routes.

Run on the final maps, after story compilation:
  python3 tools/maps/check_field_walkables.py build/NAME-maps/screens
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import dwmap
from maps import reach


def check(directory):
    results = {}
    for name in ('BARR01', 'BARR02', 'DESC01'):
        m = dwmap.MapFile((directory / (name + '.MAP')).read_bytes())
        reach.check_recipe_arrivals(m, name)
        first = m.warps[0]
        area = reach.reach(m, starts=[(first['x'], first['z'])])
        assert area, f'{name}: no reachable floor'
        for slot, warp in enumerate(m.warps):
            if warp['targetMap'] == -1:
                continue
            point = (round(warp['x'] / 10) * 10, round(warp['z'] / 10) * 10)
            assert point in area, f'{name}: arrival {slot} is disconnected'
        # Reach the same trigger the engine reads, including scripted town exits.
        visited = {reach.model_tile(x, z) for x, z in area}
        for value in set(m.collision):
            if not (110 <= value < 120 or value == 51):
                continue
            assert any(m.collision[z * 100 + x] == value for x, z in visited), \
                f'{name}: exit/step {value} cannot be entered'
        if name == 'BARR01':
            # A continuous barrier on each side must protect the whole flight.
            for z in range(40):
                assert m.collision[z * 100 + 50] & 128, ('left rail', z)
                assert m.collision[z * 100 + 61] & 128, ('right rail', z)
            assert all(m.collision[z * 100 + 51] == 51 for z in range(4)), 'left town trigger'
        elif name == 'BARR02':
            warp = m.warps[2]
            x, z = warp['x'], warp['z']
            assert all(reach.can_x(m, x, z, d, 100) and reach.can_z(m, x, z, d, 100)
                       for d in (-1, 1)), 'Cold Store arrival has no standing room'
        else:
            for x, z in ((47, 52), (35, 59), (58, 64)):
                assert reach.blocked(m, x, z), ('reported rock face', x, z)
        results[name] = dict(reachable_positions=len(area), arrivals=sum(w['targetMap'] != -1 for w in m.warps))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('screens', type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.screens), indent=2))


if __name__ == '__main__':
    main()
