# Ids: species, screens, items, techniques, cards and files

The id spaces of the game: what each kind of id numbers, its range and width in the original executable, where it
is stored and which tables it indexes, and how the mod's executable extends it (16-bit carriers, `NUM_DIGIMON` 1024,
`NUM_SCREENS` 1024, new file names). It also lists the places where an id range is shared with something else, since
these break silently when a range grows.

**Conventions.** Source references are `decomp/src/main/...` (or the overlay directory named) and
`decomp/include/dw/...`, by file and function. RAM addresses are those of the **original US executable**; the GCC
build places variables by link order, so its addresses differ (`tools/dev/symbol_addresses.py NAME --gcc`). Patch numbers refer to
`mods/patches/`.

## Overview

| Id space | Original range | Original width (carriers) | Mod range | Mod type | "None" | Patches |
|---|---|---|---|---|---|---|
| Species (Digimon type) | 0–179 (0 = the tamer, 1–65 partners) | i32 in entities, u8 in many carriers, s8 in `EVOLUTION_PATHS` | 0–1023 | `DigimonId` (i16) | −1 | 0013, 0016, 0017, 0051, 0065 |
| Screen | 0–254 | u8 | 0–1023 | `ScreenId` (i16) | −1 (0xCC at boot, see below) | 0013, 0015, 0146 |
| Item | 0–127 | u8, 0xFF = empty | 0–127 (carriers hold any i16) | `ItemId` (i16) | `ITEM_NONE` (−1) | 0018, 0019 |
| Technique | 0–121 (121 named) | u8, s8 in TRN | unchanged | `MoveId` (u16) | — | 0014 (opcodes) |
| Card | 0–65 | u8 | unchanged | `CardId` (u16) | — | 0014 (opcodes) |
| Music font | 1–33 | u8 | unchanged | — | 0xFF / 0xFFFF stops | 0014 (opcodes) |
| Trigger | 0–799 (no bounds check) | u16 | unchanged | — | — | — |
| Pstat | 0–255 | u8 value, u8 index | unchanged, plus 64 u16 wide registers | — | — | 0014 |
| Script (DG.SCN entry) | 0–221 | u16 | unchanged | — | — | — |
| MAPHEAD section | u16 | u8 in `runMapHeadScript` | u16 | — | — | 0015, 0146 |
| File | 819 names | looked up by name | 819 + mod entries + `NEW_FILES` | — | — | 0147, 0209, 0210 |
| World object | per object kind | i16 object id + instance | entity text and dropped item moved above species | — | — | 0082 |

## The id header and the memory map

Patch 0013 adds two headers that the rest of the series builds on:

- **`include/dw/ids.h`**: the id typedefs, the counts, the trigger bases and the single declaration of
  `CURRENT_SCREEN`/`PREVIOUS_SCREEN` (the original declares them separately in 18 files). Every table and loop that
  means "one per species / screen / item / ..." uses these names instead of literals.
- **`include/dw/memmap.h`**: plain `#define`s shared by C and the linker scripts (`psx.mk` runs every `.ld` through
  the C preprocessor): the load area (0x80010000–0x80090000), overlay bases, fixed buffers, the battle prefix (one
  definition for BTL, STD and VS), stack and `MIN_HEAP`, with link-time `ASSERT`s (every overlay inside the load area,
  TRN/TRN2 ≤ 0x8008F800, DOOA and MURD below their ordering tables at 0x8008C000, `main`'s bss end plus `MIN_HEAP` below
  the stack). The heap budget is in [memory.md](memory.md).

The constants of `ids.h` as the series leaves them:

