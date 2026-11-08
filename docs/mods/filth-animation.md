# Filth-family animation and movement sounds

BlackKingNumemon uses its own imported neutral articulation for slug locomotion,
praise (11), unfair scold (12), fair scold (25) and victory (42). The old field
walk/run repeated the idle body performance, while Etemon's donor care clips
rotated eye and crown joints like limbs. The replacement gives the front body,
head, eye stalks and rear shell separate phases. Smooth periodic curves provide
compression, breathing, anticipation and settle. The crown retains its local
orientation over the rear shell; the eyes do not inherit donor arm rotations.

Field walk/condition/run speeds are 20/14/38 units per tick, using native-scale
travel instead of the imported donor momentum (about 39.4/31.4/78.8). Flee and battle
walk/run (27/35/36) use the same slug articulation and preserve their previous
average travel (rounded to a whole-unit cycle distance). Sampled mesh bottoms
set the body carrier height; eye and crown joints keep their attachment points.
The six locomotion clips repeat without body drift over nine decoded cycles.
Every other animation program, mesh, texture and skeleton remains unchanged.
The existing battle reach pass still runs afterward.

Movement sounds are postprocessed after the model's field and battle passes:

| Species | Native reference | Bank / note | Slots |
| --- | --- | --- | --- |
| Gesomon | Seadramon / Tylomon | 1 / 17 | 2, 3, 4, 27, 35, 36 |
| Octomon | Seadramon / Tylomon | 1 / 17 | 2, 3, 4, 27, 35, 36 |
| ShellNumemon | Numemon | 1 / 24 | 2, 3, 4, 27, 35, 36 |
| BlackKingNumemon | Numemon | 1 / 24 | 2, 3, 4, 27, 35, 36 |

ShellNumemon previously had movement events using note 13, rather than native
Numemon's note 24. Gesomon and Octomon's field programs had no movement events.
Existing event times are preserved when changing a sample. Silent loops receive
a pulse every 20 ticks, starting at tick 7 or earlier for a shorter loop.
BlackKingNumemon's new gait pulses twice per body cycle. The sound pass preserves
all non-sound instructions, initial poses and texture events. Only explicitly
selected movement slots change. Unreferenced programs are discarded and
byte-identical streams shared to keep resident animation storage bounded.

No runtime C or patch-series changes are required. The build checks the final
model resident limit (100352 bytes), each sector-aligned cold read (8192 bytes)
and the original PlayStation heap budget. Species-provider pins cover the final
model bytes. Unit tests replay synthetic shared movement programs for nine
cycles and compare poses, root travel, texture events and untouched slots.

Rebalance decisions remain in [FILTH-PROPOSAL.md](../../FILTH-PROPOSAL.md).
No specialty, technique, evolution requirement, finisher or icon changes are
included in this repair.

## Validation

The full nine-language build passes with `main_BSS_END = 0x801ce104`,
a 187888-byte heap and 31536 bytes free on the tightest swept screen (OGRE03).
Final resident model sizes are 67746 bytes for ShellNumemon, 88442 for Gesomon,
90622 for Octomon and 82486 for BlackKingNumemon. Every sector-aligned cold
animation read remains within 8192 bytes.

Thirteen forced-slot playback checks pass on the completed disc in original
2 MB mode: walk/run for all four species, then BlackKingNumemon's praise,
both scold reactions, victory and battle run. Observed animation frames advance,
and real `playSound` calls select note 17 for the aquatic species and note 24
for the Numemon relatives. Rendering, model loading and audio use the game engine;
the fixture selects the clips directly and anchors their world positions for framing. Natural raising, care-menu triggers and
a full battle sequence are separate from this playback check.
