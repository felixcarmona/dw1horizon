# Minigames, training, VS and ending

The overlays that are neither world nor combat: fishing, curling, training with its slot machine, the two-player VS
mode, the ending's dissolve and Machinedramon's appearance. For each: how it is entered, its state in memory, its
rules and formulas, and what it hands back to the executable. Paths are `decomp/src/...`; RAM addresses are those of
the original USA build.

## Summary

Six overlays cover what is neither world nor combat: **fishing** (`FISH`, two screens
of Dragon Eye Lake), **curling** (`KAR`, Freezeland, against Penguinmon or MetalMamemon),
**training** (`TRN` for Green Gym, Gear Savanna and Misty Trees; `TRN2` for Beetle
Land, Trash Mountain and Ice Sanctuary; both with the optional slot machine), the **two-player
VS** from the main menu (`VS`, reads the 40 registered Digimon of each card), the
**tamer dissolving in the ending** (`ENDI`) and the **appearance of Machinedramon** (`EAB`:
it has no strings, it is identified by its caller, `tamerTickMachinedramonSpawn`). None of them
touches the title or the opening in the USA version. All of them return their result to the executable
through very specific variables: fishing gives the item and fires a script, curling writes
PStat `0x79`, training fills `STATS_GAINS` and sets `TRAINING_COMPLETE`, VS only
counts wins in RAM and returns to the menu. The paths below are `decomp/src/...`.

## Source files

| Overlay | Loads at | Files | Lines |
|---|---|---|---|
| `FISH_REL` | `0x80070000` | `fish/fish.c`, `fish/fish_model.c`; glue `main/fish.c` | 4671, 77; 144 |
| `KAR_REL` | `0x80053800` | `kar/kar.c`; glue `main/kar.c` | 3142; 13 |
| `TRN_REL` | `0x80088800` | `trn/trn_{hp,mp,off,def,speed,brain}.c`, `trn_reward.c`, `trn_slots.c`, `trn_hud.c` | 161, 163, 237, 271, 138, 170, 882, 426, 387 |
| `TRN2_REL` | `0x80088800` | `trn2/trn2_hp_map{99,107}.c`, `trn2_mp.c`, `trn2_off.c`, `trn2_def_map{99,108}.c`, `trn2_reward.c`, `trn2_slots.c`, `trn2_hud.c` | 145, 151, 102, 235, 181, 147, 447, 426, 587 |
| `VS_REL` | `0x80056C68` | `vs/vs_select.c`, `vs_scene.c`, `vs_intro.c`, `vs_combat.c`, `vs_main.c`, `vs_camera.c`, `vs_hud.c`, `vs_effect.c` (`vs_demo.c` JP only); registration and cards in `main/main_menu.c` | 1204, 1814, 588, 2675, 1840, 836, 1489, 5755 |
| `ENDI_REL` | `0x80060000` | `endi/endi.c` | 420 |
| `EAB_REL` | `0x80060000` | `eab/eab.c` | 710 |

Headers: `include/dw/{fish,kar,trn,trn2,training,vs,endi,eab}.h`. The `*_bss_us.c` files are
only the overlay's `.bss` reservation. How each one gets in: `FISH` and `KAR` are loaded on
entering their map (`main/fish.c:117-144`, `main/kar.c:8-13` from `map.c:4220`); `TRN`/`TRN2`
are preloaded by `loadTrainingLibrary` (`map.c:5581-5593`: maps 112, 78, 119 → TRN; 107, 108,
165, 99 → TRN2); `VS` is loaded by the main menu (`main_menu.c:3133`); `EAB` and `ENDI` are
loaded by script commands `0x33` and `0x34` (`script_interp.c:1765-1776`).

## State in memory

NTSC-U addresses from `config/us/symbols*.txt`; offsets inside structures
come from the debug information of a GCC build of the decompilation (they match the headers).

### Fishing (`FISHING_DATA` = `0x8007AC58`, 0x2D10 bytes, `fish.h`)

| Symbol / field | RAM | Type | Meaning |
|---|---|---|---|
| `FISHING_DATA_PTR` | (main) | ptr | `&FISHING_DATA` or NULL if there is no overlay (`main/fish.c:130`) |
| `rod.fishingState` | `0x8007B41C` | i32 | rod state (0 = not fishing; table below) |
| `rod.bait` | `0x8007B428` | i32 | id of the chosen bait; on a catch it becomes the fish (`fish.c:4181`) |
| `rod.throwPower` | `0x8007B42C` | i32 | cast strength 5..25 (`fish.c:3875`) |
| `rod.swimmerType` | `0x8007B434` | i32 | 1 = Old Rod, 2 = Amazing Rod (`fish.c:4564-4568`) |
| `rod.pressedFrames` | `0x8007B460` | i32 | ticks with ✕ held (>0) or released (<0) during the fight |
| `hooked.fish` | `0x8007B464` | `Fish` 56 B | byte 0: bit0 active, bits1-4 species (0..5, 6 = Seadramon); `+2` i16 size cm |
| `hooked.fish.state` | `0x8007B488` | i32 | 0xA nibbling, 0x14 pull window, 0x28 holding, 0x32 run, 0x5A flees, 0x64 Seadramon reeled in |
| `hooked.nibbleTime` / `catchingTime` | `0x8007B49C` / `0x8007B4A0` | i32 | duration of the nibble / of the window to pull |
| `hooked.powerLeft` / `powerMax` | `0x8007B4A8` / `0x8007B4AC` | i32 | fish stamina (size+150, +100) |
| `tension.level` / `limit` | `0x8007B504` / `0x8007B50C` | i32 | line tension; limit 10000 (5000 with Old Rod) |
| `fishPool.count` | `0x8007B408` | i32 | live fish (max. 32 + Seadramon) |
| `fishingDisabled` | `0x8007B5B0` | i32 | 1 blocks fishing (set by the partner/cutscene) |
| `mapId` | `0x8007B5B4` | u32 | 6 or 8 |
| `catchComplete` | `0x8007D960` | i32 | 1 = Seadramon caught → cutscene (`fish.c:4371`) |
| `FISH_RECORD_SIZE` | `0x80154F80` | i16[8] | size record per species (main bss, `fish.c:4251-4254`) |
| `HAS_FISHING_ROD` | `0x80134D2C` | i32 | 0 no option, 1 greyed option, 2 can fish (`game_menu.c:1137`) |

