# Digimon species: one JSON file per species (content/species)

Every species the game knows is a JSON file, `content/species/<id>-<name>.json`, **complete** (everything the game
reads of it, nothing inherited from another file): the 180 of the disc (ids 0–179, with what the C patches change,
e.g. the NPC Digimon made partners) and the imported ones (180..1023). `tools/species.py` is the one reader:

- species **0..179**: their rows of the executable's tables (`DIGIMON_DATA`, `RAISE_DATA`, `ITEM_TAKE_DISTANCE`,
  the voices, `ORIGINAL_DIGIMON_TYPES`, the TRN/TRN2 training rows, the battle music, the reincarnation stats and
  the new-game technique) are written from the files after linking (`tools/balance.py build`, step 5b of
  `tools/build-full.sh`); the C initializers stay as the decompilation has them and `species.py verify` (also
  `balance.py verify`, selftest `balance-int`) proves they agree with the files;
- species **180..1023** are records of `DIGI.DAT` (below) with their model and texture, built from the files.

**Policy.** The numeric gameplay data of every species is committed as JSON (the 180
originals included); models, textures, sounds, dialogue text and disc files still never. The extractor stays, so the
files can be made again from the player's own disc: `species.py extract` writes the 180 files with the disc's
values (`build/species-original/`), `species.py diff` lists every field where `content/species` differs from them
(the mod's changes: the 11 NPC partners 66, 70, 94, 113, 115, 116, 117, 119, 120, 121, 124).

Ids go up to **1023** (`NUM_DIGIMON`) and may skip numbers (the gaps are undefined records).

**Saves.** A save holds species by id: renumbering an imported species, or removing one, makes saves that hold it
load another species or a blank one. Saves of the 180 original species are unaffected.

## Record originals: an original id carried by DIGI.DAT

An original species (0..179) whose file has an imported species' model (`model.skeleton`, `model.file`, `texture`,
`effects_like`) is a **record original**: on a disc that carries it, its `DIGI.DAT` record replaces the disc's species,
everything the file says (model, texture, skeleton, techniques, partner block, evolution, effect origins, condition
bubble). The DW1 Digimon that were only enemies or NPCs and are partners now are record originals (one species per name,
not a separate import under the same name); so is
WereGarurumon 62 (the disc's row is a placeholder without a model; the Card Battle import that was 204 is it now, and
the Moon Mirror, which evolves into 62, reaches it).

| | the disc carries it (`SPECIES` names it, or `all`) | it does not (an explicitly reduced selection) |
|---|---|---|
| the game | the record (patch 0084: at boot its rows are copied over the resident tables; skeleton, model, texture, effects, evolution paths are read from the record) | the disc's species, as the original game |
| the executable's tables | the C's rows, but the name and explicitly curated native tier are the file's (a renamed record original, Goblimon 80, Golemon 108, is named alike without its record): `balance.py build` writes the file's other values only into the record, never into the executable (`species.py verify` checks their resident fallback rows and curated tiers; the archive check verifies their carried data) | the same |
| `species.py select` | the file | the disc's file (`species.py extract`), written into the build's folder |

Rules: `model.name` and `model.bones` stay the disc's (the executable's row); `model.file`, `skeleton`, `slot_aliases`,
`radius`, `height` are the record's. `evolution.from` / `to` may name any partner: an original 1..62 gets the record
original in its paths by a link (as an import), a record original 63..179 has the paths of its record (the disc's
species of those ids have none). Selection: by id like an import (`SPECIES="111 68"`, `all`). The everything release uses `SPECIES=all`, including record originals. A reduced
`IMPORTS=0` build keeps the disc species for unselected record originals. The wild enemy of a carried species is the record
too: same mesh, the record's technique list (the provisional finisher is appended last, so the enemy's own slots keep
their numbers); field NPC requests for the seven restored species use the NPC twins below.

Additional ordinary techniques are appended without shifting existing attack or finisher slots. For imported models,
`content/models/imports/models.json` may specify `technique_aliases` as `{new technique: existing technique}`.
The provider applies these clip aliases after field overlays and Buster Dive processing, so the final model retains
its authored acting and attack events. Record originals use `model.slot_aliases` directly. Both routes share animation
programs rather than duplicating them; adding a technique still requires a compatible effect and a free move slot.

Imported model recipes may also set `movement_sound` to an SL note number for the six
field/battle movement slots. The object form, `{"note": 12, "replace_notes": [20]}`,
also replaces those explicitly named bank-1 donor footsteps in other animations
(for example a landing during care or an attack). It preserves voice banks,
other effects, event frames, geometry and pose/control/texture programs. This
is an offline recipe edit; no runtime sound mapping or new sample bank is added.

## Original NPC twins

Ids 462–468 are internal NPC records for ShogunGekomon, KingSukamon,
Cherrymon, Hagurumon, Tinmon, MasterTyrannomon and Brachiomon, in that order.
`_npc_original` names the native script identity. They copy the disc skeleton,
bone count, radius, height and voice. `model.from` and `texture.from` read the
unmodified player-disc extraction, before any output CHDAT replacement. The MMD
is archived byte for byte. No models or textures are committed.

