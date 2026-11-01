# Core: boot, main loop, states, clock and new game

How the executable (`SLUS_010.32`) starts, runs one frame, keeps the game clock, starts a new game and drives the
title menu. The memory card layout and checksum are in [save-format.md](save-format.md); the partner's care and
evolution in [partner.md](partner.md); the script interpreter in [scripts.md](scripts.md).

Addresses are RAM addresses of the original US executable (`decomp/config/us/symbols.txt`). A rebuilt executable
places variables elsewhere; `tools/dwsyms.py` resolves a name for either build. `file.c:line` citations point into
`decomp/src/main/` unless another directory is given. `[inferred]` marks what is deduced rather than read in the code.

## Source files

| File | Contents |
|---|---|
| `src/main/main.c` | `main()`, initialization, outer loop, "Press Start" screen, `gameLoop`, input, `initializeLoadedMap`, `recalculatePPandArena`; also the `DIGIMON_DATA` table and the core globals (l. 3184-3267) |
| `src/main/clock.c` | `tickGameClock`, `tickPlaytime`, `advanceToTime`, `initializeClockData`, clock drawing |
| `src/main/new_game.c` | the new-game Jijimon scene (model 0x75, camera, lights) |
| `src/main/main_menu.c` | title menu, memory card, `SavegamePayload`/`SaveFile`, `writeSavegame`/`loadSavegame`, saving when going to sleep, the save machine, VS registration |
| `src/main/_psstart.c` | startup: `__start` sets `sp`/`gp`, zeroes `.sbss`/`.bss`, enables the GTE and calls `main` |
| `include/dw/main.h` | `SavedState`, `GENERAL_BUFFER` (0x80010000), `TEXTURE_BUFFER` (0x80088800) |
| `include/dw/clock.h`, `params.h` | clock prototypes; `DigimonPara`, `PartnerPara` (0x84 bytes), `CONDITION_*` |
| `src/shop/script_menu.c:1070` | `newGameStateMachine` (the naming dialog and partner choice), in the SHOP overlay |

## State in memory

**States and counters**

| Symbol | RAM | Type | Meaning / values |
|---|---|---|---|
| `MAIN_STATE` | `0x80134EB4` | i8 | kind of game, stored in the save: 0 new, 1 in progress, 2 finished, 3 quit to title |
| `GAME_STATE` | `0x80134F0A` | i8 | 0 world, 1 battle, 2 after battle, 3 battle intro, 4 tournament battle, 5 tournament/VS (2 and 3 `[inferred]`) |
| `MONEY` | `0x80134EB8` | i32 | bits, 0..999 999 (the cap is applied by whoever adds: `battle_ui.c:426`, `script_interp.c:1046`) |
| `MERIT` | `0x80134FC4` | i16 | merit points (max 9999) |
| `BATTLES_STARTED` / `BATTLES_FLED` | `0x80134FC8` / `0x80134FCA` | i16 | saved counters |
| `TOURNAMENTS_WON` / `TOURNAMENT_WINS` / `TOURNAMENTS_LOST` | `0x80134FCC` / `0x80134FCE` / `0x80134FD0` | i16 | saved counters |
| `IS_SCRIPT_PAUSED` | `0x80134FF4` | i32 | 1 = no script running; `gameLoop` only calls `tickScript` when it is 0 |
| `PAUSE_STATE` / `PAUSE_BOX_VISIBLE` | `0x80134E79` / `0x80134E78` | i8 | START pause (`utils2.c:395`) |

**Game clock** (variables in `main.c:3184-3221`)

