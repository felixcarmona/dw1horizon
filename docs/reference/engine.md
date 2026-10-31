# Engine: files, graphics, models, effects, sound

How the original engine works under the game logic: file loading and the read queue, framebuffers, ordering table
and VRAM layout, fades and menu boxes, model loading and animation playback, the battle effect files, sound banks and
music, the movie player, the random number generators, math helpers and the startup sequence. Paths are
`decomp/src/main/*.c` unless stated (`file.c:line` citations into `decomp/src/`); addresses from
`decomp/config/us/symbols.txt` (original USA executable).

## Summary

The engine is Psy-Q (libgs/libgpu/libcd/libsnd) plus a thin layer of its own: a file table looked up by name, an
asynchronous read queue of 32 entries, two 320×240 framebuffers with a 4096-level ordering table, an MMD loader (TMD
+ per-bone animation table), an effect interpreter (`EFEDAT.EFE`, one 0x5000-byte block per effect), VAB sound banks
loaded in pieces from the `.VHB` files, an STR player in an overlay and two pseudorandom generators. Almost
everything read from the CD lands in low RAM (`0x80010000`, `GENERAL_BUFFER`) or in fixed bss buffers; the `malloc3`
heap is only used by NPC models and temporary buffers. The file formats are in [file-formats.md](file-formats.md);
the heap and buffer budget in [memory.md](memory.md); our changes to the engine in
[engine-patches.md](engine-patches.md).

## Source files