A species with no techniques (these twins, and the big Whamon, id 146) can be placed by a story on a new screen as a
talk-only NPC: its three technique slots are written as 255, so it never fights. Do not `fight()` it.

They have no `partner`, techniques or evolution. All selections include them,
including `SPECIES=all` and reduced builds. They are absent from the chart, lab
partner list, site guide, portraits and DWS species names. Scripts, maps and
saved partners continue to use the existing ids; field loading resolves the NPC
record internally. Speaker names resolve back to the existing species, in the
active language. Partner, wild-battle and tournament definitions stay separate.

IceLeomon, Myotismon, Cherrymon and MasterTyrannomon also carry native records for their evolution paths. Their native engine ids (63, 66, 121, 124) have no resident path row; without their records they are neither valid evolution children nor parents. Their native ids in resident parents’ forward lists are retained, so subset discs carrying these records keep Devimon → Myotismon, Vegiemon → Cherrymon and Tyrannomon → MasterTyrannomon. Selection removes links to omitted records and pads resident rows back to five/six slots; a subset therefore cannot select a missing record’s NPC model as a partner. The latter three keep the existing generated partner models and requirement rows. IceLeomon uses Leomon's matching skeleton and mesh with its own texture; the unused `PANJ.MMD` filename is absent from the USA disc. Their tier changes and peer balance rows are applied from the curated tree. Icemon (94) also carries its existing partner model verbatim in a record, because its new Champion tier needs onward paths. No model or texture bytes change for this conversion. Their model deltas are rebuilt from disc inputs, with no additional executable allocation.

WereGarurumon (62) is the one record original inside the resident path table. `balance.py` and `species.py build` seed that resident path row from its species file, then archive links fill the remaining slots. Its obsolete disc reverse entries do not consume the new parents' slots; existing forward evolution routes remain.

## How the game reads them

For `partner.favored_region`, see the [liked-region reference](../reference/liked-regions.md):
the nine patterns include disliked places as well as liked ones, so the value
cannot be inferred from a specialty or a geographical name alone.

- **The 180 originals stay as they were**: `DIGIMON_DATA`, the skeletons,
  model names, voices and `ALLTIM.TIM` are resident and read every frame.
- **Ids 180 and up** come from `DIGI.DAT` (one `FILE_OFFSET_TABLE` entry):
  - sector 0 is the header, sectors 1 and 2 an index (the partner species in
    id order, the first Mega, and the evolution links between new and
    original species), then a 512-byte record per id: `DigimonPara` (name,
    bones, radius, height, level, specialities, drop, techniques), where the
    model and texture are (sectors of `DIGI.DAT`, no `type × 9` stride), the
    skeleton (inline), the voices (`VBALL`/`VLALL` ids), the *original type*
    (whose technique effect offsets, aura and condition icons it uses) and
    the **partner block**: raise data, evolution requirements and gains,
    evolution paths, item distance, training animations;
  - a record is read into a 16-slot cache when its model loads (map entry,
    battle, evolution) or when a per-partner row is read (`RAISE_ROW(type)`,
    `EVO_REQ_ROW`, `EVO_GAINS_ROW`, `getItemTakeDistance`,
    `getPartnerVlallSoundId`, `getEvolutionPath`: the same shape as
    `DIGI_PARA(type)`); a slot is not given away while a model of that
    species is in use (partner, NPC slots, evolution target). Every
    `DIGIMON_DATA[t]` read in the code goes through `DIGI_PARA(t)`;
  - the per-partner tables of the executable (`RAISE_DATA`,
    `EVOLUTION_REQS`, `EVOLUTION_STATS_GAINS`, `ITEM_TAKE_DISTANCE`,
    `DIGIMON_VLALL_SOUND_ID`, the training animations) have the 180 rows of the
    originals only (the NPC partners 63–124 among them); **a new species costs
    nothing resident**. At boot only the index is read: the links of new
    species into the 62 resident `EVOLUTION_PATHS` rows (a new species is
    one of the targets of the species it evolves from) and the partner
    list the lab menu walks (2 KB);
  - the **raised** and **recruited** flags of the species that have no
    trigger of their own (every id ≥ 180, and the originals whose trigger is
    taken: Icemon, Meteormon…) are two bitsets of 1024 bits
    (`SPECIES_RAISED_BITS`, `SPECIES_RECRUITED_BITS`) saved in the v2
    extension; `hasDigimonRaised`/`setDigimonRaised` and `isDigimonRecruited`
    choose the trigger or the bit.
- Records 0..179 of the file are made from the same species files (the game does not read them), with the
  disc's evolution rows (the evolution tree is not in the files yet). A `DIGI.DAT` without imported species (the
  game ignores a file of 180 ids) keeps the disc's records, so a sparse developer fixture without
  `content/species`, makes the same file.
- Record byte 0x52 is the species' battle music (`getSpeciesBattleMusic`, patch 0081).

Without `DIGI.DAT` on the disc the game has its 180 species, as before.

## The file

`content/species/3-agumon.json` (an original partner) as `species.py extract` and `sync` write it:

