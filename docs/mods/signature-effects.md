# Signature effects

A species can play an effect of its own for one of its techniques, while every other Digimon that knows the
technique keeps the shared effect. SkullMeramon's Mega Flame plays Digimon World 2's Metal Fireball this way; the
species that have one are listed in [the signature attacks](../reference/signature-attacks.md).

## How a species gets one

- Its species JSON names the technique and the effect chunk:
  `"own_effect": {"technique": "Mega Flame", "chunk": 122}`. The technique must be one of its own techniques.
  `tools/species.py` writes them to the species record (`ownEffectTech` at 0x1CF, `ownEffectChunk` at 0x1D0).
- `getSpeciesTechEffect` (src/main/mod_species.c) is where the battle, the arena and the versus mode pick a
  technique's effect id, from the species and a move byte of its stats (it does the `DIGI_PARA` lookup the call
  sites did). It returns `0x100 + chunk` for that species and technique, and `0x100 + technique` for
  everything else. The technique keeps its number, power, range, cost and name. Only the picture and the hit
  test change.
- Chunks 122 and up are appended to `ETCHI/EFEDAT.EFE` after the disc's 122 by the derive step `effects`. The
  loader takes chunk ids up to 0x179 (index 377).
- `content/battle/own-effects.json` lists the chunks: their name, the DW2 files they are converted from, the chunk
  they stand for, a scale, and optionally `hit_scale`, `area` (hit every enemy) and `hits` (damage events). The
  files are `"cast"` and `"hit"`, each either `[model, anim]` (one object at DW2 slot 1) or
  `[[slot, model, anim], ...]` (every object of the technique). `stands_for` is the species' finisher, whose launch
  point the chunk takes; `scale` is the species' model height here over its DW2 head height.
- An entry converted from a DW2003 technique has `"dw3"` in place of the DW2 files: `{"model": "M170IVRU",
  "slot": 9, "meft": [335], "pin": SHA-1}`, plus `leave_out` when parts do not fit (below). It has no scale,
  `area` or `hits`: it is gameplay-neutral, one target and one hit, as the finisher it stands for.

## Converting a DW2 technique

`tools/dw2efe.py` turns a DW2 technique's effect objects into one chunk: every cast object (DW2 slots 0 above the
head, 1 the launch point, 2 the feet) and every hit object. `convert_skill(casts, hits, ...)` takes them as
`(slot, effect)` lists, and the build uses it for every own effect; `convert(cast, hit, ...)` is its one-cast,
one-hit form. It reads them from the player's DW2 disc (`derive build --source-disc dw2=IMAGE`). The format of DW2
effects is in [the DW2 effect notes](../reference/dw2-effects.md).

- **Model.** Every drawn bone becomes TMD objects of flat, textured, unlit prims, semi-transparent with the DW2
  prim's blend mode. A flat or mirrored part is written with both windings, so it shows from behind as well. Prims
  whose texels are all transparent, and faces DW2 lists twice, are left out. Each object keeps only the vertices
  its prims use, and bones that draw the same card share one object.
- **Poses.** A pose is any rotation (as Y, X, Z angles), a scale per axis (negative for a mirror) and a 3D
  translation; only a shear, which `drawTMDYXZ` cannot draw, stops the converter. The distinct poses are nine
  tables (one per field, or a constant), and each part has a table of pose ids per tick. The battle logic ticks at
  20 Hz, so tick t shows DW2 frame 1.5 t.
- **Flipbooks.** A DW2 texture animation (a rectangle copied each frame) becomes a UV animation: its frames sit side
  by side in the strip and the engine's `initializeUVAnim` steps the prims' UVs through them, one engine tick per
  DW2 frame step. They are started once and run while the chunk is loaded.
- **Texture.** The chunk's texture slot is 256x32 texels with 6 palette rows. Each DW2 block is reduced (2 by
  default; more, or turned on its side, when it does not fit): each f x f group becomes the palette colour closest
  to its average, or transparent when half of it is. The factors are reported per conversion.
- **Palettes.** More than 6 palettes are merged into 6: the two closest by the colours their texels use, never
  merging a transparent, solid or blending colour with another kind, so blending stays as DW2 has it. Here only
  colours with the top bit blend, and colour 0 is transparent. A DW2 palette with neither (Metal Fireball's ring,
  0x3f80: a plain blue-to-green gradient) would draw its whole square opaque, so the converter makes its colour 0
  transparent and the others blend.
