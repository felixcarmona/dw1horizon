# Imported species: Digimon from other PS1 games

How Digimon that Digimon World 1 (DW1) does not have are brought in from *Digimon World 2* (DW2), *Digimon World 2003*
(DW2003, *Digimon World 3* in the USA) and *Digimon Digital Card Battle* (DCB): what those games store, how the same
Digimon is recognised across games, which game each one is taken from, the rules that give an import its identity and
data, the Mega level, and the hand-made partners. How each import is animated is [motion.md](motion.md).

What is documented elsewhere and only linked here:

- MMD/TMD/TIM formats and inspection: [models](../mods/models.md);
- editing and rebasing imported models: [model deltas](../../content/modeldelta/README.md);
- runtime buffer limits: [memory](memory.md);
- the species file (`content/species/<id>-<name>.json`), record originals, `slot_aliases`, `effect_origins`,
  `effect_origin_fallback`, `species.py` commands: [../mods/species.md](../mods/species.md);
- species ids above 180, `DIGI.DAT` records, the world object ids of patch 0082: [ids.md](ids.md); save v2 and later:
  [save-format.md](save-format.md);
- the species provider and disc replay of all 175 imports and 37 record originals (no private converted inputs):
  [../building.md](../building.md), [../derive.md](../derive.md).

## The source games

All three are PS1 games whose battle Digimon are rigid one-mesh-per-bone models, like DW1's. Each is read through a
bundled reader under `tools/derive/importers/vendor/` during disc replay. Standalone
conversion-spec authoring tools can also use sibling research toolkits through
`DCB_ROOT`, `DW2_ROOT` and `DW3_ROOT`; those are not player prerequisites.
The converters read the player's own discs.

