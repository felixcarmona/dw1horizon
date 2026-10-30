# SPDX-License-Identifier: MIT
"""Where the player can really stand: a flood fill of the engine's own movement check (map_collision.c: moving along x
tests the column at x +- radius over z +- radius/2; along z the row at z +- radius over x +- radius/2; tiles with bit 0x80
block), from the map's spawn points, on a 10-unit lattice. Tamer radius 100 (content/species/0-main-character.json).
reach(map) -> set of (x, z)."""
import sys
from pathlib import Path
from collections import deque
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dwmap

def tdiv(a): return int(a / 100)                       # C division truncates toward zero

def col(x): return tdiv(x) + 50 - (1 if x < 0 else 0)
def row(z): return 49 - tdiv(z) + (1 if z < 0 else 0)

def blocked(m, tx, tz):
    return not (0 <= tx < 100 and 0 <= tz < 100) or (m.collision[tz * 100 + tx] & 0x80) != 0

def can_x(m, x, z, d, r):                              # checkMapCollisionZ
    e = col(x + d * r)
    return not any(blocked(m, e, t) for t in range(row(z + r // 2), row(z - r // 2) + 1))

def can_z(m, x, z, d, r):                              # checkMapCollisionX
    e = row(z + d * r)
    return not any(blocked(m, t, e) for t in range(col(x - r // 2), col(x + r // 2) + 1))

def reach(m, starts=None, r=100, step=10, *, seed_policy="used_free_arrivals"):
    """Flood with explicit author or walking seed behavior.

    used_free_arrivals skips unused warps and blocked starts. spawn_coordinates
    includes nonzero unused warps and retains blocked starts for walking/recipes.
    """
    if seed_policy not in ("used_free_arrivals", "spawn_coordinates"):
        raise ValueError(f"unknown reach seed policy: {seed_policy}")
    if starts is None:
        starts = [(w['x'], w['z']) for w in m.warps if w['targetMap'] != -1 or
                  (seed_policy == 'spawn_coordinates' and (w['x'] or w['z']))]
    seen = set(); q = deque()
    for x, z in starts:
        p = (round(x / step) * step, round(z / step) * step)
        if seed_policy == 'used_free_arrivals' and blocked(m, col(p[0]), row(p[1])): continue
        seen.add(p); q.append(p)
    while q:
        x, z = q.popleft()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx * step, z + dz * step)
            if n in seen or not (-5000 <= n[0] < 5000 and -5000 <= n[1] < 5000): continue
            if dx and not can_x(m, x, z, dx, r): continue
            if dz and not can_z(m, x, z, dz, r): continue
            seen.add(n); q.append(n)
    return seen

def from_spawn_coordinates(m, starts=None, r=100, step=10):
    """Walking/recipe policy: retain all authored spawn coordinates."""
    return reach(m, starts, r, step, seed_policy="spawn_coordinates")


def check_recipe_arrivals(m, name=''):
    """Every used warp's spawn stands on a free tile and no tile within one step of it carries that warp's own exit
    value: an arrival on (or beside) its own exit tiles bounces straight back, and `reachable` cannot see it (it seeds
    from the spawns). Exits with no target are skipped."""
    for k, w in enumerate(m.warps):
        if w['targetMap'] == -1: continue
        tx, tz = int(w['x'] / 100) + 50 - (1 if w['x'] < 0 else 0), 49 - int(w['z'] / 100) + (1 if w['z'] < 0 else 0)
        if m.collision[tz * 100 + tx] & 0x80: sys.exit(f'{name}: the arrival of warp {k} at tile ({tx},{tz}) is not free')
        near = [m.collision[(tz + dz) * 100 + tx + dx] for dx in (-1, 0, 1) for dz in (-1, 0, 1)
                if 0 <= tx + dx < 100 and 0 <= tz + dz < 100]
        if 110 + k in near: sys.exit(f'{name}: the arrival of warp {k} at tile ({tx},{tz}) stands on or beside its own exit tiles')



def check_arrivals(m):
    """Reject blocked, floating, bouncing and mutually disconnected used arrivals.

    Keep one reference component: unioning every arrival hides disconnected rooms.
    A spawn near a wall can walk out even when the directional body checks prevent
    walking back to its exact center. Its own flood must join the reference component.
    This is a 10-unit lattice approximation; walk every arrival in the emulator.
    """
    errors = []
    arrivals = [(i, w) for i, w in enumerate(m.warps) if w['targetMap'] != -1]
    for i, w in arrivals:
        tx, tz = col(w['x']), row(w['z'])
        if blocked(m, tx, tz): errors.append(f'arrival {i}: blocked or outside map')
        if w['y'] != 0: errors.append(f'arrival {i}: nonzero warp height {w["y"]}')
        if any(0 <= tx+dx < 100 and 0 <= tz+dz < 100 and
               m.collision[(tz+dz)*100+tx+dx] == 110+i
               for dx in (-1,0,1) for dz in (-1,0,1)):
            errors.append(f'arrival {i}: stands on or beside its own exit')
    if arrivals and not errors:
        w = arrivals[0][1]
        connected = reach(m, [(w['x'], w['z'])])
        for i, w in arrivals:
            p = (round(w['x']/10)*10, round(w['z']/10)*10)
            outward = connected if p in connected else reach(m, [(w['x'], w['z'])])
            if not connected.intersection(outward):
                errors.append(f'arrival {i}: unreachable from arrival {arrivals[0][0]}')
            if not any((p[0]+dx*10,p[1]+dz*10) in outward for dx,dz in ((1,0),(-1,0),(0,1),(0,-1))):
                errors.append(f'arrival at {p[0]},{p[1]}: cannot move')
    return errors


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('map')
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    m = dwmap.MapFile(Path(args.map).read_bytes())
    if args.check:
        errors = check_arrivals(m)
        if errors: sys.exit('\n'.join(errors))
        print('PASS: arrivals connected, free, at ground height and clear of own exits')
    else:
        print(len(reach(m)), 'reachable lattice points')
