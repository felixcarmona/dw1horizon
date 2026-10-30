# RAM map

The key RAM addresses of the original US executable at a glance, then the main global state grouped by subsystem, and
how to get the full list of the executable's 3 183 global variables. The meaning of each value is explained in the
subsystem documents linked from each group; state of battles, items, menus and the engine (files, VRAM, sound) is
listed in [combat.md](combat.md), [items-and-menus.md](items-and-menus.md) and [engine.md](engine.md), and the heap
and load areas in [memory.md](memory.md).

All addresses are those of the original executable (`SLUS_010.32`, NTSC-U), taken from the decompilation's
`decomp/config/us/symbols.txt`. A rebuilt executable (the decompilation compiled with GCC, or any mod build) places
variables elsewhere: look them up by name (below). Values are little-endian. File offset = RAM - 0x80090000 for what
lies below 0x80134C4C; above that is bss, which has no bytes in the file.

## At a glance

| What | Value |
|---|---|
| Speed | 20 frames per second (`VSync(3)`); 20 frames = 1 game minute, one game day = 24 real minutes |
| Money | `MONEY` `0x80134EB8` (i32, max 999 999) |
| Hour / minute / day / year | `0x80134EBC` / `0x80134EBE` / `0x80134F04` / `0x80134F02` |
| Current screen | `CURRENT_SCREEN` `0x80134DA8` (u8; 204 = File City at the start) |
| Partner | species at `0x801557A8`, stats at `0x801557E0` (Off, Def, Spd, Brn, techniques, HP/MP); care values in `PARTNER_PARA` `0x80138460` |
| Triggers | 800 bits from `0x801BDFCD` (trigger n = bit n%8 of byte n/8) |
| Pstats | 256 bytes from `0x801BE031`; only 0-34 are saved; pstat 1 = prosperity |
| Player in control | `IS_SCRIPT_PAUSED` `0x80134FF4` = 1, `TAMER_STATE` `0x80134C91` = 0, `GAME_STATE` `0x80134F0A` = 0, `IS_IN_MENU` `0x80134EF0` = 0 |
| Save | memory card block `BASLUS-01032DMR<n>`, two 0xF00-byte payloads with a checksum ([save-format.md](save-format.md)) |

## Core: states, counters, clock, menu ([core.md](core.md))

