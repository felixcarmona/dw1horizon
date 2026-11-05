# Recruit screen encounters

## Lava Cave preferences

Gomamon, Ikkakumon and Zudomon retain favored regions 5, 4 and 3.
The species `partner` record has one `favored_region` byte, with no independent
hated map or region. Each map compares that byte against its `regionA` (liked)
and `regionB` (disliked) lists (`loadMapSetup` in the engine).

Drill Tunnel and Lava Cave maps currently dislike regions 1 and 8. Assigning
one of those to these species would replace their favorites. No preference
change is made: an independent hated-place setting needs a separate format and
engine change.