### Curling (`kar.h`)

| Symbol | RAM | Type | Meaning |
|---|---|---|---|
| `KAR_D_8005B5A0[3]` | `0x8005B5A0` | `KarStoneRow` ×868 B | rows: 0 player, 1 opponent, 2 obstacles. `+0` i8 points, `+1` i8 thrown, `+8` 5×`KarStone` (172 B: `+0` state, `+4` type, `+6` weight, `+8` speed, `+C` angle, `+10` ring, `+9C` pos) |
| `MAIN_D_80135244` | `0x80135244` | i32 | match state (table below) |
| `MAIN_D_8013523C` | `0x8013523C` | i8 | who throws: 0 player, 1 opponent |
| `MAIN_D_8013523A` | `0x8013523A` | i16 | selected stone 0..4 |
| `MAIN_D_8013524C` | `0x8013524C` | i32 | aiming angle (−0x5B6..−0x18F, straight = −0x400) |
| `MAIN_D_8013523E` | `0x8013523E` | i16 | meter power 0..2900 |
| `MAIN_D_80135248` | `0x80135248` | u8 | opponent entity: 2 Penguinmon, 3 MetalMamemon (= PStat 0x7A + 2, `kar.c:759-760`) |
| `MAIN_D_80135250` | `0x80135250` | i8 | ≠0 demonstration/tutorial mode |
| `KAR_D_800639C0[]` | `0x800639C0` | ptr[] | stones in throwing order (for the tally) |
| `TAMER_STATE` | `0x80134C91` | i8 | 12 = curling, 11 = fishing, 16 = ending, 18 = Machinedramon |

### Training (`trn.h`, `trn2.h`, `training.h`)

| Symbol | RAM | Type | Meaning |
|---|---|---|---|
| `TRAINING_STATE` / `MAIN_D_801353BD` | `0x80135371` / `0x801353BD` | i8 | minigame phase (TRN / TRN2) |
| `MAIN_D_80135370` / `MAIN_D_801353BC` | `0x80135370` / `0x801353BC` | i8 | 1 = slot machine active (copy of PStat 0xF6) |
| `MAIN_D_8013537A` / `MAIN_D_801353C2` | `0x8013537A` / `0x801353C2` | i16 | training ticks (ends at 1200) |
| `MAIN_D_801353A0[4]` / `MAIN_D_801353E0[4]` | `0x801353A0` / `0x801353E0` | i16[4] | slot machine round: `[0]` result (−1 = not yet), `[1]` phase, `[2]` stat |
| `TRN_SLOT_MACHINE` / `TRN2_SLOT_MACHINE` | `0x8008F3A8` / `0x8008DC94` | `SlotMachine` 44 B | `+0` result, `+2` prize, `+6` state, `+8` i8[3] reel, `+1E` stat, `+22` `assist` |
| `STATS_GAINS` | `0x8013D468` | i16[6] | pending gain HP,MP,OFF,DEF,SPD,BRN (the box keeps adding it) |
| `INITIAL_COMBAT_STATS[0]` | `0x8013D610` | i16[6] | displayed stats; on exit they are copied to the partner (`trn_hud.c:134-142`) |
| `TRAINING_COMPLETE` | `0x80134CA0` | i32 | 1 when finished; consumed by `isTrainingComplete` (`tamer.c:1305-1312`) |
| `TRN_CURRENT_FRAME/HOUR/MINUTE` | `0x8013538C/8E/90` | u16,i16,i16 | time at start (TRN2: `0x801353CE/D0/D2`) |

### VS (`vs.h`, `main_menu.c`)

| Symbol | RAM | Type | Meaning |
|---|---|---|---|
| `VS_PLAYER_INDEX` | `0x8013505C` | i32 | player whose card is being read (0/1) |
| `VS__REGISTERED_DIGIMON_BUFFER` | `0x801346D4` | ptr → `TEXTURE_BUFFER+0x4800` | 2×40 `RegisteredDigimon` (64 B: stats i16×6, discipline, name[14], `+1C` species, `+1D` 3 techniques) |
| `VS_DIGIMON_P1_PTR` / `P2_PTR` | `0x8013526C` / `0x80135270` | ptr | each player's list inside the buffer |
| `VS_BATTLE_SETUP` | `0x800716A8` | 12 B | `+0` u8[2][5] chosen slots, `+A` stage 0..2, `+B` number of battles 1/3/5 |
| `VS__SELECT_BOX_DATA_SELECTION` | `0x80134F59` | u8 | option of the mode/map box; `_COUNT` `0x80134F58`; `_HAS_SELECTED` `0x80134F5B` |
| `VS_CURRENT_BATTLE` | `0x80135264` | i32 | battle in progress |
| `VS_STATE_WINS[2]` / `LOSSES[2]` | `0x80135258` / `0x8013525A` | u8 | series score |
| `VS_ROUND_WON` / `VS_ROUND_LOST` | `0x80071690` / `0x8007169C` | i8[2][5] | result per battle |
| `VS_TIMER` / `VS_TIMER_ACTIVE` | `0x80135288` / `0x8013528C` | u8 / i32 | countdown (99) / active |
| `VS_DAMAGE[2]`, `VS_STARTING_HP[2]` | `0x80135280`, `0x8013527C` | i16 | damage taken when time runs out |
| `VS__IS_DRAW` | `0x80134F40` | i32 | draw in the current battle |