| Symbol | RAM | Type | Meaning |
|---|---|---|---|
| `MAIN_STATE` | `0x80134EB4` | i8 | 0 new, 1 in progress, 2 finished, 3 quit to title |
| `GAME_STATE` | `0x80134F0A` | i8 | 0 world, 1 battle, 2/3 after/before battle, 4 tournament battle, 5 tournament/VS |
| `MONEY` | `0x80134EB8` | i32 | bits |
| `MERIT` | `0x80134FC4` | i16 | merit points |
| `BATTLES_STARTED` / `BATTLES_FLED` | `0x80134FC8` / `0x80134FCA` | i16 | counters |
| `TOURNAMENTS_WON` / `TOURNAMENT_WINS` / `TOURNAMENTS_LOST` | `0x80134FCC` / `0x80134FCE` / `0x80134FD0` | i16 | counters |
| `PAUSE_STATE` / `PAUSE_BOX_VISIBLE` | `0x80134E79` / `0x80134E78` | i8 | START pause |
| `IS_IN_MENU` | `0x80134EF0` | | 0 in the world |
| `HOUR` / `MINUTE` | `0x80134EBC` / `0x80134EBE` | i16 | game time |
| `DAY` / `YEAR` | `0x80134F04` / `0x80134F02` | i16 / u8 | 0..29 / 0..99 |
| `CURRENT_FRAME` / `LAST_HANDLED_FRAME` | `0x80134F08` / `0x80134F06` | u16 | frame of the day, `HOUR*1200 + MINUTE*20` |
| `SUBFRAME_COUNT` | `0x80134E1C` | u16 | half-speed helper |
| `IS_GAMETIME_RUNNING` | `0x80134E20` | i8 | 0 = clock stopped |
| `CLOCK_OFFSET_X` | `0x80134E1E` | i16 | clock x on screen |
| `PLAYTIME_HOURS` / `_MINUTES` / `_FRAMES` | `0x80134EFE` / `0x80134EFC` / `0x80134F00` | u16 | real time played |
| `CURRENT_TIME_OF_DAY` | `0x80134D9D` | u8 | 0 dusk, 1 night, 2 day |
| `POLLED_INPUT` / `POLLED_INPUT_PREVIOUS` / `CHANGED_INPUT` | `0x80134EE4` / `0x80134EE8` / `0x80134EEC` | i32 | pad 1 |
| `SAVE_FILE` | `0x8013192C` | 0x2000 | memory card block image |
| `SAVE_FILE_NAME` | `0x8013190C` | char[32] | card file name |
| `SAVEGAME_SLOT_INFO[15]` | `0x801BF768` | 15 x 0x44 | slot previews |
| `CURRENT_MENU` / `TARGET_MENU` | `0x8013504C` / `0x80135068` | i32 | title menu state machine |
| `MAIN_MENU_TICKS` / `MAIN_MENU_ACTION` | `0x80135048` / `0x80135034` | i32 | |
| `MEMORY_CARD_ID` / `MEMORY_CARD_SLOT` | `0x80135044` / `0x8013503C` | i32 | -1/-1 = no card |
| `CONNECTED_CARDS` / `NEW_CARDS` / `CHECKED_MEMORY_CARD` | `0x80135030` / `0x80135050` / `0x80135064` | u32 | card polling |
| `MEMORY_CARD_ERROR` / `_OPERATION` / `_RETURN_MENU` / `_USED_BLOCKS` | `0x80135040` / `0x80135058` / `0x8013506C` / `0x80135070` | i32 | |
| `VS_PLAYER_INDEX` / `BATTLE_REGISTRATION_SLOT` | `0x8013505C` / `0x80135060` | i32 | battle mode |
| `SAVED_STATE` | `0x801555D0` | 0x19C | load-time staging of positions, partner, screens, waypoints |
| `DIGIMON_DATA[0].name` | `0x8012CEB4` | char[20] | the player's name |

## Partner and tamer ([partner.md](partner.md))

| Symbol | RAM | Type | Meaning |
|---|---|---|---|
| `PARTNER_ENTITY` | `0x801557A8` | 0x80 | species +0, stats +0x38, learned techniques +0x58, name +0x68, lives +0x7C |
| `PARTNER_ENTITY` stats | `0x801557E0` | | Off/Def/Spd/Brn i16 at +0/+2/+4/+6; equipped techniques `0x801557EC`; HP/MP max `0x801557F0`/`F2`; current `0x801557F4`/`F6` |
| `learnedMoves` | `0x80155800` | 2 x u32 | technique bitset |
| `lives` | `0x80155824` | i8 | |
| `PARTNER_PARA` | `0x80138460` | 0x84 | care values: condition +0, discipline `0x80138488`, happiness `0x8013848A`, tiredness `0x80138482`, weight `0x801384A2`, remaining lifetime `0x801384A8`, age `0x801384AA`, care mistakes `0x801384B2`, battles `0x801384B4`, evoTimer `0x801384B6` |
| `TAMER_ENTITY` | `0x8015576C` | 0x3C | tamer level at `0x801557A4`, raised count at `0x801557A5` |
| `PARTNER_STATE` / `PARTNER_SUB_STATE` | `0x80134C5B` / `0x80134C5C` | i8 | |
| `TAMER_STATE` / `TAMER_SUB_STATE` | `0x80134C91` / `0x80134C92` | i8 | |
| `EVOLUTION_TARGET` / `HAS_USED_EVOITEM` | `0x80134E50` / `0x80134E52` | i16 / u8 | evolution in progress |
| `IS_NATURAL_DEATH` | `0x80134C4C` | i32 | |
| `NANIMON_TRIGGER` | `0x80134C64` | i32 | |
| `ITEM_SCOLD_FLAG` | `0x80134C59` | i8 | |
| `HAS_IMMORTAL_HOUR` / `IMMORTAL_HOUR` | `0x80134CA8` / `0x80134CA4` | i32 / i8 | |
| `CURRENT_POOP_ID` / `POOP_TO_EAT` | `0x80134C58` / `0x80134C68` | u8 | |
| `DEATH_STATS` | `0x801384E4` | 0x20 | stats at death |
| `WORLD_POOP` | `0x80138504` | 100 x 4 | poop piles |
| `RAISE_DATA` | `0x801225BC` | 66 x 0x1C | per-species raising data |
| `SLEEP_PATTERN` | `0x80122CF4` | 8 x 6 | sleep schedules |
| `ITEM_TAKE_DISTANCE` | `0x80122D24` | 66 x i8 | |
| `EVOLUTION_REQS` | `0x8012ABEC` | 63 x 0x1C | |
| `EVOLUTION_STATS_GAINS` | `0x8012B2D0` | 66 x 0xE | |
| `EVOLUTION_PATHS` | `0x8012B66C` | 62 x 11 | |
| `EVOLUTION_ITEM_TARGET` | `0x80127C5C` | 44 x u8 | |
| `MOVE_LEARN_CHANCES` | `0x80125FA4` | 58 x 3 | |
| `STATS_LIMIT_ARRAY` | `0x80130318` | 22 x i16 | script stat caps |
| `REINCARNATE_BABY_TYPE` | `0x80134BAC` | 4 x i16 | eggs |
| `EVO_SEQUENCE_DATA` | `0x80154F90` | 0x34 | |

