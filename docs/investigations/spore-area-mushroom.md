# Happy Mushroom inside the Spore Area chests

The original scripts spawn a Happy Mushroom before spawning the three treasure
chests. `spawnChest` then calls `setImpassableSquare(tileX, tileY, 2)`, which blocks
the 4×4 square from `tile - 2` through `tile + 1`. The mushroom lies inside that
square in two versions of Mt. Panorama Spore Area. Opening the chest does not
remove its blocked footprint.

| Screen | Script | Original mushroom tile | Overlapping chest position | Replacement tile | Pickup ID |
| --- | --- | --- | --- | --- | --- |
| 21 | 22 | 84,49 | 3545,155 | 73,49 | 61 |
| 234 | 190 | 59,42 | 985,856 | 48,42 | 232 |

This is inherited from the original game. The ordinary floor collision alone
does not reveal it: the chest changes collision at runtime after the item spawns.
Screen 233 has no corresponding chest overlap and keeps its original location.

With the chest footprints applied, screen 21 has no reachable pickup position
for its original mushroom. Screen 234 retains a narrow approach: 105 reachable
positions in the pickup window, with none on the item's own tile. The left-side
approach shown in the report stops at the chest. The late mushroom is hidden and
awkward to retrieve rather than completely unobtainable.

The fix uses `at` overrides in `content/ground-items.json`. Original script
coordinates remain the stable keys, so existing daily-pickup bits still refer to
the same items. The random-roll conditions, items, chest rewards and chest flags
are unchanged.

With all three chest footprints applied, the engine body-box simulation gives
the replacement tiles 90 and 100 reachable positions respectively, and 734 and
870 in their pickup windows. Both exceed the pickup checks' minimum standing
room. The original locations fail because they are blocked.

`tools/test_ground_items.py` checks the overlap against the authored chest
positions, clearance of the replacements, instruction rewriting and preservation
of the existing save IDs.