### Ending and Machinedramon

| Symbol | RAM | Type | Meaning |
|---|---|---|---|
| `ENDI_STATE` | `0x80061524` | `{i32 frame; Entity*; i16 phase; i16 velocity}` | frame −1 = finished |
| `ENDI_PARTICLES[80]` / `ENDI_DATA` | `0x80060D98` / `0x80061518` | | particles and base point |
| `EAB_D_800617E8` | `0x800617E8` | `{i16 frame; i16 phase; Entity*; VECTOR}` | state of the appearance |
| `EAB_D_800617D0[3]`, `EAB_D_80061A10[100]` | `0x800617D0`, `0x80061A10` | | rings and particles |
| `BOSS_EFE_TMD` | `0x80134C28` | ptr | ring model (loaded by command `0x33`) |
| `SOME_SCRIPT_SYNC_BIT` | `0x80134E30` | | 1 when the effect ends and the script may continue |

## How it works

### Fishing (FISH)

**Entry.** Only on maps 6 and 8 (Dragon Eye Lake, `MAYO06`/`MAYO10`): `checkFishingMap`
loads the overlay, zeroes `FISHING_DATA` and calls `FISH_init`, which adds object
`0x3001` (fish, ripples, rod) (`main/fish.c:117-144`, `fish.c:4577-4595`). The triangle
menu adds the "Fishing" option if the overlay is present; it is greyed out without a rod (triggers 46
Amazing Rod / 45 Old Rod, `main/fish.c:19-30`) or without food (`sortingValue == 2`,
`main/fish.c:32-43`); choosing it runs `initializeFishing` + `tamerSetState(11)`
(`game_menu.c:1137-1142`, `2002-2010`). Every tick `tamerTickFishing` → `FISH_tickRod`
(`tamer.c:451-452`, `main/fish.c:81-94`). Fishing can be blocked from outside with
`fishingDisabled` (`setFishingDisabled`, `main/fish.c:45-57`).

**Rod states** (`FISH_tickRod`, `fish.c:3673-4376`; `rod.fishingState`):

| State | What happens |
|---|---|
| 2 → 3 | camera on the tamer; bait menu (food only; cancel = 0xE exit) (`fish.c:1303-1370`, `3764-3782`) |
| 1 → 0xE96 → 6 | rod-out animation; ← → rotate 0x40/tick; ✕ casts, △ exits; ○+D-pad moves the camera (`3784-3842`; USA buttons in `input.h:11-13`) |
| 7 | charge: `throwPower = ticks+5`; ✕ releases, ○ sets 20 ticks (maximum) (`3858-3876`) |
| 8 | flight: speed = remap(throwPower 0..20 → 100..400; Old Rod 100..200), gravity 3; ✕ stops dead (`3876-3909`). It must land in visible water or it is repeated (`3911-3936`) |
| 9 | waiting. Holding ✕ reels in line; without ✕, every 20 ticks the bite is rolled (below). If the float leaves the water or ends up < 300 u from the tamer it is recast (`3947-4034`) |
| 0xA | nibble/pull (below) |
| 0xB | fight with tension (below) |
| 0xD → 0xE | the fish reaches the rod, message, end (`4191-4288`) |
| 0x4B0 / 0x4B1 | line broken (exits) / hook lost (back to 9) (`4291-4322`) |
| 0x44C | an item caught instead of a fish (`4325-4352`) |
| 0x11AF | Seadramon reeled in → `catchComplete = 1` (`4359-4371`) |

**Fish.** Up to 32 live fish; every tick one is missing, one of the species least
represented relative to its zone's weights ({30,25,18,14,8,5}) spawns, inside that
species' polygon (`fish.c:2910-2958`, zones `568-641` map 8 and `712-785` map 6). They live 600..1200
ticks and leave (`2685`). Sizes and item per species (`FISH_KIND_INFO`, `fish.c:814-878`):

| Species | Item | Size (cm) | Pause between moves | Approaches the float if the bait is |
|---|---|---|---|---|
| 0 Digianchovy (62) | 62 | 50-60 | 30-60 | — |
| 1 Digisnapper (63) | 63 | 55-85 | 30-60 | — |
| 2 DigiTrout (64) | 64 | 60-100 | 40-75 | Happymushrm (69) |
| 3 Black trout (65) | 65 | 70-150 | 50-90 | DigiTrout (64) |
| 4 Digicatfish (66) | 66 | 100-230 | 60-120 | Moldy Meat (68) |
| 5 Digiseabass (67) | 67 | 210-300 | 60-120 | Digicatfish (66) |
| 6 Seadramon | — | 300 | — | — |

"Approaches": with that bait, a fish at 201..599 u swims toward the float (`fish.c:2742-2752`).
Ripples scare: the bait landing (radius 100) and the fighting fish (radius 700) make the fish
within the radius flee and stop spawns for 30 ticks (`2734-2760`, `2226`, `3249`).

