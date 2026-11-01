# Frame rate: 20 Hz logic, 30 or 60 fps drawing

How the original engine times a frame (one logic tick per drawn frame, `VSync(3)`, 20 Hz), and how the frame-rate
patches separate drawing from game time: a fixed 20 Hz logic tick, a late-tick phase, render callbacks made
repeatable, interpolation of the camera, entity roots and bones between ticks, and one present helper shared by every
game loop. It also covers the `FPS` build parameter, the OPTIONS FRAME RATE row and how battle speed changes the tick
period.

Patches: 0011, 0026-0047 and 0049 (the core work; 0048 added a lab menu row that 0080 removes), 0074 (`MOD_RENDER_ALPHA`), 0080 (build parameter), 0169/0173/0174
(OPTIONS row), 0184/0187/0196 (battle speed), 0233 (vblank waits that pump the file queue). Source references are
`decomp/src/...` paths and function names of the upstream decompilation; the mod code lives in
`decomp/src/main/main.c` (the helper), `decomp/src/main/world_object.c` (late ticks, deferred removal),
`decomp/include/dw/mod_fps.h` and `decomp/include/dw/mod_present.h` once the series is applied.

## The original timing

### One tick, one frame, 1/20 s

Game logic is tied to the drawn frame. One loop iteration runs input, scripts and every object's tick, then every
object's render, then waits with `VSync(3)` (three vertical refreshes, 1/20 s on NTSC) and swaps. Everything counts
loop iterations:

- the game clock: 20 ticks = 1 game minute = 1.0 s of real time; `PLAYTIME_FRAMES` counts ticks (1200 per minute of
  play time);
- timers, waits and state machines in scripts and objects;
- movement: walking and running are root motion of the animation, advanced once per tick;
- animation keyframes and per-bone velocities;
- battles: 20 ticks per second, AI included.

So the obvious change, `VSync(1)` or `VSync(0)`, makes the whole game three times faster.

"Line" below is one horizontal video line: NTSC has 263 lines per refresh, about 2146 CPU cycles per line at
33.87 MHz. One tick is 789 lines.

### The loops

Every loop that runs the game world has the same tail. Only `gameLoop` runs the pad and the script. Battles are nested
inside a tick: `tamerTick` → `startBattle` → `BTL_battleMain`, which loops on `BTL_battleTickFrame` until the battle
ends.

| Loop | File | Notes |
|---|---|---|
| `gameLoop` | `decomp/src/main/main.c` | the world and everything that is an object in it: minigames (fishing, curling, slots, training), evolution, the ending, the triangle menu. `GsSetOrign`, `GsSetRefView2`, `GsSetProjection` and the `*_COPY` camera snapshots are set **before** `tickObjects`; `handlePause` runs after the swap |
| `newGameScene` | `decomp/src/main/main.c` | the new-game introduction: `tickTextboxHandling`, `newGameStateMachine`, objects |
| `BTL_battleTickFrame` | `decomp/src/btl/battle_main.c` | story battles. The AI (`BTL_tickPartnerAI`, enemy AI, fighter states) runs in `BTL_battleMain` before each call, outside the object list. `GsSetOrign` is called **after** the `VSync` |
| `loadBattleDataTick` | `decomp/src/main/btl.c` | while the battle data and effect files load |
| `STD_battleTickFrame` | `decomp/src/std/std_main.c` | tournament and arena battles |
| `VS_tickFrame` | `decomp/src/vs/vs_main.c` | VS mode |
| `pauseFrame` | `decomp/src/main/utils.c` | draws the pause box, then `handlePause` busy-waits on the pad with nothing drawn |
| title, Press Start, main menu | `decomp/src/main/main.c` | `VSync(0)`: already a tick per refresh; not changed |
| movies | `decomp/src/mov/mov.c` | MDEC player with its own display environment; not changed |

The patches route the first seven through one helper (below).

### The frame pipeline

`GsGetActiveBuff` → `GsSetWorkBase(GS_WORK_BASES[buf])` (two packet areas of 0x14000 bytes) → `GsClearOt` (a
4096-entry ordering table per buffer) → tick and render into that OT and work base → `applyDrawOffset` (a `DR_OFFSET`
at OT entry 32, so entries below 32, the UI, stay at fixed screen coordinates) → `DrawSync(0)` (waits for the GPU to
finish the **previous** OT) → `VSync(3)` → `GsSwapDispBuff` → `GsSortClear` → `GsDrawOt`. The CPU work of frame N
overlaps the GPU drawing of frame N-1.

Every global packet and sub-OT is indexed by `ACTIVE_FRAMEBUFFER` (`DR_OFFSETS[2]`, `FRAMEBUFFER_OT`, the STD, VS,
curling and scene sub-OTs); global `GsSPRITE`s are templates copied into the work base by `GsSortSprite`. There are no
single-buffered primitives, so a pass can be repeated without new buffers: each pass takes the other buffer, clears its
OT and resets its work base, and the `DrawSync(0)` before the swap guarantees the GPU is done with the buffer being
reused. New code must keep it that way.

### The object system

`decomp/src/main/world_object.c`: `WORLD_OBJECTS[128]` of `{objectId, instanceId, tick, render}`. `addObject` takes the
first free slot, `removeObject` frees one by `(objectId, instanceId)`. `tickObjects` calls every non-NULL tick in slot
order, then `renderObjects` every non-NULL render in slot order. There are no priorities: the order is creation order
with holes reused. Draw order comes from the OT index, not call order. See [engine.md](engine.md) for the object ids.

### What the tick writes and the render reads