```json
{
  "id": 3,
  "name": "Agumon",
  "level": "rookie",
  "attribute": "vaccine",
  "specialties": ["fire", null, "battle"],
  "techniques": ["Spit Fire", "Fire Tower", "Magma Bomb", "Heat Laser", "Red Inferno", "Sonic Jab",
                 "Muscle Charge", "Pepper Breath"],
  "drop": {"item": "sm.recovery", "percent": 50},
  "model": {"name": "AGUM", "bones": 22, "radius": 120, "height": 250},
  "voice": 3,
  "battle_music": "normal-battle",
  "new_game_technique": "Spit Fire",
  "partner": {
    "voice": 1,
    "hunger_hours": [1, 5, 9, 13, 17, 21],
    "energy_max": 40,
    "energy_fed": 20,
    "energy_per_hour": 5,
    "poop_timer_10min": 24,
    "poop_size": 8,
    "favorite_food": "Meat",
    "sleep_cycle": "19:00-04:00",
    "favored_region": 0,
    "training_type": "even",
    "birth_weight": 15,
    "status_screen_position": [550, 230, -1870],
    "item_distance": 10,
    "training": {"animation": 51, "hit_tick": 12}
  }
}
```

An imported species (`180-veemon.json`) has `model.file`, `model.skeleton`, `texture`, `effects_like`,
`effect_origins`, `condition_bubble`, `wild` and `evolution` too; an enemy-only original (`100-icedevimon.json`)
has no `partner`. Rules: keys are snake_case; values are **named where the meaning is known** (the tables below)
and raw game numbers otherwise; units are the game's own, named in the key where they are not plain
(`poop_timer_10min`, `energy_per_hour`, `hunger_hours`, `drop.percent`); species are referred to by **number**
(50 names are shared by NPC twins: `species.py show ID` prints the names as comments); techniques and items by
name, a name shared by several techniques written with its id (`"Bubble (117)"`, `"Dynamite Kick (44)"`), a
bare number accepted; keys starting with `_` are comments. `species.py fmt` writes the canonical layout (short
lists and objects on one line); load → dump is byte-equal (selftest `species-format`).