**Bite** (`FISH_findFishToBite`, `fish.c:3021-3081`): every 20 ticks, for each fish
< 200 u from the float in state 0xA/0x14: `prob = FISH_BITE_CHANCE[(bait−38)×6 + species]`
(baits 38..70; others 0); it bites if `prob ≥ rand(1..100)`. Seadramon: every 8 ticks, fixed 20 %.

| Bait (id) | Anchovy | Snapper | Trout | Black trout | Catfish | Seabass |
|---|---|---|---|---|---|---|
| Meat (38) / Giant Meat (39) / Sirloin (40) | 10 | 20 | · | 5 / 10 / 15 | · / · / 5 | · |
| Supercarrot (41), Hawk radish (42) | 50 | 5 | 15 | · | · | · |
| Spiny green (43), Ice mushrm (45) | 30 | 10 | · / 5 | · | · | · |
| Digimushrm (44) | 50 | 5 | 20 | · | · | · |
| Deluxmushrm (46) | · | 10 | 5 | · | 5 | · |
| Digipine…Calm berry (47-61) | 20 | 10 | 5 | · | · | · |
| Digianchovy (62) / Digisnapper (63) | · | 10 / · | · | 5 | · | · |
| DigiTrout (64) | · | · | · | 15 | · | · |
| Black trout (65), Digicatfish (66) | · | · | · | · | · | 10 |
| Moldy Meat (68) | 10 | 20 | · | · | 20 | · |
| Happymushrm (69) | 80 | 10 | 10 | · | · | · |
| Chain melon (70) | · | · | · | · | 30 | · |

Digiseabass as bait catches nothing. While waiting with the bait already eaten
(`itemTaken`), from tick 31 on and every 20 ticks there is a 10 % chance of hooking an item:
`r = rand(0..99)` → ≤34 Sm. recovery, ≤62 Various, ≤82 Restore, ≤92 Omni Disk, ≤97 Auto
Pilot, 98-99 **Coral charm** (`FISH_BAIT_CHANCES`, `fish.c:359-366`, `3973-3988`).

**Pull** (`FISH_hookFish`/`FISH_tickHookedFish`, `fish.c:3090-3230`, `3429-3442`): the fish
nibbles for `nibbleTime` ticks (size < 150: 20-40; otherwise 40-60), the float sinks,
**the bait is consumed** (`removeItem`, `3201`) and the `catchingTime` window starts (30 / 60
ticks). ✕ within the first half (15 / 30 ticks) hooks it; pressing before the window keeps the bait
and says so; pressing late loses the bait; no press → it escapes.

**Fight** (`stateB`, `fish.c:4091-4172`; tension `2021-2084`): `powerLeft = size+150`,
`powerMax = +100`. Holding ✕ reels in (anim 0x22) `(Δrod×2 − remap(size 50..300 → 1..10))/2`
per tick. The fish alternates "holding" (0x28: drags `timeThisMove/8` u/tick, or `/15` if it
has ≤ 10 % power left) and "run" (0x32: 20..50 u/tick for 9..19 ticks, −1 power
every 2 ticks). It decides to run when ✕ is released or, with ✕ held ≥ 61 ticks, every 3 ticks, with
probability `powerLeft/powerMax` (`3287-3321`). Tension per tick: no ✕ and fish still
−166; no ✕ and running +41..83; with ✕ and still +71..125; with ✕ and running +166..500 (depending on
size). Limit ±10000 (±5000 with Old Rod, `2018`). At +limit for `(4 − remap(size →
1..3))×5` ticks (15 small, 5 large) **the line breaks and fishing ends**; at −limit
the hook is lost and waiting resumes. Catch when the float touches land or ends up
< 300+size u from the tamer (`4136-4150`).

**Result** (`fish.c:4191-4267`): `giveItem(species+62)`; a size message (extra praise at
≥ 200 cm; in USA it prints `size/200` m and `size%200` cm, `4236-4240`); record in
`FISH_RECORD_SIZE[species]`; `PARTNER_PARA.fishCaught++`; with the bag full the fish is released
and not given. **Seadramon**: map 6 only (map 8 has 9999 = never), every 20 ticks
it checks `HOUR == 17 || HOUR == 8` (`seadramonTime` 0x6A4/0x320, `880-919`, `2960-2977`);
it goes through 8 points and leaves. When "caught" it swims to the origin (`FISH_REEL_TARGET`), and at
< 50 u `catchComplete = 1` → `FISH_tamerTick` returns 1 → `setFishingDisabled` +
`triggerSeadramonCutscene` = `callScriptSection(0, 0x4e4, 0)` (`main/fish.c:86-93`,
`script_common.c:2972-2975`).

### Curling (KAR)

**Entry.** Map 136 (Freezeland `FRZL17`) loads `KAR_REL` (`main/kar.c:8-13`). The match is
started by the script with "Digimon routine" 1 (`SCRIPT_OP_CALL_DIGIMON_ROUTINE`,
`script_interp.c:1250-1253` → `partner.c:1136-1140`): `KAR_start`, tamer state 12 (every tick
`KAR_tick`, `tamer.c:454-455`), partner state 11. `KAR_start` loads `\ETCDAT\KARRING.TMD`,
sets up the match and sets the opponent = PStat `0x7A` + 2 (`kar.c:744-761`).

