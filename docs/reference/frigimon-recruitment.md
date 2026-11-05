# Frigimon recruitment and food-induced sickness

Foods with a sickness chance call `handleItemSickness`. The original US routine
formatted the partner's name and the translated illness suffix into a 24-byte
stack buffer. Valid names and translated suffixes exceed that capacity. Feeding
Happymushrm in Spanish reproduces a non-returning handler and CPU exception at
`0x80000080` on the v0.0.6 disc with 2 MB RAM. This happens before Frigimon's
script or an ending routine is needed.

The renderer now draws the name first, measures its width with the active font,
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
