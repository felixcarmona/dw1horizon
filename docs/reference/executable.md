# The executable, overlays and data tables

The USA main executable `SLUS_010.32`, the 16 code overlays (`*_REL.BIN`), the memory map they share, the data
tables the executable carries and how all of it relates to the decompilation and to our build. Field-level layouts of
the disc's data files are in [file-formats.md](file-formats.md); the disc layout in [disc.md](disc.md); run-time
RAM state in [ram-map.md](ram-map.md).

## Three address spaces

Do not mix them up:

1. **RAM** `0x80xxxxxx`: what `decomp/config/us/symbols*.txt`, cheat tables and debuggers use. Every address in
   these docs is a RAM address unless it says otherwise.
2. **Offset in `SLUS_010.32`** = RAM − `0x80090000` (the 0x800-byte PS-X EXE header included). The bss (from
   `0x80134C4C`) is not in the file.
3. **Raw offset in the `.bin` image** (2352-byte sectors with sync/EDC/ECC). Some older community hacks patch the
   image at such offsets; they are only valid for the untouched redump layout and break as soon as a file moves.

## `SLUS_010.32` (PS-X EXE)

| Header field | Value |
|---|---|
| `pc0` (entry) | `0x800A4240` (`__start`) |
| text | `0x80090800`, size `0xA4800` → ends at `0x80135000` (the whole file is code + initialised data) |
| bss | `0x80134C4C`, size `0x8B000` → up to `0x801BFC4C` (the linker's `_end` is `0x801BFB64`; the header rounds up) |
| stack | `0x801FFFF0` in `SYSTEM.CNF`; `__start` sets `sp = 0x801FFF00` |
| `gp` | 0 in the header; the startup code sets `$gp = 0x8013BB2C` |
| file size | 675 840 bytes |

File offset ↔ RAM: `ram = offset − 0x800 + 0x80090800`.

| RAM | Contents |
|---|---|
| `0x80090800 – 0x80113A60` | code (~1 750 functions counting the libraries) |
| `0x80113A60 – 0x80115200` | read-only data of the Psy-Q libraries (version strings of `intr.c`, `sys.c`, `bios.c`, libgpu/libcd/libspu/libsnd/libmcrd messages) |
| `0x80115200 – 0x80135000` | game data: the tables below, strings, pointer tables, the font |
| `0x80134C4C – 0x801BFC4C` | bss: run-time globals (partner state, inventory, script state, buffers) |

The game code is compiled with **Metrowerks CodeWarrior for PlayStation, Release 4** (hence the overlays' `MWo1`
magic); the libraries are the 1997 Psy-Q ones. The executable holds about 2 300 ASCII strings: Digimon, item,
technique, map and file names, item descriptions, library debug messages. Dialogue is not here: it is in
`SCN/DG.SCN` ([file-formats.md](file-formats.md#scn-scripts)).

Startup (`decomp/src/main/_psstart.c`, `main.c`) is described in [engine.md](engine.md#startup).

## Overlays (`*_REL.BIN`)

Each overlay is read whole, by `loadDynamicLibrary` (`decomp/src/main/utils2.c`), to the fixed address in
`REL_BIN_OFFSETS[]`. Overlays that share an address are mutually exclusive.

### `MWo1` header

```
0x00  "MWo1"            magic (Metrowerks overlay, version 1)
0x04  u32 id            1..15
0x08  u32 load_addr     address of this header in RAM
0x0C  u32 size_text     first section (code + data)
0x10  u32 size_data     second section
0x14  12 bytes of 0
0x20  char name[16]     e.g. "EVL_REL.BIN"
0x30  16 bytes of 0
0x40  code ...          file size = 0x40 + size_text + size_data + 4
```

The header is not consulted at run time; the executable's `_overlay_section_addresses` table stores the address of
each header. The second sections carry fragments of the compiler's DWARF 1 debug information (variable names, source
file names) without complete compilation units; the decompilation's symbol files already name everything.

### The 16 overlays

| Overlay | id | `MWo1` at | text | data | Functions | What it is (`decomp/src/<ovl>/`) |
|---|---|---|---|---|---|---|
| `BTL_REL.BIN` | 1 | `0x80056C68` | 0x1C0B8 | 0x3218 | 195 | wild battles ([combat.md](combat.md)) |
| `STD_REL.BIN` | 2 | `0x80056C68` | 0x22C44 | 0x65D8 | 270 | arena / tournament battles ([combat.md](combat.md#tournaments-arena)) |
| `FISH_REL.BIN` | 3 | `0x80070000` | 0xA120 | 0x3808 | 182 | fishing ([minigames.md](minigames.md#fishing-fish)) |
| `EVL_REL.BIN` | 4 | `0x80060000` | 0x3EA8 | 0x511C | 59 | the digivolution sequence |
| `KAR_REL.BIN` | 5 | `0x80053800` | 0x72D0 | 0x8ED8 | 69 | curling ([minigames.md](minigames.md#curling-kar)) |
| `VS_REL.BIN` | 6 | `0x80056C68` | 0x18D14 | 0x38A8 | 175 | two-player versus mode ([minigames.md](minigames.md#vs-mode-vs)) |
| `MOV_REL.BIN` | 7 | `0x80010000` | 0x90C | 0x72AD8 | 14 | STR movie player ([engine.md](engine.md#video-mov_rel)) |
| `DOO2_REL.BIN` | 8 | `0x80070000` | 0x1A40 | 0x9C68 | 6 | helpers of the death cutscene (fragments, CLUT, wireframe) and the egg choice box |
| `DOOA_REL.BIN` | 9 | `0x80080000` | 0x4894 | 0x2FD4 | 39 | partner death and reincarnation cutscene |
| `TRN_REL.BIN` | 10 | `0x80088800` | 0x6718 | 0x478 | 69 | training: Green Gym, Gear Savanna, Misty Trees ([minigames.md](minigames.md#training-trn-and-trn2)) |
| `DGET_REL.BIN` | 11 | `0x80080800` | 0x148C | 0x28 | 20 | tournament calendar and registration screen |
| `SHOP_REL.BIN` | 11 | `0x80080800` | 0x7820 | 0x5AC | 105 | shop routines; in the USA build the same code is linked into `SLUS` (see below) |
| `TRN2_REL.BIN` | 12 | `0x80088800` | 0x50F0 | 0x38C | 61 | training: Beetle Land, Ice Sanctuary, Trash Mountain |
| `MURD_REL.BIN` | 13 | `0x8007C000` | 0x1708 | 0x1214 | 19 | partner death effect (loads `ETCHI\LIFE.TIM`) |
| `ENDI_REL.BIN` | 14 | `0x80060000` | 0xD58 | 0x798 | 22 | the tamer dissolving in the ending |
| `EAB_REL.BIN` | 15 | `0x80060000` | 0x169C | 0x974 | 36 | Machinedramon's appearance effect (no strings) |

**`BTL`, `STD` and `VS` are not plain `MWo1` files.** They start with a 4 bpp TIM (0xD20 bytes, CLUT at (192,500))
followed by a 5-object TMD (at 0xD20); the `MWo1` header is at file offset `0x4188`. The whole file is read at
**`0x80052AE0`**, so the header lands at `0x80056C68` and the code starts at `0x80056CA8`. The leading data is the
finisher aura, confusion, stun and buff models ([combat.md](combat.md#source-files)).

**`SHOP_REL.BIN`**: in the USA executable the shop code (`decomp/src/shop/script_menu.c`) is linked into `SLUS`
itself (`config/us/main.yaml`); `checkShopMap` still loads the file on the 8 maps of `SHOP_MAPS`
([items-and-menus.md](items-and-menus.md)). In the JP and EU builds it is a real overlay.

How each overlay gets loaded: `BTL` by `loadBattleData`, `STD` by `startTournament`, `VS` by the main menu,
`FISH`/`KAR` on entering their maps, `TRN`/`TRN2` by `loadTrainingLibrary` on the gym maps, `EAB`/`ENDI` by script
commands `0x33`/`0x34`, `MOV` by `startMovie`, `DGET` on the arena lobby maps. Details per overlay in the linked docs.

## Memory map (2 MB)

```
0x80000000  BIOS kernel
0x80010000  GENERAL_BUFFER: map, VHB, EFE in combat ┐ low RAM: loaded data and overlays
            MOV_REL (up to 0x80083408)               │
0x80052AE0  BTL_REL / STD_REL / VS_REL (whole file)  │
0x80053800  KAR_REL                                  │
0x80060000  EVL_REL / ENDI_REL / EAB_REL             │
0x80070000  DOO2_REL / FISH_REL                      │
0x8007C000  MURD_REL                                 │
0x80080000  DOOA_REL   0x80080800 DGET/SHOP_REL      │
0x80088800  TRN_REL / TRN2_REL (also TEXTURE_BUFFER) ┘
0x80090000  PS-X EXE header (0x800)
0x80090800  SLUS_010.32 code ........ 0x80113A60
0x80113A60  rodata + data .......... 0x80135000
0x80134C4C  bss .................... 0x801BFC4C
0x801BFB70  malloc3 heap ........... 0x801EFF00   (~193 KB: NPC models, temporary buffers)
0x801EFF00  stack .................. 0x801FFF00   (64 KB)
```

How each region is used at run time (heap budget, buffers, what overwrites what) is in [memory.md](memory.md) and
[engine.md](engine.md#file-loading).

## Data tables

Everything below is in `SLUS_010.32`; `offset = RAM − 0x80090000`. Names are those of
`decomp/config/us/symbols.txt`, structs those of `decomp/include/dw/`. `tools/dwtables.py` dumps the main ones to
CSV; [../mods/data-sources.md](../mods/data-sources.md) says which JSON in `content/` is the source of each table in
our build, and [../mods/balance.md](../mods/balance.md) covers the balance tables.

| Symbol | RAM | Offset | Size | Contents |
|---|---|---|---|---|
| `FILE_OFFSET_TABLE` | `0x8011FE1C` | `0x8FE1C` | 819 × 12 | `{i32 sector, i32 size, char *name}`; the name strings start at `0x8011D490` ([disc.md](disc.md#the-file-table)) |
| `DIGIMON_SKELETONS` | `0x8011CE60` | `0x8CE60` | 180 pointers | per type, `{s8 objIndex, s8 parentIndex}` per bone ([../mods/models.md](../mods/models.md)) |
| `RAISE_DATA` | `0x801225BC` | `0x925BC` | 66 × 0x1C | `RaiseData` per playable Digimon: `hungerTimes[8]`, `energyCap/Threshold/Usage`, `poopTimer`, `poopSize`, `favoriteFood`, `sleepCycle`, `favoredRegion`, `trainingType`, `defaultWeight`, `viewX/Y/Z` ([partner.md](partner.md)) |
| `INITIAL_INVENTORY_AMOUNTS` / `_TYPES` | `0x80125F24` / `0x80125F44` | | 30 u8 each | test kit loaded at boot ([items-and-menus.md](items-and-menus.md)) |
| `TYPE_FACTORS` | `0x80125F70` | `0x95F70` | 7 × 7 u8 | element effectiveness ×0.1 ([combat.md](combat.md#techniques)) |
| `MOVE_LEARN_CHANCES` | `0x80125FA4` | `0x95FA4` | 58 × 3 u8 | chance of learning each technique, per specialty slot |
| `MOVE_NAMES` | `0x80126054` | `0x96054` | 121 pointers | technique names (strings from `0x80124C88`, aligned to 4) |
| `MOVE_DATA` | `0x8012623C` | `0x9623C` | 122 × 16 | `Move`: range, power, MP, accuracy, element, status ([combat.md](combat.md#techniques)) |
| `ITEM_PARA` | `0x801269DC` | `0x969DC` | 128 × 32 | `Item` (below) |
| `ITEM_DESC_PTR` | `0x801279DC` | `0x979DC` | 128 pointers | item description strings |
| `ITEM_CLUT_DATA` | `0x80127BDC` | | 128 u8 | palette of each item sprite |
| `EVOLUTION_ITEM_TARGET` | `0x80127C5C` | `0x97C5C` | 44 u8 | target species of evolution items 71–114 |
| `ITEM_FUNCTIONS` | `0x80127C88` | | 128 pointers | effect handler per item |
| `VHB_SOUNDBUFFER_START` | `0x80127ED4` | | u32[10] | SPU address per sound bank ([engine.md](engine.md#sound)) |
| `DIGIMON_VLALL_SOUND_ID` / `DIGIMON_VBALL_SOUND_ID` | `0x80127EFC` / `0x80127F40` | | u8 per type | each Digimon's voice chunk in `VLALL.VHB` / `VBALL.VHB` |
| `MAP_SOUND_PARA` | `0x80127FF4` | | 22 × 4 | `{sectorId, sectorCount}` (half-sectors) of each `ESALL.VHB` region |
| `MAP_NAME_PTR` | `0x801291BC` | `0x991BC` | 70 pointers | area names; strings from `0x80128A34`, 24 characters centred + 4 zero bytes |
| `MAP_PATH_PREFIX` | `0x801291A4` | | | path prefix of map files |
| `MAP_ENTRIES` | `0x801292D4` | `0x992D4` | 255 × 16 | `MapEntry` per screen ([world.md](world.md), [../mods/maps.md](../mods/maps.md); `../data/map_files.csv`) |
| `ITEM_SORT_ORDER` | `0x8012A9C4` | | 3 × 6 u8 | category order of the three inventory sorts |
| `EVOLUTION_REQS` | `0x8012ABEC` | `0x9ABEC` | 0x6E4 | evolution requirements ([partner.md](partner.md)) |
| `EVOLUTION_STATS_GAINS` | `0x8012B2D0` | `0x9B2D0` | 0x39C | stat gains on evolving |
| `EVOLUTION_PATHS` | `0x8012B66C` | `0x9B66C` | 0x2AA s8 | pre-evolutions and evolutions per species (`FF` = empty) |
| `ENEMY_MUSIC_MAPPING` | `0x8012BAE4` | | u8[48] | battle music variant per enemy type |
| `FLEE_CHANCES` | `0x8012BB14` | | 3 × 3 | in fact the chance that an extra enemy *joins* a battle ([combat.md](combat.md#start-of-a-wild-battle)) |
| `CONCAVE_SCREENS` | `0x8012BB20` | | | screens where joining needs line of sight |
| `DIGIMON_DATA` | `0x8012CEB4` | `0x9CEB4` | 180 × 52 | `DigimonPara` (below) |
| `ENTITY_TABLE` | `0x8012F344` | | 10 pointers | tamer, partner, 8 NPC entities |
| `SHOP_MAPS`, `RECYCLABLE_ITEMS`, `CARD_PRICES`, `CARD_DATA` | `0x8012FE68`, `0x8012FE78`, `0x8012FFC4`, `0x8012FFD8` | | | shops and cards ([items-and-menus.md](items-and-menus.md)) |
| `TOURNAMENT_NAMES`, `TOURNAMENT_GRADES`, `TOURNAMENT_SCHEDULE` | `0x801300E0`, `0x8013013C`, `0x80130198` | | | tournaments; schedule 30 days × 6 cups |
| `BIRDRA_TRANSPORT_TARGETS`, `MAIN_D_801303B8`, `MOJYAMON_ITEMS_GIVE/GET` | `0x8013024C`, `0x801303B8`, `0x80130438/44` | | | Birdramon, jukebox track list, Mojyamon trades |
| `STATS_LIMIT_ARRAY` | `0x80130318` | `0xA0318` | | stat caps |
| `FONT_CLUT` | `0x80130FE8` | | | font palette ([../mods/font.md](../mods/font.md)) |
| `DEFAULT_INVENTORY_AMOUNTS` / `_TYPES` | `0x801315F8` / `0x80131618` | | 30 u8 each | new-game kit |
| `HEALING_VALUES` | `0x8013435C` | | 4 i16 | 500, 1500, 5000, 9999 |
| `STAT_GAIN_ENEMY_FACTORS`, `ARENA_MAPS`, `BRAIN_TO_COMMAND_MAP`, `TARGET_ATTACKER_CHANCE` | `0x801344D0`, `0x801345BC`, `0x801346E0`, `0x801346E8` | | | combat constants ([combat.md](combat.md)) |

The overlays have tables of their own (`STD_OPPONENT_BASE_STATS`, `FISH_BITE_CHANCE`, ...), listed in
`decomp/config/us/symbols_<ovl>.txt`; their addresses are valid only while that overlay is loaded.

### `DIGIMON_DATA`: 180 × 52 bytes (`DigimonPara`)

```
0x00  char name[20]     0 = the player character, 1 Botamon ... (first 66 = playable, NUM_PARTNER_DIGIMON);
                        some entries are unnamed
0x14  i32 boneCount     bones of the skeleton (Agumon 22: 16 TMD objects + 6 joints without mesh)
0x18  i16 radius        collision radius (Agumon 120)
0x1A  i16 height        height (Agumon 250, Greymon 400)
0x1C  u8  type          1 Data, 2 Vaccine, 3 Virus (0 the player)
0x1D  u8  level         1 Fresh, 2 In-Training, 3 Rookie, 4 Champion, 5 Ultimate
0x1E  u8  special[3]    0 Fire, 1 Battle, 2 Air, 3 Nature, 4 Ice, 5 Mech, 6 Filth (FF = none)
0x21  u8  dropItem      item it drops (index into ITEM_PARA)
0x22  u8  dropChance    % (Agumon 50, Greymon 30)
0x23  u8  moves[16]     techniques it can learn (indices into MOVE_DATA; FF = empty)
0x33  u8  padding
```

`special` 3 = Nature and 4 = Ice is confirmed by the data: the ice species (Frigimon, Penguinmon, Whamon) have 4,
and so do their techniques' `special` fields. Our species are JSON in `content/species`
([../mods/species.md](../mods/species.md)); `tools/species.py extract` reads this table.

### `ITEM_PARA`: 128 × 32 bytes (`Item`)

```
0x00  char name[20]
0x14  i32  value          price (sell = value / 2)
0x18  u16  meritValue     price in merit points (0 = not in the merit shop)
0x1A  i16  sortingValue   category: 0 recovery, 1 status, 2 food, 3 disk, 4 chip/evolution, 5 tool/key
0x1C  u8   itemColor      where it can be used: 0 field, 1 battle, 2 both, 0xFF never
0x1D  u8   droppable      1 = can be sold and dropped
0x1E  u16  unk
```

Order: 0–14 recovery and status, 15–21 disks, 22 Auto Pilot, 23–31 chips, 32–37 tools, 38–70 food, 71–114
evolution items, 115–124 key items and odd ones, 125–127 the three unused evolution items (Giga Hand, Noble Mane,
Metalbanana, `value = 0`). Effects per item: [items-and-menus.md](items-and-menus.md#items).

## The decompilation and our build

`decomp/` is the public decompilation [jype0/dw_decomp](https://github.com/jype0/dw_decomp) (MIT), a submodule
pinned to one commit. It matches 100 % of the code of the 17 USA binaries (`SLUS_010.32` + the 16 overlays) and has
configurations for the JP, JP Rev 1 and EU versions. What is useful in it:

- `src/main/*.c` (the executable; `script_interp.c`, `evolution.c`, `item.c`, `partner.c`, `battle_tick.c`,
  `map.c`, `sound.c`, `file.c`, ...) and `src/<overlay>/*.c`.
- `include/dw/*.h`: the structs (`Item`, `RaiseData`, `MapEntry`, `DigimonPara`, `ScriptState`, `Move`,
  `CombatData`) and the script opcodes (`script.h`).
- `config/us/symbols.txt` and `symbols_<ovl>.txt`: names of every function and data symbol.
- `src/main/file_table_us.c`: the 819-entry sector table.
- `text/<binary>/*.yaml`: the binaries' strings per language, turned into headers at build time.

A matching build needs the original CodeWarrior compiler, which is not distributed. Our build compiles the same
sources with **GCC** instead: the result is a different binary (smaller code, other variable addresses) that boots
and plays the same. A handful of patches fix what the original layout hid (buffer sizes, null checks, overruns;
patches 0001–0004, 0022, 0094 in `mods/patches/`). Because addresses move, RAM addresses in these docs are those of
the original USA executable; for a GCC build, look the symbol up in the build's map (`tools/dwsyms.py`,
`tools/xref.py`). Every addition to the executable shrinks the heap above the bss: see [memory.md](memory.md).

How the patch series is applied and built: [../building.md](../building.md#executable-and-hardware),
[../mods/patches/README.md](../../mods/patches/README.md). Our engine patches by area:
[engine-patches.md](engine-patches.md).

### Changing the game without the decompilation

The tables above sit at fixed offsets, so a value can be changed by writing the bytes of `SLUS_010.32` at
`RAM − 0x80090000` and rebuilding the disc: the executable does not change size. Fixed-size strings (20 bytes for
item and Digimon names, 24 for map names) are edited in place; techniques and descriptions go through pointer tables
and can be repointed. Assembly patches on the original binary (armips with hooks in known functions) are how the
older community hacks work. Our build does neither: tables are generated from `content/` JSON at build time
([../derive.md](../derive.md)) and code changes are C patches on the decompilation.

## Related projects

Public work on the game that this project builds on or that is useful alongside it:

| Project | What it is |
|---|---|
| [jype0/dw_decomp](https://github.com/jype0/dw_decomp) | the complete decompilation (MIT); symbols and reverse engineering credited to SydMontague's work |
| [SydMontague/DW1-SydPatches](https://github.com/SydMontague/DW1-SydPatches) | C++ reimplementation injected into the original binary (bug fixes, debug menu) |
| [SydMontague/DW1-CheatEngine-Table](https://github.com/SydMontague/DW1-CheatEngine-Table) | a Cheat Engine table with several thousand named RAM addresses |
| [Operation-Decoded/DW1ModelConverter](https://github.com/Operation-Decoded/DW1ModelConverter) | MMD + ALLTIM to glTF with textures and animations (MIT) |
| [uzuhenry/TFSHandler](https://github.com/uzuhenry/TFSHandler) | TFS ↔ PNG converter (the same author has a script decoder and a font editor; offsets are for the Japanese version) |
| [Vicen04/Dw1DataAndPatches](https://github.com/Vicen04/Dw1DataAndPatches) | a large gameplay hack; its wiki documents the causes of many original bugs |
| [ArsonAssassin/DWAP](https://github.com/ArsonAssassin/DWAP) | Archipelago multiworld integration (emulator RAM) |

Generic PS1 tooling: mkpsxiso/dumpsxiso (disc dump and rebuild), jPSXdec (STR/XA), PSXPrev and tim2view (TIM/TMD),
armips, splat/spimdisasm, PCSX-Redux (debugger) and DuckStation. `maspsx` does not apply: the game is CodeWarrior,
not Psy-Q GCC.
