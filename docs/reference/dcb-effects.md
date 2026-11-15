# Digimon Digital Card Battle: attack effects

How Digital Card Battle (DCB, SLUS-01328) draws the attacks of its Digimon, and how
`tools/dcbeffect.py` and `tools/dcbefe.py` turn them into Digimon World effects. Nothing here comes
from the disc into the repository: the tools read the player's own image (`DCB_IMAGE`).

## Short answer: 3D, not card art

A DCB attack is not a 2D card animation. It is a small 3D scene: textured models (balls, rings, claws,
beams) and camera-facing sprites placed in the same world as the two fighters, moved by a script every
step. That is why the attacks can become real Digimon World effects (moving models in the battle
field) instead of flat pictures.

Counted over the signature scripts of the imported Digimon, the objects the scripts start are:

| object | attack scripts | hit scripts | how it is drawn in DW1 |
|---|---|---|---|
| 3D model (kind 15) | 227 | 153 | a model, with its own texture |
| animated sprite (kind 16) | 206 | 115 | a flat sprite that steps through its frames |
| glowing copy of a model (kind 1) | 66 | 36 | the model, blended |
| kind 12 | 48 | 4 | the model it names, else a flat sprite |
| kind 13 | 377 | 232 | the model it names (blended), else its sheet animated, else a flat sprite |
| ribbon trail (kind 17) | 78 | 118 | not drawn |
| screen flash (kind 0) | 163 | 111 | not drawn |
| camera move (kind 3) | 60 | 48 | not used: DW1 keeps its battle camera |

## Where the data is

- `F.DRV`: one pack per card Digimon. Besides the fighter's model it holds a type 2 record, the
  attack's script (`MSCD`).
- `E.DRV/<n>.PAK`: one effect pack per script. A pack is a model file whose record list adds more
  models (type 0, a model file without its 8-byte header), model animations (type 1), animated sprite
  definitions (type 3) and textures (type 5, TIM). A model's texture follows from its texture name
  (`1105_2.tim` is TIM 11052).
- Every attack plays two scripts: the card's own (the scene at the attacker and what flies to the
  defender) and a shared hit script (435, 437, 2000, ...: the impact on the defender).

## The script language

A script is `MSCD`, u32 3, u32 size, u32 variable count, then 4-byte aligned instructions, each
starting with u16 op, u16 a:

| op | meaning |
|---|---|
| 5 | jump; the target counts from the code (after the 16-byte header) |
| 6, 8 | inline data blocks |
| 7 | variable a = / += / -= / *= / /= / %= / random below the value (or another variable) |
| 9 | skip the next instruction when variable a == <= >= != > < the value |
| 0xA-0xE | commands with 0-4 arguments (each a constant or a variable) |

Commands the tools use:

| command | meaning |
|---|---|
| C 0 (slot, kind) | define the object in a slot from the current variables |
| C 1 (slot, type) | change its motion type |
| C 2, 3, 4 | atan2, sin, cos into variable 1 |
| B 8 / B 9 (slot) | start / stop the object |
| B 6 (slot) | give a running object new variables (a new motion segment) |
| B 15 (slot) | copy an object's variables back into 400-453 |
| B 10 (n) | wait n steps (when variable 0 is -1) |
| D 0 (TIM, column, half) | load a sprite sheet into VRAM (x = column x 64 halfwords, y + 256 per half) |
| B 0, 2, 3, 7 | banner, attacker animation, sounds (kept as events, not converted) |

An object's variables: 407-409 start, 410-412 end, 413 speed, 414 acceleration, 415-417 rotation,
418-420 its speed, 421-423 its acceleration (/64), 424-426 scale, 427-429 the scale it grows to,
430-432 the growth per step (4096 = 1), 433 arrival radius, 434 delay before it shows, 437 motion
type, 438-440 wave phase, amplitude and frequency, 441 and 446 what it is attached to, 442 model or
sprite definition, 41-43 colour (128 = unchanged), 29-30 blending, 84-87 the sprite's VRAM rectangle,
88-89 its palette.

## Motion

The executable's table at 0x800108B0 gives each motion type a class:

- S: stays at the start.
- L: from start toward end at speed v and acceleration a (distance v t + a t^2).
- A: L plus a jump arc on y.
- W / V: L plus a sine wave on x / y.
- T / U: L plus an arc tilted by the z rotation.
- Types 11-28 also say what happens on arrival, in threes: stop, snap to the end and freeze, vanish.

