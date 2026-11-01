# Scripts: the interpreter, triggers, pstats and text boxes

How the game runs its event bytecode (`DG.SCN` and `MAPHEAD.SCN`): the persistent script state, the 800 triggers and
256 pstats and what the known ones mean, the interpreter loop and call stack, what each opcode does, the `CALL_ROUTINE`
routines, the dialogue box engine and its control codes, and how flags carry the story. This is the engine's side;
compiler-emitted bytecode, containers and the `scnasm` round-trip check are described in [../mods/scripts.md](../mods/scripts.md), and our own story language that compiles to this bytecode
is described in [the Python story guide](../mods/story-language.md) and
[the DWS reference](../mods/dws.md).

Addresses are RAM addresses of the original US executable (`decomp/config/us/symbols.txt`; `tools/dwsyms.py` resolves
names for a rebuilt executable). Line numbers refer to `decomp/src/main/script_interp.c` unless another file is named.
`[inferred]` marks deductions. In the tables "s:sec" means DG.SCN script s, section sec; "MH n" is MAPHEAD section n.

## Summary

Everything outside combat and menus is driven by a bytecode interpreter that runs two files: `MAPHEAD.SCN` (one section
per screen, 0-254, which picks the screen's script and places NPCs, plus text tables 1220-1253 used by the C code) and
`DG.SCN` (222 scripts; entry N is script N, entry 0 is an unused copy of MAPHEAD). The persistent state is
`SCRIPT_STATE` (668 bytes): shop stock, cards, **800 one-bit triggers**, **256 one-byte pstats** and an 8-entry call
stack. Only the first 0x17C bytes are saved, so **only pstats 0-34 persist**. Trigger 200+T means "Digimon of type T
recruited" (or beaten, for an enemy type); prosperity (pstat 1) is recalculated from those triggers. Text is full-width
Shift-JIS with two-byte control codes.

## Source files

| File | Contents |
|---|---|
| `src/main/script_interp.c` | `tickScript`, script loading, the six opcode dispatchers, stack, triggers/pstats, the `CALL_ROUTINE` routines |
| `src/main/script_textbox.c` | dialogue boxes: `showTextbox` (expands text into 64-byte rows), selections, `drawString2` |
| `src/main/script_value.c` | `IF` comparisons (stats, cards, techniques, condition, items, money, date), speaker names, number formatting |
| `src/main/script_common.c` | tables (`BIRDRA_TRANSPORT_TARGETS`, `SHOP_MAPS`...), shops, input, `dailyPStatTrigger`, MAPHEAD text-table access, medals, "raised" |
| `src/shop/script_menu.c` | SHOP overlay: the new-game state machine, shops, Birdra, Mojyamon, naming |
| `src/main/tamer.c:627-680` | `checkMapInteraction`: which section runs when talking to an NPC or stepping on a tile |
| `src/main/font.c`, `sjis.c` | glyphs, CLUT, `drawGlyph`, ASCII → Shift-JIS conversion |
| `src/main/entity_text.c`, `bubble.c` | floating numbers over entities and status bubbles |
| `include/dw/script.h`, `trigger.h`, `pstat.h` | opcodes, `ScriptState`, `StackEntry`, `DialogueSelection`; the ~30 named triggers and pstats |

## State in memory

`ScriptState` offsets come from `script.h:158-164`; `StackEntry` holds a pointer, so the stack is aligned to 4 (0x259 →
0x25C; 0x25C + 64 = 0x29C, the size in symbols.txt).

| Symbol | RAM | Type / size | Meaning |
|---|---|---|---|
| `SCRIPT_STATE` | `0x801BDED8` | 0x29C | script-handled game state; `SCRIPT_STATE_PTR` (`0x80134FB8`) points here |
| `.smth[212]` | `0x801BDED8` | u8[212] | [0..5] today's six recycle-shop offers (`dailyPStatTrigger`); [6..83] stock per recycle index (78 `RECYCLABLE_ITEMS`); [84..211] quantity of each of the 128 items in the Item Keeper (`smth[0x54 + item]`) |
| `.cards[33]` | `0x801BDFAC` | 66 nibbles | quantity (0-9) of each card (`getCardAmount`) |
| `.triggers[100]` | `0x801BDFCD` | 800 bits | trigger N = byte N/8, bit N%8 |
| `.pstats[256]` | `0x801BE031` | u8[256] | pstat N = byte N |
| `.stack[8]` | `0x801BE134` | 8 x {u8 *ptr; u16 script; u8 type; u8 section} | call stack; `SCRIPT_STACK_OFFSET` (`0x80134FC6`, u16) is the index; no overflow check |
| `SCRIPT_POINTER` | `0x80134FDC` | u8* | next byte to execute |
| `ACTIVE_SCRIPT` | `0x80134FD8` | u8* | base of the running script (jumps are relative to it) |
| `MAP_SCRIPT_PTR` → `MAP_SCRIPT_BUFFER` | `0x80134FB4` → `0x801B9ED8` | 0x4000 | RAM copy of the screen's DG.SCN entry (max 8 sectors) |
| `MAPHEAD_SCRIPT_PTR` → `MAPHEAD_SCRIPT_BUFFER` | `0x80134FAC` → `0x801B1D30` | 0x61A8 | all of `MAPHEAD.SCN` (0x8000 in the mod executable, patch 0091) |
| `SCRIPT_OFFSET_PTR` → `SCRIPT_OFFSET_TABLE` | `0x80134FB0` → `0x801B7ED8` | 0x2000 | u32 offset table of DG.SCN |
| `CURRENT_SCRIPT_ID` | `0x80134FC0` | u16 | script of the current screen (set by `FB`) |
| `ACTIVE_MAP_SCRIPT` | `0x80134FC2` | u16 | script held in `MAP_SCRIPT_BUFFER` (the `getScript` cache) |
| `CURRENT_SCREEN_ID` | `0x80134FFE` | u16 | current screen (set by `FB`) |
| `SCRIPT_SECTION` | `0x80134FE4` | u8 | running section (= NPC section when talking) |
| `SCRIPT_SECTION_IS_EVENT` | `0x80134FE0` | s32 | 1 if the section comes from talking or map load, 0 from a tile or from C |
| `ACTIVE_INSTRUCTION` | `0x80134FE8` | u8 | opcode the script is waiting on (0 none, 0xFF closing boxes) |
| `IS_SCRIPT_PAUSED` | `0x80134FF4` | s32 | **1 = no script running**; `gameLoop` only calls `tickScript` when it is 0 |
| `MAIN_D_80134FF0` | `0x80134FF0` | s32 | 1 = the script has stopped the game (`scriptPauseGame`) |
| `MAIN_D_80134FE9` | `0x80134FE9` | u8 | 0x4B while a screen change is in progress |
| `MAIN_D_80134FE7` | `0x80134FE7` | u8 | pstat 0 value to restore when the script ends |
| `SCRIPT_PARAM_1`, `SCRIPT_STATE_2`, `SCRIPT_NEXT_STATE_2` | `0x80134FF8`, `0x80134FFA`, `0x80135014` | u16 | running routine id / routine sub-state; in a warp, target map and exit |
| `SCRIPT_JMP_BUF`, `SOME_SCRIPT_SYNC_BIT` | `0x801BE7BC`, `0x80134E30` | jmp_buf, s32 | interpreter `longjmp` buffer; sync bit with evolution/curling |
| `DELAY_FRAMES`, `AUTOCLOSE_FRAMES` | `0x80134FFC`, `0x80135010` | u16, u8 | counters for `67` and mode 2 of `68` |
| `TEXTBOX_CLOSE_MODE`, `SCRIPT_TEXTBOX_MODE` | `0x80134FE5`, `0x80135008` | u8 | how the box closes (0 button, 1 by itself, 2 after N frames); box mode inside a routine (1 text, 2 selection, 3 background) |
| `CURRENT_DIALOGUE_OWNER` | `0x80134FE6` | u8 | speaker: 0xFD player, 0xFC partner, < 0xC8 NPC, 0xC8+ special, 0xFF none |
| `TEXTBOX_ORIGIN_X/Y/Z` | `0x80134FD2/4/6` | s16 | origin of the box arrow (`55`); -9999 = use the entity |
| `TEXTBOX_LINES_PTR` → `TEXTBOX_LINES_BUFFER` | `0x80134FBC` → `0x801BE174` | 0x540 | 21 rows x 64 bytes of expanded text |
| `TEXTBOX_DATA` | `0x801BE80C` | 0x13C | `usedRows` + 6 x `TextBoxData` (flags, pages, VRAM row, tick/render) |
| `UI_BOX_DATA` | `0x8013D390` | 6 x 0x24 | box frames (state, position) |
| `DIALOGUE_SELECTION` | `0x801BE948` | 0x10 | `pointer` (target table), `endPointer`, `count`, `current`, `cursorOffsetY`, `cursorWidth` |
| `TEXTBOX_OPEN_TIMER` | `0x80135012` | u8 | frames since the last page (animates the continue icon) |
| `SCRIPT_MOVEMENT` | `0x801BE6B4` | 22 x 12 | scripted movements: 0-9 entities, 10 camera, 11 door, 12-21 objects; `type` 0xFF = free |
| `WAIT_FOR_ENTITY_ID` | `0x80134FA4` | u8 | who `4A` waits for |
| `LOADED_DIGIMON_MODELS` | `0x801BE7EC` | s32[8] | models loaded with `46` |
| `SHOP_VARIABLE` | `0x8013500C` | s32 | 16-bit number shops pass to the text; pstats 243:244 |
| `NAMING_BUFFER`, `NAMING_BOX_FLAG` | `0x801B1D1C`, `0x80134F8E` | char[20], u8 | name being edited; bit 0 = the Digimon's, bit 1 = opened from the menu |
| `INPUT_PENDING_MASK`, `INPUT_FRESH_MASK`, `INPUT_REPEAT_MASK`, `INPUT_REPEAT_COUNTER` | `0x80135024`, `0x80135020`, `0x8013501C`, `0x80135016` | u32 | one-shot input for the boxes (`processInput`) |
| `TALKED_TO_ENTITY` | `0x80134C9C` | s8 | entity talked to (2-9), passed to `startBattle` |
| `SPECIAL_SPEAKERS` | `0x8013035C` | char*[6] | Sign, Box, Betamon, Coelamon, Tanemon, Palmon (speakers 0xC8-0xCD) |
| `ENTITY_TEXT_DATA`, `CONDITION_BUBBLES` | `0x80150CD0`, `0x80155560` | | floating numbers and status bubbles |

The counters read by `IF` and the text codes (`MONEY`, `MERIT`, `BATTLES_*`, `TOURNAMENT*`) are in [core.md](core.md).
Confirm is ✕ (`0x40`) and cancel is △ (`0x10`) in the US version.

## Triggers

800 bits in `SCRIPT_STATE.triggers`: `setTrigger`/`unsetTrigger`/`isTriggerSet` compute `byte = 0x801BDFCD + N/8`,
`mask = 1 << (N % 8)`. Scripts write them with `1C`/`1D` and read them in `IF`; `2C` and `75` also write one. All 800
are saved. `trigger.h` names about 30; the rest is deduced from where scripts and code set and read them.

| Index | Name (`trigger.h`) | Meaning | Source |
|---|---|---|---|
| 0 | `TRIGGER_0` | result of `28` GIVE_ITEM: 1 = it did not fit | l. 1033-1038 |
| 1 | | battle with no escape: scripts set it before `66` and clear it after; also skips the camera return to the tamer after the battle; MH 0x4DE clears it | `btl.c:219`, l. 1867 |
| 2 | | battle without the tamer (`IS_TAMERLESS_BATTLE`) | `battle_setup.c:70` |
| 3 | | routine 8/0xE in sell mode (recycling) or selling cards; also set before routine 0 (choose an item), cleared by the routine if something was chosen | l. 355-371 |
| 4 | | card shop: buy instead of opening packs | l. 361-366 |
| 5-13 | | item row already traded with Mojyamon; 14 = all traded | `script_menu.c:1727-1740` |
| 15-36 | `TRIGGER_D_RANK_CUP_WON` ... `HUMAN_CUP_WON` | cup won = 15 + tournament id (15 D, 16 C, 17 B, 18 A, 19 S, 20 R, 21-25 Version 1/2/3/4/0, 26 Fire, 27 Grapple, 28 Thunder Wind, 29 Cool, 30 Nature, 31 Metalic, 32 Filth, 33 Dino, 34 Wing, 35 Animal, 36 Human); medals 364-367 need complete groups | `utils2.c:663`, `tournament.c:174-204` |
| 37 | `TRIGGER_TOURNAMENT_REGISTERED` | registered in a tournament (with pstats 2, 3, 4) | `dget.c:684` |
| 38, 39 | | pending tournament reminders (morning / afternoon) → MH 0x4D9 | `tournament.c:103-116` |
| 40 | `TRIGGER_TOURNAMENT_OVERLEVELED` | level too high for the cup | `dget.c:666` |
| 41 | | set by the partner death sequence (MH 0x4DE); also makes `checkShopMap` skip loading the shop overlay once | MH 1246, `script_common.c:2985` |
| 44 | `TRIGGER_44` | do not turn NPC and tamer towards each other when an event starts: cutscenes set it first; `scriptPauseGame` consumes it | l. 2660-2676 |
| 45, 46 | `TRIGGER_HAVE_OLD_FISHROD/AMAZING_ROD` | fishing rods (status menu icons) | `fish.c:21-25` |
| 47, 48 | | Dimensional Key Chain of 20 / 30 items (menu icons) | `game_menu.c:2600` |
| 49 | `TRIGGER_49` | the current selection cannot be cancelled with △; set by the new game and before mandatory questions | `script_textbox.c:222-237` |
| 50 | `TRIGGER_BEATEN_GAME_ONCE` | game finished once (Arena Lobby NPC, medal 5, complete jukebox) | `tournament.c:224` |
| 51-53 | | one-off File City events (51 Item Keeper 171:81, 52 163:81, 53 216:51) | scripts |
| 54, 55 | | **debug**: 54 enables a hidden test menu in 164:54; 55 shows test NPCs in TWNA01 (MH 204/238; 193:55 clears it). No normal path sets 55 | 164:54, MH 204 |
| 56 | | starter items already given in Jijimon's house (178:6) | 178:6 |
| 58-61, 64 | | restaurant (174/175) | scripts |
| 65-69 | | item shop (176) | 176:81-82 |
| 70-73 | | secret shop (177:5) | |
| 74 | | meat farm already explained (164/207:11) | |
| 75-81, 84 | | File City events (scripts 162, 163, 164, 211) | |
| 86-98 | | 86 Tropical Jungle (15:254); 87/88 File City; 89 Birdra (167:81); 90 Treasure Hunt (169:81); 94 Jijimon's house; 97 Ancient Speedy (81:5); 98 Great Canyon (43/123:52) | |
| 100-135 | | Grey Lord's Mansion / Misty Trees / Volume Villa / Drill Tunnel chain: 104 fridge key (63:5); 105/106 Drill Tunnel earthquake; 111/113/115/117/123/125/127 Mansion Key doors used (51-62); 112 Misty Trees; 114/116/122/319 Volume Villa (135); 118/152/154/228 Mystery Circles; 120 Drill Tunnel 2F; 128/129 graveyard and basement; 130/290 Underground Lab; 133 Freezeland evolution prompt (132:51); 134/135 Leomon's Stone Tablet | |
| 139-155 | | 139 Gear Savanna; 140 Residential Area; 141-143 Great Canyon Top; 144 Ancient Dino; 147 Misty Trees; 149/151 Drill Tunnel Entrance; 150 Secret Beach Cave; 155 Great Canyon Bottom | |
| 158-173 | | only ever cleared (one `1D` each, never read): a reset block | |
| 174-199 | | 174 Misty Trees; 178/179 Treasure Hunt; 180 Great Canyon; 181 Ogre Fortress; 182 Great Canyon Bridge; 188 Ancient Glacial/Speedy; 189/190 Gear Savanna; 191-194 a waiting point (70:5, 51-54); 198/199 Fortress Entrance (40:5) | |
| **200-311** | `TRIGGER_OGRE_FORTRESS_OPENED` (200) ... `TRIGGER_TENTOMON_BEATEN` (311) | **200 + Digimon type**: recruited for playable types (1-66; the recruit event also adds to pstat 1), beaten for enemy types (67-112; the NPC's section sets it after `66`). For example 203 Agumon (48:5/6, Ogre Fortress), 204 Betamon, 209 Meramon, 211 Numemon, 213 Mamemon, 214 Monzaemon, 220 Angemon, 221 Birdramon, 223 Frigimon, 224 Whamon, 225 Vegiemon, 227 MetalMamemon, 231 Patamon, 232 Kunemon, 233 Unimon, 235 Shellmon, 241 Giromon, 246 Palmon, 249 Coelamon, 255 Piximon; 274 Dokunemon, 277 RedVegiemon, 283 ModokiBetamon, 301 Darkrizamon, 311 Tentomon. Some baby slots are reused as flags: 202 and 243 for the fainting sequence (47/63/100:60), 215 Jijimon's house, 229 (189:5) | `main.c:3852` (prosperity), `utils2.c:594-607` (tournament rivals), `dget.c:353-392` (arena requirements), `map.c:5716` (File City layout), `murd.c:769` |
| 312 | `TRIGGER_WARUSEADRAMON_BEATEN` | 200 + 112; upper bound of the count in `dget.c:359` | |
| 313-363 | | area flags: 320 Old Fishrod (159:51); 322-324 Ice Sanctuary; 326 Mt. Infinity; 331/344 Factorial Town; 333-337 the five Dimensional Key Chains (each also adds 1 to pstat 21); 338 Gear Savanna; 339 Seadramon (7:82); 340-342 Sewer; 345 Underground Lab; 346 Beetle Land; 349 Toy Mansion; 350 Toy Town box 0 (`map_object.c:1103`); 351 Freezeland; 354 File City; 356-360 Myotismon's absence (54:254, 63:254, 51:57); 362/363 Trash Mountain (363: the King of Sukamon has reverted the partner once) | |
| 364-382 | | medals: 0x16C + medal (0-18); 364-368 awarded by 204:51; 374 tamer level medal (162:254) | `script_common.c:2941-2951` |
| 384-511 | | item shop stock: 0x180 + item id; `openShop` lists the ones set | `script_common.c:684,1589` |
| 512-574 | | Digimon ever raised: 0x200 + type (`setDigimonRaised` at birth and on evolving) | `script_common.c:2926` |
| 575-626 | | script 221, one per recruited Digimon | |
| 640 | | partner energy >= threshold (`partner_impl.c:1518`); no script reads it | |
| 650-716 | | chests opened: each `75` SPAWN_CHEST carries its trigger; `tamer.c:1510` sets it on pickup and the chest then spawns open; 707-713 are cleared by scripts (Toy Town boxes) | |

Original usage can be inspected with the diagnostic described under
[triggers and pstats](../mods/scripts.md#free-triggers-and-pstats); new mods reserve
state through the story compiler rather than treating original usage as a reservation.
The readable names our tools give to triggers live in
`story/names.toml`.

## Pstats

256 unsigned bytes at `0x801BE031 + N`. `1E`/`1F`/`20` write, add and subtract saturating to 0..255; `18` SWITCH jumps
by value; `IF` compares with `== != >= <= > <`. **Only 0-34 are saved**; the rest are reset at boot
(`initializeScripts`) and survive across screens.

| Index | Name (`pstat.h`) | Meaning / values | Source |
|---|---|---|---|
| 0 | `PSTAT_TIME_SPEED` | clock speed; **3 = clock stopped by a script**: `scriptPauseGame` writes 3 and keeps the old value in `MAIN_D_80134FE7` to restore at the end; a save writes 0 in its place | l. 2654, `main_menu.c:3999` |
| 1 | `PSTAT_PROSPERITY_POINTS` | city prosperity. `recalculateProsperity` (at game start, before every save and on City entry) rewrites it: sum of (level - 2) over types 3-58 (original story) or the IDs in `content/tables/city-residents.json` (extended story: 89 residents, 169 points) with trigger 200+type set (Numemon, Sukamon, Nanimon count 1). Scripts add 1-3 when recruiting and test `>= 10/20/25/30/35/40/50` (>= 50 = the large city, 14 scripts and MH 0x4DD) | `main.c:3845`, `murd.c:769` |
| 2 | `PSTAT_TOURNAMENT_DAY` | day of the registered tournament; bit 7 = do not remind again today `[inferred]` (`dailyPStatTrigger` clears it) | `tournament.c:62` |
| 3 | `PSTAT_TOURNAMENT_ID` | registered cup 0-22 (0xFF none) | `dget.c:463,639` |
| 4 | `PSTAT_TOURNAMENT_DIGIMON` | partner type at registration (a change voids it) | `tournament.c:54` |
| 5 | `PSTAT_SUKAMON_BACKUP_DIGIMON` | type before turning into Sukamon | `partner_impl.c:2100` |
| 6 | | show the area name on `4B`/`58`: 0 automatic (not for event sections), 1 yes, 2 no; resets to 0 | l. 784 |
| 16 | | state of the fainting / Back Dimension sequence (162:254, 185:51, sections 60) | |
| 17 | | Drill Tunnel progress (dirt boxes, 0-4) | 25/26/29/32:254 |
| 18, 19 | | counters for Underground Pond and Jijimon's house | |
| 21 | | Dimensional Key Chains collected (0-5) | |
| 24-27 | | shop states: 24 secret shop, 25/26 item shop, 27 restaurant (0-5) | |
| 28-31 | | daily counters, +1 each day unless 0xFF: 28 days since the fainting event (162:254 needs >= 20); 30 compared with 3/5/10 (Drill Tunnel, Treasure Hunt); 31 farm meat taken today | `script_common.c:1381-1387` |
| 32-36 | | per-NPC dialogue counters used with `SWITCH` | |
| 38, 39, 42-44 | | File City: 43 = layout variant (2-13, MH 180-203); 38/39/42 counters for MH 177-179/192; 44 secret shop. **Not saved** | MAPHEAD |
| 100, 110 | | random: `RANDOM p110 99` decides the ground items in sections 254; p100 in MH 19 | |
| 101 | | cutscene loop counter (0-10) | |
| 103, 109 | | stored Digimon type (`22`) and derived value (`3F`) | |
| 105-108 | | date stored by `25 p105` (year, day, hour, minute) | |
| 111-113, 120-123 | | local to Gear Savanna, Freezeland/Curling, Misty Trees, the arena, the Monochrome Shop | |
| 121, 122 | | curling minigame: 0x79 = result 0/1/2, 0x7A = parameter | `kar.c:759,930` |
| 200 | | damage % for `69 p200`; also the number of items lost on losing a battle | `script_common.c:1307` |
| 241, 242 | | timed field battles in the mod (patch 0172): 242 = the next battle's time limit in seconds, 241 = 1 when it ended by time | |
| 243, 244 | | `SHOP_VARIABLE` high:low (routines 0x1F/0x38); 243 = 0xFF during the new-game scene | `script_common.c:2444-2480` |
| 245 | | music: 0 automatic day/night, 1 day, 2-10 fixed tracks (`handleMusicOverride`); every MAPHEAD section sets it before `5D` | |
| 246 | | training parameter (`trn_*.c`) | |
| 247, 248 | `PSTAT_247/248` | target of `58` TELEPORT and Birdra (map, exit); also entity and mood (0-4) for Monochromon's bubble (routines 0x15, 0x1C) | `script_menu.c:957` |
| 249 | `PSTAT_249` | result of the routine menus (item, card, track; 0xFF nothing); item type in shops | `script_menu.c:609-1593` |
| 250 | | 1 = predefined battle with the enemies in 251-253 | `btl.c:220` |
| 251-253 | | script ids of up to 3 enemies (0xFF empty); `66` converts them to entity ids | l. 1827-1835 |
| 254 | `PSTAT_254` | **generic routine argument**: shop-owner NPC, box, chosen item (0xFF none), training type...; in the new game 0/1 = Agumon/Gabumon | `main.c:3389` |
| 255 | | **result**: of `66` (-1 defeat, 0 fled, other = victory), of a tournament (3 = won, 2 in cup 5); 0 on death or illness | l. 1846, `utils2.c:670` |

## Script format and sections

Each DG.SCN and MAPHEAD.SCN entry starts with `u16 code_offset`, then `(u16 id, u16 offset)` pairs up to `FFFF`, then
the bytecode (`getScriptSection`, l. 595, reads from +2). Jump offsets are relative to the start of the script. The
DG.SCN container begins with a u32 offset table (222 entries plus the file size) read at boot.

| Section | Who calls it |
|---|---|
| 254 | screen initialization, after `FB` (ground items with `RANDOM p110`, chests, visibility) |
| 255 | "none" as the target of `4B` WARP_TO |
| 5-12 | the NPC in slot 0-7 placed by `SET_DIGIMON` (section = 5 + slot; the id comes from the `.MAP` placement, `overworld.c:1016`), when talked to or by autotalk |
| 51-79 | a collision tile: runs when stepped on |
| 80-109 | a collision tile: runs when ✕ is pressed on it |
| 110-119 | exits, handled by C (not scripts); 120 = toilet → MH 0x4E2 |
| MAPHEAD 0-254 | `runMapHeadScript(map)` on load: `FB script map`, `1E p245`, `5D` music, `46`/`47` NPCs |
| MAPHEAD 1220-1253 | text tables and scenes called from C: 0x4C4-0x4CE shopkeeper lines (`getShopkeeperLine`), 0x4D3 cards, 0x4D4 merit, 0x4D5 Item Keeper, 0x4D6 jukebox/Birdra/Mojyamon/Jijimon's questions and naming (entries 0x10-0x39), 0x4D8 tournament, 0x4D9/0x4DA tournament reminders, 0x4DB medal categories, 0x4DC found-item line, 0x4DD Auto Pilot (`item.c:2252`), 0x4DE partner death, 0x4E2 toilet, 0x4E3 Birdra departure, 0x4E4 the Seadramon scene → 7:82, 0x4E5 `58 p247` |

The text tables are lists of `16 00 offset` (JUMP): `resolveMapHeadEntry` (`script_common.c:1160`) reads the u16 at
`section + idx*4 + 2` and skips the `1A 00`. Which screens use which script: MAPHEAD section *screen* starts with
`FB 00 <script> <screen>`; `../data/map_files.csv` has the screen files and `../data/script-map-us-jp.csv` the script
correspondence between versions. Script 5 serves eight screens, 162/163 every File City variant, 180 Mt. Infinity.

## Interpreter loop

`gameLoop` calls `tickScript` (l. 314) every frame while `IS_SCRIPT_PAUSED == 0`. The tick updates boxes and scripted
movements; during a screen change (`MAIN_D_80134FE9 == 0x4B`) it advances it (`scriptTickChangeMap`); it checks
`ACTIVE_INSTRUCTION` (waiting on `67`, `4A`, a routine or a box) and, when nothing is pending, enters a `setjmp` loop
(l. 524) that reads an opcode and dispatches by range (`10`-`27`, `28`-`3F`, `46`-`58`, `5A`-`5F`, `64`-`7E`,
`FB`-`FF`). Each handler ends with `longjmp(1)` = continue with the next instruction **in the same frame**,
`longjmp(2)` = yield to the next frame, or `longjmp(3)` = screen change. An out-of-range opcode sets
`IS_SCRIPT_PAUSED = 1` (end of script). On stopping it closes boxes, restores pstat 0 and, if `scriptPauseGame` had
stopped the game, gives back movement, camera and clock (l. 556-564).

`callScriptSection(script, section, isEvent)` (l. 2163) sets the pointer, state and boxes; `scriptPauseGame` (l. 2646)
stops the clock (pstat 0 = 3), freezes movement and, for an event without trigger 44, turns NPC and tamer to face each
other.

**Stack** (`pushScriptStack` l. 2287, `returnFromScriptFile` l. 2603): type 1 = return from `13`/`14`; type 3 = after
`FB`: when the MAPHEAD section ends, section **254** of the new script runs; type 4 = section to run when the screen
change finishes (`4B`, `58`, `7B`; 0xFF = none: `setMapHeadActive` points at the table's `FFFF`, which decodes as an
`FF` END). An empty stack ends the script. Order in a warp: {4, sec} is pushed, `FB` pushes {3}, END → 254, END → sec.
`returnFromScriptFile` is also where the `.TFS` background is read after a MAPHEAD section (see [world.md](world.md)).

`getScript(id)` (l. 571): 0 = MAPHEAD; if `ACTIVE_MAP_SCRIPT == id` the buffer is reused; otherwise it reads sectors
`table[id]..table[id+1]` of DG.SCN (max 0x4000 bytes).

## What each opcode does

Byte lengths and operand layouts are defined in `tools/dws/bytecode/__init__.py`; see [bytecode inspection](../mods/scripts.md#opcode-reference). Entity ids: 0xFD
player, 0xFC partner, 5-12 NPC slots, 0xC8+ special. Lines refer to `script_interp.c`.

| Op | Name | Behaviour |
|---|---|---|
| `10` | SET_SELECTION | options separated by `0D 00`; ✕ jumps to `target[current]`; △ continues after the closing `12 00` unless trigger 49 is set. Some selections under trigger 49 omit the `12 00`; then the cancel target lands inside the next instruction (`script_textbox.c:972`, patch 0231 fixes the case) |
| `11`, `12` | UNUSED | no-op; `12 00` doubles as the end-of-selection marker |
| `13` / `14` | JUMP_AND_LINK / JUMP_TO_FILE_AND_LINK | push {1} and jump (to another script for `14`) |
| `15` | JUMP_RETURN | pops without checking the entry type |
| `16` / `17` | JUMP_TO / JUMP_TO_FILE | |
| `18` | SWITCH | jumps by pstat value; a value >= n uses the last target |
| `19` | IF | see below (l. 831) |
| `1A` | SHOW_TEXTBOX | yields; another `1A` right after is the next page of the same box |
| `1B` | SET_DIALOG_OWNER | creates the box with its arrow on that entity |
| `1C` / `1D` | SET / UNSET_TRIGGER | |
| `1E` / `1F` / `20` | SET / ADD_TO / REDUCE_PSTAT | saturating 0..255 |
| `21` / `22` | STORE_MAP_ID / STORE_DIGIMON_TYPE | current screen / partner type into a pstat |
| `23` | SET_INVENTORY_SIZE | |
| `24` | STORE_RANDOM | 0..max into a pstat |
| `25` | STORE_DATE | year, day, hour, minute into pstat..pstat+3 |
| `26` | SET_TEXTBOX_SIZE | centred box of cols*12+10 x rows*13+7 px; the next `1A` has no speaker; △ closes it (`tickCustomSizedTextbox`) |
| `27` | FADEOUT_HUD | closes a box; yields |
| `28` / `29` | GIVE / REMOVE_ITEM | `28` sets trigger 0 if the item does not fit |
| `2A` / `2B` | ADD / REDUCE_MONEY | capped at 999 999 |
| `2C` | COMPARE_DATE | trigger = (date in pstat..+3) cmp (a, d, h, m) (`script_value.c:152`) |
| `2D` | LEARN_MOVE | |
| `2E`, `3A`-`3E`, `5B`, `5C`, `5F` | UNUSED | consume their arguments and do nothing |
| `2F` / `30` | GIVE / TAKE_CARD | |
| `31` / `32` / `33` | SET / ADD / REDUCE_MERIT | capped at 9999; in the original **`33` sets `MERIT = -value`**, which then clamps to 0 (patch 0124 makes it subtract) |
| `34` / `35` / `36` | SET / ADD / REDUCE_STAT | `SCRIPT_STAT_*` 0-22 (`getStatsPointer`), caps in `STATS_LIMIT_ARRAY` (see [partner.md](partner.md)) |
| `37` | ADVANCE_TO_DATE_AT | advances the clock to the stored date (`skipHours`) |
| `38` / `39` | ADD / SUB_MINUTES_TO_DATE_AT | on the stored date |
| `3F` | STORE_DIGIMON_VALUE | `DIGIMON_DATA[type].type` |
| `46` / `79` | LOAD / UNLOAD_DIGIMON | NPC models (8 slots). A second `46` inside a talk hangs the game; load models in MAPHEAD |
| `47` | SET_DIGIMON | places the NPC in a slot (see [world.md](world.md)) |
| `48` | UNLOAD_ENTITY | |
| `49` | CALL_DIGIMON_ROUTINE | `callDigimonRoutine` (evolution, death; MH 0x4DE uses 7) |
| `4A` | WAIT_FOR_ENTITY | waits for its movement to finish; 0xFF all; 0xC8 camera; 0xC9/0xD5 sync bit; 0xD6 training load |
| `4B` | WARP_TO | screen change; `sec` runs afterwards (255 = none) |
| `4C`, `4D` | ENTITY_LOOK_AT_ENTITY, ENTITY_SET_ROTATION | |
| `4E` / `52` | ENTITY_WALK_TO[_WITH_CAMERA] | |
| `4F`, `50` | MOVE_CAMERA_TO, MOVE_CAMERA_TO_ENTITY | |
| `51` / `53` | ENTITY_WALK_TO_ENTITY[_WITH_CAMERA] | |
| `54` | RESET_ENTITY_ORIGIN | |
| `55` | SET_TEXTBOX_ORIGIN | arrow origin of the next box |
| `56` | PLAY_ANIMATION | |
| `57` | SET_OBJ_VISIBILITY | |
| `58` | TELEPORT | screen and exit from pstat, pstat+1 |
| `5A` | PLAY_SOUND | bank, sound |
| `5D` / `5E` | SET_BGM / STOP_BGM | `5D FF` stops; pstat 245 modulates |
| `64` | CALL_ROUTINE | see below |
| `65` | REMOVE_CONDITION | clears bits of `PARTNER_PARA.condition` |
| `66` | START_BATTLE | uses pstats 250-253 and trigger 1; result in p255; defeat → MH 0x4DE; fleeing returns to the previous screen (l. 1821-1879) |
| `67` | DELAY | frames |
| `68` | SET_TEXTBOX_MODE | 0 button, 1 advances by itself, 2 after N frames |
| `69` | DEAL_DAMAGE | % (from a pstat) of max HP, never kills; shows a floating number |
| `6A` | SET_AUTOTALK | |
| `6B` | DATA | **the interpreter consumes nothing** (l. 1924): only read through a pointer (`dget.c:377`, `tournament.c:152`), for example the arena's list of required Ultimates in section 11 of its script. A section landing on one would execute the data as opcodes |
| `6C` / `6E` | ENTITY_MOVE_TO[_WITH_CAMERA] | without a walking animation |
| `6D` / `6F` | ENTITY_MOVE_TO_ENTITY[_WITH_CAMERA] | |
| `70` | ROTATE_3D_OBJECT | doors |
| `71` | MOVE_OBJECT_TO | |
| `72` / `73` | ENTITY_MOVE_TO_AXIS[_WITH_CAMERA] | |
| `74` | SPAWN_ITEM | item on the ground |
| `75` | SPAWN_CHEST | carries the chest's trigger |
| `76` / `77` / `78` | SPAWN / MOVE / DESPAWN_BOULDER | |
| `7A` | COPY_PSTAT | |
| `7B` | SECTION_ON_EXIT | pushes {4, sec} for the next screen change |
| `7C` | SET_RECT_IMPASSABLE | blocks collision tiles |
| `7D` / `7E` | SPAWN_SPRITE_AT_LOCATION / _AT_ENTITY | |
| `FB` | SET_SCRIPT | sets `CURRENT_SCRIPT_ID`/`CURRENT_SCREEN_ID`, pushes {3}, calls `loadMap` (l. 2752) |
| `FC`, `FD` | UNUSED | not handled by the `FB`-`FF` switch: the function returns without `longjmp`, so they yield one frame |
| `FE` / `FF` | END_SECTION / END_SCRIPT | `returnFromScriptFile`; files end with `FE 00 FF 00` |

**`IF`** (`scriptIfInstruction`, l. 831): after `19 _` come entries of `cop, _` plus arguments, up to a closing `19 _`.
`cop & 0x38`: `00` trigger (u16; `cop&7` = 0 "is set", otherwise "is not set"); `08` pstat (`u8 pstat, u8 value`,
`cop&7` = `== != >= <= > <`); `10` "if true jump to u16"; `18` "if false jump to u16"; `20` a sub-comparison chosen by
`cop&7`: 0 stat (`u8 stat, u8 cmp, u16`), 1 card (`u8, u8 cmp, u16`), 2 technique (`u8, u8 negate`), 3 condition
(`u8 mask, u8 negate`), 4 item (`u8, u8 cmp, u16 amount`), 5 money (`_, u8 cmp, s32`) (`script_value.c:183-385`).
`cop & 0x80` = AND with the previous result, `0x40` = OR. Example (MH 0x4DD): `IF trig220 || trig214 || p1 >= 50` with
an else jump. `pollNextScriptUShort` reads u16 values with `lhu`, so 16-bit fields must be at even addresses.

**`CALL_ROUTINE` routines** (l. 1582-2017; those that wait are completed in the `switch` of `tickScript`, l. 345-485):
0 choose an item to give or discard (`openDiscardItem`; result in p254, 0xFF none); 1 merit shop; 2 Mojyamon;
6 start a tournament; 7 training (p254: 0 HP, 1 Off, 2 Spd, 3 Def, 4 MP, 5 Brains; TRN2 on screens 0x63/0x6B/0x6C/0xA5);
8 shop (trigger 3 → recycling); 9 jukebox; 0xA Birdra; 0xB Item Keeper; 0xC/0xD remove 1/99 of item p254; 0xE cards;
0xF bits box; 0x10 close box 2; 0x12 tournament calendar; 0x13/0x14 cart and dirt pile; 0x15 reset object animation
(p247, p248); 0x16 check tournament medal; 0x17/0x18 open/close the tray of chest p254; 0x19 store p254 as the speed to
restore; 0x1A/0x1B dirt models; 0x1C Monochromon's mood bubble; 0x1D egg box (DOO2); 0x1E/0x1F/0x38 `SHOP_VARIABLE` = 0
/ += p243:p244 / → p243:p244; 0x20 naming screen (p254: bit 0 Digimon, bit 1 from the menu; without bit 1 = new game);
0x21 register for cup 22 (triggers 37-39, p2-p4); 0x22 Meramon's tremor; 0x23 load SHOP.REL; 0x24 reload the TFS;
0x25 remove the fog; 0x26 Ninjamon effect; 0x27 load TRN.REL; 0x28 `EAB_startBuildup` on entity 5 (the final boss
`[inferred]`); 0x29-0x2C Toy Town; 0x2D/0x2E fade to white; 0x2F `lostAllLives`; 0x30 save machine; 0x31/0x32 Angemon's
pedestal; 0x33/0x34 load the ending (BOSS_EFE, EAB.REL / OP.TIM, ENDI.REL); 0x35 tamer state 0x10 and, on sync,
`MAIN_STATE = 3` (end of game); 0x36 the game-finished save; 0x37 a single animation loop.

## Text box engine

`showTextbox(box, speaker)` (`script_textbox.c:1009`) expands the script text into `TEXTBOX_LINES_BUFFER`, rows of **64
bytes** (up to 31 two-byte characters plus terminator: the real limit of a line). With a speaker, the first row is
`01 c name 01 01 0D 00` with colour `c` = 6 player, 0xA partner, 5 special (0xC8-0xCD), 7 NPC (`getSpeakerName`: 0xFD =
the player's name in `DIGIMON_DATA[0]`, 0xFC = `PARTNER_ENTITY.name`, an NPC = its type's name). The normal box
(`setupDialogueBox`) is 262x59 px at (-130, 42), 4 rows (name + 3), double-buffered, with an arrow towards the speaker.
There are no portraits: the speaker is shown only by the coloured name row and the arrow. Each row is drawn with
`drawString2` into a 256x256 4 bpp VRAM text area at (704,256) and copied 252 px wide; US glyphs are variable width, so
there is no fixed character count per line.

Control codes inside the text (`script_textbox.c:1051-1194` and `drawString2`):

| Bytes | Effect |
|---|---|
| `01 c` | colour `c` (0-15, `FONT_CLUT`): 1 greyish white, 2 blue, 3 red, 4 pink, 5 green, 6 light blue, 7 yellow, 8 black, 9 grey, 10 orange. Scripts use `01 07` for NPC names, `01 06` items and the player, `01 04` key items, `01 01` to return |
| `02 x`, `03 x x x` | copied and skipped by `drawString2` (no visible effect) |
| `04 p` | value of pstat p (3 digits) |
| `05 00` / `06 00` | player / partner name |
| `07 p`, `08 p`, `09 p` | name of the Digimon / technique / item whose id is in pstat p |
| `0A 00`, `0B 00` | bits (6 digits), merit (4) |
| `0C x` / `0E x` | tab to a multiple of 8 / 11 columns (12 px) |
| `0D 00` | line break; **`0D 00 00 00` = end of page**; a following `1A` continues the same box |
| `0F x` | half space (6 px) |
| `10 00` | `SHOP_VARIABLE` (5 digits) |
| `11 p`, `12 p` | music track / tournament name (`BGM_TRACK_NAMES`, `TOURNAMENT_NAMES`) |
| `13` / `14` / `15 00` | tournaments won / wins / lost (3 digits) |
| `16`-`1C x` | (US `drawString2` only) clear and set the x position to 105/105/96/156/180/160/100 px: menu columns |
| `81 40` | space; `81 75`/`81 76` apostrophe and quote; the rest is full-width Shift-JIS (`82 60`+ capitals, `82 81`+ lower case, `82 4F`+ digits) |

The mod's one-byte text (patch 0145) and our text sources are described in [../mods/scripts.md](../mods/scripts.md) and
[text-sources.md](text-sources.md).

**Confirmation** (`tickConfirmDialogue`): mode 0 waits for ✕, 1 turns the page by itself, 2 after `AUTOCLOSE_FRAMES`.
**Selection** (`tickSelectionDialogue`): up/down move `DIALOGUE_SELECTION.current` (rows of 13 px, +13 with a speaker),
✕ confirms, △ cancels unless trigger 49; inside a routine (`SCRIPT_TEXTBOX_MODE` 2) cancel picks the last option.
**Input**: `processInput` (`script_common.c:1217`) makes each button count once until released, except for the repeat
mask (`setInputRepeatMask(0xF000)`, the D-pad, only on the naming screen: 8 frames, then every 2).
`isXPressedAfterDialogue` ignores the ✕ that opened the box.

**Font**: script texts are full-width Shift-JIS; strings in the US executable (Digimon and item names) are ASCII and
are converted on the fly (`convertAsciiToJis`, `sjis.c:63`). `drawGlyph` looks each code up in `CHAR_TO_GLYPH_TABLE`
(79 US entries; the last one is the search sentinel, so an unknown character draws `GLYPH_DATA[78]`), expands it to a
4 bpp 12x11 cell with `setTextColor(c)` and uploads it with `LoadImage`. `DRAW_STRING2_IS_FIXED_WIDTH` (`0x80134F98`)
forces 12 px per character (naming screen). `TEXT_COLORS` (`utils.c:44`) is a separate palette for numbers drawn with
polygons. The glyph format, `FONT_CLUT` and our fonts are documented in [../mods/font.md](../mods/font.md).

**Floating numbers and bubbles**: `addEntityText` (`entity_text.c:89`) shows up to 8 numbers per fighter that rise for
31 frames; `69` uses it outside battle. `addConditionBubble` (`bubble.c:428`; types 0 hunger, 1 poop, 2 sick, 3 sleep,
4 tired, 5 dying, 6 injured, 7 evolving): 3 bubbles at once, grow for 10 frames, float up 50 and pop. Monochromon's mood
bubble (routine 0x1C) is a separate sprite driven by p247/p248.

## How the flags tell the story

- **Jijimon's questions** (new game, patch 0273): the greeting remains MAPHEAD 1238 entry 0x10
  (`m1238.u16`). Entry 0x23 introduces seven questions. Each question uses three consecutive entries starting
  at 0x24: its numbered heading (the seventh says "Last question."), question, and speaker plus three answers.
  The topics are owning a Digital Monster, day/dusk/night, friends, camping, a blocked path, island supplies,
  and a partner's most valued quality. All seven are mandatory. Entry 0x39 announces the selected species using
  `{partner}`, populated from its real species name before the tamer-name prompt.
  `newGameStateMachine` loops through the questions in states 0x23-0x28. The answer vector feeds
  `modQuizResult`; **p254 is an index into `newGame.starters`**, never the species id. All three consumers
  (partner creation and the two default-name paths) call `modNewGameStarter`, which reads the packed uint16 list.
  The existing tamer-name and optional partner-name states follow unchanged; `modPartnerNameSetSpecies` supplies
  the default. Script 204 still places the new tamer in File City. Weights, cells and the 35-rookie pool
  live in `content/tables/new-game.json`; `tools/starter_quiz.py` checks all 2187 answer paths.
  `story/new-game-quiz.dws` extends the base text table only for the expanded engine; original-engine builds keep
  the legacy table and its smaller MAPHEAD buffer.
- **Recruiting** (Kunemon, script 2 section 6, the NPC in slot 1 of Kunemon's Bed): sets trigger 44, the NPC asks for
  food (a two-option selection), then trigger 3 and routine 0 let the player pick an item (into p254); `IF p254` is one
  of the meats 38..41 → animations and a challenge → trigger 1, p250 = 1, p251 = 6, p252/253 = 0xFF → `66` → clear
  trigger 1 → the recruit line → **`1C 232`** (200 + 32) and **`1F 01 01`** (p1 += 1). Trigger 203 (Agumon) is set by
  sections 5/6 of script 48 (Ogre Fortress). Back in the city, MH 180-203 and `getFileCityTopMap` choose the layout and
  164:51 sends the player to one screen or another by who has been recruited (see [world.md](world.md)).
- **Prosperity**: `IF trig220 || trig214 || p1 >= 50` (the large city) appears in 14 scripts and in the Auto Pilot;
  108:5 needs p1 >= 40, 171:6 >= 30, 163:9 >= 20 and trigger 185; 105:254 changes the Native Forest ground items with
  p1 < 10 / >= 25. `murd.c:769` and `dooa.c:1690` choose the revival screen with the same conditions. Because
  `recalculatePPandArena` rewrites p1 on every save, **what counts are the 200+type triggers**. The city rules as data
  are in [../mods/city-rules.md](../mods/city-rules.md).
- **Tournaments**: routine 0x21 or the registration in `dget.c:684` set trigger 37 (and 38/39) and p2/p3/p4;
  `tournament.c:51` watches every frame and launches MH 0x4D9/0x4DA; the result goes to p255 (3 = won) and
  `startTournament` (`utils2.c:663`) sets trigger 15 + cup. See [combat.md](combat.md).
- **Every day** (`dailyPStatTrigger`, also at boot): new recycle stock (6 ids from 1..64, never 4), p28-p31 += 1 unless
  0xFF, p2 &= 0x7F.
- C-side shortcuts into MAPHEAD: item 22 (Auto Pilot) → MH 0x4DD; partner death (`partner_impl.c:1913`) → MH 0x4DE;
  routine 0x36 saves the finished game (trigger 50 is set by the ending scripts).

## Writing state by hand

- Triggers are bits inside bytes: change one with a read-modify-write of `0x801BDFCD + N/8`. To recruit by hand, set
  trigger 200+type **and** add to p1 (the game recalculates p1 on saving anyway).
- Pstats >= 35 do not persist and are reset by screen scripts: write them after the screen has loaded.
- Running a section from outside only works with `IS_SCRIPT_PAUSED == 1` and no open boxes, and has to reproduce
  `callScriptSection` (pointer, section, event flag, dialogue owner, `ACTIVE_INSTRUCTION`, the sync bit, all 22
  `SCRIPT_MOVEMENT` types to 0xFF, then `IS_SCRIPT_PAUSED = 0`). Patching the section table in `MAP_SCRIPT_BUFFER` (so
  that an NPC's section points elsewhere, then talking to it) is simpler; the buffer is reloaded on a screen change.

Unverified: whether pstats 38-44 used by the File City MAPHEAD sections are always recalculated on load (they are not
saved); the finer meaning of many triggers in 100-199 and 313-363 (only the setting and reading sections are known).

In the extended story the wild helper emits a recruit flag only for a roster
species after a first victory, followed by a join jingle and narrator line. The
six removed residents (ModokiBetamon, Dokunemon, Vermilimon, IceDevimon,
DarkLizardmon and Gururumon) no longer receive that flag from wild recruitment.
The original story retains its legacy enemy beaten flags and original bytes.