| | DCB | DW2 | DW2003 |
|---|---|---|---|
| Models | `F.DRV/<id>.PAK`, 190 card models (ids by card; 236-254 boss variants, 235 the tamer, 300 a logo) | `AAA/4.AAA/MODEL/MODELnnn/M<id><CODE>.BIN`, M000-M375 (M300-M375 "Q" chibi versions; M400+ are vehicles and field objects) | `AAA/DAT/FIGHT/MODEL/M<id><CODE>.BIN` (M395-M456 numbered copies; M457-M464 not Digimon) |
| Units against DW1 | the same (×1.0) | ×5.1 (DW1's own meshes scaled up) | ≈ ×4.7 geometrically; the size rule uses ×0.2128 and a calibration for big Digimon |
| Rotation order of a pose | `T(joint + t)·Ry·Rx·Rz·S` | per-frame matrix (split into rotation × per-axis scale) | `Rz·Ry·Rx` |
| Rest pose | the modelling pose (not always standing) | first frame of the idle `A0` | none: first frame of the first animation |
| Texture | 4 bpp TIM, per-face palettes, fits 256×128 for almost every model | 128×256 page, palettes stored as image rows (`clut = row << 6 | x/16`) | 256×256 page, up to 19 palettes, CLUTs in rows 216-248 |
| Texture animation | none (no blink frames) | `texAnimParts` after the bone tables: parts 0-1 are blinks (destination + open/half/closed source frames) | not decoded |
| Frame rate | 30 fps | 30 fps (one frame per two 60 Hz ticks) | assumed 30 fps |

Converters turn every source pose into glTF quaternions and `mmd.import_anims` resamples at DW1's 20 ticks/s and
solves DW1's `Rx·Ry·Rz` Euler angles, so no angle is copied channel by channel (see `tools/dcb2mmd.py` and `tools/mmdport.py`).

**What each game's animations are**, in DW1 partner-slot terms (the slot table is in [motion.md](motion.md)):

- DCB: 8 animations, battle only: `anim_00` idle (loops), `anim_01..03` attacks (about 9 s each, ending with a dash
  across the arena), `anim_04` hit, `anim_05` knocked down (no getting up), `anim_06` victory (loops), `anim_07`
  the entrance, which grows the model from scale 0 (unused). About 12 DW1 slots can be filled from them.
- DW2 (its fighter code): `A0` idle, `B0` hit, `C0-C2` knocked down (fall, bounce, settle), `F0/G0/H0` the three
  technique casts, `I0` the second action, `J0` getting up, `K0` lying; no victory. Bank `D` (`D0` idle, `D1` walk,
  `D2`, `D5` run) is the city walker's set and exists on 17 models only: the only field animations of any of the
  three games. Of the Digimon DW1 lacks, only DemiDevimon has a DW2 walk.
- DW2003: 10-40 animations per model, slot meanings not decoded (its field shows sprites, so all are battle). The
  importer picks clips by features (`analyse_clips_dw3`).
- Eating, sleeping, the toilet and training exist in none of them: those slots always come from a DW1 Digimon
  (retargeting, [motion.md](motion.md)).

### DW2 details a reader needs

- **Names.** `DATAFILE/MODELDT0-2.BIN` holds one record per Digimon id with its name, and the id is the model number
  (M003 is Agumon). Its text encoding: `A` = 0x0A, `a` = 0x24, `-` = 0x49. M249-M255 are not Digimon (three guardian
  machines, the final boss and its parts) and neither is M252TNKX (a vehicle); their Q chibis are left out too.
- **Two roots.** Some models hang a part from the actor rather than the pelvis (Kimeramon's tail); a partner spec
  re-parents it (`"reparent"`, every pose kept: new local = inv(L_parent)·L_child per frame).
- **Pieces stored at another scale.** DW2 (and DW2003) store some pieces at another size and scale them back in the
  bone matrix; such a piece needs its scale channel zeroed when animations move between games.
- **Texture.** 168 of the 192 Digimon have faces whose UVs cross row 128 of the page, so the page cannot simply be
  cut in two 128×128 halves: `dw2mmd.repack` places two 128-row windows side by side and moves UV islands that fit
  neither into unused texels (see `tools/dw2mmd.py`).

### DW2003 details a reader needs

- **Section table.** A model file starts with a table of `u32` section offsets in which **0 marks an empty slot**.
  Section *i* ends at the next larger non-zero offset (or the end of the file); slicing `data[off[i]:off[i+1]]`
  turns an empty slot into a copy of the file's start and empties the section before it. Read that way, five files do
  not parse (Knightmon M178KNGT, Zanbamon M337ZAMB, M080GOBR, M398GOB2, GrapLeomon M391GRPL) and six seem to have no
  texture (M054MGDR, M060HKAB, M230GKWA, M375TAOM, M440SIJN, M453TAO9). `tools/dw3_extra.py` applies the right
  slicing in-process (`dw3_extra.patch()`); `check` lists old against fixed parses.
- **Animation table.** Section 0 is the animation table only when it has a table's shape. In Guilmon's file it is the
  track of bone 1 and in Bastemon's the mesh of bone 4; their tables are elsewhere (sections 50 and 2), found among
  the sections the hierarchy does not use.
- **Identification.** The game's own partner profiles carry the model number; the name list pairs profile *k* with
  name *k*+1 (the list starts blank). Model 230 (`GKWA`) is GranKuwagamon.
- **Pauses.** Segments that hold timeline frame 0 (a construction pose) are pauses: they hold the previous frame.

### Other releases of the source discs

The import recipes are made from one release of each game; the others are checked or patched so they give the same
bytes ([../patcher.md](../patcher.md); the discs are identified by `tools/discs.py`):

| Tool | Reference release | Others |
|---|---|---|
| `tools/dcbrelease.py` | DCB USA | Europe: every F.DRV model byte-identical; Japan (*Digital Card Arena*): every recipe model identical. The PAK records are unpacked by a plain-Python port of the game's own routine, proven equal to it, so no executable is run |
| `tools/dw2release.py` | DW2 USA | Japan: every recipe file identical (checksums only) |
| `tools/dw3release.py` | DW2003 PAL | Japan: recipe files checked by checksum. US World 3 normalization is excluded from the published recipes because it would carry PAL game bytes; use a supported World 2003 disc. |

`make RELEASE` writes a release's list (SHA-1 of each recipe file), `check RELEASE` verifies a disc against it.

## The same Digimon across games (`tools/crossgame.py`)

`crossgame.py` loads every Digimon model of DW1, DW2, Pocket Digimon World, DCB and DW2003 as a list of rigid pieces
and compares them by shape, writing its table `crossgame-models.csv` (one row per Digimon name, the model ids per game,
the relation of each game's model to a reference, texture `same`/`different`, notes).

**Shape** (`compare()`):

1. Per piece, duplicate vertex positions are merged (games split vertices at UV seams differently); pieces under 4
   vertices are ignored.
2. Signature: all pairwise vertex distances divided by their RMS (scale invariant), sorted and resampled to 64
   quantiles.
3. Two pieces with the same vertex count match when the median relative difference of their quantiles is ≤ 3 %
   (`SHAPE_TOL`) plus 1.5 units of integer rounding relative to the piece size (`ROUNDING`).
4. Pieces are paired greedily, best first. The vertex-weighted median size ratio of the pairs is the model's scale;
   a second pass pairs again requiring that ratio within 5 % (`SCALE_TOL`), which sorts out look-alike pieces of
   graduated sizes (a segmented tail).
5. Left-over pieces with the same vertex count and shape at another size are **rescaled** pieces; they count as paired.
6. **identical**: every piece of both models paired. **modified**: the paired pieces hold at least half of each model's
   vertices and are at least half of the larger piece count (`+a` pieces only in the other game, `-r` only in the
   reference, `~c` unpaired on both sides). **different**: otherwise.

Triangle counts are reported, not used: the same mesh can be triangulated differently. A looser rule (pieces of another
vertex count within 8 %) makes unrelated DW1 Digimon "modified" (boxy limbs look alike) and is not used.

**Texture** (`tex_distance()`): per piece, the mean colour of its texels sampled at 4 points of each textured triangle
(weighted by UV area) through the palette the face uses; paired pieces compared. `same` when the vertex-weighted median
RGB distance is ≤ 20 (`TEX_SAME`) and under 12 % of the paired vertices are further than 45 (`TEX_FAR`,
`TEX_FAR_SHARE`). Working per piece makes it independent of each game's texture layout. Only paired pieces are compared,
so a remade piece with new colours on a modified model is not seen.

**Names.** DW1 by species id; DCB by its card names; Pocket by the same ids as DCB (116 of its 117 models are DCB's
mesh of the same id); DW2/DW2003 by the 4-letter code in the file name when it is a DW1 file name, else by a code
table in the tool, aliases for the other games' spellings (Tailmon → Gatomon, Pinocchimon → Puppetmon, Holydramon →
Magnadramon...) and an identification table (`crossgame-identified.csv`) for the 61 models the codes did not name (code, game, name,
confidence, evidence).

What the comparison shows (Digimon names with a model):

| | DW2 | Pocket | DCB | DW2003 |
|---|---|---|---|---|
| Digimon with a model | 192 | 117 | 189 | 180 |
| of DW1's, present | 110 | 108 | 109 | 60 |
| identical to DW1's | 92 | 104 | 103 | 12 |
| modified / different | 15 / 3 | 4 / 0 | 5 / 1 | 29 / 18 |
| Digimon DW1 lacks | 82 | 9 | 80 | 120 |
| …found only in this game | 14 | 0 | 25 | 58 |

DW2, Pocket and DCB reuse DW1's meshes almost unchanged (about 95 % identical, most with the same texture); DW2003
remodelled most of them. Pocket adds nothing DCB lacks. Where DCB and DW2 both have a Digimon DW1 lacks, DCB's mesh is
DW2's or a light edit of it, at DW1 units.

## Which game each Digimon comes from (`tools/crossgame_sources.py`)

`crossgame_sources.py` reads the comparison table, measures every candidate model against DW1's limits and writes
`crossgame-sources.csv`, per Digimon, separately for the mesh and the animations.

**Fits** (lossy limits: going over means removing geometry or merging palettes): primitives ≤ 713, vertices ≤ 706, ≤ 172
per piece (identical positions counted once), bones ≤ 34 with the entity, palettes ≤ 15 (16 accepted with a note: row 15
is the flat sprite's). The texture is a separate, lossless check: DCB's TIM must lie in 256×128; DW2's page is repacked;
DW2003's UVs must be in rows 0-127 or be repacked (`dw3mmd.repack_page`, which also shrinks UV islands when the used texels
do not fit).

- **`model_from`**: of the games whose version fits (a texture to repack counts as fitting), DCB first (DW1 units), then
  DW2, then DW2003. When DCB and DW2 both fit and the meshes differ: DW2 if its version has its own field walk, else DCB if
  it is an edit of DW2's mesh adding at least as many pieces as it removes, else the one with more primitives. When nothing
  fits, the version with the fewest failed limits, in the same order. Pocket is measured, never chosen.
- **`anims_from`**: among the versions whose mesh is identical to the chosen one (so clips transfer through the shape
  pairing; piece order differs between games), the one whose own animations fill the most DW1 slots; a tie keeps
  `model_from`. Typical case: mesh from DCB, animations from DW2, which has the identical mesh and more battle animations.
- **`everyday_anims`**: `own-walk` when the animation source has DW2's walker set, else `borrowed`.

The CSV's `dw1` section lists DW1 Digimon whose same mesh elsewhere has more animations than DW1's file (enemy and NPC
models with few animations: Hagurumon and Tinmon in DW2, Jijimon, MasterTyrannomon, Brachiomon...).

## Converters in this repository

| Tool | Does | Documented in |
|---|---|---|
| `tools/dcb2mmd.py` | DCB card model → MMD + texture entry; `info`, `sheet`, `convert`, `partner SPEC` | `tools/dcb2mmd.py` |
| `tools/dw3mmd.py`, `tools/dw3_extra.py` | DW2003 battle model → MMD; palette merge, quad rebuild, repack | § 11 and above |
| `tools/dw2mmd.py` | DW2 model → MMD with its blinks; `batch` for every DW2-source Digimon | § 13 |
| `tools/mmdport.py` | the DW1 side shared by all three (`build_tmd`, `build_tim`, `skeleton`, `write_gltf`, `build_partner`) | § 10 |
| `tools/import_batch.py` | a list of source models → partner species with no per-Digimon spec (donor, clips, budgets, species data by rule) | § 12 |
| `tools/fitfix.py`, `tools/rigfix.py`, `tools/meshfix.py` | models over the partner buffer, over 34 bones, over the mesh budgets | §§ 14-16 |
| `tools/retarget.py` | motion between different skeletons by an explicit bone map | [motion.md](motion.md) |
| `tools/crossgame.py`, `tools/crossgame_sources.py` | the comparison and source choice above | here |
| `tools/dcbrelease.py`, `tools/dw2release.py`, `tools/dw3release.py` | other releases of the source discs | here |
| `tools/efe-origins.py` | where each technique of a species starts from (row, C donor, entity point, default) | here, "Technique effects" |

Every rule runs on the player's disc at build time; specs and species files hold only parameters (bone maps, slot
choices, tolerances), never model data.

### DW1-side facts a converter must respect

- **One palette per texel.** Over the 178 DW1 models, no texel is sampled by faces using different CLUT rows; palettes
  are allocated per 8×8 block in 99.45 % of the sampled blocks, not by rule (10 models break it). A converter has to
  keep each face's own row rather than assume one palette per block.
- `CBA = 0x7A00 + (row << 6)` is an **add** (rows 8-15 fold onto 0-7 with an or): [model textures](../mods/models.md#3-the-texture-alltimtim-and-the-vram-slots).
- **Texture size.** Six `ALLTIM.TIM` entries are not 256×128 (types 116 248×120, 118 256×88, 119 256×112, 121 256×96,
  122 256×104, 123 256×88): UVs must be normalised by the real size.
- **Normals past the count.** The GTE reads `normal_top + 8·index` without checking the object's normal count, so a
  primitive may use the next object's normals (Tanemon does): a reader must follow the hardware.
- **Animation playback** facts (finite loops, Euler interpolation): [motion.md](motion.md).

## Identity and data of an imported species

An import's attribute, specialties, techniques, finisher and raise data are chosen by rule, then written into its
species file. The source games' filler (the donor's technique list) is replaced.

**Attribute.** DW1 knows Vaccine, Data and Virus only (`DigimonPara.type`; it indexes the attribute damage factors and
`FLEE_CHANCES[(partner − 1) * 3 + enemy − 1]`, the join chance). A species DW1 gives an attribute keeps it, whatever canon
says. An import takes the first of Vaccine / Data / Virus its canon entry lists; with none of them (Free, Variable,
Unknown, None), Data, as DW1 does for its babies. A partner or fighter with attribute 0 indexes `FLEE_CHANCES` before the
table and draws the status icon from column −12: lint refuses it (Machinedramon and Analogman are Virus for that reason).

**Specialties.** The canon attacks and nature mapped onto DW1's seven elements (Earth = Nature), main first, 1 to 3; the
evolution line's DW1 specialties when canon is ambiguous. The main specialty must have a technique of its own: on
evolution `EVL_applyEvolution` teaches the weakest technique of the first specialty, and with none it equips a slot that
does not exist.

**Finisher.** The existing DW1 finisher (ids 58-112) closest to the canon signature attack (breath, beam, claw, thrown
weapon, punch), of an element among the specialties; a canon attack that has a DW1 finisher's name wins over the element
(as DW1 does for Centarumon and Kokatorimon). Power bands by level: Champion 130-200, Ultimate and Mega 196-260, with a
second class of 180-195 for Ultimates of Air or Battle (DW1 has no Ultimate-tier finisher of Air and none of Battle but
two signatures). Rookies are left alone (DW1 has no Battle finisher below 150). Finishers are shared, as in DW1.

**Learnable list.** Canon-backed techniques first, then the originals' size by level: Rookie 7, Champion 10, Ultimate 13,
Mega 14, split over the specialties (two: 4+3, 6+4, 8+5, 8+6; three: 3+2+2, 5+3+2, 6+4+3, 6+4+4), weakest first for
Rookie and Champion, strongest first for Ultimate and Mega. The third specialty only takes techniques with a non-zero
tertiary learn chance (`MOVE_LEARN_CHANCES[m][2]`). Each technique slot 0x2E + *i* plays one of the model's own clips of
the technique's element and range (`model.slot_aliases`); the finisher keeps its clip.

**Favourite food** (energy ×1.4 and happiness +2 when fed): no rarer than the foods the DW1 originals of the same level
like (Mega shares the Ultimate set: the disc has only two Mega-like originals). Moldy Meat (always makes it sick) only for
the filth lines. Rarity by how the food is obtained in the game:

| Rarity | Foods |
|---|---|
| common | Meat, Giant Meat, Digimushrm, Happymushrm |
| uncommon | Sirloin, Supercarrot, Hawk radish, Ice mushrm, Digipine, Blue apple, Big Berry, Sweet Nut, Pricklypear, the lake fish (Digisnapper, Digianchovy, DigiTrout, Black trout, Digicatfish), Moldy Meat |
| rare | Spiny green, Deluxmushrm, Red Berry, Gold Acorn, Super veggy, Orange bana, the six stat fruits, Digiseabass, Chain melon |

**Sleep and training.** Every sleep cycle is one the originals use; the babies' cycles only on babies. The "all-low"
training type (all stats ×0.8) only on the junk lines (Numemon, Sukamon, Nanimon and their relatives).

**Wild stats and evolution gains by role.** The role is the species' `partner.training_type` (tank `hp-defense`, striker
`offense-speed`, caster `mp-brains`, `even`, `all-low`). Wild stats are the stage template (Rookie 600/120/90, Champion
1500/250/200, Ultimate 3000/400/350 HP/Off/Def) times role factors of at most ±15 % and a deterministic ±4 % jitter per
name and stat. Evolution gains are the level's flat row (Rookie 500/500/50/50/50/50, Champion 1500/1500/150..., Ultimate
5000/5000/600/500/500/500) scaled the same way, HP/MP in steps of 50, the rest of 5.

