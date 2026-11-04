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

def reach(m, starts=None, r=100, step=10, *, seed_policy="used_free_arrivals", footprints=()):
    """Flood with explicit author or walking seed behavior.

    used_free_arrivals skips unused warps and blocked starts. spawn_coordinates
    includes nonzero unused warps and retains blocked starts for walking/recipes.
    """
    # map.c entityCheckEntityCollision/entityIsInEntity: inclusive AABB overlap.
    # Footprints are (x, z, model radius) for visible, living stationary NPCs.
    def entity_blocked(x, z):
        return any(abs(x - nx) <= r + nr and abs(z - nz) <= r + nr
                   for nx, nz, nr in footprints)

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
            if entity_blocked(*n): continue
            if dx and not can_x(m, x, z, dx, r): continue
            if dz and not can_z(m, x, z, dz, r): continue
            seen.add(n); q.append(n)
    return seen

def from_spawn_coordinates(m, starts=None, r=100, step=10):
    """Walking/recipe policy: retain all authored spawn coordinates."""
    return reach(m, starts, r, step, seed_policy="spawn_coordinates")


STEP = 50                                              # the tamer's walk advances 50 units per logic tick
_MOVES = None


def _moves():
    global _MOVES
    if _MOVES is None:
        import math
        _MOVES = sorted({(round(STEP * math.cos(k * math.pi / 16)), round(STEP * math.sin(k * math.pi / 16)))
                         for k in range(32)})
    return _MOVES


def _step_ok(m, x, z, dx, dz, r=100):
    """map.c checkMapCollision for a step that ends at (x, z): only the destination's leading edges, by the step's signs."""
    return (not dx or _edge_x(m, x, z, dx, r)) and (not dz or _edge_z(m, x, z, dz, r))