## Scripts and text ([scripts.md](scripts.md))

| Symbol | RAM | Type | Meaning |
|---|---|---|---|
| `SCRIPT_STATE` | `0x801BDED8` | 0x29C | shop stock +0, cards +0xD4 (`0x801BDFAC`), triggers +0xF5 (`0x801BDFCD`), pstats +0x159 (`0x801BE031`), stack +0x25C (`0x801BE134`) |
| `SCRIPT_STACK_OFFSET` | `0x80134FC6` | u16 | stack index |
| `SCRIPT_POINTER` / `ACTIVE_SCRIPT` | `0x80134FDC` / `0x80134FD8` | u8* | |
| `MAP_SCRIPT_BUFFER` | `0x801B9ED8` | 0x4000 | current DG.SCN entry |
| `MAPHEAD_SCRIPT_BUFFER` | `0x801B1D30` | 0x61A8 | MAPHEAD.SCN |
| `SCRIPT_OFFSET_TABLE` | `0x801B7ED8` | 0x2000 | DG.SCN offsets |
| `CURRENT_SCRIPT_ID` / `ACTIVE_MAP_SCRIPT` | `0x80134FC0` / `0x80134FC2` | u16 | |
| `SCRIPT_SECTION` / `SCRIPT_SECTION_IS_EVENT` | `0x80134FE4` / `0x80134FE0` | u8 / s32 | |
| `ACTIVE_INSTRUCTION` | `0x80134FE8` | u8 | |
| `IS_SCRIPT_PAUSED` | `0x80134FF4` | s32 | 1 = no script running |
| `SCRIPT_PARAM_1` / `SCRIPT_STATE_2` / `SCRIPT_NEXT_STATE_2` | `0x80134FF8` / `0x80134FFA` / `0x80135014` | u16 | routine state |
| `SCRIPT_JMP_BUF` / `SOME_SCRIPT_SYNC_BIT` | `0x801BE7BC` / `0x80134E30` | | |
| `DELAY_FRAMES` / `AUTOCLOSE_FRAMES` | `0x80134FFC` / `0x80135010` | u16 / u8 | |
| `CURRENT_DIALOGUE_OWNER` | `0x80134FE6` | u8 | speaker |
| `TEXTBOX_LINES_BUFFER` | `0x801BE174` | 0x540 | expanded text rows |
| `TEXTBOX_DATA` | `0x801BE80C` | 0x13C | |
| `DIALOGUE_SELECTION` | `0x801BE948` | 0x10 | |
| `SCRIPT_MOVEMENT` | `0x801BE6B4` | 22 x 12 | scripted movements |
| `LOADED_DIGIMON_MODELS` | `0x801BE7EC` | s32[8] | |
| `SHOP_VARIABLE` | `0x8013500C` | s32 | |
| `NAMING_BUFFER` / `NAMING_BOX_FLAG` | `0x801B1D1C` / `0x80134F8E` | | |
| `TALKED_TO_ENTITY` | `0x80134C9C` | s8 | |
| `FONT_CLUT` | `0x80130FE8` | u16[16] | font palette |
| `CHAR_TO_GLYPH_TABLE` / `GLYPH_DATA` | `0x801307E0` / `0x80130880` | | US font ([../mods/font.md](../mods/font.md)) |
| `SPECIAL_SPEAKERS` | `0x8013035C` | char*[6] | |

