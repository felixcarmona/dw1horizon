#!/usr/bin/env python3
"""Run the prepared battle-drop placement (item.c spawnDroppedItems) on the host and check the tamer can pick it up.

Usage: python3 tools/dev/playtest/drop_reach_host.py [BUILD_TREE]   (default build/decomp-dev)

Battle moves skip the map collision, so a defeated enemy can stand inside a wall when its drop is placed. Synthetic
maps check that a drop on open ground stays exactly where the enemy fell and that a drop in a wall, or with no room to
stand within one tile, moves toward the tamer to a tile he can stand on. With extracted/ present, the reported case
(Great Canyon Top Area, GCAN08_1, the enemy at 2811,370) and every blocked tile next to the walk area of that screen
are run through tools/maps/reach.py: the drop must end where the walk picks it up (tamer.c, his tile within one).
"""
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools'), str(ROOT / 'tools/maps')]
from tools.dev.playtest.quick_care_host import function

PREFIX = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
typedef int32_t ItemId;
#define ITEM_NONE (-1)
#define OBJECT_ID_DROPPED_ITEM 0x1f95
typedef struct { int32_t vx, vy, vz, pad; } VECTOR;
typedef struct { int16_t vx, vy, vz, pad; } SVECTOR;
typedef struct { VECTOR location; } PositionData;
typedef struct { int32_t type; PositionData *posData; } Entity;
typedef struct { Entity entity; } TamerEntity;
typedef struct { SVECTOR spriteLocation; int32_t type; } WorldItem;
typedef struct { WorldItem worldItem; int16_t tileX; int16_t tileY; } DroppedItem;
DroppedItem DROPPED_ITEMS[11];
uint8_t MOD_DROPPED_SPOT[11];
static PositionData tamerPos, enemyPos;
TamerEntity TAMER_ENTITY = { { 0, &tamerPos } };
static int added;
void renderDroppedItem(int32_t instanceId) { (void)instanceId; }
void addObject(int32_t id, int32_t instance, int32_t a, void (*f)(int32_t)) { (void)id; (void)instance; (void)a; (void)f; added++; }
'''

MAIN = r'''
uint8_t MAP_COLLISION_DATA[10000];
/* stdin: the 10000 collision bytes (hex, 2 a byte), then "enemyX enemyZ tamerX tamerZ" lines;
   stdout: "tileX tileY spriteX spriteZ" for each */
