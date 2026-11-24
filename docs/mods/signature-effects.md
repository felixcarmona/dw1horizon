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
  "slot": 9, "meft": [335], "pin": SHA-1}`, plus `leave_out` when parts do not fit (below), and `"aim": true` for
  a shot that flies to its target (a ball, not a beam): its flying part is aimed at the target, stops and vanishes
  at the target's body, and the hit lands there, at any distance (Guilmon's Pyrosphere). It has no `area` or
  `hits`: it is gameplay-neutral, one target and one hit, as the finisher it stands for.

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
| 226 | Cyclone Turbine (composed) | 306 GrapLeomon | 62 Death Claw | 5,804 bytes (as Death Claw) | chunk 15's wind streaks on a wider, taller ring, teal |
| 236 | Blade Twister (composed) | 322 Kyukimon | 62 Death Claw | 5,804 bytes (as Death Claw) | chunk 13's jagged blades on a wider ring, green |
| 256 | Hawk Beam (composed) | 184 Hawkmon | 71 Boom Bubble | 6,036 bytes (as Boom Bubble) | chunk 9's streak in place of the air puff, red |
| 262 | Metal Wolf Claw (composed) | 191 MetalGarurumon | 78 Genoside Attack | 13,872 bytes (as Genoside Attack) | chunk 20's ice crystal in place of the fire burst, icy blue, model 1.2x |
| 265 | Ex-Laser (composed) | 194 ExVeemon | 63 Mega Flame | 2,600 bytes (as Mega Flame) | chunk 29's ring in place of the fireball, blue-white |
| 321 | Thunder Volt (composed) | 252 Thundermon | 86 Solar Ray | 11,244 bytes (as Solar Ray) | chunk 66's lightning on the model and its spark on the orb, electric blue, model 1.3x |
| 278 | Needle Spray (composed) | 208 Togemon | 91 Fist of the Beast King | as the template | chunk 69's streaks, green, model drawn out 1.8x |
| 283 | V Wing Blade (composed) | 213 AeroVeedramon | 89 Iga School Knife Throw | as the template | chunk 39's crescent, blue, model 1.5x; the template (96) is a pair of demon hands |
| 301 | Free Throw Bomb (composed) | 232 BomberNanimon | 73 Bit Bomb | as Bit Bomb | chunk 39's ball, orange, model 1.5x; the template (89) throws knives |
| 307 | Pulse Blast (composed) | 238 Dolphmon | 90 Blasting Spout | as the template | chunk 112's rings, cyan, spout 2.5x taller |
| 320 | Solar Flare (composed) | 251 Solarmon | 86 Solar Ray | as Solar Ray | chunk 94's ring on the orb, white-gold, model 1.4x; the template (70) is a small flame |
| 327 | Darkness Zone (composed) | 400 Apocalymon | 74 Deadly Bomb | as Deadly Bomb | chunk 35's swirling darkness on the orb and its burst, deep purple, model 1.6x; on Frozen Fire Shot (97) the technique dealt no damage |
| 165 | Fungus Cruncher (composed) | 263 Mushroomon | 72 Sweet Breath | as Sweet Breath | chunk 28's spores in place of the cloud, purple; the DW2 source is a self-cast buff and the template (75) a drill |
| 166 | Kongou (composed) | 276 Baihumon | 81 Pummel Whack | as Pummel Whack | chunk 105's crystal, white-gold, model 1.4x; the DW2 source is a self-cast guard and the template (78) a missile volley |
| 267 | Tempest Wing (composed) | 196 Halsemon | 106 Infinity Cannon | as Infinity Cannon | chunk 15's wind streaks on the beam, pale green, 1.3x wider; the template (69) throws needles |
| 271 | Star Shower (composed) | 200 Pegasusmon | 93 Electro Shocker | as Electro Shocker | chunk 24's star in place of the spark, gold; the template (84) is a dive |

## Converting a Digital Card Battle attack

`tools/dcbefe.py` turns a Card Battle attack (the card's own script and the shared hit script, with their effect
packs) into one chunk through the same converter; the format and the conversion are in
[the Card Battle effect notes](../reference/dcb-effects.md). An entry has `"dcb"`: `{"attack": 1105, "hit": 435,
"fit": [4, 1, 24], "pin": SHA-1}`, `fit` being the animated sprite frames, the texture reduction and the alike
objects per script it was converted at (`null`: all). Like a DW2003 port it is gameplay-neutral: one target, one hit,
as the finisher it stands for. The build reads `F.DRV` (the scripts) and `E.DRV` (the packs) from the player's Card
Battle disc, which it already reads for the imported species (`derive build --source-disc dcb=IMAGE`); both are
pinned per release in `content/imports/releases/dcb-*.json`. The USA and European discs give the same chunks; the
Japanese one has its own `pins` where it differs.

Chunks 251-329 are the Card Battle attacks', one per species of `content/finishers/dcb-effects.json`. Only the
attacks whose conversion passed the fidelity check are entries here; the others keep their technique's own effect
(`"fallback": "template"` and `why` in that file). `tools/test_dcb_ports.py` checks the wiring, and with the discs
(`DCB_IMAGE`, `DCB_EU_IMAGE`, `DCB_JP_IMAGE`) builds every port to its pin.

## Authored finishers

Ten imported species play a finisher effect written here from nothing: its pictures are painted by the code, and
its script, its flight and its hit are its own, so the finisher behaves as its design says (a shot that can be
dodged, a rain on a spot, a blast that reaches every enemy). They are written with the same kit as the new
technique rows ([the technique rows](technique-rows.md)), in `tools/technique_effects/finishers.py`, one
function per species. An entry of `content/battle/own-effects.json` names it:
`{"name": ..., "technique": <species>, "authored": "finishers"}`, and the species points at the chunk with
`own_effect`. `tools/test_technique_effects.py` builds each one, plays it in the simulator to its end and checks
that it hits what its design in `content/finishers/imports.json` says, and that the three that fly miss a target
that walks away.

| Chunk | Finisher | Species | What plays | Hits |
|---|---|---|---|---|
| 222 | Pyrosphere | 433 Guilmon | a ball of fire grown at the mouth and spat at the target | where the target stood: it can be dodged |
| 246 | Diamond Storm | 354 Renamon | crystal shards that form overhead and rain down | the target, 6 hits |
| 370 | Plasma Blade | 320 Growlmon | two crossing cuts of the arm blades, close up | the target, 2 hits, may stun |
| 249 | Dragon Wheel | 409 Kyubimon | a wheel of blue fire that flies as a dragon | where the target stood: it can be dodged |
| 210 | Atomic Blaster | 326 WarGrowlmon | twin red beams from the chest cannons | the target |
| 232 | Talisman of Light | 315 Taomon | a paper charm thrown at the target that opens into a seal of light | the target, may confuse |
| 208 | Final Purification | 318 Gallantmon | a ray of holy light from the shield | the target |
| 206 | Amethyst Mandala | 316 Sakuyamon | a violet wheel of petals that opens from her | every enemy |
| 190 | Corona Blaster | 403 Beelzemon | three shots from the arm cannon through a drawn seal | where the target stood, 3 shots: they can be dodged |
| 248 | Terra Destroyer | 404 BlackWarGreymon | a black sun gathered overhead and thrown down | every enemy |

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

### Imports that keep their template

These imported finishers have no own effect: their source did not convert (a Card Battle attack that failed the
fidelity check, a self-cast support technique), and the DW1 effect they play already shows what the name says.

| Species | Finisher | Source | Plays |
|---|---|---|---|
| 123 Tinmon | Recovery Power | DW2, a self-cast heal | 111 Mail Strome: an icy beam and crystals |
| 199 Paildramon | Desperado Blaster | Card Battle, fidelity failed | 78 Genoside Attack: a volley of shots and a burst |
| 214 Shakkoumon | Clay Bomb | Card Battle, fidelity failed | 73 Bit Bomb: a lobbed bomb that bursts |
| 216 Devidramon | Crimson Claw | Card Battle, fidelity failed | 62 Death Claw: a red claw rake |
| 234 Gatomon | Lightning Paw | Card Battle, fidelity failed | 82 Hand of Fate: a glowing punch |
| 236 DemiDevimon | Demi Dart | Card Battle, fidelity failed | 69 Spinning Needle: thrown needles |
| 242 Sorcermon | Crystal Cloud | Card Battle, fidelity failed | 88 Ice Blast: a cloud and ice crystals |
| 246 Infermon | Hades' Grenade | Card Battle, fidelity failed | 74 Deadly Bomb: a dark bomb |
| 248 MarineAngemon | Ocean Love | Card Battle, larger than the slot | 60 Lovely Attack: hearts |
| 256 VioletElecmon | Jamming Thunder | Card Battle, fidelity failed | 101 Super Thunder Strike: lightning |
| 254 Tylomon | Torpedo Attack | Card Battle, fidelity failed | 87 Hydro Pressure: a sea Digimon's water jet; composed on Genoside Attack (78) its burst read bigger than any vanilla finisher |

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
