# Suijinmon: supported centaur motion

Suijinmon's lower body has four three-bone legs. The front chains are 8/9/10
and 11/12/13; the rear chains are 14/15/16 and 2/3/4. Bone 1 carries the
lower body, 17 the upright torso, 5/6/7 the tail, and 21/22/23/24 and
28/29/30/31 the cannon arms.

The reviewed field generator in
`tools/models/field_animations/suijinmon.py` pins its source model and skeleton.
It builds a four-beat walk and a staggered gallop with stance and swing phases,
folding legs, eased reaches, body weight transfer and delayed tail and arm
motion. The condition walk plays the same supported stride more slowly.
Centarumon's native walk and run provide the visual reference.

| Clip | Before, units per tick | After | Native Centarumon |
| --- | ---: | ---: | ---: |
| Walk | 17.79 | 18 | 17.5 |
| Condition walk | 15.25 | 12 | — |
| Run | 38.82 | 40 | 50 |

The feeding donor crouched its pelvis from -179 to about -99, sinking all four
legs. Feeding now holds the standing lower body, keeps the arm performance,
and reduces the torso bow so the long cannon hand also clears the floor.
Its tail retains a small delayed motion. The mesh, texture and unrelated
animation programs stay unchanged.

`tools/dev/playtest/suijinmon_host.py` checks floor clearance at animation ticks
and interpolated thirds, stance slip, nine-loop closure, speed, changed programs
and both resident and cold animation storage. The final derive provider pins
also include the additional technique aliases.

The sixteen-slot moveset keeps the complete ice range and machine artillery.
Thunder Justice preserves the strongest compatible electric attack from
WaruSeadramon; air becomes the third specialty. Full Potential replaces the
single-stat Power Crane buff. The added electric technique reuses the existing
Pulse Laser casting program, Full Potential uses Aqua Magic's casting program,
and Mail Strome keeps its previous program after moving to the final slot.