**Entities** (`decomp/include/dw/entity.h`). `posData` is one `PositionData` per bone: `{GsDOBJ2 obj; GsCOORDINATE2 posMatrix;
VECTOR scale; SVECTOR rotation; VECTOR location}` (0x88 bytes). `anim` (`EntityAnim`) holds the frame, the instruction
pointer, the root position `locX/Y/Z` (17.15 fixed point) and a `MomentumData` per bone. The tamer has 17 bones, a
Digimon up to 32 (`boneCount`), the partner array 34.

- Tick: `tickAnimation` → `tickMomentum` (`decomp/src/main/anim.c`) adds per-tick velocities to every bone's scale,
  rotation and location (delta / divisor with a remainder) and rebuilds `posMatrix.coord` (`calculatePosMatrix`, which
  clears `flg`). For bone 0, `applyRootMomentum` moves `anim.locX/Y/Z` by the root velocity rotated by the model
  matrix and writes `location`; it reads `posMatrix.coord` as the direction for the next step. Keyframe instructions
  only change velocities, so bone state is continuous; `startAnimation` is the exception and snaps every bone to the
  new animation's first pose. `tickAnimation` returns early when `animFlag & 1` is clear, so a rotation written to a
  stopped entity stays invisible until its next `startAnimation`.
- Facing is written by AI or state code: `entityLookAtLocation` (instant), `setTamerDirection` (8 directions), the NPC
  `rotateEntity` (gradual and not masked: it can leave 0..4095 and then snap, a 4096 jump in the stored value).
- Render: `renderDigimon` (`decomp/src/main/model.c`) only reads. Per bone with a TMD: `GsGetLws` (recomputes `workm`
  down the parent chain where `flg == 0`), `GsSetLightMatrix`/`GsSetLsMatrix`, `GsSortObject4`; then the drop shadow,
  which reads `location`. Effects that follow bones (entity particles, condition bubbles, butterflies) read `workm`,
  i.e. whatever the last render computed.

**World camera.** `GS_VIEWPOINT` is fixed per map (`loadMapSetup`). Scrolling is 2D only:

- `DRAWING_OFFSET_X/Y` goes to `GsSetOrign` and moves all 3D (the GPU adds the offset).
- `MAP_TILE_DATA.cameraX/Y` places the 128×128 background tiles (`setPosDataMapTile`): tile x is
  `posX - 160 - cameraX + 160 - DRAWING_OFFSET_X`, and the GPU adds `DRAWING_OFFSET_X`, so a tile lands at
  `posX - cameraX`.
- `tickCameraFollowPlayer` adds the tamer's screen delta to `cameraX/Y` and subtracts it from `DRAWING_OFFSET`
  (`updateDrawingOffsets`), then `handleTileUpdate` moves the 4×3-tile VRAM window with `LoadImage` + `DrawSync(0)`.
  In the original it is called **from `renderMap`**, i.e. from the render.
- One-tick lag: `GsSetOrign` uses the offset from before this tick while the tiles use the `cameraX` updated in this
  frame's `renderMap`. The two cancel, so tiles and models agree. Interpolation has to keep this pairing.
- Script camera moves: `tickCameraMovement` (object 0xFB1), `moveCameraByDiff`/`moveCameraByOffset`,
  `tickMeramonShake`.

**Battle cameras.** Story battles keep the map view; effect opcodes 63/64 (`BTL_setupFixedCamera`,
`BTL_restoreCameraView`) call `GsSetRefView2` and write `DRAWING_OFFSET` from the effect engine's tick. Tournament and
VS camera modes write `GS_VIEWPOINT` or build their own matrix (`STDVS_CAMERA`, `GsSetView2`) in tick objects
(`decomp/src/std/std_main.c`, `decomp/src/vs/vs_camera.c`). HUD renders switch projection and view temporarily and
restore them with `GsSetRefView2(&GS_VIEWPOINT)`.

