# Engine patches by feature

How the C patch series (`mods/patches/`, applied to the decompilation by `tools/mods.sh prepare int`) hooks into the
engine, grouped by feature: what each feature changes, which functions it hooks and which limits it keeps. Patch
numbers refer to `mods/patches/NNNN-*.patch`; several features were developed apart and arrive in the series as one
merge patch. Functions and files are those of the patched `decomp/src/`.

Features with their own page elsewhere: OPTIONS ([../mods/options.md](../mods/options.md)), fonts
([../mods/font.md](../mods/font.md)), language ([../mods/language.md](../mods/language.md)), species and DIGI.DAT
([../mods/species.md](../mods/species.md), [imported-species.md](imported-species.md)), sound
([../mods/sound.md](../mods/sound.md)), 60 fps ([frame-rate.md](frame-rate.md)), memory ([memory.md](memory.md)), ids
([ids.md](ids.md)), saves ([save-format.md](save-format.md)), GCC fixes ([compiler.md](compiler.md)), rules as data
([../mods/data-sources.md](../mods/data-sources.md), [../mods/balance.md](../mods/balance.md)).

## Number caps (merge 0059)

| Limit | Original | Patched | Constant (`include/dw/caps.h`) |
|---|---|---|---|
| Offense, Defense, Speed, Brains | 999 | 9999 | `STAT_CAP` (`OLD_STAT_CAP` 999) |
| Max HP, max MP | 9999 | 30000 | `HPMP_CAP` (`OLD_HPMP_CAP` 9999) |
| One hit, `hpDamageBuffer` | 9999 | 30000 | `DAMAGE_CAP` |
| One training gain | 999 | 9999 | |

Every stat stays `int16_t` everywhere (`Stats`, `COMBAT_DATA`, `INITIAL_COMBAT_STATS`, `STATS_GAINS`, `DIGIMON_DATA`,
the evolution gains, the tournament tables, the v1 save), so no layout changes and saves load both ways. 30000 leaves room
in an int16 for a sum before its clamp. Larger values would mean 32-bit `Stats` in every entity and overlay.

What changes:

- **Clamps** (`CAP_OF_STAT_INDEX`): `addWithLimit`, the script's stat addition and its limit array, items, buff disks and
  battle buffs, `EVL_scaleBaseStats`/`EVL_clampBaseStats`, training gains and totals, post-battle totals, damage and
  `hpDamageBuffer` in BTL and STD (`CAPS_ADD_DAMAGE`), the 9000-step `damageTick`. Medal 7 and the Brains MP discount test
  with `>=`; the 999-Brains training technique triggers on crossing; the finisher goal and buff priority stay sane past
  999; full heals fill a longer bar (`CAPS_FULL_HEAL`).
- **Display**: `renderNumber`, `drawEntityText`, `BTL_/STD_renderNumber`, the tournament intro and time-out digits grow a
  fifth digit only when needed and keep their right edge (`CAPS_DIGITS`, `CAPS_SHIFT`); the battle HUD packs five digits
  6 px apart; stat bars are full at the old limit; the tournament intro counts big stats up in 50 ticks.
- **Kept on purpose**: the ±500 clamp on Offense minus Defense (normal hits stay small, finishers scale with Offense),
  the `/999` in the hit chance (Speed far past 999 makes a fighter nearly unhittable; patch 0110 limits the speed
  difference to 999), VS mode's own clamp of an imported partner, and the tournament rivals' generation.

`renderNumber`'s wider boxes apply to every caller: a value that did not fit its box now shows all its digits.

## Memory reclaim (merge 0060, then 0092-0098, 0159-0160, 0198, 0206, 0208-0211)

Three changes come with the merge:

- **Streamed map background.** Only the `.TFS` header and a ring of tiles stay resident instead of the whole background;
  rows are read in one go, prefetched by distance to the window edges, with CD arbitration against the file queue.
- **Trimmed NPC models.** NPC models drop the animation slots NPCs never play (`tools/npcanims.py` generates
  `src/main/npc_anim_keep.c` from the scripts); a dropped slot points to a one-frame stub, and `MOD_NPC_STUB_HITS` counts
  plays of it. The table must be regenerated when scripts start playing new NPC animations.
- **Smaller stack** with a canary at its limit (`MOD_STACK_GUARD_HITS`); patch 0208 sets it to 16 KB.