- **Fitting the slot.** When the chunk is over 0x5000 bytes the converter retries coarser, in order: each pose held
  2-4 ticks, translations and scales rounded to 2-4 units (angles to 32-64), the texture strip limited to 128 wide,
  and last one-sided flat parts. The level used is reported (`detail`).
- **Scale.** `scale` turns DW2 units into this game's (0.266: the DW2 SkullMeramon's head height against this
  game's). `hit_scale` sets the hit objects' own (0.1): DW2's hit objects were made for a close camera. A support
  technique's hit objects play on the caster at the cast's scale.
- **Travellers and hits.** A cast object whose lead part moves forward at least 30% of the way between the rows is
  a traveller: before its launch tick it plays at the launch point; from the launch it flies to the target, its
  forward travel stretched to the real distance, and the hit comes on arrival. Without a traveller the hit comes at
  the end of the cast (at most 40 ticks), at the target. The hit objects play at the target (slot 0 above the head,
  1 mid height, 2 the feet), turned toward the caster; the damage is `addAttackObjectToTarget`, once per hit event
  (`hits` spread over the hit objects' life).
- **All enemies.** With `area` (a range-3 technique, DW2 target "all enemies") the chunk does what DW1's own range-3
  chunks do: it walks the fighters with `selectNextTargetEntity` and starts the hit (and a traveller) once per
  target, up to three, so every enemy is hit. Like DW1's own area chunks it walks every living fighter but the caster.
- **Sound.** The chunk plays this game's sound effects 2 (start) and 14 (launch, travellers only). In DW2 the caster
  shouts the technique's name: a voice line streamed from the disc as XA audio (Metal Fireball:
  `AAA/2.XAP/SHOT0011.XAP`, channel 1). This game's battles have no voice lines, so it is not carried.
- The build needs the DW2 disc for these chunks, as it does for the imported species.

## Converting a DW2003 technique

`tools/dw3efe.py` turns a DW2003 technique's 3D effects (the `MEFT####.BIN` files its battle model's script
spawns) into one chunk through the same converter: each effect placed where the script spawns it, in the caster's
frame, at the field's scale (this game's fighters stand 2700 units apart, DW2003's 10 752), for its whole length,
played as on the disc with the hit when it ends. The format and the conversion are in
[the DW2003 effect notes](../reference/dw3-effects.md). The build reads the model and the effect files from the
player's DW2003 or Digimon World 3 disc (`derive build --source-disc dw2003=IMAGE`; `tools/discs.py`
`DW3_EFFECT_FILES` pins them, equal on all three releases). The models' scripts and the effect files give the same
chunks on the European, USA and Japanese discs, and `pin` records that chunk's SHA-1.
`tools/test_dw3_ports.py` checks the wiring, and with the discs (`DW3_IMAGE`, `DW3_US_IMAGE`, `DW3_JP_IMAGE`)
builds every port to its pin and runs the fidelity check against the original technique. Chunks 196 to 222 are the
3D effects' (`EFFECT_IDS`).

| Chunk | DW2 technique | Species | Stands for | Kept in battle memory | Texture |
|---|---|---|---|---|---|
| 122 | Metal Fireball | 277 SkullMeramon | 63 Mega Flame | 7,776 bytes (Mega Flame: 2,600) | 158 x 20, 6 palettes |
| 162 | Nightmare Shock (composed) | 295 Vilemon | 62 Death Claw | 5,804 bytes (as Death Claw) | Death Claw's, purple |
| 163 | Poison Cobweb (composed) | 298 Dokugumon | 72 Sweet Breath | 7,724 bytes (as Sweet Breath) | Sweet Breath's cloud replaced by chunk 105's web, green |

## Composed effects

A species with no DW2 technique to convert gets a composed effect: one of the disc's own chunks (its template)
with a look of its own. `tools/efecompose.py` copies the template and changes only its texture (pictures copied
from other disc chunks), its colours and its model's size. The script, its variables, the launch table and the timing stay byte for byte, so the technique plays,
travels and hits exactly as the template does. The chunk is built at derive time from the player's disc, like
every other chunk here; nothing of the disc is committed.

The entry in `content/battle/own-effects.json`:

```json
"162": {"name": "Nightmare Shock", "stands_for": 62,
        "compose": {"recolour": {"ramp": ["#14001e", "#5a1494", "#c870ff", "#f4dcff"]}, "scale": 1.3},
        "check": {"hue": 280}}
```

