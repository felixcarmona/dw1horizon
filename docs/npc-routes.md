# NPC route audit

The guard reads all 65 `new_screen` declarations and 126 placements. It checks
shared story predicates, each clock hour, partial recruitment and disappearance
after wild fights. Day and night replacements are never combined. Other story
predicates are independent, conservatively including extra states.

The table records the original placements. Sizes below use the 10-unit walking
lattice and both entity radii; they describe ground remaining outside the body.
A cut is a defect when it separates a used arrival, exit or interaction, even if
winning a wild battle can subsequently remove the enemy. This also enforces the
project's rule against placing new NPCs across passages.

| Screen / placement | Possible state and behavior | Contents of separated ground / decision |
|---|---|---|
| 309 Whamon (750,-650), 37452/13624 | Always on the shore; range 0, no wandering/chase; talk offers the return warp, does not remove him | After the foreground changes, arrival (376,-795), chest interaction east of (-1400,-800), notebook walk (250,-400), and Whamon's talk side share the smaller beach component. Larger wreck-side pocket has no arrival, exit, pickup, step trigger or required talk position. Keep. |
| 314 east Goblimon (1642,935), 84475/420 | Always until beaten; default range 1000, chasing wild encounter; defeated enemy is removed | Small northeast pocket contains no target. Keep. |
| 319 Psychemon (-120,326), 37540/30243 | Always until beaten, chase range 400; coexists with Shamamon by day or Gururumon by night | Separates arrival/exit 0 toward 318 from arrival/exit 1 toward 320. The lower leg has daytime Shamamon; the upper leg has nighttime Gururumon and the inherited Deluxmushrm pickup near (-1050,650). The inherited Digimushrm at (-50,350) is also obstructed by the old body. Move to (-250,250), about 151 units. |
| 319 Shamamon (650,-1150), 49418/18524 | Day 05:00–19:59 until beaten, chase range 400; coexists with Psychemon, never Gururumon | Separates the same two arrivals/exits and the upper leg's Psychemon and inherited pickups; joint day state also isolates the middle leg. Move to (650,-950), 200 units. |
| 320 Shamamon (-550,-750), 104305/24 | Day 05:00–19:59 until beaten; default chase range 1000; Psychemon always, Gururumon night only | Tiny northwest edge sliver is empty. Keep. |
| 333 Psychemon (-1050,-1150), 91958/54 | Day 05:00–19:59 until beaten; default chase range 1000; Gururumon always, Shamamon night only | Tiny west edge sliver is empty. Keep. |
| 344 west Goblimon (-550,-50), 25527/18793 | Always until beaten, chase range 700; both Goblimon coexist | Separates arrival/exit 0 toward 337 from arrival/exit 1 toward 345. East contains the other Goblimon and an inherited Digimushrm pickup at (-50,350); west retains access to the Deluxmushrm pickup near (-1050,650). Move to (-400,-150), about 180 units. |
| 329 Psychemon + Shamamon + Gururumon | Wild encounters; Shamamon is day only, Gururumon night only | Three-way combination cannot exist. Both real two-enemy states connect; even the impossible joint cut contains only eight empty lattice points. Keep. |

Placement-only files retain their donor script 1, including its random ground
items (`story/base/zones/native-forest/s001-0/script.py`). In particular,
Digimushrm at (-50,350) can spawn when its roll is <=24 and Deluxmushrm near
(-1050,650) when its roll is <=1. The guard includes their pickup neighborhoods
(one tile in either direction, `tamer.c:checkItemPickup`). Resident files with
handlers receive empty owned scripts and do not inherit these items. The
remaining inherited item positions lie outside the reviewed empty pockets.
NPC visibility is set by MAPHEAD on screen load (`map.c:changeMap`), so a
newly recruited resident cannot materialize around a player inside a pocket.

The wild encounters above chase and start their existing battles on contact;
talking starts an encounter rather than removing the enemy directly. Wins remove
wild enemies; losses return the player to the city. The cuts are present while
the enemies are alive, rather than permanent post-battle softlocks. The moved
placements have no scripted walk to or from them: they are declared only in
`early-game.py`, so their battle scenes and chase ranges stay unchanged.

The 50-unit preliminary scan also reported splits at 306 (Brachiomon), 325
(Gekomon), 339 (Goblimon) and the joint residents on 362. These connect on the
10-unit lattice. The guard refines preliminary failures before rejecting them.
Accepted empty pockets have explicit world bounds and size ceilings in
`EMPTY_POCKETS`; an interaction or arrival inside one still fails. There is no
size-only exemption and no exemption for either fixed screen.

`python3 tools/check_npc_routes.py` needs no disc: it reads collision and arrivals
from the same authored JSON and foreground edits as the recipes. `--maps DIR`
also verifies every occupied screen's generated collision against those inputs
and uses its generated arrivals. A recipe without declarative geometry fails
closed when an NPC is added. Selftest runs both forms when a build exists, plus
mutation tests restoring the old Bone Field obstruction and introducing a new
Sunken Gallery block at (-500,50).