| Key | Game field | Values | When absent |
|---|---|---|---|
| `id` | the species number | 0..1023 | required |
| `name` | `DigimonPara.name` | ≤ 19 ASCII characters | required |
| `level` | `level` (`include/dw/level.h`) | `none` `fresh` `in-training` `rookie` `champion` `ultimate` `mega` | required |
| `attribute` | `type` (the 3×3 `FLEE_CHANCES` matrix) | `none` `data` `vaccine` `virus` | required |
| `specialties` | `special[3]` | 3 slots, each `fire` `battle` `air` `nature` `ice` `mech` `filth` or `null`; positional: the slot number is the learn-chance column (`MOVE_LEARN_CHANCES[tech][slot]`), slot 0 the element learnt on evolving | required |
| `techniques` | `moves[16]` | ≤ 16 techniques in slot order (slot *i* plays animation 0x2E+*i*; the finisher is the last id in 58..112), `null` keeps a slot empty, a shorter list is padded with empty slots; `[]` = sixteen empty slots (255); `null` = the row of sixteen 0s of the NPC-only species | required |
| `drop` | `dropItem`, `dropChance` | `{"item": name, "percent": 0..100}` (`dropChance > rand(100)`) | item 0, 0 % |
| `effects_like` | `ORIGINAL_DIGIMON_TYPES` / record `originalType` | the species whose technique effect origins (EFE rows), aura row, condition bubble, projectile icon and cup lists it uses | itself (originals); required for imports |
| `model.name`, `model.bones` | `PTR_DIGIMON_FILE_NAMES`, `boneCount` | the disc's model file `CHDAT/MMD<id/30>/<name>.MMD` and its skeleton's bone count (the shared skeleton arrays of the executable: not editable) | originals only, required |
| `model.file` | | a model file (built, not committed): for an original it replaces the disc's file (`build-disc.py --file`); for an import the model inside `DIGI.DAT` | the disc's (originals); imports: required (or `model.from`, an original's model) |
| `model.partner_file` | `PARTNER_MODEL_FILES` (model.c) | a model the species loads as a partner, added to the disc root (115 → `MUGP.MMD`, 116 → `ANLP.MMD`, 117 → `JIJP.MMD`) | none |
| `model.skeleton` | record `bones[]` | `[[object, parent], …]`, ≤ 34 for a partner, ≤ 64 | imports only, required |
| `model.slot_aliases` | the model's animation table | `[[slot, source], ...]`: the slot plays the clip of the source slot (a table entry pointing at the same animation, the table grows if needed); applied when the model is read for the build and for lint, the file in `build/` is not edited. Used for the provisional finishers: slot 0x2E + the finisher's index plays one of the model's own attack clips | none |
| `model.radius`, `model.height` | `radius`, `height` | world units (100 = one tile): collision, shadow, camera, bubbles | required |
| `texture` | record `texSector` | `{"file": TIM, "entry": N}` or `{"from": id}`, plus `"hue"` (degrees) or `"swap"` (`"bgr"`…) | originals: `ALLTIM.TIM` entry = id; imports: required |
| `voice` | `DIGIMON_VBALL_SOUND_ID`, record `vballId` | VBALL chunk (short voices: battle, NPC lines) | required |
| `battle_music` | `SPECIES_BATTLE_MUSIC`, record `battleMusic` (patch 0081) | the font 0x21 track it plays as a wild enemy: `event-battle` `normal-battle` `normal-battle-2` `last-battle` (jukebox names, `BGM_TRACK_NAMES`) | required |
| `reincarnation_stats` | `REINCARNATION_STATS` (patch 0081) | `{"hp", "mp", "offense", "defense", "speed", "brains"}`: the stats it hatches with from the reincarnation egg (before the inherited share); 4 rows (Botamon, Punimon, Poyomon, Yuramon); the new eggs' babies (patch 0334, ids 470-473) hatch with the row of their `vanilla_as` | none |
| `new_game_technique` | `NEW_GAME_TECHNIQUES` (patch 0081) | an explicit opening technique from its list (Agumon and Gabumon retain the 2 authored rows); other quiz starters learn and equip what evolving into them teaches, the weakest technique of their main element (`evolutionFormula.learn`, patch 0332) | the weakest technique of its main element |
| `condition_bubble` | record `conditionFx` | `[x, y, z, bone]`: where the hungry/sleepy bubble hangs | the `effects_like` species' |
| `effect_origins` | record `effectOrigins` | `[[from bone, x, y, z, to bone, x, y, z], …]`, ≤ 8, x `"any"`: moves the `effects_like` species' effect origins onto its own skeleton (see `tools/mmdport.py`); `from` is an EFE row exactly as the disc has it (never scaled with the model) | none |
| `effect_origin_fallback` | record `effectDefault` (0x1C4, the effect origins patch, efe.c) | `[bone, x, y, z]`: where a technique whose effect has no origin row for its `effects_like` type starts when the technique's rows are mostly on bones (a breath, a shot; a table of mostly entity points takes the entity point of the row of the species closest in radius instead); never replaces a row; only a species carried by its record (a new species, a record original) | derived by `species.py` (`effect_default`): the place its effects type's bone rows most often start from, moved by its `effect_origins`; a species without a record drops the effect (`checkTechCompatibility`), and lint refuses such a technique |
| `effect_origin_fallback_always` | record flag 0x10 (`SPECIES_FLAG_SHOTS_FROM_DEFAULT`, efe.c) | `true`: the techniques whose table is mostly entity points start from `effect_origin_fallback` too, instead of the entity point of the species closest in radius; for a species that fires everything from one weapon (Beelzemon's cannon); never replaces a row | absent: `false` |
| `wild` | (tooling) | `{"hp", "mp", "off", "def", "speed", "brain", "bits"}`: the battle stats DWS `place` gives it when the source names none | DWS medians by level |
| `sizing`, `size` | (tooling) | the natural size measured from the model; a hand override `{"height", "radius"}` | none |
| `needs_ram_mb` | (build) | 8: a partner model that only fits the 8 MB buffer; left out of a 2 MB disc | 2 |
| `partner` | the partner rows (record `SPECIES_FLAG_PARTNER`) | present = it can be a partner; the keys below | not a partner |
| `partner.voice` | `DIGIMON_VLALL_SOUND_ID` | VLALL chunk (the long care voices) | 15 |
| `partner.hunger_hours` | `hungerTimes[8]` | ≤ 8 hours of the day (Fresh and In-Training ignore them: every 2 / 3 hours) | required |
| `partner.energy_max`, `energy_fed`, `energy_per_hour` | `energyCap`, `energyThreshold`, `energyUsage` | the cap; the energy at birth and the "fed" line (below it when the hunger times out: a care mistake); lost every game hour | required |
| `partner.poop_timer_10min` | `poopTimer` | game-time steps of 10 minutes (200 ticks; `skipHours` takes 6 per hour) until it needs to go; reset to it (porta-potty) or twice it (toilet) | required |
| `partner.poop_size` | `poopSize` | the pile's size: drawn scale, weight lost per poop; ≥ 11 a big pile, ≥ 14 a huge one | required |
| `partner.unk2` | `unk2` | unknown, never read; written only when not 1200 (every row has 1200) | 1200 |
| `partner.favorite_food` | `favoriteFood` | item name | required |
| `partner.sleep_cycle` | `sleepCycle` (`SLEEP_PATTERN` row) | `16:00-01:00` `19:00-04:00` `22:00-07:00` `02:00-11:00` `07:00-16:00` `10:00-19:00` (when it sleeps) or `fresh`, `in-training` | required |
| `partner.favored_region` | `favoredRegion` | 0..9: native kinds of place 0..8 and cold/water profile 9 (`content/map-regions.json`); each `.MAP` names the regions its screens please (sleep ×1.2, happiness +1 an hour) and displease; no names in the game, so a number | 0 |
| `partner.training_type` | `trainingType` | which stats train well (`TRN_calculateTrainingMultiplier`): `even` (all 1.0), `offense-speed` (Off/Spd 1.1, MP/Brains 0.9), `mp-brains` (MP/Brains 1.1, HP/Def 0.9), `hp-defense` (HP/Def 1.1, Off/Spd 0.9), `all-low` (all 0.8) | `even` |
| `partner.birth_weight` | `defaultWeight` | the weight it starts with (1..99, the number the game shows) | required |
| `partner.status_screen_position` | `viewX/Y/Z` | where the model stands on the status screen (`game_menu.c`), world units | required |
| `partner.item_distance` | `ITEM_TAKE_DISTANCE` | how close the Tamer must be for it to take an item: reach = value × 20 + 160 world units | 10 |
| `partner.training`, `partner.training2` | `TRN_` / `TRN2_TRAINING_ANIM_IDS` | `{"animation": 0x2E..0x3D (a technique slot), "hit_tick": the 20 Hz tick after it starts on which the hit lands}`; `training2` (the second gym) only when it differs | `{46, 10}` |
| `status_screen_position`, `partner_voice`, `item_distance`, `training` | the same rows, outside `partner` | rows the tables keep for a species that is not a partner: the Tamer (0) has a status screen position and VLALL 0; in the disc's extraction, 66 has an item distance and a training row | zeros (VLALL 15) |
| `evolution` | record `evoReqs`, `evoGains`, `evoPaths` + the links | **provisional**, imports only: `from`, `to`, `requirements`, `gains` as the old files had them; the evolution design replaces it. The originals' evolution rows stay in the executable and in `content/balance/engine/tables.json` | every requirement −1, no gains, no paths |
| `_source`, `_…` | comments | | |

Not in the files: padding (always 0, the extractor checks), the dead row of `ITEM_TAKE_DISTANCE` (type 180, written
0), the rows of the per-partner tables of a species without `partner` (zeros, VLALL 15: what the C has).

Status portraits use `renderDigiviceEntity`'s perspective camera: eye
`[1300, 0, -3280]`, target `[0, 0, 0]`, projection distance 512 and screen
origin `[160, 120]`. On every render pass the menu resets slot 0, advances it
once and draws that pose. Audit that actual first tick, rather than shrinking
a travelling model to accommodate idle poses the menu never displays:

```sh
python3 tools/status_portraits.py build/NAME --out build/status-audit --check
python3 tools/status_portraits.py build/NAME --out build/status-size-audit --enlarge-small --check
```

The audit covers every raisable species using the built archive, resident/cold
joins, native models, runtime skeletons, scale rules, texture transparency,
face culling and all animated flame phases. Native camera rows come from the
built executable, with the same record-original replacements copied at boot.
The audit also checks that every language executable has matching camera rows. Opaque pixels must stay inside
`x=14..158`, `y=105..153`, clear the Status label (`x=20..80`, `y=107..120`)
and clear the sleeping badge (`x=67..78`, `y=121..141`, including its full bob).
Life starts at `y=154`; the model must not obscure hearts or care labels.
The first pose must remain at least 20 opaque pixels tall. Merely staying
inside the outer box is insufficient: a portrait can still cover its text.

`--fix` edits only `partner.status_screen_position`. The fitter solves the
smallest camera-depth increase for an inset rectangle and preserves the old
screen anchor where space permits. It checks several placements beside/below
the label and accepts one only after raster verification. It never moves the
camera closer unless a portrait is below the 20-pixel readability floor.
`--enlarge-small` also compares each portrait with its largest raster-verified
fit and repairs those below 85% of that attainable height. This recovers
space lost to earlier fits of travelling idle poses; wide silhouettes retain
their proportions. Both passes edit camera coordinates only, preserving
model scale, geometry, field size and animations.
Already fitting positions remain unchanged unless selected by the size check.
`--check` exits nonzero if any
built preview still needs repair. Geometry projection approximates the GTE,
so review actual emulator captures as well.

`--all-idle` retains the conservative full-animation diagnostic. Its bounds
are not the live Status view; a wide travelling idle may not fit readably
when all its non-displayed poses are included. Normal audits and repairs use
one rendered pose plus all of its texture phases.

A travelling imported idle can optionally set `partner.status_screen_anchor_bone`
to a bone index. The camera follows that bone by translating the complete posed
model; local bone transforms and field animation stay unchanged. The renderer
restores the world position after drawing. Zero/unset retains the original
view. Aquilamon uses this to keep its flight and wing poses readable without
fitting the entire flight trajectory into a tiny silhouette. The byte is stored
at `0x1CE` in existing species-record padding: record/cache sizes do not grow.

`--reference ORIGINAL_AUDIT.json` supplies original positions and restricts a
readability repair pass to that audit's fixed set. `--verify-repairs AUDIT.json`
checks the stored positions of that fixed set after rebuilding, without fitting
them again. The tool writes `audit.json`, changed-only contact sheets and an
unchanged borderline list. Review media should include the actual care rows
and compare the released appearance, the previous positions and the repair.

**What stays in C** (per-species rules that are code, not tables): Machinedramon's last-battle track (`btl.c`: the
first enemy of type 0x73, before the scripted-battle rule), `MOD_TECH_DONORS` (efe.c, the NPC partners' technique
effects), the originals' condition bubble and aura rows (`CONDITION_FX_OFFSETS`, `*_AURA_PROJECTILE_TYPES`: aura rows
have four unknown fields), the arena/VS sprite and name tables, Meteormon's ×1.5 scale, the flame textures, the lab
menu's list of NPC partners, the partner-only file table (`PARTNER_MODEL_FILES`; the files themselves are in
`model.partner_file`), and the id-keyed rules (shop keeper, Kunemon's collision, Sukamon/Numemon, prosperity points, raised/recruited flags).

## The evolution of a species of the disc

A species of the executable's tables (0..179 without a record) holds its own evolution rows, the source
`balance.py` writes the executable from:

```jsonc
"evolution": {
  "from": [-1, -1, 2, -1, -1],          // EVOLUTION_PATHS, types 1..62 only: 5 slots, -1 = empty
  "to": [5, 9, 21, 36, 47, 8],          // 6 slots; the position decides ties (the first wins)
  "requirements": { "digimon", "hp", "mp", "offense", "defense", "speed", "brain", "care", "weight",
                    "discipline", "happiness", "battles", "techs", "flags" },        // EVOLUTION_REQS, -1 = none
  "gains": { "hp", "mp", "offense", "defense", "speed", "brains" }                   // + "target" when not its own id
}
```

Every one of the 147 has `requirements` and `gains` (the rows of a species that is no partner are zeros, kept so the
table is byte for byte). An imported species links itself into these lists with its own `evolution.from` (the build
fills free `to` slots at boot). A record parent reaching a disc child with no paths of its own (for example Myotismon) stores the route in the parent's `evolution.to`; no reverse slot exists on that disc child. Such a forward route is valid and the builder does not warn about the absent reverse row. Real slot overflow still warns and loses the link.

The curated additions and Mega reparenting live in `content/tables/evolution-tree.json`; apply them with `tools/evo_tree.py --write`. Only listed children's `from` and requirements change, plus record parents' `to` entries for disc children. Parent order names the primary bonus. Limits remain six children, five parents and 510 links with originals (the two-sector index); the builder counts the engine layer's existing slots too. Canon main lines precede family/shared-specialty routes, and imported canon Megas require Perfect parents. The documented exceptions preserve existing disc/engine routes and the Kurisarimon → Infermon canon line. The starter quiz's Rookie → Champion routes are outside this generator's scope.

A deleted species (no file) is taken out of them. `species.py extract`/`sync` write the
key from an executable (the round trip is exact).

## Deleting a species

The build starts from zero: a species of the disc (0..179) whose file is deleted does not exist. Its id
stays (the tables are indexed by it) with empty rows: no name, level none, no techniques, not a partner, no evolution row,
in no evolution list (a disc row's slot naming it becomes -1, an import's link to it is dropped), and the evolution items
that gave it give nothing. Imports may still borrow its model, texture or effects (`effects_like`, `model.from`,
`texture.from`): those are disc assets by id. What still places or names it stops the build (`tools/missing_refs.py`): a
`.MAP` Digimon slot of it, a story use (spawn, recruit, battle); a question `recruited(Species.X)` answers no. The story
still compiles with its name (the disc's name stands for an id without a file). An imported species (180..) is left out by
deleting its file or leaving it out of `SPECIES`.

Proven with Centarumon's file and Amida Forest's script deleted: its rows empty, in no evolution list,
item 74 gives nothing; in the emulator an Agumon meeting Centarumon's requirements evolves into it on the plain disc and
into nothing on that one.

## Commands

```bash
python3 tools/species.py extract                # build/species-original: the 180 files from your disc (original values)
python3 tools/species.py diff                   # content/species against them: the mod's changes, field by field
python3 tools/species.py verify                 # content/species 0..179 == the tables of the linked build (the drift check)
python3 tools/species.py sync ID ... | --all     # a C patch changed a table on purpose: pull the C values into those files
python3 tools/species.py lint [--files]          # what the game cannot handle (build-full.sh runs it)
python3 tools/species.py show 124               # one species, species numbers named in comments
python3 tools/species.py fmt [--check]          # the canonical layout
python3 tools/species.py build [--species SEL]  # build/species/DIGI.DAT (checks sizes, bones, links)
python3 tools/species.py check                  # parse it back; records 0..179 == the species files
python3 tools/species.py list [--all]
python3 tools/species.py select "180 181 182 373" -o DIR --models M   # a build's species folder (build-full.sh)
python3 tools/species.py materialize DIR        # files of the old sparse format ("base", "para") -> complete files
```

An edit of a species file is what the build writes (the C initializers stay as the decompilation has them;
`verify` lists the edits). A C patch that changes a per-species table since the last `sync` (the baseline
`content/balance/engine/species-c.json` holds the hashes) makes `verify` and the build's `balance.py build` stop,
naming the species, the field, the C value and the JSON value: edit the JSON, or `sync` the species when the C
change was meant. `species.py lint` validates the values.

## Adding or editing a species

Choose an unused id within `NUM_DIGIMON` before adding a record; the imported
species already occupy many ids above 179. `tools/species.py add --help` describes
copying a base record and setting numeric fields. Keep the complete species JSON
as source. For imported model edits use [model deltas](../../content/modeldelta/README.md),
not a committed converted model. A species no source game has is drawn by hand on a DW1
donor's rig: [hand-made species](hand-made-species.md) describes the method.

The everything build selects all species through its V61 provider. Check a changed
record with `species.py lint` and rebuild through [building](../building.md), which
runs derive and writes `DIGI.DAT`, the executable tables and the disc file plan.
For a custom selection, `SPECIES` accepts ids or folders; keep the matching provider
and recipe settings consistent.

Place or replace NPCs through [Python story handlers](story-language.md). The
compiler updates map slots and MAPHEAD setup together, selects wide id operations
for the target and checks the screen's heap. Avoid hand-editing generated bytecode.

For runtime testing, the CHEATS interface can select a partner or trigger an
evolution. Test the species' field animations, battle moves, texture, evolution
and screen transitions on the integrated disc with the original 2 MB settings.

## Limits

- **1024 ids** (`NUM_DIGIMON`): the header count is 16-bit, ids are `int16_t`
  everywhere, and a species record costs nothing resident; what each new
  species costs is disc (its 512-byte record and its model and texture,
  ≈ 100 + 18 KB) and, when it is a partner, a slot of the 1022-entry partner
  list and of the 510 evolution links with the original species. Resident
  cost of the scale patches: the partner list (2 KB), the two flag bitsets
  (256 B) and the 16-record cache (8 KB), against the 19 KB of per-partner
  tables of the 256-id build (now 180 rows: −5.8 KB).
- **Voices** are existing `VBALL`/`VLALL` entries.
- **Partners**: model ≤ `PARTNER_MMD_MAX` bytes (the partner model buffer: the
  original's 0x18800; read the prepared target's `memmap.h` and final build facts
  for the selected buffer and link-time heap constraints),
  ≤ 34 bones, and the animation slots the partner state machine uses (0–14,
  0x21–0x24, 0x2C, techniques): copy a partner's MMD. A model bigger than the
  buffer is not loaded as a partner (the lab menu says "Model too big for it",
  natural evolution skips it, the loaders never write past the buffer).
- **Evolution links** need a free slot among the 6 targets of the species it
  evolves from (Agumon has none: `build` warns). Species >= 63 among the
  originals have no evolution paths. The evolution chart's overview has 61
  boxes: a new species is shown in the detail view of its parents (and has a
  detail view of its own, reached from them), with an icon rendered from its
  model.
- **Cups and VS**: new partner species join the tournament pool as opponents
  (level of the cup's list), can register for cups as the originals of their
  level, and have icons in the bracket and the VS lists.
  The intro name tables (`STD_INTRO_DIGIMON_NAMES` 0..111,
  `VS__INTRO_DIGIMON_NAMES` 0..115) still read row 0 (a blank name) for another
  type; a VS registration of a species >= 256 is stored as the original it is
  based on (the record has a byte).
- **Shop stock** (`TRIGGER_SHOP_STOCK_BASE` + item) is not a species flag:
  items stay at 128 (`NUM_ITEMS`).
- A record not cached when first needed (a species shown in a menu without
  its model loaded) is read synchronously, after the asynchronous file queue
  is empty.

## Curated tiers and balance

`content/tables/evolution-tree.json` owns the complete partner topology, identity-sheet Mega ids and 26 other tier changes. The 15 native ids with unequal on/off levels are 24, 59, 60, 63, 65, 67, 69, 88, 94, 104, 113, 115, 116, 117 and 120. `balance.py` mirrors their level into the resident table as well as their carried record; `species.py verify` checks that path after balance build. Record originals still keep their other resident fallback rows. Parents are limited to five, children to six, with Baby II extra Rookie slots handled separately. Mod-added routes share a specialty, apart from the documented canon Otamamon → Geremon exception. Original-disc routes are exempt by membership in the committed disc path tables; original battle specialties are preserved. Numemon → KingSukamon replaces its non-shared WaruMonzaemon route. Every ordinary link advances exactly one level with NEW DIGIMON on, including native Megas. Every raisable Ultimate has at least two distinct Mega targets: ordinary children or, for native species without path rows, timed `evolutionUltimate` pairs listed in `ultimate_rules`. MegaKabuterimon keeps HerculesKabuterimon and gains GranKuwagamon; Garudamon gains Phoenixmon. The guard checks stage progression, distinct choices, practical chains and agreement between the documented timed pairs and the game rules. Each changed route and requirement has a reason in the curated table.

Canon levels: species JSON supplies the NEW DIGIMON on level. An original whose level differs from `content/tables/original-species-levels.json` must declare `"off": {"level": "ultimate"}` (lint uses this committed baseline, never the disc). `"stats"` contains all six evolution target stats (required for unequal on/off levels, optional for route-only overrides): `hp`, `mp`, `offense`, `defense`, `speed`, `brains`; HP/MP are 0..9999, the rest 0..999. These are evolution targets, not the current partner's trained stats. Only explicit `off` entries enter DIGI.DAT's header at `SPECIES_HEADER_LEVEL_OFF`; no fallback is inferred from the player's disc. Imported partners use their explicit `vanilla_as` species. The runtime applies the configured level at boot and when NEW DIGIMON changes. The original evolution items use the configured off level. Levels are not saved. Phoenixmon, HerculesKabuterimon, MetalEtemon, Machinedramon, Analogman and Jijimon are Mega with the option on and explicitly Ultimate off. Their original Champion routes survive only in explicit off paths, in both directions. Red Ruby, Beetlepearl and Metalbanana require an Ultimate while their target is Mega; Noble Mane requires a Champion before Ultimate IceLeomon.


The tree generator applies frozen tier balance only when changing a level, preserving subsequent raise balancing on regeneration. `content/tables/evolution-balance.json` freezes peer-derived evolution gains, wild stats, drops and raise capacities/consumption/weight for each moved species. Peers have the same level and training role, with native disc peers preferred. Mega gains use the top Ultimate distribution and the original WarGreymon sample. Model dimensions, model/texture bytes, food preferences and sleep personality are preserved. Kurisarimon follows the identity sheet's Mech/Nature specialties and complete proposed techniques, with Sweet Breath as finisher. Technique-slot aliases point the new attacks at Kurisarimon’s existing attack/buff programs; no mesh, texture or new animation assets are authored. Rookie requirements use distinct highest-stat/weight slots under each Baby II; Mega rows retain their first-parent bonus and are resolved from every Ultimate parent.

Off target stats are stored at header offset `0x580`: a little-endian u16 count, then up to 19 rows of u16 species id, six on targets, six off targets (HP, MP, offense, defense, speed, brains). The runtime reads this header on option changes using its existing sector buffer; it allocates no persistent stats cache.

A tier change can also declare `off.evolution` for resident species 1..62: exactly five `from` and six `to` ids (`-1` pads unused slots), and an optional complete `requirements` row in the usual species format. All routes and requirements are JSON data. Header offset `0x3c` points to an optional sector with a u16 row count and up to 20 rows: u16 id, eleven signed on path ids, eleven signed off path ids, the 28-byte on requirements, then the 28-byte off requirements. The runtime rereads that sector on option changes; no path cache is retained. `off.level` may equal the on level for species that only need path restoration.

Whamon (24) uses the [official Ultimate form](https://digimon.net/reference_en/detail.php?directory_name=whamon). Its on targets are HP 6000, MP 4500, offense 400, defense 550, speed 450 and brains 500. Its native Ice arsenal (including Aurora Freeze and Winter Blast), Nature control techniques and finisher identity remain; finisher power is 210 on and 150 off. Seadramon, Shellmon and Ikkakumon lead into it; Plesiomon, MetalSeadramon and Vikemon continue the aquatic family. Explicit off data restores Champion targets 2500/1500/100/150/100/200, requirements and the Palmon/Betamon/Penguinmon routes. Dolphmon inherits its former Champion requirements and adds Palmon and Penguinmon beside Betamon and Gomamon; all share Ice. Giant story Whamon (146) is unchanged.

### Mode technique and finisher balance

A native species with explicit on/off blocks may declare `finisher: {"power": 210, "mpCost": 40, "element": "ice"}`. This adjusts the last finisher id in its technique slots; it does not replace its animation or effect identity. `mpCost` is stored units (ordinary techniques charge three times that amount; finisher execution consumes its gauge and skips MP deduction). For a mode change, `off.techniques` and `off.finisher` explicitly own the other mode. Null slots disable techniques without shifting animation indices; nonempty identities at the same slot must agree across modes.

Header offset `0x4fc` points to an optional sector: u16 count followed by up to 19 rows of u16 native species id and two 21-byte mode blocks (on then off). Each block holds 16 technique bytes followed by u8 finisher id, little-endian u16 power, u8 cost and u8 element. Only active finisher scalars remain resident. Partner-menu, battle, tournament and versus readers resolve these by casting species, so a shared technique id can have different species values. Global technique JSON remains the source for level-independent distance, accuracy, effect and status fields. The record format and version remain unchanged.

Lint requires every species with unequal on/off levels to declare six targets, technique slots and finisher scalars in each mode. The frozen fit bands in `content/tables/species-mode-balance.json` apply to both blocks; incomplete or out-of-band balancing fails.

Whamon (24) uses the [official Ultimate form](https://digimon.net/reference_en/detail.php?directory_name=whamon). Its on targets are HP 6000, MP 4500, offense 400, defense 550, speed 450 and brains 500. Its native Ice arsenal (including Aurora Freeze and Winter Blast), Nature control techniques and finisher remain. Seadramon, Shellmon and Ikkakumon lead into it; Plesiomon, MetalSeadramon and Vikemon continue the aquatic family. Explicit off data restores Champion targets 2500/1500/100/150/100/200, requirements and the Palmon/Betamon/Penguinmon routes. The three Rookies retain five/four/five Champion choices on. Giant story Whamon (146) is unchanged.

## Machine-line identities

Assaultmon keeps Machine/Battle and its existing armed moveset. Datamon uses
Machine/Air/Fire: its eight Machine moves are joined by Electric Cloud, Megalo
Spark, Static Elect, Prominence Beam and Heat Laser. Infermon uses Machine/Plant,
continuing Kurisarimon's specialties, with poison, Bug, Insect Plague and Mass
Morph alongside its Machine moves. Diaboromon uses Machine/Plant/Battle, adding
Megaton Punch, Buster Dive and Counter to the Machine and poison/Bug core.

The finishers remain Genoside Attack (215 power), Smiley Bomb (225), Deadly Bomb
(260) and Dark Shot (200), respectively. The first three are in the native
Ultimate finisher range; Diaboromon keeps its existing Mega finisher, also used
by other imported Megas. These identities preserve every evolution edge's
shared specialty and use the existing technique animation slots.
