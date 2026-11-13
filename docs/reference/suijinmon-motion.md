# Suijinmon: supported centaur motion

Suijinmon's lower body has four three-bone legs. The front chains are 8/9/10
and 11/12/13; the rear chains are 14/15/16 and 2/3/4. Bone 1 carries the
lower body, 17 the upright torso, 5/6/7 the tail, and 21/22/23/24 and
28/29/30/31 the cannon arms.

The reviewed field generator in
`tools/models/field_animations/suijinmon.py` pins its source model and skeleton.
It builds a diagonal walk (diagonal pairs a little apart, so the thick legs of one side rarely meet) and a staggered gallop with stance and swing phases,
folding legs, eased reaches, body weight transfer and delayed tail and arm
motion. The condition walk plays the same supported stride more slowly.
Centarumon's native walk and run provide the visual reference.

| Clip | Before, units per tick | After | Native Centarumon |
| --- | ---: | ---: | ---: |
| Walk | 17.79 | 18 (14 ticks) | 17.5 |
| Condition walk | 15.25 | 12 (21 ticks) | — |
| Run | 38.82 | 40 (14 ticks) | 50 |

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
and Infinity Cannon uses the same casting program as Pulse Laser in the final slot.

## Shoulder cannon emissions

The cannon meshes have distinct muzzle planes. The upper right/left barrels
are bones 19/27, with local muzzle centres `(0, -35, -154)`. The lower right/left
barrels are bones 20/26, with centres `(0, 0, -73)`. These points come from the
front ring vertices, so they follow the barrels throughout casting.

Suijinmon now uses Machinedramon's effect type and Infinity Cannon finisher
(the native Mugen Cannon attack). Its two native cannon origins map to the
upper battery. Other explicit origins and the fallback map to the lower
battery; forcing the fallback also covers techniques whose donor table uses
an entity-relative origin. No shot inherits a pelvis or leg attachment.
The existing Pulse Laser casting program supports the finisher. The generated
model bytes and provider pins stay unchanged because the previous finisher
and Pulse Laser already shared that program.