int main(void) {
    char hex[3] = {0};
    for (int i = 0; i < 10000; i++) {
        if (scanf("%2s", hex) != 1) return 2;
        MAP_COLLISION_DATA[i] = (uint8_t)strtol(hex, 0, 16);
    }
    long ex, ez, tx, tz;
    while (scanf("%ld %ld %ld %ld", &ex, &ez, &tx, &tz) == 4) {
        Entity enemy = { 0, &enemyPos };
        DROPPED_ITEMS[0].worldItem.type = ITEM_NONE;
        enemyPos.location.vx = ex; enemyPos.location.vz = ez;
        tamerPos.location.vx = tx; tamerPos.location.vz = tz;
        added = 0;
        spawnDroppedItems(&enemy, 7);
        if (added != 1 || DROPPED_ITEMS[0].worldItem.type != 7) return 3;
        printf("%d %d %d %d\n", DROPPED_ITEMS[0].tileX, DROPPED_ITEMS[0].tileY,
               DROPPED_ITEMS[0].worldItem.spriteLocation.vx, DROPPED_ITEMS[0].worldItem.spriteLocation.vz);
    }
    return 0;
}
'''


def compile_tree(tree, out):
    item = (tree / 'src/main/item.c').read_text()
    collision = (tree / 'src/main/map_collision.c').read_text()
    parts = [function(collision, 'void getModelTile(VECTOR *pos, int16_t *outTileX, int16_t *outTileY)\n')]
    if 'modDropRoom' in item:
        parts.insert(0, 'extern uint8_t MAP_COLLISION_DATA[];\n')
        parts.append(function(item, 'static inline int32_t modDropFree('))
        parts.append(function(item, 'static inline int32_t modDropRoom('))
    parts.append(function(item, 'void spawnDroppedItems(Entity *e, ItemId type)'))
    src = out / 'drop.c'
    src.write_text(PREFIX + '\n'.join(parts) + MAIN)
    exe = out / 'drop'
    subprocess.run(['cc', '-std=gnu99', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover', str(src), '-o', str(exe)], check=True)
    return exe


def place(exe, collision, cases):
    """cases: [(enemyX, enemyZ, tamerX, tamerZ)] -> [(tileX, tileY, spriteX, spriteZ)]"""
    stdin = bytes(collision).hex() + '\n' + ''.join('%d %d %d %d\n' % c for c in cases)
    out = subprocess.run([str(exe)], input=stdin, capture_output=True, text=True, check=True).stdout
    return [tuple(map(int, line.split())) for line in out.splitlines()]


def centre(tile):
    return (tile[0] - 50) * 100 + 50, (50 - tile[1]) * 100 - 50


def room(collision, x, y):
    return all(0 <= x + d < 100 and 0 <= y < 100 and not collision[y * 100 + x + d] & 0x80 for d in (-1, 0, 1))


def synthetic(exe):
    import reach
    m = bytearray(10000)
    for y in range(100):                   # a wall: columns 60..99 blocked
        for x in range(60, 100):
            m[y * 100 + x] = 0x80
    for x in range(20, 40):                # an island of floor 2 wide inside rock (rows 10..11 open, rest closed)
        for y in range(5, 17):
            m[y * 100 + x] = 0 if y in (10, 11) and 25 <= x < 27 else 0x80
    m[50 * 100 + 30] = 0x05                # a trigger tile on open floor counts as free
    tamer = centre((40, 50))
    cases = {
        'open ground': ((-1234, -567), (37, 55)),
        'beside the wall, room within one': (centre((59, 50)), (59, 50)),
        'on a trigger tile': (centre((30, 50)), (30, 50)),
        'two tiles into the wall': (centre((61, 50)), (58, 50)),
        'deep in the wall, diagonal': (centre((70, 40)), (58, 50)),
        'in the rock pocket, no room': (centre((25, 10)), (32, 17)),
        'off the map': ((-5300, 5250), (1, 2)),
    }
    got = place(exe, m, [(*e, *tamer) for e, _ in cases.values()])
    for (label, (enemy, want)), (tx, ty, sx, sz) in zip(cases.items(), got):
        assert (tx, ty) == want, (label, (tx, ty), want)
        moved = want != reach.model_tile(*enemy)
        assert (sx, sz) == (centre(want) if moved else enemy), (label, sx, sz)
        if moved:
            assert reach.model_tile(sx, sz) == (tx, ty), label
    # a drop with nowhere to go ends on the tamer's own tile
    closed = bytearray([0x80]) * 10000
    closed[50 * 100 + 40] = 0
    assert place(exe, closed, [(*centre((45, 45)), *centre((40, 50)))])[0][:2] == (40, 50)
    print('%d synthetic placements passed' % (len(cases) + 1))


def reported(exe):
    import dwmap
    import reach
    path = ROOT / 'extracted/MAP/MAP3/GCAN08_1.MAP'
    if not path.exists():
        print('GCAN08_1 skipped: needs extracted/ from the USA disc')
        return
    m = dwmap.MapFile(path.read_bytes())
    walk = reach.walk_area(m)
    points = {}
    for x, z in walk:
        points.setdefault(reach.model_tile(x, z), (x, z))
    drop = reach.model_tile(2811, 370)
    assert drop == (78, 46) and reach.pickup_room(m, drop, walk) == (0, 9), reach.pickup_room(m, drop, walk)
    tamers = sorted((t for t in points if 2 <= max(abs(t[0] - 78), abs(t[1] - 46)) <= 8), key=lambda t: t[::-1])
    res = place(exe, m.collision, [(2811, 370, *points[t]) for t in tamers])
    worst = min(reach.pickup_room(m, r[:2], walk)[1] for r in res)
    assert worst >= 200, worst              # two tiles of standing room at least, against 9 points before
    print('GCAN08_1 78,46 (picked up from 9 points): from %d tamer tiles it moves to %s, picked up from at least %d'
          % (len(tamers), sorted({r[:2] for r in res}), worst))
    # every blocked tile near the walk, the tamer a few tiles away
    near_walls = sorted({(x + a, y + b) for x, y in points for a in range(-3, 4) for b in range(-3, 4)
                         if 0 <= x + a < 100 and 0 <= y + b < 100 and m.collision[(y + b) * 100 + x + a] & 0x80})
    cases = []
    for t in near_walls:
        tamer = next((p for p in sorted(points, key=lambda p: (abs(p[0] - t[0]) + abs(p[1] - t[1]), p))
                      if max(abs(p[0] - t[0]), abs(p[1] - t[1])) >= 2), None)
        cases.append((*centre(t), *points[tamer]))
    res = place(exe, m.collision, cases)
    for case, r in zip(cases, res):
        assert reach.pickup_room(m, r[:2], walk)[1] >= 50, (case, r)   # half a tile of standing room at least
    print('GCAN08_1: %d drops on blocked tiles near the walk all land where the tamer picks them up' % len(cases))


def main():
    tree = Path(sys.argv[1] if len(sys.argv) > 1 else 'build/decomp-dev')
    with tempfile.TemporaryDirectory(prefix='drop-reach-') as temp:
        exe = compile_tree(tree, Path(temp))
        synthetic(exe)
        reported(exe)


if __name__ == '__main__':
    main()