**Evolution parents.** The curated table (`content/tables/evolution-tree.json`) prefers canon main lines, then family and shared specialty. A child has up to five parents; a parent has six targets. Imported canon Megas follow Perfect parents even when their engine level remains `ultimate`; no Champion fallback is allowed. The original disc routes to Phoenixmon and HerculesKabuterimon stay. Requirement rows distinguish siblings through stats, care and weight, with a primary-parent bonus applying only to the first parent. `tools/evo_tree.py` checks each parent with the picker; `tools/test_evo_tree.py` guards the tree in the self-test. Unlisted species and the starter quiz's hand-authored links stay unchanged. The four Baby II partners have their 6 targets in the executable's
`EVOLUTION_PATHS` (`int8_t to[6]`) full; patch 0111 gives each Baby II up to 12 more Rookie targets
(`getEvolutionExtraTargets`, made from the `DIGI.DAT` links that find no free slot), walked after the 6 by
`getInTrainingEvolutionTarget`.

### Technique effects

A technique's effect starts from an origin row of `EFEDAT.EFE` keyed by the attacker's effects type (`effects_like`, the
record's `originalType`): every technique chunk holds `{i16 type, i16 bone, i16 x, y, z}` rows ended by a negative type.
Without a row, `checkTechCompatibility` (BTL/STD/VS) ends the effect script: the clip plays and nothing hits. The disc
has rows for a type only for its own species' techniques (11 to 54 of the 121 per type).

- **Borrowed rows on a new skeleton.** `effect_origins` (`[from bone, x, y, z, to bone, x, y, z]`, `"any"` for any
  offset of a bone, up to 8; bone 0 rows are entity-relative and need nothing) moves each borrowed point from the donor
  bone (rest pose) to the mapped target bone. The game matches `from` exactly as the disc has it: it is never scaled with
  the model. `condition_bubble` places the condition bubble the same way.
- **No row at all** (patch 0106, only for species carried by their `DIGI.DAT` record): when most of the technique's rows
  are entity points (punches, stings, clouds, areas), the entity point of the row whose species is closest in collision
  radius; when most are on bones (breaths, shots, finishers), the record's `effectDefault` (`SpeciesRecord` 0x1C4,
  flag `SPECIES_FLAG_EFFECT_DEFAULT`): the place its type's bone rows most often start from, moved onto its skeleton, or
  `effect_origin_fallback` from the file. A species without a record drops the effect as on the disc, and lint refuses
  such a technique.