**Setup** (`KAR_setupMatch`, `kar.c:652-742`): 5 stones per side, random type with
weights 40/30/20/10 % (types 0..3, `KAR_D_8005AB8C`), mass per type {30,25,35,30}
(`MAIN_D_80134A08`); type 3 becomes a **fixed peg** when it stops (`813-818`).
0..2 neutral obstacles at `z ∈ [−2000,−1000)`, `x = {705,235,−235}[i] − rand(0..318)`.
Geometry: throwers at (±400, 1400); walls at `x = ±725`, back `z = −2525` with diagonal
corners (`1825-1851`, bounces `1434-1493`); a stopped stone with `z ≥ 190` is removed
(`1313-1325`).

**Player's turn** (`KAR_tickMatchState`, `kar.c:2721-3142`; state `MAIN_D_80135244`):

| State | Action |
|---|---|
| 1 | start-or-explain choice box: the second option → demonstration with 4 pages of hints and an automatic shot (`2744-2776`, pages `2051-2104`) |
| 5 | ↑↓ choose an unthrown stone, ✕ confirms (`2798-2814`) |
| 6 | ← → aim (step that grows each tick held), angle in `[−0x5B6, −0x18F]`; ✕ throws (`2889-2912`) |
| 8 | meter: +100/tick, on reaching 3000 it **goes back to 0 and to aiming**; ✕ locks (`2926-2958`); initial speed = power + 600 (`2968`) |
| 0xB → 0xC | physics until everything stops; rings are classified and throws are counted |
| 0xD | animated tally (`KAR_tickScoreTally`, `2147-2270`) |
| 0xF | next thrower: the one with fewer stones thrown; if equal, the one losing (tie → opponent) (`3055-3067`) |
| 0x10 | if both have thrown 5 → page 8 (you win) or 7 (not) → `KAR_finishMatch` (`3087-3097`, `3124-3134`) |
| 0x11 | the opponent chooses a shot and makes a taunt (page 5 if you are winning, 6 tie, 4 losing) (`3105-3118`) |

**Physics** (`KAR_tickStones`, `kar.c:763-824`): per tick `advance = speed/mass`,
`speed ×= 0.98`, it stops when `advance < 2`. Collisions in 11 substeps per tick when two
stones are < 150 u apart (`1366-1431`); the transferred energy depends on the impact angle
(`1728-1748`); a peg absorbs half (`1535-1571`).

**Scoring** (`KAR_classifyStoneRings`, `kar.c:419-426`, `2106-2145`; values `407`): only
stones with `z < −1380`; the **first** ring that contains it is assigned: 1 = circle r145 at
(0,−1718) → **+2**; 2 = r375 same centre → **+1**; 3 = r205 at (400,−2318) → **−2**; 4 = r205
at (−400,−2318) → **+2**. Each side's score is the sum of its stones in rings and
is **recalculated after every shot** (`2160-2175`), so knocking out the opponent's stones subtracts.

**Opponent** (`KAR_chooseOpponentShot`, `kar.c:2273-2411`). Penguinmon (entity 2): straight shot
at the button (0,−1700) if there is no stone < 150 u from the path (`2481-2529`, 30 u steps);
otherwise it hits a player stone in a ring or throws at random. MetalMamemon (entity 3):
first shot at (−400,−2300) or at the button; afterwards it decides based on the player's last stone
(type/ring), with bank shots off the wall (`2619-2639`) and keeps the peg for a
clean shot at the centre. The power is computed to reach the target and 600 is subtracted
(Penguinmon) or 500 (`2660-2686`); a ±rand(100) angle on "nervous" shots.

**Result** (`KAR_finishMatch`, `kar.c:911-937`): `writePStat(0x79, 0)` if you lose or
tie, `1` if you win, `2` if you win with ≥ 10 points; `SOME_SCRIPT_SYNC_BIT = 1`. The prize is
decided by the map script from that PStat (it is not in the overlay).

### Training (TRN and TRN2)

**Entry.** Script command `0x07` (`script_interp.c:1606-1652`): the type comes from PStat
`0xFE` (0 HP, 1 OFF, 2 SPD, 3 DEF, 4 MP, 5 BRN); on maps 107/108/165/99 it calls
`TRN2_setup*`, elsewhere `TRN_setup*`. Each `setup` sets positions, adds its object
(`0xFAB..0xFB0`, instance = variant), saves the time (`TRN_saveTrainingStartTime`,
`trn_reward.c:101-106`), reads PStat `0xF6` (1 = slot machine) and, if the partner is Baby/In-
Training (`level < 3`), increments that stat's `upgrade*Counter`
(`trn_hp.c:45-64`). When finished `TRAINING_COMPLETE = 1`, which the script reads with
`isTrainingComplete` (`tamer.c:1305-1312`).

**Common flow** (e.g. `trn_hp.c:66-161`): tamer state 8, partner 10, camera to the point;
the partner walks to the equipment; if there is a slot machine a round is created and the reel starts
on its own on arrival (`TRN_startSlotSpin`); the minigame lasts **1200 ticks** (`0x4B0`) or until
△ is pressed (in Defense △ only advances the clock, the cycle completes,
`trn_def.c:121-123`); with the slot machine it ends as soon as there is a result `r ≥ 0`. Then
`TRN_award*TrainingGains(species, variant, r)` fills `STATS_GAINS`, opens the stats box
and advances the clock; when the box has added everything (`TRN_statGainsAreZero`) it waits 20 ticks,
the partner returns, `TRN_applyBaseStats` writes the stats and everything is cleaned up. Without the slot machine
`r = 10`.

**Minigame and base gain per type** (`trn_reward.c:151-592`, `trn2_reward.c:137-447`):

