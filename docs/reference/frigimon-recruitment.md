# Frigimon recruitment and food-induced sickness

Foods with a sickness chance call `handleItemSickness`. The original US routine
formatted the partner's name and the translated illness suffix into a 24-byte
stack buffer. Valid names and translated suffixes exceed that capacity. Feeding
Happymushrm in Spanish reproduces a non-returning handler and CPU exception at
`0x80000080` on the v0.0.6 disc with 2 MB RAM. This happens before Frigimon's
script or an ending routine is needed.

The shared food-sickness patch draws the name first, measures its width with the active font,
and draws the translated suffix after it. No concatenation buffer is needed.
The food's illness chance and care effects stay the same. The focused host
harness compiles the actual C routine with address and undefined-behavior
sanitizers, covering all translated suffix sizes, name lengths 1..19, injury
replacement, an already sick partner and a zero-chance outcome.

The rescue uses base flag 133, named `digivolve_scene_seen` in the inherited
story sources; Frigimon's recruitment uses 223. Neither is allocated by the
extended story's save lock. An eligible sick partner on Freezeland calls script
203 section 51, which takes the player to Frigimon's house (137), script 132
section 51. The rescue removes illness, sets 133 and returns to Freezeland (94).
Returning with a cold-resistant partner reaches script 132 section 5, which
recruits Frigimon and adds two prosperity points.

`tools/dev/playtest/frigimon_recruitment.py` exercises feeding through the item
menu before the rescue and recruitment scenes. Its deterministic sickness roll,
care setup and fixture evolution isolate the route; the game scripts set the
rescue/recruit flags and prosperity. `--before` captures the feeding exception
on an unfixed disc. The reported accidental credits transition is not a required
part of this regression test; the reproduced failure is stack corruption during
food-induced sickness.


## Player-route replay

After merging the shared food-sickness and evolution grace-hour fixes, use
`tools/dev/playtest/frigimon_player_route.py` with `--route inventory`,
`--route care` or `--route climate`. Each run boots the current image on 2 MB
and selects Spanish. Inventory, initial care values, species and positions are
fixtures. The food cases feed Happymushrm through the selected menu until its
unchanged 30% sickness chance succeeds; no random result is forced. The climate
case starts with no area exposure and waits in Freezeland with Agumon until the
normal disliked-area rule causes illness.

The rescue starts from the real section-51 field tile. It must cure the partner,
set rescue flag 133 and leave recruit flag 223 clear. A fixture evolution loads
Gabumon for the return visit. The real section-52 door tile opens the house;
collision and confirm input start Frigimon's conversation. The script must set
223, award exactly two prosperity points and return control. A passive hook
checks that the tamer's ending routine is never entered. Setup clears the rescue and recruit flags. No script section is invoked
directly, and no sickness, rescue or recruit success is injected.

`tools/dev/playtest/food_sickness_host.py` is the shared sanitizer test for the
food handler. The earlier `frigimon_recruitment.py --before` remains useful for
reproducing the released stack corruption; its scripted route and forced food
roll are less comprehensive than the player-route replay.