| File | What it does |
|---|---|
| `file.c` (151) | `lookupFileTable`, `readFile`, `readFileSectors`, `loadTIMFile`, `loadTextureFile`, `loadStackedTIMEntry`: synchronous reads |
| `file_queue.c` (271) | asynchronous queue `FILE_REQUEST_QUEUE[32]`, `tickFileReadQueue`, `addFileReadRequest*` |
| `file_table_us.c` | `FILE_OFFSET_TABLE[819]` `{sector, size, name}` ([disc.md](disc.md#the-file-table)) |
| `utils2.c` | `loadDynamicLibrary` (overlays), `loadStackedTIMFile`, `startMovie`/`playMovie` |
| `main.c` | `main`, `initializeHeap`, `initializeFramebuffer`, `gameLoop`, `view_init`, `applyDrawOffset` |
| `graphics.c` (194) | `initializeGsTMDMap` (`GsFCALL4` table), `updateTMDTextureData`, `ATTACK_OBJECTS` |
| `fade.c`, `ui.c`, `line.c` | fades to black/white; menu boxes (`UI_BOX_DATA[6]`); `LINE_F2/F3` lines |
| `drop_shadow.c`, `butterfly.c`, `particle.c` | round shadow under each entity; status butterflies; healing particles |
| `efe.c` (1245), `efe_table.c` | particles, clouds, flashes, *sprites*; locating `EFEDAT.EFE`; `EFEX_TABLE` |
| `model.c` (3717), `anim.c` (499), `buff_model.c` | MMD and texture loading, skeleton, rendering; animation playback; blinking combat model |
| `sound.c` (778), `sound_async.c` (319) | VAB/SEQ: `initializeMusic`, `playSound`, `playMusic`, `loadMapSounds`; asynchronous version on top of the queue |
| `src/mov/mov.c` (252) | `MOV_REL` overlay: STR player (MDEC + XA) |
| `rng.c`, `math.c`, `vecmath.c`, `aabb.c` | `customRandom`; `_sin/_cos/_atan`, `randomLimit`; projections and angles; collision boxes |
| `_psstart.c` | Metrowerks startup: registers, stack, `gp`, clears bss, enables the GTE, calls `main` |

## State in memory

RAM addresses of the USA version (`symbols.txt`); sizes from the code.

| Symbol | RAM | Type/size | Meaning |
|---|---|---|---|
| `FILE_OFFSET_TABLE` | `0x8011FE1C` | 819×12 | file table ([disc.md](disc.md#the-file-table)) |
| `FILE_REQUEST_QUEUE` | `0x80154700` | 32×0x44 | requests: `next, buffer, *isRunning, cb, param, waitCb, param, state(+0x1C), name[29], CdlLOC, size` |
| `FILE_READ_QUEUE_HEAD/TAIL` | `0x80134E60/64` | ptr | linked list of pending requests |
| `FILE_QUEUE_CALLBACK(+PARAM)`, `FILE_REQUEST_CALLBACK2` | `0x80134E58/5C`, `0x80134E54` | ptr, i32 | wait *callback* registered by `setFileReadCallback2` |
| `GENERAL_BUFFER_PTR` | `0x801344F4` | ptr = `0x80010000` | general load area (map, VHB, EFE in combat; overlays overwrite it) |
| `TEXTURE_BUFFER`, `BOSS_EFE_TMD_BUFFER` | `0x80088800`, `0x80058000` | macros | temporary TIM for `loadTextureFile`/`CARD.ALL` (same address as `TRN_REL`); `ETCHI\BOSS_EFE.TMD` (script op. 0x33) |
| `TAMER_MODEL_BUFFER` | `0x801A1398` | 0x7800 declared, 0xE000 effective | the tamer's `BOYS.MMD` (0xDECC bytes); the adjacent symbol `MAIN_D_801A8B98` (0x6800) is the tail of the same *buffer* split in two [inferred] |
| `PARTNER_MODEL_BUFFER` | `0x801878DC` | 0x18800 | partner MMD |
| `TAMER_POSITION_DATA` / `TAMER_MOMENTUM_DATA` | `0x801A07E8` / `0x801A00DC` | 22×0x88 / 22×0x52 | tamer's per-bone pose and velocities |
| `PARTNER_POSITION_DATA` / `PARTNER_MOMENTUM_DATA` | `0x801866CC` / `0x80185BE8` | 34×0x88 / 34×0x52 | same for the partner (NPCs take theirs from the *heap*) |
| `TAMER_MODEL`, `PARTNER_MODEL`, `NPC_MODELS[5]`, `UNKNOWN_MODEL[16]` | `0x801371E0`, `0x801371FC`, `0x80137140`, `0x80137218` | `ModelComponent` 0x1C | `useCount, TMD*, animTable*, mmd*, pixelPage, clutPage, offX, offY, modelId, digiType` |
| `NPC_MODEL_TAKEN[5]`, `UNKNOWN_MODEL_TAKEN[16]` | `0x801371CC`, `0x801373D8` | i32 | occupied VRAM slots (NPCs, effects) |
| `ENTITY_TABLE[10]` | `0x8012F344` | ptr | 0 tamer (`TAMER_ENTITY` `0x8015576C`), 1 partner (`PARTNER_ENTITY` `0x801557A8`), 2–9 NPCs (`NPC_ENTITIES` `0x80155828`) |
| `DIGIMON_SKELETONS` | `0x8011CE60` | ptr[] | per type: `{objIndex, parentIndex}` per bone |
| `POOP_MODEL_BUFFER`, `GENERAL_MESH_BUFFER[2]`, `CHEST_MESH_BUFFER` | `0x80137C00`, `0x80151200`, `0x80153408` | ?, 2×0x1000, 0x800 | `UNTI.TMD`; TMDs of map objects (boxes, crystal, chest) |
| `malloc3` *heap* | `0x801BFB70–0x801EFF00` | ~193 KB | `_end`=0x801BFB64 from the linker (the EXE header's bss ends at 0x801BFC4C); NPC MMDs, NPC `posData`, temporary 0x4800 TIM |
| stack | `0x801EFF00–0x801FFF00` | 64 KB | `_stack_addr`, `_stack_size`=0x40 KB |
| `GS_ORDERING_TABLE[2]` | `0x8015DB68` | 2×GsOT | `length`=12 → 4096 entries; tags in `GS_OT_TAGS_0/1` `0x80155B68`/`0x80159B68` (0x4000 each) |
| `GS_WORK_BASES[2]` | `0x8015DBA8` | 2×0x14000 | GPU packets of each frame (`GsGetWorkBase`) |
| `DR_OFFSETS[2]` | `0x8015DB90` | DR_OFFSET | drawing offset (160,360)/(160,120) |
| `ACTIVE_FRAMEBUFFER`, `ACTIVE_ORDERING_TABLE` | `0x80134ECC`, `0x80134ED0` | i32, ptr | *buffer* and OT of the current frame |
| `DRAWING_OFFSET_X/Y`, `VIEWPORT_DISTANCE` (+`_COPY`) | `0x80134EC0/C4`, `0x80134ED4` (`EDC/EE0`, `ED8`) | i32 | 2D origin (camera offset, 160,120 by default); projection distance (0x400 at startup) |
| `GS_VIEWPOINT` (+`_COPY`) | `0x80185BA8` (`BC8`) | GsRVIEW2 | 3D camera |
| `MAP_LAYER_ENABLED` | `0x80134EC8` | u8 | draws the prerendered background |
| `LIGHT_DATA`, `GsWSMATRIX`, `GsFCALL4` | `0x801B1C24`, `0x80136F84`, `0x80137000` | 3×GsF_LIGHT, MATRIX, table | flat lights (set by `map.c`); world→screen matrix; TMD routines |
| `FADE_DATA`, `FADE_IN_TARGET`, `FADE_OUT_CURRENT`, `FADE_IN_CURRENT` | `0x80134CAC`, `CAE`, `CB0`, `CB2` | i16 | frames+1 of the fade out / fade in; counters (0 = no fade) |
| `FADE_PROGRESS`, `FADE_MODE`, `FADE_PROTECTION` | `0x80134CB4`, `CB5`, `CB8` | u8, u8, i32 | 0..160; 2 = black, 1 = white; 1 while a fade is running |
| `UI_BOX_DATA[6]` | `0x8013D390` | 6×0x24 | menu boxes (`state, frame, color, features, rects, tick, render`) |
| `ATTACK_OBJECTS[17]`, `BUTTERFLIES[2]`, `HEALING_PARTICLES[1]` | `0x80137A24`, `0x80155430`, `0x8013D1A0` | 17×0x1C, 2×8, 1 | pending hits `{victimId, active, pos, effectId, subEffect, casterId}`; butterflies; healing particles |
| `EFEDAT_CD_LOCATION` | `0x8012343C` | u32 | start sector of `EFEDAT.EFE` |
| `EFEX_TABLE` | `0x80155024` | 128×12 | positions of `FEEL_EF.TMD`, `EX.TIM`, `EX.TMD`; filled and never read |
| `EFE_DATA_PTR`, `EFE_HEAP_BASE`, `EFE_HEAP_POINTER` | `0x80134D10`, `0x80134D18`, `0x80134D14` | ptr | 16 `EfeSlot`; effect *heap* (in combat, inside `GENERAL_BUFFER`) |
| `EFE_LOADED_MOVE_DATA[17]`, `EFE_LOAD_REQUEST`, `EFE_SOUND_DATA[10]` | `0x80139A0C`, `0x80139B20`, `0x80139AD0` | i16[], 0x14, 10×8 | technique loaded in each *slot* (−1 free); load request; effect sound channels |
| `VHB_HEADER_SS/SL/FAALL/VLALL`, `_VBALL_0..3`, `_ESALL_SB` | `0x801474C4`, `0x801464C4`, `0x801444C4`, `0x801434C4`; `0x801424C4/0x801414C4/0x801404C4/0x8013F4C4`; `0x8013DCC4` | 0x1000, 0x1000, 0x2000, 0x1000; 0x1000×4; 0x1800 | VAB header (VH) in RAM for banks 0, 1, 2, 3; 4–7; 8 |
| `SEQ_BUFFER`, `SEQ_TABLE` | `0x80148574`, `0x801484C4` | 0x5800, SS_SEQ_TABSIZ | SEQ of the current font; libsnd table |
| `CURRENT_SEQ_FONT/TRACK`, `SEQ_ACCESS_NUM` | `0x80134D96/98`, `0x80134D94` | i16 | FAALL font (1..0x21) and track playing; sequence id (−1 none) |
| `ACTIVE_BGM_FONT/TRACK` | `0x80135006/07` | u8 | BGM requested by the script (before the time-of-day *override*) |
| `FREE_CHANNEL_INDEX`, `ACTIVE_MAP_SOUND_ID` | `0x80134D90`, `0x80134394` | i32 | next SFX channel; loaded `ESALL` region |
| `SOUND_BUFFERS[10]`, `LOAD_SOUND_COMPLETE_STATE` | `0x8012BB74`, `0x80134E8C` | 10×8, i32 | `{buffer, vabId, isLoading}` of the asynchronous load |
| `VHB_SOUNDBUFFER_START`, `MAP_SOUND_PARA`, `ENEMY_MUSIC_MAPPING` | `0x80127ED4`, `0x80127FF4`, `0x8012BAE4` | u32[10], 22×4, u8[48] | SPU addresses per bank; `ESALL` chunks; music per enemy |
| `MAIN_D_801303B8` | `0x801303B8` | 64×(u8 font, u8 track) | *jukebox* list (order of `BGM_TRACK_NAMES`) |
| `CUSTOM_RNG_VAL1`, `CUSTOM_RNG_VAL2` | `0x80134E68`, `0x8013442C` | u32 | `customRandom` state (VAL2 starts at 0x0013CC25) |
| `MOV_MOVIES[4]`, `MOV_ENV`, `MOV_RUN_LEVEL_BUFFER_0/1`, `MOV_SLICE_BUFFER_0/1`, `MOV_RING_BUFFER`, `MOV_VLC_TABLE` | `0x8001094C`, `0x800109EC`, `0x80010A24/0x80038A24`, `0x80060A24/0x80063724`, `0x80066424`, `0x80072424` | 4×0x28, 0x38, 2×0x28000, 2×0x2D00, 0xC000, 0x11004 | only with `MOV_REL` loaded: movie list, state, MDEC *buffers*, 24-sector ring, VLC table |

## How it works

### File loading

**Name → sector.** `lookupFileTable` (`file.c:16-42`) keeps whatever comes
after the last `\` of the *path* and compares it with `strcmp` against
`FILE_OFFSET_TABLE`; the directory is ignored. So `CHDAT\MMD0\AGUM.MMD`,
`SOUND\SS` + `.VHB` or `ESALL` resolve by their base name, and the `MMD<n>`
that `loadMMD` builds (`model.c:3395-3398`, `n = type/30`) is cosmetic.
`lookupFileSize` is used by `loadMMD` to reserve `(size + 0x7FF) & ~0x7FF`.

**Synchronous.** `readFile` (`file.c:80-96`): `CdlSetloc` + `CdRead(⌈size/2048⌉,
CdlModeSpeed)` + blocking `CdReadSync(0)`, retrying while `CdReadSync`
returns an error. `readFileSectors` (`134-151`) adds an offset in sectors:
it is the basis of the "stacked" files (`ALLTIM.TIM` 9 sectors per Digimon,
`VBALL` 7, `VLALL` 15, `FAALL` 39, `ESALL` per `MAP_SOUND_PARA`). `loadTIMFile`
reads and uploads pixels and CLUT to the TIM's own coordinates;
`loadTextureFile` does it from `TEXTURE_BUFFER` and returns `tpage`/`clut`
(`53-78`); `loadStackedTIMFile` (`utils2.c:481-498`) walks concatenated TIMs
in `GENERAL_BUFFER` (`ETCTIM.BIN`).

**Asynchronous.** `addFileReadRequest` (`file_queue.c:176-238`) looks for a
free `FileRequest` (`state < 0`; if there is none, it calls
`tickFileReadQueue` until one frees up), copies the name (max. 28
characters), sets `*isRunning = 1`, `state = 2` and enqueues it. Variants:
`…Lookup` (by table), `…Section` (sector + count), `…Path` (size −1: resolved
with `CdSearchFile("\name;1")` at dispatch time; used by the overlays and
`BOSS_EFE.TMD`). `tickFileReadQueue` (`75-158`) runs as object `0x404` every
frame (`60-64`) and serves **one request at a time**: `2` → issues `CdRead`,
`1` → polls `CdReadSync(1)`; when done it calls `finishCallback` and, if that
registered a wait *callback* with `setFileReadCallback2`, moves to `10` and
calls it every frame until it returns 0 (this is how `sound_async.c:128-168`
waits for `SsVabTransCompleted`); error → back to `2` (retry); `0` → removed
from the head on the next frame and `*isRunning = 0`. Whoever waits does so
with `while (isLoading) tickFileReadQueue(0)` loops
(`sound_async.c:255-257`).

**Where each resource lands.**

| Resource | Call | Destination |
|---|---|---|
| `*_REL.BIN` | `utils2.c:375-379` | `REL_BIN_OFFSETS` ([executable.md](executable.md#overlays-_relbin)); `MOV_REL` overwrites the map at `0x80010000` |
| `MAP\*.MAP`, `*.TFS` | `map.c:4163`, `4349` | `GENERAL_BUFFER`; the TFS tiles stay in RAM and are uploaded to VRAM in windows |
| `BOYS.MMD`, partner MMD | `model.c:3432` | `TAMER_MODEL_BUFFER`, `PARTNER_MODEL_BUFFER` |
| NPC MMD | `model.c:3399-3400` | `malloc3` (heap), freed in `unloadModel` |
| `ALLTIM.TIM` (9 sectors) | `model.c:3285-3290` | temporary `malloc3(0x4800)` → VRAM |
| `MAPHEAD.SCN`, table and entry of `DG.SCN` | `script_interp.c:2122-2123`, `589` | `0x801B1D30` (0x61A8), `0x801B7ED8` (0x2000), `0x801B9ED8` (0x4000) |
| `*.VHB` | `sound.c:393`, `sound_async.c:82-125` | temporary `GENERAL_BUFFER` → header to `VHB_HEADER_*`, body to the SPU |
| `EFEDAT.EFE` entry | `battle_effect.c:1377-1382` | EFE *heap* inside `GENERAL_BUFFER` (combat) |
| `ETCTIM.BIN`, `TITLE*.TIM`, `FI_INFO.TIM` | `main.c:3352-3377` | `GENERAL_BUFFER` → VRAM |
| `CARD.ALL` (one entry) | `game_menu.c:2174` | `TEXTURE_BUFFER` → VRAM (576,256) |
| `UNTI.TMD`, chest, boxes, crystal | `partner_impl.c:408`, `map_object.c:391-614` | `POOP_MODEL_BUFFER`, `CHEST_MESH_BUFFER`, `GENERAL_MESH_BUFFER` |

In combat `BTL_initializeEFEEngine(GENERAL_BUFFER_PTR)` (`btl.c:443`) takes
over the map area, which is always read again on return: `SKIP_MAP_FILE_READ`
(`map.c:4161`) is only ever set to 0 in the USA version.

### Graphics

**Screen.** `initializeFramebuffer` (`main.c:3485-3528`): `GsInitGraph(320,
240, GsOFSGPU, 0, 0)` (non-interlaced, offset applied by the GPU),
`GsDefDispBuff(0,0,0,240)`: two 320×240 *framebuffers* in VRAM at (0,0) and
(0,240); a 4096-entry OT per *buffer*; `DRAWING_OFFSET` = (160,120)
(origin at the center); `DR_OFFSETS[0]` = (160,360), `[1]` = (160,120).
`view_init` (`4123-4137`): projection 0x400, camera at (0,0,−2000) looking
at the origin, *near clip* 100.

**Frame** (`gameLoop`, `main.c:3876-3906`): `pollInputGame` →
`GsGetActiveBuff` → `GsSetWorkBase(GS_WORK_BASES[buf])` + `GsClearOt` →
`processInput`, `tickScript` → `GsSetOrign(DRAWING_OFFSET)` (this is how the
2D camera scrolls), `GsSetRefView2`, `GsSetProjection(VIEWPORT_DISTANCE)` →
`tickObjects`, `renderObjects` → `applyDrawOffset` (puts `DR_OFFSETS[buf]`
in OT entry 32, `3970-3974`) → `DrawSync(0)`, **`VSync(3)`** (the game runs
at 60/3 = 20 frames/s; title and menus use `VSync(0)`) →
`GsSwapDispBuff`, `GsSortClear` (black), `GsDrawOt`, `handlePause`. The OT
is drawn from the highest entry down to 0 [inferred, libgs behavior]: lower
index = on top. Fixed layers: fade 1 (black) / 10 (white), menu boxes
`6 − id`, title 30, AABB 33; entities by `otz >> 2`
(`GsSortObject4`, `model.c:2905`), *sprites* by `distance >> 4`
(`map.c:6005-6015`), shadows at 0xFFD (`drop_shadow.c:68`). With the
`DR_OFFSET` at 32, layers < 32 (UI, text, fades) stay at fixed screen
coordinates and the rest follows the camera [inferred].

**TMD.** `initializeGsTMDMap` (`graphics.c:60-89`) registers the
`GsTMDfast*`/`GsTMDdiv*` routines in `GsFCALL4`. `updateTMDTextureData`
(`156-194`) walks every textured primitive of a TMD and adds to it the
`tpage`, `clut` and the (x,y) offset of its VRAM slot: MMD UVs are relative
to the slot, so the same model can go into any *slot*.

**VRAM map** (1024×512 at 16 bits; x, w in 16-bit units: a 4 bpp image is
w×4 pixels wide, an 8 bpp one w×2). Data from the TIM headers and from the code.

| x | y | w | h | Contents | Source |
|---|---|---|---|---|---|
| 0 | 0 / 240 | 320 | 240 | *framebuffers* 0 and 1 | `main.c:3506-3507` |
| 320 | 0 | 64 | 128 | item icons (`ITEM.TIM` = `ETCTIM` #6, 4 bpp), CLUT (224,488) 16×24 | `item.c:2482`, `utils2.c:270-301` |
| 320 | 128 | 64 | 128 | `SYSTEM_W.TIM` (= #8): box borders, cursor; CLUT (96,488) 16×16 | `ui.c:renderUIBoxBorder`, `script_textbox.c:963` |
| 320 | 256 | 64 | 128 | tamer texture (`ALLTIM` 0, page 0x15), CLUT (0,488) | `model.c:3411-3416` |
| 320 | 384 | 64 | 128 | partner texture (page 0x15, offset 0x80), CLUT (16,488) | `model.c:3419-3425` |
| 384+64·(k/2) | 256+128·(k%2) | 64 | 128 | NPC/wild *slot* k=0..4, CLUT ((k+2)·16, 488) | `model.c:3385-3390` |
| 512 | 256 | 64 | 256 | `SBOY.TIM` (= #5), CLUT (112,488); medals: `MoveImage` to (512,432) | `map_object.c:1136-1142` |
| 576+64·(i/8) | 256+32·(i%8) | 64 | 32 | EFE effect textures *slot* i=0..15, CLUT (128+16·(i/4), 488+6·(i%4)) | `battle_effect.c:1495-1500` |
| 576 | 256 | 30 / 28 / 64 / 75 | 224 / 24 / 32 / 180 | `OP.TIM` (ending), `LIFE.TIM` (death), `SLOT.TIM`, `CARD.ALL` entry (8 bpp, CLUT (448,511)) — same slot as the EFEs | TIM headers, `game_menu.c:2180` |
| 640 | 0 | 8 | 32 | `IWA1.TIM` (rock); Monochromon bubble at (672,0), CLUT (0,486) | `script_common.c:262` |
| 704 | 256 | 64 | 256 | rendered text (4 bpp, 256×256 px), font CLUT (208,488) | `font.c:16-30`, `utils.c:202` |
| 768 | 0 | 160 | 256 | `TITLE256.TIM`/`TITLE2.TIM` 8 bpp (320 px): title and menu background, CLUT (0,480) | `main.c:4074-4083` |
| 768+64·(x%4) | 128·(y%3) | 64 | 128 | 4×3 window of map background tiles (8 bpp, 128×128 px), active CLUT (0,480); day/evening/night at (0,481+i) | `map.c:4379-4390`, `4525-4570`, `4360-4366` |
| 768 / 768 | 384 / 448 | 64 / 34 | 48 / 48 | `DEFEFF.TIM` (= #2, CLUT (192,488)); `EX.TIM` (CLUT (192,500)) | TIM headers |
| 832 | 384 | 64 | 128 | `SPOT256.TIM` (= #7, 8 bpp): round shadow, CLUT (0,487) | `drop_shadow.c:60-62` |
| 896 | 384 / 448 | 64 | 64 | `BI_IN.TIM` (= #0, CLUT (256,480)); `FI_INFO.TIM` (= #4): clock/HUD, CLUT (256,496..502) | `clock.c:215-275`, `fade.c:152-155` |
| 960 | 384 / 448 | 64 | 64 | `FEEL_EF.TIM` (= #3): status icons, butterfly at (960,432), CLUT (272,480); `BTLCOMND.TIM` (= #1): combat commands, CLUT (272,496) | `butterfly.c:28-47` |
| 0–320 | 480–511 | | | CLUTs: (0,480) active map; (0,481..) map; (i·16,486) 4 bpp map objects; (0,487) shadow; (0..304,488..511) `ETCTIM`, models, font, effects | `map.c:5920-5937` |
| 0 | 32 / 272 | 480 | 176 | video frames (24 bpp, width·3/2) | `mov.c:204`, `182` |

**Fades** (`fade.c`): `fadeToBlack(n)` (`73-85`) creates object 4005 with
`renderFadeOut`, `FADE_DATA = n+1`, stops the clock (`stopGameTime`) and
sets `FADE_PROTECTION`. `renderFade` (`144-168`) draws a full-screen
semitransparent `POLY_FT4` with `tpage = GetTPage(0, FADE_MODE, 896, 448)`:
`FADE_MODE` is the blend mode, 2 = B−F (subtract → black), 1 = B+F (add →
white); texel (250,509) with CLUT (256,502) is a uniform color and the gray
level `progress` (0..160) sets the intensity. `renderFadeIn` (`101-127`)
goes from 160 down to 0 in `FADE_IN_TARGET` frames. The main loops wait for
`FADE_OUT_CURRENT < 0x28` (`main.c:3609`).

**Menu boxes** (`ui.c`): `createStaticUIBox(id, color, features, rect,
tick, render)` (object `0x1A4`, layer `6 − id`); `createAnimatedUIBox` grows
over 4 frames from `startPos` with `playSound(0,0)` and closes with
`playSound(0,1)`. Border: four 4×4 corners from `SYSTEM_W` (u 0x78/0x7C,
v 0x90/0x94) and lines black 0x020202 / gold 0xFAD990 / brown 0xC59F4A;
`features` bit 0 title line, bit 2 scroll bar, bit 1 semitransparent; fill
`UI_BOX_COLORS` (0 black, 1 blue 0x2D3840). `line.c` draws `LINE_F2/F3`
and, if `mode ≠ 0`, a `DR_TPAGE` with blend mode `mode & 3`.

**Shadow, butterflies, particles.** `renderDropShadow` (`drop_shadow.c:19-79`)
projects a square of side `2·DIGIMON_DATA[type].radius` on the ground with
the `SPOT` texture subtracted (`0x30`), layer 0xFFD; `renderAABB` is stubbed
out (`aabb.c:23`). Butterflies (`butterfly.c`, object `0x80E`, max. 2): 60
frames above the head, a two-frame 16×16 *sprite*. `particle.c`
(object `0x817`): 20+20 healing particles over 44 frames. `efe.c`
(in the executable): `createParticleFX` (types 0–3, 25/48/20 particles),
`createCloudFX`, `EFECreateFlash` and `worldPosToScreenPos`/`renderSprite`
(`map.c:5989-6015`).

### Models and animation

`ModelComponent` (`model.h:22-34`) describes a loaded model: `mmdPtr`
(the whole file), `modelPtr` = `mmd + u32[0]` (TMD), `animTablePtr` =
`mmd + u32[1]`, `pixelPage` (texture page; x = (p%16)·64, y =
(p/16)·256), `clutPage` (`0x7A00 | n` → CLUT at (n·16, 488)). Slots: the
tamer (type 2) and the partner (3) have a fixed *buffer* and slot; NPCs
(type 0) share `NPC_MODELS[5]` by `digiType` with a use counter, and
`NPC_MODEL_TAKEN` hands out 5 VRAM slots; effects use
`UNKNOWN_MODEL[16]`. `loadMMD` (`model.c:3342-3439`): texture →
`loadDigimonTexture` (`3271-3291`, `ALLTIM.TIM` sector `type·9`) →
`uploadModelTexture` (`3543-3564`, **ignores the TIM's coordinates** and
uses the slot's; the TIM header says (320,0)); MMD → `readFile`,
`GsMapModelingData`, `updateTMDTextureData`. `loadMMDAsync`/`applyMMD`
(`3566-3717`) do the same in two phases on a caller-provided *buffer*
(digivolution). `DIGIMON_DATA[type].boneCount` gives the number of bones and
`DIGIMON_SKELETONS[type]` the `{objIndex, parentIndex}` tree;
`initializeDigimonObject` (`2786-2865`) links each bone to its TMD object
(`GsLinkObject4`) and to the parent's `GsCOORDINATE2`, reads the initial pose
and starts animation 0. `renderDigimon` (`2867-2929`): per bone
`GsGetLws` + `GsSortObject4(…, 2, <1 KB fast RAM at 0x1F800000>)`; wireframe (`renderWireframed`)
during digivolution; `renderFlatDigimon` (`2722-2774`) replaces the model
with a 15×15 *sprite* taken from its own texture (u 0xE0/0xF0, v
offset+0x60/0x70) when `flatSprite ≠ −1`.

**Animation format** (as `anim.c` reads it; the full format with examples is in [../mods/models.md](../mods/models.md) §2.2): the MMD's table is `u32`
offsets per *slot* (0 = does not exist), relative to the table itself. Each
animation is an `i16` stream: `frameCount` (bit 15: includes per-bone
scale), initial pose of bones 1..n−1 (`[sx sy sz] rx ry rz
tx ty tz`), and then instructions, each preceded by the frame on which it
acts (low 12 bits) and with the code in bits 12–15
(`startAnimation` `201-274`, `tickAnimation` `276-357`):

| Code | Meaning |
|---|---|
| `0x0000` | *keyframe* block: word = bone (bits 0–5) + 9-channel mask (bit 14 → scale x … bit 6 → translation z), `divisor` = frames, one `i16` per active channel = total delta; bit 15 chains another bone (`359-396`) |
| `0x1000` | loop start, repetitions in the low byte (0xFF = infinite) |
| `0x2000` | loop end: decrements and jumps back, restoring the frame |
| `0x3000` | `MoveImage` inside the texture slot (UV animation): source, size, destination in bytes |
| `0x4000` | sound: high byte bank (4 = the entity's `vabId`), low byte note; only if `isOnScreen` (`335-346`) |

`tickMomentum` (`130-199`) applies `delta/divisor` every frame, with the
accumulated remainder (`animApplyMomentum`, `420-432`), to each bone's scale,
rotation and translation and recomputes its matrix; bone 0's translation
(root motion) is accumulated in 17.15 (`locX << 15`) and transformed by the
model matrix (`applyRootMomentum`, `434-499`); `animFlag` bit 1 disables it
and bits 3–6 clip it per direction. On reaching `frameCount`, bit 0 of
`animFlag` is cleared. `animateEntityTexture` (`76-117`) cycles texture rows
every 2 frames for types 0x09/0x15/0x45/0x65/0x68/0x6A/
0x7F/0x85/0x8F (all fire Digimon: flames) [inferred].

**Animation slots** (seen in the code; the semantics are per model):

| Slot | Use | Source |
|---|---|---|
| 0 | idle (every entity on creation) | `model.c:2863` |
| 1 | alternative idle; tamer: combat wait, restarted every 171 frames | `battle_tick.c:263-289`, `partner.c:878` |
| 2 | walk | `partner.c:274`, `828` |
| 3 | partner condition walk (tamer uses its own slot 3 for running/fleeing) | `partner.c:setPartnerSlowWalking`, `battle_tick.c:165` |
| 4 | partner: fast catch-up locomotion when far from the tamer; tamer: inventory pose | `partner.c:partnerTickWalking` (closeness 0), `inventory.c:339` |
| 6 | tamer: throw item (leaves from bone 9 until frame 7) | `main.c:4177-4194` |
| 8 | partner: eat [inferred]; tamer: gesture to the partner [inferred] | `partner.c:462`, `703`, `287` |
| 9, 11 | partner: reactions (11 also "doesn't want to eat") [inferred] | `partner.c:295-302`, `partner_impl.c:1611` |
| 10 | partner: poop; tamer: watch during a finisher [inferred] | `partner.c:558`, `600`, `battle_tick.c:269` |
| 12, 13 | partner: after pooping; rejects the item [inferred] | `partner.c:611`, `466` |
| 14 | tamer: give an order in combat | `battle_tick.c:129` |
| 0x1C | only type 0x98 (no collision while it lasts) | `map.c:4007` |
| 0x1B | partner: HP training motion; external training code controls playback pauses | `trn2_hp_map99.c:73`, `trn2_hp_map107.c:52` |
| 0x21 / 0x22 | combat idle; 0x22 also used when stunned | `btl.c:186-194`, `battle_main.c:BTL_tickStunState` |
| 0x23 / 0x24 | battle walk / run (walk when flagged or HP is at most 20%); 0x24 also fleeing. No X root motion or map collision | `battle_main.c:BTL_startWalkingAnimation`, `anim.c:458`, `map.c:3576` |
| 0x25 | finite block reaction; sets blocking flag before starting the animation | `battle_main.c:2220` |
| 0x2C | partner with 0 HP when an item is used (getting up) [inferred] | `item.c:2315` |
| 0x2E + i | technique i: `DIGIMON_DATA[type].moves[i]`; type 0x3C with 0x3C → technique 0x70 | `utils2.c:326-335` |

`buff_model.c` (object `0x501`) alternates every frame the CLUT (0x7ACC /
0x7B0C) of object 5 of the TMD that precedes `BTL_REL.BIN` (`btl.c:436-441`):
a combat blink [inferred].

### Effects (`EFEDAT.EFE`)

`findEFEDATFile` (`efe.c:976-994`) locates the file at startup;
`getEFEDATEntry(id)` (`1003-1011`): **sector = start + (id − 0x100)·10**,
that is, each effect takes 0x5000 bytes (10 sectors) and the effect id is
`0x100 + index`. Each block starts with the `EfeFileHeader` (`efe.h:154-168`, 0x34 bytes:
`startScript, initScript, uvAnims, uvAnimsEnd, subEffects, tmdStart, tmdEnd,
timStart, timEnd, dataEnd, unk28, numSubEffects, effectId`) followed by the
*script* of effect 0x100. The file has 122 chunks: ids 0x100..0x178 plus
an empty one (0xCDCDCDCD); chunk 110 carries `effectId` 0x158 instead of 0x16E. In combat (`BTL_REL`): `BTL_loadMoveEFE(moves, effectIds, …)` →
`BTL_loadNextEFEFile` (`battle_effect.c:1377-1382`) requests 0x5000 bytes
through the queue at `EFE_HEAP_POINTER`; `BTL_handleEFEFileLoaded`
(`1480-1559`) uploads the TIM to slot `i` of `UNKNOWN_MODEL` (VRAM table),
maps the TMD, checks that `effectId` matches the requested technique (if not,
`isLoaded = −3`), records *slot* k in `EFE_LOADED_MOVE_DATA` and advances the
*heap* by `tmdEnd + 0x34`: only the header, *scripts* and TMD stay resident;
the TIM is overwritten by the next load. The engine (`BTL_initializeEFEEngine`,
`1890-1918`) reserves in `GENERAL_BUFFER` 16 `EfeSlot` (0x280) + emitters +
flashes + auras + 0x41000 of *heap*. Effect *scripts* are interpreted by a
stack machine (`EFE_DATA_STACK`, `EFE_CALL_STACK`,
`BTL_dispatchEFEOpcode`): that is already combat. `ATTACK_OBJECTS[16]`
(`graphics.c:91-154`) is the hit queue `{victim, active, position,
effect, subeffect, attacker}` that an effect leaves for the victim to
pick up with `popAttackObject`.

### Sound

**Banks and SPU.** `initializeMusic` (`sound.c:511-544`): `SsInit`,
`SS_TICK240`, loads `SS.VHB` (bank 0) and `SL.VHB` (1), `SsStart`, volume
127, `STUDIO_B` reverb 0x7000 on all voices. `readVHBFile`
(`379-412`): from the `{vhOffset, vbOffset}` chunk it copies the VAB header to
`VHB_HEADER_ADDR[bank]`, `SsVabOpenHeadSticky(bank, SPU address)` and
`SsVabTransBody` of the body. SPU addresses (`VHB_SOUNDBUFFER_START`):
0 SS `0x1010`, 1 SL `0xE800`, 2 FAALL `0x1B800`, 3 VLALL `0x2A000`, 4–7
VBALL `0x31800/0x34000/0x36800/0x39000`, 8 ESALL or SB `0x3B800` (up to
0x80000). Use of each bank: 0/1 system and menus; 2 the current music font;
3 the partner's long voice (`VLALL`, 15 sectors ×
`DIGIMON_VLALL_SOUND_ID[type]`); 4 the partner's voice and 5–7 NPC/enemy voices
(`VBALL`, 7 sectors × `DIGIMON_VBALL_SOUND_ID[type]`, `670-702`; tables in
[executable.md](executable.md#data-tables)); 8 map sound effects: `loadMapSounds(id)` (`715-730`) reads from
`ESALL` the sectors `MAP_SOUND_PARA[id].sectorId/2` and `sectorCount/2`, with
`id = MAP_ENTRIES[map].flags & 0x1F` (`map.c:4340-4343`, 22 regions), or
the whole `SB.VHB` (`VSLoadSounds`/`loadSB`). `sound_async.c` repeats all of
this on top of the queue (`loadVHBFile`, `loadMapSounds2`, `readVBALLSection`,
`loadVLALL`) with `SOUND_BUFFERS[bank].isLoading`.

**Sound effects.** `playSound(bank, val)` (`635-642`): banks 0/1/8 → program
`val/16`, note `60 + val%16`; banks 3–7 → program 0, note `val`.
`startSound` (`596-621`) triggers every tone of the program whose `max == note`
on a free channel 10–23 (`getNextFreeChannel`, rotating over 14; channels
0–9 belong to the music) and returns the mask; `stopSoundMask` /
`stopSound` turn them off with a ramp. Examples: `(0,0)/(0,1)` open/close box,
`(0,3)` confirm, `(0,4)` cancel, `(0,12)` feed.

**Music.** `playMusic(font, track)` (`747-771`), font 1..0x21: if the font
changes, `loadMusicFont` (`732-745`) reads 39 sectors from `FAALL` starting
at `(font−1)·39` into `GENERAL_BUFFER`, uploads VH/VB to bank 2 and copies the
SEQ block (`u32[2]..u32[3]`) to `SEQ_BUFFER`; `seqOpen` (`469-480`): the SEQ
starts with a `u32` table of offsets (`u32[0]/4` tracks) and opens the
track; `seqPlay` (`482-498`): volume 0x50, infinite loop except for fonts
0x1D (track ≠ 1) and 0x1E–0x20 (track ≠ 2), which play once. The
*scripts* request `playBGM(id)` (`script_interp.c:2508-2523`): `font = id`
and `handleMusicOverride` (`1508-1560`) picks the track according to `PSTAT_245`:
mode 0 → 0 by day (6–21 h) and 1 by night; 1 → always 0; 2..0xA → fixed
pairs (6,2), (0xB,2), (0xF,2), (0x15,0/1), (0x1A,0/1), (0x1B,0/1). In
patch 0278, `playBGM` preserves an open, infinitely looping sequence whose
resolved font and track already match, updating the active map BGM even on
that return. One-shot requests and closed sequences still restart. The first
`0xFB` of normal `runMapHeadScript` entry calls `modHeaderKeepsMusic` to peek
at an optional `1E 00 F5 mode` followed by `SET_BGM`. With the override applied,
a different font or variant stops before `loadMap`; immediate `FE` and font
0xFF stop too. The peek restores `PSTAT_245`. A header that branches first
stays deferred until its executed music request; absent a request, entry
finishes by stopping. Explicit script
`0xFB`, `STOP_BGM`, and font 0xFF still reset. Day/night updates, forced updates
and async battle music are unchanged. In combat (`btl.c:349-365`) font 0x21 plays: track 3 against type
0x73 (Machinedramon), 0 in scripted battles, 1 or 2 per
`ENEMY_MUSIC_MAPPING[type − 0x43]` (types 0x43..0x6F), 1 otherwise.

| Font | Tracks (`MAIN_D_801303B8` + `BGM_TRACK_NAMES`, USA names) |
|---|---|
| 1 | 0 Non Bewildering Forest · 1 night |
| 2 / 3 | 0 Tropical · 1 night / 0 Mt. Panorama · 1 night |
| 4 | 0 Drill Tunnel · 1 Ogre Fortress |
| 5 / 7 / 8 / 9 | Overdell Cemetery / Everything Shop / Ogremon no. 3 / Lava Cave |
| 6 | 0 Canyon · 1 Ogremon no. 2 · (2 only through the *override*) |
| 0xA | 0 Dark Aristocrat's Mansion · 1 Underground Lab |
| 0xB | 0 Gear Savanna · 1 night · 2 Leomon |
| 0xC / 0xD / 0xE | 0 Amida Forest / Speedy Time Zone / Glacial Time Zone · 1 night |
| 0xF | 0 Freezeland · 1 night · 2 Igloo |
| 0x10 / 0x11 / 0x12 | Curling / Sanctuary / Sanctuary Below |
| 0x13 / 0x14 | 0 Gecko Swamp / Misty Trees · 1 night |
| 0x15 | 0 WaruMonzaemon · 1 Toy Town |
| 0x16 / 0x17 | 0 Factorial · 1 night / Sewer |
| 0x18 / 0x19 | 0 Trash Mountain / Beatland · 1 night |
| 0x1A | 0 Secret Beach Cave · (1 only through the *override*) |
| 0x1B | 0 Mt. Infinity · 1 Last Room |
| 0x1C | 0 File City · 1 night |
| 0x1D | 0 Tournament Opening · 1 Tournament Progress (loop) · 2 Championship |
| 0x1E | 0 Partner's Entrance · 1 Opponent's Entrance · 2 Arena Battle 1 (loop) · 3 Win · 4 Loss |
| 0x1F / 0x20 | 2 Arena Battle 2 / Arena Battle 3 |
| 0x21 | 0 Event Battle · 1 Normal Battle · 2 Normal Battle 2 · 3 Last Battle |

### Video (`MOV_REL`)

`playMovie(id, 1)` (`utils2.c:500-506`) → `startMovie` (`383-393`): `CdInit`,
`ResetGraph(0)`, synchronous load of `MOV_REL` at `0x80010000` (it overwrites
the map, and its 0x72AD8 bytes of *buffers* sit on top of `GENERAL_BUFFER`),
`MOV_playMovie`, `ResetGraph(3)`, and then `initializeFramebuffer`.
`MOV_MOVIES` (`mov.c:40-45`): 0 `OP1.STR` (3637 frames, title loop),
1 `OP2.STR` (3266, after creating the save), 2 `ED2.STR` (2654,
`MAIN_STATE` 2), 3 `EDR.STR` (3447, ending; cannot be skipped, the others can
with START, `239`). Pipeline (`188-252`): 24-sector `StSetRing`,
`CdRead2(Stream|Speed|RT|Size1)` (the drive plays the XA by itself),
`StGetNext` → `DecDCTvlc2` with the VLC table → `DecDCTin` → `DecDCTout` in
24 px strips that `MOV_onSliceDecoded` uploads to VRAM (x=0, y=32 or 272,
width `w·3/2` because it is 24-bit); when the frame is complete,
`SetDefDispEnv(0, 240·f, 480, 240)` with `isrgb24` and `disp.w·2/3`. After
2000 retries without a frame it restarts the read from `StGetBackloc`.

### Random numbers

Two generators. `customRandom(min, max)` (`rng.c:13-32`), used by the
overlays (digivolution, arena, fishing, versus, combat effects):

```
VAL1 = VAL1 * 0x41C650AD + 0x3039;  VAL2 = VAL2 * 0x41C650AD + 0x3039   (u32)
r = min + ((VAL1 >> 16) | (VAL2 << 16)) % (max - min + 1)
```

`CUSTOM_RNG_VAL1` starts at 0 (bss) and `CUSTOM_RNG_VAL2` at 0x0013CC25;
nobody seeds them. The executable also uses the BIOS `rand()` (`A(0x2F)`,
*thunk* at `0x8009127C`; `srand` is never called): `randomLimit(n) =
n·rand() >> 15` (`math.c:5-11`, 41 calls: map objects, partner,
items, combat UI) and `rand() % n` in `particle.c`, `efe.c`, `model.c`.
Its state lives in *kernel* RAM (it depends on the BIOS) and the sequence is
the same on every boot; only the timing of each call changes it.

### Math

`_sin/_cos` (`math.c:13-30`): angle in 1/512 of a turn (9 bits), 128-entry
table, result in 12 bits (4096 = 1). `_atan(dy, dx)` (`32-78`):
512-entry table, returns 0..4095 (the GTE unit); watch out for the two scales.
`vecmath.c`: `getDistance` (approximation with `DISTANCE_SQRT_LOOKUP`),
`mapToWorldPosition` (`64-108`, from screen pixel to the y=0 plane using the
transpose of `GsWSMATRIX`), `rotateVector` (`RotMatrixYXZ`),
`toEulerAngles`, `matrixToEuler1/2`, `calculatePosition`,
`multiplyRotations`. `aabb.c`: `hasAABBOverlap` and `findAABBHitEntity`
(walks `ENTITY_TABLE` with `radius/2` and `height/2` from `DIGIMON_DATA`).

### Startup

`__start` (`_psstart.c:31-201`): registers to 0, `sp = 0x801FFF00 & ~0xF`,
`gp`, zeroes `.sbss` and `.bss`, enables COP2 (GTE) in `SR` and calls
`main` (without `InitHeap`). `main` (`main.c:3317-3470`), in order:
`initializeHeap` (`InitHeap3`, 0x801BFB70..0x801EFF00) · `SsInit` ·
`ResetCallback` · `ResetGraph(0)` · `initializeFramebuffer` · `PadInit` ·
`CdInit` · `MemCardInit/Start` · `initializeModelComponents` ·
`initializeWorldObjects` · `initializeGsTMDMap` · `initializeFileReadQueue`
· `initializeAttackObjects` · `initializeFontCLUT` · `fillEFEXTable` ·
`initializeFadeData` · `initializeScripts` (reads `MAPHEAD.SCN` and the
`DG.SCN` table) · `view_init` · `initializeUIBoxData` · `initializeEffectData`
(`findEFEDATFile`, particles, clouds, healing) · `initializeInventoryModules`
· `initializeMedalModel` · `initializeClockData` · `initializeStatusObjects`
· `FI_INFO.TIM`. Outer loop: `TITLE256.TIM` → `playMovie(0)` →
`initializeMusic` → `runLandingScreen` → `finalizeMusic`; `ETCTIM.BIN` →
`initializeMusic` → `runMainMenu` (`TITLE2.TIM`); depending on `MAIN_STATE`: 0
new game (`newGameScene`, `OP2`, partner 3 Agumon or 0x11 Gabumon
depending on `pstat 0xFE`, header *script* 0xCC), 1 continue, 2 `ED2` +
continue; `fadeFromBlack(40)`; `gameLoop` until `MAIN_STATE == 3`;
`cleanupGame`, `finalizeMusic`, `playMovie(3)`.

## Useful writes and breakpoints

For a debugger or an emulator's scripting ([../developing.md](../developing.md)). Addresses are those of the original
executable; for a GCC build look the symbol up in the build's map. In PCSX-Redux's Lua API a breakpoint object must
be kept in a global variable or the garbage collector removes it, and `getMemPtr()` indexes by physical offset
(without `0x80000000`); if a breakpoint does not fire, the interpreter CPU core may be needed.

| Goal | How |
|---|---|
| seed `customRandom` | write the two u32 at `0x80134E68` and `0x8013442C`; only affects the overlays that use it (digivolution, arena, fishing); the BIOS `rand()` state has no fixed address |
| force a BGM | a breakpoint on `playMusic` (`0x800C66D4`) that rewrites `a0` (font) and `a1` (track), then change screens; set `CURRENT_SEQ_FONT` (`0x80134D96`) to −1 first so the font reloads even if it matches |
| play a sound effect or voice | the same on `playSound` (`0x800C6374`): `a0` = bank (0 system, 4 partner, 8 map), `a1` = `program·16 + note − 60`, or the note in banks 3–7 |
| a partner animation | a breakpoint on `startAnimation` (`0x800C1A04`) filtered on `a0 == 0x801557A8` (`PARTNER_ENTITY`), setting `a1` to the slot (e.g. `0x2E` = first technique); it lasts until the partner's state machine changes state |
| an effect | in the world `createParticleFX` (`0x800AD54C`, `a0` type 0–3, `a1` count); in battle (BTL loaded) `BTL_startEFE` (`0x80066260`, `a0` = slot 0–15 of `EFE_LOADED_MOVE_DATA` at `0x80139A0C`) |
| inspect the read queue | 32 entries of 0x44 bytes at `0x80154700`; `state` at `+0x1C` (−1 free, 2 pending, 1 reading, 10 waiting) |

## Notes

- NPC model slot 4 falls at (512,256), on top of `ETCTIM` #5 (`SBOY.TIM`), and its CLUT (96,488) on that of
  `SYSTEM_W`: a fifth simultaneous NPC model would overwrite those textures.
- `handleMusicOverride` mode 2 requests font 6 track 2 and mode 8 font 0x1A track 1, which the jukebox does not list.
- `EFEDAT.EFE` block 110 carries `effectId` 0x158 instead of 0x16E, so if any technique maps to effect 0x16E, the id
  check rejects it (`isLoaded = −3`).
- `EFEX_TABLE` (1.5 KB) is filled at startup and never read: a leftover of loading `FEEL_EF`/`EX` by position.
- `MAIN_STATE == 2` in the main menu plays `ED2.STR` and then continues the game.
- The OT drawing order (entry 32 as the boundary between fixed-screen layers and camera-relative ones) is inferred
  from libgs behaviour.
