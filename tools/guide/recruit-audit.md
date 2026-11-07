# Recruit source audit

Reviewed against v0.0.7. These ten entries span base quests, script counters,
map-adjusted battle HP, item consumption, timed presence, and mod prerequisites.
The build checks their cited source operations; `test_recruits.py` checks the
resulting facts. No emulator or game runtime changes are part of this feature.

| Recruit | Source | Verified player meaning |
|---|---|---|
| Greymon | `story/base/zones/libraries/s210/script.py`; `content/maps/TWNA02.json` | Jijimon sets the challenge at prosperity ≥15. The placed Greymon has 4800 HP. Leave the house to meet it. |
| Kabuterimon | `story/base/zones/beetle-land/s103-107/script.py`, section 5 | Returns early unless Greymon is recruited. The second invitation choice calls `join_city`; no fight is required. |
| Garurumon | `story/base/zones/freezeland/s091-95/script.py`; `content/maps/FRZL08.json` | MAPHEAD spawns the rematch from the next day at hours 15–23, including later days. Exactly one elapsed day at 15–17 changes the greeting only. Maximum HP is species HP plus 3700, giving 4200; the rematch slot starts at 2100 HP. |
| Vegiemon | `story/base/zones/tropical-jungle/s015-14/script.py`; `story/base/zones/file-city/s162-168-169-170/script.py` | Requires the strange-plant rumor and item 121, Rain Plant. The farm supplies it at internal day 14, displayed as day 15. |
| Drimogemon | `story/base/zones/drill-tunnel/s032-32/script.py`, section 52 | First visit starts the final digging timer. Recruitment waits for `drimogemon_job_days >= 3`; this is three game days from starting that job. |
| Monochromon | `story/base/zones/monochrome-shop/s049-49/script.py`, section 82 | The shift ends at 20 customers. Profit is split into 256-bit units; the recruitment branch follows `shop_hi <= 9`, so it starts at 2560 bits profit. |
| Phantomon | `story/mods/what-the-island-forgot/arcs/residents/phantomon.py` | Screen 56, Grey Lord’s Mansion. Presence requires hour ≥20, giving 20:00–23:59. The authored fight has 1500 HP. |
| Floramon | `story/mods/what-the-island-forgot/arcs/residents/floramon.py` | Screen 4, Native Forest. Check for Sweet Nut, accept the offer, consume it with `take`, then send Floramon to the city. No battle. |
| Clockmon | `story/mods/what-the-island-forgot/arcs/residents/clockmon.py` | Screen 163, Sewer. Hours 11–13 enter the refusal branch; the riddle is available 00:00–10:59 and 14:00–23:59. Answer b, “None at all”, recruits it. |
| Kotemon | `story/mods/what-the-island-forgot/arcs/residents/kotemon.py` | Screen 45, Ogre Fortress. Presence requires the fortress-cleared flag. Win the 1200 HP fight with escape disabled. |

City membership comes exclusively from `content/tables/city-residents.json`.
The snapshot contains 72 recruits worth 144 points according to its current
species levels and the special one-point Numemon, Sukamon and Nanimon rules.
The 50 original recruits contribute 101 points with those snapshot levels.
Otamamon’s battle flag is story progress and is excluded from the roster.

Battle HP is generated from snapshot species data plus each map placement’s
absolute value or delta. Authored mod NPC stats come directly from their Python
AST, so those numbers are not copied into the annotation catalog. The source
review also corrected Betamon to Mangrove Region (15), Birdramon’s nest to
Great Canyon (129), SkullGreymon’s fight to the Underground Lab (221), and
Megadramon to Mt. Infinity (254), whose script is installed by MAPHEAD.