## World and entities ([world.md](world.md))

| Symbol | RAM | Type | Meaning |
|---|---|---|---|
| `CURRENT_SCREEN` / `PREVIOUS_SCREEN` / `CURRENT_EXIT` / `PREVIOUS_EXIT` | `0x80134DA8`..`0x80134DAB` | u8 | |
| `CURRENT_SCREEN_ID` | `0x80134FFE` | u16 | script copy |
| `TARGET_MAP` | `0x80134DE0` | u8 | pending screen change |
| `SKIP_MAP_FILE_READ` | `0x80134DA0` | | |
| `DEATH_MAP` | `0x801343B0` | | |
| `MAP_WARPS` | `0x80138730` | 0x78 | the 10 exits |
| `MAP_COLLISION_DATA` | `0x801AF398` | 10 000 | collision grid |
| `ENTITY_TABLE` | `0x8012F344` | 10 pointers | 0 player, 1 partner, 2-9 NPCs |
| `NPC_ENTITIES` | `0x80155828` | 8 x 0x68 | |
| `MAP_DIGIMON_TABLE` | `0x8013CB50` | 8 x 0xC4 | placements from the `.MAP` |
| `TAMER_POSITION_DATA` | `0x801A07E8` | | player position `0x801A0860`, heading `0x801A085A` |
| `PARTNER_POSITION_DATA` | `0x801866CC` | | partner position `0x80186744`, heading `0x8018673E` |
| `STORED_TAMER_POS` | `0x80138720` | VECTOR | |
| `TAMER_WAYPOINT_X` / `_Y` | `0x8013D5B0` / `0x8013D590` | 30 + 30 | tamer trail (with the tile and index bytes at `0x80134D50..56`) |
| `MAP_TILE_DATA` | `0x8014F084` | 0x1BBC | background tiles and 2D camera |
| `GS_VIEWPOINT` | `0x80185BA8` | GsRVIEW2 | 3D camera |
| `DRAWING_OFFSET_X/Y` | `0x80134EC0` / `0x80134EC4` | s32 | |
| `CAMERA_FOLLOW_PLAYER` | `0x80134DC8` | | |
| `CHEST_ARRAY` | `0x80150F00` | 8 x 0x38 | |
| `DROPPED_ITEMS` | `0x8013D4E0` | 11 x 0x10 | |
| `MAP_3D_OBJ` | `0x80153240` | 6 x 0x1C | doors, boulder |
| `WORLD_OBJECTS` | `0x80137418` | 129 x 0xC | live objects |
| `INVENTORY` | `0x8013D474` | 0x5B | 30 types, 30 amounts, 30 names, size ([items-and-menus.md](items-and-menus.md)) |
| `BIRDRA_TRANSPORT_TARGETS` | `0x8013024C` | 6 x 8 | |

## Function addresses

The main loop and clock functions are listed in [core.md](core.md#state-in-memory). Any function address is in
`symbols.txt` alongside the data symbols.

## The full list of globals

`decomp/config/us/symbols.txt` is the authority: one line per symbol, `NAME = 0xADDRESS;` with optional `size:` and
`type:` notes. Three tools read it:

- `python3 tools/dev/symbol_docs.py [OUT.md]` generates a reference of the executable's 3 183 data symbols grouped by the C file
  of `decomp/src/` that defines them (1 654 are located), with address, size and type when known; the default output
  is `build/symbols.md`.
- `python3 tools/dev/symbol_addresses.py NAME [NAME ...] [--gcc]` prints the address of a symbol (substrings, case-insensitive);
  with `--gcc` it reads the linker map of the GCC build instead, whose addresses differ.
- `tools/dwsyms.py` is the module the other tools import: `resolve(name, build)` gives the address of a name (or
  `NAME+0x10`) for the original executable or a rebuilt one, and `detect_build` works out which one is running by
  comparing the code in RAM with the original executable.

Reading and writing these addresses in an emulator is covered in [../developing.md](../developing.md).