**Effects** are mostly "counter in the tick, geometry in the render": `tickParticleFX`/`renderParticleFX`, clouds,
healing particles, butterflies, bubbles (`decomp/src/main/efe.c`, `particle.c`, `bubble.c`), and the battle effect
engine (`BTL_tickEFEEngine` runs scripts, UV animations and particle emitters; `BTL_renderEFEEngine` runs each
effect's render script).

## Render callbacks that change state

Drawing a tick several times requires `renderObjects()` to be repeatable: N calls per tick must leave the same game
state as one. In the original many renders advance state. Each is handled one of four ways:

- **late tick**: the mutation moves to a per-object late tick that runs once per tick, after all ticks, in the slot
  order the renders ran in. A plain tick would not do: it runs in slot order among the other ticks, possibly before
  `tamerTick`, so the camera follow would lag one more tick (breaking the tile/offset pairing) and a fade counter
  would be seen one tick early by the map change;
- **rollback**: the value is saved before the first pass; extra passes start from that value; the first pass's result
  is put back after them;
- **pass-0 guard**: the side effect happens only when `MOD_RENDER_PASS == 0` (central guards: `playSound`,
  `playSound2`, `drawString`, `clearTextSubArea`);
- **render RNG**: `rand()` in a render becomes `modRenderRand`/`modRenderCustomRandom` (below).

`randomLimit()` (`decomp/src/main/math.c`) is `rand()`, the same stream as stat gains, drops, injuries, learning and
AI. A `rand()` in a render run three times per tick would change gameplay outcomes; `customRandom()`
(`decomp/src/main/rng.c`) is a separate generator.

| Render (original) | What it advanced | Handled by | Patch |
|---|---|---|---|
| `renderMap` (object 0xFA0) | camera follow, `cameraX/Y`, drawing offset, VRAM tile uploads, `CAMERA_*_PREVIOUS`, the daytime check | late tick `lateTickMap` | 0029 |
| `renderMapOverlays`, `renderMist`, `buildSnowflakePrim` | map sprite timers and frames, mist offsets, snow positions with two `randomLimit()` per flake | `tickMapOverlays`, `tickMist`, `tickSnowflake` from `lateTickMap`; renders draw a recorded list | 0029 |
| `renderNinjamonEffect` | position, two `randomLimit()`, counter, self-removal | `lateTickNinjamonEffect` | 0029 |
| `renderFadeIn` / `renderFadeOut` | `FADE_IN/OUT_CURRENT`, `FADE_PROGRESS`, removal, `FADE_PROTECTION` (scripts and map changes wait on them) | `lateTickFadeIn` / `lateTickFadeOut` | 0030 |
| `renderUIBoxAnimated` | box frame, state, removal, close sound | `lateTickUIBoxAnimated`; the render draws `MOD_UI_BOX_DRAW_FRAME` | 0031 |
| `renderGameClock`, `renderStatusBars` | `CLOCK_OFFSET_X`, `STATUS_UI_OFFSET_X` slides | `lateTickGameClock`, `tickStatusBarsSlide` | 0032 |
| `renderEntityText` (damage and heal numbers) | rise, frame, slot release | `lateTickEntityText` | 0033 |
| menu views in `decomp/src/main/game_menu.c` | `MENU_STATE`, `MENU_SUB_STATE`, `MEDAL_ROTATION`, `UI_BOX_DATA` resize, text uploads | rollback; uploads by the pass-0 guard | 0034 |
| `renderDigiviceEntity` | `startAnimation` + `tickAnimation` on the live partner | runs every pass; extra passes put the entity back where it was before pass 0 | 0034 |
| `renderMonochromonMoodBubble`, item and award text boxes | `MONOCHROMON_BUBBLE_TIMER`, `TEXTBOX_OPEN_TIMER` | rollback | 0034 |
| `renderFlatDigimon`, Toy Town box lids | blink timer, lid state | advance on pass 0 only | 0034 |
| `renderWireframed`, `EVL_renderSparkStreak`, `ENDI_renderParticles`, finisher aura | `rand()` / `customRandom()` | render RNG | 0034, 0041 |
| `BTL_renderPartnerStatusBars`, `BTL_renderEnemyHPBars` | `damageTick` moves `hpDamageBuffer` into `currentHP`; enemy bar timers | rollback of `COMBAT_DATA` and the fighters' `Stats` | 0040 |
| `BTL_renderFinisherGauge` | pulse counters, `BTL_FINISHER_READY` | rollback | 0040 |
| `BTL_renderBattleStartText` / burst | letter pieces, colour timer, `BTL_BATTLE_TEXT_FINISHED` (the battle start waits on it) | rollback while the text exists (`BTL_START_TEXT_ACTIVE`) | 0040 |
| `BTL_renderCommandShout`, `renderFleeBubble`, finisher chargeup | frame counters, self-removal | rollback; removal with `removeObjectAfterRender` | 0040 |
| `renderPostBattleStatsBox` | `STATS_GAINS` counted into `INITIAL_COMBAT_STATS[0]`, sounds | rollback (main executable list) | 0040 |
| `BTL_renderEFEEngine` | effect render scripts: own variables, `rand()`, sounds, CLUT uploads, spawns | see "Effect render scripts" | 0041-0043 |
| `STD_renderBracket` | the whole bracket simulation (`STD_updateBracket`: animation, sounds, objects, next match) | late tick `STD_lateTickBracket` (object 0x1AE) | 0045 |
| STD/VS status bars, HP bars, start text, intro name and stats, finisher gauges | as in the story battle; `*_INTRO_DATA_RENDERED_CHARACTERS` the intro waits on | rollback; intro sounds by the pass-0 guard | 0045 |
| `VS__renderSelectDigimonPlayer` | select panels scroll and blink (`VS__SELECT_DIGIMON_DATA`) | rollback | 0045 |

Renders that only rebuild matrices from state each time (doors, chests, warp crystals, poop, the STD/VS model scenes
that overwrite `GsWSMATRIX` and restore it) are already repeatable. `renderDigimon`, drop shadows, map names, text
boxes (text reaches VRAM from the tick side, `drawTextboxStrings`), the efe.c effects, butterflies, bubbles and the
battle status effects are pure.

**Prims added from a tick.** A tick that adds primitives straight into the OT puts them in the first pass only, so they
would flicker. In the main executable these are `tickMeramonShake` (`addMeramonShakePrim`) and the save machine menu,
drawn from the script tick (`scriptTickMainMenu`, `tickSaveMachine` call `renderMainMenu`). Both are added again at the
start of each extra pass, before any render so the OT order matches (`modReplayTickPrims`, `modReplayMainMenu`; the
menu from the scroll position it had before the tick drew it). In the tournament the bracket's projectiles and hit
flashes draw from their ticks; the STD overlay records them and replays them through `ModRollbackSet.replay`.

**Draw-then-advance renders.** The map sprites, snow and entity text drew the current state and then advanced it.
Their late ticks first record what the render must draw (sprite frame, position and layer; for snow, x after its move
and y before its fall plus that tick's jitter; which text entries on which layer) and then advance, so the picture is
the original one. A UI box that finishes closing, or a damage number on its last frame, still draws that frame:
`removeObjectAfterRender` frees the slot after all passes (`modFlushRemovals` at the next `modTickStart`; up to 16
pending, beyond that the removal is immediate).

## The present helper

`decomp/include/dw/mod_present.h` (the part overlays include) and `decomp/src/main/main.c`:

```
void modTickStart(int32_t flags);                         /* before the loop's logic */
void modPresent(int32_t flags, ModRollbackSet *extra);    /* after tickObjects, instead of render + VSync(3) + swap */
#define MOD_PRESENT_BATTLE 1  /* the loop sets the 2D origin from DRAWING_OFFSET at each swap */
#define MOD_PRESENT_PAUSE  2  /* pauseFrame: use the rollback set of the loop that paused */
```

All seven loops call it: `gameLoop` (0039), `BTL_battleTickFrame` (fight, intro, victory pose and result screens) and
`loadBattleDataTick` (0040), `newGameScene` (0044), `STD_battleTickFrame` and `VS_tickFrame` (0045), `pauseFrame`
(0046).

### One tick

1. `modTickStart`: flush pending removals, `MOD_RENDER_PASS = 0`, record the tick's start refresh. With
   `MOD_PRESENT_BATTLE` the tick is counted from the previous tick's last `VSync`, as `VSync(3)` did, so the battle AI
   that runs before the loop function is part of the tick.
2. The loop's logic and `tickObjects()`.
3. `modPresent`:
   - the late tick phase, `lateTickObjects()` (in battle loops it is reached through `renderObjects()` by a flag
     `tickObjects()` sets, so fades and UI boxes keep working there without touching the overlays);
   - `MOD_FPS_TICKS++`; the interpolation snapshot;
   - save the rollback set (built-in list plus the loop's `extra` set) and the libgs view state of pass 0;
   - pass 0: `renderObjects()`, `applyDrawOffset`, `DrawSync(0)`, wait for the refresh it is due at, swap;
   - each extra pass: roll back, restore pass 0's view state, replay tick prims, apply interpolation for its alpha,
     `renderObjects()`, restore the interpolated fields, swap at its refresh;
   - put pass 0's rolled-back values back; wait until the tick's third refresh (`tickStart + 3`).

`MOD_RENDER_PASS` is 0 during the tick, the late tick and the first pass, and 1, 2 on the extra passes.
`MOD_RENDER_MULTIPASS` is set around the passes.

**When passes are shown.** A tick always lasts 3 refreshes. With n passes in the tick, pass r is shown at refresh
`tickStart + (r + 1) * 3 / n`, and every swap waits for a vertical blank. Mode 0 (20 fps) shows one pass at the third
refresh, as the original. Mode 2 (60 fps) shows passes at refreshes 1, 2, 3. Mode 1 (30 fps) shows a frame every other
refresh by tick parity (`MOD_FPS_TICKS`, so a late tick does not break the pattern): one frame at 2/3 of the tick, or two
at 1/3 and 3/3.

**Budget check.** An extra pass is skipped if its refresh has already passed, or if it would not end before the tick's
third refresh (the cost of pass 0 plus the measured pass setup against the lines left since the last vblank). Without
the check a pass ending a few lines late would stretch the tick to 4 refreshes (game at 15 Hz). So a slow scene drops
frames, never game speed, and is never slower than the original. A whole tick that is late loses time as the original
does; ticks are not run back to back.

**View state of the extra passes.** `DRAWING_OFFSET` and `GS_VIEWPOINT` already hold the post-tick values, while pass 0
renders with the origin and view set before `tickObjects` (the one-tick lag) plus whatever the tick set. Extra passes
therefore restore what pass 0 had: `POSITION`, `GsWSMATRIX`, `GsWSMATRIX_ORG`, `GsLIGHTWSMATRIX` and the projection
(`ReadGeomScreen`), saved right before pass 0. After the last pass the libgs view is left as a single
render would leave it.

**Battle origin.** Loops with `MOD_PRESENT_BATTLE` set `GsSetOrign` before each pass's swap from the (interpolated)
offset; `GsSetOrign` only sets libgs' `POSITION`, which `GsSwapDispBuff` applies at the swap, so this matches the
original's call after `VSync`.

**Pause.** `pauseFrame` with `MOD_PRESENT_PAUSE` rolls back the state of the loop that paused (the set of the last
`modPresent` without the flag), since the original pause frame runs `tickObjects` and the renders too.

**Copies.** Struct assignments and `memcpy` in main.c call the BIOS `memcpy`, which runs from ROM; the pass code copies
words itself (`modCopy`, `modCopyBytes`), about 5 lines less per extra pass (0035).

### Rollback sets

The built-in list (main executable) covers the menu counters, text box timers, `UI_BOX_DATA`, the post-battle stat
count and the flee bubbles. An overlay adds its own state with

```
typedef struct { void *ptr; int32_t size; } ModRollbackVar;
typedef struct {
    const ModRollbackVar *vars; int32_t count;
    uint32_t *pre; uint32_t *post;   /* each at least the sum of the sizes, rounded up to 4 */
    void (*replay)(void);            /* re-adds prims the caller's ticks put in pass 0's OT, or NULL */
} ModRollbackSet;
```

filled each tick (`BTL_modRollbackAdd`, `STD_modRollbackAdd`, `VS_modRollbackAdd`). BTL, STD and VS each keep two
5.6 KB buffers (`*_MOD_ROLLBACK_PRE/POST`) for `COMBAT_DATA`, both fighters' `Stats`, the start text pieces (only while
the text exists, about 3.1 KB), the finisher gauge arrays and the intro letters. Rollback keeps the original order
exactly (the HP bars drain `hpDamageBuffer` after every tick and before any other render reads `currentHP`) with no
change to the renders. One value is not restored: the enemy HP bar's screen position in `COMBAT_DATA`, a draw cache
the bar writes from the entity's (interpolated) position just before drawing; nothing reads it.

### Render random numbers

`modRenderRand()` and `modRenderCustomRandom(min, max)` call the real generators on the first pass, so with one
render per tick the streams are exactly the original ones. The first pass logs what it drew
(`modRenderRandRecord`, a 1 KB log) and the extra passes get the same numbers back in order (`modRenderRandReplay`,
0042): random sparkles and colours change once per tick, as at 20 fps, and the game's generators only advance on the
first pass. Past the log's end, a private LCG answers. `rand()` is a BIOS call; under OpenBIOS its seed is the
word at `0x80008464`, useful for checks.

## Interpolation

Extra passes show the scene between the previous and the current tick. Alpha is the refresh the pass will be shown
at, minus the tick's start, over 3: 1/3, 2/3, 1 at 60 fps. The alpha-1 pass is not touched at all, so it is the
uninterpolated picture. Interpolation adds up to one tick (50 ms) of display latency; input is still read at 20 Hz.
Effects, particles, entity text and UI move at 20 Hz; those placed from a bone's `workm` follow the interpolated
position.

`MOD_RENDER_ALPHA` (0074) holds the current pass's alpha (0..4096, 4096 outside interpolation) for any render that
wants sub-tick motion: the status bubbles' movement and bob (`decomp/src/main/bubble.c`, patches 0074 and 0155, which
keep the previous tick's positions) and the imported-animation transition blend (patch 0217, which adds `MOD_RENDER_ALPHA` to
`MOD_FPS_TICKS * 4096`).

Angles (4096 = one turn, values may lie outside 0..4095) use the shortest arc: sign-extend the low 12 bits of
`cur - prev` and add `delta * alpha >> 12` (`modLerpAngle`).

### Snapshot and snaps

The snapshot (`modInterpSnapshot`, about 5 lines) runs once per tick after the late tick and before the first pass:
the current values become the previous ones. A tick is not interpolated (it "snaps") when:

- `MOD_INTERP_MAP_GEN` changed (bumped in `setupMap` and `unloadMap`);
- `GS_VIEWPOINT` or `GAME_STATE` changed, or the loop switched between a world and a battle loop;
- `GsWSMATRIX` at the first pass changed in a story battle (the effects' fixed camera, opcodes 63/64);
- a camera value moved more than 64 px, or an entity root more than 256 units on an axis;
- the tick started more than 6 refreshes after the previous one (a battle or load ran inside it);
- interpolation was just switched on (`modInterpInvalidate`).

Teleports and placements are caught by the thresholds, `isOnScreen` going 0 → 1 by the "drawn in both ticks" rule
below, and `startAnimation` keeps the root continuous.

### World camera (0036)

Snapshot: `POSITION` as the first pass uses it (the pre-tick `DRAWING_OFFSET` of the one-tick lag), and
`MAP_TILE_DATA.cameraX/Y` plus `DRAWING_OFFSET_X/Y` after the tick. Each is lerped on its own, which keeps the lag:
tiles (and map sprites, which use the same formula) land at `posX - (cameraX + DRAWING_OFFSET_X - POSITION.offx)`,
linear in alpha between two values that already agree with the 3D. The lerped values are written into the globals for
the pass and restored after `renderObjects` (`POSITION` after the tick's last swap). Walking right in File City the
background scrolls 3/2/3 px per frame instead of 8 every third frame, while the followed tamer stays within the same
±0.5 px on screen as at 20 fps.

- **VRAM tile window.** The 4×3 window shifts when the camera crosses thresholds with about 10 px of margin
  horizontally (`cameraX` 0x8A..0xF6 for column 1) and none vertically. A pass whose interpolated background needs
  tiles outside the window (further out than the tick's own camera, which with the lag can already be 3 lines out at a
  row switch, as in the original) gets alpha raised in steps of 1/8 until it fits (`modTilesCovered`). The camera moves
  at most 8 px per tick, so only the row switch triggers the clamp.
- **Mist** is drawn in screen space and moved by the camera step in `tickMist`; `renderMist` adds the same step for
  the interpolated camera (`MOD_MIST_SHIFT[3]`).

### Entity roots (0037)

Bone 0 of each `ENTITY_TABLE` entry: the translation of the built `coord` (not `location`, which collision code can
change after the matrix was built), `location` separately (the drop shadow reads it), rotation per axis and scale. An
entity is interpolated only when

- its `coord` changed during the tick and equals what `RotMatrix(rotation)` + `ScaleMatrix(scale)` build (so a
  rotation written to a stopped entity stays invisible, and code that writes `coord` directly is skipped:
  `decomp/src/main/model.c`, the BTL/STD/VS effect files and fishing do);
- it is drawn (`isOnMap`/`isOnScreen`) in both ticks, with the same pointer and type.

Per pass the root `coord` is replaced, `flg = 0` is set on every bone (so `GsGetLws` recomputes the children), and
after the pass the tick's `coord` is restored with `flg = 0` again. If the last pass of a tick was interpolated (heavy
screens skip the alpha-1 pass), `workm` is recomputed with `GsGetLws` so ticks that read it see the original values.
Render code that moves an entity itself calls `modInterpUnapplyEntity` first to get the tick's values back
(`renderDigiviceEntity` does).

### Every bone (0038)

`MOD_FPS_INTERP_BONES`: 0 = roots only, 1 = tamer and partner, 2 = all (default).

- Only the previous tick's rotation, location and scale of bones 1..n are kept (int16, 18 bytes per bone, 5.6 KB for
  10 entities of up to 32 bones); the current values are the live fields. A pass builds each bone's `coord` from
  interpolated values (`TransMatrix`, `RotMatrix`, `ScaleMatrix`, as `calculatePosMatrix`), saves the `coord` it
  replaces (a pool of 128 matrices, 4 KB) and copies it back after the pass, so the tick sees its own matrices bit for
  bit.
- A skeleton is interpolated only if its animation ran during the tick (`animFlag` set, so `tickMomentum` rebuilt every
  bone from its fields), every moved bone's translation equals its location, and the root qualifies as above.
- `startAnimation` calls `modInterpAnimStarted`: that tick shows the new pose on every pass, as at 20 fps; pose jumps
  are shown, never blended.
- Bones that move less than 4/4096 of a turn, 2 units or 16/4096 of scale in a tick are left alone (invisible, and the
  cost is per bone).
- The Digivice view restarts the partner's animation from its render, so its skeleton is not kept that tick.

### Tournament and VS camera (0049)

These cameras move every tick, mostly through `GsSetView2` with `STDVS_CAMERA`, some states through `GS_VIEWPOINT`.
Battle loops interpolate the first pass's `GsWSMATRIX`/`GsWSMATRIX_ORG` and projection between two ticks element by
element, and `GS_VIEWPOINT`/`VIEWPORT_DISTANCE` as well when the first pass's view is the one
`GsSetRefView2(&GS_VIEWPOINT)` gives (so renders that set the view again from it, the model scenes and the start text
burst, get the interpolated one). A step over 512/4096 in a rotation element, 1024 units of translation or 64 of
projection is a cut and snaps. In story battles `GS_VIEWPOINT` only changes on those cuts.

## Effect render scripts on extra passes (0041-0043)

`BTL_renderEFEEngine` must run on every pass: its primitives are needed on every frame. But render scripts write their
own variables (the script/data area in front of the effect's TMD) and call `rand()` (opcode 2) and `customRandom`
(sub-opcode 41). On the extra passes:

- the script/data area of every slot with a running sub-effect is copied aside before its scripts and put back after
  them (`modEfeAreaSave`/`modEfeAreaRestore`, main executable). In story battles the copy goes into the top of the free
  part of the EFE heap, right below the overlay and at least 0x5000 bytes above the heap pointer, clear of an effect
  file being loaded and set up (up to 11 KB for the largest effect file). In the tournament and VS it goes below the
  arena model at `ARENA_TMD_ADDR` (0x80038000), since the area between it and the overlay is not free there.
  `MOD_FPS_EFE_NO_ROOM` counts a slot that would not fit (expected 0);
- the interpreter's target, hit and section indices are put back;
- random numbers come from the render RNG (the finisher aura's too);
- the opcodes that reach outside the effect do nothing: sounds, CLUT uploads (`LoadImage` + `DrawSync`), particle
  emitters, flashes, clouds, entity particles, attack objects, the three hit tests, turning the source entity, and the
  "finished" mark.

`decomp/src/std/std_effect.c` and `decomp/src/vs/vs_effect.c` get the same changes. Effects therefore appear on every
frame but move at 20 Hz.

## Choosing the frame rate

### The FPS build parameter (0080)

```
make TOOLCHAIN=gcc FPS=60          # in the decomp tree
FPS=30 tools/build-full.sh         # the full disc
```

`FPS` is 20, 30 or 60 (anything else stops the build; the Makefile default is `FPS ?= 60`). It is written to the
generated header `fps.h`, so a change rebuilds what depends on it. `decomp/include/dw/mod_fps.h` maps it to `MOD_FPS_MODE`:

| FPS | `MOD_FPS_MODE` |
|---|---|
| 20 | compile-time 0: one render per tick at the third refresh, as the original. The extra passes, the render random replay and the interpolation in `modPresent` compile out (the helper is under 1 KB instead of about 9.6 KB); the interpolation tables stay, so the memory layout is the same in all builds |
| 30 | the variable `MOD_FPS_MODE_RUN`, 1 at start |
| 60 | the variable `MOD_FPS_MODE_RUN`, 2 at start |

`MOD_FPS_BUILD` is a read-only word in RAM (20, 30 or 60) that tells tools which build is running. The game logic runs
at 20 Hz in every build. See [../building.md](../building.md) for the build itself.

### OPTIONS FRAME RATE (0169, 0173, 0174)

In an `FPS=30` or `FPS=60` build the title menu's OPTIONS row FRAME RATE switches `MOD_FPS_MODE_RUN` between 0
(20 FPS, the original) and 2 (60 FPS), and the choice is kept in the save's options record. In an `FPS=20` build the row
does nothing. Row layout, defaults and the saved record: [../mods/options.md](../mods/options.md#frame-rate).

## Battle speed (0184, 0187, 0196)

R2 in a battle switches x1 / x2. The switch, its plate and the arming are resident in `decomp/src/main/mod_qol.c`
(`modSpeedInput`, `modSpeedBeforeTick`, `modSpeedPlateAdd`/`Remove`) and shared by BTL (the fight), STD (from a
match's intro to its end) and VS (its fight loop, first pad). Patch 0197 draws the plate as a button with
fast-forward arrows.

- `MOD_BATTLE_FAST` is the switch (kept until the console resets). Before each tick the overlay calls
  `modSpeedBeforeTick(held)`, which sets `MOD_BATTLE_FAST_TICK` unless the fight is held at x1 (BTL: the item menu
  open, an item in hand, the defeat countdown running). `modTickStart` consumes it into `MOD_TICK_FAST` for loops with
  `MOD_PRESENT_BATTLE`.
- Fast ticks go in pairs over 3 refreshes, 40 ticks a second. The first of a pair is due 2 refreshes after the pair
  began and is shown, with one render. The second (`MOD_REAL_TICK` 0) is rendered, because render functions advance
  state (effect scripts, gauges), but its frame is thrown away and it waits for no refresh. A tick plus its render take
  about 270 of a refresh's 263 lines in a fight, so one shown frame per fast tick could not pass 30 ticks a second.
- Each fast tick is due from when the one before was due (`modFastDue`), not from when it ended, unless that is more
  than a pair behind.
- A fast tick has one pass whatever the frame rate.
- `tickPlaytime` skips `MOD_REAL_TICK` 0 ticks, so play time stays real time. The fight's logic per tick is unchanged;
  only the real time between ticks changes. A finisher charge press counts twice at x2 (BTL and STD).

## Battle data load pumping (0233)

All waits for a vertical blank in `modPresent` go through `modWaitVblank`. While `MOD_LOAD_PUMP` is set (a battle's
data loading for the quick battle start), it steps the file queue (`tickFileReadQueue`) until the vblank comes,
instead of letting the queue take one step per tick; at 20 steps a second the steps, not the disc, were most of the
wait. See [combat.md](combat.md) for the quick start.

## Cost and what fits

Lines per tick (CPU, measured in an emulator with the dynamic recompiler; averages):

| Screen | tick | first pass | extra pass |
|---|---|---|---|
| Jijimon's house | 65-80 | 215-235 | 200-210 |
| File City | 57-77 | 120-130 | 110-125 |
| Native Forest, a wild Digimon on screen | 135-150 | 175-195 | 160-170 |
| Freezeland (snow) | 100 | 240-265 | 225 |
| Story battle with effects | 75 | 225 | 190-200 |

Root and camera interpolation cost about 5 lines per pass while things move and nothing when they do not; all bones
cost 10-25 lines per pass plus 3-10 per tick for the snapshot. In battle, interpolating 3 skeletons (about 33 bones)
costs 10-14 lines per pass.

- 60 fps needs, per refresh, `render + tick / 3 ≤ 263` lines on the CPU and the GPU's drawing time per frame under
  263. 30 fps (6 refreshes = 2 ticks + 3 passes) needs `3 × render + 2 × tick ≤ 1578`.
- At the original CPU speed: File City reaches 40-60 fps, Native Forest about 40, Jijimon's house 20-40 depending on
  the emulator, Freezeland near 20 (tick plus render already exceed a refresh), and a fight with effects 25-35. A pass that does not fit is
  skipped, so no scene runs slower than the original.
- In both emulators measured, the GPU wait is about 0: this game's GPU time (small flat and gouraud polygons, one
  full-screen background) fits inside its CPU time, so the limit is the CPU. An emulator CPU overclock of 200 % gives
  a locked 60 fps in every scene tried. On a console, 30 fps is the realistic expectation where one extra pass fits,
  and evenly paced; 60 fps there would alternate 2 and 1 passes per tick.
- Background tiles are 12 `POLY_FT4` (negligible CPU); a typical Digimon model is about 400 TMD primitives, about 35
  lines per model with `GsSortObject4`.

## Curling (0292)

The KAR overlay draws its HUD on every pass. Its yes/no and hint prompts still draw from the tick, so `KAR_replayTickPrims` repeats them at the start of each extra pass, in the first pass's OT order. The arrow pulse and ready timer
advance in `KAR_tick` only; the arrow keeps the original pre-physics origin and
interpolates its displayed direction. A late tick records stone positions after
physics and evaluates held stones from the nominal hand matrix. Rendering uses
local interpolated positions, or the interpolated hand, without writing those
positions back into physics. Selection, removal, match resets and moves over
512 units snap; the held-to-released transition remains continuous. The previous
poses and validity flags stay in KAR, outside the resident small-data sections.
The camera tile-coverage guard chooses the effective fraction before applying
any interpolation; it publishes that fraction as `MOD_RENDER_ALPHA`, so the
view, camera, actors and stones stay together at tile-window boundaries.

`KAR_updateCollisions` keeps positive-state stones in their original row/slot
order and scans that compact list. Stationary stones remain included. All
eleven substeps, the repeat of a colliding final substep, resolver argument order,
rounding, friction and collision functions are unchanged. Resolvers preserve
positive states, so the list remains valid throughout the tick. Before this
change the scanner consumed about 393,000 CPU cycles per throw tick even with
no resolved collisions; square roots accounted for less than 1% of that cost.
The differential test extracts both C implementations and checks callback order,
coordinates and resulting state across 40,960 fixtures. The SDK square-root
lookup has a different cutoff from exact integer square root; it is preserved.

Curling's forced background uploads were cheap when the whole TFS stayed in
RAM. With streaming they synchronously reread three CD rows repeatedly during
camera returns. KAR now checks the streamer's existing VRAM cell identities,
keeps cells already displayed, and uses the ring for actual replacements. The
12-byte identity table is exposed without changing its size; the helper stays
in KAR. Tile replacement is deferred until all CPU geometry preparation is
complete, before submitting the new ordering table. This overlaps preparation
with the previous GPU draw: a row crossing previously waited about 155 scanlines
in tick-side VRAM readback. The native row uploader defers while the tamer is
in curling. The forced whole-window upload of `handleTileUpdate` is skipped too (patch 0295): moving the aim camera reread three CD rows per step, 9 ticks/s with stalls of about 0.7 s. Camera targets, movement and tile destinations remain unchanged.

The intro samples tick/render cost after three cold setup ticks, allows half
a render of headroom for the HUD/previews that appear later, and chooses a cadence for the entire match:
the player's requested rate when 60 fits, otherwise steady 30. The 20 FPS option
always takes precedence. This avoids oscillating between one and two extra
passes as the camera moves. The overlay arms `MOD_RENDER_CADENCE` each tick;
`modTickStart` clears it, so other scenes retain their existing scheduling.

At 30 FPS the display deadlines are refreshes 2, 4 and 6 over two nominal
three-refresh ticks. After the single-pass half, the helper uses its unused
third refresh to compute the next tick early. Nominal tick timestamps remain
three refreshes apart, and interpolation uses those timestamps. Logic therefore
advances twice per six refreshes, while input is sampled one refresh early on
that half of the pair. Forced-period comparisons disable this cadence override
to exercise all three passes; actual-cadence comparisons use `KC_PERIOD=0`.

The PCSX refresh capture of the initial cadence implementation showed 58 aiming
and 119 throw display intervals, all exactly two refreshes, with no late frames.
The score box appeared in all 240 throw refreshes, versus 165/240 before the fix.
At the VSync sample immediately preceding each render-counter increment, all
120 submitted stone matrices matched the recorded poses and `MOD_RENDER_ALPHA`.

The final DuckStation software-renderer checks requested 60 FPS. At CPU 100%,
all four states (aim, power, throw, tally) stay at 30 FPS; at CPU 200% and 250%
they stay at 60 FPS. Enabling 8 MB alone changes neither cadence nor results.
The original 2 MB profile remains the target. Rates are nominal; NTSC uses
59.94 refreshes/s. Aiming's 294 render lines alone exceed a 263-line refresh at
100%, so the match keeps steady 30 even when an individual throw is cheaper.

With seed `0x12345678`, all six profiles and the final 20 FPS option finish ten
throws at 2–2 with identical recorded state, RNG, aim and power on 2,798 ticks.
The baseline 20 FPS disc also matches every recorded tick and all ten released
stone trajectories. Recording starts after nine uninterrupted calibration ticks;
those intro ticks are not part of the hash. Per-state refresh captures check
HUD pixels, display spacing, stone/hand matrices and counters separately from
replay timing, which debugger pauses can distort.

Resident `main_BSS_END` changes from `0x801cb9fc` to `0x801cba40` (+68 bytes);
aligned heap falls by 80 bytes. KAR contains the history and tile helper.

## RAM variables

| Symbol | Meaning |
|---|---|
| `MOD_FPS_BUILD` | the build's `FPS` (read-only) |
| `MOD_FPS_MODE_RUN` | run-time mode in FPS=30/60 builds: 0, 1, 2 |
| `MOD_FPS_TICKS` | logic ticks presented through the helper |
| `MOD_FPS_RENDERS` | render passes |
| `MOD_RENDER_PASS` | 0 in the tick and first pass, 1, 2 on extra passes |
| `MOD_RENDER_MULTIPASS` | set around the passes (removals wait) |
| `MOD_RENDER_ALPHA` | this pass's fraction of the tick, 0..4096 |
| `MOD_RENDER_CADENCE` | 0 = inactive; 1/2 = normal/early half of steady 30 FPS; 4 = curling at requested rate with deferred tiles; reset at each tick; preserves the player's 20 FPS option |
| `MOD_FPS_INTERP` | interpolation on (1, default) or off; test switch |
| `MOD_FPS_INTERP_BONES` | 0 / 1 / 2, see above; test switch |
| `MOD_FPS_TEST_TICK` | test switch: every tick lasts that many refreshes (0 = off) and every pass is rendered at its fraction of the tick |
| `MOD_INTERP_MAP_GEN` | map setup/unload counter (snap) |
| `MOD_INTERP_STATS` | interpolation counters (entities, skeletons, snaps) |
| `MOD_MIST_SHIFT[3]` | mist correction for the interpolated camera |
| `MOD_FPS_EFE_NO_ROOM` | effect slots not rolled back for lack of room |
| `MOD_PERF_*` | timing counters, below |
| `MOD_BATTLE_FAST`, `MOD_BATTLE_FAST_TICK`, `MOD_TICK_FAST`, `MOD_REAL_TICK` | battle speed |
| `MOD_LOAD_PUMP` | file queue pumped in vblank waits |

**Timing counters** (0011, 0027). In lines read from root counter 1 (`0x1F801110`, a free-running hblank counter, so
differences are elapsed lines across vblank waits): `MOD_PERF_TICK_SUM/MAX` (input, script, `tickObjects`),
`MOD_PERF_RENDER_SUM/MAX` and `MOD_PERF_GPU_SUM/MAX` (first pass and its `DrawSync` wait), `MOD_PERF_XRENDER_*`,
`MOD_PERF_XGPU_*`, `MOD_PERF_XPASSES` (extra passes), `MOD_PERF_INTERP`, `MOD_PERF_SNAP`, `MOD_PERF_LATE` (passes that
missed their refresh), `MOD_PERF_PERIOD` (tick length, 789 lines), `MOD_PERF_FRAMES`; writing 1 to `MOD_PERF_RESET`
clears them.

**State checks.** With `MOD_FPS_TEST_TICK` the same N must be used in the runs being compared: forcing extra passes
alone lengthens the ticks, which moves the tick on which CD reads end and shifts the game's timeline (result boxes,
loads), so the runs would differ for reasons unrelated to rendering. With equal tick lengths, a whole wild battle, a
Grade D cup and world walks hash identically every tick at 20, 30 and 60 fps, interpolated or not. The scripts are in
`tools/dev/fps/` (its README lists them); driving the emulator and reading RAM by symbol: [../developing.md](../developing.md).

## Memory

The frame-rate work costs on the order of 25-30 KB of main-executable code and bss, which comes out of the heap
([memory.md](memory.md)). The main parts: the late tick table (0.5 KB), the map sprite draw list (1.5 KB), the rollback buffers
(0.5 KB), the previous bone values (5.6 KB), the saved matrix pool (4 KB), the render random log (1 KB), plus the
helper. `BTL_REL.BIN`, `STD_REL.BIN` and `VS_REL.BIN` each grow by two 5.6 KB rollback buffers and code and still fit
their load areas.

## Gotchas

- New render code must not change state: use a late tick (`addObjectLate`), a rollback set, or guard the side effect
  with `MOD_RENDER_PASS == 0`. Never skip the drawing itself on extra passes: its primitives live in the per-buffer work
  base, so a skipped object vanishes on those frames.
- New code must not add primitives from a tick, or it must replay them on extra passes.
- `rand()` and `randomLimit()` in a render must be `modRenderRand()`.
- Code that writes a bone's `coord` directly is excluded from interpolation automatically, but render code that moves
  a live entity must call `modInterpUnapplyEntity` first.
- A primitive or effect placed from `workm` follows the interpolated skeleton; one placed from `location` or the tick's
  state moves at 20 Hz.
- Sound and music are not tied to rendering (sequence playback runs on the libsnd interrupt; animation sounds are in
  `tickAnimation`), so they are unchanged.
- The title, Press Start, main menu and movies already run a tick per refresh and are not converted.