| Overlay | Type | Map (variant `b`) | What you see | Base gain | Tiredness / energy / happiness |
|---|---|---|---|---|---|
| TRN | HP | Green Gym 112 (0) | the equipment (map objects) goes up and down, dust clouds | HP +80, OFF +2 | 10 / 1 / 1 |
| TRN | MP | 112 (0) | still in front of the equipment, animated map objects (`trn_mp.c`) | MP +80, DEF +2 | 7 / 1 / 1 |
| TRN | OFF | 112 (0) | hits the equipment: per-species anim `TRN_TRAINING_ANIM_IDS`, impact on the given frame | OFF +8, SPD +2 | 9 / 1 / 1 |
| TRN | OFF | Gear Savanna 78 (6) | hits (variant with objects 0x27-0x2A) | HP +10, OFF +8 | 9 / 1 / 1 |
| TRN | DEF | 112 (0) | the equipment swings back and forth and it pushes it (10 phases, `trn_def.c:119-218`) | DEF +8, BRN +2 | 9 / 1 / 1 |
| TRN | SPD | 112 (0) / 78 (6) | runs laps; teleports when leaving the screen every 60 ticks | HP +10, SPD +8 | 8 / 1 / 1 |
| TRN | BRN | 112 (0) | the tamer teaches it (anim 9 every 30 ticks) | MP +10, BRN +8 | 6 / 1 / 1 |
| TRN | BRN | Misty Trees 119 (9) | the NPC (entity 2) teaches it | BRN +15 | 6 / 1 / 1 |
| TRN2 | HP | Beetle Land 107 (1) | the equipment goes up and down | HP +120 | 10 / 2 / 1 |
| TRN2 | HP | Ice Sanctuary 99 (3) | the equipment goes up and down | HP +120, DEF +2 | 10 / 2 / 2 |
| TRN2 | OFF | 107 (1) | hits the equipment | OFF +12 | 9 / 2 / 1 |
| TRN2 | DEF | Beetle Land 108 (1) | takes a hit every 30 ticks (anim 0x25) | DEF +12 | 9 / 2 / 1 |
| TRN2 | DEF | 99 (3) | withstands the falling object (40 u/tick up to 200) | DEF +12, SPD +2 | 9 / 2 / 2 |
| TRN2 | SPD | 108 (1) | runs | SPD +12 | 8 / 2 / 1 |
| TRN2 | MP | Trash Mountain 165 (8) | meditates (anim 0xC) | MP +150 | 7 / 1 / 4 |

**Formula** (`TRN_awardHpTrainingGains`, `trn_reward.c:151-201`, the same in all):
`gain = base × v / 10 × r / 10`, with `v` in tenths of
`TRN_calculateTrainingMultiplier(species, stat, b)` (`trn_reward.c:594-719`;
`trn2_hud.c:137-245` without the two ×1.2):

- affinity by `RAISE_DATA[species].trainingType` (`tt` 0..4): HP and DEF: tt0,1 → 1.0, tt2 →
  0.9, tt3 → 1.1, tt4 → 0.8; OFF and SPD: tt0,2 → 1.0, tt1 → 1.1, tt3 → 0.9, tt4 → 0.8; MP: tt0,3
  → 1.0, tt1 → 0.9, tt2 → 1.1, tt4 → 0.8. **Brains uses the MP table** (`trn_reward.c:510`);
- × level: Baby/In-Training 0.9, Rookie 1.0, Champion 1.1, Ultimate+ 1.2;
- TRN only and `b == 0` only (Green Gym): × 1.2 if trigger 219 (HP/DEF/SPD) or 251
  (OFF/MP/BRN) is set, and × 1.2 if that stat's `upgrade*Counter` ≥ 10 (that is, 10
  trainings of that stat while Baby); Brains checks the **MP** trigger and counter
  (`692-709`);
- × 1.1 with "Trn. manual" (item 33) in the bag;
- the partner's `trainBoostFlag` (bit 0x10 HP, 0x20 MP, 1 OFF, 2 DEF, 4 SPD, 8 BRN) replaces
  `× v/10` with `× v × trainBoostValue / 100` (Supercarrot and similar; applied in
  [partner.md](partner.md)). In TRN2 the bit is checked against the wrong stat in two places
  (HP+DEF uses 0x10 for the DEF part, DEF+SPD uses 2 for SPD, `trn2_reward.c:175`, `437`);
- `tiredness == 100` → **all gains are 1**; HP/MP are clamped to 999.

`TRN_advanceTrainingTime` (`trn_reward.c:721-804`; TRN2 `trn2_hud.c:247-322`): the clock jumps
to the start time + 1 h (`CURRENT_FRAME + 0x4B0`), tiredness/energy/happiness per the
table, tiredness ≥ 70 → happiness −3 and discipline −3, plus the hourly upkeep
(hunger −60, poop −6, life −1, `evoTimer`+1…).

**Brains extra** (`trn_reward.c:549-591`): if the total crosses 100/200/300/400/500 the
"new battle commands" box opens (texts `TRN_D_8008F0D8…`); if it crosses 150, 250, 350, 450,
550, 650, 750, 800, 850, 900, 950 or reaches 999, `TRN_tryLearnMove` (`811-875`): for each
specialty of the species it looks in `TRN_D_8008F14C` for the first technique the species can
learn and does not have, with weight `TRN_D_8008F184[position][specialty]` (0..25); it learns the one with
the highest weight if `weight > rand(100)`.

**Stats box** (`trn_hud.c:144-317`): 100 ticks of pause and then +1 per tick to the stat (or
all at once with ✕/△); caps 9999 HP/MP and 999 the rest.

**No other bonus.** Besides the slot machine there is no second attempt or separate bonus in the code;
the closest thing is the ×1.2 for 10 trainings as Baby.