def _edge_x(m, x, z, dx, r):
    e = col(x + r if dx > 0 else x - r)
    return not any(blocked(m, e, t) for t in range(row(z + r // 2), row(z - r // 2) + 1))


def _edge_z(m, x, z, dz, r):
    e = row(z + r if dz > 0 else z - r)
    return not any(blocked(m, t, e) for t in range(col(x - r // 2), col(x + r // 2) + 1))


def dead_points(m, tx, tz, r=100, lattice=5):
    """Points of free tile (tx, tz) where no step in any of 32 directions is allowed: a tamer standing there can never
    move again (walking a strip one tile wide between two props leaves him in one)."""
    out = []
    x0, z0 = (tx - 50) * 100, (49 - tz) * 100
    for x in range(x0, x0 + 100, lattice):
        for z in range(z0, z0 + 100, lattice):
            if (col(x), row(z)) != (tx, tz): continue
            if not any(_step_ok(m, x + mx, z + mz, mx, mz, r) for mx, mz in _moves()):
                out.append((x, z))
    return out


def trap_tiles(m, reached=None):
    """Free tiles holding a point where the tamer cannot move at all, and that no walk from the arrivals visits (so
    blocking them takes no floor away). Every such tile is a trap if anything ever places the tamer there: one was
    found in play (screen 361, between a desk and a chair). Tiles with walkable floor and only a dead wall corner are
    not listed: the original screens have those too. Only plain floor (0) counts: an exit tile warps whoever stands on
    it, and a script trigger is the script's business."""
    if reached is None: reached = reach(m)
    visited = {(col(x), row(z)) for x, z in reached}
    out = []
    for tz in range(100):
        for tx in range(100):
            if m.collision[tz * 100 + tx] != 0 or (tx, tz) in visited: continue
            if all(not blocked(m, tx + a, tz + b) for a in range(-2, 3) for b in range(-2, 3)): continue
            if dead_points(m, tx, tz): out.append((tx, tz))
    return out


def model_tile(x, z):
    """map_collision.c getModelTile: the tile the engine says a position stands on (z = 0 is row 50, not 49)."""
    return tdiv(x) + 50 - (1 if x < 0 else 0), 50 - tdiv(z) - (1 if z > 0 else 0)


PICKUP_TILE_MIN = 50      # lattice points (10 units apart, 100 to a tile) the item's own tile must give the tamer
PICKUP_WINDOW_MIN = 300   # ... and the whole 3x3 window: three tiles of standing room, not one spot
PICKUP_BACK_ROWS = 4      # free floor rows an item needs behind it (toward the screen's top): its sprite and bubble are drawn above
                          # its tile, so nearer a wall than this the item looks stuck on the wall (336's mushrooms, 2026-11)
CHEST_FRONT = {0: (0, 4), 2048: (0, -4), 1024: (-4, 0), 3072: (4, 0)}   # map_object.c spawnChest: the opening tile


def walk_area(m):
    """The positions a walk from the used arrivals visits; a screen entered only by a script (no used warp: the Drowned
    Shore's ferry) seeds from every authored spawn coordinate instead."""
    return reach(m) or from_spawn_coordinates(m)


def pickup_room(m, tile, reached=None):
    """(points on the tile, points in its 3x3 window): how much of where the tamer really walks picks up an item lying
    on tile (tamer.c checkItemPickup and checkChestCollision: the tamer's tile within one of it, both ways)."""
    if reached is None: reached = walk_area(m)
    on = near = 0
    for x, z in reached:
        tx, tz = model_tile(x, z)
        if abs(tx - tile[0]) <= 1 and abs(tz - tile[1]) <= 1:
            near += 1; on += (tx, tz) == tuple(tile)
    return on, near


def with_chest(m, tile):
    """The map as the engine has it once a chest stands on tile: spawnChest's setImpassableSquare(tile, 2) blocks the
    4x4 tiles from tile - 2 to tile + 1."""
    out = type('ChestMap', (), {})()
    out.collision = list(m.collision); out.warps = m.warps
    for tz in range(tile[1] - 2, tile[1] + 2):
        for tx in range(tile[0] - 2, tile[0] + 2):
            if 0 <= tx < 100 and 0 <= tz < 100: out.collision[tz * 100 + tx] = 0x80
    return out


def check_pickups(m, items=(), chests=()):
    """A pickup the player has to hunt for, a pixel-perfect spot, is a failure. items: [(label, (tileX, tileY))] of
    ground items (SPAWN_ITEM tiles); chests: [(label, (x, z), facing)] (SPAWN_CHEST position and rotation). An item
    must lie on plain floor (0: not rock, not an exit or a trigger) and both its own tile and its 3x3 window must give
    the walk from the arrivals room to stand (PICKUP_TILE_MIN, PICKUP_WINDOW_MIN); a chest's opening tile, four tiles
    in front of it, the same with the chest's own block in the way. -> error strings."""
    errors = []
    reached = walk_area(m) if items else None
    for label, tile in items:
        tx, tz = tile
        if not (0 <= tx < 100 and 0 <= tz < 100) or m.collision[tz * 100 + tx] != 0:
            v = m.collision[tz * 100 + tx] if 0 <= tx < 100 and 0 <= tz < 100 else 'outside'
            errors.append(f'{label}: item at tile {tx},{tz} lies on collision {v}, not plain floor'); continue
        on, near = pickup_room(m, tile, reached)
        if on < PICKUP_TILE_MIN or near < PICKUP_WINDOW_MIN:
            errors.append(f'{label}: item at tile {tx},{tz} is picked up from {near} reachable points ({on} on its own '
                          f'tile; at least {PICKUP_WINDOW_MIN} and {PICKUP_TILE_MIN})')
        else:
            rows = 0
            while rows < PICKUP_BACK_ROWS and tz - 1 - rows >= 0 and all(m.collision[(tz - 1 - rows) * 100 + tx + a] == 0
                                                                       for a in (-1, 0, 1) if 0 <= tx + a < 100):
                rows += 1
            if rows < PICKUP_BACK_ROWS:
                errors.append(f'{label}: item at tile {tx},{tz} has {rows} free rows behind it (it needs {PICKUP_BACK_ROWS}: '
                              f'its sprite would hang on the wall)'); continue
    for label, (x, z), facing in chests:
        if facing not in CHEST_FRONT:
            errors.append(f'{label}: chest facing {facing} has no opening tile (0, 1024, 2048 or 3072)'); continue
        tile = model_tile(x, z)
        front = (tile[0] + CHEST_FRONT[facing][0], tile[1] + CHEST_FRONT[facing][1])
        cm = with_chest(m, tile)
        on, near = pickup_room(cm, front, walk_area(cm))
        if near < PICKUP_WINDOW_MIN:
            errors.append(f'{label}: chest at {x},{z} opens from tile {front[0]},{front[1]}: {near} reachable points '
                          f'there (at least {PICKUP_WINDOW_MIN})')
    return errors


def check_recipe_arrivals(m, name='', traps=True):
    """Every used warp's spawn stands on a free tile and no tile within one step of it carries that warp's own exit
    value: an arrival on (or beside) its own exit tiles bounces straight back, and `reachable` cannot see it (it seeds
    from the spawns). Exits with no target are skipped. With traps (new screens), no free tile may hold a point where
    the tamer can never move again (trap_tiles); a retouch of an original screen keeps the original's own."""
    for k, w in enumerate(m.warps):
        if w['targetMap'] == -1: continue
        tx, tz = int(w['x'] / 100) + 50 - (1 if w['x'] < 0 else 0), 49 - int(w['z'] / 100) + (1 if w['z'] < 0 else 0)
        if m.collision[tz * 100 + tx] & 0x80: sys.exit(f'{name}: the arrival of warp {k} at tile ({tx},{tz}) is not free')
        near = [m.collision[(tz + dz) * 100 + tx + dx] for dx in (-1, 0, 1) for dz in (-1, 0, 1)
                if 0 <= tx + dx < 100 and 0 <= tz + dz < 100]
        if 110 + k in near: sys.exit(f'{name}: the arrival of warp {k} at tile ({tx},{tz}) stands on or beside its own exit tiles')
    if traps and any(w['targetMap'] != -1 for w in m.warps):
        found = trap_tiles(m)
        if found: sys.exit(f'{name}: tiles where the tamer could never move again (block them): {found}')



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
    if arrivals and not errors:
        errors.extend(f'trap tile {t[0]},{t[1]}: the tamer could never move again there' for t in trap_tiles(m))
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