| Symbol | RAM | Type | Meaning / values |
|---|---|---|---|
| `HOUR` / `MINUTE` | `0x80134EBC` / `0x80134EBE` | i16 | 0..23 / 0..59 |
| `DAY` | `0x80134F04` | i16 | day of the year, 0..29 |
| `YEAR` | `0x80134F02` | u8 | 0..99 (wraps to 0) |
| `CURRENT_FRAME` | `0x80134F08` | u16 | frame of the day = `HOUR*1200 + MINUTE*20`, 0..28799 |
| `LAST_HANDLED_FRAME` | `0x80134F06` | u16 | copy of `CURRENT_FRAME` at the start of the tick; the partner compares it to act once per frame (`partner_impl.c:894`) |
| `SUBFRAME_COUNT` | `0x80134E1C` | u16 | helper counter for half speed |
| `IS_GAMETIME_RUNNING` | `0x80134E20` | i8 | 0 = clock stopped (cutscenes, battle, menus) |
| `CLOCK_OFFSET_X` | `0x80134E1E` | i16 | on-screen x of the clock, -135; slides out to -220 when time stops |
| `PLAYTIME_HOURS` / `_MINUTES` / `_FRAMES` | `0x80134EFE` / `0x80134EFC` / `0x80134F00` | u16 | real time played, cap 999:59 |
| `CURRENT_TIME_OF_DAY` | `0x80134D9D` | u8 | active palette (`map.c:4443`): 0 dusk, 1 night, 2 day `[inferred type]` |
| `CLOCK_SPRITE` | `0x80150C8C` | GsSPRITE | clock hand, `rotate = MINUTE*0x6000` (6 degrees per minute) |
| pstat 0 `PSTAT_TIME_SPEED` | `0x801BE031` | u8 | 0 normal, 1 double, 2 half, 3 stopped by a script |

**Title menu and memory card** (`main_menu.c:148-166`)

| Symbol | RAM | Type | Meaning |
|---|---|---|---|
| `SAVE_FILE` | `0x8013192C` | 0x2000 | live image of the memory card block (see [save-format.md](save-format.md)) |
| `SAVE_FILE_NAME` | `0x8013190C` | char[32] | `BASLUS-01032DMR*`; byte 15 becomes the slot digit |
| `SAVEGAME_SLOT_INFO[15]` | `0x801BF768` | 15 x 0x44 | preview of each slot (valid, names, place) |
| `CURRENT_MENU` / `TARGET_MENU` | `0x8013504C` / `0x80135068` | i32 | current and next state of the menu machine (-1 closed, -2 opened from the game) |
| `MAIN_MENU_TICKS` | `0x80135048` | i32 | ticks since the last menu change |
| `MAIN_MENU_ACTION` | `0x80135034` | i32 | 0 new, 1 continue, 2 delete, 5 battle mode |
| `MEMORY_CARD_ID` / `MEMORY_CARD_SLOT` | `0x80135044` / `0x8013503C` | i32 | channel (0 port 1, 0x10 port 2) and slot 0..14; -1/-1 = playing without a card |
| `CONNECTED_CARDS` / `NEW_CARDS` / `CHECKED_MEMORY_CARD` | `0x80135030` / `0x80135050` / `0x80135064` | u32 | bits 1 and 0x10 per port; the last is the port polled next |
| `MEMORY_CARD_ERROR` / `_OPERATION` / `_RETURN_MENU` / `_USED_BLOCKS` | `0x80135040` / `0x80135058` / `0x8013506C` / `0x80135070` | i32 | error shown; operation message (0 checking, 1 saving, 2 loading, 4 deleting, 5 formatting); menu to return to; used blocks |
| `SAVE_RETRY_RETURN_MENU` | `0x80135074` | i32 | menu to return to after an in-game save error |
| `VS_PLAYER_INDEX` / `BATTLE_REGISTRATION_SLOT` | `0x8013505C` / `0x80135060` | i32 | battle mode / registration |
| `MEMCARD_DIRENTRIES` | pointer at `0x801346D0` | | card directory, at `0x8008E400` (`TEXTURE_BUFFER+0x5C00`) |
| `VS__REGISTERED_DIGIMON_BUFFER` | pointer at `0x801346D4` | 2 x 40 x 64 | registered Digimon of both players, at `0x8008D000` |
| `FIRST_SCREEN_PRESSED_START` / `FIRST_SCREEN_FRAME_COUNTER` | `0x80134EB0` / `0x80134EAC` | i32 | "Press Start" screen |
| `POLLED_INPUT` / `POLLED_INPUT_PREVIOUS` / `CHANGED_INPUT` | `0x80134EE4` / `0x80134EE8` / `0x80134EEC` | i32 | controller 1 (Psy-Q bits: START 0x800, up 0x1000, down 0x4000) |
| `NEW_GAME_JIJIMON_TICK_COUNT` | `0x80134F10` | i16 | opening scene counter |