### Training slot machine (`trn_slots.c`, `trn2_slots.c` identical)

With PStat `0xF6 == 1` the `setup` stores 1 in `MAIN_D_80135370` and the minigame creates the
round (`TRN_startSlotSession`, `371-380`) → box 3 (`387-416`): 3 reels of 13 symbols
(`TRN_D_8008F1AC`, `trn_hud.c:62-66`; 1..6 = HP, MP, OFF, DEF, SPD, BRN icons; 7 = "7"),
random starting position and a random `assist`: 0 (50 %), 1 (40 %), 2 (10 %)
(`TRN_D_8008F2CC`). ✕ starts (or `autoStart` when the partner arrives), each ✕ stops the
next reel; the symbol where it stops is adjusted by `TRN_chooseReelStop` (`262-369`):
`assist 0` **sabotages** (if the first two match and the third is going to land the same, it adds
1-2 steps); `assist 1` helps align reels 2 and 3 with the first if the symbol is
≤ 2 steps away, but never allows 7-7-7; `assist 2` looks for sevens ≤ 2 steps away. Prize (`175-191`):
no triple 5; triple 7 **100**; triple of the trained stat 40; other triple 20 → `r` → gain
×0.5 / ×10 / ×4 / ×2. The result is returned through `TRN_SLOT_MACHINE.result` and
`MAIN_D_801353A0[0]` (`trn_hud.c:327-350`).

### VS mode (VS)

**Registration.** At the in-game save machine (script command `0x30` → `openSaveMachine`,
`main_menu.c:4192-4204`): it needs a partner of level ≥ 3 (otherwise menu `0x46`) and to have
saved before (`MEMORY_CARD_ID/SLOT ≠ −1`, otherwise `0x44`). One of 40 slots is chosen (menu
`0x3D`) and `registerBattleData` copies base HP, MP, OFF, DEF, SPD, BRN, discipline, species,
name and the 3 equipped techniques (`4149-4164`) to `saves[0].battleRegistrationData[slot]`
(64 B, 40 slots = 0xA00 at the end of the save block) and writes the card.

**Loading** (main menu option 3, `main_menu.c:2334-2337`; states `0x32..0x38`,
`2998-3140`): for `VS_PLAYER_INDEX` 0 and 1, card 1 (`id 0`) and card 2 (`0x10`) are used; a
file is chosen, 0x2000 bytes are read, the checksum of `saves[0]` is validated and if it fails that of
`saves[1]`, and the 0xA00 bytes of registrations are copied to `VS__REGISTERED_DIGIMON_BUFFER[player×40]`
(`3085-3106`); error 8 if there is no registered Digimon. Then `loadDynamicLibrary(VS_REL)`
and `VS__initialize(p1, p2)`; on return, menu 0. Nothing is written to the cards.

**Selection** (`VS__initialize`, `vs_select.c:399-432`): (1) mode: 1 battle always; 3 if
both have ≥ 3 registered; 5 if ≥ 5 (`938-956`, `VS__BATTLE_COUNTS`); (2) stage 0..2
(`STDDAT T/B/E_TOGI`, music 0x1E/0x20/0x1F, `vs_scene.c:1100-1110`); (3) each player in their
half of the screen picks as many distinct Digimon as battles (`435-599`): controller 2 is the
upper half of `PadRead(1)` (`455-459`); ← → page of 4; △ □ ○ ✕ pick rows 1..4
(bits 0x10/0x80/0x20/0x40), ↑↓ change slot, L1/R1 scroll the card, START confirms;
any other button undoes the last one.

**Series** (`VS_initializeVS`, `vs_scene.c:1022-1079`): per battle it loads the two fighters
(entities 1 and 2), intro, `VS__combatMain`; result 1 = P1 wins, −1 = P2 wins, 2 = both
lose; `VS_STATE_WINS/LOSSES` and `VS_ROUND_WON/LOST` are recorded. At the end, the winner's scene
(most wins) or the "versus" scene if tied (`1516-1529`).

**Battle rules** (`vs_combat.c`): countdown 99 (`283`) that drops by 1 every 20 ticks
while nobody is dead (`vs_camera.c:805-819`; `VS_tickFrame` does `VSync(3)`, 20
ticks/s, `vs_main.c:1009`). End (`858-946`): one fighter in anim 0x2B (dead) → the other
wins; both → draw; time out → whoever has taken less damage wins
(`VS_STARTING_HP − HP`), equal → draw. Differences from normal combat (`vs_main.c`):
MP cost ×3 with a discount for Brains ≥ 700/800/900/999 of −5/−10/−15/−20 % (`728-738`,
`931-944`); hit = accuracy − accuracy/2 × (defender SPD − attacker SPD/10)/999, ×1.2
if the defender is in anim 0x21/0x22, 0 if blocking, 100 if stunned/flattened
(`293-344`); normal damage `Σtype/30 × (power + power×clamp(ATK−DEF, ±500)/500) × 90..110 %`,
finisher `(ATK+power) × Σtype/30 × 90..110 %`, cap 9999 (`346-394`); a blocked melee
attack does 10..30 % of the damage and charges the finisher (+3/50 defender, +4/50 attacker)
(`657-682`); poison 1-3 % HP every 100 ticks, confusion 200-300 ticks, stun 200-240
(`453-502`); support techniques (`257-291`).

### Ending (ENDI)