| Constant | Value | Meaning |
|---|---|---|
| `NUM_ORIGINAL_DIGIMON` | 180 | the disc's species: `DIGIMON_DATA`, models, skeletons, voices, `ALLTIM.TIM` |
| `NUM_DIGIMON` | 1024 | species id capacity; `DIGI.DAT` ids are below it (0051 set 256, 0065 1024) |
| `NUM_PARTNER_DIGIMON` | 66 | `RAISE_DATA` rows of the original, cards; partners are 1..65 |
| `NUM_EVOLVING_DIGIMON` | 63 | `EVOLUTION_REQS` (by type), raised flags; `EVOLUTION_PATHS` has one row fewer (by type − 1) |
| `NUM_EVO_CHART_DIGIMON` | 61 | `EVO_CHART_BOXES`, by type − 1 |
| `NUM_RECRUITABLE_DIGIMON` | 0x70 | legacy recruited triggers only: 200 + type, types 0..111; higher types use saved bits |
| `NUM_ORIGINAL_SCREENS` | 255 | screens with a resident `MAP_ENTRIES` row and MAPHEAD section; what a v1 save byte can name |
| `NUM_SCREENS` | 1024 | screen id capacity (overridable at build time) |
| `SCREEN_LEGACY_NONE` | 0xCC | boot value of the current screen (see Screens) |
| `NUM_ITEMS` | 128 | `ITEM_PARA`, `ITEM_FUNCTIONS`, the 16×8 icon grid |
| `NUM_MOVES` | 122 | `MOVE_DATA` rows (row 121 is the flattened Digimon's projectile) |
| `NUM_MOVE_NAMES` | 121 | `MOVE_NAMES`; `drawMoveName` checks this bound |
| `NUM_LEARNABLE_MOVES` | 58 | `MOVE_LEARN_CHANCES`, the technique grid |
| `NUM_CARDS` | 66 | `CARD_DATA`, `CARD_SPRITE_CLUT`, `CARD.ALL` |
| `TRIGGER_RECRUITED_BASE` | 200 | + species below 112 |
| `TRIGGER_SPECIES_RECRUITED_BASE` | 0x8000 | script operand + species 112..1023, redirected to recruited bits (0303) |
| `TRIGGER_SHOP_STOCK_BASE` | 0x180 | + item |
| `TRIGGER_RAISED_BASE` | 0x200 | + species |
| `LEGACY_ID_NONE` | 0xFF | "none" in the u8 layouts (inventory slots, item bytes) |
| `ITEM_NONE` | −1 | an empty item slot in RAM (patch 0019) |

## Species

Type 0 is the tamer (HIRO); partners are 1..65; the NPC-only species follow up to 179. The original writes the counts
as literals (`[180]`, `[66]`, `0xB4`, `0x41`) almost everywhere.

### Where a species id is stored

| Where | Original width | Mod | Notes |
|---|---|---|---|
| `Entity.type` (partner, NPC, tamer, fighters) | i32 | — | already wide |
| `MapDigimonEntity.typeId` (`MAP_DIGIMON_TABLE` 0x8013CB50, 8 × 196 B) | i16 | — | read from the `.MAP` as i16, −1 = empty |
| `SavegamePayload.partnerType`, `SavedState.partnerType` | i32 | — | already wide |
| `EVOLUTION_TARGET` (0x80134E50), `EvoSequenceData`, `EvoStatsGains.targetDigimon`, `EvoRequirements.digimon` | i16 | — | |
| `LOADED_DIGIMON_MODELS` (0x801BE7EC) | i32[8] | — | the NPC model slots of a screen |
| `ORIGINAL_DIGIMON_TYPES` (0x8012A84C) | i16[180] | — | the type whose technique effects a species uses |
| `EVOLUTION_PATHS.from[5]` / `to[6]` (0x8012B66C) | **s8** | `DigimonId` (0016) | −1 = empty, one entry −2; s8 capped ids at 127 |
| `RegisteredDigimon.digimonId` (VS registrations, 40 slots, saved) | u8 | u8 | a species ≥ 256 registers as the original it is based on |
| `CARD_DATA[66].digimonId` (0x8012FFD8) | u8 | u8 | |
| `EVOLUTION_ITEM_TARGET[44]` (0x80127C5C) | u8 | u8 | aliased, see Items |
| `BABY_IDS[8]`, `SHOPKEEP_DIGIMON_TYPES[11]` | u8 | u8 | content lists |
| `PARTICIPANT_TYPES[8]` (STD overlay) | u8 | u16 (0065) | a partner of 300 was truncated to 44 |
| `REINCARNATE_BABY_TYPE[4]` (DOOA) | i16 | — | |
| Cup entrant lists (`DATA` blocks in map scripts) | u8 | u8 | 0xFE/0xFF terminate |
| Pstats (`STORE_DIGIMON_TYPE`, p4 = tournament Digimon, `{digimon N}`) | u8 | u8; a partner past 254 is stored as 0xFF and read back whole (0306); wide registers carry more | see Script ids |
| Opcodes `46` LOAD_DIGIMON, `47` SET_DIGIMON, `79` UNLOAD_DIGIMON | u8 | wide twins `80`–`82` | `3F` STORE_DIGIMON_VALUE takes the species from a pstat (0306 reads a partner past 254 back whole) |
| `loadNPCModel`, `scriptSetDigimon`, `unloadDigimonModel` | u8 params | `DigimonId` (0017), one prototype in `model.h` | the original had a u8 definition and an `int32_t` prototype |
| u8 locals holding the partner's type (`isPartnerBaby`, `startTournament`, `tournamentCheckFair`/`Eligible`, tournament registration, `getSpeakerName`) | u8 | whole type (0017) | a type above 255 no longer matches its low byte |
| `EfeTechBoneOffset.type` (EFE files) | i16 | — | |

### Tables indexed by species

**Per species (180), resident in the executable:**

| Symbol | RAM | Bytes | Readers |
|---|---|---|---|
| `DIGIMON_DATA` (`DigimonPara`, 52 B) | 0x8012CEB4 | 9 360 | about 340 references in 52 files; most read fields: `height`, `radius`, `level`, `moves`, `special`, `boneCount` |
| `PTR_DIGIMON_FILE_NAMES` + `char[8]` names | 0x8011D19C, 0x80133B44 | 720 + 1 440 | `loadMMD`, `loadMMDAsync`, `applyMMD` |
| `DIGIMON_SKELETONS` (pointers) + `SKELETON_*` (`{s8 obj, s8 parent}`, 78 shared arrays) | 0x8011CE60, 0x8011C170 | 720 + ≈3 300 | model setup, EVL, DOOA |
| `DIGIMON_VBALL_SOUND_ID` | 0x80127F40 | 180 | `loadDigimonSounds` |
| `ORIGINAL_DIGIMON_TYPES` | 0x8012A84C | 360 | `getOriginalType`, technique compatibility in STD |

**Per partner (about 66):**

| Symbol | RAM | Bytes | Index |
|---|---|---|---|
| `RAISE_DATA` | 0x801225BC | 66 × 28 | type |
| `EVOLUTION_REQS` | 0x8012ABEC | 63 × 28 | target type |
| `EVOLUTION_STATS_GAINS` | 0x8012B2D0 | 66 × 14 | type |
| `EVOLUTION_PATHS` | 0x8012B66C | 62 × 11 (s8; 22 B per row in the mod) | type − 1 |
| `EVO_CHART_BOXES` | 0x80124544 | 61 × 8 | type − 1 |
| `ITEM_TAKE_DISTANCE` | 0x80122D24 | 66 | type − 1 |
| `DIGIMON_VLALL_SOUND_ID` | 0x80127EFC | 66 | guarded `type < 66` |
| `CARD_DATA` | 0x8012FFD8 | 66 × 4 | card id |
| `TRN_`/`TRN2_TRAINING_ANIM_IDS` | TRN, TRN2 overlays | 134 each | type |
| `VS_DIGIMON_SPRITE_CLUT` | VS overlay | 68 | type |

**Tables that cover only part of the range** (the original indexes them by type without a bound):

| Symbol | Covers |
|---|---|
| `STD_INTRO_DIGIMON_NAMES` (14 B each), `STD_DIGIMON_SPRITE_CLUT` | types 0..111 |
| `STD_BRACKET_PROJECTILE_ICONS` | 112 entries |
| `VS__INTRO_DIGIMON_NAMES` | 0..115 |
| `ENEMY_MUSIC_MAPPING[48]` (`btl.c`) | 0x43 ≤ type < 0x70 |
| Recruited / tournament pool = trigger 200 + type | 0..111 |
| Raised = trigger 0x200 + type (`setDigimonRaised` guards `< 0x3F`) | 0..62 |

### Hard limits in the original code

- `type >= 0xB4` is rejected in `loadMMD`, `loadMMDAsync` and `applyMMD`.
- The model path digit `'0' + type/30` is cosmetic (`lookupFileTable` strips the directory), but stops being a digit
  at type 300.
- On-disc strides: `ALLTIM.TIM` is `type × 9` sectors; `VBALL` is 7 sectors per voice and `VLALL` 15.
- About 33 hard-coded species comparisons and one switch: Sukamon (0x27) in the partner and EVL code, 0x71 in battle
  and STD, Machinedramon's music (0x73), the shopkeeper (0x75), the STD remaps of 0x3F/0x40/0x41, nine flame-texture
  types in `animateEntityTexture`. They stay as code keyed by original id.
- Technique *k* of a species is animation `0x2E + k`, so a species has at most 16 techniques (a per-species limit).

### How the mod extends species

- **16-bit carriers** (0016, 0017): `EVOLUTION_PATHS` holds `DigimonId`s (the initializer's `0xff` "none" is −1 and
  its one `0xfe` is −2, equal to the original's s8 reading); the model and script parameters take a `DigimonId`.
- **Ids 180 and up are records of `DIGI.DAT`** (0051, 0065): `DIGI_PARA(t)` reads the resident `DIGIMON_DATA` row
  below 180 and, above, the record through a 16-slot cache of 512-byte records (`SPECIES_CACHE_SLOTS`,
  `SPECIES_RECORD_SIZE`). The per-partner tables keep their 180 original rows; for a type ≥ 180 `RAISE_ROW`,
  `EVO_REQ_ROW`, `EVO_GAINS_ROW`, `getItemTakeDistance`, `getPartnerVlallSoundId`, `getEvolutionPath` and
  `getTrainingAnimRow` return the record's partner block. A new species costs nothing resident. The record layout,
  the index sectors and the cache rules are in [../mods/species.md](../mods/species.md) ("How the game reads them",
  "Limits"); the model buffer sizes in [../mods/models.md](../mods/models.md).
- **Ids may skip numbers**: `tools/species.py` writes undefined records for the gaps and every reader checks the
  record's defined flag; an undefined id reads a blank parameter row.
- **Raised and recruited flags**: types without a trigger of their own (every id ≥ 180, and originals whose trigger
  is taken, `HAS_RAISED_FLAG`) use two 1024-bit bitsets, `SPECIES_RAISED_BITS` and `SPECIES_RECRUITED_BITS`, saved
  in the save extension. `hasDigimonRaised`, `setDigimonRaised`, `isDigimonRecruited` and `setDigimonRecruited` pick
  the trigger or the bit. Recruited state always uses trigger 200+id below 112,
  and `SPECIES_RECRUITED_BITS` for every ID 112..1023, including originals
  112..179. `HAS_RAISED_FLAG` applies only to raised state; it never grants a
  recruited trigger to those originals. Within 112..179, only 115, 116, 117,
  119, 120, 121 and 124 have raised triggers (627, 628, 629, 631, 632, 633
  and 636); every other ID there uses raised bits too. Recruit bits persist in save tag
  `0x0008`. Patch 0303 redirects script trigger operands 0x8070..0x83ff to
  these same bits for setting, clearing and testing, leaving ordinary triggers
  (including raised flags) untouched. No new opcode or save tag is needed.
- **Tournament and VS tables** (0065): reads go through `STD_ROW`/`VS_NAME_ROW` (row 0 is a blank name), the bracket
  draws no portrait outside its table and `stdWinChanceRow` clamps; MasterTyrannomon (124) already read past these
  tables in the original layout.
- **Prosperity** (0161, 0277, 0296, 0303): `recalculateProsperity` rebuilds pstat 1
  from owned roster members: a 14-byte membership table below 112 and a generated
  u16 list above it. Original story still counts only types 3..58. Opening the
  City tab, saves and game start refresh the total.
- **Record originals** (0084, 0106): an original id can be carried by its `DIGI.DAT` record, see
  [../mods/species.md](../mods/species.md).

### World object ids (patch 0082)

A Digimon's world object is the pair (object id = species id, instance = entity slot), and `removeObject` removes the
first match. The original's battle and VS objects use ids 0x190–0x1B0 (400–432), which collide with species ids once
species pass 400: with species 402 the partner's damage text (0x192, slot 1) removed the partner's own object and every
battle froze at its end. Patch 0082 moves the two overworld/battle objects that carry an instance number above the
species range (`include/dw/world_object.h`):

| Constant | Original id | Mod id |
|---|---|---|
| `OBJECT_ID_ENTITY_TEXT` | 0x192 | 0x1F92 |
| `OBJECT_ID_DROPPED_ITEM` | 0x195 | 0x1F95 |

The VS-only objects (0x198, 0x19C, 0x1A3, 0x1A9–0x1B0) still sit in 400–432, so species with those ids cannot enter VS
mode. More in [../mods/models.md](../mods/models.md) ("Object ids").

## Screens

### Where a screen id is stored

| Where | Original width | Mod |
|---|---|---|
| `CURRENT_SCREEN` 0x80134DA8, `PREVIOUS_SCREEN` 0x80134DA9 | u8 (16 separate externs) | `ScreenId`, one declaration in `ids.h` (0015) |
| `TARGET_MAP` 0x80134DE0 (exit tile → map change) | u8 | `ScreenId` |
| `.MAP` `MapWarps.targetMap[10]` | s16 on disc, stored into the u8 | whole value |
| `changeMap` → `runMapHeadScript(mapId & 0xff)` | u8 parameter | whole section id |
| `SCRIPT_SECTION` 0x80134FE4 | u8 | u16; `scriptPauseGame` still uses its low byte as an NPC script id |
| `CURRENT_SCREEN_ID` 0x80134FFE (set by `FB SET_SCRIPT`) | u16 | — |
| `loadMap`, `buildMapPath`, `getMapSoundId`, `loadDoors` | i16 | — |
| `getFileCityTopMap` | declared `int8_t` in `main_menu.c` | fixed: screens 0xAE–0xB3 would have gone negative |
| Opcodes `4B` WARP_TO, `58` TELEPORT (pstats p, p+1), `21` STORE_MAP_ID | u8 | wide twins `WARP_TO16`, `TELEPORT_W`, `STORE_MAP_ID_W` |
| Save `currentScreen`, `previousScreen`, `currentExit`, `previousExit` | u8 | v1 bytes keep the low byte; the extension holds the i16 |
| `PoopPile.map` (`WORLD_POOP[100]`, saved) | u8 | `ScreenId` (0146; −1 = none) |
| `BattleEntry.mapId` (Birdramon), `MapLightUpdateData.mapId` | u8 | the light table compares the whole id (0146: screen 439 lit screen 183's lamps before) |
| `BIRDRA_TRANSPORT_TARGETS[6]` | u8 | u8 (Birdramon's six targets are originals) |

Exits are 10 per screen (`MAP_WARPS` 0x80138730, collision tiles 110–119).

**0xCC is not "no screen".** `SCREEN_LEGACY_NONE` (0xCC, TWNA01 in File City) is the value of the current screen
before the first map loads (`initializeMap`) and the start section of a new game (`initializeDefaultSavegame`,
`runMapHeadScript(0xcc)`). Nothing compares with it, and `renderMap` reads `MAP_ENTRIES[CURRENT_SCREEN]` before the
first `loadMap`, so it must stay a valid row; it is kept rather than changed to −1.

### Per-screen tables of the original

| Symbol | RAM | Bytes | State |
|---|---|---|---|
| `MAP_ENTRIES[255]` (16 B: `name[10]`, `s8 n8, n4, flags, doorsId, toiletId, loadingName`) | 0x801292D4 | 4 080 | 244 named rows; free rows 239–246, 250–252 |
| `MAP_NAME_PTR[70]` (area captions) | 0x801291BC | 280 + strings | full (highest index 69) |
| `DOOR_MAPDATA[24]` (54 B) | 0x80122E60 | 1 296 | full; `doorsId` is s8 |
| `TOILET_DATA[10]` (8 B) | 0x80122E10 | 80 | full; `toiletId` is s8 |
| `MAP_SOUND_PARA[22]` (`{u16 sector, u16 count}`, by `flags & 0x1F`) | 0x80127FF4 | 88 | values 22–31 read past the table |
| `MAPHEAD.SCN` → `MAPHEAD_SCRIPT_BUFFER` | 0x801B1D30 | 0x61A8 (0x6800 in the GCC build, patch 0004; 0x8000 since patch 0091) | 255 screen sections plus 26 shared text/scene sections (1220 and up); ≈ 97 B per screen, all resident |
| `CHEST_ARRAY` | 0x80150F00 | 8 × 56 | per screen, refilled |

Small tables keyed by screen id: `SHOP_MAPS[8]`, `ARENA_MAPS[2]`, `BIRDRA_TRANSPORT_TARGETS[6]`,
`CONCAVE_SCREENS[18]` (`btl.c`). About 22 more sites compare screen ids in code: weather and mist
(`isMistActive`: 115–119, 121, 163, 220), the `changeMap` overrides, training spots, `getFileCityTopMap` (File City
168–203), fishing (6, 8), curling (136), the crystals (101–103), and the hard-coded ids 0x6A, 0x81, 0x8F of the
HUD/STD/battle UI.

**Trap:** `CONCAVE_SCREENS` includes 0xF7–0xF9, 0xFD and 0xFE, leftover MGEN rows. A screen placed on those ids gets a
concave battle arena.

### Screens 255 and up (patch 0146)

Screen ids are 0..`NUM_SCREENS` − 1. The 255 originals keep their resident `MAP_ENTRIES` row and MAPHEAD section; a
screen from 255 up is one 2048-byte sector of `SCRN.DAT` (`include/dw/screen.h`, `mod_screen.c`), so a new screen
costs no resident RAM.

- **File layout**: sector 0 is the header (magic `SCRN`, u16 first id, u16 count); screen *n* is sector
  1 + *n* − 255, so there is no index in RAM. A sector whose magic or id does not match is no screen; a disc without
  the file (its table entry points at sector 0) has no new screens and nothing else changes.
- **Record head** (`ScreenRecordHead`, the first 0x80 bytes):

  | Offset | Field | Meaning |
  |---|---|---|
  | 0x00 | `magic[4]` | `SCR1` |
  | 0x04 | `ScreenId id` | |
  | 0x06 | `u16 scriptSize` | 0 = no section of its own: falls back to MAPHEAD's |
  | 0x08 | `MapEntry entry` | the `MAP_ENTRIES` row; `doorsId`, `toiletId`, `loadingName` may be −1 (`SCREEN_OWN`) |
  | 0x18 | `u32 flags` | `SCREEN_FLAG_CONCAVE` 1, `_MIST` 2, `_SHOP` 4 (loads SHOP), `_ARENA` 8 (loads DGET) |
  | 0x1C | `ToiletData toilet` | its own toilet |
  | 0x24 | `door[54]` | its own `DoorStruct`: 6 model ids, then x, y, z, rotation of each |
  | 0x5A | pad | |
  | 0x5C | `caption[36]` | its own area name |

  At 0x80 follows the screen's MAPHEAD section as a script of its own (at most 1920 bytes; the largest original screen
  section is 718), laid out like `MAPHEAD.SCN`: u16 table size, (u16 section, u16 offset) pairs ending with 0xFFFF,
  then the code.
- **Cache**: `mod_screen.c` keeps the last sector read (2 KB, the running section of a new screen) and the heads of
  the last 4 screens named (the current screen's slot is never replaced): about 2.7 KB of bss and 1.3 KB of code
  whatever the number of screens. A record is read synchronously when the screen is named (the caption at the fade),
  then `runMapHeadScript` and `loadMap` hit the cache; per-frame readers read the current screen's cached head.
- **Readers**: `getScreenEntry(id)` (`SCREEN_ENTRY(id)`) returns `&MAP_ENTRIES[id]` below 255 and the record's row
  above; `getScreenCaption`, `getScreenToilet`, `getScreenDoor`, `getScreenFlags`; `getMapHeadScript(section)` is the
  script `callScriptSection(0, section)` and `JUMP_TO_FILE 0, section` run.
- **Special cases stay code keyed by original id** (fishing, curling, crystals, training, File City, UI ids). A new
  screen never matches them and gets the default behaviour; the four behaviours a new screen may want are its flags.
- **Paths**: `buildMapPath` makes `MAP<id/15+1>` (MAP69 for 1023); harmless, since lookup is by name.

The recipe (screen JSON, `tools/screens.py`, file names) is in [../mods/maps.md](../mods/maps.md) ("New screens").

## Items

### Original layout (128 items, u8 everywhere, 0xFF = empty)

| Symbol | RAM | Bytes | Notes |
|---|---|---|---|
| `ITEM_PARA` (32 B: `name[20]`, `i32 value`, `u16 merit`, `i16 sort`, `u8 color`, `u8 droppable`, `u16`) | 0x801269DC | 4 096 | |
| `ITEM_DESCS` pointers + strings | 0x801279DC | 512 + ≈3 200 | |
| `ITEM_CLUT_DATA` | 0x80127BDC | 128 | palette row 0..23 |
| `ITEM_FUNCTIONS` (effect function per item) | 0x80127C88 | 512 | |
| `EVOLUTION_ITEM_TARGET` | 0x80127C5C | 44 | **aliased**: `ITEM_EVOLUTION_TARGET(item)` is `(&ITEM_CLUT_DATA[0x39])[item]`; moving `ITEM_CLUT_DATA` breaks it |
| `INVENTORY` | 0x8013D474 | 0x5B | `types[30]` u8, `amounts[30]` u8, `names[30]` u8, `size` u8; saved |
| `DROPPED_ITEMS[11]`, `TAMER_ITEM` | 0x8013D4E0, 0x8013D4D0 | 176 + 16 | `type` i32, but `spawnItem` took a u8 |
| `CHEST_ARRAY[8].item` | 0x80150F00 | — | u8 |
| `RECYCLABLE_ITEMS[78]`, `MOJYAMON_ITEMS_GIVE/GET[12]` | 0x8012FE78, 0x80130438 | 78 + 24 | u8 lists |
| `DigimonPara.dropItem`, `RAISE_DATA.favoriteFood` | — | — | u8 |

**Collisions** (worse than a plain bound):
- **Shop stock** is trigger 0x180 + item (loop `< 128`): item 128 would be trigger 0x200, the raised flag of type 0.
- **Item Keeper** counts are `SCRIPT_STATE.smth[0x54 + item]`: item 128 would write `cards[0]`.
- **Icons**: `setItemTexture` uses `u = (id % 16)·16, v = (id / 16)·16` on a 256×128 4 bpp page at VRAM (320, 0):
  exactly 128 cells; ids from 128 read other textures.

**Hard-coded ids**: `handleChips` 0x16–0x20, `handleFood` 0x26–0x46, 0x79, 0x7A (`item.c`); the
`partnerWillRefuseItem` ranges; `handleEvoItems` maps 0x7D–0x7F to species 0x40/0x3F/0x41.

### How the mod extends items (patches 0018, 0019)

- `INVENTORY.types` is `ItemId[30]` and an empty slot is `ITEM_NONE` (−1), so 255 is an ordinary item.
  `giveItem`, `removeItem`, `getItemCount` take an `ItemId`; the inventory menu (names, sprites, descriptions, move,
  sort) is 16-bit.
- u8 sources keep their meaning through `itemFromLegacy()` (0xFF = none): the initial inventory, `GIVE_ITEM`,
  `REMOVE_ITEM`, `SPAWN_ITEM`, `SPAWN_CHEST` and the IF `item` condition.
- `DROPPED_ITEMS`/`TAMER_ITEM` mark a free slot with `ITEM_NONE`; `spawnItem`, `spawnDroppedItems`, `pickupItem`,
  `setItemTexture` and `renderItemSprite` take an `ItemId` (four disagreeing prototypes unified).
- `Chest.item` is an `ItemId` made of the old byte and the padding byte after it, so `Chest` keeps its 56 bytes.
- The v1 save keeps its bytes through `SavedInventory`: loading maps 0xFF to `ITEM_NONE`, saving writes the low byte;
  the full ids go to the save extension.
- `FISH_renderBaitMenu` read the amounts one array past `types`; it reads `amounts` directly.

Still bounded by `NUM_ITEMS` (128): the item tables, the shop, Item Keeper and recycle lists (u8 `ITEM_MENU` buffers),
p254 (the chosen item's low byte; w62 holds the wide value), the shop-stock trigger range and the 128-cell icon grid.

## Techniques

| Symbol | RAM | Bytes | Notes |
|---|---|---|---|
| `MOVE_DATA` (16 B) | 0x8012623C | 1 952 | 122 rows; row 121 is the flattened Digimon's projectile |
| `MOVE_NAMES` + strings | 0x80126054 | 488 + ≈1 600 | `drawMoveName` guards `< 0x79` |
| `MOVE_LEARN_CHANCES[58][3]` | 0x80125FA4 | 174 | no bound check |
| `PARTNER_ENTITY.learnedMoves[2]` | 0x80155800 | 8 | 64 bits, saved with the partner |
| `TRN_D_8008F14C[56]` (brains training) | TRN overlay | 56 | s8 technique ids, −1 sentinel |
| `PlayerData.usedMoves[12]`, `EQUIPPED_MOVES[4]`, `DigimonPara.moves[16]` | — | — | u8 |
| `EFEDAT.EFE` | disc | 0x5000 per technique | the loader accepts ids < 0x17A |

Layout baked into code: 8 learnable techniques per element, element bases 0, 8, 16, 24, 32, 40 and 49 (EVL); the
technique grid is `col + row·8`; aliased pairs 0x2C↔0x30 and 0x37↔0x39; the finisher window `0x3A ≤ tech < 0x71` is
hard-coded at about 20 sites in BTL and VS; consumers stop at 58.

**Original bug:** `unlearnMove` builds a 16-bit mask, so every unlearn also clears bits 16–31 of that word.

The mod adds `LEARN_MOVE16` and the IF `move16` condition but no technique ids beyond the tables.

## Cards

| What | Where | Notes |
|---|---|---|
| Collection | `SCRIPT_STATE.cards[33]` (0x801BDFAC) | one nibble per card, cap 9; saved |
| `CARD_DATA[66]` `{u8 digimonId, u8 rarity, i16 merit}` | 0x8012FFD8 | |
| `CARD_SPRITE_CLUT[66]` | 0x80123E28 | |
| `CARD.ALL` | disc | 14 sectors per card; exactly 66 cards |

Loops are fixed at `< 66`; the album is a 6×11 grid; the icon UV is `(card % 8)·32, (card / 8)·16`. The mod adds
`GIVE_CARD16`/`TAKE_CARD16` and the IF `card16` condition, still within 66 cards.

## Triggers, pstats and wide registers

`SCRIPT_STATE` is at 0x801BDED8, 0x29C bytes in the original:

| Field | Size | Contents |
|---|---|---|
| `smth[212]` | 212 | 0..5 today's recycle items, 6..83 recycle stock, 84..211 Item Keeper counts (128) |
| `cards[33]` | 33 | 66 nibbles |
| `triggers[100]` | 100 | 800 bits, at 0x801BDFCD |
| `pstats[256]` | 256 | u8, at 0x801BE031 |
| `stack[8]` | | script call stack, 8 deep, no overflow check |
| `wregs[64]` (mod, patch 0014) | 128 | u16 wide registers w0..w63, appended (earlier offsets unchanged) |

The save copies the first 0x17C bytes: 212 + 33 + 100 + the first **35 pstats**.

- **Triggers** are addressed with a u16 everywhere (`SET`/`UNSET_TRIGGER`, `IF`, `COMPARE_DATE`, `SPAWN_CHEST`,
  `isTriggerSet`) but have **no bounds check**: trigger 800 is pstat 0, trigger 2848 the call stack. Ranges used as
  per-id bitsets:

  | Range | Meaning |
  |---|---|
  | 200 + species | recruited (species < 0x70) |
  | 0x180 + item | shop stock |
  | 0x200 + species | raised (species < 63) |
  | 650–716 | chests |

  The ranges are packed back to back: item 128 would land on "raised" and species 112 on shop stock. Species beyond
  these ranges use the bitsets described under Species. Original usage and compiler reservations are described in
  [usage diagnostics and reservations](../mods/scripts.md#free-triggers-and-pstats).
- **Pstats** are u8 values with a u8 index and stay so: widening them would change every `SET_PSTAT`/`IF pN` and the
  saved bytes. Wide ids go through the **wide registers** instead: w0–w15 are saved (save tag `WREGS`; w15 is the Sukamon backup), w16–w63 are
  scratch, zeroed at boot. `CALL_ROUTINE 0` (choose an item) also leaves the item in w62 (0xFFFF = none) next to p254.

## Script ids

Every original opcode keeps its bytes and meaning; the 16-bit variants live in 0x80–0x9F, which the original
interpreter treats as end of script (so a script that uses them needs the mod executable). Each u16 field sits at an
even offset.

| Op | Name | Carries | 8-bit original |
|---|---|---|---|
| 80 / 81 / 82 | LOAD_DIGIMON16 / SET_DIGIMON16 / UNLOAD_DIGIMON16 | species | 46 / 47 / 79 |
| 83 | WARP_TO16 | screen | 4B |
| 84 / 85 | GIVE_ITEM16 / REMOVE_ITEM16 | item | 28 / 29 |
| 86 / 87 | SPAWN_ITEM16 / SPAWN_CHEST16 | item | 74 / 75 |
| 88 | LEARN_MOVE16 | technique | 2D |
| 89 / 8A | GIVE_CARD16 / TAKE_CARD16 | card | 2F / 30 |
| 8B | SET_BGM16 (0xFFFF stops the music) | music font | 5D |
| 8C | SET_WREG | wide register | — |
| 8D / 8E | STORE_DIGIMON_TYPE_W / STORE_MAP_ID_W | species / screen into wN | 22 / 21 |
| 8F | TELEPORT_W (screen in wN, exit in wN+1) | screen | 58 |
| 90–93 | COPY_W (4 bytes), ADD_W (saturates), SUB_W (stops at 0), SWITCH_W | wide registers | 7A, 1F, 20, 18 |
| 94–9F | reserved (end the script) | | |

IF conditions: the original handles `condOp & 0x38` groups 0x00 (trigger), 0x08 (pstat), 0x10/0x18 and 0x20 with low
bits 0–5; the rest fall through. The mod uses 0x26 `item16`, 0x27 `wreg`, 0x28 `move16`, 0x29 `card16`;
0x2A–0x2F and the whole 0x30 and 0x38 groups stay free. The assembler (`tools/dws/bytecode/__init__.py`) picks a wide form only when
an id is above 255, so original instructions that carry 0xFF round-trip. Operand layouts and examples:
[../mods/scripts.md](../mods/scripts.md) ("Wide opcodes"); the compiler that emits them: [compiler.md](compiler.md).

A pstat can never hold a species past 255. Patch 0306 makes `STORE_DIGIMON_TYPE` store a partner past 254 as 0xFF, so a
narrow test cannot match another species by its low byte, and `STORE_DIGIMON_VALUE` and `{digimon N}` turn that 0xFF back
into the partner. Engine code uses `storePartnerSpecies` and `pstatSpecies`, never `writePStat` and `readPStat`, for a
species (`tools/test_partner_species.py`). The Sukamon backup (p5) also keeps the species in saved register w15; a save
from before 0306 has w15 = 0 and falls back to the pstat. The exception is p4, the tournament registration, which
`tournament.c` compares with the partner's low byte.

Not widened: the text escapes `{move N}`, `{item N}`, `{bgm N}`, `{cup N}`, which read a u8 pstat. Control codes 0x1D–0x1F appear in no original text (they fall into the
glyph branch of `showTextbox`).

Other script-level ids:
- **DG.SCN** script ids are u16; there are 222 entries and the offset table is one sector (room for 511). A script
  must fit `MAP_SCRIPT_BUFFER` (0x4000, no check in `getScript`). DG.SCN is read through `CdSearchFile`.
- **Entity/speaker ids** are u8 per-screen handles, not species: 0xFD = tamer, 0xFC = partner, 0xC8–0xD6 special in
  `WAIT_FOR_ENTITY`; NPC script ids and battle enemies (p251–p253) are handles too, so u8 suffices.

## Music and sound

| What | Width | Limit |
|---|---|---|
| `5D SET_BGM font` | u8 | `playMusic` accepts fonts 1..0x21; `FAALL.VHB` is 33 fonts × 39 sectors read at `(font − 1)·0x27`: full |
| Jukebox pairs and `BGM_TRACK_NAMES[63]` | — | loops to 0x3F |
| `MAP_SOUND_PARA[22]` | `{u16 sector, u16 count}` | by `MAP_ENTRIES.flags & 0x1F` |
| `5A PLAY_SOUND bank, sound` | u8, u8 | 10 fixed SPU banks (`VHB_SOUNDBUFFER_START[10]`) |
| Per-screen music | — | each MAPHEAD section stores a pstat and sets a font |
| Species battle music | — | `DIGI.DAT` record byte 0x52 (`getSpeciesBattleMusic`, patch 0081) |

The real limits are the fixed `FAALL` stride and SPU RAM, not the id width ([memory.md](memory.md)).

## Files

- **`FILE_OFFSET_TABLE`** (`file_table_us.c`, 0x8011FE1C in the original: 819 entries
  `{i32 sector, i32 size, char *name}`) ends exactly where `SIN_LOOKUP_TABLE` starts. `lookupFileTable` strips the
  directory and runs a linear name comparison until an entry of size 0: nothing indexes the table by number, so a file
  is found by its name only. In the GCC build the table grows by adding entries.
- **New names** (patch 0147): `NEW_FILES` in the decompilation's Makefile (a list of 8.3 upper-case names given by
  `tools/build-full.sh` from the content) becomes one entry each after the mod's own entries (generated
  `file_table_new.h`, sector 0 and size 0x800 until `build-disc.py --relayout` writes the real values). The original
  names resolve as before; with an empty list the executable is byte-identical. `tools/newfiles.py plan` sorts the
  files a build puts on the disc into replacements, additions and names the table lacks. A second table on the disc
  would cost no RAM but would read the CD inside `lookupFileTable`, which the file queue and the background stream call
  while their own reads may be in flight.
- **Names in the entry** (patch 0210): a `FileEntry` holds `char filename[12]` (`FILE_NAME_MAX`; no NUL at 12 letters,
  compare with `fileEntryIs`) instead of a pointer to a string: 20 bytes per entry instead of 12 plus an aligned
  string.
- **Language copies** (patch 0209): a `LANG_FILES` row is the name's 32-bit FNV-1a hash and the places of its
  Spanish copy and its copy with English signs among the new files (`u16 copy[2]`, offsets from
  `FILE_TABLE_NEW_FIRST`, 0xFFFF = none): 8 bytes per row. The build (`tools/derive`, the plan step) writes the rows and stops the
  build if two names of the disc share a hash. How the copies are chosen at run time:
  [../mods/language.md](../mods/language.md).
- **Archives instead of entries**: `DIGI.DAT` (all new species with their models and textures) and `SCRN.DAT` (all
  screens from 255) are one table entry each, so species and screen counts do not grow the table; only files with new
  names (a new screen's `.MAP`/`.TFS`, extra models, language copies) do. How the derived files are produced:
  [../derive.md](../derive.md); disc layout: [disc.md](disc.md).

## Ids in the save

The v1 layout (one block, a 0x200 header and two 0xF00 payloads) has u8 fields for screens, inventory items, VS
registrations and poop screens. The mod keeps those bytes (low byte of the id, or 0xFF for "none") so the original
executable can still read a save without new content, and stores the full ids in an extension of tagged records:

| Tag | Name | Contents |
|---|---|---|
| 0x0001 | `SCREENS` | i16 current, i16 previous screen (authoritative) |
| 0x0002 | `INVENTORY` | i16 item id per slot, −1 = empty |
| 0x0003 | `PARTNER_TYPE` | i32 species |
| 0x0004 | `WREGS` | u16 w0.. |
| 0x0005 | `REGISTERED` | i16 species of the VS registrations |
| 0x0006 | `POOP_MAPS` | i16 screen per poop pile, −1 = none (authoritative since 0146) |
| 0x0007 / 0x0008 | `SPECIES_RAISED` / `SPECIES_RECRUITED` | bit arrays, one bit per species |

A save holding anything the original executable cannot name (partner ≥ 180, item ≥ 128, a screen ≥ 255;
`needsNewExecutable`) stores its v1 checksum inverted, so the original refuses it with "Data Error" instead of loading
a partner it cannot draw. Block layout, versions, tag rules and the later tags: [save-format.md](save-format.md).

## Resident cost per id

What each id costs in the original executable's resident data (the reason new species and screens live on the disc):

| Kind | Per id | Original total | Detail |
|---|---|---|---|
| Species | ≈ 89 B | 180 → 16 KB | `DIGIMON_DATA` 52, name pointer + `char[8]` 12, skeleton pointer 4, voice 1, original type 2, shared bones ≈ 18 |
| + partner | ≈ +100 B | 66 → 6.6 KB | raise 28, evolution requirements 28, gains 14, paths 11, chart 8, card 4, TRN 4, others 3 |
| Screen | ≈ 113 B | 255 → 28 KB | `MAP_ENTRIES` 16 + MAPHEAD ≈ 97 (doors, toilets, captions shared) |
| Item | ≈ 67 B | 128 → 8.5 KB | `ITEM_PARA` 32, description ≈ 30, function 4, CLUT 1 |
| Technique | ≈ 35 B | 122 → 4.2 KB | `MOVE_DATA` 16, name ≈ 19; +4 for the 58 learnable |
| File entry | 20 B in the mod (0210) | 819 → ≈ 18 KB originally | 12 + name string originally |

With the mod: a species ≥ 180 or a screen ≥ 255 costs 0 resident bytes (records on the disc, read through the caches
above); the fixed costs are the species cache (8 KB), the partner list (2 KB), the two flag bitsets (256 B) and the
screen cache (≈ 2.7 KB). A new file name costs one table entry.

How often each kind of data is read decides what may live on the disc:

| Data | How often |
|---|---|
| `radius`, `height`, `boneCount` | every frame, for loaded entities (collision, camera, shadow) |
| `level`, `type`, `special` | per battle or menu, sometimes per frame in battle |
| `moves`, `dropItem` | per battle or event |
| name | per text box or menu (menus may list many) |
| skeleton, file name, voice | at model load |
| raise and evolution data | per partner tick, or once a day |
| `MAP_ENTRIES` row, MAPHEAD section | once per screen change |

## Buffers sized for the largest original asset

These bound what a single new species, screen or script may weigh rather than how many there are (sizes in the
mod's executable; the memory map is in [memory.md](memory.md)):

| Buffer | Original | Mod | Largest original |
|---|---|---|---|
| Partner model (`PARTNER_MODEL_BUFFER`) | 0x18800 | `PARTNER_MMD_MAX`, 0x20000 by default, sized to the disc by the build (patch 0064); the loaders refuse a larger model | ETEM.MMD 0x17E14 |
| Tamer model | 0xE000 (two arrays) | one array (patch 0002) | BOYS.MMD 0xDECC |
| `MAPHEAD_SCRIPT_BUFFER` | 0x61A8 | 0x6800 (patch 0004), 0x8000 (patch 0091) | 0x606E |
| `MAP_SCRIPT_BUFFER` | 0x4000, unchecked | — | 0x3800 |
| `SCRIPT_OFFSET_TABLE` | 0x2000 | — | 222 entries |
| `SEQ_BUFFER` | 0x5800, unchecked copy | — | 0x55F8 |
| `MAP_COLLISION_DATA` | 100 × 100 | — | 100 × 100 |
| `TEXTURE_BUFFER` card image | 0x7800, 14-sector stride | — | 0x7000 |
| New screen's MAPHEAD section | — | 1920 bytes in its `SCRN.DAT` record | 718 (largest original screen section) |

## Unknowns

- What `RegisteredDigimon.unk20[32]` and `moves[3]` hold.
- Whether the item-icon VRAM rows 128–255 at x = 320 are free on every screen.
- How card ids 0 and 65 are obtained in play.

For testing new ids in an emulator (warps, forced evolution, save round trips) see [../developing.md](../developing.md).