The player and partner blocks the core saves and restores (`SAVED_STATE`, `PARTNER_PARA`, `PARTNER_ENTITY`,
`TAMER_ENTITY`, `INVENTORY`, `WORLD_POOP`, `SCRIPT_STATE`, the screen bytes) are listed in [ram-map.md](ram-map.md).
The player's name lives in `DIGIMON_DATA[0].name` (`0x8012CEB4`, 20 bytes, entry 0 of the Digimon table in the
executable's data).

**Function addresses**: `__start 0x800A4240`, `main 0x800EE800`, `gameLoop 0x800EFB68`, `runLandingScreen 0x800EED30`,
`runMainMenu 0x800EEFE4`, `newGameScene 0x800EF1E0`, `initializeLoadedMap 0x800EF38C`, `recalculatePPandArena
0x800EFA18`, `tickGameClock 0x800DCF84`, `tickPlaytime 0x800DD5E0`, `advanceToTime 0x800DD678`, `initializeClockData
0x800DCE04`, `stopGameTime 0x800DD798`, `startGameTime 0x800DD7A0`, `tickMainMenu 0x8010FF1C`, `writeSavegame
0x801130C8`, `loadSavegame 0x80112D84`, `createSavegameChecksum 0x80112D34`, `initializeDefaultSavegame 0x80112B30`,
`openSaveMachine 0x8011381C`, `gameClearSave 0x801139AC`, `newGameStateMachine 0x8010C7AC`, `dailyPStatTrigger
0x800FC374`, `updateTimeOfDay 0x800D676C`, `handlePause 0x800E62D0`, `cleanupGame 0x800D96B4`.

## Startup and outer loop (`main.c:3317-3471`)

1. `__start` sets `sp`, `gp`, clears bss, enables the GTE (`mtc0` to status register 12) and jumps to `main`.
2. `main` initializes: heap (`initializeHeap`, from `_end` up to the stack base), sound, GPU (`GsInitGraph(320,240,...)`,
   double buffer at y=0 and y=240), controller, CD, memory card (`MemCardInit(1)`), models, objects, font, scripts,
   camera, UI, inventory, clock (`initializeClockData`) and loads `\ETCDAT\FI_INFO.TIM`.