Command `0x34` loads texture, `ENDI_REL` and sounds 0x14 (`script_interp.c:1773-1776`); the
Digimon routine 6 sets tamer state 16 (`partner.c:1160-1164`) → `tamerTickEnding`
(`tamer.c:1627-1642`) → `ENDI_tickEnding(ENTITY_TABLE[0])` (`endi.c:396-421`): it makes the
**tamer** model semi-transparent (`104-146`) and adds object `0x812` (`148-207`): phase 0
(ticks 0-60) fades the CLUT to black and releases one particle per tick at a bone; phase 1
(60-80) scales 1.0 → 0.6 (tick 78) → 1.5 (tick 80), sound (8,1); phase 2 the 80 particles are
released and rise with velocity −450 (+20/tick) until they slow down; phase 3 stops sound and particles,
`frame = −1` → `SOME_SCRIPT_SYNC_BIT = 1` and the script continues (the "game clear" save is
command `0x36`). Particles with random colour 60..129 and size 15..29 (`386-392`).

### Machinedramon's appearance (EAB)

Identification: it is called by `tamerTickMachinedramonSpawn` (tamer state 18, `tamer.c:1663-1677`)
on `ENTITY_TABLE[2]`. Command `0x33` (`script_interp.c:1765-1770`): loads the ring TMD
into `BOSS_EFE_TMD_BUFFER`, `EAB_REL`, VBALL 5/0x73 and sounds 0x15. Command `0x28`:
`EAB_startBuildup(script entity 5)` (`eab.c:649-667`): hides the entity and launches a
ring that expands every 6 ticks (`187-274`), sound (8,0). Digimon routine 8 → state 18
→ `EAB_tick` (`670-710`): 9 EFE flashes at fixed positions and object `0x60C`
(`349-460`): tick 45 white flash; tick 50 the boss appears (anim 0x21), the other
entities and the map layer are hidden, sound (8,2); ticks 50-320 appearance rings, flash
fade until 82, green particles (squares that grow for 86 ticks) with an 18-tick pattern,
anim 0x33 at tick 210, the camera orbits 180° around the boss closing in from 3500 to
3000 u and descending from 600 to 50; tick 320 restores camera, map and entities, sound (8,3);
rings until 330 and end at 340 (`frame = −1` → sync).

### Title and opening

None of these overlays is involved in USA: `VS_playDemo` and `VS_initializeTrialBattle`
(VS demo on the title screen) only exist under `JP_TRIAL`/`JP_BOMBOM` (`main.c:3357-3365`,
`main_menu.c:3381-3416`, `vs_demo.c`). The opening is the video player (`MOV`).

## Useful writes

Raw memory writes for testing these modes from a debugger or emulator ([../developing.md](../developing.md));
little-endian.

| Goal | Write | Notes |
|---|---|---|
| fishing | trigger 46 (Amazing Rod) or 45 (Old Rod) and some food in the bag, then the triangle menu on maps 6/8 | setting `TAMER_STATE = 11` directly loads no rod (`initializeFishing` is skipped) |
| a fish that does not fight | `hooked.powerLeft` (`0x8007B4A8`) = 0 during the fight | it never runs; tension only rises while ✕ is held, so reel in with pulses |
| unbreakable line | `tension.limit` (`0x8007B50C`) = `0x7FFFFFFF` at the start of the fight | |
| Seadramon cutscene | with the rod out (`0x8007B41C` ≠ 0), `catchComplete` (`0x8007D960`) = 1 | `FISH_tamerTick` returns 1 and runs script section `0x4E4` |
| huge fish | size i16 at `0x8007B466` = 300 after the pull | |
| win curling | in state 0x10 (`0x80135244`), player points (`0x8005B5A0`) = 10 and opponent points (`0x8005B904`) = 0; or state = 0x14 to finish with the current score | opponent: PStat 0x7A (0 Penguinmon, 1 MetalMamemon) before the script calls routine 1 |
| maximum training gain (TRN) | in state 2/3, `0x80135370` = 1 and `0x801353A0` = 100 (result 100 → ×10, ends at once); TRN2: `0x801353BC`, `0x801353E0` | simpler, both: with the stats box open, 999 in each `STATS_GAINS` (`0x8013D468`, 6 × i16); the box clamps to the caps |
| slot machine | PStat `0xF6` = 1 before script command `0x07`; `assist` (`0x8008F3CA`) = 2 when the box opens favours sevens | |
| VS | `VS_TIMER` (`0x80135288`) = 1 ends a battle in one second; `VS_STATE_WINS` (`0x80135258`) = 5 before the last intro forces P1's winner scene; `0x80134F59` = 2 before confirming picks 5 battles / stage 2 | two memory cards with registrations are needed |
| ending, Machinedramon | only through their script commands (`0x34` + routine 6; `0x33` + `0x28` + routine 8) | the overlay must be loaded before `TAMER_STATE` 16/18 |

## Notes

- Which scripts set PStat `0xF6` (slot machine) and `0x7A` (curling opponent), and the prize the Freezeland script
  gives for PStat `0x79` = 1 and 2, are in `DG.SCN`, not in the overlays.
- `FISH_RECORD_SIZE` (`0x80154F80`) is not referenced by the save code in `main_menu.c`.
- `FISH_REEL_TARGET` is the zero vector: a reeled-in Seadramon swims to the map origin.
- `ENDI` only dissolves the tamer; the rest of the ending is script and video (`MOV`).
- The title-screen VS demo (`vs_demo.c`) is compiled only for the Japanese trial builds.
- `TRN2_calculateTrainingMultiplier` still contains `result += t / 60` with `t` uninitialised
  (`trn2_hud.c:235-242`); it has no effect because `result` is reassigned afterwards.