- `stands_for`: the template, a disc chunk (0-121). It is the chunk of the finisher the species' technique uses
  (the technique's effect id less 0x100), so the launch point and the hit stay those the technique was balanced
  with. Use the technique the species keeps as its finisher (the last of its `techniques`).
- `compose.recolour`: the new colours of every palette colour of the template's texture, and of the colour
  vectors its script hands the engine (sprite tints, model colours).
  - `"ramp"`: two or more colours from dark to bright. Each colour takes the ramp's colour at its own brightness.
    Effects blend additively, so the brightest end is what reads; keep it light.
  - `"hue"`: degrees (0 red, 120 green, 240 blue), each colour turned to that hue, with `"saturation"` as a floor
    (0-1, default 0.6).
  - `"rows"`: only these palette rows (default all).
  - Colour 0 stays transparent, the semi-transparency bit stays, and no visible colour becomes 0.
- `compose.texture`: a list of texel rectangles copied over the template's texture before the recolour, each
  `{"from": chunk, "rect": [u, v, w, h], "to": [u, v], "palettes": [[from row, to row]]}` (`to` defaults to the
  same place; u and w even). It gives the template's sprites or faces a new picture: Poison Cobweb's breath
  sprites draw chunk 105's web. Which rectangle a template's sprites use is in the simulation's sprites
  (`u, v, w, h` and the palette row) and its prims' UVs. The texture is uploaded to video memory and not kept,
  so this costs no battle memory.
- `compose.scale`: the template's 3D model resized, one factor or `[x, y, z]`. Sprites keep their size. 1.2-1.5
  makes a template read as a different, heavier technique; the hit test does not change.
- `check.hue`: the main hue the effect must show, for the check.

The species JSON then names the chunk: `"own_effect": {"technique": "Death Claw", "chunk": 162}`, the technique
being the template's.

Engine effects that a script asks for by number (clouds, flashes, particle emitters, screen sprites) are drawn
by the engine with its own colours: a composition cannot recolour them. The check lists them.

### Making one

1. Read the design's `look` (the technique's design). When the template's picture does not fit it (a cloud for a
   web), find a disc chunk whose texture has the right one and copy it with `texture`. Then pick the colours. Pick a ramp whose dark end is nearly
   black and whose bright end is the look's colour almost white.
2. Chunks 162-195 are for composed effects. 162 and 163 are taken. The others go to the species of the
   composed-effects list in its order, from 164, skipping Vilemon and Dokugumon.
3. Add the entry and the species' `own_effect`, then render the sheet and look at it:
   `python -m tools.efecompose sheet KEY --out SHEET.png`. The template's frames are above, the composed ones
   below, at the same ticks, each column cropped around what either draws at that tick. The composed row must read as the look and not as a
   recoloured copy of the template: if it does not, change the ramp or the scale.
4. Check it: `python -m tools.efecheck --composed KEY`. Its `distinct` measure counts any change of colour, so a
   plain recolour passes it: only the sheet tells whether the effect reads as its own. It runs the template and the composed chunk through
   `tools/efesim.py` (no DW2 disc) and fails when:
   - **the technique changed**: a byte changed outside the palette, the copied texels, the model's vertices and the
     script colours,
     the launch table differs, or the run's draws, sprites, hits, hit tests or sounds differ from the template's;
   - **it is empty**: per phase (cast before the first hit, hit after; one phase when the simulation deals none)
     the energy or the coverage of the frames is under 0.35 of the template's, or the box (median diagonal over
     the lit frames) is outside 0.5-3 times the template's;
   - **the hue is off**: the main hue (the chroma-weighted circular mean over the pixels with saturation over 0.25)
     is more than 35 degrees from `check.hue`;
   - **it is the template**: the summed RGB difference of all frames is under 0.25 of their summed RGB.
5. Add the row to the table above. `python -m unittest tools.test_efecompose` checks every composed entry too.

A sheet and a check take about 15 seconds. The chunk keeps the template's size, so the memory the battle keeps is
the template's.

The chunk's data lives in the battle's effect heap (0x41000 bytes), loaded with the battle's other effects: up to
16 chunks, 4 fighters x 4 techniques. The largest conversions keep about 17 KB; four of them with the twelve largest
native chunks come to 0x39584, under the heap. The main executable grows by 112 B: `getSpeciesTechEffect`'s
140 less 28 its two resident call sites save (the patches after it, which call `digimonPara`, `raiseRow`
and the evolution rows out of line, give 2,656 B back); the converter needs no engine change.

Validation: `python3 -m unittest tools.test_dw2efe` converts small made-up effects and runs the chunks in
`tools/efesim.py`, a model of the effect script interpreter and the sub-opcodes the converter uses: one hit on the
target on arrival, every enemy with `area`, several hits, none for a support technique, flipbooks, rotations,
palette and texture reduction.