- C donors (`getModDonorTechBoneOffset`, `getModTechBoneOffset` in `efe.c`) serve the hand-made partners below.
- `tools/efe-origins.py --species ID` prints where each technique of a species starts and why. Its tables are found by
  shape; it tries every offset and keeps the longest table per terminator (a misaligned match skips a table's first
  row).

## What the game asks of every partner

Each use found in the decompilation is a lint rule of `tools/species.py` (`PARTNER_SLOTS`, `audit_model`); "empty" is a
table entry of 0, "past" an id beyond the model's table (`startAnimation` reads `animTable[id]` without a bound and
returns on an empty entry, so the previous clip goes on and code waiting for its end may wait for ever).

| Need | Where (decompilation) | Rule |
|---|---|---|
| idle 0 (the entity starts on it) | `model.c`, partner states | error if empty or past |
| poor-condition idle 1, walk 2, slow walk 3, catch-up 4 | `partner.c` (`partnerTickWalking`, `setPartnerSlowWalking`, `setPartnerIdle`), `evl.c`, `dooa.c` | warning if empty, error if past |
| eat 8, refuse 13 (feeding waits for the end) | `partner.c` | error if empty |
| toilet 10, after pooping 12 (wait for the end) | `partner.c` | error if empty |
| going to sleep 11, asleep 9; 0x0B also praise, favourite-food joy and the end of evolution; 0x0C also scold, the evolution flash and a new egg | `partner.c`, `tamer.c`, `partner_impl.c`, `evl.c`, `dooa.c` | error if empty |
| gym: 0x12, 0x16, 0x1B, 0x25 | `trn/*.c` | warning if empty |
| gym offense clip (`partner.training`, `training2`: animation 46-61 and hit tick 1-120) | `trn_off.c`, `trn2_off.c` | error past the table, warning if empty or the hit tick is after the clip |
| battle idle 0x21/0x22, battle movement 0x23/0x24, hit 0x28/0x29, senile 0x13, block 0x25 | `btl.c`, `battle_main.c` | warning if empty |
| victory 0x2A, faint 0x2B, get up 0x2C (the fight's end, the game-over countdown and item revive wait for them) | `battle_main.c`, `battle_setup.c`, `item.c` | error if empty |
| each technique's attack, 0x2E + its index in `techniques` | `battle_main.c`, `utils2.c` | error if empty or past |
| a finisher (an id 58-112 among the techniques) | `initializePartner` (the 4th battle move) | warning if absent |
| slots scripts may start (`partnerStartAnimation`): 0..0x2C except 6, 0x14, 0x1A, 0x1C-0x20, 0x26, 0x27 (the tamer's, NPCs' and the kart race's) | `script_interp.c` | warning if empty |
| bones named by animations exist in the skeleton | `anim.c` momentum and bone arrays | error |
| animation sounds (bank 4) the voice bank has a tone for | `anim.c`, `startSound` | warning (silent otherwise, as a few disc species are) |
| technique origin for `effects_like` | `checkTechCompatibility`, `efe.c` | error when it would never hit |
| aura / condition rows: `effects_like` ≤ 128 | `*_AURA_PROJECTILE_TYPES[129]`, `CONDITION_FX_OFFSETS[177]` | error above 128 |

A gym clip on a slot the model leaves empty plays nothing: an import uses one of its own attack clips (a melee clip
when it has one, else the closest-range attack of 15-50 ticks), with the hit tick at half the clip, at least 6.

## The Mega level

The original game has levels 1 Fresh to 5 Ultimate (0 = NPCs that never evolve). The `mega` patches (0058 in the
series) add **6 = Mega** (`include/dw/level.h`): a species whose record says level 6 is a Mega wherever the game asks
for a level. Only species of `DIGI.DAT` can be Megas. One species is level `mega` (373 WarGreymon); the imported
Digimon that are Megas in canon are stored as `ultimate`, with the Mega size range. Their curated parents are Perfects, so the engine's Ultimate → Ultimate wait of 96 h applies. This level representation does not permit Champion → imported canon Mega shortcuts. A well-kept earliest chain reaches its third form at age 342 h with 114 h left before the new lifetime bonus; WarGreymon waits 120 h and reaches age 366 h with 90 h left. Delayed raises and happiness below 80 reduce those margins.

**Reaching it.** `tickConditions` has one Ultimate branch: Machinedramon's special case (48 h), then
`getChampionEvolutionTarget` after 96 h for another Ultimate, and a Mega target only once `evoTimer >= 120`
(`MEGA_EVOLUTION_HOURS`). The Ultimate then calls
`getChampionEvolutionTarget` on its own paths every free frame; the choice is the Champion → Ultimate one (score ≥ 3 of
4: care mistakes, weight ± 5, the six stats, one bonus; ties by raised flags, then by the best average of the required
stats). 120 h because the earliest natural Ultimate arrives at 246 h of age with 210 h of lifetime left if happiness
stayed ≥ 80: 120 h leaves 90 h, so a well-kept Ultimate gets there and a neglected one does not. On evolving
(`EVL_applyEvolution`): the usual gains formula, tamer level +1 (100 %, as Ultimate) and **+120 h of lifetime**
(`MEGA_LIFETIME_BONUS`; Ultimate +96 h). An evolution item works from an Ultimate with no code change
(`handleEvoItems` accepts `level(target) − 1 ==` the partner's level).

Every read of the level, and what level 6 does there:

| Where | Level use | Level 6 |
|---|---|---|
| `tickConditions` | evolution clock per level (6/24/72/144 h) | **changed**: Ultimate ≥ 120 h looks for a Mega; a Mega looks for nothing |
| `setSleepTimes`, `tickSleepMechanics`, `handleSleeping` | `< 3` baby sleep, else `SLEEP_PATTERN` | adult schedule |
| `setFoodTimer`, sleepy penalties | levels 1 and 2 special | as adults |
| `partnerWillRefuseItem` | refuses evolution items of its own level, +2 or −1 | refuses Ultimate and Mega items |
| `calculateRequirementScore` | Rookie targets use the highest-stat rule | all six stats |
| `EVL_applyEvolution` | tamer level, lifetime | **changed**: 100 %, +120 h |
| training multiplier (`trn_reward.c`, `trn2_hud.c`) | ×0.9 (1-2), ×1.0, ×1.1, else ×1.2 | **changed**: ×1.3 |
| `BTL_calculateHitChance` | `< 3` defenders always hit | normal |
| counter chance (BTL/STD/VS) | `rand(100) < speed / level` | speed/6 |
| `STD_setupParticipants` | `STD_WIN_CHANCES[level − 3][level − 3]` (rows 3..5) | **changed**: counts as an Ultimate (it read past the rows) |
| `STD_initializeOpponent`, `vs_demo.c` | opponent stats ×1, ×2, ×2.5 for 3/4/5 | **changed**: ×3.5 (was uninitialised) |
| `dget.c` cup eligibility | per-species lists in the arena script | not changed |
| evolution chart | level name under the portrait | **changed**: a "Mega" name and a gold box for level 6 targets in an Ultimate's detail view (the overview has no room for a sixth column) |
| Status page, save | no level shown or stored | unchanged |

The lab menu's "To Mega" option starts the real sequence with the natural gains (the Mega of the partner's paths, else
the first level 6 species).

## Hand-made partners

Some partners are built from disc models by scripts in `content/models/` (`../mods/models.md`; `tools/build-full.sh`
runs them) rather than imported. The techniques they use show the general mechanisms.

**Executable NPCs made partners (MasterTyrannomon 124, Cherrymon 121, and the NPC partners of `partners-npc-*`).** The
per-partner tables (`RAISE_DATA`, `EVOLUTION_REQS`, `EVOLUTION_STATS_GAINS`, `ITEM_TAKE_DISTANCE`, the VLALL voice and the
gym animation rows) are sized `NUM_DIGIMON` with neutral rows, so a type above 65 can have a partner row. The voice table
keeps 15 for every type outside 1..65, and the partner sound loaders cover every type. The raised flag of type *t* is
trigger 0x200 + *t* where free (`HAS_RAISED_FLAG`; `hasDigimonRaised` returns 0 for types without one). An NPC and the
partner share the species' row and model file: the NPC becomes a partner-capable species everywhere it appears, and its
model costs its new size in the heap where it is an NPC.

- **MasterTyrannomon** shares Tyrannomon's skeleton (27 bones, same bone → object map) and is built exactly 1.5 times
  larger: every one of Tyrannomon's 39 distinct animations is played tick by tick (`mmd.AnimPlayer`), every translation
  (bone offsets and root motion) multiplied by 1.5 and re-encoded exactly (`tol 0`, loops, sounds and texture moves
  kept); rotations unchanged. Its eye frames sit where Tyrannomon's are, so blinks work as they are.
  `ORIGINAL_DIGIMON_TYPES[124] = 8` borrows Tyrannomon's technique origins, aura and condition offsets.
- **Cherrymon** is scaled to 0.55 (the full model is 1000 tall). Its NPC slots 0x1D/0x1E are replayed and re-encoded
  with their translations scaled, so the scripted NPC still works. The 45 partner slots are written per tick
  (`content/models/cherrymon/anims.py` with the helpers of `clips.py`: trunk lean, canopy sway, branch arms, roots, hops
  and the eye/mouth frames), keyed every 1-3 ticks, timed by Vegiemon's everyday slots and by Piximon's techniques
  (the same eight Earth techniques in the same order, so the clips match their effects); five techniques are
  retargeted from Vegiemon's vines (`retarget.py` chord mapping). Technique origins come from `getModTechBoneOffset`
  (`efe.c`), which borrows Piximon's row and moves it: points in front of the body 1.6 times farther out, the spear
  hand to the front-hand palm, everything else from the mouth.

**WarGreymon 373, the Mega.** DCB's card model 173 as it is (20 bones and the entity, 621 primitives, 14 palettes,
473 tall), converted with `dcb2mmd.py` (`content/models/mega/make-model.py`, `wargreymon-dcb.json`). The everyday slots
are Greymon's retargeted (two-piece arms from Greymon's three, the side tassets following the thighs at half weight);
the card game's idle, hit, victory, knock-down and five technique clips fill the battle slots; the other technique slots
are Greymon's retargeted onto the card idle's crouch, so a technique does not jump to the upright modelling pose.
Techniques borrow Greymon's (`originalType` 5): an EFE effect plays only for types its table lists, so the finisher and
the moves must come from one donor. Specialties Fire first, so the evolution teaches a Fire technique. Its field gait is
a recipe of its own ([motion.md](motion.md)).

**Veemon 180, Puppetmon 181, Kimeramon 182.** The first imports, each from a hand-written spec in
`content/models/dcb-import/` (`dcb2mmd.py partner`, `dw2mmd.py partner`): Veemon from DCB with Gabumon's everyday
slots, Puppetmon from DCB with Ogremon's (the club hand drives the hammer hand), Kimeramon from DW2 (geometry and
texture exact, DW2's blink, its tail re-hung under the pelvis) with MetalGreymon's. Parts the donor does not drive
(tails, extra wings and arms) play the source game's own idle in the looping everyday slots, retimed to whole cycles.

## Limits of the imports

- No source game has care animations; DCB and DW2003 have no blink frames (DW2 does), so many imports keep their eyes
  open in sleeping slots unless a field recipe adds texture states.
- Battle clip ranges are cut by motion analysis, not by meaning (a taunt can be taken for an attack); techniques are
  timed to the DW1 donor slot's length because the effects are.
- What new species can do in cups and VS: [../mods/species.md](../mods/species.md), "Limits".
- The donor match is a heuristic over skeleton shape: a winged humanoid can get a centaur's walk; [motion.md](motion.md)
  describes the field recipes that replace such gaits.