3. Infinite loop:
   - **Title**: `playMovie(0)` (`\MOVIE\OP1.STR`) and `runLandingScreen`: "Press Start" for 600 refreshes at 60 Hz
     (10 s), then back to the movie; START sets `FIRST_SCREEN_PRESSED_START = 1`.
   - **Menu**: loads `\ETCDAT\ETCTIM.BIN` and runs `runMainMenu` (below). It exits with `MAIN_STATE` set.
   - **Game loading** by `MAIN_STATE`:
     - 0: `newGameScene` (Jijimon scene), movie 1 (`OP2.STR`), `initializeTamer`, partner = Agumon (3) if pstat 0xFE is
       0, else Gabumon (0x11), `setDigimonRaised`, `initializeMap`, `initializeChest`, `runMapHeadScript(0xCC)` (screen
       204, `TWNA01`, File City), `addClock`, `stopGameTime`: the clock starts when the intro script releases it.
       `initializeLoadedMap` is **not** called, so the default `SAVED_STATE` (partner type 0x72, default
       `partnerPara`) is not applied; `MONEY` is.
     - 1: `initializeTamer`, `initializePartner(SAVED_STATE.partnerType)`, map, `runMapHeadScript(currentScreen)`,
       `initializeLoadedMap`, which copies `SAVED_STATE` into the live variables (positions, stats, lives, `MONEY`,
       `PARTNER_PARA`, screens, waypoints), moves the tamer to the saved exit if the partner loaded on top of an NPC and
       calls `setImmortalHour`; then `addClock`.
     - 2: as 1, but movie 2 (`ED2.STR`) plays first.
   - `recalculatePPandArena` (US only): rewrites pstat 1 (prosperity) from the recruit triggers (see
     [scripts.md](scripts.md#pstats)) and, if pstat 3 >= 0x17, clears triggers 0x25-0x27. The prosperity helper counts IDs 3..58 in original story and only the owned City roster in extended story; City entry calls only that helper.
   - **Game**: `while (MAIN_STATE != 3) gameLoop();`.
   - **End**: `cleanupGame` (removes objects 0xFA0/0xFA8/0xFA6/0xFB9/0xFA2/0xFB5, entities and models), `playMovie(3)`
     (`EDR.STR`, the only movie START cannot skip) and back to the title.

## Game loop and timing (`gameLoop`, `main.c:3876-3906`)

`pollInputGame` → `processInput` → `updateTournamentRegistration` → `tickScript` (if `IS_SCRIPT_PAUSED == 0`) →
camera → `tickObjects` → `renderObjects` → `DrawSync` → `VSync(3)` → swap → `handlePause`.

`VSync(3)` waits for three vertical retraces: **20 iterations per second** on NTSC (consistent with `tickPlaytime`
counting one real minute every 1200 frames). The title and menu screens use `VSync(0)` (60 Hz). Everything that lives
in the world (clock, partner, NPCs, UI) is an object registered with `addObject(id, ..., tick, render)` and walked
every frame. The mod's 30/60 fps option changes this; see [frame-rate.md](frame-rate.md).

**Input** (l. 3978-4018): `CHANGED_INPUT` = newly pressed buttons plus D-pad auto-repeat (mask `0xF000F000`): in the
game after 5 frames, then every 2; in menus after 15, then every 6.

**Pause** (`utils2.c:395-428`): at the end of each frame START (read with `PadRead(1)`) toggles `PAUSE_STATE`; while it
is 1 the box is drawn and the game spins in a busy loop until the next START. There is no pause while a script has time
stopped (pstat 0 == 3 or `IS_GAMETIME_RUNNING == 0`) in the world, nor during a protected fade.

## `MAIN_STATE` (`main.c:3190`)

| Value | Set by | Effect |
|---|---|---|
| 0 | the menu when creating a game (`main_menu.c:2581`), loading a file whose `mainState` is 0 (a freshly created slot carries 0), and choosing to sleep without saving in the sleep menu (l. 2837; never reaches a file, since every save forces 1) | `main` runs the new-game scene |
| 1 | `openSaveMachine` and saving when going to sleep (`partner.c:327`) | game in progress; every normal save carries it |
| 2 | `gameClearSave`, script routine 0x36 | game finished; on load `ED2.STR` plays and the player appears at `getFileCityTopMap()` (screens 0xAE-0xB3 by triggers 0xD6/0xDC/0xDD/0xE1/0xF6) |
| 3 | script routine 0x35 after the ending (`script_interp.c:443`) | the only value with an immediate effect: `gameLoop` ends, `cleanupGame`, `EDR` movie, title |

0, 1 and 2 are only checked when leaving the menu; changing them mid-game does nothing until a save writes them.

## `GAME_STATE` (`main.c:3221`)

0 world (`initializeTamer`, and on return from a battle); 1 battle (`startBattle`, `tamer.c:800`): the whole battle runs
inside `BTL_battleMain` with the clock stopped; 2 and 3 are set by the BTL overlay when the battle ends and starts
(`btl.c:491`, `:379`) `[inferred]`; 4 tournament battle (`std_main.c:3744`); 5 tournament and VS setup and menus. The
clock only advances in 0 (`clock.c:89`); partner and NPCs dispatch their tick on this value. Battles are covered in
[combat.md](combat.md).

## Game clock (`clock.c`)

`addClock` registers two objects: 0xFA2 (`tickGameClock` + `renderGameClock`) and 0xFB9 (`tickPlaytime`).

`tickGameClock`, every frame:

1. `LAST_HANDLED_FRAME = CURRENT_FRAME`. Return without advancing if `GAME_STATE != 0`, fishing is in progress,
   `MAP_LAYER_ENABLED == 0` or `IS_GAMETIME_RUNNING == 0`.
2. If pstat 0 is 3 it is set to 0, so the later `return` for speed 3 is unreachable. Speed 0: `CURRENT_FRAME += 1`;
   1: `+= 2` (kept even); 2: `+= 1` every two frames via `SUBFRAME_COUNT`.
3. Each time `CURRENT_FRAME % 20 == 0`: `MINUTE++`. **20 frames = 1 game minute = 1 real second; 1 game hour = 1 real
   minute; 1 day = 24 real minutes; 1 year (30 days) = 12 real hours.**
4. `MINUTE == 60`: `HOUR++`, `MINUTE = 0`, `PARTNER_PARA.evoTimer++`, `PARTNER_PARA.remainingLifetime--`,
   `SUBFRAME_COUNT = 0`.
5. `HOUR == 24`: `PARTNER_PARA.age++`, `DAY++`, `HOUR = 0`, `CURRENT_FRAME = 0`, `dailyPStatTrigger()`;
   `remainingLifetime` is clamped at 0.
6. `DAY >= 30`: `DAY = 0`, `YEAR++`; if happiness is 100, 5 % chance to gain a tamer level; if happiness < 0, 10 %
   chance to lose one (`addTamerLevel`, `tamer.c:1272`, level 0..10).
7. `YEAR >= 100` wraps to 0; clock hand updated; `updateBGM()`.

`dailyPStatTrigger` (`script_common.c:1355-1392`): rerolls the six card-shop offers (`SCRIPT_STATE.smth[0..5]`, values
1..64 except 4; the duplicate check compares against slots already set to 0xFF, so duplicates are possible: original
bug), increments pstats 0x1C-0x1F unless they are 0xFF and clears bit 7 of pstat 2. It also runs at boot.

Other ways time advances:

- `advanceToTime(hour, min)`: jumps to a time; if it is earlier than now it adds a day (`DAY++`, `age++`,
  `dailyPStatTrigger`, `YEAR++` when needed, without the tamer-level roll) and recomputes `CURRENT_FRAME`, then
  `updateTimeOfDay()`. Sleep uses it to jump to the wake-up time.
- `advanceBattleTime` (`tamer.c:848-884`): each battle adds 20 minutes (400 frames) and rolls hour, day and year on its
  own, **without** `dailyPStatTrigger`, `age++` or `evoTimer++`.
- Scripts: `STORE_DATE` writes year/day/hour/minute into four consecutive pstats; `ADVANCE_TO_DATE_AT` sets the date
  from four pstats, calls `skipHours` for the difference and `dailyPStatTrigger` if the day changed.
- `stopGameTime`/`startGameTime` only touch `IS_GAMETIME_RUNNING`. Script cutscenes stop the clock and set pstat 0 = 3,
  and restore it when they finish.

`tickPlaytime` counts one minute every 1200 frames whenever its object exists, capped at 999:59.
`initializeClockData`: year 0, day 0, 08:00, `CURRENT_FRAME = 9600`, playtime 0, clock at x = -135, clock running.
The mod's clock rules (how long a game day lasts) are data since patch 0127.

## Day and night

There is no single flag: each consumer compares `HOUR` against its own thresholds.

| Consumer | Day | Transition / night | Where |
|---|---|---|---|
| Map palette and lights (`updateTimeOfDay`) | 6 <= h < 16: `MAP_CLUTS[0]`, `CURRENT_TIME_OF_DAY = 2` | 16-19: `MAP_CLUTS[1]`, lights x0.7 green/blue, value 0; h < 6 or >= 20: `MAP_CLUTS[2]`, lights x0.5, value 1 | `map.c:4443-4451` |
| Live palette fade | | started on the first frame of 16:00, 20:00 and 06:00 (`CURRENT_FRAME % 1200 == 0`) and after a battle | `map.c:4096-4106`, `tamer.c:919` |
| Interiors | `MAP_ENTRIES[screen].flags & 0x40` → always `MAP_CLUTS[0]` | no transitions | `map.c:4438` |
| Clock sun/moon icon | 6 <= h < 17 | rest | `clock.c:233` |
| Music variant | 6 <= h < 21 (when pstat 245 == 0) | rest | `script_interp.c:1515` |
| Map object lights (street lamps) | 7 <= h < 19 | rest | `utils2.c:551` |

When `HOUR` is changed directly, the palette does not update until the next transition, screen change or call to
`updateTimeOfDay`.

## New game

1. In the menu, NEW GAME → a card and an empty slot, or the no-card option (menu 0x13). Either way
   `initializeDefaultSavegame` fills `SAVE_FILE.saves[0]` and `loadSavegame` copies it into RAM; with a card the file
   is also created and written with that content, so **a freshly created slot holds a game with `mainState = 0`**, and
   continuing from it replays the intro.
2. Default values (`main_menu.c:3840-3878`): everything 0; `currentScreen = 0xCC`, `currentExit = 9`; `partnerType =
   0x72` (does not decide the partner); placeholder player and Digimon names; 100 poop slots with `map = 0xFF`;
   `money = 50000`; `tamerLevel = 0`, `raisedCount = 1`; year 0, day 0, 08:00, `currentFrame = lastHandledFrame =
   9600`; `partnerLives = 3`; `remainingLifetime = 0x120` (288 h); `age = 3`; card offers 0x3A..0x3F; a 30-slot
   inventory from `DEFAULT_INVENTORY_TYPES`/`_AMOUNTS` (29 items, one free slot). The intro script of screen 0xCC trims
   what the player actually starts with. This start state is data in the mod (patch 0128,
   [../mods/city-rules.md](../mods/city-rules.md)).
3. `newGameScene` (`main.c:3670-3717`): pstat 0xFE = 0, pstat 0xF3 = 0xFF, `loadNewGameScene` (Jijimon, model 0x75,
   three flat lights); `tickNewGameJijimon` sets pstat 0xF3 = 0 at tick 0x23 and from then on `newGameStateMachine`
   runs: Jijimon's questions, the partner choice (pstat 0xFE: 0 Agumon, 1 Gabumon), the player name into
   `DIGIMON_DATA[0].name` and the partner name into `PARTNER_ENTITY.name`. The scene has its own `VSync(3)` loop. The
   question flow is described in [scripts.md](scripts.md#how-the-flags-tell-the-story).
4. Case 0 of `main` follows. The partner is created by `initializePartner` (see [partner.md](partner.md)), not from the
   file.

## Saving and loading

The block format, payload fields and checksum are in [save-format.md](save-format.md). Engine-side facts:

- `writeSavegame` first calls `recalculatePPandArena`; if pstat 0 is 3 (time stopped by a script) it saves 0 and
  restores 3 afterwards.
- `loadSavegame` writes `MONEY`, clock, inventory, names, tamer level, poop, counters, `SCRIPT_STATE` and `MAIN_STATE`
  directly, but positions, stats, lives, `partnerPara`, screens and waypoints go to `SAVED_STATE` (`0x801555D0`) and
  only reach the live variables in `initializeLoadedMap`.
- Only the first 0x17C bytes of `SCRIPT_STATE` are saved: all 800 triggers but only **pstats 0-34**.
- Not saved: anything of the loaded map (objects, wild Digimon), items on the ground, camera, pstats >= 35, the script
  stack, `IS_GAMETIME_RUNNING`, the pause state.

**Where the game saves** (skipped when `MEMORY_CARD_ID == -1`):

- Going to sleep (`partner.c:313-352`): after the fade, menu 0x28 offers sleeping with or without saving, with
  `MAIN_STATE = 1`; saving goes 0x29 (check card) → 0x2A (file exists?) → 0x2B (`writeSavegame` and write) → 9 → close.
  Errors go to 0x30 (retry/cancel).
- The save machine (routine 0x30 → `openSaveMachine`; the script advances it with `tickSaveMachine`): `MAIN_STATE = 1`,
  menu 0x3C asks whether to register the partner for battle mode → 0x3D (slots 0-38; 39 is reserved for Machinedramon)
  → 0x3E → `registerBattleData` → 0x3F-0x41 (save); declining goes to 0x45 (save prompt) → 0x3F or 9. A partner below
  level 3 (Fresh/In-Training) gets 0x46 and 0x45; no card gets 0x44.
- The ending (routine 0x36 → `gameClearSave`): `MAIN_STATE = 2`, `CURRENT_SCREEN = getFileCityTopMap()`, Machinedramon
  written into registration slot 39 (`awardMachinedramonData`: species 0x73 with the partner's stats and techniques
  0x2E/0x30/0x32), then menu 0x45; without a card, nothing is saved.

## Title menu (`runMainMenu`, `main.c:3628`; `tickMainMenu`, `main_menu.c:2278`)

A state machine on `CURRENT_MENU`/`TARGET_MENU`: when they differ, `drawMainMenuStrings` draws the new menu, makes it
current and zeroes `MAIN_MENU_TICKS`; most card operations wait for `MAIN_MENU_TICKS >= 3` so the "checking" message
is seen. `MENU_VIEWS` maps menu → screen drawn by `renderMainMenu`. `updateMemoryCardState` alternates between the two
ports on each completed `MemCardSync` and maintains `CONNECTED_CARDS`/`NEW_CARDS`; a card change returns to the source
menu (`getMenuOnCardChange`). `runMainMenu` ends when `CURRENT_MENU == -1` and the fade has finished. Navigation
(`tickMenuInput`): up 0x1000, down 0x4000, `CONFIRM_BUTTON` returns 1, `CANCEL_BUTTON` 2.

| Menu | What it is | Next |
|---|---|---|
| 0 | NEW GAME / CONTINUE / DELETE / BATTLE MODE (`TITLE_MENU_ITEMS`); the middle two need a card | 0xA / 0x14 / 0x1E / 0x32 |
| 0xA | card 1, card 2, no card | 0xC / 0x13 |
| 0xC → 0x11 | check, count blocks (15 used = no free block), choose an empty slot, confirm, create the file, write the default game | 9 with `MAIN_STATE = 0` |
| 0x13 | confirm playing without a card: `MEMORY_CARD_ID = MEMORY_CARD_SLOT = -1`, default game | 9 |
| 0x14 → 0x19 | continue: card, check, list slots (`loadSaveSlotData` reads 0x80 bytes of each `...DMR?` file and takes the names from the title), choose a used slot, confirm, read and validate | 9; `MAIN_STATE` comes from the file |
| 0x1E → 0x23 | delete (`MemCardDeleteFile`) | 0x1F |
| 1 / 2 | format prompt / formatting | source menu |
| 3 | error message (`MEMORY_CARD_ERROR_MESSAGES`); closes on a button or after 0x12D ticks | `MEMORY_CARD_RETURN_MENU` |
| 9 | close: after 3 ticks `TARGET_MENU = -1` | -1 |
| 0x28-0x2B, 0x30-0x31 | saving when going to sleep, and retry | see above |
| 0x32-0x38 | battle mode: loads the registration data of two saves into `VS__REGISTERED_DIGIMON_BUFFER` and launches `VS_REL` | 0 |
| 0x3C-0x46 | save machine and ending | see above |

The mod moves this code into a menu overlay (patch 0211) and adds an OPTIONS entry ([../mods/options.md](../mods/options.md)).

## Writing state by hand

Facts that matter when RAM is edited from outside (recipes are in [../developing.md](../developing.md)):

- `HOUR`/`MINUTE` and `CURRENT_FRAME`/`LAST_HANDLED_FRAME` must agree (`CURRENT_FRAME = HOUR*1200 + MINUTE*20`). The
  palette only follows at the next transition, screen change or sleep; partner schedules read `HOUR` at once.
- Changing `DAY` directly runs neither `dailyPStatTrigger` nor `age++`; letting the clock cross midnight does.
- Writing `IS_GAMETIME_RUNNING = 0` stops hunger and sleep and blocks the START pause.
- `MAIN_STATE = 3` ends the game on the next frame without saving; doing it in a battle or menu destroys objects under
  them. Values 0-2 only matter when saved, and every save forces 1, so a finished game can only be made by editing the
  file (see [save-format.md](save-format.md)).
- Setting `MEMORY_CARD_ID`/`MEMORY_CARD_SLOT` to a card after starting without one fails at the next save (the file does
  not exist).

Unverified: the 0x1B bytes after the tamer waypoints in the save payload and the 0x80-byte `unk20` of `SAVED_STATE`
are never written in the code read; a `mainState` other than 0-2 in a file enters none of the load cases.
