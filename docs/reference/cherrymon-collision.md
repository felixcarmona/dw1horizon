# Cherrymon's walking footprint

The PT-BR Android recording called “Passage to Town City” is screen 119,
Misty Trees (`MIST05`), ending at the northwest exit to Toy Town (144).
Cherrymon has moved to his post-conversation position (the script targets
(-2017, 1378); the NPC root can advance during its movement animation).

Frame-by-frame background alignment places the tamer near these points (world
coordinates are approximate because they are recovered from video feet pixels):

| Frame | World x,z | Tile x,z |
|---|---|---|
| 75 | -1974, 938 | 30,40 |
| 150 | -2239, 938 | 27,40 |
| 250 | -2355, 958 | 26,40 |
| 320 | -2598, 1087 | 24,39 |

The original, v0.0.7 and main MAP collision bytes agree here: all these tiles
are free. The tile grid also shows that the northwest exit approach is broad,
connected floor. The narrow stripe at column 40 is step trigger 51, not a wall.
Opening tiles cannot resolve this particular obstruction.

`entityCheckEntityCollision` in `map.c` adds another obstacle: Cherrymon's
400-unit square extends from x=-2417 to -1617 and z=978 to 1778. With the tamer's
100-unit radius, it stops northward movement across the empty southwest corner
until the tamer moves west of x=-2517. That matches the video's sideways detour.
The visual trunk occupies less ground than the square enclosing the branches.

PCSX-Redux reproduces the obstruction on the v0.0.7 disc with the original
400-unit radius. From (-2400,900), northward input stops at z=1050 in the
observed NPC pose; reducing only its loaded radius to 250 lets the same input
reach z=1250. Approaching from the west at z=1400 stops at x=-2550 before
the change and x=-2400 after it. The observed free heap remains 152104 bytes.

The field-only NPC twin (464) now uses a 250-unit trunk footprint. Its disc mesh,
height, skeleton, texture and animation remain disc-derived. The partner (121)
keeps its own radius. Static walls, props, step triggers and exits retain their
collision tiles. This changes data only, with no new heap or resident storage.

The NPC validator permits a smaller radius only with a nonempty authored walking
review (`_npc_collision_review`); all other disc-derived NPC properties remain
checked against the original.