The ring is only reopened in the world (`ringMayReopen`, patch 0160): a battle owns the load area (the EFE engine's slot
table sits at `GENERAL_BUFFER`), and a tile requested during a fight, for example by the camera lift of a tall partner,
would land on that table. Outside the world a cell keeps what VRAM holds and `MOD_TFS_STATS.refused` counts the refusal;
`modCamBattleStep` keeps the battle camera inside the 4x3 tile window VRAM holds. Patch 0206 makes a synchronous read
wait for the file queue's read in flight (a second `CdRead` aborts the first) and keeps the ring from reopening while the
queue holds a request. Layouts, budgets and the rest of the series' reclaims are in [memory.md](memory.md).

## Sound limits (merge 0061)

Removes the engine limits on music, voices and sound memory while the original files still work unchanged:

1. The chunks of `FAALL`/`VBALL`/`VLALL`/`ESALL` are found through an index sector at the head of each file (magic
   `SIDX`, `{u16 sector, u16 sectors}` per chunk) instead of fixed strides and `MAP_SOUND_PARA`. Files without the index
   get the original layout, rebuilt from the file sizes.
2. Music fonts 34..254 (`playMusic` takes the index's count); `SEQ_BUFFER_SIZE` 0x8000 (was 0x5800), the SEQ copy
   checked.
3. SPU RAM allocated per load (`spuPlaceBank`): bank 8 top-aligned under the reverb area, the others at their original
   slot when free, else the lowest free space; the map region or an oversized font is evicted when a load needs room; the
   VAB header copy is checked; `startSound` refuses unloaded banks.

The formats and `tools/sound.py` commands are in [../mods/sound.md](../mods/sound.md) (section 8).

## NPC Digimon as partners (merges 0052-0056, restoration 0281)

Eleven Digimon that were only enemies or NPCs became partners: MasterTyrannomon (124), Cherrymon (121), King of Sukamon
(120), Icemon (94), Meteormon (113), WaruMonzaemon (70), Myotismon (66), ShogunGekomon (119), Machinedramon (115),
Analogman (116) and Jijimon (117). Their data now lives in their species files
([../mods/species.md](../mods/species.md)); the engine hooks are:

- **Per-partner rows** at the species' index of the partner tables: `RAISE_DATA` (the status-screen view is the source
  partner's point pushed along the camera ray by the height ratio), `EVOLUTION_REQS`, `EVOLUTION_STATS_GAINS`,
  `ITEM_TAKE_DISTANCE`, the TRN/TRN2 animation ids, the VLALL voice set, and where missing `CONDITION_FX_OFFSETS`, the
  aura projectile rows and `DIGIMON_VBALL_SOUND_ID`. `DIGIMON_DATA` gets their level, specialties and techniques.
- **Evolution paths.** A Champion's `EVOLUTION_PATHS` row gets the new Ultimate, each with a requirement the
  Champion's other targets do not ask for (care mistakes or a weight band), so they do not compete. Panjyamon,
  Gigadramon and MetalEtemon, which the original reaches only by items, also get a natural path. An Ultimate evolving
  again (Megadramon or Gigadramon into Machinedramon, 48 hours after the evolution) is asked by `tickConditions` through
  an Ultimate-target hook; since patches 0117-0119 every such rule is data (`MOD_EVO_TIMING`, `MOD_EVO_RULES`,
  `MOD_EVO_ITEMS`, from `content/tables/evolution-rules.json`). `tickConditions` no longer reads `EVOLUTION_PATHS` past
  its end for a Champion without a row.
- **Partner-only model files** (`PARTNER_MODEL_FILES` in `model.c`). For Machinedramon, Analogman and Jijimon the NPC's
  own MMD stays byte for byte (their screens have little heap), and a second file (`MUGP.MMD`, `ANLP.MMD`, `JIJP.MMD`,
  added at the disc root and to `FILE_OFFSET_TABLE`) is loaded when that species is the partner: `loadMMD` and
  `loadMMDAsync` with model class 3 (Continue, evolution, reincarnation, VS) use the table's name. The asynchronous read
  goes through the file table, because a path search looks in `CHDAT\MMDn\`. Without the file on the disc the partner
  falls back to the NPC model. Other partner generators still replace their native CHDAT output. Patch 0281
  routes field NPC requests for types 119–124 and 126 to disc-derived records
  462–468, preserving the original NPC model and rows independently of those
  partner files. The helper is used by the shared 8/16-bit script load/set/unload
  paths and the field loader; map identities remain unchanged. Tournament
  loads bypass the field mapping. NPC speaker names use the original identity.
  The main executable grows by 384 bytes (`main_BSS_END` 0x801ce880 →
  0x801cea00, same eight padded banks); species caches and bitsets retain their
  fixed 1024-id capacity.
- **Technique effect origins.** A technique's EFE table holds launch points per attacker type; a type missing from it
  would play the clip with no hit. A donor table maps another type's row onto the partner's bones, bone 0 scaled by the
  height ratio and other bones through an explicit map. Since patch 0116 the table is data (`MOD_DONOR_ENTRIES`,
  `MOD_DONOR_ORIGINS`, `MOD_DONOR_BONES`, written by `tools/balance.py` from `content/tables/effect-donors.json`).
  A species carried by its DIGI.DAT record gets a default origin for every technique (patch 0106).
- **Raised flags.** Original partners use trigger 0x200 + type as their raised flag. Where that trigger already has
  another meaning (types in the 63..114 range collide with script triggers), `RAISED_TRIGGER(type)` in `ids.h` maps the
  species to a free trigger, used by `setDigimonRaised`/`hasDigimonRaised`. Species without a trigger use the saved
  bitsets (patch 0065, [save-format.md](save-format.md)).
- **Lab menu** (a development tool in the pause screen): the evolve list includes the new partners; its count follows
  the array.

Known limits: species outside the seven restored twins retain their existing
row-sharing behavior. The tournament intro's name tables do not cover all added
partner types. NPC twins contain their original scene animations, not partner
combat animations.

## Portraits (0066-0068, 0170, 0176, 0178-0180, 0213, 0219)

Where the game draws a Digimon icon:

| Screen | Sheet (VRAM) | Index | Code |
|---|---|---|---|
| Tournament bracket (`STD_REL`) | `STDDAT/STDTIM.BIN`, two 256x256 4 bpp pages at x 896 and 960; CLUT rows at (288, 480) and (304, 480) | tile = type - 1, 8 tiles of 32x32 per row, 64 per page; CLUT row `STD_DIGIMON_SPRITE_CLUT[tile]` (0..6, rows 7..15 empty); 4 frames of 16x16 (idle, idle 2, attack, hurt) | `STD_renderBracketDigimon` |
| VS lists and line-up (`VS_REL`) | `STDDAT/16TAISEN.TIM`, one page at (896, 0) | tile = type - 3 (types 3..66); CLUT row `DIGIMON_SPRITE_CLUT[type]`; idle and idle 2 | `VS__renderSelectDigimonPlayer`, `vs_scene.c` |
| Evolution chart | `ETCDAT/SBOY.TIM` at (512, 256), CLUT at (112, 488) | `EVO_CHART_BOXES[type - 1]` (u, v, CLUT) for the 61 chart species; normal and highlighted 16x16 | `renderEvoChartView`, `renderEvoChartDetail` |
| Status menu | none: the 3D model is drawn into the box | | `renderDigiviceEntity` |

Without the patches a species of 180 or more drew nothing in the bracket, another Digimon's tile in VS (the tile index
wraps) and an empty chart box.

**The icon.** `tools/portraits.py` renders one per species from its model (rest pose, three-quarter view facing left,
box-filtered to 14x14, quantised to 14 colours plus a dark outline), four frames in a 32x32 tile like the originals:
idle, idle shifted up a pixel, attack (a pixel forward), hurt. An icon is 0x220 bytes: a 16-colour CLUT and the 32x32
4 bpp image. A species without one draws a fallback icon. `tools/species.py build` stores them in DIGI.DAT, three to a
sector; `SpeciesRecord.portrait` (0x1C0) and `SpeciesHeader.fallbackPortrait` (0x18) hold `sector | slot << 24`; the
header sector also lists each partner species' level for the tournament.

**Engine side** (`mod_species.c`): `getSpeciesPortrait`, `loadSpeciesPortrait` (uploads 16 or 32 rows and the CLUT with
one synchronous sector read), `getSpeciesPartnersByLevel`.

- **Bracket.** `STD_preparePortraits` (from `STD_setupParticipants`, participants now `uint16_t`) uploads each new
  species' icon over the tile of a type not in this bracket (tiles 62 down of page 1) with CLUT row 8 + slot. Its
  projectile icon is the one of the original it borrows techniques from.
- **VS.** `VS_choosePortraitTiles` lists up to 12 tiles no registered fighter uses; `VS_portraitFor` assigns a tile and
  CLUT row (5..16) and loads the icon on first use. `RegisteredDigimon.digimonId` is a byte: a species of 256 or more is
  registered as the original it is based on.
- **Chart detail** (0067): icons beyond the chart's 61 are loaded when the view opens or changes
  (`loadChartPortraits`) into the battle-effect VRAM (x 576..703, y 256..271), free outside battle. The view gets a
  cursor: the D-pad moves between the "from" and "to" boxes, confirm opens a raised species, cancel goes back a level.
- **Chart overview** (0170, 0178, 0213, 0219): every partner species of the build, one tab per level (L1/R1), pages of
  boxes in the level's colour, scrolling. `tools/species.py` writes the list into DIGI.DAT's chart block
  (`SpeciesHeader.chartSector`: tab counts and ids, then a 16x16 idle frame and CLUT per species, 12 to a sector); a page
  is read when shown (`chartLoadPage`) into battle-effect VRAM. The tabs fit any font.
- **City** (0277): the fifth Player tab shares the chart's 14 by 7 grid,
  cursor, scrolling, text rows and icon VRAM. Its separate one-tab block uses a
  sector pointer at header byte `0x38`, between the record-original bitmap and
  partner levels. The v2 record/header fields keep their existing offsets;
  older archives have a zero pointer. IDs carry a hidden-until-owned bit at
  `0x8000`. The block includes generated idle icons for every resident beyond
  the sheet, including non-partners. Missing icons use luminance CLUTs made on
  entry: zero remains transparent and every nonzero colour remains nonzero.
  City, chart and card transitions reload their shared VRAM on entry.
- **Evolution requirements** (0176, 0179, 0180): on a "to" box the detail view shows that evolution's requirements;
  in the partner's own tree it adds the partner's values, met/unmet marks and a points count, and lights the reachable
  lines. Marks come from `evoRequirementsMet` (`evolution.c`), the same function `calculateRequirementScore` scores with,
  so the card and the game agree. OPTIONS' EVOLUTION GUIDE turns it off.
- **Tournaments** (0068): `startTournament` (`utils2.c`) widens opponents to `uint16_t` and adds DIGI.DAT partner species
  whose level lies in the cup's list (at most half the pool, the player's species excluded; never Megas). An opponent's
  stats depend on the cup and level only (`STD_initializeOpponent`). For registration (`tournamentCheckEligible`,
  `tournamentCheckFair`, `dget.c`) a new species takes the place of the originals of its level: a list with nine or more
  originals of that level holds it, a themed cup holds it only when it holds the original it borrows techniques from.
  `updateTournamentRegistration` compares with the registered byte wrapped.

Also fixed on the way: `getConditionFxOffset` returned a 2-aligned pointer into a cached record, and the GTE's `LWC2`
load of an `SVECTOR` needs 4-byte alignment (an address error the first time an imported partner's bubble showed); it
copies to an aligned vector.

## Status bubbles (0069-0077, 0155-0156, 0158)

The original shows one condition bubble at a time over the partner (`addConditionBubble`, `renderConditionBubble`,
`tickConditionBubble` in `bubble.c`, driven by `handleConditionBubble` in `partner_impl.c`), replaced every 50 ticks,
following the head bone (`translateConditionFXToEntity`). The patched game shows every active condition at once. The lab
menu's option (0070) switches back to the classic bubble.

- **Conditions** (`PARTNER_PARA.condition`), in display order: hungry 0x04, poopy 0x08, sleepy 0x01, tired 0x02, sick
  0x40, injured 0x20. Unhappy (0x10) is the butterfly and has no bubble. Shown while the partner is idle
  (`PARTNER_STATE` 1 or 0xA) in the world (`GAME_STATE` 0) outside menus.
- **Layout** (0155-0156): each bubble at 0.8 of the original's size (`RING_SIZE` 205/256, circle and icon); one or two in
  one row centred on the anchor, from three on two rows (the first half on top, `RING_ROW` 18 texels higher,
  `RING_COL` 22 texels between centres); the tail only on a bubble on its own (`RING_TAIL`); the bottom row drawn on top.
  The anchor is the partner's root position plus its species height and the original bob, not a bone, so the cluster
  does not move with animations.
- **Object** (0x819, `bubble.c`): one persistent world object with a state machine ticked at 20 Hz. Each condition rests
  in a slot, encoded `(x + 128) << 8 | (y + 128)` in texels (`| RING_TAIL` 0x20000; `RING_NONE` 0x10000). At rest each
  tick compares the wanted layout with the resting one; a difference starts one step of `RING_STEP_TICKS` (10 ticks,
  0.5 s) that is never restarted or cancelled: an appearing condition grows in its slot, a leaving one shrinks, the
  others slide. Slots are reassigned only after the step's last frame; changes meanwhile are picked up at rest.
- **Drawing** happens per render pass: the step phase is `((T - 1) * 4096 + MOD_RENDER_ALPHA) / 10`, eased with
  3p² - 2p³, so it is smooth at 60 fps (the sub-tick fraction comes from `modPresent`, [frame-rate.md](frame-rate.md)).
  A bubble is its circle (rows 0-25 of `CONDITION_SPRITES[11]`) plus the tail (rows 26-31) scaled from half to full
  height, so a full-size bubble looks exactly like the original. The icon scales with its own linear map and keeps its
  pivot centred. `MOD_RING_SHOWN` records what the last pass drew, for checking tools.
- **X badge** (0158): while confirm in front of the partner would open the care menu (`mod_feed.c` sets
  `MOD_FEED_HINT` for that tick), the dialogue box's X button (from the UI texture page, three frames) is drawn beside
  the bottom row's right edge, or where the bubbles would be when there are none, growing and shrinking over 0.2 s. Not
  with the classic bubble.

## Less waiting (0184-0189, 0196-0198, 0200, 0204, 0223)

Speed-ups that give no advantage the game did not have. The battle shows its switch on a small plate in the bottom right
corner (`modPlate`, `src/main/mod_qol.c`, in the digital clock's style).

### Battle x2

R2 switches x1 / x2 in every battle: field (BTL), arena and tournaments (STD), VS. Kept until reset, not saved.

- The game clock and care counters do not move in a battle (`stopGameTime`; a flat `MOD_CARE_BATTLE_TIME` is added at
  the end by `advanceBattleTime`), and the finisher gauge fills per action (`BTL_addFinisherProgress`: an attack +4 % of
  the goal, a block +6 % to the defender and +8 % to the attacker), so x2 changes neither.
- What x2 shortens is reaction time: a finisher charge press counts twice (`BTL_tickFinisherChargeup`, STD alike); the
  defeat countdown (`DEATH_COUNTDOWN`) and the item menu (open or with an item in hand) hold the fight at x1
  (`BTL_modSpeedHeld`). A timed field battle (patch 0172, pstat 242) counts fight ticks. Play time (`tickPlaytime`)
  counts real time, skipping the second tick of each fast pair (`MOD_REAL_TICK`).
- **Timing** (`modTickStart`, `modPresent`, `main.c`): the battle arms `MOD_BATTLE_FAST_TICK` before each tick
  (`BTL_modSpeedBeforeTick` from `BTL_battleTickFrame`). Fast ticks run in pairs over 3 refreshes, 40 ticks a second;
  the first of a pair is due 2 refreshes after the pair begins and its frame is shown; the second renders (render
  functions advance state such as effect scripts and gauge pulses) but its frame is dropped and it waits for no
  refresh. Each fast tick is due from when the previous one was due, not when it ended. Dropping the second frame is
  needed because a fight's tick plus render takes slightly more than a refresh; showing both gives only 30 ticks a
  second (fixed by patch 0187). At x2 the screen shows 20 frames a second whatever the frame rate.
- The loading phase before a battle (`GAME_STATE` 3) waits for the disc and is not faster.
- **Arena, tournaments, VS** (0196): the switch, its plate (object 0x19B) and the arming are resident (`modSpeedInput`,
  `modSpeedPlateAdd`, `modSpeedBeforeTick`), shared by the overlays. STD and VS arm a tick only while the plate is up
  (`MOD_SPEED_FIGHT`): STD from the match intro to its end (`STD_runMatch`), VS in the fight loop (`VS__combatMain`). VS
  reads R2 from the first pad only.

### Evolution skip

- `getEvoSequenceState` (`partner.c`, the one way into the scene) sets `MOD_EVO_SKIP` to 1 for every evolution; START
  sets it to 2. It arms (3) only once START has been released and no pause is open, so the START that closed a pause
  does not skip at once; a pause disarms it.
- The hint (`modEvoSkipInput`, `modSkipHintDraw`, `modSkipPlate`) is the string `main.QOL_STR_SKIP_EVOLUTION` drawn into
  row 0xD8 of the text area and shown in the bottom right corner, outlined by drawing it eight times in black around
  itself. The scene's own loads and a pause reach that row, so it is redrawn when the skip arms, on each state change and
  every 16 ticks.
- During loading (`tickEvoSequenceLoading`, two waits of 55 ticks) a skip ends the waits; the overlay is still waited
  for. In the EVL overlay, `EVL_modSkipToEnd` jumps from any frame before state 3 to the end of state 2, keeping what
  the evolution needs (the camera saved for state 3, the new model loaded, `EVL_applyEvolution` once,
  `waitForSoundBufferLoading`) and dropping shards, sparks and particles and the scene's sounds. State 3 then restores
  camera, palettes, entities, map and music as usual.

### Training x5

`src/trn/trn_block.h`, included by both gym overlays (TRN `trn_reward.c`, TRN2 `trn2_hud.c`), wraps each award call:
`TRN_modBlockBegin()`, then the gym's award function in a loop while `TRN_modBlockNext()`.

- **Menu**: every gym's training menu has four rows: normal training, normal training x5, Bonus Try, and leave. A tamer's
  or NPC's menu has room for three options under the speaker row, so these menus are the narrator's
  (`scriptShowSelection`: speaker 0xFF has no name row). The x5 row sets the Bonus Try flag (pstat 246) to 2;
  `modBlockArm` turns that into a normal session in a block. Its words are `qol.training_x5` in `text/en.json`.
- **A block** plays the first session's animation (triangle still cuts it), then runs the award once per session, each
  with its hour of game time and care costs (`TRN_advanceTrainingTime`) and its gains applied before the next (so a
  Brains mark is crossed as it would be). The stats box stays shut during the block (`TRN_MOD_QUIET`) and then opens once
  with the total.
- **Stopping** (`modTrainStopReason`, resident in `mod_qol.c`), after the session that left, in priority order: the gym's
  own box open (a technique or new orders), end of life, due to digivolve (`evoTimer` reached `MOD_EVO_TIMING[level]`),
  hurt or sick, hungry, needing the toilet, sleepy time inside the session, tired (past the gym's `MOD_TR_TIRED_AT`). A
  box under the stats says how many sessions ran and why it stopped (`TRN_BLOCK_*` texts).
- **Space**: the TRN overlay must end below `OVL_TRN_MAX_END` (0x7000 bytes); with the block it is close to that, which
  is why the stop check is resident and `trn_reward.c`'s small variables live in main's `.sbss`.

Patch 0198 is a prerequisite found here: an overlay loaded in the background (`loadDynamicLibrary`, asynchronous) is
found through `FILE_OFFSET_TABLE` like `readFile`, because `CdSearchFile` only sees the first sector of the root
directory, which a disc with many added files outgrows.

### How many (0223)

An amount box (`modAmountStep`, `script_common.c`): up/down change the amount by one, by ten with the alternate button,
and wrap; square jumps to the most; confirm takes it, cancel takes nothing. The shop's own amount boxes follow the same
rule.

- **Mojyamon trades** (`openMojyamonShop`, `script_menu.c`): the box replaces the yes/no, showing the item given and the
  item got with icons. The most is what the player has of the given item, limited by the got item's stack room (99). The
  given items are removed first, so a trade that empties a stack works with a full inventory; if the got items do not
  fit, the given ones come back.
- **Card packs** (`rollCardPack`): the price is `cardPack.price` in `content/tables/economy.json`
  (`MOD_ECON_PACK_PRICE`), charged by the C code, not the script. Several packs open at once into a list of the cards
  received, rarest first, with counts and a mark for cards new to the collection; the card under the cursor is shown at
  half size, its picture read from `CARD.ALL` into the end of `TEXTURE_BUFFER` (the start holds the list's arrays) and
  VRAM (576, 256). Cards are added up to `cards.maxCopies`.

## Quick battle start (0233-0234, 0236, 0238-0239)

With OPTIONS' QUICK BATTLE START on (`MOD_OPT_QUICK_BATTLE`, `mod_options.c`), a wild or scripted field battle starts in the
tick it is triggered: HUD and fighters at once, the battle music about 0.3 s later. Tournaments and VS keep their intros;
OFF is the original start unchanged. The original start spent several seconds loading (`loadBattleData`: music font,
`BTL_REL`, `SB.VHB`, voices, effects) and about 2.8 s in the intro (`BTL_handleBattleIntro`). Most of the load was not the
disc: each file queue request advanced one step per 20 Hz tick.

- **Intro** (`BTL_quickBattleIntro`, `battle_setup.c`): the BATTLE letters gather, flash and burst over the running fight
  (`BTL_tickQuickStartText`, ticked by `BTL_battleMain`, removed by `BTL_endQuickStartText`); the tamer's walk back is the
  intro loop's own logic run without rendering, so he ends where the intro would leave him.
- **Who joins, who runs** (0236): the flee bubbles appear over the running fight for 40 ticks each (`renderFleeBubble`);
  Digimon that do not join run off while the fight goes on (`modBattleFleeTick`, from `tamerTickBattle`) and are
  removed off screen or after 0xC8 ticks. `modBattleLoadFinish` removes any left at the end.
- **Queue pump** (`MOD_LOAD_PUMP`, `modWaitVblank`): while a battle loads, each vblank wait in `modPresent` steps the file
  queue repeatedly, so a request starts as soon as the previous ends.
- **`BTL_REL` read ahead** (`modBtlPreloadTick`, `btl.c`, from `tamerTickOverworld` while the tamer walks): the overlay is
  read into its own address (`OVL_BTL_BASE` .. `btl_END`), which is world scratch on every screen that keeps no overlay
  there. Any `loadDynamicLibrary` of another overlay (`modBtlPreloadDrop`) lets a read in flight land, drops the copy and
  blocks the read ahead until the next screen (`MOD_BTL_PRELOAD_BLOCKED`, cleared in the map set-up before the fishing,
  curling, shop and arena checks). The battle takes the copy only if its checksum is unchanged (`modBtlPreloadTake`),
  else it reads `BTL_REL` as before. The largest `.MAP` ends just below `OVL_BTL_BASE`.
- **The rest loads during the fight** (`modLoadBattleDataQuick`, `modBattleLoadStep`): the battle needs only `BTL_REL`.
  The music font (`modPlayMusicAsync`, `sound_async.c`: the FAALL chunk through the queue, the sequence copied and started
  in the callback), `SB.VHB` and the enemies' VBALL voices are queued; then, from `tamerTickBattle`, when the queue is
  empty, `BTL_initializeEFEEngine` and the technique effects (`BTL_loadMoveEFE`); when those are in, the fighters'
  `effectSlot`s. **This order cannot change**: the sound banks are staged at `GENERAL_BUFFER`, where the EFE engine's slot
  table and heap then live, so the engine starts only after the last bank is in SPU RAM.
- **Gates** while `MOD_BATTLE_LOADING`: `BTL_startQueuedMove` returns (the fighter is asked again next tick; it walks and
  positions itself meanwhile, the AI is untouched), and the item menu does not open. `effectSlot`s are -1 until filled.
  `modBattleLoadFinish` (called before `BTL_deinitializeCombat`) completes whatever is still loading, so fleeing in the
  first second cleans up like the original.

Techniques are ready within about a second of contact when `BTL_REL` was read ahead.

## Optional partner name (0202, 0207)

- In a new game, after the tamer's name, a yes/no question (MAPHEAD section 1238, lines 0x21 and 0x22, added by
  `story/base/maphead/hooks.py` with their words in `text/en.json`, `name.*`; shown by `newGameStateMachine` states
  0x20-0x22 in `script_menu.c`) decides whether the partner is named. Yes continues as the original; no gives the
  partner its species' name.
- On the partner's name keyboard (new game, the rename at Jijimon's, after a rebirth: `naming_and_intro` with pstat 254
  = 3) OK works on an empty name. The tamer's name is still required.
- An unnamed partner's `PARTNER_ENTITY.name` holds its species' name, so dialogue, status, save and registration read it
  as any name and the save format does not change. A typed name is full-width (two bytes a letter) and a species name is
  ASCII, so they are never equal: a name equal to the species' is always an unnamed partner, in a loaded save too.
  `modPartnerNameFollow(from, to)` (`partner_impl.c`), called by `EVL_applyEvolution`, a rebirth, the vanilla swap and
  the lab's roster switch, writes the new species' name when the old name was the old species'. A rename starts empty
  for an unnamed partner.
- Room made for a long species name: the status screen's name field copies it as wide as the species row
  (`modStatusNameWidth`), the battle registration shows it without the species in brackets, and the 14-byte VS record
  (`rec->name`) cuts it at 13 letters.

## Other patches at a glance

| Patches | Feature | Reference |
|---|---|---|
| 0005-0012, 0048, 0063, 0070, 0085, 0148-0149, 0157, 0165 | lab menu (pause screen, a development tool), roster switch, screen jump | [../developing.md](../developing.md) |
| 0013-0019, 0065, 0082, 0146-0147, 0209-0210 | ids widened | [ids.md](ids.md) |
| 0014, 0112, 0138, 0145, 0231 | script engine | [scripts.md](scripts.md), [../mods/scripts.md](../mods/scripts.md) |
| 0024-0025, 0086-0089, 0094-0095, 0097, 0099-0105, 0108-0109, 0175, 0177 | fonts, long names, layout | [../mods/font.md](../mods/font.md) |
| 0026-0049, 0074, 0080, 0173-0174 | 60 fps | [frame-rate.md](frame-rate.md) |
| 0081, 0084, 0106, 0116-0137, 0139-0143, 0229-0230, 0235 | rules and tables as data | [../mods/data-sources.md](../mods/data-sources.md), [../mods/balance.md](../mods/balance.md) |
| 0090, 0183, 0190-0191, 0203 | text bank and language | [text-sources.md](text-sources.md), [../mods/language.md](../mods/language.md) |
| 0092-0093, 0096, 0114-0115, 0129, 0182, 0193, 0205 | saves | [save-format.md](save-format.md) |
| 0150-0155 | care menu (confirm in front of the partner) | [partner.md](partner.md) |
| 0162-0164, 0166, 0218, 0220-0222 | status bars, digital clock, triangle menu | [items-and-menus.md](items-and-menus.md) |
| 0167, 0169, 0180-0181, 0193-0194, 0199, 0212, 0214, 0234, 0239, 0241 | OPTIONS | [../mods/options.md](../mods/options.md) |
| 0217, 0232, 0240 | imported animation transitions | [motion.md](motion.md) |
| 0001-0004, 0021-0023, 0050, 0094 | GCC divergences and original bugs | [compiler.md](compiler.md) |

### Original game bugs fixed

| Patch | Bug |
|---|---|
| 0023 | a self-linked GPU primitive after every cup (see [compiler.md](compiler.md)) |
| 0050 | leftovers of an older name in the save title |
| 0094 | the MP bonus message soft-locks the battle result box |
| 0124 | the script's merit reduction set merit to minus the value (always ending at 0); no original script uses it |
| 0220 | the Status page's happiness label read the wrong texture columns (a stray mark before it, its last letter cut) |
| 0231 | a selection with no end-of-selection marker let cancel continue from inside the first option's code (instant wins, entries, prosperity and money by accident); cancel is now refused there |

## Jijimon's starter quiz (0273)

All seven three-option questions run through a single state loop. `modQuizResult` totals three axes and
resolves ties by the latest supporting answer; equal scores supported last by the same answer use the earlier
axis in the documented order. It maps the element/attribute/temperament cell to a starter-list index.
`modNewGameStarter` resolves p254 to a uint16 species id for creation and both default-name paths.
The packed table adds 224 bytes; the linked main executable grows by 832 bytes (`main_BSS_END` 0x801ca0b8 → 0x801ca3f8, series through 0272 → 0273, same EN bank).
New-game technique exceptions remain the two authored rows; every other starter equips 0x2e and learns
`DIGI_PARA(type).moves[0]`. `modInitializeStarterTechniques` runs only in main's new-game branch, after
`initializePartner`. Neither Continue branch teaches a technique: `loadSavegame` has already restored the
learned bits before `initializePartner`, and `initializeLoadedMap` restores the equipped slots afterward.
Intrinsic baby Bubble attacks are outside the learned-move bitset. The rebirth path equips 0x2e; its learned
bitset survives rebirth.
The result announcement initializes the species default name before displaying `{partner}`. Naming then
continues through the existing optional-name flow. The expanded table in `story/new-game-quiz.dws` uses the existing `name.*` translation
mechanism in `text/<language>.json`, with speaker plus at most three lines.

## Monochromon shift plate (0279)

`script_interp.c` arms `modShopPlateAdd` only when routine `0x1e` clears the shift total on screen 49.
World object `0x1fb3` renders the right-anchored 3×5-font profit/count plate and blue progress bar in
`mod_qol.c`, reading `SHOP_VARIABLE` and p123 without changing either. The named 1792/2560 thresholds
match `shop_hi` in `story/base/zones/monochrome-shop/s049-49/script.py`; patch 0280 lowers the
recruit target from 3072. The object removes itself when the screen changes; accepting another shift
adds it again. It uses the existing per-pass packet allocator, with no saved flag or persistent drawing
primitives, for interpolated 30/60 fps passes.