Rotation is start + speed t + acceleration t^2 / 64; the scale moves toward its end value and stops
there. Types 90 and up do not use this table (bone-attached objects); the tools hold them still.

## Animated sprites (type 3 records)

char[16] texture name, u32 1, u32 frame count, i16 loop (-1 loops), u16 0, palette x, y, sheet x, y,
then 20 bytes per frame: u32 steps, u8 u0, u1, v0, v1, u16 width, height, u16 flags, u16 0x80, i16 0,
i16 offset.

## Conversion to a DW1 effect

`tools/dcbefe.py` traces both scripts, keeps the steps in which something is drawn and turns them into
the input of the DW2 converter (`tools/dw2efe.py`), which writes the 20 KB EFEDAT chunk:

- Units: DCB's fighters stand 5000 apart, DW2's 10240, so positions are scaled by 2.048 and then by
  the DW2 converter's own 0.266.
- Time: one DCB step is taken as one 30 Hz frame. A DW1 cast object lasts at most 60 frames and a hit
  object 30, so longer timelines are resampled evenly (WarGreymon's cast plays 1.9 times faster, its
  hit 3.8 times).
- Each species has its own chunk id, from `content/finishers/dcb-effects.json` (the DCB range is
  251-329), with the two scripts its effect comes from.
- The attack script becomes the cast (at the attacker, facing the defender); the hit script becomes
  the hit (on the defender).
- When the chunk is too full, the converter gives up detail in this order: animated sprites keep 4
  frames, then 2, then 1; the textures shrink to a half, then a quarter (on top of the halving the DW2
  converter always does); groups of alike objects (a swarm of sixty sparks) keep an evenly spread few.
- Object scale is applied in each model bone's own frame (DW1 cannot draw a sheared bone).
- Sprite colours are baked into the palette; sprites tinted black are left out.
- A sheet named without a frame list is read as 64 x 64 frames (an estimate).
- Not converted: screen flashes, camera moves, ribbon trails, sounds and banners.

`python tools/dcbefe.py convert <species> <out> --render` writes the chunk, a record of
what was kept and dropped, and frame sheets of the traced original and the converted chunk;
`python tools/dcbefe.py grid <out> <video.mp4> <names...>` puts several side by side.

## Fidelity check

Every rendered conversion is compared with the traced original on the same stage and camera, the cast
and the hit apart (`fidelity_parts` in `tools/dcbefe.py`):

| number | what it measures | must be at least |
|---|---|---|
| area | mean drawn area, converted / original | 0.3 |
| shown | share of the original's busy moments in which the conversion draws something | 0.5 |
| box | overlap of where they draw (intersection / the smaller area) | 0.3 |
| curve | correlation of the drawn area over time | 0 |

A conversion that fails any part is not counted as converted and is left out of comparison videos.
`thin_source` marks originals that draw very little, where the numbers say less.

When the first fit fails, one more round tries denser fits (more alike objects while the slot holds
them, `DENSER`) and keeps the one with the fewest failed checks.

Results for the 79 attacks are in `content/finishers/dcb-effects.json` (`result`):

| result | attacks |
|---|---|
| converted (passes every check) | 45 |
| fidelity failed after the second round | 31 |
| render did not finish in 40 minutes (MetalGarurumon) | 1 |
| does not fit the 0x5000 slot even at the smallest fit (MarineAngemon: its models alone are bigger than the slot; Gomamon: about 2 KB over) | 2 |

Each conversion is measured against the launch table of the finisher it stands for (the one the game plays it
with); Angewomon, Omnimon and VioletElecmon passed against the shared table and fail against their own. The 34
that did not pass carry a `why` (the checks they failed) and a `"fallback"`: `"template"` plays the finisher it
stands for, unchanged; `"composed"` (12 of them) is a DW1 chunk of the attack's kind recoloured
(docs/mods/signature-effects.md, "Composed effects"), used where the template's look contradicted the attack (a
projectile for a slam, a whirlpool for a sword cut). Most
failures are a cast that draws much less than the original: many alike objects (star showers, feathers)
thinned to what the slot holds. The check has a floor and no ceiling and does not compare colour: a pass
means the conversion draws in the same places and moments, not that it looks the same.

## Open questions

- The step rate (30 Hz) and the size of a sprite texel in the world (16 units) are estimates.
- Bone-attached objects (motion types 90 and up) are held still at their start.
- What kinds 1, 12 and 13 do exactly is read from the variables they use, not from the executable's
  drawing code: they are drawn as the model or sheet they name.
