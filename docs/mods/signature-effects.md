# Signature effects

A species can play an effect of its own for one of its techniques, while every other Digimon that knows the
technique keeps the shared effect. SkullMeramon's Mega Flame plays Digimon World 2's Metal Fireball this way; the
species that have one are listed in [the signature attacks](../reference/signature-attacks.md).

## How a species gets one

- Its species JSON names the technique and the effect chunk:
  `"own_effect": {"technique": "Mega Flame", "chunk": 122}`. The technique must be one of its own techniques.
  `tools/species.py` writes them to the species record (`ownEffectTech` at 0x1CF, `ownEffectChunk` at 0x1D0).
- `getSpeciesTechEffect` (src/main/mod_species.c) is where the battle, the arena and the versus mode pick a
  technique's effect id. It returns `0x100 + chunk` for that species and technique, and `0x100 + technique` for
  everything else. The technique keeps its number, power, range, cost and name. Only the picture and the hit
  test change.
- Chunks 122 and up are appended to `ETCHI/EFEDAT.EFE` after the disc's 122 by the derive step `effects`. The
  loader takes chunk ids up to 0x179 (index 377).
- `content/battle/own-effects.json` lists the chunks: their name, the DW2 files they are converted from, the chunk
  they stand for, a scale, and optionally `hit_scale`, `area` (hit every enemy) and `hits` (damage events). The
  files are `"cast"` and `"hit"`, each either `[model, anim]` (one object at DW2 slot 1) or
  `[[slot, model, anim], ...]` (every object of the technique). `stands_for` is the species' finisher, whose launch
  point the chunk takes; `scale` is the species' model height here over its DW2 head height.

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

| Chunk | DW2 technique | Species | Stands for | Kept in battle memory | Texture |
|---|---|---|---|---|---|
| 122 | Metal Fireball | 277 SkullMeramon | 63 Mega Flame | 7,776 bytes (Mega Flame: 2,600) | 158 x 20, 6 palettes |

The chunk's data lives in the battle's effect heap (0x41000 bytes), loaded with the battle's other effects: up to
16 chunks, 4 fighters x 4 techniques. The largest conversions keep about 17 KB; four of them with the twelve largest
native chunks come to 0x39584, under the heap. The main executable grows only by `getSpeciesTechEffect` and
its five call sites; the converter needs no engine change.

Validation: `python3 -m unittest tools.test_dw2efe` converts small made-up effects and runs the chunks in
`tools/efesim.py`, a model of the effect script interpreter and the sub-opcodes the converter uses: one hit on the
target on arrival, every enemy with `area`, several hits, none for a support technique, flipbooks, rotations,
palette and texture reduction.
